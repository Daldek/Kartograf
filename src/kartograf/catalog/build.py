"""
The catalog documents built from the declarations (spec 8.5).

``list_commands`` and ``command_schema`` resolve the providers of the declarations of
``kartograf/catalog/commands/`` and build ``CommandList`` (``kartograf-command-list/1``)
and ``CommandCatalog`` (``kartograf-commands/1``). The entry of every command is built
once per process and is read-only; ``command_schema`` picks one of them, from the
entries of the page of a form when it is asked for one.

An *option* of a command is a parameter that has an argument of the library function
(and so a key of an MCP tool call) and the plan option ``check`` of a command
that has a check; a flag only the CLI has (``--json``, ``--quiet``, ``--upgrade``,
``--force``) and the constant argument of ``<group> list-sources`` are not options
(``is_option``). The rules among the parameters (``Constraint``) become the fields of
the options a form reads (``requires``, ``excludes``, ``applies_to``,
``required_when``) and the choice of the command (``one_of``); the route of the
command on ``kartograf server`` (``rest``) is derived from its group, kind, effects
and options, never declared (ADR-063 decisions 1 and 2).
"""

import functools
from collections.abc import Mapping, Sequence
from typing import Final, Literal

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
    OptionI18nEntry,
    OptionPolishTexts,
    PolishTexts,
    RestEntry,
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
from kartograf.download.arguments import require_bool
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
}
_ITEMS = {"bbox": "number", "str_list": "string"}
_UNITS = {"bbox": "m, or degrees for EPSG:4326"}
# What changes the world outside the process (``Command.effects``).
_WRITING = frozenset({"store_write", "cache_write", "cache_delete"})
# The groups whose commands ``kartograf server`` never serves (ADR-063 decision 2): the
# user's own store, cache and settings, and the GUI, which starts a server itself.
_LOCAL_GROUPS: Final = frozenset({"store", "cache", "config", "gui"})
# The base of the routes of ``kartograf server`` (AGI-6.1).
_API_BASE: Final = "/api/v1"
# What a condition of a rule asks of an option (AGI-2.3): ``True``, that it is given,
# or the values it may have.
_Expected = Literal[True] | tuple[object, ...]


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


# The options whose declared values are only the usual ones: the function takes more
# (``command_schema`` also takes the ``operation_id`` of a command). The schema of an
# MCP tool does not list them (the names of the commands are in
# ``kartograf_commands_list``, and a second copy in every ``tools/list`` is waste) and
# ``validate_command`` does not check them.
OPEN_VALUES: Final = frozenset({("commands schema", "command")})


def allowed_values(command: Command, option: OptionEntry) -> list[str | int] | None:
    """Return the values an option is limited to, or ``None`` when it takes any.

    The ``enum`` of the option in the catalog document, except for the options of
    ``OPEN_VALUES``.
    """
    if not option.enum or (command.id, option.name) in OPEN_VALUES:
        return None
    return [entry.value for entry in option.enum]


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


def _with_one_of(description: str, constraint: Constraint) -> str:
    """Return the description of an option of a ``one_of`` group with the group's rule.

    A catalog message, so the page of a form renders it in Polish too.
    """
    names = ", ".join(f"`{name}`" for name in constraint.params)
    if constraint.optional:
        return message(
            "catalog.option_at_most_one_of", description=description, names=names
        )
    return message(
        "catalog.option_exactly_one_of", description=description, names=names
    )


def _named(
    command: Command, rule: str, option: str, options: frozenset[str]
) -> tuple[str, ...]:
    """Return the options the rules of a kind on an option name (AGI-2.3).

    ``requires`` or ``excludes``: the ``params`` of every such rule whose ``param`` is
    the option, merged in the order of the declaration. A name that is no option of the
    command (``upgrade``, a flag only the CLI has) is left out.
    """
    names = (
        name
        for constraint in command.constraints
        if constraint.type == rule and constraint.param == option
        for name in constraint.params
        if name in options
    )
    return tuple(dict.fromkeys(names))


