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
