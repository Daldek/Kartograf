"""
``kartograf sheet parse`` and ``sheet find``: the sheet functions as text or documents.

The library says what a sheet code is (``describe_sheet``: PL-1992 and PL-2000
codes - scale, parts, hierarchy; CZ codes - SM5 sheets, TM33 tiles and ZTM map
sheets - system, CRS and the commands that take them, all offline). The CLI
renders that document as text, or with ``--json`` prints it
(``kartograf-sheet/1``). A wrong code or option is the ``ParseError`` or
``ValidationError`` of the library that ``main`` reports (exit code 2).

``sheet find`` is ``find_sheets``: the sheet codes that cover a ``--bbox`` or the
features of a ``--geometry`` file (``kartograf-sheets/1``), one code per line in the
text.
"""

import argparse
from collections.abc import Sequence

from kartograf.catalog.commands import declared_commands
from kartograf.catalog.kinds import parse_bbox_arg
from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import language, localized
from kartograf.messages import message
from kartograf.sheet_info import (
    SheetDescendants,
    SheetInfo,
    SheetLevel,
    SheetList,
    describe_sheet,
    find_sheets,
)

# Longer lists of descendants are shortened in the text (the document has all).
_DESCENDANTS_SHOWN = 20
# What the line ``Commands:`` adds after the name of a command for a system. Which
# commands take the code is the document's (``SheetInfo.commands``).
_CZ_NOTES = {
    ("cz_sm5", "elevation download"): message("cli.note_also_contours"),
    ("cz_ztm", "maps download"): " --country cz",
}
_CRS_NAMES = {"EPSG:5514": "S-JTSK", "EPSG:3045": "ETRS89 / UTM 33N"}


def _cz_system(info: SheetInfo) -> str:
    """Return the wording of the line ``System:`` of a CZ system."""
    if info.system == "cz_tm33":
        return message("cli.system_cz_tm33", lang=language())
    if info.system == "cz_sm5":
        return message("cli.system_cz_sm5", lang=language())
    return message("cli.system_cz_ztm", lang=language(), sheet_system=info.sheet_system)


def _commands_text(info: SheetInfo) -> str:
    """Return ``--sheet in <commands>``.

    The commands that take the code, from the document (the commands that download
    first, then the report; each with its note).
    """
    ordered = sorted(
        info.commands, key=lambda command: declared_commands()[command].kind != "data"
    )
    names = [
        command + localized(_CZ_NOTES.get((info.system, command), ""))
        for command in ordered
    ]
    listed = (
        names[0]
        if len(names) == 1
        else message(
            "cli.commands_and",
            lang=language(),
            head=", ".join(names[:-1]),
            last=names[-1],
        )
    )
    return message("cli.sheet_in_commands", lang=language(), commands=listed)


def _format_cz(info: SheetInfo) -> str:
    """Return a CZ code.

    The system, CRS and extent (the frame of an SM5 or ZTM sheet is in the CUZK index,
    read at the download) and the commands.
    """
    system = _cz_system(info)
    extent: str
    if info.bounds is None:
        extent = message("cli.extent_from_cuzk_index", lang=language())
    else:
        b = info.bounds
        extent = f"{b.min_x:.0f},{b.min_y:.0f},{b.max_x:.0f},{b.max_y:.0f}"
    return "\n".join(
        [
            message("cli.label_sheet_code", lang=language(), sheet=info.sheet),
            message("cli.label_system", lang=language(), system=system),
            f"CRS:       {info.crs} ({_CRS_NAMES[info.crs]})",
            message("cli.label_extent", lang=language(), extent=extent),
            message(
                "cli.label_commands",
                lang=language(),
                commands_text=_commands_text(info),
            ),
        ]
    )


