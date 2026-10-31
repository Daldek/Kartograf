"""
The command layer: a command as data (spec 8.7; KB-2..KB-5 of Archiwista; AGI-2.1).

Every command of the catalog (``elevation download``, ``soil hsg``, ``sheet parse``,
``store init``, ...; ``kartograf commands list``) is called, read, checked and written
from its *options*: the JSON form of the arguments of its library function (``bbox`` as
four numbers with ``bbox_crs``, a path as a text, a per-country value as a text or
``{"pl": ..., "cz": ...}``, a list as a list, no ``null`` and no ``false``) - the form
of the arguments of an MCP tool. The write targets (``root``, ``output_dir``) and the
options of a run (``update``, ``plan``, ``workers``, ``summary``) are given by name
beside the options, as the arguments of the function that are not options of a call
(``Command.call_options``).

``parse_command`` reads a command line with the parser of the command catalog (the
parser of ``kartograf`` itself), ``validate_command`` checks the options against the
declaration of the command without network and without writing, ``format_command``
writes the canonical command line, ``run_command`` calls the library function of the
command and ``check_command`` its ``check_*`` twin, the plan without effects. Nothing
here knows a command by name: the function, its arguments, the required options, the
allowed values, the bounds, the rules among the options and the twin come from the
declaration (``kartograf.catalog``); the data commands keep the validation of their
own function (``kartograf.data_commands``).

Examples
--------
>>> from kartograf import format_command, parse_command
>>> call = parse_command("elevation download --product nmt --sheet N-34-130-D-d-2-4"
...                      " --resolution 1m --vertical-crs EVRF2007 --root ./data")
>>> call.options["product"], call.run["root"]
('nmt', './data')
>>> format_command(call.command, call.options, run=call.run)
'kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 \
--resolution 1m --vertical-crs EVRF2007 --root ./data'
"""

import argparse
import functools
import inspect
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.arguments import check_call
from kartograf.catalog.build import unknown_command
from kartograf.catalog.cliparser import (
    build_parser,
    parse_command_line,
    parsed_options,
    removed_command_error,
)
from kartograf.catalog.commands import declared, declared_commands
from kartograf.catalog.formatting import format_command_line
from kartograf.catalog.kinds import convert_arguments
from kartograf.catalog.spec import Command, Kind
from kartograf.data_commands import DATA_COMMANDS
from kartograf.download.fetch import UpdateMode
from kartograf.download.manager import DownloadProgress
from kartograf.download.plan import UpdatePlan
from kartograf.envelope import CommandResult, wrap
from kartograf.exceptions import UsageError, ValidationError
from kartograf.messages import message, reason
from kartograf.notices import Notice
from kartograf.output import resolve_target
from kartograf.serialization import Document

# Flags that print and exit: no part of a command that can be called.
_EXITING_FLAGS = ("-h", "--help", "--version")
_PROGRAM = "kartograf"
# The effect that makes a command work on a store (never on plain files).
_STORE_EFFECT = "store_write"


@dataclass(frozen=True)
class CommandCall:
    """A parsed command line.

    Attributes
    ----------
    command : str
        The command id (``elevation download``).
    options : dict
        The options of the call that the line gave, in the JSON form, in the order of
        the parameters of the command (``Command.call_options``); ``bbox`` always
        comes with ``bbox_crs``.
    run : dict
        The other flags the line gave, by parameter name (``output_dir``, ``root``,
        ``upgrade``, ``force``, ``check``, ``plan``, ``workers``, ``quiet``,
        ``json``, ``summary``): a text, a number or ``True``.
    """

    command: str
    options: dict[str, object]
    run: dict[str, object]


@functools.cache
def _parser() -> argparse.ArgumentParser:
    """Build the parser of ``kartograf`` that raises ``UsageError``.

    It keeps no defaults: a parsed line has the flags that were written and no
    others.
    """
    declarations = declared()
    return build_parser(
        declarations.commands,
        declarations.groups,
        usage_errors=True,
        given_only=True,
    )


