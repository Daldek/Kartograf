"""
Generyczny fallback kaflowy: pobierz kafle -> zszyj -> przytnij do bbox.

Pierwszy konsument: etap 1 (kafelkowanie CZ exportImage powyzej limitu
15000x4100 px); kolejni: Saksonia (brak WCS), wycinek PL (ADR-027). Nodata
jest propagowane do wyniku — NIGDY nie zamieniane na 0.
"""

import logging
import math
import os
import warnings
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

import rasterio
from pyproj import CRS
from rasterio.io import MemoryFile
from rasterio.merge import merge

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Tolerancja w pikselach: siatki zgodne i bboxy lezace na linii siatki
# z dokladnoscia bledu zmiennoprzecinkowego nie moga ani dokladac kolumny,
# ani rozdzielac zrodel na rozne siatki.
_GRID_TOL_PX = 1e-6

# typ numpy/rasterio -> nazwa typu GDAL w XML VRT
_VRT_TYPES = {
    "uint8": "Byte",
    "int16": "Int16",
    "uint16": "UInt16",
    "int32": "Int32",
    "uint32": "UInt32",
    "float32": "Float32",
    "float64": "Float64",
}


def _vrt_xml(path: Path, meta: dict, *, crs_wkt: str | None, dtype: str, nodata) -> str:
    """Jednopasmowy VRT 1:1 nad zrodlem: wymuszony SRS i typ pasma.

    Sciezka zrodla absolutna (``relativeToVRT="0"``) — VRT zyje w
    ``/vsimem/``, wzgledna nie mialaby do czego sie odnosic.
    """
    t = meta["transform"]
    srs = f"<SRS>{escape(crs_wkt)}</SRS>" if crs_wkt else ""
    nodata_xml = f"<NoDataValue>{nodata!r}</NoDataValue>" if nodata is not None else ""
    source = escape(os.path.abspath(path))
    return (
        f'<VRTDataset rasterXSize="{meta["width"]}" rasterYSize="{meta["height"]}">'
        f"{srs}<GeoTransform>{t.c!r}, {t.a!r}, {t.b!r}, {t.f!r}, {t.d!r}, {t.e!r}"
        f'</GeoTransform><VRTRasterBand dataType="{_VRT_TYPES[dtype]}" band="1">'
        f'{nodata_xml}<SimpleSource><SourceFilename relativeToVRT="0">{source}'
        "</SourceFilename><SourceBand>1</SourceBand></SimpleSource>"
        "</VRTRasterBand></VRTDataset>"
    )


def _same_projection(src_crs, target: CRS) -> bool:
    """Czy CRS zrodla to uklad wymuszany?

    Samo ``CRS.equals(..., ignore_axis_order=True)`` NIE wystarcza: kazdy WKT1
    EPSG:2180 (WKT1_GDAL z pyproj, ESRI, ``gdalsrsinfo -o wkt_simple`` z .prj
    Hydrografu) daje False (zmierzone 2026-09-28, pyproj 3.7.2 / PROJ 9.5.1),
    wiec porownujemy takze parametry odwzorowania (slownik PROJ.4).
    """
    candidate = CRS.from_user_input(src_crs.to_wkt())
    if candidate.equals(target, ignore_axis_order=True):
        return True
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # to_dict() ostrzega o PROJ.4
        return candidate.to_dict() == target.to_dict()


def _phase(value: float, step: float) -> int:
    """Polozenie linii siatki w obrebie piksela (w jednostkach tolerancji).

    Dwie siatki o tym samym kroku sa zgodne, gdy fazy sa rowne; faza tuz
    ponizej 1 to ta sama siatka co faza 0.
    """
    p = (value / step) % 1.0
    if p > 1.0 - _GRID_TOL_PX:
        p = 0.0
    return round(p / _GRID_TOL_PX)


