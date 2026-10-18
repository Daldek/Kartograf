"""
The tools of the MCP server as data (spec 9.3, 9.4).

``tool_specs()`` lists the 29 tools with their JSON Schema 2020-12 input schema
and annotations, built only from the command catalog: a command with a ``tool``
name is a tool (``list_sources`` and ``list_layers`` are one tool for the
commands of several groups), ``check_updates`` is the one tool that checks any
of the twelve data commands (O4) and ``project_check_updates`` the check of a
project. ``check_arguments_schema`` gives the schema of the ``arguments`` of
``check_updates``: that of the data tool without the run options.

The module imports nothing of the MCP SDK: ``kartograf.mcp_server`` turns a
``ToolSpec`` into a protocol ``Tool`` and runs it; tests read these specs
without the SDK installed. Allowed values, required arguments and descriptions
come from ``get_catalog(params=True)``; only the wording that differs between
the CLI and a tool call (the JSON form of ``bbox``, no default ``bbox_crs``, a
plan document instead of a file, absolute paths) is written here.

Examples
--------
>>> spec = {s.name: s for s in tool_specs()}["elevation_download"]
>>> spec.family, spec.annotations.read_only_hint, spec.commands
('data', False, ('elevation download',))
>>> "output_dir" in spec.input_schema["required"]
True
"""

import copy
import functools
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

from kartograf.catalog.build import get_catalog
from kartograf.catalog.model import CommandInfo, ParamInfo
from kartograf.catalog.shared import BBOX_CRS, BBOX_HELP
from kartograf.catalog.spec import Kind

FAMILIES = ("discovery", "availability", "data", "check", "project", "store")

CHECK_UPDATES = "check_updates"
PROJECT_CHECK_UPDATES = "project_check_updates"

# Arguments of the run of a data command (not options of its task): a check takes
# the task options and the store only (``check_command``).
RUN_ARGUMENTS = ("update", "plan", "workers", "summary")

# The tools that are not data commands, by family, in the order of ``tools/list``
# (the data tools follow ``COMMANDS``: the order of the catalog).
_OTHER_TOOLS = {
    "discovery": (
        "get_catalog",
        "parse_sheet",
        "find_sheets",
        "list_sources",
        "list_layers",
    ),
    "availability": ("elevation_availability",),
    "check": (CHECK_UPDATES,),
    "project": (
        "project_init",
        "project_add",
        "project_remove",
        "project_download",
        PROJECT_CHECK_UPDATES,
        "project_status",
        "project_verify",
    ),
    "store": ("store_overview", "store_entries", "store_sidecar"),
}

# What ``ok: false`` says in the document a tool returns (documents without
# ``ok`` have no entry).
_OK_MEANING = {
    "kartograf-download/1": "czesc jednostek sie nie powiodla (failed)",
    "kartograf-plan/1": "czesci pozycji nie dalo sie sprawdzic (check_failed)",
    "kartograf-availability/1": (
        "czesci zapytania nie dalo sie sprawdzic (komunikat check_failed)"
    ),
    "kartograf-project-report/1": "zadanie projektu sie nie powiodlo (failed)",
    "kartograf-project-check/1": (
        "zadanie nie jest pobrane, plik jest niezgodny z przypieciem albo "
        "pozycji nie dalo sie sprawdzic (missing, corrupt, check_failed)"
    ),
}

# Tools that stand for the commands of several groups: the title, the text of
# ``group`` and the only arguments the commands have (a new one is a program
# error, not a silently lost parameter).
_SHARED = {
    "list_sources": (
        "Wypisz zrodla danych grupy (rejestr zrodel, bez sieci)",
        "Grupa komend, ktorej zrodla wypisac",
    ),
    "list_layers": (
        "Wypisz warstwy produktu (landcover) albo wlasciwosci SoilGrids (soil), "
        "bez sieci",
        "Grupa komend: landcover (warstwy produktu product) albo soil "
        "(wlasciwosci SoilGrids)",
    ),
}
_SHARED_ARGUMENTS = ("group", "product")

_CHECK_TITLE = "Sprawdz, czy lokalne wersje danych sa aktualne (bez pobierania)"
_CHECK_SUMMARY = (
    "Porownaj magazyn (output_dir w arguments) z sygnalami zrodel dla zadania "
    "narzedzia danych (tool) i jego argumentow (arguments, bez update, plan, "
    "workers i summary). Nic nie jest pobierane"
)
_CHECK_TOOL_TEXT = "Narzedzie danych, ktorego zadanie sprawdzasz"
_CHECK_ARGUMENTS_TEXT = (
    "Argumenty tego narzedzia danych bez update, plan, workers i summary "
    "(parametry: get_catalog z command=); wymagany output_dir"
)

