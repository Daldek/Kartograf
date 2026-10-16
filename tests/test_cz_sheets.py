"""Offline behavior of the CUZK sheet version store and HTTP freshness signal."""

import json
import os
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.download.cz_cutout import download_cz_cutout
from kartograf.download.cz_sheets import (
    _check_sheet,
    _run_cz_sheet,
    check_cz_sheet,
    download_cz_sheet,
)
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import ALL_NODATA, UNVERIFIED_LOCAL, Notice
from kartograf.providers.cuzk.raster import CzRasterRoute
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import channel_for
from kartograf.transform.crs import build_pinned_transform
from tests.cz_fakes import route_of
from tests.test_cuzk_laz import KLADY, RECORDED, TM33_TIFF_URL, CuzkSession

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
    """``CuzkRasterProvider`` fake: NMT 5m (DMR 4G, SM5 file) or 2m (DMR 5G,
    TM33 tile warped from the ImageServer), Bpv."""

    def __init__(self, *, sm5: bool = True, value: float = 120.0):
        self.descriptor_key = "cz.cuzk.dmr4g" if sm5 else "cz.cuzk.dmr5g"
        self.resolution = "5m" if sm5 else "2m"
        self.vertical_crs = "Bpv"
        self.sm5 = sm5
        self.value = value
        self.http = _HTTP.copy()
        self.heads = 0
        self.fetches = 0
        self.sheet_index = SimpleNamespace(
            sm5_sheet=lambda sheet: SimpleNamespace(name="Cesky Tesin 9-6", podil=0.99)
        )

    def route(self, sheet: str | None = None):
        return route_of(self.descriptor_key, self.vertical_crs, sheet)

    def file_signal(self, sheet: str) -> dict:
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
        patch.object(provider, "file_signal", side_effect=DownloadError("brak HEAD")),
        pytest.raises(DownloadError, match="brak HEAD"),
    ):
        _run_cz_sheet(provider, _SHEET, output_dir=tmp_path, update="upgrade")
    assert before.file is not None and before.file.path.exists()
    assert provider.fetches == 1


def test_sm5_default_local_version_asks_no_head(tmp_path):
    """The default mode asks no source for a local version (ADR-036 erratum 3):
    offline (HEAD would fail) the local file is used at once, ``unchecked``."""
    provider = SheetProvider()
    first = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    provider.http["etag"] = '"new-release"'
    with patch.object(
        provider, "file_signal", side_effect=DownloadError("brak HEAD")
    ) as head:
        result = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)
    assert result.file is not None and first.file is not None
    assert result.file.status == "local" and result.file.newer is None
    assert result.file.version_path == first.file.version_path
    assert result.file.unverified == "unchecked"
    assert head.call_count == 0 and provider.fetches == 1
    assert result.notices == ()


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
    with patch.object(sm5, "file_signal", side_effect=DownloadError("brak HEAD")):
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
        patch.object(provider, "file_signal", side_effect=DownloadError("brak HEAD")),
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
    extra_head = AssertionError("extra HEAD")
    with patch.object(provider, "file_signal", side_effect=extra_head):
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

    from kartograf.providers.cuzk.raster import CuzkRasterProvider

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
        patch("kartograf.providers.cuzk.raster.CuzkClient") as client,
        patch("kartograf.providers.cuzk.raster.SheetIndex") as sheet_index,
    ):
        sheet_index.return_value.sm5_sheet.return_value = SimpleNamespace(
            name=None, podil=None
        )
        client.return_value.fetch_file.side_effect = fetch_zip
        provider = CuzkRasterProvider("nmt", "5m", vertical_crs="Bpv")
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

    return patch(
        "kartograf.providers.cuzk.create_cz_raster_provider", side_effect=create
    )


def test_download_cz_sheet_sm5_without_resolution(tmp_path):
    seen: dict = {}
    with _factory(SheetProvider(), seen):
        result = download_cz_sheet(
            _SHEET, output_dir=tmp_path, product="nmt", vertical_crs="Bpv", cache=False
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
            product="nmt",
            vertical_crs="Bpv",
            resolution="2m",
            cache=False,
        )
    assert str(error.value) == (
        "Arkusze SM5 NMT CZ sa tylko w 5m (DMR 4G) - pomin --resolution albo "
        "podaj 5m; 2m: kafel TM33 (np. 302_5550) albo --bbox z --cutout"
    )
    assert provider.fetches == 0


