"""
One policy for files without campaigns on the version store (spec 4.2).

LAZ tiles, CZ sheets, bbox cutouts (PL WCS, CZ), the PL sheet flow without
campaigns, land cover and HSG share it: the newest local version, the check
of the channel's freshness signal (``index``/``metadata``/``http``/``none``),
the download into ``<segment>/versions/.incoming/`` (D19), ``commit_version``
and the hardlink at the standard path. ``fetch_version`` downloads (modes
``None``/``"upgrade"``/``"force"``) as ``use_local`` (decision without
downloading data) + download + ``store_file`` (the staged file becomes a
version); callers storing several files of one download use the two parts
directly. ``inspect_version`` builds the update plan position WITHOUT
downloading (``--check-updates``).
"""

import functools
import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from kartograf.download.links import ensure_link
from kartograf.download.plan import ItemStatus, PlanItem, Track
from kartograf.download.versions import (
    ContentDigest,
    LocalVersion,
    VersionRef,
    commit_version,
    http_signal_of,
    list_versions,
    new_incoming_dir,
    newest_version,
    read_content,
    read_version,
    same_http_signal,
    version_key,
)
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import CHECK_FAILED, UNVERIFIED_LOCAL, NoticeSink
from kartograf.sources.descriptor import SignalKind
from kartograf.sources.edition import Edition

logger = logging.getLogger(__name__)

# Download modes (spec 4.2); ``None`` = default: local versions, missing
# ones downloaded, newer content only reported (D5).
UpdateMode = Literal["check", "upgrade", "force"]
_UPDATE_VALUES = ("upgrade", "force")  # the modes a caller names
_UPDATE_MODES = (None, *_UPDATE_VALUES)

FileStatus = Literal["new", "unchanged", "relabeled", "local", "reused"]

# Download into the staged path; returns the HTTP signal of the response
# (``response_signal``) or ``None`` for a channel without one.
Fetch = Callable[[Path], dict[str, Any] | None]
# Current HTTP signal of the source file (``HEAD``); raises ``DownloadError``.
Probe = Callable[[], dict[str, Any]]
# Current edition of the source (signal ``metadata``, D29/D30); raises
# ``DownloadError``. Memoized by the caller: one request per job (spec 4.1).
EditionLookup = Callable[[], Edition]
WriteSidecar = Callable[[Path, VersionRef, ContentDigest, dict[str, Any] | None], None]


def validate_update(update: object, *, check: str | None = None) -> None:
    """``update`` of the download functions: None, "upgrade" or "force".

    ``check``: name of the matching plan function of the caller's track
    (e.g. ``"check_landcover"``), named in the message of ``"check"``;
    public download functions pass it, internal steps reached after them
    leave the generic text.

    Raises
    ------
    ValidationError
        ``"check"`` (checking never downloads — the ``check_*`` functions
        build the plan) or an unknown mode.
    """
    if update == "check":
        hint = f"{check}()" if check else "check_*() danego toru"
        raise ValidationError(
            f"update='check' niczego nie pobiera - uzyj {hint} "
            "(plan aktualizacji, kartograf-plan/1)",
            option="update",
            allowed=_UPDATE_VALUES,
        )
    if update not in _UPDATE_MODES:
        raise ValidationError(
            f"Nieznany tryb update={update!r} (dozwolone: None, 'upgrade', 'force')",
            option="update",
            allowed=_UPDATE_VALUES,
        )


def refreshes_cache(update: UpdateMode | None) -> bool:
    """Return whether a download mode refreshes the metadata cache, not reads it.

    ``"upgrade"`` and ``"force"`` ask the source like ``--check-updates`` (a flight
    published within the cache TTL is seen); the default mode reads it (TTL 7 days).
    """
    return update in ("upgrade", "force")


@dataclass(frozen=True)
class FileSlot:
    """Where one file of a track lives in the store.

    ``std`` is the standard (link) path, ``versions_base`` the segment's
    ``versions/`` directory (staging ``.incoming/``), ``versions_root`` the
    hierarchy directory holding ``<label>_<sha8>/`` versions.
    ``related_roots``: hierarchy directories of related slots (other
    editions of the same product, format and unit, ADR-042 D7) - content
    already stored there becomes a ``relabeled`` hardlink, not a copy.
    """

    root: Path
    std: Path
    versions_base: Path
    versions_root: Path
    ext: str
    related_roots: tuple[Path, ...] = ()

    @property
    def name(self) -> str:
        """File name of every version (= name of the standard path)."""
        return self.std.name

    @property
    def segment(self) -> str:
        """Segment relative to the output directory (plan position)."""
        return self.versions_base.parent.relative_to(self.root).as_posix()

    @property
    def hierarchy(self) -> str:
        """Hierarchy below the segment (plan position)."""
        return self.versions_root.relative_to(self.versions_base).as_posix()