# The CLI texts of three kinds describe a form a tool call does not have.
_BBOX_TEXT = (
    "Prostokat obszaru: 4 liczby [min_x, min_y, max_x, max_y] w ukladzie bbox_crs "
    "(bbox_crs jest wymagany, bez wartosci domyslnej; S-JTSK: EPSG:5514, np. "
    "[-447000, -1100000, -437000, -1090000])"
)
_BBOX_CRS_TEXT = "Uklad wspolrzednych bbox (wymagany z bbox, bez wartosci domyslnej)"
_PLAN_TEXT = (
    "Plan z check_updates (obiekt kartograf-plan/1) do wykonania z "
    "update=upgrade: pozycje zmienione od planu to blad, bez pobrania"
)
_PATH_TEXT = "Sciezka bezwzgledna."
_DEFAULT_CLAUSE = re.compile(r"\s*\(domyslnie [^)]*\)")

_BBOX_SCHEMA = {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 4,
    "maxItems": 4,
}


@dataclass(frozen=True)
class ToolAnnotations:
    """Hints for the client (the MCP ``ToolAnnotations``); ``None`` = not set.

    ``destructive_hint`` and ``idempotent_hint`` are set for the tools that
    write, ``open_world_hint`` says whether the tool uses the network.
    """

    read_only_hint: bool
    destructive_hint: bool | None
    idempotent_hint: bool | None
    open_world_hint: bool


@dataclass(frozen=True)
class ToolSpec:
    """One MCP tool.

    Attributes
    ----------
    name : str
        The tool name (stable like an error code).
    title : str
        One line: the summary of the command.
    description : str
        The summary and the document the tool returns, with the meaning of ``ok``.
    input_schema : dict
        JSON Schema 2020-12 of the arguments, exactly as sent to the client; do
        not modify it.
    annotations : ToolAnnotations
        Hints for the client.
    family : str
        One of ``FAMILIES`` (what ``kartograf-mcp --tools`` selects).
    commands : tuple of str
        Ids of the catalog commands the tool runs: one, several for a tool shared
        by groups (``list_sources``), none for ``check_updates`` (the command is
        that of the ``tool`` argument).
    function : str, optional
        The library function the tool calls (a name of ``kartograf.__all__``: the
        ``check_function`` of the command for a check); a data tool calls it
        through ``run_command``; ``None`` for ``check_updates``.
    check : bool
        The tool runs the check twin of the command (``check_function``).
    kinds : dict
        Catalog kind of every argument (``path``, ``bbox``, ...).
    task_options : tuple of str
        The arguments that are options of a data task; the other arguments of a
        data tool are those of its run (``output_dir``, ``update``, ``plan``,
        ``workers``, ``summary``).
    """

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    annotations: ToolAnnotations
    family: str
    commands: tuple[str, ...]
    function: str | None
    check: bool
    kinds: dict[str, Kind]
    task_options: tuple[str, ...]


def _describe(param: ParamInfo) -> str:
    """The description of an argument: the catalog text, where the CLI wording
    does not apply to a tool call, in the wording of a tool call."""
    text = param.description
    if param.kind == "bbox":
        return text.replace(BBOX_HELP, _BBOX_TEXT)
    if param.kind == "bbox_crs":
        return _BBOX_CRS_TEXT if text == BBOX_CRS.description else text
    if param.kind == "plan":
        return _PLAN_TEXT
    if param.kind == "path":
        if param.required:
            text = _DEFAULT_CLAUSE.sub("", text)  # no default directory in a call
        if "bezwzgledn" not in text:
            text = f"{text}. {_PATH_TEXT}"
        return text
    return text


