"""
Testy weryfikacyjne dla modulu parser_2000.

Ten modul zawiera testy weryfikacyjne dla PL-2000 BBox:
- Wartosci referencyjne BBox dla wszystkich 4 stref
- Spojnosc hierarchii (children tiling)
- Testy live skorowidza GUGiK (marker ``live`` — tylko swiadomie, ``-m live``)
- Edge cases: multi-zone, round-trip, drill-down
"""

import datetime

import pytest

from kartograf.core.parser_2000 import (
    SHEET_DIMENSIONS_2000,
    ZONE_EPSG,
    Parser2000,
    find_sheets_2000_for_bbox,
)
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.providers.pl.skorowidz import query_skorowidz_layer

# =========================================================================
# 1. TestPL2000BBoxReferenceValues
# =========================================================================


# BBox formula for 1:10000:
#   south = pas * 5000 + 4_920_000
#   north = south + 5000
#   west  = strefa * 1_000_000 + slup * 8000 + 332_000
#   east  = west + 8000

# 5 test cases per zone (5, 6, 7, 8) = 20 total at 1:10000
REFERENCE_10K_CASES = [
    # Zone 5 (EPSG:2176)
    ("5.100.10", 5, 100, 10),
    ("5.150.20", 5, 150, 20),
    ("5.170.5", 5, 170, 5),
    ("5.180.30", 5, 180, 30),
    ("5.195.15", 5, 195, 15),
    # Zone 6 (EPSG:2177)
    ("6.100.10", 6, 100, 10),
    ("6.179.12", 6, 179, 12),
    ("6.150.25", 6, 150, 25),
    ("6.200.1", 6, 200, 1),
    ("6.185.18", 6, 185, 18),
    # Zone 7 (EPSG:2178)
    ("7.100.10", 7, 100, 10),
    ("7.160.8", 7, 160, 8),
    ("7.190.22", 7, 190, 22),
    ("7.175.14", 7, 175, 14),
    ("7.200.30", 7, 200, 30),
    # Zone 8 (EPSG:2179)
    ("8.100.10", 8, 100, 10),
    ("8.155.12", 8, 155, 12),
    ("8.170.20", 8, 170, 20),
    ("8.185.5", 8, 185, 5),
    ("8.195.25", 8, 195, 25),
]


class TestPL2000BBoxReferenceValues:
    """Weryfikacja BBox wedlug wzoru referencyjnego dla wszystkich stref."""

    @pytest.mark.parametrize(
        "godlo, strefa, pas, slup",
        REFERENCE_10K_CASES,
        ids=[c[0] for c in REFERENCE_10K_CASES],
    )
    def test_bbox_10k_matches_formula(self, godlo, strefa, pas, slup):
        """Weryfikacja BBox 1:10k zgodnie z formula referencyjne."""
        expected_south = pas * 5000 + 4_920_000
        expected_north = expected_south + 5000
        expected_west = strefa * 1_000_000 + slup * 8000 + 332_000
        expected_east = expected_west + 8000
        expected_crs = ZONE_EPSG[strefa]

        p = Parser2000(godlo)
        bbox = p.get_bbox()

        assert bbox.min_y == pytest.approx(expected_south, abs=0.01)
        assert bbox.max_y == pytest.approx(expected_north, abs=0.01)
        assert bbox.min_x == pytest.approx(expected_west, abs=0.01)
        assert bbox.max_x == pytest.approx(expected_east, abs=0.01)
        assert bbox.crs == expected_crs

    @pytest.mark.parametrize(
        "scale, expected_height, expected_width",
        [
            ("1:10000", 5000, 8000),
            ("1:5000", 2500, 4000),
            ("1:2000", 1000, 1600),
            ("1:1000", 500, 800),
            ("1:500", 250, 400),
        ],
        ids=["10k", "5k", "2k", "1k", "500"],
    )
    def test_sheet_dimensions_all_scales(self, scale, expected_height, expected_width):
        """Weryfikacja wymiarow arkuszy dla kazdej skali."""
        # Use a known valid godlo for each scale
        godla_per_scale = {
            "1:10000": "6.179.12",
            "1:5000": "6.179.12.1",
            "1:2000": "6.179.12.13",
            "1:1000": "6.179.12.13.1",
            "1:500": "6.179.12.13.1.1",
        }
        p = Parser2000(godla_per_scale[scale])
        bbox = p.get_bbox()

        height = bbox.max_y - bbox.min_y
        width = bbox.max_x - bbox.min_x

        assert height == pytest.approx(expected_height, abs=0.01)
        assert width == pytest.approx(expected_width, abs=0.01)

    @pytest.mark.parametrize(
        "scale, expected_height, expected_width",
        [(s, h, w) for s, (h, w) in SHEET_DIMENSIONS_2000.items()],
        ids=[s for s in SHEET_DIMENSIONS_2000],
    )
    def test_dimensions_match_constant(self, scale, expected_height, expected_width):
        """Weryfikacja ze SHEET_DIMENSIONS_2000 zgadza sie z obliczonymi wymiarami."""
        godla_per_scale = {
            "1:10000": "7.160.15",
            "1:5000": "7.160.15.2",
            "1:2000": "7.160.15.10",
            "1:1000": "7.160.15.10.3",
            "1:500": "7.160.15.10.3.2",
        }
        p = Parser2000(godla_per_scale[scale])
        bbox = p.get_bbox()

        actual_height = bbox.max_y - bbox.min_y
        actual_width = bbox.max_x - bbox.min_x

        assert actual_height == pytest.approx(expected_height, abs=0.01)
        assert actual_width == pytest.approx(expected_width, abs=0.01)

    @pytest.mark.parametrize("zone", [5, 6, 7, 8])
    def test_bbox_crs_matches_zone_epsg(self, zone):
        """Weryfikacja ze CRS zwracany przez get_bbox pasuje do strefy."""
        p = Parser2000(f"{zone}.150.10")
        bbox = p.get_bbox()
        assert bbox.crs == ZONE_EPSG[zone]

    @pytest.mark.parametrize("zone", [5, 6, 7, 8])
    def test_bbox_west_starts_with_zone_million(self, zone):
        """Weryfikacja ze west zaczyna sie od zone*1_000_000 + offset."""
        p = Parser2000(f"{zone}.150.10")
        bbox = p.get_bbox()
        expected_west = zone * 1_000_000 + 10 * 8000 + 332_000
        assert bbox.min_x == pytest.approx(expected_west, abs=0.01)


