"""
``elevation download`` and ``imagery download``: flags -> ``download_data``/
``check_data`` (Z1).

The CLI only translates flags into the library arguments (``--bbox`` text,
``pl=..,cz=..`` per-country values), reads and writes the plan file, prints
the ``DataReport`` (status lines, summary, ``Error:`` of failed parts),
prints data notices (``Info:``/``Warning:``) when the library emits them and
draws the progress bar. Every data decision is in ``kartograf.download``.
The helpers below are shared by ``landcover download``, ``soil download``
and ``soil hsg``.
"""

import argparse
import sys
import threading
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from kartograf.cli._args import parse_bbox_arg, parse_per_country
from kartograf.cli._json import emit_document, wants_json
from kartograf.download.data import DataReport, check_data, download_data
from kartograf.download.fetch import UpdateMode, VersionedFile
from kartograf.download.manager import DownloadProgress
from kartograf.download.options import require_product
from kartograf.download.plan import PlanItem, UpdatePlan
from kartograf.exceptions import ValidationError
from kartograf.notices import CACHE_DISABLED, SHEET_LIST, Notice
from kartograf.serialization import Document


class _ProgressPrinter:
    """Progress bar callback; ``pending`` = last line without a line ending.

    With ``--workers > 1`` ``pending`` reflects the last write (at worst
    a redundant or missing ``\\n`` before ``Error:``). ``used``: something was
    drawn (a blank line separates the bar from the status lines). Campaign
    lines may come from worker threads: one lock keeps them whole.
    """

    def __init__(self, workers: int = 1) -> None:
        self.pending = False
        self.used = False
        self.workers = workers
        self._lock = threading.Lock()

    def __call__(self, progress: DownloadProgress) -> None:
        """Print progress bar and status (``start``: a transfer begins;
        ``tiles``: LAZ tile counter; ``campaigns``/``campaign``: flights of
        a sheet with several selected campaigns)."""
        if progress.status in ("campaigns", "campaign"):
            with self._lock:
                self._campaign_line(progress)
            return
        if progress.status == "start":
            if progress.total > 1:  # a sheet hierarchy: "<code> w skali <scale>"
                print(
                    f"Pobieranie {progress.total} arkuszy z {progress.sheet} "
                    f"({progress.message})"
                )
                print()
            else:
                print(f"Pobieranie {progress.sheet} ({progress.message})...")
            return
        if progress.status == "tiles":
            if progress.current == 0:
                print(
                    f"Znaleziono kafli LAZ: {progress.total}. Pobieranie, "
                    f"watki: {self.workers}..."
                )
                print()
                return
            print(f"\r  {progress.current}/{progress.total} kafli", end="", flush=True)
            self.pending = True
            return
        bar_width = 30
        filled = int(bar_width * progress.current / max(progress.total, 1))
        bar = "=" * filled + "-" * (bar_width - filled)

        status_icon = {
            "downloading": ">",
            "completed": "+",
            "skipped": "o",
            "failed": "x",
            # D11: a sheet with no data at the source (sea, area abroad) is an
            # expected state, not a failure - a different icon than a download failure
            "no_coverage": "0",
        }.get(progress.status, " ")

        line = (
            f"\r[{bar}] {progress.current}/{progress.total} "
            f"{status_icon} {progress.sheet}"
        )
        line = line.ljust(80)  # overwrite previous longer lines
        if progress.status in ("completed", "failed", "no_coverage"):
            print(line, flush=True)
            self.pending = False
        else:
            print(line, end="", flush=True)
            self.pending = True

    def _campaign_line(self, progress: DownloadProgress) -> None:
        """``Kampanie <arkusz> (do pobrania k z n): ...`` before the first
        flight download of a sheet, then ``Pobieranie <arkusz> <etykieta>
        (k/n)...`` before each one; ends a pending bar line first."""
        if self.pending:
            print()
            self.pending = False
        self.used = True
        if progress.status == "campaigns":
            print(
                f"  Kampanie {progress.sheet} (do pobrania {progress.current} z "
                f"{progress.total}): {progress.message}",
                flush=True,
            )
        else:
            print(
                f"  Pobieranie {progress.sheet} {progress.message} "
                f"({progress.current}/{progress.total})...",
                flush=True,
            )


def create_progress_callback(quiet: bool = False, workers: int = 1):
    """Progress callback for downloads (``None`` under ``quiet``)."""
    if quiet:
        return None
    return _ProgressPrinter(workers)