def _declaration(command: str) -> Command:
    """Return the declaration of a command, by its name or its ``operation_id``.

    Raises
    ------
    ValidationError
        The command is not given or is not in the catalog (``option="command"``,
        ``allowed`` the names of the commands).
    """
    found = None
    if isinstance(command, str):
        found = next(
            (
                c
                for c in declared_commands().values()
                if command in (c.id, c.operation_id)
            ),
            None,
        )
    if found is None:
        raise unknown_command(command)
    return found


def _words(tokens: Sequence[str]) -> str | None:
    """Return the id of the command the first two words of a line name, if they do."""
    if len(tokens) > 1 and f"{tokens[0]} {tokens[1]}" in declared_commands():
        return f"{tokens[0]} {tokens[1]}"
    return None


def _call(parsed: argparse.Namespace) -> CommandCall:
    """Return the ``CommandCall`` of the namespace of a parsed line."""
    command = declared_commands()[parsed._command_id]
    options, run = parsed_options(command, parsed, given_only=True)
    return CommandCall(command.id, options, run)


def parse_command(argv: Sequence[str] | str) -> CommandCall:
    """Read a command line of any command with the parser of ``kartograf``.

    The parser is the one of the CLI (the same flags, ``choices`` and messages),
    built from the catalog of the commands; it tells a flag that was written from
    one that was not, so ``options`` and ``run`` hold what the line gave and
    nothing else.

    Parameters
    ----------
    argv : sequence of str or str
        The words of a line, with or without the leading ``kartograf``
        (``["elevation", "download", "--product", "nmt"]``); a text is split like a
        shell line (``shlex.split``).

    Returns
    -------
    CommandCall
        The command, its options (JSON form; ``bbox`` with ``bbox_crs``, which is
        ``EPSG:2180`` when the line gives only ``--bbox``) and the other flags of the
        line.

    Raises
    ------
    UsageError
        A mistake of the line: an unknown command or flag, a flag without its
        value, a value outside the choices of a flag, ``--help``/``--version``,
        a removed command, an empty line, a group without a command
        (``command`` is the id of the command the line named, when it did).
    ValidationError
        A ``--bbox`` that is not four numbers or a ``--bbox-crs`` without ``--bbox``
        (``option="bbox_crs"``).
    """
    try:
        tokens = shlex.split(argv) if isinstance(argv, str) else list(argv)
    except ValueError as error:
        raise UsageError(
            message("commands.invalid_command_line", error=reason(error))
        ) from error
    if tokens and tokens[0] == _PROGRAM:
        del tokens[0]  # a whole line, as ``format_command`` writes it
    if not tokens:
        raise UsageError(message("commands.give_command"))
    removed = removed_command_error(tokens)
    if removed is not None:
        raise UsageError(removed)
    named = _words(tokens)
    if any(token in _EXITING_FLAGS for token in tokens):
        raise UsageError(
            message("commands.help_version_not_a_call"),
            command=named,
        )
    parsed = parse_command_line(_parser(), tokens)
    command = getattr(parsed, "_command_id", None)
    if command is None:
        group = str(getattr(parsed, "command", tokens[0]))
        raise UsageError(
            message(
                "commands.give_group_commands",
                group=group,
                group_commands=", ".join(
                    c.id for c in declared_commands().values() if c.group == group
                ),
            )
        )
    return _call(parsed)


def _targets(
    declaration: Command,
    output_dir: str | Path | None,
    root: str | Path | None,
) -> dict[str, object]:
    """Return the write targets a call gave, for ``check_call``.

    Raises
    ------
    ValidationError
        Both are given (``exclusive_options``), or the command writes only a store
        and was given ``output_dir`` (``store_only_option``).
    """
    if output_dir is not None and root is not None:
        resolve_target(output_dir=output_dir, root=root)  # the one error of the pair
    names = {param.name for param in declaration.params}
    if (
        output_dir is not None
        and "output_dir" not in names
        and ("root" in names or _STORE_EFFECT in declaration.effects)
    ):
        raise ValidationError(
            message("commands.store_only_command", command=declaration.id),
            option="output_dir",
            hint=(
                message("output.store_only_option_hint", option="--output-dir")
                if "root" in names
                else None
            ),
            reason="store_only_option",
        )
    given = {"output_dir": output_dir, "root": root}
    return {name: value for name, value in given.items() if value is not None}


