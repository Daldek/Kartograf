"""
The meanings of the allowed values of the options (AGI-2.3 ``enum``).

The catalog document gives every allowed value of an option a one-line meaning in
English (``{"value", "meaning"}``). The values themselves come from the registries
(``Param.allowed`` is a provider); their meanings are text and live here, keyed by
the name of the option: the same value means the same in every command (``GPKG``,
``EVRF2007``), and a product name is unique across the groups. Values of a regular
form (a grid label, a depth interval, a scale, a year) get their meaning from a
pattern, so a value a registry adds later needs no entry; another new value has none
and ``meaning`` raises ``KeyError``, which a contract test turns into the reminder to
add one.
"""

import re
from collections.abc import Mapping
from typing import Final

MEANINGS: Final[Mapping[str, Mapping[str, str]]] = {
    "product": {
        "nmt": "Digital terrain model (bare earth); PL and CZ.",
        "nmpt": "Digital surface model (with the objects on the ground); PL and CZ.",
        "laz": "LIDAR point cloud; PL and CZ.",
        "contours": "ZABAGED contours, 2D vector, SM5 sheets, SHP or DGN; CZ.",
        "orto": "RGB orthophoto; PL and CZ.",
        "intensity": "LIDAR intensity images, one band, 0.25 m; PL.",
        "true-orto": "True orthophoto of selected cities, 0.05 m; PL.",
        "oblique-orto": (
            "Oblique orthophoto of selected cities; a sheet is four files "
            "(n, e, s, w); PL."
        ),
        "bdot10k": "BDOT10k topographic object database; PL.",
        "bdoo": "BDOO general geographic object database (1:250000); PL.",
        "corine": "CORINE Land Cover; EU.",
        "zabaged": (
            "ZABAGED, the basic geographic database of Czechia (land "
            "cover, waters); CZ."
        ),
        "data50": "Data50, the digital geographic model of Czechia at 1:50000; CZ.",
        "data250": "Data250, the digital geographic model of Czechia at 1:250000; CZ.",
        "soil": "SoilGrids soil property layers (ISRIC); global.",
        "admin": "Administrative and cadastral unit boundaries: PRG (PL), RUIAN (CZ).",
        "addresses": "PRG address points and streets; PL.",
        "special": "PRG special boundaries (44 kinds); PL.",
        "geomorphology": "Geomorphological units of Czechia, subprovince to part; CZ.",
        "map": "Cadastral map: EGiB (PL) and the cadastral map of Czechia (CZ).",
        "prices": "RCN register of real-estate transaction prices; PL.",
        "buildings": "3D building models (CityGML, LoD1 and LoD2); PL.",
        "mesh": "3D city mesh models (OBJ with textures); PL.",
        "trees": "3D tree models (CityGML, LoD1); PL.",
        "network": "HY-NET hydrographic network (INSPIRE Hydrography - Network); CZ.",
        "geographic": "Geographic names: PRNG (PL), Geonames (CZ).",
        "world": "Polish geographic names of the world (PRNG); PL.",
        "topographic": "Topographic maps: BDOT10k visualisations (PL), ZTM (CZ).",
        "control": "Geodetic control networks: GUGiK (PL), Bodove pole (CZ).",
        "geoid": "Quasi-geoid model: PL-geoid2021 (PL), QGZU-2013 (CZ).",
    },
    "country": {
        "pl": "Poland (GUGiK sources).",
        "cz": "Czechia (CUZK sources).",
        "auto": (
            "Both: the area is split by the bounding boxes of PL and CZ, one file per "
            "country."
        ),
    },
    "format": {
        "ASC": "ESRI ASCII grid.",
        "XYZ": "ASCII XYZ grid, ZIP.",
        "ASCII-NMT": "ASCII NMT points X Y Z, ZIP.",
        "TBD": "ASCII TBD structure points and lines, ZIP.",
        "TIN": "ESRI TIN, ZIP.",
        "TTN": "Intergraph TTN.",
        "GRD": "Intergraph GRD.",
        "DXF": "DXF (contours; CZ cadastral map).",
        "DGN": "DGN (contours, cadastral map, topographic map).",
        "SHP": "Shapefile.",
        "GPKG": "GeoPackage.",
        "GML": "GML.",
        "TIFF": "GeoTIFF.",
        "PDF": "PDF.",
        "XLSX": "Excel workbook.",
        "FGDB": "ESRI file geodatabase.",
        "VFK": "VFK exchange format of the Czech cadastre.",
    },
    "sheet_system": {
        "1992": "PL-1992 sheets (1:10000 and coarser).",
        "2000": "PL-2000 sheets (zones EPSG:2176-2179).",
        "sjtsk": "ZTM sheets in S-JTSK.",
        "etrs89": "ZTM sheets in ETRS89.",
    },
    "bbox_crs": {
        "EPSG:2176": "PL-2000 zone 5.",
        "EPSG:2177": "PL-2000 zone 6.",
        "EPSG:2178": "PL-2000 zone 7.",
        "EPSG:2179": "PL-2000 zone 8.",
        "EPSG:2180": "PL-1992 (ETRS89 / Poland CS92).",
        "EPSG:3045": "ETRS89 / UTM zone 33N.",
        "EPSG:4326": "WGS 84 geographic coordinates, in degrees.",
        "EPSG:5514": "S-JTSK / Krovak East North (CZ).",
    },
    "vertical_crs": {
        "EVRF2007": (
            "European Vertical Reference Frame 2007: the current PL height system "
            "(PL-EVRF2007-NH) and the native one of CZ TM33 files."
        ),
        "KRON86": "Kronstadt 86: the historical PL height system (PL-KRON86-NH).",
        "Bpv": (
            "Baltic after adjustment: native for CZ S-JTSK, SM5 and ImageServer data."
        ),
    },
    "model": {
        "dmr5g": "Terrain model DMR 5G.",
        "dmr4g": "Terrain model on a 5 m grid (DMR 4G).",
        "dmp1g": "Surface model DMP 1G.",
        "dmpok": "Surface model from image correlation (DMP OK).",
    },
    "coverage": {
        "standard": "The newest available orthophotos.",
        "high": "Orthophotos with a pixel of 10 cm or finer.",
    },
    "direction": {
        "n": "North.",
        "e": "East.",
        "s": "South.",
        "w": "West.",
    },
    "level": {
        "wojewodztwo": "Voivodeship (PL).",
        "powiat": "County (PL).",
        "gmina": "Municipality (PL).",
        "jednostka-ewidencyjna": "Cadastral unit (PL).",
        "obreb": "Cadastral precinct (PL).",
        "kraj": "Region, kraj (CZ).",
        "okres": "District, okres (CZ).",
        "obec": "Municipality, obec (CZ).",
        "katastralni-uzemi": "Cadastral area, katastralni uzemi (CZ).",
        "subprovincie": "Geomorphological subprovince (CZ).",
        "oblast": "Geomorphological area, oblast (CZ).",
        "celek": "Geomorphological unit, celek (CZ).",
        "podcelek": "Geomorphological subunit, podcelek (CZ).",
        "okrsek": "Geomorphological district, okrsek (CZ).",
        "podokrsek": "Geomorphological subdistrict, podokrsek (CZ).",
        "cast": "Geomorphological part, cast (CZ).",
    },
    "lod": {
        "1": "Level of detail 1 (LoD1).",
        "2": "Level of detail 2 (LoD2).",
    },
    "network": {
        "horizontal": "Horizontal control network.",
        "vertical": "Vertical (height) control network.",
        "gravity": "Gravimetric control network.",
        "magnetic": "Magnetic control network.",
        "archive-1942": (
            "Archive catalogues of the control points, 1942 (sheets 1:100000)."
        ),
        "archive-kronsztadt60": (
            "Archive catalogues of the control points, Kronstadt 60 (sheets 1:100000)."
        ),
        "gnss": "GNSS control points (CZ).",
        "densification": "Densification control network (CZ).",
        "horizontal-detailed": "Detailed horizontal control network (CZ).",
        "vertical-detailed": "Detailed vertical control network (CZ).",
    },
    "property": {
        "bdod": (
            "Bulk density of the fine earth; file unit cg/cm3 (kg/dm3 = value / 100)."
        ),
        "cec": (
            "Cation exchange capacity; file unit mmol(c)/kg (cmol(c)/kg = value / 10)."
        ),
        "cfvo": (
            "Coarse fragments by volume; file unit cm3/dm3 (cm3/100cm3 = value / 10)."
        ),
        "clay": "Clay content; file unit g/kg (percent = value / 10).",
        "nitrogen": "Total nitrogen; file unit cg/kg (g/kg = value / 100).",
        "ocd": "Organic carbon density; file unit hg/m3 (kg/m3 = value / 10).",
        "ocs": (
            "Organic carbon stock, depth 0-30cm only; file unit t/ha "
            "(kg/m2 = value / 10)."
        ),
        "phh2o": "Soil pH in water; the file holds pH x 10 (pH = value / 10).",
        "sand": "Sand content; file unit g/kg (percent = value / 10).",
        "silt": "Silt content; file unit g/kg (percent = value / 10).",
        "soc": "Soil organic carbon; file unit dg/kg (g/kg = value / 10).",
    },
    "stat": {
        "mean": "Mean.",
        "Q0.05": "5th percentile.",
        "Q0.5": "Median.",
        "Q0.95": "95th percentile.",
        "uncertainty": (
            "Prediction uncertainty: the file holds 10 * (Q0.95 - Q0.05) / Q0.5, "
            "unitless."
        ),
    },
    "update": {
        "upgrade": "Fetch newer content when the source signals it.",
        "force": "Fetch every file again; nothing is overwritten.",
    },
}

