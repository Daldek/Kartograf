"""
``kartograf download`` command (sheet code / bbox / geometry / LAZ modes).
"""

import argparse
import contextlib
import json
import math
import sys
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from kartograf.cache.defaults import open_cache
from kartograf.cli._parser import (
    COUNTRY_CHOICES,
    PRODUCT_CHOICES,
    RESOLUTION_CZ,
    RESOLUTION_PL,
    SCALE_2000_CHOICES,
    SYSTEM_CHOICES,
    VERTICAL_CRS_CZ,
    VERTICAL_CRS_PL,
    parse_bbox_arg,
)
from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox
from kartograf.download.campaigns import validate_year_bounds
from kartograf.download.countries import EDGES as _EDGES
from kartograf.download.countries import CountryPart
from kartograf.download.countries import bbox_to_wgs84 as _bbox_to_wgs84
from kartograf.download.countries import countries_for_bbox as _countries_for_bbox
from kartograf.download.countries import country_bbox as _country_bbox
from kartograf.download.fetch import UpdateMode, VersionedFile
from kartograf.download.manager import DownloadManager, DownloadProgress, DownloadResult
from kartograf.download.plan import PlanItem, UpdatePlan
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    ParseError,
    ValidationError,
)
from kartograf.notices import Notice
from kartograf.providers.pl import require_nmt_vertical_crs
from kartograf.sources.registry import horizontal_crs_for_sheet

# PL-2000 sheet scales GUGiK can publish below the 1:10000 frame.
_SCALES_2000 = ("1:5000", "1:2000", "1:1000", "1:500")


class _ProgressPrinter:
    """Progress bar callback; ``pending`` = last line without a line ending.

    With ``--workers > 1`` ``pending`` reflects the last write (at worst
    a redundant or missing ``\\n`` before ``Error:``).
    """

    def __init__(self) -> None:
        self.pending = False

    def __call__(self, progress: DownloadProgress) -> None:
        """Print progress bar and status."""
        bar_width = 30
        filled = int(bar_width * progress.current / max(progress.total, 1))
        bar = "=" * filled + "-" * (bar_width - filled)

        status_icon = {
            "downloading": "↓",
            "completed": "✓",
            "skipped": "○",
            "failed": "✗",
            # D11: a sheet with no data at the source (sea, area abroad) is an
            # expected state, not a failure - a different icon than a download failure
            "no_coverage": "∅",
        }.get(progress.status, " ")

        line = (
            f"\r[{bar}] {progress.current}/{progress.total} "
            f"{status_icon} {progress.sheet}"
        )

        # Pad to overwrite previous longer lines
        line = line.ljust(80)

        if progress.status in ("completed", "failed", "no_coverage"):
            print(line, flush=True)
            self.pending = False
        else:
            print(line, end="", flush=True)
            self.pending = True


def create_progress_callback(quiet: bool = False):
    """
    Create a progress callback for download operations.

    Parameters
    ----------
    quiet : bool
        If True, suppress output

    Returns
    -------
    callable or None
        Progress callback (``None`` under ``quiet``)
    """
    if quiet:
        return None
    return _ProgressPrinter()


def _error_lead(on_progress) -> str:
    """``"\\n"`` only if the progress bar left a line unterminated (no blank line)."""
    return "\n" if getattr(on_progress, "pending", False) is True else ""


def _create_provider_and_storage(
    product, output_dir, vertical_crs, resolution, cache=None
):
    """
    Create provider and storage based on product type.

    ``cache`` (``MetadataCache`` or ``None``) goes to the provider: GUGiK
    index records are read and written exclusively via the cache (N6;
    ``--force`` uses a refresh-mode cache from ``open_cache``).

    LAZ has a separate flow (`_cmd_download_laz`) and never reaches this
    helper — `cmd_download` short-circuits it before any provider is built.
    """
    from kartograf.download.storage import storage_for_provider

    if product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider = GugikNmptProvider(vertical_crs=vertical_crs, cache=cache)
    elif product == "orto":
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        # the CLI offers the RGB composition only (`--product orto`)
        provider = GugikOrtoProvider(cache=cache, color="RGB")
    elif product == "nmt":
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(
            vertical_crs=vertical_crs, resolution=resolution, cache=cache
        )
    else:
        raise ValidationError(
            f"Unsupported product for DownloadManager flow: {product} "
            "(LAZ uses _cmd_download_laz)"
        )

    storage = storage_for_provider(
        output_dir, provider, resolution=resolution, vertical_crs=vertical_crs
    )
    return provider, storage


# Cache warnings already printed by the current ``cmd_download`` (PL and CZ
# open separate caches on the same file, e.g. a border bbox under ``auto``).
_cache_warnings_shown: set[str] = set()


def _warn_cache_disabled(notice: Notice) -> None:
    """Print one disabled-cache warning per CLI command."""
    if notice.text in _cache_warnings_shown:
        return
    _cache_warnings_shown.add(notice.text)
    print(f"Warning: {notice.text}", file=sys.stderr, flush=True)


def _print_sheet_notice(notice: Notice) -> None:
    """Print each library sheet notice when it is emitted, also in quiet mode."""
    prefix = "Info" if notice.level == "info" else "Warning"
    print(f"{prefix}: {notice.text}", file=sys.stderr)


def _announce_geometry_layer(args: argparse.Namespace) -> bool:
    """Resolve the ``--geometry`` layer ONCE; ``Info:`` when the default was taken.

    A GPKG with several layers and no ``--layer`` is read from its first layer
    only - the area of the task comes from it. One ``Info:`` on stderr (also with
    ``-q``) names the choice and the others; ``args.layer`` then carries the
    explicit name, so the geometry readers called later neither repeat nor log it.
    Errors (missing file, unknown layer, no feature tables) print ``Error:`` and
    return ``False``.
    """
    from kartograf.core.geometry import resolve_layer

    filepath = Path(args.geometry)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return False
    try:
        choice = resolve_layer(filepath, getattr(args, "layer", None))
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    if choice.defaulted and len(choice.available) > 1:
        print(
            f"Info: {filepath.name}: liczba warstw {len(choice.available)}, uzyto "
            f"pierwszej '{choice.name}' (pozostale: "
            f"{', '.join(choice.available[1:])}); inna warstwa: --layer NAZWA",
            file=sys.stderr,
        )
    args.layer = choice.name
    return True


def _product_label(product: str, resolution: str | None) -> str:
    """Task label in messages: orto has no resolution (K5)."""
    if product == "orto":
        return "product: orto"
    return f"resolution: {resolution}"


def _print_sheet_list(
    sheets: list[str], target_scale: str, *, what: str, label: str
) -> None:
    """Header of the PL sheet list (list mode, D15): up to 10 sheet codes
    in full, a longer list as the first 3 + ``...`` + the last 2."""
    print(f"Found {len(sheets)} sheets at {target_scale} for {what} ({label})")
    sample = sheets if len(sheets) <= 10 else sheets[:3] + ["..."] + sheets[-2:]
    print(f"  Sheets: {', '.join(sample)}")
    print()


_CZ_ONLY_NMT_MSG = (
    "Error: --product {product} dla CZ bedzie dostepny w etapie 2 — teraz tylko nmt"
)


def _reject_non_nmt_for_cz(product: str) -> bool:
    """
    True (after a message on stderr) when the CZ product is other than ``nmt``.

    The guard lives in the dispatch layer - the ``_cmd_download_cz`` flow assumes
    an already resolved product.
    """
    if product == "nmt":
        return False
    print(_CZ_ONLY_NMT_MSG.format(product=product), file=sys.stderr)
    return True


def _campaign_opts(
    args: argparse.Namespace,
) -> tuple[bool, int | None, int | None]:
    """All-flights choice and year bounds; absent attributes support handmade tests."""
    return (
        getattr(args, "all_campaigns", False),
        getattr(args, "min_year", None),
        getattr(args, "max_year", None),
    )


_COUNTRY_KEYS = ("pl", "cz")


def _check_country_value_syntax(raw: str | None, flag: str) -> str | None:
    """Error text for a malformed per-country form of ``flag``, else ``None``.

    A value is either one plain value for every country of the task
    (``5m``) or comma-separated ``country=value`` pairs (``pl=1m,cz=2m``;
    keys ``pl``/``cz``, case-insensitive, each at most once).
    """
    if raw is None or "=" not in raw:
        return None
    seen: set[str] = set()
    for item in raw.split(","):
        key, sep, value = item.partition("=")
        key = key.strip().lower()
        if not sep or key not in _COUNTRY_KEYS or not value.strip() or key in seen:
            return (
                f"{flag}: nieprawidlowa wartosc {raw!r} — podaj jedna wartosc dla "
                f"kazdego kraju zadania albo pary kraj=wartosc rozdzielone "
                f"przecinkami (kraje: pl, cz), np. {flag} pl=...,cz=..."
            )
        seen.add(key)
    return None


def _country_value(raw: str | None, code: str) -> str | None:
    """Value of a plain or per-country option for country ``code`` (PL/CZ).

    A plain value applies to every country; the per-country form gives
    ``None`` for a country it does not name. Syntax is checked earlier
    (``_check_country_value_syntax``).
    """
    if raw is None or "=" not in raw:
        return raw
    for item in raw.split(","):
        key, _, value = item.partition("=")
        if key.strip().lower() == code.lower():
            return value.strip()
    return None


def _per_country_hint(raw: str | None, flag: str, countries: tuple[str, ...]) -> str:
    """Suffix suggesting the per-country form for a task spanning PL and CZ."""
    if len(countries) < 2:
        return ""
    return f" (zadanie PL+CZ: wartosci per kraj, np. {flag} pl=...,cz=...)"


