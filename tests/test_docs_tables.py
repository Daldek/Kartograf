"""Documentation tables that must stay equal to the code (spec 10.4, 10.5).

``docs/USAGE.md`` holds the only error code and exit code tables of the
documentation and they equal the command catalog; the lists of documents and
MCP tools in ``docs/USAGE.md`` and ``docs/ARCHITECTURE.md`` name exactly what
the code registers; the instructions of the MCP server are quoted verbatim;
``CLAUDE.md`` carries the rule for agents of other repositories.
"""

import re
from pathlib import Path

from kartograf import get_catalog, mcp_server
from kartograf.catalog.tools import tool_specs
from kartograf.serialization import SCHEMAS

ROOT = Path(__file__).resolve().parent.parent
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


def test_usage_error_and_exit_code_tables_equal_the_catalog():
    catalog = get_catalog(tables=True)
    assert catalog.exit_codes is not None and catalog.errors is not None
    rows = _table_rows(_section(_read(USAGE), "Kody wyjscia i kody bledow"))

    exit_rows = [(int(row[0]), _plain(row[1])) for row in rows if row[0].isdigit()]
    error_rows = [
        (_plain(row[0]), _plain(row[1]), int(row[2]))
        for row in rows
        if re.fullmatch(r"`[a-z_]+`", row[0])
    ]

    assert sorted(exit_rows) == sorted((e.code, e.name) for e in catalog.exit_codes)
    assert sorted(error_rows) == sorted(
        (e.code, e.exception, e.exit_code) for e in catalog.errors
    )


def test_error_and_exit_code_tables_exist_only_in_usage():
    catalog = get_catalog(tables=True)
    assert catalog.exit_codes is not None and catalog.errors is not None
    pairs = "|".join(
        f"`{re.escape(e.code)}`\\s*\\|\\s*`{re.escape(e.exception)}`"
        for e in catalog.errors
    )
    names = "|".join(re.escape(e.name) for e in catalog.exit_codes)
    error_row = re.compile(rf"^\|\s*(?:{pairs})\s*\|", re.M)
    exit_row = re.compile(rf"^\|\s*\d+\s*\|\s*`(?:{names})`\s*\|", re.M)

    for path in PROSE_DOCS:
        if path == USAGE:
            continue
        text = _read(path)
        assert not error_row.search(text), f"{path.name}: error code table"
        assert not exit_row.search(text), f"{path.name}: exit code table"


def test_document_tables_name_every_registered_schema_once():
    registered = sorted(SCHEMAS)
    types = sorted(cls.__name__ for classes in SCHEMAS.values() for cls in classes)
    pattern = re.compile(r"kartograf-[a-z-]+/[1-9][0-9]*")

    usage_rows = _table_rows(_section(_read(USAGE), "Dokumenty JSON"))
    usage_schemas = [s for row in usage_rows for s in pattern.findall(row[0])]
    assert sorted(usage_schemas) == registered

    architecture_rows = _table_rows(_section(_read(ARCHITECTURE), "Dokumenty JSON"))
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
    rows = _table_rows(_section(_read(USAGE), "Narzedzia serwera MCP"))

    named = [_plain(row[1]) for row in rows if re.fullmatch(r"`[a-z0-9_]+`", row[1])]

    assert sorted(named) == sorted(spec.name for spec in tool_specs())


def test_usage_quotes_the_instructions_of_the_server():
    section = _section(_read(USAGE), "Instrukcje serwera")

    (block,) = re.findall(r"^```text\n(.*?)^```", section, re.M | re.S)

    assert block.strip() == mcp_server.INSTRUCTIONS.strip()


def test_claude_md_has_the_agent_rule_and_no_agents_md():
    text = _read(CLAUDE)

    rule = _section(text, "Agenci z innych repozytoriow")

    for needed in (
        "scripts/gate.sh",
        "llms.txt",
        "kartograf catalog --json",
        "kartograf-mcp",
    ):
        assert needed in rule, needed
    assert "scripts/gate.sh" in _section(text, "Zasady pracy")
    assert (ROOT / "scripts" / "gate.sh").is_file()
    assert (ROOT / "llms.txt").is_file()
    assert not (ROOT / "AGENTS.md").exists()
