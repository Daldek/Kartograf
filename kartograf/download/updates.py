"""
Update plan ``kartograf-plan/1`` (spec 4.4).

``check_updates`` compares the freshness signal of every file of a request
with its local version WITHOUT downloading anything and returns an
``UpdatePlan`` (JSON with English keys). ``upgrade`` executes a plan: before
each position the signal is read again — a position whose signal changed
since the plan is ``stale`` and is not downloaded; positions removed from the
plan file are never executed. This module covers the ``pl_sheet`` track
(``DownloadManager``); the plan types live in ``kartograf.download.plan``.
"""

import dataclasses
from dataclasses import dataclass, field
from datetime import UTC, datetime

from kartograf._version import build_version
from kartograf.download.manager import (
    DownloadManager,
    SheetFetch,
    SheetInspection,
    _Pick,
)
from kartograf.download.plan import (
    TODO_STATUSES,
    ItemStatus,
    PlanItem,
    UpdatePlan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.versions import LocalVersion, newest_version
from kartograf.exceptions import DownloadError


@dataclass(frozen=True)
class UpgradeReport:
    """Result of ``upgrade``: executed sheets, stale positions, failures."""

    done: tuple[SheetFetch, ...]
    stale: tuple[PlanItem, ...]
    failed: dict[str, str] = field(default_factory=dict)


def _store(manager: DownloadManager) -> str:
    return store_id(manager.storage.output_dir)


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

    def item(
        name: str,
        local: LocalVersion | None,
        label: str | None,
        signal: dict | None,
        status: ItemStatus,
        error: str | None = None,
    ) -> PlanItem:
        return PlanItem(
            track="pl_sheet",
            segment=segment,
            hierarchy=hierarchy,
            name=name,
            unit=sheet,
            local_label=local.label if local is not None else None,
            local_sha256=local.sha256 if local is not None else None,
            available_label=label,
            available_signal=signal,
            status=status,
            error=error,
        )

    std = inspection.std.name
    if inspection.error is not None:
        return [item(std, None, None, None, "check_failed", str(inspection.error))]
    if not inspection.picks and not inspection.record_errors:
        local = newest_version(inspection.versions)
        status: ItemStatus = "unverifiable" if local is not None else "missing"
        return [item(std, local, None, None, status)]
    items = [
        item(pick.name, pick.local, pick.ref.dirname, _signal(pick), _status(pick))
        for pick in inspection.picks
    ]
    items.extend(
        item(std, None, label, None, "check_failed", str(error))
        for label, error in inspection.record_errors
    )
    return items


def check_updates(manager: DownloadManager, sheets: list[str]) -> UpdatePlan:
    """Plan of the request ``sheets`` without downloading anything (spec 4.4).

    The manager's strategy (``all_campaigns``), year bounds and ``full_sheet``
    select the files, exactly as a download would; coarser PL-1992 sheets
    expand to 1:10000. Every position has the track ``pl_sheet``.
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
    """Execute the ``newer``/``missing`` ``pl_sheet`` positions of a plan (spec 4.4).

    Positions of other tracks are left to their own ``run_*`` functions
    (``plan=``). Before downloading, every planned sheet is checked again;
    ``select_planned`` decides what runs and what is ``stale``.

    Raises
    ------
    ValidationError
        Unknown schema or a plan of another store (``--output``), before any
        request to the source.
    """
    require_store(plan, _store(manager))
    planned = [i for i in plan.items_for("pl_sheet") if i.status in TODO_STATUSES]
    sheets = list(dict.fromkeys(item.unit for item in planned))
    done: list[SheetFetch] = []
    failed: dict[str, str] = {}
    if not sheets:
        return UpgradeReport((), (), failed)
    checked: set[str] = set()
    fresh: list[PlanItem] = []
    picks: dict[tuple[str, str, str], _Pick] = {}
    available: dict[str, tuple[int, ...] | None] = {}
    for inspection in manager.inspect_sheets(sheets):
        sheet = inspection.sheet
        if sheet not in sheets:
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
        checked.add(sheet)
        fresh.extend(_items(manager, inspection))
        available[sheet] = inspection.available
        for pick in inspection.picks:
            picks[(sheet, pick.name, pick.ref.dirname)] = pick
    scope = dataclasses.replace(
        plan, items=tuple(i for i in planned if i.unit in checked)
    )
    todo, stale = select_planned(scope, fresh, "pl_sheet")
    records: dict[str, list] = {}
    for item in todo:
        pick = picks[(item.unit, item.name, item.available_label or "")]
        records.setdefault(item.unit, []).append(pick.record)
    for sheet, chosen in records.items():
        try:
            done.append(
                manager.download_records(sheet, tuple(chosen), available[sheet])
            )
        except DownloadError as e:
            failed[sheet] = str(e)
    return UpgradeReport(tuple(done), tuple(stale), failed)
