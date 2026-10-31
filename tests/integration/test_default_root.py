"""A call that names no store works on the default store (DEV-19.2, ADR-054)."""

import json

from kartograf.cli import main
from kartograf.download.manager import DownloadManager
from kartograf.landcover.manager import LandCoverManager
from kartograf.testing import build_fixture_store
from tests.integration.test_hsg import RasterSoilGrids
from tests.integration.test_manager_campaigns import G, c14_fake
from tests.integration.test_mcp_server import call, error_of, needs_mcp
from tests.support.data_fixtures import HSG_SHEET, landcover_sources


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_the_library_writes_the_default_store_without_a_root(monkeypatch, tmp_path):
    store = tmp_path / "default-store"
    monkeypatch.setenv("KARTOGRAF_ROOT", str(store))

    result = DownloadManager(provider=c14_fake()).download_sheet(G)

    assert result.succeeded
    assert all(path.is_relative_to(store) for path in result.succeeded)


def test_the_managers_without_a_root_keep_their_directory_until_a_write(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path / "default-store"))

    LandCoverManager("bdot10k")

    assert not (tmp_path / "default-store").exists()


def test_the_store_commands_read_the_default_store_without_a_root(
    capsys, monkeypatch, tmp_path
):
    store = build_fixture_store(tmp_path / "default-store").root
    monkeypatch.setenv("KARTOGRAF_ROOT", str(store))

    code, out, err = run(capsys, "store", "overview", "--json")

    assert (code, err) == (0, "")
    assert json.loads(out)["result"]["root"] == str(store)


@needs_mcp
def test_an_mcp_call_without_a_root_needs_the_default_store_inside_allow_dir(
    monkeypatch, tmp_path
):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    monkeypatch.setenv("KARTOGRAF_ROOT", str(outside))
    refused = call("kartograf_store_overview", {}, allow_dirs=[allowed])
    report = error_of(refused, code="forbidden")
    assert report["details"]["option"] == "root"
    assert report["details"]["reason"] == "outside_allowed_dirs"
    assert report["details"]["path"] == str(outside.resolve())
    assert report["details"]["allowed"] == [str(allowed.resolve())]

    monkeypatch.setenv("KARTOGRAF_ROOT", str(allowed / "store"))
    (allowed / "store").mkdir()
    allowed_call = call("kartograf_store_overview", {}, allow_dirs=[allowed])
    assert allowed_call.is_error is False
    assert allowed_call.structured_content["result"]["root"] == str(allowed / "store")


@needs_mcp
def test_an_mcp_call_with_an_output_dir_needs_no_default_store(monkeypatch, tmp_path):
    """The target of the call is ``output_dir``: the default store is not involved."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path / "outside"))
    arguments = {"sheet": HSG_SHEET, "depth": "0-5cm", "check": True}

    with landcover_sources(soilgrids=RasterSoilGrids):
        refused = call("kartograf_soil_hsg", arguments, allow_dirs=[allowed])
        planned = call(
            "kartograf_soil_hsg",
            {**arguments, "output_dir": str(allowed / "out")},
            allow_dirs=[allowed],
        )

    error_of(refused, code="forbidden", reason="outside_allowed_dirs")
    assert planned.is_error is False
    assert planned.structured_content["result"]["mode"] == "plain"


@needs_mcp
def test_an_mcp_server_without_allow_dir_reads_the_default_store(monkeypatch, tmp_path):
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path))

    result = call("kartograf_store_overview", {})

    assert result.is_error is False
