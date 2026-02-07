"""
Testy jednostkowe dla modułu gugik_orto provider.

Ten moduł zawiera testy dla klasy GugikOrtoProvider:
- download(godlo) → OpenData (TIF)
- download_bbox(bbox) → WCS (GeoTIFF/PNG/JPEG)
"""

from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.gugik_orto import GugikOrtoProvider


class TestGugikOrtoProviderInit:
    """Testy inicjalizacji GugikOrtoProvider."""

    def test_init_no_args(self):
        """Test tworzenia providera bez argumentów (domyślne wartości)."""
        provider = GugikOrtoProvider()
        assert provider._session is None

    def test_init_with_session(self):
        """Test tworzenia providera z własną sesją HTTP."""
        session = Mock(spec=requests.Session)
        provider = GugikOrtoProvider(session=session)
        assert provider._session is session

    def test_no_vertical_crs(self):
        """Test że provider nie ma atrybutu vertical_crs (w odróżnieniu od NMT/NMPT)."""
        provider = GugikOrtoProvider()
        assert not hasattr(provider, "vertical_crs")

    def test_no_resolution(self):
        """Test że provider nie ma atrybutu resolution (w odróżnieniu od NMT)."""
        provider = GugikOrtoProvider()
        assert not hasattr(provider, "resolution")


class TestGugikOrtoProviderProperties:
    """Testy właściwości GugikOrtoProvider."""

    def test_name(self):
        """Test nazwy providera."""
        provider = GugikOrtoProvider()
        assert provider.name == "GUGiK Ortofotomapa"

    def test_base_url(self):
        """Test bazowego URL geoportal."""
        provider = GugikOrtoProvider()
        assert provider.base_url == "https://mapy.geoportal.gov.pl"

    def test_default_extension(self):
        """Test domyślnego rozszerzenia pliku."""
        provider = GugikOrtoProvider()
        assert provider.default_extension == ".tif"

    def test_repr(self):
        """Test metody __repr__ — zawiera nazwę klasy."""
        provider = GugikOrtoProvider()
        repr_str = repr(provider)
        assert "GugikOrtoProvider" in repr_str

    def test_str(self):
        """Test metody __str__ — zawiera nazwę providera."""
        provider = GugikOrtoProvider()
        str_repr = str(provider)
        assert "GUGiK Ortofotomapa" in str_repr


