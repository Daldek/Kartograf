"""Build the PL-2000 zone data of Kartograf from the GUGiK PRG powiats (ADR-055).

The regulation on the national spatial reference system (Rozporządzenie Rady
Ministrów z dnia 15 października 2012 r. w sprawie państwowego systemu
odniesień przestrzennych, Dz.U. 2012 poz. 1247, § 22) puts the actual
boundaries of the PL-2000 zones on powiat boundaries: a powiat that the
meridian 16.5, 19.5 or 22.5 E cuts belongs to the zone of its larger part.
The regulation gives that rule, not a list, so this script derives the list
from the PRG layer ``A02_Granice_powiatow``:

1. one WFS GetFeature request for every powiat with its geometry
   (EPSG:2180) - the only network access; ``--source`` reads a saved
   response instead;
2. the zone of every powiat: the nominal 3-degree strip it lies in or, for a
   powiat a boundary meridian cuts, the strip of its larger part (areas in
   EPSG:2180);
3. the exceptions to the nominal strips: the parts of the cut powiats on the
   smaller side of their meridian, cut exactly along the meridian in WGS84,
   merged per meridian and side and simplified (Douglas-Peucker,
   ``TOLERANCE_DEG``; checked against the PRG boundary in metres).

Writes ``src/kartograf/_data/pl2000_zones.json.gz`` (the exceptions, read by
``kartograf.core.pl2000_zones``; gzip keeps the 1 cm coordinates under 1 MB)
and ``src/kartograf/_data/pl2000_powiat_zones.json`` (TERYT -> zone, with
both areas of every cut powiat). The tests never run it.

Usage::

    uv run scripts/build_pl2000_zones.py --save prg.xml    # fetch, keep, build
    uv run scripts/build_pl2000_zones.py --source prg.xml  # build from a file
"""

import argparse
import gzip
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import requests
import shapely
from pyproj import Transformer

