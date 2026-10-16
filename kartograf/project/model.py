"""Types of a project manifest and of the project operations (ADR-040).

A project (``kartograf-project.json``, schema ``kartograf-project/1``) is a
store (``output_dir``) and tasks: a data command of a CLI group with its
options and the store versions it pinned. Field meanings: spec
``docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`` 3.3, 4.3.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from kartograf.notices import Notice

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


@dataclass(frozen=True)
class PinnedFile:
    """One pinned store file of a task (``tasks[].files[]``).

    ``role``: ``output`` (result of the task), ``raw`` (original package,
    e.g. the BDOT10k ZIP of ``keep_raw``) or ``input`` (input of a derived
    file: clay/sand/silt of HSG). ``unit``: sheet, LAZ tile, TERYT or
    cutout - for messages. ``path``: the standard path (WHICH file),
    ``version``: the pinned version file (WHICH bytes), both relative to the
    store with ``/``. ``label``, ``sha256`` and ``size_bytes`` of the version.
    """

    role: PinRole
    unit: str
    path: str
    version: str
    label: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ProjectTask:
    """One task: a data command (``command``, e.g. ``elevation download``)
    with its ``options`` in the JSON form of the manifest (read-only
    mapping) and its pinned files (empty before the first download).

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
class Project:
    """A project read from its manifest: ``directory`` holds
    ``kartograf-project.json``, ``output_dir`` is the store (both absolute)."""

    directory: Path
    output_dir: Path
    tasks: tuple[ProjectTask, ...]


@dataclass(frozen=True)
class TaskResult:
    """Outcome of one task of ``download_project``.

    ``outcome``: ``pinned`` (first pin), ``unchanged`` (pins kept, nothing
    to do), ``restored`` (missing pinned versions back with the same
    SHA-256), ``updated`` (re-pinned by ``upgrade``/``force``) or ``failed``
    (``errors``; the pins of the task are unchanged, except restored ones).
    ``pinned``: new pins, ``unpinned``: pins replaced or dropped.
    """

    name: str
    outcome: TaskOutcome
    pinned: tuple[PinnedFile, ...]
    unpinned: tuple[PinnedFile, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class ProjectReport:
    """Outcome of ``download_project``: the manifest after the run, one
    result per selected task, the data notices (prefixed with the task
    name) and ``ok`` = no selected task failed."""

    project: Project
    tasks: tuple[TaskResult, ...]
    notices: tuple[Notice, ...]
    ok: bool


@dataclass(frozen=True)
class FileCheck:
    """State of one pinned file (or of a plan position without a pin).

    ``status``: ``ok``/``missing``/``corrupt`` (``get_project_status``,
    ``verify_project``) or ``current``/``newer``/``added``/``removed``/
    ``unverifiable``/``check_failed``/``missing`` (``check_project``).
    ``detail``: the reason with a remedy, ``None`` when nothing to do.
    """

    task: str
    unit: str
    path: str
    status: PinStatus
    pinned_label: str | None
    available_label: str | None
    detail: str | None


@dataclass(frozen=True)
class ProjectCheck:
    """Outcome of ``get_project_status``, ``verify_project`` and ``check_project``.

    ``not_downloaded``: selected tasks without pins. ``ok``: status/verify -
    every selected task pinned and every file ``ok``; check - no file
    ``check_failed``.
    """

    project: Project
    files: tuple[FileCheck, ...]
    not_downloaded: tuple[str, ...]
    notices: tuple[Notice, ...]
    ok: bool
