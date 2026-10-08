"""
Testy jednostkowe dla modułu gugik provider.

Ten moduł zawiera testy dla klasy GugikProvider z nową architekturą:
- download(godlo) → OpenData (ASC)
- download_bbox(bbox) → WCS (GeoTIFF/PNG/JPEG)
"""

import threading
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.pl.gugik import GugikProvider
from tests.conftest import _STUB_LAYERS, gfi_record, render_gfi_body

_EVRF2007_LAYERS = _STUB_LAYERS["NMT/WMS/SkorowidzeUkladEVRF2007"]
# Fabryka sesji na watek zyje w SkorowidzLayersMixin (skorowidz.py)
SESSION_FACTORY = "kartograf.transport.http.make_gugik_session"


def _wms_response(body: str) -> Mock:
    """Atrapa odpowiedzi HTTP 200 skorowidza (GetFeatureInfo / GetCapabilities)."""
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.text = body
    response.raise_for_status = Mock()
    return response


def _queried_layers(session: Mock) -> list[str]:
    """Wartosci LAYERS= z kolejnych zapytan GetFeatureInfo na sesji."""
    return [
        parse_qs(urlparse(call.args[0]).query)["LAYERS"][0]
        for call in session.get.call_args_list
    ]


class TestGugikProviderBasic:
    """Testy podstawowej funkcjonalności GugikProvider."""

    def test_provider_name(self):
        """Test nazwy providera."""
        provider = GugikProvider()
        assert provider.name == "GUGiK"

    def test_provider_base_url(self):
        """Test bazowego URL."""
        provider = GugikProvider()
        assert provider.base_url == "https://mapy.geoportal.gov.pl"

    def test_supported_formats(self):
        """Test obsługiwanych formatów WCS."""
        provider = GugikProvider()
        formats = provider.get_supported_formats()

        assert "GTiff" in formats
        assert "PNG" in formats
        assert "JPEG" in formats
        assert len(formats) == 3  # Only WCS formats

    def test_file_extensions(self):
        """Test rozszerzeń plików."""
        provider = GugikProvider()

        assert provider.get_file_extension("GTiff") == ".tif"
        assert provider.get_file_extension("PNG") == ".png"
        assert provider.get_file_extension("JPEG") == ".jpg"
        assert provider.get_file_extension("ASC") == ".asc"

    def test_file_extension_invalid_format(self):
        """Test rozszerzenia dla nieprawidłowego formatu."""
        provider = GugikProvider()

        with pytest.raises(ValueError, match="Unknown format"):
            provider.get_file_extension("InvalidFormat")


