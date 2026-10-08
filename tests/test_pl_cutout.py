"""Tests of the PL --target-crs cutout (ADR-027).

Library API, content, validation, sidecar, CLI flow.
"""

import argparse
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
import rasterio

from kartograf.cli.commands import main
from kartograf.cli.download_cmd import _download_pl_bbox
from kartograf.core.sheet_parser import BBox
from kartograf.download.cutout import build_pl_cutout, prepare_pl_cutout
from kartograf.download.manager import DownloadProgress, DownloadResult
from kartograf.exceptions import DownloadError
from kartograf.transform.crs import (
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)

_NODATA = -9999.0
_APEX = (530050.0, 382050.0)  # EPSG:2180, Piotrkow Trybunalski area


@pytest.fixture(autouse=True)
def _cwd_outside_repo(tmp_path, monkeypatch):
    """The PL-path ``MetadataCache`` lands in cwd — outside the repo and output dir."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)


def _write_sheet_asc(path, west, south, size=100, pixel=1.0, apex=None, fill=100.0):
    """Synthetic AAIGrid 'sheet': a cone around the apex or a flat ``fill``."""
    cols, rows = np.meshgrid(np.arange(size), np.arange(size))
    xs = west + (cols + 0.5) * pixel
    ys = (south + size * pixel) - (rows + 0.5) * pixel
    if apex is None:
        data = np.full((size, size), fill, dtype="float32")
    else:
        data = (1000.0 - np.hypot(xs - apex[0], ys - apex[1])).astype("float32")
    header = (
        f"ncols {size}\nnrows {size}\nxllcorner {west}\nyllcorner {south}\n"
        f"cellsize {pixel}\nNODATA_value {_NODATA}\n"
    )
    body = "\n".join(" ".join(f"{v:.3f}" for v in row) for row in data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body + "\n", encoding="ascii")
    return path


def _pinned_2180_to(target_crs):
    return build_pinned_transform(
        "EPSG:2180",
        target_crs,
        TransformPolicy(
            min_accuracy_m=1.0, probe_point=_APEX, allow_network_grids=False
        ),
    )


def _write_grid_sheet(
    path,
    col0,
    cols,
    rows,
    value,
    *,
    x0=529950.5,
    y_top=382150.5,
    pixel=1.0,
    nodata_header="-9999.0",
    fmt="{:.4f}",
):
    """ASC sheet on a GUGiK-like grid: pixel corners half a pixel from whole
    numbers (fact 1 of the 2026-09-28 plan). value(xs, ys) -> values (pixel
    centres)."""
    xs = x0 + (np.arange(cols) + col0 + 0.5) * pixel
    ys = y_top - (np.arange(rows) + 0.5) * pixel
    gx, gy = np.meshgrid(xs, ys)
    data = value(gx, gy)
    header = (
        f"ncols {cols}\nnrows {rows}\nxllcorner {x0 + col0 * pixel}\n"
        f"yllcorner {y_top - rows * pixel}\ncellsize {pixel}\n"
        f"nodata_value {nodata_header}\n"
    )
    body = "\n".join(" ".join(fmt.format(v) for v in row) for row in data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body + "\n", encoding="ascii")
    return path


def _ids(gx, gy):
    """Unique value per pixel of the global grid (x0 = 529950.5, y_top = 382150.5)."""
    return 1000.0 * np.floor(382150.5 - gy) + np.floor(gx - 529950.5)


# P-01: real .prj content, not WKT1_GDAL from pyproj
_HYDROGRAF_2180_WKT = (  # .prj from the Hydrograf cache (gdalsrsinfo -o wkt_simple)
    'PROJCS["ETRF2000-PL / CS92",GEOGCS["ETRF2000-PL",DATUM["ETRF2000_Poland",'
    'SPHEROID["GRS 1980",6378137,298.257222101]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
    'PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",19],'
    'PARAMETER["scale_factor",0.9993],PARAMETER["false_easting",500000],'
    'PARAMETER["false_northing",-5300000],UNIT["metre",1]]'
)


class TestBuildPlCutout:
    """Spec 8a-c: content regression, mosaic with nodata, crop without warp."""

    def test_target_5514_content_lt_1px(self, tmp_path):
        """Mosaic of 2 sheets + warp: the apex where pyproj says it should be."""
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        west = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000, apex=_APEX)
        east = _write_sheet_asc(tmp_path / "b.asc", 530100, 382000, apex=_APEX)
        bbox_2180 = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX))
        bbox_target = bbox_to_crs(bbox_2180, "EPSG:5514")
        target = tmp_path / "out" / "cut.tif"

        build_pl_cutout([west, east], bbox_2180, bbox_target, 1.0, pinned, target)

        with rasterio.open(target) as ds:
            assert ds.crs.to_epsg() == 5514
            data = ds.read(1, masked=True)
            row, col = np.unravel_index(np.argmax(data.filled(-np.inf)), data.shape)
            gx, gy = ds.xy(int(row), int(col))
        assert abs(gx - ax) < 1.0, f"E: {gx} vs {ax}"
        assert abs(gy - ay) < 1.0, f"N: {gy} vs {ay}"
        assert list(target.parent.glob("*.mosaic.tif")) == []  # tmp cleaned up

    def test_target_5514_full_coverage_from_source_bbox(self, tmp_path):
        """R-01: sheets with ``bbox_source_2180`` cover the WHOLE result grid.

        The image of a 2180 rectangle in Krovak is a rotated quadrilateral, so
        the target envelope sticks out past the request - without a margin on
        the source side the result corners would be nodata.
        """
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox,
            "EPSG:5514",
            output_dir=str(tmp_path),
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        sheets = [
            _write_sheet_asc(tmp_path / "a.asc", 529900, 381950, size=200),
            _write_sheet_asc(tmp_path / "b.asc", 530100, 381950, size=200),
        ]

        build_pl_cutout(
            sheets,
            cut.bbox_source_2180,
            cut.bbox_target,
            1.0,
            cut.pinned,
            cut.target_path,
        )

        with rasterio.open(cut.target_path) as ds:
            data = ds.read(1)
        assert not (data == _NODATA).any()

    def test_nodata_seam_between_sheets(self, tmp_path):
        """Mosaic of sheets with a gap: a nodata strip in the result, never zero."""
        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        b = _write_sheet_asc(tmp_path / "b.asc", 530120, 382000)  # 20 m gap
        bbox = BBox(530010, 382010, 530210, 382090, "EPSG:2180")
        target = tmp_path / "cut.tif"

        build_pl_cutout([a, b], bbox, bbox, 1.0, None, target)

        with rasterio.open(target) as ds:
            assert ds.nodata == _NODATA
            data = ds.read(1)
        # gap 530100..530120 = columns 90..109 (min_x 530010, 1 m pixel)
        assert (data[:, 90:110] == _NODATA).all()
        assert not (data == 0.0).any()

    def test_target_2180_crop_only(self, tmp_path):
        """EPSG:2180: crop only — a GeoTIFF with the CRS written, extent = bbox."""
        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        bbox = BBox(530010, 382010, 530090, 382090, "EPSG:2180")
        target = tmp_path / "cut.tif"

        build_pl_cutout([a], bbox, bbox, 1.0, None, target)

        with rasterio.open(target) as ds:
            assert ds.crs is not None and ds.crs.to_epsg() == 2180
            assert ds.bounds == (530010.0, 382010.0, 530090.0, 382090.0)

    def test_failed_build_keeps_previous_result(self, tmp_path):
        """An aborted build does NOT destroy the previous result or leave tmp.

        Both write paths are atomic (``os.replace`` for a plain crop, the
        internal ``os.replace`` in ``warp_to_grid``), so a half-written file
        cannot be left at the final path - and that being the case, deleting
        the old result was pure data loss (exit code 0 for the whole task on
        the border under ``--country auto``).
        """
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        bbox = BBox(530010, 382010, 530090, 382090, "EPSG:2180")
        pinned = _pinned_2180_to("EPSG:5514")
        target = tmp_path / "out" / "cut.tif"
        target.parent.mkdir()
        target.write_bytes(b"II*\x00poprzedni wynik")

        with (
            patch(
                "kartograf.transform.raster.warp_to_grid",
                side_effect=RuntimeError("warp przerwany"),
            ),
            pytest.raises(RuntimeError, match="warp przerwany"),
        ):
            build_pl_cutout(
                [a], bbox, bbox_to_crs(bbox, "EPSG:5514"), 1.0, pinned, target
            )

        assert target.read_bytes() == b"II*\x00poprzedni wynik"
        assert list(target.parent.glob("*.mosaic.tif")) == []


class TestPreparePlCutout:
    def test_target_2180_no_pinned_and_native_name(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox, "EPSG:2180", output_dir=str(tmp_path), vertical_crs="EVRF2007"
        )
        assert cut.pinned is None
        assert cut.bbox_target is cut.bbox_2180
        # without a warp the result grid equals the request - margin unneeded (R-01)
        assert cut.bbox_source_2180 is cut.bbox_2180
        assert cut.target_path == (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )

    def test_target_5514_builds_pinned_and_names_in_target(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox, "EPSG:5514", output_dir=str(tmp_path), vertical_crs="EVRF2007"
        )
        assert cut.pinned is not None and cut.pinned.accuracy_m <= 1.0
        assert cut.bbox_target.crs == "EPSG:5514"
        # source wider than the request on EVERY side (R-01: grid coverage)
        source = cut.bbox_source_2180
        assert source.crs == "EPSG:2180"
        assert source.min_x < cut.bbox_2180.min_x
        assert source.min_y < cut.bbox_2180.min_y
        assert source.max_x > cut.bbox_2180.max_x
        assert source.max_y > cut.bbox_2180.max_y
        # the name carries coordinates in the RESULT CRS (Krovak: negative)
        assert cut.target_path.name.startswith("-")
        assert cut.target_path.parent == (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        )

    @pytest.mark.parametrize(("resolution", "margin"), [("1m", 4.0), ("5m", 20.0)])
    def test_source_has_warp_margin_of_four_pixels(self, tmp_path, resolution, margin):
        """D9: source margin = WARP_MARGIN_PX (4 px) on each side.

        Measured around the target envelope mapped to EPSG:2180 — the same
        constant as on the CZ path.
        """
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox,
            "EPSG:5514",
            output_dir=str(tmp_path),
            resolution=resolution,
            vertical_crs="EVRF2007",
        )
        back = bbox_to_crs(cut.bbox_target, "EPSG:2180")
        source = cut.bbox_source_2180
        assert source.min_x == pytest.approx(back.min_x - margin)
        assert source.min_y == pytest.approx(back.min_y - margin)
        assert source.max_x == pytest.approx(back.max_x + margin)
        assert source.max_y == pytest.approx(back.max_y + margin)

    def test_probe_point_is_center_of_request(self, tmp_path):
        """The operations are chosen by the policy WITH A PROBE at the request
        centre, not by the policy alone.

        Without the probe an operation whose grid does not cover the area
        (inf/NaN for the request) would pass - policy rule 3, a mirror of the
        CZ path.
        """
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        real = _pinned_2180_to("EPSG:5514")

        with patch(
            "kartograf.transform.crs.build_pinned_transform", return_value=real
        ) as build:
            prepare_pl_cutout(
                bbox, "EPSG:5514", output_dir=str(tmp_path), vertical_crs="EVRF2007"
            )

        policy = build.call_args.args[2]
        assert policy.probe_point == (530100.0, 382050.0)
        assert policy.min_accuracy_m == 1.0
        assert policy.allow_network_grids is False

    def test_vertical_kron86_lands_in_kron86_segment(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox, "EPSG:2180", output_dir=str(tmp_path), vertical_crs="KRON86"
        )
        assert "pl_1992_1m_kron86" in cut.target_path.parts

    @pytest.mark.parametrize("label", ["epsg:5514", " EPSG:5514 "])
    def test_czech_crs_label_leaves_krovak_by_pinned_operation(self, tmp_path, label):
        """m-2: the Czech CRS label is independent of letter case and spaces.

        The comparison used to be literal: a library call with ``"epsg:5514"``
        silently went through the default pyproj transformer instead of the
        pinned operation (a bypass of ADR-024 in the public API).
        """
        from kartograf.core.bbox import transform_bbox

        coords = (-455000.0, -1117000.0, -454000.0, -1116000.0)  # Cieszyn (PL)
        pinned = prepare_pl_cutout(
            BBox(*coords, "EPSG:5514"),
            "EPSG:2180",
            output_dir=str(tmp_path),
            vertical_crs="EVRF2007",
        ).bbox_2180
        # sanity condition: the unpinned path gives a DIFFERENT bbox here (measured
        # 1.06 m on max_y) - otherwise the test would not tell the paths apart
        unpinned = transform_bbox(BBox(*coords, "EPSG:5514"), "EPSG:2180")
        shift = max(abs(a - b) for a, b in zip(pinned[:4], unpinned[:4], strict=True))
        assert shift > 0.01

        cut = prepare_pl_cutout(
            BBox(*coords, label),
            "EPSG:2180",
            output_dir=str(tmp_path),
            vertical_crs="EVRF2007",
        )

        assert cut.bbox_2180 == pinned

    def test_lowercase_2180_label_is_canonical(self, tmp_path):
        """m-2: ``"epsg:2180"`` is the cutout CRS without a transformation, and
        the ``PlCutout`` fields carry the canonical label - as before
        normalisation, when such a bbox went through an identity transformation."""
        cut = prepare_pl_cutout(
            BBox(530010, 382010, 530190, 382090, "epsg:2180"),
            "EPSG:2180",
            output_dir=str(tmp_path),
            vertical_crs="EVRF2007",
        )

        assert cut.bbox_2180 == BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        assert cut.target_path.name == "530010_382010_530190_382090.tif"

    def test_wgs84_bbox_across_19e_keeps_southern_band(self, tmp_path):
        """K6: a WGS84 bbox across the EPSG:2180 central meridian (19E) - the S
        edge is an arc bent to the south, and four corners lost ~479 m of the
        strip (min_y 237447.4 instead of 236968.4). The file name carries the
        correct extent."""
        cut = prepare_pl_cutout(
            BBox(18.0, 50.0, 20.0, 50.2, "EPSG:4326"),
            "EPSG:2180",
            output_dir=str(tmp_path),
            vertical_crs="EVRF2007",
        )

        assert cut.bbox_2180.min_y == pytest.approx(236968.4486, abs=0.01)
        assert cut.target_path.name.split("_")[1] == "236968.4486"

    def test_utm_cutout_name_keeps_full_coordinates(self, tmp_path):
        """D7: the cutout name is ``format(v, ".10g")`` of the result grid -
        a UTM northing (7 digits) without exponent notation; the same function
        as the CZ path."""
        cut = prepare_pl_cutout(
            BBox(530010, 382010, 530190, 382090, "EPSG:2180"),
            "EPSG:3045",
            output_dir=str(tmp_path),
        )
        b = cut.bbox_target
        coords = [format(v, ".10g") for v in (b.min_x, b.min_y, b.max_x, b.max_y)]
        assert cut.target_path.name == "_".join(coords) + ".tif"
        assert "e+" not in cut.target_path.name

    def test_wgs84_bbox_normalized_to_2180(self, tmp_path):
        bbox = BBox(18.60, 49.75, 18.65, 49.77, "EPSG:4326")
        cut = prepare_pl_cutout(
            bbox, "EPSG:2180", output_dir=str(tmp_path), vertical_crs="EVRF2007"
        )
        assert cut.bbox_2180.crs == "EPSG:2180"
        assert 400000 < cut.bbox_2180.min_x < 700000  # order of magnitude of 2180

    def test_unavailable_operation_raises_transform_error(self, tmp_path):
        """Fail-fast: no operation -> TransformError BEFORE the network (spec 6.3)."""
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch(
                "kartograf.transform.crs.build_pinned_transform",
                side_effect=TransformUnavailableError("brak operacji", remedy="R"),
            ),
            pytest.raises(TransformUnavailableError),
        ):
            prepare_pl_cutout(
                bbox, "EPSG:5514", output_dir=str(tmp_path), vertical_crs="EVRF2007"
            )


_DL = "kartograf.cli.download_cmd"
# cutout library layer (R3) - sheet selection and the manager live here
_CUT = "kartograf.download.cutout"


def _pl_args(tmp_path, **overrides):
    """Namespace as from argparse for direct calls of _download_pl_bbox."""
    base = dict(
        godlo=None,
        bbox="530010,382010,530190,382090",
        bbox_crs="EPSG:2180",
        geometry=None,
        layer=None,
        scale=None,
        output=str(tmp_path),
        force=False,
        quiet=True,
        vertical_crs=None,
        resolution=None,
        product="nmt",
        system=None,
        country="pl",
        target_crs="EPSG:2180",
        workers=1,
        year=None,
        min_density=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


_PARENT = {
    "bbox": [530010.0, 382010.0, 530190.0, 382090.0],
    "bbox_crs": "EPSG:2180",
    "countries": ["PL"],
}

# The request bbox shared by the flows below. A constant, not an object built
# in a helper - the tests check the IDENTITY of the object passed to sheet
# selection (proof that without --target-crs the margin does NOT enter selection).
_BBOX_2180 = BBox(530010, 382010, 530190, 382090, "EPSG:2180")


class TestSheetGrid:
    """Finding 1 / R1: a cutout on the sheet grid, without shifting the content."""

    def _sheets(self, tmp_path, value):
        a = _write_grid_sheet(tmp_path / "a.asc", 0, 160, 200, value)
        b = _write_grid_sheet(
            tmp_path / "b.asc", 150, 160, 200, value
        )  # an overlap of 10 px
        return [a, b]

    @pytest.mark.parametrize(
        "bbox",
        [
            BBox(530010.37, 382010.61, 530150.29, 382085.43, "EPSG:2180"),
            BBox(530010, 382010, 530150, 382086, "EPSG:2180"),
        ],
        ids=["ulamkowy", "calkowity"],
    )
    def test_target_2180_on_sheet_grid_exact_values(self, tmp_path, bbox):
        from kartograf.download.cutout import build_pl_cutout

        sheets = self._sheets(tmp_path, _ids)
        target = tmp_path / "out.tif"
        build_pl_cutout(sheets, bbox, bbox, 1.0, None, target)
        with rasterio.open(target) as ds:
            t, data = ds.transform, ds.read(1)
            left, bottom, right, top = ds.bounds
        assert (t.c - 0.5) == pytest.approx(round(t.c - 0.5), abs=1e-6)
        assert (t.f - 0.5) == pytest.approx(round(t.f - 0.5), abs=1e-6)
        assert left <= bbox.min_x < left + 1 and right - 1 < bbox.max_x <= right
        assert bottom <= bbox.min_y < bottom + 1 and top - 1 < bbox.max_y <= top
        gx, gy = np.meshgrid(
            t.c + (np.arange(data.shape[1]) + 0.5),
            t.f - (np.arange(data.shape[0]) + 0.5),
        )
        np.testing.assert_array_equal(data, _ids(gx, gy).astype("float32"))

    def test_target_5514_warp_has_no_subpixel_shift(self, tmp_path):
        """Linear ramp: a cutout from sheets == a warp of an ideal raster on the
        sheet grid (the same pinned operation, the same result grid). Any
        content shift in the mosaic shows up as a discrepancy (without the fix:
        mean 0.35 m, max 0.64 m; after the fix: 0)."""
        from rasterio.transform import from_origin

        from kartograf.download.cutout import build_pl_cutout, prepare_pl_cutout
        from kartograf.transform.raster import warp_to_grid

        def ramp(gx, gy):
            return 0.3 * (gx - 529950.0) + 0.7 * (gy - 381950.0)

        sheets = self._sheets(tmp_path, ramp)
        cut = prepare_pl_cutout(
            BBox(530010.37, 382010.61, 530150.29, 382085.43, "EPSG:2180"),
            "EPSG:5514",
            output_dir=tmp_path,
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        build_pl_cutout(
            sheets,
            cut.bbox_source_2180,
            cut.bbox_target,
            1.0,
            cut.pinned,
            cut.target_path,
        )
        cols, rows = np.meshgrid(np.arange(310), np.arange(200))  # sum of both sheets
        ideal = tmp_path / "ideal.tif"
        with rasterio.open(
            ideal,
            "w",
            driver="GTiff",
            width=310,
            height=200,
            count=1,
            dtype="float32",
            crs="EPSG:2180",
            nodata=_NODATA,
            transform=from_origin(529950.5, 382150.5, 1.0, 1.0),
        ) as dst:
            dst.write(
                ramp(529950.5 + cols + 0.5, 382150.5 - rows - 0.5).astype("float32"), 1
            )
        ref = tmp_path / "ref.tif"
        warp_to_grid(
            ideal,
            ref,
            cut.bbox_target,
            1.0,
            cut.pinned,
            src_crs="EPSG:2180",
            nodata=_NODATA,
        )
        with rasterio.open(cut.target_path) as got, rasterio.open(ref) as exp:
            assert got.transform == exp.transform
            np.testing.assert_array_equal(got.read(1), exp.read(1))

    def test_mixed_prj_cache_builds(self, tmp_path):
        """Fact 6: a sheet with .prj (Hydrograf) next to a sheet without .prj.
        Uses the real .prj content from the Hydrograf cache (P-01) - WKT1_GDAL
        from pyproj would differ from what is actually in the .prj on the
        Hydrograf disk."""
        from kartograf.download.cutout import build_pl_cutout

        sheets = self._sheets(tmp_path, _ids)
        sheets[0].with_suffix(".prj").write_text(_HYDROGRAF_2180_WKT)
        bbox = BBox(530010, 382010, 530150, 382086, "EPSG:2180")
        build_pl_cutout(sheets, bbox, bbox, 1.0, None, tmp_path / "o.tif")
        with rasterio.open(tmp_path / "o.tif") as ds:
            assert not (ds.read(1) == _NODATA).any()

    @pytest.mark.parametrize("reverse", [False, True], ids=["a_first", "b_first"])
    def test_integer_first_sheet_keeps_decimals(self, tmp_path, reverse):
        """Fact 5: a sheet with integers only must not truncate the heights of
        the other sheets, REGARDLESS OF INPUT ORDER (P-07). RED expected for
        the order [a, b]: before the fix (`sorted()`/`dtype="float32"` in
        Step 3) merge takes the dtype from the FIRST source on the input
        list, and `a` (int) is then first; the order [b, a] is not RED (float
        is already first) but stays as a regression guard."""
        from kartograf.download.cutout import build_pl_cutout

        a = _write_grid_sheet(
            tmp_path / "a.asc",
            0,
            160,
            200,
            lambda gx, gy: gx * 0 + 100,
            nodata_header="-9999",
            fmt="{:.0f}",
        )
        b = _write_grid_sheet(
            tmp_path / "b.asc",
            150,
            160,
            200,
            lambda gx, gy: gx * 0 + 100.25,
            nodata_header="-9999",
        )
        with rasterio.open(a) as ds:
            assert ds.dtypes[0] == "int32"  # sanity check
        bbox = BBox(530010, 382010, 530250, 382086, "EPSG:2180")
        order = [b, a] if reverse else [a, b]
        build_pl_cutout(order, bbox, bbox, 1.0, None, tmp_path / "o.tif")
        with rasterio.open(tmp_path / "o.tif") as ds:
            assert ds.read(1)[0, -1] == pytest.approx(100.25)

    def test_pl2000_sheet_rejected_loudly(self, tmp_path):
        """Fact 7: a sheet in PL-2000 coordinates under a PL-1992 sheet code
        (cache from before 0.7.0) - an error with a description and a path to
        delete instead of a silent nodata hole."""
        from kartograf.download.cutout import build_pl_cutout
        from kartograf.exceptions import ValidationError

        good = _write_grid_sheet(tmp_path / "a.asc", 0, 160, 200, _ids)
        foreign = _write_grid_sheet(tmp_path / "b.asc", 0, 160, 200, _ids, x0=6500000.5)
        bbox = BBox(530010, 382010, 530150, 382086, "EPSG:2180")
        with pytest.raises(ValidationError, match="PL-2000") as exc:
            build_pl_cutout([good, foreign], bbox, bbox, 1.0, None, tmp_path / "o.tif")
        assert not (tmp_path / "o.tif").exists()
        message = str(exc.value)
        assert "wczesniejszej wersji Kartografa" in message
        assert f"Usun go i ponow pobranie: {foreign}" in message
        assert str(good) not in message

    def test_selection_expanded_by_one_pixel(self, tmp_path):
        """Crop snapped outwards (< 1 px) - selection with a 1 px margin so
        that an edge pixel does not fall into a sheet outside the list."""
        from kartograf.download.cutout import prepare_pl_cutout, select_pl_cutout_sheets

        cut = prepare_pl_cutout(
            _BBOX_2180,
            "EPSG:2180",
            output_dir=tmp_path,
            resolution="5m",
            vertical_crs="EVRF2007",
        )
        with patch(
            f"{_CUT}.find_sheets_for_bbox", return_value=["N-34-130-D-d-2-4"]
        ) as find:
            select_pl_cutout_sheets(cut)
        sent = find.call_args.args[0]
        src = cut.bbox_source_2180
        assert (sent.min_x, sent.min_y, sent.max_x, sent.max_y) == (
            src.min_x - 5.0,
            src.min_y - 5.0,
            src.max_x + 5.0,
            src.max_y + 5.0,
        )

    def test_geometry_sum_selection_expanded_by_one_pixel(self, tmp_path):
        """The R-01 sum (geometry + warp) takes sheets from the same envelope
        with a 1 px margin as the bbox mode - the outward-snapped crop applies
        to both modes."""
        from kartograf.download.cutout import prepare_pl_cutout, select_pl_cutout_sheets

        cut = prepare_pl_cutout(
            _BBOX_2180,
            "EPSG:5514",
            output_dir=tmp_path,
            resolution="5m",
            vertical_crs="EVRF2007",
        )
        with (
            # local import in select_pl_cutout_sheets -> patch at the source
            patch(
                "kartograf.core.geometry.find_sheets_for_geometry",
                return_value=["N-1"],
            ),
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-2"]) as find,
        ):
            sheets = select_pl_cutout_sheets(cut, geometry=tmp_path / "area.gpkg")
        assert sheets.godla == ("N-1", "N-2")
        sent = find.call_args.args[0]
        src = cut.bbox_source_2180
        assert (sent.min_x, sent.min_y, sent.max_x, sent.max_y) == (
            src.min_x - 5.0,
            src.min_y - 5.0,
            src.max_x + 5.0,
            src.max_y + 5.0,
        )

    def test_input_order_does_not_change_result(self, tmp_path):
        """Sorted inputs: the result does not depend on list order (parallel
        download returns sheets in completion order). ``merge`` gives the
        overlap to the FIRST source, so without sorting the same sheet list in
        a different order would give a different raster."""
        from kartograf.download.cutout import build_pl_cutout

        a = _write_grid_sheet(
            tmp_path / "a.asc", 0, 160, 200, lambda gx, gy: gx * 0 + 1.0
        )
        b = _write_grid_sheet(
            tmp_path / "b.asc", 150, 160, 200, lambda gx, gy: gx * 0 + 2.0
        )
        bbox = BBox(530010, 382010, 530250, 382086, "EPSG:2180")
        results = []
        for name, order in (("ab.tif", [a, b]), ("ba.tif", [b, a])):
            build_pl_cutout(order, bbox, bbox, 1.0, None, tmp_path / name)
            with rasterio.open(tmp_path / name) as ds:
                results.append(ds.read(1))
        # sanity condition: both sheets are in the result, and their overlap
        # (x 530100.5-530110.5) lies within the bbox
        assert {1.0, 2.0} <= set(np.unique(results[0]).tolist())
        np.testing.assert_array_equal(results[0], results[1])


class TestDownloadPlBboxCutout:
    """Spec 8: the cutout flow at the PL worker level (mocked download)."""

    def _run(
        self,
        tmp_path,
        args,
        sheets,
        failed=(),
        no_coverage=(),
        provider=None,
        bbox=_BBOX_2180,
        godla=("N-1", "N-2"),
    ):
        """PL worker with a mocked download; returns ``(rc, manager, find)``.

        The CLASS mock of ``DownloadManager`` (constructor kwargs, e.g.
        ``sidecar_extra``) stays in ``self.dm`` - the return stays a triple
        because later tests unpack it. ``no_coverage`` is a subset of
        ``failed`` (sheets without GUGiK data, R5) - as in ``DownloadResult``.
        """
        from kartograf.download.manager import DownloadResult

        provider = provider or SimpleNamespace(vertical_crs="EVRF2007")
        manager = Mock()
        manager.download_sheets.return_value = list(sheets)
        manager.last_result = DownloadResult(
            failed=list(failed), no_coverage=list(no_coverage)
        )
        with (
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=list(godla)) as find,
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager) as dm,
        ):
            rc = _download_pl_bbox(args, bbox, _PARENT)
        self.dm = dm
        return rc, manager, find

    def test_sheet_list_header(self, tmp_path, capsys):
        """D15: the cutout sheet-list header = the same as in list mode."""
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        godla = tuple(f"N-{i}" for i in range(1, 13))
        rc, *_ = self._run(
            tmp_path, _pl_args(tmp_path, quiet=False), sheets, godla=godla
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Found 12 sheets at 1:10000 for bbox (resolution: 1m)\n" in out
        assert "  Sheets: N-1, N-2, N-3, ..., N-11, N-12\n" in out

    def test_creates_cutout_and_sidecar(self, tmp_path):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        target = (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        assert target.exists()
        payload = json.loads(
            (target.parent / f"{target.name}.meta.json").read_text("utf-8")
        )
        assert payload["dataset"] == "pl.gugik.nmt_1m"
        assert payload["horizontal_crs"] == "EPSG:2180"
        assert payload["transform"] is None  # 2180 = sam crop (spec 6.1)
        assert payload["nodata"] == _NODATA
        assert payload["vertical_crs"] == "EPSG:9651"  # EVRF2007-PL, sheet channel
        assert payload["request"]["bbox_crs"] == "EPSG:2180"
        assert payload["extra"]["parent_request"] == _PARENT
        # the SHEET sidecars (cache) also carry the task parent - as without a cutout
        assert self.dm.call_args.kwargs["sidecar_extra"] == {"parent_request": _PARENT}

    def test_target_5514_sidecar_has_pinned_transform(self, tmp_path):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, _manager, find = self._run(
            tmp_path, _pl_args(tmp_path, target_crs="EPSG:5514"), sheets
        )

        assert rc == 0
        cut_dir = tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        tifs = list(cut_dir.glob("*.tif"))
        assert len(tifs) == 1
        payload = json.loads((cut_dir / f"{tifs[0].name}.meta.json").read_text("utf-8"))
        assert payload["horizontal_crs"] == "EPSG:5514"
        assert payload["transform"]["horizontal"].startswith("pinned: ")
        # D7: same format as the CZ path (`pinned_label`) — with the accuracy
        assert payload["transform"]["horizontal"].endswith(" m)")
        assert payload["request"]["bbox_crs"] == "EPSG:5514"
        # R-01: the bbox WITH A MARGIN goes to sheet SELECTION, not the request
        # itself - otherwise rotated result-grid corners fall outside the sheets
        sent = find.call_args.args[0]
        assert sent.min_x < _BBOX_2180.min_x
        assert sent.max_x > _BBOX_2180.max_x
        assert sent.min_y < _BBOX_2180.min_y
        assert sent.max_y > _BBOX_2180.max_y

    def test_5m_kron86_grid_dataset_vertical_and_segment(self, tmp_path):
        """The whole 5m flow in one test: grid, descriptor, vertical, segment.

        ``--resolution 5m`` with ``--vertical-crs KRON86`` is corrected to
        EVRF2007 in the provider factory (5m does not exist in KRON86), so the
        cutout must follow the PROVIDER, not the raw CLI flag. For sheets this
        error class has long been guarded - the cutout path was a gap in it:
        a 1 m pixel from 5 m data (25x the file size) or a ``pl_1992_5m_kron86``
        segment with an EPSG:9650 sidecar passed the whole suite.
        """
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 529900, 381950, size=40, pixel=5.0),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 381950, size=40, pixel=5.0),
        ]
        args = _pl_args(
            tmp_path, resolution="5m", vertical_crs="KRON86", target_crs="EPSG:5514"
        )
        rc, *_ = self._run(tmp_path, args, sheets)

        assert rc == 0
        cut_dir = tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox"
        tifs = list(cut_dir.glob("*.tif"))
        assert len(tifs) == 1
        with rasterio.open(tifs[0]) as ds:
            assert ds.res == (5.0, 5.0)
        payload = json.loads((cut_dir / f"{tifs[0].name}.meta.json").read_text("utf-8"))
        assert payload["dataset"] == "pl.gugik.nmt_5m"
        assert payload["vertical_crs"] == "EPSG:9651"

    def test_unexpected_raster_error_returns_1(self, tmp_path, capsys):
        """An error outside (ValidationError, TransformError) also ends with code 1.

        ``mosaic_and_crop``/``warp_to_grid`` may raise ``RasterioIOError``
        (a damaged cached sheet). Letting such an exception leak out of the
        country loop of ``_dispatch_area`` breaks the ADR-023 partial-success
        contract.
        """
        from rasterio.errors import RasterioIOError

        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        with patch(
            f"{_CUT}.build_pl_cutout",
            side_effect=RasterioIOError("uszkodzony arkusz"),
        ):
            rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 1
        assert "uszkodzony arkusz" in capsys.readouterr().err

    def test_pl2000_sheet_returns_1_with_reason(self, tmp_path, capsys):
        foreign = _write_grid_sheet(tmp_path / "b.asc", 0, 160, 200, _ids, x0=6500000.5)
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), [foreign])
        assert rc == 1
        assert "PL-2000" in capsys.readouterr().err

    def test_failed_sheet_returns_1_and_no_cutout(self, tmp_path):
        """R5: a sheet download failure (not missing GUGiK data) = code 1, no cutout."""
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets, failed=["N-2"])

        assert rc == 1
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()

    def test_missing_sheet_warns_and_returns_0(self, tmp_path, capsys):
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, *_ = self._run(
            tmp_path, _pl_args(tmp_path), sheets, failed=["N-2"], no_coverage=["N-2"]
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning:" in err and "N-2" in err

    def test_all_nodata_cutout_warns_and_returns_0(self, tmp_path, capsys):
        """N2: downloaded sheets without a single valid pixel = Warning:, code 0."""
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000, fill=_NODATA),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000, fill=_NODATA),
        ]
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning: wycinek w calosci nodata" in err
        assert "brak danych GUGiK / obszar poza pokryciem" in err
        (tif,) = (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        assert tif.exists()

    def test_cutout_with_data_has_no_nodata_warning(self, tmp_path, capsys):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000, fill=_NODATA),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        assert "w calosci nodata" not in capsys.readouterr().err

    def test_skipped_cutout_repeats_missing_sheets_warning_from_sidecar(
        self, tmp_path, capsys
    ):
        """N4: a skipped cutout warns about holes from the SIDECAR (silent before)."""
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, *_ = self._run(
            tmp_path, _pl_args(tmp_path), sheets, failed=["N-2"], no_coverage=["N-2"]
        )
        assert rc == 0
        first = capsys.readouterr().err
        assert "z sidecara" not in first

        rc, manager, find = self._run(tmp_path, _pl_args(tmp_path), sheets=[])

        assert rc == 0
        manager.download_sheets.assert_not_called()
        find.assert_not_called()
        second = capsys.readouterr().err
        assert "Warning: GUGiK nie ma danych dla 1 arkuszy wycinka (N-2)" in second
        assert "(z sidecara istniejacego wycinka)" in second

    def test_skipped_cutout_to_krovak_reports_legacy_sidecar(self, tmp_path, capsys):
        """D12: a PL -> 5514 cutout from before the S-JTSK fix (step "(3)") = Info:."""
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        args = _pl_args(tmp_path, target_crs="EPSG:5514")
        rc, *_ = self._run(tmp_path, args, sheets)
        assert rc == 0
        (tif,) = (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        sidecar = tif.with_name(f"{tif.name}.meta.json")
        payload = json.loads(sidecar.read_text("utf-8"))
        # after the K2 fix the new cutout does NOT pin step (3)
        assert "S-JTSK to ETRS89 (3)" not in payload["transform"]["horizontal"]
        assert "sprzed naprawy" not in capsys.readouterr().err

        payload["transform"]["horizontal"] = "S-JTSK to ETRS89 (3) + Krovak (0.5 m)"
        sidecar.write_text(json.dumps(payload), "utf-8")
        rc, *_ = self._run(tmp_path, args, sheets=[])

        assert rc == 0
        err = capsys.readouterr().err
        assert "sprzed naprawy operacji S-JTSK" in err and "--force" in err

    def test_missing_sheets_warning_shows_10_sidecar_lists_all(self, tmp_path, capsys):
        """Stderr shows up to 10 sheet codes; the full, sorted list is in the sidecar.

        A coast or a border strip is dozens of sheets without data - stderr
        stays readable, and the consumer gets the full list from the sidecar.
        Input in reverse order: parallel download returns sheets in completion
        order, and the list must be stable.
        """
        names = [f"N-{i:02d}" for i in range(12)]
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, *_ = self._run(
            tmp_path,
            _pl_args(tmp_path),
            sheets,
            failed=names[::-1],
            no_coverage=names[::-1],
        )

        assert rc == 0
        err = capsys.readouterr().err
        assert "12 arkuszy" in err
        # the first 10 after sorting, the rest as " ..."
        assert "N-00, N-01" in err and "N-09 ..." in err and "N-10" not in err
        cut_dir = tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        (tif,) = cut_dir.glob("*.tif")
        payload = json.loads((cut_dir / f"{tif.name}.meta.json").read_text("utf-8"))
        assert payload["extra"]["missing_sheets"] == names

    def test_error_lists_all_failed_sheets(self, tmp_path, capsys):
        """The message lists ALL failed sheets (``download_sheets``).

        Until now the thread pool ended with the first exception - the user
        learned about one missing sheet per run.
        """
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), [], failed=["N-1", "N-2"])

        assert rc == 1
        err = capsys.readouterr().err
        assert "N-1" in err and "N-2" in err, err
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()

    def test_skip_existing_short_circuits_before_download(self, tmp_path):
        target = (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        target.parent.mkdir(parents=True)
        target.write_bytes(b"II*\x00")
        rc, manager, find = self._run(tmp_path, _pl_args(tmp_path), sheets=[])

        assert rc == 0
        manager.download_sheets.assert_not_called()
        # the shortcut works BEFORE sheet selection - no work on sheet codes
        find.assert_not_called()

    def test_force_rebuilds_existing_cutout_and_passes_workers(self, tmp_path):
        """I-1/m-1: ``--force`` and ``--workers`` from the CLI reach the library.

        ``run_pl_cutout`` has its OWN "file exists" shortcut: if the CLI stopped
        passing ``force``, ``--force`` on an existing cutout would be a silent
        no-op (code 0, ``Downloaded to <old file>``) - and the CHANGELOG says
        to rebuild cutouts from before the grid fix precisely with ``--force``.
        """
        target = (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        target.parent.mkdir(parents=True)
        stale = b"II*\x00stary wycinek"
        target.write_bytes(stale)
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]

        rc, manager, _ = self._run(
            tmp_path, _pl_args(tmp_path, force=True, workers=3), sheets
        )

        assert rc == 0
        assert target.read_bytes() != stale, "--force nie przebudowal wycinka"
        with rasterio.open(target) as ds:
            # both flat 100.0 sheets cover the whole bbox - zero nodata
            assert (ds.read(1) == 100.0).all()
        # --force downloads the sheets again too (CHANGELOG), not just the cutout
        assert manager.download_sheets.call_args.kwargs["skip_existing"] is False
        # --workers reaches the cutout path's manager (m-1)
        assert self.dm.call_args.kwargs["max_workers"] == 3

    def test_without_target_crs_behaviour_unchanged(self, tmp_path):
        """Without the flag: a sheet list as before, no cutout (spec 6.1).

        The path WITHOUT a cutout stays in ``cli.download_cmd`` - hence the own
        ``_DL`` patches, not the ``_run`` harness (which patches ``download.cutout``).
        """
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        with (
            patch(f"{_DL}.find_sheets_for_bbox", return_value=["N-1"]) as find,
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(SimpleNamespace(vertical_crs="EVRF2007"), Mock()),
            ),
            patch(f"{_DL}.DownloadManager"),
            patch(
                f"{_DL}._download_godlo_list",
                return_value=(sheets, DownloadResult(succeeded=sheets)),
            ),
        ):
            rc = _download_pl_bbox(
                _pl_args(tmp_path, target_crs=None), _BBOX_2180, _PARENT
            )

        assert rc == 0
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()
        # without a cutout the margin does NOT enter selection - the sheets are
        # determined exactly by the user's request (the same object, not a padded copy)
        assert find.call_args.args[0] is _BBOX_2180


class TestCutoutSize:
    """Finding 9: no hard limit, but no discovering of the full disk after hours."""

    def test_disk_check_blocks_before_download(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "shutil.disk_usage", lambda path: SimpleNamespace(total=0, used=0, free=0)
        )
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, manager, _ = TestDownloadPlBboxCutout()._run(
            tmp_path, _pl_args(tmp_path), sheets
        )
        assert rc == 1
        assert "Za malo miejsca" in capsys.readouterr().err
        manager.download_sheets.assert_not_called()

    def test_estimate_counts_only_pending_sheets(self, tmp_path):
        from kartograf.download.cutout import (
            PlCutoutSheets,
            estimate_pl_cutout_bytes,
            prepare_pl_cutout,
        )
        from kartograf.download.storage import FileStorage

        cut = prepare_pl_cutout(_BBOX_2180, "EPSG:2180", output_dir=tmp_path)
        sheets = PlCutoutSheets(godla=("N-34-130-D-d-2-3", "N-34-130-D-d-2-4"))
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        both, pending_both = estimate_pl_cutout_bytes(cut, sheets, storage=storage)
        cached = storage.get_path("N-34-130-D-d-2-3", ".asc")
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"x")
        one, pending_one = estimate_pl_cutout_bytes(cut, sheets, storage=storage)
        assert (pending_both, pending_one) == (2, 1)
        assert cut.estimated_bytes < one < both

    def test_estimate_default_storage_is_sheet_segment_of_vertical(self, tmp_path):
        """D18: without ``storage=`` the cached sheets are looked up in the
        segment of the cutout's ACTUAL vertical (KRON86), not the default EVRF2007."""
        from kartograf.download.cutout import (
            PlCutoutSheets,
            estimate_pl_cutout_bytes,
            prepare_pl_cutout,
        )

        cut = prepare_pl_cutout(
            _BBOX_2180, "EPSG:2180", output_dir=tmp_path, vertical_crs="KRON86"
        )
        sheets = PlCutoutSheets(godla=("N-34-130-D-d-2-3", "N-34-130-D-d-2-4"))
        cached = (
            tmp_path / "nmt/pl_1992_1m_kron86/N-34/130/D/d/2/3/N-34-130-D-d-2-3.asc"
        )
        cached.parent.mkdir(parents=True)
        cached.write_bytes(b"x")
        _, pending = estimate_pl_cutout_bytes(cut, sheets)
        assert pending == 1

    def test_estimate_builds_one_transformer_for_all_sheets(self, tmp_path):
        """N9: ``Transformer.from_crs`` (~7 ms, pyproj does not cache it) once
        per process, not once per sheet - the estimate for 1221 sheets dropped
        from ~9 s to < 0.2 s, so a caller computing it itself before
        ``run_pl_cutout`` does not pay twice. Bytes identical to the
        ``SheetParser`` envelope."""
        from pyproj import Transformer

        from kartograf.core import bbox as core_bbox
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.download.cutout import (
            PlCutoutSheets,
            estimate_pl_cutout_bytes,
            prepare_pl_cutout,
        )

        cut = prepare_pl_cutout(_BBOX_2180, "EPSG:2180", output_dir=tmp_path)
        godla = ("N-34-130-D-d-2-3", "N-34-130-D-d-2-4", "N-34-130-D-d-4-1")
        sheets = PlCutoutSheets(godla=godla)
        core_bbox._transformer.cache_clear()
        with patch.object(Transformer, "from_crs", wraps=Transformer.from_crs) as made:
            first, pending = estimate_pl_cutout_bytes(cut, sheets)
            second, _ = estimate_pl_cutout_bytes(cut, sheets)
        assert pending == 3 and made.call_count == 1
        expected = cut.estimated_bytes
        for godlo in godla:
            frame = SheetParser(godlo).get_bbox("EPSG:2180")
            expected += int(
                (frame.max_x - frame.min_x) * (frame.max_y - frame.min_y) * 5.5
            )
        assert first == second == expected

    def test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe(self, tmp_path):
        from kartograf.download.cutout import build_pl_cutout
        from kartograf.transport import mosaic as mosaic_mod

        west = _write_sheet_asc(tmp_path / "w.asc", 530000, 382000, apex=_APEX)
        east = _write_sheet_asc(tmp_path / "e.asc", 530100, 382000, apex=_APEX)
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        pinned = _pinned_2180_to("EPSG:5514")
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        with patch.object(
            mosaic_mod, "mosaic_and_crop", wraps=mosaic_mod.mosaic_and_crop
        ) as spy:
            build_pl_cutout(
                [west, east],
                bbox,
                bbox_to_crs(bbox, "EPSG:5514", pinned),
                1.0,
                pinned,
                tmp_path / "w.tif",
            )
            build_pl_cutout([west, east], bbox, bbox, 1.0, None, tmp_path / "c.tif")
        warp_kwds = spy.call_args_list[0].kwargs["dst_kwds"]
        crop_kwds = spy.call_args_list[1].kwargs["dst_kwds"]
        assert warp_kwds["compress"] == "deflate" and warp_kwds["predictor"] == 3
        assert warp_kwds["tiled"] is True and warp_kwds["blockxsize"] == 512
        assert warp_kwds["bigtiff"] == "IF_SAFER"
        assert "compress" not in crop_kwds  # EPSG:2180: the intermediate is the result

    def test_large_grid_prints_info(self, tmp_path, capsys):
        from kartograf.download.cutout import PlCutoutResult

        args = _pl_args(
            tmp_path, bbox="400000,300000,440000,330000"
        )  # 40 x 30 km @ 1 m
        big = BBox(400000, 300000, 440000, 330000, "EPSG:2180")
        with (
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-1"]),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(SimpleNamespace(vertical_crs="EVRF2007"), Mock()),
            ),
            patch(
                f"{_CUT}.run_pl_cutout",
                return_value=PlCutoutResult(path=tmp_path / "x.tif"),
            ),
        ):
            rc = _download_pl_bbox(args, big, _PARENT)
        assert rc == 0
        err = capsys.readouterr().err
        assert "Info:" in err and "GiB" in err


