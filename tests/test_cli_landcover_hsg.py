"""``landcover download`` and ``soilgrids hsg`` on the version store (CLI).

Update modes, plan files and status lines (spec 4.2, 4.4, 4.5) through
``main`` with fake sources (no network).
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.cli.commands import main
from kartograf.exceptions import DownloadError
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kPackage, Bdot10kProvider
from tests.conftest import FakeCorine, FakeSoilGrids

BBOX_ARG = "770000,509000,772000,511000"
COORDS = "770000_509000_772000_511000"
SOIL = ["--source", "soilgrids", "--property", "clay", "--depth", "0-5cm"]
SOIL += ["--stat", "mean", "--bbox", BBOX_ARG]
CLAY = f"soil/global_soilgrids_clay_0-5cm_mean/bbox/{COORDS}.tif"


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    """The CLI metadata cache lands in the cwd."""
    monkeypatch.chdir(tmp_path)


def _session(fake):
    """Every provider session of the call is ``fake``."""
    return patch("kartograf.transport.http.SessionPerThread.get", return_value=fake)


def _lc(tmp_path, *argv):
    return main(["landcover", "download", *argv, "-o", str(tmp_path / "out")])


def _hsg(tmp_path, *argv):
    return main(
        ["soilgrids", "hsg", "--bbox", BBOX_ARG, "--depth", "0-5cm"]
        + ["-o", str(tmp_path / "out"), *argv]
    )


# --- landcover download -------------------------------------------------------


@pytest.mark.parametrize(
    "flags", [["--check-updates", "--upgrade"], ["--upgrade", "--force"]]
)
def test_landcover_update_flags_exclusive(tmp_path, flags, capsys):
    with pytest.raises(SystemExit) as exc:
        _lc(tmp_path, *SOIL, *flags)
    assert exc.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


@pytest.mark.parametrize("command", [["landcover", "download"], ["soilgrids", "hsg"]])
def test_plan_without_mode_is_error(tmp_path, command, capsys):
    with pytest.raises(SystemExit) as exc:
        main([*command, "--plan", str(tmp_path / "p.json"), "-o", str(tmp_path)])
    assert exc.value.code == 2
    assert "--plan wymaga --check-updates albo --upgrade" in capsys.readouterr().err


def test_landcover_check_writes_plan(tmp_path, capsys):
    fake = FakeSoilGrids("2.0")
    plan_file = tmp_path / "plan.json"
    with _session(fake):
        rc = _lc(tmp_path, *SOIL, "--check-updates", "--plan", str(plan_file))
    assert rc == 0
    assert fake.coverages == 0
    assert f"{COORDS}: do pobrania (2.0)" in capsys.readouterr().out
    items = json.loads(plan_file.read_text())["items"]
    assert [(i["track"], i["status"]) for i in items] == [("landcover", "missing")]
    assert not (tmp_path / "out" / "soil").exists()


def test_landcover_soilgrids_status_and_newer_edition_info(tmp_path, capsys):
    with _session(FakeSoilGrids("2.0")):
        assert _lc(tmp_path, *SOIL) == 0
    first = capsys.readouterr().out
    assert f"{CLAY}: nowa wersja 2.0_" in first
    assert "Downloaded to:" not in first
    with _session(FakeSoilGrids("2.1")):
        assert _lc(tmp_path, *SOIL) == 0
    out = capsys.readouterr().out
    assert f"{CLAY}: lokalna wersja 2.0; dostepna nowsza 2.1 (--upgrade)" in out


def test_landcover_upgrade_plan_stale_exit_1(tmp_path, capsys):
    plan_file = tmp_path / "plan.json"
    with _session(FakeSoilGrids("2.0")):
        _lc(tmp_path, *SOIL)
    with _session(FakeSoilGrids("2.1")):
        _lc(tmp_path, *SOIL, "--check-updates", "--plan", str(plan_file))
    capsys.readouterr()
    fake = FakeSoilGrids("2.2")
    with _session(fake):
        rc = _lc(tmp_path, *SOIL, "--upgrade", "--plan", str(plan_file))
    assert rc == 1
    assert fake.coverages == 0
    assert f"Error: {COORDS}: zrodlo zmienilo sie od planu (2.1)" in (
        capsys.readouterr().err
    )


def test_landcover_status_lines_and_summary(tmp_path, capsys):
    def package(code, output_path, **kwargs):
        if code == "0224":
            raise DownloadError("BDOT10k TERYT 0224: HTTP 500")
        output_path.write_bytes(code.encode())
        return Bdot10kPackage(path=output_path, teryt=code, url="u", format="GPKG")

    with (
        patch(
            "kartograf.providers.pl.bdot10k.discover_teryts_for_bbox",
            return_value=["0208", "0224"],
        ),
        patch.object(Bdot10kProvider, "download_package", side_effect=package),
    ):
        rc = _lc(tmp_path, "--source", "bdot10k", "--bbox", BBOX_ARG)
    assert rc == 1
    captured = capsys.readouterr()
    assert "landcover/pl_bdot10k_gpkg/teryt/0208.gpkg: nowa wersja " in captured.out
    assert "Error: 0224: BDOT10k TERYT 0224: HTTP 500" in captured.err
    assert (
        "Nowe: 1, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 1 "
        f"({tmp_path / 'out'})"
    ) in captured.out


def test_landcover_bdot_rerun_unchecked_line(tmp_path, capsys):
    def package(code, output_path, **kwargs):
        output_path.write_bytes(b"gpkg")
        return Bdot10kPackage(path=output_path, teryt=code, url="u", format="GPKG")

    with patch.object(Bdot10kProvider, "download_package", side_effect=package) as pkg:
        assert _lc(tmp_path, "--source", "bdot10k", "--teryt", "1465") == 0
        assert _lc(tmp_path, "--source", "bdot10k", "--teryt", "1465") == 0
        assert _lc(tmp_path, "--source", "bdot10k", "--teryt", "1465", "--upgrade") == 0
    assert pkg.call_count == 1
    captured = capsys.readouterr()
    assert "landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: lokalna wersja " in captured.out
    assert "(bez sprawdzania; --check-updates)" in captured.out
    assert "Info: landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: lokalna wersja" in (
        captured.err
    )


def test_landcover_corine_preview_line(tmp_path, capsys):
    with (
        _session(FakeCorine()),
        patch.object(CorineProvider, "has_clms_token", new=False),
    ):
        rc = _lc(tmp_path, "--source", "corine", "--year", "2018", "--bbox", BBOX_ARG)
    assert rc == 0
    captured = capsys.readouterr()
    assert "Info: CORINE 2018: podglad WMS" in captured.err
    assert (
        f"landcover/eu_corine_2018_preview/bbox/{COORDS}.png: nowa wersja "
        in captured.out
    )


# --- soilgrids hsg ------------------------------------------------------------


def test_hsg_cli_output_tif_rejected(tmp_path, capsys):
    fake = FakeSoilGrids()
    with _session(fake):
        rc = main(
            ["soilgrids", "hsg", "--bbox", BBOX_ARG, "--depth", "0-5cm"]
            + ["-o", str(tmp_path / "hsg.tif")]
        )
    assert rc == 1
    assert fake.capabilities == 0
    assert "Error: --output to katalog magazynu (od 0.8.0)" in capsys.readouterr().err


def test_hsg_cli_keep_intermediate_removed(tmp_path):
    with pytest.raises(SystemExit) as exc:
        _hsg(tmp_path, "--keep-intermediate")
    assert exc.value.code == 2


def test_hsg_cli_reused_line(tmp_path, capsys):
    with _session(FakeSoilGrids("2.0")):
        assert _hsg(tmp_path) == 0
    first = capsys.readouterr().out
    hsg = f"hsg/global_soilgrids_0-5cm_mean/bbox/{COORDS}.tif"
    assert f"{hsg}: nowa wersja 2.0_" in first
    assert f"{CLAY}: nowa wersja 2.0_" in first
    fake = FakeSoilGrids("2.0")
    with _session(fake):
        assert _hsg(tmp_path, "--force") == 0
    out = capsys.readouterr().out
    assert f"{CLAY}: bez zmian 2.0" in out
    assert f"{hsg}: uzyta ponownie 2.0" in out
    assert fake.coverages == 3


def test_hsg_cli_check_plan_tracks(tmp_path, capsys):
    plan_file = tmp_path / "plan.json"
    fake = FakeSoilGrids("2.0")
    with _session(fake):
        rc = _hsg(tmp_path, "--check-updates", "--plan", str(plan_file))
    assert rc == 0 and fake.coverages == 0
    out = capsys.readouterr().out
    for layer in ("clay", "sand", "silt", "hsg"):
        assert f"{layer} {COORDS}: do pobrania (2.0)" in out
    items = json.loads(plan_file.read_text())["items"]
    assert [i["track"] for i in items] == ["landcover"] * 3 + ["hsg"]
    assert {i["unit"] for i in items} == {COORDS}
    with _session(FakeSoilGrids("2.0")):
        assert _hsg(tmp_path, "--upgrade", "--plan", str(plan_file)) == 0
    assert "hsg/global_soilgrids_0-5cm_mean" in capsys.readouterr().out


def test_hsg_cli_stats_from_store_path(tmp_path, capsys):
    with _session(FakeSoilGrids("2.0")):
        assert _hsg(tmp_path, "--stats") == 0
    out = capsys.readouterr().out
    assert "HSG Statistics:" in out
    assert "Group B: " in out or "Group A: " in out
    store = Path(tmp_path / "out" / "hsg/global_soilgrids_0-5cm_mean/bbox")
    assert (store / f"{COORDS}.tif").exists()
