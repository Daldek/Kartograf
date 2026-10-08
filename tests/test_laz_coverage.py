"""
LAZ tile selection by area coverage (LAZ 2026-10-07, E2E C13 "duplicated area").

Two layers:

- the geometry of convex polygons (``kartograf.core.coverage``) - pure, no IO;
- ``GugikLazProvider.select_tiles`` on RAW WFS responses from the 2026-10-06
  round (area w2, Warsaw: a 2022 tile in PL-2000:S7 and the same area
  2023/2025 in PL-1992) and on synthetic tiles for the edge tolerance.
"""

from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from kartograf.core.coverage import (
    expand_convex,
    normalize_convex,
    polygon_area,
    rectangle,
    subtract_convex,
    uncovered_pieces,
)
from kartograf.core.sheet_parser import BBox
from kartograf.providers.pl.gugik_laz import (
    COVERAGE_TOLERANCE_M,
    GugikLazProvider,
    LazTile,
    select_newest_cover,
)

REAL_LAZ = Path(__file__).parent / "fixtures" / "gugik_laz" / "real_2026_10_06"

# Zadanie z rundy E2E (C13, L1): 50 x 50 m w Warszawie
W2_AREA = BBox(637400, 487000, 637450, 487050, "EPSG:2180")
NEW_1992 = "N-34-139-A-c-1-1-3-4"  # 2023 i 2025, PL-1992
OLD_2000 = "7.173.21.06.2"  # 2022, PL-2000:S7


def laz_session() -> MagicMock:
    """WFS z surowych XML rundy 2026-10-06 (GetCapabilities + GetFeature/rok)."""
    session = MagicMock()

    def get(url, **kwargs):
        query = parse_qs(urlparse(url).query)
        vcrs = "KRON86" if "LidarKRON86" in url else "EVRF2007"
        if query["REQUEST"][0] == "GetCapabilities":
            path = REAL_LAZ / f"caps_{vcrs}.xml"
        else:
            year = query["TYPENAMES"][0][-4:]
            path = REAL_LAZ / f"w2_{vcrs}_{year}.xml"
        response = MagicMock()
        response.text = path.read_text(encoding="utf-8")
        response.raise_for_status = MagicMock()
        return response

    session.get = MagicMock(side_effect=get)
    return session


