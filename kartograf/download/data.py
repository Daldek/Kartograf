"""``download_data`` / ``check_data``: the ``elevation download`` and
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
SHEET_LIST             info     PL area expanded to a sheet list (header;
                                the CLI prints it on stdout, ``-q`` hides it)
GEOMETRY_LAYER_DEFAULT info     GPKG with several layers, no ``layer``
AUTO_NARROWED_TO_PL    info     ``auto`` + PL-only choice (ADR-023 pkt 5)
AUTO_CLIPPED           info     ``auto``: country part clipped to its envelope
AUTO_AREA_OUTSIDE      info     ``auto``: part of the area outside PL/CZ
AUTO_PARTIAL_SUCCESS   warning  ``auto``: one country failed, another succeeded
LEGACY_CAMPAIGNS_DIR   info     0.7.x ``kampanie/`` directory present
NEWER_AVAILABLE        info     (DownloadManager) newer campaign, local used
UNVERIFIED_LOCAL       warning  (DownloadManager) index down, local used
NO_COVERAGE_SOME       warning  some sheets without GUGiK data, >= 1 file
NO_COVERAGE_HINT       info     provider hints for sheets without data
BETTER_COVERAGE        info     older flight with better coverage
LINK_OUTSIDE_RANGE     info     link kept on a flight outside the request
SHEET_CRS_MISMATCH     warning  sheet file CRS differs from the sheet code
INCOMPLETE_CAMPAIGN    warning  newest campaign declares an incomplete sheet
CHECK_FAILED           warning  local version used, source check failed
UNVERIFIED_LOCAL       info     ``upgrade``: local version without a signal
CUTOUT_SIZE            info     (download_pl_cutout) large cutout
ALL_NODATA             warning  (cutouts, CZ sheet) raster without data
LAZ_SUPERSEDED         info     (download_laz_area) skipped LAZ tiles
CACHE_DISABLED         warning  (open_cache) metadata cache unusable
=====================  =======  ==============================================

Every former ``Error:`` is a ``ValidationError`` (input, raised before any
download), a ``TransformError`` (no safe pinned operation) or a
``UnitFailure`` of the report (a failed country, sheet set or tile set;
``ok=False`` unless ``auto`` partial success applies).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import BBox, SheetParser, find_sheets_for_bbox
from kartograf.download.area import (
    cz_geometry_bbox,
    emit_clipping_notices,
    geometry_envelope,
    parent_request_for,
    pl_only_flags,
    resolve_geometry_layer,
)
from kartograf.download.countries import countries_for_bbox, country_bbox
from kartograf.download.fetch import UpdateMode, VersionedFile
from kartograf.download.manager import DownloadManager, DownloadProgress, DownloadResult
from kartograf.download.options import (
    CZ_ONLY_NMT,
    campaign_opts_given,
    country_value,
    cz_option_error,
    is_source_file_request,
    pl_option_error,
    pl_target_scale,
    reject_campaign_opts_with_cutout,
    require_cz_cutout,
    resolve_pl_options,
    validate_request,
)
from kartograf.download.plan import PlanItem, UpdatePlan
from kartograf.exceptions import (
    DownloadError,
    KartografError,
    ValidationError,
)
from kartograf.notices import (
    AUTO_NARROWED_TO_PL,
    AUTO_PARTIAL_SUCCESS,
    BETTER_COVERAGE,
    CHECK_FAILED,
    INCOMPLETE_CAMPAIGN,
    LEGACY_CAMPAIGNS_DIR,
    LINK_OUTSIDE_RANGE,
    NO_COVERAGE_HINT,
    NO_COVERAGE_SOME,
    SHEET_CRS_MISMATCH,
    SHEET_LIST,
    UNVERIFIED_LOCAL,
    Notice,
    NoticeSink,
)
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import SupersededLazTile
from kartograf.sources.registry import horizontal_crs_for_sheet

FailureKind = Literal["no_coverage", "download", "country"]
MAX_HINT_LINES = 5


@dataclass(frozen=True)
class UnitFile:
    """One file of the request: ``unit`` = sheet code, LAZ file name or the
    cutout path relative to ``output_dir``; ``country`` = ``"PL"``/``"CZ"``."""

    unit: str
    country: str
    file: VersionedFile


@dataclass(frozen=True)
class UnitFailure:
    """A failed part of the request (country, sheet set or tile set).

    ``kind``: ``no_coverage`` (no data at the source), ``download`` (network,
    server) or ``country`` (the country part of the request failed).
    """

    unit: str
    country: str
    error: str
    kind: FailureKind


@dataclass(frozen=True)
class DataReport:
    """Outcome of ``download_data`` (spec 4.1).

    ``ok`` is the exit rule of the CLI (former ``_finish_pl_sheets`` and
    ``country="auto"`` partial success): ``False`` after any failure or stale
    plan position, except ``auto`` with at least one country succeeding.
    """

    files: tuple[UnitFile, ...]
    failed: tuple[UnitFailure, ...]
    stale: tuple[PlanItem, ...]
    superseded: tuple[SupersededLazTile, ...]
    notices: tuple[Notice, ...]
    ok: bool


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
    stale: list[PlanItem] = field(default_factory=list)
    superseded: list[SupersededLazTile] = field(default_factory=list)
    plans: list[UpdatePlan] = field(default_factory=list)
    dry: bool = False

    def add(
        self,
        unit: str,
        country: str,
        file: VersionedFile | None,
        *,
        reported_check_failure: bool = False,
    ) -> None:
        """Record a file and signal notices not already emitted by its manager."""
        if file is None:
            return
        self.files.append(UnitFile(unit, country, file))
        unverified = file.unverified or ""
        if unverified.startswith("check_failed") and not reported_check_failure:
            error = unverified.split(":", 1)[1].strip()
            self.sink.emit(
                "warning",
                CHECK_FAILED,
                f"{unit}: nie udalo sie sprawdzic zrodla ({error}) - uzyto "
                f"lokalnej wersji {file.label}",
            )
        if file.status == "local" and unverified == "none" and self.update == "upgrade":
            self.sink.emit(
                "info",
                UNVERIFIED_LOCAL,
                f"{unit}: lokalna wersja {file.label} niesprawdzona - zrodlo "
                "bez taniego sygnalu; pobierz ponownie: --force",
            )

    def add_stale(self, stale) -> int:
        self.stale.extend(stale)
        return 1 if stale else 0

    def fail(self, unit: str, country: str, error: str, kind: FailureKind) -> int:
        self.failed.append(UnitFailure(unit, country, error, kind))
        return 1


def _error_text(error: Exception) -> str:
    """Error text with the remedy of a ``TransformError`` (if any)."""
    remedy = getattr(error, "remedy", None)
    return f"{error}" + (f" Remedium: {remedy}" if remedy else "")


def _task(**kwargs) -> SimpleNamespace:
    task = SimpleNamespace(**kwargs)
    task.output_dir = Path(task.output_dir) if task.output_dir is not None else None
    task.geometry = Path(task.geometry) if task.geometry is not None else None
    return task


def _start(
    kwargs: dict,
    *,
    update: UpdateMode | None,
    plan: UpdatePlan | None,
    check: bool,
    workers: int,
    cache: MetadataCache | bool,
    on_progress: Callable[[DownloadProgress], None] | None,
    on_notice: Callable[[Notice], None] | None,
) -> tuple[_Run, int]:
    from kartograf.download.fetch import validate_update

    validate_update(update)
    if plan is not None and update != "upgrade":
        raise ValidationError("Plan aktualizacji wymaga update='upgrade'")
    run = _Run(
        sink=NoticeSink(on_notice),
        update=update,
        check=check,
        loaded=plan,
        cache=cache,
        workers=workers,
        on_progress=on_progress,
    )
    return run, _execute(_task(**kwargs), run)


def download_data(
    *,
    product: str | None,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    country: str | None = None,
    vertical_crs: str | Mapping[str, str] | None = None,
    resolution: str | Mapping[str, str] | None = None,
    format: str | None = None,
    sheet_system: str | None = None,
    scale: str | None = None,
    cutout: bool = False,
    horizontal_crs: str | None = None,
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
    """Download NMT/NMPT/orto/LAZ for a sheet, bbox or geometry (spec 4.1).

    Parameter names and values are the ``elevation download`` / ``imagery download``
    flags in ``snake_case``. Every data choice is explicit (no defaults): ``product``,
    ``output_dir``, ``vertical_crs``/``resolution`` (plain or per country,
    ``{"pl": "1m", "cz": "2m"}``; PL values from the variant registry,
    ``kartograf.sources.variants``), ``country`` (``pl``/``cz``/``auto``,
    required with ``bbox``/``geometry``), ``sheet_system``/``scale`` for PL
    sheets of an area. ``format`` (PL NMT/NMPT): ``None`` = ASC grids, an
    archive token (``"XYZ"``, ``"TBD"``, ...) = the original files of the
    index, whose sheets (any scale) come from the index (ADR-041).
    ``cutout=True`` with ``horizontal_crs`` gives ONE
    cutout of the area instead of sheets (PL: GUGiK WCS, CZ: CUZK; an area
    reaching CZ requires it).
    ``bbox`` may be in any supported CRS; ``geometry`` is a SHP/GPKG file.
    ``update``/``plan``: modes of every track (``plan`` from ``check_data``
    with ``update="upgrade"``). ``cache``: ``True`` = default metadata cache
    in the current directory, a ``MetadataCache`` = that cache, ``False`` =
    none. ``on_notice`` receives each data notice when it is emitted (e.g.
    country clipping before the first download); ``on_progress`` receives
    the sheet and tile progress.

    Raises
    ------
    ValidationError
        Invalid or missing choice (before any download; texts name the CLI
        flags, the CLI prints them as ``Error:``).
    ParseError
        Malformed sheet code.
    TransformError
        No safe pinned operation for the request area.
    """
    run, rc = _start(
        _selection_kwargs(locals()),
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
    )


def check_data(
    *,
    product: str | None,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    country: str | None = None,
    vertical_crs: str | Mapping[str, str] | None = None,
    resolution: str | Mapping[str, str] | None = None,
    format: str | None = None,
    sheet_system: str | None = None,
    scale: str | None = None,
    cutout: bool = False,
    horizontal_crs: str | None = None,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    all_campaigns: bool = False,
    full_sheet: bool = False,
    min_density: int | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
) -> UpdatePlan:
    """Update plan of ``download_data`` with the same arguments; no download.

    ``country="auto"`` gives ONE merged plan of every country. A country
    that cannot be checked is a ``CHECK_FAILED`` notice when another one
    was checked, else its error is raised (``DownloadError``).
    """
    run, _ = _start(
        _selection_kwargs(locals()),
        update=None,
        plan=None,
        check=True,
        workers=1,
        cache=cache,
        on_progress=None,
        on_notice=on_notice,
    )
    if not run.plans:
        error = run.failed[0].error if run.failed else "brak pozycji planu"
        raise DownloadError(error)
    for failure in run.failed:
        run.sink.emit("warning", CHECK_FAILED, f"{failure.unit}: {failure.error}")
    merged = run.plans[0]
    for other in run.plans[1:]:
        merged = merged.merge(other)
    return merged


def validate_data_request(
    *,
    product: str | None,
    output_dir: str | Path | None,
    sheet: str | None = None,
    bbox: BBox | None = None,
    geometry: str | Path | None = None,
    layer: str | None = None,
    country: str | None = None,
    vertical_crs: str | Mapping[str, str] | None = None,
    resolution: str | Mapping[str, str] | None = None,
    format: str | None = None,
    sheet_system: str | None = None,
    scale: str | None = None,
    cutout: bool = False,
    horizontal_crs: str | None = None,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    all_campaigns: bool = False,
    full_sheet: bool = False,
    min_density: int | None = None,
) -> None:
    """Every check ``download_data``/``check_data`` make before their first
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
    task = _task(**_selection_kwargs(locals()))
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
    "output_dir",
    "sheet",
    "bbox",
    "geometry",
    "layer",
    "country",
    "vertical_crs",
    "resolution",
    "format",
    "sheet_system",
    "scale",
    "cutout",
    "horizontal_crs",
    "year",
    "min_year",
    "max_year",
    "all_campaigns",
    "full_sheet",
    "min_density",
)


