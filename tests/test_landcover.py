"""
Tests for land cover functionality.

Tests cover LandCoverProvider, Bdot10kProvider, CorineProvider,
and LandCoverManager classes.
"""

import sqlite3
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.bdot10k import (
    WOJEWODZTWO_NAMES,
    Bdot10kProvider,
)
from kartograf.providers.corine import CorineProvider
from kartograf.providers.landcover_base import LandCoverProvider


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
        assert "PTZB" in layers  # built-up areas
        assert len(layers) == 12

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
        assert "1465_GPKG.zip" in url

    def test_construct_opendata_url_shp(self):
        """Test OpenData URL construction for SHP."""
        provider = Bdot10kProvider()
        url = provider._construct_opendata_url("1465", "SHP")
        assert "SHP" in url
        assert "1465_SHP.zip" in url

    def test_construct_opendata_url_invalid_woj(self):
        """Test OpenData URL with invalid województwo code."""
        provider = Bdot10kProvider()
        with pytest.raises(ValidationError):
            provider._construct_opendata_url("9999", "GPKG")

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
        assert 2006 in years
        assert 2000 in years
        assert 1990 in years
        assert len(years) == 5  # EEA: 2018, 2012, 2006, 2000 + DLR: 1990

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

    def test_construct_wms_url_eea(self):
        """Test WMS URL construction for EEA endpoint."""
        provider = CorineProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        url = provider._construct_wms_url(bbox, 2018, 100, 100)
        assert "WMS" in url
        assert "GetMap" in url
        assert "discomap.eea.europa.eu" in url  # EEA Discomap endpoint
        assert "CLC2018" in url

    def test_construct_wms_url_dlr_fallback(self):
        """Test WMS URL construction for DLR fallback (1990)."""
        provider = CorineProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        url = provider._construct_wms_url(bbox, 1990, 100, 100)
        assert "WMS" in url
        assert "GetMap" in url
        assert "geoservice.dlr.de" in url  # DLR WMS endpoint
        assert "CORINE" in url

    def test_clms_token_property(self):
        """Test CLMS OAuth2 credentials property."""
        # Test with empty credentials (explicitly disabled)
        provider = CorineProvider(clms_credentials={})
        assert provider.has_clms_token is False

        # Test with mock credentials
        mock_credentials = {
            "client_id": "test-client",
            "private_key": (
                "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----"
            ),
            "token_uri": "https://example.com/token",
        }
        provider_with_creds = CorineProvider(clms_credentials=mock_credentials)
        assert provider_with_creds.has_clms_token is True

    def test_clms_years(self):
        """Test CLMS API supported years."""
        provider = CorineProvider()
        assert 2018 in provider.CLMS_YEARS
        assert 2012 in provider.CLMS_YEARS
        assert 1990 not in provider.CLMS_YEARS  # Only via DLR WMS


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
        assert "2018" in captured.out  # Most recent available year

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


# ===========================================================================
# New tests for Bdot10kProvider (download, retry, extract, merge)
# ===========================================================================


class TestBdot10kProviderDownload:
    """Test Bdot10kProvider download methods with mocks."""

    def test_download_by_teryt_invalid_format(self):
        """Invalid format raises ValueError."""
        provider = Bdot10kProvider()
        with pytest.raises(ValueError, match="Unsupported format"):
            provider.download_by_teryt("1465", Path("/tmp/out.gpkg"), format="XML")

    def test_download_by_teryt_success(self, tmp_path):
        """Successful download by TERYT."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"

        with patch.object(
            provider, "_download_with_retry", return_value=output
        ) as mock_dl:
            result = provider.download_by_teryt("1465", output)

        assert result == output
        mock_dl.assert_called_once()
        call_kwargs = mock_dl.call_args
        assert "1465" in call_kwargs.kwargs.get(
            "description", call_kwargs[1].get("description", "")
        )

    @patch("kartograf.core.sheet_parser.SheetParser")
    def test_download_by_godlo_success(self, mock_parser_cls, tmp_path):
        """download_by_godlo resolves TERYT via center point."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"

        mock_parser = Mock()
        mock_parser.get_bbox.return_value = BBox(
            450000, 550000, 460000, 560000, "EPSG:2180"
        )
        mock_parser_cls.return_value = mock_parser

        with (
            patch.object(provider, "_get_teryt_for_point", return_value="1465"),
            patch.object(provider, "download_by_teryt", return_value=output) as mock_dl,
        ):
            result = provider.download_by_godlo("N-34-130-D", output)

        assert result == output
        mock_dl.assert_called_once()

    def test_get_teryt_for_point_gpkg_pattern(self):
        """Extract TERYT from GPKG URL pattern in WMS response."""
        provider = Bdot10kProvider()
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.text = (
            '<a href="https://opendata.geoportal.gov.pl/bdot10k/GPKG/14/1465_GPKG.zip">'
        )
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider._session = mock_session

        teryt = provider._get_teryt_for_point(500000, 600000)
        assert teryt == "1465"

    def test_get_teryt_for_point_shp_fallback(self):
        """Fall back to SHP URL pattern when no GPKG match."""
        provider = Bdot10kProvider()
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.text = (
            '<a href="https://opendata.geoportal.gov.pl/bdot10k/SHP/14/1465_SHP.zip">'
        )
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider._session = mock_session

        teryt = provider._get_teryt_for_point(500000, 600000)
        assert teryt == "1465"

    def test_get_teryt_for_point_not_found(self):
        """No URL match -> DownloadError."""
        provider = Bdot10kProvider()
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.text = "<html>No data here</html>"
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider._session = mock_session

        with pytest.raises(DownloadError, match="Could not determine TERYT"):
            provider._get_teryt_for_point(500000, 600000)

    def test_get_teryt_for_point_network_error(self):
        """Network error -> DownloadError."""
        provider = Bdot10kProvider()
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("timeout")
        provider._session = mock_session

        with pytest.raises(DownloadError, match="WMS GetFeatureInfo failed"):
            provider._get_teryt_for_point(500000, 600000)


