"""Tests of source descriptors and the registry (kartograf.sources)."""

import dataclasses

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError
from kartograf.sources.descriptor import (
    AccessChannel,
    CountryProfile,
    LicenseInfo,
    SourceDescriptor,
    TileScheme,
    TransportKind,
)
from kartograf.sources.registry import (
    all_countries,
    channel_signal,
    get_country,
    get_source,
    horizontal_crs_for_sheet,
    horizontal_crs_for_system,
    resolve_vertical_crs,
    sources_for,
    vertical_crs_code,
)

EXPECTED_KEYS = {
    "pl.gugik.nmt_1m",
    "pl.gugik.nmt_5m",
    "pl.gugik.nmpt",
    "pl.gugik.orto",
    "pl.gugik.laz",
    "pl.gugik.bdot10k",
    "eu.clms.corine",
    "global.isric.soilgrids",
    "cz.cuzk.dmr5g",
    "cz.cuzk.dmr4g",
}

# Signal inventory (docs/research/2026-10-12-signal-inventory/raport.md).
CHANNEL_SIGNALS = [
    ("pl.gugik.nmt_1m", TransportKind.WMS_SHEET_INDEX, "index"),
    ("pl.gugik.nmt_1m", TransportKind.WCS, "none"),
    ("pl.gugik.nmt_5m", TransportKind.WMS_SHEET_INDEX, "index"),
    ("pl.gugik.nmpt", TransportKind.WMS_SHEET_INDEX, "index"),
    ("pl.gugik.nmpt", TransportKind.WCS, "none"),
    ("pl.gugik.orto", TransportKind.WMS_SHEET_INDEX, "index"),
    ("pl.gugik.laz", TransportKind.WFS, "index"),
    ("pl.gugik.bdot10k", TransportKind.DIRECT_FILES, "none"),
    ("eu.clms.corine", TransportKind.CLMS_API, "metadata"),
    ("eu.clms.corine", TransportKind.WMS, "none"),
    ("global.isric.soilgrids", TransportKind.WCS, "metadata"),
    ("cz.cuzk.dmr5g", TransportKind.ARCGIS_IMAGE, "none"),
    ("cz.cuzk.dmr4g", TransportKind.DIRECT_FILES, "http"),
    ("cz.cuzk.dmr4g", TransportKind.ARCGIS_IMAGE, "none"),
]


@pytest.mark.parametrize(("key", "transport", "signal"), CHANNEL_SIGNALS)
def test_channel_signals_match_inventory(key, transport, signal):
    assert channel_signal(key, transport) == signal


def test_every_channel_has_an_inventoried_signal():
    inventoried = {(key, transport) for key, transport, _ in CHANNEL_SIGNALS}
    channels = {(d.key, c.transport) for d in sources_for() for c in d.channels}
    assert channels == inventoried


@pytest.mark.parametrize(
    ("key", "transport"),
    [("xx.none.zadne", TransportKind.WCS), ("pl.gugik.nmt_5m", TransportKind.WCS)],
)
def test_unknown_channel_signal_is_error(key, transport):
    with pytest.raises(ValidationError):
        channel_signal(key, transport)


