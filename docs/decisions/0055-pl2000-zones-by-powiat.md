# ADR-055: PL-2000 zones are areas of powiats (§ 22), not longitude strips

**Date:** 2026-10-25
**Status:** Accepted (the author set the rule on 2026-10-25: a PL-2000 zone is the area of its powiats);
amends ADR-017
**Standard:** Nogat 2.1: DEV-6.4 (the new runtime dependency), DEV-10.1 (offline tests)

**Context:** Archiwista's map showed two whole PL-2000 sheet grids over one view across a zone
boundary ("Siatka godeł", `GET /map/sheets` -> `find_sheets_for_bbox(..., "2000")`).
`find_sheets_2000_for_bbox` took the zones as fixed longitude strips (`_ZONE_LON_RANGES`: 13.5, 16.5,
19.5, 22.5 and 25.5 E), kept every zone whose strip overlaps the bbox and searched the whole bbox in
the grid of each of them. For 19.3-19.7 E x 51.95-52.05 N that gave 12 + 12 sheets at 1:10000 (37
pairs of sheets of different zones with intersecting interiors, 441 km² drawn twice) and 228 + 228
at 1:2000 (862 pairs), and a bbox download with `--sheet-system 2000` asked for the same 456 sheets.
Nor is a zone a longitude range: the regulation on the national spatial reference system
(Rozporządzenie Rady Ministrów z dnia 15 października 2012 r. w sprawie państwowego systemu odniesień
przestrzennych, Dz.U. 2012 poz. 1247), § 22: "Faktyczne granice pasów południkowych w układzie
współrzędnych PL-2000 wyznacza się wzdłuż granic jednostek administracyjnych szczebla powiatowego,
przy czym w przypadku jednostek administracyjnych przecinanych na dwie części przez południki
graniczne pasów południkowych: 16,5ºE, 19,5ºE lub 22,5ºE o przynależności obszaru powiatu do
określonego pasa południkowego przesądza część o większej powierzchni." Annex 1, Table 12 repeats
it ("W praktyce granice strefy odwzorowawczej pokrywają się z granicami jednostek administracyjnych
szczebla powiatowego") and gives the nominal strips. The regulation states a rule, not a list of
powiats; the regulation it replaced (Dz.U. 2000 nr 70 poz. 821) has no list either, and the GUGiK
per-zone NMT sheet grids (dane.gov.pl dataset 2095) are whole rectangles that overlap (21,440 sheets
1:5000 per zone). Kartograf had no powiat-to-zone mapping and no powiat geometry offline (the PRG
client asks the WFS for powiat codes only).

**Options considered:**
- (a) Cut each zone's grid at the nominal meridian: simple, but it puts the parts of 73 powiats in
  the wrong zone (§ 22) - rejected.
- (b) A TERYT -> zone table plus the PRG powiat polygons fetched per request: the network for every
  map view and sheet search, which are offline today - rejected.
- (c) The zone areas derived once from PRG by § 22 and shipped with the package (chosen): the table
  and the parts of the cut powiats that lie in the neighbouring strip.
- (d) Four whole zone polygons: the same information plus the national border and the coast, about
  three times the size.

**Decision:**
1. **A zone is an area.** Zone N is its nominal strip (Table 12: 13.5-16.5, 16.5-19.5, 19.5-22.5,
   22.5-25.5 E) without the parts of cut powiats that belong to a neighbouring zone, plus the parts of
   its own cut powiats that lie in a neighbouring strip (the exceptions,
   `kartograf.core.pl2000_zones`). Outside Poland, where § 22 does not apply, a zone is its nominal
   strip, so a search abroad or at sea keeps its former result. Every computation of a zone area is
   in WGS84, where a meridian is a straight line: the areas of two zones meet exactly.
2. **Data** (`src/kartograf/_data/`): `pl2000_zones.json.gz` (`kartograf-pl2000-zones/1`: six
   exception areas, one per meridian and side, each with its zone, the strip it lies in and its TERYT
   codes; MultiPolygon in EPSG:4326, 7 decimals) and `pl2000_powiat_zones.json`
   (`kartograf-pl2000-powiat-zones/1`: every powiat with its zone; a cut powiat also with its meridian
   and the areas of both sides in m², EPSG:2180). Source: GUGiK PRG WFS
   `https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries`, layer
   `ms:A02_Granice_powiatow`, one GetFeature request with geometry on 2026-10-25: 380 powiats, newest
   `WERSJA_OD` and `IIP_WERSJA` 2026-10-23T08:26:38, newest `WAZNY_OD` 2024-02-21. Licence: PRG is
   open data under art. 40a ust. 2 pkt 1 of Prawo geodezyjne i kartograficzne, attribution "Dane:
   Główny Urząd Geodezji i Kartografii (www.geoportal.gov.pl)" (`PL-PGiK-40a`, as every GUGiK source).
3. **Derivation** (`scripts/build_pl2000_zones.py`: the network, never run by the tests; `--source`
   rebuilds from a saved response byte for byte, `--fixtures` writes the test fixtures). A powiat is
   cut when both sides of a meridian hold more than 1 m² of it; the areas are measured in EPSG:2180
   (the parts cut in WGS84 along the exact meridian, their meridian edge densified back). 73 powiats
   are cut (16.5 E: 19, 19.5 E: 28, 22.5 E: 26); none crosses two meridians and none only touches one.
   Examples: Łódź (1061) 170.4 km² west and 122.5 km² east of 19.5 E, zone 6; powiat świdnicki (0219)
   488.2 / 252.8 km² at 16.5 E, zone 5; Lublin (0663) 19.1 / 128.3 km² at 22.5 E, zone 8. The minority
   parts are merged per meridian and side, simplified by Douglas-Peucker with 4.5e-6 deg in WGS84
   (vertices on the meridian stay exact) and rounded to 1e-7 deg; the build checks the Hausdorff
   distance to the PRG boundary: at most 0.614 m (limit 1 m). Size: 67,488 vertices, 1.61 MB of JSON,
   523,676 bytes with gzip (the plain JSON is above the 1 MB target); the table 34,519 bytes.
4. **Sheet search.** `find_sheets_2000_for_bbox` (and `find_sheets_for_bbox(..., "2000")`) takes the
   zones whose area meets the bbox; the candidates of a zone are found as before (sheet rectangles
   meeting the envelope of the bbox in the zone CRS), and a candidate stays when its part inside the
   zone area and the envelope has a positive area (more than 1e-9 of its part in the envelope, in WGS84
   with sheet edges split at 1 km). A bbox inside one zone keeps exactly the former result. A point
   gives one sheet; on a zone boundary, the zone with the larger share of the 1 mm square east/north of
   it (the east zone on a meridian outside Poland). `zone=` restricts the search to that zone's area.
5. **Outlines.** `find_sheet_outlines(bbox, target_scale, sheet_system) -> list[SheetOutline]`
   (`sheet`, `zone`, `outline`): the sheets of `find_sheets_for_bbox`, each with its PL-2000 zone
   (`None` for PL-1992) and its outline in EPSG:4326 for a map: the sheet rectangle with its edges split
   into equal parts of at most 1 km (neighbour sheets share the points), and for a sheet that a zone
   boundary cuts, its part inside its zone (Polygon or MultiPolygon, RFC 7946 ring order). The outlines
   of two zones never overlap and together cover the bbox; a download keeps the whole sheet
   (`get_bbox()`).
6. **Dependency.** `shapely>=2.1` (GEOS; `orient_polygons` since 2.1) joins the runtime dependencies:
   the zone areas are polygons with holes, beyond `core/coverage.py` (convex polygons).

**Consequences:**
- Across a zone boundary the map and the downloads get each zone's sheets on its own side: the view
  above gives 214 zone-6 and 29 zone-7 sheets at 1:2000 (was 228 + 228) and no overlap; a view inside
  one zone is unchanged. The regression tests (`tests/unit/test_pl2000_zones.py`) take real PRG
  powiats around each meridian (`tests/fixtures/pl2000_zones`, from the same response, their own
  simplification of 1e-6 deg) and the shipped table as the oracle.
- A sheet code of one zone over another zone's powiats (e.g. `8.175.8` at 22.5 E) is no longer a sheet
  of that area; such a code given with `--sheet` is still downloaded as asked.
- The zones follow PRG as fetched: when powiat boundaries change, rebuild the data with the script (a
  new PRG request) and record the new PRG version in an erratum here.
- Archiwista draws `find_sheet_outlines` and shows the zone of each sheet (after its re-pin).
