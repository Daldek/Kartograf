"""CZ (CUZK) DMR cutout in the library (A6, 0.7.1).

The CLI ``--country cz``/``auto`` bbox flow and library callers share one
implementation: request normalization, download, the all-nodata flag and
the sidecar. The grid starts at the requested bbox (as in the CLI before
0.7.1); aligning it to the PL grid is a separate future spec.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kartograf.core.bbox import BBox
from kartograf.download.storage import bbox_cutout_path, prune_empty_dirs
from kartograf.providers.cuzk.client import wkid
from kartograf.providers.cuzk.dmr import CUZK_NODATA, NATIVE_CRS
from kartograf.sources.registry import get_source

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CzCutoutResult:
    """Result of ``run_cz_cutout`` / ``download_cz_cutout``."""

    path: Path
    skipped: bool = False  # file existed (force=False) - no network
    # not a single valid pixel (area outside CUZK coverage); the file exists
    all_nodata: bool = False


def read_tif_nodata(path: Path) -> float | None:
    """Nodata from a GeoTIFF tag (None if missing/unreadable)."""
    try:
        import rasterio

        with rasterio.open(path) as src:
            return src.nodata
    except Exception:  # noqa: BLE001 — enriching metadata < data
        return None


def _all_nodata(path: Path, nodata: float | None) -> bool:
    """True when the raster has no valid pixel (no tag: CUZK writes -9999).

    Best-effort like ``read_tif_nodata``: an unreadable file gives False
    (debug log) - the check never aborts a finished download.
    """
    from kartograf.transport.mosaic import has_valid_pixels

    try:
        return not has_valid_pixels(path, CUZK_NODATA if nodata is None else nodata)
    except Exception as e:  # noqa: BLE001 — a flag never aborts the download
        logger.debug(f"Kontrola nodata {path} pominieta: {e}")
        return False


def write_cz_sidecar(
    provider,
    target: Path,
    *,
    request: dict,
    capability: str,
    horizontal_crs: str,
    nodata: float | None,
    extra: dict | None = None,
) -> None:
    """Best-effort sidecar for a CZ result (an error does not abort the download).

    `horizontal_crs` is the CRS of the ACTUAL result (TM33 tile: EPSG:3045,
    --target-crs: the CRS requested by the user), not the channel's default CRS.

    Both `transform` entries describe PINNED operations performed locally -
    horizontal and vertical alike (ADR-024). Previously the horizontal field carried
    `"server:EPSG:<code>"` without an accuracy, which hid the server-side
    reprojection error (135 m) from the sidecar consumer.
    """
    from kartograf.sources.sidecar import emit_sidecar

    emit_sidecar(
        provider.descriptor_key,
        target,
        request=request,
        vertical_crs=provider.vertical_crs,
        horizontal_crs=horizontal_crs,
        pinned_transforms={
            "horizontal": provider.horizontal_transform(horizontal_crs),
            "vertical": provider.vertical_transform,
        },
        capability=capability,
        nodata=nodata,
        extra=extra,
    )


def run_cz_cutout(
    provider,
    bbox: BBox,
    *,
    output_dir: str | Path,
    image_crs: str | None,
    force: bool = False,
    parent_request: dict | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzCutoutResult:
    """One CZ GeoTIFF for ``bbox`` with a given provider (CLI and library).

    ``image_crs`` is the result CRS the provider was built for (None =
    native EPSG:5514); the bbox is normalized to it before naming the file.
    An existing file with ``force=False`` is returned as skipped
    (``all_nodata`` read from it). A failed download removes the empty
    ``<segment>/bbox/`` tree and re-raises.
    """
    from kartograf.providers.cuzk.dmr import bbox_to_crs  # patch point of CLI tests

    image_sr = image_crs or NATIVE_CRS
    if wkid(bbox.crs) != wkid(image_sr):
        # normalization BEFORE naming the file: the name carries the
        # coordinates of the actually requested cutout (in download_bbox
        # this is already a no-op)
        bbox = bbox_to_crs(bbox, image_sr)
    descriptor = get_source(provider.descriptor_key)
    target = bbox_cutout_path(
        output_dir,
        descriptor.resolve_subdir(vertical_crs=provider.vertical_crs),
        bbox,
        descriptor.default_extension,
    )
    if not force and target.exists():
        return CzCutoutResult(
            target,
            skipped=True,
            all_nodata=_all_nodata(target, read_tif_nodata(target)),
        )
    # the provider creates directories only when fetching - the sidecar needs them
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        provider.download_bbox(bbox, target, on_download=on_download)
    except BaseException:
        # a failure leaves no empty <segment>/bbox/ tree
        prune_empty_dirs(target.parent, Path(output_dir))
        raise
    nodata = read_tif_nodata(target)
    empty = _all_nodata(target, nodata)
    if empty:
        # A6: the library reports it too (result flag + sidecar + log)
        logger.warning(
            f"Wycinek CZ {target} jest w calosci nodata — obszar poza pokryciem "
            "DMR CUZK (poza granica CZ?)"
        )
    extra: dict = {"all_nodata": empty}
    if parent_request:
        extra["parent_request"] = parent_request
    write_cz_sidecar(
        provider,
        target,
        request={
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": bbox.crs,
        },
        capability="bbox_raster",
        horizontal_crs=image_sr,
        nodata=nodata if nodata is not None else CUZK_NODATA,
        extra=extra,
    )
    return CzCutoutResult(target, all_nodata=empty)


def download_cz_cutout(
    bbox: BBox,
    *,
    output_dir: str | Path,
    target_crs: str,
    vertical_crs: str,
    resolution: str,
    force: bool = False,
    cache=None,
    parent_request: dict | None = None,
) -> CzCutoutResult:
    """CZ DMR cutout in ``target_crs`` (e.g. EPSG:2180 + EVRF2007, A6).

    No configuration defaults (A8): output directory, CRSs and resolution
    (``"2m"`` DMR 5G / ``"5m"`` DMR 4G) are explicit. The grid starts at
    ``bbox`` converted to ``target_crs``.

    Raises
    ------
    ValidationError
        Bad resolution, CRS or vertical CRS.
    TransformError
        No safe pinned operation to ``target_crs``.
    DownloadError
        CUZK service failure.
    """
    from kartograf.providers.cuzk import create_dmr_provider

    image_crs = None if wkid(target_crs) == wkid(NATIVE_CRS) else target_crs
    provider = create_dmr_provider(
        resolution=resolution,
        cache=cache,
        target_crs=image_crs,
        vertical_crs=vertical_crs,
    )
    return run_cz_cutout(
        provider,
        bbox,
        output_dir=output_dir,
        image_crs=image_crs,
        force=force,
        parent_request=parent_request,
    )
