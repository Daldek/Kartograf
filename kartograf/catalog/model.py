"""
The document ``kartograf-catalog/1``: the model of the catalog (spec 8.1).

``Catalog`` is the document (a ``Document`` with ``to_dict()``/``to_json()``);
the other types are its nested objects. Every text is Polish ASCII, every name a
snake_case or CLI word, every collection a tuple: a catalog is built once per
process and is read-only data.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from kartograf.serialization import Document


@dataclass(frozen=True)
class ParamInfo:
    """One parameter of a command (the catalog form of ``spec.Param``).

    Attributes
    ----------
    name : str
        Unique in the command; the key of a project task option and, when
        ``argument`` is set, the argument name.
    argument : str, optional
        Argument of the library function; ``None`` = CLI only.
    flag : str, optional
        CLI flag; ``None`` = API only (or a positional argument).
    short : str, optional
        Short flag.
    positional : bool
        A positional CLI argument.
    kind : str
        ``str``, ``int``, ``flag``, ``bbox``, ``bbox_crs``, ``path``,
        ``per_country``, ``str_list``, ``plan`` or ``options``.
    required : bool
        The library rejects the call without it.
    task : bool
        A key of ``tasks[].options`` of a project task.
    allowed : tuple of str, optional
        Allowed values from the registry; ``None`` = any value.
    default : object
        The value the library function uses when the argument is omitted.
    cli_default : object
        Default of the CLI flag when it differs from the library's.
    accepts : tuple of str, optional
        ``sheet`` only: the sheet systems the command accepts.
    section : str, optional
        Title of the ``--help`` section.
    description : str
        The text of the flag in ``--help``.
    """

    name: str
    argument: str | None
    flag: str | None
    short: str | None
    positional: bool
    kind: str
    required: bool
    task: bool
    allowed: tuple[str, ...] | None
    default: object
    cli_default: object
    accepts: tuple[str, ...] | None
    section: str | None
    description: str


@dataclass(frozen=True)
class ConstraintInfo:
    """A rule among the parameters (``one_of``, ``any_of``, ``requires``,
    ``excludes``, ``applies_to``, ``required_when``); ``when`` maps a parameter
    to ``True`` (given) or to the list of values it has."""

    type: str
    param: str | None
    params: tuple[str, ...]
    when: Mapping[str, object] | None
    message: str


@dataclass(frozen=True)
class ExampleInfo:
    """An example call: the task options in the JSON form of the manifest and the
    command line computed from them."""

    title: str | None
    options: Mapping[str, object]
    command_line: str


@dataclass(frozen=True)
class CommandInfo:
    """One command: a CLI command, an API function and, when ``tool`` is set, an
    MCP tool.

    ``params``, ``constraints`` and ``examples`` are ``None`` in the short view
    of the catalog (``get_catalog()``) and set in the view of one command or of
    ``params=True``.
    """

    id: str
    group: str | None
    name: str
    summary: str
    description: str
    kind: str
    effects: tuple[str, ...]
    idempotent: bool
    destructive: bool
    project_task: bool
    function: str
    check_function: str | None
    result_schema: str
    check_result_schema: str | None
    supports_check: bool
    cli: str | None
    tool: str | None
    params: tuple[ParamInfo, ...] | None
    constraints: tuple[ConstraintInfo, ...] | None
    examples: tuple[ExampleInfo, ...] | None


@dataclass(frozen=True)
class ProductInfo:
    """A product of a group: the value of ``--product``, its description, the
    countries (``pl``, ``cz``, ``eu``, ``global``) and the descriptor keys of its
    sources (``list_sources`` gives the details)."""

    name: str
    summary: str
    countries: tuple[str, ...]
    sources: tuple[str, ...]


@dataclass(frozen=True)
class GroupInfo:
    """A CLI group: ``kartograf <name> <command>``."""

    name: str
    summary: str
    description: str
    products: tuple[ProductInfo, ...]
    commands: tuple[str, ...]


@dataclass(frozen=True)
class ExitCodeInfo:
    """A row of the exit code table of the CLI."""

    code: int
    name: str
    meaning: str


@dataclass(frozen=True)
class ErrorCodeInfo:
    """A row of the error code table: the exception and its code."""

    code: str
    exception: str
    exit_code: int
    meaning: str


@dataclass(frozen=True)
class SchemaInfo:
    """A document schema, the ids of the commands that produce it."""

    schema: str
    description: str
    produced_by: tuple[str, ...]


@dataclass(frozen=True)
class Catalog(Document):
    """The catalog of the commands (``kartograf-catalog/1``): the groups with their
    products, the commands with their parameters, constraints and examples, the
    exit code and error code tables and the document schemas."""

    SCHEMA: ClassVar[str] = "kartograf-catalog/1"

    kartograf_version: str
    language: str
    groups: tuple[GroupInfo, ...]
    commands: tuple[CommandInfo, ...]
    exit_codes: tuple[ExitCodeInfo, ...]
    errors: tuple[ErrorCodeInfo, ...]
    schemas: tuple[SchemaInfo, ...]
