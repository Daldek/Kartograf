"""Write the reference tables of the documentation from the code (DOC-9.4, DEV-10.4).

Regions of ``docs/USAGE.md`` between ``<!-- generated: NAME ... -->`` and
``<!-- end generated -->`` hold tables built from the package; a contract test
(``tests/contract/test_docs_tables.py``) fails when a region is stale.

Usage::

    uv run scripts/generate_docs.py            # rewrite the regions
    uv run scripts/generate_docs.py --check    # fail when a region is stale
"""

import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE = ROOT / "docs" / "USAGE.md"

_REGION = re.compile(
    r"(?P<start><!-- generated: (?P<name>[a-z-]+) [^\n]*-->\n)"
    r"(?P<body>.*?)"
    r"(?P<end><!-- end generated -->)",
    re.S,
)


def exit_codes_table() -> str:
    """Return the table of the exit codes of the CLI (``kartograf.error_report``)."""
    from kartograf.error_report import EXIT_CODES

    lines = ["| Exit | Name | Meaning |", "|---|---|---|"]
    lines += [f"| {row.code} | `{row.name}` | {row.meaning} |" for row in EXIT_CODES]
    return "\n".join(lines) + "\n"


def error_codes_table() -> str:
    """Return the table of the errors: registry code, reason, exception, exit code."""
    from kartograf.error_report import ERROR_CODES

    lines = [
        "| Code | `details.reason` | Exception | Exit | When |",
        "|---|---|---|---|---|",
    ]
    for row in ERROR_CODES:
        reason = "-" if row.reason is None else f"`{row.reason}`"
        lines.append(
            f"| `{row.code}` | {reason} | `{row.exception}` | {row.exit_code} "
            f"| {row.meaning} |"
        )
    return "\n".join(lines) + "\n"


def mcp_tools_table() -> str:
    """Return the table of the MCP tools (``kartograf.catalog.tools``, AGI-5.2)."""
    from kartograf.catalog.build import command_entries
    from kartograf.catalog.tools import hidden_tools, tool_specs

    documents = {entry.name: entry.result.schema for entry in command_entries()}
    plans = {spec.name for spec in tool_specs(allow_writes=False) if spec.plan_only}
    hidden = set(hidden_tools(allow_writes=False))
    lines = [
        "| Tool | Catalog command | Library function | Families | Document | Hints "
        "| Without `--allow-writes` |",
        "|---|---|---|---|---|---|---|",
    ]
    for spec in tool_specs(allow_writes=True):
        hints = spec.annotations
        shown = ", ".join(
            label
            for label, value in (
                ("RO", hints.read_only_hint),
                ("D", hints.destructive_hint),
                ("I", hints.idempotent_hint),
                ("OW", hints.open_world_hint),
            )
            if value
        )
        if spec.name in hidden:
            mode = "not offered"
        else:
            mode = "plan" if spec.name in plans else "same"
        families = ", ".join(f"`{family}`" for family in spec.families)
        lines.append(
            f"| `{spec.name}` | `{spec.command}` | `{spec.function}` | {families} "
            f"| `{documents[spec.command]}` | {shown} | {mode} |"
        )
    return "\n".join(lines) + "\n"


def mcp_instructions_block() -> str:
    """Return the instructions of the server in a ``text`` fence (AGI-5.10)."""
    from kartograf.mcp_server import INSTRUCTIONS

    return f"```text\n{INSTRUCTIONS}\n```\n"


TABLES: dict[str, Callable[[], str]] = {
    "exit-codes": exit_codes_table,
    "error-codes": error_codes_table,
    "mcp-tools": mcp_tools_table,
    "mcp-instructions": mcp_instructions_block,
}


def render(text: str) -> str:
    """Return ``text`` with every generated region rebuilt from the code.

    Raises
    ------
    ValueError
        A region has an unknown name, or a known table has no region.
    """
    seen: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        if name not in TABLES:
            raise ValueError(f"unknown generated region {name!r}")
        seen.append(name)
        return f"{match.group('start')}{TABLES[name]()}{match.group('end')}"

    done = _REGION.sub(replace, text)
    missing = sorted(set(TABLES) - set(seen))
    if missing:
        raise ValueError(f"no generated region for: {', '.join(missing)}")
    return done


def main(argv: list[str] | None = None) -> int:
    """Write the regions, or with ``--check`` fail when one is stale."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="do not write")
    args = parser.parse_args(argv)
    text = USAGE.read_text(encoding="utf-8")
    done = render(text)
    if args.check:
        if done != text:
            print(f"{USAGE.relative_to(ROOT)} is stale: run generate_docs.py")
            return 1
        return 0
    USAGE.write_text(done, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
