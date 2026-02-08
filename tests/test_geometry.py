"""
Unit tests for kartograf.core.geometry module.

Tests for reading SHP/GPKG geometry files, GPKG envelope parsing,
CRS transformation, and sheet lookup from geometry.
"""

import sqlite3
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.core.geometry import (
    _parse_gpkg_envelope,
    _transform_bbox,
    find_sheets_for_geometry,
    get_overall_bbox,
    read_feature_bboxes,
)
from kartograf.exceptions import ValidationError  # noqa: I001

# =========================================================================
# Fixtures — SHP
# =========================================================================


def _write_prj(path: Path, epsg: int = 2180):
    """Write a .prj file for the given EPSG code."""
    from pyproj import CRS

    crs = CRS.from_epsg(epsg)
    path.write_text(crs.to_wkt(), encoding="utf-8")


@pytest.fixture
def shp_epsg2180(tmp_path):
    """Create a shapefile with 2 polygon features in EPSG:2180."""
    import shapefile

    shp_path = tmp_path / "test_2180.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("name", "C", 40)
        # Feature 1: small polygon near Krakow
        w.poly(
            [
                [
                    (420000, 230000),
                    (421000, 230000),
                    (421000, 231000),
                    (420000, 231000),
                    (420000, 230000),
                ]
            ]
        )
        w.record("area1")
        # Feature 2: small polygon offset (different location)
        w.poly(
            [
                [
                    (500000, 300000),
                    (501000, 300000),
                    (501000, 301000),
                    (500000, 301000),
                    (500000, 300000),
                ]
            ]
        )
        w.record("area2")

    _write_prj(shp_path.with_suffix(".prj"), 2180)
    return shp_path


@pytest.fixture
def shp_epsg4326(tmp_path):
    """Create a shapefile with a polygon feature in EPSG:4326."""
    import shapefile

    shp_path = tmp_path / "test_4326.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("name", "C", 40)
        # Polygon in WGS84 (lon, lat) near Krakow
        w.poly(
            [
                [
                    (19.93, 50.05),
                    (19.95, 50.05),
                    (19.95, 50.07),
                    (19.93, 50.07),
                    (19.93, 50.05),
                ]
            ]
        )
        w.record("area_wgs84")

    _write_prj(shp_path.with_suffix(".prj"), 4326)
    return shp_path


@pytest.fixture
def shp_no_prj(tmp_path):
    """Create a shapefile without a .prj file."""
    import shapefile

    shp_path = tmp_path / "no_prj.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("name", "C", 40)
        w.poly(
            [
                [
                    (420000, 230000),
                    (421000, 230000),
                    (421000, 231000),
                    (420000, 231000),
                    (420000, 230000),
                ]
            ]
        )
        w.record("area1")

    # Explicitly remove .prj if it was auto-created
    prj = shp_path.with_suffix(".prj")
    if prj.exists():
        prj.unlink()
    return shp_path


@pytest.fixture
def shp_with_null(tmp_path):
    """Create a shapefile with a NULL geometry feature."""
    import shapefile

    shp_path = tmp_path / "with_null.shp"
    with shapefile.Writer(str(shp_path)) as w:
        w.field("name", "C", 40)
        # Normal polygon
        w.poly(
            [
                [
                    (420000, 230000),
                    (421000, 230000),
                    (421000, 231000),
                    (420000, 231000),
                    (420000, 230000),
                ]
            ]
        )
        w.record("area1")
        # NULL shape
        w.null()
        w.record("null_area")

    _write_prj(shp_path.with_suffix(".prj"), 2180)
    return shp_path


# =========================================================================
# Fixtures — GPKG
# =========================================================================


def _make_gpkg_blob(
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    srs_id: int = 2180,
    envelope_type: int = 1,
    byte_order: int = 1,
) -> bytes:
    """Create a minimal GeoPackage binary geometry blob with envelope."""
    flags = (envelope_type << 1) | byte_order
    endian = "<" if byte_order == 1 else ">"

    header = b"GP"  # magic
    header += struct.pack("B", 0)  # version
    header += struct.pack("B", flags)  # flags
    header += struct.pack(f"{endian}i", srs_id)  # SRS ID

    if envelope_type > 0:
        # Envelope: minx, maxx, miny, maxy
        header += struct.pack(f"{endian}4d", min_x, max_x, min_y, max_y)

    # Add minimal WKB point after envelope (for completeness)
    header += struct.pack(f"{endian}Bi2d", byte_order, 1, min_x, min_y)

    return header


