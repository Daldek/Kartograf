"""Declare ``kartograf boundaries``.

Boundaries and addresses - PRG (GUGiK), RUIAN and geomorphological units (CUZK) (ADR-042
D9, D17; plan E, E3).
"""

from kartograf.catalog.commands._collection import (
    Products,
    choice_text,
    choice_values,
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example, Param
from kartograf.download.collections import collection_level_choices
from kartograf.messages import message


def _content(products: Products) -> tuple[Param, ...]:
    def level_help() -> str:
        return message(
            "catalog_boundaries.level_description",
            collection_level_choices=collection_level_choices(products()),
        )

    def format_help() -> str:
        return message(
            "catalog_boundaries.format_description",
            choice_text=choice_text(products(), "format"),
        )

    return (
        Param(
            "level",
            "per_country",
            level_help,
            metavar=message("catalog.metavar_level"),
            allowed=lambda: choice_values(products(), "level"),
            task=True,
        ),
        Param(
            "format",
            "str",
            format_help,
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "boundaries",
    summary=message("catalog_boundaries.download_summary"),
    description=message("catalog_boundaries.download_description"),
    teryt=message("catalog_boundaries.teryt_description"),
    examples=(
        Example(
            {"product": "admin", "teryt": "12"},
            title=message(
                "catalog_boundaries.example_prg_boundaries_voivodeship_package"
            ),
        ),
        Example(
            {
                "product": "admin",
                "country": "pl",
                "level": "gmina",
                "bbox": [550000, 220000, 590000, 270000],
                "bbox_crs": "EPSG:2180",
            },
            title=message("catalog_boundaries.example_pl_municipalities_rectangle"),
        ),
        Example(
            {
                "product": "addresses",
                "country": "pl",
                "whole_country": True,
                "format": "SHP",
            },
            title=message("catalog_boundaries.example_pl_address_points_national_file"),
        ),
        Example(
            {
                "product": "admin",
                "country": "cz",
                "level": "obec",
                "bbox": [-470000, -1130000, -440000, -1100000],
                "bbox_crs": "EPSG:5514",
            },
            title=message(
                "catalog_boundaries.example_cz_municipalities_ruian_rectangle_s_jtsk"
            ),
        ),
        Example(
            {
                "product": "admin",
                "country": "auto",
                "level": {"pl": "gmina", "cz": "obec"},
                "bbox": [18.60, 49.73, 18.66, 49.76],
                "bbox_crs": "EPSG:4326",
            },
            title=message(
                "catalog_boundaries.example_pl_municipalities_cz_obce_rectangle_border"
            ),
        ),
        Example(
            {
                "product": "special",
                "country": "pl",
                "bbox": [566200, 244650, 566250, 244700],
                "bbox_crs": "EPSG:2180",
            },
            title=message(
                "catalog_boundaries.example_pl_special_boundaries_rectangle_takes"
            ),
        ),
        Example(
            {
                "product": "geomorphology",
                "country": "cz",
                "level": "celek",
                "bbox": [-470000, -1130000, -440000, -1100000],
                "bbox_crs": "EPSG:5514",
            },
            title=message(
                "catalog_boundaries.example_cz_geomorphological_units_celky_rectangle"
            ),
        ),
    ),
    area_result=message("catalog_boundaries.area_result_description"),
    whole_country=message("catalog_boundaries.whole_country_description"),
    content=_content,
    rules=(message("catalog_boundaries.commands_rule"),),
)

GROUPS = (
    collection_group(
        "boundaries",
        message("catalog_boundaries.group_summary"),
        message("catalog_boundaries.group_description"),
    ),
)
