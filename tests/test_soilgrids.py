"""
Tests for SoilGrids provider functionality.

Tests cover SoilGridsProvider class for downloading soil property data
from ISRIC SoilGrids via WCS API.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.soilgrids import PROPERTY_DESCRIPTIONS, SoilGridsProvider


class TestSoilGridsProvider:
    """Test SoilGridsProvider."""

    def test_provider_name(self):
        """Test provider name."""
        provider = SoilGridsProvider()
        assert provider.name == "SoilGrids"

    def test_source_url(self):
        """Test source URL."""
        provider = SoilGridsProvider()
        assert "soilgrids.org" in provider.source_url

    def test_available_properties(self):
        """Test available properties."""
        provider = SoilGridsProvider()
        props = provider.get_available_properties()
        assert "soc" in props  # soil organic carbon
        assert "clay" in props
        assert "sand" in props
        assert "silt" in props
        assert "phh2o" in props
        assert len(props) == 11

    def test_available_depths(self):
        """Test available depths."""
        provider = SoilGridsProvider()
        depths = provider.get_available_depths()
        assert "0-5cm" in depths
        assert "5-15cm" in depths
        assert "15-30cm" in depths
        assert "30-60cm" in depths
        assert "60-100cm" in depths
        assert "100-200cm" in depths
        assert len(depths) == 6

    def test_available_stats(self):
        """Test available statistics."""
        provider = SoilGridsProvider()
        stats = provider.get_available_stats()
        assert "mean" in stats
        assert "Q0.05" in stats
        assert "Q0.5" in stats
        assert "Q0.95" in stats
        assert "uncertainty" in stats
        assert len(stats) == 5

    def test_property_description(self):
        """Test property descriptions."""
        provider = SoilGridsProvider()
        assert "Clay" in provider.get_property_description("clay")
        assert "carbon" in provider.get_property_description("soc").lower()
        assert "pH" in provider.get_property_description("phh2o")

    def test_supported_formats(self):
        """Test supported formats."""
        provider = SoilGridsProvider()
        formats = provider.get_supported_formats()
        assert "GTiff" in formats

    def test_get_available_layers_alias(self):
        """Test that get_available_layers returns properties."""
        provider = SoilGridsProvider()
        layers = provider.get_available_layers()
        props = provider.get_available_properties()
        assert layers == props


class TestSoilGridsValidation:
    """Test SoilGridsProvider input validation."""

    def test_download_by_bbox_wrong_crs(self):
        """Test download with wrong CRS."""
        provider = SoilGridsProvider()
        bbox = BBox(14.0, 52.0, 15.0, 53.0, "EPSG:4326")
        with pytest.raises(ValueError, match="EPSG:2180"):
            provider.download_by_bbox(bbox, Path("/tmp/test.tif"))

    def test_download_by_bbox_invalid_property(self):
        """Test download with invalid property."""
        provider = SoilGridsProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        with pytest.raises(ValueError, match="Invalid property"):
            provider.download_by_bbox(
                bbox, Path("/tmp/test.tif"), property="invalid_property"
            )

    def test_download_by_bbox_invalid_depth(self):
        """Test download with invalid depth."""
        provider = SoilGridsProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        with pytest.raises(ValueError, match="Invalid depth"):
            provider.download_by_bbox(
                bbox, Path("/tmp/test.tif"), depth="invalid_depth"
            )

    def test_download_by_bbox_invalid_stat(self):
        """Test download with invalid stat."""
        provider = SoilGridsProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        with pytest.raises(ValueError, match="Invalid stat"):
            provider.download_by_bbox(bbox, Path("/tmp/test.tif"), stat="invalid_stat")


class TestSoilGridsWCSUrl:
    """Test WCS URL construction."""

    def test_construct_wcs_url_basic(self):
        """Test basic WCS URL construction."""
        provider = SoilGridsProvider()
        bbox_wgs84 = (14.0, 52.0, 15.0, 53.0)
        url = provider._construct_wcs_url(bbox_wgs84, "soc", "0-5cm", "mean")

        assert "maps.isric.org" in url
        assert "WCS" in url
        assert "GetCoverage" in url
        assert "soc_0-5cm_mean" in url
        # Note: image/tiff is URL-encoded as image%2Ftiff
        assert "image%2Ftiff" in url or "image/tiff" in url

    def test_construct_wcs_url_different_property(self):
        """Test WCS URL with different property."""
        provider = SoilGridsProvider()
        bbox_wgs84 = (14.0, 52.0, 15.0, 53.0)
        url = provider._construct_wcs_url(bbox_wgs84, "clay", "15-30cm", "Q0.5")

        assert "clay_15-30cm_Q0.5" in url
        assert "/map/clay.map" in url

    def test_construct_wcs_url_bbox_in_url(self):
        """Test that bbox coordinates are in URL."""
        provider = SoilGridsProvider()
        bbox_wgs84 = (14.5, 52.5, 15.5, 53.5)
        url = provider._construct_wcs_url(bbox_wgs84, "soc", "0-5cm", "mean")

        assert "long(14.5,15.5)" in url
        assert "lat(52.5,53.5)" in url


class TestSoilGridsCRSTransform:
    """Test CRS transformation."""

    def test_transform_bbox_to_wgs84(self):
        """Test transformation from EPSG:2180 to WGS84."""
        provider = SoilGridsProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        result = provider._transform_bbox_to_wgs84(bbox)

        # Result should be (min_lon, min_lat, max_lon, max_lat)
        min_lon, min_lat, max_lon, max_lat = result

        # Check approximate bounds for Poland
        assert 14 < min_lon < 25  # Poland longitude range
        assert 49 < min_lat < 55  # Poland latitude range
        assert min_lon < max_lon
        assert min_lat < max_lat

    def test_transform_bbox_to_wgs84_covers_all_corners(self):
        """Envelope covers all four corners, not only SW and NE."""
        from pyproj import Transformer

        from kartograf.core.sheet_parser import SheetParser

        provider = SoilGridsProvider()
        bbox = SheetParser("N-34-130-D").get_bbox("EPSG:2180")
        min_lon, min_lat, max_lon, max_lat = provider._transform_bbox_to_wgs84(bbox)

        transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
        for x, y in (
            (bbox.min_x, bbox.min_y),
            (bbox.min_x, bbox.max_y),
            (bbox.max_x, bbox.min_y),
            (bbox.max_x, bbox.max_y),
        ):
            lon, lat = transformer.transform(x, y)
            assert min_lon <= lon <= max_lon, f"corner {(x, y)}: lon outside envelope"
            assert min_lat <= lat <= max_lat, f"corner {(x, y)}: lat outside envelope"

        # Two corners span 0.1657 deg of latitude, the true envelope 0.1830 deg.
        assert max_lat - min_lat > 0.18


class TestSoilGridsTeryt:
    """Test TERYT-related functionality."""

    def test_validate_teryt_valid(self):
        """Test TERYT validation with valid codes."""
        provider = SoilGridsProvider()
        assert provider.validate_teryt("1465") is True
        assert provider.validate_teryt("1234567") is True

    def test_validate_teryt_invalid(self):
        """Test TERYT validation with invalid codes."""
        provider = SoilGridsProvider()
        assert provider.validate_teryt("") is False
        assert provider.validate_teryt("123") is False
        assert provider.validate_teryt("abc") is False

    @pytest.mark.parametrize("code", ["1465", "invalid"])
    def test_download_by_teryt_raises_not_implemented(self, code, tmp_path):
        """TERYT selection is not supported - no data for a guessed area."""
        provider = SoilGridsProvider()
        with pytest.raises(NotImplementedError, match="TERYT"):
            provider.download_by_teryt(code, tmp_path / "x.tif")

    def test_download_by_admin_unit_raises_not_implemented(self, tmp_path):
        """Canonical name behaves like the deprecated alias."""
        provider = SoilGridsProvider()
        with pytest.raises(NotImplementedError, match="TERYT"):
            provider.download_by_admin_unit("1465", tmp_path / "x.tif")


class TestSoilGridsDownload:
    """Test download functionality with mocks."""

    @patch("kartograf.providers.soilgrids.requests.Session")
    def test_download_with_retry_success(self, mock_session_class):
        """Test successful download."""
        import tempfile

        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock response
        mock_response = Mock()
        mock_response.headers = {"Content-Type": "image/tiff"}
        mock_response.iter_content.return_value = [b"fake tiff data"]
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        provider = SoilGridsProvider(session=mock_session)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.tif"
            result = provider._download_with_retry(
                url="https://example.com/test.tif",
                output_path=output_path,
                timeout=30,
                description="test download",
            )

            assert result == output_path
            assert output_path.exists()

    @patch("kartograf.providers.soilgrids.requests.Session")
    def test_download_with_retry_xml_error(self, mock_session_class):
        """Test download handling WCS error response."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock XML error response
        mock_response = Mock()
        mock_response.headers = {"Content-Type": "application/xml"}
        mock_response.text = "<ServiceExceptionReport>Error</ServiceExceptionReport>"
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        provider = SoilGridsProvider(session=mock_session)

        with pytest.raises(DownloadError, match="WCS returned error"):
            provider._download_with_retry(
                url="https://example.com/test.tif",
                output_path=Path("/tmp/test.tif"),
                timeout=30,
                description="test download",
            )


