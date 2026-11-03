"""
Unit tests for the GugikNmptProvider module.

This module contains tests for the GugikNmptProvider class, which inherits
from GugikProvider and provides Digital Surface Model (NMPT) downloads from
GUGiK - DSM data containing terrain + surface objects.

The provider serves one variant of the registry (``kartograf.sources.variants``:
0.5m/0.6m/1m grids, XYZ archives in KRON86); sheet records come from the NMPT
WFS index of the chosen vertical CRS (one GetFeature with every yearly type)
and the file from OpenData. WCS (GeoTIFF from ``image/x-aaigrid``) exists only
for the 1m grid. Index answers are the recorded WFS fixtures of 2026-10-15
(``tests/fixtures/gugik_wfs/real_2026_10_15``).
"""

from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import rasterio
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.sources.variants import variants
from tests.conftest import (
    WCS_FIXTURES,
    recorded_response,
    render_wfs_body,
    wfs_endpoint,
    wfs_fixture,
    wfs_requests,
    wfs_response,
    wfs_types,
)

NMPT_EVRF2007 = wfs_endpoint("nmpt_evrf2007")
NMPT_KRON86 = wfs_endpoint("nmpt_kron86")
OPENDATA = "https://opendata.geoportal.gov.pl/NumDaneWys/NMPT"
# Recorded sheet N-33-58-A-d-1-2 (EVRF2007): 1m 2022 and 0.5m 2025 (partial)
SHEET_E = "N-33-58-A-d-1-2"
URL_E_1M = f"{OPENDATA}/76027/76027_1185054_{SHEET_E}.asc"
URL_E_05M = f"{OPENDATA}/84018/84018_1843926_{SHEET_E}.asc"
# Recorded sheet N-34-50-C-d-3-4 (KRON86): 0.5m ASC and XYZ, 2010 and 2018
SHEET_K = "N-34-50-C-d-3-4"
ASC_BYTES = b"ncols 100\nnrows 100\n"


def _nmpt(**kwargs) -> GugikNmptProvider:
    """NMPT provider; EVRF2007 1m grid unless overridden."""
    return GugikNmptProvider(
        **{"vertical_crs": "EVRF2007", "resolution": "1m", **kwargs}
    )


def _file_response() -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.iter_content = Mock(return_value=[ASC_BYTES, b"data..."])
    return response


def _index_session(answers: dict[str, str]) -> Mock:
    """Session answering GetFeature per WFS service (``answers``: endpoint ->
    GML; a service missing from it answers an empty collection) and any
    other URL with an ASC file."""

    def get(url: str, **kwargs):
        for endpoint in (NMPT_EVRF2007, NMPT_KRON86):
            if url.startswith(f"{endpoint}?"):
                return wfs_response(answers.get(endpoint, render_wfs_body([])))
        if url.startswith("https://mapy.geoportal.gov.pl/"):
            raise AssertionError(f"unexpected index request: {url}")
        return _file_response()

    session = Mock(spec=requests.Session)
    session.get = Mock(side_effect=get)
    return session


def _file_urls(session: Mock) -> list[str]:
    return [
        call.args[0]
        for call in session.get.call_args_list
        if call.args[0].startswith(f"{OPENDATA}/")
    ]


# =========================================================================
# TestGugikNmptProviderInit
# =========================================================================


