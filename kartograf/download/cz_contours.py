"""CZ contour lines (ZABAGED, CUZK) on the versioned store, one SM5 sheet at a time.

Plan E1 (raport E, wiersz 16). CUZK publishes the 2D contours of ZABAGED as
one ZIP per SM5 sheet on openzu, in S-JTSK (EPSG:5514) with heights in Bpv,
in two formats - SHP (8 files) and DGN (3 files) - one descriptor each
(``cz.cuzk.zabaged_contours_shp``, ``cz.cuzk.zabaged_contours_dgn``). The
ZIP is stored as published (no unpacking, no conversion) at
``contours/cz_zabaged_<format>/<SM5 hierarchy>/<sheet>.zip``, after its
members were read and checked (an HTML page or a cut ZIP commits no version).

Signal ``http``: a local version compares the ``ETag``/``Last-Modified`` of
the ZIP with one ``HEAD``; plan track ``cz_sheet`` (unit = the SM5 code),
label ``downloaded``.

Public pair (Z2): ``download_cz_contours_sheet`` / ``check_cz_contours_sheet``;
``cz_contours_area_sheets`` lists the SM5 sheets of an area. The library
entry point is ``download_data(product="contours", format=..., ...)``.
"""

import logging
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import requests

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.parser_registry import detect_system
from kartograf.core.sheet_parser import BBox
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
    Track,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import FileStorage
from kartograf.download.versions import ContentDigest, VersionRef
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import FILES, Notice, NoticeSink, count_text
from kartograf.sources.descriptor import SignalKind, SourceDescriptor
from kartograf.sources.registry import get_source
from kartograf.sources.sidecar import emit_sidecar
from kartograf.sources.variants import variants
from kartograf.transport.http import (
    SessionPerThread,
    download_to,
    head_signal,
    response_signal,
)

logger = logging.getLogger(__name__)

PRODUCT = "contours"
_TRACK: Track = "cz_sheet"
_SIGNAL: SignalKind = "http"
_SM5_CRS = "EPSG:5514"
# Timeouts of a sheet ZIP (about 1.5 MB) and of its HEAD (STANDARDS 13.4).
ZIP_TIMEOUT = 60
HEAD_TIMEOUT = 30

CZ_CONTOURS_SHEETS = (
    "warstwice CZ to arkusze SM5 (np. CTES96, AS91); kafle TM33 sa tylko dla NMT i NMPT"
)

_sessions = SessionPerThread()


def _session() -> requests.Session:
    """HTTP session of the current thread (sheet index, HEAD, ZIPs)."""
    return _sessions.get()


@dataclass(frozen=True)
class CzContoursResult:
    """One contour sheet: ``file=None`` only when a plan skips a sheet without
    a local version; ``stale`` = positions of the plan whose source changed
    since the check; ``notices`` = data notices."""

    file: VersionedFile | None
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()


def contours_formats() -> tuple[str, ...]:
    """Formats of the CZ contours (``--format``), registry order."""
    return tuple(v.format for v in variants(product=PRODUCT, country="CZ"))


def contours_source(fmt: str) -> SourceDescriptor:
    """Descriptor of the contours published in ``fmt`` (``"SHP"``, ``"DGN"``).

    Raises
    ------
    ValidationError
        A format the registry has no contours in (the message names them).
    """
    found = variants(product=PRODUCT, country="CZ", format=fmt)
    if len(found) != 1:
        raise ValidationError(
            f"--format {fmt!r}: nieznana wartosc dla --product {PRODUCT} - "
            f"dostepne: {', '.join(contours_formats())}"
        )
    return get_source(found[0].source)


def cz_contours_sheet(sheet: str) -> str:
    """The SM5 code of a contour sheet (whitespace stripped).

    Raises
    ------
    ValidationError
        A TM33 tile code or a code that is not an SM5 sheet.
    """
    code = sheet.strip()
    system = detect_system(code).id
    if system == "cz_tm33":
        raise ValidationError(f"{CZ_CONTOURS_SHEETS} (podano {code})")
    if system != "cz_sm5":
        raise ValidationError(
            f"Godlo '{code}' nie jest arkuszem SM5 warstwic CZ (2 albo 4 wielkie "
            "litery + 2 cyfry, np. CTES96, AS91)"
        )
    return code