from kartograf.core.pl2000_zones import NOMINAL_STRIPS
from kartograf.providers.pl.prg import (
    _GML,
    _MS,
    _WFS_MEMBER,
    POWIAT_LAYER,
    PRG_WFS_ENDPOINT,
    _check_complete,
    _feature_collection,
    _polygon,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "src" / "kartograf" / "_data"
ZONES_FILE = DATA / "pl2000_zones.json.gz"
POWIATS_FILE = DATA / "pl2000_powiat_zones.json"

RULE = (
    "Rozporządzenie Rady Ministrów z dnia 15 października 2012 r. w sprawie"
    " państwowego systemu odniesień przestrzennych (Dz.U. 2012 poz. 1247), § 22:"
    " faktyczne granice pasów południkowych w układzie współrzędnych PL-2000"
    " wyznacza się wzdłuż granic jednostek administracyjnych szczebla"
    " powiatowego, przy czym w przypadku jednostek administracyjnych"
    " przecinanych na dwie części przez południki graniczne pasów południkowych:"
    " 16,5ºE, 19,5ºE lub 22,5ºE o przynależności obszaru powiatu do określonego"
    " pasa południkowego przesądza część o większej powierzchni."
)
LICENCE = {
    "id": "PL-PGiK-40a",
    "attribution": (
        "Dane: Glowny Urzad Geodezji i Kartografii (www.geoportal.gov.pl), "
        "art. 40a ust. 2 pkt 1 ustawy Prawo geodezyjne i kartograficzne"
    ),
}
# Boundary meridians between the nominal strips: (west zone, east zone).
MERIDIANS = {16.5: (5, 6), 19.5: (6, 7), 22.5: (7, 8)}
# Douglas-Peucker tolerance in degrees: 4.5e-6 deg is 0.50 m of latitude and
# 0.31 m of longitude at 52 N (the check below measures it in metres).
TOLERANCE_DEG = 4.5e-6
# Coordinates are written with 7 decimals (1 cm).
PRECISION_DEG = 1e-7
# PRG segments are straight in EPSG:2180, the stored ones in WGS84: 100 m
# segments differ by < 1 mm (the curvature of a straight EPSG:2180 line in
# longitude and latitude).
DENSIFY_M = 100.0
# The largest allowed distance between a stored exception and its PRG boundary.
MAX_ERROR_M = 1.0
# A part of a powiat on one side of a meridian smaller than this is a
# boundary touching the meridian, not a cut.
MIN_PART_M2 = 1.0
# Latitudes of the half-planes the meridians bound (Poland: 49.0 - 54.9 N).
SOUTH, NORTH = 48.0, 56.0
# Test fixtures (``--fixtures``): PRG powiats around a zone boundary, clipped
# to a window, with whole powiats for the § 22 check; their own (finer)
# simplification keeps them independent of the shipped exceptions.
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "pl2000_zones"
FIXTURE_TOLERANCE_DEG = 1e-6
FIXTURES = {
    "lodz": ((19.25, 51.65, 19.75, 51.90), ("1061",)),
    "meridian_16_5": ((16.30, 50.90, 16.70, 51.10), ()),
    "meridian_22_5": ((22.30, 51.15, 22.70, 51.35), ()),
}


@dataclass(frozen=True)
class Powiat:
    """A powiat of the PRG response."""

    teryt: str
    name: str
    geometry: Any  # shapely Polygon or MultiPolygon in EPSG:2180


def fetch(timeout: float) -> bytes:
    """Fetch every powiat with its geometry: one WFS 2.0 GetFeature request."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": POWIAT_LAYER,
        "COUNT": "1000",
    }
    response = requests.get(PRG_WFS_ENDPOINT, params=params, timeout=timeout)
    response.raise_for_status()
    return response.content


def read_powiats(content: bytes) -> tuple[list[Powiat], dict[str, str]]:
    """Decode the powiats and the PRG version fields of a GetFeature response."""
    root = _feature_collection(content)
    members = root.findall(_WFS_MEMBER)
    _check_complete(root, len(members))
    powiats = []
    versions: dict[str, set[str]] = {}
    for member in members:
        feature = member.find(POWIAT_LAYER.replace("ms:", _MS))
        if feature is None:
            raise SystemExit(f"a member without {POWIAT_LAYER}")
        teryt = (feature.findtext(f"{_MS}JPT_KOD_JE") or "").strip()
        name = (feature.findtext(f"{_MS}JPT_NAZWA_") or "").strip()
        for child in feature:
            tag = child.tag.replace(_MS, "")
            if tag.startswith(("WERSJA", "WAZNY", "IIP_W")) and child.text:
                versions.setdefault(tag, set()).add(child.text.strip())
        geom = feature.find(f"{_MS}msGeometry")
        if geom is None or len(geom) != 1:
            raise SystemExit(f"powiat {teryt}: no geometry")
        shape = geom[0]
        if shape.tag == f"{_GML}Polygon":
            rings = _polygon(shape)
            geometry = shapely.Polygon(rings[0], rings[1:])
        elif shape.tag == f"{_GML}MultiSurface":
            parts = [
                _polygon(p) for p in shape.findall(f"{_GML}surfaceMember/{_GML}Polygon")
            ]
            geometry = shapely.MultiPolygon([(p[0], p[1:]) for p in parts])
        else:
            raise SystemExit(f"powiat {teryt}: unknown geometry {shape.tag}")
        if not geometry.is_valid:
            geometry = shapely.make_valid(geometry)
        powiats.append(Powiat(teryt, name, geometry))
    teryts = [p.teryt for p in powiats]
    if len(set(teryts)) != len(teryts) or not all(
        len(t) == 4 and t.isdigit() for t in teryts
    ):
        raise SystemExit("duplicate or malformed TERYT codes in the response")
    newest = {tag: max(values) for tag, values in sorted(versions.items())}
    return sorted(powiats, key=lambda p: p.teryt), newest


def to_wgs84(geometry: Any) -> Any:
    """Densify a EPSG:2180 geometry (``DENSIFY_M``) and transform it to WGS84."""
    transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    dense = shapely.segmentize(geometry, DENSIFY_M)
    return shapely.transform(
        dense,
        lambda xy: np.column_stack(transformer.transform(xy[:, 0], xy[:, 1])),
    )


def to_2180(geometry: Any) -> Any:
    """Densify a WGS84 geometry (0.001 deg) and transform it to EPSG:2180."""
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    dense = shapely.segmentize(geometry, 0.001)
    return shapely.transform(
        dense,
        lambda xy: np.column_stack(transformer.transform(xy[:, 0], xy[:, 1])),
    )


def nominal_zone(lon: float) -> int:
    """Zone of the nominal strip of a longitude."""
    for zone, (west, east) in NOMINAL_STRIPS.items():
        if west <= lon < east:
            return zone
    raise SystemExit(f"longitude {lon} outside the PL-2000 strips")


def half_planes(meridian: float) -> tuple[Any, Any]:
    """Return the WGS84 half-planes west and east of a meridian (in the strips)."""
    west = shapely.box(meridian - 3.0, SOUTH, meridian, NORTH)
    east = shapely.box(meridian, SOUTH, meridian + 3.0, NORTH)
    return west, east


def zones(powiats: list[Powiat]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Zone of every powiat by § 22; the WGS84 parts on the smaller side."""
    rows = []
    minority: dict[str, Any] = {}
    for powiat in powiats:
        wgs = to_wgs84(powiat.geometry)
        min_lon, _, max_lon, _ = wgs.bounds
        cut = [m for m in MERIDIANS if min_lon < m < max_lon]
        row: dict[str, Any] = {"teryt": powiat.teryt, "name": powiat.name}
        if not cut:
            point = shapely.point_on_surface(wgs)
            row["zone"] = nominal_zone(point.x)
            rows.append(row)
            continue
        if len(cut) > 1:
            raise SystemExit(f"powiat {powiat.teryt} crosses {cut}")
        meridian = cut[0]
        west, east = half_planes(meridian)
        west_part = shapely.intersection(wgs, west)
        east_part = shapely.intersection(wgs, east)
        # Areas in EPSG:2180 (the CRS of PRG): the parts with their meridian
        # edges densified back.
        west_m2 = float(shapely.area(to_2180(west_part)))
        east_m2 = float(shapely.area(to_2180(east_part)))
        west_zone, east_zone = MERIDIANS[meridian]
        if min(west_m2, east_m2) < MIN_PART_M2:
            row["zone"] = west_zone if west_m2 > east_m2 else east_zone
            print(
                f"{powiat.teryt} touches {meridian} ({west_m2:.3f} / {east_m2:.3f} m2)",
                file=sys.stderr,
            )
            rows.append(row)
            continue
        if west_m2 > east_m2:
            row["zone"] = west_zone
            minority[powiat.teryt] = (meridian, "east", west_zone, east_part)
        else:
            row["zone"] = east_zone
            minority[powiat.teryt] = (meridian, "west", east_zone, west_part)
        row["meridian"] = meridian
        row["west_m2"] = round(west_m2)
        row["east_m2"] = round(east_m2)
        rows.append(row)
    return rows, minority


def exceptions(minority: dict[str, Any], prg: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge the minority parts per meridian and side; simplify and check them."""
    groups: dict[tuple[float, str], list[str]] = {}
    for teryt, (meridian, side, _zone, _part) in minority.items():
        groups.setdefault((meridian, side), []).append(teryt)
    result = []
    for (meridian, side), teryts in sorted(groups.items()):
        zone = minority[teryts[0]][2]
        strip = MERIDIANS[meridian][0 if side == "west" else 1]
        merged = shapely.union_all([minority[t][3] for t in teryts])
        simple = shapely.simplify(merged, TOLERANCE_DEG, preserve_topology=True)
        stored = shapely.set_precision(simple, PRECISION_DEG)
        stored = shapely.MultiPolygon(
            [g for g in shapely.get_parts(stored) if g.geom_type == "Polygon"]
        )
        if not stored.is_valid:
            raise SystemExit(f"{meridian} {side}: invalid after rounding")
        # The meridian edge stays exact: every vertex near it lies on it.
        xy = shapely.get_coordinates(stored)
        near = np.abs(xy[:, 0] - meridian) < 1e-6
        if not np.all(xy[near, 0] == meridian):
            raise SystemExit(f"{meridian} {side}: a vertex next to the meridian")
        error = shapely.hausdorff_distance(
            to_2180(shapely.boundary(stored)), prg_boundary(prg, teryts, meridian, side)
        )
        if error > MAX_ERROR_M:
            raise SystemExit(f"{meridian} {side}: {error:.3f} m from PRG")
        print(
            f"{meridian} {side}: zone {zone} in strip {strip}, powiats {teryts},"
            f" {len(xy)} vertices, {shapely.area(to_2180(stored)) / 1e6:.3f} km2,"
            f" {error:.3f} m from PRG",
            file=sys.stderr,
        )
        result.append(
            {
                "meridian": meridian,
                "side": side,
                "strip": strip,
                "zone": zone,
                "teryt": sorted(teryts),
                "geometry": json.loads(shapely.to_geojson(stored)),
            }
        )
    return result


def prg_boundary(
    prg: dict[str, Any], teryts: list[str], meridian: float, side: str
) -> Any:
    """Boundary (EPSG:2180) of the unsimplified merged minority part."""
    west, east = half_planes(meridian)
    merged = shapely.union_all([prg[t] for t in teryts])
    part = shapely.intersection(to_wgs84(merged), west if side == "west" else east)
    return to_2180(shapely.boundary(part))


def write_fixtures(powiats: list[Powiat], source: dict[str, Any]) -> None:
    """Write the PRG powiats of the fixture windows (``FIXTURES``)."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, (window, whole) in FIXTURES.items():
        box = shapely.box(*window)
        features = []
        for powiat in powiats:
            wgs = to_wgs84(powiat.geometry)
            if powiat.teryt in whole:
                geometry, clipped = wgs, False
            elif shapely.intersects(wgs, box):
                geometry, clipped = shapely.clip_by_rect(wgs, *window), True
            else:
                continue
            simple = shapely.simplify(
                geometry, FIXTURE_TOLERANCE_DEG, preserve_topology=True
            )
            features.append(
                {
                    "type": "Feature",
                    "properties": {"teryt": powiat.teryt, "clipped": clipped},
                    "geometry": json.loads(
                        shapely.to_geojson(shapely.set_precision(simple, PRECISION_DEG))
                    ),
                }
            )
        document = {
            "type": "FeatureCollection",
            "source": source,
            "window": list(window),
            "tolerance_deg": FIXTURE_TOLERANCE_DEG,
            "features": features,
        }
        path = FIXTURE_DIR / f"prg_powiats_{name}.geojson"
        text = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
        path.write_text(text + "\n", encoding="utf-8")
        print(f"{path.relative_to(ROOT)}: {len(features)} powiats", file=sys.stderr)


def main() -> int:
    """Build the two data files."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, help="a saved GetFeature response")
    parser.add_argument("--save", type=Path, help="keep the fetched response here")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--fixtures", action="store_true", help="also write the test fixtures"
    )
    args = parser.parse_args()
    if args.source is not None:
        content = args.source.read_bytes()
        fetched = datetime.fromtimestamp(args.source.stat().st_mtime, UTC)
    else:
        content = fetch(args.timeout)
        fetched = datetime.now(UTC)
        if args.save is not None:
            args.save.write_bytes(content)
    powiats, versions = read_powiats(content)
    rows, minority = zones(powiats)
    prg = {p.teryt: p.geometry for p in powiats}
    source = {
        "service": PRG_WFS_ENDPOINT,
        "layer": POWIAT_LAYER,
        "fetched": fetched.date().isoformat(),
        "powiats": len(powiats),
        "versions": versions,
        "licence": LICENCE,
    }
    common = {"rule": RULE, "source": source}
    zones_doc = {
        "schema": "kartograf-pl2000-zones/1",
        **common,
        "crs": "EPSG:4326",
        "area_crs": "EPSG:2180",
        "tolerance_deg": TOLERANCE_DEG,
        "max_error_m": MAX_ERROR_M,
        "strips": {str(z): list(r) for z, r in NOMINAL_STRIPS.items()},
        "exceptions": exceptions(minority, prg),
    }
    powiats_doc = {
        "schema": "kartograf-pl2000-powiat-zones/1",
        **common,
        "powiats": rows,
    }
    text = json.dumps(zones_doc, ensure_ascii=False, separators=(",", ":")) + "\n"
    # mtime=0: the same input gives the same bytes.
    ZONES_FILE.write_bytes(gzip.compress(text.encode("utf-8"), 9, mtime=0))
    POWIATS_FILE.write_text(
        json.dumps(powiats_doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    for path in (ZONES_FILE, POWIATS_FILE):
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size} bytes", file=sys.stderr)
    cut = sum(1 for row in rows if "meridian" in row)
    print(f"{len(rows)} powiats, {cut} cut by a meridian", file=sys.stderr)
    if args.fixtures:
        write_fixtures(powiats, source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
