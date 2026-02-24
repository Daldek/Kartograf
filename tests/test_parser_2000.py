"""
Testy jednostkowe dla modulu parser_2000.

Ten modul zawiera testy dla klasy Parser2000, weryfikujace poprawnosc
parsowania godel PL-2000 dla skal 1:10000 do 1:500.
"""

import pytest

from kartograf.core.parser_2000 import (
    SCALE_HIERARCHY_2000,
    SHEET_DIMENSIONS_2000,
    Parser2000,
    find_sheets_2000_for_bbox,
)
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError

# =========================================================================
# Parsowanie i skala
# =========================================================================


class TestParser2000Parsing:
    """Testy parsowania godel PL-2000."""

    def test_parse_10k(self):
        """Test parsowania godla 1:10000."""
        p = Parser2000("6.179.12")
        assert p.godlo == "6.179.12"
        assert p.scale == "1:10000"
        assert p.uklad == "2000"
        assert p.components == {"strefa": "6", "pas": "179", "slup": "12"}

    def test_parse_5k(self):
        """Test parsowania godla 1:5000."""
        p = Parser2000("6.179.12.3")
        assert p.godlo == "6.179.12.3"
        assert p.scale == "1:5000"
        assert p.components == {
            "strefa": "6",
            "pas": "179",
            "slup": "12",
            "ark_5k": "3",
        }

    def test_parse_2k(self):
        """Test parsowania godla 1:2000."""
        p = Parser2000("6.179.12.15")
        assert p.godlo == "6.179.12.15"
        assert p.scale == "1:2000"
        assert p.components == {
            "strefa": "6",
            "pas": "179",
            "slup": "12",
            "ark_2k": "15",
        }

    def test_parse_1k(self):
        """Test parsowania godla 1:1000."""
        p = Parser2000("6.179.12.15.2")
        assert p.godlo == "6.179.12.15.2"
        assert p.scale == "1:1000"
        assert p.components == {
            "strefa": "6",
            "pas": "179",
            "slup": "12",
            "ark_2k": "15",
            "ark_1k": "2",
        }

    def test_parse_500(self):
        """Test parsowania godla 1:500."""
        p = Parser2000("6.179.12.15.2.4")
        assert p.godlo == "6.179.12.15.2.4"
        assert p.scale == "1:500"
        assert p.components == {
            "strefa": "6",
            "pas": "179",
            "slup": "12",
            "ark_2k": "15",
            "ark_1k": "2",
            "ark_500": "4",
        }

    def test_parse_all_zones(self):
        """Test parsowania dla kazdej strefy (5-8)."""
        for zone in [5, 6, 7, 8]:
            p = Parser2000(f"{zone}.100.10")
            assert p.zone == zone
            assert p.components["strefa"] == str(zone)

    def test_parse_single_digit_pas(self):
        """Test parsowania z jednocyfrowym pasem."""
        p = Parser2000("6.1.1")
        assert p.scale == "1:10000"
        assert p.components["pas"] == "1"

    def test_parse_single_digit_slup(self):
        """Test parsowania z jednocyfrowym slupem."""
        p = Parser2000("6.100.1")
        assert p.scale == "1:10000"
        assert p.components["slup"] == "1"

    def test_components_returns_copy(self):
        """Test ze components zwraca kopie."""
        p = Parser2000("6.179.12")
        c1 = p.components
        c2 = p.components
        assert c1 == c2
        assert c1 is not c2
        c1["extra"] = "value"
        assert "extra" not in p.components


# =========================================================================
# Walidacja
# =========================================================================


class TestParser2000Validation:
    """Testy walidacji danych wejsciowych."""

    def test_non_string_raises_parse_error(self):
        """Test ze non-string podnosi ParseError."""
        with pytest.raises(ParseError, match="stringiem"):
            Parser2000(123)

    def test_empty_string_raises_parse_error(self):
        """Test ze pusty string podnosi ParseError."""
        with pytest.raises(ParseError, match="puste"):
            Parser2000("")

    def test_whitespace_only_raises_parse_error(self):
        """Test ze sam whitespace podnosi ParseError."""
        with pytest.raises(ParseError, match="puste"):
            Parser2000("   ")

    def test_pl1992_format_rejected(self):
        """Test ze format PL-1992 (z myslnikami) jest odrzucany."""
        with pytest.raises(ParseError):
            Parser2000("N-34-130-D-d-2-4")

    def test_invalid_zone_low(self):
        """Test ze strefa < 5 jest odrzucana."""
        with pytest.raises(ParseError):
            Parser2000("4.179.12")

    def test_invalid_zone_high(self):
        """Test ze strefa > 8 jest odrzucana."""
        with pytest.raises(ParseError):
            Parser2000("9.179.12")

    def test_invalid_zone_zero(self):
        """Test ze strefa 0 jest odrzucana."""
        with pytest.raises(ParseError):
            Parser2000("0.179.12")

    def test_ark_2k_zero_raises_validation_error(self):
        """Test ze ark_2k = 00 podnosi ValidationError."""
        with pytest.raises(ValidationError, match="01.*25"):
            Parser2000("6.179.12.00")

    def test_ark_2k_too_high_raises_validation_error(self):
        """Test ze ark_2k = 26 podnosi ValidationError."""
        with pytest.raises(ValidationError, match="01.*25"):
            Parser2000("6.179.12.26")

    def test_ark_2k_boundary_01_valid(self):
        """Test ze ark_2k = 01 jest prawidlowe."""
        p = Parser2000("6.179.12.01")
        assert p.components["ark_2k"] == "01"

    def test_ark_2k_boundary_25_valid(self):
        """Test ze ark_2k = 25 jest prawidlowe."""
        p = Parser2000("6.179.12.25")
        assert p.components["ark_2k"] == "25"

    def test_quadrant_5k_invalid(self):
        """Test ze kwadrant 5k > 4 jest odrzucany."""
        with pytest.raises(ParseError):
            Parser2000("6.179.12.5")

    def test_quadrant_5k_zero(self):
        """Test ze kwadrant 5k = 0 jest odrzucany."""
        with pytest.raises(ParseError):
            Parser2000("6.179.12.0")

    def test_quadrant_1k_invalid(self):
        """Test ze kwadrant 1k > 4 jest odrzucany."""
        with pytest.raises(ParseError):
            Parser2000("6.179.12.15.5")

    def test_quadrant_500_invalid(self):
        """Test ze kwadrant 500 > 4 jest odrzucany."""
        with pytest.raises(ParseError):
            Parser2000("6.179.12.15.2.5")

    def test_garbage_string(self):
        """Test ze losowy string jest odrzucany."""
        with pytest.raises(ParseError):
            Parser2000("abc.def.ghi")

    def test_too_many_dots(self):
        """Test ze zbyt wiele segmentow jest odrzucane."""
        with pytest.raises(ParseError):
            Parser2000("6.179.12.15.2.4.1")

    def test_trailing_dot(self):
        """Test ze trailing dot jest odrzucany."""
        with pytest.raises(ParseError):
            Parser2000("6.179.12.")


# =========================================================================
# Wlasciwosci
# =========================================================================


