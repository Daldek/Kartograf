"""
ParserTM33 - computable grid of 2x2 km ETRS89/TM33N (EPSG:3045) tiles for CZ.

The sheet code `{E_km}_{N_km}` is the SW corner of the tile (e.g.
"302_5550" => E 302000..304000, N 5550000..5552000; verified against georss
in the 2026-08-10 research). Pure maths, zero IO - modelled on Parser2000.
"""

import math

from kartograf.core.bbox import BBox
from kartograf.core.parser_registry import CZ_TM33_PATTERN
from kartograf.exceptions import ParseError, ValidationError
from kartograf.messages import message

TM33_CRS = "EPSG:3045"
TILE_SIZE_M = 2000


class ParserTM33:
    """Parser of TM33 grid sheet codes (SW corner, 2 km step)."""

    system = "cz_tm33"

    def __init__(self, sheet: str):
        if not isinstance(sheet, str):
            raise ParseError(
                message(
                    "core.tm33_sheet_code_must_be_string",
                    sheet_type=type(sheet).__name__,
                )
            )
        sheet = sheet.strip()
        match = CZ_TM33_PATTERN.match(sheet)
        if not match:
            raise ParseError(message("core.tm33_code_format", sheet=sheet))
        e_km, n_km = int(match.group(1)), int(match.group(2))
        if e_km % 2 or n_km % 2:
            raise ParseError(message("core.tm33_code_odd_km", sheet=sheet))
        self.sheet = sheet
        self._west = e_km * 1000
        self._south = n_km * 1000

    def get_bbox(self) -> BBox:
        """Tile BBox in EPSG:3045."""
        return BBox(
            self._west,
            self._south,
            self._west + TILE_SIZE_M,
            self._south + TILE_SIZE_M,
            TM33_CRS,
        )

    @staticmethod
    def tile_for(easting: float, northing: float) -> str:
        """Sheet code of the tile containing the point (EPSG:3045)."""
        e_km = int(math.floor(easting / TILE_SIZE_M)) * 2
        n_km = int(math.floor(northing / TILE_SIZE_M)) * 2
        return f"{e_km:03d}_{n_km:04d}"

    def __repr__(self) -> str:
        """Return the constructor-like text of the parser."""
        return f"ParserTM33('{self.sheet}')"


def find_tiles_tm33_for_bbox(bbox: BBox) -> list[str]:
    """Sheet codes of TM33 tiles intersecting the bbox (EPSG:3045).

    Touching edges do NOT count as an intersection (a tile is included when
    its interior intersects the bbox). Order: rows S->N, columns W->E.
    """
    if bbox.crs != TM33_CRS:
        raise ValidationError(
            message(
                "core.find_tiles_tm33_bbox_needs_bbox", tm33_crs=TM33_CRS, crs=bbox.crs
            )
        )
    if bbox.min_x >= bbox.max_x or bbox.min_y >= bbox.max_y:
        raise ValidationError(
            message(
                "core.invalid_bbox",
                min_x=bbox.min_x,
                min_y=bbox.min_y,
                max_x=bbox.max_x,
                max_y=bbox.max_y,
            )
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
