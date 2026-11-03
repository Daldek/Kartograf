"""``AGENTS.md`` and ``llms.txt``: the guides for AI agents, generated (AGI section 8).

The files in the root of the repository are the output of ``kartograf commands guide``,
byte for byte, so they cannot drift from the catalog. The guides are read outside the
repository, so every command in them is read by the real parser, every link is an
absolute link to a file of the repository, every error code is a code of the registry
and the budgets of DOC-1.7 hold.
"""

import json
import re
import shlex
from pathlib import Path

import pytest

import kartograf
from kartograf import agent_guide
from kartograf import guide as guide_module
from kartograf.catalog.build import command_entries
from kartograf.cli.commands import main
from kartograf.error_report import ERROR_CODES, EXIT_CODES
from kartograf.exceptions import ValidationError
from kartograf.guide import BLOCK_BEGIN, BLOCK_END, GUIDE_FORMATS, inject_block
from kartograf.serialization import SCHEMAS
from tests.support.command_lines import check_command_line

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ROOT / "AGENTS.md"
LLMS = ROOT / "llms.txt"
RAW = "https://raw.githubusercontent.com/Daldek/Kartograf/main/"
SECTIONS = (
    "Purpose and scope",
    "Install",
    "Interfaces",
    "Workflow rules",
    "Result envelope",
    "Error codes",
    "Command index",
    "Typical flows",
    "Things not to do",
)
LAST_LINE = "Developing this repository? Read CLAUDE.md."


def _quoted_commands(text: str) -> list[str]:
    """The command lines of the text: the ones in code spans, as written."""
    return [
        line
        for line in re.findall(r"`(kartograf [^`]+)`", text)
        if "<" not in line and "..." not in line
    ]


# -- the files are the output of the generator ------------------------------------


def test_the_files_are_the_output_of_the_generator():
    assert AGENTS.read_text(encoding="utf-8") == agent_guide(format="agents").text
    assert LLMS.read_text(encoding="utf-8") == agent_guide(format="llms").text
    for path in (AGENTS, LLMS):
        data = path.read_bytes()
        assert data.endswith(b"\n") and b"\r" not in data, path.name
        assert data.isascii(), path.name


def test_the_guide_is_a_document_and_the_text_depends_on_nothing_local():
    document = agent_guide(format="agents-md-block")

    assert document.schema == "kartograf-guide/1"
    assert SCHEMAS["kartograf-guide/1"] == (type(document),)
    assert document.to_dict() == {
        "schema": "kartograf-guide/1",
        "format": "agents-md-block",
        "text": document.text,
    }
    for format in GUIDE_FORMATS:
        text = agent_guide(format=format).text
        assert str(ROOT) not in text and "/home/" not in text
        assert kartograf.__version__ not in text  # no version: the file does not age


def test_an_unknown_format_is_a_validation_error_that_lists_the_formats():
    with pytest.raises(ValidationError) as caught:
        agent_guide(format="html")

    assert caught.value.option == "format"
    assert (
        tuple(caught.value.allowed)
        == GUIDE_FORMATS
        == (
            "agents",
            "llms",
            "agents-md-block",
        )
    )


# -- the budgets of DOC-1.7 ---------------------------------------------------------


def test_agents_md_is_within_200_lines_and_16_kib():
    data = AGENTS.read_bytes()

    assert len(data.splitlines()) <= 200
    assert len(data) <= 16 * 1024


def test_llms_txt_says_what_it_has_to_say_before_the_links_in_8000_characters():
    text = LLMS.read_text(encoding="utf-8")
    first_link_list = re.search(r"^## ", text, re.M)

    assert first_link_list is not None
    assert len(text[: first_link_list.start()]) <= 8_000


def test_the_block_is_within_60_lines_and_delimited():
    text = agent_guide(format="agents-md-block").text
    lines = text.splitlines()

    assert len(lines) <= 60
    assert lines[0] == BLOCK_BEGIN and lines[-1] == BLOCK_END
    assert text.count(BLOCK_BEGIN) == text.count(BLOCK_END) == 1