def validate_command(
    command: str,
    options: Mapping[str, object],
    *,
    output_dir: str | Path | None = None,
    root: str | Path | None = None,
) -> None:
    """Check a call of a command against its declaration.

    Runs without network and without writing. A data command gets the checks of its
    library function: what it does before its first request. Every other command is
    checked against its declaration
    (``kartograf commands schema``): the names and the form of the options, the
    required ones, the allowed values, the bounds and the rules among the options;
    what its function checks of a value is the function's, at the run.

    Parameters
    ----------
    command : str
        A command of the catalog (``elevation download``) or its ``operation_id``.
    options : Mapping
        The options in the JSON form (``Command.call_options``): not the targets and
        the options of a run, which are given by name.
    output_dir, root : str or Path, optional
        Where the command would write, plain files or the store (at most one: both
        are ``validation_error``, ``details.reason`` ``exclusive_options``); the
        checks do not open either, and without a store the current directory stands
        in. A command that works on a store only refuses ``output_dir``
        (``store_only_option``). A geometry file is read, as the function reads it.

    Raises
    ------
    ValidationError
        An unknown command or option, a value of a wrong form, both targets, or a
        rule of the command (``option`` names the option; ``allowed`` its values).
    """
    declaration = _declaration(command)
    if declaration.kind == "data":
        resolve_target(output_dir=output_dir, root=root)
        entry = DATA_COMMANDS[declaration.id]
        store = Path(root) if root is not None and output_dir is None else Path(".")
        entry.validate(store, convert_arguments(entry.options, options))
        return
    check_call(declaration, options, _targets(declaration, output_dir, root))


def _option_kinds(declaration: Command) -> dict[str, Kind]:
    """Return the options of a call by name, with their kinds."""
    return {param.name: param.kind for param in declaration.call_options}


def _run_kinds(declaration: Command) -> dict[str, Kind]:
    """Return the flags of a run that a command line can write, by name.

    The kinds are those a line gives the flags: a plan is a file (a path), not the
    document of the API, and the argument ``update`` has no flag (``--upgrade``
    and ``--force`` stand for it).
    """
    options = {param.name for param in declaration.call_options}
    return {
        param.name: "path" if param.kind == "plan" else param.kind
        for param in declaration.params
        if param.name not in options
        and (param.cli_flag is not None or param.positional)
    }


def format_command(
    command: str,
    options: Mapping[str, object],
    *,
    run: Mapping[str, object] | None = None,
) -> str:
    """Return the canonical command line of a command.

    The line has the form ``kartograf <group> <command> <flags>``.

    The flags follow the order of the parameters of the command; ``--bbox-crs`` is
    left out when it is the default of the flag; ``run`` adds the other flags
    (``root`` as ``--root``): ``root`` and ``plan`` are paths, ``workers``
    a whole number, ``upgrade``, ``force``, ``check``, ``quiet``, ``json``
    and ``summary`` are ``True`` (or left out). ``parse_command`` reads the line
    back into the same command, options and run.

    Raises
    ------
    ValidationError
        An unknown command, an option the command does not have, one in both
        ``options`` and ``run``, a flag of ``run`` that is not a flag of a run (an
        option of the call, the argument ``update``), or a value of a wrong form
        (``option`` names it).
    """
    declaration = _declaration(command)
    given_options = dict(options)
    given_run = {} if run is None else dict(run)
    names = {param.name for param in declaration.params}
    for name in (*given_options, *given_run):
        if name not in names:
            raise ValidationError(
                message(
                    "commands.option_not_of_command", name=name, command=declaration.id
                ),
                option=name,
            )
    for name in sorted(set(given_options) & set(given_run)):
        raise ValidationError(
            message("commands.option_given_twice", name=name),
            option=name,
        )
    convert_arguments(_option_kinds(declaration), given_options)
    convert_arguments(_run_kinds(declaration), given_run)
    return format_command_line(declaration, given_options, given_run)


