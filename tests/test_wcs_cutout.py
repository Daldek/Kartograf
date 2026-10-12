"""PL cutout from GUGiK WCS (ADR-035): library and CLI on recorded WCS responses."""

import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import rasterio
import requests

from kartograf.cli.commands import main
from kartograf.core.sheet_parser import BBox
from kartograf.download.cutout import (
    check_pl_cutout,
    download_pl_cutout,
    prepare_pl_cutout,
    run_pl_wcs_cutout,
)
from kartograf.download.plan import UpdatePlan
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.prg import LandMask
from tests.conftest import (
    WCS_FIXTURES,
    multipart_asc_body,
    recorded_response,
    write_gpkg_layers,
)

NOW = datetime(2026, 10, 11, tzinfo=UTC)
# Request inside the recorded 20 x 20 m window (fixture README), off the grid.
BBOX = BBox(567580.6, 243664.7, 567600.4, 243684.3, "EPSG:2180")
WINDOW = (567580.5, 567600.5, 243664.5, 243684.5)
MASK = "kartograf.providers.pl.prg.fetch_land_mask"


def _square(x0, y0, x1, y1) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


ALL_LAND = LandMask((_square(0, 0, 1_000_000, 1_000_000),), ())


def _subset(url: str) -> tuple[float, float, float, float]:
    subsets = parse_qs(urlparse(url).query)["SUBSET"]
    x = next(s for s in subsets if s.startswith("x("))[2:-1].split(",")
    y = next(s for s in subsets if s.startswith("y("))[2:-1].split(",")
    return float(x[0]), float(x[1]), float(y[0]), float(y[1])


def _recorded_subset(path: Path) -> tuple[float, float, float, float]:
    head = path.read_bytes()[:600].decode()
    field = {
        key: float(value)
        for key, value in re.findall(
            r"(ncols|nrows|xllcorner|yllcorner|cellsize)\s+(\S+)", head
        )
    }
    x0, y0, step = field["xllcorner"], field["yllcorner"], field["cellsize"]
    return (x0, x0 + field["ncols"] * step, y0, y0 + field["nrows"] * step)


def _recorded_session(base: str = "nmt_evrf2007_20x20") -> Mock:
    """``session.get`` answers each recorded SUBSET with its raw response."""
    by_subset = {_recorded_subset(p): p for p in WCS_FIXTURES.glob(f"{base}*.mime")}
    session = Mock(spec=requests.Session)
    session.get = Mock(
        side_effect=lambda url, **kw: recorded_response(by_subset[_subset(url)])
    )
    return session


def _synthetic_session(values) -> Mock:
    """``session.get`` answers any SUBSET with ``values(xs, ys)`` at pixel centres."""

    def respond(url, **kwargs):
        x0, x1, y0, y1 = _subset(url)
        cols, rows = round(x1 - x0), round(y1 - y0)
        xs = x0 + 0.5 + np.arange(cols)[None, :]
        ys = y1 - 0.5 - np.arange(rows)[:, None]
        grid = np.broadcast_to(values(xs, ys), (rows, cols)).astype("float32")
        return recorded_response(
            WCS_FIXTURES / "nmt_evrf2007_20x20.mime",
            body=multipart_asc_body(grid, x0, y0),
        )

    session = Mock(spec=requests.Session)
    session.get = Mock(side_effect=respond)
    return session


def _cutout(tmp_path, target_crs="EPSG:2180", bbox=BBOX, **kwargs):
    kwargs = {"vertical_crs": "EVRF2007", "product": "nmt", **kwargs}
    return prepare_pl_cutout(bbox, target_crs, output_dir=tmp_path, **kwargs)


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(f"{path.name}.meta.json").read_text("utf-8"))


