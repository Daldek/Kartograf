"""Update plan ``kartograf-plan/1`` and sheet upgrade behavior."""

import dataclasses
import json
from unittest.mock import patch

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections
from kartograf.download.collections import check_collection
from kartograf.download.data import check_data
from kartograf.download.manager import DownloadManager
from kartograf.download.plan import PLAN_SCHEMA, UpdatePlan
from kartograf.exceptions import NoCoverageError, ValidationError, YearRangeError
from kartograf.hydrology.hsg import check_hsg
from kartograf.landcover.manager import check_landcover, check_soil
from kartograf.notices import GEOMETRY_LAYER_DEFAULT, UNIT_LIST, Notice
from kartograf.providers.soilgrids import SoilGridsProvider
from tests.conftest import FakeSoilGrids, write_gpkg_layers
from tests.contract.test_parity_landcover import CLAY, _bdot, _providers
from tests.integration.test_collections import AREA, _prg_route
from tests.integration.test_hsg import RasterSoilGrids
from tests.integration.test_landcover_output_params import FakePackages
from tests.integration.test_manager_campaigns import (
    C14,
    REC,
    FakeCampaignProvider,
    G,
    _transport_error,
    c14_fake,
    std_path,
)
from tests.integration.test_nmt_100m import CHOICE as NMT_100M
from tests.integration.test_nmt_100m import KRAKOW, FakeGugik
from tests.support.fake_packages import FakePackageSession

G2 = "N-34-139-C-a-3-2"


def _manager(tmp_path, fake, **kwargs):
    return DownloadManager(provider=fake, root=tmp_path, **kwargs)


def test_check_sheets_plan_equals_old_check(tmp_path):
    fake = FakeCampaignProvider(C14)
    plan = _manager(tmp_path, fake).check_sheets([G])
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


