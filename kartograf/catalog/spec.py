"""
Declaration types of the command catalog (spec 8.2, 8.3).

A module of ``kartograf/catalog/commands/`` declares its commands as
``Command`` objects, each with its ``Param`` list, ``Constraint`` rules and
``Example`` lines. The declarations are the single source of truth of the
CLI parser, the catalog document and the tools of the MCP server; they are
plain frozen data, built without side effects.

Two fields may be *providers* - functions without arguments returning the
value (``Text``, ``Values``): the allowed values and texts that come from
the source registry. A provider is called by ``resolve`` when the catalog or
the parser is built, never when a declaration is created or its module is
imported.
"""

import enum
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, cast, get_args

from kartograf.serialization import SCHEMA_PATTERN

# Value kinds of a parameter: the kinds of the project manifest options plus
# ``plan`` (an update plan: a file on the CLI, a document in the API) and
# ``options`` (the options object of a project task).
Kind = Literal[
    "str",
    "int",
    "flag",
    "bbox",
    "bbox_crs",
    "path",
    "per_country",
    "str_list",
    "plan",
    "options",
]
Normalize = Literal["lower", "upper", "strip"]
Nargs = Literal["?", "*", "REMAINDER"]
CommandKind = Literal["data", "query", "manage"]
Effect = Literal[
    "network", "store_write", "project_write", "cache_write", "cache_delete"
]
ConstraintType = Literal[
    "one_of", "any_of", "requires", "excludes", "applies_to", "required_when"
]

KINDS: Final[tuple[str, ...]] = get_args(Kind)
NORMALIZERS: Final[tuple[str, ...]] = get_args(Normalize)
NARGS: Final[tuple[str, ...]] = get_args(Nargs)
COMMAND_KINDS: Final[tuple[str, ...]] = get_args(CommandKind)
EFFECTS: Final[tuple[str, ...]] = get_args(Effect)
CONSTRAINT_TYPES: Final[tuple[str, ...]] = get_args(ConstraintType)
# Sheet systems a ``sheet`` parameter may accept (``SheetInfo.system``): the ids
# of ``core.parser_registry.SYSTEMS`` and the ZTM map sheets of CUZK.
SHEET_SYSTEMS: Final[tuple[str, ...]] = (
    "pl1992",
    "pl2000",
    "cz_sm5",
    "cz_tm33",
    "cz_ztm",
)
# ``Document`` schema names (``kartograf-<kind>/<version>``).
_SCHEMA_NAME = re.compile(SCHEMA_PATTERN)

