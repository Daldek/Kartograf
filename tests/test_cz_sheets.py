"""Offline behavior of the CUZK sheet version store and HTTP freshness signal."""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from kartograf.download.cz_sheets import (
    _check_sheet,
    _run_cz_sheet,
    check_cz_sheet,
    download_cz_sheet,
)
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import ALL_NODATA, Notice

_FIXTURE = Path("tests/fixtures/signals/real_2026_10_12/cuzk_sm5_ctes96_get.json")
_GET_HEADERS = json.loads(_FIXTURE.read_text(encoding="utf-8"))["headers"]
_HTTP = {
    "etag": _GET_HEADERS["ETag"],
    "last_modified": _GET_HEADERS["Last-Modified"],
    "content_length": int(_GET_HEADERS["Content-Length"]),
}
_SHEET = "CTES96"
_TM33 = "302_5550"


def _metadata(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


def _write_raster(path: Path, *, value: float = 120.0, nodata: float = -9999.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        dtype="float32",
        count=1,
        width=2,
        height=2,
        crs="EPSG:5514",
        transform=from_origin(-450000, -1112000, 5, 5),
        nodata=nodata,
    ) as dataset:
        dataset.write(np.full((2, 2), value, dtype="float32"), 1)


class SheetProvider:
    def __init__(self, *, sm5: bool = True, value: float = 120.0):
        self.descriptor_key = "cz.cuzk.dmr4g" if sm5 else "cz.cuzk.dmr5g"
        self.resolution = "5m" if sm5 else "2m"
        self.vertical_crs = "Bpv"
        self.vertical_transform = None
        self.sm5 = sm5
        self.value = value
        self.http = _HTTP.copy()
        self.heads = 0
        self.fetches = 0
        self.sheet_index = SimpleNamespace(
            sm5_sheet=lambda sheet: SimpleNamespace(name="Cesky Tesin 9-6", podil=0.99)
        )

    def horizontal_transform(self, crs: str):
        return None

    def sm5_signal(self, sheet: str) -> dict:
        self.heads += 1
        return self.http.copy()

    def download(self, sheet: str, target: Path, *, on_download=None, on_response=None):
        self.fetches += 1
        if on_download is not None:
            on_download()
        if on_response is not None:
            on_response(
                SimpleNamespace(
                    headers={
                        "ETag": self.http["etag"],
                        "Last-Modified": self.http["last_modified"],
                        "Content-Length": str(self.http["content_length"]),
                    }
                )
            )
        _write_raster(target, value=self.value)
        return target


def test_sm5_version_with_extra_http(tmp_path):
    provider = SheetProvider()
    result = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    file = result.file
    assert file is not None
    assert file.status == "new"
    assert provider.fetches == 1 and provider.heads == 0
    assert file.path == tmp_path / "nmt/cz_dmr4g_bpv/CTES/96/CTES96.tif"
    assert file.version_path.parent.name == f"{file.label}_{file.sha256[:8]}"
    assert (
        file.version_path.parent.parent
        == tmp_path / "nmt/cz_dmr4g_bpv/versions/CTES/96"
    )
    assert os.path.samefile(file.path, file.version_path)
    version = _metadata(file.version_path)
    assert version["sha256"] == file.sha256
    assert version["extra"]["version"] == {
        "label": file.label,
        "label_source": "downloaded",
    }
    assert version["extra"]["http"] == _HTTP
    assert "link" not in version["extra"]
    assert _metadata(file.path)["extra"]["link"] == "hardlink"


def test_sm5_default_same_etag_is_local_one_head(tmp_path):
    provider = SheetProvider()
    first = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    second = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    assert second.file is not None and first.file is not None
    assert second.file.status == "local"
    assert second.file.version_path == first.file.version_path
    assert provider.fetches == 1 and provider.heads == 1


def test_sm5_default_new_etag_is_local_with_newer(tmp_path):
    provider = SheetProvider()
    _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    provider.http["etag"] = '"new-release"'
    result = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    assert result.file is not None
    assert result.file.status == "local" and result.file.newer == '"new-release"'
    assert provider.heads == 1 and provider.fetches == 1


def test_sm5_upgrade_new_etag_downloads(tmp_path):
    provider = SheetProvider()
    before = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    provider.http["etag"] = '"new-release"'
    provider.value = 250.0
    after = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path, update="upgrade")
    assert after.file is not None and before.file is not None
    assert after.file.status == "new"
    assert after.file.sha256 != before.file.sha256
    assert provider.fetches == 2 and provider.heads == 1
    assert os.path.samefile(after.file.path, after.file.version_path)
    assert before.file.version_path.exists()
    assert (
        _metadata(after.file.version_path)["extra"]["http"]["etag"] == '"new-release"'
    )