class TestSoilGridsCLI:
    """Test CLI integration."""

    def test_landcover_list_sources_includes_soilgrids(self, capsys):
        """Test that list-sources shows soilgrids."""
        from kartograf.cli.commands import main

        result = main(["landcover", "list-sources"])
        assert result == 0
        captured = capsys.readouterr()
        assert "soilgrids" in captured.out
        assert "SoilGrids" in captured.out

    def test_landcover_list_layers_soilgrids(self, capsys):
        """Test list-layers for soilgrids."""
        from kartograf.cli.commands import main

        result = main(["landcover", "list-layers", "--source", "soilgrids"])
        assert result == 0
        captured = capsys.readouterr()
        assert "soc" in captured.out
        assert "clay" in captured.out
        assert "0-5cm" in captured.out
        assert "mean" in captured.out


class TestSoilGridsManager:
    """Test LandCoverManager integration."""

    def test_manager_soilgrids_provider(self):
        """Test manager with soilgrids provider."""
        from kartograf.landcover.manager import LandCoverManager

        manager = LandCoverManager(provider="soilgrids")
        assert manager.provider_name == "SoilGrids"

    def test_manager_available_providers(self):
        """Test that soilgrids is in available providers."""
        from kartograf.landcover.manager import LandCoverManager

        providers = LandCoverManager.get_available_providers()
        assert "soilgrids" in providers


class TestPropertyDescriptions:
    """Test property descriptions dictionary."""

    def test_all_properties_have_descriptions(self):
        """Test that all properties have descriptions."""
        provider = SoilGridsProvider()
        for prop in provider.PROPERTIES:
            assert prop in PROPERTY_DESCRIPTIONS
            assert len(PROPERTY_DESCRIPTIONS[prop]) > 0

    def test_description_format(self):
        """Test description format includes units."""
        # Most descriptions should include units in parentheses
        assert "%" in PROPERTY_DESCRIPTIONS["clay"]
        assert "g/kg" in PROPERTY_DESCRIPTIONS["soc"]
        assert "pH" in PROPERTY_DESCRIPTIONS["phh2o"]
