"""``elevation download`` and ``imagery download``.

Flags -> ``download_data``/``check_data`` (Z1).

The CLI only translates flags into the library arguments (``library_arguments``:
the catalog says what each flag is), reads and writes the plan file, prints
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
from typing import Any, Protocol

from kartograf.cli._args import library_arguments, store_dir, target_arguments
from kartograf.cli._json import command_id, emit_result, wants_json
from kartograf.cli._language import language, localized
from kartograf.download.data import DataReport, check_data, download_data
from kartograf.download.fetch import UpdateMode, VersionedFile
from kartograf.download.manager import DownloadProgress
from kartograf.download.options import require_product
from kartograf.download.plan import PlanItem, UpdatePlan
from kartograf.envelope import exit_code_of
from kartograf.exceptions import ValidationError
from kartograf.messages import message, reason
from kartograf.notices import CACHE_DISABLED, SHEET_LIST, Notice
from kartograf.output import store_only
from kartograf.serialization import Document


class _ProgressPrinter:
    r"""Progress bar callback; ``pending`` = last line without a line ending.

    With ``--workers > 1`` ``pending`` reflects the last write (at worst
    a redundant or missing ``\n`` before ``Error:``). ``used``: something was
    drawn (a blank line separates the bar from the status lines). Campaign
    lines may come from worker threads: one lock keeps them whole.
    """

    def __init__(self, workers: int = 1) -> None:
        self.pending = False
        self.used = False
        self.workers = workers
        self._lock = threading.Lock()

    def __call__(self, progress: DownloadProgress) -> None:
        """Print progress bar and status.

        ``start``: a transfer begins; ``tiles``: LAZ tile counter;
        ``campaigns``/``campaign``: flights of a sheet with several selected campaigns.
        """
        if progress.status in ("campaigns", "campaign"):
            with self._lock:
                self._campaign_line(progress)
            return
        if progress.status == "start":
            if progress.total > 1:  # a sheet hierarchy: "<code> w skali <scale>"
                print(
                    message(
                        "cli.download_sheets_progress",
                        lang=language(),
                        total=progress.total,
                        sheet=progress.sheet,
                        message=progress.message,
                    )
                )
                print()
            else:
                print(
                    message(
                        "cli.download_sheet_progress",
                        lang=language(),
                        sheet=progress.sheet,
                        message=progress.message,
                    )
                )
            return
        if progress.status == "tiles":
            if progress.current == 0:
                print(
                    message(
                        "cli.laz_tiles_found",
                        lang=language(),
                        total=progress.total,
                        workers=self.workers,
                    )
                )
                print()
                return
            print(
                "\r"
                + message(
                    "cli.tiles_progress",
                    lang=language(),
                    current=progress.current,
                    total=progress.total,
                ),
                end="",
                flush=True,
            )
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
        """Print the campaign lines of a sheet.

        ``Campaigns <sheet> (to download k of n): ...`` before the first flight download
        of a sheet, then ``Downloading <sheet> <label> (k/n)...`` before each one;
        ends a pending bar line first.
        """
        if self.pending:
            print()
            self.pending = False
        self.used = True
        if progress.status == "campaigns":
            print(
                message(
                    "cli.campaigns_to_download",
                    lang=language(),
                    sheet=progress.sheet,
                    current=progress.current,
                    total=progress.total,
                    message=progress.message,
                ),
                flush=True,
            )
        else:
            print(
                message(
                    "cli.campaign_download_progress",
                    lang=language(),
                    sheet=progress.sheet,
                    message=progress.message,
                    current=progress.current,
                    total=progress.total,
                ),
                flush=True,
            )


def create_progress_callback(
    quiet: bool = False, workers: int = 1
) -> _ProgressPrinter | None:
    """Progress callback for downloads (``None`` under ``quiet``)."""
    if quiet:
        return None
    return _ProgressPrinter(workers)


def _end_progress(on_progress: Any) -> None:
    """End a bar line left unterminated before the status lines and errors.

    It is the last unit ``skipped`` or a LAZ tile counter.
    """
    if getattr(on_progress, "pending", False) is True:
        print()
        on_progress.pending = False


# Cache warnings already printed by the current command (several tracks may
# open the same cache file, e.g. a border bbox under ``auto``).
_cache_warnings_shown: set[str] = set()


def _warn_cache_disabled(notice: Notice) -> None:
    """Print one disabled-cache warning per CLI command."""
    if notice.message in _cache_warnings_shown:
        return
    _cache_warnings_shown.add(notice.message)
    print(f"Warning: {localized(notice.message)}", file=sys.stderr, flush=True)


def _print_notice(notice: Notice) -> None:
    """Print each library data notice when it is emitted, also in quiet mode.

    A disabled-cache warning is printed once per command (several tracks may
    open the same cache file).
    """
    if notice.code == CACHE_DISABLED:
        _warn_cache_disabled(notice)
        return
    prefix = "Info" if notice.level == "info" else "Warning"
    print(f"{prefix}: {localized(notice.message)}", file=sys.stderr)


def notice_printer(args: argparse.Namespace) -> Callable[[Notice], None] | None:
    """Return the ``on_notice`` of a command: it prints each data notice on stderr.

    With ``--json`` there is none - the notices are in the document (``notices``).
    """
    return None if wants_json(args) else _print_notice


def progress_printer(
    args: argparse.Namespace, workers: int = 1
) -> _ProgressPrinter | None:
    """Return the ``on_progress`` of a command.

    The bar of ``create_progress_callback`` (none under ``--quiet`` and ``--json``).
    """
    return create_progress_callback(args.quiet or wants_json(args), workers)


# =============================================================================
# Plan file and status lines (shared by every store command)
# =============================================================================


@dataclass
class _PlanContext:
    """Update plan of one run.

    ``--check`` collects one plan per request (``plans``, written as ONE file);
    ``--upgrade --plan`` reads the file once (``loaded``). ``document``: the result of
    the run (a plan or a report); with ``--json`` it waits until the plan file is
    written, then it is printed.
    """

    plans: list[UpdatePlan] = field(default_factory=list)
    loaded: UpdatePlan | None = None
    document: Document | None = None


def _plan_context(args: argparse.Namespace) -> _PlanContext:
    """Return the run's plan context (a bare ``Namespace`` in tests: a fresh one)."""
    ctx = getattr(args, "plan_ctx", None)
    if not isinstance(ctx, _PlanContext):
        ctx = _PlanContext()
        args.plan_ctx = ctx
    return ctx


