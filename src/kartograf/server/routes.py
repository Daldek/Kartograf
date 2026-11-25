"""
The routes of ``kartograf server``, read from the command catalog (ADR-063 decision 2).

Every command whose catalog entry has a ``rest`` is served at its path,
``/api/v1/<group>/<verb>``, with its method (AGI-6.1): a ``GET`` takes its options
from the query (an array as its values joined by ``,``), a ``POST`` from a JSON
object. A data command is served as its plan alone (``POST …?check=true``). An
option with a ``path_role`` is local: the server refuses it. A command whose
``rest`` is ``null`` (the user's store, cache and settings) is not served. Nothing
here imports Starlette.
"""

import functools
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from kartograf.catalog.build import command_entries, declared_options
from kartograf.catalog.commands import declared
from kartograf.catalog.kinds import parse_per_country
from kartograf.catalog.model import CommandEntry, RestEntry
from kartograf.catalog.spec import Command, Kind, PathRole
from kartograf.exceptions import ValidationError
from kartograf.messages import message

__all__ = [
    "API_BASE",
    "LocalCommand",
    "ServedCommand",
    "local_commands",
    "query_options",
    "served_commands",
]

API_BASE: Final = "/api/v1"
"""The base of the routes of the API, major 1 (AGI-6.1)."""

_INTEGER = re.compile(r"[+-]?[0-9]+")
_TRUE: Final = frozenset({"true", "1"})
_FALSE: Final = frozenset({"false", "0"})


@dataclass(frozen=True)
class ServedCommand:
    """A command the server serves, with what its route needs of the declaration.

    Attributes
    ----------
    command : Command
        The declaration.
    entry : CommandEntry
        Its entry of ``kartograf-commands/1``.
    rest : RestEntry
        Its route: ``method``, ``path`` and ``key``.
    kinds : Mapping
        Every option of the command as ``commands schema`` lists it, with its kind.
    paths : Mapping
        The options with a ``path_role`` (refused), with the role.
    call : frozenset of str
        The options of a call proper (``Command.call_options``); the others are the
        write targets, ``check`` and the options of a run.
    """

    command: Command
    entry: CommandEntry
    rest: RestEntry
    kinds: Mapping[str, Kind]
    paths: Mapping[str, PathRole]
    call: frozenset[str]

    @property
    def plans(self) -> bool:
        """The command is a data command: the server answers its plan only."""
        return self.command.kind == "data"


@dataclass(frozen=True)
class LocalCommand:
    """A command of the catalog the server does not serve (``rest`` ``null``).

    Its path, ``/api/v1/<group>/<verb>``, answers ``forbidden`` (``not_served``):
    it works on the user's own store, cache or settings.
    """

    command: Command
    path: str


@functools.cache
def served_commands() -> tuple[ServedCommand, ...]:
    """Return the commands the server serves, in the order of the catalog.

    Raises
    ------
    ValueError
        A route outside ``API_BASE`` (a program error of the catalog).
    """
    served = []
    for command, entry in zip(declared().commands, command_entries(), strict=True):
        if entry.rest is None:
            continue
        if not entry.rest.path.startswith(f"{API_BASE}/"):
            raise ValueError(f"{command.id}: the route {entry.rest.path} is not API 1")
        options = declared_options(command)
        served.append(
            ServedCommand(
                command=command,
                entry=entry,
                rest=entry.rest,
                kinds={param.name: param.kind for param in options},
                paths={
                    param.name: param.path_role
                    for param in options
                    if param.path_role is not None
                },
                call=frozenset(param.name for param in command.call_options),
            )
        )
    return tuple(served)


@functools.cache
def local_commands() -> tuple[LocalCommand, ...]:
    """Return the commands of the catalog the server does not serve, with their path."""
    return tuple(
        LocalCommand(command, f"{API_BASE}/{command.group}/{command.name}")
        for command, entry in zip(declared().commands, command_entries(), strict=True)
        if entry.rest is None
    )


def query_options(
    served: ServedCommand, items: Sequence[tuple[str, str]]
) -> dict[str, object]:
    """Return the options of a ``GET`` from its query, in the JSON form of the API.

    A whole number (``int``), ``true`` or ``false`` (``flag``, also ``1`` and ``0``),
    four numbers joined by ``,`` (``bbox``), values joined by ``,`` (a list) and a
    per-country value as the CLI writes it (``pl=1m,cz=2m``). A text that is not of
    its kind stays a text, and a name that is no option of the command stays too:
    the check of the call refuses both with the messages of the library.

    Raises
    ------
    ValidationError
        A name given more than once (``option`` the name).
    """
    counts = Counter(name for name, _ in items)
    options: dict[str, object] = {}
    for name, text in items:
        if counts[name] > 1:
            raise ValidationError(
                message("server.query_repeated", name=name, count=counts[name]),
                option=name,
            )
        options[name] = _query_value(served.kinds.get(name), name, text)
    return options


def _query_value(kind: Kind | None, name: str, text: str) -> object:
    """Return a value of the query in the JSON form of its kind (see above)."""
    match kind:
        case "int":
            return int(text) if _INTEGER.fullmatch(text.strip()) else text
        case "flag":
            word = text.strip().lower()
            return True if word in _TRUE else False if word in _FALSE else text
        case "bbox":
            try:
                numbers = [float(part) for part in text.split(",")]
            except ValueError:
                return text
            if len(numbers) != 4 or not all(math.isfinite(n) for n in numbers):
                return text
            return numbers
        case "str_list":
            return [part.strip() for part in text.split(",") if part.strip()]
        case "per_country":
            return parse_per_country(text, name)
        case _:
            return text
