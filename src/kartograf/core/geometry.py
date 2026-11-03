"""
Reading geometry files (SHP, GPKG, GeoJSON) for spatial data selection.

Reads the features of a geometry file - their envelopes (``read_feature_bboxes``:
SHP and GPKG from the file headers) or their whole geometry
(``find_sheets_for_geometry``, ``read_feature_areas``) - and maps them to
map sheet codes for tile-based downloads. A feature selects the sheets its
geometry meets, not every sheet of its envelope (ADR-058).
"""

import logging
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import shapely
import shapely.geometry
from pyproj import CRS

from kartograf.core.bbox import BBox, transform_bbox, transform_shape
from kartograf.core.coverage import (
    COLLINEAR_TOL_M,
    Point,
    Polygon,
    normalize_convex,
    rectangle,
)
from kartograf.core.sheet_parser import find_sheets_for_shape, shape_parts
from kartograf.exceptions import ValidationError
from kartograf.messages import message, reason

logger = logging.getLogger(__name__)

# Supported file extensions; a GeoJSON file is ``.geojson`` or ``.json``
_GEOJSON_EXTENSIONS = frozenset({".geojson", ".json"})
_SUPPORTED_EXTENSIONS = {".shp", ".gpkg", *_GEOJSON_EXTENSIONS}
# The GDAL driver of a GeoJSON file (RFC 7946: FeatureCollection, Feature or a
# geometry); a ``.json`` file read by another driver (Esri JSON, TopoJSON) is
# not an area file
_GEOJSON_DRIVER = "GeoJSON"
# The CRS of GeoJSON (RFC 7946: WGS84 longitude, latitude) when GDAL names none
_GEOJSON_CRS = "EPSG:4326"
# metres: longest edge of a feature before it leaves the CRS of its file; the
# image of a straight edge is a curve (65 m off a 50 km chord in EPSG:2180)
_SEGMENT_M = 100.0
# metres per degree of latitude: the edge length of a feature in degrees
_METRES_PER_DEGREE = 111_320.0
# Bytes of the envelope of a GeoPackage geometry by its contents indicator
# (flags bits 1-3): none, xy, xyz, xym, xyzm
_GPKG_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def _unsupported_format(ext: str) -> ValidationError:
    """Build the error of a geometry file that is not SHP, GPKG or GeoJSON."""
    return ValidationError(
        message(
            "core.unsupported_geometry_format",
            ext=ext,
            supported_extensions=", ".join(sorted(_SUPPORTED_EXTENSIONS)),
        )
    )


# =========================================================================
# GPKG Binary Envelope Parsing
# =========================================================================


def _point_from_wkb(
    blob: bytes, offset: int
) -> tuple[float, float, float, float] | None:
    """
    Read a degenerate envelope from a WKB geometry that starts at ``offset``.

    Used when the GeoPackage header carries no envelope (``envelope_type == 0``);
    GDAL/QGIS write point layers exactly this way, and for a point the geometry
    itself is the envelope.

    Parameters
    ----------
    blob : bytes
        Raw geometry blob from GPKG
    offset : int
        Index of the first WKB byte (byte order marker)

    Returns
    -------
    tuple or None
        (x, y, x, y) for a POINT, or None if the WKB is truncated before the
        geometry type or before the coordinates

    Raises
    ------
    ValidationError
        If the WKB holds a non-point geometry (its extent cannot be derived
        without a full WKB parser)
    """
    # WKB prefix: 1 B byte order + 4 B geometry type
    if len(blob) < offset + 5:
        return None

    order = blob[offset]
    endian = "<" if order == 1 else ">"
    wkb_type = struct.unpack(f"{endian}I", blob[offset + 1 : offset + 5])[0]

    # Strip EWKB flag bits (Z=0x80000000, M=0x40000000, SRID=0x20000000), then
    # the ISO dimension prefix (1001 = POINT Z, 2001 = POINT M, 3001 = POINT ZM).
    base_type = (wkb_type & 0x0FFFFFFF) % 1000
    if base_type != 1:
        raise ValidationError(
            message("core.gpkg_geometry_without_envelope_header", wkb_type=wkb_type)
        )

    # EWKB with the SRID flag inserts a 4 B CRS identifier BETWEEN the type and
    # the coordinates - without skipping it we would read garbage.
    coord_offset = offset + 9 if wkb_type & 0x20000000 else offset + 5
    if len(blob) < coord_offset + 16:  # 2 x float64
        return None

    x, y = struct.unpack(f"{endian}2d", blob[coord_offset : coord_offset + 16])
    return (x, y, x, y)