def _present(
    args: argparse.Namespace, document: Document, render: Callable[[], int]
) -> int:
    """Return the outcome of a command.

    Its text (``render`` prints it and gives the exit code) or, with ``--json``, the
    document - kept until ``run_with_plan_file`` has written the plan file, so that a
    failed write is the only thing reported.
    """
    _plan_context(args).document = document
    if wants_json(args):
        return 0
    return render()


def _ran_nothing(document: Document | None) -> bool:
    """Return a report with no file, no failure and no stale position.

    The five reports of ``kartograf-download/1`` share these keys; a plan has none of
    them.
    """
    names = ("files", "raw", "inputs", "failed", "stale")
    return document is not None and not any(getattr(document, n, None) for n in names)


def run_with_plan_file(
    args: argparse.Namespace, body: Callable[[argparse.Namespace], int]
) -> int:
    """Plan file cycle of a store command (spec 4.4).

    ``--upgrade --plan`` reads the plan before any work; ``--check
    --plan`` writes the plans collected by ``body`` as ONE file after it -
    a file in an existing directory, checked before any request. A plan that
    cannot be read, a directory in place of the file and a directory that does
    not exist are input errors (``ValidationError`` of the option ``plan``, no
    work done); a plan that cannot be written is the ``OSError`` of the write
    (``main`` reports it). ``--upgrade --plan`` that ran no position of the plan
    (all current, or done already) says so with an ``Info:`` line.

    With ``--json`` the body keeps its document (``_present``): the plan file is
    written first, the document printed after it and the ``Info:`` lines are not
    (the file is the same document as stdout).
    """
    if getattr(args, "output_dir", None) is not None and getattr(args, "plan", None):
        raise store_only("--plan")
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
                message("cli.plan_read_failed", plan_file=plan_file, error=reason(e)),
                option="plan",
            ) from e
        except ValidationError as e:
            e.option = "plan"
            raise
    if getattr(args, "check", False) and plan_file:
        if Path(plan_file).is_dir():
            raise ValidationError(
                message(
                    "cli.plan_is_directory",
                    plan_file=plan_file,
                    path=Path(plan_file) / "plan.json",
                ),
                option="plan",
            )
        directory = Path(plan_file).parent
        if not directory.is_dir():
            raise ValidationError(
                message(
                    "cli.plan_dir_missing", plan_file=plan_file, directory=directory
                ),
                option="plan",
            )
    rc = body(args)
    wrote_plan = False
    if getattr(args, "check", False) and plan_file and ctx.plans:
        plan = ctx.plans[0]
        for other in ctx.plans[1:]:
            plan = plan.merge(other)
        Path(plan_file).write_text(plan.to_json(), encoding="utf-8")
        wrote_plan = True
    if wants_json(args):
        if ctx.document is None:
            raise RuntimeError("--json: the command left no document to print")
        check = bool(getattr(args, "check", False))
        return emit_result(command_id(args), ctx.document, check=check)
    if wrote_plan:
        print(
            message("cli.plan_saved_info", lang=language(), plan_file=plan_file),
            file=sys.stderr,
        )
    elif getattr(args, "upgrade", False) and plan_file and _ran_nothing(ctx.document):
        print(
            message("cli.plan_nothing_to_do", lang=language(), plan_file=plan_file),
            file=sys.stderr,
        )
    return rc