def _selection_kwargs(values: dict) -> dict:
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
                f"Godlo '{task.sheet}' nalezy do systemu {system.id} "
                f"(kraj {system.country}), a podano --country {country}"
            )
        if system.country == "CZ":
            if task.product != "nmt":
                raise ValidationError(CZ_ONLY_NMT.format(product=task.product))
            _reject_campaign_opts_without_pl(task, ("CZ",))
            return _download_cz(task, run)
        parsed = SheetParser(task.sheet)
        resolve_pl_options(
            task, code_system=parsed.sheet_system, code_scale=parsed.scale
        )
    if task.product == "laz":
        return _download_laz(task, run)
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
    """PL-only campaign/year choices are rejected for a CZ-only request (a
    PL+CZ area is a cutout, which rejects them itself, ADR-038)."""
    if campaign_opts_given(task) and "PL" not in countries:
        raise ValidationError(
            "CZ (CUZK) nie ma kampanii - "
            "--all-campaigns/--min-year/--max-year/--year/--full-sheet dotycza "
            "tylko PL"
        )


def _dispatch_area(
    task: SimpleNamespace, run: _Run, bbox: BBox, filepath: Path | None = None
) -> int:
    """Split an area request (bbox or geometry envelope) into countries and run them.

    With ``filepath`` the PL part works on the file (sheets per feature, not
    the envelope); the bbox recognizes countries and gives ``parent_request``.
    """
    auto = task.country == "auto"
    countries = (
        countries_for_bbox(bbox) if auto else ({"pl": "PL", "cz": "CZ"}[task.country],)
    )
    if not countries:
        raise ValidationError(
            "obszar nie przecina zasiegu zadnego znanego kraju (PL, CZ)"
        )
    # ADR-023 point 5: a choice without a CZ counterpart decides the country
    if auto and len(countries) > 1 and "PL" in countries:
        pl_only = pl_only_flags(
            task.product, task.vertical_crs, task.resolution, task.format
        )
        if pl_only:
            run.sink.emit(
                "info",
                AUTO_NARROWED_TO_PL,
                f"--country auto -> pl ({', '.join(pl_only)} dotyczy tylko PL)",
            )
            auto = False
            countries = ("PL",)
    if countries == ("CZ",) and task.product != "nmt":
        raise ValidationError(CZ_ONLY_NMT.format(product=task.product))
    _reject_campaign_opts_without_pl(task, countries)
    require_cz_cutout(task, countries)
    _validate_cross_country(task, countries)
    if "PL" in countries:
        reject_campaign_opts_with_cutout(task)

    parent_request = parent_request_for(bbox, countries)
    cz_crs = task.horizontal_crs or "EPSG:5514"
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
            pl_geometry_sheets=filepath is not None and not task.cutout,
            pl_sheet_list=filepath is None and not task.cutout,
        )

    results: list[tuple[str, int]] = []
    for code in countries:
        part = parts[code].bbox
        # a COPY per country: each branch narrows the per-country values
        country_task = SimpleNamespace(**vars(task))
        try:
            if code == "CZ":
                rc = _download_cz(
                    country_task, run, bbox=part, parent_request=parent_request
                )
            elif filepath is not None:
                rc = _download_pl_geometry(
                    country_task, run, filepath, parent_request, part
                )
            else:
                rc = _download_pl_bbox(country_task, run, part, parent_request)
        except DownloadError as e:
            rc = run.fail(code, code, _error_text(e), "country")
        results.append((code, rc))

    exit_codes = [rc for _, rc in results]
    # A3-2: `auto` takes countries from RECTANGULAR envelopes, so a request deep
    # inside one country routinely hits the other one too - code 0 with a warning.
    if auto and len(results) > 1 and 0 in exit_codes and max(exit_codes) != 0:
        failed = [code for code, rc in results if rc != 0]
        ok = [code for code, rc in results if rc == 0]
        if run.check:
            text = (
                f"czesc {', '.join(failed)} zadania nie mogla zostac sprawdzona "
                f"- sprawdzono {', '.join(ok)}; kod 0 "
                "(prostokatne obwiednie krajow, ADR-023 pkt 4-5)"
            )
        else:
            text = (
                f"czesc {', '.join(failed)} zadania zakonczyla sie bledem "
                f"(patrz Error) - pobrano {', '.join(ok)}; kod 0 "
                "(prostokatne obwiednie krajow, ADR-023 pkt 4-5)"
            )
        run.sink.emit("warning", AUTO_PARTIAL_SUCCESS, text)
        return 0
    return max(exit_codes)


