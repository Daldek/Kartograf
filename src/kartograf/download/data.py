"""Download and check elevation data and imagery for the commands.

``download_data`` / ``check_data``: the ``elevation download`` and
``imagery download`` commands (R1, R11).

The whole data logic of the command lives here (Z1): recognizing the sheet
code and the country, ``country="auto"`` with narrowing to PL and partial
success (ADR-023 points 4-5), validation of every country before any
download, per-country values, PL areas expanded to sheets (PL-1992 always
1:10000, PL-2000 ``scale``), ``parent_request`` and the exit rule ``ok``.
The CLI only translates flags into the arguments and prints the
``DataReport``; library calls get the same files, plan and messages.

Messages (inventory of the former CLI lines; Z3, decision 4):

=====================  =======  ==============================================
code                   level    condition
=====================  =======  ==============================================
SHEET_LIST             info     PL area, CZ orthophoto or contour area expanded
                                to a sheet list (header; the CLI prints it on
                                stdout, ``-q`` hides it)
GEOMETRY_LAYER_DEFAULT info     GPKG with several layers, no ``layer``
AUTO_NARROWED_TO_PL    info     ``auto`` + PL-only product or choice (ADR-023
                                pkt 5)
AUTO_NARROWED_TO_CZ    info     ``auto`` + CZ-only product (contours)
AUTO_CLIPPED           info     ``auto``: country part clipped to its envelope
AUTO_AREA_OUTSIDE      info     ``auto``: part of the area outside PL/CZ
AUTO_PARTIAL_SUCCESS   warning  ``auto``: one country failed, another succeeded
LEGACY_CAMPAIGNS_DIR   info     0.7.x ``kampanie/`` directory present
NEWER_AVAILABLE        info     (DownloadManager) newer campaign, local used
CHECK_FAILED           warning  local version used, source check failed (also
                                a GUGiK index down in DownloadManager)
NO_COVERAGE_SOME       warning  some sheets without GUGiK data, >= 1 file
NO_COVERAGE_HINT       info     provider hints for sheets without data
BETTER_COVERAGE        info     older flight with better coverage
LINK_OUTSIDE_RANGE     info     link kept on a flight outside the request
SHEET_CRS_MISMATCH     warning  sheet file CRS differs from the sheet code
INCOMPLETE_CAMPAIGN    warning  newest campaign declares an incomplete sheet
UNVERIFIED_LOCAL       info     ``upgrade``: local version without a signal
CUTOUT_SIZE            info     (PL cutouts) several WCS requests or >= 1 GiB
ALL_NODATA             warning  (NMT/NMPT cutouts, CZ sheet) raster without data
LAZ_SUPERSEDED         info     (download_laz_area) skipped LAZ tiles
CACHE_DISABLED         warning  (open_cache) metadata cache unusable
=====================  =======  ==============================================

The codes of every command (collections, land cover, project) with their
level and condition: ``docs/USAGE.md`` section 2.

Every former ``Error:`` is a ``ValidationError`` (input, raised before any
download), a ``TransformError`` (no safe pinned operation) or a
``UnitFailure`` of the report (a failed country, sheet set or tile set;
``ok=False`` unless ``auto`` partial success applies).
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal, cast

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.config import resolve_root
from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser, find_sheets_for_bbox
from kartograf.download.area import (
    cz_geometry_bbox,
    emit_clipping_notices,
    emit_partial_success,
    geometry_envelope,
    parent_request_for,
    pl_only_flags,
    resolve_geometry_layer,
)
from kartograf.download.arguments import option_error, require_workers
from kartograf.download.countries import (
    countries_for_bbox,
    country_bbox,
    outside_country,
)
from kartograf.download.cutout import PlCutoutResult
from kartograf.download.cz_contours import PRODUCT as CONTOURS
from kartograf.download.fetch import (
    UpdateMode,
    VersionedFile,
    emit_file_notices,
    refreshes_cache,
)
from kartograf.download.manager import (
    DownloadManager,
    DownloadProgress,
    DownloadResult,
    incomplete_text,
    no_coverage_text,
)
from kartograf.download.options import (
    campaign_option_names,
    canonical_bbox,
    canonical_country,
    canonical_crs,
    canonical_format,
    canonical_vertical_crs,
    country_value,
    cz_option_error,
    cz_orto_option_error,
    is_source_file_request,
    parse_sheet,
    pl_file_variant,
    pl_option_error,
    pl_target_scale,
    reject_campaign_opts_with_cutout,
    require_cz_cutout,
    require_geometry_area,
    resolve_pl_options,
    validate_request,
)
from kartograf.download.orto_cutout import ORTO_CUTOUT_PL_ONLY, ImageCutoutResult
from kartograf.download.plan import PlanItem, UpdatePlan, conflict_plan, plain_items
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    NoCoverageError,
    ValidationError,
    YearRangeError,
)
from kartograf.marker import store_refusal
from kartograf.messages import message
from kartograf.notices import (
    AUTO_NARROWED_TO_CZ,
    AUTO_NARROWED_TO_PL,
    BETTER_COVERAGE,
    CHECK_FAILED,
    FULL_SHEET_REDUNDANT,
    INCOMPLETE_CAMPAIGN,
    LEGACY_CAMPAIGNS_DIR,
    LINK_OUTSIDE_RANGE,
    NO_COVERAGE_HINT,
    NO_COVERAGE_SOME,
    OF_SHEETS,
    OF_TILES,
    SHEET_CRS_MISMATCH,
    SHEET_LIST,
    SHEETS,
    SKIPPED_INCOMPLETE,
    UNVERIFIED_LOCAL,
    Notice,
    NoticeSink,
    count_text,
)
from kartograf.output import Mode, Staging, directory_refusal, plain_of, refuse, writing
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import SupersededLazTile
from kartograf.providers.pl.gugik_orto import image_directions, image_source
from kartograf.serialization import Document, EncodeContext
from kartograf.sources.registry import horizontal_crs_for_sheet, sources_for
from kartograf.sources.variants import cz_model_text, cz_models, cz_sheet_system

if TYPE_CHECKING:
    from kartograf.download.storage import FileStorage

FailureKind = Literal[
    "no_coverage", "year_out_of_range", "download", "country", "skipped_incomplete"
]
MAX_HINT_LINES = 5

# ``kartograf-download/1``: the schema of the five command reports (``DataReport``,
# ``CollectionReport``, ``LandCoverReport``, ``SoilReport``, ``HsgReport``; spec
# 5.4.1). One key set in one order for all of them: a class without a field for a
# key gives the value of ``DOWNLOAD_FILL`` (consumers read one shape).
DOWNLOAD_SCHEMA = "kartograf-download/1"
DOWNLOAD_KEYS = (
    "mode",
    "root",
    "output_dir",
    "files",
    "raw",
    "inputs",
    "failed",
    "skipped",
    "stale",
    "superseded",
    "summary",
    "notices",
    "ok",
)
DOWNLOAD_FILL: Mapping[str, object] = {
    "raw": (),
    "inputs": (),
    "skipped": (),
    "superseded": (),
    "summary": None,
}
# The ``status`` of a file in a report (DEV-19.19): ``unchanged`` stands for the store
# words ``local`` (the local version was used, no transfer) and ``reused`` (a derived
# file whose inputs match a version); ``VersionedFile.status`` keeps both words for
# the flow of the tracks.
_DOCUMENT_STATUS: Mapping[str, str] = {"local": "unchanged", "reused": "unchanged"}
_PLAIN_STATUSES = ("written", "replaced")


@dataclass(frozen=True)
class UnitFile:
    """Describe one file of the request.

    One file of the request: ``unit`` = sheet code, LAZ file name, TERYT
    or bbox coordinates (``<coords>`` of a cutout or of a collection area);
    ``country`` = ``"PL"``/``"CZ"`` (``"EU"`` CORINE, ``"GLOBAL"``
    SoilGrids and HSG - the country of the source).
    """

    unit: str
    country: str
    file: VersionedFile

    def __json__(self, ctx: EncodeContext) -> dict[str, object]:
        """Return the entry of ``files[]`` (DEV-19.19, ADR-054 decision 10).

        ``unit`` and ``country`` of the request, then ``path``, ``size_bytes``,
        ``sha256`` and ``status`` of the file; a file of the store also has
        ``label`` and ``version_path`` (``path`` is its standard path), and
        ``newer``, ``unverified`` and ``same_as`` when the track found them.
        """
        file = self.file
        entry: dict[str, object] = {
            "unit": self.unit,
            "country": self.country,
            "path": file.path,
            "size_bytes": file.size_bytes,
            "sha256": file.sha256,
            "status": _DOCUMENT_STATUS.get(file.status, file.status),
        }
        if file.status not in _PLAIN_STATUSES:
            entry["label"] = file.label
            entry["version_path"] = file.version_path
        for key in ("newer", "unverified", "same_as"):
            if (value := getattr(file, key)) is not None:
                entry[key] = value
        return entry


@dataclass(frozen=True)
class SkippedUnit:
    """A unit the request leaves out on purpose (DEV-19.4, ``skipped[]``).

    ``id`` names the unit as ``items[]`` of the result does, ``reason`` is
    ``skipped_incomplete`` (a PL sheet of a plain write that has no full flight in
    the range) and ``message`` says why, with the hint.
    """

    id: str
    reason: str
    message: str


class WriteTarget:
    """What a download report says of where it wrote (``kartograf-download/1``).

    ``output_dir`` is the directory of the plain files and ``root`` the store: one
    of them is set (``None`` for a report built by hand). ``mode`` follows from
    ``output_dir``.
    """

    output_dir: Path | None

    @property
    def mode(self) -> Mode:
        """Return ``plain`` for a write into a directory, else ``store``."""
        return "plain" if self.output_dir is not None else "store"


# The registry code (and ``details.reason``) a failed unit of each ``kind`` stands
# for: the states of the data are ``no_data`` (the same names as the exception
# classes ``NoCoverageError`` and ``YearRangeError``), a failed transfer or country
# is ``source_unavailable`` (ERR §4).
FAILURE_CODES: Mapping[FailureKind, tuple[str, str | None]] = {
    "no_coverage": ("no_data", "no_coverage"),
    "year_out_of_range": ("no_data", "year_out_of_range"),
    "skipped_incomplete": ("no_data", "skipped_incomplete"),
    "download": ("source_unavailable", None),
    "country": ("source_unavailable", None),
}


@dataclass(frozen=True)
class UnitFailure:
    """A failed part of the request (country, sheet set or tile set).

    ``kind``: ``no_coverage`` (no data at the source), ``year_out_of_range``
    (data, but none of the requested years - the code of ``YearRangeError``),
    ``download`` (network, server) or ``country`` (the country part of the
    request failed).
    """

    unit: str
    country: str
    error: str
    kind: FailureKind

    @property
    def code(self) -> str:
        """Return the registry code of the failure (``FAILURE_CODES``)."""
        return FAILURE_CODES[self.kind][0]

    @property
    def reason(self) -> str | None:
        """Return the ``details.reason`` of the failure (``None``: none)."""
        return FAILURE_CODES[self.kind][1]


@dataclass(frozen=True)
class DataReport(WriteTarget, Document):
    """Outcome of ``download_data`` (spec 4.1; ``kartograf-download/1``).

    ``ok`` is the exit rule of the CLI (former ``_finish_pl_sheets`` and
    ``country="auto"`` partial success): ``False`` after any failure or stale
    plan position, except ``auto`` with at least one country succeeding.
    """

    SCHEMA = DOWNLOAD_SCHEMA
    JSON_KEYS = DOWNLOAD_KEYS
    JSON_FILL = {key: DOWNLOAD_FILL[key] for key in ("raw", "inputs", "summary")}

    files: tuple[UnitFile, ...]
    failed: tuple[UnitFailure, ...]
    stale: tuple[PlanItem, ...]
    superseded: tuple[SupersededLazTile, ...]
    notices: tuple[Notice, ...]
    ok: bool
    root: Path | None = None
    output_dir: Path | None = None
    skipped: tuple[SkippedUnit, ...] = ()


@dataclass
class _Run:
    """State of one call: collected files, failures, plans and notices.

    ``dry``: validation only (``validate_data_request``) - every track
    returns right before its first request to the source (no provider, no
    cache, nothing written), after all checks the download makes there.
    """

    sink: NoticeSink
    update: UpdateMode | None
    check: bool
    loaded: UpdatePlan | None
    cache: MetadataCache | bool
    workers: int
    on_progress: Callable[[DownloadProgress], None] | None
    files: list[UnitFile] = field(default_factory=list)
    failed: list[UnitFailure] = field(default_factory=list)
    skipped: list[SkippedUnit] = field(default_factory=list)
    stale: list[PlanItem] = field(default_factory=list)
    superseded: list[SupersededLazTile] = field(default_factory=list)
    plans: list[UpdatePlan] = field(default_factory=list)
    causes: dict[UnitFailure, DownloadError] = field(default_factory=dict)
    dry: bool = False
    preflight: bool = False
    root: Path | None = None
    output_dir: Path | None = None

    def add(
        self,
        unit: str,
        country: str,
        file: VersionedFile | None,
        *,
        reported_check_failure: bool = False,
        reported_unverified: bool = False,
    ) -> None:
        """Record a file and signal notices not already emitted by its track."""
        if file is None:
            return
        self.files.append(UnitFile(unit, country, file))
        emit_file_notices(
            self.sink,
            unit,
            file,
            self.update,
            check_failure=not reported_check_failure,
            unverified_local=not reported_unverified,
        )

    @property
    def refresh(self) -> bool:
        """Return True when the metadata cache is refreshed, not read.

        Metadata cache refreshed, not read: the check (``--check``
        always asks the source), ``--upgrade`` and ``--force``; the check run of
        a plain write's preflight (``preflight``) reads the cache like the download.
        """
        return (self.check and not self.preflight) or refreshes_cache(self.update)

    def add_stale(self, stale: Sequence[PlanItem]) -> int:
        self.stale.extend(stale)
        return 1 if stale else 0

    def fail(
        self,
        unit: str,
        country: str,
        error: str,
        kind: FailureKind,
        cause: DownloadError | None = None,
    ) -> int:
        """Record a failed part.

        ``cause`` (the error it comes from) is kept for
        ``check_data``, which raises it when no plan came out.
        """
        failure = UnitFailure(unit, country, error, kind)
        self.failed.append(failure)
        if cause is not None:
            self.causes[failure] = cause
        return 1


def _error_text(error: Exception) -> str:
    """Error text with the remedy of a ``TransformError`` (if any)."""
    remedy = getattr(error, "remedy", None)
    return f"{error}" + (f" Remedium: {remedy}" if remedy else "")


def failure_kind(
    error: DownloadError, default: FailureKind = "download"
) -> FailureKind:
    """Return the failure kind of an error.

    The ``UnitFailure.kind`` of an error: the states of the data keep the
    name of their error code (``no_coverage``, ``year_out_of_range``), any other
    ``DownloadError`` gets ``default``.
    """
    if isinstance(error, NoCoverageError):
        return (
            "skipped_incomplete"
            if error.reason == "skipped_incomplete"
            else "no_coverage"
        )
    if isinstance(error, YearRangeError):
        return "year_out_of_range"
    return default


def _check_error(run: _Run) -> DownloadError:
    """Return the error of a check that planned nothing.

    The error of a check that planned nothing: the error of its first
    failure (its class says why: no data, data outside the years), else a
    ``DownloadError`` of its text.
    """
    if not run.failed:
        return DownloadError("brak pozycji planu")
    failure = run.failed[0]
    cause = run.causes.get(failure)
    if cause is not None:
        return cause
    if failure.kind == "no_coverage":
        return NoCoverageError(failure.error)
    return DownloadError(failure.error)


def _task(**kwargs: Any) -> SimpleNamespace:
    task = SimpleNamespace(**kwargs)
    task.root = resolve_root(task.root)
    task.geometry = Path(task.geometry) if task.geometry is not None else None
    # enumerated values in any case: the spelling of the registry (UX-11)
    task.country = canonical_country(task.country)
    task.format = canonical_format(task.format)
    task.horizontal_crs = canonical_crs(task.horizontal_crs)
    task.vertical_crs = canonical_vertical_crs(task.vertical_crs)
    task.bbox = canonical_bbox(task.bbox)
    return task


def _preflight(task: SimpleNamespace, run: _Run) -> None:
    """Refuse a plain write that would conflict, before its first byte (DEV-19.6).

    The check run of the same request lists the target of every track (the names are
    known before the transfer) and one plan judges them all together: a name that
    two tracks share, a store, a file that exists. Failures of the check run are not
    reported here: the run reports them again when it fetches.
    """
    probe = _Run(
        sink=NoticeSink(None),
        update=run.update,
        check=True,
        loaded=None,
        cache=run.cache,
        workers=run.workers,
        on_progress=None,
        preflight=True,
    )
    _execute(task, probe)
    write = plain_of(task.root)
    assert write is not None  # only a plain write is checked
    refuse(write.plan([item.name for plan in probe.plans for item in plan.items]))


def _rejudged(write: Staging, plans: list[UpdatePlan]) -> list[UpdatePlan]:
    """Judge the targets of all plans of a plain check together (DEV-19.10)."""
    judged = iter(plain_items(write, [item for plan in plans for item in plan.items]))
    return [
        replace(plan, items=tuple(next(judged) for _ in plan.items)) for plan in plans
    ]


def _start(
    kwargs: dict[str, Any],
    *,
    output_dir: str | Path | None,
    force: bool = False,
    update: UpdateMode | None,
    plan: UpdatePlan | None,
    check: bool,
    workers: int,
    cache: MetadataCache | bool,
    on_progress: Callable[[DownloadProgress], None] | None,
    on_notice: Callable[[Notice], None] | None,
) -> tuple[_Run, int]:
    from kartograf.download.fetch import validate_update

    validate_update(update, check="check_data")
    require_workers(workers)
    if plan is not None and update != "upgrade":
        raise ValidationError(
            "Plan aktualizacji wymaga update='upgrade'", options=("plan", "update")
        )
    run = _Run(
        sink=NoticeSink(on_notice),
        update=update,
        check=check,
        loaded=plan,
        cache=cache,
        workers=workers,
        on_progress=on_progress,
    )
    with writing(
        output_dir=output_dir,
        root=kwargs["root"],
        update=update,
        plan=plan,
        all_campaigns=kwargs["all_campaigns"],
        force=force,
        guard=False,  # the request is judged first: see the refusal below
    ) as root:
        task = _task(**{**kwargs, "root": root})
        write = plain_of(root)
        if write is None:
            run.root = task.root
            refusal = store_refusal(task.root)
        else:
            run.output_dir = write.directory
            # a check lists the target of every file, a conflict of the directory too
            refusal = None if check else directory_refusal(write.directory)
        if refusal is not None:
            # A request that is invalid is invalid, whatever its target; then the
            # refusal comes before any request (DEV-19.11, DEV-19.13, DEV-19.14): the
            # error of the command, or, for a check, the plan that lists it.
            _validate(task)
            if not check:
                raise refusal
            run.plans.append(conflict_plan(task.root, refusal))
            return run, 0
        if write is not None:
            if task.full_sheet:  # a plain write takes the newest full flight anyway
                run.sink.emit(
                    "info", FULL_SHEET_REDUNDANT, message("output.full_sheet_redundant")
                )
                task.full_sheet = False
            if not check:
                _preflight(task, run)
        rc = _execute(task, run)
        if write is not None and check:
            run.plans = _rejudged(write, run.plans)
    return run, rc


def download_data(
    *,
    product: str | None,
    root: str | Path | None = None,
    output_dir: str | Path | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    country: str | None = None,
    vertical_crs: str | Mapping[str, str] | None = None,
    resolution: str | Mapping[str, str] | None = None,
    model: str | None = None,
    format: str | None = None,
    sheet_system: str | None = None,
    scale: str | None = None,
    cutout: bool = False,
    horizontal_crs: str | None = None,
    coverage: str | None = None,
    direction: str | Sequence[str] | None = None,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    all_campaigns: bool = False,
    full_sheet: bool = False,
    min_density: int | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int = 4,
    cache: MetadataCache | bool = True,
    on_progress: Callable[[DownloadProgress], None] | None = None,
    on_notice: Callable[[Notice], None] | None = None,
) -> DataReport:
    """Download elevation data or images for a sheet, bbox or geometry.

    Download NMT/NMPT/LAZ, the CZ contours and the images
    (orthophotomap, intensity images, true and oblique orthophotomap) for a
    sheet, bbox or geometry (spec 4.1).

    Parameter names and values are the ``elevation download`` / ``imagery download``
    flags in ``snake_case``. Every data choice is explicit (no defaults): ``product``,
    ``root``, ``vertical_crs``/``resolution`` (plain or per country,
    ``{"pl": "1m", "cz": "2m"}``; PL values from the variant registry,
    ``kartograf.sources.variants``), ``country`` (``pl``/``cz``/``auto``,
    required with ``bbox``/``geometry``), ``sheet_system``/``scale`` for PL
    sheets of an area (a product with one sheet system - true orto PL-1992,
    oblique orto PL-2000 - may omit ``sheet_system``). ``format`` (PL
    NMT/NMPT): ``None`` = ASC grids, an archive token (``"XYZ"``, ``"TBD"``,
    ...) = the original files of the index, whose sheets (any scale) come
    from the index (ADR-041); the CZ contours (``product="contours"``)
    require it: ``"SHP"`` or ``"DGN"`` (the ZIP of an SM5 sheet, kept as
    published; an area gives the SM5 sheets of the CUZK index, heights Bpv:
    ``vertical_crs`` may be omitted). ``cutout=True`` with ``horizontal_crs`` gives
    ONE cutout of the area instead of sheets (PL: GUGiK WCS, CZ: CUZK; an
    area reaching CZ requires it). ``coverage`` - the orthophotomap cutout
    only (``product="orto"``, ``cutout=True``, PL,
    ``horizontal_crs="EPSG:2180"``): the WCS coverage ``"standard"`` or
    ``"high"``, with the cutout pixel in ``resolution`` (``"0.1m"``,
    ``"0.25m"``, ``"0.5m"``, ``"1m"``; ADR-042 D14); the true orthophotomap
    (``product="true-orto"``) has one coverage and the pixels ``"0.05m"``
    to ``"1m"``; image sheets take neither. ``direction`` - the oblique
    orthophotomap only (``product="oblique-orto"``): a code or a sequence of
    the view directions ``"n"``, ``"e"``, ``"s"``, ``"w"`` (each a file of
    the sheet, ``<sheet>_<direction>.tif``); ``None`` = all four.
    ``bbox`` may be in any supported CRS; ``geometry`` is a SHP/GPKG file.
    ``update``/``plan``: modes of every track (``plan`` from ``check_data``
    with ``update="upgrade"``). ``output_dir`` writes plain files, named as in the
    store, into that directory instead of the store at ``root`` (the default root
    when neither is given): no sidecar, no version, no link; ``update="force"``
    replaces existing files, any other existing file or a name two files share is
    a ``conflict`` before the first byte; it excludes ``root``,
    ``update="upgrade"``, ``plan`` and ``all_campaigns``. ``cache``: ``True`` =
    default metadata cache in the current directory, a ``MetadataCache`` = that
    cache, ``False`` =
    none. ``on_notice`` receives each data notice when it is emitted (e.g.
    country clipping before the first download); ``on_progress`` receives
    the sheet and tile progress.

    Raises
    ------
    ValidationError
        Invalid or missing choice, or an argument of a wrong type
        (``year="2018"``, ``workers="4"``; never converted) - before any
        download; texts name the CLI flags, the CLI prints them as ``Error:``.
    ParseError
        Malformed sheet code.
    TransformError
        No safe pinned operation for the request area.
    """
    run, rc = _start(
        _selection_kwargs(locals()),
        output_dir=output_dir,
        update=update,
        plan=plan,
        check=False,
        workers=workers,
        cache=cache,
        on_progress=on_progress,
        on_notice=on_notice,
    )
    return DataReport(
        files=tuple(run.files),
        failed=tuple(run.failed),
        stale=tuple(run.stale),
        superseded=tuple(run.superseded),
        notices=run.sink.notices,
        ok=rc == 0,
        root=run.root,
        output_dir=run.output_dir,
        skipped=tuple(run.skipped),
    )


def check_data(
    *,
    product: str | None,
    root: str | Path | None = None,
    output_dir: str | Path | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    country: str | None = None,
    vertical_crs: str | Mapping[str, str] | None = None,
    resolution: str | Mapping[str, str] | None = None,
    model: str | None = None,
    format: str | None = None,
    sheet_system: str | None = None,
    scale: str | None = None,
    cutout: bool = False,
    horizontal_crs: str | None = None,
    coverage: str | None = None,
    direction: str | Sequence[str] | None = None,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    all_campaigns: bool = False,
    full_sheet: bool = False,
    min_density: int | None = None,
    force: bool = False,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_data`` with the same arguments; no download.

    ``country="auto"`` gives ONE merged plan of every country. A country
    that cannot be checked is a ``CHECK_FAILED`` notice when another one
    was checked, else its error is raised (``DownloadError``; the states of
    the data keep their class - ``NoCoverageError`` when no sheet has data,
    ``YearRangeError`` when the data are outside the years - as in the
    download, where they are the ``kind`` of the failure). With ``output_dir`` the
    positions are the targets of a plain write, each with its ``action`` (``write``,
    ``replace`` with ``force``, ``conflict``), ``path`` and ``reason``; a plan that
    lists conflicts is a result, not an error.
    """
    run, _ = _start(
        _selection_kwargs(locals()),
        output_dir=output_dir,
        force=force,
        update=None,
        plan=None,
        check=True,
        workers=1,
        cache=cache,
        on_progress=None,
        on_notice=on_notice,
    )
    if not run.plans:
        raise _check_error(run)
    for failure in run.failed:
        run.sink.emit("warning", CHECK_FAILED, f"{failure.unit}: {failure.error}")
    merged = run.plans[0]
    for other in run.plans[1:]:
        merged = merged.merge(other)
    return replace(merged, notices=run.sink.notices)


