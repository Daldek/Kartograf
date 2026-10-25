"""Guide for AI agents generated from the command catalog (AGI section 8).

:func:`agent_guide` renders ``AGENTS.md`` (``format="agents"``), ``llms.txt``
(``format="llms"``) and the compact block for the ``AGENTS.md`` of a consumer
repository (``format="agents-md-block"``), always in English (AGI-9.2), from the
hand-written templates in ``src/kartograf/_data/agents`` (``<format>.md``). Every marker
``<!-- kartograf:<block> -->`` of a template is replaced by a block generated from the
command catalog, the error registry and the data of this module: the rules of the work
and the typical flows, whose steps are command lines of the catalog. A marker that fills
a whole line takes a block of any number of lines, a marker inside a line a one-line
block; an unknown block or a block used twice is a program error (``ValueError``).

The flows are checked while they are rendered: every line is read by the parser of the
CLI and, for a data command, by ``validate_command``, so a renamed option or command
stops the generator instead of leaving a stale example in the guide. The rules name
options and commands through ``{opt:...}`` and ``{cmd:...}`` placeholders that are
checked against the catalog in the same way.

The output depends only on the installed package (no dates, no version, no local
paths), so ``AGENTS.md`` and ``llms.txt`` in the repository root are derived files that
the tests compare byte for byte with the generator. Regenerate them after any change of
the catalog, the error registry, the templates or this module::

    kartograf commands guide --format agents > AGENTS.md
    kartograf commands guide --format llms > llms.txt

Examples
--------
>>> agent_guide(format="llms").text.splitlines()[0]
'# Kartograf'
"""

import inspect
import re
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.resources import files
from typing import ClassVar, Final

from kartograf.catalog.build import command_entries
from kartograf.catalog.cliparser import build_parser, parse_command_line
from kartograf.catalog.commands import declared
from kartograf.catalog.model import CommandEntry
from kartograf.commands import parse_command, validate_command
from kartograf.error_report import ERROR_CODES
from kartograf.exceptions import ValidationError
from kartograf.serialization import Document

GUIDE_FORMATS: Final[tuple[str, ...]] = ("agents", "llms", "agents-md-block")
"""Formats of :func:`agent_guide` (AGI-3.8)."""
BLOCK_BEGIN: Final = "<!-- BEGIN kartograf -->"
BLOCK_END: Final = "<!-- END kartograf -->"
"""Markers that delimit the block of ``agents-md-block`` (AGI-8.2)."""

_MARKER: Final = re.compile(r"<!--\s*kartograf:(?P<name>[^\s>]*)\s*-->")
_PLACEHOLDER: Final = re.compile(r"\{(?P<kind>opt|cmd):(?P<name>[^{}]+)\}")
_TEMPLATES: Final = ("_data", "agents")
_STORE: Final = "/data/kartograf"
_SHEET: Final = "N-34-130-D-d-2-4"

