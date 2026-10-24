"""
Parameters shared by the commands of the catalog (spec 8.2, 8.3 item 4).

A parameter that means the same in many commands is declared once here: the
area choice (``sheet``, ``bbox`` + ``bbox_crs``, ``geometry`` + ``layer``), the
product and country choice, the store directory, the update modes and the
display flags. A command includes it and may override ``description``,
``allowed``, ``required`` or ``section`` with ``dataclasses.replace``; the
helpers below do that for the usual cases. The texts and the section titles are
the ones of the ``--help`` of the CLI (the sheet, bbox and layer descriptions
are common to every area command).
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import get_args

from kartograf.catalog.spec import Command, Param, Text, Values, resolve
from kartograf.download.fetch import UpdateMode
from kartograf.download.options import BBOX_CRS_CHOICES

BBOX_HELP = (
    "Prostokat obszaru: min_x,min_y,max_x,max_y (domyslny uklad: EPSG:2180; "
    "wspolrzedne S-JTSK: --bbox-crs EPSG:5514, np. --bbox -447000,-1100000,"
    "-437000,-1090000)"
)
# Area groups (land cover, soil): a sheet code is an area like --bbox (ADR-039).
SHEET_AREA_HELP = (
    "Obszar = zasieg arkusza o tym godle (np. N-34-130-D), jak --bbox z jego "
    "naroznikami"
)
GEOMETRY_HELP = "Plik geometrii (SHP albo GPKG); obszar = obwiednia obiektow"
LAYER_HELP = (
    "Warstwa GPKG (domyslnie pierwsza; przy wielu warstwach Info z lista pozostalych)"
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
    "Produkt (wymagany)",
    required=True,
    task=True,
    section=SELECTION_TITLE,
)
COUNTRY = Param(
    "country",
    "str",
    "Kraj zrodla danych",
    task=True,
    normalize="lower",
    section=SELECTION_TITLE,
)
SHEET = Param(
    "sheet",
    "str",
    "Godlo arkusza",
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
    metavar="BBOX",
    task=True,
    section=SELECTION_TITLE,
)
BBOX_CRS = Param(
    "bbox_crs",
    "bbox_crs",
    "Uklad wspolrzednych --bbox (domyslnie EPSG:2180)",
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
    metavar="PLIK",
    task=True,
    section=SELECTION_TITLE,
)
LAYER = Param(
    "layer",
    "str",
    LAYER_HELP,
    metavar="NAZWA",
    task=True,
    section=SELECTION_TITLE,
)
OUTPUT_DIR = Param(
    "output_dir",
    "path",
    "Katalog magazynu (wymagany)",
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
    "Liczba rownoleglych pobran",
    short="-w",
    metavar="N",
    section=OUTPUT_TITLE,
)
QUIET = Param(
    "quiet",
    "flag",
    "Bez paska postepu i linii statusu na stdout (Info:, Warning: i Error: na "
    "stderr zostaja)",
    argument=None,
    short="-q",
    section=OUTPUT_TITLE,
)
JSON = Param(
    "json",
    "flag",
    "Wypisz wynik jako jeden dokument JSON na stdout (pole schema nazywa jego "
    "typ), bez paska postepu i tekstu; blad jako kartograf-error/1",
    argument=None,
)
CHECK_UPDATES = Param(
    "check_updates",
    "flag",
    "Sprawdz aktualnosc lokalnych wersji bez pobierania",
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
UPGRADE = Param(
    "upgrade",
    "flag",
    "Pobierz nowsza tresc",
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
FORCE = Param(
    "force",
    "flag",
    "Pobierz ponownie",
    argument=None,
    exclusive="update",
    section=OUTPUT_TITLE,
)
UPDATE = Param(
    "update",
    "str",
    "Tryb aktualizacji (pominiety: lokalne wersje, brakujace sa pobierane)",
    flag=None,
    # ``check`` is the ``check_*`` twin of a command, not a mode of its function
    allowed=lambda: [mode for mode in get_args(UpdateMode) if mode != "check"],
    section=OUTPUT_TITLE,
)
PLAN = Param(
    "plan",
    "plan",
    "Plan aktualizacji",
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
    ``choices_text(products)`` names them in the description (``Produkt (wymagany): nmt
    (...), nmpt (...)``).
    """

    def description() -> str:
        return f"Produkt (wymagany): {choices_text(tuple(resolve(products)))}"

    return replace(
        PRODUCT,
        description=description,
        allowed=lambda: tuple(resolve(products)),
        choices=True,
        section=section,
    )