def _square(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _tile(godlo, year, footprint, *, full_sheet=True, date=None, crs="PL-1992"):
    xs = [p[0] for p in footprint]
    ys = [p[1] for p in footprint]
    return LazTile(
        godlo=godlo,
        url=f"https://opendata.geoportal.gov.pl/x/{year}_{godlo}.laz",
        year=year,
        density=12,
        crs=crs,
        min_x=min(xs),
        min_y=min(ys),
        max_x=max(xs),
        max_y=max(ys),
        footprint=tuple(footprint),
        date=date,
        full_sheet=full_sheet,
    )


# =============================================================================
# Geometria wypuklych wielokatow
# =============================================================================


class TestConvexGeometry:
    def test_normalize_drops_closing_and_collinear_vertices(self):
        # realny kafel PL-1992 z Krakowa: 9 wierzcholkow (srodki bokow
        # wspolliniowe + zamkniecie) -> 4 wierzcholki
        ring = [
            (535834.31, 235351.46),
            (535830.44, 235930.44),
            (536390.29, 235934.21),
            (536950.14, 235938.04),
            (536954.13, 235359.07),
            (536958.12, 234780.09),
            (536398.15, 234776.26),
            (535838.18, 234772.49),
            (535834.31, 235351.46),
        ]
        poly = normalize_convex(ring)
        assert poly is not None
        assert len(poly) == 4
        assert polygon_area(poly) > 0  # CCW

    def test_normalize_orients_clockwise_ring_ccw(self):
        poly = normalize_convex([(0, 0), (0, 10), (10, 10), (10, 0)])
        assert poly is not None
        assert polygon_area(poly) == pytest.approx(100.0)

    def test_normalize_rejects_non_convex_and_degenerate(self):
        assert normalize_convex([(0, 0), (10, 0), (5, 2), (10, 10), (0, 10)]) is None
        assert normalize_convex([(0, 0), (5, 0), (10, 0)]) is None
        assert normalize_convex([(0, 0), (1, 1)]) is None

    def test_subtract_full_cover_leaves_nothing(self):
        assert subtract_convex(rectangle(0, 0, 10, 10), rectangle(-1, -1, 11, 11)) == []

    def test_subtract_half_cover_leaves_half(self):
        pieces = subtract_convex(rectangle(0, 0, 10, 10), rectangle(0, 0, 5, 10))
        assert sum(polygon_area(p) for p in pieces) == pytest.approx(50.0)

    def test_subtract_hole_inside_leaves_frame(self):
        pieces = subtract_convex(rectangle(0, 0, 10, 10), rectangle(2, 2, 8, 8))
        assert sum(polygon_area(p) for p in pieces) == pytest.approx(64.0)

    def test_expand_offsets_every_edge(self):
        grown = expand_convex(rectangle(0, 0, 10, 10), 1.0)
        assert polygon_area(grown) == pytest.approx(144.0)

    def test_uncovered_pieces_union_of_covers(self):
        region = rectangle(0, 0, 10, 10)
        covers = [rectangle(0, 0, 5, 10), rectangle(5, 0, 10, 10)]
        assert uncovered_pieces(region, covers) == []
        assert sum(
            polygon_area(p) for p in uncovered_pieces(region, covers[:1])
        ) == pytest.approx(50.0)


# =============================================================================
# Footprint z WFS (msGeometry, osie N,E)
# =============================================================================


class TestFootprintParsing:
    def test_real_pl2000_footprint_is_easting_northing(self):
        provider = GugikLazProvider(session=laz_session())
        (tile,) = provider.select_tiles(W2_AREA, year=2022).tiles
        assert tile.godlo == OLD_2000
        assert tile.footprint is not None
        # posList GUGiK: "486799.764986 637347.517691 ..." = (N, E)
        assert len(tile.footprint) == 4  # no closing vertex
        corners = {(round(x, 3), round(y, 3)) for x, y in tile.footprint}
        assert (637347.518, 486799.765) in corners  # SW: (E, N), not (N, E)
        assert (638133.109, 487321.447) in corners
        assert tile.date == "2022-05-09"
        assert tile.full_sheet is True


# =============================================================================
# Selekcja na surowym WFS w2
# =============================================================================


class TestSelectTilesOnRealWfs:
    def test_newest_tile_covers_area_older_systems_are_skipped(self):
        """C13 L1: 2025/PL-1992 pokrywa obszar -> 2022/PL-2000 i 2023 pominiete."""
        selection = GugikLazProvider(session=laz_session()).select_tiles(W2_AREA)
        assert [(t.godlo, t.year) for t in selection.tiles] == [(NEW_1992, 2025)]
        skipped = {(s.tile.godlo, s.tile.year): s for s in selection.superseded}
        assert set(skipped) == {(OLD_2000, 2022), (NEW_1992, 2023)}
        for entry in skipped.values():
            assert [(t.godlo, t.year) for t in entry.covered_by] == [(NEW_1992, 2025)]
            assert entry.reason == "covered"

    def test_discover_tiles_returns_the_selected_tiles(self):
        provider = GugikLazProvider(session=laz_session())
        assert [(t.godlo, t.year) for t in provider.discover_tiles(W2_AREA)] == [
            (NEW_1992, 2025)
        ]

    def test_older_tile_adding_uncovered_area_is_kept(self):
        # obszar wychodzi na wschod poza kafel 2025 (E <= 637617.67), w kafel
        # 2022 (E do ~638146) — kafel 2022 wnosi niepokryty kawalek
        area = BBox(637500, 487000, 637800, 487100, "EPSG:2180")
        selection = GugikLazProvider(session=laz_session()).select_tiles(area)
        assert sorted((t.godlo, t.year) for t in selection.tiles) == [
            (OLD_2000, 2022),
            (NEW_1992, 2025),
        ]
        assert [(s.tile.godlo, s.tile.year) for s in selection.superseded] == [
            (NEW_1992, 2023)
        ]

    def test_year_restricts_to_one_year_without_cross_year_dedup(self):
        selection = GugikLazProvider(session=laz_session()).select_tiles(
            W2_AREA, year=2022
        )
        assert [(t.godlo, t.year) for t in selection.tiles] == [(OLD_2000, 2022)]
        assert selection.superseded == ()

    def test_tile_whose_footprint_misses_area_is_skipped_as_outside(self):
        # SW corner of the PL-2000 tile envelope (rotated relative to EPSG:2180):
        # the envelope intersects the area, the tile polygon does not
        area = BBox(637334, 486800, 637340, 486806, "EPSG:2180")
        selection = GugikLazProvider(session=laz_session()).select_tiles(
            area, year=2022
        )
        assert selection.tiles == ()
        (entry,) = selection.superseded
        assert entry.tile.godlo == OLD_2000
        assert entry.covered_by == ()
        assert entry.reason == "outside"

    def test_kron86_newest_year_covers_2012(self):
        selection = GugikLazProvider(
            session=laz_session(), vertical_crs="KRON86"
        ).select_tiles(W2_AREA)
        assert [(t.godlo, t.year) for t in selection.tiles] == [(NEW_1992, 2018)]
        assert [(s.tile.year, s.reason) for s in selection.superseded] == [
            (2012, "covered")
        ]


# =============================================================================
# Regula zachlanna (kafle syntetyczne)
# =============================================================================


AREA = BBox(100, 100, 200, 200, "EPSG:2180")


class TestSelectNewestCover:
    def test_newest_first_regardless_of_input_order(self):
        old = _tile("OLD", 2020, _square(0, 0, 300, 300))
        new = _tile("NEW", 2024, _square(50, 50, 250, 250))
        for tiles in ([old, new], [new, old]):
            selection = select_newest_cover(tiles, AREA)
            assert [t.godlo for t in selection.tiles] == ["NEW"]
            assert [s.tile.godlo for s in selection.superseded] == ["OLD"]

    def test_union_of_newer_tiles_covers_older(self):
        old = _tile("OLD", 2020, _square(0, 0, 300, 300))
        west = _tile("W", 2024, _square(0, 0, 150, 300))
        east = _tile("E", 2024, _square(150, 0, 300, 300))
        selection = select_newest_cover([old, west, east], AREA)
        assert sorted(t.godlo for t in selection.tiles) == ["E", "W"]
        (entry,) = selection.superseded
        assert sorted(t.godlo for t in entry.covered_by) == ["E", "W"]

    def test_gap_within_tolerance_is_covered(self):
        # the newer tile ends 0.5 m before the area edge
        old = _tile("OLD", 2020, _square(0, 0, 300, 300))
        new = _tile("NEW", 2024, _square(0, 0, 199.5, 300))
        selection = select_newest_cover([old, new], AREA)
        assert [t.godlo for t in selection.tiles] == ["NEW"]
        assert COVERAGE_TOLERANCE_M == 1.0

    def test_gap_beyond_tolerance_keeps_older(self):
        old = _tile("OLD", 2020, _square(0, 0, 300, 300))
        new = _tile("NEW", 2024, _square(0, 0, 198, 300))
        selection = select_newest_cover([old, new], AREA)
        assert sorted(t.godlo for t in selection.tiles) == ["NEW", "OLD"]

    def test_zero_tolerance_keeps_older_for_half_metre_gap(self):
        old = _tile("OLD", 2020, _square(0, 0, 300, 300))
        new = _tile("NEW", 2024, _square(0, 0, 199.5, 300))
        selection = select_newest_cover([old, new], AREA, tolerance_m=0.0)
        assert sorted(t.godlo for t in selection.tiles) == ["NEW", "OLD"]

    def test_partial_newer_sheet_does_not_cover(self):
        """``czy_ark_wypelniony=NIE``: the footprint is the sheet frame, not the data
        extent."""
        old = _tile("OLD", 2020, _square(0, 0, 300, 300))
        new = _tile("NEW", 2024, _square(0, 0, 300, 300), full_sheet=False)
        selection = select_newest_cover([old, new], AREA)
        assert sorted(t.godlo for t in selection.tiles) == ["NEW", "OLD"]

    def test_same_year_duplicate_is_deduplicated_by_coverage(self):
        # sheet codes in reverse to dates: the newer akt_data wins, not sheet code order
        newer = _tile("Z", 2024, _square(0, 0, 300, 300), date="2024-08-01")
        older = _tile("A", 2024, _square(0, 0, 300, 300), date="2024-03-01")
        selection = select_newest_cover([older, newer], AREA)
        assert [t.godlo for t in selection.tiles] == ["Z"]
        assert [s.tile.godlo for s in selection.superseded] == ["A"]

    def test_older_tile_outside_newer_cover_kept(self):
        new = _tile("NEW", 2024, _square(0, 0, 150, 300))
        old = _tile("OLD", 2020, _square(150, 0, 300, 300))
        selection = select_newest_cover([new, old], AREA)
        assert sorted(t.godlo for t in selection.tiles) == ["NEW", "OLD"]
        assert selection.superseded == ()

    def test_tiles_without_geometry_are_kept(self):
        nan = float("nan")
        tile = LazTile("X", "u/x.laz", 2020, 12, "PL-1992", nan, nan, nan, nan)
        new = _tile("NEW", 2024, _square(0, 0, 300, 300))
        selection = select_newest_cover([tile, new], AREA)
        assert sorted(t.godlo for t in selection.tiles) == ["NEW", "X"]

    def test_same_godlo_covers_without_footprint(self):
        """A tile without msGeometry: the same sheet code (the same frame) still
        covers."""
        new = LazTile("SAME", "u/new.laz", 2024, 12, "PL-1992", 0, 0, 300, 300)
        old = LazTile("SAME", "u/old.laz", 2023, 12, "PL-1992", 0, 0, 300, 300)
        selection = select_newest_cover([old, new], AREA)
        assert [t.url for t in selection.tiles] == ["u/new.laz"]
        assert [s.tile.url for s in selection.superseded] == ["u/old.laz"]

    def test_envelope_alone_never_covers(self):
        """The envelope of a rotated frame sticks out past it - it must not cover."""
        new = LazTile("NEW", "u/new.laz", 2024, 12, "PL-1992", 0, 0, 300, 300)
        old = _tile("OLD", 2020, _square(0, 0, 300, 300))
        selection = select_newest_cover([old, new], AREA)
        assert sorted(t.godlo for t in selection.tiles) == ["NEW", "OLD"]

    def test_partial_same_godlo_does_not_cover(self):
        """Wroclaw 2025: two deliveries of NOT the same sheet - both stay."""
        a = _tile(
            "G", 2025, _square(0, 0, 300, 300), full_sheet=False, date="2025-08-12"
        )
        b = _tile(
            "G", 2025, _square(0, 0, 300, 300), full_sheet=False, date="2025-03-19"
        )
        selection = select_newest_cover([a, b], AREA)
        assert len(selection.tiles) == 2
