"""
``elevation availability``: flags -> ``check_availability`` (ADR-037, ADR-041).

The CLI only translates the flags (``--bbox`` text, ``--force``) and prints
the ``AvailabilityReport`` per country: PL - a table of the combinations
(newest year first) and the newest complete one; CZ - a table per model and
sheet system with the publication date and size of the files (CUZK publishes
no survey years) and the commands of the complete combinations (at most
``MAX_HINT_LINES`` each); ``--details`` lists the partial and missing sheets,
the uncovered area, PL the share of the land in full sheets, each campaign on
its own and the campaigns of the records to download (KD-1/KD-2), and every
command; ``--json`` prints the report as the one
document of stdout (its notices are in it). Notices go to stderr (``Info:``/
``Warning:``) when the library emits them; an error of a source is ``Error:``
with exit code 1, a report without data exits with 0 (it is an answer, not
a failure), a report with a part that could not be checked (``auto``,
``ok=False``) is printed and exits with 1.
"""

import argparse

from kartograf.catalog.kinds import parse_bbox_arg
from kartograf.cli._json import emit_document
from kartograf.cli.download_cmd import notice_printer
from kartograf.download.availability import (
    AvailabilityArea,
    AvailabilityCombination,
    AvailabilityReport,
    check_availability,
)
from kartograf.download.data import MAX_HINT_LINES
from kartograf.sources.variants import CZ_MODELS, variants

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
_CZ_HEADER = (
    "MODEL",
    "UKLAD",
    "ROZDZ.",
    "WYSOKOSCI",
    "FORMAT",
    "ARKUSZE SA/BRAK",
    "PUBLIKACJA",
    "ROZMIAR",
    "KOMPLET",
)
_CZ_DATES = "CUZK nie publikuje lat nalotu; daty = publikacja pliku"


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
        on_notice=notice_printer(args),
    )
    if args.json:
        return emit_document(report)
    _print_tables(report)
    if args.details:
        _print_details(report)
    _print_footer(report)
    return 0 if report.ok else 1


def area_text(value_m2: float) -> str:
    """``0,88 ha`` / ``16,00 km2`` - an area with a decimal comma."""
    if value_m2 >= 1_000_000:
        return f"{value_m2 / 1_000_000:.2f}".replace(".", ",") + " km2"
    return f"{value_m2 / 10_000:.2f}".replace(".", ",") + " ha"


def size_text(value: int | None) -> str:
    """``15,9 MB`` - a size with a decimal comma (``-``: unknown)."""
    if value is None:
        return "-"
    for unit, scale in (("GB", 10**9), ("MB", 10**6), ("kB", 10**3)):
        if value >= scale:
            return f"{value / scale:.1f}".replace(".", ",") + f" {unit}"
    return f"{value} B"


