"""
Versioned store core (spec 3, 3.1; D17-D23).

Every downloaded file lives as an immutable version in
``<segment>/versions/<hierarchy>/<label>_<sha8>/<name>`` next to its version
sidecar ``<name>.meta.json``. Versions are published exclusively: the data
file by ``os.link`` (never overwrites, D18) and the sidecar by the caller's
exclusive writer, so concurrent writers of the same content (also from other
hosts on a shared volume) end in one version directory without locks. The
staging directory ``.incoming/<host>_<pid>_<token>/`` lies on the same file
system; leftovers older than ``STALE_AFTER_S`` are removed (D19).
"""

import contextlib
import errno
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import socket
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from kartograf.download.campaigns import AscCoverage, measure_coverage
from kartograf.exceptions import DownloadError
from kartograf.sources.sidecar import file_digest

logger = logging.getLogger(__name__)

VERSIONS_DIR = "versions"
INCOMING_DIR = ".incoming"
STALE_AFTER_S = 24 * 3600

LabelSource = Literal["campaign", "edition", "downloaded"]
CommitStatus = Literal["new", "unchanged", "relabeled"]

_READ_CHUNK = 1_048_576
_VERSION_DIR = re.compile(r".+_([0-9a-f]{8})")
_LABEL_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# os.link failures meaning "this file system cannot hardlink" (D22).
_NO_HARDLINK = frozenset(
    code
    for code in (
        errno.EPERM,
        errno.EOPNOTSUPP,
        getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
        errno.EXDEV,
        errno.EMLINK,
    )
)

_warned: set[Path] = set()
_warned_lock = threading.Lock()


@dataclass(frozen=True)
class VersionRef:
    """Human label of a version and where it comes from (spec 3)."""

    label: str
    label_source: LabelSource

    def to_extra(self) -> dict:
        """``extra.version`` of the version sidecar."""
        return {"label": self.label, "label_source": self.label_source}

    @staticmethod
    def downloaded(now: datetime | None = None) -> "VersionRef":
        """Label of a source without a campaign or edition: UTC download date."""
        moment = (now or datetime.now(UTC)).astimezone(UTC)
        return VersionRef(moment.date().isoformat(), "downloaded")


@dataclass(frozen=True)
class ContentDigest:
    """Identity of a staged file from its single read (D20)."""

    sha256: str
    size_bytes: int
    coverage: float | None = None


@dataclass(frozen=True)
class LocalVersion:
    """A valid local version: data file plus a readable version sidecar."""

    path: Path
    label: str
    label_source: str
    sha256: str
    meta: dict


@dataclass(frozen=True)
class VersionCommit:
    """Outcome of ``commit_version``; ``path`` is the version data file."""

    status: CommitStatus
    path: Path
    sha256: str
    label: str


def read_content(path: Path, *, ext: str, coverage: bool) -> ContentDigest:
    """sha256, size and optionally the valid-cell share of a staged file.

    D20: one read. ASC coverage is counted from the same chunks that feed the
    hash. A GeoTIFF is hashed first and its mask read by ``rasterio`` right
    after (the bytes are in the page cache). A measurement failure is not a
    download failure (spec 6): ``coverage`` is ``None`` and a warning logged.
    """
    digest = hashlib.sha256()
    size = 0
    counter = AscCoverage(path.name) if coverage and ext == ".asc" else None
    with open(path, "rb") as stream:
        while chunk := stream.read(_READ_CHUNK):
            digest.update(chunk)
            size += len(chunk)
            if counter is not None:
                counter.feed(chunk)
    share: float | None = None
    if coverage:
        try:
            share = (
                counter.result() if counter is not None else measure_coverage(path, ext)
            )
        except DownloadError as e:
            logger.warning(f"Brak pomiaru pokrycia {path.name}: {e}")
    return ContentDigest(digest.hexdigest(), size, share)


def _host() -> str:
    return re.sub(r"[^A-Za-z0-9-]", "-", socket.gethostname()) or "host"


def new_incoming_dir(versions_root: Path) -> Path:
    """Private staging directory ``<versions_root>/.incoming/<host>_<pid>_<token>``."""
    path = (
        Path(versions_root)
        / INCOMING_DIR
        / f"{_host()}_{os.getpid()}_{secrets.token_hex(4)}"
    )
    path.mkdir(parents=True)
    return path


