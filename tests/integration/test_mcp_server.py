"""The MCP server (AGI section 5; test row 12.8).

The calls run through ``mcp.Client`` connected to the server in memory, with the
sources of the download tests replaced by their fakes (``tests/project_fixtures``);
the gate test of AGI-5.13 and the others on the protocol start
``python -m kartograf.mcp_server`` and speak to it over stdio. The tools that
download need a server that writes (``writing``: ``--allow-writes`` inside a
directory); a server that does not write only plans, and the tests of that mode say
so. The tests that need the ``mcp`` package are skipped without it; the ones of the
command line and of the install hint are not.
"""

import importlib.util
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

import kartograf
from kartograf import (
    ConfigError,
    calculate_hsg,
    check_command,
    download_data,
    run_command,
)
from kartograf._output_schema import OUTPUT_SCHEMA
from kartograf.cache.defaults import default_cache_path
from kartograf.catalog.tools import ALWAYS_LOAD_KEY, DESCRIPTION_MAX, tool_specs
from kartograf.core.bbox import BBox
from kartograf.download.data import DataReport
from kartograf.download.manager import DownloadProgress
from kartograf.envelope import wrap
from kartograf.exceptions import ValidationError
from kartograf.mcp_server import (
    INSTRUCTIONS,
    INSTRUCTIONS_MAX,
    _parser,
    build_instructions,
    create_server,
    default_cache_file,
    main,
)
from tests.integration.test_hsg import RasterSoilGrids
from tests.integration.test_manager_campaigns import C14, REC, FakeCampaignProvider
from tests.support.project_fixtures import (
    HSG_SHEET,
    PL_SHEET,
    landcover_sources,
    pl_sheets,
)

REPO = Path(__file__).resolve().parent.parent.parent
needs_mcp = pytest.mark.skipif(
    importlib.util.find_spec("mcp") is None, reason="the mcp package is not installed"
)

if importlib.util.find_spec("mcp") is not None:
    # ``stdio_client`` keeps the ``sys.stderr`` it finds when its module is first
    # imported (the default ``errlog``). Import it now, at collection, and not in the
    # first test that captures stderr with ``capsys``: that stream has no file
    # descriptor to give a subprocess, and every stdio test after it would fail.
    import mcp.client.stdio  # noqa: F401

SHEET = "N-34-130-D-d-2-4"
AREA = BBox(19.93, 50.05, 19.95, 50.07, "EPSG:4326")
# what a fake of ``run_command`` answers: the envelope of an empty download
EMPTY_RESULT = wrap("elevation download", DataReport((), (), (), (), (), True))
PAGE_MAX = 20_000  # characters of a default page (DOC-1.7)
FORBIDDEN_HINT = "--allow-writes"


def writing(root: Path, *more: Path) -> dict:
    """The arguments of a server that writes inside ``root`` (and ``more``)."""
    return {"allow_writes": True, "allow_dirs": [root, *more]}


def run_session(scenario, *, server=None, **server_kwargs):
    """Run ``await scenario(client)`` against a server in memory: the given one or
    one made with ``server_kwargs`` (no cache unless ``cache`` is given)."""
    import anyio
    from mcp import Client

    async def main_task():
        target = server or create_server(**{"cache": False, **server_kwargs})
        async with Client(target, raise_exceptions=True) as client:
            return await scenario(client)

    return anyio.run(main_task)


def call(tool, arguments=None, *, progress=None, server=None, **server_kwargs):
    """The result of one call of a tool."""

    async def scenario(client):
        return await client.call_tool(tool, arguments or {}, progress_callback=progress)

    return run_session(scenario, server=server, **server_kwargs)


def normal(data, *stores: Path) -> str:
    """A document as text, with the store directories named."""
    text = json.dumps(data)
    for store in stores:
        text = text.replace(str(store), "<store>")
    return text


def error_of(result, *, code="validation_error", reason=None):
    """The ``kartograf-error/1`` document of a failed call."""
    report = result.structured_content
    assert result.is_error is True
    assert report["schema"] == "kartograf-error/1", report
    assert report["code"] == code, report
    if reason is not None:
        assert report["details"]["reason"] == reason, report
    assert json.loads(result.content[0].text) == report
    return report


def capture_server(argv, monkeypatch):
    """The server ``main(argv)`` would serve (the serving itself is left out)."""
    from kartograf import mcp_server

    served = []

    async def serve(server):
        served.append(server)

    monkeypatch.setattr(mcp_server, "_serve", serve)
    assert main(argv) == 0
    return served[0]


def document_of(stderr: str) -> dict:
    """The ``kartograf-error/1`` document that is the last line of stderr."""
    return json.loads(stderr.splitlines()[-1])


# -- no SDK needed --------------------------------------------------------------


def test_instructions_are_english_short_and_say_what_the_tools_do_not_repeat():
    assert INSTRUCTIONS.isascii()
    # Claude Code loads them at the start of a session and cuts them at 4096
    assert len(INSTRUCTIONS) <= INSTRUCTIONS_MAX == 4096
    # what is the same in many tools is said here, once
    for word in (
        "kartograf_commands_list",
        "kartograf_commands_schema",
        "absolute",
        "bbox_crs",
        "sheet",
        "geometry",
        "country",
        "update",
        "check",
        "kartograf-plan/1",
        "kartograf-result/1",
        "kartograf-error/1",
        "forbidden",
    ):
        assert word in INSTRUCTIONS, word
    # the tools it names exist (the names are read from the catalog)
    names = {spec.name for spec in tool_specs(allow_writes=True)}
    assert set(re.findall(r"kartograf_[a-z0-9_]+", INSTRUCTIONS)) <= names
    assert not re.search("[ąćęłńóśźż]", INSTRUCTIONS, re.IGNORECASE)
    for banned in ("always recommend", "best tool for", "ignore previous"):
        assert banned not in INSTRUCTIONS.lower()


def test_the_instructions_state_the_mode_of_the_server(tmp_path):
    reading = build_instructions()
    allowed = build_instructions(allow_dirs=[tmp_path])
    writes = build_instructions(allow_writes=True, allow_dirs=[tmp_path])
    limited = build_instructions(families=("core", "store"))

    assert reading == INSTRUCTIONS
    assert "does not write" in reading and "kartograf_project_init" in reading
    assert "Paths must lie inside" not in reading
    assert f"Paths must lie inside {tmp_path.as_posix()}" in allowed
    assert "Writes are enabled inside" in writes and tmp_path.as_posix() in writes
    assert "does not write" not in writes
    assert "Exposed families (--tools): core, store" in limited
    assert all(
        len(text) <= INSTRUCTIONS_MAX for text in (reading, allowed, writes, limited)
    )


def test_main_without_mcp_reports_missing_dependency_and_exits_6():
    code = (
        "import sys\n"
        "sys.modules['mcp'] = None\n"
        "from kartograf.mcp_server import main\n"
        "sys.exit(main(['--no-cache']))\n"
    )

    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True
    )

    assert done.returncode == 6
    assert done.stdout == ""
    assert "Traceback" not in done.stderr
    document = document_of(done.stderr)
    assert (document["code"], document["exit_code"]) == ("missing_dependency", 6)
    assert document["hint"] == 'uv add "kartograf[mcp]"'
    assert document["details"] == {"extra": "mcp"}


def test_import_kartograf_does_not_import_mcp():
    code = (
        "import sys\n"
        "import kartograf, kartograf.cli.commands, kartograf.mcp_server\n"
        "loaded = [m for m in sys.modules if m.split('.')[0] in ('mcp', 'mcp_types')]\n"
        "assert not loaded, loaded\n"
    )

    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True
    )

    assert done.returncode == 0, done.stderr