class TestParser2000Properties:
    """Testy wlasciwosci Parser2000."""

    def test_godlo_property(self):
        """Test wlasciwosci godlo."""
        p = Parser2000("7.200.15")
        assert p.godlo == "7.200.15"

    def test_scale_property(self):
        """Test wlasciwosci scale."""
        p = Parser2000("7.200.15")
        assert p.scale == "1:10000"

    def test_uklad_always_2000(self):
        """Test ze uklad jest zawsze '2000'."""
        p = Parser2000("6.179.12")
        assert p.uklad == "2000"

    def test_zone_property(self):
        """Test wlasciwosci zone."""
        for z in [5, 6, 7, 8]:
            p = Parser2000(f"{z}.100.10")
            assert p.zone == z

    def test_native_crs_zone_5(self):
        """Test native_crs dla strefy 5."""
        p = Parser2000("5.100.10")
        assert p.native_crs == "EPSG:2176"

    def test_native_crs_zone_6(self):
        """Test native_crs dla strefy 6."""
        p = Parser2000("6.100.10")
        assert p.native_crs == "EPSG:2177"

    def test_native_crs_zone_7(self):
        """Test native_crs dla strefy 7."""
        p = Parser2000("7.100.10")
        assert p.native_crs == "EPSG:2178"

    def test_native_crs_zone_8(self):
        """Test native_crs dla strefy 8."""
        p = Parser2000("8.100.10")
        assert p.native_crs == "EPSG:2179"


# =========================================================================
# Rownosc i hashing
# =========================================================================


class TestParser2000Equality:
    """Testy rownosci i hashowania."""

    def test_equal_parsers(self):
        """Test rownosci dwoch identycznych parserow."""
        p1 = Parser2000("6.179.12")
        p2 = Parser2000("6.179.12")
        assert p1 == p2

    def test_unequal_parsers(self):
        """Test nierownosci roznych parserow."""
        p1 = Parser2000("6.179.12")
        p2 = Parser2000("6.179.13")
        assert p1 != p2

    def test_hash_equal(self):
        """Test ze identyczne parsery maja ten sam hash."""
        p1 = Parser2000("6.179.12")
        p2 = Parser2000("6.179.12")
        assert hash(p1) == hash(p2)

    def test_hash_usable_in_set(self):
        """Test ze parsery mozna uzyc w zbiorze."""
        p1 = Parser2000("6.179.12")
        p2 = Parser2000("6.179.12")
        p3 = Parser2000("6.179.13")
        s = {p1, p2, p3}
        assert len(s) == 2

    def test_not_equal_to_non_parser(self):
        """Test ze porownanie z non-Parser2000 zwraca NotImplemented."""
        p = Parser2000("6.179.12")
        assert p != "6.179.12"
        assert p != 42


# =========================================================================
# Repr i str
# =========================================================================


class TestParser2000Repr:
    """Testy repr i str."""

    def test_repr(self):
        """Test reprezentacji repr."""
        p = Parser2000("6.179.12")
        r = repr(p)
        assert "6.179.12" in r
        assert "1:10000" in r
        assert "2000" in r

    def test_str(self):
        """Test reprezentacji str."""
        p = Parser2000("6.179.12")
        s = str(p)
        assert "6.179.12" in s
        assert "1:10000" in s
        assert "2000" in s


# =========================================================================
# BBox — 1:10000 (bazowa skala)
# =========================================================================


class TestParser2000BBox10k:
    """Testy BBox dla skali 1:10000."""

    def test_bbox_native_crs(self):
        """Test BBox w natywnym CRS (PL-2000 zone 6 = EPSG:2177)."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()

        # south = 179*5000 + 4_920_000 = 5_815_000
        # north = 5_815_000 + 5000 = 5_820_000
        # west = 6*1_000_000 + 12*8000 + 332_000 = 6_428_000
        # east = 6_428_000 + 8000 = 6_436_000
        assert bbox.min_y == pytest.approx(5_815_000)
        assert bbox.max_y == pytest.approx(5_820_000)
        assert bbox.min_x == pytest.approx(6_428_000)
        assert bbox.max_x == pytest.approx(6_436_000)
        assert bbox.crs == "EPSG:2177"

    def test_bbox_dimensions_10k(self):
        """Test wymiarow BBox 1:10k (5000 x 8000 m)."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        assert bbox.max_y - bbox.min_y == pytest.approx(5000)
        assert bbox.max_x - bbox.min_x == pytest.approx(8000)

    def test_bbox_different_zone(self):
        """Test BBox w innej strefie."""
        p = Parser2000("7.179.12")
        bbox = p.get_bbox()

        # west = 7*1_000_000 + 12*8000 + 332_000 = 7_428_000
        assert bbox.min_x == pytest.approx(7_428_000)
        assert bbox.crs == "EPSG:2178"

    def test_bbox_zone_5(self):
        """Test BBox w strefie 5."""
        p = Parser2000("5.179.12")
        bbox = p.get_bbox()
        assert bbox.min_x == pytest.approx(5_428_000)
        assert bbox.crs == "EPSG:2176"


# =========================================================================
# BBox — 1:5000 (podpodzial 2x2)
# =========================================================================


class TestParser2000BBox5k:
    """Testy BBox dla skali 1:5000."""

    def test_bbox_5k_quadrant_1(self):
        """Test BBox 1:5000 kwadrant 1 (NW = row0,col0)."""
        p = Parser2000("6.179.12.1")
        bbox = p.get_bbox()

        # Parent 10k: south=5_815_000, north=5_820_000, west=6_428_000, east=6_436_000
        # Quadrant 1 (row=0,col=0): NW corner
        # south = parent.north - 2500 = 5_817_500
        # north = parent.north = 5_820_000
        # west = parent.west = 6_428_000
        # east = parent.west + 4000 = 6_432_000
        assert bbox.min_y == pytest.approx(5_817_500)
        assert bbox.max_y == pytest.approx(5_820_000)
        assert bbox.min_x == pytest.approx(6_428_000)
        assert bbox.max_x == pytest.approx(6_432_000)

    def test_bbox_5k_quadrant_2(self):
        """Test BBox 1:5000 kwadrant 2 (NE = row0,col1)."""
        p = Parser2000("6.179.12.2")
        bbox = p.get_bbox()
        assert bbox.min_y == pytest.approx(5_817_500)
        assert bbox.max_y == pytest.approx(5_820_000)
        assert bbox.min_x == pytest.approx(6_432_000)
        assert bbox.max_x == pytest.approx(6_436_000)

    def test_bbox_5k_quadrant_3(self):
        """Test BBox 1:5000 kwadrant 3 (SW = row1,col0)."""
        p = Parser2000("6.179.12.3")
        bbox = p.get_bbox()
        assert bbox.min_y == pytest.approx(5_815_000)
        assert bbox.max_y == pytest.approx(5_817_500)
        assert bbox.min_x == pytest.approx(6_428_000)
        assert bbox.max_x == pytest.approx(6_432_000)

    def test_bbox_5k_quadrant_4(self):
        """Test BBox 1:5000 kwadrant 4 (SE = row1,col1)."""
        p = Parser2000("6.179.12.4")
        bbox = p.get_bbox()
        assert bbox.min_y == pytest.approx(5_815_000)
        assert bbox.max_y == pytest.approx(5_817_500)
        assert bbox.min_x == pytest.approx(6_432_000)
        assert bbox.max_x == pytest.approx(6_436_000)

    def test_bbox_5k_dimensions(self):
        """Test wymiarow BBox 1:5k (2500 x 4000 m)."""
        p = Parser2000("6.179.12.1")
        bbox = p.get_bbox()
        assert bbox.max_y - bbox.min_y == pytest.approx(2500)
        assert bbox.max_x - bbox.min_x == pytest.approx(4000)