class TestGugikNmptProviderInit:
    """Tests of GugikNmptProvider initialization (variant from the registry)."""

    @pytest.mark.parametrize(
        ("vertical_crs", "resolution", "file_format", "key", "extension"),
        [
            ("EVRF2007", "1m", "ASC", "pl.gugik.nmpt", ".asc"),
            ("KRON86", "1m", "ASC", "pl.gugik.nmpt", ".asc"),
            ("EVRF2007", "0.5m", "ASC", "pl.gugik.nmpt_0_5m", ".asc"),
            ("KRON86", "0.5m", "ASC", "pl.gugik.nmpt_0_5m", ".asc"),
            ("EVRF2007", "0.6m", "ASC", "pl.gugik.nmpt_0_6m", ".asc"),
            ("KRON86", "0.5m", "XYZ", "pl.gugik.nmpt_xyz_0_5m", ".zip"),
            ("KRON86", "1m", "XYZ", "pl.gugik.nmpt_xyz_1m", ".zip"),
        ],
    )
    def test_serves_chosen_variant(
        self, vertical_crs, resolution, file_format, key, extension
    ):
        """The provider serves the chosen variant: its label, descriptor (the
        sidecar ``dataset``; 1m keeps ``pl.gugik.nmpt``) and file extension."""
        provider = GugikNmptProvider(
            vertical_crs=vertical_crs, resolution=resolution, format=file_format
        )

        assert provider.resolution == resolution
        assert provider.vertical_crs == vertical_crs
        assert provider.format == file_format
        assert provider.descriptor_key == key
        assert provider.default_extension == extension

    @pytest.mark.parametrize(
        "variant",
        variants(product="nmpt", country="PL"),
        ids=lambda v: f"{v.format}-{v.label}-{v.vertical_crs}",
    )
    def test_every_registry_variant_is_served(self, variant):
        """Every NMPT variant of the registry is a valid provider choice."""
        provider = GugikNmptProvider(
            vertical_crs=variant.vertical_crs,
            resolution=variant.label,
            format=variant.format,
        )

        assert provider.variant == variant
        assert provider.descriptor_key == variant.source

    def test_missing_resolution_lists_registry_labels(self):
        """NMPT has no default resolution (0.8.0): the error lists the grid
        labels of the registry per vertical CRS."""
        with pytest.raises(ValidationError) as exc:
            GugikNmptProvider(vertical_crs="EVRF2007", resolution=None)

        message = str(exc.value)
        assert message.startswith("--resolution required for NMPT ASC PL: ")
        for vertical_crs in ("EVRF2007", "KRON86"):
            grid = variants(
                product="nmpt", country="PL", vertical_crs=vertical_crs, format="ASC"
            )
            labels = [v.label for v in sorted(grid, key=lambda v: v.resolution_m)]
            assert f"{vertical_crs}: {', '.join(labels)}" in message

    @pytest.mark.parametrize("resolution", ["5m", "0.50m", "50cm", "2m"])
    def test_unknown_resolution_lists_registry_labels(self, resolution):
        """A label outside the registry (or not canonical) names every NMPT
        grid label instead of falling back to a default."""
        with pytest.raises(ValidationError) as exc:
            _nmpt(resolution=resolution)

        message = str(exc.value)
        assert message.startswith(
            f"PL has no resolution {resolution} for NMPT ASC - available: "
        )
        grid_labels = {v.label for v in variants(product="nmpt", format="ASC")}
        assert grid_labels == {"0.5m", "0.6m", "1m"}
        for label in grid_labels:
            assert label in message

    def test_resolution_of_other_vertical_crs(self):
        """0.6m exists only in EVRF2007: the error names the KRON86 labels."""
        with pytest.raises(ValidationError) as exc:
            _nmpt(vertical_crs="KRON86", resolution="0.6m")

        assert str(exc.value) == (
            "NMPT ASC 0.6m (PL) is only available in EVRF2007 - got --vertical-crs "
            "KRON86; available in KRON86: 0.5m, 1m"
        )

    def test_archive_only_in_kron86(self):
        """The XYZ archives are KRON86 only: EVRF2007 XYZ is not a variant."""
        with pytest.raises(ValidationError) as exc:
            _nmpt(resolution="0.5m", format="XYZ")

        assert str(exc.value) == (
            "NMPT XYZ (PL) is only available in KRON86 - got --vertical-crs EVRF2007"
        )

    def test_invalid_vertical_crs(self):
        """An unknown vertical CRS names the registry systems."""
        with pytest.raises(ValidationError) as exc:
            _nmpt(vertical_crs="INVALID")

        assert str(exc.value) == (
            "NMPT ASC (PL) is only available in EVRF2007, KRON86 - got "
            "--vertical-crs INVALID"
        )