@pytest.fixture
def gpkg_epsg2180(tmp_path):
    """Create a minimal GPKG with 2 polygon features in EPSG:2180."""
    from pyproj import CRS

    gpkg_path = tmp_path / "test_2180.gpkg"
    conn = sqlite3.connect(str(gpkg_path))

    crs = CRS.from_epsg(2180)
    wkt = crs.to_wkt()

    # Create GeoPackage metadata tables
    conn.execute(
        "CREATE TABLE gpkg_spatial_ref_sys ("
        "srs_name TEXT, srs_id INTEGER PRIMARY KEY, "
        "organization TEXT, organization_coordsys_id INTEGER, "
        "definition TEXT, description TEXT)"
    )
    conn.execute(
        "INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)",
        ("EPSG:2180", 2180, "EPSG", 2180, wkt, "PL-1992"),
    )

    conn.execute(
        "CREATE TABLE gpkg_contents ("
        "table_name TEXT PRIMARY KEY, data_type TEXT, "
        "identifier TEXT, description TEXT, "
        "last_change TEXT, min_x REAL, min_y REAL, max_x REAL, max_y REAL, "
        "srs_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO gpkg_contents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "features",
            "features",
            "features",
            "",
            "",
            420000,
            230000,
            501000,
            301000,
            2180,
        ),
    )

    conn.execute(
        "CREATE TABLE gpkg_geometry_columns ("
        "table_name TEXT, column_name TEXT, "
        "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
    )
    conn.execute(
        "INSERT INTO gpkg_geometry_columns VALUES (?, ?, ?, ?, ?, ?)",
        ("features", "geom", "POLYGON", 2180, 0, 0),
    )

    # Create feature table with geometry blobs
    conn.execute(
        "CREATE TABLE features (fid INTEGER PRIMARY KEY, name TEXT, geom BLOB)"
    )

    blob1 = _make_gpkg_blob(420000, 230000, 421000, 231000)
    blob2 = _make_gpkg_blob(500000, 300000, 501000, 301000)

    conn.execute("INSERT INTO features (name, geom) VALUES (?, ?)", ("area1", blob1))
    conn.execute("INSERT INTO features (name, geom) VALUES (?, ?)", ("area2", blob2))

    conn.commit()
    conn.close()
    return gpkg_path


@pytest.fixture
def gpkg_multi_layer(tmp_path):
    """Create a GPKG with two feature layers."""
    from pyproj import CRS

    gpkg_path = tmp_path / "multi_layer.gpkg"
    conn = sqlite3.connect(str(gpkg_path))

    crs = CRS.from_epsg(2180)
    wkt = crs.to_wkt()

    conn.execute(
        "CREATE TABLE gpkg_spatial_ref_sys ("
        "srs_name TEXT, srs_id INTEGER PRIMARY KEY, "
        "organization TEXT, organization_coordsys_id INTEGER, "
        "definition TEXT, description TEXT)"
    )
    conn.execute(
        "INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)",
        ("EPSG:2180", 2180, "EPSG", 2180, wkt, "PL-1992"),
    )

    conn.execute(
        "CREATE TABLE gpkg_contents ("
        "table_name TEXT PRIMARY KEY, data_type TEXT, "
        "identifier TEXT, description TEXT, "
        "last_change TEXT, min_x REAL, min_y REAL, max_x REAL, max_y REAL, "
        "srs_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO gpkg_contents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "layer_a",
            "features",
            "layer_a",
            "",
            "",
            420000,
            230000,
            421000,
            231000,
            2180,
        ),
    )
    conn.execute(
        "INSERT INTO gpkg_contents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "layer_b",
            "features",
            "layer_b",
            "",
            "",
            500000,
            300000,
            501000,
            301000,
            2180,
        ),
    )

    conn.execute(
        "CREATE TABLE gpkg_geometry_columns ("
        "table_name TEXT, column_name TEXT, "
        "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
    )
    conn.execute(
        "INSERT INTO gpkg_geometry_columns VALUES (?, ?, ?, ?, ?, ?)",
        ("layer_a", "geom", "POLYGON", 2180, 0, 0),
    )
    conn.execute(
        "INSERT INTO gpkg_geometry_columns VALUES (?, ?, ?, ?, ?, ?)",
        ("layer_b", "geom", "POLYGON", 2180, 0, 0),
    )

    conn.execute("CREATE TABLE layer_a (fid INTEGER PRIMARY KEY, name TEXT, geom BLOB)")
    conn.execute("CREATE TABLE layer_b (fid INTEGER PRIMARY KEY, name TEXT, geom BLOB)")

    blob_a = _make_gpkg_blob(420000, 230000, 421000, 231000)
    blob_b = _make_gpkg_blob(500000, 300000, 501000, 301000)

    conn.execute("INSERT INTO layer_a (name, geom) VALUES (?, ?)", ("a1", blob_a))
    conn.execute("INSERT INTO layer_b (name, geom) VALUES (?, ?)", ("b1", blob_b))

    conn.commit()
    conn.close()
    return gpkg_path


