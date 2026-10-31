"""``README.md``: the first document an agent or a search pipeline reads (DOC §2).

The sections follow DOC-2.1 in order, the file stays within its budget (DOC-1.7), the
summary fits the description ladder (DOC-2.3) and the links are absolute (DOC-1.4).
The examples are executed (DOC-2.6): every ``kartograf`` line is read by the real
parser and runs as written, the ones that need the network against the fake index of
the download tests, and the JSON that the README shows after a command is a part of
what the command prints.
"""

import json
import os
import re
import shlex
import tomllib
from pathlib import Path

import pytest

import kartograf
from kartograf import list_commands, list_sources
from kartograf.catalog.tools import tool_specs
from kartograf.cli.commands import main
from kartograf.config import KEYS, SHARED_KEYS
from tests.support.command_lines import check_command_line
from tests.support.data_fixtures import pl_sheets

ROOT = Path(__file__).resolve().parent.parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
SECTIONS = (
    "When to use",
    "When not to use",
    "Install",
    "Quick start",
    "Capabilities",
    "For AI agents",
    "MCP server",
    "Related tools",
    "Errors and exit codes",
    "Data and licensing",
    "Documentation",
    "Development",
    "Status, licence, author",
)
FENCE = re.compile(r"^```(\w*)\n(.*?)^```$", re.DOTALL | re.MULTILINE)
SUMMARY_MAX = 400  # DOC-1.7: the README summary paragraph
DESCRIPTION_MAX = 200  # DOC-1.7: the pyproject description
README_LINES = 400  # DOC-1.7
# What the pyproject description names and the longer summary must name too (DOC-2.3).
TERMS = ("NMT", "NMPT", "orthophoto", "LAZ", "BDOT10k", "CORINE", "SoilGrids")


def blocks() -> list[tuple[str, str]]:
    """The fenced code blocks of the README as ``(language, text)``, in order."""
    return [(match[1], match[2]) for match in FENCE.finditer(README)]


def prose() -> str:
    """The README without its code blocks."""
    return FENCE.sub("", README)


def section(title: str) -> str:
    """The text of the ``## title`` section, up to the next one."""
    return README.split(f"\n## {title}\n")[1].split("\n## ")[0]


def cli_lines() -> list[str]:
    """Every ``kartograf ...`` command line of the ``bash`` blocks."""
    return [
        line
        for language, text in blocks()
        if language == "bash"
        for line in text.splitlines()
        if line.startswith("kartograf ")
    ]


def shown_in(shown, actual, path="$"):
    """Assert that the JSON ``shown`` is a part of the JSON ``actual``.

    An object lists some of the keys, an array its first elements, an empty array
    stands for an empty array, a value for itself.
    """
    if isinstance(shown, dict):
        assert isinstance(actual, dict), path
        for key, value in shown.items():
            assert key in actual, f"{path}.{key} is missing"
            shown_in(value, actual[key], f"{path}.{key}")
    elif isinstance(shown, list):
        assert isinstance(actual, list) and len(actual) >= len(shown), path
        if not shown:
            assert actual == [], path
        for index, value in enumerate(shown):
            shown_in(value, actual[index], f"{path}[{index}]")
    else:
        assert shown == actual, path


