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
from kartograf.exceptions import ValidationError
from kartograf.sources.descriptor import (
    AccessChannel,
    CountryProfile,
    FeatureBBoxParams,
    FeatureLayer,
    LicenseInfo,
    PackageVariant,
    SignalKind,
    SourceDescriptor,
    TileScheme,
    TransportKind,
    UnitPackageParams,
)
from kartograf.sources.variants import (
    IndexRef,
    ProductVariant,
    file_format,
    parse_resolution,
)

# Mapping of vertical CRS names used in the CLI to EPSG codes.
_VERTICAL_CRS_CODES = {
    "KRON86": "EPSG:9650",  # PL-KRON86-NH (unchanged)
    "EVRF2007": "EPSG:5621",  # pan-European EVRF2007 (decision 2026-08-11)
    "EVRF2007-PL": "EPSG:9651",  # Polish realization PL-EVRF2007-NH
    "Bpv": "EPSG:8357",  # Baltic 1957 (CZ)
}

# Family -> national realizations; consumed when building the sidecar: if the family
# code is absent from the channel's vertical_crs_options but its realization is
# present, the sidecar records the realization code (fact, not wish).
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
    attribution="SoilGrids - ISRIC World Soil Information, CC BY 4.0",
    url="https://www.isric.org/explore/soilgrids",
)

_CUZK_LICENSE = LicenseInfo(
    id="CC-BY-4.0",
    attribution="Podklad: Cesky urad zememericky a katastralni (CUZK), CC BY 4.0",
    url="https://geoportal.cuzk.gov.cz",
)

_PL_VERTICAL_BOTH = ("EPSG:9650", "EPSG:9651")

# --- Collection channels of GUGiK (ADR-042, plan C) ---------------------------
_OPENDATA = "https://opendata.geoportal.gov.pl"

# BDOT10k archive: yearly snapshots 2014-2025 (state at the start of the year)
# in GML and SHP, one ZIP per powiat (reconnaissance 2026-10-15: GPKG, 2013 and
# 2026 = 404). A GML package holds ``.xml`` files, a SHP package ``.shp``.
_BDOT10K_ARCHIVE = f"{_OPENDATA}/Archiwum/bdot10k"
_BDOT10K_ARCHIVE_YEARS = tuple(range(2014, 2026))
_BDOT10K_ARCHIVE_FORMATS = (("GML", ".xml"), ("SHP", ".shp"))


def _bdot10k_archive_variants() -> tuple[PackageVariant, ...]:
    return tuple(
        PackageVariant(
            choice=(("format", fmt), ("year", str(year))),
            url_template=(
                f"{_BDOT10K_ARCHIVE}/{year}/{fmt}/{{woj}}/{{teryt}}_{fmt}_{year}.zip"
            ),
            edition=str(year),
            segment_tokens=(fmt.lower(), str(year)),
            members=(member,),
        )
        for year in _BDOT10K_ARCHIVE_YEARS
        for fmt, member in _BDOT10K_ARCHIVE_FORMATS
    )


# 3D building models (CityGML, one ZIP per powiat): LoD1 yearly releases (2019
# with the ``_gml`` file name suffix) and the only LoD2 release, 2017. The
# vertical CRS is the one declared by ``srsName`` of the GML files (measured
# 2026-10-15 on powiat 0401: 2019 PL-KRON86-NH, 2021/2022 PL-EVRF2007-NH,
# 2024 EPSG::9651; LoD2 2017 PL-KRON86-NH).
_BUILDINGS_3D = f"{_OPENDATA}/InneDane/Budynki3D"
_BUILDINGS_3D_RELEASES = (
    ("1", "2019", f"{_BUILDINGS_3D}/LOD1/2019/{{woj}}/{{teryt}}_gml.zip", "EPSG:9650"),
    ("1", "2021", f"{_BUILDINGS_3D}/LOD1/2021/{{woj}}/{{teryt}}.zip", "EPSG:9651"),
    ("1", "2022", f"{_BUILDINGS_3D}/LOD1/2022/{{woj}}/{{teryt}}.zip", "EPSG:9651"),
    ("1", "2024", f"{_BUILDINGS_3D}/LOD1/2024/{{woj}}/{{teryt}}.zip", "EPSG:9651"),
    ("2", "2017", f"{_BUILDINGS_3D}/LOD2/{{teryt}}_gml.zip", "EPSG:9650"),
)


