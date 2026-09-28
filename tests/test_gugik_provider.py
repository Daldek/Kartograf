"""
Testy jednostkowe dla modułu gugik provider.

Ten moduł zawiera testy dla klasy GugikProvider z nową architekturą:
- download(godlo) → OpenData (ASC)
- download_bbox(bbox) → WCS (GeoTIFF/PNG/JPEG)
"""

from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.pl.gugik import GugikProvider


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
        """Mock odpowiedzi WMS GetFeatureInfo z URL OpenData."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = (
            '<html><script>var data = {url:"https://opendata.geoportal.gov.pl'
            '/NumDaneWys/NMT/78955/78955_1467030_N-34-130-D.asc"};</script></html>'
        )
        return response

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
        wms_response = Mock()
        wms_response.status_code = 200
        wms_response.text = 'url:"https://opendata.geoportal.gov.pl/test.asc"'

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
        wms_response = Mock()
        wms_response.status_code = 200
        wms_response.text = 'url:"https://opendata.geoportal.gov.pl/test.asc"'

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

        wms_response = Mock()
        wms_response.status_code = 200
        wms_response.text = 'url:"https://opendata.geoportal.gov.pl/test.asc"'

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


class TestGugikProviderGetOpendataUrl:
    """Testy dla _get_opendata_url."""

    @pytest.fixture
    def mock_wms_ogc_exception(self):
        """Mock odpowiedzi 200 z raportem wyjatku OGC zamiast wyniku zapytania."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = _OGC_EXCEPTION_REPORT
        return response

    @pytest.fixture
    def mock_wms_response_with_url(self):
        """Mock odpowiedzi WMS GetFeatureInfo z URL OpenData."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = (
            '<html><script>var data = {url:"https://opendata.geoportal.gov.pl'
            '/NumDaneWys/NMT/78955/78955_1467030_N-34-130-D-d-2-4.asc"};'
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
        """Test znajdowania URL OpenData."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_response_with_url)

        provider = GugikProvider(session=session)
        url = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert "opendata.geoportal.gov.pl" in url
        assert "N-34-130-D-d-2-4.asc" in url

    def test_get_opendata_url_not_found(self, mock_wms_response_no_url):
        """Test błędu gdy nie znaleziono URL."""
        from kartograf.exceptions import NoCoverageError

        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_response_no_url)

        provider = GugikProvider(session=session)

        with pytest.raises(DownloadError) as exc_info:
            provider._get_opendata_url("N-34-130-D-d-2-4")

        assert "No NMT 1m data available" in str(exc_info.value)
        assert isinstance(exc_info.value, NoCoverageError)

    def test_get_opendata_url_all_layers_transport_error_reports_service_failure(
        self,
    ):
        """Awaria WMS na wszystkich warstwach != brak pokrycia danymi."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=requests.HTTPError("500 Server Error"))

        provider = GugikProvider(session=session)
        # Warstwy podane wprost — bez zapytania GetCapabilities do sieci
        provider._validated_layers[("1m", "EVRF2007")] = ["L1", "L2", "L3"]

        with pytest.raises(DownloadError, match="unavailable") as exc_info:
            provider._get_opendata_url("N-34-130-D-d-2-4")

        message = str(exc_info.value)
        assert "500" in message
        assert "all 3 layer queries failed" in message
        assert session.get.call_count == 3

    def test_get_opendata_url_partial_transport_error_is_not_no_coverage(
        self, mock_wms_response_no_url
    ):
        """Czesc warstw padla, reszta bez arkusza: brak pokrycia jest NIEPEWNY
        — to zwykly DownloadError, nie NoCoverageError (R5, plan 2026-09-28)."""
        from kartograf.exceptions import NoCoverageError

        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                requests.HTTPError("500 Server Error"),
                mock_wms_response_no_url,
                mock_wms_response_no_url,
            ]
        )
        provider = GugikProvider(session=session)
        provider._validated_layers[("1m", "EVRF2007")] = ["L1", "L2", "L3"]

        with pytest.raises(DownloadError) as exc_info:
            provider._get_opendata_url("N-34-130-D-d-2-4")

        assert not isinstance(exc_info.value, NoCoverageError)
        assert "niepewny" in str(exc_info.value)
        assert "500" in str(exc_info.value)

    def test_ogc_exception_report_on_all_layers_is_service_failure(
        self, mock_wms_ogc_exception, caplog
    ):
        """I-2: raport wyjatku OGC z HTTP 200 to porazka zapytania, nie brak arkusza.

        Liczony jako "warstwa odpowiedziala, arkusza brak" dawal
        ``NoCoverageError``, a pod R5 — nodata i ``missing_sheets`` w wycinku,
        ktory kolejne przebiegi pomijaja jako istniejacy (trwala dziura po
        chwilowym bledzie uslugi albo po nieaktualnej nazwie warstwy).
        """
        from kartograf.exceptions import NoCoverageError

        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_ogc_exception)
        provider = GugikProvider(session=session)
        provider._validated_layers[("1m", "EVRF2007")] = ["L1", "L2", "L3"]

        with (
            caplog.at_level("WARNING"),
            pytest.raises(DownloadError, match="unavailable") as exc_info,
        ):
            provider._get_opendata_url("N-34-130-D-d-2-4")

        assert not isinstance(exc_info.value, NoCoverageError)
        message = str(exc_info.value)
        assert "all 3 layer queries failed" in message
        # ostatni blad: nazwa warstwy + tresc raportu, nie naglowek XML
        assert "L3" in message and "Invalid layer(s)" in message
        assert session.get.call_count == 3
        assert "L1" in caplog.text  # kazda warstwa ostrzega na biezaco

    def test_ogc_exception_on_one_layer_is_uncertain_not_no_coverage(
        self, mock_wms_ogc_exception, mock_wms_response_no_url
    ):
        """I-2: raport wyjatku na jednej warstwie + brak arkusza na reszcie =
        brak pokrycia NIEPEWNY (arkusz moze lezec wlasnie w tej warstwie)."""
        from kartograf.exceptions import NoCoverageError

        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                mock_wms_ogc_exception,
                mock_wms_response_no_url,
                mock_wms_response_no_url,
            ]
        )
        provider = GugikProvider(session=session)
        provider._validated_layers[("1m", "EVRF2007")] = ["L1", "L2", "L3"]

        with pytest.raises(DownloadError) as exc_info:
            provider._get_opendata_url("N-34-130-D-d-2-4")

        assert not isinstance(exc_info.value, NoCoverageError)
        assert "niepewny" in str(exc_info.value)

    def test_url_in_response_wins_over_exception_marker(
        self, mock_wms_response_with_url
    ):
        """Ruling I-2: URL w odpowiedzi zawsze wygrywa — straz raportu wyjatku
        dotyczy wylacznie odpowiedzi BEZ URL."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = (
            mock_wms_response_with_url.text + "<!-- ServiceExceptionReport -->"
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=response)
        provider = GugikProvider(session=session)
        provider._validated_layers[("1m", "EVRF2007")] = ["L1"]

        url = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert url.endswith("N-34-130-D-d-2-4.asc")

    def test_get_opendata_url_tries_all_layers(
        self, mock_wms_response_no_url, mock_wms_response_with_url
    ):
        """Test że sprawdzane są wszystkie warstwy."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                mock_wms_response_no_url,
                mock_wms_response_no_url,
                mock_wms_response_with_url,
            ]
        )

        provider = GugikProvider(session=session)
        # call_count must measure the loop, not the number of layers GUGiK
        # publishes — pin the layer list instead of taking it from WMS_LAYERS
        provider._validated_layers[("1m", "EVRF2007")] = ["L1", "L2", "L3"]
        url = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert "opendata.geoportal.gov.pl" in url
        assert session.get.call_count == 3

    def test_fallback_url_of_other_sheet_warns(self, caplog):
        """Skorowidz zwrocil URL bez tego godla (np. arkusz PL-2000 nowszej
        kampanii) — plik trafi pod godlo PL-1992, wiec to musi byc widac."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = (
            '<html><script>var data = {url:"https://opendata.geoportal.gov.pl'
            '/NumDaneWys/NMT/99999/99999_1_6.179.12.20.asc"};</script></html>'
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=response)
        provider = GugikProvider(session=session)
        provider._validated_layers[("1m", "EVRF2007")] = ["L1"]

        with caplog.at_level("WARNING"):
            url = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert url.endswith("6.179.12.20.asc")
        assert "N-34-130-D-d-2-4" in caplog.text and "6.179.12.20" in caplog.text

    def test_get_opendata_url_uses_correct_endpoint_for_1m(
        self, mock_wms_response_with_url
    ):
        """Test że 1m używa właściwego endpointu (domyślnie EVRF2007)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_response_with_url)

        provider = GugikProvider(session=session, resolution="1m")
        provider._get_opendata_url("N-34-130-D-d-2-4")

        call_url = session.get.call_args[0][0]
        # Default vertical CRS is now EVRF2007
        assert "SkorowidzeUkladEVRF2007" in call_url

    def test_get_opendata_url_uses_correct_endpoint_for_5m(
        self, mock_wms_response_with_url
    ):
        """Test że 5m używa właściwego endpointu."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_response_with_url)

        provider = GugikProvider(
            session=session, resolution="5m", vertical_crs="EVRF2007"
        )
        provider._get_opendata_url("N-34-130-D-d-2-4")

        call_url = session.get.call_args[0][0]
        assert "SheetsGrid5mEVRF2007" in call_url


class TestGugikProviderSession:
    """Testy zarządzania sesją HTTP."""

    def test_uses_provided_session(self, tmp_path):
        """Test że provider używa dostarczonej sesji."""
        session = Mock(spec=requests.Session)

        wms_response = Mock()
        wms_response.status_code = 200
        wms_response.text = 'url:"https://opendata.geoportal.gov.pl/test.asc"'

        opendata_response = Mock()
        opendata_response.iter_content = Mock(return_value=[b"data"])

        session.get = Mock(side_effect=[wms_response, opendata_response])

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.asc"

        provider.download("N-34-130-D", output_path)

        assert session.get.called


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