def test_unknown_family_is_a_usage_error_with_the_error_document(capsys):
    assert main(["--tools", "discovery,nope"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""  # stdout belongs to the protocol
    assert "Error: argument --tools: unknown tool family: 'nope'" in captured.err
    document = document_of(captured.err)
    assert (document["code"], document["exit_code"]) == ("validation_error", 2)
    assert document["details"]["reason"] == "usage"


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--version"])

    assert caught.value.code == 0
    assert capsys.readouterr().out.strip() == f"kartograf-mcp {kartograf.__version__}"


def test_cache_flags_exclude_each_other(capsys):
    assert main(["--cache-file", "x.db", "--no-cache"]) == 2

    assert "not allowed with argument --cache-file" in capsys.readouterr().err


@pytest.mark.parametrize("directory", ["data", ".", "../data", "./a/b"])
def test_a_relative_allow_dir_stops_the_start_with_a_usage_error(directory, capsys):
    """A relative directory would stand for the working directory the client chose
    for the server; the paths of the calls are absolute, so the flag is too."""
    assert main(["--no-cache", "--allow-dir", directory]) == 2

    error = capsys.readouterr().err
    assert "--allow-dir needs an absolute path" in error
    assert repr(directory) in error
    assert document_of(error)["code"] == "validation_error"


def test_allow_dir_takes_an_absolute_directory_and_the_home_shortcut(tmp_path):
    args = _parser().parse_args(["--allow-dir", str(tmp_path), "--allow-dir", "~/dane"])

    assert args.allow_dir == [tmp_path.resolve(), Path("~/dane").expanduser().resolve()]


def test_allow_writes_needs_a_directory_to_write_in(tmp_path, capsys):
    assert main(["--no-cache", "--allow-writes"]) == 2

    error = capsys.readouterr().err
    document = document_of(error)
    assert document["code"] == "validation_error"
    assert document["details"]["option"] == "allow_writes"
    assert document["details"]["options"] == ["allow_writes", "allow_dirs"]
    assert "--allow-writes and --allow-dir" in document["hint"]
    with pytest.raises(ValidationError) as caught:
        create_server(cache=False, allow_writes=True)
    assert caught.value.option == "allow_writes"


@pytest.mark.parametrize(
    ("kwargs", "option"),
    [
        ({"families": ["discovery", "nope"]}, "families"),
        ({"families": []}, "families"),
        ({"allow_dirs": ["data"]}, "allow_dirs"),
        ({"cache": True}, "cache"),
    ],
)
def test_create_server_refuses_what_it_cannot_serve(kwargs, option, tmp_path):
    database = tmp_path / "cache.db"
    kwargs = {"cache": database, **kwargs}  # opened only after the checks

    with pytest.raises(ValidationError) as caught:
        create_server(**kwargs)

    assert caught.value.option == option
    assert not database.exists()


def test_the_start_line_says_how_the_server_started(tmp_path, monkeypatch, capsys):
    capture_server(
        [
            "--no-cache",
            "--allow-writes",
            "--allow-dir",
            str(tmp_path),
            "--tools",
            "core,store",
        ],
        monkeypatch,
    )

    assert capsys.readouterr().err == (
        f"kartograf-mcp {kartograf.__version__}: stdio, writes on, "
        f"allow-dir {tmp_path.resolve().as_posix()}, tools core,store\n"
    )


def test_the_server_does_not_start_with_settings_that_cannot_be_used(
    tmp_path, monkeypatch, capsys
):
    """Like the CLI, the server stops instead of ignoring an unusable nogat.toml; the
    error document is the last line of stderr. The check comes before the import of
    the SDK, so the test needs no ``mcp`` package."""
    bad = tmp_path / "nogat.toml"
    bad.write_bytes(b"\xff\xfe[\x00k\x00]\x00")  # UTF-16, not UTF-8
    monkeypatch.setenv("NOGAT_CONFIG", str(bad))

    with pytest.raises(ConfigError):
        create_server(cache=False)
    assert main(["--no-cache"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    document = document_of(captured.err)
    assert (document["code"], document["exit_code"]) == ("validation_error", 2)
    assert document["details"] == {
        "reason": "invalid_config",
        "option": "NOGAT_CONFIG",
        "path": bad.as_posix(),
    }


def test_default_cache_file_is_the_default_cache_of_the_library(
    tmp_path, monkeypatch, user_environment
):
    expected = user_environment / "cache" / "kartograf" / "metadata.db"
    assert default_cache_file() == default_cache_path() == expected
    # cache_dir of the settings moves it, for the server as for the CLI
    monkeypatch.setenv("KARTOGRAF_CACHE_DIR", str(tmp_path / "own"))
    assert default_cache_file() == tmp_path / "own" / "kartograf" / "metadata.db"


# -- the tools --------------------------------------------------------------------


@needs_mcp
def test_server_identity_and_instructions(tmp_path):
    async def scenario(client):
        return client.server_info, client.instructions

    info, instructions = run_session(scenario)
    _, in_a_directory = run_session(scenario, **writing(tmp_path))
    _, limited = run_session(scenario, families=["core"])

    assert (info.name, info.version, info.title) == (
        "kartograf",
        kartograf.__version__,
        "Kartograf",
    )
    assert instructions == INSTRUCTIONS
    assert in_a_directory == build_instructions(
        allow_writes=True, allow_dirs=[tmp_path.resolve()]
    )
    assert limited == build_instructions(families=["core"])


def hints_of(annotations):
    return (
        annotations.title,
        annotations.read_only_hint,
        annotations.destructive_hint,
        annotations.idempotent_hint,
        annotations.open_world_hint,
    )


@needs_mcp
@pytest.mark.parametrize("mode", ["plans", "writes"])
def test_list_tools_equals_tool_specs(mode, tmp_path):
    async def scenario(client):
        return (await client.list_tools()).tools

    arguments = writing(tmp_path) if mode == "writes" else {}
    tools = run_session(scenario, **arguments)
    specs = tool_specs(allow_writes=mode == "writes")

    assert len(tools) == (40 if mode == "writes" else 37)
    assert [t.name for t in tools] == [s.name for s in specs]
    for tool, spec in zip(tools, specs, strict=True):
        assert tool.title == spec.title
        assert tool.description == spec.description
        assert tool.input_schema == spec.input_schema
        assert tool.output_schema == spec.output_schema == OUTPUT_SCHEMA
        assert hints_of(tool.annotations) == (
            spec.annotations.title,
            spec.annotations.read_only_hint,
            spec.annotations.destructive_hint,
            spec.annotations.idempotent_hint,
            spec.annotations.open_world_hint,
        )
        assert tool.meta == ({ALWAYS_LOAD_KEY: True} if spec.always_load else None)


@needs_mcp
def test_a_server_that_does_not_write_lists_plans_and_leaves_out_three_tools():
    async def scenario(client):
        return {t.name: t for t in (await client.list_tools()).tools}

    tools = run_session(scenario)

    assert not {
        "kartograf_project_init",
        "kartograf_project_add",
        "kartograf_project_remove",
    } & set(tools)
    plan = tools["kartograf_elevation_download"]
    properties = plan.input_schema["properties"]
    assert plan.annotations.read_only_hint is True
    assert not {"update", "plan", "workers", "summary"} & set(properties)
    assert properties["check"]["const"] is True
    assert plan.description.endswith("This server only plans: nothing is written.")
    # what only reads is the same in both modes
    assert tools["kartograf_store_overview"].annotations.read_only_hint is True


@needs_mcp
def test_the_tools_flag_core_is_the_ten_tools_of_the_main_tasks(monkeypatch):
    server = capture_server(["--tools", "core", "--no-cache"], monkeypatch)

    async def scenario(client):
        return [t.name for t in (await client.list_tools()).tools]

    names = run_session(scenario, server=server)

    assert len(names) == 10  # AGI-5.12
    assert names == [s.name for s in tool_specs(("core",), allow_writes=False)]
    assert "kartograf_commands_list" in names and "kartograf_soil_hsg" in names


DISCOVERY = [
    (
        "kartograf_commands_schema",
        {"command": "elevation download"},
        lambda: kartograf.command_schema("elevation download"),
        "commands schema",
    ),
    ("kartograf_commands_list", {}, lambda: kartograf.list_commands(), "commands list"),
    (
        "kartograf_sheet_parse",
        {"sheet": SHEET, "hierarchy": True, "descendants": "1:5000"},
        lambda: kartograf.describe_sheet(SHEET, hierarchy=True, descendants="1:5000"),
        "sheet parse",
    ),
    (
        "kartograf_elevation_list_sources",
        {"product": "nmt"},
        lambda: kartograf.list_sources(group="elevation", product="nmt"),
        "elevation list-sources",
    ),
    (
        "kartograf_soil_list_layers",
        {},
        lambda: kartograf.list_layers(group="soil"),
        "soil list-layers",
    ),
    (
        "kartograf_sheet_find",
        {
            "bbox": [AREA.min_x, AREA.min_y, AREA.max_x, AREA.max_y],
            "bbox_crs": "EPSG:4326",
            "scale": "1:200000",
            "sheet_system": "1992",
        },
        lambda: kartograf.find_sheets(bbox=AREA, scale="1:200000", sheet_system="1992"),
        "sheet find",
    ),
]


@needs_mcp
@pytest.mark.parametrize(
    ("tool", "arguments", "document", "command"),
    DISCOVERY,
    ids=lambda x: x if isinstance(x, str) else "",
)
def test_discovery_tools_return_the_envelope_of_the_library_documents(
    tool, arguments, document, command
):
    expected = wrap(command, document())

    result = call(tool, arguments)

    assert result.is_error is False
    assert result.structured_content == expected.to_dict()
    assert result.content[0].text == expected.to_json(indent=None)
    assert len(result.content) == 1


@needs_mcp
@pytest.mark.usefixtures("frozen_clock")
def test_data_tool_result_equals_the_envelope_of_the_library_document(tmp_path):
    with pl_sheets():
        direct = wrap(
            "elevation download",
            download_data(**PL_SHEET, root=tmp_path / "lib", cache=False),
        )
    with pl_sheets():
        result = call(
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path / "mcp")},
            **writing(tmp_path),
        )

    assert result.is_error is False
    envelope = result.structured_content
    document = envelope["result"]
    assert envelope["schema"] == "kartograf-result/1" and envelope["status"] == "ok"
    assert envelope["check"] is False
    assert document["schema"] == "kartograf-download/1" and document["ok"] is True
    assert normal(envelope, tmp_path / "mcp") == normal(
        direct.to_dict(), tmp_path / "lib"
    )
    assert result.content[0].text.replace(str(tmp_path / "mcp"), "<store>") == (
        direct.to_json(indent=None).replace(str(tmp_path / "lib"), "<store>")
    )
    (item,) = document["files"]
    assert Path(item["path"]).is_file()  # the version is in the store
    assert Path(item["path"]).is_relative_to(tmp_path / "mcp")


@needs_mcp
@pytest.mark.usefixtures("frozen_clock")
def test_ok_false_is_a_result_with_the_status_of_its_units(tmp_path):
    failing = FakeCampaignProvider(C14, fail_urls={C14["newest"][0].url})
    with pl_sheets(failing):
        report = download_data(**PL_SHEET, root=tmp_path / "lib", cache=False)
        result = call(
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path / "mcp")},
            **writing(tmp_path),
        )

    direct = wrap("elevation download", report)
    assert report.ok is False and direct.exit_code == 11  # the CLI exits with 11
    assert result.is_error is False  # an outcome, not an error (AGI-5.7)
    envelope = result.structured_content
    document = envelope["result"]
    assert (envelope["status"], envelope["items"][0]["status"]) == ("failed", "failed")
    assert document["schema"] == "kartograf-download/1" and document["ok"] is False
    assert document["failed"]
    assert normal(envelope, tmp_path / "mcp") == normal(
        direct.to_dict(), tmp_path / "lib"
    )


