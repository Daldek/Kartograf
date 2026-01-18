"""
Tests for land cover functionality.

Tests cover LandCoverProvider, Bdot10kProvider, CorineProvider,
and LandCoverManager classes.
"""

import pytest
from pathlib import Path

from kartograf.core.sheet_parser import BBox
from kartograf.providers.landcover_base import LandCoverProvider
from kartograf.providers.bdot10k import Bdot10kProvider, WOJEWODZTWO_NAMES
from kartograf.providers.corine import CorineProvider
from kartograf.landcover.manager import LandCoverManager
from kartograf.exceptions import ValidationError


class TestLandCoverProviderBase:
    """Test LandCoverProvider abstract base class."""

    def test_cannot_instantiate_directly(self):
        """Test that LandCoverProvider cannot be instantiated."""
        with pytest.raises(TypeError):
            LandCoverProvider()

    def test_validate_teryt_valid(self):
        """Test TERYT validation with valid codes."""
        provider = Bdot10kProvider()
        assert provider.validate_teryt("1465") is True  # 4 digits
        assert provider.validate_teryt("1234567") is True  # 7 digits

    def test_validate_teryt_invalid(self):
        """Test TERYT validation with invalid codes."""
        provider = Bdot10kProvider()
        assert provider.validate_teryt("") is False
        assert provider.validate_teryt("123") is False
        assert provider.validate_teryt("abc") is False
        assert provider.validate_teryt("12345") is False


class TestBdot10kProvider:
    """Test Bdot10kProvider."""

    def test_provider_name(self):
        """Test provider name."""
        provider = Bdot10kProvider()
        assert provider.name == "BDOT10k"

    def test_source_url(self):
        """Test source URL."""
        provider = Bdot10kProvider()
        assert "geoportal.gov.pl" in provider.source_url

    def test_available_layers(self):
        """Test available layers."""
        provider = Bdot10kProvider()
        layers = provider.get_available_layers()
        assert "PTLZ" in layers  # forests
        assert "PTWP" in layers  # waters
        assert len(layers) == 9

    def test_layer_description(self):
        """Test layer descriptions."""
        provider = Bdot10kProvider()
        assert provider.get_layer_description("PTLZ") == "Tereny leśne"
        assert provider.get_layer_description("PTWP") == "Wody powierzchniowe"

    def test_supported_formats(self):
        """Test supported formats."""
        provider = Bdot10kProvider()
        formats = provider.get_supported_formats()
        assert "GPKG" in formats
        assert "SHP" in formats

    def test_construct_opendata_url_gpkg(self):
        """Test OpenData URL construction for GPKG."""
        provider = Bdot10kProvider()
        url = provider._construct_opendata_url("1465", "GPKG")
        assert "opendata.geoportal.gov.pl/bdot10k" in url
        assert "GPKG" in url
        assert "1465.zip" in url

    def test_construct_opendata_url_shp(self):
        """Test OpenData URL construction for SHP."""
        provider = Bdot10kProvider()
        url = provider._construct_opendata_url("1465", "SHP")
        assert "SHP" in url

    def test_construct_opendata_url_invalid_woj(self):
        """Test OpenData URL with invalid województwo code."""
        provider = Bdot10kProvider()
        with pytest.raises(ValidationError):
            provider._construct_opendata_url("9999", "GPKG")

    def test_construct_wfs_url(self):
        """Test WFS URL construction."""
        provider = Bdot10kProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        url = provider._construct_wfs_url(bbox, "PTLZ")
        assert "WFS" in url
        assert "GetFeature" in url
        assert "PTLZ" in url

    def test_download_by_teryt_invalid(self):
        """Test download with invalid TERYT."""
        provider = Bdot10kProvider()
        with pytest.raises(ValidationError):
            provider.download_by_teryt("invalid", Path("/tmp/test.gpkg"))

    def test_download_by_bbox_wrong_crs(self):
        """Test download with wrong CRS."""
        provider = Bdot10kProvider()
        bbox = BBox(14.0, 52.0, 15.0, 53.0, "EPSG:4326")
        with pytest.raises(ValueError):
            provider.download_by_bbox(bbox, Path("/tmp/test.gml"))


class TestCorineProvider:
    """Test CorineProvider."""

    def test_provider_name(self):
        """Test provider name."""
        provider = CorineProvider()
        assert provider.name == "CORINE Land Cover"

    def test_source_url(self):
        """Test source URL."""
        provider = CorineProvider()
        assert "copernicus" in provider.source_url

    def test_available_years(self):
        """Test available years."""
        provider = CorineProvider()
        years = provider.get_available_years()
        assert 2018 in years
        assert 2012 in years
        assert 1990 in years
        assert len(years) == 5

    def test_clc_classes(self):
        """Test CLC classification dictionary."""
        provider = CorineProvider()
        classes = provider.get_clc_classes()
        assert "111" in classes  # Continuous urban fabric
        assert "311" in classes  # Broad-leaved forest
        assert len(classes) == 44

    def test_download_by_teryt_not_supported(self):
        """Test that TERYT download is not supported."""
        provider = CorineProvider()
        with pytest.raises(NotImplementedError):
            provider.download_by_teryt("1465", Path("/tmp/test.tif"))

    def test_download_by_bbox_wrong_crs(self):
        """Test download with wrong CRS."""
        provider = CorineProvider()
        bbox = BBox(14.0, 52.0, 15.0, 53.0, "EPSG:4326")
        with pytest.raises(ValueError):
            provider.download_by_bbox(bbox, Path("/tmp/test.png"))

    def test_download_by_bbox_invalid_year(self):
        """Test download with invalid year."""
        provider = CorineProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        with pytest.raises(ValueError):
            provider.download_by_bbox(bbox, Path("/tmp/test.png"), year=2020)

    def test_construct_wms_url(self):
        """Test WMS URL construction."""
        provider = CorineProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        url = provider._construct_wms_url(bbox, 2018, 100, 100)
        assert "WMS" in url
        assert "GetMap" in url
        assert "2180" in url


