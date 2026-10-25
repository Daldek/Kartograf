"""Declare ``kartograf models3d``.

3D models of GUGiK - buildings and trees (CityGML, powiat packages) and the mesh of
towns (OBJ tiles of an index) (ADR-042 D9; plan E, E5).
"""

from kartograf.catalog.commands._collection import (
    Products,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param
from kartograf.download.collections import collection_variant_choices
from kartograf.messages import message


def _content(products: Products) -> tuple[Param, ...]:
    def lod_help() -> str:
        return message(
            "catalog_models3d.lod_description",
            collection_variant_choices=collection_variant_choices(products()),
        )

    return (
        Param(
            "lod",
            "int",
            lod_help,
            metavar="N",
            allowed=lambda: choice_values(products(), "lod"),
            task=True,
        ),
        Param(
            "year",
            "int",
            message("catalog_models3d.year_description"),
            metavar=message("catalog.metavar_year"),
            allowed=lambda: choice_values(products(), "year"),
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "models3d",
    summary=message("catalog_models3d.download_summary"),
    description=message("catalog_models3d.download_description"),
    teryt=message("catalog_models3d.teryt_description"),
    examples=(
        Example(
            {"product": "buildings", "lod": 1, "year": 2024, "teryt": "1261"},
            title=message(
                "catalog_models3d.example_buildings_lod1_2024_county_package"
            ),
        ),
        Example(
            {
                "product": "mesh",
                "country": "pl",
                "bbox": [566200, 244650, 566250, 244700],
                "bbox_crs": "EPSG:2180",
            },
            title=message("catalog_models3d.example_city_mesh_tiles_rectangle"),
        ),
        Example(
            {"product": "trees", "teryt": "1261"},
            title=message(
                "catalog_models3d.example_trees_lod1_2023_county_package_0_3_25_gb"
            ),
        ),
    ),
    area_result=message("catalog_models3d.area_result_description"),
    check=message("catalog_models3d.check_description"),
    content=_content,
    rules=(message("catalog_models3d.commands_rule"),),
)

GROUPS = (
    collection_group(
        "models3d",
        message("catalog_models3d.group_summary"),
        message("catalog_models3d.group_description"),
    ),
)