# =========================================================================
# 2. TestPL2000HierarchyConsistency
# =========================================================================


class TestPL2000HierarchyConsistency:
    """Testy spojnosci hierarchii — children tiling, brak overlap."""

    def test_5k_children_tile_exactly_over_parent(self):
        """4 dzieci 1:5000 pokrywaja dokladnie rodzica 1:10000."""
        parent = Parser2000("6.179.12")
        parent_bbox = parent.get_bbox()
        children = parent.get_children(scale="1:5000")

        assert len(children) == 4

        child_bboxes = [c.get_bbox() for c in children]

        # Union of children should equal parent
        assert min(b.min_y for b in child_bboxes) == pytest.approx(
            parent_bbox.min_y, abs=0.01
        )
        assert max(b.max_y for b in child_bboxes) == pytest.approx(
            parent_bbox.max_y, abs=0.01
        )
        assert min(b.min_x for b in child_bboxes) == pytest.approx(
            parent_bbox.min_x, abs=0.01
        )
        assert max(b.max_x for b in child_bboxes) == pytest.approx(
            parent_bbox.max_x, abs=0.01
        )

        # Total area of children should equal parent area
        parent_area = (parent_bbox.max_y - parent_bbox.min_y) * (
            parent_bbox.max_x - parent_bbox.min_x
        )
        children_area = sum(
            (b.max_y - b.min_y) * (b.max_x - b.min_x) for b in child_bboxes
        )
        assert children_area == pytest.approx(parent_area, abs=1.0)

    def test_2k_children_tile_exactly_over_parent(self):
        """25 dzieci 1:2000 pokrywaja dokladnie rodzica 1:10000."""
        parent = Parser2000("7.180.15")
        parent_bbox = parent.get_bbox()
        children = parent.get_children(scale="1:2000")

        assert len(children) == 25

        child_bboxes = [c.get_bbox() for c in children]

        # Union of children should equal parent
        assert min(b.min_y for b in child_bboxes) == pytest.approx(
            parent_bbox.min_y, abs=0.01
        )
        assert max(b.max_y for b in child_bboxes) == pytest.approx(
            parent_bbox.max_y, abs=0.01
        )
        assert min(b.min_x for b in child_bboxes) == pytest.approx(
            parent_bbox.min_x, abs=0.01
        )
        assert max(b.max_x for b in child_bboxes) == pytest.approx(
            parent_bbox.max_x, abs=0.01
        )

        # Total area of children should equal parent area
        parent_area = (parent_bbox.max_y - parent_bbox.min_y) * (
            parent_bbox.max_x - parent_bbox.min_x
        )
        children_area = sum(
            (b.max_y - b.min_y) * (b.max_x - b.min_x) for b in child_bboxes
        )
        assert children_area == pytest.approx(parent_area, abs=1.0)

    def test_1k_children_tile_over_2k_parent(self):
        """4 dzieci 1:1000 pokrywaja dokladnie rodzica 1:2000."""
        parent = Parser2000("8.170.10.13")
        parent_bbox = parent.get_bbox()
        children = parent.get_children()

        assert len(children) == 4

        child_bboxes = [c.get_bbox() for c in children]

        # Union of children should equal parent
        assert min(b.min_y for b in child_bboxes) == pytest.approx(
            parent_bbox.min_y, abs=0.01
        )
        assert max(b.max_y for b in child_bboxes) == pytest.approx(
            parent_bbox.max_y, abs=0.01
        )
        assert min(b.min_x for b in child_bboxes) == pytest.approx(
            parent_bbox.min_x, abs=0.01
        )
        assert max(b.max_x for b in child_bboxes) == pytest.approx(
            parent_bbox.max_x, abs=0.01
        )

        # Total area
        parent_area = (parent_bbox.max_y - parent_bbox.min_y) * (
            parent_bbox.max_x - parent_bbox.min_x
        )
        children_area = sum(
            (b.max_y - b.min_y) * (b.max_x - b.min_x) for b in child_bboxes
        )
        assert children_area == pytest.approx(parent_area, abs=1.0)

    def test_500_children_tile_over_1k_parent(self):
        """4 dzieci 1:500 pokrywaja dokladnie rodzica 1:1000."""
        parent = Parser2000("5.160.8.07.2")
        parent_bbox = parent.get_bbox()
        children = parent.get_children()

        assert len(children) == 4

        child_bboxes = [c.get_bbox() for c in children]

        assert min(b.min_y for b in child_bboxes) == pytest.approx(
            parent_bbox.min_y, abs=0.01
        )
        assert max(b.max_y for b in child_bboxes) == pytest.approx(
            parent_bbox.max_y, abs=0.01
        )
        assert min(b.min_x for b in child_bboxes) == pytest.approx(
            parent_bbox.min_x, abs=0.01
        )
        assert max(b.max_x for b in child_bboxes) == pytest.approx(
            parent_bbox.max_x, abs=0.01
        )

    def test_no_descendant_exceeds_ancestor_bbox(self):
        """Zaden potomek nie wychodzi poza BBox przodka."""
        ancestor = Parser2000("6.179.12")
        ancestor_bbox = ancestor.get_bbox()

        # Check 1:2000 descendants (25 sheets)
        for child_2k in ancestor.get_children(scale="1:2000"):
            child_bbox = child_2k.get_bbox()
            assert child_bbox.min_y >= ancestor_bbox.min_y - 0.01
            assert child_bbox.max_y <= ancestor_bbox.max_y + 0.01
            assert child_bbox.min_x >= ancestor_bbox.min_x - 0.01
            assert child_bbox.max_x <= ancestor_bbox.max_x + 0.01

        # Check 1:5000 descendants (4 sheets)
        for child_5k in ancestor.get_children(scale="1:5000"):
            child_bbox = child_5k.get_bbox()
            assert child_bbox.min_y >= ancestor_bbox.min_y - 0.01
            assert child_bbox.max_y <= ancestor_bbox.max_y + 0.01
            assert child_bbox.min_x >= ancestor_bbox.min_x - 0.01
            assert child_bbox.max_x <= ancestor_bbox.max_x + 0.01

        # Check 1:1000 descendants (100 sheets = 25 * 4)
        descendants_1k = ancestor.get_all_descendants("1:1000")
        assert len(descendants_1k) == 100
        for desc in descendants_1k:
            desc_bbox = desc.get_bbox()
            assert desc_bbox.min_y >= ancestor_bbox.min_y - 0.01
            assert desc_bbox.max_y <= ancestor_bbox.max_y + 0.01
            assert desc_bbox.min_x >= ancestor_bbox.min_x - 0.01
            assert desc_bbox.max_x <= ancestor_bbox.max_x + 0.01

    def test_no_5k_children_overlap(self):
        """Dzieci 1:5000 nie nakladaja sie (brak wspolnej powierzchni wewnetrznej)."""
        parent = Parser2000("6.179.12")
        children = parent.get_children(scale="1:5000")
        bboxes = [c.get_bbox() for c in children]

        for i in range(len(bboxes)):
            for j in range(i + 1, len(bboxes)):
                a, b = bboxes[i], bboxes[j]
                # Interior overlap = positive area of intersection
                overlap_width = min(a.max_x, b.max_x) - max(a.min_x, b.min_x)
                overlap_height = min(a.max_y, b.max_y) - max(a.min_y, b.min_y)
                # Allow touching (overlap=0) but no positive area
                if overlap_width > 0 and overlap_height > 0:
                    overlap_area = overlap_width * overlap_height
                    assert overlap_area == pytest.approx(0, abs=0.01), (
                        f"Children {children[i].godlo} and {children[j].godlo} overlap"
                    )

    def test_no_2k_children_overlap(self):
        """Dzieci 1:2000 nie nakladaja sie (brak wspolnej powierzchni wewnetrznej)."""
        parent = Parser2000("7.180.15")
        children = parent.get_children(scale="1:2000")
        bboxes = [c.get_bbox() for c in children]

        for i in range(len(bboxes)):
            for j in range(i + 1, len(bboxes)):
                a, b = bboxes[i], bboxes[j]
                overlap_width = min(a.max_x, b.max_x) - max(a.min_x, b.min_x)
                overlap_height = min(a.max_y, b.max_y) - max(a.min_y, b.min_y)
                if overlap_width > 0 and overlap_height > 0:
                    overlap_area = overlap_width * overlap_height
                    assert overlap_area == pytest.approx(0, abs=0.01), (
                        f"Children {children[i].godlo} and {children[j].godlo} overlap"
                    )

    def test_no_1k_children_overlap(self):
        """Dzieci 1:1000 nie nakladaja sie."""
        parent = Parser2000("6.179.12.13")
        children = parent.get_children()
        bboxes = [c.get_bbox() for c in children]

        for i in range(len(bboxes)):
            for j in range(i + 1, len(bboxes)):
                a, b = bboxes[i], bboxes[j]
                overlap_width = min(a.max_x, b.max_x) - max(a.min_x, b.min_x)
                overlap_height = min(a.max_y, b.max_y) - max(a.min_y, b.min_y)
                if overlap_width > 0 and overlap_height > 0:
                    overlap_area = overlap_width * overlap_height
                    assert overlap_area == pytest.approx(0, abs=0.01), (
                        f"Children {children[i].godlo} and {children[j].godlo} overlap"
                    )

    def test_hierarchy_tiling_multiple_zones(self):
        """Weryfikacja tiling consistency w roznych strefach."""
        for zone in [5, 6, 7, 8]:
            parent = Parser2000(f"{zone}.150.10")
            parent_bbox = parent.get_bbox()

            # 5k children
            children_5k = parent.get_children(scale="1:5000")
            assert len(children_5k) == 4
            area_5k = sum(
                (c.get_bbox().max_y - c.get_bbox().min_y)
                * (c.get_bbox().max_x - c.get_bbox().min_x)
                for c in children_5k
            )
            parent_area = (parent_bbox.max_y - parent_bbox.min_y) * (
                parent_bbox.max_x - parent_bbox.min_x
            )
            assert area_5k == pytest.approx(parent_area, abs=1.0)

            # 2k children
            children_2k = parent.get_children(scale="1:2000")
            assert len(children_2k) == 25
            area_2k = sum(
                (c.get_bbox().max_y - c.get_bbox().min_y)
                * (c.get_bbox().max_x - c.get_bbox().min_x)
                for c in children_2k
            )
            assert area_2k == pytest.approx(parent_area, abs=1.0)


