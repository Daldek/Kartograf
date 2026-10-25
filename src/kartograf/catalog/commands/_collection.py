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
    BBOX_HELP_PL,
    DATA_ERRORS,
    GEOMETRY_HELP,
    GEOMETRY_HELP_PL,
    OUTPUT_TITLE,
    PL_SHEETS,
    PRODUCT_TITLE,
    SELECTION_TITLE,
    SHEET_AREA_HELP,
    SHEET_AREA_HELP_PL,
    Pair,
)
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.download.collections import (
    collection_choice_values,
    collection_countries,
    collection_product_choices,
    collection_products,
)
from kartograf.download.options import country_choices, store_files

WORKERS_HELP: Pair = (
    "Parallel file transfers when the task has several files (unit packages, sheets, "
    "the countries of auto); default 1.",
    "Liczba rownoleglych pobran plikow, gdy zadanie ma ich kilka (paczki "
    "jednostek obszaru, arkusze, kraje --country auto; domyslnie 1)",
)
CHECK_HELP: Pair = (
    "Cheap signal: the HTTP headers of the national CUZK files; GUGiK packages and "
    "area objects have none (reported as cannot be checked without downloading).",
    "Porownaj lokalne wersje ze zrodlem bez pobierania: plik "
    "z sygnalem zrodla (naglowki HTTP plikow krajowych CUZK) - porownanie "
    "bez pobrania; paczki GUGiK i obiekty obszaru nie maja taniego sygnalu "
    "(nie da sie sprawdzic bez pobrania), brakujace pliki = do pobrania",
)

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


def collection_group(name: str, summary: Pair, description: Pair) -> Group:
    """Return the CLI group of a collection: its products with the registry's texts.

    ``summary`` and ``description`` are ``(English, Polish)``.
    """

    def products() -> list[tuple[str, str]]:
        return shared.product_summaries(
            collection_products(name), collection_product_choices
        )

    return Group(
        name,
        str(summary[0]),
        str(description[0]),
        products=products,
        summary_pl=str(summary[1]),
        description_pl=str(description[1]),
    )


def collection_commands(
    group: str,
    *,
    summary: Pair,
    description: Pair,
    area_result: Pair,
    examples: Sequence[Example],
    rules: tuple[tuple[str, ...], tuple[str, ...]] = ((), ()),
    teryt: Pair | None = None,
    ku: Pair | None = None,
    sheet: bool = True,
    sheet_help: Pair = (SHEET_AREA_HELP, SHEET_AREA_HELP_PL),
    sheet_systems: tuple[str, ...] = PL_SHEETS,
    whole_country: Pair | None = None,
    check: Pair | None = None,
    workers: Pair | None = WORKERS_HELP,
    content: Content | None = None,
    constraints: Sequence[Constraint] = (),
) -> tuple[Command, Command]:
    """``<group> download`` and ``<group> list-sources``.

    ``summary``, ``description``, ``area_result``, ``teryt``, ``ku``,
    ``sheet_help``, ``whole_country``, ``check`` and ``workers`` are texts of both
    languages, ``(English, Polish)``, and ``rules`` is the tuple of the English and
    the tuple of the Polish rules of the command.

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

    def country_help() -> str:
        countries = (*collection_countries(products()), "auto")
        units = [
            text
            for text, given in (
                ("Z --teryt tylko pl", teryt is not None),
                ("Z --ku tylko cz", ku is not None),
                ("Z --sheet kraj wynika z godla", sheet),
            )
            if given
        ]
        return (
            "Kraj zrodla - wymagany z --bbox/--geometry"
            + (" i --whole-country (bez auto)" if whole_country else "")
            + f": {country_choices(countries)}"
            + "".join(f". {text}" for text in units)
        )

    country_english = (
        "Country of the source; required with bbox or geometry"
        + (" and whole_country (auto is not allowed with it)" if whole_country else "")
        + ". auto splits the area between PL and CZ."
        + (" teryt implies pl." if teryt is not None else "")
        + (" ku implies cz." if ku is not None else "")
        + (" A sheet code implies its country." if sheet else "")
    )

    params: list[Param] = [
        shared.product(products, collection_product_choices),
        shared.country(
            lambda: (*collection_countries(products()), "auto"),
            (country_english, country_help),
        ),
    ]
    if teryt is not None:
        params.append(
            Param(
                "teryt",
                "str",
                teryt[0],
                description_pl=teryt[1],
                metavar="KOD",
                task=True,
                section=SELECTION_TITLE,
            )
        )
    if ku is not None:
        params.append(
            Param(
                "ku",
                "str",
                ku[0],
                description_pl=ku[1],
                metavar="KOD",
                task=True,
                section=SELECTION_TITLE,
            )
        )
    params += shared.area(
        sheet=(
            (f"{sheet_help[0]} {area_result[0]}", f"{sheet_help[1]}; {area_result[1]}")
            if sheet
            else None
        ),
        accepts=sheet_systems,
        bbox=(f"{BBOX_HELP} {area_result[0]}", f"{BBOX_HELP_PL}; {area_result[1]}"),
        geometry=(
            f"{GEOMETRY_HELP} {area_result[0]}",
            f"{GEOMETRY_HELP_PL}; {area_result[1]}",
        ),
    )
    if whole_country is not None:
        params.append(
            Param(
                "whole_country",
                "flag",
                whole_country[0],
                description_pl=whole_country[1],
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
        upgrade="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje; pliki "
        "bez taniego sygnalu zostaja lokalne (pobranie: --force); z --plan "
        "wykonaj zapisany plan",
        force="Pobierz ponownie kazdy plik zadania; ta sama tresc = bez "
        "zmian, inna = nowa wersja; nic nie jest nadpisywane",
        plan="Z --check: zapisz plan aktualizacji (kartograf-plan/1); "
        "z --upgrade: wykonaj plan (pozycje zmienione od planu = blad)",
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
            "Podaj dokladnie jeden wybor: "
            + ", ".join(f"--{name.replace('_', '-')}" for name in choices),
        )
    ]
    if whole_country is not None:
        # the countries of the group's products: hydro has CZ only
        countries = " albo ".join(
            f"--country {code}" for code in collection_countries(products())
        )
        declared.append(
            Constraint(
                "requires",
                ("country",),
                f"--whole-country wymaga {countries}",
                "whole_country",
            )
        )
    download = Command(
        f"{group} download",
        str(summary[0]),
        "data",
        "download_collection",
        "kartograf-download/1",
        tuple(params),
        description=f"{description[0]} {shared.PLAIN_NOTE}",
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_collection",
        check_result_schema="kartograf-plan/1",
        constraints=(*declared, *constraints, *shared.target_constraints()),
        examples=tuple(examples),
        summary_pl=str(summary[1]),
        description_pl=f"{description[1]} {shared.PLAIN_NOTE_PL}",
        rules=rules[0],
        rules_pl=rules[1],
        errors=DATA_ERRORS,
        family="data",
    )
    return download, shared.list_sources_command(group, products)