def _function(name: str) -> Callable[..., Any]:
    """Return a library function of the catalog: a public name of ``kartograf``."""
    import kartograf

    return cast(Callable[..., Any], getattr(kartograf, name))


def _hooks(
    function: Callable[..., Any], cache: MetadataCache | bool, **given: object
) -> dict[str, object]:
    """Return what ``function`` takes of the cache, the hooks and the flags given.

    By name: a function without the parameter is not given it, and a hook that is
    not set (``None``, or a flag that is false) is left out; the cache is always
    given, ``False`` too.
    """
    parameters = inspect.signature(function).parameters
    hooks: dict[str, object] = {
        name: value
        for name, value in given.items()
        if name in parameters and value is not None and value is not False
    }
    if "cache" in parameters:
        hooks["cache"] = cache
    return hooks


def _summary_commands() -> str:
    """Return the commands that have the option ``summary``, for the message."""
    return ", ".join(
        command.id
        for command in declared_commands().values()
        if any(param.name == "summary" for param in command.params)
    )


def run_command(
    command: str,
    options: Mapping[str, object],
    *,
    output_dir: str | Path | None = None,
    root: str | Path | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int | None = None,
    summary: bool = False,
    cache: MetadataCache | bool = True,
    on_progress: Callable[[DownloadProgress], None] | None = None,
    on_notice: Callable[[Notice], None] | None = None,
) -> CommandResult[Document]:
    """Run a command: the library function of the command with the options.

    The options are checked first (``validate_command``); the function is then the one
    the declaration names (``download_data``, ``download_collection``,
    ``download_landcover``, ``download_soil`` or ``calculate_hsg`` for a data command,
    ``describe_sheet``, ``init_store``, ... for another). The
    result is the envelope ``kartograf-result/1`` of the command (``to_dict()`` is the
    document the CLI ``--json`` prints), and ``result`` is what that function returns
    (``kartograf-download/1`` for a download, the document of the command for the
    others: a read-only command returns its document, ``store init`` writes the marker
    and returns it).

    Parameters
    ----------
    command : str
        A command of the catalog (``elevation download``) or its ``operation_id``.
    options : Mapping
        The options in the JSON form (``validate_command``).
    output_dir : str or Path, optional
        Write plain files, named as in the store, into this directory (no sidecar,
        no version; ``update="force"`` replaces existing files). Excludes ``root``,
        ``update="upgrade"`` and ``plan`` (``store_only_option``); a command that
        works on a store only refuses it.
    root : str or Path, optional
        The store (default, when ``output_dir`` is not given either: the store root
        of the settings, DEV-19.2).
    update : {"upgrade", "force"}, optional
        The update mode of the function (``None``: local versions are kept).
    plan : UpdatePlan, optional
        The plan of ``check_command`` (its ``result``) for ``update="upgrade"``.
    workers : int, optional
        Parallel transfers (``None``: the default of the function).
    summary : bool
        ``soil hsg`` only: put the statistics of the HSG raster in the report.
    cache : MetadataCache or bool
        As in the library functions (given to the function that takes it).
    on_progress, on_notice : callable, optional
        As in the library functions (``soil`` and ``soil hsg`` take no
        ``on_progress``; a function that takes neither is not given it).

    Raises
    ------
    ValidationError
        As ``validate_command``; ``summary`` for a command that has no such option
        (``option="summary"``); ``update``, ``plan`` or ``workers`` for a command that
        has none of them; and the errors of the function.
    ConflictError
        A plain target that exists without ``update="force"``, a name two files
        share, or a store as ``output_dir``: before the first byte.
    """
    declaration = _declaration(command)
    if summary and not any(param.name == "summary" for param in declaration.params):
        raise ValidationError(
            message(
                "commands.summary_only_for_hsg", summary_command=_summary_commands()
            ),
            option="summary",
        )
    if declaration.kind == "data":
        entry = DATA_COMMANDS[declaration.id]
        arguments = convert_arguments(entry.options, options)
        target = resolve_target(output_dir=output_dir, root=root)
        entry.validate(target.path if target.mode == "store" else Path("."), arguments)
        report = entry.download(
            None if root is None else Path(root),
            arguments,
            output_dir=None if output_dir is None else Path(output_dir),
            update=update,
            plan=plan,
            workers=workers,
            summary=summary,
            cache=cache,
            on_progress=on_progress,
            on_notice=on_notice,
        )
        return wrap(declaration.id, report)
    given = _targets(declaration, output_dir, root)
    given |= {
        name: value
        for name, value in (
            ("update", update),
            ("plan", plan),
            ("workers", workers),
            ("summary", summary),
        )
        if value is not None and value is not False
    }
    arguments = check_call(declaration, options, given)
    function = _function(declaration.function)
    hooks = _hooks(function, cache=cache, on_progress=on_progress, on_notice=on_notice)
    return wrap(declaration.id, function(**arguments, **hooks))