# The rules of AGENTS.md. ``{opt:name}`` and ``{cmd:name}`` are checked against the
# catalog and replaced by the bare name.
_PRINCIPLES: Final[tuple[str, ...]] = (
    "**Discover, do not guess:** `kartograf {cmd:commands list}` lists the commands "
    "and `kartograf {cmd:commands schema}` (option `{opt:command}`) gives the options "
    "of one, with allowed values and their meanings, rules, examples and errors; in "
    "MCP use `kartograf_commands_list` and `kartograf_commands_schema`.",
    "**Select the data explicitly:** `{opt:product}`, `{opt:resolution}`, "
    "`{opt:vertical_crs}` and the area: `{opt:sheet}`, `{opt:bbox}` with "
    "`{opt:bbox_crs}`, or `{opt:geometry}`, exactly one; `{opt:country}` goes with a "
    "bbox or a geometry. Nothing is guessed: a missing argument is an error with a "
    "hint.",
    "**Absolute paths, outside the repository and /tmp:** `{opt:root}` (CLI "
    "`--root`) is the store; a version is never overwritten, so a rerun is safe.",
    "**Check, then run:** `--check-updates` (MCP: `check_updates`) plans without "
    "fetching; `--upgrade` fetches newer content, `--force` fetches again, and "
    "`--plan` runs a saved plan.",
    "**Decide by codes:** `status` of the envelope (`ok`, `partial`, `failed`), "
    "`code`, `details.option` and `details.reason`, or the exit code; `partial` and "
    "`failed` (exit 10 and 11) are results: read `items` and retry only the failed "
    "units.",
    "**Read `notices`:** non-fatal warnings (a skipped sheet, a mixed campaign); pass "
    "them on with the result.",
    "**MCP reads and plans by default:** without `--allow-writes` a tool that writes "
    "only plans; `--allow-writes` needs `--allow-dir`, and a path outside it is "
    "`forbidden`.",
)
# What each code of the error registry means for an agent.
_ERROR_ADVICE: Final[Mapping[str, str]] = {
    "internal_error": "bug in Kartograf: report the command, options and version",
    "validation_error": "wrong or missing option: fix `details.option` as `hint` says",
    "source_unavailable": "network, HTTP or timeout: wait and retry the same call",
    "no_data": "the source has no data there (`details.reason`): change area or year",
    "store_unavailable": "the metadata cache is locked or unreadable: retry or "
    "`--no-cache`",
    "data_error": "a sidecar is unreadable or of another schema: see `details.path`",
    "missing_dependency": "an extra is missing: install it as `hint` says",
    "forbidden": "MCP refused: a path outside `--allow-dir` or a write without "
    "`--allow-writes`",
    "calculation_error": "a coordinate transformation failed: change the CRS or area",
    "unsupported": "no safe transformation for these coordinate systems: use another",
    "io_error": "a directory or file is unavailable: check `details.path`",
    "cancelled": "interrupted (Ctrl+C): nothing half written, run again",
    "terminated": "ended by SIGTERM: nothing half written, run again",
}


@dataclass(frozen=True)
class AgentGuide(Document):
    """The guide for AI agents (``kartograf-guide/1``).

    Attributes
    ----------
    format : str
        ``agents``, ``llms`` or ``agents-md-block``.
    text : str
        The Markdown of the guide, ending with a newline.
    """

    SCHEMA: ClassVar[str] = "kartograf-guide/1"

    format: str
    text: str


@dataclass(frozen=True)
class _Step:
    """One line of a flow: a command of ``kartograf`` (checked) or of another tool."""

    note: str
    line: str
    external: bool = False


@dataclass(frozen=True)
class _Flow:
    """A typical task of an agent: a title, an introduction and its steps."""

    title: str
    intro: str
    steps: tuple[_Step, ...]