class TestGugikProviderResolution:
    """Testy obsługi rozdzielczości (1m/5m)."""

    def test_default_resolution_is_1m(self):
        """Test że domyślna rozdzielczość to 1m."""
        provider = GugikProvider()
        assert provider.resolution == "1m"

    def test_resolution_1m_explicit(self):
        """Test jawnego ustawienia rozdzielczości 1m."""
        provider = GugikProvider(resolution="1m")
        assert provider.resolution == "1m"

    def test_resolution_5m(self):
        """Test ustawienia rozdzielczości 5m (wymaga EVRF2007)."""
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        assert provider.resolution == "5m"
        assert provider.vertical_crs == "EVRF2007"

    def test_resolution_5m_requires_evrf2007(self):
        """Test że rozdzielczość 5m wymaga EVRF2007."""
        with pytest.raises(ValueError, match="5m is only available for EVRF2007"):
            GugikProvider(resolution="5m", vertical_crs="KRON86")

    def test_resolution_invalid(self):
        """Test nieprawidłowej rozdzielczości."""
        with pytest.raises(ValueError, match="Unsupported resolution"):
            GugikProvider(resolution="2m")

    def test_supported_resolutions(self):
        """Test listy obsługiwanych rozdzielczości."""
        provider = GugikProvider()
        resolutions = provider.get_supported_resolutions()

        assert "1m" in resolutions
        assert "5m" in resolutions
        assert len(resolutions) == 2

    def test_supported_vertical_crs_for_1m(self):
        """Test obsługiwanych CRS dla 1m."""
        provider = GugikProvider(resolution="1m")
        crs_list = provider.get_supported_vertical_crs_for_resolution()

        assert "KRON86" in crs_list
        assert "EVRF2007" in crs_list

    def test_supported_vertical_crs_for_5m(self):
        """Test obsługiwanych CRS dla 5m."""
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        crs_list = provider.get_supported_vertical_crs_for_resolution()

        assert "EVRF2007" in crs_list
        assert "KRON86" not in crs_list

    def test_is_wcs_available_1m(self):
        """Test dostępności WCS dla 1m (tylko KRON86 — EVRF2007 = 404)."""
        provider = GugikProvider(resolution="1m", vertical_crs="KRON86")
        assert provider.is_wcs_available() is True

    def test_is_wcs_available_1m_evrf2007_false(self):
        """Test niedostępności WCS dla 1m/EVRF2007 (endpoint wycofany)."""
        provider = GugikProvider(resolution="1m", vertical_crs="EVRF2007")
        assert provider.is_wcs_available() is False

    def test_is_wcs_available_5m(self):
        """Test niedostępności WCS dla 5m."""
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        assert provider.is_wcs_available() is False

    def test_download_bbox_not_available_for_5m(self, tmp_path):
        """Test że download_bbox nie jest dostępne dla 5m."""
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        output_path = tmp_path / "test.tif"

        bbox = BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

        with pytest.raises(ValueError, match="not available for 5m"):
            provider.download_bbox(bbox, output_path)


class TestGugikProviderValidation:
    """Testy walidacji godła."""

    def test_validate_valid_godlo(self):
        """Test walidacji poprawnego godła."""
        provider = GugikProvider()

        assert provider.validate_godlo("N-34-130-D") is True
        assert provider.validate_godlo("N-34-130-D-d-2-4") is True
        assert provider.validate_godlo("M-33-A") is True

    def test_validate_invalid_godlo(self):
        """Test walidacji niepoprawnego godła."""
        provider = GugikProvider()

        assert provider.validate_godlo("INVALID") is False
        assert provider.validate_godlo("") is False
        assert provider.validate_godlo("123") is False


class TestGugikProviderDownloadGodlo:
    """Testy pobierania przez godło (OpenData)."""

    @pytest.fixture
    def mock_wms_response(self):
        """Mock odpowiedzi WMS GetFeatureInfo z rekordem arkusza N-34-130-D."""
        return _wms_response(render_gfi_body([gfi_record("N-34-130-D")]))

    @pytest.fixture
    def mock_opendata_response(self):
        """Mock odpowiedzi pobierania pliku ASC."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.iter_content = Mock(
            return_value=[b"ncols 100\nnrows 100\n", b"data..."]
        )
        return response

    def test_download_godlo_uses_opendata(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test że download(godlo) używa OpenData."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.asc"

        result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert output_path.exists()

        # First call should be WMS GetFeatureInfo
        first_call_url = session.get.call_args_list[0][0][0]
        assert "GetFeatureInfo" in first_call_url

        # Second call should be OpenData URL
        second_call_url = session.get.call_args_list[1][0][0]
        assert "opendata.geoportal.gov.pl" in second_call_url

    def test_download_godlo_creates_directory(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test że download tworzy katalog docelowy."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikProvider(session=session)
        output_path = tmp_path / "subdir" / "nested" / "test.asc"

        result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert output_path.parent.exists()

    def test_download_godlo_saves_content(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test że download zapisuje zawartość pliku."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.asc"

        provider.download("N-34-130-D", output_path)

        content = output_path.read_bytes()
        assert b"ncols" in content

    def test_download_godlo_with_timeout(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test pobierania z określonym timeout."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.asc"

        provider.download("N-34-130-D", output_path, timeout=60)

        # Check timeout was passed to requests
        for call in session.get.call_args_list:
            assert call.kwargs["timeout"] == 60

    def test_download_skorowidz_failure_leaves_no_directory(
        self, tmp_path, mock_opendata_response
    ):
        """Awaria skorowidza (3 x ConnectionError) = DownloadError przed mkdir."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset")] * 3
            + [mock_opendata_response]
        )
        provider = GugikProvider(session=session)
        output_path = tmp_path / "not-created" / "test.asc"

        with patch("time.sleep"), pytest.raises(DownloadError) as exc_info:
            provider.download("N-34-130-D", output_path)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert not output_path.parent.exists()
        assert session.get.call_count == 3


