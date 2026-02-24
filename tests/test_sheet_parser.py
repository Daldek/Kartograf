"""
Testy jednostkowe dla modułu sheet_parser.

Ten moduł zawiera testy dla klasy SheetParser, weryfikujące poprawność
parsowania godeł dla wszystkich obsługiwanych skal (1:1M do 1:10k).
"""

import pytest

from kartograf.core.sheet_parser import (
    BBox,
    SheetParser,
    _bboxes_intersect,
    find_sheets_for_bbox,
)
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
        """Test układu 2000 z godłem PL-2000."""
        parser = SheetParser("6.179.12", uklad="2000")
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
        """Test nierówności przy różnych układach — PL-1992 vs PL-2000."""
        parser1 = SheetParser("N-34-130-D", uklad="1992")
        parser2 = SheetParser("6.179.12", uklad="2000")

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
        assert expected == SheetParser.SCALE_HIERARCHY

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
        parser = SheetParser("N-34-130-D", uklad="1992")
        parent = parser.get_parent()

        assert parent.uklad == "1992"


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
        parser = SheetParser("N-34-130-D", uklad="1992")
        children = parser.get_children()

        assert all(c.uklad == "1992" for c in children)


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
        parser = SheetParser("N-34-130-D-d", uklad="1992")
        descendants = parser.get_all_descendants("1:10000")

        assert all(d.uklad == "1992" for d in descendants)


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


# =============================================================================
# Testy metody get_bbox() (obliczanie bounding box)
# =============================================================================