def test_sm5_upgrade_head_failure_is_error(tmp_path):
    provider = SheetProvider()
    before = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    with (
        patch.object(provider, "sm5_signal", side_effect=DownloadError("brak HEAD")),
        pytest.raises(DownloadError, match="brak HEAD"),
    ):
        _run_cz_sheet(provider, _SHEET, output_dir=tmp_path, update="upgrade")
    assert before.file is not None and before.file.path.exists()
    assert provider.fetches == 1


def test_sm5_default_head_failure_is_local_unverified(tmp_path):
    provider = SheetProvider()
    _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    with patch.object(provider, "sm5_signal", side_effect=DownloadError("brak HEAD")):
        result = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    assert result.file is not None
    assert result.file.status == "local"
    assert result.file.unverified == "check_failed: brak HEAD"
    assert provider.fetches == 1


def test_tm33_default_is_local_without_network(tmp_path):
    provider = SheetProvider(sm5=False)
    first = _run_cz_sheet(provider, _TM33, output_dir=tmp_path)
    second = _run_cz_sheet(provider, _TM33, output_dir=tmp_path)
    assert first.file is not None and second.file is not None
    assert second.file.status == "local" and second.file.newer is None
    assert provider.heads == 0 and provider.fetches == 1
    assert "http" not in _metadata(first.file.version_path)["extra"]


def test_tm33_upgrade_is_local_unverified_none(tmp_path):
    provider = SheetProvider(sm5=False)
    _run_cz_sheet(provider, _TM33, output_dir=tmp_path)
    result = _run_cz_sheet(provider, _TM33, output_dir=tmp_path, update="upgrade")
    assert result.file is not None
    assert result.file.status == "local" and result.file.unverified == "none"
    assert provider.fetches == 1 and provider.heads == 0


def test_check_cz_sheet_never_downloads(tmp_path):
    sm5 = SheetProvider()
    missing = _check_sheet(sm5, _SHEET, output_dir=tmp_path)
    assert missing.items[0].status == "missing"
    assert missing.items[0].track == "cz_sheet" and missing.items[0].unit == _SHEET
    assert missing.items[0].available_signal == _HTTP
    assert sm5.fetches == 0
    _run_cz_sheet(sm5, _SHEET, output_dir=tmp_path)
    assert _check_sheet(sm5, _SHEET, output_dir=tmp_path).items[0].status == "current"
    sm5.http["etag"] = '"changed"'
    assert _check_sheet(sm5, _SHEET, output_dir=tmp_path).items[0].status == "newer"
    with patch.object(sm5, "sm5_signal", side_effect=DownloadError("brak HEAD")):
        failure = _check_sheet(sm5, _SHEET, output_dir=tmp_path).items[0]
    assert failure.status == "check_failed" and failure.error == "brak HEAD"
    assert sm5.fetches == 1

    tm33 = SheetProvider(sm5=False)
    assert _check_sheet(tm33, _TM33, output_dir=tmp_path).items[0].status == "missing"
    _run_cz_sheet(tm33, _TM33, output_dir=tmp_path)
    assert (
        _check_sheet(tm33, _TM33, output_dir=tmp_path).items[0].status == "unverifiable"
    )
    assert tm33.fetches == 1 and tm33.heads == 0


def test_cz_sm5_upgrade_plan_etag_changed_is_stale(tmp_path):
    provider = SheetProvider()
    plan = _check_sheet(provider, _SHEET, output_dir=tmp_path)
    provider.http["etag"] = '"replaced-since-plan"'
    result = _run_cz_sheet(
        provider, _SHEET, output_dir=tmp_path, update="upgrade", plan=plan
    )
    assert result.file is None
    assert result.stale == plan.items
    assert provider.heads == 2 and provider.fetches == 0
    assert not list(tmp_path.rglob("*.tif"))


def test_cz_sm5_upgrade_plan_downloads_only_matching_signal(tmp_path):
    provider = SheetProvider()
    plan = _check_sheet(provider, _SHEET, output_dir=tmp_path)
    result = _run_cz_sheet(
        provider, _SHEET, output_dir=tmp_path, update="upgrade", plan=plan
    )
    assert result.file is not None and result.file.status == "new"
    assert result.stale == ()
    assert provider.heads == 2 and provider.fetches == 1


def test_cz_sm5_upgrade_plan_head_failure_is_error(tmp_path):
    provider = SheetProvider()
    plan = _check_sheet(provider, _SHEET, output_dir=tmp_path)
    with (
        patch.object(provider, "sm5_signal", side_effect=DownloadError("brak HEAD")),
        pytest.raises(DownloadError, match="brak HEAD"),
    ):
        _run_cz_sheet(
            provider, _SHEET, output_dir=tmp_path, update="upgrade", plan=plan
        )
    assert provider.fetches == 0