def _end_progress(on_progress) -> None:
    """End a bar line left unterminated (the last unit ``skipped``, a LAZ
    tile counter) before the status lines and errors."""
    if getattr(on_progress, "pending", False) is True:
        print()
        on_progress.pending = False


# Cache warnings already printed by the current command (several tracks may
# open the same cache file, e.g. a border bbox under ``auto``).
_cache_warnings_shown: set[str] = set()


def _warn_cache_disabled(notice: Notice) -> None:
    """Print one disabled-cache warning per CLI command."""
    if notice.text in _cache_warnings_shown:
        return
    _cache_warnings_shown.add(notice.text)
    print(f"Warning: {notice.text}", file=sys.stderr, flush=True)


def _print_notice(notice: Notice) -> None:
    """Print each library data notice when it is emitted, also in quiet mode.

    A disabled-cache warning is printed once per command (several tracks may
    open the same cache file).
    """
    if notice.code == CACHE_DISABLED:
        _warn_cache_disabled(notice)
        return
    prefix = "Info" if notice.level == "info" else "Warning"
    print(f"{prefix}: {notice.text}", file=sys.stderr)


def notice_printer(args: argparse.Namespace) -> Callable[[Notice], None] | None:
    """The ``on_notice`` of a command: it prints each data notice on stderr. With
    ``--json`` there is none - the notices are in the document (``notices``)."""
    return None if wants_json(args) else _print_notice


def progress_printer(args: argparse.Namespace, workers: int = 1):
    """The ``on_progress`` of a command: the bar of ``create_progress_callback``
    (none under ``--quiet`` and ``--json``)."""
    return create_progress_callback(args.quiet or wants_json(args), workers)


# =============================================================================
# Plan file and status lines (shared by every store command)
# =============================================================================


@dataclass
class _PlanContext:
    """Update plan of one run: ``--check-updates`` collects one plan per
    request (``plans``, written as ONE file); ``--upgrade --plan`` reads the
    file once (``loaded``). ``--json``: the document of the run waits in
    ``document`` until the plan file is written, then it is printed."""

    plans: list[UpdatePlan] = field(default_factory=list)
    loaded: UpdatePlan | None = None
    document: Document | None = None


def _plan_context(args: argparse.Namespace) -> _PlanContext:
    """The run's plan context (a bare ``Namespace`` in tests: a fresh one)."""
    ctx = getattr(args, "plan_ctx", None)
    if not isinstance(ctx, _PlanContext):
        ctx = _PlanContext()
        args.plan_ctx = ctx
    return ctx


def _present(
    args: argparse.Namespace, document: Document, render: Callable[[], int]
) -> int:
    """The outcome of a command: its text (``render`` prints it and gives the exit
    code) or, with ``--json``, the document - kept until ``run_with_plan_file`` has
    written the plan file, so that a failed write is the only thing reported."""
    if wants_json(args):
        _plan_context(args).document = document
        return 0
    return render()