class TestGugikOrtoProviderDownload:
    """Testy pobierania przez godło (OpenData)."""

    @pytest.fixture
    def mock_wms_response(self):
        """Mock odpowiedzi WMS GetFeatureInfo z URL OpenData."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = (
            '<html><script>var data = {url:"https://opendata.geoportal.gov.pl'
            '/NumDaneWys/ORTO/12345/12345_N-34-130-D-d-2-4.tif"};</script></html>'
        )
        return response

    @pytest.fixture
    def mock_opendata_response(self):
        """Mock odpowiedzi pobierania pliku TIF z OpenData."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.iter_content = Mock(
            return_value=[b"TIFF header data\x00\x00", b"pixel data..."]
        )
        return response

    def test_download_success(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test że download(godlo) używa WMS → OpenData URL, pobiera i zapisuje plik."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "sheet.tif"

        result = provider.download("N-34-130-D-d-2-4", output_path)

        assert result == output_path
        assert output_path.exists()

        # First call should be WMS GetFeatureInfo
        first_call_url = session.get.call_args_list[0][0][0]
        assert "GetFeatureInfo" in first_call_url

        # Second call should be OpenData URL
        second_call_url = session.get.call_args_list[1][0][0]
        assert "opendata.geoportal.gov.pl" in second_call_url

    def test_download_creates_directory(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test że download tworzy katalog docelowy jeśli nie istnieje."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "subdir" / "nested" / "sheet.tif"

        result = provider.download("N-34-130-D-d-2-4", output_path)

        assert result == output_path
        assert output_path.parent.exists()

    def test_download_saves_content(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test że download zapisuje zawartość pliku na dysk."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "sheet.tif"

        provider.download("N-34-130-D-d-2-4", output_path)

        content = output_path.read_bytes()
        assert b"TIFF header data" in content


class TestGugikOrtoProviderDownloadBbox:
    """Testy pobierania przez bbox (WCS)."""

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

    def test_download_bbox_success(self, tmp_path, mock_wcs_response, sample_bbox):
        """Test że download_bbox pobiera dane przez WCS."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "area.tif"

        result = provider.download_bbox(sample_bbox, output_path)

        assert result == output_path
        assert output_path.exists()

        call_url = session.get.call_args[0][0]
        assert "WCS" in call_url
        assert "SUBSET=x(" in call_url
        assert "SUBSET=y(" in call_url

    def test_download_bbox_url_contains_coverage_id(
        self, tmp_path, mock_wcs_response, sample_bbox
    ):
        """Test że URL WCS zawiera COVERAGEID=Orthoimagery_StandardResolution."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "area.tif"

        provider.download_bbox(sample_bbox, output_path)

        call_url = session.get.call_args[0][0]
        assert "Orthoimagery_StandardResolution" in call_url

    def test_download_bbox_invalid_crs(self, tmp_path):
        """Test błędu dla bbox z nieprawidłowym CRS (nie EPSG:2180)."""
        provider = GugikOrtoProvider()
        output_path = tmp_path / "area.tif"

        wrong_crs_bbox = BBox(
            min_x=18.0, min_y=52.0, max_x=19.0, max_y=53.0, crs="EPSG:4326"
        )

        with pytest.raises(ValueError, match="EPSG:2180"):
            provider.download_bbox(wrong_crs_bbox, output_path)

    def test_download_bbox_invalid_format(self, tmp_path, sample_bbox):
        """Test błędu dla nieobsługiwanego formatu WCS."""
        provider = GugikOrtoProvider()
        output_path = tmp_path / "area.xyz"

        with pytest.raises(ValueError, match="Unsupported WCS format"):
            provider.download_bbox(sample_bbox, output_path, format="InvalidFormat")


class TestGugikOrtoProviderGetOpendataUrl:
    """Testy dla _get_opendata_url."""

    @pytest.fixture
    def mock_wms_response_with_url(self):
        """Mock odpowiedzi WMS GetFeatureInfo z URL OpenData."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = (
            '<html><script>var data = {url:"https://opendata.geoportal.gov.pl'
            '/NumDaneWys/ORTO/12345/12345_N-34-130-D-d-2-4.tif"};'
            "</script></html>"
        )
        return response

    @pytest.fixture
    def mock_wms_response_no_url(self):
        """Mock odpowiedzi WMS GetFeatureInfo bez URL."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = "<html><body>No data</body></html>"
        return response

    def test_get_opendata_url_success(self, mock_wms_response_with_url):
        """Test znajdowania URL OpenData w odpowiedzi WMS."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_response_with_url)

        provider = GugikOrtoProvider(session=session)
        url = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert "opendata.geoportal.gov.pl" in url
        assert "N-34-130-D-d-2-4" in url

    def test_get_opendata_url_not_found(self, mock_wms_response_no_url):
        """Test błędu gdy żadna warstwa nie zwraca URL."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_response_no_url)

        provider = GugikOrtoProvider(session=session)

        with pytest.raises(DownloadError) as exc_info:
            provider._get_opendata_url("N-34-130-D-d-2-4")

        assert "No orthophoto data available" in str(exc_info.value)

    def test_get_opendata_url_tries_all_layers(
        self, mock_wms_response_no_url, mock_wms_response_with_url
    ):
        """Test że sprawdzane są wszystkie 9 warstw WMS."""
        session = Mock(spec=requests.Session)
        # All layers return empty, should query all 9
        session.get = Mock(return_value=mock_wms_response_no_url)

        provider = GugikOrtoProvider(session=session)

        with pytest.raises(DownloadError):
            provider._get_opendata_url("N-34-130-D-d-2-4")

        # Should have tried all 9 layers
        assert session.get.call_count == 9

        # Verify it queries the correct number of layers
        assert len(provider.WMS_LAYERS) == 9


class TestGugikOrtoProviderRetry:
    """Testy retry i obsługi błędów."""

    def test_download_retry_on_failure(self, tmp_path):
        """Test ponawiania próby po błędzie — 1. nieudana, 2. udana."""
        session = Mock(spec=requests.Session)

        # Mock WMS response (succeeds)
        wms_response = Mock()
        wms_response.status_code = 200
        wms_response.text = 'url:"https://opendata.geoportal.gov.pl/test.tif"'

        # First OpenData request fails, second succeeds
        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        success_response = Mock()
        success_response.iter_content = Mock(return_value=[b"data"])

        session.get = Mock(side_effect=[wms_response, fail_response, success_response])

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "test.tif"

        with patch("time.sleep"):
            result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert session.get.call_count == 3

    def test_download_retry_exhausted(self, tmp_path):
        """Test błędu DownloadError po wyczerpaniu wszystkich prób."""
        session = Mock(spec=requests.Session)

        # Mock WMS response (succeeds)
        wms_response = Mock()
        wms_response.status_code = 200
        wms_response.text = 'url:"https://opendata.geoportal.gov.pl/test.tif"'

        # All OpenData requests fail
        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        session.get = Mock(
            side_effect=[wms_response, fail_response, fail_response, fail_response]
        )

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "test.tif"

        with patch("time.sleep"), pytest.raises(DownloadError):
            provider.download("N-34-130-D", output_path)

    def test_download_exponential_backoff(self, tmp_path):
        """Test exponential backoff — czasy oczekiwania [2, 4] sekund."""
        session = Mock(spec=requests.Session)

        wms_response = Mock()
        wms_response.status_code = 200
        wms_response.text = 'url:"https://opendata.geoportal.gov.pl/test.tif"'

        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        session.get = Mock(
            side_effect=[wms_response, fail_response, fail_response, fail_response]
        )

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "test.tif"

        sleep_times = []
        with (
            patch("time.sleep", side_effect=lambda t: sleep_times.append(t)),
            pytest.raises(DownloadError),
        ):
            provider.download("N-34-130-D", output_path)

        # Exponential backoff: 2^1=2, 2^2=4 seconds
        assert sleep_times == [2, 4]


class TestGugikOrtoProviderInfo:
    """Testy metod informacyjnych."""

    def test_supported_formats(self):
        """Test listy obsługiwanych formatów WCS."""
        provider = GugikOrtoProvider()
        formats = provider.get_supported_formats()

        assert formats == ["GTiff", "PNG", "JPEG"]

    def test_validate_valid_godlo(self):
        """Test walidacji poprawnego godła — zwraca True."""
        provider = GugikOrtoProvider()

        assert provider.validate_godlo("N-34-130-D") is True
        assert provider.validate_godlo("N-34-130-D-d-2-4") is True
        assert provider.validate_godlo("M-33-A") is True

    def test_validate_invalid_godlo(self):
        """Test walidacji niepoprawnego godła — zwraca False."""
        provider = GugikOrtoProvider()

        assert provider.validate_godlo("INVALID") is False
        assert provider.validate_godlo("") is False
        assert provider.validate_godlo("123") is False
