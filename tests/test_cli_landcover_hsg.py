"""``landcover download`` and ``soilgrids hsg`` on the version store (CLI).

Update modes, plan files and status lines (spec 4.2, 4.4, 4.5) through
``main`` with fake sources (no network).
"""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.download.fetch import VersionedFile
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.hydrology import HSGCalculator
from kartograf.landcover.manager import (
    LandCoverAreaResult,
    LandCoverManager,
    LandCoverResult,
)
from kartograf.notices import NO_COVERAGE_SOME, Notice
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


def test_landcover_status_lines_and_summary(tmp_path, capsys, caplog):
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
    error = "Error: 0224: BDOT10k TERYT 0224: HTTP 500"
    assert captured.err.splitlines().count(error) == 1
    assert (
        "Nowe: 1, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 1 "
        f"({tmp_path / 'out'})"
    ) in captured.out
    assert not any(
        record.name == "kartograf.landcover.manager"
        and record.levelno >= logging.WARNING
        for record in caplog.records
    )


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


def test_landcover_corine_preview_line(tmp_path, capsys, caplog):
    with (
        _session(FakeCorine()),
        patch.object(CorineProvider, "has_clms_token", new=False),
    ):
        rc = _lc(tmp_path, "--source", "corine", "--year", "2018", "--bbox", BBOX_ARG)
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == (
        "Info: CORINE 2018: podglad WMS (stylizowany PNG, nie dane; "
        "dane CLMS wymagaja CLMS_CREDENTIALS)\n"
    )
    assert (
        f"landcover/eu_corine_2018_preview/bbox/{COORDS}.png: nowa wersja "
        in captured.out
    )
    assert not any(
        record.name == "kartograf.providers.corine"
        and record.levelno >= logging.WARNING
        for record in caplog.records
    )


def test_corine_preview_not_emitted_for_invalid_sheet(tmp_path, capsys):
    with patch.object(CorineProvider, "has_clms_token", new=False):
        manager = LandCoverManager(tmp_path / "api", "corine", cache=False)
        with pytest.raises(ValidationError) as exc:
            manager.download(sheet="XYZ", year=2018)
        assert (
            _lc(tmp_path, "--source", "corine", "--sheet", "XYZ", "--year", "2018") == 1
        )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Error: {exc.value}\n"


