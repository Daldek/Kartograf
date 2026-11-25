"""``kartograf hydro``: hydrography - HY-NET, PGW and CAMELS-PL.

HY-NET of CUZK (ADR-042 D16), the water management plan data of PGW (ADR-059) and
the catchments and gauging stations of CAMELS-PL (ADR-062).
"""

from kartograf.catalog.commands._collection import (
    Products,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.shared import DATA_ERRORS
from kartograf.catalog.spec import Constraint, Example, Param
from kartograf.messages import message


def _content(products: Products) -> tuple[Param, ...]:
    # the feature datasets of the PGW geodatabase (ADR-059 decision 5): checked by
    # the library in any letter case, so the CLI names them in the help only
    return (
        Param(
            "layers",
            "str_list",
            message("catalog_hydro.layers_description"),
            metavar=message("catalog.metavar_codes"),
        ),
        # the releases of CAMELS-PL the registry reads (ADR-062): the library names a
        # refused or unknown one and why, so the CLI offers no ``choices``
        Param(
            "version",
            "str",
            message("catalog_hydro.version_description"),
            metavar=message("catalog.metavar_version"),
            allowed=lambda: choice_values(products(), "version"),
        ),
    )


COMMANDS = collection_commands(
    "hydro",
    summary=message("catalog_hydro.download_summary"),
    description=message("catalog_hydro.download_description"),
    area_result=message("catalog_hydro.area_result_description"),
    examples=(
        Example(
            {
                "product": "network",
                "country": "cz",
                "bbox": [-470000, -1130000, -440000, -1100000],
                "bbox_crs": "EPSG:5514",
            },
            title=message("catalog_hydro.example_water_network_rectangle_s_jtsk"),
        ),
        Example(
            {"product": "network", "country": "cz", "whole_country": True},
            title=message("catalog_hydro.example_water_network_national_file"),
        ),
        Example(
            {
                "product": "pgw",
                "country": "pl",
                "bbox": [380000, 540000, 390000, 550000],
                "bbox_crs": "EPSG:2180",
                "layers": ["PGW_WP"],
            },
            title=message("catalog_hydro.example_pgw_area_surface_waters"),
        ),
        Example(
            {"product": "pgw", "country": "pl", "whole_country": True},
            title=message("catalog_hydro.example_pgw_national_archive"),
        ),
        Example(
            {"product": "camels", "country": "pl", "whole_country": True},
            title=message("catalog_hydro.example_camels_newest_release"),
        ),
        Example(
            {
                "product": "camels",
                "country": "pl",
                "whole_country": True,
                "version": "2.0.0",
            },
            title=message("catalog_hydro.example_camels_release"),
        ),
    ),
    # no sheet or TERYT selection: PGW catchments are taken for a study area,
    # HY-NET is CZ (ADR-059 decision 1) and CAMELS-PL is read whole (ADR-062)
    sheet=False,
    whole_country=message("catalog_hydro.whole_country_description"),
    check=message("catalog_hydro.check_description"),
    # one GeoPackage of the area (for PGW after the archive it is read from), one
    # national file or the two files of a CAMELS-PL release: nothing to parallelise
    workers=None,
    # a CAMELS-PL release whose ZIP differs from the registry (ADR-062)
    errors=(*DATA_ERRORS, "data_error"),
    content=_content,
    constraints=(
        Constraint(
            "applies_to",
            (),
            message("catalog_hydro.rule_layers_applies_only_pgw"),
            "layers",
            {"product": ["pgw"]},
        ),
        Constraint(
            "excludes",
            ("whole_country",),
            message("catalog_hydro.rule_layers_excludes_whole_country"),
            "layers",
        ),
        Constraint(
            "applies_to",
            (),
            message("catalog_hydro.rule_version_applies_only_camels"),
            "version",
            {"product": ["camels"]},
        ),
    ),
)

GROUPS = (
    collection_group(
        "hydro",
        message("catalog_hydro.group_summary"),
        message("catalog_hydro.group_description"),
    ),
)