@pytest.fixture
def gpkg_no_envelope(tmp_path):
    """Create a GPKG with envelope_type=0 (no envelope in blob)."""
    from pyproj import CRS

    gpkg_path = tmp_path / "no_env.gpkg"
    conn = sqlite3.connect(str(gpkg_path))

    crs = CRS.from_epsg(2180)
    wkt = crs.to_wkt()

    conn.execute(
        "CREATE TABLE gpkg_spatial_ref_sys ("
        "srs_name TEXT, srs_id INTEGER PRIMARY KEY, "
        "organization TEXT, organization_coordsys_id INTEGER, "
        "definition TEXT, description TEXT)"
    )
    conn.execute(
        "INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)",
        ("EPSG:2180", 2180, "EPSG", 2180, wkt, "PL-1992"),
    )

    conn.execute(
        "CREATE TABLE gpkg_contents ("
        "table_name TEXT PRIMARY KEY, data_type TEXT, "
        "identifier TEXT, description TEXT, "
        "last_change TEXT, min_x REAL, min_y REAL, max_x REAL, max_y REAL, "
        "srs_id INTEGER)"
    )
    conn.execute(
        "INSERT INTO gpkg_contents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("features", "features", "features", "", "", 0, 0, 0, 0, 2180),
    )

    conn.execute(
        "CREATE TABLE gpkg_geometry_columns ("
        "table_name TEXT, column_name TEXT, "
        "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
    )
    conn.execute(
        "INSERT INTO gpkg_geometry_columns VALUES (?, ?, ?, ?, ?, ?)",
        ("features", "geom", "POLYGON", 2180, 0, 0),
    )

    conn.execute(
        "CREATE TABLE features (fid INTEGER PRIMARY KEY, name TEXT, geom BLOB)"
    )

    # Blob with envelope_type=0
    blob = _make_gpkg_blob(420000, 230000, 421000, 231000, envelope_type=0)
    conn.execute("INSERT INTO features (name, geom) VALUES (?, ?)", ("no_env", blob))

    conn.commit()
    conn.close()
    return gpkg_path


@pytest.fixture
def gpkg_no_features(tmp_path):
    """Create a GPKG with no feature tables."""
    gpkg_path = tmp_path / "no_features.gpkg"
    conn = sqlite3.connect(str(gpkg_path))

    conn.execute(
        "CREATE TABLE gpkg_spatial_ref_sys ("
        "srs_name TEXT, srs_id INTEGER PRIMARY KEY, "
        "organization TEXT, organization_coordsys_id INTEGER, "
        "definition TEXT, description TEXT)"
    )

    conn.execute(
        "CREATE TABLE gpkg_contents ("
        "table_name TEXT PRIMARY KEY, data_type TEXT, "
        "identifier TEXT, description TEXT, "
        "last_change TEXT, min_x REAL, min_y REAL, max_x REAL, max_y REAL, "
        "srs_id INTEGER)"
    )

    conn.commit()
    conn.close()
    return gpkg_path


