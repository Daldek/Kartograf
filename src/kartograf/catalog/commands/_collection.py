"""Declare ``download`` and ``list-sources`` of a collection group.

The groups are ``boundaries``, ``cadastre``, ``models3d``, ``hydro``, ``names``,
``maps`` and ``geodesy`` (ADR-042 D9).

Every collection group has the same command shape: ``--product`` and
``--country`` like ``elevation``/``imagery`` (the countries of the group's
products plus ``auto``), one selection (``--teryt``, in ``cadastre``
``--ku``, ``--sheet``/``--bbox``/``--geometry``, in some groups
``--whole-country``), the content flags of the group only (``--level``,
``--lod``/``--year``, ``--format``, ``--network``, ...), the store flags
and ``--workers`` (default 1; not in a group whose request is always one
file - ``hydro``). ``--teryt`` and ``--sheet`` select PL units and sheet
codes: a group without PL sources (``hydro``) has neither; ``--ku`` selects
a CZ cadastral area. The choices in ``--help`` come from the source registry
through the library; the examples are the ``epilog`` of ``download --help``.

The pattern lives here (a module starting with ``_`` is no group): the group
modules call ``collection_commands`` with their texts and content flags.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace

from kartograf.catalog import shared
from kartograf.catalog.shared import (
    BBOX_HELP,
    DATA_ERRORS,
    GEOMETRY_HELP,
    OUTPUT_TITLE,
    PL_SHEETS,
    PRODUCT_TITLE,
    SELECTION_TITLE,
    SHEET_AREA_HELP,
)
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.collections import (
    collection_choice_values,
    collection_countries,
    collection_product_choices,
    collection_products,
)
from kartograf.download.options import country_choices, store_files
from kartograf.messages import message

WORKERS_HELP = message("catalog.collection_workers_description")
CHECK_HELP = message("catalog.collection_check_description")

# Provider of the products of a group (the registry decides, late).
Products = Callable[[], tuple[str, ...]]
# What a group adds to the common flags: its content parameters, which may
# describe themselves from the group's products.
Content = Callable[[Products], Sequence[Param]]


def choice_values(products: Sequence[str], key: str) -> list[str]:
    """Return the values of the option ``key`` over a group, each once.

    The products and countries of the group are walked in registry order.
    """
    found = (
        value
        for product in products
        for values in collection_choice_values(product, key).values()
        for value in values
    )
    return list(dict.fromkeys(found))


def choice_text(products: Sequence[str], key: str) -> str:
    """Return the values of the option ``key`` per product and country.

    The text is like ``admin PL: a, b; admin CZ: c`` (the texts of ``--format``,
    ``--network``, ...).
    """
    return "; ".join(
        f"{product} {country}: {', '.join(values)}"
        for product in products
        for country, values in collection_choice_values(product, key).items()
    )


def collection_group(name: str, summary: str, description: str) -> Group:
    """Return the CLI group of a collection: its products with the registry's texts."""

    def products() -> list[tuple[str, str]]:
        return shared.product_summaries(
            collection_products(name), collection_product_choices
        )

    return Group(name, summary, description, products=products)


def _fragment(key: str, given: bool) -> str:
    """Return the message of a part of the country text, or nothing."""
    return message(key) if given else ""


