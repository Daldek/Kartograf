"""The MCP server (spec 9; test row 12.8).

The calls run through ``mcp.Client`` connected to the server in memory, with the
sources of the download tests replaced by their fakes (``tests/project_fixtures``);
one test starts ``python -m kartograf.mcp_server`` and speaks to it over stdio.
The tests that need the ``mcp`` package are skipped without it; the ones of the
command line and of the install hint are not.
"""

import importlib.util
import json
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
from kartograf.cache.defaults import default_cache_path
from kartograf.catalog.tools import tool_specs
from kartograf.core.bbox import BBox
from kartograf.download.data import DataReport
from kartograf.download.manager import DownloadProgress
from kartograf.envelope import wrap
from kartograf.mcp_server import INSTRUCTIONS, _parser, default_cache_file, main
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
SHEET = "N-34-130-D-d-2-4"
AREA = BBox(19.93, 50.05, 19.95, 50.07, "EPSG:4326")
EMPTY_REPORT = DataReport((), (), (), (), (), True)


def run_session(scenario, *, server=None, **server_kwargs):
    """Run ``await scenario(client)`` against a server in memory: the given one or
    one made with ``server_kwargs`` (no cache unless ``cache`` is given)."""
    import anyio
    from mcp import Client

    from kartograf.mcp_server import create_server

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


# -- no SDK needed --------------------------------------------------------------


def test_instructions_are_ascii_short_and_say_what_the_tools_do_not_repeat():
    assert INSTRUCTIONS.isascii()
    # Claude Code loads them at the start of a session and cuts them at 4096
    assert len(INSTRUCTIONS) <= 2000
    assert len(INSTRUCTIONS.splitlines()) <= 8
    # what is the same in many tools is said here, once
    for word in (
        "get_catalog",
        "tables=true",
        "bezwzglednie",
        "bbox_crs",
        "sheet",
        "geometry",
        "country",
        "update",
        "check_updates",
        "kartograf-download/1",
        "kartograf-result/1",
        "kartograf-error/1",
    ):
        assert word in INSTRUCTIONS, word


def test_main_without_mcp_prints_the_install_hint_and_exits_1():
    code = (
        "import sys\n"
        "sys.modules['mcp'] = None\n"
        "from kartograf.mcp_server import main\n"
        "sys.exit(main(['--no-cache']))\n"
    )

    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True
    )

    assert done.returncode == 1
    assert 'pip install "kartograf[mcp]"' in done.stderr
    assert done.stdout == ""
    assert "Traceback" not in done.stderr


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


def test_unknown_family_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--tools", "discovery,nope"])

    assert caught.value.code == 2
    assert "nieznana rodzina narzedzi: nope" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--version"])

    assert caught.value.code == 0
    assert capsys.readouterr().out.strip() == f"kartograf-mcp {kartograf.__version__}"


def test_cache_flags_exclude_each_other():
    with pytest.raises(SystemExit) as caught:
        _parser().parse_args(["--cache-file", "x.db", "--no-cache"])

    assert caught.value.code == 2


@pytest.mark.parametrize("directory", ["data", ".", "../data", "./a/b"])
def test_a_relative_allow_dir_stops_the_start_with_a_usage_error(directory, capsys):
    """A relative directory would stand for the working directory the client chose
    for the server; the paths of the calls are absolute, so the flag is too."""
    with pytest.raises(SystemExit) as caught:
        main(["--no-cache", "--allow-dir", directory])

    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert "--allow-dir wymaga sciezki bezwzglednej" in error
    assert repr(directory) in error


def test_allow_dir_takes_an_absolute_directory_and_the_home_shortcut(tmp_path):
    args = _parser().parse_args(["--allow-dir", str(tmp_path), "--allow-dir", "~/dane"])

    assert args.allow_dir == [tmp_path.resolve(), Path("~/dane").expanduser().resolve()]


