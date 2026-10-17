"""
Registry of sheet code systems: pl2000, cz_tm33, cz_sm5 and the pl1992 fallback.

The single source of truth for recognising the system from a sheet code
(``detect_system``), for splitting a sheet code into ``FileStorage``
directories (``path_parts``) and for the CZ sheet code patterns
(``CZ_TM33_PATTERN``, ``CZ_SM5_PATTERN`` - imported by ``core.parser_tm33``
and ``providers.cuzk.sheets``). Whitespace around the sheet code is stripped
in every function (consistent with the parsers).

The registry is the ``SYSTEMS`` literal (order = detection priority); the
module imports nothing from ``kartograf``, so there are no cycles with the
parsers.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

# Sheet code patterns use [0-9], not \d: \d also matches non-ASCII digits (P5).
# TM33 tile sheet code `{E_km}_{N_km}` (groups: E and N kilometres of the SW corner).
CZ_TM33_PATTERN = re.compile(r"^([0-9]{3})_([0-9]{4})$")
# SM5 sheet code (MAPNOM): 4 uppercase letters (2 for As - the 99 sheets AS22
# ... AS94 of the 16 299 in the SM5 index) + 2 digits, e.g. CTES96, AS91.
CZ_SM5_PATTERN = re.compile(r"^[A-Z]{2}(?:[A-Z]{2})?[0-9]{2}$")
_PL2000_PATTERN = re.compile(r"^[5-8]\.[0-9]")


@dataclass(frozen=True)
class SheetSystem:
    """Description of a single sheet coding system."""

    id: str  # "pl1992", "pl2000", "cz_tm33", "cz_sm5"
    name: str  # in messages: "PL-1992", "PL-2000", "TM33", "SM5"
    country: str
    detect: Callable[[str], bool]  # receives the sheet code without whitespace
    path_parts: Callable[[str], list[str]]  # path parts for FileStorage


def _pl2000_path_parts(sheet: str) -> list[str]:
    # PL-2000: split on dots, use all parts as directory hierarchy
    return sheet.split(".")


def _pl1992_path_parts(sheet: str) -> list[str]:
    # PL-1992: split on dashes, first two parts form the base (e.g. N-34).
    # Identifiers without a dash (e.g. opaque non-PL raw identifiers routed
    # through the fallback system) are used as a single directory part.
    parts = sheet.split("-")
    if len(parts) < 2:
        return parts
    dir_parts = [f"{parts[0]}-{parts[1]}"]
    for part in parts[2:]:
        dir_parts.append(part)
    return dir_parts


SYSTEMS: tuple[SheetSystem, ...] = (
    SheetSystem(
        id="pl2000",
        name="PL-2000",
        country="PL",
        detect=lambda sheet: bool(_PL2000_PATTERN.match(sheet)),
        path_parts=_pl2000_path_parts,
    ),
    SheetSystem(
        id="cz_tm33",
        name="TM33",
        country="CZ",
        detect=lambda sheet: bool(CZ_TM33_PATTERN.match(sheet)),
        path_parts=lambda sheet: sheet.split("_"),
    ),
    SheetSystem(
        id="cz_sm5",
        name="SM5",
        country="CZ",
        detect=lambda sheet: bool(CZ_SM5_PATTERN.match(sheet)),
        path_parts=lambda sheet: [sheet[:-2], sheet[-2:]],
    ),
    SheetSystem(
        id="pl1992",
        name="PL-1992",
        country="PL",
        detect=lambda sheet: True,  # fallback - always last
        path_parts=_pl1992_path_parts,
    ),
)


def detect_system(sheet: str) -> SheetSystem:
    """
    First system (in ``SYSTEMS`` order) whose ``detect`` matches.

    The sheet code is stripped of whitespace. Never returns ``None``:
    ``pl1992`` is the fallback for any identifier (including an invalid one -
    validation is done by the system's parser).
    """
    cleaned = sheet.strip()
    return next(s for s in SYSTEMS if s.detect(cleaned))


def path_parts(sheet: str) -> list[str]:
    """Directory path parts for a sheet code (whitespace stripped), by system."""
    cleaned = sheet.strip()
    return detect_system(cleaned).path_parts(cleaned)


# 1:1 000 000 sheet of an ETRS89 map sheet code of CUZK: letters before the
# first hyphen ("NM" of "NM-34-07-1-D-15").
_IMW_ROW = re.compile(r"[A-Za-z]+")


def cuzk_map_path_parts(mapnom: str) -> list[str]:
    """Directory path parts of a CUZK map sheet code (``MAPNOM`` of a
    ``KladyMapovychListu`` layer: the ZTM sheets), whitespace stripped.

    The same hierarchy as every sheet code (ADR-044 D7): each part between
    hyphens is a directory, an ETRS89 code keeps its 1:1 000 000 sheet in one
    directory as PL-1992 does (``N-34``): ``0510-D-11`` -> ``0510/D/11``,
    ``NM-34-07-1-D-15`` -> ``NM-34/07/1/D/15``, ``0607`` -> ``0607``.
    """
    parts = mapnom.strip().split("-")
    if len(parts) > 1 and _IMW_ROW.fullmatch(parts[0]):
        return [f"{parts[0]}-{parts[1]}", *parts[2:]]
    return parts