@needs_mcp
@pytest.mark.usefixtures("frozen_clock")
@pytest.mark.parametrize("mode", ["plans", "writes"])
def test_check_equals_check_command(mode, tmp_path):
    """The plan of a server that writes (``check`` true) and the plan of a
    server that does not (the only thing it does, so the argument may be left out)
    are the document of ``check_command``."""
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    with pl_sheets(fake):
        for store in ("lib", "mcp"):
            run_command(
                "elevation download", PL_SHEET, root=tmp_path / store, cache=False
            )
    fake.records = {"newest": [REC["84183"]]}
    arguments = {**PL_SHEET, "root": str(tmp_path / "mcp")}
    if mode == "writes":
        arguments["check"] = True
    with pl_sheets(fake):
        direct = check_command(
            "elevation download", PL_SHEET, root=tmp_path / "lib", cache=False
        )
        result = call(
            "kartograf_elevation_download",
            arguments,
            **(writing(tmp_path) if mode == "writes" else {}),
        )

    assert result.is_error is False
    envelope = result.structured_content
    plan = envelope["result"]
    assert envelope["check"] is True and envelope["command"] == "elevation download"
    assert plan["schema"] == "kartograf-plan/1" and plan["ok"] is True
    assert [item["status"] for item in plan["items"]] == ["newer"]
    assert normal(envelope, tmp_path / "mcp") == normal(
        direct.to_dict(), tmp_path / "lib"
    )
    assert result.content[0].text.replace(str(tmp_path / "mcp"), "<store>") == (
        direct.to_json(indent=None).replace(str(tmp_path / "lib"), "<store>")
    )


@needs_mcp
@pytest.mark.usefixtures("frozen_clock")
def test_a_plan_document_and_update_upgrade_reach_the_library(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    with pl_sheets(fake):
        for store in ("lib", "mcp"):
            run_command(
                "elevation download", PL_SHEET, root=tmp_path / store, cache=False
            )
    fake.records = {"newest": [REC["84183"]]}
    server = writing(tmp_path)
    with pl_sheets(fake):
        library_plan = check_command(
            "elevation download", PL_SHEET, root=tmp_path / "lib", cache=False
        )
        direct = run_command(
            "elevation download",
            PL_SHEET,
            root=tmp_path / "lib",
            update="upgrade",
            plan=library_plan.result,
            cache=False,
        )
        checked = call(
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path / "mcp"), "check": True},
            **server,
        )
        upgraded = call(
            "kartograf_elevation_download",
            {
                **PL_SHEET,
                "root": str(tmp_path / "mcp"),
                "update": "upgrade",
                "plan": checked.structured_content["result"],
            },
            **server,
        )

    assert upgraded.is_error is False
    (new,) = upgraded.structured_content["result"]["files"]
    assert new["status"] == "new"
    assert new["label"].startswith("2025-10-21_84183")
    assert normal(upgraded.structured_content, tmp_path / "mcp") == normal(
        direct.to_dict(), tmp_path / "lib"
    )


@needs_mcp
def test_summary_is_an_argument_of_the_run_not_of_the_task(tmp_path):
    hsg = {"sheet": HSG_SHEET, "depth": "0-5cm"}
    with landcover_sources(soilgrids=RasterSoilGrids):
        direct = calculate_hsg(root=tmp_path / "lib", cache=False, summary=True, **hsg)
        with_summary = call(
            "kartograf_soil_hsg",
            {**hsg, "root": str(tmp_path / "a"), "summary": True},
            **writing(tmp_path),
        )
        without = call(
            "kartograf_soil_hsg",
            {**hsg, "root": str(tmp_path / "b")},
            **writing(tmp_path),
        )

    assert with_summary.is_error is False
    assert with_summary.structured_content["result"]["summary"] == direct.summary
    assert set(with_summary.structured_content["result"]["summary"]) == {
        "A",
        "B",
        "C",
        "D",
        "nodata",
    }
    assert without.structured_content["result"]["summary"] is None


@needs_mcp
def test_check_refuses_the_options_of_a_run(tmp_path):
    here = str(tmp_path)
    selection = {**PL_SHEET, "root": here, "check": True}
    hsg = {"depth": "0-5cm", "sheet": HSG_SHEET, "root": here}
    project = {"project_dir": here, "check": True}
    cases = [
        ("kartograf_elevation_download", selection | {"update": "upgrade"}, "update"),
        ("kartograf_elevation_download", selection | {"plan": {}}, "plan"),
        ("kartograf_elevation_download", selection | {"workers": 2}, "workers"),
        (
            "kartograf_soil_hsg",
            hsg | {"summary": True, "check": True},
            "summary",
        ),
        ("kartograf_project_download", project | {"update": "upgrade"}, "update"),
        ("kartograf_project_download", project | {"workers": 2}, "workers"),
    ]

    for tool, arguments, option in cases:
        report = error_of(call(tool, arguments, **writing(tmp_path)))

        assert report["details"]["option"] == option, arguments
        assert report["details"]["options"] == ["check", option]
        assert "Drop check to run" in report["hint"]
        assert report["exit_code"] == 2
    assert list(tmp_path.iterdir()) == []  # a plan writes nothing


