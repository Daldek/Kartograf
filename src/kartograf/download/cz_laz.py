"""CUZK point clouds (LAZ) on the versioned file store - library layer.

One request = one model and height system: ``Bpv`` selects SM5 sheets
(S-JTSK, EPSG:5514), ``EVRF2007`` TM33 tiles (ETRS89, EPSG:3045) - the only
pairs CUZK publishes, and a point cloud is never transformed (plan B,
decision 2). A sheet code or an area (any supported CRS; sheets from the
``KladyMapovychListu`` index) selects the files; each one is versioned like an
SM5 raster sheet: HTTP signal of the openzu ZIP (one ``HEAD`` for a local
version), label ``downloaded``, plan track ``cz_laz``. Files download in
parallel; a failed file does not stop the others (``CzLazResult.failed``).

Example::

    from kartograf import BBox, download_cz_laz

    result = download_cz_laz(
        model="dmr5g", vertical_crs="Bpv", root="./data",
        bbox=BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514"),
    )
    for failure in result.failed:
        print(failure.sheet, failure.error)
"""

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import requests

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.download.arguments import require_workers
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    fetch_version,
    inspect_version,
    refreshes_cache,
    validate_update,
)
from kartograf.download.plan import (
    PlanItem,
    UpdatePlan,
    new_plan,
    refusal_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import storage_for_provider
from kartograf.download.versions import ContentDigest, VersionRef
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.interrupt import run_parallel
from kartograf.messages import message, reason
from kartograf.notices import Notice, NoticeSink
from kartograf.output import preflight, writing
from kartograf.providers.cuzk.laz import CuzkLazProvider
from kartograf.sources.descriptor import SignalKind, TransportKind
from kartograf.sources.registry import channel_for
from kartograf.sources.sidecar import emit_sidecar
from kartograf.sources.variants import cz_sheet_system, find_cz_laz_variant
from kartograf.transport.http import response_signal

logger = logging.getLogger(__name__)

# (processed files, files selected for execution) - called in the caller's
# thread; ``(0, total)`` comes once before the first file (as LAZ PL).
CzLazProgressCallback = Callable[[int, int], None]

NO_SHEETS_MESSAGE = message("tracks.no_laz_sheets")


@dataclass(frozen=True)
class CzLazFailure:
    """A sheet whose file could not be downloaded, and the download error."""

    sheet: str
    error: DownloadError


@dataclass(frozen=True)
class CzLazResult:
    """Selected sheets, versioned files, failures and stale plan items.

    With ``plan=`` the files include only executed plan positions. Results
    are ordered by sheet code.
    """

    sheets: tuple[str, ...]
    files: tuple[VersionedFile, ...] = ()
    failed: tuple[CzLazFailure, ...] = ()
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()

    @property
    def ok(self) -> bool:
        """True when no file failed."""
        return not self.failed


def _slot(provider: CuzkLazProvider, sheet: str, root: str | Path) -> FileSlot:
    """``laz/cz_<model>_<vcrs>/<sheet hierarchy>/<sheet>.laz`` and its versions."""
    storage = storage_for_provider(
        root, provider, resolution=None, vertical_crs=provider.vertical_crs
    )
    return FileSlot(
        Path(root),
        storage.get_raw_path(sheet, f"{sheet}{provider.default_extension}"),
        storage.get_raw_versions_base(sheet),
        storage.get_raw_versions_root(sheet),
        provider.default_extension,
    )


def _signal(provider: CuzkLazProvider) -> SignalKind:
    return channel_for(
        provider.descriptor_key or "",
        TransportKind.DIRECT_FILES,
        provider.horizontal_crs,
    ).update_signal


def _provider(model: str, vertical_crs: str, cache: MetadataCache | None) -> Any:
    # looked up on the module: callers patch the class at its source
    from kartograf.providers.cuzk import laz

    return laz.CuzkLazProvider(model, cache=cache, vertical_crs=vertical_crs)


def _validate_selection(
    *, model: str, vertical_crs: str, sheet: str | None, bbox: BBox | None
) -> BBox | None:
    """Validate the choice of exactly one of ``sheet``/``bbox`` before any request.

    Exactly one of ``sheet``/``bbox`` and a valid choice - before any
    request; the bbox in the registry spelling of its CRS (or ``None``).
    """
    from kartograf.download.options import validate_request_bbox

    if (sheet is None) == (bbox is None):
        raise ValidationError(message("tracks.sheet_or_bbox_required"))
    if bbox is not None:
        bbox = validate_request_bbox(bbox)
    system = cz_sheet_system(sheet) if sheet is not None else None
    find_cz_laz_variant(model=model, vertical_crs=vertical_crs, system=system)
    return bbox


def _select(
    provider: CuzkLazProvider, sheet: str | None, bbox: BBox | None
) -> tuple[str, ...]:
    """Sheet codes of the request, sorted; an area without sheets is an error."""
    if sheet is not None:
        return (sheet.strip(),)
    assert bbox is not None  # _validate_selection
    sheets = tuple(info.sheet for info in provider.sheets(bbox))
    if not sheets:
        raise NoCoverageError(NO_SHEETS_MESSAGE)
    return sheets


def _check(
    provider: CuzkLazProvider, sheets: tuple[str, ...], root: str | Path
) -> UpdatePlan:
    """Plan positions of the sheets: one ``HEAD`` each, no file transfer."""
    signal = _signal(provider)
    items = tuple(
        inspect_version(
            _slot(provider, sheet, root),
            track="cz_laz",
            unit=sheet,
            signal=signal,
            probe=functools.partial(provider.file_signal, sheet),
        )
        for sheet in sheets
    )
    return new_plan(store_id(root), items)


def _fetch_sheet(
    provider: CuzkLazProvider,
    sheet: str,
    *,
    root: str | Path,
    update: UpdateMode | None,
    parent_request: dict[str, Any] | None,
    planned: dict[str, Any] | None,
) -> VersionedFile:
    """Local version or download of one sheet's file with its sidecar.

    ``planned``: the signal of a just-checked plan position - reused instead
    of a second ``HEAD`` before the download.
    """
    slot = _slot(provider, sheet, root)
    received: dict[str, Any] | None = None

    def on_response(response: requests.Response) -> None:
        nonlocal received
        received = response_signal(response)

    def fetch(staged: Path) -> dict[str, Any] | None:
        provider.download(sheet, staged, on_response=on_response)
        return received

    def probe() -> dict[str, Any]:
        if planned is not None:
            return planned
        return provider.file_signal(sheet)

    def write_sidecar(
        data: Path,
        version: VersionRef,
        digest: ContentDigest,
        http: dict[str, Any] | None,
    ) -> None:
        extra: dict[str, Any] = {}
        if http is not None:
            extra["http"] = http
        if provider.system == "sm5":
            try:
                info = provider.sheet_index.sm5_sheet(sheet)
                if info.name is not None:
                    extra["mapname"] = info.name
                if info.podil is not None:
                    extra["cz_share"] = info.podil
            except Exception as e:  # noqa: BLE001 - data matters more than metadata
                logger.warning(
                    message("tracks.sidecar_no_cz_share", sheet=sheet, error=reason(e))
                )
        if parent_request is not None:
            extra["parent_request"] = parent_request
        emit_sidecar(
            provider.descriptor_key,
            data,
            request={"sheet": sheet},
            vertical_crs=provider.vertical_crs,
            horizontal_crs=provider.horizontal_crs,
            capability="sheet_files",
            extra=extra,
            digest=(digest.sha256, digest.size_bytes),
            version=version.to_extra(),
            exclusive=True,
        )

    return fetch_version(
        slot,
        update,
        signal=_signal(provider),
        fetch=fetch,
        version=VersionRef.downloaded(),
        write_sidecar=write_sidecar,
        probe=probe,
    )


def _run(
    provider: CuzkLazProvider,
    sheets: tuple[str, ...],
    *,
    root: str | Path,
    update: UpdateMode | None,
    plan: UpdatePlan | None,
    parent_request: dict[str, Any] | None,
    workers: int,
    on_progress: CzLazProgressCallback | None,
) -> CzLazResult:
    """Version the files of the sheets, collecting per-sheet failures."""
    selected = sheets
    planned: dict[str, dict[str, Any] | None] = {}
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        require_store(plan, store_id(root))
        fresh = _check(provider, sheets, root).items
        todo, excluded = select_planned(plan, list(fresh), "cz_laz")
        planned = {item.unit: item.available_signal for item in todo}
        selected = tuple(sheet for sheet in sheets if sheet in planned)
        stale = tuple(excluded)
    preflight(root, [_slot(provider, sheet, root).name for sheet in selected])
    total = len(selected)

    def fetch(sheet: str) -> tuple[str, VersionedFile | None, DownloadError | None]:
        try:
            file = _fetch_sheet(
                provider,
                sheet,
                root=root,
                update=update,
                parent_request=parent_request,
                planned=planned.get(sheet),
            )
        except DownloadError as error:
            return sheet, None, error
        return sheet, file, None

    outcomes: list[tuple[str, VersionedFile | None, DownloadError | None]] = []

    def record(outcome: tuple[str, VersionedFile | None, DownloadError | None]) -> None:
        outcomes.append(outcome)
        if on_progress is not None:
            on_progress(len(outcomes), total)

    if on_progress is not None:
        on_progress(0, total)
    if workers > 1 and total > 1:
        run_parallel(
            fetch,
            selected,
            workers=workers,
            on_done=lambda _ended, _sheet, outcome: record(outcome),
        )
    else:
        for sheet in selected:
            record(fetch(sheet))

    outcomes.sort(key=lambda outcome: outcome[0])
    return CzLazResult(
        sheets=sheets,
        files=tuple(file for _, file, _ in outcomes if file is not None),
        failed=tuple(
            CzLazFailure(sheet, error)
            for sheet, _, error in outcomes
            if error is not None
        ),
        stale=stale,
    )


def check_cz_laz(
    *,
    model: str,
    vertical_crs: str,
    root: str | Path | None = None,
    output_dir: str | Path | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_cz_laz`` with the same selection, no download.

    One ``HEAD`` per file (plus the index query of an area); positions of
    track ``cz_laz`` with the sheet code as ``unit``. The source is always
    asked: the metadata cache is refreshed, never read. Invalid choices
    raise the same errors as the download. With ``output_dir`` the positions are the
    targets of a plain write (``action``, ``path``), nothing is probed.
    """
    bbox = _validate_selection(
        model=model, vertical_crs=vertical_crs, sheet=sheet, bbox=bbox
    )
    sink = NoticeSink(on_notice)
    with (
        writing(output_dir=output_dir, root=root, guard=False) as store,
        open_cache(cache, force=True, on_notice=sink.add) as metadata,
    ):
        if (refused := refusal_plan(store)) is not None:
            return refused
        provider = _provider(model, vertical_crs, metadata)
        return _check(provider, _select(provider, sheet, bbox), store)


def download_cz_laz(
    *,
    model: str,
    vertical_crs: str,
    root: str | Path | None = None,
    output_dir: str | Path | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    parent_request: dict[str, Any] | None = None,
    workers: int = 4,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
    on_progress: CzLazProgressCallback | None = None,
) -> CzLazResult:
    """
    CUZK LAZ files of a sheet or an area into the versioned store, or plain files.

    Parameters
    ----------
    model : str
        ``dmr5g``, ``dmr4g``, ``dmp1g`` or ``dmpok``.
    vertical_crs : str
        ``"Bpv"`` (SM5 sheets, S-JTSK) or ``"EVRF2007"`` (TM33 tiles,
        ETRS89); the file is stored as published, never transformed.
    root : str or Path, optional
        Store root: ``laz/cz_<model>_<vcrs>/<sheet hierarchy>/<sheet>.laz``;
        the default root when neither ``root`` nor ``output_dir`` is given.
    output_dir : str or Path, optional
        Write plain files ``<sheet>.laz`` into this directory instead (DEV-19.1;
        no sidecar, no version; ``update="force"`` replaces existing files, a
        conflict stops before the first byte). Excludes ``root``; not with
        ``update="upgrade"`` or ``plan``.
    sheet, bbox
        Exactly one: a sheet code of the height system's sheet system, or
        an area in any supported CRS (sheets from ``KladyMapovychListu``).
    update : None or "upgrade" or "force", optional
        Default: a local version is used after one ``HEAD`` (a changed
        source is reported in ``newer``); ``"upgrade"`` downloads a changed
        file; ``"force"`` downloads again.
    plan : UpdatePlan, optional
        From :func:`check_cz_laz`; with ``update="upgrade"`` only its
        ``missing``/``newer`` positions execute, changed ones land in ``stale``.
    parent_request : dict, optional
        Sidecar ``extra.parent_request`` of an area request.
    workers : int
        Parallel file downloads (1 = sequential).
    cache : MetadataCache or bool
        ``True`` = default metadata cache in the current directory, a
        ``MetadataCache`` = that cache, ``False`` = none.
    on_notice, on_progress
        Data notices; progress ``(done, total)`` (``(0, total)`` first).

    Returns
    -------
    CzLazResult
        File failures (e.g. a 404 with the sheet index hint) are in
        ``failed``, not raised - ``result.ok``.

    Raises
    ------
    ValidationError
        Not exactly one of ``sheet``/``bbox``, unknown model, a height
        system without LAZ, a sheet of the other system, ``workers`` not an
        ``int``, a plan without ``"upgrade"`` - all before any request.
    NoCoverageError
        No index sheet for the area.
    DownloadError
        Index or plan check failure.
    """
    validate_update(update, check="check_cz_laz")
    require_workers(workers, "workers")
    bbox = _validate_selection(
        model=model, vertical_crs=vertical_crs, sheet=sheet, bbox=bbox
    )
    if plan is not None and update != "upgrade":
        raise ValidationError(message("hydrology.plan_requires_upgrade"))
    sink = NoticeSink(on_notice)
    with (
        writing(output_dir=output_dir, root=root, update=update, plan=plan) as store,
        open_cache(
            cache, force=refreshes_cache(update), on_notice=sink.add
        ) as metadata,
    ):
        provider = _provider(model, vertical_crs, metadata)
        result = _run(
            provider,
            _select(provider, sheet, bbox),
            root=store,
            update=update,
            plan=plan,
            parent_request=parent_request,
            workers=workers,
            on_progress=on_progress,
        )
    return replace(result, notices=sink.notices)