def test_wcs_cutout_2180_corner_on_sheet_grid(tmp_path):
    session = _recorded_session()
    provider = GugikProvider(session=session, vertical_crs="EVRF2007", resolution="1m")
    with (
        patch(MASK, return_value=ALL_LAND) as mask,
        patch.object(provider, "_download_wcs", wraps=provider._download_wcs) as wcs,
    ):
        result = run_pl_wcs_cutout(_cutout(tmp_path), provider=provider, now=NOW)

    assert [_subset(c.args[0]) for c in session.get.call_args_list] == [WINDOW]
    work = wcs.call_args.args[1]
    assert work.parent.parent.name == ".incoming"
    assert work.name.endswith(".wcs.tif")
    assert not work.exists()
    # the mask covers the raster actually written (aligned), not the raw request
    area = mask.call_args.args[0]
    assert (area.min_x, area.max_x, area.min_y, area.max_y) == WINDOW
    with rasterio.open(result.file.path) as src:
        assert (src.bounds.left, src.bounds.right) == (WINDOW[0], WINDOW[1])
        assert (src.bounds.bottom, src.bounds.top) == (WINDOW[2], WINDOW[3])
        assert src.nodata == -9999.0 and src.crs.to_epsg() == 2180
        values = src.read(1)
    np.testing.assert_array_equal(
        values, np.load(WCS_FIXTURES / "nmt_evrf2007_20x20_sheet_values.npy")
    )
    assert result.masked_pixels == 0 and result.zero_pixels == 0
    assert result.file.status == "new" and not result.all_nodata


def test_pl_cutout_default_local_without_prg_or_wcs(tmp_path):
    cut = _cutout(tmp_path)
    first_session = _recorded_session()
    with patch(MASK, return_value=ALL_LAND):
        first = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=first_session, vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )
    second_session = _recorded_session()
    with patch(MASK) as mask:
        second = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=second_session, vertical_crs="EVRF2007", resolution="1m"
            ),
        )
    assert first.file.status == "new"
    assert second.file.status == "local"
    assert second.file.unverified == "none"
    assert second.file.sha256 == first.file.sha256
    assert first_session.get.call_count == 1
    second_session.get.assert_not_called()
    mask.assert_not_called()


def test_wcs_cutout_5514_uses_pinned_warp(tmp_path):
    import kartograf.transform.raster as raster_mod

    bbox = BBox(530010, 382010, 530090, 382090, "EPSG:2180")
    cut = _cutout(tmp_path, "EPSG:5514", bbox=bbox)
    session = _synthetic_session(lambda xs, ys: 0.3 * (xs - 530000) + 100)
    with (
        patch(MASK, return_value=ALL_LAND) as mask,
        patch.object(raster_mod, "warp_to_grid", wraps=raster_mod.warp_to_grid) as warp,
    ):
        result = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )

    # the WCS area and the mask: the source envelope (warp margin) on the sheet grid
    area = mask.call_args.args[0]
    src = cut.bbox_source_2180
    assert all(v % 1 == 0.5 for v in (area.min_x, area.max_x, area.min_y, area.max_y))
    assert area.min_x <= src.min_x and area.max_x >= src.max_x
    assert area.min_y <= src.min_y and area.max_y >= src.max_y
    x0, x1, y0, y1 = _subset(session.get.call_args.args[0])
    assert all(v % 1 == 0.5 for v in (x0, x1, y0, y1))
    assert x0 <= src.min_x and x1 >= src.max_x and y0 <= src.min_y and y1 >= src.max_y
    args, kwargs = warp.call_args
    assert args[2:5] == (cut.bbox_target, 1.0, cut.pinned)
    assert kwargs == {"src_crs": "EPSG:2180", "nodata": -9999.0}
    meta = _meta(result.file.path)
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert meta["transform"]["horizontal"].startswith("pinned: ")
    with rasterio.open(result.file.path) as out:
        assert out.crs.to_epsg() == 5514