@dataclass(frozen=True)
class VersionedFile:
    """Outcome for one file of a track.

    ``status``: ``new`` (new version), ``unchanged`` (downloaded content
    equal to an existing version), ``relabeled`` (same content, new label,
    D23), ``local`` (no download) or ``reused`` (a derived file whose inputs
    match an existing version, nothing computed, D33). ``newer``: the
    source signal differs from the local version (ETag or Last-Modified of
    the source, or the newer edition; the default mode knows it only from
    an index record asked for the selection). ``unverified``: the local
    version was used without a comparison — ``"unchecked"`` (the default
    mode asks no source for the freshness of a local version: ADR-036
    erratum 3, ``--check-updates``/``--upgrade`` compare it), ``"none"`` (no
    cheap or comparable signal) or ``"check_failed: <error>"``. ``same_as``: for
    ``relabeled``, the label of the newest existing version with identical
    content; otherwise ``None``.
    """

    path: Path
    status: FileStatus
    label: str
    sha256: str
    version_path: Path
    newer: str | None = None
    unverified: str | None = None
    same_as: str | None = None


def link_version(std: Path, version: LocalVersion, *, refresh: bool) -> None:
    """``ensure_link`` of the standard path; ``OSError`` -> ``DownloadError``."""
    try:
        ensure_link(std, version.path, version_key(version), refresh=refresh)
    except OSError as e:
        raise DownloadError(f"dowiazanie {std}: {e}") from e


def local_version(slot: FileSlot) -> LocalVersion | None:
    """Return the newest valid local version of the slot (``None``: none)."""
    return newest_version(list_versions(slot.versions_root, slot.name))


def _prune_empty(start: Path, stop: Path) -> None:
    """Remove ``start`` and its parents while empty, never ``stop``.

    A failed first download leaves no empty ``versions/.incoming`` tree.
    """
    current = start
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def new_staging(slot: FileSlot) -> Path:
    """Private staging path of one download of the slot (D19)."""
    return new_incoming_dir(slot.versions_base) / slot.name


def discard_staging(staged: Path, slot: FileSlot) -> None:
    """Remove a staging directory and the empty ``.incoming`` tree above it."""
    shutil.rmtree(staged.parent, ignore_errors=True)
    _prune_empty(staged.parent.parent, slot.root)


def _signal_label(signal: dict[str, Any]) -> str:
    return str(signal.get("etag") or signal.get("last_modified") or "?")


def _check_label_args(
    signal: SignalKind, version: VersionRef | None, edition: EditionLookup | None
) -> None:
    """Check the label arguments against the freshness signal.

    ``metadata``: the edition labels the version; ``index``: ``version`` (the caller
    selected the file by its record, LAZ) or ``edition`` (the label of the unit's
    index record, compared like an edition, ADR-043); other signals: ``version``.
    """
    if signal == "metadata":
        if edition is None or version is not None:
            raise ValidationError(
                "sygnal metadata: wersje etykietuje wydanie (edition=, bez version=)"
            )
    elif signal == "index":
        if (version is None) == (edition is None):
            raise ValidationError(
                "sygnal index: version= albo edition= (etykieta rekordu indeksu)"
            )
    elif version is None or edition is not None:
        raise ValidationError(
            f"sygnal {signal}: wymagane version=, edition= tylko dla metadata i index"
        )


def _keep_local(
    local: LocalVersion,
    update: UpdateMode | None,
    signal: SignalKind,
    probe: Probe | None,
    edition: EditionLookup | None,
) -> tuple[bool, str | None, str | None]:
    """``(keep_local, newer, unverified)`` for an existing local version.

    The default mode asks no source (no ``HEAD``, no edition lookup) and
    keeps the local version ``"unchecked"`` (ADR-036 erratum 3); the label
    of an index record (signal ``index``) was already asked for the
    selection and is still compared.
    """
    if update is None and (
        (signal == "http" and probe is not None)
        or (signal == "metadata" and edition is not None)
    ):
        return True, None, "unchecked"
    if signal == "http" and probe is not None:
        try:
            remote = probe()
        except DownloadError as e:
            if update == "upgrade":
                raise
            return True, None, f"check_failed: {e}"
        same = same_http_signal(http_signal_of(local), remote)
        if same is None:
            return True, None, "none"
        if same:
            return True, None, None
        if update == "upgrade":
            return False, None, None
        return True, _signal_label(remote), None
    if signal in ("metadata", "index") and edition is not None:
        if local.label_source != "edition":
            return True, None, "none"  # not from an edition: not comparable
        try:
            current = edition().id
        except DownloadError as e:
            if update == "upgrade":
                raise
            return True, None, f"check_failed: {e}"
        if local.label == current:
            return True, None, None
        if update == "upgrade":
            return False, None, None
        return True, current, None
    if signal in ("none", "http"):  # http without a probe: no cheap signal
        return True, None, "none"
    return True, None, None  # index without a record label: the caller selected


