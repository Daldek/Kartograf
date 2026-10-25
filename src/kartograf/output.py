"""
Plain output: ordinary files in a directory, without metadata (DEV §19, ADR-054).

Every plain write of Kartograf goes through the steps of this module, written once:

0. the write target is the directory ``output_dir`` (plain mode) or the store at
   ``root`` (store mode), never both, and the store at the default root when
   neither is given (`resolve_target`);
1. the target list is built before the first byte and checked as a whole
   (`plan_plain`): duplicate names are a ``conflict`` with the reason
   ``duplicate_output_name``, a directory that is or lies in a store one with
   ``output_in_store``, an existing target without ``force`` one with
   ``output_exists``; the error lists every offending path (`refuse`);
2. the files are written to a staging directory
   ``<dir>/.kartograf-incoming/<host>_<pid>_<token>/`` on the same file system, read
   once for their size and SHA-256 (`Staging.commit`) and moved into place with
   ``os.replace``; the staging directory is removed on success, on error, on SIGINT
   and on SIGTERM, and leftovers older than 24 hours are removed by the next run.

No sidecar, no hard link and no ``versions/`` directory: the output works on FAT,
exFAT and SMB. A store is recognised by its marker file name alone, so nothing is
imported from another tool (DEV-19.11, DEV-19.12; ``kartograf.marker``).
"""

import contextlib
import hashlib
import os
import secrets
import shutil
import socket
import threading
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Final, Literal

from kartograf.config import resolve_root
from kartograf.exceptions import ConflictError, ValidationError
from kartograf.interrupt import sigterm_interrupts
from kartograf.marker import STORE_MARKERS, store_around
from kartograf.messages import message

__all__ = [
    "STAGING",
    "FileResult",
    "Mode",
    "PlanEntry",
    "Staging",
    "Target",
    "digest_of",
    "plain_of",
    "plan_plain",
    "preflight",
    "refuse",
    "resolve_target",
    "store_only",
    "writing",
]

STAGING: Final = ".kartograf-incoming"
"""Name of the staging directory inside the output directory (DEV-19.7)."""
_STALE_SECONDS: Final = 24 * 60 * 60
_CHUNK: Final = 1 << 20

Mode = Literal["plain", "store"]
Action = Literal["write", "replace", "conflict"]
Reason = Literal["duplicate_output_name", "output_exists", "output_in_store"]
_REASONS: Final[tuple[Reason, ...]] = (
    "duplicate_output_name",
    "output_in_store",
    "output_exists",
)


@dataclass(frozen=True)
class FileResult:
    """
    One file a plain write put in place (DEV-19.19).

    Attributes
    ----------
    path : Path
        The target.
    size_bytes : int
        Size of the file in bytes.
    sha256 : str
        SHA-256 of the file, 64 lower-case hexadecimal digits.
    status : {"written", "replaced"}
        ``written`` for a new file, ``replaced`` for an existing one (with
        ``force``).
    """

    path: Path
    size_bytes: int
    sha256: str
    status: Literal["written", "replaced"]


@dataclass(frozen=True)
class PlanEntry:
    """
    One target of a plain write and what would happen to it (DEV-19.10).

    Attributes
    ----------
    path : Path
        The target.
    action : {"write", "replace", "conflict"}
        ``write`` for a new file, ``replace`` for an existing file with ``force``,
        ``conflict`` for a target that cannot be written.
    reason : {"duplicate_output_name", "output_exists", "output_in_store"} or None
        Why the target is a conflict; None for ``write`` and ``replace``.
    """

    path: Path
    action: Action
    reason: Reason | None = None


@dataclass(frozen=True)
class Target:
    """
    Where a writing command puts its data (DEV-19.1, DEV-19.2).

    Attributes
    ----------
    mode : {"plain", "store"}
        ``plain``: ordinary files in ``path`` (``output_dir``); ``store``: the
        versioned store at ``path`` (``root``).
    path : Path
        The output directory or the store root, as given (the default root is
        absolute).
    """

    mode: Mode
    path: Path


