"""Testy wycinka PL --target-crs (ADR-027): tresc, walidacje, sidecar, przeplyw."""

import argparse
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest
import rasterio

from kartograf.cli.commands import main
from kartograf.cli.download_cmd import (
    _build_pl_cutout,
    _download_pl_bbox,
    _prepare_pl_cutout,
)
from kartograf.core.sheet_parser import BBox
from kartograf.transform.crs import (
    TransformPolicy,
    TransformUnavailableError,
    build_pinned_transform,
)

_NODATA = -9999.0
_APEX = (530050.0, 382050.0)  # EPSG:2180, okolice Piotrkowa Trybunalskiego


def _write_sheet_asc(path, west, south, size=100, pixel=1.0, apex=None):
    """Syntetyczny 'arkusz' AAIGrid: stozek wokol apex albo plaski 100.0."""
    cols, rows = np.meshgrid(np.arange(size), np.arange(size))
    xs = west + (cols + 0.5) * pixel
    ys = (south + size * pixel) - (rows + 0.5) * pixel
    if apex is None:
        data = np.full((size, size), 100.0, dtype="float32")
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


class TestBuildPlCutout:
    """Spec 8a-c: regresja tresci, mozaika z nodata, crop bez warpa."""

    def test_target_5514_content_lt_1px(self, tmp_path):
        """Mozaika 2 arkuszy + warp: wierzcholek tam, gdzie mowi pyproj."""
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        west = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000, apex=_APEX)
        east = _write_sheet_asc(tmp_path / "b.asc", 530100, 382000, apex=_APEX)
        bbox_2180 = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        pinned = _pinned_2180_to("EPSG:5514")
        ax, ay = (float(v) for v in pinned.transform(*_APEX))
        bbox_target = bbox_to_crs(bbox_2180, "EPSG:5514")
        target = tmp_path / "out" / "cut.tif"

        _build_pl_cutout([west, east], bbox_2180, bbox_target, 1.0, pinned, target)

        with rasterio.open(target) as ds:
            assert ds.crs.to_epsg() == 5514
            data = ds.read(1, masked=True)
            row, col = np.unravel_index(np.argmax(data.filled(-np.inf)), data.shape)
            gx, gy = ds.xy(int(row), int(col))
        assert abs(gx - ax) < 1.0, f"E: {gx} vs {ax}"
        assert abs(gy - ay) < 1.0, f"N: {gy} vs {ay}"
        assert list(target.parent.glob("*.mosaic.tif")) == []  # sprzatanie tmp

    def test_target_5514_full_coverage_from_source_bbox(self, tmp_path):
        """R-01: arkusze z ``bbox_source_2180`` pokrywaja CALA siatke wyniku.

        Obraz prostokata 2180 w Krovaku jest czworokatem obroconym, wiec
        obwiednia celu wystaje poza zadanie — bez zapasu po stronie zrodla
        rogi wyniku byly by nodata.
        """
        args = argparse.Namespace(
            output=str(tmp_path),
            target_crs="EPSG:5514",
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = _prepare_pl_cutout(args, bbox, "EVRF2007")
        sheets = [
            _write_sheet_asc(tmp_path / "a.asc", 529900, 381950, size=200),
            _write_sheet_asc(tmp_path / "b.asc", 530100, 381950, size=200),
        ]

        _build_pl_cutout(
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
        """Mozaika arkuszy z przerwa: pas nodata w wyniku, nigdy zero."""
        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        b = _write_sheet_asc(tmp_path / "b.asc", 530120, 382000)  # 20 m przerwy
        bbox = BBox(530010, 382010, 530210, 382090, "EPSG:2180")
        target = tmp_path / "cut.tif"

        _build_pl_cutout([a, b], bbox, bbox, 1.0, None, target)

        with rasterio.open(target) as ds:
            assert ds.nodata == _NODATA
            data = ds.read(1)
        # przerwa 530100..530120 = kolumny 90..109 (min_x 530010, piksel 1 m)
        assert (data[:, 90:110] == _NODATA).all()
        assert not (data == 0.0).any()

    def test_target_2180_crop_only(self, tmp_path):
        """EPSG:2180: sam crop — GeoTIFF z wpisanym CRS, zasieg = bbox."""
        a = _write_sheet_asc(tmp_path / "a.asc", 530000, 382000)
        bbox = BBox(530010, 382010, 530090, 382090, "EPSG:2180")
        target = tmp_path / "cut.tif"

        _build_pl_cutout([a], bbox, bbox, 1.0, None, target)

        with rasterio.open(target) as ds:
            assert ds.crs is not None and ds.crs.to_epsg() == 2180
            assert ds.bounds == (530010.0, 382010.0, 530090.0, 382090.0)


class TestPreparePlCutout:
    def _args(self, tmp_path, **overrides):
        base = dict(
            output=str(tmp_path),
            target_crs="EPSG:5514",
            resolution="1m",
            vertical_crs="EVRF2007",
        )
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_target_2180_no_pinned_and_native_name(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = _prepare_pl_cutout(
            self._args(tmp_path, target_crs="EPSG:2180"), bbox, "EVRF2007"
        )
        assert cut.pinned is None
        assert cut.bbox_target is cut.bbox_2180
        # bez warpa siatka wyniku rowna sie zadaniu — zapas zbedny (R-01)
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
        cut = _prepare_pl_cutout(self._args(tmp_path), bbox, "EVRF2007")
        assert cut.pinned is not None and cut.pinned.accuracy_m <= 1.0
        assert cut.bbox_target.crs == "EPSG:5514"
        # zrodlo szersze z KAZDEJ strony niz zadanie (R-01: pokrycie siatki)
        source = cut.bbox_source_2180
        assert source.crs == "EPSG:2180"
        assert source.min_x < cut.bbox_2180.min_x
        assert source.min_y < cut.bbox_2180.min_y
        assert source.max_x > cut.bbox_2180.max_x
        assert source.max_y > cut.bbox_2180.max_y
        # nazwa niesie wspolrzedne w ukladzie WYNIKU (Krovak: ujemne)
        assert cut.target_path.name.startswith("-")
        assert cut.target_path.parent == (
            tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        )

    def test_vertical_kron86_lands_in_kron86_segment(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = _prepare_pl_cutout(
            self._args(tmp_path, target_crs="EPSG:2180"), bbox, "KRON86"
        )
        assert "pl_1992_1m_kron86" in cut.target_path.parts

    def test_wgs84_bbox_normalized_to_2180(self, tmp_path):
        bbox = BBox(18.60, 49.75, 18.65, 49.77, "EPSG:4326")
        cut = _prepare_pl_cutout(
            self._args(tmp_path, target_crs="EPSG:2180"), bbox, "EVRF2007"
        )
        assert cut.bbox_2180.crs == "EPSG:2180"
        assert 400000 < cut.bbox_2180.min_x < 700000  # rzad wielkosci 2180

    def test_unavailable_operation_raises_transform_error(self, tmp_path):
        """Fail-fast: brak operacji -> TransformError PRZED siecia (spec 6.3)."""
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch(
                "kartograf.transform.crs.build_pinned_transform",
                side_effect=TransformUnavailableError("brak operacji", remedy="R"),
            ),
            pytest.raises(TransformUnavailableError),
        ):
            _prepare_pl_cutout(self._args(tmp_path), bbox, "EVRF2007")


_DL = "kartograf.cli.download_cmd"


def _pl_args(tmp_path, **overrides):
    """Namespace jak z argparse dla bezposrednich wywolan _download_pl_bbox."""
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


class TestDownloadPlBboxCutout:
    """Spec 8: przeplyw wycinka na poziomie workera PL (mockowane pobranie)."""

    def _run(self, tmp_path, args, sheets, failed=()):
        provider = SimpleNamespace(vertical_crs="EVRF2007")
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch(f"{_DL}.find_sheets_for_bbox", return_value=["N-1", "N-2"]),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(provider, Mock()),
            ),
            patch(f"{_DL}.DownloadManager"),
            patch(
                f"{_DL}._download_godlo_list",
                return_value=(list(sheets), list(failed)),
            ) as dl,
        ):
            rc = _download_pl_bbox(args, bbox, _PARENT)
        return rc, dl

    def test_creates_cutout_and_sidecar(self, tmp_path):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, _ = self._run(tmp_path, _pl_args(tmp_path), sheets)

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
        assert payload["vertical_crs"] == "EPSG:9651"  # EVRF2007-PL, kanal arkuszy
        assert payload["request"]["bbox_crs"] == "EPSG:2180"
        assert payload["extra"]["parent_request"] == _PARENT

    def test_target_5514_sidecar_has_pinned_transform(self, tmp_path):
        sheets = [
            _write_sheet_asc(tmp_path / "s1.asc", 530000, 382000),
            _write_sheet_asc(tmp_path / "s2.asc", 530100, 382000),
        ]
        rc, _ = self._run(tmp_path, _pl_args(tmp_path, target_crs="EPSG:5514"), sheets)

        assert rc == 0
        cut_dir = tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox"
        tifs = list(cut_dir.glob("*.tif"))
        assert len(tifs) == 1
        payload = json.loads((cut_dir / f"{tifs[0].name}.meta.json").read_text("utf-8"))
        assert payload["horizontal_crs"] == "EPSG:5514"
        assert payload["transform"]["horizontal"].startswith("pinned: ")
        assert payload["request"]["bbox_crs"] == "EPSG:5514"

    def test_failed_sheet_returns_1_and_no_cutout(self, tmp_path):
        """Spec 6.1: wycinek wymaga kompletu pokrycia."""
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, _ = self._run(tmp_path, _pl_args(tmp_path), sheets, failed=["N-2"])

        assert rc == 1
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
        rc, dl = self._run(tmp_path, _pl_args(tmp_path), sheets=[])

        assert rc == 0
        dl.assert_not_called()

    def test_without_target_crs_behaviour_unchanged(self, tmp_path):
        """Bez flagi: lista arkuszy jak dotad, zero wycinka (spec 6.1)."""
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, _ = self._run(tmp_path, _pl_args(tmp_path, target_crs=None), sheets)

        assert rc == 0
        assert not (tmp_path / "nmt" / "pl_1992_1m_evrf2007" / "bbox").exists()


class TestTargetCrsValidations:
    """Spec 6.3 przez main() — czytelne bledy, kod 1."""

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