_FLOWS: Final[tuple[_Flow, ...]] = (
    _Flow(
        "The elevation model (NMT) of a sheet",
        "A sheet code (PL-1992 or PL-2000, CZ SM5, TM33 or ZTM) is the shortest way "
        "to name an area.",
        (
            _Step(
                "properties of the sheet, no network.",
                f"kartograf sheet parse {_SHEET} --json",
            ),
            _Step(
                "what the area has (years, grids, vertical CRSs); nothing is fetched.",
                f"kartograf elevation availability --product nmt --sheet {_SHEET} "
                "--json",
            ),
            _Step(
                "the plan (`kartograf-plan/1`): what a run would fetch; nothing is "
                "written.",
                f"kartograf elevation download --product nmt --sheet {_SHEET} "
                f"--resolution 1m --vertical-crs EVRF2007 --root {_STORE} "
                "--check-updates --json",
            ),
            _Step(
                "the run: `kartograf-download/1`, `files[].path` of the versions "
                "written below the store.",
                f"kartograf elevation download --product nmt --sheet {_SHEET} "
                f"--resolution 1m --vertical-crs EVRF2007 --root {_STORE} --json",
            ),
        ),
    ),
    _Flow(
        "An area given as a bounding box, and the point cloud",
        "A bbox needs its CRS (`--bbox-crs`, default EPSG:2180) and a country; an "
        "area gets one request per sheet.",
        (
            _Step(
                "the elevation model of the sheets that cover the area.",
                "kartograf elevation download --product nmt --country pl --bbox "
                "565000,242000,569000,246000 --sheet-system 1992 --resolution 1m "
                f"--vertical-crs EVRF2007 --root {_STORE} --json",
            ),
            _Step(
                "LAZ point clouds of the area.",
                "kartograf elevation download --product laz --country pl --bbox "
                f"530000,382000,533000,386000 --vertical-crs KRON86 --root {_STORE} "
                "--json",
            ),
        ),
    ),
    _Flow(
        "Land cover, soils and hydrologic soil groups (HSG)",
        "Sources and layers (offline): `kartograf landcover list-layers --product "
        "bdot10k`, `kartograf soil list-sources`.",
        (
            _Step(
                "BDOT10k of a county (TERYT code).",
                f"kartograf landcover download --product bdot10k --teryt 1465 "
                f"--root {_STORE} --json",
            ),
            _Step(
                "a SoilGrids layer for an area.",
                "kartograf soil download --property clay --depth 0-5cm --stat mean "
                f"--bbox 626000,480000,628000,482000 --root {_STORE} --json",
            ),
            _Step(
                "the HSG raster from the texture layers, with the share of each "
                "group in `result.summary`.",
                "kartograf soil hsg --depth 0-5cm --bbox 626000,480000,628000,482000 "
                f"--root {_STORE} --summary --json",
            ),
        ),
    ),
    _Flow(
        "A project: tasks with pinned versions",
        "Run the lines in the directory of the project; `--json` goes before the "
        "name of the task.",
        (
            _Step(
                "the project and its store.",
                f"kartograf project init --root {_STORE} --json",
            ),
            _Step(
                "a task: a data command with its options.",
                "kartograf project add --json area elevation download --product nmt "
                f"--sheet {_SHEET} --resolution 1m --vertical-crs EVRF2007",
            ),
            _Step("fetch and pin the versions.", "kartograf project download --json"),
            _Step(
                "is everything there? `status` reads sizes, `verify` the checksums.",
                "kartograf project status --json",
            ),
        ),
    ),
)
# Commands of the compact block: the discovery pair, then the commonest tasks.
_BLOCK_LINES: Final[tuple[str, ...]] = (
    "kartograf commands list --json",
    'kartograf commands schema --command "elevation download" --json',
    f"kartograf sheet parse {_SHEET} --json",
    f"kartograf elevation availability --product nmt --sheet {_SHEET} --json",
    f"kartograf elevation download --product nmt --sheet {_SHEET} --resolution 1m "
    f"--vertical-crs EVRF2007 --root {_STORE} --check-updates --json",
)
_PYTHON_CALL: Final = (
    "kartograf.download_data",
    {
        "product": "nmt",
        "sheet": _SHEET,
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "root": _STORE,
    },
)


# --- helpers --------------------------------------------------------------------


def _code(text: object) -> str:
    return f"`{text}`"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(cell(text) for text in header) + " |",
        "|" + "---|" * len(header),
    ]
    lines += ["| " + " | ".join(cell(text) for text in row) + " |" for row in rows]
    return "\n".join(lines)


def _checked(text: str) -> str:
    """Return ``text`` with its ``{opt:...}`` and ``{cmd:...}`` checked and replaced.

    Raises
    ------
    ValueError
        A placeholder names an option or a command that the catalog lacks.
    """
    entries = command_entries()
    options = {option.name for entry in entries for option in entry.options}
    names = {entry.name for entry in entries}

    def fill(match: re.Match[str]) -> str:
        known, kind = (
            (options, "option") if match["kind"] == "opt" else (names, "command")
        )
        if match["name"] not in known:
            raise ValueError(
                f"The guide names the {kind} {match['name']!r}, which the catalog "
                "does not have"
            )
        return match["name"]

    return _PLACEHOLDER.sub(fill, text)


