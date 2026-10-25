"""
Parameters shared by the commands of the catalog (spec 8.2, 8.3 item 4).

A parameter that means the same in many commands is declared once here: the
area choice (``sheet``, ``bbox`` + ``bbox_crs``, ``geometry`` + ``layer``), the
product and country choice, the store directory, the update modes and the
display flags. A command includes it and may override ``description``,
``allowed``, ``required`` or ``section`` with ``dataclasses.replace``; the
helpers below do that for the usual cases. The texts and the section titles are
the ones of the ``--help`` of the CLI (the sheet, bbox and layer descriptions
are common to every area command). Every text exists in English (``description``)
and Polish (``description_pl``); where a helper takes a text of both languages it
takes a ``Pair``: ``(English, Polish)``.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import get_args

from kartograf.catalog.spec import Command, Example, Param, Text, Values, resolve
from kartograf.download.fetch import UpdateMode
from kartograf.download.options import BBOX_CRS_CHOICES

# A text of both languages: ``(English, Polish)``.
Pair = tuple[Text, Text]

BBOX_HELP = (
    "Area rectangle [min_x, min_y, max_x, max_y] in the CRS of bbox_crs, as numbers "
    "(metres, or degrees for EPSG:4326)."
)
BBOX_HELP_PL = (
    "Prostokat obszaru: min_x,min_y,max_x,max_y (domyslny uklad: EPSG:2180; "
    "wspolrzedne S-JTSK: --bbox-crs EPSG:5514, np. --bbox -447000,-1100000,"
    "-437000,-1090000)"
)
# Area groups (land cover, soil): a sheet code is an area like --bbox (ADR-039).
SHEET_AREA_HELP = (
    "Sheet code (for example N-34-130-D): the area is the extent of that sheet, "
    "as bbox with its corners."
)
SHEET_AREA_HELP_PL = (
    "Obszar = zasieg arkusza o tym godle (np. N-34-130-D), jak --bbox z jego "
    "naroznikami"
)
GEOMETRY_HELP = (
    "Vector file (SHP or GPKG) with the area: the extent of its features is the area."
)
GEOMETRY_HELP_PL = "Plik geometrii (SHP albo GPKG); obszar = obwiednia obiektow"
LAYER_HELP = "GPKG layer of geometry (default: the first one)."
LAYER_HELP_PL = (
    "Warstwa GPKG (domyslnie pierwsza; przy wielu warstwach Info z lista pozostalych)"
)
CHECK_HELP = (
    "Plan without effects: compare the local versions with the source and return the "
    "plan (kartograf-plan/1: current, newer, to download, or cannot be checked "
    "without downloading); nothing is fetched or written."
)
UPDATE_HELP = (
    "Update mode. Omitted: keep the local versions and fetch the missing ones. "
    "upgrade: fetch newer content when the source signals it. force: fetch every "
    "file again (the same content is unchanged, other content is a new version; "
    "nothing is overwritten). CLI: --upgrade, --force."
)
PLAN_HELP = (
    "Update plan (the result of a check) to run with update=upgrade; a position "
    "that changed since the plan stops the run. CLI: the file of --plan."
)
# Titles of the --help sections of every data command (UX-27).
SELECTION_TITLE = "Produkt i obszar"
PRODUCT_TITLE = "Parametry produktu"
OUTPUT_TITLE = "Wynik i aktualizacja"
# The sheet systems of the PL codes (``SheetParser`` reads both).
PL_SHEETS = ("pl1992", "pl2000")

PRODUCT = Param(
    "product",
    "str",
    "Product.",
    description_pl="Produkt (wymagany)",
    required=True,
    task=True,
    section=SELECTION_TITLE,
)
COUNTRY = Param(
    "country",
    "str",
    "Country of the source: pl, cz or auto (split by the bounding boxes of PL and CZ).",
    description_pl="Kraj zrodla danych",
    task=True,
    normalize="lower",
    section=SELECTION_TITLE,
)
SHEET = Param(
    "sheet",
    "str",
    "Sheet code.",
    description_pl="Godlo arkusza",
    metavar="GODLO",
    # argparse does not strip whitespace; a sheet code with padding would
    # reach the system registry and the file name (parser review 2026-10-07, K5)
    normalize="strip",
    task=True,
    section=SELECTION_TITLE,
)
BBOX = Param(
    "bbox",
    "bbox",
    BBOX_HELP,
    description_pl=BBOX_HELP_PL,
    metavar="BBOX",
    examples=([565000, 242000, 566000, 243000],),
    task=True,
    section=SELECTION_TITLE,
)
BBOX_CRS = Param(
    "bbox_crs",
    "bbox_crs",
    "CRS of bbox, required with it (the CLI defaults to EPSG:2180).",
    description_pl="Uklad wspolrzednych --bbox (domyslnie EPSG:2180)",
    allowed=lambda: BBOX_CRS_CHOICES,
    choices=True,
    normalize="upper",
    cli_default="EPSG:2180",
    task=True,
    section=SELECTION_TITLE,
)
GEOMETRY = Param(
    "geometry",
    "path",
    GEOMETRY_HELP,
    description_pl=GEOMETRY_HELP_PL,
    path_role="input",
    metavar="PLIK",
    task=True,
    section=SELECTION_TITLE,
)
LAYER = Param(
    "layer",
    "str",
    LAYER_HELP,
    description_pl=LAYER_HELP_PL,
    metavar="NAZWA",
    task=True,
    section=SELECTION_TITLE,
)
OUTPUT_DIR = Param(
    "output_dir",
    "path",
    "Store directory (required): versions are written below it, one directory per "
    "product, never over existing ones.",
    description_pl="Katalog magazynu (wymagany)",
    path_role="root",
    flag="--output",
    short="-o",
    dest="output",
    metavar="KATALOG",
    required=True,
    section=OUTPUT_TITLE,
)
WORKERS = Param(
    "workers",
    "int",
    "Parallel transfers.",
    description_pl="Liczba rownoleglych pobran",
    minimum=1,
    short="-w",
    metavar="N",
    section=OUTPUT_TITLE,
)
QUIET = Param(
    "quiet",
    "flag",
    description_pl="Bez paska postepu i linii statusu na stdout (Info:, Warning: i "
    "Error: na stderr zostaja)",
    argument=None,
    short="-q",
    section=OUTPUT_TITLE,
)
JSON = Param(
    "json",
    "flag",
    description_pl="Wypisz wynik jako jeden dokument JSON na stdout (pole schema "
    "nazywa jego typ), bez paska postepu i tekstu; blad jako kartograf-error/1",
    argument=None,
)
LANG = Param(
    "lang",
    "str",
    "Language of the text for people: pl or en (default: KARTOGRAF_LANG, then "
    "nogat.toml, then pl). The --json document, the error line and every notice "
    "of the library stay English.",
    description_pl="Jezyk tekstu dla czlowieka: pl albo en (domyslnie KARTOGRAF_LANG, "
    "potem nogat.toml, potem pl); dokument --json, linia bledu i komunikaty "
    "biblioteki zostaja po angielsku",
    argument=None,
    allowed=("pl", "en"),
    choices=True,
    normalize="lower",
    metavar="JEZYK",
)
CHECK_UPDATES = Param(
    "check_updates",
    "flag",
    CHECK_HELP,
    description_pl="Sprawdz aktualnosc lokalnych wersji bez pobierania",
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
UPGRADE = Param(
    "upgrade",
    "flag",
    description_pl="Pobierz nowsza tresc",
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
FORCE = Param(
    "force",
    "flag",
    description_pl="Pobierz ponownie",
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
UPDATE = Param(
    "update",
    "str",
    UPDATE_HELP,
    description_pl="Tryb aktualizacji (pominiety: lokalne wersje, brakujace sa "
    "pobierane)",
    flag=None,
    # ``check`` is the ``check_*`` twin of a command, not a mode of its function
    allowed=lambda: [mode for mode in get_args(UpdateMode) if mode != "check"],
    section=OUTPUT_TITLE,
)
PLAN = Param(
    "plan",
    "plan",
    PLAN_HELP,
    description_pl="Plan aktualizacji",
    metavar="PLIK",
    section=OUTPUT_TITLE,
)


def product(
    products: Values,
    choices_text: Callable[[Sequence[str]], str],
    *,
    section: str = SELECTION_TITLE,
) -> Param:
    """``--product`` of a group.

    ``products`` are the allowed values and the parser choices,
    ``choices_text(products)`` names them in the Polish description (``Produkt
    (wymagany): nmt (...), nmpt (...)``); the meanings of the English ones are in
    ``kartograf.catalog.meanings``.
    """

    def description_pl() -> str:
        return f"Produkt (wymagany): {choices_text(tuple(resolve(products)))}"

    return replace(
        PRODUCT,
        description_pl=description_pl,
        allowed=lambda: tuple(resolve(products)),
        choices=True,
        section=section,
    )


def country(
    countries: Values, description: Pair, *, section: str = SELECTION_TITLE
) -> Param:
    """``--country`` of a command.

    ``countries`` are the allowed values and the parser choices; ``description`` is the
    text of the command in English and Polish.
    """
    english, polish = description
    return replace(
        COUNTRY,
        description=english,
        description_pl=polish,
        allowed=lambda: tuple(resolve(countries)),
        choices=True,
        section=section,
    )


def area(
    *,
    sheet: Pair | None,
    accepts: tuple[str, ...] | None = None,
    bbox: Pair = (BBOX_HELP, BBOX_HELP_PL),
    geometry: Pair = (GEOMETRY_HELP, GEOMETRY_HELP_PL),
    section: str = SELECTION_TITLE,
) -> tuple[Param, ...]:
    """One area choice of a request.

    ``sheet`` (when ``sheet`` is the text of its description in English and Polish;
    ``accepts`` are the sheet systems it takes), ``bbox`` with ``bbox_crs``,
    ``geometry`` with ``layer``. Exactly one is checked by the library (a ``one_of``
    constraint of the command).
    """
    params: list[Param] = []
    if sheet is not None:
        if accepts is None:
            raise ValueError("area: a sheet parameter declares the systems it accepts")
        params.append(
            replace(
                SHEET, description=sheet[0], description_pl=sheet[1], accepts=accepts
            )
        )
    params += [
        replace(BBOX, description=bbox[0], description_pl=bbox[1]),
        BBOX_CRS,
        replace(GEOMETRY, description=geometry[0], description_pl=geometry[1]),
        LAYER,
    ]
    return tuple(replace(param, section=section) for param in params)


def output_dir(files: Text) -> Param:
    """``--output``/``-o``.

    The store directory of a data command; ``files`` says where its files go (``pliki w
    <KATALOG>/nmt/...``, Polish).
    """

    def description_pl() -> str:
        return f"Katalog magazynu (wymagany): {resolve(files)} (wersje w versions/)"

    return replace(OUTPUT_DIR, description_pl=description_pl)


def workers(description: Pair, default: int | None) -> Param:
    """``--workers``/``-w``.

    Parallel transfers (``description``: English and Polish); ``default`` is the number
    the library function uses (and the flag).
    """
    return replace(
        WORKERS,
        description=description[0],
        description_pl=description[1],
        default=default,
    )


def update_params(
    *,
    check: Pair,
    upgrade: Text,
    force: Text,
    plan: Text | None = None,
) -> tuple[Param, ...]:
    """Update modes of a store command.

    The exclusive flags ``--check-updates``, ``--upgrade`` and ``--force``, the API
    argument ``update`` and, when ``plan`` is the Polish text of its description,
    ``--plan``. ``check`` is ``(English, Polish)``: the English sentence says what
    the source signals for this command and is added to the common text of the
    option; ``upgrade`` and ``force`` are Polish, the flags only spell ``update``.
    """
    params = [
        replace(
            CHECK_UPDATES,
            description=f"{CHECK_HELP} {check[0]}".strip(),
            description_pl=check[1],
        ),
        replace(UPGRADE, description_pl=upgrade),
        replace(FORCE, description_pl=force),
        UPDATE,
    ]
    if plan is not None:
        params.append(replace(PLAN, description_pl=plan))
    return tuple(params)


def product_summaries(
    products: Sequence[str], choices_text: Callable[[Sequence[str]], str]
) -> list[tuple[str, str]]:
    """Return the ``(product, summary)`` pairs of a group.

    The text in the parentheses of ``choices_text`` of one product (``nmt (Numeryczny
    Model Terenu; PL i CZ)`` gives ``Numeryczny Model Terenu; PL i CZ``).
    """
    pairs = []
    for name in products:
        text = choices_text([name])
        prefix = f"{name} ("
        if not (text.startswith(prefix) and text.endswith(")")):
            raise ValueError(f"{text!r} is not '{name} (<summary>)'")
        pairs.append((name, text[len(prefix) : -1]))
    return pairs


# What a command that only reads can raise: a wrong argument and, in the MCP server, a
# path outside the allowed directories (ERR-1).
READ_ERRORS = ("validation_error", "io_error", "forbidden")
# What a command that downloads can raise.
DATA_ERRORS = (
    "validation_error",
    "source_unavailable",
    "no_data",
    "unsupported",
    "calculation_error",
    "store_unavailable",
    "io_error",
    "forbidden",
)


def list_sources_command(group: str, products: Values) -> Command:
    """``<group> list-sources``.

    The registered sources of the group's ``products`` (the registry, no network). The
    API function ``list_sources`` serves every group, so ``group`` is a fixed argument
    with the one value of this command and ``product`` narrows the list.
    """
    return Command(
        f"{group} list-sources",
        f"List the registered data sources of the {group} group (offline)",
        "query",
        "list_sources",
        "kartograf-sources/1",
        (
            Param(
                "group",
                "str",
                description_pl=f"Grupa komend (tu: {group}); list_sources obsluguje "
                "wszystkie grupy",
                flag=None,
                required=True,
                fixed=group,
            ),
            Param(
                "product",
                "str",
                "Only the sources of this product (default: every product of the "
                "group).",
                description_pl="Tylko zrodla tego produktu (domyslnie wszystkie "
                "produkty grupy)",
                metavar="PRODUKT",
                allowed=lambda: tuple(resolve(products)),
                choices=True,
            ),
            JSON,
        ),
        description=f"For each source of the {group} group: the options that select it "
        f"in `{group} download`, its directory in the store and the `dataset` key of "
        "its sidecar. Use it to see which variants exist; to see what exists for an "
        "area use `elevation availability`.",
        summary_pl="Wypisz zrodla danych grupy (rejestr zrodel, bez sieci)",
        description_pl=f"Wypisz zrodla danych grupy {group} z rejestru zrodel "
        "(bez sieci): WYBOR = wymagane flagi wyboru zrodla w download (a|b - "
        "jedna z wartosci), KATALOG = katalog plikow pod --output, KLUCZ = "
        "pole dataset w sidecarze pliku",
        rules=("Offline: nothing is fetched.",),
        rules_pl=("Bez sieci: nic nie jest pobierane.",),
        errors=("validation_error",),
        family="discovery",
        cardinality="bounded",
        examples=(
            Example(
                {},
                title=f"The sources of the {group} group",
                title_pl=f"Zrodla grupy {group}",
            ),
        ),
    )
