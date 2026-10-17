"""
Tests for Hydrologic Soil Group (HSG) calculation functionality.

Tests cover USDA texture classification, HSG mapping, and HSGCalculator.
"""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.hydrology.hsg import (
    HSG_DESCRIPTIONS,
    HSG_VALUES,
    TEXTURE_CLASSES,
    TEXTURE_NAMES,
    HSGCalculator,
    classify_usda_texture,
    classify_usda_texture_array,
    hsg_statistics,
    texture_to_hsg,
    texture_to_hsg_array,
)
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.sources.edition import Edition

# Control points of the canonical USDA triangle (Soil Survey Manual):
# 4 points from verification A4-4 + the centres of all 12 classes.
CANONICAL_CONTROL_POINTS = [
    # (clay, sand, silt, expected)
    (0, 70, 30, "sandy_loam"),  # silt + 2*clay = 30 >= 30
    (20, 45, 35, "loam"),  # sand <= 52, silt 28-50
    (35, 45, 20, "clay_loam"),  # sand <= 45 => not sandy_clay
    (12, 75, 13, "sandy_loam"),  # silt + 2*clay = 37 >= 30
    (5, 90, 5, "sand"),
    (5, 80, 15, "loamy_sand"),
    (10, 65, 25, "sandy_loam"),
    (20, 40, 40, "loam"),
    (15, 20, 65, "silt_loam"),
    (5, 5, 90, "silt"),
    (27, 60, 13, "sandy_clay_loam"),
    (33, 33, 34, "clay_loam"),
    (33, 10, 57, "silty_clay_loam"),
    (42, 52, 6, "sandy_clay"),
    (47, 6, 47, "silty_clay"),
    (60, 20, 20, "clay"),
]


def _simplex_points():
    """All simplex points clay+sand+silt=100 in 1 percent steps (5151 points)."""
    return [
        (clay, sand, 100 - clay - sand)
        for clay in range(0, 101)
        for sand in range(0, 101 - clay)
    ]


class TestUSDATextureClassification:
    """Test USDA texture triangle classification."""

    def test_sand(self):
        """Test sand classification."""
        assert classify_usda_texture(clay=5, sand=90, silt=5) == "sand"
        # canonical USDA: silt + 1.5*clay = 14.0 < 15
        assert classify_usda_texture(clay=8, sand=90, silt=2) == "sand"

    def test_loamy_sand(self):
        """Test loamy sand classification."""
        assert classify_usda_texture(clay=5, sand=80, silt=15) == "loamy_sand"
        # canonical USDA: silt + 1.5*clay = 17 >= 15, silt + 2*clay = 21 < 30
        # (formerly pinned as "sand")
        assert classify_usda_texture(clay=8, sand=87, silt=5) == "loamy_sand"

    def test_sandy_loam(self):
        """Test sandy loam classification."""
        assert classify_usda_texture(clay=15, sand=60, silt=25) == "sandy_loam"
        assert classify_usda_texture(clay=10, sand=65, silt=25) == "sandy_loam"
        # canonical USDA: silt + 2*clay = 30 >= 30 (formerly "loamy_sand")
        assert classify_usda_texture(clay=10, sand=80, silt=10) == "sandy_loam"
        # canonical USDA: silt + 2*clay = 37 >= 30 (formerly "loamy_sand")
        assert classify_usda_texture(clay=12, sand=75, silt=13) == "sandy_loam"

    def test_loam(self):
        """Test loam classification."""
        assert classify_usda_texture(clay=20, sand=40, silt=40) == "loam"
        assert classify_usda_texture(clay=15, sand=35, silt=50) == "silt_loam"

    def test_silt_loam(self):
        """Test silt loam classification."""
        assert classify_usda_texture(clay=15, sand=20, silt=65) == "silt_loam"
        assert classify_usda_texture(clay=20, sand=15, silt=65) == "silt_loam"

    def test_silt(self):
        """Test silt classification."""
        assert classify_usda_texture(clay=5, sand=10, silt=85) == "silt"
        assert classify_usda_texture(clay=8, sand=8, silt=84) == "silt"

    def test_sandy_clay_loam(self):
        """Test sandy clay loam classification."""
        assert classify_usda_texture(clay=25, sand=55, silt=20) == "sandy_clay_loam"
        assert classify_usda_texture(clay=30, sand=50, silt=20) == "sandy_clay_loam"

    def test_clay_loam(self):
        """Test clay loam classification."""
        assert classify_usda_texture(clay=35, sand=30, silt=35) == "clay_loam"
        assert classify_usda_texture(clay=30, sand=35, silt=35) == "clay_loam"

    def test_silty_clay_loam(self):
        """Test silty clay loam classification."""
        assert classify_usda_texture(clay=35, sand=10, silt=55) == "silty_clay_loam"
        assert classify_usda_texture(clay=30, sand=15, silt=55) == "silty_clay_loam"

    def test_sandy_clay(self):
        """Test sandy clay classification."""
        assert classify_usda_texture(clay=40, sand=50, silt=10) == "sandy_clay"
        assert classify_usda_texture(clay=45, sand=48, silt=7) == "sandy_clay"

    def test_silty_clay(self):
        """Test silty clay classification."""
        assert classify_usda_texture(clay=45, sand=5, silt=50) == "silty_clay"
        assert classify_usda_texture(clay=50, sand=10, silt=40) == "silty_clay"

    def test_clay(self):
        """Test clay classification."""
        assert classify_usda_texture(clay=55, sand=25, silt=20) == "clay"
        assert classify_usda_texture(clay=60, sand=20, silt=20) == "clay"

    def test_normalization(self):
        """Test that values are normalized if they don't sum to 100."""
        # These should give same result after normalization
        result1 = classify_usda_texture(clay=10, sand=180, silt=10)
        result2 = classify_usda_texture(clay=5, sand=90, silt=5)
        assert result1 == result2

    @pytest.mark.parametrize(
        ("clay", "sand", "silt", "expected"), CANONICAL_CONTROL_POINTS
    )
    def test_classify_matches_canonical_usda_control_points(
        self, clay, sand, silt, expected
    ):
        """Canonical control points of the USDA triangle (Soil Survey Manual)."""
        assert classify_usda_texture(clay=clay, sand=sand, silt=silt) == expected

    def test_zero_sum_returns_loam(self):
        """Sum 0 (no data) -> explicitly loam, not a hit of the `sand` rule."""
        assert classify_usda_texture(clay=0, sand=0, silt=0) == "loam"


