"""
The ``--json`` mode of the CLI (spec 6.6, 7.1).

``json_mode`` tells from the tokens of a command line whether the mode is on; it
is asked before the parsing, so that a mistake of the line itself is reported in
the mode of the line. ``wants_json`` tells it of a parsed command (the handlers
ask it), ``emit_document`` prints the one document of stdout and gives the exit
code it stands for. Nothing else is written to stdout in this mode.
"""

import argparse
import sys
from collections.abc import Sequence

from kartograf.error_report import ErrorReport
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


def use_utf8_stdout() -> None:
    """Write the document in UTF-8 whatever the locale of the terminal or pipe."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")


def emit_document(document: Document) -> int:
    """Print ``document`` as the JSON of stdout; return its exit code.

    The code is the ``exit_code`` of an error document (``kartograf-error/1``);
    for a result it is 0 when the document has no ``ok`` or ``ok`` is true, and
    1 when ``ok`` is false (the document is printed in both cases).
    """
    sys.stdout.write(document.to_json())
    if isinstance(document, ErrorReport):
        return document.exit_code
    return 0 if getattr(document, "ok", True) else 1
