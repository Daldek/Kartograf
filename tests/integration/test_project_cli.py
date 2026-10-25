"""Project CLI commands through the public API, with offline store providers."""

import argparse
from pathlib import Path

import pytest

from kartograf import (
    add_project_task,
    check_project,
    download_project,
    get_project_status,
    init_project,
    open_project,
    verify_project,
)
from kartograf.cli import main
from kartograf.cli._parser import create_parser
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.project.commands import COMMANDS
from tests.integration.test_cli import _cz_provider_mock
from tests.support.errors import without_error_document
from tests.support.parity import assert_notices_printed, assert_same_store
from tests.support.project_fixtures import (
    AUTO_CUTOUT,
    PL_SHEET,
    G,
    auto_pl_cz,
    pl_sheets,
)

pytestmark = pytest.mark.usefixtures("frozen_clock")

SHEET_FLAGS = [
    "--product",
    "nmt",
    "--sheet",
    G,
    "--resolution",
    "1m",
    "--vertical-crs",
    "EVRF2007",
]


def _add(project: Path, name: str, *args: str) -> list[str]:
    return ["project", "add", "--project", str(project), name, *args]


def _manifest_bytes(project: Path) -> bytes:
    return (project / "kartograf-project.json").read_bytes()


def _parser_for(command: str) -> argparse.ArgumentParser:
    parser = create_parser()
    group, subcommand = command.split()
    top = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    group_parser = top.choices[group]
    children = next(
        action
        for action in group_parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return children.choices[subcommand]


@pytest.mark.parametrize("command", COMMANDS)
def test_data_parser_options_cover_manifest_options(command):
    """A chosen data flag never disappears when stored as a project task."""
    parser = _parser_for(command)
    run_flags = {
        "root",
        "check_updates",
        "upgrade",
        "force",
        "plan",
        "workers",
        "quiet",
        "summary",
        "json",
        "lang",
    }
    parsed = {
        action.dest
        for action in parser._actions
        if action.dest not in {"help", *run_flags}
    }
    assert parsed == set(COMMANDS[command].options)


@pytest.mark.parametrize(
    ("command", "flags", "expected"),
    [
        (
            "elevation download",
            [
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
                "pl=EVRF2007,cz=Bpv",
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
            ],
            {
                "bbox": [18.6, 49.73, 18.66, 49.76],
                "bbox_crs": "EPSG:4326",
                "resolution": {"pl": "1m", "cz": "2m"},
                "vertical_crs": {"pl": "EVRF2007", "cz": "Bpv"},
                "cutout": True,
            },
        ),
        (
            "imagery download",
            ["--product", "orto", "--sheet", G, "--year", "2022", "--all-campaigns"],
            {"product": "orto", "sheet": G, "year": 2022, "all_campaigns": True},
        ),
        (
            "landcover download",
            [
                "--product",
                "bdot10k",
                "--teryt",
                "1465",
                "--format",
                "GPKG",
                "--layers",
                "SWRS,PTWP",
                "--keep-raw",
            ],
            {
                "product": "bdot10k",
                "teryt": "1465",
                "layers": ["SWRS", "PTWP"],
                "keep_raw": True,
            },
        ),
        (
            "soil download",
            ["--sheet", G, "--property", "clay", "--depth", "0-5cm", "--stat", "mean"],
            {"sheet": G, "property": "clay", "depth": "0-5cm", "stat": "mean"},
        ),
        (
            "soil hsg",
            ["--sheet", G, "--depth", "0-5cm"],
            {"sheet": G, "depth": "0-5cm"},
        ),
        (
            "imagery download",
            [
                "--product",
                "orto",
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
            ],
            {
                "cutout": True,
                "horizontal_crs": "EPSG:2180",
                "coverage": "high",
                "resolution": "0.5m",
            },
        ),
        (
            "landcover download",
            [
                "--product",
                "zabaged",
                "--whole-country",
                "--horizontal-crs",
                "EPSG:3045",
            ],
            {
                "product": "zabaged",
                "whole_country": True,
                "horizontal_crs": "EPSG:3045",
            },
        ),
        (
            "boundaries download",
            [
                "--product",
                "admin",
                "--country",
                "auto",
                "--level",
                "pl=gmina,cz=obec",
                "--bbox",
                "18.5,49.6,18.8,49.9",
                "--bbox-crs",
                "EPSG:4326",
            ],
            {"country": "auto", "level": {"pl": "gmina", "cz": "obec"}},
        ),
        (
            "hydro download",
            ["--product", "network", "--country", "cz", "--whole-country"],
            {"product": "network", "country": "cz", "whole_country": True},
        ),
    ],
)
def test_add_records_selected_options_for_every_data_command(
    tmp_path, capsys, command, flags, expected
):
    project = tmp_path / "projekt"
    assert (
        main(
            [
                "project",
                "init",
                "--project",
                str(project),
                "--root",
                str(project / "data"),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(_add(project, "warstwa", *command.split(), *flags)) == 0
    task = open_project(project).tasks[0]
    assert task.command == command
    for name, value in expected.items():
        assert task.options[name] == value
    assert task.files == ()
    assert (project / "data").is_dir()
    assert "Dodano zadanie warstwa" in capsys.readouterr().out


def test_cz_laz_task_pins_model_file_and_rejects_availability(
    tmp_path, monkeypatch, capsys
):
    """A project task keeps the model and pins the downloaded CUZK LAZ version."""
    from tests.integration.test_cuzk_laz import CTES96_URL, CuzkSession, zip_member
    from tests.integration.test_cz_laz import recorded

    monkeypatch.chdir(tmp_path)
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    assert (
        main(
            _add(
                project,
                "teren",
                "elevation",
                "download",
                "--product",
                "laz",
                "--country",
                "cz",
                "--model",
                "dmr4g",
                "--vertical-crs",
                "Bpv",
                "--sheet",
                "CTES96",
            )
        )
        == 0
    )
    (task,) = open_project(project).tasks
    assert task.options["model"] == "dmr4g"
    assert task.files == ()

    with recorded(CuzkSession()) as session:
        assert (
            main(["project", "download", "--project", str(project), "teren", "-q"]) == 0
        )
    assert session.of("GET") == [CTES96_URL]
    (task,) = open_project(project).tasks
    (pin,) = task.files
    assert pin.path == "laz/cz_dmr4g_bpv/CTES/96/CTES96.laz"
    assert (project / "data" / pin.version).read_bytes() == zip_member(CTES96_URL)

    before = _manifest_bytes(project)
    assert (
        main(
            _add(
                project,
                "raport",
                "elevation",
                "availability",
                "--product",
                "laz",
                "--country",
                "cz",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
            )
        )
        == 2
    )
    assert "do projektu mozna dodac komendy zapisujace dane" in capsys.readouterr().err
    assert _manifest_bytes(project) == before


@pytest.mark.parametrize(
    "flag", ["--upgrade", "--force", "--check-updates", "--plan", "--root"]
)
def test_add_rejects_update_modes_and_foreign_output(tmp_path, capsys, flag):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    manifest = project / "kartograf-project.json"
    before = manifest.read_bytes()
    trailing = (
        [flag, str(tmp_path / "obcy")] if flag in ("--plan", "--root") else [flag]
    )
    assert (
        main(_add(project, "teren", "elevation", "download", *SHEET_FLAGS, *trailing))
        == 2
    )
    error = capsys.readouterr().err
    assert error.startswith("Error: ")
    assert flag in error
    assert manifest.read_bytes() == before
    assert list((project / "data").iterdir()) == []


@pytest.mark.parametrize(
    ("command", "flag"),
    [
        (["elevation", "download", *SHEET_FLAGS, "-w", "8"], "--workers"),
        (["elevation", "download", *SHEET_FLAGS, "--workers=2"], "--workers"),
        (["elevation", "download", *SHEET_FLAGS, "-q"], "-q/--quiet"),
        (["elevation", "download", *SHEET_FLAGS, "--quiet"], "-q/--quiet"),
        (["soil", "hsg", "--sheet", G, "--depth", "0-5cm", "--summary"], "--summary"),
    ],
)
def test_add_rejects_run_options(tmp_path, capsys, command, flag):
    """Run and display options are not part of a task: an error, not a silently
    dropped value (parallel downloads: ``project download --workers``)."""
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    before = _manifest_bytes(project)
    assert main(_add(project, "teren", *command)) == 2
    error = capsys.readouterr().err
    assert error.startswith(f"Error: {flag} nie jest czescia zadania")
    if flag == "--workers":
        hint = f"kartograf project download --project {project} --workers N teren"
        assert hint in error
    assert _manifest_bytes(project) == before


def test_project_download_rejects_workers_below_one(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    with pytest.raises(ValidationError, match="--workers musi byc >= 1, podano 0"):
        download_project(project, workers=0)
    assert main(["project", "download", "--project", str(project), "-w", "0"]) == 2
    assert (
        without_error_document(capsys.readouterr().err)
        == "Error: --workers musi byc >= 1, podano 0\n"
    )


def test_project_download_has_no_store_plan_file_option(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    before = _manifest_bytes(project)
    with pytest.raises(SystemExit) as error:
        main(
            [
                "project",
                "download",
                "--project",
                str(project),
                "--check-updates",
                "--plan",
                str(tmp_path / "plan.json"),
            ]
        )
    assert error.value.code == 2
    assert "nieznana opcja --plan (maja ja:" in capsys.readouterr().err
    assert _manifest_bytes(project) == before


def test_add_accepts_same_store_output_and_optional_separator(tmp_path):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    same_store = project / "data" / ".." / "data"
    assert (
        main(
            _add(
                project,
                "teren",
                "--",
                "elevation",
                "download",
                *SHEET_FLAGS,
                "--root",
                str(same_store),
            )
        )
        == 0
    )
    assert open_project(project).tasks[0].options["product"] == "nmt"


def test_add_accepts_store_output_through_symlink(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    project = tmp_path / "projekt"
    init_project(project, root=alias)
    assert (
        main(
            _add(
                project,
                "teren",
                "elevation",
                "download",
                *SHEET_FLAGS,
                "--root",
                str(alias),
            )
        )
        == 0
    )
    with pl_sheets():
        report = download_project(project)
    assert report.ok
    assert (actual / report.project.tasks[0].files[0].version).is_file()


def test_add_selection_error_matches_public_api_without_store_changes(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    manifest = _manifest_bytes(project)
    with pytest.raises(ValidationError) as api_error:
        add_project_task(
            project,
            name="teren",
            command="elevation download",
            options={"product": "nmt", "sheet": G, "resolution": "1m"},
        )
    assert (
        main(
            _add(
                project,
                "teren",
                "elevation",
                "download",
                "--product",
                "nmt",
                "--sheet",
                G,
                "--resolution",
                "1m",
            )
        )
        == 2
    )
    assert without_error_document(capsys.readouterr().err).splitlines() == [
        f"Error: {api_error.value.localized('pl')}"
    ]
    assert _manifest_bytes(project) == manifest
    assert list((project / "data").iterdir()) == []


@pytest.mark.parametrize(
    "invalid",
    [
        ["sheet", "parse"],
        ["soil", "list-layers"],
        ["elevation", "list-sources"],
        # the report writes nothing: not a data command (no ``_task``)
        [
            "elevation",
            "availability",
            "--product",
            "nmt",
            "--country",
            "pl",
            "--bbox",
            "565000,242000,569000,246000",
        ],
    ],
)
def test_add_rejects_commands_without_data(tmp_path, capsys, invalid):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    assert main(_add(project, "teren", *invalid)) == 2
    assert (
        "Error: do projektu mozna dodac komendy zapisujace dane:"
        in capsys.readouterr().err
    )
    assert open_project(project).tasks == ()


def test_add_rejects_a_group_without_its_command(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    assert main(_add(project, "teren", "cache")) == 2
    assert (
        "Error: cache: podaj komende grupy (komendy danych:" in capsys.readouterr().err
    )
    assert open_project(project).tasks == ()


def test_add_misplaced_project_flag_explains_position(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    assert (
        main(
            _add(
                project,
                "teren",
                "elevation",
                "download",
                *SHEET_FLAGS,
                "--project",
                str(project),
            )
        )
        == 2
    )
    assert "--project podaj przed nazwa zadania" in capsys.readouterr().err
    assert open_project(project).tasks == ()


def test_nested_removed_command_and_help(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    assert main(_add(project, "teren", "download", *SHEET_FLAGS)) == 2
    assert "usunieta w 0.8.0" in capsys.readouterr().err
    for args, phrase in (
        (["project", "--help"], "download"),
        (["project", "add", "--help"], "NAZWA"),
        (_add(project, "teren", "elevation", "download", "--help"), "--vertical-crs"),
    ):
        with pytest.raises(SystemExit) as help_exit:
            main(args)
        assert help_exit.value.code == 0
        assert phrase in capsys.readouterr().out
    assert open_project(project).tasks == ()


def test_project_cli_matches_api_for_download_status_verify_and_updates(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    cli_dir, api_dir = tmp_path / "cli", tmp_path / "api"
    assert (
        main(["project", "init", "--project", str(cli_dir), "--root", "cli/data"]) == 0
    )
    init_project(api_dir, root="api/data")
    capsys.readouterr()

    assert main(_add(cli_dir, "teren", "elevation", "download", *SHEET_FLAGS)) == 0
    add_project_task(
        api_dir, name="teren", command="elevation download", options=PL_SHEET
    )
    assert (
        main(
            _add(
                cli_dir,
                "drugi",
                "elevation",
                "download",
                *SHEET_FLAGS,
                "--year",
                "2025",
            )
        )
        == 0
    )
    add_project_task(
        api_dir,
        name="drugi",
        command="elevation download",
        options={**PL_SHEET, "year": 2025},
    )
    capsys.readouterr()
    assert _manifest_bytes(cli_dir) == _manifest_bytes(api_dir)

    with pl_sheets():
        cli_code = main(["project", "download", "--project", str(cli_dir), "-q"])
        cli_out = capsys.readouterr()
        api = download_project(api_dir)
    assert cli_code == (0 if api.ok else 1) == 0
    assert cli_out.out == ""
    assert_notices_printed(cli_out.err, api.notices)
    assert_same_store(cli_dir / "data", api_dir / "data")
    assert _manifest_bytes(cli_dir) == _manifest_bytes(api_dir)

    for cmd, call in (
        ("status", get_project_status),
        ("verify", verify_project),
    ):
        result = call(api_dir)
        assert main(["project", cmd, "--project", str(cli_dir), "-q"]) == (
            0 if result.ok else 1
        )
        assert capsys.readouterr().out == ""
        assert [file.status for file in result.files] == ["ok", "ok"]

    with pl_sheets() as fake:
        check_bytes = (cli_dir / "kartograf-project.json").read_bytes()
        count = len(fake.downloads)
        code = main(
            ["project", "download", "--check-updates", "--project", str(cli_dir)]
        )
        text = capsys.readouterr()
        api_check = check_project(api_dir)
        assert code == (0 if api_check.ok else 1)
        assert_notices_printed(text.err, api_check.notices)
        assert fake.downloads[count:] == []
        assert check_bytes == (cli_dir / "kartograf-project.json").read_bytes()
        assert (
            main(["project", "download", "--upgrade", "--project", str(cli_dir), "-q"])
            == 0
        )
        capsys.readouterr()
        assert download_project(api_dir, update="upgrade").ok
    assert_same_store(cli_dir / "data", api_dir / "data")
    assert _manifest_bytes(cli_dir) == _manifest_bytes(api_dir)


def test_status_errors_and_remove_leave_store_versions(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    assert main(_add(project, "teren", "elevation", "download", *SHEET_FLAGS)) == 0
    assert f"pobierz: kartograf project download --project {project} teren" in (
        capsys.readouterr().out
    )
    assert main(["project", "status", "--project", str(project), "-q"]) == 11
    assert capsys.readouterr() == ("", "")  # a state: exit code only under -q
    assert main(["project", "status", "--project", str(project)]) == 11
    text = capsys.readouterr()
    assert text.err == ""
    assert text.out.splitlines()[-1] == (
        f"teren: nie pobrane (pobierz: kartograf project download --project "
        f"{project} teren)"
    )
    with pl_sheets():
        assert main(["project", "download", "--project", str(project), "-q"]) == 0
    capsys.readouterr()
    (pinned,) = open_project(project).tasks[0].files
    store_file = project / "data" / pinned.version
    assert store_file.is_file()
    store_file.write_bytes(b"broken")
    for command in ("status", "verify"):
        assert main(["project", command, "--project", str(project), "-q"]) == 11
        assert "Error: teren:" in capsys.readouterr().err
    assert main(["project", "remove", "--project", str(project), "teren"]) == 0
    assert open_project(project).tasks == ()
    assert store_file.read_bytes() == b"broken"


def test_project_lines_name_unit_and_file(tmp_path, capsys):
    """Live test 0.8.0: ``orto_cz: CTES96: ok`` four times. One format of the
    project lines: ``task: unit (file): status`` - also for a fresh pin."""
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    assert main(_add(project, "teren", "elevation", "download", *SHEET_FLAGS)) == 0
    with pl_sheets():
        assert main(["project", "download", "--project", str(project)]) == 0
    (pinned,) = open_project(project).tasks[0].files
    name = pinned.path.rsplit("/", 1)[1]
    assert f"teren: {pinned.unit} ({name}): przypieto {pinned.label}" in (
        capsys.readouterr().out
    )
    assert main(["project", "status", "--project", str(project)]) == 0
    assert f"teren: {pinned.unit} ({name}): ok" in capsys.readouterr().out


def test_project_error_same_as_public_api(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    with pytest.raises(ValidationError) as api_error:
        download_project(project, tasks=["literowka"])
    assert main(["project", "download", "--project", str(project), "literowka"]) == 2
    assert without_error_document(capsys.readouterr().err).splitlines() == [
        f"Error: {api_error.value.localized('pl')}"
    ]
    assert open_project(project).tasks == ()


def test_quiet_still_prints_project_warnings(tmp_path, capsys):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    options = AUTO_CUTOUT
    flags = [
        "--product",
        "nmt",
        "--bbox",
        "18.6300,49.7450,18.6303,49.7452",
        "--bbox-crs",
        "EPSG:4326",
        "--country",
        "auto",
        "--resolution",
        "pl=1m,cz=2m",
        "--vertical-crs",
        "pl=EVRF2007,cz=Bpv",
        "--cutout",
        "--horizontal-crs",
        "EPSG:5514",
    ]
    assert main(_add(project, "teren", "elevation", "download", *flags)) == 0
    capsys.readouterr()
    assert open_project(project).tasks[0].options["resolution"] == options["resolution"]
    cz = _cz_provider_mock()
    cz.download_bbox.side_effect = DownloadError("CUZK 503")
    with auto_pl_cz(cz):
        assert main(["project", "download", "--project", str(project), "-q"]) == 11
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Warning: teren: " in captured.err
    assert "Error: teren: CUZK 503" in captured.err
    assert open_project(project).tasks[0].files == ()