# =========================================================================
# 3. TestLiveGugikIndex
# =========================================================================

# Godla PL-2000 1:10000 (interior PL, pokrycie NMT 1 m): zapytanie w srodku
# arkusza sprawdza geometrie Parser2000 wzgledem poligonow skorowidza GUGiK.
LIVE_WMS_SHEETS = [
    # Zone 5 — western Poland
    ("5.176.14", 5),  # near Szczecin area
    ("5.180.10", 5),  # further west
    # Zone 6 — central-west Poland
    ("6.179.12", 6),  # Bialystok area reference
    ("6.175.15", 6),  # central Poland
    ("6.185.20", 6),  # another central sheet
    # Zone 7 — central-east Poland
    ("7.170.12", 7),  # eastern Poland
    ("7.180.8", 7),  # central-east
    # Zone 8 — eastern Poland
    ("8.170.10", 8),  # far east
]

LIVE_TIMEOUT = 15

# (provider, endpoint, rotacja roczna) — kazdy publiczny skorowidz PL; KRON86
# to produkt zamrozony (2019..2017iStarsze), bez nowych warstw rocznych
LIVE_INDEX_ENDPOINTS = [
    pytest.param(
        GugikProvider(resolution="1m", vertical_crs="EVRF2007"),
        GugikProvider.WMS_SKOROWIDZE_ENDPOINTS["1m"]["EVRF2007"],
        True,
        id="nmt-1m-evrf2007",
    ),
    pytest.param(
        GugikProvider(resolution="1m", vertical_crs="KRON86"),
        GugikProvider.WMS_SKOROWIDZE_ENDPOINTS["1m"]["KRON86"],
        False,
        id="nmt-1m-kron86",
    ),
    pytest.param(
        GugikProvider(resolution="5m"),
        GugikProvider.WMS_SKOROWIDZE_ENDPOINTS["5m"]["EVRF2007"],
        True,
        id="nmt-5m-evrf2007",
    ),
    pytest.param(
        GugikNmptProvider(vertical_crs="EVRF2007"),
        GugikNmptProvider.WMS_SKOROWIDZE_ENDPOINTS["1m"]["EVRF2007"],
        True,
        id="nmpt-1m-evrf2007",
    ),
    pytest.param(
        GugikOrtoProvider(),
        GugikOrtoProvider.WMS_SKOROWIDZE_ENDPOINT,
        True,
        id="orto",
    ),
]


