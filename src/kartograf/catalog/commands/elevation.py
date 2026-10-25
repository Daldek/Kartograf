"""``kartograf elevation``: NMT, NMPT, LAZ and contours from GUGiK/CUZK (ADR-039)."""

from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import OUTPUT_TITLE, PL_SHEETS, PRODUCT_TITLE
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.availability import (
    AVAILABILITY_COUNTRIES,
    AVAILABILITY_PRODUCTS,
)
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_contours import contours_formats
from kartograf.download.options import (
    COUNTRIES,
    COUNTRY_CHOICES,
    ELEVATION_PRODUCTS,
    SCALE_2000_CHOICES,
    SCALES_2000,
    SHEET_SYSTEM_CHOICES,
    cz_resolution_help,
    format_text,
    product_choices,
    product_directory,
    resolution_text,
    store_files,
    vertical_crs_text,
)
from kartograf.messages import message
from kartograf.sources.variants import (
    CZ_VERTICAL_TEXT,
    cz_model_text,
    format_tokens,
    resolution_label,
    variants,
)

_SHEET_PRODUCTS = ("nmt", "nmpt")
# The sheet systems of the elevation commands: the PL ones and the CZ ones of
# the sheet products (SM5 sheets, TM33 tiles).
_ACCEPTS = (*PL_SHEETS, "cz_sm5", "cz_tm33")


def _products() -> list[tuple[str, str]]:
    return shared.product_summaries(ELEVATION_PRODUCTS, product_choices)


def _resolutions() -> list[str]:
    """Every grid label of the sheet products of both countries."""
    found = [v for product in _SHEET_PRODUCTS for v in variants(product=product)]
    values = sorted({v.resolution_m for v in found if v.resolution_m is not None})
    return [resolution_label(value) for value in values]


def _vertical_systems() -> list[str]:
    """Return the height systems of every variant, registry order."""
    return list(dict.fromkeys(v.vertical_crs for v in variants() if v.vertical_crs))


def _formats() -> list[str]:
    """Return the ``--format`` tokens.

    The file formats of the PL sheet products and the CZ contours.
    """
    found = tuple(
        v
        for product in _SHEET_PRODUCTS
        for v in variants(product=product, country="PL")
    )
    return list(dict.fromkeys((*format_tokens(found), *contours_formats())))


def _models() -> list[str]:
    """Return the CUZK models of the CZ point clouds."""
    found = variants(product="laz", country="CZ")
    return list(dict.fromkeys(v.model for v in found if v.model is not None))


def _sheet_systems() -> list[str]:
    """Return the PL sheet systems the registry has variants for.

    They are the values of ``--sheet-system``.
    """
    found = variants(country="PL")
    return sorted({system for v in found for system in v.systems})


def _resolution_help() -> str:
    return message(
        "catalog_elevation.resolution_description",
        resolution_text=resolution_text(),
        cz_resolution_help=cz_resolution_help(),
    )


def _model_help() -> str:
    return message("catalog_elevation.model_description", cz_model_text=cz_model_text())


def _vertical_crs_help() -> str:
    return message(
        "catalog_elevation.vertical_crs_description",
        vertical_crs_text=vertical_crs_text(),
        cz_vertical_text=CZ_VERTICAL_TEXT,
    )


def _format_help() -> str:
    return message(
        "catalog_elevation.format_description",
        format_text=format_text(),
        contours_formats=", ".join(contours_formats()),
    )


def _scale_help() -> str:
    return message(
        "catalog_elevation.scale_description", scale_2000_choices=SCALE_2000_CHOICES
    )


def _sheet_system_help() -> str:
    return message(
        "catalog_elevation.sheet_system_description",
        sheet_system_choices=SHEET_SYSTEM_CHOICES,
    )


def _output_files() -> str:
    return store_files(product_directory(p) for p in ELEVATION_PRODUCTS)


def _country_description() -> str:
    return message(
        "catalog_elevation.country_description", country_choices=COUNTRY_CHOICES
    )