def _expected(command: Command, when: Mapping[str, object]) -> dict[str, _Expected]:
    """Return the ``when`` of a rule in the JSON form: ``True`` or the values.

    Raises
    ------
    ValueError
        A value that is neither ``True`` nor a list of values.
    """
    condition: dict[str, _Expected] = {}
    for name, value in when.items():
        if value is True:
            condition[name] = True
        elif isinstance(value, list | tuple):
            condition[name] = tuple(value)
        else:
            raise ValueError(
                f"{command.id}: the condition on {name!r} is neither True nor a list"
            )
    return condition


def _all_of(
    first: dict[str, _Expected], second: dict[str, _Expected]
) -> dict[str, _Expected] | None:
    """Return the condition that holds where both hold; ``None``: they never do."""
    merged = dict(first)
    for name, value in second.items():
        current = merged.get(name, True)
        if current is True:
            merged[name] = value
        elif value is not True:
            common = tuple(item for item in current if item in value)
            if not common:
                return None
            merged[name] = common
    return merged


def _any_of(
    first: dict[str, _Expected], second: dict[str, _Expected]
) -> dict[str, _Expected] | None:
    """Return the condition that holds where either holds.

    ``None`` when no single condition says it: only the values of one same option join
    (``{product: [laz]}`` and ``{product: [nmt]}``).
    """
    if first == second:
        return first
    if len(first) != 1 or first.keys() != second.keys():
        return None
    ((name, one),) = first.items()
    other = second[name]
    if one is True or other is True:
        return {name: True}
    return {name: tuple(dict.fromkeys((*one, *other)))}


def _condition(
    command: Command, rule: str, option: str, options: frozenset[str]
) -> dict[str, _Expected] | None:
    """Return the condition of the rules of a kind on an option (AGI-2.3).

    ``applies_to`` or ``required_when``: the ``when`` of every such rule whose
    ``param`` is the option, ``{option: True | (values...)}``. Several merge: the option
    applies where all of their conditions hold, and is required where one of them
    does. A rule whose condition names a parameter that is no option of the command
    stays in the prose of the rules only.

    Raises
    ------
    ValueError
        Rules that no single condition says: ``applies_to`` conditions that never hold
        together, ``required_when`` conditions on more than the values of one option.
    """
    merged: dict[str, _Expected] | None = None
    for constraint in command.constraints:
        when = constraint.when
        if constraint.type != rule or constraint.param != option or not when:
            continue
        if not set(when) <= options:
            continue
        condition = _expected(command, when)
        if merged is None:
            merged = condition
            continue
        merged = (_all_of if rule == "applies_to" else _any_of)(merged, condition)
        if merged is None:
            raise ValueError(
                f"{command.id}: the {rule} rules of {option!r} are no single condition"
            )
    return merged


def _alternatives(
    command: Command, options: frozenset[str]
) -> tuple[tuple[str, ...], ...]:
    """Return the choice a command requires (AGI-2.3, the ``one_of`` of a command).

    The first ``one_of`` constraint that is not optional, an alternative of one option
    per member: the area, ``(("sheet",), ("bbox",), ("geometry",))``. commands-1 holds
    one choice per command, so another such group (``depth`` or ``depth_rule`` of
    ``soil hsg``) is the ``one_of`` group of its options only, as an optional group
    (``target``) always is. Empty when the command has none.
    """
    for constraint in one_of_constraints(command):
        names = [name for name in constraint.params if name in options]
        if not constraint.optional and len(names) > 1:
            return tuple((name,) for name in names)
    return ()


def _summaries(commands: Sequence[Command]) -> dict[str, str]:
    """Return the summary of every command by its id."""
    return {command.id: command.summary for command in commands}


