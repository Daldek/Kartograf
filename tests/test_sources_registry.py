"""Tests of source descriptors and the registry (kartograf.sources).

PL NMT/NMPT sheets: one descriptor per (product, format, resolution) of the
variant registry (ADR-041), sheet records from the GUGiK WFS index.
"""

import dataclasses
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.download.collections import _capability
from kartograf.exceptions import ValidationError
from kartograf.sources.descriptor import (
    PACKAGE_URL_TOKENS,
    AccessChannel,
    AtomFilesParams,
    CountryProfile,
    FeatureBBoxParams,
    LicenseInfo,
    SourceDescriptor,
    TileScheme,
    TransportKind,
    UnitPackageParams,
    WcsCutoutParams,
)
from kartograf.sources.registry import (
    all_countries,
    channel_for,
    channel_signal,
    get_country,
    get_source,
    horizontal_crs_for_sheet,
    horizontal_crs_for_system,
    resolve_vertical_crs,
    sources_for,
    vertical_crs_code,
)
from kartograf.sources.sidecar import _select_channel_by_capability
from kartograf.sources.variants import ProductVariant, resolution_label, variants

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
    "pl.gugik.nmt_ascii_nmt_10m",
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

# CUZK sources (plan B): rasters of four models and the LAZ of each model.
CZ_MODEL_KEYS = ("dmr5g", "dmr4g", "dmp1g", "dmpok")
CZ_KEYS = (
    *(f"cz.cuzk.{model}" for model in CZ_MODEL_KEYS),
    *(f"cz.cuzk.{model}_laz" for model in CZ_MODEL_KEYS),
)
# key -> (product, resolution, openzu directory, ImageServer service); the
# recorded publication of 2026-10-15 (tests/fixtures/cuzk/real_2026_10_15)
_CZ_PUBLICATION = {
    "cz.cuzk.dmr5g": ("nmt", "2m", None, "dmr5g"),
    "cz.cuzk.dmr4g": ("nmt", "5m", "DMR4G-TIFF", "dmr4g"),
    "cz.cuzk.dmp1g": ("nmpt", "2m", None, "dmp1g"),
    "cz.cuzk.dmpok": ("nmpt", "0.5m", "DMPOK-TIFF", "dmp_obrazova_korelace"),
    "cz.cuzk.dmr5g_laz": ("laz", None, "DMR5G", None),
    "cz.cuzk.dmr4g_laz": ("laz", None, "DMR4G", None),
    "cz.cuzk.dmp1g_laz": ("laz", None, "DMP1G", None),
    "cz.cuzk.dmpok_laz": ("laz", None, "DMPOK-LAZ", None),
}
_CUZK_FIXTURES = Path(__file__).parent / "fixtures" / "cuzk" / "real_2026_10_15"
_OPENZU_HEAD = {
    response["url"]: response["status"]
    for response in json.loads((_CUZK_FIXTURES / "openzu_head.json").read_text())[
        "responses"
    ]
}

EXPECTED_KEYS = {
    *PL_SHEET_KEYS,
    "pl.gugik.orto",
    "pl.gugik.laz",
    "pl.gugik.bdot10k",
    "eu.clms.corine",
    "global.isric.soilgrids",
    *CZ_KEYS,
    "pl.gugik.prg",
    "pl.gugik.egib",
    "pl.gugik.buildings_3d",
    "cz.cuzk.zabaged",
    "cz.cuzk.ruian",
    "cz.cuzk.hy_net",
    "cz.cuzk.ortofoto",
}