# Values of a regular form: (the options, the form, the meaning with {} for the value).
_PATTERNS: Final[tuple[tuple[frozenset[str], re.Pattern[str], str], ...]] = (
    (
        frozenset({"resolution"}),
        re.compile(r"[0-9.]+m"),
        "Cell or pixel size {} (metres).",
    ),
    (
        frozenset({"depth"}),
        re.compile(r"[0-9]+-[0-9]+cm"),
        "Depth interval {} below the surface.",
    ),
    (frozenset({"scale"}), re.compile(r"1:[0-9]+"), "Sheets or maps at the scale {}."),
    (frozenset({"year"}), re.compile(r"[0-9]{4}"), "Year {}."),
)


def meaning(option: str, value: str) -> str:
    """Return the one-line English meaning of an allowed value of an option.

    Parameters
    ----------
    option : str
        The name of the option (``product``, ``vertical_crs``, ``depth``...);
        ``horizontal_crs`` is read as ``bbox_crs``.
    value : str
        One of its allowed values.

    Raises
    ------
    KeyError
        The value has no meaning here: add it to ``MEANINGS``.
    """
    table = MEANINGS.get("bbox_crs" if option == "horizontal_crs" else option, {})
    if value in table:
        return table[value]
    for options, form, text in _PATTERNS:
        if option in options and form.fullmatch(value):
            return text.format(value)
    raise KeyError(f"no meaning of the value {value!r} of the option {option!r}")
