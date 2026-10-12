"""Versioned CZ (CUZK) DMR bbox cutouts shared by the CLI and library.

The result grid starts at the bbox normalized to the requested image CRS.
The standard ``bbox/<coords>.tif`` path is a hardlink to an immutable
version; local versions restore ``all_nodata`` from their sidecar.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kartograf.core.bbox import BBox
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    fetch_version,
    inspect_version,
    link_version,
    local_version,
    validate_update,
)
from kartograf.download.plan import (
    PlanItem,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import bbox_slot
from kartograf.download.versions import ContentDigest, VersionRef, read_version
from kartograf.exceptions import ValidationError
from kartograf.providers.cuzk.client import wkid
from kartograf.providers.cuzk.dmr import CUZK_NODATA, NATIVE_CRS
from kartograf.sources.registry import get_source

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CzCutoutResult:
    """Result of a CZ cutout; ``file=None`` only when a plan excludes a missing file."""

    file: VersionedFile | None
    all_nodata: bool = False
    stale: tuple[PlanItem, ...] = ()


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
    extra: dict | None,
    version: VersionRef,
    digest: ContentDigest,
    http: dict | None,
) -> None:
    """Write the mandatory, exclusive sidecar of a versioned CZ cutout.

    `horizontal_crs` is the CRS of the ACTUAL result (TM33 tile: EPSG:3045,
    --target-crs: the CRS requested by the user), not the channel's default CRS.

    Both `transform` entries describe PINNED operations performed locally -
    horizontal and vertical alike (ADR-024). Previously the horizontal field carried
    `"server:EPSG:<code>"` without an accuracy, which hid the server-side
    reprojection error (135 m) from the sidecar consumer.
    """
    from kartograf.sources.sidecar import emit_sidecar

    metadata_extra = dict(extra or {})
    if http is not None:
        metadata_extra["http"] = http
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
        extra=metadata_extra,
        version=version.to_extra(),
        digest=(digest.sha256, digest.size_bytes),
        exclusive=True,
    )


def _cutout_slot(
    provider, bbox: BBox, output_dir: str | Path, image_crs: str | None
) -> tuple[BBox, str, FileSlot]:
    """Normalize to the result CRS before choosing the stable bbox file name."""
    from kartograf.providers.cuzk.dmr import bbox_to_crs  # CLI patch point

    image_sr = image_crs or NATIVE_CRS
    if wkid(bbox.crs) != wkid(image_sr):
        bbox = bbox_to_crs(bbox, image_sr)
    descriptor = get_source(provider.descriptor_key)
    slot = bbox_slot(
        output_dir,
        descriptor.resolve_subdir(vertical_crs=provider.vertical_crs),
        bbox,
        ".tif",
    )
    return bbox, image_sr, slot


def _result(
    file: VersionedFile | None, stale: tuple[PlanItem, ...] = ()
) -> CzCutoutResult:
    """Read the nodata flag from the immutable version sidecar, not the raster."""
    if file is None:
        return CzCutoutResult(None, stale=stale)

    version = read_version(file.version_path.parent, file.version_path.name)
    extra = version.meta.get("extra", {}) if version is not None else {}
    return CzCutoutResult(file, all_nodata=extra.get("all_nodata") is True, stale=stale)


def check_cz_cutout(
    provider,
    bbox: BBox,
    *,
    output_dir: str | Path,
    image_crs: str | None,
) -> UpdatePlan:
    """Check a CZ bbox version without raster access or network requests."""
    _, _, slot = _cutout_slot(provider, bbox, output_dir, image_crs)
    item = inspect_version(
        slot,
        track="cz_cutout",
        unit=slot.std.stem,
        signal="none",
    )
    return new_plan(store_id(output_dir), (item,))


def run_cz_cutout(
    provider,
    bbox: BBox,
    *,
    output_dir: str | Path,
    image_crs: str | None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    parent_request: dict | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzCutoutResult:
    """Fetch or reuse a CZ cutout; planned upgrades fetch only selected files.

    A plan-excluded cutout with no local version returns ``file=None``.
    Local versions restore ``all_nodata`` from their immutable sidecar.
    """
    validate_update(update)
    if plan is not None:
        if update != "upgrade":
            raise ValidationError("Plan wycinka CZ wymaga update='upgrade'")
        require_store(plan, store_id(output_dir))
    bbox, image_sr, slot = _cutout_slot(provider, bbox, output_dir, image_crs)
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        fresh = inspect_version(
            slot,
            track="cz_cutout",
            unit=slot.std.stem,
            signal="none",
        )
        todo, skipped = select_planned(plan, [fresh], "cz_cutout")
        stale = tuple(skipped)
        if not todo:
            local = local_version(slot)
            if local is None:
                return _result(None, stale)
            link_version(slot.std, local, refresh=False)
            return _result(
                VersionedFile(slot.std, "local", local.label, local.sha256, local.path),
                stale,
            )

    def fetch(staged: Path) -> None:
        provider.download_bbox(bbox, staged, on_download=on_download)

    def sidecar(
        data: Path, ref: VersionRef, digest: ContentDigest, http: dict | None
    ) -> None:
        nodata = read_tif_nodata(data)
        empty = _all_nodata(data, nodata)
        if empty:
            logger.warning(
                f"Wycinek CZ {slot.std} jest w calosci nodata - obszar poza pokryciem "
                "DMR CUZK (poza granica CZ?)"
            )
        extra: dict = {"all_nodata": empty}
        if parent_request:
            extra["parent_request"] = parent_request
        write_cz_sidecar(
            provider,
            data,
            request={
                "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
                "bbox_crs": bbox.crs,
            },
            capability="bbox_raster",
            horizontal_crs=image_sr,
            nodata=nodata if nodata is not None else CUZK_NODATA,
            extra=extra,
            version=ref,
            digest=digest,
            http=http,
        )

    file = fetch_version(
        slot,
        update,
        signal="none",
        fetch=fetch,
        version=VersionRef.downloaded(),
        write_sidecar=sidecar,
    )
    return _result(file, stale)


def download_cz_cutout(
    bbox: BBox,
    *,
    output_dir: str | Path,
    target_crs: str,
    vertical_crs: str,
    resolution: str,
    update: UpdateMode | None = None,
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
        update=update,
        parent_request=parent_request,
    )
