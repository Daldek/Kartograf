"""Declare ``kartograf imagery``.

GUGiK images - orthophotomap (sheets and WCS cutout), intensity images, true
orthophotomap (sheets and WCS cutout), oblique orthophotomap (PL) - and CUZK SM5
orthophoto sheets (CZ) (ADR-039, ADR-042 D13, D14, plan E1).
"""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import (
    OUTPUT_TITLE,
    PL_SHEETS,
    SELECTION_TITLE,
)
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.options import (
    COUNTRIES,
    COUNTRY_CHOICES,
    IMAGERY_PRODUCTS,
    SCALE_2000_CHOICES,
    SCALES_2000,
    SHEET_SYSTEM_CHOICES,
    product_choices,
    product_directory,
    store_files,
)
from kartograf.download.orto_cutout import (
    ORTO_CUTOUT_CRS,
    cutout_resolution_choices,
    orto_coverage_choices,
)
from kartograf.messages import message
from kartograf.providers.pl.gugik_orto import (
    ORTO_KEY,
    image_directions,
    image_source,
    wcs_cutout_channels,
)
from kartograf.sources.descriptor import WcsCutoutParams
from kartograf.sources.variants import resolution_label, variants

# The sheet systems of the imagery commands: the PL ones and the CZ SM5 sheets
# of the orthophotomap.
_ACCEPTS = (*PL_SHEETS, "cz_sm5")
_CAMPAIGNS = message("catalog.section_year_flights")


def _products() -> list[tuple[str, str]]:
    return shared.product_summaries(IMAGERY_PRODUCTS, product_choices)


def _directions() -> list[str]:
    """Return the view directions of the image products (the oblique orthophotomap)."""
    found = (d for product in IMAGERY_PRODUCTS for d in image_directions(product))
    return list(dict.fromkeys(found))


def _coverages() -> list[str]:
    """Return the WCS variants of the orthophotomap cutout (``standard``, ``high``)."""
    return [
        channel.params.variant
        for channel in wcs_cutout_channels(ORTO_KEY)
        if isinstance(channel.params, WcsCutoutParams)
    ]


def _cutout_resolutions() -> list[str]:
    """Return the pixels of every WCS cutout channel of the image products."""
    labels: list[str] = []
    for product in IMAGERY_PRODUCTS:
        source = image_source(product)
        channels = wcs_cutout_channels(source.key) if source is not None else ()
        for channel in channels:
            if isinstance(channel.params, WcsCutoutParams):
                labels += [resolution_label(v) for v in channel.params.resolutions]
    return list(dict.fromkeys(labels))


def _sheet_systems() -> list[str]:
    """Return the PL sheet systems the registry has variants for.

    They are the values of ``--sheet-system``.
    """
    found = variants(country="PL")
    return sorted({system for v in found for system in v.systems})


def _output_files() -> str:
    return store_files(product_directory(p) for p in IMAGERY_PRODUCTS)


def _sheet_system_help() -> str:
    return message(
        "catalog_imagery.sheet_system_description",
        sheet_system_choices=SHEET_SYSTEM_CHOICES,
    )


def _scale_help() -> str:
    return message(
        "catalog_imagery.scale_description", scale_2000_choices=SCALE_2000_CHOICES
    )


def _coverage_help() -> str:
    return message(
        "catalog_imagery.coverage_description",
        orto_coverage_choices=orto_coverage_choices(),
    )


def _resolution_help() -> str:
    return message(
        "catalog_imagery.resolution_description",
        cutout_resolution_choices=cutout_resolution_choices(IMAGERY_PRODUCTS),
    )


def _country_description() -> str:
    return message(
        "catalog_imagery.country_description", country_choices=COUNTRY_CHOICES
    )


