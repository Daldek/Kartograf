"""
The marker of a store, ``kartograf-store.json`` (DEV-19.12 to DEV-19.14, ADR-054).

A versioned store of Kartograf is a root directory with the marker
``kartograf-store.json`` (schema ``kartograf-store/1``: ``schema``, ``tool``,
``created_at``, ``producer_version``). Every Nogat tool with a store has one, and a
tool recognises the store of another by the marker's file name alone, so nothing is
imported between the tools (``STORE_MARKERS``).

- ``prepare_store`` is called by every write into the store: a missing root or one
  without files gets its marker, a root that has the layout of a store (files in the
  product trees ``nmt/``, ``laz/``..., of this version or of 0.7.x) and no marker is
  ``store_unavailable`` (``no_marker``), a root that holds other files is ``conflict``
  (``not_empty``);
- ``lenient_store`` makes the same checks for a plan or a read and creates nothing;
- ``store_state`` is the same judgement, read only, for a consumer that reads a store:
  ``marked``, ``layout``, ``new`` or ``foreign``, and the refusals that every check
  raises (a nested store, a marker that is not ``kartograf-store/1``);
- ``init_store`` is ``kartograf store init``: it verifies the layout of a root that has
  one and no marker, then writes the marker; ``check_store`` is ``store init --check``,
  the plan of that write;
- a store never nests in another store, whichever tool wrote it: the ancestors of the
  root, the root itself (the marker of the other tool) and what lies below it are
  looked at (``conflict``, ``nested_store``).

``store_around`` and ``store_below`` find a marker around and below a directory; the
plain output uses them to refuse a directory that is or lies in a store.
"""

import functools
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from kartograf import _clock
from kartograf._version import build_version
from kartograf.exceptions import (
    ConflictError,
    InvalidLayoutError,
    StoreUnavailableError,
    ValidationError,
)
from kartograf.messages import message
from kartograf.serialization import Document

if TYPE_CHECKING:
    from kartograf.download.plan import UpdatePlan

__all__ = [
    "MARKER",
    "MARKER_SCHEMA",
    "STORE_MARKERS",
    "StoreInit",
    "StoreState",
    "check_store",
    "has_layout",
    "init_store",
    "lenient_store",
    "managed_trees",
    "prepare_store",
    "store_around",
    "store_below",
    "store_refusal",
    "store_state",
]

MARKER: Final = "kartograf-store.json"
"""File name of the marker of a Kartograf store."""
MARKER_SCHEMA: Final = "kartograf-store/1"
TOOL: Final = "kartograf"
STORE_MARKERS: Final[tuple[str, ...]] = (MARKER, "imgw-store.json")
"""File names that mark the root of a store of any Nogat tool (DEV-19.12)."""
MAX_PROBLEMS: Final = 20
INCOMING: Final = ".incoming"  # the staging directory of a version

StoreState = Literal["marked", "layout", "new", "foreign"]
"""What a directory is to a write into the store (``store_state``)."""


@dataclass(frozen=True)
class StoreInit(Document):
    """The marker of a store (``kartograf-store-init/1``): the result of ``store init``.

    Attributes
    ----------
    root : Path
        The store root (absolute in JSON).
    marker : Path
        The marker file, ``<root>/kartograf-store.json``.
    created : bool
        ``True`` when the marker was written now, ``False`` when the store had it.
    tool : str
        ``kartograf``.
    created_at : str
        When the marker was written (UTC, ISO 8601 with offset).
    producer_version : str
        The version of Kartograf that wrote the marker.
    """

    SCHEMA = "kartograf-store-init/1"

    root: Path
    marker: Path
    created: bool
    tool: str
    created_at: str
    producer_version: str


@functools.cache
def managed_trees() -> frozenset[str]:
    """Return the top directories Kartograf writes: its products and ``hsg``.

    The product trees of a store are not looked into for a nested store: they are
    this store's own.
    """
    from kartograf.sources.registry import all_sources

    tops = {source.storage_subdir.split("/", 1)[0] for source in all_sources()}
    return frozenset({*tops, "hsg"})


def store_around(path: Path) -> Path | None:
    """
    Find the store that is ``path`` or contains it.

    Parameters
    ----------
    path : pathlib.Path
        A file or directory, existing or not.

    Returns
    -------
    pathlib.Path or None
        The nearest directory (``path`` itself included) that holds a store marker of
        any tool, or None.
    """
    resolved = path.resolve()
    return next(
        (
            candidate
            for candidate in (resolved, *resolved.parents)
            if any((candidate / name).is_file() for name in STORE_MARKERS)
        ),
        None,
    )


