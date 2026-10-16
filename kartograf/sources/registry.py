"""
Registry of data sources and countries.

Descriptors are the source of truth for storage_subdir (segment templates,
ADR-026), default_extension, licenses, vertical options and capabilities
(consumed by: sidecar + consistency tests). Capabilities select the channel
in the sidecar; managers do not enforce them.
"""

import re
from decimal import Decimal
from typing import Literal

from kartograf.core.parser_2000 import ZONE_EPSG
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import ValidationError
from kartograf.sources.descriptor import (
    AccessChannel,
    AtomFilesParams,
    CountryProfile,
    FeatureBBoxParams,
    FeatureLayer,
    IndexSource,
    LicenseInfo,
    PackageVariant,
    SheetGrid,
    SheetIndexParams,
    SignalKind,
    SourceDescriptor,
    TileScheme,
    TransportKind,
    UnitPackageParams,
    WcsCutoutParams,
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
# ASCII NMT 10 m lies on 215 8-part sheets (in SheetParser since plan E1; the
# ZIP holds points every 0.5 m although the index declares 10 m - the record
# label names the variant, as for every archive).
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
    _pl_sheet_source("nmt", "10m", _EVRF, format="ASCII-NMT"),
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

# --- CUZK (CZ, plan B) -----------------------------------------------------------
_AGS = "https://ags.cuzk.gov.cz/arcgis2/rest/services"
# Horizontal CRS of the CZ sheet systems (``ProductVariant.systems``): SM5 sheets
# in S-JTSK / Krovak, TM33 tiles 2x2 km in ETRS89 / TM33N.
CZ_SYSTEM_CRS = {"sm5": "EPSG:5514", "tm33": "EPSG:3045"}
# Height system of the CUZK files of a sheet system: S-JTSK files in Bpv, ETRS89
# files in EVRF2007 (CSW metadata of the datasets; research 2026-10-15, 3.3).
_CZ_FILE_VERTICAL = {"sm5": "Bpv", "tm33": "EVRF2007"}
_CZ_VERTICAL = ("Bpv", "EVRF2007")
_CZ_FILE_NOTES = {
    "sm5": "arkusze SM5 (S-JTSK, wysokosci Bpv); plik 1:1 z ZIP, CRS z kanalu",
    "tm33": "kafle TM33 2x2 km (ETRS89, wysokosci EVRF2007); plik 1:1 z ZIP",
}
_CZ_TM33_SCHEME = TileScheme(
    kind="computable",
    crs="EPSG:3045",
    width_m=2000.0,
    height_m=2000.0,
    description="TM33 {E_km}_{N_km}, naroznik SW",
)
_CZ_SM5_SCHEME = TileScheme(
    kind="index",
    crs="EPSG:5514",
    width_m=2500.0,
    height_m=2000.0,
    description=(
        "SM5: 2 albo 4 litery miasta + 2 cyfry (indeks KladyMapovychListu w. 24); "
        "kafle TM33 {E_km}_{N_km} (w. 26)"
    ),
)


def _cz_image(service: str) -> AccessChannel:
    """ImageServer of a CUZK model: requests only in EPSG:5514 + Bpv (ADR-024)."""
    return AccessChannel(
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
        endpoint=f"{_AGS}/{service}/ImageServer",
    )


def _cz_files(directory: str, system: str) -> AccessChannel:
    """openzu files of one sheet system (one ZIP per sheet, signal ``http``)."""
    crs = CZ_SYSTEM_CRS[system]
    return AccessChannel(
        transport=TransportKind.DIRECT_FILES,
        update_signal="http",
        horizontal_crs=crs,
        vertical_crs_options=(_VERTICAL_CRS_CODES[_CZ_FILE_VERTICAL[system]],),
        capabilities=frozenset({"sheet_files"}),
        endpoint=f"{_CUZK_OPENZU}/{directory}/epsg-{crs.split(':')[1]}/{{sheet}}.zip",
        notes=_CZ_FILE_NOTES[system],
    )


def _cz_raster_source(
    model: str,
    product: str,
    resolution: str,
    name: str,
    service: str,
    files: str | None,
) -> SourceDescriptor:
    """A CUZK raster model: the rows of the route table (plan B, decision 2).

    With files (``files`` = the openzu directory, e.g. ``DMR4G-TIFF``): SM5
    sheets from the S-JTSK file in Bpv and EVRF2007 (pinned operation), TM33
    tiles from the ETRS89 file in EVRF2007 (native) and from the ImageServer
    warped onto the tile grid in Bpv. Without files: TM33 tiles from the
    ImageServer in both height systems, no SM5 sheets. A cutout is the
    ImageServer channel (not a row).
    """
    key = f"cz.cuzk.{model}"
    value = parse_resolution(resolution)
    if value is None:
        raise ValueError(f"etykieta rozdzielczosci spoza K2: {resolution!r}")
    rows = []
    for system in ("sm5", "tm33"):
        for vertical_crs in _CZ_VERTICAL:
            if files is None and system == "sm5":
                continue
            from_file = files is not None and (
                system == "sm5" or vertical_crs == _CZ_FILE_VERTICAL[system]
            )
            rows.append(
                ProductVariant(
                    source=key,
                    product=product,
                    country="CZ",
                    resolution_m=value,
                    vertical_crs=vertical_crs,
                    format="TIFF",
                    systems=(system,),
                    channel=(
                        TransportKind.DIRECT_FILES
                        if from_file
                        else TransportKind.ARCGIS_IMAGE
                    ),
                    index_ref=None,
                    model=model,
                )
            )
    file_channels = (
        ()
        if files is None
        else tuple(_cz_files(files, system) for system in ("sm5", "tm33"))
    )
    return SourceDescriptor(
        key=key,
        country="CZ",
        product=product,
        name=name,
        provider_name="CUZK",
        channels=(*file_channels, _cz_image(service)),
        tile_scheme=_CZ_TM33_SCHEME if files is None else _CZ_SM5_SCHEME,
        storage_subdir=f"{product}/cz_{model}_{{vcrs}}",
        default_extension=".tif",
        license=_CUZK_LICENSE,
        resolution=resolution,
        variants=tuple(rows),
    )


def _cz_laz_source(model: str, directory: str, name: str) -> SourceDescriptor:
    """Point clouds of a CUZK model: S-JTSK sheets in Bpv, ETRS89 tiles in
    EVRF2007 - the file as published, never transformed."""
    key = f"cz.cuzk.{model}_laz"
    return SourceDescriptor(
        key=key,
        country="CZ",
        product="laz",
        name=name,
        provider_name="CUZK",
        channels=tuple(_cz_files(directory, system) for system in ("sm5", "tm33")),
        tile_scheme=_CZ_SM5_SCHEME,
        storage_subdir=f"laz/cz_{model}_{{vcrs}}",
        default_extension=".laz",
        license=_CUZK_LICENSE,
        variants=tuple(
            ProductVariant(
                source=key,
                product="laz",
                country="CZ",
                resolution_m=None,
                vertical_crs=_CZ_FILE_VERTICAL[system],
                format="LAZ",
                systems=(system,),
                channel=TransportKind.DIRECT_FILES,
                index_ref=None,
                model=model,
            )
            for system in ("sm5", "tm33")
        ),
    )


# CZ collections (plan D, ADR-042 D15-D17). Area results come from the
# services in their DefaultCRS (EPSG:5514); national files from CUZK in the
# CRS of the file (ATOM category / file name).
_CUZK_ARCGIS = "https://ags.cuzk.gov.cz/arcgis/rest/services"
_CUZK_OPENZU = "https://openzu.cuzk.gov.cz/opendata"
_CUZK_ATOM = "https://atom.cuzk.gov.cz"

# ZABAGED land cover and hydrography layers (ADR-042 D15): the ArcGIS REST
# layer id and its code = the layer name without diacritics, lower case,
# runs outside [a-z0-9] as "_" (ZABAGED_POLOHOPIS/MapServer?f=pjson,
# 2026-10-15). The codes are the GPKG layer names; no translation of the
# classes to BDOT10k codes. Lines: 93, 112; the rest polygons.
_ZABAGED_LAYERS = (
    ("93", "vodni_tok"),
    ("99", "budova_jednotliva_nebo_blok_budov_plocha"),
    ("112", "brehova_cara"),
    ("114", "areal_ucelove_zastavby"),
    ("115", "ostatni_plocha_v_sidlech"),
    ("116", "hrbitov"),
    ("117", "skladka"),
    ("118", "povrchova_tezba_lom"),
    ("129", "sesuv_pudy_sut"),
    ("130", "skalni_utvary"),
    ("131", "bazina_mocal"),
    ("132", "vodni_plocha"),
    ("134", "udrzovana_zelen"),
    ("135", "ovocny_sad_zahrada"),
    ("136", "vinice"),
    ("137", "chmelnice"),
    ("138", "orna_puda_a_ostatni_dale_nespecifikovane_plochy"),
    ("139", "trvaly_travni_porost"),
    ("140", "lesni_puda_s_krovinatym_porostem"),
    ("141", "lesni_puda_s_kosodrevinou"),
    ("142", "lesni_puda_se_stromy"),
    ("144", "lesni_puda_se_stromy_kategorizovana_plocha"),
)

_CZ_ZABAGED = SourceDescriptor(
    key="cz.cuzk.zabaged",
    country="CZ",
    product="landcover",
    name="ZABAGED - Zakladni baze geografickych dat CR (pokrycie terenu i wody)",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.ARCGIS_QUERY,
            update_signal="none",
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"bbox_vector"}),
            endpoint=f"{_CUZK_ARCGIS}/ZABAGED_POLOHOPIS/MapServer",
            notes=(
                "22 warstwy pokrycia terenu i hydrografii (nazwy zrodla); pelne "
                "geometrie obiektow przecinajacych obszar"
            ),
            params=FeatureBBoxParams(
                protocol="arcgis",
                native_crs="EPSG:5514",
                axis_order="xy",
                page_size=2000,
                layers=tuple(
                    FeatureLayer(code=code, source=layer, name=code, id_field="fid_zbg")
                    for layer, code in _ZABAGED_LAYERS
                ),
                selection="all",
                order_field="OBJECTID",
            ),
        ),
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="metadata",
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"country_files"}),
            endpoint=f"{_CUZK_ATOM}/ZABAGED-GPKG/ZABAGED-GPKG.xml",
            notes=(
                "plik krajowy GPKG (5,8 GB EPSG:5514, 6,7 GB EPSG:3045; warstwy "
                "pelnej bazy pod nazwami CUZK), tylko z --whole-country"
            ),
            params=AtomFilesParams(
                service_feed=f"{_CUZK_ATOM}/ZABAGED-GPKG/ZABAGED-GPKG.xml",
                entry_pattern=r"CUZK_ZABAGED-GPKG_[0-9]+\.xml$",
                crs=("EPSG:5514", "EPSG:3045"),
                segment_tokens=("gpkg",),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="landcover/cz_zabaged",
    default_extension=".gpkg",
    license=_CUZK_LICENSE,
)

