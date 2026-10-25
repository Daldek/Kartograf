"""``kartograf hydro``: hydrography - the HY-NET water network (CUZK) (ADR-042 D16)."""

from kartograf.catalog.commands._collection import (
    collection_commands,
    collection_group,
)
from kartograf.catalog.spec import Example
from kartograf.messages import message

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
    ),
    # sheet codes and TERYT select PL areas; HY-NET is CZ only
    sheet=False,
    whole_country=message("catalog_hydro.whole_country_description"),
    check=message("catalog_hydro.check_description"),
    # one GeoPackage of the area or one national file: nothing to parallelise
    workers=None,
)

GROUPS = (
    collection_group(
        "hydro",
        message("catalog_hydro.group_summary"),
        message("catalog_hydro.group_description"),
    ),
)
