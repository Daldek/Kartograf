"""
Registry of data sources and countries.

Descriptors are the source of truth for storage_subdir (segment templates,
ADR-026), default_extension, licenses, vertical options and capabilities
(consumed by: sidecar + consistency tests). Capabilities select the channel
in the sidecar; managers do not enforce them.
"""

import re

from kartograf.core.parser_2000 import ZONE_EPSG
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.sources.descriptor import (
    AccessChannel,
    CountryProfile,
    LicenseInfo,
    SourceDescriptor,
    TileScheme,
    TransportKind,
)

# Mapping of vertical CRS names used in the CLI to EPSG codes.
_VERTICAL_CRS_CODES = {
    "KRON86": "EPSG:9650",  # PL-KRON86-NH (unchanged)
    "EVRF2007": "EPSG:5621",  # pan-European EVRF2007 (decision 2026-08-11)
    "EVRF2007-PL": "EPSG:9651",  # Polish realization PL-EVRF2007-NH
    "Bpv": "EPSG:8357",  # Baltic 1957 (CZ)
}

# Family -> national realizations; consumed when building the sidecar:
# if the family code is absent from the channel's vertical_crs_options but
# its realization is present - the sidecar records the realization code (fact, not
# wish).
_VERTICAL_FAMILY: dict[str, tuple[str, ...]] = {"EPSG:5621": ("EPSG:9651",)}

# Horizontal CRS of PL sources. Channels declare EPSG:2180 (the CRS of bbox/WCS
# queries and PL-1992 sheets); a PL-2000 sheet or tile file is in the CRS of ITS OWN
# zone (5..8 -> EPSG:2176..2179) - the sidecar takes it from horizontal_crs_for_*
# below, not from the channel (N8).
PL_1992_CRS = "EPSG:2180"

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
                    horizontal_crs=PL_1992_CRS,  # PL-2000: zone from sheet code (N8)
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
    """Return a source descriptor; KeyError with a list of available keys."""
    try:
        return _SOURCES[key]
    except KeyError:
        raise KeyError(
            f"Nieznane zrodlo: '{key}'. Dostepne: {sorted(_SOURCES)}"
        ) from None


def sources_for(
    country: str | None = None, product: str | None = None
) -> list[SourceDescriptor]:
    """Return descriptors matching the country and/or product."""
    return [
        d
        for d in _SOURCES.values()
        if (country is None or d.country == country)
        and (product is None or d.product == product)
    ]


def get_country(code: str) -> CountryProfile:
    """Return a country profile; KeyError with a list of available codes."""
    try:
        return _COUNTRIES[code]
    except KeyError:
        raise KeyError(
            f"Nieznany kraj: '{code}'. Dostepne: {sorted(_COUNTRIES)}"
        ) from None


def all_countries() -> list[CountryProfile]:
    """All country profiles, deterministically by code (for --country auto)."""
    return [_COUNTRIES[code] for code in sorted(_COUNTRIES)]


def vertical_crs_code(name: str) -> str:
    """Map a CLI vertical CRS name to an EPSG code (codes pass through unchanged)."""
    if name in _VERTICAL_CRS_CODES:
        return _VERTICAL_CRS_CODES[name]
    if name in _VERTICAL_CRS_CODES.values():
        return name
    raise KeyError(
        f"Nieznany uklad pionowy: '{name}'. Dostepne: {sorted(_VERTICAL_CRS_CODES)}"
    )


def resolve_vertical_crs(name: str, options: tuple[str, ...]) -> str:
    """EPSG code for a CRS name relative to the channel options (family ->
    realization)."""
    code = vertical_crs_code(name)
    if code in options:
        return code
    for realization in _VERTICAL_FAMILY.get(code, ()):
        if realization in options:
            return realization
    return code


def horizontal_crs_for_godlo(godlo: str) -> str:
    """Horizontal CRS of a PL sheet from the sheet code format: PL-1992 -> 2180,
    PL-2000 -> zone."""
    parser = SheetParser(godlo)
    if parser.uklad == "2000":
        return ZONE_EPSG[int(parser.godlo.split(".")[0])]
    return PL_1992_CRS


def parse_pl_uklad(value: str | None) -> tuple[str, int | None] | None:
    """The ONLY parser of GUGiK horizontal CRS values (review-1 D3, E11).

    The index fields ``ukladWspolrzednychPoziomych``/``ukladWspolrzednych``
    and WFS LAZ ``uklad_xy``: ``"PL-1992"`` -> ``("1992", None)``,
    ``"PL-2000:S5"``..``"PL-2000:S8"`` -> ``("2000", zone)``. Surrounding
    whitespace is stripped; any other value (``"PL-2000"`` without a zone,
    ``"PL-2000:S9"``, different letter case, ``None``) -> ``None``. Real GUGiK
    data (E2E 2026-10-06) contains only recognized values.

    Consumers (index record selection, ``horizontal_crs_for_uklad``,
    ``LazTile.uklad``) treat ``None`` consistently: the record/tile is rejected
    or an explicit error is raised - never a ``pl_2000`` segment with an EPSG:2180
    sidecar.
    """
    text = (value or "").strip()
    if text == "PL-1992":
        return "1992", None
    match = re.fullmatch(r"PL-2000:S([5-8])", text)
    return ("2000", int(match[1])) if match else None


def horizontal_crs_for_uklad(uklad: str | None) -> str | None:
    """EPSG code from a GUGiK CRS name ("PL-1992", "PL-2000:S6"); None if unknown.

    Value recognition: ``parse_pl_uklad`` (shared with the index and LAZ).
    """
    parsed = parse_pl_uklad(uklad)
    if parsed is None:
        return None
    _system, zone = parsed
    return ZONE_EPSG[zone] if zone is not None else PL_1992_CRS