def _availability_country_description() -> str:
    return message(
        "catalog_elevation.availability_country_description",
        countries=", ".join(AVAILABILITY_COUNTRIES.values()),
    )


_DOWNLOAD_PARAMS = (
    shared.product(lambda: ELEVATION_PRODUCTS, product_choices),
    shared.country(lambda: COUNTRIES, _country_description),
    *shared.area(
        sheet=message("catalog_elevation.sheet_description"),
        accepts=_ACCEPTS,
        geometry=message("catalog_elevation.geometry_description"),
    ),
    Param(
        "resolution",
        "per_country",
        _resolution_help,
        short="-r",
        metavar=message("catalog.metavar_resolution"),
        allowed=_resolutions,
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "model",
        "str",
        _model_help,
        metavar="MODEL",
        allowed=_models,
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "vertical_crs",
        "per_country",
        _vertical_crs_help,
        metavar=message("catalog.metavar_crs"),
        allowed=_vertical_systems,
        task=True,
        section=PRODUCT_TITLE,
    ),
    Param(
        "format",
        "str",
        _format_help,
        metavar="FORMAT",
        allowed=_formats,
        task=True,
        section=PRODUCT_TITLE,
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
        message("catalog_elevation.cutout_description"),
        default=False,
        task=True,
        section=message("catalog.section_cutout"),
    ),
    Param(
        "horizontal_crs",
        "str",
        message("catalog_elevation.horizontal_crs_description"),
        # the PL cutout set (download/cutout.py) also constrains the CZ path -
        # extending it on one side only requires per-country validation
        allowed=lambda: list(CUTOUT_CRS),
        choices=True,
        normalize="upper",
        task=True,
        section=message("catalog.section_cutout"),
    ),
    Param(
        "year",
        "int",
        message("catalog_elevation.year_description"),
        metavar=message("catalog.metavar_year"),
        task=True,
        section=message("catalog.section_year_flights_tiles"),
    ),
    Param(
        "min_year",
        "int",
        message("catalog_elevation.min_year_description"),
        metavar=message("catalog.metavar_year"),
        task=True,
        section=message("catalog.section_year_flights_tiles"),
    ),
    Param(
        "max_year",
        "int",
        message("catalog_elevation.max_year_description"),
        metavar=message("catalog.metavar_year"),
        task=True,
        section=message("catalog.section_year_flights_tiles"),
    ),
    Param(
        "all_campaigns",
        "flag",
        message("catalog_elevation.all_campaigns_description"),
        default=False,
        task=True,
        section=message("catalog.section_year_flights_tiles"),
    ),
    Param(
        "full_sheet",
        "flag",
        message("catalog_elevation.full_sheet_description"),
        default=False,
        task=True,
        section=message("catalog.section_year_flights_tiles"),
    ),
    Param(
        "min_density",
        "int",
        message("catalog_elevation.min_density_description"),
        metavar="N",
        task=True,
        section=message("catalog.section_year_flights_tiles"),
        unit="points/m2",
    ),
    *shared.target(_output_files, sheets=True),
    *shared.update_params(
        check=message("catalog_elevation.check_description"),
        upgrade=message("catalog_elevation.download_upgrade_description"),
        force=message("catalog_elevation.download_force_description"),
        plan=message(
            "catalog_elevation.download_plan_description", common=shared.PLAN_HELP
        ),
    ),
    shared.workers(
        message("catalog_elevation.workers_description"),
        4,
    ),
    shared.QUIET,
    replace(shared.JSON, section=OUTPUT_TITLE),
)

