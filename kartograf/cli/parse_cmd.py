"""
``kartograf parse`` command and its formatting helpers.
"""

import argparse
import sys

from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import ParseError, ValidationError


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
        f"Godlo:     {parser.sheet}",
        f"Skala:     {parser.scale}",
        f"Uklad:     {parser.sheet_system}",
        "Czlony:",
    ]

    for name, value in parser.components.items():
        lines.append(f"  {name}: {value}")

    if parser.sheet_system == "2000":
        from kartograf.core.parser_2000 import ZONE_EPSG

        zone = int(parser.components["strefa"])
        lines.append(f"  Strefa: {zone}")
        lines.append(f"  Natywny CRS: {ZONE_EPSG[zone]}")

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
    top_scale = hierarchy[-1].scale if hierarchy else parser.scale
    lines = [f"Hierarchia (od arkusza do {top_scale}):", ""]

    for i, level in enumerate(hierarchy):
        indent = "  " * i
        arrow = "`- " if i > 0 else ""
        lines.append(f"{indent}{arrow}{level.sheet} ({level.scale})")

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
        return (
            f"Arkusz {parser.sheet} nie ma arkuszy potomnych "
            f"(najdokladniejsza skala {parser.scale})"
        )

    lines = [
        f"Arkusze potomne {parser.sheet} ({len(children)}):",
        "",
    ]

    for child in children:
        lines.append(f"  {child.sheet} ({child.scale})")

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
        f"Arkusze potomne {parser.sheet} do skali {target_scale} ({len(descendants)}):",
        "",
    ]

    # Group by intermediate scales if there are many
    if len(descendants) <= 20:
        for desc in descendants:
            lines.append(f"  {desc.sheet}")
    else:
        # Just show count and first/last few
        lines.append(f"  {descendants[0].sheet}")
        lines.append(f"  {descendants[1].sheet}")
        lines.append("  ...")
        lines.append(f"  {descendants[-2].sheet}")
        lines.append(f"  {descendants[-1].sheet}")

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
        parser = SheetParser(args.sheet)
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
