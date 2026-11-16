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
from kartograf.cli._json import command_id, emit_result
from kartograf.cli._language import language, localized
from kartograf.cli.download_cmd import notice_printer
from kartograf.download.availability import (
    AvailabilityArea,
    AvailabilityCombination,
    AvailabilityReport,
    check_availability,
)
from kartograf.download.data import MAX_HINT_LINES
from kartograf.envelope import exit_code_of
from kartograf.messages import message
from kartograf.sources.variants import CZ_MODELS, variants

_HEADER = (
    message("cli.header_year"),
    message("cli.header_flight"),
    message("cli.header_crs"),
    message("cli.header_resolution"),
    message("cli.header_heights"),
    "FORMAT",
    message("cli.header_sheets_yes_no"),
    message("cli.header_complete"),
)
_CZ_HEADER = (
    "MODEL",
    message("cli.header_crs"),
    message("cli.header_resolution"),
    message("cli.header_heights"),
    "FORMAT",
    message("cli.header_sheets_present"),
    message("cli.header_published"),
    message("cli.header_size"),
    message("cli.header_complete"),
)
_CZ_DATES = message("cli.cz_dates_note")


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
        return emit_result(command_id(args), report)
    _print_tables(report)
    if args.details:
        _print_details(report)
    _print_footer(report)
    return exit_code_of(report)


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
    """Format a share as ``58%``, rounded down.

    An incomplete combination never reads 100%; ``<1%`` is for a non-zero share below
    one per cent.
    """
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
        return message(
            "cli.points_per_m2",
            lang=language(),
            densities=", ".join(map(str, combination.densities)),
        )
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


def _complete(combination: AvailabilityCombination, land_m2: float) -> str:
    if combination.complete:
        # no land to cover: "yes" would promise data the area does not need
        return (
            message("cli.yes", lang=language())
            if land_m2 > 0
            else message("cli.complete_no_land", lang=language())
        )
    parts = []
    if combination.sheets_partial:
        parts.append(
            message(
                "cli.sheets_incomplete_count",
                lang=language(),
                count=len(combination.sheets_partial),
            )
        )
    if combination.sheets_missing:
        parts.append(
            message(
                "cli.sheets_missing_file",
                lang=language(),
                sheets_missing_count=len(combination.sheets_missing),
                area_text=area_text(combination.uncovered_m2),
            )
        )
    elif combination.uncovered:
        parts.append(
            message(
                "cli.no_sheets_for_area",
                lang=language(),
                area_text=area_text(combination.uncovered_m2),
            )
        )
    return message("cli.complete_no_parts", lang=language(), parts=", ".join(parts))


def _label(combination: AvailabilityCombination) -> str:
    """Return a combination in one line.

    The text is like ``2025 PL-1992 1m EVRF2007 ASC`` / ``DMP OK S-JTSK 0.5m Bpv TIFF``.
    """
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
    header = tuple(localized(cell) for cell in header)
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
        message(
            "cli.pl_availability_header",
            lang=language(),
            name=name,
            area_text=area_text(area.area_m2),
            land_text=area_text(area.land_m2),
        )
    )
    found = _of(report, "PL")
    if not found:
        unit = (
            message("cli.unit_tiles", lang=language())
            if product == "laz"
            else message("cli.unit_sheets", lang=language())
        )
        print(message("cli.pl_no_sheets_found", lang=language(), unit=unit, name=name))
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
                _complete(c, area.land_m2),
            )
            for c in found
        ],
    )


def _print_cz(report: AvailabilityReport, area: AvailabilityArea) -> None:
    name = str(report.request["product"]).upper()
    print(
        message(
            "cli.cz_availability_header",
            lang=language(),
            name=name,
            area_text=area_text(area.area_m2),
        )
    )
    print(localized(_CZ_DATES))
    found = _of(report, "CZ")
    if not found:
        print(message("cli.cz_no_sheets_found", lang=language(), name=name))
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
                _complete(c, area.land_m2),
            )
            for c in found
        ],
    )


