"""Update plan types shared by every track (kartograf.download.plan)."""

import dataclasses
import json

import pytest

from kartograf.download.plan import (
    TRACKS,
    PlanItem,
    UpdatePlan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.exceptions import ValidationError
from kartograf.notices import Notice


def _item(track="laz_tile", name="a.laz", status="missing", **kwargs) -> PlanItem:
    fields = {
        "track": track,
        "segment": "laz/pl_1992_evrf2007",
        "hierarchy": "N-34/139/C/a/3",
        "name": name,
        "unit": "N-34-139-C-a-3-1",
        "local_label": None,
        "local_sha256": None,
        "available_label": "2025-10-21_84183",
        "available_signal": {"url": f"https://example.test/{name}", "date": "x"},
        "status": status,
    }
    fields.update(kwargs)
    return PlanItem(**fields)


def _plan(*items: PlanItem, store="/magazyn") -> UpdatePlan:
    return UpdatePlan(store, "2026-10-12T08:00:00+00:00", "0.8.0", tuple(items))


def test_store_path_is_the_position_below_the_store():
    assert _item().store_path == "laz/pl_1992_evrf2007/N-34/139/C/a/3/a.laz"
    # a flat segment has no hierarchy: no empty part, no double slash
    assert _item(hierarchy="").store_path == "laz/pl_1992_evrf2007/a.laz"


def test_plan_round_trip_all_tracks():
    assert {"landcover", "hsg"} <= set(TRACKS)
    plan = _plan(*(_item(track=t, name=f"{t}.tif") for t in TRACKS))
    assert UpdatePlan.from_json(plan.to_json()) == plan
    assert [i["track"] for i in json.loads(plan.to_json())["items"]] == list(TRACKS)


@pytest.mark.parametrize(
    ("field", "value"), [("track", "pl_campaign"), ("status", "stale")]
)
def test_plan_unknown_track_or_status_is_validation_error(field, value):
    payload = json.loads(_plan(_item()).to_json())
    payload["items"][0][field] = value
    with pytest.raises(ValidationError, match=repr(value)):
        UpdatePlan.from_json(json.dumps(payload))


def test_plan_without_track_is_validation_error():
    payload = json.loads(_plan(_item()).to_json())
    del payload["items"][0]["track"]
    with pytest.raises(ValidationError, match="Niekompletny"):
        UpdatePlan.from_json(json.dumps(payload))


def test_plan_to_dict_schema_first():
    unit_list = Notice("info", "unit_list", "nmt: wojewodztwa obszaru wg PRG (1): 12")
    plan = dataclasses.replace(_plan(_item()), notices=(unit_list,))

    data = plan.to_dict()

    assert list(data) == [
        "schema",
        "store",
        "checked_at",
        "kartograf_version",
        "items",
        "notices",
        "ok",
    ]
    assert data["schema"] == "kartograf-plan/1" == plan.schema
    assert data["notices"] == [
        {"level": "info", "code": "unit_list", "message": unit_list.message}
    ]
    assert data["ok"] is True
    assert list(data["items"][0]) == [f.name for f in dataclasses.fields(PlanItem)]


def test_plan_ok_is_false_with_check_failed():
    good = _plan(_item(status="missing"), _item(name="b.laz", status="current"))
    failed = _plan(
        _item(), _item(name="b.laz", status="check_failed", error="HTTP 500")
    )

    assert good.ok is True and good.to_dict()["ok"] is True
    assert failed.ok is False and failed.to_dict()["ok"] is False
    assert _plan().ok is True


def test_plan_from_dict_reads_0_8_dev_plans():
    """A plan file written before ``notices`` and ``ok`` existed (``schema`` was
    the last key) still loads; ``ok`` is computed, never read."""
    plan = _plan(_item(), _item(name="b.laz", status="current", local_label="x"))
    old = {
        "store": plan.store,
        "checked_at": plan.checked_at,
        "kartograf_version": plan.kartograf_version,
        "items": [dataclasses.asdict(item) for item in plan.items],
        "schema": "kartograf-plan/1",
    }
    foreign_ok = {**old, "ok": False}

    assert UpdatePlan.from_dict(old) == plan
    assert UpdatePlan.from_dict(foreign_ok) == plan
    assert UpdatePlan.from_dict(foreign_ok).ok is True
    assert UpdatePlan.from_json(json.dumps(old)) == plan


def test_plan_from_dict_rejects_other_schema():
    payload = _plan(_item()).to_dict()
    for schema in ("kartograf-plan/2", "kartograf-availability/1", None):
        broken = {**payload, "schema": schema}
        with pytest.raises(ValidationError, match="schemat"):
            UpdatePlan.from_dict(broken)
    del payload["schema"]
    with pytest.raises(ValidationError, match="schemat"):
        UpdatePlan.from_dict(payload)
    with pytest.raises(ValidationError, match="schemat"):
        UpdatePlan.from_json("[1, 2]")


def test_plan_from_dict_rejects_malformed_notices():
    payload = _plan(_item()).to_dict()
    for notices in (
        [{"level": "info", "code": "x"}],
        [{"level": "info", "code": "x", "message": "zażółć"}],
        "not a list",
        None,
    ):
        with pytest.raises(ValidationError, match="Niekompletny"):
            UpdatePlan.from_dict({**payload, "notices": notices})
    unknown_level = [{"level": "debug", "code": "x", "message": "t"}]
    with pytest.raises(ValidationError, match="Nieznany poziom"):
        UpdatePlan.from_dict({**payload, "notices": unknown_level})


def test_plan_json_round_trip_with_notices():
    notices = (
        Notice("info", "unit_list", "nmt: wojewodztwa obszaru wg PRG (2)\n  12, 24"),
        Notice("warning", "check_failed", "N-34-130-D: HTTP 500"),
    )
    plan = dataclasses.replace(_plan(_item(), _item(track="pl_sheet")), notices=notices)

    again = UpdatePlan.from_json(plan.to_json())

    assert again == plan
    assert again.notices == notices
    assert again.to_json() == plan.to_json()


def test_merge_joins_notices_without_repeats():
    first = Notice("info", "unit_list", "pierwszy")
    shared = Notice("warning", "check_failed", "wspolny")
    last = Notice("info", "sheet_list", "ostatni")
    pl = dataclasses.replace(_plan(_item(track="pl_sheet")), notices=(first, shared))
    cz = dataclasses.replace(_plan(_item(track="cz_cutout")), notices=(shared, last))

    assert pl.merge(cz).notices == (first, shared, last)
    assert cz.merge(pl).notices == (shared, last, first)


def test_merge_keeps_both_and_earliest_check():
    pl = _plan(_item(track="pl_sheet"))
    cz = dataclasses.replace(
        _plan(_item(track="cz_cutout")), checked_at="2026-10-12T07:00:00+00:00"
    )
    merged = pl.merge(cz)
    assert [i.track for i in merged.items] == ["pl_sheet", "cz_cutout"]
    assert merged.checked_at == "2026-10-12T07:00:00+00:00"
    assert merged.items_for("cz_cutout") == cz.items


def test_merge_rejects_other_store():
    with pytest.raises(ValidationError, match="roznych magazynow"):
        _plan(_item()).merge(_plan(_item(), store="/inny"))


def test_require_store_rejects_other_store(tmp_path):
    plan = _plan(_item(), store=store_id(tmp_path))
    require_store(plan, store_id(tmp_path / "." / ""))
    with pytest.raises(ValidationError, match="innego magazynu") as caught:
        require_store(plan, store_id(tmp_path / "b"))
    # the error names the argument like the other errors of a plan do
    assert caught.value.option == "plan"


def test_select_planned_stale_and_removed():
    same = _item(name="same.laz")
    changed = _item(name="changed.laz")
    done = _item(name="done.laz")
    gone = _item(name="gone.laz")
    removed = _item(name="removed.laz")
    other_track = _item(track="cz_cutout", name="same.laz")
    plan = _plan(same, changed, done, gone, other_track)
    fresh = [
        same,
        dataclasses.replace(changed, available_signal={"url": "nowy"}),
        dataclasses.replace(done, status="current", local_label="x"),
        removed,
    ]
    todo, stale = select_planned(plan, fresh, "laz_tile")
    assert [i.name for i in todo] == ["same.laz"]
    assert [i.name for i in stale] == ["changed.laz", "gone.laz"]


def test_select_planned_ignores_positions_not_to_do():
    current = _item(status="current", local_label="x")
    unverifiable = _item(name="b.laz", status="unverifiable")
    todo, stale = select_planned(_plan(current, unverifiable), [], "laz_tile")
    assert (todo, stale) == ([], [])
