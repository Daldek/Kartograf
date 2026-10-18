"""
The example of an error hint (spec 6.3, part (b)): ``example_for``.

A ``ValidationError`` names the argument that is wrong (``option``); the hint of
its ``kartograf-error/1`` document points at the CLI flag of that argument and at
a command line that uses it, taken from the examples of the catalog - the same
lines as the ``epilog`` of ``--help`` and ``ExampleInfo.command_line``. The
function is a lookup in the declarations: no catalog is built, nothing is
raised for an unknown command or option.
"""

import shlex

from kartograf.catalog.commands import declared_commands
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.spec import Command, Example, Param


def _shows(command: Command, param: Param, example: Example) -> bool:
    """The command line of ``example`` has ``param``: its flag (not dropped as a
    default of the flag) or, for a positional argument, its value."""
    if param.positional:
        return param.name in example.options or param.name in example.run
    flags = {flag for flag in (param.cli_flag, param.short) if flag}
    return bool(flags & set(shlex.split(example_command_line(command, example))))


def example_for(
    command: str | None, option: str | None
) -> tuple[str | None, str | None]:
    """The CLI flag of an argument and an example command line that uses it.

    Parameters
    ----------
    command : str, optional
        Id of the command (``elevation download``); ``None`` or an unknown id
        gives no flag and no example.
    option : str, optional
        The argument the error is about (``ValidationError.option``: the name of
        the API argument, e.g. ``vertical_crs``, ``output_dir``).

    Returns
    -------
    tuple of (str or None, str or None)
        ``(flag, command_line)``: ``flag`` is the CLI flag of the argument
        (``--vertical-crs``; ``None`` for an unknown argument, a positional one
        or one only the API has); ``command_line`` is the first example of the
        command that shows the argument, else its first example (``None`` for a
        command without examples or without a CLI).
    """
    found = declared_commands().get(command) if command is not None else None
    if found is None:
        return None, None
    param = None
    if option is not None:
        param = next(
            (p for p in found.params if option in (p.name, p.api_argument)), None
        )
    flag = None if param is None else param.cli_flag
    if found.cli is None or not found.examples:
        return flag, None
    chosen = next(
        (e for e in found.examples if param is not None and _shows(found, param, e)),
        found.examples[0],
    )
    return flag, example_command_line(found, chosen)