def store_below(path: Path, *, skip: frozenset[str] = frozenset()) -> Path | None:
    """
    Find a store marker below ``path`` (a nested store).

    Parameters
    ----------
    path : pathlib.Path
        Directory to search; symbolic links are not followed.
    skip : frozenset of str, optional
        Names of the directories directly under ``path`` that are not entered (the
        product trees of the store at ``path``).

    Returns
    -------
    pathlib.Path or None
        The first directory below ``path`` that holds a store marker, or None.
    """
    if not path.is_dir():
        return None
    for base, dirs, files in os.walk(path, followlinks=False):
        folder = Path(base)
        if folder != path and any(name in files for name in STORE_MARKERS):
            return folder
        dirs[:] = [
            name
            for name in dirs
            if not (folder / name).is_symlink()
            and not (folder == path and name in skip)
        ]
    return None


def _has_files(path: Path) -> bool:
    """Say whether a directory tree holds a file; staging directories do not count."""
    for _, dirs, files in os.walk(path, followlinks=False):
        if files:
            return True
        dirs[:] = [name for name in dirs if name != INCOMING]
    return False


def _contents(path: Path) -> tuple[bool, bool]:
    """Say what a directory without a marker holds: ``(store files, other files)``.

    Store files are files in a product tree of Kartograf (``nmt/``, ``laz/``,
    ``hsg/``...), outside the staging directories ``.incoming``: the layout of a
    store, of this version or of 0.7.x (plain files, ``kampanie/``). Anything else
    that is a file, a link or a directory with a file in it is other content. An
    empty directory tree and the temporary file of a competing writer are neither: a
    writer makes the directories of its first file before it asks for the marker.
    """
    trees = managed_trees()
    store = other = False
    try:
        entries = list(os.scandir(path))
    except OSError:
        return False, False
    for entry in entries:
        if entry.name.startswith(f".{MARKER}."):
            continue
        if not entry.is_dir(follow_symlinks=False):
            other = True
        elif entry.name in trees:
            store = store or _has_files(Path(entry.path))
        else:
            other = other or _has_files(Path(entry.path))
    return store, other


def has_layout(root: Path) -> bool:
    """Say whether ``root`` has the layout of a store, with or without a marker.

    The layout is files in the product trees of Kartograf (``nmt/``, ``laz/``,
    ``hsg/``...): versions, the standard files of 0.8.0 and the plain files and
    ``kampanie/`` of 0.7.x.
    """
    return root.is_dir() and _contents(root)[0]


def _check_nested(path: Path, *, below: bool) -> None:
    """Refuse a root that lies in, is, or contains the store of any tool.

    Raises
    ------
    ConflictError
        ``nested_store``: an ancestor holds a marker, the root holds the marker of
        another tool, or (with ``below``) a store lies below the root, outside the
        product trees of this one.
    """
    for ancestor in path.parents:
        for name in STORE_MARKERS:
            if (ancestor / name).is_file():
                raise ConflictError(
                    message(
                        "marker.inside_a_store",
                        path=path,
                        ancestor=ancestor,
                        marker=name,
                    ),
                    reason="nested_store",
                    path=path,
                )
    foreign = next(
        (name for name in STORE_MARKERS if name != MARKER and (path / name).is_file()),
        None,
    )
    if foreign is not None:
        raise ConflictError(
            message("marker.holds_another_store", path=path, marker=foreign),
            reason="nested_store",
            path=path,
        )
    if not below:
        return
    skip = managed_trees() if (path / MARKER).is_file() else frozenset()
    found = store_below(path, skip=skip)
    if found is not None:
        marker = next(name for name in STORE_MARKERS if (found / name).is_file())
        raise ConflictError(
            message("marker.store_below", path=path, folder=found, marker=marker),
            reason="nested_store",
            path=path,
        )


def _absolute(root: str | os.PathLike[str]) -> Path:
    """Return ``root`` as an absolute path of the real location (links resolved)."""
    return Path(root).expanduser().resolve()


