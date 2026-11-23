"""
Files of the releases of a published data set, read from the ZIP of a release.

``ReleaseFilesParams`` (ADR-062): the catchments and the gauges of CAMELS-PL.
``choose_release`` takes the newest release the registry supports, or the one of
``version``; a refused or an unknown version is a ``ValidationError`` naming it,
before any request. ``run_release`` gives every file of the release:

- in the store, a file whose bytes (the SHA-256 the registry pins for the release)
  are a version of its slot is that version, without a request (status ``local``);
  with ``update="force"`` it is read again (``unchanged``). The other files are read
  out of the ZIP: its central directory by HTTP range requests, then each member,
  checked - found by its path pattern exactly once, the length of the ZIP and the
  size, CRC, method and SHA-256 of the member those the registry pins - and only then
  published, all of them, labelled by the date of the first release with these
  bytes: a release with the same bytes makes no new version (``unchanged``). A ZIP
  that differs is a ``ReleaseLayoutError`` naming the version, and nothing is
  written. A server that does not answer a range request with the range gets the
  whole ZIP downloaded (``WHOLE_ARCHIVE``) and the members read from it.
- in a plain write (``output_dir``) every file is read and written under its store
  name, with ``ATTRIBUTION.txt`` (the provider lines, merged into an existing one).

The sidecar of a version names the release it was read from (``extra.release``),
every release the registry knows with these bytes (``extra.releases``) and the
provider lines of the release (``extra.attribution``; ``license.attribution`` holds
them one per line): ``S``, ``P`` and ``L`` for CAMELS-PL (DEV-20.12).
``plan_release`` (``--check``) judges the same files without a transfer. Both ask
the record of the concept DOI for the newest release (one request) and report a
release newer than every one the registry knows (``NEWER_RELEASE``); a run asks it
only when it reads the ZIP or with ``update="upgrade"``.
"""

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import requests

from kartograf.attribution import (
    ATTRIBUTION_FILE,
    plan_attribution,
    provider_lines,
    write_attribution,
)
from kartograf.download.data import UnitFile
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    WriteSidecar,
    discard_staging,
    emit_file_notices,
    link_version,
    local_file,
    local_only,
    new_staging,
    plain_file,
    store_file,
)
from kartograf.download.manager import DownloadProgress
from kartograf.download.plan import (
    PlanItem,
    Track,
    UpdatePlan,
    new_plan,
    select_planned,
)
from kartograf.download.storage import unit_slot
from kartograf.download.versions import (
    ContentDigest,
    LocalVersion,
    VersionRef,
    list_versions,
    newest_version,
)
from kartograf.exceptions import DownloadError, ReleaseLayoutError, ValidationError
from kartograf.marker import lenient_store
from kartograf.messages import message, reason
from kartograf.notices import (
    CHECK_FAILED,
    NEWER_RELEASE,
    WHOLE_ARCHIVE,
    WHOLE_COUNTRY_SIZE,
    NoticeSink,
    ascii_text,
    size_text,
)
from kartograf.output import plain_of, preflight, refuse, unit_of
from kartograf.sources.descriptor import (
    AccessChannel,
    DatasetRelease,
    ReleaseFile,
    ReleaseFilesParams,
    ReleaseMember,
    SourceDescriptor,
)
from kartograf.sources.sidecar import emit_sidecar
from kartograf.transport.http import RANGE_UNSUPPORTED, download_to, get_with_retry
from kartograf.transport.zip_range import (
    READ_METHODS,
    MemberDigest,
    ZipEntry,
    extract_member,
    fetch_member,
    local_directory,
    read_directory,
)

logger = logging.getLogger(__name__)

# The ranges of the ZIP directory, the record of the concept DOI, the transfer of a
# member (its local header included) or of the whole ZIP (read timeouts, seconds).
RANGE_TIMEOUT = 60
RECORD_TIMEOUT = 30
TRANSFER_TIMEOUT = 120
_ENCRYPTED_FLAG = 0x0001

_SlotKey = tuple[str, str, str]
Progress = Callable[[DownloadProgress], None]


