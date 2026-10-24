"""
``download`` and ``list-sources`` of a collection group (``boundaries``,
``cadastre``, ``models3d``, ``hydro``, ``names``, ``maps``, ``geodesy``;
ADR-042 D9).

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

WORKERS_HELP = (
    "Liczba rownoleglych pobran plikow, gdy zadanie ma ich kilka (paczki "
    "jednostek obszaru, arkusze, kraje --country auto; domyslnie 1)"
)

# Provider of the products of a group (the registry decides, late).
Products = Callable[[], tuple[str, ...]]
# What a group adds to the common flags: its content parameters, which may
# describe themselves from the group's products.
Content = Callable[[Products], Sequence[Param]]


def choice_values(products: Sequence[str], key: str) -> list[str]:
    """The values of the option ``key`` over the products and countries of a group
    (registry order, each once)."""
    found = (
        value
        for product in products
        for values in collection_choice_values(product, key).values()
        for value in values
    )
    return list(dict.fromkeys(found))


def choice_text(products: Sequence[str], key: str) -> str:
    """``admin PL: a, b; admin CZ: c``: the values of the option ``key`` per
    product and country (the texts of ``--format``, ``--network``, ...)."""
    return "; ".join(
        f"{product} {country}: {', '.join(values)}"
        for product in products
        for country, values in collection_choice_values(product, key).items()
    )


def collection_group(name: str, summary: str, description: str) -> Group:
    """The CLI group of a collection: its products with the registry's texts."""

    def products() -> list[tuple[str, str]]:
        return shared.product_summaries(
            collection_products(name), collection_product_choices
        )

    return Group(name, summary, description, products=products)


def collection_commands(
    group: str,
    *,
    summary: str,
    description: str,
    area_result: str,
    examples: Sequence[Example],
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

    ``area_result``: what an area gives (help of the area flags); ``examples``:
    the examples (``epilog`` of ``download --help``); ``teryt``: the group has
    ``--teryt`` with this help; ``ku``: the group has ``--ku`` (CZ cadastral
    area); ``sheet``: the group has ``--sheet`` (``False``: no PL sheet area);
    ``sheet_help`` and ``sheet_systems`` describe the sheet codes of a group with
    CZ map sheets; ``whole_country``: the group has ``--whole-country`` with this
    help; ``check``: the source signals in ``--check-updates``; ``workers``: the
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

    params: list[Param] = [
        shared.product(products, collection_product_choices),
        shared.country(
            lambda: (*collection_countries(products()), "auto"), country_help
        ),
    ]
    if teryt is not None:
        params.append(
            Param(
                "teryt", "str", teryt, metavar="KOD", task=True, section=SELECTION_TITLE
            )
        )
    if ku is not None:
        params.append(
            Param("ku", "str", ku, metavar="KOD", task=True, section=SELECTION_TITLE)
        )
    params += shared.area(
        sheet=f"{sheet_help}; {area_result}" if sheet else None,
        accepts=sheet_systems,
        bbox=f"{BBOX_HELP}; {area_result}",
        geometry=f"{GEOMETRY_HELP}; {area_result}",
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
    params.append(shared.output_dir(lambda: store_files([group])))
    params += shared.update_params(
        check=check
        or (
            "Porownaj lokalne wersje ze zrodlem bez pobierania: plik "
            "z sygnalem zrodla (naglowki HTTP plikow krajowych CUZK) - porownanie "
            "bez pobrania; paczki GUGiK i obiekty obszaru nie maja taniego sygnalu "
            "(nie da sie sprawdzic bez pobrania), brakujace pliki = do pobrania"
        ),
        upgrade="Pobierz nowsza tresc, gdy sygnal zrodla ja wskazuje; pliki "
        "bez taniego sygnalu zostaja lokalne (pobranie: --force); z --plan "
        "wykonaj zapisany plan",
        force="Pobierz ponownie kazdy plik zadania; ta sama tresc = bez "
        "zmian, inna = nowa wersja; nic nie jest nadpisywane",
        plan="Z --check-updates: zapisz plan aktualizacji (kartograf-plan/1); "
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
    rules = [
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
        rules.append(
            Constraint(
                "requires",
                ("country",),
                f"--whole-country wymaga {countries}",
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
        description=description,
        effects=("network", "store_write"),
        project_task=True,
        check_function="check_collection",
        check_result_schema="kartograf-plan/1",
        tool=f"{group}_download",
        constraints=(*rules, *constraints),
        examples=tuple(examples),
    )
    return download, shared.list_sources_command(group, products)
