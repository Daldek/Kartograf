"""
Top-level parser of the Kartograf CLI (ADR-039, ADR-046).

The commands, flags, sections and examples are declared once, in
``kartograf.catalog.commands`` (one module per group); the argparse tree is built
from them by ``kartograf.catalog.cliparser``. This module is the CLI's view of
that parser: ``create_parser`` and the helpers the entry point and the tests of
the CLI use.
"""

import argparse

from kartograf.catalog.cliparser import (
    _subparsers,
    build_parser,
    parse_command_line,
    removed_command_error,
)
from kartograf.catalog.commands import declared

__all__ = [
    "_subparsers",
    "create_parser",
    "parse_command_line",
    "removed_command_error",
]


def create_parser(*, usage_errors: bool = False) -> argparse.ArgumentParser:
    """
    Create the argument parser of ``kartograf`` from the declared commands.

    Parameters
    ----------
    usage_errors : bool
        Raise ``UsageError`` for a mistake of the command line instead of
        printing ``usage:`` and exiting with 2 (the ``--json`` mode).

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser
    """
    declarations = declared()
    return build_parser(
        declarations.commands, declarations.groups, usage_errors=usage_errors
    )