class TestGugikProviderDownloadBbox:
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

    def test_download_bbox_uses_wcs(self, tmp_path, mock_wcs_response, sample_bbox):
        """Test że download_bbox używa WCS."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikProvider(session=session, vertical_crs="KRON86")
        output_path = tmp_path / "test.tif"

        result = provider.download_bbox(sample_bbox, output_path)

        assert result == output_path
        assert output_path.exists()

        # WCS bbox jest dostepne wylacznie w KRON86 (EVRF2007 = HTTP 404)
        call_url = session.get.call_args[0][0]
        assert "WCS" in call_url
        assert "COVERAGEID=DTM_PL-KRON86-NH_TIFF" in call_url
        assert "SUBSET=x(" in call_url
        assert "SUBSET=y(" in call_url

    def test_download_bbox_gtiff_format(self, tmp_path, mock_wcs_response, sample_bbox):
        """Test pobierania bbox w formacie GTiff."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikProvider(session=session, vertical_crs="KRON86")
        output_path = tmp_path / "test.tif"

        provider.download_bbox(sample_bbox, output_path, format="GTiff")

        call_url = session.get.call_args[0][0]
        assert "image%2Ftiff" in call_url or "image/tiff" in call_url

    def test_download_bbox_png_format(self, tmp_path, mock_wcs_response, sample_bbox):
        """Test pobierania bbox w formacie PNG."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikProvider(session=session, vertical_crs="KRON86")
        output_path = tmp_path / "test.png"

        provider.download_bbox(sample_bbox, output_path, format="PNG")

        call_url = session.get.call_args[0][0]
        assert "image%2Fpng" in call_url or "image/png" in call_url

    def test_download_bbox_invalid_format(self, tmp_path, sample_bbox):
        """Test błędu dla nieprawidłowego formatu."""
        provider = GugikProvider()
        output_path = tmp_path / "test.xyz"

        with pytest.raises(ValueError, match="Unsupported WCS format"):
            provider.download_bbox(sample_bbox, output_path, format="InvalidFormat")

    def test_download_bbox_wrong_crs(self, tmp_path):
        """Test błędu dla nieprawidłowego CRS."""
        provider = GugikProvider()
        output_path = tmp_path / "test.tif"

        wrong_crs_bbox = BBox(
            min_x=18.0, min_y=52.0, max_x=19.0, max_y=53.0, crs="EPSG:4326"
        )

        with pytest.raises(ValueError, match="EPSG:2180"):
            provider.download_bbox(wrong_crs_bbox, output_path)

    def test_download_bbox_contains_subset_parameters(
        self, tmp_path, mock_wcs_response, sample_bbox
    ):
        """Test że URL zawiera parametry SUBSET z bounding box."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikProvider(session=session, vertical_crs="KRON86")
        output_path = tmp_path / "test.tif"

        provider.download_bbox(sample_bbox, output_path)

        call_url = session.get.call_args[0][0]

        # URL should contain SUBSET parameters with bbox values
        assert "SUBSET=x(450000" in call_url
        assert "SUBSET=y(550000" in call_url

    def test_download_bbox_evrf2007_raises_validation_error(
        self, tmp_path, sample_bbox
    ):
        """WCS NMT 1m dla EVRF2007 zostal wycofany — blad walidacji, nie 404."""
        session = Mock(spec=requests.Session)

        provider = GugikProvider(session=session)  # domyslnie EVRF2007
        output_path = tmp_path / "test.tif"

        with pytest.raises(ValidationError, match="KRON86"):
            provider.download_bbox(sample_bbox, output_path)

        session.get.assert_not_called()


