"""
Testy jednostkowe dla modułu GugikNmptProvider.

Ten moduł zawiera testy dla klasy GugikNmptProvider, która dziedziczy
z GugikProvider i udostępnia pobieranie NMPT (Numeryczny Model Pokrycia Terenu)
z GUGiK — dane DSM (Digital Surface Model) zawierające teren + obiekty powierzchniowe.

Endpoints i coverage IDs są inne niż NMT (DTM), ale mechanizm pobierania
(WMS skorowidze -> OpenData ASC, WCS -> GeoTIFF) jest identyczny.
"""

from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from tests.conftest import gfi_record, render_gfi_body

NMPT_OPENDATA_URL = "https://opendata.geoportal.gov.pl/NumDaneWys/NMPT/78955/78955_1467030_N-34-130-D.asc"


def _layer_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["LAYERS"][0]


# =========================================================================
# TestGugikNmptProviderInit
# =========================================================================


class TestGugikNmptProviderInit:
    """Testy inicjalizacji GugikNmptProvider."""

    def test_default_vertical_crs(self):
        """Test że domyślny vertical CRS to EVRF2007."""
        provider = GugikNmptProvider()
        assert provider.vertical_crs == "EVRF2007"

    def test_resolution_is_1m(self):
        """Test że rozdzielczość to zawsze 1m — NMPT nie ma 5m."""
        provider = GugikNmptProvider()
        assert provider.resolution == "1m"

    def test_invalid_resolution_not_possible(self):
        """Test że __init__ wymusza resolution='1m' — nie da się podać innej."""
        # GugikNmptProvider.__init__ zawsze przekazuje resolution="1m" do super()
        # Jedyny parametr to vertical_crs i session — resolution nie jest argumentem
        provider = GugikNmptProvider()
        assert provider.resolution == "1m"

        # SUPPORTED_RESOLUTIONS zawiera tylko "1m"
        assert provider.SUPPORTED_RESOLUTIONS == ["1m"]

    def test_custom_vertical_crs_kron86(self):
        """Test tworzenia providera z KRON86."""
        provider = GugikNmptProvider(vertical_crs="KRON86")
        assert provider.vertical_crs == "KRON86"

    def test_invalid_vertical_crs(self):
        """Test że nieprawidłowy vertical CRS podnosi ValueError."""
        with pytest.raises(ValueError, match="Unsupported vertical CRS"):
            GugikNmptProvider(vertical_crs="INVALID")


# =========================================================================
# TestGugikNmptProviderProperties
# =========================================================================


class TestGugikNmptProviderProperties:
    """Testy właściwości (properties) GugikNmptProvider."""

    def test_name(self):
        """Test że name zwraca 'GUGiK NMPT'."""
        provider = GugikNmptProvider()
        assert provider.name == "GUGiK NMPT"

    def test_base_url(self):
        """Test że base_url zwraca URL geoportalu."""
        provider = GugikNmptProvider()
        assert provider.base_url == "https://mapy.geoportal.gov.pl"

    def test_default_extension(self):
        """Test że domyślne rozszerzenie to .asc."""
        provider = GugikNmptProvider()
        assert provider.default_extension == ".asc"

    def test_repr(self):
        """Test że repr zawiera 'GugikNmptProvider'."""
        provider = GugikNmptProvider()
        repr_str = repr(provider)
        assert "GugikNmptProvider" in repr_str
        assert "mapy.geoportal.gov.pl" in repr_str

    def test_str(self):
        """Test że str zawiera 'GUGiK NMPT'."""
        provider = GugikNmptProvider()
        str_repr = str(provider)
        assert "GUGiK NMPT" in str_repr
        assert "mapy.geoportal.gov.pl" in str_repr


# =========================================================================
# TestGugikNmptProviderEndpoints
# =========================================================================


class TestGugikNmptProviderEndpoints:
    """Testy endpointów i konfiguracji warstw NMPT."""

    def test_wcs_endpoints_are_nmpt(self):
        """Test że endpointy WCS zawierają 'NMPT' (nie 'NMT')."""
        provider = GugikNmptProvider()
        for crs, url in provider.WCS_ENDPOINTS.items():
            assert "NMPT" in url, f"WCS endpoint for {crs} should contain 'NMPT'"
            assert "NMT/" not in url, (
                f"WCS endpoint for {crs} should not contain 'NMT/'"
            )

    def test_wms_endpoints_are_nmpt(self):
        """Test że endpointy WMS skorowidze zawierają 'NMPT'."""
        provider = GugikNmptProvider()
        for resolution, crs_endpoints in provider.WMS_SKOROWIDZE_ENDPOINTS.items():
            for crs, url in crs_endpoints.items():
                assert "NMPT" in url, (
                    f"WMS endpoint for {resolution}/{crs} should contain 'NMPT'"
                )

    def test_coverage_ids_are_dsm(self):
        """Test że coverage IDs to DSM_PL-* (nie DTM)."""
        provider = GugikNmptProvider()
        for crs, coverage_id in provider.COVERAGE_IDS.items():
            assert coverage_id.startswith("DSM_PL-"), (
                f"Coverage ID for {crs} should start with "
                f"'DSM_PL-', got '{coverage_id}'"
            )
            assert "DTM" not in coverage_id, (
                f"Coverage ID for {crs} should not contain 'DTM'"
            )

    def test_wcs_available_for_both_vertical_crs(self):
        """Awaria endpointu WCS NMT EVRF2007 nie dotyczy NMPT (inny endpoint)."""
        assert GugikNmptProvider().WITHDRAWN_WCS_VERTICAL_CRS == ()
        assert GugikNmptProvider(vertical_crs="EVRF2007").is_wcs_available() is True
        assert GugikNmptProvider(vertical_crs="KRON86").is_wcs_available() is True


