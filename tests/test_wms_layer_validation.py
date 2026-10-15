"""
Tests of GUGiK index (skorowidz) layer discovery.

- NMT/NMPT (``WfsSkorowidzLayersMixin``, 0.8.0): the yearly feature types of
  the WFS index service of the variant come from one GetCapabilities per
  service, memoized only on success; ``_layers`` gives ONE query group (every
  type, comma-joined). A discovery failure fails the sheet query before any
  GetFeature (``DownloadError``, never no coverage). Parsing of the WFS
  capabilities: ``tests/test_skorowidz_wfs.py``.
- Orthophoto (``SkorowidzLayersMixin``, WMS GetCapabilities): the
  ``SkorowidzeOrtofotomapy*`` layers on a real recording and the provider
  timeout; the rest of its discovery is in ``tests/test_gugik_orto.py``.

GetCapabilities gets the provider timeout (N3: 30 s NMT/NMPT, 60 s ortho).
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from tests.conftest import (
    make_provider,
    render_gfi_body,
    render_wfs_body,
    wfs_endpoint,
    wfs_fixture,
    wfs_requests,
    wfs_response,
    wfs_types,
)

ENDPOINT = "https://example.com/wms"
SHEET = "N-34-130-D-d-2-4"
OTHER_SHEET = "N-34-130-D-d-2-3"
NMT_EVRF2007 = wfs_endpoint("nmt_evrf2007")
NMT_KRON86 = wfs_endpoint("nmt_kron86")
# WFS index services of the NMT/NMPT providers, by fixture tag
WFS_TAGS = ("nmt_evrf2007", "nmt_kron86", "nmpt_evrf2007", "nmpt_kron86")


def _make_mock_response(text: str) -> Mock:
    """Fake HTTP 200 response with the given body."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = text
    mock_response.raise_for_status = Mock()
    return mock_response


def _make_session(*responses) -> Mock:
    """A session with a queue of responses (one response = always the same)."""
    session = Mock(spec=requests.Session)
    if len(responses) == 1:
        session.get = Mock(return_value=responses[0])
    else:
        session.get = Mock(side_effect=list(responses))
    return session


def _is_caps(url: str) -> bool:
    return "REQUEST=GetCapabilities" in url


def _wfs_session(caps: dict[str, list] | None = None) -> Mock:
    """Session of the NMT/NMPT WFS services: GetCapabilities answers the
    recorded caps of the service (``caps``: endpoint -> queue of answers or
    exceptions overriding it), GetFeature an empty collection (no coverage)."""
    queues = {endpoint: list(answers) for endpoint, answers in (caps or {}).items()}

    def get(url: str, **kwargs):
        if not _is_caps(url):
            return wfs_response(render_wfs_body([]))
        endpoint = url.split("?", 1)[0]
        if queues.get(endpoint):
            answer = queues[endpoint].pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        tag = next(t for t in WFS_TAGS if wfs_endpoint(t) == endpoint)
        return wfs_response(wfs_fixture(f"caps_{tag}.xml"))

    session = Mock(spec=requests.Session)
    session.get = Mock(side_effect=get)
    return session


def _caps_calls(session: Mock, endpoint: str) -> list:
    return [
        call
        for call in session.get.call_args_list
        if call.args[0].startswith(f"{endpoint}?") and _is_caps(call.args[0])
    ]


# ===========================================================================
# NMT/NMPT: yearly WFS feature types of the index service
# ===========================================================================


