"""Declare ``kartograf landcover``.

BDOT10k and BDOO (GUGiK), CORINE Land Cover, ZABAGED, Data50 and Data250 (CUZK)
(ADR-039, ADR-042 D15, ADR-043).
"""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import (
    OUTPUT_TITLE,
    PL_SHEETS,
    PRODUCT_TITLE,
    SELECTION_TITLE,
    SHEET_AREA_HELP,
)
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.options import store_files
from kartograf.landcover.manager import (
    COLLECTION_SOURCES,
    LANDCOVER_PRODUCT_CHOICES,
    LANDCOVER_PRODUCTS,
    bdoo_year_choices,
    bdot10k_archive_choices,
)
from kartograf.messages import message
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.sources.descriptor import AtomFilesParams, UnitPackageParams
from kartograf.sources.registry import get_source, sources_for

_BDOT10K = "pl.gugik.bdot10k"


def _products() -> list[tuple[str, str]]:
    """Each product with the name and country of its source, as the help names it."""
    summaries = []
    for name in LANDCOVER_PRODUCTS:
        source = next(
            d
            for d in sources_for(product=name)
            if d.storage_subdir.split("/", 1)[0] == "landcover"
        )
        summaries.append((name, f"{source.name}, {source.country}"))
    return summaries


def _formats() -> list[str]:
    """Return the BDOT10k formats: the current packages and the yearly archive."""
    archive = (
        dict(variant.choice)["format"]
        for channel in get_source(_BDOT10K).channels
        if isinstance(channel.params, UnitPackageParams)
        for variant in channel.params.variants
    )
    return list(dict.fromkeys((*Bdot10kProvider.OPENDATA_PATTERNS, *archive)))


def _national_file_crs() -> list[str]:
    """Return the ``--horizontal-crs`` values.

    The CRSs in which the national files of the land cover sources on the collection
    engines are published (the ATOM channels of the registry).
    """
    return list(
        dict.fromkeys(
            crs
            for key in COLLECTION_SOURCES.values()
            for channel in get_source(key).channels
            if isinstance(channel.params, AtomFilesParams)
            for crs in channel.params.crs
        )
    )


def _year_help() -> str:
    return message(
        "catalog_landcover.year_description",
        bdot10k_archive_choices=bdot10k_archive_choices(),
        bdoo_year_choices=bdoo_year_choices(),
    )


def _product_help() -> str:
    return message(
        "catalog.product_choices_description", choices=LANDCOVER_PRODUCT_CHOICES
    )


_PRODUCT = replace(
    shared.PRODUCT,
    description=_product_help,
    allowed=lambda: LANDCOVER_PRODUCTS,
    choices=True,
)

