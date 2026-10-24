"""The ``--json`` mode of the CLI: the envelope of stdout and the exit code of a
result (spec 7.1, AGI-3.2).

The data commands print the envelope ``kartograf-result/1`` of the document of the
library call, byte for byte (``run_both`` runs the CLI and the call with two stores;
the stores aside, the two documents are the same text), and nothing else: no
progress bar, no status line, no notice line - the notices are in the document.
Every other command of the CLI prints the envelope of the document of its library
function, too (the last part). An error writes nothing to stdout.
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
    add_project_task,
    calculate_hsg,
    check_availability,
    check_data,
    check_project,
    clear_cache,
    describe_sheet,
    download_collection,
    download_data,
    download_landcover,
    download_project,
    download_soil,
    get_cache_info,
    get_cache_path,
    get_config,
    get_project_status,
    init_project,
    list_layers,
    list_sources,
    remove_project_task,
    verify_project,
)
from kartograf._errors import OUTCOMES
from kartograf.cache.defaults import default_cache_path
from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.commands import declared
from kartograf.cli import main
from kartograf.cli._json import emit_error, emit_result
from kartograf.core.bbox import BBox
from kartograf.download.data import DataReport, UnitFailure
from kartograf.download.plan import PlanItem, UpdatePlan, new_plan
from kartograf.envelope import wrap
from kartograf.error_report import error_report
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.interrupt import Terminated
from kartograf.providers.pl.gugik_laz import SupersededLazTile
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.serialization import SCHEMAS
from kartograf.source_info import SOURCE_GROUPS
from kartograf.testing import PL_SEGMENT, build_fixture_store
from tests.conftest import FakeSoilGrids, RecordedIndex
from tests.contract.test_parity import (
    PL_SHEET_ARGS,
    PL_SHEET_KW,
    AnySheetProvider,
    G,
    _bbox_arg,
    _inner,
    _pl_store,
)
from tests.contract.test_parity_collections import _serve
from tests.contract.test_parity_landcover import (
    BBOX,
    BBOX_ARG,
    CLAY,
    CLAY_ARGS,
    _bdot,
    _providers,
)
from tests.integration.test_cli_update_modes import LAZ_SHEET, LazCliProvider
from tests.integration.test_cuzk_laz import CIESZYN, CuzkSession
from tests.integration.test_hsg import RasterSoilGrids
from tests.integration.test_landcover_output_params import FakePackages
from tests.integration.test_laz_download import _selection, _tile
from tests.integration.test_manager_campaigns import C14, FakeCampaignProvider
from tests.support.fake_packages import package_route
from tests.support.parity import run_both
from tests.support.project_fixtures import new_project, pl_sheets

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


def _position(status: str) -> PlanItem:
    return PlanItem(
        "pl_sheet",
        "nmt",
        "1992",
        SHEET,
        SHEET,
        None,
        None,
        None,
        None,
        status,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("statuses", "code"),
    [
        (["current"], 0),
        (["missing"], 0),
        (["current", "missing"], 0),
        (["check_failed"], 11),
        (["current", "check_failed"], 10),
    ],
)
def test_emit_result_prints_the_envelope_and_returns_the_code_of_its_status(
    capsys, tmp_path, statuses, code
):
    plan = new_plan(tmp_path, [_position(status) for status in statuses])
    envelope = wrap("elevation download", plan, check=True)

    assert emit_result("elevation download", plan, check=True) == code
    assert capsys.readouterr().out == envelope.to_json()
    assert json.loads(envelope.to_json())["result"] == plan.to_dict()


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ValidationError("zle dane"), 2),
        (DownloadError("siec"), 5),
        (KeyboardInterrupt(), 130),
        (Terminated(), 143),
    ],
)
def test_emit_error_writes_the_document_as_the_last_line_of_stderr(capsys, error, code):
    report = error_report(error)

    assert emit_error(report) == code == report.exit_code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == report.to_json(indent=None) + "\n"


# -- the data commands: the document of the library call ---------------------


def _without_store(text: str, store: Path) -> str:
    """``text`` with the store directory (as given and resolved) replaced."""
    for form in {store.as_posix(), store.resolve().as_posix()}:
        text = text.replace(form, STORE)
    return text


def _same_document(run, schema: str, command: str, *, check: bool = False) -> dict:
    """The CLI wrote the envelope of the API call - the stores aside, the same
    text -, nothing on stderr, and the exit code of its status. The result is the
    domain document of the envelope."""
    envelope = wrap(command, run.api_result, check=check)
    cli = _without_store(run.cli_stdout, run.cli_store)
    api = _without_store(envelope.to_json(), run.api_store)

    assert run.cli_stderr == ""
    assert cli == api
    assert run.cli_code == envelope.exit_code
    document = json.loads(run.cli_stdout)
    assert document["schema"] == "kartograf-result/1"
    assert (document["command"], document["check"]) == (command, check)
    assert document["result"]["schema"] == schema
    return document["result"]


@pytest.mark.usefixtures("frozen_clock")
def test_json_pl_sheet(tmp_path):
    with _pl_store(FakeCampaignProvider(C14)):
        run = run_both(
            [*ELEVATION, "--json"],
            lambda out: download_data(output_dir=out, **NMT_SHEET),
            tmp_path,
        )

    document = _same_document(run, "kartograf-download/1", "elevation download")
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

    document = _same_document(run, "kartograf-download/1", "elevation download")
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

    document = _same_document(run, "kartograf-download/1", "models3d download")
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

    document = _same_document(run, "kartograf-download/1", "landcover download")
    assert len(document["files"]) == 1


@pytest.mark.usefixtures("frozen_clock")
def test_json_soil(tmp_path):
    with _providers(soilgrids=lambda: SoilGridsProvider(session=FakeSoilGrids())):
        run = run_both(
            ["soil", "download", "--bbox", BBOX_ARG, *CLAY_ARGS, "--json"],
            lambda out: download_soil(output_dir=out, bbox=BBOX, **CLAY),
            tmp_path,
        )

    document = _same_document(run, "kartograf-download/1", "soil download")
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

    document = _same_document(run, "kartograf-download/1", "soil hsg")
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

    document = _same_document(run, "kartograf-plan/1", "elevation download", check=True)
    assert json.loads(plan_file.read_text(encoding="utf-8")) == document
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

    document = _same_document(upgraded, "kartograf-download/1", "elevation download")
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

    envelope = json.loads(run.cli_stdout, parse_constant=refuse)
    _same_document(run, "kartograf-download/1", "elevation download")
    (entry,) = envelope["result"]["superseded"]
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

    document = _same_document(run, "kartograf-download/1", "elevation download")
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


def test_json_ok_false_is_a_result_with_the_exit_code_of_its_status(capsys, tmp_path):
    """A failure of every unit is a result, not an error: the envelope with the
    status ``failed`` - the failed unit in it, no ``Error:`` line, no error
    document - and code 11."""
    code, out, err = _with_report(FAILED, capsys, tmp_path, "--json")

    assert code == 11
    assert out == wrap("elevation download", FAILED).to_json()
    assert err == ""
    envelope = json.loads(out)
    assert envelope["status"] == "failed"
    assert envelope["result"]["failed"][0]["error"] == "brak odpowiedzi zrodla"
    assert envelope["items"] == [
        {
            "id": G,
            "status": "failed",
            "code": "source_unavailable",
            "message": "brak odpowiedzi zrodla",
        }
    ]


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
    assert out == wrap("elevation availability", report).to_json()


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
    assert out == wrap("elevation availability", report).to_json()
    assert json.loads(out)["result"]["notices"] == json.loads(out)["notices"] != []


# -- the query and management commands: the document of the library function -


def _offline_lines(project: Path, base: Path) -> dict[str, list[str]]:
    """The command line of every leaf command that runs offline, by command id
    (``project`` has the task ``teren``; ``project init`` makes ``base/nowy``)."""
    here = str(project)
    store = base / "store"
    return {
        **{f"{group} list-sources": [group, "list-sources"] for group in SOURCE_GROUPS},
        "landcover list-layers": ["landcover", "list-layers", "--product", "corine"],
        "soil list-layers": ["soil", "list-layers"],
        "sheet parse": ["sheet", "parse", "N-34-130-D", "--hierarchy", "--children"],
        "sheet find": [
            *("sheet", "find", "--bbox", "565000,242000,566000,243000"),
            *("--scale", "1:10000", "--sheet-system", "1992"),
        ],
        "store overview": ["store", "overview", "--output", str(store)],
        "store entries": [
            *("store", "entries", "--output", str(store)),
            *("--segment", PL_SEGMENT, "--limit", "3"),
        ],
        "store sidecar": [
            *("store", "sidecar", "--path"),
            str(next(store.rglob("*.asc"), store / "none.asc")),
        ],
        "commands list": ["commands", "list"],
        "commands schema": ["commands", "schema", "--command", "sheet parse"],
        "cache stats": ["cache", "stats"],
        "cache path": ["cache", "path"],
        "cache clear": ["cache", "clear"],
        "config show": ["config", "show"],
        "project init": [
            *("project", "init", "--project", str(base / "nowy")),
            *("--output", str(base / "nowy" / "dane")),
        ],
        "project add": ["project", "add", "--project", here, "drugi", *ELEVATION],
        "project remove": ["project", "remove", "--project", here, "teren"],
        "project status": ["project", "status", "--project", here],
        "project verify": ["project", "verify", "--project", here],
        "project download": ["project", "download", "--project", here],
    }


OFFLINE = sorted(_offline_lines(Path("."), Path(".")))


def _project(tmp_path: Path) -> Path:
    """A project with one task, ``teren``: the elevation sheet of ``ELEVATION``."""
    project = new_project(tmp_path)
    add_project_task(
        project, name="teren", command="elevation download", options=NMT_SHEET
    )
    build_fixture_store(tmp_path / "store")  # what the store commands read
    return project


@pytest.mark.parametrize("command", OFFLINE)
def test_query_and_management_commands_print_one_document(
    command, tmp_path, monkeypatch, capsys
):
    """``--json``: all of stdout is one envelope whose result has the schema of the
    command, stderr is empty, the exit code is that of its status (a project that is
    not downloaded yet is a result with ``ok: false``)."""
    monkeypatch.chdir(tmp_path)
    argv = _offline_lines(_project(tmp_path), tmp_path)[command]
    declaration = next(c for c in declared().commands if c.id == command)
    with pl_sheets():
        code = main([*argv, "--json"] if command != "project add" else _json_add(argv))
    captured = capsys.readouterr()

    envelope = json.loads(captured.out)
    assert captured.err == ""
    assert envelope["schema"] == "kartograf-result/1"
    assert (envelope["command"], envelope["check"]) == (command, False)
    assert envelope["result"]["schema"] in SCHEMAS
    assert envelope["result"]["schema"] == declaration.result_schema
    assert code == OUTCOMES[envelope["status"]]
    assert (code == 0) == envelope["result"].get("ok", True)


def _json_add(argv: list[str]) -> list[str]:
    """``project add ... --json``: the flag goes before the name of the task (after
    it, it is a flag of the data command that is not part of a task)."""
    return [*argv[:2], "--json", *argv[2:]]


def test_every_cli_command_has_a_json_test():
    """A command added to the catalog is a data command (the parity tests above and
    ``tests/integration/test_project_cli.py``), ``elevation availability`` or one
    of ``OFFLINE``."""
    leaves = {c.id for c in declared().commands}
    data = {c.id for c in declared().commands if c.project_task}
    data.add("elevation availability")

    assert set(OFFLINE) | data == leaves
    assert not set(OFFLINE) & data


@pytest.mark.parametrize(
    ("command", "argv", "document"),
    [
        (
            "sheet parse",
            ["sheet", "parse", "N-34-130-D", "--hierarchy", "--descendants", "1:25000"],
            lambda: describe_sheet("N-34-130-D", hierarchy=True, descendants="1:25000"),
        ),
        (
            "sheet parse",
            ["sheet", "parse", "CTES96"],
            lambda: describe_sheet("CTES96"),
        ),
        (
            "elevation list-sources",
            ["elevation", "list-sources"],
            lambda: list_sources(group="elevation"),
        ),
        (
            "geodesy list-sources",
            ["geodesy", "list-sources"],
            lambda: list_sources(group="geodesy"),
        ),
        (
            "landcover list-layers",
            ["landcover", "list-layers", "--product", "bdoo"],
            lambda: list_layers(group="landcover", product="bdoo"),
        ),
        (
            "soil list-layers",
            ["soil", "list-layers"],
            lambda: list_layers(group="soil"),
        ),
        ("config show", ["config", "show"], get_config),
    ],
    ids=[
        "parse-pl",
        "parse-cz",
        "elevation",
        "geodesy",
        "bdoo-layers",
        "soil-layers",
        "config",
    ],
)
def test_json_is_the_envelope_of_the_document_of_the_library_function(
    command, argv, document, capsys
):
    assert main([*argv, "--json"]) == 0

    assert capsys.readouterr().out == wrap(command, document()).to_json()


def test_parse_prints_no_text_before_an_error(capsys):
    """The code is described before anything is printed: a scale that does not
    exist is the error alone (stdout is what a script can use or nothing)."""
    assert main(["sheet", "parse", SHEET, "--descendants", "1:77"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error: ")


def test_cache_documents(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    cache = MetadataCache(db_path=default_cache_path())
    cache.set_record("nmt", "1m", "EVRF2007", "A", {"source": {"url": "https://x/a"}})
    cache.close()

    assert main(["cache", "stats", "--json"]) == 0
    stats = capsys.readouterr().out
    assert main(["cache", "path", "--json"]) == 0
    path = capsys.readouterr().out
    info = get_cache_info()
    assert stats == wrap("cache stats", info).to_json()
    assert path == wrap("cache path", get_cache_path()).to_json()
    assert json.loads(stats)["result"]["entries"]["records"] == 1
    # the path says where the cache is and does not count what is in it
    assert json.loads(path)["result"]["action"] == "path"
    assert json.loads(path)["result"]["entries"] is None

    assert main(["cache", "clear", "--json"]) == 0
    cleared = json.loads(capsys.readouterr().out)["result"]
    assert cleared["action"] == "clear" and cleared["cleared"] is True
    assert cleared["removed_unreadable"] is False
    assert get_cache_info().entries.records == 0  # type: ignore[union-attr]
    assert clear_cache().cleared is True


def test_cache_path_is_given_when_the_database_cannot_be_read(
    tmp_path, monkeypatch, capsys
):
    """``cache path`` does not open the database: the path of a cache that cannot
    be read is what is needed to repair it, in the text and in the document."""
    monkeypatch.chdir(tmp_path)
    db = default_cache_path()
    db.parent.mkdir(parents=True)
    db.write_bytes(b"to nie jest baza SQLite\n" * 200)

    assert main(["cache", "stats", "--json"]) == 8
    captured = capsys.readouterr()
    assert captured.out == ""
    document = json.loads(captured.err.splitlines()[-1])
    assert (document["code"], document["details"]["reason"]) == (
        "store_unavailable",
        "cache",
    )
    assert main(["cache", "path", "--json"]) == 0
    document = json.loads(capsys.readouterr().out)["result"]
    assert (document["path"], document["exists"]) == (db.as_posix(), True)
    assert document["size_bytes"] == db.stat().st_size
    assert main(["cache", "path"]) == 0
    assert capsys.readouterr().out == f"{db}\n"


# -- project: the documents are the ones of the public API -------------------


def _without_dir(text: str, directory: Path) -> str:
    for form in {directory.as_posix(), directory.resolve().as_posix()}:
        text = text.replace(form, "<project>")
    return text


@pytest.mark.usefixtures("frozen_clock")
def test_json_project_commands_print_the_documents_of_the_api(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    cli_dir, api_dir = tmp_path / "cli", tmp_path / "api"
    where = ["--project", str(cli_dir)]

    def same(document, command: str, *argv: str, check: bool = False) -> None:
        """The CLI line printed the envelope of the document of the API call (the
        project directories aside) and returned the exit code of its status."""
        code = main(list(argv))
        captured = capsys.readouterr()
        envelope = wrap(command, document, check=check)
        assert captured.err == ""
        assert _without_dir(captured.out, cli_dir) == _without_dir(
            envelope.to_json(), api_dir
        )
        assert code == envelope.exit_code

    same(
        init_project(api_dir, output_dir="api/data"),
        "project init",
        *("project", "init", *where, "--output", "cli/data", "--json"),
    )
    same(
        add_project_task(
            api_dir, name="teren", command="elevation download", options=NMT_SHEET
        ),
        "project add",
        *("project", "add", "--json", *where, "teren", *ELEVATION),
    )
    with pl_sheets():
        same(
            download_project(api_dir),
            "project download",
            *("project", "download", *where, "--json"),
        )
    same(
        get_project_status(api_dir),
        "project status",
        *("project", "status", *where, "--json"),
    )
    same(
        verify_project(api_dir),
        "project verify",
        *("project", "verify", *where, "--json"),
    )
    with pl_sheets():
        same(
            check_project(api_dir),
            "project download",
            *("project", "download", "--check-updates", *where, "--json"),
            check=True,
        )
    same(
        remove_project_task(api_dir, name="teren"),
        "project remove",
        *("project", "remove", *where, "teren", "--json"),
    )


@pytest.mark.parametrize(
    ("flags", "option"),
    [
        (["--json"], "json"),
        (["-w", "8"], "workers"),
        (["-w4"], "workers"),  # the default written out is a flag that was given
        (["--check-updates"], "check_updates"),
        (["--upgrade"], "upgrade"),
        (["--force"], "force"),
        (["--plan", "plan.json", "--upgrade"], "upgrade"),
    ],
)
def test_project_add_uses_parse_command(tmp_path, capsys, flags, option):
    """``project add`` reads the data command with ``parse_command``: a flag of a
    run is rejected as an input error that names it, also when it equals the
    default of the flag, and the manifest is not touched."""
    project = new_project(tmp_path)
    manifest = (project / "kartograf-project.json").read_bytes()
    argv = ["project", "add", "--json", "--project", str(project), "teren"]

    code = main([*argv, *ELEVATION, *flags])
    captured = capsys.readouterr()

    document = json.loads(captured.err.splitlines()[-1])
    assert code == 2 and captured.out == ""
    assert document["schema"] == "kartograf-error/1"
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "invalid_input"
    assert document["details"]["option"] == option
    assert (project / "kartograf-project.json").read_bytes() == manifest
