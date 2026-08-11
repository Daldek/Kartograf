"""Testy deskryptorow i rejestru zrodel (kartograf.sources)."""

import dataclasses

import pytest

from kartograf.core.sheet_parser import BBox
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
    get_country,
    get_source,
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
            storage_subdir="nmt_1m",
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
        # rodzina EVRF2007 -> realizacja PL, gdy kanal ja oferuje
        assert (
            resolve_vertical_crs("EVRF2007", ("EPSG:9650", "EPSG:9651")) == "EPSG:9651"
        )
        # kanal CZ (Bpv) nie ma realizacji -> kod rodziny (cel transformacji)
        assert resolve_vertical_crs("EVRF2007", ("EPSG:8357",)) == "EPSG:5621"
        assert resolve_vertical_crs("Bpv", ("EPSG:8357",)) == "EPSG:8357"
        assert resolve_vertical_crs("KRON86", ("EPSG:9650", "EPSG:9651")) == "EPSG:9650"
        assert (
            resolve_vertical_crs("EVRF2007-PL", ("EPSG:9650", "EPSG:9651"))
            == "EPSG:9651"
        )

    def test_nmt_1m_entry_values(self):
        d = get_source("pl.gugik.nmt_1m")
        assert d.storage_subdir == "nmt_1m"
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
        assert d.storage_subdir == "cz_dmr5g"
        assert d.default_extension == ".tif"
        assert d.license.id == "CC-BY-4.0"
        assert len(d.channels) == 1
        ch = d.channels[0]
        assert ch.transport == TransportKind.ARCGIS_IMAGE
        assert ch.horizontal_crs == "EPSG:5514"
        assert ch.vertical_crs_options == ("EPSG:8357",)
        assert ch.server_reprojection is True
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
        assert d.storage_subdir == "cz_dmr4g"
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
        assert image_ch.server_reprojection is True
        assert image_ch.endpoint == (
            "https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr4g/ImageServer"
        )
        assert d.tile_scheme.kind == "index"
        assert d.tile_scheme.crs == "EPSG:5514"
        assert (d.tile_scheme.width_m, d.tile_scheme.height_m) == (2500.0, 2000.0)


class TestDescriptorProviderConsistency:
    """Spec 6.12: deskryptor musi zgadzac sie ze stanem faktycznym providera."""

    def test_nmt_1m(self, tmp_path):
        from kartograf import FileStorage, GugikProvider

        d = get_source("pl.gugik.nmt_1m")
        provider = GugikProvider(resolution="1m")
        assert d.default_extension == provider.default_extension
        storage = FileStorage(tmp_path, resolution="1m")
        assert d.storage_subdir == storage._subdir
        supported = provider.get_supported_vertical_crs_for_resolution("1m")
        for ch in d.channels:
            codes = {
                resolve_vertical_crs(n, ch.vertical_crs_options) for n in supported
            }
            assert set(ch.vertical_crs_options) == codes

    def test_nmt_5m(self, tmp_path):
        from kartograf import FileStorage, GugikProvider

        d = get_source("pl.gugik.nmt_5m")
        provider = GugikProvider(resolution="5m")
        assert d.default_extension == provider.default_extension
        storage = FileStorage(tmp_path, resolution="5m")
        assert d.storage_subdir == storage._subdir
        supported = provider.get_supported_vertical_crs_for_resolution("5m")
        assert {
            resolve_vertical_crs(n, d.channels[0].vertical_crs_options)
            for n in supported
        } == set(d.channels[0].vertical_crs_options)

    def test_nmpt(self, tmp_path):
        from kartograf import FileStorage, GugikNmptProvider

        d = get_source("pl.gugik.nmpt")
        provider = GugikNmptProvider()
        assert d.default_extension == provider.default_extension
        assert d.storage_subdir == FileStorage(tmp_path, product="nmpt")._subdir
        codes = {
            resolve_vertical_crs(n, d.channels[0].vertical_crs_options)
            for n in provider.SUPPORTED_VERTICAL_CRS
        }
        assert set(d.channels[0].vertical_crs_options) == codes

    def test_orto(self, tmp_path):
        from kartograf import FileStorage, GugikOrtoProvider

        d = get_source("pl.gugik.orto")
        provider = GugikOrtoProvider()
        assert d.default_extension == provider.default_extension
        assert d.storage_subdir == FileStorage(tmp_path, product="orto")._subdir
        assert d.channels[0].vertical_crs_options == ()

    def test_laz(self, tmp_path):
        from kartograf import FileStorage, GugikLazProvider

        d = get_source("pl.gugik.laz")
        provider = GugikLazProvider()
        assert d.default_extension == provider.default_extension
        assert d.storage_subdir == FileStorage(tmp_path, product="laz")._subdir
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
            assert d.storage_subdir is None
            assert d.default_extension == provider.get_file_extension(fmt)
            assert d.provider_name != ""
            assert d.license.attribution != ""

    def test_horizontal_crs_matches_channel_reality(self):
        """CRS poziomy deskryptora = CRS faktycznie zwracany przez dany kanal."""
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
        # CORINE: EPSG:3035 dotyczy kanalu CLMS GeoTIFF (fallback PNG z WMS ma
        # inny CRS i jest korygowany w LandCoverManager._write_sidecar)
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
            GugikProvider(resolution="1m"): "pl.gugik.nmt_1m",
            GugikProvider(resolution="5m"): "pl.gugik.nmt_5m",
            GugikNmptProvider(): "pl.gugik.nmpt",
            GugikOrtoProvider(): "pl.gugik.orto",
            GugikLazProvider(): "pl.gugik.laz",
            Bdot10kProvider(): "pl.gugik.bdot10k",
            CorineProvider(use_proxy=False): "eu.clms.corine",
            SoilGridsProvider(): "global.isric.soilgrids",
        }
        for provider, key in expected.items():
            assert provider.descriptor_key == key
            get_source(key)  # klucz istnieje w rejestrze