def resolve_target(
    *,
    output_dir: str | os.PathLike[str] | None = None,
    root: str | os.PathLike[str] | None = None,
) -> Target:
    """
    Choose between plain files and the store (DEV-19.1, DEV-19.2).

    Parameters
    ----------
    output_dir : str or os.PathLike or None, optional
        Directory of the plain files.
    root : str or os.PathLike or None, optional
        Root of the store.

    Returns
    -------
    Target
        The plain directory when ``output_dir`` is given, else the store at ``root``
        or, when neither is given, the store at the default root (``KARTOGRAF_ROOT``,
        ``[kartograf] root`` of ``nogat.toml`` or ``<data_dir>/kartograf``).

    Raises
    ------
    ValidationError
        Both are given (``details.reason`` is ``exclusive_options``,
        ``details.option`` is ``root`` and ``details.options`` lists the pair), or
        one of them is an empty string.
    """
    if output_dir is not None and root is not None:
        raise ValidationError(
            message("output.exclusive_options"),
            option="root",
            options=("output_dir", "root"),
            hint=message("output.exclusive_options_hint"),
            reason="exclusive_options",
        )
    if output_dir is not None:
        if not os.fspath(output_dir):
            raise ValidationError(
                message("output.empty_output_dir"), option="output_dir"
            )
        return Target("plain", Path(output_dir))
    return Target("store", resolve_root(root))


def plan_plain(
    directory: Path, relative: Sequence[str], *, force: bool
) -> list[PlanEntry]:
    """
    Check the full target list of a plain write without writing anything.

    Parameters
    ----------
    directory : pathlib.Path
        The output directory (it need not exist yet).
    relative : sequence of str
        POSIX sub-path of every target below ``directory`` (the file name in the
        store, below the sub-path of its source).
    force : bool
        Replace existing targets.

    Returns
    -------
    list of PlanEntry
        One entry per target in the given order: duplicates are conflicts (every
        occurrence), then targets of a directory that is or lies in a store, or that
        enter a subdirectory that holds a marker, then existing targets without
        ``force``; the rest is ``write`` or ``replace``. A store elsewhere below
        ``directory`` does not matter: nothing is written into it.
    """
    in_store = store_around(directory) is not None
    counts: dict[str, int] = {}
    for name in relative:
        counts[name] = counts.get(name, 0) + 1
    entries: list[PlanEntry] = []
    for name in relative:
        path = directory.joinpath(*name.split("/"))
        if counts[name] > 1:
            entries.append(PlanEntry(path, "conflict", "duplicate_output_name"))
        elif in_store or _holds_marker(directory, name):
            entries.append(PlanEntry(path, "conflict", "output_in_store"))
        elif path.exists():
            entries.append(
                PlanEntry(path, "replace")
                if force
                else PlanEntry(path, "conflict", "output_exists")
            )
        else:
            entries.append(PlanEntry(path, "write"))
    return entries


def _holds_marker(directory: Path, name: str) -> bool:
    """Say whether a directory the write would enter holds a store marker."""
    parent = directory
    for part in name.split("/")[:-1]:
        parent = parent / part
        if any((parent / marker).is_file() for marker in STORE_MARKERS):
            return True
    return False


def refuse(entries: Sequence[PlanEntry]) -> None:
    """
    Raise ``conflict`` when the plan lists a conflict (DEV-19.6, DEV-19.11).

    Parameters
    ----------
    entries : sequence of PlanEntry
        The plan of `plan_plain`.

    Raises
    ------
    ConflictError
        ``details.reason`` is the first reason in the order
        ``duplicate_output_name``, ``output_in_store``, ``output_exists``, and
        ``details.paths`` lists every path with a conflict of any reason.
    """
    conflicts = [entry for entry in entries if entry.action == "conflict"]
    if not conflicts:
        return
    first = next(
        reason
        for reason in _REASONS
        if any(entry.reason == reason for entry in conflicts)
    )
    paths = [str(entry.path) for entry in conflicts]
    messages = {
        "duplicate_output_name": (
            message("output.duplicate_output_name", count=len(paths), first=paths[0]),
            message("output.duplicate_output_name_hint"),
        ),
        "output_in_store": (
            message("output.output_in_store", count=len(paths), first=paths[0]),
            message("output.output_in_store_hint"),
        ),
        "output_exists": (
            message("output.output_exists", count=len(paths), first=paths[0]),
            message("output.output_exists_hint"),
        ),
    }
    summary, hint = messages[first]
    raise ConflictError(summary, reason=first, paths=paths, hint=hint)


def digest_of(path: Path) -> tuple[int, str]:
    """
    Read a file once, in chunks, for its size and SHA-256.

    Parameters
    ----------
    path : pathlib.Path
        An existing file.

    Returns
    -------
    tuple of (int, str)
        The size in bytes and the SHA-256 in lower-case hexadecimal digits.
    """
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _leftovers(staging: Path) -> None:
    """Remove staging directories of earlier runs that are over 24 hours old."""
    if not staging.is_dir():
        return
    cutoff = time.time() - _STALE_SECONDS
    for child in staging.iterdir():
        with contextlib.suppress(OSError):
            if (
                child.is_dir()
                and not child.is_symlink()
                and child.stat().st_mtime < cutoff
            ):
                shutil.rmtree(child, ignore_errors=True)


