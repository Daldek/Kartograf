"""
Unit tests for the gugik provider module.

GugikProvider serves one NMT variant of the registry (resolution, height
system, file format):
- download(sheet) -> the newest record of the variant in the WFS sheet index
  (ONE GetFeature with every yearly type of the variant's service, in a 20 m
  square around the sheet centre) -> the file from OpenData;
- download_bbox(bbox) -> WCS (1 m grid only; GeoTIFF/PNG/JPEG).
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

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.sources.variants import resolution_label, variants
from tests.conftest import (
    WCS_FIXTURES,
    make_provider,
    multipart_asc_body,
    recorded_response,
    render_wfs_body,
    wfs_endpoint,
    wfs_fixture,
    wfs_record,
    wfs_requests,
    wfs_response,
    wfs_types,
)

# WFS sheet index services of NMT (one per height system)
_EVRF2007 = wfs_endpoint("nmt_evrf2007")
_KRON86 = wfs_endpoint("nmt_kron86")
# A valid empty answer (sea, abroad): no record, not a failure
_EMPTY = render_wfs_body([])
# SessionPerThread (transport/http.py) calls the factory once per thread
SESSION_FACTORY = "kartograf.transport.http.make_gugik_session"


def _index_session(**answers: str) -> Mock:
    """Session answering WFS requests per service tag (``nmt_kron86=<body>``);
    a service not named answers a valid empty collection."""
    bodies = {wfs_endpoint(tag): body for tag, body in answers.items()}

    def get(url: str, **kwargs: object) -> Mock:
        return wfs_response(bodies.get(url.split("?", 1)[0], _EMPTY))

    session = Mock(spec=requests.Session)
    session.get = Mock(side_effect=get)
    return session


def _grid_labels(vertical_crs: str) -> str:
    """Labels of the NMT grids of the registry in one height system, ascending."""
    values = sorted(
        v.resolution_m
        for v in variants(
            product="nmt", country="PL", vertical_crs=vertical_crs, format="ASC"
        )
        if v.resolution_m is not None
    )
    return ", ".join(resolution_label(value) for value in values)


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

        with pytest.raises(ValidationError, match="Unknown format"):
            provider.get_file_extension("InvalidFormat")


class TestGugikProviderResolution:
    """Tests of the variant choice (resolution, height system, format): the
    registry decides."""

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
        """NMT 5m exists only in EVRF2007: KRON86 is rejected, naming the
        labels the registry has in KRON86."""
        with pytest.raises(ValidationError) as exc_info:
            GugikProvider(resolution="5m", vertical_crs="KRON86")

        message = str(exc_info.value)
        assert "5m (PL) is only available in EVRF2007" in message
        assert f"available in KRON86: {_grid_labels('KRON86')}" in message

    def test_every_registry_variant_is_accepted(self):
        """Every NMT variant of the registry (grids of every resolution,
        archives) builds a provider serving exactly that variant."""
        for variant in variants(product="nmt", country="PL"):
            provider = GugikProvider(
                resolution=variant.label,
                vertical_crs=variant.vertical_crs,
                format=variant.format,
            )
            assert provider.variant == variant
            assert provider.resolution == variant.label

    @pytest.mark.parametrize("label", ["2m", "0.50m", "50cm"])
    def test_unknown_label_lists_registry_labels(self, label):
        """A label outside the registry (also another spelling of a registry
        label) is rejected, listing the NMT grid labels of each height system."""
        with pytest.raises(ValidationError) as exc_info:
            GugikProvider(resolution=label, vertical_crs="EVRF2007")

        message = str(exc_info.value)
        assert label in message
        for vertical_crs in ("EVRF2007", "KRON86"):
            assert f"{vertical_crs}: {_grid_labels(vertical_crs)}" in message

    def test_is_wcs_available_1m(self):
        """WCS is available for 1m in both vertical CRS."""
        for vertical_crs in ("KRON86", "EVRF2007"):
            provider = GugikProvider(resolution="1m", vertical_crs=vertical_crs)
            assert provider.is_wcs_available() is True

    def test_is_wcs_available_only_for_1m_grid(self):
        """No WCS for any other NMT variant of the registry (other grid
        resolutions, archives)."""
        for variant in variants(product="nmt", country="PL"):
            provider = GugikProvider(
                resolution=variant.label,
                vertical_crs=variant.vertical_crs,
                format=variant.format,
            )
            grid_1m = variant.format == "ASC" and variant.label == "1m"
            assert provider.is_wcs_available() is grid_1m, variant

    @pytest.mark.parametrize(
        ("resolution", "vertical_crs", "file_format"),
        [("5m", "EVRF2007", "ASC"), ("0.5m", "KRON86", "ASC"), ("1m", "KRON86", "XYZ")],
    )
    def test_download_bbox_only_for_1m_grid(
        self, tmp_path, resolution, vertical_crs, file_format
    ):
        """download_bbox of a variant without WCS = ValidationError before any
        request."""
        session = Mock(spec=requests.Session)
        provider = GugikProvider(
            session=session,
            resolution=resolution,
            vertical_crs=vertical_crs,
            format=file_format,
        )
        bbox = BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

        with pytest.raises(ValidationError, match="available only for the NMT 1m grid"):
            provider.download_bbox(bbox, tmp_path / "test.tif")

        session.get.assert_not_called()


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
    """Tests of download by sheet code (WFS index -> OpenData)."""

    @pytest.fixture
    def mock_index_response(self):
        """WFS GetFeature answer with the N-34-130-D sheet record."""
        return wfs_response(render_wfs_body([wfs_record("N-34-130-D")]))

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
        self, tmp_path, mock_index_response, mock_opendata_response
    ):
        """The record comes from the variant's WFS index, the file from its URL."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_index_response, mock_opendata_response])

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert output_path.exists()

        # First call: GetFeature of the NMT EVRF2007 WFS index
        assert session.get.call_args_list[0][0][0].startswith(f"{_EVRF2007}?")
        assert len(wfs_requests(session)) == 1

        # Second call: the record's OpenData URL
        second_call_url = session.get.call_args_list[1][0][0]
        assert second_call_url == wfs_record("N-34-130-D")["url_do_pobrania"]

    def test_download_sheet_creates_directory(
        self, tmp_path, mock_index_response, mock_opendata_response
    ):
        """Test that download creates the target directory."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_index_response, mock_opendata_response])

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "subdir" / "nested" / "test.asc"

        result = provider.download("N-34-130-D", output_path)

        assert result == output_path
        assert output_path.parent.exists()

    def test_download_sheet_saves_content(
        self, tmp_path, mock_index_response, mock_opendata_response
    ):
        """Test that download writes the file content."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[mock_index_response, mock_opendata_response])

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        provider.download("N-34-130-D", output_path)

        content = output_path.read_bytes()
        assert b"ncols" in content

    @pytest.mark.real_wfs_types
    def test_download_sheet_with_timeout(
        self, tmp_path, mock_index_response, mock_opendata_response
    ):
        """The timeout given to download reaches every request: GetCapabilities
        of the index service, GetFeature and the file."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                wfs_response(wfs_fixture("caps_nmt_evrf2007.xml")),
                mock_index_response,
                mock_opendata_response,
            ]
        )

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        provider.download("N-34-130-D", output_path, timeout=60)

        timeouts = [call.kwargs["timeout"] for call in session.get.call_args_list]
        assert timeouts == [60, 60, 60]

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

        with pytest.raises(ValidationError, match="Unsupported WCS format"):
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

    @staticmethod
    def index_response() -> Mock:
        """WFS answer with one N-34-130-D record (file URL test.asc)."""
        record = wfs_record(
            "N-34-130-D", url="https://opendata.geoportal.gov.pl/test.asc"
        )
        return wfs_response(render_wfs_body([record]))

    def test_download_retry_on_failure(self, tmp_path):
        """Test of retrying after an error."""
        session = Mock(spec=requests.Session)

        # First OpenData request fails, second succeeds
        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        success_response = Mock()
        success_response.iter_content = Mock(return_value=[b"data"])

        session.get = Mock(
            side_effect=[self.index_response(), fail_response, success_response]
        )

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

        # All OpenData requests fail
        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        session.get = Mock(side_effect=[self.index_response()] + [fail_response] * 3)

        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )
        output_path = tmp_path / "test.asc"

        with patch("time.sleep"), pytest.raises(DownloadError):
            provider.download("N-34-130-D", output_path)

    def test_download_exponential_backoff(self, tmp_path):
        """Test of exponential backoff between tries."""
        session = Mock(spec=requests.Session)

        fail_response = Mock()
        fail_response.raise_for_status.side_effect = requests.RequestException("Error")

        session.get = Mock(side_effect=[self.index_response()] + [fail_response] * 3)

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


class TestGugikProviderGetOpendataUrl:
    """Tests of _get_opendata_url (feature types from the conftest stub)."""

    SHEET = "N-34-130-D-d-2-4"
    URL = f"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/78955/78955_1_{SHEET}.asc"

    @pytest.fixture
    def record_response(self):
        """Answer with a single 1 m PL-1992 record for SHEET."""
        return wfs_response(render_wfs_body([wfs_record(self.SHEET)]))

    @pytest.fixture
    def empty_response(self):
        """Valid empty answer (sea, abroad)."""
        return wfs_response(_EMPTY)

    def test_get_opendata_url_success(self, record_response):
        """The URL of the record, from one query."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=record_response)

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == self.URL
        assert session.get.call_count == 1

    def test_one_get_feature_asks_every_yearly_type(self):
        """A record of the oldest yearly type comes from the same single query:
        ONE GetFeature with every type of the service, newest first, in a 20 m
        square around the sheet centre (URN axis order: N, E)."""
        record = wfs_record(self.SHEET, akt_data="2018-05-14")
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=wfs_response(render_wfs_body([record])))

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == self.URL
        assert session.get.call_count == 1
        (query,) = wfs_requests(session, _EVRF2007)
        assert query["TYPENAMES"] == ",".join(wfs_types("nmt_evrf2007"))
        frame = SheetParser(self.SHEET).get_bbox(crs="EPSG:2180")
        north = (frame.min_y + frame.max_y) / 2
        east = (frame.min_x + frame.max_x) / 2
        *corners, crs = query["BBOX"].split(",")
        assert [float(value) for value in corners] == pytest.approx(
            [north - 10, east - 10, north + 10, east + 10]
        )
        assert crs == "urn:ogc:def:crs:EPSG::2180"

    def test_get_opendata_url_not_found(self, empty_response):
        """A valid empty answer = NoCoverageError describing the request; the
        variant's service is asked once, the other height system once (P10)."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=empty_response)

        with pytest.raises(NoCoverageError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert str(exc_info.value) == (
            f"No NMT 1m data for {self.SHEET} (PL-1992 system, EVRF2007)"
        )
        assert len(wfs_requests(session, _EVRF2007)) == 1
        assert len(wfs_requests(session, _KRON86)) == 1
        assert session.get.call_count == 2

    def test_transport_error_retries_same_query(self, record_response):
        """A dropped connection repeats THE SAME GetFeature after backoff."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset"), record_response]
        )

        with patch("time.sleep") as sleep:
            url = GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert url == self.URL
        first, second = (call.args[0] for call in session.get.call_args_list)
        assert first == second
        assert first.startswith(f"{_EVRF2007}?")
        assert sleep.call_count == 1

    def test_transport_error_exhausted_is_service_failure(self, record_response):
        """3 x failure of the one query = DownloadError naming the sheet; no
        other query follows, so no older campaign ever stands in for the
        unknown answer."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset")] * 3 + [record_response] * 3
        )

        with patch("time.sleep") as sleep, pytest.raises(DownloadError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert exc_info.value.sheet == self.SHEET
        assert self.SHEET in str(exc_info.value)
        assert len({call.args[0] for call in session.get.call_args_list}) == 1
        assert session.get.call_count == 3
        assert sleep.call_count == 2

    @pytest.mark.parametrize(
        ("status", "shown"),
        [(400, "HTTP 400"), (200, "TYPENAME 'SkorowidzNMT1900' doesn't exist")],
    )
    def test_exception_report_is_service_failure(self, status, shown):
        """A WFS ExceptionReport (recorded with HTTP 400; also with HTTP 200) =
        DownloadError naming the sheet after one query, without retries and not
        mistaken for a missing sheet."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            return_value=wfs_response(wfs_fixture("exception_report.xml"), status)
        )

        with patch("time.sleep") as sleep, pytest.raises(DownloadError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert shown in str(exc_info.value)
        assert self.SHEET in str(exc_info.value)
        assert session.get.call_count == 1
        sleep.assert_not_called()

    @pytest.mark.parametrize(
        "body",
        [
            "<html><body>502 Bad Gateway</body></html>",
            "<html><body><h1>502 Bad Gateway</h1><hr></body></html>",
        ],
    )
    def test_answer_without_features_is_service_failure(self, body):
        """HTTP 200 that is not a feature collection (a gateway page, HTML that
        is not XML) = DownloadError after one query, never no coverage."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=wfs_response(body))

        with pytest.raises(DownloadError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert not isinstance(exc_info.value, NoCoverageError)
        assert session.get.call_count == 1

    @pytest.mark.parametrize("newest_first", [True, False])
    def test_latest_campaign_wins_within_type(self, newest_first):
        """Two campaigns of one yearly type: the newest acquisition date wins,
        not the order of the answer."""
        records = [
            wfs_record(self.SHEET, akt_data="2023-09-06", url="https://x/new.asc"),
            wfs_record(self.SHEET, akt_data="2023-04-06", url="https://x/old.asc"),
        ]
        if not newest_first:
            records.reverse()
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=wfs_response(render_wfs_body(records)))

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == "https://x/new.asc"

    def test_dt_pzgik_breaks_aktualnosc_tie(self):
        """An acquisition date tie is broken by the later dt_pzgik."""
        records = [
            wfs_record(self.SHEET, dt_pzgik="2024-11-02", url="https://x/earlier.asc"),
            wfs_record(self.SHEET, dt_pzgik="2025-01-10", url="https://x/later.asc"),
        ]
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=wfs_response(render_wfs_body(records)))

        url = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution="1m"
        )._get_opendata_url(self.SHEET)

        assert url == "https://x/later.asc"

    def test_other_resolution_only_is_no_coverage_with_hint(self):
        """0.5m and 5m grids and a 1m XYZ archive, no 1m grid: the hints name the
        grid resolutions from the same answer (no second query to the service),
        not the archive."""
        xyz = (
            "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/73843/"
            f"73843_1036985_{self.SHEET}.xyz.zip"
        )
        records = [
            wfs_record(self.SHEET, resolution="0.50 m", akt_data="2025-01-30"),
            wfs_record(self.SHEET, resolution="5.00 m"),
            wfs_record(self.SHEET, format="ASCII XYZ GRID", url=xyz),
        ]
        session = _index_session(nmt_evrf2007=render_wfs_body(records))

        with pytest.raises(NoCoverageError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        assert exc_info.value.hints == (
            (
                "The GUGiK sheet index has this sheet in NMT 0.5m EVRF2007 - use "
                "--resolution 0.5m"
            ),
            (
                "The GUGiK sheet index has this sheet in NMT 5m EVRF2007 - use "
                "--resolution 5m"
            ),
        )
        assert len(wfs_requests(session, _EVRF2007)) == 1

    def test_negative_cache_preserves_resolution_hint(self, tmp_path):
        """A cached no-coverage answer repeats the message with its hints for
        another provider on the same cache, without a request."""
        from kartograf.cache.metadata import MetadataCache

        record = wfs_record(self.SHEET, resolution="0.50 m")
        session = _index_session(nmt_evrf2007=render_wfs_body([record]))
        cache = MetadataCache(db_path=tmp_path / "cache.db")
        try:
            with pytest.raises(NoCoverageError) as first:
                GugikProvider(
                    session=session,
                    cache=cache,
                    vertical_crs="EVRF2007",
                    resolution="1m",
                )._get_opendata_url(self.SHEET)
            calls = session.get.call_count
            with pytest.raises(NoCoverageError) as cached:
                GugikProvider(
                    session=session,
                    cache=cache,
                    vertical_crs="EVRF2007",
                    resolution="1m",
                )._get_opendata_url(self.SHEET)
            assert session.get.call_count == calls
            assert str(cached.value) == str(first.value)
            assert cached.value.hints == first.value.hints
            assert "use --resolution 0.5m" in str(cached.value)
        finally:
            cache.close()

    def test_other_vertical_crs_hint_from_one_query(self):
        """No record of the sheet in EVRF2007: ONE GetFeature with every KRON86
        type (recorded answer) finds its 1m grid there - the hint names
        --vertical-crs; the KRON86 archives of the point are not named."""
        sheet = "N-33-58-A-c-1-4"
        session = _index_session(
            nmt_kron86=wfs_fixture(f"sheet_nmt_kron86_{sheet}.xml")
        )

        with pytest.raises(NoCoverageError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(sheet)

        assert exc_info.value.hints == (
            (
                "The GUGiK sheet index has this sheet in NMT 1m KRON86 - use "
                "--vertical-crs KRON86"
            ),
        )
        assert [query["TYPENAMES"] for query in wfs_requests(session, _KRON86)] == [
            ",".join(wfs_types("nmt_kron86"))
        ]

    @pytest.mark.parametrize(
        ("resolution", "vertical_crs", "char_przestrz", "tag"),
        [
            ("1m", "EVRF2007", "1.00 m", "nmt_evrf2007"),
            ("5m", "EVRF2007", "5.00 m", "nmt_evrf2007"),
            ("0.5m", "KRON86", "0.50 m", "nmt_kron86"),
            ("1m", "KRON86", "1.00 m", "nmt_kron86"),
        ],
    )
    def test_get_feature_goes_to_variant_service(
        self, resolution, vertical_crs, char_przestrz, tag
    ):
        """The one GetFeature asks the WFS service of the variant's height
        system, with every type that service publishes."""
        record = wfs_record(
            self.SHEET, resolution=char_przestrz, uklad_h=f"PL-{vertical_crs}-NH"
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=wfs_response(render_wfs_body([record])))

        url = GugikProvider(
            session=session, resolution=resolution, vertical_crs=vertical_crs
        )._get_opendata_url(self.SHEET)

        assert url == self.URL
        assert session.get.call_count == 1
        (query,) = wfs_requests(session, wfs_endpoint(tag))
        assert query["TYPENAMES"] == ",".join(wfs_types(tag))


class TestGugikProviderSession:
    """Tests of HTTP session management: one injected or one per thread."""

    SHEET = "N-34-130-D"

    @pytest.fixture
    def record_body(self):
        return render_wfs_body([wfs_record(self.SHEET)])

    @staticmethod
    def file_response():
        response = Mock()
        response.iter_content = Mock(return_value=[b"data"])
        return response

    def test_uses_provided_session(self, tmp_path, record_body):
        """The injected session serves the index and the file; no other is created."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[wfs_response(record_body), self.file_response()]
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
        session.get = Mock(return_value=wfs_response(record_body))

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
            session.get = Mock(return_value=wfs_response(record_body))
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
        assert results == [wfs_record(self.SHEET)["url_do_pobrania"]] * 2

    @pytest.mark.real_wfs_types
    def test_provided_session_serves_get_capabilities(self, tmp_path, record_body):
        """Without the type stub: the injected session does GetCapabilities of
        the variant's WFS service, ONE GetFeature with every yearly type it
        publishes (recorded: 2026..2018), then the file stream."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                wfs_response(wfs_fixture("caps_nmt_evrf2007.xml")),
                wfs_response(record_body),
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
        assert calls[0].args[0].startswith(f"{_EVRF2007}?")
        assert "REQUEST=GetCapabilities" in calls[0].args[0]
        (query,) = wfs_requests(session, _EVRF2007)
        assert query["TYPENAMES"] == ",".join(
            f"gugik:SkorowidzNMT{year}" for year in range(2026, 2017, -1)
        )
        assert calls[2].kwargs["stream"] is True

    @pytest.mark.real_wfs_types
    def test_thread_session_serves_get_capabilities(self, record_body):
        """Without an injected session GetCapabilities and GetFeature share the
        one session make_gugik_session gives the thread."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                wfs_response(wfs_fixture("caps_nmt_evrf2007.xml")),
                wfs_response(record_body),
            ]
        )

        with patch(SESSION_FACTORY, return_value=session) as factory:
            url = GugikProvider(
                vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url(self.SHEET)

        factory.assert_called_once()
        assert url == wfs_record(self.SHEET)["url_do_pobrania"]
        requested = [
            parse_qs(urlparse(call.args[0]).query)["REQUEST"]
            for call in session.get.call_args_list
        ]
        assert requested == [["GetCapabilities"], ["GetFeature"]]


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
    """Sheet selection on recorded WFS answers (fixture README) and on records
    shaped like them."""

    @staticmethod
    def response(body):
        response = requests.Response()
        response.status_code = 200
        response._content = body.encode()
        response.encoding = "utf-8"
        return response

    @pytest.mark.parametrize(
        ("sheet", "resolution", "vertical_crs", "expected"),
        [
            # 1m of 2022, while the 0.5m and 5m records of 2025 are newer
            ("N-33-58-A-c-1-4", "1m", "EVRF2007", "76036_1189924"),
            # the newest of four 1m campaigns, never the ASCII NMT 1m archive
            ("N-33-77-B-c-3-3", "1m", "EVRF2007", "80196_1534047"),
            # the newest of three 0.6m campaigns among 0.5m, 1m and 5m ones
            ("N-33-77-B-c-3-3", "0.6m", "EVRF2007", "84008_1843892"),
            # the 1m grid of 2011, while the 1m XYZ archive of 2017 is newer
            ("N-33-58-A-c-1-4", "1m", "KRON86", "3646_66649"),
        ],
    )
    def test_exact_resolution_and_latest_campaign(
        self, sheet, resolution, vertical_crs, expected
    ):
        recorded = wfs_fixture(f"sheet_nmt_{vertical_crs.lower()}_{sheet}.xml")
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(recorded)

        url = GugikProvider(
            session=session, vertical_crs=vertical_crs, resolution=resolution
        )._get_opendata_url(sheet)

        assert url.rsplit("/", 1)[-1] == f"{expected}_{sheet}.asc"

    def test_no_substring_fallback(self):
        """Only a record of a descendant of the PL-2000 sheet: no coverage, the
        hint names the descendant's --scale."""
        body = render_wfs_body([wfs_record("5.167.25.13", system="PL-2000:S5")])
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(body)
        with pytest.raises(NoCoverageError, match="--scale 1:2000"):
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url("5.167.25")

    def test_no_other_system_fallback(self):
        """PL-2000 sheet 6.125.25 (recorded answer) has 5m and 10m records, the
        1m records of the point are PL-1992 sheets: nothing is chosen, the
        hints name the resolutions and the PL-1992 sheets."""
        session = _index_session(
            nmt_evrf2007=wfs_fixture("sheet_nmt_evrf2007_6.125.25.xml")
        )

        with pytest.raises(NoCoverageError) as exc_info:
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url("6.125.25")

        assert exc_info.value.hints == (
            (
                "The GUGiK sheet index has this sheet in NMT 10m EVRF2007 - use "
                "--resolution 10m"
            ),
            (
                "The GUGiK sheet index has this sheet in NMT 5m EVRF2007 - use "
                "--resolution 5m"
            ),
            "The sheet index has this area in PL-1992: M-34-62-C-c-1-1 (1:10000) - "
            "use this sheet code or --sheet-system 1992",
            "The sheet index has this area in PL-1992: M-34-62-C-c-1-3 (1:10000) - "
            "use this sheet code or --sheet-system 1992",
        )

    def test_uppercase_asc_is_available(self):
        """A record URL ending in .ASC (old deliveries; no recorded WFS answer
        has one) is the ASC grid."""
        record = wfs_record(
            "N-33-126-C-c-3-2",
            resolution="5.00 m",
            url="https://opendata.geoportal.gov.pl/NumDaneWys/NMT/76969/"
            "76969_1298029_N-33-126-C-c-3-2.ASC",
        )
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(render_wfs_body([record]))
        url = GugikProvider(
            session=session, resolution="5m", vertical_crs="EVRF2007"
        )._get_opendata_url("N-33-126-C-c-3-2")
        assert url.endswith("76969_1298029_N-33-126-C-c-3-2.ASC")

    def test_no_coverage_leaves_no_directory(self, tmp_path):
        """Sea (recorded answer without features) = NoCoverageError, no directory."""
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(
            wfs_fixture("sheet_nmt_evrf2007_N-33-46-C-c-3-2.xml")
        )
        output = tmp_path / "not-created" / "sheet.asc"
        with pytest.raises(NoCoverageError):
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            ).download("N-33-46-C-c-3-2", output)
        assert not output.parent.exists()

    def test_failed_query_is_not_cached(self, tmp_path):
        """A failed query caches nothing: the next call asks the index again and
        gets the newest record (recorded answer)."""
        from kartograf.cache.metadata import MetadataCache

        sheet = "N-33-58-A-c-1-4"
        cache = MetadataCache(tmp_path / "cache.db")
        session = Mock(spec=requests.Session)
        session.get.side_effect = [requests.ConnectionError("reset")] * 3 + [
            self.response(wfs_fixture(f"sheet_nmt_evrf2007_{sheet}.xml"))
        ]
        provider = GugikProvider(
            session=session, cache=cache, vertical_crs="EVRF2007", resolution="1m"
        )
        try:
            with patch("time.sleep"), pytest.raises(DownloadError):
                provider._get_opendata_url(sheet)
            url = provider._get_opendata_url(sheet)
        finally:
            cache.close()
        assert url.endswith(f"76036_1189924_{sheet}.asc")
        assert session.get.call_count == 4

    def test_1m_rejects_5m_record(self):
        body = render_wfs_body([wfs_record("N-33-90-C-c-2-4", resolution="5.00 m")])
        session = _index_session(nmt_evrf2007=body)
        with pytest.raises(NoCoverageError, match="use --resolution 5m"):
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url("N-33-90-C-c-2-4")

    def test_5m_accepts_5m_record(self):
        record = wfs_record("N-33-90-C-c-2-4", resolution="5.00 m")
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(render_wfs_body([record]))
        provider = GugikProvider(
            session=session, resolution="5m", vertical_crs="EVRF2007"
        )
        assert (
            provider._get_opendata_url("N-33-90-C-c-2-4") == record["url_do_pobrania"]
        )

    def test_pl2000_record_matches_only_same_zone(self):
        record = wfs_record("7.173.21.06", system="PL-2000:S7")
        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(render_wfs_body([record]))
        assert (
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url("7.173.21.06")
            == record["url_do_pobrania"]
        )

        session = Mock(spec=requests.Session)
        session.get.return_value = self.response(
            render_wfs_body([wfs_record("7.173.21.06", system="PL-2000:S6")])
        )
        with pytest.raises(NoCoverageError, match="PL-2000"):
            GugikProvider(
                session=session, vertical_crs="EVRF2007", resolution="1m"
            )._get_opendata_url("7.173.21.06")
