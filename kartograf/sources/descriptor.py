"""
Source descriptors - pure data, zero IO, zero behavior.

A descriptor describes ONE dataset (e.g. NMT 1 m from GUGiK): access channels,
coordinate systems, licenses, tile scheme. The providers remain the source of
truth for runtime logic; capabilities currently only drive channel selection
in the sidecar (``build_metadata(capability=)``) and are not enforced in managers.

Collection channels (ADR-042) carry typed engine configuration in
``AccessChannel.params``: ``UnitPackageParams`` (one package per TERYT unit or
the country, from a URL template) and ``FeatureBBoxParams`` (features of an
area from WFS / ArcGIS REST into one GeoPackage). A new product of such a
channel is a descriptor entry, not a provider.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError

if TYPE_CHECKING:
    # variants.py imports TransportKind from here; the field only needs the type
    from kartograf.sources.variants import ProductVariant


class TransportKind(StrEnum):
    """Kind of data transport (the download mechanism)."""

    WCS = "wcs"  # PL nmt_1m bbox, SoilGrids; later DE/SK
    WMS_SHEET_INDEX = "wms_sheet_index"  # PL: WMS index (skorowidz) -> file URL
    WFS = "wfs"  # PL LAZ
    DIRECT_FILES = "direct_files"  # PL BDOT10k, CZ openzu (DMR 4G)
    CLMS_API = "clms_api"  # CORINE
    WMS = "wms"  # CORINE preview (EEA/DLR styled PNG, not data)
    ARCGIS_IMAGE = "arcgis_image"  # stage 1 (CZ exportImage)
    ARCGIS_QUERY = "arcgis_query"  # stage 3 (ZABAGED), SK
    OGC_API_FEATURES = "ogc_api_features"  # DE basemap.de


# Cheap freshness signal of a channel (versioned store spec 4.1, 8): the
# sheet index record (``index``), source metadata (``metadata``), HTTP
# ``ETag``/``Last-Modified`` of the file (``http``) or none (``none``).
SignalKind = Literal["index", "metadata", "http", "none"]

# URL template tokens of a unit package (ADR-042 D1): the TERYT code of the
# unit and the voivodeship code (its first two digits).
PACKAGE_URL_TOKENS = ("teryt", "woj")


@dataclass(frozen=True)
class PackageVariant:
    """One published package variant: choice values -> URL template.

    ``choice`` = the user's choice that selects this variant (keys are the
    API/CLI option names: ``("format", "SHP"), ("year", "2024")``); ``()``
    when the source publishes one variant. ``edition`` labels the version
    (``label_source="edition"``) of a product with the release in its
    segment (BDOT10k archive year, 3D models year). ``segment_tokens`` name
    the content in the storage segment (ADR-042 D8). ``members``: suffixes
    that must occur among the ZIP members of this variant (a package without
    them is not data; the GML and SHP packages of one channel differ).
    ``vertical_crs`` is the vertical CRS declared in the data (3D CityGML),
    ``None`` for 2D data.
    """

    choice: tuple[tuple[str, str], ...]
    url_template: str  # tokens: {teryt}, {woj} only
    edition: str | None = None
    segment_tokens: tuple[str, ...] = ()
    members: tuple[str, ...] = ()
    vertical_crs: str | None = None


@dataclass(frozen=True)
class UnitPackageParams:
    """Engine ``unit_package``: one ZIP per unit (``powiat``, ``woj``, ``country``).

    ``unpack``: the suffix of the ONE member stored instead of the ZIP
    (``None`` = the ZIP is stored 1:1).
    """

    unit: Literal["powiat", "woj", "country"]
    variants: tuple[PackageVariant, ...]
    unpack: str | None = None


@dataclass(frozen=True)
class FeatureLayer:
    """One source layer of a ``feature_bbox`` channel.

    ``code`` is the public value (``--level gmina``) or a fixed layer code,
    ``source`` the WFS type name (``ms:A03_Granice_gmin``) or the ArcGIS
    layer id (``"12"``), ``name`` the GeoPackage layer name and ``id_field``
    the stable feature identifier (deduplication, order of the features).
    """

    code: str
    source: str
    name: str
    id_field: str


@dataclass(frozen=True)
class FeatureBBoxParams:
    """Engine ``feature_bbox``: features of an area into one GPKG (ADR-042 D3-D5).

    ``axis_order`` is the order of the BBOX numbers of the service in
    ``native_crs`` (``"yx"`` = northing first, EPSG:2180 per EPSG; a swapped
    order gives an empty answer without an error). ``selection``: ``level``
    = one layer chosen by ``FeatureLayer.code`` (``--level``), ``all`` =
    every layer. ``order_field``: ArcGIS ``orderByFields`` of the pages.
    ``drop_fields``: fields whose value is the moment of the response (EGiB
    ``DATA``) - kept out of the GeoPackage, reported in the sidecar.
    """

    protocol: Literal["wfs", "arcgis"]
    native_crs: str
    axis_order: Literal["xy", "yx"]
    page_size: int
    layers: tuple[FeatureLayer, ...]
    selection: Literal["level", "all"]
    order_field: str | None = None
    drop_fields: tuple[str, ...] = ()


ChannelParams = UnitPackageParams | FeatureBBoxParams


@dataclass(frozen=True)
class LicenseInfo:
    """License and ready-made attribution text for a source."""

    id: str  # e.g. "CC-BY-4.0", "PL-PGiK-40a", "dl-de/by-2-0"
    attribution: str  # ready-made attribution text
    url: str = ""


@dataclass(frozen=True)
class AccessChannel:
    """One access channel to a source (transport + CRSs + capabilities)."""

    transport: TransportKind
    horizontal_crs: str  # "EPSG:2180", "EPSG:5514", ...
    vertical_crs_options: tuple[str, ...] = ()  # () when n/a (orto, landcover)
    vertical_source: str = "native"  # "native" | "ellipsoidal" | "server"
    server_reprojection: bool = False
    capabilities: frozenset[str] = frozenset()
    # {"bbox_raster","bbox_vector","sheet_files","area_files","admin_unit_files",
    #  "archive_unit_files","country_files"}; a collection channel (``params``)
    # declares a capability no other channel of its descriptor has (sidecar
    # channel selection, ``build_metadata(capability=)``)
    notes: str = ""
    endpoint: str = ""
    # Channel URL for descriptor-driven engines (stage 1: CuzkClient; ADR-042:
    # the service of a feature_bbox channel, the directory of unit packages).
    # PL sheet entries: "" - the provider constants remain the source of truth.
    update_signal: SignalKind = "none"
    # Freshness signal of THIS channel (one dataset may have several, e.g.
    # CZ DMR 4G: SM5 files with ETag, exportImage without a content signal).
    params: ChannelParams | None = None
    # Typed configuration of a collection engine (ADR-042 D1); None = the
    # channel is driven by a provider.


@dataclass(frozen=True)
class TileScheme:
    """Tile scheme of a source (computable or requiring an index)."""

    kind: str  # "computable" | "index"
    crs: str
    width_m: float | None
    height_m: float | None
    description: str  # e.g. "SM5: nazwa miasta + cyfry, wymaga indeksu"


@dataclass(frozen=True)
class SourceDescriptor:
    """Full description of one dataset."""

    key: str  # "pl.gugik.nmt_1m"
    country: str  # "PL" | "CZ" | "EU" | "GLOBAL" (later "DE","SK")
    product: str  # "nmt" | "nmpt" | "orto" | "laz" | "landcover" | "soil"
    name: str  # human-readable dataset name
    provider_name: str  # "GUGiK", "CUZK", ...
    channels: tuple[AccessChannel, ...]
    tile_scheme: TileScheme | None
    # Segment template {system}/{vcrs} (ADR-026); land cover and collections: a
    # prefix completed by content tokens (download.storage.content_segment,
    # spec 3.4, ADR-042 D8)
    storage_subdir: str
    default_extension: str
    license: LicenseInfo
    resolution: str | None = None
    auth: str = "none"  # "none" | "clms_oauth"
    # Variants stored by this descriptor (ADR-041, kartograf.sources.variants):
    # PL NMT/NMPT one per height system of the (product, format, resolution).
    variants: tuple["ProductVariant", ...] = ()

    def resolve_subdir(
        self, *, system: str | None = None, vertical_crs: str | None = None
    ) -> str:
        """Fill in the ``storage_subdir`` template (placeholders {system}, {vcrs}).

        ``str.replace``, not ``str.format`` - partial filling is legal
        ({system} may be left to be resolved later, per sheet code, in
        FileStorage). A dimension absent from the template = no-op (orto ignores
        vcrs). The "no braces left in the segment" validation is done by the
        final caller (FileStorage) - ADR-026.

        ``None`` still means "fill in later" (allowed), but an empty string
        (or whitespace only) is a caller error, not a missing dimension - without
        this check it produced a silent, dangling storage segment (e.g.
        `nmt/pl_1992_1m_`, review max 2026-08-30, finding 7).
        """
        for name, value in (("system", system), ("vcrs", vertical_crs)):
            if value is not None and not value.strip():
                raise ValidationError(
                    f"Pusty wymiar segmentu storage '{name}' (zrodlo '{self.key}') "
                    "- podaj wartosc albo None"
                )
        subdir = self.storage_subdir
        if system is not None:
            subdir = subdir.replace("{system}", system)
        if vertical_crs is not None:
            subdir = subdir.replace("{vcrs}", vertical_crs.lower())
        return subdir


@dataclass(frozen=True)
class CountryProfile:
    """Country profile: rough extent (for --country auto in stage 1) + datasets."""

    code: str  # "PL"
    name: str
    extent_wgs84: BBox
    dataset_keys: tuple[str, ...]
