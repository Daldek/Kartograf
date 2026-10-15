"""
Tests for land cover functionality.

Tests cover LandCoverProvider, Bdot10kProvider, CorineProvider,
and LandCoverManager classes.
"""

import hashlib
import json
import os
import shutil
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
    Bdot10kPackage,
    Bdot10kProvider,
)
from kartograf.transform.bbox import envelope_from_2180
from kartograf.transport.http import SessionPerThread


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
        assert provider.get_layer_description("PTLZ") == "Tereny lesne"
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
        """Test OpenData URL with invalid voivodeship code."""
        provider = Bdot10kProvider()
        with pytest.raises(ValidationError):
            provider._construct_opendata_url("9999", "GPKG")

    def test_download_by_teryt_invalid(self):
        """Test download with invalid TERYT."""
        provider = Bdot10kProvider()
        with pytest.raises(ValidationError):
            provider.download_by_teryt("invalid", Path("/tmp/test.gpkg"))

    def test_download_by_bbox_any_crs(self, tmp_path):
        """A bbox in EPSG:4326 reaches PRG discovery without CRS rejection."""
        provider = Bdot10kProvider()
        bbox = BBox(14.0, 52.0, 15.0, 53.0, "EPSG:4326")
        with (
            patch.object(provider, "teryts_for_area", return_value=["0208"]) as teryts,
            patch.object(
                provider, "download_by_admin_unit", return_value=tmp_path / "x.gpkg"
            ) as package,
        ):
            assert provider.download_by_bbox(bbox, tmp_path / "x.gpkg") == (
                tmp_path / "x.gpkg"
            )
        assert teryts.call_args.args[0] is bbox
        assert package.call_args.args[0] == "0208"