# =========================================================================
# TestGugikNmptProviderDownload
# =========================================================================


class TestGugikNmptProviderDownload:
    """Testy pobierania danych NMPT."""

    @pytest.fixture
    def mock_wms_response(self):
        """Mock odpowiedzi WMS GetFeatureInfo z URL OpenData NMPT."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = render_gfi_body(
            [gfi_record("N-34-130-D", url=NMPT_OPENDATA_URL)]
        )
        return response

    @pytest.fixture
    def mock_opendata_response(self):
        """Mock odpowiedzi pobierania pliku ASC z OpenData."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.iter_content = Mock(
            return_value=[b"ncols 100\nnrows 100\n", b"data..."]
        )
        return response

    @pytest.fixture
    def mock_wcs_response(self):
        """Mock odpowiedzi WCS."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.iter_content = Mock(return_value=[b"TIFF data..."])
        return response

    @pytest.fixture
    def sample_bbox(self):
        """Przykładowy bbox w EPSG:2180."""
        return BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

    def test_download_uses_opendata(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test że download(godlo) używa WMS + OpenData (tak jak GugikProvider)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikNmptProvider(session=session)
        output_path = tmp_path / "test.asc"

        result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert output_path.exists()

        # First call should be WMS GetFeatureInfo on the NMPT endpoint,
        # newest skorowidz layer first
        first_call_url = session.get.call_args_list[0][0][0]
        assert "GetFeatureInfo" in first_call_url
        assert "NMPT" in first_call_url
        assert _layer_of(first_call_url) == "SkorowidzeNMPT2026"

        # Second call should be the OpenData URL from the skorowidz record
        second_call_url = session.get.call_args_list[1][0][0]
        assert second_call_url == NMPT_OPENDATA_URL

    def test_download_bbox_uses_wcs(self, tmp_path, mock_wcs_response, sample_bbox):
        """Test że download_bbox używa WCS z endpointem NMPT."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikNmptProvider(session=session)
        output_path = tmp_path / "test.tif"

        result = provider.download_bbox(sample_bbox, output_path)

        assert result == output_path
        assert output_path.exists()

        # Should use NMPT WCS endpoint with DSM coverage ID
        call_url = session.get.call_args[0][0]
        assert "WCS" in call_url
        assert "NMPT" in call_url
        assert "COVERAGEID=DSM_PL-EVRF2007-NH" in call_url
        assert "SUBSET=x(" in call_url
        assert "SUBSET=y(" in call_url

    def test_get_opendata_url_uses_nmpt_endpoint(self, mock_wms_response):
        """Test że _get_opendata_url odpytuje endpoint NMPT (nie NMT)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_response)

        provider = GugikNmptProvider(session=session)
        url = provider._get_opendata_url("N-34-130-D")

        assert url == NMPT_OPENDATA_URL
        session.get.assert_called_once()
        call_url = session.get.call_args[0][0]
        # Endpoint should contain NMPT
        assert "NMPT" in call_url
        # Newest NMPT layer answers first, so it is the only one queried
        assert _layer_of(call_url) == "SkorowidzeNMPT2026"


# =========================================================================
# TestGugikNmptProviderInheritance
# =========================================================================


class TestGugikNmptProviderInheritance:
    """Testy dziedziczenia GugikNmptProvider."""

    def test_is_instance_of_base_provider(self):
        """Test że GugikNmptProvider jest instancją BaseProvider."""
        provider = GugikNmptProvider()
        assert isinstance(provider, BaseProvider)

    def test_is_instance_of_gugik_provider(self):
        """Test że GugikNmptProvider jest instancją GugikProvider."""
        provider = GugikNmptProvider()
        assert isinstance(provider, GugikProvider)

    def test_inherits_retry_logic(self):
        """Test że MAX_RETRIES jest odziedziczone i wynosi 3."""
        provider = GugikNmptProvider()
        assert provider.MAX_RETRIES == 3
