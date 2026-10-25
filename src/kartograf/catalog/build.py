"""
The catalog documents built from the declarations (spec 8.5).

``list_commands`` and ``command_schema`` resolve the providers of the declarations of
``kartograf/catalog/commands/`` and build ``CommandList`` (``kartograf-command-list/1``)
and ``CommandCatalog`` (``kartograf-commands/1``). The entry of every command is built
once per process and is read-only; ``command_schema`` picks one of them.

An *option* of a command is a parameter that has an argument of the library function
(and so a key of an MCP tool call) and the plan option ``check`` of a command
that has a check; a flag only the CLI has (``--json``, ``--quiet``, ``--upgrade``,
``--force``) and the constant argument of ``<group> list-sources`` are not options
(``is_option``).
"""

import functools
from collections.abc import Sequence

from kartograf.catalog.commands import declared
from kartograf.catalog.excerpts import EXCERPTS
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.meanings import meaning
from kartograf.catalog.model import (
    CommandCatalog,
    CommandEntry,
    CommandList,
    CommandRow,
    EffectsEntry,
    EnumValue,
    ExampleEntry,
    GroupRow,
    I18nEntry,
    OptionEntry,
    PolishTexts,
    ResultEntry,
)
from kartograf.catalog.spec import (
    CHECK_OPTION,
    Command,
    Constraint,
    Group,
    Param,
    check_declarations,
    resolve,
    sorted_groups,
)
from kartograf.exceptions import ValidationError
from kartograf.messages import localize, message

TOOL = "kartograf"

# The JSON type of a parameter kind (a ``per_country`` value is a text, or an object
# with the keys ``pl`` and ``cz`` that the description of the option names).
_TYPES = {
    "str": "string",
    "int": "integer",
    "flag": "boolean",
    "bbox": "array",
    "bbox_crs": "string",
    "path": "string",
    "per_country": "string",
    "str_list": "array",
    "plan": "object",
    "options": "object",
}
_ITEMS = {"bbox": "number", "str_list": "string"}
_UNITS = {"bbox": "m, or degrees for EPSG:4326"}
# What changes the world outside the process (``Command.effects``).
_WRITING = frozenset({"store_write", "project_write", "cache_write", "cache_delete"})


def is_option(command: Command, param: Param) -> bool:
    """Check whether a parameter is an option of the command in every interface.

    It has an argument of the library function, or it is ``check`` of a command
    with a check; the constant argument of a command (``fixed``) is none.
    """
    if param.fixed is not None:
        return False
    return param.api_argument is not None or (
        param.name == CHECK_OPTION and command.supports_check
    )


def declared_options(command: Command) -> tuple[Param, ...]:
    """Return the parameters of a command that are its options, in declaration order."""
    return tuple(param for param in command.params if is_option(command, param))


def one_of_constraints(command: Command) -> tuple[Constraint, ...]:
    """Return the mutual exclusion groups of the command (``one_of`` constraints).

    Raises
    ------
    ValueError
        Two constraints name the same group, or one option is in two groups.
    """
    found = tuple(c for c in command.constraints if c.type == "one_of")
    groups = [c.group for c in found]
    options = [name for c in found for name in c.params]
    if len(set(groups)) != len(groups) or len(set(options)) != len(options):
        raise ValueError(f"{command.id}: a one_of group or option is declared twice")
    return found


def _one_of_sentence(constraint: Constraint) -> str:
    names = ", ".join(f"`{name}`" for name in constraint.params)
    if constraint.optional:
        return f" Give at most one of {names}."
    return f" Give exactly one of {names}."


def _summaries(commands: Sequence[Command]) -> dict[str, str]:
    """Return the summary of every command by its id."""
    return {command.id: command.summary for command in commands}


def _enum(param: Param, summaries: dict[str, str]) -> tuple[EnumValue, ...] | None:
    """Return the allowed values of a parameter with their meanings."""
    allowed = resolve(param.allowed)
    if allowed is None:
        return None
    values = []
    for value in allowed:
        if param.name == "command":  # a command of the catalog says itself
            text = summaries[str(value)]
        else:
            text = meaning(param.name, str(value))
        values.append(
            EnumValue(int(value) if param.kind == "int" else str(value), text)
        )
    return tuple(values)


def _option(command: Command, param: Param, summaries: dict[str, str]) -> OptionEntry:
    description = resolve(param.description)
    group = next(
        (c for c in one_of_constraints(command) if param.name in c.params), None
    )
    if group is not None:
        description += _one_of_sentence(group)
    return OptionEntry(
        name=param.name,
        type=_TYPES[param.kind],
        required=param.required,
        description=description,
        items=_ITEMS.get(param.kind),
        unit=param.unit or _UNITS.get(param.kind),
        default=param.default,
        enum=_enum(param, summaries),
        minimum=param.minimum,
        maximum=param.maximum,
        examples=param.examples or None,
        one_of=group.group if group is not None else None,
        path_role=param.path_role,
    )


def effects(command: Command) -> EffectsEntry:
    """Return what a declared command changes (AGI-2.2 ``effects``).

    The command is read only when it writes neither the store, a project, nor the
    cache; ``writes`` is ``delete`` for a command that removes data and ``add`` for
    every other that writes (a store never overwrites a version; a plain write
    replaces a file only with ``update`` force, as IMGWTools declares its downloads).
    """
    read_only = not _WRITING & set(command.effects)
    writes = "delete" if command.destructive else "add"
    return EffectsEntry(
        read_only=read_only,
        writes="none" if read_only else writes,
        idempotent=command.idempotent,
        network="network" in command.effects,
        destructive=command.destructive and not read_only,
    )


