"""
Reading geometry files (SHP, GPKG) for spatial data selection.

Extracts per-feature bounding boxes from geometry files and maps them
to map sheet identifiers (godla) for tile-based downloads.
"""

import logging
import sqlite3
import struct
from pathlib import Path

from pyproj import CRS, Transformer

from kartograf.core.sheet_parser import BBox, find_sheets_for_bbox
from kartograf.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Supported file extensions
_SUPPORTED_EXTENSIONS = {".shp", ".gpkg"}


# =========================================================================
# GPKG Binary Envelope Parsing
# =========================================================================


def _parse_gpkg_envelope(blob: bytes) -> tuple[float, float, float, float] | None:
    """
    Parse GeoPackage Binary geometry header to extract envelope.

    GeoPackage spec binary header:
      Offset 0: "GP" magic (2 bytes)
      Offset 2: version (1 byte)
      Offset 3: flags (1 byte) — envelope_type = (flags >> 1) & 0x07
      Offset 4: SRS ID (4 bytes, int32)
      Offset 8: envelope (if type > 0):
        type 1 (2D): minx, maxx, miny, maxy (4 x float64)

    Parameters
    ----------
    blob : bytes
        Raw geometry blob from GPKG

    Returns
    -------
    tuple or None
        (min_x, min_y, max_x, max_y) or None if no envelope
    """
    if blob is None or len(blob) < 8:
        return None

    # Check magic bytes "GP"
    if blob[0:2] != b"GP":
        return None

    flags = blob[3]
    byte_order = flags & 0x01  # 0 = big-endian, 1 = little-endian
    envelope_type = (flags >> 1) & 0x07

    if envelope_type == 0:
        return None

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
    """
    import shapefile

    source_crs = _read_shp_crs(filepath)

    bboxes = []
    with shapefile.Reader(str(filepath)) as sf:
        for shape in sf.iterShapes():
            if shape.shapeType == 0:  # NULL shape
                continue
            bbox = shape.bbox  # (min_x, min_y, max_x, max_y)
            transformed = _transform_bbox(
                bbox[0], bbox[1], bbox[2], bbox[3], source_crs, target_crs
            )
            bboxes.append(transformed)

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
        tables = _get_gpkg_feature_tables(conn)
        if not tables:
            raise ValidationError(f"No feature tables found in GeoPackage: {filepath}")

        if layer is not None:
            if layer not in tables:
                raise ValidationError(
                    f"Layer '{layer}' not found in GeoPackage. "
                    f"Available layers: {', '.join(tables)}"
                )
            table_name = layer
        else:
            table_name = tables[0]
            if len(tables) > 1:
                logger.info(
                    "Multiple layers in GPKG, using '%s'. Available: %s",
                    table_name,
                    ", ".join(tables),
                )

        source_crs = _read_gpkg_crs(conn, table_name)

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
            min_x, min_y, max_x, max_y = envelope
            transformed = _transform_bbox(
                min_x, min_y, max_x, max_y, source_crs, target_crs
            )
            bboxes.append(transformed)

        return bboxes
    finally:
        conn.close()


# =========================================================================
# CRS Transformation
# =========================================================================


def _transform_bbox(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    source_crs: CRS,
    target_crs: str,
) -> BBox:
    """
    Transform a bounding box from source CRS to target CRS.

    Uses 4-corner approach for accuracy.

    Parameters
    ----------
    min_x, min_y, max_x, max_y : float
        Source bbox coordinates
    source_crs : CRS
        Source CRS object
    target_crs : str
        Target CRS string (e.g. "EPSG:2180")

    Returns
    -------
    BBox
        Transformed bounding box
    """
    target = CRS.from_user_input(target_crs)

    if source_crs == target:
        return BBox(min_x, min_y, max_x, max_y, target_crs)

    transformer = Transformer.from_crs(source_crs, target, always_xy=True)

    corners = [
        (min_x, min_y),  # SW
        (min_x, max_y),  # NW
        (max_x, min_y),  # SE
        (max_x, max_y),  # NE
    ]

    transformed = [transformer.transform(x, y) for x, y in corners]

    t_min_x = min(c[0] for c in transformed)
    t_min_y = min(c[1] for c in transformed)
    t_max_x = max(c[0] for c in transformed)
    t_max_y = max(c[1] for c in transformed)

    return BBox(t_min_x, t_min_y, t_max_x, t_max_y, target_crs)


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

    Returns
    -------
    list[str]
        Sorted, deduplicated list of godla (sheet identifiers)
    """
    bboxes = read_feature_bboxes(filepath, layer=layer, target_crs="EPSG:2180")

    if not bboxes:
        return []

    all_godla: set[str] = set()
    for bbox in bboxes:
        godla = find_sheets_for_bbox(bbox, target_scale)
        all_godla.update(godla)

    return sorted(all_godla)
