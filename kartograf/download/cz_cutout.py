"""Versioned CZ (CUZK) DMR bbox cutouts shared by the CLI and library.

The result grid starts at the bbox normalized to the requested image CRS.
The standard ``bbox/<coords>.tif`` path is a hardlink to an immutable
version; local versions restore ``all_nodata`` from their sidecar.
Public pair (Z2): ``download_cz_cutout`` / ``check_cz_cutout`` with the same
selection arguments; data messages are ``Notice``s in the result.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox, bbox_coords
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
from kartograf.notices import ALL_NODATA, Notice, NoticeSink
from kartograf.providers.cuzk.client import wkid
from kartograf.providers.cuzk.dmr import CUZK_NODATA, NATIVE_CRS
from kartograf.sources.registry import get_source

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CzCutoutResult:
    """Result of a CZ cutout; ``file=None`` only when a plan excludes a missing file.

    ``notices`` holds the all-nodata message of a freshly downloaded file.
    """

    file: VersionedFile | None
    all_nodata: bool = False
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()


def emit_cz_all_nodata(
    sink: NoticeSink, file: VersionedFile | None, all_nodata: bool
) -> None:
    """``ALL_NODATA`` for a downloaded (not reused local) CZ raster without data."""
    if all_nodata and file is not None and file.status != "local":
        sink.emit(
            "warning",
            ALL_NODATA,
            f"{file.path} jest w calosci nodata - obszar poza pokryciem DMR CUZK "
            "(poza granica CZ?)",
        )


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
    --horizontal-crs: the CRS requested by the user), not the channel's default CRS.

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


def _check_cutout(
    provider,
    bbox: BBox,
    *,
    output_dir: str | Path,
    image_crs: str | None,
) -> UpdatePlan:
    """Plan of a CZ bbox version without raster access or network requests."""
    _, _, slot = _cutout_slot(provider, bbox, output_dir, image_crs)
    item = inspect_version(
        slot,
        track="cz_cutout",
        unit=slot.std.stem,
        signal="none",
    )
    return new_plan(store_id(output_dir), (item,))


def _run_cz_cutout(
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
        extra: dict = {"all_nodata": empty}
        if parent_request:
            extra["parent_request"] = parent_request
        write_cz_sidecar(
            provider,
            data,
            request={
                "bbox": bbox_coords(bbox),
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


def _image_crs(target_crs: str) -> str | None:
    """``None`` for the native EPSG:5514 result, else the requested result CRS."""
    return None if wkid(target_crs) == wkid(NATIVE_CRS) else target_crs


def _cz_provider(
    *,
    horizontal_crs: str,
    vertical_crs: str,
    resolution: str,
    cache: MetadataCache | None,
):
    """CZ DMR provider of a cutout (``TransformError`` before any network)."""
    from kartograf.download.cutout import CUTOUT_CRS
    from kartograf.providers.cuzk import create_dmr_provider

    if horizontal_crs not in CUTOUT_CRS:
        raise ValidationError(
            f"Nieobslugiwany uklad docelowy wycinka CZ: {horizontal_crs!r} "
            f"(dostepne: {', '.join(CUTOUT_CRS)})"
        )
    return create_dmr_provider(
        resolution=resolution,
        cache=cache,
        horizontal_crs=_image_crs(horizontal_crs),
        vertical_crs=vertical_crs,
    )


def check_cz_cutout(
    bbox: BBox,
    *,
    output_dir: str | Path,
    horizontal_crs: str,
    vertical_crs: str,
    resolution: str,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_cz_cutout`` with the same arguments, no download.

    The cutout channel has no remote version signal: the plan reads only the
    local store (no network, no metadata cache). ``cache`` and ``on_notice``
    are accepted for symmetry with the download. Invalid choices raise the
    same ``ValidationError``/``TransformError`` as the download.
    """
    from kartograf.download.options import validate_request_bbox

    validate_request_bbox(bbox)
    del cache, on_notice  # same signature as the download (Z2); unused here
    provider = _cz_provider(
        horizontal_crs=horizontal_crs,
        vertical_crs=vertical_crs,
        resolution=resolution,
        cache=None,
    )
    return _check_cutout(
        provider, bbox, output_dir=output_dir, image_crs=_image_crs(horizontal_crs)
    )


def download_cz_cutout(
    bbox: BBox,
    *,
    output_dir: str | Path,
    horizontal_crs: str,
    vertical_crs: str,
    resolution: str,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    parent_request: dict | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzCutoutResult:
    """CZ DMR cutout in ``horizontal_crs`` (e.g. EPSG:2180 + EVRF2007, A6).

    No configuration defaults (A8): output directory, CRSs and resolution
    (``"2m"`` DMR 5G / ``"5m"`` DMR 4G) are explicit. The grid starts at
    ``bbox`` converted to ``horizontal_crs``. ``plan`` (from ``check_cz_cutout``
    with ``update="upgrade"``) downloads only its missing position; a changed
    position lands in ``stale``. ``cache``: ``True`` = default metadata cache
    in the current directory, a ``MetadataCache`` = that cache, ``False`` =
    none. ``on_notice`` receives each data notice when emitted;
    ``on_download`` is called right before the first service request.

    Raises
    ------
    ValidationError
        Bad resolution, CRS, vertical CRS or plan/update combination.
    TransformError
        No safe pinned operation to ``horizontal_crs``.
    DownloadError
        CUZK service failure.
    """
    from kartograf.download.options import validate_request_bbox

    validate_request_bbox(bbox)
    validate_update(update)
    sink = NoticeSink(on_notice)
    with open_cache(cache, force=update == "force", on_notice=sink.add) as metadata:
        provider = _cz_provider(
            horizontal_crs=horizontal_crs,
            vertical_crs=vertical_crs,
            resolution=resolution,
            cache=metadata,
        )
        result = _run_cz_cutout(
            provider,
            bbox,
            output_dir=output_dir,
            image_crs=_image_crs(horizontal_crs),
            update=update,
            plan=plan,
            parent_request=parent_request,
            on_download=on_download,
        )
    emit_cz_all_nodata(sink, result.file, result.all_nodata)
    return replace(result, notices=sink.notices)
