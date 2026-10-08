"""
Reading geometry files (SHP, GPKG) for spatial data selection.

Extracts per-feature bounding boxes from geometry files and maps them
to map sheet codes (godla) for tile-based downloads.
"""

import logging
import sqlite3
import struct
from pathlib import Path

from pyproj import CRS

from kartograf.core.bbox import BBox, transform_bbox
from kartograf.core.sheet_parser import find_sheets_for_bbox
from kartograf.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Supported file extensions
_SUPPORTED_EXTENSIONS = {".shp", ".gpkg"}


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
            "GPKG geometry without envelope in header (envelope_type=0) "
            f"for WKB type {wkb_type} - rebuild the file with envelopes "
            "(e.g. ogr2ogr) or use SHP"
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
        raise ValidationError(
            f"Missing .prj file for shapefile: {prj_path}. "
            "Cannot determine coordinate reference system."
        )

    wkt = prj_path.read_text(encoding="utf-8").strip()
    try:
        return CRS.from_wkt(wkt)
    except Exception:
        try:
            return CRS.from_user_input(wkt)
        except Exception as e:
            raise ValidationError(f"Cannot parse CRS from {prj_path}: {e}") from e


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
        raise ValidationError(f"No geometry column metadata for table '{table_name}'")
    srs_id = row[0]

    # Get CRS definition from gpkg_spatial_ref_sys
    cursor = conn.execute(
        "SELECT definition FROM gpkg_spatial_ref_sys WHERE srs_id = ?",
        (srs_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValidationError(f"No SRS definition for srs_id={srs_id}")

    wkt = row[0]
    try:
        return CRS.from_wkt(wkt)
    except Exception:
        try:
            return CRS.from_authority("EPSG", str(srs_id))
        except Exception as e:
            raise ValidationError(f"Cannot parse CRS for srs_id={srs_id}: {e}") from e


def _resolve_gpkg_layer(
    conn: sqlite3.Connection, filepath: Path, layer: str | None
) -> str:
    """
    Name of the feature table to read (``--layer`` validation, first by default).

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
    tables = _get_gpkg_feature_tables(conn)
    if not tables:
        raise ValidationError(f"No feature tables found in GeoPackage: {filepath}")

    if layer is not None:
        if layer not in tables:
            raise ValidationError(
                f"Layer '{layer}' not found in GeoPackage. "
                f"Available layers: {', '.join(tables)}"
            )
        return layer

    table_name = tables[0]
    if len(tables) > 1:
        logger.info(
            "Multiple layers in GPKG, using '%s'. Available: %s",
            table_name,
            ", ".join(tables),
        )
    return table_name


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

    Parameters
    ----------
    filepath : Path
        Path to SHP or GPKG file
    layer : str or None
        Layer name for GPKG (None = first layer)
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
    elif ext == ".gpkg":
        return _read_gpkg_bboxes(filepath, layer, target_crs)
    else:
        raise ValidationError(
            f"Unsupported geometry format: '{ext}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
        )


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
        Path to SHP or GPKG file
    layer : str or None
        Layer name for GPKG (None = first feature table)

    Returns
    -------
    CRS
        pyproj CRS object

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

    raise ValidationError(
        f"Unsupported geometry format: '{ext}'. "
        f"Supported: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}"
    )


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
        Path to SHP or GPKG file
    layer : str or None
        Layer name for GPKG (None = first layer)
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
        raise ValidationError(f"No features with geometry found in: {filepath}")

    min_x = min(b.min_x for b in bboxes)
    min_y = min(b.min_y for b in bboxes)
    max_x = max(b.max_x for b in bboxes)
    max_y = max(b.max_y for b in bboxes)

    return BBox(min_x, min_y, max_x, max_y, target_crs)


def find_sheets_for_geometry(
    filepath: Path,
    target_scale: str = "1:10000",
    layer: str | None = None,
    system: str = "1992",
) -> list[str]:
    """
    Find map sheets intersecting features in a geometry file.

    Extracts per-feature bounding boxes and finds sheets for each,
    then deduplicates. This ensures that scattered features only
    download tiles they actually intersect, not the full bounding box.

    Parameters
    ----------
    filepath : Path
        Path to SHP or GPKG file
    target_scale : str
        Target scale (default: "1:10000")
    layer : str or None
        Layer name for GPKG (None = first layer)
    system : str
        Coordinate system: "1992" (PL-1992) or "2000" (PL-2000).
        Default: "1992" - full backward compatibility.

    Returns
    -------
    list[str]
        Sorted, deduplicated list of sheet codes (godla)
    """
    bboxes = read_feature_bboxes(filepath, layer=layer, target_crs="EPSG:2180")

    if not bboxes:
        return []

    all_godla: set[str] = set()
    for bbox in bboxes:
        godla = find_sheets_for_bbox(bbox, target_scale, system=system)
        all_godla.update(godla)

    return sorted(all_godla)