# =========================================================================
# TestGugikNmptProviderProperties
# =========================================================================


class TestGugikNmptProviderProperties:
    """Tests of the GugikNmptProvider properties."""

    def test_name(self):
        """Test that name returns 'GUGiK NMPT'."""
        assert _nmpt().name == "GUGiK NMPT"

    def test_base_url(self):
        """Test that base_url returns the geoportal URL."""
        assert _nmpt().base_url == "https://mapy.geoportal.gov.pl"

    def test_describe_names_product_and_variant(self):
        """Messages name the NMPT variant (grid label, archive format)."""
        assert _nmpt(resolution="0.5m").describe() == "NMPT 0.5m"
        assert (
            _nmpt(vertical_crs="KRON86", resolution="1m", format="XYZ").describe()
            == "NMPT XYZ 1m"
        )

    def test_repr(self):
        """Test that repr contains 'GugikNmptProvider'."""
        repr_str = repr(_nmpt())
        assert "GugikNmptProvider" in repr_str
        assert "mapy.geoportal.gov.pl" in repr_str

    def test_str(self):
        """Test that str contains 'GUGiK NMPT'."""
        str_repr = str(_nmpt())
        assert "GUGiK NMPT" in str_repr
        assert "mapy.geoportal.gov.pl" in str_repr


# =========================================================================
# TestGugikNmptProviderEndpoints
# =========================================================================


class TestGugikNmptProviderEndpoints:
    """Tests of NMPT endpoints and the sheet index."""

    def test_wcs_endpoints_are_nmpt(self):
        """Test that the WCS endpoints contain 'NMPT' (not 'NMT')."""
        provider = _nmpt()
        for crs, url in provider.WCS_ENDPOINTS.items():
            assert "NMPT" in url, f"WCS endpoint for {crs} should contain 'NMPT'"
            assert "NMT/" not in url, (
                f"WCS endpoint for {crs} should not contain 'NMT/'"
            )

    @pytest.mark.parametrize(
        ("vertical_crs", "own", "other"),
        [
            ("EVRF2007", "nmpt_evrf2007", "nmpt_kron86"),
            ("KRON86", "nmpt_kron86", "nmpt_evrf2007"),
        ],
    )
    def test_sheet_records_come_from_nmpt_wfs_of_vertical_crs(
        self, tmp_path, vertical_crs, own, other
    ):
        """The sheet query is one GetFeature to the NMPT WFS index of the chosen
        vertical CRS with every yearly SkorowidzNMPT type; no NMT service is
        asked (the other NMPT system only for the no-coverage hint, P10)."""
        session = _index_session({})

        with pytest.raises(NoCoverageError):
            _nmpt(session=session, vertical_crs=vertical_crs).download(
                SHEET_E, tmp_path / "s.asc"
            )

        own_queries = wfs_requests(session, wfs_endpoint(own))
        assert [q["TYPENAMES"] for q in own_queries] == [",".join(wfs_types(own))]
        assert all("SkorowidzNMPT" in t for t in wfs_types(own))
        assert len(wfs_requests(session, wfs_endpoint(other))) == 1
        assert len(wfs_requests(session)) == 2

    def test_coverage_ids_are_dsm(self):
        """Test that the coverage IDs are DSM_PL-* (not DTM)."""
        for crs, coverage_id in _nmpt().COVERAGE_IDS.items():
            assert coverage_id.startswith("DSM_PL-"), (
                f"Coverage ID for {crs} should start with "
                f"'DSM_PL-', got '{coverage_id}'"
            )
            assert "DTM" not in coverage_id, (
                f"Coverage ID for {crs} should not contain 'DTM'"
            )

    def test_wcs_available_only_for_1m_grid(self):
        """WCS heights exist for the 1m grid in both vertical CRS (own
        endpoint); 0.5m/0.6m grids and archives are sheets only."""
        assert _nmpt(vertical_crs="EVRF2007").is_wcs_available() is True
        assert _nmpt(vertical_crs="KRON86").is_wcs_available() is True
        assert _nmpt(resolution="0.5m").is_wcs_available() is False
        assert _nmpt(resolution="0.6m").is_wcs_available() is False
        assert _nmpt(vertical_crs="KRON86", format="XYZ").is_wcs_available() is False