class TestTextureToHSG:
    """Test texture class to HSG mapping."""

    def test_group_a_textures(self):
        """Test textures that map to HSG A."""
        assert texture_to_hsg("sand") == "A"
        assert texture_to_hsg("loamy_sand") == "A"

    def test_group_b_textures(self):
        """Test textures that map to HSG B."""
        assert texture_to_hsg("sandy_loam") == "B"
        assert texture_to_hsg("loam") == "B"
        assert texture_to_hsg("silt_loam") == "B"
        assert texture_to_hsg("silt") == "B"

    def test_group_c_textures(self):
        """Test textures that map to HSG C."""
        assert texture_to_hsg("sandy_clay_loam") == "C"
        assert texture_to_hsg("clay_loam") == "C"
        assert texture_to_hsg("silty_clay_loam") == "C"

    def test_group_d_textures(self):
        """Test textures that map to HSG D."""
        assert texture_to_hsg("sandy_clay") == "D"
        assert texture_to_hsg("silty_clay") == "D"
        assert texture_to_hsg("clay") == "D"

    def test_unknown_defaults_to_b(self):
        """Test that unknown texture defaults to B."""
        assert texture_to_hsg("unknown") == "B"


class TestArrayClassification:
    """Test array-based classification."""

    def test_classify_array_basic(self):
        """Test basic array classification."""
        clay = np.array([5, 20, 35, 55])
        sand = np.array([90, 40, 30, 20])
        silt = np.array([5, 40, 35, 25])

        result = classify_usda_texture_array(clay, sand, silt)

        assert result[0] == TEXTURE_CLASSES["sand"]
        assert result[3] == TEXTURE_CLASSES["clay"]

    def test_hsg_array_mapping(self):
        """Test HSG array mapping."""
        texture = np.array(
            [
                TEXTURE_CLASSES["sand"],
                TEXTURE_CLASSES["loam"],
                TEXTURE_CLASSES["clay_loam"],
                TEXTURE_CLASSES["clay"],
            ]
        )

        result = texture_to_hsg_array(texture)

        assert result[0] == HSG_VALUES["A"]
        assert result[1] == HSG_VALUES["B"]
        assert result[2] == HSG_VALUES["C"]
        assert result[3] == HSG_VALUES["D"]

    def test_nodata_handling(self):
        """Test nodata (0) handling in HSG array."""
        texture = np.array([0, TEXTURE_CLASSES["sand"], 0])
        result = texture_to_hsg_array(texture)

        assert result[0] == 0
        assert result[1] == HSG_VALUES["A"]
        assert result[2] == 0

    def test_scalar_and_array_agree_on_whole_simplex(self):
        """Scalar and vector compute from one rule list - a 1:1 match."""
        points = _simplex_points()
        assert len(points) == 5151

        clay = np.array([p[0] for p in points], dtype=np.float64)
        sand = np.array([p[1] for p in points], dtype=np.float64)
        silt = np.array([p[2] for p in points], dtype=np.float64)

        codes = classify_usda_texture_array(clay, sand, silt)
        expected = np.array(
            [TEXTURE_CLASSES[classify_usda_texture(c, s, si)] for c, s, si in points],
            dtype=np.uint8,
        )

        assert np.array_equal(codes, expected)
        # the USDA rules partition the simplex - every point has a class 1-12
        assert (codes >= 1).all() and (codes <= 12).all()

    def test_array_float32_input_boundary_clay_15(self):
        """float32 at the clay=15% boundary does not diverge from the scalar (A4-8)."""
        # as in the raster pipeline: g/kg (float32) / 10 -> percent
        clay = np.array([np.float32(150)], dtype=np.float32) / np.float32(10)
        sand = np.array([np.float32(750)], dtype=np.float32) / np.float32(10)
        silt = np.array([np.float32(100)], dtype=np.float32) / np.float32(10)

        code = int(classify_usda_texture_array(clay, sand, silt)[0])
        scalar = classify_usda_texture(15.0, 75.0, 10.0)

        assert TEXTURE_NAMES[code] == scalar

    def test_array_zero_sum_returns_loam(self):
        """Sum 0 in an array -> loam (explicit guard, not the `sand` rule)."""
        clay = np.array([0.0, 5.0])
        sand = np.array([0.0, 90.0])
        silt = np.array([0.0, 5.0])

        result = classify_usda_texture_array(clay, sand, silt)

        assert result[0] == TEXTURE_CLASSES["loam"]
        assert result[1] == TEXTURE_CLASSES["sand"]


