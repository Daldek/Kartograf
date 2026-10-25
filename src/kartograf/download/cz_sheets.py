"""CUZK SM5 and TM33 sheet downloads (NMT, NMPT) on the versioned file store.

The route of a sheet is a row of the variant registry (plan B decision 2,
``CuzkRasterProvider.route``): an SM5 sheet is the S-JTSK file, a TM33 tile
in EVRF2007 of a model with files is the ETRS89 file (signal ``http``, one
``HEAD`` compares a local version), every other tile is an ImageServer
export warped onto the tile grid (no cheap signal).

Public pair (Z2): ``download_cz_sheet`` / ``check_cz_sheet`` with the same
selection arguments; data messages are ``Notice``s in the result.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import requests

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.download.cz_cutout import (
    _all_nodata,
    emit_cz_all_nodata,
    read_tif_nodata,
)
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    fetch_version,
    inspect_version,
    link_version,
    local_file,
    local_version,
    refreshes_cache,
    validate_update,
)
from kartograf.download.plan import (
    TODO_STATUSES,
    PlanItem,
    UpdatePlan,
    new_plan,
    refusal_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import storage_for_provider
from kartograf.download.versions import ContentDigest, VersionRef, read_version
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.messages import message, reason
from kartograf.notices import UNVERIFIED_LOCAL, Notice, NoticeSink
from kartograf.output import plain_of, preflight, writing
from kartograf.providers.cuzk.raster import CuzkRasterProvider
from kartograf.sources.registry import get_source
from kartograf.sources.sidecar import emit_sidecar
from kartograf.sources.variants import (
    ProductVariant,
    cz_sheet_system,
    find_cz_variant,
)
from kartograf.transport.http import response_signal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CzSheetResult:
    """One CZ sheet; ``file=None`` only when a plan skips a missing file.

    ``notices`` holds the all-nodata message of a freshly downloaded file
    and the unverified local version of a file route (decision 12).
    """

    file: VersionedFile | None
    all_nodata: bool
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()


def cz_sheet_variant(
    sheet: str, product: str, resolution: str | None, vertical_crs: str
) -> ProductVariant:
    """Return the row of the route table of a CZ sheet code (plan B, decision 2).

    An SM5 sheet may omit ``resolution`` when one label of the product has
    SM5 files (NMT 5m DMR 4G, NMPT 0.5m DMP OK); a TM33 tile requires it.

    Raises
    ------
    ValidationError
        Not a CZ code, or a choice without a variant (SM5 for 2m, a label or
        height system outside the registry).
    ParseError
        A malformed TM33 code.
    """
    sheet = sheet.strip()
    system = cz_sheet_system(sheet)
    if system == "tm33":
        ParserTM33(sheet)  # full validation of the grid (even kilometres)
    return find_cz_variant(
        product=product,
        resolution=resolution,
        vertical_crs=vertical_crs,
        system=system,
    )


def _sheet_slot(provider: CuzkRasterProvider, sheet: str, root: str | Path) -> FileSlot:
    sheet = sheet.strip()
    descriptor = get_source(cast(str, provider.descriptor_key))
    storage = storage_for_provider(
        root,
        provider,
        resolution=provider.resolution,
        vertical_crs=provider.vertical_crs,
    )
    return FileSlot(
        Path(root),
        storage.get_raw_path(sheet, f"{sheet}{descriptor.default_extension}"),
        storage.get_raw_versions_base(sheet),
        storage.get_raw_versions_root(sheet),
        descriptor.default_extension,
    )


def _check_sheet(
    provider: CuzkRasterProvider, sheet: str, *, root: str | Path
) -> UpdatePlan:
    """Inspect one CZ sheet without transferring raster bytes."""
    sheet = sheet.strip()
    route = provider.route(sheet)
    item = inspect_version(
        _sheet_slot(provider, sheet, root),
        track="cz_sheet",
        unit=sheet,
        signal=route.channel.update_signal,
        probe=(lambda: provider.file_signal(sheet)) if route.files else None,
    )
    return new_plan(store_id(root), (item,))


def _local_result(slot: FileSlot, stale: tuple[PlanItem, ...]) -> CzSheetResult:
    """Return a planned-but-unselected sheet without probing or reading raster data."""
    local = local_version(slot)
    if local is None:
        return CzSheetResult(None, False, stale)
    link_version(slot.std, local, refresh=False)
    return CzSheetResult(
        local_file(slot.std, local),
        local.meta.get("extra", {}).get("all_nodata", False) is True,
        stale,
    )


def _run_cz_sheet(
    provider: CuzkRasterProvider,
    sheet: str,
    *,
    root: str | Path,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzSheetResult:
    """Download or use the local version of a TM33 tile or an SM5 sheet.

    A file route compares the openzu ZIP's HTTP signal with one HEAD request
    when a local version exists; an ImageServer tile has no cheap freshness
    signal. With a plan, only a matching ``missing``/``newer`` position may be
    downloaded; a skipped position with no local version has ``file=None``.
    """
    validate_update(update)
    if plan is not None and update != "upgrade":
        raise ValidationError(message("hydrology.plan_requires_upgrade"))
    sheet = sheet.strip()
    # the route (variant, channel, pinned operations) before any request
    route = provider.route(sheet)
    slot = _sheet_slot(provider, sheet, root)
    preflight(root, [slot.name])
    probe = (lambda: provider.file_signal(sheet)) if route.files else None
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        require_store(plan, store_id(root))
        scoped = replace(
            plan,
            items=tuple(
                item for item in plan.items_for("cz_sheet") if item.unit == sheet
            ),
        )
        if not any(item.status in TODO_STATUSES for item in scoped.items):
            return _local_result(slot, ())
        fresh = _check_sheet(provider, sheet, root=root).items
        if fresh[0].status == "check_failed":
            raise DownloadError(
                message(
                    "tracks.cz_sheet_check_failed", sheet=sheet, error=fresh[0].error
                )
            )
        todo, rejected = select_planned(scoped, list(fresh), "cz_sheet")
        stale = tuple(rejected)
        if not todo:
            return _local_result(slot, stale)
        # The plan was just checked: reuse that one HEAD result instead of
        # issuing a second HEAD for the same signal before downloading.
        if route.files:
            available_signal = todo[0].available_signal

            def planned_probe() -> dict[str, Any]:
                return available_signal or {}

            probe = planned_probe

    received: dict[str, Any] | None = None
    empty = False

    def on_response(response: requests.Response) -> None:
        nonlocal received
        received = response_signal(response)

    def fetch(staged: Path) -> dict[str, Any] | None:
        nonlocal empty
        provider.download(
            sheet,
            staged,
            on_download=on_download,
            on_response=on_response if route.files else None,
        )
        if plain_of(root) is not None:  # no sidecar says it: look at the raster
            empty = _all_nodata(staged, read_tif_nodata(staged))
        return received if route.files else None

    def write_sidecar(
        data: Path,
        version: VersionRef,
        digest: ContentDigest,
        http: dict[str, Any] | None,
    ) -> None:
        nonlocal empty
        nodata = read_tif_nodata(data)
        empty = _all_nodata(data, nodata)
        extra: dict[str, Any] = {"all_nodata": empty}
        if http is not None:
            extra["http"] = http
        if cz_sheet_system(sheet) == "sm5":
            try:
                info = provider.sheet_index.sm5_sheet(sheet)
                if info.name is not None:
                    extra["mapname"] = info.name
                if info.podil is not None:
                    extra["cz_share"] = info.podil
            except Exception as e:  # noqa: BLE001 — data matters more than metadata
                logger.warning(
                    message("tracks.sidecar_no_cz_share", sheet=sheet, error=reason(e))
                )
        emit_sidecar(
            provider.descriptor_key,
            data,
            request={"sheet": sheet},
            vertical_crs=provider.vertical_crs,
            horizontal_crs=route.horizontal_crs,
            pinned_transforms={
                "horizontal": route.horizontal,
                "vertical": route.vertical,
            },
            capability=route.capability,
            nodata=nodata,
            extra=extra,
            digest=(digest.sha256, digest.size_bytes),
            version=version.to_extra(),
            exclusive=True,
        )

    file = fetch_version(
        slot,
        update,
        signal=route.channel.update_signal,
        fetch=fetch,
        version=VersionRef.downloaded(),
        write_sidecar=write_sidecar,
        probe=probe,
    )
    notices: tuple[Notice, ...] = ()
    if file.status == "local":
        stored = read_version(file.version_path.parent, file.version_path.name)
        empty = (
            stored is not None
            and stored.meta.get("extra", {}).get("all_nodata", False) is True
        )
        if route.files and file.unverified == "none":
            # decision 12: a local version without the HTTP signal of the file
            # (e.g. a TM33 tile warped from the ImageServer by an earlier build)
            notices = (
                Notice(
                    "info",
                    UNVERIFIED_LOCAL,
                    message(
                        "tracks.unverified_local_version", sheet=sheet, label=file.label
                    ),
                ),
            )
    return CzSheetResult(file, empty, stale, notices)


def _sheet_provider(
    sheet: str,
    *,
    product: str,
    vertical_crs: str,
    resolution: str | None,
    cache: MetadataCache | None,
) -> CuzkRasterProvider:
    """CZ raster provider of a sheet code (the variant of its route table row)."""
    from kartograf.providers.cuzk import create_cz_raster_provider

    variant = cz_sheet_variant(sheet, product, resolution, vertical_crs)
    assert variant.label is not None  # CZ rasters have a resolution
    return create_cz_raster_provider(
        product=product,
        resolution=variant.label,
        cache=cache,
        vertical_crs=vertical_crs,
    )


def check_cz_sheet(
    *,
    sheet: str,
    root: str | Path | None = None,
    output_dir: str | Path | None = None,
    product: str,
    vertical_crs: str,
    resolution: str | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_cz_sheet`` with the same arguments, no download.

    A file route compares the openzu ZIP's HTTP signal (one HEAD request and
    the sheet index, both from the source: the metadata cache is refreshed,
    never read); an ImageServer tile has no remote signal and reads only the
    local store. Invalid choices raise the same errors as the download. With
    ``output_dir`` the position is the target of a plain write (``action``,
    ``path``); nothing is probed.
    """
    sink = NoticeSink(on_notice)
    with (
        writing(output_dir=output_dir, root=root, guard=False) as store,
        open_cache(cache, force=True, on_notice=sink.add) as metadata,
    ):
        provider = _sheet_provider(
            sheet,
            product=product,
            vertical_crs=vertical_crs,
            resolution=resolution,
            cache=metadata,
        )
        if (refused := refusal_plan(store)) is not None:
            return refused
        return _check_sheet(provider, sheet, root=store)


