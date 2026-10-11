"""PL cutout from GUGiK WCS (ADR-035): library and CLI on recorded WCS responses."""

import json
import re
import warnings
from datetime import date
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
    PlCutoutSheets,
    download_pl_cutout,
    prepare_pl_cutout,
    run_pl_cutout,
    run_pl_wcs_cutout,
)
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

DAY = date(2026, 10, 11)
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
    return prepare_pl_cutout(bbox, target_crs, output_dir=tmp_path, **kwargs)


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(f"{path.name}.meta.json").read_text("utf-8"))


def test_wcs_cutout_2180_corner_on_sheet_grid(tmp_path):
    session = _recorded_session()
    with patch(MASK, return_value=ALL_LAND) as mask:
        result = run_pl_wcs_cutout(
            _cutout(tmp_path), provider=GugikProvider(session=session), today=DAY
        )

    assert [_subset(c.args[0]) for c in session.get.call_args_list] == [WINDOW]
    # the mask covers the raster actually written (aligned), not the raw request
    area = mask.call_args.args[0]
    assert (area.min_x, area.max_x, area.min_y, area.max_y) == WINDOW
    with rasterio.open(result.path) as src:
        assert (src.bounds.left, src.bounds.right) == (WINDOW[0], WINDOW[1])
        assert (src.bounds.bottom, src.bounds.top) == (WINDOW[2], WINDOW[3])
        assert src.nodata == -9999.0 and src.crs.to_epsg() == 2180
        values = src.read(1)
    np.testing.assert_array_equal(
        values, np.load(WCS_FIXTURES / "nmt_evrf2007_20x20_sheet_values.npy")
    )
    assert result.masked_pixels == 0 and result.zero_pixels == 0
    assert not result.skipped and not result.all_nodata


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
            cut, provider=GugikProvider(session=session), today=DAY
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
    meta = _meta(result.path)
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert meta["transform"]["horizontal"].startswith("pinned: ")
    with rasterio.open(result.path) as out:
        assert out.crs.to_epsg() == 5514


def test_name_carries_download_date(tmp_path):
    with patch(MASK, return_value=ALL_LAND):
        nmt = run_pl_wcs_cutout(
            _cutout(tmp_path),
            provider=GugikProvider(session=_recorded_session()),
            today=DAY,
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
            today=DAY,
        )

    rel = nmt.path.relative_to(tmp_path)
    assert rel.parts[:3] == ("nmt", "pl_1992_1m_evrf2007", "bbox")
    assert rel.name.endswith("_20261011.tif")
    assert nmpt.path.relative_to(tmp_path).parts[:3] == (
        "nmpt",
        "pl_1992_1m_kron86",
        "bbox",
    )
    assert nmpt.path.name.endswith("_20261011.tif")
    with rasterio.open(nmpt.path) as src:
        values = src.read(1)
    np.testing.assert_array_equal(
        values, np.load(WCS_FIXTURES / "nmpt_kron86_20x20_sf05_sheet_values.npy")
    )
    assert _meta(nmpt.path)["extra"]["source"]["coverage"] == "DSM_PL-KRON86-NH"


def test_every_run_downloads(tmp_path):
    cut = _cutout(tmp_path)
    with patch(MASK, return_value=ALL_LAND):
        first = run_pl_wcs_cutout(
            cut,
            provider=GugikProvider(session=_synthetic_session(lambda x, y: 1.0)),
            today=DAY,
        )
        session = _synthetic_session(lambda x, y: 2.0)
        second = run_pl_wcs_cutout(
            cut, provider=GugikProvider(session=session), today=DAY
        )

    assert session.get.call_count == 1
    assert second.path == first.path and not second.skipped
    with rasterio.open(second.path) as src:
        assert set(np.unique(src.read(1))) == {2.0}
    assert sorted(p.name for p in second.path.parent.iterdir()) == sorted(
        [second.path.name, f"{second.path.name}.meta.json"]
    )


