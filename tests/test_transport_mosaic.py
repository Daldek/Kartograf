"""Testy mozaikowania (kartograf.transport.mosaic) na syntetycznych rastrach."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.transport.mosaic import mosaic_and_crop


def _write_tile(
    path: Path,
    origin_x: float,
    origin_y: float,
    value: float,
    size: int = 10,
    res: float = 1.0,
    crs: str = "EPSG:2180",
    nodata: float | None = None,
) -> Path:
    data = np.full((size, size), value, dtype="float32")
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": from_origin(origin_x, origin_y, res, res),
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
    return path


@pytest.fixture
def four_tiles(tmp_path):
    # Kafle 2x2 (kazdy 10x10 m, res 1 m): wspolny naroznik w (10, 10).
    return [
        _write_tile(tmp_path / "a.tif", 0, 20, 1.0),  # NW
        _write_tile(tmp_path / "b.tif", 10, 20, 2.0),  # NE
        _write_tile(tmp_path / "c.tif", 0, 10, 3.0),  # SW
        _write_tile(tmp_path / "d.tif", 10, 10, 4.0),  # SE
    ]


class TestMosaicAndCrop:
    def test_merge_and_crop_to_bbox(self, four_tiles, tmp_path):
        out = mosaic_and_crop(
            four_tiles,
            BBox(5.0, 5.0, 15.0, 15.0, "EPSG:2180"),
            tmp_path / "out.tif",
        )
        with rasterio.open(out) as src:
            assert src.width == 10 and src.height == 10
            assert src.bounds == pytest.approx((5.0, 5.0, 15.0, 15.0))
            data = src.read(1)
        # Cwiartki wyniku pochodza z 4 roznych kafli.
        assert data[0, 0] == 1.0 and data[0, -1] == 2.0
        assert data[-1, 0] == 3.0 and data[-1, -1] == 4.0

    def test_nodata_propagated_never_zeroed(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, nodata=-9999.0),
        ]
        out = mosaic_and_crop(
            tiles,
            BBox(0.0, 0.0, 20.0, 10.0, "EPSG:2180"),
            tmp_path / "out.tif",
            nodata=-9999.0,
        )
        with rasterio.open(out) as src:
            assert src.nodata == -9999.0
            data = src.read(1)
        # Obszar bez pokrycia (x 10..20) = nodata, NIE 0.
        assert data[0, -1] == -9999.0

    def test_empty_inputs_raise(self, tmp_path):
        with pytest.raises(ValidationError):
            mosaic_and_crop([], BBox(0, 0, 1, 1, "EPSG:2180"), tmp_path / "out.tif")

    def test_crs_mismatch_raises(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, crs="EPSG:2180"),
            _write_tile(tmp_path / "b.tif", 10, 10, 2.0, crs="EPSG:2177"),
        ]
        with pytest.raises(ValidationError):
            mosaic_and_crop(
                tiles, BBox(0, 0, 20, 10, "EPSG:2180"), tmp_path / "out.tif"
            )

    def test_resolution_mismatch_raises(self, tmp_path):
        tiles = [
            _write_tile(tmp_path / "a.tif", 0, 10, 1.0, res=1.0),
            _write_tile(tmp_path / "b.tif", 10, 10, 2.0, res=2.0),
        ]
        with pytest.raises(ValidationError):
            mosaic_and_crop(
                tiles, BBox(0, 0, 20, 10, "EPSG:2180"), tmp_path / "out.tif"
            )