# =========================================================================
# TestGugikNmptProviderDownload
# =========================================================================


class TestGugikNmptProviderDownload:
    """Tests of NMPT data download."""

    @pytest.fixture
    def sample_bbox(self):
        """Sample bbox in EPSG:2180."""
        return BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

    def test_download_uses_opendata(self, tmp_path):
        """One GetFeature to the NMPT EVRF2007 index, then the OpenData file of
        the 1m record (the 0.5m record of the same answer is not taken)."""
        session = _index_session(
            {NMPT_EVRF2007: wfs_fixture(f"sheet_nmpt_evrf2007_{SHEET_E}.xml")}
        )
        output_path = tmp_path / "test.asc"

        result = _nmpt(session=session).download(SHEET_E, output_path)

        assert result == output_path
        assert output_path.read_bytes() == ASC_BYTES + b"data..."
        first_call_url = session.get.call_args_list[0].args[0]
        assert first_call_url.startswith(f"{NMPT_EVRF2007}?")
        assert len(wfs_requests(session)) == 1
        assert _file_urls(session) == [URL_E_1M]

    def test_nmpt_0_5m(self, tmp_path):
        """0.5m EVRF2007: the newest 0.5m grid of the sheet (2025, partial)
        from the same index; its source names the WFS service and type."""
        session = _index_session(
            {NMPT_EVRF2007: wfs_fixture(f"sheet_nmpt_evrf2007_{SHEET_E}.xml")}
        )
        provider = _nmpt(session=session, resolution="0.5m")

        provider.download(SHEET_E, tmp_path / "s.asc")

        assert _file_urls(session) == [URL_E_05M]
        source = provider.source_info(SHEET_E)
        assert source is not None
        assert source["index_url"] == NMPT_EVRF2007
        assert source["layer"] == "SkorowidzNMPT2025"
        assert source["resolution_m"] == 0.5
        assert source["full_sheet"] is False

    @pytest.mark.parametrize(
        ("file_format", "url"),
        [
            ("ASC", f"{OPENDATA}/70934/70934_850798_{SHEET_K}.asc"),
            ("XYZ", f"{OPENDATA}/70933/70933_850645_{SHEET_K}.xyz.zip"),
        ],
    )
    def test_kron86_format_filter(self, tmp_path, file_format, url):
        """KRON86 publishes the same 0.5m flight as ASC grid and XYZ archive:
        the format of the variant picks the record (newest, 2018)."""
        session = _index_session(
            {NMPT_KRON86: wfs_fixture(f"sheet_nmpt_kron86_{SHEET_K}.xml")}
        )
        provider = _nmpt(
            session=session,
            vertical_crs="KRON86",
            resolution="0.5m",
            format=file_format,
        )

        provider.download(SHEET_K, tmp_path / f"s{provider.default_extension}")

        assert _file_urls(session) == [url]
        assert wfs_requests(session, NMPT_EVRF2007) == []

    def test_no_coverage_names_other_nmpt_resolutions(self, tmp_path):
        """A sheet with only 0.5m/0.6m grids: 1m is no coverage with hints
        naming the other NMPT labels from the same answer."""
        sheet = "N-33-77-B-c-3-3"
        session = _index_session(
            {NMPT_EVRF2007: wfs_fixture(f"sheet_nmpt_evrf2007_{sheet}.xml")}
        )

        with pytest.raises(NoCoverageError) as exc:
            _nmpt(session=session).download(sheet, tmp_path / "s.asc")

        assert exc.value.sheet == sheet
        assert exc.value.hints == (
            (
                "The GUGiK sheet index has this sheet in NMPT 0.5m EVRF2007 - use "
                "--resolution 0.5m"
            ),
            (
                "The GUGiK sheet index has this sheet in NMPT 0.6m EVRF2007 - use "
                "--resolution 0.6m"
            ),
        )
        assert len(wfs_requests(session, NMPT_EVRF2007)) == 1
        assert _file_urls(session) == []

    def test_index_failure_is_download_error_not_no_coverage(self, tmp_path):
        """A broken index answer fails the sheet - never an empty result."""
        session = _index_session({NMPT_EVRF2007: wfs_fixture("exception_report.xml")})

        with pytest.raises(
            DownloadError, match=("the result would be incomplete")
        ) as exc:
            _nmpt(session=session).download(SHEET_E, tmp_path / "s.asc")

        assert not isinstance(exc.value, NoCoverageError)
        assert _file_urls(session) == []

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

        _nmpt(session=session, vertical_crs=vertical_crs).download_bbox(
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

    @pytest.mark.parametrize(
        "choice",
        [
            {"resolution": "0.5m"},
            {"resolution": "0.6m"},
            {"vertical_crs": "KRON86", "resolution": "1m", "format": "XYZ"},
        ],
    )
    def test_download_bbox_only_for_1m_grid(self, tmp_path, sample_bbox, choice):
        """Only the 1m grid has WCS: other variants fail before the network."""
        session = Mock(spec=requests.Session)
        provider = _nmpt(session=session, **choice)

        with pytest.raises(ValidationError) as exc:
            provider.download_bbox(sample_bbox, tmp_path / "x.tif")

        assert str(exc.value) == (
            "WCS download (download_bbox) is available only for the NMPT 1m grid - "
            f"download {provider.describe()} via download() (sheets)"
        )
        session.get.assert_not_called()

    def test_nmpt_chunk_budget_counts_coverage_pixels(self):
        """NMPT 1 m reads 4 coverage pixels (0.5 m) per result pixel, so its
        4 Mpx coverage budget cuts a 2000 x 1000 m area into chunks of at most
        1 Mpx of result; NMT EVRF2007 (1 m coverage, 1 Mpx budget) gets the same."""
        bbox = BBox(567099.5, 243999.5, 569099.5, 244999.5, "EPSG:2180")

        nmpt = _nmpt().plan_wcs_chunks(bbox)
        nmt = GugikProvider(vertical_crs="EVRF2007", resolution="1m").plan_wcs_chunks(
            bbox
        )

        assert len(nmpt) == 2 and max(c.width * c.height for c in nmpt) <= 1_000_000
        assert [(c.width, c.height) for c in nmt] == [(c.width, c.height) for c in nmpt]

    def test_download_bbox_rejects_exception_report(self, tmp_path, sample_bbox):
        """The single NMPT request is validated too: an OGC ExceptionReport with
        HTTP 200 is a DownloadError, never a .tif file."""
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
            _nmpt(session=session).download_bbox(sample_bbox, output_path)
        assert not output_path.exists()

    def test_get_opendata_url_uses_nmpt_index(self):
        """_get_opendata_url reads the NMPT WFS index (not NMT): one query."""
        session = _index_session(
            {NMPT_EVRF2007: wfs_fixture(f"sheet_nmpt_evrf2007_{SHEET_E}.xml")}
        )

        url = _nmpt(session=session)._get_opendata_url(SHEET_E)

        assert url == URL_E_1M
        session.get.assert_called_once()
        assert session.get.call_args.args[0].startswith(f"{NMPT_EVRF2007}?")


# =========================================================================
# TestGugikNmptProviderInheritance
# =========================================================================


class TestGugikNmptProviderInheritance:
    """Tests of GugikNmptProvider inheritance."""

    def test_is_instance_of_base_provider(self):
        """Test that GugikNmptProvider is an instance of BaseProvider."""
        assert isinstance(_nmpt(), BaseProvider)

    def test_is_instance_of_gugik_provider(self):
        """Test that GugikNmptProvider is an instance of GugikProvider."""
        assert isinstance(_nmpt(), GugikProvider)

    def test_inherits_retry_logic(self):
        """Test that MAX_RETRIES is inherited and equals 3."""
        assert _nmpt().MAX_RETRIES == 3
