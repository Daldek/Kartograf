"""Testy rejestru systemow godel (kartograf.core.parser_registry)."""

import pytest

from kartograf.core import parser_registry
from kartograf.core.parser_registry import SheetSystem, detect_system, path_parts


class TestDetection:
    def test_pl2000_detected(self):
        system = detect_system("6.179.12.20")
        assert system is not None and system.id == "pl2000"
        assert system.country == "PL"

    def test_pl1992_fallback(self):
        assert detect_system("N-34-130-D-d-2-4").id == "pl1992"
        assert detect_system("N-34").id == "pl1992"
        # Opaque godlo kafla LAZ (drobniejsze niz 1:10000) tez trafia do pl1992
        assert detect_system("N-33-131-B-a-1-1-4").id == "pl1992"

    def test_registration_order_and_duplicate_guard(self):
        with pytest.raises(ValueError):
            parser_registry.register_system(
                SheetSystem(
                    id="pl2000",
                    country="PL",
                    detect=lambda g: False,
                    parser_factory=lambda g: None,
                    path_parts=lambda g: [],
                )
            )


class TestPathParts:
    """Zlote wartosci — identyczne z dotychczasowym FileStorage._get_directory_parts."""

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


class TestParserFactories:
    def test_pl2000_factory(self):
        parser = detect_system("6.179.12.20").parser_factory("6.179.12.20")
        assert parser.godlo == "6.179.12.20"

    def test_pl1992_factory(self):
        parser = detect_system("N-34-130-D").parser_factory("N-34-130-D")
        assert parser.scale == "1:100000"


class TestSheetParserIntegration:
    def test_is_pl2000_format_delegates_to_registry(self):
        from kartograf.core.sheet_parser import _is_pl2000_format

        assert _is_pl2000_format("6.179.12.20") is True
        assert _is_pl2000_format("N-34-130-D") is False
        assert _is_pl2000_format("4.179.12") is False  # strefa spoza 5-8


class TestCzechSystems:
    """Systemy cz_tm33/cz_sm5 — pomiedzy pl2000 a fallbackiem pl1992."""

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
        # opaque godlo LAZ — musi dalej trafiac do pl1992 (get_raw_path)
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

    def test_cz_tm33_factory(self):
        parser = detect_system("302_5550").parser_factory("302_5550")
        assert parser.uklad == "cz_tm33"
        assert parser.get_bbox().crs == "EPSG:3045"

    def test_cz_sm5_factory_no_io_at_construction(self):
        parser = detect_system("CTES96").parser_factory("CTES96")
        assert parser.uklad == "cz_sm5"
        assert parser.godlo == "CTES96"
        # get_bbox() wymaga indeksu (IO) — NIE wolamy go tutaj

    def test_no_pattern_collisions(self):
        """Wzorce CZ nie przechwytuja godel PL i odwrotnie."""
        assert detect_system("30_5550").id == "pl1992"  # za krotkie na TM33
        assert detect_system("CTES9").id == "pl1992"  # za krotkie na SM5
        assert detect_system("CTES961").id == "pl1992"  # za dlugie na SM5