def validate_data_request(
    *,
    product: str | None,
    root: str | Path | None = None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    country: str | None = None,
    vertical_crs: str | Mapping[str, str] | None = None,
    resolution: str | Mapping[str, str] | None = None,
    model: str | None = None,
    format: str | None = None,
    sheet_system: str | None = None,
    scale: str | None = None,
    cutout: bool = False,
    horizontal_crs: str | None = None,
    coverage: str | None = None,
    direction: str | Sequence[str] | None = None,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    all_campaigns: bool = False,
    full_sheet: bool = False,
    min_density: int | None = None,
) -> None:
    """Check a request completely before its first network access.

    Every check ``download_data``/``check_data`` make before their first
    request, without network and without writing (``project add``, ADR-040).

    The same dispatch as ``download_data`` with every track stopping right
    before its source, so an invalid choice raises exactly what the download
    raises (type, text and order of the checks). A ``geometry`` file is read
    (layer, envelope, sheets of the features); nothing else is touched.

    Raises
    ------
    ValidationError
        Invalid or missing choice (``ParseError``: malformed sheet code).
    TransformError
        No safe pinned operation for the request area.
    """
    _validate(_task(**_selection_kwargs(locals())))


def _validate(task: SimpleNamespace) -> None:
    """Run every check of a request that comes before its first request (a dry run)."""
    run = _Run(
        sink=NoticeSink(None),
        update=None,
        check=False,
        loaded=None,
        cache=False,
        workers=1,
        on_progress=None,
        dry=True,
    )
    _execute(task, run)


