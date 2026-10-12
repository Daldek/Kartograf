"""CUZK SM5 and TM33 sheet downloads on the versioned file store.

Public pair (Z2): ``download_cz_sheet`` / ``check_cz_sheet`` with the same
selection arguments; data messages are ``Notice``s in the result.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import requests

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_registry import detect_system
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
    local_version,
    validate_update,
)
from kartograf.download.plan import (
    TODO_STATUSES,
    PlanItem,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import storage_for_provider
from kartograf.download.versions import ContentDigest, VersionRef, read_version
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import Notice, NoticeSink
from kartograf.sources.descriptor import SignalKind, TransportKind
from kartograf.sources.registry import channel_signal, get_source
from kartograf.sources.sidecar import emit_sidecar
from kartograf.transport.http import response_signal

logger = logging.getLogger(__name__)

# Resolutions of CZ DMR (help and error texts of the CLI and the library).
RESOLUTION_CZ = "2m (DMR 5G), 5m (DMR 4G)"


@dataclass(frozen=True)
class CzSheetResult:
    """One CZ sheet; ``file=None`` only when a plan skips a missing file.

    ``notices`` holds the all-nodata message of a freshly downloaded file.
    """

    file: VersionedFile | None
    all_nodata: bool
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()


def cz_sheet_resolution(sheet: str, resolution: str | None) -> str:
    """Resolution of a CZ sheet code: SM5 only ``5m`` (default), TM33 required.

    An SM5 sheet is a ready-made DMR 4G file that exists only at 5 m; TM33
    tiles are cut from the service, where ``2m`` and ``5m`` are a real choice.
    Raises ``ValidationError`` (or ``ParseError`` for a malformed code).
    """
    sheet = sheet.strip()
    system = detect_system(sheet)
    if system.country != "CZ":
        raise ValidationError(f"Godlo '{sheet}' nie nalezy do zadnego systemu CZ")
    if system.id == "cz_sm5":
        if resolution not in (None, "5m"):
            raise ValidationError(
                f"Arkusze SM5 sa dostepne tylko w 5m (DMR 4G) - pomin "
                f"--resolution albo podaj 5m; dla {resolution} uzyj godla TM33 "
                f"albo --bbox [arkusz: {sheet}]"
            )
        return "5m"
    if resolution is None:
        raise ValidationError(f"--resolution wymagane dla NMT CZ: {RESOLUTION_CZ}")
    return resolution


def _sheet_slot(provider, sheet: str, output_dir: str | Path) -> tuple[FileSlot, bool]:
    sheet = sheet.strip()
    system = detect_system(sheet)
    if system.country != "CZ":
        raise ValidationError(f"Godlo '{sheet}' nie nalezy do zadnego systemu CZ")
    sm5 = system.id == "cz_sm5"
    descriptor = get_source(provider.descriptor_key)
    storage = storage_for_provider(
        output_dir,
        provider,
        resolution=provider.resolution,
        vertical_crs=provider.vertical_crs,
    )
    return (
        FileSlot(
            Path(output_dir),
            storage.get_raw_path(sheet, f"{sheet}{descriptor.default_extension}"),
            storage.get_raw_versions_base(sheet),
            storage.get_raw_versions_root(sheet),
            descriptor.default_extension,
        ),
        sm5,
    )


def _signal(provider, sm5: bool) -> SignalKind:
    transport = TransportKind.DIRECT_FILES if sm5 else TransportKind.ARCGIS_IMAGE
    return channel_signal(provider.descriptor_key, transport)


def _check_sheet(provider, sheet: str, *, output_dir: str | Path) -> UpdatePlan:
    """Inspect one CZ sheet without transferring raster bytes."""
    sheet = sheet.strip()
    slot, sm5 = _sheet_slot(provider, sheet, output_dir)
    item = inspect_version(
        slot,
        track="cz_sheet",
        unit=sheet,
        signal=_signal(provider, sm5),
        probe=(lambda: provider.sm5_signal(sheet)) if sm5 else None,
    )
    return new_plan(store_id(output_dir), (item,))


def _local_result(slot: FileSlot, stale: tuple[PlanItem, ...]) -> CzSheetResult:
    """Return a planned-but-unselected sheet without probing or reading raster data."""
    local = local_version(slot)
    if local is None:
        return CzSheetResult(None, False, stale)
    link_version(slot.std, local, refresh=False)
    return CzSheetResult(
        VersionedFile(slot.std, "local", local.label, local.sha256, local.path),
        local.meta.get("extra", {}).get("all_nodata", False) is True,
        stale,
    )


def _run_cz_sheet(
    provider,
    sheet: str,
    *,
    output_dir: str | Path,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzSheetResult:
    """Download or use the local version of a TM33 tile or an SM5 sheet.

    SM5 compares the openzu ZIP's HTTP signal with one HEAD request when a
    local version exists; TM33 has no cheap freshness signal. With a plan,
    only a matching ``missing``/``newer`` position may be downloaded; a
    skipped position with no local version has ``file=None``.
    """
    validate_update(update)
    if plan is not None and update != "upgrade":
        raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
    sheet = sheet.strip()
    slot, sm5 = _sheet_slot(provider, sheet, output_dir)
    signal = _signal(provider, sm5)
    probe = (lambda: provider.sm5_signal(sheet)) if sm5 else None
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        require_store(plan, store_id(output_dir))
        scoped = replace(
            plan,
            items=tuple(
                item for item in plan.items_for("cz_sheet") if item.unit == sheet
            ),
        )
        if not any(item.status in TODO_STATUSES for item in scoped.items):
            return _local_result(slot, ())
        fresh = _check_sheet(provider, sheet, output_dir=output_dir).items
        if fresh[0].status == "check_failed":
            raise DownloadError(
                f"Nie udalo sie sprawdzic arkusza CZ {sheet}: {fresh[0].error}"
            )
        todo, rejected = select_planned(scoped, list(fresh), "cz_sheet")
        stale = tuple(rejected)
        if not todo:
            return _local_result(slot, stale)
        # The plan was just checked: reuse that one HEAD result instead of
        # issuing a second HEAD for the same signal before downloading.
        if sm5:
            available_signal = todo[0].available_signal

            def planned_probe() -> dict:
                return available_signal or {}

            probe = planned_probe

    received: dict | None = None
    empty = False

    def on_response(response: requests.Response) -> None:
        nonlocal received
        received = response_signal(response)

    def fetch(staged: Path) -> dict | None:
        provider.download(
            sheet,
            staged,
            on_download=on_download,
            on_response=on_response if sm5 else None,
        )
        return received if sm5 else None

    def write_sidecar(
        data: Path, version: VersionRef, digest: ContentDigest, http: dict | None
    ) -> None:
        nonlocal empty
        nodata = read_tif_nodata(data)
        empty = _all_nodata(data, nodata)
        extra: dict = {"all_nodata": empty}
        if http is not None:
            extra["http"] = http
        if sm5:
            try:
                info = provider.sheet_index.sm5_sheet(sheet)
                if info.name is not None:
                    extra["mapname"] = info.name
                if info.podil is not None:
                    extra["cz_share"] = info.podil
            except Exception as e:  # noqa: BLE001 — data matters more than metadata
                logger.warning(
                    f"Sidecar {sheet} bez extra.cz_share (PODIL; blad indeksu): {e}"
                )
        horizontal_crs = "EPSG:5514" if sm5 else "EPSG:3045"
        emit_sidecar(
            provider.descriptor_key,
            data,
            request={"sheet": sheet},
            vertical_crs=provider.vertical_crs,
            horizontal_crs=horizontal_crs,
            pinned_transforms={
                "horizontal": provider.horizontal_transform(horizontal_crs),
                "vertical": provider.vertical_transform,
            },
            capability="sheet_files" if sm5 else "bbox_raster",
            nodata=nodata,
            extra=extra,
            digest=(digest.sha256, digest.size_bytes),
            version=version.to_extra(),
            exclusive=True,
        )

    file = fetch_version(
        slot,
        update,
        signal=signal,
        fetch=fetch,
        version=VersionRef.downloaded(),
        write_sidecar=write_sidecar,
        probe=probe,
    )
    if file.status == "local":
        stored = read_version(file.version_path.parent, file.version_path.name)
        empty = (
            stored is not None
            and stored.meta.get("extra", {}).get("all_nodata", False) is True
        )
    return CzSheetResult(file, empty, stale)


def _sheet_provider(sheet: str, *, vertical_crs: str, resolution: str | None, cache):
    """CZ DMR provider for a sheet code after the resolution rule of the code."""
    from kartograf.providers.cuzk import create_dmr_provider

    return create_dmr_provider(
        resolution=cz_sheet_resolution(sheet, resolution),
        cache=cache,
        vertical_crs=vertical_crs,
    )


def check_cz_sheet(
    sheet: str,
    *,
    output_dir: str | Path,
    vertical_crs: str,
    resolution: str | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_cz_sheet`` with the same arguments, no download.

    SM5 compares the openzu ZIP's HTTP signal (one HEAD request, sheet index
    from the metadata cache); TM33 has no remote signal and reads only the
    local store. Invalid choices raise the same errors as the download.
    """
    sink = NoticeSink(on_notice)
    with open_cache(cache, force=False, on_notice=sink.add) as metadata:
        provider = _sheet_provider(
            sheet, vertical_crs=vertical_crs, resolution=resolution, cache=metadata
        )
        return _check_sheet(provider, sheet, output_dir=output_dir)