# RUIAN levels (ADR-042 D17): --level code -> layer of RUIAN/MapServer.
_RUIAN_LEVELS = (
    ("kraj", "17", "VyssiUzemneSamospravnyCelek"),
    ("okres", "15", "Okres"),
    ("obec", "12", "Obec"),
    ("katastralni-uzemi", "7", "KatastralniUzemi"),
)

_CZ_RUIAN = SourceDescriptor(
    key="cz.cuzk.ruian",
    country="CZ",
    product="admin",
    name="RUIAN - granice jednostek terytorialnych (kraje, okresy, obce, k.u.)",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.ARCGIS_QUERY,
            update_signal="none",
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"bbox_vector"}),
            endpoint=f"{_CUZK_ARCGIS}/RUIAN/MapServer",
            notes="pelne geometrie jednostek przecinajacych obszar",
            params=FeatureBBoxParams(
                protocol="arcgis",
                native_crs="EPSG:5514",
                axis_order="xy",
                page_size=1000,
                layers=tuple(
                    FeatureLayer(code=code, source=layer, name=name, id_field="kod")
                    for code, layer, name in _RUIAN_LEVELS
                ),
                selection="level",
                order_field="objectid",
            ),
        ),
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="http",
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"country_files"}),
            endpoint="https://services.cuzk.gov.cz/shp/stat/epsg-5514/",
            notes="plik krajowy SHP (ok. 253 MB), tylko z --whole-country",
            params=UnitPackageParams(
                unit="country",
                variants=(
                    PackageVariant(
                        choice=(),
                        url_template="https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip",
                        segment_tokens=("shp",),
                        members=(".shp",),
                    ),
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="boundaries/cz_ruian",
    default_extension=".gpkg",
    license=_CUZK_LICENSE,
)

_CZ_HY_NET = SourceDescriptor(
    key="cz.cuzk.hy_net",
    country="CZ",
    product="network",
    name="HY-NET - siec hydrograficzna (INSPIRE Hydrography - Network)",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.WFS,
            update_signal="none",
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"bbox_vector"}),
            endpoint="https://geoportal.cuzk.gov.cz/geoserver/hy-n/wfs",
            notes=(
                "odcinki ciekow i wezly sieci przecinajace obszar (skrzyzowania "
                "bezkolizyjne - relacje bez geometrii - tylko w pliku krajowym)"
            ),
            params=FeatureBBoxParams(
                protocol="wfs",
                native_crs="EPSG:5514",
                axis_order="xy",
                page_size=1000,
                # No WatercourseSeparatedCrossing: its GML has no geometry (a
                # relation of two links) and GeoServer answers RESULTTYPE=hits
                # with a BBOX by 0 while the pages hold objects (2026-10-16:
                # 30 x 30 km 0 vs 4, 100 x 100 km 0 vs 24), so completeness
                # cannot be checked; the national file has the crossings.
                layers=tuple(
                    FeatureLayer(
                        code=name, source=f"hy-n:{name}", name=name, id_field="gml_id"
                    )
                    for name in ("WatercourseLink", "HydroNode")
                ),
                selection="all",
            ),
        ),
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="http",
            horizontal_crs="EPSG:3045",
            capabilities=frozenset({"country_files"}),
            endpoint=f"{_CUZK_OPENZU}/HY-NET/",
            notes=(
                "plik krajowy GPKG (ok. 194 MB) w EPSG:3045 (kategoria feedu ATOM), "
                "tylko z --whole-country"
            ),
            params=UnitPackageParams(
                unit="country",
                variants=(
                    PackageVariant(
                        choice=(),
                        url_template=f"{_CUZK_OPENZU}/HY-NET/HY-NET.zip",
                        segment_tokens=("gpkg",),
                        members=(".gpkg",),
                    ),
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="hydro/cz_hynet",
    default_extension=".gpkg",
    license=_CUZK_LICENSE,
)

# Orthophotomap WCS (DescribeCoverage 2.0.1, 2026-10-16): Standard and High
# share one national grid with a 0.1 m step, the true orthophotomap has a
# 0.05 m grid; the cutout pixel is a choice (SCALEFACTOR). One GetCoverage
# reads at most 4 Mpx of coverage = 200 x 200 m at 0.1 m (64 s live
# 2026-10-15, docs/research/2026-10-15-plan-c-d/raport.md).
_ORTO_WCS = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WCS"
_ORTO_PIXELS = ("0.1", "0.25", "0.5", "1")


def _orto_wcs(
    service: str,
    variant: str,
    coverage_id: str,
    notes: str,
    *,
    native_step: str,
    resolutions: tuple[str, ...],
) -> AccessChannel:
    """WCS cutout channel of an orthophotomap (ADR-042 D14); ``notes`` = the
    meaning of ``variant`` named in messages (abstract of the service)."""
    return AccessChannel(
        transport=TransportKind.WCS,
        update_signal="none",
        horizontal_crs=PL_1992_CRS,
        capabilities=frozenset({"bbox_raster"}),
        notes=notes,
        endpoint=f"{_ORTO_WCS}/{service}",
        params=WcsCutoutParams(
            variant=variant,
            coverage_id=coverage_id,
            native_step=Decimal(native_step),
            resolutions=tuple(Decimal(v) for v in resolutions),
            max_native_pixels=4_000_000,
        ),
    )


# CUZK products (research 2026-10-15, 3.1-3.3): DMR 5G and DMP 1G have no
# raster files (DMR5G-TIFF/DMP1G-TIFF = 404), every model has LAZ files.
_CZ_SOURCES = (
    _cz_raster_source(
        "dmr5g",
        "nmt",
        "2m",
        "DMR 5G - Digitalni model reliefu 5. generace (2 m, ImageServer: kafel "
        "TM33 i wycinek)",
        "dmr5g",
        None,
    ),
    _cz_raster_source(
        "dmr4g",
        "nmt",
        "5m",
        "DMR 4G - Digitalni model reliefu 4. generace (5 m, arkusze SM5 i kafle TM33)",
        "dmr4g",
        "DMR4G-TIFF",
    ),
    _cz_raster_source(
        "dmp1g",
        "nmpt",
        "2m",
        "DMP 1G - Digitalni model povrchu 1. generace (2 m, ImageServer: kafel "
        "TM33 i wycinek)",
        "dmp1g",
        None,
    ),
    _cz_raster_source(
        "dmpok",
        "nmpt",
        "0.5m",
        "DMP OK - Digitalni model povrchu z obrazove korelace (0,5 m, arkusze "
        "SM5 i kafle TM33)",
        "dmp_obrazova_korelace",
        "DMPOK-TIFF",
    ),
    _cz_laz_source(
        "dmr5g", "DMR5G", "DMR 5G - chmura punktow LAZ (arkusze SM5 i kafle TM33)"
    ),
    _cz_laz_source(
        "dmr4g",
        "DMR4G",
        "DMR 4G - chmura punktow LAZ (siatka 5 m; arkusze SM5 i kafle TM33)",
    ),
    _cz_laz_source(
        "dmp1g", "DMP1G", "DMP 1G - chmura punktow LAZ (arkusze SM5 i kafle TM33)"
    ),
    _cz_laz_source(
        "dmpok",
        "DMPOK-LAZ",
        "DMP OK - chmura punktow LAZ (korelacja obrazowa; arkusze SM5 i kafle TM33)",
    ),
)

# Orthophoto of CR (ADR-042 D13): one ZIP per SM5 sheet listed by the ORTOFOTO
# ATOM feed (the release year is in the file name, so the URL exists only in
# the feed); the JPEG and its three world files are stored 1:1.
_ORTOFOTO_FEED = f"{_CUZK_ATOM}/ORTOFOTO/ORTOFOTO.xml"
_CZ_ORTOFOTO = SourceDescriptor(
    key="cz.cuzk.ortofoto",
    country="CZ",
    product="orto",
    name="Ortofoto CR (JPEG, arkusze SM5)",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="metadata",
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"sheet_files"}),
            endpoint=_ORTOFOTO_FEED,
            notes=(
                "aktualny rocznik arkusza (archiwalne ortofoto CUZK sa platne - "
                "poza zakresem); JPEG z plikami JGW w S-JTSK, TM33N i TM34N"
            ),
            params=AtomFilesParams(
                service_feed=_ORTOFOTO_FEED,
                entry_pattern=(
                    r"ORTOFOTO_WRTO24\.(?P<year>[0-9]{4})\."
                    r"(?P<sheet>[A-Z]{2,4}[0-9]{2})\.xml$"
                ),
                members=(
                    (".jpg", ".jpg"),
                    (".jgw", ".jgw"),
                    (".TM33N.jgw", ".TM33N.jgw"),
                    (".TM34N.jgw", ".TM34N.jgw"),
                ),
            ),
        ),
    ),
    tile_scheme=TileScheme(
        kind="index",
        crs="EPSG:5514",
        width_m=2500.0,
        height_m=2000.0,
        description=(
            "SM5: 2 albo 4 litery miasta + 2 cyfry; indeks KladyMapovychListu w. 24"
        ),
    ),
    storage_subdir="orto/cz_sjtsk",
    default_extension=".jpg",
    license=_CUZK_LICENSE,
)