# =========================================================================
# Tests — _parse_gpkg_envelope
# =========================================================================


class TestParseGpkgEnvelope:
    """Tests for GPKG binary envelope parsing."""

    def test_valid_2d_envelope_little_endian(self):
        """Parse valid 2D envelope with little-endian byte order."""
        blob = _make_gpkg_blob(100.0, 200.0, 300.0, 400.0, byte_order=1)
        result = _parse_gpkg_envelope(blob)
        assert result is not None
        min_x, min_y, max_x, max_y = result
        assert min_x == pytest.approx(100.0)
        assert min_y == pytest.approx(200.0)
        assert max_x == pytest.approx(300.0)
        assert max_y == pytest.approx(400.0)

    def test_valid_2d_envelope_big_endian(self):
        """Parse valid 2D envelope with big-endian byte order."""
        blob = _make_gpkg_blob(100.0, 200.0, 300.0, 400.0, byte_order=0)
        result = _parse_gpkg_envelope(blob)
        assert result is not None
        min_x, min_y, max_x, max_y = result
        assert min_x == pytest.approx(100.0)
        assert min_y == pytest.approx(200.0)
        assert max_x == pytest.approx(300.0)
        assert max_y == pytest.approx(400.0)

    def test_no_envelope_type_0(self):
        """Envelope type 0 (no envelope) returns None."""
        blob = _make_gpkg_blob(100.0, 200.0, 300.0, 400.0, envelope_type=0)
        result = _parse_gpkg_envelope(blob)
        assert result is None

    def test_empty_blob(self):
        """Empty blob returns None."""
        assert _parse_gpkg_envelope(b"") is None
        assert _parse_gpkg_envelope(b"GP") is None

    def test_none_blob(self):
        """None blob returns None."""
        assert _parse_gpkg_envelope(None) is None

    def test_invalid_magic(self):
        """Invalid magic bytes return None."""
        blob = b"XX\x00\x02" + b"\x00" * 36
        assert _parse_gpkg_envelope(blob) is None

    def test_short_blob(self):
        """Blob too short for envelope returns None."""
        # Has envelope type but not enough bytes
        blob = b"GP\x00\x02" + b"\x00" * 10
        assert _parse_gpkg_envelope(blob) is None


# =========================================================================
# Tests — SHP reading
# =========================================================================


class TestReadShpBboxes:
    """Tests for reading bounding boxes from shapefiles."""

    def test_two_features(self, shp_epsg2180):
        """Two polygon features produce two bboxes in EPSG:2180."""
        bboxes = read_feature_bboxes(shp_epsg2180, target_crs="EPSG:2180")
        assert len(bboxes) == 2

        # Feature 1
        assert bboxes[0].min_x == pytest.approx(420000, abs=1)
        assert bboxes[0].min_y == pytest.approx(230000, abs=1)
        assert bboxes[0].max_x == pytest.approx(421000, abs=1)
        assert bboxes[0].max_y == pytest.approx(231000, abs=1)
        assert bboxes[0].crs == "EPSG:2180"

    def test_null_geometry_skipped(self, shp_with_null):
        """NULL geometry features are skipped."""
        bboxes = read_feature_bboxes(shp_with_null, target_crs="EPSG:2180")
        assert len(bboxes) == 1  # Only the non-null feature

    def test_crs_transformation(self, shp_epsg4326):
        """Features in EPSG:4326 are transformed to EPSG:2180."""
        bboxes = read_feature_bboxes(shp_epsg4326, target_crs="EPSG:2180")
        assert len(bboxes) == 1

        # Should be in PL-1992 coordinate range
        assert 100_000 < bboxes[0].min_x < 900_000
        assert 100_000 < bboxes[0].min_y < 900_000
        assert bboxes[0].crs == "EPSG:2180"

    def test_missing_prj_raises_error(self, shp_no_prj):
        """Missing .prj file raises ValidationError."""
        with pytest.raises(ValidationError, match="Missing .prj"):
            read_feature_bboxes(shp_no_prj, target_crs="EPSG:2180")


# =========================================================================
# Tests — GPKG reading
# =========================================================================