class Staging:
    """
    The plain write of one request: its staging directory and the root its tracks use.

    Used as a context manager: entering arms SIGTERM (in the main thread it
    interrupts the run like Ctrl-C, ``sigterm_interrupts``) and registers the handle
    root; nothing is created before the first transfer, so a request that fails its
    validation or its preflight leaves no directory behind. The first
    `stage_directory` creates ``<directory>/.kartograf-incoming/<host>_<pid>_<token>/``
    (the output directory too, when it is missing) and removes leftovers older than
    24 hours; leaving removes the staging directory, and the ``.kartograf-incoming``
    directory when it is empty, whatever ended the block (success, an error, SIGINT,
    SIGTERM). Threads of one run may stage and commit at the same time.

    The tracks take ``handle`` where they take a store root: a path inside the
    staging directory that no file ever reaches, by which `plain_of` recognises the
    write from any slot built on it, so a plain run reads nothing from and writes
    nothing to the store.

    Parameters
    ----------
    directory : pathlib.Path
        The output directory.
    force : bool, optional
        Replace a target that exists when the file is committed. Without it a target
        that appeared after the plan is a ``conflict`` and nothing is replaced.
    """

    def __init__(self, directory: Path, *, force: bool = False) -> None:
        """Name the staging directory of ``directory`` without creating it."""
        self.directory = directory
        self.force = force
        self.root = directory / STAGING
        self.path = (
            self.root / f"{socket.gethostname()}_{os.getpid()}_{secrets.token_hex(4)}"
        )
        self.handle = self.path / "root"
        self._opened = False
        self._counter = 0
        self._lock = threading.Lock()
        self._signals = contextlib.ExitStack()

    def __enter__(self) -> "Staging":
        """Arm the SIGTERM handler and register the handle root."""
        self._signals.enter_context(sigterm_interrupts())
        with _OPEN_LOCK:
            for key in _keys(self.handle):
                _OPEN[key] = self
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        """Remove the staging directory, forget the handle and restore SIGTERM."""
        with _OPEN_LOCK:
            for key in _keys(self.handle):
                _OPEN.pop(key, None)
        self._signals.close()
        if self._opened:
            shutil.rmtree(self.path, ignore_errors=True)
            with contextlib.suppress(OSError):
                self.root.rmdir()  # only when no other run is staging beside this one

    def _open(self) -> None:
        """Create the output and the staging directory at the first transfer."""
        with self._lock:
            if self._opened:
                return
            self.directory.mkdir(parents=True, exist_ok=True)
            _leftovers(self.root)
            self.path.mkdir(parents=True)
            self._opened = True

    def target(self, name: str) -> Path:
        """Return the path of the file ``name`` in the output directory."""
        return self.directory.joinpath(*name.split("/"))

    def plan(self, names: Sequence[str]) -> list[PlanEntry]:
        """Check the target list of this write (`plan_plain`) with its ``force``."""
        return plan_plain(self.directory, names, force=self.force)

    def stage_directory(self) -> Path:
        """
        Make a private directory for the files of one download.

        Returns
        -------
        pathlib.Path
            A new empty directory inside the staging directory.
        """
        self._open()
        with self._lock:
            self._counter += 1
            number = self._counter
        private = self.path / f"{number:06d}"
        private.mkdir()
        return private

    def stage_path(self, name: str) -> Path:
        """
        Name a private path where a download writes the file ``name``.

        Parameters
        ----------
        name : str
            The file name (its extension may steer the download); the file is created
            by the caller.

        Returns
        -------
        pathlib.Path
            ``<private directory>/<name>`` on the file system of the output directory.
        """
        return self.stage_directory() / name

    def commit(
        self,
        staged: Path,
        target: Path,
        *,
        size_bytes: int | None = None,
        sha256: str | None = None,
    ) -> FileResult:
        """
        Move a staged file into place with ``os.replace`` (DEV-19.9).

        Parameters
        ----------
        staged : pathlib.Path
            The file the download wrote.
        target : pathlib.Path
            The target; its directory is created when missing.
        size_bytes, sha256 : int and str, optional
            Size and SHA-256 when the caller has read the file already; both come
            from one chunked read of the file otherwise.

        Returns
        -------
        FileResult
            ``written`` for a new target, ``replaced`` for an existing one.

        Raises
        ------
        ConflictError
            ``output_exists``: the target exists, appeared after the plan, and the
            write is not forced. Nothing is replaced.
        """
        if size_bytes is None or sha256 is None:
            size_bytes, sha256 = digest_of(staged)
        replaced = target.exists()
        if replaced and not self.force:
            raise ConflictError(
                message("output.target_appeared", path=target),
                reason="output_exists",
                paths=[str(target)],
                hint=message("output.output_exists_hint"),
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged, target)
        return FileResult(
            target, size_bytes, sha256, "replaced" if replaced else "written"
        )

    def discard(self, staged: Path) -> None:
        """
        Remove the private directory of a download that failed.

        Parameters
        ----------
        staged : pathlib.Path
            A path made by `stage_path`, or any file in a directory of
            `stage_directory`; nothing else is removed.
        """
        if staged.parent.parent == self.path:
            shutil.rmtree(staged.parent, ignore_errors=True)


