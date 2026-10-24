"""
CLI entry point of Kartograf and a facade of its public names.

``main`` is the entry point (pyproject: kartograf = "kartograf.cli.commands:main").
The parser is built from the declarations of the command catalog
(``_parser.create_parser``, ADR-039/ADR-046); ``_handlers.HANDLERS`` maps the id
of the parsed command to its handler, and the translation to the library is in
the ``*_cmd`` modules. This module re-exports public names only
(``create_parser``, ``cmd_*``, formatters); private helpers are imported from
the target module (e.g. ``kartograf.cli.download_cmd``).

Every command except ``config show`` first checks the user settings
(``kartograf.config.check_config``: a ``nogat.toml`` that cannot be used is a
``ConfigError``, exit code 2).

Exit codes come from the shared Nogat registry (``kartograf._errors``): 0 ok, 10
``partial`` and 11 ``failed`` (a result with ``ok: false``: some or no unit
succeeded, the outcomes of ERR §1), and for an error 1 ``internal_error`` (a
program error), 2 ``validation_error`` (argparse, ``ValidationError`` and its
subclasses), 5 ``source_unavailable``, 7 ``data_error``, 8 ``store_unavailable``, 9
``io_error``, 12 ``forbidden``, 13 ``calculation_error``, 14 ``no_data``, 15
``unsupported``, 130 ``cancelled`` (Ctrl-C), 143 ``terminated`` (SIGTERM, handled
like Ctrl-C). With ``--json`` the result is the envelope ``kartograf-result/1`` on
stdout (also for the outcomes 10 and 11). An error writes nothing to stdout: the last
line of stderr is the document ``kartograf-error/1`` in both modes (AGI-3.3).
"""

import argparse
import logging
import sys

from kartograf.cli._handlers import HANDLERS
from kartograf.cli._json import emit_error, json_mode, use_utf8_stdout
from kartograf.cli._parser import (
    create_parser,
    parse_command_line,
    removed_command_error,
)
from kartograf.cli.cache_cmd import cmd_cache
from kartograf.cli.download_cmd import cmd_download, create_progress_callback
from kartograf.cli.parse_cmd import cmd_parse, format_sheet
from kartograf.config import check_config, debug
from kartograf.error_report import error_report
from kartograf.exceptions import KartografError, UsageError, ValidationError
from kartograf.interrupt import sigterm_interrupts

__all__ = [
    "create_parser",
    "main",
    "cmd_parse",
    "cmd_download",
    "cmd_cache",
    "create_progress_callback",
    "format_sheet",
]


def _dispatch(parser: argparse.ArgumentParser, parsed_args: argparse.Namespace) -> int:
    """Dispatch the parsed arguments to the handler of their command."""
    command = getattr(parsed_args, "_command_id", None)
    if command is None:
        # no command, or a group without its command: that level's help on
        # stderr and exit 2, like any other missing argument (a script with a
        # typo must not "pass"); the error document is the last line (AGI-3.3)
        getattr(parsed_args, "_group_parser", parser).print_help(sys.stderr)
        return emit_error(error_report(UsageError("nie podano komendy")))
    if command != _CONFIG_SHOW:  # `config show` reports unusable settings itself
        check_config()
    # --plan needs a mode in every store command
    if getattr(parsed_args, "plan", None) is not None and not (
        parsed_args.check_updates or parsed_args.upgrade
    ):
        raise ValidationError(
            "--plan wymaga --check-updates albo --upgrade", option="plan"
        )
    return HANDLERS[command](parsed_args)


_HTTP_LOGGER = "kartograf.transport.http"
_CONFIG_SHOW = "config show"


class _StderrLines(logging.Handler):
    """Print warning and error records of the library as prefixed lines on stderr.

    The prefixes are ``Warning:`` and ``Error:``; without this handler Python's
    fallback prints them as bare messages.

    ``--json`` keeps stderr empty (USAGE 9.2): of all the records only the
    failed attempts of the HTTP transport (before their retry) pass; the other
    records are diagnostics of the library, and what concerns the result is in
    the document (``notices``, the verdict of the command). ``KARTOGRAF_DEBUG``
    lets every record through.
    """

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.as_json = False

    def emit(self, record: logging.LogRecord) -> None:
        if self.as_json and record.name != _HTTP_LOGGER and not debug():
            return
        prefix = "Error" if record.levelno >= logging.ERROR else "Warning"
        print(f"{prefix}: {record.getMessage()}", file=sys.stderr)


