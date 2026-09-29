"""
Lokalna reprojekcja rastra na zadana siatke, WYMUSZONA operacja przypieta.

Sparametryzowany wzorzec `providers/cuzk/dmr.py::_warp_to_grid`
(ADR-024) dla torow PL (ADR-027). Oba tory wymuszaja operacje wybrana przez
`transform/crs.py`, wlacznie z przypietym czeskim krokiem datum S-JTSK.
"""

import contextlib
import logging
import os
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path
from xml.sax.saxutils import escape

import rasterio
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import reproject

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.transform.crs import PinnedTransform, TransformError

logger = logging.getLogger(__name__)


def _same_crs(a: str, b: str) -> bool:
    """Czy to ten sam uklad? Porownanie semantyczne, nie tekstowe.

    `EPSG:2180` i `epsg:2180` to ten sam uklad — samo porownanie stringow
    dawaloby falszywe odrzuty, a odrzut zdrowego wywolania jest gorszy niz
    przepuszczenie dziwnie zapisanego ukladu.
    """
    if a == b:
        return True
    try:
        return bool(CRS.from_user_input(a) == CRS.from_user_input(b))
    except Exception:  # noqa: BLE001 — nieparsowalny uklad = nie ta sama para
        return False


@contextlib.contextmanager
def _quiet_transformer_only_option():
    """Wycisz jeden komunikat GDAL: `COORDINATE_OPERATION` jest opcja
    TRANSFORMERA, a `rasterio.warp.reproject` podaje kwargs takze jako opcje
    warpera — GDAL loguje wtedy ostrzezenie o nieznanej opcji (lustro filtra
    z providers/cuzk/dmr.py)."""
    gdal_logger = logging.getLogger("rasterio._env")

    class _Filter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "COORDINATE_OPERATION" not in record.getMessage()

    _filter = _Filter()
    gdal_logger.addFilter(_filter)
    try:
        yield
    finally:
        gdal_logger.removeFilter(_filter)


# typ numpy/rasterio -> nazwa typu GDAL w XML VRT
VRT_TYPES = {
    "uint8": "Byte",
    "int16": "Int16",
    "uint16": "UInt16",
    "int32": "Int32",
    "uint32": "UInt32",
    "float32": "Float32",
    "float64": "Float64",
}


def vrt_xml(path: Path, meta: dict, *, crs_wkt: str | None, dtype: str, nodata) -> str:
    """Jednopasmowy VRT 1:1 nad zrodlem: wymuszony SRS i typ pasma.

    Sciezka zrodla absolutna (``relativeToVRT="0"``) — VRT zyje w
    ``/vsimem/``, wzgledna nie mialaby do czego sie odnosic. ``meta``:
    ``transform``, ``width``, ``height`` zrodla.
    """
    t = meta["transform"]
    srs = f"<SRS>{escape(crs_wkt)}</SRS>" if crs_wkt else ""
    nodata_xml = f"<NoDataValue>{nodata!r}</NoDataValue>" if nodata is not None else ""
    source = escape(os.path.abspath(path))
    return (
        f'<VRTDataset rasterXSize="{meta["width"]}" rasterYSize="{meta["height"]}">'
        f"{srs}<GeoTransform>{t.c!r}, {t.a!r}, {t.b!r}, {t.f!r}, {t.d!r}, {t.e!r}"
        f'</GeoTransform><VRTRasterBand dataType="{VRT_TYPES[dtype]}" band="1">'
        f'{nodata_xml}<SimpleSource><SourceFilename relativeToVRT="0">{source}'
        "</SourceFilename><SourceBand>1</SourceBand></SimpleSource>"
        "</VRTRasterBand></VRTDataset>"
    )


@contextlib.contextmanager
def _vrt_over(path: Path, *, crs_wkt: str, dtype: str) -> Iterator[str]:
    """Nazwa VRT 1:1 w ``/vsimem/`` nad zrodlem: SRS i typ pasma wymuszone,
    nodata WLASNE zrodla (lustro owijania w ``mosaic_and_crop``).

    Po co: ``reproject`` ze zrodla BEZ CRS (arkusz ASC GUGiK bez ``.prj``)
    zwraca sam nodata mimo jawnego ``src_crs`` (zmierzone 2026-09-29,
    rasterio 1.5), a arkusz z samymi liczbami calkowitymi GDAL czyta jako
    Int32. VRT nie trzyma deskryptora; zrodlo otwiera dopiero czytelnik VRT.
    """
    with rasterio.open(path) as src:
        if src.count != 1:
            raise ValidationError(
                f"warp_to_grid: zrodlo {path.name} ma {src.count} pasm — "
                "reprojekcja obsluguje tylko rastry jednopasmowe"
            )
        meta = {"transform": src.transform, "width": src.width, "height": src.height}
        nodata = src.nodata
    memfile = MemoryFile(
        vrt_xml(path, meta, crs_wkt=crs_wkt, dtype=dtype, nodata=nodata).encode(),
        ext=".vrt",
    )
    try:
        yield memfile.name
    finally:
        memfile.close()


