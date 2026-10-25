"""CLI and public API produce identical versioned stores for every E5 product:
mesh tiles of an area, the trees package of a powiat, the points of a PL
and of a CZ network of an area and both national quasi-geoid models
(recorded answers of ``tests/integration/test_mesh_trees.py`` and
``tests/integration/test_geodesy.py``)."""

import functools

import pytest

from kartograf.download import collections as col
from kartograf.download.collections import download_collection
from kartograf.notices import DOWNLOAD_SIZE, WHOLE_COUNTRY_SIZE
from tests.integration.test_collections_units import MESH_AREA, Response, Router, _key
from tests.integration.test_geodesy import (
    GEOID,
    GEOID_FILE,
    PL_AREAS,
    PRPOG,
    QGZU_FILE,
    SURVEY,
    TESIN,
    _recorded_page_size,
    _serve_qgzu,
    _serve_recordings,
)
from tests.integration.test_mesh_trees import (
    TREES_FILES,
    _serve_pages,
    _serve_tiles,
    _zip_answer,
)
from tests.support.fake_packages import zip_bytes
from tests.support.parity import assert_notices_printed, assert_same_store, run_both

pytestmark = pytest.mark.usefixtures("frozen_clock")


@pytest.fixture
def router(monkeypatch) -> Router:
    fake = Router()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _same(run):
    assert run.cli_code == 0, run.cli_stderr
    assert run.api_result.ok, run.api_result.failed
    assert_same_store(run.cli_store, run.api_store)
    assert_notices_printed(run.cli_stderr, run.api_result.notices)
    assert {item.file.status for item in run.api_result.files} == {"new"}


def test_mesh_tiles_of_an_area(tmp_path, router, monkeypatch):
    _serve_pages(router, monkeypatch)
    _serve_tiles(router)
    run = run_both(
        [
            "models3d",
            "download",
            "--product",
            "mesh",
            "--country",
            "pl",
            "--bbox",
            "566100,244500,566300,244700",
        ],
        lambda out: download_collection(
            product="mesh", country="pl", bbox=MESH_AREA, root=out
        ),
        tmp_path,
    )
    _same(run)
    assert len(run.api_result.files) == 4


def test_trees_package_of_a_powiat(tmp_path, router):
    entry = TREES_FILES["trees_3063"]
    router.add(
        entry["url"], functools.partial(_zip_answer, zip_bytes(entry["members"]))
    )
    router.heads[_key(entry["url"])] = entry["headers"]
    run = run_both(
        ["models3d", "download", "--product", "trees", "--teryt", "3063"],
        lambda out: download_collection(product="trees", teryt="3063", root=out),
        tmp_path,
    )
    _same(run)
    assert [n.code for n in run.api_result.notices] == [DOWNLOAD_SIZE]


def test_pl_control_network_of_an_area(tmp_path, router, monkeypatch):
    _recorded_page_size(monkeypatch)
    _serve_recordings(router, PRPOG)
    run = run_both(
        [
            "geodesy",
            "download",
            "--product",
            "control",
            "--country",
            "pl",
            "--network",
            "vertical",
            "--bbox",
            "567600,240600,568300,241200",
        ],
        lambda out: download_collection(
            product="control",
            country="pl",
            network="vertical",
            bbox=PL_AREAS["vertical"],
            root=out,
        ),
        tmp_path,
    )
    _same(run)
    assert run.api_result.files[0].file.path.suffix == ".gpkg"


def test_cz_control_network_of_an_area(tmp_path, router):
    _serve_recordings(router, SURVEY)
    run = run_both(
        [
            "geodesy",
            "download",
            "--product",
            "control",
            "--country",
            "cz",
            "--network",
            "vertical",
            "--bbox=-452000,-1113000,-449000,-1110000",
            "--bbox-crs",
            "EPSG:5514",
        ],
        lambda out: download_collection(
            product="control",
            country="cz",
            network="vertical",
            bbox=TESIN,
            root=out,
        ),
        tmp_path,
    )
    _same(run)


def test_pl_quasigeoid_model(tmp_path, router):
    text = (GEOID / GEOID_FILE["head"]).read_bytes()
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Length": str(len(text)),
    }
    router.add(GEOID_FILE["url"], lambda: Response(200, headers, text))
    router.heads[_key(GEOID_FILE["url"])] = GEOID_FILE["headers"]
    run = run_both(
        [
            "geodesy",
            "download",
            "--product",
            "geoid",
            "--country",
            "pl",
            "--whole-country",
        ],
        lambda out: download_collection(
            product="geoid", country="pl", whole_country=True, root=out
        ),
        tmp_path,
    )
    _same(run)
    assert [n.code for n in run.api_result.notices] == [WHOLE_COUNTRY_SIZE]


def test_cz_quasigeoid_model(tmp_path, router):
    _serve_qgzu(router, zip_bytes(QGZU_FILE["members"]))
    run = run_both(
        [
            "geodesy",
            "download",
            "--product",
            "geoid",
            "--country",
            "cz",
            "--whole-country",
        ],
        lambda out: download_collection(
            product="geoid", country="cz", whole_country=True, root=out
        ),
        tmp_path,
    )
    _same(run)
    assert run.api_result.files[0].file.label == "2021-02-22"
