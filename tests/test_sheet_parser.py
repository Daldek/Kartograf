"""
Testy jednostkowe dla modułu sheet_parser.

Ten moduł zawiera testy dla klasy SheetParser, weryfikujące poprawność
parsowania godeł dla wszystkich obsługiwanych skal (1:1M do 1:10k).
"""

import pytest

from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import ParseError, ValidationError


class TestSheetParserBasic:
    """Testy podstawowej funkcjonalności SheetParser."""

    def test_parse_valid_godlo_1m(self):
        """Test parsowania godła 1:1000000."""
        parser = SheetParser("N-34", uklad="1992")

        assert parser.godlo == "N-34"
        assert parser.scale == "1:1000000"
        assert parser.uklad == "1992"
        assert parser.components["pas"] == "N"
        assert parser.components["slup"] == "34"

    def test_parse_valid_godlo_500k(self):
        """Test parsowania godła 1:500000."""
        parser = SheetParser("N-34-A", uklad="1992")

        assert parser.godlo == "N-34-A"
        assert parser.scale == "1:500000"
        assert parser.components["pas"] == "N"
        assert parser.components["slup"] == "34"
        assert parser.components["arkusz_200k"] == "A"

    def test_parse_valid_godlo_200k(self):
        """Test parsowania godła 1:200000."""
        parser = SheetParser("N-34-130", uklad="1992")

        assert parser.godlo == "N-34-130"
        assert parser.scale == "1:200000"
        assert parser.components["pas"] == "N"
        assert parser.components["slup"] == "34"
        assert parser.components["arkusz_200k"] == "130"

    def test_parse_valid_godlo_100k(self):
        """Test parsowania godła 1:100000."""
        parser = SheetParser("N-34-130-D", uklad="1992")

        assert parser.godlo == "N-34-130-D"
        assert parser.scale == "1:100000"
        assert parser.components["pas"] == "N"
        assert parser.components["slup"] == "34"
        assert parser.components["arkusz_200k"] == "130"
        assert parser.components["arkusz_100k"] == "D"

    def test_parse_valid_godlo_50k(self):
        """Test parsowania godła 1:50000."""
        parser = SheetParser("N-34-130-D-d", uklad="1992")

        assert parser.godlo == "N-34-130-D-d"
        assert parser.scale == "1:50000"
        assert parser.components["pas"] == "N"
        assert parser.components["slup"] == "34"
        assert parser.components["arkusz_200k"] == "130"
        assert parser.components["arkusz_100k"] == "D"
        assert parser.components["arkusz_50k"] == "d"

    def test_parse_valid_godlo_25k(self):
        """Test parsowania godła 1:25000."""
        parser = SheetParser("N-34-130-D-d-2", uklad="1992")

        assert parser.godlo == "N-34-130-D-d-2"
        assert parser.scale == "1:25000"
        assert parser.components["pas"] == "N"
        assert parser.components["slup"] == "34"
        assert parser.components["arkusz_200k"] == "130"
        assert parser.components["arkusz_100k"] == "D"
        assert parser.components["arkusz_50k"] == "d"
        assert parser.components["arkusz_25k"] == "2"

    def test_parse_valid_godlo_10k(self):
        """Test parsowania godła 1:10000."""
        parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")

        assert parser.godlo == "N-34-130-D-d-2-4"
        assert parser.scale == "1:10000"
        assert parser.uklad == "1992"
        assert parser.components["pas"] == "N"
        assert parser.components["slup"] == "34"
        assert parser.components["arkusz_200k"] == "130"
        assert parser.components["arkusz_100k"] == "D"
        assert parser.components["arkusz_50k"] == "d"
        assert parser.components["arkusz_25k"] == "2"
        assert parser.components["arkusz_10k"] == "4"


class TestSheetParserNormalization:
    """Testy normalizacji godeł."""

    def test_normalize_lowercase_pas(self):
        """Test normalizacji małej litery pasa do wielkiej."""
        parser = SheetParser("n-34-130-D", uklad="1992")
        assert parser.godlo == "N-34-130-D"

    def test_normalize_lowercase_100k(self):
        """Test normalizacji małej litery arkusza 100k do wielkiej."""
        parser = SheetParser("N-34-130-d", uklad="1992")
        assert parser.godlo == "N-34-130-D"

    def test_normalize_uppercase_50k_to_lowercase(self):
        """Test normalizacji wielkiej litery arkusza 50k do małej."""
        parser = SheetParser("N-34-130-D-D", uklad="1992")
        assert parser.godlo == "N-34-130-D-d"

    def test_normalize_mixed_case(self):
        """Test normalizacji mieszanych wielkości liter."""
        parser = SheetParser("n-34-130-d-D-2-4", uklad="1992")
        assert parser.godlo == "N-34-130-D-d-2-4"

    def test_strip_whitespace(self):
        """Test usuwania białych znaków."""
        parser = SheetParser("  N-34-130-D  ", uklad="1992")
        assert parser.godlo == "N-34-130-D"


