"""
Tests for Hydrologic Soil Group (HSG) calculation functionality.

Tests cover USDA texture classification, HSG mapping, and HSGCalculator.
"""

from unittest.mock import Mock, patch

import numpy as np
import pytest

from kartograf.hydrology.hsg import (
    HSG_DESCRIPTIONS,
    HSG_VALUES,
    TEXTURE_CLASSES,
    TEXTURE_NAMES,
    HSGCalculator,
    classify_usda_texture,
    classify_usda_texture_array,
    texture_to_hsg,
    texture_to_hsg_array,
)

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

    def test_calculator_initialization(self):
        """Test calculator initialization."""
        calc = HSGCalculator()
        assert calc._provider is None

    def test_calculator_with_provider(self):
        """Test calculator with custom provider."""
        mock_provider = Mock()
        calc = HSGCalculator(provider=mock_provider)
        assert calc._provider is mock_provider

    def test_lazy_provider_loading(self):
        """Test that provider is lazy-loaded."""
        calc = HSGCalculator()
        assert calc._provider is None

        # Accessing provider should load it
        provider = calc.provider
        assert provider is not None
        assert calc._provider is not None

    def test_conversion_factor(self):
        """Test conversion factor is correct."""
        assert HSGCalculator.CONVERSION_FACTOR == 10.0


