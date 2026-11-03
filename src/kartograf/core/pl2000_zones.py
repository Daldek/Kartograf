"""
PL-2000 zone areas: the nominal strips with the powiat exceptions (ADR-055).

The regulation on the national spatial reference system (Dz.U. 2012 poz.
1247, § 22) puts the actual boundaries of the PL-2000 zones on powiat
boundaries: a powiat that the meridian 16.5, 19.5 or 22.5 E cuts belongs to
the zone of its larger part. A zone is therefore its nominal 3-degree strip
(``NOMINAL_STRIPS``, Annex 1 Table 12) without the parts of the cut powiats
that belong to the neighbouring zone, and with the parts of its own cut
powiats that lie in the neighbouring strip. Those parts (the exceptions) are
derived from the GUGiK PRG powiats by ``scripts/build_pl2000_zones.py`` and
ship in ``_data/pl2000_zones.json``; outside Poland, where § 22 has nothing
to say, a zone is its nominal strip.

All geometry here is WGS84 (EPSG:4326, longitude and latitude): a meridian
is a straight line there, so the exceptions meet the strips exactly and the
areas of two zones never overlap.
"""

import functools
import gzip
import json
from dataclasses import dataclass
from importlib import resources
from typing import Any

import shapely

# Nominal strips (west, east longitude) of the zones; the regulation's
# ranges of Annex 1 Table 12.
NOMINAL_STRIPS: dict[int, tuple[float, float]] = {
    5: (13.5, 16.5),
    6: (16.5, 19.5),
    7: (19.5, 22.5),
    8: (22.5, 25.5),
}

_DATA_FILE = "pl2000_zones.json.gz"


@dataclass(frozen=True)
class _ZoneException:
    """Parts of cut powiats lying in the nominal strip of another zone."""

    zone: int  # the zone of their powiats
    strip: int  # the nominal strip they lie in
    geometry: Any  # shapely MultiPolygon, WGS84
    bounds: tuple[float, float, float, float]


@functools.cache
def _exceptions() -> tuple[_ZoneException, ...]:
    """Read the exceptions of the package data once per process."""
    data = resources.files("kartograf").joinpath("_data", _DATA_FILE)
    document = json.loads(gzip.decompress(data.read_bytes()).decode("utf-8"))
    found = []
    for item in document["exceptions"]:
        geometry = shapely.from_geojson(json.dumps(item["geometry"]))
        min_x, min_y, max_x, max_y = (float(v) for v in geometry.bounds)
        found.append(
            _ZoneException(
                zone=int(item["zone"]),
                strip=int(item["strip"]),
                geometry=geometry,
                bounds=(min_x, min_y, max_x, max_y),
            )
        )
    return tuple(found)


def zone_area(zone: int, window: tuple[float, float, float, float]) -> Any:
    """
    Return the area of a PL-2000 zone inside a WGS84 window.

    Parameters
    ----------
    zone : int
        Zone number (5-8).
    window : tuple[float, float, float, float]
        ``(min_lon, min_lat, max_lon, max_lat)`` in EPSG:4326.

    Returns
    -------
    shapely.Geometry
        Polygon or MultiPolygon in EPSG:4326, empty when the zone does not
        reach the window.
    """
    min_lon, min_lat, max_lon, max_lat = window
    west, east = NOMINAL_STRIPS[zone]
    west, east = max(min_lon, west), min(max_lon, east)
    area = shapely.box(west, min_lat, east, max_lat) if west < east else None
    for exception in _exceptions():
        if zone not in (exception.zone, exception.strip):
            continue
        ex_min_lon, ex_min_lat, ex_max_lon, ex_max_lat = exception.bounds
        if (
            ex_min_lon >= max_lon
            or ex_max_lon <= min_lon
            or ex_min_lat >= max_lat
            or ex_max_lat <= min_lat
        ):
            continue
        part = shapely.clip_by_rect(exception.geometry, *window)
        if part.is_empty:
            continue
        if exception.zone == zone:
            area = part if area is None else shapely.union(area, part)
        elif area is not None:
            area = shapely.difference(area, part)
    return shapely.Polygon() if area is None else area


def zones_in(window: tuple[float, float, float, float]) -> list[int]:
    """Return the zones whose area covers part of a WGS84 window, ascending."""
    return [
        zone
        for zone in NOMINAL_STRIPS
        if float(shapely.area(zone_area(zone, window))) > 0.0
    ]
