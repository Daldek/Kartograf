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

# TM33 tile sheet code `{E_km}_{N_km}` (groups: E and N kilometres of the SW corner).
CZ_TM33_PATTERN = re.compile(r"^(\d{3})_(\d{4})$")
# SM5 sheet code (MAPNOM): 4 uppercase letters + 2 digits, e.g. CTES96.
CZ_SM5_PATTERN = re.compile(r"^[A-Z]{4}\d{2}$")
_PL2000_PATTERN = re.compile(r"^[5-8]\.\d")


@dataclass(frozen=True)
class SheetSystem:
    """Description of a single sheet coding system."""

    id: str  # "pl1992", "pl2000", "cz_tm33", "cz_sm5"
    country: str
    detect: Callable[[str], bool]  # receives the sheet code without whitespace
    path_parts: Callable[[str], list[str]]  # path parts for FileStorage


def _pl2000_path_parts(godlo: str) -> list[str]:
    # PL-2000: split on dots, use all parts as directory hierarchy
    return godlo.split(".")


def _pl1992_path_parts(godlo: str) -> list[str]:
    # PL-1992: split on dashes, first two parts form the base (e.g. N-34).
    # Identifiers without a dash (e.g. opaque non-PL raw identifiers routed
    # through the fallback system) are used as a single directory part.
    parts = godlo.split("-")
    if len(parts) < 2:
        return parts
    dir_parts = [f"{parts[0]}-{parts[1]}"]
    for part in parts[2:]:
        dir_parts.append(part)
    return dir_parts


SYSTEMS: tuple[SheetSystem, ...] = (
    SheetSystem(
        id="pl2000",
        country="PL",
        detect=lambda godlo: bool(_PL2000_PATTERN.match(godlo)),
        path_parts=_pl2000_path_parts,
    ),
    SheetSystem(
        id="cz_tm33",
        country="CZ",
        detect=lambda godlo: bool(CZ_TM33_PATTERN.match(godlo)),
        path_parts=lambda godlo: godlo.split("_"),
    ),
    SheetSystem(
        id="cz_sm5",
        country="CZ",
        detect=lambda godlo: bool(CZ_SM5_PATTERN.match(godlo)),
        path_parts=lambda godlo: [godlo[:4], godlo[4:]],
    ),
    SheetSystem(
        id="pl1992",
        country="PL",
        detect=lambda godlo: True,  # fallback - always last
        path_parts=_pl1992_path_parts,
    ),
)


def detect_system(godlo: str) -> SheetSystem:
    """
    First system (in ``SYSTEMS`` order) whose ``detect`` matches.

    The sheet code is stripped of whitespace. Never returns ``None``:
    ``pl1992`` is the fallback for any identifier (including an invalid one -
    validation is done by the system's parser).
    """
    cleaned = godlo.strip()
    return next(s for s in SYSTEMS if s.detect(cleaned))


def path_parts(godlo: str) -> list[str]:
    """Directory path parts for a sheet code (whitespace stripped), by system."""
    cleaned = godlo.strip()
    return detect_system(cleaned).path_parts(cleaned)