def test_hsg_invalid_sheet_has_no_header(tmp_path, capsys):
    with pytest.raises(ValidationError) as exc:
        HSGCalculator(tmp_path / "api", cache=False).calculate_hsg(
            sheet="XYZ", depth="0-5cm"
        )
    assert (
        main(
            [
                "soilgrids",
                "hsg",
                "--sheet",
                "XYZ",
                "--depth",
                "0-5cm",
                "-o",
                str(tmp_path / "cli"),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Error: {exc.value}\n"


@pytest.mark.parametrize("mode", ["check", "download"])
def test_invalid_teryt_matches_cli_and_api(tmp_path, capsys, mode):
    manager = LandCoverManager(tmp_path / "api", "bdot10k", cache=False)
    with pytest.raises(ValidationError, match="^Nieprawidlowy kod TERYT: 14$") as exc:
        getattr(manager, mode)(teryt="14")
    flags = ["--check-updates"] if mode == "check" else []
    assert _lc(tmp_path, "--source", "bdot10k", "--teryt", "14", *flags) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Error: {exc.value}\n"


@pytest.mark.parametrize(
    ("coordinates", "bbox"),
    [
        ("2,1,1,2", BBox(2, 1, 1, 2, "EPSG:2180")),
        ("nan,1,2,2", BBox(float("nan"), 1, 2, 2, "EPSG:2180")),
    ],
)
@pytest.mark.parametrize("mode", ["check", "download"])
def test_invalid_landcover_bbox_matches_cli_and_api(
    tmp_path, capsys, coordinates, bbox, mode
):
    manager = LandCoverManager(tmp_path / "api", "bdot10k", cache=False)
    with pytest.raises(ValidationError) as exc:
        getattr(manager, mode)(bbox=bbox)
    flags = ["--check-updates"] if mode == "check" else []
    assert _lc(tmp_path, "--source", "bdot10k", "--bbox", coordinates, *flags) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Error: {exc.value}\n"


@pytest.mark.parametrize(
    ("coordinates", "bbox"),
    [
        ("2,1,1,2", BBox(2, 1, 1, 2, "EPSG:2180")),
        ("nan,1,2,2", BBox(float("nan"), 1, 2, 2, "EPSG:2180")),
    ],
)
@pytest.mark.parametrize("mode", ["check_hsg", "calculate_hsg"])
def test_invalid_hsg_bbox_matches_cli_and_api(
    tmp_path, capsys, coordinates, bbox, mode
):
    calc = HSGCalculator(tmp_path / "api", cache=False)
    with pytest.raises(ValidationError) as exc:
        getattr(calc, mode)(bbox=bbox, depth="0-5cm")
    flags = ["--check-updates"] if mode == "check_hsg" else []
    assert (
        main(
            [
                "soilgrids",
                "hsg",
                "--bbox",
                coordinates,
                "--depth",
                "0-5cm",
                "-o",
                str(tmp_path / "cli"),
                *flags,
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Error: {exc.value}\n"


@pytest.mark.parametrize("mode", ["check", "download"])
def test_unsupported_bbox_crs_rejected_before_transform(tmp_path, mode):
    manager = LandCoverManager(tmp_path / "api", "corine", cache=False)
    with pytest.raises(ValidationError, match="Nieprawidlowy bbox:") as exc:
        getattr(manager, mode)(bbox=BBox(0, 0, 1, 1, "EPSG:999999"), year=2018)
    assert "EPSG:999999" in str(exc.value)


@pytest.mark.parametrize("mode", ["check_hsg", "calculate_hsg"])
def test_hsg_unsupported_bbox_crs_rejected_before_transform(tmp_path, mode):
    calc = HSGCalculator(tmp_path / "api", cache=False)
    with pytest.raises(ValidationError, match="Nieprawidlowy bbox:") as exc:
        getattr(calc, mode)(bbox=BBox(0, 0, 1, 1, "EPSG:999999"), depth="0-5cm")
    assert "EPSG:999999" in str(exc.value)


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
    with pytest.raises(ValidationError) as error:
        HSGCalculator(tmp_path / "hsg.tif")
    assert capsys.readouterr().err == f"Error: {error.value}\n"


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
    assert "Statystyki HSG:" in out
    assert "Grupa B: " in out or "Grupa A: " in out
    store = Path(tmp_path / "out" / "hsg/global_soilgrids_0-5cm_mean/bbox")
    assert (store / f"{COORDS}.tif").exists()


def test_hsg_unexpected_error_uses_main_barrier(tmp_path, capsys, monkeypatch):
    with patch(_HSG) as calc:
        calc.return_value.calculate_hsg.side_effect = RuntimeError("nieoczekiwany blad")
        assert _hsg(tmp_path) == 1
        (line, hint) = capsys.readouterr().err.splitlines()
        assert line == "Error: RuntimeError: nieoczekiwany blad"
        assert hint == "Ustaw KARTOGRAF_DEBUG=1, aby zobaczyc pelny traceback."
        monkeypatch.setenv("KARTOGRAF_DEBUG", "1")
        with pytest.raises(RuntimeError, match="nieoczekiwany blad"):
            _hsg(tmp_path)


# --- R7 flags: --layers, --keep-raw, --bbox-crs, --workers, --quiet ----------

_MANAGER = "kartograf.cli.landcover_cmd.LandCoverManager"
_HSG = "kartograf.hydrology.HSGCalculator"


def _bdot(tmp_path, *flags):
    return ["landcover", "download", "--source", "bdot10k", "-o", str(tmp_path), *flags]


def _file(path: Path) -> VersionedFile:
    return VersionedFile(path, "new", "2026-10-12", "0" * 64, path)


def _manager(tmp_path, result=None):
    manager = MagicMock()
    manager.output_dir = tmp_path
    manager.download.return_value = result or LandCoverAreaResult(())
    return manager


def test_layers_flag_comma_list(tmp_path):
    manager = _manager(tmp_path)
    with patch(_MANAGER, return_value=manager):
        assert main(_bdot(tmp_path, "--teryt", "1465", "--layers", "SWRS,PTWP")) == 0
    assert manager.download.call_args.kwargs["layers"] == ("SWRS", "PTWP")


def test_layers_bad_code_is_library_error_before_network(tmp_path, capsys):
    with patch(
        "kartograf.providers.pl.bdot10k.Bdot10kProvider.download_package"
    ) as get:
        rc = main(_bdot(tmp_path, "--teryt", "1465", "--layers", "SWRS,swrs1"))
    assert rc == 1
    get.assert_not_called()
    (line,) = capsys.readouterr().err.splitlines()
    assert line.startswith("Error: ") and "swrs1" in line


@pytest.mark.parametrize("flag", ["--layers", "--keep-raw"])
def test_bdot_only_flags_rejected_for_other_sources(tmp_path, capsys, flag):
    argv = [
        "landcover",
        "download",
        "--source",
        "corine",
        "--year",
        "2018",
        "--sheet",
        "N-34-130-D",
        "-o",
        str(tmp_path),
        flag,
        *(["SWRS"] if flag == "--layers" else []),
    ]
    assert main(argv) == 1
    assert f"Error: {flag} dziala tylko z --source bdot10k" in capsys.readouterr().err


def test_keep_raw_flag(tmp_path):
    manager = _manager(tmp_path)
    with patch(_MANAGER, return_value=manager):
        assert main(_bdot(tmp_path, "--teryt", "1465", "--keep-raw")) == 0
        assert manager.download.call_args.kwargs["keep_raw"] is True
        assert main(_bdot(tmp_path, "--teryt", "1465")) == 0
        assert "keep_raw" not in manager.download.call_args.kwargs


def test_bbox_crs_landcover_and_hsg(tmp_path):
    expected = BBox(18.6, 49.7, 18.7, 49.8, "EPSG:4326")
    manager = _manager(tmp_path)
    with patch(_MANAGER, return_value=manager):
        main(
            _bdot(tmp_path, "--bbox", "18.6,49.7,18.7,49.8", "--bbox-crs", "EPSG:4326")
        )
    assert manager.download.call_args.kwargs["bbox"] == expected
    with patch(_HSG) as calc:
        calc.return_value.calculate_hsg.return_value = MagicMock(
            inputs=(), file=None, stale=(), ok=True
        )
        main(
            [
                "soilgrids",
                "hsg",
                "--bbox",
                "18.6,49.7,18.7,49.8",
                "--bbox-crs",
                "EPSG:4326",
                "--depth",
                "0-5cm",
                "-o",
                str(tmp_path),
            ]
        )
    assert calc.return_value.calculate_hsg.call_args.kwargs["bbox"] == expected


def test_workers_landcover(tmp_path):
    manager = _manager(tmp_path)
    with patch(_MANAGER, return_value=manager):
        main(_bdot(tmp_path, "--sheet", "N-34-130-D", "--workers", "3"))
        assert manager.download.call_args.kwargs["workers"] == 3
        main(_bdot(tmp_path, "--sheet", "N-34-130-D"))
        assert manager.download.call_args.kwargs["workers"] == 1


def test_quiet_suppresses_status_lines_not_notices(tmp_path, capsys):
    notice = Notice("warning", NO_COVERAGE_SOME, "powiat 1465 bez danych")
    path = tmp_path / "landcover" / "pl_bdot10k_gpkg" / "teryt" / "1465.gpkg"
    result = LandCoverAreaResult((LandCoverResult("1465", _file(path)),))

    def download(**kwargs):
        kwargs["on_notice"](notice)
        return result

    manager = _manager(tmp_path)
    manager.download.side_effect = download
    with patch(_MANAGER, return_value=manager):
        assert main(_bdot(tmp_path, "--sheet", "N-34-130-D")) == 0
        loud = capsys.readouterr()
        assert main(_bdot(tmp_path, "--sheet", "N-34-130-D", "-q")) == 0
        quiet = capsys.readouterr()
    assert "nowa wersja" in loud.out and quiet.out == ""
    assert quiet.err == loud.err == "Warning: powiat 1465 bez danych\n"


def test_quiet_hsg_prints_nothing_on_stdout(tmp_path, capsys):
    with patch(_HSG) as calc:
        calc.return_value.calculate_hsg.return_value = MagicMock(
            inputs=(), file=None, stale=(), ok=True
        )
        argv = ["soilgrids", "hsg", "--sheet", "N-34-130-D", "--depth", "0-5cm"]
        assert main([*argv, "-o", str(tmp_path), "-q"]) == 0
    assert capsys.readouterr().out == ""
