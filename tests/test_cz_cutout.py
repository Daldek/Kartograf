"""A6: CZ cutout in the library: sidecar, all-nodata flag, failures."""

import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from kartograf.core.bbox import BBox
from kartograf.download.cz_cutout import CzCutoutResult, run_cz_cutout


def _write_tif(path: Path, bbox: BBox, value: float, nodata: float = -9999.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    width = max(1, round(bbox.max_x - bbox.min_x) // 2)
    height = max(1, round(bbox.max_y - bbox.min_y) // 2)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        dtype="float32",
        count=1,
        width=width,
        height=height,
        crs=bbox.crs,
        transform=from_origin(bbox.min_x, bbox.max_y, 2, 2),
        nodata=nodata,
    ) as dst:
        dst.write(np.full((height, width), value, dtype="float32"), 1)


def _provider(value: float):
    provider = Mock()
    provider.descriptor_key = "cz.cuzk.dmr5g"
    provider.vertical_crs = "EVRF2007"
    provider.resolution = "2m"
    provider.horizontal_transform.return_value = None
    provider.vertical_transform = None

    def download_bbox(bbox, target, on_download=None):
        _write_tif(target, bbox, value)
        return target

    provider.download_bbox.side_effect = download_bbox
    return provider


B = BBox(330001.3, 260003.7, 331000.2, 261001.1, "EPSG:2180")
COORDS = [B.min_x, B.min_y, B.max_x, B.max_y]


def test_run_writes_sidecar_and_result(tmp_path):
    result = run_cz_cutout(
        _provider(300.0), B, output_dir=tmp_path, image_crs="EPSG:2180"
    )
    assert isinstance(result, CzCutoutResult)
    assert result.path.exists() and not result.all_nodata and not result.skipped
    meta = json.loads(
        result.path.with_name(result.path.name + ".meta.json").read_text()
    )
    assert meta["horizontal_crs"] == "EPSG:2180"
    assert meta["extra"]["all_nodata"] is False
    # grid from the requested bbox, as the CLI does today (no alignment in 0.7.1)
    assert meta["request"]["bbox"] == COORDS


def test_all_nodata_is_flagged(tmp_path, caplog):
    result = run_cz_cutout(
        _provider(-9999.0), B, output_dir=tmp_path, image_crs="EPSG:2180"
    )
    assert result.all_nodata is True
    # A6: not silent in the library either
    assert "nodata" in caplog.text
    meta = json.loads(
        result.path.with_name(result.path.name + ".meta.json").read_text()
    )
    assert meta["extra"]["all_nodata"] is True


def test_skipped_existing_all_nodata_flag(tmp_path):
    """Review Focus 5: an existing empty cutout still reports all_nodata."""
    run_cz_cutout(_provider(-9999.0), B, output_dir=tmp_path, image_crs="EPSG:2180")
    provider = _provider(300.0)
    again = run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert again.skipped is True and again.all_nodata is True
    provider.download_bbox.assert_not_called()


def test_unreadable_result_is_not_flagged(tmp_path):
    """D8: the nodata check is best-effort - it never aborts a download."""
    provider = _provider(1.0)

    def write_garbage(bbox, target, on_download=None):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"II*\x00dane")
        return target

    provider.download_bbox.side_effect = write_garbage
    result = run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert result.path.exists() and result.all_nodata is False


def test_failure_leaves_no_empty_dirs(tmp_path):
    from kartograf.exceptions import DownloadError

    provider = _provider(1.0)
    provider.download_bbox.side_effect = DownloadError("boom")
    with pytest.raises(DownloadError):
        run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert list(tmp_path.iterdir()) == []


def test_parent_request_in_sidecar(tmp_path):
    parent = {"bbox": [1, 2, 3, 4], "bbox_crs": "EPSG:4326", "countries": ["CZ", "PL"]}
    result = run_cz_cutout(
        _provider(5.0),
        B,
        output_dir=tmp_path,
        image_crs="EPSG:2180",
        parent_request=parent,
    )
    meta = json.loads(
        result.path.with_name(result.path.name + ".meta.json").read_text()
    )
    assert meta["extra"]["parent_request"] == parent


def test_download_cz_cutout_builds_provider(tmp_path, monkeypatch):
    from kartograf.download import cz_cutout

    seen = {}

    def factory(**kw):
        seen.update(kw)
        return _provider(1.0)

    # looked up lazily inside download_cz_cutout - patch it at the source
    monkeypatch.setattr("kartograf.providers.cuzk.create_dmr_provider", factory)
    result = cz_cutout.download_cz_cutout(
        B,
        output_dir=tmp_path,
        target_crs="EPSG:2180",
        vertical_crs="EVRF2007",
        resolution="2m",
    )
    assert seen["target_crs"] == "EPSG:2180" and seen["vertical_crs"] == "EVRF2007"
    meta = json.loads(
        result.path.with_name(result.path.name + ".meta.json").read_text()
    )
    assert meta["horizontal_crs"] == "EPSG:2180"


def test_native_target_crs_gives_native_provider(tmp_path, monkeypatch, caplog):
    """P9d: ``target_crs="EPSG:5514"`` (native) -> provider without
    reprojection (``target_crs=None``); an all-nodata result is a WARNING."""
    from kartograf.download import cz_cutout

    seen = {}

    def factory(**kw):
        seen.update(kw)
        return _provider(-9999.0)

    monkeypatch.setattr("kartograf.providers.cuzk.create_dmr_provider", factory)
    native = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
    result = cz_cutout.download_cz_cutout(
        native,
        output_dir=tmp_path,
        target_crs="EPSG:5514",
        vertical_crs="EVRF2007",
        resolution="2m",
    )
    assert seen["target_crs"] is None
    meta = json.loads(
        result.path.with_name(result.path.name + ".meta.json").read_text()
    )
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert result.all_nodata is True
    assert any(
        r.levelname == "WARNING" and "nodata" in r.getMessage() for r in caplog.records
    )