def cz_contours_area_sheets(bbox: BBox) -> tuple[str, ...]:
    """SM5 sheets of the CUZK files of an area (a part in CZ), sorted by code.

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
    infos = SheetIndex(session=_session()).file_sheets("sm5", area)
    return tuple(info.sheet for info in infos)


def _slot(source: SourceDescriptor, sheet: str, output_dir: str | Path) -> FileSlot:
    """``contours/cz_zabaged_<format>/<SM5 hierarchy>/<sheet>.zip`` and its versions."""
    storage = FileStorage(
        output_dir, resolution=None, vertical_crs=None, subdir=source.storage_subdir
    )
    return FileSlot(
        Path(output_dir),
        storage.get_raw_path(sheet, f"{sheet}{source.default_extension}"),
        storage.get_raw_versions_base(sheet),
        storage.get_raw_versions_root(sheet),
        source.default_extension,
    )


def _url(source: SourceDescriptor, sheet: str) -> str:
    """openzu ZIP of the sheet (the URL template of the descriptor channel)."""
    (channel,) = source.channels
    return channel.endpoint.format(sheet=sheet)


def _probe(session: requests.Session, url: str) -> Callable[[], dict]:
    def probe() -> dict:
        return head_signal(session, url, timeout=HEAD_TIMEOUT)

    return probe


def _inspect(
    session: requests.Session, source: SourceDescriptor, sheet: str, slot: FileSlot
) -> PlanItem:
    return inspect_version(
        slot,
        track=_TRACK,
        unit=sheet,
        signal=_SIGNAL,
        probe=_probe(session, _url(source, sheet)),
    )


def _local_file(slot: FileSlot) -> VersionedFile | None:
    """The local version of a sheet outside the plan, linked; no request."""
    local = local_version(slot)
    if local is None:
        return None
    link_version(slot.std, local, refresh=False)
    return VersionedFile(slot.std, "local", local.label, local.sha256, local.path)


def _members(path: Path, url: str, fmt: str) -> list[str]:
    """Member names of a downloaded ZIP after a CRC check of every member.

    Raises
    ------
    DownloadError
        Not a ZIP (e.g. an HTML page), a cut or corrupt archive, or a package
        without the ``.<format>`` file.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            names = [info.filename for info in archive.infolist() if not info.is_dir()]
            broken = archive.testzip()
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError) as e:
        raise DownloadError(f"{url}: uszkodzona albo nie-ZIP paczka: {e}") from e
    except OSError as e:
        raise DownloadError(f"{url}: nie udalo sie odczytac paczki: {e}") from e
    if broken is not None:
        raise DownloadError(f"{url}: uszkodzony plik {broken} w paczce ZIP")
    suffix = f".{fmt.lower()}"
    if not any(name.lower().endswith(suffix) for name in names):
        raise DownloadError(
            f"{url}: paczka bez pliku {suffix} ({count_text(len(names), *FILES)}) - "
            "to nie sa oczekiwane dane"
        )
    return sorted(names)


def _sheet_extra(
    session: requests.Session, metadata: MetadataCache | None, sheet: str
) -> dict:
    """Map name and the share of the sheet in CZ from the sheet index (best
    effort: the data matter more than the metadata)."""
    from kartograf.providers.cuzk.sheets import SheetIndex

    extra: dict = {}
    try:
        info = SheetIndex(session=session, cache=metadata).sm5_sheet(sheet)
        if info.name is not None:
            extra["mapname"] = info.name
        if info.podil is not None:
            extra["cz_share"] = info.podil
    except Exception as e:  # noqa: BLE001 - data matters more than metadata
        logger.warning(
            f"Sidecar {sheet} bez extra.mapname/cz_share (blad indeksu): {e}"
        )
    return extra


def _fetch(
    session: requests.Session,
    metadata: MetadataCache | None,
    source: SourceDescriptor,
    sheet: str,
    slot: FileSlot,
    *,
    update: UpdateMode | None,
    planned: dict | None,
    parent_request: dict | None,
    on_download: Callable[[], None] | None,
) -> VersionedFile:
    """Local version or download of the sheet's ZIP with its sidecar.

    ``planned``: the signal of a just-checked plan position - reused instead
    of a second ``HEAD`` before the download.
    """
    url = _url(source, sheet)
    (variant,) = source.variants
    received: dict | None = None
    members: list[str] = []

    def on_response(response: requests.Response) -> None:
        nonlocal received
        received = response_signal(response)

    def fetch(staged: Path) -> dict | None:
        nonlocal members
        if on_download is not None:
            on_download()
        try:
            download_to(
                session, url, staged, timeout=ZIP_TIMEOUT, on_response=on_response
            )
        except DownloadError as e:
            if e.status_code != 404:
                raise
            raise DownloadError(
                f"{e} - CUZK nie ma pliku warstwic arkusza {sheet} (zweryfikuj "
                "godlo w indeksie KladyMapovychListu)",
                sheet=sheet,
                status_code=e.status_code,
            ) from e
        members = _members(staged, url, variant.format)
        return received

    probe = _probe(session, url)
    if planned is not None:

        def planned_probe() -> dict:
            return planned

        probe = planned_probe

    def write_sidecar(
        data: Path, version: VersionRef, digest: ContentDigest, http: dict | None
    ) -> None:
        extra: dict = {"members": members, **_sheet_extra(session, metadata, sheet)}
        if http is not None:
            extra["http"] = http
        if parent_request is not None:
            extra["parent_request"] = parent_request
        emit_sidecar(
            source.key,
            data,
            request={"sheet": sheet, "format": variant.format},
            vertical_crs=variant.vertical_crs,
            horizontal_crs=_SM5_CRS,
            capability="sheet_files",
            extra=extra,
            digest=(digest.sha256, digest.size_bytes),
            version=version.to_extra(),
            exclusive=True,
        )

    return fetch_version(
        slot,
        update,
        signal=_SIGNAL,
        fetch=fetch,
        version=VersionRef.downloaded(),
        write_sidecar=write_sidecar,
        probe=probe,
    )