def _stderr_lines(as_json: bool) -> None:
    """Install the handler of the library records and set its mode.

    The handler is installed once per process; the mode is that of this command line.
    """
    log = logging.getLogger("kartograf")
    handler = next((h for h in log.handlers if isinstance(h, _StderrLines)), None)
    if handler is None:
        handler = _StderrLines()
        log.addHandler(handler)
    handler.as_json = as_json


def _fail(
    error: BaseException,
    command: str | None,
    as_json: bool,
    given: dict[str, object] | None = None,
) -> int:
    """Report ``error`` in the mode of the command line.

    The exit code of the error document (ERR §2): ``exit_code`` of a
    ``KartografError``, 9 for ``OSError``, 130 for Ctrl-C, 143 for SIGTERM, 1
    for every other exception.

    The last line of stderr is the document ``kartograf-error/1`` in both modes
    (``given``: the arguments the line gave, for the example of its hint); stdout
    stays empty. Text mode first prints one ``Error:`` line - the message of a
    ``KartografError`` (its hint is not printed twice: the texts of ``hints`` are in
    the message), with the remedy of an unavailable coordinate transformation; any
    other exception with its class and the way to a traceback.
    """
    report = error_report(error, command=command, given=given)
    if as_json:
        return emit_error(report)
    if isinstance(error, KeyboardInterrupt):
        # versions are committed atomically from .incoming/ staging (a stale
        # leftover is removed by a later run): no half-written file is kept
        print(f"Error: {report.message}", file=sys.stderr)
    elif isinstance(error, KartografError):
        remedy = getattr(error, "remedy", None)  # TransformUnavailableError
        text = f"Error: {error}" + (f" Remedium: {remedy}" if remedy else "")
        print(text, file=sys.stderr)
    else:
        print(f"Error: {type(error).__name__}: {error}", file=sys.stderr)
        print("Ustaw KARTOGRAF_DEBUG=1, aby zobaczyc pelny traceback.", file=sys.stderr)
    return emit_error(report)


def main(args: list[str] | None = None) -> int:
    """Run the CLI and return the exit code.

    Parameters
    ----------
    args : list[str], optional
        Command-line arguments (defaults to sys.argv[1:])

    Returns
    -------
    int
        Exit code: 0 ok, 10 partial and 11 failed (a result with ``ok: false``), 1
        ``internal_error``, 2 wrong use or wrong input, another registry code for a
        failure of that kind (5, 7, 8, 9, 12, 13, 14, 15), 130 cancelled (Ctrl-C),
        143 terminated (SIGTERM). ``--help`` and ``--version`` end the process
        (``SystemExit``) as argparse does.
    """
    argv = sys.argv[1:] if args is None else args
    as_json = json_mode(argv)
    _stderr_lines(as_json)
    if as_json:
        use_utf8_stdout()
    command: str | None = None
    given: dict[str, object] | None = None
    with sigterm_interrupts():
        try:
            parser = create_parser(usage_errors=as_json)
            removed = removed_command_error(argv)
            if removed is not None:
                parser.error(removed)  # exit 2, like any unknown command
            # argparse raises SystemExit for --help/--version - let it pass unchanged
            parsed_args = parse_command_line(parser, argv)
            command = getattr(parsed_args, "_command_id", None)
            given = dict(vars(parsed_args))
            return _dispatch(parser, parsed_args)
        except KeyboardInterrupt as e:
            return _fail(e, command, as_json)
        except Exception as e:  # noqa: BLE001 - last-resort barrier for the CLI user
            if debug():
                raise
            return _fail(e, command, as_json, given)


if __name__ == "__main__":
    sys.exit(main())