def download_cz_sheet(
    sheet: str,
    *,
    output_dir: str | Path,
    vertical_crs: str,
    resolution: str | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzSheetResult:
    """Download or reuse one CZ sheet: an SM5 sheet (openzu) or a TM33 tile.

    ``resolution``: an SM5 sheet exists only at ``5m`` (``None`` = ``5m``);
    a TM33 tile requires ``2m`` or ``5m``. ``vertical_crs`` is ``"Bpv"``
    (native) or ``"EVRF2007"``. SM5 compares the openzu ZIP's HTTP signal with
    one HEAD request when a local version exists; TM33 has no cheap signal.
    ``plan`` (from ``check_cz_sheet`` with ``update="upgrade"``) downloads
    only a matching ``missing``/``newer`` position; a changed position lands in
    ``stale``. ``cache``: ``True`` = default metadata cache in the current
    directory, a ``MetadataCache`` = that cache, ``False`` = none.
    ``on_notice`` receives each data notice when emitted; ``on_download`` is
    called right before the transfer starts.

    Raises
    ------
    ParseError
        Malformed sheet code.
    ValidationError
        Not a CZ code, bad resolution or vertical CRS, plan without upgrade.
    DownloadError
        CUZK service failure; no new version is committed.
    """
    validate_update(update)
    sink = NoticeSink(on_notice)
    with open_cache(cache, force=update == "force", on_notice=sink.add) as metadata:
        provider = _sheet_provider(
            sheet, vertical_crs=vertical_crs, resolution=resolution, cache=metadata
        )
        result = _run_cz_sheet(
            provider,
            sheet,
            output_dir=output_dir,
            update=update,
            plan=plan,
            on_download=on_download,
        )
    emit_cz_all_nodata(sink, result.file, result.all_nodata)
    return replace(result, notices=sink.notices)