@needs_mcp
def test_check_input_errors(tmp_path):
    here = str(tmp_path)
    selection = {**PL_SHEET, "root": here, "check": True}
    cases = [
        (selection | {"root": "rel"}, "root"),
        (selection | {"check": "yes"}, "check"),
        ({"root": here, "check": True}, "product"),
    ]

    for arguments, option in cases:
        report = error_of(
            call("kartograf_elevation_download", arguments, **writing(tmp_path))
        )

        assert report["details"]["option"] == option, arguments
        assert report["command"] == "elevation download"
        assert report["exit_code"] == 2
    # a rule of the library, checked without network and without writing
    report = error_of(
        call(
            "kartograf_elevation_download",
            {"product": "nmt", "root": here, "check": True},
            **writing(tmp_path),
        )
    )
    assert report["command"] == "elevation download"
    assert report["details"]["options"] == ["sheet", "bbox", "geometry"]
    assert list(tmp_path.iterdir()) == []


@needs_mcp
@pytest.mark.parametrize(
    ("tool", "arguments", "option", "command"),
    [
        (
            "kartograf_elevation_download",
            {"product": "nmt", "root": "rel/dir"},
            "root",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {"product": "nmt", "root": "ABS", "nope": 1},
            "nope",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {"product": "xx", "root": "ABS"},
            "product",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {"product": "nmt", "bbox": [1, 2, 3, 4], "root": "ABS"},
            "bbox_crs",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {"root": "ABS"},
            "product",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {"product": "nmt", "root": "ABS", "workers": 0},
            "workers",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {
                "product": "nmt",
                "root": "ABS",
                "bbox": [1, 2, 3],
                "bbox_crs": "EPSG:2180",
            },
            "bbox",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {"product": "nmt", "root": "ABS", "resolution": 5},
            "resolution",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {"product": "nmt", "root": "ABS", "vertical_crs": 5},
            "vertical_crs",
            "elevation download",
        ),
        (
            "kartograf_elevation_download",
            {"product": "nmt", "root": "ABS", "plan": {"schema": "other/1"}},
            "plan",
            "elevation download",
        ),
        ("kartograf_sheet_parse", {"sheet": 5}, "sheet", "sheet parse"),
        (
            "kartograf_elevation_list_sources",
            {"group": "nope"},
            "group",
            "elevation list-sources",
        ),
        (
            "kartograf_elevation_list_sources",
            {"product": "orto"},
            "product",
            "elevation list-sources",
        ),
        (
            "kartograf_store_overview",
            {"root": "relative"},
            "root",
            "store overview",
        ),
        ("kartograf_store_sidecar", {"path": "x.meta.json"}, "path", "store sidecar"),
        (
            "kartograf_project_status",
            {"project_dir": "."},
            "project_dir",
            "project status",
        ),
        (
            "kartograf_commands_schema",
            {"command": "nope nope"},
            "command",
            "commands schema",
        ),
    ],
)
def test_input_errors_are_error_documents(tmp_path, tool, arguments, option, command):
    arguments = {k: str(tmp_path) if v == "ABS" else v for k, v in arguments.items()}

    report = error_of(call(tool, arguments, **writing(tmp_path)))

    assert report["exit_code"] == 2 and report.get("command") == command
    assert report["details"].get("option") == option
    assert report["message"].isascii() and (report["hint"] or "").isascii()
    assert list(tmp_path.iterdir()) == []  # nothing was written


@needs_mcp
@pytest.mark.parametrize(
    "spec",
    tool_specs(("data",), allow_writes=True),
    ids=lambda s: s.name,
)
def test_every_data_tool_runs_its_own_command(tmp_path, spec):
    """Without an area the library refuses every data command: the answer names
    the command the tool stands for, for a run, for ``check`` and for a
    server that only plans."""
    arguments = {"root": str(tmp_path)}
    properties = spec.input_schema["properties"]
    if "product" in properties:
        arguments["product"] = properties["product"]["enum"][0]
    if "depth" in spec.input_schema["required"]:
        arguments["depth"] = properties["depth"]["enum"][0]

    run = error_of(call(spec.name, arguments, **writing(tmp_path)))
    check = error_of(call(spec.name, {**arguments, "check": True}, **writing(tmp_path)))
    plan = error_of(call(spec.name, arguments))

    assert run["command"] == check["command"] == plan["command"] == spec.command
    assert run["exit_code"] == check["exit_code"] == plan["exit_code"] == 2
    assert run["details"] and run["details"] == check["details"] == plan["details"]
    assert list(tmp_path.iterdir()) == []  # no network, nothing written


@needs_mcp
def test_a_bad_sheet_code_is_invalid_sheet_code():
    report = error_of(
        call("kartograf_sheet_parse", {"sheet": "not-a-sheet"}),
        reason="invalid_sheet_code",
    )

    assert report["exit_code"] == 2 and report["command"] == "sheet parse"
    assert report["details"]["option"] == "sheet"


@needs_mcp
def test_input_error_hints_name_the_fix(tmp_path):
    relative = error_of(call("kartograf_store_overview", {"root": "relative"}))
    bad_enum = error_of(
        call(
            "kartograf_elevation_download",
            {"product": "xx", "root": str(tmp_path)},
        )
    )
    unknown = error_of(
        call(
            "kartograf_elevation_download",
            {"product": "nmt", "root": str(tmp_path), "nope": 1},
        )
    )
    companion = error_of(
        call(
            "kartograf_elevation_download",
            {"product": "nmt", "root": str(tmp_path), "bbox": [1, 2, 3, 4]},
        )
    )

    assert "Give an absolute path" in relative["hint"]
    assert bad_enum["details"]["allowed"] == ["nmt", "nmpt", "laz", "contours"]
    assert "nmpt" in bad_enum["hint"]
    assert "product" in unknown["hint"] and "root" in unknown["hint"]
    assert companion["details"]["options"] == ["bbox", "bbox_crs"]
    assert "--bbox-crs" in companion["hint"]


@needs_mcp
def test_input_error_hint_example_is_of_the_product_and_country_of_the_call(tmp_path):
    # E2E 0.8.0 D P3-7: the same call as in the CLI, the same example
    report = error_of(
        call(
            "kartograf_boundaries_download",
            {
                "product": "admin",
                "country": "auto",
                "level": "gmina",
                "bbox": [18.6, 49.7, 18.7, 49.8],
                "bbox_crs": "EPSG:4326",
                "root": str(tmp_path),
            },
            **writing(tmp_path),
        )
    )

    assert report["details"]["option"] == "level"
    assert "--country auto" in report["hint"] and "--product admin" in report["hint"]


@needs_mcp
def test_oserror_is_io_error(tmp_path):
    missing = tmp_path / "missing"

    report = error_of(
        call("kartograf_store_overview", {"root": str(missing)}), code="io_error"
    )

    assert report["exit_code"] == 9 and report["command"] == "store overview"
    assert report["details"] == {"errno": "ENOENT", "path": str(missing)}


