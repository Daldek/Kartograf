"""The ``--json`` mode of the CLI: the document of stdout and the exit code of a
result (spec 7.1).

The data commands print the document of the library call, byte for byte
(``run_both`` runs the CLI and the call with two stores; the stores aside, the
two documents are the same text), and nothing else: no progress bar, no status
line, no notice line - the notices are in the document.
"""

import contextlib
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from kartograf import (
    calculate_hsg,
    check_availability,
    check_data,
    download_collection,
    download_data,
    download_landcover,
    download_soil,
)
from kartograf.cli import main
from kartograf.cli._json import emit_document
from kartograf.core.bbox import BBox
from kartograf.download.data import DataReport, UnitFailure
from kartograf.download.plan import PlanItem, UpdatePlan, new_plan
from kartograf.error_report import error_report
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.pl.gugik_laz import SupersededLazTile
from kartograf.providers.soilgrids import SoilGridsProvider
from tests.conftest import FakeSoilGrids, RecordedIndex
from tests.fake_packages import package_route
from tests.parity import run_both
from tests.test_cli_update_modes import LAZ_SHEET, LazCliProvider
from tests.test_cuzk_laz import CIESZYN, CuzkSession
from tests.test_hsg import RasterSoilGrids
from tests.test_landcover_output_params import FakePackages
from tests.test_laz_download import _selection, _tile
from tests.test_manager_campaigns import C14, FakeCampaignProvider
from tests.test_parity import (
    PL_SHEET_ARGS,
    PL_SHEET_KW,
    AnySheetProvider,
    G,
    _bbox_arg,
    _inner,
    _pl_store,
)
from tests.test_parity_collections import _serve
from tests.test_parity_landcover import (
    BBOX,
    BBOX_ARG,
    CLAY,
    CLAY_ARGS,
    _bdot,
    _providers,
)

SHEET = "N-34-130-D-d-2-4"
STORE = "<store>"
ELEVATION = [
    "elevation",
    "download",
    "--product",
    "nmt",
    "--sheet",
    G,
    *PL_SHEET_ARGS,
]
# the keyword arguments of ``download_data``/``check_data`` for the sheet of ELEVATION
PL_KW: dict[str, Any] = dict(PL_SHEET_KW)
NMT_SHEET: dict[str, Any] = {"product": "nmt", "sheet": G, **PL_KW}


@pytest.mark.parametrize(
    ("status", "code"),
    [("current", 0), ("missing", 0), ("check_failed", 1)],
)
def test_emit_document_prints_the_document_and_returns_the_code_of_ok(
    capsys, tmp_path, status, code
):
    item = PlanItem(
        "pl_sheet", "nmt", "1992", SHEET, SHEET, None, None, None, None, status
    )
    plan = new_plan(tmp_path, [item])

    assert emit_document(plan) == code
    assert capsys.readouterr().out == plan.to_json()


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ValidationError("zle dane"), 2),
        (DownloadError("siec"), 1),
        (KeyboardInterrupt(), 130),
    ],
)
def test_emit_document_returns_the_exit_code_of_an_error_document(capsys, error, code):
    report = error_report(error)

    assert emit_document(report) == code == report.exit_code
    assert capsys.readouterr().out == report.to_json()


# -- the data commands: the document of the library call ---------------------


def _without_store(text: str, store: Path) -> str:
    """``text`` with the store directory (as given and resolved) replaced."""
    for form in {store.as_posix(), store.resolve().as_posix()}:
        text = text.replace(form, STORE)
    return text


def _same_document(run, schema: str) -> dict:
    """The CLI wrote the one document of the API call - the stores aside, the
    same text -, nothing on stderr, and the exit code of its ``ok``."""
    cli = _without_store(run.cli_stdout, run.cli_store)
    api = _without_store(run.api_result.to_json(), run.api_store)

    assert run.cli_stderr == ""
    assert cli == api
    assert run.cli_code == (0 if getattr(run.api_result, "ok", True) else 1)
    document = json.loads(run.cli_stdout)
    assert document["schema"] == schema
    return document