_SELECTION = (
    "product",
    "root",
    "sheet",
    "bbox",
    "geometry",
    "layer",
    "country",
    "vertical_crs",
    "model",
    "resolution",
    "format",
    "sheet_system",
    "scale",
    "cutout",
    "horizontal_crs",
    "coverage",
    "direction",
    "year",
    "min_year",
    "max_year",
    "all_campaigns",
    "full_sheet",
    "min_density",
)


def _selection_kwargs(values: dict[str, Any]) -> dict[str, Any]:
    return {name: values[name] for name in _SELECTION}


# =============================================================================
# Dispatch
# =============================================================================


def _execute(task: SimpleNamespace, run: _Run) -> int:
    """Validate the request and run its tracks; the exit code of the CLI."""
    from kartograf.core.parser_registry import detect_system

    validate_request(task)
    if task.sheet is not None:
        # the registry ends with the pl1992 fallback (always matches)
        system = detect_system(task.sheet)
        country = task.country
        if country not in (None, "auto") and country != system.country.lower():
            raise ValidationError(
                f"Godlo '{task.sheet}' nalezy do systemu {system.name} "
                f"(kraj {system.country}), a podano --country {country}",
                options=("sheet", "country"),
            )
        if not sources_for(country=system.country, product=task.product):
            raise ValidationError(
                f"--product {task.product} nie ma danych {system.country} - godlo "
                f"'{task.sheet}' nalezy do systemu {system.name} (kraj "
                f"{system.country}); podaj godlo kraju produktu",
                options=("product", "sheet"),
            )
        if system.country == "CZ":
            if task.product == "orto":  # SM5 sheets, own rules (ADR-042 D13)
                return _download_cz(task, run)
            _reject_campaign_opts_without_pl(task, ("CZ",))
            if task.product == "laz":
                return _download_cz_laz(task, run)
            return _download_cz(task, run)
        parsed = parse_sheet(task.sheet)
        if pl_file_variant(task) is not None:
            return _download_pl_files(
                task,
                run,
                parsed.get_bbox(crs="EPSG:2180"),
                {"sheet": parsed.sheet, "countries": ["PL"]},
            )
        resolve_pl_options(
            task, code_system=parsed.sheet_system, code_scale=parsed.scale
        )
        if task.model is not None:
            raise ValidationError(
                "--model dotyczy tylko --product laz w CZ - pomin --model dla PL",
                options=("model", "sheet"),
            )
    if task.product == "laz" and task.sheet is not None:
        return _download_pl_laz(task, run, {"sheet": task.sheet})
    if task.geometry is not None:
        return _download_geometry(task, run)
    if task.bbox is not None:
        return _dispatch_area(task, run, task.bbox)
    if is_source_file_request(task):
        from kartograf.providers.pl.skorowidz_wfs import sheet_frame_2180

        return _download_pl_archive(
            task,
            run,
            [sheet_frame_2180(task.sheet)],
            None,
            what=f"arkusza {task.sheet}",
        )
    return _download_pl_sheet(task, run)


def _reject_campaign_opts_without_pl(
    task: SimpleNamespace, countries: tuple[str, ...]
) -> None:
    """Reject PL-only campaign/year choices for a CZ-only request.

    PL-only campaign/year choices are rejected for a CZ-only request (a
    PL+CZ area is a cutout, which rejects them itself, ADR-038).
    """
    names = campaign_option_names(task)
    if names and "PL" not in countries:
        raise option_error(
            "CZ (CUZK) nie ma kampanii - "
            "--all-campaigns/--min-year/--max-year/--year/--full-sheet dotycza "
            "tylko PL",
            *names,
        )


