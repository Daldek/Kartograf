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


# =============================================================================
# Testy metod hierarchii (Etap 4)
# =============================================================================


class TestSheetParserGetParent:
    """Testy metody get_parent()."""

    def test_get_parent_from_10k(self):
        """Test get_parent() dla skali 1:10000."""
        parser = SheetParser("N-34-130-D-d-2-4")
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34-130-D-d-2"
        assert parent.scale == "1:25000"
        assert parent.uklad == "1992"

    def test_get_parent_from_25k(self):
        """Test get_parent() dla skali 1:25000."""
        parser = SheetParser("N-34-130-D-d-2")
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34-130-D-d"
        assert parent.scale == "1:50000"

    def test_get_parent_from_50k(self):
        """Test get_parent() dla skali 1:50000."""
        parser = SheetParser("N-34-130-D-d")
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34-130-D"
        assert parent.scale == "1:100000"

    def test_get_parent_from_100k(self):
        """Test get_parent() dla skali 1:100000."""
        parser = SheetParser("N-34-130-D")
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34-130"
        assert parent.scale == "1:200000"

    def test_get_parent_from_200k_section_a(self):
        """Test get_parent() dla skali 1:200000 w sekcji A (1-36)."""
        parser = SheetParser("N-34-1")  # Arkusz 1 → sekcja A
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34-A"
        assert parent.scale == "1:500000"

    def test_get_parent_from_200k_section_b(self):
        """Test get_parent() dla skali 1:200000 w sekcji B (37-72)."""
        parser = SheetParser("N-34-37")  # Arkusz 37 → sekcja B
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34-B"
        assert parent.scale == "1:500000"

    def test_get_parent_from_200k_section_c(self):
        """Test get_parent() dla skali 1:200000 w sekcji C (73-108)."""
        parser = SheetParser("N-34-73")  # Arkusz 73 → sekcja C
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34-C"
        assert parent.scale == "1:500000"

    def test_get_parent_from_200k_section_d(self):
        """Test get_parent() dla skali 1:200000 w sekcji D (109-144)."""
        parser = SheetParser("N-34-130")  # Arkusz 130 → sekcja D
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34-D"
        assert parent.scale == "1:500000"

    def test_get_parent_from_500k(self):
        """Test get_parent() dla skali 1:500000."""
        parser = SheetParser("N-34-A")
        parent = parser.get_parent()

        assert parent is not None
        assert parent.godlo == "N-34"
        assert parent.scale == "1:1000000"

    def test_get_parent_from_1m_returns_none(self):
        """Test get_parent() dla skali 1:1000000 zwraca None."""
        parser = SheetParser("N-34")
        parent = parser.get_parent()

        assert parent is None

    def test_get_parent_preserves_uklad(self):
        """Test że get_parent() zachowuje układ."""
        parser = SheetParser("N-34-130-D", uklad="2000")
        parent = parser.get_parent()

        assert parent.uklad == "2000"