def _validate_cross_country(task: SimpleNamespace, countries: tuple[str, ...]) -> None:
    """Choices must be valid for EVERY country before any download."""
    hint = "; uzyj jawnie --country pl albo --country cz" if len(countries) > 1 else ""
    if "CZ" in countries and task.product != "nmt":
        raise ValidationError(
            f"--product {task.product} jest dostepny tylko dla PL{hint}"
        )
    for code in countries:
        if code == "PL":
            error = pl_option_error(task, countries=countries)
        else:
            error = cz_option_error(task, countries=countries)
        if error is not None:
            raise ValidationError(error)


def _download_geometry(task: SimpleNamespace, run: _Run) -> int:
    """Geometry request: explicit CZ (envelope in the CZ CRS) or country dispatch."""
    assert task.geometry is not None
    if task.country == "cz":
        if task.product != "nmt":
            raise ValidationError(CZ_ONLY_NMT.format(product=task.product))
        _reject_campaign_opts_without_pl(task, ("CZ",))
        require_cz_cutout(task, ("CZ",))
        task.layer = resolve_geometry_layer(task.geometry, task.layer, run.sink)
        bbox = cz_geometry_bbox(task.geometry, task.layer, task.horizontal_crs)
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
    """Request label in messages: orto has no resolution (K5), archives name
    their format."""
    if product == "orto":
        return "product: orto"
    if fmt is not None and fmt != "ASC":
        return f"format: {fmt}, resolution: {resolution or '-'}"
    return f"resolution: {resolution}"


