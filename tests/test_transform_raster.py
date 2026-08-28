"""Testy warp_to_grid — lokalna reprojekcja przypieta operacja (wzorzec ADR-024)."""

from unittest.mock import patch

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.transform.crs import TransformPolicy, build_pinned_transform
from kartograf.transform.raster import warp_to_grid

_NODATA = -9999.0
# EPSG:2180, srodkowa Polska — realny teren, operacja 2180->5514 ma tu 0,5 m
_APEX_2180 = (530050.0, 382050.0)


def _pinned_2180_to(target_crs):
    return build_pinned_transform(
        "EPSG:2180",
        target_crs,
        TransformPolicy(
            min_accuracy_m=1.0, probe_point=_APEX_2180, allow_network_grids=False
        ),
    )


def _write_cone_tif(path, apex, size=300, pixel=1.0):
    """Stozek wokol apex w EPSG:2180 (wzorzec _server_emulator z test_cuzk_dmr)."""
    west = apex[0] - size / 2 * pixel
    north = apex[1] + size / 2 * pixel
    cols, rows = np.meshgrid(np.arange(size), np.arange(size))
    xs = west + (cols + 0.5) * pixel
    ys = north - (rows + 0.5) * pixel
    data = (1000.0 - np.hypot(xs - apex[0], ys - apex[1])).astype("float32")
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": size,
        "height": size,
        "crs": CRS.from_string("EPSG:2180"),
        "transform": from_origin(west, north, pixel, pixel),
        "nodata": _NODATA,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
    return path


def _apex_of(path):
    with rasterio.open(path) as ds:
        data = ds.read(1, masked=True)
        row, col = np.unravel_index(np.argmax(data.filled(-np.inf)), data.shape)
        return ds.xy(int(row), int(col))


class TestWarpToGrid:
    def test_content_lands_where_pyproj_says(self, tmp_path):
        """Regresja TRESCI: wierzcholek < 1 px od wzorca pyproj (2180->5514)."""
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 100, ay - 100, ax + 100, ay + 100, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        gx, gy = _apex_of(dst)
        assert abs(gx - ax) < 1.0, f"E: {gx} vs {ax}"
        assert abs(gy - ay) < 1.0, f"N: {gy} vs {ay}"

    def test_grid_matches_bbox_and_profile(self, tmp_path):
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 40, ax + 50, ay + 40, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 2.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        with rasterio.open(dst) as ds:
            assert (ds.width, ds.height) == (50, 40)
            assert ds.crs.to_epsg() == 5514
            assert ds.nodata == _NODATA
        # zapis atomowy: brak plikow tymczasowych
        assert list(tmp_path.glob("*.warp.tif")) == []

    def test_operation_is_forced(self, tmp_path):
        """COORDINATE_OPERATION musi byc podane GDAL-owi jawnie (ADR-024)."""
        from rasterio.warp import reproject as real_reproject

        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")

        with patch(
            "kartograf.transform.raster.reproject", wraps=real_reproject
        ) as warp:
            warp_to_grid(
                src,
                tmp_path / "dst.tif",
                bbox,
                1.0,
                pinned,
                src_crs="EPSG:2180",
                nodata=_NODATA,
            )

        warp.assert_called_once()
        assert warp.call_args.kwargs["COORDINATE_OPERATION"] == pinned.gdal_operation()