class TestLandCoverManager:
    """Test LandCoverManager."""

    def test_init_default_provider(self):
        """Test default provider is BDOT10k."""
        manager = LandCoverManager()
        assert manager.provider_name == "BDOT10k"

    def test_init_with_provider_name(self):
        """Test initialization with provider name."""
        manager = LandCoverManager(provider="corine")
        assert manager.provider_name == "CORINE Land Cover"

    def test_init_with_provider_instance(self):
        """Test initialization with provider instance."""
        provider = CorineProvider()
        manager = LandCoverManager(provider=provider)
        assert manager.provider_name == "CORINE Land Cover"

    def test_init_invalid_provider(self):
        """Test initialization with invalid provider."""
        with pytest.raises(ValueError):
            LandCoverManager(provider="invalid")

    def test_set_provider_by_name(self):
        """Test setting provider by name."""
        manager = LandCoverManager()
        manager.set_provider("corine")
        assert manager.provider_name == "CORINE Land Cover"

    def test_set_provider_by_instance(self):
        """Test setting provider by instance."""
        manager = LandCoverManager()
        manager.set_provider(Bdot10kProvider())
        assert manager.provider_name == "BDOT10k"

    def test_get_available_providers(self):
        """Test getting available providers."""
        providers = LandCoverManager.get_available_providers()
        assert "bdot10k" in providers
        assert "corine" in providers

    def test_download_no_selection(self):
        """Test download with no selection method."""
        manager = LandCoverManager()
        with pytest.raises(ValueError):
            manager.download()

    def test_download_multiple_selection(self):
        """Test download with multiple selection methods."""
        manager = LandCoverManager()
        with pytest.raises(ValueError):
            manager.download(teryt="1465", godlo="N-34-130-D")

    def test_repr(self):
        """Test string representation."""
        manager = LandCoverManager()
        repr_str = repr(manager)
        assert "LandCoverManager" in repr_str
        assert "BDOT10k" in repr_str


class TestLandCoverCLI:
    """Test land cover CLI commands."""

    def test_landcover_help(self, capsys):
        """Test landcover help command."""
        from kartograf.cli.commands import main

        result = main(["landcover"])
        assert result == 0
        captured = capsys.readouterr()
        assert "download" in captured.out
        assert "list-sources" in captured.out

    def test_landcover_list_sources(self, capsys):
        """Test list-sources command."""
        from kartograf.cli.commands import main

        result = main(["landcover", "list-sources"])
        assert result == 0
        captured = capsys.readouterr()
        assert "bdot10k" in captured.out
        assert "corine" in captured.out

    def test_landcover_list_layers_bdot10k(self, capsys):
        """Test list-layers for BDOT10k."""
        from kartograf.cli.commands import main

        result = main(["landcover", "list-layers", "--source", "bdot10k"])
        assert result == 0
        captured = capsys.readouterr()
        assert "PTLZ" in captured.out
        assert "Tereny leśne" in captured.out

    def test_landcover_list_layers_corine(self, capsys):
        """Test list-layers for CORINE."""
        from kartograf.cli.commands import main

        result = main(["landcover", "list-layers", "--source", "corine"])
        assert result == 0
        captured = capsys.readouterr()
        assert "2018" in captured.out

    def test_landcover_download_no_selection(self, capsys):
        """Test download without selection method."""
        from kartograf.cli.commands import main

        result = main(["landcover", "download"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Must provide one of" in captured.err

    def test_landcover_download_invalid_bbox(self, capsys):
        """Test download with invalid bbox."""
        from kartograf.cli.commands import main

        result = main(["landcover", "download", "--bbox", "invalid"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid bbox" in captured.err


class TestWojewodztwoMapping:
    """Test województwo TERYT mapping."""

    def test_all_wojewodztwa_mapped(self):
        """Test that all 16 województwa are mapped."""
        assert len(WOJEWODZTWO_NAMES) == 16

    def test_known_wojewodztwa(self):
        """Test known województwo mappings."""
        assert WOJEWODZTWO_NAMES["14"] == "mazowieckie"
        assert WOJEWODZTWO_NAMES["12"] == "malopolskie"
        assert WOJEWODZTWO_NAMES["02"] == "dolnoslaskie"
