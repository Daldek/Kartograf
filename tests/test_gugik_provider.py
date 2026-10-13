"""
Unit tests for the gugik provider module.

This module contains tests for the GugikProvider class with the new architecture:
- download -> OpenData (ASC)
- download_bbox(bbox) -> WCS (GeoTIFF/PNG/JPEG)
"""

import re
import threading
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import rasterio
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.pl.gugik import GugikProvider
from tests.conftest import (
    _STUB_LAYERS,
    WCS_FIXTURES,
    gfi_record,
    make_provider,
    multipart_asc_body,
    recorded_response,
    render_gfi_body,
)

_EVRF2007_LAYERS = _STUB_LAYERS["NMT/WMS/SkorowidzeUkladEVRF2007"]
# The per-thread session factory lives in SkorowidzLayersMixin (skorowidz.py)
SESSION_FACTORY = "kartograf.transport.http.make_gugik_session"


def _wms_response(body: str) -> Mock:
    """Fake HTTP 200 index response (GetFeatureInfo / GetCapabilities)."""
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.text = body
    response.raise_for_status = Mock()
    return response


def _queried_layers(session: Mock, endpoint: str | None = None) -> list[str]:
    """LAYERS= values from successive GetFeatureInfo requests on the session
    (only those sent to ``endpoint`` when given)."""
    return [
        parse_qs(urlparse(call.args[0]).query)["LAYERS"][0]
        for call in session.get.call_args_list
        if endpoint is None or call.args[0].startswith(f"{endpoint}?")
    ]


def _subset(url: str) -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) from the SUBSET parameters of a WCS GetCoverage URL."""
    subsets = parse_qs(urlparse(url).query)["SUBSET"]
    x = next(s for s in subsets if s.startswith("x("))[2:-1].split(",")
    y = next(s for s in subsets if s.startswith("y("))[2:-1].split(",")
    return float(x[0]), float(x[1]), float(y[0]), float(y[1])


def _recorded_subset(path: Path) -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) a recorded ASC response covers (from its ASC header)."""
    head = path.read_bytes()[:600].decode()
    field = {
        key: float(value)
        for key, value in re.findall(
            r"(ncols|nrows|xllcorner|yllcorner|cellsize)\s+(\S+)", head
        )
    }
    x0, y0, step = field["xllcorner"], field["yllcorner"], field["cellsize"]
    return (x0, x0 + field["ncols"] * step, y0, y0 + field["nrows"] * step)


def _encoded(left: float, top: float, width: int, height: int) -> np.ndarray:
    """Pixel value = 1000 * northing index + easting index (1 m grid, absolute)."""
    rows = (550200.5 - top) + np.arange(height)[:, None]
    cols = (left - 449000.5) + np.arange(width)[None, :]
    return (1000 * rows + cols).astype("float32")


def _geotiff_response(url: str) -> Mock:
    """HTTP 200 image/tiff with a 1 m GeoTIFF of the URL's SUBSET."""
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    x0, x1, y0, y1 = _subset(url)
    width, height = round(x1 - x0), round(y1 - y0)
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            width=width,
            height=height,
            count=1,
            dtype="float32",
            crs="EPSG:2180",
            transform=from_origin(x0, y1, 1.0, 1.0),
        ) as dst:
            dst.write(_encoded(x0, y1, width, height), 1)
        body = mem.read()
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.headers = {"Content-Type": "image/tiff"}
    response.iter_content = Mock(return_value=[body])
    return response


