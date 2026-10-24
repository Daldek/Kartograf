"""
The data flags of a parsed command as library arguments (ADR-037, ADR-046).

The handlers of the data commands (``elevation download``, ``soil hsg``, ...) do
not know the flags of their command: the declaration in ``kartograf.catalog`` says
which flags are the options of the command and of what kind, and
``library_arguments`` reads them from the namespace the same way ``parse_command``
reads a line and a project task reads its options - one conversion for all of them.
"""

import argparse
from typing import Any

from kartograf.catalog.cliparser import parsed_options
from kartograf.catalog.commands import declared_commands
from kartograf.catalog.kinds import convert_arguments


def library_arguments(args: argparse.Namespace) -> dict[str, Any]:
    """Return the data options of a parsed data command as library arguments.

    They are the arguments of its library function.

    ``--bbox`` becomes a ``BBox`` (with the CRS of ``--bbox-crs``), a path a
    ``Path``, ``--layers`` and ``--direction`` tuples, ``pl=..,cz=..`` a mapping; a
    flag the line did not give is left out, so the library applies its own default.
    The store (``output_dir``), ``workers`` and the update mode are not data
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
    return convert_arguments(command.task_options, options)