def _center_query_bbox(godlo: str) -> tuple[float, float, str]:
    """Punkt w srodku arkusza (EPSG:2180) i BBOX GetFeatureInfo jak w providerach."""
    bbox = SheetParser(godlo).get_bbox(crs="EPSG:2180")
    x = (bbox.min_x + bbox.max_x) / 2
    y = (bbox.min_y + bbox.max_y) / 2
    return x, y, f"{y - 10},{x - 10},{y + 10},{x + 10}"


@pytest.mark.live
@pytest.mark.real_wms_layers
class TestLiveGugikIndex:
    """Skorowidz GUGiK na zywo: warstwy, wybor arkusza, brak pokrycia, geometria.

    Zadnych ``skip`` na bledach: awaria uslugi po 3 probach = porazka testu
    (to jedyny sygnal, ze S1/S4/K3 wrocily). Uruchomienie: ``pytest -m live``.
    """

    @pytest.mark.parametrize(("provider", "endpoint", "rotates"), LIVE_INDEX_ENDPOINTS)
    def test_getcapabilities_layers_match_pattern_and_rotate(
        self, provider, endpoint, rotates
    ):
        """Warstwy z LAYER_PATTERN: roczne malejaco, JEDNA warstwa zbiorcza na
        koncu, produkt aktualizowany ma warstwe biezacego/zeszlego roku —
        coroczna rotacja i zmiana nazw (S4) sa widoczne tylko tutaj."""
        layers = provider._layers(endpoint)

        assert layers, endpoint
        matches = [provider.LAYER_PATTERN.fullmatch(name) for name in layers]
        assert all(matches), layers
        years = [int(m.group(1)) for m in matches if m.group(1)]
        cumulative = [n for n, m in zip(layers, matches, strict=True) if m.group(2)]
        assert years == sorted(years, reverse=True), layers
        assert len(set(years)) == len(years), layers
        assert len(cumulative) == 1 and layers[-1] == cumulative[0], layers
        if rotates:
            assert years[0] >= datetime.date.today().year - 1, layers

    def test_land_sheet_resolves_to_matching_asc(self):
        """D4 na zywo: URL z godlem jako CALYM tokenem i rozdzielczoscia 5 m."""
        provider = GugikProvider(resolution="5m")

        url = provider._get_opendata_url("N-33-48-C-a-3-4", timeout=LIVE_TIMEOUT)

        assert url.startswith("https://opendata.geoportal.gov.pl/")
        assert url.lower().endswith("_n-33-48-c-a-3-4.asc"), url
        source = provider.source_info("N-33-48-C-a-3-4")
        assert source is not None
        assert source["resolution_m"] == 5.0
        assert source["uklad"] == "PL-1992"
        assert source["layer"] in provider._layers(
            GugikProvider.WMS_SKOROWIDZE_ENDPOINTS["5m"]["EVRF2007"]
        )

    def test_sea_sheet_is_no_coverage(self):
        """Morze (N-33-48-C-a-1-3): wszystkie warstwy puste = NoCoverageError (R5)."""
        provider = GugikProvider(resolution="5m")

        with pytest.raises(NoCoverageError) as exc:
            provider._get_opendata_url("N-33-48-C-a-1-3", timeout=LIVE_TIMEOUT)

        assert exc.value.godlo == "N-33-48-C-a-1-3"

    def test_unknown_layer_is_service_exception_not_no_coverage(self):
        """Nieistniejaca warstwa: raport OGC = DownloadError, nigdy brak pokrycia."""
        provider = GugikProvider()
        _, _, query_bbox = _center_query_bbox("N-33-48-C-a-3-4")

        with pytest.raises(DownloadError, match="OGC") as exc:
            query_skorowidz_layer(
                provider._sessions.get(),
                GugikProvider.WMS_SKOROWIDZE_ENDPOINTS["1m"]["EVRF2007"],
                "SkorowidzeNMT1999NieIstnieje",
                query_bbox=query_bbox,
                godlo="N-33-48-C-a-3-4",
                timeout=LIVE_TIMEOUT,
            )

        assert not isinstance(exc.value, NoCoverageError)

    @pytest.mark.parametrize(
        ("godlo", "zone"), LIVE_WMS_SHEETS, ids=[s[0] for s in LIVE_WMS_SHEETS]
    )
    def test_pl2000_center_query_returns_sheets_containing_the_point(self, godlo, zone):
        """Geometria PL-2000 vs skorowidz GUGiK: srodek arkusza trafia w rekordy
        NMT 1 m, a bbox KAZDEGO zwroconego godla (PL-1992 albo PL-2000 wlasciwej
        strefy) zawiera punkt zapytania."""
        provider = GugikProvider(resolution="1m", vertical_crs="EVRF2007")
        endpoint = GugikProvider.WMS_SKOROWIDZE_ENDPOINTS["1m"]["EVRF2007"]
        x, y, query_bbox = _center_query_bbox(godlo)

        records = []
        for layer in provider._layers(endpoint):
            records.extend(
                query_skorowidz_layer(
                    provider._sessions.get(),
                    endpoint,
                    layer,
                    query_bbox=query_bbox,
                    godlo=godlo,
                    timeout=LIVE_TIMEOUT,
                )
            )

        assert records, f"{godlo}: zaden rekord NMT 1 m w srodku arkusza"
        for record in records:
            sheet = SheetParser(record.godlo).get_bbox(crs="EPSG:2180")
            assert sheet.min_x - 1 <= x <= sheet.max_x + 1, (godlo, record.godlo)
            assert sheet.min_y - 1 <= y <= sheet.max_y + 1, (godlo, record.godlo)
            assert record.uklad in {"1992", "2000"}, record
            if record.uklad == "2000":
                assert record.zone == zone, record
                assert record.godlo.startswith(f"{zone}."), record
                assert record.raw["ukladWspolrzednychPoziomych"] == (f"PL-2000:S{zone}")


