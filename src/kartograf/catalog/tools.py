"""
The tools of the MCP server as data (AGI-5.2 to AGI-5.5, AGI-5.8, AGI-5.12).

Every command of the catalog that has a ``family`` is one tool, in the order of the
catalog. The name is the ``operation_id`` (``kartograf_<group>_<verb>``), the title
is the summary and the description is the summary, the description and the rules of
the declaration (English, at most 600 characters together, DOC-1.7). The input
schema (JSON Schema 2020-12, ``additionalProperties: false``) has one property per
option of the command, with the description, the allowed values, the bounds and the
default of the catalog; a rule among options (``one_of``) is a sentence of their
descriptions, not a keyword that clients reject. ``check_updates`` is an option of
every command that has a check, so there is no separate tool for a check.

The server mode decides what a write tool is (``allow_writes``): with writes it is
the command as declared; without them a command that has a check is its plan-only
variant (the options of a run are gone, ``check_updates`` is fixed to true, the
annotations say read only) and a command that writes without a check
(``project init``, ``project add``, ``project remove``) is not offered at all
(``hidden_tools``).

The module imports nothing of the MCP SDK: ``kartograf.mcp_server`` turns a
``ToolSpec`` into a protocol ``Tool`` and runs it, and tests read these specs
without the SDK installed.

Examples
--------
>>> spec = {s.name: s for s in tool_specs(allow_writes=True)}["kartograf_soil_hsg"]
>>> spec.families, spec.annotations.read_only_hint
(('data', 'core'), False)
>>> "output_dir" in spec.input_schema["required"]
True
"""

import functools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from kartograf._output_schema import OUTPUT_SCHEMA
from kartograf.catalog.build import command_entries, declared_options, effects
from kartograf.catalog.commands import declared
from kartograf.catalog.model import CommandEntry, OptionEntry
from kartograf.catalog.spec import (
    CHECK_OPTION,
    Command,
    Kind,
    Param,
    PathRole,
)
from kartograf.catalog.spec import FAMILIES as COMMAND_FAMILIES
from kartograf.exceptions import ValidationError

FAMILIES: Final[tuple[str, ...]] = (*COMMAND_FAMILIES, "core")
"""What ``--tools`` selects: the families of the commands and ``core`` (AGI-5.12)."""

RUN_OPTIONS: Final[tuple[str, ...]] = ("update", "plan", "workers", "summary")
"""The options of a run: a plan (``check_updates``) has none of them."""

ALWAYS_LOAD_KEY: Final = "anthropic/alwaysLoad"
"""Key of ``_meta`` that tells Claude Code to load a tool's definition up front."""
ALWAYS_LOAD_COMMANDS: Final[tuple[str, ...]] = ("commands list", "commands schema")
"""The catalog commands (AGI-5.9): the only tools marked with ``ALWAYS_LOAD_KEY``."""

DESCRIPTION_MAX: Final = 600
"""Longest description of a tool in characters (DOC-1.7)."""

PLAN_ONLY_NOTE: Final = "This server only plans: nothing is written."
_PLAN_ONLY_DIRECTORY: Final = " This server only plans: nothing is written there."
_PLAN_ONLY_CHECK: Final = " Always true here: this server only plans."

# Options whose allowed values are not listed in the schema: they are the names of
# the commands, which ``kartograf_commands_list`` has, and a second copy in every
# ``tools/list`` is waste.
_NO_ENUM: Final = {("commands schema", "command")}


@dataclass(frozen=True)
class ToolAnnotations:
    """The hints of a tool for the client (the MCP ``ToolAnnotations``, AGI-5.4).

    All five are always set: a client that sees no ``destructiveHint`` assumes the
    tool is destructive.
    """

    title: str
    read_only_hint: bool
    destructive_hint: bool
    idempotent_hint: bool
    open_world_hint: bool


@dataclass(frozen=True)
class ToolSpec:
    """One MCP tool.

    Attributes
    ----------
    name : str
        The tool name: the ``operation_id`` of the command (stable like an error code).
    title : str
        The summary of the command.
    description : str
        Summary, description and rules of the command (the mode of a plan-only tool
        is added); at most ``DESCRIPTION_MAX`` characters.
    input_schema : dict
        JSON Schema 2020-12 of the arguments, as sent to the client; do not modify it.
    output_schema : dict
        The result envelope ``kartograf-result/1``, self-contained; do not modify it.
    annotations : ToolAnnotations
        Hints for the client.
    families : tuple of str
        The families of the tool: its own and ``core`` for the main tasks.
    command : str
        The id of the catalog command the tool runs (``elevation download``).
    function : str
        The library function the command calls (a name of ``kartograf.__all__``).
    check_function : str, optional
        The ``check_*`` twin the tool calls for ``check_updates``.
    kinds : dict
        The catalog kind of every argument that reaches the library
        (``check_updates`` does not).
    fixed : dict
        Constant arguments of the function (the ``group`` of ``<group> list-sources``).
    paths : dict
        The path arguments with what each is for (AGI-2.3 ``path_role``): the sandbox
        of ``--allow-dir`` applies to every one.
    task_options : tuple of str
        The arguments that are options of a data task (``project_task``); the other
        arguments of a data tool belong to its run (``output_dir``, ``update``,
        ``plan``, ``workers``, ``summary``).
    plan_only : bool
        The command writes and has a check, and the server does not write: every
        call is a plan.
    refused : frozenset of str
        The options of a run that a plan-only tool refuses with ``forbidden``.
    always_load : bool
        The definition is loaded up front by the client (``_meta``).
    """

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    annotations: ToolAnnotations
    families: tuple[str, ...]
    command: str
    function: str
    check_function: str | None
    kinds: dict[str, Kind]
    fixed: dict[str, str]
    paths: dict[str, PathRole]
    task_options: tuple[str, ...]
    plan_only: bool
    refused: frozenset[str]
    always_load: bool