class TestSheetParserGetBBox:
    """Testy metody get_bbox()."""

    def test_bbox_returns_named_tuple(self):
        """Test że get_bbox() zwraca BBox NamedTuple."""
        parser = SheetParser("N-34")
        bbox = parser.get_bbox()

        assert isinstance(bbox, BBox)
        assert hasattr(bbox, "min_x")
        assert hasattr(bbox, "min_y")
        assert hasattr(bbox, "max_x")
        assert hasattr(bbox, "max_y")
        assert hasattr(bbox, "crs")

    def test_bbox_1m_wgs84(self):
        """Test bbox dla 1:1M w WGS84."""
        parser = SheetParser("N-34")
        bbox = parser.get_bbox(crs="EPSG:4326")

        assert bbox.crs == "EPSG:4326"
        # N-34: pas N (row 13) → 52°N-56°N, słup 34 → 18°E-24°E
        assert bbox.min_y == pytest.approx(52.0, abs=0.01)  # south
        assert bbox.max_y == pytest.approx(56.0, abs=0.01)  # north
        assert bbox.min_x == pytest.approx(18.0, abs=0.01)  # west
        assert bbox.max_x == pytest.approx(24.0, abs=0.01)  # east

    def test_bbox_1m_epsg2180(self):
        """Test bbox dla 1:1M w EPSG:2180."""
        parser = SheetParser("N-34")
        bbox = parser.get_bbox(crs="EPSG:2180")

        assert bbox.crs == "EPSG:2180"
        # Współrzędne w metrach, powinny być w sensownym zakresie dla Polski
        # N-34 to duży arkusz (4° × 6°), więc max_y może przekraczać 900000
        assert 100_000 < bbox.min_x < 900_000
        assert 100_000 < bbox.max_x < 1_000_000
        assert 100_000 < bbox.min_y < 900_000
        assert 100_000 < bbox.max_y < 1_000_000

    def test_bbox_500k(self):
        """Test bbox dla 1:500k."""
        parser = SheetParser("N-34-A")
        bbox = parser.get_bbox(crs="EPSG:4326")

        # A = NW quarter: 54°N-56°N, 18°E-21°E
        assert bbox.min_y == pytest.approx(54.0, abs=0.01)
        assert bbox.max_y == pytest.approx(56.0, abs=0.01)
        assert bbox.min_x == pytest.approx(18.0, abs=0.01)
        assert bbox.max_x == pytest.approx(21.0, abs=0.01)

    def test_bbox_200k(self):
        """Test bbox dla 1:200k."""
        parser = SheetParser("N-34-1")
        bbox = parser.get_bbox(crs="EPSG:4326")

        # Arkusz 1 = pierwszy w siatce 12x12 (NW corner)
        # Wymiary: 20' lat × 30' lon
        # row=0, col=0 → N: 56°-20/60=55.667°, S: 55.667°-20/60=55.333°
        # W: 18°, E: 18.5°
        assert bbox.max_y == pytest.approx(56.0, abs=0.01)  # north
        assert bbox.min_y == pytest.approx(56.0 - 20 / 60, abs=0.01)  # south
        assert bbox.min_x == pytest.approx(18.0, abs=0.01)  # west
        assert bbox.max_x == pytest.approx(18.5, abs=0.01)  # east

    def test_bbox_100k(self):
        """Test bbox dla 1:100k."""
        parser = SheetParser("N-34-130-D")
        bbox = parser.get_bbox(crs="EPSG:4326")

        # Arkusz 130 w 12x12: row=10, col=9
        # D = SE quarter of 1:200k
        # Bbox powinien być sensowny (w granicach N-34)
        assert 52.0 < bbox.min_y < 56.0
        assert 52.0 < bbox.max_y < 56.0
        assert 18.0 < bbox.min_x < 24.0
        assert 18.0 < bbox.max_x < 24.0
        # D jest w SE, więc min_y/min_x powinny być większe niż dla A
        assert bbox.min_y > 52.0

    def test_bbox_child_within_parent(self):
        """Test że bbox dziecka mieści się w bbox rodzica."""
        parent = SheetParser("N-34-130-D")
        parent_bbox = parent.get_bbox(crs="EPSG:4326")

        for child in parent.get_children():
            child_bbox = child.get_bbox(crs="EPSG:4326")

            assert child_bbox.min_x >= parent_bbox.min_x - 0.0001
            assert child_bbox.max_x <= parent_bbox.max_x + 0.0001
            assert child_bbox.min_y >= parent_bbox.min_y - 0.0001
            assert child_bbox.max_y <= parent_bbox.max_y + 0.0001

    def test_bbox_10k(self):
        """Test bbox dla 1:10k."""
        parser = SheetParser("N-34-130-D-d-2-4")
        bbox = parser.get_bbox(crs="EPSG:4326")

        # Bbox powinien być bardzo mały (ok 1.25' × 1.875')
        lat_span = bbox.max_y - bbox.min_y
        lon_span = bbox.max_x - bbox.min_x

        # 1.25' = 1.25/60 deg ≈ 0.0208 deg
        assert lat_span == pytest.approx(1.25 / 60, abs=0.001)
        # 1.875' = 1.875/60 deg ≈ 0.03125 deg
        assert lon_span == pytest.approx(1.875 / 60, abs=0.001)

    def test_bbox_invalid_crs(self):
        """Test błędu dla nieobsługiwanego CRS."""
        parser = SheetParser("N-34")

        with pytest.raises(ValidationError, match="Nieobsługiwany układ"):
            parser.get_bbox(crs="EPSG:3857")

    def test_bbox_default_crs_is_2180(self):
        """Test że domyślny CRS to EPSG:2180."""
        parser = SheetParser("N-34")
        bbox = parser.get_bbox()

        assert bbox.crs == "EPSG:2180"

    def test_bbox_consistency_across_hierarchy(self):
        """Test spójności bbox w hierarchii - suma dzieci = rodzic."""
        parser = SheetParser("N-34-130-D-d")
        parent_bbox = parser.get_bbox(crs="EPSG:4326")

        children = parser.get_children()
        assert len(children) == 4

        # Oblicz sumaryczny bbox wszystkich dzieci
        all_min_x = min(c.get_bbox(crs="EPSG:4326").min_x for c in children)
        all_max_x = max(c.get_bbox(crs="EPSG:4326").max_x for c in children)
        all_min_y = min(c.get_bbox(crs="EPSG:4326").min_y for c in children)
        all_max_y = max(c.get_bbox(crs="EPSG:4326").max_y for c in children)

        assert all_min_x == pytest.approx(parent_bbox.min_x, abs=0.0001)
        assert all_max_x == pytest.approx(parent_bbox.max_x, abs=0.0001)
        assert all_min_y == pytest.approx(parent_bbox.min_y, abs=0.0001)
        assert all_max_y == pytest.approx(parent_bbox.max_y, abs=0.0001)


# =============================================================================
# Testy _bboxes_intersect()
# =============================================================================