def collection_commands(
    group: str,
    *,
    summary: str,
    description: str,
    area_result: str,
    examples: Sequence[Example],
    rules: tuple[str, ...] = (),
    teryt: str | None = None,
    ku: str | None = None,
    sheet: bool = True,
    sheet_help: str = SHEET_AREA_HELP,
    sheet_systems: tuple[str, ...] = PL_SHEETS,
    whole_country: str | None = None,
    check: str | None = None,
    workers: str | None = WORKERS_HELP,
    content: Content | None = None,
    constraints: Sequence[Constraint] = (),
) -> tuple[Command, Command]:
    """``<group> download`` and ``<group> list-sources``.

    ``summary``, ``description``, ``area_result``, ``teryt``, ``ku``,
    ``sheet_help``, ``whole_country``, ``check`` and ``workers`` are the catalog
    messages of the texts, and ``rules`` the tuple of the rules of the command.

    ``area_result``: what an area gives (help of the area flags); ``examples``:
    the examples (``epilog`` of ``download --help``); ``teryt``: the group has
    ``--teryt`` with this help; ``ku``: the group has ``--ku`` (CZ cadastral
    area); ``sheet``: the group has ``--sheet`` (``False``: no PL sheet area);
    ``sheet_help`` and ``sheet_systems`` describe the sheet codes of a group with
    CZ map sheets; ``whole_country``: the group has ``--whole-country`` with this
    help; ``check``: the source signals in ``--check``; ``workers``: the
    help of ``--workers`` (``None`` for a group whose request is one file; no
    flag); ``content``: the content parameters of the group, from its products;
    ``constraints``: the rules besides the area choice.
    """

    def products() -> tuple[str, ...]:
        return collection_products(group)

    def country_description() -> str:
        countries = (*collection_countries(products()), "auto")
        return message(
            "catalog.collection_country_description",
            choices=country_choices(countries),
            whole=_fragment(
                "catalog.collection_country_whole", whole_country is not None
            ),
            teryt=_fragment("catalog.collection_country_teryt", teryt is not None),
            ku=_fragment("catalog.collection_country_ku", ku is not None),
            sheet=_fragment("catalog.collection_country_sheet", sheet),
        )

    def area_text(text: str) -> str:
        return message(
            "catalog.collection_area_description", text=text, result=area_result
        )

    params: list[Param] = [
        shared.product(products, collection_product_choices),
        shared.country(
            lambda: (*collection_countries(products()), "auto"), country_description
        ),
    ]
    if teryt is not None:
        params.append(
            Param(
                "teryt",
                "str",
                teryt,
                metavar=message("catalog.metavar_code"),
                task=True,
                section=SELECTION_TITLE,
            )
        )
    if ku is not None:
        params.append(
            Param(
                "ku",
                "str",
                ku,
                metavar=message("catalog.metavar_code"),
                task=True,
                section=SELECTION_TITLE,
            )
        )
    params += shared.area(
        sheet=area_text(sheet_help) if sheet else None,
        accepts=sheet_systems,
        bbox=area_text(BBOX_HELP),
        geometry=area_text(GEOMETRY_HELP),
    )
    if whole_country is not None:
        params.append(
            Param(
                "whole_country",
                "flag",
                whole_country,
                default=False,
                task=True,
                section=SELECTION_TITLE,
            )
        )
    if content is not None:
        params += [replace(p, section=PRODUCT_TITLE) for p in content(products)]
    params += shared.target(lambda: store_files([group]))
    params += shared.update_params(
        check=check or CHECK_HELP,
        upgrade=message("catalog.collection_upgrade_description"),
        force=message("catalog.collection_force_description"),
        plan=message("catalog.collection_plan_description", common=shared.PLAN_HELP),
    )
    if workers is not None:
        params.append(shared.workers(workers, 1))
    params += [shared.QUIET, replace(shared.JSON, section=OUTPUT_TITLE)]

    choices = ["sheet"] if sheet else []
    choices += ["bbox", "geometry"]
    choices += ["teryt"] if teryt is not None else []
    choices += ["ku"] if ku is not None else []
    choices += ["whole_country"] if whole_country is not None else []
    declared = [
        Constraint(
            "one_of",
            tuple(choices),
            message(
                "catalog.rule_collection_one_of",
                flags=", ".join(f"--{name.replace('_', '-')}" for name in choices),
            ),
        )
    ]
    if whole_country is not None:
        # the countries of the group's products: hydro has CZ only
        declared.append(
            Constraint(
                "requires",
                ("country",),
                message(
                    "catalog.rule_collection_whole_country",
                    countries=[
                        f"--country {code}" for code in collection_countries(products())
                    ],
                ),
                "whole_country",
            )
        )
    download = Command(
        f"{group} download",
        summary,
        "data",
        "download_collection",
        "kartograf-download/1",
        tuple(params),
        description=message(
            "catalog.with_plain_note", text=description, note=shared.PLAIN_NOTE
        ),
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_collection",
        check_result_schema="kartograf-plan/1",
        constraints=(*declared, *constraints, *shared.target_constraints()),
        examples=tuple(examples),
        rules=rules,
        errors=DATA_ERRORS,
        family="data",
    )
    return download, shared.list_sources_command(group, products)