def _dispatch_area(
    task: SimpleNamespace, run: _Run, bbox: BBox, filepath: Path | None = None
) -> int:
    """Split an area request (bbox or geometry envelope) into countries and run them.

    With ``filepath`` the PL part works on the file (sheets per feature, not
    the envelope); the bbox recognizes countries and gives ``parent_request``.
    """
    if filepath is not None and (task.cutout or task.product == "laz"):
        # a point picks sheets, units or pixels; these two cut or select by AREA
        require_geometry_area(
            bbox, "wycinek (--cutout)" if task.cutout else "wybor kafli LAZ"
        )
    auto = task.country == "auto"
    countries = (
        countries_for_bbox(bbox) if auto else ({"pl": "PL", "cz": "CZ"}[task.country],)
    )
    if not countries:
        raise ValidationError(
            "obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)",
            option="bbox" if filepath is None else "geometry",
        )
    if auto:
        # a product of one country keeps that country (as the collections)
        own = tuple(
            c for c in countries if sources_for(country=c, product=task.product)
        )
        if not own:
            raise ValidationError(
                f"--product {task.product} jest dostepny tylko dla "
                f"{_product_countries(task.product)}, a obszar lezy w "
                f"{', '.join(countries)}",
                options=("product", "country"),
            )
        if own != countries:
            run.sink.emit(
                "info",
                AUTO_NARROWED_TO_PL if own == ("PL",) else AUTO_NARROWED_TO_CZ,
                f"--country auto -> {own[0].lower()} (--product {task.product} "
                f"tylko dla {own[0]})",
            )
            auto = False
            countries = own
    # ADR-023 point 5: a choice without a CZ counterpart decides the country
    if auto and len(countries) > 1 and "PL" in countries:
        pl_only = pl_only_flags(
            task.product,
            task.vertical_crs,
            task.resolution,
            task.format,
            task.coverage,
            year=task.year,
            min_year=task.min_year,
            max_year=task.max_year,
            all_campaigns=task.all_campaigns,
            min_density=task.min_density,
        )
        if pl_only:
            run.sink.emit(
                "info",
                AUTO_NARROWED_TO_PL,
                f"--country auto -> pl ({', '.join(pl_only)} dotyczy tylko PL)",
            )
            auto = False
            countries = ("PL",)
    if countries == ("PL",) and task.model is not None:
        raise ValidationError(
            "--model dotyczy tylko --product laz w CZ - pomin --model dla PL",
            options=("model", "country"),
        )
    if task.product == "orto" and task.cutout and "PL" not in countries:
        raise option_error(ORTO_CUTOUT_PL_ONLY, "cutout", "country")
    if task.product != "orto":  # CZ orthophoto: its own year rules (ADR-042 D13)
        _reject_campaign_opts_without_pl(task, countries)
    _validate_cross_country(task, countries)
    require_cz_cutout(task, countries)
    if "PL" in countries:
        reject_campaign_opts_with_cutout(task)
    if task.country != "auto":
        option = "bbox" if filepath is None else "geometry"
        error = outside_country(bbox, countries[0], flag=f"--{option}")
        if error is not None:
            raise ValidationError(error, option=option)

    parent_request = parent_request_for(bbox, countries)
    cz_crs = (
        (
            "EPSG:3045"
            if country_value(task.vertical_crs, "CZ") == "EVRF2007"
            else "EPSG:5514"
        )
        if task.product == "laz"
        else task.horizontal_crs or "EPSG:5514"
    )
    # per-country parts BEFORE any download (TransformError fails the request)
    parts = {
        code: country_bbox(bbox, code, auto=auto, cz_crs=cz_crs) for code in countries
    }
    if auto:
        emit_clipping_notices(
            run.sink,
            bbox,
            countries,
            parts,
            pl_geometry_sheets=filepath is not None
            and not task.cutout
            and task.product != "laz",
            pl_sheet_list=filepath is None and not task.cutout,
            sheet_files=task.product == "laz",
        )

    results: list[tuple[str, int]] = []
    for code in countries:
        part = parts[code].bbox
        # a COPY per country: each branch narrows the per-country values
        country_task = SimpleNamespace(**vars(task))
        try:
            if code == "CZ":
                if task.product == "laz":
                    rc = _download_cz_laz(
                        country_task, run, bbox=part, parent_request=parent_request
                    )
                else:
                    rc = _download_cz(
                        country_task, run, bbox=part, parent_request=parent_request
                    )
            elif task.product == "laz":
                rc = _download_pl_laz(country_task, run, {"bbox": part}, parent_request)
            elif filepath is not None:
                rc = _download_pl_geometry(
                    country_task, run, filepath, parent_request, part
                )
            else:
                rc = _download_pl_bbox(country_task, run, part, parent_request)
        except DownloadError as e:
            kind = failure_kind(e, "country")
            rc = run.fail(code, code, _error_text(e), kind, e)
        results.append((code, rc))

    exit_codes = [rc for _, rc in results]
    # A3-2: `auto` takes countries from RECTANGULAR envelopes, so a request deep
    # inside one country routinely hits the other one too - code 0 with a warning.
    if auto and len(results) > 1 and 0 in exit_codes and max(exit_codes) != 0:
        failed = [code for code, rc in results if rc != 0]
        ok = [code for code, rc in results if rc == 0]
        emit_partial_success(run.sink, failed, ok, check=run.check)
        return 0
    return max(exit_codes)


def _product_countries(product: str) -> str:
    """Countries with sources of ``product`` (``PL``, ``CZ``) in messages."""
    return ", ".join(c for c in ("PL", "CZ") if sources_for(country=c, product=product))


def _validate_cross_country(task: SimpleNamespace, countries: tuple[str, ...]) -> None:
    """Choices must be valid for EVERY country before any download."""
    hint = "; uzyj jawnie --country pl albo --country cz" if len(countries) > 1 else ""
    for code in countries:
        if not sources_for(country=code, product=task.product):
            raise ValidationError(
                f"--product {task.product} jest dostepny tylko dla "
                f"{_product_countries(task.product)}{hint}",
                options=("product", "country"),
            )
    if (
        task.product == "laz"
        and task.model is None
        and "CZ" in countries
        and "PL" in countries
    ):
        raise ValidationError(
            f"obszar siega CZ: podaj --model {cz_model_text()} albo --country pl",
            option="model",
            allowed=cz_models(),
        )
    for code in countries:
        if code == "PL":
            error = pl_option_error(task, countries=countries)
        elif task.product == "orto":
            error = cz_orto_option_error(task, countries=countries)
        elif task.product == CONTOURS:
            error = None  # CZ only: every choice checked by validate_request
        else:
            error = cz_option_error(task, countries=countries)
        if error is not None:
            raise error


def _download_geometry(task: SimpleNamespace, run: _Run) -> int:
    """Geometry request: explicit CZ (envelope in the CZ CRS) or country dispatch."""
    assert task.geometry is not None
    if task.country == "cz" and task.product != "laz":
        if task.product != "orto":  # CZ orthophoto: its own year rules
            _reject_campaign_opts_without_pl(task, ("CZ",))
        require_cz_cutout(task, ("CZ",))
        task.layer = resolve_geometry_layer(task.geometry, task.layer, run.sink)
        bbox = cz_geometry_bbox(
            task.geometry, task.layer, task.horizontal_crs or "EPSG:5514"
        )
        if task.cutout:
            require_geometry_area(bbox, "wycinek (--cutout)")
        error = outside_country(bbox, "CZ", flag="--geometry")
        if error is not None:
            raise ValidationError(error, option="geometry")
        return _download_cz(
            task, run, bbox=bbox, parent_request=parent_request_for(bbox, ("CZ",))
        )
    task.layer = resolve_geometry_layer(task.geometry, task.layer, run.sink)
    overall = geometry_envelope(task.geometry, task.layer)
    return _dispatch_area(task, run, overall, filepath=task.geometry)


# =============================================================================
# PL sheets
# =============================================================================


def _product_label(product: str, resolution: str | None, fmt: str | None = None) -> str:
    """Return the request label used in messages.

    Request label in messages (``Pobieranie <godlo> (<label>)...``):
    images have no resolution (K5), archives name their format, the CZ
    contours only their format.
    """
    if image_source(product) is not None:
        return f"produkt: {product}"
    if product == CONTOURS:
        return f"format: {fmt}"
    if fmt is not None and fmt != "ASC":
        return f"format: {fmt}, rozdzielczosc: {resolution or '-'}"
    return f"rozdzielczosc: {resolution}"


def _create_provider_and_storage(
    product: str,
    root: str | Path,
    vertical_crs: str,
    resolution: str | None,
    cache: MetadataCache | None = None,
    fmt: str | None = None,
    direction: str | None = None,
) -> "tuple[BaseProvider, FileStorage]":
    """Create the provider and storage of a PL sheet product.

    Provider and storage of a PL sheet product (``cache``: ``MetadataCache``
    or ``None``; GUGiK index records go through it, N6). ``fmt``: ``None``
    = ASC grids, else an archive format of the variant registry;
    ``direction``: the view direction of an oblique orthophotomap sheet.
    """
    from kartograf.download.storage import storage_for_provider

    provider: BaseProvider
    if product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider = GugikNmptProvider(
            vertical_crs=vertical_crs,
            resolution=resolution,
            format=fmt or "ASC",
            cache=cache,
        )
    elif image_source(product) is not None:
        from kartograf.providers.pl.gugik_orto import image_provider

        # `download_data` offers the RGB composition of the orthophotomap only
        provider = image_provider(product, cache=cache, direction=direction)
    elif product == "nmt":
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(
            vertical_crs=vertical_crs,
            resolution=resolution,
            cache=cache,
            format=fmt or "ASC",
        )
    else:
        raise ValidationError(f"Nieobslugiwany produkt arkuszy PL: {product}")
    storage = storage_for_provider(
        root, provider, resolution=resolution, vertical_crs=vertical_crs
    )
    return provider, storage


def _manager(
    task: SimpleNamespace,
    run: _Run,
    metadata: MetadataCache | None,
    parent_request: dict[str, Any] | None,
    direction: str | None,
) -> DownloadManager:
    provider, storage = _create_provider_and_storage(
        task.product,
        task.root,
        task.vertical_crs,
        task.resolution,
        cache=metadata,
        fmt=task.format,
        direction=direction,
    )
    return DownloadManager(
        root=task.root,
        provider=provider,
        storage=storage,
        workers=run.workers,
        sidecar_extra=(
            {"parent_request": parent_request} if parent_request is not None else None
        ),
        all_campaigns=task.all_campaigns,
        min_year=task.min_year,
        max_year=task.max_year,
        full_sheet=task.full_sheet,
        on_notice=run.sink.add,
    )


