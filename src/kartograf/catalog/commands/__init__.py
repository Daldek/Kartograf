"""
Declarations of the commands: one module per group (spec 8.2).

Every public module of this package declares ``COMMANDS`` (a tuple of
``Command``) and, when it owns CLI groups, ``GROUPS`` (a tuple of ``Group``);
``declared`` finds the modules by name, so a new group is one new module - no
shared file to edit. Modules starting with ``_`` are helpers, not groups.
"""

import functools
from collections.abc import Mapping
from dataclasses import replace
from importlib import import_module
from pkgutil import iter_modules
from types import MappingProxyType
from typing import NamedTuple

from kartograf.catalog.shared import LANG
from kartograf.catalog.spec import Command, Group, check_declarations, sorted_groups

# Order of the modules - and so of the commands of the catalog: the data
# commands of the project manifest in the order of ``COMMANDS`` (elevation
# first), then the project, the cache and the queries. A module that is not
# listed follows, by name.
MODULE_ORDER = (
    "elevation",
    "imagery",
    "landcover",
    "soil",
    "boundaries",
    "cadastre",
    "models3d",
    "hydro",
    "names",
    "maps",
    "geodesy",
    "project",
    "misc",
    "config",
)


class Declared(NamedTuple):
    """Every declared command (module order) and CLI group (``--help`` order)."""

    commands: tuple[Command, ...]
    groups: tuple[Group, ...]


def _module_names() -> list[str]:
    names = [m.name for m in iter_modules(__path__) if not m.name.startswith("_")]
    return sorted(
        names,
        key=lambda name: (
            MODULE_ORDER.index(name) if name in MODULE_ORDER else len(MODULE_ORDER),
            name,
        ),
    )


def _with_language(command: Command) -> Command:
    """Give a command the CLI-only ``--lang``, after ``--json`` (all commands)."""
    if any(param.name == LANG.name for param in command.params):
        return command
    params = list(command.params)
    after = next((i for i, param in enumerate(params) if param.name == "json"), None)
    params.insert(len(params) if after is None else after + 1, LANG)
    return replace(command, params=tuple(params))


@functools.cache
def declared() -> Declared:
    """Return the declarations of every module of this package.

    Raises
    ------
    ValueError
        A command id or a group name declared twice, a command of a CLI group
        nobody declares, or a group without commands.
    """
    commands: list[Command] = []
    groups: list[Group] = []
    for name in _module_names():
        module = import_module(f"{__name__}.{name}")
        commands.extend(_with_language(command) for command in module.COMMANDS)
        groups.extend(getattr(module, "GROUPS", ()))
    check_declarations(commands, groups)
    return Declared(tuple(commands), sorted_groups(groups))


@functools.cache
def declared_commands() -> Mapping[str, Command]:
    """Return the declared commands by id (``elevation download``).

    The order is that of ``declared().commands``.
    """
    return MappingProxyType({command.id: command for command in declared().commands})