def _buildings_3d_variants() -> tuple[PackageVariant, ...]:
    return tuple(
        PackageVariant(
            choice=(("lod", lod), ("year", year)),
            url_template=url,
            edition=year,
            segment_tokens=(f"lod{lod}", year),
            members=(".gml",),
            vertical_crs=vertical,
        )
        for lod, year, url, vertical in _BUILDINGS_3D_RELEASES
    )


# PRG WFS levels (--level -> type of AdministrativeBoundaries); the stable
# feature key is IIP_IDENTY (gml:id is a page position, reconnaissance 2026-10-15).
_PRG_LEVELS = (
    ("wojewodztwo", "A01_Granice_wojewodztw"),
    ("powiat", "A02_Granice_powiatow"),
    ("gmina", "A03_Granice_gmin"),
    ("jednostka-ewidencyjna", "A05_Granice_jednostek_ewidencyjnych"),
    ("obreb", "A06_Granice_obrebow_ewidencyjnych"),
)

# EPSG code of the PL vertical CRS names in the channel options (sidecar).
_PL_VERTICAL_OPTION = {"KRON86": "EPSG:9650", "EVRF2007": "EPSG:9651"}

_PZGIK = "https://mapy.geoportal.gov.pl/wss/service/PZGIK"


def _wfs_index(service: str, prefix: str) -> dict[str, IndexRef]:
    """WFS sheet index per height system: ``<service><VCRS>/WFS/Skorowidze``."""
    return {
        vertical_crs: IndexRef(
            f"{_PZGIK}/{service}{vertical_crs}/WFS/Skorowidze", prefix
        )
        for vertical_crs in ("EVRF2007", "KRON86")
    }


# Sheet indexes of the PL elevation products (inventory 2026-10-15,
# docs/research/2026-10-15-plan-a-b/raport.md 1): one service per height system.
_PL_INDEX = {
    "nmt": _wfs_index("NumerycznyModelTerenu", "SkorowidzNMT"),
    "nmpt": _wfs_index("NumerycznyModelPokryciaTerenu", "SkorowidzNMPT"),
    "laz": _wfs_index("DanePomiaroweLidar", "SkorowidzDanychPomiarowychLIDAR"),
}

_PRODUCT_NAMES = {
    "nmt": "Numeryczny Model Terenu",
    "nmpt": "Numeryczny Model Pokrycia Terenu",
}

_NMT_WCS = AccessChannel(
    transport=TransportKind.WCS,
    update_signal="none",
    horizontal_crs="EPSG:2180",
    vertical_crs_options=_PL_VERTICAL_BOTH,
    capabilities=frozenset({"bbox_raster"}),
    notes=(
        "KRON86 GeoTIFF float32, EVRF2007 tylko image/x-aaigrid "
        "(zapisywany jako GeoTIFF float32); siatka arkuszy 1 m"
    ),
)
_NMPT_WCS = AccessChannel(
    transport=TransportKind.WCS,
    update_signal="none",
    horizontal_crs="EPSG:2180",
    vertical_crs_options=_PL_VERTICAL_BOTH,
    capabilities=frozenset({"bbox_raster"}),
    notes=(
        "wysokosci tylko image/x-aaigrid (zapisywany jako GeoTIFF "
        "float32); 1 m przez SCALEFACTOR=0.5 na siatce arkuszy 1 m"
    ),
)