class TestSheetParserUklad:
    """Testy walidacji układu współrzędnych."""

    def test_uklad_1992(self):
        """Test układu 1992."""
        parser = SheetParser("N-34-130-D", uklad="1992")
        assert parser.uklad == "1992"

    def test_uklad_2000(self):
        """Test układu 2000."""
        parser = SheetParser("N-34-130-D", uklad="2000")
        assert parser.uklad == "2000"

    def test_auto_detect_uklad(self):
        """Test automatycznego wykrywania układu (domyślnie 1992)."""
        parser = SheetParser("N-34-130-D")
        assert parser.uklad == "1992"

    def test_invalid_uklad(self):
        """Test walidacji nieprawidłowego układu."""
        with pytest.raises(ValidationError, match="Nieprawidłowy układ"):
            SheetParser("N-34-130-D", uklad="1965")

    def test_invalid_uklad_wrong_type(self):
        """Test walidacji układu o złym typie."""
        with pytest.raises(ValidationError, match="Nieprawidłowy układ"):
            SheetParser("N-34-130-D", uklad="PUWG")


class TestSheetParserValidation:
    """Testy walidacji godeł."""

    def test_invalid_godlo_format(self):
        """Test walidacji nieprawidłowego formatu godła."""
        with pytest.raises(ParseError, match="Nieprawidłowe godło"):
            SheetParser("INVALID-GODLO")

    def test_empty_godlo(self):
        """Test pustego godła."""
        with pytest.raises(ParseError, match="nie może być puste"):
            SheetParser("")

    def test_whitespace_only_godlo(self):
        """Test godła zawierającego tylko białe znaki."""
        with pytest.raises(ParseError, match="nie może być puste"):
            SheetParser("   ")

    def test_invalid_godlo_type(self):
        """Test nieprawidłowego typu godła."""
        with pytest.raises(ParseError, match="musi być stringiem"):
            SheetParser(12345)  # type: ignore

    def test_invalid_pas_letter(self):
        """Test nieprawidłowej litery pasa."""
        with pytest.raises(ParseError, match="Nieprawidłowe godło"):
            SheetParser("1-34")

    def test_invalid_100k_subdivision(self):
        """Test nieprawidłowego podziału 100k (E nie jest dozwolone)."""
        with pytest.raises(ParseError, match="Nieprawidłowe godło"):
            SheetParser("N-34-130-E")

    def test_invalid_50k_subdivision(self):
        """Test nieprawidłowego podziału 50k (e nie jest dozwolone)."""
        with pytest.raises(ParseError, match="Nieprawidłowe godło"):
            SheetParser("N-34-130-D-e")

    def test_invalid_25k_subdivision(self):
        """Test nieprawidłowego podziału 25k (5 nie jest dozwolone)."""
        with pytest.raises(ParseError, match="Nieprawidłowe godło"):
            SheetParser("N-34-130-D-d-5")

    def test_invalid_10k_subdivision(self):
        """Test nieprawidłowego podziału 10k (0 nie jest dozwolone)."""
        with pytest.raises(ParseError, match="Nieprawidłowe godło"):
            SheetParser("N-34-130-D-d-2-0")