class TestBdot10kRetryAndIO:
    """Test retry, save, extract, merge."""

    def test_download_with_retry_success(self, tmp_path):
        """Successful download on first attempt."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.shp"
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.iter_content.return_value = [b"shp_data"]
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider._session = mock_session

        result = provider._download_with_retry(
            url="https://example.com/file.shp",
            output_path=output,
            timeout=30,
            description="test",
        )
        assert result == output
        assert output.read_bytes() == b"shp_data"

    @patch("kartograf.providers.bdot10k.time.sleep")
    def test_download_with_retry_all_fail(self, _sleep, tmp_path):
        """All retries fail -> DownloadError."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.shp"
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("fail")
        provider._session = mock_session

        with pytest.raises(DownloadError, match="after 3 attempts"):
            provider._download_with_retry(
                url="https://example.com/file.shp",
                output_path=output,
                timeout=30,
                description="test",
            )

    def test_save_response(self, tmp_path):
        """_save_response writes response content to file."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"
        mock_resp = Mock()
        mock_resp.iter_content.return_value = [b"chunk1", b"chunk2"]

        provider._save_response(mock_resp, output)
        assert output.read_bytes() == b"chunk1chunk2"

    def test_extract_gpkg_from_zip(self, tmp_path):
        """Extract PT* GPKG files from ZIP and merge."""
        provider = Bdot10kProvider()
        output = tmp_path / "merged.gpkg"

        # Create a minimal SQLite GPKG file
        gpkg_path = tmp_path / "temp_PTLZ.gpkg"
        conn = sqlite3.connect(str(gpkg_path))
        c = conn.cursor()
        c.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c.execute("CREATE TABLE PTLZ (id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("INSERT INTO PTLZ VALUES (1, 'forest')")
        conn.commit()
        conn.close()

        # Create a ZIP with the GPKG
        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf, open(gpkg_path, "rb") as f:
            zf.writestr("data/BDOT10k_PTLZ.gpkg", f.read())
        zip_buf.seek(0)

        # Create mock response
        mock_resp = Mock()
        mock_resp.iter_content.return_value = [zip_buf.getvalue()]

        provider._extract_gpkg_from_zip(mock_resp, output)
        assert output.with_suffix(".gpkg").exists()

    def test_extract_gpkg_bad_zip(self, tmp_path):
        """Invalid ZIP -> DownloadError."""
        provider = Bdot10kProvider()
        output = tmp_path / "merged.gpkg"

        mock_resp = Mock()
        mock_resp.iter_content.return_value = [b"not a zip file"]

        with pytest.raises(DownloadError, match="Invalid ZIP"):
            provider._extract_gpkg_from_zip(mock_resp, output)

    def test_merge_gpkg_files_empty(self):
        """Empty file list -> DownloadError."""
        provider = Bdot10kProvider()
        with pytest.raises(DownloadError, match="No files to merge"):
            provider._merge_gpkg_files([], Path("/tmp/out.gpkg"))

    def test_merge_gpkg_files(self, tmp_path):
        """Merge two GPKG files into one."""
        provider = Bdot10kProvider()

        # Create first GPKG
        gpkg1 = tmp_path / "one.gpkg"
        conn1 = sqlite3.connect(str(gpkg1))
        c1 = conn1.cursor()
        c1.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c1.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c1.execute("CREATE TABLE PTLZ (id INTEGER PRIMARY KEY, name TEXT)")
        c1.execute("INSERT INTO PTLZ VALUES (1, 'forest')")
        conn1.commit()
        conn1.close()

        # Create second GPKG
        gpkg2 = tmp_path / "two.gpkg"
        conn2 = sqlite3.connect(str(gpkg2))
        c2 = conn2.cursor()
        c2.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c2.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c2.execute("CREATE TABLE PTWP (id INTEGER PRIMARY KEY, name TEXT)")
        c2.execute("INSERT INTO PTWP VALUES (1, 'water')")
        conn2.commit()
        conn2.close()

        output = tmp_path / "merged.gpkg"
        provider._merge_gpkg_files([gpkg1, gpkg2], output)

        assert output.exists()
        conn = sqlite3.connect(str(output))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert "PTLZ" in tables
        assert "PTWP" in tables


# ===========================================================================
# New tests for CorineProvider
# ===========================================================================


class TestCorineProviderInit:
    """Test CorineProvider initialization."""

    def test_init_with_credentials(self):
        """Credentials with client_id + private_key -> direct mode."""
        creds = {
            "client_id": "test",
            "private_key": (
                "-----BEGIN RSA PRIVATE KEY-----\nk\n-----END RSA PRIVATE KEY-----"
            ),
            "token_uri": "https://example.com/token",
        }
        provider = CorineProvider(clms_credentials=creds)
        assert provider._clms_auth is not None
        assert provider._use_proxy is False

    def test_init_empty_credentials(self):
        """Empty dict -> no auth."""
        provider = CorineProvider(clms_credentials={})
        assert provider._clms_auth is None

    def test_init_no_proxy(self):
        """use_proxy=False without creds."""
        provider = CorineProvider(use_proxy=False)
        assert provider._use_proxy is False


class TestCorineProviderDownload:
    """Test CorineProvider download methods."""

    def test_download_by_bbox_wms_fallback(self, tmp_path):
        """No CLMS token -> WMS fallback."""
        provider = CorineProvider(use_proxy=False)
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "test.png"

        with patch.object(
            provider, "_download_via_wms", return_value=output
        ) as mock_wms:
            provider.download_by_bbox(bbox, output)
        mock_wms.assert_called_once()

    def test_download_via_wms_success(self, tmp_path):
        """WMS download returns PNG file."""
        provider = CorineProvider(use_proxy=False)
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "test.png"

        with patch.object(
            provider, "_download_with_retry", return_value=output
        ) as mock_dl:
            result = provider._download_via_wms(bbox, output, 2018, 60)

        assert result == output
        mock_dl.assert_called_once()

    def test_download_via_wms_calculates_dimensions(self, tmp_path):
        """WMS dimensions are calculated from bbox size."""
        provider = CorineProvider(use_proxy=False)
        # 10km x 10km bbox at 100m resolution -> 100 x 100 pixels
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "test.png"

        with patch.object(
            provider, "_download_with_retry", return_value=output
        ) as mock_dl:
            provider._download_via_wms(bbox, output, 2018, 60)

        call_args = mock_dl.call_args
        url = call_args.kwargs.get("url", call_args[1].get("url", ""))
        assert "WIDTH=100" in url
        assert "HEIGHT=100" in url

    def test_download_via_wms_max_size_limit(self, tmp_path):
        """Huge bbox dimensions capped at 4096."""
        provider = CorineProvider(use_proxy=False)
        # 500km x 500km -> 5000px at 100m resolution -> capped to 4096
        bbox = BBox(200000, 300000, 700000, 800000, "EPSG:2180")
        output = tmp_path / "test.png"

        with patch.object(
            provider, "_download_with_retry", return_value=output
        ) as mock_dl:
            provider._download_via_wms(bbox, output, 2018, 60)

        call_args = mock_dl.call_args
        url = call_args.kwargs.get("url", call_args[1].get("url", ""))
        assert "WIDTH=4096" in url
        assert "HEIGHT=4096" in url

    @patch("kartograf.core.sheet_parser.SheetParser")
    def test_download_by_godlo_delegates_to_bbox(self, mock_parser_cls, tmp_path):
        """download_by_godlo delegates to download_by_bbox."""
        provider = CorineProvider(use_proxy=False)
        output = tmp_path / "test.png"

        mock_parser = Mock()
        mock_parser.get_bbox.return_value = BBox(
            450000, 550000, 460000, 560000, "EPSG:2180"
        )
        mock_parser_cls.return_value = mock_parser

        with patch.object(provider, "download_by_bbox", return_value=output) as mock_dl:
            result = provider.download_by_godlo("N-34-130-D", output, year=2018)

        assert result == output
        mock_dl.assert_called_once()

    def test_download_with_retry_success(self, tmp_path):
        """Successful download on first attempt."""
        provider = CorineProvider(use_proxy=False)
        output = tmp_path / "test.png"
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.headers = {"Content-Type": "image/png"}
        mock_resp.iter_content.return_value = [b"png_data"]
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider._session = mock_session

        result = provider._download_with_retry(
            url="https://example.com/wms",
            output_path=output,
            timeout=30,
            description="test",
        )
        assert result == output

    def test_download_with_retry_wms_error_response(self, tmp_path):
        """XML content type -> DownloadError."""
        provider = CorineProvider(use_proxy=False)
        output = tmp_path / "test.png"
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.headers = {"Content-Type": "application/xml"}
        mock_resp.text = "<ServiceException>Error</ServiceException>"
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider._session = mock_session

        with pytest.raises(DownloadError, match="WMS returned error"):
            provider._download_with_retry(
                url="https://example.com/wms",
                output_path=output,
                timeout=30,
                description="test",
            )

    @patch("kartograf.providers.corine.time.sleep")
    def test_download_with_retry_all_fail(self, _sleep, tmp_path):
        """All retries fail -> DownloadError."""
        provider = CorineProvider(use_proxy=False)
        output = tmp_path / "test.png"
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("timeout")
        provider._session = mock_session

        with pytest.raises(DownloadError, match="after 3 attempts"):
            provider._download_with_retry(
                url="https://example.com/wms",
                output_path=output,
                timeout=30,
                description="test",
            )

    def test_save_response_atomic(self, tmp_path):
        """_save_response writes atomically via temp file."""
        provider = CorineProvider(use_proxy=False)
        output = tmp_path / "out.png"
        mock_resp = Mock()
        mock_resp.iter_content.return_value = [b"data"]

        provider._save_response(mock_resp, output)
        assert output.read_bytes() == b"data"
        # Temp file should not remain
        assert not output.with_suffix(".png.tmp").exists()

    def test_transform_bbox_to_wgs84(self):
        """Known EPSG:2180 bbox transforms to WGS84."""
        provider = CorineProvider(use_proxy=False)
        bbox = BBox(500000, 600000, 510000, 610000, "EPSG:2180")
        result = provider._transform_bbox_to_wgs84(bbox)
        # Should be roughly in Poland (14-25 E, 49-55 N)
        assert 14 < result[0] < 25  # min_lon
        assert 49 < result[1] < 56  # min_lat
        assert 14 < result[2] < 25  # max_lon
        assert 49 < result[3] < 56  # max_lat

    def test_transform_bbox_to_epsg3857(self):
        """Known EPSG:2180 bbox transforms to EPSG:3857."""
        provider = CorineProvider(use_proxy=False)
        bbox = BBox(500000, 600000, 510000, 610000, "EPSG:2180")
        result = provider._transform_bbox_to_epsg3857(bbox)
        # EPSG:3857 values are in millions for European coordinates
        assert result[0] > 1_000_000
        assert result[2] > result[0]
        assert result[3] > result[1]

    def test_get_available_layers(self):
        """Returns CLC_year strings."""
        provider = CorineProvider(use_proxy=False)
        layers = provider.get_available_layers()
        assert "CLC_2018" in layers
        assert "CLC_1990" in layers

    def test_get_supported_formats(self):
        """Returns PNG and GTiff."""
        provider = CorineProvider(use_proxy=False)
        formats = provider.get_supported_formats()
        assert "PNG" in formats
        assert "GTiff" in formats


# ===========================================================================
# New tests for LandCoverManager
# ===========================================================================


class TestLandCoverManagerDownload:
    """Test LandCoverManager download methods with mocks."""

    def test_download_by_teryt(self, tmp_path):
        """download_by_teryt delegates to provider."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        mock_provider.download_by_teryt.return_value = tmp_path / "out.gpkg"

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        result = manager.download_by_teryt("1465", output_path=tmp_path / "out.gpkg")

        assert result == tmp_path / "out.gpkg"
        mock_provider.download_by_teryt.assert_called_once()

    def test_download_by_teryt_auto_path(self, tmp_path):
        """download_by_teryt generates path when not provided."""
        mock_provider = Mock()
        mock_provider.name = "TestProv"
        mock_provider.download_by_teryt.return_value = tmp_path / "auto.gpkg"

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        manager.download_by_teryt("1465")

        # Check auto-generated path contains provider name and TERYT
        call_args = mock_provider.download_by_teryt.call_args
        auto_path = call_args[0][1]
        assert "TestProv" in str(auto_path)
        assert "1465" in str(auto_path)

    def test_download_by_bbox(self, tmp_path):
        """download_by_bbox delegates to provider."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        mock_provider.download_by_bbox.return_value = tmp_path / "out.gpkg"
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        result = manager.download_by_bbox(bbox, output_path=tmp_path / "out.gpkg")

        assert result == tmp_path / "out.gpkg"
        mock_provider.download_by_bbox.assert_called_once()

    def test_download_by_bbox_auto_path(self, tmp_path):
        """download_by_bbox generates path with bbox coordinates."""
        mock_provider = Mock()
        mock_provider.name = "Test"
        mock_provider.download_by_bbox.return_value = tmp_path / "auto.gpkg"
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        manager.download_by_bbox(bbox)

        call_args = mock_provider.download_by_bbox.call_args
        auto_path = call_args[0][1]
        assert "bbox" in str(auto_path)

    def test_download_by_godlo(self, tmp_path):
        """download_by_godlo delegates to provider."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        mock_provider.download_by_godlo.return_value = tmp_path / "out.gpkg"

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        result = manager.download_by_godlo(
            "N-34-130-D", output_path=tmp_path / "out.gpkg"
        )

        assert result == tmp_path / "out.gpkg"
        mock_provider.download_by_godlo.assert_called_once()

    def test_download_by_godlo_auto_path(self, tmp_path):
        """download_by_godlo generates path with godlo."""
        mock_provider = Mock()
        mock_provider.name = "Test"
        mock_provider.download_by_godlo.return_value = tmp_path / "auto.gpkg"

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        manager.download_by_godlo("N-34-130-D")

        call_args = mock_provider.download_by_godlo.call_args
        auto_path = call_args[0][1]
        assert "N-34-130-D" in str(auto_path)

    def test_download_dispatches_teryt(self, tmp_path):
        """download(teryt=...) dispatches to download_by_teryt."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        mock_provider.download_by_teryt.return_value = tmp_path / "out.gpkg"

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        manager.download(teryt="1465")

        mock_provider.download_by_teryt.assert_called_once()

    def test_download_dispatches_godlo(self, tmp_path):
        """download(godlo=...) dispatches to download_by_godlo."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        mock_provider.download_by_godlo.return_value = tmp_path / "out.gpkg"

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        manager.download(godlo="N-34-130-D")

        mock_provider.download_by_godlo.assert_called_once()

    def test_download_dispatches_bbox(self, tmp_path):
        """download(bbox=...) dispatches to download_by_bbox."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        mock_provider.download_by_bbox.return_value = tmp_path / "out.gpkg"
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        manager.download(bbox=bbox)

        mock_provider.download_by_bbox.assert_called_once()

    def test_get_available_layers(self, tmp_path):
        """get_available_layers delegates to provider."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        mock_provider.get_available_layers.return_value = ["layer1", "layer2"]

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        layers = manager.get_available_layers()

        assert layers == ["layer1", "layer2"]

    def test_get_supported_formats(self, tmp_path):
        """get_supported_formats delegates to provider."""
        mock_provider = Mock()
        mock_provider.name = "MockProvider"
        mock_provider.get_supported_formats.return_value = ["GPKG"]

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        formats = manager.get_supported_formats()

        assert formats == ["GPKG"]

    def test_generate_output_path(self, tmp_path):
        """_generate_output_path creates correct paths."""
        mock_provider = Mock()
        mock_provider.name = "Test Provider"

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)

        # By TERYT
        path = manager._generate_output_path("1465", None, None)
        assert "teryt_1465" in str(path)

        # By bbox
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        path = manager._generate_output_path(None, bbox, None)
        assert "bbox" in str(path)

        # By godlo
        path = manager._generate_output_path(None, None, "N-34-130-D")
        assert "godlo_N-34-130-D" in str(path)


