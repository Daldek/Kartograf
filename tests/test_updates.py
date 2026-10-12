"""Update plan ``kartograf-plan/1``: check_updates / upgrade (spec 4.4)."""

import dataclasses
import json

import pytest

from kartograf.download.manager import DownloadManager
from kartograf.download.plan import PLAN_SCHEMA, UpdatePlan
from kartograf.download.updates import check_updates, upgrade
from kartograf.exceptions import ValidationError
from tests.test_manager_campaigns import (
    C14,
    REC,
    FakeCampaignProvider,
    G,
    _transport_error,
    c14_fake,
)

G2 = "N-34-139-C-a-3-2"


def _manager(tmp_path, fake, **kwargs):
    return DownloadManager(tmp_path, provider=fake, **kwargs)


def test_check_updates_downloads_nothing_and_reports_missing(tmp_path):
    fake = FakeCampaignProvider(C14)
    plan = check_updates(_manager(tmp_path, fake), [G])
    assert fake.downloads == []
    (item,) = plan.items
    assert item.status == "missing" and item.available_label == "2025-10-21_84183"
    assert item.track == "pl_sheet" and item.unit == G
    assert item.segment == "nmt/pl_1992_1m_evrf2007"
    assert item.hierarchy == "N-34/139/C/a/3/1" and item.name == f"{G}.asc"
    assert item.available_signal == {
        "url": REC["84183"].url,
        "date": "2025-10-21",
        "pzgik_date": REC["84183"].dt_pzgik,
    }
    assert plan.store == str(tmp_path.resolve()) and plan.schema == PLAN_SCHEMA


def test_check_updates_current_and_newer(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    _manager(tmp_path, fake).download_sheet(G)
    (current,) = check_updates(_manager(tmp_path, fake), [G]).items
    assert current.status == "current" and current.local_label == "2025-04-27_83233"
    assert current.local_sha256 and len(current.local_sha256) == 64
    fake.records = {"newest": [REC["84183"]]}
    (newer,) = check_updates(_manager(tmp_path, fake), [G]).items
    assert newer.status == "newer" and newer.available_label == "2025-10-21_84183"
    assert newer.local_label == "2025-04-27_83233"
    assert fake.downloads == [REC["83233"].url]


def test_check_failed_item_on_index_error(tmp_path):
    fake = FakeCampaignProvider(C14)
    fake.resolve_error = _transport_error(G, 503)
    (item,) = check_updates(_manager(tmp_path, fake), [G]).items
    assert item.status == "check_failed" and "503" in (item.error or "")


def test_plan_json_round_trip(tmp_path):
    plan = check_updates(_manager(tmp_path, c14_fake()), [G, G2])
    text = plan.to_json()
    assert json.loads(text)["schema"] == PLAN_SCHEMA
    assert UpdatePlan.from_json(text) == plan


def test_plan_from_json_rejects_unknown_schema(tmp_path):
    payload = json.loads(check_updates(_manager(tmp_path, c14_fake()), [G]).to_json())
    payload["schema"] = "kartograf-plan/2"
    with pytest.raises(ValidationError, match="schemat"):
        UpdatePlan.from_json(json.dumps(payload))
    with pytest.raises(ValidationError):
        UpdatePlan.from_json("{")


def test_upgrade_rejects_foreign_store(tmp_path):
    fake = c14_fake()
    plan = check_updates(_manager(tmp_path / "a", fake), [G])
    fake.resolve_calls.clear()
    with pytest.raises(ValidationError, match="innego magazynu"):
        upgrade(_manager(tmp_path / "b", fake), plan)
    assert fake.resolve_calls == [] and fake.downloads == []


def test_upgrade_executes_missing_and_newer(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    _manager(tmp_path, fake).download_sheet(G)
    fake.records = {"newest": [REC["84183"]]}
    m = _manager(tmp_path, fake)
    plan = check_updates(m, [G])
    report = upgrade(m, plan)
    assert fake.downloads == [REC["83233"].url, REC["84183"].url]
    (fetch,) = report.done
    assert fetch.status == "new" and fetch.version == "2025-10-21_84183"
    assert report.stale == () and report.failed == {}
    # nothing left to do: a second run downloads nothing
    assert upgrade(m, check_updates(m, [G])).done == ()


def test_upgrade_stale_item_fails_others_run(tmp_path):
    fake = c14_fake()
    m = _manager(tmp_path, fake)
    plan = check_updates(m, [G, G2])
    assert [i.status for i in plan.items] == ["missing", "missing"]
    # the source of G changes after the plan: a different newest record
    fake.records = {
        "newest": [r for r in fake.records["newest"] if r.sheet != G] + [REC["83233"]],
        "all": fake.records["all"],
    }
    report = upgrade(m, plan)
    assert [i.unit for i in report.stale] == [G]
    assert [f.sheet for f in report.done] == [G2]
    assert all(G2 in url for url in fake.downloads)


def test_upgrade_skips_items_removed_from_plan(tmp_path):
    fake = c14_fake()
    m = _manager(tmp_path, fake)
    plan = check_updates(m, [G, G2])
    edited = dataclasses.replace(plan, items=plan.items[1:])
    report = upgrade(m, edited)
    assert [f.sheet for f in report.done] == [G2]
    assert all(G not in url for url in fake.downloads)


def test_upgrade_all_strategy_only_planned_campaigns(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = _manager(tmp_path, fake, all_campaigns=True)
    plan = check_updates(m, [G])
    assert len(plan.items) == 4
    keep = [i for i in plan.items if i.available_label == "2023-09-05_78047"]
    upgrade(m, dataclasses.replace(plan, items=tuple(keep)))
    assert fake.downloads == [REC["78047"].url]