def _pl_option_error(
    args: argparse.Namespace,
    *,
    sheet_system: str | None = None,
    sheet_scale: str | None = None,
    countries: tuple[str, ...] = ("PL",),
) -> str | None:
    """Error text (without ``Error:``) for the PL data choices of the task.

    ``sheet_system``/``sheet_scale`` describe a ``--sheet`` task (system and
    scale of the code); ``None`` = area task (``--bbox``/``--geometry``).
    Checked before any network access; values come from the PL part of a
    plain or per-country ``--resolution``/``--vertical-crs``.
    """
    product = args.product
    resolution = _country_value(args.resolution, "PL")
    vertical_crs = _country_value(args.vertical_crs, "PL")
    target_crs = getattr(args, "target_crs", None)
    res_hint = _per_country_hint(args.resolution, "--resolution", countries)
    vcrs_hint = _per_country_hint(args.vertical_crs, "--vertical-crs", countries)

    if target_crs is not None and product in ("orto", "laz"):
        return (
            "--target-crs dla PL dziala tylko z --product nmt albo nmpt "
            "(wycinek wysokosci z WCS GUGiK; orto i laz — pobierz bez "
            "--target-crs)"
        )
    if product == "nmt":
        if target_crs is not None:
            if resolution not in (None, "1m"):
                return (
                    "wycinki --target-crs sa tylko 1 m (WCS GUGiK); arkusze 5 m: "
                    "pomin --target-crs; wycinek: --resolution 1m albo pomin "
                    "--resolution"
                )
        elif resolution is None:
            return f"--resolution wymagane dla NMT PL: {RESOLUTION_PL}{res_hint}"
        elif resolution not in ("1m", "5m"):
            return (
                f"PL nie ma rozdzielczosci {resolution} — dostepne: "
                f"{RESOLUTION_PL}{res_hint}"
            )
    elif product == "nmpt" and resolution not in (None, "1m"):
        return (
            f"--product nmpt jest dostepny tylko w rozdzielczosci 1m (podano "
            f"{resolution}); pomin --resolution albo podaj 1m"
        )

    if product == "orto":
        if vertical_crs is not None:
            return (
                "--vertical-crs nie dotyczy --product orto "
                "(ortofotomapa nie ma ukladu pionowego)"
            )
    elif vertical_crs is None:
        return (
            f"--vertical-crs wymagane dla --product {product} (PL): "
            f"{VERTICAL_CRS_PL}{vcrs_hint}"
        )
    elif vertical_crs not in ("KRON86", "EVRF2007"):
        return (
            f"{vertical_crs} nie jest ukladem wysokosci PL — dostepne: "
            f"{VERTICAL_CRS_PL}{vcrs_hint}"
        )
    elif product == "nmt":
        # 0.7.1: the library rule (`require_nmt_vertical_crs`) - 5m exists only
        # in EVRF2007; the message names CLI flags, not keyword arguments.
        try:
            require_nmt_vertical_crs(resolution or "1m", vertical_crs)
        except ValidationError:
            return (
                f"NMT {resolution} (PL) jest dostepny tylko w EVRF2007 — podano "
                f"--vertical-crs {vertical_crs}; uzyj --vertical-crs EVRF2007 "
                f"albo --resolution 1m dla {vertical_crs}"
            )

    if product == "laz":
        return None  # LAZ: per-tile system from WFS, no sheet scale
    system = getattr(args, "system", None)
    scale = getattr(args, "scale", None)
    if target_crs is not None:
        if system not in (None, "1992"):
            return (
                "--target-crs nie dziala z --system 2000 — bbox wielostrefowy "
                "dalby arkusze w roznych CRS (2176-2179); wycinek: --system 1992 "
                "albo pomin --system"
            )
        return None
    if sheet_system is None:
        if system is None:
            return f"--system wymagane dla --bbox/--geometry w PL: {SYSTEM_CHOICES}"
        effective = system
    else:
        effective = sheet_system
    if effective == "1992":
        if scale is not None:
            return (
                "--scale nie dotyczy PL-1992: GUGiK publikuje arkusze PL-1992 "
                "tylko w 1:10000 (godlo 7-czlonowe), a grubsze godlo rozwija sie "
                "do 1:10000 samo — pomin --scale"
            )
        return None
    if scale is None and (sheet_system is None or sheet_scale == "1:10000"):
        return f"--scale wymagane dla arkuszy PL-2000: {SCALE_2000_CHOICES}"
    if scale is not None and scale not in _SCALES_2000:
        return f"Nieznana skala PL-2000 {scale} — dostepne: {SCALE_2000_CHOICES}"
    return None


def _cz_option_error(
    args: argparse.Namespace,
    *,
    is_sm5: bool = False,
    countries: tuple[str, ...] = ("CZ",),
) -> str | None:
    """Error text (without ``Error:``) for the CZ data choices of the task.

    ``is_sm5``: a ``--sheet`` SM5 code (a ready DMR 4G file: only 5m).
    """
    resolution = _country_value(args.resolution, "CZ")
    vertical_crs = _country_value(args.vertical_crs, "CZ")
    res_hint = _per_country_hint(args.resolution, "--resolution", countries)
    vcrs_hint = _per_country_hint(args.vertical_crs, "--vertical-crs", countries)
    if is_sm5:
        if resolution not in (None, "5m"):
            return (
                f"Arkusze SM5 sa dostepne tylko w 5m (DMR 4G) — pomin "
                f"--resolution albo podaj 5m; dla {resolution} uzyj godla TM33 "
                f"albo --bbox [arkusz: {args.sheet}]"
            )
    elif resolution is None:
        return f"--resolution wymagane dla NMT CZ: {RESOLUTION_CZ}{res_hint}"
    elif resolution not in ("2m", "5m"):
        return (
            f"CZ nie ma rozdzielczosci {resolution} — dostepne: "
            f"{RESOLUTION_CZ}{res_hint}"
        )
    if vertical_crs is None:
        return f"--vertical-crs wymagane dla NMT CZ: {VERTICAL_CRS_CZ}{vcrs_hint}"
    if vertical_crs not in ("Bpv", "EVRF2007"):
        return (
            f"{vertical_crs} nie jest dostepny dla CZ — dostepne: "
            f"{VERTICAL_CRS_CZ}{vcrs_hint}"
        )
    if "PL" not in countries and getattr(args, "system", None) is not None:
        return "--system dotyczy tylko PL (godla CZ wykrywane wzorcem)"
    return None


def _reject_laz_only_opts(args: argparse.Namespace) -> bool:
    """Reject ``--min-density`` on non-LAZ products before any network request."""
    product = args.product
    if product == "laz":
        return False
    if getattr(args, "min_density", None) is not None:
        print(
            f"Error: --min-density dziala tylko z --product laz (podano "
            f"{product}); pomin --min-density",
            file=sys.stderr,
        )
        return True
    return False


def _reject_full_sheet_for_laz(args: argparse.Namespace) -> bool:
    """Reject ``--full-sheet`` for LAZ before any network request (ADR-033)."""
    if args.product != "laz" or not getattr(args, "full_sheet", False):
        return False
    print(
        "Error: --full-sheet dziala tylko z NMT/NMPT/orto (podano laz) — LAZ "
        "nie ma sciezki standardowej ani dowiazania full_sheet/; pomin --full-sheet",
        file=sys.stderr,
    )
    return True


def _reject_campaign_opts_without_pl(
    args: argparse.Namespace, countries: tuple[str, ...]
) -> bool:
    """Reject PL-only campaign/year choices in CZ; describe mixed tasks once."""
    all_campaigns, min_year, max_year = _campaign_opts(args)
    if (
        not all_campaigns
        and min_year is None
        and max_year is None
        and getattr(args, "year", None) is None
        and not getattr(args, "full_sheet", False)
    ):
        return False
    if "PL" not in countries:
        print(
            "Error: CZ (CUZK) nie ma kampanii — "
            "--all-campaigns/--min-year/--max-year/--year/--full-sheet dotycza "
            "tylko PL",
            file=sys.stderr,
        )
        return True
    if "CZ" in countries:
        print(
            "Info: --all-campaigns/--min-year/--max-year/--year/--full-sheet dotycza "
            "tylko czesci PL (CZ: biezaca wersja danych CUZK)",
            file=sys.stderr,
        )
    return False


def _reject_campaign_opts_with_target_crs(args: argparse.Namespace) -> bool:
    """A PL cutout (WCS, ADR-035) has no year or campaign choice: the server's
    flight composition, the download date in the name."""
    if getattr(args, "target_crs", None) is None:
        return False
    all_campaigns, min_year, max_year = _campaign_opts(args)
    flag = next(
        (
            name
            for name, supplied in (
                ("--year", getattr(args, "year", None)),
                ("--min-year", min_year),
                ("--max-year", max_year),
            )
            if supplied is not None
        ),
        None,
    )
    if flag is not None:
        print(
            f"Error: {flag} nie dziala z --target-crs — wycinek z WCS GUGiK ma "
            "kompozycje lotow serwera (bez wyboru roku); rok danych: pobierz "
            "arkusze bez --target-crs",
            file=sys.stderr,
        )
        return True
    if all_campaigns:
        print(
            "Error: --all-campaigns nie dziala z --target-crs — wycinek z WCS "
            "GUGiK ma jedna kompozycje lotow serwera; wszystkie kampanie: "
            "pobierz arkusze bez --target-crs",
            file=sys.stderr,
        )
        return True
    if getattr(args, "full_sheet", False):
        print(
            "Error: --full-sheet nie dziala z --target-crs — wycinek pochodzi "
            "z WCS GUGiK, nie z arkuszy",
            file=sys.stderr,
        )
        return True
    return False


def _resolve_pl_options(
    args: argparse.Namespace,
    *,
    sheet_system: str | None = None,
    sheet_scale: str | None = None,
) -> int:
    """
    Validate the PL data choices and narrow ``args`` to the PL values.

    Called ONLY on the PL branch, after the country is resolved - it mutates
    ``args`` (``--resolution``/``--vertical-crs`` become the plain PL values),
    so arguments heading to CZ must be a separate copy (``_dispatch_area``).
    Nothing is defaulted: a missing choice is an ``Error:`` listing the
    admissible values (``_pl_option_error``). Only single-valued choices are
    filled in: NMPT and the ``--target-crs`` cutout are 1m only, the cutout
    is PL-1992 only, a ``--sheet`` task takes its system from the code.

    Returns
    -------
    int
        0 = OK, 1 = error (message already printed to stderr)
    """
    error = _pl_option_error(args, sheet_system=sheet_system, sheet_scale=sheet_scale)
    if error is not None:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    product = args.product
    target_crs = getattr(args, "target_crs", None)
    resolution = _country_value(args.resolution, "PL")
    if resolution is None and (product == "nmpt" or target_crs is not None):
        resolution = "1m"
    args.resolution = resolution
    args.vertical_crs = _country_value(args.vertical_crs, "PL")
    if sheet_system is not None:
        args.system = sheet_system
    elif target_crs is not None:
        args.system = "1992"
    return 0


def _pl_target_scale(args: argparse.Namespace) -> str:
    """Sheet scale of a PL area task: PL-1992 fixed 1:10000, PL-2000 ``--scale``.

    GUGiK publishes PL-1992 sheets only at 1:10000 (7-part code); PL-2000
    sheets in several modules, so the (validated, required) ``--scale``.
    """
    return args.scale if args.system == "2000" else "1:10000"


def _run_cz(
    args: argparse.Namespace,
    bbox: BBox | None = None,
    parent_request: dict | None = None,
) -> int:
    """
    Call the CZ flow, translating a task exception into a CLI message.

    The CZ flow signals a bad task with an exception: ``ValidationError`` (e.g.
    ``--target-crs`` with a sheet code), ``ParseError`` (a sheet code matching the
    TM33/SM5 pattern but invalid - e.g. odd kilometers) or ``TransformError``
    (normalizing the bbox to the task CRS has no safe operation). ``main`` has a barrier
    (``KartografError`` -> ``Error: ...``, code 1), but an exception leaking from here
    would break the country loop of ``_dispatch_area`` - under ``--country auto`` the
    success of the other country would no longer give code 0 (ADR-023 points 4-5). Hence
    they are translated here; the PL branch catches the same exceptions in
    ``cmd_download``.
    """
    from kartograf.transform.crs import TransformError

    try:
        return _cmd_download_cz(args, bbox=bbox, parent_request=parent_request)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except TransformError as e:
        return _print_transform_error(e)


def _print_transform_error(error: Exception) -> int:
    """Transformation error message (with a remedy, if any); always returns 1.

    The only place of the ``Error: <error> Remedium: <remedy>`` format in the CLI;
    an exception without a ``remedy`` attribute gives just ``Error: <error>``.
    """
    remedy = getattr(error, "remedy", None)
    print(
        f"Error: {error}" + (f" Remedium: {remedy}" if remedy else ""),
        file=sys.stderr,
    )
    return 1


def _deg(value: float, unit: str) -> str:
    """``54,90°N`` — degrees with a decimal comma (Polish messages)."""
    return f"{value:.2f}".replace(".", ",") + f"°{unit}"