def check_command(
    command: str,
    options: Mapping[str, object],
    *,
    output_dir: str | Path | None = None,
    root: str | Path | None = None,
    force: bool = False,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> CommandResult[UpdatePlan]:
    """Plan a command without effects: the ``check_*`` twin of its function.

    Nothing is downloaded or written: the function that the declaration names as the
    check of the command runs with the options (``check_data``, ``check_collection``,
    ``check_landcover``, ``check_soil`` or ``check_hsg`` for a data command,
    ``check_store`` for ``store init``).
    With ``output_dir`` the plan of a data command lists the targets of a plain write
    (``write``, ``replace`` with ``force``, ``conflict``); ``force`` does nothing for a
    store.

    Parameters
    ----------
    command : str
        A command of the catalog that has a check (``kartograf commands list``:
        ``check``).
    options : Mapping
        The options in the JSON form (``validate_command``).
    output_dir, root : str or Path, optional
        Where the command would write (at most one).
    force : bool
        Plan the replacement of existing plain files.
    cache : MetadataCache or bool
        As in the library functions. The check asks the source for every
        answer the cache holds, except those a ``MetadataCache`` got less than
        its ``refresh_ttl_seconds`` ago (ADR-056): a check of a PL hint right
        after ``check_availability`` of the same area with that cache asks the
        GUGiK index nothing.
    on_notice : callable, optional
        As in the library functions.

    Returns
    -------
    CommandResult
        The envelope ``kartograf-result/1`` with ``check`` true; ``result`` is the plan
        (``kartograf-plan/1``), whose
        ``ok`` is false when a position could not be checked (status ``partial`` or
        ``failed``). A plan that lists a ``conflict`` is ``ok``: only the run fails.

    Raises
    ------
    ValidationError
        As ``validate_command``; a command that has no check (``details.reason``
        ``no_check``).
    """
    declaration = _declaration(command)
    if declaration.check_function is None:
        raise ValidationError(
            message("commands.no_check", command=declaration.id),
            option="check",
            hint=message("commands.no_check_hint"),
            reason="no_check",
        )
    if declaration.kind == "data":
        entry = DATA_COMMANDS[declaration.id]
        arguments = convert_arguments(entry.options, options)
        target = resolve_target(output_dir=output_dir, root=root)
        entry.validate(target.path if target.mode == "store" else Path("."), arguments)
        plan = entry.check(
            None if root is None else Path(root),
            arguments,
            output_dir=None if output_dir is None else Path(output_dir),
            force=force,
            cache=cache,
            on_notice=on_notice,
        )
        return wrap(declaration.id, plan, check=True)
    arguments = check_call(
        declaration, options, _targets(declaration, output_dir, root)
    )
    function = _function(declaration.check_function)
    hooks = _hooks(function, cache=cache, on_notice=on_notice, force=force)
    return wrap(declaration.id, function(**arguments, **hooks), check=True)
