"""``llms.txt``: the guide for AI agents must stay true (spec 10.2).

The file is read outside the repository, so every command in it is parsed by the
real parser, every tool name is a tool of the catalog, every error code is a code
of the error table and every link points to a file of the repository.
"""

import ast
import inspect
import re
import shlex
import tomllib
from pathlib import Path

import pytest

import kartograf
from kartograf import get_catalog, mcp_server, parse_command, validate_command
from kartograf.catalog import data_commands
from kartograf.catalog.tools import FAMILIES
from kartograf.cli._parser import create_parser
from kartograf.error_report import ERROR_CODES, EXIT_CODES

ROOT = Path(__file__).resolve().parent.parent.parent
LLMS = ROOT / "llms.txt"
BLOB = "https://github.com/Daldek/Kartograf/blob/main/"

# Parameter and result fields the MCP section names next to the tools.
NOT_TOOLS = {"is_error", "output_dir", "bbox_crs"}
# Tools that are not a command of the catalog (spec 9.3).
SHARED_TOOLS = {"check_updates", "project_check_updates"}


def _text() -> str:
    return LLMS.read_text(encoding="utf-8")


def _section(title: str) -> str:
    """The text of the ``## title`` section, up to the next ``## `` heading."""
    match = re.search(
        rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", _text(), re.M | re.S
    )
    assert match, f"llms.txt has no section {title!r}"
    return match.group(1)


def _blocks(language: str) -> list[str]:
    """The fenced code blocks of the file that open with ``language``."""
    return re.findall(rf"^```{language}\n(.*?)^```", _text(), re.M | re.S)


def _command_lines() -> list[str]:
    return [
        line
        for block in _blocks("")
        for line in block.splitlines()
        if line.startswith("kartograf ")
    ]


def test_file_is_short_ascii_llmstxt():
    text = _text()
    assert text.isascii()
    assert len(text.splitlines()) < 150
    lines = text.splitlines()
    assert lines[0] == "# Kartograf"
    assert lines[2].startswith("> ")
    assert text.count("\n# ") == 0  # one title; the rest are ## sections
    assert "## Optional" in text


def test_every_command_is_parsed_by_the_real_parser():
    lines = _command_lines()
    assert len(lines) >= 10
    parser = create_parser(usage_errors=True)
    data = {command.id for command in data_commands()}
    for line in lines:
        words = shlex.split(line)[1:]
        namespace = parser.parse_args(words)  # UsageError on any mistake
        if namespace._command_id in data:
            call = parse_command(words)
            output_dir = call.run.get("output_dir")
            assert output_dir is None or Path(str(output_dir)).is_absolute(), line
            validate_command(call.command, call.options, output_dir=output_dir)


def test_commands_name_json_and_absolute_output():
    for line in _command_lines():
        words = shlex.split(line)
        assert "--json" in words, line
        if "--output" in words:
            assert Path(words[words.index("--output") + 1]).is_absolute(), line


def test_quoted_commands_of_the_text_exist():
    """Commands quoted inside sentences (`kartograf ...`) parse as well."""
    quoted = re.findall(r"`(kartograf [^`]+)`", _text())
    assert "kartograf commands list --json" in quoted
    assert "kartograf commands list elevation download --json" in quoted
    parser = create_parser(usage_errors=True)
    for command in quoted:
        if command == "kartograf --version":
            continue
        words = shlex.split(command)[1:]
        if "..." in words:
            continue
        parser.parse_args(words)


def test_python_example_uses_real_api():
    (source,) = _blocks("python")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module == "kartograf"
            for alias in node.names:
                assert alias.name in kartograf.__all__, alias.name
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            function = getattr(kartograf, node.func.id, None)
            if function is None:
                continue  # print()
            parameters = inspect.signature(function).parameters
            for keyword in node.keywords:
                assert keyword.arg in parameters, (node.func.id, keyword.arg)


def test_mcp_tool_names_are_tools_of_the_catalog():
    section = _section("Serwer MCP")
    tools = {command.tool for command in get_catalog().commands if command.tool}
    tools |= SHARED_TOOLS
    named = set(re.findall(r"`([a-z0-9]+(?:_[a-z0-9]+)+)`", section)) - NOT_TOOLS
    assert {"get_catalog", "elevation_download", "check_updates"} <= named
    assert named <= tools, sorted(named - tools)


def test_mcp_options_of_the_text_are_those_of_the_server():
    """Every option that configures ``kartograf-mcp`` is described, and no other."""
    section = _section("Serwer MCP")
    # ``--json`` is the CLI flag whose document a tool result equals
    flags = set(re.findall(r"`(--[a-z-]+)`", section)) - {"--json"}
    parser = mcp_server._parser()
    options = {flag for action in parser._actions for flag in action.option_strings}

    assert flags == options - {"-h", "--help", "--version"}
    # the families ``--tools`` takes are named, as the server knows them
    assert ", ".join(FAMILIES) in section


def test_mcp_script_and_extra_are_those_of_the_package():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    text = _text()

    assert project["scripts"]["kartograf-mcp"] == "kartograf.mcp_server:main"
    assert "mcp" in project["optional-dependencies"]
    assert "kartograf-mcp" in _section("Serwer MCP")
    assert 'kartograf[mcp] @ git+https://github.com/Daldek/Kartograf.git"' in text


def test_error_table_is_the_registry_codes_of_the_library():
    rows = re.findall(
        r"^- `(\w+)` \(wyjscie (\d+)\)", _section("Kody wyjscia i bledow"), re.M
    )
    # the file names each registry code once, with the reasons of its classes
    expected = list(
        dict.fromkeys((row.code, str(row.exit_code)) for row in ERROR_CODES)
    )
    assert rows == expected
    text = _section("Kody wyjscia i bledow")
    for row in ERROR_CODES:
        if row.reason is not None:
            assert f"`{row.reason}`" in text, row


def test_exit_codes_are_the_exit_codes_of_the_library():
    text = _section("Kody wyjscia i bledow")
    for exit_code in EXIT_CODES:
        assert f"{exit_code.code} =" in text, exit_code


@pytest.mark.parametrize(
    "url", sorted(set(re.findall(r"\]\((https://[^)]+)\)", _text())))
)
def test_links_point_to_files_of_the_repository(url):
    assert url.startswith(BLOB), url
    assert (ROOT / url.removeprefix(BLOB)).is_file(), url