def _create_provider_and_storage(
    product, output_dir, vertical_crs, resolution, cache=None, fmt=None
):
    """Provider and storage of a PL sheet product (``cache``: ``MetadataCache``
    or ``None``; GUGiK index records go through it, N6). ``fmt``: ``None``
    = ASC grids, else an archive format of the variant registry."""
    from kartograf.download.storage import storage_for_provider

    if product == "nmpt":
        from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider

        provider = GugikNmptProvider(
            vertical_crs=vertical_crs,
            resolution=resolution,
            format=fmt or "ASC",
            cache=cache,
        )
    elif product == "orto":
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        # `download_data` offers the RGB composition only (`product="orto"`)
        provider = GugikOrtoProvider(cache=cache, color="RGB")
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
        output_dir, provider, resolution=resolution, vertical_crs=vertical_crs
    )
    return provider, storage


def _manager(
    task: SimpleNamespace,
    run: _Run,
    metadata: MetadataCache | None,
    parent_request: dict | None = None,
) -> DownloadManager:
    provider, storage = _create_provider_and_storage(
        task.product,
        task.output_dir,
        task.vertical_crs,
        task.resolution,
        cache=metadata,
        fmt=task.format,
    )
    manager = DownloadManager(
        output_dir=task.output_dir,
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
    if manager.storage.has_legacy_campaigns() is True:
        run.sink.emit(
            "info",
            LEGACY_CAMPAIGNS_DIR,
            "katalog kampanie/ z wersji 0.7.x nie jest uzywany; dane "
            "zostana pobrane ponownie do versions/",
        )
    return manager


def _plan_modes(run: _Run, manager: DownloadManager, sheets: list[str]) -> int | None:
    """Check or planned upgrade of PL sheets; ``None`` = a plain download."""
    if run.check:
        run.plans.append(manager.check_sheets(sheets))
        return 0
    if run.update != "upgrade" or run.loaded is None:
        return None
    report = manager.download_sheets(sheets, update="upgrade", plan=run.loaded)
    reported = any(n.code == UNVERIFIED_LOCAL for n in report.notices)
    for sheet, files in report.files.items():
        for file in files:
            run.add(
                sheet,
                "PL",
                file,
                reported_check_failure=reported or sheet in report.unverified,
            )
    rc = run.add_stale(report.stale)
    for sheet, message in report.errors.items():
        run.fail(sheet, "PL", f"{sheet}: {message}", "download")
    return 1 if rc or report.failed else 0


def _announcer(run: _Run, unit: str, details: str) -> Callable[[], None]:
    """``on_download`` hook: a ``start`` progress event when a transfer starts."""

    def announce() -> None:
        if run.on_progress is not None:
            run.on_progress(DownloadProgress(0, 1, unit, "start", details))

    return announce


def _download_pl_sheet(task: SimpleNamespace, run: _Run) -> int:
    """PL sheet code (validated): one sheet, a coarser code or a ``scale`` list."""
    if run.dry:
        return 0
    label = _product_label(task.product, task.resolution)
    with open_cache(
        run.cache, force=run.update == "force", on_notice=run.sink.add
    ) as metadata:
        manager = _manager(task, run, metadata)
        sheets = (
            [d.sheet for d in SheetParser(task.sheet).get_all_descendants(task.scale)]
            if task.scale
            else [task.sheet]
        )
        planned = _plan_modes(run, manager, sheets)
        if planned is not None:
            return planned
        try:
            if task.scale:
                if run.on_progress is not None:
                    count = manager.count_sheets(task.sheet, task.scale)
                    run.on_progress(
                        DownloadProgress(
                            0, count, f"{task.sheet} to {task.scale}", "start", label
                        )
                    )
                result = manager.download_hierarchy(
                    task.sheet,
                    task.scale,
                    update=run.update,
                    on_progress=run.on_progress,
                )
                return _finish_pl_sheets(task, run, result)
            parsed = SheetParser(task.sheet)
            expanded = parsed.sheet_system != "2000" and parsed.scale != "1:10000"
            announce = _announcer(run, task.sheet, label)
            if expanded:
                announce()
            result = manager.download_sheet(
                task.sheet,
                update=run.update,
                on_progress=run.on_progress,
                on_download=announce,
            )
        except DownloadError as e:
            return run.fail(task.sheet, "PL", str(e), "download")
    if expanded:
        return _finish_pl_sheets(task, run, result)
    reported = any(n.code == UNVERIFIED_LOCAL for n in result.notices)
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
    """Standard paths of successful sheets, including already-local sheets."""
    if result.files:
        return [files[0].path for files in result.files.values() if files]
    return list(result.succeeded)


def _download_pl_bbox(
    task: SimpleNamespace, run: _Run, bbox: BBox, parent_request: dict
) -> int:
    """PL part of a bbox request: a cutout (``cutout``) or a sheet list."""
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
    parent_request: dict,
    bbox: BBox,
) -> int:
    """PL part of a geometry request: sheets per feature, or a cutout of the
    (clipped) envelope with ``cutout``."""
    from kartograf.core.geometry import find_sheets_for_geometry

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
    parent_request: dict,
    *,
    what: str,
    target_scale: str,
) -> int:
    """PL sheet list (area without ``cutout``): manager + finish (D15)."""
    if run.dry:
        return 0
    _emit_sheet_list(run, task, sheets, f"w skali {target_scale}", what)
    with open_cache(
        run.cache, force=run.update == "force", on_notice=run.sink.add
    ) as metadata:
        try:
            manager = _manager(task, run, metadata, parent_request)
            planned = _plan_modes(run, manager, sheets)
            if planned is not None:
                return planned
            result = manager.download_sheets(
                sheets, update=run.update, on_progress=run.on_progress
            )
        except DownloadError as e:
            return run.fail("PL", "PL", str(e), "download")
    return _finish_pl_sheets(task, run, result)


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
    areas: list,
    parent_request: dict | None,
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
    with open_cache(
        run.cache, force=run.update == "force", on_notice=run.sink.add
    ) as metadata:
        try:
            manager = _manager(task, run, metadata, parent_request)
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
            return run.fail("PL", "PL", str(e), "download")
    return _finish_pl_sheets(task, run, result)