class TestGugikProviderBasic:
    """Tests of the basic GugikProvider functionality."""

    def test_provider_name(self):
        """Test the provider name."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
        assert provider.name == "GUGiK"

    def test_provider_base_url(self):
        """Test the base URL."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
        assert provider.base_url == "https://mapy.geoportal.gov.pl"

    def test_supported_formats(self):
        """Test of the supported WCS formats."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
        formats = provider.get_supported_formats()

        assert "GTiff" in formats
        assert "PNG" in formats
        assert "JPEG" in formats
        assert len(formats) == 3  # Only WCS formats

    def test_file_extensions(self):
        """Test of file extensions."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")

        assert provider.get_file_extension("GTiff") == ".tif"
        assert provider.get_file_extension("PNG") == ".png"
        assert provider.get_file_extension("JPEG") == ".jpg"
        assert provider.get_file_extension("ASC") == ".asc"

    def test_file_extension_invalid_format(self):
        """Test of the extension for an invalid format."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")

        with pytest.raises(ValidationError, match="Nieznany format"):
            provider.get_file_extension("InvalidFormat")


class TestGugikProviderResolution:
    """Tests of resolution handling (1m/5m)."""

    def test_resolution_1m_explicit(self):
        """Test of explicitly setting the 1m resolution."""
        provider = GugikProvider(resolution="1m", vertical_crs="EVRF2007")
        assert provider.resolution == "1m"

    def test_resolution_5m(self):
        """Test of setting the 5m resolution (requires EVRF2007)."""
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        assert provider.resolution == "5m"
        assert provider.vertical_crs == "EVRF2007"

    def test_resolution_5m_requires_evrf2007(self):
        """Test that the 5m resolution requires EVRF2007."""
        with pytest.raises(
            ValidationError, match="5m jest dostepna tylko dla EVRF2007"
        ):
            GugikProvider(resolution="5m", vertical_crs="KRON86")

    def test_resolution_invalid(self):
        """Test of an invalid resolution."""
        with pytest.raises(ValidationError, match="Nieobslugiwana rozdzielczosc"):
            GugikProvider(resolution="2m", vertical_crs="EVRF2007")

    def test_supported_resolutions(self):
        """Test of the list of supported resolutions."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
        resolutions = provider.get_supported_resolutions()

        assert "1m" in resolutions
        assert "5m" in resolutions
        assert len(resolutions) == 2

    def test_supported_vertical_crs_for_1m(self):
        """Test of the supported CRS for 1m."""
        provider = GugikProvider(resolution="1m", vertical_crs="EVRF2007")
        crs_list = provider.get_supported_vertical_crs_for_resolution()

        assert "KRON86" in crs_list
        assert "EVRF2007" in crs_list

    def test_supported_vertical_crs_for_5m(self):
        """Test of the supported CRS for 5m."""
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        crs_list = provider.get_supported_vertical_crs_for_resolution()

        assert "EVRF2007" in crs_list
        assert "KRON86" not in crs_list

    def test_is_wcs_available_1m(self):
        """WCS is available for 1m in both vertical CRS."""
        for vertical_crs in ("KRON86", "EVRF2007"):
            provider = GugikProvider(resolution="1m", vertical_crs=vertical_crs)
            assert provider.is_wcs_available() is True

    def test_is_wcs_available_5m(self):
        """Test of WCS unavailability for 5m."""
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        assert provider.is_wcs_available() is False

    def test_download_bbox_not_available_for_5m(self, tmp_path):
        """Test that download_bbox is not available for 5m."""
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        output_path = tmp_path / "test.tif"

        bbox = BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

        with pytest.raises(ValidationError, match="nie jest dostepne dla"):
            provider.download_bbox(bbox, output_path)


class TestGugikProviderValidation:
    """Tests of sheet code validation."""

    def test_validate_valid_sheet(self):
        """Test of validation of a valid sheet code."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")

        assert provider.validate_sheet("N-34-130-D") is True
        assert provider.validate_sheet("N-34-130-D-d-2-4") is True
        assert provider.validate_sheet("M-33-A") is True

    def test_validate_invalid_sheet(self):
        """Test of validation of an invalid sheet code."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")

        assert provider.validate_sheet("INVALID") is False
        assert provider.validate_sheet("") is False
        assert provider.validate_sheet("123") is False


