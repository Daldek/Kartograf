"""
``kartograf download`` command (sheet code / bbox / geometry / LAZ modes).
"""

import argparse
import contextlib
import json
import math
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from kartograf.cli._parser import parse_bbox_arg
from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox
from kartograf.download.campaigns import validate_campaign_args
from kartograf.download.countries import EDGES as _EDGES
from kartograf.download.countries import CountryPart
from kartograf.download.countries import bbox_to_wgs84 as _bbox_to_wgs84
from kartograf.download.countries import countries_for_bbox as _countries_for_bbox
from kartograf.download.countries import country_bbox as _country_bbox
from kartograf.download.cz_cutout import read_tif_nodata as _read_tif_nodata
from kartograf.download.cz_cutout import write_cz_sidecar as _write_cz_sidecar
from kartograf.download.manager import (
    DownloadManager,
    DownloadProgress,
    DownloadResult,
    SheetFetch,
)
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    ParseError,
    ValidationError,
)
from kartograf.providers.pl import require_nmt_vertical_crs
from kartograf.sources.registry import horizontal_crs_for_godlo

if TYPE_CHECKING:
    from kartograf.cache import MetadataCache


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
            f"{status_icon} {progress.godlo}"
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
    index (skorowidz) records are read and written exclusively via the cache (N6; CLI:
    ``--force`` = cache in ``refresh`` mode, see ``_pl_metadata_cache``).

    LAZ has a separate flow (`_cmd_download_laz`) and never reaches this
    helper — `cmd_download` short-circuits it before any provider is built.
    """
    from kartograf.download.storage import storage_for_provider

    if product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider = GugikNmptProvider(vertical_crs=vertical_crs, cache=cache)
    elif product == "orto":
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        provider = GugikOrtoProvider(cache=cache)
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


def _warn_cache_disabled(message: str) -> None:
    """``on_disabled`` of the CLI ``MetadataCache``: one ``Warning:`` on stderr.

    The library reports the disabled cache once per instance; the CLI
    prints it right away (the download goes on without the cache, so the
    exit code follows the download result) and once per command.
    """
    if message in _cache_warnings_shown:
        return
    _cache_warnings_shown.add(message)
    print(f"Warning: {message}", file=sys.stderr, flush=True)


def _cli_metadata_cache(force: bool) -> "MetadataCache":
    """``MetadataCache`` in the cwd for the CLI (``--force`` = refresh mode)."""
    from kartograf.cache import MetadataCache

    return MetadataCache(refresh=force, on_disabled=_warn_cache_disabled)


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


@contextlib.contextmanager
def _pl_metadata_cache(args: argparse.Namespace) -> Iterator[object | None]:
    """
    ``MetadataCache`` of the PL path for the duration of one task (N6; model: the CZ
    path).

    ``--force`` = ``MetadataCache(refresh=True)`` (E14): index records are NOT read, but
    the freshly chosen record (and a confirmed no coverage) is WRITTEN - the next run
    without ``--force`` gets the new record, not the old one from before a campaign
    change (until the 7-day TTL expires). The cache is opened in the cwd and closed
    after the task (``close()`` purges expired entries).
    """
    cache = _cli_metadata_cache(bool(args.force))
    try:
        yield cache
    finally:
        cache.close()


def _product_label(product: str, resolution: str | None) -> str:
    """Task label in messages: orto has no resolution (K5)."""
    if product == "orto":
        return "product: orto"
    return f"resolution: {resolution}"


def _print_sheet_list(
    godla: list[str], target_scale: str, *, what: str, label: str
) -> None:
    """Header of the PL sheet list (cutout and list mode, D15): up to 10 sheet codes
    in full, a longer list as the first 3 + ``...`` + the last 2."""
    print(f"Found {len(godla)} sheets at {target_scale} for {what} ({label})")
    sample = godla if len(godla) <= 10 else godla[:3] + ["..."] + godla[-2:]
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
) -> tuple[str | None, int | None, int | None]:
    """Campaign strategy and year bounds; absent attributes support handmade tests."""
    return (
        getattr(args, "campaigns", None),
        getattr(args, "min_year", None),
        getattr(args, "max_year", None),
    )


def _reject_laz_only_opts(args: argparse.Namespace) -> bool:
    """Reject ``--min-density`` on non-LAZ products before any network request."""
    product = getattr(args, "product", "nmt")
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
    if getattr(args, "product", "nmt") != "laz" or not getattr(
        args, "full_sheet", False
    ):
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
    campaigns, min_year, max_year = _campaign_opts(args)
    if (
        campaigns != "all"
        and min_year is None
        and max_year is None
        and getattr(args, "year", None) is None
        and not getattr(args, "full_sheet", False)
    ):
        return False
    if "PL" not in countries:
        print(
            "Error: CZ (CUZK) nie ma kampanii — "
            "--campaigns all/--min-year/--max-year/--year/--full-sheet dotycza "
            "tylko PL",
            file=sys.stderr,
        )
        return True
    if "CZ" in countries:
        print(
            "Info: --campaigns/--min-year/--max-year/--year/--full-sheet dotycza "
            "tylko czesci PL (CZ: biezaca wersja danych CUZK)",
            file=sys.stderr,
        )
    return False


def _reject_campaign_opts_with_target_crs(args: argparse.Namespace) -> bool:
    """A PL cutout (WCS, ADR-035) has no year or campaign choice: the server's
    flight composition, the download date in the name."""
    if getattr(args, "target_crs", None) is None:
        return False
    campaigns, min_year, max_year = _campaign_opts(args)
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
    if campaigns == "all":
        print(
            "Error: --campaigns all nie dziala z --target-crs — wycinek z WCS "
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


def _resolve_pl_sentinels(args: argparse.Namespace) -> int:
    """
    Resolve None sentinels to Polish defaults; PL validation.

    Called ONLY on the PL branch, after the country is resolved - it mutates
    ``args``, so arguments heading to CZ must keep the value ``None``
    (``_cmd_download_cz`` distinguishes "not given" from a Polish value).

    Covers validation of the product/resolution and product/vertical_crs pairs
    (symmetric to the hard rejections of the CZ branch) and of the ``--target-crs``
    exclusions (product orto/laz, ``--resolution 5m``, ``--system 2000`` -
    ADR-027/035)
    - checked BEFORE defaults are substituted, so that "not given" does not
    pose as a user choice. NMT 5m with KRON86 is rejected after the
    defaults (0.7.1, ``require_nmt_vertical_crs``): only an explicit
    ``--vertical-crs KRON86`` can produce the pair.

    Returns
    -------
    int
        0 = OK, 1 = error (message already printed to stderr)
    """
    product = getattr(args, "product", "nmt")
    if product == "nmpt" and getattr(args, "resolution", None) == "5m":
        print(
            "Error: --product nmpt jest dostepny tylko w rozdzielczosci 1m (podano 5m)",
            file=sys.stderr,
        )
        return 1
    if product == "orto" and getattr(args, "vertical_crs", None) is not None:
        print(
            "Error: --vertical-crs nie dotyczy --product orto "
            "(ortofotomapa nie ma ukladu pionowego)",
            file=sys.stderr,
        )
        return 1

    target_crs = getattr(args, "target_crs", None)
    if target_crs is not None and product in ("orto", "laz"):
        print(
            "Error: --target-crs dla PL dziala tylko z --product nmt albo nmpt "
            "(wycinek wysokosci z WCS GUGiK; orto i laz — pobierz bez "
            "--target-crs)",
            file=sys.stderr,
        )
        return 1
    if target_crs is not None and getattr(args, "resolution", None) == "5m":
        print(
            "Error: wycinki --target-crs sa tylko 1 m (WCS GUGiK); arkusze 5 m: "
            "pomin --target-crs; wycinek: --resolution 1m",
            file=sys.stderr,
        )
        return 1
    if target_crs is not None and getattr(args, "system", None) == "2000":
        print(
            "Error: --target-crs nie dziala z --system 2000 — bbox "
            "wielostrefowy dalby arkusze w roznych CRS (2176-2179), "
            "mozaika miedzystrefowa to etap 2; uzyj domyslnego --system 1992",
            file=sys.stderr,
        )
        return 1

    args.resolution = getattr(args, "resolution", None) or "1m"
    args.vertical_crs = getattr(args, "vertical_crs", None) or "EVRF2007"
    args.system = getattr(args, "system", None) or "1992"

    if args.resolution == "2m":
        print(
            "Error: PL nie ma rozdzielczosci 2m — dostepne: 1m, 5m (2m to DMR 5G w CZ)",
            file=sys.stderr,
        )
        return 1
    if args.vertical_crs == "Bpv":
        print(
            "Error: Bpv to uklad czeski — dla PL dostepne: KRON86, EVRF2007",
            file=sys.stderr,
        )
        return 1
    if product == "nmt":
        # 0.7.1: the library rule (`require_nmt_vertical_crs`) - 5m exists only
        # in EVRF2007, so an explicit --vertical-crs KRON86 is an error (no
        # swap); the default (None -> EVRF2007 above) never trips it. The
        # message names CLI flags instead of the library's keyword arguments.
        try:
            require_nmt_vertical_crs(args.resolution, args.vertical_crs)
        except ValidationError:
            print(
                f"Error: NMT {args.resolution} (PL) jest dostepny tylko w "
                f"EVRF2007 — podano --vertical-crs {args.vertical_crs}; uzyj "
                "--vertical-crs EVRF2007 (albo pomin --vertical-crs) albo "
                f"--resolution 1m dla {args.vertical_crs}",
                file=sys.stderr,
            )
            return 1
    return 0


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
    Options must be resolvable for EVERY intersected country (0=OK, 1=error).

    Validation happens BEFORE any download - otherwise part of one country would be
    downloaded and the other branch would reject the task only afterwards (partial
    execution). Instead of silently skipping a country, the CLI suggests an explicit
    ``--country`` - but only when the area actually intersects more than one country
    (with one country the choice is already resolved).

    ORDER: under ``--country auto`` some options are already resolved
    earlier (``_pl_only_flags`` in ``_dispatch_area``, ADR-023 point 5), so
    ``countries`` is then single-element and these checks see only
    truly ambiguous tasks (e.g. ``--resolution 2m``, which has no
    PL counterpart) or an explicit ``--country``, which the CLI does not
    override.

    ``--target-crs`` is NOT validated here: since ADR-027 it works on both sides of the
    border (PL: a merged cutout), so a cross-border task with this flag is
    legal. PL exclusions (product != nmt, ``--system 2000``) are checked by
    ``_resolve_pl_sentinels``, already on the Polish branch.
    """
    product = getattr(args, "product", "nmt")
    resolution = getattr(args, "resolution", None)
    vertical_crs = getattr(args, "vertical_crs", None)
    checks: list[tuple[bool, str]] = [
        (
            "CZ" in countries and product != "nmt",
            f"--product {product} jest dostepny tylko dla PL",
        ),
        (
            "CZ" in countries and resolution == "1m",
            "--resolution 1m nie istnieje dla CZ (dostepne 2m/5m)",
        ),
        (
            "PL" in countries and resolution == "2m",
            "--resolution 2m nie istnieje dla PL (dostepne 1m/5m)",
        ),
        (
            "CZ" in countries and vertical_crs == "KRON86",
            "KRON86 nie jest osiagalny dla CZ (siatki GUGiK niepubliczne)",
        ),
        ("PL" in countries and vertical_crs == "Bpv", "Bpv to uklad czeski"),
        (
            "CZ" in countries and getattr(args, "system", None) is not None,
            "--system dotyczy tylko PL",
        ),
    ]
    hint = f"; {_CROSS_COUNTRY_HINT}" if len(countries) > 1 else ""
    for failed, message in checks:
        if failed:
            print(f"Error: {message}{hint}", file=sys.stderr)
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
    * ``--target-crs`` since ADR-027 works on both sides of the border (PL: a merged
      cutout), so it does not decide the country in either direction;
    * ``--campaigns all``/``--min-year`` (ADR-030) neither: a PL+CZ area
      downloads CZ in its current version (``_reject_campaign_opts_without_pl``).
    """
    flags: list[str] = []
    product = getattr(args, "product", "nmt")
    if product in ("nmpt", "orto"):
        flags.append(f"--product {product}")
    if getattr(args, "system", None) is not None:
        flags.append("--system")
    if getattr(args, "vertical_crs", None) == "KRON86":
        flags.append("--vertical-crs KRON86")
    if getattr(args, "resolution", None) == "1m":
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

    ``Info:``/``Warning:`` messages about country resolution, the mixed default
    vertical CRSs of a PL+CZ task (PL EVRF2007, CZ Bpv) and partial success go
    to stderr, so ``-q`` (suppressing stdout) does NOT hide them - just like
    ``Error:`` messages.
    """
    from kartograf.transform.crs import TransformError

    country_flag = getattr(args, "country", "auto")
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
    product = getattr(args, "product", "nmt")
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
        # Each country keeps its own default vertical CRS (PL EVRF2007, CZ Bpv,
        # ~0.11-0.15 m apart); say so before the work. The country envelopes are
        # rectangles (ADR-023 point 4), so this names the CRS of the parts the task
        # runs, not whether both hold data (spec silent-defaults 2.3).
        if {"PL", "CZ"} <= parts.keys() and getattr(args, "vertical_crs", None) is None:
            print(
                "Info: --country auto bez --vertical-crs: czesc PL w EVRF2007, "
                "czesc CZ w Bpv (rozne uklady wysokosci, roznica ok. "
                "0,11-0,15 m); jeden uklad dla obu: --vertical-crs EVRF2007",
                file=sys.stderr,
            )

    results: list[tuple[str, int]] = []
    for code in countries:
        part = parts[code].bbox
        if code == "CZ":
            rc = _run_cz(args, bbox=part, parent_request=parent_request)
        else:
            # COPY of args: _resolve_pl_sentinels mutates the Namespace (None->"1m"),
            # which would poison the CZ branch; the copy removes the order dependence
            pl_args = argparse.Namespace(**vars(args))
            if filepath is not None:
                rc = _download_pl_geometry(pl_args, filepath, parent_request, bbox=part)
            else:
                rc = _download_pl_bbox(pl_args, part, parent_request)
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
    except (ValidationError, ValueError, TransformError) as e:
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