def _update_mode(args: argparse.Namespace) -> UpdateMode | None:
    """``update`` of a store command: ``--upgrade`` / ``--force``.

    The two exclude each other; ``--check --force`` is a plan (it never gets here).
    """
    upgrade = getattr(args, "upgrade", False)
    force = getattr(args, "force", False)
    if upgrade and force:
        raise ValidationError(
            message("cli.upgrade_force_exclusive"),
            option="force",
            options=("upgrade", "force"),
        )
    if upgrade:
        return "upgrade"
    return "force" if force else None


_PLAN_TEXT = {
    "current": message("cli.status_current"),
    "missing": message("cli.plan_text_missing"),
    "unverifiable": message("cli.plan_text_unverifiable"),
}
# The positions of a plain write (``--output-dir``): what the run would do with the
# file and why it would refuse it.
_ACTION_TEXT = {
    "write": message("cli.plan_action_write"),
    "replace": message("cli.plan_action_replace"),
}
_CONFLICT_TEXT = {
    "output_exists": message("cli.plan_conflict_output_exists"),
    "duplicate_output_name": message("cli.plan_conflict_duplicate_output_name"),
    "output_in_store": message("cli.plan_conflict_output_in_store"),
    "nested_store": message("cli.plan_conflict_nested_store"),
    "not_empty": message("cli.plan_conflict_not_empty"),
}


def plan_line(item: PlanItem) -> str:
    """Return the line of ``--check`` for one position of a plan."""
    text: str
    if item.action is not None:
        if item.action in _ACTION_TEXT:
            text = localized(_ACTION_TEXT[item.action])
        else:
            text = message(
                "cli.plan_conflict",
                lang=language(),
                reason=_CONFLICT_TEXT.get(item.reason or "", item.reason),
            )
        return f"{item.store_path}: {text}"
    if item.status == "newer":
        signal = item.available_signal or {}
        available = (
            item.available_label or signal.get("etag") or signal.get("last_modified")
        )
        text = message(
            "cli.plan_newer",
            lang=language(),
            available=available,
            local_label=item.local_label,
        )
    elif item.status == "check_failed":
        text = message("cli.plan_check_failed", lang=language(), error=item.error)
    else:
        text = localized(_PLAN_TEXT[item.status])
        label = item.local_label or item.available_label
        if label:
            text += f" ({label})"
    return f"{item.store_path}: {text}"


def _report_plan(args: argparse.Namespace, plan: UpdatePlan) -> int:
    """Run ``--check``.

    Print the positions (stdout, also with ``-q``) and keep the plan for ``--plan``. A
    position that could not be checked = 1.
    """
    _plan_context(args).plans.append(plan)

    def render() -> int:
        for item in plan.items:
            print(plan_line(item))
        return exit_code_of(plan, check=True)

    return _present(args, plan, render)


def _report_stale(stale: Sequence[PlanItem]) -> int:
    """``--upgrade --plan``: positions whose source changed since the plan."""
    for item in stale:
        print(
            message(
                "cli.plan_source_stale",
                lang=language(),
                store_path=item.store_path,
                available_label=item.available_label or item.available_signal,
            ),
            file=sys.stderr,
        )
    return 1 if stale else 0


_STATUS_TEXT = {
    "new": message("cli.status_new"),
    "relabeled": message("cli.status_relabeled"),
    "unchanged": message("cli.status_unchanged"),
    "local": message("cli.status_local"),
    "reused": message("cli.status_reused"),
    "written": message("cli.status_written"),
    "replaced": message("cli.status_replaced"),
}


def _status_lines(
    sheet: str, files: Sequence[VersionedFile], newer: str | None
) -> list[str]:
    """Render the selected version of each file of one unit."""
    lines = []
    for file in files:
        status = file.status
        if status in ("written", "replaced"):  # a plain file has no version
            lines.append(f"{sheet}: {localized(_STATUS_TEXT[status])}")
            continue
        dirname = file.version_path.parent.name
        label = dirname.rsplit("_", 1)[0] if status != "new" else dirname
        text = f"{sheet}: {localized(_STATUS_TEXT.get(status, status))} {label}"
        if status == "relabeled":
            text += message(
                "cli.relabeled_same_as",
                lang=language(),
                same_as=file.same_as
                or message("cli.existing_version", lang=language()),
            )
        if status == "local" and newer is not None:
            text += message("cli.newer_available", lang=language(), newer=newer)
            newer = None
        lines.append(text)
    return lines


