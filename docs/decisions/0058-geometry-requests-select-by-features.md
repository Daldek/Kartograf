# ADR-058: A geometry request selects by its features, not their envelopes; GeoJSON area files

**Date:** 2026-10-31
**Status:** Accepted (request of the author through Archiwista); amends ADR-015 (feature geometry
read and compared, not only envelopes; GeoJSON read by GDAL)
**Standard:** Nogat 2.1: DEV-10.1 (offline tests)

**Context:** The author reported through Archiwista that downloading for a polygon behaves as if
it were a rectangle. Measured by an Archiwista agent on a diagonal 11 km strip near Kraków
(PL-2000 1:1000): the bbox gives 200 sheets, a GPKG with the polygon as one feature 200 too
(1:5000 15 = 15, PL-1992 1:10000 25 = 25), while the polygon meets 32. `find_sheets_for_geometry`
took the envelope of each feature from the file header (ADR-015) and returned every sheet of
that envelope (`find_sheets_for_bbox`); the archive sheet selection (`_download_pl_archive`)
and the area the availability report measures (`_area_polygons`) used the same envelopes. The
help of `--geometry` and ARCHITECTURE 4.2 already said "the sheets that intersect its features".
Archiwista also wants to pass its area as a WGS84 GeoJSON file instead of a GPKG.

**Options considered:**
- (a) Keep the envelopes and document them - rejected: a diagonal or L-shaped area downloads
  several times the sheets it needs.
- (b) Read the features with GDAL (pyogrio) for every format - one reader, but a second reader of
  the same SHP/GPKG files beside the header envelopes of the other tracks, with GDAL's view of
  the hand-made GeoPackages of the tests and of pyshp files.
- (c) Read the whole geometry with the readers that already read these files (chosen): pyshp for
  SHP (the rings organised by `shapefile.organize_polygon_rings`, without the warning pyshp logs
  in `__geo_interface__`), the WKB after the GeoPackage header for GPKG (shapely); GeoJSON with
  GDAL (pyogrio), which Kartograf already uses for the GeoJSON pages of OGC API Features.

**Decision:**
1. **Selection.** A `--geometry` request selects the sheets whose frame meets a feature's
   geometry (`find_sheets_for_shape`), in the CRS of the sheet system: WGS84 degrees for PL-1992,
   the zone CRS for PL-2000, where a sheet counts only by its part inside the area of its zone
   (ADR-055, `sheets_meeting_2000`). A polygon meets a sheet with a positive area (more than
   `_MIN_SHARE` = 1e-9 of the sheet, the share of the zone rule), so an edge or a corner contact
   does not count; a line with a positive length in the frame or along its edge; a point keeps
   the one sheet `find_sheets_for_bbox` gives for it (east/north of a grid line). The envelope of
   each part only pre-selects candidates. Invalid geometry is repaired (`make_valid`); several
   features select the sorted union of their sheets.
2. **Transformation.** The rules of the envelopes (`core.bbox`): the cached pyproj transformer,
   EPSG:2180 -> EPSG:4326 -> zone CRS. A feature's edges are densified ONCE, in the CRS of its
   file, at 100 m (`_SEGMENT_M`), then only its vertices move (`transform_shape`): a straight edge
   is a curve in another CRS (30 m off its chord for a 50 km EPSG:2180 edge across 19 E), and a
   second densification in another CRS would put vertices on the chords. A cut along a zone
   boundary splits its long edges at 0.01 deg before the move.
3. **Archives and the availability report.** `read_feature_areas` gives a polygon as its own
   convex pieces in EPSG:2180 (vertices within 10 cm of a line dropped, constrained Delaunay
   triangles joined while convex: Hertel-Mehlhorn), so `overlaps_area` and the 1 m raster of the
   report measure the polygon (its holes left out), not its envelope. A feature without an area (a
   point, a line) keeps its envelope there, as before. `overlaps_area` answers separate envelopes
   first.
4. **By design by the AREA envelope** (unchanged, documented): `--cutout` (PL WCS and CZ
   exportImage), LAZ tiles, the CZ part of a request, and the unit selections of collections, land
   cover, soils and HSG (`geometry_envelope`, `get_overall_bbox`: one envelope of the layer).
5. **GeoJSON.** `--geometry` accepts `.geojson`, and `.json` that GDAL reads as GeoJSON (a
   FeatureCollection, a Feature or a geometry; Esri JSON, TopoJSON and other JSON are refused,
   `core.not_geojson`). RFC 7946 coordinates are WGS84 longitude and latitude; GDAL honours a
   legacy `crs` member (GeoJSON 2008, e.g. a QGIS export in EPSG:2180). A GeoJSON has one layer:
   `layer` does not apply, as for SHP. A file without features is refused as an empty GPKG layer.

**Consequences:**
- Fewer sheets for non-rectangular areas: the strip of the context (300 m wide) takes 37 PL-2000
  sheets 1:1000 instead of 216, 6 of 12 at 1:5000 and 8 of 20 PL-1992 sheets; a polygon equal to
  a sheet frame takes that sheet, not its eight neighbours. A rectangle along the axes of its
  sheet system keeps its sheets.
- The availability report measures the polygon: a triangle over half of a 4 x 4 km square
  measures 7,998,000 m2 (the square 16,000,000) and lists its 5 sheets, not the 6 of the square;
  the hint keeps `--geometry`.
- A feature whose geometry cannot be read is an error (`core.unreadable_feature_geometry`) where
  its envelope was enough before; a GPKG of non-point features without header envelopes still
  needs them for the envelope tracks (`read_feature_bboxes`).
- Offline tests (`tests/unit/test_geometry.py`) compare the selection with an oracle computed
  apart (pyproj and shapely in the test, the zone areas of ADR-055 for PL-2000).