def test_failed_rerun_keeps_previous_same_day_file(tmp_path):
    cut = _cutout(tmp_path)
    with patch(MASK, return_value=ALL_LAND):
        first = run_pl_wcs_cutout(
            cut, provider=GugikProvider(session=_recorded_session()), today=DAY
        )
    sidecar = first.path.with_name(f"{first.path.name}.meta.json")
    before = (first.path.read_bytes(), sidecar.read_bytes())

    failing = Mock(spec=requests.Session)
    failing.get = Mock(
        return_value=recorded_response(WCS_FIXTURES / "exception_report.xml")
    )
    with patch(MASK, return_value=ALL_LAND), pytest.raises(DownloadError):
        run_pl_wcs_cutout(cut, provider=GugikProvider(session=failing), today=DAY)

    assert (first.path.read_bytes(), sidecar.read_bytes()) == before
    assert sorted(p.name for p in first.path.parent.iterdir()) == sorted(
        [first.path.name, sidecar.name]
    )


def test_prg_failure_makes_no_wcs_request(tmp_path):
    session = _recorded_session()
    with (
        patch(MASK, side_effect=DownloadError("PRG WFS: blad uslugi")),
        pytest.raises(DownloadError, match="PRG"),
    ):
        run_pl_wcs_cutout(
            _cutout(tmp_path), provider=GugikProvider(session=session), today=DAY
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
            provider=GugikProvider(session=session),
            parent_request={"bbox": [1, 2, 3, 4]},
            today=DAY,
        )

    assert (result.masked_pixels, result.zero_pixels) == (200, 100)
    with rasterio.open(result.path) as src:
        values = src.read(1)
    assert (values[:, 10:] == -9999.0).all()
    assert (values[:, :5] == 0.0).all() and (values[:, 5:10] == 7.0).all()
    meta = _meta(result.path)
    # capability="bbox_raster" selects the WCS channel: EVRF2007 resolved by it
    assert meta["dataset"] == "pl.gugik.nmt_1m"
    assert meta["vertical_crs"] == "EPSG:9651"
    assert meta["nodata"] == -9999.0
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
    for key in ("sheet_sources", "missing_sheets", "all_nodata"):
        assert key not in extra


def test_zero_pixels_absent_from_sidecar_when_none(tmp_path):
    with patch(MASK, return_value=ALL_LAND):
        result = run_pl_wcs_cutout(
            _cutout(tmp_path),
            provider=GugikProvider(session=_recorded_session()),
            today=DAY,
        )
    extra = _meta(result.path)["extra"]
    assert "zero_pixels" not in extra and extra["mask"]["masked_pixels"] == 0


def test_all_outside_land_is_all_nodata(tmp_path):
    abroad = LandMask((_square(0, 0, 10, 10),), ())
    with patch(MASK, return_value=abroad):
        result = run_pl_wcs_cutout(
            _cutout(tmp_path),
            provider=GugikProvider(session=_recorded_session()),
            today=DAY,
        )

    assert result.all_nodata and result.path.exists()
    assert result.masked_pixels == 400
    assert _meta(result.path)["extra"]["all_nodata"] is True


def test_5m_rejected_before_network(tmp_path):
    session = _recorded_session()
    cut = _cutout(tmp_path, resolution="5m")
    with patch(MASK) as mask:
        with pytest.raises(ValidationError, match="run_pl_cutout"):
            run_pl_wcs_cutout(cut, provider=GugikProvider(session=session), today=DAY)
        with pytest.raises(ValidationError, match="1m"):
            download_pl_cutout(BBOX, "EPSG:2180", output_dir=tmp_path, resolution="5m")

    mask.assert_not_called()
    session.get.assert_not_called()
    assert not (tmp_path / "nmt").exists()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("geometry", "area.gpkg"),
        ("layer", "dzialki"),
        ("scale", "1:5000"),
        ("max_workers", 4),
        ("force", True),
        ("on_progress", print),
        ("cache", object()),
    ],
)
def test_download_pl_cutout_sheet_params_warn(tmp_path, name, value):
    with (
        patch("kartograf.download.cutout.run_pl_wcs_cutout") as run,
        pytest.warns(DeprecationWarning, match=name),
    ):
        download_pl_cutout(BBOX, "EPSG:2180", output_dir=tmp_path, **{name: value})
    run.assert_called_once()