class TestGugikProviderRetry:
    """Testy retry i obsługi błędów."""

    def test_download_retry_on_failure(self, tmp_path):
        """Test ponawiania próby po błędzie."""
        session = Mock(spec=requests.Session)

        # Mock WMS response (succeeds)
        wms_response = _wms_response(
            render_gfi_body(
                [
                    gfi_record(
                        "N-34-130-D", url="https://opendata.geoportal.gov.pl/test.asc"
                    )
                ]
            )
        )

        # First OpenData request fails, second succeeds
        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        success_response = Mock()
        success_response.iter_content = Mock(return_value=[b"data"])

        session.get = Mock(side_effect=[wms_response, fail_response, success_response])

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.asc"

        with patch("time.sleep"):
            result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert session.get.call_count == 3

    def test_download_retry_exhausted(self, tmp_path):
        """Test błędu po wyczerpaniu prób."""
        session = Mock(spec=requests.Session)

        # Mock WMS response (succeeds)
        wms_response = _wms_response(
            render_gfi_body(
                [
                    gfi_record(
                        "N-34-130-D", url="https://opendata.geoportal.gov.pl/test.asc"
                    )
                ]
            )
        )

        # All OpenData requests fail
        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        session.get = Mock(
            side_effect=[wms_response, fail_response, fail_response, fail_response]
        )

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.asc"

        with patch("time.sleep"), pytest.raises(DownloadError):
            provider.download("N-34-130-D", output_path)

    def test_download_exponential_backoff(self, tmp_path):
        """Test exponential backoff między próbami."""
        session = Mock(spec=requests.Session)
        wms_response = _wms_response(
            render_gfi_body(
                [
                    gfi_record(
                        "N-34-130-D", url="https://opendata.geoportal.gov.pl/test.asc"
                    )
                ]
            )
        )

        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        session.get = Mock(
            side_effect=[wms_response, fail_response, fail_response, fail_response]
        )

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.asc"

        sleep_times = []
        with (
            patch("time.sleep", side_effect=lambda t: sleep_times.append(t)),
            pytest.raises(DownloadError),
        ):
            provider.download("N-34-130-D", output_path)

        # Exponential backoff: 2^1=2, 2^2=4 seconds
        assert sleep_times == [2, 4]


# Raport wyjatku OGC w ksztalcie MapServera (WMS 1.3.0), ktory odpowiada nim
# z HTTP 200. Tresc "Invalid layer(s) given in the LAYERS parameter" GUGiK
# zwracal naprawde na GetFeatureInfo o nieaktualna warstwe (CHANGELOG 0.7.0,
# nazwy warstw WMS); kodu HTTP i Content-Type realnej odpowiedzi nikt nie
# zapisal (checklista live).
_OGC_EXCEPTION_REPORT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
    '<ServiceExceptionReport version="1.3.0" xmlns="http://www.opengis.net/ogc" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:schemaLocation="http://www.opengis.net/ogc '
    'http://schemas.opengis.net/wms/1.3.0/exceptions_1_3_0.xsd">\n'
    '<ServiceException code="LayerNotDefined">\n'
    "msWMSLoadGetMapParams(): WMS server error. Invalid layer(s) given in the "
    "LAYERS parameter. A layer might be disabled for this request.\n"
    "</ServiceException>\n"
    "</ServiceExceptionReport>\n"
)


# Minimalne GetCapabilities z warstwa skorowidza, warstwa zbiorcza i warstwa
# innego produktu (ZasiegiNMT — odrzucana przez LAYER_PATTERN).
_CAPABILITIES_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">'
    "<Capability><Layer><Name>ZasiegiNMT2025</Name>"
    "<Layer><Name>SkorowidzeNMT2023iStarsze</Name></Layer>"
    "<Layer><Name>SkorowidzeNMT2024</Name></Layer>"
    "</Layer></Capability></WMS_Capabilities>"
)