@dataclass(frozen=True)
class ReleaseJob:
    """One file of a release request: its member, slot and version label.

    ``unit`` is ``<country>_<theme>`` (``pl_catchments``), the name of the file in
    the store and in a plain write; ``label`` the date of the first release the
    registry knows with the bytes of ``member``.
    """

    file: ReleaseFile
    member: ReleaseMember
    unit: str
    slot: FileSlot
    label: str

    @property
    def key(self) -> _SlotKey:
        """Return the slot identity (segment, hierarchy, name)."""
        return (self.slot.segment, self.slot.hierarchy, self.slot.name)


def release_params(channel: AccessChannel) -> ReleaseFilesParams:
    """Return the ``ReleaseFilesParams`` of a channel of release files."""
    params = channel.params
    assert isinstance(params, ReleaseFilesParams)
    return params


def supported_releases(params: ReleaseFilesParams) -> tuple[DatasetRelease, ...]:
    """Return the releases that are read, oldest first (the last is the default)."""
    return tuple(release for release in params.releases if release.refusal is None)


def choose_release(
    params: ReleaseFilesParams, version: str | None, *, product: str
) -> DatasetRelease:
    """Return the release of ``version``, the newest supported one without it.

    Raises
    ------
    ValidationError
        ``option="version"`` with the supported versions in ``allowed``: a release
        the registry refuses (the text names it and why) or a version it does not
        know (a newer release is read by the Kartograf release that adds it).
    """
    supported = supported_releases(params)
    versions = tuple(release.version for release in supported)
    if version is None:
        return supported[-1]
    found = next((r for r in params.releases if r.version == version), None)
    if found is None:
        raise ValidationError(
            message(
                "releases.unknown_version",
                dataset=params.dataset,
                version=version,
                product=product,
                versions=", ".join(versions),
            ),
            option="version",
            allowed=versions,
        )
    if found.refusal is not None:
        raise ValidationError(
            message(
                "releases.refused_version",
                dataset=params.dataset,
                version=found.version,
                record=found.record,
                refusal=found.refusal,
                versions=", ".join(versions),
            ),
            option="version",
            allowed=versions,
        )
    return found


def release_lines(
    params: ReleaseFilesParams, release: DatasetRelease
) -> tuple[str, ...]:
    """Return the provider lines of the files of ``release`` (DEV §20)."""
    return provider_lines(
        params.lines,
        version=release.version,
        year=release.published[:4],
        doi=release.doi,
    )


def holders(
    params: ReleaseFilesParams, theme: str, sha256: str
) -> tuple[DatasetRelease, ...]:
    """Return the supported releases with these bytes of ``theme``, oldest first."""
    return tuple(
        release
        for release in supported_releases(params)
        if release.member(theme).sha256 == sha256
    )


def release_jobs(
    root: Path,
    params: ReleaseFilesParams,
    release: DatasetRelease,
    *,
    segment: str,
    ext: str,
    country: str,
) -> list[ReleaseJob]:
    """Return one job per file of ``release``, in its slot of ``segment``."""
    jobs = []
    for file in params.files:
        member = release.member(file.theme)
        unit = f"{country.lower()}_{file.theme}"
        (first, *_) = holders(params, file.theme, member.sha256)
        jobs.append(
            ReleaseJob(
                file,
                member,
                unit,
                unit_slot(root, segment, ext, country=unit),
                first.published,
            )
        )
    return jobs


# =============================================================================
# Run
# =============================================================================


