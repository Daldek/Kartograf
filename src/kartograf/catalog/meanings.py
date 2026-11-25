"""
The meanings of the allowed values of the options (AGI-2.3 ``enum``).

The catalog document gives every allowed value of an option a one-line meaning
(``{"value", "meaning"}``) in English, and the page of a form (``commands schema
--form``) its Polish twin (``i18n.pl.enum``). The values themselves come from the
registries (``Param.allowed`` is a provider); their meanings are catalog messages of the
area ``meanings`` (``kartograf.messages.meanings``, both languages of a text side by
side), mapped here by the name of the option: the same value means the same in every
command (``GPKG``, ``EVRF2007``), and a product name is unique across the groups. Values
of a regular form (a grid label, a depth interval, a scale, a year, a release) get their
meaning from a pattern, so a value a registry adds later needs no entry; another new
value has none and ``meaning`` raises ``KeyError``, which a contract test turns into the
reminder to add one.
"""

import re
from collections.abc import Mapping
from typing import Final

from kartograf.messages import Message, message

MEANINGS: Final[Mapping[str, Mapping[str, Message]]] = {
    "product": {
        "nmt": message("meanings.product_nmt"),
        "nmpt": message("meanings.product_nmpt"),
        "laz": message("meanings.product_laz"),
        "contours": message("meanings.product_contours"),
        "orto": message("meanings.product_orto"),
        "intensity": message("meanings.product_intensity"),
        "true-orto": message("meanings.product_true_orto"),
        "oblique-orto": message("meanings.product_oblique_orto"),
        "bdot10k": message("meanings.product_bdot10k"),
        "bdoo": message("meanings.product_bdoo"),
        "corine": message("meanings.product_corine"),
        "zabaged": message("meanings.product_zabaged"),
        "data50": message("meanings.product_data50"),
        "data250": message("meanings.product_data250"),
        "soil": message("meanings.product_soil"),
        "admin": message("meanings.product_admin"),
        "addresses": message("meanings.product_addresses"),
        "special": message("meanings.product_special"),
        "geomorphology": message("meanings.product_geomorphology"),
        "map": message("meanings.product_map"),
        "prices": message("meanings.product_prices"),
        "buildings": message("meanings.product_buildings"),
        "mesh": message("meanings.product_mesh"),
        "trees": message("meanings.product_trees"),
        "network": message("meanings.product_network"),
        "pgw": message("meanings.product_pgw"),
        "camels": message("meanings.product_camels"),
        "geographic": message("meanings.product_geographic"),
        "world": message("meanings.product_world"),
        "topographic": message("meanings.product_topographic"),
        "control": message("meanings.product_control"),
        "geoid": message("meanings.product_geoid"),
    },
    "country": {
        "pl": message("meanings.country_pl"),
        "cz": message("meanings.country_cz"),
        "auto": message("meanings.country_auto"),
    },
    "format": {
        "ASC": message("meanings.format_asc"),
        "XYZ": message("meanings.format_xyz"),
        "ASCII-NMT": message("meanings.format_ascii_nmt"),
        "TBD": message("meanings.format_tbd"),
        "TIN": message("meanings.format_tin"),
        "TTN": message("meanings.format_ttn"),
        "GRD": message("meanings.format_grd"),
        "DXF": message("meanings.format_dxf"),
        "DGN": message("meanings.format_dgn"),
        "SHP": message("meanings.format_shp"),
        "GPKG": message("meanings.format_gpkg"),
        "GML": message("meanings.format_gml"),
        "TIFF": message("meanings.format_tiff"),
        "PDF": message("meanings.format_pdf"),
        "XLSX": message("meanings.format_xlsx"),
        "FGDB": message("meanings.format_fgdb"),
        "VFK": message("meanings.format_vfk"),
        "agents": message("meanings.format_agents"),
        "llms": message("meanings.format_llms"),
        "agents-md-block": message("meanings.format_agents_md_block"),
    },
    "sheet_system": {
        "1992": message("meanings.sheet_system_1992"),
        "2000": message("meanings.sheet_system_2000"),
        "sjtsk": message("meanings.sheet_system_sjtsk"),
        "etrs89": message("meanings.sheet_system_etrs89"),
    },
    "lang": {
        "pl": message("meanings.lang_pl"),
        "en": message("meanings.lang_en"),
    },
    "bbox_crs": {
        "EPSG:2176": message("meanings.bbox_crs_epsg_2176"),
        "EPSG:2177": message("meanings.bbox_crs_epsg_2177"),
        "EPSG:2178": message("meanings.bbox_crs_epsg_2178"),
        "EPSG:2179": message("meanings.bbox_crs_epsg_2179"),
        "EPSG:2180": message("meanings.bbox_crs_epsg_2180"),
        "EPSG:3045": message("meanings.bbox_crs_epsg_3045"),
        "EPSG:4326": message("meanings.bbox_crs_epsg_4326"),
        "EPSG:5514": message("meanings.bbox_crs_epsg_5514"),
    },
    "vertical_crs": {
        "EVRF2007": message("meanings.vertical_crs_evrf2007"),
        "KRON86": message("meanings.vertical_crs_kron86"),
        "Bpv": message("meanings.vertical_crs_bpv"),
    },
    "model": {
        "dmr5g": message("meanings.model_dmr5g"),
        "dmr4g": message("meanings.model_dmr4g"),
        "dmp1g": message("meanings.model_dmp1g"),
        "dmpok": message("meanings.model_dmpok"),
    },
    "coverage": {
        "standard": message("meanings.coverage_standard"),
        "high": message("meanings.coverage_high"),
    },
    "direction": {
        "n": message("meanings.direction_n"),
        "e": message("meanings.direction_e"),
        "s": message("meanings.direction_s"),
        "w": message("meanings.direction_w"),
    },
    "level": {
        "wojewodztwo": message("meanings.level_wojewodztwo"),
        "powiat": message("meanings.level_powiat"),
        "gmina": message("meanings.level_gmina"),
        "jednostka-ewidencyjna": message("meanings.level_jednostka_ewidencyjna"),
        "obreb": message("meanings.level_obreb"),
        "kraj": message("meanings.level_kraj"),
        "okres": message("meanings.level_okres"),
        "obec": message("meanings.level_obec"),
        "katastralni-uzemi": message("meanings.level_katastralni_uzemi"),
        "subprovincie": message("meanings.level_subprovincie"),
        "oblast": message("meanings.level_oblast"),
        "celek": message("meanings.level_celek"),
        "podcelek": message("meanings.level_podcelek"),
        "okrsek": message("meanings.level_okrsek"),
        "podokrsek": message("meanings.level_podokrsek"),
        "cast": message("meanings.level_cast"),
    },
    "lod": {
        "1": message("meanings.lod_1"),
        "2": message("meanings.lod_2"),
    },
    "network": {
        "horizontal": message("meanings.network_horizontal"),
        "vertical": message("meanings.network_vertical"),
        "gravity": message("meanings.network_gravity"),
        "magnetic": message("meanings.network_magnetic"),
        "archive-1942": message("meanings.network_archive_1942"),
        "archive-kronsztadt60": message("meanings.network_archive_kronsztadt60"),
        "gnss": message("meanings.network_gnss"),
        "densification": message("meanings.network_densification"),
        "horizontal-detailed": message("meanings.network_horizontal_detailed"),
        "vertical-detailed": message("meanings.network_vertical_detailed"),
    },
    "property": {
        "bdod": message("meanings.property_bdod"),
        "cec": message("meanings.property_cec"),
        "cfvo": message("meanings.property_cfvo"),
        "clay": message("meanings.property_clay"),
        "nitrogen": message("meanings.property_nitrogen"),
        "ocd": message("meanings.property_ocd"),
        "ocs": message("meanings.property_ocs"),
        "phh2o": message("meanings.property_phh2o"),
        "sand": message("meanings.property_sand"),
        "silt": message("meanings.property_silt"),
        "soc": message("meanings.property_soc"),
    },
    "stat": {
        "mean": message("meanings.stat_mean"),
        "Q0.05": message("meanings.stat_q0_05"),
        "Q0.5": message("meanings.stat_q0_5"),
        "Q0.95": message("meanings.stat_q0_95"),
        "uncertainty": message("meanings.stat_uncertainty"),
    },
    "depth_rule": {
        "least-permeable": message("meanings.depth_rule_least_permeable"),
    },
    "update": {
        "upgrade": message("meanings.update_upgrade"),
        "force": message("meanings.update_force"),
    },
}