def _managers(
    task: SimpleNamespace,
    run: _Run,
    metadata: MetadataCache | None,
    parent_request: dict[str, Any] | None = None,
) -> list[DownloadManager]:
    """Create the managers of a PL sheet request.

    The managers of a PL sheet request: one per view direction of the
    oblique orthophotomap (its sheet is one file per direction, the chosen
    ``direction`` or all of them), else one.
    """
    directions = image_directions(task.product)
    chosen: tuple[str | None, ...] = (
        (task.direction or directions) if directions else (None,)
    )
    managers = [
        _manager(task, run, metadata, parent_request, direction) for direction in chosen
    ]
    if managers[0].storage.has_legacy_campaigns() is True:
        run.sink.emit(
            "info",
            LEGACY_CAMPAIGNS_DIR,
            "katalog kampanie/ z wersji 0.7.x nie jest uzywany; dane "
            "zostana pobrane ponownie do versions/",
        )
    return managers


def _direction_of(manager: DownloadManager) -> str | None:
    direction = getattr(manager.provider, "direction", None)
    return direction if isinstance(direction, str) else None


def _prefix(manager: DownloadManager) -> str:
    """Prefix of the messages of one view direction (``kierunek n: ``)."""
    direction = _direction_of(manager)
    return f"kierunek {direction}: " if direction is not None else ""


def _progress(
    run: _Run, manager: DownloadManager
) -> Callable[[DownloadProgress], None] | None:
    """Build the ``on_progress`` callback of a manager.

    ``on_progress`` of a manager: the events of a view direction name it
    after the sheet (``7.125.11.08 n``).
    """
    direction = _direction_of(manager)
    progress = run.on_progress
    if progress is None or direction is None:
        return progress

    def on_progress(event: DownloadProgress) -> None:
        progress(replace(event, sheet=f"{event.sheet} {direction}"))

    return on_progress


def _plan_modes(run: _Run, manager: DownloadManager, sheets: list[str]) -> int | None:
    """Check or planned upgrade of PL sheets; ``None`` = a plain download."""
    if run.check:
        run.plans.append(
            manager.check_sheets(
                sheets,
                on_no_coverage=_check_no_coverage(run, _prefix(manager)),
                on_incomplete=lambda incomplete, _total: _skip_incomplete(
                    run,
                    {s: incomplete_text(s, r) for s, r in incomplete.items()},
                    _prefix(manager),
                ),
            )
        )
        return 0
    if run.update != "upgrade" or run.loaded is None:
        return None
    report = manager.download_sheets(
        sheets, update="upgrade", plan=run.loaded, on_progress=_progress(run, manager)
    )
    reported = any(n.code == CHECK_FAILED for n in report.notices)
    for sheet, files in report.files.items():
        for file in files:
            run.add(
                sheet,
                "PL",
                file,
                reported_check_failure=reported or sheet in report.unverified,
            )
    rc = run.add_stale(report.stale)
    prefix = _prefix(manager)
    for sheet, failure in report.errors.items():
        kind: FailureKind = "no_coverage" if sheet in report.no_coverage else "download"
        run.fail(sheet, "PL", f"{prefix}{sheet}: {failure}", kind)
    return 1 if rc or report.failed else 0


def _check_no_coverage(
    run: _Run, prefix: str
) -> Callable[[Mapping[str, NoCoverageError], int], None]:
    """Build the ``on_no_coverage`` callback of ``check_sheets``.

    ``on_no_coverage`` of ``DownloadManager.check_sheets``: the sheets
    without data are reported as the download reports them
    (``_finish_pl_sheets``) - a ``NO_COVERAGE_SOME`` warning when the rest has
    positions, the hints of the provider always.
    """

    def report(no_data: Mapping[str, NoCoverageError], total: int) -> None:
        kept = total - len(no_data)
        if kept:
            _no_coverage_warning(
                run, list(no_data), total, f"sprawdzono {kept}", prefix
            )
        _coverage_hints(run, {sheet: e.hints for sheet, e in no_data.items()})

    return report


def _announcer(
    on_progress: Callable[[DownloadProgress], None] | None, unit: str, details: str
) -> Callable[[], None]:
    """``on_download`` hook: a ``start`` progress event when a transfer starts."""

    def announce() -> None:
        if on_progress is not None:
            on_progress(DownloadProgress(0, 1, unit, "start", details))

    return announce


def _download_pl_sheet(task: SimpleNamespace, run: _Run) -> int:
    """Download or check a PL sheet code request.

    PL sheet code (validated): one sheet, a coarser code or a ``scale``
    list; the view directions of an oblique sheet one after another.
    """
    if run.dry:
        return 0
    with open_cache(run.cache, force=run.refresh, on_notice=run.sink.add) as metadata:
        return max(
            _download_pl_code(task, run, manager)
            for manager in _managers(task, run, metadata)
        )


def _download_pl_code(
    task: SimpleNamespace, run: _Run, manager: DownloadManager
) -> int:
    """Handle the files of one manager of a PL sheet code request."""
    label = _product_label(task.product, task.resolution)
    prefix = _prefix(manager)
    on_progress = _progress(run, manager)
    sheets = (
        [d.sheet for d in SheetParser(task.sheet).get_all_descendants(task.scale)]
        if task.scale
        else [task.sheet]
    )
    try:
        planned = _plan_modes(run, manager, sheets)
        if planned is not None:
            return planned
        if task.scale:
            if on_progress is not None:
                count = manager.count_sheets(task.sheet, task.scale)
                on_progress(
                    DownloadProgress(
                        0, count, f"{task.sheet} w skali {task.scale}", "start", label
                    )
                )
            result = manager.download_hierarchy(
                task.sheet,
                task.scale,
                update=run.update,
                on_progress=on_progress,
            )
            return _finish_pl_sheets(task, run, result, prefix)
        parsed = SheetParser(task.sheet)
        # a PL-1992 code coarser than the sheet level of the product (the
        # manager expands it, ``DownloadManager.is_hierarchy``)
        expanded = parsed.sheet_system != "2000" and parsed.scale != (
            pl_target_scale(task)
        )
        announce = _announcer(on_progress, task.sheet, label)
        if expanded:
            announce()
        result = manager.download_sheet(
            task.sheet,
            update=run.update,
            on_progress=on_progress,
            on_download=announce,
        )
    except DownloadError as e:
        # a sheet without data or outside the years is the same kind of failure
        # in the download and in the check (``_check_error``)
        if failure_kind(e) == "skipped_incomplete" and e.sheet is not None:
            _skip_incomplete(run, {e.sheet: str(e)}, prefix)
        return run.fail(task.sheet, "PL", f"{prefix}{e}", failure_kind(e), e)
    if expanded:
        return _finish_pl_sheets(task, run, result, prefix)
    reported = any(n.code == CHECK_FAILED for n in result.notices)
    for file in result.files.get(parsed.sheet, ()):
        run.add(
            parsed.sheet,
            "PL",
            file,
            reported_check_failure=reported or parsed.sheet in result.unverified,
        )
    paths = _result_paths(result)
    _sheet_sidecar_notices(task, run, result, paths)
    return 0


def _result_paths(result: DownloadResult) -> list[Path]:
    """Return the standard paths of successful and already-local sheets."""
    if result.files:
        return [files[0].path for files in result.files.values() if files]
    return list(result.succeeded)


def _download_pl_bbox(
    task: SimpleNamespace, run: _Run, bbox: BBox, parent_request: dict[str, Any]
) -> int:
    """Download or check the PL part of a bbox request.

    PL part of a bbox request: a cutout (``cutout``), a sheet list or the
    voivodeship files of a file variant.
    """
    if pl_file_variant(task) is not None:
        return _download_pl_files(task, run, bbox, parent_request)
    resolve_pl_options(task)
    if task.cutout:
        return _download_pl_cutout(task, run, bbox, parent_request)
    if is_source_file_request(task):
        from kartograf.core.coverage import rectangle
        from kartograf.download.area import bbox_to_2180

        area = bbox_to_2180(bbox)
        return _download_pl_archive(
            task,
            run,
            [rectangle(area.min_x, area.min_y, area.max_x, area.max_y)],
            parent_request,
            what="bbox",
        )
    target_scale = pl_target_scale(task)
    sheets = find_sheets_for_bbox(bbox, target_scale, sheet_system=task.sheet_system)
    if not sheets:
        return run.fail("PL", "PL", "Brak arkuszy dla podanego bbox", "no_coverage")
    return _download_pl_sheet_list(
        task, run, sheets, parent_request, what="bbox", target_scale=target_scale
    )


def _download_pl_geometry(
    task: SimpleNamespace,
    run: _Run,
    filepath: Path,
    parent_request: dict[str, Any],
    bbox: BBox,
) -> int:
    """Download or check the PL part of a geometry request.

    PL part of a geometry request: sheets per feature, a cutout of the
    (clipped) envelope with ``cutout``, or the voivodeship files of a file
    variant for that envelope.
    """
    from kartograf.core.geometry import find_sheets_for_geometry

    if pl_file_variant(task) is not None:
        return _download_pl_files(task, run, bbox, parent_request)
    resolve_pl_options(task)
    if task.cutout:
        return _download_pl_cutout(task, run, bbox, parent_request)
    if is_source_file_request(task):
        from kartograf.core.coverage import rectangle
        from kartograf.core.geometry import read_feature_bboxes

        areas = [
            rectangle(b.min_x, b.min_y, b.max_x, b.max_y)
            for b in read_feature_bboxes(filepath, task.layer, "EPSG:2180")
        ]
        return _download_pl_archive(
            task, run, areas, parent_request, what=f"geometry {filepath.name}"
        )
    target_scale = pl_target_scale(task)
    sheets = find_sheets_for_geometry(
        filepath,
        target_scale=target_scale,
        layer=task.layer,
        sheet_system=task.sheet_system,
    )
    if not sheets:
        return run.fail("PL", "PL", "Brak arkuszy dla podanej geometrii", "no_coverage")
    return _download_pl_sheet_list(
        task,
        run,
        sheets,
        parent_request,
        what=f"geometry {filepath.name}",
        target_scale=target_scale,
    )