def _enum(param: Param, summaries: dict[str, str]) -> tuple[EnumValue, ...] | None:
    """Return the allowed values of a parameter with their meanings.

    A meaning is a catalog message (``kartograf.catalog.meanings``, the summary of a
    command), so the page of a form renders it in Polish too.
    """
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


def _polish(
    param: Param, description: str, enum: tuple[EnumValue, ...] | None
) -> OptionI18nEntry:
    """Return the Polish texts of an option: those of ``--help --lang pl``."""
    return OptionI18nEntry(
        OptionPolishTexts(
            description=localize(description, "pl"),
            section=None if param.section is None else localize(param.section, "pl"),
            enum=(
                None
                if enum is None
                else {str(item.value): localize(item.meaning, "pl") for item in enum}
            ),
        )
    )


def _option(
    command: Command,
    param: Param,
    summaries: dict[str, str],
    options: frozenset[str],
    *,
    form: bool,
) -> OptionEntry:
    """Return the entry of an option; ``options`` are the names of all of them.

    With ``form`` it also has its section and its Polish texts (``commands schema
    --form``).
    """
    description = resolve(param.description)
    group = next(
        (c for c in one_of_constraints(command) if param.name in c.params), None
    )
    if group is not None:
        description = _with_one_of(description, group)
    enum = _enum(param, summaries)
    section = None
    if form and param.section is not None:
        section = localize(param.section, "en")
    return OptionEntry(
        name=param.name,
        type=_TYPES[param.kind],
        required=param.required,
        description=description,
        items=_ITEMS.get(param.kind),
        unit=param.unit or _UNITS.get(param.kind),
        default=param.default,
        enum=enum,
        minimum=param.minimum,
        maximum=param.maximum,
        examples=param.examples or None,
        one_of=group.group if group is not None else None,
        path_role=param.path_role,
        section=section,
        requires=_named(command, "requires", param.name, options),
        excludes=_named(command, "excludes", param.name, options),
        applies_to=_condition(command, "applies_to", param.name, options),
        required_when=_condition(command, "required_when", param.name, options),
        i18n=_polish(param, description, enum) if form else None,
    )


