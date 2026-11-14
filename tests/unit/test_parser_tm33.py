"""Unit tests for the parser_tm33 module (CZ TM33 2x2 km grid)."""

import pytest

from kartograf.core.parser_tm33 import ParserTM33
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError


class TestParserTM33Parsing:
    def test_valid_sheet(self):
        p = ParserTM33("302_5550")
        assert p.sheet == "302_5550"
        assert p.system == "cz_tm33"

    def test_whitespace_stripped(self):
        assert ParserTM33("  302_5550 ").sheet == "302_5550"

    def test_non_string_raises_parse_error(self):
        with pytest.raises(ParseError, match="TM33 sheet code must be"):
            ParserTM33(123)

    @pytest.mark.parametrize(
        "sheet",
        ["302-5550", "3025550", "30_5550", "302_555", "302_55501", "abc_5550", ""],
    )
    def test_invalid_format_raises(self, sheet):
        with pytest.raises(ParseError):
            ParserTM33(sheet)

    @pytest.mark.parametrize("sheet", ["303_5550", "302_5551", "301_5549"])
    def test_odd_kilometers_raise(self, sheet):
        """Tiles every 2 km - odd kilometres are not an SW corner."""
        with pytest.raises(ParseError, match="must be even"):
            ParserTM33(sheet)


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