def test_pl_cutout_undated_link_and_version(tmp_path):
    with patch(MASK, return_value=ALL_LAND):
        nmt = run_pl_wcs_cutout(
            _cutout(tmp_path),
            provider=GugikProvider(
                session=_recorded_session(), vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )
        nmpt = run_pl_wcs_cutout(
            _cutout(
                tmp_path,
                product="nmpt",
                vertical_crs="KRON86",
                bbox=BBox(479013.9, 451886.5, 479033.2, 451906.1, "EPSG:2180"),
            ),
            provider=GugikNmptProvider(
                session=_recorded_session("nmpt_kron86_20x20_sf05"),
                vertical_crs="KRON86",
            ),
            now=NOW,
        )

    for result, product, vertical in (
        (nmt, "nmt", "evrf2007"),
        (nmpt, "nmpt", "kron86"),
    ):
        file = result.file
        assert file.status == "new"
        rel = file.path.relative_to(tmp_path)
        assert rel.parts[:3] == (product, f"pl_1992_1m_{vertical}", "bbox")
        assert file.path.name == file.version_path.name
        assert file.version_path.parent.name == f"2026-10-11_{file.sha256[:8]}"
        assert file.version_path.parent.parent.name == "bbox"
        assert file.version_path.parent.parent.parent.name == "versions"
        assert file.path.samefile(file.version_path)
        assert _meta(file.version_path)["sha256"] == file.sha256
        assert _meta(file.version_path)["extra"]["version"] == {
            "label": "2026-10-11",
            "label_source": "downloaded",
        }
        assert _meta(file.path)["extra"]["link"] == "hardlink"
    with rasterio.open(nmpt.file.path) as src:
        values = src.read(1)
    np.testing.assert_array_equal(
        values, np.load(WCS_FIXTURES / "nmpt_kron86_20x20_sf05_sheet_values.npy")
    )
    assert _meta(nmpt.file.version_path)["extra"]["source"]["coverage"] == (
        "DSM_PL-KRON86-NH"
    )


def test_pl_cutout_force_same_content_unchanged(tmp_path):
    cut = _cutout(tmp_path)

    def provider(session):
        return GugikProvider(session=session, vertical_crs="EVRF2007", resolution="1m")

    with patch(MASK, return_value=ALL_LAND):
        first = run_pl_wcs_cutout(cut, provider=provider(_recorded_session()), now=NOW)
        original_sidecar = _meta(first.file.version_path)
        session = _recorded_session()
        second = run_pl_wcs_cutout(
            cut, provider=provider(session), update="force", now=NOW
        )
    assert session.get.call_count == 1
    assert second.file.status == "unchanged"
    assert second.file.version_path == first.file.version_path
    assert second.file.path.samefile(first.file.version_path)
    assert _meta(second.file.version_path) == original_sidecar
    assert list(
        first.file.version_path.parent.parent.glob(f"*/{cut.target_path.name}")
    ) == [first.file.version_path]


def test_pl_cutout_force_new_content_new_version_link_moves(tmp_path):
    cut = _cutout(tmp_path)
    with patch(MASK, return_value=ALL_LAND):
        first = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=_synthetic_session(lambda x, y: 1.0),
                vertical_crs="EVRF2007",
                resolution="1m",
            ),
            now=NOW,
        )
        session = _synthetic_session(lambda x, y: 2.0)
        second = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ),
            update="force",
            now=NOW,
        )

    assert session.get.call_count == 1
    assert second.file.status == "new"
    assert second.file.path == first.file.path
    assert first.file.version_path.exists()
    assert first.file.version_path != second.file.version_path
    assert second.file.path.samefile(second.file.version_path)
    assert not second.file.path.samefile(first.file.version_path)
    with rasterio.open(second.file.path) as src:
        assert set(np.unique(src.read(1))) == {2.0}
    with rasterio.open(first.file.version_path) as src:
        assert set(np.unique(src.read(1))) == {1.0}


def test_pl_cutout_failure_keeps_previous_version_and_link(tmp_path):
    cut = _cutout(tmp_path)
    with patch(MASK, return_value=ALL_LAND):
        first = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=_recorded_session(), vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )
    version_meta = _meta(first.file.version_path)
    link_meta = _meta(first.file.path)
    failing = Mock(spec=requests.Session)
    failing.get = Mock(
        return_value=recorded_response(WCS_FIXTURES / "exception_report.xml")
    )
    with patch(MASK, return_value=ALL_LAND), pytest.raises(DownloadError):
        run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=failing, vertical_crs="EVRF2007", resolution="1m"
            ),
            update="force",
            now=NOW,
        )

    assert _meta(first.file.version_path) == version_meta
    assert _meta(first.file.path) == link_meta
    assert first.file.path.samefile(first.file.version_path)
    assert list(
        first.file.version_path.parent.parent.glob(f"*/{cut.target_path.name}")
    ) == [first.file.version_path]
    assert not (first.file.version_path.parents[2] / ".incoming").exists()


def test_pl_cutout_dated_files_ignored(tmp_path):
    cut = _cutout(tmp_path)
    legacy = cut.target_path.with_name(f"{cut.target_path.stem}_20261011.tif")
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"legacy cutout")
    with patch(MASK, return_value=ALL_LAND):
        result = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=_recorded_session(), vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )
    assert result.file.status == "new"
    assert result.file.path == cut.target_path
    assert result.file.path != legacy
    assert legacy.read_bytes() == b"legacy cutout"
    assert not legacy.samefile(result.file.path)