def cmd_download(args: argparse.Namespace) -> int:
    """
    Execute the download command.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    _cache_warnings_shown.clear()
    has_godlo = args.godlo is not None
    has_bbox = args.bbox is not None
    has_geometry = getattr(args, "geometry", None) is not None

    provided = sum([has_godlo, has_bbox, has_geometry])
    if provided > 1:
        print(
            "Error: Specify only one of: godlo, --bbox, or --geometry",
            file=sys.stderr,
        )
        return 1

    if provided == 0:
        print(
            "Error: Must specify one of: godlo, --bbox, or --geometry",
            file=sys.stderr,
        )
        return 1

    # --- Per-country dispatch: the sheet code decides the country via the system
    # registry ---
    from kartograf.core.parser_registry import detect_system

    campaigns, min_year, max_year = _campaign_opts(args)
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
        validate_campaign_args(campaigns, min_year, max_year)
    except ValidationError as e:
        message = (
            str(e)
            .replace("min_year", "--year" if year is not None else "--min-year")
            .replace("max_year", "--max-year")
        )
        print(f"Error: {message}", file=sys.stderr)
        return 1
    # Year bounds only restrict the admissible years; --campaigns sets how many
    # flights (model A, ADR-032 point 3): the same rule for every product.
    campaigns = campaigns or "newest"
    args.campaigns = campaigns
    args.min_year, args.max_year = min_year, max_year
    full_sheet = bool(getattr(args, "full_sheet", False))

    # Point-density filtering is LAZ-only, --full-sheet the reverse (ADR-033);
    # every product supports year flags.
    if _reject_laz_only_opts(args) or _reject_full_sheet_for_laz(args):
        return 1

    country_flag = getattr(args, "country", "auto")
    product = getattr(args, "product", "nmt")

    if has_godlo:
        # the registry ends with the pl1992 fallback (always matches, never None)
        system = detect_system(args.godlo)
        system_id = system.id
        system_country = system.country
        if country_flag != "auto" and country_flag.upper() != system_country:
            print(
                f"Error: Godlo '{args.godlo}' nalezy do systemu {system_id} "
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
        if _resolve_pl_sentinels(args):
            return 1
        if getattr(args, "target_crs", None) is not None:
            print(
                "Error: --target-crs dziala tylko z --bbox/--geometry; godlo "
                "wyznacza zasieg i uklad produktu (arkusz PL 1:1 w ukladzie "
                "godla, arkusz SM5 1:1 w EPSG:5514, kafel TM33 na siatce "
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

    # --- Sheet code mode (existing logic) ---
    try:
        # Validate sheet code first
        SheetParser(args.godlo)
    except (ParseError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Create download manager with vertical CRS, resolution, and product
    output_dir = Path(args.output)
    # the PL sentinels are already resolved (`_resolve_pl_sentinels`), and argparse
    # always creates both attributes - we read them directly
    vertical_crs = args.vertical_crs
    resolution = args.resolution
    product = getattr(args, "product", "nmt")
    label = _product_label(product, resolution)

    workers = getattr(args, "workers", 4)

    with _pl_metadata_cache(args) as cache:
        provider, storage = _create_provider_and_storage(
            product, output_dir, vertical_crs, resolution, cache=cache
        )
        on_progress = create_progress_callback(args.quiet)
        try:
            manager = DownloadManager(
                output_dir=output_dir,
                provider=provider,
                storage=storage,
                # the vertical CRS is already validated: 5m + KRON86 is
                # rejected in _resolve_pl_sentinels (0.7.1)
                vertical_crs=vertical_crs,
                resolution=resolution,
                max_workers=workers,
                campaigns=campaigns,
                min_year=min_year,
                max_year=max_year,
                full_sheet=full_sheet,
            )
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        skip_existing = not args.force

        try:
            if args.scale:
                # Download hierarchy
                if not args.quiet:
                    count = manager.count_sheets(args.godlo, args.scale)
                    print(
                        f"Downloading {count} sheets from {args.godlo} to "
                        f"{args.scale} ({label})"
                    )
                    print()

                paths = manager.download_hierarchy(
                    args.godlo,
                    args.scale,
                    skip_existing=skip_existing,
                    on_progress=on_progress,
                )
            else:
                # Download single sheet (may expand to hierarchy for non-1:10000)
                def announce() -> None:
                    # O-3: only when the download starts (not on Skipped/Error)
                    if not args.quiet:
                        print(f"Downloading {args.godlo} ({label})...")

                parsed = SheetParser(args.godlo)
                if parsed.uklad != "2000" and parsed.scale != "1:10000":
                    announce()  # coarser sheet code: expanded to a hierarchy

                result = manager.download_sheet(
                    args.godlo,
                    skip_existing=skip_existing,
                    on_progress=on_progress,
                    on_download=announce,
                )
                if not isinstance(result, list):
                    # a single 1:10000 / PL-2000 sheet: success = no exception (no data
                    # = DownloadError, code 1 - D10). E15: skip is reported by the
                    # manager (`last_sheet`), not by the existence of the standard path
                    # - a link may exist while a new campaign is still downloaded.
                    # isinstance (I-1): the manager's Mock() stand-in has
                    # `last_sheet.skipped` = Mock (truthy).
                    fetch = manager.last_sheet
                    sheet = fetch if isinstance(fetch, SheetFetch) else None
                    # U15: when the standard path keeps a newer flight, name the
                    # campaign file of this request instead.
                    where = result
                    if sheet is not None and sheet.link_outside_range is not None:
                        where = (sheet.downloaded or sheet.reused)[0]
                    if not args.quiet:
                        if campaigns == "all" and sheet is not None:
                            # M-1: like the list - campaign files, not a sheet
                            _print_campaign_summary(
                                len(sheet.downloaded), 1, output_dir, len(sheet.reused)
                            )
                        elif sheet is not None and sheet.skipped:
                            print(f"Skipped {args.godlo} - already exists at {where}")
                        elif (
                            sheet is not None
                            and len(sheet.downloaded + sheet.reused) > 1
                        ):
                            # --full-sheet: the newest and the newest full flight
                            _print_campaign_summary(
                                len(sheet.downloaded), 1, output_dir, len(sheet.reused)
                            )
                        else:
                            print(f"Downloaded to {where}")
                    if sheet is not None and sheet.link == "copy":
                        _warn_copied_links([args.godlo])
                    if sheet is not None and sheet.unverified is not None:
                        print(
                            f"Warning: {args.godlo}: skorowidz GUGiK niedostepny "
                            "— uzyto lokalnej kampanii bez sprawdzenia nowszej "
                            f"({sheet.unverified})",
                            file=sys.stderr,
                        )
                    # one-element result from the sheet facts, read like a list
                    facts = _sheet_result(sheet)
                    _warn_sheet_sidecars(
                        [result],
                        facts,
                        full_sheet=full_sheet,
                        campaigns=campaigns,
                        ranged=min_year is not None or max_year is not None,
                    )
                    _print_better_coverage(facts, [result])
                    _print_link_outside_range(
                        facts.link_outside_range, facts.full_link_outside_range
                    )
                    return 0
                paths = result

        except DownloadError as e:
            print(f"{_error_lead(on_progress)}Error: {e}", file=sys.stderr)
            return 1
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # The hierarchy (--scale or a sheet code coarser than 1:10000) swallows failures
    # of individual sheets and reports them in `last_result` - the same
    # finish as the sheet list mode (D10: sea sheets under a 1:50000 sheet code
    # on the coast are the same situation as under --bbox).
    return _finish_pl_sheets(
        _last_result(manager),
        paths,
        output_dir=output_dir,
        quiet=args.quiet,
        campaigns=campaigns,
        full_sheet=full_sheet,
        ranged=min_year is not None or max_year is not None,
    )


def _last_result(manager: DownloadManager) -> DownloadResult:
    """``manager.last_result`` after a hierarchy/list - always filled (contract)."""
    result = manager.last_result
    if result is None:  # pragma: no cover — contract of download_sheets/hierarchy
        raise RuntimeError("DownloadManager nie wypelnil last_result po pobraniu listy")
    return result


def _download_godlo_list(
    manager: DownloadManager,
    godlo_list: list[str],
    skip_existing: bool,
    on_progress,
) -> tuple[list[Path], DownloadResult]:
    """
    Download a list of sheet codes with one ``DownloadManager.download_sheets`` (S2/D2).

    Sheet codes coarser than 1:10000 are expanded by ``expand_sheets`` (the manager),
    the download goes to the manager's ``max_workers``, and failures of individual
    sheets do NOT abort the list: ``NoCoverageError`` (sea, a sheet abroad) and
    ``DownloadError`` (network, server) land in ``DownloadResult`` - every sheet is
    attempted independently of ``--workers``. The exit code and messages are produced by
    ``_finish_pl_sheets``.

    Returns
    -------
    tuple[list[Path], DownloadResult]
        Files available after the task (downloaded + skipped as existing)
        and a per-sheet summary (``manager.last_result``).
    """
    paths = manager.download_sheets(
        godlo_list, skip_existing=skip_existing, on_progress=on_progress
    )
    return list(paths), _last_result(manager)


def _warn_copied_links(godla: Sequence[str]) -> None:
    """``Warning:`` about the standard path being a COPY of a campaign (ADR-030)."""
    shown = ", ".join(godla[:10]) + (" ..." if len(godla) > 10 else "")
    print(
        "Warning: hardlink niedostepny na tym systemie plikow — sciezka "
        f"standardowa jest KOPIA najnowszej kampanii dla {len(godla)} arkuszy "
        f"({shown}) (extra.link=copy)",
        file=sys.stderr,
    )


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


def _print_campaign_summary(
    downloaded: int, sheets: int, output_dir: Path, existed: int
) -> None:
    """Summary of ``--campaigns all`` (sheet list and a single sheet code)."""
    print(
        f"Downloaded {downloaded} campaign files for "
        f"{sheets} sheets to {output_dir} ({existed} already existed)"
    )


def _warn_unverified(unverified: dict[str, str], *, from_sidecar: bool = False) -> None:
    """``Warning:`` for sheets taken from a local campaign unverified (I-1)."""
    godla = list(unverified)
    shown = ", ".join(godla[:10]) + (" ..." if len(godla) > 10 else "")
    print(
        "Warning: skorowidz GUGiK niedostepny — dla "
        f"{len(godla)} arkuszy uzyto lokalnej kampanii bez sprawdzenia nowszej "
        f"({shown}) ({unverified[godla[0]]})"
        + (" (z sidecara istniejacego wycinka)" if from_sidecar else ""),
        file=sys.stderr,
    )


def _finish_pl_sheets(
    result: DownloadResult,
    paths: list[Path],
    *,
    output_dir: Path,
    quiet: bool,
    campaigns: str = "newest",
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
    Standard path as a campaign COPY (``result.copied``) ->
    ``Warning:``, code unchanged. ``campaigns="all"`` or ``full_sheet``: the
    summary counts campaign files (``result.campaign_files``), not sheets.
    ``newest`` sheets
    from a local campaign on an index failure
    (``result.unverified``, I-1) -> ``Warning:``, code unchanged.

    ``Warning:``/``Error:`` go to stderr, so ``-q`` does NOT suppress them.
    """
    _warn_sheet_sidecars(
        paths, result, full_sheet=full_sheet, campaigns=campaigns, ranged=ranged
    )
    _print_better_coverage(result, paths)
    _print_link_outside_range(result.link_outside_range, result.full_link_outside_range)
    if result.copied:
        _warn_copied_links(result.copied)
    if result.unverified:
        _warn_unverified(result.unverified)
    if not quiet:
        # the progress bar ends with "skipped"/"downloading" without a newline
        print()
    if not quiet and paths:
        # O-7: with no file and no skip (only gaps/failures) a summary of 0 is noise
        if campaigns == "all" or full_sheet:
            # `campaign_files` = downloaded + local; local ones separately
            # (`reused_campaign_files`, a per-sheet subset)
            files = result.campaign_files
            existed = sum(len(f) for f in result.reused_campaign_files.values())
            total_files = sum(len(f) for f in files.values())
            _print_campaign_summary(
                total_files - existed, len(files), output_dir, existed
            )
        else:
            print(
                f"Downloaded {len(result.succeeded)} files to {output_dir} "
                f"({len(result.skipped)} already existed)"
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
    for godlo, better_id in shown.items():
        meta = sidecars.get(godlo) or {}
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
        print(f"  {godlo}: {detail}", file=sys.stderr)
    if len(better) > len(shown):
        print(f"  ... i {len(better) - len(shown)} innych", file=sys.stderr)


def _campaign_dirname(path: Path) -> str:
    """``<date>_<id>`` of a ``kampanie/<date>_<id>/...`` path; else the file name."""
    parts = Path(path).parts
    if "kampanie" in parts and parts.index("kampanie") + 1 < len(parts):
        return parts[parts.index("kampanie") + 1]
    return Path(path).name


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
        [(godlo, "sciezka standardowa", t) for godlo, t in outside.items()]
        + [(godlo, "full_sheet/", t) for godlo, t in (full_outside or {}).items()]
    )
    if not rows:
        return
    print(
        f"Info: {len(rows)} dowiazan wskazuje lokalny lot spoza tego zadania "
        "(dowiazanie nigdy nie cofa sie na starszy lot); pobrane loty sa "
        "w <segment>/kampanie/:",
        file=sys.stderr,
    )
    for godlo, tree, target in rows[:10]:
        print(
            f"  {godlo}: {tree} -> dowiazanie {_campaign_dirname(target)}",
            file=sys.stderr,
        )
    if len(rows) > 10:
        print(f"  ... i {len(rows) - 10} innych", file=sys.stderr)