def _area_outside_extents(
    wgs: BBox, extents: Sequence[BBox]
) -> tuple[BBox | None, float]:
    """
    Part of the WGS84 bbox outside ALL ``extents`` rectangles (S3).

    The rectangle edges cut the bbox into cells; a cell whose center is not
    covered by any rectangle is lost (under ``--country auto`` nobody will download
    it). Returns the envelope of the lost cells (``None`` when the bbox
    is fully covered) and their area share of the bbox area
    (0..1; cells weighted by ``cos(latitude)``, so the share is metric).

    The edge test alone is not enough: a bbox 13-15°E x 53-55°N has its W edge
    within the CZ longitude range, but CZ ends at 51.06°N - the loss
    in the corner is visible only after the split into cells.
    """
    xs = sorted(
        {wgs.min_x, wgs.max_x}
        | {v for e in extents for v in (e.min_x, e.max_x) if wgs.min_x < v < wgs.max_x}
    )
    ys = sorted(
        {wgs.min_y, wgs.max_y}
        | {v for e in extents for v in (e.min_y, e.max_y) if wgs.min_y < v < wgs.max_y}
    )
    total = 0.0
    lost_area = 0.0
    lost: list[tuple[float, float, float, float]] = []
    for x0, x1 in zip(xs, xs[1:], strict=False):
        for y0, y1 in zip(ys, ys[1:], strict=False):
            area = (x1 - x0) * (y1 - y0) * math.cos(math.radians((y0 + y1) / 2))
            total += area
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if not any(
                e.min_x <= cx <= e.max_x and e.min_y <= cy <= e.max_y for e in extents
            ):
                lost.append((x0, y0, x1, y1))
                lost_area += area
    if not lost or total <= 0:
        return None, 0.0
    envelope = BBox(
        min(c[0] for c in lost),
        min(c[1] for c in lost),
        max(c[2] for c in lost),
        max(c[3] for c in lost),
        "EPSG:4326",
    )
    return envelope, lost_area / total


def _print_clipping_info(
    bbox: BBox,
    countries: tuple[str, ...],
    parts: dict[str, CountryPart],
    *,
    pl_geometry_sheets: bool = False,
    pl_sheet_list: bool = False,
) -> None:
    """``Info:`` about clipping under ``--country auto`` (S3; stderr, ``-q`` does not
    suppress).

    PL --geometry without a cutout downloads sheets from the whole geometry, so
    clipping its auxiliary bbox does not limit the PL download.
    """
    from kartograf.sources.registry import get_country

    for code in countries:
        if code == "PL" and pl_geometry_sheets:
            continue
        part = parts[code]
        if not part.clipped:
            continue
        extent = get_country(code).extent_wgs84
        edges = ", ".join(
            f"{edge}: {_deg(getattr(extent, attr), unit)}"
            for edge, attr, _is_min, unit in _EDGES
            if edge in part.clipped
        )
        if code == "PL" and pl_sheet_list:
            result = (
                "arkusze wyznaczono z przycietego bboxa, sidecar ma "
                "request.sheet; oryginal w extra.parent_request.bbox"
            )
        else:
            result = (
                "plik i request.bbox niosa zasieg przyciety, oryginal "
                "w extra.parent_request.bbox"
            )
        print(
            f"Info: --country auto: czesc {code} przycieta do obwiedni kraju "
            f"({edges}); {result}",
            file=sys.stderr,
        )
    if not any(parts[code].clipped for code in countries):
        return
    if pl_geometry_sheets and "PL" in countries:
        # PL reads the WHOLE geometry, so also the area outside the rectangles.
        return
    lost, share = _area_outside_extents(
        _bbox_to_wgs84(bbox), [get_country(c).extent_wgs84 for c in countries]
    )
    if lost is None:
        return
    explicit = "pl" if "PL" in countries else countries[0].lower()
    print(
        f"Info: --country auto: obszar {_deg(lost.min_x, 'E')}-{_deg(lost.max_x, 'E')}"
        f" x {_deg(lost.min_y, 'N')}-{_deg(lost.max_y, 'N')} (~{share * 100:.0f} % "
        "powierzchni zadania) lezy poza zasiegiem PL/CZ i zostal pominiety; "
        f"caly bbox pobiera jawne --country {explicit} (za granica: arkusze "
        "bez danych / nodata)",
        file=sys.stderr,
    )


def _build_parent_request(bbox: BBox, countries: tuple[str, ...]) -> dict:
    """
    Description of an area task for the sidecars' ``extra.parent_request``.

    Groups the files of one bbox/geometry task (including those lying on both
    sides of the border): carries the task's ORIGINAL bbox - before per-country
    clipping - its CRS and the countries QUERIED in this call (attempted, not
    downloaded - ADR-023 point 3).

    The returned dict must NOT be mutated later: consumers (CZ sidecars,
    ``DownloadManager(sidecar_extra=)``) hold it by reference, and a shallow
    copy in the manager does not protect nested values.
    """
    return {
        "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
        "bbox_crs": bbox.crs,
        "countries": list(countries),
    }


_CROSS_COUNTRY_HINT = "uzyj jawnie --country pl albo --country cz"


def _validate_cross_country(
    args: argparse.Namespace, countries: tuple[str, ...]
) -> int:
    """
    Options must be valid for EVERY country of the task (0=OK, 1=error).

    Validation happens BEFORE any download - otherwise part of one country would be
    downloaded and the other branch would reject the task only afterwards (partial
    execution). Each country is checked with its own value of a plain or
    per-country ``--resolution``/``--vertical-crs`` (``pl=..,cz=..``); a task
    spanning PL and CZ gets the per-country form in the hint.

    ORDER: under ``--country auto`` some options are already resolved
    earlier (``_pl_only_flags`` in ``_dispatch_area``, ADR-023 point 5), so
    ``countries`` may be single-element by now.
    """
    product = args.product
    hint = f"; {_CROSS_COUNTRY_HINT}" if len(countries) > 1 else ""
    if "CZ" in countries and product != "nmt":
        print(
            f"Error: --product {product} jest dostepny tylko dla PL{hint}",
            file=sys.stderr,
        )
        return 1
    for code in countries:
        if code == "PL":
            error = _pl_option_error(args, countries=countries)
        else:
            error = _cz_option_error(args, countries=countries)
        if error is not None:
            print(f"Error: {error}", file=sys.stderr)
            return 1
    return 0


def _pl_only_flags(args: argparse.Namespace) -> list[str]:
    """
    Task options that have no counterpart in CZ at stage 1.

    They serve to resolve ``--country auto`` (ADR-023 point 5): since the variant
    exists only for PL, the user's intent is unambiguous and it is better to
    pick the country than to reject the whole task. The list is DELIBERATELY narrow:

    * ``--product laz`` does not belong to it despite being PL-only - it has its own
      flow (``_cmd_download_laz``) and never reaches ``_dispatch_area``;
    * ``--resolution 5m`` exists on both sides of the border (PL 5m, DMR 4G);
    * ``--resolution 2m`` and ``--vertical-crs Bpv`` are Czech, so they decide
      at most in the other direction (today: a validation error);
    * a per-country value (``pl=..,cz=..``) names both countries on purpose;
    * ``--system`` is required for every PL area task, so it carries no intent;
    * ``--target-crs`` since ADR-027 works on both sides of the border (PL: a merged
      cutout), so it does not decide the country in either direction;
    * ``--all-campaigns``/``--min-year`` (ADR-030) neither: a PL+CZ area
      downloads CZ in its current version (``_reject_campaign_opts_without_pl``).
    """
    flags: list[str] = []
    product = args.product
    if product in ("nmpt", "orto"):
        flags.append(f"--product {product}")
    if args.vertical_crs == "KRON86":
        flags.append("--vertical-crs KRON86")
    if args.resolution == "1m":
        flags.append("--resolution 1m")
    return flags


def _dispatch_area(
    args: argparse.Namespace, bbox: BBox, filepath: Path | None = None
) -> int:
    """
    Split an area task (bbox or geometry) into countries and run them.

    ``bbox`` is the user's task: the given bbox or the geometry's envelope.
    With ``filepath`` the PL branch keeps working on the file (sheets per feature,
    not from the envelope), and the bbox serves to recognize countries and
    ``parent_request``.

    ``Info:``/``Warning:`` messages about country resolution and partial
    success go to stderr, so ``-q`` (suppressing stdout) does NOT hide them -
    just like ``Error:`` messages.
    """
    from kartograf.transform.crs import TransformError

    country_flag = args.country
    auto = country_flag == "auto"
    countries = _countries_for_bbox(bbox) if auto else (country_flag.upper(),)
    if not countries:
        print(
            "Error: obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)",
            file=sys.stderr,
        )
        return 1
    # ADR-023 point 5 (N6-2): country envelopes are rectangles (point 4), so auto-split
    # pulls CZ in also for tasks lying entirely in Poland - and then an option with no
    # Czech counterpart broke the whole command (`--system 2000` near Racibórz: code 1,
    # a regression vs 0.6.1). Such an option therefore decides the country instead of
    # spoiling the task; from here on it is exactly an explicit `--country pl`
    # (auto=False => no clipping to the envelope). The condition `len(countries) > 1 and
    # "PL" in countries` narrows this to truly disputed areas: an entirely Czech area
    # still gets the message about stage 2 (below); an entirely Polish one needs none.
    if auto and len(countries) > 1 and "PL" in countries:
        pl_only = _pl_only_flags(args)
        if pl_only:
            print(
                f"Info: --country auto -> pl ({', '.join(pl_only)} dotyczy tylko PL)",
                file=sys.stderr,
            )
            auto = False
            countries = ("PL",)
    product = args.product
    # an entirely Czech area: the stage 2 message is more apt than the
    # "choose a country" hint - the country is already resolved
    if countries == ("CZ",) and _reject_non_nmt_for_cz(product):
        return 1
    if _validate_cross_country(args, countries):
        return 1
    # PL cutout + campaign options: the only place of this guard (a PL cutout
    # arises only from here). Here, not in the PL branch - under auto CZ goes BEFORE
    # PL (sorting), so a later guard would come after the CZ download; before the
    # campaign Info, so a rejected task does not get an Info. Countries are
    # already resolved (`_pl_only_flags` above): an area without PL rejects
    # campaign options, a PL+CZ area gets an Info.
    if "PL" in countries and _reject_campaign_opts_with_target_crs(args):
        return 1
    if _reject_campaign_opts_without_pl(args, countries):
        return 1

    parent_request = _build_parent_request(bbox, countries)
    cz_crs = getattr(args, "target_crs", None) or "EPSG:5514"

    # Per-country parts BEFORE any download: transformation errors
    # fail the whole task, and clipping messages (S3) go
    # in one block before the work.
    parts: dict[str, CountryPart] = {}
    for code in countries:
        try:
            parts[code] = _country_bbox(bbox, code, auto=auto, cz_crs=cz_crs)
        except TransformError as e:
            return _print_transform_error(e)
    if auto:
        pl_geometry_sheets = filepath is not None and not getattr(
            args, "target_crs", None
        )
        _print_clipping_info(
            bbox,
            countries,
            parts,
            pl_geometry_sheets=pl_geometry_sheets,
            pl_sheet_list=filepath is None and not getattr(args, "target_crs", None),
        )

    results: list[tuple[str, int]] = []
    for code in countries:
        part = parts[code].bbox
        # A COPY of args per country: each branch narrows --resolution and
        # --vertical-crs to its own country's value (per-country form).
        country_args = argparse.Namespace(**vars(args))
        if code == "CZ":
            rc = _run_cz(country_args, bbox=part, parent_request=parent_request)
        elif filepath is not None:
            rc = _download_pl_geometry(
                country_args, filepath, parent_request, bbox=part
            )
        else:
            rc = _download_pl_bbox(country_args, part, parent_request)
        results.append((code, rc))

    exit_codes = [rc for _, rc in results]
    # A3-2: under `auto` countries are taken from RECTANGULAR envelopes (ADR-023 point
    # 4), so a task deep inside one country routinely hits the other one too, which has
    # no data there - this is a normal result of country selection, not a task failure.
    # Code 0, but with a warning, so that one country's failure in a border strip does
    # not vanish silently. An explicit `--country` (the user pointed out the extent
    # themself) and failure of ALL countries stay with the existing `max(exit_codes)`.
    # The text does not guess the cause: after D2 the PL branch's code 1 means "download
    # error or zero data" (some sheets may have been downloaded), and details stand in
    # the Error above.
    if auto and len(results) > 1 and 0 in exit_codes and max(exit_codes) != 0:
        failed = [code for code, rc in results if rc != 0]
        ok = [code for code, rc in results if rc == 0]
        print(
            f"Warning: czesc {', '.join(failed)} zadania zakonczyla sie bledem "
            f"(patrz Error wyzej) — pobrano {', '.join(ok)}; kod 0 "
            "(prostokatne obwiednie krajow, ADR-023 pkt 4-5)",
            file=sys.stderr,
        )
        return 0
    return max(exit_codes)


