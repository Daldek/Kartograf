"""
``kartograf parse``: ``describe_sheet`` as text, or as its document.

The library says what a sheet code is (``describe_sheet``: PL-1992 and PL-2000
codes - scale, parts, hierarchy; CZ codes - SM5 sheets, TM33 tiles and ZTM map
sheets - system, CRS and the commands that take them, all offline). The CLI
renders that document as text, or with ``--json`` prints it
(``kartograf-sheet/1``). A wrong code or option is the ``ParseError`` or
``ValidationError`` of the library that ``main`` reports (exit code 2).
"""

import argparse
from collections.abc import Sequence

from kartograf.catalog.commands import declared_commands
from kartograf.cli._json import emit_document, wants_json
from kartograf.sheet_info import (
    SheetDescendants,
    SheetInfo,
    SheetLevel,
    describe_sheet,
)

# Longer lists of descendants are shortened in the text (the document has all).
_DESCENDANTS_SHOWN = 20
# The wording of the line ``Uklad:`` of each CZ system.
_CZ_SYSTEM = {
    "cz_tm33": "TM33 (CZ) - kafel 2 x 2 km",
    "cz_sm5": "SM5 (CZ) - arkusz Statni mapy 1:5000",
    "cz_ztm": "ZTM (CZ) - arkusz mapy topograficznej (--sheet-system {sheet_system})",
}
# What the line ``Komendy:`` adds after the name of a command for a system. Which
# commands take the code is the document's (``SheetInfo.commands``).
_CZ_NOTES = {
    ("cz_sm5", "elevation download"): " (takze warstwice)",
    ("cz_ztm", "maps download"): " --country cz",
}
_CRS_NAMES = {"EPSG:5514": "S-JTSK", "EPSG:3045": "ETRS89 / UTM 33N"}


def _commands_text(info: SheetInfo) -> str:
    """``--sheet w <komendy>``: the commands that take the code, from the document
    (the commands that download first, then the report; each with its note)."""
    ordered = sorted(
        info.commands, key=lambda command: declared_commands()[command].kind != "data"
    )
    names = [command + _CZ_NOTES.get((info.system, command), "") for command in ordered]
    listed = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} i {names[-1]}"
    return f"--sheet w {listed}"


def _format_cz(info: SheetInfo) -> str:
    """A CZ code: the system, CRS and extent (the frame of an SM5 or ZTM sheet is
    in the CUZK index, read at the download) and the commands."""
    system = _CZ_SYSTEM[info.system].format(sheet_system=info.sheet_system)
    if info.bounds is None:
        extent = "rama z indeksu arkuszy CUZK (odczyt przy pobraniu)"
    else:
        b = info.bounds
        extent = f"{b.min_x:.0f},{b.min_y:.0f},{b.max_x:.0f},{b.max_y:.0f}"
    return "\n".join(
        [
            f"Godlo:     {info.sheet}",
            f"Uklad:     {system}",
            f"CRS:       {info.crs} ({_CRS_NAMES[info.crs]})",
            f"Zasieg:    {extent}",
            f"Komendy:   {_commands_text(info)}",
        ]
    )


def _format_basics(info: SheetInfo) -> str:
    """A PL code: the sheet, scale, system and parts (PL-2000 also the zone and
    the native CRS)."""
    lines = [
        f"Godlo:     {info.sheet}",
        f"Skala:     {info.scale}",
        f"Uklad:     {info.sheet_system}",
        "Czlony:",
    ]
    for name, value in (info.components or {}).items():
        lines.append(f"  {name}: {value}")
    if info.zone is not None:
        lines.append(f"  Strefa: {info.zone}")
        lines.append(f"  Natywny CRS: {info.crs}")
    return "\n".join(lines)


def _format_hierarchy(sheet_scale: str | None, levels: Sequence[SheetLevel]) -> str:
    top_scale = levels[-1].scale if levels else sheet_scale
    lines = [f"Hierarchia (od arkusza do {top_scale}):", ""]
    for i, level in enumerate(levels):
        arrow = "`- " if i > 0 else ""
        lines.append(f"{'  ' * i}{arrow}{level.sheet} ({level.scale})")
    return "\n".join(lines)


def _format_children(info: SheetInfo, children: Sequence[SheetLevel]) -> str:
    if not children:
        return (
            f"Arkusz {info.sheet} nie ma arkuszy potomnych "
            f"(najdokladniejsza skala {info.scale})"
        )
    lines = [f"Arkusze potomne {info.sheet} ({len(children)}):", ""]
    lines.extend(f"  {child.sheet} ({child.scale})" for child in children)
    return "\n".join(lines)


def _format_descendants(sheet: str, found: SheetDescendants) -> str:
    lines = [f"Arkusze potomne {sheet} do skali {found.scale} ({found.count}):", ""]
    sheets = found.sheets
    if len(sheets) > _DESCENDANTS_SHOWN:
        # the first and the last two: the count is in the header
        sheets = (sheets[0], sheets[1], "...", sheets[-2], sheets[-1])
    lines.extend(f"  {code}" for code in sheets)
    return "\n".join(lines)


def format_sheet(info: SheetInfo) -> str:
    """The text of ``kartograf parse`` from the document: what the code is and, for
    a PL code, the hierarchy, children and descendants the document has (each
    block after a blank line)."""
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
        return emit_document(info)
    print(format_sheet(info))
    return 0