def run_with_plan_file(
    args: argparse.Namespace, body: Callable[[argparse.Namespace], int]
) -> int:
    """Plan file cycle of a store command (spec 4.4).

    ``--upgrade --plan`` reads the plan before any work; ``--check-updates
    --plan`` writes the plans collected by ``body`` as ONE file after it -
    into an existing directory, checked before any request. A plan that
    cannot be read and a directory that does not exist are input errors
    (``ValidationError`` of the option ``plan``, no work done); a plan that
    cannot be written is the ``OSError`` of the write (``main`` reports it).

    With ``--json`` the body keeps its document (``_present``): the plan file is
    written first, the document printed after it and the ``Info:`` line is not
    (the file is the same document as stdout).
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
            raise ValidationError(
                f"nie udalo sie odczytac planu {plan_file}: {e}", option="plan"
            ) from e
        except ValidationError as e:
            e.option = "plan"
            raise
    if getattr(args, "check_updates", False) and plan_file:
        directory = Path(plan_file).parent
        if not directory.is_dir():
            raise ValidationError(
                f"--plan {plan_file}: katalog {directory} nie istnieje - "
                "utworz go albo podaj inny plik planu",
                option="plan",
            )
    rc = body(args)
    wrote_plan = False
    if getattr(args, "check_updates", False) and plan_file and ctx.plans:
        plan = ctx.plans[0]
        for other in ctx.plans[1:]:
            plan = plan.merge(other)
        Path(plan_file).write_text(plan.to_json(), encoding="utf-8")
        wrote_plan = True
    if wants_json(args):
        if ctx.document is None:
            raise RuntimeError("--json: the command left no document to print")
        return emit_document(ctx.document)
    if wrote_plan:
        print(f"Info: zapisano plan aktualizacji {plan_file}", file=sys.stderr)
    return rc


def _update_mode(args: argparse.Namespace) -> UpdateMode | None:
    """``update`` of a store command: ``--upgrade`` / ``--force``."""
    if getattr(args, "upgrade", False):
        return "upgrade"
    return "force" if getattr(args, "force", False) else None


_PLAN_TEXT = {
    "current": "aktualne",
    "missing": "do pobrania",
    "unverifiable": "nie da sie sprawdzic bez pobrania",
}


def store_path_label(item: PlanItem) -> str:
    """Subject of a plan line: the position's path below ``--output``, as in
    the status lines of the download (one format in both modes; a derived
    file and its raw ZIP of the same TERYT get different lines)."""
    return "/".join(part for part in (item.segment, item.hierarchy, item.name) if part)


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
    return f"{store_path_label(item)}: {text}"


def _report_plan(args: argparse.Namespace, plan: UpdatePlan) -> int:
    """``--check-updates``: print the positions (stdout, also with ``-q``) and
    keep the plan for ``--plan``. A position that could not be checked = 1."""
    _plan_context(args).plans.append(plan)

    def render() -> int:
        for item in plan.items:
            print(_plan_line(item))
        return 0 if plan.ok else 1

    return _present(args, plan, render)


def _report_stale(stale: Sequence[PlanItem]) -> int:
    """``--upgrade --plan``: positions whose source changed since the plan."""
    for item in stale:
        print(
            f"Error: {store_path_label(item)}: zrodlo zmienilo sie od planu "
            f"({item.available_label or item.available_signal}) - sprawdz "
            "ponownie (--check-updates)",
            file=sys.stderr,
        )
    return 1 if stale else 0


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
    """Render the selected version of each file of one unit."""
    lines = []
    for file in files:
        status = file.status
        dirname = file.version_path.parent.name
        label = dirname.rsplit("_", 1)[0] if status != "new" else dirname
        text = f"{sheet}: {_STATUS_TEXT.get(status, status)} {label}"
        if status == "relabeled":
            text += f" (plik identyczny z {file.same_as or 'istniejaca wersja'})"
        if status == "local" and newer is not None:
            text += f"; dostepna nowsza {newer} (--upgrade)"
            newer = None
        lines.append(text)
    return lines


def _status_line(unit: str, file: VersionedFile, update: UpdateMode | None) -> str:
    """Status line of one file (``unit``: its path below ``--output``); a
    local version the default mode did not compare with the source (no cheap
    signal, or not asked: ADR-036 erratum 3) gets ``(bez sprawdzania;
    --check-updates)``."""
    (line,) = _status_lines(unit, (file,), file.newer)
    unchecked = file.unverified in ("none", "unchecked")
    if file.status == "local" and unchecked and update is None:
        line += " (bez sprawdzania; --check-updates)"
    return line


def _report_file(
    args: argparse.Namespace,
    unit: str,
    file: VersionedFile | None,
    update: UpdateMode | None,
) -> None:
    """Status line of one land cover/HSG file (data notices come from the API)."""
    if file is None:
        return
    if not args.quiet:
        print(_status_line(unit, file, update))


def _unit_of(path: Path, output_dir: Path) -> str:
    """Unit of a file in status lines: its path below ``--output``."""
    try:
        return Path(path).relative_to(output_dir).as_posix()
    except ValueError:
        return str(path)


def _print_version_summary(
    statuses: Sequence[str], failed: int, output_dir: Path
) -> None:
    """Counters of the files of the request (spec 4.5); ``uzyte ponownie``
    (HSG, D33) only when a derived file was reused."""
    counts = Counter(statuses)
    reused = f"uzyte ponownie: {counts['reused']}, " if counts["reused"] else ""
    print(
        f"Nowe: {counts['new']}, nowa etykieta: {counts['relabeled']}, "
        f"bez zmian: {counts['unchanged']}, lokalne: {counts['local']}, "
        f"{reused}bledy: {failed} ({output_dir})"
    )


# =============================================================================
# download
# =============================================================================


def download_task_arguments(args: argparse.Namespace) -> dict:
    """Data options shared by a group download and a project task."""
    return {
        "product": args.product,
        "sheet": args.sheet,
        "bbox": parse_bbox_arg(args.bbox, args.bbox_crs) if args.bbox else None,
        "geometry": Path(args.geometry) if getattr(args, "geometry", None) else None,
        "layer": getattr(args, "layer", None),
        "country": args.country,
        "vertical_crs": parse_per_country(
            getattr(args, "vertical_crs", None), "--vertical-crs"
        ),
        "resolution": parse_per_country(
            getattr(args, "resolution", None), "--resolution"
        ),
        "model": getattr(args, "model", None),
        "format": getattr(args, "format", None),
        "sheet_system": getattr(args, "sheet_system", None),
        "scale": getattr(args, "scale", None),
        "cutout": getattr(args, "cutout", False),
        "horizontal_crs": getattr(args, "horizontal_crs", None),
        "coverage": getattr(args, "coverage", None),
        "direction": getattr(args, "direction", None),
        "year": getattr(args, "year", None),
        "min_year": getattr(args, "min_year", None),
        "max_year": getattr(args, "max_year", None),
        "all_campaigns": getattr(args, "all_campaigns", False),
        "full_sheet": getattr(args, "full_sheet", False),
        "min_density": getattr(args, "min_density", None),
    }


def _download_arguments(args: argparse.Namespace) -> dict:
    """Library request, including the store, from the same task translation."""
    return {**download_task_arguments(args), "output_dir": args.output}


def cmd_download(
    args: argparse.Namespace, products: Sequence[str] | None = None
) -> int:
    """``<grupa> download`` of sheet products (plan file cycle around
    ``_cmd_download``).

    ``products``: the ``--product`` values of the group; a missing
    ``--product`` names only them (ADR-039: the group checks the presence of
    its choice flag, as every group with ``--product``; the value is checked
    by argparse ``choices`` and by the library). ``None``: the library
    message naming every product of ``download_data``.
    """
    if products is not None:
        require_product(args.product, products)
    return run_with_plan_file(args, _cmd_download)


def _data_notices(args: argparse.Namespace) -> Callable[[Notice], None] | None:
    """The ``on_notice`` of ``elevation download``/``imagery download``: the data
    notices on stderr, the sheet list header as the preamble of the result on
    stdout (D15); none with ``--json`` (every notice is in the document)."""
    if wants_json(args):
        return None
    quiet = args.quiet

    def on_notice(notice: Notice) -> None:
        if notice.code == SHEET_LIST:
            if not quiet:
                print(notice.text)
                print()
            return
        _print_notice(notice)

    return on_notice


def _cmd_download(args: argparse.Namespace) -> int:
    """One ``download_data``/``check_data`` call after the plan file is read."""
    _cache_warnings_shown.clear()
    arguments = _download_arguments(args)
    on_notice = _data_notices(args)
    if getattr(args, "check_updates", False):
        return _report_plan(args, check_data(**arguments, on_notice=on_notice))
    workers = getattr(args, "workers", 4) or 1
    on_progress = progress_printer(args, workers)
    report = download_data(
        **arguments,
        update=_update_mode(args),
        plan=_plan_context(args).loaded,
        workers=workers,
        on_progress=on_progress,
        on_notice=on_notice,
    )
    return _present(args, report, lambda: _print_report(args, report, on_progress))


def _print_report(args: argparse.Namespace, report: DataReport, on_progress) -> int:
    """Status lines (the path of each file below ``--output``), summary,
    failures and stale positions of a report."""
    update = _update_mode(args)
    _end_progress(on_progress)
    if not args.quiet:
        if getattr(on_progress, "used", False):
            print()  # campaign lines: a blank line before the status lines
        output = Path(args.output)
        for unit_file in report.files:
            print(
                _status_line(
                    _unit_of(unit_file.file.path, output), unit_file.file, update
                )
            )
        several = (
            args.product == "laz"
            or len(report.files) > 1
            or bool(getattr(args, "scale", None))
            or (args.sheet is None and not getattr(args, "cutout", False))
        )
        # no files (the source or the index failed): the Error lines tell it
        # all, a "Nowe: 0, ..., bledy: 0" summary would contradict them
        if several and report.files:
            _print_version_summary(
                [f.file.status for f in report.files],
                sum(1 for f in report.failed if f.kind == "download"),
                Path(args.output) / ("laz" if args.product == "laz" else ""),
            )
    for failure in report.failed:
        print(f"Error: {failure.error}", file=sys.stderr)
    _report_stale(report.stale)
    return 0 if report.ok else 1
