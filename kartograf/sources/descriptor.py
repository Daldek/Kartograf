"""
Source descriptors - pure data, zero IO, zero behavior.

A descriptor describes ONE dataset (e.g. NMT 1 m from GUGiK): access channels,
coordinate systems, licenses, tile scheme. The providers remain the source of
truth for runtime logic; capabilities currently only drive channel selection
in the sidecar (``build_metadata(capability=)``) and are not enforced in managers.
"""

from dataclasses import dataclass
from enum import StrEnum

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ValidationError


class TransportKind(StrEnum):
    """Kind of data transport (the download mechanism)."""

    WCS = "wcs"  # PL nmt_1m bbox, SoilGrids; later DE/SK
    WMS_SHEET_INDEX = "wms_sheet_index"  # PL: WMS index (skorowidz) -> file URL
    WFS = "wfs"  # PL LAZ
    DIRECT_FILES = "direct_files"  # PL BDOT10k, CZ openzu (DMR 4G)
    CLMS_API = "clms_api"  # CORINE
    ARCGIS_IMAGE = "arcgis_image"  # stage 1 (CZ exportImage)
    ARCGIS_QUERY = "arcgis_query"  # stage 3 (ZABAGED), SK
    OGC_API_FEATURES = "ogc_api_features"  # DE basemap.de


@dataclass(frozen=True)
class LicenseInfo:
    """License and ready-made attribution text for a source."""

    id: str  # np. "CC-BY-4.0", "PL-PGiK-40a", "dl-de/by-2-0"
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
    # {"bbox_raster","bbox_vector","sheet_files","area_files","admin_unit_files"}
    notes: str = ""
    endpoint: str = ""
    # Channel URL for descriptor-driven engines (stage 1: CuzkClient).
    # PL entries: "" - the provider constants remain the source of truth (stage 0).


@dataclass(frozen=True)
class TileScheme:
    """Tile scheme of a source (computable or requiring an index)."""

    kind: str  # "computable" | "index"
    crs: str
    width_m: float | None
    height_m: float | None
    description: str  # np. "SM5: nazwa miasta + cyfry, wymaga indeksu"


@dataclass(frozen=True)
class SourceDescriptor:
    """Pelny opis jednego zbioru danych."""

    key: str  # "pl.gugik.nmt_1m"
    country: str  # "PL" | "CZ" | "EU" | "GLOBAL" (later "DE","SK")
    product: str  # "nmt" | "nmpt" | "orto" | "laz" | "landcover" | "soil"
    name: str  # human-readable dataset name
    provider_name: str  # "GUGiK", "CUZK", ...
    channels: tuple[AccessChannel, ...]
    tile_scheme: TileScheme | None
    # Segment template {uklad}/{vcrs} (ADR-026); None for LandCoverManager sources
    storage_subdir: str | None
    default_extension: str
    license: LicenseInfo
    resolution: str | None = None
    auth: str = "none"  # "none" | "clms_oauth"

    def resolve_subdir(
        self, *, uklad: str | None = None, vertical_crs: str | None = None
    ) -> str:
        """Fill in the ``storage_subdir`` template (placeholders {uklad}, {vcrs}).

        ``str.replace``, not ``str.format`` - partial filling is legal
        ({uklad} may be left to be resolved later, per sheet code, in
        FileStorage). A dimension absent from the template = no-op (orto ignores
        vcrs). The "no braces left in the segment" validation is done by the
        final caller (FileStorage) - ADR-026.

        ``None`` still means "fill in later" (allowed), but an empty string
        (or whitespace only) is a caller error, not a missing dimension - without
        this check it produced a silent, dangling storage segment (e.g.
        `nmt/pl_1992_1m_`, review max 2026-08-30, finding 7).
        """
        if self.storage_subdir is None:
            raise ValueError(f"Zrodlo '{self.key}' nie ma storage_subdir")
        for name, value in (("uklad", uklad), ("vcrs", vertical_crs)):
            if value is not None and not value.strip():
                raise ValidationError(
                    f"Pusty wymiar segmentu storage '{name}' (zrodlo '{self.key}') "
                    "— podaj wartosc albo None"
                )
        subdir = self.storage_subdir
        if uklad is not None:
            subdir = subdir.replace("{uklad}", uklad)
        if vertical_crs is not None:
            subdir = subdir.replace("{vcrs}", vertical_crs.lower())
        return subdir


@dataclass(frozen=True)
class CountryProfile:
    """Country profile: approximate extent (for --country auto in stage 1) +
    datasets."""

    code: str  # "PL"
    name: str
    extent_wgs84: BBox
    dataset_keys: tuple[str, ...]