class TestSheetParserGetChildren:
    """Testy metody get_children()."""

    def test_get_children_from_1m(self):
        """Test get_children() dla skali 1:1000000 (4 dzieci)."""
        parser = SheetParser("N-34")
        children = parser.get_children()

        assert len(children) == 4
        assert children[0].godlo == "N-34-A"
        assert children[1].godlo == "N-34-B"
        assert children[2].godlo == "N-34-C"
        assert children[3].godlo == "N-34-D"
        assert all(c.scale == "1:500000" for c in children)

    def test_get_children_from_500k_section_a(self):
        """Test get_children() dla skali 1:500000 sekcja A (36 dzieci)."""
        parser = SheetParser("N-34-A")
        children = parser.get_children()

        assert len(children) == 36
        assert children[0].godlo == "N-34-1"
        assert children[35].godlo == "N-34-36"
        assert all(c.scale == "1:200000" for c in children)

    def test_get_children_from_500k_section_d(self):
        """Test get_children() dla skali 1:500000 sekcja D (36 dzieci)."""
        parser = SheetParser("N-34-D")
        children = parser.get_children()

        assert len(children) == 36
        assert children[0].godlo == "N-34-109"
        assert children[35].godlo == "N-34-144"
        assert all(c.scale == "1:200000" for c in children)

    def test_get_children_from_200k(self):
        """Test get_children() dla skali 1:200000 (4 dzieci)."""
        parser = SheetParser("N-34-130")
        children = parser.get_children()

        assert len(children) == 4
        assert children[0].godlo == "N-34-130-A"
        assert children[1].godlo == "N-34-130-B"
        assert children[2].godlo == "N-34-130-C"
        assert children[3].godlo == "N-34-130-D"
        assert all(c.scale == "1:100000" for c in children)

    def test_get_children_from_100k(self):
        """Test get_children() dla skali 1:100000 (4 dzieci)."""
        parser = SheetParser("N-34-130-D")
        children = parser.get_children()

        assert len(children) == 4
        assert children[0].godlo == "N-34-130-D-a"
        assert children[1].godlo == "N-34-130-D-b"
        assert children[2].godlo == "N-34-130-D-c"
        assert children[3].godlo == "N-34-130-D-d"
        assert all(c.scale == "1:50000" for c in children)

    def test_get_children_from_50k(self):
        """Test get_children() dla skali 1:50000 (4 dzieci)."""
        parser = SheetParser("N-34-130-D-d")
        children = parser.get_children()

        assert len(children) == 4
        assert children[0].godlo == "N-34-130-D-d-1"
        assert children[1].godlo == "N-34-130-D-d-2"
        assert children[2].godlo == "N-34-130-D-d-3"
        assert children[3].godlo == "N-34-130-D-d-4"
        assert all(c.scale == "1:25000" for c in children)

    def test_get_children_from_25k(self):
        """Test get_children() dla skali 1:25000 (4 dzieci)."""
        parser = SheetParser("N-34-130-D-d-2")
        children = parser.get_children()

        assert len(children) == 4
        assert children[0].godlo == "N-34-130-D-d-2-1"
        assert children[1].godlo == "N-34-130-D-d-2-2"
        assert children[2].godlo == "N-34-130-D-d-2-3"
        assert children[3].godlo == "N-34-130-D-d-2-4"
        assert all(c.scale == "1:10000" for c in children)

    def test_get_children_from_10k_returns_empty(self):
        """Test get_children() dla skali 1:10000 zwraca pustą listę."""
        parser = SheetParser("N-34-130-D-d-2-4")
        children = parser.get_children()

        assert children == []

    def test_get_children_preserves_uklad(self):
        """Test że get_children() zachowuje układ."""
        parser = SheetParser("N-34-130-D", uklad="2000")
        children = parser.get_children()

        assert all(c.uklad == "2000" for c in children)


class TestSheetParserGetHierarchyUp:
    """Testy metody get_hierarchy_up()."""

    def test_hierarchy_up_from_10k(self):
        """Test get_hierarchy_up() od 1:10000 do 1:1M."""
        parser = SheetParser("N-34-130-D-d-2-4")
        hierarchy = parser.get_hierarchy_up()

        expected_scales = [
            "1:10000",
            "1:25000",
            "1:50000",
            "1:100000",
            "1:200000",
            "1:500000",
            "1:1000000",
        ]

        assert len(hierarchy) == 7
        assert [p.scale for p in hierarchy] == expected_scales

    def test_hierarchy_up_from_100k(self):
        """Test get_hierarchy_up() od 1:100000 do 1:1M."""
        parser = SheetParser("N-34-130-D")
        hierarchy = parser.get_hierarchy_up()

        expected_scales = [
            "1:100000",
            "1:200000",
            "1:500000",
            "1:1000000",
        ]

        assert len(hierarchy) == 4
        assert [p.scale for p in hierarchy] == expected_scales

    def test_hierarchy_up_from_1m(self):
        """Test get_hierarchy_up() od 1:1M (tylko 1 element)."""
        parser = SheetParser("N-34")
        hierarchy = parser.get_hierarchy_up()

        assert len(hierarchy) == 1
        assert hierarchy[0].scale == "1:1000000"
        assert hierarchy[0].godlo == "N-34"

    def test_hierarchy_up_godlo_values(self):
        """Test poprawnych wartości godło w hierarchii."""
        parser = SheetParser("N-34-130-D-d-2-4")
        hierarchy = parser.get_hierarchy_up()

        expected_godla = [
            "N-34-130-D-d-2-4",
            "N-34-130-D-d-2",
            "N-34-130-D-d",
            "N-34-130-D",
            "N-34-130",
            "N-34-D",  # 130 → sekcja D
            "N-34",
        ]

        assert [p.godlo for p in hierarchy] == expected_godla


