"""
Area requests split into chunks: align -> plan -> fetch and stitch (ADR-034).

Consumers: CZ exportImage (``providers/cuzk/client.py``, budget 4 Mpx below the
measured ~8 Mpx limit) and GUGiK WCS NMT 1 m (``providers/pl/wcs.py``, budget
16 Mpx - a reliability budget, the server has no limit up to 100 Mpx;
``docs/research/2026-10-10-wcs-limits/raport.md``). The module knows no services,
URLs or CRSs: the caller supplies ``fetch(chunk, path)``.

Chunks share one grid anchored at the NW corner of the aligned bbox and are cut on
whole pixels, so stitching copies pixels 1:1 (measured bit for bit against one
request, report point 5). Why NW: the mosaic result grid starts at max_y and has
height round((max_y - min_y) / res), so for a bbox of fractional height an SW
anchor diverges from it by 0 < delta < res - the bottom row of the result falls
below the chunk extent and the content is shifted by up to 1 px, invisibly in
metadata (ADR-024, A3-1).
"""

import math
import os
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rasterio
from rasterio.transform import Affine

from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.messages import message, reason
from kartograf.transport.mosaic import _snap_outward, mosaic_and_crop


@dataclass(frozen=True)
class GridSpec:
    """Pixel grid of a service: step and the position of one grid line.

    The service resamples to the REQUESTED grid (GUGiK WCS: nearest neighbour), so
    a bbox off the source grid shifts content by a fraction of a pixel against its
    georeference; requests are therefore aligned to this grid.
    """

    step: float
    origin_x: float = 0.0
    origin_y: float = 0.0


@dataclass(frozen=True)
class ChunkLimits:
    """Per-request limits: width and height (px) and the pixel budget."""

    max_width: int
    max_height: int
    max_pixels: int


@dataclass(frozen=True)
class Chunk:
    """One request of an area: bbox and its exact size in pixels."""

    bbox: BBox
    width: int
    height: int


def align_bbox(
    bbox: BBox, pixel_size: float, grid: GridSpec | None = None
) -> tuple[BBox, int, int]:
    """Bbox aligned for a raster request and its size in pixels.

    Without ``grid``: NW anchor and a whole pixel count (``round``, at least 1);
    ``min_y``/``max_x`` follow from the anchor, so a single request, the chunks and
    the mosaic share one grid (CZ exportImage rule). With ``grid``: the bbox is
    expanded OUTWARD to the grid lines (< 1 px per side, within ``_GRID_TOL_PX`` a
    bbox already on a line gains nothing) - the result always contains the request.
    """
    if grid is None:
        width = max(1, round((bbox.max_x - bbox.min_x) / pixel_size))
        height = max(1, round((bbox.max_y - bbox.min_y) / pixel_size))
        aligned = BBox(
            bbox.min_x,
            bbox.max_y - height * pixel_size,
            bbox.min_x + width * pixel_size,
            bbox.max_y,
            bbox.crs,
        )
        return aligned, width, height

    if not math.isclose(pixel_size, grid.step, rel_tol=1e-9):
        raise ValidationError(
            message(
                "transport.pixel_grid_step_mismatch",
                pixel_size=pixel_size,
                grid_step=grid.step,
            )
        )
    ref = Affine(grid.step, 0.0, grid.origin_x, 0.0, -grid.step, grid.origin_y)
    min_x, min_y, max_x, max_y = _snap_outward(
        (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y), ref
    )
    width = max(1, round((max_x - min_x) / grid.step))
    height = max(1, round((max_y - min_y) / grid.step))
    return (
        BBox(
            min_x,
            max_y - height * grid.step,
            min_x + width * grid.step,
            max_y,
            bbox.crs,
        ),
        width,
        height,
    )