# -- the layout of the guides ---------------------------------------------------------


def test_agents_md_has_the_sections_of_doc_4_2_and_ends_with_the_pointer():
    text = AGENTS.read_text(encoding="utf-8")
    headings = re.findall(r"^## (.*)$", text, re.M)

    assert headings == list(SECTIONS)
    assert text.splitlines()[-1] == LAST_LINE
    assert text.startswith("# Kartograf - guide for agents\n")
    assert "Do not edit it by hand" in text


def test_llms_txt_follows_the_llmstxt_layout_with_raw_links():
    text = LLMS.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections = re.split(r"^## .*$", text, flags=re.M)[1:]

    assert lines[0] == "# Kartograf" and lines[2].startswith("> ")
    assert text.count("\n# ") == 0  # one title; the rest are sections
    assert re.findall(r"^## (.*)$", text, re.M) == ["Documentation", "Optional"]
    for section in sections:  # H2 sections hold link lists only (DOC-5.1)
        items = [line for line in section.splitlines() if line.strip()]
        assert items and all(
            re.fullmatch(r"- \[[^\]]+\]\(" + re.escape(RAW) + r"[^)]+\): .+", line)
            for line in items
        ), items
    assert "llms-full" not in text  # DOC-5.4


@pytest.mark.parametrize(
    "url", sorted(set(re.findall(r"\]\((https://[^)]+)\)", LLMS.read_text())))
)
def test_links_of_llms_txt_point_to_files_of_the_repository(url):
    assert url.startswith(RAW), url
    assert (ROOT / url.removeprefix(RAW)).is_file(), url


# -- the guides say what the catalog and the registry say -----------------------------


def test_the_command_index_has_every_command_once_with_its_tool():
    text = AGENTS.read_text(encoding="utf-8")
    index = text.split("## Command index")[1].split("## Typical flows")[0]
    lines = [line for line in index.splitlines() if line.startswith("- ")]

    assert len(lines) == len(command_entries()) == 39
    for entry, line in zip(command_entries(), lines, strict=True):
        assert line.startswith(f"- `{entry.name}` (")
        assert line.endswith(f": {entry.summary}")
        has_tool = f"`{entry.operation_id}`" in line
        assert has_tool == bool(entry.families), entry.name  # a tool only when exposed


def test_every_error_code_of_the_registry_is_in_the_table_with_its_exit_code():
    text = AGENTS.read_text(encoding="utf-8")
    table = text.split("## Error codes")[1].split("## Command index")[0]
    rows = dict(re.findall(r"^\| `([a-z_]+)` \| (\d+) \|", table, re.M))

    expected = {row.code: str(row.exit_code) for row in ERROR_CODES}
    assert rows == expected
    for exit_code in EXIT_CODES:
        if exit_code.code in (0, 10, 11):
            continue  # an outcome, not an error code
        assert str(exit_code.code) in rows.values(), exit_code
    llms = LLMS.read_text(encoding="utf-8")
    for code, exit_code in expected.items():
        assert f"`{code}` ({exit_code})" in llms, code


def test_the_envelope_and_the_outcomes_are_described_as_the_catalog_has_them():
    text = AGENTS.read_text(encoding="utf-8")

    assert "`kartograf-result/1`" in text and "`kartograf-error/1`" in text
    assert "exit code 10" in text and "exit code 11" in text
    for schema in re.findall(r"`(kartograf-[a-z-]+/\d)`", text):
        if schema != "kartograf-meta/1":  # the sidecar is a file, not a result
            assert schema in SCHEMAS, schema