def _sheet_result(sheet: SheetFetch | None) -> DownloadResult:
    """One-element ``DownloadResult`` with the message facts of one sheet."""
    result = DownloadResult()
    if sheet is None:
        return result
    g = sheet.godlo
    if sheet.better_coverage is not None:
        result.better_coverage[g] = sheet.better_coverage
    if sheet.link_outside_range is not None:
        result.link_outside_range[g] = sheet.link_outside_range
    if sheet.full_link is not None:
        result.full_links[g] = sheet.full_link
    if sheet.full_link_outside_range is not None:
        result.full_link_outside_range[g] = sheet.full_link_outside_range
    if sheet.no_full_flight:
        result.without_full.append(g)
    return result


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
    godlo = request.get("sheet") if isinstance(request, dict) else None
    actual = meta.get("horizontal_crs")
    if not isinstance(godlo, str) or not isinstance(actual, str):
        return None
    try:
        expected = horizontal_crs_for_godlo(godlo)
    except KartografError:
        return None
    if expected == actual:
        return None
    return godlo, expected, actual


def _warn_crs_mismatch_sheets(paths) -> None:
    """E17: ``Warning:`` about sheets whose file is in a different CRS than
    the sheet code/index record declares. Exit code unchanged; the sidecar describes
    the FILE's CRS. Reads sidecars, so it repeats on skip."""
    found = [m for m in (_sheet_crs_mismatch(Path(p)) for p in paths) if m]
    if not found:
        return
    found.sort()
    shown = ", ".join(
        f"{godlo} (godlo: {expected}, plik: {actual})"
        for godlo, expected, actual in found[:10]
    ) + (" ..." if len(found) > 10 else "")
    print(
        f"Warning: {len(found)} arkuszy GUGiK opublikowano w innym ukladzie "
        f"niz wskazuje godlo: {shown} — sidecar opisuje uklad pliku "
        "(horizontal_crs); deklaracja rekordu w extra.source.declared_crs",
        file=sys.stderr,
    )


