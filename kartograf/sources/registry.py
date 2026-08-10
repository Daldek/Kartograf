"""
Rejestr zrodel danych i krajow.

Etap 0: deskryptory sa zrodlem prawdy dla storage_subdir, default_extension,
licencji, opcji pionowych i capabilities (konsumpcja: sidecar + testy
spojnosci). Egzekwowanie capabilities w managerach zaczyna sie w etapie 1.
"""

from kartograf.core.sheet_parser import BBox
from kartograf.sources.descriptor import (
    AccessChannel,
    CountryProfile,
    LicenseInfo,
    SourceDescriptor,
    TransportKind,
)

# Mapowanie nazw ukladow pionowych uzywanych w CLI na kody EPSG.
_VERTICAL_CRS_CODES = {
    "KRON86": "EPSG:9650",  # PL-KRON86-NH
    "EVRF2007": "EPSG:9651",  # PL-EVRF2007-NH (realizacja PL)
}

_GUGIK_LICENSE = LicenseInfo(
    id="PL-PGiK-40a",
    attribution=(
        "Dane: Glowny Urzad Geodezji i Kartografii (www.geoportal.gov.pl), "
        "art. 40a ust. 2 pkt 1 ustawy Prawo geodezyjne i kartograficzne"
    ),
    url="https://www.geoportal.gov.pl",
)

_CLMS_LICENSE = LicenseInfo(
    id="COPERNICUS-CLMS",
    attribution=(
        "(c) European Union, Copernicus Land Monitoring Service, "
        "European Environment Agency (EEA)"
    ),
    url="https://land.copernicus.eu/en/products/corine-land-cover",
)

_SOILGRIDS_LICENSE = LicenseInfo(
    id="CC-BY-4.0",
    attribution="SoilGrids — ISRIC World Soil Information, CC BY 4.0",
    url="https://www.isric.org/explore/soilgrids",
)

_PL_VERTICAL_BOTH = ("EPSG:9650", "EPSG:9651")

_SOURCES: dict[str, SourceDescriptor] = {
    d.key: d
    for d in (
        SourceDescriptor(
            key="pl.gugik.nmt_1m",
            country="PL",
            product="nmt",
            name="Numeryczny Model Terenu 1 m (GRID1)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"sheet_files"}),
                ),
                AccessChannel(
                    transport=TransportKind.WCS,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"bbox_raster"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir="nmt_1m",
            default_extension=".asc",
            license=_GUGIK_LICENSE,
            resolution="1m",
        ),
        SourceDescriptor(
            key="pl.gugik.nmt_5m",
            country="PL",
            product="nmt",
            name="Numeryczny Model Terenu 5 m",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=("EPSG:9651",),
                    capabilities=frozenset({"sheet_files"}),
                    notes="WCS niedostepne dla 5m — tylko arkusze OpenData",
                ),
            ),
            tile_scheme=None,
            storage_subdir="nmt_5m",
            default_extension=".asc",
            license=_GUGIK_LICENSE,
            resolution="5m",
        ),
        SourceDescriptor(
            key="pl.gugik.nmpt",
            country="PL",
            product="nmpt",
            name="Numeryczny Model Pokrycia Terenu 1 m (DSM)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"sheet_files"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir="nmpt",
            default_extension=".asc",
            license=_GUGIK_LICENSE,
            resolution="1m",
        ),
        SourceDescriptor(
            key="pl.gugik.orto",
            country="PL",
            product="orto",
            name="Ortofotomapa Standard Resolution (25 cm)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"sheet_files"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir="orto",
            default_extension=".tif",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="pl.gugik.laz",
            country="PL",
            product="laz",
            name="Chmury punktow LIDAR (dane pomiarowe ALS)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WFS,
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"area_files"}),
                    notes="WMS skorowidzy LAZ zwraca 401 — WFS jedyna droga",
                ),
            ),
            tile_scheme=None,
            storage_subdir="laz",
            default_extension=".laz",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="pl.gugik.bdot10k",
            country="PL",
            product="landcover",
            name="BDOT10k — baza danych obiektow topograficznych",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"admin_unit_files"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir=None,
            default_extension=".gpkg",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="eu.clms.corine",
            country="EU",
            product="landcover",
            name="CORINE Land Cover",
            provider_name="Copernicus CLMS",
            channels=(
                AccessChannel(
                    transport=TransportKind.CLMS_API,
                    horizontal_crs="EPSG:3035",
                    capabilities=frozenset({"bbox_raster"}),
                    notes="bez credentials CLMS fallback: podglad PNG z WMS",
                ),
            ),
            tile_scheme=None,
            storage_subdir=None,
            default_extension=".tif",
            license=_CLMS_LICENSE,
            auth="clms_oauth",
        ),
        SourceDescriptor(
            key="global.isric.soilgrids",
            country="GLOBAL",
            product="soil",
            name="SoilGrids — globalne dane glebowe",
            provider_name="ISRIC",
            channels=(
                AccessChannel(
                    transport=TransportKind.WCS,
                    horizontal_crs="EPSG:4326",
                    capabilities=frozenset({"bbox_raster"}),
                    notes="tylko WGS84 bbox; transformacja z EPSG:2180 automatyczna",
                ),
            ),
            tile_scheme=None,
            storage_subdir=None,
            default_extension=".tif",
            license=_SOILGRIDS_LICENSE,
        ),
    )
}

_COUNTRIES: dict[str, CountryProfile] = {
    "PL": CountryProfile(
        code="PL",
        name="Polska",
        extent_wgs84=BBox(14.07, 49.00, 24.20, 54.90, "EPSG:4326"),
        dataset_keys=tuple(sorted(k for k in _SOURCES if k.startswith("pl."))),
    ),
}


def get_source(key: str) -> SourceDescriptor:
    """Zwroc deskryptor zrodla; KeyError z lista dostepnych kluczy."""
    try:
        return _SOURCES[key]
    except KeyError:
        raise KeyError(
            f"Nieznane zrodlo: '{key}'. Dostepne: {sorted(_SOURCES)}"
        ) from None


def sources_for(
    country: str | None = None, product: str | None = None
) -> list[SourceDescriptor]:
    """Zwroc deskryptory pasujace do kraju i/lub produktu."""
    return [
        d
        for d in _SOURCES.values()
        if (country is None or d.country == country)
        and (product is None or d.product == product)
    ]


def get_country(code: str) -> CountryProfile:
    """Zwroc profil kraju; KeyError z lista dostepnych kodow."""
    try:
        return _COUNTRIES[code]
    except KeyError:
        raise KeyError(
            f"Nieznany kraj: '{code}'. Dostepne: {sorted(_COUNTRIES)}"
        ) from None


def vertical_crs_code(name: str) -> str:
    """Mapuj nazwe CLI ukladu pionowego na kod EPSG (kody przechodza bez zmian)."""
    if name in _VERTICAL_CRS_CODES:
        return _VERTICAL_CRS_CODES[name]
    if name in _VERTICAL_CRS_CODES.values():
        return name
    raise KeyError(
        f"Nieznany uklad pionowy: '{name}'. Dostepne: {sorted(_VERTICAL_CRS_CODES)}"
    )