def test_the_flags_of_the_mcp_server_in_the_guides_are_those_of_the_server():
    from kartograf import mcp_server

    parser = mcp_server._parser()
    options = {flag for action in parser._actions for flag in action.option_strings}
    (line,) = [
        line
        for line in AGENTS.read_text(encoding="utf-8").splitlines()
        if line.startswith("- MCP:")
    ]

    mentioned = set(re.findall(r"--[a-z-]+", line))
    assert {"--allow-writes", "--allow-dir", "--tools"} <= mentioned
    assert mentioned <= options, sorted(mentioned - options)
    assert "kartograf-mcp" in line


def test_the_python_example_is_a_call_of_the_library_with_its_arguments():
    import inspect

    text = AGENTS.read_text(encoding="utf-8")
    (call,) = re.findall(r"`(kartograf\.download_data\([^`]*\))`", text)
    names = re.findall(r"(\w+)=", call)

    assert "download_data" in kartograf.__all__
    assert set(names) <= set(inspect.signature(kartograf.download_data).parameters)


@pytest.mark.parametrize(
    ("path", "least"), [(AGENTS, 14), (LLMS, 2)], ids=["AGENTS.md", "llms.txt"]
)
def test_every_command_line_of_a_guide_is_read_by_the_parser(path, least):
    lines = _quoted_commands(path.read_text(encoding="utf-8"))

    assert len(lines) >= least
    for line in lines:
        check_command_line(line)


def test_the_lines_of_the_flows_and_the_block_are_json_and_absolute():
    flows = AGENTS.read_text(encoding="utf-8").split("## Typical flows")[1]
    block = agent_guide(format="agents-md-block").text
    lines = re.findall(r"^\d+\. `(kartograf [^`]+)`", flows, re.M)
    lines += [line for line in block.splitlines() if line.startswith("kartograf ")]

    assert len(lines) >= 14
    for line in lines:
        words = shlex.split(line)
        assert "--json" in words, line
        if "--root" in words:
            assert Path(words[words.index("--root") + 1]).is_absolute(), line
        check_command_line(line)


# -- a stale example stops the generator ----------------------------------------------


def test_a_renamed_flag_in_a_flow_stops_the_generator(monkeypatch):
    stale = guide_module._Flow(
        "A stale flow",
        "The flag was renamed.",
        (
            guide_module._Step(
                "no such flag", "kartograf elevation download --product nmt --no-such 1"
            ),
        ),
    )
    monkeypatch.setattr(guide_module, "_FLOWS", (stale,))

    with pytest.raises(ValueError, match="rejects"):
        agent_guide(format="agents")


def test_a_rule_that_names_a_missing_option_or_command_stops_the_generator(monkeypatch):
    monkeypatch.setattr(guide_module, "_PRINCIPLES", ("Use `{opt:no_such_option}`.",))
    with pytest.raises(ValueError, match="no_such_option"):
        agent_guide(format="agents")

    monkeypatch.setattr(guide_module, "_PRINCIPLES", ("Run `{cmd:no such}`.",))
    with pytest.raises(ValueError, match="no such"):
        agent_guide(format="agents")


def test_a_code_of_the_registry_without_advice_stops_the_generator(monkeypatch):
    advice = dict(guide_module._ERROR_ADVICE)
    del advice["forbidden"]
    monkeypatch.setattr(guide_module, "_ERROR_ADVICE", advice)

    with pytest.raises(ValueError, match="forbidden"):
        agent_guide(format="agents")


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("<!-- kartograf:nope -->\n", "Unknown guide block"),
        ("<!-- kartograf:one -->\n<!-- kartograf:one -->\n", "used twice"),
        ("text <!-- kartograf:two --> text\n", "several lines"),
    ],
)
def test_a_template_with_a_bad_marker_is_a_program_error(template, message):
    blocks = {"one": lambda: "1", "two": lambda: "a\nb"}

    with pytest.raises(ValueError, match=message):
        guide_module._render(template, blocks)