class TestDescriptorDataclasses:
    def _channel(self) -> AccessChannel:
        return AccessChannel(
            transport=TransportKind.WCS,
            horizontal_crs="EPSG:2180",
            vertical_crs_options=("EPSG:9650", "EPSG:9651"),
            capabilities=frozenset({"bbox_raster"}),
        )

    def test_transport_kind_values(self):
        assert TransportKind.WCS == "wcs"
        assert TransportKind.WMS_SHEET_INDEX == "wms_sheet_index"
        assert TransportKind.WFS == "wfs"
        assert TransportKind.DIRECT_FILES == "direct_files"
        assert TransportKind.CLMS_API == "clms_api"
        assert TransportKind.ARCGIS_IMAGE == "arcgis_image"
        assert TransportKind.ARCGIS_QUERY == "arcgis_query"
        assert TransportKind.OGC_API_FEATURES == "ogc_api_features"

    def test_access_channel_defaults(self):
        ch = self._channel()
        assert ch.vertical_source == "native"
        assert ch.server_reprojection is False
        assert ch.notes == ""
        assert ch.endpoint == ""

    def test_descriptor_frozen(self):
        desc = SourceDescriptor(
            key="pl.gugik.nmt_1m",
            country="PL",
            product="nmt",
            name="NMT 1m",
            provider_name="GUGiK",
            channels=(self._channel(),),
            tile_scheme=None,
            storage_subdir="nmt/pl_{system}_1m_{vcrs}",
            default_extension=".asc",
            license=LicenseInfo(id="PL-PGiK-40a", attribution="GUGiK"),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            desc.key = "x"  # type: ignore[misc]
        assert desc.resolution is None
        assert desc.auth == "none"

    def test_tile_scheme_and_country_profile(self):
        ts = TileScheme(
            kind="computable",
            crs="EPSG:2180",
            width_m=2000.0,
            height_m=2000.0,
            description="test",
        )
        assert ts.kind == "computable"
        cp = CountryProfile(
            code="PL",
            name="Polska",
            extent_wgs84=BBox(14.07, 49.00, 24.20, 54.90, "EPSG:4326"),
            dataset_keys=("pl.gugik.nmt_1m",),
        )
        assert cp.extent_wgs84.crs == "EPSG:4326"


class TestRegistry:
    def test_all_keys_present(self):
        assert {d.key for d in sources_for()} == EXPECTED_KEYS

    def test_get_source_unknown_key_lists_available(self):
        with pytest.raises(KeyError) as exc:
            get_source("xx.none.zadne")
        assert "pl.gugik.nmt_1m" in str(exc.value)

    def test_sources_for_filters(self):
        pl = sources_for(country="PL")
        assert len(pl) == 6
        nmt = sources_for(country="PL", product="nmt")
        assert {d.key for d in nmt} == {"pl.gugik.nmt_1m", "pl.gugik.nmt_5m"}
        cz = sources_for(country="CZ")
        assert {d.key for d in cz} == {"cz.cuzk.dmr4g", "cz.cuzk.dmr5g"}

    def test_country_pl(self):
        pl = get_country("PL")
        assert pl.code == "PL"
        assert pl.extent_wgs84.crs == "EPSG:4326"
        assert set(pl.dataset_keys) == {k for k in EXPECTED_KEYS if k.startswith("pl.")}
        with pytest.raises(KeyError):
            get_country("XX")

    def test_vertical_crs_code(self):
        assert vertical_crs_code("KRON86") == "EPSG:9650"
        assert vertical_crs_code("EVRF2007") == "EPSG:5621"
        assert vertical_crs_code("EVRF2007-PL") == "EPSG:9651"
        assert vertical_crs_code("Bpv") == "EPSG:8357"
        assert vertical_crs_code("EPSG:9651") == "EPSG:9651"
        with pytest.raises(KeyError):
            vertical_crs_code("Kronsztad")

    def test_resolve_vertical_crs(self):
        # EVRF2007 family -> PL realization, when the channel offers it
        assert (
            resolve_vertical_crs("EVRF2007", ("EPSG:9650", "EPSG:9651")) == "EPSG:9651"
        )
        # CZ channel (Bpv) has no realization -> family code (transformation target)
        assert resolve_vertical_crs("EVRF2007", ("EPSG:8357",)) == "EPSG:5621"
        assert resolve_vertical_crs("Bpv", ("EPSG:8357",)) == "EPSG:8357"
        assert resolve_vertical_crs("KRON86", ("EPSG:9650", "EPSG:9651")) == "EPSG:9650"
        assert (
            resolve_vertical_crs("EVRF2007-PL", ("EPSG:9650", "EPSG:9651"))
            == "EPSG:9651"
        )

    def test_horizontal_crs_for_sheet(self):
        """N8: strefa PL-2000 z sheets; PL-1992 = EPSG:2180."""
        assert horizontal_crs_for_sheet("5.176.14") == "EPSG:2176"
        assert horizontal_crs_for_sheet("6.179.12.20") == "EPSG:2177"
        assert horizontal_crs_for_sheet("7.124.07.24") == "EPSG:2178"
        assert horizontal_crs_for_sheet("8.170.10") == "EPSG:2179"
        assert horizontal_crs_for_sheet("N-34-130-D-d-2-4") == "EPSG:2180"

    def test_horizontal_crs_for_system(self):
        """GUGiK CRS names (uklad_xy of a LAZ tile, index) -> EPSG code."""
        assert horizontal_crs_for_system("PL-2000:S6") == "EPSG:2177"
        assert horizontal_crs_for_system(" PL-2000:S8 ") == "EPSG:2179"
        assert horizontal_crs_for_system("PL-1992") == "EPSG:2180"
        assert horizontal_crs_for_system("PL-2000:S9") is None
        assert horizontal_crs_for_system("") is None
        assert horizontal_crs_for_system(None) is None

    def test_nmt_1m_entry_values(self):
        d = get_source("pl.gugik.nmt_1m")
        assert d.storage_subdir == "nmt/pl_{system}_1m_{vcrs}"
        assert d.default_extension == ".asc"
        assert d.resolution == "1m"
        transports = {ch.transport for ch in d.channels}
        assert transports == {TransportKind.WMS_SHEET_INDEX, TransportKind.WCS}

    def test_no_vertical_for_orto_and_landcover(self):
        for key in (
            "pl.gugik.orto",
            "pl.gugik.bdot10k",
            "eu.clms.corine",
            "global.isric.soilgrids",
        ):
            for ch in get_source(key).channels:
                assert ch.vertical_crs_options == ()

    def test_country_cz(self):
        cz = get_country("CZ")
        assert cz.code == "CZ"
        assert cz.extent_wgs84 == BBox(12.09, 48.55, 18.86, 51.06, "EPSG:4326")
        assert cz.dataset_keys == ("cz.cuzk.dmr4g", "cz.cuzk.dmr5g")

    def test_all_countries(self):
        codes = [c.code for c in all_countries()]
        assert codes == ["CZ", "PL"]

    def test_cz_dmr5g_entry_values(self):
        d = get_source("cz.cuzk.dmr5g")
        assert d.country == "CZ"
        assert d.product == "nmt"
        assert d.resolution == "2m"
        assert d.storage_subdir == "nmt/cz_dmr5g_{vcrs}"
        assert d.default_extension == ".tif"
        assert d.license.id == "CC-BY-4.0"
        assert len(d.channels) == 1
        ch = d.channels[0]
        assert ch.transport == TransportKind.ARCGIS_IMAGE
        assert ch.horizontal_crs == "EPSG:5514"
        assert ch.vertical_crs_options == ("EPSG:8357",)
        # ADR-024: exportImage only in native 5514, local reprojection
        assert ch.server_reprojection is False
        assert "ADR-024" in ch.notes
        assert ch.capabilities == frozenset({"bbox_raster"})
        assert ch.endpoint == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer"
        )
        assert d.tile_scheme.kind == "computable"
        assert d.tile_scheme.crs == "EPSG:3045"
        assert (d.tile_scheme.width_m, d.tile_scheme.height_m) == (2000.0, 2000.0)

    def test_cz_dmr4g_entry_values(self):
        d = get_source("cz.cuzk.dmr4g")
        assert d.resolution == "5m"
        assert d.storage_subdir == "nmt/cz_dmr4g_{vcrs}"
        transports = [ch.transport for ch in d.channels]
        assert transports == [TransportKind.DIRECT_FILES, TransportKind.ARCGIS_IMAGE]
        for ch in d.channels:
            assert ch.horizontal_crs == "EPSG:5514"
            assert ch.vertical_crs_options == ("EPSG:8357",)
        files_ch = d.channels[0]
        assert files_ch.capabilities == frozenset({"sheet_files"})
        assert files_ch.server_reprojection is False
        assert files_ch.endpoint == (
            "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/epsg-5514/{sheet}.zip"
        )
        image_ch = d.channels[1]
        assert image_ch.capabilities == frozenset({"bbox_raster"})
        # ADR-024: we do not trust the server imageSR - local reprojection
        assert image_ch.server_reprojection is False
        assert "ADR-024" in image_ch.notes
        assert image_ch.endpoint == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr4g/ImageServer"
        )
        assert d.tile_scheme.kind == "index"
        assert d.tile_scheme.crs == "EPSG:5514"
        assert (d.tile_scheme.width_m, d.tile_scheme.height_m) == (2500.0, 2000.0)