def test_check_pl_cutout_never_downloads(tmp_path):
    cut = _cutout(tmp_path)
    with (
        patch(MASK) as mask,
        patch("kartograf.providers.pl.create_nmt_provider") as factory,
    ):
        missing = check_pl_cutout(cut)
    assert missing.items[0].track == "pl_cutout"
    assert missing.items[0].unit == cut.target_path.stem
    assert missing.items[0].status == "missing"
    assert missing.items[0].available_signal is None
    assert UpdatePlan.from_json(missing.to_json()).items == missing.items
    mask.assert_not_called()
    factory.assert_not_called()
    with patch(MASK, return_value=ALL_LAND):
        run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=_recorded_session(), vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )
    with (
        patch(MASK) as mask,
        patch("kartograf.providers.pl.create_nmt_provider") as factory,
    ):
        local = check_pl_cutout(cut)
    assert local.items[0].status == "unverifiable"
    assert local.items[0].local_sha256
    mask.assert_not_called()
    factory.assert_not_called()


def test_pl_cutout_plan_skips_missing_or_stale_without_fetch(tmp_path):
    cut = _cutout(tmp_path)
    missing = check_pl_cutout(cut)
    session = _recorded_session()
    provider = GugikProvider(session=session, vertical_crs="EVRF2007", resolution="1m")
    with patch(MASK) as mask:
        removed = run_pl_wcs_cutout(
            cut, provider=provider, update="upgrade", plan=replace(missing, items=())
        )
        stale = run_pl_wcs_cutout(
            cut,
            provider=provider,
            update="upgrade",
            plan=replace(
                missing,
                items=(replace(missing.items[0], available_label="different"),),
            ),
        )
    assert removed.file is None and removed.stale == ()
    assert stale.file is None and stale.stale == (
        replace(missing.items[0], available_label="different"),
    )
    mask.assert_not_called()
    session.get.assert_not_called()
    with patch(MASK, return_value=ALL_LAND):
        fetched = run_pl_wcs_cutout(
            cut, provider=provider, update="upgrade", plan=missing, now=NOW
        )
    assert fetched.file.status == "new"
    with patch(MASK) as mask:
        local = run_pl_wcs_cutout(
            cut, provider=provider, update="upgrade", plan=missing
        )
    assert local.file.status == "local" and local.stale == ()
    assert local.file.unverified is None
    mask.assert_not_called()
    assert session.get.call_count == 1


def test_disk_space_checked_only_when_fetching(tmp_path):
    cut = _cutout(tmp_path)
    provider = GugikProvider(
        session=_recorded_session(), vertical_crs="EVRF2007", resolution="1m"
    )
    with (
        patch(MASK, return_value=ALL_LAND),
        patch("kartograf.download.cutout._check_wcs_disk_space") as disk,
    ):
        first = run_pl_wcs_cutout(cut, provider=provider, now=NOW)
    assert disk.call_count == 1
    staged = disk.call_args.args[1]
    assert staged.parent.parent.name == ".incoming"
    assert staged.name == cut.target_path.name
    later_session = _recorded_session()
    later_provider = GugikProvider(
        session=later_session, vertical_crs="EVRF2007", resolution="1m"
    )
    with (
        patch(MASK) as mask,
        patch(
            "kartograf.download.cutout._check_wcs_disk_space",
            side_effect=ValidationError("disk full"),
        ) as disk,
    ):
        for update in (None, "upgrade"):
            reused = run_pl_wcs_cutout(cut, provider=later_provider, update=update)
            assert reused.file.status == "local"
        with pytest.raises(ValidationError, match="disk full"):
            run_pl_wcs_cutout(cut, provider=later_provider, update="force")
    assert disk.call_count == 1
    mask.assert_not_called()
    later_session.get.assert_not_called()
    assert first.file.path.samefile(first.file.version_path)


def test_prg_failure_makes_no_wcs_request(tmp_path):
    session = _recorded_session()
    with (
        patch(MASK, side_effect=DownloadError("PRG WFS: blad uslugi")),
        pytest.raises(DownloadError, match="PRG"),
    ):
        run_pl_wcs_cutout(
            _cutout(tmp_path),
            provider=GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )

    session.get.assert_not_called()
    assert not (tmp_path / "nmt").exists()