def test_download_cz_sheet_tm33_requires_resolution(tmp_path):
    provider = SheetProvider(sm5=False)
    with _factory(provider), pytest.raises(ValidationError, match="wymagane"):
        download_cz_sheet(
            _TM33, output_dir=tmp_path, product="nmt", vertical_crs="Bpv", cache=False
        )
    assert provider.fetches == 0
    seen: dict = {}
    with _factory(provider, seen):
        result = download_cz_sheet(
            _TM33,
            output_dir=tmp_path,
            product="nmt",
            vertical_crs="Bpv",
            resolution="2m",
            cache=False,
        )
    assert seen["resolution"] == "2m"
    assert result.file is not None and result.file.status == "new"


def test_check_cz_sheet_plan_items(tmp_path):
    """The check takes the download's arguments; its plan drives the upgrade."""
    provider = SheetProvider()
    selection = {
        "output_dir": tmp_path,
        "product": "nmt",
        "vertical_crs": "Bpv",
        "cache": False,
    }
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
        "product": "nmt",
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
        f"{result.file.path} jest w calosci nodata - obszar poza pokryciem rastra "
        "CUZK (poza granica CZ?)",
    )
    assert result.notices == (expected,)
    assert seen == [expected]
    assert local.file is not None and local.file.status == "local"
    assert local.all_nodata and local.notices == ()


# --- the route table (plan B, decision 2) through the public functions ---------

_OPENZU = "https://openzu.cuzk.gov.cz/opendata"
_AGS = "https://ags.cuzk.gov.cz/arcgis2/rest/services"
_RAW_TM33 = "760_5518"


class _FirstRequest(Exception):
    """The first request for data reached the session (the route is known)."""


class _StopSession(CuzkSession):
    """The recorded sheet index answers; the first file or ``exportImage``
    request is recorded and stops the download."""

    def get(self, url, timeout=None, params=None, stream=False, **kwargs):
        if url.startswith(KLADY):
            return super().get(url, timeout=timeout, params=params, stream=stream)
        self._record("GET", url.split("?")[0])
        raise _FirstRequest(url)

    def head(self, url, timeout=None, allow_redirects=True, **kwargs):
        self._record("HEAD", url)
        raise _FirstRequest(url)


def _pinned(src_crs, dst_crs, policy):
    """The vertical Bpv->EVRF2007 operation as a stand-in (no PROJ grid, no
    network); horizontal operations are the real pinned ones."""
    if src_crs != "EPSG:8357":
        return build_pinned_transform(src_crs, dst_crs, policy)
    pinned = MagicMock()
    pinned.description = f"{src_crs} -> {dst_crs}"
    pinned.accuracy_m = 0.1
    return pinned


def _real_provider(session):
    """Real ``CuzkRasterProvider`` of the public functions on ``session``."""
    from kartograf.providers.cuzk import CuzkRasterProvider

    return patch(
        "kartograf.providers.cuzk.create_cz_raster_provider",
        side_effect=lambda **kwargs: CuzkRasterProvider(session=session, **kwargs),
    )


_PINNED = "kartograf.providers.cuzk.raster.build_pinned_transform"
_DMR4G_SM5 = f"{_OPENZU}/DMR4G-TIFF/epsg-5514/CTES96.zip"
_DMPOK_SM5 = f"{_OPENZU}/DMPOK-TIFF/epsg-5514/CTES96.zip"