def _warn_sheet_sidecars(
    paths, result: DownloadResult, *, full_sheet: bool, campaigns: str, ranged: bool
) -> None:
    """CLI warnings from the result sheets' sidecars: incomplete sheet (E13)
    and file CRS different from the sheet code's (E17)."""
    _warn_partial_sheets(
        paths, result, full_sheet=full_sheet, campaigns=campaigns, ranged=ranged
    )
    _warn_crs_mismatch_sheets(paths)


def _godla_text(godla: list[str]) -> str:
    return ", ".join(godla[:10]) + (" ..." if len(godla) > 10 else "")


def _warn_partial_sheets(
    paths, result: DownloadResult, *, full_sheet: bool, campaigns: str, ranged: bool
) -> None:
    """E13: ``Warning:`` about sheets from an incomplete newest GUGiK campaign.

    The selection rule (ADR-028: newest campaign, no preference for a full
    sheet) stays - the warning only makes it visible. Reads the sidecars of
    result files, so it also works for sheets skipped as existing. One
    ``Warning:`` splits the sheets (ADR-033): with a ``full_sheet/`` link
    (``result.full_links``), without a full flight in the index
    (``result.without_full``; with ``campaigns="all"`` every flight of the
    range is local, so no link means none; ``ranged`` limits that claim to
    the year bounds), and the rest — not downloaded, with the
    ``--full-sheet`` hint unless the flag was given.
    """
    partial = sorted(Path(p).stem for p in paths if _is_partial_sheet(Path(p)))
    if not partial:
        return
    linked = [g for g in partial if g in result.full_links]
    rest = [g for g in partial if g not in result.full_links]
    absent = [g for g in rest if g in result.without_full or campaigns == "all"]
    missing = [g for g in rest if g not in absent]
    groups = []
    if linked:
        groups.append(f"pelny lot w <segment>/full_sheet/: {_godla_text(linked)}")
    if absent:
        scope = " w zakresie lat zadania" if ranged else ""
        groups.append(f"brak pelnego lotu w skorowidzu{scope}: {_godla_text(absent)}")
    if missing:
        hint = "" if full_sheet else " — uzyj --full-sheet"
        groups.append(f"pelny lot nie pobrany: {_godla_text(missing)}{hint}")
    print(
        f"Warning: najnowsza kampania GUGiK jest niepelna dla {len(partial)} "
        "arkuszy — skorowidz deklaruje arkusz nie w calosci wypelniony "
        "trescia; plik w sciezce standardowej moze miec duzo nodata/czerni "
        "(extra.source.full_sheet w sidecarze); " + "; ".join(groups),
        file=sys.stderr,
    )


