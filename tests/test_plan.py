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


def test_plan_round_trip_all_tracks():
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


def test_require_store_rejects_other_store_and_schema(tmp_path):
    plan = _plan(_item(), store=store_id(tmp_path))
    require_store(plan, store_id(tmp_path / "." / ""))
    with pytest.raises(ValidationError, match="innego magazynu"):
        require_store(plan, store_id(tmp_path / "b"))
    with pytest.raises(ValidationError, match="schemat"):
        require_store(dataclasses.replace(plan, schema="kartograf-plan/2"), plan.store)


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