class TestDescriptorProviderConsistency:
    """Spec 6.12: the descriptor must agree with the provider's actual state."""

    def test_nmt_1m(self, tmp_path):
        from kartograf import FileStorage, GugikProvider

        d = get_source("pl.gugik.nmt_1m")
        provider = GugikProvider(resolution="1m", vertical_crs="EVRF2007")
        assert d.default_extension == provider.default_extension
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        assert d.resolve_subdir(vertical_crs="EVRF2007") == storage._subdir
        supported = provider.get_supported_vertical_crs_for_resolution("1m")
        # Compared per channel: the WMS index (skorowidz) and the WCS channel
        # declare the vertical CRS for which the provider has a working source.
        sheets_ch = next(
            ch for ch in d.channels if ch.transport == TransportKind.WMS_SHEET_INDEX
        )
        sheet_codes = {
            resolve_vertical_crs(n, sheets_ch.vertical_crs_options) for n in supported
        }
        assert set(sheets_ch.vertical_crs_options) == sheet_codes
        assert sheet_codes == {"EPSG:9650", "EPSG:9651"}

        wcs_ch = next(ch for ch in d.channels if ch.transport == TransportKind.WCS)
        wcs_supported = {
            n
            for n in supported
            if GugikProvider(resolution="1m", vertical_crs=n).is_wcs_available()
        }
        wcs_codes = {
            resolve_vertical_crs(n, wcs_ch.vertical_crs_options) for n in wcs_supported
        }
        assert set(wcs_ch.vertical_crs_options) == wcs_codes
        assert wcs_codes == {"EPSG:9650", "EPSG:9651"}

    def test_nmpt_wcs_channel_matches_provider(self):
        from kartograf import GugikNmptProvider

        d = get_source("pl.gugik.nmpt")
        wcs_ch = next(ch for ch in d.channels if ch.transport == TransportKind.WCS)
        assert wcs_ch.capabilities == frozenset({"bbox_raster"})
        wcs_codes = {
            resolve_vertical_crs(n, wcs_ch.vertical_crs_options)
            for n in ("KRON86", "EVRF2007")
            if GugikNmptProvider(vertical_crs=n).is_wcs_available()
        }
        assert set(wcs_ch.vertical_crs_options) == wcs_codes
        assert wcs_codes == {"EPSG:9650", "EPSG:9651"}

    def test_nmt_5m(self, tmp_path):
        from kartograf import FileStorage, GugikProvider

        d = get_source("pl.gugik.nmt_5m")
        provider = GugikProvider(resolution="5m", vertical_crs="EVRF2007")
        assert d.default_extension == provider.default_extension
        storage = FileStorage(tmp_path, resolution="5m", vertical_crs="EVRF2007")
        assert d.resolve_subdir(vertical_crs="EVRF2007") == storage._subdir
        supported = provider.get_supported_vertical_crs_for_resolution("5m")
        assert {
            resolve_vertical_crs(n, d.channels[0].vertical_crs_options)
            for n in supported
        } == set(d.channels[0].vertical_crs_options)

    def test_nmpt(self, tmp_path):
        from kartograf import FileStorage, GugikNmptProvider

        d = get_source("pl.gugik.nmpt")
        provider = GugikNmptProvider(vertical_crs="EVRF2007")
        assert d.default_extension == provider.default_extension
        storage = FileStorage(
            tmp_path, resolution="1m", vertical_crs="EVRF2007", product="nmpt"
        )
        assert d.resolve_subdir(vertical_crs="EVRF2007") == storage._subdir
        codes = {
            resolve_vertical_crs(n, d.channels[0].vertical_crs_options)
            for n in provider.SUPPORTED_VERTICAL_CRS
        }
        assert set(d.channels[0].vertical_crs_options) == codes

    def test_orto(self, tmp_path):
        from kartograf import FileStorage, GugikOrtoProvider

        d = get_source("pl.gugik.orto")
        provider = GugikOrtoProvider(color="RGB")
        assert d.default_extension == provider.default_extension
        assert (
            d.resolve_subdir()
            == FileStorage(
                tmp_path, resolution=None, vertical_crs=None, product="orto"
            )._subdir
        )
        assert d.channels[0].vertical_crs_options == ()

    def test_laz(self, tmp_path):
        from kartograf import FileStorage, GugikLazProvider

        d = get_source("pl.gugik.laz")
        provider = GugikLazProvider(vertical_crs="EVRF2007")
        assert d.default_extension == provider.default_extension
        storage = FileStorage(
            tmp_path, resolution=None, vertical_crs="EVRF2007", product="laz"
        )
        assert d.resolve_subdir(vertical_crs="EVRF2007") == storage._subdir
        codes = {
            resolve_vertical_crs(n, d.channels[0].vertical_crs_options)
            for n in provider.SUPPORTED_VERTICAL_CRS
        }
        assert set(d.channels[0].vertical_crs_options) == codes

    def test_landcover_and_soil(self):
        from kartograf import Bdot10kProvider, CorineProvider, SoilGridsProvider

        cases = [
            ("pl.gugik.bdot10k", Bdot10kProvider(), "GPKG"),
            ("eu.clms.corine", CorineProvider(use_proxy=False), "GTiff"),
            ("global.isric.soilgrids", SoilGridsProvider(), "GTiff"),
        ]
        for key, provider, fmt in cases:
            d = get_source(key)
            assert d.default_extension == provider.get_file_extension(fmt)
            assert d.provider_name != ""
            assert d.license.attribution != ""

    def test_landcover_storage_prefixes(self):
        """Spec 3.4: land cover segments = prefix + content tokens, no placeholders."""
        assert {
            key: get_source(key).storage_subdir
            for key in ("pl.gugik.bdot10k", "eu.clms.corine", "global.isric.soilgrids")
        } == {
            "pl.gugik.bdot10k": "landcover/pl_bdot10k",
            "eu.clms.corine": "landcover/eu_corine",
            "global.isric.soilgrids": "soil/global_soilgrids",
        }

    def test_horizontal_crs_matches_channel_reality(self):
        """Descriptor horizontal CRS = the CRS the channel actually returns."""
        for key in (
            "pl.gugik.nmt_1m",
            "pl.gugik.nmt_5m",
            "pl.gugik.nmpt",
            "pl.gugik.orto",
            "pl.gugik.laz",
            "pl.gugik.bdot10k",
        ):
            for ch in get_source(key).channels:
                assert ch.horizontal_crs == "EPSG:2180", key
        # CORINE: EPSG:3035 applies to the CLMS GeoTIFF channel (the WMS PNG fallback
        # has a different CRS and is corrected in LandCoverManager._write_sidecar)
        assert get_source("eu.clms.corine").channels[0].horizontal_crs == "EPSG:3035"
        assert (
            get_source("global.isric.soilgrids").channels[0].horizontal_crs
            == "EPSG:4326"
        )

    def test_descriptor_keys_bound(self):
        from kartograf import (
            Bdot10kProvider,
            CorineProvider,
            GugikLazProvider,
            GugikNmptProvider,
            GugikOrtoProvider,
            GugikProvider,
            SoilGridsProvider,
        )

        expected = {
            GugikProvider(resolution="1m", vertical_crs="EVRF2007"): "pl.gugik.nmt_1m",
            GugikProvider(resolution="5m", vertical_crs="EVRF2007"): "pl.gugik.nmt_5m",
            GugikNmptProvider(vertical_crs="EVRF2007"): "pl.gugik.nmpt",
            GugikOrtoProvider(color="RGB"): "pl.gugik.orto",
            GugikLazProvider(vertical_crs="EVRF2007"): "pl.gugik.laz",
            Bdot10kProvider(): "pl.gugik.bdot10k",
            CorineProvider(use_proxy=False): "eu.clms.corine",
            SoilGridsProvider(): "global.isric.soilgrids",
        }
        for provider, key in expected.items():
            assert provider.descriptor_key == key
            get_source(key)  # the key exists in the registry


