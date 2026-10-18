"""
Arguments shared by the command groups of the CLI (ADR-039).

Flags that mean the same in every group are defined once here: the area
choice (``--sheet``/``--bbox``/``--bbox-crs``/``--geometry``/``--layer``), the
update modes, ``--quiet``, the ``--bbox`` text parser and the per-country
value parser (``pl=..,cz=..``). A group adds them to its own parser (or to an
argument group of it) and keeps the flags only it understands in its module
(``kartograf/cli/groups/``).
"""

import argparse

from kartograf.core.bbox import BBox
from kartograf.download.options import (
    BBOX_CRS_CHOICES,
    BBOX_EXPECTED,
    COUNTRY_KEYS,
    validate_request_bbox,
)
from kartograf.exceptions import ValidationError

# A parser or one of its argument groups (titled sections of --help).
Container = argparse.ArgumentParser | argparse._ArgumentGroup

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


def add_output(parser: Container, files: str) -> None:
    """``--output``/``-o``: the store directory of a data command; ``files``
    says where its files go (``store_files``: ``pliki w <KATALOG>/nmt/...``)."""
    parser.add_argument(
        "--output",
        "-o",
        metavar="KATALOG",
        default=None,
        help=f"Katalog magazynu (wymagany): {files} (wersje w versions/)",
    )


def examples(*commands: str) -> str:
    """``epilog`` of a command: ``Przyklady:`` and one command per line (kept
    unwrapped by the help formatter, ready to copy)."""
    return "Przyklady:\n" + "\n".join(f"  {command}" for command in commands)


def add_update_flags(
    parser: Container,
    *,
    check_help: str,
    upgrade_help: str,
    force_help: str,
    plan_help: str | None = None,
) -> None:
    """Update modes of a store command; omit ``--plan`` when not supported."""
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-updates", action="store_true", help=check_help)
    modes.add_argument("--upgrade", action="store_true", help=upgrade_help)
    modes.add_argument("--force", action="store_true", help=force_help)
    if plan_help is not None:
        parser.add_argument("--plan", metavar="PLIK", default=None, help=plan_help)


def add_bbox_crs(parser: Container) -> None:
    """``--bbox-crs``: the CRS of the ``--bbox`` numbers."""
    parser.add_argument(
        "--bbox-crs",
        type=str.upper,
        choices=BBOX_CRS_CHOICES,
        default="EPSG:2180",
        help="Uklad wspolrzednych --bbox (domyslnie EPSG:2180)",
    )


def add_area_flags(
    parser: Container,
    *,
    sheet_help: str | None,
    bbox_help: str = BBOX_HELP,
    geometry_help: str = GEOMETRY_HELP,
) -> None:
    """One area choice of a request: ``--sheet``, ``--bbox`` (+ ``--bbox-crs``),
    ``--geometry`` (+ ``--layer``); exactly one is checked by the library.
    ``sheet_help=None``: no ``--sheet`` (a group whose sources take no sheet
    code as an area)."""
    if sheet_help is not None:
        parser.add_argument(
            "--sheet",
            metavar="GODLO",
            default=None,
            # argparse does not strip whitespace; a sheet code with padding would
            # reach the system registry and the file name (parser review
            # 2026-10-07, K5)
            type=str.strip,
            help=sheet_help,
        )
    parser.add_argument("--bbox", metavar="BBOX", help=bbox_help)
    add_bbox_crs(parser)
    parser.add_argument("--geometry", metavar="PLIK", help=geometry_help)
    parser.add_argument("--layer", metavar="NAZWA", help=LAYER_HELP)


def add_quiet(parser: Container) -> None:
    """``--quiet``/``-q``: no progress bar and status lines on stdout."""
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Bez paska postepu i linii statusu na stdout (Info:, Warning: "
        "i Error: na stderr zostaja)",
    )


def layer_codes(text: str) -> tuple[str, ...]:
    """``--layers SWRS,PTWP`` -> ``("SWRS", "PTWP")`` (also ``--direction n,e``);
    codes checked by the library."""
    return tuple(code.strip() for code in text.split(","))


def parse_per_country(raw: str | None, flag: str) -> str | dict[str, str] | None:
    """``5m`` (every country) or ``pl=1m,cz=2m`` (per country) as library value.

    Raises
    ------
    ValidationError
        An item without ``=``, a country other than PL/CZ, an empty value or
        a country given twice (the text of the library's per-country check).
    """
    if raw is None or "=" not in raw:
        return raw
    values: dict[str, str] = {}
    for item in raw.split(","):
        key, sep, value = item.partition("=")
        key = key.strip().lower()
        if not sep or key not in COUNTRY_KEYS or not value.strip() or key in values:
            raise ValidationError(
                f"{flag}: nieprawidlowa wartosc {raw!r} - podaj jedna wartosc dla "
                f"kazdego kraju zadania albo pary kraj=wartosc rozdzielone "
                f"przecinkami (kraje: pl, cz), np. {flag} pl=...,cz=..."
            )
        values[key] = value.strip()
    return values


def parse_bbox_arg(text: str, crs: str) -> BBox:
    """
    Parses the ``--bbox`` value (``"min_x,min_y,max_x,max_y"``) into a ``BBox``.

    One message for every input defect - callers do not catch the exception:
    ``ValidationError`` is a ``KartografError``, so ``main`` prints
    ``Error: ...`` to stderr and returns 2 (input error; the hint comes with the
    error, not on stdout).

    Parameters
    ----------
    text : str
        Argument value; whitespace around numbers is allowed
    crs : str
        CRS in which the coordinates were given

    Raises
    ------
    ValidationError
        ``Nieprawidlowy bbox: <reason>. Oczekiwano: ...`` for a number of values
        other than 4, a non-numeric value, NaN/inf or ``min > max``
        (``core.bbox.validate_bbox``; a point bbox is allowed).
    """
    parts = text.split(",")
    if len(parts) != 4:
        reason = f"oczekiwano 4 wartosci rozdzielonych przecinkami, podano {len(parts)}"
        raise ValidationError(f"Nieprawidlowy bbox: {reason}. {BBOX_EXPECTED}")
    values = []
    for part in parts:
        try:
            values.append(float(part.strip()))
        except ValueError:
            reason = f"{part.strip()!r} nie jest liczba"
            raise ValidationError(
                f"Nieprawidlowy bbox: {reason}. {BBOX_EXPECTED}"
            ) from None
    return validate_request_bbox(BBox(values[0], values[1], values[2], values[3], crs))
