"""
The tools of the MCP server as data (spec 9.3, 9.4).

``tool_specs()`` lists the 30 tools with their JSON Schema 2020-12 input schema
and annotations, built only from the command catalog: a command with a ``tool``
name is a tool (``list_sources`` and ``list_layers`` are one tool for the
commands of several groups), ``check_updates`` is the one tool that checks any
of the twelve data commands (O4) and ``project_check_updates`` the check of a
project. ``check_arguments_schema`` gives the schema of the ``arguments`` of
``check_updates``: that of the data tool without the run options.

The module imports nothing of the MCP SDK: ``kartograf.mcp_server`` turns a
``ToolSpec`` into a protocol ``Tool`` and runs it; tests read these specs
without the SDK installed.

The list of the tools is what a client puts in the context of the model at the
start of every conversation, so it is short: the names, kinds and allowed
values of the arguments come from the declarations, but the wording is not the
catalog's. A catalog description is the CLI help (long, with flags and every
allowed value) and is read on demand with ``commands_schema``; the
descriptions here are a few words written for a tool call (``_BRIEF``), and a
tool says where the rest is. No ``$ref``: clients do not agree on resolving it
(Claude Code and Codex hand a model an object behind a ``$ref`` as a string).

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
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from kartograf.catalog.commands import declared
from kartograf.catalog.spec import Command, Kind, Param, resolve

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
        "commands_list",
        "commands_schema",
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

# Tools that stand for the commands of several groups: the summary and the text of
# ``group`` and ``product`` (the commands have no other arguments: a new one is a
# program error, not a silently lost parameter).
_SHARED = {
    "list_sources": (
        "Wypisz zrodla danych grupy (rejestr zrodel, bez sieci)",
        "Grupa, ktorej zrodla wypisac",
        "Tylko zrodla tego produktu (domyslnie wszystkie produkty grupy)",
    ),
    "list_layers": (
        "Wypisz warstwy produktu (landcover) albo wlasciwosci SoilGrids (soil), "
        "bez sieci",
        "Grupa, ktorej warstwy wypisac",
        "Produkt landcover, ktorego warstwy wypisac",
    ),
}
_SHARED_ARGUMENTS = ("group", "product")

_CHECK_SUMMARY = (
    "Porownaj magazyn z sygnalami zrodel dla zadania narzedzia danych (tool) i "
    "jego argumentow (arguments: te same, bez update, plan, workers i summary; "
    "output_dir wymagany). Nic nie jest pobierane"
)
_CHECK_TOOL_TEXT = "Narzedzie danych, ktorego zadanie sprawdzasz"
_CHECK_ARGUMENTS_TEXT = "Argumenty tego narzedzia danych, z output_dir"

# Where a tool sends for the arguments it does not list in words.
_PARAMS_POINTER = 'Parametry: commands_schema(command="{}").'
_ADD_POINTER = "Parametry komendy: commands_schema(command=<command>)."

# Arguments whose allowed values the catalog has but a tool does not list: the
# list is as long as the overview and an unknown value is an error that names
# the allowed ones.
_NO_ENUM = {("commands_schema", "command")}

# What a tool call says about an argument, in a few words: the allowed values
# are in the schema (``enum``), whether it is required in ``required``, the long
# text (flags, every value, the cases of the CLI) in ``commands_schema``. ``None``:
# the name, the type and the values say enough, or the argument means the same
# in many tools and the instructions of the server say it once (the area, the
# store directory, the update mode: ``mcp_server.INSTRUCTIONS``). ``_BRIEF_FOR``
# is the wording of one tool where the argument means something else than
# elsewhere. Every argument of every tool has an entry (a new argument of the
# catalog fails the build of the specs until it gets one).
_BRIEF: dict[str, str | None] = {
    "all_campaigns": "Wszystkie loty z zakresu lat, nie tylko najnowszy",
    "bbox": "[min_x, min_y, max_x, max_y]",
    "bbox_crs": None,
    "children": "Bezposrednie arkusze potomne (tylko godla PL)",
    "country": None,
    "coverage": "Wariant WCS wycinka ortofotomapy",
    "cutout": "Jeden wycinek WCS zamiast arkuszy; wymaga horizontal_crs",
    "depth": None,
    "descendants": "Wszystkie arkusze potomne do tej skali, np. 1:10000 (PL)",
    "direction": "Kierunki widoku; domyslnie wszystkie",
    "force": "Pomin cache metadanych",
    "format": "Format pliku; wartosci zaleza od produktu i kraju",
    "full_sheet": "Dolacz najnowszy pelny lot arkusza (w full_sheet/)",
    "geometry": None,
    "hierarchy": "Hierarchia arkuszy do skali 1:1000000 (tylko godla PL)",
    "horizontal_crs": "Uklad poziomy wycinka albo pliku krajowego",
    "keep_raw": "Zachowaj oryginalny ZIP GUGiK (tylko biezace BDOT10k GPKG)",
    "ku": "Kod katastralniho uzemi CZ (6 cyfr)",
    "layer": None,
    "layers": "Kody warstw BDOT10k albo klas BDOO; domyslnie wszystkie",
    "level": "Poziom jednostek obszaru; wartosci zaleza od produktu i kraju",
    "limit": "Najwyzej tyle wpisow; truncated w wyniku mowi o dalszych",
    "lod": "Poziom szczegolowosci (LoD) paczek modeli",
    "max_year": None,
    "min_density": "Tylko LAZ PL: kafle o gestosci >= N pkt/m2",
    "min_year": None,
    "model": "Model chmury LAZ CZ (wymagany z product=laz dla CZ)",
    "name": "Nazwa zadania",
    "network": "Siec osnowy; wartosci zaleza od kraju",
    "options": "Opcje zadania jak argumenty narzedzia danych, bez output_dir",
    "output_dir": None,
    "path": "Plik magazynu albo jego sidecar .meta.json (sciezka bezwzgledna)",
    "plan": None,
    "product": None,
    "project_dir": None,
    "property": None,
    "resolution": "Rozdzielczosc siatki, np. 1m; wartosci zaleza od produktu i kraju",
    "scale": "Skala arkuszy PL-2000 (z sheet_system 2000)",
    "segment": "Segment magazynu, np. nmt/pl_1992_1m_evrf2007 (z store_overview)",
    "sheet": None,
    "sheet_system": "Uklad godel PL (z sheet wynika z godla)",
    "stat": None,
    "summary": "Dodaj podsumowanie grup A-D (udzial i powierzchnia)",
    "tasks": "Tylko te zadania (domyslnie wszystkie)",
    "teryt": "Kod TERYT: wojewodztwo (2 cyfry) albo powiat (4 cyfry)",
    "units": "Tylko te jednostki segmentu (nazwy jak sidecar.unit)",
    "update": None,
    "vertical_crs": "Uklad wysokosci, np. EVRF2007; osobno per kraj: {pl, cz}",
    "whole_country": "Plik krajowy zamiast obszaru (wymaga country pl albo cz)",
    "workers": None,
    "year": None,
}
_BRIEF_FOR: dict[tuple[str, str], str | None] = {
    ("commands_schema", "command"): (
        "Nazwa komendy z commands_list (np. elevation download) albo jej operation_id"
    ),
    ("find_sheets", "scale"): "Skala arkuszy (zalezy od ukladu godel)",
    ("find_sheets", "sheet_system"): None,
    ("imagery_download", "cutout"): (
        "Jeden wycinek WCS (tylko PL); wymaga horizontal_crs"
    ),
    ("imagery_download", "resolution"): "Piksel wycinka (z cutout)",
    ("landcover_download", "year"): "Rocznik archiwum albo wydanie (CORINE, BDOO)",
    ("maps_download", "scale"): "Skala mapy",
    ("maps_download", "sheet_system"): "Uklad arkuszy ZTM (CZ)",
    ("models3d_download", "year"): "Rok wydania paczek albo rok danych kafli mesh",
    ("parse_sheet", "sheet"): "Godlo: PL-1992, PL-2000, SM5, TM33 albo ZTM",
    ("project_add", "command"): "Komenda danych zadania",
    ("project_download", "update"): (
        "Pominiety: tylko niepobrane zadania; inaczej przepina cale zadanie"
    ),
    ("project_remove", "name"): "Nazwa zadania do usuniecia",
}

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
    description : str
        The summary of the command, where the arguments are described
        (``commands_schema``) and the document the tool returns; there is no title:
        the first sentence is the summary.
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
    description: str
    input_schema: dict[str, Any]
    annotations: ToolAnnotations
    family: str
    commands: tuple[str, ...]
    function: str | None
    check: bool
    kinds: dict[str, Kind]
    task_options: tuple[str, ...]


def _brief(tool: str, name: str) -> str | None:
    """Return the words a tool call has for an argument (``None``: none)."""
    if (tool, name) in _BRIEF_FOR:
        return _BRIEF_FOR[tool, name]
    if name in _BRIEF:
        return _BRIEF[name]
    raise ValueError(
        f"{tool}: the argument {name} has no wording for a tool call "
        "(add it to _BRIEF or _BRIEF_FOR; None = name, type and values only)"
    )


def _property(param: Param, tool: str) -> dict[str, Any]:
    """Return the JSON Schema of one argument (spec 9.4 item 2)."""
    values = resolve(param.allowed)
    listed = values is not None and (tool, param.name) not in _NO_ENUM
    allowed = list(values) if listed and values is not None else None
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
    text = _brief(tool, param.name)
    if text is not None:
        schema["description"] = text
    return schema


def _object_schema(
    properties: dict[str, dict[str, Any]], required: Sequence[str]
) -> dict[str, Any]:
    """Return the root schema of a tool: an object with exactly these arguments."""
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = list(required)
    schema["additionalProperties"] = False
    if "bbox" in properties and "bbox_crs" in properties:
        schema["dependentRequired"] = {"bbox": ["bbox_crs"]}
    return schema


def _from_params(
    params: Sequence[Param], tool: str
) -> tuple[dict[str, Any], dict[str, Kind]]:
    """Return the input schema and the kind of every argument.

    The parameters that have an API argument are used.
    """
    exposed = [param for param in params if param.api_argument]
    properties = {str(param.api_argument): _property(param, tool) for param in exposed}
    required = [str(param.api_argument) for param in exposed if param.required]
    kinds = {str(param.api_argument): param.kind for param in exposed}
    return _object_schema(properties, required), kinds


def _annotations(command: Command, *, read_only: bool) -> ToolAnnotations:
    network = "network" in command.effects
    if read_only:
        return ToolAnnotations(True, None, None, network)
    return ToolAnnotations(False, command.destructive, command.idempotent, network)


def _describe_tool(
    summary: str, schema: str | None = None, pointer: str | None = None
) -> str:
    """Return ``<summary>. <where the arguments are>. Wynik: <document>.``.

    A data tool names no document: all twelve return the same, the instructions say
    which.
    """
    parts = [f"{summary.rstrip('.')}."]
    if pointer is not None:
        parts.append(pointer)
    if schema is not None:
        parts.append(f"Wynik: {schema}.")
    return " ".join(parts)


def _command_tool(command: Command, family: str) -> ToolSpec:
    """Build the tool that runs one catalog command."""
    assert command.tool is not None
    schema, kinds = _from_params(command.params, command.tool)
    pointer: str | None = None
    result: str | None = command.result_schema
    if command.project_task:
        pointer, result = _PARAMS_POINTER.format(command.id), None
    elif command.tool == "project_add":
        pointer = _ADD_POINTER
    return ToolSpec(
        name=command.tool,
        description=_describe_tool(command.summary_pl, result, pointer),
        input_schema=schema,
        annotations=_annotations(command, read_only=command.kind == "query"),
        family=family,
        commands=(command.id,),
        function=command.function,
        check=False,
        kinds=kinds,
        task_options=tuple(
            str(param.api_argument) for param in command.params if param.task
        ),
    )


def _shared_tool(name: str, commands: Sequence[Command], family: str) -> ToolSpec:
    """One tool for the commands of several groups: ``group`` picks the command."""
    title, group_text, product_text = _SHARED[name]
    has_product = False
    for command in commands:
        arguments = [
            str(param.api_argument) for param in command.params if param.api_argument
        ]
        if not set(arguments) <= set(_SHARED_ARGUMENTS):
            raise ValueError(
                f"{command.id}: the tool {name} is shared, its arguments are "
                f"{_SHARED_ARGUMENTS}, not {arguments}"
            )
        has_product = has_product or "product" in arguments
    properties: dict[str, dict[str, Any]] = {
        "group": {
            "type": "string",
            "enum": [str(command.group) for command in commands],
            "description": group_text,
        }
    }
    kinds: dict[str, Kind] = {"group": "str"}
    if has_product:
        properties["product"] = {"type": "string", "description": product_text}
        kinds["product"] = "str"
    first = commands[0]
    return ToolSpec(
        name=name,
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


def _project_check_tool(command: Command) -> ToolSpec:
    """``project_check_updates``: ``check_project`` of ``project download``."""
    assert command.check_result_schema is not None
    params = [param for param in command.params if param.name not in RUN_ARGUMENTS]
    schema, kinds = _from_params(params, PROJECT_CHECK_UPDATES)
    summary = next(
        resolve(param.description_pl)
        for param in command.params
        if param.name == "check_updates"
    )
    return ToolSpec(
        name=PROJECT_CHECK_UPDATES,
        description=_describe_tool(summary, command.check_result_schema),
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
    """Return the schema of a data tool for a check.

    The task options and ``output_dir``.
    """
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
    """Return every tool in the order of ``FAMILIES`` and the check schemas.

    The check schema of every data tool is included.
    """
    commands = declared().commands
    by_tool: dict[str, list[Command]] = {}
    for command in commands:
        if command.tool is not None:
            by_tool.setdefault(command.tool, []).append(command)
    data_commands = [command for command in commands if command.project_task]
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
    """Return the tools of the given families.

    All families are the default; the order is that of ``FAMILIES``.

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
    """Return the schema of the ``arguments`` of ``check_updates`` for a data tool.

    Its input schema without the arguments of a run (``update``, ``plan``, ``workers``,
    ``summary``), ``output_dir`` still required.

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
