"""
Stitch rasters on one grid and crop to a bbox.

Consumers: assembling chunks of one area request (``transport/chunks.py`` - CZ
exportImage, GUGiK WCS; ADR-034) and caller-provided raster mosaics.
Nodata is propagated to the result - NEVER replaced with 0.
"""

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.merge import merge
from rasterio.transform import Affine

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.transform.raster import VRT_TYPES, vrt_xml

# Tolerance in pixels: matching grids and bboxes lying on a grid line
# within floating-point error must neither add a column nor
# split the sources into different grids. Floating-point noise of coordinates
# ~5e5..7e5 m is ~2e-11 px (5 m); real offsets between GUGiK sheets (headers
# with 2-3 decimal places) are >= 2e-3 px - 1e-6 lies 5 orders above the noise and 3
# below
# the smallest real offset.
_GRID_TOL_PX = 1e-6


@dataclass(frozen=True)
class OffGridSource:
    """A source off the reference grid.

    ``dx_px``/``dy_px``: offset of the source's grid lines relative to the
    reference grid lines, in pixels, in the range [-0.5, 0.5).
    """

    path: Path
    dx_px: float
    dy_px: float


@dataclass(frozen=True)
class SourceGrid:
    """Pixel grid of the mosaic sources (``check_source_grid``).

    ``reference``: transform of the reference source - the grid of the MAJORITY of
    sources (a tie is broken by input order). ``off_grid``: sources whose grid
    lines lie farther than ``_GRID_TOL_PX`` from the reference lines; empty = all
    sources on one grid.
    """

    reference: Affine
    off_grid: tuple[OffGridSource, ...]

    def describe_off_grid(self, total: int, noun: str = "zrodel") -> str:
        """Description of ``off_grid``: count, largest offset, up to 10 names."""
        worst = max(max(abs(s.dx_px), abs(s.dy_px)) for s in self.off_grid)
        names = ", ".join(s.path.name for s in self.off_grid[:10])
        more = " ..." if len(self.off_grid) > 10 else ""
        return (
            f"{len(self.off_grid)} z {total} {noun} lezy na innej siatce pikseli "
            f"niz pozostale (maks. przesuniecie {worst:.3f} px): {names}{more}"
        )


def _phase_key(value: float, step: float) -> int:
    """Bucket of a grid line's phase (in tolerance units) - for choosing the
    majority grid; a phase just below 1 is the same grid as phase 0."""
    p = (value / step) % 1.0
    if p > 1.0 - _GRID_TOL_PX:
        p = 0.0
    return round(p / _GRID_TOL_PX)


def _shift_px(value: float, origin: float, step: float) -> float:
    """Offset of the grid line ``value`` relative to the grid ``origin + k * step``
    in pixels, in the range [-0.5, 0.5) - wrapping by 1 is done by the modulo."""
    return ((value - origin) / step + 0.5) % 1.0 - 0.5


