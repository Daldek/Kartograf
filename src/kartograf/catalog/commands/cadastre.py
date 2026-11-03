"""Declare ``kartograf cadastre``.

Cadastral map - EGiB (GUGiK) and the CZ cadastral map (CUZK) - and transaction prices
RCN (GUGiK) (ADR-042 D9; plan E, E3).
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
    def format_help() -> str:
        return message(
            "catalog_cadastre.format_description",
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
    )


COMMANDS = collection_commands(
    "cadastre",
    summary=message("catalog_cadastre.download_summary"),
    description=message("catalog_cadastre.download_description"),
    teryt=message("catalog_cadastre.teryt_description"),
    ku=message("catalog_cadastre.ku_description"),
    examples=(
        Example(
            {"product": "map", "teryt": "1261"},
            title=message("catalog_cadastre.example_egib_cadastral_map_county_export"),
        ),
        Example(
            {"product": "map", "ku": "623164", "format": "SHP"},
            title=message(
                "catalog_cadastre.example_cz_cadastral_map_cadastral_area_package"
            ),
        ),
        Example(
            {"product": "prices", "teryt": "1201"},
            title=message(
                "catalog_cadastre.example_rcn_transaction_prices_county_export"
            ),
        ),
    ),
    area_result=message("catalog_cadastre.area_result_description"),
    check=message("catalog_cadastre.check_description"),
    content=_content,
    rules=(message("catalog_cadastre.commands_rule"),),
)

GROUPS = (
    collection_group(
        "cadastre",
        message("catalog_cadastre.group_summary"),
        message("catalog_cadastre.group_description"),
    ),
)