class TestTextureClassesDict:
    """Test texture classes dictionary."""

    def test_all_classes_present(self):
        """Test that all 12 USDA classes are present."""
        assert len(TEXTURE_CLASSES) == 12
        expected_classes = [
            "sand",
            "loamy_sand",
            "sandy_loam",
            "loam",
            "silt_loam",
            "silt",
            "sandy_clay_loam",
            "clay_loam",
            "silty_clay_loam",
            "sandy_clay",
            "silty_clay",
            "clay",
        ]
        for cls in expected_classes:
            assert cls in TEXTURE_CLASSES

    def test_class_values_unique(self):
        """Test that all class values are unique."""
        values = list(TEXTURE_CLASSES.values())
        assert len(values) == len(set(values))


class TestHSGDescriptions:
    """Test HSG descriptions."""

    def test_all_groups_have_descriptions(self):
        """Test that all HSG groups have descriptions."""
        for group in ["A", "B", "C", "D"]:
            assert group in HSG_DESCRIPTIONS
            assert len(HSG_DESCRIPTIONS[group]) > 0


class TestHSGCalculator:
    """Test HSGCalculator class."""

    def test_calculator_requires_output_dir(self):
        with pytest.raises(TypeError):
            HSGCalculator()  # type: ignore[call-arg]

    def test_lazy_provider_loading(self, tmp_path):
        from kartograf.providers.soilgrids import SoilGridsProvider

        calc = HSGCalculator(tmp_path)
        assert isinstance(calc.provider, SoilGridsProvider)
        assert list(tmp_path.iterdir()) == []

    def test_reading_provider_keeps_default_cache_for_checks(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        calc = HSGCalculator(tmp_path / "data")
        assert isinstance(calc.provider, SoilGridsProvider)

        def edition_requiring_cache(provider, property, timeout=120):
            if provider._cache is None:
                raise DownloadError("brak cache")
            return Edition("2.0", f"https://example.test/{property}")

        with patch.object(SoilGridsProvider, "edition", edition_requiring_cache):
            plan = calc.check_hsg(bbox=BBOX, depth="0-5cm")
        assert [item.status for item in plan.items] == ["missing"] * 4

    def test_output_path_must_be_a_store_directory(self, tmp_path):
        for extension in (".tif", ".tiff"):
            with pytest.raises(ValidationError) as caught:
                HSGCalculator(tmp_path / f"hsg{extension}")
            assert str(caught.value) == (
                "--output to katalog magazynu (od 0.8.0); plik poza "
                "magazynem: hsg_from_rasters"
            )
        assert list(tmp_path.iterdir()) == []

    def test_conversion_factor(self):
        """Test conversion factor is correct."""
        assert HSGCalculator.CONVERSION_FACTOR == 10.0


def _create_test_raster(path, data, transform=None, crs="EPSG:2180", nodata=0):
    """Helper to create a minimal GeoTIFF for testing."""
    import rasterio
    from rasterio.transform import from_bounds

    if transform is None:
        transform = from_bounds(
            450000, 550000, 460000, 560000, data.shape[1], data.shape[0]
        )

    profile = {
        "driver": "GTiff",
        "dtype": data.dtype,
        "width": data.shape[1],
        "height": data.shape[0],
        "count": 1,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }

    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)


class RasterSoilGrids(SoilGridsProvider):
    """SoilGrids without network: fixed editions and rasters per property.

    ``rasters[property]`` = ``(array, nodata)``; ``editions[property]`` = an
    edition id or a ``DownloadError``. Counts GetCapabilities
    (``capabilities``) and GetCoverage (``downloads``).
    """

    def __init__(self, rasters=None, editions=None):
        super().__init__()
        self.rasters = dict(rasters or {})
        self.editions = dict(editions or {})
        self.capabilities = 0
        self.downloads: list[str] = []

    def edition(self, property, timeout=120):
        self.capabilities += 1
        current = self.editions.get(property, "2.0")
        if isinstance(current, Exception):
            raise current
        return Edition(current, f"https://example.test/{property}")

    def download_by_bbox(self, bbox, output_path, timeout=120, *, property, **kwargs):
        self.downloads.append(property)
        if isinstance(self.rasters.get(property), Exception):
            raise self.rasters[property]
        data, nodata = self.rasters.get(property, (_LOAM[property], 0))
        target = Path(output_path).with_suffix(".tif")
        _create_test_raster(target, data, nodata=nodata)
        return target


# 20% clay, 40% sand, 40% silt (g/kg) -> loam -> HSG B
_LOAM = {
    "clay": np.full((5, 5), 200, np.float32),
    "sand": np.full((5, 5), 400, np.float32),
    "silt": np.full((5, 5), 400, np.float32),
}
BBOX = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
COORDS = "450000_550000_460000_560000"
HSG_SEG = "hsg/global_soilgrids_0-5cm_mean"