def warp_to_grid(
    sources: Path | Sequence[Path],
    dst_path: Path,
    bbox: BBox,
    pixel_size: float,
    pinned: PinnedTransform,
    *,
    src_crs: str,
    nodata: float,
) -> None:
    """Zreprojektuj raster(y) na siatke ``bbox``/``pixel_size`` (``bbox.crs``).

    Operacja jest WYMUSZONA (`COORDINATE_OPERATION`) — bez tego GDAL wybiera
    ja sam, poza polityka `transform/crs.py` (zakaz ballparku, limit
    dokladnosci, probe). `src_nodata`/`dst_nodata` maskuja piksele puste,
    zeby nodata nie weszlo do interpolacji. Zapis atomowy: plik docelowy
    powstaje dopiero z gotowej kopii tymczasowej — a skoro tak, awaria NIE
    kasuje ``dst_path``: jesli lezal tam poprzedni wynik, przezywa on
    nietkniety (sprzatany jest tylko plik tymczasowy).

    ``sources`` to jeden raster albo ich lista (W1, S5): kazde zrodlo jest
    reprojektowane RAZ, ze swojej siatki na siatke wyniku, do TEGO SAMEGO
    pasma docelowego (pierwsze z ``init_dest_nodata=True``, kolejne ``False``)
    — bez mozaiki posredniej, wiec arkusze o roznych fazach siatki nie sa
    najpierw przepisywane na wspolna siatke. W zakladce wygrywa PIERWSZE
    zrodlo listy (jak w ``rasterio.merge``): GDAL nadpisuje wazne piksele
    kolejnym zrodlem, a nodata zrodla NIE nadpisuje waznych pikseli
    poprzednika (zmierzone 2026-09-29), wiec lista jest przetwarzana od konca.
    ``src_crs`` obowiazuje kazde zrodlo (takze ASC bez CRS). Szwy miedzy
    zrodlami to niezalezne warpy: interpolator nie widzi sasiada zza szwu.

    Para ukladow musi zgadzac sie z ``pinned`` (o ile ten ja zna) — inaczej
    ``TransformError``. Wymuszona operacja czyni bowiem ``src_crs`` martwym
    dla GDAL-a (zmierzone: dla tego samego pipeline'u 2180/4326/3857/32633/5514
    daja identyczny wynik), wiec sama sygnatura nie chroni przed podaniem
    ``pinned`` zbudowanego dla innej pary niz faktycznie zadana.
    """
    if (pinned.src_crs is not None and not _same_crs(pinned.src_crs, src_crs)) or (
        pinned.dst_crs is not None and not _same_crs(pinned.dst_crs, bbox.crs)
    ):
        raise TransformError(
            f"Niespojna para ukladow: operacja przypieta to "
            f"{pinned.src_crs} -> {pinned.dst_crs}, a zadana reprojekcja "
            f"{src_crs} -> {bbox.crs} [{pinned.description}]"
        )
    paths = (
        [Path(sources)]
        if isinstance(sources, (str, Path))
        else [Path(p) for p in sources]
    )
    if not paths:
        raise ValidationError("warp_to_grid: brak rastrow wejsciowych")
    width = max(1, round((bbox.max_x - bbox.min_x) / pixel_size))
    height = max(1, round((bbox.max_y - bbox.min_y) / pixel_size))
    dst_transform = from_origin(bbox.min_x, bbox.max_y, pixel_size, pixel_size)
    tmp_path = dst_path.with_name(
        f"{dst_path.name}.{os.getpid()}_{threading.get_ident()}.warp.tif"
    )
    more = f" (+{len(paths) - 1} zrodel)" if len(paths) > 1 else ""
    logger.debug(
        f"Reprojekcja lokalna {paths[0].name}{more} -> {bbox.crs}: "
        f"{pinned.description} (dokladnosc {pinned.accuracy_m} m)"
    )
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": width,
        "height": height,
        "crs": CRS.from_string(bbox.crs),
        "transform": dst_transform,
        "nodata": nodata,
    }
    src_wkt = CRS.from_string(src_crs).to_wkt()
    try:
        with (
            rasterio.open(tmp_path, "w", **profile) as dst,
            _quiet_transformer_only_option(),
        ):
            # Od konca listy: ostatnie reprojektowane zrodlo wygrywa w zakladce,
            # wiec pierwsze na liscie laduje na wierzchu (jak w `merge`).
            for i, path in enumerate(reversed(paths)):
                with (
                    _vrt_over(path, crs_wkt=src_wkt, dtype="float32") as name,
                    rasterio.open(name) as src,
                ):
                    reproject(
                        source=rasterio.band(src, 1),
                        destination=rasterio.band(dst, 1),
                        src_crs=CRS.from_string(src_crs),
                        src_nodata=nodata,
                        dst_crs=CRS.from_string(bbox.crs),
                        dst_nodata=nodata,
                        resampling=Resampling.bilinear,
                        COORDINATE_OPERATION=pinned.gdal_operation(),
                        init_dest_nodata=i == 0,
                    )
        os.replace(tmp_path, dst_path)
    finally:
        # Sprzatamy WYLACZNIE plik tymczasowy. Pliku docelowego nie ruszamy:
        # przy awarii jest to nadal poprzedni, poprawny wynik.
        tmp_path.unlink(missing_ok=True)