@pytest.fixture
def home(tmp_path, monkeypatch):
    """The home directory the examples write below (``~/kartograf-data``)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def shell_words(line: str) -> list[str]:
    """The arguments of a command line as a shell gives them (``~`` expanded)."""
    return [os.path.expanduser(word) for word in shlex.split(line)[1:]]


# -- the shape of the file ------------------------------------------------------------


def test_the_sections_follow_the_documentation_standard_in_order():
    headings = re.findall(r"^(#{1,3}) (.+)$", prose(), re.MULTILINE)

    assert headings[0][0] == "#" and headings[0][1].startswith("Kartograf: ")
    assert " - " not in headings[0][1] and "\u2014" not in headings[0][1]
    assert [title for level, title in headings if level == "##"] == list(SECTIONS)


def test_the_summary_follows_the_title_with_nothing_before_it():
    title, summary = README.split("\n\n")[:2]

    assert title.startswith("# ") and "\n" not in title
    assert len(summary) <= SUMMARY_MAX
    assert not summary.startswith(("![", "[![", "<", "#"))


def test_the_summary_names_what_the_pyproject_description_names():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    description = meta["project"]["description"]
    summary = README.split("\n\n")[1]

    assert len(description) <= DESCRIPTION_MAX
    for term in TERMS:
        assert term in description, term
        assert term in summary, term


def test_the_file_stays_within_its_budget():
    assert len(README.splitlines()) <= README_LINES


def test_links_are_absolute_and_no_local_path_leaks():
    targets = re.findall(r"\]\(([^)\s]+)\)", README)

    assert len(targets) >= 20
    assert [t for t in targets if not t.startswith("https://")] == []
    assert "/home/" not in README and "C:\\" not in README


def test_the_capabilities_table_names_real_commands_products_and_functions():
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in section("Capabilities").splitlines()
        if line.startswith("| ") and not line.startswith(("| Task", "| ---"))
    ]
    commands = {entry["name"] for entry in list_commands().to_dict()["commands"]}
    assert len(rows) >= 14

    for _task, cli, functions, _source in rows:
        for function in re.findall(r"`(\w+)`", functions):
            assert function in kartograf.__all__, function
        names = re.findall(r"`([^`]+)`", cli)
        group = names[0].split()[0]
        verbs = {name.split()[1] for name in commands if name.startswith(group + " ")}
        assert verbs, group
        products = (
            set(list_sources(group=group).to_dict()["products"])
            if (f"{group} list-sources" in commands)
            else set()
        )
        for name in names:
            assert name in commands or name == group or name in verbs | products, name


def test_the_mcp_numbers_are_the_ones_of_the_server():
    text = section("MCP server")
    served = tool_specs(allow_writes=True)

    assert f"serves {len(served)} tools" in text
    assert sum("core" in spec.families for spec in served) == 10
    assert "the ten tools" in text


def test_the_variable_table_lists_every_setting_and_credential():
    table = README.split("### Settings, directories and backup")[1].split("\n## ")[0]
    named = set(re.findall(r"`((?:KARTOGRAF|NOGAT|CLMS)_[A-Z_]+)`", table))
    expected = {f"KARTOGRAF_{key.upper()}" for key in KEYS}
    expected |= {f"NOGAT_{key.upper()}" for key in SHARED_KEYS}
    expected |= {"NOGAT_CONFIG", "CLMS_CREDENTIALS"}
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    exported = set(
        re.findall(r"^#? ?((?:KARTOGRAF|NOGAT|CLMS)_[A-Z_]+)=", example, re.M)
    )

    assert named == expected
    assert {f"KARTOGRAF_{key.upper()}" for key in KEYS} | {
        "CLMS_CREDENTIALS"
    } <= exported


# -- the examples ---------------------------------------------------------------------


def test_every_command_line_is_read_by_the_parser(home):
    lines = cli_lines()

    assert len(lines) >= 3
    for line in lines:
        check_command_line(line.replace("~/", f"{home}{os.sep}"))


@pytest.mark.usefixtures("frozen_clock")
def test_the_command_lines_run_and_print_what_the_readme_shows(home, capsys):
    compared = 0
    printed = None
    with pl_sheets():
        for language, text in blocks():
            if language == "bash":
                for line in filter(
                    lambda line: line.startswith("kartograf "), text.splitlines()
                ):
                    assert main(shell_words(line)) == 0, line
                    out = capsys.readouterr().out
                    printed = json.loads(out) if "--json" in line else None
            elif language == "json":
                shown = json.loads(text)
                if (
                    isinstance(shown, dict)
                    and shown.get("schema") == "kartograf-result/1"
                ):
                    shown_in(shown, printed)
                    compared += 1

    assert compared == 2


@pytest.mark.usefixtures("frozen_clock")
def test_the_python_examples_run_and_print_what_their_comments_say(home, capsys):
    ran = 0
    with pl_sheets():
        for language, text in blocks():
            if language != "python":
                continue
            namespace: dict[str, object] = {}
            exec(compile(text, "README.md", "exec"), namespace)  # noqa: S102
            printed = capsys.readouterr().out.splitlines()
            expected = [
                line.split("# ", 1)[1]
                for line in text.splitlines()
                if line.startswith("print(") and "# " in line
            ]
            assert printed[: len(expected)] == expected
            if "report" in namespace:
                assert namespace["report"].ok is True
            ran += 1

    assert ran == 2


def test_the_mcp_example_is_a_call_of_a_tool_that_answers_like_the_cli(capsys):
    pytest.importorskip("mcp")
    from tests.integration.test_mcp_server import call

    (text,) = [
        text
        for language, text in blocks()
        if language == "json" and text.lstrip().startswith('{"name"')
    ]
    request = json.loads(text)
    result = call(request["name"], request["arguments"])
    sheet = request["arguments"]["sheet"]

    assert main(["sheet", "parse", sheet, "--json"]) == 0
    assert result.is_error is False
    assert result.structured_content == json.loads(capsys.readouterr().out)