def _finish_pl_sheets(task: SimpleNamespace, run: _Run, result: DownloadResult) -> int:
    """Files, notices and exit code of a multi-sheet PL request (D2/D10, R5).

    All downloaded/local -> 0; >= 1 file and the rest without GUGiK data ->
    ``NO_COVERAGE_SOME``, 0; >= 1 download failure -> failure, 1; no file at
    all -> ``no_coverage`` failure, 1.
    """
    paths = _result_paths(result)
    _sheet_sidecar_notices(task, run, result, paths)
    reported = any(n.code == UNVERIFIED_LOCAL for n in result.notices)
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
        shown = ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else "")
        run.sink.emit(
            "warning",
            NO_COVERAGE_SOME,
            f"GUGiK nie ma danych dla {len(missing)} z {total} arkuszy "
            f"({shown}) - pominiete (skorowidz GUGiK nie ma tych arkuszy dla "
            "wybranego produktu i rozdzielczosci, np. morze, obszar za granica, "
            f"brak NMT 5 m w czesci kraju); pobrano {len(paths)}",
        )
        _coverage_hints(run, result)
    if hard:
        causes = "; ".join(
            f"{sheet}: {result.errors[sheet].removeprefix(sheet + ': ')}"
            for sheet in hard
        )
        return run.fail(
            "PL",
            "PL",
            f"{len(hard)} z {total} arkuszy nie pobrano (blad pobrania, "
            f"nie brak danych): {causes} - ponow pobranie",
            "download",
        )
    if not paths:
        _coverage_hints(run, result)
        return run.fail(
            "PL",
            "PL",
            f"GUGiK nie ma danych dla zadnego z {total} arkuszy obszaru",
            "no_coverage",
        )
    return 0