@pytest.mark.parametrize(
    ("product", "resolution", "vertical_crs", "sheet", "request_url"),
    [
        # SM5 sheet: the S-JTSK file (EVRF2007 through the pinned operation)
        ("nmt", "5m", "Bpv", "CTES96", _DMR4G_SM5),
        ("nmt", None, "EVRF2007", "CTES96", _DMR4G_SM5),
        ("nmpt", "0.5m", "Bpv", "CTES96", _DMPOK_SM5),
        ("nmpt", None, "EVRF2007", "CTES96", _DMPOK_SM5),
        # TM33 tile in EVRF2007 of a model with files: the ETRS89 file
        ("nmt", "5m", "EVRF2007", _RAW_TM33, TM33_TIFF_URL),
        (
            "nmpt",
            "0.5m",
            "EVRF2007",
            _RAW_TM33,
            f"{_OPENZU}/DMPOK-TIFF/epsg-3045/760_5518.zip",
        ),
        # every other TM33 tile: the ImageServer warped onto the tile grid
        ("nmt", "5m", "Bpv", _RAW_TM33, f"{_AGS}/dmr4g/ImageServer/exportImage"),
        (
            "nmpt",
            "0.5m",
            "Bpv",
            _RAW_TM33,
            f"{_AGS}/dmp_obrazova_korelace/ImageServer/exportImage",
        ),
        ("nmt", "2m", "Bpv", _RAW_TM33, f"{_AGS}/dmr5g/ImageServer/exportImage"),
        ("nmt", "2m", "EVRF2007", _RAW_TM33, f"{_AGS}/dmr5g/ImageServer/exportImage"),
        ("nmpt", "2m", "Bpv", _RAW_TM33, f"{_AGS}/dmp1g/ImageServer/exportImage"),
        ("nmpt", "2m", "EVRF2007", _RAW_TM33, f"{_AGS}/dmp1g/ImageServer/exportImage"),
    ],
)
def test_route_table(product, resolution, vertical_crs, sheet, request_url, tmp_path):
    """Every raster row of decision 2: the first data request of the sheet."""
    session = _StopSession()
    with (
        _real_provider(session),
        patch(_PINNED, side_effect=_pinned),
        pytest.raises(_FirstRequest),
    ):
        download_cz_sheet(
            sheet,
            output_dir=tmp_path,
            product=product,
            resolution=resolution,
            vertical_crs=vertical_crs,
            cache=False,
        )
    assert session.of("GET") == [request_url]
    assert session.of("HEAD") == []
    assert "/dmp/" not in request_url  # DMP OK: only dmp_obrazova_korelace


@pytest.mark.parametrize(
    ("product", "resolution", "vertical_crs", "sheet", "error"),
    [
        (
            "nmt",
            "2m",
            "Bpv",
            "CTES96",
            "Arkusze SM5 NMT CZ sa tylko w 5m (DMR 4G) - pomin --resolution albo "
            "podaj 5m; 2m: kafel TM33 (np. 302_5550) albo --bbox z --cutout",
        ),
        (
            "nmpt",
            "2m",
            "EVRF2007",
            "CTES96",
            "Arkusze SM5 NMPT CZ sa tylko w 0.5m (DMP OK) - pomin --resolution albo "
            "podaj 0.5m; 2m: kafel TM33 (np. 302_5550) albo --bbox z --cutout",
        ),
        (
            "nmpt",
            None,
            "Bpv",
            _RAW_TM33,
            "--resolution wymagane dla NMPT CZ: 0.5m (DMP OK), 2m (DMP 1G)",
        ),
        (
            "nmpt",
            "1m",
            "Bpv",
            _RAW_TM33,
            "CZ nie ma rozdzielczosci 1m dla NMPT - dostepne: 0.5m (DMP OK), "
            "2m (DMP 1G)",
        ),
    ],
)
def test_route_table_rejected_before_network(
    product, resolution, vertical_crs, sheet, error, tmp_path
):
    """A choice without a row of the route table: the error, no request."""
    session = _StopSession()
    for call in (download_cz_sheet, check_cz_sheet):
        with (
            _real_provider(session),
            pytest.raises(ValidationError) as caught,
        ):
            call(
                sheet,
                output_dir=tmp_path,
                product=product,
                resolution=resolution,
                vertical_crs=vertical_crs,
                cache=False,
            )
        assert str(caught.value) == error
    assert session.calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("product", "resolution", "service"),
    [
        ("nmt", "2m", "dmr5g"),
        ("nmt", "5m", "dmr4g"),
        ("nmpt", "2m", "dmp1g"),
        ("nmpt", "0.5m", "dmp_obrazova_korelace"),
    ],
)
def test_route_table_cutout_is_the_image_server(product, resolution, service, tmp_path):
    """A cutout of every label: the ImageServer of the model (native 5514)."""
    session = _StopSession()
    with _real_provider(session), pytest.raises(_FirstRequest):
        download_cz_cutout(
            BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514"),
            output_dir=tmp_path,
            product=product,
            horizontal_crs="EPSG:5514",
            vertical_crs="Bpv",
            resolution=resolution,
            cache=False,
        )
    assert session.of("GET") == [f"{_AGS}/{service}/ImageServer/exportImage"]