class TestGugikProviderGetOpendataUrl:
    """Testy dla _get_opendata_url (warstwy z autouse stuba conftest)."""

    GODLO = "N-34-130-D-d-2-4"
    URL = f"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/78955/78955_1_{GODLO}.asc"

    @pytest.fixture
    def record_response(self):
        """Odpowiedz z jednym rekordem 1 m PL-1992 dla GODLO."""
        return _wms_response(render_gfi_body([gfi_record(self.GODLO)]))

    @pytest.fixture
    def empty_response(self):
        """Pusty szablon skorowidza (morze, zagranica)."""
        return _wms_response(render_gfi_body([]))

    def test_get_opendata_url_success(self, record_response):
        """Rekord w najnowszej warstwie: jej URL, petla konczy sie po 1 zapytaniu."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=record_response)

        url = GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert url == self.URL
        assert _queried_layers(session) == [_EVRF2007_LAYERS[0]]

    def test_get_opendata_url_not_found(self, empty_response):
        """Pusta odpowiedz KAZDEJ warstwy = NoCoverageError z opisem zadania."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=empty_response)

        with pytest.raises(NoCoverageError) as exc_info:
            GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert f"Brak danych NMT 1m dla {self.GODLO} (uklad PL-1992, EVRF2007)" in str(
            exc_info.value
        )
        assert _queried_layers(session) == list(_EVRF2007_LAYERS)

    def test_transport_error_retries_same_layer(self, record_response):
        """Zerwane polaczenie ponawia TE SAMA warstwe po backoffie."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset"), record_response]
        )

        with patch("time.sleep") as sleep:
            url = GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert url == self.URL
        assert _queried_layers(session) == [_EVRF2007_LAYERS[0]] * 2
        assert sleep.call_count == 1

    def test_transport_error_exhausted_is_service_failure(self, record_response):
        """3 x awaria najnowszej warstwy = DownloadError; starszych warstw nie
        pytamy (rekord z 2. warstwy nigdy nie zastepuje nieznanej nowszej kampanii)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset")] * 3 + [record_response] * 3
        )

        with patch("time.sleep") as sleep, pytest.raises(DownloadError) as exc_info:
            GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert not isinstance(exc_info.value, NoCoverageError)
        message = str(exc_info.value)
        assert self.GODLO in message and _EVRF2007_LAYERS[0] in message
        assert _queried_layers(session) == [_EVRF2007_LAYERS[0]] * 3
        assert sleep.call_count == 2

    def test_ogc_exception_report_is_service_failure(self):
        """Raport wyjatku OGC z HTTP 200 = DownloadError po 1 zapytaniu, bez
        ponowien i bez brania go za brak arkusza."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(_OGC_EXCEPTION_REPORT))

        with patch("time.sleep") as sleep, pytest.raises(DownloadError) as exc_info:
            GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert "Invalid layer(s)" in str(exc_info.value)
        assert session.get.call_count == 1
        sleep.assert_not_called()

    def test_html_without_template_is_service_failure(self):
        """HTML 200 bez szablonu skorowidza (np. strona bramy) = DownloadError."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            return_value=_wms_response("<html><body>502 Bad Gateway</body></html>")
        )

        with pytest.raises(DownloadError) as exc_info:
            GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert session.get.call_count == 1

    def test_get_opendata_url_tries_all_layers(self, empty_response, record_response):
        """Puste warstwy sa odpytywane po kolei od najnowszej az do rekordu."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[empty_response] * 3 + [record_response])

        url = GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert url == self.URL
        assert _queried_layers(session) == list(_EVRF2007_LAYERS)

    @pytest.mark.parametrize("newest_first", [True, False])
    def test_latest_campaign_wins_within_layer(self, newest_first):
        """W jednej warstwie wygrywa najnowsza aktualnosc, nie kolejnosc w HTML."""
        records = [
            gfi_record(self.GODLO, aktualnosc="2024-09-03", url="https://x/new.asc"),
            gfi_record(self.GODLO, aktualnosc="2019-04-18", url="https://x/old.asc"),
        ]
        if not newest_first:
            records.reverse()
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(render_gfi_body(records)))

        url = GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert url == "https://x/new.asc"

    def test_dt_pzgik_breaks_aktualnosc_tie(self):
        """Remis aktualnosc rozstrzyga pozniejszy dt_pzgik."""
        records = [
            gfi_record(self.GODLO, dt_pzgik="2024-11-02", url="https://x/earlier.asc"),
            gfi_record(self.GODLO, dt_pzgik="2025-01-10", url="https://x/later.asc"),
        ]
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(render_gfi_body(records)))

        url = GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert url == "https://x/later.asc"

    def test_other_resolution_only_is_no_coverage_with_hint(self):
        """Jedyny rekord 0,50 m: 1 m nie ma, ale podpowiedz mowi, co jest."""
        body = render_gfi_body([gfi_record(self.GODLO, resolution="0.50 m")])
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(body))

        with pytest.raises(NoCoverageError) as exc_info:
            GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert "0.5 m" in str(exc_info.value)

    def test_negative_cache_preserves_resolution_hint(self, tmp_path):
        from kartograf.cache.metadata import MetadataCache

        body = render_gfi_body([gfi_record(self.GODLO, resolution="0.50 m")])
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(body))
        cache = MetadataCache(db_path=tmp_path / "cache.db")
        try:
            provider = GugikProvider(session=session, cache=cache)
            with pytest.raises(NoCoverageError) as first:
                provider._get_opendata_url(self.GODLO)
            calls = session.get.call_count
            with pytest.raises(NoCoverageError) as cached:
                provider._get_opendata_url(self.GODLO)
            assert session.get.call_count == calls
            assert str(cached.value) == str(first.value)
            assert "0.5 m" in str(cached.value)
        finally:
            cache.close()

    def test_rejected_record_does_not_stop_layer_loop(self, record_response):
        """Warstwa z samym 0,50 m nie konczy petli — 1 m z nastepnej warstwy."""
        first = _wms_response(
            render_gfi_body([gfi_record(self.GODLO, resolution="0.50 m")])
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[first, record_response])

        url = GugikProvider(session=session)._get_opendata_url(self.GODLO)

        assert url == self.URL
        assert _queried_layers(session) == list(_EVRF2007_LAYERS[:2])

    def test_get_opendata_url_uses_correct_endpoint_for_1m(self, record_response):
        """Test że 1m używa właściwego endpointu (domyślnie EVRF2007)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=record_response)

        provider = GugikProvider(session=session, resolution="1m")
        provider._get_opendata_url(self.GODLO)

        call_url = session.get.call_args[0][0]
        assert "SkorowidzeUkladEVRF2007" in call_url

    def test_get_opendata_url_uses_correct_endpoint_for_5m(self):
        """Test że 5m używa właściwego endpointu."""
        body = render_gfi_body([gfi_record(self.GODLO, resolution="5.00 m")])
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(body))

        provider = GugikProvider(
            session=session, resolution="5m", vertical_crs="EVRF2007"
        )
        assert provider._get_opendata_url(self.GODLO) == self.URL

        call_url = session.get.call_args[0][0]
        assert "SheetsGrid5mEVRF2007" in call_url