# ===========================================================================
# Tests for rtree spatial index preservation during GPKG merge
# ===========================================================================


def _create_gpkg_with_rtree(path: Path, table_name: str, geom_col: str = "geom"):
    """Helper: create a minimal GPKG with an rtree spatial index."""
    conn = sqlite3.connect(str(path))
    c = conn.cursor()
    c.execute(
        "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
        "identifier TEXT, description TEXT, last_change TEXT, "
        "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
    )
    c.execute(
        "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
        "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
    )
    c.execute(
        f"INSERT INTO gpkg_geometry_columns VALUES "
        f"('{table_name}', '{geom_col}', 'POLYGON', 2180, 0, 0)"
    )
    c.execute(
        f"INSERT INTO gpkg_contents VALUES "
        f"('{table_name}', 'features', '{table_name}', '', '', "
        f"0.0, 0.0, 1.0, 1.0, 2180)"
    )
    c.execute(
        f"CREATE TABLE [{table_name}] "
        f"(fid INTEGER PRIMARY KEY, [{geom_col}] BLOB, name TEXT)"
    )
    c.execute(f"INSERT INTO [{table_name}] VALUES (1, X'00', 'test')")
    # Create rtree
    rtree_name = f"rtree_{table_name}_{geom_col}"
    c.execute(
        f"CREATE VIRTUAL TABLE [{rtree_name}] USING rtree(id, minx, maxx, miny, maxy)"
    )
    c.execute(f"INSERT INTO [{rtree_name}] VALUES (1, 0.0, 1.0, 0.0, 1.0)")
    # Create gpkg_extensions entry
    c.execute(
        "CREATE TABLE gpkg_extensions ("
        "table_name TEXT, column_name TEXT, extension_name TEXT, "
        "definition TEXT, scope TEXT)"
    )
    c.execute(
        f"INSERT INTO gpkg_extensions VALUES "
        f"('{table_name}', '{geom_col}', 'gpkg_rtree_index', "
        f"'http://www.geopackage.org/spec120/#extension_rtree', 'write-only')"
    )
    conn.commit()
    conn.close()