def test_cz_sheet_unrelated_plan_item_is_not_stale(tmp_path):
    provider = SheetProvider()
    tm33 = SheetProvider(sm5=False)
    plan = _check_sheet(tm33, _TM33, output_dir=tmp_path)
    result = _run_cz_sheet(
        provider, _SHEET, output_dir=tmp_path, update="upgrade", plan=plan
    )
    assert result.file is None and result.stale == ()
    assert provider.heads == 0 and provider.fetches == 0


def test_cz_sheet_plan_omitted_item_keeps_local_without_probe(tmp_path):
    provider = SheetProvider()
    first = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    current = _check_sheet(provider, _SHEET, output_dir=tmp_path)
    with patch.object(provider, "sm5_signal", side_effect=AssertionError("extra HEAD")):
        result = _run_cz_sheet(
            provider, _SHEET, output_dir=tmp_path, update="upgrade", plan=current
        )
    assert result.file is not None and first.file is not None
    assert result.file.status == "local" and result.file.unverified is None
    assert result.file.version_path == first.file.version_path
    assert result.stale == () and provider.fetches == 1
    assert provider.heads == 1


def test_cz_sheet_legacy_plain_file_replaced_by_link(tmp_path):
    provider = SheetProvider(sm5=False)
    path = tmp_path / "nmt/cz_dmr5g_bpv/302/5550/302_5550.tif"
    _write_raster(path, value=99)
    Path(f"{path}.meta.json").write_text(json.dumps({"request": {"sheet": _TM33}}))
    result = _run_cz_sheet(provider, _TM33, output_dir=tmp_path)
    assert result.file is not None and result.file.status == "new"
    assert os.path.samefile(path, result.file.version_path)
    assert _metadata(path)["extra"]["link"] == "hardlink"
    assert provider.fetches == 1


def test_sm5_worldfile_georeference_survives_staging_cleanup(tmp_path):
    """Openzu often carries coordinates only in a .tfw outside its TIFF."""
    import warnings

    from kartograf.providers.cuzk.dmr import CuzkDmrProvider

    def fetch_zip(url, output_path, *, unzip_single, on_response):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", rasterio.errors.NotGeoreferencedWarning)
            with rasterio.open(
                output_path,
                "w",
                driver="GTiff",
                dtype="float32",
                count=1,
                width=2,
                height=2,
                nodata=-9999.0,
            ) as dataset:
                dataset.write(np.full((2, 2), 120.0, dtype="float32"), 1)
        output_path.with_suffix(".tfw").write_text(
            "5\n0\n0\n-5\n-449997.5\n-1112002.5\n"
        )
        on_response(SimpleNamespace(headers=_GET_HEADERS))
        return output_path

    with (
        patch("kartograf.providers.cuzk.dmr.CuzkClient") as client,
        patch("kartograf.providers.cuzk.dmr.SheetIndex") as sheet_index,
    ):
        sheet_index.return_value.sm5_sheet.return_value = SimpleNamespace(
            name=None, podil=None
        )
        client.return_value.fetch_file.side_effect = fetch_zip
        provider = CuzkDmrProvider(resolution="5m", vertical_crs="Bpv")
        result = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)

    assert result.file is not None
    assert not result.file.path.with_suffix(".tfw").exists()
    with rasterio.open(result.file.path) as raster:
        assert raster.crs.to_epsg() == 5514
        assert tuple(raster.bounds) == (-450000.0, -1112010.0, -449990.0, -1112000.0)


def test_cz_sheet_sidecar_fields_unchanged(tmp_path):
    sm5 = SheetProvider()
    result = _run_cz_sheet(sm5, _SHEET, output_dir=tmp_path)
    assert result.file is not None
    meta = _metadata(result.file.version_path)
    assert meta["dataset"] == "cz.cuzk.dmr4g"
    assert meta["request"] == {"sheet": _SHEET}
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert meta["vertical_crs"] == "EPSG:8357"
    assert meta["extra"]["mapname"] == "Cesky Tesin 9-6"
    assert meta["extra"]["cz_share"] == 0.99
    tm33 = SheetProvider(sm5=False)
    tile = _run_cz_sheet(tm33, _TM33, output_dir=tmp_path)
    assert tile.file is not None
    tile_meta = _metadata(tile.file.version_path)
    assert tile_meta["dataset"] == "cz.cuzk.dmr5g"
    assert tile_meta["request"] == {"sheet": _TM33}
    assert tile_meta["horizontal_crs"] == "EPSG:3045"
    assert "cz_share" not in tile_meta["extra"]


