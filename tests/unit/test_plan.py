"""Update plan types shared by every track (kartograf.download.plan)."""

import dataclasses
import json

import pytest

from kartograf.download.plan import (
    DETACHED,
    TRACKS,
    ArchiveMember,
    Fetch,
    PlanItem,
    PlanSource,
    UpdatePlan,
    detached_directory,
    detached_plan,
    fetch_fields,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.exceptions import ValidationError
from kartograf.notices import Notice
from kartograf.output import Staging
from kartograf.sources.registry import get_source


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


def _plan(*items: PlanItem, root="/magazyn") -> UpdatePlan:
    return UpdatePlan(root, "2026-10-12T08:00:00+00:00", "0.8.0", tuple(items))


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
    with pytest.raises(ValidationError, match="Incomplete update plan"):
        UpdatePlan.from_json(json.dumps(payload))


def test_plan_to_dict_schema_first():
    unit_list = Notice("info", "unit_list", "nmt: wojewodztwa obszaru wg PRG (1): 12")
    plan = dataclasses.replace(_plan(_item()), notices=(unit_list,))

    data = plan.to_dict()

    assert list(data) == [
        "schema",
        "mode",
        "root",
        "output_dir",
        "checked_at",
        "kartograf_version",
        "items",
        "notices",
        "ok",
        "sources",
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


def test_plan_from_dict_reads_a_plan_without_notices_and_ok():
    """A plan file without ``notices`` and ``ok`` (``schema`` last) still loads;
    ``ok`` is computed, never read."""
    plan = _plan(_item(), _item(name="b.laz", status="current", local_label="x"))
    old = {
        "root": plan.root,
        "output_dir": None,
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
        with pytest.raises(ValidationError, match="schema"):
            UpdatePlan.from_dict(broken)
    del payload["schema"]
    with pytest.raises(ValidationError, match="schema"):
        UpdatePlan.from_dict(payload)
    with pytest.raises(ValidationError, match="schema"):
        UpdatePlan.from_json("[1, 2]")


def test_plan_from_dict_rejects_malformed_notices():
    payload = _plan(_item()).to_dict()
    for notices in (
        [{"level": "info", "code": "x"}],
        [{"level": "info", "code": "x", "message": "zażółć"}],
        "not a list",
        None,
    ):
        with pytest.raises(ValidationError, match="Incomplete update plan"):
            UpdatePlan.from_dict({**payload, "notices": notices})
    unknown_level = [{"level": "debug", "code": "x", "message": "t"}]
    with pytest.raises(ValidationError, match="Unknown plan notice level"):
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
    with pytest.raises(ValidationError, match="different stores"):
        _plan(_item()).merge(_plan(_item(), root="/inny"))


def test_require_store_rejects_other_store(tmp_path):
    plan = _plan(_item(), root=store_id(tmp_path))
    require_store(plan, store_id(tmp_path / "." / ""))
    with pytest.raises(ValidationError, match="different store") as caught:
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


def test_a_plan_of_a_plain_write_names_its_directory_and_the_action_of_each_target(
    tmp_path,
):
    item = _item(
        segment="",
        hierarchy="",
        status="unverifiable",
        action="conflict",
        path=tmp_path / "a.laz",
        reason="output_exists",
    )
    plan = UpdatePlan(
        None,
        "2026-10-12T08:00:00+00:00",
        "0.8.0",
        (item,),
        output_dir=store_id(tmp_path),
    )

    data = plan.to_dict()

    assert (data["mode"], data["root"], data["output_dir"]) == (
        "plain",
        None,
        store_id(tmp_path),
    )
    assert data["items"][0]["action"] == "conflict"
    assert data["items"][0]["reason"] == "output_exists"
    assert item.store_path == "a.laz"
    assert UpdatePlan.from_dict(data) == plan
    assert _plan().mode == "store"


def test_a_plan_of_0_8_dev_with_the_key_store_is_not_read():
    old = {**_plan(_item()).to_dict(), "store": "/magazyn"}
    del old["root"]

    with pytest.raises(ValidationError, match="make a new plan") as caught:
        UpdatePlan.from_dict(old)

    assert caught.value.option == "plan"


def test_plans_of_a_store_and_of_a_directory_do_not_merge(tmp_path):
    plain = UpdatePlan(
        None, "2026-10-12T08:00:00+00:00", "0.8.0", (), output_dir=store_id(tmp_path)
    )

    with pytest.raises(ValidationError, match="different stores"):
        _plan(_item()).merge(plain)


# --- where the files come from (ADR-063 decision 3) ----------------------------

NMT = "pl.gugik.nmt_1m"
LAZ = "pl.gugik.laz"
CORINE = "eu.clms.corine"


def test_new_plan_lists_each_source_once_in_the_order_of_its_first_position(
    tmp_path,
):
    items = [
        _item(name="a.laz", source=LAZ),
        _item(name="b.asc", source=NMT),
        _item(name="c.laz", source=LAZ),
        _item(track="store", name="root", source=None),
    ]

    plan = new_plan(tmp_path, items)

    assert [source.key for source in plan.sources] == [LAZ, NMT]
    nmt = get_source(NMT)
    assert plan.sources[1] == PlanSource(NMT, nmt.provider_name, nmt.license, nmt.auth)
    assert plan.to_dict()["sources"][1] == {
        "key": NMT,
        "provider": "GUGiK",
        "license": {
            "id": nmt.license.id,
            "attribution": nmt.license.attribution,
            "url": nmt.license.url,
        },
        "auth": "none",
    }


def test_merge_joins_the_sources_of_both_plans_without_repeats(tmp_path):
    pl = new_plan(tmp_path, [_item(source=NMT), _item(name="b.laz", source=LAZ)])
    cz = new_plan(tmp_path, [_item(name="c.laz", source=LAZ), _item(source=CORINE)])

    assert [s.key for s in pl.merge(cz).sources] == [NMT, LAZ, CORINE]
    assert [s.key for s in cz.merge(pl).sources] == [LAZ, CORINE, NMT]


def test_plan_round_trip_keeps_the_source_and_the_fetch_of_each_position(tmp_path):
    fetched = _item(
        source=LAZ, fetch=Fetch("https://example.test/a.laz", 1024, "ab" * 32)
    )
    built = _item(name="b.tif", source=NMT, fetch_reason="built")
    keyed = _item(name="c.tif", source=CORINE, fetch_reason="credentials")
    member = _item(
        name="d.gpkg",
        source=NMT,
        fetch_reason="built",
        archive=ArchiveMember(
            "https://example.test/r.zip", 4096, "r/d.gpkg", "cd" * 32
        ),
    )
    unnamed = _item(
        name="e.zip", source=NMT, fetch=Fetch(None), fetch_reason="feed_not_cached"
    )
    plan = new_plan(tmp_path, [fetched, built, keyed, member, unnamed])

    again = UpdatePlan.from_json(plan.to_json())

    assert again == plan
    assert again.items[0].fetch == Fetch("https://example.test/a.laz", 1024, "ab" * 32)
    assert [item.fetch_reason for item in again.items] == [
        None,
        "built",
        "credentials",
        "built",
        "feed_not_cached",
    ]
    assert [s.key for s in again.sources] == [LAZ, NMT, CORINE]
    items = json.loads(plan.to_json())["items"]
    assert items[0]["fetch"] == {
        "url": "https://example.test/a.laz",
        "size_bytes": 1024,
        "sha256": "ab" * 32,
    }
    assert items[3]["archive"] == {
        "url": "https://example.test/r.zip",
        "size_bytes": 4096,
        "member": "r/d.gpkg",
        "sha256": "cd" * 32,
    }
    assert items[4]["fetch"] == {"url": None, "size_bytes": None, "sha256": None}


def test_a_plan_of_0_9_0_without_sources_and_fetch_still_loads():
    """A plan written by 0.9.0: no ``sources``, no ``source``, ``fetch``,
    ``fetch_reason`` or ``archive`` in its positions."""
    plan = _plan(_item(), _item(name="b.laz", status="current", local_label="x"))
    old = plan.to_dict()
    del old["sources"]
    for item in old["items"]:  # type: ignore[attr-defined]
        for key in ("source", "fetch", "fetch_reason", "archive"):
            del item[key]

    loaded = UpdatePlan.from_dict(old)

    assert loaded == plan
    assert loaded.sources == ()
    assert {(i.source, i.fetch, i.fetch_reason, i.archive) for i in loaded.items} == {
        (None, None, None, None)
    }


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("fetch_reason", "proxy", "Unknown plan item fetch_reason 'proxy'"),
        ("fetch", {"url": "https://example.test/a"}, "Incomplete update plan"),
        (
            "fetch",
            {"url": None, "size_bytes": "10", "sha256": None},
            "Incomplete update plan",
        ),
        (
            "archive",
            {
                "url": "https://example.test/r.zip",
                "size_bytes": "10",
                "member": "m",
                "sha256": "ab",
            },
            "Incomplete update plan",
        ),
    ],
)
def test_a_malformed_fetch_of_a_position_is_validation_error(field, value, match):
    payload = json.loads(_plan(_item()).to_json())
    payload["items"][0][field] = value

    with pytest.raises(ValidationError, match=match):
        UpdatePlan.from_dict(payload)


def test_a_source_without_a_licence_is_validation_error():
    payload = json.loads(_plan(_item()).to_json())
    payload["sources"] = [{"key": NMT, "provider": "GUGiK", "auth": "none"}]

    with pytest.raises(ValidationError, match="Incomplete update plan"):
        UpdatePlan.from_dict(payload)


def test_fetch_fields_name_the_key_exchange_before_anything_the_track_says():
    url = Fetch("https://example.test/a.tif")

    assert fetch_fields(LAZ, url) == (url, None)
    assert fetch_fields(NMT, None) == (None, "built")
    assert fetch_fields(CORINE, url) == (None, "credentials")
    assert fetch_fields(CORINE, None) == (None, "credentials")
    assert fetch_fields(None, url) == (None, None)


def test_detached_plan_is_the_write_into_dot_with_relative_posix_paths():
    directory = detached_directory()
    with Staging(directory) as write:
        plan = new_plan(
            write.handle,
            [
                _item(name="N-34-130-D-d-2-4.asc", source=NMT),
                _item(name="teryt/1465.zip", source=LAZ),
                _item(name="c.asc", status="check_failed", error="HTTP 503"),
            ],
        )

    detached = detached_plan(plan, directory)
    data = detached.to_dict()

    assert not directory.exists()
    assert (data["mode"], data["root"], data["output_dir"]) == ("plain", None, DETACHED)
    assert [i["path"] for i in data["items"]] == [
        "N-34-130-D-d-2-4.asc",
        "teryt/1465.zip",
        None,
    ]
    assert [i["action"] for i in data["items"]] == ["write", "write", None]
    assert UpdatePlan.from_dict(data).to_dict() == data