# --- plan E - E1 (PL) -------------------------------------------------------------
# NMT 100 m (raport E, wiersz 1; feeds recorded 2026-10-16): one ATOM dataset per
# voivodeship (dataset feed id ``...spatial_dataset_identifier_code=NMT100_<woj>``),
# one ZIP with an XYZ text file each. The feeds link everything with http://, the
# host answers over https. Neither the feeds nor the CSW record declare a height
# system (decision P1 of 2026-10-15: unknown; no {vcrs} in the segment).
_NMT100_FEED = (
    "https://mapy.geoportal.gov.pl/wss/service/ATOM/httpauth/atom/GUGIK_NMT100"
)
_NMT100_NOTE = (
    "GUGiK nie deklaruje ukladu wysokosci NMT 100 m (feed ATOM i rekord CSW bez "
    "ukladu; model z NMT projektu LPIS) - uklad wysokosci nieznany"
)
_PL_NMT_100M = SourceDescriptor(
    key="pl.gugik.nmt_100m",
    country="PL",
    product="nmt",
    name="Numeryczny Model Terenu 100 m (XYZ, pliki wojewodztw; uklad wysokosci "
    "nieznany)",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="metadata",
            horizontal_crs=PL_1992_CRS,
            capabilities=frozenset({"admin_unit_files"}),
            endpoint=_NMT100_FEED,
            notes=(
                "feed ATOM GUGiK: jeden ZIP z plikiem XYZ na wojewodztwo (wydanie "
                "2019); wojewodztwa obszaru wg PRG; ZIP zapisywany 1:1"
            ),
            params=AtomFilesParams(
                service_feed=_NMT100_FEED,
                entry_pattern=r"spatial_dataset_identifier_code=NMT100_(?P<woj>[0-9]{2})",
                force_https=True,
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="nmt/pl_1992_100m",
    default_extension=".zip",
    license=_GUGIK_LICENSE,
    resolution="100m",
    variants=(
        ProductVariant(
            source="pl.gugik.nmt_100m",
            product="nmt",
            country="PL",
            resolution_m=Decimal("100"),
            vertical_crs=None,
            format="XYZ",
            systems=("1992",),
            channel=TransportKind.DIRECT_FILES,
            index_ref=None,
            vertical_note=_NMT100_NOTE,
        ),
    ),
)

# Image products on GUGiK WMS sheet indexes (raport E, wiersze 2-4; GFI recorded
# 2026-10-16, tests/fixtures/pl/{intensity,orto_true,orto_oblique}): one layer of
# records each (intensity: PL-1992 and PL-2000 sheets in one layer; true orto:
# 8-part PL-1992 codes; oblique: one layer per view direction, PL-2000 sheets of
# 1:2000 and 1:1000). The layers are fixed, no GetCapabilities; the records of
# intensity and true orto have no calyArkuszWypelnionyTrescia.
_PL_INTENSITY = SourceDescriptor(
    key="pl.gugik.intensity",
    country="PL",
    product="intensity",
    name="Obrazy intensywnosci LIDAR (arkusze wg lotow)",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.WMS_SHEET_INDEX,
            update_signal="index",
            horizontal_crs=PL_1992_CRS,
            capabilities=frozenset({"sheet_files"}),
            endpoint=f"{_PZGIK}/OI/WMS/SkorowidzeObrazowIntensywnosci",
            notes=(
                "GeoTIFF 1 pasmo (intensywnosc odbicia), piksel 0,25 m; arkusze "
                "PL-1992 (godla 7-czlonowe) i PL-2000 wg lotow"
            ),
            params=SheetIndexParams(
                layers=("SkorowidzeOI",),
                systems=("1992", "2000"),
                sheet_parts=7,
                full_sheet=False,
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="intensity/pl_{system}",
    default_extension=".tif",
    license=_GUGIK_LICENSE,
)
_PL_ORTO_TRUE = SourceDescriptor(
    key="pl.gugik.orto_true",
    country="PL",
    product="true-orto",
    name="Prawdziwa ortofotomapa (true orto) wybranych miast (arkusze; wycinek WCS)",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.WMS_SHEET_INDEX,
            update_signal="index",
            horizontal_crs=PL_1992_CRS,
            capabilities=frozenset({"sheet_files"}),
            endpoint=f"{_PZGIK}/ORTO/WMS/TrueOrtho",
            notes=(
                "GeoTIFF RGB, piksel 0,05 m; arkusze PL-1992 8-czlonowe (modul "
                "GUGiK 1:2500) wg lotow"
            ),
            params=SheetIndexParams(
                layers=("Skorowidze",),
                systems=("1992",),
                sheet_parts=8,
                full_sheet=False,
                extent="true orto GUGiK obejmuje tylko wybrane miasta (np. Gdansk)",
            ),
        ),
        _orto_wcs(
            "TrueOrto",
            "true",
            "True_Orthoimagery",
            "prawdziwa ortofotomapa 0,05 m wybranych miast (poza nimi piksele 0,0,0)",
            native_step="0.05",
            resolutions=("0.05", *_ORTO_PIXELS),
        ),
    ),
    tile_scheme=None,
    storage_subdir="orto/pl_{system}_true",
    default_extension=".tif",
    license=_GUGIK_LICENSE,
)
_OBLIQUE_LAYER = "SkorowidzeOrtofotomapyUkosnej"
_PL_ORTO_OBLIQUE = SourceDescriptor(
    key="pl.gugik.orto_oblique",
    country="PL",
    product="oblique-orto",
    name="Ortofotomapa ukosna wybranych miast (arkusze PL-2000, kierunki N, E, S, W)",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.WMS_SHEET_INDEX,
            update_signal="index",
            horizontal_crs=PL_1992_CRS,
            capabilities=frozenset({"sheet_files"}),
            endpoint=f"{_PZGIK}/ORTO/WMS/{_OBLIQUE_LAYER}",
            notes=(
                "GeoTIFF RGB, piksel 0,05 m; arkusz to 4 pliki kierunkow (n, e, s, "
                "w); arkusze PL-2000 (1:2000, 1:1000) wg lotow"
            ),
            params=SheetIndexParams(
                layers=(),
                systems=("2000",),
                sheet_parts=7,
                full_sheet=True,
                directions=tuple(
                    (code, f"{_OBLIQUE_LAYER}-{name}")
                    for code, name in (
                        ("n", "Polnoc"),
                        ("e", "Wschod"),
                        ("s", "Poludnie"),
                        ("w", "Zachod"),
                    )
                ),
                extent=(
                    "orto ukosna GUGiK obejmuje tylko wybrane miasta (np. Krakow, "
                    "Gdansk)"
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="orto/pl_{system}_oblique",
    default_extension=".tif",
    license=_GUGIK_LICENSE,
)
_E1_PL_SOURCES = (_PL_NMT_100M, _PL_INTENSITY, _PL_ORTO_TRUE, _PL_ORTO_OBLIQUE)

# --- plan E - E1 (CZ) -------------------------------------------------------------
# ZABAGED 2D contours (raport E, wiersz 16; HEAD recorded 2026-10-16,
# tests/fixtures/cz/contours): one ZIP per SM5 sheet on openzu, S-JTSK with heights
# in Bpv, ETag and Last-Modified; SHP (8 files) and DGN (3 files) in two
# directories - one descriptor per format, as the PL archive formats. The ZIP is
# kept as published. The ATOM feed of the dataset (16 301 entries) and the REST
# service stay unused: the sheet URL is a template (plan E, decision 7).
_CZ_CONTOURS_FORMATS = (("SHP", "ZABAGED-vyskopis"), ("DGN", "ZABAGED-vyskopis-DGN"))


def _cz_contours_source(fmt: str, directory: str) -> SourceDescriptor:
    """ZABAGED contours in ``fmt``: the openzu ZIP of an SM5 sheet (signal ``http``)."""
    key = f"cz.cuzk.zabaged_contours_{fmt.lower()}"
    return SourceDescriptor(
        key=key,
        country="CZ",
        product="contours",
        name=f"ZABAGED - warstwice 2D (vrstevnice; {fmt}, ZIP arkusza SM5)",
        provider_name="CUZK",
        channels=(
            AccessChannel(
                transport=TransportKind.DIRECT_FILES,
                update_signal="http",
                horizontal_crs=CZ_SYSTEM_CRS["sm5"],
                vertical_crs_options=(_VERTICAL_CRS_CODES["Bpv"],),
                capabilities=frozenset({"sheet_files"}),
                endpoint=f"{_CUZK_OPENZU}/{directory}/epsg-5514/{{sheet}}.zip",
                notes=(
                    "arkusze SM5 (S-JTSK, wysokosci Bpv); ZIP zapisywany 1:1, bez "
                    "rozpakowania i konwersji"
                ),
            ),
        ),
        tile_scheme=_CZ_SM5_SCHEME,
        storage_subdir=f"contours/cz_zabaged_{fmt.lower()}",
        default_extension=".zip",
        license=_CUZK_LICENSE,
        variants=(
            ProductVariant(
                source=key,
                product="contours",
                country="CZ",
                resolution_m=None,
                vertical_crs="Bpv",
                format=fmt,
                systems=("sm5",),
                channel=TransportKind.DIRECT_FILES,
                index_ref=None,
            ),
        ),
    )


_E1_CZ_SOURCES = tuple(
    _cz_contours_source(fmt, directory) for fmt, directory in _CZ_CONTOURS_FORMATS
)

# plan E - E2: geographic names and published topographic map sheets.
_PRNG_API = "https://ogcapi.geoportal.gov.pl/res/ims/maps/PRNG/apiFeatures"
_BDOT10K_MAP_INDEX = IndexSource(
    kind="wms_gfi",
    endpoint=f"{_PZGIK}/BDOT/WMS/PobieranieArkuszeMapBDOT10k",
    parser="map_links",
    unit_field="godlo",
    url_field=None,
    label_fields=("stan_bazy",),
)


def _prng_source(*, world: bool) -> SourceDescriptor:
    product = "world" if world else "geographic"
    source = "prng_world" if world else "prng"
    collection = "PolskaNazwaGeograficznaSwiata" if world else "NazwaGeograficznaRP"
    themes = ("SWIAT",) if world else ("MIEJSCOWOSCI", "OBIEKTY_FIZJOGRAFICZNE")
    return SourceDescriptor(
        key=f"pl.gugik.{source}",
        country="PL",
        product=product,
        name=(
            "PRNG - polskie nazwy geograficzne swiata"
            if world
            else "PRNG - nazwy geograficzne RP"
        ),
        provider_name="GUGiK",
        channels=(
            AccessChannel(
                transport=TransportKind.OGC_API_FEATURES,
                horizontal_crs="OGC:CRS84",
                capabilities=frozenset({"bbox_vector"}),
                endpoint=_PRNG_API,
                update_signal="none",
                params=FeatureBBoxParams(
                    protocol="ogcapi",
                    native_crs="OGC:CRS84",
                    axis_order="xy",
                    page_size=10000,
                    layers=(
                        FeatureLayer(
                            code=product,
                            source=collection,
                            name="prng_world" if world else "prng",
                            id_field="id",
                        ),
                    ),
                    selection="all",
                    timeout=180,
                ),
            ),
            AccessChannel(
                transport=TransportKind.DIRECT_FILES,
                horizontal_crs="EPSG:2180" if not world else "EPSG:4326",
                capabilities=frozenset({"country_files"}),
                endpoint=f"{_OPENDATA}/prng/",
                update_signal="none",
                params=UnitPackageParams(
                    unit="country",
                    themes=themes,
                    variants=tuple(
                        PackageVariant(
                            choice=(("format", fmt),),
                            url_template=f"{_OPENDATA}/prng/PRNG_{{theme}}_{fmt}.zip",
                            segment_tokens=(fmt.lower(),),
                        )
                        for fmt in ("GML", "SHP", "XLSX")
                    ),
                ),
            ),
        ),
        tile_scheme=None,
        storage_subdir=f"names/pl_{source}",
        default_extension=".gpkg",
        license=_GUGIK_LICENSE,
    )


_PL_PRNG = _prng_source(world=False)
_PL_PRNG_WORLD = _prng_source(world=True)

_PL_BDOT10K_MAPS = SourceDescriptor(
    key="pl.gugik.bdot10k_maps",
    country="PL",
    product="topographic",
    name="Wizualizacje map topograficznych BDOT10k",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"sheet_files"}),
            endpoint=_BDOT10K_MAP_INDEX.endpoint,
            update_signal="index",
            params=UnitPackageParams(
                unit="sheet",
                index=_BDOT10K_MAP_INDEX,
                variants=tuple(
                    PackageVariant(
                        choice=(("scale", scale), ("format", fmt)),
                        url_template=None,
                        segment_tokens=(scale.split(":")[1], fmt.lower()),
                        sheet_grid=SheetGrid(system="1992", parts=parts),
                        index_layer=layer,
                        file_kind="tiff" if fmt == "TIFF" else "pdf",
                    )
                    for scale, parts, layer in (
                        ("1:10000", 6, "Mapy10k"),
                        ("1:25000", 5, "Mapy25k"),
                        ("1:50000", 4, "Mapy50k"),
                        ("1:100000", 3, "Mapy100k"),
                    )
                    for fmt in ("TIFF", "PDF")
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="maps/pl_bdot10k",
    default_extension=".tif",
    license=_GUGIK_LICENSE,
)

# Object layers 0-24 of GEONAMES/Geonames/MapServer (published 2026-10-16).
_GEONAMES_NAMES = (
    "mesta_obce",
    "casti_mest_obci",
    "mistni_casti",
    "chranena_uzemi_prirody",
    "regiony",
    "reky_velke_vodni_plochy",
    "ostatni_vodni_toky_a_plochy",
    "ostatni_objekty_vodstva",
    "rozsahle_terenni_tvary",
    "ostatni_terenni_tvary",
    "povrch_vegetace",
    "pozemni_komunikace",
    "vodni_komunikace",
    "letiste",
    "telekomunikacni_zarizeni",
    "kulturni_objekty",
    "hrady_zamky_tvrze",
    "sakralni_objekty",
    "hrbitovy_hrobky",
    "sportovni_zarizeni",
    "lecebna_lazenska_zarizeni",
    "ubytovaci_stravovaci_zarizeni",
    "vyrobni_tezebni_zarizeni",
    "ostatni",
    "hranicni_jmena",
)

_CZ_GEONAMES = SourceDescriptor(
    key="cz.cuzk.geonames",
    country="CZ",
    product="geographic",
    name="Geonames - nazwy geograficzne Czech",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.ARCGIS_QUERY,
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"bbox_vector"}),
            endpoint=f"{_CUZK_ARCGIS}/GEONAMES/Geonames/MapServer",
            update_signal="none",
            params=FeatureBBoxParams(
                protocol="arcgis",
                native_crs="EPSG:5514",
                axis_order="xy",
                page_size=1000,
                layers=tuple(
                    FeatureLayer(
                        code=name, source=str(i), name=name, id_field="OBJECTID"
                    )
                    for i, name in enumerate(_GEONAMES_NAMES)
                ),
                selection="all",
                order_field="OBJECTID",
            ),
        ),
        *(
            AccessChannel(
                transport=TransportKind.DIRECT_FILES,
                horizontal_crs="EPSG:5514",
                capabilities=frozenset({"country_files"}),
                endpoint=f"{_CUZK_ATOM}/GEONAMES-{fmt}/GEONAMES-{fmt}.xml",
                update_signal="metadata",
                params=AtomFilesParams(
                    service_feed=f"{_CUZK_ATOM}/GEONAMES-{fmt}/GEONAMES-{fmt}.xml",
                    entry_pattern=rf"CUZK_GEONAMES-{fmt}_[0-9]+\.xml$",
                    crs=("EPSG:5514", "EPSG:3045"),
                    segment_tokens=(fmt.lower(),),
                    choice=(("format", fmt),),
                ),
            )
            for fmt in ("GPKG", "FGDB")
        ),
    ),
    tile_scheme=None,
    storage_subdir="names/cz_geonames",
    default_extension=".gpkg",
    license=_CUZK_LICENSE,
)

