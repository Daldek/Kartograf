"""Documentation tables that must stay equal to the code (DOC-9.4, DEV-10.4).

The error code and exit code tables of ``docs/USAGE.md`` are generated from the
code (``scripts/generate_docs.py``) and exist only there; the lists of documents
and MCP tools in ``docs/USAGE.md`` and ``docs/ARCHITECTURE.md`` name exactly what
the code registers; the instructions of the MCP server are quoted verbatim;
``CLAUDE.md`` carries the rule for agents of other repositories.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from kartograf import mcp_server
from kartograf.catalog.tools import tool_specs
from kartograf.error_report import ERROR_CODES, EXIT_CODES
from kartograf.serialization import SCHEMAS

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ROOT / "docs"
USAGE = DOCS / "USAGE.md"
ARCHITECTURE = DOCS / "ARCHITECTURE.md"
CLAUDE = ROOT / "CLAUDE.md"

# Documents that describe the code as it is; the specification and the research
# reports keep their own copies of the tables (historical record).
PROSE_DOCS = sorted(DOCS.glob("*.md")) + [ROOT / "README.md", CLAUDE]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """``(line index, level, text)`` of the headings outside code fences."""
    found = []
    fenced = False
    for index, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            match = re.match(r"(#+) (.*)", line)
            if match:
                found.append((index, len(match.group(1)), match.group(2)))
    return found


def _section(text: str, title: str) -> str:
    """The first section whose heading contains ``title``, with its subsections."""
    lines = text.splitlines()
    headings = _headings(lines)
    for position, (start, level, heading) in enumerate(headings):
        if title in heading:
            end = next(
                (
                    following
                    for following, deeper, _ in headings[position + 1 :]
                    if deeper <= level
                ),
                len(lines),
            )
            return "\n".join(lines[start:end])
    raise AssertionError(f"no heading with {title!r}")


def _table_rows(section: str) -> list[list[str]]:
    """The cells of every table row of the section (separator rows dropped)."""
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        rows.append(cells)
    return rows


def _plain(cell: str) -> str:
    return cell.strip("`")


def _docs_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_docs", ROOT / "scripts" / "generate_docs.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_usage_error_and_exit_code_tables_are_generated_from_the_code():
    generator = _docs_generator()

    assert generator.render(_read(USAGE)) == _read(USAGE)
    assert generator.main(["--check"]) == 0


def test_error_and_exit_code_tables_exist_only_in_usage():
    pairs = "|".join(
        f"`{re.escape(e.code)}`\\s*\\|\\s*(?:`[a-z_]+`|-)\\s*\\|\\s*`{re.escape(e.exception)}`"
        for e in ERROR_CODES
    )
    names = "|".join(re.escape(e.name) for e in EXIT_CODES)
    error_row = re.compile(rf"^\|\s*(?:{pairs})\s*\|", re.M)
    exit_row = re.compile(rf"^\|\s*\d+\s*\|\s*`(?:{names})`\s*\|", re.M)

    for path in PROSE_DOCS:
        if path == USAGE:
            continue
        text = _read(path)
        assert not error_row.search(text), f"{path.name}: error code table"
        assert not exit_row.search(text), f"{path.name}: exit code table"


def _library_documents() -> dict[str, list[str]]:
    """Schema -> class names of the documents of the library.

    Other tests register throwaway documents (``kartograf-test-widget/1``) in the
    same registry; they are not documented.
    """
    return {
        schema: [cls.__name__ for cls in classes]
        for schema, classes in SCHEMAS.items()
        if all(cls.__module__.startswith("kartograf.") for cls in classes)
    }


def test_document_tables_name_every_registered_schema_once():
    documents = _library_documents()
    registered = sorted(documents)
    types = sorted(name for names in documents.values() for name in names)
    pattern = re.compile(r"kartograf-[a-z-]+/[1-9][0-9]*")

    usage_rows = _table_rows(_section(_read(USAGE), "JSON documents"))
    usage_schemas = [s for row in usage_rows for s in pattern.findall(row[0])]
    assert sorted(usage_schemas) == registered

    architecture_rows = _table_rows(_section(_read(ARCHITECTURE), "JSON documents"))
    architecture_schemas = [
        s for row in architecture_rows for s in pattern.findall(row[0])
    ]
    assert sorted(architecture_schemas) == registered
    documented_types = [
        name
        for row in architecture_rows
        if pattern.search(row[0])
        for name in re.findall(r"`([A-Za-z]+)`", row[1])
    ]
    assert sorted(documented_types) == types


def test_usage_tool_table_lists_every_mcp_tool():
    rows = _table_rows(_section(_read(USAGE), "MCP server tools"))

    named = [_plain(row[0]) for row in rows if re.fullmatch(r"`[a-z0-9_]+`", row[0])]

    assert sorted(named) == sorted(spec.name for spec in tool_specs(allow_writes=True))
    assert len(named) == 39


def test_usage_quotes_the_instructions_of_the_server():
    section = _section(_read(USAGE), "Server instructions")

    (block,) = re.findall(r"^```text\n(.*?)^```", section, re.M | re.S)

    assert block.strip() == mcp_server.INSTRUCTIONS.strip()


def test_claude_md_has_the_agent_rule_and_points_to_the_generated_guides():
    text = _read(CLAUDE)

    rule = _section(text, "Agenci z innych repozytoriow")

    for needed in (
        "scripts/gate.sh",
        "AGENTS.md",
        "llms.txt",
        "kartograf commands guide",
        "kartograf commands list --json",
        "kartograf-mcp",
    ):
        assert needed in rule, needed
    assert "scripts/gate.sh" in _section(text, "Zasady pracy")
    assert (ROOT / "scripts" / "gate.sh").is_file()
    assert (ROOT / "llms.txt").is_file() and (ROOT / "AGENTS.md").is_file()
