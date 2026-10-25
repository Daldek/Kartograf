"""
The CLI parser built from the declarations of the catalog (spec 8.2, ADR-039).

``build_parser`` turns ``Command`` and ``Group`` declarations into the argparse
tree of ``kartograf``: one parser per group and per command, one flag per
parameter with a CLI form, sections and examples of ``--help`` from the
declarations. Flags are never ``required`` - the library reports a missing
value in its own words (rule Z1); only positional arguments are.

``usage_errors=True`` makes every parser raise ``UsageError`` instead of printing
``usage:`` and exiting with 2 (``parse_command``, the ``--json`` mode of the
CLI). The module needs only the standard library, the library's exceptions and
the declarations (and ``kartograf.error_report`` when a usage error ends the
process, which prints the error document).

``parsed_options`` is the way back: the flags of a parsed line, read by the
declarations, as the JSON form of the options (what ``parse_command`` returns and
what the handlers of the CLI convert to library arguments).
"""

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from typing import Any, NoReturn, cast

from kartograf._version import build_version
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.kinds import layer_codes, parse_bbox_arg, parse_per_country
from kartograf.catalog.spec import Command, Group, Param, resolve, sorted_groups
from kartograf.exceptions import UsageError, ValidationError
from kartograf.messages import DEFAULT_LANG, Lang, Message, localize, message

_NORMALIZERS: dict[str, Callable[[str], str]] = {
    "lower": str.lower,
    "upper": str.upper,
    "strip": str.strip,
}


class _HelpFormatter(argparse.HelpFormatter):
    """Help text wrapped by paragraph (a line break starts a new one).

    Lines indented by two spaces - the commands of an ``epilog`` with examples - stay as
    written, so an example can be copied whole.
    """

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        lines = []
        for line in text.split("\n"):
            if line.startswith("  "):
                lines.append(indent + line)
            else:
                lines.append(super()._fill_text(line, width, indent))
        return "\n".join(lines)


