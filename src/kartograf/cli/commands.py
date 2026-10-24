"""
CLI entry point of Kartograf and a facade of its public names.

``main`` is the entry point (pyproject: kartograf = "kartograf.cli.commands:main").
The parser is built from the declarations of the command catalog
(``_parser.create_parser``, ADR-039/ADR-046); ``_handlers.HANDLERS`` maps the id
of the parsed command to its handler, and the translation to the library is in
the ``*_cmd`` modules. This module re-exports public names only
(``create_parser``, ``cmd_*``, formatters); private helpers are imported from
the target module (e.g. ``kartograf.cli.download_cmd``).

Exit codes (one table, spec 6.5): 0 ok, 1 failed (a source, the network, the
cache, a program error, or a result with ``ok: false``), 2 wrong use or wrong
input (argparse, ``ValidationError`` and its subclasses), 130 interrupted
(Ctrl-C), 143 terminated (SIGTERM, handled like Ctrl-C). With
``--json`` every error is the document ``kartograf-error/1`` on stdout and
stderr stays empty.
"""

import argparse
import logging
import os
import sys

from kartograf.cli._handlers import HANDLERS
from kartograf.cli._json import emit_document, json_mode, use_utf8_stdout
from kartograf.cli._parser import (
    create_parser,
    parse_command_line,
    removed_command_error,
)
from kartograf.cli.cache_cmd import cmd_cache
from kartograf.cli.download_cmd import cmd_download, create_progress_callback
from kartograf.cli.parse_cmd import cmd_parse, format_sheet
from kartograf.error_report import error_report
from kartograf.exceptions import KartografError, ValidationError
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
        # typo must not "pass")
        getattr(parsed_args, "_group_parser", parser).print_help(sys.stderr)
        return 2
    # --plan needs a mode in every store command
    if getattr(parsed_args, "plan", None) is not None and not (
        parsed_args.check_updates or parsed_args.upgrade
    ):
        raise ValidationError(
            "--plan wymaga --check-updates albo --upgrade", option="plan"
        )
    return HANDLERS[command](parsed_args)


_HTTP_LOGGER = "kartograf.transport.http"


class _StderrLines(logging.Handler):
    """Warning and error records of the library as prefixed lines on the
    current stderr (``Warning:``/``Error:``); without this handler Python's
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
        if (
            self.as_json
            and record.name != _HTTP_LOGGER
            and not os.environ.get("KARTOGRAF_DEBUG")
        ):
            return
        prefix = "Error" if record.levelno >= logging.ERROR else "Warning"
        print(f"{prefix}: {record.getMessage()}", file=sys.stderr)


def _stderr_lines(as_json: bool) -> None:
    """Install (once per process) the handler of the library records and set its
    mode for this command line."""
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
    """Report ``error`` in the mode of the command line; the exit code of the
    error table (spec 6.2): ``exit_code`` of a ``KartografError``, 130 for Ctrl-C,
    143 for SIGTERM, 1 for every other exception.

    ``--json``: the document ``kartograf-error/1`` on stdout (``given``: the
    arguments the line gave, for the example of its hint). Text: one
    ``Error:`` line on stderr - the message of a ``KartografError`` (its hint is
    not printed twice: the texts of ``hints`` are in the message), with the
    remedy of an unavailable coordinate transformation; any other exception
    with its class and the way to a traceback.
    """
    if as_json:
        return emit_document(error_report(error, command=command, given=given))
    if isinstance(error, KeyboardInterrupt):
        # versions are committed atomically from .incoming/ staging (a stale
        # leftover is removed by a later run): no half-written file is kept
        report = error_report(error)
        print(f"Error: {report.message}", file=sys.stderr)
        return report.exit_code
    if isinstance(error, KartografError):
        remedy = getattr(error, "remedy", None)  # TransformUnavailableError
        text = f"Error: {error}" + (f" Remedium: {remedy}" if remedy else "")
        print(text, file=sys.stderr)
        return error.exit_code
    print(f"Error: {type(error).__name__}: {error}", file=sys.stderr)
    print("Ustaw KARTOGRAF_DEBUG=1, aby zobaczyc pelny traceback.", file=sys.stderr)
    return 1


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for the CLI.

    Parameters
    ----------
    args : list[str], optional
        Command-line arguments (defaults to sys.argv[1:])

    Returns
    -------
    int
        Exit code: 0 ok, 1 failed (or a result with ``ok: false``), 2 wrong
        use or wrong input, 130 interrupted (Ctrl-C), 143 terminated (SIGTERM).
        ``--help`` and ``--version`` end the process (``SystemExit``) as argparse
        does.
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
            if os.environ.get("KARTOGRAF_DEBUG"):
                raise
            return _fail(e, command, as_json, given)


if __name__ == "__main__":
    sys.exit(main())