def _resolve_cz_geometry_bbox(args: argparse.Namespace) -> BBox | None:
    """
    Envelope of a geometry in the CZ task CRS (None => error already printed).

    CUZK does not accept a geometry file - an area task is one ``exportImage``
    cutout, so the geometry is reduced here to an envelope (as
    in the LAZ flow, except in a Czech CRS instead of EPSG:2180).

    The envelope is computed IN THE FILE'S CRS, and the jump to the target CRS is done
    by ``bbox_to_crs`` (pinned operation + edge sampling). The transformation from
    ``core/geometry`` is unacceptable here: it uses the default pyproj transformer
    (ballpark allowed, unknown accuracy) and a four-corner envelope that, with a rotated
    Krovak, cuts off slivers of the area. A single jump straight to the task CRS also
    means that ``_cz_download_bbox`` does not transform a second time.
    """
    from pyproj import CRS

    from kartograf.core.geometry import get_overall_bbox, read_source_crs
    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.transform.crs import TransformError

    filepath = Path(args.geometry)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return None

    layer = getattr(args, "layer", None)
    image_sr = getattr(args, "target_crs", None) or "EPSG:5514"
    try:
        source_crs = read_source_crs(filepath, layer=layer)
        bbox = get_overall_bbox(filepath, layer=layer, target_crs=source_crs.to_wkt())
        if source_crs == CRS.from_user_input(image_sr):
            # the file is already in the task CRS - only a label, zero transformation
            return BBox(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, image_sr)
        return bbox_to_crs(bbox, image_sr)
    except (ValidationError, TransformError) as e:
        _print_transform_error(e)
        return None


def _geometry_envelope(filepath: Path, layer: str | None) -> BBox:
    """Envelope of a geometry for country dispatch (``--country auto``/``pl``).

    A file in a Czech CRS (EPSG:5514/3045): the envelope IN THE FILE'S CRS labeled with
    the EPSG CODE - the jump to EPSG:2180 will be done by the pinned operation in
    ``_country_bbox`` (review max 2026-08-30, finding 4: the default transformer from
    ``core/geometry`` shifted the result grid by ~1.2 m). A WKT label would not suffice:
    ``wkid()`` does not recognize it and the pinned jump would be skipped. Other CRSs -
    as before, straight to EPSG:2180.
    """
    from kartograf.core.bbox import is_czech_crs
    from kartograf.core.geometry import get_overall_bbox, read_source_crs

    source_crs = read_source_crs(filepath, layer=layer)
    epsg = source_crs.to_epsg()
    if epsg is not None and is_czech_crs(f"EPSG:{epsg}"):
        # envelope in the file's CRS (identity - zero transformation)
        env = get_overall_bbox(filepath, layer=layer, target_crs=source_crs.to_wkt())
        return BBox(env.min_x, env.min_y, env.max_x, env.max_y, f"EPSG:{epsg}")
    return get_overall_bbox(filepath, layer=layer, target_crs="EPSG:2180")


@dataclass
class _PlanContext:
    """Update plan of one ``download`` run, shared by every track.

    ``--check-updates`` collects one plan per track (``plans``) and writes
    them as ONE plan file (``--country auto``: PL and CZ, ``UpdatePlan.merge``);
    ``--upgrade --plan`` reads the file once (``loaded``) and every track
    executes its own positions.
    """

    plans: list[UpdatePlan] = field(default_factory=list)
    loaded: UpdatePlan | None = None


def _plan_context(args: argparse.Namespace) -> _PlanContext:
    """The run's plan context (a bare ``Namespace`` in tests: a fresh one)."""
    ctx = getattr(args, "plan_ctx", None)
    if not isinstance(ctx, _PlanContext):
        ctx = _PlanContext()
        args.plan_ctx = ctx
    return ctx


def run_with_plan_file(
    args: argparse.Namespace, body: Callable[[argparse.Namespace], int]
) -> int:
    """Plan file cycle of a store command (``download``, ``landcover
    download``, ``soilgrids hsg``; spec 4.4).

    ``--upgrade --plan`` reads the plan before any work (``_PlanContext.loaded``);
    ``--check-updates --plan`` writes the plans collected by ``body``
    (``_report_plan``) as ONE file after it. A plan that cannot be read =
    ``Error:``, code 1, no work.
    """
    ctx = _PlanContext()
    args.plan_ctx = ctx
    plan_file = getattr(args, "plan", None)
    if getattr(args, "upgrade", False) and plan_file:
        try:
            ctx.loaded = UpdatePlan.from_json(
                Path(plan_file).read_text(encoding="utf-8")
            )
        except OSError as e:
            print(
                f"Error: nie udalo sie odczytac planu {plan_file}: {e}", file=sys.stderr
            )
            return 1
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    rc = body(args)
    if getattr(args, "check_updates", False) and plan_file and ctx.plans:
        plan = ctx.plans[0]
        for other in ctx.plans[1:]:
            plan = plan.merge(other)
        Path(plan_file).write_text(plan.to_json(), encoding="utf-8")
        print(f"Info: zapisano plan aktualizacji {plan_file}", file=sys.stderr)
    return rc


