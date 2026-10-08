"""Unit tests for the parser_tm33 module (CZ TM33 2x2 km grid)."""

import pytest

from kartograf.core.parser_tm33 import (
    TILE_SIZE_M,
    TM33_CRS,
    ParserTM33,
    find_tiles_tm33_for_bbox,
)
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError


class TestParserTM33Parsing:
    def test_valid_godlo(self):
        p = ParserTM33("302_5550")
        assert p.godlo == "302_5550"
        assert p.uklad == "cz_tm33"

    def test_whitespace_stripped(self):
        assert ParserTM33("  302_5550 ").godlo == "302_5550"

    def test_non_string_raises_parse_error(self):
        with pytest.raises(ParseError, match="stringiem"):
            ParserTM33(123)

    @pytest.mark.parametrize(
        "godlo",
        ["302-5550", "3025550", "30_5550", "302_555", "302_55501", "abc_5550", ""],
    )
    def test_invalid_format_raises(self, godlo):
        with pytest.raises(ParseError):
            ParserTM33(godlo)

    @pytest.mark.parametrize("godlo", ["303_5550", "302_5551", "301_5549"])
    def test_odd_kilometers_raise(self, godlo):
        """Tiles every 2 km - odd kilometres are not an SW corner."""
        with pytest.raises(ParseError, match="parzyste"):
            ParserTM33(godlo)


class TestParserTM33BBox:
    def test_bbox_research_example(self):
        """Example verified by research: 302_5550."""
        bbox = ParserTM33("302_5550").get_bbox()
        assert bbox == BBox(302_000, 5_550_000, 304_000, 5_552_000, "EPSG:3045")

    def test_bbox_second_example(self):
        """756_5516 — kafel z openzu (DMR5G/epsg-3045)."""
        bbox = ParserTM33("756_5516").get_bbox()
        assert bbox == BBox(756_000, 5_516_000, 758_000, 5_518_000, "EPSG:3045")


class TestTileFor:
    def test_sw_corner_maps_to_itself(self):
        assert ParserTM33.tile_for(302_000.0, 5_550_000.0) == "302_5550"

    def test_interior_point(self):
        assert ParserTM33.tile_for(303_999.9, 5_551_999.9) == "302_5550"

    def test_next_tile_at_east_edge(self):
        assert ParserTM33.tile_for(304_000.0, 5_550_000.0) == "304_5550"


class TestFindTilesTM33ForBBox:
    def test_single_tile(self):
        bbox = BBox(302_500, 5_550_500, 303_500, 5_551_500, "EPSG:3045")
        assert find_tiles_tm33_for_bbox(bbox) == ["302_5550"]

    def test_two_by_two(self):
        bbox = BBox(301_000, 5_549_000, 305_000, 5_553_000, "EPSG:3045")
        assert find_tiles_tm33_for_bbox(bbox) == [
            "300_5548",
            "302_5548",
            "304_5548",
            "300_5550",
            "302_5550",
            "304_5550",
            "300_5552",
            "302_5552",
            "304_5552",
        ]

    def test_touching_edge_excluded(self):
        """max exactly on the tile edge - the tile past the edge is NOT included."""
        bbox = BBox(302_000, 5_550_000, 304_000, 5_552_000, "EPSG:3045")
        assert find_tiles_tm33_for_bbox(bbox) == ["302_5550"]

    def test_wrong_crs_raises(self):
        with pytest.raises(ValidationError, match="EPSG:3045"):
            find_tiles_tm33_for_bbox(BBox(0, 0, 1, 1, "EPSG:2180"))

    def test_degenerate_bbox_raises(self):
        with pytest.raises(ValidationError):
            find_tiles_tm33_for_bbox(
                BBox(302_000, 5_550_000, 302_000, 5_552_000, "EPSG:3045")
            )

    def test_constants(self):
        assert TM33_CRS == "EPSG:3045"
        assert TILE_SIZE_M == 2000