def plan_chunks(
    bbox: BBox,
    width: int,
    height: int,
    pixel_size: float,
    limits: ChunkLimits,
    *,
    multiple: int = 1,
) -> list[Chunk]:
    """Deterministic chunk grid cut on whole pixels (N->S, W->E), NW anchor.

    One chunk (the whole bbox) when the request fits the limits. Otherwise
    square-ish chunks instead of narrow strips (CUZK probes confirmed that class
    of shapes), sizes split evenly by ``divmod``. ``multiple``: every chunk
    width and height is a multiple of it (``width``/``height`` must be too) -
    GUGiK WCS resamples the middle row/column of an odd-sized request from the
    neighbouring source pixel (``providers/pl/wcs.py``).
    """
    if width % multiple or height % multiple:
        raise ValidationError(
            message(
                "transport.chunk_size_not_multiple",
                width=width,
                height=height,
                multiple=multiple,
            )
        )
    if (
        width <= limits.max_width
        and height <= limits.max_height
        and width * height <= limits.max_pixels
    ):
        return [Chunk(bbox, width, height)]

    def _splits(total_px: int, parts: int) -> list[tuple[int, int]]:
        base, extra = divmod(total_px // multiple, parts)
        return [
            (
                (i * base + min(i, extra)) * multiple,
                (base + (1 if i < extra else 0)) * multiple,
            )
            for i in range(parts)
        ]

    def _cap(limit: int) -> int:
        return max(multiple, limit // multiple * multiple)

    col_cap = _cap(min(limits.max_width, math.isqrt(limits.max_pixels)))
    cols = _splits(width, math.ceil(width / col_cap))
    chunk_w = max(size for _, size in cols)
    row_cap = _cap(min(limits.max_height, limits.max_pixels // chunk_w))
    rows = _splits(height, math.ceil(height / row_cap))

    return [
        Chunk(
            BBox(
                bbox.min_x + col_off * pixel_size,
                bbox.max_y - (row_off + row_px) * pixel_size,
                bbox.min_x + (col_off + col_px) * pixel_size,
                bbox.max_y - row_off * pixel_size,
                bbox.crs,
            ),
            col_px,
            row_px,
        )
        for row_off, row_px in rows
        for col_off, col_px in cols
    ]


def fetch_chunks(
    chunks: Sequence[Chunk],
    bbox: BBox,
    output_path: Path,
    fetch: Callable[[Chunk, Path], None],
    *,
    nodata: float | None = None,
) -> Path:
    """Fetch every chunk and stitch them into ``output_path``; return it.

    One chunk equal to ``bbox`` is fetched straight into ``output_path``.
    Otherwise (several chunks, or chunks covering more than ``bbox``) they are
    fetched ONE AT A TIME (the GUGiK host drops connections; CZ has a time
    budget) into part files next to the result, stitched and cropped to
    ``bbox`` by ``mosaic_and_crop`` without resampling and removed in any case.
    A ``fetch`` error propagates unchanged (retries are per chunk, inside
    ``fetch``); a stitching error other than ``ValidationError`` becomes
    ``DownloadError`` and no partial result is left.
    """
    output_path = Path(output_path)
    if len(chunks) == 1 and chunks[0].bbox == bbox:
        fetch(chunks[0], output_path)
        return output_path
    parts: list[Path] = []
    try:
        for i, chunk in enumerate(chunks):
            part = output_path.with_name(
                f"{output_path.name}.{os.getpid()}_{threading.get_ident()}.part{i}.tif"
            )
            parts.append(part)
            fetch(chunk, part)
        try:
            mosaic_and_crop(
                parts, bbox, output_path, nodata=nodata, dst_kwds=_result_kwds(parts[0])
            )
        except ValidationError:
            output_path.unlink(missing_ok=True)
            raise
        except Exception as e:  # noqa: BLE001 - rasterio/GDAL have no common base
            output_path.unlink(missing_ok=True)
            raise DownloadError(
                message(
                    "transport.mosaic_stitch_failed",
                    parts_count=len(parts),
                    output_path=output_path,
                    error=reason(e),
                )
            ) from e
    finally:
        for part in parts:
            part.unlink(missing_ok=True)
    return output_path


def _result_kwds(first_part: Path) -> dict[str, Any] | None:
    """Tiles for a result stitched from STRIPED chunks (GUGiK WCS GeoTIFF).

    ``merge`` copies the profile of the first source; a striped GeoTIFF carries
    ``blockxsize`` = its width without ``tiled``, which GDAL rejects for the result
    with a warning ("BLOCKXSIZE can only be used with TILED=YES", live run
    2026-10-10). Tiled chunks (CZ exportImage) keep their own profile.
    """
    with rasterio.open(first_part) as src:
        if src.profile.get("tiled"):
            return None
    return {"tiled": True, "blockxsize": 256, "blockysize": 256}
