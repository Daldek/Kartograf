"""
Declarations of the commands: one module per group (spec 8.2).

Every public module of this package declares ``COMMANDS`` (a tuple of
``Command``) and, when it owns CLI groups, ``GROUPS`` (a tuple of ``Group``);
``declared`` finds the modules by name, so a new group is one new module - no
shared file to edit. Modules starting with ``_`` are helpers, not groups.
"""

import functools
from importlib import import_module
from pkgutil import iter_modules
from typing import NamedTuple

from kartograf.catalog.spec import Command, Group

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


@functools.cache
def declared() -> Declared:
    """The declarations of every module of this package.

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
        commands.extend(module.COMMANDS)
        groups.extend(getattr(module, "GROUPS", ()))
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
    ordered = sorted(groups, key=lambda group: (group.position, group.name))
    return Declared(tuple(commands), tuple(ordered))
