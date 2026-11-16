"""CLI and public API produce identical versioned stores for every E2 product."""

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import download_collection
from tests.integration.test_collections_units import (
    CUZK,
    FILES,
    INDEX,
    MAPS_GFI,
    Response,
    Router,
    _key,
    file_answer,
    head_of,
    recorded,
)
from tests.integration.test_names import (
    COLLECTIONS,
    CZ_BBOX,
    WORLD,
    _geonames_first_layer,
    _geonames_session,
    _prng_page_size,
)
from tests.support.fake_packages import zip_bytes
from tests.support.parity import assert_notices_printed, assert_same_store, run_both
from tests.unit.test_feature_bbox import FakeService, prng

pytestmark = pytest.mark.usefixtures("frozen_clock")


def _same(run):
    assert run.cli_code == 0, run.cli_stderr
    assert run.api_result.ok, run.api_result.failed
    assert_same_store(run.cli_store, run.api_store)
    assert_notices_printed(run.cli_stderr, run.api_result.notices)
    assert {item.file.status for item in run.api_result.files} == {"new"}


def test_prng_rp_two_pages(tmp_path, monkeypatch):
    _prng_page_size(monkeypatch, 5)
    monkeypatch.setattr(col, "_session", lambda: FakeService(prng()))
    area = BBox(19.93, 50.055, 19.945, 50.065, "EPSG:4326")
    run = run_both(
        [
            "names",
            "download",
            "--product",
            "geographic",
            "--country",
            "pl",
            "--bbox=19.93,50.055,19.945,50.065",
            "--bbox-crs",
            "EPSG:4326",
        ],
        lambda out: download_collection(
            product="geographic", country="pl", bbox=area, root=out
        ),
        tmp_path,
    )
    _same(run)
    assert run.api_result.files[0].file.path.suffix == ".gpkg"


def test_prng_world_outside_europe(tmp_path, monkeypatch):
    session = Router()
    url = "https://ogcapi.geoportal.gov.pl/res/ims/maps/PRNG/apiFeatures"
    session.add(
        f"{url}/collections",
        lambda: Response(
            200, {"Content-Type": "application/json"}, COLLECTIONS.read_bytes()
        ),
        {"f": "json"},
    )
    session.add(
        f"{url}/collections/PolskaNazwaGeograficznaSwiata/items",
        lambda: Response(200, {"Content-Type": "application/json"}, WORLD.read_bytes()),
        {"f": "json", "bbox": "-74.02,40.69,-73.92,40.79", "limit": "10000"},
    )
    monkeypatch.setattr(col, "_session", lambda: session)
    run = run_both(
        [
            "names",
            "download",
            "--product",
            "world",
            "--country",
            "pl",
            "--bbox=-74.02,40.69,-73.92,40.79",
            "--bbox-crs",
            "EPSG:4326",
        ],
        lambda out: download_collection(
            product="world",
            country="pl",
            bbox=BBox(-74.02, 40.69, -73.92, 40.79, "EPSG:4326"),
            root=out,
        ),
        tmp_path,
    )
    _same(run)


def test_geonames_cz_bbox(tmp_path, monkeypatch):
    _geonames_first_layer(monkeypatch)
    monkeypatch.setattr(col, "_session", _geonames_session)
    run = run_both(
        [
            "names",
            "download",
            "--product",
            "geographic",
            "--country",
            "cz",
            "--bbox=-452000,-1112000,-450000,-1110000",
            "--bbox-crs",
            "EPSG:5514",
        ],
        lambda out: download_collection(
            product="geographic",
            country="cz",
            bbox=CZ_BBOX,
            root=out,
        ),
        tmp_path,
    )
    _same(run)


def test_bdot10k_map_tiff(tmp_path, monkeypatch):
    router = Router()
    router.add_prefix(
        f"{MAPS_GFI}?", lambda: recorded(INDEX / "gfi_mapy10k_M-34-64-D-d-1.html")
    )
    key = "map10k_tiff"
    router.add(FILES[key]["url"], file_answer(key, head_of(key)))
    monkeypatch.setattr(col, "_session", lambda: router)
    run = run_both(
        [
            "maps",
            "download",
            "--product",
            "topographic",
            "--country",
            "pl",
            "--sheet",
            "M-34-064-D-d-1",
            "--scale",
            "1:10000",
            "--format",
            "TIFF",
        ],
        lambda out: download_collection(
            product="topographic",
            sheet="M-34-064-D-d-1",
            scale="1:10000",
            format="TIFF",
            root=out,
        ),
        tmp_path,
    )
    _same(run)
    assert run.api_result.files[0].file.path.suffix == ".tif"


def test_ztm_sjtsk_tiff_from_sheet(tmp_path, monkeypatch):
    router = Router()
    router.add_recorded(CUZK / "klady_2_where_0510-D-11.json")
    entry = FILES["cz_ztm10_tiff_0510-D-11"]
    body = zip_bytes(["0510D11.tif", "0510D11.tfw"])
    router.add(
        entry["url"],
        lambda: Response(
            200, {**entry["headers"], "Content-Length": str(len(body))}, body
        ),
    )
    router.heads[_key(entry["url"])] = entry["headers"]
    monkeypatch.setattr(col, "_session", lambda: router)
    run = run_both(
        [
            "maps",
            "download",
            "--product",
            "topographic",
            "--country",
            "cz",
            "--sheet",
            "0510-D-11",
            "--scale",
            "1:10000",
            "--format",
            "TIFF",
        ],
        lambda out: download_collection(
            product="topographic",
            country="cz",
            sheet="0510-D-11",
            scale="1:10000",
            format="TIFF",
            root=out,
        ),
        tmp_path,
    )
    _same(run)
    assert run.api_result.files[0].file.path.suffix == ".zip"