_CZ_ZTM = SourceDescriptor(
    key="cz.cuzk.ztm",
    country="CZ",
    product="topographic",
    name="ZTM - zakladni topograficke mapy Czech",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"sheet_files"}),
            endpoint=f"{_CUZK_OPENZU}/",
            update_signal="http",
            params=UnitPackageParams(
                unit="sheet",
                variants=tuple(
                    PackageVariant(
                        choice=(
                            ("scale", f"1:{scale * 1000}"),
                            ("sheet_system", system.lower()),
                            ("format", fmt),
                        ),
                        url_template=(
                            f"{_CUZK_OPENZU}/ZTM{scale}-{service}-{fmt}/"
                            "{sheet}" + (".pdf" if fmt == "PDF" else ".zip")
                        ),
                        segment_tokens=(str(scale * 1000), system.lower(), fmt.lower()),
                        sheet_grid=SheetGrid(
                            system="cuzk",
                            layer=2 * i + (12 if system == "ETRS89" else 0),
                            crs="EPSG:3045" if system == "ETRS89" else "EPSG:5514",
                        ),
                        file_kind="pdf" if fmt == "PDF" else "zip",
                    )
                    for i, scale in enumerate((5, 10, 25, 50, 100, 250))
                    for system, service, formats in (
                        ("SJTSK", "SJTSK", ("TIFF", "PDF", "DGN", "SHP")),
                        ("ETRS89", "ETRS89", ("TIFF", "PDF")),
                    )
                    for fmt in formats
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="maps/cz_ztm",
    default_extension=".zip",
    license=_CUZK_LICENSE,
)

# plan E - E3: special PRG boundaries, separate from administrative boundaries.
# One OGC API request per collection (items of an area, CRS84). Measured
# 2026-10-16 (Krakow, 0.015 x 0.01 deg): 42 collections answer in 0.4-11 s,
# GranicaRejonuStatystycznego in 36-38 s (channel timeout 120 s) and
# GranicaObwoduSpisowego (census districts) in 158-184 s, over 400 s in
# Warsaw - it is not part of the area result (decision of 2026-10-16,
# ADR-043 errata 1); the national files have it (R02_Granice_obwodow_spisowych).
_PRG_SPECIAL_API = "https://ogcapi.geoportal.gov.pl/res/ims/maps/PRG/apiFeatures"
_PRG_SPECIAL_COLLECTIONS = (
    "GranicaRejonuStatystycznego",
    "SadApelacyjny",
    "SadOkregowy",
    "SadRejonowy",
    "WojewodzkiSadAdministracyjny",
    "ProkuraturaRegionalna",
    "ProkuraturaOkregowa",
    "ProkuraturaRejonowa",
    "KomendaWojewodzkaPolicji",
    "KomendaPowiatowaPolicji",
    "KomendaStolecznaPolicji",
    "KomendaRejonowaPolicji",
    "KomisariatPolicji",
    "KomendaWojewodzkaStrazyPozarnej",
    "KomendaPowiatowaStrazyPozarnej",
    "OddzialStrazyGranicznej",
    "PlacowkaStrazyGranicznej",
    "DywizjonStrazyGranicznej",
    "ObszarDzialaniaSzefaObronyCywilnejWojewodztwa",
    "ObszarDzialaniaSzefaObronyCywilnejPowiatu",
    "ObszarDzialaniaSzefaObronyCywilnejGminy",
    "ArchiwumPanstwowe",
    "UrzadSkarbowy",
    "WyspecjalizowanyUrzadSkarbowy",
    "UrzadCelnoSkarbowy",
    "IzbaAdministracjiSkarbowej",
    "Nadlesnictwo",
    "RegionalnaDyrekcjaLasowPanstwowych",
    "ZarzadZlewniPanstwowegoGospodarstwaWodnegoWodyPolskie",
    "RegionalnyZarzadGospodarkiWodnejPanstwowegoGospodarstwaWodnegoWodyPolskie",
    "UrzadMorski",
    "UrzadZeglugiSrodladowej",
    "LiniaPodstawowaMorzaTerytorialnego",
    "MorzeTerytorialneRP",
    "MorskieWodyWewnetrzne",
    "WylacznaStrefaEkonomiczna",
    "StrefaPrzylegla",
    "MorskaLiniaBrzegowa",
    "PasNadbrzezny",
    "PasOchronny",
    "PasTechniczny",
    "Reda",
    "PortMorski",
    "PrzystanMorska",
)

_PL_PRG_SPECIAL = SourceDescriptor(
    key="pl.gugik.prg_special",
    country="PL",
    product="special",
    name="PRG - granice specjalne",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.OGC_API_FEATURES,
            horizontal_crs="OGC:CRS84",
            capabilities=frozenset({"bbox_vector"}),
            endpoint=_PRG_SPECIAL_API,
            update_signal="none",
            params=FeatureBBoxParams(
                protocol="ogcapi",
                native_crs="OGC:CRS84",
                axis_order="xy",
                page_size=10000,
                layers=tuple(
                    FeatureLayer(code=name, source=name, name=name, id_field="id")
                    for name in _PRG_SPECIAL_COLLECTIONS
                ),
                selection="all",
                timeout=120,
                area_omitted=(
                    "wynik obszaru bez obwodow spisowych (kolekcja "
                    "GranicaObwoduSpisowego: usluga odpowiada minutami) - sa "
                    "w pliku krajowym: --whole-country --format SHP|GML"
                ),
            ),
        ),
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"country_files"}),
            endpoint=f"{_OPENDATA}/prg/granice/",
            update_signal="none",
            params=UnitPackageParams(
                unit="country",
                variants=tuple(
                    PackageVariant(
                        choice=(("format", fmt),),
                        url_template=(
                            f"{_OPENDATA}/prg/granice/00_granice_specjalne_{suffix}.zip"
                        ),
                        segment_tokens=(fmt.lower(),),
                        members=(member,),
                    )
                    for fmt, suffix, member in (
                        ("SHP", "shp", ".shp"),
                        ("GML", "xml", ".gml"),
                    )
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="boundaries/pl_prg_special",
    default_extension=".gpkg",
    license=_GUGIK_LICENSE,
)

# PRG address points (raport E, wiersz 9; WFS and package heads recorded
# 2026-10-16, tests/fixtures/pl/prg_addresses): the KIN WFS (GeoServer, N,E
# axes, gml:id on every feature, CountDefault 10000), one SHP package per
# powiat (no voivodeship packages: 404) and two national files - SHP
# (POLSKA.zip) and GML (PRG-punkty_adresowe.zip: 16 voivodeship GML files of
# the PRGAD schema).
_PRG_ADDRESSES = f"{_OPENDATA}/prg/adresy"
_PL_PRG_ADDRESSES = SourceDescriptor(
    key="pl.gugik.prg_addresses",
    country="PL",
    product="addresses",
    name="PRG - punkty adresowe i ulice",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.WFS,
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"bbox_vector"}),
            endpoint=(
                "https://mapy.geoportal.gov.pl/wss/ext/wfs/"
                "KrajowaIntegracjaNumeracjiAdresowej"
            ),
            update_signal="none",
            notes="punkty adresowe i ulice przecinajace obszar (stan uslugi)",
            params=FeatureBBoxParams(
                protocol="wfs",
                native_crs="EPSG:2180",
                axis_order="yx",
                page_size=1000,
                layers=(
                    FeatureLayer(
                        code="punkty_adresowe",
                        source="adresyUlice:A07_Punkty_adresowe",
                        name="punkty_adresowe",
                        id_field="gml_id",
                    ),
                    FeatureLayer(
                        code="ulice",
                        source="adresyUlice:A08_Ulice",
                        name="ulice",
                        id_field="gml_id",
                    ),
                ),
                selection="all",
            ),
        ),
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"admin_unit_files"}),
            endpoint=f"{_PRG_ADDRESSES}/PunktyAdresowe/",
            update_signal="none",
            notes=(
                "paczka SHP powiatu: punkty adresowe, ulice, place, miejscowosci "
                "(GUGiK nie publikuje paczek wojewodztw)"
            ),
            params=UnitPackageParams(
                unit="powiat",
                variants=(
                    PackageVariant(
                        choice=(),
                        url_template=f"{_PRG_ADDRESSES}/PunktyAdresowe/{{woj}}/{{teryt}}.zip",
                        segment_tokens=("shp",),
                        members=(".shp",),
                    ),
                ),
            ),
        ),
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"country_files"}),
            endpoint=f"{_PRG_ADDRESSES}/",
            update_signal="none",
            notes=(
                "plik krajowy SHP (ok. 564 MB) albo GML (16 plikow wojewodztw, "
                "ok. 804 MB), tylko z --whole-country"
            ),
            params=UnitPackageParams(
                unit="country",
                variants=(
                    PackageVariant(
                        choice=(("format", "SHP"),),
                        url_template=f"{_PRG_ADDRESSES}/PunktyAdresowe/POLSKA.zip",
                        segment_tokens=("shp",),
                        members=(".shp",),
                    ),
                    PackageVariant(
                        choice=(("format", "GML"),),
                        url_template=f"{_PRG_ADDRESSES}/PRG-punkty_adresowe.zip",
                        segment_tokens=("gml",),
                        members=(".gml",),
                    ),
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="boundaries/pl_prg_addresses",
    default_extension=".gpkg",
    license=_GUGIK_LICENSE,
)

# Transaction prices (RCN; raport E, wiersz 14; heads and a trimmed real
# GeoPackage recorded 2026-10-16, tests/fixtures/pl/rcn): the daily export of
# one powiat or voivodeship, a ZIP with ONE GeoPackage of three layers in
# EPSG:2180. The file under latest_exports is replaced (1261: 236 404 584 B
# on 2026-10-15, 301 623 607 B on 2026-10-16), so there is no cheap signal.
_RCN = f"{_OPENDATA}/InneDane/latest_exports/rcn_transakcje_ceny/GPKG"


def _rcn_channel(unit: Literal["powiat", "woj"], text: str) -> AccessChannel:
    """The RCN export of one TERYT unit (``powiat``: 4 digits, ``woj``: 2)."""
    return AccessChannel(
        transport=TransportKind.DIRECT_FILES,
        horizontal_crs="EPSG:2180",
        capabilities=frozenset({"admin_unit_files"}),
        endpoint=f"{_RCN}/",
        update_signal="none",
        notes=(
            f"eksport {text} odswiezany co dobe: GeoPackage z warstwami "
            "transakcje_dzialki, transakcje_budynki, transakcje_lokale"
        ),
        params=UnitPackageParams(
            unit=unit,
            variants=(
                PackageVariant(
                    choice=(),
                    url_template=f"{_RCN}/{{teryt}}_transakcje_ceny.gpkg.zip",
                ),
            ),
            unpack=".gpkg",
            unpack_layers=(
                "transakcje_dzialki",
                "transakcje_budynki",
                "transakcje_lokale",
            ),
        ),
    )


_PL_RCN = SourceDescriptor(
    key="pl.gugik.rcn",
    country="PL",
    product="prices",
    name="RCN - rejestr cen nieruchomosci (transakcje: dzialki, budynki, lokale)",
    provider_name="GUGiK",
    channels=(_rcn_channel("powiat", "powiatu"), _rcn_channel("woj", "wojewodztwa")),
    tile_scheme=None,
    storage_subdir="cadastre/pl_rcn",
    default_extension=".gpkg",
    license=_GUGIK_LICENSE,
)
_E3_PL_SOURCES = (_PL_PRG_ADDRESSES, _PL_PRG_SPECIAL, _PL_RCN)

# Geomorphological units (raport E, wiersz 24; service and layer 39 recorded
# 2026-10-16, tests/fixtures/cz/geomorphology): --level -> one polygon layer
# of GeomorfologickeJednotky/MapServer. The annotation layers (0-21) and the
# shaded relief mosaic (22-25) are not data.
_GEOMORPHOLOGY_LEVELS = (
    ("subprovincie", "33"),
    ("oblast", "34"),
    ("celek", "39"),
    ("podcelek", "35"),
    ("okrsek", "36"),
    ("podokrsek", "37"),
    ("cast", "38"),
)
_CZ_GEOMORPHOLOGY = SourceDescriptor(
    key="cz.cuzk.geomorphology",
    country="CZ",
    product="geomorphology",
    name="Jednostki geomorfologiczne Czech (od subprovincie do casti)",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.ARCGIS_QUERY,
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"bbox_vector"}),
            endpoint=f"{_CUZK_ARCGIS}/GeomorfologickeJednotky/MapServer",
            update_signal="none",
            notes="pelne geometrie jednostek poziomu --level przecinajacych obszar",
            params=FeatureBBoxParams(
                protocol="arcgis",
                native_crs="EPSG:5514",
                axis_order="xy",
                page_size=1000,
                layers=tuple(
                    FeatureLayer(
                        code=code, source=layer, name=code, id_field="OBJECTID"
                    )
                    for code, layer in _GEOMORPHOLOGY_LEVELS
                ),
                selection="level",
                order_field="OBJECTID",
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="boundaries/cz_geomorphology",
    default_extension=".gpkg",
    license=_CUZK_LICENSE,
)