def test_check_current_and_newer(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    _manager(tmp_path, fake).download_sheet(G)
    (current,) = _manager(tmp_path, fake).check_sheets([G]).items
    assert current.status == "current" and current.local_label == "2025-04-27_83233"
    assert current.local_sha256 and len(current.local_sha256) == 64
    fake.records = {"newest": [REC["84183"]]}
    (newer,) = _manager(tmp_path, fake).check_sheets([G]).items
    assert newer.status == "newer" and newer.available_label == "2025-10-21_84183"
    assert newer.local_label == "2025-04-27_83233"
    assert fake.downloads == [REC["83233"].url]


def test_check_failed_item_on_index_error(tmp_path):
    fake = FakeCampaignProvider(C14)
    fake.resolve_error = _transport_error(G, 503)
    (item,) = _manager(tmp_path, fake).check_sheets([G]).items
    assert item.status == "check_failed" and "503" in (item.error or "")


def test_plan_json_round_trip(tmp_path):
    plan = _manager(tmp_path, c14_fake()).check_sheets([G, G2])
    text = plan.to_json()
    assert json.loads(text)["schema"] == PLAN_SCHEMA
    assert UpdatePlan.from_json(text) == plan


def test_plan_from_json_rejects_unknown_schema(tmp_path):
    payload = json.loads(_manager(tmp_path, c14_fake()).check_sheets([G]).to_json())
    payload["schema"] = "kartograf-plan/2"
    with pytest.raises(ValidationError, match="schemat"):
        UpdatePlan.from_json(json.dumps(payload))
    with pytest.raises(ValidationError):
        UpdatePlan.from_json("{")


def test_upgrade_rejects_foreign_store(tmp_path):
    fake = c14_fake()
    plan = _manager(tmp_path / "a", fake).check_sheets([G])
    fake.resolve_calls.clear()
    with pytest.raises(ValidationError, match="innego magazynu"):
        _manager(tmp_path / "b", fake).download_sheets([G], update="upgrade", plan=plan)
    assert fake.resolve_calls == [] and fake.downloads == []


def test_upgrade_executes_missing_and_newer(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    _manager(tmp_path, fake).download_sheet(G)
    fake.records = {"newest": [REC["84183"]]}
    m = _manager(tmp_path, fake)
    plan = m.check_sheets([G])
    report = m.download_sheets([G], update="upgrade", plan=plan)
    assert fake.downloads == [REC["83233"].url, REC["84183"].url]
    (version,) = report.files[G]
    assert version.status == "new" and version.label == "2025-10-21_84183"
    assert report.stale == () and report.failed == []
    # nothing left to do: a second run downloads nothing
    assert (
        m.download_sheets([G], update="upgrade", plan=m.check_sheets([G])).succeeded
        == []
    )


def test_download_sheets_stale_plan_item_reported_not_downloaded(tmp_path):
    fake = c14_fake()
    m = _manager(tmp_path, fake)
    plan = m.check_sheets([G, G2])
    assert [i.status for i in plan.items] == ["missing", "missing"]
    # the source of G changes after the plan: a different newest record
    fake.records = {
        "newest": [r for r in fake.records["newest"] if r.sheet != G] + [REC["83233"]],
        "all": fake.records["all"],
    }
    report = m.download_sheets([G, G2], update="upgrade", plan=plan)
    assert [i.unit for i in report.stale] == [G]
    assert report.succeeded == [std_path(tmp_path, G2)]
    assert all(G2 in url for url in fake.downloads)


def test_download_sheets_upgrade_with_plan_downloads_only_planned(tmp_path):
    fake = c14_fake()
    m = _manager(tmp_path, fake)
    plan = m.check_sheets([G, G2])
    edited = dataclasses.replace(plan, items=plan.items[1:])
    report = m.download_sheets([G, G2], update="upgrade", plan=edited)
    assert report.succeeded == [std_path(tmp_path, G2)]
    assert all(G not in url for url in fake.downloads)


def test_upgrade_all_strategy_only_planned_campaigns(tmp_path):
    fake = FakeCampaignProvider(C14)
    m = _manager(tmp_path, fake, all_campaigns=True)
    plan = m.check_sheets([G])
    assert len(plan.items) == 4
    keep = [i for i in plan.items if i.available_label == "2023-09-05_78047"]
    m.download_sheets(
        [G], update="upgrade", plan=dataclasses.replace(plan, items=tuple(keep))
    )
    assert fake.downloads == [REC["78047"].url]


# --- the plan of a command carries the notices of its call ---------------------


def _geometry(tmp_path):
    """A multi-layer GPKG without ``layer``: ``GEOMETRY_LAYER_DEFAULT``."""
    return write_gpkg_layers(tmp_path / "area.gpkg", ["zlewnia", "inna"])


_ENVELOPE = BBox(770000, 509000, 772000, 511000, "EPSG:2180")


def _plan_of_data(tmp_path, monkeypatch, on_notice):
    monkeypatch.setattr(collections, "_session", lambda: FakeGugik())
    return check_data(
        root=tmp_path, bbox=KRAKOW, country="pl", on_notice=on_notice, **NMT_100M
    )


def _plan_of_collection(tmp_path, monkeypatch, on_notice):
    session = FakePackageSession({})
    session.routes.update([_prg_route()])
    monkeypatch.setattr(collections, "_session", lambda: session)
    return check_collection(
        product="buildings",
        root=tmp_path,
        bbox=AREA,
        country="pl",
        lod=1,
        year=2024,
        cache=False,
        on_notice=on_notice,
    )


def _plan_of_landcover(tmp_path, monkeypatch, on_notice):
    download, teryts = _bdot(["1465"], FakePackages())
    with download, teryts, patch_envelope():
        return check_landcover(
            product="bdot10k",
            root=tmp_path / "store",
            geometry=_geometry(tmp_path),
            cache=False,
            on_notice=on_notice,
        )


def _plan_of_soil(tmp_path, monkeypatch, on_notice):
    soil = _providers(soilgrids=lambda: SoilGridsProvider(session=FakeSoilGrids()))
    with soil, patch_envelope():
        return check_soil(
            root=tmp_path / "store",
            geometry=_geometry(tmp_path),
            cache=False,
            on_notice=on_notice,
            **CLAY,
        )


def _plan_of_hsg(tmp_path, monkeypatch, on_notice):
    with _providers(soilgrids=RasterSoilGrids), patch_envelope():
        return check_hsg(
            root=tmp_path / "store",
            geometry=_geometry(tmp_path),
            depth="0-5cm",
            cache=False,
            on_notice=on_notice,
        )


def patch_envelope():
    """The geometry readers stay out of it: the file only has to name layers."""
    return patch("kartograf.core.geometry.get_overall_bbox", return_value=_ENVELOPE)


@pytest.mark.parametrize(
    ("scenario", "code"),
    [
        (_plan_of_data, UNIT_LIST),
        (_plan_of_collection, UNIT_LIST),
        (_plan_of_landcover, GEOMETRY_LAYER_DEFAULT),
        (_plan_of_soil, GEOMETRY_LAYER_DEFAULT),
        (_plan_of_hsg, GEOMETRY_LAYER_DEFAULT),
    ],
    ids=[
        "check_data",
        "check_collection",
        "check_landcover",
        "check_soil",
        "check_hsg",
    ],
)
def test_check_plan_carries_the_notices_of_the_call(
    tmp_path, monkeypatch, scenario, code
):
    """``on_notice`` is not the only place the messages of a check are: the
    plan has them too (``--json`` prints them), in the order they were emitted."""
    received: list[Notice] = []

    plan = scenario(tmp_path, monkeypatch, received.append)

    assert code in [notice.code for notice in received]
    assert plan.notices == tuple(received)


# --- the check of sheets without data: a state of the data, as in the download ---

NO_DATA = "N-34-139-C-a-1-1"  # no record in the C14 fixtures


def test_check_sheets_without_data_are_no_positions_and_not_a_failed_check(tmp_path):
    seen: list[tuple[list[str], int]] = []
    plan = _manager(tmp_path, c14_fake()).check_sheets(
        [G, NO_DATA],
        on_no_coverage=lambda missing, total: seen.append((sorted(missing), total)),
    )
    assert plan.ok and [item.unit for item in plan.items] == [G]
    assert seen == [([NO_DATA], 2)]


def test_check_sheets_of_one_sheet_without_data_raises_its_own_error(tmp_path):
    with pytest.raises(NoCoverageError, match=NO_DATA):
        _manager(tmp_path, c14_fake()).check_sheets([NO_DATA])


def test_check_sheets_without_any_data_fails_like_the_download(tmp_path):
    with pytest.raises(NoCoverageError) as caught:
        _manager(tmp_path, c14_fake()).check_sheets([NO_DATA, "N-34-139-C-a-1-2"])
    assert str(caught.value) == "GUGiK nie ma danych dla zadnego z 2 arkuszy obszaru"


def test_check_sheets_year_conflicts_are_one_error_for_all_the_sheets(tmp_path):
    sheets = [f"N-34-139-C-a-3-{i}" for i in range(1, 5)]
    manager = _manager(tmp_path, c14_fake(), min_year=2026)
    with pytest.raises(YearRangeError) as caught:
        manager.check_sheets([*sheets, NO_DATA])
    assert set(caught.value.sheets) == {G, "N-34-139-C-a-3-3"}
    assert "dla 2 z 5 arkuszy" in str(caught.value)