def test_the_server_does_not_start_with_settings_that_cannot_be_used(
    tmp_path, monkeypatch, capsys
):
    """Like the CLI, the server stops instead of ignoring an unusable nogat.toml; the
    error document is the last line of stderr. The check comes before the import of
    the SDK, so the test needs no ``mcp`` package (and binds no ``sys.stderr`` to it:
    the SDK keeps the stream it finds when it is first imported)."""
    from kartograf.mcp_server import create_server

    bad = tmp_path / "nogat.toml"
    bad.write_bytes(b"\xff\xfe[\x00k\x00]\x00")  # UTF-16, not UTF-8
    monkeypatch.setenv("NOGAT_CONFIG", str(bad))

    with pytest.raises(ConfigError):
        create_server(cache=False)
    assert main(["--no-cache"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    document = json.loads(captured.err.splitlines()[-1])
    assert (document["code"], document["exit_code"]) == ("validation_error", 2)
    assert document["details"] == {
        "reason": "invalid_config",
        "option": "NOGAT_CONFIG",
        "path": bad.as_posix(),
    }


@needs_mcp
def test_create_server_refuses_a_relative_allow_dir_before_it_opens_the_cache(tmp_path):
    from kartograf.mcp_server import create_server

    database = tmp_path / "cache.db"

    with pytest.raises(ValueError, match="sciezki bezwzglednej"):
        create_server(cache=database, allow_dirs=["data"])

    assert not database.exists()


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
def test_server_identity_and_instructions():
    async def scenario(client):
        return client.server_info, client.instructions

    info, instructions = run_session(scenario)

    assert (info.name, info.version) == ("kartograf", kartograf.__version__)
    assert instructions == INSTRUCTIONS


def dataclass_values(hints):
    return (
        hints.read_only_hint,
        hints.destructive_hint,
        hints.idempotent_hint,
        hints.open_world_hint,
    )


@needs_mcp
def test_list_tools_equals_tool_specs():
    async def scenario(client):
        return (await client.list_tools()).tools

    tools = run_session(scenario)
    specs = tool_specs()

    assert [t.name for t in tools] == [s.name for s in specs]
    for tool, spec in zip(tools, specs, strict=True):
        assert tool.title is None  # the first sentence of the description says it
        assert tool.description == spec.description
        assert tool.input_schema == spec.input_schema
        assert tool.output_schema is None  # a result is a family of documents
        hints = tool.annotations
        assert (
            hints.read_only_hint,
            hints.destructive_hint,
            hints.idempotent_hint,
            hints.open_world_hint,
        ) == dataclass_values(spec.annotations)


@needs_mcp
def test_tools_list_on_the_wire_is_under_30000_characters():
    """The acceptance of the context budget on the real protocol objects: what
    ``tools/list`` sends (it was 65 883) and the answer of ``get_catalog()``
    (it was 47 807; the CLI form is the same document, indented)."""

    async def scenario(client):
        listed = (await client.list_tools()).tools
        overview = await client.call_tool("get_catalog", {})
        return listed, overview

    listed, overview = run_session(scenario)

    wire = [tool.model_dump(by_alias=True, exclude_none=True) for tool in listed]
    assert len(json.dumps(wire, ensure_ascii=False, separators=(",", ":"))) <= 30_000
    text = overview.content[0].text
    assert text == json.dumps(
        json.loads(text), ensure_ascii=False, separators=(",", ":")
    )
    assert len(text) <= 8_000


DISCOVERY = [
    (
        "get_catalog",
        {"command": "elevation download"},
        lambda: kartograf.get_catalog(command="elevation download"),
        "commands list",
    ),
    ("get_catalog", {}, lambda: kartograf.get_catalog(), "commands list"),
    (
        "parse_sheet",
        {"sheet": SHEET, "hierarchy": True, "descendants": "1:5000"},
        lambda: kartograf.describe_sheet(SHEET, hierarchy=True, descendants="1:5000"),
        "sheet parse",
    ),
    (
        "list_sources",
        {"group": "elevation", "product": "nmt"},
        lambda: kartograf.list_sources(group="elevation", product="nmt"),
        "elevation list-sources",
    ),
    (
        "list_layers",
        {"group": "soil"},
        lambda: kartograf.list_layers(group="soil"),
        "soil list-layers",
    ),
    (
        "find_sheets",
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
            download_data(**PL_SHEET, output_dir=tmp_path / "lib", cache=False),
        )
    with pl_sheets():
        result = call(
            "elevation_download", {**PL_SHEET, "output_dir": str(tmp_path / "mcp")}
        )

    assert result.is_error is False
    envelope = result.structured_content
    document = envelope["result"]
    assert envelope["schema"] == "kartograf-result/1" and envelope["status"] == "ok"
    assert document["schema"] == "kartograf-download/1" and document["ok"] is True
    assert normal(envelope, tmp_path / "mcp") == normal(
        direct.to_dict(), tmp_path / "lib"
    )
    assert result.content[0].text.replace(str(tmp_path / "mcp"), "<store>") == (
        direct.to_json(indent=None).replace(str(tmp_path / "lib"), "<store>")
    )
    (item,) = document["files"]
    assert Path(item["file"]["path"]).is_file()  # the version is in the store
    assert Path(item["file"]["path"]).is_relative_to(tmp_path / "mcp")


@needs_mcp
@pytest.mark.usefixtures("frozen_clock")
def test_ok_false_is_a_result_with_the_status_of_its_units(tmp_path):
    failing = FakeCampaignProvider(C14, fail_urls={C14["newest"][0].url})
    with pl_sheets(failing):
        report = download_data(**PL_SHEET, output_dir=tmp_path / "lib", cache=False)
        result = call(
            "elevation_download", {**PL_SHEET, "output_dir": str(tmp_path / "mcp")}
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
def test_check_updates_equals_check_command(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    with pl_sheets(fake):
        for store in ("lib", "mcp"):
            run_command(
                "elevation download", PL_SHEET, output_dir=tmp_path / store, cache=False
            )
    fake.records = {"newest": [REC["84183"]]}
    with pl_sheets(fake):
        direct = check_command(
            "elevation download", PL_SHEET, output_dir=tmp_path / "lib", cache=False
        )
        result = call(
            "check_updates",
            {
                "tool": "elevation_download",
                "arguments": {**PL_SHEET, "output_dir": str(tmp_path / "mcp")},
            },
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
                "elevation download", PL_SHEET, output_dir=tmp_path / store, cache=False
            )
    fake.records = {"newest": [REC["84183"]]}
    with pl_sheets(fake):
        library_plan = check_command(
            "elevation download", PL_SHEET, output_dir=tmp_path / "lib", cache=False
        )
        direct = run_command(
            "elevation download",
            PL_SHEET,
            output_dir=tmp_path / "lib",
            update="upgrade",
            plan=library_plan.result,
            cache=False,
        )
        checked = call(
            "check_updates",
            {
                "tool": "elevation_download",
                "arguments": {**PL_SHEET, "output_dir": str(tmp_path / "mcp")},
            },
        )
        upgraded = call(
            "elevation_download",
            {
                **PL_SHEET,
                "output_dir": str(tmp_path / "mcp"),
                "update": "upgrade",
                "plan": checked.structured_content["result"],
            },
        )

    assert upgraded.is_error is False
    (new,) = upgraded.structured_content["result"]["files"]
    assert new["file"]["status"] == "new"
    assert new["file"]["label"].startswith("2025-10-21_84183")
    assert normal(upgraded.structured_content, tmp_path / "mcp") == normal(
        direct.to_dict(), tmp_path / "lib"
    )


@needs_mcp
def test_summary_is_an_argument_of_the_run_not_of_the_task(tmp_path):
    hsg = {"sheet": HSG_SHEET, "depth": "0-5cm"}
    with landcover_sources(soilgrids=RasterSoilGrids):
        direct = calculate_hsg(
            output_dir=tmp_path / "lib", cache=False, summary=True, **hsg
        )
        with_summary = call(
            "soil_hsg", {**hsg, "output_dir": str(tmp_path / "a"), "summary": True}
        )
        without = call("soil_hsg", {**hsg, "output_dir": str(tmp_path / "b")})

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
def test_check_updates_input_errors(tmp_path):
    here = str(tmp_path)
    selection = {**PL_SHEET, "output_dir": here}
    cases = [
        ({"tool": "nope", "arguments": selection}, "tool", None),
        (
            {
                "tool": "elevation_download",
                "arguments": selection | {"update": "force"},
            },
            "update",
            "elevation download",
        ),
        (
            {"tool": "elevation_download", "arguments": selection | {"plan": {}}},
            "plan",
            "elevation download",
        ),
        (
            {"tool": "elevation_download", "arguments": selection | {"workers": 2}},
            "workers",
            "elevation download",
        ),
        (
            {"tool": "elevation_download", "arguments": PL_SHEET},
            "output_dir",
            "elevation download",
        ),
        (
            {
                "tool": "elevation_download",
                "arguments": selection | {"output_dir": "rel"},
            },
            "output_dir",
            "elevation download",
        ),
        (
            {
                "tool": "soil_hsg",
                "arguments": {
                    "depth": "0-5cm",
                    "sheet": HSG_SHEET,
                    "output_dir": here,
                    "summary": True,
                },
            },
            "summary",
            "soil hsg",
        ),
        (
            {"tool": "elevation_download", "arguments": {"output_dir": here}},
            "product",
            "elevation download",
        ),
    ]

    for arguments, option, command in cases:
        report = error_of(call("check_updates", arguments))

        assert report["details"]["option"] == option, arguments
        assert report.get("command") == command, arguments
        assert report["exit_code"] == 2
    # a rule of the library, checked without network and without writing
    area_missing = {
        "tool": "elevation_download",
        "arguments": {"product": "nmt", "output_dir": here},
    }
    report = error_of(call("check_updates", area_missing))
    assert report["command"] == "elevation download"
    assert report["details"]["options"]
    assert list(tmp_path.iterdir()) == []


@needs_mcp
def test_check_updates_tool_names_come_from_the_schema_enum():
    report = error_of(
        call("check_updates", {"tool": "soil", "arguments": {"output_dir": "/x"}})
    )

    assert report["details"]["allowed"] == [s.name for s in tool_specs(("data",))]
    assert "elevation_download" in report["hint"]


@needs_mcp
@pytest.mark.parametrize(
    ("tool", "arguments", "option", "command"),
    [
        (
            "elevation_download",
            {"product": "nmt", "output_dir": "rel/dir"},
            "output_dir",
            "elevation download",
        ),
        (
            "elevation_download",
            {"product": "nmt", "output_dir": "ABS", "nope": 1},
            "nope",
            "elevation download",
        ),
        (
            "elevation_download",
            {"product": "xx", "output_dir": "ABS"},
            "product",
            "elevation download",
        ),
        (
            "elevation_download",
            {"product": "nmt", "bbox": [1, 2, 3, 4], "output_dir": "ABS"},
            "bbox_crs",
            "elevation download",
        ),
        ("elevation_download", {"output_dir": "ABS"}, "product", "elevation download"),
        (
            "elevation_download",
            {"product": "nmt", "output_dir": "ABS", "workers": 0},
            "workers",
            "elevation download",
        ),
        (
            "elevation_download",
            {
                "product": "nmt",
                "output_dir": "ABS",
                "bbox": [1, 2, 3],
                "bbox_crs": "EPSG:2180",
            },
            "bbox",
            "elevation download",
        ),
        (
            "elevation_download",
            {"product": "nmt", "output_dir": "ABS", "resolution": 5},
            "resolution",
            "elevation download",
        ),
        (
            "elevation_download",
            {"product": "nmt", "output_dir": "ABS", "plan": {"schema": "other/1"}},
            "plan",
            "elevation download",
        ),
        ("parse_sheet", {"sheet": 5}, "sheet", "sheet parse"),
        ("list_sources", {"group": "nope"}, "group", None),
        (
            "list_sources",
            {"group": "elevation", "product": "orto"},
            "product",
            "elevation list-sources",
        ),
        ("store_overview", {"output_dir": "relative"}, "output_dir", "store overview"),
        ("store_sidecar", {"path": "x.meta.json"}, "path", "store sidecar"),
        ("project_status", {"project_dir": "."}, "project_dir", "project status"),
    ],
)
def test_input_errors_are_error_documents(tmp_path, tool, arguments, option, command):
    arguments = {k: str(tmp_path) if v == "ABS" else v for k, v in arguments.items()}

    report = error_of(call(tool, arguments))

    assert report["exit_code"] == 2 and report.get("command") == command
    assert report["details"].get("option") == option
    assert report["message"].isascii() and (report["hint"] or "").isascii()
    assert list(tmp_path.iterdir()) == []  # nothing was written


@needs_mcp
@pytest.mark.parametrize("spec", tool_specs(("data",)), ids=lambda s: s.name)
def test_every_data_tool_runs_its_own_command(tmp_path, spec):
    """Without an area the library refuses every data command: the answer names
    the command the tool stands for, for the tool and for ``check_updates``."""
    arguments = {"output_dir": str(tmp_path)}
    if "product" in spec.input_schema["properties"]:
        arguments["product"] = spec.input_schema["properties"]["product"]["enum"][0]
    if "depth" in spec.input_schema["required"]:
        arguments["depth"] = spec.input_schema["properties"]["depth"]["enum"][0]

    run = error_of(call(spec.name, arguments))
    check = error_of(call("check_updates", {"tool": spec.name, "arguments": arguments}))

    assert run["command"] == check["command"] == spec.commands[0]
    assert run["exit_code"] == check["exit_code"] == 2
    assert run["details"] and run["details"] == check["details"]
    assert list(tmp_path.iterdir()) == []  # no network, nothing written


@needs_mcp
def test_a_bad_sheet_code_is_invalid_sheet_code():
    report = error_of(
        call("parse_sheet", {"sheet": "not-a-sheet"}), reason="invalid_sheet_code"
    )

    assert report["exit_code"] == 2 and report["command"] == "sheet parse"
    assert report["details"]["option"] == "sheet"


@needs_mcp
def test_input_error_hints_name_the_fix(tmp_path):
    relative = error_of(call("store_overview", {"output_dir": "relative"}))
    bad_enum = error_of(
        call("elevation_download", {"product": "xx", "output_dir": str(tmp_path)})
    )
    unknown = error_of(
        call(
            "elevation_download",
            {"product": "nmt", "output_dir": str(tmp_path), "nope": 1},
        )
    )

    assert "Podaj sciezke bezwzgledna" in relative["hint"]
    assert bad_enum["details"]["allowed"] == ["nmt", "nmpt", "laz", "contours"]
    assert "nmpt" in bad_enum["hint"]
    assert "product" in unknown["hint"] and "output_dir" in unknown["hint"]


@needs_mcp
def test_input_error_hint_example_is_of_the_product_and_country_of_the_call(tmp_path):
    # E2E 0.8.0 D P3-7: the same call as in the CLI, the same example
    report = error_of(
        call(
            "boundaries_download",
            {
                "product": "admin",
                "country": "auto",
                "level": "gmina",
                "bbox": [18.6, 49.7, 18.7, 49.8],
                "bbox_crs": "EPSG:4326",
                "output_dir": str(tmp_path),
            },
        )
    )

    assert report["details"]["option"] == "level"
    assert "--country auto" in report["hint"] and "--product admin" in report["hint"]


@needs_mcp
def test_oserror_is_io_error(tmp_path):
    missing = tmp_path / "missing"

    report = error_of(
        call("store_overview", {"output_dir": str(missing)}), code="io_error"
    )

    assert report["exit_code"] == 9 and report["command"] == "store overview"
    assert report["details"] == {"errno": "ENOENT", "path": str(missing)}


@needs_mcp
def test_foreign_exception_is_internal_error(tmp_path, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise KeyError("boom")

    monkeypatch.setattr(kartograf, "describe_store", broken)

    result = call("store_overview", {"output_dir": str(tmp_path)})

    report = error_of(result, code="internal_error")
    assert report["message"] == "KeyError: 'boom'" and report["exit_code"] == 1
    assert "Traceback" not in result.content[0].text
    assert "KeyError" in caplog.text and "Traceback" in caplog.text  # the log has it


@needs_mcp
def test_unknown_tool_is_a_protocol_error():
    from mcp.shared.exceptions import MCPError
    from mcp_types import INVALID_PARAMS

    async def scenario(client):
        try:
            await client.call_tool("nope", {})
        except MCPError as error:  # the one failure that is not a result
            return error
        return None

    error = run_session(scenario)

    assert error is not None and error.code == INVALID_PARAMS
    assert "nope" in error.message


@needs_mcp
def test_progress_is_strictly_increasing(tmp_path):
    """Events from four threads with the same ``current`` reach the client as
    1, 2, 3, ... with the text of the event; the total stays unknown."""
    calls = []

    def download(command, options, *, output_dir, on_progress, **kwargs):
        calls.append(command)

        def work(worker):
            for _ in range(5):
                on_progress(DownloadProgress(1, 3, f"N-{worker}", "downloading"))
            on_progress(DownloadProgress(1, 3, f"N-{worker}", "failed", "blad \u0142"))

        with ThreadPoolExecutor(4) as pool:
            list(pool.map(work, range(4)))
        return EMPTY_REPORT

    received = []

    async def on_progress(progress, total, message):
        received.append((progress, total, message))

    with patch("kartograf.mcp_server.run_command", download):
        result = call(
            "elevation_download",
            {**PL_SHEET, "output_dir": str(tmp_path)},
            progress=on_progress,
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

    result = call("store_overview", {"output_dir": str(tmp_path)}, progress=on_progress)

    assert result.is_error is False and received == []


@needs_mcp
def test_allow_dir_rejects_paths_outside_after_resolve(tmp_path):
    allowed, outside = tmp_path / "allowed", tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (allowed / "link").symlink_to(outside, target_is_directory=True)

    inside = call("store_overview", {"output_dir": str(allowed)}, allow_dirs=[allowed])
    assert inside.is_error is False

    for path in (outside, allowed / "link", allowed / ".." / "outside"):
        report = error_of(
            call("store_overview", {"output_dir": str(path)}, allow_dirs=[allowed])
        )
        assert report["details"]["option"] == "output_dir"
        assert str(allowed) in report["hint"]
    # the same rule for the paths nested in a call
    nested = call(
        "check_updates",
        {
            "tool": "elevation_download",
            "arguments": {**PL_SHEET, "output_dir": str(outside)},
        },
        allow_dirs=[allowed],
    )
    assert error_of(nested)["details"]["option"] == "output_dir"
    task = call(
        "project_add",
        {
            "project_dir": str(allowed),
            "name": "t",
            "command": "elevation download",
            "options": {"product": "nmt", "geometry": str(outside / "area.gpkg")},
        },
        allow_dirs=[allowed],
    )
    assert error_of(task)["details"]["option"] == "geometry"


@needs_mcp
def test_a_relative_path_inside_task_options_is_refused(tmp_path):
    report = error_of(
        call(
            "project_add",
            {
                "project_dir": str(tmp_path),
                "name": "t",
                "command": "elevation download",
                "options": {"product": "nmt", "geometry": "area.gpkg"},
            },
        )
    )

    assert report["details"]["option"] == "geometry"
    assert "Podaj sciezke bezwzgledna" in report["hint"]


@needs_mcp
def test_at_most_four_calls_run_at_once(tmp_path):
    import anyio

    state = {"active": 0, "peak": 0}
    gate = threading.Condition()

    def download(command, options, *, output_dir, **kwargs):
        with gate:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            gate.notify_all()
            gate.wait_for(lambda: state["active"] >= 4, timeout=10)
        time.sleep(0.05)
        with gate:
            state["active"] -= 1
        return EMPTY_REPORT

    async def scenario(client):
        results = []

        async def one(number):
            arguments = {**PL_SHEET, "output_dir": str(tmp_path / str(number))}
            results.append(await client.call_tool("elevation_download", arguments))

        async with anyio.create_task_group() as group:
            for number in range(8):
                group.start_soon(one, number)
        return results

    with patch("kartograf.mcp_server.run_command", download):
        results = run_session(scenario)

    assert len(results) == 8 and not any(r.is_error for r in results)
    assert state["peak"] == 4 and state["active"] == 0


@needs_mcp
def test_library_does_not_write_to_stdout_during_calls(tmp_path, capfd):
    with pl_sheets():
        call("elevation_download", {**PL_SHEET, "output_dir": str(tmp_path / "a")})
    call("parse_sheet", {"sheet": SHEET})
    call("get_catalog", {})
    call("store_overview", {"output_dir": str(tmp_path / "missing")})
    call("elevation_download", {"product": "xx", "output_dir": str(tmp_path)})

    out, _err = capfd.readouterr()

    assert out == ""


@needs_mcp
def test_function_tools_get_library_types_and_the_server_cache(tmp_path, monkeypatch):
    from kartograf.cache.metadata import MetadataCache

    seen = []

    def availability(*, cache, **kwargs):
        seen.append({**kwargs, "cache": cache})
        return kartograf.get_catalog(command="commands list")

    monkeypatch.setattr(kartograf, "check_availability", availability)
    cache = MetadataCache(tmp_path / "cache.db")
    geometry = tmp_path / "area.shp"

    call(
        "elevation_availability",
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
    call("elevation_availability", {"product": "laz", "force": False}, cache=cache)

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
        return kartograf.get_catalog(command="commands list")

    monkeypatch.setattr(kartograf, "download_project", download)
    received = []

    async def on_progress(progress, total, message):
        received.append((progress, total, message))

    result = call(
        "project_download",
        {
            "project_dir": str(tmp_path),
            "update": "upgrade",
            "workers": 2,
            "tasks": ["a", "b"],
        },
        progress=on_progress,
    )

    assert result.is_error is False
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

    init = call("project_init", {**here, "output_dir": str(store)})
    added = call(
        "project_add",
        {**here, "name": "area", "command": "elevation download", "options": PL_SHEET},
    )
    before = call("project_status", here)
    with pl_sheets():
        downloaded = call("project_download", here)
        checked = call("project_check_updates", here)
    after = call("project_status", here)
    verified = call("project_verify", here)

    assert init.structured_content["result"]["schema"] == "kartograf-project-state/1"
    assert [t["name"] for t in added.structured_content["result"]["tasks"]] == ["area"]
    # a task that is not downloaded is ok: false, a result with the status failed
    # (the CLI's exit 11), not an error
    assert before.is_error is False
    assert before.structured_content["status"] == "failed"
    assert before.structured_content["result"]["ok"] is False
    assert before.structured_content["result"]["not_downloaded"] == ["area"]
    assert downloaded.is_error is False
    result_schema = downloaded.structured_content["result"]["schema"]
    assert result_schema == "kartograf-project-report/1"
    assert checked.structured_content["result"]["schema"] == "kartograf-project-check/1"
    assert checked.is_error is False
    assert (after.is_error, verified.is_error) == (False, False)
    assert verified.structured_content["result"]["ok"] is True

    overview = call("store_overview", {"output_dir": str(store)})
    segment = overview.structured_content["result"]["segments"][0]["segment"]
    entries = call(
        "store_entries", {"output_dir": str(store), "segment": segment, "limit": 5}
    )
    path = entries.structured_content["result"]["entries"][0]["path"]
    sidecar = call("store_sidecar", {"path": path})

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
    one = call(
        "store_entries",
        {"output_dir": str(store), "segment": segment, "units": [], "limit": 1},
    )
    assert one.is_error is False

    removed = call("project_remove", {**here, "name": "area"})
    assert removed.structured_content["result"]["tasks"] == []


@needs_mcp
def test_a_cancelled_call_is_abandoned_not_stopped(tmp_path):
    from mcp.shared.exceptions import MCPError

    release, finished = threading.Event(), threading.Event()

    def download(command, options, *, output_dir, **kwargs):
        release.wait(30)
        finished.set()
        return EMPTY_REPORT

    async def scenario(client):
        arguments = {**PL_SHEET, "output_dir": str(tmp_path)}
        try:
            await client.call_tool(
                "elevation_download", arguments, read_timeout_seconds=0.5
            )
        except MCPError as error:  # the client gave up and cancelled the call
            timed_out = error
        parsed = await client.call_tool("parse_sheet", {"sheet": SHEET})
        return timed_out, parsed

    # the library check is left out: only the call that is running can be abandoned
    with (
        patch("kartograf.mcp_server.run_command", download),
        patch("kartograf.mcp_server.validate_command"),
    ):
        timed_out, parsed = run_session(scenario)
        assert not finished.is_set()  # still running when the connection is gone
        release.set()
        assert finished.wait(30)  # nobody stopped the thread

    assert "Timed out" in timed_out.message
    assert parsed.is_error is False  # the server went on


# -- the arguments of the server ----------------------------------------------------


@needs_mcp
def test_tools_flag_selects_families(monkeypatch):
    families = ("discovery", "availability", "data", "check")
    server = capture_server(["--tools", ",".join(families), "--no-cache"], monkeypatch)

    async def scenario(client):
        return [t.name for t in (await client.list_tools()).tools]

    names = run_session(scenario, server=server)

    assert len(names) == 19
    assert names == [s.name for s in tool_specs(families)]


def call_on(server, tool, arguments):
    return call(tool, arguments, server=server)


def _cache_probe(seen):
    """A ``run_command`` that writes a record to the cache it is given."""

    def download(command, options, *, output_dir, cache, **kwargs):
        seen.append(cache)
        if cache is not False:
            cache.set_record("nmt", "1m", "EVRF2007", SHEET, {"no_coverage": True})
        return EMPTY_REPORT

    return download


@needs_mcp
def test_default_cache_is_created_at_first_use_in_the_cache_dir(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("KARTOGRAF_CACHE_DIR", str(tmp_path / "own"))
    database = tmp_path / "own" / "kartograf" / "metadata.db"

    server = capture_server([], monkeypatch)
    assert not database.parent.exists()  # the first write makes the directory
    seen = []
    with patch("kartograf.mcp_server.run_command", _cache_probe(seen)):
        result = call_on(
            server,
            "elevation_download",
            {**PL_SHEET, "output_dir": str(tmp_path / "s")},
        )

    assert result.is_error is False
    assert seen[0].db_path == database and database.is_file()
    assert list(cwd.iterdir()) == []  # nothing lands in the working directory


@needs_mcp
def test_cache_file_flag(tmp_path, monkeypatch):
    database = tmp_path / "own" / "cache.db"
    seen = []

    server = capture_server(["--cache-file", str(database)], monkeypatch)
    with patch("kartograf.mcp_server.run_command", _cache_probe(seen)):
        call_on(
            server,
            "elevation_download",
            {**PL_SHEET, "output_dir": str(tmp_path / "s")},
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

    server = capture_server(["--cache-file", str(database)], monkeypatch)
    with patch("kartograf.mcp_server.run_command", _cache_probe(seen)):
        result = call_on(
            server,
            "elevation_download",
            {**PL_SHEET, "output_dir": str(tmp_path / "s")},
        )

    assert result.is_error is False
    assert seen[0].db_path == database and not database.exists()
    assert "niedostepny do otwarcia lub zapisu" in caplog.text


@needs_mcp
def test_no_cache_flag(tmp_path, monkeypatch):
    seen = []

    server = capture_server(["--no-cache"], monkeypatch)
    with patch("kartograf.mcp_server.run_command", _cache_probe(seen)):
        call_on(
            server,
            "elevation_download",
            {**PL_SHEET, "output_dir": str(tmp_path / "s")},
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
        result = call_on(server, "store_overview", {"output_dir": str(directory)})
        assert result.is_error is refused


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
    call_on(server, "parse_sheet", {"sheet": SHEET})

    assert closed == [database]


# -- stdio ----------------------------------------------------------------------------


@needs_mcp
def test_stdio_server_lists_tools_and_parses_a_sheet(tmp_path):
    import anyio
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "kartograf.mcp_server", "--no-cache"],
        cwd=REPO,
        env={"XDG_CACHE_HOME": str(tmp_path)},
    )

    async def scenario():
        async with Client(parameters) as client:
            tools = (await client.list_tools()).tools
            parsed = await client.call_tool("parse_sheet", {"sheet": SHEET})
            failed = await client.call_tool("store_overview", {"output_dir": "rel"})
            return tools, parsed, failed

    tools, parsed, failed = anyio.run(scenario)

    assert [t.name for t in tools] == [s.name for s in tool_specs()]
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
def test_stdio_stdout_has_only_protocol_frames():
    """What the library prints (``print`` or a write to descriptor 1) while a tool
    runs goes to stderr: every line of stdout is a JSON-RPC message."""
    program = (
        "import os, sys, kartograf\n"
        "real = kartograf.get_catalog\n"
        "def noisy(**kwargs):\n"
        "    print('STRAY PRINT')\n"
        "    os.write(1, b'STRAY WRITE\\n')\n"
        "    return real(**kwargs)\n"
        "kartograf.get_catalog = noisy\n"
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
            "params": {"name": "get_catalog", "arguments": {}},
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
    # the keys of the protocol are camelCase, the hints that are not set are absent
    tools = {t["name"]: t for t in by_id[2]["tools"]}
    assert len(tools) == 29
    assert tools["elevation_download"]["annotations"] == {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
    assert tools["get_catalog"]["annotations"] == {
        "readOnlyHint": True,
        "openWorldHint": False,
    }
    schema = tools["elevation_download"]["inputSchema"]
    assert schema["dependentRequired"] == {"bbox": ["bbox_crs"]}
    assert not any("outputSchema" in tool for tool in tools.values())
    assert by_id[3]["structuredContent"]["result"]["schema"] == "kartograf-catalog/1"
    assert by_id[3]["isError"] is False