# =========================================================================
# BBox — 1:2000 (podpodzial 5x5)
# =========================================================================


class TestParser2000BBox2k:
    """Testy BBox dla skali 1:2000."""

    def test_bbox_2k_ark_01(self):
        """Test BBox 1:2000 arkusz 01 (row=0,col=0 w siatce 5x5 w 10k)."""
        p = Parser2000("6.179.12.01")
        bbox = p.get_bbox()

        # Arkusz 01: divmod(0,5) -> row=0, col=0
        # south = parent_10k.north - 1*1000 = 5_820_000 - 1000 = 5_819_000
        # north = parent_10k.north - 0*1000 = 5_820_000
        # west = parent_10k.west + 0*1600 = 6_428_000
        # east = parent_10k.west + 1*1600 = 6_429_600
        assert bbox.min_y == pytest.approx(5_819_000)
        assert bbox.max_y == pytest.approx(5_820_000)
        assert bbox.min_x == pytest.approx(6_428_000)
        assert bbox.max_x == pytest.approx(6_429_600)

    def test_bbox_2k_ark_05(self):
        """Test BBox 1:2000 arkusz 05 (row=0,col=4 — koniec wiersza)."""
        p = Parser2000("6.179.12.05")
        bbox = p.get_bbox()

        # Arkusz 05: divmod(4,5) -> row=0, col=4
        # west = 6_428_000 + 4*1600 = 6_434_400
        # east = 6_434_400 + 1600 = 6_436_000
        assert bbox.min_y == pytest.approx(5_819_000)
        assert bbox.max_y == pytest.approx(5_820_000)
        assert bbox.min_x == pytest.approx(6_434_400)
        assert bbox.max_x == pytest.approx(6_436_000)

    def test_bbox_2k_ark_06(self):
        """Test BBox 1:2000 arkusz 06 (row=1,col=0 — nowy wiersz)."""
        p = Parser2000("6.179.12.06")
        bbox = p.get_bbox()

        # Arkusz 06: divmod(5,5) -> row=1, col=0
        assert bbox.min_y == pytest.approx(5_818_000)
        assert bbox.max_y == pytest.approx(5_819_000)
        assert bbox.min_x == pytest.approx(6_428_000)
        assert bbox.max_x == pytest.approx(6_429_600)

    def test_bbox_2k_ark_25(self):
        """Test BBox 1:2000 arkusz 25 (row=4,col=4 — ostatni)."""
        p = Parser2000("6.179.12.25")
        bbox = p.get_bbox()

        # Arkusz 25: divmod(24,5) -> row=4, col=4
        # south = 5_820_000 - 5*1000 = 5_815_000
        # north = 5_815_000 + 1000 = 5_816_000
        # west = 6_428_000 + 4*1600 = 6_434_400
        # east = 6_434_400 + 1600 = 6_436_000
        assert bbox.min_y == pytest.approx(5_815_000)
        assert bbox.max_y == pytest.approx(5_816_000)
        assert bbox.min_x == pytest.approx(6_434_400)
        assert bbox.max_x == pytest.approx(6_436_000)

    def test_bbox_2k_dimensions(self):
        """Test wymiarow BBox 1:2k (1000 x 1600 m)."""
        p = Parser2000("6.179.12.13")
        bbox = p.get_bbox()
        assert bbox.max_y - bbox.min_y == pytest.approx(1000)
        assert bbox.max_x - bbox.min_x == pytest.approx(1600)

    def test_bbox_2k_all_25_tile_parent_10k(self):
        """Test ze 25 arkuszy 1:2k pokrywa caly arkusz 1:10k."""
        parent = Parser2000("6.179.12")
        parent_bbox = parent.get_bbox()

        all_south = []
        all_north = []
        all_west = []
        all_east = []

        for ark in range(1, 26):
            p = Parser2000(f"6.179.12.{ark:02d}")
            bbox = p.get_bbox()
            all_south.append(bbox.min_y)
            all_north.append(bbox.max_y)
            all_west.append(bbox.min_x)
            all_east.append(bbox.max_x)

        assert min(all_south) == pytest.approx(parent_bbox.min_y)
        assert max(all_north) == pytest.approx(parent_bbox.max_y)
        assert min(all_west) == pytest.approx(parent_bbox.min_x)
        assert max(all_east) == pytest.approx(parent_bbox.max_x)


# =========================================================================
# BBox — 1:1000
# =========================================================================


class TestParser2000BBox1k:
    """Testy BBox dla skali 1:1000."""

    def test_bbox_1k_quadrant_1(self):
        """Test BBox 1:1000 kwadrant 1 w arkuszu 2k nr 01."""
        p = Parser2000("6.179.12.01.1")
        bbox = p.get_bbox()

        # Parent 2k ark_01: s=5_819_000 n=5_820_000 w=6_428_000 e=6_429_600
        # Q1 (row=0,col=0): north half, west half
        assert bbox.min_y == pytest.approx(5_819_500)
        assert bbox.max_y == pytest.approx(5_820_000)
        assert bbox.min_x == pytest.approx(6_428_000)
        assert bbox.max_x == pytest.approx(6_428_800)

    def test_bbox_1k_quadrant_4(self):
        """Test BBox 1:1000 kwadrant 4 (SE)."""
        p = Parser2000("6.179.12.01.4")
        bbox = p.get_bbox()

        # Q4 (row=1,col=1): south half, east half
        assert bbox.min_y == pytest.approx(5_819_000)
        assert bbox.max_y == pytest.approx(5_819_500)
        assert bbox.min_x == pytest.approx(6_428_800)
        assert bbox.max_x == pytest.approx(6_429_600)

    def test_bbox_1k_dimensions(self):
        """Test wymiarow BBox 1:1k (500 x 800 m)."""
        p = Parser2000("6.179.12.01.1")
        bbox = p.get_bbox()
        assert bbox.max_y - bbox.min_y == pytest.approx(500)
        assert bbox.max_x - bbox.min_x == pytest.approx(800)


# =========================================================================
# BBox — 1:500
# =========================================================================


class TestParser2000BBox500:
    """Testy BBox dla skali 1:500."""

    def test_bbox_500_quadrant_1(self):
        """Test BBox 1:500 kwadrant 1 (NW)."""
        p = Parser2000("6.179.12.01.1.1")
        bbox = p.get_bbox()

        # Parent 1k Q1: south=5_819_500, north=5_820_000, west=6_428_000, east=6_428_800
        # Q1 (row=0,col=0): north half, west half
        assert bbox.min_y == pytest.approx(5_819_750)
        assert bbox.max_y == pytest.approx(5_820_000)
        assert bbox.min_x == pytest.approx(6_428_000)
        assert bbox.max_x == pytest.approx(6_428_400)

    def test_bbox_500_quadrant_4(self):
        """Test BBox 1:500 kwadrant 4 (SE)."""
        p = Parser2000("6.179.12.01.1.4")
        bbox = p.get_bbox()

        # Q4 (row=1,col=1): south half, east half
        assert bbox.min_y == pytest.approx(5_819_500)
        assert bbox.max_y == pytest.approx(5_819_750)
        assert bbox.min_x == pytest.approx(6_428_400)
        assert bbox.max_x == pytest.approx(6_428_800)

    def test_bbox_500_dimensions(self):
        """Test wymiarow BBox 1:500 (250 x 400 m)."""
        p = Parser2000("6.179.12.01.1.1")
        bbox = p.get_bbox()
        assert bbox.max_y - bbox.min_y == pytest.approx(250)
        assert bbox.max_x - bbox.min_x == pytest.approx(400)