def cmd_download(args: argparse.Namespace) -> int:
    """
    Execute the download command.

    ``--upgrade --plan`` reads the plan before any work; ``--check-updates
    --plan`` writes the plan of every track of the task after it
    (`run_with_plan_file`).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    return run_with_plan_file(args, _cmd_download)


def _cmd_download(args: argparse.Namespace) -> int:
    """``download`` after the plan file is read (see :func:`cmd_download`)."""
    _cache_warnings_shown.clear()
    has_sheet = args.sheet is not None
    has_bbox = args.bbox is not None
    has_geometry = getattr(args, "geometry", None) is not None

    provided = sum([has_sheet, has_bbox, has_geometry])
    if provided > 1:
        print(
            "Error: Specify only one of: --sheet, --bbox, or --geometry",
            file=sys.stderr,
        )
        return 1

    if provided == 0:
        print(
            "Error: Must specify one of: --sheet, --bbox, or --geometry",
            file=sys.stderr,
        )
        return 1

    # 0.8.0: no data-affecting defaults - every choice is explicit (checked
    # before any network access; values listed in the message)
    if args.product is None:
        print(f"Error: --product wymagane: {PRODUCT_CHOICES}", file=sys.stderr)
        return 1
    if args.output is None:
        print(
            "Error: --output wymagane: katalog wyniku (pliki trafiaja do "
            "<DIR>/<produkt>/<segment>/...)",
            file=sys.stderr,
        )
        return 1
    if not has_sheet and args.country is None:
        print(
            f"Error: --country wymagane z --bbox/--geometry: {COUNTRY_CHOICES}",
            file=sys.stderr,
        )
        return 1
    for raw, flag in (
        (args.resolution, "--resolution"),
        (args.vertical_crs, "--vertical-crs"),
    ):
        syntax_error = _check_country_value_syntax(raw, flag)
        if syntax_error is not None:
            print(f"Error: {syntax_error}", file=sys.stderr)
            return 1

    # --- Per-country dispatch: the sheet code decides the country via the system
    # registry ---
    from kartograf.core.parser_registry import detect_system

    all_campaigns, min_year, max_year = _campaign_opts(args)
    year = getattr(args, "year", None)
    if year is not None and (min_year is not None or max_year is not None):
        print(
            "Error: --year wyklucza sie z --min-year/--max-year "
            "(--year Y to skrot --min-year Y --max-year Y)",
            file=sys.stderr,
        )
        return 1
    if year is not None:
        min_year = max_year = year
    try:
        validate_year_bounds(min_year, max_year)
    except ValidationError as e:
        message = (
            str(e)
            .replace("min_year", "--year" if year is not None else "--min-year")
            .replace("max_year", "--max-year")
        )
        print(f"Error: {message}", file=sys.stderr)
        return 1
    # Year bounds only restrict admissible years; --all-campaigns selects every
    # flight (model A, ADR-032 point 3): the same rule for every product.
    args.min_year, args.max_year = min_year, max_year
    full_sheet = bool(getattr(args, "full_sheet", False))

    # Point-density filtering is LAZ-only, --full-sheet the reverse (ADR-033);
    # every product supports year flags.
    if _reject_laz_only_opts(args) or _reject_full_sheet_for_laz(args):
        return 1

    country_flag = args.country
    product = args.product

    if has_sheet:
        # the registry ends with the pl1992 fallback (always matches, never None)
        system = detect_system(args.sheet)
        system_id = system.id
        system_country = system.country
        if (
            country_flag not in (None, "auto")
            and country_flag.upper() != system_country
        ):
            print(
                f"Error: Godlo '{args.sheet}' nalezy do systemu {system_id} "
                f"(kraj {system_country}), a podano --country {country_flag}",
                file=sys.stderr,
            )
            return 1
        if system_country == "CZ":
            if _reject_non_nmt_for_cz(product):
                return 1
            # a CZ sheet code regardless of `country_flag` (explicit cz or auto)
            if _reject_campaign_opts_without_pl(args, ("CZ",)):
                return 1
            return _run_cz(args)
        try:
            parsed = SheetParser(args.sheet)
        except (ParseError, ValidationError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        if _resolve_pl_options(
            args, sheet_system=parsed.system, sheet_scale=parsed.scale
        ):
            return 1
        if getattr(args, "target_crs", None) is not None:
            print(
                "Error: --target-crs dziala tylko z --bbox/--geometry; --sheet "
                "wyznacza zasieg i uklad produktu (arkusz PL 1:1 w ukladzie "
                "arkusza, arkusz SM5 1:1 w EPSG:5514, kafel TM33 na siatce "
                "EPSG:3045)",
                file=sys.stderr,
            )
            return 1

    # --- LAZ product: a discrete area->WFS->tiles flow (all 3 modes) ---
    if product == "laz":
        return _cmd_download_laz(args)

    # --- Geometry mode ---
    if has_geometry:
        return _cmd_download_geometry(args)

    # --- Bbox mode ---
    if has_bbox:
        return _cmd_download_bbox(args)

    # --- Sheet code mode (validated and resolved above) ---
    output_dir = Path(args.output)
    # the PL options are already resolved (`_resolve_pl_options`)
    vertical_crs = args.vertical_crs
    resolution = args.resolution
    label = _product_label(product, resolution)

    workers = getattr(args, "workers", 4)

    with open_cache(
        True, force=bool(args.force), on_notice=_warn_cache_disabled
    ) as cache:
        provider, storage = _create_provider_and_storage(
            product, output_dir, vertical_crs, resolution, cache=cache
        )
        on_progress = create_progress_callback(args.quiet)
        try:
            manager = DownloadManager(
                output_dir=output_dir,
                provider=provider,
                storage=storage,
                workers=workers,
                all_campaigns=all_campaigns,
                min_year=min_year,
                max_year=max_year,
                full_sheet=full_sheet,
                on_notice=_print_sheet_notice,
            )
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        _info_legacy_campaigns(manager)
        update = _update_mode(args)
        planned = _run_plan_modes(args, manager, _requested_sheets(args))
        if planned is not None:
            return planned

        try:
            if args.scale:
                if not args.quiet:
                    count = manager.count_sheets(args.sheet, args.scale)
                    print(
                        f"Downloading {count} sheets from {args.sheet} to "
                        f"{args.scale} ({label})"
                    )
                    print()
                result = manager.download_hierarchy(
                    args.sheet,
                    args.scale,
                    update=update,
                    on_progress=on_progress,
                )
                return _finish_pl_sheets(
                    result,
                    _result_paths(result),
                    output_dir=output_dir,
                    quiet=args.quiet,
                    all_campaigns=all_campaigns,
                    full_sheet=full_sheet,
                    ranged=min_year is not None or max_year is not None,
                )

            def announce() -> None:
                if not args.quiet:
                    print(f"Downloading {args.sheet} ({label})...")

            parsed = SheetParser(args.sheet)
            expanded = parsed.system != "2000" and parsed.scale != "1:10000"
            if expanded:
                announce()
            result = manager.download_sheet(
                args.sheet,
                update=update,
                on_progress=on_progress,
                on_download=announce,
            )
            paths = _result_paths(result)
            if expanded:
                return _finish_pl_sheets(
                    result,
                    paths,
                    output_dir=output_dir,
                    quiet=args.quiet,
                    all_campaigns=all_campaigns,
                    full_sheet=full_sheet,
                    ranged=min_year is not None or max_year is not None,
                )
            if not args.quiet:
                files = result.files.get(parsed.sheet, ())
                if files:
                    for line in _status_lines(
                        parsed.sheet, files, result.newer.get(parsed.sheet)
                    ):
                        print(line)
                elif paths:
                    print(f"{args.sheet}: {paths[0]}")
            _warn_sheet_sidecars(
                paths,
                result,
                full_sheet=full_sheet,
                all_campaigns=all_campaigns,
                ranged=min_year is not None or max_year is not None,
            )
            _print_better_coverage(result, paths)
            _print_link_outside_range(
                result.link_outside_range, result.full_link_outside_range
            )
            return 0
        except DownloadError as e:
            print(f"{_error_lead(on_progress)}Error: {e}", file=sys.stderr)
            return 1
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


def _result_paths(result: DownloadResult) -> list[Path]:
    """Standard paths of successful sheets, including already-local sheets."""
    if result.files:
        return [files[0].path for files in result.files.values() if files]
    return list(result.succeeded)


def _update_mode(args: argparse.Namespace) -> UpdateMode | None:
    """``update`` of every download track (spec 4.2): ``--upgrade`` /
    ``--force``; ``--check-updates`` never downloads (``_report_plan``)."""
    if getattr(args, "upgrade", False):
        return "upgrade"
    return "force" if args.force else None


def _requested_sheets(args: argparse.Namespace) -> list[str]:
    """Sheets of the sheet-code mode (``--scale``: its descendants)."""
    if args.scale:
        return [
            d.sheet for d in SheetParser(args.sheet).get_all_descendants(args.scale)
        ]
    return [args.sheet]


def _info_legacy_campaigns(manager: DownloadManager) -> None:
    """Spec 4.5: a 0.7.x ``kampanie/`` directory is not used (no migration, D10).

    ``is True``: a manager stand-in (``Mock``) answers with a ``Mock``."""
    if manager.storage.has_legacy_campaigns() is True:
        print(
            "Info: katalog kampanie/ z wersji 0.7.x nie jest uzywany; dane "
            "zostana pobrane ponownie do versions/",
            file=sys.stderr,
        )


_PLAN_TEXT = {
    "current": "aktualne",
    "missing": "do pobrania",
    "unverifiable": "nie da sie sprawdzic bez pobrania",
}


def _plan_line(item: PlanItem) -> str:
    if item.status == "newer":
        signal = item.available_signal or {}
        available = (
            item.available_label or signal.get("etag") or signal.get("last_modified")
        )
        text = f"nowsza: {available} (lokalna {item.local_label})"
    elif item.status == "check_failed":
        text = f"nie udalo sie sprawdzic: {item.error}"
    else:
        text = _PLAN_TEXT[item.status]
        label = item.local_label or item.available_label
        if label:
            text += f" ({label})"
    return f"{item.unit}: {text}"


def _report_plan(
    args: argparse.Namespace,
    plan: UpdatePlan,
    label: Callable[[PlanItem], str] | None = None,
) -> int:
    """``--check-updates``: print the positions (stdout, also with ``-q`` — it
    is the result) and keep the plan for ``--plan`` (written once by
    `run_with_plan_file`). ``label`` names a position in its line (default:
    its unit). A position that could not be checked = code 1."""
    for item in plan.items:
        line = _plan_line(item)
        if label is not None:
            line = f"{label(item)}{line[len(item.unit) :]}"
        print(line)
    _plan_context(args).plans.append(plan)
    return 1 if any(i.status == "check_failed" for i in plan.items) else 0


def _report_stale(stale: Sequence[PlanItem]) -> int:
    """``--upgrade --plan``: positions whose source changed since the plan."""
    for item in stale:
        print(
            f"Error: {item.unit}: zrodlo zmienilo sie od planu "
            f"({item.available_label or item.available_signal}) — sprawdz "
            "ponownie (--check-updates)",
            file=sys.stderr,
        )
    return 1 if stale else 0


def _run_plan_modes(
    args: argparse.Namespace, manager: DownloadManager, sheets: list[str]
) -> int | None:
    """PL sheets: ``--check-updates`` and ``--upgrade --plan`` (spec 4.4).

    ``None`` = neither: the caller downloads. A position that could not be
    checked, a stale position or a failure = code 1 (partial success).
    """
    if getattr(args, "check_updates", False):
        return _report_plan(args, manager.check_sheets(sheets))
    plan = _plan_context(args).loaded
    if not getattr(args, "upgrade", False) or plan is None:
        return None
    report = manager.download_sheets(sheets, update="upgrade", plan=plan)
    if not args.quiet:
        for sheet, files in report.files.items():
            for line in _status_lines(sheet, files, report.newer.get(sheet)):
                print(line)
    rc = _report_stale(report.stale)
    for sheet, message in report.errors.items():
        print(f"Error: {sheet}: {message}", file=sys.stderr)
    return 1 if rc or report.failed else 0


_STATUS_TEXT = {
    "new": "nowa wersja",
    "relabeled": "nowa etykieta",
    "unchanged": "bez zmian",
    "local": "lokalna wersja",
    "reused": "uzyta ponownie",
}


def _status_lines(
    sheet: str, files: Sequence[VersionedFile], newer: str | None
) -> list[str]:
    """Render the selected version of each file of one sheet."""
    lines = []
    for file in files:
        status = file.status
        dirname = file.version_path.parent.name
        label = dirname.rsplit("_", 1)[0] if status != "new" else dirname
        text = f"{sheet}: {_STATUS_TEXT.get(status, status)} {label}"
        if status == "relabeled":
            text += " (ta sama tresc)"
        if status == "local" and newer is not None:
            text += f"; dostepna nowsza {newer} (--upgrade)"
            newer = None
        lines.append(text)
    return lines


def _report_file(
    args: argparse.Namespace,
    unit: str,
    file: VersionedFile | None,
    update: UpdateMode | None,
) -> None:
    """Status line of one file of a track without campaigns (spec 4.2, 4.5).

    A local version without a cheap signal gets ``(bez sprawdzania;
    --check-updates)`` by default and an ``Info:`` about ``--force`` with
    ``--upgrade``; a failed signal check is a ``Warning:`` (stderr, also with
    ``-q``). ``file`` is ``None`` only when a plan skipped the file.
    """
    if file is None:
        return
    unverified = file.unverified or ""
    if unverified.startswith("check_failed"):
        error = unverified.split(":", 1)[1].strip()
        print(
            f"Warning: {unit}: nie udalo sie sprawdzic zrodla ({error}) — uzyto "
            f"lokalnej wersji {file.label}",
            file=sys.stderr,
        )
    unchecked = file.status == "local" and unverified == "none"
    if not args.quiet:
        (line,) = _status_lines(unit, (file,), file.newer)
        if unchecked and update is None:
            line += " (bez sprawdzania; --check-updates)"
        print(line)
    if unchecked and update == "upgrade":
        print(
            f"Info: {unit}: lokalna wersja {file.label} niesprawdzona — zrodlo "
            "bez taniego sygnalu; pobierz ponownie: --force",
            file=sys.stderr,
        )


def _unit_of(path: Path, output_dir: Path) -> str:
    """Unit of a cutout in status lines: its path below ``--output``."""
    try:
        return Path(path).relative_to(output_dir).as_posix()
    except ValueError:
        return str(path)


def _print_version_summary(
    statuses: Sequence[str], failed: int, output_dir: Path
) -> None:
    """Counters of the files of the task (spec 4.5); ``uzyte ponownie`` (HSG,
    D33) only when a derived file was reused."""
    counts = Counter(statuses)
    reused = f"uzyte ponownie: {counts['reused']}, " if counts["reused"] else ""
    print(
        f"Nowe: {counts['new']}, nowa etykieta: {counts['relabeled']}, "
        f"bez zmian: {counts['unchanged']}, lokalne: {counts['local']}, "
        f"{reused}bledy: {failed} ({output_dir})"
    )


def _download_sheet_list(
    manager: DownloadManager,
    sheet_list: list[str],
    update: UpdateMode | None,
    on_progress: Callable[[DownloadProgress], None] | None,
) -> tuple[list[Path], DownloadResult]:
    """Download a PL sheet list and return its standard paths and facts."""
    result = manager.download_sheets(sheet_list, update=update, on_progress=on_progress)
    return _result_paths(result), result


MAX_HINT_LINES = 5


def _print_coverage_hints(result: DownloadResult) -> None:
    """``Info:`` with ``NoCoverageError`` hints (stderr, despite ``-q``).

    The hints are built by the provider (``NoCoverageError.hints``); the CLI only
    relays them: without literal duplicates, in order of first occurrence,
    up to ``MAX_HINT_LINES`` lines; the rest is one line with the number skipped
    (full list in ``DownloadResult.no_coverage_hints``).
    """
    unique = dict.fromkeys(
        h for hints in result.no_coverage_hints.values() for h in hints
    )
    hints = list(unique)
    for hint in hints[:MAX_HINT_LINES]:
        print(f"Info: {hint}", file=sys.stderr)
    rest = len(hints) - MAX_HINT_LINES
    if rest > 0:
        print(
            f"Info: ... i {rest} innych podpowiedzi "
            "(pelna lista: DownloadResult.no_coverage_hints)",
            file=sys.stderr,
        )


def _finish_pl_sheets(
    result: DownloadResult,
    paths: list[Path],
    *,
    output_dir: Path,
    quiet: bool,
    all_campaigns: bool = False,
    full_sheet: bool = False,
    ranged: bool = False,
) -> int:
    """
    Shared summary and exit code of the multi-sheet PL mode (D2/D10).

    Used by ``--bbox``/``--geometry`` (sheet list) and by the sheet code
    mode with a hierarchy (``--scale`` or a sheet code coarser than 1:10000) - the same
    "many files" semantics, the same sea sheets under a 1:50000 sheet code on the
    coast as under a bbox. R5 tolerance as in the cutout:

    - all downloaded/skipped -> 0, silence;
    - >= 1 file, the rest without GUGiK data (``no_coverage``) -> ``Warning:``
      with a list (up to 10 sheet codes), code 0;
    - >= 1 download failure (``hard_failures``: network, server) -> ``Error:``
      with the FULL list and "retry the download", code 1 (plus the ``Warning:`` above,
      when
      there are also sheets without data);
    - 0 files and all without data -> ``Error:``, code 1 (nothing to download,
      consistent with the cutout: ``ValidationError``).

    Sheets from an incomplete newest campaign (sidecar
    ``extra.source.full_sheet: false``) -> ``Warning:`` (E13, ADR-033: which of
    them have a ``full_sheet/`` link), code unchanged.
    ``all_campaigns=True`` or ``full_sheet``: the
    summary counts campaign files (``result.campaign_files``), not sheets.
    ``newest`` sheets
    from a local campaign on an index failure
    (``result.unverified``, I-1) -> ``Warning:``, code unchanged.

    ``Warning:``/``Error:`` go to stderr, so ``-q`` does NOT suppress them.
    """
    _warn_sheet_sidecars(
        paths, result, full_sheet=full_sheet, all_campaigns=all_campaigns, ranged=ranged
    )
    _print_better_coverage(result, paths)
    _print_link_outside_range(result.link_outside_range, result.full_link_outside_range)
    if not quiet:
        # the progress bar ends with "skipped"/"downloading" without a newline
        print()
        for sheet, files in result.files.items():
            for line in _status_lines(sheet, files, result.newer.get(sheet)):
                print(line)
    if not quiet and paths:
        # O-7: with no file and no skip (only gaps/failures) a summary of 0 is noise
        _print_version_summary(
            [file.status for files in result.files.values() for file in files],
            len(result.failed),
            output_dir,
        )
    total = result.total
    hard = result.hard_failures
    missing = result.no_coverage
    if missing and (paths or hard):
        shown = ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
        print(
            f"Warning: GUGiK nie ma danych dla {len(missing)} z {total} arkuszy "
            f"({shown}) — pominiete (skorowidz GUGiK nie ma tych arkuszy dla "
            "wybranego produktu i rozdzielczosci, np. morze, obszar za granica, "
            f"brak NMT 5 m w czesci kraju); pobrano {len(paths)}",
            file=sys.stderr,
        )
        _print_coverage_hints(result)
    if hard:
        print(
            f"Error: {len(hard)} z {total} arkuszy nie pobrano (blad pobrania, "
            f"nie brak danych): {', '.join(hard)} — ponow pobranie",
            file=sys.stderr,
        )
        return 1
    if not paths:
        print(
            f"Error: GUGiK nie ma danych dla zadnego z {total} arkuszy obszaru",
            file=sys.stderr,
        )
        _print_coverage_hints(result)
        return 1
    return 0


def _cmd_download_bbox(args: argparse.Namespace) -> int:
    """
    Handle download command in bbox mode (per-country dispatch).

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments (with args.bbox set)

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    # ValidationError (zly format, NaN, min > max) -> `Error: ...` w main
    return _dispatch_area(args, parse_bbox_arg(args.bbox, args.bbox_crs))