# Cadastral map (raport E, wiersz 19; heads and member lists recorded
# 2026-10-16, tests/fixtures/cz/cadastral_map): one ZIP per cadastral area
# (KU) in each of four formats, each with ETag and Last-Modified; the KU of
# an area come from RUIAN KatastralniUzemi. VKM (a pilot of 10 KU) is not
# part of 0.8.0 (decision P2 of 2026-10-15).
_CUZK_SERVICES = "https://services.cuzk.gov.cz"
_CZ_CADASTRAL_MAP = SourceDescriptor(
    key="cz.cuzk.cadastral_map",
    country="CZ",
    product="map",
    name="Mapa katastralna Czech (katastralni mapa: SHP, DXF, DGN, VFK)",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"admin_unit_files"}),
            endpoint=f"{_CUZK_SERVICES}/",
            update_signal="http",
            notes=(
                "paczka katastralniho uzemi (KU) w jednym z formatow; KU obszaru "
                "wg RUIAN; ZIP zapisywany 1:1"
            ),
            params=UnitPackageParams(
                unit="ku",
                ku_layer=f"{_CUZK_ARCGIS}/RUIAN/MapServer/7",
                variants=tuple(
                    PackageVariant(
                        choice=(("format", fmt),),
                        url_template=f"{_CUZK_SERVICES}/{path}/{{ku}}.zip",
                        segment_tokens=(fmt.lower(),),
                        members=(member,),
                    )
                    for fmt, path, member in (
                        ("SHP", "shp/ku/epsg-5514", ".shp"),
                        ("DXF", "dxf/ku", ".dxf"),
                        ("DGN", "dgn/ku", ".dgn"),
                        ("VFK", "vfk/stavy/aktualni", ".vfk"),
                    )
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="cadastre/cz_km",
    default_extension=".zip",
    license=_CUZK_LICENSE,
)
_E3_CZ_SOURCES = (_CZ_GEOMORPHOLOGY, _CZ_CADASTRAL_MAP)

# --- plan E - E4 -------------------------------------------------------------
# BDOO (raport E, wiersz 8; the 112 packages of 2026-10-16,
# tests/fixtures/pl/bdoo): one GML ZIP per voivodeship and release (2015,
# 2021-2026; 2014, 2016-2020 answer 404; no national file). The classes of a
# release are the union over its 16 voivodeship packages: up to 2023 a
# package has no file of a class without objects in its voivodeship, from
# 2024 every package has all 26. GML in ``.xml`` files up to 2023, ``.gml``
# from 2024; EPSG:2180.
_BDOO = f"{_OPENDATA}/bdoo"
_BDOO_CLASSES_2015 = tuple(
    [
        "ADJA",
        "ADMS",
        "BUHD",
        "BUIN",
        "BUIT",
        "BUTR",
        "BUUO",
        "BUWT",
        "BUZM",
        "KUHU",
        "KUIK",
        "KUKO",
        "KUPG",
        "KUSC",
        "KUSK",
        "KUZA",
        "OIKM",
        "OIMK",
        "PTGN",
        "PTKM",
        "PTLZ",
        "PTNZ",
        "PTPL",
        "PTRK",
        "PTSO",
        "PTTR",
        "PTUT",
        "PTWP",
        "PTWZ",
        "PTZB",
        "SKDR",
        "SKPP",
        "SKRP",
        "SKRW",
        "SKTR",
        "SULN",
        "SUPR",
        "SWKN",
        "SWRM",
        "SWRS",
        "TCON",
        "TCPK",
        "TCPN",
        "TCRZ",
    ]
)
_BDOO_CLASSES_2021 = tuple(
    [
        "ADJA",
        "ADMS",
        "BUHD",
        "BUIN",
        "BUIT",
        "BUWT",
        "BUZM",
        "KUIK",
        "KUKO",
        "KUPG",
        "KUSC",
        "KUSK",
        "OIKM",
        "OIMK",
        "PTGN",
        "PTLZ",
        "PTNZ",
        "PTPL",
        "PTRK",
        "PTSO",
        "PTTR",
        "PTUT",
        "PTWP",
        "PTZB",
        "SKDR",
        "SKPP",
        "SKRP",
        "SKRW",
        "SKTR",
        "SULN",
        "SWKN",
        "SWRM",
        "SWRS",
        "TCON",
        "TCPK",
        "TCPN",
        "TCRZ",
    ]
)
_BDOO_CLASSES_2024 = tuple(
    [
        "ADJA",
        "ADMS",
        "BUUO",
        "KUKO",
        "KUPG",
        "KUPW",
        "KUSC",
        "OIKM",
        "OIMK",
        "PTGN",
        "PTLZ",
        "PTNZ",
        "PTRK",
        "PTTR",
        "PTUT",
        "PTWP",
        "PTZB",
        "SKDR",
        "SKPP",
        "SKTR",
        "SULN",
        "SWKN",
        "SWRS",
        "TCPK",
        "TCPN",
        "TCRZ",
    ]
)
_BDOO_RELEASES = (
    ("2015", ".xml", _BDOO_CLASSES_2015),
    ("2021", ".xml", _BDOO_CLASSES_2021),
    ("2022", ".xml", _BDOO_CLASSES_2021),
    ("2023", ".xml", _BDOO_CLASSES_2021),
    ("2024", ".gml", _BDOO_CLASSES_2024),
    ("2025", ".gml", _BDOO_CLASSES_2024),
    ("2026", ".gml", _BDOO_CLASSES_2024),
)
_PL_BDOO = SourceDescriptor(
    key="pl.gugik.bdoo",
    country="PL",
    product="landcover",
    name="BDOO - baza danych obiektow ogolnogeograficznych (1:250 000)",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="none",
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"admin_unit_files"}),
            endpoint=f"{_BDOO}/",
            notes=(
                "paczka GML wojewodztwa wg rocznika (2015, 2021-2026) zapisywana "
                "1:1; z --layers ZIP plikow wybranych klas"
            ),
            params=UnitPackageParams(
                unit="woj",
                variants=tuple(
                    PackageVariant(
                        choice=(("year", year),),
                        url_template=f"{_BDOO}/{year}/PL.PZGiK.201.{{woj}}.zip",
                        edition=year,
                        segment_tokens=(year,),
                        members=(suffix,),
                        classes=classes,
                    )
                    for year, suffix, classes in _BDOO_RELEASES
                ),
                class_pattern=r"__OT_(?P<code>[A-Z]{4})_[A-Z]\.",
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="landcover/pl_bdoo",
    default_extension=".zip",
    license=_GUGIK_LICENSE,
)
_E4_PL_SOURCES = (_PL_BDOO,)