def _parse_gpkg_envelope(blob: bytes) -> tuple[float, float, float, float] | None:
    """
    Parse GeoPackage Binary geometry header to extract envelope.

    GeoPackage spec binary header:
      Offset 0: "GP" magic (2 bytes)
      Offset 2: version (1 byte)
      Offset 3: flags (1 byte) — envelope_type = (flags >> 1) & 0x07,
                empty geometry flag = (flags >> 4) & 0x01
      Offset 4: SRS ID (4 bytes, int32)
      Offset 8: envelope (if type > 0):
        type 1 (2D): minx, maxx, miny, maxy (4 x float64)

    Code paths:
      * empty-geometry flag - the feature is skipped (``None``), it has no extent;
      * ``envelope_type > 0`` - the envelope is read straight from the header;
      * ``envelope_type == 0`` - there is no envelope (this is how GDAL/QGIS
        write point layers), so the coordinates come from the WKB itself
        (``_point_from_wkb``); for a non-point geometry this ends in
        ``ValidationError``.

    Parameters
    ----------
    blob : bytes
        Raw geometry blob from GPKG

    Returns
    -------
    tuple or None
        (min_x, min_y, max_x, max_y), or None for an empty geometry or an
        unusable header/WKB

    Raises
    ------
    ValidationError
        If the header has no envelope and the WKB is not a point
    """
    if blob is None or len(blob) < 8:
        return None

    # Check magic bytes "GP"
    if blob[0:2] != b"GP":
        return None

    flags = blob[3]
    byte_order = flags & 0x01  # 0 = big-endian, 1 = little-endian
    envelope_type = (flags >> 1) & 0x07
    is_empty = (flags >> 4) & 0x01

    if is_empty:
        # An empty geometry has no extent - GDAL writes it as POINT(NaN NaN),
        # so the feature must be skipped before NaN reaches the sheet lookup.
        return None

    if envelope_type == 0:
        # No envelope in the header - try to read a point from the WKB right after it.
        return _point_from_wkb(blob, offset=8)

    # Need at least 8 (header) + 32 (4 doubles) = 40 bytes for 2D envelope
    if len(blob) < 40:
        return None

    endian = "<" if byte_order == 1 else ">"

    # Envelope: minx, maxx, miny, maxy
    minx, maxx, miny, maxy = struct.unpack(f"{endian}4d", blob[8:40])

    return (minx, miny, maxx, maxy)


# =========================================================================
# SHP Reading
# =========================================================================


def _read_shp_crs(filepath: Path) -> CRS:
    """
    Read CRS from .prj file accompanying a shapefile.

    Parameters
    ----------
    filepath : Path
        Path to .shp file

    Returns
    -------
    CRS
        pyproj CRS object

    Raises
    ------
    ValidationError
        If .prj file is missing or CRS cannot be parsed
    """
    prj_path = filepath.with_suffix(".prj")
    if not prj_path.exists():
        raise ValidationError(message("core.no_prj_file_shapefile", prj_path=prj_path))

    wkt = prj_path.read_text(encoding="utf-8").strip()
    try:
        return CRS.from_wkt(wkt)
    except Exception:
        try:
            return CRS.from_user_input(wkt)
        except Exception as e:
            raise ValidationError(
                message(
                    "core.cannot_read_coordinate_system",
                    prj_path=prj_path,
                    error=reason(e),
                )
            ) from e


def _read_shp_bboxes(filepath: Path, target_crs: str) -> list[BBox]:
    """
    Read per-feature bounding boxes from a shapefile.

    Parameters
    ----------
    filepath : Path
        Path to .shp file
    target_crs : str
        Target CRS (e.g. "EPSG:2180")

    Returns
    -------
    list[BBox]
        Per-feature bboxes in target CRS

    Notes
    -----
    Point features (POINT/POINTZ/POINTM) give a degenerate envelope
    ``(x, y, x, y)`` - pyshp does not expose a ``bbox`` attribute for them.
    """
    import shapefile

    # CRS label as WKT: the transformer cache key in core.bbox is a string -
    # one transformer per layer, not per feature
    source_label = _read_shp_crs(filepath).to_wkt()

    bboxes = []
    with shapefile.Reader(str(filepath)) as sf:
        for shape in sf.iterShapes():
            if shape.shapeType == 0:  # NULL shape
                continue
            # pyshp exposes `bbox` only for multi-vertex shapes; POINT/POINTZ/
            # POINTM carry a single vertex, so build a degenerate bbox from it.
            bbox = getattr(shape, "bbox", None)  # (min_x, min_y, max_x, max_y)
            if bbox is None:
                if not shape.points:
                    continue
                x, y = shape.points[0][0], shape.points[0][1]
                bbox = (x, y, x, y)
            source_bbox = BBox(bbox[0], bbox[1], bbox[2], bbox[3], source_label)
            bboxes.append(transform_bbox(source_bbox, target_crs))

    return bboxes


