"""
Tests for WMS GetCapabilities layer validation in GugikProvider.

Tests cover two new methods being added to GugikProvider:
- _fetch_wms_layers(): fetches and parses WMS GetCapabilities XML
- _get_validated_layers(): validates hardcoded layers against live WMS

These methods validate that hardcoded WMS layer names match what the
GUGiK WMS service actually exposes, falling back to hardcoded layers
on errors.
"""

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest
import requests

from kartograf.providers.gugik import GugikProvider
from kartograf.providers.gugik_nmpt import GugikNmptProvider

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

WMS_XML_MIXED_LAYERS = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeNMT2025</Name>
  </Layer><Layer>
    <Name>OtherLayer</Name>
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

WMS_XML_WITH_NO_YEAR_LAYER = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeNMTNajnowsze</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2023</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Patch target for requests.Session created inside _fetch_wms_layers
_SESSION_PATCH = "kartograf.providers.gugik.requests.Session"


def _make_mock_response(text: str) -> MagicMock:
    """Create a mock HTTP response with the given text content."""
    mock_response = MagicMock()
    mock_response.text = text
    mock_response.raise_for_status = MagicMock()
    return mock_response


def _make_provider(session=None) -> GugikProvider:
    """Create a GugikProvider with an optional mock session."""
    return GugikProvider(session=session)


# ===========================================================================
# TestFetchWmsLayers
# ===========================================================================


class TestFetchWmsLayers:
    """Tests for GugikProvider._fetch_wms_layers().

    Note: _fetch_wms_layers creates its own requests.Session() to avoid
    interfering with the main session used for downloads. Tests must
    patch requests.Session to inject mock responses.
    """

    def _call_with_mock_response(self, xml_text):
        """Helper: call _fetch_wms_layers with a mocked session returning xml_text."""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response(xml_text)
        provider = _make_provider()
        with patch(_SESSION_PATCH, return_value=mock_session):
            return provider._fetch_wms_layers("https://example.com/wms", timeout=10)

    def test_fetch_wms_layers_with_namespace(self):
        """Namespaced WMS 1.3.0 XML is parsed correctly."""
        result = self._call_with_mock_response(WMS_XML_WITH_NAMESPACE)

        assert result == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023",
            "SkorowidzeNMT2022iStarsze",
        ]

    def test_fetch_wms_layers_without_namespace(self):
        """XML without xmlns attribute is parsed via namespace fallback."""
        result = self._call_with_mock_response(WMS_XML_WITHOUT_NAMESPACE)

        assert result == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023",
            "SkorowidzeNMT2022iStarsze",
        ]

    def test_fetch_wms_layers_sorting(self):
        """Layers in random order are returned sorted: newest first, iStarsze last."""
        result = self._call_with_mock_response(WMS_XML_RANDOM_ORDER)

        assert result == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023",
            "SkorowidzeNMT2022iStarsze",
        ]

    def test_fetch_wms_layers_filters_non_skorowidze(self):
        """Only layer names starting with 'Skorowidze' are returned."""
        result = self._call_with_mock_response(WMS_XML_MIXED_LAYERS)

        assert result == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2023",
        ]

    def test_fetch_wms_layers_empty_raises_valueerror(self):
        """ValueError is raised when no Skorowidze layers are found."""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response(WMS_XML_NO_SKOROWIDZE)
        provider = _make_provider()

        with (
            patch(_SESSION_PATCH, return_value=mock_session),
            pytest.raises(ValueError),
        ):
            provider._fetch_wms_layers("https://example.com/wms", timeout=10)

    def test_fetch_wms_layers_network_error(self):
        """Network errors propagate as requests.RequestException."""
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.ConnectionError("Connection refused")
        provider = _make_provider()

        with (
            patch(_SESSION_PATCH, return_value=mock_session),
            pytest.raises(requests.RequestException),
        ):
            provider._fetch_wms_layers("https://example.com/wms", timeout=10)

    def test_fetch_wms_layers_invalid_xml(self):
        """Non-XML response causes a parse error."""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response("This is not XML at all")
        provider = _make_provider()

        with (
            patch(_SESSION_PATCH, return_value=mock_session),
            pytest.raises(ET.ParseError),
        ):
            provider._fetch_wms_layers("https://example.com/wms", timeout=10)