def parse_families(text: str) -> tuple[str, ...]:
    """Return the families of the text of ``--tools``: names separated by commas.

    Raises
    ------
    ValidationError
        A name that is not in ``FAMILIES`` (``allowed`` lists them), or no name.
    """
    return check_families([name.strip() for name in text.split(",")])


def check_families(names: Sequence[str]) -> tuple[str, ...]:
    """Return ``names`` when every one is a family of the tools.

    Raises
    ------
    ValidationError
        No family, or one that is not in ``FAMILIES`` (``allowed`` lists them).
    """
    unknown = [name for name in names if name not in FAMILIES]
    if not names or unknown:
        shown = ", ".join(repr(name) for name in unknown) or "none given"
        raise ValidationError(
            f"unknown tool family: {shown}",
            option="families",
            allowed=FAMILIES,
            hint=f"Tool families: {', '.join(FAMILIES)}.",
        )
    return tuple(names)


def _read_only(command: Command) -> bool:
    return effects(command).read_only


def _hidden(command: Command, allow_writes: bool) -> bool:
    """Say whether a server without writes leaves the command out (no check)."""
    return not allow_writes and not _read_only(command) and not command.supports_check


def _plan_only(command: Command, allow_writes: bool) -> bool:
    return not allow_writes and not _read_only(command) and command.supports_check


def _values(option: OptionEntry, command: Command) -> list[Any] | None:
    """Return the allowed values of an option as they go in ``enum`` (``None``: any)."""
    if not option.enum or (command.id, option.name) in _NO_ENUM:
        return None
    return [entry.value for entry in option.enum]


