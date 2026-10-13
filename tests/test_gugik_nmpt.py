"""
Unit tests for the GugikNmptProvider module.

This module contains tests for the GugikNmptProvider class, which inherits
from GugikProvider and provides Digital Surface Model (NMPT) downloads from
GUGiK - DSM data containing terrain + surface objects.

Endpoints and coverage IDs differ from NMT (DTM), but the download mechanism
(WMS index -> OpenData ASC, WCS -> GeoTIFF) is identical.
"""

from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import rasterio
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from tests.conftest import (
    WCS_FIXTURES,
    gfi_record,
    recorded_response,
    render_gfi_body,
)

NMPT_OPENDATA_URL = "https://opendata.geoportal.gov.pl/NumDaneWys/NMPT/78955/78955_1467030_N-34-130-D.asc"


def _layer_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["LAYERS"][0]


# =========================================================================
# TestGugikNmptProviderInit
# =========================================================================


class TestGugikNmptProviderInit:
    """Tests of GugikNmptProvider initialization."""

    def test_resolution_is_1m(self):
        """Test that the resolution is always 1m - NMPT has no 5m."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        assert provider.resolution == "1m"

    def test_custom_vertical_crs_kron86(self):
        """Test creating the provider with KRON86."""
        provider = GugikNmptProvider(vertical_crs="KRON86")
        assert provider.vertical_crs == "KRON86"

    def test_invalid_vertical_crs(self):
        """Test that an invalid vertical CRS raises ValidationError."""
        with pytest.raises(ValidationError, match="Nieobslugiwany uklad wysokosci"):
            GugikNmptProvider(vertical_crs="INVALID")


# =========================================================================
# TestGugikNmptProviderProperties
# =========================================================================


class TestGugikNmptProviderProperties:
    """Tests of the GugikNmptProvider properties."""

    def test_name(self):
        """Test that name returns 'GUGiK NMPT'."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        assert provider.name == "GUGiK NMPT"

    def test_base_url(self):
        """Test that base_url returns the geoportal URL."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        assert provider.base_url == "https://mapy.geoportal.gov.pl"

    def test_default_extension(self):
        """Test that the default extension is .asc."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        assert provider.default_extension == ".asc"

    def test_repr(self):
        """Test that repr contains 'GugikNmptProvider'."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        repr_str = repr(provider)
        assert "GugikNmptProvider" in repr_str
        assert "mapy.geoportal.gov.pl" in repr_str

    def test_str(self):
        """Test that str contains 'GUGiK NMPT'."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        str_repr = str(provider)
        assert "GUGiK NMPT" in str_repr
        assert "mapy.geoportal.gov.pl" in str_repr


# =========================================================================
# TestGugikNmptProviderEndpoints
# =========================================================================