class TestGugikProviderDownloadSheet:
    """Tests of download by sheet code (OpenData)."""

    @pytest.fixture
    def mock_wms_response(self):
        """Mock of a WMS GetFeatureInfo response with the N-34-130-D sheet record."""
        return _wms_response(render_gfi_body([gfi_record("N-34-130-D")]))

    @pytest.fixture
    def mock_opendata_response(self):
        """Mock of an ASC file download response."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.iter_content = Mock(
            return_value=[b"ncols 100\nnrows 100\n", b"data..."]
        )
        return response

    def test_download_sheet_uses_opendata(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test that download uses OpenData."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
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

    def test_download_sheet_creates_directory(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test that download creates the target directory."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "subdir" / "nested" / "test.asc"

        result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert output_path.parent.exists()

    def test_download_sheet_saves_content(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test that download writes the file content."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        provider.download("N-34-130-D", output_path)

        content = output_path.read_bytes()
        assert b"ncols" in content

    def test_download_sheet_with_timeout(
        self, tmp_path, mock_wms_response, mock_opendata_response
    ):
        """Test of download with a specified timeout."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_wms_response, mock_opendata_response])

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        provider.download("N-34-130-D", output_path, timeout=60)

        # Check timeout was passed to requests
        for call in session.get.call_args_list:
            assert call.kwargs["timeout"] == 60

    def test_download_skorowidz_failure_leaves_no_directory(
        self, tmp_path, mock_opendata_response
    ):
        """Index failure (3 x ConnectionError) = DownloadError before mkdir."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset")] * 3
            + [mock_opendata_response]
        )
        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "not-created" / "test.asc"

        with patch("time.sleep"), pytest.raises(DownloadError) as exc_info:
            provider.download("N-34-130-D", output_path)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert not output_path.parent.exists()
        assert session.get.call_count == 3


class TestGugikProviderDownloadBbox:
    """Tests of download by bbox (WCS)."""

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
        """Sample bbox in EPSG:2180 (100 x 100 m: one WCS request)."""
        return BBox(
            min_x=450000, min_y=550000, max_x=450100, max_y=550100, crs="EPSG:2180"
        )

    def test_download_bbox_uses_wcs(self, tmp_path, sample_bbox):
        """KRON86 GeoTIFF heights from the TIFF endpoint."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=lambda url, **kw: _geotiff_response(url))

        provider = GugikProvider(
            session=session, vertical_crs="KRON86", resolution="1m"
        )
        output_path = tmp_path / "test.tif"

        result = provider.download_bbox(sample_bbox, output_path)

        assert result == output_path
        assert output_path.exists()
        query = parse_qs(urlparse(session.get.call_args[0][0]).query)
        assert query["COVERAGEID"] == ["DTM_PL-KRON86-NH_TIFF"]
        assert query["FORMAT"] == ["image/tiff"]
        assert session.get.call_args.kwargs["timeout"] == 30  # GeoTIFF streams early

    def test_download_bbox_png_format(self, tmp_path, mock_wcs_response, sample_bbox):
        """Test of bbox download in the PNG format."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikProvider(
            session=session, vertical_crs="KRON86", resolution="1m"
        )
        output_path = tmp_path / "test.png"

        provider.download_bbox(sample_bbox, output_path, format="PNG")

        call_url = session.get.call_args[0][0]
        assert "image%2Fpng" in call_url or "image/png" in call_url

    def test_download_bbox_invalid_format(self, tmp_path, sample_bbox):
        """Test of the error for an invalid format."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
        output_path = tmp_path / "test.xyz"

        with pytest.raises(ValidationError, match="Nieobslugiwany format WCS"):
            provider.download_bbox(sample_bbox, output_path, format="InvalidFormat")

    def test_download_bbox_wrong_crs(self, tmp_path):
        """Test of the error for an invalid CRS."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
        output_path = tmp_path / "test.tif"

        wrong_crs_bbox = BBox(
            min_x=18.0, min_y=52.0, max_x=19.0, max_y=53.0, crs="EPSG:4326"
        )

        with pytest.raises(ValidationError, match="EPSG:2180"):
            provider.download_bbox(wrong_crs_bbox, output_path)

    def test_odd_size_requested_even_and_cropped(self, tmp_path, sample_bbox):
        """The aligned bbox is 101 x 101 px: the request is widened east and
        south to 102 x 102 (an odd size makes the server resample its middle
        row/column from the neighbouring source pixel) and the file is cropped
        back to the aligned bbox, values 1:1."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=lambda url, **kw: _geotiff_response(url))
        provider = GugikProvider(
            session=session, vertical_crs="KRON86", resolution="1m"
        )
        output_path = tmp_path / "test.tif"

        provider.download_bbox(sample_bbox, output_path)

        assert session.get.call_count == 1
        assert _subset(session.get.call_args[0][0]) == (
            449999.5,
            450101.5,
            549998.5,
            550100.5,
        )
        with rasterio.open(output_path) as src:
            assert src.shape == (101, 101)
            assert (src.bounds.left, src.bounds.top) == (449999.5, 550100.5)
            np.testing.assert_array_equal(
                src.read(1), _encoded(449999.5, 550100.5, 101, 101)
            )
        assert list(tmp_path.glob("*.part*")) == []

    def test_nmt_download_bbox_chunks_large_area(self, tmp_path):
        """Above WCS_CHUNK_LIMITS the area is requested in chunks on the source
        grid and stitched 1:1 (values encode the global pixel position)."""
        from kartograf.transport.chunks import ChunkLimits

        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=lambda url, **kw: _geotiff_response(url))
        provider = GugikProvider(
            session=session, vertical_crs="KRON86", resolution="1m"
        )
        output_path = tmp_path / "big.tif"
        bbox = BBox(450000, 550000, 450150, 550150, "EPSG:2180")

        with patch.object(
            GugikProvider, "WCS_CHUNK_LIMITS", ChunkLimits(100, 100, 10_000)
        ):
            provider.download_bbox(bbox, output_path)

        subsets = [_subset(call.args[0]) for call in session.get.call_args_list]
        assert len(subsets) == 4
        for x0, x1, y0, y1 in subsets:
            for v in (x0, x1, y0, y1):
                assert v % 1 == 0.5
        with rasterio.open(output_path) as src:
            assert src.shape == (151, 151)
            assert (src.bounds.left, src.bounds.top) == (449999.5, 550150.5)
            np.testing.assert_array_equal(
                src.read(1), _encoded(449999.5, 550150.5, 151, 151)
            )
        assert list(tmp_path.glob("*.part*")) == []

    def test_nmt_download_bbox_png_single_request_unaligned(
        self, tmp_path, mock_wcs_response, sample_bbox
    ):
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)
        provider = GugikProvider(
            session=session, vertical_crs="KRON86", resolution="1m"
        )

        provider.download_bbox(sample_bbox, tmp_path / "a.png", format="PNG")

        assert session.get.call_count == 1
        assert _subset(session.get.call_args[0][0]) == (
            450000.0,
            450100.0,
            550000.0,
            550100.0,
        )

    def test_nmt_download_bbox_rejects_exception_report(self, tmp_path, sample_bbox):
        """An OGC ExceptionReport with HTTP 200 is an error, not a .tif file."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.headers = {"Content-Type": "text/xml"}
        response.text = (
            "<ows:ExceptionReport>InvalidParameterValue</ows:ExceptionReport>"
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=response)
        provider = GugikProvider(
            session=session, vertical_crs="KRON86", resolution="1m"
        )
        output_path = tmp_path / "err.tif"

        with pytest.raises(DownloadError, match="ExceptionReport"):
            provider.download_bbox(sample_bbox, output_path)
        assert not output_path.exists()

    def test_evrf2007_download_bbox_aaigrid_on_sheet_grid(self, tmp_path):
        """EVRF2007: image/x-aaigrid from DigitalTerrainModel, bbox expanded to the
        sheet grid, written as float32 GeoTIFF equal to the OpenData sheet."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            return_value=recorded_response(WCS_FIXTURES / "nmt_evrf2007_20x20.mime")
        )
        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )  # EVRF2007 by default
        output_path = tmp_path / "evrf.tif"
        bbox = BBox(567580.6, 243664.7, 567600.4, 243684.3, "EPSG:2180")

        provider.download_bbox(bbox, output_path)

        assert session.get.call_count == 1
        url = session.get.call_args[0][0]
        query = parse_qs(urlparse(url).query)
        assert urlparse(url).path.endswith("/NMT/GRID1/WCS/DigitalTerrainModel")
        assert query["COVERAGEID"] == ["DTM_PL-EVRF2007-NH"]
        assert query["FORMAT"] == ["image/x-aaigrid"]
        assert "SCALEFACTOR" not in query
        assert _subset(url) == (567580.5, 567600.5, 243664.5, 243684.5)
        # ASC: no byte before the whole chunk is computed - a longer read timeout
        assert session.get.call_args.kwargs["timeout"] == 120
        with rasterio.open(output_path) as src:
            assert (src.count, src.dtypes, src.crs.to_epsg()) == (1, ("float32",), 2180)
            assert (src.bounds.left, src.bounds.top) == (567580.5, 243684.5)
            values = src.read(1)
        np.testing.assert_array_equal(
            values, np.load(WCS_FIXTURES / "nmt_evrf2007_20x20_sheet_values.npy")
        )

    def test_aaigrid_chunk_budget_is_one_mpx(self, tmp_path):
        """ASC chunks are cut at 1 Mpx, GeoTIFF at 16 Mpx: a 2000 x 1000 px area
        is two EVRF2007 requests, stitched 1:1, and one KRON86 request."""
        bbox = BBox(449999.5, 549999.5, 451999.5, 550999.5, "EPSG:2180")

        def asc_response(url, **kwargs):
            x0, x1, y0, y1 = _subset(url)
            values = _encoded(x0, y1, round(x1 - x0), round(y1 - y0))
            return recorded_response(
                WCS_FIXTURES / "nmt_evrf2007_20x20.mime",
                body=multipart_asc_body(values, x0, y0),
            )

        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=asc_response)
        GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        ).download_bbox(bbox, tmp_path / "evrf.tif")

        subsets = [_subset(call.args[0]) for call in session.get.call_args_list]
        assert subsets == [
            (449999.5, 450999.5, 549999.5, 550999.5),
            (450999.5, 451999.5, 549999.5, 550999.5),
        ]
        with rasterio.open(tmp_path / "evrf.tif") as src:
            assert src.shape == (1000, 2000)
            np.testing.assert_array_equal(
                src.read(1), _encoded(449999.5, 550999.5, 2000, 1000)
            )
        assert list(tmp_path.glob("*.part*")) == []

        kron = Mock(spec=requests.Session)
        kron.get = Mock(side_effect=lambda url, **kw: _geotiff_response(url))
        GugikProvider(
            session=kron, vertical_crs="KRON86", resolution="1m"
        ).download_bbox(bbox, tmp_path / "kron.tif")
        assert kron.get.call_count == 1

    def test_aaigrid_content_error_is_not_retried(self, tmp_path):
        """An ASC whose corner differs from the request is a DownloadError after
        one request (deterministic server answer), no file left."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            return_value=recorded_response(WCS_FIXTURES / "nmt_evrf2007_20x20.mime")
        )
        output_path = tmp_path / "evrf.tif"
        shifted = BBox(567590.6, 243664.7, 567610.4, 243684.3, "EPSG:2180")

        with pytest.raises(DownloadError, match="xllcorner"):
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ).download_bbox(shifted, output_path)

        assert session.get.call_count == 1
        assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("provider_cls", "vertical_crs", "base", "budget"),
    [
        ("nmt", "EVRF2007", "nmt_evrf2007_20x20", 100),
        # the ASC budget counts coverage pixels: 4 per NMPT 1 m pixel
        ("nmpt", "EVRF2007", "nmpt_evrf2007_20x20_sf05", 400),
    ],
)
def test_aaigrid_chunks_stitch_bit_exact_recorded(
    tmp_path, provider_cls, vertical_crs, base, budget
):
    """Four recorded 10 x 10 chunks stitch into the recorded 20 x 20 response
    (NMPT with SCALEFACTOR=0.5 too) - and both equal the OpenData sheet."""
    from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
    from kartograf.transport.chunks import ChunkLimits

    by_subset = {
        _recorded_subset(path): path for path in WCS_FIXTURES.glob(f"{base}*.mime")
    }
    session = Mock(spec=requests.Session)
    session.get = Mock(
        side_effect=lambda url, **kw: recorded_response(by_subset[_subset(url)])
    )
    cls = GugikProvider if provider_cls == "nmt" else GugikNmptProvider
    provider = make_provider(cls, session=session, vertical_crs=vertical_crs)
    bbox = BBox(567580.5, 243664.5, 567600.5, 243684.5, "EPSG:2180")

    provider.download_bbox(bbox, tmp_path / "whole.tif")
    with patch.object(cls, "WCS_CHUNK_LIMITS_AAIGRID", ChunkLimits(10, 10, budget)):
        provider.download_bbox(bbox, tmp_path / "chunked.tif")

    assert session.get.call_count == 5
    with rasterio.open(tmp_path / "whole.tif") as whole:
        expected = whole.read(1)
    with rasterio.open(tmp_path / "chunked.tif") as chunked:
        assert chunked.bounds == whole.bounds
        np.testing.assert_array_equal(chunked.read(1), expected)
    np.testing.assert_array_equal(
        expected, np.load(WCS_FIXTURES / f"{base}_sheet_values.npy")
    )


class TestGugikProviderRetry:
    """Tests of retry and error handling."""

    def test_download_retry_on_failure(self, tmp_path):
        """Test of retrying after an error."""
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

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        with patch("time.sleep"):
            result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert session.get.call_count == 3

    def test_download_retry_exhausted(self, tmp_path):
        """Test of the error after retries are exhausted."""
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

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        with patch("time.sleep"), pytest.raises(DownloadError):
            provider.download("N-34-130-D", output_path)

    def test_download_exponential_backoff(self, tmp_path):
        """Test of exponential backoff between tries."""
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

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        sleep_times = []
        with (
            patch("time.sleep", side_effect=lambda t: sleep_times.append(t)),
            pytest.raises(DownloadError),
        ):
            provider.download("N-34-130-D", output_path)

        # Exponential backoff: 2^1=2, 2^2=4 seconds
        assert sleep_times == [2, 4]


# OGC exception report in the MapServer shape (WMS 1.3.0) that answers with it
# on HTTP 200. GUGiK really returned the text "Invalid layer(s) given in the
# LAYERS parameter" on GetFeatureInfo for an outdated layer (CHANGELOG 0.7.0,
# WMS layer names); nobody recorded the HTTP status and Content-Type of the real
# response (live checklist).
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


# Minimal GetCapabilities with an index (skorowidz) layer, an aggregate layer
# and a layer of another product (ZasiegiNMT - rejected by LAYER_PATTERN).
_CAPABILITIES_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">'
    "<Capability><Layer><Name>ZasiegiNMT2025</Name>"
    "<Layer><Name>SkorowidzeNMT2023iStarsze</Name></Layer>"
    "<Layer><Name>SkorowidzeNMT2024</Name></Layer>"
    "</Layer></Capability></WMS_Capabilities>"
)


class TestGugikProviderGetOpendataUrl:
    """Tests of _get_opendata_url (layers from the conftest autouse stub)."""

    SHEET = "N-34-130-D-d-2-4"
    URL = f"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/78955/78955_1_{SHEET}.asc"

    @pytest.fixture
    def record_response(self):
        """Response with a single 1 m PL-1992 record for SHEET."""
        return _wms_response(render_gfi_body([gfi_record(self.SHEET)]))

    @pytest.fixture
    def empty_response(self):
        """Empty index template (sea, abroad)."""
        return _wms_response(render_gfi_body([]))

    def test_get_opendata_url_success(self, record_response):
        """Record in the newest layer: its URL, the loop ends after 1 query."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=record_response)

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == self.URL
        assert _queried_layers(session) == [_EVRF2007_LAYERS[0]]

    def test_get_opendata_url_not_found(self, empty_response):
        """Empty response from EVERY layer = NoCoverageError describing the request."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=empty_response)

        with pytest.raises(NoCoverageError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert f"Brak danych NMT 1m dla {self.SHEET} (uklad PL-1992, EVRF2007)" in str(
            exc_info.value
        )
        # its own index, all layers; the variant check (P10) asks other indexes
        own = GugikProvider.WMS_INDEX_ENDPOINTS["1m"]["EVRF2007"]
        assert _queried_layers(session, own) == list(_EVRF2007_LAYERS)

    def test_transport_error_retries_same_layer(self, record_response):
        """A dropped connection retries THE SAME layer after backoff."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset"), record_response]
        )

        with patch("time.sleep") as sleep:
            url = GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert url == self.URL
        assert _queried_layers(session) == [_EVRF2007_LAYERS[0]] * 2
        assert sleep.call_count == 1

    def test_transport_error_exhausted_is_service_failure(self, record_response):
        """3 x failure of the newest layer = DownloadError; older layers are not
        queried (a record from the 2nd layer never replaces an unknown newer
        campaign)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset")] * 3 + [record_response] * 3
        )

        with patch("time.sleep") as sleep, pytest.raises(DownloadError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert not isinstance(exc_info.value, NoCoverageError)
        message = str(exc_info.value)
        assert self.SHEET in message and _EVRF2007_LAYERS[0] in message
        assert _queried_layers(session) == [_EVRF2007_LAYERS[0]] * 3
        assert sleep.call_count == 2

    def test_ogc_exception_report_is_service_failure(self):
        """An OGC exception report on HTTP 200 = DownloadError after 1 query, without
        retries and not mistaken for a missing sheet."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(_OGC_EXCEPTION_REPORT))

        with patch("time.sleep") as sleep, pytest.raises(DownloadError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert "Invalid layer(s)" in str(exc_info.value)
        assert session.get.call_count == 1
        sleep.assert_not_called()

    def test_html_without_template_is_service_failure(self):
        """HTML 200 without an index template (e.g. a gateway page) = DownloadError."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            return_value=_wms_response("<html><body>502 Bad Gateway</body></html>")
        )

        with pytest.raises(DownloadError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert session.get.call_count == 1

    def test_get_opendata_url_tries_all_layers(self, empty_response, record_response):
        """Empty layers are queried in turn from the newest until a record."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[empty_response] * 3 + [record_response])

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == self.URL
        assert _queried_layers(session) == list(_EVRF2007_LAYERS)

    @pytest.mark.parametrize("newest_first", [True, False])
    def test_latest_campaign_wins_within_layer(self, newest_first):
        """Within a layer the newest acquisition date wins, not the HTML order."""
        records = [
            gfi_record(self.SHEET, aktualnosc="2024-09-03", url="https://x/new.asc"),
            gfi_record(self.SHEET, aktualnosc="2019-04-18", url="https://x/old.asc"),
        ]
        if not newest_first:
            records.reverse()
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(render_gfi_body(records)))

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == "https://x/new.asc"

    def test_dt_pzgik_breaks_aktualnosc_tie(self):
        """An acquisition date tie is broken by the later dt_pzgik."""
        records = [
            gfi_record(self.SHEET, dt_pzgik="2024-11-02", url="https://x/earlier.asc"),
            gfi_record(self.SHEET, dt_pzgik="2025-01-10", url="https://x/later.asc"),
        ]
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(render_gfi_body(records)))

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == "https://x/later.asc"

    def test_other_resolution_only_is_no_coverage_with_hint(self):
        """The only 0.50 m record: there is no 1 m, but the hint says what exists."""
        body = render_gfi_body([gfi_record(self.SHEET, resolution="0.50 m")])
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(body))

        with pytest.raises(NoCoverageError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert "0.5 m" in str(exc_info.value)

    def test_negative_cache_preserves_resolution_hint(self, tmp_path):
        from kartograf.cache.metadata import MetadataCache

        body = render_gfi_body([gfi_record(self.SHEET, resolution="0.50 m")])
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(body))
        cache = MetadataCache(db_path=tmp_path / "cache.db")
        try:
            provider = GugikProvider(
                session=session, cache=cache, vertical_crs="EVRF2007", resolution="1m"
            )
            with pytest.raises(NoCoverageError) as first:
                provider._get_opendata_url(self.SHEET)
            calls = session.get.call_count
            with pytest.raises(NoCoverageError) as cached:
                provider._get_opendata_url(self.SHEET)
            assert session.get.call_count == calls
            assert str(cached.value) == str(first.value)
            assert "0.5 m" in str(cached.value)
        finally:
            cache.close()

    def test_rejected_record_does_not_stop_layer_loop(self, record_response):
        """A layer with only 0.50 m does not end the loop - 1 m from the next layer."""
        first = _wms_response(
            render_gfi_body([gfi_record(self.SHEET, resolution="0.50 m")])
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[first, record_response])

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == self.URL
        assert _queried_layers(session) == list(_EVRF2007_LAYERS[:2])

    def test_get_opendata_url_uses_correct_endpoint_for_1m(self, record_response):
        """Test that 1m uses the right endpoint (default EVRF2007)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=record_response)

        provider = GugikProvider(
            session=session, resolution="1m", vertical_crs="EVRF2007"
        )
        provider._get_opendata_url(self.SHEET)

        call_url = session.get.call_args[0][0]
        assert "SkorowidzeUkladEVRF2007" in call_url

    def test_get_opendata_url_uses_correct_endpoint_for_5m(self):
        """Test that 5m uses the right endpoint."""
        body = render_gfi_body([gfi_record(self.SHEET, resolution="5.00 m")])
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(body))

        provider = GugikProvider(
            session=session, resolution="5m", vertical_crs="EVRF2007"
        )
        assert provider._get_opendata_url(self.SHEET) == self.URL

        call_url = session.get.call_args[0][0]
        assert "SheetsGrid5mEVRF2007" in call_url


class TestGugikProviderSession:
    """Tests of HTTP session management: one injected or one per thread."""

    SHEET = "N-34-130-D"

    @pytest.fixture
    def record_body(self):
        return render_gfi_body([gfi_record(self.SHEET)])

    @staticmethod
    def file_response():
        response = Mock()
        response.iter_content = Mock(return_value=[b"data"])
        return response

    def test_uses_provided_session(self, tmp_path, record_body):
        """The injected session serves the index and the file; no other is created."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[_wms_response(record_body), self.file_response()]
        )

        with patch(SESSION_FACTORY) as factory:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ).download(self.SHEET, tmp_path / "test.asc")

        factory.assert_not_called()
        assert session.get.call_count == 2

    def test_one_session_per_thread(self, record_body):
        """Two requests in one thread share one session from make_gugik_session."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=_wms_response(record_body))

        with patch(SESSION_FACTORY, return_value=session) as factory:
            provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
            provider._get_opendata_url(self.SHEET)
            provider._get_opendata_url(self.SHEET)

        factory.assert_called_once()
        assert session.get.call_count == 2

    def test_separate_session_per_thread(self, record_body) -> None:
        """Each thread gets its own session and uses only that one."""
        sessions: list[Mock] = []
        results: list[str] = []
        errors: list[Exception] = []

        def new_session():
            session = Mock(spec=requests.Session)
            session.get = Mock(return_value=_wms_response(record_body))
            sessions.append(session)
            return session

        with patch(SESSION_FACTORY, side_effect=new_session) as factory:
            provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")

            def worker():
                try:
                    results.append(provider._get_opendata_url(self.SHEET))
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
        assert results == [gfi_record(self.SHEET)["url"]] * 2

    @pytest.mark.real_wms_layers
    def test_provided_session_serves_get_capabilities(self, tmp_path, record_body):
        """Without the layer stub: the injected session does GetCapabilities, then
        GetFeatureInfo on a layer from capabilities, then the file stream."""
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
            result = GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ).download(self.SHEET, output_path)

        factory.assert_not_called()
        assert result == output_path and output_path.read_bytes() == b"data"
        calls = session.get.call_args_list
        assert "REQUEST=GetCapabilities" in calls[0].args[0]
        assert "REQUEST=GetFeatureInfo" in calls[1].args[0]
        assert "LAYERS=SkorowidzeNMT2024" in calls[1].args[0]
        assert calls[2].kwargs["stream"] is True


class TestGugikProviderRepr:
    """Tests of the string representation."""

    def test_repr(self):
        """Test __repr__."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
        repr_str = repr(provider)

        assert "GugikProvider" in repr_str
        assert "mapy.geoportal.gov.pl" in repr_str

    def test_str(self):
        """Test __str__."""
        provider = GugikProvider(vertical_crs="EVRF2007", resolution="1m")
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
        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
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
        ("sheet", "fixture", "expected"),
        [
            ("N-33-90-C-c-2-4", "szczecin_c24_2024.body", "80225_1536688"),
            ("N-34-139-A-c-1-1", "warszawa_2023iStarsze.body", "78047_1404533"),
        ],
    )
    def test_exact_resolution_and_latest_campaign(self, sheet, fixture, expected):
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(self.sample(fixture))
        assert expected in GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(sheet)

    @pytest.mark.parametrize(
        ("sheet", "record_sheet", "system", "hint"),
        [
            ("5.167.25", "5.167.25.13", "PL-2000:S5", "--scale 1:2000"),
            ("7.124.7.4", "N-33-48-C-a-3-4", "PL-1992", "PL-1992"),
        ],
    )
    def test_no_substring_or_other_system_fallback(
        self, sheet, record_sheet, system, hint
    ):
        body = render_gfi_body(
            [
                {
                    "url": f"https://opendata.geoportal.gov.pl/{record_sheet}.asc",
                    "godlo": record_sheet,
                    "ukladWspolrzednychPoziomych": system,
                    "charakterystykaPrzestrzenna": "1.00 m",
                    "aktualnosc": "2024-09-03",
                }
            ]
        )
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(body)
        with pytest.raises(NoCoverageError, match=hint):
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(sheet)

    def test_uppercase_asc_is_available(self):
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(
            self.sample("slubice_c32_2022iStarsze.html")
        )
        url = GugikProvider(
            session=session, resolution="5m", vertical_crs="EVRF2007"
        )._get_opendata_url("N-33-126-C-c-3-2")
        assert url.endswith("76969_1298029_N-33-126-C-c-3-2.ASC")

    def test_no_coverage_leaves_no_directory(self, tmp_path):
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(self.sample("empty.body"))
        output = tmp_path / "not-created" / "sheet.asc"
        with pytest.raises(NoCoverageError):
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ).download("N-33-90-C-c-2-4", output)
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
        provider = GugikProvider(
            session=session, cache=cache, vertical_crs="EVRF2007", resolution="1m"
        )
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
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url("N-33-90-C-c-2-4")

    def test_5m_accepts_5m_record(self):
        record = gfi_record("N-33-90-C-c-2-4", resolution="5.00 m")
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(render_gfi_body([record]))
        provider = GugikProvider(
            session=session, resolution="5m", vertical_crs="EVRF2007"
        )
        assert provider._get_opendata_url("N-33-90-C-c-2-4") == record["url"]

    def test_pl2000_record_matches_only_same_zone(self):
        record = gfi_record("7.173.21.06", system="PL-2000:S7")
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(render_gfi_body([record]))
        assert (
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url("7.173.21.06")
            == (record["url"])
        )

        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(
            render_gfi_body([gfi_record("7.173.21.06", system="PL-2000:S6")])
        )
        with pytest.raises(NoCoverageError, match="PL-2000"):
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url("7.173.21.06")