class TestSheetParserEdgeCases:
    """Testy przypadków brzegowych."""

    def test_single_digit_slup(self):
        """Test jednoznakowego numeru słupa."""
        parser = SheetParser("M-1", uklad="1992")
        assert parser.godlo == "M-1"
        assert parser.components["slup"] == "1"

    def test_double_digit_slup(self):
        """Test dwuznakowego numeru słupa."""
        parser = SheetParser("M-99", uklad="1992")
        assert parser.godlo == "M-99"
        assert parser.components["slup"] == "99"

    def test_three_digit_arkusz_200k(self):
        """Test trzycyfrowego numeru arkusza 200k."""
        parser = SheetParser("N-34-130", uklad="1992")
        assert parser.components["arkusz_200k"] == "130"

    def test_single_digit_arkusz_200k(self):
        """Test jednocyfrowego numeru arkusza 200k."""
        parser = SheetParser("N-34-1", uklad="1992")
        assert parser.components["arkusz_200k"] == "1"

    def test_all_a_subdivisions(self):
        """Test arkusza z wszystkimi podziałami 'A/a/1'."""
        parser = SheetParser("N-34-130-A-a-1-1", uklad="1992")
        assert parser.components["arkusz_100k"] == "A"
        assert parser.components["arkusz_50k"] == "a"
        assert parser.components["arkusz_25k"] == "1"
        assert parser.components["arkusz_10k"] == "1"

    def test_all_d_subdivisions(self):
        """Test arkusza z wszystkimi podziałami 'D/d/4'."""
        parser = SheetParser("N-34-130-D-d-4-4", uklad="1992")
        assert parser.components["arkusz_100k"] == "D"
        assert parser.components["arkusz_50k"] == "d"
        assert parser.components["arkusz_25k"] == "4"
        assert parser.components["arkusz_10k"] == "4"


class TestSheetParserStringRepresentations:
    """Testy reprezentacji tekstowych."""

    def test_repr(self):
        """Test metody __repr__."""
        parser = SheetParser("N-34-130-D", uklad="1992")
        repr_str = repr(parser)

        assert "SheetParser" in repr_str
        assert "N-34-130-D" in repr_str
        assert "1:100000" in repr_str
        assert "1992" in repr_str

    def test_str(self):
        """Test metody __str__."""
        parser = SheetParser("N-34-130-D", uklad="1992")
        str_repr = str(parser)

        assert "N-34-130-D" in str_repr
        assert "1:100000" in str_repr
        assert "1992" in str_repr


class TestSheetParserEquality:
    """Testy równości obiektów."""

    def test_equal_parsers(self):
        """Test równości identycznych parserów."""
        parser1 = SheetParser("N-34-130-D", uklad="1992")
        parser2 = SheetParser("N-34-130-D", uklad="1992")

        assert parser1 == parser2

    def test_different_godlo(self):
        """Test nierówności przy różnych godłach."""
        parser1 = SheetParser("N-34-130-D", uklad="1992")
        parser2 = SheetParser("N-34-130-C", uklad="1992")

        assert parser1 != parser2

    def test_different_uklad(self):
        """Test nierówności przy różnych układach."""
        parser1 = SheetParser("N-34-130-D", uklad="1992")
        parser2 = SheetParser("N-34-130-D", uklad="2000")

        assert parser1 != parser2

    def test_hash_equal_parsers(self):
        """Test hash dla równych parserów."""
        parser1 = SheetParser("N-34-130-D", uklad="1992")
        parser2 = SheetParser("N-34-130-D", uklad="1992")

        assert hash(parser1) == hash(parser2)

    def test_hash_different_parsers(self):
        """Test hash dla różnych parserów."""
        parser1 = SheetParser("N-34-130-D", uklad="1992")
        parser2 = SheetParser("N-34-130-C", uklad="1992")

        # Hash może być różny (nie musi, ale zazwyczaj jest)
        # Testujemy tylko że hash działa
        assert isinstance(hash(parser1), int)
        assert isinstance(hash(parser2), int)

    def test_not_equal_to_other_types(self):
        """Test nierówności z innymi typami."""
        parser = SheetParser("N-34-130-D", uklad="1992")

        assert parser != "N-34-130-D"
        assert parser != 123
        assert parser != None  # noqa: E711


class TestSheetParserComponentsImmutability:
    """Testy niezmienności słownika components."""

    def test_components_returns_copy(self):
        """Test że components zwraca kopię słownika."""
        parser = SheetParser("N-34-130-D", uklad="1992")
        components1 = parser.components
        components2 = parser.components

        # Modyfikacja jednej kopii nie wpływa na drugą
        components1["test"] = "value"

        assert "test" not in components2
        assert "test" not in parser.components


class TestSheetParserScaleHierarchy:
    """Testy hierarchii skal."""

    def test_scale_hierarchy_order(self):
        """Test poprawnej kolejności skal w hierarchii."""
        expected = [
            "1:1000000",
            "1:500000",
            "1:200000",
            "1:100000",
            "1:50000",
            "1:25000",
            "1:10000",
        ]
        assert SheetParser.SCALE_HIERARCHY == expected

    def test_all_scales_have_patterns(self):
        """Test że wszystkie skale mają zdefiniowane wzorce."""
        for scale in SheetParser.SCALE_HIERARCHY:
            assert scale in SheetParser.PATTERNS