class TestGeometryCutout:
    def test_geometry_mode_builds_cutout(self, tmp_path):
        from kartograf.cli.download_cmd import _download_pl_geometry
        from kartograf.download.manager import DownloadResult

        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        geom = tmp_path / "area.gpkg"
        geom.write_bytes(b"stub")  # unused path: discovery mocked
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        args = _pl_args(tmp_path, bbox=None, geometry=str(geom))
        manager = Mock()
        manager.download_sheets.return_value = sheets
        manager.last_result = DownloadResult()

        with (
            # local import in select_pl_cutout_sheets -> patch at the source
            # (same convention as the geometry tests in test_cli.py)
            patch(
                "kartograf.core.geometry.find_sheets_for_geometry",
                return_value=["N-1", "N-2"],
            ),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = _download_pl_geometry(args, geom, _PARENT, bbox=bbox)

        assert rc == 0
        assert (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        ).exists()

    def test_geometry_target_5514_covers_whole_envelope(self, tmp_path):
        """R-01 also applies in `--geometry`: the margin enters SELECTION.

        The geometry points at the western sheet only, but the target envelope
        returns to EPSG:2180 larger than the request (Krovak rotation) and
        already reaches the eastern sheet. Without the union with
        ``find_sheets_for_bbox`` the cutout has a nodata frame on the eastern
        edge - with the same flag that gives a complete result in ``--bbox`` mode.
        """
        from kartograf.cli.download_cmd import _download_pl_geometry
        from kartograf.download.manager import DownloadResult

        sheets = {
            "N-1": _write_sheet_asc(tmp_path / "s1.asc", 529900, 381950, size=200),
            "N-2": _write_sheet_asc(tmp_path / "s2.asc", 530100, 381950, size=200),
        }
        geom = tmp_path / "area.gpkg"
        geom.write_bytes(b"stub")  # unused path: discovery mocked
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        args = _pl_args(tmp_path, bbox=None, geometry=str(geom), target_crs="EPSG:5514")
        manager = Mock()
        # sheet codes -> sheets: EXACTLY the selected sheets go into the mosaic
        manager.download_sheets.side_effect = lambda godla, **kw: [
            sheets[g] for g in godla
        ]
        manager.last_result = DownloadResult()

        with (
            patch(
                "kartograf.core.geometry.find_sheets_for_geometry",
                return_value=["N-1"],
            ),
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-1", "N-2"]) as find,
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = _download_pl_geometry(args, geom, _PARENT, bbox=_BBOX_2180)

        assert rc == 0
        cut = next(
            iter((tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif"))
        )
        with rasterio.open(cut) as ds:
            data = ds.read(1)
        assert not (data == _NODATA).any(), (
            f"ramka nodata: {(data == _NODATA).sum()} z {data.size} pikseli"
        )
        sent = find.call_args.args[0]
        assert sent.min_x < _BBOX_2180.min_x and sent.max_x > _BBOX_2180.max_x

    def test_cli_geometry_target_crs_reaches_worker(self, tmp_path):
        """The whole path through main(): dispatch MUST pass the envelope to the worker.

        Guards `bbox=part` in `_dispatch_area` - the only line that makes the
        geometry cutout reachable from the CLI: the envelope determines the
        grid and the crop of the cutout, and ``bbox`` is a REQUIRED argument
        in ``_download_pl_geometry``. Without that line the worker gets no
        envelope and the cutout is not created (the command ends with code 1).
        """
        from pyproj import CRS

        from kartograf.download.manager import DownloadResult

        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        geom = tmp_path / "area.gpkg"
        geom.write_bytes(b"stub")  # content unused: discovery is mocked
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        overall = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        manager = Mock()
        manager.download_sheets.return_value = sheets
        manager.last_result = DownloadResult()

        with (
            # both imports are local (cli.download_cmd, download.cutout) -> patch
            # at the source;
            # stub file (P-03): _geometry_envelope reads the CRS BEFORE the envelope
            patch(
                "kartograf.core.geometry.read_source_crs",
                return_value=CRS.from_epsg(2180),
            ),
            patch("kartograf.core.geometry.get_overall_bbox", return_value=overall),
            patch(
                "kartograf.core.geometry.find_sheets_for_geometry",
                return_value=["N-1", "N-2"],
            ),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = main(
                [
                    "download",
                    "--geometry",
                    str(geom),
                    "--country",
                    "pl",
                    "--target-crs",
                    "EPSG:2180",
                    "-o",
                    str(tmp_path),
                    "-q",
                ]
            )

        assert rc == 0
        target = (
            tmp_path
            / "nmt"
            / "pl_1992_1m_evrf2007"
            / "bbox"
            / "530010_382010_530190_382090.tif"
        )
        assert target.exists()
        # parent_request arises ONLY in the dispatch layer - proof that the
        # cutout came through `_dispatch_area`, not beside it
        payload = json.loads(
            (target.parent / f"{target.name}.meta.json").read_text("utf-8")
        )
        assert payload["horizontal_crs"] == "EPSG:2180"
        assert payload["nodata"] == _NODATA
        assert payload["extra"]["parent_request"]["countries"] == ["PL"]


class TestBorderTwoCutouts:
    """Spec 13.6 / 8(e): one command -> two cutouts in the same CRS."""

    # a small rectangle intersecting the RECTANGULAR envelopes of both countries
    # (CZ: 12.09..18.86E / 48.55..51.06N, PL: 14.07..24.20E / 49.00..54.90N)
    _BBOX = "18.80,49.70,18.801,49.7005"

    def _cz_provider(self):
        """CuzkDmrProvider stub: writes a file and pretends to be a pinned operation."""
        provider = Mock()
        provider.descriptor_key = "cz.cuzk.dmr4g"
        provider.resolution = "5m"
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

    def test_two_cutouts_share_parent_request(self, tmp_path):
        from kartograf.core.bbox import transform_bbox
        from kartograf.download.manager import DownloadResult

        # one synthetic sheet covering the Polish part of the request
        b = transform_bbox(
            BBox(18.80, 49.70, 18.801, 49.7005, "EPSG:4326"), "EPSG:2180"
        )
        sheet = _write_sheet_asc(
            tmp_path / "sheet.asc",
            b.min_x - 100,
            b.min_y - 100,
            size=60,
            pixel=5.0,
        )
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        manager = Mock()
        manager.download_sheets.return_value = [sheet]
        manager.last_result = DownloadResult()

        with (
            patch(
                "kartograf.providers.cuzk.create_dmr_provider",
                return_value=self._cz_provider(),
            ),
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-34-130-D"]),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = main(
                [
                    "download",
                    "--bbox",
                    self._BBOX,
                    "--bbox-crs",
                    "EPSG:4326",
                    "--resolution",
                    "5m",
                    "--target-crs",
                    "EPSG:2180",
                    "--vertical-crs",
                    "EVRF2007",
                    "-o",
                    str(tmp_path),
                ]
            )

        assert rc == 0
        pl = list((tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox").glob("*.tif"))
        cz = list((tmp_path / "nmt" / "cz_dmr4g_evrf2007" / "bbox").glob("*.tif"))
        assert len(pl) == 1 and len(cz) == 1
        parents = []
        for f in (*pl, *cz):
            payload = json.loads((f.parent / f"{f.name}.meta.json").read_text("utf-8"))
            assert payload["horizontal_crs"] == "EPSG:2180"
            parents.append(payload["extra"]["parent_request"])
        assert parents[0] == parents[1]
        assert parents[0]["countries"] == ["CZ", "PL"]

    def test_border_pl_sheet_without_data_still_gives_both_cutouts(
        self, tmp_path, capsys
    ):
        """R5: the Czech side of a border bbox has no GUGiK data -
        the PL cutout is created (nodata there), the CZ cutout too, code 0."""
        from kartograf.core.bbox import transform_bbox
        from kartograf.download.manager import DownloadResult

        b = transform_bbox(
            BBox(18.80, 49.70, 18.801, 49.7005, "EPSG:4326"), "EPSG:2180"
        )
        sheet = _write_sheet_asc(
            tmp_path / "sheet.asc", b.min_x - 100, b.min_y - 100, size=60, pixel=5.0
        )
        manager = Mock()
        manager.download_sheets.return_value = [sheet]
        manager.last_result = DownloadResult(
            failed=["N-34-130-D-d-2-1"], no_coverage=["N-34-130-D-d-2-1"]
        )
        with (
            patch(
                "kartograf.providers.cuzk.create_dmr_provider",
                return_value=self._cz_provider(),
            ),
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-34-130-D"]),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(SimpleNamespace(vertical_crs="EVRF2007"), Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = main(
                [
                    "download",
                    "--bbox",
                    self._BBOX,
                    "--bbox-crs",
                    "EPSG:4326",
                    "--resolution",
                    "5m",
                    "--target-crs",
                    "EPSG:2180",
                    "--vertical-crs",
                    "EVRF2007",
                    "-o",
                    str(tmp_path),
                ]
            )

        assert rc == 0
        pl_dir = tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox"
        assert len(list(pl_dir.glob("*.tif"))) == 1
        cz_dir = tmp_path / "nmt" / "cz_dmr4g_evrf2007" / "bbox"
        assert len(list(cz_dir.glob("*.tif"))) == 1
        err = capsys.readouterr().err
        assert "Warning:" in err and "N-34-130-D-d-2-1" in err


class TestTargetCrsValidations:
    """Spec 6.3 through main() - readable errors, code 1."""

    _BBOX = ["--bbox", "530010,382010,530190,382090", "--country", "pl"]

    def test_pl_godlo_rejected(self, tmp_path, capsys):
        rc = main(
            [
                "download",
                "N-34-130-D-d-2-4",
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "--bbox/--geometry" in capsys.readouterr().err

    @pytest.mark.parametrize("product", ["nmpt", "orto", "laz"])
    def test_non_nmt_rejected(self, product, tmp_path, capsys):
        rc = main(
            [
                "download",
                *self._BBOX,
                "--product",
                product,
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "--product nmt" in capsys.readouterr().err

    def test_system_2000_rejected_with_remedy(self, tmp_path, capsys):
        rc = main(
            [
                "download",
                *self._BBOX,
                "--system",
                "2000",
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "1992" in capsys.readouterr().err


class TestLibraryApi:
    """R3: the PL cutout as a library API (without argparse)."""

    _SHEETS = {
        "N-34-130-D-d-2-3": (530000, 382000),
        "N-34-130-D-d-2-4": (530100, 382000),
    }

    def _provider(self):
        provider = Mock()
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "1m"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        provider.default_extension = ".asc"
        provider.calls = []

        def download(godlo, path, timeout=30):
            provider.calls.append(godlo)
            west, south = self._SHEETS[godlo]
            return _write_sheet_asc(path, west, south)

        provider.download = download
        return provider

    def test_download_pl_cutout_end_to_end_skip_and_force(self, tmp_path):
        from kartograf import download_pl_cutout

        provider = self._provider()
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            first = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
            second = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
            third = download_pl_cutout(
                bbox, "EPSG:2180", output_dir=tmp_path, force=True
            )

        assert first.path.exists() and not first.skipped
        assert first.path.with_name(first.path.name + ".meta.json").exists()
        assert second.skipped and second.path == first.path
        assert not third.skipped
        assert sorted(provider.calls) == sorted(list(self._SHEETS) * 2)

    def test_rebuild_reuses_cached_sheets(self, tmp_path):
        """No cutout, sheets in cache: rebuild WITHOUT downloading (force=False).

        Sheets act as a cache (``skip_existing = not force``) - a deleted or
        never-built cutout must not cost re-downloading sheets that already
        lie in their segment.
        """
        from kartograf import download_pl_cutout

        provider = self._provider()
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            first = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
            first.path.unlink()  # the cutout disappears, the sheets stay in the segment
            rebuilt = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)

        assert sorted(provider.calls) == sorted(self._SHEETS)  # the 1st run only
        assert not rebuilt.skipped and rebuilt.path == first.path
        assert rebuilt.path.exists()
        assert len(rebuilt.sheet_paths) == len(self._SHEETS)

    def test_default_sheet_storage_follows_provider_vertical(self, tmp_path):
        """D18: ``run_pl_cutout`` without ``storage=`` puts sheets in the
        provider's vertical segment (KRON86) - the same segment as the CLI sheet
        list."""
        from kartograf import download_pl_cutout

        provider = self._provider()
        provider.vertical_crs = "KRON86"
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            result = download_pl_cutout(
                bbox, "EPSG:2180", output_dir=tmp_path, vertical_crs="KRON86"
            )

        segments = {p.relative_to(tmp_path).parts[:2] for p in result.sheet_paths}
        assert segments == {("nmt", "pl_1992_1m_kron86")}

    def test_5m_request_follows_factory_vertical_rule(self, tmp_path):
        """NMT factory rule (5m => EVRF2007): the cutout follows the PROVIDER.

        ``download_pl_cutout`` gives the factory the raw parameters, and takes
        the cutout vertical from the provider - with the raw KRON86 flag a 5m
        cutout would not be created (5m exists only in EVRF2007).
        """
        from kartograf import download_pl_cutout

        provider = self._provider()
        # what the real factory returns for 5m + KRON86 (vertical correction)
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "5m"
        provider.descriptor_key = "pl.gugik.nmt_5m"

        def download(godlo, path, timeout=30):
            provider.calls.append(godlo)
            west, south = self._SHEETS[godlo]
            return _write_sheet_asc(path, west, south, size=40, pixel=5.0)

        provider.download = download
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch(
                "kartograf.providers.pl.create_nmt_provider", return_value=provider
            ) as factory,
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            result = download_pl_cutout(
                bbox,
                "EPSG:2180",
                output_dir=tmp_path,
                resolution="5m",
                vertical_crs="KRON86",
            )

        factory.assert_called_once_with(
            vertical_crs="KRON86", resolution="5m", cache=None
        )
        assert result.path.parent == tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox"
        assert result.path.exists()

    def test_cache_is_handed_to_the_factory(self, tmp_path):
        """N6: ``download_pl_cutout(cache=)`` -> a provider with the record cache;
        without the kwarg the factory gets ``cache=None`` (CLI: ``--force``)."""
        from kartograf import download_pl_cutout

        provider = self._provider()
        cache = object()
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch(
                "kartograf.providers.pl.create_nmt_provider", return_value=provider
            ) as factory,
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path, cache=cache)
        assert factory.call_args.kwargs["cache"] is cache

    def test_skipped_download_reads_sheet_lists_from_sidecar(self, tmp_path):
        """N4: an existing cutout (``force=False``) returns ``missing_sheets``
        and ``off_grid_sheets`` from its OWN sidecar, not empty tuples - with
        no network and no sheet selection."""
        from kartograf import download_pl_cutout

        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
        cut.target_path.parent.mkdir(parents=True)
        cut.target_path.write_bytes(b"II*\x00")
        cut.target_path.with_name(cut.target_path.name + ".meta.json").write_text(
            json.dumps(
                {
                    "extra": {
                        "missing_sheets": ["N-34-130-D-d-2-4"],
                        "off_grid_sheets": ["N-34-130-D-d-2-3"],
                    }
                }
            )
        )
        provider = self._provider()
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch("kartograf.download.cutout.find_sheets_for_bbox") as find,
        ):
            result = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)

        assert result.skipped and result.path == cut.target_path
        assert result.missing_sheets == ("N-34-130-D-d-2-4",)
        assert result.off_grid_sheets == ("N-34-130-D-d-2-3",)
        assert result.sheet_paths == ()
        assert provider.calls == [] and not find.called

    @pytest.mark.parametrize(
        ("attr", "value"), [("vertical_crs", "KRON86"), ("resolution", "5m")]
    )
    def test_run_rejects_provider_not_matching_cutout(self, tmp_path, attr, value):
        """A provider inconsistent with the cutout would poison the shared sheet cache.

        The sheet segment and the cutout sidecar take the vertical/resolution
        from the cutout, and the data from the provider: KRON86 (or 5 m) sheets
        would land in the ``pl_1992_1m_evrf2007`` segment and later EVRF2007 1m
        runs would reuse them without warning. The error comes BEFORE the
        download and before the directories.
        """
        from kartograf.download.cutout import PlCutoutSheets, run_pl_cutout
        from kartograf.exceptions import ValidationError

        provider = self._provider()
        setattr(provider, attr, value)
        cut = prepare_pl_cutout(_BBOX_2180, "EPSG:2180", output_dir=tmp_path)
        sheets = PlCutoutSheets(godla=tuple(self._SHEETS))

        with pytest.raises(ValidationError, match=value):
            run_pl_cutout(cut, sheets, provider=provider)

        assert provider.calls == []
        assert not (tmp_path / "nmt").exists()

    def test_public_exports(self):
        import kartograf

        for name in (
            "PlCutout",
            "PlCutoutResult",
            "PlCutoutSheets",
            "GridMismatchError",
            "download_pl_cutout",
            "prepare_pl_cutout",
            "run_pl_cutout",
            "select_pl_cutout_sheets",
        ):
            assert name in kartograf.__all__ and hasattr(kartograf, name)

    def test_sidecar_failure_does_not_break_cutout(self, tmp_path, caplog):
        """D7: a cutout sidecar build error = a warning, the cutout stays."""
        import logging

        from kartograf import download_pl_cutout

        provider = self._provider()
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
            patch(
                "kartograf.sources.sidecar.build_metadata",
                side_effect=RuntimeError("zepsuty deskryptor"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            result = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)

        assert result.path.exists()
        assert not result.path.with_name(result.path.name + ".meta.json").exists()
        assert "zepsuty deskryptor" in caplog.text

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"target_crs": "EPSG:4326"},
            {"resolution": "2m"},
            {"resolution": "5m", "vertical_crs": "KRON86"},
            {"vertical_crs": "Bpv"},
        ],
    )
    def test_prepare_rejects_bad_params(self, tmp_path, kwargs):
        from kartograf.download.cutout import prepare_pl_cutout
        from kartograf.exceptions import ValidationError

        params = {"target_crs": "EPSG:2180", **kwargs}
        target = params.pop("target_crs")
        with pytest.raises(ValidationError):
            prepare_pl_cutout(_BBOX_2180, target, output_dir=tmp_path, **params)


class TestMissingSheets:
    """R5: no GUGiK data = nodata + warning; a download failure = error."""

    def _provider(self, *, no_coverage=(), broken=()):
        from kartograf.exceptions import NoCoverageError

        provider = Mock()
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "1m"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        provider.default_extension = ".asc"

        def download(godlo, path, timeout=30):
            if godlo in no_coverage:
                raise NoCoverageError(
                    f"No NMT 1m data available for {godlo}", godlo=godlo
                )
            if godlo in broken:
                raise DownloadError(f"timeout {godlo}", godlo=godlo)
            west, south = TestLibraryApi._SHEETS[godlo]
            return _write_sheet_asc(path, west, south)

        provider.download = download
        return provider

    def _cutout(self, tmp_path):
        from kartograf.download.cutout import PlCutoutSheets, prepare_pl_cutout

        cut = prepare_pl_cutout(
            BBox(530010, 382010, 530190, 382090, "EPSG:2180"),
            "EPSG:2180",
            output_dir=tmp_path,
        )
        return cut, PlCutoutSheets(godla=tuple(TestLibraryApi._SHEETS))

    def test_no_coverage_sheet_becomes_nodata_with_record(self, tmp_path):
        from kartograf.download.cutout import run_pl_cutout

        cut, sheets = self._cutout(tmp_path)
        result = run_pl_cutout(
            cut, sheets, provider=self._provider(no_coverage={"N-34-130-D-d-2-4"})
        )
        assert result.missing_sheets == ("N-34-130-D-d-2-4",)
        with rasterio.open(result.path) as ds:
            data = ds.read(1)
        assert (data[:, -50:] == _NODATA).all() and (data[:, :50] != _NODATA).all()
        meta = json.loads(
            result.path.with_name(result.path.name + ".meta.json").read_text()
        )
        assert meta["extra"]["missing_sheets"] == ["N-34-130-D-d-2-4"]

    def test_skipped_run_reads_missing_sheets_from_sidecar(self, tmp_path):
        """N4: the second run without ``force`` -> ``skipped`` with the list of
        missing sheets from the sidecar (previously empty ``()``); no sidecar -
        empty."""
        from kartograf.download.cutout import run_pl_cutout

        cut, sheets = self._cutout(tmp_path)
        first = run_pl_cutout(
            cut, sheets, provider=self._provider(no_coverage={"N-34-130-D-d-2-4"})
        )
        assert first.missing_sheets == ("N-34-130-D-d-2-4",)

        untouched = self._provider()
        untouched.download = Mock(side_effect=AssertionError("pobranie przy skipie"))
        again = run_pl_cutout(cut, sheets, provider=untouched)
        assert again.skipped and again.path == first.path
        assert again.missing_sheets == ("N-34-130-D-d-2-4",)
        assert again.off_grid_sheets == () and again.sheet_paths == ()

        first.path.with_name(first.path.name + ".meta.json").unlink()
        without_sidecar = run_pl_cutout(cut, sheets, provider=untouched)
        assert without_sidecar.skipped and without_sidecar.missing_sheets == ()

    def test_sidecar_lists_sheet_sources_from_sheet_sidecars(self, tmp_path):
        """P5/D5: ``extra.sheet_sources`` = the origin of each mosaic sheet
        from its sidecar; a sheet from the pre-0.7.0 cache (no sidecar) has
        ``null`` fields except the sheet code, and so does a sheet with a
        sidecar without ``source``."""
        from kartograf.download.cutout import run_pl_cutout

        sources = {
            "N-34-130-D-d-2-3": {
                "url": "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/1/1_a.asc",
                "index_url": "https://mapy.geoportal.gov.pl/.../SkorowidzeUkladEVRF2007",
                "layer": "SkorowidzeNMT2025",
                "sheet": "N-34-130-D-d-2-3",
                "acquisition_date": "2025-04-01",
                "resolution_m": 1.0,
                "full_sheet": True,
            },
            "N-34-130-D-d-2-4": {
                "url": "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/2/2_b.asc",
                "index_url": "https://mapy.geoportal.gov.pl/.../SkorowidzeUkladEVRF2007",
                "layer": "SkorowidzeNMT2023iStarsze",
                "sheet": "N-34-130-D-d-2-4",
                "acquisition_date": "2022-05-09",
                "resolution_m": 1.0,
                "full_sheet": False,
            },
        }
        provider = self._provider()
        provider.source_info = lambda godlo: sources.get(godlo)
        downloads = []
        download = provider.download

        def counting_download(godlo, path, timeout=30):
            downloads.append(godlo)
            return download(godlo, path, timeout)

        provider.download = counting_download
        cut, sheets = self._cutout(tmp_path)
        result = run_pl_cutout(cut, sheets, provider=provider)
        meta = json.loads(
            result.path.with_name(result.path.name + ".meta.json").read_text()
        )
        by_godlo = {entry["sheet"]: entry for entry in meta["extra"]["sheet_sources"]}
        assert by_godlo == {
            "N-34-130-D-d-2-3": {
                "sheet": "N-34-130-D-d-2-3",
                "url": sources["N-34-130-D-d-2-3"]["url"],
                "layer": "SkorowidzeNMT2025",
                "acquisition_date": "2025-04-01",
                "full_sheet": True,
            },
            "N-34-130-D-d-2-4": {
                "sheet": "N-34-130-D-d-2-4",
                "url": sources["N-34-130-D-d-2-4"]["url"],
                "layer": "SkorowidzeNMT2023iStarsze",
                "acquisition_date": "2022-05-09",
                "full_sheet": False,
            },
        }
        # E13: a partial sheet is visible in the library result too
        assert result.partial_sheets == ("N-34-130-D-d-2-4",)
        assert sorted(downloads) == sorted(TestLibraryApi._SHEETS)

        # rebuild from cached sheets: one without a sidecar, the other without source
        result.path.unlink()
        sheet_a, sheet_b = sorted(result.sheet_paths)
        sheet_a.with_name(sheet_a.name + ".meta.json").unlink()
        sidecar_b = sheet_b.with_name(sheet_b.name + ".meta.json")
        payload_b = json.loads(sidecar_b.read_text())
        payload_b["extra"] = {}
        sidecar_b.write_text(json.dumps(payload_b))
        rebuilt = run_pl_cutout(cut, sheets, provider=provider)
        meta = json.loads(
            rebuilt.path.with_name(rebuilt.path.name + ".meta.json").read_text()
        )
        assert sorted(meta["extra"]["sheet_sources"], key=lambda e: e["sheet"]) == [
            {
                "sheet": sheet_a.stem,
                "url": None,
                "layer": None,
                "acquisition_date": None,
                "full_sheet": None,
            },
            {
                "sheet": sheet_b.stem,
                "url": None,
                "layer": None,
                "acquisition_date": None,
                "full_sheet": None,
            },
        ]
        assert rebuilt.partial_sheets == ()
        assert len(downloads) == 2  # rebuild without downloading (sheets from cache)

    def test_transport_failure_stays_fatal(self, tmp_path):
        from kartograf.download.cutout import run_pl_cutout

        cut, sheets = self._cutout(tmp_path)
        with pytest.raises(DownloadError, match="N-34-130-D-d-2-4"):
            run_pl_cutout(
                cut, sheets, provider=self._provider(broken={"N-34-130-D-d-2-4"})
            )
        assert not cut.target_path.exists()

    def test_all_sheets_without_data_is_an_error(self, tmp_path):
        from kartograf.download.cutout import run_pl_cutout
        from kartograf.exceptions import ValidationError

        cut, sheets = self._cutout(tmp_path)
        with pytest.raises(ValidationError, match="nie ma danych"):
            run_pl_cutout(
                cut,
                sheets,
                provider=self._provider(no_coverage=set(TestLibraryApi._SHEETS)),
            )
        assert not cut.target_path.exists()

    def test_cutout_entirely_nodata_warns_and_flags_result(self, tmp_path, caplog):
        """N2: sheets downloaded, but without a single valid pixel in the request.

        The file IS CREATED (a correct "no data" result), ``all_nodata=True``
        and ``logger.warning`` - zero pixels with sheets present is NOT a
        ``ValidationError`` (zero sheets). Control: a cutout with data ->
        ``all_nodata=False``.
        """
        import logging

        from kartograf.download.cutout import run_pl_cutout

        provider = self._provider()
        provider.download = lambda godlo, path, timeout=30: _write_sheet_asc(
            path, *TestLibraryApi._SHEETS[godlo], fill=_NODATA
        )
        cut, sheets = self._cutout(tmp_path)
        with caplog.at_level(logging.WARNING, logger="kartograf.download.cutout"):
            result = run_pl_cutout(cut, sheets, provider=provider)

        assert result.all_nodata is True
        assert result.path.exists() and result.missing_sheets == ()
        assert any("w calosci nodata" in r.message for r in caplog.records)
        with rasterio.open(result.path) as ds:
            assert (ds.read(1) == _NODATA).all()

        control = run_pl_cutout(
            self._cutout(tmp_path)[0], sheets, provider=self._provider(), force=True
        )
        assert control.all_nodata is False

    def test_failed_build_leaves_no_empty_bbox_dir(self, tmp_path):
        """Finding 10: a failed build with no previous result leaves no empty bbox/."""
        from kartograf.download.cutout import run_pl_cutout

        cut, sheets = self._cutout(tmp_path)
        with (
            patch(
                "kartograf.transport.mosaic.mosaic_and_crop",
                side_effect=RuntimeError("zepsuty arkusz"),
            ),
            pytest.raises(RuntimeError),
        ):
            run_pl_cutout(cut, sheets, provider=self._provider())
        assert not cut.target_path.parent.exists()
        assert cut.target_path.parent.parent.exists()  # the sheet segment stays


class TestOffGridSheets:
    """S5 (D3/D8): sheets with different pixel grid phases.

    Headers as in L1 (5 m, 2022 campaign): ``xllcorner 535807.22`` (phase
    0.444) and ``538045.16`` (phase 0.032) -> the eastern sheet lies 0.412 px
    west of the western sheet's grid; a common ``yllcorner`` (the offset is in x only).
    """

    _GODLA = ("M-34-76-A-a-1-1", "M-34-76-A-a-1-2")
    # request on the seam (sheets: 535807..538107 and 538045..538545 x 232508..233008)
    _BBOX = BBox(537800, 232600, 538300, 232900, "EPSG:2180")

    @staticmethod
    def _write_asc_5m(path, xll, ncols, value, fmt="{:.3f}"):
        header = (
            f"ncols {ncols}\nnrows 100\nxllcorner {xll}\nyllcorner 232508.63\n"
            "cellsize 5\nNODATA_value -9999\n"
        )
        row = " ".join(fmt.format(value) for _ in range(ncols))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header + "\n".join([row] * 100) + "\n", encoding="ascii")
        return path

    def _provider(self, tmp_path, *, east_xll=538045.16, east_fmt="{:.3f}"):
        """5 m provider writing the western sheet (100.25) and the eastern (200)."""
        provider = Mock()
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "5m"
        provider.descriptor_key = "pl.gugik.nmt_5m"
        provider.default_extension = ".asc"

        def download(godlo, path, timeout=30):
            if godlo == self._GODLA[0]:
                return self._write_asc_5m(path, 535807.22, 460, 100.25)
            return self._write_asc_5m(path, east_xll, 100, 200.0, east_fmt)

        provider.download = download
        return provider

    def _cutout(self, tmp_path, target_crs):
        from kartograf.download.cutout import PlCutoutSheets

        cut = prepare_pl_cutout(
            self._BBOX,
            target_crs,
            output_dir=tmp_path,
            resolution="5m",
            vertical_crs="EVRF2007",
        )
        return cut, PlCutoutSheets(godla=self._GODLA)

    def test_target_2180_off_grid_sheets_is_an_error(self, tmp_path):
        """D3: EPSG:2180 (values 1:1) from sheets with different phases = an error
        with a hint for another --target-crs; no result file, no ``bbox/``,
        the sheets stay in the cache."""
        from kartograf.download.cutout import run_pl_cutout
        from kartograf.download.storage import FileStorage
        from kartograf.exceptions import GridMismatchError, ValidationError

        cut, sheets = self._cutout(tmp_path, "EPSG:2180")
        with pytest.raises(GridMismatchError, match=r"--target-crs EPSG:5514") as e:
            run_pl_cutout(cut, sheets, provider=self._provider(tmp_path))

        message = str(e.value)
        assert "1 z 2 arkuszy" in message and "0.412 px" in message
        assert "M-34-76-A-a-1-2.asc" in message and "EPSG:3045" in message
        assert isinstance(e.value, ValidationError)
        assert [s.path.stem for s in e.value.off_grid] == ["M-34-76-A-a-1-2"]
        assert e.value.off_grid[0].dx_px == pytest.approx(-0.412)
        assert not cut.target_path.exists()
        assert not cut.target_path.parent.exists()  # bbox/ cleaned up
        storage = FileStorage(tmp_path, resolution="5m", vertical_crs="EVRF2007")
        assert all(storage.get_path(g, ".asc").exists() for g in self._GODLA)

    def test_cli_target_2180_off_grid_returns_1_with_hint(self, tmp_path, capsys):
        west = self._write_asc_5m(tmp_path / "M-34-76-A-a-1-1.asc", 535807.22, 460, 100)
        east = self._write_asc_5m(tmp_path / "M-34-76-A-a-1-2.asc", 538045.16, 100, 200)
        rc, *_ = TestDownloadPlBboxCutout()._run(
            tmp_path, _pl_args(tmp_path), [west, east]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert err.startswith("Error: 1 z 2 arkuszy")
        assert "--target-crs EPSG:5514" in err and "Arkusze zostaja w cache" in err

    def test_cli_target_5514_off_grid_prints_info(self, tmp_path, capsys):
        """W1 in the CLI: other-phase sheets = Info: (stderr), code 0, file made."""
        west = self._write_asc_5m(tmp_path / "M-34-76-A-a-1-1.asc", 535807.22, 460, 100)
        east = self._write_asc_5m(tmp_path / "M-34-76-A-a-1-2.asc", 538045.16, 100, 200)
        args = _pl_args(tmp_path, target_crs="EPSG:5514", resolution="5m")
        rc, *_ = TestDownloadPlBboxCutout()._run(
            tmp_path, args, [west, east], bbox=self._BBOX
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "Info: 1 arkuszy o innej fazie siatki przeprobkowanych osobno (W1" in err
        assert "extra.off_grid_sheets" in err
        assert "Warning:" not in err

    def test_target_5514_warps_each_off_grid_sheet_separately(self, tmp_path):
        """D8 (W1): a warp from sheets with different phases - each sheet from
        its own grid straight to the result grid. The result has EXACTLY two
        levels (100.25 and 200): no mixture on the seam, no nodata; in the
        overlap the first in sort order wins (western, up to 538107); the
        eastern sheet with integers only (Int32) does not truncate the western
        one. Without the fix the intermediate ``merge`` mosaic left a nodata
        column on the seam, and bilinear smeared it into ~70 intermediate
        values."""
        from kartograf.download.cutout import run_pl_cutout

        cut, sheets = self._cutout(tmp_path, "EPSG:5514")
        result = run_pl_cutout(
            cut, sheets, provider=self._provider(tmp_path, east_fmt="{:.0f}")
        )

        assert result.off_grid_sheets == ("M-34-76-A-a-1-2",)
        with rasterio.open(result.path) as ds:
            assert ds.crs.to_epsg() == 5514
            data = ds.read(1)
            west_px = ds.index(
                *(float(v) for v in cut.pinned.transform(538100, 232750))
            )
            east_px = ds.index(
                *(float(v) for v in cut.pinned.transform(538115, 232750))
            )
        assert not (data == _NODATA).any()
        assert set(np.unique(np.round(data, 3)).tolist()) == {100.25, 200.0}
        assert data[west_px] == pytest.approx(100.25) and data[east_px] == 200.0
        meta = json.loads(
            result.path.with_name(result.path.name + ".meta.json").read_text()
        )
        assert meta["extra"]["off_grid_sheets"] == ["M-34-76-A-a-1-2"]
        assert list(result.path.parent.glob("*.mosaic.tif")) == []

    def test_single_phase_sheets_keep_mosaic_path(self, tmp_path):
        """Sheets on one phase: the existing path (1:1 mosaic + warp from an
        intermediate file), without ``off_grid_sheets`` in the result and sidecar."""
        from kartograf.download.cutout import run_pl_cutout
        from kartograf.transform import raster as raster_mod
        from kartograf.transport import mosaic as mosaic_mod

        cut, sheets = self._cutout(tmp_path, "EPSG:5514")
        with (
            patch.object(
                mosaic_mod, "mosaic_and_crop", wraps=mosaic_mod.mosaic_and_crop
            ) as mosaic,
            patch.object(
                raster_mod, "warp_to_grid", wraps=raster_mod.warp_to_grid
            ) as warp,
        ):
            # the eastern one 10 px west of the western one's end, same phase (0,444)
            result = run_pl_cutout(
                cut, sheets, provider=self._provider(tmp_path, east_xll=538057.22)
            )

        assert result.off_grid_sheets == ()
        mosaic.assert_called_once()
        assert warp.call_args.args[0].name.endswith(".mosaic.tif")
        meta = json.loads(
            result.path.with_name(result.path.name + ".meta.json").read_text()
        )
        assert "off_grid_sheets" not in meta["extra"]
        with rasterio.open(result.path) as ds:
            data = ds.read(1)
        assert not (data == _NODATA).any()
        # mosaic + warp: the interpolator sees the neighbour across the seam, so
        # there are intermediate values on the seam - but only between the two levels
        assert data.min() == pytest.approx(100.25) and data.max() == 200.0


def _write_sheet_source(sheet, *, full_sheet, godlo=None, url=None):
    """Sheet sidecar with ``extra.source`` as after a download by the manager."""
    godlo = godlo or sheet.stem
    payload = {
        "request": {"sheet": godlo},
        "extra": {
            "source": {
                "url": url or f"https://opendata.geoportal.gov.pl/NMT/1/1_{godlo}.asc",
                "layer": "SkorowidzeNMT2025",
                "acquisition_date": "2025-10-21",
                "full_sheet": full_sheet,
            }
        },
    }
    sheet.with_name(sheet.name + ".meta.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


class TestPartialSheetVisibility:
    """E13 (E2E-B C14-b, C12-a): a partial newest campaign is visible.

    The ADR-028 selection rule is unchanged (the newest campaign) - this is
    only about visibility: ``full_sheet`` in ``extra.sheet_sources``,
    ``Warning:`` and the text of the empty-cutout warning.
    """

    _run = TestDownloadPlBboxCutout._run

    def _sheets(self, tmp_path, *, fill=100.0, full=(True, False)):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000, fill=fill),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000, fill=fill),
        ]
        for sheet, godlo, full_sheet in zip(
            sheets, ("N-34-139-C-a-3-2", "N-34-139-C-a-3-1"), full, strict=True
        ):
            _write_sheet_source(sheet, full_sheet=full_sheet, godlo=godlo)
        return sheets

    def test_sheet_sources_carry_full_sheet(self, tmp_path):
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), self._sheets(tmp_path))

        assert rc == 0
        (tif,) = (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        meta = json.loads(tif.with_name(tif.name + ".meta.json").read_text("utf-8"))
        flags = {s["sheet"]: s["full_sheet"] for s in meta["extra"]["sheet_sources"]}
        assert flags == {"N-34-139-C-a-3-2": True, "N-34-139-C-a-3-1": False}

    def test_partial_sheet_warns(self, tmp_path, capsys):
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), self._sheets(tmp_path))

        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning:" in err and "niepelna" in err
        assert "N-34-139-C-a-3-1" in err and "N-34-139-C-a-3-2" not in err

    def test_skipped_cutout_repeats_partial_warning(self, tmp_path, capsys):
        """A skipped cutout restores ``partial_sheets`` from ``extra.sheet_sources``."""
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), self._sheets(tmp_path))
        assert rc == 0
        capsys.readouterr()

        rc, manager, _ = self._run(tmp_path, _pl_args(tmp_path), sheets=[])

        assert rc == 0
        manager.download_sheets.assert_not_called()
        err = capsys.readouterr().err
        assert "niepelna" in err and "N-34-139-C-a-3-1" in err

    def test_skip_with_pre_adr031_cutout_sidecar_is_no_information(
        self, tmp_path, capsys
    ):
        """ADR-031: ``sheet_sources`` with Polish keys (``godlo``) carry no
        usable sheet name — skip treats them as no information, no error."""
        from kartograf.download.cutout import skipped_pl_cutout

        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), self._sheets(tmp_path))
        assert rc == 0
        (tif,) = (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        sidecar = tif.with_name(tif.name + ".meta.json")
        meta = json.loads(sidecar.read_text("utf-8"))
        meta["extra"]["sheet_sources"] = [
            {
                "godlo": s["sheet"],
                "url": s["url"],
                "layer": s["layer"],
                "aktualnosc": s["acquisition_date"],
                "full_sheet": s["full_sheet"],
            }
            for s in meta["extra"]["sheet_sources"]
        ]
        sidecar.write_text(json.dumps(meta), encoding="utf-8")
        capsys.readouterr()

        cutout = prepare_pl_cutout(_BBOX_2180, "EPSG:2180", output_dir=tmp_path)
        assert skipped_pl_cutout(cutout).partial_sheets == ()
        rc, manager, _ = self._run(tmp_path, _pl_args(tmp_path), sheets=[])
        assert rc == 0
        manager.download_sheets.assert_not_called()
        assert "niepelna" not in capsys.readouterr().err

    def test_pre_adr031_sheet_sidecar_gives_null_fields(self, tmp_path):
        """Sheet sidecar with Polish keys: ``sheet`` from the file name,
        renamed fields null, unchanged ones (``url``) kept."""
        from kartograf.download.cutout import _sheet_source

        sheet = _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)
        sheet.with_name(sheet.name + ".meta.json").write_text(
            json.dumps(
                {
                    "request": {"godlo": "N-34-139-C-a-3-2"},
                    "extra": {
                        "source": {
                            "url": "https://example.invalid/s1.asc",
                            "aktualnosc": "2025-10-21",
                            "godlo": "N-34-139-C-a-3-2",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        assert _sheet_source(sheet) == {
            "sheet": "s1",
            "url": "https://example.invalid/s1.asc",
            "layer": None,
            "acquisition_date": None,
            "full_sheet": None,
        }

    def test_full_sheets_do_not_warn(self, tmp_path, capsys):
        sheets = self._sheets(tmp_path, full=(True, True))
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        assert "niepelna" not in capsys.readouterr().err

    def test_all_nodata_with_partial_sheet_blames_campaign(self, tmp_path, capsys):
        """C14-b: an empty cutout from a partial campaign - not "no GUGiK data"."""
        sheets = self._sheets(tmp_path, fill=_NODATA)
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning: wycinek w calosci nodata" in err
        assert "niepelna" in err and "N-34-139-C-a-3-1" in err
        assert "brak danych GUGiK / obszar poza pokryciem" not in err


class TestEmptyCutoutSkip:
    """E15 (E2E-B C17c): an empty cutout recorded in the sidecar, skip warns."""

    _run = TestDownloadPlBboxCutout._run

    def _empty_sheets(self, tmp_path):
        return [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000, fill=_NODATA),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000, fill=_NODATA),
        ]

    def test_sidecar_records_all_nodata(self, tmp_path):
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), self._empty_sheets(tmp_path))

        assert rc == 0
        (tif,) = (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        meta = json.loads(tif.with_name(tif.name + ".meta.json").read_text("utf-8"))
        assert meta["extra"]["all_nodata"] is True

    def test_sidecar_without_flag_when_cutout_has_data(self, tmp_path):
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        (tif,) = (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        meta = json.loads(tif.with_name(tif.name + ".meta.json").read_text("utf-8"))
        assert "all_nodata" not in meta["extra"]

    def test_skip_repeats_all_nodata_warning(self, tmp_path, capsys):
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), self._empty_sheets(tmp_path))
        assert rc == 0
        capsys.readouterr()

        rc, manager, _ = self._run(tmp_path, _pl_args(tmp_path), sheets=[])

        assert rc == 0
        manager.download_sheets.assert_not_called()
        err = capsys.readouterr().err
        assert "Warning: wycinek w calosci nodata" in err
        assert "(z sidecara istniejacego wycinka)" in err

    def test_library_skip_restores_all_nodata(self, tmp_path):
        from kartograf.download.cutout import skipped_pl_cutout

        self._run(tmp_path, _pl_args(tmp_path), self._empty_sheets(tmp_path))
        cutout = prepare_pl_cutout(_BBOX_2180, "EPSG:2180", output_dir=tmp_path)

        result = skipped_pl_cutout(cutout)

        assert result.skipped and result.all_nodata is True


class TestCutoutOverCampaignLinks:
    """ADR-030 (errata Q4): the cutout reads sheets through campaign links."""

    # Synthetic 100 m sheets inside their godlo frames (B4 extent check):
    # the frames of 2-3 and 2-4 overlap around x = 770000 (EPSG:2180).
    _SHEETS = {
        "N-34-130-D-d-2-3": (769900, 509000),
        "N-34-130-D-d-2-4": (770000, 509000),
    }
    _BBOX = BBox(769910, 509010, 770090, 509090, "EPSG:2180")

    class _CampaignProvider:
        """A fake with the campaign contract (CLASS attribute supports_campaigns)."""

        supports_campaigns = True
        descriptor_key = "pl.gugik.nmt_1m"
        vertical_crs = "EVRF2007"
        resolution = "1m"
        default_extension = ".asc"
        name = "fake"

        def __init__(self, sheets):
            self.sheets = sheets
            self.resolve_calls = []

        def resolve_campaigns(
            self, godlo, *, campaigns="newest", min_year=None, timeout=None
        ):
            from kartograf.providers.pl.skorowidz import SkorowidzRecord

            self.resolve_calls.append(godlo)
            return [
                SkorowidzRecord(
                    url=f"https://opendata.geoportal.gov.pl/NMT/83233/"
                    f"83233_1744736_{godlo}.asc",
                    godlo=godlo,
                    aktualnosc="2025-04-27",
                    dt_pzgik="2025-05-01",
                    layer="SkorowidzeNMT2025",
                    uklad="1992",
                    zone=None,
                    resolution_m=1.0,
                    full_sheet=True,
                    raw={"format": "ARC/INFO ASCII GRID"},
                )
            ]

        def record_source(self, record):
            return record.to_source("https://wms")

        def download_record(self, record, path, timeout=None):
            west, south = self.sheets[record.godlo]
            return _write_sheet_asc(path, west, south)

    def _run(self, tmp_path, provider=None, **kwargs):
        from kartograf import download_pl_cutout

        provider = provider or self._CampaignProvider(self._SHEETS)
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            result = download_pl_cutout(
                self._BBOX, "EPSG:2180", output_dir=tmp_path, **kwargs
            )
        return result, provider

    def test_cutout_builds_from_hardlinked_sheets(self, tmp_path):
        import os

        from kartograf.download.links import linked_campaign

        result, _ = self._run(tmp_path)

        assert result.path.exists() and not result.skipped
        assert len(result.sheet_paths) == 2
        for sheet in result.sheet_paths:
            target = linked_campaign(sheet)
            assert not sheet.is_symlink() and os.path.samefile(sheet, target)
            assert "kampanie/2025-04-27_83233" in str(target)
        with rasterio.open(result.path) as src:
            assert src.count == 1

    def test_cutout_sheet_sources_from_standard_sidecar(self, tmp_path):
        result, _ = self._run(tmp_path)

        meta = json.loads(
            result.path.with_name(result.path.name + ".meta.json").read_text("utf-8")
        )
        sources = meta["extra"]["sheet_sources"]
        assert sorted(s["sheet"] for s in sources) == sorted(self._SHEETS)
        for source in sources:
            assert source["url"] == (
                "https://opendata.geoportal.gov.pl/NMT/83233/"
                f"83233_1744736_{source['sheet']}.asc"
            )

    def test_cutout_skip_still_by_target_existence(self, tmp_path):
        first, provider = self._run(tmp_path)
        calls = len(provider.resolve_calls)
        assert calls == 2

        second, _ = self._run(tmp_path, provider=provider)

        assert second.skipped and second.path == first.path
        assert len(provider.resolve_calls) == calls

    def test_estimate_skips_hardlinked_sheet(self, tmp_path):
        import os

        from kartograf.download.cutout import (
            estimate_pl_cutout_bytes,
            prepare_pl_cutout,
            select_pl_cutout_sheets,
        )
        from kartograf.download.storage import storage_for_provider

        cutout = prepare_pl_cutout(self._BBOX, "EPSG:2180", output_dir=tmp_path)
        with patch(
            "kartograf.download.cutout.find_sheets_for_bbox",
            return_value=list(self._SHEETS),
        ):
            sheets = select_pl_cutout_sheets(cutout)
        storage = storage_for_provider(tmp_path)
        base_need, base_pending = estimate_pl_cutout_bytes(
            cutout, sheets, storage=storage
        )
        assert base_pending == 2

        first, _ = sorted(self._SHEETS)
        real = tmp_path / "kampanie_real" / f"{first}.asc"
        real.parent.mkdir(parents=True)
        real.write_text("x")
        live = storage.get_path(first, ".asc")
        live.parent.mkdir(parents=True, exist_ok=True)
        os.link(real, live)

        need, pending = estimate_pl_cutout_bytes(cutout, sheets, storage=storage)

        assert pending == 1  # the missing sheet is counted, the hardlink is not
        assert need < base_need


class TestUnverifiedSheets:
    """I-1: a cutout when the index fails (local campaign without checking)."""

    _run = TestDownloadPlBboxCutout._run

    def _run_unverified(self, tmp_path):
        from kartograf.download.manager import DownloadResult

        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]

        def make(**kw):
            result = DownloadResult(**kw)
            result.unverified = {"N-1": "HTTP 503"}
            return result

        with patch("kartograf.download.manager.DownloadResult", make):
            rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)
        return rc

    def test_cli_warns_and_sidecar_records(self, tmp_path, capsys):
        rc = self._run_unverified(tmp_path)

        assert rc == 0
        err = capsys.readouterr().err
        assert (
            "Warning: skorowidz GUGiK niedostepny — dla 1 arkuszy uzyto lokalnej "
            "kampanii bez sprawdzenia nowszej (N-1) (HTTP 503)"
        ) in err
        (tif,) = (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        meta = json.loads(tif.with_name(tif.name + ".meta.json").read_text("utf-8"))
        assert meta["extra"]["unverified_sheets"] == {"N-1": "HTTP 503"}

    def test_verified_cutout_has_no_warning_nor_field(self, tmp_path, capsys):
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), sheets)

        assert rc == 0
        assert "skorowidz GUGiK niedostepny" not in capsys.readouterr().err
        (tif,) = (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").glob("*.tif")
        meta = json.loads(tif.with_name(tif.name + ".meta.json").read_text("utf-8"))
        assert "unverified_sheets" not in (meta.get("extra") or {})

    def test_skip_restores_unverified_from_sidecar_and_warns(self, tmp_path, capsys):
        assert self._run_unverified(tmp_path) == 0
        capsys.readouterr()

        rc, manager, _ = self._run(tmp_path, _pl_args(tmp_path), sheets=[])

        assert rc == 0
        manager.download_sheets.assert_not_called()
        err = capsys.readouterr().err
        assert "skorowidz GUGiK niedostepny" in err and "(N-1) (HTTP 503)" in err
        assert "z sidecara istniejacego wycinka" in err

    def test_cutout_error_after_unfinished_progress_starts_new_line(
        self, tmp_path, capsys
    ):
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        args = _pl_args(tmp_path, quiet=False)

        def boom(*a, on_progress=None, **kw):
            on_progress(DownloadProgress(0, 1, "N-1", "downloading", ""))
            raise DownloadError("padl")

        with patch(f"{_CUT}.run_pl_cutout", side_effect=boom):
            rc, *_ = self._run(tmp_path, args, sheets)

        assert rc == 1
        err = capsys.readouterr().err
        assert err.endswith("\nError: padl\n")


class TestBuildFromLocalSheets:
    """A10: mosaic from local files, no network, caller's output path."""

    def test_no_network_and_path_outside_data_tree(self, tmp_path):
        from kartograf.download.cutout import build_cutout_from_sheets

        a = _write_sheet_asc(
            tmp_path / "s" / "N-34-130-D-d-2-3.asc", 500000.0, 600000.0, fill=100.0
        )
        out = tmp_path / "project" / "dem.tif"
        result = build_cutout_from_sheets(
            [a],
            BBox(500010, 600010, 500090, 600090, "EPSG:2180"),
            "EPSG:2180",
            out,
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        assert result.path == out and not result.all_nodata
        assert result.sheet_paths == (a,)
        assert sorted(p.name for p in out.parent.iterdir()) == [
            "dem.tif",
            "dem.tif.meta.json",
        ]

    def test_off_grid_sheets_with_2180_target_raise(self, tmp_path):
        """Grid rule as in download_pl_cutout: no silent resampling (A11 deferred)."""
        from kartograf.download.cutout import build_cutout_from_sheets
        from kartograf.exceptions import GridMismatchError

        a = _write_sheet_asc(tmp_path / "N-34-130-D-d-2-3.asc", 500000.0, 600000.0)
        b = _write_sheet_asc(tmp_path / "N-34-130-D-d-2-4.asc", 500100.5, 600000.0)
        with pytest.raises(GridMismatchError):
            build_cutout_from_sheets(
                [a, b],
                BBox(500010, 600010, 500190, 600090, "EPSG:2180"),
                "EPSG:2180",
                tmp_path / "out" / "c.tif",
                resolution="1m",
                vertical_crs="EVRF2007",
            )

    def test_sidecar_has_sheet_sources_and_checksum(self, tmp_path):
        from kartograf.download.cutout import build_cutout_from_sheets

        a = _write_sheet_asc(
            tmp_path / "s" / "N-34-130-D-d-2-3.asc", 500000.0, 600000.0
        )
        (tmp_path / "s" / "N-34-130-D-d-2-3.asc.meta.json").write_text(
            json.dumps(
                {
                    "request": {"sheet": "N-34-130-D-d-2-3"},
                    "extra": {
                        "source": {
                            "url": "https://example.test/a.asc",
                            "layer": "L",
                            "acquisition_date": "2022-01-01",
                            "full_sheet": False,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        out = tmp_path / "project" / "dem.tif"
        result = build_cutout_from_sheets(
            [a],
            BBox(500010, 600010, 500090, 600090, "EPSG:2180"),
            "EPSG:2180",
            out,
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        meta = json.loads((out.parent / "dem.tif.meta.json").read_text("utf-8"))
        assert meta["dataset"] == "pl.gugik.nmt_1m"
        assert meta["sha256"] and meta["size_bytes"] == out.stat().st_size
        (entry,) = meta["extra"]["sheet_sources"]
        assert entry["sheet"] == "N-34-130-D-d-2-3"
        assert entry["url"] == "https://example.test/a.asc"
        assert result.partial_sheets == ("N-34-130-D-d-2-3",)

    def test_off_grid_sheets_with_warp_target_are_reported(self, tmp_path):
        """Warp target (W1): off-grid sheets are reprojected separately."""
        from kartograf.download.cutout import build_cutout_from_sheets

        a = _write_sheet_asc(tmp_path / "N-34-130-D-d-2-3.asc", 530000.0, 382000.0)
        b = _write_sheet_asc(tmp_path / "N-34-130-D-d-2-4.asc", 530100.5, 382000.0)
        c = _write_sheet_asc(tmp_path / "N-34-130-D-d-2-5.asc", 530200.0, 382000.0)
        out = tmp_path / "out" / "c.tif"
        result = build_cutout_from_sheets(
            [a, b, c],
            BBox(530010, 382010, 530290, 382090, "EPSG:2180"),
            "EPSG:5514",
            out,
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        assert result.off_grid_sheets == ("N-34-130-D-d-2-4",)
        meta = json.loads((out.parent / "c.tif.meta.json").read_text("utf-8"))
        assert meta["extra"]["off_grid_sheets"] == ["N-34-130-D-d-2-4"]
        with rasterio.open(out) as ds:
            assert ds.crs.to_epsg() == 5514

    def test_empty_list_rejected(self, tmp_path):
        from kartograf.download.cutout import build_cutout_from_sheets
        from kartograf.exceptions import ValidationError

        with pytest.raises(ValidationError, match="arkusz"):
            build_cutout_from_sheets(
                [],
                BBox(0, 0, 1, 1, "EPSG:2180"),
                "EPSG:2180",
                tmp_path / "c.tif",
                resolution="1m",
                vertical_crs="EVRF2007",
            )

    def test_exported(self):
        import kartograf

        assert "build_cutout_from_sheets" in kartograf.__all__