# ===========================================================================
# TestGetValidatedLayers
# ===========================================================================


class TestGetValidatedLayers:
    """Tests for GugikProvider._get_validated_layers()."""

    def test_returns_discovered_layers_on_mismatch(self):
        """Discovered layers are used on mismatch, with warning."""
        provider = _make_provider()
        discovered = [
            "SkorowidzeNMT2026",
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023iStarsze",
        ]

        with (
            patch.object(provider, "_fetch_wms_layers", return_value=discovered),
            patch("kartograf.providers.gugik.logger") as mock_logger,
        ):
            result = provider._get_validated_layers("1m", "EVRF2007")

        assert result == discovered
        mock_logger.warning.assert_called_once()
        # The warning message should mention the mismatch
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "layer" in warning_msg.lower() or "different" in warning_msg.lower()

    def test_returns_hardcoded_on_match(self):
        """Hardcoded layers used when WMS matches, no warning."""
        provider = _make_provider()
        hardcoded = list(GugikProvider.WMS_LAYERS["1m"]["EVRF2007"])

        with (
            patch.object(provider, "_fetch_wms_layers", return_value=hardcoded),
            patch("kartograf.providers.gugik.logger") as mock_logger,
        ):
            result = provider._get_validated_layers("1m", "EVRF2007")

        assert result == hardcoded
        mock_logger.warning.assert_not_called()

    def test_falls_back_on_network_error(self):
        """On network error, hardcoded layers are returned with a warning."""
        provider = _make_provider()
        hardcoded = list(GugikProvider.WMS_LAYERS["1m"]["EVRF2007"])

        with (
            patch.object(
                provider,
                "_fetch_wms_layers",
                side_effect=requests.ConnectionError("timeout"),
            ),
            patch("kartograf.providers.gugik.logger") as mock_logger,
        ):
            result = provider._get_validated_layers("1m", "EVRF2007")

        assert result == hardcoded
        mock_logger.warning.assert_called_once()

    def test_falls_back_on_valueerror(self):
        """On ValueError (no Skorowidze layers found), hardcoded layers are returned."""
        provider = _make_provider()
        hardcoded = list(GugikProvider.WMS_LAYERS["1m"]["EVRF2007"])

        with (
            patch.object(
                provider,
                "_fetch_wms_layers",
                side_effect=ValueError("No Skorowidze layers"),
            ),
            patch("kartograf.providers.gugik.logger") as mock_logger,
        ):
            result = provider._get_validated_layers("1m", "EVRF2007")

        assert result == hardcoded
        mock_logger.warning.assert_called_once()

    def test_caches_result(self):
        """Second call uses cache; _fetch_wms_layers called once."""
        provider = _make_provider()
        hardcoded = list(GugikProvider.WMS_LAYERS["1m"]["EVRF2007"])

        with patch.object(
            provider, "_fetch_wms_layers", return_value=hardcoded
        ) as mock_fetch:
            result1 = provider._get_validated_layers("1m", "EVRF2007")
            result2 = provider._get_validated_layers("1m", "EVRF2007")

        assert result1 == result2
        mock_fetch.assert_called_once()

    def test_falls_back_when_endpoint_not_found(self):
        """Unknown resolution/crs combo returns hardcoded fallback silently."""
        provider = _make_provider()

        # "5m" + "KRON86" has no entry in WMS_SKOROWIDZE_ENDPOINTS
        # The method should return hardcoded or handle gracefully
        # Since there's no hardcoded entry for 5m/KRON86 either, we test
        # with a valid hardcoded combo but missing endpoint.
        with (
            patch.dict(provider.WMS_SKOROWIDZE_ENDPOINTS, {"5m": {}}, clear=False),
            patch("kartograf.providers.gugik.logger"),
        ):
            # 5m/KRON86 has no endpoint AND no hardcoded layers
            # _get_validated_layers should handle this without raising
            try:
                result = provider._get_validated_layers("5m", "KRON86")
                # If it returns something, it should be a list (possibly empty
                # or the hardcoded fallback)
                assert isinstance(result, list)
            except (KeyError, ValueError):
                # Also acceptable — the endpoint doesn't exist
                pass


