"""Tests of source descriptors and the registry (kartograf.sources).

PL NMT/NMPT sheets: one descriptor per (product, format, resolution) of the
variant registry (ADR-041), sheet records from the GUGiK WFS index.
"""

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
from kartograf.sources.variants import ProductVariant, variants

# Sidecar `dataset` keys of the PL NMT/NMPT sheet sources (ADR-041): ASC grids
# (`pl.gugik.nmt_1m`, `pl.gugik.nmt_5m` and `pl.gugik.nmpt` = NMPT 1 m keep the
# keys of existing sidecars) and archives downloaded as source files.
PL_GRID_KEYS = (
    "pl.gugik.nmt_0_15m",
    "pl.gugik.nmt_0_5m",
    "pl.gugik.nmt_0_6m",
    "pl.gugik.nmt_1m",
    "pl.gugik.nmt_5m",
    "pl.gugik.nmt_10m",
    "pl.gugik.nmpt_0_5m",
    "pl.gugik.nmpt_0_6m",
    "pl.gugik.nmpt",
)
PL_ARCHIVE_KEYS = (
    "pl.gugik.nmt_xyz_1m",
    "pl.gugik.nmt_xyz_5m",
    "pl.gugik.nmt_ascii_nmt_0_5m",
    "pl.gugik.nmt_ascii_nmt_1m",
    "pl.gugik.nmt_ascii_nmt_5m",
    "pl.gugik.nmt_tbd_1m",
    "pl.gugik.nmt_tbd_5m",
    "pl.gugik.nmt_tbd_10m",
    "pl.gugik.nmt_tbd_15m",
    "pl.gugik.nmt_tbd_20m",
    "pl.gugik.nmt_tbd_25m",
    "pl.gugik.nmt_tbd_30m",
    "pl.gugik.nmt_tbd_40m",
    "pl.gugik.nmt_tbd_50m",
    "pl.gugik.nmt_tin",
    "pl.gugik.nmt_ttn",
    "pl.gugik.nmt_grd_5m",
    "pl.gugik.nmt_dxf_25m",
    "pl.gugik.nmt_dgn_25m",
    "pl.gugik.nmpt_xyz_0_5m",
    "pl.gugik.nmpt_xyz_1m",
)
PL_SHEET_KEYS = PL_GRID_KEYS + PL_ARCHIVE_KEYS
# Grids with a WCS cutout channel (1 m only)
PL_WCS_KEYS = ("pl.gugik.nmt_1m", "pl.gugik.nmpt")

EXPECTED_KEYS = {
    *PL_SHEET_KEYS,
    "pl.gugik.orto",
    "pl.gugik.laz",
    "pl.gugik.bdot10k",
    "eu.clms.corine",
    "global.isric.soilgrids",
    "cz.cuzk.dmr5g",
    "cz.cuzk.dmr4g",
}

