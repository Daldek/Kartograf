"""Internal PL-sheet plan item construction for ``DownloadManager.check_sheets``."""

from typing import Any

from kartograf.download.manager import DownloadManager, SheetInspection, _Pick
from kartograf.download.plan import ItemStatus, PlanItem
from kartograf.download.versions import LocalVersion, newest_version


def _where(manager: DownloadManager, sheet: str) -> tuple[str, str]:
    """``(segment, hierarchy)`` of a sheet, relative to the output directory."""
    storage = manager.storage
    segment_root = storage.get_versions_base(sheet).parent
    std = storage.get_path(sheet, manager.provider.default_extension)
    return (
        segment_root.relative_to(storage.root).as_posix(),
        std.parent.relative_to(segment_root).as_posix(),
    )


def _signal(pick: _Pick) -> dict[str, Any]:
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
        signal: dict[str, Any] | None,
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