class TestBBoxesIntersect:
    """Testy funkcji _bboxes_intersect()."""

    def test_overlapping_boxes(self):
        """Test przecinających się boxów."""
        a = BBox(0, 0, 10, 10, "EPSG:4326")
        b = BBox(5, 5, 15, 15, "EPSG:4326")
        assert _bboxes_intersect(a, b) is True

    def test_non_overlapping_right(self):
        """Test nieprzecinających się boxów (b na prawo od a)."""
        a = BBox(0, 0, 5, 5, "EPSG:4326")
        b = BBox(6, 0, 10, 5, "EPSG:4326")
        assert _bboxes_intersect(a, b) is False

    def test_non_overlapping_above(self):
        """Test nieprzecinających się boxów (b powyżej a)."""
        a = BBox(0, 0, 5, 5, "EPSG:4326")
        b = BBox(0, 6, 5, 10, "EPSG:4326")
        assert _bboxes_intersect(a, b) is False

    def test_touching_edge(self):
        """Test boxów stykających się krawędzią — traktowane jako przecinające."""
        a = BBox(0, 0, 5, 5, "EPSG:4326")
        b = BBox(5, 0, 10, 5, "EPSG:4326")
        # Touching at edge (a.max_x == b.min_x) — considered intersecting
        # (shared boundary counts as overlap)
        assert _bboxes_intersect(a, b) is True

    def test_contained_box(self):
        """Test boxa zawartego w innym boxie."""
        a = BBox(0, 0, 10, 10, "EPSG:4326")
        b = BBox(2, 2, 8, 8, "EPSG:4326")
        assert _bboxes_intersect(a, b) is True

    def test_identical_boxes(self):
        """Test identycznych boxów."""
        a = BBox(0, 0, 10, 10, "EPSG:4326")
        assert _bboxes_intersect(a, a) is True


# =============================================================================
# Testy find_sheets_for_bbox()
# =============================================================================