class TestBdot10kRtreeIndex:
    """Test rtree spatial index preservation during GPKG merge."""

    def test_merge_preserves_rtree_indices(self, tmp_path):
        """Merge 2 GPKGs with rtree — both should have indices in output."""
        provider = Bdot10kProvider()

        gpkg1 = tmp_path / "one.gpkg"
        _create_gpkg_with_rtree(gpkg1, "PTLZ")

        gpkg2 = tmp_path / "two.gpkg"
        _create_gpkg_with_rtree(gpkg2, "PTWP")

        output = tmp_path / "merged.gpkg"
        provider._merge_gpkg_files([gpkg1, gpkg2], output)

        conn = sqlite3.connect(str(output))
        cursor = conn.cursor()

        # Check that rtree for PTWP (copied layer) exists
        cursor.execute("SELECT name FROM sqlite_master WHERE name='rtree_PTWP_geom'")
        assert cursor.fetchone() is not None, "rtree_PTWP_geom should exist"

        # Check rtree has data
        cursor.execute("SELECT COUNT(*) FROM rtree_PTWP_geom")
        assert cursor.fetchone()[0] == 1

        # Base file rtree should also be intact
        cursor.execute("SELECT name FROM sqlite_master WHERE name='rtree_PTLZ_geom'")
        assert cursor.fetchone() is not None, "rtree_PTLZ_geom should exist"

        conn.close()

    def test_copy_rtree_no_geometry(self, tmp_path):
        """Table without geometry — no error, no rtree created."""
        provider = Bdot10kProvider()

        gpkg1 = tmp_path / "base.gpkg"
        conn1 = sqlite3.connect(str(gpkg1))
        c1 = conn1.cursor()
        c1.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c1.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c1.execute("CREATE TABLE dummy (id INTEGER PRIMARY KEY)")
        conn1.commit()
        conn1.close()

        # Create source with table that has no geometry
        gpkg2 = tmp_path / "src.gpkg"
        conn2 = sqlite3.connect(str(gpkg2))
        c2 = conn2.cursor()
        c2.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c2.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c2.execute("CREATE TABLE no_geom_table (id INTEGER PRIMARY KEY, val TEXT)")
        conn2.commit()
        conn2.close()

        output = tmp_path / "merged.gpkg"
        provider._merge_gpkg_files([gpkg1, gpkg2], output)

        conn = sqlite3.connect(str(output))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE name LIKE 'rtree_%'")
        assert cursor.fetchone() is None  # No rtree should be created
        conn.close()

    def test_copy_rtree_no_index_in_source(self, tmp_path):
        """Geometry but no rtree in source — no error."""
        provider = Bdot10kProvider()

        gpkg1 = tmp_path / "base.gpkg"
        conn1 = sqlite3.connect(str(gpkg1))
        c1 = conn1.cursor()
        c1.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c1.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c1.execute("CREATE TABLE dummy (id INTEGER PRIMARY KEY)")
        conn1.commit()
        conn1.close()

        # Source has geometry columns entry but no rtree virtual table
        gpkg2 = tmp_path / "src.gpkg"
        conn2 = sqlite3.connect(str(gpkg2))
        c2 = conn2.cursor()
        c2.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c2.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c2.execute(
            "INSERT INTO gpkg_geometry_columns VALUES "
            "('PTLZ', 'geom', 'POLYGON', 2180, 0, 0)"
        )
        c2.execute(
            "INSERT INTO gpkg_contents VALUES "
            "('PTLZ', 'features', 'PTLZ', '', '', 0, 0, 1, 1, 2180)"
        )
        c2.execute("CREATE TABLE PTLZ (fid INTEGER PRIMARY KEY, geom BLOB)")
        conn2.commit()
        conn2.close()

        output = tmp_path / "merged.gpkg"
        provider._merge_gpkg_files([gpkg1, gpkg2], output)

        conn = sqlite3.connect(str(output))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE name LIKE 'rtree_%'")
        assert cursor.fetchone() is None  # No rtree should be created
        conn.close()

    def test_copy_rtree_gpkg_extensions_copied(self, tmp_path):
        """gpkg_extensions entry for rtree is copied."""
        provider = Bdot10kProvider()

        gpkg1 = tmp_path / "base.gpkg"
        _create_gpkg_with_rtree(gpkg1, "PTLZ")

        gpkg2 = tmp_path / "src.gpkg"
        _create_gpkg_with_rtree(gpkg2, "PTWP")

        output = tmp_path / "merged.gpkg"
        provider._merge_gpkg_files([gpkg1, gpkg2], output)

        conn = sqlite3.connect(str(output))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM gpkg_extensions "
            "WHERE table_name='PTWP' AND extension_name='gpkg_rtree_index'"
        )
        row = cursor.fetchone()
        assert row is not None, "gpkg_extensions entry for PTWP rtree should exist"
        conn.close()

    def test_base_file_rtree_preserved(self, tmp_path):
        """First file's rtree still works after merge."""
        provider = Bdot10kProvider()

        gpkg1 = tmp_path / "base.gpkg"
        _create_gpkg_with_rtree(gpkg1, "PTLZ")

        gpkg2 = tmp_path / "src.gpkg"
        _create_gpkg_with_rtree(gpkg2, "PTWP")

        output = tmp_path / "merged.gpkg"
        provider._merge_gpkg_files([gpkg1, gpkg2], output)

        conn = sqlite3.connect(str(output))
        cursor = conn.cursor()
        # Query the base file's rtree — should work
        cursor.execute(
            "SELECT * FROM rtree_PTLZ_geom WHERE minx <= 0.5 AND maxx >= 0.5"
        )
        results = cursor.fetchall()
        assert len(results) == 1
        conn.close()


