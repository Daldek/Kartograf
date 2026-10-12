"""A6: CZ cutout in the library: sidecar, all-nodata flag, failures."""

import json
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from kartograf.core.bbox import BBox
from kartograf.download.cz_cutout import (
    CzCutoutResult,
    _check_cutout,
    _run_cz_cutout,
    check_cz_cutout,
    download_cz_cutout,
)
from kartograf.notices import ALL_NODATA, Notice


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


def test_cz_cutout_version_and_link(tmp_path):
    result = _run_cz_cutout(
        _provider(300.0), B, output_dir=tmp_path, image_crs="EPSG:2180"
    )
    assert isinstance(result, CzCutoutResult)
    assert result.file is not None
    assert result.file.status == "new" and not result.all_nodata
    assert result.file.path.exists()
    assert result.file.version_path.parent.parent.name == "bbox"
    assert os.path.samefile(result.file.path, result.file.version_path)
    version_meta = json.loads(
        result.file.version_path.with_name(
            result.file.version_path.name + ".meta.json"
        ).read_text()
    )
    link_meta = json.loads(
        result.file.path.with_name(result.file.path.name + ".meta.json").read_text()
    )
    assert version_meta["sha256"] == result.file.sha256
    assert version_meta["extra"]["version"] == {
        "label": result.file.label,
        "label_source": "downloaded",
    }
    assert "link" not in version_meta["extra"]
    assert link_meta["extra"]["link"] == "hardlink"
    assert version_meta["horizontal_crs"] == "EPSG:2180"
    assert version_meta["extra"]["all_nodata"] is False
    assert version_meta["request"]["bbox"] == COORDS


def test_all_nodata_is_flagged(tmp_path):
    result = _run_cz_cutout(
        _provider(-9999.0), B, output_dir=tmp_path, image_crs="EPSG:2180"
    )
    assert result.all_nodata is True
    assert result.file is not None
    meta = json.loads(
        result.file.version_path.with_name(
            result.file.version_path.name + ".meta.json"
        ).read_text()
    )
    assert meta["extra"]["all_nodata"] is True


def test_cz_cutout_default_local_without_network(tmp_path):
    first = _run_cz_cutout(
        _provider(-9999.0), B, output_dir=tmp_path, image_crs="EPSG:2180"
    )
    provider = _provider(300.0)
    again = _run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert first.file is not None and again.file is not None
    assert again.file.status == "local" and again.file.unverified == "none"
    assert again.file.version_path == first.file.version_path
    assert again.all_nodata is True
    provider.download_bbox.assert_not_called()


def test_unreadable_result_is_not_flagged(tmp_path):
    """D8: the nodata check is best-effort - it never aborts a download."""
    provider = _provider(1.0)

    def write_garbage(bbox, target, on_download=None):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"II*\x00dane")
        return target

    provider.download_bbox.side_effect = write_garbage
    result = _run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert result.file is not None
    assert result.file.path.exists() and result.all_nodata is False


def test_cz_cutout_failure_leaves_no_version_and_no_empty_tree(tmp_path):
    from kartograf.exceptions import DownloadError

    provider = _provider(1.0)
    provider.download_bbox.side_effect = DownloadError("boom")
    with pytest.raises(DownloadError):
        _run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert list(tmp_path.iterdir()) == []