def _pl_sheet_source(
    product: str,
    resolution: str | None,
    vertical_crs: tuple[str, ...],
    *,
    format: str = "ASC",
    key: str | None = None,
    wcs: AccessChannel | None = None,
) -> SourceDescriptor:
    """Descriptor of one PL sheet variant set: (product, format, resolution).

    One variant per height system in ``vertical_crs`` (ADR-041), records
    from the WFS index of the product (``_PL_INDEX``). The key, the segment
    template and the extension follow from the format and the label:
    grids ``pl.gugik.nmt_0_5m`` / ``nmt/pl_{system}_0.5m_{vcrs}``, archives
    ``pl.gugik.nmt_tbd_25m`` / ``nmt/pl_{system}_tbd_25m_{vcrs}`` (format
    token before the resolution, ARCHITECTURE 3.3 rule 1). ``key`` keeps
    the keys of existing sidecars (``pl.gugik.nmpt`` = NMPT 1 m).
    """
    fmt = file_format(format)
    value = parse_resolution(resolution) if resolution is not None else None
    if resolution is not None and value is None:
        raise ValueError(f"etykieta rozdzielczosci spoza K2: {resolution!r}")
    tokens = [format.lower()] if fmt.source_file else []
    if resolution is not None:
        tokens.append(resolution)
    if key is None:
        key_tokens = [t.replace("-", "_").replace(".", "_") for t in tokens]
        key = f"pl.gugik.{product}_{'_'.join(key_tokens)}"
    shown = f"{resolution.replace('.', ',')[:-1]} m" if resolution else None
    if fmt.source_file:
        name = (
            f"{_PRODUCT_NAMES[product]} - archiwum {format}"
            + (f" {shown}" if shown else "")
            + f" ({fmt.description}; plik zrodlowy)"
        )
    else:
        name = f"{_PRODUCT_NAMES[product]} {shown} (siatka ASC)"
    sheets = AccessChannel(
        transport=TransportKind.WFS,
        update_signal="index",
        horizontal_crs=PL_1992_CRS,  # PL-2000: zone from sheet code (N8)
        vertical_crs_options=tuple(
            code
            for code in _PL_VERTICAL_BOTH
            if code in {_PL_VERTICAL_OPTION[v] for v in vertical_crs}
        ),
        capabilities=frozenset({"sheet_files"}),
        notes=(
            "skorowidz WFS GUGiK; plik jak w zrodle (bez konwersji)"
            if fmt.source_file
            else "skorowidz WFS GUGiK; arkusze OpenData"
        ),
    )
    return SourceDescriptor(
        key=key,
        country="PL",
        product=product,
        name=name,
        provider_name="GUGiK",
        channels=(sheets,) if wcs is None else (sheets, wcs),
        tile_scheme=None,
        storage_subdir=f"{product}/pl_{{system}}_{'_'.join(tokens)}_{{vcrs}}",
        default_extension=fmt.extension,
        license=_GUGIK_LICENSE,
        resolution=resolution,
        variants=tuple(
            ProductVariant(
                source=key,
                product=product,
                country="PL",
                resolution_m=value,
                vertical_crs=name_vcrs,
                format=format,
                systems=("1992", "2000"),
                channel=TransportKind.WFS,
                index_ref=_PL_INDEX[product][name_vcrs],
            )
            for name_vcrs in vertical_crs
        ),
    )


_EVRF = ("EVRF2007",)
_KRON = ("KRON86",)
_BOTH = ("EVRF2007", "KRON86")

# PL sheet variants: every ASC grid of the WFS inventory 2026-10-15 and the
# archive formats downloaded as source files (decision 2026-10-15, ADR-041).
# ASCII NMT 10 m is absent: all its 215 sheets have 8-part codes outside the
# PL-1992 sheet system of SheetParser (reported by `availability` as Info).
_PL_SHEET_SOURCES = (
    _pl_sheet_source("nmt", "0.15m", _EVRF),
    _pl_sheet_source("nmt", "0.5m", _BOTH),
    _pl_sheet_source("nmt", "0.6m", _EVRF),
    _pl_sheet_source("nmt", "1m", _BOTH, wcs=_NMT_WCS),
    _pl_sheet_source("nmt", "5m", _EVRF),
    _pl_sheet_source("nmt", "10m", _EVRF),
    _pl_sheet_source("nmpt", "0.5m", _BOTH),
    _pl_sheet_source("nmpt", "0.6m", _EVRF),
    _pl_sheet_source("nmpt", "1m", _BOTH, key="pl.gugik.nmpt", wcs=_NMPT_WCS),
    _pl_sheet_source("nmt", "1m", _BOTH, format="XYZ"),
    _pl_sheet_source("nmt", "5m", _EVRF, format="XYZ"),
    _pl_sheet_source("nmt", "0.5m", _EVRF, format="ASCII-NMT"),
    _pl_sheet_source("nmt", "1m", _EVRF, format="ASCII-NMT"),
    _pl_sheet_source("nmt", "5m", _BOTH, format="ASCII-NMT"),
    _pl_sheet_source("nmt", "1m", _BOTH, format="TBD"),
    _pl_sheet_source("nmt", "5m", _BOTH, format="TBD"),
    _pl_sheet_source("nmt", "10m", _BOTH, format="TBD"),
    _pl_sheet_source("nmt", "15m", _BOTH, format="TBD"),
    _pl_sheet_source("nmt", "20m", _BOTH, format="TBD"),
    _pl_sheet_source("nmt", "25m", _BOTH, format="TBD"),
    _pl_sheet_source("nmt", "30m", _KRON, format="TBD"),
    _pl_sheet_source("nmt", "40m", _KRON, format="TBD"),
    _pl_sheet_source("nmt", "50m", _KRON, format="TBD"),
    _pl_sheet_source("nmt", None, _KRON, format="TIN"),
    _pl_sheet_source("nmt", None, _KRON, format="TTN"),
    _pl_sheet_source("nmt", "5m", _KRON, format="GRD"),
    _pl_sheet_source("nmt", "25m", _KRON, format="DXF"),
    _pl_sheet_source("nmt", "25m", _KRON, format="DGN"),
    _pl_sheet_source("nmpt", "0.5m", _KRON, format="XYZ"),
    _pl_sheet_source("nmpt", "1m", _KRON, format="XYZ"),
)