_DOWNLOAD_CONSTRAINTS = (
    Constraint(
        "one_of",
        ("sheet", "bbox", "geometry"),
        message("catalog_elevation.rule_give_exactly_one_area_sheet_bbox_geometry"),
    ),
    Constraint(
        "requires",
        ("horizontal_crs",),
        message("catalog_elevation.rule_cutout_needs_horizontal_crs"),
        "cutout",
    ),
    Constraint(
        "applies_to",
        (),
        message("catalog_elevation.rule_horizontal_crs_works_only_cutout"),
        "horizontal_crs",
        {"cutout": True},
    ),
    Constraint(
        "excludes",
        ("sheet",),
        message("catalog_elevation.rule_cutout_works_only_bbox_geometry"),
        "cutout",
    ),
    Constraint(
        "excludes",
        ("min_year", "max_year"),
        message("catalog_elevation.rule_year_excludes_min_year_max_year"),
        "year",
    ),
    Constraint(
        "applies_to",
        (),
        message("catalog_elevation.rule_min_density_works_only_product_laz"),
        "min_density",
        {"product": ["laz"]},
    ),
    Constraint(
        "applies_to",
        (),
        message("catalog_elevation.rule_model_applies_only_product_laz"),
        "model",
        {"product": ["laz"]},
    ),
    *shared.target_constraints(campaigns=True),
)

_DOWNLOAD_EXAMPLES = (
    Example(
        {
            "product": "nmt",
            "sheet": "N-34-130-D-d-2-4",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
        },
        title=message("catalog_elevation.example_pl_sheet_nmt_1_m_evrf2007"),
    ),
    Example(
        {
            "product": "laz",
            "country": "pl",
            "bbox": [530000, 382000, 533000, 386000],
            "bbox_crs": "EPSG:2180",
            "vertical_crs": "KRON86",
        },
        title=message("catalog_elevation.example_pl_laz_point_cloud_rectangle"),
    ),
    Example(
        {
            "product": "nmt",
            "country": "pl",
            "bbox": [565000, 242000, 565500, 242500],
            "bbox_crs": "EPSG:2180",
            "sheet_system": "1992",
            "resolution": "5m",
            "vertical_crs": "EVRF2007",
        },
        title=message("catalog_elevation.example_pl_area_nmt_5_m_sheets_1992_system"),
    ),
    Example(
        {
            "product": "nmt",
            "country": "pl",
            "bbox": [566000, 243000, 566500, 243500],
            "bbox_crs": "EPSG:2180",
            "cutout": True,
            "horizontal_crs": "EPSG:2180",
            "vertical_crs": "EVRF2007",
        },
        title=message("catalog_elevation.example_pl_cutout_nmt_1_m_wcs"),
    ),
    Example(
        {
            "product": "nmt",
            "sheet": "CTES96",
            "resolution": "5m",
            "vertical_crs": "Bpv",
        },
        title=message("catalog_elevation.example_cz_sm5_sheet_nmt_5_m_bpv"),
    ),
    Example(
        {
            "product": "nmt",
            "country": "cz",
            "bbox": [-447000, -1114000, -446000, -1113000],
            "bbox_crs": "EPSG:5514",
            "cutout": True,
            "horizontal_crs": "EPSG:5514",
            "resolution": "5m",
            "vertical_crs": "Bpv",
        },
        title=message("catalog_elevation.example_cz_cutout_s_jtsk"),
    ),
    Example(
        {
            "product": "laz",
            "country": "cz",
            "bbox": [-447000, -1114000, -446000, -1113000],
            "bbox_crs": "EPSG:5514",
            "model": "dmr5g",
            "vertical_crs": "Bpv",
        },
        title=message(
            "catalog_elevation.example_cz_laz_point_cloud_dmr_5g_model_rectangle"
        ),
    ),
)

