"""
Download manager for coordinating NMT data downloads.

This module provides the DownloadManager class for downloading
single sheets and entire hierarchies of map sheets.

Supports parallel downloads via ThreadPoolExecutor when workers > 1.
"""

import concurrent.futures
import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Protocol, cast

import requests

from kartograf.core.sheet_parser import SheetParser
from kartograf.download.campaigns import (
    CampaignRef,
    campaign_extension,
    in_year_range,
    record_year,
    validate_year_bounds,
    verify_file_format,
    verify_record_url,
    verify_record_vertical_crs,
    verify_sheet_extent,
    year_range_error,
)
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    fetch_version,
    validate_update,
)
from kartograf.download.links import ensure_link, linked_version, update_sidecar_extra
from kartograf.download.plan import (
    TODO_STATUSES,
    PlanItem,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import FileStorage, storage_for_provider
from kartograf.download.versions import (
    ContentDigest,
    LocalVersion,
    VersionCommit,
    VersionRef,
    commit_version,
    list_versions,
    new_incoming_dir,
    newest_version,
    read_content,
    read_version,
    version_key,
)
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.notices import NEWER_AVAILABLE, UNVERIFIED_LOCAL, Notice, NoticeSink
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.skorowidz import SkorowidzRecord

# Outcome of one sheet: the strongest status among its files (spec 4.5).
SheetStatus = Literal["new", "unchanged", "relabeled", "local"]

logger = logging.getLogger(__name__)


@dataclass
class DownloadProgress:
    """
    Progress information for download operations.

    Attributes
    ----------
    current : int
        Number of sheets processed so far
    total : int
        Total number of sheets to process
    sheet : str
        Current sheet being processed
    status : str
        Status of current operation ("downloading", "skipped", "completed",
        "failed", "no_coverage"). ``no_coverage`` is a sheet the source has
        no data for (``NoCoverageError``: sea, area beyond the border) — an
        expected outcome, not a transport failure; it is still listed in
        ``DownloadResult.failed`` (and ``no_coverage``).
    message : str
        Optional message with additional details
    """

    current: int
    total: int
    sheet: str
    status: str
    message: str = ""

    @property
    def progress_percent(self) -> float:
        """Return progress as percentage (0-100)."""
        if self.total == 0:
            return 100.0
        return (self.current / self.total) * 100


@dataclass
class DownloadResult:
    """
    Result of a batch/hierarchy download operation.

    Attributes
    ----------
    succeeded : list[Path]
        Paths to successfully downloaded files
    failed : list[str]
        Sheet identifiers that failed to download
    skipped : list[str]
        Sheet identifiers that were skipped (already existed)
    no_coverage : list[str]
        Subset of ``failed``: sheets the source has no data for
        (``NoCoverageError``) — as opposed to a transport/service failure.
    campaign_files : dict[str, tuple[Path, ...]]
        Campaign flow (ADR-030): sheet -> version files of the campaigns
        selected by this run, downloaded and already local (for successful
        sheets). Flow without campaigns: empty.
    new, relabeled, unchanged, local : list[str]
        Successful sheets by strongest file status: a new version, the same
        content under a new campaign label (D23), downloaded content equal
        to an existing version, or only local versions used (no download).
    reused_campaign_files : dict[str, tuple[Path, ...]]
        Subset of ``campaign_files``: sheet -> version files already local
        (not downloaded in this run). Flow without campaigns: empty.
    no_coverage_hints : dict[str, tuple[str, ...]]
        Subset of the ``no_coverage`` keys: sheet -> ``NoCoverageError.hints``
        (e.g. ``use --scale 1:2000``); only sheets with a hint.
    unverified : dict[str, str]
        Subset of ``skipped``: sheet -> GUGiK index transport error with
        which a local campaign was used without checking for a newer one.
    better_coverage : dict[str, str]
        With a ranged ``all`` request, sheets whose older flight measured
        higher pixel coverage than the standard link: sheet -> flight ID.
    link_outside_range : dict[str, Path]
        With year bounds, sheets whose standard path still points to a newer
        local flight outside this request: sheet -> that campaign file.
    full_links : dict[str, Path]
        Sheets with a ``full_sheet/`` link (ADR-033) after this request:
        sheet -> that link path.
    full_link_outside_range : dict[str, Path]
        With year bounds, sheets whose ``full_sheet/`` link still points to a
        full flight outside this request: sheet -> that campaign file.
    without_full : list[str]
        With ``full_sheet=True``: sheets whose newest flight is partial and
        whose index lists no full flight within the year bounds.
    newer : dict[str, str]
        Default mode: sheet -> label of a newer campaign available in the
        index that was NOT downloaded (``update="upgrade"`` fetches it, D5).
    files : dict[str, tuple[VersionedFile, ...]]
        Successful sheets: one versioned file per selected campaign.
    stale : tuple[PlanItem, ...]
        Planned files whose source signal changed since the plan was created.
    notices : tuple[Notice, ...]
        Data messages emitted during this call, also forwarded to ``on_notice``.
    """

    succeeded: list[Path] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    no_coverage: list[str] = field(default_factory=list)
    campaign_files: dict[str, tuple[Path, ...]] = field(default_factory=dict)
    new: list[str] = field(default_factory=list)
    relabeled: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    local: list[str] = field(default_factory=list)
    reused_campaign_files: dict[str, tuple[Path, ...]] = field(default_factory=dict)
    unverified: dict[str, str] = field(default_factory=dict)
    no_coverage_hints: dict[str, tuple[str, ...]] = field(default_factory=dict)
    better_coverage: dict[str, str] = field(default_factory=dict)
    link_outside_range: dict[str, Path] = field(default_factory=dict)
    full_links: dict[str, Path] = field(default_factory=dict)
    full_link_outside_range: dict[str, Path] = field(default_factory=dict)
    without_full: list[str] = field(default_factory=list)
    newer: dict[str, str] = field(default_factory=dict)
    files: dict[str, tuple[VersionedFile, ...]] = field(default_factory=dict)
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def total(self) -> int:
        """Return total number of sheets processed."""
        return len(self.succeeded) + len(self.failed) + len(self.skipped)

    @property
    def all_paths(self) -> list[Path]:
        """Return paths of successfully downloaded files."""
        return list(self.succeeded)

    @property
    def hard_failures(self) -> list[str]:
        """``failed`` minus ``no_coverage``: transport/service failures only.

        These are the sheets worth retrying — a sheet the source has no
        data for stays missing no matter how often it is requested.
        """
        no_data = set(self.no_coverage)
        return [g for g in self.failed if g not in no_data]


@dataclass(frozen=True)
class YearRangeCheck:
    """Pre-download classification of every sheet against the requested year range.

    ``selected`` contains the records to download, newest first; ``available``
    includes all known years even when none fall inside the requested range.
    ``no_data`` identifies sheets with no years at all, while ``conflicts``
    identifies sheets with years only outside the range. ``failed`` contains
    index errors for which the year cannot be established.
    """

    selected: dict[str, tuple[SkorowidzRecord, ...]]
    available: dict[str, tuple[int, ...]]
    no_data: dict[str, NoCoverageError]
    conflicts: dict[str, tuple[int, ...]]
    failed: dict[str, DownloadError]


@dataclass(frozen=True)
class SheetFetch:
    """Internal result of downloading one sheet.

    Attributes
    ----------
    sheet : str
        The sheet.
    path : Path
        Standard path — a hardlink of the newest local version.
    skipped : bool
        Nothing was downloaded in this call (everything already local).
    downloaded : tuple[Path, ...]
        Version files committed from downloads in this call.
    reused : tuple[Path, ...]
        Version files already local (no download).
    status : str
        ``new`` (a new version), ``relabeled`` (same content, new campaign
        label, D23), ``unchanged`` (downloaded content equal to a local
        version) or ``local`` (no download) — the strongest among the files.
    version : str or None
        Label of the version the standard path points to after this call.
    unverified : str or None
        ``newest``: text of the GUGiK index TRANSPORT error
        (network, 429, 5xx) with which an existing local campaign was used
        without checking whether a newer one exists (``skipped=True``, link
        untouched). ``None`` = record resolved normally.
    better_coverage : str or None
        Flight ID with better measured coverage than the standard path
        (only for ranged ``all`` requests).
    link_outside_range : Path or None
        With year bounds: the campaign file the standard path still points to
        when it is a newer local flight this request did not select (the link
        never moves back, ADR-030 (d)). ``None`` = the link points at a
        selected flight, or no bounds.
    full_link : Path or None
        The ``full_sheet/`` link path (ADR-033) when it exists after this
        call; ``None`` = no local flight declared full has ever been linked.
    full_link_outside_range : Path or None
        With year bounds: the campaign file the ``full_sheet/`` link still
        points to when this request did not select it (never moves back).
    no_full_flight : bool
        ``full_sheet=True`` and the index has no full flight within the
        year bounds, while the newest one is partial.
    newer : str or None
        Default mode, newest flight: label of a newer campaign in the index
        kept out of the store (the local version stays, D5).
    files : tuple[VersionedFile, ...]
        One result per selected file, with its path, status, label and hash.
    """

    sheet: str
    path: Path
    skipped: bool
    downloaded: tuple[Path, ...] = ()
    reused: tuple[Path, ...] = ()
    status: SheetStatus = "local"
    version: str | None = None
    unverified: str | None = None
    better_coverage: str | None = None
    link_outside_range: Path | None = None
    full_link: Path | None = None
    full_link_outside_range: Path | None = None
    no_full_flight: bool = False
    newer: str | None = None
    files: tuple[VersionedFile, ...] = ()


@dataclass(frozen=True)
class _Pick:
    """Decision for one record of a sheet (``DownloadManager._select``).

    ``local`` set = keep that local version (``local_ref`` its campaign);
    ``None`` = download the record. ``newer``: the kept version is older
    than the record (D5, default mode). ``previous``: a local version with
    the record's label when it is downloaded anyway (``force``).
    """

    record: SkorowidzRecord
    ref: CampaignRef
    ext: str
    name: str
    local: LocalVersion | None
    local_ref: CampaignRef | None
    newer: bool
    previous: LocalVersion | None = None


@dataclass(frozen=True)
class SheetInspection:
    """Freshness of one sheet without downloading (``inspect_sheets``).

    ``picks`` follow the default-mode rule (the same as downloads);
    ``records`` are the resolved records (``upgrade`` reuses them);
    ``error`` = the index could not be checked (or no data / a year
    conflict); ``record_errors`` = invalid records (campaign, error).
    ``versions`` = local versions of a sheet without campaigns.
    """

    sheet: str
    std: Path
    picks: tuple[_Pick, ...] = ()
    records: tuple[SkorowidzRecord, ...] = ()
    available: tuple[int, ...] | None = None
    error: Exception | None = None
    record_errors: tuple[tuple[str, DownloadError], ...] = ()
    versions: tuple[LocalVersion, ...] = ()


class CampaignProvider(Protocol):
    """GUGiK provider campaign API (ADR-030; a PL-ONLY mechanism).

    ``BaseProvider`` does not declare it — the manager picks the campaign
    flow by ``supports_campaigns is True`` and casts the provider to this
    protocol.
    """

    def resolve_campaigns(
        self,
        sheet: str,
        *,
        all_campaigns: bool = False,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> list[SkorowidzRecord]:
        """False selects the newest flight within year bounds; True selects all."""

    def download_record(self, record: SkorowidzRecord, output_path: Path) -> Path: ...

    def record_source(self, record: SkorowidzRecord) -> dict: ...


# Type alias for progress callback
ProgressCallback = Callable[[DownloadProgress], None]


def _sheet_status(commits: list[VersionCommit]) -> SheetStatus:
    """The strongest commit status of a sheet; no commit = ``local``."""
    statuses = {c.status for c in commits}
    for status in ("new", "relabeled", "unchanged"):
        if status in statuses:
            return cast(SheetStatus, status)
    return "local"


def _label_of(path: Path | None) -> str | None:
    """Label of the version file ``path`` (from its version sidecar)."""
    if path is None:
        return None
    version = read_version(path.parent, path.name)
    return version.label if version is not None else None


def _version_coverage(path: Path) -> float | None:
    """``extra.coverage`` of a version sidecar (measured at commit, D13)."""
    version = read_version(path.parent, path.name)
    extra = version.meta.get("extra") if version is not None else None
    value = extra.get("coverage") if isinstance(extra, dict) else None
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return float(value) if 0 <= value <= 1 else None
    return None


def _is_transport_failure(error: DownloadError) -> bool:
    """A TRANSPORT error (network, 429, 5xx) per the ``transport/http.py`` policy.

    ``status_code`` carries the HTTP code of the last attempt
    (``http_failure``): 429 and 5xx = transport, other 4xx not. Without a
    code the cause decides (``get_with_retry`` raises ``... from`` a
    ``requests`` exception): a network/timeout error. No coverage
    (``NoCoverageError``) and response content errors (OGC report, bad
    template, XML) have neither a code nor a ``requests`` cause — they are
    not transport.
    """
    if error.status_code is not None:
        return error.status_code == 429 or error.status_code >= 500
    return isinstance(error.__cause__, requests.RequestException)


class DownloadManager:
    """
    Manages downloading of NMT data sheets.

    Coordinates between the provider (data source), storage (file system),
    and sheet parser to download single sheets or entire hierarchies.

    Two download modes:
    - By sheet code: downloads ASC files from OpenData
    - By bbox: downloads GeoTIFF float32 from WCS (1m, both vertical CRS) on the
      1 m sheet grid

    The injected provider selects the product, resolution (NMT 1m or 5m)
    and vertical CRS (EVRF2007 or KRON86 for PL). NMT 5m exists only in
    EVRF2007; bbox WCS is available only for 1m.

    Examples
    --------
    >>> from kartograf.providers.pl import create_nmt_provider
    >>> manager = DownloadManager("./data", create_nmt_provider("EVRF2007", "1m"))
    >>> result = manager.download_sheet("N-34-130-D-d-2-4")
    >>> result.files["N-34-130-D-d-2-4"][0].status
    'new'
    """

    def __init__(
        self,
        output_dir: str | Path,
        provider: BaseProvider,
        *,
        storage: FileStorage | None = None,
        workers: int = 1,
        sidecar_extra: dict | None = None,
        year: int | None = None,
        all_campaigns: bool = False,
        min_year: int | None = None,
        max_year: int | None = None,
        full_sheet: bool = False,
        on_notice: Callable[[Notice], None] | None = None,
    ):
        """
        Initialize download manager.

        Parameters
        ----------
        output_dir : str or Path
            Base directory for downloads; the provider selects the segment.
        provider : BaseProvider
            Source of the downloaded data, its resolution and vertical CRS.
            PL NMT supports 1m (EVRF2007 or KRON86) or 5m (EVRF2007 only);
            NMPT supports 1m (EVRF2007 or KRON86); orthophotos select RGB,
            CIR or B/W in the provider. No provider is created implicitly.
        storage : FileStorage, optional
            Explicit storage manager (default: storage from the provider's
            descriptor, resolution, vertical CRS and optional variant).
        workers : int, optional
            Maximum number of parallel download threads (default: 1).
            When > 1, uses ThreadPoolExecutor for parallel downloads.
        sidecar_extra : dict, optional
            Extra fields merged into the `extra` of every sidecar (stage 1:
            `parent_request` in bbox/geometry mode).
        all_campaigns : bool, optional
            False (default) selects the newest flight per sheet within the year
            bounds; True selects every flight within them. Year bounds only
            restrict admissible years. Only PL GUGiK supports campaigns;
            LAZ with True does not deduplicate coverage.
        year : int, optional
            One acquisition year (equivalent to equal ``min_year``/``max_year``).
        min_year, max_year : int, optional
            Inclusive bounds on the campaign acquisition year.
        full_sheet : bool, optional
            ADR-033: with ``all_campaigns=False``, when the newest flight within
            the year bounds is not declared full, also download the newest
            flight declared full within them (at most one extra flight per
            sheet) and link it in ``full_sheet/``. No effect with True.

        Raises
        ------
        ValidationError
            Invalid year bounds or a provider without campaigns used with
            a year bound, ``all_campaigns=True`` or ``full_sheet=True``;
            incompatible resolution/CRS.
        """
        if year is not None:
            if min_year is not None or max_year is not None:
                raise ValidationError(
                    "--year wyklucza sie z --min-year/--max-year "
                    "(--year Y to skrot --min-year Y --max-year Y)"
                )
            min_year = max_year = year
        validate_year_bounds(min_year, max_year)
        self._provider = provider
        # Do not infer a different dataset when the provider has no resolution
        # or height dimension (e.g. ortho or lightweight test providers).
        provider_resolution = getattr(provider, "resolution", None)
        resolution = (
            provider_resolution if isinstance(provider_resolution, str) else None
        )
        provider_vertical_crs = getattr(provider, "vertical_crs", None)
        vertical_crs = (
            provider_vertical_crs if isinstance(provider_vertical_crs, str) else None
        )
        self._record_vertical_crs = vertical_crs
        if storage is None:
            storage = storage_for_provider(
                output_dir, provider, resolution=resolution, vertical_crs=vertical_crs
            )
        self._storage = storage
        self._vertical_crs = vertical_crs
        self._resolution = resolution
        self._default_ext = self._provider.default_extension
        self._workers = max(1, workers)
        self._sidecar_extra = sidecar_extra
        self._on_notice = on_notice
        # `is True`, not truthiness: Mock/Mock(spec=...) yields a Mock -> plain flow.
        self._campaign_aware = (
            getattr(self._provider, "supports_campaigns", False) is True
        )
        if not self._campaign_aware and (
            all_campaigns or min_year is not None or max_year is not None or full_sheet
        ):
            raise ValidationError(
                f"Provider {self._provider.name} nie obsluguje kampanii "
                f"(--all-campaigns/--min-year/--max-year/--year/--full-sheet)"
            )
        self._all_campaigns = all_campaigns
        self._min_year = min_year
        self._max_year = max_year
        self._full_sheet = full_sheet
        self._has_range = min_year is not None or max_year is not None

    @property
    def vertical_crs(self) -> str | None:
        """Actual provider vertical CRS, or None for data without heights."""
        return self._vertical_crs

    @property
    def resolution(self) -> str | None:
        """Actual provider resolution, or None when the product has no grid."""
        return self._resolution

    @property
    def all_campaigns(self) -> bool:
        """False selects the newest flight in the year range; True selects all."""
        return self._all_campaigns

    @property
    def full_sheet(self) -> bool:
        """Whether the newest declared-full flight is fetched too (ADR-033)."""
        return self._full_sheet

    @property
    def min_year(self) -> int | None:
        """Lower bound of the campaign year (``None`` = no bound)."""
        return self._min_year

    @property
    def max_year(self) -> int | None:
        """Upper bound of the campaign year (``None`` = no bound)."""
        return self._max_year

    @property
    def provider(self) -> BaseProvider:
        """Return the data provider."""
        return self._provider

    @property
    def storage(self) -> FileStorage:
        """Return the storage manager."""
        return self._storage

    @property
    def _campaign_provider(self) -> CampaignProvider:
        """Campaign-flow provider (``supports_campaigns is True``, GUGiK)."""
        return cast(CampaignProvider, self._provider)

    def check_year_range(
        self, sheets: list[str], workers: int | None = None
    ) -> YearRangeCheck:
        """Check every PL sheet against the year bounds before any download.

        The complete campaign list for each sheet is fetched exactly once,
        without year bounds, so callers can inspect ``available`` even when
        ``selected`` is empty. This public phase performs no file downloads;
        callers must abort if ``failed`` or ``conflicts`` is nonempty.
        ``workers`` overrides the manager's default worker count for the queries.
        """
        if not self._campaign_aware or not self._has_range:
            raise ValidationError(
                "Sprawdzenie przedzialu wymaga kampanii PL i granicy roku"
            )

        def classify(
            sheet: str,
        ) -> tuple[str, tuple[SkorowidzRecord, ...], tuple[int, ...], Exception | None]:
            try:
                records = self._campaign_provider.resolve_campaigns(
                    sheet, all_campaigns=True
                )
            except DownloadError as e:
                return sheet, (), (), e
            years = tuple(
                sorted({y for r in records if (y := record_year(r)) is not None})
            )
            selected = tuple(
                sorted(
                    (
                        r
                        for r in records
                        if in_year_range(record_year(r), self._min_year, self._max_year)
                    ),
                    key=lambda r: (r.aktualnosc, r.dt_pzgik or "", r.url),
                    reverse=True,
                )
            )
            if not self._all_campaigns:
                selected = selected[:1]
            return sheet, selected, years, None

        pool = self._workers if workers is None else workers
        if len(sheets) > 1 and pool > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=pool) as executor:
                rows = list(executor.map(classify, sheets))
        else:
            rows = [classify(g) for g in sheets]

        selected: dict[str, tuple[SkorowidzRecord, ...]] = {}
        available: dict[str, tuple[int, ...]] = {}
        no_data: dict[str, NoCoverageError] = {}
        conflicts: dict[str, tuple[int, ...]] = {}
        failed: dict[str, DownloadError] = {}
        for sheet, records, years, error in rows:
            if isinstance(error, NoCoverageError):
                no_data[sheet] = error
            elif isinstance(error, DownloadError):
                failed[sheet] = error
            elif not years:
                no_data[sheet] = NoCoverageError(f"Brak kampanii {sheet}", sheet=sheet)
            elif not records:
                conflicts[sheet] = years
            else:
                selected[sheet] = records
                available[sheet] = years
        return YearRangeCheck(selected, available, no_data, conflicts, failed)

    def _checked_range(
        self,
        sheets: list[str],
        workers: int | None = None,
        update: UpdateMode | None = None,
    ) -> YearRangeCheck:
        """Abort the whole task on an index failure or a year conflict.

        D14: in the default mode an index TRANSPORT failure is not fatal when
        EVERY sheet of the task (except those without data) has a local
        version from the year range — the failed sheets stay in
        ``check.failed`` and are served from local versions with a warning.
        """
        check = self.check_year_range(sheets, workers)
        if check.failed and not (
            update is None
            and all(_is_transport_failure(e) for e in check.failed.values())
            and all(
                self._local_in_range(g) is not None
                for g in sheets
                if g not in check.no_data
            )
        ):
            names = ", ".join(check.failed)
            raise DownloadError(
                f"nie udalo sie sprawdzic roku danych dla {len(check.failed)} z "
                f"{len(sheets)} arkuszy (blad skorowidza, nie brak danych): "
                f"{names} - ponow pobranie"
            )
        if check.conflicts:
            raise year_range_error(
                check.conflicts, self._min_year, self._max_year, total=len(sheets)
            )
        return check

    def _in_range(self, version: LocalVersion) -> bool:
        """A campaign version whose acquisition year is in the bounds."""
        ref = CampaignRef.from_sidecar(version.meta)
        if ref is None:
            return False
        return not self._has_range or in_year_range(
            ref.year, self._min_year, self._max_year
        )

    def _current_local(
        self, std: Path, versions: list[LocalVersion]
    ) -> LocalVersion | None:
        """The local campaign version the default mode keeps (D5): the
        standard link target when it is a version in range, else the newest
        version in range."""
        in_range = [v for v in versions if self._in_range(v)]
        target = linked_version(std)
        if target is not None:
            for version in in_range:
                if os.path.abspath(version.path) == os.path.abspath(target):
                    return version
        return newest_version(in_range)

    def _local_in_range(self, sheet: str) -> LocalVersion | None:
        std = self._storage.get_path(sheet, self._default_ext)
        root = self._storage.get_versions_root(sheet)
        return self._current_local(std, list_versions(root, std.name))

    def _local_unverified(self, sheet: str, error: DownloadError) -> SheetFetch:
        """D14: a sheet whose index check failed, served from a local version."""
        version = self._local_in_range(sheet)
        if version is None:  # pragma: no cover — guarded by _checked_range
            raise error
        std = self._storage.get_path(sheet, self._default_ext)
        self._link(std, version.path, version_key(version), refresh=False)
        logger.warning(
            f"{sheet}: skorowidz GUGiK niedostepny ({error}) - uzyto lokalnej "
            f"wersji {version.label} z zakresu lat bez sprawdzenia nowszej"
        )
        full = self._storage.get_full_sheet_path(sheet, self._default_ext)
        return SheetFetch(
            sheet,
            std,
            skipped=True,
            reused=(version.path,),
            status="local",
            version=version.label,
            unverified=str(error),
            files=(
                VersionedFile(
                    std,
                    "local",
                    version.label,
                    version.sha256,
                    version.path,
                    unverified=f"check_failed: {error}",
                ),
            ),
            full_link=full if linked_version(full) is not None else None,
        )

    # =========================================================================
    # Download by sheet code → ASC
    # =========================================================================

    def download_sheet(
        self,
        sheet: str,
        *,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        on_progress: ProgressCallback | None = None,
        on_download: Callable[[], None] | None = None,
    ) -> DownloadResult:
        """Download one PL sheet (expand coarser PL-1992 codes).

        A direct leaf failure raises ``DownloadError``. A hierarchy collects
        per-sheet failures in the result. With ``plan``, only matching positions
        are executed and changed source signals are reported in ``stale``.
        ``on_download`` runs before the first actual leaf download.
        """
        validate_update(update)
        if plan is not None and update != "upgrade":
            raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
        parser = SheetParser(sheet)
        if parser.system != "2000" and parser.scale != "1:10000":
            return self.download_hierarchy(
                sheet, "1:10000", update=update, plan=plan, on_progress=on_progress
            )
        if plan is not None:
            return self.download_sheets(
                [parser.sheet], update=update, plan=plan, on_progress=on_progress
            )

        check = (
            self._checked_range([parser.sheet], update=update)
            if self._has_range
            else None
        )
        if check is not None and parser.sheet in check.no_data:
            raise check.no_data[parser.sheet]
        if check is not None and parser.sheet in check.failed:
            fetch = self._local_unverified(parser.sheet, check.failed[parser.sheet])
        else:
            fetch = self._fetch_sheet(
                parser.sheet,
                update,
                on_download,
                records=check.selected[parser.sheet] if check is not None else None,
                available=check.available[parser.sheet] if check is not None else None,
            )
        result = DownloadResult()
        self._record(
            result, parser.sheet, fetch, "skipped" if fetch.skipped else "completed"
        )
        return self._finish_result(result, single=True)

    def download_hierarchy(
        self,
        sheet: str,
        target_scale: str,
        *,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download every descendant to ``target_scale``; collect leaf failures."""
        validate_update(update)
        descendants = SheetParser(sheet).get_all_descendants(target_scale)
        sheets = [descendant.sheet for descendant in descendants]
        logger.info(
            "Starting hierarchy download: %s -> %s (%d sheets, workers=%d)",
            sheet,
            target_scale,
            len(sheets),
            self._workers,
        )
        return self.download_sheets(
            sheets, update=update, plan=plan, on_progress=on_progress
        )

    @staticmethod
    def expand_sheets(sheets: list[str]) -> list[str]:
        """
        Leaf sheets actually requested from the provider for a list of sheets.

        PL-1992 sheets coarser than 1:10000 expand to their 1:10000
        descendants (like :meth:`download_sheet`); 1:10000 and PL-2000 sheets
        stay as they are. Identifiers are normalized, duplicates dropped,
        first-seen order kept.

        Raises
        ------
        ParseError
            If any sheet is invalid
        """
        leaves: list[str] = []
        seen: set[str] = set()
        for sheet in sheets:
            parser = SheetParser(sheet)
            if parser.system != "2000" and parser.scale != "1:10000":
                expanded = [d.sheet for d in parser.get_all_descendants("1:10000")]
            else:
                expanded = [parser.sheet]
            for leaf in expanded:
                if leaf not in seen:
                    seen.add(leaf)
                    leaves.append(leaf)
        return leaves

    def download_sheets(
        self,
        sheets: list[str],
        *,
        update: UpdateMode | None = None,
        plan: UpdatePlan | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download normalized leaf sheets; with ``plan`` execute only planned files.

        Individual download errors are collected; a year-range preflight
        error aborts the whole unplanned request before the first download.
        """
        validate_update(update)
        if plan is not None and update != "upgrade":
            raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
        if plan is not None:
            require_store(plan, store_id(self._storage.output_dir))
        leaves = self.expand_sheets(sheets)
        if plan is not None:
            return self._download_planned(leaves, plan, on_progress)
        logger.info(
            "Starting sheet list download: %d sheets, workers=%d",
            len(leaves),
            self._workers,
        )
        return self._download_many(leaves, update, on_progress, self._workers)

    def inspect_sheets(self, sheets: list[str]) -> list[SheetInspection]:
        """Freshness of the leaf sheets WITHOUT downloading (spec 4.1, 4.4).

        Campaign providers: the records of the request (strategy, year
        bounds via ``check_year_range``, ``full_sheet``) compared with the
        local versions by the same rule as the default download mode
        (``_select``). An index error, no data or a year conflict is the
        sheet's ``error``. Providers without campaigns have no cheap signal:
        only their local versions are listed.
        """
        leaves = self.expand_sheets(sheets)
        if not self._campaign_aware:
            result = []
            for sheet in leaves:
                std = self._storage.get_path(sheet, self._default_ext)
                root = self._storage.get_versions_root(sheet)
                versions = tuple(list_versions(root, std.name))
                result.append(SheetInspection(sheet, std, versions=versions))
            return result
        check = self.check_year_range(leaves) if self._has_range else None

        def inspect(sheet: str) -> SheetInspection:
            std = self._storage.get_path(sheet, self._default_ext)
            available = None
            try:
                if check is not None:
                    if sheet in check.failed:
                        raise check.failed[sheet]
                    if sheet in check.no_data:
                        raise check.no_data[sheet]
                    if sheet in check.conflicts:
                        raise year_range_error(
                            {sheet: check.conflicts[sheet]},
                            self._min_year,
                            self._max_year,
                            total=1,
                        )
                    available = check.available[sheet]
                    chosen, _ = self._resolve_chosen(sheet, check.selected[sheet])
                else:
                    chosen, _ = self._resolve_chosen(sheet)
            except DownloadError as e:
                return SheetInspection(sheet, std, error=e)
            picks, errors = self._select(sheet, chosen, None)
            return SheetInspection(
                sheet,
                std,
                picks=tuple(picks),
                records=tuple(chosen),
                available=available,
                record_errors=tuple(errors),
            )

        if len(leaves) > 1 and self._workers > 1:
            with concurrent.futures.ThreadPoolExecutor(self._workers) as executor:
                return list(executor.map(inspect, leaves))
        return [inspect(sheet) for sheet in leaves]

    def check_sheets(self, sheets: list[str]) -> UpdatePlan:
        """Return the PL-sheet update plan without downloading any files."""
        from kartograf.download.updates import _items

        items = [
            item
            for inspection in self.inspect_sheets(sheets)
            for item in _items(self, inspection)
        ]
        return new_plan(self._storage.output_dir, items)

    def _download_planned(
        self,
        leaves: list[str],
        plan: UpdatePlan,
        on_progress: ProgressCallback | None,
    ) -> DownloadResult:
        """Recheck and execute exactly the selected positions of this request."""
        from kartograf.download.updates import _items

        requested = set(leaves)
        planned = [
            item
            for item in plan.items_for("pl_sheet")
            if item.status in TODO_STATUSES and item.unit in requested
        ]
        result = DownloadResult()
        if not planned:
            return result
        sheets = list(dict.fromkeys(item.unit for item in planned))
        checked: set[str] = set()
        fresh: list[PlanItem] = []
        picks: dict[tuple[str, str, str], _Pick] = {}
        available: dict[str, tuple[int, ...] | None] = {}
        for inspection in self.inspect_sheets(sheets):
            sheet = inspection.sheet
            if inspection.error is not None:
                result.failed.append(sheet)
                result.errors[sheet] = str(inspection.error)
                self._emit(
                    on_progress,
                    result.total,
                    len(sheets),
                    sheet,
                    "failed",
                    str(inspection.error),
                )
                continue
            if not inspection.picks:
                # Sources without a comparable signal have only one file.
                current = _items(self, inspection)
                scope = replace(
                    plan, items=tuple(i for i in planned if i.unit == sheet)
                )
                todo, stale = select_planned(scope, current, "pl_sheet")
                result.stale += tuple(stale)
                if todo:
                    _, fetch, status, message, hints = self._download_single_sheet_task(
                        sheet, "upgrade"
                    )
                    self._record(result, sheet, fetch, status, hints, message)
                    self._emit(
                        on_progress, result.total, len(sheets), sheet, status, message
                    )
                continue
            checked.add(sheet)
            fresh.extend(_items(self, inspection))
            available[sheet] = inspection.available
            for pick in inspection.picks:
                picks[(sheet, pick.name, pick.ref.dirname)] = pick
        scope = replace(plan, items=tuple(i for i in planned if i.unit in checked))
        todo, stale = select_planned(scope, fresh, "pl_sheet")
        result.stale += tuple(stale)
        records: dict[str, list[SkorowidzRecord]] = {}
        for item in todo:
            pick = picks[(item.unit, item.name, item.available_label or "")]
            records.setdefault(item.unit, []).append(pick.record)
        for sheet, chosen in records.items():
            try:
                fetch = self._fetch_campaigns(
                    sheet,
                    "upgrade",
                    records=tuple(chosen),
                    available=available[sheet],
                    exact=True,
                )
            except DownloadError as error:
                result.failed.append(sheet)
                result.errors[sheet] = str(error)
                self._emit(
                    on_progress, result.total, len(sheets), sheet, "failed", str(error)
                )
                continue
            status = "skipped" if fetch.skipped else "completed"
            self._record(result, sheet, fetch, status)
            self._emit(on_progress, result.total, len(sheets), sheet, status)
        return self._finish_result(result)

    def _fetch_sheet(
        self,
        sheet: str,
        update: UpdateMode | None,
        on_download: Callable[[], None] | None = None,
        records: tuple[SkorowidzRecord, ...] | None = None,
        available: tuple[int, ...] | None = None,
    ) -> SheetFetch:
        """
        Download one sheet — the single "download a sheet" implementation (D10).

        A provider with campaigns (``supports_campaigns is True``) takes the
        campaign flow (``_fetch_campaigns``), any other — today's flow
        (``_fetch_sheet_plain``). ``on_download`` is called right before the
        first download (sequential mode reports ``"downloading"``).
        """
        if self._campaign_aware:
            return self._fetch_campaigns(
                sheet, update, on_download, records=records, available=available
            )
        return self._fetch_sheet_plain(sheet, update, on_download)

    def _fetch_sheet_plain(
        self,
        sheet: str,
        update: UpdateMode | None,
        on_download: Callable[[], None] | None = None,
    ) -> SheetFetch:
        """
        Flow without campaigns (stubs, foreign providers) on the version store.

        Without ``force`` the newest local version is used without a
        download (no cheap freshness signal: ``upgrade`` keeps it too);
        otherwise the provider downloads into a private staging
        directory and the file becomes a version labelled with the UTC
        download date (``downloaded``, plan 1/3 decision 7). The standard path
        is a hardlink of the newest version. Provider exceptions propagate
        unchanged.
        """
        std = self._storage.get_path(sheet, self._default_ext)
        slot = FileSlot(
            output_dir=self._storage.output_dir,
            std=std,
            versions_base=self._storage.get_versions_base(sheet),
            versions_root=self._storage.get_versions_root(sheet),
            ext=self._default_ext,
        )

        def fetch(staged: Path) -> None:
            if on_download is not None:
                on_download()
            logger.info(f"Downloading {sheet}...")
            path = Path(self._provider.download(sheet, staged))
            if path != staged:
                os.replace(path, staged)

        result = fetch_version(
            slot,
            update,
            signal="none",
            fetch=fetch,
            version=VersionRef.downloaded(),
            write_sidecar=lambda data, ref, dg, _http: self._write_sidecar(
                data, {"sheet": sheet}, digest=dg, version=ref
            ),
        )
        if result.status == "local":
            logger.info(f"{sheet}: lokalna wersja {result.label}")
        return SheetFetch(
            sheet,
            std,
            skipped=result.status == "local",
            # "reused" is only for derived files (HSG), never a sheet
            status=cast(SheetStatus, result.status),
            version=result.label,
            files=(result,),
        )

    @staticmethod
    def _link(
        link: Path, target: Path, key: tuple[str, str, str], *, refresh: bool
    ) -> Path:
        """``ensure_link`` raising ``DownloadError`` (R5: a sheet failure)."""
        try:
            return ensure_link(link, target, key, refresh=refresh).target
        except OSError as e:
            raise DownloadError(f"dowiazanie {link}: {e}") from e

    def _download_version(
        self,
        sheet: str,
        record: SkorowidzRecord,
        ref: CampaignRef,
        ext: str,
        available: tuple[int, ...] | None,
    ) -> VersionCommit:
        """Download one campaign file and commit it as a version (spec 3.1).

        ``download_record`` writes into a private staging directory, then
        ``verify_file_format`` and ``verify_sheet_extent`` (B4); one read gives
        sha256 and — for a flight not declared full — ``extra.coverage``
        (D13, D20); the mandatory version sidecar is written exclusively.
        Any failure leaves no version and no staged file.
        """
        root = self._storage.get_versions_root(sheet)
        name = self._storage.get_path(sheet, ext).name
        staged = new_incoming_dir(self._storage.get_versions_base(sheet)) / name
        try:
            self._campaign_provider.download_record(record, staged)
            verify_file_format(staged, ext)
            verify_sheet_extent(staged, sheet, ext)
            digest = read_content(staged, ext=ext, coverage=ref.full_sheet is not True)
            return commit_version(
                staged,
                root,
                name,
                VersionRef(ref.dirname, "campaign"),
                digest,
                lambda data, version, dg: self._write_campaign_sidecar(
                    data,
                    sheet,
                    record,
                    ref,
                    available=available,
                    digest=dg,
                    version=version,
                ),
            )
        finally:
            shutil.rmtree(staged.parent, ignore_errors=True)

    def _resolve_chosen(
        self, sheet: str, records: tuple[SkorowidzRecord, ...] | None = None
    ) -> tuple[list[SkorowidzRecord], bool]:
        """Records of the request (strategy, year bounds, ``full_sheet``).

        ``records`` = already selected by the year-range check; otherwise
        ``resolve_campaigns`` (an index error propagates). ``full_sheet`` with
        ``newest``: a partial newest record gets the newest declared-full
        record of the range appended; ``True`` in the result = none exists.
        """
        if records is None:
            chosen = list(
                self._campaign_provider.resolve_campaigns(
                    sheet, all_campaigns=self._all_campaigns, min_year=self._min_year
                )
            )
        else:
            chosen = list(records)
        if (
            self._full_sheet
            and not self._all_campaigns
            and chosen[0].full_sheet is not True
        ):
            pool = self._campaign_provider.resolve_campaigns(
                sheet,
                all_campaigns=True,
                min_year=self._min_year,
                max_year=self._max_year,
            )
            extra_full = next((r for r in pool if r.full_sheet is True), None)
            if extra_full is None:
                return chosen, True
            chosen.append(extra_full)
        return chosen, False

    def _select(
        self,
        sheet: str,
        chosen: list[SkorowidzRecord],
        update: UpdateMode | None,
    ) -> tuple[list[_Pick], list[tuple[str, DownloadError]]]:
        """The single rule "local or download" per record (spec 4.2, D5).

        Each record is checked BEFORE the network (``verify_record_url``, B4;
        ``verify_record_vertical_crs``; extension from ``format``) — a bad
        record is an error of that campaign. Without ``force`` a local
        version with the record's label is kept. Default mode, newest flight
        not local: another local version in range (the standard link target
        first) is kept and ``newer`` says whether the record is newer than
        it. Anything else is downloaded. Used by downloads and by
        ``inspect_sheets`` (used by ``check_sheets``), so both read one rule.
        """
        std = self._storage.get_path(sheet, self._default_ext)
        root = self._storage.get_versions_root(sheet)
        known: dict[str, list[LocalVersion]] = {}  # file name -> local versions
        picks: list[_Pick] = []
        errors: list[tuple[str, DownloadError]] = []  # (campaign, error)
        for index, record in enumerate(chosen):
            try:  # R16 (cf. Q10): bad date = this campaign fails
                ref = CampaignRef.from_record(record)
            except DownloadError as e:
                errors.append((record.url, e))
                continue
            try:  # B4 + record datum + extension - before the network
                verify_record_url(record.url, sheet)
                verify_record_vertical_crs(record, self._record_vertical_crs, sheet)
                ext = campaign_extension(ref, self._default_ext)
            except DownloadError as e:
                errors.append((ref.dirname, e))
                continue
            name = self._storage.get_path(sheet, ext).name
            if name not in known:
                known[name] = list_versions(root, name)
            same = newest_version(v for v in known[name] if v.label == ref.dirname)
            if update != "force" and same is not None:
                picks.append(_Pick(record, ref, ext, name, same, ref, False))
                continue
            if (
                update is None
                and same is None
                and not self._all_campaigns
                and index == 0
            ):
                current = self._current_local(std, known[name])
                current_ref = (
                    CampaignRef.from_sidecar(current.meta)
                    if current is not None
                    else None
                )
                if current is not None and current_ref is not None:
                    newer = ref.sort_key > current_ref.sort_key
                    picks.append(
                        _Pick(record, ref, ext, name, current, current_ref, newer)
                    )
                    continue
            picks.append(_Pick(record, ref, ext, name, None, None, False, same))
        return picks, errors

    def _fetch_campaigns(
        self,
        sheet: str,
        update: UpdateMode | None,
        on_download: Callable[[], None] | None = None,
        records: tuple[SkorowidzRecord, ...] | None = None,
        available: tuple[int, ...] | None = None,
        *,
        exact: bool = False,
    ) -> SheetFetch:
        """
        Campaign flow (ADR-030) on the version store (spec 3).

        Records from ``provider.resolve_campaigns`` (never an empty list —
        none = ``NoCoverageError``). For each campaign, BEFORE the network:
        ``verify_record_url`` (the record URL must name the sheet, B4),
        ``verify_record_vertical_crs`` (the record vertical datum vs the
        provider ``vertical_crs``) and the extension from the record
        ``format`` field. Without ``force`` a local version labelled
        ``<date>_<id>`` of the campaign is used without a download (the
        existence of the standard path is NOT a reason to skip). Default mode
        (D5): when the newest flight is not local but another local version
        in range is (the standard link target first), that one is kept and a
        newer record is only reported (``SheetFetch.newer``); ``upgrade``
        downloads it. Otherwise ``_download_version`` commits the file as a
        version (``new``, ``unchanged`` or ``relabeled``, D23). After the
        campaigns are
        collected the standard path points to the newest LOCAL version of
        this request (``max`` by ``sort_key``; ``ensure_link`` never moves
        the link back), and the ``full_sheet/`` path (ADR-033) to the newest
        one declared full (``full_sheet is True``); without such a campaign
        the ``full_sheet/`` link stays as it is.

        Ranged ``all`` requests list the local flights in the standard
        sidecar; when the linked flight is partial and there are several,
        their coverage (``extra.coverage`` of the version sidecars, measured
        at commit, D13) gives ``better_coverage`` — a declared-full flight
        counts as fully covered.

        Concurrency: the link is set ONCE per sheet, after all its campaigns
        are collected, and ``expand_sheets`` deduplicates sheets — one sheet =
        one thread; concurrent writers of the same version are resolved by
        ``commit_version`` (D18).

        Index outage (I-1, every strategy) without year bounds in the default
        mode: when ``resolve_campaigns`` ends with a TRANSPORT error
        (``_is_transport_failure``) and the standard path points to an
        existing local version (``linked_version``) — NOT a failure:
        ``logger.warning`` and ``SheetFetch(skipped=True,
        unverified=<error>)`` from the local version, link unchanged.
        ``upgrade``/``force``, no local version or another error — an
        exception. With year bounds the outage is handled per task (D14,
        ``_checked_range``).

        ``full_sheet=True`` with ``newest``: when the chosen record is not
        declared full, the full list within the year bounds
        (``resolve_campaigns(all_campaigns=True)``) supplies the newest
        declared-full record as one extra campaign; none =
        ``SheetFetch.no_full_flight``. An index error of that call is a
        sheet failure, as with ``all``.

        Raises
        ------
        NoCoverageError
            No campaigns (from ``resolve_campaigns``).
        DownloadError
            Failure of at least one campaign (an invalid record
            ``aktualnosc`` too) or of a link — all in one message;
            successful versions stay on disk, and the link points to the
            newest of them.
        """
        std = self._storage.get_path(sheet, self._default_ext)
        if records is None:
            try:
                chosen, no_full_flight = self._resolve_chosen(sheet)
            except DownloadError as e:
                # I-1 for every strategy without year bounds (spec 4.2)
                if update is None and not self._has_range and _is_transport_failure(e):
                    fetch = self._local_newest(sheet, std, e)
                    if fetch is not None:
                        return fetch
                raise
        elif exact:  # Execute exactly the records selected by the plan.
            chosen, no_full_flight = list(records), False
        else:
            chosen, no_full_flight = self._resolve_chosen(sheet, records)
        logger.info(
            "%s: %d kampanii (%s)",
            sheet,
            len(chosen),
            "all" if self._all_campaigns else "newest",
        )
        picks, errors = self._select(sheet, chosen, update)
        downloaded: list[Path] = []
        reused: list[Path] = []
        local: list[tuple[CampaignRef, Path]] = []
        commits: list[VersionCommit] = []
        started = False
        newer: str | None = None
        files: list[VersionedFile] = []
        for pick in picks:
            if pick.local is not None and pick.local_ref is not None:
                logger.info(f"{sheet} {pick.local.label}: lokalna wersja")
                if pick.newer:
                    newer = pick.ref.dirname
                reused.append(pick.local.path)
                files.append(
                    VersionedFile(
                        std,
                        "local",
                        pick.local.label,
                        pick.local.sha256,
                        pick.local.path,
                        newer=pick.ref.dirname if pick.newer else None,
                    )
                )
                local.append((pick.local_ref, pick.local.path))
                continue
            if on_download is not None and not started:
                on_download()
                started = True
            logger.info(f"Downloading {sheet} {pick.ref.dirname}...")
            try:
                commit = self._download_version(
                    sheet, pick.record, pick.ref, pick.ext, available
                )
            except DownloadError as e:
                errors.append((pick.ref.dirname, e))
                continue
            commits.append(commit)
            files.append(
                VersionedFile(
                    std,
                    commit.status,
                    commit.label,
                    commit.sha256,
                    commit.path,
                )
            )
            downloaded.append(commit.path)
            local.append((pick.ref, commit.path))
        refreshed = {c.path for c in commits if c.status != "unchanged"}
        linked_target: Path | None = None
        link_error: DownloadError | None = None
        if local:
            ref, path = max(local, key=lambda rp: rp[0].sort_key)
            try:
                linked_target = self._link(
                    std, path, ref.sort_key, refresh=path in refreshed
                )
            except DownloadError as e:  # R5: sheet failure, not an abort of the list
                link_error = e
        # ADR-033: the second link, same mechanics, only declared-full flights.
        full = self._storage.get_full_sheet_path(sheet, self._default_ext)
        full_target: Path | None = None
        full_link_error: DownloadError | None = None
        candidates = [rp for rp in local if rp[0].full_sheet is True]
        if candidates:
            ref, path = max(candidates, key=lambda rp: rp[0].sort_key)
            try:
                full_target = self._link(
                    full, path, ref.sort_key, refresh=path in refreshed
                )
            except DownloadError as e:
                full_link_error = e
        else:
            full_target = linked_version(full)  # existing link stays untouched
        # Q10: full failure list
        if errors or link_error is not None or full_link_error is not None:
            problems = []
            if errors:
                listing = ", ".join(f"{name}: {e}" for name, e in errors)
                problems.append(
                    f"nie pobrano {len(errors)} z {len(chosen)} kampanii ({listing})"
                )
            problems.extend(
                str(e) for e in (link_error, full_link_error) if e is not None
            )
            raise DownloadError(f"{sheet}: " + "; ".join(problems), sheet=sheet)
        better_coverage = None
        if self._has_range and self._all_campaigns and linked_target is not None:
            better_coverage = self._add_range_flights(std, local, linked_target)
        # ADR-032 point 3 (U15): the link never moves back, so with year bounds
        # it may keep pointing at a newer local flight this request did not pick.
        local_paths = {os.path.abspath(path) for _, path in local}
        link_outside_range = None
        if (
            self._has_range
            and linked_target is not None
            and os.path.abspath(linked_target) not in local_paths
        ):
            link_outside_range = linked_target
        full_link_outside_range = None
        if (
            self._has_range
            and full_target is not None
            and os.path.abspath(full_target) not in local_paths
        ):
            full_link_outside_range = full_target
        return SheetFetch(
            sheet,
            std,
            skipped=not downloaded,
            downloaded=tuple(downloaded),
            reused=tuple(reused),
            status=_sheet_status(commits),
            version=_label_of(linked_target),
            better_coverage=better_coverage,
            link_outside_range=link_outside_range,
            full_link=full if full_target is not None else None,
            full_link_outside_range=full_link_outside_range,
            no_full_flight=no_full_flight,
            newer=newer,
            files=tuple(files),
        )

    def _add_range_flights(
        self, std: Path, local: list[tuple[CampaignRef, Path]], linked_target: Path
    ) -> str | None:
        """List local flights (and their coverage) in the standard link sidecar.

        Link selection has already finished and is never changed by this phase.
        Coverage comes from the version sidecars (measured at commit, D13);
        a version sidecar is never written here. A newer local link outside
        the current selection cannot be compared with these flights; keep its
        metadata but do not infer a better flight.
        """
        ordered = sorted(local, key=lambda rp: rp[0].sort_key, reverse=True)
        linked = next(
            (
                ref
                for ref, path in ordered
                if os.path.abspath(path) == os.path.abspath(linked_target)
            ),
            None,
        )
        measure = (
            len(ordered) > 1 and linked is not None and linked.full_sheet is not True
        )
        flights: list[dict] = []
        scored: list[tuple[float, CampaignRef]] = []
        linked_score: float | None = None
        for ref, path in ordered:
            flight: dict[str, object] = {
                "id": ref.id,
                "date": ref.date,
                "full_sheet": ref.full_sheet,
            }
            if measure:
                coverage = _version_coverage(path)
                if coverage is not None:
                    flight["coverage"] = coverage
                # a declared-full flight is not measured (D13): fully covered
                score = 1.0 if ref.full_sheet is True else coverage
                if score is not None:
                    scored.append((score, ref))
                    if ref is linked:
                        linked_score = score
            flights.append(flight)
        better = None
        if linked_score is not None and scored:
            best_score, best_ref = max(scored, key=lambda item: item[0])
            if best_score > linked_score:
                better = best_ref.id
        update_sidecar_extra(std, {"flights": flights, "better_coverage": better})
        return better

    def _local_newest(
        self, sheet: str, std: Path, error: DownloadError
    ) -> SheetFetch | None:
        """I-1: the local ``newest`` version when the GUGiK index is unavailable.

        ``None`` = no local version (no file, nonexistent
        ``extra.link_target``, an old regular file, no standard sidecar) —
        the caller reports the original error. The link is NOT moved; a
        link sidecar replaced by a symlink is rewritten as a regular file.
        The ``full_sheet/`` link is not touched either.
        """
        target = linked_version(std)
        if target is None:
            return None
        try:
            ensure_link(std, target, ("", "", ""))
        except (OSError, DownloadError):
            return None
        logger.warning(
            f"{sheet}: skorowidz GUGiK niedostepny ({error}) - uzyto lokalnej "
            f"wersji {target} bez sprawdzenia nowszej"
        )
        version = read_version(target.parent, target.name)
        if version is None:
            return None
        full = self._storage.get_full_sheet_path(sheet, self._default_ext)
        return SheetFetch(
            sheet,
            std,
            skipped=True,
            reused=(target,),
            status="local",
            version=version.label,
            unverified=str(error),
            files=(
                VersionedFile(
                    std,
                    "local",
                    version.label,
                    version.sha256,
                    target,
                    unverified=f"check_failed: {error}",
                ),
            ),
            full_link=full if linked_version(full) is not None else None,
        )

    def _download_single_sheet_task(
        self,
        sheet: str,
        update: UpdateMode | None,
        on_download: Callable[[], None] | None = None,
        check: YearRangeCheck | None = None,
    ) -> tuple[str, SheetFetch | None, str, str, tuple[str, ...]]:
        """
        Download a list sheet: ``DownloadError`` -> a status instead of an
        exception.

        Shared by sequential and parallel mode. Another exception (e.g. a
        write ``OSError``) propagates: sequentially it aborts the list, in a
        thread pool ``_download_many`` catches it as ``"failed"``.

        Returns
        -------
        tuple[str, SheetFetch | None, str, str, tuple[str, ...]]
            (sheet, fetch_or_none, status, message, hints)
            status is one of: "skipped", "completed", "failed", "no_coverage"
        """
        try:
            if check is not None and sheet in check.no_data:
                raise check.no_data[sheet]
            if check is not None and sheet in check.failed:
                fetch = self._local_unverified(sheet, check.failed[sheet])
            else:
                fetch = self._fetch_sheet(
                    sheet,
                    update,
                    on_download,
                    records=check.selected[sheet] if check is not None else None,
                    available=check.available[sheet] if check is not None else None,
                )
        except NoCoverageError as e:
            logger.warning(f"No data for {sheet}: {e}")
            return (sheet, None, "no_coverage", str(e), e.hints)
        except DownloadError as e:
            logger.error(f"Failed to download {sheet}: {e}")
            return (sheet, None, "failed", str(e), ())
        if fetch.skipped:
            return (sheet, fetch, "skipped", "Already exists", ())
        return (sheet, fetch, "completed", "", ())

    @staticmethod
    def _record(
        result: DownloadResult,
        sheet: str,
        fetch: SheetFetch | None,
        status: str,
        hints: tuple[str, ...] = (),
        message: str = "",
    ) -> None:
        """Accumulate the outcome of a leaf in one returned result."""
        if status in ("completed", "skipped") and fetch is not None:
            if status == "skipped":
                result.skipped.append(sheet)
            else:
                result.succeeded.append(fetch.path)
            if fetch.downloaded or fetch.reused:
                result.campaign_files[sheet] = fetch.downloaded + fetch.reused
                result.reused_campaign_files[sheet] = fetch.reused
            getattr(result, fetch.status).append(sheet)
            if fetch.unverified is not None:
                result.unverified[sheet] = fetch.unverified
            if fetch.better_coverage is not None:
                result.better_coverage[sheet] = fetch.better_coverage
            if fetch.link_outside_range is not None:
                result.link_outside_range[sheet] = fetch.link_outside_range
            if fetch.full_link is not None:
                result.full_links[sheet] = fetch.full_link
            if fetch.full_link_outside_range is not None:
                result.full_link_outside_range[sheet] = fetch.full_link_outside_range
            if fetch.no_full_flight:
                result.without_full.append(sheet)
            if fetch.newer is not None:
                result.newer[sheet] = fetch.newer
            if fetch.files:
                result.files[sheet] = fetch.files
        elif status in ("failed", "no_coverage"):
            result.failed.append(sheet)
            result.errors[sheet] = message
            if status == "no_coverage":
                result.no_coverage.append(sheet)
                if hints:
                    result.no_coverage_hints[sheet] = hints

    def _finish_result(
        self, result: DownloadResult, *, single: bool = False
    ) -> DownloadResult:
        """Emit data notices once and return them together with the outcomes."""
        sink = NoticeSink(self._on_notice)
        if result.unverified:
            sheets = list(result.unverified)
            if single:
                sheet = sheets[0]
                text = (
                    f"{sheet}: skorowidz GUGiK niedostepny - uzyto lokalnej "
                    "wersji bez sprawdzenia nowszej "
                    f"({result.unverified[sheet]})"
                )
            else:
                shown = ", ".join(sheets[:10]) + (" ..." if len(sheets) > 10 else "")
                text = (
                    f"skorowidz GUGiK niedostepny - dla {len(sheets)} arkuszy "
                    "uzyto lokalnych wersji bez sprawdzenia nowszej "
                    f"({shown}) ({result.unverified[sheets[0]]})"
                )
            sink.emit(
                "warning",
                UNVERIFIED_LOCAL,
                text.encode("ascii", "backslashreplace").decode("ascii"),
            )
        if result.newer:
            sheets = list(result.newer)
            shown = ", ".join(sheets[:10]) + (" ..." if len(sheets) > 10 else "")
            sink.emit(
                "info",
                NEWER_AVAILABLE,
                f"dostepna nowsza kampania dla {len(sheets)} arkuszy ({shown}) - "
                "uzyto lokalnych wersji; pobierz: --upgrade",
            )
        result.notices = sink.notices
        return result

    @staticmethod
    def _emit(
        on_progress: ProgressCallback | None,
        current: int,
        total: int,
        sheet: str,
        status: str,
        message: str = "",
    ) -> None:
        """The single place building ``DownloadProgress`` for both modes."""
        if on_progress:
            on_progress(
                DownloadProgress(
                    current=current,
                    total=total,
                    sheet=sheet,
                    status=status,
                    message=message,
                )
            )

    def _download_many(
        self,
        sheets: list[str],
        update: UpdateMode | None,
        on_progress: ProgressCallback | None,
        workers: int,
    ) -> DownloadResult:
        """Download a list of sheets (``workers <= 1`` sequential, otherwise a pool).

        Both modes call ``_download_single_sheet_task`` and report via
        ``_emit``/``_record``. Sequential additionally reports ``"downloading"``
        before each download and lets exceptions other than ``DownloadError``
        through; parallel counts them as ``"failed"``. Progress follows the
        completion order; the result (and its notices) the order of ``sheets``,
        so the same request always gives the same report.
        """
        check = (
            self._checked_range(sheets, workers, update) if self._has_range else None
        )
        result = DownloadResult()
        total = len(sheets)

        if workers <= 1:
            for i, sheet in enumerate(sheets, 1):

                def started(i: int = i, sheet: str = sheet) -> None:
                    self._emit(on_progress, i, total, sheet, "downloading")

                _, fetch, status, message, hints = self._download_single_sheet_task(
                    sheet, update, on_download=started, check=check
                )
                self._record(result, sheet, fetch, status, hints, message)
                self._emit(on_progress, i, total, sheet, status, message)
        else:
            counter = 0
            outcomes: dict[str, tuple] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_sheet = {
                    executor.submit(
                        self._download_single_sheet_task,
                        sheet,
                        update,
                        check=check,
                    ): sheet
                    for sheet in sheets
                }
                for future in concurrent.futures.as_completed(future_to_sheet):
                    sheet = future_to_sheet[future]
                    try:
                        sheet, fetch, status, message, hints = future.result()
                    except Exception as e:
                        logger.error(f"Unexpected error downloading {sheet}: {e}")
                        fetch, status, message, hints = None, "failed", str(e), ()
                    counter += 1
                    outcomes[sheet] = (fetch, status, hints, message)
                    self._emit(on_progress, counter, total, sheet, status, message)
            for sheet in sheets:
                self._record(result, sheet, *outcomes[sheet])

        logger.info(
            f"Hierarchy download complete: {len(result.succeeded)} downloaded, "
            f"{len(result.skipped)} skipped, {len(result.failed)} failed (of {total})"
        )
        return self._finish_result(result)

    # =========================================================================
    # Utility methods
    # =========================================================================

    def get_missing_sheets(
        self,
        sheet: str,
        target_scale: str,
    ) -> list[str]:
        """
        Get list of sheets that haven't been downloaded yet.

        Parameters
        ----------
        sheet : str
            Starting map sheet identifier
        target_scale : str
            Target scale to check

        Returns
        -------
        list[str]
            List of sheet code identifiers for missing sheets
        """
        parser = SheetParser(sheet)
        descendants = parser.get_all_descendants(target_scale)

        missing = []
        for descendant in descendants:
            if not self._storage.exists(descendant.sheet, self._default_ext):
                missing.append(descendant.sheet)

        return missing

    def count_sheets(self, sheet: str, target_scale: str) -> int:
        """
        Count total number of sheets in hierarchy.

        Parameters
        ----------
        sheet : str
            Starting map sheet identifier
        target_scale : str
            Target scale to count

        Returns
        -------
        int
            Number of sheets
        """
        parser = SheetParser(sheet)
        descendants = parser.get_all_descendants(target_scale)
        return len(descendants)

    def _write_sidecar(
        self,
        data_path: Path,
        request: dict,
        *,
        extra_override: dict | None = None,
        digest: ContentDigest | None = None,
        version: VersionRef | None = None,
    ) -> None:
        """Write the .meta.json sidecar; best-effort without ``version``.

        For a request with ``sheet`` it adds ``extra.source`` — the file origin
        per ``provider.source_info`` (GUGiK index record: URL, layer,
        acquisition date; D5). Only a ``dict`` goes into the sidecar: a
        provider without origin returns ``None``, and ``Mock(spec=...)`` — a
        ``Mock``. ``extra_override`` (campaign sidecar) replaces
        ``source_info``: its fields are merged into ``extra`` after
        ``sidecar_extra``. With ``version`` it is the mandatory VERSION
        sidecar (spec 3.3): ``extra.version``, ``extra.coverage`` when
        measured, sha256 from ``digest`` (D20), written exclusively —
        ``FileExistsError`` propagates (another writer was first), any other
        failure is a ``DownloadError``.
        """
        from kartograf.sources.sidecar import emit_sidecar

        extra = dict(self._sidecar_extra) if self._sidecar_extra else {}
        if extra_override is not None:
            extra.update(extra_override)
        else:
            sheet = request.get("sheet")
            source_info = getattr(self._provider, "source_info", None)
            if sheet is not None and callable(source_info):
                source = source_info(sheet)
                if isinstance(source, dict):
                    extra["source"] = source
        if version is not None and digest is not None and digest.coverage is not None:
            extra["coverage"] = digest.coverage
        emit_sidecar(
            getattr(self._provider, "descriptor_key", None),
            data_path,
            request=request,
            vertical_crs=getattr(self._provider, "vertical_crs", None),
            extra=extra or None,
            digest=(digest.sha256, digest.size_bytes) if digest is not None else None,
            version=version.to_extra() if version is not None else None,
            exclusive=version is not None,
        )

    def _write_campaign_sidecar(
        self,
        path: Path,
        sheet: str,
        record: SkorowidzRecord,
        ref: CampaignRef,
        *,
        available: tuple[int, ...] | None = None,
        digest: ContentDigest,
        version: VersionRef,
    ) -> None:
        """MANDATORY version sidecar of a campaign file (errata 2 N-1, spec 3.3).

        ``request`` describes the resolved strategy, supplied year bounds and
        ``full_sheet: true`` when that flag is set (ADR-033);
        ``extra`` includes the source and campaign identity of THIS record
        (R13), plus all available years for range-checked requests. Failure
        is a campaign ``DownloadError`` (the commit removes the data file);
        ``FileExistsError`` = another writer published it (``commit_version``).
        """
        request: dict = {
            "sheet": sheet,
            "campaigns": "all" if self._all_campaigns else "newest",
        }
        if self._full_sheet:  # describes the request, not this flight
            request["full_sheet"] = True
        if self._min_year is not None:
            request["min_year"] = self._min_year
        if self._max_year is not None:
            request["max_year"] = self._max_year
        if self._min_year is not None and self._min_year == self._max_year:
            request["year"] = self._min_year
        try:
            source = self._campaign_provider.record_source(record)
        except Exception as e:  # noqa: BLE001 — mandatory sidecar: campaign failure
            raise DownloadError(
                f"Nie udalo sie zapisac obowiazkowego sidecara kampanii "
                f"{ref.dirname}: {e}",
                sheet=sheet,
            ) from e
        extra: dict = {"source": source, "campaign": ref.to_extra()}
        if available is not None:
            extra["available_years"] = list(available)
        self._write_sidecar(
            path, request, extra_override=extra, digest=digest, version=version
        )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"DownloadManager(provider={self._provider.name}, "
            f"output_dir='{self._storage.output_dir}', "
            f"resolution='{self._resolution}', "
            f"workers={self._workers})"
        )
