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
from kartograf.providers.base import LandCoverProvider
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import (
    WOJEWODZTWO_NAMES,
    Bdot10kProvider,
)
from kartograf.transform.bbox import envelope_from_2180


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
        assert len(layers) == 15

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

    def test_supported_formats_excludes_gml(self):
        """GML was advertised but never implemented (phantom format)."""
        provider = Bdot10kProvider()
        formats = provider.get_supported_formats()
        assert formats == ["GPKG", "SHP"]
        assert "GML" not in formats

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
        bounds = envelope_from_2180(bbox, "EPSG:3857")
        url = provider._construct_wms_url(bounds, 2018, 100, 100)
        assert "WMS" in url
        assert "GetMap" in url
        assert "discomap.eea.europa.eu" in url  # EEA Discomap endpoint
        assert "CLC2018" in url

    def test_construct_wms_url_dlr_fallback(self):
        """Test WMS URL construction for DLR fallback (1990)."""
        provider = CorineProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        bounds = envelope_from_2180(bbox, "EPSG:4326")
        url = provider._construct_wms_url(bounds, 1990, 100, 100)
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
        assert "GML" not in captured.out

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
        # podpowiedz "Expected" idzie na stderr razem z bledem (review-1 D4)
        assert "Expected" in captured.err
        assert "Expected" not in captured.out

    @pytest.mark.parametrize(
        "bbox",
        ["10,10,5,5", "1,10,5,5", "nan,1,2,3", "1,2,inf,4", "1,2,3", "1,2,3,4,5"],
    )
    def test_landcover_download_rejects_bad_bbox(self, bbox, capsys, tmp_path):
        """Odwrocony/NaN/inf/zla liczba wartosci -> Error na stderr, kod 1 (K7a)."""
        from kartograf.cli.commands import main

        with patch("kartograf.cli.landcover_cmd.LandCoverManager") as manager:
            result = main(
                ["landcover", "download", f"--bbox={bbox}", "-o", str(tmp_path)]
            )
        assert result == 1
        manager.assert_not_called()
        captured = capsys.readouterr()
        assert "Error: Invalid bbox format" in captured.err
        assert "ValueError" not in captured.err
        assert "Expected" not in captured.out


class TestLandCoverInvalidOptions:
    """Bledny --property/--year/--depth/--stat to blad UZYTKOWNIKA (N8).

    `Error: <tresc>` bez nazwy typu wyjatku i bez podpowiedzi KARTOGRAF_DEBUG
    (ta jest dla bledow wewnetrznych), kod 1, przed siecia (conftest blokuje
    gniazda — proba polaczenia wywrocilaby test).
    """

    @pytest.mark.parametrize(
        ("extra", "fragment"),
        [
            (["--source", "soilgrids", "--property", "foo"], "Invalid property"),
            (["--source", "soilgrids", "--depth", "1-2cm"], "Invalid depth"),
            (["--source", "soilgrids", "--stat", "median"], "Invalid stat"),
            (["--source", "corine", "--year", "1999"], "1999"),
        ],
    )
    def test_invalid_option_is_user_error(self, extra, fragment, tmp_path, capsys):
        from kartograf.cli.commands import main

        rc = main(
            ["landcover", "download", "--godlo", "N-34-130-D", "-o", str(tmp_path)]
            + extra
        )
        err = capsys.readouterr().err
        assert rc == 1
        assert fragment in err
        assert "Error: " in err
        assert "ValueError" not in err
        assert "KARTOGRAF_DEBUG" not in err