def effects(command: Command) -> EffectsEntry:
    """Return what a declared command changes (AGI-2.2 ``effects``).

    The command is read only when it writes neither the store nor the
    cache; ``writes`` is ``delete`` for a command that removes data and ``add`` for
    every other that writes (a store never overwrites a version; a plain write
    replaces a file only with ``update`` force, as Obserwator declares its downloads).
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


def rest(command: Command) -> RestEntry | None:
    """Return the route of a declared command on ``kartograf server`` (ADR-063).

    Derived, never declared (decision 2): ``None`` for the commands of the groups the
    server never serves (the user's store, cache and settings, and the GUI); ``POST``
    with ``key`` for a data command, whose plan the server answers (``?check=true``)
    and whose run it refuses; for another read-only command ``POST`` when one of its
    options is an object, which a URL cannot carry, else ``GET``, without ``key``;
    ``None`` for a command that writes. The path is ``/api/v1/<group>/<verb>``.
    """
    if command.group in _LOCAL_GROUPS:
        return None
    path = f"{_API_BASE}/{command.group}/{command.name}"
    if command.kind == "data":
        return RestEntry("POST", path, key=True)
    if not effects(command).read_only:
        return None
    takes_object = any(
        _TYPES[param.kind] == "object" for param in declared_options(command)
    )
    return RestEntry("POST" if takes_object else "GET", path, key=False)


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


def command_entry(
    command: Command, summaries: dict[str, str], *, form: bool = False
) -> CommandEntry:
    """Return the entry of one declared command (``kartograf-commands/1``).

    With ``form`` each option also has its section and its Polish texts (the page of a
    form, ``commands schema --form``).

    Raises
    ------
    ValueError
        A constraint or an example names a parameter the command does not have, the
        command declares a ``one_of`` group or one of its options twice, or rules of
        one kind on one option that no single condition says.
    KeyError
        An allowed value without a meaning (``kartograf.catalog.meanings``).
    """
    _check_references(command)
    params = declared_options(command)
    options = frozenset(param.name for param in params)
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
            _option(command, param, summaries, options, form=form) for param in params
        ),
        result=ResultEntry(command.result_schema, command.cardinality),
        effects=effects(command),
        check=command.id if command.supports_check else None,
        rest=rest(command),
        families=command.families,
        one_of=_alternatives(command, options),
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
    commands: Sequence[Command], groups: Sequence[Group], *, form: bool = False
) -> tuple[CommandEntry, ...]:
    """Return the entry of every command of the declarations, in their order.

    ``form``: the entries of the page of a form (``command_entry``).

    Raises
    ------
    ValueError
        The declarations are inconsistent (a group without commands, a constraint or
        an example naming a parameter the command does not have).
    """
    check_declarations(commands, groups)
    summaries = _summaries(commands)
    return tuple(command_entry(command, summaries, form=form) for command in commands)


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
            effects=entry.effects,
            rest=entry.rest,
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


def _version() -> str:
    from kartograf import __version__  # the package imports the catalog

    return __version__


@functools.cache
def _entries(form: bool) -> tuple[CommandEntry, ...]:
    """Return the entries of every command, of the page of a form with ``form``."""
    declarations = declared()
    return build_entries(declarations.commands, declarations.groups, form=form)


@functools.cache
def _list() -> CommandList:
    return _command_list(_entries(False), declared().groups, _version())


def command_entries() -> tuple[CommandEntry, ...]:
    """Return the entry of every declared command, in the order of the catalog."""
    return _entries(False)


def list_commands() -> CommandList:
    """Return the summary of the catalog: ``kartograf commands list --json``.

    Every group (its summary and the products of its commands) and every command (name,
    ``operation_id``, summary, MCP families, whether it only reads, its plan command,
    its effects and its route on ``kartograf server``) in a short document: the first
    thing an agent reads (AGI-1.5). The options of a command are one call away
    (``command_schema``).

    Returns
    -------
    CommandList
        The document ``kartograf-command-list/1``; no network is used. The same object
        every time.
    """
    return _list()


def unknown_command(command: object) -> ValidationError:
    """Return the error of a command that is not given or is not in the catalog.

    ``option`` is ``command`` and ``allowed`` the names of the commands.
    """
    return ValidationError(
        message("catalog.no_command")
        if command is None
        else message("catalog.unknown_command", command=command),
        option="command",
        allowed=tuple(entry.name for entry in _entries(False)),
        hint=message("catalog.commands_list_hint"),
    )


def command_schema(command: str, *, form: bool = False) -> CommandCatalog:
    """Return the description of one command: ``kartograf commands schema --json``.

    Parameters
    ----------
    command : str
        The name of a command (``elevation download``) or its ``operation_id``
        (``kartograf_elevation_download``).
    form : bool
        Also give each option its section and its Polish texts (``section`` and
        ``i18n.pl``: the description, the title of the section and the meaning of each
        allowed value), what a form of the command reads (``--form``); a longer page.

    Returns
    -------
    CommandCatalog
        The document ``kartograf-commands/1`` with that one command: its options (type,
        bounds, allowed values with their meanings, path role, the options each one
        requires or excludes, where it applies and where it is required), its choice
        (``one_of``), result, effects, route on ``kartograf server`` (``rest``), rules,
        examples with excerpts of their results, errors and Polish texts.

    Raises
    ------
    ValidationError
        The command is not given or is unknown (``option="command"``, ``allowed`` the
        names of the commands), or ``form`` is no switch (``option="form"``).
    """
    require_bool(form, "--form")
    entries = _entries(form)
    found = None
    if isinstance(command, str):
        found = next((e for e in entries if command in (e.name, e.operation_id)), None)
    if found is None:
        raise unknown_command(command)
    return CommandCatalog(TOOL, _version(), (found,))
