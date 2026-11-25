"""Where the files of a plan come from (ADR-063 decisions 3 and 4).

Every position names its source and either the URL whose bytes the file is, unchanged
(``fetch``), or why no URL serves it (``fetch_reason``), from what the check reads and
no request more; a detached plan is the plain write into ``.``. The tracks talk to the
fakes and recorded answers of their own tests.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf import check_command
from kartograf.download.cz_sheets import _check_sheet
from kartograf.download.laz import check_laz_area
from kartograf.download.manager import DownloadManager
from kartograf.download.plan import DETACHED, Fetch
from kartograf.exceptions import ValidationError
from kartograf.providers.pl.gugik_laz import GugikLazProvider
from tests.integration.test_cz_sheets import SheetProvider
from tests.integration.test_laz_download import W2_AREA, wfs_session
from tests.integration.test_manager_campaigns import (
    C14,
    REC,
    FakeCampaignProvider,
    G,
    _transport_error,
)
from tests.integration.test_orto_cutout import KRAKOW, SESSION_FACTORY

LAZ = {"vertical_crs": "EVRF2007", "min_density": 4, "cache": False}
ORTO_CUTOUT = {
    "product": "orto",
    "country": "pl",
    "bbox": [KRAKOW.min_x, KRAKOW.min_y, KRAKOW.max_x, KRAKOW.max_y],
    "bbox_crs": "EPSG:2180",
    "cutout": True,
    "horizontal_crs": "EPSG:2180",
    "coverage": "standard",
    "resolution": "0.25m",
}


def test_a_sheet_is_the_url_of_its_index_record_and_names_its_source(tmp_path):
    plan = DownloadManager(
        provider=FakeCampaignProvider(C14), root=tmp_path
    ).check_sheets([G])

    (item,) = plan.items
    assert (item.source, item.fetch, item.fetch_reason) == (
        "pl.gugik.nmt_1m",
        Fetch(REC["84183"].url),
        None,
    )
    assert [source.key for source in plan.sources] == ["pl.gugik.nmt_1m"]
    assert plan.sources[0].auth == "none" and plan.sources[0].provider == "GUGiK"


def test_a_sheet_whose_index_failed_has_a_fetch_without_url(tmp_path):
    fake = FakeCampaignProvider(C14)
    fake.resolve_error = _transport_error(G, 503)

    (item,) = DownloadManager(provider=fake, root=tmp_path).check_sheets([G]).items

    assert item.status == "check_failed"
    assert (item.source, item.fetch, item.fetch_reason) == (
        "pl.gugik.nmt_1m",
        Fetch(None),
        None,
    )


@pytest.mark.parametrize("plain", [False, True], ids=["store", "plain"])
def test_a_laz_tile_is_its_opendata_url_in_store_and_plain_plans(tmp_path, plain):
    target = {"output_dir": tmp_path / "out"} if plain else {"root": tmp_path}
    provider = GugikLazProvider(session=wfs_session(), vertical_crs="EVRF2007")

    plan = check_laz_area(bbox=W2_AREA, provider=provider, **target, **LAZ)

    (item,) = plan.items
    assert item.source == "pl.gugik.laz" and item.fetch_reason is None
    assert item.fetch is not None and item.fetch.size_bytes is None
    assert item.fetch.url is not None and item.fetch.url.endswith(".laz")
    signal = item.available_signal or {"url": item.fetch.url}  # plain: no signal
    assert signal["url"] == item.fetch.url
    assert (item.action == "write") is plain


def test_a_cz_sheet_is_built_even_when_its_probe_answers(tmp_path):
    provider = SheetProvider()

    (item,) = _check_sheet(provider, "CTES96", root=tmp_path).items

    assert (item.source, item.fetch, item.fetch_reason) == (
        "cz.cuzk.dmr4g",
        None,
        "built",
    )
    assert provider.heads == 1  # the freshness signal, not a size


# --- detached plans (ADR-063 decision 4) -----------------------------------------


@pytest.mark.parametrize("option", ["output_dir", "root"])
def test_a_detached_plan_refuses_a_target(tmp_path, option):
    with pytest.raises(ValidationError) as caught:
        check_command(
            "imagery download",
            ORTO_CUTOUT,
            detached=True,
            cache=False,
            **{option: tmp_path},
        )

    assert caught.value.option == option
    assert caught.value.reason == "exclusive_options"
    assert list(tmp_path.iterdir()) == []


def test_a_detached_plan_is_the_plain_write_into_dot(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr("tempfile.tempdir", None)

    with patch(SESSION_FACTORY) as factory:
        result = check_command(
            "imagery download", ORTO_CUTOUT, detached=True, cache=False
        )

    factory.assert_not_called()
    plan = result.result
    assert plan is not None
    data = result.to_dict()["result"]
    assert isinstance(data, dict)
    (item,) = data["items"]
    assert (data["mode"], data["root"], data["output_dir"]) == ("plain", None, DETACHED)
    assert (item["action"], item["status"]) == ("write", "missing")
    assert item["path"] == item["name"] and not Path(item["path"]).is_absolute()
    assert (item["source"], item["fetch"], item["fetch_reason"]) == (
        "pl.gugik.orto",
        None,
        "built",
    )
    assert list(tmp_path.iterdir()) == []  # the directory of the plan never existed


def test_a_detached_plan_refuses_what_a_plain_write_refuses():
    options = {
        "product": "nmt",
        "sheet": G,
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "all_campaigns": True,
    }

    with pytest.raises(ValidationError) as caught:
        check_command("elevation download", options, detached=True, cache=False)

    assert caught.value.reason == "store_only_option"
