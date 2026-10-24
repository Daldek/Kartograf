"""Examples of error hints (spec 6.3, part (b)).

It has ``example_for``, and the hint of a wrong command line (``usage_hint``).

A ``ValidationError`` names the argument that is wrong (``option``); the hint of
its ``kartograf-error/1`` document points at the CLI flag of that argument and at
a command line that uses it, taken from the examples of the catalog - the same
lines as the ``epilog`` of ``--help`` and ``ExampleInfo.command_line``. The
example is the one of the product the call had (an example of another product
shows another thing), then the one that shows the argument, then the one of the
country, of the mode (a cutout or a list of sheets) and of the kind of
selection of the call. A ``UsageError`` names the command whose line was wrong;
its hint says where the parameters of that command are and gives its first
example. The functions are lookups in the declarations:
no catalog is built, nothing is raised for an unknown command or option.
"""

import shlex
from collections.abc import Mapping

from kartograf.catalog.commands import declared_commands
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.spec import Command, Example, Param

# The arguments that choose the area or the unit of a data command: an example
# that chooses it the same way is closer to the call than one that does not.
_SELECTIONS = ("teryt", "ku", "sheet", "bbox", "geometry", "whole_country")


def _shows(command: Command, param: Param, example: Example) -> bool:
    """Check whether the command line of ``example`` has ``param``.

    It has its flag (not dropped as a default of the flag) or, for a positional
    argument, its value.
    """
    if param.positional:
        return param.name in example.options or param.name in example.run
    flags = {flag for flag in (param.cli_flag, param.short) if flag}
    return bool(flags & set(shlex.split(example_command_line(command, example))))


def _best(
    command: Command, param: Param | None, given: Mapping[str, object] | None
) -> Example | None:
    """Return the example of the hint of a call that gave ``given``.

    ``None`` means the command has examples of other products only.

    With a ``product`` among ``given`` only the examples of that product are
    taken (when the examples of the command tell products apart). Of those the
    first that shows ``param`` wins, then the one of the same ``country``
    (an example without a country is next to it, another country last), then
    the one of the same mode (``cutout`` among ``given``: a cutout of the area
    or a list of sheets), then the one that chooses the area or the unit as
    the call did.
    """
    examples = command.examples
    given = given or {}
    product = given.get("product")
    if isinstance(product, str) and any("product" in e.options for e in examples):
        examples = tuple(e for e in examples if e.options.get("product") == product)
    country = given.get("country")
    selection = next((name for name in _SELECTIONS if given.get(name)), None)

    def rank(example: Example) -> tuple[bool, int, bool, bool]:
        own = example.options.get("country")
        if not isinstance(country, str) or own == country:
            nearness = 0
        else:
            nearness = 1 if own is None else 2
        return (
            param is None or not _shows(command, param, example),
            nearness,
            "cutout" in given
            and bool(example.options.get("cutout")) != bool(given["cutout"]),
            selection is not None and selection not in example.options,
        )

    return min(examples, key=rank, default=None)


def example_for(
    command: str | None,
    option: str | None,
    given: Mapping[str, object] | None = None,
) -> tuple[str | None, str | None]:
    """Return the CLI flag of an argument and an example command line that uses it.

    Parameters
    ----------
    command : str, optional
        Id of the command (``elevation download``); ``None`` or an unknown id
        gives no flag and no example.
    option : str, optional
        The argument the error is about (``ValidationError.option``: the name of
        the API argument, e.g. ``vertical_crs``, ``output_dir``).
    given : mapping, optional
        The arguments of the failed call by their names (``product``,
        ``country``, ``bbox``, ...: what the CLI parsed or an MCP tool was
        given); without it the example does not depend on the call.

    Returns
    -------
    tuple of (str or None, str or None)
        ``(flag, command_line)``: ``flag`` is the CLI flag of the argument
        (``--vertical-crs``; ``None`` for an unknown argument, a positional one
        or one only the API has); ``command_line`` is the first example of the
        command that shows the argument, else its first example - of the
        product of ``given`` when it has one (``None`` for a command without
        examples or without an example of that product).
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
    if not found.examples:
        return flag, None
    chosen = _best(found, param, given)
    return flag, None if chosen is None else example_command_line(found, chosen)


def usage_hint(command: str | None, *, max_chars: int) -> str | None:
    """Return where the parameters of a command are and an example line of it.

    This is the hint of a ``UsageError`` about the command.

    Parameters
    ----------
    command : str, optional
        Id of the command (``elevation download``); ``None`` or an unknown id
        gives no hint.
    max_chars : int
        The longest text allowed: the example is left out when the hint would
        pass it.

    Returns
    -------
    str or None
        ``Parametry komendy: kartograf commands schema --command "<id>".`` followed by
        ``Przyklad:``
        and the first example of the command when it has one and the text fits.
    """
    found = declared_commands().get(command) if command is not None else None
    if found is None:
        return None
    where = f'Parametry komendy: kartograf commands schema --command "{found.id}".'
    _, line = example_for(found.id, None)
    if line and len(candidate := f"{where} Przyklad: {line}") <= max_chars:
        return candidate
    return where