_AVAILABILITY_PARAMS = (
    replace(
        shared.product(lambda: AVAILABILITY_PRODUCTS, product_choices),
        task=False,
    ),
    replace(
        shared.country(
            lambda: list(AVAILABILITY_COUNTRIES), _availability_country_description
        ),
        task=False,
    ),
    *(
        replace(param, task=False)
        for param in shared.area(
            sheet=message("catalog_elevation.sheet_description_2"),
            accepts=_ACCEPTS,
            geometry=message("catalog_elevation.geometry_description_2"),
        )
    ),
    Param(
        "year",
        "int",
        message("catalog_elevation.availability_year_description"),
        metavar=message("catalog.metavar_year"),
        section=message("catalog.section_year_availability"),
    ),
    Param(
        "min_year",
        "int",
        message("catalog_elevation.availability_min_year_description"),
        metavar=message("catalog.metavar_year"),
        section=message("catalog.section_year_availability"),
    ),
    Param(
        "max_year",
        "int",
        message("catalog_elevation.availability_max_year_description"),
        metavar=message("catalog.metavar_year"),
        section=message("catalog.section_year_availability"),
    ),
    Param(
        "details",
        "flag",
        argument=None,
        section=message("catalog.section_result"),
        description=message("catalog_elevation.details_description"),
    ),
    Param(
        "json",
        "flag",
        argument=None,
        section=message("catalog.section_result"),
        description=message("catalog_elevation.json_description"),
    ),
    Param(
        "force",
        "flag",
        message("catalog_elevation.force_description"),
        default=False,
        section=message("catalog.section_result"),
    ),
)

COMMANDS = (
    Command(
        "elevation download",
        message("catalog_elevation.elevation_download_summary"),
        "data",
        "download_data",
        "kartograf-download/1",
        _DOWNLOAD_PARAMS,
        description=message(
            "catalog_elevation.elevation_download_description", note=shared.PLAIN_NOTE
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_data",
        check_result_schema="kartograf-plan/1",
        constraints=_DOWNLOAD_CONSTRAINTS,
        examples=_DOWNLOAD_EXAMPLES,
        rules=(
            message("catalog_elevation.elevation_download_rule_1"),
            message("catalog_elevation.elevation_download_rule_2"),
        ),
        errors=shared.DATA_ERRORS,
        family="data",
        core=True,
    ),
    shared.list_sources_command("elevation", lambda: ELEVATION_PRODUCTS),
    Command(
        "elevation availability",
        message("catalog_elevation.elevation_availability_summary"),
        "query",
        "check_availability",
        "kartograf-availability/1",
        _AVAILABILITY_PARAMS,
        description=message("catalog_elevation.elevation_availability_description"),
        effects=("network",),
        constraints=(
            Constraint(
                "one_of",
                ("sheet", "bbox", "geometry"),
                message(
                    "catalog_elevation.rule_give_exactly_one_area_sheet_bbox_geometry"
                ),
            ),
            Constraint(
                "excludes",
                ("min_year", "max_year"),
                message("catalog_elevation.rule_year_excludes_min_year_max_year"),
                "year",
            ),
        ),
        examples=(
            Example(
                {
                    "product": "nmt",
                    "country": "pl",
                    "bbox": [565000, 242000, 569000, 246000],
                    "bbox_crs": "EPSG:2180",
                },
                title=message(
                    "catalog_elevation.example_nmt_availability_pl_rectangle"
                ),
            ),
            Example(
                {"product": "nmpt", "sheet": "CTES96"},
                title=message("catalog_elevation.example_nmpt_availability_cz_sheet"),
            ),
            Example(
                {
                    "product": "laz",
                    "country": "pl",
                    "geometry": "zlewnia.gpkg",
                    "min_year": 2020,
                },
                title=message(
                    "catalog_elevation.example_laz_availability_pl_since_2020_geometry"
                ),
                run={"details": True},
            ),
        ),
        rules=(message("catalog_elevation.elevation_availability_rule"),),
        errors=(
            "validation_error",
            "source_unavailable",
            "no_data",
            "store_unavailable",
            "io_error",
            "forbidden",
        ),
        family="availability",
        core=True,
    ),
)

GROUPS = (
    Group(
        "elevation",
        message("catalog_elevation.elevation_group_summary"),
        message("catalog_elevation.elevation_group_description"),
        products=_products,
    ),
)
