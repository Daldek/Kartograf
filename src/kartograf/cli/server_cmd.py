"""
``kartograf server``: the read-only HTTP server (ADR-063 decision 7).

Outside the command catalog, as ``kartograf-mcp``: it starts a process and AGI-6.1
reserves ``server`` (no catalog group has the name). ``main`` reads ``--host``,
``--port`` and ``--lang``, checks the settings (``check_config``: an unusable
``nogat.toml`` or limit is a ``ConfigError``) and serves
(``kartograf.server.serving.serve``) until Ctrl+C or ``SIGTERM``, then ends with 0. A
failure to start prints an ``Error:`` line and the ``kartograf-error/1`` document as
the last line of stderr (AGI-3.3).
"""

import argparse
import sys
from collections.abc import Sequence
from typing import NoReturn

from kartograf.cli._json import emit_error
from kartograf.cli._language import language
from kartograf.config import LANGUAGES, check_config
from kartograf.error_report import error_report
from kartograf.exceptions import KartografError, UsageError
from kartograf.messages import message
from kartograf.server.serving import DEFAULT_HOST, DEFAULT_PORT, serve

__all__ = ["SERVER_COMMAND", "main", "server_parser"]

SERVER_COMMAND = "server"
"""The first word of ``kartograf server`` (not a catalog group)."""
_MAX_PORT = 65535


class _Parser(argparse.ArgumentParser):
    """A parser whose mistakes are ``UsageError`` (exit 2 with the error document)."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        raise UsageError(message)


def _port(text: str) -> int:
    """Return a TCP port of ``--port``: a whole number from 0 to 65535."""
    if not text.isdigit() or int(text) > _MAX_PORT:
        raise argparse.ArgumentTypeError(message("server.cli_port_invalid", value=text))
    return int(text)


def server_parser() -> argparse.ArgumentParser:
    """Return the parser of ``kartograf server`` in the language of the line."""
    lang = language()
    parser = _Parser(
        prog=f"kartograf {SERVER_COMMAND}",
        description=message("server.cli_description", lang),
        epilog=message("server.cli_epilog", lang),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=message("server.cli_host", lang),
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=DEFAULT_PORT,
        help=message("server.cli_port", lang),
    )
    parser.add_argument(
        "--lang",
        choices=LANGUAGES,
        type=str.lower,
        help=message("catalog.lang_description", lang),
    )
    return parser


def main(argv: Sequence[str]) -> int:
    """Run ``kartograf server`` with the arguments after ``server``.

    Returns
    -------
    int
        0 after a stop by Ctrl+C or ``SIGTERM``; the exit code of the error that kept
        the server from starting (2 for a wrong option or setting, 4 a port in use, 6
        the extra ``server`` missing). ``--help`` ends the process as argparse does.
    """
    try:
        args = server_parser().parse_args(list(argv))
        check_config()
        serve(host=args.host, port=args.port)
    except KartografError as error:
        print(f"Error: {error.localized(language())}", file=sys.stderr)
        return emit_error(error_report(error))
    return 0
