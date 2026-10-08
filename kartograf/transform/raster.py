"""
Local raster reprojection onto a given grid, with a FORCED pinned operation.

Shared warp of the PL (ADR-027) and CZ (ADR-024) paths (since 2026-10-06 the former copy
`providers/cuzk/dmr.py::_warp_to_grid` is removed - review D8/N7). Both paths
force the operation chosen by `transform/crs.py`, including the pinned
Czech S-JTSK datum step. A failure does not delete the previous result.
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
    """Is it the same CRS? A semantic comparison, not a textual one.

    `EPSG:2180` and `epsg:2180` are the same CRS - comparing strings alone
    would give false rejections, and rejecting a healthy call is worse than
    letting an oddly written CRS through.
    """
    if a == b:
        return True
    try:
        return bool(CRS.from_user_input(a) == CRS.from_user_input(b))
    except Exception:  # noqa: BLE001 — an unparsable CRS = not the same pair
        return False


@contextlib.contextmanager
def _quiet_transformer_only_option():
    """Silence one GDAL message: `COORDINATE_OPERATION` is a TRANSFORMER
    option, while `rasterio.warp.reproject` passes kwargs also as warper
    options - GDAL then logs a warning about an unknown option
    (`CPLE_NotSupported`). The operation works (the test
    `test_bbox_target_crs_puts_content_where_pyproj_says` checks this on
    content), but the warning would land on stderr on every PL/CZ warp. The filter
    is narrow (matched by option name) and removed immediately."""
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


# numpy/rasterio type -> GDAL type name in the VRT XML
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
    """Single-band 1:1 VRT over a source: forced SRS and band type.

    The source path is absolute (``relativeToVRT="0"``) - the VRT lives in
    ``/vsimem/``, a relative one would have nothing to refer to. ``meta``:
    the source's ``transform``, ``width``, ``height``.
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
    """Name of a 1:1 VRT in ``/vsimem/`` over a source: SRS and band type forced,
    the source's OWN nodata (mirrors the wrapping in ``mosaic_and_crop``).

    Why: ``reproject`` from a source WITHOUT a CRS (a GUGiK ASC sheet without ``.prj``)
    returns only nodata despite an explicit ``src_crs`` (measured 2026-09-29,
    rasterio 1.5), and a sheet with integers only is read by GDAL as
    Int32. The VRT holds no descriptor; the source is opened only by the VRT reader.
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
    """Reproject raster(s) onto the ``bbox``/``pixel_size`` grid (``bbox.crs``).

    The operation is FORCED (`COORDINATE_OPERATION`) - without it GDAL picks
    it itself, outside the `transform/crs.py` policy (ballpark ban, accuracy
    limit, probe). `src_nodata`/`dst_nodata` mask empty pixels so that
    nodata does not enter the interpolation. Atomic write: the target file
    is created only from a finished temporary copy - and since that is so, a failure
    does NOT
    delete ``dst_path``: if a previous result was there, it survives
    untouched (only the temporary file is cleaned up).

    ``sources`` is one raster or a list of them (W1, S5): each source is
    reprojected ONCE, from its own grid onto the result grid, into THE SAME
    target band (the first with ``init_dest_nodata=True``, the rest ``False``)
    - without an intermediate mosaic, so sheets with different grid phases are not
    first rewritten onto a common grid. In an overlap the FIRST list
    source wins (as in ``rasterio.merge``): GDAL overwrites valid pixels with
    the next source, while a source's nodata does NOT overwrite the predecessor's
    valid pixels (measured 2026-09-29), so the list is processed from the end.
    ``src_crs`` applies to every source (also an ASC without a CRS). Seams between
    sources are independent warps: the interpolator does not see the neighbor across
    the seam.

    The CRS pair must agree with ``pinned`` (if it knows it) - otherwise
    ``TransformError``. A forced operation makes ``src_crs`` dead
    for GDAL (measured: for the same pipeline 2180/4326/3857/32633/5514
    give an identical result), so the signature alone does not protect against passing a
    ``pinned`` built for a different pair than the one actually requested.
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
            # From the end of the list: the last reprojected source wins in an overlap,
            # so the first on the list ends up on top (as in `merge`).
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
        # We clean up ONLY the temporary file. We do not touch the target file:
        # on failure it is still the previous, valid result.
        tmp_path.unlink(missing_ok=True)
