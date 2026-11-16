"""
The ``--json`` mode of the CLI (spec 6.6, 7.1; AGI-3.2, AGI-3.3).

``json_mode`` tells from the tokens of a command line whether the mode is on; it
is asked before the parsing, so that a mistake of the line itself is reported in
the mode of the line. ``wants_json`` tells it of a parsed command (the handlers
ask it), ``emit_result`` prints the result envelope ``kartograf-result/1`` of
stdout and gives the exit code it stands for (0, 10 or 11). Nothing else is
written to stdout in this mode, and an error writes nothing there: ``emit_error``
puts the error document ``kartograf-error/1`` on the last line of stderr (in both
modes).
"""

import argparse
import sys
from collections.abc import Sequence

from kartograf.envelope import wrap
from kartograf.error_report import ErrorReport, error_line
from kartograf.serialization import Document

JSON_FLAG = "--json"


def json_mode(argv: Sequence[str]) -> bool:
    """Whether ``--json`` is among the tokens of the command line."""
    return JSON_FLAG in argv


def wants_json(args: argparse.Namespace) -> bool:
    """Check whether the parsed command was given ``--json``.

    A bare ``Namespace`` of a unit test has no such flag: text.
    """
    return bool(getattr(args, "json", False))


def command_id(args: argparse.Namespace) -> str:
    """Return the catalog id the parser put on a parsed command (``sheet parse``).

    A bare ``Namespace`` of a unit test has none: the empty text, which is no
    command name.
    """
    return str(getattr(args, "_command_id", ""))


def use_utf8_stdout() -> None:
    """Write the document in UTF-8 whatever the locale of the terminal or pipe."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")


def emit_result(command: str, document: Document, *, check: bool = False) -> int:
    """Print the envelope of ``command`` as the JSON of stdout; return its exit code.

    The envelope is ``wrap(command, document, check=check)``: its status, and so the
    exit code, follows the ``ok`` verdict of the document (0 ``ok``, 10 ``partial``,
    11 ``failed``); the document is printed in every case.
    """
    result = wrap(command, document, check=check)
    sys.stdout.write(result.to_json())
    return result.exit_code


def emit_error(report: ErrorReport) -> int:
    """Write the error document as the last line of stderr; return its exit code.

    The line is ``error_line(report)``, the compact ASCII JSON of ``kartograf-error/1``
    (AGI-3.3); stdout stays empty.
    """
    print(error_line(report), file=sys.stderr, flush=True)
    return report.exit_code