def run_release(
    root: Path,
    descriptor: SourceDescriptor,
    channel: AccessChannel,
    release: DatasetRelease,
    *,
    segment: str,
    ext: str,
    request: dict[str, Any],
    update: UpdateMode | None,
    plan: UpdatePlan | None,
    sink: NoticeSink,
    track: Track,
    session: requests.Session,
    on_progress: Progress | None = None,
) -> tuple[tuple[UnitFile, ...], tuple[PlanItem, ...]]:
    """Return the files of ``release`` and the stale positions of ``plan``.

    ``root`` is the store or the handle root of a plain write (``writing``);
    ``request`` the sidecar ``request``. Out of a ``plan``: the local version of a
    file or nothing. The rules are the module's.

    Raises
    ------
    ReleaseLayoutError
        The ZIP differs from what the registry pins for ``release``; nothing is
        written.
    DownloadError
        A request failed, or a member was damaged on the way; nothing is written.
    ConflictError
        A target of a plain write exists (without ``force``), or its
        ``ATTRIBUTION.txt`` is no readable UTF-8 file - before any request.
    """
    params = release_params(channel)
    country = descriptor.country
    jobs = release_jobs(
        root, params, release, segment=segment, ext=ext, country=country
    )
    write = plain_of(root)
    lines = release_lines(params, release)
    if write is not None:
        preflight(root, [job.slot.name for job in jobs])
        entry = plan_attribution(write, lines)
        if entry is not None:
            refuse([entry])
    planned: set[_SlotKey] | None = None
    stale: tuple[PlanItem, ...] = ()
    if plan is not None:
        fresh = [_item(job, release, track) for job in jobs]
        todo, stale_items = select_planned(plan, fresh, track)
        planned = {(item.segment, item.hierarchy, item.name) for item in todo}
        stale = tuple(stale_items)

    def progress(job: ReleaseJob, status: str) -> None:
        if on_progress is not None:
            on_progress(
                DownloadProgress(jobs.index(job) + 1, len(jobs), job.unit, status)
            )

    outcomes: dict[_SlotKey, VersionedFile | None] = {}
    wanted: list[ReleaseJob] = []
    for job in jobs:
        if planned is not None and job.key not in planned:
            outcomes[job.key] = local_only(job.slot)
        elif write is None and update != "force" and (stored := _stored(job)):
            link_version(job.slot.std, stored, refresh=False)
            outcomes[job.key] = local_file(job.slot.std, stored)
        else:
            wanted.append(job)
            continue
        progress(job, "skipped")
    if wanted or update == "upgrade":
        newer_release(params, session, sink, check=False)
    if wanted:
        staged, sources = _stage(
            descriptor, params, release, wanted, session, sink, progress
        )
        done: set[_SlotKey] = set()
        try:
            for job in wanted:
                outcomes[job.key] = store_file(
                    job.slot,
                    staged[job.key],
                    version=VersionRef(job.label, "edition"),
                    write_sidecar=_sidecar(
                        descriptor,
                        channel,
                        params,
                        release,
                        job,
                        request,
                        lines,
                        sources[job.key],
                    ),
                    http=None,
                    signal=channel.update_signal,
                )
                done.add(job.key)
                progress(job, "completed")
        finally:
            for job in wanted:
                if job.key not in done:
                    discard_staging(staged[job.key], job.slot)
    files: list[UnitFile] = []
    for job in jobs:
        outcome = outcomes.get(job.key)
        if outcome is not None:
            files.append(UnitFile(job.unit, country, outcome))
            emit_file_notices(sink, unit_of(outcome.path, root), outcome, update)
    if write is not None:
        written = write_attribution(write, lines)
        if written is not None:
            files.append(UnitFile(ATTRIBUTION_FILE, country, plain_file(written)))
    return tuple(files), stale


def _stored(job: ReleaseJob) -> LocalVersion | None:
    """Return the newest version of the slot with the bytes of the job's member."""
    return newest_version(
        version
        for version in list_versions(job.slot.versions_root, job.slot.name)
        if version.sha256 == job.member.sha256
    )


def _release_document(release: DatasetRelease) -> dict[str, str]:
    """Return the release as the sidecar names it."""
    return {
        "version": release.version,
        "record": release.record,
        "doi": release.doi,
        "published": release.published,
    }


def _sidecar(
    descriptor: SourceDescriptor,
    channel: AccessChannel,
    params: ReleaseFilesParams,
    release: DatasetRelease,
    job: ReleaseJob,
    request: dict[str, Any],
    lines: tuple[str, ...],
    source: dict[str, Any],
) -> WriteSidecar:
    """Return the sidecar writer of one file of ``release`` (module docstring)."""

    def write(
        data: Path, ref: VersionRef, digest: ContentDigest, http: dict[str, Any] | None
    ) -> None:
        extra = {
            "source": source,
            "release": _release_document(release),
            "releases": [
                _release_document(other)
                for other in holders(params, job.file.theme, digest.sha256)
            ],
            "attribution": list(lines),
        }
        emit_sidecar(
            descriptor.key,
            data,
            request=request,
            horizontal_crs=channel.horizontal_crs,
            capability=min(channel.capabilities),
            extra=extra,
            digest=(digest.sha256, digest.size_bytes),
            version=ref.to_extra(),
            exclusive=True,
            attribution="\n".join(lines),
        )

    return write