def share_text(part_m2: float, whole_m2: float) -> str:
    """``58%`` - a share rounded down (an incomplete combination never reads
    100%), ``<1%`` for a non-zero share below one per cent."""
    if whole_m2 <= 0:
        return "-"
    percent = int(part_m2 * 100 // whole_m2)
    if percent == 0 and part_m2 > 0:
        return "<1%"
    return f"{percent}%"


def _span(dates: tuple[str, str] | None) -> str:
    if dates is None:
        return "-"
    return dates[0] if dates[0] == dates[1] else f"{dates[0]}..{dates[1]}"


def _resolution(combination: AvailabilityCombination) -> str:
    if combination.densities:
        return f"{', '.join(map(str, combination.densities))} pkt/m2"
    return combination.resolution or "-"


def _model(combination: AvailabilityCombination) -> str:
    """``DMP OK``: the CUZK model of a CZ combination (registry variant)."""
    model = next(
        (v.model for v in variants(country="CZ") if v.source == combination.source),
        None,
    )
    if model is not None and model in CZ_MODELS:
        return CZ_MODELS[model][0]
    return combination.source


def _complete(combination: AvailabilityCombination) -> str:
    if combination.complete:
        return "tak"
    parts = []
    if combination.sheets_partial:
        parts.append(f"{len(combination.sheets_partial)} niepelne")
    if combination.sheets_missing:
        parts.append(
            f"{len(combination.sheets_missing)} bez pliku "
            f"({area_text(combination.uncovered_m2)})"
        )
    elif combination.uncovered:
        parts.append(f"brak arkuszy dla {area_text(combination.uncovered_m2)}")
    return "nie: " + ", ".join(parts)


def _label(combination: AvailabilityCombination) -> str:
    """``2025 PL-1992 1m EVRF2007 ASC`` / ``DMP OK S-JTSK 0.5m Bpv TIFF`` - a
    combination in one line."""
    first = (
        str(combination.year) if combination.year is not None else _model(combination)
    )
    return " ".join(
        part
        for part in (
            first,
            combination.horizontal,
            combination.resolution,
            combination.vertical_crs,
            combination.format,
        )
        if part
    )


def _of(report: AvailabilityReport, country: str) -> list[AvailabilityCombination]:
    return [c for c in report.combinations if c.country == country]


def _print_rows(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]
    print()
    for row in (header, *rows):
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        print("  " + "  ".join(cells).rstrip())


def _print_tables(report: AvailabilityReport) -> None:
    for number, area in enumerate(report.areas):
        if number:
            print()
        if area.country == "CZ":
            _print_cz(report, area)
        else:
            _print_pl(report, area)


def _print_pl(report: AvailabilityReport, area: AvailabilityArea) -> None:
    product = str(report.request["product"])
    name = product.upper()
    print(
        f"Dostepnosc {name} PL wg skorowidza GUGiK: obszar "
        f"{area_text(area.area_m2)}, w tym lad {area_text(area.land_m2)}"
    )
    found = _of(report, "PL")
    if not found:
        unit = "kafli" if product == "laz" else "arkuszy"
        print(f"Brak {unit} {name} dla obszaru w skorowidzu GUGiK")
        return
    _print_rows(
        _HEADER,
        [
            (
                str(c.year),
                _span(c.acquisition_dates),
                c.horizontal,
                _resolution(c),
                c.vertical_crs,
                c.format,
                f"{len(c.sheets_full)}/{len(c.sheets_partial)}",
                _complete(c),
            )
            for c in found
        ],
    )


def _print_cz(report: AvailabilityReport, area: AvailabilityArea) -> None:
    name = str(report.request["product"]).upper()
    print(
        f"Dostepnosc {name} CZ wg indeksu arkuszy i plikow CUZK: obszar "
        f"{area_text(area.area_m2)}"
    )
    print(_CZ_DATES)
    found = _of(report, "CZ")
    if not found:
        print(f"Brak arkuszy {name} dla obszaru w indeksie CUZK")
        return
    _print_rows(
        _CZ_HEADER,
        [
            (
                _model(c),
                c.horizontal,
                _resolution(c),
                c.vertical_crs,
                c.format,
                f"{len(c.sheets_full)}/{len(c.sheets_missing)}",
                _span(c.published),
                size_text(c.size_bytes),
                _complete(c),
            )
            for c in found
        ],
    )


def _print_details(report: AvailabilityReport) -> None:
    if not report.combinations:
        return
    land = {area.country: area.land_m2 for area in report.areas}
    print()
    print("Szczegoly kombinacji:")
    for combination in report.combinations:
        print(f"  {_label(combination)}: {_complete(combination)}")
        if combination.sheets_partial:
            print(
                f"    arkusze niepelne ({len(combination.sheets_partial)}): "
                f"{', '.join(combination.sheets_partial)}"
            )
        if combination.sheets_missing:
            print(
                f"    arkusze bez pliku ({len(combination.sheets_missing)}): "
                f"{', '.join(combination.sheets_missing)}"
            )
        elif combination.uncovered:
            print(
                f"    lad bez zadnego arkusza kombinacji: "
                f"{area_text(combination.uncovered_m2)}"
            )
        if combination.country == "PL":
            _print_campaigns(combination, land[combination.country])
        for hint in combination.download_hint:
            print(f"    kartograf {hint}")


def _print_campaigns(combination: AvailabilityCombination, land_m2: float) -> None:
    """KD-1/KD-2 of a PL combination: the land in full sheets (incomplete
    only), each campaign on its own and the campaigns of the records the
    hint downloads."""
    if not combination.complete:
        print(
            "    lad w ramach pelnych arkuszy: "
            f"{share_text(combination.full_m2, land_m2)} "
            f"({area_text(combination.full_m2)})"
        )
    if combination.campaign_coverage:
        coverage = ", ".join(
            f"{c.campaign} "
            f"({'komplet' if c.complete else share_text(c.full_m2, land_m2)})"
            for c in combination.campaign_coverage
        )
        print(f"    kampanie: {coverage}")
    if combination.sheet_records:
        counts: dict[str, int] = {}
        for record in combination.sheet_records:
            name = record.campaign or "bez numeru"
            counts[name] = counts.get(name, 0) + 1
        sheets = len({record.sheet for record in combination.sheet_records})
        unit = "kafli" if combination.product == "laz" else "ark."
        print(
            f"    pobierane rekordy: {sheets} {unit}, kampanie: "
            + ", ".join(f"{name} ({count})" for name, count in sorted(counts.items()))
        )


def _print_footer(report: AvailabilityReport) -> None:
    if _of(report, "PL"):
        _print_pl_footer(_of(report, "PL"))
    if _of(report, "CZ"):
        _print_cz_footer(_of(report, "CZ"))


def _print_pl_footer(found: list[AvailabilityCombination]) -> None:
    newest = next((c for c in found if c.complete), None)
    print()
    if newest is None:
        print(
            "Zadna kombinacja nie pokrywa calego ladu obszaru pelnymi arkuszami "
            "(arkusze niepelne i brakujace: --details)"
        )
        return
    print(f"Najnowsza kompletna kombinacja: {_label(newest)}")
    hints = newest.download_hint
    for hint in hints[:MAX_HINT_LINES]:
        print(f"  Pobranie (dodaj --output KATALOG): kartograf {hint}")
        print(f"  W projekcie: kartograf project add NAZWA {hint}")
    rest = len(hints) - MAX_HINT_LINES
    if rest > 0:
        print(f"  ... pozostale polecenia: {rest} (wszystkie: --details albo --json)")


def _print_cz_footer(found: list[AvailabilityCombination]) -> None:
    complete = [c for c in found if c.complete]
    print()
    if not complete:
        print(
            "Zadna kombinacja CZ nie ma plikow wszystkich arkuszy obszaru "
            "(arkusze bez pliku: --details)"
        )
        return
    print(
        "Kompletne kombinacje CZ (pobranie: dodaj --output KATALOG; w projekcie: "
        "kartograf project add NAZWA zamiast kartograf):"
    )
    for combination in complete:
        print(f"  {_label(combination)}")
        hints = combination.download_hint
        for hint in hints[:MAX_HINT_LINES]:
            print(f"    kartograf {hint}")
        rest = len(hints) - MAX_HINT_LINES
        if rest > 0:
            print(
                f"    ... pozostale polecenia: {rest} (wszystkie: --details albo "
                "--json)"
            )