def _string(values: list[Any] | None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string"}
    if values is not None:
        schema["enum"] = values
    return schema


def _property(command: Command, param: Param, option: OptionEntry) -> dict[str, Any]:
    """Return the JSON Schema of one option (AGI-5.5)."""
    values = _values(option, command)
    schema: dict[str, Any]
    match param.kind:
        case "str" | "bbox_crs":
            schema = _string(values)
        case "int":
            schema = {"type": "integer"}
            if option.minimum is not None:
                schema["minimum"] = option.minimum
            if option.maximum is not None:
                schema["maximum"] = option.maximum
            if values is not None:
                schema["enum"] = values
        case "flag":
            schema = {"type": "boolean"}
        case "bbox":
            schema = {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 4,
                "maxItems": 4,
            }
        case "path":
            schema = {"type": "string"}
        case "per_country":
            schema = {
                "anyOf": [
                    _string(values),
                    {
                        "type": "object",
                        "properties": {"pl": _string(values), "cz": _string(values)},
                        "additionalProperties": False,
                    },
                ]
            }
        case "str_list":
            schema = {"type": "array", "items": _string(values)}
        case "plan" | "options":
            schema = {"type": "object"}
        case _:
            raise ValueError(f"{command.id}: kind {param.kind!r} has no JSON Schema")
    schema["description"] = option.description
    if option.default is not None:
        schema["default"] = option.default
    if option.examples:
        schema["examples"] = list(option.examples)
    return schema


@dataclass(frozen=True)
class _Built:
    schema: dict[str, Any]
    kinds: dict[str, Kind]
    paths: dict[str, PathRole]
    refused: frozenset[str]


def _input_schema(command: Command, entry: CommandEntry, *, plan_only: bool) -> _Built:
    """Build the input schema of a command for a mode (see the module docstring)."""
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    kinds: dict[str, Kind] = {}
    paths: dict[str, PathRole] = {}
    refused: set[str] = set()
    for param, option in zip(declared_options(command), entry.options, strict=True):
        name = param.name
        if param.api_argument not in (None, name):
            raise ValueError(f"{command.id}: the option {name!r} has another argument")
        if plan_only and name in RUN_OPTIONS:
            refused.add(name)
            continue
        schema = _property(command, param, option)
        if name == CHECK_OPTION and plan_only:
            schema.update(const=True, default=True)
            schema["description"] += _PLAN_ONLY_CHECK
        elif plan_only and param.path_role in ("root", "output"):
            schema["description"] += _PLAN_ONLY_DIRECTORY
        properties[name] = schema
        if option.required:
            required.append(name)
        if param.api_argument is not None:
            kinds[name] = param.kind
            if param.path_role is not None:
                paths[name] = param.path_role
    root: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        root["required"] = required
    root["additionalProperties"] = False
    if "bbox" in properties and "bbox_crs" in properties:
        root["dependentRequired"] = {"bbox": ["bbox_crs"]}
    return _Built(root, kinds, paths, frozenset(refused))


def _description(entry: CommandEntry, *, plan_only: bool) -> str:
    parts = [entry.summary, entry.description]
    if entry.rules:
        parts.append(" ".join(entry.rules))
    if plan_only:
        parts.append(PLAN_ONLY_NOTE)
    return "\n\n".join(parts)


def _annotations(entry: CommandEntry, *, plan_only: bool) -> ToolAnnotations:
    """Derive the hints from the effects of the command and the mode (AGI-5.4)."""
    changes = entry.effects
    read_only = changes.read_only or plan_only
    return ToolAnnotations(
        title=entry.summary,
        read_only_hint=read_only,
        destructive_hint=changes.destructive and not read_only,
        idempotent_hint=changes.idempotent,
        open_world_hint=changes.network,
    )


def _tool(command: Command, entry: CommandEntry, *, plan_only: bool) -> ToolSpec:
    built = _input_schema(command, entry, plan_only=plan_only)
    return ToolSpec(
        name=entry.operation_id,
        title=entry.summary,
        description=_description(entry, plan_only=plan_only),
        input_schema=built.schema,
        output_schema=OUTPUT_SCHEMA,
        annotations=_annotations(entry, plan_only=plan_only),
        families=entry.families,
        command=command.id,
        function=command.function,
        check_function=command.check_function,
        kinds=built.kinds,
        fixed={
            str(param.api_argument): param.fixed
            for param in command.params
            if param.fixed is not None
        },
        paths=built.paths,
        task_options=tuple(
            str(param.api_argument)
            for param in command.params
            if command.project_task and param.task
        ),
        plan_only=plan_only,
        refused=built.refused,
        always_load=command.id in ALWAYS_LOAD_COMMANDS,
    )


@dataclass(frozen=True)
class _Hidden:
    command: str
    families: tuple[str, ...]


@functools.cache
def _built(allow_writes: bool) -> tuple[tuple[ToolSpec, ...], dict[str, _Hidden]]:
    """Return the tools of a mode, in the order of the catalog, and the hidden ones."""
    specs: list[ToolSpec] = []
    hidden: dict[str, _Hidden] = {}
    for command, entry in zip(declared().commands, command_entries(), strict=True):
        if command.family is None:
            continue
        if _hidden(command, allow_writes):
            hidden[entry.operation_id] = _Hidden(command.id, entry.families)
            continue
        specs.append(_tool(command, entry, plan_only=_plan_only(command, allow_writes)))
    return tuple(specs), hidden


def clear_caches() -> None:
    """Forget the tools built so far (for tests that swap the declarations)."""
    _built.cache_clear()


def tool_specs(
    families: Sequence[str] | None = None, *, allow_writes: bool
) -> tuple[ToolSpec, ...]:
    """Return the tools a server offers, in the order of the catalog.

    Parameters
    ----------
    families : sequence of str, optional
        Only the tools of these families (``FAMILIES``); all by default.
    allow_writes : bool
        Whether the server writes: without it the commands that have a check are
        their plan-only variants and the others that write are left out
        (``hidden_tools``).

    Raises
    ------
    ValidationError
        An unknown family (``option="families"``, ``allowed`` lists them).
    """
    specs = _built(allow_writes)[0]
    if families is None:
        return specs
    wanted = set(check_families(families))
    return tuple(spec for spec in specs if wanted & set(spec.families))


def hidden_tools(
    families: Sequence[str] | None = None, *, allow_writes: bool
) -> dict[str, str]:
    """Return the tools that exist but are not offered: name -> command id.

    These are the commands that write and have no check (``project init``,
    ``project add``, ``project remove``) on a server that does not write; none with
    writes. A call of one is ``forbidden``, not an unknown tool.

    Raises
    ------
    ValidationError
        An unknown family (``option="families"``, ``allowed`` lists them).
    """
    hidden = _built(allow_writes)[1]
    wanted = None if families is None else set(check_families(families))
    return {
        name: item.command
        for name, item in hidden.items()
        if wanted is None or wanted & set(item.families)
    }


def task_paths(command: str) -> dict[str, PathRole]:
    """Return the path options of a data command with what each is for.

    The options of a task nested in ``project add`` follow the sandbox of the server
    like the arguments of a tool.

    Raises
    ------
    KeyError
        ``command`` is not a command of the catalog.
    """
    by_id = {c.id: c for c in declared().commands}
    return {
        param.name: param.path_role
        for param in by_id[command].params
        if param.task and param.kind == "path" and param.path_role is not None
    }
