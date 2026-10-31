"""
The check of a call against the declaration of its command (AGI-2.1).

``check_call`` reads the options of a call in the JSON form (the keys of an MCP tool
call) and answers with the arguments of the library function of the command, or raises
``ValidationError``. It knows nothing of a
command in particular: the names, the kinds, ``required``, the allowed values, the
bounds of an integer and the rules among the parameters (``Constraint``) all come from
the declaration - what ``command_schema`` says of the command and the schema of its MCP
tool enforces. What a function checks of the *values* (a sheet code, a TERYT, a country)
is the function's.

The library functions of the data commands check their own request first
(``kartograf.data_commands``); ``validate_command`` leaves those to them.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from kartograf.catalog.build import allowed_values, command_entries
from kartograf.catalog.kinds import convert_arguments
from kartograf.catalog.model import OptionEntry
from kartograf.catalog.spec import Command, Constraint
from kartograf.core.bbox import BBox
from kartograf.exceptions import ValidationError
from kartograf.messages import message


def _entry_options(command: Command) -> dict[str, OptionEntry]:
    """Return the options of the command in the catalog document, by name."""
    entry = next(e for e in command_entries() if e.name == command.id)
    return {option.name: option for option in entry.options}


def _holds(when: Mapping[str, object], arguments: Mapping[str, Any]) -> bool:
    """Say whether every condition of a ``when`` holds (``Constraint.when``).

    ``True`` asks the parameter to be given, a list its value to be one of the listed.
    """
    for name, expected in when.items():
        value = arguments.get(name)
        if expected is True:
            if value is None:
                return False
        elif not isinstance(expected, Sequence) or value not in expected:
            return False
    return True


def _violated(constraint: Constraint, arguments: Mapping[str, Any]) -> bool:
    """Say whether the arguments break a rule among the parameters."""
    given = [name for name in constraint.params if name in arguments]
    param = constraint.param
    when = constraint.when or {}
    match constraint.type:
        case "one_of":
            return len(given) > 1 or (not given and not constraint.optional)
        case "any_of":
            return not given
        case "requires":
            return param in arguments and len(given) < len(constraint.params)
        case "excludes":
            return param in arguments and bool(given)
        case "applies_to":
            return param in arguments and not _holds(when, arguments)
        case "required_when":
            return param not in arguments and _holds(when, arguments)
    raise AssertionError(constraint.type)  # a Constraint checks its own type


def check_constraints(command: Command, arguments: Mapping[str, Any]) -> None:
    """Check the arguments against the rules among the parameters of the command.

    Raises
    ------
    ValidationError
        A rule is broken: ``option`` is the parameter of a rule that is about one,
        ``options`` the parameters of a rule among several, in the order of the rule.
    """
    for constraint in command.constraints:
        if not _violated(constraint, arguments):
            continue
        if constraint.type in ("applies_to", "required_when"):
            raise ValidationError(constraint.message, option=constraint.param)
        own = () if constraint.param is None else (constraint.param,)
        raise ValidationError(constraint.message, options=(*own, *constraint.params))


def _check_allowed(
    name: str, kind: str, value: object, values: list[str | int]
) -> None:
    """Check that a value, or every text of a mapping or list, is one of ``values``."""
    if kind == "per_country" and isinstance(value, Mapping):
        checked = list(value.values())
    elif kind == "str_list" and isinstance(value, tuple):
        checked = list(value)
    else:
        checked = [value]
    for item in checked:
        if item not in values:
            raise ValidationError(
                message(
                    "commands.value_not_allowed",
                    name=name,
                    value=item,
                    allowed=", ".join(str(v) for v in values),
                ),
                option=name,
                allowed=[str(v) for v in values],
            )


def _check_bounds(
    name: str, value: int, minimum: int | None, maximum: int | None
) -> None:
    """Check an integer against its inclusive bounds."""
    if minimum is not None and value < minimum:
        raise ValidationError(
            message("commands.value_at_least", name=name, limit=minimum), option=name
        )
    if maximum is not None and value > maximum:
        raise ValidationError(
            message("commands.value_at_most", name=name, limit=maximum), option=name
        )


def check_call(
    command: Command,
    options: Mapping[str, object],
    targets: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Check a call of a command and return the arguments of its function.

    Parameters
    ----------
    command : Command
        The declaration.
    options : Mapping
        The options of the call in the JSON form, by name (``Command.call_options``):
        ``bbox`` with ``bbox_crs``, a path as a text, a list as a list.
    targets : Mapping, optional
        The write targets the call gave (``root``, ``output_dir``): paths.

    Returns
    -------
    dict
        The library arguments: the options and the targets in the form the function
        takes (a ``BBox``, ``Path`` values, a tuple for a list), and the constants of
        the command (``fixed``).

    Raises
    ------
    ValidationError
        ``options`` is no mapping; an option or a target the command does not have; a
        value of a wrong form, outside the allowed values or the bounds; a missing
        required option; a broken rule among the options (``option`` or ``options``
        name them).
    """
    if not isinstance(options, Mapping):
        raise ValidationError(
            message("commands.options_not_mapping", got=type(options).__name__),
            option="options",
        )
    declared = {param.name: param for param in command.call_options}
    arguments = convert_arguments({n: p.kind for n, p in declared.items()}, options)
    given = dict(targets or {})
    for name in given:
        if not any(p.name == name and p.api_argument for p in command.params):
            raise ValidationError(
                message(
                    "commands.option_not_of_command", name=name, command=command.id
                ),
                option=name,
            )
    arguments.update(convert_arguments(dict.fromkeys(given, "path"), given))
    entries = _entry_options(command)
    for name, param in declared.items():
        if param.kind == "bbox_crs":
            continue  # a part of the bbox
        if param.required and name not in arguments:
            values = allowed_values(command, entries[name])
            raise ValidationError(
                message("commands.option_required", name=name, command=command.id),
                option=name,
                allowed=None if values is None else [str(v) for v in values],
            )
        if name not in arguments:
            continue
        value = arguments[name]
        if param.kind == "bbox" and isinstance(value, BBox) and "bbox_crs" in declared:
            values = allowed_values(command, entries["bbox_crs"])
            if values is not None:
                _check_allowed("bbox_crs", "str", value.crs, values)
            continue
        values = allowed_values(command, entries[name])
        if values is not None:
            _check_allowed(name, param.kind, value, values)
        if param.kind == "int":
            _check_bounds(name, value, param.minimum, param.maximum)
    check_constraints(command, arguments)
    for param in command.params:
        if param.fixed is not None:
            arguments[str(param.api_argument)] = param.fixed
    return arguments