def test_mask_counts_and_sidecar(tmp_path):
    # land = western half of the 20 x 20 window; on land 5 zero columns
    land = LandMask((_square(500000, 200000, 567590.5, 300000),), ())
    session = _synthetic_session(lambda xs, ys: np.where(xs < 567585.5, 0.0, 7.0))
    with patch(MASK, return_value=land):
        result = run_pl_wcs_cutout(
            _cutout(tmp_path),
            provider=GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ),
            parent_request={"bbox": [1, 2, 3, 4]},
            now=NOW,
        )

    assert (result.masked_pixels, result.zero_pixels) == (200, 100)
    with rasterio.open(result.file.path) as src:
        values = src.read(1)
    assert (values[:, 10:] == -9999.0).all()
    assert (values[:, :5] == 0.0).all() and (values[:, 5:10] == 7.0).all()
    meta = _meta(result.file.path)
    # capability="bbox_raster" selects the WCS channel: EVRF2007 resolved by it
    assert meta["dataset"] == "pl.gugik.nmt_1m"
    assert meta["vertical_crs"] == "EPSG:9651"
    assert meta["nodata"] == -9999.0
    assert meta["sha256"] == result.file.sha256
    assert meta["size_bytes"] == result.file.version_path.stat().st_size
    extra = meta["extra"]
    assert extra["source"] == {
        "service": "WCS",
        "endpoint": GugikProvider.WCS_ENDPOINTS["EVRF2007"],
        "coverage": "DTM_PL-EVRF2007-NH",
        "format": "image/x-aaigrid",
        "composition": "server",
    }
    assert extra["mask"] == {
        "source": "PRG",
        "layers": [
            "A00_Granice_panstwa",
            "-W02_Morze_terytorialne_RP",
            "-W03_Morskie_wody_wewnetrzne",
        ],
        "masked_pixels": 200,
    }
    assert extra["zero_pixels"] == 100
    assert extra["parent_request"] == {"bbox": [1, 2, 3, 4]}
    assert extra["version"] == {
        "label": "2026-10-11",
        "label_source": "downloaded",
    }
    assert "http" not in extra
    for key in ("sheet_sources", "missing_sheets", "all_nodata"):
        assert key not in extra


def test_pl_cutout_local_result_fields_from_sidecar(tmp_path):
    cut = _cutout(tmp_path)
    land = LandMask((_square(500000, 200000, 567590.5, 300000),), ())
    session = _synthetic_session(lambda xs, ys: np.where(xs < 567585.5, 0.0, 7.0))
    with patch(MASK, return_value=land):
        fetched = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )
    next_session = _recorded_session()
    with (
        patch(MASK) as mask,
        patch("kartograf.transport.mosaic.has_valid_pixels") as scan,
    ):
        local = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(
                session=next_session, vertical_crs="EVRF2007", resolution="1m"
            ),
            update="upgrade",
        )
    assert fetched.file.status == "new" and local.file.status == "local"
    assert (local.all_nodata, local.masked_pixels, local.zero_pixels) == (
        False,
        200,
        100,
    )
    mask.assert_not_called()
    scan.assert_not_called()
    next_session.get.assert_not_called()


def test_zero_pixels_absent_from_sidecar_when_none(tmp_path):
    with patch(MASK, return_value=ALL_LAND):
        result = run_pl_wcs_cutout(
            _cutout(tmp_path),
            provider=GugikProvider(
                session=_recorded_session(), vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )
    extra = _meta(result.file.path)["extra"]
    assert "zero_pixels" not in extra and extra["mask"]["masked_pixels"] == 0


def test_all_outside_land_is_all_nodata(tmp_path):
    abroad = LandMask((_square(0, 0, 10, 10),), ())
    with patch(MASK, return_value=abroad):
        result = run_pl_wcs_cutout(
            _cutout(tmp_path),
            provider=GugikProvider(
                session=_recorded_session(), vertical_crs="EVRF2007", resolution="1m"
            ),
            now=NOW,
        )

    assert result.all_nodata and result.file.path.exists()
    assert result.masked_pixels == 400
    assert _meta(result.file.path)["extra"]["all_nodata"] is True
    with patch(MASK) as mask:
        local = run_pl_wcs_cutout(_cutout(tmp_path), update="upgrade")
    assert local.file.status == "local"
    assert local.all_nodata and local.masked_pixels == 400
    mask.assert_not_called()


def test_download_pl_cutout_writes_parent_request(tmp_path):
    session = _recorded_session()
    with (
        patch(
            "kartograf.providers.pl.create_nmt_provider",
            return_value=GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ),
        ),
        patch(MASK, return_value=ALL_LAND),
    ):
        result = download_pl_cutout(
            BBOX,
            "EPSG:2180",
            output_dir=tmp_path,
            parent_request={"p": 1},
            vertical_crs="EVRF2007",
            product="nmt",
        )

    assert result.file.path == _cutout(tmp_path).target_path
    assert _meta(result.file.path)["extra"]["parent_request"] == {"p": 1}
    assert session.get.call_count == 1


