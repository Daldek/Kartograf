"""
Deskryptory zrodel danych — czyste dane, zero IO, zero zachowan.

Deskryptor opisuje JEDEN zbior danych (np. NMT 1m z GUGiK): kanaly dostepu,
uklady, licencje, schemat kafli. Zrodlem prawdy dla logiki wykonawczej
pozostaja providery (etap 0); egzekwowanie capabilities zaczyna sie w etapie 1.
"""

from dataclasses import dataclass
from enum import StrEnum

from kartograf.core.sheet_parser import BBox


class TransportKind(StrEnum):
    """Rodzaj transportu danych (mechanizm pobierania)."""

    WCS = "wcs"  # PL nmt_1m bbox, SoilGrids; pozniej DE/SK
    WMS_SHEET_INDEX = "wms_sheet_index"  # PL: skorowidz WMS -> URL pliku
    WFS = "wfs"  # PL LAZ
    DIRECT_FILES = "direct_files"  # PL BDOT10k; pozniej CZ openzu
    CLMS_API = "clms_api"  # CORINE
    ARCGIS_IMAGE = "arcgis_image"  # etap 1 (CZ exportImage)
    ARCGIS_QUERY = "arcgis_query"  # etap 3 (ZABAGED), SK
    OGC_API_FEATURES = "ogc_api_features"  # DE basemap.de


@dataclass(frozen=True)
class LicenseInfo:
    """Licencja i gotowy tekst atrybucji dla zrodla."""

    id: str  # np. "CC-BY-4.0", "PL-PGiK-40a", "dl-de/by-2-0"
    attribution: str  # gotowy tekst atrybucji
    url: str = ""


@dataclass(frozen=True)
class AccessChannel:
    """Jeden kanal dostepu do zrodla (transport + uklady + zdolnosci)."""

    transport: TransportKind
    horizontal_crs: str  # "EPSG:2180", "EPSG:5514", ...
    vertical_crs_options: tuple[str, ...] = ()  # () gdy nie dotyczy (orto, landcover)
    vertical_source: str = "native"  # "native" | "ellipsoidal" | "server"
    server_reprojection: bool = False
    capabilities: frozenset[str] = frozenset()
    # {"bbox_raster","bbox_vector","sheet_files","area_files","admin_unit_files"}
    notes: str = ""
    endpoint: str = ""
    # URL kanalu dla silnikow sterowanych deskryptorem (etap 1: CuzkClient).
    # Wpisy PL: "" — zrodlem prawdy pozostaja stale providerow (etap 0).


@dataclass(frozen=True)
class TileScheme:
    """Schemat kafli zrodla (obliczalny lub wymagajacy indeksu)."""

    kind: str  # "computable" | "index"
    crs: str
    width_m: float | None
    height_m: float | None
    description: str  # np. "SM5: nazwa miasta + cyfry, wymaga indeksu"


@dataclass(frozen=True)
class SourceDescriptor:
    """Pelny opis jednego zbioru danych."""

    key: str  # "pl.gugik.nmt_1m"
    country: str  # "PL" | "EU" | "GLOBAL" (pozniej "CZ","DE","SK")
    product: str  # "nmt" | "nmpt" | "orto" | "laz" | "landcover" | "soil"
    name: str  # czytelna nazwa zbioru
    provider_name: str  # "GUGiK", "CUZK", ...
    channels: tuple[AccessChannel, ...]
    tile_scheme: TileScheme | None
    # Szablon segmentu {uklad}/{vcrs} (ADR-026); None dla zrodel LandCoverManagera
    storage_subdir: str | None
    default_extension: str
    license: LicenseInfo
    resolution: str | None = None
    auth: str = "none"  # "none" | "clms_oauth"

    def resolve_subdir(
        self, *, uklad: str | None = None, vertical_crs: str | None = None
    ) -> str:
        """Wypelnij szablon ``storage_subdir`` (placeholdery {uklad}, {vcrs}).

        ``str.replace``, nie ``str.format`` — czesciowe wypelnienie jest
        legalne ({uklad} moze zostac do rozwiazania pozniej, per godlo,
        w FileStorage). Wymiar nieobecny w szablonie = no-op (orto ignoruje
        vcrs). Walidacje "zero klamer w segmencie" robi wolajacy koncowy
        (FileStorage) — ADR-026.
        """
        if self.storage_subdir is None:
            raise ValueError(f"Zrodlo '{self.key}' nie ma storage_subdir")
        subdir = self.storage_subdir
        if uklad is not None:
            subdir = subdir.replace("{uklad}", uklad)
        if vertical_crs is not None:
            subdir = subdir.replace("{vcrs}", vertical_crs.lower())
        return subdir


@dataclass(frozen=True)
class CountryProfile:
    """Profil kraju: przyblizony zasieg (dla --country auto w etapie 1) + zbiory."""

    code: str  # "PL"
    name: str
    extent_wgs84: BBox
    dataset_keys: tuple[str, ...]