def _read_sheet_sidecar(path: Path) -> dict | None:
    """Sheet sidecar ``<file>.meta.json``; ``None`` if missing/unreadable."""
    sidecar = path.with_name(f"{path.name}.meta.json")
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def _flight_description(flight: dict) -> str:
    """Format a flight's sidecar date, ID, completeness and measured coverage."""
    flight_id = flight["id"]
    date = flight.get("date")
    name = f"{date}_{flight_id}" if isinstance(date, str) else str(flight_id)
    details: list[str] = []
    if flight.get("full_sheet") is True:
        details.append("pelny")
    elif flight.get("full_sheet") is False:
        details.append("niepelny")
    coverage = flight.get("coverage")
    if (
        isinstance(coverage, (int, float))
        and not isinstance(coverage, bool)
        and 0 <= coverage <= 1
    ):
        percent = f"{coverage * 100:.1f}".replace(".", ",").removesuffix(",0")
        details.append(f"pokrycie {percent} %")
    return f"{name} ({', '.join(details)})" if details else name


def _print_better_coverage(result: DownloadResult, paths: list[Path]) -> None:
    """Report older flights with higher coverage; sidecar detail is best-effort."""
    better = result.better_coverage
    if not better:
        return
    print(
        f"Info: dla {len(better)} arkuszy starszy lot z przedzialu ma wieksze "
        "pokrycie niz najnowszy (dowiazanie wskazuje najnowszy):",
        file=sys.stderr,
    )
    shown = dict(sorted(better.items())[:10])
    sidecars = {
        Path(path).stem: _read_sheet_sidecar(Path(path))
        for path in paths
        if Path(path).stem in shown
    }
    for sheet, better_id in shown.items():
        meta = sidecars.get(sheet) or {}
        extra = meta.get("extra")
        if not isinstance(extra, dict):
            extra = {}
        flights = extra.get("flights")
        campaign = extra.get("campaign")
        linked_id = campaign.get("id") if isinstance(campaign, dict) else None
        if isinstance(flights, list):
            linked = next(
                (
                    flight
                    for flight in flights
                    if isinstance(flight, dict) and flight.get("id") == linked_id
                ),
                None,
            )
            older = next(
                (
                    flight
                    for flight in flights
                    if isinstance(flight, dict) and flight.get("id") == better_id
                ),
                None,
            )
        else:
            linked = older = None
        if linked is not None and older is not None:
            detail = (
                f"dowiazanie {_flight_description(linked)}; "
                f"wieksze pokrycie: {_flight_description(older)}"
            )
        else:
            detail = f"wieksze pokrycie: lot {better_id} (brak szczegolow w sidecarze)"
        print(f"  {sheet}: {detail}", file=sys.stderr)
    if len(better) > len(shown):
        print(f"  ... i {len(better) - len(shown)} innych", file=sys.stderr)


def _campaign_dirname(path: Path) -> str:
    """``<date>_<id>`` label of a version file ``<label>_<sha8>/<file>``; else
    the file name."""
    path = Path(path)
    if "versions" in path.parts and "_" in path.parent.name:
        return path.parent.name.rsplit("_", 1)[0]
    return path.name


def _print_link_outside_range(
    outside: dict[str, Path], full_outside: dict[str, Path] | None = None
) -> None:
    """Report links still pointing at a flight outside the request.

    ADR-032 point 3 (U15): the link never moves back to an older campaign, so
    after a year-bounded request it may keep the previously downloaded flight.
    The same holds for the ``full_sheet/`` link (ADR-033): one line per sheet
    and tree.
    """
    rows = sorted(
        [(sheet, "sciezka standardowa", t) for sheet, t in outside.items()]
        + [(sheet, "full_sheet/", t) for sheet, t in (full_outside or {}).items()]
    )
    if not rows:
        return
    print(
        f"Info: {len(rows)} dowiazan wskazuje lokalny lot spoza tego zadania "
        "(dowiazanie nigdy nie cofa sie na starszy lot); pobrane loty sa "
        "w <segment>/versions/:",
        file=sys.stderr,
    )
    for sheet, tree, target in rows[:10]:
        print(
            f"  {sheet}: {tree} -> dowiazanie {_campaign_dirname(target)}",
            file=sys.stderr,
        )
    if len(rows) > 10:
        print(f"  ... i {len(rows) - 10} innych", file=sys.stderr)


def _is_partial_sheet(path: Path) -> bool:
    """The sheet sidecar declares an incomplete sheet (``extra.source.full_sheet``
    ``false``, E13). Best-effort: missing/unreadable sidecar = ``False``."""
    try:
        source = (_read_sheet_sidecar(path) or {})["extra"]["source"]
        return source.get("full_sheet") is False
    except (KeyError, TypeError, AttributeError):
        return False


def _sheet_crs_mismatch(path: Path) -> tuple[str, str, str] | None:
    """E17: ``(sheet code, sheet code CRS, file CRS)`` when a PL sheet sidecar has a
    ``horizontal_crs`` (the FILE's CRS, ``pl_sheet_horizontal_crs``) different from what
    the sheet code implies - e.g. a PL-2000 zone 7 sheet published by GUGiK
    in EPSG:2180 coordinates. Best-effort: missing sidecar/sheet code = ``None``."""
    meta = _read_sheet_sidecar(path)
    if meta is None or meta.get("country") != "PL":
        return None
    request = meta.get("request")
    sheet = request.get("sheet") if isinstance(request, dict) else None
    actual = meta.get("horizontal_crs")
    if not isinstance(sheet, str) or not isinstance(actual, str):
        return None
    try:
        expected = horizontal_crs_for_sheet(sheet)
    except KartografError:
        return None
    if expected == actual:
        return None
    return sheet, expected, actual


def _warn_crs_mismatch_sheets(paths) -> None:
    """E17: ``Warning:`` about sheets whose file is in a different CRS than
    the sheet code/index record declares. Exit code unchanged; the sidecar describes
    the FILE's CRS. Reads sidecars, so it repeats on skip."""
    found = [m for m in (_sheet_crs_mismatch(Path(p)) for p in paths) if m]
    if not found:
        return
    found.sort()
    shown = ", ".join(
        f"{sheet} (godlo: {expected}, plik: {actual})"
        for sheet, expected, actual in found[:10]
    ) + (" ..." if len(found) > 10 else "")
    print(
        f"Warning: {len(found)} arkuszy GUGiK opublikowano w innym ukladzie "
        f"niz wskazuje godlo: {shown} — sidecar opisuje uklad pliku "
        "(horizontal_crs); deklaracja rekordu w extra.source.declared_crs",
        file=sys.stderr,
    )


def _warn_sheet_sidecars(
    paths,
    result: DownloadResult,
    *,
    full_sheet: bool,
    all_campaigns: bool,
    ranged: bool,
) -> None:
    """CLI warnings from the result sheets' sidecars: incomplete sheet (E13)
    and file CRS different from the sheet code's (E17)."""
    _warn_partial_sheets(
        paths, result, full_sheet=full_sheet, all_campaigns=all_campaigns, ranged=ranged
    )
    _warn_crs_mismatch_sheets(paths)


def _sheets_text(sheets: list[str]) -> str:
    return ", ".join(sheets[:10]) + (" ..." if len(sheets) > 10 else "")


def _warn_partial_sheets(
    paths,
    result: DownloadResult,
    *,
    full_sheet: bool,
    all_campaigns: bool,
    ranged: bool,
) -> None:
    """E13: ``Warning:`` about sheets from an incomplete newest GUGiK campaign.

    The selection rule (ADR-028: newest campaign, no preference for a full
    sheet) stays - the warning only makes it visible. Reads the sidecars of
    result files, so it also works for sheets skipped as existing. One
    ``Warning:`` splits the sheets (ADR-033): with a ``full_sheet/`` link
    (``result.full_links``), without a full flight in the index
    (``result.without_full``; with ``all_campaigns=True`` every flight of the
    range is local, so no link means none; ``ranged`` limits that claim to
    the year bounds), and the rest — not downloaded, with the
    ``--full-sheet`` hint unless the flag was given.
    """
    partial = sorted(Path(p).stem for p in paths if _is_partial_sheet(Path(p)))
    if not partial:
        return
    linked = [g for g in partial if g in result.full_links]
    rest = [g for g in partial if g not in result.full_links]
    absent = [g for g in rest if g in result.without_full or all_campaigns]
    missing = [g for g in rest if g not in absent]
    groups = []
    if linked:
        groups.append(f"pelny lot w <segment>/full_sheet/: {_sheets_text(linked)}")
    if absent:
        scope = " w zakresie lat zadania" if ranged else ""
        groups.append(f"brak pelnego lotu w skorowidzu{scope}: {_sheets_text(absent)}")
    if missing:
        hint = "" if full_sheet else " — uzyj --full-sheet"
        groups.append(f"pelny lot nie pobrany: {_sheets_text(missing)}{hint}")
    print(
        f"Warning: najnowsza kampania GUGiK jest niepelna dla {len(partial)} "
        "arkuszy — skorowidz deklaruje arkusz nie w calosci wypelniony "
        "trescia; plik w sciezce standardowej moze miec duzo nodata/czerni "
        "(extra.source.full_sheet w sidecarze); " + "; ".join(groups),
        file=sys.stderr,
    )