@pytest.mark.real_wfs_types
class TestWfsFeatureTypes:
    """Feature types of the NMT/NMPT WFS index from GetCapabilities."""

    @staticmethod
    def _nmt(session: Mock) -> GugikProvider:
        return GugikProvider(session=session, vertical_crs="EVRF2007", resolution="1m")

    def test_types_discovered_once_per_service(self, tmp_path):
        """Two sheets without coverage: one GetCapabilities per service (own
        index, and the other height system asked for the P10 hint); every
        GetFeature of the own index carries all its yearly types."""
        session = _wfs_session()
        provider = self._nmt(session)

        for sheet in (SHEET, OTHER_SHEET):
            with pytest.raises(NoCoverageError):
                provider.download(sheet, tmp_path / "x.asc")

        assert len(_caps_calls(session, NMT_EVRF2007)) == 1
        assert len(_caps_calls(session, NMT_KRON86)) == 1
        own = wfs_requests(session, NMT_EVRF2007)
        assert [q["TYPENAMES"] for q in own] == [
            ",".join(wfs_types("nmt_evrf2007"))
        ] * 2

    @pytest.mark.parametrize(
        "answer",
        [
            pytest.param(
                wfs_response(wfs_fixture("exception_report.xml")),
                id="exception-report",
            ),
            pytest.param(wfs_response("<html>Blad</html"), id="not-xml"),
            pytest.param(
                wfs_response(wfs_fixture("caps_laz_evrf2007.xml")),
                id="no-nmt-types",
            ),
        ],
    )
    def test_discovery_failure_fails_sheet_before_get_feature(self, tmp_path, answer):
        """A failed type discovery is a DownloadError of the sheet (the result
        would be incomplete) - no GetFeature, no file, never no coverage."""
        session = _wfs_session({NMT_EVRF2007: [answer]})

        with pytest.raises(DownloadError, match="wynik bylby niepelny") as exc:
            self._nmt(session).download(SHEET, tmp_path / "x.asc")

        assert not isinstance(exc.value, NoCoverageError)
        assert wfs_requests(session) == []
        assert len(session.get.call_args_list) == 1

    def test_network_failure_after_retries_fails_before_get_feature(self, tmp_path):
        """GetCapabilities failing on every try (3) = DownloadError, no GetFeature."""
        failures = [requests.ConnectionError("refused")] * 3
        session = _wfs_session({NMT_EVRF2007: failures})

        with (
            patch("time.sleep"),
            pytest.raises(DownloadError, match="wynik bylby niepelny"),
        ):
            self._nmt(session).download(SHEET, tmp_path / "x.asc")

        assert len(_caps_calls(session, NMT_EVRF2007)) == 3
        assert wfs_requests(session) == []

    def test_failure_is_not_memoized(self, tmp_path):
        """After a failed discovery the next sheet asks again and goes on; the
        success is memoized from then on."""
        session = _wfs_session({NMT_EVRF2007: [wfs_response("not xml")]})
        provider = self._nmt(session)

        with pytest.raises(DownloadError):
            provider.download(SHEET, tmp_path / "x.asc")
        for sheet in (SHEET, OTHER_SHEET):
            with pytest.raises(NoCoverageError):
                provider.download(sheet, tmp_path / "x.asc")

        assert len(_caps_calls(session, NMT_EVRF2007)) == 2
        assert len(wfs_requests(session, NMT_EVRF2007)) == 2

    def test_concurrent_threads_trigger_one_get_capabilities(self):
        """Four threads at once -> exactly one GetCapabilities, shared result:
        one group with every yearly type of the service."""
        caps = wfs_response(wfs_fixture("caps_nmt_evrf2007.xml"))

        def slow_caps(url, **kwargs):
            time.sleep(0.05)
            return caps

        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=slow_caps)
        provider = self._nmt(session)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: provider._layers(NMT_EVRF2007), range(4)))

        assert session.get.call_count == 1
        assert results == [[",".join(wfs_types("nmt_evrf2007"))]] * 4

    @pytest.mark.parametrize(
        ("cls", "own", "other"),
        [
            (GugikProvider, "nmt_evrf2007", "nmt_kron86"),
            (GugikNmptProvider, "nmpt_evrf2007", "nmpt_kron86"),
        ],
    )
    def test_capabilities_use_provider_timeout(self, tmp_path, cls, own, other):
        """N3: the index GetCapabilities gets the provider timeout (30 s), not
        a shorter hard-coded one - its failure ends the whole sheet (the P10
        service of the other height system gets the same)."""
        session = _wfs_session()
        provider = make_provider(cls, session=session)

        with pytest.raises(NoCoverageError):
            provider.download(SHEET, tmp_path / "x.asc")

        for tag in (own, other):
            calls = _caps_calls(session, wfs_endpoint(tag))
            assert [call.kwargs.get("timeout") for call in calls] == [30]


# ===========================================================================
# Orthophoto: WMS GetCapabilities
# ===========================================================================

ORTO_CAPS = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeOrtofotomapy2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapy2024</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapyStarsze</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""


@pytest.mark.real_wms_layers
class TestOrtoCapabilitiesTimeout:
    """N3: the orthophoto GetCapabilities gets the provider timeout (60 s)."""

    def test_capabilities_use_provider_timeout(self, tmp_path):
        caps = _make_mock_response(ORTO_CAPS)
        empty = _make_mock_response(render_gfi_body([]))
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=lambda url, **kw: caps if "GetCapabilities" in url else empty
        )
        provider = GugikOrtoProvider(session=session, color="RGB")

        with pytest.raises(NoCoverageError):
            provider.download(SHEET, tmp_path / "x")

        own = GugikOrtoProvider.WMS_INDEX_ENDPOINT
        timeouts = [call.kwargs.get("timeout") for call in _caps_calls(session, own)]
        assert timeouts == [60]

    def test_layers_default_timeout_is_provider_timeout(self):
        session = _make_session(_make_mock_response(ORTO_CAPS))

        GugikOrtoProvider(session=session, color="RGB")._layers(ENDPOINT)

        assert session.get.call_args.kwargs["timeout"] == 60


# ===========================================================================
# ADR-030: orthophoto layer name family on a real GetCapabilities
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
    provider = GugikOrtoProvider(session=session, color="RGB")
    with caplog.at_level(logging.WARNING):
        layers = provider._fetch_wms_layers(ENDPOINT, timeout=10)
    assert layers == [
        "SkorowidzeOrtofotomapy2026",
        "SkorowidzeOrtofotomapy2025",
        "SkorowidzeOrtofotomapy2024",
        "SkorowidzeOrtofotomapyStarsze",
    ]
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
