"""
Update plan ``kartograf-plan/1`` (spec 4.4).

``check_updates`` compares the freshness signal of every file of a request
with its local version WITHOUT downloading anything and returns an
``UpdatePlan`` (JSON with English keys). ``upgrade`` executes a plan: before
each position the signal is read again — a position whose signal changed
since the plan is ``stale`` and is not downloaded; positions removed from the
plan file are never executed. Plan 1/3 covers PL sheets downloaded through
``DownloadManager``.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast, get_args

from kartograf._version import build_version
from kartograf.download.manager import (
    DownloadManager,
    SheetFetch,
    SheetInspection,
    _Pick,
)
from kartograf.download.versions import newest_version
from kartograf.exceptions import DownloadError, ValidationError

PLAN_SCHEMA = "kartograf-plan/1"
ItemStatus = Literal["current", "newer", "missing", "unverifiable", "check_failed"]
_TODO = ("newer", "missing")


@dataclass(frozen=True)
class PlanItem:
    """One file of the request: local version vs. the source signal.

    ``available_signal`` for an index (skorowidz) record: ``url``, ``date``
    and ``pzgik_date``. ``status``: ``current`` (the local version is the
    newest), ``newer`` (a newer campaign exists, not local), ``missing`` (no
    local version), ``unverifiable`` (no cheap signal), ``check_failed``
    (the signal could not be read; ``error``).
    """

    segment: str
    hierarchy: str
    name: str
    sheet: str
    local_label: str | None
    local_sha256: str | None
    available_label: str | None
    available_signal: dict | None
    status: ItemStatus
    error: str | None = None


@dataclass(frozen=True)
class UpdatePlan:
    """Result of ``check_updates``; ``store`` = resolved output directory."""

    store: str
    checked_at: str
    kartograf_version: str
    items: tuple[PlanItem, ...]
    schema: str = PLAN_SCHEMA

    def to_json(self) -> str:
        """The plan as JSON (``kartograf-plan/1``)."""
        payload = asdict(self)
        payload["items"] = [asdict(item) for item in self.items]
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "UpdatePlan":
        """Read a plan; an unknown schema or a malformed plan = ``ValidationError``."""
        try:
            payload = json.loads(text)
        except ValueError as e:
            raise ValidationError(f"Plan aktualizacji nie jest JSON: {e}") from e
        if not isinstance(payload, dict) or payload.get("schema") != PLAN_SCHEMA:
            schema = payload.get("schema") if isinstance(payload, dict) else None
            raise ValidationError(
                f"Nieznany schemat planu aktualizacji {schema!r} "
                f"(oczekiwano {PLAN_SCHEMA!r})"
            )
        try:
            items = tuple(_item(raw) for raw in payload["items"])
            return cls(
                store=str(payload["store"]),
                checked_at=str(payload["checked_at"]),
                kartograf_version=str(payload["kartograf_version"]),
                items=items,
            )
        except (KeyError, TypeError) as e:
            raise ValidationError(f"Niekompletny plan aktualizacji: {e}") from e


@dataclass(frozen=True)
class UpgradeReport:
    """Result of ``upgrade``: executed sheets, stale positions, failures."""

    done: tuple[SheetFetch, ...]
    stale: tuple[PlanItem, ...]
    failed: dict[str, str] = field(default_factory=dict)


def _item(raw: dict) -> PlanItem:
    status = raw["status"]
    if status not in get_args(ItemStatus):
        raise ValidationError(f"Nieznany status pozycji planu {status!r}")
    return PlanItem(
        segment=str(raw["segment"]),
        hierarchy=str(raw["hierarchy"]),
        name=str(raw["name"]),
        sheet=str(raw["sheet"]),
        local_label=raw.get("local_label"),
        local_sha256=raw.get("local_sha256"),
        available_label=raw.get("available_label"),
        available_signal=raw.get("available_signal"),
        status=cast(ItemStatus, status),
        error=raw.get("error"),
    )


def _store(manager: DownloadManager) -> str:
    return str(Path(manager.storage.output_dir).resolve())


def _where(manager: DownloadManager, sheet: str) -> tuple[str, str]:
    """``(segment, hierarchy)`` of a sheet, relative to the output directory."""
    storage = manager.storage
    segment_root = storage.get_versions_base(sheet).parent
    std = storage.get_path(sheet, manager.provider.default_extension)
    return (
        segment_root.relative_to(storage.output_dir).as_posix(),
        std.parent.relative_to(segment_root).as_posix(),
    )


def _signal(pick: _Pick) -> dict:
    record = pick.record
    return {"url": record.url, "date": record.aktualnosc, "pzgik_date": record.dt_pzgik}


def _status(pick: _Pick) -> ItemStatus:
    if pick.local is None:
        return "missing"
    return "newer" if pick.newer else "current"


def _items(manager: DownloadManager, inspection: SheetInspection) -> list[PlanItem]:
    sheet = inspection.sheet
    segment, hierarchy = _where(manager, sheet)
    if inspection.error is not None:
        return [
            PlanItem(
                segment,
                hierarchy,
                inspection.std.name,
                sheet,
                None,
                None,
                None,
                None,
                "check_failed",
                str(inspection.error),
            )
        ]
    if not inspection.picks and not inspection.record_errors:
        local = newest_version(inspection.versions)
        return [
            PlanItem(
                segment,
                hierarchy,
                inspection.std.name,
                sheet,
                local.label if local is not None else None,
                local.sha256 if local is not None else None,
                None,
                None,
                "unverifiable" if local is not None else "missing",
            )
        ]
    items = [
        PlanItem(
            segment,
            hierarchy,
            pick.name,
            sheet,
            pick.local.label if pick.local is not None else None,
            pick.local.sha256 if pick.local is not None else None,
            pick.ref.dirname,
            _signal(pick),
            _status(pick),
        )
        for pick in inspection.picks
    ]
    items.extend(
        PlanItem(
            segment,
            hierarchy,
            inspection.std.name,
            sheet,
            None,
            None,
            label,
            None,
            "check_failed",
            str(error),
        )
        for label, error in inspection.record_errors
    )
    return items


def check_updates(manager: DownloadManager, sheets: list[str]) -> UpdatePlan:
    """Plan of the request ``sheets`` without downloading anything (spec 4.4).

    The manager's strategy (``all_campaigns``), year bounds and ``full_sheet``
    select the files, exactly as a download would; coarser PL-1992 sheets
    expand to 1:10000.
    """
    items = [
        item
        for inspection in manager.inspect_sheets(sheets)
        for item in _items(manager, inspection)
    ]
    return UpdatePlan(
        store=_store(manager),
        checked_at=datetime.now(UTC).isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        items=tuple(items),
    )


def upgrade(manager: DownloadManager, plan: UpdatePlan) -> UpgradeReport:
    """Execute the ``newer``/``missing`` positions of a plan (spec 4.4).

    Raises
    ------
    ValidationError
        Unknown schema or a plan of another store (``--output``), before any
        request to the source.
    """
    if plan.schema != PLAN_SCHEMA:
        raise ValidationError(
            f"Nieznany schemat planu aktualizacji {plan.schema!r} "
            f"(oczekiwano {PLAN_SCHEMA!r})"
        )
    if plan.store != _store(manager):
        raise ValidationError(
            f"Plan dotyczy innego magazynu ({plan.store}), nie {_store(manager)}"
        )
    todo: dict[str, list[PlanItem]] = {}
    for item in plan.items:
        if item.status in _TODO:
            todo.setdefault(item.sheet, []).append(item)
    done: list[SheetFetch] = []
    stale: list[PlanItem] = []
    failed: dict[str, str] = {}
    if not todo:
        return UpgradeReport((), (), failed)
    for inspection in manager.inspect_sheets(list(todo)):
        sheet = inspection.sheet
        if sheet not in todo:
            continue
        if inspection.error is not None:
            failed[sheet] = str(inspection.error)
            continue
        if not inspection.picks:  # provider without campaigns: no signal
            try:
                manager.download_sheet(sheet, update="upgrade")
            except DownloadError as e:
                failed[sheet] = str(e)
                continue
            if manager.last_sheet is not None:
                done.append(manager.last_sheet)
            continue
        fresh = {(p.name, p.ref.dirname): p for p in inspection.picks}
        records = []
        for item in todo[sheet]:
            pick = fresh.get((item.name, item.available_label or ""))
            if pick is None or _signal(pick) != item.available_signal:
                stale.append(item)  # the source changed since the plan
            elif _status(pick) in _TODO:
                records.append(pick.record)
        if not records:
            continue
        try:
            done.append(
                manager.download_records(sheet, tuple(records), inspection.available)
            )
        except DownloadError as e:
            failed[sheet] = str(e)
    return UpgradeReport(tuple(done), tuple(stale), failed)
