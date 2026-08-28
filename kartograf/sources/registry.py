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
    TileScheme,
    TransportKind,
)

# Mapowanie nazw ukladow pionowych uzywanych w CLI na kody EPSG.
_VERTICAL_CRS_CODES = {
    "KRON86": "EPSG:9650",  # PL-KRON86-NH (bez zmian)
    "EVRF2007": "EPSG:5621",  # ogolnoeuropejski EVRF2007 (decyzja 2026-08-11)
    "EVRF2007-PL": "EPSG:9651",  # realizacja polska PL-EVRF2007-NH
    "Bpv": "EPSG:8357",  # Baltic 1957 (CZ)
}

# Rodzina -> realizacje krajowe; konsumowane przy budowie sidecara:
# jesli kod rodziny nie wystepuje w vertical_crs_options kanalu, ale wystepuje
# jego realizacja — sidecar zapisuje kod realizacji (fakt, nie zyczenie).
_VERTICAL_FAMILY: dict[str, tuple[str, ...]] = {"EPSG:5621": ("EPSG:9651",)}

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

_CUZK_LICENSE = LicenseInfo(
    id="CC-BY-4.0",
    attribution="Podklad: Cesky urad zememericky a katastralni (CUZK), CC BY 4.0",
    url="https://geoportal.cuzk.gov.cz",
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
                    vertical_crs_options=("EPSG:9650",),
                    capabilities=frozenset({"bbox_raster"}),
                    notes=(
                        "WCS EVRF2007 (DigitalTerrainModelFormatTIFFEVRF2007) "
                        "wycofany przez GUGiK - HTTP 404 od 2026-08-11 "
                        "(docs/PROGRESS.md); bbox raster tylko KRON86"
                    ),
                ),
            ),
            tile_scheme=None,
            storage_subdir="nmt/pl_{uklad}_1m_{vcrs}",
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
            storage_subdir="nmt/pl_{uklad}_5m_{vcrs}",
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
            storage_subdir="nmpt/pl_{uklad}_1m_{vcrs}",
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
            storage_subdir="orto/pl_{uklad}",
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
            storage_subdir="laz/pl_{uklad}_{vcrs}",
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
        SourceDescriptor(
            key="cz.cuzk.dmr5g",
            country="CZ",
            product="nmt",
            name="DMR 5G — Digitalni model reliefu (raster 2 m z exportImage)",
            provider_name="CUZK",
            channels=(
                AccessChannel(
                    transport=TransportKind.ARCGIS_IMAGE,
                    horizontal_crs="EPSG:5514",
                    vertical_crs_options=("EPSG:8357",),
                    server_reprojection=False,
                    notes=(
                        "Serwer obsluguje imageSR, ale ADR-024 zabrania - "
                        "reprojekcja tresci wylacznie lokalna, przypieta operacja"
                    ),
                    capabilities=frozenset({"bbox_raster"}),
                    endpoint=(
                        "https://ags.cuzk.gov.cz/arcgis2/rest/services/"
                        "dmr5g/ImageServer"
                    ),
                ),
            ),
            tile_scheme=TileScheme(
                kind="computable",
                crs="EPSG:3045",
                width_m=2000.0,
                height_m=2000.0,
                description="TM33 {E_km}_{N_km}, naroznik SW",
            ),
            storage_subdir="nmt/cz_dmr5g_{vcrs}",
            default_extension=".tif",
            license=_CUZK_LICENSE,
            resolution="2m",
        ),
        SourceDescriptor(
            key="cz.cuzk.dmr4g",
            country="CZ",
            product="nmt",
            name="DMR 4G — Digitalni model reliefu (GeoTIFF 5 m, arkusze SM5)",
            provider_name="CUZK",
            channels=(
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    horizontal_crs="EPSG:5514",
                    vertical_crs_options=("EPSG:8357",),
                    capabilities=frozenset({"sheet_files"}),
                    endpoint=(
                        "https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/"
                        "epsg-5514/{sheet}.zip"
                    ),
                ),
                AccessChannel(
                    transport=TransportKind.ARCGIS_IMAGE,
                    horizontal_crs="EPSG:5514",
                    vertical_crs_options=("EPSG:8357",),
                    server_reprojection=False,
                    notes=(
                        "Serwer obsluguje imageSR, ale ADR-024 zabrania - "
                        "reprojekcja tresci wylacznie lokalna, przypieta operacja"
                    ),
                    capabilities=frozenset({"bbox_raster"}),
                    endpoint=(
                        "https://ags.cuzk.gov.cz/arcgis2/rest/services/"
                        "dmr4g/ImageServer"
                    ),
                ),
            ),
            tile_scheme=TileScheme(
                kind="index",
                crs="EPSG:5514",
                width_m=2500.0,
                height_m=2000.0,
                description=(
                    "SM5: 4 litery miasta + 2 cyfry; indeks KladyMapovychListu w. 24"
                ),
            ),
            storage_subdir="nmt/cz_dmr4g_{vcrs}",
            default_extension=".tif",
            license=_CUZK_LICENSE,
            resolution="5m",
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
    "CZ": CountryProfile(
        code="CZ",
        name="Czechy",
        extent_wgs84=BBox(12.09, 48.55, 18.86, 51.06, "EPSG:4326"),
        dataset_keys=("cz.cuzk.dmr4g", "cz.cuzk.dmr5g"),
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


def all_countries() -> list[CountryProfile]:
    """Wszystkie profile krajow, deterministycznie po kodzie (dla --country auto)."""
    return [_COUNTRIES[code] for code in sorted(_COUNTRIES)]


def vertical_crs_code(name: str) -> str:
    """Mapuj nazwe CLI ukladu pionowego na kod EPSG (kody przechodza bez zmian)."""
    if name in _VERTICAL_CRS_CODES:
        return _VERTICAL_CRS_CODES[name]
    if name in _VERTICAL_CRS_CODES.values():
        return name
    raise KeyError(
        f"Nieznany uklad pionowy: '{name}'. Dostepne: {sorted(_VERTICAL_CRS_CODES)}"
    )


def resolve_vertical_crs(name: str, options: tuple[str, ...]) -> str:
    """Kod EPSG dla nazwy ukladu wzgledem opcji kanalu (rodzina -> realizacja)."""
    code = vertical_crs_code(name)
    if code in options:
        return code
    for realization in _VERTICAL_FAMILY.get(code, ()):
        if realization in options:
            return realization
    return code