@needs_mcp
def test_foreign_exception_is_internal_error(tmp_path, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise KeyError("boom")

    monkeypatch.setattr(kartograf, "describe_store", broken)

    result = call("kartograf_store_overview", {"root": str(tmp_path)})

    report = error_of(result, code="internal_error")
    assert report["message"] == "KeyError: 'boom'" and report["exit_code"] == 1
    assert "Traceback" not in result.content[0].text
    assert "KeyError" in caplog.text and "Traceback" in caplog.text  # the log has it


@needs_mcp
def test_unknown_tool_is_a_protocol_error():
    from mcp.shared.exceptions import MCPError
    from mcp_types import INVALID_PARAMS

    async def scenario(client):
        errors = []
        for name in ("nope", "kartograf_elevation_downlod", "elevation_download"):
            try:
                await client.call_tool(name, {})
            except MCPError as error:  # the one failure that is not a result
                errors.append(error)
        return errors

    errors = run_session(scenario)

    assert [e.code for e in errors] == [INVALID_PARAMS] * 3
    assert "'nope'" in errors[0].message and "Did you mean" not in errors[0].message
    assert "Did you mean: kartograf_elevation_download" in errors[1].message
    # the name of the old tools points to the new one
    assert "Did you mean: kartograf_elevation_download" in errors[2].message


@needs_mcp
def test_a_tool_that_writes_and_is_not_offered_answers_forbidden(tmp_path):
    """``project init``, ``project add`` and ``project remove`` have no plan: on a
    server that does not write they are not listed and a call is ``forbidden``,
    not an unknown tool (a client with a cached list may still call them)."""
    calls = [
        ("kartograf_project_init", {"project_dir": "p", "root": "s"}),
        ("kartograf_project_add", {}),
        ("kartograf_project_remove", {"project_dir": str(tmp_path)}),
    ]

    for tool, arguments in calls:
        report = error_of(call(tool, arguments), code="forbidden")

        assert report["exit_code"] == 12
        assert report["command"] == tool.removeprefix("kartograf_").replace("_", " ")
        assert FORBIDDEN_HINT in report["hint"]
        assert "does not write" in report["message"]
    assert list(tmp_path.iterdir()) == []
    # a family the hidden tool is not in does not know it either
    from mcp.shared.exceptions import MCPError

    async def scenario(client):
        try:
            await client.call_tool("kartograf_project_init", {})
        except MCPError as error:
            return error
        return None

    error = run_session(scenario, families=["core"])
    assert (
        error is not None and "Unknown tool 'kartograf_project_init'" in error.message
    )
    # the server that writes lists and runs them
    done = call(
        "kartograf_project_init",
        {"project_dir": str(tmp_path / "p"), "root": str(tmp_path / "s")},
        **writing(tmp_path),
    )
    assert done.is_error is False


@needs_mcp
@pytest.mark.parametrize(
    ("tool", "option", "value"),
    [
        ("kartograf_elevation_download", "update", "force"),
        ("kartograf_elevation_download", "plan", {}),
        ("kartograf_elevation_download", "workers", 2),
        ("kartograf_soil_hsg", "summary", True),
        ("kartograf_elevation_download", "check", False),
        ("kartograf_project_download", "update", "upgrade"),
        ("kartograf_project_download", "workers", 2),
    ],
)
def test_a_server_that_does_not_write_refuses_a_run_with_forbidden(
    tmp_path, tool, option, value
):
    base = {
        "kartograf_elevation_download": {**PL_SHEET, "root": str(tmp_path)},
        "kartograf_soil_hsg": {
            "depth": "0-5cm",
            "sheet": HSG_SHEET,
            "root": str(tmp_path),
        },
        "kartograf_project_download": {"project_dir": str(tmp_path)},
    }[tool]

    report = error_of(call(tool, {**base, option: value}), code="forbidden")

    assert report["exit_code"] == 12
    assert report["details"] == {"reason": "writes_disabled", "option": option}
    assert report["command"] == tool.removeprefix("kartograf_").replace("_", " ", 1)
    assert FORBIDDEN_HINT in report["hint"] and "check=true" in report["hint"]
    assert list(tmp_path.iterdir()) == []  # nothing was fetched or written


@needs_mcp
def test_a_server_that_does_not_write_plans_what_a_run_would_do(tmp_path):
    """The call a client makes with the arguments of a run, left as they are, is the
    plan (``check`` true); the options of a run it leaves out are not needed."""
    with landcover_sources(soilgrids=RasterSoilGrids):
        result = call(
            "kartograf_soil_hsg",
            {"sheet": HSG_SHEET, "depth": "0-5cm", "root": str(tmp_path)},
        )

    assert result.is_error is False
    envelope = result.structured_content
    assert (envelope["check"], envelope["command"]) == (True, "soil hsg")
    assert envelope["result"]["schema"] == "kartograf-plan/1"
    assert list(tmp_path.iterdir()) == []


HSG = {"sheet": HSG_SHEET, "depth": "0-5cm"}


@needs_mcp
def test_a_writing_server_writes_plain_files_and_plans_the_replacement(tmp_path):
    out = tmp_path / "plain"
    with landcover_sources(soilgrids=RasterSoilGrids):
        written = call(
            "kartograf_soil_hsg", {**HSG, "output_dir": str(out)}, **writing(tmp_path)
        )

    assert written.is_error is False
    report = written.structured_content["result"]
    assert (report["mode"], report["root"], report["output_dir"]) == (
        "plain",
        None,
        str(out),
    )
    (entry,) = report["files"]
    assert entry["status"] == "written" and entry["path"].startswith(str(out))
    assert [p.suffix for p in out.iterdir()] == [".tif"]  # the raster and nothing else
    # a server that does not write plans the call as it stands: the file is a conflict;
    # with update=force (a server that writes) the plan says replace
    with landcover_sources(soilgrids=RasterSoilGrids):
        plan = call("kartograf_soil_hsg", {**HSG, "output_dir": str(out)})
        forced = call(
            "kartograf_soil_hsg",
            {**HSG, "output_dir": str(out), "check": True, "update": "force"},
            **writing(tmp_path),
        )

    plans = [r.structured_content["result"] for r in (plan, forced)]
    assert [p["mode"] for p in plans] == ["plain", "plain"]
    assert [[i["action"] for i in p["items"]] for p in plans] == [
        ["conflict"],
        ["replace"],
    ]
    assert [p.name for p in out.iterdir()] == [Path(entry["path"]).name]


@needs_mcp
def test_output_dir_is_confined_like_every_path_and_excludes_root(tmp_path):
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()

    refused = call(
        "kartograf_soil_hsg",
        {**HSG, "output_dir": str(outside)},
        **writing(allowed),
    )
    both = call(
        "kartograf_soil_hsg",
        {**HSG, "output_dir": str(allowed / "a"), "root": str(allowed / "b")},
        **writing(allowed),
    )

    forbidden = error_of(refused, code="forbidden", reason="outside_allowed_dirs")
    assert (forbidden["details"]["option"], forbidden["exit_code"]) == (
        "output_dir",
        12,
    )
    exclusive = error_of(both, reason="exclusive_options")
    assert exclusive["details"]["options"] == ["output_dir", "root"]
    assert list(tmp_path.iterdir()) == [allowed] and list(allowed.iterdir()) == []


@needs_mcp
def test_a_plan_only_project_download_calls_the_check_of_the_library(
    tmp_path, monkeypatch
):
    seen = []

    def check(project_dir, *, cache, **kwargs):
        seen.append((project_dir, {**kwargs, "cache": cache}))
        return kartograf.command_schema("commands list")

    def download(*args, **kwargs):
        raise AssertionError("a server that does not write must not download")

    monkeypatch.setattr(kartograf, "check_project", check)
    monkeypatch.setattr(kartograf, "download_project", download)

    result = call("kartograf_project_download", {"project_dir": str(tmp_path)})

    assert result.is_error is False
    assert result.structured_content["check"] is True
    assert seen == [(tmp_path, {"cache": False})]


@needs_mcp
def test_progress_is_strictly_increasing(tmp_path):
    """Events from four threads with the same ``current`` reach the client as
    1, 2, 3, ... with the text of the event; the total stays unknown."""
    calls = []

    def download(command, options, *, root, on_progress, **kwargs):
        calls.append(command)

        def work(worker):
            for _ in range(5):
                on_progress(DownloadProgress(1, 3, f"N-{worker}", "downloading"))
            on_progress(DownloadProgress(1, 3, f"N-{worker}", "failed", "blad \u0142"))

        with ThreadPoolExecutor(4) as pool:
            list(pool.map(work, range(4)))
        return EMPTY_RESULT

    received = []

    async def on_progress(progress, total, message):
        received.append((progress, total, message))

    with patch("kartograf.mcp_server.run_command", download):
        result = call(
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path)},
            progress=on_progress,
            **writing(tmp_path),
        )

    assert result.is_error is False and calls == ["elevation download"]
    assert [p for p, _, _ in received] == list(range(1, 25))
    assert {t for _, t, _ in received} == {None}
    texts = [m for _, _, m in received]
    assert texts.count("downloading N-0 (1/3)") == 5
    assert "failed N-3 (1/3): blad \\u0142" in texts  # ASCII only
    assert all(isinstance(m, str) and m.isascii() for m in texts)


