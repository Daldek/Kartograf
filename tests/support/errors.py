"""Read the error document on the last line of stderr (AGI-3.3, ERR-4)."""

import json
from typing import Any

from kartograf.messages import localize, reason

SCHEMA = "kartograf-error/1"


def _document(line: str) -> dict[str, Any] | None:
    """Return the ``kartograf-error/1`` document a line holds, else ``None``."""
    try:
        document = json.loads(line)
    except ValueError:
        return None
    if isinstance(document, dict) and document.get("schema") == SCHEMA:
        return document
    return None


def error_document(stderr: str) -> dict[str, Any]:
    """Return the error document on the last line of ``stderr``.

    Fails when the last line is no ``kartograf-error/1`` document.
    """
    lines = stderr.splitlines()
    document = _document(lines[-1]) if lines else None
    assert document is not None, (
        f"no error document on the last stderr line: {lines[-1:]}"
    )
    return document


def without_error_document(stderr: str) -> str:
    """Return ``stderr`` without its last line when that is the error document.

    What the human lines of an error say (``Error: ...``) apart from the document
    that follows them.
    """
    lines = stderr.splitlines(keepends=True)
    if lines and _document(lines[-1]) is not None:
        return "".join(lines[:-1])
    return stderr


def error_line(error: BaseException) -> str:
    """Return the ``Error:`` line the CLI prints for ``error`` on a Polish command line.

    The catalog text of the error in Polish, its Polish letters folded for the terminal
    and its values as they are (``cli._language.localized``).
    """
    return f"Error: {localize(reason(error), 'pl', folded=True)}"
