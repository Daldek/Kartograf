"""Check the ``kartograf ...`` lines that the documents for readers quote."""

import shlex
from pathlib import Path, PurePosixPath

from kartograf import parse_command, validate_command
from kartograf.catalog.cliparser import build_parser, parse_command_line
from kartograf.catalog.commands import declared


def is_absolute_root(root: str) -> bool:
    """Return whether ``root`` is absolute: in the POSIX form the documents quote
    (``/data/kartograf``, which has no drive on Windows) or as a path of this system.
    """
    return PurePosixPath(root).is_absolute() or Path(root).is_absolute()


def check_command_line(line: str) -> None:
    """Parse a ``kartograf ...`` line like the CLI, and validate a data command.

    A data command also needs an absolute ``--root`` and options that pass the
    validation of the library (no network).
    """
    words = shlex.split(line)[1:]
    declarations = declared()
    parser = build_parser(declarations.commands, declarations.groups, usage_errors=True)
    parsed = parse_command_line(parser, words)
    data = {c.id for c in declarations.commands if c.kind == "data"}
    if getattr(parsed, "_command_id", None) in data:
        call = parse_command(words)
        root = call.run.get("root")
        if root is not None:
            assert is_absolute_root(str(root)), line
        validate_command(
            call.command,
            call.options,
            root=None if root is None else str(root),
        )
