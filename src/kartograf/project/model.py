"""Types of a project manifest and of the project operations (ADR-040).

A project (``kartograf-project.json``, schema ``kartograf-project/1``) is a
store (``output_dir``) and tasks: a data command of a CLI group with its
options and the store versions it pinned. Field meanings: spec
``docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`` 3.3, 4.3.

``Project``, ``ProjectReport`` and ``ProjectCheck`` are JSON documents
(``kartograf-project-state/1``, ``-project-report/1``, ``-project-check/1``;
spec 5.4.8). The manifest keeps the paths of the pins relative to the store;
the documents have absolute paths: they set ``EncodeContext.store`` to the
store of the project and ``PinnedFile``/``FileCheck`` join their paths to it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kartograf.notices import Notice
from kartograf.serialization import Document, EncodeContext

PinRole = Literal["output", "raw", "input"]
TaskOutcome = Literal["pinned", "unchanged", "restored", "updated", "failed"]
PinStatus = Literal[
    "ok",
    "missing",
    "corrupt",
    "current",
    "newer",
    "added",
    "removed",
    "unverifiable",
    "check_failed",
]


def _store_of(ctx: EncodeContext, what: str) -> Path:
    """Return the store of the enclosing project document (a pin has no other)."""
    if ctx.store is None:
        raise ValueError(
            f"{what} is encoded only inside a project document "
            "(its paths are relative to the store of the project)"
        )
    return ctx.store


@dataclass(frozen=True)
class PinnedFile:
    """One pinned store file of a task (``tasks[].files[]``).

    ``role``: ``output`` (result of the task), ``raw`` (original package,
    e.g. the BDOT10k ZIP of ``keep_raw``) or ``input`` (input of a derived
    file: clay/sand/silt of HSG). ``unit``: sheet, LAZ tile, TERYT or
    cutout - for messages. ``path``: the standard path (WHICH file),
    ``version``: the pinned version file (WHICH bytes), both relative to the
    store with ``/``. ``label``, ``sha256`` and ``size_bytes`` of the version.

    In a project document ``path`` and ``version`` are absolute: the store of
    the project joined to the manifest value (``__json__``).
    """

    role: PinRole
    unit: str
    path: str
    version: str
    label: str
    sha256: str
    size_bytes: int

    def __json__(self, ctx: EncodeContext) -> dict[str, object]:
        """Encode the pin into its JSON form."""
        store = _store_of(ctx, "PinnedFile")
        return {
            "role": self.role,
            "unit": self.unit,
            "path": store / self.path,
            "version": store / self.version,
            "label": self.label,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class ProjectTask:
    """One task: a data command (``command``, e.g. ``elevation download``).

    It has its ``options`` in the JSON form of the manifest (read-only mapping) and its
    pinned files (empty before the first download).

    ``pinned_at``/``kartograf_version``: the last change of the pins (UTC,
    ISO 8601) and the Kartograf version that made it, ``None`` for a task
    not downloaded yet. ``geometry_sha256``: ``{file name: sha256}`` of the
    geometry files of ``options["geometry"]`` when the task was pinned.
    """

    name: str
    command: str
    options: Mapping[str, object]
    pinned_at: str | None
    kartograf_version: str | None
    geometry_sha256: Mapping[str, str] | None
    files: tuple[PinnedFile, ...]


@dataclass(frozen=True)
class Project(Document):
    """A project read from its manifest.

    ``directory`` holds ``kartograf-project.json``, ``output_dir`` is the store (both
    absolute).

    Document ``kartograf-project-state/1``; ``tasks[].options`` keep the form
    of the manifest (paths relative to ``directory``, ``bbox`` + ``bbox_crs``).
    """

    SCHEMA = "kartograf-project-state/1"

    directory: Path
    output_dir: Path
    tasks: tuple[ProjectTask, ...]

    def prepare_context(self, ctx: EncodeContext) -> None:
        """Set the store of the encoding context."""
        ctx.store = self.output_dir


@dataclass(frozen=True)
class TaskResult:
    """Outcome of one task of ``download_project``.

    ``outcome``: ``pinned`` (first pin), ``unchanged`` (pins kept, nothing
    to do), ``restored`` (missing pinned versions back with the same
    SHA-256), ``updated`` (re-pinned by ``upgrade``/``force``) or ``failed``
    (``errors``; the pins of the task are unchanged, except restored ones).
    ``pinned``: new pins, ``unpinned``: pins replaced or dropped. A failed task
    has the registry ``code`` of its failure and, where the code does not say
    enough, its ``reason`` (``details.reason``); both are ``None`` otherwise.
    """

    name: str
    outcome: TaskOutcome
    pinned: tuple[PinnedFile, ...]
    unpinned: tuple[PinnedFile, ...]
    errors: tuple[str, ...]
    code: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ProjectReport(Document):
    """Outcome of ``download_project``.

    It holds the manifest after the run, one result per selected task, the data notices
    (prefixed with the task name) and ``ok`` = no selected task failed.

    Document ``kartograf-project-report/1``; ``project`` is nested (no
    ``schema`` key).
    """

    SCHEMA = "kartograf-project-report/1"

    project: Project
    tasks: tuple[TaskResult, ...]
    notices: tuple[Notice, ...]
    ok: bool

    def prepare_context(self, ctx: EncodeContext) -> None:
        """Set the store of the encoding context."""
        ctx.store = self.project.output_dir


@dataclass(frozen=True)
class FileCheck:
    """State of one pinned file (or of a plan position without a pin).

    ``status``: ``ok``/``missing``/``corrupt`` (``get_project_status``,
    ``verify_project``) or ``current``/``newer``/``added``/``removed``/
    ``unverifiable``/``check_failed``/``missing`` (``check_project``).
    ``detail``: the reason with a remedy, ``None`` when nothing to do.

    ``path`` is the standard path relative to the store; in a project
    document it is absolute (``__json__``).
    """

    task: str
    unit: str
    path: str
    status: PinStatus
    pinned_label: str | None
    available_label: str | None
    detail: str | None

    def __json__(self, ctx: EncodeContext) -> dict[str, object]:
        """Encode the report into its JSON form."""
        return {
            "task": self.task,
            "unit": self.unit,
            "path": _store_of(ctx, "FileCheck") / self.path,
            "status": self.status,
            "pinned_label": self.pinned_label,
            "available_label": self.available_label,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ProjectCheck(Document):
    """Outcome of ``get_project_status``, ``verify_project`` and ``check_project``.

    ``not_downloaded``: selected tasks without pins. ``ok``: status/verify -
    every selected task pinned and every file ``ok``; check - no file
    ``check_failed``.

    Document ``kartograf-project-check/1``; ``project`` is nested (no
    ``schema`` key).
    """

    SCHEMA = "kartograf-project-check/1"

    project: Project
    files: tuple[FileCheck, ...]
    not_downloaded: tuple[str, ...]
    notices: tuple[Notice, ...]
    ok: bool

    def prepare_context(self, ctx: EncodeContext) -> None:
        """Set the store of the encoding context."""
        ctx.store = self.project.output_dir