@pytest.mark.usefixtures("frozen_clock")
def test_json_pl_sheet(tmp_path):
    with _pl_store(FakeCampaignProvider(C14)):
        run = run_both(
            [*ELEVATION, "--json"],
            lambda out: download_data(output_dir=out, **NMT_SHEET),
            tmp_path,
        )

    document = _same_document(run, "kartograf-download/1")
    assert [f["unit"] for f in document["files"]] == [G]
    assert document["ok"] is True


@pytest.mark.usefixtures("frozen_clock")
def test_json_pl_area(tmp_path):
    bbox = _inner(G)
    with _pl_store(AnySheetProvider(C14)):
        run = run_both(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                _bbox_arg(bbox),
                "--country",
                "pl",
                "--sheet-system",
                "1992",
                *PL_SHEET_ARGS,
                "--json",
            ],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                bbox=bbox,
                country="pl",
                sheet_system="1992",
                **PL_KW,
            ),
            tmp_path,
        )

    document = _same_document(run, "kartograf-download/1")
    assert [f["unit"] for f in document["files"]] == [G]
    # the header of the sheet list is a notice of the document, not a line of stdout
    assert "sheet_list" in {notice["code"] for notice in document["notices"]}


@pytest.mark.usefixtures("frozen_clock")
def test_json_collection(tmp_path, monkeypatch):
    _serve(monkeypatch, package_route("buildings_lod1_2024_1261"))
    run = run_both(
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
            "--json",
        ],
        lambda out: download_collection(
            product="buildings", output_dir=out, teryt="1261", lod=1, year=2024
        ),
        tmp_path,
    )

    document = _same_document(run, "kartograf-download/1")
    assert len(document["files"]) == 1


@pytest.mark.usefixtures("frozen_clock")
def test_json_landcover(tmp_path):
    download, teryts = _bdot(["1465"], FakePackages())
    with download, teryts:
        run = run_both(
            [
                "landcover",
                "download",
                "--product",
                "bdot10k",
                "--teryt",
                "1465",
                "--json",
            ],
            lambda out: download_landcover(
                product="bdot10k", output_dir=out, teryt="1465"
            ),
            tmp_path,
        )

    document = _same_document(run, "kartograf-download/1")
    assert len(document["files"]) == 1


@pytest.mark.usefixtures("frozen_clock")
def test_json_soil(tmp_path):
    with _providers(soilgrids=lambda: SoilGridsProvider(session=FakeSoilGrids())):
        run = run_both(
            ["soil", "download", "--bbox", BBOX_ARG, *CLAY_ARGS, "--json"],
            lambda out: download_soil(output_dir=out, bbox=BBOX, **CLAY),
            tmp_path,
        )

    document = _same_document(run, "kartograf-download/1")
    assert len(document["files"]) == 1


@pytest.mark.usefixtures("frozen_clock")
def test_json_hsg_with_summary(tmp_path):
    """``--summary`` puts the statistics of the HSG raster into the document
    (``calculate_hsg(summary=True)``): the text of the CLI has them too, from
    the same report."""
    with _providers(soilgrids=RasterSoilGrids):
        run = run_both(
            [
                "soil",
                "hsg",
                "--depth",
                "0-5cm",
                "--bbox",
                BBOX_ARG,
                "--summary",
                "--json",
            ],
            lambda out: calculate_hsg(
                output_dir=out, depth="0-5cm", bbox=BBOX, summary=True
            ),
            tmp_path,
        )

    document = _same_document(run, "kartograf-download/1")
    assert set(document["summary"]) >= {"A", "B", "nodata"}
    assert document["summary"] == run.api_result.summary
    assert len(document["files"]) == 1
    assert len(document["inputs"]) == 3  # clay, sand, silt