# description of the datum step in sidecars from before the K2 fix (EPSG:4829, area of
# use:
# Slovakia; content shifted 1-5 m) - after the fix the CZ path and the PL cutout -> 5514
# pin "S-JTSK to ETRS89 (1)"/"(2)"
_LEGACY_KROVAK_STEP = "S-JTSK to ETRS89 (3)"


def _print_legacy_krovak_info(target: Path) -> None:
    """D12: a skipped file from before the S-JTSK operation fix gets an ``Info:``.

    Reads the ``<file>.meta.json`` sidecar (best-effort: missing/unreadable =
    silence) and checks ``transform.horizontal``. No automatic
    rebuild - the user decides (``--force``).
    """
    sidecar = target.parent / f"{target.name}.meta.json"
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        horizontal = (payload.get("transform") or {}).get("horizontal")
    except (OSError, ValueError, AttributeError):
        return
    if isinstance(horizontal, str) and _LEGACY_KROVAK_STEP in horizontal:
        print(
            f"Info: {target} pochodzi sprzed naprawy operacji S-JTSK (tresc "
            "przesunieta 1-5 m) — pobierz ponownie z --force",
            file=sys.stderr,
        )


def _download_pl_cutout(
    args: argparse.Namespace,
    bbox: BBox,
    parent_request: dict,
) -> int:
    """Polish --target-crs cutout from GUGiK WCS (ADR-035): a CLI overlay on
    ``download/cutout.py``.

    Called after ``_resolve_pl_sentinels`` (nmt/nmpt, 1m only). ``bbox`` is
    the request or the ``--geometry`` envelope. Preparation errors
    (``TransformError``/``ValidationError``) and EVERY download or build
    error (PRG, WCS) end with code 1 and a message, not a traceback: an
    exception leaking out of the country loop of ``_dispatch_area`` would break
    the partial success contract (ADR-023 points 4-5). Every run downloads
    (``--force``, ``--workers`` and ``--scale`` have no effect). A cutout
    entirely outside PL land = ``Warning:``, code 0.
    """
    from kartograf.download.cutout import prepare_pl_cutout, run_pl_wcs_cutout
    from kartograf.transform.crs import TransformError

    product = getattr(args, "product", "nmt")
    output_dir = Path(args.output)
    try:
        # fail-fast: the pinned operation is built BEFORE any network access
        cutout = prepare_pl_cutout(
            bbox,
            args.target_crs,
            output_dir=output_dir,
            resolution=args.resolution,
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
    chunks = len(provider.plan_wcs_chunks(cutout.bbox_source_2180))
    if chunks > 1 or cutout.estimated_bytes >= 2**30:
        # stderr, not stdout: -q does NOT suppress Info:/Warning:
        height, width = cutout.grid_shape
        print(
            f"Info: wycinek {width} x {height} px float32 "
            f"(~{cutout.estimated_bytes / 2**20:.0f} MiB), {chunks} zapytan WCS "
            "GUGiK pobieranych po kolei",
            file=sys.stderr,
        )
    try:
        result = run_pl_wcs_cutout(
            cutout, provider=provider, parent_request=parent_request
        )
    except Exception as e:  # noqa: BLE001 — code 1 instead of a traceback (ADR-023)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if result.all_nodata:
        print(
            "Warning: wycinek w calosci nodata — obszar poza ladem PL (maska PRG: "
            "granica panstwa bez morza terytorialnego i wod wewnetrznych)",
            file=sys.stderr,
        )
    if not args.quiet:
        print(f"Downloaded to {result.path}")
    return 0


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
    if _resolve_pl_sentinels(args):
        return 1
    if args.target_crs is not None:
        return _download_pl_cutout(args, bbox, parent_request)

    target_scale = args.scale or "1:10000"

    # Find sheets covering the bbox (no network, no cache)
    try:
        godlo_list = find_sheets_for_bbox(bbox, target_scale, system=args.system)
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not godlo_list:
        print("Error: No sheets found for the given bbox", file=sys.stderr)
        return 1

    return _download_pl_sheet_list(
        args, godlo_list, parent_request, what="bbox", target_scale=target_scale
    )


def _download_pl_sheet_list(
    args: argparse.Namespace,
    godlo_list: list[str],
    parent_request: dict,
    *,
    what: str,
    target_scale: str,
) -> int:
    """PL sheet list mode (bbox/geometry without ``--target-crs``): manager + finish.

    The PL sentinels are already resolved (``_resolve_pl_sentinels``), and argparse
    always creates both attributes - we read them directly. ``MetadataCache`` lives
    only for the duration of the task (N6).
    """
    output_dir = Path(args.output)
    vertical_crs = args.vertical_crs
    resolution = args.resolution
    product = getattr(args, "product", "nmt")
    workers = getattr(args, "workers", 4)
    skip_existing = not args.force
    campaigns, min_year, max_year = _campaign_opts(args)
    campaigns = campaigns or "newest"
    full_sheet = bool(getattr(args, "full_sheet", False))

    if not args.quiet:
        _print_sheet_list(
            godlo_list,
            target_scale,
            what=what,
            label=_product_label(product, resolution),
        )

    with _pl_metadata_cache(args) as cache:
        provider, storage = _create_provider_and_storage(
            product, output_dir, vertical_crs, resolution, cache=cache
        )
        on_progress = create_progress_callback(args.quiet)
        try:
            manager = DownloadManager(
                output_dir=output_dir,
                provider=provider,
                storage=storage,
                # the vertical CRS is already validated: 5m + KRON86 is
                # rejected in _resolve_pl_sentinels (0.7.1)
                vertical_crs=vertical_crs,
                resolution=resolution,
                max_workers=workers,
                sidecar_extra={"parent_request": parent_request},
                campaigns=campaigns,
                min_year=min_year,
                max_year=max_year,
                full_sheet=full_sheet,
            )
            all_paths, result = _download_godlo_list(
                manager, godlo_list, skip_existing, on_progress
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
        campaigns=campaigns,
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
    return SheetParser(args.godlo).get_bbox(crs="EPSG:2180")


def _laz_parent_request(args: argparse.Namespace, bbox: BBox) -> dict | None:
    """``extra.parent_request`` of LAZ tiles (ADR-023 (f).1, review-2 N15).

    Only ``--bbox``/``--geometry`` mode (sheet code: ``None``). As in the other
    paths: ``--bbox`` in the GIVEN CRS (before transformation to EPSG:2180),
    ``--geometry`` as an EPSG:2180 envelope; ``countries`` = ``["PL"]`` - LAZ
    queries GUGiK only.
    """
    if args.godlo is not None:
        return None
    if args.bbox is not None:
        parts = [float(x.strip()) for x in args.bbox.split(",")]
        bbox = BBox(parts[0], parts[1], parts[2], parts[3], args.bbox_crs)
    return _build_parent_request(bbox, ("PL",))


def _laz_tile_label(tile) -> str:
    return f"{tile.godlo} ({tile.year}, {tile.crs})"


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
    if getattr(args, "country", "auto") == "cz":
        print(_CZ_ONLY_NMT_MSG.format(product="laz"), file=sys.stderr)
        return 1
    campaigns, min_year, max_year = _campaign_opts(args)
    campaigns = campaigns or "newest"
    if _resolve_pl_sentinels(args):
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
        getattr(args, "country", "auto") == "auto"
        and args.godlo is None
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
            campaigns=campaigns,
            min_year=min_year,
            max_year=max_year,
        )
    except (ValueError, ValidationError, DownloadError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    _print_laz_superseded(selection.superseded)
    if not selection.tiles:
        # N7: discovery passed (all vintages answered), so an empty
        # list means extent/filters, not a WFS failure
        print(f"Error: {NO_TILES_MESSAGE}", file=sys.stderr)
        return 1

    total = len(selection.tiles)
    if not quiet:
        print(f"Found {total} LAZ tiles. Downloading with {workers} worker(s)...")
        print()

    def _progress(done: int, count: int) -> None:
        if not quiet:
            print(f"\r  {done}/{count} tiles", end="", flush=True)

    result = run_laz_download(
        selection,
        provider=provider,
        bbox=bbox,
        output_dir=output_dir,
        min_density=min_density,
        campaigns=campaigns,
        min_year=min_year,
        max_year=max_year,
        max_workers=workers,
        force=args.force,
        on_progress=_progress,
        parent_request=_laz_parent_request(args, bbox),
    )

    if not quiet:
        print()
        print(
            f"Downloaded {len(result.downloaded)} tiles "
            f"({len(result.skipped)} skipped) to {output_dir / 'laz'}"
        )
    if result.failed:
        # Code 1 => `Error:` (convention: `Warning:` only with code 0) and the FULL
        # list of failed tiles to retry - model `_finish_pl_sheets` (N6).
        names = ", ".join(f.tile.godlo for f in result.failed)
        print(
            f"Error: {len(result.failed)} z {total} kafli LAZ nie pobrano "
            f"(blad pobrania): {names} — ponow pobranie",
            file=sys.stderr,
        )
        for failure in result.failed:
            print(f"  {failure.tile.godlo}: {failure.error}", file=sys.stderr)
        return 1

    return 0


def _warn_cz_all_nodata(target: Path, nodata: float | None) -> None:
    """N2: ``Warning:`` when a CZ raster has not a single valid pixel (code 0).

    Best-effort like ``_read_tif_nodata`` - a read error = silence (provider
    mocks do not write a file). No nodata tag: CUZK writes -9999.
    """
    from kartograf.providers.cuzk.dmr import CUZK_NODATA
    from kartograf.transport.mosaic import has_valid_pixels

    try:
        empty = not has_valid_pixels(target, CUZK_NODATA if nodata is None else nodata)
    except Exception:  # noqa: BLE001 — a warning never aborts the download
        return
    if empty:
        print(
            f"Warning: {target} jest w calosci nodata — obszar poza pokryciem "
            "DMR CUZK (poza granica CZ?)",
            file=sys.stderr,
        )


def _cz_download_godlo(args, provider, *, quiet: bool, skip_existing: bool) -> int:
    """CZ sheet code: TM33 tile (exportImage) or SM5 sheet (openzu) into FileStorage."""
    import logging

    from kartograf.core.parser_registry import detect_system
    from kartograf.download.storage import storage_for_provider
    from kartograf.sources.registry import get_source

    godlo = args.godlo
    system = detect_system(godlo)
    descriptor = get_source(provider.descriptor_key)
    storage = storage_for_provider(args.output, provider)
    target = storage.get_raw_path(godlo, f"{godlo}{descriptor.default_extension}")

    if skip_existing and target.exists():
        if not quiet:
            print(f"Skipped {godlo} - already exists at {target}")
        _print_legacy_krovak_info(target)
        return 0

    def announce() -> None:
        # O-3 as in the PL flow: only when the transfer really starts (after
        # the provider's validations: SM5 sheet index, TM33 grid parse)
        if not quiet:
            print(f"Downloading {godlo} (CZ, resolution: {provider.resolution})...")

    try:
        provider.download(godlo, target, on_download=announce)
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    nodata = _read_tif_nodata(target)
    _warn_cz_all_nodata(target, nodata)
    is_sm5 = system.id == "cz_sm5"
    extra: dict = {}
    if is_sm5:
        try:
            info = provider.sheet_index.sm5_sheet(godlo)
            if info.name is not None:
                extra["mapname"] = info.name
            if info.podil is not None:
                extra["cz_share"] = info.podil
        except Exception as e:  # noqa: BLE001 — data matters more than metadata
            logging.getLogger(__name__).warning(
                f"Sidecar {godlo} bez extra.cz_share (PODIL; blad indeksu): {e}"
            )
    _write_cz_sidecar(
        provider,
        target,
        request={"sheet": godlo},
        capability="sheet_files" if is_sm5 else "bbox_raster",
        # an SM5 sheet arrives in Krovak, a TM33 tile in the UTM33/ETRS89 grid
        horizontal_crs="EPSG:5514" if is_sm5 else "EPSG:3045",
        nodata=nodata,
        extra=extra or None,
    )
    if not quiet:
        print(f"Downloaded to {target}")
    return 0


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


def _cz_download_bbox(
    args,
    provider,
    bbox: BBox,
    parent_request: dict | None,
    *,
    quiet: bool,
    skip_existing: bool,
) -> int:
    """CZ bbox: one `exportImage` cutout in `<subdir>/bbox/<coords>.tif`.

    The bbox is normalized to the RESULT's CRS (`--target-crs` or native
    5514) - the file name carries the coordinates of the actually requested cutout.
    The request then goes to the server in the native CRS, and the local
    warp in the provider moves it onto the result grid (ADR-024).

    Implementation: ``download.cz_cutout.run_cz_cutout``.
    """
    from kartograf.download.cz_cutout import run_cz_cutout

    image_sr = args.target_crs or "EPSG:5514"

    def announce() -> None:
        # O-3: printed by the provider right before the first exportImage
        if not quiet:
            print(f"Downloading CZ bbox ({provider.resolution}, {image_sr})...")

    try:
        # the CLI prints its own 'Warning:' line - the library log would
        # repeat it on stderr (logging.lastResort; the CLI configures no logging)
        with _library_log_muted("kartograf.download.cz_cutout"):
            result = run_cz_cutout(
                provider,
                bbox,
                output_dir=args.output,
                image_crs=args.target_crs,
                force=not skip_existing,
                parent_request=parent_request,
                on_download=announce,
            )
    except (DownloadError, ValidationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if result.skipped:
        if not quiet:
            print(f"Skipped - already exists at {result.path}")
        _print_legacy_krovak_info(result.path)
        return 0
    if result.all_nodata:
        print(
            f"Warning: {result.path} jest w calosci nodata — obszar poza pokryciem "
            "DMR CUZK (poza granica CZ?)",
            file=sys.stderr,
        )
    if not quiet:
        print(f"Downloaded to {result.path}")
    return 0


def _cmd_download_cz(
    args: argparse.Namespace,
    bbox: BBox | None = None,
    parent_request: dict | None = None,
) -> int:
    """
    Handle the download command for Czech (CUZK) sources.

    Model: :func:`_cmd_download_laz` - a flow outside ``DownloadManager``, because a
    CZ task yields exactly one file (a TM33 tile, an SM5 sheet or an
    `exportImage` cutout), and the sidecars are written by the CLI layer.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments (sheet code / --bbox / --target-crs / --resolution ...).
    bbox : BBox, optional
        Bbox of area mode (``_dispatch_area`` always passes it, also
        with an explicit ``--country cz``); ``None`` = sheet code mode (``args.godlo``).
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

    has_godlo = bbox is None
    # An SM5 sheet is a ready-made DMR 4G file that exists only at 5 m, so the
    # sheet itself determines the resolution; TM33 tiles and bbox cutouts are
    # cut from the service, where 2 m (default) and 5 m are a real choice.
    is_sm5 = has_godlo and detect_system(args.godlo).id == "cz_sm5"
    resolution = args.resolution or ("5m" if is_sm5 else "2m")
    vertical_crs = args.vertical_crs or "Bpv"

    if resolution == "1m":
        print(
            "Error: CZ nie ma rozdzielczosci 1m — dostepne: 2m (DMR 5G), 5m (DMR 4G)",
            file=sys.stderr,
        )
        return 1
    if is_sm5 and resolution != "5m":
        # contradictory request: rejected before the provider (no network)
        # and before the "Downloading" announcement
        print(
            f"Error: Arkusze SM5 sa dostepne tylko w 5m (DMR 4G) — pomin "
            f"--resolution albo podaj 5m; dla {resolution} uzyj godla TM33 "
            f"albo --bbox [godlo: {args.godlo}]",
            file=sys.stderr,
        )
        return 1
    if getattr(args, "system", None) is not None:
        print(
            "Error: --system dotyczy tylko PL (godla CZ wykrywane wzorcem)",
            file=sys.stderr,
        )
        return 1
    if has_godlo and args.target_crs is not None:
        # the provider ignores target_crs in sheet code mode - silence would be a lie
        raise ValidationError(
            "--target-crs dziala tylko z --bbox/--geometry; godlo wyznacza "
            "zasieg i uklad produktu (arkusz SM5 1:1 w EPSG:5514, kafel TM33 "
            "na siatce EPSG:3045)"
        )

    # D16: --force as in the PL path - the cache read (SM5 sheet index)
    # is skipped, the fresh entry is written
    cache = _cli_metadata_cache(bool(args.force))
    try:
        try:
            provider = create_dmr_provider(
                resolution=resolution,
                cache=cache,
                target_crs=None if has_godlo else args.target_crs,
                vertical_crs=vertical_crs,
            )
        except TransformError as e:
            return _print_transform_error(e)
        except ValidationError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        quiet = args.quiet
        skip_existing = not args.force
        if bbox is None:
            return _cz_download_godlo(
                args, provider, quiet=quiet, skip_existing=skip_existing
            )
        return _cz_download_bbox(
            args,
            provider,
            bbox,
            parent_request,
            quiet=quiet,
            skip_existing=skip_existing,
        )
    finally:
        cache.close()


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
    country_flag = getattr(args, "country", "auto")
    if country_flag == "cz":
        if _reject_non_nmt_for_cz(getattr(args, "product", "nmt")):
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

    if _resolve_pl_sentinels(args):
        return 1
    if args.target_crs is not None:
        return _download_pl_cutout(args, bbox, parent_request)

    target_scale = args.scale or "1:10000"
    layer = getattr(args, "layer", None)

    try:
        godlo_list = find_sheets_for_geometry(
            filepath, target_scale=target_scale, layer=layer, system=args.system
        )
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not godlo_list:
        print("Error: No sheets found for the given geometry", file=sys.stderr)
        return 1

    return _download_pl_sheet_list(
        args,
        godlo_list,
        parent_request,
        what=f"geometry {filepath.name}",
        target_scale=target_scale,
    )
