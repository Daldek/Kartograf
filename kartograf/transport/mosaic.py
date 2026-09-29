"""
Generyczny fallback kaflowy: pobierz kafle -> zszyj -> przytnij do bbox.

Pierwszy konsument: etap 1 (kafelkowanie CZ exportImage powyzej limitu
15000x4100 px — deklarowanego przez usluge; realny limit ~8 Mpx, znany blad
K6); kolejny: wycinek PL (ADR-027); planowany: Saksonia (brak WCS, etap DE).
Nodata jest propagowane do wyniku — NIGDY nie zamieniane na 0.
"""

import math
import warnings
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio.transform import Affine

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import GridMismatchError, ValidationError
from kartograf.transform.raster import VRT_TYPES, vrt_xml

# Tolerancja w pikselach: siatki zgodne i bboxy lezace na linii siatki
# z dokladnoscia bledu zmiennoprzecinkowego nie moga ani dokladac kolumny,
# ani rozdzielac zrodel na rozne siatki. Szum zmiennoprzecinkowy wspolrzednych
# ~5e5..7e5 m to ~2e-11 px (5 m); realne rozjazdy arkuszy GUGiK (naglowki
# z 2-3 miejscami) to >= 2e-3 px — 1e-6 lezy 5 rzedow nad szumem i 3 pod
# najmniejszym realnym rozjazdem.
_GRID_TOL_PX = 1e-6


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


@dataclass(frozen=True)
class OffGridSource:
    """Zrodlo poza siatka odniesienia.

    ``dx_px``/``dy_px``: przesuniecie linii siatki zrodla wzgledem linii
    siatki odniesienia, w pikselach, w przedziale [-0,5; 0,5).
    """

    path: Path
    dx_px: float
    dy_px: float


@dataclass(frozen=True)
class SourceGrid:
    """Siatka pikseli zrodel mozaiki (``check_source_grid``).

    ``reference``: transformacja zrodla odniesienia — siatka WIEKSZOSCI zrodel
    (remis rozstrzyga kolejnosc wejscia). ``off_grid``: zrodla, ktorych linie
    siatki leza dalej niz ``_GRID_TOL_PX`` od linii odniesienia; puste = wszystkie
    zrodla na jednej siatce.
    """

    reference: Affine
    off_grid: tuple[OffGridSource, ...]

    def describe_off_grid(self, total: int, noun: str = "zrodel") -> str:
        """Tresc ``GridMismatchError``: liczba, najwieksze przesuniecie, do 10 nazw."""
        worst = max(max(abs(s.dx_px), abs(s.dy_px)) for s in self.off_grid)
        names = ", ".join(s.path.name for s in self.off_grid[:10])
        more = " ..." if len(self.off_grid) > 10 else ""
        return (
            f"{len(self.off_grid)} z {total} {noun} lezy na innej siatce pikseli "
            f"niz pozostale (maks. przesuniecie {worst:.3f} px): {names}{more}"
        )


def _phase_key(value: float, step: float) -> int:
    """Kubelek fazy linii siatki (w jednostkach tolerancji) — do wyboru siatki
    wiekszosci; faza tuz ponizej 1 to ta sama siatka co faza 0."""
    p = (value / step) % 1.0
    if p > 1.0 - _GRID_TOL_PX:
        p = 0.0
    return round(p / _GRID_TOL_PX)


def _shift_px(value: float, origin: float, step: float) -> float:
    """Przesuniecie linii siatki ``value`` wzgledem siatki ``origin + k * step``
    w pikselach, w przedziale [-0,5; 0,5) — owiniecie przez 1 jest w modulo."""
    return ((value - origin) / step + 0.5) % 1.0 - 0.5


def _source_grid(paths: list[Path], transforms: list[Affine]) -> SourceGrid:
    """``check_source_grid`` na gotowych transformacjach (bez otwierania plikow).

    Linie pionowe ``x0 + k * rx``, poziome ``y0 + k * ry`` (``y0`` to GORNA
    krawedz, ``transform.f``). Arkusze GUGiK zwykle leza na jednej siatce, ale
    NIE na wielokrotnosciach piksela (1977 arkuszy 5 m z cache Hydrografu:
    narozniki na 5k + 2,5 m; 84 arkusze 1 m na zywo 2026-09-29: k + 0,5 m) —
    stad siatka z transformacji. Nie zawsze: arkusze 5 m kampanii 2022 pod
    Krakowem maja kazdy inna faze (19 arkuszy, 19 faz; S5). Siatke wiekszosci
    wybieraja kubelki faz (``_phase_key``), ale o przynaleznosci KAZDEGO zrodla
    rozstrzyga odleglosc jego linii od linii odniesienia (``<= _GRID_TOL_PX``,
    z owinieciem przez 1) — dwa szumy po dwu stronach granicy kubelka nie moga
    dac falszywego bledu twardego.
    """
    for path, t in zip(paths, transforms, strict=True):
        if t.b != 0 or t.d != 0:
            raise ValidationError(f"obrocona siatka zrodla {path.name}")
    res_set = {(t.a, -t.e) for t in transforms}
    if len(res_set) > 1:
        raise ValidationError(f"niezgodne rozdzielczosci zrodel: {sorted(res_set)}")
    rx, ry = transforms[0].a, -transforms[0].e
    keys = [(_phase_key(t.c, rx), _phase_key(t.f, ry)) for t in transforms]
    majority = Counter(keys).most_common(1)[0][0]
    ref = transforms[keys.index(majority)]
    off_grid = []
    for path, t in zip(paths, transforms, strict=True):
        dx, dy = _shift_px(t.c, ref.c, rx), _shift_px(t.f, ref.f, ry)
        if abs(dx) > _GRID_TOL_PX or abs(dy) > _GRID_TOL_PX:
            off_grid.append(OffGridSource(path, dx, dy))
    return SourceGrid(reference=ref, off_grid=tuple(off_grid))