def _read_shp_shapes(filepath: Path) -> list[Any]:
    """
    Read the geometry of every feature of a shapefile (ADR-058).

    The features of ``_read_shp_bboxes`` (NULL shapes skipped), each as a
    shapely geometry in the CRS of the file. The rings of a polygon become
    its exteriors and holes by ``shapefile.organize_polygon_rings`` (clockwise
    exteriors; a shape of counter-clockwise rings only is taken as exteriors,
    without the warning pyshp logs for it in ``__geo_interface__``); the other
    shapes come from their GeoJSON form.

    Raises
    ------
    ValidationError
        A shape that is no geometry (``core.unreadable_feature_geometry``)
    """
    import shapefile

    polygon_types = (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM)
    shapes = []
    with shapefile.Reader(str(filepath)) as sf:
        for number, shape in enumerate(sf.iterShapes(), start=1):
            if shape.shapeType == 0 or not shape.points:  # NULL or empty shape
                continue
            try:
                if shape.shapeType in polygon_types:
                    ends = [*shape.parts[1:], len(shape.points)]
                    rings = [
                        [(p[0], p[1]) for p in shape.points[start:end]]
                        for start, end in zip(shape.parts, ends, strict=True)
                    ]
                    found = {
                        "type": "MultiPolygon",
                        "coordinates": shapefile.organize_polygon_rings(rings),
                    }
                else:
                    found = shape.__geo_interface__
                geometry = shapely.geometry.shape(found)
            except Exception as e:  # pyshp raises a plain Exception, shapely its own
                raise _unreadable(filepath, number, reason(e)) from e
            if not geometry.is_empty:
                shapes.append(geometry)
    return shapes


def _unreadable(filepath: Path, number: int, error: str) -> ValidationError:
    """Build the error of a feature whose geometry cannot be read."""
    return ValidationError(
        message(
            "core.unreadable_feature_geometry",
            number=number,
            filepath=filepath,
            error=error,
        )
    )


# =========================================================================
# GPKG Reading
# =========================================================================


def _get_gpkg_feature_tables(conn: sqlite3.Connection) -> list[str]:
    """
    Get feature table names from a GeoPackage.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open GPKG database connection

    Returns
    -------
    list[str]
        Feature table names
    """
    cursor = conn.execute(
        "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
    )
    return [row[0] for row in cursor.fetchall()]