def _download_pl_sheet_list(
    task: SimpleNamespace,
    run: _Run,
    sheets: list[str],
    parent_request: dict[str, Any],
    *,
    what: str,
    target_scale: str,
) -> int:
    """Download or check a PL sheet list.

    PL sheet list (area without ``cutout``): managers + finish (D15; the
    view directions of the oblique orthophotomap one after another).
    """
    if run.dry:
        return 0
    _emit_sheet_list(run, task, sheets, f"w skali {target_scale}", what)
    with open_cache(run.cache, force=run.refresh, on_notice=run.sink.add) as metadata:
        try:
            managers = _managers(task, run, metadata, parent_request)
        except DownloadError as e:
            return run.fail("PL", "PL", str(e), failure_kind(e), e)
        rc = 0
        for manager in managers:
            prefix = _prefix(manager)
            try:
                planned = _plan_modes(run, manager, sheets)
                if planned is not None:
                    rc = max(rc, planned)
                    continue
                result = manager.download_sheets(
                    sheets, update=run.update, on_progress=_progress(run, manager)
                )
            except DownloadError as e:
                kind = failure_kind(e)
                rc = max(rc, run.fail("PL", "PL", f"{prefix}{e}", kind, e))
                continue
            rc = max(rc, _finish_pl_sheets(task, run, result, prefix))
    return rc


def _emit_sheet_list(
    run: _Run, task: SimpleNamespace, sheets: list[str], where: str, what: str
) -> None:
    """``SHEET_LIST``: the sheets of a PL area request (header of the result)."""
    sample = sheets if len(sheets) <= 10 else sheets[:3] + ["..."] + sheets[-2:]
    run.sink.emit(
        "info",
        SHEET_LIST,
        f"Znaleziono arkuszy {where}: {len(sheets)} dla {what} "
        f"({_product_label(task.product, task.resolution, task.format)})\n"
        f"  Arkusze: {', '.join(sample)}",
    )


def _download_pl_archive(
    task: SimpleNamespace,
    run: _Run,
    areas: list[Any],
    parent_request: dict[str, Any] | None,
    *,
    what: str,
) -> int:
    """PL archive files (``format`` other than ASC) of an area (ADR-041).

    Archives lie on sheets of several scales (1:25000 and 1:10000 frames of
    one variant, PL-2000 sheets), so the sheets are the variant's records of
    the WFS index overlapping ``areas`` (convex EPSG:2180 polygons: the sheet
    frame, the bbox, the feature envelopes of a geometry), within the year
    bounds - then the usual sheet flow (campaigns, versions, sidecars).
    """
    if run.dry:
        return 0
    with open_cache(run.cache, force=run.refresh, on_notice=run.sink.add) as metadata:
        try:
            (manager,) = _managers(task, run, metadata, parent_request)
            provider = cast(GugikProvider, manager.provider)
            sheets = provider.index_sheets(
                areas,
                system=task.sheet_system,
                min_year=task.min_year,
                max_year=task.max_year,
            )
            if not sheets:
                from kartograf.download.campaigns import year_range_label

                years = (
                    ""
                    if task.min_year is None and task.max_year is None
                    else " " + year_range_label(task.min_year, task.max_year)
                )
                return run.fail(
                    "PL",
                    "PL",
                    f"Skorowidz GUGiK nie ma plikow {provider.describe()} "
                    f"{task.vertical_crs} (PL-{task.sheet_system}){years} dla "
                    f"{what} - dostepne dane obszaru: kartograf elevation "
                    "availability",
                    "no_coverage",
                )
            _emit_sheet_list(run, task, sheets, "w skorowidzu GUGiK", what)
            planned = _plan_modes(run, manager, sheets)
            if planned is not None:
                return planned
            result = manager.download_sheets(
                sheets, update=run.update, on_progress=run.on_progress
            )
        except DownloadError as e:
            return run.fail("PL", "PL", str(e), failure_kind(e), e)
    return _finish_pl_sheets(task, run, result)


def _download_pl_files(
    task: SimpleNamespace, run: _Run, area: BBox, parent_request: dict[str, Any]
) -> int:
    """PL voivodeship files of an ATOM feed (NMT 100 m, ADR-043 D10).

    The voivodeships of the area (``area`` in any CRS; a sheet: its extent)
    come from PRG; each file goes to ``<segment>/teryt/<woj>.zip`` on the
    plan track ``collection`` with the edition of its dataset feed (signal
    ``metadata``). Flags of the sheet tracks were rejected by
    ``validate_request``.
    """
    from kartograf.download.collections import (
        atom_area_request,
        plan_request,
        run_request,
    )

    variant = pl_file_variant(task)
    assert variant is not None
    if run.dry:
        return 0
    request = atom_area_request(
        variant.source,
        product=task.product,
        root=task.root,
        area=area,
        parent=parent_request,
        choice={"resolution": variant.label},
        extra=(
            {"vertical_crs_note": variant.vertical_note}
            if variant.vertical_note
            else {}
        ),
    )
    try:
        if run.check:
            run.plans.append(plan_request(request, cache=run.cache, sink=run.sink))
            return 0
        files, failed, stale = run_request(
            request,
            update=run.update,
            plan=run.loaded,
            workers=run.workers,
            cache=run.cache,
            sink=run.sink,
            on_progress=run.on_progress,
        )
    except DownloadError as e:
        return run.fail("PL", "PL", str(e), failure_kind(e), e)
    # run_request emitted the file notices already
    run.files.extend(files)
    run.failed.extend(failed)
    return max(run.add_stale(stale), 1 if failed else 0)


def _skip_incomplete(run: _Run, sheets: Mapping[str, str], prefix: str = "") -> None:
    """Record the sheets a plain write leaves out (DEV-19.4, ADR-054 decision 5).

    Each sheet is an entry of ``skipped[]`` with the reason ``skipped_incomplete``
    (its message ends with the hint ``--root``); one warning notice names the first
    ten, ``prefix`` the view direction of an oblique sheet.
    """
    hint = message("output.skipped_incomplete_hint")
    run.skipped.extend(
        SkippedUnit(sheet, "skipped_incomplete", f"{message} ({hint})")
        for sheet, message in sheets.items()
    )
    shown = ", ".join(list(sheets)[:10]) + (" ..." if len(sheets) > 10 else "")
    run.sink.emit(
        "warning",
        SKIPPED_INCOMPLETE,
        prefix
        + message("output.skipped_incomplete_some", count=len(sheets), sheets=shown),
    )


def _finish_pl_sheets(
    task: SimpleNamespace, run: _Run, result: DownloadResult, prefix: str = ""
) -> int:
    """Files, notices and exit code of a multi-sheet PL request (D2/D10, R5).

    All downloaded/local -> 0; >= 1 file and the rest without GUGiK data ->
    ``NO_COVERAGE_SOME``, 0; >= 1 download failure -> failure, 1; no file at
    all -> ``no_coverage`` failure, 1. ``prefix`` names the view direction
    of the result in its messages (``kierunek n: ``, oblique orthophotomap).
    """
    paths = _result_paths(result)
    if result.incomplete:
        _skip_incomplete(run, result.incomplete, prefix)
        if not paths and not result.failed:  # every sheet was left out: no_data
            return max(
                run.fail(sheet, "PL", message, "skipped_incomplete")
                for sheet, message in result.incomplete.items()
            )
    _sheet_sidecar_notices(task, run, result, paths)
    reported = any(n.code == CHECK_FAILED for n in result.notices)
    for sheet, files in result.files.items():
        for file in files:
            run.add(
                sheet,
                "PL",
                file,
                reported_check_failure=reported or sheet in result.unverified,
            )
    total = result.total
    hard = result.hard_failures
    missing = result.no_coverage
    if missing and (paths or hard):
        _no_coverage_warning(run, missing, total, f"pobrano {len(paths)}", prefix)
        _coverage_hints(run, result.no_coverage_hints)
    if hard:
        causes = "; ".join(
            f"{sheet}: {result.errors[sheet].removeprefix(sheet + ': ')}"
            for sheet in hard
        )
        return run.fail(
            "PL",
            "PL",
            f"{prefix}{len(hard)} z {count_text(total, *OF_SHEETS)} nie pobrano "
            "(blad pobrania, "
            f"nie brak danych): {causes} - ponow pobranie",
            "download",
        )
    if not paths:
        _coverage_hints(run, result.no_coverage_hints)
        return run.fail("PL", "PL", f"{prefix}{no_coverage_text(total)}", "no_coverage")
    return 0


def _no_coverage_warning(
    run: _Run, missing: Sequence[str], total: int, outcome: str, prefix: str
) -> None:
    """Report sheets without GUGiK data (``NO_COVERAGE_SOME``).

    ``NO_COVERAGE_SOME``: sheets without GUGiK data of a request that goes on
    with the others (R5) - the download and ``--check`` say it the same
    way; ``outcome`` is what became of the rest (``pobrano 3``,
    ``sprawdzono 3``), ``prefix`` the view direction (``kierunek n: ``).
    """
    shown = ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
    run.sink.emit(
        "warning",
        NO_COVERAGE_SOME,
        f"{prefix}GUGiK nie ma danych dla {len(missing)} z "
        f"{count_text(total, *OF_SHEETS)} "
        f"({shown}) - pominiete (skorowidz GUGiK nie ma tych arkuszy dla "
        "wybranego produktu i rozdzielczosci, np. morze, obszar za granica, "
        f"brak NMT 5 m w czesci kraju); {outcome}",
    )


def _coverage_hints(run: _Run, hints_by_sheet: Mapping[str, Sequence[str]]) -> None:
    """Report provider hints for sheets without data.

    ``NO_COVERAGE_HINT``: provider hints without duplicates, at most
    ``MAX_HINT_LINES`` (full list: ``DownloadResult.no_coverage_hints``).
    """
    hints = list(dict.fromkeys(h for hs in hints_by_sheet.values() for h in hs))
    # the view directions of one oblique request share their hints
    shown = {n.message for n in run.sink.notices if n.code == NO_COVERAGE_HINT}
    hints = [hint for hint in hints if hint not in shown]
    for hint in hints[:MAX_HINT_LINES]:
        run.sink.emit("info", NO_COVERAGE_HINT, hint)
    rest = len(hints) - MAX_HINT_LINES
    if rest > 0:
        run.sink.emit(
            "info",
            NO_COVERAGE_HINT,
            f"... i {rest} innych podpowiedzi "
            "(pelna lista: DownloadResult.no_coverage_hints)",
        )