@needs_mcp
def test_a_tool_without_progress_sends_none(tmp_path):
    received = []

    async def on_progress(progress, total, message):
        received.append(progress)

    result = call(
        "kartograf_store_overview", {"root": str(tmp_path)}, progress=on_progress
    )

    assert result.is_error is False and received == []


@needs_mcp
def test_allow_dir_rejects_paths_outside_after_resolve(tmp_path):
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (allowed / "link").symlink_to(outside, target_is_directory=True)

    inside = call(
        "kartograf_store_overview", {"root": str(allowed)}, allow_dirs=[allowed]
    )
    assert inside.is_error is False

    for path in (outside, allowed / "link", allowed / ".." / "outside"):
        report = error_of(
            call(
                "kartograf_store_overview",
                {"root": str(path)},
                allow_dirs=[allowed],
            ),
            code="forbidden",
        )
        assert report["exit_code"] == 12
        assert report["details"]["option"] == "root"
        assert report["details"]["path"] == str(outside.resolve())
        assert report["details"]["allowed"] == [str(allowed.resolve())]
        assert str(allowed) in report["hint"]
    # the same rule for a plan, which has the paths of a run
    planned = call(
        "kartograf_elevation_download",
        {**PL_SHEET, "root": str(outside)},
        allow_dirs=[allowed],
    )
    assert error_of(planned, code="forbidden")["details"]["option"] == "root"
    # and for the paths nested in a call
    task = call(
        "kartograf_project_add",
        {
            "project_dir": str(allowed),
            "name": "t",
            "command": "elevation download",
            "options": {"product": "nmt", "geometry": str(outside / "area.gpkg")},
        },
        **writing(allowed),
    )
    assert error_of(task, code="forbidden")["details"]["option"] == "geometry"
    # reading a file of the store is confined as well
    sidecar = call(
        "kartograf_store_sidecar",
        {"path": str(outside / "a.meta.json")},
        allow_dirs=[allowed],
    )
    assert error_of(sidecar, code="forbidden")["details"]["option"] == "path"


@needs_mcp
def test_a_server_without_allow_dir_reads_any_absolute_path(tmp_path):
    result = call("kartograf_store_overview", {"root": str(tmp_path)})

    assert result.is_error is False


@needs_mcp
def test_a_relative_path_inside_task_options_is_refused(tmp_path):
    report = error_of(
        call(
            "kartograf_project_add",
            {
                "project_dir": str(tmp_path),
                "name": "t",
                "command": "elevation download",
                "options": {"product": "nmt", "geometry": "area.gpkg"},
            },
            **writing(tmp_path),
        )
    )

    assert report["details"]["option"] == "geometry"
    assert "Give an absolute path" in report["hint"]


@needs_mcp
def test_at_most_four_calls_run_at_once(tmp_path):
    import anyio

    state = {"active": 0, "peak": 0}
    gate = threading.Condition()

    def download(command, options, *, root, **kwargs):
        with gate:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            gate.notify_all()
            gate.wait_for(lambda: state["active"] >= 4, timeout=10)
        time.sleep(0.05)
        with gate:
            state["active"] -= 1
        return EMPTY_RESULT

    async def scenario(client):
        results = []

        async def one(number):
            arguments = {**PL_SHEET, "root": str(tmp_path / str(number))}
            results.append(
                await client.call_tool("kartograf_elevation_download", arguments)
            )

        async with anyio.create_task_group() as group:
            for number in range(8):
                group.start_soon(one, number)
        return results

    with patch("kartograf.mcp_server.run_command", download):
        results = run_session(scenario, **writing(tmp_path))

    assert len(results) == 8 and not any(r.is_error for r in results)
    assert state["peak"] == 4 and state["active"] == 0


@needs_mcp
def test_library_does_not_write_to_stdout_during_calls(tmp_path, capfd):
    with pl_sheets():
        call(
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path / "a")},
            **writing(tmp_path),
        )
    call("kartograf_sheet_parse", {"sheet": SHEET})
    call("kartograf_commands_list", {})
    call("kartograf_store_overview", {"root": str(tmp_path / "missing")})
    call("kartograf_elevation_download", {"product": "xx", "root": str(tmp_path)})

    out, _err = capfd.readouterr()

    assert out == ""


@needs_mcp
def test_function_tools_get_library_types_and_the_server_cache(tmp_path, monkeypatch):
    from kartograf.cache.metadata import MetadataCache

    seen = []

    def availability(*, cache, **kwargs):
        seen.append({**kwargs, "cache": cache})
        return kartograf.command_schema("commands list")

    monkeypatch.setattr(kartograf, "check_availability", availability)
    cache = MetadataCache(tmp_path / "cache.db")
    geometry = tmp_path / "area.shp"

    call(
        "kartograf_elevation_availability",
        {
            "product": "nmt",
            "bbox": [1, 2, 3, 4],
            "bbox_crs": "EPSG:2180",
            "geometry": str(geometry),
            "layer": "L",
            "year": 2024,
            "force": True,
        },
        cache=cache,
    )
    call(
        "kartograf_elevation_availability",
        {"product": "laz", "force": False},
        cache=cache,
    )

    assert seen[0] == {
        "product": "nmt",
        "bbox": BBox(1, 2, 3, 4, "EPSG:2180"),
        "geometry": geometry,
        "layer": "L",
        "year": 2024,
        "force": True,
        "cache": cache,  # the cache of the server
    }
    # a flag that is false is not given, and the function reports no progress
    assert seen[1] == {"product": "laz", "cache": cache}


@needs_mcp
def test_project_download_passes_its_arguments_and_reports_progress(
    tmp_path, monkeypatch
):
    seen = []

    def download(project_dir, *, cache, on_progress=None, **kwargs):
        seen.append((project_dir, {**kwargs, "cache": cache}))
        assert on_progress is not None
        on_progress(DownloadProgress(1, 2, "N-1", "downloading"))
        on_progress(DownloadProgress(2, 2, "N-1", "completed"))
        return kartograf.command_schema("commands list")

    monkeypatch.setattr(kartograf, "download_project", download)
    received = []

    async def on_progress(progress, total, message):
        received.append((progress, total, message))

    result = call(
        "kartograf_project_download",
        {
            "project_dir": str(tmp_path),
            "update": "upgrade",
            "workers": 2,
            "tasks": ["a", "b"],
        },
        progress=on_progress,
        **writing(tmp_path),
    )

    assert result.is_error is False
    assert result.structured_content["check"] is False
    assert seen == [
        (
            tmp_path,
            {"update": "upgrade", "workers": 2, "tasks": ("a", "b"), "cache": False},
        )
    ]
    assert received == [
        (1, None, "downloading N-1 (1/2)"),
        (2, None, "completed N-1 (2/2)"),
    ]