def check_source_grid(paths: Sequence[Path]) -> SourceGrid:
    """Siatka pikseli zrodel: odniesienie (wiekszosc) + zrodla spoza niej.

    Sama detekcja, bez decyzji — co zrobic ze zrodlami ``off_grid``, wybiera
    wolajacy: ``mosaic_and_crop(snap_to_source_grid=True)`` rzuca
    ``GridMismatchError`` (kopia pikseli 1:1 jest wtedy niemozliwa), a wycinek
    PL z warpem reprojektuje kazdy arkusz osobno na siatke wyniku
    (``download/cutout.py``, W1). Zrodla otwierane sa po jednym (tylko
    metadane). ``ValidationError``: brak zrodel, obrocona siatka (rotacja/skos
    w transformacji), rozne rozdzielczosci.
    """
    if not paths:
        raise ValidationError("check_source_grid: brak rastrow wejsciowych")
    resolved = [Path(p) for p in paths]
    transforms = []
    for path in resolved:
        with rasterio.open(path) as src:
            transforms.append(src.transform)
    return _source_grid(resolved, transforms)


def _snap_outward(
    bounds: tuple[float, float, float, float], ref: Affine
) -> tuple[float, float, float, float]:
    """Bounds rozszerzone NA ZEWNATRZ do linii siatki odniesienia (< 1 px)."""
    rx, ry = ref.a, -ref.e
    x0, y0 = ref.c, ref.f
    min_x, min_y, max_x, max_y = bounds
    return (
        x0 + math.floor((min_x - x0) / rx + _GRID_TOL_PX) * rx,
        y0 + math.floor((min_y - y0) / ry + _GRID_TOL_PX) * ry,
        x0 + math.ceil((max_x - x0) / rx - _GRID_TOL_PX) * rx,
        y0 + math.ceil((max_y - y0) / ry - _GRID_TOL_PX) * ry,
    )


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
    (review max 2026-08-30, zn. 1). Zrodlo spoza tej siatki (dalej niz
    ``_GRID_TOL_PX`` od jej linii) konczy sie ``GridMismatchError`` z lista
    przesuniec (``.off_grid``): ``merge`` przepisalby je "przez okno" —
    nie zawsze z najblizszego piksela i z kolumna/wierszem nodata na szwie
    (S5, testy na zywo 2026-09-29) — a wolajacy, ktory chce warpu, ma
    ``check_source_grid`` i reprojekcje per zrodlo. Zrodlo z obrocona siatka
    (rotacja/skos w transformie) konczy sie ``ValidationError``.

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
    spoza ``VRT_TYPES``; domyslny sterownik wyniku to GTiff, domyslnie bez
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
    # _source_grid konsumuje transformacje zrodel — wyprowadzone z metas,
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
            if band_type not in VRT_TYPES:
                raise ValidationError(
                    f"mosaic_and_crop: typ pasma {band_type!r} (zrodlo "
                    f"{path.name}) spoza obslugiwanych: {sorted(VRT_TYPES)}"
                )

    bounds = (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    if snap_to_source_grid:
        # Bez tego siatke wyniku kotwiczy rog bbox, a merge przepisuje piksele
        # najblizszym sasiadem: tresc przesuwa sie o ulamek piksela, a przy
        # remisie (bbox calkowity na siatce GUGiK z narozami w k + 0,5) sasiednie
        # kolumny mieszaja sie (review max 2026-08-30, zn. 1; fakt 2 planu).
        grid = _source_grid(paths, transforms)
        if grid.off_grid:
            raise GridMismatchError(grid.describe_off_grid(len(paths)), grid.off_grid)
        bounds = _snap_outward(bounds, grid.reference)

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
                xml = vrt_xml(
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


def has_valid_pixels(path: Path, nodata: float | None) -> bool:
    """Czy raster ma choc jeden piksel spoza nodata/NaN (wczesne wyjscie)."""
    with rasterio.open(path) as src:
        for _, window in src.block_windows(1):
            data = src.read(1, window=window)
            mask = np.isfinite(data)
            if nodata is not None:
                mask &= data != nodata
            if mask.any():
                return True
    return False