# =============================================================================
# Reading the ZIP
# =============================================================================


def _layout_error(
    text: str, release: DatasetRelease, member: str | None = None
) -> ReleaseLayoutError:
    return ReleaseLayoutError(
        text,
        version=release.version,
        record=release.record,
        url=release.url,
        member=member,
        hint=message("releases.layout_hint", doi=release.doi),
    )


def _check_length(
    params: ReleaseFilesParams, release: DatasetRelease, length: int | None
) -> None:
    """Check that the ZIP of a release has the length the registry pins."""
    if length != release.size:
        raise _layout_error(
            message(
                "releases.zip_length",
                dataset=params.dataset,
                version=release.version,
                record=release.record,
                url=release.url,
                length=length if length is not None else "?",
                expected=release.size,
            ),
            release,
        )


def _entry(
    params: ReleaseFilesParams,
    release: DatasetRelease,
    job: ReleaseJob,
    entries: tuple[ZipEntry, ...],
) -> ZipEntry:
    """Return the one member of the job's file, as the registry pins it."""
    pattern = re.compile(job.file.pattern)
    found = [entry for entry in entries if pattern.search(entry.name)]
    if len(found) != 1:
        raise _layout_error(
            message(
                "releases.member_count",
                dataset=params.dataset,
                version=release.version,
                record=release.record,
                pattern=job.file.pattern,
                count=len(found),
            ),
            release,
            job.file.pattern,
        )
    (entry,) = found
    member = job.member
    if (entry.size, f"{entry.crc32:08x}") != (member.size, member.crc32):
        raise _layout_error(
            message(
                "releases.member_differs",
                dataset=params.dataset,
                version=release.version,
                record=release.record,
                member=entry.name,
                size=entry.size,
                crc32=f"{entry.crc32:08x}",
                expected_size=member.size,
                expected_crc32=member.crc32,
            ),
            release,
            entry.name,
        )
    if entry.method not in READ_METHODS or entry.flags & _ENCRYPTED_FLAG:
        raise _layout_error(
            message(
                "releases.member_method",
                dataset=params.dataset,
                version=release.version,
                record=release.record,
                member=entry.name,
                method=entry.method,
            ),
            release,
            entry.name,
        )
    return entry


def _check_digest(
    params: ReleaseFilesParams,
    release: DatasetRelease,
    job: ReleaseJob,
    entry: ZipEntry,
    digest: MemberDigest,
) -> None:
    """Check that the unpacked member has the SHA-256 the registry pins."""
    if digest.sha256 != job.member.sha256:
        raise _layout_error(
            message(
                "releases.member_sha256",
                dataset=params.dataset,
                version=release.version,
                record=release.record,
                member=entry.name,
                sha256=digest.sha256,
                expected=job.member.sha256,
            ),
            release,
            entry.name,
        )


def _source(release: DatasetRelease, entry: ZipEntry, read: str) -> dict[str, Any]:
    """``extra.source`` of a file: the ZIP, its member and how it was read."""
    return {
        "url": release.url,
        "member": entry.name,
        "crc32": f"{entry.crc32:08x}",
        "read": read,
    }


def _discard(staged: Mapping[_SlotKey, Path], jobs: list[ReleaseJob]) -> None:
    for job in jobs:
        if job.key in staged:
            discard_staging(staged[job.key], job.slot)