# ===========================================================================
# Tests for BDOT10k hydro category support
# ===========================================================================


class TestBdot10kCategory:
    """Test BDOT10k category-based layer extraction."""

    def test_category_filters_mapping(self):
        """Verify CATEGORY_FILTERS constant."""
        assert "pt" in Bdot10kProvider.CATEGORY_FILTERS
        assert "hydro" in Bdot10kProvider.CATEGORY_FILTERS
        assert "_PT" in Bdot10kProvider.CATEGORY_FILTERS["pt"]
        assert "_SW" in Bdot10kProvider.CATEGORY_FILTERS["hydro"]
        assert "_PTWP" in Bdot10kProvider.CATEGORY_FILTERS["hydro"]

    def test_hydro_layers_list(self):
        """Verify HYDRO_LAYERS constant."""
        assert "SWRS" in Bdot10kProvider.HYDRO_LAYERS
        assert "SWKN" in Bdot10kProvider.HYDRO_LAYERS
        assert "SWRM" in Bdot10kProvider.HYDRO_LAYERS
        assert "PTWP" in Bdot10kProvider.HYDRO_LAYERS

    def test_extract_category_pt_default(self, tmp_path):
        """Default category extracts only PT* files."""
        provider = Bdot10kProvider()
        output = tmp_path / "merged.gpkg"

        # Create GPKG files for both PT and SW layers
        gpkg_pt = tmp_path / "temp_PTLZ.gpkg"
        conn = sqlite3.connect(str(gpkg_pt))
        c = conn.cursor()
        c.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c.execute("CREATE TABLE PTLZ (id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("INSERT INTO PTLZ VALUES (1, 'forest')")
        conn.commit()
        conn.close()

        gpkg_sw = tmp_path / "temp_SWRS.gpkg"
        conn2 = sqlite3.connect(str(gpkg_sw))
        c2 = conn2.cursor()
        c2.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c2.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c2.execute("CREATE TABLE SWRS (id INTEGER PRIMARY KEY, name TEXT)")
        c2.execute("INSERT INTO SWRS VALUES (1, 'river')")
        conn2.commit()
        conn2.close()

        # Create ZIP with both
        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            with open(gpkg_pt, "rb") as f:
                zf.writestr("data/BDOT10k_PTLZ.gpkg", f.read())
            with open(gpkg_sw, "rb") as f:
                zf.writestr("data/BDOT10k_SWRS.gpkg", f.read())
        zip_buf.seek(0)

        mock_resp = Mock()
        mock_resp.iter_content.return_value = [zip_buf.getvalue()]

        # Default category="pt" should only extract PT*
        provider._extract_gpkg_from_zip(mock_resp, output)
        out_gpkg = output.with_suffix(".gpkg")
        assert out_gpkg.exists()

        conn = sqlite3.connect(str(out_gpkg))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'rtree_%'"
        )
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert "PTLZ" in tables
        assert "SWRS" not in tables

    def test_extract_category_hydro(self, tmp_path):
        """Hydro category extracts SW* + PTWP files."""
        provider = Bdot10kProvider()
        output = tmp_path / "merged.gpkg"

        # Create SW GPKG
        gpkg_sw = tmp_path / "temp_SWRS.gpkg"
        conn = sqlite3.connect(str(gpkg_sw))
        c = conn.cursor()
        c.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c.execute("CREATE TABLE SWRS (id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("INSERT INTO SWRS VALUES (1, 'river')")
        conn.commit()
        conn.close()

        # Create PT GPKG (should not be extracted)
        gpkg_pt = tmp_path / "temp_PTLZ.gpkg"
        conn2 = sqlite3.connect(str(gpkg_pt))
        c2 = conn2.cursor()
        c2.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c2.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c2.execute("CREATE TABLE PTLZ (id INTEGER PRIMARY KEY, name TEXT)")
        c2.execute("INSERT INTO PTLZ VALUES (1, 'forest')")
        conn2.commit()
        conn2.close()

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            with open(gpkg_sw, "rb") as f:
                zf.writestr("data/BDOT10k_SWRS.gpkg", f.read())
            with open(gpkg_pt, "rb") as f:
                zf.writestr("data/BDOT10k_PTLZ.gpkg", f.read())
        zip_buf.seek(0)

        mock_resp = Mock()
        mock_resp.iter_content.return_value = [zip_buf.getvalue()]

        provider._extract_gpkg_from_zip(mock_resp, output, category="hydro")
        out_gpkg = output.with_suffix(".gpkg")

        conn = sqlite3.connect(str(out_gpkg))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'rtree_%'"
        )
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert "SWRS" in tables
        assert "PTLZ" not in tables

    def test_extract_category_hydro_includes_ptwp(self, tmp_path):
        """PTWP is included in hydro category."""
        provider = Bdot10kProvider()
        output = tmp_path / "merged.gpkg"

        gpkg_ptwp = tmp_path / "temp_PTWP.gpkg"
        conn = sqlite3.connect(str(gpkg_ptwp))
        c = conn.cursor()
        c.execute(
            "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT, "
            "identifier TEXT, description TEXT, last_change TEXT, "
            "min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER)"
        )
        c.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, "
            "geometry_type_name TEXT, srs_id INTEGER, z INTEGER, m INTEGER)"
        )
        c.execute("CREATE TABLE PTWP (id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("INSERT INTO PTWP VALUES (1, 'lake')")
        conn.commit()
        conn.close()

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf, open(gpkg_ptwp, "rb") as f:
            zf.writestr("data/BDOT10k_PTWP.gpkg", f.read())
        zip_buf.seek(0)

        mock_resp = Mock()
        mock_resp.iter_content.return_value = [zip_buf.getvalue()]

        provider._extract_gpkg_from_zip(mock_resp, output, category="hydro")
        out_gpkg = output.with_suffix(".gpkg")

        conn = sqlite3.connect(str(out_gpkg))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'rtree_%'"
        )
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()

        assert "PTWP" in tables

    def test_download_by_teryt_passes_category(self, tmp_path):
        """category kwarg flows through download_by_teryt."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"

        with patch.object(
            provider, "_download_with_retry", return_value=output
        ) as mock_dl:
            provider.download_by_teryt("1465", output, category="hydro")

        call_kwargs = mock_dl.call_args
        assert call_kwargs.kwargs.get("category") == "hydro"

    def test_download_by_teryt_invalid_category(self, tmp_path):
        """Invalid category raises ValueError."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"

        with pytest.raises(ValueError, match="Unknown category"):
            provider.download_by_teryt("1465", output, category="invalid")

    @patch("kartograf.core.sheet_parser.SheetParser")
    def test_download_by_godlo_passes_category(self, mock_parser_cls, tmp_path):
        """category kwarg flows through download_by_godlo."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"

        mock_parser = Mock()
        mock_parser.get_bbox.return_value = BBox(
            450000, 550000, 460000, 560000, "EPSG:2180"
        )
        mock_parser_cls.return_value = mock_parser

        with (
            patch.object(provider, "_get_teryt_for_point", return_value="1465"),
            patch.object(provider, "download_by_teryt", return_value=output) as mock_dl,
        ):
            provider.download_by_godlo("N-34-130-D", output, category="hydro")

        call_kwargs = mock_dl.call_args
        assert call_kwargs.kwargs.get("category") == "hydro"

    def test_download_by_bbox_passes_category(self, tmp_path):
        """category kwarg flows through download_by_bbox."""
        provider = Bdot10kProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "out.gpkg"

        with (
            patch.object(provider, "_get_teryt_for_point", return_value="1465"),
            patch.object(provider, "download_by_teryt", return_value=output) as mock_dl,
        ):
            provider.download_by_bbox(bbox, output, category="hydro")

        call_kwargs = mock_dl.call_args
        assert call_kwargs.kwargs.get("category") == "hydro"

    def test_get_available_layers_hydro(self):
        """get_available_layers("hydro") returns HYDRO_LAYERS."""
        provider = Bdot10kProvider()
        layers = provider.get_available_layers("hydro")
        assert "SWRS" in layers
        assert "SWKN" in layers
        assert "SWRM" in layers
        assert "PTWP" in layers

    def test_get_layer_description_hydro(self):
        """Hydro layers have descriptions."""
        provider = Bdot10kProvider()
        assert provider.get_layer_description("SWRS") == "Rzeki i strumienie"
        assert provider.get_layer_description("SWKN") == "Kanały"
        assert provider.get_layer_description("SWRM") == "Rowy melioracyjne"