def _read_sheet_sidecar(path: Path) -> dict[str, Any] | None:
    """Sheet sidecar ``<file>.meta.json``; ``None`` if missing/unreadable."""
    import json

    sidecar = path.with_name(f"{path.name}.meta.json")
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def _sheet_sidecar_notices(
    task: SimpleNamespace, run: _Run, result: DownloadResult, paths: list[Path]
) -> None:
    """Notices read from the result sheets' sidecars and the result facts."""
    ranged = task.min_year is not None or task.max_year is not None
    _incomplete_campaign(
        run, result, paths, task.full_sheet, task.all_campaigns, ranged
    )
    _crs_mismatch(run, paths)
    _better_coverage(run, result, paths)
    _link_outside_range(run, result.link_outside_range, result.full_link_outside_range)


def _sheets_text(sheets: list[str]) -> str:
    return ", ".join(sheets[:10]) + (" ..." if len(sheets) > 10 else "")


def _incomplete_campaign(
    run: _Run,
    result: DownloadResult,
    paths: list[Path],
    full_sheet: bool,
    all_campaigns: bool,
    ranged: bool,
) -> None:
    """E13: sheets from an incomplete newest GUGiK campaign (ADR-033 split)."""

    def partial_sheet(path: Path) -> bool:
        try:
            source = (_read_sheet_sidecar(path) or {})["extra"]["source"]
            return source.get("full_sheet") is False
        except (KeyError, TypeError, AttributeError):
            return False

    partial = sorted(Path(p).stem for p in paths if partial_sheet(Path(p)))
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
        hint = "" if full_sheet else " - uzyj --full-sheet"
        groups.append(f"pelny lot nie pobrany: {_sheets_text(missing)}{hint}")
    run.sink.emit(
        "warning",
        INCOMPLETE_CAMPAIGN,
        f"najnowsza kampania GUGiK jest niepelna dla {len(partial)} "
        "arkuszy - skorowidz deklaruje arkusz nie w calosci wypelniony "
        "trescia; plik w sciezce standardowej moze miec duzo nodata/czerni "
        "(extra.source.full_sheet w sidecarze); " + "; ".join(groups),
    )


def _crs_mismatch(run: _Run, paths: list[Path]) -> None:
    """E17: sheet files in another CRS than the sheet code declares."""
    found = []
    for path in paths:
        meta = _read_sheet_sidecar(Path(path))
        if meta is None or meta.get("country") != "PL":
            continue
        request = meta.get("request")
        sheet = request.get("sheet") if isinstance(request, dict) else None
        actual = meta.get("horizontal_crs")
        if not isinstance(sheet, str) or not isinstance(actual, str):
            continue
        try:
            expected = horizontal_crs_for_sheet(sheet)
        except KartografError:
            continue
        if expected != actual:
            found.append((sheet, expected, actual))
    if not found:
        return
    found.sort()
    shown = ", ".join(
        f"{sheet} (godlo: {expected}, plik: {actual})"
        for sheet, expected, actual in found[:10]
    ) + (" ..." if len(found) > 10 else "")
    run.sink.emit(
        "warning",
        SHEET_CRS_MISMATCH,
        f"{count_text(len(found), *SHEETS)} GUGiK opublikowano w innym ukladzie "
        f"niz wskazuje godlo: {shown} - sidecar opisuje uklad pliku "
        "(horizontal_crs); deklaracja rekordu w extra.source.declared_crs",
    )


def _flight_description(flight: dict[str, Any]) -> str:
    """Describe a flight's sidecar date, ID, completeness and measured coverage."""
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


def _better_coverage(run: _Run, result: DownloadResult, paths: list[Path]) -> None:
    """Older flights of the range with better coverage (sidecar detail best-effort)."""
    better = result.better_coverage
    if not better:
        return
    lines = [
        f"dla {count_text(len(better), *OF_SHEETS)} starszy lot z przedzialu ma "
        "wieksze "
        "pokrycie niz najnowszy (dowiazanie wskazuje najnowszy):"
    ]
    shown = dict(sorted(better.items())[:10])
    sidecars = {
        Path(path).stem: _read_sheet_sidecar(Path(path))
        for path in paths
        if Path(path).stem in shown
    }
    for sheet, better_id in shown.items():
        extra = (sidecars.get(sheet) or {}).get("extra")
        if not isinstance(extra, dict):
            extra = {}
        flights = extra.get("flights")
        campaign = extra.get("campaign")
        linked_id = campaign.get("id") if isinstance(campaign, dict) else None
        linked = older = None
        if isinstance(flights, list):
            linked = next(
                (
                    f
                    for f in flights
                    if isinstance(f, dict) and f.get("id") == linked_id
                ),
                None,
            )
            older = next(
                (
                    f
                    for f in flights
                    if isinstance(f, dict) and f.get("id") == better_id
                ),
                None,
            )
        if linked is not None and older is not None:
            detail = (
                f"dowiazanie {_flight_description(linked)}; "
                f"wieksze pokrycie: {_flight_description(older)}"
            )
        else:
            detail = f"wieksze pokrycie: lot {better_id} (brak szczegolow w sidecarze)"
        lines.append(f"  {sheet}: {detail}")
    if len(better) > len(shown):
        lines.append(f"  ... i {len(better) - len(shown)} innych")
    run.sink.emit("info", BETTER_COVERAGE, "\n".join(lines))


def _campaign_dirname(path: Path) -> str:
    """``<date>_<id>`` label of a version file ``<label>_<sha8>/<file>``."""
    path = Path(path)
    if "versions" in path.parts and "_" in path.parent.name:
        return path.parent.name.rsplit("_", 1)[0]
    return path.name


def _link_outside_range(
    run: _Run, outside: dict[str, Path], full_outside: dict[str, Path] | None
) -> None:
    """Links still pointing at a flight outside the request (ADR-032 pkt 3)."""
    rows = sorted(
        [(sheet, "sciezka standardowa", t) for sheet, t in outside.items()]
        + [(sheet, "full_sheet/", t) for sheet, t in (full_outside or {}).items()]
    )
    if not rows:
        return
    lines = [
        f"{len(rows)} dowiazan wskazuje lokalny lot spoza tego zadania "
        "(dowiazanie nigdy nie cofa sie na starszy lot); pobrane loty sa "
        "w <segment>/versions/:"
    ]
    for sheet, tree, target in rows[:10]:
        lines.append(f"  {sheet}: {tree} -> dowiazanie {_campaign_dirname(target)}")
    if len(rows) > 10:
        lines.append(f"  ... i {len(rows) - 10} innych")
    run.sink.emit("info", LINK_OUTSIDE_RANGE, "\n".join(lines))


# =============================================================================
# Single-file tracks: PL cutout, CZ, LAZ
# =============================================================================


def _cutout_unit(path: Path) -> str:
    """Return the unit of a cutout.

    Unit of a cutout: the coordinates of its grid (``bbox/<coords>.tif``),
    as the area units of the other tracks.
    """
    return Path(path).stem


def _download_pl_cutout(
    task: SimpleNamespace, run: _Run, bbox: BBox, parent_request: dict[str, Any]
) -> int:
    """Download a PL cutout from GUGiK WCS.

    PL cutout (``cutout``) from GUGiK WCS: NMT/NMPT (ADR-035) or an image
    (the orthophotomap with ``coverage``, ADR-042 D14; the true
    orthophotomap).

    A source failure is recorded for the PL part; invalid input and unexpected
    errors propagate to the caller.
    """
    from kartograf.download.cutout import check_pl_cutout, download_pl_cutout
    from kartograf.download.orto_cutout import (
        check_image_cutout,
        download_image_cutout,
    )

    if run.dry:
        return 0
    common = {
        "horizontal_crs": task.horizontal_crs,
        "root": task.root,
        "cache": run.cache,
        "on_notice": run.sink.add,
    }
    result: PlCutoutResult | ImageCutoutResult
    try:
        if image_source(task.product) is not None:
            image = {
                **common,
                "product": task.product,
                "coverage": task.coverage,
                "resolution": task.resolution,
            }
            if run.check:
                run.plans.append(check_image_cutout(bbox=bbox, **image))
                return 0
            result = download_image_cutout(
                bbox=bbox,
                update=run.update,
                plan=run.loaded,
                parent_request=parent_request,
                **image,
            )
        else:
            selection = {
                **common,
                "vertical_crs": task.vertical_crs,
                "product": task.product,
            }
            if run.check:
                run.plans.append(check_pl_cutout(bbox=bbox, **selection))
                return 0
            result = download_pl_cutout(
                bbox=bbox,
                update=run.update,
                plan=run.loaded,
                parent_request=parent_request,
                **selection,
            )
    except DownloadError as e:
        # a cutout entirely off PL land (PRG mask) is "no data", like a sheet
        return run.fail("PL", "PL", _error_text(e), failure_kind(e), e)
    if result.file is not None:
        run.add(_cutout_unit(result.file.path), "PL", result.file)
    return run.add_stale(result.stale)


def _download_cz(
    task: SimpleNamespace,
    run: _Run,
    *,
    bbox: BBox | None = None,
    parent_request: dict[str, Any] | None = None,
) -> int:
    """Download or check a CZ request.

    CZ request: a sheet code (TM33 tile / SM5 sheet) or an area cutout;
    the orthophoto and the contours have their own tracks.
    """
    from kartograf.download.cz_cutout import check_cz_cutout, download_cz_cutout
    from kartograf.download.cz_sheets import (
        check_cz_sheet,
        cz_sheet_variant,
        download_cz_sheet,
    )

    if task.product == "orto":
        return _download_cz_orto(task, run, bbox=bbox, parent_request=parent_request)
    if task.product == CONTOURS:
        return _download_cz_contours(
            task, run, bbox=bbox, parent_request=parent_request
        )
    has_sheet = bbox is None
    system = cz_sheet_system(task.sheet) if has_sheet else None
    # an `auto` area request was validated for all its countries already
    countries = ("CZ",) if has_sheet or task.country == "cz" else ("CZ", "PL")
    error = cz_option_error(task, system=system, countries=countries)
    if error is not None:
        raise error
    resolution = country_value(task.resolution, "CZ")  # only SM5 may omit it
    vertical_crs = country_value(task.vertical_crs, "CZ")
    assert vertical_crs is not None  # required: checked by cz_option_error
    if run.dry:
        return 0
    common = {
        "root": task.root,
        "product": task.product,
        "vertical_crs": vertical_crs,
        "resolution": resolution,
        "cache": run.cache,
        "on_notice": run.sink.add,
    }
    try:
        if has_sheet:
            if run.check:
                run.plans.append(check_cz_sheet(sheet=task.sheet, **common))
                return 0
            label = cz_sheet_variant(
                task.sheet, task.product, resolution, vertical_crs
            ).label
            sheet = download_cz_sheet(
                sheet=task.sheet,
                update=run.update,
                plan=run.loaded,
                on_download=_announcer(
                    run.on_progress, task.sheet, f"CZ, rozdzielczosc: {label}"
                ),
                **common,
            )
            run.add(
                task.sheet,
                "CZ",
                sheet.file,
                reported_unverified=any(
                    notice.code == UNVERIFIED_LOCAL for notice in sheet.notices
                ),
            )
            return run.add_stale(sheet.stale)
        assert bbox is not None
        target = task.horizontal_crs
        if run.check:
            run.plans.append(
                check_cz_cutout(bbox=bbox, horizontal_crs=target, **common)
            )
            return 0
        cutout = download_cz_cutout(
            bbox=bbox,
            horizontal_crs=target,
            update=run.update,
            plan=run.loaded,
            parent_request=parent_request,
            on_download=_announcer(
                run.on_progress, "wycinka CZ", f"rozdzielczosc: {resolution}, {target}"
            ),
            **common,
        )
    except DownloadError as e:
        return run.fail(task.sheet or "CZ", "CZ", str(e), failure_kind(e), e)
    if cutout.file is not None:
        run.add(_cutout_unit(cutout.file.path), "CZ", cutout.file)
    return run.add_stale(cutout.stale)