class TestHSGCalculatorCalculation:
    """Test HSGCalculator calculation methods (with mocks)."""

    def test_calculator_with_custom_provider(self):
        """Test that calculator accepts custom provider."""
        mock_provider = Mock()
        calc = HSGCalculator(provider=mock_provider)
        assert calc.provider is mock_provider

    def test_calculator_provider_attribute(self):
        """Test provider attribute is set correctly."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        calc = HSGCalculator(provider=mock_provider)
        assert calc._provider is mock_provider


class TestHSGCLI:
    """Test CLI integration."""

    def test_soilgrids_command_exists(self):
        """Test that soilgrids command is registered."""
        from kartograf.cli.commands import create_parser

        parser = create_parser()
        # Parse with soilgrids command
        args = parser.parse_args(["soilgrids"])
        assert args.command == "soilgrids"

    def test_soilgrids_hsg_command_exists(self):
        """Test that soilgrids hsg command is registered."""
        from kartograf.cli.commands import create_parser

        parser = create_parser()
        args = parser.parse_args(["soilgrids", "hsg", "--godlo", "N-34-130-D"])
        assert args.command == "soilgrids"
        assert args.soilgrids_command == "hsg"
        assert args.godlo == "N-34-130-D"

    def test_soilgrids_hsg_default_values(self):
        """Test default values for soilgrids hsg command."""
        from kartograf.cli.commands import create_parser

        parser = create_parser()
        args = parser.parse_args(["soilgrids", "hsg", "--godlo", "N-34-130-D"])

        assert args.depth == "0-5cm"
        assert args.output == "./data/hsg"
        assert args.keep_intermediate is False
        assert args.stats is False

    def test_soilgrids_hsg_custom_options(self):
        """Test custom options for soilgrids hsg command."""
        from kartograf.cli.commands import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "soilgrids",
                "hsg",
                "--godlo",
                "N-34-130-D",
                "--depth",
                "15-30cm",
                "--output",
                "/tmp/custom.tif",
                "--keep-intermediate",
                "--stats",
            ]
        )

        assert args.depth == "15-30cm"
        assert args.output == "/tmp/custom.tif"
        assert args.keep_intermediate is True
        assert args.stats is True


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


class TestHSGCalculatorCalculateFull:
    """Test HSGCalculator calculation with mocked provider and rasterio."""

    def test_calculate_hsg_by_godlo(self, tmp_path):
        """calculate_hsg_by_godlo downloads clay/sand/silt and produces HSG."""
        mock_provider = Mock()
        calc = HSGCalculator(provider=mock_provider)

        # Mock download_by_bbox to create test rasters
        def fake_download(bbox, path, timeout, property, depth, stat):
            # Create raster with data in g/kg
            if property == "clay":
                data = np.full((10, 10), 200, dtype=np.float32)  # 20%
            elif property == "sand":
                data = np.full((10, 10), 400, dtype=np.float32)  # 40%
            else:  # silt
                data = np.full((10, 10), 400, dtype=np.float32)  # 40%
            _create_test_raster(path, data)
            return path

        mock_provider.download_by_bbox.side_effect = fake_download

        output = tmp_path / "hsg.tif"

        with patch("kartograf.core.sheet_parser.SheetParser") as mock_parser_cls:
            from kartograf.core.sheet_parser import BBox

            mock_parser = Mock()
            mock_parser.get_bbox.return_value = BBox(
                450000, 550000, 460000, 560000, "EPSG:2180"
            )
            mock_parser_cls.return_value = mock_parser

            result = calc.calculate_hsg_by_godlo("N-34-130-D", output)

        assert result == output
        assert output.exists()

        # Verify HSG content
        import rasterio

        with rasterio.open(output) as src:
            hsg = src.read(1)
        # 20% clay, 40% sand, 40% silt -> loam -> HSG B = 2
        assert np.all(hsg == 2)

    def test_calculate_hsg_by_bbox(self, tmp_path):
        """calculate_hsg_by_bbox produces HSG raster."""
        from kartograf.core.sheet_parser import BBox

        mock_provider = Mock()
        calc = HSGCalculator(provider=mock_provider)

        def fake_download(bbox, path, timeout, property, depth, stat):
            if property == "clay":
                data = np.full((5, 5), 50, dtype=np.float32)  # 5%
            elif property == "sand":
                data = np.full((5, 5), 900, dtype=np.float32)  # 90%
            else:  # silt
                data = np.full((5, 5), 50, dtype=np.float32)  # 5%
            _create_test_raster(path, data)
            return path

        mock_provider.download_by_bbox.side_effect = fake_download

        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "hsg.tif"
        result = calc.calculate_hsg_by_bbox(bbox, output)

        assert result == output

        import rasterio

        with rasterio.open(output) as src:
            hsg = src.read(1)
        # 5% clay, 90% sand, 5% silt -> sand -> HSG A = 1
        assert np.all(hsg == 1)

    def test_calculate_hsg_nodata_handling(self, tmp_path):
        """Cells with all-zero values -> nodata (0)."""
        from kartograf.core.sheet_parser import BBox

        mock_provider = Mock()
        calc = HSGCalculator(provider=mock_provider)

        def fake_download(bbox, path, timeout, property, depth, stat):
            data = np.zeros((5, 5), dtype=np.float32)
            _create_test_raster(path, data)
            return path

        mock_provider.download_by_bbox.side_effect = fake_download

        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "hsg.tif"
        calc.calculate_hsg_by_bbox(bbox, output)

        import rasterio

        with rasterio.open(output) as src:
            hsg = src.read(1)
        assert np.all(hsg == 0)

    def test_calculate_hsg_masks_int16_nodata(self, tmp_path):
        """Cells flagged as nodata in the source rasters -> HSG 0, not B."""
        from kartograf.core.sheet_parser import BBox

        mock_provider = Mock()
        calc = HSGCalculator(provider=mock_provider)

        # Valid soil everywhere: clay=300, sand=300, silt=400 g/kg -> clay_loam -> C
        def fake_download(bbox, path, timeout, property, depth, stat):
            fill = {"clay": 300, "sand": 300, "silt": 400}[property]
            data = np.full((3, 3), fill, dtype=np.int16)
            # [1, 1] is nodata in clay only, [2, 2] is nodata in all three
            if property == "clay":
                data[1, 1] = -32768
            data[2, 2] = -32768
            _create_test_raster(path, data, nodata=-32768)
            return path

        mock_provider.download_by_bbox.side_effect = fake_download

        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "hsg.tif"
        calc.calculate_hsg_by_bbox(bbox, output)

        import rasterio

        with rasterio.open(output) as src:
            hsg = src.read(1)

        assert hsg[0, 0] == 3  # clay_loam -> C
        assert hsg[1, 1] == 0  # nodata in clay alone is enough
        assert hsg[2, 2] == 0  # nodata in all three bands

    def test_calculate_hsg_masks_nan(self, tmp_path):
        """NaN in a source raster -> HSG 0, even without a nodata tag."""
        from kartograf.core.sheet_parser import BBox

        mock_provider = Mock()
        calc = HSGCalculator(provider=mock_provider)

        def fake_download(bbox, path, timeout, property, depth, stat):
            fill = {"clay": 300.0, "sand": 300.0, "silt": 400.0}[property]
            data = np.full((3, 3), fill, dtype=np.float32)
            if property == "sand":
                data[1, 1] = np.nan
            _create_test_raster(path, data, nodata=None)
            return path

        mock_provider.download_by_bbox.side_effect = fake_download

        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "hsg.tif"
        calc.calculate_hsg_by_bbox(bbox, output)

        import rasterio

        with rasterio.open(output) as src:
            hsg = src.read(1)

        assert hsg[1, 1] == 0
        assert np.all(np.delete(hsg.reshape(-1), 4) > 0)

    def test_calculate_hsg_keep_intermediate(self, tmp_path):
        """keep_intermediate=True copies clay/sand/silt files."""
        from kartograf.core.sheet_parser import BBox

        mock_provider = Mock()
        calc = HSGCalculator(provider=mock_provider)

        def fake_download(bbox, path, timeout, property, depth, stat):
            data = np.full((3, 3), 333, dtype=np.float32)
            _create_test_raster(path, data)
            return path

        mock_provider.download_by_bbox.side_effect = fake_download

        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "out" / "hsg.tif"
        calc.calculate_hsg_by_bbox(bbox, output, keep_intermediate=True)

        assert (tmp_path / "out" / "clay.tif").exists()
        assert (tmp_path / "out" / "sand.tif").exists()
        assert (tmp_path / "out" / "silt.tif").exists()

    def test_get_hsg_statistics(self, tmp_path):
        """get_hsg_statistics returns correct counts and areas."""
        calc = HSGCalculator()

        # Create test HSG raster: 2x A, 1x B, 1x C
        data = np.array([[1, 1], [2, 3]], dtype=np.uint8)
        hsg_path = tmp_path / "hsg.tif"
        _create_test_raster(hsg_path, data)

        stats = calc.get_hsg_statistics(hsg_path)

        assert stats["A"]["count"] == 2
        assert stats["B"]["count"] == 1
        assert stats["C"]["count"] == 1
        assert stats["D"]["count"] == 0
        assert abs(stats["A"]["percent"] - 50.0) < 0.1
        assert abs(stats["B"]["percent"] - 25.0) < 0.1

    def test_get_hsg_statistics_geographic_crs_area_in_hectares(self, tmp_path):
        """EPSG:4326 rasters get geodetic areas, not square degrees."""
        from pyproj import Geod
        from rasterio.transform import from_origin

        calc = HSGCalculator()

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

        stats = calc.get_hsg_statistics(hsg_path)

        assert stats["B"]["count"] == 10000
        assert stats["B"]["area_ha"] == pytest.approx(expected_ha, rel=0.02)
        assert stats["B"]["percent"] == 100.0

    def test_get_hsg_statistics_projected_crs_unchanged(self, tmp_path):
        """Metric CRS keeps the plain width*height cell area."""
        calc = HSGCalculator()

        # 2x2 raster over 10x10 km -> 5x5 km cells = 2500 ha each
        data = np.array([[1, 1], [2, 3]], dtype=np.uint8)
        hsg_path = tmp_path / "hsg_2180.tif"
        _create_test_raster(hsg_path, data)

        stats = calc.get_hsg_statistics(hsg_path)

        assert stats["A"]["area_ha"] == pytest.approx(5000.0)
        assert stats["B"]["area_ha"] == pytest.approx(2500.0)

    def test_get_hsg_statistics_structure(self, tmp_path):
        """Verify stats dict has required keys."""
        calc = HSGCalculator()

        data = np.array([[1, 2], [3, 4]], dtype=np.uint8)
        hsg_path = tmp_path / "hsg.tif"
        _create_test_raster(hsg_path, data)

        stats = calc.get_hsg_statistics(hsg_path)

        for group in ["A", "B", "C", "D"]:
            assert group in stats
            assert "count" in stats[group]
            assert "area_m2" in stats[group]
            assert "area_ha" in stats[group]
            assert "percent" in stats[group]
            assert "description" in stats[group]


class TestHSGSidecar:
    """The HSG result gets a <file>.meta.json sidecar (project rule)."""

    def _calc(self):
        mock_provider = Mock()

        def fake_download(bbox, path, timeout, property, depth, stat):
            data = np.full((5, 5), 200 if property == "clay" else 400, np.float32)
            _create_test_raster(path, data)
            return path

        mock_provider.download_by_bbox.side_effect = fake_download
        return HSGCalculator(provider=mock_provider)

    def test_sidecar_written(self, tmp_path):
        import json

        from kartograf.core.sheet_parser import BBox

        out = tmp_path / "hsg_x.tif"
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        self._calc().calculate_hsg_by_bbox(bbox, out, depth="5-15cm", stat="mean")

        meta = json.loads((tmp_path / "hsg_x.tif.meta.json").read_text())
        assert meta["dataset"] == "global.isric.soilgrids"
        assert meta["horizontal_crs"] == "EPSG:2180"
        assert meta["nodata"] == 0
        assert meta["request"]["bbox"] == [450000, 550000, 460000, 560000]
        assert meta["request"]["bbox_crs"] == "EPSG:2180"
        assert meta["extra"]["derived"] == "hsg"
        assert meta["extra"]["source_layers"] == ["clay", "sand", "silt"]
        assert meta["extra"]["depth"] == "5-15cm"
        assert meta["extra"]["stat"] == "mean"

    def test_sidecar_by_godlo_records_sheet(self, tmp_path):
        import json

        out = tmp_path / "hsg_sheet.tif"
        self._calc().calculate_hsg_by_godlo("N-34-130-D", out)

        request = json.loads((tmp_path / "hsg_sheet.tif.meta.json").read_text())[
            "request"
        ]
        assert request["sheet"] == "N-34-130-D"
        assert request["bbox_crs"] == "EPSG:2180"
        assert len(request["bbox"]) == 4

    def test_sidecar_by_bbox_has_no_sheet(self, tmp_path):
        import json

        from kartograf.core.sheet_parser import BBox

        out = tmp_path / "hsg_nosheet.tif"
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        self._calc().calculate_hsg_by_bbox(bbox, out)

        request = json.loads((tmp_path / "hsg_nosheet.tif.meta.json").read_text())[
            "request"
        ]
        assert "sheet" not in request

    def test_sidecar_uses_bbox_raster_capability(self, tmp_path):
        from kartograf.core.sheet_parser import BBox

        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        with patch("kartograf.sources.sidecar.emit_sidecar") as emit:
            self._calc().calculate_hsg_by_bbox(bbox, tmp_path / "h.tif")
        assert emit.call_args.kwargs["capability"] == "bbox_raster"

    def test_sidecar_failure_does_not_break(self, tmp_path):
        from kartograf.core.sheet_parser import BBox

        out = tmp_path / "hsg_y.tif"
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        with patch("kartograf.sources.sidecar.write_sidecar", side_effect=OSError("x")):
            result = self._calc().calculate_hsg_by_bbox(bbox, out)
        assert result == out and out.exists()


class TestHSGOutputDirOnWrite:
    """The output directory is created only right before the result is written."""

    @staticmethod
    def _bbox():
        from kartograf.core.sheet_parser import BBox

        return BBox(450000, 550000, 460000, 560000, "EPSG:2180")

    def test_download_failure_leaves_no_output_dir(self, tmp_path):
        from kartograf.exceptions import DownloadError

        provider = Mock()
        provider.download_by_bbox.side_effect = DownloadError("siec")
        out = tmp_path / "a" / "b" / "hsg.tif"
        with pytest.raises(DownloadError):
            HSGCalculator(provider=provider).calculate_hsg_by_bbox(self._bbox(), out)
        assert not (tmp_path / "a").exists()

    def test_nested_output_dir_created_on_success(self, tmp_path):
        def fake_download(bbox, path, timeout, property, depth, stat):
            _create_test_raster(path, np.full((5, 5), 200, np.float32))
            return path

        provider = Mock()
        provider.download_by_bbox.side_effect = fake_download
        out = tmp_path / "a" / "b" / "hsg.tif"
        HSGCalculator(provider=provider).calculate_hsg_by_bbox(
            self._bbox(), out, keep_intermediate=True
        )
        assert out.exists()
        assert (tmp_path / "a" / "b" / "hsg.tif.meta.json").exists()
        assert (tmp_path / "a" / "b" / "clay.tif").exists()