class TestSheetParserGetAllDescendants:
    """Testy metody get_all_descendants()."""

    def test_descendants_from_50k_to_10k(self):
        """Test get_all_descendants() od 1:50000 do 1:10000."""
        parser = SheetParser("N-34-130-D-d")
        descendants = parser.get_all_descendants("1:10000")

        # 1:50k → 1:25k (4) → 1:10k (4) = 16 arkuszy
        assert len(descendants) == 16
        assert all(d.scale == "1:10000" for d in descendants)

    def test_descendants_from_100k_to_10k(self):
        """Test get_all_descendants() od 1:100000 do 1:10000."""
        parser = SheetParser("N-34-130-D")
        descendants = parser.get_all_descendants("1:10000")

        # 1:100k → 1:50k (4) → 1:25k (4) → 1:10k (4) = 64 arkuszy
        assert len(descendants) == 64
        assert all(d.scale == "1:10000" for d in descendants)

    def test_descendants_from_25k_to_10k(self):
        """Test get_all_descendants() od 1:25000 do 1:10000."""
        parser = SheetParser("N-34-130-D-d-2")
        descendants = parser.get_all_descendants("1:10000")

        assert len(descendants) == 4
        assert all(d.scale == "1:10000" for d in descendants)
        assert descendants[0].godlo == "N-34-130-D-d-2-1"
        assert descendants[3].godlo == "N-34-130-D-d-2-4"

    def test_descendants_from_500k_to_200k(self):
        """Test get_all_descendants() od 1:500000 do 1:200000 (36 arkuszy)."""
        parser = SheetParser("N-34-A")
        descendants = parser.get_all_descendants("1:200000")

        assert len(descendants) == 36
        assert all(d.scale == "1:200000" for d in descendants)

    def test_descendants_from_1m_to_100k(self):
        """Test get_all_descendants() od 1:1M do 1:100000."""
        parser = SheetParser("N-34")
        descendants = parser.get_all_descendants("1:100000")

        # 1:1M → 1:500k (4) → 1:200k (36) → 1:100k (4) = 576 arkuszy
        assert len(descendants) == 576
        assert all(d.scale == "1:100000" for d in descendants)

    def test_descendants_invalid_target_scale(self):
        """Test get_all_descendants() z nieprawidłową skalą docelową."""
        parser = SheetParser("N-34-130-D")

        with pytest.raises(ValidationError, match="Nieprawidłowa skala"):
            parser.get_all_descendants("1:5000")

    def test_descendants_target_scale_not_smaller(self):
        """Test get_all_descendants() gdy skala docelowa >= bieżąca."""
        parser = SheetParser("N-34-130-D")  # 1:100000

        with pytest.raises(ValueError, match="musi być większa"):
            parser.get_all_descendants("1:100000")

        with pytest.raises(ValueError, match="musi być większa"):
            parser.get_all_descendants("1:200000")

    def test_descendants_preserves_uklad(self):
        """Test że get_all_descendants() zachowuje układ."""
        parser = SheetParser("N-34-130-D-d", uklad="2000")
        descendants = parser.get_all_descendants("1:10000")

        assert all(d.uklad == "2000" for d in descendants)


class TestSheetParserHierarchyRoundTrip:
    """Testy spójności hierarchii (parent ↔ children)."""

    def test_parent_child_consistency(self):
        """Test że dziecko.get_parent() zwraca rodzica."""
        parser = SheetParser("N-34-130-D")
        children = parser.get_children()

        for child in children:
            parent = child.get_parent()
            assert parent == parser

    def test_children_parent_consistency_for_500k(self):
        """Test spójności parent ↔ children dla 1:500k."""
        parser = SheetParser("N-34-D")
        children = parser.get_children()

        assert len(children) == 36
        for child in children:
            parent = child.get_parent()
            assert parent == parser

    def test_full_hierarchy_roundtrip(self):
        """Test pełnej ścieżki w górę i w dół."""
        # Start od 1:10k
        parser_10k = SheetParser("N-34-130-D-d-2-4")

        # Idź w górę do 1:1M
        hierarchy = parser_10k.get_hierarchy_up()
        parser_1m = hierarchy[-1]

        assert parser_1m.scale == "1:1000000"
        assert parser_1m.godlo == "N-34"

        # Znajdź drogę z powrotem do oryginalnego arkusza
        descendants = parser_1m.get_all_descendants("1:10000")

        # Oryginalny arkusz powinien być wśród potomków
        assert parser_10k in descendants