def _sidecar(data: Path) -> Path:
    return data.parent / f"{data.name}.meta.json"


def _warn_once(directory: Path, message: str) -> None:
    with _warned_lock:
        if directory in _warned:
            return
        _warned.add(directory)
    logger.warning(message)


def read_version(directory: Path, name: str) -> LocalVersion | None:
    """The version ``directory/name`` when valid (see ``list_versions``)."""
    match = _VERSION_DIR.fullmatch(directory.name)
    data = directory / name
    if match is None or not data.is_file():
        return None
    try:
        meta = json.loads(_sidecar(data).read_text(encoding="utf-8"))
        sha256 = meta["sha256"]
        version = meta["extra"]["version"]
        label, label_source = version["label"], version["label_source"]
    except (OSError, ValueError, KeyError, TypeError):
        _warn_once(
            directory,
            f"Pominieto wersje bez czytelnego sidecara: {directory} "
            "(naprawi ja nastepny zapis tej samej tresci)",
        )
        return None
    if not isinstance(sha256, str) or not sha256.startswith(match.group(1)):
        _warn_once(directory, f"Pominieto wersje o niezgodnym sha256: {directory}")
        return None
    return LocalVersion(data, str(label), str(label_source), sha256, meta)


def list_versions(versions_root: Path, name: str) -> list[LocalVersion]:
    """Valid versions of ``name`` in one hierarchy directory, by directory name.

    A directory is a version only with both the data file and a readable
    version sidecar whose sha256 matches the ``_<sha8>`` suffix; otherwise
    it is skipped (with one warning when it holds the data file).
    """
    root = Path(versions_root)
    try:
        entries = sorted(p for p in root.iterdir() if p.is_dir())
    except FileNotFoundError:
        return []
    found = []
    for directory in entries:
        if directory.name.startswith("."):
            continue
        version = read_version(directory, name)
        if version is not None:
            found.append(version)
    return found


def version_key(v: LocalVersion) -> tuple[str, str, str]:
    """Ordering of versions of one file ("newest").

    Campaign: ``(date, pzgik_date or "", source url)`` (ADR-028/030). Others:
    ``(date from the label or "", downloaded_at, sha256)``.
    """
    extra = v.meta.get("extra") or {}
    campaign = extra.get("campaign")
    if v.label_source == "campaign" and isinstance(campaign, dict):
        source = extra.get("source") or {}
        return (
            str(campaign.get("date") or ""),
            str(campaign.get("pzgik_date") or ""),
            str(source.get("url") or "") if isinstance(source, dict) else "",
        )
    date = _LABEL_DATE.match(v.label)
    return (
        date.group(0) if date else "",
        str(v.meta.get("downloaded_at") or ""),
        v.sha256,
    )


def newest_version(versions: Iterable[LocalVersion]) -> LocalVersion | None:
    """The newest version by ``version_key``; ``None`` for no versions.

    Equal keys (new content of the same campaign) — the later download wins.
    """
    return max(
        versions,
        key=lambda v: (version_key(v), str(v.meta.get("downloaded_at") or "")),
        default=None,
    )


def _newest_mtime(path: Path) -> float:
    newest = path.stat().st_mtime
    for child in path.rglob("*"):
        newest = max(newest, child.lstat().st_mtime)
    return newest