# Signal inventory (docs/research/2026-10-12-signal-inventory/raport.md;
# NMT/NMPT sheets: WFS index since ADR-041, a new index record = new data).
CHANNEL_SIGNALS = [
    *((key, TransportKind.WFS, "index") for key in PL_SHEET_KEYS),
    *((key, TransportKind.WCS, "none") for key in PL_WCS_KEYS),
    ("pl.gugik.orto", TransportKind.WMS_SHEET_INDEX, "index"),
    ("pl.gugik.orto", TransportKind.WCS, "none"),
    ("pl.gugik.laz", TransportKind.WFS, "index"),
    ("pl.gugik.bdot10k", TransportKind.DIRECT_FILES, "none"),
    ("eu.clms.corine", TransportKind.CLMS_API, "metadata"),
    ("eu.clms.corine", TransportKind.WMS, "none"),
    ("global.isric.soilgrids", TransportKind.WCS, "metadata"),
    ("cz.cuzk.dmr5g", TransportKind.ARCGIS_IMAGE, "none"),
    ("cz.cuzk.dmr4g", TransportKind.DIRECT_FILES, "http"),
    ("cz.cuzk.dmr4g", TransportKind.ARCGIS_IMAGE, "none"),
    ("cz.cuzk.dmp1g", TransportKind.ARCGIS_IMAGE, "none"),
    ("cz.cuzk.dmpok", TransportKind.DIRECT_FILES, "http"),
    ("cz.cuzk.dmpok", TransportKind.ARCGIS_IMAGE, "none"),
    *(
        (f"cz.cuzk.{model}_laz", TransportKind.DIRECT_FILES, "http")
        for model in CZ_MODEL_KEYS
    ),
    ("pl.gugik.prg", TransportKind.WFS, "none"),
    ("pl.gugik.prg", TransportKind.DIRECT_FILES, "none"),
    ("pl.gugik.egib", TransportKind.DIRECT_FILES, "none"),
    ("pl.gugik.egib", TransportKind.WFS, "none"),
    ("pl.gugik.buildings_3d", TransportKind.DIRECT_FILES, "none"),
    ("cz.cuzk.zabaged", TransportKind.ARCGIS_QUERY, "none"),
    ("cz.cuzk.zabaged", TransportKind.DIRECT_FILES, "metadata"),
    ("cz.cuzk.ruian", TransportKind.ARCGIS_QUERY, "none"),
    ("cz.cuzk.ruian", TransportKind.DIRECT_FILES, "http"),
    ("cz.cuzk.hy_net", TransportKind.WFS, "none"),
    ("cz.cuzk.hy_net", TransportKind.DIRECT_FILES, "http"),
    ("cz.cuzk.ortofoto", TransportKind.DIRECT_FILES, "metadata"),
]

