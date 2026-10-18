"""Data commands only translate flags and print the report (Z1):
``elevation download``/``imagery download`` -> ``download_data``,
``landcover download`` -> ``download_landcover``, collection groups ->
``download_collection``."""

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.download.collections import CollectionReport
from kartograf.download.data import DataReport, UnitFailure
from kartograf.download.laz import LazDownloadResult
from kartograf.download.plan import new_plan
from kartograf.exceptions import ValidationError
from kartograf.notices import AUTO_CLIPPED, NO_COVERAGE_SOME, Notice

_DOWNLOAD = "kartograf.cli.download_cmd.download_data"
_CHECK = "kartograf.cli.download_cmd.check_data"
_COLLECTION = "kartograf.cli.collection_cmd.download_collection"


def _report(*, ok=True, failed=(), notices=()) -> DataReport:
    return DataReport((), tuple(failed), (), (), tuple(notices), ok)


def test_flags_map_to_download_data_kwargs(tmp_path):
    shp = tmp_path / "a.shp"
    argv = [
        "elevation",
        "download",
        "--product",
        "nmt",
        "--bbox",
        "18.6,49.73,18.66,49.76",
        "--bbox-crs",
        "EPSG:4326",
        "--country",
        "auto",
        "--resolution",
        "pl=1m,cz=2m",
        "--vertical-crs",
        "EVRF2007",
        "--sheet-system",
        "2000",
        "--scale",
        "1:2000",
        "--min-year",
        "2019",
        "--all-campaigns",
        "--workers",
        "3",
        "--force",
        "-o",
        str(tmp_path),
    ]
    with patch(_DOWNLOAD, return_value=_report()) as download:
        assert main(argv) == 0
    kwargs = download.call_args.kwargs
    assert kwargs["bbox"] == BBox(18.6, 49.73, 18.66, 49.76, "EPSG:4326")
    assert kwargs["resolution"] == {"pl": "1m", "cz": "2m"}
    assert kwargs["vertical_crs"] == "EVRF2007"
    assert (kwargs["country"], kwargs["sheet_system"], kwargs["scale"]) == (
        "auto",
        "2000",
        "1:2000",
    )
    assert (kwargs["min_year"], kwargs["all_campaigns"]) == (2019, True)
    assert (kwargs["workers"], kwargs["update"]) == (3, "force")
    assert kwargs["output_dir"] == str(tmp_path)
    with patch(_DOWNLOAD, return_value=_report()) as download:
        main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--geometry",
                str(shp),
                "--layer",
                "obszar",
                "--country",
                "pl",
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
    kwargs = download.call_args.kwargs
    assert (kwargs["geometry"], kwargs["layer"]) == (shp, "obszar")
    assert kwargs["cutout"] is True and kwargs["horizontal_crs"] == "EPSG:2180"
    assert kwargs["bbox"] is None


def test_malformed_per_country_value_is_one_error_line(tmp_path, capsys):
    with patch(_DOWNLOAD) as download:
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--sheet",
                "N-34-139-C-a-3-1",
                "--resolution",
                "pl=1m,de=2m",
                "-o",
                str(tmp_path),
            ]
        )
    assert rc == 2
    download.assert_not_called()
    (line,) = capsys.readouterr().err.splitlines()
    assert line.startswith("Error: --resolution: nieprawidlowa wartosc 'pl=1m,de=2m'")


def test_imagery_new_flags_translation(tmp_path):
    """The orthophotomap cutout flags and ``--country cz`` reach
    ``download_data`` unchanged; flags not given stay unset."""
    argv = ["imagery", "download", "--product", "orto", "-o", str(tmp_path)]
    with patch(_DOWNLOAD, return_value=_report()) as download:
        rc = main(
            [
                *argv,
                "--country",
                "pl",
                "--bbox",
                "566000,243000,566500,243500",
                "--cutout",
                "--horizontal-crs",
                "EPSG:2180",
                "--coverage",
                "high",
                "--resolution",
                "0.5m",
            ]
        )
    assert rc == 0
    kwargs = download.call_args.kwargs
    assert kwargs["bbox"] == BBox(566000, 243000, 566500, 243500, "EPSG:2180")
    assert (kwargs["product"], kwargs["country"], kwargs["cutout"]) == (
        "orto",
        "pl",
        True,
    )
    assert (kwargs["horizontal_crs"], kwargs["coverage"], kwargs["resolution"]) == (
        "EPSG:2180",
        "high",
        "0.5m",
    )
    with patch(_DOWNLOAD, return_value=_report()) as download:
        rc = main([*argv, "--country", "cz", "--sheet", "CTES96"])
    assert rc == 0
    kwargs = download.call_args.kwargs
    assert (kwargs["country"], kwargs["sheet"], kwargs["bbox"]) == (
        "cz",
        "CTES96",
        None,
    )
    assert kwargs["cutout"] is False
    assert (kwargs["horizontal_crs"], kwargs["coverage"], kwargs["resolution"]) == (
        None,
        None,
        None,
    )


def test_level_per_country_syntax(tmp_path, capsys):
    """``--level pl=gmina,cz=obec`` is a mapping for ``download_collection``;
    a country outside PL/CZ is one error line before any request."""
    argv = [
        "boundaries",
        "download",
        "--product",
        "admin",
        "--country",
        "auto",
        "--bbox",
        "18.5,49.6,18.8,49.9",
        "--bbox-crs",
        "EPSG:4326",
        "-o",
        str(tmp_path),
    ]
    report = CollectionReport((), (), (), (), True)
    with patch(_COLLECTION, return_value=report) as download:
        assert main([*argv, "--level", "pl=gmina,cz=obec"]) == 0
    assert download.call_args.kwargs["level"] == {"pl": "gmina", "cz": "obec"}
    with patch(_COLLECTION, return_value=report) as download:
        assert main([*argv, "--level", "obec"]) == 0
    assert download.call_args.kwargs["level"] == "obec"
    capsys.readouterr()
    with patch(_COLLECTION) as download:
        assert main([*argv, "--level", "pl=gmina,de=obec"]) == 2
    download.assert_not_called()
    (line,) = capsys.readouterr().err.splitlines()
    assert line.startswith("Error: --level: nieprawidlowa wartosc 'pl=gmina,de=obec'")


