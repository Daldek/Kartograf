"""
Arguments shared by the command groups of the CLI (ADR-039).

Flags that mean the same in every group are defined once here: the area
choice (``--sheet``/``--bbox``/``--bbox-crs``/``--geometry``/``--layer``), the
update modes, ``--quiet`` and the ``--bbox`` text parser. A group adds them
to its own parser (or to an argument group of it) and keeps the flags only
it understands in its module (``kartograf/cli/groups/``).
"""

import argparse

from kartograf.core.bbox import BBox
from kartograf.download.options import (
    BBOX_CRS_CHOICES,
    BBOX_EXPECTED,
    validate_request_bbox,
)
from kartograf.exceptions import ValidationError

# A parser or one of its argument groups (titled sections of --help).
Container = argparse.ArgumentParser | argparse._ArgumentGroup

BBOX_HELP = "Prostokat obszaru: min_x,min_y,max_x,max_y (domyslny uklad: EPSG:2180)"
# Area groups (land cover, soil): a sheet code is an area like --bbox (ADR-039).
SHEET_AREA_HELP = (
    "Obszar = zasieg arkusza o tym godle (np. N-34-130-D), jak --bbox z jego "
    "naroznikami"
)
GEOMETRY_HELP = "Plik geometrii (SHP albo GPKG); obszar = obwiednia obiektow"
LAYER_HELP = (
    "Warstwa GPKG (domyslnie pierwsza; przy wielu warstwach Info z lista pozostalych)"
)
OUTPUT_TITLE = "Wynik i aktualizacja"


def add_update_flags(
    parser: Container,
    *,
    check_help: str,
    upgrade_help: str,
    force_help: str,
    plan_help: str,
) -> None:
    """Update modes of a store command (spec 4.2, 4.4): ``--check-updates``,
    ``--upgrade``, ``--force`` (mutually exclusive) and ``--plan PLIK``
    (with a mode only — checked in ``commands._dispatch``)."""
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check-updates", action="store_true", help=check_help)
    modes.add_argument("--upgrade", action="store_true", help=upgrade_help)
    modes.add_argument("--force", action="store_true", help=force_help)
    parser.add_argument("--plan", metavar="PLIK", default=None, help=plan_help)


def add_bbox_crs(parser: Container) -> None:
    """``--bbox-crs``: the CRS of the ``--bbox`` numbers."""
    parser.add_argument(
        "--bbox-crs",
        choices=BBOX_CRS_CHOICES,
        default="EPSG:2180",
        help="Uklad wspolrzednych --bbox (domyslnie EPSG:2180)",
    )


def add_area_flags(
    parser: Container,
    *,
    sheet_help: str,
    bbox_help: str = BBOX_HELP,
    geometry_help: str = GEOMETRY_HELP,
) -> None:
    """One area choice of a request: ``--sheet``, ``--bbox`` (+ ``--bbox-crs``),
    ``--geometry`` (+ ``--layer``); exactly one is checked by the library."""
    parser.add_argument(
        "--sheet",
        metavar="GODLO",
        default=None,
        # argparse does not strip whitespace; a sheet code with padding would reach
        # the system registry and the file name (parser review 2026-10-07, K5)
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
    """``--layers SWRS,PTWP`` -> ``("SWRS", "PTWP")``; codes checked by the library."""
    return tuple(code.strip() for code in text.split(","))


def parse_bbox_arg(text: str, crs: str) -> BBox:
    """
    Parses the ``--bbox`` value (``"min_x,min_y,max_x,max_y"``) into a ``BBox``.

    One message for every input defect - callers do not catch the exception:
    ``ValidationError`` is a ``KartografError``, so ``main`` prints
    ``Error: ...`` to stderr and returns 1 (the hint comes with the error,
    not on stdout).

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
    bbox = BBox(values[0], values[1], values[2], values[3], crs)
    validate_request_bbox(bbox)
    return bbox