class TestReadGpkgBboxes:
    """Tests for reading bounding boxes from GeoPackages."""

    def test_two_features(self, gpkg_epsg2180):
        """Two features produce two bboxes."""
        bboxes = read_feature_bboxes(gpkg_epsg2180, target_crs="EPSG:2180")
        assert len(bboxes) == 2

        assert bboxes[0].min_x == pytest.approx(420000, abs=1)
        assert bboxes[0].min_y == pytest.approx(230000, abs=1)
        assert bboxes[0].crs == "EPSG:2180"

    def test_layer_selection(self, gpkg_multi_layer):
        """Specific layer can be selected."""
        bboxes_a = read_feature_bboxes(
            gpkg_multi_layer, layer="layer_a", target_crs="EPSG:2180"
        )
        assert len(bboxes_a) == 1
        assert bboxes_a[0].min_x == pytest.approx(420000, abs=1)

        bboxes_b = read_feature_bboxes(
            gpkg_multi_layer, layer="layer_b", target_crs="EPSG:2180"
        )
        assert len(bboxes_b) == 1
        assert bboxes_b[0].min_x == pytest.approx(500000, abs=1)

    def test_invalid_layer_raises_error(self, gpkg_multi_layer):
        """Requesting non-existent layer raises ValidationError."""
        with pytest.raises(ValidationError, match="not found"):
            read_feature_bboxes(
                gpkg_multi_layer, layer="nonexistent", target_crs="EPSG:2180"
            )

    def test_no_feature_tables_raises_error(self, gpkg_no_features):
        """GPKG without feature tables raises ValidationError."""
        with pytest.raises(ValidationError, match="No feature tables"):
            read_feature_bboxes(gpkg_no_features, target_crs="EPSG:2180")

    def test_no_envelope_skipped(self, gpkg_no_envelope):
        """Features without envelope are skipped."""
        bboxes = read_feature_bboxes(gpkg_no_envelope, target_crs="EPSG:2180")
        assert len(bboxes) == 0


# =========================================================================
# Tests — read_feature_bboxes dispatch
# =========================================================================


class TestReadFeatureBboxes:
    """Tests for read_feature_bboxes dispatch."""

    def test_shp_dispatch(self, shp_epsg2180):
        """SHP files are dispatched correctly."""
        bboxes = read_feature_bboxes(shp_epsg2180)
        assert len(bboxes) == 2

    def test_gpkg_dispatch(self, gpkg_epsg2180):
        """GPKG files are dispatched correctly."""
        bboxes = read_feature_bboxes(gpkg_epsg2180)
        assert len(bboxes) == 2

    def test_unsupported_format(self, tmp_path):
        """Unsupported format raises ValidationError."""
        geojson = tmp_path / "test.geojson"
        geojson.write_text("{}")
        with pytest.raises(ValidationError, match="Unsupported geometry format"):
            read_feature_bboxes(geojson)


# =========================================================================
# Tests — get_overall_bbox
# =========================================================================


class TestGetOverallBbox:
    """Tests for get_overall_bbox."""

    def test_two_scattered_features(self, shp_epsg2180):
        """Union of two scattered features."""
        bbox = get_overall_bbox(shp_epsg2180, target_crs="EPSG:2180")

        assert bbox.min_x == pytest.approx(420000, abs=1)
        assert bbox.min_y == pytest.approx(230000, abs=1)
        assert bbox.max_x == pytest.approx(501000, abs=1)
        assert bbox.max_y == pytest.approx(301000, abs=1)

    def test_single_feature(self, shp_epsg4326):
        """Single feature bbox equals feature bbox."""
        bbox = get_overall_bbox(shp_epsg4326, target_crs="EPSG:2180")
        bboxes = read_feature_bboxes(shp_epsg4326, target_crs="EPSG:2180")

        assert bbox.min_x == pytest.approx(bboxes[0].min_x)
        assert bbox.min_y == pytest.approx(bboxes[0].min_y)

    def test_no_features_raises_error(self, gpkg_no_envelope):
        """No features with geometry raises ValidationError."""
        with pytest.raises(ValidationError, match="No features"):
            get_overall_bbox(gpkg_no_envelope)