_SOURCES: dict[str, SourceDescriptor] = {
    d.key: d
    for d in (
        *_PL_SHEET_SOURCES,
        SourceDescriptor(
            key="pl.gugik.orto",
            country="PL",
            product="orto",
            name="Ortofotomapa Standard Resolution (25 cm)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    update_signal="index",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"sheet_files"}),
                ),
            ),
            tile_scheme=None,
            storage_subdir="orto/pl_{system}",
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
                    update_signal="index",
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"area_files"}),
                    notes="WMS skorowidzy LAZ zwraca 401 - WFS jedyna droga",
                ),
            ),
            tile_scheme=None,
            storage_subdir="laz/pl_{system}_{vcrs}",
            default_extension=".laz",
            license=_GUGIK_LICENSE,
            variants=tuple(
                ProductVariant(
                    source="pl.gugik.laz",
                    product="laz",
                    country="PL",
                    resolution_m=None,
                    vertical_crs=vertical_crs,
                    format="LAZ",
                    systems=("1992", "2000"),
                    channel=TransportKind.WFS,
                    index_ref=_PL_INDEX["laz"][vertical_crs],
                )
                for vertical_crs in _BOTH
            ),
        ),
        SourceDescriptor(
            key="pl.gugik.bdot10k",
            country="PL",
            product="landcover",
            name="BDOT10k - baza danych obiektow topograficznych",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    update_signal="none",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"admin_unit_files"}),
                ),
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    update_signal="none",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"archive_unit_files"}),
                    endpoint=f"{_BDOT10K_ARCHIVE}/",
                    notes=(
                        "archiwum rocznikow 2014-2025 (stan z poczatku roku), "
                        "GML albo SHP; paczka powiatu zapisywana 1:1"
                    ),
                    params=UnitPackageParams(
                        unit="powiat", variants=_bdot10k_archive_variants()
                    ),
                ),
            ),
            tile_scheme=None,
            storage_subdir="landcover/pl_bdot10k",
            default_extension=".gpkg",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="pl.gugik.prg",
            country="PL",
            product="admin",
            name="PRG - granice jednostek administracyjnych i ewidencyjnych",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WFS,
                    update_signal="none",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"bbox_vector"}),
                    endpoint=f"{_PZGIK}/PRG/WFS/AdministrativeBoundaries",
                    notes="pelne geometrie jednostek przecinajacych obszar",
                    params=FeatureBBoxParams(
                        protocol="wfs",
                        native_crs="EPSG:2180",
                        axis_order="yx",
                        page_size=1000,
                        layers=tuple(
                            FeatureLayer(
                                code=code,
                                source=f"ms:{name}",
                                name=name,
                                id_field="IIP_IDENTY",
                            )
                            for code, name in _PRG_LEVELS
                        ),
                        selection="level",
                    ),
                ),
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    update_signal="none",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"admin_unit_files"}),
                    endpoint=f"{_OPENDATA}/prg/granice/",
                    notes="paczka wojewodztwa: GML poziomow A01, A02, A03, A05, A06",
                    params=UnitPackageParams(
                        unit="woj",
                        variants=(
                            PackageVariant(
                                choice=(),
                                url_template=(
                                    f"{_OPENDATA}/prg/granice/"
                                    "{woj}_GraniceAdministracyjne.zip"
                                ),
                                segment_tokens=("gml",),
                                members=(".gml",),
                            ),
                        ),
                    ),
                ),
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    update_signal="none",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"country_files"}),
                    endpoint=f"{_OPENDATA}/prg/granice/",
                    notes="plik krajowy SHP (ok. 377 MB), tylko z --whole-country",
                    params=UnitPackageParams(
                        unit="country",
                        variants=(
                            PackageVariant(
                                choice=(),
                                url_template=(
                                    f"{_OPENDATA}/prg/granice/"
                                    "00_jednostki_administracyjne.zip"
                                ),
                                segment_tokens=("shp",),
                                members=(".shp",),
                            ),
                        ),
                    ),
                ),
            ),
            tile_scheme=None,
            storage_subdir="boundaries/pl_prg",
            default_extension=".gpkg",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="pl.gugik.egib",
            country="PL",
            product="map",
            name="EGiB - mapa ewidencyjna (dzialki i budynki)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    update_signal="none",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"admin_unit_files"}),
                    endpoint=f"{_OPENDATA}/InneDane/latest_exports/eziudp_wfs/GPKG/",
                    notes=(
                        "eksport powiatu odswiezany co dobe: warstwy dzialki, "
                        "budynki i transakcje (RCN)"
                    ),
                    params=UnitPackageParams(
                        unit="powiat",
                        variants=(
                            PackageVariant(
                                choice=(),
                                url_template=(
                                    f"{_OPENDATA}/InneDane/latest_exports/"
                                    "eziudp_wfs/GPKG/{teryt}.gpkg.zip"
                                ),
                                segment_tokens=("gpkg",),
                            ),
                        ),
                        unpack=".gpkg",
                    ),
                ),
                AccessChannel(
                    transport=TransportKind.WFS,
                    update_signal="none",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"bbox_vector"}),
                    endpoint=f"{_PZGIK}/EGIB/WFS/UslugaZbiorcza",
                    notes=(
                        "usluga zbiorcza powiatowych WFS: luki w powiatach bez "
                        "integracji, atrybuty zastrzezone = brak_uprawnien"
                    ),
                    params=FeatureBBoxParams(
                        protocol="wfs",
                        native_crs="EPSG:2180",
                        axis_order="yx",
                        page_size=1000,
                        layers=(
                            FeatureLayer(
                                code="dzialki",
                                source="ms:dzialki",
                                name="dzialki",
                                id_field="gml_id",
                            ),
                            FeatureLayer(
                                code="budynki",
                                source="ms:budynki",
                                name="budynki",
                                id_field="gml_id",
                            ),
                        ),
                        selection="all",
                        drop_fields=("DATA",),
                    ),
                ),
            ),
            tile_scheme=None,
            storage_subdir="cadastre/pl_egib",
            default_extension=".gpkg",
            license=_GUGIK_LICENSE,
        ),
        SourceDescriptor(
            key="pl.gugik.buildings_3d",
            country="PL",
            product="buildings",
            name="Modele 3D budynkow (CityGML LoD1, LoD2)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    update_signal="none",
                    horizontal_crs="EPSG:2180",
                    vertical_crs_options=_PL_VERTICAL_BOTH,
                    capabilities=frozenset({"admin_unit_files"}),
                    endpoint=f"{_BUILDINGS_3D}/",
                    notes=(
                        "LoD2 nie pokrywa calego kraju (brak paczki powiatu = "
                        "brak danych); pliki krajowe (3,5-4,1 GB) poza zakresem"
                    ),
                    params=UnitPackageParams(
                        unit="powiat", variants=_buildings_3d_variants()
                    ),
                ),
            ),
            tile_scheme=None,
            storage_subdir="models3d/pl_buildings",
            default_extension=".zip",
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
                    update_signal="metadata",
                    horizontal_crs="EPSG:3035",
                    capabilities=frozenset({"bbox_raster"}),
                    notes="wymaga credentials CLMS (CLMS_CREDENTIALS)",
                ),
                AccessChannel(
                    transport=TransportKind.WMS,
                    update_signal="none",
                    horizontal_crs="EPSG:3857",
                    capabilities=frozenset({"bbox_raster"}),
                    notes=(
                        "bez credentials CLMS: stylizowany PNG z WMS EEA - podglad, "
                        "nie dane; 1990: WMS DLR w EPSG:4326"
                    ),
                ),
            ),
            tile_scheme=None,
            storage_subdir="landcover/eu_corine",
            default_extension=".tif",
            license=_CLMS_LICENSE,
            auth="clms_oauth",
        ),
        SourceDescriptor(
            key="global.isric.soilgrids",
            country="GLOBAL",
            product="soil",
            name="SoilGrids - globalne dane glebowe",
            provider_name="ISRIC",
            channels=(
                AccessChannel(
                    transport=TransportKind.WCS,
                    update_signal="metadata",
                    horizontal_crs="EPSG:4326",
                    capabilities=frozenset({"bbox_raster"}),
                    notes="tylko WGS84 bbox; transformacja z EPSG:2180 automatyczna",
                ),
            ),
            tile_scheme=None,
            storage_subdir="soil/global_soilgrids",
            default_extension=".tif",
            license=_SOILGRIDS_LICENSE,
        ),
        SourceDescriptor(
            key="cz.cuzk.dmr5g",
            country="CZ",
            product="nmt",
            name="DMR 5G - Digitalni model reliefu (raster 2 m z exportImage)",
            provider_name="CUZK",
            channels=(
                AccessChannel(
                    transport=TransportKind.ARCGIS_IMAGE,
                    update_signal="none",
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
            name="DMR 4G - Digitalni model reliefu (GeoTIFF 5 m, arkusze SM5)",
            provider_name="CUZK",
            channels=(
                AccessChannel(
                    transport=TransportKind.DIRECT_FILES,
                    update_signal="http",
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
                    update_signal="none",
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


def channel_signal(key: str, transport: TransportKind) -> SignalKind:
    """Freshness signal of the ``transport`` channel of source ``key``.

    Raises
    ------
    ValidationError
        Unknown source or a source without such a channel.
    """
    source = _SOURCES.get(key)
    if source is None:
        raise ValidationError(f"Nieznane zrodlo: '{key}'. Dostepne: {sorted(_SOURCES)}")
    for channel in source.channels:
        if channel.transport == transport:
            return channel.update_signal
    raise ValidationError(
        f"Zrodlo '{key}' nie ma kanalu {transport.value!r} "
        f"(kanaly: {[c.transport.value for c in source.channels]})"
    )


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


def all_sources() -> list[SourceDescriptor]:
    """Every registered descriptor in registry order (variants, tests)."""
    return list(_SOURCES.values())


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
    """EPSG code of a CRS name given the channel options (family -> realization)."""
    code = vertical_crs_code(name)
    if code in options:
        return code
    for realization in _VERTICAL_FAMILY.get(code, ()):
        if realization in options:
            return realization
    return code


def horizontal_crs_for_sheet(sheet: str) -> str:
    """Horizontal CRS of a PL sheet code: PL-1992 -> 2180, PL-2000 -> its zone."""
    parser = SheetParser(sheet)
    if parser.sheet_system == "2000":
        return ZONE_EPSG[int(parser.sheet.split(".")[0])]
    return PL_1992_CRS


def parse_pl_system(value: str | None) -> tuple[str, int | None] | None:
    """The ONLY parser of GUGiK horizontal CRS values (review-1 D3, E11).

    The index fields ``ukladWspolrzednychPoziomych``/``ukladWspolrzednych``
    and WFS LAZ ``uklad_xy``: ``"PL-1992"`` -> ``("1992", None)``,
    ``"PL-2000:S5"``..``"PL-2000:S8"`` -> ``("2000", zone)``. Surrounding
    whitespace is stripped; any other value (``"PL-2000"`` without a zone,
    ``"PL-2000:S9"``, different letter case, ``None``) -> ``None``. Real GUGiK
    data (E2E 2026-10-06) contains only recognized values.

    Consumers (index record selection, ``horizontal_crs_for_system``,
    ``LazTile.system``) treat ``None`` consistently: the record/tile is rejected
    or an explicit error is raised - never a ``pl_2000`` segment with an EPSG:2180
    sidecar.
    """
    text = (value or "").strip()
    if text == "PL-1992":
        return "1992", None
    match = re.fullmatch(r"PL-2000:S([5-8])", text)
    return ("2000", int(match[1])) if match else None


def horizontal_crs_for_system(system: str | None) -> str | None:
    """EPSG code from a GUGiK CRS name ("PL-1992", "PL-2000:S6"); None if unknown.

    Value recognition: ``parse_pl_system`` (shared with the index and LAZ).
    """
    parsed = parse_pl_system(system)
    if parsed is None:
        return None
    _system, zone = parsed
    return ZONE_EPSG[zone] if zone is not None else PL_1992_CRS