class TestBdot10kShpFormat:
    """`--format SHP`: archiwum ZIP z shapefile'ami nie moze udawac `.gpkg` (N1)."""

    SHP_ZIP = b"PK\x03\x04 udawany ZIP z plikami .shp"

    def _session(self):
        response = Mock()
        response.raise_for_status = Mock()
        response.iter_content = lambda chunk_size: iter([self.SHP_ZIP])
        session = Mock()
        session.get.return_value = response
        return session

    def test_cli_saves_shp_package_as_zip(self, tmp_path, capsys):
        from kartograf.cli.commands import main

        session = self._session()
        with patch("kartograf.transport.http.make_gugik_session", return_value=session):
            rc = main(
                [
                    "landcover",
                    "download",
                    "--source",
                    "bdot10k",
                    "--teryt",
                    "1465",
                    "--format",
                    "SHP",
                    "-o",
                    str(tmp_path),
                ]
            )
        assert rc == 0
        assert session.get.call_args[0][0].endswith("/SHP/14/1465_SHP.zip")
        expected = tmp_path / "bdot10k_teryt_1465.zip"
        assert expected.read_bytes().startswith(b"PK")
        assert (tmp_path / "bdot10k_teryt_1465.zip.meta.json").exists()
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "bdot10k_teryt_1465.zip",
            "bdot10k_teryt_1465.zip.meta.json",
        ]
        assert f"Downloaded to: {expected}" in capsys.readouterr().out

    def test_provider_returns_zip_path_for_shp(self, tmp_path):
        provider = Bdot10kProvider(session=self._session())
        result = provider.download_by_admin_unit(
            "1465", tmp_path / "powiat.gpkg", format="SHP"
        )
        assert result == tmp_path / "powiat.zip"
        assert result.read_bytes() == self.SHP_ZIP
        assert not (tmp_path / "powiat.gpkg").exists()


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

        with patch(
            "kartograf.providers.pl.bdot10k.download_to", return_value=output
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
            patch.object(
                provider, "download_by_admin_unit", return_value=output
            ) as mock_dl,
        ):
            result = provider.download_by_godlo("N-34-130-D", output)

        assert result == output
        mock_dl.assert_called_once()

    def test_download_by_admin_unit_returns_existing_gpkg_path(self, tmp_path):
        """download_by_admin_unit must return the path that was actually
        written to disk (the merged .gpkg), not the .zip target path that
        _extract_gpkg_from_zip never creates.
        """
        provider = Bdot10kProvider()

        # Minimal single-table GPKG, same recipe as test_extract_gpkg_from_zip.
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

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf, open(gpkg_path, "rb") as f:
            zf.writestr("data/BDOT10k_PTLZ.gpkg", f.read())

        mock_resp = Mock()
        mock_resp.iter_content.return_value = [zip_buf.getvalue()]
        mock_resp.raise_for_status = Mock()

        mock_session = Mock()
        mock_session.get.return_value = mock_resp
        provider._sessions.injected = mock_session

        output_zip = tmp_path / "powiat_1465.zip"
        result = provider.download_by_admin_unit("1465", output_zip)

        assert result == tmp_path / "powiat_1465.gpkg"
        assert result.exists()

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
        provider._sessions.injected = mock_session

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
        provider._sessions.injected = mock_session

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
        provider._sessions.injected = mock_session

        with pytest.raises(DownloadError, match="Could not determine TERYT"):
            provider._get_teryt_for_point(500000, 600000)

    @patch("kartograf.transport.http.time.sleep")
    def test_get_teryt_for_point_network_error(self, _sleep):
        """Network error -> DownloadError (po 3 probach get_with_retry)."""
        provider = Bdot10kProvider()
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("timeout")
        provider._sessions.injected = mock_session

        with pytest.raises(DownloadError, match="WMS GetFeatureInfo failed"):
            provider._get_teryt_for_point(500000, 600000)