def _read_marker(path: Path) -> dict[str, str]:
    """Return the fields of the marker of the store at ``path``.

    Raises
    ------
    InvalidLayoutError
        The marker is not a JSON object of the schema ``kartograf-store/1``.
    OSError
        The marker cannot be read: that says nothing of its schema.
    """
    marker = path / MARKER
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
    except ValueError:  # not JSON, or not UTF-8
        document = None
    if not isinstance(document, dict) or document.get("schema") != MARKER_SCHEMA:
        raise InvalidLayoutError(
            message("marker.not_a_marker", path=marker, schema=MARKER_SCHEMA),
            path=path,
            problems=[
                message("marker.not_a_marker", path=marker, schema=MARKER_SCHEMA)
            ],
        )
    return {key: str(value) for key, value in document.items()}


def _unmarked(path: Path) -> StoreUnavailableError:
    """Return the error of the layout of a store without its marker."""
    return StoreUnavailableError(
        message("marker.layout_without_marker", path=path, marker=MARKER),
        reason="no_marker",
        path=path,
        hint=message("marker.init_hint", path=path),
    )


def _not_empty(path: Path) -> ConflictError:
    return ConflictError(
        message("marker.not_empty", path=path, marker=MARKER),
        reason="not_empty",
        path=path,
        hint=message("marker.not_empty_hint"),
    )


def _inspect(path: Path) -> StoreState:
    """Check the root and say what it is (``store_state`` of an absolute path).

    Returns
    -------
    str
        ``marked`` (it has the marker), ``layout`` (the layout of a store, no
        marker), ``new`` (missing, or without a file) or ``foreign`` (something else).

    Raises
    ------
    ConflictError
        ``nested_store``.
    InvalidLayoutError
        The marker is not a ``kartograf-store/1`` document.
    OSError
        The marker cannot be read.
    """
    if (path / MARKER).is_file():
        _check_nested(path, below=True)
        _read_marker(path)
        return "marked"
    if not path.exists():
        _check_nested(path, below=True)
        return "new"
    if not path.is_dir():
        return "foreign"
    store, other = _contents(path)
    # A competing writer writes the marker before its first file: when the files are
    # seen, the marker is there, so it is looked for after the files, not before them.
    if (path / MARKER).is_file():
        return _inspect(path)
    if store:
        _check_nested(path, below=False)
        return "layout"
    _check_nested(path, below=True)
    return "foreign" if other else "new"


def _timestamp(moment: datetime | None) -> str:
    stamp = moment or _clock.now()
    if stamp.tzinfo is None:
        raise ValidationError(message("marker.naive_time"), option="created_at")
    return stamp.astimezone(UTC).isoformat(timespec="seconds")


def _write_marker(path: Path, created_at: datetime | None) -> bool:
    """Write the marker of a new root; return False when another writer was first."""
    payload = {
        "schema": MARKER_SCHEMA,
        "tool": TOOL,
        "created_at": _timestamp(created_at),
        "producer_version": build_version(),
    }
    path.mkdir(parents=True, exist_ok=True)
    marker = path / MARKER
    temporary = path / f".{MARKER}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write((json.dumps(payload, indent=2) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, marker)  # exclusive: never replaces a competing marker
        except FileExistsError:
            return False
        except OSError:
            # a file system without hard links (FAT, SMB): the marker needs none
            if marker.exists():
                return False
            os.replace(temporary, marker)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def prepare_store(root: str | os.PathLike[str]) -> Path:
    """
    Open the store at ``root`` for a write; the first write creates the marker.

    The root must not nest a store. A root with a marker is used as it is; a missing
    or empty root gets its marker now, as ``init_store`` writes it (DEV-19.13); a
    root with the layout of a store and no marker is ``store_unavailable``, and
    ``kartograf store init`` verifies it. Called before the first byte of every write
    into the store (the staging of a version).

    Parameters
    ----------
    root : str or os.PathLike
        Store root; created (with parents) when missing.

    Returns
    -------
    pathlib.Path
        The absolute root, which exists and has its marker.

    Raises
    ------
    ConflictError
        ``nested_store``, or ``not_empty`` (the root holds other files and no
        layout).
    StoreUnavailableError
        ``no_marker``: the layout of a store without its marker.
    InvalidLayoutError
        The marker is not a ``kartograf-store/1`` document.
    OSError
        The marker cannot be read.
    """
    path = _absolute(root)
    state = _inspect(path)
    if state == "layout":
        raise _unmarked(path)
    if state == "foreign":
        raise _not_empty(path)
    if state == "new":
        _write_marker(path, None)
    return path