@pytest.mark.usefixtures("frozen_clock")
def test_json_check_updates_plan(tmp_path):
    """``--check-updates`` is the plan document; ``--plan FILE`` writes the same
    document, and the line ``Info: zapisano plan`` is not printed."""
    plan_file = tmp_path / "plan.json"
    with _pl_store(FakeCampaignProvider(C14)):
        run = run_both(
            [*ELEVATION, "--check-updates", "--plan", str(plan_file), "--json"],
            lambda out: check_data(output_dir=out, **NMT_SHEET),
            tmp_path,
        )

    document = _same_document(run, "kartograf-plan/1")
    assert plan_file.read_text(encoding="utf-8") == run.cli_stdout
    assert document["items"] and document["ok"] is True
    assert isinstance(run.api_result, UpdatePlan)


@pytest.mark.usefixtures("frozen_clock")
def test_json_plan_file_feeds_the_upgrade(tmp_path):
    """The plan file written by ``--check-updates --json`` is read by ``--upgrade
    --plan``, which prints the document of ``download_data(update="upgrade")``."""
    plan_file = tmp_path / "plan.json"
    with _pl_store(FakeCampaignProvider(C14)):
        checked = run_both(
            [*ELEVATION, "--check-updates", "--plan", str(plan_file), "--json"],
            lambda out: check_data(output_dir=out, **NMT_SHEET),
            tmp_path,
        )
        upgraded = run_both(
            [*ELEVATION, "--upgrade", "--plan", str(plan_file), "--json"],
            lambda out: download_data(
                output_dir=out,
                update="upgrade",
                plan=checked.api_result,  # type: ignore[arg-type]
                **NMT_SHEET,
            ),
            tmp_path,
        )

    document = _same_document(upgraded, "kartograf-download/1")
    assert [f["file"]["status"] for f in document["files"]] == ["new"]


@pytest.mark.usefixtures("frozen_clock")
def test_json_laz_superseded_tile_without_geometry(tmp_path):
    """A tile the WFS gave no geometry for has an extent of NaN in memory; the
    document has ``null`` there (NaN is no JSON value) and parses strictly."""

    class Provider(LazCliProvider):
        def select_tiles(self, bbox, **kwargs):
            nan = float("nan")
            selected = _tile(LAZ_SHEET, crs="PL-1992")
            unknown = replace(
                selected,
                sheet="N-34-130-D-d-2-3",
                min_x=nan,
                min_y=nan,
                max_x=nan,
                max_y=nan,
                footprint=None,
            )
            older = replace(selected, year=2019)
            return _selection(
                selected, superseded=[SupersededLazTile(older, (selected, unknown))]
            )

    with patch(
        "kartograf.providers.pl.gugik_laz.GugikLazProvider",
        side_effect=lambda **_kw: Provider(),
    ):
        run = run_both(
            [
                "elevation",
                "download",
                "--product",
                "laz",
                "--sheet",
                LAZ_SHEET,
                "--vertical-crs",
                "EVRF2007",
                "--json",
            ],
            lambda out: download_data(
                product="laz",
                output_dir=out,
                sheet=LAZ_SHEET,
                vertical_crs="EVRF2007",
            ),
            tmp_path,
        )

    def refuse(constant: str):
        raise AssertionError(f"{constant} is no JSON")

    document = json.loads(run.cli_stdout, parse_constant=refuse)
    _same_document(run, "kartograf-download/1")
    (entry,) = document["superseded"]
    unknown = entry["covered_by"][1]
    assert [unknown[key] for key in ("min_x", "min_y", "max_x", "max_y")] == [None] * 4
    assert unknown["footprint"] is None


@pytest.mark.usefixtures("frozen_clock")
def test_json_mode_has_no_progress_and_no_notice_lines(tmp_path):
    """A request that makes notices and a bar: stdout is the document alone
    (``json.loads`` of all of it), stderr is empty, the notices - the header of
    the sheet list included - are in the document."""
    parent = G.rsplit("-", 1)[0]  # 1:25000 -> 4 sheets, data only for G
    with _pl_store(FakeCampaignProvider(C14)):
        run = run_both(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--sheet",
                parent,
                *PL_SHEET_ARGS,
                "--json",
            ],
            lambda out: download_data(
                product="nmt", output_dir=out, sheet=parent, **PL_KW
            ),
            tmp_path,
        )

    document = _same_document(run, "kartograf-download/1")
    assert "no_coverage_some" in {notice["code"] for notice in document["notices"]}


