"""
The command layer: a data command as data (spec 8.7; KB-2..KB-5 of Archiwista).

A data command is one of the twelve commands a project task may run
(``elevation download``, ``soil hsg``, ...; the keys of
``kartograf.project.commands.COMMANDS``). This module reads, checks, writes and
runs such a command from its *options*: the JSON form of the task options
(``bbox`` as four numbers with ``bbox_crs``, a path as a text, a per-country
value as a text or ``{"pl": ..., "cz": ...}``, a list as a list, no ``null`` and
no ``false``) - the form of ``tasks[].options`` of a project and of the
arguments of an MCP tool.

``parse_command`` reads a command line with the parser of the command catalog
(the parser of ``kartograf`` itself), ``validate_command`` runs the checks of
the library function without network and without writing, ``format_command``
writes the canonical command line, ``run_command`` and ``check_command`` call
the library function and its ``check_*`` twin.

Examples
--------
>>> from kartograf import format_command, parse_command
>>> call = parse_command("elevation download --product nmt --sheet N-34-130-D-d-2-4"
...                      " --resolution 1m --vertical-crs EVRF2007 -o ./data")
>>> call.options["product"], call.run["output_dir"]
('nmt', './data')
>>> format_command(call.command, call.options, run=call.run)
'kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 \
--resolution 1m --vertical-crs EVRF2007 -o ./data'
"""

import argparse
import functools
import shlex
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kartograf.cache.metadata import MetadataCache
from kartograf.catalog.cliparser import (
    build_parser,
    parse_command_line,
    parsed_options,
    removed_command_error,
)
from kartograf.catalog.commands import declared, declared_commands
from kartograf.catalog.formatting import format_command_line
from kartograf.catalog.kinds import convert_arguments
from kartograf.download.fetch import UpdateMode
from kartograf.download.manager import DownloadProgress
from kartograf.download.plan import UpdatePlan
from kartograf.exceptions import UsageError, ValidationError
from kartograf.notices import Notice
from kartograf.project.commands import data_commands_text, task_command
from kartograf.serialization import Document

# Flags that print and exit: no part of a command that can be called.
_EXITING_FLAGS = ("-h", "--help", "--version")
# The only command with a ``summary`` (statistics of the HSG raster).
_SUMMARY_COMMAND = "soil hsg"


@dataclass(frozen=True)
class CommandCall:
    """A parsed command line.

    Attributes
    ----------
    command : str
        The command id (``elevation download``).
    options : dict
        The task options that the line gave, in the JSON form, in the order of the
        parameters of the command; ``bbox`` always comes with ``bbox_crs``.
    run : dict
        The other flags the line gave, by parameter name (``output_dir``,
        ``upgrade``, ``force``, ``check_updates``, ``plan``, ``workers``,
        ``quiet``, ``json``, ``summary``): a text, a number or ``True``.
    """

    command: str
    options: dict[str, object]
    run: dict[str, object]


@functools.cache
def _parser() -> argparse.ArgumentParser:
    """The parser of ``kartograf`` that raises ``UsageError`` and keeps no
    defaults: a parsed line has the flags that were written and no others."""
    declarations = declared()
    return build_parser(
        declarations.commands,
        declarations.groups,
        usage_errors=True,
        given_only=True,
    )


def _words(tokens: Sequence[str]) -> str | None:
    """The id of the command the first words of a line name, if they do."""
    ids = declared_commands()
    if tokens and tokens[0] in ids:
        return tokens[0]
    if len(tokens) > 1 and f"{tokens[0]} {tokens[1]}" in ids:
        return f"{tokens[0]} {tokens[1]}"
    return None


def _call(parsed: argparse.Namespace) -> CommandCall:
    """A ``CommandCall`` of the namespace of a parsed line."""
    command = declared_commands()[parsed._command_id]
    options, run = parsed_options(command, parsed)
    return CommandCall(command.id, options, run)


def parse_command(argv: Sequence[str] | str) -> CommandCall:
    """Read a command line of a data command with the parser of ``kartograf``.

    The parser is the one of the CLI (the same flags, ``choices`` and messages),
    built from the catalog of the commands; it tells a flag that was written from
    one that was not, so ``options`` and ``run`` hold what the line gave and
    nothing else.

    Parameters
    ----------
    argv : sequence of str or str
        The words after ``kartograf`` (``["elevation", "download", "--product",
        "nmt"]``); a text is split like a shell line (``shlex.split``).

    Returns
    -------
    CommandCall
        The command, its task options (JSON form; ``bbox`` with ``bbox_crs``,
        which is ``EPSG:2180`` when the line gives only ``--bbox``) and the other
        flags of the line.

    Raises
    ------
    UsageError
        A mistake of the line: an unknown command or flag, a flag without its
        value, a value outside the choices of a flag, ``--help``/``--version``,
        a removed command, an empty line, a group without a command.
    ValidationError
        A command that is not a data command (``parse``, ``catalog``,
        ``elevation availability``, ``project ...``; ``option="command"``,
        ``allowed``: the data commands) or a ``--bbox`` that is not four numbers.
    """
    try:
        tokens = shlex.split(argv) if isinstance(argv, str) else list(argv)
    except ValueError as error:
        raise UsageError(f"nieprawidlowy zapis komendy: {error}") from error
    if not tokens:
        raise UsageError(
            f"podaj komende danych (grupa i komenda, np. elevation download): "
            f"{data_commands_text()}"
        )
    removed = removed_command_error(tokens)
    if removed is not None:
        raise UsageError(removed)
    if any(token in _EXITING_FLAGS for token in tokens):
        raise UsageError(
            "--help i --version nie sa czescia komendy danych; opis komendy: "
            "kartograf catalog <grupa> <komenda> --params"
        )
    named = _words(tokens)
    if named is not None:
        task_command(named)  # before the parser asks for the flags of the command
    parsed = parse_command_line(_parser(), tokens)
    command = getattr(parsed, "_command_id", None)
    if command is None:
        group = getattr(parsed, "command", tokens[0])
        raise UsageError(
            f"{group}: podaj komende grupy (komendy danych: {data_commands_text()})"
        )
    task_command(command)
    return _call(parsed)