class TestGugikNmptProviderEndpoints:
    """Tests of NMPT endpoints and layer configuration."""

    def test_wcs_endpoints_are_nmpt(self):
        """Test that the WCS endpoints contain 'NMPT' (not 'NMT')."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        for crs, url in provider.WCS_ENDPOINTS.items():
            assert "NMPT" in url, f"WCS endpoint for {crs} should contain 'NMPT'"
            assert "NMT/" not in url, (
                f"WCS endpoint for {crs} should not contain 'NMT/'"
            )

    def test_wms_endpoints_are_nmpt(self):
        """Test that the WMS index endpoints contain 'NMPT'."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        for resolution, crs_endpoints in provider.WMS_INDEX_ENDPOINTS.items():
            for crs, url in crs_endpoints.items():
                assert "NMPT" in url, (
                    f"WMS endpoint for {resolution}/{crs} should contain 'NMPT'"
                )

    def test_coverage_ids_are_dsm(self):
        """Test that the coverage IDs are DSM_PL-* (not DTM)."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        for crs, coverage_id in provider.COVERAGE_IDS.items():
            assert coverage_id.startswith("DSM_PL-"), (
                f"Coverage ID for {crs} should start with "
                f"'DSM_PL-', got '{coverage_id}'"
            )
            assert "DTM" not in coverage_id, (
                f"Coverage ID for {crs} should not contain 'DTM'"
            )

    def test_wcs_available_for_both_vertical_crs(self):
        """WCS heights are available for both vertical CRS (own endpoint)."""
        assert GugikNmptProvider(vertical_crs="EVRF2007").is_wcs_available() is True
        assert GugikNmptProvider(vertical_crs="KRON86").is_wcs_available() is True


# =========================================================================
# TestGugikNmptProviderDownload
# =========================================================================


class TestGugikNmptProviderDownload:
    """Tests of NMPT data download."""

    @pytest.fixture
    def mock_wms_response(self):
        """Mock WMS GetFeatureInfo response with an NMPT OpenData URL."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = render_gfi_body(
            [gfi_record("N-34-130-D", url=NMPT_OPENDATA_URL)]
        )
        return response

    @pytest.fixture
    def mock_opendata_response(self):
        """Mock response for downloading an ASC file from OpenData."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.iter_content = Mock(
            return_value=[b"ncols 100\nnrows 100\n", b"data..."]
        )
        return response

    @pytest.fixture
    def mock_wcs_response(self):
        """Mock WCS response."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.headers = {"Content-Type": "image/tiff"}
        response.iter_content = Mock(return_value=[b"TIFF data..."])
        return response

    @pytest.fixture
    def sample_bbox(self):
        """Sample bbox in EPSG:2180."""
        return BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

    def test_download_uses_opendata(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test that download uses WMS + OpenData (like GugikProvider)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikNmptProvider(session=session, vertical_crs="EVRF2007")
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

    @pytest.mark.parametrize(
        ("vertical_crs", "base", "bbox"),
        [
            (
                "EVRF2007",
                "nmpt_evrf2007_20x20_sf05",
                BBox(567580.6, 243664.7, 567600.4, 243684.3, "EPSG:2180"),
            ),
            (
                "KRON86",
                "nmpt_kron86_20x20_sf05",
                BBox(479013.9, 451886.5, 479033.2, 451906.1, "EPSG:2180"),
            ),
        ],
    )
    def test_nmpt_download_bbox_on_sheet_grid_with_scalefactor(
        self, tmp_path, vertical_crs, base, bbox
    ):
        """NMPT heights: image/x-aaigrid with SCALEFACTOR=0.5 (0.5 m coverage,
        1 m result) on the 1 m sheet grid - one float32 band equal to the sheet
        (before 0.7.2: a 3-band uint8 RGB GeoTIFF)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            return_value=recorded_response(WCS_FIXTURES / f"{base}.mime")
        )
        output_path = tmp_path / "nmpt.tif"

        GugikNmptProvider(session=session, vertical_crs=vertical_crs).download_bbox(
            bbox, output_path
        )

        assert session.get.call_count == 1
        url = session.get.call_args[0][0]
        query = parse_qs(urlparse(url).query)
        assert urlparse(url).path.endswith("/NMPT/GRID1/WCS/DigitalSurfaceModel")
        assert query["COVERAGEID"] == [f"DSM_PL-{vertical_crs}-NH"]
        assert query["FORMAT"] == ["image/x-aaigrid"]
        assert query["SCALEFACTOR"] == ["0.5"]
        for subset in query["SUBSET"]:
            low, high = subset[2:-1].split(",")
            assert float(low) % 1 == 0.5 and float(high) % 1 == 0.5
        with rasterio.open(output_path) as src:
            assert (src.count, src.dtypes, src.shape) == (1, ("float32",), (20, 20))
            assert src.res == (1.0, 1.0)
            values = src.read(1)
        np.testing.assert_array_equal(
            values, np.load(WCS_FIXTURES / f"{base}_sheet_values.npy")
        )

    def test_nmpt_chunk_budget_counts_coverage_pixels(self):
        """NMPT 1 m reads 4 coverage pixels (0.5 m) per result pixel, so its
        4 Mpx coverage budget cuts a 2000 x 1000 m area into chunks of at most
        1 Mpx of result; NMT EVRF2007 (1 m coverage, 1 Mpx budget) gets the same."""
        bbox = BBox(567099.5, 243999.5, 569099.5, 244999.5, "EPSG:2180")

        nmpt = GugikNmptProvider(vertical_crs="EVRF2007").plan_wcs_chunks(bbox)
        nmt = GugikProvider(vertical_crs="EVRF2007", resolution="1m").plan_wcs_chunks(
            bbox
        )

        assert len(nmpt) == 2 and max(c.width * c.height for c in nmpt) <= 1_000_000
        assert [(c.width, c.height) for c in nmt] == [(c.width, c.height) for c in nmpt]

    def test_download_bbox_rejects_exception_report(self, tmp_path, sample_bbox):
        """The single NMPT request is validated too: an OGC ExceptionReport with
        HTTP 200 is a DownloadError, never a .tif file."""
        from kartograf.exceptions import DownloadError

        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.headers = {"Content-Type": "text/xml"}
        response.text = (
            "<ows:ExceptionReport>InvalidParameterValue</ows:ExceptionReport>"
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=response)
        output_path = tmp_path / "err.tif"

        with pytest.raises(DownloadError, match="ExceptionReport"):
            GugikNmptProvider(session=session, vertical_crs="EVRF2007").download_bbox(
                sample_bbox, output_path
            )
        assert not output_path.exists()

    def test_get_opendata_url_uses_nmpt_endpoint(self, mock_wms_response):
        """Test that _get_opendata_url queries the NMPT endpoint (not NMT)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wms_response)

        provider = GugikNmptProvider(session=session, vertical_crs="EVRF2007")
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
    """Tests of GugikNmptProvider inheritance."""

    def test_is_instance_of_base_provider(self):
        """Test that GugikNmptProvider is an instance of BaseProvider."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        assert isinstance(provider, BaseProvider)

    def test_is_instance_of_gugik_provider(self):
        """Test that GugikNmptProvider is an instance of GugikProvider."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        assert isinstance(provider, GugikProvider)

    def test_inherits_retry_logic(self):
        """Test that MAX_RETRIES is inherited and equals 3."""
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        assert provider.MAX_RETRIES == 3