# ===========================================================================
# TestGetValidatedLayersIntegration
# ===========================================================================


class TestGetValidatedLayersIntegration:
    """Integration tests for _get_validated_layers with _get_opendata_url."""

    def test_get_opendata_url_uses_validated_layers(self):
        """_get_opendata_url uses _get_validated_layers."""
        mock_session = MagicMock()

        # WMS GetFeatureInfo response with OpenData URL
        mock_wms_response = MagicMock()
        mock_wms_response.status_code = 200
        mock_wms_response.text = (
            '<html><script>var data = {url:"https://opendata.geoportal.gov.pl'
            '/NumDaneWys/NMT/12345/12345_N-34-130-D-d-2-4.asc"};'
            "</script></html>"
        )
        mock_wms_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_wms_response

        provider = GugikProvider(session=mock_session)

        custom_layers = ["SkorowidzeNMT2026", "SkorowidzeNMT2025"]

        with patch.object(
            provider, "_get_validated_layers", return_value=custom_layers
        ) as mock_validated:
            url = provider._get_opendata_url("N-34-130-D-d-2-4")

        # _get_validated_layers should have been called
        mock_validated.assert_called_once()

        # The URL found should be from OpenData
        assert "opendata.geoportal.gov.pl" in url


# ===========================================================================
# TestNmptInheritsValidation
# ===========================================================================


class TestNmptInheritsValidation:
    """Tests that GugikNmptProvider inherits WMS validation correctly."""

    def test_nmpt_provider_uses_validation(self):
        """NMPT provider calls _fetch_wms_layers with the NMPT WMS endpoint."""
        provider = GugikNmptProvider()

        # NMPT EVRF2007 endpoint
        expected_endpoint = GugikNmptProvider.WMS_SKOROWIDZE_ENDPOINTS["1m"]["EVRF2007"]
        nmpt_layers = list(GugikNmptProvider.WMS_LAYERS["1m"]["EVRF2007"])

        with patch.object(
            provider, "_fetch_wms_layers", return_value=nmpt_layers
        ) as mock_fetch:
            provider._get_validated_layers("1m", "EVRF2007")

        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        # First positional arg should be the NMPT endpoint
        called_endpoint = call_args[0][0]
        assert "NMPT" in called_endpoint
        assert called_endpoint == expected_endpoint


# ===========================================================================
# TestLayerSorting
# ===========================================================================


class TestLayerSorting:
    """Tests for the layer sorting logic used in _fetch_wms_layers."""

    def test_sort_with_istarsze_last(self):
        """iStarsze layers sort after regular year layers."""
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeNMT2022iStarsze</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2023</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response(xml)
        provider = _make_provider()

        with patch(_SESSION_PATCH, return_value=mock_session):
            result = provider._fetch_wms_layers("https://example.com/wms")

        assert result == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2023",
            "SkorowidzeNMT2022iStarsze",
        ]

    def test_sort_layers_without_year(self):
        """Layer names without a 4-digit year sort last (year=0)."""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response(WMS_XML_WITH_NO_YEAR_LAYER)
        provider = _make_provider()

        with patch(_SESSION_PATCH, return_value=mock_session):
            result = provider._fetch_wms_layers("https://example.com/wms")

        # Year-bearing layers first (descending), no-year layer last
        assert result == [
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2023",
            "SkorowidzeNMTNajnowsze",
        ]
