"""CLI and public API produce identical versioned stores for every E3 product:
PRG address points of an area, the special boundaries of an area (with the
``Info`` about the census districts), CZ geomorphological units of an area,
the RCN export of a powiat and the CZ cadastral map of one cadastral area
(recorded answers of each test module)."""

import pytest

from kartograf.download import collections as col
from kartograf.download.collections import download_collection
from kartograf.notices import AREA_OMITTED
from tests.parity import assert_notices_printed, assert_same_store, run_both
from tests.test_collections_units import Router
from tests.test_cz_cadastral_map import FILES as KM_FILES
from tests.test_cz_cadastral_map import serve_package
from tests.test_cz_geomorphology import TESIN, serve_celek
from tests.test_prg_addresses import AREA, serve_kin
from tests.test_prg_special import BBOX as SPECIAL_AREA
from tests.test_prg_special import SpecialService
from tests.test_rcn import RECORDED_ZIP
from tests.test_rcn import _session as rcn_session

pytestmark = pytest.mark.usefixtures("frozen_clock")


def _same(run):
    assert run.cli_code == 0, run.cli_stderr
    assert run.api_result.ok, run.api_result.failed
    assert_same_store(run.cli_store, run.api_store)
    assert_notices_printed(run.cli_stderr, run.api_result.notices)
    assert {item.file.status for item in run.api_result.files} == {"new"}


def test_addresses_area(tmp_path, monkeypatch):
    serve_kin(monkeypatch)
    run = run_both(
        [
            "boundaries",
            "download",
            "--product",
            "addresses",
            "--country",
            "pl",
            "--bbox",
            "567100,244150,567150,244200",
        ],
        lambda out: download_collection(
            product="addresses", country="pl", bbox=AREA, output_dir=out
        ),
        tmp_path,
    )
    _same(run)
    assert run.api_result.files[0].file.path.suffix == ".gpkg"


def test_special_area(tmp_path, monkeypatch):
    monkeypatch.setattr(col, "_session", lambda: SpecialService(empty_others=True))
    run = run_both(
        [
            "boundaries",
            "download",
            "--product",
            "special",
            "--country",
            "pl",
            "--bbox=19.93,50.055,19.945,50.065",
            "--bbox-crs",
            "EPSG:4326",
        ],
        lambda out: download_collection(
            product="special", country="pl", bbox=SPECIAL_AREA, output_dir=out
        ),
        tmp_path,
    )
    _same(run)
    assert [n.code for n in run.api_result.notices] == [AREA_OMITTED]


def test_geomorphology_area_level(tmp_path, monkeypatch):
    router = Router()
    serve_celek(router)
    monkeypatch.setattr(col, "_session", lambda: router)
    run = run_both(
        [
            "boundaries",
            "download",
            "--product",
            "geomorphology",
            "--country",
            "cz",
            "--level",
            "celek",
            "--bbox=-452000,-1112000,-450000,-1110000",
            "--bbox-crs",
            "EPSG:5514",
        ],
        lambda out: download_collection(
            product="geomorphology",
            country="cz",
            level="celek",
            bbox=TESIN,
            output_dir=out,
        ),
        tmp_path,
    )
    _same(run)


def test_rcn_powiat_export(tmp_path, monkeypatch):
    session = rcn_session("rcn_1201", RECORDED_ZIP.read_bytes())
    monkeypatch.setattr(col, "_session", lambda: session)
    run = run_both(
        ["cadastre", "download", "--product", "prices", "--teryt", "1201"],
        lambda out: download_collection(product="prices", teryt="1201", output_dir=out),
        tmp_path,
    )
    _same(run)
    assert run.api_result.files[0].file.path.suffix == ".gpkg"


def test_cz_cadastral_map_ku(tmp_path, monkeypatch):
    router = Router()
    serve_package(router, "km_dxf_623164", KM_FILES["km_dxf_623164"]["members"])
    monkeypatch.setattr(col, "_session", lambda: router)
    run = run_both(
        [
            "cadastre",
            "download",
            "--product",
            "map",
            "--ku",
            "623164",
            "--format",
            "DXF",
        ],
        lambda out: download_collection(
            product="map", ku="623164", format="DXF", output_dir=out
        ),
        tmp_path,
    )
    _same(run)
    assert run.api_result.files[0].file.path.suffix == ".zip"