_OPEN: dict[Path, Staging] = {}
_OPEN_LOCK = threading.Lock()


def _keys(path: str | os.PathLike[str]) -> tuple[Path, Path]:
    """Return the absolute and the real path: a handle is found by either."""
    raw = os.fspath(path)
    return Path(os.path.abspath(raw)), Path(os.path.realpath(raw))


def plain_of(root: str | os.PathLike[str] | None) -> Staging | None:
    """
    Return the plain write whose handle root ``root`` is.

    Parameters
    ----------
    root : str or os.PathLike or None
        What a track takes as the store root.

    Returns
    -------
    Staging or None
        The open write when ``root`` is its handle (or lies below it); None for a
        store root.
    """
    if root is None or not _OPEN:
        return None
    with _OPEN_LOCK:
        for key in _keys(root):
            for handle, write in _OPEN.items():
                if key == handle or handle in key.parents:
                    return write
    return None


def preflight(root: str | os.PathLike[str], names: Iterable[str]) -> None:
    """
    Refuse a plain write whose target list conflicts, before its first byte.

    Parameters
    ----------
    root : str or os.PathLike
        What the track takes as the store root.
    names : iterable of str
        The file name of every target of the track (DEV-19.5).

    Raises
    ------
    ConflictError
        ``root`` is a plain write and the plan lists a conflict (`refuse`). Nothing
        happens for a store.
    """
    write = plain_of(root)
    if write is not None:
        refuse(write.plan(list(names)))


def store_only(option: str) -> ValidationError:
    """
    Build the error of an option that acts on versions, given with ``output_dir``.

    Parameters
    ----------
    option : str
        The CLI spelling of the option (``--upgrade``).

    Returns
    -------
    ValidationError
        ``details.reason`` is ``store_only_option``, ``details.option`` the option,
        and the hint names ``--root`` (DEV-19.17).
    """
    return ValidationError(
        message("output.store_only_option", option=option),
        option=option,
        hint=message("output.store_only_option_hint", option=option),
        reason="store_only_option",
    )


@contextlib.contextmanager
def writing(
    *,
    output_dir: str | os.PathLike[str] | None = None,
    root: str | os.PathLike[str] | None = None,
    update: str | None = None,
    plan: object | None = None,
    all_campaigns: bool = False,
    force: bool = False,
) -> Iterator[Path]:
    """
    Open the write of one request and give what its tracks take as the store root.

    Parameters
    ----------
    output_dir, root : str or os.PathLike or None, optional
        The target (`resolve_target`); ``root`` may also be the handle root of an
        enclosing plain write, which this block then joins.
    update : str or None, optional
        The update mode of the request: ``force`` lets a plain write replace
        existing files (DEV-19.9); ``upgrade`` acts on versions and is refused.
    plan : object or None, optional
        A saved update plan (``--plan``), refused in plain mode.
    all_campaigns : bool, optional
        Several flights of one sheet (``--all-campaigns``), refused in plain mode.
    force : bool, optional
        Replace existing files, as ``update="force"`` does (the plan of a check, which
        has no update mode).

    Yields
    ------
    pathlib.Path
        The store root (the default root when none is given), or the handle root of
        the plain write, which lives as long as the block.

    Raises
    ------
    ValidationError
        Both targets are given (`resolve_target`), or ``output_dir`` is given with
        ``update="upgrade"``, a ``plan`` or ``all_campaigns`` (`store_only`).
    """
    if root is not None and plain_of(root) is not None:
        yield Path(root)
        return
    target = resolve_target(output_dir=output_dir, root=root)
    if target.mode == "store":
        yield target.path
        return
    if update == "upgrade":
        raise store_only("--upgrade")
    if plan is not None:
        raise store_only("--plan")
    if all_campaigns:
        raise store_only("--all-campaigns")
    with Staging(target.path, force=force or update == "force") as write:
        yield write.handle