def _checked_line(line: str) -> str:
    """Return ``line``, a command line of ``kartograf``, after the CLI has read it.

    A data command is validated as well (``validate_command``), without network.

    Raises
    ------
    ValueError
        The parser of the CLI or the library refuses the line.
    """
    words = shlex.split(line)
    if words[0] != "kartograf":
        raise ValueError(
            f"The guide has a line that is not a kartograf command: {line}"
        )
    declarations = declared()
    parser = build_parser(declarations.commands, declarations.groups, usage_errors=True)
    data = {command.id for command in declarations.commands if command.project_task}
    try:
        parsed = parse_command_line(parser, words[1:])
        if getattr(parsed, "_command_id", None) in data:
            call = parse_command(words[1:])
            root = call.run.get("root")
            validate_command(
                call.command,
                call.options,
                root=None if root is None else str(root),
            )
    except (ValidationError, ValueError) as error:
        raise ValueError(
            f"The guide has a line the CLI rejects: {line}: {error}"
        ) from error
    return line


def _rendered_step(step: _Step) -> str:
    """Return the line of a step: checked when it is a command of ``kartograf``."""
    if step.external:
        return step.line
    return _checked_line(step.line)


# --- blocks ---------------------------------------------------------------------


def _rules() -> str:
    return "\n".join(
        f"{number}. {_checked(rule)}" for number, rule in enumerate(_PRINCIPLES, 1)
    )


def _index_line(entry: CommandEntry) -> str:
    """Return the line of a command: name, its MCP tool (if any) and the summary."""
    tool = _code(entry.operation_id) if entry.families else "no MCP tool"
    return f"- {_code(entry.name)} ({tool}): {entry.summary}"


def _index() -> str:
    """Return a line per command, in the order of the catalog."""
    entries: Sequence[CommandEntry] = command_entries()
    return "\n".join(_index_line(entry) for entry in entries)


def _group_names() -> str:
    return ", ".join(_code(group.name) for group in declared().groups)


def _errors() -> str:
    """Return the table of the error codes with what to do about each."""
    rows = []
    seen: set[str] = set()
    for spec in ERROR_CODES:
        if spec.code in seen:
            continue
        seen.add(spec.code)
        advice = _ERROR_ADVICE.get(spec.code)
        if advice is None:
            raise ValueError(
                f"The guide has no advice for the error code {spec.code!r}"
            )
        rows.append((_code(spec.code), str(spec.exit_code), advice))
    return _table(("Code", "Exit", "What to do"), rows)


def _error_codes() -> str:
    seen: dict[str, int] = {}
    for spec in ERROR_CODES:
        seen.setdefault(spec.code, spec.exit_code)
    return ", ".join(f"{_code(code)} ({exit_code})" for code, exit_code in seen.items())


def _python_call() -> str:
    """Return the call of the library the guide shows, checked against its signature."""
    import kartograf  # the package imports this module, so not at the top

    name, arguments = _PYTHON_CALL
    function = getattr(kartograf, name.removeprefix("kartograf."))
    parameters = inspect.signature(function).parameters
    unknown = [argument for argument in arguments if argument not in parameters]
    if unknown:
        raise ValueError(f"The guide calls {name} with unknown arguments: {unknown}")
    shown = ", ".join(f'{key}="{value}"' for key, value in arguments.items())
    return f"{name}({shown})"


def _python_example() -> str:
    return _code(_python_call())


def _cli_example() -> str:
    return _code(_checked_line(_BLOCK_LINES[2]))


def _flows() -> str:
    """Render the typical flows: a numbered CLI line with a note per step."""
    sections = []
    for number, flow in enumerate(_FLOWS, start=1):
        lines = [f"### {number}. {flow.title}", "", flow.intro, ""]
        lines += [
            f"{index}. {_code(_rendered_step(step))} - {step.note}"
            for index, step in enumerate(flow.steps, start=1)
        ]
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _block_commands() -> str:
    """Render the commands of the compact block in a fence."""
    return "\n".join(
        ["```bash", *(_checked_line(line) for line in _BLOCK_LINES), "```"]
    )


def _blocks() -> dict[str, Callable[[], str]]:
    """Build the generated blocks of the guide (rendered only when used)."""
    return {
        "rules": _rules,
        "python_example": _python_example,
        "cli_example": _cli_example,
        "index": _index,
        "group_names": _group_names,
        "errors": _errors,
        "error_codes": _error_codes,
        "flows": _flows,
        "block_commands": _block_commands,
    }


# --- templates ------------------------------------------------------------------