def _read_gpkg_crs(conn: sqlite3.Connection, table_name: str) -> CRS:
    """
    Read CRS for a feature table from GeoPackage metadata.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open GPKG database connection
    table_name : str
        Feature table name

    Returns
    -------
    CRS
        pyproj CRS object
    """
    # Get SRS ID from gpkg_geometry_columns
    cursor = conn.execute(
        "SELECT srs_id FROM gpkg_geometry_columns WHERE table_name = ?",
        (table_name,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValidationError(
            message("core.no_geometry_column_metadata_table", table_name=table_name)
        )
    srs_id = row[0]

    # Get CRS definition from gpkg_spatial_ref_sys
    cursor = conn.execute(
        "SELECT definition FROM gpkg_spatial_ref_sys WHERE srs_id = ?",
        (srs_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValidationError(message("core.no_srs_definition_srs_id", srs_id=srs_id))

    wkt = row[0]
    try:
        return CRS.from_wkt(wkt)
    except Exception:
        try:
            return CRS.from_authority("EPSG", str(srs_id))
        except Exception as e:
            raise ValidationError(
                message(
                    "core.cannot_read_coordinate_system_srs_id",
                    srs_id=srs_id,
                    error=reason(e),
                )
            ) from e


@dataclass(frozen=True)
class LayerChoice:
    """Layer a geometry file is read from (``resolve_layer``)."""

    name: str | None  # None for SHP (one layer, no names)
    available: tuple[str, ...]  # GPKG feature tables in file order; () for SHP
    defaulted: bool  # True when no layer was given and the first one was taken


def _gpkg_layer_choice(
    conn: sqlite3.Connection, filepath: Path, layer: str | None
) -> LayerChoice:
    """Return the validated GPKG layer choice (first feature table by default).

    Does no logging.
    """
    tables = tuple(_get_gpkg_feature_tables(conn))
    if not tables:
        raise ValidationError(
            message("core.no_feature_tables_geopackage", filepath=filepath)
        )
    if layer is not None:
        if layer not in tables:
            raise ValidationError(
                message(
                    "core.no_layer_geopackage", layer=layer, tables=", ".join(tables)
                )
            )
        return LayerChoice(layer, tables, defaulted=False)
    return LayerChoice(tables[0], tables, defaulted=True)


def _resolve_gpkg_layer(
    conn: sqlite3.Connection, filepath: Path, layer: str | None
) -> str:
    """
    Name of the feature table to read (``--layer`` validation, first by default).

    The default choice among several layers is logged as a WARNING (visible by
    default): the area then comes from the first layer only. Pass ``layer`` to
    choose explicitly and silence it.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open GPKG database connection
    filepath : Path
        Path to .gpkg file (for error messages)
    layer : str or None
        Layer name (None = first feature table)

    Returns
    -------
    str
        Feature table name

    Raises
    ------
    ValidationError
        If the GeoPackage has no feature tables or the layer does not exist
    """
    choice = _gpkg_layer_choice(conn, filepath, layer)
    if choice.defaulted and len(choice.available) > 1:
        logger.warning(
            "GPKG %s has %d layers, using the first '%s' (others: %s); "
            "pass layer= to choose",
            filepath.name,
            len(choice.available),
            choice.name,
            ", ".join(choice.available[1:]),
        )
    assert choice.name is not None  # GPKG always names its layer
    return choice.name


def resolve_layer(filepath: Path, layer: str | None = None) -> LayerChoice:
    """
    Which layer of a geometry file is read, without reading features.

    For the CLI: resolve the layer ONCE, show the default choice, then pass the
    explicit name on (the readers below would otherwise warn on every call).

    Parameters
    ----------
    filepath : Path
        Path to SHP, GPKG or GeoJSON file
    layer : str or None
        Requested GPKG layer (None = first feature table); ignored for SHP
        and GeoJSON (one layer each)

    Returns
    -------
    LayerChoice
        Chosen layer, all feature tables and whether the choice was the default

    Raises
    ------
    ValidationError
        If the format is unsupported, the GPKG has no feature tables or the
        layer does not exist
    """
    ext = filepath.suffix.lower()
    if ext == ".shp" or ext in _GEOJSON_EXTENSIONS:
        return LayerChoice(None, (), defaulted=False)
    if ext == ".gpkg":
        conn = sqlite3.connect(str(filepath))
        try:
            return _gpkg_layer_choice(conn, filepath, layer)
        finally:
            conn.close()
    raise _unsupported_format(ext)


def _read_gpkg_bboxes(filepath: Path, layer: str | None, target_crs: str) -> list[BBox]:
    """
    Read per-feature bounding boxes from a GeoPackage.

    Parameters
    ----------
    filepath : Path
        Path to .gpkg file
    layer : str or None
        Layer name (None = first feature table)
    target_crs : str
        Target CRS (e.g. "EPSG:2180")

    Returns
    -------
    list[BBox]
        Per-feature bboxes in target CRS
    """
    conn = sqlite3.connect(str(filepath))
    try:
        table_name = _resolve_gpkg_layer(conn, filepath, layer)
        source_label = _read_gpkg_crs(conn, table_name).to_wkt()

        # Get geometry column name
        cursor = conn.execute(
            "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
            (table_name,),
        )
        geom_col = cursor.fetchone()[0]

        # Read geometry blobs and extract envelopes
        cursor = conn.execute(
            f'SELECT "{geom_col}" FROM "{table_name}"'  # noqa: S608
        )

        bboxes = []
        for (blob,) in cursor:
            if blob is None:
                continue
            envelope = _parse_gpkg_envelope(blob)
            if envelope is None:
                continue
            source_bbox = BBox(*envelope, source_label)
            bboxes.append(transform_bbox(source_bbox, target_crs))

        return bboxes
    finally:
        conn.close()


def _gpkg_wkb(blob: bytes, filepath: Path, number: int) -> bytes | None:
    """
    Return the WKB of the GeoPackage geometry blob of feature ``number``.

    ``None`` for an empty geometry or a blob that is not GeoPackage Binary -
    the features ``_parse_gpkg_envelope`` skips too.

    Raises
    ------
    ValidationError
        An envelope contents indicator the specification does not define (5-7)
    """
    if len(blob) < 8 or blob[0:2] != b"GP":
        return None
    flags = blob[3]
    if (flags >> 4) & 0x01:
        return None  # the empty geometry flag
    indicator = (flags >> 1) & 0x07
    size = _GPKG_ENVELOPE_BYTES.get(indicator)
    if size is None:
        text = message("core.gpkg_invalid_envelope_indicator", indicator=indicator)
        raise _unreadable(filepath, number, text)
    return blob[8 + size :]


def _read_gpkg_shapes(filepath: Path, layer: str | None) -> tuple[CRS, list[Any]]:
    """
    Read the CRS and the geometry of every feature of a GeoPackage layer.

    The layer and the features of ``_read_gpkg_bboxes`` (NULL and empty
    geometries skipped), each parsed from its WKB by shapely (ADR-058), in
    the CRS of the layer.

    Raises
    ------
    ValidationError
        As ``_read_gpkg_bboxes``, and a blob whose WKB cannot be read
        (``core.unreadable_feature_geometry``)
    """
    conn = sqlite3.connect(str(filepath))
    try:
        table_name = _resolve_gpkg_layer(conn, filepath, layer)
        crs = _read_gpkg_crs(conn, table_name)
        cursor = conn.execute(
            "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
            (table_name,),
        )
        geom_col = cursor.fetchone()[0]
        cursor = conn.execute(
            f'SELECT "{geom_col}" FROM "{table_name}"'  # noqa: S608
        )
        shapes = []
        for number, (blob,) in enumerate(cursor, start=1):
            wkb = None if blob is None else _gpkg_wkb(blob, filepath, number)
            if wkb is None:
                continue
            try:
                geometry = shapely.from_wkb(wkb)
            except shapely.errors.ShapelyError as e:
                raise _unreadable(filepath, number, reason(e)) from e
            if not geometry.is_empty:
                shapes.append(geometry)
        return crs, shapes
    finally:
        conn.close()


# =========================================================================
# GeoJSON Reading
# =========================================================================


def _geojson_info(filepath: Path) -> dict[str, Any]:
    """
    Return the pyogrio layer info of a GeoJSON file.

    GDAL reads GeoJSON (pyogrio), as it reads the OGC API Features pages of
    ``transform.gpkg``: RFC 7946 coordinates are WGS84 longitude and latitude,
    a legacy ``crs`` member (GeoJSON 2008) names the CRS of the coordinates.

    Raises
    ------
    ValidationError
        A file GDAL does not read as GeoJSON (``core.not_geojson``): plain
        JSON, Esri JSON, TopoJSON
    """
    import pyogrio
    from pyogrio.errors import DataLayerError, DataSourceError

    try:
        info: dict[str, Any] = pyogrio.read_info(str(filepath))
    except (DataSourceError, DataLayerError) as e:
        raise ValidationError(message("core.not_geojson", filepath=filepath)) from e
    driver = info.get("driver")
    if driver != _GEOJSON_DRIVER:
        raise ValidationError(
            message("core.not_geojson_driver", filepath=filepath, driver=driver)
        )
    return info


def _read_geojson_crs(filepath: Path) -> CRS:
    """Read the CRS of a GeoJSON file (WGS84 unless a legacy ``crs`` names one)."""
    return CRS.from_user_input(_geojson_info(filepath).get("crs") or _GEOJSON_CRS)


def _read_geojson_shapes(filepath: Path) -> tuple[CRS, list[Any]]:
    """
    Read the CRS and the geometry of every feature of a GeoJSON file.

    A FeatureCollection, a Feature or a bare geometry (one feature); features
    without a geometry are skipped. A GeoJSON file has one layer, so a
    ``layer`` does not apply to it (as to a shapefile).

    Raises
    ------
    ValidationError
        As ``_geojson_info``, and a geometry that cannot be read
        (``core.unreadable_feature_geometry``)
    """
    import pyogrio.raw
    from pyogrio.errors import DataLayerError, DataSourceError

    crs = _read_geojson_crs(filepath)
    try:
        _meta, _fids, geometries, _fields = pyogrio.raw.read(
            str(filepath), columns=[], read_geometry=True
        )
    except (DataSourceError, DataLayerError) as e:
        raise ValidationError(message("core.not_geojson", filepath=filepath)) from e
    shapes = []
    for number, wkb in enumerate(geometries, start=1):
        if wkb is None:
            continue
        try:
            geometry = shapely.from_wkb(wkb)
        except shapely.errors.ShapelyError as e:
            raise _unreadable(filepath, number, reason(e)) from e
        if not geometry.is_empty:
            shapes.append(geometry)
    return crs, shapes


def _read_geojson_bboxes(filepath: Path, target_crs: str) -> list[BBox]:
    """Read per-feature bounding boxes of a GeoJSON file in ``target_crs``."""
    crs, shapes = _read_geojson_shapes(filepath)
    label = crs.to_wkt()  # the transformer cache key: one transformer per file
    bboxes = []
    for shape in shapes:
        min_x, min_y, max_x, max_y = (float(v) for v in shape.bounds)
        source_bbox = BBox(min_x, min_y, max_x, max_y, label)
        bboxes.append(transform_bbox(source_bbox, target_crs))
    return bboxes


# =========================================================================
# Feature geometry (ADR-058)
# =========================================================================


def _read_shapes(filepath: Path, layer: str | None) -> tuple[CRS, list[Any]]:
    """Read the CRS and the feature geometries of a SHP, a GPKG layer or GeoJSON."""
    ext = filepath.suffix.lower()
    if ext == ".shp":
        return _read_shp_crs(filepath), _read_shp_shapes(filepath)
    if ext == ".gpkg":
        return _read_gpkg_shapes(filepath, layer)
    if ext in _GEOJSON_EXTENSIONS:
        return _read_geojson_shapes(filepath)
    raise _unsupported_format(ext)


def _segment_length(crs: CRS) -> float:
    """Return the longest edge of a feature before it leaves ``crs`` (~100 m)."""
    if crs.is_geographic:
        return _SEGMENT_M / _METRES_PER_DEGREE
    axes = crs.axis_info
    return _SEGMENT_M / (axes[0].unit_conversion_factor if axes else 1.0)


def _shapes_2180(crs: CRS, shapes: list[Any]) -> list[Any]:
    """
    Move feature geometries to EPSG:2180, their edges densified first.

    Densified ONCE, in the CRS of the file (``_SEGMENT_M``; also when it is
    EPSG:2180, as the sheet frames are compared in WGS84 and the zone CRSs):
    the new vertices lie on the straight edges, so they move exactly.
    """
    label = crs.to_wkt()  # the transformer cache key: one transformer per layer
    step = _segment_length(crs)
    return [
        transform_shape(shapely.segmentize(shape, step), label, "EPSG:2180")
        for shape in shapes
    ]


def _turn(o: Point, a: Point, b: Point) -> float:
    """Cross product of ``o -> a`` and ``o -> b``: positive for a left turn."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _convex_pieces(polygons: Any) -> list[Polygon]:
    """
    Cut polygons (EPSG:2180) into convex counter-clockwise pieces.

    Vertices within ``COLLINEAR_TOL_M`` of the line of their neighbours go
    first (the densified edges of a feature from another CRS). A convex
    polygon without holes is one piece; any other is triangulated (constrained
    Delaunay: the triangles cover the polygon, its holes stay out) and the
    triangles are joined across their shared edges while the union stays
    convex (Hertel-Mehlhorn: at most four times the fewest convex pieces).
    """
    pieces: list[Polygon] = []
    for polygon in shapely.get_parts(shapely.simplify(polygons, COLLINEAR_TOL_M)):
        if polygon.is_empty:
            continue
        if shapely.get_num_interior_rings(polygon) == 0:
            convex = normalize_convex(polygon.exterior.coords)
            if convex is not None:
                pieces.append(convex)
                continue
        triangles = shapely.get_parts(shapely.constrained_delaunay_triangles(polygon))
        pieces.extend(_merge_triangles(triangles))
    return pieces


def _merge_triangles(triangles: Any) -> list[Polygon]:
    """Join triangles across their shared edges while each union stays convex."""
    rings: list[list[Point] | None] = []
    for triangle in triangles:
        a, b, c = (
            (float(x), float(y)) for x, y in shapely.get_coordinates(triangle)[:3]
        )
        turn = _turn(a, b, c)
        if turn != 0:
            rings.append([a, b, c] if turn > 0 else [a, c, b])
    owner: dict[tuple[Point, Point], int] = {}
    for index, ring in enumerate(rings):
        assert ring is not None
        owner.update(dict.fromkeys(_edges(ring), index))
    for p, q in list(owner):
        first, second = owner.get((p, q)), owner.get((q, p))
        if first is None or second is None or first == second:
            continue
        kept, absorbed = rings[first], rings[second]
        assert kept is not None and absorbed is not None
        joined = _joined(kept, absorbed, p, q)
        if joined is None:
            continue
        rings[first], rings[second] = joined, None
        del owner[(p, q)], owner[(q, p)]
        owner.update(dict.fromkeys(_edges(joined), first))
    return [tuple(ring) for ring in rings if ring is not None]


def _edges(ring: list[Point]) -> list[tuple[Point, Point]]:
    """Return the directed edges of a closed ring given without its closing vertex."""
    return list(zip(ring, ring[1:] + ring[:1], strict=True))


def _joined(
    first: list[Point], second: list[Point], p: Point, q: Point
) -> list[Point] | None:
    """
    Return the union of two convex CCW rings that share an edge.

    ``p -> q`` is an edge of ``first`` and ``q -> p`` of ``second``; ``None``
    when the union is not convex at ``p`` or ``q``.
    """
    at = first.index(q)
    around_first = first[at:] + first[:at]  # q ... p
    at = second.index(p)
    around_second = second[at:] + second[:at]  # p ... q
    if (
        _turn(around_first[-2], p, around_second[1]) < 0
        or _turn(around_second[-2], q, around_first[1]) < 0
    ):
        return None
    return around_first + around_second[1:-1]


# =========================================================================
# Public API
# =========================================================================


def read_feature_bboxes(
    filepath: Path,
    layer: str | None = None,
    target_crs: str = "EPSG:2180",
) -> list[BBox]:
    """
    Read per-feature bounding boxes from a geometry file.

    SHP and GPKG from their headers (pyshp ``bbox``, the GeoPackage envelope),
    GeoJSON from its geometries (GDAL).

    Parameters
    ----------
    filepath : Path
        Path to SHP, GPKG or GeoJSON file
    layer : str or None
        Layer name for GPKG (None = first layer; with several layers a
        logger WARNING names the choice)
    target_crs : str
        Target CRS (default: "EPSG:2180")

    Returns
    -------
    list[BBox]
        Per-feature bboxes in target CRS

    Raises
    ------
    ValidationError
        If file format is unsupported or file cannot be read
    """
    ext = filepath.suffix.lower()

    if ext == ".shp":
        return _read_shp_bboxes(filepath, target_crs)
    if ext == ".gpkg":
        return _read_gpkg_bboxes(filepath, layer, target_crs)
    if ext in _GEOJSON_EXTENSIONS:
        return _read_geojson_bboxes(filepath, target_crs)
    raise _unsupported_format(ext)


def read_source_crs(filepath: Path, layer: str | None = None) -> CRS:
    """
    Read the CRS the geometry file stores its coordinates in (no transformation).

    Makes it possible to compute the envelope IN THE FILE'S CRS (``target_crs``
    equal to that CRS = no transformation) and to make the jump to the target
    CRS with the pinned-operation mechanism from ``kartograf.transform.crs``
    instead of the default pyproj transformer used in this module.

    Parameters
    ----------
    filepath : Path
        Path to SHP, GPKG or GeoJSON file
    layer : str or None
        Layer name for GPKG (None = first feature table; with several layers a
        logger WARNING names the choice)

    Returns
    -------
    CRS
        pyproj CRS object; GeoJSON: WGS84 (RFC 7946) unless a legacy ``crs``
        member names another CRS

    Raises
    ------
    ValidationError
        If the format is unsupported or the CRS cannot be determined
    """
    ext = filepath.suffix.lower()

    if ext == ".shp":
        return _read_shp_crs(filepath)
    if ext == ".gpkg":
        conn = sqlite3.connect(str(filepath))
        try:
            return _read_gpkg_crs(conn, _resolve_gpkg_layer(conn, filepath, layer))
        finally:
            conn.close()
    if ext in _GEOJSON_EXTENSIONS:
        return _read_geojson_crs(filepath)
    raise _unsupported_format(ext)


def get_overall_bbox(
    filepath: Path,
    layer: str | None = None,
    target_crs: str = "EPSG:2180",
) -> BBox:
    """
    Compute the union bounding box of all features in a geometry file.

    Parameters
    ----------
    filepath : Path
        Path to SHP, GPKG or GeoJSON file
    layer : str or None
        Layer name for GPKG (None = first layer; with several layers a
        logger WARNING names the choice)
    target_crs : str
        Target CRS (default: "EPSG:2180")

    Returns
    -------
    BBox
        Union bounding box

    Raises
    ------
    ValidationError
        If no features found or file format unsupported
    """
    bboxes = read_feature_bboxes(filepath, layer=layer, target_crs=target_crs)

    if not bboxes:
        raise ValidationError(message("core.no_features_geometry", filepath=filepath))

    min_x = min(b.min_x for b in bboxes)
    min_y = min(b.min_y for b in bboxes)
    max_x = max(b.max_x for b in bboxes)
    max_y = max(b.max_y for b in bboxes)

    return BBox(min_x, min_y, max_x, max_y, target_crs)


def read_feature_areas(filepath: Path, layer: str | None = None) -> list[Polygon]:
    """
    Read the features of a geometry file as convex (E, N) polygons in EPSG:2180.

    The area of the archive sheet selection (``GugikProvider.index_sheets``)
    and of the availability report (ADR-058): a polygon is its own shape, cut
    into convex pieces (its holes stay out), so a sheet frame or a pixel
    counts only where the polygon is, not anywhere in its envelope. A feature
    without an area (a point, a line) is its envelope, as before: zero area
    for a point or a line along an axis.

    Parameters
    ----------
    filepath : Path
        Path to SHP, GPKG or GeoJSON file
    layer : str or None
        Layer name for GPKG (None = first layer; with several layers a
        logger WARNING names the choice)

    Returns
    -------
    list[Polygon]
        Convex counter-clockwise polygons, one or more per feature; ``[]`` for
        a layer without features

    Raises
    ------
    ValidationError
        If the format is unsupported, the file cannot be read or a feature's
        geometry cannot be read
    """
    crs, shapes = _read_shapes(filepath, layer)
    label = crs.to_wkt()
    areas: list[Polygon] = []
    for source, shape in zip(shapes, _shapes_2180(crs, shapes), strict=True):
        polygons = shape_parts(shape)[2]
        if polygons is not None:
            areas.extend(_convex_pieces(polygons))
            continue
        min_x, min_y, max_x, max_y = (float(v) for v in source.bounds)
        box = transform_bbox(BBox(min_x, min_y, max_x, max_y, label), "EPSG:2180")
        areas.append(rectangle(box.min_x, box.min_y, box.max_x, box.max_y))
    return areas


def find_sheets_for_geometry(
    filepath: Path,
    target_scale: str,
    layer: str | None = None,
    *,
    sheet_system: str,
) -> list[str]:
    """
    Find the map sheets that the features of a geometry file meet (ADR-058).

    Every feature is read whole and moved to EPSG:2180 with its edges
    densified; ``find_sheets_for_shape`` keeps the sheets whose frame it
    meets in the CRS of the sheet system: a polygon - the sheets it overlaps
    with a positive area (a sheet it only touches along an edge or at a corner
    does not count), a line - the sheets it runs through, a point - the one
    sheet it lies in. The envelope of a feature only pre-selects candidates,
    so a diagonal or an L-shaped area does not take every sheet of its
    envelope and scattered features take only their own sheets.

    Parameters
    ----------
    filepath : Path
        Path to SHP, GPKG or GeoJSON file
    target_scale : str
        PL-1992: 1:1000000, 1:500000, 1:200000, 1:100000,
        1:50000, 1:25000 or 1:10000 (GUGiK publishes 1:10000).
        PL-2000: 1:10000, 1:5000, 1:2000, 1:1000 or 1:500.
    layer : str or None
        Layer name for GPKG (None = first layer; with several layers a
        logger WARNING names the choice)
    sheet_system : str
        "1992" for the PL-1992 sheet grid, or "2000" for the PL-2000
        grid (whose finer scales differ).

    Returns
    -------
    list[str]
        Sorted, deduplicated list of sheet codes

    Raises
    ------
    ValidationError
        If the format is unsupported, the file or a feature's geometry cannot
        be read, or as ``find_sheets_for_bbox``
    """
    crs, shapes = _read_shapes(filepath, layer)
    found: set[str] = set()
    for shape in _shapes_2180(crs, shapes):
        found.update(find_sheets_for_shape(shape, target_scale, sheet_system))
    return sorted(found)