_DOWNLOAD_PARAMS = (
    _PRODUCT,
    Param(
        "teryt",
        "str",
        message("catalog_landcover.teryt_description"),
        metavar=message("catalog.metavar_code"),
        task=True,
        section=SELECTION_TITLE,
    ),
    *shared.area(
        sheet=message("catalog_landcover.sheet_description", sheet=SHEET_AREA_HELP),
        accepts=PL_SHEETS,
    ),
    Param(
        "whole_country",
        "flag",
        message("catalog_landcover.whole_country_description"),
        default=False,
        task=True,
        section=SELECTION_TITLE,
    ),
    Param(
        "year",
        "int",
        _year_help,
        metavar=message("catalog.metavar_year"),
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "format",
        "str",
        message("catalog_landcover.format_description"),
        short="-f",
        allowed=_formats,
        choices=True,
        normalize="upper",
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "layers",
        "str_list",
        message("catalog_landcover.layers_description"),
        metavar=message("catalog.metavar_codes"),
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "keep_raw",
        "flag",
        message("catalog_landcover.keep_raw_description"),
        default=False,
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "horizontal_crs",
        "str",
        message("catalog_landcover.horizontal_crs_description"),
        allowed=_national_file_crs,
        choices=True,
        normalize="upper",
        task=True,
        section=PRODUCT_TITLE,
    ),
    *shared.target(lambda: store_files(["landcover"])),
    *shared.update_params(
        check=message("catalog_landcover.check_description"),
        upgrade=message("catalog_landcover.download_upgrade_description"),
        force=message("catalog_landcover.download_force_description"),
        plan=message(
            "catalog_landcover.download_plan_description", common=shared.PLAN_HELP
        ),
    ),
    shared.workers(
        message("catalog_landcover.workers_description"),
        1,
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_DOWNLOAD_CONSTRAINTS = (
    Constraint(
        "one_of",
        ("teryt", "sheet", "bbox", "geometry", "whole_country"),
        message("catalog_landcover.rule_give_exactly_one_area_teryt_sheet_bbox"),
    ),
    Constraint(
        "requires",
        ("horizontal_crs",),
        message("catalog_landcover.rule_whole_country_needs_horizontal_crs"),
        "whole_country",
    ),
    Constraint(
        "applies_to",
        (),
        message("catalog_landcover.rule_keep_raw_applies_only_current_bdot10k"),
        "keep_raw",
        {"product": ["bdot10k"]},
    ),
    Constraint(
        "applies_to",
        (),
        message("catalog_landcover.rule_whole_country_applies_only_zabaged_data50"),
        "whole_country",
        {"product": ["zabaged", "data50", "data250"]},
    ),
    *shared.target_constraints(),
)

COMMANDS = (
    Command(
        "landcover download",
        message("catalog_landcover.landcover_download_summary"),
        "data",
        "download_landcover",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=message(
            "catalog_landcover.landcover_download_description", note=shared.PLAIN_NOTE
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_landcover",
        check_result_schema="kartograf-plan/1",
        constraints=_DOWNLOAD_CONSTRAINTS,
        examples=(
            Example(
                {"product": "bdot10k", "teryt": "1465"},
                title=message("catalog_landcover.example_bdot10k_county_package"),
            ),
            Example(
                {"product": "bdoo", "teryt": "12", "year": 2023},
                title=message(
                    "catalog_landcover.example_bdoo_voivodeship_package_2023_archive"
                ),
            ),
            Example(
                {"product": "corine", "year": 2018, "sheet": "N-34-130-D"},
                title=message("catalog_landcover.example_corine_2018_sheet"),
            ),
            Example(
                {
                    "product": "zabaged",
                    "bbox": [-460000, -1120000, -450000, -1110000],
                    "bbox_crs": "EPSG:5514",
                },
                title=message("catalog_landcover.example_cz_zabaged_rectangle_s_jtsk"),
            ),
        ),
        rules=(message("catalog_landcover.landcover_download_rule"),),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    shared.list_sources_command("landcover", lambda: LANDCOVER_PRODUCTS),
    Command(
        "landcover list-layers",
        message("catalog_landcover.landcover_list_layers_summary"),
        "query",
        "list_layers",
        "kartograf-layers/1",
        (
            Param(
                "group",
                "str",
                flag=None,
                required=True,
                description=message("catalog_landcover.group_description"),
                fixed="landcover",
            ),
            replace(
                _PRODUCT,
                task=False,
                section=None,
            ),
            shared.JSON,
        ),
        description=message("catalog_landcover.landcover_list_layers_description"),
        rules=(),
        errors=("validation_error",),
        family="discovery",
        cardinality="bounded",
        examples=(
            Example(
                {"product": "bdoo"},
                title=message(
                    "catalog_landcover.example_classes_bdoo_per_archive_year"
                ),
            ),
            Example(
                {"product": "corine"},
                title=message("catalog_landcover.example_years_corine"),
            ),
        ),
    ),
)

GROUPS = (
    Group(
        "landcover",
        message("catalog_landcover.landcover_group_summary"),
        message("catalog_landcover.landcover_group_description"),
        products=_products,
    ),
)