def use_local(
    slot: FileSlot,
    update: UpdateMode | None,
    *,
    signal: SignalKind,
    probe: Probe | None = None,
    edition: EditionLookup | None = None,
) -> VersionedFile | None:
    """Return the local version to use, or ``None`` when the file must be downloaded.

    Spec 4.2 table (plan 2/3 4, plan 3/3 decision 2). Without ``"force"``
    an existing local version is used. The default mode asks no source for
    it: ``http`` + ``probe`` and ``metadata`` + ``edition`` give
    ``unverified="unchecked"`` without a request (ADR-036 erratum 3).
    ``"upgrade"``: ``http`` + ``probe``: one ``HEAD`` compares it with the
    source — equal = local, different = a download, not comparable =
    ``unverified="none"``, a probe failure = the ``DownloadError``.
    ``metadata`` + ``edition``: a version labelled by an edition is compared
    with the current edition the same way; a version with another label
    source is not comparable. ``index`` + ``edition`` (the label of the
    unit's index record, ADR-043, known without a request) is compared in
    every mode: different = local with ``newer`` (default) or a download
    (``"upgrade"``). ``none`` (and ``http`` without a probe) = local with
    ``unverified="none"``; ``index`` without an edition = local (the caller
    selected the file by its record). A used local version gets the
    standard path linked.

    Raises
    ------
    ValidationError
        ``update="check"`` or an unknown mode.
    DownloadError
        Link failure; with ``"upgrade"`` also a failed probe or edition.
    """
    validate_update(update)
    local = local_version(slot) if update != "force" else None
    if local is None:
        return None
    keep, newer, unverified = _keep_local(local, update, signal, probe, edition)
    if not keep:
        return None
    link_version(slot.std, local, refresh=False)
    return VersionedFile(
        slot.std,
        "local",
        local.label,
        local.sha256,
        local.path,
        newer=newer,
        unverified=unverified,
    )


def emit_file_notices(
    sink: NoticeSink,
    unit: str,
    file: VersionedFile,
    update: UpdateMode | None,
    *,
    check_failure: bool = True,
    unverified_local: bool = True,
) -> None:
    """Notices of one store file of a request result (one text for every track).

    ``CHECK_FAILED`` (warning): the local version was used because the
    source check failed (skipped with ``check_failure=False`` when the
    caller already reported it); ``UNVERIFIED_LOCAL`` (info): ``"upgrade"``
    kept a local version of a source without a cheap signal (skipped with
    ``unverified_local=False`` when the track already reported the file,
    e.g. a CZ sheet file whose local version has no HTTP signal).
    """
    unverified = file.unverified or ""
    if unverified.startswith("check_failed") and check_failure:
        error = unverified.split(":", 1)[1].strip()
        sink.emit(
            "warning",
            CHECK_FAILED,
            f"{unit}: nie udalo sie sprawdzic zrodla ({error}) - uzyto "
            f"lokalnej wersji {file.label}",
        )
    if (
        unverified_local
        and file.status == "local"
        and unverified == "none"
        and update == "upgrade"
    ):
        sink.emit(
            "info",
            UNVERIFIED_LOCAL,
            f"{unit}: lokalna wersja {file.label} niesprawdzona - zrodlo "
            "bez taniego sygnalu; pobierz ponownie: --force",
        )


def store_file(
    slot: FileSlot,
    staged: Path,
    *,
    version: VersionRef,
    write_sidecar: WriteSidecar,
    http: dict[str, Any] | None,
    signal: SignalKind,
    coverage: bool = False,
) -> VersionedFile:
    """Return the staged file (``new_staging``) as a version of the slot, linked.

    sha256 from one read (D20), ``commit_version`` and the hardlink of the
    standard path. ``http`` (headers of the download) is passed to
    ``write_sidecar`` (``extra.http``) and, ONLY for the ``http`` channel,
    to ``commit_version`` as the D23 signal — headers of a channel without
    a freshness signal never turn equal content into ``relabeled``. The
    staging directory is always removed; a failure leaves no version.

    Raises
    ------
    DownloadError
        Version, sidecar or link failure.
    """
    try:
        digest = read_content(staged, ext=slot.ext, coverage=coverage)
        commit = commit_version(
            staged,
            slot.versions_root,
            slot.name,
            version,
            digest,
            lambda data, ref, dg: write_sidecar(data, ref, dg, http),
            signal=http if signal == "http" else None,
            related_roots=slot.related_roots,
        )
    except BaseException:
        discard_staging(staged, slot)
        raise
    shutil.rmtree(staged.parent, ignore_errors=True)
    committed = read_version(commit.path.parent, commit.path.name)
    if committed is None:
        raise DownloadError(f"{commit.path}: wersja bez czytelnego sidecara")
    link_version(slot.std, committed, refresh=commit.status != "unchanged")
    return VersionedFile(
        slot.std,
        commit.status,
        commit.label,
        commit.sha256,
        commit.path,
        same_as=commit.same_as,
    )