_PARAM_NAME = re.compile(r"[a-z][a-z0-9_]*")
_FLAG = re.compile(r"--[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_SHORT = re.compile(r"-[A-Za-z]")
_COMMAND_ID = re.compile(r"[a-z][a-z0-9_]*(?: [a-z][a-z0-9-]*)?")
_GROUP_NAME = re.compile(r"[a-z][a-z0-9]*")
_TOOL_NAME = re.compile(r"[a-z][a-z0-9_]*")


class _Auto(enum.Enum):
    """Type of the ``AUTO`` sentinel."""

    AUTO = enum.auto()

    def __repr__(self) -> str:
        return "AUTO"


# ``flag``/``argument`` of a ``Param``: derive from the name (``None`` = absent).
AUTO: Final = _Auto.AUTO

Text = str | Callable[[], str]
Values = Sequence[str] | Callable[[], Sequence[str]]
# ``(product, summary)`` pairs of a group, or the function giving them.
Products = Sequence[tuple[str, str]] | Callable[[], Sequence[tuple[str, str]]]


def resolve[T](value: T | Callable[[], T]) -> T:
    """The value of a declaration field.

    A provider (a function without arguments) is called here - the only place
    where registry-backed values are computed; any other value is returned as it
    is.
    """
    if callable(value):
        return cast(T, value())
    return value


@dataclass(frozen=True)
class Param:
    """One parameter of a command: a CLI flag or argument, an API argument, or both.

    The fields up to ``description`` are the catalog fields of ``ParamInfo``;
    the last six are used by the CLI parser only (spec 8.3) and are not part of
    the catalog document.

    Parameters
    ----------
    name : str
        Unique in the command; the key of a project task option and, when the
        parameter has an API argument, that argument's name.
    kind : Kind
        Value kind.
    description : str or callable
        Help text of the flag and description in the catalog (Polish, ASCII).
    flag : str, None or AUTO
        CLI flag; AUTO derives ``--<name with dashes>`` (none for a positional
        parameter), ``None`` = API only.
    argument : str, None or AUTO
        Name of the argument of the library function; AUTO = ``name``,
        ``None`` = CLI only.
    short : str, optional
        Short flag (``-o``).
    positional : bool
        A positional CLI argument.
    required : bool
        The library rejects the call without it (needs an API argument).
    task : bool
        A key of ``tasks[].options`` of a project task.
    allowed : sequence of str or callable, optional
        Allowed values (a provider reads them from the registry).
    default : object
        The value the library function uses when the argument is omitted.
    cli_default : object
        Default of the CLI flag when it differs from the library's.
    accepts : tuple of str, optional
        ``sheet`` only: the sheet systems the command accepts.
    section : str, optional
        Title of the ``--help`` section.
    dest : str, optional
        ``Namespace`` attribute of the flag (default: ``name``).
    metavar : str, optional
        Placeholder of the value in ``--help`` (Polish).
    normalize : {"lower", "upper", "strip"}, optional
        Applied by the parser to the text of the value.
    exclusive : str, optional
        Id of the mutually exclusive group of flags the flag belongs to.
    choices : bool
        ``allowed`` are also the ``choices`` of the parser.
    nargs : {"*", "REMAINDER"}, optional
        Number of values of a positional argument.
    """

    name: str
    kind: Kind
    description: Text = ""
    flag: str | _Auto | None = AUTO
    argument: str | _Auto | None = AUTO
    short: str | None = None
    positional: bool = False
    required: bool = False
    task: bool = False
    allowed: Values | None = None
    default: object = None
    cli_default: object = None
    accepts: tuple[str, ...] | None = None
    section: str | None = None
    dest: str | None = None
    metavar: str | None = None
    normalize: Normalize | None = None
    exclusive: str | None = None
    choices: bool = False
    nargs: Nargs | None = None

    def __post_init__(self) -> None:
        name = self.name
        if not _PARAM_NAME.fullmatch(name):
            raise ValueError(f"Param {name!r}: the name must be snake_case")
        if self.kind not in KINDS:
            raise ValueError(f"Param {name}: unknown kind {self.kind!r}")
        if isinstance(self.flag, str) and not _FLAG.fullmatch(self.flag):
            raise ValueError(f"Param {name}: flag {self.flag!r} is not a long flag")
        if self.short is not None and not _SHORT.fullmatch(self.short):
            raise ValueError(f"Param {name}: short {self.short!r} is not a short flag")
        if self.positional and isinstance(self.flag, str):
            raise ValueError(f"Param {name}: a positional parameter has no flag")
        flagged = self.cli_flag is not None
        if self.short is not None and not flagged:
            raise ValueError(f"Param {name}: short without a flag")
        if self.dest is not None and not flagged:
            raise ValueError(f"Param {name}: dest without a flag")
        if self.exclusive is not None and not flagged:
            raise ValueError(f"Param {name}: exclusive without a flag")
        if self.nargs is not None and (not self.positional or self.nargs not in NARGS):
            raise ValueError(f"Param {name}: nargs only for a positional parameter")
        if self.normalize is not None and self.normalize not in NORMALIZERS:
            raise ValueError(f"Param {name}: unknown normalize {self.normalize!r}")
        if isinstance(self.allowed, str):
            raise ValueError(f"Param {name}: allowed must be a sequence, not a text")
        if self.choices and self.allowed is None:
            raise ValueError(f"Param {name}: choices need allowed")
        if self.required and self.api_argument is None:
            raise ValueError(
                f"Param {name}: required needs an API argument (spec 8.3 item 5)"
            )
        if self.task and self.api_argument is None:
            raise ValueError(f"Param {name}: a task option needs an API argument")
        if self.accepts is not None:
            unknown = [s for s in self.accepts if s not in SHEET_SYSTEMS]
            if name != "sheet" or unknown:
                raise ValueError(
                    f"Param {name}: accepts is for sheet systems {SHEET_SYSTEMS} "
                    f"of a sheet parameter, got {self.accepts!r}"
                )

    @property
    def cli_flag(self) -> str | None:
        """The CLI flag (``--vertical-crs``); ``None`` for an API-only or a
        positional parameter."""
        if self.positional:
            return None
        if isinstance(self.flag, _Auto):
            return "--" + self.name.replace("_", "-")
        return self.flag

    @property
    def api_argument(self) -> str | None:
        """The argument of the library function; ``None`` for a CLI-only parameter."""
        return self.name if isinstance(self.argument, _Auto) else self.argument

    @property
    def cli_dest(self) -> str:
        """The ``Namespace`` attribute the parser stores the value in."""
        return self.dest or self.name


@dataclass(frozen=True)
class Constraint:
    """A rule among the parameters of a command (documentation, spec 8.4).

    ``one_of``: exactly one of ``params``; ``any_of``: at least one;
    ``requires``: when ``param`` is given, all ``params`` are; ``excludes``:
    when ``param`` is given, none of ``params``; ``applies_to``: ``param`` only
    when ``when`` holds; ``required_when``: ``param`` is required when ``when``
    holds. ``when`` maps a parameter to ``True`` (given) or to the list of values
    it has; several keys all hold.
    """

    type: ConstraintType
    params: tuple[str, ...]
    message: str
    param: str | None = None
    when: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if self.type not in CONSTRAINT_TYPES:
            raise ValueError(f"Constraint: unknown type {self.type!r}")


@dataclass(frozen=True)
class Example:
    """An example call: ``options`` are the project task options in the JSON form
    of the manifest (``bbox`` as 4 numbers with ``bbox_crs``, a per-country value
    as a text or ``{"pl": ..., "cz": ...}``), ``run`` the other flags shown in
    the command line (the store directory is added by the catalog)."""

    options: Mapping[str, object]
    title: str | None = None
    run: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Command:
    """One command of the catalog: a CLI command, an API function, a tool.

    Parameters
    ----------
    id : str
        ``<group> <name>`` of a CLI command (the key of ``COMMANDS`` of the
        project), ``parse``/``catalog``, or the function name of an API-only
        command.
    summary : str
        One line, at most 120 characters (the command's ``help``).
    kind : {"data", "query", "manage"}
        Writes to the store, only reads, or changes a project or the cache.
    function, result_schema : str
        The library function and the schema of its result.
    params : tuple of Param
        In the order of the flags in ``--help``.
    description : str or callable
        Full description (the command's ``description``).
    effects : tuple of str
        Subset of ``network``, ``store_write``, ``project_write``,
        ``cache_write``, ``cache_delete``.
    idempotent, destructive : bool
        Repeating the call does not change the effect; the call removes data.
    project_task : bool
        A data command a project task may run (a key of ``COMMANDS``).
    check_function, check_result_schema : str, optional
        The ``check_*`` twin and its result schema (both or neither).
    cli : AUTO or None
        AUTO: the CLI words are the id; ``None``: an API-only command.
    tool : str, optional
        MCP tool name.
    constraints, examples : tuple
        Rules among the parameters and example calls.
    """

    id: str
    summary: str
    kind: CommandKind
    function: str
    result_schema: str
    params: tuple[Param, ...]
    description: Text = ""
    effects: tuple[Effect, ...] = ()
    idempotent: bool = True
    destructive: bool = False
    project_task: bool = False
    check_function: str | None = None
    check_result_schema: str | None = None
    cli: _Auto | None = AUTO
    tool: str | None = None
    constraints: tuple[Constraint, ...] = ()
    examples: tuple[Example, ...] = ()

    def __post_init__(self) -> None:
        name = self.id
        if not _COMMAND_ID.fullmatch(name):
            raise ValueError(f"Command {name!r}: id is '<group> <name>' or one word")
        if self.kind not in COMMAND_KINDS:
            raise ValueError(f"Command {name}: unknown kind {self.kind!r}")
        unknown = [effect for effect in self.effects if effect not in EFFECTS]
        if unknown:
            raise ValueError(f"Command {name}: unknown effects {unknown}")
        for schema in (self.result_schema, self.check_result_schema):
            if schema is not None and not _SCHEMA_NAME.fullmatch(schema):
                raise ValueError(f"Command {name}: schema {schema!r} is malformed")
        if (self.check_function is None) != (self.check_result_schema is None):
            raise ValueError(
                f"Command {name}: check_function and check_result_schema go together"
            )
        if self.project_task and self.kind != "data":
            raise ValueError(f"Command {name}: a project task is a data command")
        if self.tool is not None and not _TOOL_NAME.fullmatch(self.tool):
            raise ValueError(f"Command {name}: tool {self.tool!r} is not snake_case")
        names = [param.name for param in self.params]
        for duplicate in sorted({n for n in names if names.count(n) > 1}):
            raise ValueError(f"Command {name}: parameter {duplicate!r} declared twice")
        if self.cli is None:
            for param in self.params:
                if param.cli_flag is not None or param.positional:
                    raise ValueError(
                        f"Command {name}: an API-only command declares no CLI flag "
                        f"({param.name})"
                    )

    @property
    def group(self) -> str | None:
        """The CLI group (``elevation``); ``None`` for ``parse``, ``catalog`` and
        the API-only commands."""
        first, space, _ = self.id.partition(" ")
        return first if space else None

    @property
    def name(self) -> str:
        """The last word of the id."""
        return self.id.rpartition(" ")[2]

    @property
    def cli_words(self) -> str | None:
        """The words after ``kartograf``; ``None`` for an API-only command."""
        return None if self.cli is None else self.id

    @property
    def supports_check(self) -> bool:
        """The command has a check of the update state (``check_function``)."""
        return self.check_function is not None

    @property
    def check_tool(self) -> str | None:
        """The MCP tool that runs the check twin of the command: ``check_updates``
        for a data command (a project task), ``<group>_check_updates`` for the
        others (``project_check_updates``); ``None`` without a check or a tool."""
        if self.check_function is None or self.tool is None:
            return None
        if self.project_task:
            return "check_updates"
        return f"{self.group}_check_updates" if self.group else "check_updates"

    @property
    def task_options(self) -> dict[str, Kind]:
        """The keys of ``tasks[].options`` of a project task with their kinds, in
        the order of the parameters (the order of the keys of a manifest)."""
        return {param.name: param.kind for param in self.params if param.task}


@dataclass(frozen=True)
class Group:
    """A CLI group: ``kartograf <name> <command>`` (spec 8.1).

    ``products``: the ``(product, summary)`` pairs of the group (a provider reads
    them from the registry); ``position``: the place in the list of commands of
    ``kartograf --help`` and in the catalog - lower first, equal ones by name.
    """

    name: str
    summary: str
    description: str
    products: Products = ()
    position: int = 1

    def __post_init__(self) -> None:
        if not _GROUP_NAME.fullmatch(self.name):
            raise ValueError(f"Group {self.name!r}: the name is lowercase letters")


def sorted_groups(groups: Iterable[Group]) -> tuple[Group, ...]:
    """The groups in the order of ``kartograf --help`` and of the catalog: by
    ``position``, then by name."""
    return tuple(sorted(groups, key=lambda group: (group.position, group.name)))


def check_declarations(commands: Sequence[Command], groups: Sequence[Group]) -> None:
    """Check the declarations as a whole.

    Raises
    ------
    ValueError
        A command id or a group name declared twice, a command of a CLI group
        that nobody declares, or a group without commands.
    """
    ids = [command.id for command in commands]
    for duplicate in sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"command {duplicate!r} is declared twice")
    names = [group.name for group in groups]
    for duplicate in sorted({n for n in names if names.count(n) > 1}):
        raise ValueError(f"group {duplicate!r} is declared twice")
    owned = {
        command.group
        for command in commands
        if command.cli is not None and command.group is not None
    }
    for missing in sorted(owned - set(names)):
        raise ValueError(f"group {missing!r} has commands but no declaration")
    for group in groups:
        if group.name not in owned:
            raise ValueError(f"group {group.name!r} has no commands")
