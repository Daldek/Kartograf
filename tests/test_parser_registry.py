"""Tests of the sheet code system registry (kartograf.core.parser_registry)."""

import pytest

from kartograf.core import parser_registry
from kartograf.core.parser_registry import SheetSystem, detect_system, path_parts
from kartograf.core.parser_tm33 import ParserTM33
from kartograf.exceptions import ParseError


class TestDetection:
    def test_pl2000_detected(self):
        system = detect_system("6.179.12.20")
        assert system is not None and system.id == "pl2000"
        assert system.country == "PL"

    def test_pl1992_fallback(self):
        assert detect_system("N-34-130-D-d-2-4").id == "pl1992"
        assert detect_system("N-34").id == "pl1992"
        # An opaque LAZ tile sheet code (finer than 1:10000) also goes to pl1992
        assert detect_system("N-33-131-B-a-1-1-4").id == "pl1992"

    def test_systems_order_fallback_last(self):
        """Order = detection priority; pl1992 (detect always True) is last."""
        ids = [s.id for s in parser_registry.SYSTEMS]
        assert ids == ["pl2000", "cz_tm33", "cz_sm5", "pl1992"]
        assert all(isinstance(s, SheetSystem) for s in parser_registry.SYSTEMS)

    def test_detect_never_returns_none(self):
        assert detect_system("").id == "pl1992"

    def test_cz_codes_with_non_ascii_digits_not_detected(self):
        """P5: full-width digits are not a CZ sheet code (nor accepted by TM33)."""
        assert detect_system("７３０_５５５５").id == "pl1992"
        assert detect_system("CTES９６").id == "pl1992"
        with pytest.raises(ParseError):
            ParserTM33("７３０_５５５５")


class TestPathParts:
    """Golden values — identical to the former FileStorage._get_directory_parts."""

    @pytest.mark.parametrize(
        ("godlo", "expected"),
        [
            ("N-34-130-D-d-2-4", ["N-34", "130", "D", "d", "2", "4"]),
            ("N-34-130-D", ["N-34", "130", "D"]),
            ("N-34", ["N-34"]),
            ("M-34-27-B-b-2-1-1", ["M-34", "27", "B", "b", "2", "1", "1"]),
            ("6.179.12.20", ["6", "179", "12", "20"]),
            ("6.179.12", ["6", "179", "12"]),
            ("6.162.34.02.3", ["6", "162", "34", "02", "3"]),
        ],
    )
    def test_golden_values(self, godlo, expected):
        assert path_parts(godlo) == expected


class TestSheetParserIntegration:
    def test_is_pl2000_format_delegates_to_registry(self):
        from kartograf.core.sheet_parser import _is_pl2000_format

        assert _is_pl2000_format("6.179.12.20") is True
        assert _is_pl2000_format("N-34-130-D") is False
        assert _is_pl2000_format("4.179.12") is False  # zone outside 5-8


class TestCzechSystems:
    """Systems cz_tm33/cz_sm5 — between pl2000 and the pl1992 fallback."""

    def test_cz_tm33_detected(self):
        system = detect_system("302_5550")
        assert system.id == "cz_tm33"
        assert system.country == "CZ"

    def test_cz_sm5_detected(self):
        system = detect_system("CTES96")
        assert system.id == "cz_sm5"
        assert system.country == "CZ"

    def test_pl_godla_still_detected_first(self):
        assert detect_system("6.179.12.20").id == "pl2000"
        assert detect_system("N-34-130-D-d-2-4").id == "pl1992"

    def test_fallback_still_catches_everything_else(self):
        # opaque LAZ sheet code — must still go to pl1992 (get_raw_path)
        assert detect_system("N-33-131-B-a-1-1-4").id == "pl1992"
        assert detect_system("cokolwiek").id == "pl1992"

    @pytest.mark.parametrize(
        "godlo,parts",
        [
            ("302_5550", ["302", "5550"]),
            ("756_5516", ["756", "5516"]),
            ("CTES96", ["CTES", "96"]),
            ("BENE09", ["BENE", "09"]),
        ],
    )
    def test_cz_path_parts(self, godlo, parts):
        assert path_parts(godlo) == parts

    def test_cz_patterns_are_shared_with_parsers(self):
        """One pattern per system: ParserTM33 and SheetIndex use the registry."""
        from kartograf.core import parser_tm33
        from kartograf.providers.cuzk import sheets

        assert parser_tm33.CZ_TM33_PATTERN is parser_registry.CZ_TM33_PATTERN
        assert sheets.CZ_SM5_PATTERN is parser_registry.CZ_SM5_PATTERN

    def test_no_pattern_collisions(self):
        """CZ patterns do not capture PL sheet codes and vice versa."""
        assert detect_system("30_5550").id == "pl1992"  # too short for TM33
        assert detect_system("CTES9").id == "pl1992"  # too short for SM5
        assert detect_system("CTES961").id == "pl1992"  # too long for SM5


class TestWhitespace:
    """K5: detect_system and path_parts strip whitespace (like the parsers)."""

    @pytest.mark.parametrize(
        ("godlo", "system_id"),
        [
            (" CTES96", "cz_sm5"),
            ("CTES96 ", "cz_sm5"),
            ("302_5550 ", "cz_tm33"),
            (" 302_5550", "cz_tm33"),
            (" 6.179.12.20", "pl2000"),
            ("\tN-34-130-D ", "pl1992"),
        ],
    )
    def test_detect_strips(self, godlo, system_id):
        assert detect_system(godlo).id == system_id

    @pytest.mark.parametrize(
        ("godlo", "parts"),
        [
            (" 302_5550", ["302", "5550"]),
            ("CTES96 ", ["CTES", "96"]),
            (" 6.179.12.20 ", ["6", "179", "12", "20"]),
            (" N-34-130-D", ["N-34", "130", "D"]),
        ],
    )
    def test_path_parts_strip(self, godlo, parts):
        assert path_parts(godlo) == parts
