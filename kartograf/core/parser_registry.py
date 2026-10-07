"""
Rejestr systemow godel: pl2000, cz_tm33, cz_sm5 i fallback pl1992.

Jedno zrodlo prawdy dla rozpoznania systemu z godla (``detect_system``),
dla podzialu godla na katalogi ``FileStorage`` (``path_parts``) oraz dla
wzorcow godel CZ (``CZ_TM33_PATTERN``, ``CZ_SM5_PATTERN`` — importowane przez
``core.parser_tm33`` i ``providers.cuzk.sheets``). Biale znaki wokol godla sa
obcinane w kazdej funkcji (spojnie z parserami).

Rejestr jest literalem ``SYSTEMS`` (kolejnosc = priorytet detekcji); modul
nie importuje niczego z ``kartograf`` — brak cykli z parserami.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

# Godlo kafla TM33 `{E_km}_{N_km}` (grupy: kilometry E i N narozniku SW).
CZ_TM33_PATTERN = re.compile(r"^(\d{3})_(\d{4})$")
# Godlo arkusza SM5 (MAPNOM): 4 wielkie litery + 2 cyfry, np. CTES96.
CZ_SM5_PATTERN = re.compile(r"^[A-Z]{4}\d{2}$")
_PL2000_PATTERN = re.compile(r"^[5-8]\.\d")


@dataclass(frozen=True)
class SheetSystem:
    """Opis jednego systemu godlowania arkuszy."""

    id: str  # "pl1992", "pl2000", "cz_tm33", "cz_sm5"
    country: str
    detect: Callable[[str], bool]  # dostaje godlo bez bialych znakow
    path_parts: Callable[[str], list[str]]  # czesci sciezki dla FileStorage


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
        detect=lambda godlo: True,  # fallback — zawsze ostatni
        path_parts=_pl1992_path_parts,
    ),
)


def detect_system(godlo: str) -> SheetSystem:
    """
    Pierwszy system (w kolejnosci ``SYSTEMS``), ktorego ``detect`` pasuje.

    Godlo jest obcinane z bialych znakow. Nigdy nie zwraca ``None``: ``pl1992``
    jest fallbackiem dla kazdego identyfikatora (takze nieprawidlowego —
    walidacje robi parser systemu).
    """
    cleaned = godlo.strip()
    return next(s for s in SYSTEMS if s.detect(cleaned))


def path_parts(godlo: str) -> list[str]:
    """Czesci sciezki katalogowej dla godla (bez bialych znakow) wg systemu."""
    cleaned = godlo.strip()
    return detect_system(cleaned).path_parts(cleaned)