def _stage(
    descriptor: SourceDescriptor,
    params: ReleaseFilesParams,
    release: DatasetRelease,
    jobs: list[ReleaseJob],
    session: requests.Session,
    sink: NoticeSink,
    progress: Callable[[ReleaseJob, str], None],
) -> tuple[dict[_SlotKey, Path], dict[_SlotKey, dict[str, Any]]]:
    """Read the members of ``jobs`` into staging by range requests; publish nothing.

    Returns the staged file and the ``extra.source`` of each job. A server that
    does not answer a range request with the range: ``_stage_archive``.
    """
    try:
        entries, length = read_directory(session, release.url, timeout=RANGE_TIMEOUT)
    except DownloadError as e:
        if e.reason != RANGE_UNSUPPORTED:
            raise
        return _stage_archive(
            descriptor, params, release, jobs, session, sink, progress, e
        )
    _check_length(params, release, length)
    found = {job.key: _entry(params, release, job, entries) for job in jobs}
    sink.emit(
        "warning",
        WHOLE_COUNTRY_SIZE,
        message(
            "releases.range_size",
            product=descriptor.product,
            country=descriptor.country,
            dataset=params.dataset,
            version=release.version,
            record=release.record,
            count=len(jobs),
            size_text=size_text(sum(entry.size for entry in found.values())),
            transfer=size_text(sum(entry.compressed_size for entry in found.values())),
            zip_size=size_text(release.size),
            url=release.url,
        ),
    )
    staged: dict[_SlotKey, Path] = {}
    try:
        for job in jobs:
            progress(job, "downloading")
            entry = found[job.key]
            path = staged[job.key] = new_staging(job.slot)
            digest = fetch_member(
                session, release.url, entry, path, timeout=TRANSFER_TIMEOUT
            )
            _check_digest(params, release, job, entry, digest)
    except DownloadError as e:
        _discard(staged, jobs)
        if e.reason != RANGE_UNSUPPORTED:
            raise
        return _stage_archive(
            descriptor, params, release, jobs, session, sink, progress, e
        )
    except BaseException:
        _discard(staged, jobs)
        raise
    return staged, {
        key: _source(release, entry, "range") for key, entry in found.items()
    }


def _stage_archive(
    descriptor: SourceDescriptor,
    params: ReleaseFilesParams,
    release: DatasetRelease,
    jobs: list[ReleaseJob],
    session: requests.Session,
    sink: NoticeSink,
    progress: Callable[[ReleaseJob, str], None],
    cause: DownloadError,
) -> tuple[dict[_SlotKey, Path], dict[_SlotKey, dict[str, Any]]]:
    """Download the whole ZIP, read the members of ``jobs`` from it, remove it."""
    sink.emit(
        "warning",
        WHOLE_ARCHIVE,
        message(
            "releases.whole_archive",
            product=descriptor.product,
            country=descriptor.country,
            url=release.url,
            error=ascii_text(reason(cause)),
            zip_size=size_text(release.size),
            count=len(jobs),
        ),
    )

    def whole(response: requests.Response) -> None:
        length = response.headers.get("Content-Length")
        coding = response.headers.get("Content-Encoding")
        if (
            isinstance(length, str)
            and length.isdigit()
            and coding in (None, "identity")
            and int(length) != release.size
        ):
            response.close()
            _check_length(params, release, int(length))

    first = jobs[0]
    scratch = new_staging(first.slot)
    archive = scratch.with_name(f"{first.slot.name}.zip")
    staged: dict[_SlotKey, Path] = {}
    entries: dict[_SlotKey, ZipEntry] = {}
    try:
        progress(first, "downloading")
        download_to(
            session,
            release.url,
            archive,
            timeout=TRANSFER_TIMEOUT,
            validate=whole,
            headers={"Accept-Encoding": "identity"},
        )
        _check_length(params, release, archive.stat().st_size)
        listed = local_directory(archive)
        for job in jobs:
            entry = entries[job.key] = _entry(params, release, job, listed)
            path = staged[job.key] = new_staging(job.slot)
            _check_digest(
                params, release, job, entry, extract_member(archive, entry, path)
            )
    except BaseException:
        _discard(staged, jobs)
        raise
    finally:
        discard_staging(archive, first.slot)
    return staged, {
        key: _source(release, entry, "archive") for key, entry in entries.items()
    }


# =============================================================================
# The newest release and the plan
# =============================================================================