def test_cz_sheet_local_all_nodata_from_sidecar(tmp_path):
    provider = SheetProvider(sm5=False, value=-9999.0)
    first = _run_cz_sheet(provider, _TM33, output_dir=tmp_path)
    assert first.file is not None and first.all_nodata
    assert _metadata(first.file.version_path)["extra"]["all_nodata"] is True
    with (
        patch(
            "kartograf.download.cz_sheets.read_tif_nodata",
            side_effect=AssertionError("raster opened"),
        ),
        patch(
            "kartograf.download.cz_sheets._all_nodata",
            side_effect=AssertionError("raster scanned"),
        ),
    ):
        result = _run_cz_sheet(provider, _TM33, output_dir=tmp_path)
    assert result.file is not None and result.file.status == "local"
    assert result.all_nodata


def test_cz_sheet_check_mode_rejects_download(tmp_path):
    provider = SheetProvider()
    with pytest.raises(ValidationError, match="check"):
        _run_cz_sheet(provider, _SHEET, output_dir=tmp_path, update="check")
    assert provider.fetches == 0


# --- public API: download_cz_sheet / check_cz_sheet (same selection arguments)


def _factory(provider: SheetProvider, seen: dict | None = None):
    """Patch of the CZ DMR provider factory used by the public sheet functions."""

    def create(**kwargs):
        if seen is not None:
            seen.update(kwargs)
        return provider

    return patch("kartograf.providers.cuzk.create_dmr_provider", side_effect=create)


def test_download_cz_sheet_sm5_without_resolution(tmp_path):
    seen: dict = {}
    with _factory(SheetProvider(), seen):
        result = download_cz_sheet(
            _SHEET, output_dir=tmp_path, vertical_crs="Bpv", cache=False
        )
    assert seen["resolution"] == "5m" and seen["vertical_crs"] == "Bpv"
    assert result.file is not None and result.file.status == "new"
    assert result.notices == ()


def test_download_cz_sheet_sm5_2m_is_validation_error(tmp_path):
    provider = SheetProvider()
    with _factory(provider), pytest.raises(ValidationError) as error:
        download_cz_sheet(
            _SHEET,
            output_dir=tmp_path,
            vertical_crs="Bpv",
            resolution="2m",
            cache=False,
        )
    assert str(error.value) == (
        "Arkusze SM5 sa dostepne tylko w 5m (DMR 4G) - pomin --resolution albo "
        "podaj 5m; dla 2m uzyj godla TM33 albo --bbox [arkusz: CTES96]"
    )
    assert provider.fetches == 0


def test_download_cz_sheet_tm33_requires_resolution(tmp_path):
    provider = SheetProvider(sm5=False)
    with _factory(provider), pytest.raises(ValidationError, match="wymagane"):
        download_cz_sheet(_TM33, output_dir=tmp_path, vertical_crs="Bpv", cache=False)
    assert provider.fetches == 0
    seen: dict = {}
    with _factory(provider, seen):
        result = download_cz_sheet(
            _TM33,
            output_dir=tmp_path,
            vertical_crs="Bpv",
            resolution="2m",
            cache=False,
        )
    assert seen["resolution"] == "2m"
    assert result.file is not None and result.file.status == "new"


def test_check_cz_sheet_plan_items(tmp_path):
    """The check takes the download's arguments; its plan drives the upgrade."""
    provider = SheetProvider()
    selection = {"output_dir": tmp_path, "vertical_crs": "Bpv", "cache": False}
    with _factory(provider):
        missing = check_cz_sheet(_SHEET, **selection)
        assert [(i.track, i.unit, i.status) for i in missing.items] == [
            ("cz_sheet", _SHEET, "missing")
        ]
        assert provider.fetches == 0
        done = download_cz_sheet(_SHEET, update="upgrade", plan=missing, **selection)
        assert done.file is not None and done.file.status == "new"
        assert check_cz_sheet(_SHEET, **selection).items[0].status == "current"


def test_cz_all_nodata_notice(tmp_path):
    provider = SheetProvider(sm5=False, value=-9999.0)
    seen: list[Notice] = []
    selection = {
        "output_dir": tmp_path,
        "vertical_crs": "Bpv",
        "resolution": "2m",
        "cache": False,
    }
    with _factory(provider):
        result = download_cz_sheet(_TM33, on_notice=seen.append, **selection)
        local = download_cz_sheet(_TM33, **selection)
    assert result.file is not None and result.all_nodata
    expected = Notice(
        "warning",
        ALL_NODATA,
        f"{result.file.path} jest w calosci nodata - obszar poza pokryciem DMR "
        "CUZK (poza granica CZ?)",
    )
    assert result.notices == (expected,)
    assert seen == [expected]
    assert local.file is not None and local.file.status == "local"
    assert local.all_nodata and local.notices == ()
