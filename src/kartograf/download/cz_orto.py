"""CZ orthophoto (CUZK) on the versioned store, one SM5 sheet at a time.

ADR-042 D13. The ORTOFOTO ATOM feed lists the current release of every SM5
sheet (``WRTO24.<rok>.<arkusz>.zip``, 16-64 MB; archival CUZK orthophotos
are paid - out of scope). Its ZIP holds a JPEG and three world files, stored
1:1 (no pixel conversion) as four versioned files
``orto/cz_sjtsk/<SM5 hierarchy>/<sheet><suffix>``: ``.jgw`` (S-JTSK,
EPSG:5514), ``.TM33N.jgw`` (ETRS89 / UTM 33N, EPSG:3045), ``.TM34N.jgw``
(ETRS89 / UTM 34N, EPSG:3046) and ``.jpg``.

Signal ``metadata``: the edition of a sheet - the release year and the date
of its dataset feed entry (``2024_2025-02-06``) - comes from ONE
``resolve_atom_file`` call per sheet (remembered also when it fails: the
four files ask it). All four files local with the current edition =
``local`` without a transfer; otherwise the ZIP is downloaded once and its
members are committed in the order ``.jgw``, ``.TM33N.jgw``, ``.TM34N.jgw``,
``.jpg`` - a JPEG version always has its world files, a file whose commit
fails leaves no version and the next run adds it.

Public pair (Z2): ``download_cz_orto_sheet`` / ``check_cz_orto_sheet``;
``cz_orto_area_sheets`` lists the SM5 sheets of an area (``download_data``).
"""

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import requests

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.core.parser_registry import detect_system
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    WriteSidecar,
    discard_staging,
    inspect_version,
    link_version,
    local_file,
    local_version,
    new_staging,
    refreshes_cache,
    store_file,
    use_local,
    validate_update,
)
from kartograf.download.plan import (
    TODO_STATUSES,
    PlanItem,
    Track,
    UpdatePlan,
    new_plan,
    refusal_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import FileStorage
from kartograf.download.versions import ContentDigest, VersionRef, new_incoming_dir
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.marker import lenient_store
from kartograf.messages import message, reason
from kartograf.notices import Notice, NoticeSink
from kartograf.output import plain_of, preflight, writing
from kartograf.sources.descriptor import AtomFilesParams, SignalKind
from kartograf.sources.edition import Edition
from kartograf.sources.registry import get_source
from kartograf.sources.sidecar import emit_sidecar
from kartograf.transport.atom import (
    AtomFile,
    fetch_atom_file,
    resolve_atom_file,
    unpack_members,
)
from kartograf.transport.http import SessionPerThread

logger = logging.getLogger(__name__)

_KEY = "cz.cuzk.orto"
_TRACK: Track = "cz_orto"
_SIGNAL: SignalKind = "metadata"
# Read timeout of a sheet ZIP (16-64 MB; DEV-13.2).
ZIP_TIMEOUT = 120
# CRS georeferenced by each world file. Measured 2026-10-16 on CTES96, CTES86
# and AS91: the origin of the TM33N/TM34N file is the S-JTSK origin
# transformed to EPSG:3045/EPSG:3046 (within 3 cm).
_WORLD_FILES = {
    ".jgw": "EPSG:5514",
    ".TM33N.jgw": "EPSG:3045",
    ".TM34N.jgw": "EPSG:3046",
}
_IMAGE = ".jpg"
_IMAGE_CRS = "EPSG:5514"
# Commit order: the world files before the image.
_SUFFIXES = (*_WORLD_FILES, _IMAGE)
_SM5_CRS = "EPSG:5514"

CZ_ORTO_SHEETS = message("tracks.cz_orto_sheets_hint")

_sessions = SessionPerThread()


def _session() -> requests.Session:
    """HTTP session of the current thread (feeds, ZIPs, sheet index)."""
    return _sessions.get()


@dataclass(frozen=True)
class CzOrtoResult:
    """Describe the result of downloading one CZ orthophoto sheet.

    One CZ orthophoto sheet: its files in commit order (``.jgw``,
    ``.TM33N.jgw``, ``.TM34N.jgw``, ``.jpg``). A plan may skip a file
    without a local version (fewer files); ``stale`` = positions of the plan
    whose source changed since the check; ``notices`` = data notices.
    """

    files: tuple[VersionedFile, ...]
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()


def cz_orto_sheet(sheet: str) -> str:
    """Return the SM5 code of a CZ orthophoto sheet (whitespace stripped).

    Raises
    ------
    ValidationError
        A TM33 tile code (the tiles are a NMT grid) or a code that is not
        an SM5 sheet.
    """
    code = sheet.strip()
    system = detect_system(code).id
    if system == "cz_tm33":
        raise ValidationError(
            message(
                "tracks.cz_orto_tm33_given", cz_orto_sheets=CZ_ORTO_SHEETS, code=code
            ),
            option="sheet",
        )
    if system != "cz_sm5":
        raise ValidationError(
            message("tracks.cz_orto_bad_sheet_code", code=code),
            option="sheet",
        )
    return code


def cz_orto_area_sheets(bbox: BBox) -> tuple[str, ...]:
    """SM5 sheets of an area from the CUZK sheet index, sorted by code.

    ``bbox`` in another CRS than EPSG:5514 is converted by the pinned
    operation (ADR-024); sheets touching the area only with an edge do not
    count (``SheetIndex``).

    Raises
    ------
    DownloadError
        The sheet index does not answer.
    TransformError
        No safe operation into EPSG:5514 for the area.
    """
    from kartograf.providers.cuzk.client import wkid
    from kartograf.providers.cuzk.raster import bbox_to_crs
    from kartograf.providers.cuzk.sheets import SheetIndex

    area = bbox if wkid(bbox.crs) == wkid(_SM5_CRS) else bbox_to_crs(bbox, _SM5_CRS)
    infos = SheetIndex(session=_session()).sm5_sheets_for_bbox(area)
    return tuple(info.sheet for info in infos)


def _params() -> AtomFilesParams:
    (params,) = (
        channel.params
        for channel in get_source(_KEY).channels
        if isinstance(channel.params, AtomFilesParams)
    )
    return params


def _slots(sheet: str, root: str | Path) -> dict[str, FileSlot]:
    """Build the four store slots of a sheet in commit order.

    The four store slots of a sheet (commit order): one SM5 hierarchy,
    ``versions/<hierarchy>/<label>_<sha8>/`` per file.
    """
    storage = FileStorage(
        root,
        resolution=None,
        vertical_crs=None,
        subdir=get_source(_KEY).storage_subdir,
    )
    base = storage.get_raw_versions_base(sheet)
    versions_root = storage.get_raw_versions_root(sheet)
    slots = {}
    for suffix in _SUFFIXES:
        std = storage.get_raw_path(sheet, f"{sheet}{suffix}")
        slots[suffix] = FileSlot(Path(root), std, base, versions_root, std.suffix)
    return slots


def _release_lookup(
    session: requests.Session,
    sheet: str,
    metadata: MetadataCache | None,
    *,
    refresh: bool,
) -> Callable[[], AtomFile]:
    """Return a callable resolving the current release of the sheet.

    The current release of the sheet from ONE ``resolve_atom_file`` call;
    a failure is remembered too (raised again, not asked again).
    """
    outcome: list[AtomFile | DownloadError] = []

    def release() -> AtomFile:
        if not outcome:
            try:
                outcome.append(
                    resolve_atom_file(
                        session,
                        _params(),
                        key=sheet,
                        crs=None,
                        cache=metadata,
                        refresh=refresh,
                    )
                )
            except DownloadError as e:
                outcome.append(e)
        found = outcome[0]
        if isinstance(found, DownloadError):
            raise found
        return found

    return release


def _edition(release: Callable[[], AtomFile]) -> Callable[[], Edition]:
    """``EditionLookup`` of the store: the release label and its dataset feed."""

    def edition() -> Edition:
        file = release()
        return Edition(id=file.edition, url=file.dataset_feed)

    return edition


def _inspect(
    slots: dict[str, FileSlot], sheet: str, edition: Callable[[], Edition]
) -> list[PlanItem]:
    return [
        inspect_version(slot, track=_TRACK, unit=sheet, signal=_SIGNAL, edition=edition)
        for slot in slots.values()
    ]


def _local_file(slot: FileSlot) -> VersionedFile | None:
    """Return the local version of a file outside the plan, linked; no request."""
    local = local_version(slot)
    if local is None:
        return None
    link_version(slot.std, local, refresh=False)
    return local_file(slot.std, local)


def _sheet_extra(
    session: requests.Session,
    metadata: MetadataCache | None,
    sheet: str,
    parent_request: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the ``extra`` shared by the files of a sheet.

    ``extra`` shared by the files of a sheet: map name and the share of the
    sheet in CZ from the sheet index (best effort), ``parent_request``.
    """
    from kartograf.providers.cuzk.sheets import SheetIndex

    extra: dict[str, Any] = {}
    try:
        info = SheetIndex(session=session, cache=metadata).sm5_sheet(sheet)
        if info.name is not None:
            extra["mapname"] = info.name
        if info.podil is not None:
            extra["cz_share"] = info.podil
    except Exception as e:  # noqa: BLE001 — data matters more than metadata
        logger.warning(
            message("tracks.sidecar_missing_extra", sheet=sheet, error=reason(e))
        )
    if parent_request:
        extra["parent_request"] = parent_request
    return extra


def _writer(
    sheet: str, suffix: str, member: str, file: AtomFile, extra: dict[str, Any]
) -> WriteSidecar:
    """Build the version sidecar writer of one member.

    Version sidecar of one member: its CRS, the release and the member name;
    the JPEG names the CRS of every world file.
    """
    source = {
        "url": file.url,
        "dataset_feed": file.dataset_feed,
        "edition": file.edition,
        "year": int(file.groups["year"]),
        "updated": file.updated,
        "member": member,
    }
    own = {**extra, "source": source}
    if suffix == _IMAGE:
        own["world_files"] = dict(_WORLD_FILES)

    def write(
        data: Path,
        version: VersionRef,
        digest: ContentDigest,
        http: dict[str, Any] | None,
    ) -> None:
        emit_sidecar(
            _KEY,
            data,
            request={"sheet": sheet},
            horizontal_crs=_WORLD_FILES.get(suffix, _IMAGE_CRS),
            capability="sheet_files",
            extra={**own, "http": http} if http is not None else own,
            digest=(digest.sha256, digest.size_bytes),
            version=version.to_extra(),
            exclusive=True,
        )

    return write


def _stage(slot: FileSlot, unpacked: Path) -> Path:
    """Move an unpacked member into the slot's own staging directory."""
    staged = new_staging(slot)
    try:
        os.replace(unpacked, staged)
    except BaseException:
        discard_staging(staged, slot)
        raise
    return staged


def _download(
    session: requests.Session,
    metadata: MetadataCache | None,
    sheet: str,
    slots: dict[str, FileSlot],
    scope: set[str],
    release: Callable[[], AtomFile],
    parent_request: dict[str, Any] | None,
    on_download: Callable[[], None] | None,
) -> dict[str, VersionedFile]:
    """Commit the members of one ZIP of the current release.

    One ZIP of the current release; the members of ``scope`` committed in
    the order of ``_SUFFIXES`` (staging removed in every case).
    """
    file = release()  # the label before the transfer (D30)
    version = VersionRef(file.edition, "edition")
    image = slots[_IMAGE]
    plain = plain_of(image.root)
    if plain is not None:  # the ZIP and its members in one private staging directory
        archive = plain.stage_path(f"{sheet}.zip")
    else:
        lenient_store(image.root)
        archive = new_incoming_dir(image.versions_base) / f"{sheet}.zip"
    stored: dict[str, VersionedFile] = {}
    try:
        if on_download is not None:
            on_download()
        http = fetch_atom_file(session, file, archive, timeout=ZIP_TIMEOUT)
        members = unpack_members(
            archive, _params(), archive.parent, sheet, url=file.url
        )
        archive.unlink()
        extra = _sheet_extra(session, metadata, sheet, parent_request)
        for suffix in _SUFFIXES:
            if suffix not in scope:
                continue
            slot = slots[suffix]
            stored[suffix] = store_file(
                slot,
                _stage(slot, members[suffix].path),
                version=version,
                write_sidecar=_writer(
                    sheet, suffix, members[suffix].member, file, extra
                ),
                http=http,
                signal=_SIGNAL,
            )
    finally:
        discard_staging(archive, image)
    return stored


def _run(
    session: requests.Session,
    metadata: MetadataCache | None,
    sheet: str,
    *,
    root: str | Path,
    update: UpdateMode | None,
    plan: UpdatePlan | None,
    parent_request: dict[str, Any] | None,
    on_download: Callable[[], None] | None,
) -> CzOrtoResult:
    """Local files or one download of the sheet (module docstring).

    With a plan only its ``missing``/``newer`` positions of this sheet are
    stored; a position whose source changed since the check is ``stale``.
    """
    slots = _slots(sheet, root)
    preflight(root, [slot.name for slot in slots.values()])
    release = _release_lookup(session, sheet, metadata, refresh=update == "upgrade")
    edition = _edition(release)
    outcome: dict[str, VersionedFile | None]
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        require_store(plan, store_id(root))
        scoped = replace(
            plan,
            items=tuple(item for item in plan.items_for(_TRACK) if item.unit == sheet),
        )
        outcome = {suffix: _local_file(slot) for suffix, slot in slots.items()}
        if not any(item.status in TODO_STATUSES for item in scoped.items):
            return CzOrtoResult(_present(outcome))
        fresh = _inspect(slots, sheet, edition)
        failed = next((item for item in fresh if item.status == "check_failed"), None)
        if failed is not None:
            raise DownloadError(
                message("tracks.cz_orto_check_failed", sheet=sheet, error=failed.error)
            )
        todo, rejected = select_planned(scoped, fresh, _TRACK)
        stale = tuple(rejected)
        names = {item.name for item in todo}
        scope = {suffix for suffix, slot in slots.items() if slot.name in names}
        if not scope:
            return CzOrtoResult(_present(outcome), stale)
    else:
        outcome = {
            suffix: use_local(slot, update, signal=_SIGNAL, edition=edition)
            for suffix, slot in slots.items()
        }
        if all(file is not None for file in outcome.values()):
            return CzOrtoResult(_present(outcome))
        scope = set(slots)
    stored = _download(
        session, metadata, sheet, slots, scope, release, parent_request, on_download
    )
    return CzOrtoResult(_present({**outcome, **stored}), stale)


def _present(outcome: dict[str, VersionedFile | None]) -> tuple[VersionedFile, ...]:
    return tuple(file for file in outcome.values() if file is not None)


def check_cz_orto_sheet(
    *,
    sheet: str,
    root: str | Path | None = None,
    output_dir: str | Path | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Plan the update of one CZ orthophoto sheet.

    Update plan of ``download_cz_orto_sheet``: four positions (track
    ``cz_orto``), the current edition from the ATOM feeds, no image download.

    ``current``/``newer`` compare the local edition label, ``missing`` = no
    local file, ``check_failed`` = the feeds could not be read. The source is
    always asked: the metadata cache is refreshed, never read. With ``output_dir``
    the four positions are the targets of a plain write (``action``, ``path``) and
    no feed is read.

    Raises
    ------
    ValidationError
        Not an SM5 sheet code (TM33 tiles are NMT only).
    """
    sheet = cz_orto_sheet(sheet)
    sink = NoticeSink(on_notice)
    with (
        writing(output_dir=output_dir, root=root, guard=False) as store,
        open_cache(cache, force=True, on_notice=sink.add) as metadata,
    ):
        if (refused := refusal_plan(store)) is not None:
            return refused
        release = _release_lookup(_session(), sheet, metadata, refresh=True)
        items = _inspect(_slots(sheet, store), sheet, _edition(release))
        return new_plan(store_id(store), items)


def download_cz_orto_sheet(
    *,
    sheet: str,
    root: str | Path | None = None,
    output_dir: str | Path | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    parent_request: dict[str, Any] | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzOrtoResult:
    """Download or reuse the current CUZK orthophoto of one SM5 sheet.

    Four files under ``orto/cz_sjtsk/<SM5 hierarchy>/``: the JPEG and its
    world files, bytes of the ZIP members 1:1. ``update``: ``None`` = local
    files when all four exist (a newer edition only reported in
    ``VersionedFile.newer``), missing ones downloaded; ``"upgrade"`` = a newer
    edition downloaded (older versions stay in ``versions/``); ``"force"`` =
    downloaded again. ``plan`` (``check_cz_orto_sheet`` with
    ``update="upgrade"``) stores only its ``missing``/``newer`` positions of
    the sheet. ``output_dir`` writes the four plain files ``<sheet>.jpg`` and its
    world files into that directory instead of the store (no sidecar, no version;
    ``update="force"`` replaces existing files, a conflict stops before the first
    byte; it excludes ``root``, ``update="upgrade"`` and ``plan``).
    ``parent_request`` (area requests) goes into the sidecars.
    ``cache``: ``True`` = default metadata cache in the current directory, a
    ``MetadataCache`` = that cache (the ATOM feed index), ``False`` = none
    (the whole service feed, 23.7 MB, is read for every sheet).
    ``on_notice`` receives each data notice when emitted, ``on_download`` is
    called right before the ZIP transfer.

    Raises
    ------
    ValidationError
        Not an SM5 sheet code, an unknown ``update``, a plan without
        ``update="upgrade"`` or of another store.
    NoCoverageError
        The ATOM feed has no orthophoto of the sheet.
    DownloadError
        Feed, transfer or store failure; files committed before the failure
        (world files before the JPEG) stay, the failed one has no version.
    """
    sheet = cz_orto_sheet(sheet)
    validate_update(update, check="check_cz_orto_sheet")
    if plan is not None and update != "upgrade":
        raise ValidationError(message("hydrology.plan_requires_upgrade"))
    sink = NoticeSink(on_notice)
    with (
        writing(output_dir=output_dir, root=root, update=update, plan=plan) as store,
        open_cache(
            cache, force=refreshes_cache(update), on_notice=sink.add
        ) as metadata,
    ):
        result = _run(
            _session(),
            metadata,
            sheet,
            root=store,
            update=update,
            plan=plan,
            parent_request=parent_request,
            on_download=on_download,
        )
    return replace(result, notices=sink.notices)