def _print_details(report: AvailabilityReport) -> None:
    if not report.combinations:
        return
    land = {area.country: area.land_m2 for area in report.areas}
    print()
    print(message("cli.combination_details", lang=language()))
    for combination in report.combinations:
        complete = _complete(combination, land[combination.country])
        print(f"  {_label(combination)}: {complete}")
        if combination.sheets_partial:
            print(
                message(
                    "cli.sheets_partial_list",
                    lang=language(),
                    sheets_partial_count=len(combination.sheets_partial),
                    sheets_partial=", ".join(combination.sheets_partial),
                )
            )
        if combination.sheets_missing:
            print(
                message(
                    "cli.sheets_without_file",
                    lang=language(),
                    sheets_missing_count=len(combination.sheets_missing),
                    sheets_missing=", ".join(combination.sheets_missing),
                )
            )
        elif combination.uncovered:
            print(
                message(
                    "cli.uncovered_land_area",
                    lang=language(),
                    area_text=area_text(combination.uncovered_m2),
                )
            )
        if combination.country == "PL":
            _print_campaigns(combination, land[combination.country])
        for hint in combination.download_hint:
            print(f"    kartograf {hint}")


def _print_campaigns(combination: AvailabilityCombination, land_m2: float) -> None:
    """KD-1/KD-2 of a PL combination.

    The land in full sheets (incomplete only), each campaign on its own and the
    campaigns of the records the hint downloads.
    """
    if not combination.complete:
        print(
            message(
                "cli.land_in_full_sheets",
                lang=language(),
                share_text=share_text(combination.full_m2, land_m2),
                area_text=area_text(combination.full_m2),
            )
        )
    if combination.campaign_coverage:
        done = message("cli.campaign_complete", lang=language())
        coverage = ", ".join(
            f"{c.campaign} ({done if c.complete else share_text(c.full_m2, land_m2)})"
            for c in combination.campaign_coverage
        )
        print(message("cli.campaigns_coverage", lang=language(), coverage=coverage))
    if combination.sheet_records:
        counts: dict[str, int] = {}
        for record in combination.sheet_records:
            name = record.campaign or message("cli.campaign_no_number", lang=language())
            counts[name] = counts.get(name, 0) + 1
        sheets = len({record.sheet for record in combination.sheet_records})
        unit = (
            message("cli.unit_tiles", lang=language())
            if combination.product == "laz"
            else message("cli.unit_sheets_short", lang=language())
        )
        print(
            message(
                "cli.records_to_download",
                lang=language(),
                sheets=sheets,
                unit=unit,
                texts=", ".join(
                    f"{name} ({count})" for name, count in sorted(counts.items())
                ),
            )
        )


def _print_footer(report: AvailabilityReport) -> None:
    if _of(report, "PL"):
        land = next(a.land_m2 for a in report.areas if a.country == "PL")
        _print_pl_footer(_of(report, "PL"), land)
    if _of(report, "CZ"):
        _print_cz_footer(_of(report, "CZ"))


def _print_pl_footer(found: list[AvailabilityCombination], land_m2: float) -> None:
    newest = next((c for c in found if c.complete), None)
    print()
    if land_m2 <= 0:
        # every combination is complete for lack of land: nothing is proposed
        print(message("cli.no_pl_land", lang=language()))
        return
    if newest is None:
        print(message("cli.no_full_combination", lang=language()))
        return
    print(
        message(
            "cli.newest_complete_combination", lang=language(), label=_label(newest)
        )
    )
    hints = newest.download_hint
    for hint in hints[:MAX_HINT_LINES]:
        print(message("cli.download_hint_line", lang=language(), hint=hint))
    rest = len(hints) - MAX_HINT_LINES
    if rest > 0:
        print(message("cli.remaining_commands_pl", lang=language(), rest=rest))


def _print_cz_footer(found: list[AvailabilityCombination]) -> None:
    complete = [c for c in found if c.complete]
    print()
    if not complete:
        print(message("cli.no_complete_cz_combination", lang=language()))
        return
    print(message("cli.complete_cz_combinations", lang=language()))
    for combination in complete:
        print(f"  {_label(combination)}")
        hints = combination.download_hint
        for hint in hints[:MAX_HINT_LINES]:
            print(f"    kartograf {hint}")
        rest = len(hints) - MAX_HINT_LINES
        if rest > 0:
            print(message("cli.remaining_commands_cz", lang=language(), rest=rest))