def _hsg(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as src:
        return src.read(1)


def _meta(file) -> dict:
    import json

    return json.loads(Path(f"{file.version_path}.meta.json").read_text())


class TestHSGCalculatorCalculateFull:
    """HSG from SoilGrids input versions (D33)."""

    def test_calculate_hsg_bbox_and_sheet_and_geometry(self, tmp_path):
        from unittest.mock import patch

        calc = HSGCalculator(tmp_path, RasterSoilGrids())
        by_sheet = calc.calculate_hsg(sheet="N-34-130-D", depth="0-5cm")
        assert by_sheet.files[0].file.path == (
            tmp_path / HSG_SEG / "N-34/130/D/N-34-130-D.tif"
        )
        assert np.all(_hsg(by_sheet.files[0].file.path) == 2)  # loam -> B
        by_bbox = calc.calculate_hsg(bbox=BBOX, depth="0-5cm")
        shp = tmp_path / "area.shp"
        shp.touch()
        with patch("kartograf.core.geometry.get_overall_bbox", return_value=BBOX):
            by_geometry = calc.calculate_hsg(geometry=shp, depth="0-5cm")
        assert by_geometry.files[0].file.path == by_bbox.files[0].file.path
        assert by_geometry.files[0].file.status == "reused" and by_geometry.ok

    def test_stat_argument_rejected(self, tmp_path):
        calc = HSGCalculator(tmp_path, RasterSoilGrids())
        with pytest.raises(TypeError):
            calc.calculate_hsg(bbox=BBOX, depth="0-5cm", stat="mean")  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            calc.check_hsg(bbox=BBOX, depth="0-5cm", stat="mean")  # type: ignore[call-arg]

    def test_hsg_segment_unchanged_after_stat_removal(self, tmp_path):
        """The store written with ``stat="mean"`` keeps working: same segments,
        the HSG version of the same inputs is reused (no migration)."""
        first = HSGCalculator(tmp_path, RasterSoilGrids()).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        assert first.files[0].file.path == tmp_path / HSG_SEG / "bbox" / f"{COORDS}.tif"
        assert [i.file.path.parent.parent.name for i in first.inputs] == [
            f"global_soilgrids_{p}_0-5cm_mean" for p in ("clay", "sand", "silt")
        ]
        assert _meta(first.files[0].file)["extra"]["stat"] == "mean"
        again = HSGCalculator(tmp_path, RasterSoilGrids()).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        assert again.files[0].file.status == "reused"
        assert again.files[0].file.version_path == first.files[0].file.version_path

    def test_bbox_any_crs(self, tmp_path):
        """A WGS84 bbox computes the HSG of its EPSG:2180 envelope."""
        from kartograf.core.bbox import transform_bbox
        from kartograf.landcover.store import selection_unit

        wgs = transform_bbox(BBOX, "EPSG:4326")
        result = HSGCalculator(tmp_path, RasterSoilGrids()).calculate_hsg(
            bbox=wgs, depth="0-5cm"
        )
        unit = selection_unit(bbox=transform_bbox(wgs, "EPSG:2180"))
        assert result.files[0].unit == unit
        assert result.files[0].file.path == tmp_path / HSG_SEG / "bbox" / f"{unit}.tif"
        assert _meta(result.files[0].file)["request"]["bbox_crs"] == "EPSG:2180"

    def test_check_hsg_items(self, tmp_path):
        calc = HSGCalculator(tmp_path, RasterSoilGrids())
        plan = calc.check_hsg(sheet="N-34-130-D", depth="0-5cm")
        assert [(i.track, i.status) for i in plan.items] == [
            ("landcover", "missing"),
            ("landcover", "missing"),
            ("landcover", "missing"),
            ("hsg", "missing"),
        ]
        assert {i.unit for i in plan.items} == {"N-34-130-D"}

    @pytest.mark.parametrize(
        "selection",
        [{}, {"sheet": "N-34-130-D", "bbox": BBOX}],
        ids=["none", "two"],
    )
    def test_exactly_one_selection(self, tmp_path, selection):
        calc = HSGCalculator(tmp_path, RasterSoilGrids())
        with pytest.raises(ValidationError, match="dokladnie jeden wybor"):
            calc.calculate_hsg(**selection, depth="0-5cm")
        with pytest.raises(ValidationError, match="dokladnie jeden wybor"):
            calc.check_hsg(**selection, depth="0-5cm")

    def test_calculate_hsg_bbox_sand_is_a(self, tmp_path):
        rasters = {
            "clay": (np.full((5, 5), 50, np.float32), 0),  # 5%
            "sand": (np.full((5, 5), 900, np.float32), 0),  # 90%
            "silt": (np.full((5, 5), 50, np.float32), 0),  # 5%
        }
        result = HSGCalculator(tmp_path, RasterSoilGrids(rasters)).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        assert np.all(_hsg(result.files[0].file.path) == 1)  # sand -> A

    def test_calculate_hsg_nodata_handling(self, tmp_path):
        """Cells with all-zero values -> nodata (0)."""
        zeros = {p: (np.zeros((5, 5), np.float32), 0) for p in ("clay", "sand", "silt")}
        result = HSGCalculator(tmp_path, RasterSoilGrids(zeros)).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        assert np.all(_hsg(result.files[0].file.path) == 0)

    def test_calculate_hsg_masks_int16_nodata(self, tmp_path):
        """Cells flagged as nodata in the source rasters -> HSG 0, not B."""
        rasters = {}
        for prop, fill in {"clay": 300, "sand": 300, "silt": 400}.items():
            data = np.full((3, 3), fill, dtype=np.int16)
            if prop == "clay":
                data[1, 1] = -32768  # nodata in clay only
            data[2, 2] = -32768  # nodata in all three
            rasters[prop] = (data, -32768)
        result = HSGCalculator(tmp_path, RasterSoilGrids(rasters)).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        hsg = _hsg(result.files[0].file.path)
        assert hsg[0, 0] == 3  # clay_loam -> C
        assert hsg[1, 1] == 0
        assert hsg[2, 2] == 0

    def test_calculate_hsg_masks_nan(self, tmp_path):
        """NaN in a source raster -> HSG 0, even without a nodata tag."""
        rasters = {}
        for prop, fill in {"clay": 300.0, "sand": 300.0, "silt": 400.0}.items():
            data = np.full((3, 3), fill, dtype=np.float32)
            if prop == "sand":
                data[1, 1] = np.nan
            rasters[prop] = (data, None)
        result = HSGCalculator(tmp_path, RasterSoilGrids(rasters)).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        hsg = _hsg(result.files[0].file.path)
        assert hsg[1, 1] == 0
        assert np.all(np.delete(hsg.reshape(-1), 4) > 0)

    def test_hsg_version_from_input_versions(self, tmp_path):
        provider = RasterSoilGrids()
        result = HSGCalculator(tmp_path, provider).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        file = result.files[0].file
        assert result.files[0].unit == COORDS
        assert file.path == tmp_path / HSG_SEG / "bbox" / f"{COORDS}.tif"
        assert (file.status, file.label) == ("new", "2.0")
        assert file.version_path.parent.name == f"2.0_{file.sha256[:8]}"
        assert [r.file.path.parent.parent.name for r in result.inputs] == [
            "global_soilgrids_clay_0-5cm_mean",
            "global_soilgrids_sand_0-5cm_mean",
            "global_soilgrids_silt_0-5cm_mean",
        ]
        meta = _meta(file)
        assert meta["extra"]["version"] == {"label": "2.0", "label_source": "edition"}
        assert meta["extra"]["source_files"] == [
            {
                "name": name,
                "file": r.file.version_path.relative_to(tmp_path).as_posix(),
                "sha256": r.file.sha256,
                "label": "2.0",
            }
            for name, r in zip(("clay", "sand", "silt"), result.inputs, strict=True)
        ]
        assert meta["dataset"] == "global.isric.soilgrids"
        assert meta["horizontal_crs"] == "EPSG:2180" and meta["nodata"] == 0
        assert meta["request"] == {
            "bbox": [450000, 550000, 460000, 560000],
            "bbox_crs": "EPSG:2180",
        }
        assert meta["extra"]["derived"] == "hsg"
        assert (meta["extra"]["depth"], meta["extra"]["stat"]) == ("0-5cm", "mean")

    def test_hsg_rerun_reused_no_compute(self, tmp_path):
        first = HSGCalculator(tmp_path, RasterSoilGrids()).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        provider = RasterSoilGrids()
        with patch("kartograf.hydrology.hsg._classify_hsg") as classify:
            again = HSGCalculator(tmp_path, provider).calculate_hsg(
                bbox=BBOX, depth="0-5cm"
            )
        classify.assert_not_called()
        assert provider.downloads == []
        assert (again.files[0].file.status, again.files[0].file.version_path) == (
            "reused",
            first.files[0].file.version_path,
        )
        assert [r.file.status for r in again.inputs] == ["local"] * 3

    def test_hsg_new_input_content_new_version(self, tmp_path):
        HSGCalculator(tmp_path, RasterSoilGrids()).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        # 600 g/kg clay with sand/silt 400 -> clay -> D (loam B before)
        sandy = RasterSoilGrids({"clay": (np.full((5, 5), 600, np.float32), 0)})
        result = HSGCalculator(tmp_path, sandy).calculate_hsg(
            bbox=BBOX, depth="0-5cm", update="force"
        )
        assert [r.file.status for r in result.inputs] == [
            "new",
            "unchanged",
            "unchanged",
        ]
        assert result.files[0].file.status == "new"
        assert len(list(result.files[0].file.version_path.parent.parent.iterdir())) == 2

    def test_hsg_force_same_inputs_is_reused(self, tmp_path):
        first = HSGCalculator(tmp_path, RasterSoilGrids()).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        provider = RasterSoilGrids()
        again = HSGCalculator(tmp_path, provider).calculate_hsg(
            bbox=BBOX, depth="0-5cm", update="force"
        )
        assert provider.downloads == ["clay", "sand", "silt"]
        assert [r.file.status for r in again.inputs] == ["unchanged"] * 3
        assert again.files[0].file.status == "reused"
        assert again.files[0].file.version_path == first.files[0].file.version_path

    def test_hsg_mixed_editions_label(self, tmp_path):
        provider = RasterSoilGrids(editions={"sand": "2.1"})
        result = HSGCalculator(tmp_path, provider).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        assert result.files[0].file.label == "2.0+2.1"
        assert [
            f["label"] for f in _meta(result.files[0].file)["extra"]["source_files"]
        ] == [
            "2.0",
            "2.1",
            "2.0",
        ]

    def test_hsg_input_error_no_result(self, tmp_path):
        provider = RasterSoilGrids({"silt": DownloadError("WCS 500")})
        report = HSGCalculator(tmp_path, provider).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        assert not report.ok and report.files == ()
        assert [(item.unit, item.kind) for item in report.failed] == [
            (f"silt {COORDS}", "download")
        ]
        assert len(report.inputs) == 2
        assert not (tmp_path / "hsg").exists()
        assert not (tmp_path / "soil/global_soilgrids_silt_0-5cm_mean/bbox").exists()

    def test_check_hsg_never_downloads_or_computes(self, tmp_path):
        provider = RasterSoilGrids()
        calc = HSGCalculator(tmp_path, provider)
        with patch("kartograf.hydrology.hsg._classify_hsg") as classify:
            plan = calc.check_hsg(bbox=BBOX, depth="0-5cm")
        classify.assert_not_called()
        assert provider.downloads == []
        assert [(i.track, i.status) for i in plan.items] == [
            ("landcover", "missing"),
            ("landcover", "missing"),
            ("landcover", "missing"),
            ("hsg", "missing"),
        ]
        assert plan.items[3].available_label == "2.0"
        assert plan.items[3].segment == HSG_SEG
        calc.calculate_hsg(bbox=BBOX, depth="0-5cm")
        current = calc.check_hsg(bbox=BBOX, depth="0-5cm")
        assert [i.status for i in current.items] == ["current"] * 4
        provider.editions["clay"] = "2.1"
        newer = calc.check_hsg(bbox=BBOX, depth="0-5cm")
        assert [i.status for i in newer.items] == [
            "newer",
            "current",
            "current",
            "missing",
        ]
        assert newer.items[3].available_label == "2.0+2.1"
        provider.editions["clay"] = DownloadError("caps 503")
        failed = calc.check_hsg(bbox=BBOX, depth="0-5cm")
        assert failed.items[3].status == "check_failed"
        assert len(provider.downloads) == 3  # only the calculate call above

    def test_hsg_default_inputs_ask_no_source(self, tmp_path):
        """The default mode asks no source for local inputs (ADR-036 erratum
        3): an edition lookup that would fail changes nothing, no notice."""
        provider = RasterSoilGrids()
        calc = HSGCalculator(tmp_path, provider)
        calc.calculate_hsg(bbox=BBOX, depth="0-5cm")
        provider.editions["clay"] = DownloadError("caps 503")
        observed = []
        result = calc.calculate_hsg(bbox=BBOX, depth="0-5cm", on_notice=observed.append)
        assert result.files[0].file.status == "reused"
        assert result.inputs[0].file.status == "local"
        assert result.inputs[0].file.unverified == "unchecked"
        assert result.notices == tuple(observed) == ()

    def test_hsg_plan_upgrade_recomputes_with_new_input(self, tmp_path):
        provider = RasterSoilGrids()
        calc = HSGCalculator(tmp_path, provider)
        calc.calculate_hsg(bbox=BBOX, depth="0-5cm")
        provider.editions["clay"] = "2.1"
        provider.rasters["clay"] = (np.full((5, 5), 600, np.float32), 0)  # -> D
        plan = calc.check_hsg(bbox=BBOX, depth="0-5cm")
        result = calc.calculate_hsg(
            bbox=BBOX, depth="0-5cm", update="upgrade", plan=plan
        )
        assert [r.file.status for r in result.inputs] == ["new", "local", "local"]
        assert (result.files[0].file.status, result.files[0].file.label) == (
            "new",
            "2.0+2.1",
        )
        assert result.stale == ()

    def test_hsg_sheet_and_bbox_distinct_paths(self, tmp_path):
        calc = HSGCalculator(tmp_path, RasterSoilGrids())
        by_sheet = calc.calculate_hsg(sheet="M-33-036-A", depth="0-5cm")
        by_bbox = calc.calculate_hsg(bbox=BBOX, depth="0-5cm")
        other = calc.calculate_hsg(
            bbox=BBox(450000, 550000, 455000, 555000, "EPSG:2180"),
            depth="0-5cm",
        )
        paths = {
            by_sheet.files[0].file.path,
            by_bbox.files[0].file.path,
            other.files[0].file.path,
        }
        assert len(paths) == 3
        assert by_sheet.files[0].file.path.name == "M-33-36-A.tif"
        assert _meta(by_sheet.files[0].file)["request"] == {"sheet": "M-33-36-A"}

    def test_hsg_no_keep_intermediate(self, tmp_path):
        with pytest.raises(TypeError):
            HSGCalculator(tmp_path, RasterSoilGrids()).calculate_hsg(
                bbox=BBOX, depth="0-5cm", keep_intermediate=True
            )

    def test_hsg_statistics(self, tmp_path):
        """Module function returns correct counts and areas."""

        # Create test HSG raster: 2x A, 1x B, 1x C
        data = np.array([[1, 1], [2, 3]], dtype=np.uint8)
        hsg_path = tmp_path / "hsg.tif"
        _create_test_raster(hsg_path, data)

        stats = hsg_statistics(hsg_path)

        assert stats["A"]["count"] == 2
        assert stats["B"]["count"] == 1
        assert stats["C"]["count"] == 1
        assert stats["D"]["count"] == 0
        assert abs(stats["A"]["percent"] - 50.0) < 0.1
        assert abs(stats["B"]["percent"] - 25.0) < 0.1

    def test_hsg_statistics_no_data_entry(self, tmp_path):
        """Classes use pixels with data; nodata uses all cells."""
        data = np.array([[2, 0, 0, 0], [2, 0, 0, 0]], dtype=np.uint8)
        hsg_path = tmp_path / "hsg.tif"
        _create_test_raster(hsg_path, data)

        stats = hsg_statistics(hsg_path)

        assert stats["B"]["percent"] == 100.0 and stats["B"]["count"] == 2
        assert stats["nodata"]["count"] == 6
        assert stats["nodata"]["percent"] == 75.0
        assert stats["nodata"]["area_ha"] == pytest.approx(3 * stats["B"]["area_ha"])

    def test_hsg_statistics_geographic_crs_area_in_hectares(self, tmp_path):
        """EPSG:4326 rasters get geodetic areas, not square degrees."""
        from pyproj import Geod
        from rasterio.transform import from_origin

        res = 0.0022457  # ~250 m in latitude
        transform = from_origin(22.7, 52.5, res, res)
        data = np.full((100, 100), 2, dtype=np.uint8)
        hsg_path = tmp_path / "hsg_4326.tif"
        _create_test_raster(hsg_path, data, transform=transform, crs="EPSG:4326")

        west, north = 22.7, 52.5
        east, south = west + 100 * res, north - 100 * res
        geod = Geod(ellps="WGS84")
        area, _ = geod.polygon_area_perimeter(
            [west, east, east, west], [south, south, north, north]
        )
        expected_ha = abs(area) / 10000

        stats = hsg_statistics(hsg_path)

        assert stats["B"]["count"] == 10000
        assert stats["B"]["area_ha"] == pytest.approx(expected_ha, rel=0.02)
        assert stats["B"]["percent"] == 100.0

    def test_hsg_statistics_projected_crs_unchanged(self, tmp_path):
        """Metric CRS keeps the plain width*height cell area."""

        # 2x2 raster over 10x10 km -> 5x5 km cells = 2500 ha each
        data = np.array([[1, 1], [2, 3]], dtype=np.uint8)
        hsg_path = tmp_path / "hsg_2180.tif"
        _create_test_raster(hsg_path, data)

        stats = hsg_statistics(hsg_path)

        assert stats["A"]["area_ha"] == pytest.approx(5000.0)
        assert stats["B"]["area_ha"] == pytest.approx(2500.0)


class TestHSGOutputDirOnWrite:
    """The store root is not touched before an input exists."""

    def test_init_creates_nothing(self, tmp_path):
        HSGCalculator(tmp_path / "a" / "b", RasterSoilGrids())
        assert list(tmp_path.iterdir()) == []

    def test_edition_failure_records_failed_input_without_hsg(self, tmp_path):
        provider = RasterSoilGrids(editions={"clay": DownloadError("caps")})
        report = HSGCalculator(tmp_path / "a", provider).calculate_hsg(
            bbox=BBOX, depth="0-5cm"
        )
        assert not report.ok and not report.files
        assert [(item.unit, item.kind) for item in report.failed] == [
            (f"clay {COORDS}", "download")
        ]
        # the other inputs still ran and stay stored (like landcover units)
        assert [item.unit.split()[0] for item in report.inputs] == ["sand", "silt"]
        assert (tmp_path / "a" / "soil").exists()
        assert not (tmp_path / "a" / "hsg").exists()


class TestHsgFromRasters:
    """A8: HSG from ready clay/sand/silt rasters, no configuration defaults."""

    def _raster(self, path, value, nodata=None, width=20):
        import rasterio
        from rasterio.transform import from_origin

        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            dtype="int16",
            count=1,
            width=width,
            height=20,
            crs="EPSG:2180",
            transform=from_origin(500000, 600000, 250, 250),
            nodata=nodata,
        ) as dst:
            dst.write(np.full((20, width), value, dtype="int16"), 1)
        return path

    def test_classifies_on_requested_grid(self, tmp_path):
        import json

        import rasterio

        from kartograf import BBox, hsg_from_rasters

        clay = self._raster(tmp_path / "clay.tif", 450)  # 45 % clay -> D
        sand = self._raster(tmp_path / "sand.tif", 200)
        silt = self._raster(tmp_path / "silt.tif", 350)
        bbox = BBox(501000, 596000, 503000, 598000, "EPSG:2180")
        out = hsg_from_rasters(
            clay,
            sand,
            silt,
            bbox=bbox,
            crs="EPSG:2180",
            pixel_m=100.0,
            output_path=tmp_path / "out" / "hsg.tif",
        )
        with rasterio.open(out) as src:
            assert src.res == (100.0, 100.0)
            assert (src.bounds.left, src.bounds.top) == (501000.0, 598000.0)
            data = src.read(1)
            assert src.nodata == 0
        assert np.all(data == 4)
        meta = json.loads(out.with_name(out.name + ".meta.json").read_text())
        assert meta["extra"]["derived"] == "hsg"
        # Same type as calculate_hsg_by_bbox: list[str] (kartograf-meta/1).
        assert meta["extra"]["source_layers"] == ["clay", "sand", "silt"]
        layers = meta["extra"]["source_files"]
        assert [layer["name"] for layer in layers] == ["clay", "sand", "silt"]
        assert [layer["file"] for layer in layers] == [
            "clay.tif",
            "sand.tif",
            "silt.tif",
        ]
        assert all(len(layer["sha256"]) == 64 for layer in layers)

    def test_sidecar_sha256_matches_input_files(self, tmp_path):
        import hashlib
        import json

        from kartograf import BBox, hsg_from_rasters

        clay = self._raster(tmp_path / "clay.tif", 450)
        sand = self._raster(tmp_path / "sand.tif", 200)
        silt = self._raster(tmp_path / "silt.tif", 350)
        out = hsg_from_rasters(
            clay,
            sand,
            silt,
            bbox=BBox(501000, 596000, 502000, 597000, "EPSG:2180"),
            crs="EPSG:2180",
            pixel_m=250.0,
            output_path=tmp_path / "h.tif",
        )
        meta = json.loads(out.with_name(out.name + ".meta.json").read_text())
        by_name = {x["name"]: x["sha256"] for x in meta["extra"]["source_files"]}
        for name, path in (("clay", clay), ("sand", sand), ("silt", silt)):
            assert by_name[name] == hashlib.sha256(path.read_bytes()).hexdigest()

    def test_nodata_triplet_is_zero(self, tmp_path):
        import rasterio

        from kartograf import BBox, hsg_from_rasters

        clay = self._raster(tmp_path / "clay.tif", 0)
        sand = self._raster(tmp_path / "sand.tif", 0)
        silt = self._raster(tmp_path / "silt.tif", 0)
        out = hsg_from_rasters(
            clay,
            sand,
            silt,
            bbox=BBox(501000, 596000, 502000, 597000, "EPSG:2180"),
            crs="EPSG:2180",
            pixel_m=250.0,
            output_path=tmp_path / "h.tif",
        )
        with rasterio.open(out) as src:
            assert np.all(src.read(1) == 0)

    def test_untagged_inputs_outside_footprint_are_zero(self, tmp_path):
        """No nodata tag = no nodata value; cells outside the inputs are gaps."""
        import rasterio

        from kartograf import BBox, hsg_from_rasters

        clay = self._raster(tmp_path / "clay.tif", 450)  # no nodata tag
        sand = self._raster(tmp_path / "sand.tif", 200)
        silt = self._raster(tmp_path / "silt.tif", 350)
        # top 1000 m of the grid lie north of the inputs (y > 600000)
        out = hsg_from_rasters(
            clay,
            sand,
            silt,
            bbox=BBox(501000, 596000, 504000, 601000, "EPSG:2180"),
            crs="EPSG:2180",
            pixel_m=100.0,
            output_path=tmp_path / "h.tif",
        )
        with rasterio.open(out) as src:
            data = src.read(1)
        assert np.all(data[:10] == 0)
        assert np.all(data[10:] == 4)

    def test_one_input_narrower_than_others_leaves_gap(self, tmp_path):
        """A cell outside ONE input is a gap, not soil with that part set to 0."""
        import rasterio

        from kartograf import BBox, hsg_from_rasters

        clay = self._raster(tmp_path / "clay.tif", 450, width=10)  # x < 502500
        sand = self._raster(tmp_path / "sand.tif", 200)
        silt = self._raster(tmp_path / "silt.tif", 350)
        out = hsg_from_rasters(
            clay,
            sand,
            silt,
            bbox=BBox(501000, 596000, 504000, 598000, "EPSG:2180"),
            crs="EPSG:2180",
            pixel_m=250.0,
            output_path=tmp_path / "h.tif",
        )
        with rasterio.open(out) as src:
            data = src.read(1)
        assert np.all(data[:, :6] == 4)  # x 501000-502500 covered by all three
        assert np.all(data[:, 6:] == 0)  # beyond the clay footprint

    def test_tagged_nodata_masks_cells(self, tmp_path):
        import rasterio

        from kartograf import BBox, hsg_from_rasters

        clay = self._raster(tmp_path / "clay.tif", -1, nodata=-1)
        sand = self._raster(tmp_path / "sand.tif", 200)
        silt = self._raster(tmp_path / "silt.tif", 350)
        out = hsg_from_rasters(
            clay,
            sand,
            silt,
            bbox=BBox(501000, 596000, 502000, 597000, "EPSG:2180"),
            crs="EPSG:2180",
            pixel_m=250.0,
            output_path=tmp_path / "h.tif",
        )
        with rasterio.open(out) as src:
            assert np.all(src.read(1) == 0)

    def test_bbox_in_other_crs_is_converted_to_grid_crs(self, tmp_path):
        import rasterio

        from kartograf import BBox, hsg_from_rasters
        from kartograf.core.bbox import transform_bbox

        clay = self._raster(tmp_path / "clay.tif", 450)
        sand = self._raster(tmp_path / "sand.tif", 200)
        silt = self._raster(tmp_path / "silt.tif", 350)
        bbox_2180 = BBox(501000, 596000, 503000, 598000, "EPSG:2180")
        bbox_4326 = transform_bbox(bbox_2180, "EPSG:4326")
        out = hsg_from_rasters(
            clay,
            sand,
            silt,
            bbox=bbox_4326,
            crs="EPSG:2180",
            pixel_m=100.0,
            output_path=tmp_path / "h.tif",
        )
        expected = transform_bbox(bbox_4326, "EPSG:2180")
        with rasterio.open(out) as src:
            assert src.crs.to_string() == "EPSG:2180"
            assert src.bounds.left == pytest.approx(expected.min_x)
            assert src.bounds.top == pytest.approx(expected.max_y)

    def test_non_positive_pixel_rejected(self, tmp_path):
        from kartograf import BBox, ValidationError, hsg_from_rasters

        clay = self._raster(tmp_path / "clay.tif", 450)
        with pytest.raises(ValidationError, match="pixel_m"):
            hsg_from_rasters(
                clay,
                clay,
                clay,
                bbox=BBox(501000, 596000, 502000, 597000, "EPSG:2180"),
                crs="EPSG:2180",
                pixel_m=0,
                output_path=tmp_path / "h.tif",
            )
        assert not (tmp_path / "h.tif").exists()

    def test_signature_has_no_defaults(self):
        import inspect

        from kartograf import hsg_from_rasters

        params = inspect.signature(hsg_from_rasters).parameters.values()
        assert all(p.default is inspect.Parameter.empty for p in params)

    def test_shared_classifier_masks_tag_nan_and_zero_triplets(self):
        """The helper used by calculate_hsg_by_bbox and hsg_from_rasters."""
        from kartograf.hydrology.hsg import _classify_hsg

        clay = np.array([[450.0, -1.0, 0.0, np.nan]], dtype=np.float32)
        sand = np.array([[200.0, 200.0, 0.0, 200.0]], dtype=np.float32)
        silt = np.array([[350.0, 350.0, 0.0, 350.0]], dtype=np.float32)
        hsg = _classify_hsg(clay, sand, silt, (-1.0, None, None))
        assert hsg.dtype == np.uint8
        assert hsg.tolist() == [[4, 0, 0, 0]]

    def test_zero_clay_with_sand_or_silt_is_not_a_gap(self):
        """P9c: only an all-zero triplet is a gap; pure sand or pure silt
        (clay 0 g/kg) is real soil and gets a class."""
        from kartograf.hydrology.hsg import _classify_hsg

        clay = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
        sand = np.array([[1000.0, 0.0, 0.0]], dtype=np.float32)
        silt = np.array([[0.0, 1000.0, 0.0]], dtype=np.float32)
        hsg = _classify_hsg(clay, sand, silt, (None, None, None))
        sand_class, silt_class, gap = hsg[0].tolist()
        assert sand_class != 0 and silt_class != 0
        assert gap == 0