class TestFindSheetsForBBox:
    """Testy funkcji find_sheets_for_bbox()."""

    def test_single_sheet_exact_match(self):
        """Test bbox = get_bbox() jednego 1:10k → zwraca dokładnie to jedno godło."""
        godlo = "N-34-130-D-d-2-4"
        parser = SheetParser(godlo)
        bbox = parser.get_bbox(crs="EPSG:4326")

        # Nieco zmniejszamy bbox, żeby mieścił się wewnątrz arkusza
        shrink = 0.0001
        inner_bbox = BBox(
            bbox.min_x + shrink,
            bbox.min_y + shrink,
            bbox.max_x - shrink,
            bbox.max_y - shrink,
            "EPSG:4326",
        )

        result = find_sheets_for_bbox(inner_bbox, "1:10000")
        assert result == [godlo]

    def test_100k_contains_64_sheets(self):
        """Test bbox = get_bbox() jednego 1:100k → 64 arkuszy 1:10k."""
        godlo_100k = "N-34-130-D"
        parser = SheetParser(godlo_100k)
        bbox = parser.get_bbox(crs="EPSG:4326")

        # Nieco zmniejszamy, żeby nie chwycić sąsiadów
        shrink = 0.0001
        inner_bbox = BBox(
            bbox.min_x + shrink,
            bbox.min_y + shrink,
            bbox.max_x - shrink,
            bbox.max_y - shrink,
            "EPSG:4326",
        )

        result = find_sheets_for_bbox(inner_bbox, "1:10000")
        assert len(result) == 64
        # Wszystkie powinny zaczynać się od N-34-130-D
        assert all(g.startswith("N-34-130-D") for g in result)

    def test_bbox_epsg2180(self):
        """Test bbox w EPSG:2180 → poprawna konwersja i wynik."""
        # Użyj bbox jednego arkusza 1:10k w EPSG:2180
        godlo = "N-34-130-D-d-2-4"
        parser = SheetParser(godlo)
        bbox_2180 = parser.get_bbox(crs="EPSG:2180")

        # Nieco zmniejszamy
        shrink = 10  # 10 metrów
        inner_bbox = BBox(
            bbox_2180.min_x + shrink,
            bbox_2180.min_y + shrink,
            bbox_2180.max_x - shrink,
            bbox_2180.max_y - shrink,
            "EPSG:2180",
        )

        result = find_sheets_for_bbox(inner_bbox, "1:10000")
        assert godlo in result

    def test_bbox_epsg4326(self):
        """Test bbox w EPSG:4326 → poprawny wynik."""
        # Mały bbox w centrum Krakowa (powinien trafić w M-34)
        bbox = BBox(19.93, 50.05, 19.95, 50.07, "EPSG:4326")
        result = find_sheets_for_bbox(bbox, "1:10000")
        assert len(result) >= 1
        # Powinny być w okolicy M-34
        assert all(g.startswith("M-34") for g in result)

    def test_bbox_on_1m_boundary(self):
        """Test bbox na granicy dwóch 1:1M → arkusze z obu."""
        # Bbox rozciągający się na granicy pasów N i M (52°N)
        # N: 52-56°N, M: 48-52°N
        bbox = BBox(20.0, 51.99, 20.1, 52.01, "EPSG:4326")
        result = find_sheets_for_bbox(bbox, "1:1000000")
        godla = sorted(result)
        # Powinien zawierać oba pasy: M (48-52) i N (52-56)
        pasy = {g.split("-")[0] for g in godla}
        assert "M" in pasy
        assert "N" in pasy

    def test_target_scale_1m(self):
        """Test target 1:1M → zwraca godła 1:1M."""
        bbox = BBox(20.0, 52.5, 20.5, 53.0, "EPSG:4326")
        result = find_sheets_for_bbox(bbox, "1:1000000")
        assert len(result) >= 1
        # Sprawdź format — godło 1:1M to X-YY
        for godlo in result:
            parser = SheetParser(godlo)
            assert parser.scale == "1:1000000"

    def test_target_scale_200k(self):
        """Test target 1:200k → godła formatu N-34-XXX."""
        bbox = BBox(20.0, 52.5, 20.5, 53.0, "EPSG:4326")
        result = find_sheets_for_bbox(bbox, "1:200000")
        assert len(result) >= 1
        for godlo in result:
            parser = SheetParser(godlo)
            assert parser.scale == "1:200000"

    def test_invalid_scale(self):
        """Test złej skali docelowej → ValidationError."""
        bbox = BBox(20.0, 52.0, 20.5, 52.5, "EPSG:4326")
        with pytest.raises(ValidationError, match="Nieprawidłowa skala"):
            find_sheets_for_bbox(bbox, "1:5000")

    def test_invalid_crs(self):
        """Test nieobsługiwanego CRS → ValidationError."""
        bbox = BBox(0, 0, 1, 1, "EPSG:3857")
        with pytest.raises(ValidationError, match="Nieobsługiwany CRS"):
            find_sheets_for_bbox(bbox, "1:10000")

    def test_sorted_output(self):
        """Test że wynik jest posortowany."""
        # Bbox pokrywający kilka arkuszy
        bbox = BBox(20.0, 52.5, 20.3, 52.7, "EPSG:4326")
        result = find_sheets_for_bbox(bbox, "1:10000")
        assert result == sorted(result)

    def test_target_scale_500k(self):
        """Test target 1:500k."""
        bbox = BBox(20.0, 52.5, 20.5, 53.0, "EPSG:4326")
        result = find_sheets_for_bbox(bbox, "1:500000")
        assert len(result) >= 1
        for godlo in result:
            parser = SheetParser(godlo)
            assert parser.scale == "1:500000"

    def test_roundtrip_single_sheet_all_scales(self):
        """Test roundtrip: get_bbox → find_sheets_for_bbox dla różnych skal."""
        test_cases = [
            ("N-34", "1:1000000"),
            ("N-34-A", "1:500000"),
            ("N-34-130", "1:200000"),
            ("N-34-130-D", "1:100000"),
            ("N-34-130-D-d", "1:50000"),
            ("N-34-130-D-d-2", "1:25000"),
            ("N-34-130-D-d-2-4", "1:10000"),
        ]

        for godlo, scale in test_cases:
            parser = SheetParser(godlo)
            bbox = parser.get_bbox(crs="EPSG:4326")
            # Zmniejsz bbox żeby mieścił się wewnątrz
            shrink = 0.00001
            inner_bbox = BBox(
                bbox.min_x + shrink,
                bbox.min_y + shrink,
                bbox.max_x - shrink,
                bbox.max_y - shrink,
                "EPSG:4326",
            )
            result = find_sheets_for_bbox(inner_bbox, scale)
            assert godlo in result, f"Expected {godlo} in result for scale {scale}"


# =============================================================================
# Testy auto-detekcji PL-1992 vs PL-2000
# =============================================================================


