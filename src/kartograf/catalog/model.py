"""
The documents of the command catalog (AGI-2.4, spec 8.1).

``CommandList`` is ``kartograf-command-list/1``, what ``kartograf commands list``
writes: one short row per command, so that an agent picks a command without loading the
options of all of them (AGI-1.5). ``CommandCatalog`` is ``kartograf-commands/1`` (Nogat
``commands-1``), what ``kartograf commands schema --command "<group> <verb>"`` writes: a
command with its options, result, effects, rules, examples and errors, in English
(AGI-9.1) with the Polish texts in ``i18n.pl``.

The documents are built from the declarations of ``kartograf.catalog.commands`` by
``kartograf.catalog.build``; every collection is a tuple: a catalog is built once per
process and is read-only data. An optional key of an option is left out of the JSON when
it has no value (the schema has no ``null`` there).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from kartograf.serialization import Document, EncodeContext


@dataclass(frozen=True)
class CommandRow:
    """One command of the list (``kartograf-command-list/1``).

    Attributes
    ----------
    name : str
        ``<group> <verb>`` as typed in the CLI.
    operation_id : str
        ``kartograf_<group>_<verb>``: the name of the MCP tool and the key of the
        command in every interface.
    summary : str
        One sentence that starts with a verb (English).
    families : tuple of str
        The MCP tool families of the command (``core`` among them for the main
        tasks); empty for a command without a tool.
    read_only : bool
        The command changes nothing outside the process.
    check : str, optional
        The command that plans this one without effects: the command itself with the
        option ``check_updates``; ``None`` when it has no plan.
    """

    name: str
    operation_id: str
    summary: str
    families: tuple[str, ...]
    read_only: bool
    check: str | None


@dataclass(frozen=True)
class GroupRow:
    """A group of the list: its summary and the products of its commands."""

    name: str
    summary: str
    products: tuple[str, ...]


@dataclass(frozen=True)
class CommandList(Document):
    """The summary of the catalog (``kartograf-command-list/1``).

    Attributes
    ----------
    tool, version : str
        ``kartograf`` and its version.
    groups : tuple of GroupRow
        Every group in the order of ``kartograf --help``.
    commands : tuple of CommandRow
        Every command in the order of the catalog.
    """

    SCHEMA: ClassVar[str] = "kartograf-command-list/1"

    tool: str
    version: str
    groups: tuple[GroupRow, ...]
    commands: tuple[CommandRow, ...]


@dataclass(frozen=True)
class EnumValue:
    """An allowed value of an option with its one-line meaning (AGI-2.3)."""

    value: str | int
    meaning: str


@dataclass(frozen=True)
class OptionEntry:
    """One option of a command (AGI-2.3).

    The JSON object has the keys ``name``, ``type``, ``items``, ``unit``,
    ``required``, ``default``, ``enum``, ``min``, ``max``, ``examples``,
    ``description``, ``one_of`` and ``path_role``, in this order; those without a value
    are left out.

    Attributes
    ----------
    name : str
        The name of the option: the argument of the library function, the key of an MCP
        tool call and, as ``--kebab-case``, the flag of the CLI.
    type : str
        ``string``, ``integer``, ``boolean``, ``array`` or ``object``.
    required : bool
        The library rejects the call without it.
    description : str
        What the option is, in English.
    items : str, optional
        The type of the items of an ``array``.
    unit : str, optional
        The unit of a physical value.
    default : object
        The value the library uses when the option is omitted (``None``: none).
    enum : tuple of EnumValue, optional
        The allowed values with their meanings.
    minimum, maximum : int, optional
        Bounds of an integer.
    examples : tuple, optional
        Example values.
    one_of : str, optional
        The mutually exclusive group the option belongs to (``area``): exactly one of
        its members is given.
    path_role : {"input", "output", "root"}, optional
        What a path option is for; the MCP server checks it against its allowed
        directories.
    """

    name: str
    type: str
    required: bool
    description: str
    items: str | None = None
    unit: str | None = None
    default: object = None
    enum: tuple[EnumValue, ...] | None = None
    minimum: int | None = None
    maximum: int | None = None
    examples: tuple[object, ...] | None = None
    one_of: str | None = None
    path_role: str | None = None

    def __json__(self, ctx: EncodeContext) -> dict[str, object]:
        """Return the object without the keys that have no value."""
        entry: dict[str, object] = {"name": self.name, "type": self.type}
        if self.items is not None:
            entry["items"] = self.items
        if self.unit is not None:
            entry["unit"] = self.unit
        entry["required"] = self.required
        if self.default is not None:
            entry["default"] = self.default
        if self.enum:
            entry["enum"] = self.enum
        if self.minimum is not None:
            entry["min"] = self.minimum
        if self.maximum is not None:
            entry["max"] = self.maximum
        if self.examples:
            entry["examples"] = self.examples
        entry["description"] = self.description
        if self.one_of is not None:
            entry["one_of"] = self.one_of
        if self.path_role is not None:
            entry["path_role"] = self.path_role
        return entry


@dataclass(frozen=True)
class ResultEntry:
    """The document a command returns and how many a call may return (AGI-2.2)."""

    schema: str
    cardinality: str


@dataclass(frozen=True)
class EffectsEntry:
    """What a command does to the outside world (AGI-2.2).

    Attributes
    ----------
    read_only : bool
        The command changes nothing.
    writes : {"none", "add", "replace", "delete"}
        The kind of write: ``add`` writes new versions or entries and never overwrites,
        ``delete`` removes data.
    idempotent, network, destructive : bool
        Repeating the call gives the same state; the command uses the network; it
        removes data.
    """

    read_only: bool
    writes: str
    idempotent: bool
    network: bool
    destructive: bool


@dataclass(frozen=True)
class ExampleEntry:
    """An example call: the CLI line, an excerpt of its result and what it shows."""

    call: str
    result: Mapping[str, object]
    title: str


@dataclass(frozen=True)
class PolishTexts:
    """The Polish texts of a command (``i18n.pl``)."""

    summary: str
    description: str
    rules: tuple[str, ...]


@dataclass(frozen=True)
class I18nEntry:
    """The translations of the texts of a command."""

    pl: PolishTexts


@dataclass(frozen=True)
class CommandEntry:
    """One command of ``kartograf-commands/1`` (Nogat ``commands-1``).

    Attributes
    ----------
    name, operation_id, function : str
        ``<group> <verb>``, ``kartograf_<group>_<verb>`` (the MCP tool) and the library
        function that implements it.
    summary, description : str
        What the command does, in English: one sentence, then when to use it, when not
        to and its main limit.
    options : tuple of OptionEntry
        The options of the command.
    result : ResultEntry
        The result document.
    effects : EffectsEntry
        What the command changes.
    check : str, optional
        The command that plans this one without effects (``name`` itself with the option
        ``check_updates``).
    families : tuple of str
        The MCP tool families (``core`` among them for the main tasks).
    rules : tuple of str
        Short imperative rules for an agent.
    examples : tuple of ExampleEntry
        At least one: a complete CLI call with an excerpt of its result.
    errors : tuple of str
        The registry codes the command can raise.
    i18n : I18nEntry
        The Polish texts.
    """

    name: str
    operation_id: str
    function: str
    summary: str
    description: str
    options: tuple[OptionEntry, ...]
    result: ResultEntry
    effects: EffectsEntry
    check: str | None
    families: tuple[str, ...]
    rules: tuple[str, ...]
    examples: tuple[ExampleEntry, ...]
    errors: tuple[str, ...]
    i18n: I18nEntry


@dataclass(frozen=True)
class CommandCatalog(Document):
    """The description of commands (``kartograf-commands/1``).

    Attributes
    ----------
    tool, version : str
        ``kartograf`` and its version.
    commands : tuple of CommandEntry
        The commands described: the one of ``command_schema``.
    """

    SCHEMA: ClassVar[str] = "kartograf-commands/1"

    tool: str
    version: str
    commands: tuple[CommandEntry, ...]
