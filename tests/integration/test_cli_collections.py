"""``boundaries``, ``cadastre`` and ``models3d`` only translate flags and print
the report (ADR-037, ADR-042 D9); the stores they write are compared with the
library in ``tests/contract/test_parity_collections.py``, the group listing and
``list-sources`` in ``tests/integration/test_cli.py::TestCommandGroups``."""

from unittest.mock import patch

import pytest

from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.download.collections import CollectionReport
from kartograf.download.data import UnitFailure
from kartograf.download.plan import new_plan

_DOWNLOAD = "kartograf.cli.collection_cmd.download_collection"
_CHECK = "kartograf.cli.collection_cmd.check_collection"


def _report(*, failed=(), ok=True) -> CollectionReport:
    return CollectionReport((), tuple(failed), (), (), ok)


@pytest.mark.parametrize(
    "argv",
    [
        ["cadastre", "download", "--level", "gmina"],
        ["cadastre", "download", "--whole-country"],
        ["cadastre", "download", "--lod", "1"],
        ["boundaries", "download", "--lod", "1"],
        ["boundaries", "download", "--year", "2024"],
        ["models3d", "download", "--level", "gmina"],
        ["models3d", "download", "--whole-country"],
        ["boundaries", "download", "--product", "map"],  # a product of cadastre
    ],
)
def test_group_flags_only_own(argv):
    with pytest.raises(SystemExit) as error:
        main(argv)
    assert error.value.code == 2


def test_flags_map_to_download_collection_kwargs(tmp_path):
    with patch(_DOWNLOAD, return_value=_report()) as download:
        rc = main(
            [
                "boundaries",
                "download",
                "--product",
                "admin",
                "--bbox",
                "19.9,50.05,19.92,50.06",
                "--bbox-crs",
                "EPSG:4326",
                "--country",
                "auto",
                "--level",
                "pl=gmina",
                "--workers",
                "3",
                "--force",
                "-o",
                str(tmp_path),
            ]
        )
    assert rc == 0
    kwargs = download.call_args.kwargs
    assert kwargs["bbox"] == BBox(19.9, 50.05, 19.92, 50.06, "EPSG:4326")
    assert (kwargs["product"], kwargs["country"]) == ("admin", "auto")
    assert kwargs["level"] == {"pl": "gmina"}
    assert (kwargs["workers"], kwargs["update"]) == (3, "force")
    assert kwargs["output_dir"] == str(tmp_path)
    assert kwargs.get("teryt") is None and not kwargs.get("whole_country")
    with patch(_DOWNLOAD, return_value=_report()) as download:
        main(
            [
                "models3d",
                "download",
                "--product",
                "buildings",
                "--teryt",
                "1261",
                "--lod",
                "1",
                "--year",
                "2024",
                "-o",
                str(tmp_path),
            ]
        )
    kwargs = download.call_args.kwargs
    assert (kwargs["teryt"], kwargs["lod"], kwargs["year"]) == ("1261", 1, 2024)
    assert (kwargs["workers"], kwargs["update"], kwargs.get("level")) == (1, None, None)


def test_check_updates_calls_check_collection_and_writes_plan(tmp_path):
    plan_file = tmp_path / "plan.json"
    plan = new_plan(tmp_path, [])
    with patch(_CHECK, return_value=plan) as check, patch(_DOWNLOAD) as download:
        rc = main(
            [
                "cadastre",
                "download",
                "--product",
                "map",
                "--teryt",
                "1261",
                "--check-updates",
                "--plan",
                str(plan_file),
                "-o",
                str(tmp_path),
            ]
        )
    assert rc == 0
    download.assert_not_called()
    assert check.call_args.kwargs["teryt"] == "1261"
    assert "update" not in check.call_args.kwargs
    assert plan_file.read_text(encoding="utf-8") == plan.to_json()


def test_missing_product_names_only_the_group_products(tmp_path, capsys):
    with patch(_DOWNLOAD) as download:
        rc = main(["models3d", "download", "--teryt", "1261", "-o", str(tmp_path)])
    assert rc == 2
    download.assert_not_called()
    (line,) = capsys.readouterr().err.splitlines()
    assert line.startswith("Error: --product wymagane: buildings (")
    assert "admin" not in line and "map" not in line


def test_failed_unit_is_error_line_and_exit_1(tmp_path, capsys):
    failure = UnitFailure("0224", "PL", "brak paczki powiatu 0224", "no_coverage")
    with patch(_DOWNLOAD, return_value=_report(failed=[failure], ok=False)):
        rc = main(
            [
                "models3d",
                "download",
                "--product",
                "buildings",
                "--lod",
                "2",
                "--country",
                "pl",
                "--bbox",
                "340000,290000,350000,300000",
                "-q",
                "-o",
                str(tmp_path),
            ]
        )
    assert rc == 1
    assert capsys.readouterr().err.splitlines() == [
        "Error: 0224: brak paczki powiatu 0224"
    ]
