"""
ParserTM33 — obliczalna siatka kafli 2x2 km ETRS89/TM33N (EPSG:3045) dla CZ.

Godlo `{E_km}_{N_km}` to naroznik SW kafla (np. "302_5550" => E 302000..304000,
N 5550000..5552000; zweryfikowane wobec georss w researchu 2026-08-10).
Czysta matematyka, zero IO — wzor: Parser2000.
"""

import math
import re

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError

TM33_CRS = "EPSG:3045"
TILE_SIZE_M = 2000

_GODLO_RE = re.compile(r"^(\d{3})_(\d{4})$")


class ParserTM33:
    """Parser godel siatki TM33 (naroznik SW, krok 2 km)."""

    uklad = "cz_tm33"

    def __init__(self, godlo: str):
        if not isinstance(godlo, str):
            raise ParseError(
                f"Godlo TM33 musi byc stringiem, otrzymano: {type(godlo).__name__}"
            )
        godlo = godlo.strip()
        match = _GODLO_RE.match(godlo)
        if not match:
            raise ParseError(
                f"Niepoprawne godlo TM33: '{godlo}' (oczekiwano EEE_NNNN, np. 302_5550)"
            )
        e_km, n_km = int(match.group(1)), int(match.group(2))
        if e_km % 2 or n_km % 2:
            raise ParseError(
                f"Niepoprawne godlo TM33: '{godlo}' "
                f"(kafle co 2 km — kilometry musza byc parzyste)"
            )
        self.godlo = godlo
        self._west = e_km * 1000
        self._south = n_km * 1000

    def get_bbox(self) -> BBox:
        """BBox kafla w EPSG:3045."""
        return BBox(
            self._west,
            self._south,
            self._west + TILE_SIZE_M,
            self._south + TILE_SIZE_M,
            TM33_CRS,
        )

    @staticmethod
    def tile_for(easting: float, northing: float) -> str:
        """Godlo kafla zawierajacego punkt (EPSG:3045)."""
        e_km = int(math.floor(easting / TILE_SIZE_M)) * 2
        n_km = int(math.floor(northing / TILE_SIZE_M)) * 2
        return f"{e_km:03d}_{n_km:04d}"

    def __repr__(self) -> str:
        return f"ParserTM33('{self.godlo}')"


def find_tiles_tm33_for_bbox(bbox: BBox) -> list[str]:
    """Godla kafli TM33 przecinajacych bbox (EPSG:3045).

    Krawedzie stykajace sie NIE licza sie jako przeciecie (kafel wchodzi,
    gdy jego wnetrze przecina bbox). Kolejnosc: wiersze S->N, kolumny W->E.
    """
    if bbox.crs != TM33_CRS:
        raise ValidationError(
            f"find_tiles_tm33_for_bbox wymaga bbox w {TM33_CRS}, otrzymano: {bbox.crs}"
        )
    if bbox.min_x >= bbox.max_x or bbox.min_y >= bbox.max_y:
        raise ValidationError(
            f"Niepoprawny bbox: ({bbox.min_x}, {bbox.min_y}, "
            f"{bbox.max_x}, {bbox.max_y})"
        )
    e_start = int(math.floor(bbox.min_x / TILE_SIZE_M)) * TILE_SIZE_M
    n_start = int(math.floor(bbox.min_y / TILE_SIZE_M)) * TILE_SIZE_M
    tiles: list[str] = []
    north = n_start
    while north < bbox.max_y:
        east = e_start
        while east < bbox.max_x:
            tiles.append(f"{east // 1000:03d}_{north // 1000:04d}")
            east += TILE_SIZE_M
        north += TILE_SIZE_M
    return tiles