def _snap_outward(
    bounds: tuple[float, float, float, float],
    paths: list[Path],
    transforms: list,
) -> tuple[tuple[float, float, float, float], list[tuple[Path, float, float]]]:
    """Bounds rozszerzone na zewnatrz do siatki zrodel + zrodla spoza niej.

    Siatka odniesienia = siatka WIEKSZOSCI zrodel (remis: pierwszej w
    kolejnosci wejscia). Linie pionowe ``x0 + k * rx``, poziome ``y0 + k * ry``
    (``y0`` to GORNA krawedz, ``transform.f``). Arkusze GUGiK jednego produktu
    leza na jednej siatce, ale NIE na wielokrotnosciach piksela (zmierzone na
    1977 arkuszach 5 m: narozniki na 5k + 2,5 m) — stad siatka z transformacji.
    Zrodlo spoza siatki nie jest bledem (arkusze sa juz w cache, blad bylby
    trwaly): wraca na liscie z przesunieciem w pikselach, a jego tresc merge
    przepisze metoda najblizszego sasiada.
    """
    for path, t in zip(paths, transforms, strict=True):
        if t.b != 0 or t.d != 0:
            raise ValidationError(
                f"mosaic_and_crop: obrocona siatka zrodla {path.name}"
            )
    rx, ry = transforms[0].a, -transforms[0].e
    keys = [(_phase(t.c, rx), _phase(t.f, ry)) for t in transforms]
    majority = Counter(keys).most_common(1)[0][0]
    ref = transforms[keys.index(majority)]
    x0, y0 = ref.c, ref.f
    off_grid = [
        (
            path,
            ((t.c - x0) / rx + 0.5) % 1.0 - 0.5,
            ((t.f - y0) / ry + 0.5) % 1.0 - 0.5,
        )
        for path, t, key in zip(paths, transforms, keys, strict=True)
        if key != majority
    ]
    min_x, min_y, max_x, max_y = bounds
    snapped = (
        x0 + math.floor((min_x - x0) / rx + _GRID_TOL_PX) * rx,
        y0 + math.floor((min_y - y0) / ry + _GRID_TOL_PX) * ry,
        x0 + math.ceil((max_x - x0) / rx - _GRID_TOL_PX) * rx,
        y0 + math.ceil((max_y - y0) / ry - _GRID_TOL_PX) * ry,
    )
    return snapped, off_grid