def _format_basics(info: SheetInfo) -> str:
    """Return a PL code.

    The sheet, scale, system and parts (PL-2000 also the zone and the native CRS).
    """
    lines: list[str] = [
        message("cli.label_sheet_code", lang=language(), sheet=info.sheet),
        message("cli.label_scale", lang=language(), scale=info.scale),
        message("cli.label_system", lang=language(), system=info.sheet_system),
        message("cli.label_components", lang=language()),
    ]
    for name, value in (info.components or {}).items():
        lines.append(f"  {name}: {value}")
    if info.zone is not None:
        lines.append(message("cli.label_zone", lang=language(), zone=info.zone))
        lines.append(message("cli.label_native_crs", lang=language(), crs=info.crs))
    return "\n".join(lines)


def _format_hierarchy(sheet_scale: str | None, levels: Sequence[SheetLevel]) -> str:
    top_scale = levels[-1].scale if levels else sheet_scale
    lines = [message("cli.hierarchy_header", lang=language(), top_scale=top_scale), ""]
    for i, level in enumerate(levels):
        arrow = "`- " if i > 0 else ""
        lines.append(f"{'  ' * i}{arrow}{level.sheet} ({level.scale})")
    return "\n".join(lines)


def _format_children(info: SheetInfo, children: Sequence[SheetLevel]) -> str:
    if not children:
        return message(
            "cli.no_child_sheets", lang=language(), sheet=info.sheet, scale=info.scale
        )
    lines = [
        message(
            "cli.child_sheets_header",
            lang=language(),
            sheet=info.sheet,
            children_count=len(children),
        ),
        "",
    ]
    lines.extend(f"  {child.sheet} ({child.scale})" for child in children)
    return "\n".join(lines)


def _format_descendants(sheet: str, found: SheetDescendants) -> str:
    lines = [
        message(
            "cli.descendant_sheets_header",
            lang=language(),
            sheet=sheet,
            scale=found.scale,
            count=found.count,
        ),
        "",
    ]
    sheets = found.sheets
    if len(sheets) > _DESCENDANTS_SHOWN:
        # the first and the last two: the count is in the header
        sheets = (sheets[0], sheets[1], "...", sheets[-2], sheets[-1])
    lines.extend(f"  {code}" for code in sheets)
    return "\n".join(lines)


def format_sheet(info: SheetInfo) -> str:
    """Return the text of ``kartograf sheet parse`` from the document.

    What the code is and, for a PL code, the hierarchy, children and descendants the
    document has (each block after a blank line).
    """
    if info.country == "CZ":
        return _format_cz(info)
    blocks = [_format_basics(info)]
    if info.hierarchy is not None:
        blocks.append(_format_hierarchy(info.scale, info.hierarchy))
    if info.children is not None:
        blocks.append(_format_children(info, info.children))
    if info.descendants is not None:
        blocks.append(_format_descendants(info.sheet, info.descendants))
    return "\n\n".join(blocks)


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
        Exit code (0 for success); a wrong sheet code or option is the
        ``ParseError``/``ValidationError`` ``main`` reports (exit code 2).
    """
    info = describe_sheet(
        args.sheet,
        hierarchy=args.hierarchy,
        children=args.children,
        descendants=args.descendants or None,
    )
    if wants_json(args):
        return emit_result(command_id(args), info)
    print(format_sheet(info))
    return 0


def format_sheets(found: SheetList) -> str:
    """Return the text of ``kartograf sheet find`` from the document.

    A header with the system, scale and number of the sheets, then one code per line.
    """
    request = found.request
    system = f"PL-{request.sheet_system}"
    header = message(
        "cli.sheets_list_header",
        lang=language(),
        system=system,
        scale=request.scale,
        count=found.count,
    )
    return "\n".join([header, "", *(f"  {code}" for code in found.sheets)])


def cmd_find_sheets(args: argparse.Namespace) -> int:
    """
    Execute the ``sheet find`` command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success); a wrong area, scale or sheet system is the
        ``ValidationError`` of the library that ``main`` reports (exit code 2).
    """
    found = find_sheets(
        bbox=parse_bbox_arg(args.bbox, args.bbox_crs) if args.bbox else None,
        geometry=args.geometry,
        layer=args.layer,
        scale=args.scale,
        sheet_system=args.sheet_system,
    )
    if wants_json(args):
        return emit_result(command_id(args), found)
    print(format_sheets(found))
    return 0