class TestSheetParserAutoDetection:
    """Auto-detection of PL-1992 vs PL-2000 format."""

    def test_pl1992_detected(self):
        p = SheetParser("N-34-130-D")
        assert p.uklad == "1992"

    def test_pl2000_detected(self):
        p = SheetParser("6.179.12")
        assert p.uklad == "2000"
        assert p.scale == "1:10000"

    def test_pl2000_2k(self):
        p = SheetParser("6.179.12.20")
        assert p.uklad == "2000"
        assert p.scale == "1:2000"

    def test_pl2000_5k(self):
        p = SheetParser("6.179.12.3")
        assert p.uklad == "2000"
        assert p.scale == "1:5000"

    def test_pl2000_500(self):
        p = SheetParser("6.179.12.01.1.1")
        assert p.uklad == "2000"
        assert p.scale == "1:500"

    def test_pl2000_bbox(self):
        p = SheetParser("6.179.12")
        bbox = p.get_bbox()
        assert bbox.crs == "EPSG:2177"

    def test_pl2000_parent(self):
        p = SheetParser("6.179.12.01")
        parent = p.get_parent()
        assert parent is not None
        assert parent.godlo == "6.179.12"
        assert isinstance(parent, SheetParser)

    def test_pl2000_children(self):
        p = SheetParser("6.179.12")
        children = p.get_children()
        assert len(children) == 25
        assert all(isinstance(c, SheetParser) for c in children)

    def test_pl2000_hierarchy_up(self):
        p = SheetParser("6.179.12.01.1")
        h = p.get_hierarchy_up()
        assert len(h) == 3
        assert all(isinstance(x, SheetParser) for x in h)

    def test_pl2000_descendants(self):
        p = SheetParser("6.179.12")
        desc = p.get_all_descendants("1:2000")
        assert len(desc) == 25
        assert all(isinstance(d, SheetParser) for d in desc)

    def test_explicit_uklad_2000_match(self):
        p = SheetParser("6.179.12", uklad="2000")
        assert p.uklad == "2000"

    def test_explicit_uklad_1992_conflict(self):
        with pytest.raises(ValidationError):
            SheetParser("6.179.12", uklad="1992")

    def test_explicit_uklad_2000_conflict_with_1992_format(self):
        with pytest.raises(ValidationError):
            SheetParser("N-34-130-D", uklad="2000")

    def test_pl2000_components(self):
        p = SheetParser("6.179.12")
        c = p.components
        assert c["strefa"] == "6"
        assert c["pas"] == "179"

    def test_pl2000_equality(self):
        a = SheetParser("6.179.12")
        b = SheetParser("6.179.12")
        assert a == b
        assert hash(a) == hash(b)

    def test_pl2000_repr(self):
        p = SheetParser("6.179.12")
        assert "6.179.12" in repr(p)

    def test_pl2000_str(self):
        p = SheetParser("6.179.12")
        assert "2000" in str(p)

    def test_pl1992_backward_compat(self):
        """Existing PL-1992 usage unchanged."""
        p = SheetParser("N-34-130-D-d-2-4")
        assert p.uklad == "1992"
        assert p.scale == "1:10000"
        bbox = p.get_bbox()
        assert bbox.crs == "EPSG:2180"


class TestFindSheetsForBBoxSystem:
    """find_sheets_for_bbox with system parameter."""

    def test_default_system_1992(self):
        """Default system='1992' returns PL-1992 godla (dash-separated)."""
        bbox = BBox(400000, 500000, 410000, 510000, "EPSG:2180")
        result = find_sheets_for_bbox(bbox, target_scale="1:10000")
        assert all("-" in g for g in result)

    def test_system_2000(self):
        """system='2000' returns PL-2000 godla (dot-separated)."""
        bbox = BBox(400000, 500000, 410000, 510000, "EPSG:2180")
        result = find_sheets_for_bbox(bbox, target_scale="1:10000", system="2000")
        assert all("." in g for g in result)
        assert len(result) > 0

    def test_backward_compatible(self):
        """Calling without system param gives same result as system='1992'."""
        bbox = BBox(400000, 500000, 410000, 510000, "EPSG:2180")
        result_default = find_sheets_for_bbox(bbox, "1:10000")
        result_explicit = find_sheets_for_bbox(bbox, "1:10000", system="1992")
        assert result_default == result_explicit

    def test_system_2000_wgs84(self):
        """system='2000' works with WGS84 bbox, zone detected from longitude."""
        bbox = BBox(17.0, 52.0, 17.1, 52.1, "EPSG:4326")
        result = find_sheets_for_bbox(bbox, "1:10000", system="2000")
        assert all(g.startswith("6.") for g in result)