def _property(param: ParamInfo) -> dict[str, Any]:
    """The JSON Schema of one argument (spec 9.4 item 2)."""
    allowed = None if param.allowed is None else list(param.allowed)
    schema: dict[str, Any]
    match param.kind:
        case "str" | "bbox_crs":
            schema = {"type": "string"}
            if allowed is not None:
                schema["enum"] = allowed
        case "int":
            schema = {"type": "integer"}
            if param.name == "workers":
                schema["minimum"] = 1
        case "flag":
            schema = {"type": "boolean"}
        case "bbox":
            schema = copy.deepcopy(_BBOX_SCHEMA)
        case "path":
            schema = {"type": "string"}
        case "per_country":
            schema = {
                "anyOf": [
                    {"type": "string"},
                    {
                        "type": "object",
                        "properties": {
                            "pl": {"type": "string"},
                            "cz": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                ]
            }
        case "str_list":
            items: dict[str, Any] = {"type": "string"}
            if allowed is not None:
                items["enum"] = allowed
            schema = {"type": "array", "items": items}
        case "plan" | "options":
            schema = {"type": "object"}
        case _:
            raise ValueError(f"{param.name}: kind {param.kind!r} has no JSON Schema")
    schema["description"] = _describe(param)
    return schema


def _object_schema(
    properties: dict[str, dict[str, Any]], required: Sequence[str]
) -> dict[str, Any]:
    """The root schema of a tool: an object with exactly these arguments."""
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = list(required)
    schema["additionalProperties"] = False
    if "bbox" in properties and "bbox_crs" in properties:
        schema["dependentRequired"] = {"bbox": ["bbox_crs"]}
    return schema


def _from_params(
    params: Sequence[ParamInfo],
) -> tuple[dict[str, Any], dict[str, Kind]]:
    """The input schema and the kind of every argument of the parameters that have
    an API argument."""
    exposed = [param for param in params if param.argument]
    properties = {str(param.argument): _property(param) for param in exposed}
    required = [str(param.argument) for param in exposed if param.required]
    kinds = {str(param.argument): cast(Kind, param.kind) for param in exposed}
    return _object_schema(properties, required), kinds


def _annotations(command: CommandInfo, *, read_only: bool) -> ToolAnnotations:
    network = "network" in command.effects
    if read_only:
        return ToolAnnotations(True, None, None, network)
    return ToolAnnotations(False, command.destructive, command.idempotent, network)


def _result_text(schema: str) -> str:
    text = f"Wynik: {schema}"
    meaning = _OK_MEANING.get(schema)
    return f"{text}; ok=false oznacza, ze {meaning}." if meaning else f"{text}."


def _describe_tool(summary: str, schema: str) -> str:
    return f"{summary.rstrip('.')}. {_result_text(schema)}"


def _command_tool(command: CommandInfo, family: str) -> ToolSpec:
    """A tool that runs one catalog command."""
    assert command.params is not None and command.tool is not None
    schema, kinds = _from_params(command.params)
    return ToolSpec(
        name=command.tool,
        title=command.summary,
        description=_describe_tool(command.summary, command.result_schema),
        input_schema=schema,
        annotations=_annotations(command, read_only=command.kind == "query"),
        family=family,
        commands=(command.id,),
        function=command.function,
        check=False,
        kinds=kinds,
        task_options=tuple(
            str(param.argument) for param in command.params if param.task
        ),
    )


def _shared_tool(name: str, commands: Sequence[CommandInfo], family: str) -> ToolSpec:
    """One tool for the commands of several groups: ``group`` picks the command."""
    title, group_text = _SHARED[name]
    products: list[ParamInfo] = []
    for command in commands:
        assert command.params is not None
        arguments = [str(param.argument) for param in command.params if param.argument]
        if not set(arguments) <= set(_SHARED_ARGUMENTS):
            raise ValueError(
                f"{command.id}: the tool {name} is shared, its arguments are "
                f"{_SHARED_ARGUMENTS}, not {arguments}"
            )
        products += [param for param in command.params if param.argument == "product"]
    properties: dict[str, dict[str, Any]] = {
        "group": {
            "type": "string",
            "enum": [str(command.group) for command in commands],
            "description": group_text,
        }
    }
    kinds: dict[str, Kind] = {"group": "str"}
    if products:
        values = list(
            dict.fromkeys(v for param in products for v in param.allowed or ())
        )
        properties["product"] = {
            "type": "string",
            "enum": values,
            "description": products[0].description,
        }
        kinds["product"] = "str"
    first = commands[0]
    return ToolSpec(
        name=name,
        title=title,
        description=_describe_tool(title, first.result_schema),
        input_schema=_object_schema(properties, ["group"]),
        annotations=_annotations(first, read_only=True),
        family=family,
        commands=tuple(command.id for command in commands),
        function=first.function,
        check=False,
        kinds=kinds,
        task_options=(),
    )


def _check_updates_tool(data: Sequence[ToolSpec], check_schema: str) -> ToolSpec:
    """``check_updates``: any data tool and its arguments (O4)."""
    properties: dict[str, dict[str, Any]] = {
        "tool": {
            "type": "string",
            "enum": [spec.name for spec in data],
            "description": _CHECK_TOOL_TEXT,
        },
        "arguments": {"type": "object", "description": _CHECK_ARGUMENTS_TEXT},
    }
    return ToolSpec(
        name=CHECK_UPDATES,
        title=_CHECK_TITLE,
        description=_describe_tool(_CHECK_SUMMARY, check_schema),
        input_schema=_object_schema(properties, ["tool", "arguments"]),
        annotations=ToolAnnotations(True, None, None, True),
        family="check",
        commands=(),
        function=None,
        check=True,
        kinds={"tool": "str", "arguments": "options"},
        task_options=(),
    )


def _project_check_tool(command: CommandInfo) -> ToolSpec:
    """``project_check_updates``: ``check_project`` of ``project download``."""
    assert command.params is not None and command.check_result_schema is not None
    params = [param for param in command.params if param.name not in RUN_ARGUMENTS]
    schema, kinds = _from_params(params)
    title = next(
        param.description for param in command.params if param.name == "check_updates"
    )
    return ToolSpec(
        name=PROJECT_CHECK_UPDATES,
        title=title,
        description=_describe_tool(title, command.check_result_schema),
        input_schema=schema,
        annotations=_annotations(command, read_only=True),
        family="project",
        commands=(command.id,),
        function=command.check_function,
        check=True,
        kinds=kinds,
        task_options=(),
    )


def _check_schema(spec: ToolSpec) -> dict[str, Any]:
    """The schema of a data tool for a check: the task options and ``output_dir``."""
    keep = {*spec.task_options, "output_dir"}
    properties = {
        name: copy.deepcopy(schema)
        for name, schema in spec.input_schema["properties"].items()
        if name in keep
    }
    required = [name for name in spec.input_schema.get("required", ()) if name in keep]
    return _object_schema(properties, required)


@functools.cache
def _built() -> tuple[tuple[ToolSpec, ...], dict[str, dict[str, Any]]]:
    """Every tool in the order of ``FAMILIES`` and the check schema of every data
    tool."""
    catalog = get_catalog(params=True)
    by_tool: dict[str, list[CommandInfo]] = {}
    for command in catalog.commands:
        if command.tool is not None:
            by_tool.setdefault(command.tool, []).append(command)
    data_commands = [command for command in catalog.commands if command.project_task]
    data = [_command_tool(command, "data") for command in data_commands]
    listed = {name for names in _OTHER_TOOLS.values() for name in names}
    derived = {CHECK_UPDATES, PROJECT_CHECK_UPDATES}
    unknown = set(by_tool) - listed - {spec.name for spec in data}
    if unknown:
        raise ValueError(f"tools without a family: {sorted(unknown)}")
    missing = listed - derived - set(by_tool)
    if missing:
        raise ValueError(f"tools of no catalog command: {sorted(missing)}")
    check_schema = data_commands[0].check_result_schema
    assert check_schema is not None

    def make(name: str, family: str) -> ToolSpec:
        if name == CHECK_UPDATES:
            return _check_updates_tool(data, check_schema)
        if name == PROJECT_CHECK_UPDATES:
            return _project_check_tool(by_tool["project_download"][0])
        commands = by_tool[name]
        if name in _SHARED:
            return _shared_tool(name, commands, family)
        return _command_tool(commands[0], family)

    specs: list[ToolSpec] = []
    for family in FAMILIES:
        if family == "data":
            specs += data
        else:
            specs += [make(name, family) for name in _OTHER_TOOLS[family]]
    return tuple(specs), {spec.name: _check_schema(spec) for spec in data}


def tool_specs(families: Sequence[str] | None = None) -> tuple[ToolSpec, ...]:
    """The tools of the given families (all by default) in the order of
    ``FAMILIES``.

    Raises
    ------
    ValueError
        A family that is not in ``FAMILIES``.
    """
    specs = _built()[0]
    if families is None:
        return specs
    unknown = [family for family in families if family not in FAMILIES]
    if unknown:
        raise ValueError(
            f"nieznana rodzina narzedzi: {', '.join(unknown)} "
            f"(dozwolone: {', '.join(FAMILIES)})"
        )
    return tuple(spec for spec in specs if spec.family in families)


def check_arguments_schema(tool: str) -> dict[str, Any]:
    """The schema of the ``arguments`` of ``check_updates`` for a data tool: its
    input schema without the arguments of a run (``update``, ``plan``,
    ``workers``, ``summary``), ``output_dir`` still required.

    Raises
    ------
    ValueError
        ``tool`` is not the name of a data tool.
    """
    schemas = _built()[1]
    if tool not in schemas:
        raise ValueError(
            f"{tool!r} nie jest narzedziem danych (dozwolone: {', '.join(schemas)})"
        )
    return copy.deepcopy(schemas[tool])