def _render(template: str, blocks: Mapping[str, Callable[[], str]]) -> list[str]:
    """Return the lines of ``template``, each with a newline, every marker replaced.

    Raises
    ------
    ValueError
        A marker names an unknown block, a block is used twice or a multi-line block
        stands inside a line (program errors of a template).
    """
    used: set[str] = set()

    def block(name: str) -> str:
        if name not in blocks:
            raise ValueError(f"Unknown guide block {name!r} in a template")
        if name in used:
            raise ValueError(f"Guide block {name!r} is used twice in a template")
        used.add(name)
        return blocks[name]()

    def inline(match: re.Match[str]) -> str:
        text = block(match["name"])
        if "\n" in text:
            raise ValueError(
                f"Guide block {match['name']!r} has several lines but its marker "
                "stands inside a line of the template"
            )
        return text

    lines: list[str] = []
    for line in template.removesuffix("\n").split("\n"):
        whole = _MARKER.fullmatch(line.strip())
        if whole is not None:
            lines += block(whole["name"]).split("\n")
        else:
            lines.append(_MARKER.sub(inline, line))
    return [f"{line}\n" for line in lines]


def inject_block(existing: str, block: str) -> str:
    r"""Return ``existing`` with its Kartograf block replaced by ``block``.

    The block runs from :data:`BLOCK_BEGIN` to :data:`BLOCK_END`; ``block`` carries
    both markers. A text without the block gets it appended after a blank line, so
    injecting the same block again returns the same text (AGI-8.2).

    Parameters
    ----------
    existing : str
        Current text of the consumer's ``AGENTS.md`` (may be empty).
    block : str
        The block to put in, markers included.

    Returns
    -------
    str
        The new text, ending with a newline.

    Examples
    --------
    >>> inject_block("# Mine\n", "<!-- BEGIN kartograf -->\nx\n<!-- END kartograf -->")
    '# Mine\n\n<!-- BEGIN kartograf -->\nx\n<!-- END kartograf -->\n'
    """
    start = existing.find(BLOCK_BEGIN)
    end = existing.find(BLOCK_END, start) if start >= 0 else -1
    wanted = block.strip("\n")
    if start >= 0 and end >= 0:
        tail = existing[end + len(BLOCK_END) :]
        return existing[:start] + wanted + (tail if tail.strip() else "\n")
    if not existing.strip():
        return wanted + "\n"
    return existing.rstrip("\n") + "\n\n" + wanted + "\n"


def agent_guide(*, format: str = "agents") -> AgentGuide:
    r"""Generate the English guide for AI agents from the command catalog.

    ``format="agents"`` gives ``AGENTS.md`` (at most 200 lines and 16 KiB): purpose and
    scope, install, interfaces, the discover-check-run-read workflow, the result
    envelope, the error codes, the command index, typical flows and what not to do.
    ``format="llms"`` gives ``llms.txt`` in the llmstxt.org layout.
    ``format="agents-md-block"`` gives the compact block (at most 60 lines) between
    :data:`BLOCK_BEGIN` and :data:`BLOCK_END` for the ``AGENTS.md`` of a repository that
    uses Kartograf (see :func:`inject_block`). The text depends only on the installed
    package (no dates, no version, no local paths), so the repository files
    ``AGENTS.md`` and ``llms.txt`` equal ``agent_guide(format=...).text`` byte for byte.

    Parameters
    ----------
    format : {"agents", "llms", "agents-md-block"}, optional
        The guide to generate.

    Returns
    -------
    AgentGuide
        The document ``kartograf-guide/1``; ``text`` is UTF-8 Markdown with ``"\n"``
        line ends, ending with a newline.

    Raises
    ------
    ValidationError
        ``format`` is not allowed (``option="format"``, ``allowed``).
    ValueError
        A template or a flow is inconsistent with the catalog (a program error that
        the tests of the repository catch).
    """
    if format not in GUIDE_FORMATS:
        raise ValidationError(
            f"unknown guide format {format!r}",
            option="format",
            allowed=GUIDE_FORMATS,
        )
    resource = files("kartograf").joinpath(*_TEMPLATES, f"{format}.md")
    template = resource.read_text(encoding="utf-8")
    return AgentGuide(format, "".join(_render(template, _blocks())))
