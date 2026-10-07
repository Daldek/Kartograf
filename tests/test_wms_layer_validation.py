"""
Testy odkrywania warstw skorowidza WMS (SkorowidzLayersMixin w GugikProvider).

GugikProvider nie ma juz zaszytych list warstw ani cichego fallbacku:
- _fetch_wms_layers(endpoint): GetCapabilities przez get_with_retry (3 proby,
  backoff), filtr <Name> wzorcem LAYER_PATTERN, sortowanie rok malejaco
  z warstwa "iStarsze" na koncu; kazda porazka (siec, zly XML, brak warstw)
  konczy sie DownloadError
- _layers(endpoint): memoizacja sukcesu per endpoint pod lockiem; porazka
  nie jest zapamietywana, kolejne wywolanie probuje ponownie
- GugikNmptProvider dziedziczy mechanizm z wlasnym wzorcem SkorowidzeNMPT*

GugikOrtoProvider dzieli ten sam mixin (wzorzec SkorowidzeOrtofotomapy*,
warstwa "Starsze" bez roku) — testy w tests/test_gugik_orto.py.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch
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
# N3 / E10: GetCapabilities skorowidza z timeoutem providera
# ===========================================================================


@pytest.mark.real_wms_layers
class TestCapabilitiesTimeout:
    """N3: GetCapabilities dostaje timeout providera (30 s NMT/NMPT, 60 s orto),
    a nie zaszyte 10 s — porazka tego zapytania konczy caly tor."""

    CAPS = {
        "nmt": WMS_XML_WITH_NAMESPACE,
        "nmpt": WMS_XML_NMT_AND_NMPT,
        "orto": WMS_XML_WITH_NAMESPACE.replace(
            "SkorowidzeNMT2022iStarsze", "SkorowidzeOrtofotomapyStarsze"
        ).replace("SkorowidzeNMT", "SkorowidzeOrtofotomapy"),
    }

    @staticmethod
    def _provider(product, session):
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        cls = {
            "nmt": GugikProvider,
            "nmpt": GugikNmptProvider,
            "orto": GugikOrtoProvider,
        }[product]
        return cls(session=session)

    @pytest.mark.parametrize(
        ("product", "expected"), [("nmt", 30), ("nmpt", 30), ("orto", 60)]
    )
    def test_capabilities_use_provider_timeout(self, tmp_path, product, expected):
        caps = _make_mock_response(self.CAPS[product])
        empty = _make_mock_response(render_gfi_body([]))
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=lambda url, **kw: caps if "GetCapabilities" in url else empty
        )
        provider = self._provider(product, session)

        with pytest.raises(NoCoverageError):
            provider.download(GODLO, tmp_path / "x")

        timeouts = [
            call.kwargs.get("timeout")
            for call in session.get.call_args_list
            if "GetCapabilities" in call.args[0]
        ]
        assert timeouts == [expected]

    def test_explicit_download_timeout_reaches_capabilities(self, tmp_path):
        caps = _make_mock_response(WMS_XML_WITH_NAMESPACE)
        empty = _make_mock_response(render_gfi_body([]))
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=lambda url, **kw: caps if "GetCapabilities" in url else empty
        )

        with pytest.raises(NoCoverageError):
            GugikProvider(session=session).download(GODLO, tmp_path / "x", timeout=45)

        caps_call = next(
            c for c in session.get.call_args_list if "GetCapabilities" in c.args[0]
        )
        assert caps_call.kwargs["timeout"] == 45

    @pytest.mark.parametrize(("product", "expected"), [("nmt", 30), ("orto", 60)])
    def test_layers_default_timeout_is_provider_timeout(self, product, expected):
        session = _make_session(_make_mock_response(self.CAPS[product]))

        self._provider(product, session)._layers(ENDPOINT)

        assert session.get.call_args.kwargs["timeout"] == expected


# ===========================================================================
# ADR-030: rodzina nazw warstw (LAYER_FAMILY) na realnych GetCapabilities
# ===========================================================================

CAPS = (
    Path(__file__).parent / "fixtures" / "gugik_skorowidz" / "real_2026_10_06" / "caps"
)


def _caps(name: str) -> str:
    return (CAPS / name).read_text(encoding="utf-8")


@pytest.mark.real_wms_layers
def test_real_caps_orto_skips_default_wms_and_zasiegi_without_warning(caplog):
    session = _make_session(
        _make_mock_response(_caps("ORTO_WMS_SkorowidzeWgAktualnosci.xml"))
    )
    provider = GugikOrtoProvider(session=session)
    with caplog.at_level(logging.WARNING):
        layers = provider._fetch_wms_layers(ENDPOINT, timeout=10)
    assert layers == [
        "SkorowidzeOrtofotomapy2026",
        "SkorowidzeOrtofotomapy2025",
        "SkorowidzeOrtofotomapy2024",
        "SkorowidzeOrtofotomapyStarsze",
    ]
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.real_wms_layers
def test_family_name_outside_pattern_warns_and_is_not_queried(caplog):
    xml = _caps("NMT_WMS_SkorowidzeUkladEVRF2007.xml")
    assert "<Name>SkorowidzeNMT2026</Name>" in xml
    xml = xml.replace(
        "<Name>SkorowidzeNMT2026</Name>",
        "<Name>SkorowidzeNMT2026</Name><Name>SkorowidzeNMT2027Kwartal1</Name>",
        1,
    )
    provider = GugikProvider(session=_make_session(_make_mock_response(xml)))
    with caplog.at_level(logging.WARNING):
        layers = provider._fetch_wms_layers(ENDPOINT, timeout=10)
    assert "SkorowidzeNMT2027Kwartal1" not in layers
    assert "SkorowidzeNMT2026" in layers
    assert "SkorowidzeNMT2027Kwartal1" in caplog.text
    assert "NIE odpytywana" in caplog.text


@pytest.mark.real_wms_layers
def test_nmt_family_does_not_warn_for_nmpt_names(caplog):
    xml = _caps("NMPT_WMS_SkorowidzeUkladEVRF2007.xml")
    provider = GugikProvider(session=_make_session(_make_mock_response(xml)))
    with caplog.at_level(logging.WARNING), pytest.raises(DownloadError):
        provider._fetch_wms_layers(ENDPOINT, timeout=10)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
