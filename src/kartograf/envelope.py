"""
The result envelope ``kartograf-result/1`` of a command (AGI-4.2, ADR-051).

The CLI with ``--json``, every MCP tool and ``run_command``/``check_command`` answer
with this one document: the domain document of the command (``kartograf-download/1``,
``kartograf-plan/1``, ...) as ``result``, the outcome as ``status`` and the
``notices`` of the run. A batch also lists the outcome of every unit in ``items``.
A failure that stops the command is no envelope but the error document
``kartograf-error/1`` (``kartograf.error_report``).

The status is the verdict of the domain document (its ``ok``): ``ok``; ``partial`` when
it is false and a unit succeeded; ``failed`` when it is false and no unit did. The
process exit code follows the status (``kartograf._errors.OUTCOMES``: 0, 10, 11).
Every document with a verdict has a reader in ``_READERS`` that gives its units; a
document without a verdict (a sheet, a list of sources, a store overview, ...) is ``ok``
with no items.

Examples
--------
>>> from kartograf.envelope import wrap
>>> from kartograf.source_info import list_sources
>>> envelope = wrap("elevation list-sources", list_sources(group="elevation"))
>>> envelope.status, envelope.exit_code, envelope.check
('ok', 0, False)
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from kartograf._errors import OUTCOMES
from kartograf.download.availability import AvailabilityReport
from kartograf.download.collections import CollectionReport
from kartograf.download.data import DataReport, UnitFailure
from kartograf.download.plan import PlanItem, UpdatePlan
from kartograf.hydrology.hsg import HsgReport
from kartograf.landcover.manager import LandCoverReport, SoilReport
from kartograf.notices import Notice
from kartograf.serialization import Document, EncodeContext, encode

__all__ = [
    "CommandResult",
    "Outcome",
    "ResultItem",
    "exit_code_of",
    "outcome_of",
    "wrap",
]

TOOL: Final = "kartograf"

Status = Literal["ok", "partial", "failed", "cancelled"]
ItemStatus = Literal["ok", "failed"]

_DownloadReport = (
    DataReport | CollectionReport | LandCoverReport | SoilReport | HsgReport
)


def _package_version() -> str:
    """Return ``kartograf.__version__`` (the module cannot import the package early)."""
    import kartograf

    return kartograf.__version__


@dataclass(frozen=True)
class ResultItem:
    """The outcome of one unit of a batch (an entry of ``items``, AGI-4.2).

    ``id`` names the unit (a sheet, a country, a task, a path below the store). A
    failed unit has the registry ``code`` of its failure and, when the code does not
    say enough, the ``reason`` of ``details.reason``; ``message`` is the text of the
    failure.
    """

    id: str
    status: ItemStatus
    code: str | None = None
    reason: str | None = None
    message: str | None = None

    def __json__(self, ctx: EncodeContext) -> dict[str, object]:
        """Encode the item; a key without a value is left out."""
        document: dict[str, object] = {"id": self.id, "status": self.status}
        for key in ("code", "reason", "message"):
            value = getattr(self, key)
            if value is not None:
                document[key] = value
        return document


@dataclass(frozen=True)
class Outcome:
    """What a domain document says of its run: the status, the units and the notices."""

    status: Status
    items: tuple[ResultItem, ...]
    notices: tuple[Notice, ...]


@dataclass(frozen=True)
class CommandResult[T: Document](Document):
    """The envelope of a command (``kartograf-result/1``, AGI-4.2).

    Parameters
    ----------
    command : str
        The catalog id of the command (``elevation download``).
    check : bool
        The run was a plan without effects (the result is ``kartograf-plan/1``).
    status : {"ok", "partial", "failed", "cancelled"}
        The outcome; ``partial`` has an ``ok`` and a ``failed`` item, ``failed`` has
        no ``ok`` item. ``cancelled`` is never produced: a cancelled command is the
        error ``cancelled``.
    result : Document or None
        The domain document of the command, ``None`` when nothing was produced.
    items : tuple of ResultItem
        The outcome of every unit of a batch (``()`` for a command with no batch).
    notices : tuple of Notice
        The notices of the run (the ones of ``result``).
    version : str
        The version of the package (``kartograf.__version__``).

    ``to_dict()`` is the document the CLI ``--json`` prints and the MCP tools return;
    ``result`` is written with its own ``schema``. The key ``page`` of the schema is
    not written: no command pages its result yet.
    """

    SCHEMA = "kartograf-result/1"
    JSON_KEYS = (
        "tool",
        "version",
        "command",
        "check",
        "status",
        "result",
        "items",
        "notices",
    )
    JSON_FILL = {"tool": TOOL}

    command: str
    check: bool
    status: Status
    result: T | None
    items: tuple[ResultItem, ...] = ()
    notices: tuple[Notice, ...] = ()
    version: str = field(default_factory=_package_version)

    @property
    def exit_code(self) -> int:
        """Return the exit code of the CLI for the status (0, 10, 11 or 130)."""
        return OUTCOMES[self.status]

    def to_dict(self) -> dict[str, object]:
        """Return the envelope as a JSON object; ``result`` keeps its ``schema``."""
        return {
            "schema": self.SCHEMA,
            "tool": TOOL,
            "version": self.version,
            "command": self.command,
            "check": self.check,
            "status": self.status,
            "result": None if self.result is None else self.result.to_dict(),
            "items": encode(self.items),
            "notices": encode(self.notices),
        }


# --- the units of a document ---------------------------------------------------------

_Reading = tuple[bool, tuple[ResultItem, ...], tuple[Notice, ...]]


def _failure_item(failure: UnitFailure) -> ResultItem:
    return ResultItem(
        failure.unit, "failed", failure.code, failure.reason, failure.error
    )


def _stale_item(position: PlanItem) -> ResultItem:
    """Return the item of a planned position the source changed since the plan."""
    return ResultItem(
        position.store_path,
        "failed",
        "conflict",
        "stale_plan",
        "The source changed since the plan was made: make a new plan.",
    )


def _download(report: _DownloadReport) -> _Reading:
    """Read a ``kartograf-download/1`` report: a unit per file, failure and stale pin.

    A failed part of a successful report (``--country auto`` with one country down,
    ADR-049 A3-2) is a notice of the report, not a failed unit.
    """
    items = [
        ResultItem(unit, "ok") for unit in dict.fromkeys(f.unit for f in report.files)
    ]
    if not report.ok:
        failed = [
            *(_failure_item(failure) for failure in report.failed),
            *(_stale_item(position) for position in report.stale),
        ]
        named = {item.id for item in failed}
        items = [item for item in items if item.id not in named] + failed
    return report.ok, tuple(items), report.notices


def _position_item(position: PlanItem) -> ResultItem:
    if position.status == "check_failed":
        return ResultItem(
            position.store_path,
            "failed",
            "source_unavailable",
            "check_failed",
            position.error,
        )
    return ResultItem(position.store_path, "ok")


def _plan(plan: UpdatePlan) -> _Reading:
    """Read a plan: a position per unit; only one the source could not tell fails."""
    return plan.ok, tuple(_position_item(item) for item in plan.items), plan.notices


def _availability(report: AvailabilityReport) -> _Reading:
    """Read an availability report: a unit per country, a country not checked fails."""
    items = [
        ResultItem(country, "ok")
        for country in dict.fromkeys(area.country for area in report.areas)
    ]
    items += [_failure_item(failure) for failure in report.failed]
    return report.ok, tuple(items), report.notices


# document type -> its reader (by type: a document with a verdict nobody reads is a
# program error, not a success)
_READERS: Mapping[type[Document], Callable[[Any], _Reading]] = {
    DataReport: _download,
    CollectionReport: _download,
    LandCoverReport: _download,
    SoilReport: _download,
    HsgReport: _download,
    UpdatePlan: _plan,
    AvailabilityReport: _availability,
}


def outcome_of(document: Document | None, *, command: str = "") -> Outcome:
    """Return the status, the units and the notices of the document of a command.

    Parameters
    ----------
    document : Document or None
        The domain document of the command; ``None`` (nothing produced) is ``ok``.
    command : str
        The catalog id of the command: the id of the unit that stands for a verdict
        ``ok: false`` the document gives no failed unit for.

    Raises
    ------
    TypeError
        A document with an ``ok`` verdict that has no reader in this module.
    """
    if document is None:
        return Outcome("ok", (), ())
    reader = _READERS.get(type(document))
    if reader is None:
        if hasattr(document, "ok"):
            raise TypeError(
                f"{type(document).__name__} has a verdict (ok) and no reader in "
                "kartograf.envelope"
            )
        return Outcome("ok", (), ())
    ok, items, notices = reader(document)
    if ok:
        return Outcome("ok", items, notices)
    if not any(item.status == "failed" for item in items):
        items += (
            ResultItem(
                command or type(document).__name__,
                "failed",
                "internal_error",
                None,
                "The command failed without naming a failed unit.",
            ),
        )
    done = any(item.status == "ok" for item in items)
    return Outcome("partial" if done else "failed", items, notices)


def wrap[T: Document](
    command: str, document: T | None, *, check: bool = False
) -> CommandResult[T]:
    """Return the envelope of the document a command produced.

    Parameters
    ----------
    command : str
        The catalog id of the command (``elevation download``).
    document : Document or None
        The domain document.
    check : bool
        The run was a plan without effects.
    """
    outcome = outcome_of(document, command=command)
    return CommandResult(
        command, check, outcome.status, document, outcome.items, outcome.notices
    )


def exit_code_of(document: Document | None) -> int:
    """Return the exit code of the CLI for the document of a command (0, 10 or 11)."""
    return OUTCOMES[outcome_of(document).status]