def _download_pl_cutout(
    args: argparse.Namespace,
    bbox: BBox,
    parent_request: dict,
) -> int:
    """Polish --target-crs cutout from GUGiK WCS (ADR-035): a CLI overlay on
    ``download/cutout.py``.

    Called after ``_resolve_pl_options`` (nmt/nmpt, 1m only). ``bbox`` is
    the request or the ``--geometry`` envelope. Preparation errors
    (``TransformError``/``ValidationError``) and EVERY download or build
    error (PRG, WCS) end with code 1 and a message, not a traceback: an
    exception leaking out of the country loop of ``_dispatch_area`` would break
    the partial success contract (ADR-023 points 4-5). ``--force`` fetches a
    new version; by default a local version is reused. ``--workers`` and
    ``--scale`` have no effect. An all-nodata cutout = ``Warning:``, code 0.
    """
    from kartograf.download.cutout import prepare_pl_cutout, run_pl_wcs_cutout
    from kartograf.transform.crs import TransformError

    product = args.product
    output_dir = Path(args.output)
    try:
        # fail-fast: the pinned operation is built BEFORE any network access
        cutout = prepare_pl_cutout(
            bbox,
            args.target_crs,
            output_dir=output_dir,
            vertical_crs=args.vertical_crs,
            product=product,
        )
    except TransformError as e:
        return _print_transform_error(e)
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    provider, _storage = _create_provider_and_storage(
        product, output_dir, args.vertical_crs, args.resolution
    )
    if getattr(args, "check_updates", False):
        from kartograf.download.cutout import check_pl_cutout

        return _report_plan(args, check_pl_cutout(cutout))
    chunks = len(provider.plan_wcs_chunks(cutout.bbox_source_2180))
    fetching = args.force or not cutout.target_path.exists()
    if fetching and (chunks > 1 or cutout.estimated_bytes >= 2**30):
        # stderr, not stdout: -q does NOT suppress Info:/Warning:
        height, width = cutout.grid_shape
        print(
            f"Info: wycinek {width} x {height} px float32 "
            f"(~{cutout.estimated_bytes / 2**20:.0f} MiB), {chunks} zapytan WCS "
            "GUGiK pobieranych po kolei",
            file=sys.stderr,
        )
    update = _update_mode(args)
    try:
        result = run_pl_wcs_cutout(
            cutout,
            provider=provider,
            update=update,
            plan=_plan_context(args).loaded,
            parent_request=parent_request,
        )
    except Exception as e:  # noqa: BLE001 — code 1 instead of a traceback (ADR-023)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if result.all_nodata and result.file is not None and result.file.status != "local":
        print(
            "Warning: wycinek w calosci nodata — obszar poza ladem PL (maska PRG: "
            "granica panstwa bez morza terytorialnego i wod wewnetrznych)",
            file=sys.stderr,
        )
    _report_file(args, _unit_of(cutout.target_path, output_dir), result.file, update)
    return _report_stale(result.stale)


def _download_pl_bbox(
    args: argparse.Namespace, bbox: BBox, parent_request: dict
) -> int:
    """
    Polish part of a bbox task: GUGiK sheets with sidecars carrying the parent.

    ``args`` is a COPY of the task namespace (see ``_dispatch_area``) - sentinels
    are resolved here so as not to touch the arguments going to CZ.

    ``bbox`` is already in a Polish CRS: tasks given in a Czech CRS are
    normalized by ``_country_bbox`` with the pinned operation (a second, unpinned
    Krovak jump here would be exactly what the stage forbids).

    With ``--target-crs`` (ADR-035) - ``_download_pl_cutout`` (library
    ``download/cutout.py``): one cutout from GUGiK WCS instead of a sheet list.
    Without it - a sheet list with R5 tolerance (``_finish_pl_sheets``, D2).
    """
    if _resolve_pl_options(args):
        return 1
    if args.target_crs is not None:
        return _download_pl_cutout(args, bbox, parent_request)

    target_scale = _pl_target_scale(args)

    # Find sheets covering the bbox (no network, no cache)
    try:
        sheet_list = find_sheets_for_bbox(bbox, target_scale, system=args.system)
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not sheet_list:
        print("Error: No sheets found for the given bbox", file=sys.stderr)
        return 1

    return _download_pl_sheet_list(
        args, sheet_list, parent_request, what="bbox", target_scale=target_scale
    )


def _download_pl_sheet_list(
    args: argparse.Namespace,
    sheet_list: list[str],
    parent_request: dict,
    *,
    what: str,
    target_scale: str,
) -> int:
    """PL sheet list mode (bbox/geometry without ``--target-crs``): manager + finish.

    The PL options are already resolved (``_resolve_pl_options``).
    ``MetadataCache`` lives only for the duration of the task (N6).
    """
    output_dir = Path(args.output)
    vertical_crs = args.vertical_crs
    resolution = args.resolution
    product = args.product
    workers = getattr(args, "workers", 4)
    update = _update_mode(args)
    all_campaigns, min_year, max_year = _campaign_opts(args)
    full_sheet = bool(getattr(args, "full_sheet", False))

    if not args.quiet:
        _print_sheet_list(
            sheet_list,
            target_scale,
            what=what,
            label=_product_label(product, resolution),
        )

    with open_cache(
        True, force=bool(args.force), on_notice=_warn_cache_disabled
    ) as cache:
        provider, storage = _create_provider_and_storage(
            product, output_dir, vertical_crs, resolution, cache=cache
        )
        on_progress = create_progress_callback(args.quiet)
        try:
            manager = DownloadManager(
                output_dir=output_dir,
                provider=provider,
                storage=storage,
                workers=workers,
                sidecar_extra={"parent_request": parent_request},
                all_campaigns=all_campaigns,
                min_year=min_year,
                max_year=max_year,
                full_sheet=full_sheet,
                on_notice=_print_sheet_notice,
            )
            _info_legacy_campaigns(manager)
            planned = _run_plan_modes(args, manager, sheet_list)
            if planned is not None:
                return planned
            all_paths, result = _download_sheet_list(
                manager, sheet_list, update, on_progress
            )
        except DownloadError as e:
            print(f"{_error_lead(on_progress)}Error: {e}", file=sys.stderr)
            return 1
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    return _finish_pl_sheets(
        result,
        all_paths,
        output_dir=output_dir,
        quiet=args.quiet,
        all_campaigns=all_campaigns,
        full_sheet=full_sheet,
        ranged=min_year is not None or max_year is not None,
    )


def _resolve_laz_bbox(args: argparse.Namespace) -> BBox | None:
    """
    Resolve a sheet code / --bbox / --geometry input to an EPSG:2180 BBox for LAZ.

    Returns None (after printing an error) if a geometry file is missing or its
    layer is invalid. Raises ParseError / ValidationError on invalid input.
    """
    if getattr(args, "geometry", None):
        from kartograf.core.geometry import get_overall_bbox

        if not _announce_geometry_layer(args):
            return None
        return get_overall_bbox(
            Path(args.geometry), layer=args.layer, target_crs="EPSG:2180"
        )

    if args.bbox is not None:
        bbox = parse_bbox_arg(args.bbox, args.bbox_crs)
        from kartograf.core.bbox import is_czech_crs, transform_bbox

        if is_czech_crs(bbox.crs):
            # A Czech CRS (Krovak/UTM33N) is left ONLY via the pinned
            # operation (like _country_bbox) - an unpinned pyproj transformer
            # (ballpark, unknown accuracy) would risk a wrong selection of LAZ
            # tiles on the border strip.
            from kartograf.providers.cuzk.dmr import bbox_to_crs

            return bbox_to_crs(bbox, "EPSG:2180")
        return transform_bbox(bbox, "EPSG:2180")

    # sheet code mode - SheetParser validates and transforms to EPSG:2180
    return SheetParser(args.sheet).get_bbox(crs="EPSG:2180")


def _laz_parent_request(args: argparse.Namespace, bbox: BBox) -> dict | None:
    """``extra.parent_request`` of LAZ tiles (ADR-023 (f).1, review-2 N15).

    Only ``--bbox``/``--geometry`` mode (sheet code: ``None``). As in the other
    paths: ``--bbox`` in the GIVEN CRS (before transformation to EPSG:2180),
    ``--geometry`` as an EPSG:2180 envelope; ``countries`` = ``["PL"]`` - LAZ
    queries GUGiK only.
    """
    if args.sheet is not None:
        return None
    if args.bbox is not None:
        parts = [float(x.strip()) for x in args.bbox.split(",")]
        bbox = BBox(parts[0], parts[1], parts[2], parts[3], args.bbox_crs)
    return _build_parent_request(bbox, ("PL",))


def _laz_tile_label(tile) -> str:
    return f"{tile.sheet} ({tile.year}, {tile.crs})"


def _print_laz_superseded(superseded) -> None:
    """``Info:`` about tiles skipped during selection (stderr, also with ``-q``)."""
    if not superseded:
        return
    print(
        f"Info: pominieto {len(superseded)} kafli LAZ — obszar pokrywaja "
        "nowsze kafle (domyslnie najnowszy rocznik per obszar; inny "
        "rocznik: --year/--min-year/--max-year)",
        file=sys.stderr,
    )
    for entry in superseded:
        if entry.covered_by:
            covering = ", ".join(_laz_tile_label(t) for t in entry.covered_by)
            reason = f"pokryty przez {covering}"
        else:
            reason = "rama kafla nie przecina obszaru (tylko obwiednia WFS)"
        print(f"  {_laz_tile_label(entry.tile)}: {reason}", file=sys.stderr)


