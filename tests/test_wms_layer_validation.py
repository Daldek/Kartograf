"""
Testy odkrywania warstw skorowidza WMS w GugikProvider.

GugikProvider nie ma juz zaszytych list warstw ani cichego fallbacku:
- _fetch_wms_layers(endpoint): GetCapabilities przez get_with_retry (3 proby,
  backoff), filtr <Name> wzorcem LAYER_PATTERN, sortowanie rok malejaco
  z warstwa "iStarsze" na koncu; kazda porazka (siec, zly XML, brak warstw)
  konczy sie DownloadError
- _layers(endpoint): memoizacja sukcesu per endpoint pod lockiem; porazka
  nie jest zapamietywana, kolejne wywolanie probuje ponownie
- GugikNmptProvider dziedziczy mechanizm z wlasnym wzorcem SkorowidzeNMPT*

GugikOrtoProvider zachowuje wlasna walidacje zaszytej listy WMS_LAYERS.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from tests.conftest import render_gfi_body

# ---------------------------------------------------------------------------
# XML fixtures
# ---------------------------------------------------------------------------

WMS_XML_WITH_NAMESPACE = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeNMT2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2024</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2023</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2022iStarsze</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""

WMS_XML_WITHOUT_NAMESPACE = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeNMT2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2024</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2023</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2022iStarsze</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""

# Nazwy spoza wzorca: zasiegi, warstwa zbiorcza bez roku, inne produkty
WMS_XML_MIXED_LAYERS = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeNMT2025</Name>
  </Layer><Layer>
    <Name>ZasiegiNMT2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMTNajnowsze</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMPT2025</Name>
  </Layer><Layer>
    <Name>BaseMap</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2023</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""

WMS_XML_NO_SKOROWIDZE = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>OtherLayer</Name>
  </Layer><Layer>
    <Name>BaseMap</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""

WMS_XML_RANDOM_ORDER = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeNMT2022iStarsze</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2023</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2024</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""

WMS_XML_NMT_AND_NMPT = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeNMT2026</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMPT2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMPT2026</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMPT2024iStarsze</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2023iStarsze</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENDPOINT = "https://example.com/wms"
NMT_1M_EVRF2007 = GugikProvider.WMS_SKOROWIDZE_ENDPOINTS["1m"]["EVRF2007"]
GODLO = "N-34-130-D-d-2-4"


def _make_mock_response(text: str) -> Mock:
    """Atrapa odpowiedzi HTTP 200 z podana trescia."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = text
    mock_response.raise_for_status = Mock()
    return mock_response


def _make_session(*responses) -> Mock:
    """Sesja z kolejka odpowiedzi (jedna odpowiedz = zawsze ta sama)."""
    session = Mock(spec=requests.Session)
    if len(responses) == 1:
        session.get = Mock(return_value=responses[0])
    else:
        session.get = Mock(side_effect=list(responses))
    return session


def _layer_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["LAYERS"][0]


# ===========================================================================
# TestFetchWmsLayers
# ===========================================================================


