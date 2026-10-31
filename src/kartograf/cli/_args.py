"""
The data flags of a parsed command as library arguments (ADR-037, ADR-046).

The handlers of the data commands (``elevation download``, ``soil hsg``, ...) do
not know the flags of their command: the declaration in ``kartograf.catalog`` says
which flags are the options of the command and of what kind, and
``library_arguments`` reads them from the namespace the same way ``parse_command``
reads a line - one conversion for both.
"""

import argparse
from pathlib import Path
from typing import Any

from kartograf.catalog.cliparser import parsed_options
from kartograf.catalog.commands import declared_commands
from kartograf.catalog.kinds import convert_arguments
from kartograf.config import resolve_root


def library_arguments(args: argparse.Namespace) -> dict[str, Any]:
    """Return the data options of a parsed data command as library arguments.

    They are the arguments of its library function.

    ``--bbox`` becomes a ``BBox`` (with the CRS of ``--bbox-crs``), a path a
    ``Path``, ``--layers`` and ``--direction`` tuples, ``pl=..,cz=..`` a mapping; a
    flag the line did not give is left out, so the library applies its own default.
    The store (``root``), ``workers`` and the update mode are not data
    options: the handler passes them itself.

    Parameters
    ----------
    args : argparse.Namespace
        The parsed command line (``_command_id`` names its command).

    Raises
    ------
    ValidationError
        A ``--bbox`` that is not four numbers or a per-country value of a wrong
        form (the message of the library).
    """
    command = declared_commands()[args._command_id]
    options, _ = parsed_options(command, args)
    kinds = {param.name: param.kind for param in command.call_options}
    return convert_arguments(kinds, options)


def target_arguments(args: argparse.Namespace) -> dict[str, Path | None]:
    """Return the write target of a parsed command: ``output_dir`` and ``root``.

    At most one of them is given (both is the ``validation_error`` the library
    raises); neither is the default store, which the library resolves. The
    handlers pass them to the library function as they are.
    """
    output_dir = getattr(args, "output_dir", None)
    root = getattr(args, "root", None)
    return {
        "output_dir": None if output_dir is None else Path(output_dir),
        "root": None if root is None else Path(root),
    }


def store_dir(args: argparse.Namespace) -> Path:
    """Return the store of a parsed command: ``--root``, else the default root.

    The default is the root of the settings (``kartograf.config.store_root()``,
    DEV-19.2); the commands that only read the store use it.
    """
    return resolve_root(args.root)