class TestBdot10kPrgTimeout:
    """P7: the caller's ``timeout`` reaches the PRG powiat lookup too."""

    BBOX = BBox(340000, 290000, 350000, 300000, "EPSG:2180")
    DISCOVER = "kartograf.providers.pl.bdot10k.discover_teryts_for_bbox"

    def test_provider_bbox_and_sheet(self, tmp_path):
        provider = Bdot10kProvider()
        with (
            patch(self.DISCOVER, return_value=["0208"]) as discover,
            patch.object(provider, "download_by_admin_unit"),
        ):
            provider.download_by_bbox(self.BBOX, tmp_path / "x.gpkg", timeout=7)
            assert discover.call_args.kwargs["timeout"] == 7
            provider.download_by_sheet("N-34-130-D", tmp_path / "x.gpkg", timeout=9)
            assert discover.call_args.kwargs["timeout"] == 9

    def test_manager_passes_timeout_option(self, tmp_path):
        manager = LandCoverManager(output_dir=tmp_path, provider="bdot10k")
        with (
            patch(self.DISCOVER, return_value=["0208"]) as discover,
            patch.object(manager, "_run"),
        ):
            manager.download(bbox=self.BBOX, timeout=7)
            assert discover.call_args.kwargs["timeout"] == 7
            manager.download(sheet="N-34-130-D", timeout=8)
            assert discover.call_args.kwargs["timeout"] == 8
            manager.download(bbox=self.BBOX)
            assert discover.call_args.kwargs["timeout"] == 30


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
        with pytest.raises(ValidationError):
            provider.download_by_bbox(bbox, Path("/tmp/test.png"), year=2018)

    def test_download_by_bbox_invalid_year(self):
        """Test download with invalid year."""
        provider = CorineProvider()
        bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
        with pytest.raises(ValidationError):
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

    def test_init_with_provider_name(self):
        """Test initialization with provider name."""
        manager = LandCoverManager(output_dir="data", provider="corine")
        assert manager.provider_name == "CORINE Land Cover"

    def test_init_with_provider_instance(self):
        """Test initialization with provider instance."""
        provider = CorineProvider()
        manager = LandCoverManager(output_dir="data", provider=provider)
        assert manager.provider_name == "CORINE Land Cover"

    def test_init_invalid_provider(self):
        """Test initialization with invalid provider."""
        with pytest.raises(ValidationError):
            LandCoverManager(output_dir="data", provider="invalid")

    def test_set_provider_by_name(self):
        """Test setting provider by name."""
        manager = LandCoverManager(output_dir="data", provider="bdot10k")
        manager.set_provider("corine")
        assert manager.provider_name == "CORINE Land Cover"

    def test_set_provider_by_instance(self):
        """Test setting provider by instance."""
        manager = LandCoverManager(output_dir="data", provider="corine")
        manager.set_provider(Bdot10kProvider())
        assert manager.provider_name == "BDOT10k"

    def test_get_available_providers(self):
        """Test getting available providers."""
        providers = LandCoverManager.get_available_providers()
        assert "bdot10k" in providers
        assert "corine" in providers

    def test_download_no_selection(self):
        """Test download with no selection method."""
        manager = LandCoverManager(output_dir="data", provider="bdot10k")
        with pytest.raises(ValidationError):
            manager.download()

    def test_download_multiple_selection(self):
        """Test download with multiple selection methods."""
        manager = LandCoverManager(output_dir="data", provider="bdot10k")
        with pytest.raises(ValidationError):
            manager.download(teryt="1465", sheet="N-34-130-D")

    def test_repr(self):
        """Test string representation."""
        manager = LandCoverManager(output_dir="data", provider="bdot10k")
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
        assert "Tereny lesne" in captured.out

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

        result = main(["landcover", "download", "--source", "bdot10k", "-o", "unused"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Error: Podaj dokladnie jeden wybor" in captured.err

    def test_landcover_download_invalid_bbox(self, capsys):
        """Test download with invalid bbox."""
        from kartograf.cli.commands import main

        result = main(
            [
                "landcover",
                "download",
                "--source",
                "bdot10k",
                "-o",
                "unused",
                "--bbox",
                "invalid",
            ]
        )
        assert result == 1
        captured = capsys.readouterr()
        assert "Nieprawidlowy bbox" in captured.err
        # the "Oczekiwano" hint goes to stderr together with the error (review-1 D4)
        assert "Oczekiwano" in captured.err
        assert "Oczekiwano" not in captured.out

    @pytest.mark.parametrize(
        "bbox",
        ["10,10,5,5", "1,10,5,5", "nan,1,2,3", "1,2,inf,4", "1,2,3", "1,2,3,4,5"],
    )
    def test_landcover_download_rejects_bad_bbox(self, bbox, capsys, tmp_path):
        """Inverted/NaN/inf/wrong value count -> Error on stderr, code 1 (K7a)."""
        from kartograf.cli.commands import main

        with patch("kartograf.cli.landcover_cmd.LandCoverManager") as manager:
            result = main(
                [
                    "landcover",
                    "download",
                    "--source",
                    "bdot10k",
                    f"--bbox={bbox}",
                    "-o",
                    str(tmp_path),
                ]
            )
        assert result == 1
        manager.assert_not_called()
        captured = capsys.readouterr()
        assert "Error: Nieprawidlowy bbox" in captured.err
        assert "ValueError" not in captured.err
        assert "Oczekiwano" not in captured.out


class TestLandCoverInvalidOptions:
    """An invalid --property/--year/--depth/--stat is a USER error (N8).

    `Error: <message>` without the exception type name and without the
    KARTOGRAF_DEBUG hint (that one is for internal errors), exit code 1, before
    the network (conftest blocks sockets - a connection attempt would fail the
    test).
    """

    _SOIL = ["soil", "download"]

    @pytest.mark.parametrize(
        ("command", "fragment"),
        [
            (
                [*_SOIL, "--property", "foo", "--depth", "0-5cm", "--stat", "mean"],
                "Nieprawidlowa wlasciwosc",
            ),
            (
                [*_SOIL, "--property", "soc", "--depth", "1-2cm", "--stat", "mean"],
                "Nieprawidlowa glebokosc",
            ),
            (
                [*_SOIL, "--property", "soc", "--depth", "0-5cm", "--stat", "median"],
                "Nieprawidlowa statystyka",
            ),
            (["landcover", "download", "--source", "corine", "--year", "1999"], "1999"),
        ],
    )
    def test_invalid_option_is_user_error(self, command, fragment, tmp_path, capsys):
        from kartograf.cli.commands import main

        rc = main([*command, "--sheet", "N-34-130-D", "-o", str(tmp_path)])
        err = capsys.readouterr().err
        assert rc == 1
        assert fragment in err
        assert "Error: " in err
        assert "ValueError" not in err
        assert "KARTOGRAF_DEBUG" not in err


class TestBdot10kShpFormat:
    """`--format SHP`: a ZIP archive of shapefiles must not pass as `.gpkg` (N1)."""

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
        expected = tmp_path / "landcover/pl_bdot10k_shp/teryt/1465.zip"
        assert expected.read_bytes().startswith(b"PK")
        (version,) = (tmp_path / "landcover/pl_bdot10k_shp/versions/teryt").iterdir()
        assert sorted(p.name for p in version.iterdir()) == [
            "1465.zip",
            "1465.zip.meta.json",
        ]
        assert os.path.samefile(expected, version / "1465.zip")
        out = capsys.readouterr().out
        assert "landcover/pl_bdot10k_shp/teryt/1465.zip: nowa wersja " in out

    def test_provider_returns_zip_path_for_shp(self, tmp_path):
        provider = Bdot10kProvider(session=self._session())
        result = provider.download_by_admin_unit(
            "1465", tmp_path / "powiat.gpkg", format="SHP"
        )
        assert result == tmp_path / "powiat.zip"
        assert result.read_bytes() == self.SHP_ZIP
        assert not (tmp_path / "powiat.gpkg").exists()


class TestWojewodztwoMapping:
    """Test voivodeship TERYT mapping."""

    def test_all_wojewodztwa_mapped(self):
        """Test that all 16 voivodeships are mapped."""
        assert len(WOJEWODZTWO_NAMES) == 16

    def test_known_wojewodztwa(self):
        """Test known voivodeship mappings."""
        assert WOJEWODZTWO_NAMES["14"] == "mazowieckie"
        assert WOJEWODZTWO_NAMES["12"] == "malopolskie"
        assert WOJEWODZTWO_NAMES["02"] == "dolnoslaskie"


# ===========================================================================
# New tests for Bdot10kProvider (download, retry, extract, merge)
# ===========================================================================


class TestBdot10kProviderDownload:
    """Test Bdot10kProvider download methods with mocks."""

    def test_download_by_teryt_invalid_format(self):
        """Invalid format raises ValidationError."""
        provider = Bdot10kProvider()
        with pytest.raises(ValidationError, match="Nieobslugiwany format"):
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
    def test_download_by_sheet_success(self, mock_parser_cls, tmp_path):
        """download_by_sheet resolves the one TERYT of the sheet frame (PRG)."""
        provider = Bdot10kProvider()
        output = tmp_path / "out.gpkg"

        mock_parser = Mock()
        mock_parser.get_bbox.return_value = BBox(
            450000, 550000, 460000, 560000, "EPSG:2180"
        )
        mock_parser_cls.return_value = mock_parser

        with (
            patch.object(provider, "teryts_for_area", return_value=["1465"]),
            patch.object(
                provider, "download_by_admin_unit", return_value=output
            ) as mock_dl,
        ):
            result = provider.download_by_sheet("N-34-130-D", output)

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


class TestBdot10kRetryAndIO:
    """Test retry, save, extract, merge."""

    def test_download_shp_success(self, tmp_path):
        """SHP package downloaded the first time: the stream saved as .zip."""
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
        """All response chunks end up in the file, no .tmp leftovers."""
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

    def test_redownload_overwrites_existing_gpkg_like_windows(self, tmp_path):
        """The merged GPKG replaces the old file also under Windows semantics
        (``Path.rename`` refuses an existing target; the swap is
        ``os.replace``)."""
        import os

        body = _bdot_zip(tmp_path, ["OT_PTLZ_A"])
        output = tmp_path / "out" / "bdot10k_teryt_0262.gpkg"
        output.parent.mkdir()
        output.write_bytes(b"stary plik")

        def windows_rename(self, target):
            if Path(target).exists():
                raise FileExistsError(f"[WinError 183] {target}")
            return os.replace(self, target)

        provider = Bdot10kProvider(session=_zip_session(body))
        with patch.object(Path, "rename", windows_rename):
            provider.download_package("0262", output)
        assert output.read_bytes().startswith(b"SQLite format 3")
        assert [p.name for p in output.parent.iterdir()] == [output.name]

    def test_extract_gpkg_bad_zip(self, tmp_path):
        """Nieprawidlowy plik ZIP -> DownloadError."""
        provider = Bdot10kProvider()
        output = tmp_path / "merged.gpkg"

        mock_resp = Mock()
        mock_resp.iter_content.return_value = [b"not a zip file"]

        with pytest.raises(DownloadError, match="Nieprawidlowy plik ZIP"):
            provider._extract_gpkg_from_zip(mock_resp, output)

    def test_merge_gpkg_files_empty(self):
        """Empty file list -> DownloadError."""
        provider = Bdot10kProvider()
        with pytest.raises(DownloadError, match="Brak plikow do scalenia"):
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
        """CLMS_CREDENTIALS in env does NOT enable direct mode (ADR-002).

        Credentials from env are consumed exclusively by the auth proxy subprocess
        (kartograf.auth.proxy) - never by CorineProvider.__init__ directly. This
        pins that removing the dead get_clms_credentials()/Keychain block in
        corine.py (task 20 of the 0.7.0 audit) does not change this behaviour.
        """
        monkeypatch.setenv("CLMS_CREDENTIALS", '{"client_id": "x"}')
        provider = CorineProvider()
        assert provider._use_proxy is True
        assert provider._clms_auth is None


def _wms_bbox(url):
    """Value of the BBOX parameter of a GetMap URL as four numbers."""
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
            provider.download_by_bbox(bbox, output, year=2018)
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
    def test_download_by_sheet_delegates_to_bbox(self, mock_parser_cls, tmp_path):
        """download_by_sheet delegates to download_by_bbox."""
        provider = CorineProvider(use_proxy=False)
        output = tmp_path / "test.png"

        mock_parser = Mock()
        mock_parser.get_bbox.return_value = BBox(
            450000, 550000, 460000, 560000, "EPSG:2180"
        )
        mock_parser_cls.return_value = mock_parser

        with patch.object(provider, "download_by_bbox", return_value=output) as mock_dl:
            result = provider.download_by_sheet("N-34-130-D", output, year=2018)

        assert result == output
        mock_dl.assert_called_once()

    _BBOX = BBox(450000, 550000, 460000, 560000, "EPSG:2180")

    def test_download_via_wms_writes_png(self, tmp_path):
        """A WMS preview downloaded the first time goes to .png."""
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
        # atomic write: no temporary file leftovers
        assert [p.name for p in tmp_path.iterdir()] == ["t.png"]

    @patch("kartograf.transport.http.time.sleep")
    def test_download_via_wms_error_response(self, sleep, tmp_path):
        """XML content type -> DownloadError without retries and without a file."""
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
        # provider path: DLR (1990) sends BBOX in EPSG:4326 (WMS 1.1.1, lon/lat)
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
        # provider path: EEA (2018) sends BBOX in EPSG:3857
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
    """Stage 0 (spec 6.7): canonical download_by_admin_unit + teryt aliases."""

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


class TestBdot10kDefaultTimeout:
    """N11: ``Bdot10kProvider.DEFAULT_TIMEOUT`` is the source of the default
    download timeout in all modes (SCOPE 3.2: 120 s), not a dead constant
    contradicting the signatures."""

    @pytest.mark.parametrize(
        "method", ["download_by_admin_unit", "download_by_sheet", "download_by_bbox"]
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
    """CIFS/SMB without nobrl: SQLite cannot write in the output directory."""

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

        real_copyfile = shutil.copyfile

        def partial_copy(src_path, dst_path, *a, **kw):
            if Path(dst_path).parent == out_dir:
                Path(dst_path).write_bytes(b"partial")
                raise OSError("copy to share failed")
            return real_copyfile(src_path, dst_path, *a, **kw)

        monkeypatch.setattr(
            "kartograf.providers.pl.bdot10k.shutil.copyfile", partial_copy
        )

        with pytest.raises(OSError, match="copy to share failed"):
            Bdot10kProvider()._merge_gpkg_files([g1, g2], out_dir / "merged.gpkg.tmp")

        assert list(out_dir.iterdir()) == []
        assert len(work_dirs) == 1 and not work_dirs[0].exists()

    def test_failed_swap_keeps_previous_gpkg(self, tmp_path, monkeypatch):
        """P1: the staged GPKG replaces the previous one last; a failed swap
        leaves the previous file and no ``.tmp``."""
        body = _bdot_zip(tmp_path, ["OT_PTWP_A"])
        out = tmp_path / "o"
        out.mkdir()
        target = out / "bdot10k_teryt_0262.gpkg"
        target.write_bytes(b"previous")

        def boom(src_path, dst_path):
            raise OSError("replace failed")

        monkeypatch.setattr("kartograf.providers.pl.bdot10k.os.replace", boom)
        provider = Bdot10kProvider(session=_zip_session(body))
        with pytest.raises(DownloadError, match="replace failed"):
            provider.download_package("0262", target)
        assert target.read_bytes() == b"previous"
        assert sorted(p.name for p in out.iterdir()) == [target.name]


def _tree(root: Path) -> list[str]:
    """Sorted relative paths of everything under ``root``."""
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def _stream_response(body: bytes, content_type: str) -> Mock:
    resp = Mock()
    resp.headers = {"Content-Type": content_type}
    resp.raise_for_status = Mock()
    resp.iter_content.return_value = [body]
    return resp


class TestLandCoverNoSideEffectsOnInit:
    """The output directory is created only on write, not in ``__init__``."""

    @pytest.fixture
    def empty_cwd(self, tmp_path, monkeypatch):
        cwd = tmp_path / "empty"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        return cwd

    @pytest.mark.parametrize(
        "argv",
        [
            ["landcover", "list-sources"],
            ["landcover", "list-layers", "--source", "bdot10k"],
            ["landcover", "list-layers", "--source", "corine"],
            ["soil", "list-layers"],
            ["soil", "list-sources"],
            ["elevation", "list-sources"],
            ["imagery", "list-sources"],
        ],
    )
    def test_cli_list_commands_create_nothing(self, empty_cwd, argv, capsys):
        from kartograf.cli.commands import main

        assert main(argv) == 0
        assert _tree(empty_cwd) == []

    def test_bdot10k_download_creates_output_dir_and_file(self, empty_cwd):
        out_dir = empty_cwd / "data"
        provider = Bdot10kProvider()
        session = Mock()
        session.get.return_value = _stream_response(b"PK zip", "application/zip")
        provider._sessions.injected = session
        manager = LandCoverManager(output_dir=out_dir, provider=provider)
        assert not out_dir.exists()

        file = manager.download(teryt="1465", format="SHP").files[0].file

        assert file.path == out_dir / "landcover/pl_bdot10k_shp/teryt/1465.zip"
        assert file.path.read_bytes() == b"PK zip"
        assert Path(f"{file.version_path}.meta.json").exists()

    @pytest.mark.parametrize("source", ["bdot10k", "corine", "soilgrids"])
    def test_failed_download_leaves_no_output_dir(self, empty_cwd, source):
        out_dir = empty_cwd / "out"
        manager = LandCoverManager(output_dir=out_dir, provider=source)
        if source == "corine":
            manager.set_provider(CorineProvider(use_proxy=False))
        session = Mock()
        response = Mock(status_code=404, headers={})
        response.raise_for_status.side_effect = requests.HTTPError(
            "404", response=response
        )
        session.get.return_value = response
        manager.provider._sessions.injected = session

        with pytest.raises(DownloadError):
            if source == "bdot10k":
                manager.download(teryt="1465")
            else:
                options = (
                    {"year": 2018}
                    if source == "corine"
                    else {"property": "soc", "depth": "0-5cm", "stat": "mean"}
                )
                manager.download(
                    bbox=BBox(450000, 550000, 451000, 551000, "EPSG:2180"),
                    **options,
                )

        # the store root may stay (staging lives below it), never a file
        assert _tree(empty_cwd) in ([], ["out"])


def _bdot_zip(tmp_path, tables):
    """ZIP like a GUGiK package: one GPKG per table, real file naming."""
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        for table in tables:
            gpkg = tmp_path / f"{table}.gpkg"
            _make_layer_gpkg(gpkg, table, table.lower())
            zf.write(gpkg, f"PL.PZGiK.337.BDOT10k.0262__{table}.gpkg")
    return zip_buf.getvalue()


def _zip_session(body: bytes):
    response = Mock()
    response.raise_for_status = Mock()
    response.headers = {"Content-Length": str(len(body))}
    response.iter_content = lambda chunk_size=8192: iter([body])
    session = Mock()
    session.get.return_value = response
    return session


def _tables(path):
    conn = sqlite3.connect(str(path))
    names = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'OT_%'"
        )
    }
    conn.close()
    return names


class TestBdot10kLayersAndDuplicates:
    def test_layers_filter_keeps_only_requested(self, tmp_path):
        body = _bdot_zip(tmp_path, ["OT_PTWP_A", "OT_SWRS_L", "OT_PTLZ_A"])
        provider = Bdot10kProvider(session=_zip_session(body))
        pkg = provider.download_package(
            "0262", tmp_path / "out" / "x.gpkg", layers=["PTWP", "SWRS"]
        )
        assert _tables(pkg.path) == {"OT_PTWP_A", "OT_SWRS_L"}
        assert pkg.teryt == "0262" and pkg.url.endswith("/GPKG/02/0262_GPKG.zip")

    def test_unknown_layer_raises(self, tmp_path):
        body = _bdot_zip(tmp_path, ["OT_PTWP_A"])
        provider = Bdot10kProvider(session=_zip_session(body))
        with pytest.raises(DownloadError, match="SWKN"):
            provider.download_package(
                "0262", tmp_path / "o" / "x.gpkg", layers=["SWKN"]
            )

    def test_bad_layer_code_rejected_before_network(self, tmp_path):
        session = _zip_session(b"")
        provider = Bdot10kProvider(session=session)
        with pytest.raises(ValidationError, match="warstw"):
            provider.download_package("0262", tmp_path / "x.gpkg", layers=["ptwp_a"])
        session.get.assert_not_called()

    def test_duplicate_table_raises(self, tmp_path):
        g1, g2 = tmp_path / "a.gpkg", tmp_path / "b.gpkg"
        _make_layer_gpkg(g1, "OT_PTWP_A", "one")
        _make_layer_gpkg(g2, "OT_PTWP_A", "two")
        with pytest.raises(DownloadError, match="OT_PTWP_A"):
            Bdot10kProvider()._merge_gpkg_files([g1, g2], tmp_path / "m.gpkg")


class TestBdot10kSidecarSource:
    """A4: source URL, HTTP headers and the raw GUGiK ZIP of a BDOT10k package."""

    def _session(self, body, headers):
        session = _zip_session(body)
        session.get.return_value.headers = headers
        return session

    def test_package_http_headers(self, tmp_path):
        body = _bdot_zip(tmp_path, ["OT_PTWP_A"])
        provider = Bdot10kProvider(
            session=self._session(body, {"Content-Length": str(len(body))})
        )
        pkg = provider.download_package("0262", tmp_path / "o" / "x.gpkg")
        assert pkg.http == {
            "etag": None,
            "last_modified": None,
            "content_length": len(body),
        }
        assert pkg.raw_path is None
        assert not (tmp_path / "o" / "x_GPKG.zip").exists()

    def test_keep_raw_saves_original_zip(self, tmp_path):
        body = _bdot_zip(tmp_path, ["OT_PTWP_A"])
        provider = Bdot10kProvider(session=self._session(body, {"ETag": '"abc"'}))
        pkg = provider.download_package(
            "0262", tmp_path / "o" / "bdot10k_teryt_0262.gpkg", keep_raw=True
        )
        assert pkg.raw_path == tmp_path / "o" / "bdot10k_teryt_0262_GPKG.zip"
        assert pkg.raw_path.read_bytes() == body
        assert pkg.http["etag"] == '"abc"'
        assert [p.name for p in (tmp_path / "o").iterdir() if ".tmp" in p.name] == []

    def test_keep_raw_with_shp_rejected(self, tmp_path):
        session = _zip_session(b"")
        provider = Bdot10kProvider(session=session)
        with pytest.raises(ValidationError, match="keep_raw"):
            provider.download_package(
                "0262", tmp_path / "x", format="SHP", keep_raw=True
            )
        session.get.assert_not_called()

    def test_raw_path_without_keep_raw_rejected(self, tmp_path):
        session = _zip_session(b"")
        provider = Bdot10kProvider(session=session)
        with pytest.raises(ValidationError, match="raw_path"):
            provider.download_package("0262", tmp_path / "x", raw_path=tmp_path / "r")
        session.get.assert_not_called()

    def test_keep_raw_failed_merge_leaves_no_zip(self, tmp_path):
        """The raw ZIP is written only after a successful merge (no orphan):
        two package files with the same table fail inside the merge."""
        g1, g2 = tmp_path / "a.gpkg", tmp_path / "b.gpkg"
        _make_layer_gpkg(g1, "OT_PTWP_A", "one")
        _make_layer_gpkg(g2, "OT_PTWP_A", "two")
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.write(g1, "PL.PZGiK.337.BDOT10k.0262__OT_PTWP_A.gpkg")
            zf.write(g2, "PL.PZGiK.337.BDOT10k.0262__OT_PTWP_A_copy.gpkg")
        provider = Bdot10kProvider(session=self._session(buf.getvalue(), {}))
        with pytest.raises(DownloadError, match="OT_PTWP_A"):
            provider.download_package("0262", tmp_path / "o" / "x.gpkg", keep_raw=True)
        assert sorted(p.name for p in (tmp_path / "o").iterdir()) == []

    def test_keep_raw_write_error_leaves_no_file(self, tmp_path, monkeypatch):
        """OSError while writing the raw ZIP (first download): DownloadError,
        and neither the GPKG (it would have no sidecar) nor a partial ZIP
        nor the staged GPKG stays on disk."""
        body = _bdot_zip(tmp_path, ["OT_PTWP_A"])
        real_write_bytes = Path.write_bytes

        def disk_full(self, data):
            if "_GPKG.zip" in self.name:
                real_write_bytes(self, bytes(data)[:10])  # partial write
                raise OSError(28, "No space left on device")
            return real_write_bytes(self, data)

        monkeypatch.setattr(Path, "write_bytes", disk_full)
        provider = Bdot10kProvider(session=self._session(body, {}))
        with pytest.raises(DownloadError, match="oryginalnego ZIP") as exc:
            provider.download_package(
                "0262", tmp_path / "o" / "bdot10k_teryt_0262.gpkg", keep_raw=True
            )
        assert "No space left" in str(exc.value)
        assert isinstance(exc.value.__cause__, OSError)
        assert sorted(p.name for p in (tmp_path / "o").iterdir()) == []

    def test_keep_raw_write_error_keeps_previous_result(self, tmp_path, monkeypatch):
        """P1: a re-download whose raw ZIP write fails leaves the previous
        versions and links untouched and no staging behind."""
        out = tmp_path / "out"
        manager = LandCoverManager(output_dir=out, provider="bdot10k")
        z1, z2 = tmp_path / "z1", tmp_path / "z2"
        z1.mkdir()
        z2.mkdir()
        first = _bdot_zip(z1, ["OT_PTWP_A"])
        manager.provider._sessions = SessionPerThread(self._session(first, {}))
        result = manager.download(teryt="0262", keep_raw=True)
        (item,) = result.files
        gpkg = item.file.path
        before = gpkg.read_bytes()
        sidecar = json.loads(Path(f"{item.file.version_path}.meta.json").read_text())

        second = _bdot_zip(z2, ["OT_PTWP_A", "OT_SWRS_L"])
        manager.provider._sessions = SessionPerThread(self._session(second, {}))

        def disk_full(self, data):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(Path, "write_bytes", disk_full)
        with pytest.raises(DownloadError, match="No space left"):
            manager.download(teryt="0262", keep_raw=True, update="force")
        assert gpkg.read_bytes() == before
        assert hashlib.sha256(before).hexdigest() == sidecar["sha256"]
        assert [p for p in out.rglob("*") if ".incoming" in p.parts[-2:]] == []
        assert not any(".tmp" in p.name for p in out.rglob("*"))

    def test_failed_raw_zip_write_releases_buffer_view(self, tmp_path, monkeypatch):
        """P9g: the ``getbuffer`` view is released even when the write fails
        and the caller keeps the exception (``DownloadError ... from e``: the
        traceback holds the frame). A held view makes the buffer unresizable
        and unclosable (``BufferError``)."""
        buf = BytesIO(b"PK zip bytes")

        def disk_full(self, data):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(Path, "write_bytes", disk_full)
        with pytest.raises(OSError) as exc:
            Bdot10kProvider._write_raw_zip(buf, tmp_path / "a_GPKG.zip")
        assert exc.value.__traceback__ is not None  # frame still referenced
        buf.write(b" more")  # resizing needs no exported views
        buf.close()

    def test_manager_keep_raw_write_error_leaves_no_file(self, tmp_path, monkeypatch):
        """Through the manager: no data file without a sidecar, no sidecar."""

        def disk_full(self, data):
            raise OSError(28, "No space left on device")

        body = _bdot_zip(tmp_path, ["OT_PTWP_A"])
        manager = LandCoverManager(output_dir=tmp_path / "out", provider="bdot10k")
        manager.provider._sessions = SessionPerThread(self._session(body, {}))
        monkeypatch.setattr(Path, "write_bytes", disk_full)
        with pytest.raises(DownloadError):
            manager.download(teryt="0262", keep_raw=True)
        assert sorted(p.name for p in (tmp_path / "out").iterdir()) == []

    def test_extraction_os_error_is_download_error(self, tmp_path, monkeypatch):
        """An OSError while extracting a layer (e.g. ENOMEM, full temp disk)
        is a DownloadError, not a bare OSError."""

        def no_memory(src, dst, *args, **kwargs):
            raise OSError(12, "Cannot allocate memory")

        body = _bdot_zip(tmp_path, ["OT_PTWP_A"])
        provider = Bdot10kProvider(session=self._session(body, {}))
        monkeypatch.setattr(
            "kartograf.providers.pl.bdot10k.shutil.copyfileobj", no_memory
        )
        with pytest.raises(DownloadError, match="Cannot allocate memory"):
            provider.download_package("0262", tmp_path / "o" / "x.gpkg")
        assert not (tmp_path / "o" / "x.gpkg").exists()

    def test_cli_extraction_os_error_exit_1(self, tmp_path, monkeypatch, capsys):
        """CLI: the OSError reaches the user as a DownloadError message
        (``Error: Nie udalo sie ...``), not via the last-resort barrier
        (``Error: OSError: ...``)."""
        from kartograf.cli.commands import main

        def no_memory(src, dst, *args, **kwargs):
            raise OSError(12, "Cannot allocate memory")

        session = self._session(_bdot_zip(tmp_path, ["OT_PTWP_A"]), {})
        monkeypatch.setattr(
            "kartograf.providers.pl.bdot10k.shutil.copyfileobj", no_memory
        )
        out = tmp_path / "out"
        with patch("kartograf.transport.http.make_gugik_session", return_value=session):
            rc = main(
                [
                    "landcover",
                    "download",
                    "--source",
                    "bdot10k",
                    "--teryt",
                    "0262",
                    "-o",
                    str(out),
                ]
            )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error: Nie udalo sie rozpakowac" in err
        assert "Cannot allocate memory" in err
        assert "OSError" not in err


class TestLandCoverManagerCache:
    def test_soilgrids_gets_manager_cache(self, tmp_path):
        """A13: the cache reaches SoilGrids (CORINE has none)."""
        from kartograf.cache.metadata import MetadataCache

        cache = MetadataCache(db_path=tmp_path / "c.db")
        manager = LandCoverManager(
            output_dir=tmp_path, provider="soilgrids", cache=cache
        )
        assert manager.provider._cache is cache


class TestLandCoverCliManyCounties:
    """``landcover download --source bdot10k`` through ``main`` (cwd = tmp_path:
    the CLI ``MetadataCache`` lands in cwd)."""

    def test_cli_bbox_downloads_every_county(self, tmp_path, capsys, monkeypatch):
        from kartograf.cli.commands import main

        monkeypatch.chdir(tmp_path)
        with (
            patch(
                "kartograf.providers.pl.bdot10k.discover_teryts_for_bbox",
                return_value=["0208", "0224"],
            ),
            patch.object(
                Bdot10kProvider,
                "download_package",
                side_effect=lambda code, output_path, **kw: (
                    output_path.parent.mkdir(parents=True, exist_ok=True),
                    output_path.write_bytes(b"x"),
                    Bdot10kPackage(
                        path=output_path, teryt=code, url="u", format="GPKG"
                    ),
                )[-1],
            ),
        ):
            rc = main(
                [
                    "landcover",
                    "download",
                    "--source",
                    "bdot10k",
                    "--bbox",
                    "340000,290000,350000,300000",
                    "-o",
                    str(tmp_path / "out"),
                ]
            )
        assert rc == 0
        out = capsys.readouterr().out
        assert "landcover/pl_bdot10k_gpkg/teryt/0208.gpkg: nowa wersja " in out
        assert "landcover/pl_bdot10k_gpkg/teryt/0224.gpkg: nowa wersja " in out

    def test_cli_passes_metadata_cache(self, tmp_path, monkeypatch, capsys):
        from kartograf.cli.commands import main

        monkeypatch.chdir(tmp_path)
        seen = {}

        def fake_discover(bbox, *, session=None, cache=None, timeout=30):
            seen["cache"] = cache
            return []

        with patch(
            "kartograf.providers.pl.bdot10k.discover_teryts_for_bbox",
            side_effect=fake_discover,
        ):
            rc = main(
                [
                    "landcover",
                    "download",
                    "--source",
                    "bdot10k",
                    "--bbox",
                    "340000,290000,350000,300000",
                    "-o",
                    str(tmp_path / "out"),
                ]
            )
        assert seen["cache"] is not None  # U5
        # the sea answer (no powiat) reaches the user as an error, not a crash
        assert rc == 1
        assert "nie przecina zadnego powiatu" in capsys.readouterr().err
