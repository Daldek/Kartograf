"""
Testy jednostkowe dla modułu gugik provider.

Ten moduł zawiera testy dla klasy GugikProvider, weryfikujące poprawność
konstruowania URL-i i pobierania danych z mockami HTTP.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

import requests

from kartograf.exceptions import DownloadError
from kartograf.providers.gugik import GugikProvider


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
        """Test obsługiwanych formatów."""
        provider = GugikProvider()
        formats = provider.get_supported_formats()

        assert "GTiff" in formats
        assert "AAIGrid" in formats
        assert "XYZ" in formats
        assert len(formats) == 3

    def test_file_extensions(self):
        """Test rozszerzeń plików."""
        provider = GugikProvider()

        assert provider.get_file_extension("GTiff") == ".tif"
        assert provider.get_file_extension("AAIGrid") == ".asc"
        assert provider.get_file_extension("XYZ") == ".xyz"

    def test_file_extension_invalid_format(self):
        """Test rozszerzenia dla nieprawidłowego formatu."""
        provider = GugikProvider()

        with pytest.raises(ValueError, match="Unknown format"):
            provider.get_file_extension("InvalidFormat")


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


class TestGugikProviderConstructUrl:
    """Testy konstruowania URL."""

    def test_construct_url_default_format(self):
        """Test konstruowania URL z domyślnym formatem."""
        provider = GugikProvider()
        url = provider.construct_url("N-34-130-D-d-2-4")

        assert "mapy.geoportal.gov.pl" in url
        assert "N-34-130-D-d-2-4" in url
        assert "SERVICE=WCS" in url
        assert "REQUEST=GetCoverage" in url
        assert "image%2Ftiff" in url or "image/tiff" in url

    def test_construct_url_gtiff_format(self):
        """Test konstruowania URL dla formatu GTiff."""
        provider = GugikProvider()
        url = provider.construct_url("N-34-130-D", format="GTiff")

        assert "image%2Ftiff" in url or "image/tiff" in url

    def test_construct_url_aaigrid_format(self):
        """Test konstruowania URL dla formatu AAIGrid."""
        provider = GugikProvider()
        url = provider.construct_url("N-34-130-D", format="AAIGrid")

        assert "application%2Fx-ogc-aaigrid" in url or "x-ogc-aaigrid" in url

    def test_construct_url_xyz_format(self):
        """Test konstruowania URL dla formatu XYZ."""
        provider = GugikProvider()
        url = provider.construct_url("N-34-130-D", format="XYZ")

        assert "text%2Fplain" in url or "text/plain" in url

    def test_construct_url_invalid_format(self):
        """Test konstruowania URL z nieprawidłowym formatem."""
        provider = GugikProvider()

        with pytest.raises(ValueError, match="Unsupported format"):
            provider.construct_url("N-34-130-D", format="InvalidFormat")

    def test_construct_url_normalizes_godlo(self):
        """Test że URL zawiera znormalizowane godło."""
        provider = GugikProvider()

        # Małe litery powinny być znormalizowane
        url = provider.construct_url("n-34-130-d")
        assert "N-34-130-D" in url

    def test_construct_url_wcs_parameters(self):
        """Test że URL zawiera wymagane parametry WCS."""
        provider = GugikProvider()
        url = provider.construct_url("N-34-130-D")

        assert "SERVICE=WCS" in url
        assert "VERSION=2.0.1" in url
        assert "REQUEST=GetCoverage" in url
        assert "COVERAGEID=" in url
        assert "FORMAT=" in url


class TestGugikProviderDownload:
    """Testy pobierania danych z mockami HTTP."""

    @pytest.fixture
    def mock_response(self):
        """Fixture z mockowaną odpowiedzią HTTP."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.iter_content = Mock(return_value=[b"test", b"data"])
        return response

    @pytest.fixture
    def provider_with_mock_session(self, mock_response):
        """Fixture z providerem używającym mockowanej sesji."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_response)
        return GugikProvider(session=session), session

    def test_download_success(self, tmp_path, provider_with_mock_session):
        """Test udanego pobierania."""
        provider, session = provider_with_mock_session
        output_path = tmp_path / "test.tif"

        result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert output_path.exists()
        session.get.assert_called_once()

    def test_download_creates_directory(self, tmp_path, provider_with_mock_session):
        """Test że pobieranie tworzy katalog docelowy."""
        provider, _ = provider_with_mock_session
        output_path = tmp_path / "subdir" / "nested" / "test.tif"

        result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert output_path.parent.exists()

    def test_download_saves_content(self, tmp_path, provider_with_mock_session):
        """Test że pobieranie zapisuje zawartość pliku."""
        provider, _ = provider_with_mock_session
        output_path = tmp_path / "test.tif"

        provider.download("N-34-130-D", output_path)

        content = output_path.read_bytes()
        assert content == b"testdata"

    def test_download_with_timeout(self, tmp_path, provider_with_mock_session):
        """Test pobierania z określonym timeout."""
        provider, session = provider_with_mock_session
        output_path = tmp_path / "test.tif"

        provider.download("N-34-130-D", output_path, timeout=60)

        call_kwargs = session.get.call_args.kwargs
        assert call_kwargs["timeout"] == 60

    def test_download_retry_on_failure(self, tmp_path):
        """Test ponawiania próby po błędzie."""
        session = Mock(spec=requests.Session)

        # Pierwsza próba nie udana, druga udana
        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        success_response = Mock()
        success_response.iter_content = Mock(return_value=[b"data"])

        session.get = Mock(side_effect=[fail_response, success_response])

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.tif"

        with patch("time.sleep"):  # Skip actual sleep
            result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert session.get.call_count == 2

    def test_download_retry_exhausted(self, tmp_path):
        """Test błędu po wyczerpaniu prób."""
        session = Mock(spec=requests.Session)
        response = Mock()
        response.raise_for_status.side_effect = requests.RequestException("Error")
        session.get = Mock(return_value=response)

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.tif"

        with patch("time.sleep"):  # Skip actual sleep
            with pytest.raises(DownloadError) as exc_info:
                provider.download("N-34-130-D", output_path)

        assert "N-34-130-D" in str(exc_info.value)
        assert exc_info.value.godlo == "N-34-130-D"
        assert session.get.call_count == 3  # MAX_RETRIES

    def test_download_exponential_backoff(self, tmp_path):
        """Test exponential backoff między próbami."""
        session = Mock(spec=requests.Session)
        response = Mock()
        response.raise_for_status.side_effect = requests.RequestException("Error")
        session.get = Mock(return_value=response)

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.tif"

        sleep_times = []

        with patch("time.sleep", side_effect=lambda t: sleep_times.append(t)):
            with pytest.raises(DownloadError):
                provider.download("N-34-130-D", output_path)

        # Exponential backoff: 2^1=2, 2^2=4 seconds
        assert sleep_times == [2, 4]

    def test_download_atomic_write(self, tmp_path, provider_with_mock_session):
        """Test atomowego zapisu (temp file → rename)."""
        provider, _ = provider_with_mock_session
        output_path = tmp_path / "test.tif"

        # Check that no temp file remains
        provider.download("N-34-130-D", output_path)

        temp_path = output_path.with_suffix(".tif.tmp")
        assert not temp_path.exists()
        assert output_path.exists()

    def test_download_cleanup_on_error(self, tmp_path):
        """Test czyszczenia pliku tymczasowego przy błędzie zapisu."""
        session = Mock(spec=requests.Session)
        response = Mock()
        response.iter_content = Mock(side_effect=IOError("Write error"))
        session.get = Mock(return_value=response)

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.tif"

        with pytest.raises(IOError):
            provider.download("N-34-130-D", output_path)

        temp_path = output_path.with_suffix(".tif.tmp")
        assert not temp_path.exists()


class TestGugikProviderSession:
    """Testy zarządzania sesją HTTP."""

    def test_uses_provided_session(self, tmp_path):
        """Test że provider używa dostarczonej sesji."""
        session = Mock(spec=requests.Session)
        response = Mock()
        response.iter_content = Mock(return_value=[b"data"])
        session.get = Mock(return_value=response)

        provider = GugikProvider(session=session)
        output_path = tmp_path / "test.tif"

        provider.download("N-34-130-D", output_path)

        session.get.assert_called_once()

    def test_creates_new_session_if_not_provided(self, tmp_path):
        """Test że provider tworzy nową sesję jeśli nie podano."""
        provider = GugikProvider()

        with patch("kartograf.providers.gugik.requests.Session") as mock_session_class:
            mock_session = MagicMock()
            mock_response = Mock()
            mock_response.iter_content = Mock(return_value=[b"data"])
            mock_session.get = Mock(return_value=mock_response)
            mock_session_class.return_value = mock_session

            output_path = tmp_path / "test.tif"
            provider.download("N-34-130-D", output_path)

            mock_session_class.assert_called_once()


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
