"""
CLI entry point of Kartograf and a facade of its public names.

``main`` is the entry point (pyproject: kartograf = "kartograf.cli.commands:main").
Commands live in ``_parser`` (``parse``, ``cache``) and in the data groups of
``kartograf/cli/groups/`` (ADR-039), which set the handler of each command;
the translation to the library is in the ``*_cmd`` modules. This module
re-exports public names only (``create_parser``, ``cmd_*``, formatters);
private helpers are imported from the target module (e.g.
``kartograf.cli.download_cmd``).
"""

import argparse
import os
import sys

from kartograf.cli._parser import (
    create_parser,
    parse_command_line,
    removed_command_error,
)
from kartograf.cli.cache_cmd import cmd_cache
from kartograf.cli.download_cmd import cmd_download, create_progress_callback
from kartograf.cli.parse_cmd import (
    cmd_parse,
    format_children,
    format_descendants,
    format_hierarchy,
    format_sheet_info,
)
from kartograf.exceptions import KartografError, ValidationError

__all__ = [
    "create_parser",
    "main",
    "cmd_parse",
    "cmd_download",
    "cmd_cache",
    "create_progress_callback",
    "format_sheet_info",
    "format_hierarchy",
    "format_children",
    "format_descendants",
]


def _dispatch(parser: argparse.ArgumentParser, parsed_args: argparse.Namespace) -> int:
    """Dispatch the parsed arguments to the right command."""
    if parsed_args.command == "parse":
        return cmd_parse(parsed_args)
    if parsed_args.command == "cache" and parsed_args.cache_command is not None:
        return cmd_cache(parsed_args)

    handler = getattr(parsed_args, "_handler", None)
    if handler is None:
        # no command, or a data group without its command: that level's help
        getattr(parsed_args, "_group_parser", parser).print_help()
        return 0
    # --plan needs a mode in every store command
    if getattr(parsed_args, "plan", None) is not None and not (
        parsed_args.check_updates or parsed_args.upgrade
    ):
        raise ValidationError("--plan wymaga --check-updates albo --upgrade")
    return handler(parsed_args)


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
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    argv = sys.argv[1:] if args is None else args
    removed = removed_command_error(argv)
    if removed is not None:
        parser.error(removed)  # exit 2, like any unknown command
    # argparse raises SystemExit for --help/--version - let it pass unchanged
    parsed_args = parse_command_line(parser, argv)

    try:
        return _dispatch(parser, parsed_args)
    except KartografError as e:
        if os.environ.get("KARTOGRAF_DEBUG"):
            raise
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - last-resort barrier for the CLI user
        if os.environ.get("KARTOGRAF_DEBUG"):
            raise
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        print("Ustaw KARTOGRAF_DEBUG=1, aby zobaczyc pelny traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