def _coverage_hints(run: _Run, result: DownloadResult) -> None:
    """``NO_COVERAGE_HINT``: provider hints without duplicates, at most
    ``MAX_HINT_LINES`` (full list: ``DownloadResult.no_coverage_hints``)."""
    hints = list(
        dict.fromkeys(h for hs in result.no_coverage_hints.values() for h in hs)
    )
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


def _read_sheet_sidecar(path: Path) -> dict | None:
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
        f"{len(found)} arkuszy GUGiK opublikowano w innym ukladzie "
        f"niz wskazuje godlo: {shown} - sidecar opisuje uklad pliku "
        "(horizontal_crs); deklaracja rekordu w extra.source.declared_crs",
    )


def _flight_description(flight: dict) -> str:
    """A flight's sidecar date, ID, completeness and measured coverage."""
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
        f"dla {len(better)} arkuszy starszy lot z przedzialu ma wieksze "
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


def _unit_of(path: Path, output_dir: Path) -> str:
    """Unit of a cutout: its path below ``output_dir``."""
    try:
        return Path(path).relative_to(output_dir).as_posix()
    except ValueError:
        return str(path)


def _download_pl_cutout(
    task: SimpleNamespace, run: _Run, bbox: BBox, parent_request: dict
) -> int:
    """PL cutout (``cutout``) from GUGiK WCS (ADR-035).

    A source failure is recorded for the PL part; invalid input and unexpected
    errors propagate to the caller.
    """
    from kartograf.download.cutout import check_pl_cutout, download_pl_cutout

    if run.dry:
        return 0
    selection = {
        "horizontal_crs": task.horizontal_crs,
        "output_dir": task.output_dir,
        "vertical_crs": task.vertical_crs,
        "product": task.product,
        "cache": run.cache,
        "on_notice": run.sink.add,
    }
    try:
        if run.check:
            run.plans.append(check_pl_cutout(bbox, **selection))
            return 0
        result = download_pl_cutout(
            bbox,
            update=run.update,
            plan=run.loaded,
            parent_request=parent_request,
            **selection,
        )
    except DownloadError as e:
        return run.fail("PL", "PL", _error_text(e), "download")
    if result.file is not None:
        run.add(_unit_of(result.file.path, task.output_dir), "PL", result.file)
    return run.add_stale(result.stale)