@needs_mcp
@pytest.mark.usefixtures("frozen_clock")
def test_project_and_store_tools_work_on_real_files(tmp_path):
    project, store = tmp_path / "project", tmp_path / "store"
    here = {"project_dir": str(project)}
    server = writing(tmp_path)

    def go(tool, arguments):
        return call(tool, arguments, **server)

    init = go("kartograf_project_init", {**here, "root": str(store)})
    added = go(
        "kartograf_project_add",
        {**here, "name": "area", "command": "elevation download", "options": PL_SHEET},
    )
    before = go("kartograf_project_status", here)
    with pl_sheets():
        downloaded = go("kartograf_project_download", here)
        checked = go("kartograf_project_download", {**here, "check": True})
    after = go("kartograf_project_status", here)
    verified = go("kartograf_project_verify", here)

    assert init.structured_content["result"]["schema"] == "kartograf-project-state/1"
    assert [t["name"] for t in added.structured_content["result"]["tasks"]] == ["area"]
    # a task that is not downloaded is ok: false, a result with the status failed
    # (the CLI's exit 11), not an error
    assert before.is_error is False
    assert before.structured_content["status"] == "failed"
    assert before.structured_content["result"]["ok"] is False
    assert before.structured_content["result"]["not_downloaded"] == ["area"]
    assert (
        downloaded.is_error is False and downloaded.structured_content["check"] is False
    )
    result_schema = downloaded.structured_content["result"]["schema"]
    assert result_schema == "kartograf-project-report/1"
    assert checked.is_error is False and checked.structured_content["check"] is True
    assert checked.structured_content["command"] == "project download"
    assert checked.structured_content["result"]["schema"] == "kartograf-project-check/1"
    assert (after.is_error, verified.is_error) == (False, False)
    assert verified.structured_content["result"]["ok"] is True

    overview = go("kartograf_store_overview", {"root": str(store)})
    segment = overview.structured_content["result"]["segments"][0]["segment"]
    entries = go(
        "kartograf_store_entries",
        {"root": str(store), "segment": segment, "limit": 5},
    )
    path = entries.structured_content["result"]["entries"][0]["path"]
    sidecar = go("kartograf_store_sidecar", {"path": path})

    assert (
        overview.structured_content
        == wrap("store overview", kartograf.describe_store(store)).to_dict()
    )
    assert (
        entries.structured_content
        == wrap(
            "store entries",
            kartograf.list_store_entries(store, segment=segment, limit=5),
        ).to_dict()
    )
    assert (
        sidecar.structured_content
        == wrap("store sidecar", kartograf.read_store_sidecar(path)).to_dict()
    )
    for result in (overview, entries, sidecar):
        assert result.is_error is False
    # the store tools take a list of units too, and a limit of one entry truncates
    one = go(
        "kartograf_store_entries",
        {"root": str(store), "segment": segment, "units": [], "limit": 1},
    )
    assert one.is_error is False

    removed = go("kartograf_project_remove", {**here, "name": "area"})
    assert removed.structured_content["result"]["tasks"] == []


@needs_mcp
def test_a_cancelled_call_is_abandoned_not_stopped(tmp_path):
    from mcp.shared.exceptions import MCPError

    release, finished = threading.Event(), threading.Event()

    def download(command, options, *, root, **kwargs):
        release.wait(30)
        finished.set()
        return EMPTY_RESULT

    async def scenario(client):
        arguments = {**PL_SHEET, "root": str(tmp_path)}
        try:
            await client.call_tool(
                "kartograf_elevation_download", arguments, read_timeout_seconds=0.5
            )
        except MCPError as error:  # the client gave up and cancelled the call
            timed_out = error
        parsed = await client.call_tool("kartograf_sheet_parse", {"sheet": SHEET})
        return timed_out, parsed

    # the library check is left out: only the call that is running can be abandoned
    with (
        patch("kartograf.mcp_server.run_command", download),
        patch("kartograf.mcp_server.validate_command"),
    ):
        timed_out, parsed = run_session(scenario, **writing(tmp_path))
        assert not finished.is_set()  # still running when the connection is gone
        release.set()
        assert finished.wait(30)  # nobody stopped the thread

    assert "Timed out" in timed_out.message
    assert parsed.is_error is False  # the server went on


# -- the arguments of the server ----------------------------------------------------


@needs_mcp
def test_tools_flag_selects_families(monkeypatch):
    families = ("discovery", "availability", "data", "store")
    server = capture_server(["--tools", ",".join(families), "--no-cache"], monkeypatch)

    async def scenario(client):
        return [t.name for t in (await client.list_tools()).tools]

    names = run_session(scenario, server=server)

    assert len(names) == 34  # 17 + 1 + 12 + 4: the plans of the data tools
    assert names == [s.name for s in tool_specs(families, allow_writes=False)]


def call_on(server, tool, arguments):
    return call(tool, arguments, server=server)


def _cache_probe(seen):
    """A ``run_command`` that writes a record to the cache it is given."""

    def download(command, options, *, root, cache, **kwargs):
        seen.append(cache)
        if cache is not False:
            cache.set_record("nmt", "1m", "EVRF2007", SHEET, {"no_coverage": True})
        return EMPTY_RESULT

    return download


def writes_in(path: Path) -> list[str]:
    """The arguments of ``kartograf-mcp`` that let it write inside ``path``."""
    return ["--allow-writes", "--allow-dir", str(path)]


@needs_mcp
def test_default_cache_is_created_at_first_use_in_the_cache_dir(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("KARTOGRAF_CACHE_DIR", str(tmp_path / "own"))
    database = tmp_path / "own" / "kartograf" / "metadata.db"

    server = capture_server(writes_in(tmp_path), monkeypatch)
    assert not database.parent.exists()  # the first write makes the directory
    seen = []
    with patch("kartograf.mcp_server.run_command", _cache_probe(seen)):
        result = call_on(
            server,
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path / "s")},
        )

    assert result.is_error is False
    assert seen[0].db_path == database and database.is_file()
    assert list(cwd.iterdir()) == []  # nothing lands in the working directory


@needs_mcp
def test_cache_file_flag(tmp_path, monkeypatch):
    database = tmp_path / "own" / "cache.db"
    seen = []

    server = capture_server(
        ["--cache-file", str(database), *writes_in(tmp_path)], monkeypatch
    )
    with patch("kartograf.mcp_server.run_command", _cache_probe(seen)):
        call_on(
            server,
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path / "s")},
        )

    assert seen[0].db_path == database and database.is_file()


@needs_mcp
def test_a_cache_directory_that_cannot_be_made_does_not_stop_the_server(
    tmp_path, monkeypatch, caplog
):
    """A read-only home or a file in the way: the library works without a cache it
    cannot open (CLI and library warn and go on), and so does the server - it used
    to end at startup with a traceback."""
    (tmp_path / "file").write_text("in the way")
    database = tmp_path / "file" / "sub" / "cache.db"
    seen = []

    server = capture_server(
        ["--cache-file", str(database), *writes_in(tmp_path)], monkeypatch
    )
    with patch("kartograf.mcp_server.run_command", _cache_probe(seen)):
        result = call_on(
            server,
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path / "s")},
        )

    assert result.is_error is False
    assert seen[0].db_path == database and not database.exists()
    assert "cannot be opened or written" in caplog.text


@needs_mcp
def test_no_cache_flag(tmp_path, monkeypatch):
    seen = []

    server = capture_server(["--no-cache", *writes_in(tmp_path)], monkeypatch)
    with patch("kartograf.mcp_server.run_command", _cache_probe(seen)):
        call_on(
            server,
            "kartograf_elevation_download",
            {**PL_SHEET, "root": str(tmp_path / "s")},
        )

    assert seen == [False]


@needs_mcp
def test_allow_dir_flag_is_repeatable(tmp_path, monkeypatch):
    one, two, other = (tmp_path / name for name in ("one", "two", "other"))
    for directory in (one, two, other):
        directory.mkdir()

    server = capture_server(
        ["--no-cache", "--allow-dir", str(one), "--allow-dir", str(two)], monkeypatch
    )

    for directory, refused in ((one, False), (two, False), (other, True)):
        result = call_on(server, "kartograf_store_overview", {"root": str(directory)})
        assert result.is_error is refused


@needs_mcp
def test_allow_writes_flag_lists_the_tools_that_write(tmp_path, monkeypatch):
    server = capture_server(["--no-cache", *writes_in(tmp_path)], monkeypatch)

    async def scenario(client):
        return {t.name: t for t in (await client.list_tools()).tools}

    tools = run_session(scenario, server=server)

    assert len(tools) == 40
    download = tools["kartograf_elevation_download"]
    assert download.annotations.read_only_hint is False
    assert download.annotations.destructive_hint is False
    assert {"update", "plan", "workers"} <= set(download.input_schema["properties"])
    assert tools["kartograf_project_remove"].annotations.destructive_hint is True


@needs_mcp
def test_the_cache_the_server_opened_is_closed_with_the_connection(
    tmp_path, monkeypatch
):
    from kartograf.cache.metadata import MetadataCache

    closed = []
    real_close = MetadataCache.close
    monkeypatch.setattr(
        MetadataCache,
        "close",
        lambda self: (closed.append(self.db_path), real_close(self)),
    )
    database = tmp_path / "c.db"

    server = capture_server(["--cache-file", str(database)], monkeypatch)
    call_on(server, "kartograf_sheet_parse", {"sheet": SHEET})

    assert closed == [database]


# -- stdio ----------------------------------------------------------------------------


def stdio_parameters(tmp_path, *arguments):
    from mcp.client.stdio import StdioServerParameters

    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "kartograf.mcp_server", "--no-cache", *arguments],
        cwd=REPO,
        env={"XDG_CACHE_HOME": str(tmp_path)},
    )