def test_parent_request_in_sidecar(tmp_path):
    parent = {"bbox": [1, 2, 3, 4], "bbox_crs": "EPSG:4326", "countries": ["CZ", "PL"]}
    result = _run_cz_cutout(
        _provider(5.0),
        B,
        output_dir=tmp_path,
        image_crs="EPSG:2180",
        parent_request=parent,
    )
    assert result.file is not None
    meta = json.loads(
        result.file.version_path.with_name(
            result.file.version_path.name + ".meta.json"
        ).read_text()
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
    assert result.file is not None
    meta = json.loads(
        result.file.path.with_name(result.file.path.name + ".meta.json").read_text()
    )
    assert meta["horizontal_crs"] == "EPSG:2180"


def test_native_target_crs_gives_native_provider(tmp_path, monkeypatch):
    """P9d: ``target_crs="EPSG:5514"`` (native) -> provider without
    reprojection (``target_crs=None``); an all-nodata result is a notice."""
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
    assert result.file is not None
    meta = json.loads(
        result.file.path.with_name(result.file.path.name + ".meta.json").read_text()
    )
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert result.all_nodata is True
    assert result.notices == (
        Notice(
            "warning",
            ALL_NODATA,
            f"{result.file.path} jest w calosci nodata - obszar poza pokryciem "
            "DMR CUZK (poza granica CZ?)",
        ),
    )


# Selection shared by ``download_cz_cutout`` and ``check_cz_cutout``.
SELECTION = {"target_crs": "EPSG:2180", "vertical_crs": "EVRF2007", "resolution": "2m"}


def test_check_cz_cutout_same_args_as_download(tmp_path, monkeypatch):
    """No provider and no image CRS: the check takes the download's arguments."""
    provider = _provider(5.0)
    monkeypatch.setattr(
        "kartograf.providers.cuzk.create_dmr_provider", lambda **_kw: provider
    )
    selection = {"output_dir": tmp_path, "cache": False, **SELECTION}
    before = check_cz_cutout(B, **selection)
    result = download_cz_cutout(B, **selection)
    after = check_cz_cutout(B, **selection)
    assert before.items[0].status == "missing"
    assert before.items[0].unit == result.file.path.stem == after.items[0].unit
    assert after.items[0].local_sha256 == result.file.sha256
    provider.download_bbox.assert_called_once()


def test_download_cz_cutout_plan(tmp_path, monkeypatch):
    provider = _provider(5.0)
    monkeypatch.setattr(
        "kartograf.providers.cuzk.create_dmr_provider", lambda **_kw: provider
    )
    selection = {"output_dir": tmp_path, "cache": False, **SELECTION}
    plan = check_cz_cutout(B, **selection)
    changed = replace(plan.items[0], available_label="different")
    stale = download_cz_cutout(
        B, update="upgrade", plan=replace(plan, items=(changed,)), **selection
    )
    assert stale.file is None and stale.stale == (changed,)
    provider.download_bbox.assert_not_called()
    done = download_cz_cutout(B, update="upgrade", plan=plan, **selection)
    assert done.file is not None and done.file.status == "new"
    assert done.stale == ()
    provider.download_bbox.assert_called_once()


def test_cz_cutout_force_same_content_unchanged(tmp_path):
    provider = _provider(15.0)
    first = _run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    again = _run_cz_cutout(
        provider, B, output_dir=tmp_path, image_crs="EPSG:2180", update="force"
    )
    assert first.file is not None and again.file is not None
    assert again.file.status == "unchanged"
    assert again.file.version_path == first.file.version_path
    assert provider.download_bbox.call_count == 2
    versions = list(
        again.file.version_path.parent.parent.glob(f"*/{again.file.path.name}")
    )
    assert versions == [first.file.version_path]


def test_cz_cutout_local_all_nodata_from_sidecar(tmp_path, monkeypatch):
    from kartograf.download import cz_cutout

    _run_cz_cutout(_provider(-9999.0), B, output_dir=tmp_path, image_crs="EPSG:2180")

    def raster_read_is_forbidden(*args, **kwargs):
        raise AssertionError("local result must not read the raster")

    monkeypatch.setattr(cz_cutout, "read_tif_nodata", raster_read_is_forbidden)
    monkeypatch.setattr(cz_cutout, "_all_nodata", raster_read_is_forbidden)
    provider = _provider(1.0)
    local = _run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert local.file is not None and local.file.status == "local"
    assert local.all_nodata is True
    provider.download_bbox.assert_not_called()


def test_check_cz_cutout_never_downloads(tmp_path):
    provider = _provider(1.0)
    plan = _check_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert plan.store == str(tmp_path.resolve())
    assert len(plan.items) == 1
    assert plan.items[0].track == "cz_cutout"
    assert plan.items[0].status == "missing"
    assert plan.items[0].unit == plan.items[0].name.removesuffix(".tif")
    assert plan.items[0].segment == "nmt/cz_dmr5g_evrf2007"
    assert plan.items[0].hierarchy == "bbox"
    assert plan.items[0].available_label is None
    assert plan.items[0].available_signal is None
    provider.download_bbox.assert_not_called()

    done = _run_cz_cutout(
        provider,
        B,
        output_dir=tmp_path,
        image_crs="EPSG:2180",
        update="upgrade",
        plan=plan,
    )
    assert done.file is not None and done.file.status == "new"
    assert done.stale == ()
    current = _check_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert current.items[0].status == "unverifiable"
    provider.download_bbox.assert_called_once()


def test_cz_cutout_upgrade_plan_excluded_missing_and_stale(tmp_path):
    provider = _provider(1.0)
    plan = _check_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    excluded = replace(plan, items=())
    missing = _run_cz_cutout(
        provider,
        B,
        output_dir=tmp_path,
        image_crs="EPSG:2180",
        update="upgrade",
        plan=excluded,
    )
    assert missing.file is None and missing.stale == ()
    stale_plan = replace(plan, items=(replace(plan.items[0], available_label="older"),))
    stale = _run_cz_cutout(
        provider,
        B,
        output_dir=tmp_path,
        image_crs="EPSG:2180",
        update="upgrade",
        plan=stale_plan,
    )
    assert stale.file is None and stale.stale == stale_plan.items
    provider.download_bbox.assert_not_called()
    first = _run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert first.file is not None
    provider.download_bbox.reset_mock()
    local = _run_cz_cutout(
        provider,
        B,
        output_dir=tmp_path,
        image_crs="EPSG:2180",
        update="upgrade",
        plan=stale_plan,
    )
    assert local.file is not None and local.file.status == "local"
    assert local.file.version_path == first.file.version_path
    assert local.file.unverified is None and local.stale == stale_plan.items
    provider.download_bbox.assert_not_called()


def test_cz_cutout_legacy_plain_file_replaced_by_link(tmp_path):
    from kartograf.download.storage import bbox_cutout_path

    legacy = bbox_cutout_path(tmp_path, "nmt/cz_dmr5g_evrf2007", B, ".tif")
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy")
    provider = _provider(15.0)
    result = _run_cz_cutout(provider, B, output_dir=tmp_path, image_crs="EPSG:2180")
    assert result.file is not None and result.file.status == "new"
    assert legacy.read_bytes() != b"legacy"
    assert os.path.samefile(legacy, result.file.version_path)
    provider.download_bbox.assert_called_once()