@pytest.mark.real_wms_layers
class TestFetchWmsLayers:
    """GugikProvider._fetch_wms_layers() na wstrzynietej sesji."""

    def _fetch(self, xml_text: str) -> list[str]:
        session = _make_session(_make_mock_response(xml_text))
        provider = GugikProvider(session=session)
        return provider._fetch_wms_layers(ENDPOINT, timeout=10)

    def test_uses_injected_session_for_get_capabilities(self):
        """GetCapabilities idzie przez sesje powierzona przez wolajacego."""
        session = _make_session(_make_mock_response(WMS_XML_WITH_NAMESPACE))
        provider = GugikProvider(session=session)

        provider._fetch_wms_layers(ENDPOINT, timeout=10)

        session.get.assert_called_once()
        url = session.get.call_args[0][0]
        assert url.startswith(f"{ENDPOINT}?")
        assert parse_qs(urlparse(url).query)["REQUEST"] == ["GetCapabilities"]
        assert session.get.call_args[1]["timeout"] == 10

    def test_parses_namespaced_xml(self):
        """XML WMS 1.3.0 z xmlns jest parsowany."""
        assert self._fetch(WMS_XML_WITH_NAMESPACE) == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023",
            "SkorowidzeNMT2022iStarsze",
        ]

    def test_parses_xml_without_namespace(self):
        """XML bez xmlns daje ten sam wynik."""
        assert self._fetch(WMS_XML_WITHOUT_NAMESPACE) == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023",
            "SkorowidzeNMT2022iStarsze",
        ]

    def test_sorts_newest_first_istarsze_last(self):
        """Losowa kolejnosc w XML -> rok malejaco, warstwa zbiorcza na koncu."""
        assert self._fetch(WMS_XML_RANDOM_ORDER) == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023",
            "SkorowidzeNMT2022iStarsze",
        ]

    def test_filters_names_by_layer_pattern(self):
        """Zasiegi, warstwa bez roku i inne produkty sa odrzucane."""
        assert self._fetch(WMS_XML_MIXED_LAYERS) == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2023",
        ]

    def test_no_matching_layers_raises_download_error(self):
        """Endpoint bez warstw skorowidza = DownloadError, nie pusta lista."""
        with pytest.raises(DownloadError, match="nie publikuje warstw"):
            self._fetch(WMS_XML_NO_SKOROWIDZE)

    def test_invalid_xml_raises_download_error(self):
        """Odpowiedz niebedaca XML = DownloadError."""
        with pytest.raises(DownloadError, match="nieprawidlowy XML"):
            self._fetch("This is not XML at all")

    def test_network_error_after_three_attempts_raises(self):
        """Trzy nieudane proby GetCapabilities = DownloadError (bez fallbacku)."""
        session = _make_session(*[requests.ConnectionError("refused")] * 3)
        provider = GugikProvider(session=session)

        with (
            patch("time.sleep") as mock_sleep,
            pytest.raises(DownloadError, match="pobranie nieudane po 3 probach"),
        ):
            provider._fetch_wms_layers(ENDPOINT, timeout=10)

        assert session.get.call_count == 3
        assert mock_sleep.call_count == 2

    def test_network_error_then_success_returns_layers(self):
        """Jedna zerwana proba i sukces -> lista warstw po 2 zapytaniach."""
        session = _make_session(
            requests.ConnectionError("reset"),
            _make_mock_response(WMS_XML_WITH_NAMESPACE),
        )
        provider = GugikProvider(session=session)

        with patch("time.sleep") as mock_sleep:
            result = provider._fetch_wms_layers(ENDPOINT, timeout=10)

        assert result == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023",
            "SkorowidzeNMT2022iStarsze",
        ]
        assert session.get.call_count == 2
        mock_sleep.assert_called_once()


# ===========================================================================
# TestLayers
# ===========================================================================