def download_cz_sheet(
    *,
    sheet: str,
    root: str | Path | None = None,
    output_dir: str | Path | None = None,
    product: str,
    vertical_crs: str,
    resolution: str | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzSheetResult:
    """Download or reuse one CZ sheet: an SM5 sheet or a TM33 tile.

    ``product``: ``"nmt"`` (DMR 5G 2m, DMR 4G 5m) or ``"nmpt"`` (DMP 1G 2m,
    DMP OK 0.5m). ``resolution``: an SM5 sheet exists only for the label
    with SM5 files (NMT 5m, NMPT 0.5m; ``None`` = that label); a TM33 tile
    requires it. ``vertical_crs`` is ``"Bpv"`` or ``"EVRF2007"`` (native for
    the ETRS89 tile files, otherwise the pinned operation). The route (plan
    B, decision 2): SM5 = the S-JTSK file, TM33 in EVRF2007 of DMR 4G/DMP OK
    = the ETRS89 file, other tiles = the ImageServer warped onto the tile
    grid. A file compares its HTTP signal with one HEAD request when a local
    version exists; an ImageServer tile has no cheap signal. ``plan`` (from
    ``check_cz_sheet`` with ``update="upgrade"``) downloads only a matching
    ``missing``/``newer`` position; a changed position lands in ``stale``.
    ``output_dir`` writes the plain file ``<sheet>.<ext>`` into that directory
    instead of the store (no sidecar, no version; ``update="force"`` replaces an
    existing file, a conflict stops before the first byte; it excludes ``root``,
    ``update="upgrade"`` and ``plan``).
    ``cache``: ``True`` = default metadata cache in the current directory, a
    ``MetadataCache`` = that cache, ``False`` = none. ``on_notice`` receives
    each data notice when emitted; ``on_download`` is called right before
    the transfer starts.

    Raises
    ------
    ParseError
        Malformed sheet code.
    ValidationError
        Not a CZ code, a choice without a variant (SM5 for 2m), a bad
        resolution or vertical CRS, a plan without upgrade.
    TransformError
        No safe pinned operation of the route.
    DownloadError
        CUZK service failure; no new version is committed.
    """
    validate_update(update, check="check_cz_sheet")
    sink = NoticeSink(on_notice)
    with (
        writing(output_dir=output_dir, root=root, update=update, plan=plan) as store,
        open_cache(
            cache, force=refreshes_cache(update), on_notice=sink.add
        ) as metadata,
    ):
        provider = _sheet_provider(
            sheet,
            product=product,
            vertical_crs=vertical_crs,
            resolution=resolution,
            cache=metadata,
        )
        result = _run_cz_sheet(
            provider,
            sheet,
            root=store,
            update=update,
            plan=plan,
            on_download=on_download,
        )
    for notice in result.notices:
        sink.add(notice)
    emit_cz_all_nodata(sink, result.file, result.all_nodata)
    return replace(result, notices=sink.notices)