_DOWNLOAD_PARAMS = (
    shared.product(lambda: IMAGERY_PRODUCTS, product_choices),
    shared.country(lambda: COUNTRIES, _country_description),
    *shared.area(
        sheet=message("catalog_imagery.sheet_description"),
        accepts=_ACCEPTS,
        geometry=message("catalog_imagery.geometry_description"),
    ),
    Param(
        "direction",
        "str_list",
        message("catalog_imagery.direction_description"),
        metavar=message("catalog.metavar_directions"),
        allowed=_directions,
        task=True,
        section=SELECTION_TITLE,
    ),
    Param(
        "sheet_system",
        "str",
        _sheet_system_help,
        allowed=_sheet_systems,
        choices=True,
        task=True,
        section=message("catalog.section_sheets"),
    ),
    Param(
        "scale",
        "str",
        _scale_help,
        metavar=message("catalog.metavar_scale"),
        allowed=lambda: SCALES_2000,
        task=True,
        section=message("catalog.section_sheets"),
    ),
    Param(
        "cutout",
        "flag",
        message("catalog_imagery.cutout_description"),
        default=False,
        task=True,
        section=message("catalog.section_cutout_pl"),
    ),
    Param(
        "horizontal_crs",
        "str",
        message("catalog_imagery.horizontal_crs_description"),
        allowed=lambda: [ORTO_CUTOUT_CRS],
        choices=True,
        normalize="upper",
        task=True,
        section=message("catalog.section_cutout_pl"),
    ),
    Param(
        "coverage",
        "str",
        _coverage_help,
        metavar=message("catalog.metavar_variant"),
        allowed=_coverages,
        task=True,
        section=message("catalog.section_cutout_pl"),
    ),
    Param(
        "resolution",
        "per_country",
        _resolution_help,
        short="-r",
        metavar=message("catalog.metavar_resolution"),
        allowed=_cutout_resolutions,
        task=True,
        section=message("catalog.section_cutout_pl"),
    ),
    Param(
        "year",
        "int",
        message("catalog_imagery.year_description"),
        metavar=message("catalog.metavar_year"),
        task=True,
        section=_CAMPAIGNS,
    ),
    Param(
        "min_year",
        "int",
        message("catalog_imagery.min_year_description"),
        metavar=message("catalog.metavar_year"),
        task=True,
        section=_CAMPAIGNS,
    ),
    Param(
        "max_year",
        "int",
        message("catalog_imagery.max_year_description"),
        metavar=message("catalog.metavar_year"),
        task=True,
        section=_CAMPAIGNS,
    ),
    Param(
        "all_campaigns",
        "flag",
        message("catalog_imagery.all_campaigns_description"),
        default=False,
        task=True,
        section=_CAMPAIGNS,
    ),
    Param(
        "full_sheet",
        "flag",
        message("catalog_imagery.full_sheet_description"),
        default=False,
        task=True,
        section=_CAMPAIGNS,
    ),
    *shared.target(_output_files, sheets=True),
    *shared.update_params(
        check=message("catalog_imagery.check_description"),
        upgrade=message("catalog_imagery.download_upgrade_description"),
        force=message("catalog_imagery.download_force_description"),
        plan=message(
            "catalog_imagery.download_plan_description", common=shared.PLAN_HELP
        ),
    ),
    shared.workers(
        message("catalog_imagery.workers_description"),
        4,
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_DOWNLOAD_CONSTRAINTS = (
    Constraint(
        "one_of",
        ("sheet", "bbox", "geometry"),
        message("catalog_imagery.rule_give_exactly_one_area_sheet_bbox_geometry"),
    ),
    Constraint(
        "requires",
        ("horizontal_crs", "resolution"),
        message("catalog_imagery.rule_cutout_needs_horizontal_crs_resolution"),
        "cutout",
    ),
    Constraint(
        "required_when",
        (),
        message("catalog_imagery.rule_product_orto_cutout_needs_coverage"),
        "coverage",
        {"cutout": True, "product": ["orto"]},
    ),
    Constraint(
        "applies_to",
        (),
        message("catalog_imagery.rule_horizontal_crs_coverage_resolution_work_only"),
        "horizontal_crs",
        {"cutout": True},
    ),
    Constraint(
        "excludes",
        ("sheet",),
        message("catalog_imagery.rule_cutout_works_only_bbox_geometry"),
        "cutout",
    ),
    Constraint(
        "applies_to",
        (),
        message("catalog_imagery.rule_direction_applies_only_product_oblique_orto"),
        "direction",
        {"product": ["oblique-orto"]},
    ),
    Constraint(
        "excludes",
        ("min_year", "max_year"),
        message("catalog_imagery.rule_year_excludes_min_year_max_year"),
        "year",
    ),
    *shared.target_constraints(campaigns=True),
)

_DOWNLOAD_EXAMPLES = (
    Example(
        {"product": "orto", "sheet": "N-34-130-D-d-2-4"},
        title=message("catalog_imagery.example_pl_orthophoto_sheet"),
    ),
    Example(
        {
            "product": "orto",
            "country": "pl",
            "bbox": [566000, 243000, 566500, 243500],
            "bbox_crs": "EPSG:2180",
            "cutout": True,
            "horizontal_crs": "EPSG:2180",
            "coverage": "standard",
            "resolution": "0.25m",
        },
        title=message("catalog_imagery.example_pl_orthophoto_wcs_cutout"),
    ),
    Example(
        {
            "product": "orto",
            "country": "pl",
            "bbox": [566000, 243000, 566500, 243500],
            "bbox_crs": "EPSG:2180",
            "sheet_system": "1992",
        },
        title=message(
            "catalog_imagery.example_pl_orthophoto_sheets_rectangle_1992_system"
        ),
    ),
    Example(
        {"product": "oblique-orto", "sheet": "7.125.11.08", "direction": ["n"]},
        title=message("catalog_imagery.example_pl_oblique_orthophoto_north_direction"),
    ),
    Example(
        {"product": "orto", "sheet": "CTES96"},
        title=message("catalog_imagery.example_cz_orthophoto_sm5_sheet"),
    ),
    Example(
        {
            "product": "orto",
            "country": "cz",
            "bbox": [-447000, -1114000, -446000, -1113000],
            "bbox_crs": "EPSG:5514",
        },
        title=message("catalog_imagery.example_cz_orthophoto_sm5_sheets_rectangle"),
    ),
)

COMMANDS = (
    Command(
        "imagery download",
        message("catalog_imagery.imagery_download_summary"),
        "data",
        "download_data",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=message(
            "catalog_imagery.imagery_download_description", note=shared.PLAIN_NOTE
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_data",
        check_result_schema="kartograf-plan/1",
        constraints=_DOWNLOAD_CONSTRAINTS,
        examples=_DOWNLOAD_EXAMPLES,
        rules=(message("catalog_imagery.imagery_download_rule"),),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    shared.list_sources_command("imagery", lambda: IMAGERY_PRODUCTS),
)

GROUPS = (
    Group(
        "imagery",
        message("catalog_imagery.imagery_group_summary"),
        message("catalog_imagery.imagery_group_description"),
        products=_products,
    ),
)