# =========================================================================
# Tests — _transform_bbox
# =========================================================================


class TestTransformBbox:
    """Tests for CRS transformation of bboxes."""

    def test_same_crs_no_transform(self):
        """Same CRS returns original coordinates."""
        from pyproj import CRS

        source = CRS.from_epsg(2180)
        result = _transform_bbox(420000, 230000, 421000, 231000, source, "EPSG:2180")

        assert result.min_x == pytest.approx(420000)
        assert result.min_y == pytest.approx(230000)
        assert result.crs == "EPSG:2180"

    def test_4326_to_2180(self):
        """Transform from WGS84 to PL-1992."""
        from pyproj import CRS

        source = CRS.from_epsg(4326)
        result = _transform_bbox(19.93, 50.05, 19.95, 50.07, source, "EPSG:2180")

        assert 100_000 < result.min_x < 900_000
        assert 100_000 < result.min_y < 900_000
        assert result.crs == "EPSG:2180"

    def test_2180_to_4326(self):
        """Transform from PL-1992 to WGS84."""
        from pyproj import CRS

        source = CRS.from_epsg(2180)
        result = _transform_bbox(420000, 230000, 421000, 231000, source, "EPSG:4326")

        assert 14 < result.min_x < 25  # longitude range for Poland
        assert 49 < result.min_y < 55  # latitude range for Poland
        assert result.crs == "EPSG:4326"


# =========================================================================
# Tests — find_sheets_for_geometry
# =========================================================================


class TestFindSheetsForGeometry:
    """Tests for find_sheets_for_geometry."""

    @patch("kartograf.core.geometry.find_sheets_for_bbox")
    def test_single_feature(self, mock_find, shp_epsg4326):
        """Single feature calls find_sheets_for_bbox once."""
        mock_find.return_value = ["M-34-76-A-a-1-1"]

        result = find_sheets_for_geometry(shp_epsg4326, target_scale="1:10000")

        assert result == ["M-34-76-A-a-1-1"]
        assert mock_find.call_count == 1

    @patch("kartograf.core.geometry.find_sheets_for_bbox")
    def test_two_features_deduplication(self, mock_find, shp_epsg2180):
        """Two features with overlapping sheets are deduplicated."""
        mock_find.side_effect = [
            ["M-34-76-A-a-1-1", "M-34-76-A-a-1-2"],
            ["M-34-76-A-a-1-2", "N-34-130-D-d-2-4"],
        ]

        result = find_sheets_for_geometry(shp_epsg2180, target_scale="1:10000")

        # Deduplicated and sorted
        assert result == [
            "M-34-76-A-a-1-1",
            "M-34-76-A-a-1-2",
            "N-34-130-D-d-2-4",
        ]
        assert mock_find.call_count == 2

    @patch("kartograf.core.geometry.find_sheets_for_bbox")
    def test_empty_result(self, mock_find, shp_epsg4326):
        """No matching sheets returns empty list."""
        mock_find.return_value = []

        result = find_sheets_for_geometry(shp_epsg4326)
        assert result == []

    @patch("kartograf.core.geometry.find_sheets_for_bbox")
    def test_passes_target_scale(self, mock_find, shp_epsg4326):
        """Target scale is passed to find_sheets_for_bbox."""
        mock_find.return_value = ["M-34-76-A-a-1-1"]

        find_sheets_for_geometry(shp_epsg4326, target_scale="1:25000")

        call_args = mock_find.call_args
        assert call_args[0][1] == "1:25000"

    def test_no_features_returns_empty(self, gpkg_no_envelope):
        """File with no valid features returns empty list."""
        result = find_sheets_for_geometry(gpkg_no_envelope)
        assert result == []

    def test_gpkg_layer_param(self, gpkg_multi_layer):
        """Layer parameter is forwarded for GPKG."""
        with patch("kartograf.core.geometry.find_sheets_for_bbox") as mock_find:
            mock_find.return_value = ["N-34-130-D-d-2-4"]
            result = find_sheets_for_geometry(gpkg_multi_layer, layer="layer_b")
            assert result == ["N-34-130-D-d-2-4"]
            # Should have been called once (one feature in layer_b)
            assert mock_find.call_count == 1
