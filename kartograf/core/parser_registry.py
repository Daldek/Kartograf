"""
Rejestr systemow godel (etap 0: pl1992 + pl2000; etap 1: cz_tm33, cz_sm5).

Logika detekcji PL-2000 (regex) i dzielenia sciezek przeniesiona 1:1
z sheet_parser._is_pl2000_format i FileStorage._get_directory_parts.
Fabryki parserow uzywaja importow lazy (unikamy cyklu importow z sheet_parser).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SheetSystem:
    """Opis jednego systemu godlowania arkuszy."""

    id: str  # "pl1992", "pl2000", "cz_tm33", "cz_sm5"
    country: str
    detect: Callable[[str], bool]
    parser_factory: Callable[[str], Any]  # obiekt z .godlo, .get_bbox(), ...
    path_parts: Callable[[str], list[str]]  # czesci sciezki dla FileStorage


_REGISTRY: list[SheetSystem] = []


def register_system(system: SheetSystem) -> None:
    """Zarejestruj system godel; ValueError przy duplikacie id."""
    if any(s.id == system.id for s in _REGISTRY):
        raise ValueError(f"System godel '{system.id}' jest juz zarejestrowany")
    _REGISTRY.append(system)


def detect_system(godlo: str) -> SheetSystem | None:
    """Zwroc pierwszy system (w kolejnosci rejestracji), ktorego detect pasuje."""
    for system in _REGISTRY:
        if system.detect(godlo):
            return system
    return None


def path_parts(godlo: str) -> list[str]:
    """Czesci sciezki katalogowej dla godla wg wykrytego systemu."""
    system = detect_system(godlo)
    if system is None:
        raise ValueError(f"Brak systemu godel pasujacego do: '{godlo}'")
    return system.path_parts(godlo)


_PL2000_PATTERN = re.compile(r"^[5-8]\.\d")


def _detect_pl2000(godlo: str) -> bool:
    return bool(_PL2000_PATTERN.match(godlo))


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


def _make_parser_pl2000(godlo: str) -> Any:
    from kartograf.core.parser_2000 import Parser2000

    return Parser2000(godlo)


def _make_parser_pl1992(godlo: str) -> Any:
    from kartograf.core.sheet_parser import SheetParser

    return SheetParser(godlo)


_CZ_TM33_PATTERN = re.compile(r"^\d{3}_\d{4}$")
_CZ_SM5_PATTERN = re.compile(r"^[A-Z]{4}\d{2}$")


def _make_parser_cz_tm33(godlo: str) -> Any:
    from kartograf.core.parser_tm33 import ParserTM33

    return ParserTM33(godlo)


def _make_parser_cz_sm5(godlo: str) -> Any:
    # Import leniwy: unika ciagniecia providers/cuzk (i jego IO-zaleznych
    # importow, np. CuzkClient) do core przy imporcie modulu. Wartosc "cz_sm5"
    # jest zgodna z Sm5Sheet.uklad i SheetIndex.SM5_SYSTEM (providers/cuzk/sheets.py) —
    # nie importowana stad celowo, zeby nie naruszyc warstwy core/providers.
    from kartograf.providers.cuzk.sheets import Sm5Sheet

    return Sm5Sheet(godlo)


register_system(
    SheetSystem(
        id="pl2000",
        country="PL",
        detect=_detect_pl2000,
        parser_factory=_make_parser_pl2000,
        path_parts=_pl2000_path_parts,
    )
)
register_system(
    SheetSystem(
        id="cz_tm33",
        country="CZ",
        detect=lambda godlo: bool(_CZ_TM33_PATTERN.match(godlo)),
        parser_factory=_make_parser_cz_tm33,
        path_parts=lambda godlo: godlo.split("_"),
    )
)
register_system(
    SheetSystem(
        id="cz_sm5",
        country="CZ",
        detect=lambda godlo: bool(_CZ_SM5_PATTERN.match(godlo)),
        parser_factory=_make_parser_cz_sm5,
        path_parts=lambda godlo: [godlo[:4], godlo[4:]],
    )
)
register_system(
    SheetSystem(
        id="pl1992",
        country="PL",
        detect=lambda godlo: True,  # fallback — zawsze ostatni
        parser_factory=_make_parser_pl1992,
        path_parts=_pl1992_path_parts,
    )
)