def _download_cz(
    task: SimpleNamespace,
    run: _Run,
    *,
    bbox: BBox | None = None,
    parent_request: dict | None = None,
) -> int:
    """CZ request: a sheet code (TM33 tile / SM5 sheet) or an area cutout."""
    from kartograf.core.parser_registry import detect_system
    from kartograf.download.cz_cutout import check_cz_cutout, download_cz_cutout
    from kartograf.download.cz_sheets import check_cz_sheet, download_cz_sheet

    has_sheet = bbox is None
    is_sm5 = has_sheet and detect_system(task.sheet).id == "cz_sm5"
    # an `auto` area request was validated for all its countries already
    countries = ("CZ",) if has_sheet or task.country == "cz" else ("CZ", "PL")
    error = cz_option_error(task, is_sm5=is_sm5, countries=countries)
    if error is not None:
        raise ValidationError(error)
    resolution = country_value(task.resolution, "CZ") or "5m"  # only SM5 omits it
    vertical_crs = country_value(task.vertical_crs, "CZ")
    assert vertical_crs is not None  # required: checked by cz_option_error
    if run.dry:
        return 0
    common = {
        "output_dir": task.output_dir,
        "vertical_crs": vertical_crs,
        "resolution": resolution,
        "cache": run.cache,
        "on_notice": run.sink.add,
    }
    try:
        if has_sheet:
            if run.check:
                run.plans.append(check_cz_sheet(task.sheet, **common))
                return 0
            sheet = download_cz_sheet(
                task.sheet,
                update=run.update,
                plan=run.loaded,
                on_download=_announcer(
                    run, task.sheet, f"CZ, resolution: {resolution}"
                ),
                **common,
            )
            run.add(task.sheet, "CZ", sheet.file)
            return run.add_stale(sheet.stale)
        assert bbox is not None
        target = task.horizontal_crs
        if run.check:
            run.plans.append(check_cz_cutout(bbox, horizontal_crs=target, **common))
            return 0
        cutout = download_cz_cutout(
            bbox,
            horizontal_crs=target,
            update=run.update,
            plan=run.loaded,
            parent_request=parent_request,
            on_download=_announcer(run, "CZ bbox", f"{resolution}, {target}"),
            **common,
        )
    except DownloadError as e:
        return run.fail(task.sheet or "CZ", "CZ", str(e), "download")
    if cutout.file is not None:
        run.add(_unit_of(cutout.file.path, task.output_dir), "CZ", cutout.file)
    return run.add_stale(cutout.stale)