# Data50 and Data250 (raport E, wiersze 17-18; services and feeds recorded
# 2026-10-16, tests/fixtures/cz/data50_250): an area = one GeoPackage of
# every object layer of DATA50/DATA250 MapServer in EPSG:5514 (the shaded
# relief rasters 5 and 6 of DATA250 are not data), layer codes as ZABAGED
# (the CUZK name without diacritics; no mapping to BDOT10k classes); the
# national SHP ZIP of the ATOM feed in EPSG:5514 or EPSG:3045 only with
# --whole-country.
_DATA50_LAYERS = (
    ("0", "hranice_spravni_jednotky_a_ku"),
    ("1", "spravni_jednotky"),
    ("2", "chranene_uzemi"),
    ("3", "definicni_bod_spravniho_celku"),
    ("4", "definicni_bod_casti_obce"),
    ("5", "jmeno_b"),
    ("6", "jmeno_l"),
    ("7", "jmeno_p"),
    ("8", "objekt_ruzny"),
    ("9", "kotovany_bod"),
    ("10", "pevnustka_bunkr"),
    ("11", "kostel"),
    ("12", "synagoga"),
    ("13", "hrad"),
    ("14", "zamek"),
    ("15", "zricenina"),
    ("16", "rozhledna_vysilac"),
    ("17", "vezovita_stavba"),
    ("18", "vodojem_vezovy"),
    ("19", "vodojem_zemni"),
    ("20", "vetrny_motor"),
    ("21", "lyzarsky_mustek"),
    ("22", "nemocnice"),
    ("23", "autobusove_nadrazi"),
    ("24", "cerpaci_stanice"),
    ("25", "stadion"),
    ("26", "budova"),
    ("27", "zeleznicni_stanice"),
    ("28", "pristav"),
    ("29", "letiste"),
    ("30", "akvadukt"),
    ("31", "shybka"),
    ("32", "lavka"),
    ("33", "plavebni_komora"),
    ("34", "jez"),
    ("35", "hraz"),
    ("36", "most"),
    ("37", "zeleznicni_trat"),
    ("38", "zeleznicni_vlecka"),
    ("39", "lanova_draha"),
    ("40", "tunel"),
    ("41", "silnice_a_dalnice"),
    ("42", "cesta"),
    ("43", "pesina"),
    ("44", "silnice_ve_vystavbe"),
    ("45", "ulice"),
    ("46", "privoz"),
    ("47", "letiste_obvodova_linie"),
    ("48", "elektricke_vedeni"),
    ("49", "produktovod_potrubi"),
    ("50", "jeskyne"),
    ("51", "lesni_prusek"),
    ("52", "skalnaty_sraz_skaly_bod"),
    ("53", "skalnaty_sraz_skaly_linie"),
    ("54", "terenni_stupen"),
    ("55", "terenni_stupen_spadnice"),
    ("56", "vrstevnice"),
    ("57", "budova_blok_budov"),
    ("58", "znicena_budova_rozvalina"),
    ("59", "chatova_kolonie"),
    ("60", "hrbitov"),
    ("61", "usazovaci_nadrz_odkaliste"),
    ("62", "vodni_plocha"),
    ("63", "vodni_tok"),
    ("64", "raseliniste_mocal_bazina"),
    ("65", "zahrada_sad_park_vinice_chmelnice"),
    ("66", "louka_pastvina"),
    ("67", "les"),
    ("68", "orna_puda_a_ostatni_plochy"),
)
_DATA250_LAYERS = (
    ("0", "hranice_statniho_uzemi"),
    ("1", "hranice_kraje"),
    ("2", "hranice_okresu_obvodu_prahy"),
    ("3", "hranice_obce"),
    ("4", "chranene_uzemi"),
    ("7", "nazev_mesta_s_vice_nez_100000_obyvateli"),
    ("8", "nazev_mesta_od_50001_do_100000_obyvatel"),
    ("9", "nazev_mesta_od_20001_do_50000_obyvatel"),
    ("10", "nazev_mesta_od_5001_do_20000_obyvatel"),
    ("11", "nazev_mesta_do_5000_obyvatel"),
    ("12", "nazev_casti_mesta"),
    ("13", "nazev_obce_s_vice_nez_2000_obyvateli"),
    ("14", "nazev_obce_od_501_do_2000_obyvatel"),
    ("15", "nazev_obce_do_500_obyvatel"),
    ("16", "nazev_casti_obce"),
    ("17", "nazev_mistni_casti"),
    ("18", "kotovany_bod"),
    ("19", "vstup_do_jeskyne"),
    ("20", "pramen"),
    ("21", "studna_vrt"),
    ("22", "vodopad"),
    ("23", "jez_bod"),
    ("24", "plavebni_komora_bod"),
    ("25", "rozhledna"),
    ("26", "rozhledna_s_vysilacem"),
    ("27", "vysilac"),
    ("28", "kostel"),
    ("29", "zamek"),
    ("30", "zricenina_hradu_zricenina_zamku"),
    ("31", "historicka_hradba_opevneni"),
    ("32", "mohyla_pomnik_nahrobek"),
    ("33", "hvezdarna"),
    ("34", "nemocnice"),
    ("35", "spravni_budova_urad"),
    ("36", "skola"),
    ("37", "sportovni_areal"),
    ("38", "stadion"),
    ("39", "aquapark"),
    ("40", "upravna_vody"),
    ("41", "cistirna_odpadnich_vod_cov"),
    ("42", "prumyslovy_podnik"),
    ("43", "precerpavaci_stanice"),
    ("44", "halda_odval"),
    ("45", "skladka_odpadu"),
    ("46", "povrchova_tezba_lom"),
    ("47", "usti_sachty_stoly_v_provozu"),
    ("48", "elektrarna_jaderna"),
    ("49", "elektrarna_tepelna"),
    ("50", "elektrarna_vodni"),
    ("51", "elektrarna_vetrna"),
    ("52", "elektrarna_solarni"),
    ("53", "spalovani_biomasy"),
    ("54", "letiste_bod"),
    ("55", "heliport"),
    ("56", "pristav"),
    ("57", "zeleznicni_stanice"),
    ("58", "zeleznicni_zastavka"),
    ("59", "zeleznicni_prejezd"),
    ("60", "silnicni_krizeni"),
    ("61", "krizovatka_mimourovnova_s_najezdy"),
    ("62", "parkoviste_s_cerpaci_stanici"),
    ("63", "parkoviste_bez_cerpaci_stanice"),
    ("64", "stanice_privozu"),
    ("65", "elektricke_vedeni"),
    ("66", "dalkovy_produktovod_dalkove_potrubi"),
    ("67", "privoz"),
    ("68", "most_silnicni_2_uroven"),
    ("69", "most_silnicni_1_uroven"),
    ("70", "zeleznicni_trat"),
    ("71", "zeleznicni_trat_elektrifikovana_normalni_rozchod_vice_koleji"),
    ("72", "zeleznicni_trat_elektrifikovana_normalni_rozchod_1_kolej"),
    ("73", "zeleznicni_trat_neelektrifikovana_normalni_rozchod_vice_koleji"),
    ("74", "zeleznicni_trat_neelektrifikovana_normalni_rozchod_1_kolej"),
    ("75", "zeleznicni_trat_nepouzivana"),
    ("76", "most_zeleznicni_2_uroven"),
    ("77", "most_zeleznicni_1_uroven"),
    ("78", "tunel_silnicni"),
    ("79", "tunel_zeleznicni"),
    ("80", "dalnice_linie_bez_kontur"),
    ("81", "silnice_pro_motorova_vozidla_linie_bez_kontur"),
    ("82", "silnice_1_tridy_linie_bez_kontur"),
    ("83", "silnice_2_tridy_linie_bez_kontur"),
    ("84", "silnice_3_tridy_linie_bez_kontur"),
    ("85", "dalnice"),
    ("86", "silnice_pro_motorova_vozidla"),
    ("87", "silnice_1_tridy"),
    ("88", "silnice_2_tridy"),
    ("89", "silnice_3_tridy"),
    ("90", "silnice_neevidovana"),
    ("91", "silnice_ve_vystavbe"),
    ("92", "najezd"),
    ("93", "pristavaci_draha"),
    ("94", "hraz"),
    ("95", "jez_linie"),
    ("96", "plavebni_komora_linie"),
    ("97", "vodni_tok_povrchovy_staly_od_20_do_50_m"),
    ("98", "vodni_tok_povrchovy_staly_od_5_do_20_m"),
    ("99", "vodni_tok_povrchovy_staly_do_5_m"),
    ("100", "vodni_tok_povrchovy_obcasny"),
    ("101", "vodni_tok_podzemni"),
    ("102", "vodni_tok_popis"),
    ("103", "terenni_stupen_hrana_jama"),
    ("104", "skalnaty_sraz_skaly_linie"),
    ("105", "vrstevnice_zesilena"),
    ("106", "vrstevnice_zakladni"),
    ("107", "vrstevnice_doplnkova"),
    ("108", "vodni_plocha"),
    ("109", "vodni_tok_povrchovy_sirsi_nez_50_m"),
    ("110", "bazina_mocal"),
    ("111", "ostrov"),
    ("112", "blok_zastavby_s_vice_nez_5000_obyvateli"),
    ("113", "letiste_plocha"),
    ("114", "ovocny_sad_zahrada"),
    ("115", "vinice"),
    ("116", "chmelnice"),
    ("117", "les"),
)