# Values of a regular form: (the options, the form, the message of the meaning, whose
# placeholder ``value`` is the value).
_PATTERNS: Final[tuple[tuple[frozenset[str], re.Pattern[str], str], ...]] = (
    (frozenset({"resolution"}), re.compile(r"[0-9.]+m"), "meanings.resolution"),
    (frozenset({"depth"}), re.compile(r"[0-9]+-[0-9]+cm"), "meanings.depth"),
    (frozenset({"scale"}), re.compile(r"1:[0-9]+"), "meanings.scale"),
    (frozenset({"year"}), re.compile(r"[0-9]{4}"), "meanings.year"),
    (
        frozenset({"version"}),
        re.compile(r"[0-9]+\.[0-9]+\.[0-9]+"),
        "meanings.version",
    ),
)


def meaning(option: str, value: str) -> Message:
    """Return the one-line meaning of an allowed value of an option.

    Parameters
    ----------
    option : str
        The name of the option (``product``, ``vertical_crs``, ``depth``...);
        ``horizontal_crs`` is read as ``bbox_crs``.
    value : str
        One of its allowed values.

    Returns
    -------
    Message
        The English text; ``localize(text, "pl")`` renders its Polish twin.

    Raises
    ------
    KeyError
        The value has no meaning here: add its entry to ``kartograf.messages.meanings``
        and its line to ``MEANINGS``.
    """
    table = MEANINGS.get("bbox_crs" if option == "horizontal_crs" else option, {})
    if value in table:
        return table[value]
    for options, form, key in _PATTERNS:
        if option in options and form.fullmatch(value):
            return message(key, value=value)
    raise KeyError(f"no meaning of the value {value!r} of the option {option!r}")