class _Parser(argparse.ArgumentParser):
    """``ArgumentParser`` without prefix abbreviations of long flags.

    A command line keeps its meaning when a group gains a flag (``--out`` is never read
    as ``--root``, ``--lay`` is no ambiguous prefix). Every subparser of the CLI is of
    this class (``add_subparsers`` uses the class of its parser) and formats its help
    with ``_HelpFormatter`` (examples in ``epilog``).

    ``usage_errors``: an error raises ``UsageError`` (the argparse message, and the
    id of the command whose parser found it) instead of printing the usage and
    exiting with 2. Otherwise the usage and the message are printed as argparse does
    (a catalog message in ``lang``) and the compact error document
    ``kartograf-error/1``, in English, follows as the last line of stderr (AGI-3.3)
    before the exit.
    """

    def __init__(
        self,
        *args: Any,
        usage_errors: bool = False,
        lang: Lang = DEFAULT_LANG,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("allow_abbrev", False)
        kwargs.setdefault("formatter_class", _HelpFormatter)
        super().__init__(*args, **kwargs)
        self.usage_errors = usage_errors
        self.lang = lang

    def error(self, message: str) -> NoReturn:
        # only the parser of a command knows its id: a group or the root parser
        # has none, and the error is not about one command
        error = UsageError(message, command=self.get_default("_command_id"))
        if self.usage_errors:
            raise error
        try:
            super().error(localize(message, self.lang))
        except SystemExit:
            from kartograf.error_report import error_line, error_report

            print(error_line(error_report(error)), file=sys.stderr, flush=True)
            raise


class _LazyVersionAction(argparse.Action):
    """``--version`` resolving the build identifier only when requested."""

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str = argparse.SUPPRESS,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            option_strings, dest=dest, default=argparse.SUPPRESS, nargs=0, **kwargs
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> NoReturn:
        sys.stdout.write(f"{parser.prog} {build_version()}\n")
        parser.exit()


# Commands removed in 0.8.0 (ADR-039): an input error naming the new command,
# never a working alias.
_REMOVED_COMMANDS = {
    "download": message("catalog.removed_download_replacement"),
    "soilgrids": message("catalog.removed_soilgrids_replacement"),
}


def _product_value(argv: Sequence[str]) -> str | None:
    """Return the ``--product`` value of a command line.

    Also the 0.7.x ``--source``/``-s`` value (``None`` if absent).
    """
    for i, arg in enumerate(argv):
        flag, eq, value = arg.partition("=")
        if eq and flag in ("--product", "--source"):
            return value
        if arg in ("--product", "--source", "-s") and i + 1 < len(argv):
            return argv[i + 1]
    return None


def removed_command_error(argv: Sequence[str]) -> Message | None:
    """Error text for a command line of a command removed in 0.8.0.

    ``kartograf download``, ``kartograf soilgrids ...`` and ``kartograf
    landcover ... --product soilgrids`` (also the 0.7.x ``--source
    soilgrids``) name their replacement; ``None`` for every other command
    line (argparse handles it).
    """
    if not argv:
        return None
    command = argv[0]
    if command in _REMOVED_COMMANDS:
        return message(
            "catalog.removed_command",
            command=command,
            replacement=_REMOVED_COMMANDS[command],
        )
    if command == "landcover" and _product_value(argv[1:]) == "soilgrids":
        return message("catalog.soilgrids_moved")
    return None


# ``--bbox -447000,...``: argparse takes a value starting with "-" after a
# space for a flag; four comma-separated numbers are always a --bbox value.
_BBOX_VALUE = re.compile(r"-?[0-9]+(\.[0-9]+)?(,-?[0-9]+(\.[0-9]+)?){3}")
# Usual mix-ups of a command with a flag of another group (or a flag removed
# in 0.8.0): the hint replaces the list of the commands having the flag.
_LANDCOVER_PRODUCT_HINT = message("catalog.hint_landcover_product")
_UNKNOWN_HINTS = {
    **{
        (f"kartograf landcover {command}", flag): _LANDCOVER_PRODUCT_HINT
        for command in ("download", "list-layers")
        for flag in ("--source", "-s")
    },
    ("kartograf landcover download", "--country"): message(
        "catalog.hint_landcover_country"
    ),
    ("kartograf soil download", "--product"): message("catalog.hint_soil_product"),
    ("kartograf soil hsg", "--stats"): message("catalog.hint_hsg_stats"),
    ("kartograf hydro download", "--sheet"): message("catalog.hint_hydro_sheet"),
}
_JSON_FLAG = "--json"
_JSON_HINT = message("catalog.hint_json")


def _join_bbox_values(argv: Sequence[str]) -> list[str]:
    """Join ``--bbox -447000,...`` into ``--bbox=-447000,...``.

    This is for negative coordinates (e.g. S-JTSK) after a space.
    """
    joined: list[str] = []
    i = 0
    while i < len(argv):
        if (
            argv[i] == "--bbox"
            and i + 1 < len(argv)
            and _BBOX_VALUE.fullmatch(argv[i + 1])
        ):
            joined.append(f"--bbox={argv[i + 1]}")
            i += 2
            continue
        joined.append(argv[i])
        i += 1
    return joined


def _subparsers(
    parser: argparse.ArgumentParser,
) -> "argparse._SubParsersAction[argparse.ArgumentParser] | None":
    return next(
        (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
        None,
    )


def _command_parser(
    root: argparse.ArgumentParser, parsed: argparse.Namespace
) -> argparse.ArgumentParser:
    """Return the parser of the command of a parsed line.

    For ``kartograf elevation download`` it is that command's parser; a line without a
    command gives the group or the root parser.
    """
    current = root
    group = getattr(parsed, "command", None)
    names = (group, getattr(parsed, f"{group}_command", None) if group else None)
    for name in names:
        action = _subparsers(current)
        if name is None or action is None or name not in action.choices:
            break
        current = action.choices[name]
    return current


def _flag_owners(root: argparse.ArgumentParser, flag: str) -> str:
    """Return the commands having ``flag``.

    The text is like ``boundaries, cadastre download; soil hsg``.
    """
    by_command: dict[str, list[str]] = {}
    top = _subparsers(root)
    assert top is not None
    for group, group_parser in top.choices.items():
        commands = _subparsers(group_parser)
        parsers = (
            commands.choices.items() if commands is not None else [("", group_parser)]
        )
        for command, command_parser in parsers:
            if flag in command_parser._option_string_actions:
                by_command.setdefault(command, []).append(group)
    return "; ".join(
        f"{', '.join(groups)} {command}".strip()
        for command, groups in by_command.items()
    )


def _unknown_text(
    root: argparse.ArgumentParser, command: argparse.ArgumentParser, extras: list[str]
) -> str:
    """Return the input error of arguments a command does not have."""
    first = extras[0]
    flag = first.partition("=")[0]
    if not flag.startswith("-"):
        return message("catalog.unknown_argument", argument=first, prog=command.prog)
    hint = _UNKNOWN_HINTS.get((command.prog, flag))
    if hint is None and flag == _JSON_FLAG:
        hint = _JSON_HINT  # every command has it: the listing of owners says nothing
    if hint is None:
        owners = _flag_owners(root, flag)
        hint = message("catalog.hint_owners", owners=owners) if owners else None
    if hint is None:
        return message("catalog.unknown_option", flag=flag, prog=command.prog)
    return message(
        "catalog.unknown_option_hint", flag=flag, hint=hint, prog=command.prog
    )


def parse_command_line(
    parser: argparse.ArgumentParser, argv: Sequence[str]
) -> argparse.Namespace:
    """Run ``parser.parse_args(argv)`` with readable input errors.

    An error exits with code 2, or raises ``UsageError`` for a parser built with
    ``usage_errors``.

    ``--bbox`` with negative coordinates after a space is joined with its
    value; an unknown flag is reported by the parser of the command (its
    usage) with the commands that have it, or a hint for the usual mix-ups
    (``landcover download --product``, ``soil download --product``, ...).
    """
    parsed, extras = parser.parse_known_args(_join_bbox_values(argv))
    if extras:
        command = _command_parser(parser, parsed)
        command.error(_unknown_text(parser, command, extras))
    return parsed


def _json_value(param: Param, value: object) -> object:
    """Return the JSON form of the text or number a flag was given."""
    if param.kind == "per_country":
        return parse_per_country(str(value), param.cli_flag or param.name)
    if param.kind == "str_list":
        return list(cast(Sequence[str], value))
    if param.kind in ("path", "plan"):
        return str(value)
    return value


def parsed_options(
    command: Command, parsed: argparse.Namespace, *, given_only: bool = False
) -> tuple[dict[str, object], dict[str, object]]:
    """Return the flags of a parsed command line as the JSON form of the options.

    Parameters
    ----------
    command : Command
        The declaration of the parsed command (``parsed._command_id``).
    parsed : argparse.Namespace
        The result of the parser of ``command``. A parameter counts when the
        namespace has a value for it that is not ``None`` and not ``False``: with
        the parser of ``given_only`` that is a flag the line wrote, with the parser
        of the CLI (which has defaults) a flag the line wrote or a default.
    given_only : bool
        ``parsed`` comes from the parser of ``given_only``, whose namespace tells
        what the line wrote: a ``--bbox-crs`` without ``--bbox`` is then a mistake
        (the parser of the CLI has the default of the flag for it, so a lone
        ``--bbox-crs`` cannot be told from none there).

    Returns
    -------
    tuple of dict
        ``(options, run)``: the options of the call (``Command.call_options``; of a
        project task, ``Param.task``) and the other flags (``--root``, ``--workers``,
        ``--quiet``, ...), by parameter name, in the JSON form: ``--bbox`` is four
        numbers with ``bbox_crs`` (the CRS of ``--bbox-crs``, else the default of the
        flag), a per-country value a text or a ``{"pl": ..., "cz": ...}`` mapping, a
        path a text, a list of codes a list.

    Raises
    ------
    ValidationError
        A ``--bbox`` that is not four numbers, a per-country value that is not a
        text or ``pl=..,cz=..`` pairs, or (``given_only``) a ``--bbox-crs`` without
        ``--bbox`` (``option="bbox_crs"``).
    """
    crs = next((param for param in command.params if param.kind == "bbox_crs"), None)
    named = {param.name for param in command.call_options}
    options: dict[str, object] = {}
    run: dict[str, object] = {}
    for param in command.params:
        if param.kind == "bbox_crs" or (
            param.cli_flag is None and not param.positional
        ):
            continue
        attribute = param.name if param.positional else param.cli_dest
        value = getattr(parsed, attribute, None)
        if value is None or value is False:
            continue
        if param.kind == "bbox":
            assert crs is not None, f"{command.id}: bbox without bbox_crs"
            given = getattr(parsed, crs.cli_dest, None) or crs.cli_default
            box = parse_bbox_arg(str(value), str(given))
            options[param.name] = [box.min_x, box.min_y, box.max_x, box.max_y]
            options[crs.name] = box.crs
            continue
        target = options if param.name in named else run
        target[param.name] = _json_value(param, value)
    if (
        given_only
        and crs is not None
        and crs.name not in options
        and getattr(parsed, crs.cli_dest, None)
    ):
        area = next(param for param in command.params if param.kind == "bbox")
        raise ValidationError(
            message("catalog.crs_needs_bbox", flag=crs.cli_flag, area=area.cli_flag),
            option=crs.name,
            options=(area.name, crs.name),
        )
    # a line that leaves a required option to the default of its flag (``--project``
    # of a project command) gives it: the call needs it
    for param in command.call_options:
        if param.required and param.cli_default is not None:
            options.setdefault(param.name, _json_value(param, param.cli_default))
    order = [param.name for param in command.call_options]
    return {name: options[name] for name in order if name in options}, run


def _help(text: str, lang: Lang) -> str:
    """Text of an argparse ``help`` in ``lang``: ``%`` starts a format of the parser."""
    return localize(text, lang).replace("%", "%%")


def _epilog(command: Command, lang: Lang) -> str | None:
    """Return ``Examples:`` and one command line per example.

    The help formatter keeps them unwrapped, ready to copy.
    """
    if not command.examples:
        return None
    lines = (f"  {example_command_line(command, e)}" for e in command.examples)
    return message("catalog.examples_header", lang=lang) + "\n" + "\n".join(lines)


def _type(param: Param) -> Callable[[str], Any] | None:
    """Return the argparse ``type`` of a parameter.

    The text of a flag is converted here only when the conversion cannot fail; the rest
    is the library's.
    """
    if param.normalize is not None:
        return _NORMALIZERS[param.normalize]
    if param.kind == "int":
        return int
    if param.kind == "str_list" and not param.positional:
        return layer_codes
    return None


def _argument_kwargs(param: Param, given_only: bool, lang: Lang) -> dict[str, Any]:
    """Return the keyword arguments of ``add_argument`` of a parameter.

    With ``given_only`` there is no default, so the namespace has the flags of the line
    only.
    """
    kwargs: dict[str, Any] = {"help": _help(resolve(param.description), lang)}
    if not param.positional:
        kwargs["dest"] = param.cli_dest
    if param.kind == "flag":
        kwargs["action"] = "store_true"
        if given_only:
            kwargs["default"] = argparse.SUPPRESS
        return kwargs
    if param.metavar is not None:
        kwargs["metavar"] = localize(param.metavar, lang)
    default = param.cli_default if param.cli_default is not None else param.default
    if given_only:
        kwargs["default"] = argparse.SUPPRESS
    elif default is not None:
        kwargs["default"] = default
    converter = _type(param)
    if converter is not None:
        kwargs["type"] = converter
    if param.choices and param.allowed is not None:
        kwargs["choices"] = list(resolve(param.allowed))
    if param.nargs is not None:
        kwargs["nargs"] = (
            argparse.REMAINDER if param.nargs == "REMAINDER" else param.nargs
        )
    return kwargs


def _add_params(
    parser: argparse.ArgumentParser, command: Command, given_only: bool, lang: Lang
) -> None:
    """Return the flags and arguments of ``command`` in declaration order.

    The sections of ``--help`` in order of first use, the exclusive groups inside them.
    """
    sections: dict[str, argparse._ArgumentGroup] = {}
    exclusive: dict[str, argparse._MutuallyExclusiveGroup] = {}
    for param in command.params:
        flag = param.cli_flag
        if flag is None and not param.positional:
            continue
        container: Any = parser
        if param.section is not None:
            title = localize(param.section, lang)
            if title not in sections:
                sections[title] = parser.add_argument_group(title)
            container = sections[title]
        kwargs = _argument_kwargs(param, given_only, lang)
        if flag is None:
            container.add_argument(param.name, **kwargs)
            continue
        if param.exclusive is not None:
            if param.exclusive not in exclusive:
                exclusive[param.exclusive] = container.add_mutually_exclusive_group()
            container = exclusive[param.exclusive]
        names = [flag] if param.short is None else [flag, param.short]
        container.add_argument(*names, **kwargs)


def _add_command(
    subparsers: "argparse._SubParsersAction[Any]",
    command: Command,
    usage_errors: bool,
    given_only: bool,
    lang: Lang,
) -> None:
    parser = subparsers.add_parser(
        command.name,
        help=_help(command.summary, lang),
        description=localize(resolve(command.description), lang) or None,
        epilog=_epilog(command, lang),
        usage_errors=usage_errors,
        lang=lang,
    )
    parser.set_defaults(_command_id=command.id)
    _add_params(parser, command, given_only, lang)


def build_parser(
    commands: Sequence[Command],
    groups: Sequence[Group],
    *,
    prog: str = "kartograf",
    usage_errors: bool = False,
    given_only: bool = False,
    lang: Lang = DEFAULT_LANG,
) -> argparse.ArgumentParser:
    """Return the parser of ``kartograf`` for the declared commands.

    Every command belongs to a group, so the root parser holds the groups, by position
    and name. A parsed
    line carries ``_command_id`` (the id of the command parser) or, for a bare group,
    ``_group_parser`` (the group's parser, whose help the caller prints).

    Parameters
    ----------
    commands, groups : sequence
        The declarations (``declared()`` or synthetic ones).
    prog : str
        The program name of the usage lines.
    usage_errors : bool
        Raise ``UsageError`` instead of printing ``usage:`` and exiting.
    given_only : bool
        The flags have no defaults: a parsed line has an attribute for each flag
        that was written and for no other (``parse_command`` tells a flag given
        with its default value from one that was not given). The help differs
        from the CLI's only in that it shows no defaults.
    lang : {"en", "pl"}
        The language of the help and of the usage errors a parser prints (the
        error document stays English); English for the API.
    """
    parser = _Parser(
        prog=prog,
        description=localize(message("catalog.parser_description"), lang),
        epilog=localize(message("catalog.parser_epilog"), lang),
        usage_errors=usage_errors,
        lang=lang,
    )
    parser.add_argument(
        "--version",
        action=_LazyVersionAction,
        help=localize(message("catalog.version_help"), lang),
    )
    subparsers = parser.add_subparsers(
        dest="command", help=localize(message("catalog.commands_help"), lang)
    )
    for group in sorted_groups(groups):
        group_parser = subparsers.add_parser(
            group.name,
            help=_help(group.summary, lang),
            description=localize(group.description, lang),
            usage_errors=usage_errors,
            lang=lang,
        )
        group_parser.set_defaults(_group_parser=group_parser)
        group_commands = group_parser.add_subparsers(
            dest=f"{group.name}_command",
            title=localize(message("catalog.commands_title"), lang),
            metavar=localize(message("catalog.metavar_command"), lang),
        )
        for command in commands:
            if command.group == group.name:
                _add_command(group_commands, command, usage_errors, given_only, lang)
    return parser
