"""Testy warp_to_grid — lokalna reprojekcja przypieta operacja (wzorzec ADR-024)."""

import dataclasses
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.transform.crs import (
    TransformError,
    TransformPolicy,
    build_pinned_transform,
)
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


def _write_cone_tif(path, apex, size=300, pixel=1.0, *, hole=None, declare_nodata=True):
    """A cone around the apex in EPSG:2180 (pattern _server_emulator from
    test_cuzk_dmr).

    ``hole`` is a (start, stop) range of rows and columns filled with the
    nodata value; ``declare_nodata=False`` gives a raster that does NOT
    declare the hole in its profile - only such a raster exposes the missing
    ``src_nodata``/``dst_nodata`` in the warp (with declared nodata rasterio
    infers it from the band and the test would be a decoy).
    """
    west = apex[0] - size / 2 * pixel
    north = apex[1] + size / 2 * pixel
    cols, rows = np.meshgrid(np.arange(size), np.arange(size))
    xs = west + (cols + 0.5) * pixel
    ys = north - (rows + 0.5) * pixel
    data = (1000.0 - np.hypot(xs - apex[0], ys - apex[1])).astype("float32")
    if hole is not None:
        start, stop = hole
        data[start:stop, start:stop] = _NODATA
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": size,
        "height": size,
        "crs": CRS.from_string("EPSG:2180"),
        "transform": from_origin(west, north, pixel, pixel),
        "nodata": _NODATA if declare_nodata else None,
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
        # atomic write: no temporary files
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
        # bilinear, not nearest: the DEM is a continuous field, and `nearest` would
        # also undo the point of the nodata test (no interpolation, nothing to poison)
        assert warp.call_args.kwargs["resampling"] == Resampling.bilinear

    def test_nodata_does_not_bleed_into_interpolation(self, tmp_path):
        """A source WITHOUT declared nodata: masking is done by src/dst_nodata.

        A fixture declaring nodata would NOT guard this - rasterio then infers
        `src_nodata` from the band and the result is the same with and without
        the arguments. Such a raster is reachable on the PL path:
        `transport/mosaic.py` writes `nodata` to the profile only when the
        caller supplies a value.
        """
        src = _write_cone_tif(
            tmp_path / "src.tif", _APEX_2180, hole=(100, 140), declare_nodata=False
        )
        with rasterio.open(src) as ds:
            assert ds.nodata is None, "fixtura deklaruje nodata — test bylby atrapa"
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 100, ay - 100, ax + 100, ay + 100, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        with rasterio.open(dst) as ds:
            valid = ds.read(1, masked=True).compressed()
        assert valid.size > 0, "caly wynik zamaskowany — warp nie przeniosl tresci"
        assert valid.min() > 0.0, f"nodata weszlo do interpolacji: min {valid.min()}"

    def test_failed_warp_writes_only_to_temp_file(self, tmp_path):
        """The write is atomic: the target path does not appear during the warp.

        The mere absence of `*.warp.tif` after a successful run does not prove
        it (without a temporary file it is absent too). The proof is the STATE
        AT THE MOMENT OF FAILURE: the target does not exist yet, but the
        temporary file already does.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")
        dst = tmp_path / "dst.tif"
        seen = {}

        def boom(*args, **kwargs):
            seen["dst_exists"] = dst.exists()
            seen["tmp"] = [p.name for p in tmp_path.glob("*.warp.tif")]
            raise RuntimeError("warp przerwany")

        with (
            patch("kartograf.transform.raster.reproject", side_effect=boom),
            pytest.raises(RuntimeError, match="warp przerwany"),
        ):
            warp_to_grid(
                src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA
            )

        assert seen["dst_exists"] is False, "polzapisany raster pod finalna sciezka"
        assert seen["tmp"], "warp nie uzyl pliku tymczasowego"
        assert not dst.exists()
        assert list(tmp_path.glob("*.warp.tif")) == []  # sprzatanie po awarii

    def test_failed_warp_keeps_previous_destination(self, tmp_path):
        """A failed warp LEAVES the previous result untouched.

        The write goes through a temporary file and `os.replace`, so deleting
        the target did not protect against a half-written file - it only
        destroyed the old, correct result. `exists()` alone does not prove it:
        we check the CONTENT.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")
        dst = tmp_path / "dst.tif"
        previous = b"II*\x00stary wynik"
        dst.write_bytes(previous)

        with (
            patch(
                "kartograf.transform.raster.reproject",
                side_effect=RuntimeError("warp przerwany"),
            ),
            pytest.raises(RuntimeError),
        ):
            warp_to_grid(
                src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA
            )

        assert dst.exists(), "awaria warpu skasowala poprzedni wynik"
        assert dst.read_bytes() == previous, "poprzedni wynik zostal nadpisany"
        assert list(tmp_path.glob("*.warp.tif")) == []  # sprzatanie po awarii

    def test_lowercase_crs_is_the_same_pair(self, tmp_path):
        """`epsg:2180` is the same CRS as `EPSG:2180` - a semantic comparison.

        The CRS-pair guard compares CRSs, not strings; a bare `a == b`
        would reject a healthy call with a differently written code.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "epsg:5514")
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 1.0, pinned, src_crs="epsg:2180", nodata=_NODATA)

        assert dst.exists()

    def test_pinned_pair_must_match_src_crs(self, tmp_path):
        """An inconsistent source pair = an error, not a silently wrong result.

        With a forced `COORDINATE_OPERATION` GDAL ignores the declared
        `src_crs` (measured: 2180/4326/3857/32633/5514 give the same result),
        so without this guard the parameter would be dead and give false
        assurance.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX_2180))
        bbox = BBox(ax - 50, ay - 50, ax + 50, ay + 50, "EPSG:5514")
        dst = tmp_path / "dst.tif"

        with pytest.raises(TransformError, match="Niespojna para ukladow"):
            warp_to_grid(
                src, dst, bbox, 1.0, pinned, src_crs="EPSG:4326", nodata=_NODATA
            )

        assert not dst.exists()

    def test_pinned_pair_must_match_bbox_crs(self, tmp_path):
        """An inconsistent target pair (bbox.crs != pinned.dst_crs) = an error."""
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = _pinned_2180_to("EPSG:5514")
        bbox = BBox(
            _APEX_2180[0] - 50,
            _APEX_2180[1] - 50,
            _APEX_2180[0] + 50,
            _APEX_2180[1] + 50,
            "EPSG:2180",
        )
        dst = tmp_path / "dst.tif"

        with pytest.raises(TransformError, match="Niespojna para ukladow"):
            warp_to_grid(
                src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA
            )

        assert not dst.exists()

    def test_guard_skips_unknown_pinned_pair(self, tmp_path):
        """The `src_crs`/`dst_crs` fields are optional - the guard must not fail on
        them.

        When `pinned` does not know its pair, the absence is decided by
        `gdal_operation()` (its own message), not by the guard - even if the
        given `src_crs` differs from the operation's actual source.
        """
        src = _write_cone_tif(tmp_path / "src.tif", _APEX_2180)
        pinned = dataclasses.replace(
            _pinned_2180_to("EPSG:5514"), src_crs=None, dst_crs=None
        )
        bbox = BBox(0.0, 0.0, 100.0, 100.0, "EPSG:5514")

        with pytest.raises(TransformError, match="wymaga znanej pary ukladow"):
            warp_to_grid(
                src,
                tmp_path / "dst.tif",
                bbox,
                1.0,
                pinned,
                src_crs="EPSG:4326",
                nodata=_NODATA,
            )

    def _flat_tif(
        self, path, west, north, value, *, size=100, hole=None, crs="EPSG:2180"
    ):
        data = np.full((size, size), value, dtype="float32")
        if hole is not None:
            r0, r1, c0, c1 = hole
            data[r0:r1, c0:c1] = _NODATA
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=size,
            height=size,
            count=1,
            dtype="float32",
            crs=crs,
            nodata=_NODATA,
            transform=from_origin(west, north, 1.0, 1.0),
        ) as dst:
            dst.write(data, 1)
        return path

    def _grid_for(self, pinned, points):
        """A 5514 target grid around the image of a 2180 bbox (without the R-01
        margin - the corners may be nodata, the tests look at the centre)."""
        xs, ys = zip(*(pinned.transform(x, y) for x, y in points), strict=True)
        return BBox(min(xs) + 5, min(ys) + 5, max(xs) - 5, max(ys) - 5, "EPSG:5514")

    def test_many_sources_first_wins_and_nodata_never_overwrites(self, tmp_path):
        """W1 (S5): a list of sources = each reprojected separately into one band.

        In the overlap the FIRST source of the list wins (as in ``merge``), and
        the nodata of a later source does not erase valid pixels of an earlier
        one - GDAL overwrites valid pixels with the next source (measured
        2026-09-29), hence the list goes from the end.
        """
        # a: x 0..100, b: x 90..190 (zakladka 10 m); dziura w b w strefie zakladki
        a = self._flat_tif(tmp_path / "a.tif", 530000, 382100, 100.0)
        b = self._flat_tif(
            tmp_path / "b.tif", 530090, 382100, 200.0, hole=(40, 60, 0, 10)
        )
        pinned = _pinned_2180_to("EPSG:5514")
        bbox = self._grid_for(
            pinned,
            [(530010, 382010), (530180, 382010), (530010, 382090), (530180, 382090)],
        )
        in_overlap = tuple(float(v) for v in pinned.transform(530095, 382080))
        in_hole = tuple(float(v) for v in pinned.transform(530095, 382050))
        only_b = tuple(float(v) for v in pinned.transform(530150, 382050))

        def probe(order, name):
            dst = tmp_path / name
            warp_to_grid(
                order, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA
            )
            with rasterio.open(dst) as ds:
                data = ds.read(1)
                return {
                    key: float(data[ds.index(*xy)])
                    for key, xy in (
                        ("overlap", in_overlap),
                        ("hole", in_hole),
                        ("only_b", only_b),
                    )
                }

        a_first = probe([a, b], "ab.tif")
        b_first = probe([b, a], "ba.tif")
        assert a_first == {"overlap": 100.0, "hole": 100.0, "only_b": 200.0}
        assert b_first == {"overlap": 200.0, "hole": 100.0, "only_b": 200.0}

    def test_source_without_crs_takes_src_crs(self, tmp_path):
        """A GUGiK ASC sheet has no CRS: ``src_crs`` must apply to the source
        (``reproject`` from a source without a CRS returned only nodata despite
        ``src_crs`` - hence a VRT with a forced SRS over every source)."""

        src = self._flat_tif(tmp_path / "nocrs.tif", 530000, 382100, 7.0, crs=None)
        with rasterio.open(src) as ds:
            assert ds.crs is None, "fixtura ma CRS — test bylby atrapa"
        pinned = _pinned_2180_to("EPSG:5514")
        bbox = self._grid_for(
            pinned,
            [(530010, 382010), (530090, 382010), (530010, 382090), (530090, 382090)],
        )
        dst = tmp_path / "dst.tif"

        warp_to_grid(src, dst, bbox, 1.0, pinned, src_crs="EPSG:2180", nodata=_NODATA)

        with rasterio.open(dst) as ds:
            data = ds.read(1)
        assert (data == 7.0).all()

    def test_empty_source_list_is_an_error(self, tmp_path):
        from kartograf.exceptions import ValidationError

        pinned = _pinned_2180_to("EPSG:5514")
        with pytest.raises(ValidationError, match="brak rastrow"):
            warp_to_grid(
                [],
                tmp_path / "dst.tif",
                BBox(0.0, 0.0, 10.0, 10.0, "EPSG:5514"),
                1.0,
                pinned,
                src_crs="EPSG:2180",
                nodata=_NODATA,
            )
        assert not (tmp_path / "dst.tif").exists()
