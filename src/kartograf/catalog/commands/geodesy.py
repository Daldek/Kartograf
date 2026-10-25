"""Declare ``kartograf geodesy``.

Survey control networks - PRPOG (GUGiK, PL) and Bodove pole (CUZK, CZ) - and the
quasi-geoid models PL-geoid2021 and QGZU-2013 (plan E, E5).
"""

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
    def network_help() -> str:
        return message(
            "catalog_geodesy.network_description",
            choice_text=choice_text(products(), "network"),
        )

    return (
        Param(
            "network",
            "per_country",
            network_help,
            metavar=message("catalog.metavar_network"),
            allowed=lambda: choice_values(products(), "network"),
            task=True,
        ),
    )


COMMANDS = collection_commands(
    "geodesy",
    summary=message("catalog_geodesy.download_summary"),
    description=message("catalog_geodesy.download_description"),
    teryt=message("catalog_geodesy.teryt_description"),
    examples=(
        Example(
            {"product": "control", "network": "horizontal", "teryt": "1201"},
            title=message(
                "catalog_geodesy.example_pl_horizontal_control_county_package"
            ),
        ),
        Example(
            {
                "product": "control",
                "country": "pl",
                "network": "vertical",
                "bbox": [560000, 240000, 575000, 250000],
                "bbox_crs": "EPSG:2180",
            },
            title=message("catalog_geodesy.example_pl_vertical_control_rectangle"),
        ),
        Example(
            {"product": "geoid", "country": "cz", "whole_country": True},
            title=message(
                "catalog_geodesy.example_cz_quasi_geoid_qgzu_2013_national_file"
            ),
        ),
    ),
    area_result=message("catalog_geodesy.area_result_description"),
    whole_country=message("catalog_geodesy.whole_country_description"),
    check=message("catalog_geodesy.check_description"),
    content=_content,
)

GROUPS = (
    collection_group(
        "geodesy",
        message("catalog_geodesy.group_summary"),
        message("catalog_geodesy.group_description"),
    ),
)