def test_download_pl_cutout_defaults_do_not_warn(tmp_path):
    session = _recorded_session()
    with (
        patch(
            "kartograf.providers.pl.create_nmt_provider",
            return_value=GugikProvider(session=session),
        ),
        patch(MASK, return_value=ALL_LAND),
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("error", DeprecationWarning)
        result = download_pl_cutout(
            BBOX, "EPSG:2180", output_dir=tmp_path, parent_request={"p": 1}
        )

    assert result.path.name.endswith(f"_{date.today():%Y%m%d}.tif")
    assert _meta(result.path)["extra"]["parent_request"] == {"p": 1}
    assert session.get.call_count == 1


def test_run_pl_cutout_rejects_nmpt(tmp_path):
    cut = _cutout(tmp_path, product="nmpt")
    with pytest.raises(ValidationError, match="run_pl_wcs_cutout"):
        run_pl_cutout(cut, PlCutoutSheets(godla=("N-34-130-D-d-2-3",)))
    assert not (tmp_path / "nmpt").exists()


@pytest.mark.parametrize(
    ("cutout_kwargs", "provider"),
    [
        ({"product": "nmpt"}, lambda s: GugikProvider(session=s)),
        ({"product": "nmt"}, lambda s: GugikNmptProvider(session=s)),
        (
            {"vertical_crs": "EVRF2007"},
            lambda s: GugikProvider(session=s, vertical_crs="KRON86"),
        ),
    ],
)
def test_provider_mismatch_rejected(tmp_path, cutout_kwargs, provider):
    session = _recorded_session()
    with patch(MASK) as mask, pytest.raises(ValidationError, match="niezgodny"):
        run_pl_wcs_cutout(
            _cutout(tmp_path, **cutout_kwargs), provider=provider(session), today=DAY
        )
    mask.assert_not_called()
    session.get.assert_not_called()


def test_prepare_rejects_unknown_product_and_nmpt_5m(tmp_path):
    with pytest.raises(ValidationError, match="orto"):
        _cutout(tmp_path, product="orto")
    with pytest.raises(ValidationError, match="NMPT"):
        _cutout(tmp_path, product="nmpt", resolution="5m")


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
            tmp_path, GugikNmptProvider(session=session), "--product", "nmpt"
        )

        assert rc == 0, capsys.readouterr().err
        (tif,) = (tmp_path / "nmpt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        assert tif.name.endswith(f"_{date.today():%Y%m%d}.tif")
        with rasterio.open(tif) as src:
            values = src.read(1)
        np.testing.assert_array_equal(
            values, np.load(WCS_FIXTURES / "nmpt_evrf2007_20x20_sf05_sheet_values.npy")
        )
        assert capsys.readouterr().err == ""

    def test_cli_5m_target_crs_rejected_before_network(self, tmp_path, capsys):
        session = _recorded_session()
        rc = self._main(tmp_path, GugikProvider(session=session), "--resolution", "5m")

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

    def test_cli_force_has_no_effect_and_no_message(self, tmp_path, capsys):
        first = _recorded_session()
        assert self._main(tmp_path, GugikProvider(session=first)) == 0
        plain = capsys.readouterr()
        second = _recorded_session()
        assert self._main(tmp_path, GugikProvider(session=second), "--force") == 0
        forced = capsys.readouterr()

        # every run downloads; --force changes neither the work nor the messages
        assert first.get.call_count == second.get.call_count == 1
        assert (forced.out, forced.err) == (plain.out, plain.err) == ("", "")

    def test_cli_wcs_error_code_1_no_traceback(self, tmp_path, capsys):
        failing = Mock(spec=requests.Session)
        failing.get = Mock(
            return_value=recorded_response(WCS_FIXTURES / "exception_report.xml")
        )
        rc = self._main(tmp_path, GugikProvider(session=failing))

        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error:") and "Traceback" not in err
        assert not (tmp_path / "nmt").exists()

    def test_cli_prg_error_code_1(self, tmp_path, capsys):
        session = _recorded_session()
        with (
            patch(self._FACTORY, return_value=(GugikProvider(session=session), Mock())),
            patch(MASK, side_effect=DownloadError("PRG WFS: blad uslugi")),
        ):
            rc = main(
                ["download", *self._BBOX_ARGS, "--target-crs", "EPSG:2180"]
                + ["-o", str(tmp_path), "-q"]
            )

        assert rc == 1
        assert "PRG" in capsys.readouterr().err
        session.get.assert_not_called()

    def test_cli_all_nodata_warning_code_0(self, tmp_path, capsys):
        abroad = LandMask((_square(0, 0, 10, 10),), ())
        rc = self._main(
            tmp_path, GugikProvider(session=_recorded_session()), mask=abroad
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert err.startswith("Warning:") and "nodata" in err
        assert len(list((tmp_path / "nmt").rglob("*.tif"))) == 1

    def test_cli_no_zero_pixels_info(self, tmp_path, capsys):
        session = _synthetic_session(lambda xs, ys: np.zeros_like(xs + ys))
        rc = self._main(tmp_path, GugikProvider(session=session))

        assert rc == 0
        assert "Info:" not in capsys.readouterr().err
        (tif,) = (tmp_path / "nmt").rglob("*.tif")
        assert _meta(tif)["extra"]["zero_pixels"] == 400

    def test_cli_chunk_count_info(self, tmp_path, capsys):
        from kartograf.transport.chunks import ChunkLimits

        session = _recorded_session()
        with patch.object(
            GugikProvider, "WCS_CHUNK_LIMITS_AAIGRID", ChunkLimits(10, 10, 100)
        ):
            rc = self._main(tmp_path, GugikProvider(session=session))

        assert rc == 0
        err = capsys.readouterr().err
        assert err.startswith("Info:") and "4 zapytan WCS" in err
        assert session.get.call_count == 4
        (tif,) = (tmp_path / "nmt").rglob("*.tif")
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
            patch(self._FACTORY, return_value=(GugikProvider(session=session), Mock())),
            patch(MASK, return_value=ALL_LAND),
        ):
            rc = main(
                ["download", "--geometry", str(geom), "--country", "pl"]
                + ["--target-crs", "EPSG:2180", "-o", str(tmp_path), "-q"]
            )

        assert rc == 0
        assert [_subset(c.args[0]) for c in session.get.call_args_list] == [WINDOW]
        (tif,) = (tmp_path / "nmt").rglob("*.tif")
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
                return_value=(GugikProvider(session=pl_session), Mock()),
            ),
            patch(MASK, return_value=ALL_LAND),
        ):
            return main(
                ["download", "--bbox", "18.80,49.70,18.801,49.7005"]
                + ["--bbox-crs", "EPSG:4326", "--target-crs", "EPSG:2180"]
                + ["--vertical-crs", "EVRF2007", "-o", str(tmp_path), "-q"]
            )

    def test_cli_auto_two_cutouts_shared_parent(self, tmp_path):
        rc = self._border(tmp_path, _synthetic_session(lambda xs, ys: xs * 0 + 300))

        assert rc == 0
        pl = list((tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif"))
        cz = [p for p in (tmp_path / "nmt").rglob("*.tif") if "pl_1992" not in str(p)]
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