FAILED = DataReport(
    files=(),
    failed=(UnitFailure(G, "PL", "brak odpowiedzi zrodla", "download"),),
    stale=(),
    superseded=(),
    notices=(),
    ok=False,
)


def _with_report(report: DataReport, capsys, tmp_path, *flags: str):
    with patch("kartograf.cli.download_cmd.download_data", return_value=report):
        code = main([*ELEVATION, "-o", str(tmp_path), *flags])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_json_ok_false_exits_1_with_the_report(capsys, tmp_path):
    """A partial failure is a result, not an error: the document of the report
    with ``ok: false`` - the failed unit in it, no ``Error:`` line - and code 1."""
    code, out, err = _with_report(FAILED, capsys, tmp_path, "--json")

    assert code == 1
    assert out == FAILED.to_json()
    assert err == ""
    assert json.loads(out)["failed"][0]["error"] == "brak odpowiedzi zrodla"


def test_quiet_with_json_is_allowed_and_has_no_effect(capsys, tmp_path):
    plain = _with_report(FAILED, capsys, tmp_path, "--json")
    quiet = _with_report(FAILED, capsys, tmp_path, "--json", "-q")

    assert quiet == plain


# -- elevation availability --------------------------------------------------


def _availability(argv: list[str], session, tmp_path, monkeypatch):
    """``elevation availability argv --json --force`` through the CLI; the
    session of the indexes stands in for the network."""
    monkeypatch.chdir(tmp_path)
    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        patch("kartograf.transport.http.make_gugik_session", return_value=session),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        code = main(["elevation", "availability", *argv, "--json", "--force"])
    return code, stdout.getvalue(), stderr.getvalue()


@pytest.mark.usefixtures("frozen_clock")
def test_json_availability_bytes_equal_to_json(tmp_path, monkeypatch):
    """The report of Pomorze (the coast): the text of ``check_availability(...)
    .to_json()``, and nothing on stderr."""
    areas = {
        f"nmt_{vcrs}": [f"area_nmt_{vcrs}_pomorze.xml.gz"]
        for vcrs in ("evrf2007", "kron86")
    }
    argv = [
        "--product",
        "nmt",
        "--country",
        "pl",
        "--bbox",
        "339000,744800,343000,747000",
    ]
    code, out, err = _availability(
        argv, RecordedIndex(areas, coast=True), tmp_path, monkeypatch
    )
    with patch(
        "kartograf.transport.http.make_gugik_session",
        return_value=RecordedIndex(areas, coast=True),
    ):
        report = check_availability(
            product="nmt",
            country="pl",
            bbox=BBox(339000, 744800, 343000, 747000, "EPSG:2180"),
            force=True,
        )

    assert code == 0 and err == ""
    assert out == report.to_json()


@pytest.mark.usefixtures("frozen_clock")
def test_json_availability_cz_has_its_notices_in_the_document(tmp_path, monkeypatch):
    """The recorded CUZK index and ``HEAD`` answers of the Cieszyn border area:
    the report has notices, they are in the document and not on stderr."""
    argv = [
        "--product",
        "nmpt",
        "--country",
        "cz",
        "--bbox=-447000,-1114000,-446000,-1113000",
        "--bbox-crs",
        "EPSG:5514",
    ]
    code, out, err = _availability(argv, CuzkSession(), tmp_path, monkeypatch)
    with patch(
        "kartograf.transport.http.make_gugik_session", return_value=CuzkSession()
    ):
        report = check_availability(
            product="nmpt", country="cz", bbox=CIESZYN, force=True
        )

    assert code == 0 and report.combinations and report.notices
    assert err == ""
    assert out == report.to_json()
    assert json.loads(out)["notices"]