def lenient_store(root: str | os.PathLike[str]) -> Path:
    """
    Check the store at ``root`` for a plan or a read; nothing is created.

    A missing or empty root is an empty store (every file of a plan is new); a root
    that a write would refuse is refused the same way, with the same reason.

    Parameters
    ----------
    root : str or os.PathLike
        Store root; it need not exist.

    Returns
    -------
    pathlib.Path
        The absolute root.

    Raises
    ------
    ConflictError
        ``nested_store`` or ``not_empty``.
    StoreUnavailableError
        ``no_marker``.
    InvalidLayoutError
        The marker is not a ``kartograf-store/1`` document.
    OSError
        The marker cannot be read.
    """
    path = _absolute(root)
    state = _inspect(path)
    if state == "layout":
        raise _unmarked(path)
    if state == "foreign":
        raise _not_empty(path)
    return path


def store_refusal(
    root: str | os.PathLike[str],
) -> ConflictError | StoreUnavailableError | InvalidLayoutError | None:
    """
    Return the error a write into the store at ``root`` is refused with, or None.

    The checks of `lenient_store`, with the error returned instead of raised, so that
    a caller can raise it (the run of a command) or list it (its plan, DEV-19.10).
    Nothing is created.

    Parameters
    ----------
    root : str or os.PathLike
        Store root; it need not exist.

    Returns
    -------
    ConflictError or StoreUnavailableError or InvalidLayoutError or None
        The error of `lenient_store`, or None when a write may go on.
    """
    try:
        lenient_store(root)
    except (ConflictError, StoreUnavailableError, InvalidLayoutError) as refusal:
        return refusal
    return None


def store_state(root: str | os.PathLike[str]) -> StoreState:
    """
    Say what the directory ``root`` is to a write into the store; nothing is written.

    The judgement of the writer itself (``prepare_store``, ``init_store``), so that a
    consumer that reads a store (Archiwista, Retman) asks Kartograf instead of judging
    the marker and the layout by file names (DEV-19.12 to DEV-19.14). It reads the
    marker, the top of the root, the product trees up to their first file, the
    ancestors of the root and what lies below it outside the product trees.

    Parameters
    ----------
    root : str or os.PathLike
        The directory; it need not exist.

    Returns
    -------
    {"marked", "layout", "new", "foreign"}
        ``marked``: the root holds ``kartograf-store.json`` of the schema
        ``kartograf-store/1``, a store a write uses as it is. ``layout``: files in the
        product trees of Kartograf (``nmt/``, ``laz/``..., of this version or of 0.7.x)
        and no marker: a write is ``store_unavailable`` (``no_marker``) until
        ``kartograf store init`` verifies the layout and writes the marker. ``new``:
        missing, or a directory without a file (a staging directory ``.incoming``
        does not count): the first write creates the marker. ``foreign``: a file, or
        a directory that holds other files and no layout: a write is ``conflict``
        (``not_empty``).

    Raises
    ------
    ConflictError
        ``nested_store``: the root lies in a store of any tool, holds the marker of
        another tool or has a store below it (markers found by their file names,
        ``STORE_MARKERS``).
    InvalidLayoutError
        The marker is not a ``kartograf-store/1`` document.
    OSError
        The marker cannot be read, or a directory above the root cannot be searched.

    Examples
    --------
    >>> from kartograf import store_state
    >>> store_state("/srv/nogat/kartograf")  # doctest: +SKIP
    'marked'
    """
    return _inspect(_absolute(root))


def _verify_layout(path: Path) -> None:
    """Verify a root with the layout of a store and no marker (DEV-19.13).

    Raises
    ------
    InvalidLayoutError
        An entry at the top level that is not a product directory of Kartograf, a
        product that is not a real directory, or a sidecar that is not
        ``kartograf-meta/1``.
    """
    problems: list[str] = []
    trees = managed_trees()
    for entry in sorted(path.iterdir()):
        if entry.name not in trees:
            problems.append(message("marker.unexpected_entry", name=entry.name))
        elif entry.is_symlink() or not entry.is_dir():
            problems.append(message("marker.tree_not_directory", name=entry.name))
        else:
            problems.extend(_foreign_sidecars(path, entry))
    if problems:
        raise InvalidLayoutError(
            message("marker.not_a_store", path=path, count=len(problems)),
            path=path,
            problems=problems[:MAX_PROBLEMS],
            hint=message("marker.layout_hint"),
        )


