"""
The canonical command line of a catalog command (spec 8.7).

``format_command_line`` writes ``kartograf <group> <command> <flags>`` from the
values of a call: the flags (and positional values) in the order of the
declaration, so the same call gives the same text and a positional list that
takes the rest of the line (``project add``) stays last.
``example_command_line`` writes the line of a declared example; it is the text
of the ``epilog`` of the command, of ``ExampleInfo.command_line`` and of the
hint of an error (the three agree because there is one formatter).
"""

import os
import shlex
from collections.abc import Mapping, Sequence

from kartograf.catalog.spec import Command, Example, Param

# The store directory of an example line (a command with ``output_dir``).
EXAMPLE_STORE = "./data"
# Per-country values are written PL first, as the library names the countries.
_COUNTRY_ORDER = ("pl", "cz")


def format_command_line(
    command: Command,
    options: Mapping[str, object],
    run: Mapping[str, object] | None = None,
) -> str:
    """The command line of a call.

    Parameters
    ----------
    command : Command
        The declaration; it must have a CLI.
    options : Mapping
        The task options in the JSON form of the manifest, by parameter name
        (``bbox`` as 4 numbers, a per-country value as a text or ``{"pl": ...,
        "cz": ...}``, a list of codes as a list); ``None`` and ``False`` are
        left out.
    run : Mapping, optional
        The other flags of the line by parameter name; they are written short
        when the parameter has a short flag (``-o``).

    Returns
    -------
    str
        ``kartograf elevation download --product nmt ... -o ./data``; a value is
        quoted for a shell (``shlex.quote``), ``--bbox-crs`` is left out when it
        is the default of the flag.

    Raises
    ------
    ValueError
        A command without a CLI, a name that is not a parameter (or has no CLI
        form), a name in both mappings or a value of a wrong form.
    """
    if command.cli_words is None:
        raise ValueError(f"{command.id}: a command without a CLI has no command line")
    run = {} if run is None else run
    known = {param.name: param for param in command.params}
    for name in (*options, *run):
        if name not in known:
            raise ValueError(f"{command.id}: {name!r} is not a parameter")
    for name in sorted(set(options) & set(run)):
        raise ValueError(f"{command.id}: {name!r} given as an option and as a run flag")
    words = ["kartograf", *command.cli_words.split()]
    for param in command.params:
        if param.name in options:
            words += _words(command, param, options[param.name], short=False)
        elif param.name in run:
            words += _words(command, param, run[param.name], short=True)
    return " ".join(words)


def example_command_line(command: Command, example: Example) -> str:
    """The command line of a declared example; a command with a store directory
    gets ``-o ./data`` unless the example names another one."""
    run = dict(example.run)
    if any(param.name == "output_dir" for param in command.params):
        run.setdefault("output_dir", EXAMPLE_STORE)
    return format_command_line(command, example.options, run)


def _words(command: Command, param: Param, value: object, *, short: bool) -> list[str]:
    """The words of one parameter: its flag and value, or a positional's values."""
    flag = param.cli_flag
    if flag is None and not param.positional:
        raise ValueError(f"{command.id}: {param.name} has no command line form")
    if value is None or (param.kind == "flag" and value is False):
        return []
    if param.cli_default is not None and value == param.cli_default:
        return []
    if param.kind == "flag":
        if value is not True or flag is None:
            raise ValueError(f"{param.name}: a flag is true or false, got {value!r}")
        return [param.short if short and param.short else flag]
    if param.positional:
        values = value if param.nargs in ("*", "REMAINDER") else [value]
        if isinstance(values, str) or not isinstance(values, Sequence):
            raise ValueError(f"{param.name}: expected a list of words, got {value!r}")
        return [shlex.quote(_text(param, item)) for item in values]
    assert flag is not None
    text = shlex.quote(_text(param, value))
    return [param.short if short and param.short else flag, text]


def _number(value: object) -> str:
    """``530000`` for ``530000.0``, ``19.93`` as it is."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{value!r} is not a number")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _text(param: Param, value: object) -> str:
    """One value in the text a flag takes."""
    kind = param.kind
    if kind == "bbox":
        if not isinstance(value, Sequence) or isinstance(value, str) or len(value) != 4:
            raise ValueError(f"{param.name}: expected 4 numbers, got {value!r}")
        return ",".join(_number(item) for item in value)
    if kind == "per_country" and isinstance(value, Mapping):
        ordered = sorted(
            value.items(),
            key=lambda item: (
                _COUNTRY_ORDER.index(item[0]) if item[0] in _COUNTRY_ORDER else 9
            ),
        )
        return ",".join(f"{country}={text}" for country, text in ordered)
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{param.name}: expected an integer, got {value!r}")
        return str(value)
    if kind == "str_list" and not param.positional:
        if isinstance(value, str) or not isinstance(value, Sequence):
            raise ValueError(f"{param.name}: expected a list of texts, got {value!r}")
        return ",".join(str(item) for item in value)
    if kind in ("path", "plan") and isinstance(value, os.PathLike):
        return os.fspath(value)
    if isinstance(value, str):
        return value
    raise ValueError(f"{param.name}: cannot write {value!r} on a command line")