def _clean_incoming(incoming: Path, limit: float, keep: Path | None = None) -> None:
    try:
        entries = list(incoming.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry == keep:
            continue
        try:
            if _newest_mtime(entry) >= limit:
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        except OSError:
            continue  # another process may be cleaning in parallel


def cleanup_stale(versions_root: Path, *, now: float | None = None) -> None:
    """Remove leftovers older than ``STALE_AFTER_S`` (D19).

    Staging entries in ``<versions_root>/.incoming/`` and EMPTY version
    directories in ``versions_root``; younger entries may belong to a live
    process on another host and are never touched.
    """
    root = Path(versions_root)
    limit = (time.time() if now is None else now) - STALE_AFTER_S
    _clean_incoming(root / INCOMING_DIR, limit)
    try:
        entries = list(root.iterdir())
    except OSError:
        return
    for entry in entries:
        if entry.name.startswith(".") or _VERSION_DIR.fullmatch(entry.name) is None:
            continue
        try:
            empty = entry.is_dir() and not any(entry.iterdir())
            if empty and entry.stat().st_mtime < limit:
                entry.rmdir()
        except OSError:
            continue


def _discard(staged: Path) -> None:
    """Remove the staged file and its (now empty) private staging directory."""
    staged.unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        staged.parent.rmdir()


def _fsync(path: Path) -> None:
    flags = os.O_RDWR if os.name == "nt" else os.O_RDONLY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def commit_version(
    staged: Path,
    versions_root: Path,
    name: str,
    version: VersionRef,
    digest: ContentDigest,
    write_sidecar: Callable[[Path, VersionRef, ContentDigest], None],
) -> VersionCommit:
    """Publish a staged file as a version of ``name`` (spec 3.1).

    Same sha256 as a valid version: ``unchanged`` when the label matches or
    the label is ``downloaded`` (no signal); a new campaign/edition label
    gets its own directory hardlinked to the existing data, ``relabeled``
    (D23). Otherwise ``os.link`` publishes the data exclusively (D18); an
    existing target is compared by sha256: different = ``DownloadError``,
    equal with a sidecar = ``unchanged``, equal without = repair.

    ``write_sidecar(data, version, digest)`` must create ``<data>.meta.json``
    EXCLUSIVELY: ``FileExistsError`` means another writer published the
    sidecar first (``unchanged``); any other failure removes the data file
    created by this call and raises ``DownloadError``. The staged file is
    always removed.

    Raises
    ------
    DownloadError
        sha256 collision with an existing file, a file system without
        hardlinks (D22), or a failed sidecar.
    """
    root = Path(versions_root)
    limit = time.time() - STALE_AFTER_S
    cleanup_stale(root)
    if staged.parent.parent.name == INCOMING_DIR:
        _clean_incoming(staged.parent.parent, limit, keep=staged.parent)

    same = [v for v in list_versions(root, name) if v.sha256 == digest.sha256]
    source = staged
    status: CommitStatus = "new"
    if same:
        labelled = [v for v in same if v.label == version.label]
        if labelled or version.label_source == "downloaded":
            match = labelled[0] if labelled else max(same, key=version_key)
            _discard(staged)
            return VersionCommit("unchanged", match.path, digest.sha256, match.label)
        source, status = same[0].path, "relabeled"
    else:
        _fsync(staged)

    vdir = root / f"{version.label}_{digest.sha256[:8]}"
    target = vdir / name
    created = False
    try:
        vdir.mkdir(parents=True, exist_ok=True)
        os.link(source, target)
        created = True
    except FileExistsError:
        existing = file_digest(target)[0]
        if existing != digest.sha256:
            _discard(staged)
            raise DownloadError(
                f"{target}: plik wersji ma inne sha256 ({existing[:8]}) niz pobrany "
                f"({digest.sha256[:8]}) — kolizja albo uszkodzony plik"
            ) from None
        if _sidecar(target).exists():
            _discard(staged)
            return VersionCommit("unchanged", target, digest.sha256, version.label)
    except (OSError, NotImplementedError) as e:
        _discard(staged)
        with contextlib.suppress(OSError):
            vdir.rmdir()  # only when empty: created by this call
        if isinstance(e, NotImplementedError) or e.errno in _NO_HARDLINK:
            raise DownloadError(
                f"{target}: magazyn wersji wymaga systemu plikow z hardlinkami "
                f"(D22): {e}"
            ) from e
        raise DownloadError(f"{target}: nie udalo sie zapisac wersji: {e}") from e
    _discard(staged)

    try:
        write_sidecar(target, version, digest)
    except FileExistsError:
        return VersionCommit("unchanged", target, digest.sha256, version.label)
    except Exception as e:  # noqa: BLE001 — any failure invalidates the version
        if created:
            target.unlink(missing_ok=True)
            with contextlib.suppress(OSError):
                vdir.rmdir()
        if isinstance(e, DownloadError):
            raise
        raise DownloadError(
            f"{target}: nie udalo sie zapisac sidecara wersji: {e}"
        ) from e
    return VersionCommit(status, target, digest.sha256, version.label)