@pytest.mark.parametrize(
    ("cutout_kwargs", "provider"),
    [
        (
            {"product": "nmpt"},
            lambda s: GugikProvider(
                session=s, vertical_crs="EVRF2007", resolution="1m"
            ),
        ),
        (
            {"product": "nmt"},
            lambda s: GugikNmptProvider(session=s, vertical_crs="EVRF2007"),
        ),
        (
            {"vertical_crs": "EVRF2007"},
            lambda s: GugikProvider(session=s, vertical_crs="KRON86", resolution="1m"),
        ),
    ],
)
def test_provider_mismatch_rejected(tmp_path, cutout_kwargs, provider):
    session = _recorded_session()
    with patch(MASK) as mask, pytest.raises(ValidationError, match="niezgodny"):
        run_pl_wcs_cutout(
            _cutout(tmp_path, **cutout_kwargs), provider=provider(session), now=NOW
        )
    mask.assert_not_called()
    session.get.assert_not_called()


def test_prepare_rejects_unknown_product(tmp_path):
    with pytest.raises(ValidationError, match="orto"):
        _cutout(tmp_path, product="orto")


class TestCli:
    """``download --bbox/--geometry --target-crs`` for PL goes through WCS."""

    _FACTORY = "kartograf.cli.download_cmd._create_provider_and_storage"
    _BBOX_ARGS = ["--bbox", "567580.6,243664.7,567600.4,243684.3", "--country", "pl"]

    def _main(self, tmp_path, provider, *extra, mask=ALL_LAND):
        with (
            patch(self._FACTORY, return_value=(provider, Mock())) as factory,
            patch(MASK, return_value=mask) as fetch_mask,
        ):
            rc = main(
                [
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    *self._BBOX_ARGS,
                    "--target-crs",
                    "EPSG:2180",
                    *extra,
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )
        self.factory, self.fetch_mask = factory, fetch_mask
        return rc

    def test_cli_nmpt_target_crs_allowed(self, tmp_path, capsys):
        session = _recorded_session("nmpt_evrf2007_20x20_sf05")
        rc = self._main(
            tmp_path,
            GugikNmptProvider(session=session, vertical_crs="EVRF2007"),
            "--product",
            "nmpt",
        )

        assert rc == 0, capsys.readouterr().err
        (tif,) = (tmp_path / "nmpt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        assert tif.name == "567580.6_243664.7_567600.4_243684.3.tif"
        with rasterio.open(tif) as src:
            values = src.read(1)
        np.testing.assert_array_equal(
            values, np.load(WCS_FIXTURES / "nmpt_evrf2007_20x20_sf05_sheet_values.npy")
        )
        assert capsys.readouterr().err == ""

    def test_cli_5m_target_crs_rejected_before_network(self, tmp_path, capsys):
        session = _recorded_session()
        rc = self._main(
            tmp_path,
            GugikProvider(session=session, vertical_crs="EVRF2007", resolution="1m"),
            "--resolution",
            "5m",
        )

        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error:") and "--target-crs" in err and "1m" in err
        self.factory.assert_not_called()
        self.fetch_mask.assert_not_called()
        session.get.assert_not_called()
        assert not (tmp_path / "nmt").exists()

    @pytest.mark.parametrize("product", ["orto", "laz"])
    def test_cli_orto_laz_target_crs_still_rejected(self, tmp_path, capsys, product):
        rc = self._main(tmp_path, Mock(), "--product", product)

        assert rc == 1
        assert capsys.readouterr().err.startswith("Error:")
        self.factory.assert_not_called()

    def test_cli_default_uses_local_and_force_refetches(self, tmp_path, capsys):
        first = _recorded_session()
        assert (
            self._main(
                tmp_path,
                GugikProvider(session=first, vertical_crs="EVRF2007", resolution="1m"),
            )
            == 0
        )
        plain = capsys.readouterr()
        second = _recorded_session()
        assert (
            self._main(
                tmp_path,
                GugikProvider(session=second, vertical_crs="EVRF2007", resolution="1m"),
            )
            == 0
        )
        reused = capsys.readouterr()
        third = _recorded_session()
        assert (
            self._main(
                tmp_path,
                GugikProvider(session=third, vertical_crs="EVRF2007", resolution="1m"),
                "--force",
            )
            == 0
        )
        forced = capsys.readouterr()

        assert first.get.call_count == third.get.call_count == 1
        second.get.assert_not_called()
        assert (
            (forced.out, forced.err)
            == (plain.out, plain.err)
            == (
                reused.out,
                reused.err,
            )
            == ("", "")
        )

    def test_cli_wcs_error_code_1_no_traceback(self, tmp_path, capsys):
        failing = Mock(spec=requests.Session)
        failing.get = Mock(
            return_value=recorded_response(WCS_FIXTURES / "exception_report.xml")
        )
        rc = self._main(
            tmp_path,
            GugikProvider(session=failing, vertical_crs="EVRF2007", resolution="1m"),
        )

        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error:") and "Traceback" not in err
        assert not (tmp_path / "nmt").exists()

    def test_cli_prg_error_code_1(self, tmp_path, capsys):
        session = _recorded_session()
        with (
            patch(
                self._FACTORY,
                return_value=(
                    GugikProvider(
                        session=session, vertical_crs="EVRF2007", resolution="1m"
                    ),
                    Mock(),
                ),
            ),
            patch(MASK, side_effect=DownloadError("PRG WFS: blad uslugi")),
        ):
            rc = main(
                [
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    *self._BBOX_ARGS,
                    "--target-crs",
                    "EPSG:2180",
                ]
                + ["-o", str(tmp_path), "-q"]
            )

        assert rc == 1
        assert "PRG" in capsys.readouterr().err
        session.get.assert_not_called()

    def test_cli_all_nodata_warning_code_0(self, tmp_path, capsys):
        abroad = LandMask((_square(0, 0, 10, 10),), ())
        rc = self._main(
            tmp_path,
            GugikProvider(
                session=_recorded_session(), vertical_crs="EVRF2007", resolution="1m"
            ),
            mask=abroad,
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert err.startswith("Warning:") and "nodata" in err
        assert len(list((tmp_path / "nmt").rglob("bbox/*.tif"))) == 1

    def test_cli_no_zero_pixels_info(self, tmp_path, capsys):
        session = _synthetic_session(lambda xs, ys: np.zeros_like(xs + ys))
        rc = self._main(
            tmp_path,
            GugikProvider(session=session, vertical_crs="EVRF2007", resolution="1m"),
        )

        assert rc == 0
        assert "Info:" not in capsys.readouterr().err
        (tif,) = (tmp_path / "nmt").rglob("bbox/*.tif")
        assert _meta(tif)["extra"]["zero_pixels"] == 400

    def test_cli_chunk_count_info(self, tmp_path, capsys):
        from kartograf.transport.chunks import ChunkLimits

        session = _recorded_session()
        with patch.object(
            GugikProvider, "WCS_CHUNK_LIMITS_AAIGRID", ChunkLimits(10, 10, 100)
        ):
            rc = self._main(
                tmp_path,
                GugikProvider(
                    session=session, vertical_crs="EVRF2007", resolution="1m"
                ),
            )

        assert rc == 0
        err = capsys.readouterr().err
        assert err.startswith("Info:") and "4 zapytan WCS" in err
        assert session.get.call_count == 4
        (tif,) = (tmp_path / "nmt").rglob("bbox/*.tif")
        with rasterio.open(tif) as src:
            values = src.read(1)
        np.testing.assert_array_equal(
            values, np.load(WCS_FIXTURES / "nmt_evrf2007_20x20_sheet_values.npy")
        )

    def test_cli_geometry_target_crs_uses_envelope(self, tmp_path):
        """``--geometry`` + ``--target-crs``: the WCS area is the envelope of the
        geometry (on the sheet grid) and the dispatch layer's parent reaches
        the sidecar."""
        from pyproj import CRS

        geom = write_gpkg_layers(tmp_path / "area.gpkg", ["area"])
        session = _recorded_session()
        with (
            patch(
                "kartograf.core.geometry.read_source_crs",
                return_value=CRS.from_epsg(2180),
            ),
            patch("kartograf.core.geometry.get_overall_bbox", return_value=BBOX),
            patch(
                self._FACTORY,
                return_value=(
                    GugikProvider(
                        session=session, vertical_crs="EVRF2007", resolution="1m"
                    ),
                    Mock(),
                ),
            ),
            patch(MASK, return_value=ALL_LAND),
        ):
            rc = main(
                [
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--system",
                    "1992",
                    "--geometry",
                    str(geom),
                    "--country",
                    "pl",
                ]
                + ["--target-crs", "EPSG:2180", "-o", str(tmp_path), "-q"]
            )

        assert rc == 0
        assert [_subset(c.args[0]) for c in session.get.call_args_list] == [WINDOW]
        (tif,) = (tmp_path / "nmt").rglob("bbox/*.tif")
        assert _meta(tif)["extra"]["parent_request"]["countries"] == ["PL"]

    def _cz_provider(self, *, fail=False):
        """CuzkDmrProvider stub: writes a file and pretends to be a pinned operation."""
        provider = Mock()
        provider.descriptor_key = "cz.cuzk.dmr5g"
        provider.resolution = "2m"
        provider.vertical_crs = "EVRF2007"
        provider.vertical_transform = None

        def fake_horizontal(target_crs):
            pinned = Mock()
            pinned.description = f"S-JTSK to ETRS89 (1) -> {target_crs}"
            pinned.accuracy_m = 1.0
            return pinned

        provider.horizontal_transform.side_effect = fake_horizontal

        def fake_bbox(bbox, target, **kw):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"II*\x00dane")
            return target

        provider.download_bbox.side_effect = fake_bbox
        return provider

    def _border(self, tmp_path, pl_session):
        """``--country auto`` over a small PL+CZ rectangle (18.80E, 49.70N)."""
        with (
            patch(
                "kartograf.providers.cuzk.create_dmr_provider",
                return_value=self._cz_provider(),
            ),
            patch(
                self._FACTORY,
                return_value=(
                    GugikProvider(
                        session=pl_session, vertical_crs="EVRF2007", resolution="1m"
                    ),
                    Mock(),
                ),
            ),
            patch(MASK, return_value=ALL_LAND),
        ):
            return main(
                [
                    "download",
                    "--product",
                    "nmt",
                    "-o",
                    "./data",
                    "--country",
                    "auto",
                    "--resolution",
                    "pl=1m,cz=2m",
                    "--vertical-crs",
                    "pl=EVRF2007,cz=Bpv",
                    "--system",
                    "1992",
                    "--bbox",
                    "18.80,49.70,18.801,49.7005",
                ]
                + ["--bbox-crs", "EPSG:4326", "--target-crs", "EPSG:2180"]
                + ["--vertical-crs", "EVRF2007", "-o", str(tmp_path), "-q"]
            )

    def test_cli_auto_two_cutouts_shared_parent(self, tmp_path):
        rc = self._border(tmp_path, _synthetic_session(lambda xs, ys: xs * 0 + 300))

        assert rc == 0
        pl = list((tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif"))
        cz = [
            p for p in (tmp_path / "nmt").rglob("bbox/*.tif") if "pl_1992" not in str(p)
        ]
        assert len(pl) == 1 and len(cz) == 1
        parents = [_meta(p)["extra"]["parent_request"] for p in (*pl, *cz)]
        assert parents[0] == parents[1]
        assert parents[0]["countries"] == ["CZ", "PL"]
        assert all(_meta(p)["horizontal_crs"] == "EPSG:2180" for p in (*pl, *cz))

    def test_cli_auto_pl_wcs_error_with_cz_success_is_warning(self, tmp_path, capsys):
        failing = Mock(spec=requests.Session)
        failing.get = Mock(
            return_value=recorded_response(WCS_FIXTURES / "exception_report.xml")
        )
        rc = self._border(tmp_path, failing)

        assert rc == 0
        assert "Warning:" in capsys.readouterr().err
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007").exists()