def _cmd_download_laz(args: argparse.Namespace) -> int:
    """
    Handle the download command for the LAZ product (area-based via WFS).

    Accepts the same inputs as the other products — a sheet code (down to 1:10000),
    --bbox/--bbox-crs, or --geometry/--layer — resolves them to an EPSG:2180
    bbox and hands the work to the library (``kartograf.download.laz``):
    ``GugikLazProvider.select_tiles`` (newest tile per area) and
    ``run_laz_download`` (parallel download, sidecars, failures). This
    function only prints and maps the result to an exit code.
    """
    from kartograf.download.laz import NO_TILES_MESSAGE, run_laz_download
    from kartograf.providers.pl.gugik_laz import GugikLazProvider

    # a CZ sheet code + laz is dropped already at dispatch; what remains here is an
    # explicit --country cz in area mode (LAZ skips cmd_download's bbox/geometry
    # branches)
    if args.country == "cz":
        print(_CZ_ONLY_NMT_MSG.format(product="laz"), file=sys.stderr)
        return 1
    all_campaigns, min_year, max_year = _campaign_opts(args)
    if _resolve_pl_options(args):
        return 1

    try:
        bbox = _resolve_laz_bbox(args)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if bbox is None:
        return 1  # error already printed

    # area mode: LAZ exists only for PL, so an area reaching into CZ
    # would be downloaded silently and only partially (spec 5.7: no silent skipping
    # of a country). A PL sheet code unambiguously points to the country - no guard.
    if (
        args.country == "auto"
        and args.sheet is None
        and "CZ" in _countries_for_bbox(bbox)
    ):
        print(
            "Error: --product laz jest dostepny tylko dla PL, a obszar "
            "przecina CZ (LAZ dla CZ: etap 2); uzyj jawnie --country pl",
            file=sys.stderr,
        )
        return 1

    vertical_crs = args.vertical_crs
    min_density = getattr(args, "min_density", None)
    workers = getattr(args, "workers", 4) or 1
    output_dir = Path(args.output)
    quiet = args.quiet

    provider = GugikLazProvider(vertical_crs=vertical_crs)

    if not quiet:
        print(f"Querying GUGiK WFS for LAZ tiles ({vertical_crs})...")
    try:
        selection = provider.select_tiles(
            bbox,
            min_density=min_density,
            all_campaigns=all_campaigns,
            min_year=min_year,
            max_year=max_year,
        )
    except (ValidationError, DownloadError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    _print_laz_superseded(selection.superseded)
    if not selection.tiles:
        # N7: discovery passed (all vintages answered), so an empty
        # list means extent/filters, not a WFS failure
        print(f"Error: {NO_TILES_MESSAGE}", file=sys.stderr)
        return 1

    if getattr(args, "check_updates", False):
        from kartograf.download.laz import check_laz_updates

        return _report_plan(
            args,
            check_laz_updates(selection, provider=provider, output_dir=output_dir),
        )

    total = len(selection.tiles)
    if not quiet:
        print(f"Found {total} LAZ tiles. Downloading with {workers} worker(s)...")
        print()

    def _progress(done: int, count: int) -> None:
        if not quiet:
            print(f"\r  {done}/{count} tiles", end="", flush=True)

    update = _update_mode(args)
    result = run_laz_download(
        selection,
        provider=provider,
        bbox=bbox,
        output_dir=output_dir,
        min_density=min_density,
        all_campaigns=all_campaigns,
        min_year=min_year,
        max_year=max_year,
        max_workers=workers,
        update=update,
        plan=_plan_context(args).loaded,
        on_progress=_progress,
        parent_request=_laz_parent_request(args, bbox),
    )

    if not quiet:
        print()
    for file in result.files:
        _report_file(args, file.path.name, file, update)
    if not quiet:
        _print_version_summary(
            [file.status for file in result.files],
            len(result.failed),
            output_dir / "laz",
        )
    stale = _report_stale(result.stale)
    if result.failed:
        # Code 1 => `Error:` (convention: `Warning:` only with code 0) and the FULL
        # list of failed tiles to retry - model `_finish_pl_sheets` (N6).
        names = ", ".join(f.tile.sheet for f in result.failed)
        print(
            f"Error: {len(result.failed)} z {total} kafli LAZ nie pobrano "
            f"(blad pobrania): {names} — ponow pobranie",
            file=sys.stderr,
        )
        for failure in result.failed:
            print(f"  {failure.tile.sheet}: {failure.error}", file=sys.stderr)
        return 1

    return stale


@contextlib.contextmanager
def _library_log_muted(name: str) -> Iterator[None]:
    """Mute one library logger while the CLI prints the same message itself."""
    import logging

    log = logging.getLogger(name)
    previous = log.disabled
    log.disabled = True
    try:
        yield
    finally:
        log.disabled = previous


def _cz_download_sheet(args: argparse.Namespace, provider) -> int:
    """CZ sheet code: TM33 tile (exportImage) or SM5 sheet (openzu).

    Implementation: ``download.cz_sheets.run_cz_sheet`` / ``check_cz_sheet``.
    """
    from kartograf.download.cz_sheets import check_cz_sheet, run_cz_sheet

    sheet = args.sheet
    if getattr(args, "check_updates", False):
        try:
            plan = check_cz_sheet(provider, sheet, output_dir=args.output)
        except (DownloadError, ValidationError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return _report_plan(args, plan)

    def announce() -> None:
        # O-3: only when the transfer really starts (after the provider's
        # validations: SM5 sheet index, TM33 grid parse)
        if not args.quiet:
            print(f"Downloading {sheet} (CZ, resolution: {provider.resolution})...")

    update = _update_mode(args)
    try:
        with _library_log_muted("kartograf.download.cz_sheets"):
            result = run_cz_sheet(
                provider,
                sheet,
                output_dir=args.output,
                update=update,
                plan=_plan_context(args).loaded,
                on_download=announce,
            )
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    _warn_cz_all_nodata(result.file, result.all_nodata)
    _report_file(args, sheet, result.file, update)
    return _report_stale(result.stale)


def _warn_cz_all_nodata(file: VersionedFile | None, all_nodata: bool) -> None:
    """N2: ``Warning:`` when a downloaded CZ raster has no valid pixel (code 0)."""
    if all_nodata and file is not None and file.status != "local":
        print(
            f"Warning: {file.path} jest w calosci nodata — obszar poza pokryciem "
            "DMR CUZK (poza granica CZ?)",
            file=sys.stderr,
        )


def _cz_download_bbox(
    args: argparse.Namespace,
    provider,
    bbox: BBox,
    parent_request: dict | None,
) -> int:
    """CZ bbox: one `exportImage` cutout in `<subdir>/bbox/<coords>.tif`.

    The bbox is normalized to the RESULT's CRS (`--target-crs` or native
    5514) - the file name carries the coordinates of the actually requested cutout.
    The request then goes to the server in the native CRS, and the local
    warp in the provider moves it onto the result grid (ADR-024).

    Implementation: ``download.cz_cutout.run_cz_cutout`` / ``check_cz_cutout``.
    """
    from kartograf.download.cz_cutout import check_cz_cutout, run_cz_cutout

    image_sr = args.target_crs or "EPSG:5514"
    if getattr(args, "check_updates", False):
        plan = check_cz_cutout(
            provider, bbox, output_dir=args.output, image_crs=args.target_crs
        )
        return _report_plan(args, plan)

    def announce() -> None:
        # O-3: printed by the provider right before the first exportImage
        if not args.quiet:
            print(f"Downloading CZ bbox ({provider.resolution}, {image_sr})...")

    update = _update_mode(args)
    try:
        # the CLI prints its own 'Warning:' line - the library log would
        # repeat it on stderr (logging.lastResort; the CLI configures no logging)
        with _library_log_muted("kartograf.download.cz_cutout"):
            result = run_cz_cutout(
                provider,
                bbox,
                output_dir=args.output,
                image_crs=args.target_crs,
                update=update,
                plan=_plan_context(args).loaded,
                parent_request=parent_request,
                on_download=announce,
            )
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    _warn_cz_all_nodata(result.file, result.all_nodata)
    if result.file is not None:
        unit = _unit_of(result.file.path, Path(args.output))
        _report_file(args, unit, result.file, update)
    return _report_stale(result.stale)


def _cmd_download_cz(
    args: argparse.Namespace,
    bbox: BBox | None = None,
    parent_request: dict | None = None,
) -> int:
    """
    Handle the download command for Czech (CUZK) sources.

    Model: :func:`_cmd_download_laz` - a flow outside ``DownloadManager``, because a
    CZ task yields exactly one file (a TM33 tile, an SM5 sheet or an
    `exportImage` cutout); the library writes its versioned sidecar.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments (sheet code / --bbox / --target-crs / --resolution ...).
    bbox : BBox, optional
        Bbox of area mode (``_dispatch_area`` always passes it, also
        with an explicit ``--country cz``); ``None`` = sheet code mode (``args.sheet``).
    parent_request : dict, optional
        The user's original task before the per-country split; goes to the sidecar's
        ``extra.parent_request``.

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)

    Raises
    ------
    ValidationError
        When ``--target-crs`` accompanies a sheet code (the sheet code determines the
        extent and CRS of the product: an SM5 sheet 1:1 in EPSG:5514, a TM33 tile by a
        local warp onto the EPSG:3045 grid). Translated by ``_run_cz`` (called from
        ``cmd_download`` and ``_dispatch_area``) - as the other flows treat
        ValidationError.
    """
    from kartograf.core.parser_registry import detect_system
    from kartograf.providers.cuzk import create_dmr_provider
    from kartograf.transform.crs import TransformError

    has_sheet = bbox is None
    # An SM5 sheet is a ready-made DMR 4G file that exists only at 5 m, so the
    # sheet itself determines the resolution; TM33 tiles and bbox cutouts are
    # cut from the service, where 2 m and 5 m are a real (required) choice.
    is_sm5 = has_sheet and detect_system(args.sheet).id == "cz_sm5"
    # an `auto` area task was validated for all its countries in
    # `_dispatch_area` (there --system may belong to the PL part)
    countries = ("CZ",) if has_sheet or args.country == "cz" else ("CZ", "PL")
    error = _cz_option_error(args, is_sm5=is_sm5, countries=countries)
    if error is not None:
        # rejected before the provider (no network) and before "Downloading"
        print(f"Error: {error}", file=sys.stderr)
        return 1
    resolution = _country_value(args.resolution, "CZ") or "5m"  # only SM5 omits it
    vertical_crs = _country_value(args.vertical_crs, "CZ")
    assert vertical_crs is not None  # required: checked by _cz_option_error
    args.resolution, args.vertical_crs = resolution, vertical_crs
    if has_sheet and args.target_crs is not None:
        # the provider ignores target_crs in sheet code mode - silence would be a lie
        raise ValidationError(
            "--target-crs dziala tylko z --bbox/--geometry; --sheet wyznacza "
            "zasieg i uklad produktu (arkusz SM5 1:1 w EPSG:5514, kafel TM33 "
            "na siatce EPSG:3045)"
        )

    # D16: --force as in the PL path - the cache read (SM5 sheet index)
    # is skipped, the fresh entry is written.
    with open_cache(
        True, force=bool(args.force), on_notice=_warn_cache_disabled
    ) as cache:
        try:
            provider = create_dmr_provider(
                resolution=resolution,
                cache=cache,
                target_crs=None if has_sheet else args.target_crs,
                vertical_crs=vertical_crs,
            )
        except TransformError as e:
            return _print_transform_error(e)
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if bbox is None:
            return _cz_download_sheet(args, provider)
        return _cz_download_bbox(args, provider, bbox, parent_request)


def _cmd_download_geometry(args: argparse.Namespace) -> int:
    """
    Handle download command in geometry mode (per-country dispatch).

    An explicit ``--country cz`` goes through ``_resolve_cz_geometry_bbox``
    (envelope in the FILE's CRS + one pinned-operation jump). The auto mode
    and ``--country pl`` compute the envelope via ``_geometry_envelope``: a file
    in a Czech CRS (EPSG:5514/3045) stays in the FILE's CRS (EPSG label)
    and leaves Krovak only in ``_country_bbox`` via the pinned operation,
    other CRSs compute the envelope straight in EPSG:2180 as before. The result
    decides the countries and goes to ``parent_request``, while PL sheets are still
    determined by the geometry itself (per feature), not by its envelope.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments (with args.geometry set)

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    if args.country == "cz":
        if _reject_non_nmt_for_cz(args.product):
            return 1
        # this branch bypasses `_dispatch_area` - the campaign guard here too
        if _reject_campaign_opts_without_pl(args, ("CZ",)):
            return 1
        # after the option guards (no file I/O before them), before any reader
        if not _announce_geometry_layer(args):
            return 1
        bbox = _resolve_cz_geometry_bbox(args)
        if bbox is None:
            return 1  # error already printed
        return _run_cz(
            args, bbox=bbox, parent_request=_build_parent_request(bbox, ("CZ",))
        )

    if not _announce_geometry_layer(args):
        return 1
    filepath = Path(args.geometry)

    try:
        overall = _geometry_envelope(filepath, getattr(args, "layer", None))
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return _dispatch_area(args, overall, filepath=filepath)


def _download_pl_geometry(
    args: argparse.Namespace,
    filepath: Path,
    parent_request: dict,
    bbox: BBox,
) -> int:
    """
    Polish part of a geometry task (sheets per feature, not from the envelope).

    ``args`` is a COPY of the task namespace - see ``_dispatch_area``.

    ``bbox`` - the envelope of the PL task (clipped under auto), required. With
    ``--target-crs`` (ADR-035) - ``_download_pl_cutout`` (library
    ``download/cutout.py``): the cutout covers the WHOLE envelope of the
    geometry, without masking to its features (WCS area = the envelope). Without
    ``--target-crs`` the sheets are determined by the geometry itself and ``bbox`` is
    not used; the list goes through ``_download_pl_sheet_list`` (R5 tolerance, D2).
    """
    from kartograf.core.geometry import find_sheets_for_geometry

    if _resolve_pl_options(args):
        return 1
    if args.target_crs is not None:
        return _download_pl_cutout(args, bbox, parent_request)

    target_scale = _pl_target_scale(args)
    layer = getattr(args, "layer", None)

    try:
        sheet_list = find_sheets_for_geometry(
            filepath, target_scale=target_scale, layer=layer, system=args.system
        )
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not sheet_list:
        print("Error: No sheets found for the given geometry", file=sys.stderr)
        return 1

    return _download_pl_sheet_list(
        args,
        sheet_list,
        parent_request,
        what=f"geometry {filepath.name}",
        target_scale=target_scale,
    )