def _source_grid(paths: list[Path], transforms: list[Affine]) -> SourceGrid:
    """``check_source_grid`` on ready-made transforms (without opening files).

    Vertical lines ``x0 + k * rx``, horizontal ``y0 + k * ry`` (``y0`` is the TOP
    edge, ``transform.f``). GUGiK sheets usually lie on one grid, but
    NOT on pixel multiples (1977 5 m sheets from the Hydrograf cache:
    corners at 5k + 2.5 m; 84 1 m sheets live 2026-09-29: k + 0.5 m) -
    hence the grid from transforms. Not always: 5 m sheets of the 2022 campaign near
    Krakow each have a different phase (19 sheets, 19 phases; S5). The majority grid is
    chosen by phase buckets (``_phase_key``), but the membership of EACH source is
    decided by the distance of its lines from the reference lines (``<= _GRID_TOL_PX``,
    with wrapping by 1) - two noise values on either side of a bucket boundary must not
    give a false hard error.
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
    """Pixel grid of the sources: reference (majority) + sources off it.

    Detection only, no decisions - callers can inspect ``off_grid`` and
    reproject sources individually if needed. Sources are opened one at a time
    (metadata only). ``ValidationError``: no sources, a rotated grid
    (rotation/skew in the transform), differing resolutions.
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
    """Bounds expanded OUTWARD to the reference grid lines (< 1 px)."""
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
    dtype: str | None = None,
) -> Path:
    """Stitch the input rasters and crop to bbox; return output_path.

    ``dst_kwds`` overrides the output profile (e.g. driver/CRS when ASC sources
    lack them).

    Sources are opened ONE AT A TIME: metadata is read by a sequential loop (one
    descriptor at a time), while ``merge`` gets PATHS and opens the sources itself one
    at a time, per chunk of the result. A 75 x 75 km cutout is >1200 sheets, and the
    default descriptor limit is 1024 (Linux; macOS 256) - keeping all sources open at
    once ended in "Too many open files" only AFTER a multi-hour download (review max
    2026-08-30, finding 3).

    ``dtype`` (default ``None``): when given, each source is wrapped in a
    single-band 1:1 VRT in ``/vsimem/`` with its own CRS and nodata and the
    requested band type. An integer source before a floating-point source
    would otherwise truncate floating-point values when ``merge`` takes the
    first source's type. Wrapping rejects multiband sources and band types
    outside ``VRT_TYPES``; the default result driver is GTiff, without tiles
    unless explicitly enabled in ``dst_kwds``.

    Without ``dtype`` all sources must share one band type: ``merge`` would take the
    type of the FIRST source (e.g. float heights silently truncated to integers), so
    mixed types end in ``ValidationError`` asking for ``dtype=``.
    """
    if not inputs:
        raise ValidationError("mosaic_and_crop: brak rastrow wejsciowych")

    output_path = Path(output_path)
    paths = [Path(p) for p in inputs]
    wrap = dtype is not None

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

    crs_set = {str(m["crs"]) for m in metas}
    if len(crs_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne CRS wejsc: {sorted(crs_set)}"
        )
    if len(res_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne rozdzielczosci wejsc: {sorted(res_set)}"
        )
    if dtype is None:
        dtype_set = {m["dtype"] for m in metas}
        if len(dtype_set) > 1:
            raise ValidationError(
                "mosaic_and_crop: zrodla maja rozne typy pasm "
                f"({', '.join(sorted(dtype_set))}) — podaj dtype="
            )
    if wrap:
        for path, meta in zip(paths, metas, strict=True):
            if meta["count"] != 1:
                raise ValidationError(
                    f"mosaic_and_crop: zrodlo {path.name} ma {meta['count']} "
                    "pasm — owijanie w VRT (dtype) obsluguje tylko "
                    "rastry jednopasmowe"
                )
            band_type = dtype or meta["dtype"]
            if band_type not in VRT_TYPES:
                raise ValidationError(
                    f"mosaic_and_crop: typ pasma {band_type!r} (zrodlo "
                    f"{path.name}) spoza obslugiwanych: {sorted(VRT_TYPES)}"
                )

    bounds = (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)

    # merge opens the file for writing from dst_path itself (hence mkdir BEFORE
    # the call) and computes the result in chunks per mem_limit; without dst_path
    # the whole raster would load into one array in RAM - a peak of 2.63x
    # the data size, i.e. about 2.4 GB for a 30x30 km catchment at DMR 5G.
    # merge takes the output profile from the FIRST source.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kwds: dict = {}
    if nodata is not None:
        kwds["nodata"] = nodata
    if dst_kwds:
        kwds.update(dst_kwds)
    if wrap:
        # The first source is a VRT: without this, a result without dst_kwds would
        # be written with the VRT driver ("Writing through VRTSourcedRasterBand
        # is not supported").
        kwds.setdefault("driver", "GTiff")
        # ...and would inherit the VRT tiles min(128, w) x min(128, h) (tiled for
        # a source wider than 128 px): a height < 128 not divisible by 16
        # ended the GTiff write with RasterBlockError. Explicit tiles from dst_kwds
        # win (setdefault).
        kwds.setdefault("tiled", False)

    # VRTs in /vsimem/ hold no descriptors; merge opens each VRT (and its
    # source beneath) one at a time.
    memfiles: list[MemoryFile] = []
    try:
        if wrap:
            sources: list = []
            for path, meta in zip(paths, metas, strict=True):
                wkt = meta["crs"].to_wkt() if meta["crs"] else None
                xml = vrt_xml(
                    path,
                    meta,
                    crs_wkt=wkt,
                    dtype=dtype or meta["dtype"],
                    # NoDataValue = the source's OWN nodata, not the mosaic's:
                    # SimpleSource copies pixels 1:1, so a different value would
                    # unmask the source's nodata and, in a sheet overlap,
                    # cover valid data of the next source. The RESULT's nodata
                    # is set by merge (the nodata parameter), as without wrapping.
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
    """Whether the raster has at least one pixel other than nodata/NaN (early exit)."""
    with rasterio.open(path) as src:
        for _, window in src.block_windows(1):
            data = src.read(1, window=window)
            mask = np.isfinite(data)
            if nodata is not None:
                mask &= data != nodata
            if mask.any():
                return True
    return False