def mosaic_and_crop(
    inputs: list[Path],
    bbox: BBox,
    output_path: Path,
    *,
    nodata: float | None = None,
    dst_kwds: dict | None = None,
    snap_to_source_grid: bool = False,
    assign_crs: str | None = None,
    dtype: str | None = None,
) -> Path:
    """Zszyj rastry wejsciowe i przytnij do bbox; zwroc output_path.

    ``dst_kwds`` nadpisuje profil wyjscia (np. driver/CRS, gdy zrodla ASC
    ich nie maja).

    Zrodla otwierane sa POJEDYNCZO: metadane czyta petla sekwencyjna (jeden
    deskryptor naraz), a ``merge`` dostaje SCIEZKI i sam otwiera zrodla po
    jednym, per kawalek wyniku. Wycinek 75 x 75 km to >1200 arkuszy, a domyslny
    limit deskryptorow to 1024 (Linux; macOS 256) — trzymanie wszystkich
    zrodel otwartych naraz konczylo sie "Too many open files" dopiero PO
    wielogodzinnym pobraniu (review max 2026-08-30, zn. 3).

    ``snap_to_source_grid`` (domyslnie ``False``, tor CZ bez zmian): przed
    przycieciem rozszerza bbox NA ZEWNATRZ do linii siatki pikseli zrodel
    (siatka WIEKSZOSCI zrodel; remis rozstrzyga kolejnosc wejscia), wiec
    wynik kopiuje piksele zrodel 1:1 zamiast przesuwac tresc o ulamek piksela
    (review max 2026-08-30, zn. 1). Zrodlo spoza tej siatki NIE przerywa
    mozaikowania (arkusze sa juz w cache — blad bylby trwaly): idzie do
    ``logger.warning`` z przesunieciem w px, a jego tresc ``merge`` przepisze
    najblizszym sasiadem. Zrodlo z obrocona siatka (rotacja/skos w transformie)
    konczy sie ``ValidationError``.

    ``assign_crs`` / ``dtype`` (domyslnie ``None``, tor CZ bez zmian): gdy
    ktorys jest podany, kazde zrodlo owijane jest w jednopasmowy VRT 1:1 w
    ``/vsimem/`` z SRS = ``assign_crs`` (albo wlasny CRS zrodla) i typem pasma
    = ``dtype`` (albo wlasny); ``merge`` dostaje nazwy VRT, a VRT niesie
    nodata WLASNE zrodla, wiec maskowanie pikseli jest takie jak bez owijania.
    Po co: Hydrograf dopisuje ``.prj`` (EPSG:2180) do czesci arkuszy ASC —
    arkusz z ``.prj`` ma CRS, swiezy bez niego ``None``, i ``merge`` rzucal
    ``CRS mismatch``; arkusz ASC z samymi liczbami calkowitymi GDAL czyta
    jako Int32, a ``merge`` bierze typ z PIERWSZEGO zrodla, wiec calosc
    bylaby obcieta do liczb calkowitych. Z ``assign_crs`` zrodlo bez CRS
    jest dozwolone, a zrodlo z WLASNYM CRS innym niz wymuszany konczy sie
    ``ValidationError`` (wymuszenie nie przelicza wspolrzednych). Przy
    owijaniu ``ValidationError`` daje tez zrodlo wielopasmowe i typ pasma
    spoza ``_VRT_TYPES``; domyslny sterownik wyniku to GTiff, domyslnie bez
    kafli (``tiled=False``; jawne kafle w ``dst_kwds`` wygrywaja) — profil
    wyjscia ``merge`` bierze z pierwszego zrodla, czyli z VRT.
    """
    if not inputs:
        raise ValidationError("mosaic_and_crop: brak rastrow wejsciowych")

    output_path = Path(output_path)
    paths = [Path(p) for p in inputs]
    wrap = assign_crs is not None or dtype is not None

    res_set: set[tuple[float, float]] = set()
    metas: list[dict] = []
    for path in paths:
        with rasterio.open(path) as src:
            res_set.add(src.res)
            metas.append(
                {
                    "crs": src.crs,
                    "transform": src.transform,
                    "width": src.width,
                    "height": src.height,
                    "count": src.count,
                    "dtype": src.dtypes[0],
                    "nodata": src.nodata,
                }
            )
    # _snap_outward konsumuje transformacje zrodel — wyprowadzone z metas,
    # bez drugiej petli otwierajacej pliki.
    transforms = [m["transform"] for m in metas]

    if assign_crs is None:
        crs_set = {str(m["crs"]) for m in metas}
        if len(crs_set) > 1:
            raise ValidationError(
                f"mosaic_and_crop: niezgodne CRS wejsc: {sorted(crs_set)}"
            )
    else:
        # CRS None (ASC bez .prj) obok EPSG:2180 jest dozwolony — VRT nada
        # mu SRS; odrzucamy tylko zrodlo z WLASNYM, innym ukladem.
        target = CRS.from_user_input(assign_crs)
        for path, meta in zip(paths, metas, strict=True):
            if meta["crs"] is not None and not _same_projection(meta["crs"], target):
                raise ValidationError(
                    f"mosaic_and_crop: zrodlo {path.name} ma CRS {meta['crs']}, "
                    f"a wymuszany jest {assign_crs}"
                )
    if len(res_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne rozdzielczosci wejsc: {sorted(res_set)}"
        )
    if wrap:
        for path, meta in zip(paths, metas, strict=True):
            if meta["count"] != 1:
                raise ValidationError(
                    f"mosaic_and_crop: zrodlo {path.name} ma {meta['count']} "
                    "pasm — owijanie w VRT (assign_crs/dtype) obsluguje tylko "
                    "rastry jednopasmowe"
                )
            band_type = dtype or meta["dtype"]
            if band_type not in _VRT_TYPES:
                raise ValidationError(
                    f"mosaic_and_crop: typ pasma {band_type!r} (zrodlo "
                    f"{path.name}) spoza obslugiwanych: {sorted(_VRT_TYPES)}"
                )

    bounds = (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    if snap_to_source_grid:
        # Bez tego siatke wyniku kotwiczy rog bbox, a merge przepisuje piksele
        # najblizszym sasiadem: tresc przesuwa sie o ulamek piksela, a przy
        # remisie (bbox calkowity na siatce GUGiK z narozami w k + 0,5) sasiednie
        # kolumny mieszaja sie (review max 2026-08-30, zn. 1; fakt 2 planu).
        bounds, off_grid = _snap_outward(bounds, paths, transforms)
        if off_grid:
            worst = max(max(abs(dx), abs(dy)) for _, dx, dy in off_grid)
            names = ", ".join(p.name for p, _, _ in off_grid[:10])
            logger.warning(
                f"mosaic_and_crop: {len(off_grid)} z {len(paths)} zrodel poza "
                f"siatka pikseli wiekszosci (maks. przesuniecie {worst:.3f} px) "
                f"— ich tresc przepisana najblizszym sasiadem: {names}"
                + (" ..." if len(off_grid) > 10 else "")
            )

    # merge z dst_path sam otwiera plik do zapisu (stad mkdir PRZED
    # wywolaniem) i liczy wynik kawalkami wg mem_limit; bez dst_path
    # caly raster ladowalby do jednej tablicy w RAM — szczyt 2,63x
    # rozmiaru danych, czyli ok. 2,4 GB dla zlewni 30x30 km przy DMR 5G.
    # Profil wyjscia merge bierze z PIERWSZEGO zrodla.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kwds: dict = {}
    if nodata is not None:
        kwds["nodata"] = nodata
    if dst_kwds:
        kwds.update(dst_kwds)
    if wrap:
        # Pierwsze zrodlo to VRT: bez tego wynik bez dst_kwds zapisywalby sie
        # sterownikiem VRT ("Writing through VRTSourcedRasterBand is not
        # supported").
        kwds.setdefault("driver", "GTiff")
        # ...i dziedziczylby kafle VRT min(128, w) x min(128, h) (tiled dla
        # zrodla szerszego niz 128 px): wysokosc < 128 niepodzielna przez 16
        # konczyla zapis GTiff RasterBlockError. Jawne kafle z dst_kwds
        # wygrywaja (setdefault).
        kwds.setdefault("tiled", False)

    # Owijanie PO przyciaganiu: transformacje VRT = transformacje zrodel, wiec
    # siatka policzona na oryginalach jest wazna. VRT w /vsimem/ nie trzyma
    # deskryptorow; merge otwiera je (i zrodla pod nimi) po jednym.
    memfiles: list[MemoryFile] = []
    try:
        if wrap:
            forced_wkt = (
                CRS.from_user_input(assign_crs).to_wkt() if assign_crs else None
            )
            sources: list = []
            for path, meta in zip(paths, metas, strict=True):
                wkt = forced_wkt or (meta["crs"].to_wkt() if meta["crs"] else None)
                xml = _vrt_xml(
                    path,
                    meta,
                    crs_wkt=wkt,
                    dtype=dtype or meta["dtype"],
                    # NoDataValue = nodata WLASNE zrodla, nie mozaiki:
                    # SimpleSource kopiuje piksele 1:1, wiec inna wartosc
                    # odmaskowalaby nodata zrodla i w zakladce arkuszy
                    # przykrylaby wazne dane nastepnego zrodla. Nodata WYNIKU
                    # ustawia merge (parametr nodata), jak bez owijania.
                    nodata=meta["nodata"],
                )
                memfile = MemoryFile(xml.encode(), ext=".vrt")
                memfiles.append(memfile)
                sources.append(memfile.name)
        else:
            sources = paths
        merge(
            sources,
            bounds=bounds,
            nodata=nodata,
            dst_path=str(output_path),
            dst_kwds=kwds or None,
        )
    finally:
        for memfile in memfiles:
            memfile.close()
    return output_path