def _foreign_sidecars(root: Path, tree: Path) -> list[str]:
    """List the sidecars below ``tree`` that are not ``kartograf-meta/1``."""
    found: list[str] = []
    for sidecar in sorted(tree.rglob("*.meta.json")):
        try:
            schema = json.loads(sidecar.read_text(encoding="utf-8")).get("schema")
        except (OSError, ValueError, AttributeError):
            schema = None
        if sidecar.is_symlink() or schema != "kartograf-meta/1":
            found.append(
                message(
                    "marker.foreign_sidecar", path=sidecar.relative_to(root).as_posix()
                )
            )
    return found


def init_store(
    root: str | os.PathLike[str] | None = None, *, created_at: datetime | None = None
) -> StoreInit:
    """
    Write the marker of a store: ``kartograf store init`` (DEV-19.13).

    A new, missing or empty root gets the marker ``kartograf-store.json``. A root
    that has the layout of a store (``<product>/<variant>/versions/``, or the 0.7.x
    ``kampanie/``) but no marker is verified first (the top level holds product
    directories of Kartograf only and every sidecar is ``kartograf-meta/1``) and then
    marked; its files are not touched. A root that already has the marker is left as
    it is.

    Parameters
    ----------
    root : str or os.PathLike, optional
        Store root; created (with parents) when missing. Default: the store root of
        the settings (``store_root()``, DEV-19.2).
    created_at : datetime.datetime, optional
        Timezone-aware creation time recorded in the marker; now by default.

    Returns
    -------
    StoreInit
        The marker; ``created`` is false when the store had it already.

    Raises
    ------
    ValidationError
        An empty ``root`` or a ``created_at`` without a time zone.
    ConflictError
        ``nested_store``, or ``not_empty`` (the root holds other files and has no
        layout).
    InvalidLayoutError
        The layout of a root without a marker is not that of a Kartograf store
        (``details.problems``), or the existing marker is not a
        ``kartograf-store/1`` document.
    OSError
        The existing marker cannot be read.
    """
    from kartograf.config import resolve_root

    path = _absolute(resolve_root(root))
    stamp = _timestamp(created_at)  # fails before anything is written
    state = _inspect(path)
    if state == "foreign":
        raise _not_empty(path)
    if state == "layout":
        _verify_layout(path)
    created = state != "marked"
    if created:
        created = _write_marker(path, created_at)
    fields = _read_marker(path)
    return StoreInit(
        path,
        path / MARKER,
        created,
        fields.get("tool", TOOL),
        fields.get("created_at", stamp),
        fields.get("producer_version", ""),
    )


def check_store(root: str | os.PathLike[str] | None = None) -> "UpdatePlan":
    """
    Plan ``init_store`` without writing anything: ``kartograf store init --check``.

    The plan has one position of the track ``store``: the marker, ``missing`` with the
    action ``write`` when ``init_store`` would write it (a new, missing or empty root,
    or a root of the layout of a store that passes the verification), ``current`` when
    the root has it. A root that ``init_store`` refuses as a ``conflict``
    (``nested_store``, ``not_empty``) is the one position of that conflict, and the plan
    is ``ok``: only the run fails (DEV-19.10); every other refusal is raised, as the
    run raises it.

    Parameters
    ----------
    root : str or os.PathLike, optional
        Store root; it need not exist. Default: the store root of the settings
        (DEV-19.2).

    Returns
    -------
    UpdatePlan
        The plan of the store at ``root`` (``kartograf-plan/1``); nothing is created.

    Raises
    ------
    InvalidLayoutError
        The layout of a root without a marker is not that of a Kartograf store
        (``details.problems``), or the existing marker is not a ``kartograf-store/1``
        document.
    OSError
        The existing marker cannot be read.
    """
    from kartograf.config import resolve_root
    from kartograf.download.plan import PlanItem, conflict_plan, new_plan

    path = _absolute(resolve_root(root))
    try:
        state = _inspect(path)
        if state == "foreign":
            raise _not_empty(path)
        if state == "layout":
            _verify_layout(path)
    except ConflictError as refusal:
        return conflict_plan(path, refusal)
    marked = state == "marked"
    marker = PlanItem(
        track="store",
        segment="",
        hierarchy="",
        name=MARKER,
        unit=str(path),
        local_label=None,
        local_sha256=None,
        available_label=None,
        available_signal=None,
        status="current" if marked else "missing",
        action=None if marked else "write",
        path=path / MARKER,
    )
    return new_plan(path, [marker])