def test_check_updates_calls_check_data_and_writes_plan(tmp_path, capsys):
    plan_file = tmp_path / "plan.json"
    plan = new_plan(tmp_path, [])
    with patch(_CHECK, return_value=plan) as check, patch(_DOWNLOAD) as download:
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--sheet",
                "N-34-139-C-a-3-1",
                "--check-updates",
                "--plan",
                str(plan_file),
                "-o",
                str(tmp_path),
            ]
        )
    assert rc == 0
    download.assert_not_called()
    assert check.call_args.kwargs["sheet"] == "N-34-139-C-a-3-1"
    assert "update" not in check.call_args.kwargs
    assert plan_file.read_text(encoding="utf-8") == plan.to_json()


def test_report_ok_false_exit_1(tmp_path, capsys):
    failure = UnitFailure("PL", "PL", "2 z 4 arkuszy nie pobrano", "download")
    with patch(_DOWNLOAD, return_value=_report(ok=False, failed=[failure])):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--sheet",
                "X",
                "-o",
                str(tmp_path),
            ]
        )
    assert rc == 1
    assert "Error: 2 z 4 arkuszy nie pobrano" in capsys.readouterr().err


def test_notices_printed_once_on_stderr_in_order(tmp_path, capsys):
    first = Notice("info", AUTO_CLIPPED, "pierwszy")
    second = Notice("warning", NO_COVERAGE_SOME, "drugi")

    def fake(**kwargs):
        kwargs["on_notice"](first)
        kwargs["on_notice"](second)
        return _report(notices=[first, second])

    with patch(_DOWNLOAD, side_effect=fake):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--sheet",
                "X",
                "-q",
                "-o",
                str(tmp_path),
            ]
        )
    assert rc == 0
    assert capsys.readouterr().err.splitlines() == [
        "Info: pierwszy",
        "Warning: drugi",
    ]


def test_validation_error_single_error_line(tmp_path, capsys):
    with patch(_DOWNLOAD, side_effect=ValidationError("--vertical-crs wymagane: x")):
        rc = main(
            ["elevation", "download", "--product", "nmt", "--sheet", "X"]
            + ["-o", str(tmp_path)]
        )
    assert rc == 2
    assert capsys.readouterr().err.splitlines() == ["Error: --vertical-crs wymagane: x"]


@pytest.mark.parametrize("check", [False, True], ids=["download", "check"])
def test_laz_preamble_only_after_validation_with_pl_crs(tmp_path, capsys, check):
    argv = [
        "elevation",
        "download",
        "--product",
        "laz",
        "--sheet",
        "N-34-139-C-a-3-1",
        "-o",
        str(tmp_path),
    ]
    if check:
        argv.append("--check-updates")
    with (
        patch(
            "kartograf.download.laz.download_laz_area",
            return_value=LazDownloadResult(tiles=()),
        ),
        patch(
            "kartograf.download.laz.check_laz_area",
            return_value=new_plan(tmp_path, []),
        ),
    ):
        assert main(argv) == 2
        invalid = capsys.readouterr()
        assert invalid.out == ""
        assert invalid.err.startswith("Error: --vertical-crs wymagane")
        assert main([*argv, "--vertical-crs", "pl=KRON86,cz=Bpv"]) == 0
    valid = capsys.readouterr()
    assert valid.err == ""
    if check:
        assert valid.out == ""
    else:
        assert valid.out.startswith("Pobieranie kafli LAZ (WFS GUGiK, KRON86)...\n")
        assert "pl=KRON86,cz=Bpv" not in valid.out


_FORBIDDEN = {
    "find_sheets_for_bbox",
    "find_sheets_for_geometry",
    "country_bbox",
    "countries_for_bbox",
    "split_bbox_by_country",
    "get_overall_bbox",
    "DownloadManager",
}


def test_cli_imports_no_data_logic():
    """Z1 is an architecture rule, not behaviour: the CLI must not import the
    data decisions it used to make (country split, sheet selection, geometry
    envelopes, the PL sheet manager, providers). The only source-text test of
    the suite, because a regression here is invisible to behaviour tests
    until the CLI and the library diverge again."""
    offenders = []
    # the command modules and the group modules of kartograf/cli/groups/
    for path in sorted(Path("kartograf/cli").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = {alias.name for alias in node.names}
                if module.startswith("kartograf.providers") or names & _FORBIDDEN:
                    offenders.append(f"{path.name}: {module} {sorted(names)}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("kartograf.providers"):
                        offenders.append(f"{path.name}: {alias.name}")
    assert offenders == []


@pytest.mark.parametrize("flag", ["--product", "--output", "--vertical-crs"])
def test_missing_choice_is_error_before_network(flag, tmp_path, capsys):
    argv = {
        "--product": ["--product", "nmt"],
        "--output": ["-o", str(tmp_path)],
        "--vertical-crs": ["--vertical-crs", "EVRF2007"],
    }
    args = [
        "elevation",
        "download",
        "--sheet",
        "N-34-139-C-a-3-1",
        "--resolution",
        "1m",
    ]
    for name, values in argv.items():
        if name != flag:
            args += values
    assert main(args) == 2
    err = capsys.readouterr().err
    assert err.startswith("Error: ") and "wymagane" in err