def memoized_edition(edition: EditionLookup) -> EditionLookup:
    """``edition`` asked at most once (a failure is asked again)."""
    return functools.cache(edition)


def fetch_version(
    slot: FileSlot,
    update: UpdateMode | None,
    *,
    signal: SignalKind,
    fetch: Fetch,
    write_sidecar: WriteSidecar,
    version: VersionRef | None = None,
    probe: Probe | None = None,
    edition: EditionLookup | None = None,
    coverage: bool = False,
) -> VersionedFile:
    """Local version or download of one file: ``use_local`` + ``store_file``.

    ``signal="metadata"`` requires ``edition`` (the version label is
    ``VersionRef(edition().id, "edition")``, asked BEFORE the download: no
    version without an edition, D30); ``signal="index"`` takes ``version``
    or ``edition`` (the label of the unit's index record, labelled the same
    way, ADR-043); other signals require ``version``.
    A download goes into a private staging directory and becomes a version;
    a failure leaves no version and no staging directory.

    Raises
    ------
    ValidationError
        ``update="check"``, an unknown mode or a wrong ``version``/``edition``
        pair.
    DownloadError
        Download, edition, version or link failure; with ``"upgrade"`` also
        a failed probe or edition check.
    """
    validate_update(update)
    _check_label_args(signal, version, edition)
    lookup = memoized_edition(edition) if edition is not None else None
    local = use_local(slot, update, signal=signal, probe=probe, edition=lookup)
    if local is not None:
        return local
    if version is None:
        assert lookup is not None  # _check_label_args
        version = VersionRef(lookup().id, "edition")
    staged = new_staging(slot)
    try:
        http = fetch(staged)
    except BaseException:
        discard_staging(staged, slot)
        raise
    return store_file(
        slot,
        staged,
        version=version,
        write_sidecar=write_sidecar,
        http=http,
        signal=signal,
        coverage=coverage,
    )


def inspect_version(
    slot: FileSlot,
    *,
    track: Track,
    unit: str,
    signal: SignalKind,
    probe: Probe | None = None,
    edition: EditionLookup | None = None,
    available: tuple[str | None, dict[str, Any] | None] = (None, None),
) -> PlanItem:
    """Plan position of one file WITHOUT downloading (``--check-updates``).

    ``missing`` without a local version; with a local version: ``http`` +
    ``probe`` -> ``current``/``newer`` (``unverifiable`` when the signals
    are not comparable), ``metadata`` -> ``current``/``newer`` by the
    edition (``unverifiable`` for a version not labelled by an edition),
    ``index`` + ``edition`` (the label of the unit's index record,
    ADR-043) -> the same comparison, ``index`` without an edition ->
    ``current`` (the caller selected the file by its record), ``none`` ->
    ``unverifiable``. A failed probe or edition = ``check_failed``.
    ``available`` = ``(label, signal)`` of the source known to the caller
    (e.g. the LAZ tile record, the fields of an index record); with ``http``
    the signal is the probe's, with ``metadata`` ``(edition id, {"edition":
    id})``; with ``index`` + ``edition`` the label is the edition id.

    Raises
    ------
    ValidationError
        ``signal="metadata"`` without ``edition``.
    """
    if signal == "metadata" and edition is None:
        raise ValidationError("sygnal metadata: wymagane edition=")
    local = local_version(slot)
    label, remote = available
    status: ItemStatus
    error: str | None = None
    try:
        if signal == "http" and probe is not None:
            remote = probe()
        elif signal == "metadata" and edition is not None:
            label = edition().id
            remote = {"edition": label}
        elif signal == "index" and edition is not None:
            label = edition().id
            remote = remote if remote is not None else {"edition": label}
    except DownloadError as e:
        status, error = "check_failed", str(e)
    else:
        if local is None:
            status = "missing"
        elif signal == "http" and probe is not None:
            same = same_http_signal(http_signal_of(local), remote)
            status = "unverifiable" if same is None else "current" if same else "newer"
        elif signal == "metadata" or (signal == "index" and edition is not None):
            if local.label_source != "edition":
                status = "unverifiable"
            else:
                status = "current" if local.label == label else "newer"
        elif signal == "index":
            status = "current"
        else:
            status = "unverifiable"
    return PlanItem(
        track=track,
        segment=slot.segment,
        hierarchy=slot.hierarchy,
        name=slot.name,
        unit=unit,
        local_label=local.label if local is not None else None,
        local_sha256=local.sha256 if local is not None else None,
        available_label=label,
        available_signal=remote,
        status=status,
        error=error,
    )