class TestGugikProviderSession:
    """Testy zarzadzania sesja HTTP: jedna wstrzyknieta albo jedna na watek."""

    GODLO = "N-34-130-D"

    @pytest.fixture
    def record_body(self):
        return render_gfi_body([gfi_record(self.GODLO)])

    @staticmethod
    def file_response():
        response = Mock()
        response.iter_content = Mock(return_value=[b"data"])
        return response

    def test_uses_provided_session(self, tmp_path, record_body):
        """Wstrzyknieta sesja obsluguje skorowidz i plik; zadna inna nie powstaje."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[_wms_response(record_body), self.file_response()]
        )

        with patch(SESSION_FACTORY) as factory:
            GugikProvider(session=session).download(self.GODLO, tmp_path / "test.asc")

        factory.assert_not_called()
        assert session.get.call_count == 2

    def test_one_session_per_thread(self, record_body):
        """Dwa zadania w jednym watku dziela jedna sesje z make_gugik_session."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(record_body))

        with patch(SESSION_FACTORY, return_value=session) as factory:
            provider = GugikProvider()
            provider._get_opendata_url(self.GODLO)
            provider._get_opendata_url(self.GODLO)

        factory.assert_called_once()
        assert session.get.call_count == 2

    def test_separate_session_per_thread(self, record_body) -> None:
        """Kazdy watek dostaje wlasna sesje i uzywa tylko jej."""
        sessions: list[Mock] = []
        results: list[str] = []
        errors: list[Exception] = []

        def new_session():
            session = Mock(spec=requests.Session)
            session.get = Mock(return_value=_wms_response(record_body))
            sessions.append(session)
            return session

        with patch(SESSION_FACTORY, side_effect=new_session) as factory:
            provider = GugikProvider()

            def worker():
                try:
                    results.append(provider._get_opendata_url(self.GODLO))
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        assert errors == []
        assert factory.call_count == 2
        assert [session.get.call_count for session in sessions] == [1, 1]
        assert results == [gfi_record(self.GODLO)["url"]] * 2

    @pytest.mark.real_wms_layers
    def test_provided_session_serves_get_capabilities(self, tmp_path, record_body):
        """Bez stuba warstw: wstrzyknieta sesja robi GetCapabilities, potem
        GetFeatureInfo na warstwie z capabilities, potem strumien pliku."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                _wms_response(_CAPABILITIES_XML),
                _wms_response(record_body),
                self.file_response(),
            ]
        )
        output_path = tmp_path / "test.asc"

        with patch(SESSION_FACTORY) as factory:
            result = GugikProvider(session=session).download(self.GODLO, output_path)

        factory.assert_not_called()
        assert result == output_path and output_path.read_bytes() == b"data"
        calls = session.get.call_args_list
        assert "REQUEST=GetCapabilities" in calls[0].args[0]
        assert "REQUEST=GetFeatureInfo" in calls[1].args[0]
        assert "LAYERS=SkorowidzeNMT2024" in calls[1].args[0]
        assert calls[2].kwargs["stream"] is True


class TestGugikProviderRepr:
    """Testy reprezentacji tekstowej."""

    def test_repr(self):
        """Test metody __repr__."""
        provider = GugikProvider()
        repr_str = repr(provider)

        assert "GugikProvider" in repr_str
        assert "mapy.geoportal.gov.pl" in repr_str

    def test_str(self):
        """Test metody __str__."""
        provider = GugikProvider()
        str_repr = str(provider)

        assert "GUGiK" in str_repr
        assert "mapy.geoportal.gov.pl" in str_repr


class TestSkorowidzRegression:
    @staticmethod
    def response(body):
        response = requests.Response()
        response.status_code = 200
        response._content = body.encode()
        response.encoding = "utf-8"
        return response

    @staticmethod
    def sample(name):
        return (
            Path(__file__).parent / "fixtures" / "gugik_skorowidz" / name
        ).read_text()

    def test_failed_newest_layer_never_uses_older_campaign(self):
        session = Mock(spec=requests.Session)
        session.get.side_effect = [
            requests.ConnectionError("reset"),
            requests.ConnectionError("reset"),
            requests.ConnectionError("reset"),
            self.response(self.sample("szczecin_c24_2024.body")),
        ]
        provider = GugikProvider(session=session)
        with (
            patch("time.sleep"),
            pytest.raises(DownloadError) as exc,
        ):
            provider._get_opendata_url("N-33-90-C-c-2-4")
        assert not isinstance(exc.value, NoCoverageError)
        assert "N-33-90-C-c-2-4" in str(exc.value)
        assert "SkorowidzeNMT2026" in str(exc.value)
        assert session.get.call_count == 3

    @pytest.mark.parametrize(
        ("godlo", "fixture", "expected"),
        [
            ("N-33-90-C-c-2-4", "szczecin_c24_2024.body", "80225_1536688"),
            ("N-34-139-A-c-1-1", "warszawa_2023iStarsze.body", "78047_1404533"),
        ],
    )
    def test_exact_resolution_and_latest_campaign(self, godlo, fixture, expected):
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(self.sample(fixture))
        assert expected in GugikProvider(session=session)._get_opendata_url(godlo)

    @pytest.mark.parametrize(
        ("godlo", "record_godlo", "uklad", "hint"),
        [
            ("5.167.25", "5.167.25.13", "PL-2000:S5", "--scale 1:2000"),
            ("7.124.7.4", "N-33-48-C-a-3-4", "PL-1992", "PL-1992"),
        ],
    )
    def test_no_substring_or_other_system_fallback(
        self, godlo, record_godlo, uklad, hint
    ):
        body = render_gfi_body(
            [
                {
                    "url": f"https://opendata.geoportal.gov.pl/{record_godlo}.asc",
                    "godlo": record_godlo,
                    "ukladWspolrzednychPoziomych": uklad,
                    "charakterystykaPrzestrzenna": "1.00 m",
                    "aktualnosc": "2024-09-03",
                }
            ]
        )
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(body)
        with pytest.raises(NoCoverageError, match=hint):
            GugikProvider(session=session)._get_opendata_url(godlo)

    def test_uppercase_asc_is_available(self):
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(
            self.sample("slubice_c32_2022iStarsze.html")
        )
        url = GugikProvider(session=session, resolution="5m")._get_opendata_url(
            "N-33-126-C-c-3-2"
        )
        assert url.endswith("76969_1298029_N-33-126-C-c-3-2.ASC")

    def test_no_coverage_leaves_no_directory(self, tmp_path):
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(self.sample("empty.body"))
        output = tmp_path / "not-created" / "sheet.asc"
        with pytest.raises(NoCoverageError):
            GugikProvider(session=session).download("N-33-90-C-c-2-4", output)
        assert not output.parent.exists()

    def test_failed_layer_does_not_cache_older_record(self, tmp_path):
        from kartograf.cache.metadata import MetadataCache

        cache = MetadataCache(tmp_path / "cache.db")
        session = Mock(spec=requests.Session)
        session.get.side_effect = [
            requests.ConnectionError("reset"),
            requests.ConnectionError("reset"),
            requests.ConnectionError("reset"),
            self.response(self.sample("szczecin_c24_2024.body")),
        ]
        provider = GugikProvider(session=session, cache=cache)
        try:
            with patch("time.sleep"), pytest.raises(DownloadError):
                provider._get_opendata_url("N-33-90-C-c-2-4")
            assert cache.get_record("nmt", "1m", "EVRF2007", "N-33-90-C-c-2-4") is None
        finally:
            cache.close()

    def test_1m_rejects_5m_record(self):
        body = render_gfi_body([gfi_record("N-33-90-C-c-2-4", resolution="5.00 m")])
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(body)
        with pytest.raises(NoCoverageError, match="5 m"):
            GugikProvider(session=session)._get_opendata_url("N-33-90-C-c-2-4")

    def test_5m_accepts_5m_record(self):
        record = gfi_record("N-33-90-C-c-2-4", resolution="5.00 m")
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(render_gfi_body([record]))
        provider = GugikProvider(session=session, resolution="5m")
        assert provider._get_opendata_url("N-33-90-C-c-2-4") == record["url"]

    def test_pl2000_record_matches_only_same_zone(self):
        record = gfi_record("7.173.21.06", uklad="PL-2000:S7")
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(render_gfi_body([record]))
        assert (
            GugikProvider(session=session)._get_opendata_url("7.173.21.06")
            == (record["url"])
        )

        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(
            render_gfi_body([gfi_record("7.173.21.06", uklad="PL-2000:S6")])
        )
        with pytest.raises(NoCoverageError, match="PL-2000"):
            GugikProvider(session=session)._get_opendata_url("7.173.21.06")