def _check_references(command: Command) -> None:
    """Constraints and examples name only the parameters of their command."""
    names = {param.name for param in command.params}
    for constraint in command.constraints:
        refs = [constraint.param, *constraint.params, *(constraint.when or {})]
        for ref in refs:
            if ref is not None and ref not in names:
                raise ValueError(
                    f"{command.id}: constraint {constraint.type} names {ref!r}, "
                    "which is not a parameter"
                )
    for example in command.examples:
        for key in (*example.options, *example.run):
            if key not in names:
                raise ValueError(
                    f"{command.id}: an example names {key!r}, which is not a parameter"
                )


def command_entry(command: Command, summaries: dict[str, str]) -> CommandEntry:
    """Return the entry of one declared command (``kartograf-commands/1``).

    Raises
    ------
    ValueError
        A constraint or an example names a parameter the command does not have, or the
        command declares a ``one_of`` group or one of its options twice.
    KeyError
        An allowed value without a meaning (``kartograf.catalog.meanings``).
    """
    _check_references(command)
    examples = tuple(
        ExampleEntry(
            call=example_command_line(command, example),
            result=example.result or EXCERPTS[command.result_schema],
            title=example.title or "",
        )
        for example in command.examples
    )
    return CommandEntry(
        name=command.id,
        operation_id=command.operation_id,
        function=command.function,
        summary=command.summary,
        description=resolve(command.description),
        options=tuple(
            _option(command, param, summaries) for param in declared_options(command)
        ),
        result=ResultEntry(command.result_schema, command.cardinality),
        effects=effects(command),
        check=command.id if command.supports_check else None,
        families=command.families,
        rules=command.rules,
        examples=examples,
        errors=command.errors,
        i18n=I18nEntry(
            PolishTexts(
                summary=localize(command.summary, "pl"),
                description=localize(resolve(command.description), "pl"),
                rules=tuple(localize(rule, "pl") for rule in command.rules),
            )
        ),
    )


def build_entries(
    commands: Sequence[Command], groups: Sequence[Group]
) -> tuple[CommandEntry, ...]:
    """Return the entry of every command of the declarations, in their order.

    Raises
    ------
    ValueError
        The declarations are inconsistent (a group without commands, a constraint or
        an example naming a parameter the command does not have).
    """
    check_declarations(commands, groups)
    summaries = _summaries(commands)
    return tuple(command_entry(command, summaries) for command in commands)


def _command_list(
    entries: Sequence[CommandEntry], groups: Sequence[Group], version: str
) -> CommandList:
    rows = tuple(
        CommandRow(
            name=entry.name,
            operation_id=entry.operation_id,
            summary=entry.summary,
            families=entry.families,
            read_only=entry.effects.read_only,
            check=entry.check,
        )
        for entry in entries
    )
    group_rows = tuple(
        GroupRow(
            group.name,
            group.summary,
            tuple(name for name, _ in resolve(group.products)),
        )
        for group in sorted_groups(groups)
    )
    return CommandList(TOOL, version, group_rows, rows)


def build_list(
    commands: Sequence[Command], groups: Sequence[Group], version: str
) -> CommandList:
    """Return the ``kartograf-command-list/1`` document of the declarations."""
    return _command_list(build_entries(commands, groups), groups, version)


def _version() -> str:
    from kartograf import __version__  # the package imports the catalog

    return __version__


@functools.cache
def _entries() -> tuple[CommandEntry, ...]:
    declarations = declared()
    return build_entries(declarations.commands, declarations.groups)


@functools.cache
def _list() -> CommandList:
    return _command_list(_entries(), declared().groups, _version())


def clear_caches() -> None:
    """Forget the documents built so far (for tests that swap the declarations)."""
    _entries.cache_clear()
    _list.cache_clear()


def command_entries() -> tuple[CommandEntry, ...]:
    """Return the entry of every declared command, in the order of the catalog."""
    return _entries()


def list_commands() -> CommandList:
    """Return the summary of the catalog: ``kartograf commands list --json``.

    Every group (its summary and the products of its commands) and every command (name,
    ``operation_id``, summary, MCP families, whether it only reads and its plan command)
    in a short document: the first thing an agent reads (AGI-1.5). The options of a
    command are one call away (``command_schema``).

    Returns
    -------
    CommandList
        The document ``kartograf-command-list/1``; no network is used. The same object
        every time.
    """
    return _list()


def command_schema(command: str) -> CommandCatalog:
    """Return the description of one command: ``kartograf commands schema --json``.

    Parameters
    ----------
    command : str
        The name of a command (``elevation download``) or its ``operation_id``
        (``kartograf_elevation_download``).

    Returns
    -------
    CommandCatalog
        The document ``kartograf-commands/1`` with that one command: its options (type,
        bounds, allowed values with their meanings, path role), result, effects, rules,
        examples with excerpts of their results, errors and Polish texts.

    Raises
    ------
    ValidationError
        The command is not given or is unknown (``option="command"``, ``allowed`` the
        names of the commands).
    """
    entries = _entries()
    found = None
    if isinstance(command, str):
        found = next((e for e in entries if command in (e.name, e.operation_id)), None)
    if found is None:
        names = tuple(entry.name for entry in entries)
        raise ValidationError(
            message("catalog.no_command")
            if command is None
            else message("catalog.unknown_command", command=command),
            option="command",
            allowed=names,
            hint=message("catalog.commands_list_hint"),
        )
    return CommandCatalog(TOOL, _version(), (found,))