def _cz_data_source(
    dataset: str, scale: str, layers: tuple[tuple[str, str], ...], sizes: str
) -> SourceDescriptor:
    """Data50/Data250 of CUZK: the objects of an area (REST) or the national
    SHP ZIP (ATOM feed, one file per CRS)."""
    feed = f"{_CUZK_ATOM}/{dataset}/{dataset}.xml"
    return SourceDescriptor(
        key=f"cz.cuzk.{dataset.lower()}",
        country="CZ",
        product="landcover",
        name=f"{dataset} - cyfrowy model geograficzny Czech ({scale})",
        provider_name="CUZK",
        channels=(
            AccessChannel(
                transport=TransportKind.ARCGIS_QUERY,
                update_signal="none",
                horizontal_crs="EPSG:5514",
                capabilities=frozenset({"bbox_vector"}),
                endpoint=f"{_CUZK_ARCGIS}/{dataset.upper()}/MapServer",
                notes=(
                    f"{len(layers)} warstw obiektowych (nazwy zrodla); pelne "
                    "geometrie obiektow przecinajacych obszar"
                ),
                params=FeatureBBoxParams(
                    protocol="arcgis",
                    native_crs="EPSG:5514",
                    axis_order="xy",
                    page_size=2000,
                    layers=tuple(
                        FeatureLayer(
                            code=code, source=layer, name=code, id_field="OBJECTID"
                        )
                        for layer, code in layers
                    ),
                    selection="all",
                    order_field="OBJECTID",
                ),
            ),
            AccessChannel(
                transport=TransportKind.DIRECT_FILES,
                update_signal="metadata",
                horizontal_crs="EPSG:5514",
                capabilities=frozenset({"country_files"}),
                endpoint=feed,
                notes=f"plik krajowy SHP ({sizes}), tylko z --whole-country",
                params=AtomFilesParams(
                    service_feed=feed,
                    entry_pattern=rf"CUZK_{dataset}_[0-9]+\.xml$",
                    crs=("EPSG:5514", "EPSG:3045"),
                    segment_tokens=("shp",),
                ),
            ),
        ),
        tile_scheme=None,
        storage_subdir=f"landcover/cz_{dataset.lower()}",
        default_extension=".gpkg",
        license=_CUZK_LICENSE,
    )


_E4_CZ_SOURCES = (
    _cz_data_source(
        "Data50", "1:50 000", _DATA50_LAYERS, "516 MB EPSG:5514, 757 MB EPSG:3045"
    ),
    _cz_data_source(
        "Data250", "1:250 000", _DATA250_LAYERS, "230 MB EPSG:5514, 320 MB EPSG:3045"
    ),
)