class TestLayers:
    """GugikProvider._layers(endpoint): memoizacja sukcesu pod lockiem."""

    @pytest.mark.real_wms_layers
    def test_memoizes_success_per_endpoint(self):
        """Drugie wywolanie dla tego samego endpointu nie odpytuje uslugi."""
        provider = GugikProvider()
        layers = ["SkorowidzeNMT2026", "SkorowidzeNMT2025iStarsze"]

        with patch.object(
            provider, "_fetch_wms_layers", return_value=layers
        ) as mock_fetch:
            first = provider._layers(ENDPOINT)
            second = provider._layers(ENDPOINT)
            provider._layers("https://example.com/other")

        assert first == second == layers
        assert mock_fetch.call_count == 2
        assert [call[0][0] for call in mock_fetch.call_args_list] == [
            ENDPOINT,
            "https://example.com/other",
        ]

    @pytest.mark.real_wms_layers
    def test_failure_is_not_memoized(self):
        """Po DownloadError kolejne wywolanie probuje ponownie i moze sie udac."""
        provider = GugikProvider()

        with patch.object(
            provider,
            "_fetch_wms_layers",
            side_effect=[DownloadError("x"), ["SkorowidzeNMT2026"]],
        ) as mock_fetch:
            with pytest.raises(DownloadError):
                provider._layers(ENDPOINT)
            result = provider._layers(ENDPOINT)

        assert result == ["SkorowidzeNMT2026"]
        assert mock_fetch.call_count == 2

    @pytest.mark.real_wms_layers
    def test_lock_serializes_concurrent_discovery(self):
        """Cztery watki naraz -> dokladnie jedno GetCapabilities, wspolny wynik."""
        provider = GugikProvider()
        calls: list[str] = []

        def slow_fetch(endpoint, timeout=10):
            calls.append(endpoint)
            time.sleep(0.05)
            return ["SkorowidzeNMT2026", "SkorowidzeNMT2025iStarsze"]

        with (
            patch.object(provider, "_fetch_wms_layers", side_effect=slow_fetch),
            ThreadPoolExecutor(max_workers=4) as pool,
        ):
            results = list(pool.map(lambda _: provider._layers(ENDPOINT), range(4)))

        assert calls == [ENDPOINT]
        assert results == [["SkorowidzeNMT2026", "SkorowidzeNMT2025iStarsze"]] * 4

    @pytest.mark.real_wms_layers
    def test_get_opendata_url_fails_before_get_feature_info(self):
        """Porazka odkrywania warstw przewraca zapytanie bez GetFeatureInfo."""
        session = _make_session(_make_mock_response(render_gfi_body([])))
        provider = GugikProvider(session=session)

        with (
            patch.object(
                provider,
                "_fetch_wms_layers",
                side_effect=DownloadError("GetCapabilities down"),
            ),
            pytest.raises(DownloadError, match="GetCapabilities down"),
        ):
            provider._get_opendata_url(GODLO)

        session.get.assert_not_called()

    def test_get_opendata_url_queries_layers_newest_first(self):
        """Puste odpowiedzi -> kazda warstwa z _layers po kolei, NoCoverageError."""
        session = _make_session(_make_mock_response(render_gfi_body([])))
        provider = GugikProvider(session=session)

        with pytest.raises(NoCoverageError, match="Brak danych NMT 1m"):
            provider._get_opendata_url(GODLO)

        urls = [call[0][0] for call in session.get.call_args_list]
        assert all(url.startswith(f"{NMT_1M_EVRF2007}?") for url in urls)
        assert [_layer_of(url) for url in urls] == provider._layers(NMT_1M_EVRF2007)
        assert [_layer_of(url) for url in urls] == [
            "SkorowidzeNMT2026",
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023iStarsze",
        ]


# ===========================================================================
# TestNmptLayerPattern
# ===========================================================================


class TestNmptLayerPattern:
    """GugikNmptProvider odkrywa warstwy wlasnym wzorcem SkorowidzeNMPT*."""

    def test_pattern_accepts_only_nmpt_names(self):
        assert GugikNmptProvider.LAYER_PATTERN.fullmatch("SkorowidzeNMPT2026")
        assert GugikNmptProvider.LAYER_PATTERN.fullmatch("SkorowidzeNMPT2023iStarsze")
        assert GugikNmptProvider.LAYER_PATTERN.fullmatch("SkorowidzeNMT2026") is None
        assert GugikProvider.LAYER_PATTERN.fullmatch("SkorowidzeNMPT2026") is None

    @pytest.mark.real_wms_layers
    def test_fetch_wms_layers_returns_only_nmpt(self):
        """GetCapabilities z warstwami obu produktow -> tylko NMPT, posortowane."""
        session = _make_session(_make_mock_response(WMS_XML_NMT_AND_NMPT))
        provider = GugikNmptProvider(session=session)

        result = provider._fetch_wms_layers(ENDPOINT, timeout=10)

        assert result == [
            "SkorowidzeNMPT2026",
            "SkorowidzeNMPT2025",
            "SkorowidzeNMPT2024iStarsze",
        ]


# ===========================================================================
# TestOrtoLayerValidation
# ===========================================================================


_ORTO_SESSION_PATCH = "kartograf.providers.pl.gugik_orto.requests.Session"

