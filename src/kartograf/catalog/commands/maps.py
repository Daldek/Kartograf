"""``kartograf maps``: BDOT10k visualizations (PL) and ZTM sheets (CZ)."""

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
    def scale_help() -> str:
        return message(
            "catalog_maps.scale_description",
            choice_text=choice_text(products(), "scale"),
        )

    def format_help() -> str:
        return message(
            "catalog_maps.format_description",
            choice_text=choice_text(products(), "format"),
        )

    def sheet_system_help() -> str:
        return message(
            "catalog_maps.sheet_system_description",
            choice_text=choice_text(products(), "sheet_system"),
        )

    return (
        Param(
            "scale",
            "str",
            scale_help,
            metavar=message("catalog.metavar_scale"),
            allowed=lambda: choice_values(products(), "scale"),
            required=True,
        ),
        Param(
            "format",
            "str",
            format_help,
            metavar="FORMAT",
            allowed=lambda: choice_values(products(), "format"),
            required=True,
        ),
        Param(
            "sheet_system",
            "str",
            sheet_system_help,
            metavar=message("catalog.metavar_crs"),
            allowed=lambda: choice_values(products(), "sheet_system"),
        ),
    )


COMMANDS = collection_commands(
    "maps",
    summary=message("catalog_maps.download_summary"),
    description=message("catalog_maps.download_description"),
    area_result=message("catalog_maps.area_result_description"),
    examples=(
        Example(
            {
                "product": "topographic",
                "country": "pl",
                "sheet": "M-34-064-D-d-1",
                "scale": "1:10000",
                "format": "TIFF",
            },
            title=message("catalog_maps.example_pl_bdot10k_map_sheet"),
        ),
        Example(
            {
                "product": "topographic",
                "country": "cz",
                "sheet": "0510-D-11",
                "scale": "1:10000",
                "format": "TIFF",
            },
            title=message("catalog_maps.example_cz_ztm_map_sheet"),
        ),
        Example(
            {
                "product": "topographic",
                "country": "cz",
                "bbox": [-452000, -1112000, -450000, -1110000],
                "bbox_crs": "EPSG:5514",
                "scale": "1:10000",
                "sheet_system": "sjtsk",
                "format": "PDF",
            },
            title=message("catalog_maps.example_cz_ztm_map_sheets_rectangle"),
        ),
    ),
    content=_content,
    sheet_help=message("catalog_maps.sheet_help_description"),
    sheet_systems=("pl1992", "pl2000", "cz_ztm"),
    check=message("catalog_maps.check_description"),
)

GROUPS = (
    collection_group(
        "maps",
        message("catalog_maps.group_summary"),
        message("catalog_maps.group_description"),
    ),
)