def _download_laz(task: SimpleNamespace, run: _Run) -> int:
    """LAZ tiles of a sheet code, bbox or geometry (PL only, ADR-029)."""
    from kartograf.core.geometry import get_overall_bbox
    from kartograf.download.area import bbox_to_2180
    from kartograf.download.laz import check_laz_area, download_laz_area

    if task.country == "cz":
        raise ValidationError(CZ_ONLY_NMT.format(product="laz"))
    resolve_pl_options(task)
    if task.geometry is not None:
        task.layer = resolve_geometry_layer(task.geometry, task.layer, run.sink)
        bbox = get_overall_bbox(task.geometry, layer=task.layer, target_crs="EPSG:2180")
    elif task.bbox is not None:
        bbox = task.bbox
    else:
        bbox = SheetParser(task.sheet).get_bbox(crs="EPSG:2180")
    # an area reaching into CZ would be downloaded only partially (spec 5.7)
    if (
        task.country == "auto"
        and task.sheet is None
        and "CZ" in countries_for_bbox(bbox_to_2180(bbox))
    ):
        raise ValidationError(
            "--product laz jest dostepny tylko dla PL, a obszar "
            "przecina CZ (LAZ dla CZ: etap 2); uzyj jawnie --country pl"
        )
    if run.dry:
        return 0
    selection = {
        "output_dir": task.output_dir,
        "vertical_crs": task.vertical_crs,
        "min_density": task.min_density,
        "all_campaigns": task.all_campaigns,
        "min_year": task.min_year,
        "max_year": task.max_year,
        "cache": run.cache,
        "on_notice": run.sink.add,
    }
    if run.check:
        run.plans.append(check_laz_area(bbox, **selection))
        return 0
    if run.on_progress is not None:
        _announcer(run, "kafle LAZ", f"WFS GUGiK, {task.vertical_crs}")()
    on_progress = run.on_progress

    def tiles(done: int, total: int) -> None:
        if on_progress is not None:
            on_progress(DownloadProgress(done, total, "", "tiles"))

    result = download_laz_area(
        bbox,
        workers=run.workers,
        update=run.update,
        plan=run.loaded,
        on_progress=tiles,
        parent_request=(
            None if task.sheet is not None else parent_request_for(bbox, ("PL",))
        ),
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
            f"{len(result.failed)} z {len(result.tiles)} kafli LAZ nie pobrano "
            f"(blad pobrania): {names} - ponow pobranie{details}",
            "download",
        )
    return rc