class TestBdot10kRetryAndIO:
    """Test retry, save, extract, merge."""

    def test_download_shp_success(self, tmp_path):
        """Paczka SHP pobrana za pierwszym razem: strumien zapisany w .zip."""
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.iter_content.return_value = [b"shp_data"]
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider = Bdot10kProvider(session=mock_session)

        result = provider.download_by_admin_unit(
            "1465", tmp_path / "out.shp", format="SHP"
        )
        assert result == tmp_path / "out.zip"
        assert result.read_bytes() == b"shp_data"

    @patch("kartograf.transport.http.time.sleep")
    def test_download_all_fail(self, _sleep, tmp_path):
        """All retries fail -> DownloadError."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("fail")
        provider = Bdot10kProvider(session=mock_session)

        with pytest.raises(DownloadError, match="po 3 probach"):
            provider.download_by_admin_unit("1465", tmp_path / "out.shp", format="SHP")
        assert mock_session.get.call_count == 3
        assert list(tmp_path.iterdir()) == []

    def test_download_writes_all_chunks(self, tmp_path):
        """Wszystkie fragmenty odpowiedzi trafiaja do pliku, bez resztek .tmp."""
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider = Bdot10kProvider(session=mock_session)

        output = provider.download_by_admin_unit(
            "1465", tmp_path / "out.gpkg", format="SHP"
        )
        assert output.read_bytes() == b"chunk1chunk2"
        assert [p.name for p in tmp_path.iterdir()] == ["out.zip"]

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

    def test_merge_overwrites_existing_gpkg_like_windows(self, tmp_path):
        """Scalony GPKG nadpisuje stary plik takze przy semantyce Windows."""
        import os

        provider = Bdot10kProvider()
        gpkg_path = tmp_path / "PTLZ.gpkg"
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
        conn.commit()
        conn.close()
        output = tmp_path / "out" / "merged.gpkg"
        output.parent.mkdir()
        output.write_bytes(b"stary plik")

        def windows_rename(self, target):
            if Path(target).exists():
                raise FileExistsError(f"[WinError 183] {target}")
            return os.replace(self, target)

        with patch.object(Path, "rename", windows_rename):
            provider._merge_gpkg_files([gpkg_path], output)
        assert output.read_bytes().startswith(b"SQLite format 3")
        assert [p.name for p in output.parent.iterdir()] == ["merged.gpkg"]

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

    def test_env_var_does_not_enable_direct_mode(self, monkeypatch):
        """CLMS_CREDENTIALS w env NIE wlacza trybu direct (ADR-002).

        Credentials z env sa konsumowane wylacznie przez podproces auth
        proxy (kartograf.auth.proxy) — nigdy przez CorineProvider.__init__
        bezposrednio. Przypina to, ze usuniecie martwego bloku
        get_clms_credentials()/Keychain w corine.py (zad. 20 audytu
        0.7.0) nie zmienia tego zachowania.
        """
        monkeypatch.setenv("CLMS_CREDENTIALS", '{"client_id": "x"}')
        provider = CorineProvider()
        assert provider._use_proxy is True
        assert provider._clms_auth is None


def _wms_bbox(url):
    """Wartosc parametru BBOX z URL GetMap jako cztery liczby."""
    from urllib.parse import parse_qs, urlparse

    return tuple(float(v) for v in parse_qs(urlparse(url).query)["BBOX"][0].split(","))


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

        with patch(
            "kartograf.providers.corine.download_to", return_value=output
        ) as mock_dl:
            result = provider._download_via_wms(bbox, output, 2018, 60)

        assert result == output
        mock_dl.assert_called_once()

    def test_download_via_wms_calculates_dimensions(self, tmp_path):
        """WMS dimensions are calculated from bbox size."""
        import re

        provider = CorineProvider(use_proxy=False)
        # 10km x 10km bbox at 100m resolution -> 100 x ~100 pixels
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "test.png"

        with patch(
            "kartograf.providers.corine.download_to", return_value=output
        ) as mock_dl:
            provider._download_via_wms(bbox, output, 2018, 60)

        url = mock_dl.call_args.args[1]
        assert "WIDTH=100" in url
        # Height follows the EPSG:3857 envelope, which is not an exact square
        height = int(re.search(r"HEIGHT=(\d+)", url).group(1))
        assert 98 <= height <= 102

    def test_download_via_wms_dlr_height_from_metric_aspect(self, tmp_path):
        """DLR (1990, EPSG:4326 BBOX): height keeps the ground resolution.

        Plate carree is not conformal - a pixel that is square in degrees is
        1/cos(lat) taller on the ground, so the aspect ratio must come from
        the metric (EPSG:3857) envelope, not from the degrees sent as BBOX.
        """
        import re

        provider = CorineProvider(use_proxy=False)
        # 10km x 10km bbox at 100m resolution -> 100 x ~100 pixels
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        output = tmp_path / "test.png"

        with patch(
            "kartograf.providers.corine.download_to", return_value=output
        ) as mock_dl:
            provider._download_via_wms(bbox, output, 1990, 60)

        url = mock_dl.call_args.args[1]
        assert "geoservice.dlr.de" in url  # DLR branch, BBOX in degrees
        assert "WIDTH=100" in url
        height = int(re.search(r"HEIGHT=(\d+)", url).group(1))
        assert 98 <= height <= 102

    def test_download_via_wms_max_size_limit(self, tmp_path):
        """Huge bbox dimensions capped at 4096."""
        provider = CorineProvider(use_proxy=False)
        # 500km x 500km -> 5000px at 100m resolution -> capped to 4096
        bbox = BBox(200000, 300000, 700000, 800000, "EPSG:2180")
        output = tmp_path / "test.png"

        with patch(
            "kartograf.providers.corine.download_to", return_value=output
        ) as mock_dl:
            provider._download_via_wms(bbox, output, 2018, 60)

        url = mock_dl.call_args.args[1]
        assert "WIDTH=4096" in url
        assert "HEIGHT=4096" in url

    def test_download_via_wms_aspect_matches_bbox_3857(self, tmp_path):
        """Pixel aspect ratio matches the EPSG:3857 BBOX sent to the WMS."""
        import re
        from urllib.parse import unquote

        from kartograf.core.sheet_parser import SheetParser

        provider = CorineProvider(use_proxy=False)
        bbox = SheetParser("N-34-130-D").get_bbox("EPSG:2180")
        output = tmp_path / "test.png"

        with patch(
            "kartograf.providers.corine.download_to", return_value=output
        ) as mock_dl:
            provider._download_via_wms(bbox, output, 2018, 60)

        url = mock_dl.call_args.args[1]
        width = int(re.search(r"WIDTH=(\d+)", url).group(1))
        height = int(re.search(r"HEIGHT=(\d+)", url).group(1))
        bx_min, by_min, bx_max, by_max = (
            float(v)
            for v in unquote(re.search(r"BBOX=([^&]+)", url).group(1)).split(",")
        )
        aspect_px = width / height
        aspect_bbox = (bx_max - bx_min) / (by_max - by_min)
        assert abs(aspect_px - aspect_bbox) < 0.02

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

    _BBOX = BBox(450000, 550000, 460000, 560000, "EPSG:2180")

    def test_download_via_wms_writes_png(self, tmp_path):
        """Podglad WMS pobrany za pierwszym razem trafia do .png."""
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.headers = {"Content-Type": "image/png"}
        mock_resp.iter_content.return_value = [b"png_data"]
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider = CorineProvider(session=mock_session, use_proxy=False)

        result = provider._download_via_wms(self._BBOX, tmp_path / "t.tif", 2018, 30)
        assert result == tmp_path / "t.png"
        assert result.read_bytes() == b"png_data"
        # zapis atomowy: zadnych resztek pliku tymczasowego
        assert [p.name for p in tmp_path.iterdir()] == ["t.png"]

    @patch("kartograf.transport.http.time.sleep")
    def test_download_via_wms_error_response(self, sleep, tmp_path):
        """XML content type -> DownloadError bez ponowien i bez pliku."""
        mock_session = Mock()
        mock_resp = Mock()
        mock_resp.headers = {"Content-Type": "application/xml"}
        mock_resp.text = "<ServiceException>Error</ServiceException>"
        mock_resp.raise_for_status = Mock()
        mock_session.get.return_value = mock_resp
        provider = CorineProvider(session=mock_session, use_proxy=False)

        with pytest.raises(DownloadError, match="WMS returned error"):
            provider._download_via_wms(self._BBOX, tmp_path / "t.png", 2018, 30)
        assert mock_session.get.call_count == 1
        sleep.assert_not_called()
        assert list(tmp_path.iterdir()) == []

    @patch("kartograf.transport.http.time.sleep")
    def test_download_via_wms_all_fail(self, _sleep, tmp_path):
        """All retries fail -> DownloadError."""
        mock_session = Mock()
        mock_session.get.side_effect = requests.RequestException("timeout")
        provider = CorineProvider(session=mock_session, use_proxy=False)

        with pytest.raises(DownloadError, match="po 3 probach"):
            provider._download_via_wms(self._BBOX, tmp_path / "t.png", 2018, 30)
        assert mock_session.get.call_count == 3

    def test_transform_bbox_to_wgs84(self):
        """Known EPSG:2180 bbox transforms to WGS84."""
        bbox = BBox(500000, 600000, 510000, 610000, "EPSG:2180")
        result = envelope_from_2180(bbox, "EPSG:4326")
        # Should be roughly in Poland (14-25 E, 49-55 N)
        assert 14 < result[0] < 25  # min_lon
        assert 49 < result[1] < 56  # min_lat
        assert 14 < result[2] < 25  # max_lon
        assert 49 < result[3] < 56  # max_lat

    def test_transform_bbox_to_epsg3857(self):
        """Known EPSG:2180 bbox transforms to EPSG:3857."""
        bbox = BBox(500000, 600000, 510000, 610000, "EPSG:2180")
        result = envelope_from_2180(bbox, "EPSG:3857")
        # EPSG:3857 values are in millions for European coordinates
        assert result[0] > 1_000_000
        assert result[2] > result[0]
        assert result[3] > result[1]

    def test_wms_dlr_bbox_covers_all_corners(self, tmp_path):
        """Envelope covers all four corners, not only SW and NE."""
        from pyproj import Transformer

        from kartograf.core.sheet_parser import SheetParser

        bbox = SheetParser("N-34-130-D").get_bbox("EPSG:2180")
        # tor providera: DLR (1990) wysyla BBOX w EPSG:4326 (WMS 1.1.1, lon/lat)
        provider = CorineProvider(use_proxy=False)
        with patch("kartograf.providers.corine.download_to") as dl:
            provider._download_via_wms(bbox, tmp_path / "x.png", 1990, 30)
        min_lon, min_lat, max_lon, max_lat = _wms_bbox(dl.call_args.args[1])

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

    def test_wms_eea_bbox_covers_all_corners(self, tmp_path):
        """Envelope covers all four corners, not only SW and NE."""
        from pyproj import Transformer

        from kartograf.core.sheet_parser import SheetParser

        bbox = SheetParser("N-34-130-D").get_bbox("EPSG:2180")
        # tor providera: EEA (2018) wysyla BBOX w EPSG:3857
        provider = CorineProvider(use_proxy=False)
        with patch("kartograf.providers.corine.download_to") as dl:
            provider._download_via_wms(bbox, tmp_path / "x.png", 2018, 30)
        min_x, min_y, max_x, max_y = _wms_bbox(dl.call_args.args[1])

        transformer = Transformer.from_crs("EPSG:2180", "EPSG:3857", always_xy=True)
        for x, y in (
            (bbox.min_x, bbox.min_y),
            (bbox.min_x, bbox.max_y),
            (bbox.max_x, bbox.min_y),
            (bbox.max_x, bbox.max_y),
        ):
            merc_x, merc_y = transformer.transform(x, y)
            assert min_x <= merc_x <= max_x, f"corner {(x, y)}: x outside envelope"
            assert min_y <= merc_y <= max_y, f"corner {(x, y)}: y outside envelope"

        # Two corners span 30244 m of northing, the true envelope 33406 m.
        assert max_y - min_y > 33000

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
        assert "testprov" in str(auto_path).lower()
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

    @pytest.mark.parametrize(
        "call_kwargs,method_name",
        [
            ({"godlo": "N-34-130-D"}, "godlo"),
            ({"teryt": "1465"}, "teryt"),
            (
                {"bbox": BBox(500000, 300000, 510000, 310000, "EPSG:2180")},
                "bbox",
            ),
        ],
    )
    def test_download_and_download_by_x_generate_same_path(
        self, tmp_path, call_kwargs, method_name
    ):
        """download() i download_by_* musza generowac identyczne sciezki bez spacji."""
        mock_provider = Mock()
        mock_provider.name = "CORINE Land Cover"
        provider_method = getattr(mock_provider, f"download_by_{method_name}")
        provider_method.return_value = tmp_path / "out.gpkg"

        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)

        with patch.object(manager, "_write_sidecar"):
            manager.download(**call_kwargs)
        path_via_download = provider_method.call_args[0][1]

        provider_method.reset_mock()
        manager_method = getattr(manager, f"download_by_{method_name}")
        manager_method(**call_kwargs)
        path_via_download_by = provider_method.call_args[0][1]

        assert path_via_download == path_via_download_by
        assert " " not in str(path_via_download)
        assert " " not in str(path_via_download_by)

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


class TestAdminUnitAliases:
    """Etap 0 (spec 6.7): kanoniczne download_by_admin_unit + aliasy teryt."""

    def test_validate_admin_unit_same_as_teryt(self):
        provider = Bdot10kProvider()
        assert provider.validate_admin_unit("1465") is True
        assert provider.validate_admin_unit("123") is False
        assert provider.validate_teryt("1465") is provider.validate_admin_unit("1465")

    def test_download_by_teryt_delegates_to_admin_unit(self, tmp_path):
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"
        with patch.object(
            provider, "download_by_admin_unit", return_value=output
        ) as mock_new:
            result = provider.download_by_teryt("1465", output, timeout=99)
        mock_new.assert_called_once_with("1465", output, timeout=99)
        assert result == output

    def test_source_url_aliases_base_url(self):
        provider = Bdot10kProvider()
        assert provider.source_url == provider.base_url

    def test_data_source_provider_hierarchy(self):
        from kartograf.providers.base import BaseProvider, DataSourceProvider

        assert issubclass(LandCoverProvider, DataSourceProvider)
        assert issubclass(BaseProvider, DataSourceProvider)
        assert DataSourceProvider.descriptor_key is None


class TestSidecarLandCover:
    """Sidecar .meta.json po pobraniu pokrycia terenu (spec etap 0)."""

    def test_download_by_teryt_writes_sidecar(self, tmp_path):
        mock_provider = Mock()
        mock_provider.name = "BDOT10k"
        mock_provider.descriptor_key = "pl.gugik.bdot10k"
        out = tmp_path / "out.gpkg"

        def fake(teryt, output_path, **kwargs):
            out.write_bytes(b"GPKG")
            return out

        mock_provider.download_by_teryt.side_effect = fake
        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        result = manager.download_by_teryt("1465", output_path=out)
        sidecar = result.parent / f"{result.name}.meta.json"
        assert sidecar.exists()
        import json

        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload["dataset"] == "pl.gugik.bdot10k"
        assert payload["request"] == {"teryt": "1465"}
        assert payload["vertical_crs"] is None

    def test_sidecar_failure_does_not_break_download(self, tmp_path, caplog):
        """D7: blad budowy sidecara = ostrzezenie, plik danych zostaje."""
        import logging

        mock_provider = Mock()
        mock_provider.name = "BDOT10k"
        mock_provider.descriptor_key = "pl.gugik.bdot10k"
        out = tmp_path / "out.gpkg"

        def fake(teryt, output_path, **kwargs):
            out.write_bytes(b"GPKG")
            return out

        mock_provider.download_by_teryt.side_effect = fake
        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        with (
            patch(
                "kartograf.sources.sidecar.build_metadata",
                side_effect=RuntimeError("zepsuty deskryptor"),
            ),
            caplog.at_level(logging.WARNING),
        ):
            result = manager.download_by_teryt("1465", output_path=out)
        assert result.exists()
        assert not (result.parent / f"{result.name}.meta.json").exists()
        assert "zepsuty deskryptor" in caplog.text

    @staticmethod
    def _corine_png_sidecar(tmp_path, **kwargs):
        """Pobierz CORINE po bbox z fallbackiem PNG; zwroc payload sidecara."""
        import json

        mock_provider = Mock()
        mock_provider.name = "CORINE"
        mock_provider.descriptor_key = "eu.clms.corine"
        out = tmp_path / "clc.png"

        def fake(bbox, output_path, **_kwargs):
            out.write_bytes(b"\x89PNG")
            return out

        mock_provider.download_by_bbox.side_effect = fake
        manager = LandCoverManager(output_dir=tmp_path, provider=mock_provider)
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        result = manager.download_by_bbox(bbox, output_path=out, **kwargs)
        sidecar = result.parent / f"{result.name}.meta.json"
        assert sidecar.exists()
        return json.loads(sidecar.read_text(encoding="utf-8"))

    def test_corine_png_fallback_uses_web_mercator(self, tmp_path):
        payload = self._corine_png_sidecar(tmp_path)
        assert payload["horizontal_crs"] == "EPSG:3857"
        assert payload["extra"]["fallback"] == "wms_png"
        assert payload["extra"]["note"] == "podglad WMS, nie dane"

    def test_corine_png_fallback_1990_uses_wgs84(self, tmp_path):
        payload = self._corine_png_sidecar(tmp_path, year=1990)
        assert payload["horizontal_crs"] == "EPSG:4326"
        assert payload["extra"]["fallback"] == "wms_png"


class TestBdot10kDefaultTimeout:
    """N11: ``Bdot10kProvider.DEFAULT_TIMEOUT`` jest zrodlem domyslnego
    timeoutu pobrania we wszystkich trybach (SCOPE 3.2: 120 s), nie martwa
    stala sprzeczna z sygnaturami."""

    @pytest.mark.parametrize(
        "method", ["download_by_admin_unit", "download_by_godlo", "download_by_bbox"]
    )
    def test_download_default_timeout_is_class_constant(self, method):
        import inspect

        from kartograf.providers.pl.bdot10k import Bdot10kProvider

        default = (
            inspect.signature(getattr(Bdot10kProvider, method))
            .parameters["timeout"]
            .default
        )
        assert default == Bdot10kProvider.DEFAULT_TIMEOUT == 120


def _make_layer_gpkg(path, table, value):
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
    c.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT)")
    c.execute(f"INSERT INTO {table} VALUES (1, '{value}')")
    conn.commit()
    conn.close()


class TestBdot10kMergeOnNetworkShare:
    """CIFS/SMB bez nobrl: SQLite nie moze pisac w katalogu wyjsciowym."""

    def _patch_locked_in(self, monkeypatch, out_dir):
        real_connect = sqlite3.connect

        def fake_connect(database, *a, **kw):
            if Path(str(database)).resolve().is_relative_to(out_dir.resolve()):
                raise sqlite3.OperationalError("database is locked")
            return real_connect(database, *a, **kw)

        monkeypatch.setattr(sqlite3, "connect", fake_connect)

    def test_merge_succeeds_when_sqlite_locked_in_output_dir(
        self, tmp_path, monkeypatch
    ):
        src = tmp_path / "src"
        src.mkdir()
        out_dir = tmp_path / "share"
        out_dir.mkdir()
        g1, g2 = src / "one.gpkg", src / "two.gpkg"
        _make_layer_gpkg(g1, "PTLZ", "forest")
        _make_layer_gpkg(g2, "PTWP", "water")
        self._patch_locked_in(monkeypatch, out_dir)

        output = out_dir / "merged.gpkg"
        Bdot10kProvider()._merge_gpkg_files([g1, g2], output)

        monkeypatch.undo()
        assert output.exists()
        conn = sqlite3.connect(str(output))
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()
        assert {"PTLZ", "PTWP"} <= tables
        assert [p.name for p in out_dir.iterdir()] == ["merged.gpkg"]

    def test_no_leftovers_on_failure(self, tmp_path, monkeypatch):
        import tempfile

        src = tmp_path / "src"
        src.mkdir()
        out_dir = tmp_path / "share"
        out_dir.mkdir()
        g1, g2 = src / "one.gpkg", src / "two.gpkg"
        _make_layer_gpkg(g1, "PTLZ", "forest")
        _make_layer_gpkg(g2, "PTWP", "water")

        work_dirs = []
        real_tmpdir = tempfile.TemporaryDirectory

        class SpyTmp(real_tmpdir):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                work_dirs.append(Path(self.name))

        monkeypatch.setattr(tempfile, "TemporaryDirectory", SpyTmp)

        def boom(self, target):
            # final_tmp juz istnieje (kopia po scaleniu) - awaria podmiany
            assert self.exists()
            raise OSError("replace failed")

        monkeypatch.setattr(Path, "replace", boom)

        with pytest.raises(OSError, match="replace failed"):
            Bdot10kProvider()._merge_gpkg_files([g1, g2], out_dir / "merged.gpkg")

        assert list(out_dir.glob("*.tmp")) == []
        assert list(out_dir.iterdir()) == []
        assert len(work_dirs) == 1 and not work_dirs[0].exists()