# =========================================================================
# BBox — transformacja CRS
# =========================================================================


class TestParser2000BBoxCRS:
    """Testy transformacji CRS w get_bbox."""

    def test_bbox_default_is_native(self):
        """Test ze domyslny CRS to natywny CRS strefy."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        assert bbox.crs == "EPSG:2177"

    def test_bbox_explicit_native_crs(self):
        """Test ze jawne podanie natywnego CRS dziala."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox(crs="EPSG:2177")
        assert bbox.crs == "EPSG:2177"
        assert bbox.min_y == pytest.approx(5_815_000)

    def test_bbox_different_zone_crs(self):
        """Test transformacji do CRS innej strefy."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox(crs="EPSG:2178")
        assert bbox.crs == "EPSG:2178"
        # Wspolrzedne powinny byc rozne od natywnych
        assert bbox.min_x != pytest.approx(6_428_000)

    def test_bbox_epsg_2180(self):
        """Test transformacji do EPSG:2180 (PL-1992)."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox(crs="EPSG:2180")
        assert bbox.crs == "EPSG:2180"
        # Wspolrzedne PL-1992 powinny byc w sensownym zakresie
        assert 100_000 < bbox.min_x < 900_000
        assert 100_000 < bbox.min_y < 900_000

    def test_bbox_epsg_4326(self):
        """Test transformacji do EPSG:4326 (WGS84)."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox(crs="EPSG:4326")
        assert bbox.crs == "EPSG:4326"
        # Wspolrzedne WGS84 — dlug. geogr. w zakresie Polski (14-24)
        assert 14 < bbox.min_x < 24
        # Szer. geogr. w zakresie Polski (49-55)
        assert 49 < bbox.min_y < 55

    def test_bbox_unsupported_crs_raises(self):
        """Test ze nieobslugiwany CRS podnosi ValidationError."""
        p = Parser2000("6.179.12")
        with pytest.raises(ValidationError, match="Nieobs"):
            p.get_bbox(crs="EPSG:4258")

    def test_bbox_all_zone_crs_accepted(self):
        """Test ze wszystkie CRS stref PL-2000 sa akceptowane."""
        p = Parser2000("6.179.12")
        for epsg in ["EPSG:2176", "EPSG:2177", "EPSG:2178", "EPSG:2179"]:
            bbox = p.get_bbox(crs=epsg)
            assert bbox.crs == epsg

    def test_bbox_crs_transform_preserves_area(self):
        """Test ze transformacja CRS zachowuje przyblizona powierzchnie."""
        p = Parser2000("6.179.12")
        native = p.get_bbox()  # EPSG:2177
        pl1992 = p.get_bbox(crs="EPSG:2180")

        native_area = (native.max_x - native.min_x) * (native.max_y - native.min_y)
        pl1992_area = (pl1992.max_x - pl1992.min_x) * (pl1992.max_y - pl1992.min_y)

        # Powierzchnia powinna byc zblizona (tolerancja 5%)
        assert native_area == pytest.approx(pl1992_area, rel=0.05)


# =========================================================================
# BBox returns BBox NamedTuple
# =========================================================================


class TestParser2000BBoxType:
    """Test ze get_bbox zwraca BBox NamedTuple."""

    def test_bbox_is_namedtuple(self):
        """Test ze wynik jest instancja BBox."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        assert isinstance(bbox, BBox)

    def test_bbox_fields(self):
        """Test ze BBox ma wymagane pola."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        assert hasattr(bbox, "min_x")
        assert hasattr(bbox, "min_y")
        assert hasattr(bbox, "max_x")
        assert hasattr(bbox, "max_y")
        assert hasattr(bbox, "crs")


# =========================================================================
# Stale eksportowane
# =========================================================================


class TestParser2000Constants:
    """Testy stalych eksportowanych."""

    def test_scale_hierarchy(self):
        """Test SCALE_HIERARCHY_2000."""
        assert SCALE_HIERARCHY_2000 == [
            "1:10000",
            "1:5000",
            "1:2000",
            "1:1000",
            "1:500",
        ]

    def test_sheet_dimensions(self):
        """Test SHEET_DIMENSIONS_2000."""
        assert SHEET_DIMENSIONS_2000 == {
            "1:10000": (5000, 8000),
            "1:5000": (2500, 4000),
            "1:2000": (1000, 1600),
            "1:1000": (500, 800),
            "1:500": (250, 400),
        }

    def test_sheet_dimensions_consistent_with_bbox(self):
        """Test ze wymiary w SHEET_DIMENSIONS_2000 sa zgodne z BBox."""
        for scale, (h, w) in SHEET_DIMENSIONS_2000.items():
            # Tworzymy odpowiednie godlo dla kazdej skali
            if scale == "1:10000":
                godlo = "6.179.12"
            elif scale == "1:5000":
                godlo = "6.179.12.1"
            elif scale == "1:2000":
                godlo = "6.179.12.01"
            elif scale == "1:1000":
                godlo = "6.179.12.01.1"
            elif scale == "1:500":
                godlo = "6.179.12.01.1.1"
            else:
                continue

            p = Parser2000(godlo)
            bbox = p.get_bbox()
            assert bbox.max_y - bbox.min_y == pytest.approx(h), (
                f"Height mismatch for {scale}"
            )
            assert bbox.max_x - bbox.min_x == pytest.approx(w), (
                f"Width mismatch for {scale}"
            )


# =========================================================================
# Whitespace handling
# =========================================================================


class TestParser2000Whitespace:
    """Testy obslugi bialych znakow."""

    def test_leading_trailing_whitespace_stripped(self):
        """Test ze wiodace/koncowe biale znaki sa usuwane."""
        p = Parser2000("  6.179.12  ")
        assert p.godlo == "6.179.12"
        assert p.scale == "1:10000"


# =========================================================================
# Hierarchia — get_parent()
# =========================================================================


class TestParser2000GetParent:
    """Testy metody get_parent()."""

    def test_parent_of_10k_is_none(self):
        """1:10000 nie ma rodzica — zwraca None."""
        p = Parser2000("6.179.12")
        assert p.get_parent() is None

    def test_parent_of_5k(self):
        """1:5000 -> rodzic to 1:10000 (usun ark_5k)."""
        p = Parser2000("6.179.12.3")
        parent = p.get_parent()
        assert parent is not None
        assert parent.godlo == "6.179.12"
        assert parent.scale == "1:10000"

    def test_parent_of_2k(self):
        """1:2000 -> rodzic to 1:10000 (usun ark_2k)."""
        p = Parser2000("6.179.12.15")
        parent = p.get_parent()
        assert parent is not None
        assert parent.godlo == "6.179.12"
        assert parent.scale == "1:10000"

    def test_parent_of_1k(self):
        """1:1000 -> rodzic to 1:2000 (usun ark_1k)."""
        p = Parser2000("6.179.12.15.2")
        parent = p.get_parent()
        assert parent is not None
        assert parent.godlo == "6.179.12.15"
        assert parent.scale == "1:2000"

    def test_parent_of_500(self):
        """1:500 -> rodzic to 1:1000 (usun ark_500)."""
        p = Parser2000("6.179.12.15.2.4")
        parent = p.get_parent()
        assert parent is not None
        assert parent.godlo == "6.179.12.15.2"
        assert parent.scale == "1:1000"

    def test_parent_returns_parser2000(self):
        """get_parent zwraca instancje Parser2000."""
        p = Parser2000("6.179.12.3")
        parent = p.get_parent()
        assert isinstance(parent, Parser2000)

    def test_parent_chain_500_to_10k(self):
        """Lancuch rodzicow od 1:500 do 1:10000."""
        p = Parser2000("6.179.12.15.2.4")
        # 1:500 -> 1:1000
        p1 = p.get_parent()
        assert p1.scale == "1:1000"
        assert p1.godlo == "6.179.12.15.2"
        # 1:1000 -> 1:2000
        p2 = p1.get_parent()
        assert p2.scale == "1:2000"
        assert p2.godlo == "6.179.12.15"
        # 1:2000 -> 1:10000
        p3 = p2.get_parent()
        assert p3.scale == "1:10000"
        assert p3.godlo == "6.179.12"
        # 1:10000 -> None
        assert p3.get_parent() is None

    def test_parent_of_5k_all_quadrants(self):
        """Wszystkie kwadrenty 1:5000 maja tego samego rodzica 1:10000."""
        parent_godlo = "6.179.12"
        for q in [1, 2, 3, 4]:
            p = Parser2000(f"6.179.12.{q}")
            parent = p.get_parent()
            assert parent.godlo == parent_godlo

    def test_parent_of_2k_all_arks(self):
        """Wszystkie arkusze 1:2000 (01-25) maja tego samego rodzica 1:10000."""
        parent_godlo = "6.179.12"
        for ark in range(1, 26):
            p = Parser2000(f"6.179.12.{ark:02d}")
            parent = p.get_parent()
            assert parent.godlo == parent_godlo

    def test_parent_different_zone(self):
        """get_parent dziala poprawnie dla roznych stref."""
        p = Parser2000("8.100.5.15")
        parent = p.get_parent()
        assert parent.godlo == "8.100.5"
        assert parent.zone == 8


# =========================================================================
# Hierarchia — get_children()
# =========================================================================


class TestParser2000GetChildren:
    """Testy metody get_children()."""

    # --- 1:10000 -> 1:5000 (2x2) ---

    def test_children_10k_to_5k(self):
        """1:10000 -> 4 dzieci 1:5000 (kwadranty 1-4)."""
        p = Parser2000("6.179.12")
        children = p.get_children(scale="1:5000")
        assert len(children) == 4
        godla = [c.godlo for c in children]
        assert godla == ["6.179.12.1", "6.179.12.2", "6.179.12.3", "6.179.12.4"]

    def test_children_10k_to_5k_all_are_5k(self):
        """Wszystkie dzieci 1:10000 przy scale=1:5000 maja skale 1:5000."""
        p = Parser2000("6.179.12")
        children = p.get_children(scale="1:5000")
        for c in children:
            assert c.scale == "1:5000"

    # --- 1:10000 -> 1:2000 (5x5) ---

    def test_children_10k_to_2k(self):
        """1:10000 -> 25 dzieci 1:2000 (arkusze 01-25)."""
        p = Parser2000("6.179.12")
        children = p.get_children(scale="1:2000")
        assert len(children) == 25
        godla = [c.godlo for c in children]
        assert godla[0] == "6.179.12.01"
        assert godla[24] == "6.179.12.25"

    def test_children_10k_default_is_2k(self):
        """Domyslny scale dla 1:10000 to 1:2000."""
        p = Parser2000("6.179.12")
        children_default = p.get_children()
        children_2k = p.get_children(scale="1:2000")
        assert [c.godlo for c in children_default] == [c.godlo for c in children_2k]

    def test_children_10k_to_2k_all_are_2k(self):
        """Wszystkie dzieci 1:10000 przy scale=1:2000 maja skale 1:2000."""
        p = Parser2000("6.179.12")
        children = p.get_children(scale="1:2000")
        for c in children:
            assert c.scale == "1:2000"

    # --- 1:2000 -> 1:1000 (2x2) ---

    def test_children_2k_to_1k(self):
        """1:2000 -> 4 dzieci 1:1000."""
        p = Parser2000("6.179.12.15")
        children = p.get_children()
        assert len(children) == 4
        godla = [c.godlo for c in children]
        assert godla == [
            "6.179.12.15.1",
            "6.179.12.15.2",
            "6.179.12.15.3",
            "6.179.12.15.4",
        ]

    def test_children_2k_to_1k_all_are_1k(self):
        """Wszystkie dzieci 1:2000 maja skale 1:1000."""
        p = Parser2000("6.179.12.15")
        children = p.get_children()
        for c in children:
            assert c.scale == "1:1000"

    # --- 1:1000 -> 1:500 (2x2) ---

    def test_children_1k_to_500(self):
        """1:1000 -> 4 dzieci 1:500."""
        p = Parser2000("6.179.12.15.2")
        children = p.get_children()
        assert len(children) == 4
        godla = [c.godlo for c in children]
        assert godla == [
            "6.179.12.15.2.1",
            "6.179.12.15.2.2",
            "6.179.12.15.2.3",
            "6.179.12.15.2.4",
        ]

    def test_children_1k_to_500_all_are_500(self):
        """Wszystkie dzieci 1:1000 maja skale 1:500."""
        p = Parser2000("6.179.12.15.2")
        children = p.get_children()
        for c in children:
            assert c.scale == "1:500"

    # --- Leaf nodes ---

    def test_children_500_empty(self):
        """1:500 nie ma dzieci — zwraca pusta liste."""
        p = Parser2000("6.179.12.15.2.4")
        assert p.get_children() == []

    def test_children_5k_empty(self):
        """1:5000 nie ma dzieci — zwraca pusta liste (liscie galezi 5k)."""
        p = Parser2000("6.179.12.3")
        assert p.get_children() == []

    # --- Return type ---

    def test_children_return_parser2000_instances(self):
        """get_children zwraca liste instancji Parser2000."""
        p = Parser2000("6.179.12")
        children = p.get_children()
        for c in children:
            assert isinstance(c, Parser2000)

    # --- Sorted output ---

    def test_children_10k_to_2k_sorted(self):
        """Dzieci 1:10000 -> 1:2000 sa posortowane wg godla."""
        p = Parser2000("6.179.12")
        children = p.get_children(scale="1:2000")
        godla = [c.godlo for c in children]
        assert godla == sorted(godla)

    # --- Different zones ---

    def test_children_different_zone(self):
        """get_children dziala poprawnie dla roznych stref."""
        p = Parser2000("8.100.5")
        children = p.get_children(scale="1:5000")
        assert len(children) == 4
        for c in children:
            assert c.zone == 8


# =========================================================================
# Hierarchia — get_all_descendants()
# =========================================================================


class TestParser2000GetAllDescendants:
    """Testy metody get_all_descendants()."""

    # --- Same scale ---

    def test_descendants_same_scale(self):
        """Ta sama skala -> zwraca [self]."""
        p = Parser2000("6.179.12")
        result = p.get_all_descendants("1:10000")
        assert len(result) == 1
        assert result[0] == p

    def test_descendants_same_scale_2k(self):
        """Ta sama skala 1:2000 -> zwraca [self]."""
        p = Parser2000("6.179.12.15")
        result = p.get_all_descendants("1:2000")
        assert len(result) == 1
        assert result[0] == p

    # --- 1:10000 -> various targets ---

    def test_descendants_10k_to_5k(self):
        """1:10000 -> 1:5000: 4 arkusze (galaz 5k)."""
        p = Parser2000("6.179.12")
        result = p.get_all_descendants("1:5000")
        assert len(result) == 4
        for d in result:
            assert d.scale == "1:5000"

    def test_descendants_10k_to_2k(self):
        """1:10000 -> 1:2000: 25 arkuszy."""
        p = Parser2000("6.179.12")
        result = p.get_all_descendants("1:2000")
        assert len(result) == 25
        for d in result:
            assert d.scale == "1:2000"

    def test_descendants_10k_to_1k(self):
        """1:10000 -> 1:1000: 25 * 4 = 100 arkuszy."""
        p = Parser2000("6.179.12")
        result = p.get_all_descendants("1:1000")
        assert len(result) == 100
        for d in result:
            assert d.scale == "1:1000"

    def test_descendants_10k_to_500(self):
        """1:10000 -> 1:500: 25 * 4 * 4 = 400 arkuszy."""
        p = Parser2000("6.179.12")
        result = p.get_all_descendants("1:500")
        assert len(result) == 400
        for d in result:
            assert d.scale == "1:500"

    # --- 1:2000 -> various targets ---

    def test_descendants_2k_to_1k(self):
        """1:2000 -> 1:1000: 4 arkusze."""
        p = Parser2000("6.179.12.15")
        result = p.get_all_descendants("1:1000")
        assert len(result) == 4

    def test_descendants_2k_to_500(self):
        """1:2000 -> 1:500: 4 * 4 = 16 arkuszy."""
        p = Parser2000("6.179.12.15")
        result = p.get_all_descendants("1:500")
        assert len(result) == 16
        for d in result:
            assert d.scale == "1:500"

    # --- 1:1000 -> 1:500 ---

    def test_descendants_1k_to_500(self):
        """1:1000 -> 1:500: 4 arkusze."""
        p = Parser2000("6.179.12.15.2")
        result = p.get_all_descendants("1:500")
        assert len(result) == 4

    # --- Sorted output ---

    def test_descendants_sorted(self):
        """Wyniki get_all_descendants sa posortowane wg godla."""
        p = Parser2000("6.179.12")
        result = p.get_all_descendants("1:1000")
        godla = [d.godlo for d in result]
        assert godla == sorted(godla)

    def test_descendants_10k_to_2k_sorted(self):
        """1:10000 -> 1:2000 posortowane: 01, 02, ..., 25."""
        p = Parser2000("6.179.12")
        result = p.get_all_descendants("1:2000")
        godla = [d.godlo for d in result]
        expected = [f"6.179.12.{i:02d}" for i in range(1, 26)]
        assert godla == expected

    # --- Coarser target raises error ---

    def test_descendants_coarser_raises(self):
        """Grubsza skala docelowa podnosi ValidationError."""
        p = Parser2000("6.179.12.15")
        with pytest.raises(ValidationError):
            p.get_all_descendants("1:10000")

    def test_descendants_5k_coarser_raises(self):
        """1:5000 -> 1:10000 podnosi ValidationError."""
        p = Parser2000("6.179.12.3")
        with pytest.raises(ValidationError):
            p.get_all_descendants("1:10000")

    def test_descendants_500_coarser_raises(self):
        """1:500 -> coarser scale podnosi ValidationError."""
        p = Parser2000("6.179.12.15.2.4")
        with pytest.raises(ValidationError):
            p.get_all_descendants("1:1000")

    # --- Leaf nodes ---

    def test_descendants_500_same_scale(self):
        """1:500 -> 1:500 zwraca [self]."""
        p = Parser2000("6.179.12.15.2.4")
        result = p.get_all_descendants("1:500")
        assert len(result) == 1
        assert result[0] == p

    def test_descendants_5k_same_scale(self):
        """1:5000 -> 1:5000 zwraca [self]."""
        p = Parser2000("6.179.12.3")
        result = p.get_all_descendants("1:5000")
        assert len(result) == 1
        assert result[0] == p

    # --- Cross-branch: 5k has no finer descendants ---

    def test_descendants_5k_to_2k_raises(self):
        """1:5000 -> 1:2000 podnosi ValidationError (5k jest lisciem)."""
        p = Parser2000("6.179.12.3")
        with pytest.raises(ValidationError):
            p.get_all_descendants("1:2000")

    def test_descendants_5k_to_1k_raises(self):
        """1:5000 -> 1:1000 podnosi ValidationError (5k jest lisciem)."""
        p = Parser2000("6.179.12.3")
        with pytest.raises(ValidationError):
            p.get_all_descendants("1:1000")

    def test_descendants_5k_to_500_raises(self):
        """1:5000 -> 1:500 podnosi ValidationError (5k jest lisciem)."""
        p = Parser2000("6.179.12.3")
        with pytest.raises(ValidationError):
            p.get_all_descendants("1:500")

    # --- Return type ---

    def test_descendants_return_parser2000_instances(self):
        """get_all_descendants zwraca liste instancji Parser2000."""
        p = Parser2000("6.179.12")
        result = p.get_all_descendants("1:2000")
        for d in result:
            assert isinstance(d, Parser2000)


# =========================================================================
# Hierarchia — get_hierarchy_up()
# =========================================================================


class TestParser2000GetHierarchyUp:
    """Testy metody get_hierarchy_up()."""

    def test_hierarchy_up_10k(self):
        """1:10000 -> [self] (jeden element)."""
        p = Parser2000("6.179.12")
        chain = p.get_hierarchy_up()
        assert len(chain) == 1
        assert chain[0] == p

    def test_hierarchy_up_5k(self):
        """1:5000 -> [self, parent_10k]."""
        p = Parser2000("6.179.12.3")
        chain = p.get_hierarchy_up()
        assert len(chain) == 2
        assert chain[0].godlo == "6.179.12.3"
        assert chain[0].scale == "1:5000"
        assert chain[1].godlo == "6.179.12"
        assert chain[1].scale == "1:10000"

    def test_hierarchy_up_2k(self):
        """1:2000 -> [self, parent_10k]."""
        p = Parser2000("6.179.12.15")
        chain = p.get_hierarchy_up()
        assert len(chain) == 2
        assert chain[0].godlo == "6.179.12.15"
        assert chain[1].godlo == "6.179.12"

    def test_hierarchy_up_1k(self):
        """1:1000 -> [self, parent_2k, parent_10k]."""
        p = Parser2000("6.179.12.15.2")
        chain = p.get_hierarchy_up()
        assert len(chain) == 3
        assert chain[0].godlo == "6.179.12.15.2"
        assert chain[0].scale == "1:1000"
        assert chain[1].godlo == "6.179.12.15"
        assert chain[1].scale == "1:2000"
        assert chain[2].godlo == "6.179.12"
        assert chain[2].scale == "1:10000"

    def test_hierarchy_up_500(self):
        """1:500 -> [self, parent_1k, parent_2k, parent_10k]."""
        p = Parser2000("6.179.12.15.2.4")
        chain = p.get_hierarchy_up()
        assert len(chain) == 4
        assert chain[0].godlo == "6.179.12.15.2.4"
        assert chain[0].scale == "1:500"
        assert chain[1].godlo == "6.179.12.15.2"
        assert chain[1].scale == "1:1000"
        assert chain[2].godlo == "6.179.12.15"
        assert chain[2].scale == "1:2000"
        assert chain[3].godlo == "6.179.12"
        assert chain[3].scale == "1:10000"

    def test_hierarchy_up_first_is_self(self):
        """Pierwszy element to zawsze self."""
        p = Parser2000("6.179.12.15.2")
        chain = p.get_hierarchy_up()
        assert chain[0] == p

    def test_hierarchy_up_last_is_10k(self):
        """Ostatni element to zawsze 1:10000."""
        p = Parser2000("6.179.12.15.2.4")
        chain = p.get_hierarchy_up()
        assert chain[-1].scale == "1:10000"

    def test_hierarchy_up_returns_parser2000_instances(self):
        """get_hierarchy_up zwraca liste instancji Parser2000."""
        p = Parser2000("6.179.12.15.2")
        chain = p.get_hierarchy_up()
        for item in chain:
            assert isinstance(item, Parser2000)


# =========================================================================
# find_sheets_2000_for_bbox
# =========================================================================


class TestFindSheets2000ForBBox:
    """Testy funkcji find_sheets_2000_for_bbox()."""

    # --- Pojedynczy arkusz 1:10000 ---

    def test_single_10k_sheet_native_crs(self):
        """Bbox wewnatrz jednego arkusza 1:10k -> zwraca dokladnie ten arkusz."""
        # Punkt wewnatrz 6.179.12 (zone 6, native CRS EPSG:2177)
        # Sheet bbox: south=5815000, north=5820000, west=6428000, east=6436000
        bbox = BBox(
            min_x=6430000, min_y=5816000, max_x=6434000, max_y=5818000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert result == ["6.179.12"]

    def test_single_10k_sheet_wgs84(self):
        """Bbox w WGS84 wewnatrz jednego arkusza 1:10k -> auto-detect zone."""
        # 6.179.12 WGS84 bbox: lon ~16.94-17.06, lat ~52.46-52.51
        bbox = BBox(min_x=16.97, min_y=52.47, max_x=17.03, max_y=52.50, crs="EPSG:4326")
        result = find_sheets_2000_for_bbox(bbox)
        assert result == ["6.179.12"]

    # --- Wiele arkuszy 1:10000 ---

    def test_multiple_10k_sheets(self):
        """Bbox rozciagajacy sie na kilka arkuszy 1:10k."""
        # Bbox covering 6.179.12 and 6.179.13 (adjacent columns)
        # 6.179.12: west=6428000, east=6436000
        # 6.179.13: west=6436000, east=6444000
        bbox = BBox(
            min_x=6434000, min_y=5816000, max_x=6438000, max_y=5818000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "6.179.12" in result
        assert "6.179.13" in result
        assert len(result) >= 2

    def test_multiple_10k_sheets_rows_and_cols(self):
        """Bbox rozciagajacy sie na 4 arkusze (2x2) 1:10k."""
        # Bbox crossing 6.179.12 / 6.179.13 / 6.180.12 / 6.180.13
        # Row boundary at northing=5820000
        # Col boundary at easting=6436000
        bbox = BBox(
            min_x=6434000, min_y=5818000, max_x=6438000, max_y=5822000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "6.179.12" in result
        assert "6.179.13" in result
        assert "6.180.12" in result
        assert "6.180.13" in result

    # --- Drill down do 1:2000 ---

    def test_drill_down_to_2k(self):
        """Bbox w jednym arkuszu 1:10k -> drill down to 1:2k, mniejsza ilosc."""
        # Maly bbox w srodku 6.179.12 -> powinien dac kilka arkuszy 1:2k
        bbox = BBox(
            min_x=6431000, min_y=5817000, max_x=6433000, max_y=5818500, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:2000")
        assert len(result) > 0
        # Wszystkie powinny byc potomkami 6.179.12
        for godlo in result:
            assert godlo.startswith("6.179.12.")
        # Nie powinno byc wiecej niz 25 (caly arkusz 10k to 25 ark. 2k)
        assert len(result) <= 25

    def test_small_bbox_fewer_2k_sheets(self):
        """Bardzo maly bbox -> mala ilosc arkuszy 1:2000."""
        # Bbox ~200m x 200m w srodku jednego 1:2k arkusza
        # 1:2000 sheet 6.179.12.13 bbox: S=5817000 N=5818000 W=6431200 E=6432800
        bbox = BBox(
            min_x=6431500, min_y=5817300, max_x=6431700, max_y=5817500, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:2000")
        assert len(result) == 1
        assert result == ["6.179.12.13"]

    def test_drill_down_full_10k_all_2k(self):
        """Bbox pokrywajacy caly arkusz 1:10k (lekko zmniejszony) -> 25 arkuszy 1:2k."""
        # Caly arkusz 6.179.12 — lekko scisniety, zeby nie zahaczac o sasiednie
        # (transformacja CRS powoduje lekkie poszerzenie na granicach)
        bbox = BBox(
            min_x=6428001, min_y=5815001, max_x=6435999, max_y=5819999, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:2000")
        assert len(result) == 25

    # --- Target 1:5000 ---

    def test_target_5k(self):
        """Target 1:5000 — zwraca kwadrenty 5k."""
        # Maly bbox w polnocno-zachodnim rogu 6.179.12 -> 1:5k kwadrant 1
        # 5k.1 (NW): south=5817500, north=5820000, west=6428000, east=6432000
        bbox = BBox(
            min_x=6429000, min_y=5818000, max_x=6431000, max_y=5819000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:5000")
        assert "6.179.12.1" in result
        assert len(result) >= 1

    def test_target_5k_all_four(self):
        """Target 1:5000 — caly arkusz 10k (lekko zmniejszony) -> 4 kwadrenty."""
        # Lekko scisniety, zeby nie zahaczac o sasiednie arkusze
        bbox = BBox(
            min_x=6428001, min_y=5815001, max_x=6435999, max_y=5819999, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:5000")
        assert len(result) == 4
        assert result == ["6.179.12.1", "6.179.12.2", "6.179.12.3", "6.179.12.4"]

    # --- WGS84 bbox z auto-detekcja strefy ---

    def test_wgs84_bbox_auto_detect_zone_6(self):
        """WGS84 bbox w strefie 6 (lon 16.5-19.5)."""
        # Punkt okolo Warszawy (lon ~18, lat ~52)
        p = Parser2000("6.179.12")
        wgs_bbox = p.get_bbox("EPSG:4326")
        # Uzyjmy bbox nieco mniejszy, zeby byc pewnym jednego arkusza
        bbox = BBox(
            min_x=wgs_bbox.min_x + 0.01,
            min_y=wgs_bbox.min_y + 0.01,
            max_x=wgs_bbox.max_x - 0.01,
            max_y=wgs_bbox.max_y - 0.01,
            crs="EPSG:4326",
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "6.179.12" in result

    def test_wgs84_bbox_auto_detect_zone_7(self):
        """WGS84 bbox w strefie 7 (lon 19.5-22.5)."""
        p = Parser2000("7.179.12")
        wgs_bbox = p.get_bbox("EPSG:4326")
        bbox = BBox(
            min_x=wgs_bbox.min_x + 0.01,
            min_y=wgs_bbox.min_y + 0.01,
            max_x=wgs_bbox.max_x - 0.01,
            max_y=wgs_bbox.max_y - 0.01,
            crs="EPSG:4326",
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "7.179.12" in result

    # --- Bbox w EPSG:2180 (PL-1992) ---

    def test_accept_epsg_2180_bbox(self):
        """Bbox w PL-1992 (EPSG:2180) — transformacja do WGS84 i auto-detect zone."""
        p = Parser2000("6.179.12")
        bbox_2180 = p.get_bbox("EPSG:2180")
        # Lekko zmniejsz bbox zeby byc w jednym arkuszu
        bbox = BBox(
            min_x=bbox_2180.min_x + 500,
            min_y=bbox_2180.min_y + 500,
            max_x=bbox_2180.max_x - 500,
            max_y=bbox_2180.max_y - 500,
            crs="EPSG:2180",
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "6.179.12" in result

    # --- Roundtrip: get_bbox -> find_sheets -> oryginalny arkusz ---

    def test_roundtrip_10k(self):
        """Roundtrip: get_bbox -> find_sheets -> oryginalne godlo w wynikach."""
        p = Parser2000("6.179.12")
        native_bbox = p.get_bbox()
        # Lekko scisniety bbox, zeby na pewno w srodku
        bbox = BBox(
            min_x=native_bbox.min_x + 100,
            min_y=native_bbox.min_y + 100,
            max_x=native_bbox.max_x - 100,
            max_y=native_bbox.max_y - 100,
            crs=native_bbox.crs,
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "6.179.12" in result

    def test_roundtrip_zone_5(self):
        """Roundtrip zone 5."""
        p = Parser2000("5.179.12")
        native_bbox = p.get_bbox()
        bbox = BBox(
            min_x=native_bbox.min_x + 100,
            min_y=native_bbox.min_y + 100,
            max_x=native_bbox.max_x - 100,
            max_y=native_bbox.max_y - 100,
            crs=native_bbox.crs,
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "5.179.12" in result

    def test_roundtrip_zone_8(self):
        """Roundtrip zone 8 — uzywamy arkusza centralnie w strefie."""
        # Arkusz 8.100.15 (lon ~23.3-23.5) jest bezpiecznie w strefie 8
        p = Parser2000("8.100.15")
        native_bbox = p.get_bbox()
        bbox = BBox(
            min_x=native_bbox.min_x + 100,
            min_y=native_bbox.min_y + 100,
            max_x=native_bbox.max_x - 100,
            max_y=native_bbox.max_y - 100,
            crs=native_bbox.crs,
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "8.100.15" in result

    def test_roundtrip_2k(self):
        """Roundtrip z target_scale 1:2000."""
        p = Parser2000("6.179.12.13")
        native_bbox = p.get_bbox()
        bbox = BBox(
            min_x=native_bbox.min_x + 10,
            min_y=native_bbox.min_y + 10,
            max_x=native_bbox.max_x - 10,
            max_y=native_bbox.max_y - 10,
            crs=native_bbox.crs,
        )
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:2000")
        assert "6.179.12.13" in result

    def test_roundtrip_wgs84(self):
        """Roundtrip z WGS84 bbox."""
        p = Parser2000("6.179.12")
        wgs_bbox = p.get_bbox("EPSG:4326")
        bbox = BBox(
            min_x=wgs_bbox.min_x + 0.01,
            min_y=wgs_bbox.min_y + 0.01,
            max_x=wgs_bbox.max_x - 0.01,
            max_y=wgs_bbox.max_y - 0.01,
            crs="EPSG:4326",
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert "6.179.12" in result

    # --- Explicit zone parameter ---

    def test_explicit_zone_parameter(self):
        """Jawne podanie strefy ogranicza wyszukiwanie do tej strefy."""
        # Bbox w strefie 6
        bbox = BBox(
            min_x=6430000, min_y=5816000, max_x=6434000, max_y=5818000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox, zone=6)
        assert "6.179.12" in result
        # Wszystkie wyniki sa w strefie 6
        for godlo in result:
            assert godlo.startswith("6.")

    def test_explicit_zone_wrong_zone_empty(self):
        """Jawna strefa inna niz faktyczna -> pusty wynik (brak przeciecia)."""
        # Bbox w natywnym CRS strefy 6, ale pytamy o strefe 7
        # W strefie 7 te wspolrzedne nie beda sensowne (rozne CRS)
        # Ale jesli bbox jest w WGS84 i jest w strefie 6, a pytamy o zone=7
        p = Parser2000("6.179.12")
        wgs_bbox = p.get_bbox("EPSG:4326")
        bbox = BBox(
            min_x=wgs_bbox.min_x + 0.01,
            min_y=wgs_bbox.min_y + 0.01,
            max_x=wgs_bbox.max_x - 0.01,
            max_y=wgs_bbox.max_y - 0.01,
            crs="EPSG:4326",
        )
        result = find_sheets_2000_for_bbox(bbox, zone=7)
        assert result == []

    # --- Posortowane wyniki ---

    def test_results_sorted(self):
        """Wyniki sa zawsze posortowane."""
        bbox = BBox(
            min_x=6434000, min_y=5818000, max_x=6438000, max_y=5822000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert result == sorted(result)

    def test_results_sorted_2k(self):
        """Wyniki 1:2000 sa posortowane."""
        bbox = BBox(
            min_x=6428000, min_y=5815000, max_x=6436000, max_y=5820000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:2000")
        assert result == sorted(result)

    # --- Bbox na granicy stref ---

    def test_bbox_spanning_two_zones(self):
        """Bbox na granicy stref 6 i 7 (lon ~19.5) -> arkusze z obu stref."""
        # Granica stref 6/7 jest na 19.5E
        bbox = BBox(min_x=19.4, min_y=52.0, max_x=19.6, max_y=52.1, crs="EPSG:4326")
        result = find_sheets_2000_for_bbox(bbox)
        # Powinny byc arkusze z obu stref
        has_zone_6 = any(g.startswith("6.") for g in result)
        has_zone_7 = any(g.startswith("7.") for g in result)
        assert has_zone_6
        assert has_zone_7

    # --- Zwracane typy ---

    def test_returns_list_of_strings(self):
        """Wynik to lista stringow."""
        bbox = BBox(
            min_x=6430000, min_y=5816000, max_x=6434000, max_y=5818000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    # --- Validacja godla: kazdy wynik to prawidlowe godlo ---

    def test_each_result_is_valid_godlo(self):
        """Kazdy wynik to prawidlowe godlo Parser2000."""
        bbox = BBox(
            min_x=6428000, min_y=5815000, max_x=6436000, max_y=5820000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox, target_scale="1:2000")
        for godlo in result:
            p = Parser2000(godlo)
            assert p.scale == "1:2000"

    def test_each_10k_result_is_valid(self):
        """Kazdy wynik 1:10k to prawidlowe godlo 1:10000."""
        bbox = BBox(
            min_x=6434000, min_y=5818000, max_x=6438000, max_y=5822000, crs="EPSG:2177"
        )
        result = find_sheets_2000_for_bbox(bbox)
        for godlo in result:
            p = Parser2000(godlo)
            assert p.scale == "1:10000"
