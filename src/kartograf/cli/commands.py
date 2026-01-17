"""
Command-line interface for Kartograf.

This module provides CLI commands for parsing map sheet identifiers
and displaying hierarchy information.
"""

import argparse
import sys
from typing import Optional

from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import ParseError, ValidationError


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="kartograf",
        description="Tool for parsing and downloading Polish topographic map sheets",
        epilog="Example: kartograf parse N-34-130-D --hierarchy",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Parse command
    parse_parser = subparsers.add_parser(
        "parse",
        help="Parse and display information about a map sheet",
        description="Parse a map sheet identifier (godlo) and display its properties",
    )
    parse_parser.add_argument(
        "godlo",
        help="Map sheet identifier (e.g., N-34-130-D, N-34-130-D-d-2-4)",
    )
    parse_parser.add_argument(
        "--hierarchy",
        action="store_true",
        help="Display the full hierarchy from this sheet up to 1:1000000",
    )
    parse_parser.add_argument(
        "--children",
        action="store_true",
        help="Display direct children of this sheet",
    )
    parse_parser.add_argument(
        "--descendants",
        metavar="SCALE",
        help="Display all descendants to target scale (e.g., 1:10000)",
    )

    return parser


def format_sheet_info(parser: SheetParser) -> str:
    """
    Format sheet information for display.

    Parameters
    ----------
    parser : SheetParser
        Parsed sheet

    Returns
    -------
    str
        Formatted information string
    """
    lines = [
        f"Sheet:     {parser.godlo}",
        f"Scale:     {parser.scale}",
        f"Layout:    {parser.uklad}",
        "Components:",
    ]

    for name, value in parser.components.items():
        lines.append(f"  {name}: {value}")

    return "\n".join(lines)


def format_hierarchy(parser: SheetParser) -> str:
    """
    Format hierarchy information for display.

    Parameters
    ----------
    parser : SheetParser
        Starting sheet

    Returns
    -------
    str
        Formatted hierarchy string
    """
    hierarchy = parser.get_hierarchy_up()
    lines = ["Hierarchy (from current to 1:1000000):", ""]

    for i, sheet in enumerate(hierarchy):
        indent = "  " * i
        arrow = "└─ " if i > 0 else ""
        lines.append(f"{indent}{arrow}{sheet.godlo} ({sheet.scale})")

    return "\n".join(lines)


def format_children(parser: SheetParser) -> str:
    """
    Format children information for display.

    Parameters
    ----------
    parser : SheetParser
        Parent sheet

    Returns
    -------
    str
        Formatted children string
    """
    children = parser.get_children()

    if not children:
        return f"Sheet {parser.godlo} has no children (already at finest scale 1:10000)"

    lines = [
        f"Children of {parser.godlo} ({len(children)} sheets):",
        "",
    ]

    for child in children:
        lines.append(f"  {child.godlo} ({child.scale})")

    return "\n".join(lines)


def format_descendants(parser: SheetParser, target_scale: str) -> str:
    """
    Format descendants information for display.

    Parameters
    ----------
    parser : SheetParser
        Starting sheet
    target_scale : str
        Target scale

    Returns
    -------
    str
        Formatted descendants string
    """
    descendants = parser.get_all_descendants(target_scale)

    lines = [
        f"Descendants of {parser.godlo} to {target_scale} ({len(descendants)} sheets):",
        "",
    ]

    # Group by intermediate scales if there are many
    if len(descendants) <= 20:
        for desc in descendants:
            lines.append(f"  {desc.godlo}")
    else:
        # Just show count and first/last few
        lines.append(f"  {descendants[0].godlo}")
        lines.append(f"  {descendants[1].godlo}")
        lines.append("  ...")
        lines.append(f"  {descendants[-2].godlo}")
        lines.append(f"  {descendants[-1].godlo}")

    return "\n".join(lines)


def cmd_parse(args: argparse.Namespace) -> int:
    """
    Execute the parse command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    try:
        parser = SheetParser(args.godlo)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Always show basic info
    print(format_sheet_info(parser))

    # Show hierarchy if requested
    if args.hierarchy:
        print()
        print(format_hierarchy(parser))

    # Show children if requested
    if args.children:
        print()
        print(format_children(parser))

    # Show descendants if requested
    if args.descendants:
        try:
            print()
            print(format_descendants(parser, args.descendants))
        except ValidationError as e:
            print(f"\nError: {e}", file=sys.stderr)
            return 1

    return 0


def main(args: Optional[list[str]] = None) -> int:
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
    parsed_args = parser.parse_args(args)

    if parsed_args.command is None:
        parser.print_help()
        return 0

    if parsed_args.command == "parse":
        return cmd_parse(parsed_args)

    # Unknown command (shouldn't happen with argparse)
    print(f"Unknown command: {parsed_args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
