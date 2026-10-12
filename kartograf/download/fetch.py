"""
One policy for files without campaigns on the version store (spec 4.2).

LAZ tiles, CZ sheets, bbox cutouts (PL WCS, CZ) and the PL sheet flow
without campaigns share it: the newest local version, the check of the
channel's freshness signal (``index``/``metadata``/``http``/``none``), the
download into ``<segment>/versions/.incoming/`` (D19), ``commit_version`` and
the hardlink at the standard path. ``fetch_version`` downloads (modes
``None``/``"upgrade"``/``"force"``); ``inspect_version`` builds the update
plan position WITHOUT downloading (``--check-updates``).
"""

import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
from kartograf.sources.descriptor import SignalKind

logger = logging.getLogger(__name__)

# Download modes (spec 4.2); ``None`` = default: local versions, missing
# ones downloaded, newer content only reported (D5).
UpdateMode = Literal["check", "upgrade", "force"]
_UPDATE_MODES = (None, "upgrade", "force")

FileStatus = Literal["new", "unchanged", "relabeled", "local"]

# Download into the staged path; returns the HTTP signal of the response
# (``response_signal``) or ``None`` for a channel without one.
Fetch = Callable[[Path], dict | None]
# Current HTTP signal of the source file (``HEAD``); raises ``DownloadError``.
Probe = Callable[[], dict]
WriteSidecar = Callable[[Path, VersionRef, ContentDigest, dict | None], None]


def validate_update(update: object) -> None:
    """``update`` of the download functions: None, "upgrade" or "force".

    Raises
    ------
    ValidationError
        ``"check"`` (checking never downloads — the ``check_*`` functions
        build the plan) or an unknown mode.
    """
    if update == "check":
        raise ValidationError(
            "update='check' niczego nie pobiera — uzyj check_updates() albo "
            "check_*() danego toru (plan aktualizacji, kartograf-plan/1)"
        )
    if update not in _UPDATE_MODES:
        raise ValidationError(
            f"Nieznany tryb update={update!r} (dozwolone: None, 'upgrade', 'force')"
        )


@dataclass(frozen=True)
class FileSlot:
    """Where one file of a track lives in the store.

    ``std`` is the standard (link) path, ``versions_base`` the segment's
    ``versions/`` directory (staging ``.incoming/``), ``versions_root`` the
    hierarchy directory holding ``<label>_<sha8>/`` versions.
    """

    output_dir: Path
    std: Path
    versions_base: Path
    versions_root: Path
    ext: str

    @property
    def name(self) -> str:
        """File name of every version (= name of the standard path)."""
        return self.std.name

    @property
    def segment(self) -> str:
        """Segment relative to the output directory (plan position)."""
        return self.versions_base.parent.relative_to(self.output_dir).as_posix()

    @property
    def hierarchy(self) -> str:
        """Hierarchy below the segment (plan position)."""
        return self.versions_root.relative_to(self.versions_base).as_posix()


@dataclass(frozen=True)
class VersionedFile:
    """Outcome for one file of a track.

    ``status``: ``new`` (new version), ``unchanged`` (downloaded content
    equal to an existing version), ``relabeled`` (same content, new label,
    D23) or ``local`` (no download). ``newer``: default mode, the source
    signal differs from the local version (ETag or Last-Modified of the
    source). ``unverified``: the local version was used without a
    comparison — ``"none"`` (no cheap signal) or ``"check_failed: <error>"``.
    """

    path: Path
    status: FileStatus
    label: str
    sha256: str
    version_path: Path
    newer: str | None = None
    unverified: str | None = None


def link_version(std: Path, version: LocalVersion, *, refresh: bool) -> None:
    """``ensure_link`` of the standard path; ``OSError`` -> ``DownloadError``."""
    try:
        ensure_link(std, version.path, version_key(version), refresh=refresh)
    except OSError as e:
        raise DownloadError(f"dowiazanie {std}: {e}") from e


def local_version(slot: FileSlot) -> LocalVersion | None:
    """The newest valid local version of the slot (``None``: none)."""
    return newest_version(list_versions(slot.versions_root, slot.name))


