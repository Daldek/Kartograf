"""``kartograf hydro``: hydrography - HY-NET (CUZK, ADR-042 D16) and PGW (ADR-059)."""

from kartograf.catalog.commands._collection import (
    Products,
    collection_commands,
    collection_group,
)
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
    ),
    # no sheet or TERYT selection: PGW catchments are taken for a study area, and
    # HY-NET is CZ (ADR-059 decision 1)
    sheet=False,
    whole_country=message("catalog_hydro.whole_country_description"),
    check=message("catalog_hydro.check_description"),
    # one GeoPackage of the area (for PGW after the archive it is read from) or one
    # national file: nothing to parallelise
    workers=None,
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
    ),
)

GROUPS = (
    collection_group(
        "hydro",
        message("catalog_hydro.group_summary"),
        message("catalog_hydro.group_description"),
    ),
)
