"""PL-2000 zones are areas: each zone's sheets only over its own powiats (ADR-055).

§ 22 of the regulation on the national spatial reference system (Dz.U. 2012
poz. 1247) puts the zone boundaries on powiat boundaries: a powiat that the
meridian 16.5, 19.5 or 22.5 E cuts belongs to the zone of its larger part.
The oracle here is independent of the shipped zone data: real PRG powiats
around each boundary (``tests/fixtures/pl2000_zones``, written by
``scripts/build_pl2000_zones.py --fixtures`` from the same PRG response, with
their own finer simplification) and the shipped TERYT -> zone table.
"""

import json
from importlib import resources
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import shapely
from pyproj import Transformer

from kartograf import BBox, find_sheet_outlines, find_sheets_for_bbox

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pl2000_zones"
_TO_2180 = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
_TO_WGS84 = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

# Views across each zone boundary, inside the window of their fixture.
VIEWS = {
    "lodz": (19.30, 51.70, 19.70, 51.85),
    "meridian_16_5": (16.35, 50.95, 16.65, 51.05),
    "meridian_22_5": (22.35, 51.20, 22.65, 51.30),
}
SCALES = ("1:10000", "1:2000")


def _metric(geometry: Any) -> Any:
    """A WGS84 geometry in EPSG:2180 (edges densified: straight in lon/lat)."""
    return shapely.transform(
        shapely.segmentize(geometry, 0.0002),
        lambda xy: np.column_stack(_TO_2180.transform(xy[:, 0], xy[:, 1])),
    )


def _m2(geometry: Any) -> float:
    return float(shapely.area(_metric(geometry)))


def _powiat_zones() -> dict[str, dict[str, Any]]:
    data = resources.files("kartograf").joinpath("_data", "pl2000_powiat_zones.json")
    rows = json.loads(data.read_text(encoding="utf-8"))["powiats"]
    return {row["teryt"]: row for row in rows}


def _powiats(name: str) -> list[tuple[str, Any, bool]]:
    """``(teryt, WGS84 geometry, clipped to the window)`` of a fixture."""
    path = FIXTURES / f"prg_powiats_{name}.geojson"
    document = json.loads(path.read_text(encoding="utf-8"))
    return [
        (
            feature["properties"]["teryt"],
            shapely.from_geojson(json.dumps(feature["geometry"])),
            feature["properties"]["clipped"],
        )
        for feature in document["features"]
    ]


def _outlines(name: str, scale: str) -> dict[int, list[Any]]:
    found: dict[int, list[Any]] = {}
    for sheet in find_sheet_outlines(BBox(*VIEWS[name], "EPSG:4326"), scale, "2000"):
        geometry = shapely.from_geojson(json.dumps(sheet.outline))
        found.setdefault(sheet.zone or 0, []).append(geometry)
    return found


@pytest.mark.parametrize("scale", SCALES)
@pytest.mark.parametrize("name", sorted(VIEWS))
def test_sheets_of_two_zones_never_overlap_and_cover_the_view(name, scale):
    """Across a zone boundary the map gets each zone's sheets on its own side:
    no interior of a sheet of one zone meets a sheet of the other (before:
    two whole grids over the whole view), and together they leave no gap.
    The download list is the same selection."""
    view = BBox(*VIEWS[name], "EPSG:4326")

    by_zone = _outlines(name, scale)
    codes = find_sheets_for_bbox(view, scale, "2000")

    assert len(by_zone) == 2, "the view crosses a zone boundary"
    for first, second in combinations(sorted(by_zone), 2):
        both = shapely.intersection(
            shapely.union_all(by_zone[first]), shapely.union_all(by_zone[second])
        )
        assert _m2(both) < 0.01, (first, second)
    drawn = shapely.union_all([g for parts in by_zone.values() for g in parts])
    assert _m2(shapely.difference(shapely.box(*VIEWS[name]), drawn)) < 0.01
    assert sorted(codes) == codes
    assert len(codes) == sum(len(parts) for parts in by_zone.values())
    assert {int(code.split(".")[0]) for code in codes} == set(by_zone)


@pytest.mark.parametrize("scale", SCALES)
@pytest.mark.parametrize("name", sorted(VIEWS))
def test_sheet_zone_is_the_zone_of_the_powiat_under_it(name, scale):
    """Every drawn part of a sheet lies over a powiat of the sheet's zone: the
    point of the part 1 m inside its edge (clear of the 0.5 m simplification
    of the zone data) falls in a PRG powiat whose zone is the sheet's."""
    zones = _powiat_zones()
    powiats = _powiats(name)
    document = json.loads((FIXTURES / f"prg_powiats_{name}.geojson").read_text())
    window = shapely.box(*document["window"])
    checked = 0

    for zone, parts in _outlines(name, scale).items():
        for part in shapely.get_parts(shapely.intersection(parts, window)):
            inner = shapely.buffer(_metric(part), -1.0)
            if inner.is_empty:
                continue  # a sliver narrower than 2 m
            point_2180 = shapely.point_on_surface(inner)
            point = shapely.Point(_TO_WGS84.transform(point_2180.x, point_2180.y))
            under = [t for t, g, _clipped in powiats if shapely.contains(g, point)]
            assert len(under) == 1, (zone, point)
            assert zones[under[0]]["zone"] == zone, (under[0], point)
            checked += 1

    assert checked > 0


def test_border_powiat_belongs_to_the_zone_of_its_larger_part():
    """§ 22 on a known cut powiat: Łódź (1061) lies on both sides of 19.5 E,
    the larger part (in EPSG:2180) west of it, so it is zone 6 - also its east
    part, where the nominal strip is zone 7."""
    lodz = next(g for t, g, clipped in _powiats("lodz") if t == "1061" and not clipped)
    west = shapely.intersection(lodz, shapely.box(16.5, 49.0, 19.5, 55.0))
    east = shapely.intersection(lodz, shapely.box(19.5, 49.0, 22.5, 55.0))
    row = _powiat_zones()["1061"]
    point = shapely.point_on_surface(east)

    sheets = find_sheets_for_bbox(
        BBox(point.x, point.y, point.x, point.y, "EPSG:4326"), "1:10000", "2000"
    )

    assert _m2(west) > _m2(east) > 0
    assert row["meridian"] == 19.5
    assert row["west_m2"] == pytest.approx(_m2(west), rel=1e-3)
    assert row["east_m2"] == pytest.approx(_m2(east), rel=1e-3)
    assert row["zone"] == 6
    assert len(sheets) == 1
    assert sheets[0].startswith("6.")