def _zip_raster(path: Path) -> tuple[np.ndarray, tuple]:
    """Values and georeference (``.tfw``) of the ``.tif`` member of a CUZK ZIP
    (the member has no geotransform of its own: georeference only in ``.tfw``)."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        (tif,) = [n for n in names if n.endswith(".tif")]
        (tfw,) = [n for n in names if n.endswith(".tfw")]
        world = [float(v) for v in archive.read(tfw).decode().split()]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", rasterio.errors.NotGeoreferencedWarning)
            with MemoryFile(archive.read(tif)) as memory, memory.open() as raster:
                return raster.read(1), tuple(world)


def test_tm33_file_is_native_evrf2007(tmp_path):
    """DMR 4G 760_5518 in EVRF2007: the ETRS89 file 1:1, no pinned operation."""
    session = CuzkSession()
    with (
        _real_provider(session),
        patch(_PINNED, side_effect=AssertionError("no operation on a native file")),
    ):
        result = download_cz_sheet(
            _RAW_TM33,
            output_dir=tmp_path,
            product="nmt",
            resolution="5m",
            vertical_crs="EVRF2007",
            cache=False,
        )
    assert session.of("GET") == [TM33_TIFF_URL]
    file = result.file
    assert file is not None and file.status == "new"
    assert file.path == tmp_path / "nmt/cz_dmr4g_evrf2007/760/5518/760_5518.tif"
    values, world = _zip_raster(RECORDED / "openzu_DMR4G-TIFF_3045_760_5518.zip")
    with rasterio.open(file.path) as raster:
        assert raster.crs.to_epsg() == 3045
        np.testing.assert_array_equal(raster.read(1), values)
        transform = raster.transform
    # the .tfw gives the pixel CENTRE of the upper-left pixel
    assert (transform.a, transform.e) == (world[0], world[3])
    assert transform.c == pytest.approx(world[4] - world[0] / 2)
    assert transform.f == pytest.approx(world[5] - world[3] / 2)
    meta = _metadata(file.version_path)
    assert meta["dataset"] == "cz.cuzk.dmr4g"
    assert meta["horizontal_crs"] == "EPSG:3045"
    assert meta["vertical_crs"] == "EPSG:5621"
    assert meta["transform"] is None  # neither horizontal nor vertical operation
    assert meta["extra"]["http"]["etag"] == '"c38fbfc1e789dc1:0"'


def test_tm33_file_route_signal_and_capability():
    """Native file rows compare the HTTP signal; warps have no cheap signal."""
    from kartograf.providers.cuzk import CuzkRasterProvider

    with patch(_PINNED, side_effect=_pinned):
        native = CuzkRasterProvider("nmt", "5m", vertical_crs="EVRF2007")
        warped = CuzkRasterProvider("nmt", "5m", vertical_crs="Bpv")
        file_route = native.route(_RAW_TM33)
        warp_route = warped.route(_RAW_TM33)
    assert file_route.files and file_route.capability == "sheet_files"
    assert file_route.channel.update_signal == "http"
    assert (file_route.horizontal, file_route.vertical) == (None, None)
    assert not warp_route.files and warp_route.capability == "bbox_raster"
    assert warp_route.channel.update_signal == "none"
    assert warp_route.horizontal_crs == "EPSG:3045"
    assert warp_route.horizontal is not None and warp_route.vertical is None


def test_sm5_evrf2007_still_transformed(tmp_path):
    """SM5 + EVRF2007: the S-JTSK file and the pinned Bpv->EVRF2007 operation
    (values shifted, the operation in the sidecar)."""
    from kartograf.providers.cuzk import CuzkRasterProvider

    vertical = MagicMock()
    vertical.description = "Baltic 1957 height to EVRF2007 height (1)"
    vertical.accuracy_m = 0.1
    vertical.transform.side_effect = lambda x, y, z: (x, y, np.asarray(z) + 0.13)
    lonlat = MagicMock()
    lonlat.transform.side_effect = lambda x, y: (x, y)

    def pinned(src_crs, dst_crs, policy):
        return vertical if src_crs == "EPSG:8357" else lonlat

    def fetch_zip(url, output_path, *, unzip_single, on_response):
        _write_raster(output_path, value=120.0)
        on_response(SimpleNamespace(headers=_GET_HEADERS))
        return output_path

    with (
        patch("kartograf.providers.cuzk.raster.CuzkClient") as client,
        patch("kartograf.providers.cuzk.raster.SheetIndex") as sheet_index,
        patch(_PINNED, side_effect=pinned),
    ):
        sheet_index.return_value.sm5_sheet.return_value = SimpleNamespace(
            name="Cesky Tesin 9-6", podil=0.99
        )
        client.return_value.fetch_file.side_effect = fetch_zip
        provider = CuzkRasterProvider("nmt", "5m", vertical_crs="EVRF2007")
        result = _run_cz_sheet(provider, _SHEET, output_dir=tmp_path)

    assert client.return_value.fetch_file.call_args.args[0] == (
        f"{_OPENZU}/DMR4G-TIFF/epsg-5514/CTES96.zip"
    )
    assert result.file is not None
    with rasterio.open(result.file.path) as raster:
        assert raster.crs.to_epsg() == 5514
        assert raster.read(1)[0, 0] == pytest.approx(120.13, abs=1e-4)
    meta = _metadata(result.file.version_path)
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert meta["vertical_crs"] == "EPSG:5621"
    assert meta["transform"] == {
        "vertical": "pinned: Baltic 1957 height to EVRF2007 height (1) (0.1 m)"
    }


class _WarpedTile(SheetProvider):
    """A DMR 4G TM33 tile in EVRF2007 as Kartograf 0.7 stored it: the
    ImageServer warped onto the tile grid (signal ``none``, no ``extra.http``)."""

    def __init__(self) -> None:
        super().__init__(sm5=True, value=300.0)
        self.vertical_crs = "EVRF2007"

    def route(self, sheet: str | None = None):
        image = channel_for(self.descriptor_key, TransportKind.ARCGIS_IMAGE)
        return CzRasterRoute(image, "EPSG:3045", None, None)


def test_existing_tm33_warp_kept_locally(tmp_path):
    """Decision 12: the warped version stays in the default mode and with
    ``upgrade`` (one Info, no download); ``force`` stores the CUZK file as a
    new version and moves the standard path to it."""
    warped = _run_cz_sheet(_WarpedTile(), _RAW_TM33, output_dir=tmp_path).file
    assert warped is not None
    assert "http" not in _metadata(warped.version_path)["extra"]
    selection = {
        "output_dir": tmp_path,
        "product": "nmt",
        "resolution": "5m",
        "vertical_crs": "EVRF2007",
        "cache": False,
    }
    session = CuzkSession()
    with _real_provider(session):
        kept = download_cz_sheet(_RAW_TM33, **selection)
        upgraded = download_cz_sheet(_RAW_TM33, update="upgrade", **selection)
        assert session.of("GET") == []
        forced = download_cz_sheet(_RAW_TM33, update="force", **selection)

    # the default mode asks nothing; upgrade compares and reports decision 12
    assert kept.file is not None and kept.file.status == "local"
    assert kept.file.version_path == warped.version_path
    assert kept.file.unverified == "unchecked" and kept.notices == ()
    assert upgraded.file is not None and upgraded.file.status == "local"
    assert upgraded.file.version_path == warped.version_path
    assert upgraded.file.unverified == "none"
    assert [n.code for n in upgraded.notices] == [UNVERIFIED_LOCAL]
    assert upgraded.notices[0].level == "info"
    assert "--force" in upgraded.notices[0].text
    assert session.of("GET") == [TM33_TIFF_URL]
    assert forced.file is not None and forced.file.status == "new"
    assert forced.file.version_path != warped.version_path
    assert warped.version_path.exists()
    assert os.path.samefile(forced.file.path, forced.file.version_path)
    assert _metadata(forced.file.version_path)["extra"]["http"]["etag"] == (
        '"c38fbfc1e789dc1:0"'
    )


def test_existing_tm33_warp_upgrade_reported_once(tmp_path):
    """``download_data`` with ``upgrade``: one Info of the track (decision 12),
    not a second generic one of the request."""
    from kartograf.download.data import download_data

    _run_cz_sheet(_WarpedTile(), _RAW_TM33, output_dir=tmp_path)
    with _real_provider(CuzkSession()):
        report = download_data(
            product="nmt",
            output_dir=tmp_path,
            sheet=_RAW_TM33,
            resolution="5m",
            vertical_crs="EVRF2007",
            update="upgrade",
            cache=False,
        )
    assert report.ok
    assert [notice.code for notice in report.notices] == [UNVERIFIED_LOCAL]
    assert "bez sygnalu HTTP pliku CUZK" in report.notices[0].text
