"""
``kartograf parse`` command and its formatting helpers.

PL sheet codes (PL-1992, PL-2000) are parsed by ``SheetParser`` (scale,
parts, hierarchy); CZ codes - SM5 sheets, TM33 tiles (``parser_registry``)
and ZTM map sheets - are recognised offline and described: system, CRS
and the commands taking them in ``--sheet``.
"""

import argparse
import sys

from kartograf.core.parser_registry import detect_system, ztm_sheet_system
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import ParseError, ValidationError

_CZ_CODES = (
    "Godla CZ: SM5 (np. CTES96), kafel TM33 (np. 302_5550), ZTM (np. 0510-D-11, "
    "NM-34-07-1-D-15)."
)
_ZTM_CRS = {"sjtsk": "EPSG:5514 (S-JTSK)", "etrs89": "EPSG:3045 (ETRS89 / UTM 33N)"}


def format_cz_sheet(sheet: str) -> str | None:
    """Description of a CZ sheet code (SM5 sheet, TM33 tile, ZTM map sheet);
    ``None`` for any other code (a PL code or an invalid one).

    Raises
    ------
    ParseError
        A TM33 tile code off the 2 km grid.
    """
    system = detect_system(sheet).id
    ztm = ztm_sheet_system(sheet)
    if system == "cz_tm33":
        bbox = ParserTM33(sheet).get_bbox()
        lines = [
            "Uklad:     TM33 (CZ) - kafel 2 x 2 km",
            f"CRS:       {bbox.crs} (ETRS89 / UTM 33N)",
            f"Zasieg:    {bbox.min_x:.0f},{bbox.min_y:.0f},{bbox.max_x:.0f},"
            f"{bbox.max_y:.0f}",
            "Komendy:   --sheet w elevation download i elevation availability",
        ]
    elif system == "cz_sm5":
        lines = [
            "Uklad:     SM5 (CZ) - arkusz Statni mapy 1:5000",
            "CRS:       EPSG:5514 (S-JTSK)",
            "Zasieg:    rama z indeksu arkuszy CUZK (odczyt przy pobraniu)",
            "Komendy:   --sheet w elevation download (takze warstwice), imagery "
            "download i elevation availability",
        ]
    elif ztm is not None:
        lines = [
            f"Uklad:     ZTM (CZ) - arkusz mapy topograficznej (--sheet-system {ztm})",
            f"CRS:       {_ZTM_CRS[ztm]}",
            "Zasieg:    rama z indeksu arkuszy CUZK (odczyt przy pobraniu)",
            "Komendy:   --sheet w maps download --country cz",
        ]
    else:
        return None
    return "\n".join([f"Godlo:     {sheet.strip()}", *lines])


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
        cz = format_cz_sheet(args.sheet)
    except ParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if cz is not None:
        if args.hierarchy or args.children or args.descendants:
            print(
                "Error: --hierarchy, --children i --descendants dotycza tylko "
                "godel PL (PL-1992, PL-2000)",
                file=sys.stderr,
            )
            return 1
        print(cz)
        return 0
    try:
        parser = SheetParser(args.sheet)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e} {_CZ_CODES}", file=sys.stderr)
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