ORTO_WMS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeOrtofotomapy2024</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapyStarsze</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapy2026</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapy2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapyZasiegi2026</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapyZasiegiStarsze</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""


class TestOrtoLayerValidation:
    """Tests for GugikOrtoProvider WMS GetCapabilities validation."""

    def test_hardcoded_orto_layers(self):
        """Hardcoded orto layers match the verified GetCapabilities set."""
        assert GugikOrtoProvider.WMS_LAYERS == [
            "SkorowidzeOrtofotomapy2026",
            "SkorowidzeOrtofotomapy2025",
            "SkorowidzeOrtofotomapy2024",
            "SkorowidzeOrtofotomapyStarsze",
        ]

    @pytest.mark.real_wms_layers
    def test_fetch_orto_layers_sorts_and_excludes_zasiegi(self):
        """Year layers sort descending, Starsze last, Zasiegi excluded."""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response(ORTO_WMS_XML)
        provider = GugikOrtoProvider()

        with patch(_ORTO_SESSION_PATCH, return_value=mock_session):
            result = provider._fetch_wms_layers(timeout=10)

        assert result == [
            "SkorowidzeOrtofotomapy2026",
            "SkorowidzeOrtofotomapy2025",
            "SkorowidzeOrtofotomapy2024",
            "SkorowidzeOrtofotomapyStarsze",
        ]

    @pytest.mark.real_wms_layers
    def test_fetch_orto_layers_empty_raises(self):
        """ValueError raised when no SkorowidzeOrtofotomapy layers found."""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response(WMS_XML_NO_SKOROWIDZE)
        provider = GugikOrtoProvider()

        with (
            patch(_ORTO_SESSION_PATCH, return_value=mock_session),
            pytest.raises(ValueError),
        ):
            provider._fetch_wms_layers(timeout=10)

    def test_get_validated_orto_returns_discovered_on_mismatch(self):
        """Discovered layers used (with warning) when they differ from hardcoded."""
        provider = GugikOrtoProvider()
        discovered = ["SkorowidzeOrtofotomapy2027", "SkorowidzeOrtofotomapyStarsze"]
        assert set(discovered) != set(GugikOrtoProvider.WMS_LAYERS)

        with (
            patch.object(provider, "_fetch_wms_layers", return_value=discovered),
            patch("kartograf.providers.pl.gugik_orto.logger") as mock_logger,
        ):
            result = provider._get_validated_layers()

        assert result == discovered
        mock_logger.warning.assert_called_once()

    def test_get_validated_orto_returns_hardcoded_on_match(self):
        """Hardcoded layers used (no warning) when GetCapabilities matches."""
        provider = GugikOrtoProvider()
        hardcoded = list(GugikOrtoProvider.WMS_LAYERS)

        with (
            patch.object(provider, "_fetch_wms_layers", return_value=hardcoded),
            patch("kartograf.providers.pl.gugik_orto.logger") as mock_logger,
        ):
            result = provider._get_validated_layers()

        assert result == hardcoded
        mock_logger.warning.assert_not_called()

    def test_get_validated_orto_falls_back_on_network_error(self):
        """On network error, hardcoded layers returned with a warning."""
        provider = GugikOrtoProvider()
        hardcoded = list(GugikOrtoProvider.WMS_LAYERS)

        with (
            patch.object(
                provider,
                "_fetch_wms_layers",
                side_effect=requests.ConnectionError("timeout"),
            ),
            patch("kartograf.providers.pl.gugik_orto.logger") as mock_logger,
        ):
            result = provider._get_validated_layers()

        assert result == hardcoded
        mock_logger.warning.assert_called_once()

    def test_get_validated_orto_caches_result(self):
        """Second call uses cache; _fetch_wms_layers called once."""
        provider = GugikOrtoProvider()
        hardcoded = list(GugikOrtoProvider.WMS_LAYERS)

        with patch.object(
            provider, "_fetch_wms_layers", return_value=hardcoded
        ) as mock_fetch:
            provider._get_validated_layers()
            provider._get_validated_layers()

        mock_fetch.assert_called_once()