@needs_mcp
def test_the_gate_of_agi_5_13_over_stdio(tmp_path):
    """AGI-5.13: start the server with an SDK client and check the names (AGI-5.2),
    the annotations, the schemas and the ``outputSchema``; the descriptions, the
    instructions and the default page against DOC-1.7; the cold start of AGI-5.11;
    one read-only call; one validation error with ``isError``, code and hint."""
    import anyio
    import jsonschema
    from mcp import Client

    async def scenario():
        started = time.monotonic()
        async with Client(stdio_parameters(tmp_path)) as client:
            listed = (await client.list_tools()).tools
            cold_start = time.monotonic() - started  # process, handshake, tools/list
            again = (await client.list_tools()).tools
            instructions = client.instructions
            page = await client.call_tool("kartograf_commands_list", {})
            largest = await client.call_tool(
                "kartograf_commands_schema", {"command": "elevation download"}
            )
            read = await client.call_tool("kartograf_sheet_parse", {"sheet": SHEET})
            invalid = await client.call_tool(
                "kartograf_elevation_download",
                {"product": "xx", "root": str(tmp_path)},
            )
        return listed, again, cold_start, instructions, page, largest, read, invalid

    listed, again, cold_start, instructions, page, largest, read, invalid = anyio.run(
        scenario
    )

    names = [tool.name for tool in listed]
    assert names == [tool.name for tool in again]  # deterministic (AGI-5.2)
    assert names == [s.name for s in tool_specs(allow_writes=False)]
    assert len(set(names)) == len(names) == 37
    for tool in listed:
        assert re.fullmatch(r"kartograf_[a-z0-9_]+", tool.name) and len(tool.name) <= 48
        hints = tool.annotations  # AGI-5.4: the title and the four hints are set
        assert hints is not None and hints.title
        assert None not in hints_of(hints), tool.name
        jsonschema.Draft202012Validator.check_schema(tool.input_schema)
        assert tool.input_schema["type"] == "object"
        assert tool.input_schema["additionalProperties"] is False
        assert all(
            p.get("description") for p in tool.input_schema["properties"].values()
        )
        jsonschema.Draft202012Validator.check_schema(tool.output_schema)
        assert tool.output_schema == OUTPUT_SCHEMA  # the envelope (AGI-5.5)
        assert tool.description and len(tool.description) <= DESCRIPTION_MAX
    assert 0 < len(instructions) <= INSTRUCTIONS_MAX
    assert instructions == INSTRUCTIONS
    assert cold_start < 5  # AGI-5.11

    for answer in (page, largest):  # the default page of DOC-1.7
        assert answer.is_error is False
        assert 0 < len(answer.content[0].text) <= PAGE_MAX
        assert answer.structured_content["schema"] == "kartograf-result/1"
    # one read-only call: a result the client checked against the outputSchema
    assert read.is_error is False
    assert (
        read.structured_content
        == wrap("sheet parse", kartograf.describe_sheet(SHEET)).to_dict()
    )
    # one validation error: an error document, with the code and a hint to fix it
    report = error_of(invalid)
    assert report["exit_code"] == 2 and report["hint"]
    assert report["details"]["option"] == "product"
    assert report["details"]["allowed"] == ["nmt", "nmpt", "laz", "contours"]


@needs_mcp
def test_stdio_server_lists_tools_and_parses_a_sheet(tmp_path):
    import anyio
    from mcp import Client

    async def scenario():
        async with Client(stdio_parameters(tmp_path)) as client:
            tools = (await client.list_tools()).tools
            parsed = await client.call_tool("kartograf_sheet_parse", {"sheet": SHEET})
            failed = await client.call_tool("kartograf_store_overview", {"root": "rel"})
            return tools, parsed, failed

    tools, parsed, failed = anyio.run(scenario)

    assert [t.name for t in tools] == [s.name for s in tool_specs(allow_writes=False)]
    assert parsed.is_error is False
    assert (
        parsed.structured_content
        == wrap("sheet parse", kartograf.describe_sheet(SHEET)).to_dict()
    )
    assert (
        failed.is_error is True
        and failed.structured_content["code"] == "validation_error"
    )


@needs_mcp
def test_stdio_server_with_writes_downloads_inside_its_directory(tmp_path):
    import anyio
    from mcp import Client

    inside, outside = tmp_path / "inside", tmp_path / "outside"
    inside.mkdir()
    outside.mkdir()

    async def scenario():
        async with Client(stdio_parameters(tmp_path, *writes_in(inside))) as client:
            tools = (await client.list_tools()).tools
            refused = await client.call_tool(
                "kartograf_store_overview", {"root": str(outside)}
            )
            created = await client.call_tool(
                "kartograf_project_init",
                {
                    "project_dir": str(inside / "p"),
                    "root": str(inside / "s"),
                },
            )
            return tools, refused, created

    tools, refused, created = anyio.run(scenario)

    assert len(tools) == 40
    assert error_of(refused, code="forbidden")["details"]["allowed"] == [
        inside.resolve().as_posix()
    ]
    assert created.is_error is False
    assert (inside / "p").is_dir()
    assert list(outside.iterdir()) == []


@needs_mcp
def test_stdio_stdout_has_only_protocol_frames():
    """What the library prints (``print`` or a write to descriptor 1) while a tool
    runs goes to stderr: every line of stdout is a JSON-RPC message."""
    program = (
        "import os, sys, kartograf\n"
        "real = kartograf.list_commands\n"
        "def noisy(**kwargs):\n"
        "    print('STRAY PRINT')\n"
        "    os.write(1, b'STRAY WRITE\\n')\n"
        "    return real(**kwargs)\n"
        "kartograf.list_commands = noisy\n"
        "from kartograf.mcp_server import main\n"
        "sys.exit(main(['--no-cache']))\n"
    )
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "kartograf_commands_list", "arguments": {}},
        },
    ]

    process = subprocess.Popen(
        [sys.executable, "-c", program],
        cwd=REPO,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    watchdog = threading.Timer(120, process.kill)
    watchdog.start()
    try:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write("".join(json.dumps(r) + "\n" for r in requests))
        process.stdin.flush()
        lines = []
        for line in process.stdout:  # until the answer to the call: stdin stays open
            lines.append(line)
            if json.loads(line).get("id") == 3:
                break
        process.stdin.close()  # the end of the connection ends the server
        lines += process.stdout.read().splitlines()  # until the server exits
        process.wait(timeout=60)
        assert process.stderr is not None
        stderr = process.stderr.read()
    finally:
        watchdog.cancel()
        process.kill()

    frames = [json.loads(line) for line in lines]
    assert process.returncode == 0, stderr
    assert [f["id"] for f in frames if "id" in f] == [1, 2, 3]
    assert all(f["jsonrpc"] == "2.0" for f in frames)
    assert not any("STRAY" in line for line in lines)
    assert "STRAY PRINT" in stderr and "STRAY WRITE" in stderr
    by_id = {f["id"]: f["result"] for f in frames if "id" in f}
    assert by_id[1]["serverInfo"]["name"] == "kartograf"
    assert by_id[1]["instructions"] == INSTRUCTIONS
    # the keys of the protocol are camelCase; the five hints are always set
    tools = {t["name"]: t for t in by_id[2]["tools"]}
    assert len(tools) == 37
    plan = tools["kartograf_elevation_download"]
    assert plan["annotations"] == {
        "title": plan["title"],
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
    assert tools["kartograf_commands_list"]["annotations"]["openWorldHint"] is False
    assert plan["inputSchema"]["dependentRequired"] == {"bbox": ["bbox_crs"]}
    assert all(tool["outputSchema"] == OUTPUT_SCHEMA for tool in tools.values())
    assert {name for name, tool in tools.items() if tool.get("_meta")} == {
        "kartograf_commands_list",
        "kartograf_commands_schema",
    }
    assert tools["kartograf_commands_list"]["_meta"] == {ALWAYS_LOAD_KEY: True}
    assert by_id[3]["structuredContent"]["result"]["schema"] == (
        "kartograf-command-list/1"
    )
    assert by_id[3]["isError"] is False