def _status_line(unit: str, file: VersionedFile, update: UpdateMode | None) -> str:
    """Return the status line of one file.

    ``unit`` is its path below ``--root``; a local version the default mode did not
    compare with the source (no cheap signal, or not asked: ADR-036 erratum 3) gets
    ``(not checked; --check)``.
    """
    (line,) = _status_lines(unit, (file,), file.newer)
    unchecked = file.unverified in ("none", "unchecked")
    if file.status == "local" and unchecked and update is None:
        line += message("cli.unchecked_hint", lang=language())
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


def _unit_of(path: Path, root: Path) -> str:
    """Return the unit of a file in status lines: its path below ``--root``."""
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return str(path)


class _Written(Protocol):
    """What a report says of where it wrote (``WriteTarget`` and the ``root`` field)."""

    @property
    def root(self) -> Path | None:
        """Return the store root of a store report."""

    @property
    def output_dir(self) -> Path | None:
        """Return the directory of a plain report."""


def _written_to(args: argparse.Namespace, report: _Written) -> Path:
    """Return what the status lines of a report name files below.

    It is the output directory of a plain report and the store root of a store report;
    a report built by hand names neither, and the store of the command stands in.
    """
    if report.output_dir is not None:
        return report.output_dir
    return report.root if report.root is not None else store_dir(args)


def _print_version_summary(
    statuses: Sequence[str], failed: int, root: Path, *, plain: bool = False
) -> None:
    """Print the counters of the files of the request (spec 4.5).

    ``reused`` (HSG, D33) only when a derived file was reused; a plain write
    (``plain``) counts the files it ``written`` and ``replaced``, since it has no
    versions.
    """
    counts = Counter(statuses)
    if plain:
        print(
            message(
                "cli.plain_summary",
                lang=language(),
                counts_written=counts["written"],
                counts_replaced=counts["replaced"],
                failed=failed,
                root=root,
            )
        )
        return
    reused = (
        message("cli.summary_reused", lang=language(), counts_reused=counts["reused"])
        if counts["reused"]
        else ""
    )
    print(
        message(
            "cli.version_summary",
            lang=language(),
            counts_new=counts["new"],
            counts_relabeled=counts["relabeled"],
            counts_unchanged=counts["unchanged"],
            counts_local=counts["local"],
            reused=reused,
            failed=failed,
            root=root,
        )
    )


# =============================================================================
# download
# =============================================================================


def cmd_download(
    args: argparse.Namespace, products: Sequence[str] | None = None
) -> int:
    """Run ``<grupa> download`` of sheet products.

    It is the plan file cycle around ``_cmd_download``.

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
    """Return the ``on_notice`` of ``elevation download``/``imagery download``.

    The data notices on stderr, the sheet list header as the preamble of the result on
    stdout (D15); none with ``--json`` (every notice is in the document).
    """
    if wants_json(args):
        return None
    quiet = args.quiet

    def on_notice(notice: Notice) -> None:
        if notice.code == SHEET_LIST:
            if not quiet:
                print(localized(notice.message))
                print()
            return
        _print_notice(notice)

    return on_notice


def _cmd_download(args: argparse.Namespace) -> int:
    """One ``download_data``/``check_data`` call after the plan file is read."""
    _cache_warnings_shown.clear()
    arguments: dict[str, Any] = {**library_arguments(args), **target_arguments(args)}
    on_notice = _data_notices(args)
    if getattr(args, "check", False):
        return _report_plan(
            args,
            check_data(
                **arguments, force=getattr(args, "force", False), on_notice=on_notice
            ),
        )
    workers = getattr(args, "workers", 4)
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


def _print_report(
    args: argparse.Namespace, report: DataReport, on_progress: object
) -> int:
    """Print status lines, summary, failures and stale positions of a report.

    The status lines name the path of each file below ``--root``.
    """
    update = _update_mode(args)
    _end_progress(on_progress)
    if not args.quiet:
        if getattr(on_progress, "used", False):
            print()  # campaign lines: a blank line before the status lines
        output = _written_to(args, report)
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
        # all, a "New: 0, ..., errors: 0" summary would contradict them
        if several and report.files:
            _print_version_summary(
                [f.file.status for f in report.files],
                sum(1 for f in report.failed if f.kind == "download"),
                output / ("laz" if args.product == "laz" and report.root else ""),
                plain=report.output_dir is not None,
            )
    for failure in report.failed:
        print(f"Error: {localized(failure.error)}", file=sys.stderr)
    _report_stale(report.stale)
    return exit_code_of(report)
