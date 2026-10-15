"""
``elevation availability``: flags -> ``check_availability`` (ADR-037, ADR-041).

The CLI only translates the flags (``--bbox`` text, ``--force``) and prints
the ``AvailabilityReport``: a table of the combinations (newest year first),
``--details`` with the partial sheets, uncovered land and the commands of
every combination, ``--json`` with exactly ``AvailabilityReport.to_json()``.
Notices go to stderr (``Info:``/``Warning:``) when the library emits them;
an error of a source is ``Error:`` with exit code 1, a report without data
exits with 0 (it is an answer, not a failure).
"""

import argparse

from kartograf.cli._args import parse_bbox_arg
from kartograf.cli.download_cmd import _print_notice
from kartograf.download.availability import (
    AvailabilityCombination,
    AvailabilityReport,
    check_availability,
)

_HEADER = (
    "ROK",
    "NALOT",
    "UKLAD",
    "ROZDZ.",
    "WYSOKOSCI",
    "FORMAT",
    "ARKUSZE TAK/NIE",
    "KOMPLET",
)


def cmd_availability(args: argparse.Namespace) -> int:
    """Print the availability report of the flags (table or ``--json``)."""
    report = check_availability(
        product=args.product,
        country=args.country,
        sheet=args.sheet,
        bbox=parse_bbox_arg(args.bbox, args.bbox_crs) if args.bbox else None,
        geometry=args.geometry,
        layer=args.layer,
        year=args.year,
        min_year=args.min_year,
        max_year=args.max_year,
        force=args.force,
        on_notice=_print_notice,
    )
    if args.json:
        print(report.to_json(), end="")
        return 0
    _print_table(report)
    if args.details:
        _print_details(report)
    _print_footer(report)
    return 0


def area_text(value_m2: float) -> str:
    """``0,88 ha`` / ``16,00 km2`` - an area with a decimal comma."""
    if value_m2 >= 1_000_000:
        return f"{value_m2 / 1_000_000:.2f}".replace(".", ",") + " km2"
    return f"{value_m2 / 10_000:.2f}".replace(".", ",") + " ha"


def _flown(combination: AvailabilityCombination) -> str:
    dates = combination.acquisition_dates
    if dates is None:
        return "-"
    return dates[0] if dates[0] == dates[1] else f"{dates[0]}..{dates[1]}"


def _resolution(combination: AvailabilityCombination) -> str:
    if combination.densities:
        return f"{', '.join(map(str, combination.densities))} pkt/m2"
    return combination.resolution or "-"


def _complete(combination: AvailabilityCombination) -> str:
    if combination.complete:
        return "tak"
    parts = []
    if combination.sheets_partial:
        parts.append(f"{len(combination.sheets_partial)} niepelne")
    if combination.uncovered:
        parts.append(f"brak arkuszy dla {area_text(combination.uncovered_m2)}")
    return "nie: " + ", ".join(parts)


def _label(combination: AvailabilityCombination) -> str:
    """``2025 PL-1992 1m EVRF2007 ASC`` - a combination in one line."""
    return " ".join(
        part
        for part in (
            str(combination.year),
            combination.horizontal,
            combination.resolution,
            combination.vertical_crs,
            combination.format,
        )
        if part
    )


def _print_table(report: AvailabilityReport) -> None:
    request = report.request
    name = str(request["product"]).upper()
    for area in report.areas:
        print(
            f"Dostepnosc {name} {area.country} wg skorowidza GUGiK: obszar "
            f"{area_text(area.area_m2)}, w tym lad {area_text(area.land_m2)}"
        )
    if not report.combinations:
        unit = "kafli" if request["product"] == "laz" else "arkuszy"
        print(f"Brak {unit} {name} dla obszaru w skorowidzu GUGiK")
        return
    rows = [
        (
            str(c.year),
            _flown(c),
            c.horizontal,
            _resolution(c),
            c.vertical_crs,
            c.format,
            f"{len(c.sheets_full)}/{len(c.sheets_partial)}",
            _complete(c),
        )
        for c in report.combinations
    ]
    widths = [max(len(row[i]) for row in (_HEADER, *rows)) for i in range(len(_HEADER))]
    print()
    for row in (_HEADER, *rows):
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        print("  " + "  ".join(cells).rstrip())


def _print_details(report: AvailabilityReport) -> None:
    if not report.combinations:
        return
    print()
    print("Szczegoly kombinacji:")
    for combination in report.combinations:
        print(f"  {_label(combination)}: {_complete(combination)}")
        if combination.sheets_partial:
            print(
                f"    arkusze niepelne ({len(combination.sheets_partial)}): "
                f"{', '.join(combination.sheets_partial)}"
            )
        if combination.uncovered:
            print(
                f"    lad bez zadnego arkusza kombinacji: "
                f"{area_text(combination.uncovered_m2)}"
            )
        for hint in combination.download_hint:
            print(f"    kartograf {hint}")


def _print_footer(report: AvailabilityReport) -> None:
    if not report.combinations:
        return
    newest = next((c for c in report.combinations if c.complete), None)
    print()
    if newest is None:
        print(
            "Zadna kombinacja nie pokrywa calego ladu obszaru pelnymi arkuszami "
            "(arkusze niepelne i brakujace: --details)"
        )
        return
    print(f"Najnowsza kompletna kombinacja: {_label(newest)}")
    for hint in newest.download_hint:
        print(f"  Pobranie (dodaj --output KATALOG): kartograf {hint}")
        print(f"  W projekcie: kartograf project add NAZWA {hint}")