def validate_command(
    command: str,
    options: Mapping[str, object],
    *,
    output_dir: str | Path | None = None,
) -> None:
    """The checks of the library function of a data command, without network and
    without writing: what the function does before its first request.

    Parameters
    ----------
    command : str
        A data command (``elevation download``).
    options : Mapping
        The task options in the JSON form.
    output_dir : str or Path, optional
        The store; without it the current directory stands in (the checks do not
        open the store). A geometry file is read, as the function reads it.

    Raises
    ------
    ValidationError
        An unknown command or option, a value of a wrong form, or a rule of the
        command (``option`` names the option; ``allowed`` its values).
    """
    entry = task_command(command)
    store = Path(".") if output_dir is None else Path(output_dir)
    entry.validate(store, convert_arguments(entry.options, options))


def format_command(
    command: str,
    options: Mapping[str, object],
    *,
    run: Mapping[str, object] | None = None,
) -> str:
    """The canonical command line of a data command (``kartograf <group>
    <command> <flags>``).

    The flags follow the order of the parameters of the command; ``--bbox-crs`` is
    left out when it is the default of the flag; ``run`` adds the other flags
    (``output_dir`` as ``-o``). ``parse_command`` reads the line back into the
    same command, options and run.

    Raises
    ------
    ValidationError
        An unknown command, an option the command does not have, one in both
        ``options`` and ``run``, or a value of a wrong form.
    """
    entry = task_command(command)
    declaration = declared_commands()[command]
    given_run = {} if run is None else run
    names = {param.name for param in declaration.params}
    for name in (*options, *given_run):
        if name not in names:
            raise ValidationError(
                f"opcja {name!r} nie nalezy do komendy {command}", option=name
            )
    for name in sorted(set(options) & set(given_run)):
        raise ValidationError(
            f"opcja {name!r} podana jako opcja zadania i jako flaga uruchomienia",
            option=name,
        )
    convert_arguments(entry.options, options)
    try:
        return format_command_line(declaration, options, given_run)
    except ValueError as error:
        raise ValidationError(str(error)) from error


def _store(output_dir: str | Path) -> Path:
    if output_dir is None or not str(output_dir):
        raise ValidationError(
            "output_dir wymagane (katalog magazynu)", option="output_dir"
        )
    return Path(output_dir)


def run_command(
    command: str,
    options: Mapping[str, object],
    *,
    output_dir: str | Path,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int | None = None,
    summary: bool = False,
    cache: MetadataCache | bool = True,
    on_progress: Callable[[DownloadProgress], None] | None = None,
    on_notice: Callable[[Notice], None] | None = None,
) -> Document:
    """Run a data command: the library function of the command with the options.

    The options are checked first (``validate_command``); the function is then
    ``download_data``, ``download_collection``, ``download_landcover``,
    ``download_soil`` or ``calculate_hsg``, so the result is what that function
    returns (``kartograf-download/1``).

    Parameters
    ----------
    command : str
        A data command (``elevation download``).
    options : Mapping
        The task options in the JSON form.
    output_dir : str or Path
        The store.
    update : {"upgrade", "force"}, optional
        The update mode of the function (``None``: local versions are kept).
    plan : UpdatePlan, optional
        The plan of ``check_command`` for ``update="upgrade"``.
    workers : int, optional
        Parallel transfers (``None``: the default of the function).
    summary : bool
        ``soil hsg`` only: put the statistics of the HSG raster in the report.
    cache : MetadataCache or bool
        As in the library functions.
    on_progress, on_notice : callable, optional
        As in the library functions (``soil`` and ``soil hsg`` take no
        ``on_progress``).

    Raises
    ------
    ValidationError
        As ``validate_command``; ``summary`` for another command than
        ``soil hsg`` (``option="summary"``); and the errors of the function.
    """
    entry = task_command(command)
    arguments = convert_arguments(entry.options, options)
    if summary and command != _SUMMARY_COMMAND:
        raise ValidationError(
            f"summary dotyczy tylko komendy {_SUMMARY_COMMAND} (statystyki HSG)",
            option="summary",
        )
    store = _store(output_dir)
    entry.validate(store, arguments)
    return entry.download(
        store,
        arguments,
        update=update,
        plan=plan,
        workers=workers,
        summary=summary,
        cache=cache,
        on_progress=on_progress,
        on_notice=on_notice,
    )


def check_command(
    command: str,
    options: Mapping[str, object],
    *,
    output_dir: str | Path,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Check whether the local versions of a data command are up to date,
    without downloading: ``check_data``, ``check_collection``,
    ``check_landcover``, ``check_soil`` or ``check_hsg`` with the options.

    Returns
    -------
    UpdatePlan
        The plan (``kartograf-plan/1``); ``ok`` is false when a position could
        not be checked.

    Raises
    ------
    ValidationError
        As ``validate_command``.
    """
    entry = task_command(command)
    arguments = convert_arguments(entry.options, options)
    store = _store(output_dir)
    entry.validate(store, arguments)
    return entry.check(store, arguments, cache=cache, on_notice=on_notice)