def country(
    countries: Values, description: Text, *, section: str = SELECTION_TITLE
) -> Param:
    """``--country`` of a command.

    ``countries`` are the allowed values and the parser choices.
    """
    return replace(
        COUNTRY,
        description=description,
        allowed=lambda: tuple(resolve(countries)),
        choices=True,
        section=section,
    )


def area(
    *,
    sheet: Text | None,
    accepts: tuple[str, ...] | None = None,
    bbox: Text = BBOX_HELP,
    geometry: Text = GEOMETRY_HELP,
    section: str = SELECTION_TITLE,
) -> tuple[Param, ...]:
    """One area choice of a request.

    ``sheet`` (when ``sheet`` is the text of its description; ``accepts`` are the sheet
    systems it takes), ``bbox`` with ``bbox_crs``, ``geometry`` with ``layer``. Exactly
    one is checked by the library (a ``one_of`` constraint of the command).
    """
    params: list[Param] = []
    if sheet is not None:
        if accepts is None:
            raise ValueError("area: a sheet parameter declares the systems it accepts")
        params.append(replace(SHEET, description=sheet, accepts=accepts))
    params += [
        replace(BBOX, description=bbox),
        BBOX_CRS,
        replace(GEOMETRY, description=geometry),
        LAYER,
    ]
    return tuple(replace(param, section=section) for param in params)


def output_dir(files: Text) -> Param:
    """``--output``/``-o``.

    The store directory of a data command; ``files`` says where its files go (``pliki w
    <KATALOG>/nmt/...``).
    """

    def description() -> str:
        return f"Katalog magazynu (wymagany): {resolve(files)} (wersje w versions/)"

    return replace(OUTPUT_DIR, description=description)


def workers(description: Text, default: int | None) -> Param:
    """``--workers``/``-w``.

    Parallel transfers; ``default`` is the number the library function uses (and the
    flag).
    """
    return replace(WORKERS, description=description, default=default)


def update_params(
    *, check: Text, upgrade: Text, force: Text, plan: Text | None = None
) -> tuple[Param, ...]:
    """Update modes of a store command.

    The exclusive flags ``--check-updates``, ``--upgrade`` and ``--force``, the API
    argument ``update`` and, when ``plan`` is the text of its description, ``--plan``.
    """
    params = [
        replace(CHECK_UPDATES, description=check),
        replace(UPGRADE, description=upgrade),
        replace(FORCE, description=force),
        UPDATE,
    ]
    if plan is not None:
        params.append(replace(PLAN, description=plan))
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


def list_sources_command(group: str, products: Values) -> Command:
    """``<group> list-sources``.

    The registered sources of the group's ``products`` (the registry, no network). The
    API function ``list_sources`` serves every group, so ``group`` is an API-only
    parameter with the one value of this command and ``product`` narrows the list.
    """
    return Command(
        f"{group} list-sources",
        "Wypisz zrodla danych grupy (rejestr zrodel, bez sieci)",
        "query",
        "list_sources",
        "kartograf-sources/1",
        (
            Param(
                "group",
                "str",
                f"Grupa komend (tu: {group}); list_sources obsluguje wszystkie grupy",
                flag=None,
                required=True,
                allowed=(group,),
            ),
            Param(
                "product",
                "str",
                "Tylko zrodla tego produktu (domyslnie wszystkie produkty grupy)",
                flag=None,
                allowed=lambda: tuple(resolve(products)),
            ),
            JSON,
        ),
        description=f"Wypisz zrodla danych grupy {group} z rejestru zrodel "
        "(bez sieci): WYBOR = wymagane flagi wyboru zrodla w download (a|b - "
        "jedna z wartosci), KATALOG = katalog plikow pod --output, KLUCZ = "
        "pole dataset w sidecarze pliku",
        tool="list_sources",
    )