def test_a_marker_fills_a_line_or_a_place_in_a_line():
    blocks = {"lines": lambda: "a\nb", "word": lambda: "W"}

    rendered = guide_module._render(
        "x <!-- kartograf:word --> y\n<!-- kartograf:lines -->\n", blocks
    )

    assert rendered == ["x W y\n", "a\n", "b\n"]


# -- injecting the block into the AGENTS.md of another repository ---------------------


def test_inject_puts_the_block_at_the_end_and_replaces_it_the_next_time():
    block = agent_guide(format="agents-md-block").text
    mine = "# My project\n\nRules of mine.\n"

    first = inject_block(mine, block)
    again = inject_block(first, block)
    changed = inject_block(first, f"{BLOCK_BEGIN}\nnew\n{BLOCK_END}\n")

    assert first.startswith(mine + "\n" + BLOCK_BEGIN) and first.endswith(
        BLOCK_END + "\n"
    )
    assert again == first  # idempotent (AGI-8.2)
    assert changed.startswith(mine) and "\nnew\n" in changed
    assert changed.count(BLOCK_BEGIN) == 1 and "Kartograf downloads" not in changed
    assert inject_block("", block) == block.strip("\n") + "\n"


def test_inject_keeps_what_follows_the_block():
    block = agent_guide(format="agents-md-block").text
    existing = f"# Mine\n\n{BLOCK_BEGIN}\nold\n{BLOCK_END}\n\n## After\n\ntext\n"

    done = inject_block(existing, block)

    assert done.startswith("# Mine\n\n" + BLOCK_BEGIN)
    assert done.endswith(f"{BLOCK_END}\n\n## After\n\ntext\n")
    assert "old" not in done


# -- kartograf commands guide -----------------------------------------------------


def test_the_cli_prints_the_guide_and_json_prints_the_envelope(capsys):
    assert main(["commands", "guide", "--format", "llms"]) == 0
    text = capsys.readouterr().out
    assert main(["commands", "guide", "--json"]) == 0
    envelope = json.loads(capsys.readouterr().out)

    assert text == LLMS.read_text(encoding="utf-8")
    assert envelope["schema"] == "kartograf-result/1"
    assert envelope["command"] == "commands guide"
    assert envelope["result"]["schema"] == "kartograf-guide/1"
    assert envelope["result"]["format"] == "agents"  # the default
    assert envelope["result"]["text"] == AGENTS.read_text(encoding="utf-8")


def test_the_cli_injects_the_block_into_a_file_and_does_it_once(tmp_path, capsys):
    target = tmp_path / "AGENTS.md"
    target.write_text("# Theirs\n\nTheir rules.\n", encoding="utf-8")
    argv = ["commands", "guide", "--format", "agents-md-block", "--inject", str(target)]

    assert main(argv) == 0
    first = target.read_text(encoding="utf-8")
    assert main(argv) == 0

    assert capsys.readouterr().out == ""  # the block went to the file
    assert first.startswith("# Theirs\n\nTheir rules.\n\n" + BLOCK_BEGIN)
    assert target.read_text(encoding="utf-8") == first
    assert first.count(BLOCK_BEGIN) == 1
    assert list(tmp_path.iterdir()) == [target]  # no temporary file is left


def test_the_cli_creates_the_file_to_inject_into(tmp_path):
    target = tmp_path / "new" / "AGENTS.md"

    assert (
        main(
            [
                "commands",
                "guide",
                "--format",
                "agents-md-block",
                "--inject",
                str(target),
            ]
        )
        == 0
    )

    assert (
        target.read_text(encoding="utf-8") == agent_guide(format="agents-md-block").text
    )


def test_inject_needs_the_block_format(tmp_path, capsys):
    target = tmp_path / "AGENTS.md"

    code = main(["commands", "guide", "--format", "llms", "--inject", str(target)])

    assert code == 2 and not target.exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    document = json.loads(captured.err.splitlines()[-1])
    assert document["code"] == "validation_error"
    assert document["details"]["option"] == "inject"
    assert document["details"]["options"] == ["format", "inject"]