def newer_release(
    params: ReleaseFilesParams,
    session: requests.Session,
    sink: NoticeSink,
    *,
    check: bool,
) -> None:
    """Report a release newer than every one the registry knows (``NEWER_RELEASE``).

    One request: the record of the concept DOI, which resolves to the newest
    release. A release the registry knows (read or refused) is no news. A failed
    request is a ``CHECK_FAILED`` warning in a plan (``check``) and a log record in
    a run; it never stops either.
    """
    try:
        response = get_with_retry(
            session,
            params.concept,
            timeout=RECORD_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        record = response.json()
        latest = str(record["id"])
        version = str(record["metadata"]["version"])
        published = str(record["metadata"]["publication_date"])
        doi = str(record["doi"])
    except (DownloadError, ValueError, KeyError, TypeError) as e:
        logger.debug("%s: the newest release not asked: %s", params.concept, e)
        if check:
            sink.emit(
                "warning",
                CHECK_FAILED,
                message(
                    "releases.concept_failed",
                    dataset=params.dataset,
                    concept_doi=params.concept_doi,
                    error=ascii_text(reason(e)),
                ),
            )
        return
    if latest in {release.record for release in params.releases}:
        return
    sink.emit(
        "info",
        NEWER_RELEASE,
        message(
            "releases.newer_release",
            dataset=params.dataset,
            version=ascii_text(version),
            record=ascii_text(latest),
            doi=ascii_text(doi),
            published=ascii_text(published),
            newest=supported_releases(params)[-1].version,
        ),
    )


def _item(job: ReleaseJob, release: DatasetRelease, track: Track) -> PlanItem:
    """Return the plan position of one file, without a request.

    In the store: ``current`` when a version has the bytes of the release, ``newer``
    when the slot holds other versions only, ``missing`` without a version; the
    available label is the version label of the release's bytes and the signal names
    the release and their SHA-256. In a plain write: the position of its target.
    """
    plain = plain_of(job.slot.root)
    if plain is not None:  # the position of a plain target: judged by `new_plan`
        return PlanItem(
            track=track,
            segment="",
            hierarchy="",
            name=job.slot.name,
            unit=job.unit,
            local_label=None,
            local_sha256=None,
            available_label=None,
            available_signal=None,
            status="missing",
            action="write",
            path=plain.target(job.slot.name),
        )
    lenient_store(job.slot.root)
    stored = _stored(job)
    local = stored or newest_version(
        list_versions(job.slot.versions_root, job.slot.name)
    )
    return PlanItem(
        track=track,
        segment=job.slot.segment,
        hierarchy=job.slot.hierarchy,
        name=job.slot.name,
        unit=job.unit,
        local_label=local.label if local is not None else None,
        local_sha256=local.sha256 if local is not None else None,
        available_label=job.label,
        available_signal={
            "version": release.version,
            "record": release.record,
            "sha256": job.member.sha256,
        },
        status="current" if stored else "newer" if local else "missing",
    )


def plan_release(
    root: Path,
    channel: AccessChannel,
    release: DatasetRelease,
    *,
    segment: str,
    ext: str,
    country: str,
    sink: NoticeSink,
    track: Track,
    session: requests.Session,
) -> UpdatePlan:
    """Return the update plan of the files of ``release`` (``--check``).

    The positions of ``_item`` - no transfer, the registry pins the bytes - and, in a
    plain write, the position of ``ATTRIBUTION.txt`` (``write``, ``replace`` when it
    lacks a line, ``conflict`` when it is no readable UTF-8 file). The record of the
    concept DOI is asked for a newer release (``newer_release``).
    """
    params = release_params(channel)
    jobs = release_jobs(
        root, params, release, segment=segment, ext=ext, country=country
    )
    items = [_item(job, release, track) for job in jobs]
    newer_release(params, session, sink, check=True)
    plan = new_plan(root, items)
    write = plain_of(root)
    if write is None:
        return plan
    entry = plan_attribution(write, release_lines(params, release))
    if entry is None:
        return plan
    attribution = PlanItem(
        track=track,
        segment="",
        hierarchy="",
        name=ATTRIBUTION_FILE,
        unit=ATTRIBUTION_FILE,
        local_label=None,
        local_sha256=None,
        available_label=None,
        available_signal=None,
        status="missing" if entry.action == "write" else "unverifiable",
        action=entry.action,
        path=entry.path,
        reason=entry.reason,
    )
    return replace(plan, items=(*plan.items, attribution))