# --- plan E - E5 -------------------------------------------------------------
# Mesh 3D (raport E, wiersz 5; WFS pages, HEAD of tiles and ZIP members
# recorded 2026-10-16, tests/fixtures/pl/mesh_3d): one record per file of the
# index ModeleSiatkowe3D; the field ``modul`` repeats across works and towns,
# so a tile is the file of its record (unit_field=None: the file name). OBJ,
# MTL and JPG in one ZIP stored 1:1; PL-1992 or PL-2000 zone S5-S7 per record
# (uklad_xy), heights PL-EVRF2007-NH in every record (uklad_h).
_MESH_3D_INDEX = IndexSource(
    kind="wfs",
    endpoint=f"{_PZGIK}/NMT/WFS/ModeleSiatkowe3D",
    parser=None,
    unit_field=None,
    url_field="URL_do_pobrania",
    label_fields=("Aktualnosc", "Numer_zgloszenia_pracy"),
    year_field="akt_rok",
    zone_field="uklad_xy",
)
_PL_MESH_3D = SourceDescriptor(
    key="pl.gugik.mesh_3d",
    country="PL",
    product="mesh",
    name="Modele siatkowe 3D miast (mesh OBJ z teksturami)",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="index",
            horizontal_crs="EPSG:2180",
            vertical_crs_options=("EPSG:9651",),
            capabilities=frozenset({"area_files"}),
            endpoint=_MESH_3D_INDEX.endpoint,
            notes=(
                "kafel = plik rekordu indeksu WFS (ZIP z OBJ, MTL i JPG zapisywany "
                "1:1); uklad kafla z rekordu (PL-1992, PL-2000 S5-S7), wysokosci "
                "PL-EVRF2007-NH"
            ),
            params=UnitPackageParams(
                unit="tile",
                index=_MESH_3D_INDEX,
                variants=(
                    PackageVariant(
                        choice=(),
                        url_template=None,
                        members=(".obj",),
                        vertical_crs="EPSG:9651",
                        index_layer="gugik:SkorowidzModeleSiatkowe3D",
                    ),
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="models3d/pl_mesh",
    default_extension=".zip",
    license=_GUGIK_LICENSE,
)

# 3D trees (raport E, wiersz 6; HEAD of packages recorded 2026-10-16,
# tests/fixtures/pl/trees_3d): one CityGML LoD1 package of the 2023 release
# per powiat (0.3-25 GB; some powiats have none: 404), the GML files of
# 1:500 sheets in EPSG:2180 without a vertical CRS; no LoD2, no other year.
_TREES_3D = f"{_OPENDATA}/InneDane/Drzewa3D"
_PL_TREES_3D = SourceDescriptor(
    key="pl.gugik.trees_3d",
    country="PL",
    product="trees",
    name="Modele 3D drzew (CityGML LoD1)",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="none",
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"admin_unit_files"}),
            endpoint=f"{_TREES_3D}/",
            notes=(
                "paczka powiatu (0,3-25 GB): pliki GML arkuszy 1:500, EPSG:2180 bez "
                "ukladu wysokosci; nie kazdy powiat ma paczke"
            ),
            params=UnitPackageParams(
                unit="powiat",
                variants=(
                    PackageVariant(
                        choice=(("lod", "1"), ("year", "2023")),
                        url_template=f"{_TREES_3D}/LOD1/2023/{{woj}}/{{teryt}}.zip",
                        edition="2023",
                        segment_tokens=("lod1", "2023"),
                        members=(".gml",),
                    ),
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="models3d/pl_trees",
    default_extension=".zip",
    license=_GUGIK_LICENSE,
)

# Basic survey control networks (raport E, wiersz 13; WFS of each network,
# packages and archives recorded 2026-10-16, tests/fixtures/pl/prpog): one
# WFS 2.0 service per network (MapServer, EPSG:2180 N,E, no gml:id - a point
# is ``nr_punktu``, an isogonic zone ``zakres_wartosci_deklinacji``; the
# labels of the isogons are not data), the packages of the horizontal and
# vertical network per powiat (coordinate lists XLS and point descriptions
# JPG) and the archive catalogues per 1:100 000 sheet (scans, PDF and TIFF).
_BDPOG = f"{_OPENDATA}/bdpog"
_PL_CONTROL_SERVICES = (
    (
        "horizontal",
        "PodstawowaOsnowaGeodezyjnaPozioma",
        ("Fundamentalna_pozioma", "Bazowa_pozioma"),
    ),
    (
        "vertical",
        "PodstawowaOsnowaGeodezyjnaWysokosciowa",
        ("Fundamentalna_wysokosciowa", "Bazowa_wysokosciowa"),
    ),
    (
        "gravity",
        "OsnowaGrawimetryczna",
        ("Fundamentalna_grawimetryczna", "Bazowa_grawimetryczna"),
    ),
    (
        "magnetic",
        "OsnowaMagnetyczna",
        ("Fundamentalna_magnetyczna", "Bazowa_magnetyczna", "izogony"),
    ),
)


def _pl_control_wfs(
    network: str, service: str, layers: tuple[str, ...]
) -> AccessChannel:
    """The WFS of one PL control network (the address without ``/WFS`` does
    not answer)."""
    return AccessChannel(
        transport=TransportKind.WFS,
        update_signal="none",
        horizontal_crs="EPSG:2180",
        capabilities=frozenset({"bbox_vector"}),
        endpoint=f"{_PZGIK}/{service}/WFS",
        notes="punkty osnowy (i strefy izogon) przecinajace obszar, stan uslugi",
        params=FeatureBBoxParams(
            protocol="wfs",
            native_crs="EPSG:2180",
            axis_order="yx",
            page_size=1000,
            layers=tuple(
                FeatureLayer(
                    code=name.lower(),
                    source=f"ms:{name}",
                    name=name.lower(),
                    id_field=(
                        "zakres_wartosci_deklinacji"
                        if name == "izogony"
                        else "nr_punktu"
                    ),
                )
                for name in layers
            ),
            selection="all",
            choice=(("network", network),),
        ),
    )


_PL_PRPOG = SourceDescriptor(
    key="pl.gugik.prpog",
    country="PL",
    product="control",
    name="Osnowy podstawowe: pozioma, wysokosciowa, grawimetryczna, magnetyczna "
    "(z archiwami)",
    provider_name="GUGiK",
    channels=(
        *(
            _pl_control_wfs(network, service, layers)
            for network, service, layers in _PL_CONTROL_SERVICES
        ),
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="none",
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"admin_unit_files"}),
            endpoint=f"{_BDPOG}/",
            notes=(
                "paczka powiatu sieci poziomej albo wysokosciowej: wykazy "
                "wspolrzednych (XLS) i opisy topograficzne (JPG), ZIP 1:1"
            ),
            params=UnitPackageParams(
                unit="powiat",
                variants=tuple(
                    PackageVariant(
                        choice=(("network", network),),
                        url_template=(
                            f"{_BDPOG}/{folder}/{{teryt}}_PodstawowaOsnowa{folder}.zip"
                        ),
                        segment_tokens=(network, "package"),
                        members=(".xls",),
                    )
                    for network, folder in (
                        ("horizontal", "Pozioma"),
                        ("vertical", "Wysokosciowa"),
                    )
                ),
            ),
        ),
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="none",
            horizontal_crs="EPSG:2180",
            capabilities=frozenset({"sheet_files"}),
            endpoint=f"{_BDPOG}/MaterialyArchiwalne/",
            notes=(
                "archiwalne katalogi i kartoteki punktow arkusza 1:100 000 (skany "
                "PDF i TIFF w ukladach historycznych), ZIP 1:1"
            ),
            params=UnitPackageParams(
                unit="sheet",
                variants=tuple(
                    PackageVariant(
                        choice=(("network", network),),
                        url_template=(
                            f"{_BDPOG}/MaterialyArchiwalne/Katalogi_{folder}/{{sheet}}.zip"
                        ),
                        segment_tokens=(network,),
                        members=(".pdf",),
                        sheet_grid=SheetGrid(system="1992", parts=3),
                    )
                    for network, folder in (
                        ("archive-1942", "Kartoteki1942"),
                        ("archive-kronsztadt60", "Kronsztadt60"),
                    )
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="geodesy/pl_control",
    default_extension=".gpkg",
    license=_GUGIK_LICENSE,
)

# PL-geoid2021 (raport E, wiersz 15; head and tail of the file recorded
# 2026-10-16, tests/fixtures/pl/quasigeoid): one text file (latitude,
# longitude, zeta on a 0.01 deg grid in ETRF2000-PL, 42 MB) of the quasi-geoid
# of PL-EVRF2007-NH; the KRON86 variant is not published (404).
_QUASIGEOID = f"{_OPENDATA}/InneDane/ModeleQuasiGeoidy"
_PL_QUASIGEOID = SourceDescriptor(
    key="pl.gugik.quasigeoid",
    country="PL",
    product="geoid",
    name="Model quasi-geoidy PL-geoid2021 (PL-EVRF2007-NH)",
    provider_name="GUGiK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="none",
            horizontal_crs="EPSG:9702",
            capabilities=frozenset({"country_files"}),
            endpoint=f"{_QUASIGEOID}/",
            notes=(
                "jeden plik krajowy TXT (szerokosc, dlugosc, zeta; siatka 0,01 st., "
                "42 MB) zapisywany 1:1, tylko z --whole-country"
            ),
            params=UnitPackageParams(
                unit="country",
                variants=(
                    PackageVariant(
                        choice=(),
                        url_template=(
                            f"{_QUASIGEOID}/PL-geoid2021/"
                            "Model_quasi-geoidy-geoid2021-PL-EVRF2007-NH.txt"
                        ),
                        segment_tokens=("evrf2007",),
                        file_kind="txt",
                    ),
                ),
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="geodesy/pl_geoid2021",
    default_extension=".txt",
    license=_GUGIK_LICENSE,
)
_E5_PL_SOURCES = (_PL_MESH_3D, _PL_TREES_3D, _PL_PRPOG, _PL_QUASIGEOID)

# Survey control of CR (raport E, wiersz 23; service and layers recorded
# 2026-10-16, tests/fixtures/cz/survey_control): --network -> the point layers
# of BodovaPole/MapServer, layer names without diacritics. The points
# determined in ETRS89 (layers 2-8, 22-28) are not subsets of the main
# layers (18/20, 38/40: no common point in the whole country), so a network
# is the union of its layers; abolished points (10-17, 30-37) and the number
# labels (odd layers) are not data.
_BODOVA_POLE_NETWORKS = (
    ("gnss", (("0", "czepos"),)),
    (
        "horizontal",
        (
            ("18", "bod_zpbp"),
            ("20", "pridruzeny_bod_k_bodu_zpbp"),
            ("2", "bod_zpbp_urceny_v_etrs89"),
            ("4", "bod_zpbp_urceny_v_etrs89_metodou_rtk"),
            ("6", "pridruzeny_bod_k_bodu_zpbp_urceny_v_etrs89"),
            ("8", "pridruzeny_bod_k_bodu_zpbp_urceny_v_etrs89_metodou_rtk"),
        ),
    ),
    (
        "densification",
        (
            ("38", "zhb"),
            ("40", "pridruzeny_bod_k_zhb"),
            ("22", "zhb_urceny_v_etrs89"),
            ("24", "zhb_urceny_v_etrs89_metodou_rtk"),
            ("26", "pridruzeny_bod_k_zhb_urceny_v_etrs89"),
            ("28", "pridruzeny_bod_k_zhb_urceny_v_etrs89_metodou_rtk"),
        ),
    ),
    ("horizontal-detailed", (("42", "bod_ppbp"),)),
    ("vertical", (("44", "bod_zvbp"),)),
    ("vertical-detailed", (("46", "bod_pvbp"),)),
    ("gravity", (("48", "bod_ztbp"),)),
)
_CZ_SURVEY_CONTROL = SourceDescriptor(
    key="cz.cuzk.survey_control",
    country="CZ",
    product="control",
    name="Bodove pole - osnowy geodezyjne Czech (polohove, vyskove, tihove, CZEPOS)",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.ARCGIS_QUERY,
            update_signal="none",
            horizontal_crs="EPSG:5514",
            capabilities=frozenset({"bbox_vector"}),
            endpoint=f"{_CUZK_ARCGIS}/BodovaPole/MapServer",
            notes="punkty sieci --network przecinajace obszar (suma jej warstw)",
            params=FeatureBBoxParams(
                protocol="arcgis",
                native_crs="EPSG:5514",
                axis_order="xy",
                page_size=1000,
                layers=tuple(
                    FeatureLayer(
                        code=network, source=layer, name=name, id_field="OBJECTID"
                    )
                    for network, layers in _BODOVA_POLE_NETWORKS
                    for layer, name in layers
                ),
                selection="level",
                order_field="OBJECTID",
                selection_key="network",
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="geodesy/cz_control",
    default_extension=".gpkg",
    license=_CUZK_LICENSE,
)

# QGZU-2013 (raport E, wiersz 22; feeds recorded 2026-10-16,
# tests/fixtures/cz/qgzu): one dataset of the ATOM feed QGZU, one ZIP of 17
# text grids (ETRS89, EPSG:4258; the quasi-geoid of Bpv heights) stored 1:1.
_QGZU_FEED = f"{_CUZK_ATOM}/QGZU/QGZU.xml"
_CZ_QGZU = SourceDescriptor(
    key="cz.cuzk.qgzu",
    country="CZ",
    product="geoid",
    name="Kvazigeoid QGZU-2013 (siatki TXT, Bpv)",
    provider_name="CUZK",
    channels=(
        AccessChannel(
            transport=TransportKind.DIRECT_FILES,
            update_signal="metadata",
            horizontal_crs="EPSG:4258",
            capabilities=frozenset({"country_files"}),
            endpoint=_QGZU_FEED,
            notes=(
                "jeden plik krajowy: ZIP 17 siatek TXT (58 MB) zapisywany 1:1, "
                "tylko z --whole-country; wydanie z feedu ATOM"
            ),
            params=AtomFilesParams(
                service_feed=_QGZU_FEED,
                entry_pattern=r"CUZK_QGZU_KVAZIGEOID\.xml$",
            ),
        ),
    ),
    tile_scheme=None,
    storage_subdir="geodesy/cz_qgzu2013",
    default_extension=".zip",
    license=_CUZK_LICENSE,
)
_E5_CZ_SOURCES = (_CZ_SURVEY_CONTROL, _CZ_QGZU)

_SOURCES: dict[str, SourceDescriptor] = {
    d.key: d
    for d in (
        *_PL_SHEET_SOURCES,
        SourceDescriptor(
            key="pl.gugik.orto",
            country="PL",
            product="orto",
            name="Ortofotomapa (arkusze wg kampanii; wycinek WCS Standard i High)",
            provider_name="GUGiK",
            channels=(
                AccessChannel(
                    transport=TransportKind.WMS_SHEET_INDEX,
                    update_signal="index",
                    horizontal_crs="EPSG:2180",
                    capabilities=frozenset({"sheet_files"}),
                    endpoint=f"{_PZGIK}/ORTO/WMS/SkorowidzeWgAktualnosci",
                    params=SheetIndexParams(
                        layers=(),
                        systems=("1992", "2000"),
                        sheet_parts=7,
                        full_sheet=True,
                    ),
                ),
                _orto_wcs(
                    "StandardResolution",
                    "standard",
                    "Orthoimagery_StandardResolution",
                    "najnowsze dostepne ortofotomapy",
                    native_step="0.1",
                    resolutions=_ORTO_PIXELS,
                ),
                _orto_wcs(
                    "HighResolution",
                    "high",
                    "Orthoimagery_High_Resolution",
                    "ortofotomapy o pikselu 10 cm i mniejszym",
                    native_step="0.1",
                    resolutions=_ORTO_PIXELS,
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
        # plan E - E1
        *_E1_PL_SOURCES,
        # plan E - E2: PL names and maps.
        _PL_PRNG,
        _PL_PRNG_WORLD,
        _PL_BDOT10K_MAPS,
        # plan E - E3: PRG addresses and special boundaries, RCN.
        *_E3_PL_SOURCES,
        # plan E - E4: BDOO.
        *_E4_PL_SOURCES,
        # plan E - E5: mesh 3D, 3D trees, survey control networks, PL-geoid2021.
        *_E5_PL_SOURCES,
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
        *_CZ_SOURCES,
        _CZ_ZABAGED,
        _CZ_RUIAN,
        _CZ_HY_NET,
        _CZ_ORTOFOTO,
        # plan E - E1: CZ contours.
        *_E1_CZ_SOURCES,
        # plan E - E2: CZ names and maps.
        _CZ_GEONAMES,
        _CZ_ZTM,
        # plan E - E3: CZ geomorphology and cadastral map.
        *_E3_CZ_SOURCES,
        # plan E - E4: CZ Data50 and Data250.
        *_E4_CZ_SOURCES,
        # plan E - E5: CZ survey control and QGZU.
        *_E5_CZ_SOURCES,
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
        dataset_keys=tuple(sorted(k for k in _SOURCES if k.startswith("cz."))),
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


def _channels(
    key: str, transport: TransportKind, horizontal_crs: str | None
) -> list[AccessChannel]:
    """Channels of ``key`` with ``transport`` (in ``horizontal_crs``, if given);
    ``ValidationError`` for an unknown source or no such channel."""
    source = _SOURCES.get(key)
    if source is None:
        raise ValidationError(f"Nieznane zrodlo: '{key}'. Dostepne: {sorted(_SOURCES)}")
    found = [
        channel
        for channel in source.channels
        if channel.transport == transport
        and (horizontal_crs is None or channel.horizontal_crs == horizontal_crs)
    ]
    if not found:
        where = f" w {horizontal_crs}" if horizontal_crs is not None else ""
        raise ValidationError(
            f"Zrodlo '{key}' nie ma kanalu {transport.value!r}{where} (kanaly: "
            f"{[(c.transport.value, c.horizontal_crs) for c in source.channels]})"
        )
    return found


def channel_for(
    key: str, transport: TransportKind, horizontal_crs: str | None = None
) -> AccessChannel:
    """The ONE channel of source ``key`` with ``transport`` and ``horizontal_crs``.

    CZ descriptors publish one file channel per sheet system (SM5 in
    EPSG:5514, TM33 tiles in EPSG:3045): the CRS chooses the endpoint.
    ``horizontal_crs=None`` is enough for a transport with one channel.

    Raises
    ------
    ValidationError
        Unknown source, no such channel, or several channels left (the CRS
        is needed to choose).
    """
    found = _channels(key, transport, horizontal_crs)
    if len(found) > 1:
        raise ValidationError(
            f"Zrodlo '{key}' ma kilka kanalow {transport.value!r} "
            f"({', '.join(c.horizontal_crs for c in found)}) - wybor wymaga "
            "ukladu poziomego kanalu"
        )
    return found[0]


def channel_signal(
    key: str, transport: TransportKind, horizontal_crs: str | None = None
) -> SignalKind:
    """Freshness signal of the ``transport`` channel of source ``key``.

    ``horizontal_crs`` chooses among channels of one transport (CZ files of
    SM5 and TM33); without it every channel of the transport must declare the
    same signal.

    Raises
    ------
    ValidationError
        Unknown source, a source without such a channel, or channels of the
        transport with different signals and no ``horizontal_crs``.
    """
    signals = {c.update_signal for c in _channels(key, transport, horizontal_crs)}
    if len(signals) > 1:
        raise ValidationError(
            f"Kanaly {transport.value!r} zrodla '{key}' maja rozne sygnaly "
            f"({', '.join(sorted(signals))}) - wybor wymaga ukladu poziomego kanalu"
        )
    return signals.pop()


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
