"""Tests of PL WCS cutout preparation and CLI validation (ADR-027/035)."""

from unittest.mock import patch

import pytest

from kartograf.cli.commands import main
from kartograf.core.sheet_parser import BBox
from kartograf.download.cutout import prepare_pl_cutout
from kartograf.transform.crs import TransformUnavailableError


class TestPreparePlCutout:
    def test_target_2180_no_pinned_and_native_name(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox,
            "EPSG:2180",
            output_dir=str(tmp_path),
            vertical_crs="EVRF2007",
            product="nmt",
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
            bbox,
            "EPSG:5514",
            output_dir=str(tmp_path),
            vertical_crs="EVRF2007",
            product="nmt",
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

    def test_source_has_warp_margin_of_four_pixels(self, tmp_path):
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
            vertical_crs="EVRF2007",
            product="nmt",
        )
        back = bbox_to_crs(cut.bbox_target, "EPSG:2180")
        source = cut.bbox_source_2180
        margin = 4.0  # WARP_MARGIN_PX at the fixed 1 m grid
        assert source.min_x == pytest.approx(back.min_x - margin)
        assert source.min_y == pytest.approx(back.min_y - margin)
        assert source.max_x == pytest.approx(back.max_x + margin)
        assert source.max_y == pytest.approx(back.max_y + margin)

    def test_vertical_kron86_lands_in_kron86_segment(self, tmp_path):
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        cut = prepare_pl_cutout(
            bbox,
            "EPSG:2180",
            output_dir=str(tmp_path),
            vertical_crs="KRON86",
            product="nmt",
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
            product="nmt",
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
            product="nmt",
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
            product="nmt",
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
            product="nmt",
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
            vertical_crs="EVRF2007",
            product="nmt",
        )
        b = cut.bbox_target
        coords = [format(v, ".10g") for v in (b.min_x, b.min_y, b.max_x, b.max_y)]
        assert cut.target_path.name == "_".join(coords) + ".tif"
        assert "e+" not in cut.target_path.name

    def test_wgs84_bbox_normalized_to_2180(self, tmp_path):
        bbox = BBox(18.60, 49.75, 18.65, 49.77, "EPSG:4326")
        cut = prepare_pl_cutout(
            bbox,
            "EPSG:2180",
            output_dir=str(tmp_path),
            vertical_crs="EVRF2007",
            product="nmt",
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
                bbox,
                "EPSG:5514",
                output_dir=str(tmp_path),
                vertical_crs="EVRF2007",
                product="nmt",
            )

    def test_public_exports(self):
        import kartograf

        for name in (
            "PlCutout",
            "PlCutoutResult",
            "download_pl_cutout",
            "prepare_pl_cutout",
            "run_pl_wcs_cutout",
        ):
            assert name in kartograf.__all__ and hasattr(kartograf, name)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"target_crs": "EPSG:4326"},
            {"vertical_crs": "Bpv"},
            {"product": "orto"},
        ],
    )
    def test_prepare_rejects_bad_params(self, tmp_path, kwargs):
        from kartograf.exceptions import ValidationError

        params = {
            "target_crs": "EPSG:2180",
            "vertical_crs": "EVRF2007",
            "product": "nmt",
            **kwargs,
        }
        target = params.pop("target_crs")
        with pytest.raises(ValidationError):
            prepare_pl_cutout(
                BBox(530010, 382010, 530190, 382090, "EPSG:2180"),
                target,
                output_dir=tmp_path,
                **params,
            )


class TestTargetCrsValidations:
    """Spec 6.3 through main() - readable errors, code 1."""

    _BBOX = ["--bbox", "530010,382010,530190,382090", "--country", "pl"]

    def test_pl_sheet_rejected(self, tmp_path, capsys):
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
                "--sheet",
                "N-34-130-D-d-2-4",
                "--target-crs",
                "EPSG:2180",
                "-o",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert "--bbox/--geometry" in capsys.readouterr().err

    @pytest.mark.parametrize("product", ["orto", "laz"])
    def test_non_height_product_rejected(self, product, tmp_path, capsys):
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
