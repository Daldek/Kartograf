"""
The document ``kartograf-catalog/1``: the model of the catalog (spec 8.1).

``Catalog`` is the document (a ``Document`` with ``to_dict()``/``to_json()``);
the other types are its nested objects. Every text is Polish ASCII, every name a
snake_case or CLI word, every collection a tuple: a catalog is built once per
process and is read-only data.

The catalog has two views (``Catalog.view``). The *overview* (``get_catalog()``)
is what an agent reads first, so its document is a short projection of the same
objects: a group is its name, summary and product names, a command its id,
summary, tool and ``supports_check``; every other field is asked for with
``group=``, ``command=`` or ``params=True`` (the *full* view). The objects of
both views carry every field a caller of the library may read; only the
document leaves them out.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from kartograf.serialization import Document

OVERVIEW = "overview"
FULL = "full"
VIEWS = (OVERVIEW, FULL)


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
    """A rule among the parameters.

    The rules are ``one_of``, ``any_of``, ``requires``, ``excludes``, ``applies_to`` and
    ``required_when``; ``when`` maps a parameter to ``True`` (given) or to the list of
    values it has.
    """

    type: str
    param: str | None
    params: tuple[str, ...]
    when: Mapping[str, object] | None
    message: str


@dataclass(frozen=True)
class ExampleInfo:
    """Return an example call.

    The task options in the JSON form of the manifest and the command line computed from
    them.
    """

    title: str | None
    options: Mapping[str, object]
    command_line: str


@dataclass(frozen=True)
class CommandInfo:
    """One command.

    A CLI command, an API function and, when ``tool`` is set, an MCP tool.

    ``params``, ``constraints`` and ``examples`` are ``None`` unless a command or
    ``params=True`` was asked for (``get_catalog()``, ``group=`` alone).
    ``check_tool`` is the MCP tool that checks the command (``check_updates`` for
    a data command, ``project_check_updates`` for ``project download``; ``None``
    without a check), left out of the document of the overview.
    """

    id: str
    group: str
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
    check_tool: str | None
    cli: str | None
    tool: str | None
    params: tuple[ParamInfo, ...] | None
    constraints: tuple[ConstraintInfo, ...] | None
    examples: tuple[ExampleInfo, ...] | None


@dataclass(frozen=True)
class ProductInfo:
    """A product of a group.

    The value of ``--product``, its description, the countries (``pl``, ``cz``, ``eu``,
    ``global``) and the descriptor keys of its sources (``list_sources`` gives the
    details).
    """

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
    """A row of the error table: the registry code, its reason and the exception."""

    code: str
    reason: str | None
    exception: str
    exit_code: int
    meaning: str


@dataclass(frozen=True)
class SchemaInfo:
    """A document schema, the ids of the commands that produce it."""

    schema: str
    description: str
    produced_by: tuple[str, ...]


def _records_json(document: Mapping[str, object], indent: int) -> str:
    """Return the document as JSON text with one record of every list per line.

    The same document as ``json.dumps(document, indent=indent)``, but a record
    (a group, a command) is one compact line instead of a line per key: the
    overview is a list of short records, and indenting every key of every record
    makes it a third longer.
    """
    pad = " " * indent

    def dump(value: object) -> str:
        return json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )

    entries = []
    for key, value in document.items():
        if isinstance(value, list) and value:
            rows = ",\n".join(f"{pad}{pad}{dump(row)}" for row in value)
            entries.append(f"{pad}{dump(key)}: [\n{rows}\n{pad}]")
        else:
            entries.append(f"{pad}{dump(key)}: {dump(value)}")
    return "{\n" + ",\n".join(entries) + "\n}\n"


@dataclass(frozen=True)
class Catalog(Document):
    """Return the catalog of the commands (``kartograf-catalog/1``).

    The groups with their products, the commands with their parameters, constraints and
    examples, and - when asked for - the exit code and error code tables and the
    document schemas.

    Attributes
    ----------
    view : str
        ``overview`` (``get_catalog()``: nothing selected, no parameters) or
        ``full`` (a group, a command or ``params=True`` was asked for). The
        document of the overview is a projection (see the module docstring); the
        document of the full view has every field of the objects.
    exit_codes, errors, schemas : tuple, optional
        The reference tables; ``None`` (``null``) unless asked for with
        ``tables=True`` (or by the whole catalog with parameters).
    """

    SCHEMA: ClassVar[str] = "kartograf-catalog/1"

    view: str
    kartograf_version: str
    language: str
    groups: tuple[GroupInfo, ...]
    commands: tuple[CommandInfo, ...]
    exit_codes: tuple[ExitCodeInfo, ...] | None
    errors: tuple[ErrorCodeInfo, ...] | None
    schemas: tuple[SchemaInfo, ...] | None

    def __post_init__(self) -> None:
        """Check the view name."""
        if self.view not in VIEWS:
            raise ValueError(f"unknown catalog view {self.view!r} (allowed: {VIEWS})")

    def to_dict(self) -> dict[str, object]:
        """Return the document.

        In the overview ``groups`` and ``commands`` are the short records of the module
        docstring.
        """
        document = super().to_dict()
        if self.view == OVERVIEW:
            document["groups"] = [
                {
                    "name": group.name,
                    "summary": group.summary,
                    "products": [product.name for product in group.products],
                }
                for group in self.groups
            ]
            document["commands"] = [
                {
                    "id": command.id,
                    "summary": command.summary,
                    "tool": command.tool,
                    "supports_check": command.supports_check,
                }
                for command in self.commands
            ]
        return document

    def to_json(self, *, indent: int | None = 2) -> str:
        """Return the document as JSON text (``Document.to_json``).

        The overview with one record per line instead of one line per key.
        """
        if indent is None or self.view != OVERVIEW:
            return super().to_json(indent=indent)
        return _records_json(self.to_dict(), indent)
