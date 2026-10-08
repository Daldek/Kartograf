"""Testy kartograf.core.bbox — BBox, validate_bbox, transform_bbox, is_czech_crs."""

import math
from unittest.mock import patch

import numpy as np
import pytest
from pyproj import Transformer

from kartograf.core import bbox as bbox_mod
from kartograf.core.bbox import BBox, is_czech_crs, transform_bbox, validate_bbox
from kartograf.exceptions import ValidationError


@pytest.fixture(autouse=True)
def _fresh_cache():
    bbox_mod._transformer.cache_clear()
    bbox_mod._same_crs.cache_clear()
    yield
    bbox_mod._transformer.cache_clear()
    bbox_mod._same_crs.cache_clear()


class TestBBoxImportPaths:
    """Hydrograf importuje BBox z trzech sciezek — wszystkie to ta sama klasa."""

    def test_all_import_paths_are_the_same_class(self):
        import kartograf
        from kartograf.core import geometry, sheet_parser

        assert kartograf.BBox is BBox
        assert sheet_parser.BBox is BBox
        assert geometry.BBox is BBox

    def test_shape_unchanged(self):
        assert BBox._fields == ("min_x", "min_y", "max_x", "max_y", "crs")


class TestTransformBBoxIdentity:
    def test_same_label_after_normalization_is_not_transformed(self):
        src = BBox(1.5, 2.5, 3.5, 4.5, "epsg:2180")
        with patch.object(bbox_mod, "_transformer") as made:
            out = transform_bbox(src, "EPSG:2180")
        made.assert_not_called()
        assert out == BBox(1.5, 2.5, 3.5, 4.5, "EPSG:2180")

    def test_wkt_of_same_crs_is_identity(self):
        from pyproj import CRS

        wkt = CRS.from_epsg(2180).to_wkt()
        out = transform_bbox(BBox(1.0, 2.0, 3.0, 4.0, wkt), "EPSG:2180")
        assert out == BBox(1.0, 2.0, 3.0, 4.0, "EPSG:2180")


class TestTransformBBoxDense:
    def test_4326_to_2180_keeps_southern_band_at_central_meridian(self):
        """Rownoleznik ma minimum y na 19E — 4 narozniki dawaly 237447,4 (479 m)."""
        out = transform_bbox(BBox(18.0, 50.0, 20.0, 50.2, "EPSG:4326"), "EPSG:2180")
        assert out.min_y == pytest.approx(236968.4, abs=0.5)
        assert out.crs == "EPSG:2180"

    def test_2180_to_4326_keeps_northern_band_at_central_meridian(self):
        """Linia stalego y ma maksimum szerokosci na x=500000 (19E)."""
        out = transform_bbox(
            BBox(475000, 600000, 525000, 610000, "EPSG:2180"), "EPSG:4326"
        )
        assert out.max_y == pytest.approx(53.3551052, abs=1e-7)

    def test_transformer_is_built_once_per_pair(self):
        with patch.object(Transformer, "from_crs", wraps=Transformer.from_crs) as made:
            for _ in range(200):
                transform_bbox(BBox(18.0, 50.0, 18.1, 50.1, "EPSG:4326"), "EPSG:2180")
        assert made.call_count == 1


class TestTransformBBoxDuck:
    def test_object_with_transform_gets_84_points_and_returns_envelope(self):
        seen = {}

        class Shift:
            def transform(self, xs, ys):
                seen["xs"], seen["ys"] = xs, ys
                return xs + 10.0, ys - 5.0

        out = transform_bbox(BBox(0.0, 0.0, 2.0, 4.0, "A"), "B", transformer=Shift())
        assert isinstance(seen["xs"], np.ndarray)
        assert len(seen["xs"]) == len(seen["ys"]) == 84
        assert out == BBox(10.0, -5.0, 12.0, -1.0, "B")

    def test_pinned_transform_passes(self):
        """PinnedTransform (ADR-024) works through duck typing; the envelope
        covers the images of all corners (Krovak is rotated)."""
        from kartograf.transform.crs import TransformPolicy, build_pinned_transform

        src = BBox(-447000, -1114000, -440000, -1110000, "EPSG:5514")
        pinned = build_pinned_transform(
            "EPSG:5514",
            "EPSG:2180",
            TransformPolicy(probe_point=(-443500, -1112000), allow_network_grids=False),
        )
        out = transform_bbox(src, "EPSG:2180", transformer=pinned)
        xs, ys = pinned.transform(
            np.array([src.min_x, src.min_x, src.max_x, src.max_x]),
            np.array([src.min_y, src.max_y, src.min_y, src.max_y]),
        )
        assert out.crs == "EPSG:2180"
        assert out.min_x <= xs.min() and out.max_x >= xs.max()
        assert out.min_y <= ys.min() and out.max_y >= ys.max()


class TestValidateBBox:
    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    @pytest.mark.parametrize("pos", range(4))
    def test_non_finite_rejected(self, bad, pos):
        coords = [1.0, 2.0, 3.0, 4.0]
        coords[pos] = bad
        with pytest.raises(ValidationError, match="skonczone"):
            validate_bbox(BBox(*coords, "EPSG:2180"))

    @pytest.mark.parametrize(
        "coords", [(10, 10, 5, 50), (10, 10, 50, 5), (10, 10, 5, 5)]
    )
    def test_inverted_rejected(self, coords):
        with pytest.raises(ValidationError, match="odwrocony"):
            validate_bbox(BBox(*coords, "EPSG:2180"))

    def test_point_allowed(self):
        validate_bbox(BBox(5.0, 5.0, 5.0, 5.0, "EPSG:2180"))

    def test_crs_mismatch_rejected(self):
        with pytest.raises(ValidationError, match="EPSG:4326"):
            validate_bbox(BBox(1, 2, 3, 4, "EPSG:2180"), crs="EPSG:4326")

    def test_crs_label_normalized(self):
        validate_bbox(BBox(1, 2, 3, 4, " epsg:2180"), crs="EPSG:2180")


class TestIsCzechCrs:
    @pytest.mark.parametrize(
        "label",
        ["EPSG:5514", "EPSG:3045", "epsg:5514", " EPSG:5514 ", "5514", "ESRI:5514"],
    )
    def test_czech(self, label):
        assert is_czech_crs(label)

    @pytest.mark.parametrize(
        "label", ["EPSG:2180", "EPSG:4326", "EPSG:55140", "EPSG:51514", "", "FOO:5514"]
    )
    def test_not_czech(self, label):
        assert not is_czech_crs(label)