class TestResolveSubdir:
    """ADR-026: storage_subdir is a template; resolve_subdir fills it in."""

    def _descriptor(self, subdir):
        from kartograf.sources.descriptor import (
            AccessChannel,
            LicenseInfo,
            SourceDescriptor,
            TransportKind,
        )

        return SourceDescriptor(
            key="test.key",
            country="PL",
            product="nmt",
            name="Test",
            provider_name="Test",
            channels=(
                AccessChannel(transport=TransportKind.WCS, horizontal_crs="EPSG:2180"),
            ),
            tile_scheme=None,
            storage_subdir=subdir,
            default_extension=".asc",
            license=LicenseInfo(id="X", attribution="X"),
        )

    def test_full_fill(self):
        d = self._descriptor("nmt/pl_{system}_1m_{vcrs}")
        assert (
            d.resolve_subdir(system="1992", vertical_crs="EVRF2007")
            == "nmt/pl_1992_1m_evrf2007"
        )

    def test_partial_fill_leaves_system(self):
        d = self._descriptor("nmt/pl_{system}_1m_{vcrs}")
        assert d.resolve_subdir(vertical_crs="KRON86") == "nmt/pl_{system}_1m_kron86"

    def test_vcrs_lowercased(self):
        d = self._descriptor("nmt/cz_dmr5g_{vcrs}")
        assert d.resolve_subdir(vertical_crs="Bpv") == "nmt/cz_dmr5g_bpv"

    def test_unknown_dimension_is_noop(self):
        """Ortho has no {vcrs} - passing vertical_crs breaks nothing."""
        d = self._descriptor("orto/pl_{system}")
        assert (
            d.resolve_subdir(system="1992", vertical_crs="EVRF2007") == "orto/pl_1992"
        )

    def test_no_args_returns_template(self):
        d = self._descriptor("laz/pl_{system}_{vcrs}")
        assert d.resolve_subdir() == "laz/pl_{system}_{vcrs}"

    @pytest.mark.parametrize(
        "kwargs", [{"vertical_crs": ""}, {"vertical_crs": "  "}, {"system": ""}]
    )
    def test_empty_dimension_raises(self, kwargs):
        """Finding 7: an empty string is a caller error, not a missing dimension - so
        far it gave a silent segment `nmt/pl_{system}_1m_` (FileStorage closes the
        same trap with a falsy check)."""
        from kartograf.exceptions import ValidationError

        d = self._descriptor("nmt/pl_{system}_1m_{vcrs}")
        with pytest.raises(ValidationError, match="Pusty wymiar"):
            d.resolve_subdir(**kwargs)