# Collection channels (ADR-042 D6) by their capability - a descriptor may have
# several channels of one transport (BDOT10k: current packages + archive).
COLLECTION_CHANNEL_SIGNALS = [
    ("pl.gugik.bdot10k", "archive_unit_files", "none"),
    ("pl.gugik.prg", "bbox_vector", "none"),
    ("pl.gugik.prg", "admin_unit_files", "none"),
    ("pl.gugik.prg", "country_files", "none"),
    ("pl.gugik.egib", "admin_unit_files", "none"),
    ("pl.gugik.egib", "bbox_vector", "none"),
    ("pl.gugik.buildings_3d", "admin_unit_files", "none"),
    ("cz.cuzk.zabaged", "bbox_vector", "none"),
    ("cz.cuzk.zabaged", "country_files", "metadata"),
    ("cz.cuzk.ruian", "bbox_vector", "none"),
    ("cz.cuzk.ruian", "country_files", "http"),
    ("cz.cuzk.hy_net", "bbox_vector", "none"),
    ("cz.cuzk.hy_net", "country_files", "http"),
    ("cz.cuzk.ortofoto", "sheet_files", "metadata"),
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


def _collection_channels():
    """Channels of the collection engines (the WCS cutout channels of the
    orthophotomap carry provider configuration, ADR-042 D14)."""
    return [
        (d, ch)
        for d in sources_for()
        for ch in d.channels
        if ch.params is not None and not isinstance(ch.params, WcsCutoutParams)
    ]


def _sidecar_crs(channel: AccessChannel) -> tuple:
    """CRSs a collection file sidecar takes from its channel: the horizontal
    CRS of the file (native CRS of a feature service) and the vertical one."""
    params = channel.params
    horizontal = (
        params.native_crs
        if isinstance(params, FeatureBBoxParams)
        else channel.horizontal_crs
    )
    return horizontal, channel.vertical_crs_options, channel.vertical_source


def test_collection_channel_signals_match_inventory():
    found = {
        (d.key, capability, ch.update_signal)
        for d, ch in _collection_channels()
        for capability in ch.capabilities
    }
    assert found == set(COLLECTION_CHANNEL_SIGNALS)


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
        assert {d.key for d in cz} == {k for k in EXPECTED_KEYS if k.startswith("cz.")}
        assert {d.key for d in sources_for(country="CZ", product="nmpt")} == {
            "cz.cuzk.dmp1g",
            "cz.cuzk.dmpok",
        }

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
            "cz.cuzk.ortofoto",
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
        assert cz.dataset_keys == tuple(
            sorted(k for k in EXPECTED_KEYS if k.startswith("cz."))
        )

    def test_all_countries(self):
        codes = [c.code for c in all_countries()]
        assert codes == ["CZ", "PL"]

    @pytest.mark.parametrize("key", CZ_KEYS)
    def test_cz_entry_matches_publication(self, key):
        """Endpoints, CRSs and signals of the CUZK channels = the recorded
        publication (openzu HEAD, ImageServer metadata, 2026-10-15)."""
        product, resolution, files, service = _CZ_PUBLICATION[key]
        d = get_source(key)
        model = key.removeprefix("cz.cuzk.").removesuffix("_laz")
        assert (d.country, d.product, d.resolution) == ("CZ", product, resolution)
        assert d.storage_subdir == f"{product}/cz_{model}_{{vcrs}}"
        assert d.default_extension == (".laz" if product == "laz" else ".tif")
        assert d.license.id == "CC-BY-4.0"
        expected = set()
        if files is not None:
            for epsg, vertical, sheet in (
                ("5514", "EPSG:8357", "CTES96"),
                ("3045", "EPSG:5621", "760_5518"),
            ):
                ch = channel_for(key, TransportKind.DIRECT_FILES, f"EPSG:{epsg}")
                url = f"https://openzu.cuzk.gov.cz/opendata/{files}/epsg-{epsg}/"
                assert ch.endpoint == url + "{sheet}.zip"
                assert _OPENZU_HEAD[ch.endpoint.format(sheet=sheet)] == 200
                assert ch.vertical_crs_options == (vertical,)
                assert (ch.update_signal, ch.capabilities) == (
                    "http",
                    frozenset({"sheet_files"}),
                )
                expected.add((TransportKind.DIRECT_FILES, f"EPSG:{epsg}"))
        if service is not None:
            ch = channel_for(key, TransportKind.ARCGIS_IMAGE)
            assert ch.endpoint == (
                f"https://ags.cuzk.gov.cz/arcgis2/rest/services/{service}/ImageServer"
            )
            # ADR-024: requests only in the native EPSG:5514 + Bpv of the service
            assert (ch.horizontal_crs, ch.vertical_crs_options) == (
                "EPSG:5514",
                ("EPSG:8357",),
            )
            assert ch.server_reprojection is False and "ADR-024" in ch.notes
            assert (ch.update_signal, ch.capabilities) == (
                "none",
                frozenset({"bbox_raster"}),
            )
            published = json.loads(
                (_CUZK_FIXTURES / f"imageserver_{service}.json").read_text()
            )
            pixel = resolution_label(Decimal(str(published["pixelSizeX"])))
            assert pixel == resolution
            assert published["spatialReference"]["latestWkid"] == 5514
            assert published["spatialReference"]["vcsWkid"] == 8357
            expected.add((TransportKind.ARCGIS_IMAGE, "EPSG:5514"))
        assert {(c.transport, c.horizontal_crs) for c in d.channels} == expected

    @pytest.mark.parametrize("directory", ["DMR5G-TIFF", "DMP1G-TIFF"])
    def test_cz_models_without_raster_files(self, directory):
        """DMR 5G and DMP 1G have no raster files (404): ImageServer only."""
        for url, status in _OPENZU_HEAD.items():
            if f"/opendata/{directory}/" in url:
                assert status == 404
        endpoints = {c.endpoint for d in sources_for(country="CZ") for c in d.channels}
        assert not any(directory in endpoint for endpoint in endpoints)

    def test_channel_for_by_crs(self):
        files = "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF"
        key = "cz.cuzk.dmr4g"
        tm33 = channel_for(key, TransportKind.DIRECT_FILES, "EPSG:3045")
        assert tm33.endpoint == f"{files}/epsg-3045/{{sheet}}.zip"
        sm5 = channel_for(key, TransportKind.DIRECT_FILES, "EPSG:5514")
        assert sm5.endpoint == f"{files}/epsg-5514/{{sheet}}.zip"
        assert channel_for(key, TransportKind.ARCGIS_IMAGE).endpoint.endswith(
            "/dmr4g/ImageServer"
        )
        # two file channels: the CRS chooses; none in a CRS: error
        with pytest.raises(ValidationError, match="kilka kanalow"):
            channel_for(key, TransportKind.DIRECT_FILES)
        with pytest.raises(ValidationError, match="nie ma kanalu"):
            channel_for(key, TransportKind.DIRECT_FILES, "EPSG:2180")
        with pytest.raises(ValidationError, match="nie ma kanalu"):
            channel_for("cz.cuzk.dmr5g", TransportKind.DIRECT_FILES, "EPSG:5514")

    def test_channel_signal_by_crs(self):
        key = "cz.cuzk.dmpok"
        assert channel_signal(key, TransportKind.DIRECT_FILES, "EPSG:3045") == "http"
        assert channel_signal(key, TransportKind.DIRECT_FILES, "EPSG:5514") == "http"
        assert channel_signal(key, TransportKind.ARCGIS_IMAGE, "EPSG:5514") == "none"
        # channels of one transport with the same signal need no CRS
        assert channel_signal(key, TransportKind.DIRECT_FILES) == "http"
        with pytest.raises(ValidationError, match="nie ma kanalu"):
            channel_signal(key, TransportKind.ARCGIS_IMAGE, "EPSG:3045")


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


_SEGMENT_TOKEN = re.compile(r"[a-z0-9.-]+")


class TestCollectionChannels:
    """ADR-042 D1: collection channels carry typed engine parameters."""

    def test_collection_channels_are_typed(self):
        channels = _collection_channels()
        assert channels
        for d, ch in channels:
            if ch.transport == TransportKind.DIRECT_FILES:
                assert isinstance(ch.params, UnitPackageParams | AtomFilesParams), d.key
                if isinstance(ch.params, AtomFilesParams):
                    assert ch.params.service_feed == ch.endpoint, d.key
                    assert ch.endpoint.startswith("https://"), d.key
                    assert ch.update_signal == "metadata", d.key
            else:
                assert isinstance(ch.params, FeatureBBoxParams), d.key
                expected = {
                    TransportKind.WFS: "wfs",
                    TransportKind.ARCGIS_QUERY: "arcgis",
                    TransportKind.OGC_API_FEATURES: "ogcapi",
                }
                assert ch.params.protocol == expected[ch.transport], d.key
                assert ch.endpoint.startswith("https://"), d.key

    def test_sidecar_channel_describes_collection_channel(self):
        """The sidecar reads the CRSs of a file from the first channel of the
        capability that names its channel (ADR-043: channels of one kind - one
        WFS service per network - share a capability), so that channel must
        declare the same CRSs."""
        for d, ch in _collection_channels():
            named = _select_channel_by_capability(d, _capability(d, ch))
            assert _sidecar_crs(named) == _sidecar_crs(ch), (d.key, ch.endpoint)

    def test_url_templates_use_known_tokens(self):
        for d, ch in _collection_channels():
            if not isinstance(ch.params, UnitPackageParams):
                continue
            keys = {tuple(k for k, _ in v.choice) for v in ch.params.variants}
            assert len(keys) == 1, d.key  # one set of choice keys per channel
            choices = [v.choice for v in ch.params.variants]
            assert len(set(choices)) == len(choices), d.key
            for v in ch.params.variants:
                if v.url_template is not None:
                    tokens = set(re.findall(r"{([^}]*)}", v.url_template))
                    assert tokens <= set(PACKAGE_URL_TOKENS), (d.key, v.url_template)
                    assert v.url_template.startswith("https://"), d.key
                for token in (*v.segment_tokens, *([v.edition] if v.edition else [])):
                    assert _SEGMENT_TOKEN.fullmatch(token), (d.key, token)

    def test_unit_package_variants_addressable(self):
        """Every variant of a unit package channel gets a URL for each unit
        (ADR-043): a template filled only by tokens of its unit (a theme in
        every template of a product of several themes), else the URL of an
        index record."""
        unit_tokens = {
            "powiat": {"teryt", "woj"},
            "woj": {"teryt", "woj"},
            "country": set(),
            "sheet": {"sheet"},
            "tile": set(),
            "ku": {"ku"},
        }
        for d, ch in _collection_channels():
            params = ch.params
            if not isinstance(params, UnitPackageParams):
                continue
            allowed = unit_tokens[params.unit] | ({"theme"} if params.themes else set())
            for v in params.variants:
                if v.url_template is None:
                    assert params.index is not None, (d.key, v.choice)
                    continue
                tokens = set(re.findall(r"{([^}]*)}", v.url_template))
                assert tokens <= allowed, (d.key, params.unit, v.url_template)
                if params.themes:
                    assert "theme" in tokens, (d.key, v.url_template)

    def test_unit_sources_complete(self):
        """Sheets, tiles and cadastral areas of an area are found from the
        channel configuration alone (ADR-043): a sheet grid per variant, an
        index layer per variant of an indexed channel, the RUIAN layer."""
        for d, ch in _collection_channels():
            params = ch.params
            if not isinstance(params, UnitPackageParams):
                continue
            index = params.index
            if params.unit == "tile":
                assert index is not None and index.kind == "wfs", d.key
            if params.unit == "ku":
                assert params.ku_layer is not None, d.key
            if index is not None:
                assert params.unit in ("sheet", "tile"), d.key
                if index.kind == "wms_gfi":
                    assert index.parser == "map_links", d.key
                else:
                    assert index.url_field is not None, d.key
            for v in params.variants:
                if index is not None:
                    assert v.index_layer, (d.key, v.choice)
                grid = v.sheet_grid
                if params.unit != "sheet":
                    assert grid is None, (d.key, v.choice)
                    continue
                assert grid is not None, (d.key, v.choice)
                if grid.system == "cuzk":
                    assert grid.layer is not None and grid.crs, (d.key, v.choice)
                else:
                    assert grid.parts in range(2, 8), (d.key, v.choice)

    def test_index_signal_only_with_index(self):
        """Signal ``index`` compares the label of the unit's index record
        (ADR-043): a collection channel has it exactly when it has an index."""
        for d, ch in _collection_channels():
            indexed = isinstance(ch.params, UnitPackageParams) and (
                ch.params.index is not None
            )
            assert (ch.update_signal == "index") == indexed, (d.key, ch.endpoint)

    def test_feature_layers_unique(self):
        for d, ch in _collection_channels():
            if not isinstance(ch.params, FeatureBBoxParams):
                continue
            layers = ch.params.layers
            assert layers, d.key
            assert ch.params.page_size > 0, d.key
            for attribute in ("code", "name", "source"):
                values = [getattr(layer, attribute) for layer in layers]
                assert len(set(values)) == len(values), (d.key, attribute)
            if ch.params.selection == "level":
                for layer in layers:
                    assert _SEGMENT_TOKEN.fullmatch(layer.code), (d.key, layer.code)

    def test_new_sources_registered(self):
        pl = {d.key: d for d in sources_for(country="PL")}
        expected = {
            "pl.gugik.prg": ("admin", "boundaries/pl_prg"),
            "pl.gugik.egib": ("map", "cadastre/pl_egib"),
            "pl.gugik.buildings_3d": ("buildings", "models3d/pl_buildings"),
        }
        for key, (product, subdir) in expected.items():
            d = pl[key]
            assert (d.product, d.storage_subdir) == (product, subdir)
            assert d.license == pl["pl.gugik.bdot10k"].license
            assert all(ch.horizontal_crs == "EPSG:2180" for ch in d.channels)

    def test_bdot10k_archive_is_channel_of_bdot10k(self):
        d = get_source("pl.gugik.bdot10k")
        files = [ch for ch in d.channels if ch.transport == TransportKind.DIRECT_FILES]
        assert len(files) == 2
        current, archive = files
        assert current.params is None  # current packages: Bdot10kProvider
        assert isinstance(archive.params, UnitPackageParams)
        assert archive.params.unit == "powiat"
        assert {d.key for d in sources_for(product="landcover")} == {
            "pl.gugik.bdot10k",
            "eu.clms.corine",
            "cz.cuzk.zabaged",
        }
        published = {dict(v.choice)["year"] for v in archive.params.variants}
        assert published == {str(year) for year in range(2014, 2026)}
        for v in archive.params.variants:
            choice = dict(v.choice)
            assert v.edition == choice["year"]
            assert v.members == ({"GML": ".xml", "SHP": ".shp"}[choice["format"]],)

    def test_buildings_variants_declare_vertical_crs(self):
        """Every release declares the vertical CRS measured in its GML (srsName)."""
        (channel,) = get_source("pl.gugik.buildings_3d").channels
        assert isinstance(channel.params, UnitPackageParams)
        measured = {
            (dict(v.choice)["lod"], dict(v.choice)["year"]): v.vertical_crs
            for v in channel.params.variants
        }
        assert measured == {
            ("1", "2019"): "EPSG:9650",
            ("1", "2021"): "EPSG:9651",
            ("1", "2022"): "EPSG:9651",
            ("1", "2024"): "EPSG:9651",
            ("2", "2017"): "EPSG:9650",
        }
        assert set(measured.values()) <= set(channel.vertical_crs_options)
