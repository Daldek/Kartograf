"""
Lokalna reprojekcja rastra na zadana siatke, WYMUSZONA operacja przypieta.

Sparametryzowana kopia wzorca `providers/cuzk/dmr.py::_warp_to_grid`
(ADR-024) dla torow PL. Celowo NIE wspoldzielona z CZ: testy regresyjne
ADR-024 patchuja `kartograf.providers.cuzk.dmr.reproject`, a tor CZ jest
zweryfikowany na zywo — nie ruszamy go tuz przed wydaniem (ADR-027).
"""

import contextlib
import logging
import os
import threading
from pathlib import Path

import rasterio
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject

from kartograf.core.sheet_parser import BBox
from kartograf.transform.crs import PinnedTransform

logger = logging.getLogger(__name__)


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


def warp_to_grid(
    src_path: Path,
    dst_path: Path,
    bbox: BBox,
    pixel_size: float,
    pinned: PinnedTransform,
    *,
    src_crs: str,
    nodata: float,
) -> None:
    """Zreprojektuj raster na siatke ``bbox``/``pixel_size`` (``bbox.crs``).

    Operacja jest WYMUSZONA (`COORDINATE_OPERATION`) — bez tego GDAL wybiera
    ja sam, poza polityka `transform/crs.py` (zakaz ballparku, limit
    dokladnosci, probe). `src_nodata`/`dst_nodata` maskuja piksele puste,
    zeby nodata nie weszlo do interpolacji. Zapis atomowy: plik docelowy
    powstaje dopiero z gotowej kopii tymczasowej.
    """
    width = max(1, round((bbox.max_x - bbox.min_x) / pixel_size))
    height = max(1, round((bbox.max_y - bbox.min_y) / pixel_size))
    dst_transform = from_origin(bbox.min_x, bbox.max_y, pixel_size, pixel_size)
    tmp_path = dst_path.with_name(
        f"{dst_path.name}.{os.getpid()}_{threading.get_ident()}.warp.tif"
    )
    logger.debug(
        f"Reprojekcja lokalna {src_path.name} -> {bbox.crs}: "
        f"{pinned.description} (dokladnosc {pinned.accuracy_m} m)"
    )
    try:
        with rasterio.open(src_path) as src:
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
            with (
                rasterio.open(tmp_path, "w", **profile) as dst,
                _quiet_transformer_only_option(),
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
                )
        os.replace(tmp_path, dst_path)
    except BaseException:
        dst_path.unlink(missing_ok=True)
        raise
    finally:
        tmp_path.unlink(missing_ok=True)