# Signal inventory (docs/research/2026-10-12-signal-inventory/raport.md;
# NMT/NMPT sheets: WFS index since ADR-041, a new index record = new data).
CHANNEL_SIGNALS = [
    *((key, TransportKind.WFS, "index") for key in PL_SHEET_KEYS),
    *((key, TransportKind.WCS, "none") for key in PL_WCS_KEYS),
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

PL_VARIANTS = variants(country="PL")


def _variant_id(v: ProductVariant) -> str:
    return f"{v.product}-{v.format}-{v.label}-{v.vertical_crs}"


def _provider_for(variant: ProductVariant):
    """The provider a CLI/API choice of ``variant`` builds."""
    from kartograf import GugikLazProvider, GugikNmptProvider, GugikProvider

    if variant.product == "laz":
        return GugikLazProvider(vertical_crs=variant.vertical_crs)
    cls = GugikNmptProvider if variant.product == "nmpt" else GugikProvider
    return cls(
        vertical_crs=variant.vertical_crs,
        resolution=variant.label,
        format=variant.format,
    )


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
        assert {d.key for d in pl} == {k for k in EXPECTED_KEYS if k.startswith("pl.")}
        nmt = sources_for(country="PL", product="nmt")
        assert {d.key for d in nmt} == {
            k for k in PL_SHEET_KEYS if k.startswith("pl.gugik.nmt_")
        }
        nmpt = sources_for(country="PL", product="nmpt")
        assert {d.key for d in nmpt} == {
            k for k in PL_SHEET_KEYS if k.startswith("pl.gugik.nmpt")
        }
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

    @pytest.mark.parametrize(
        ("key", "segment", "extension"),
        [
            # segments of existing data stay unchanged
            ("pl.gugik.nmt_1m", "nmt/pl_{system}_1m_{vcrs}", ".asc"),
            ("pl.gugik.nmt_5m", "nmt/pl_{system}_5m_{vcrs}", ".asc"),
            ("pl.gugik.nmpt", "nmpt/pl_{system}_1m_{vcrs}", ".asc"),
            # new grids: label K2 in the segment
            ("pl.gugik.nmt_0_15m", "nmt/pl_{system}_0.15m_{vcrs}", ".asc"),
            ("pl.gugik.nmt_0_5m", "nmt/pl_{system}_0.5m_{vcrs}", ".asc"),
            ("pl.gugik.nmt_10m", "nmt/pl_{system}_10m_{vcrs}", ".asc"),
            ("pl.gugik.nmpt_0_6m", "nmpt/pl_{system}_0.6m_{vcrs}", ".asc"),
            # archives: format token before the label, extension from the format
            ("pl.gugik.nmt_xyz_1m", "nmt/pl_{system}_xyz_1m_{vcrs}", ".zip"),
            ("pl.gugik.nmt_tbd_25m", "nmt/pl_{system}_tbd_25m_{vcrs}", ".zip"),
            (
                "pl.gugik.nmt_ascii_nmt_5m",
                "nmt/pl_{system}_ascii-nmt_5m_{vcrs}",
                ".zip",
            ),
            ("pl.gugik.nmt_tin", "nmt/pl_{system}_tin_{vcrs}", ".zip"),
            ("pl.gugik.nmt_ttn", "nmt/pl_{system}_ttn_{vcrs}", ".ttn"),
            ("pl.gugik.nmt_grd_5m", "nmt/pl_{system}_grd_5m_{vcrs}", ".grd"),
            ("pl.gugik.nmt_dxf_25m", "nmt/pl_{system}_dxf_25m_{vcrs}", ".dxf"),
            ("pl.gugik.nmt_dgn_25m", "nmt/pl_{system}_dgn_25m_{vcrs}", ".dgn"),
            ("pl.gugik.nmpt_xyz_0_5m", "nmpt/pl_{system}_xyz_0.5m_{vcrs}", ".zip"),
        ],
    )
    def test_pl_sheet_segments(self, key, segment, extension):
        d = get_source(key)
        assert d.storage_subdir == segment
        assert d.default_extension == extension

    @pytest.mark.parametrize("key", PL_SHEET_KEYS)
    def test_pl_sheet_channel_capabilities(self, key):
        """Sheet files from the WFS index; the WCS channel (1 m) serves bboxes."""
        capabilities = {
            ch.transport: ch.capabilities for ch in get_source(key).channels
        }
        assert capabilities[TransportKind.WFS] == frozenset({"sheet_files"})
        if key in PL_WCS_KEYS:
            assert capabilities[TransportKind.WCS] == frozenset({"bbox_raster"})

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

    @pytest.mark.parametrize("variant", PL_VARIANTS, ids=_variant_id)
    def test_variant_matches_provider(self, variant, tmp_path):
        """Segment, extension and channels of a variant agree with the provider
        built from that variant (CLI/API choice -> files of the descriptor)."""
        from kartograf import FileStorage
        from kartograf.download.storage import storage_for_provider

        d = get_source(variant.source)
        provider = _provider_for(variant)
        assert provider.descriptor_key == variant.source
        assert provider.default_extension == d.default_extension

        segment = d.resolve_subdir(vertical_crs=variant.vertical_crs)
        storage = storage_for_provider(
            tmp_path,
            provider,
            resolution=variant.label,
            vertical_crs=variant.vertical_crs,
        )
        assert storage._subdir == segment
        # the store opened for the same choice without a provider: same segment
        assert (
            FileStorage(
                tmp_path,
                resolution=variant.label,
                vertical_crs=variant.vertical_crs,
                product=variant.product,
                format=variant.format,
            )._subdir
            == segment
        )
        assert segment.endswith(f"_{variant.vertical_crs.lower()}")
        if variant.label is not None:
            assert f"_{variant.label}_" in segment

        if variant.product != "laz":
            has_wcs = any(ch.transport == TransportKind.WCS for ch in d.channels)
            assert provider.has_wcs() is has_wcs
            assert provider.is_wcs_available() is has_wcs

    @pytest.mark.parametrize("key", (*PL_SHEET_KEYS, "pl.gugik.laz"))
    def test_channel_vertical_crs_matches_providers(self, key):
        """Each channel declares exactly the height systems for which the
        provider of a variant has a working source (WCS: is_wcs_available)."""
        d = get_source(key)
        assert d.variants
        for ch in d.channels:
            working = [
                v
                for v in d.variants
                if ch.transport != TransportKind.WCS
                or _provider_for(v).is_wcs_available()
            ]
            codes = {
                resolve_vertical_crs(v.vertical_crs, ch.vertical_crs_options)
                for v in working
            }
            assert set(ch.vertical_crs_options) == codes, (key, ch.transport)

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
        for d in sources_for(country="PL"):
            for ch in d.channels:
                assert ch.horizontal_crs == "EPSG:2180", d.key
        # CORINE: EPSG:3035 is the CLMS GeoTIFF channel; the WMS preview channel
        # is EPSG:3857 (1990 DLR: EPSG:4326, set by LandCoverManager per file)
        assert get_source("eu.clms.corine").channels[0].horizontal_crs == "EPSG:3035"
        assert get_source("eu.clms.corine").channels[1].horizontal_crs == "EPSG:3857"
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
            # keys of existing sidecars stay (NMPT 1 m = `pl.gugik.nmpt`)
            GugikProvider(resolution="1m", vertical_crs="EVRF2007"): "pl.gugik.nmt_1m",
            GugikProvider(resolution="5m", vertical_crs="EVRF2007"): "pl.gugik.nmt_5m",
            GugikNmptProvider(
                resolution="1m", vertical_crs="EVRF2007"
            ): "pl.gugik.nmpt",
            GugikProvider(resolution="0.5m", vertical_crs="KRON86"): (
                "pl.gugik.nmt_0_5m"
            ),
            GugikNmptProvider(resolution="0.5m", vertical_crs="EVRF2007"): (
                "pl.gugik.nmpt_0_5m"
            ),
            GugikProvider(resolution="25m", vertical_crs="KRON86", format="TBD"): (
                "pl.gugik.nmt_tbd_25m"
            ),
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