def _run(
    session: requests.Session,
    metadata: MetadataCache | None,
    source: SourceDescriptor,
    sheet: str,
    *,
    output_dir: str | Path,
    update: UpdateMode | None,
    plan: UpdatePlan | None,
    parent_request: dict | None,
    on_download: Callable[[], None] | None,
) -> CzContoursResult:
    """Local version or one download of the sheet (module docstring).

    With a plan only its ``missing``/``newer`` position of this sheet is
    downloaded; a position whose source changed since the check is ``stale``.
    """
    slot = _slot(source, sheet, output_dir)
    planned: dict | None = None
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        require_store(plan, store_id(output_dir))
        scoped = replace(
            plan,
            items=tuple(
                item
                for item in plan.items_for(_TRACK)
                if item.unit == sheet and item.name == slot.name
            ),
        )
        if not any(item.status in TODO_STATUSES for item in scoped.items):
            return CzContoursResult(_local_file(slot))
        fresh = _inspect(session, source, sheet, slot)
        if fresh.status == "check_failed":
            raise DownloadError(
                f"Nie udalo sie sprawdzic arkusza warstwic CZ {sheet}: {fresh.error}"
            )
        todo, rejected = select_planned(scoped, [fresh], _TRACK)
        stale = tuple(rejected)
        if not todo:
            return CzContoursResult(_local_file(slot), stale)
        planned = todo[0].available_signal or {}
    file = _fetch(
        session,
        metadata,
        source,
        sheet,
        slot,
        update=update,
        planned=planned,
        parent_request=parent_request,
        on_download=on_download,
    )
    return CzContoursResult(file, stale)


def check_cz_contours_sheet(
    sheet: str, *, format: str, output_dir: str | Path
) -> UpdatePlan:
    """Update plan of ``download_cz_contours_sheet``: one position (track
    ``cz_sheet``), one ``HEAD`` of the ZIP, nothing downloaded.

    Raises
    ------
    ValidationError
        Not an SM5 sheet code, or a format without contours.
    """
    sheet = cz_contours_sheet(sheet)
    source = contours_source(format)
    item = _inspect(_session(), source, sheet, _slot(source, sheet, output_dir))
    return new_plan(store_id(output_dir), (item,))


def download_cz_contours_sheet(
    sheet: str,
    *,
    format: str,
    output_dir: str | Path,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    parent_request: dict | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
    on_download: Callable[[], None] | None = None,
) -> CzContoursResult:
    """Download or reuse the ZABAGED contours of one SM5 sheet.

    ``format``: ``"SHP"`` or ``"DGN"`` (the published ZIP, stored 1:1 under
    ``contours/cz_zabaged_<format>/``). ``update``: ``None`` = a local version
    after one ``HEAD`` (a changed ZIP only reported in
    ``VersionedFile.newer``); ``"upgrade"`` = a changed ZIP downloaded (older
    versions stay in ``versions/``); ``"force"`` = downloaded again. ``plan``
    (``check_cz_contours_sheet`` with ``update="upgrade"``) downloads only its
    ``missing``/``newer`` position of the sheet. ``parent_request`` (area
    requests) goes into the sidecar. ``cache``: ``True`` = default metadata
    cache in the current directory (the sheet index record of the sidecar), a
    ``MetadataCache`` = that cache, ``False`` = none. ``on_notice`` receives
    each data notice when emitted, ``on_download`` is called right before the
    ZIP transfer.

    Raises
    ------
    ValidationError
        Not an SM5 sheet code, a format without contours, an unknown
        ``update``, a plan without ``update="upgrade"`` or of another store.
    DownloadError
        openzu failure (a 404 names the sheet index), not a ZIP or a ZIP
        without the format's file; no version is committed.
    """
    sheet = cz_contours_sheet(sheet)
    source = contours_source(format)
    validate_update(update)
    if plan is not None and update != "upgrade":
        raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
    sink = NoticeSink(on_notice)
    with open_cache(cache, force=update == "force", on_notice=sink.add) as metadata:
        result = _run(
            _session(),
            metadata,
            source,
            sheet,
            output_dir=output_dir,
            update=update,
            plan=plan,
            parent_request=parent_request,
            on_download=on_download,
        )
    return replace(result, notices=sink.notices)
