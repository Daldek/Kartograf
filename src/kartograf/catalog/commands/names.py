"""``kartograf names``: geographic names of Poland, Czechia and the world."""

from kartograf.catalog.commands._collection import (
    Products,
    choice_text,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param
from kartograf.messages import message


def _content(products: Products) -> tuple[Param, ...]:
    def format_help() -> str:
        return message(
            "catalog_names.format_description",
            choice_text=choice_text(products(), "format"),
        )

    return (
        Param(
            "format",
            "str",
            format_help,
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
        ),
        Param(
            "horizontal_crs",
            "str",
            message("catalog_names.horizontal_crs_description"),
            metavar=message("catalog.metavar_epsg_code"),
        ),
    )


COMMANDS = collection_commands(
    "names",
    summary=message("catalog_names.download_summary"),
    description=message("catalog_names.download_description"),
    examples=(
        Example(
            {
                "product": "geographic",
                "country": "pl",
                "bbox": [19.93, 50.055, 19.945, 50.065],
                "bbox_crs": "EPSG:4326",
            },
            title=message("catalog_names.example_prng_names_rectangle_wgs84"),
        ),
        Example(
            {
                "product": "geographic",
                "country": "cz",
                "whole_country": True,
                "format": "GPKG",
                "horizontal_crs": "EPSG:5514",
            },
            title=message("catalog_names.example_cz_geonames_national_file_s_jtsk"),
        ),
        Example(
            {
                "product": "world",
                "country": "pl",
                "bbox": [-74.02, 40.69, -73.92, 40.79],
                "bbox_crs": "EPSG:4326",
            },
            title=message(
                "catalog_names.example_polish_names_world_rectangle_new_york"
            ),
        ),
    ),
    area_result=message("catalog_names.area_result_description"),
    whole_country=message("catalog_names.whole_country_description"),
    check=message("catalog_names.check_description"),
    content=_content,
)

GROUPS = (
    collection_group(
        "names",
        message("catalog_names.group_summary"),
        message("catalog_names.group_description"),
    ),
)