def _download_cz_laz(
    task: SimpleNamespace,
    run: _Run,
    *,
    bbox: BBox | None = None,
    parent_request: dict[str, Any] | None = None,
) -> int:
    """CUZK LAZ files for an SM5/TM33 code or the index sheets of an area."""
    from kartograf.download.cz_laz import check_cz_laz, download_cz_laz

    system = cz_sheet_system(task.sheet) if bbox is None else None
    countries = ("CZ",) if bbox is None or task.country == "cz" else ("CZ", "PL")
    error = cz_option_error(task, system=system, countries=countries)
    if error is not None:
        raise error
    vertical_crs = country_value(task.vertical_crs, "CZ")
    assert vertical_crs is not None
    assert task.model is not None
    if run.dry:
        return 0
    selection = {
        "model": task.model,
        "vertical_crs": vertical_crs,
        "root": task.root,
        "sheet": task.sheet if bbox is None else None,
        "bbox": bbox,
        "cache": run.cache,
        "on_notice": run.sink.add,
    }
    try:
        if run.check:
            run.plans.append(check_cz_laz(**selection))
            return 0
        progress = run.on_progress

        def on_progress(done: int, total: int) -> None:
            if progress is not None:
                progress(DownloadProgress(done, total, "", "tiles"))

        result = download_cz_laz(
            update=run.update,
            plan=run.loaded,
            workers=run.workers,
            parent_request=parent_request,
            on_progress=on_progress if progress is not None else None,
            **selection,
        )
    except DownloadError as e:
        return run.fail(task.sheet or "CZ", "CZ", _error_text(e), failure_kind(e), e)
    for file in result.files:
        run.add(file.path.stem, "CZ", file)
    rc = run.add_stale(result.stale)
    for failure in result.failed:
        rc = run.fail(failure.sheet, "CZ", _error_text(failure.error), "download")
    return rc


def _download_cz_orto(
    task: SimpleNamespace,
    run: _Run,
    *,
    bbox: BBox | None = None,
    parent_request: dict[str, Any] | None = None,
) -> int:
    """Download or check the CZ orthophoto.

    CZ orthophoto (ADR-042 D13): an SM5 sheet or the SM5 sheets of an area
    from the CUZK index, four files each; a failed sheet does not stop the
    others (one ``UnitFailure`` per sheet).
    """
    from kartograf.download.cz_orto import (
        check_cz_orto_sheet,
        cz_orto_area_sheets,
        download_cz_orto_sheet,
    )

    # an `auto` area request was validated for all its countries already
    countries = ("CZ",) if bbox is None or task.country == "cz" else ("CZ", "PL")
    error = cz_orto_option_error(task, countries=countries)
    if error is not None:
        raise error
    if run.dry:
        return 0
    if bbox is None:
        sheets: tuple[str, ...] = (task.sheet.strip(),)
    else:
        try:
            sheets = cz_orto_area_sheets(bbox)
        except DownloadError as e:
            return run.fail("CZ", "CZ", str(e), failure_kind(e), e)
        if not sheets:
            return run.fail(
                "CZ",
                "CZ",
                "indeks arkuszy SM5 CUZK nie ma arkuszy obszaru (obszar poza CZ?)",
                "no_coverage",
            )
        what = "bbox" if task.geometry is None else f"geometry {task.geometry.name}"
        _emit_sheet_list(run, task, list(sheets), "SM5 (CUZK)", what)
    common = {
        "root": task.root,
        "cache": run.cache,
        "on_notice": run.sink.add,
    }
    rc = 0
    for done, sheet in enumerate(sheets, start=1):
        status = "completed"
        try:
            if run.check:
                run.plans.append(check_cz_orto_sheet(sheet=sheet, **common))
                continue
            result = download_cz_orto_sheet(
                sheet=sheet,
                update=run.update,
                plan=run.loaded,
                parent_request=parent_request,
                on_download=(
                    _announcer(run.on_progress, sheet, "CZ, ortofoto SM5")
                    if bbox is None
                    else None
                ),
                **common,
            )
        except DownloadError as e:
            kind = failure_kind(e)
            rc = run.fail(sheet, "CZ", str(e), kind, e)
            status = "no_coverage" if kind == "no_coverage" else "failed"
        else:
            for position, file in enumerate(result.files):
                # one CHECK_FAILED per sheet: its files share one edition lookup
                run.add(sheet, "CZ", file, reported_check_failure=position > 0)
            rc = max(rc, run.add_stale(result.stale))
            if all(file.status == "local" for file in result.files):
                status = "skipped"
        if bbox is not None and run.on_progress is not None:
            run.on_progress(DownloadProgress(done, len(sheets), sheet, status))
    return rc


def _download_cz_contours(
    task: SimpleNamespace,
    run: _Run,
    *,
    bbox: BBox | None = None,
    parent_request: dict[str, Any] | None = None,
) -> int:
    """Download or check the CZ contours.

    CZ contours (plan E1): an SM5 sheet or the SM5 sheets of an area from
    the CUZK index, one ZIP each; a failed sheet does not stop the others
    (one ``UnitFailure`` per sheet). The choices were checked by
    ``validate_request`` (a CZ-only product).
    """
    from kartograf.download.cz_contours import (
        check_cz_contours_sheet,
        cz_contours_area_sheets,
        cz_contours_sheet,
        download_cz_contours_sheet,
    )

    if bbox is None:
        sheets: tuple[str, ...] = (cz_contours_sheet(task.sheet),)
    if run.dry:
        return 0
    if bbox is not None:
        try:
            sheets = cz_contours_area_sheets(bbox)
        except DownloadError as e:
            return run.fail("CZ", "CZ", str(e), failure_kind(e), e)
        if not sheets:
            return run.fail(
                "CZ",
                "CZ",
                "indeks arkuszy SM5 CUZK nie ma arkuszy obszaru (obszar poza CZ?)",
                "no_coverage",
            )
        what = "bbox" if task.geometry is None else f"geometry {task.geometry.name}"
        _emit_sheet_list(run, task, list(sheets), "SM5 (CUZK)", what)
    rc = 0
    for done, sheet in enumerate(sheets, start=1):
        status = "completed"
        try:
            if run.check:
                run.plans.append(
                    check_cz_contours_sheet(sheet, format=task.format, root=task.root)
                )
                continue
            result = download_cz_contours_sheet(
                sheet,
                format=task.format,
                root=task.root,
                update=run.update,
                plan=run.loaded,
                parent_request=parent_request,
                cache=run.cache,
                on_notice=run.sink.add,
                on_download=(
                    _announcer(run.on_progress, sheet, f"CZ, warstwice {task.format}")
                    if bbox is None
                    else None
                ),
            )
        except DownloadError as e:
            rc = run.fail(sheet, "CZ", str(e), failure_kind(e), e)
            status = "failed"
        else:
            run.add(sheet, "CZ", result.file)
            rc = max(rc, run.add_stale(result.stale))
            if result.file is None or result.file.status == "local":
                status = "skipped"
        if bbox is not None and run.on_progress is not None:
            run.on_progress(DownloadProgress(done, len(sheets), sheet, status))
    return rc


def _download_pl_laz(
    task: SimpleNamespace,
    run: _Run,
    area: dict[str, Any],
    parent_request: dict[str, Any] | None = None,
) -> int:
    """Download or check GUGiK LAZ tiles for the PL part of a request.

    GUGiK LAZ tiles for the PL part of a sheet or area request (ADR-029);
    ``area``: ``{"sheet": code}`` (tiles of the sheet frame) or
    ``{"bbox": part}``.
    """
    from kartograf.download.laz import check_laz_area, download_laz_area

    resolve_pl_options(task)
    if run.dry:
        return 0
    selection = {
        "root": task.root,
        "vertical_crs": country_value(task.vertical_crs, "PL"),
        "min_density": task.min_density,
        "all_campaigns": task.all_campaigns,
        "min_year": task.min_year,
        "max_year": task.max_year,
        "cache": run.cache,
        "on_notice": run.sink.add,
    }
    if run.check:
        run.plans.append(check_laz_area(**area, **selection))
        return 0
    if run.on_progress is not None:
        _announcer(
            run.on_progress,
            "kafli LAZ",
            f"WFS GUGiK, {country_value(task.vertical_crs, 'PL')}",
        )()
    on_progress = run.on_progress

    def tiles(done: int, total: int) -> None:
        if on_progress is not None:
            on_progress(DownloadProgress(done, total, "", "tiles"))

    result = download_laz_area(
        **area,
        workers=run.workers,
        update=run.update,
        plan=run.loaded,
        on_progress=tiles,
        parent_request=parent_request,
        **selection,
    )
    for file in result.files:
        run.add(file.path.name, "PL", file)
    run.superseded.extend(result.superseded)
    rc = run.add_stale(result.stale)
    if result.failed:
        names = ", ".join(f.tile.sheet for f in result.failed)
        details = "".join(f"\n  {f.tile.sheet}: {f.error}" for f in result.failed)
        return run.fail(
            "PL",
            "PL",
            f"{len(result.failed)} z {count_text(len(result.tiles), *OF_TILES)} "
            "LAZ nie pobrano "
            f"(blad pobrania): {names} - ponow pobranie{details}",
            "download",
        )
    return rc