# =========================================================================
# 4. TestPL2000EdgeCases
# =========================================================================


class TestPL2000EdgeCases:
    """Edge cases — multi-zone, round-trip, single point, zone forced, drill-down."""

    def test_multi_zone_bbox_crossing_16_5(self):
        """BBox przecinajacy granice stref 5/6 (16.5E) zwraca arkusze z obu stref."""
        # BBox in WGS84 crossing 16.5E (zone 5/6 boundary)
        bbox = BBox(min_x=16.3, min_y=52.0, max_x=16.7, max_y=52.1, crs="EPSG:4326")
        sheets = find_sheets_2000_for_bbox(bbox)

        zones_found = set()
        for godlo in sheets:
            zone = int(godlo.split(".")[0])
            zones_found.add(zone)

        assert 5 in zones_found, "Should find sheets in zone 5"
        assert 6 in zones_found, "Should find sheets in zone 6"

    def test_multi_zone_bbox_crossing_19_5(self):
        """BBox przecinajacy granice stref 6/7 (19.5E) zwraca arkusze z obu stref."""
        bbox = BBox(min_x=19.3, min_y=52.0, max_x=19.7, max_y=52.1, crs="EPSG:4326")
        sheets = find_sheets_2000_for_bbox(bbox)

        zones_found = set()
        for godlo in sheets:
            zone = int(godlo.split(".")[0])
            zones_found.add(zone)

        assert 6 in zones_found, "Should find sheets in zone 6"
        assert 7 in zones_found, "Should find sheets in zone 7"

    def test_multi_zone_bbox_crossing_22_5(self):
        """BBox przecinajacy granice stref 7/8 (22.5E) zwraca arkusze z obu stref."""
        bbox = BBox(min_x=22.3, min_y=52.0, max_x=22.7, max_y=52.1, crs="EPSG:4326")
        sheets = find_sheets_2000_for_bbox(bbox)

        zones_found = set()
        for godlo in sheets:
            zone = int(godlo.split(".")[0])
            zones_found.add(zone)

        assert 7 in zones_found, "Should find sheets in zone 7"
        assert 8 in zones_found, "Should find sheets in zone 8"

    def test_round_trip_godlo_to_bbox_and_back(self):
        """Round-trip: godlo -> BBox -> find_sheets -> zawiera oryginal."""
        test_godla = [
            "5.170.10",
            "6.179.12",
            "7.180.15",
            "8.175.8",
        ]
        for godlo in test_godla:
            p = Parser2000(godlo)
            bbox = p.get_bbox()

            # Shrink bbox slightly inward to ensure we are inside the sheet
            epsilon = 1.0  # 1 meter inward
            inner_bbox = BBox(
                min_x=bbox.min_x + epsilon,
                min_y=bbox.min_y + epsilon,
                max_x=bbox.max_x - epsilon,
                max_y=bbox.max_y - epsilon,
                crs=bbox.crs,
            )

            sheets = find_sheets_2000_for_bbox(inner_bbox)
            assert godlo in sheets, (
                f"Round-trip failed: {godlo} not found in "
                f"find_sheets_2000_for_bbox result {sheets}"
            )

    def test_single_point_bbox_finds_exactly_one_sheet(self):
        """Punkt (BBox z zerowa powierzchnia) powinien znalezc dokladnie 1 arkusz."""
        # Use center of a known sheet
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()
        center_x = (bbox.min_x + bbox.max_x) / 2
        center_y = (bbox.min_y + bbox.max_y) / 2

        point_bbox = BBox(
            min_x=center_x,
            min_y=center_y,
            max_x=center_x,
            max_y=center_y,
            crs=bbox.crs,
        )

        sheets = find_sheets_2000_for_bbox(point_bbox)
        assert len(sheets) == 1
        assert sheets[0] == "6.179.12"

    def test_zone_forced_parameter_limits_search(self):
        """Parametr zone ogranicza wyszukiwanie do jednej strefy."""
        # BBox that could span multiple zones in WGS84
        bbox = BBox(min_x=16.3, min_y=52.0, max_x=16.7, max_y=52.1, crs="EPSG:4326")

        # Without zone restriction — finds from both zones
        sheets_all = find_sheets_2000_for_bbox(bbox)
        zones_all = {int(g.split(".")[0]) for g in sheets_all}

        # With zone restriction — only one zone
        sheets_z5 = find_sheets_2000_for_bbox(bbox, zone=5)
        zones_z5 = {int(g.split(".")[0]) for g in sheets_z5}

        sheets_z6 = find_sheets_2000_for_bbox(bbox, zone=6)
        zones_z6 = {int(g.split(".")[0]) for g in sheets_z6}

        # zone=5 should only return zone 5 sheets
        assert zones_z5 == {5} or len(sheets_z5) == 0
        # zone=6 should only return zone 6 sheets
        assert zones_z6 == {6} or len(sheets_z6) == 0

        # Together they should cover at least what the unrestricted search finds
        # (possibly more, since zone projection might clip differently)
        assert len(zones_all) >= 2, "Unrestricted search should span zones"

    def test_drill_down_to_5000(self):
        """Drill-down do skali 1:5000 — wynik zawiera arkusze 1:5000."""
        # Use center of a known sheet
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()

        # Shrink slightly inward
        epsilon = 100.0
        inner_bbox = BBox(
            min_x=bbox.min_x + epsilon,
            min_y=bbox.min_y + epsilon,
            max_x=bbox.max_x - epsilon,
            max_y=bbox.max_y - epsilon,
            crs=bbox.crs,
        )

        sheets = find_sheets_2000_for_bbox(inner_bbox, target_scale="1:5000")

        # All sheets should be 1:5000 scale (4 segments dot-separated)
        for godlo in sheets:
            p_child = Parser2000(godlo)
            assert p_child.scale == "1:5000"

        # Should find all 4 children of parent 6.179.12
        assert len(sheets) == 4
        expected = {"6.179.12.1", "6.179.12.2", "6.179.12.3", "6.179.12.4"}
        assert set(sheets) == expected

    def test_drill_down_to_2000(self):
        """Drill-down do skali 1:2000 — wynik zawiera arkusze 1:2000."""
        p = Parser2000("7.180.15")
        bbox = p.get_bbox()

        epsilon = 100.0
        inner_bbox = BBox(
            min_x=bbox.min_x + epsilon,
            min_y=bbox.min_y + epsilon,
            max_x=bbox.max_x - epsilon,
            max_y=bbox.max_y - epsilon,
            crs=bbox.crs,
        )

        sheets = find_sheets_2000_for_bbox(inner_bbox, target_scale="1:2000")

        # All sheets should be 1:2000 scale
        for godlo in sheets:
            p_child = Parser2000(godlo)
            assert p_child.scale == "1:2000"

        # Should find all 25 children of parent 7.180.15
        assert len(sheets) == 25

    def test_drill_down_partial_coverage(self):
        """Drill-down z czesciowym pokryciem — nie wszystkie dzieci."""
        # Small bbox covering only part of one 1:10000 sheet
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()

        # Take only NW quarter of the sheet (roughly 1:5000 quadrant 1 area)
        partial_bbox = BBox(
            min_x=bbox.min_x + 100,
            min_y=(bbox.min_y + bbox.max_y) / 2 + 100,
            max_x=(bbox.min_x + bbox.max_x) / 2 - 100,
            max_y=bbox.max_y - 100,
            crs=bbox.crs,
        )

        sheets_5k = find_sheets_2000_for_bbox(partial_bbox, target_scale="1:5000")

        # Should find only 1 child (quadrant 1 = NW)
        assert len(sheets_5k) == 1
        assert sheets_5k[0] == "6.179.12.1"

    def test_round_trip_finer_scales(self):
        """Round-trip dla drobniejszych skal: 1:5k i 1:2k."""
        # 1:5000 round-trip
        godlo_5k = "6.179.12.3"
        p5k = Parser2000(godlo_5k)
        bbox_5k = p5k.get_bbox()
        epsilon = 1.0
        inner_5k = BBox(
            min_x=bbox_5k.min_x + epsilon,
            min_y=bbox_5k.min_y + epsilon,
            max_x=bbox_5k.max_x - epsilon,
            max_y=bbox_5k.max_y - epsilon,
            crs=bbox_5k.crs,
        )
        sheets_5k = find_sheets_2000_for_bbox(inner_5k, target_scale="1:5000")
        assert godlo_5k in sheets_5k

        # 1:2000 round-trip
        godlo_2k = "7.180.15.13"
        p2k = Parser2000(godlo_2k)
        bbox_2k = p2k.get_bbox()
        inner_2k = BBox(
            min_x=bbox_2k.min_x + epsilon,
            min_y=bbox_2k.min_y + epsilon,
            max_x=bbox_2k.max_x - epsilon,
            max_y=bbox_2k.max_y - epsilon,
            crs=bbox_2k.crs,
        )
        sheets_2k = find_sheets_2000_for_bbox(inner_2k, target_scale="1:2000")
        assert godlo_2k in sheets_2k

    def test_bbox_in_epsg2180_finds_sheets(self):
        """BBox w EPSG:2180 (PL-1992) jest poprawnie obslugiwany."""
        # Transform known sheet BBox to EPSG:2180
        p = Parser2000("6.179.12")
        bbox_2180 = p.get_bbox(crs="EPSG:2180")

        epsilon = 100.0
        inner_bbox = BBox(
            min_x=bbox_2180.min_x + epsilon,
            min_y=bbox_2180.min_y + epsilon,
            max_x=bbox_2180.max_x - epsilon,
            max_y=bbox_2180.max_y - epsilon,
            crs="EPSG:2180",
        )

        sheets = find_sheets_2000_for_bbox(inner_bbox)
        assert "6.179.12" in sheets

    def test_bbox_in_native_zone_crs(self):
        """BBox w natywnym CRS strefy (EPSG:2177) jest poprawnie obslugiwany."""
        p = Parser2000("6.179.12")
        bbox = p.get_bbox()  # native EPSG:2177

        epsilon = 100.0
        inner_bbox = BBox(
            min_x=bbox.min_x + epsilon,
            min_y=bbox.min_y + epsilon,
            max_x=bbox.max_x - epsilon,
            max_y=bbox.max_y - epsilon,
            crs=bbox.crs,
        )

        sheets = find_sheets_2000_for_bbox(inner_bbox)
        assert "6.179.12" in sheets