def _prune_empty(start: Path, stop: Path) -> None:
    """Remove ``start`` and its parents while empty, never ``stop`` (a failed
    first download leaves no empty ``versions/.incoming`` tree)."""
    current = start
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _signal_label(signal: dict) -> str:
    return str(signal.get("etag") or signal.get("last_modified") or "?")


def _use_local(
    local: LocalVersion,
    update: UpdateMode | None,
    signal: SignalKind,
    probe: Probe | None,
) -> tuple[bool, str | None, str | None]:
    """``(keep_local, newer, unverified)`` for an existing local version."""
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
    if signal in ("none", "http"):  # http without a probe: no cheap signal
        return True, None, "none"
    return True, None, None  # index/metadata: the caller selected the file


def fetch_version(
    slot: FileSlot,
    update: UpdateMode | None,
    *,
    signal: SignalKind,
    fetch: Fetch,
    version: VersionRef,
    write_sidecar: WriteSidecar,
    probe: Probe | None = None,
    coverage: bool = False,
) -> VersionedFile:
    """Local version or download of one file (spec 4.2 table, plan 2/3 4).

    Without ``"force"`` an existing local version is used; with the
    ``http`` signal and a ``probe`` one ``HEAD`` compares it with the
    source: equal = local, different = local with ``newer`` (default) or a
    download (``"upgrade"``), not comparable = local, ``unverified="none"``;
    a probe failure is ``unverified="check_failed: ..."`` (default) or the
    ``DownloadError`` (``"upgrade"``). ``none`` (and ``http`` without a
    probe) = local with ``unverified="none"``; ``index``/``metadata`` =
    local (the caller already selected the file by its signal). A
    download goes into a private staging directory, becomes a version
    (``commit_version`` with the HTTP signal returned by ``fetch``) and the
    standard path is linked to it. A failure leaves no version and no
    staging directory.

    Raises
    ------
    ValidationError
        ``update="check"`` or an unknown mode.
    DownloadError
        Download, version or link failure; with ``"upgrade"`` also a failed
        probe.
    """
    validate_update(update)
    local = local_version(slot) if update != "force" else None
    if local is not None:
        keep, newer, unverified = _use_local(local, update, signal, probe)
        if keep:
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
    incoming = new_incoming_dir(slot.versions_base)
    staged = incoming / slot.name
    try:
        http = fetch(staged)
        digest = read_content(staged, ext=slot.ext, coverage=coverage)
        commit = commit_version(
            staged,
            slot.versions_root,
            slot.name,
            version,
            digest,
            lambda data, ref, dg: write_sidecar(data, ref, dg, http),
            signal=http,
        )
    except BaseException:
        shutil.rmtree(incoming, ignore_errors=True)
        _prune_empty(incoming.parent, slot.output_dir)
        raise
    shutil.rmtree(incoming, ignore_errors=True)
    committed = read_version(commit.path.parent, commit.path.name)
    if committed is None:
        raise DownloadError(f"{commit.path}: wersja bez czytelnego sidecara")
    link_version(slot.std, committed, refresh=commit.status != "unchanged")
    return VersionedFile(
        slot.std, commit.status, commit.label, commit.sha256, commit.path
    )


def inspect_version(
    slot: FileSlot,
    *,
    track: Track,
    unit: str,
    signal: SignalKind,
    probe: Probe | None = None,
    available: tuple[str | None, dict | None] = (None, None),
) -> PlanItem:
    """Plan position of one file WITHOUT downloading (``--check-updates``).

    ``missing`` without a local version; with a local version: ``http`` +
    ``probe`` -> ``current``/``newer`` (``unverifiable`` when the signals
    are not comparable), ``index``/``metadata`` -> ``current``,
    ``none`` -> ``unverifiable``. A failed probe = ``check_failed``.
    ``available`` = ``(label, signal)`` of the source known to the caller
    (e.g. the LAZ tile record); with ``http`` the signal is the probe's.
    """
    local = local_version(slot)
    label, remote = available
    status: ItemStatus
    error: str | None = None
    try:
        if signal == "http" and probe is not None:
            remote = probe()
    except DownloadError as e:
        status, error = "check_failed", str(e)
    else:
        if local is None:
            status = "missing"
        elif signal == "http" and probe is not None:
            same = same_http_signal(http_signal_of(local), remote)
            status = "unverifiable" if same is None else "current" if same else "newer"
        elif signal in ("index", "metadata"):
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
