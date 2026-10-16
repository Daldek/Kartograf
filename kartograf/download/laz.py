"""
Downloading LAZ tiles for an area — library layer (review-1 D17).

Pattern: ``download/cutout.py`` — the CLI (``kartograf elevation download --product
laz``) is a thin layer over this module: it prints messages and translates
the result into an exit code. There is no ``print`` or argparse here.

Flow: bbox in any supported CRS -> EPSG:2180 (Czech CRSs only via the pinned
operation) or a sheet code -> its frame in EPSG:2180 and the envelope of
the frame -> ``GugikLazProvider.select_tiles`` (WFS for the envelope, tile
selection for the area from the newest vintage without duplicating it) ->
``_run_laz_download`` (parallel downloads into ``versions/``, mandatory
version sidecars and standard hardlinks; tile failures collected). Public
pair (Z2): ``download_laz_area`` / ``check_laz_area`` with the same
selection arguments.

Example::

    from kartograf import BBox, download_laz_area

    result = download_laz_area(
        BBox(637400, 487000, 637450, 487050, "EPSG:2180"),
        output_dir="./data", vertical_crs="EVRF2007",
        workers=4,
    )
    for skipped in result.superseded:
        print(skipped.tile.sheet, "covered by", skipped.covered_by)
    if result.failed:
        ...  # retry: locally versioned tiles are reused by default
"""

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

from kartograf.cache.defaults import open_cache
from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import bbox_coords
from kartograf.core.coverage import Polygon
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.download.area import bbox_to_2180
from kartograf.download.arguments import require_bool, require_int
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    fetch_version,
    inspect_version,
    validate_update,
)
from kartograf.download.options import validate_request_bbox
from kartograf.download.plan import (
    PlanItem,
    UpdatePlan,
    new_plan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import FileStorage
from kartograf.download.versions import ContentDigest, VersionRef
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.notices import LAZ_SUPERSEDED, TILES, Notice, NoticeSink, count_text
from kartograf.providers.pl.gugik_laz import (
    COVERAGE_TOLERANCE_M,
    GugikLazProvider,
    LazTile,
    LazTileSelection,
    SupersededLazTile,
)
from kartograf.providers.pl.skorowidz_wfs import sheet_frame_2180

# (processed tiles, tiles selected for execution) — called in the caller's
# thread; ``(0, total)`` comes once before the first tile download.
LazProgressCallback = Callable[[int, int], None]

NO_TILES_MESSAGE = (
    "Brak kafli LAZ dla podanego obszaru (sprawdz obszar, --year, "
    "--min-year, --max-year i --vertical-crs; wszystkie roczniki WFS odpowiedzialy)"
)


@dataclass(frozen=True)
class LazTileFailure:
    """A tile that could not be downloaded, and the download error."""

    tile: LazTile
    error: DownloadError


@dataclass(frozen=True)
class LazDownloadResult:
    """Selected tiles, versioned files, failures, superseded tiles and stale plan items.

    With ``plan=`` the files include only executed plan positions; tiles
    removed from the plan or whose index signal changed are not downloaded.
    ``notices`` holds the superseded-tiles message (Z3).
    """

    tiles: tuple[LazTile, ...]
    files: tuple[VersionedFile, ...] = ()
    failed: tuple[LazTileFailure, ...] = ()
    superseded: tuple[SupersededLazTile, ...] = ()
    stale: tuple[PlanItem, ...] = ()
    notices: tuple[Notice, ...] = ()

    @property
    def ok(self) -> bool:
        """True when no tile failed."""
        return not self.failed


def laz_version_ref(tile: LazTile) -> VersionRef:
    """Campaign label of one WFS tile: acquisition date (or year) and request id."""
    label = f"{tile.date or tile.year}_{tile.filename.split('_', 1)[0]}"
    return VersionRef(label, "campaign")


def laz_slot(storage: FileStorage, tile: LazTile) -> FileSlot:
    """Standard path and version hierarchy in the tile's own horizontal system."""
    system = tile.system
    return FileSlot(
        output_dir=storage.output_dir,
        std=storage.get_raw_path(tile.sheet, tile.filename, system=system),
        versions_base=storage.get_raw_versions_base(tile.sheet, system=system),
        versions_root=storage.get_raw_versions_root(tile.sheet, system=system),
        ext=".laz",
    )


def write_laz_sidecar(
    provider,
    tile: LazTile,
    target: Path,
    bbox: BBox,
    *,
    year: int | None = None,
    min_density: int | None = None,
    all_campaigns: bool = False,
    min_year: int | None = None,
    max_year: int | None = None,
    parent_request: dict | None = None,
    digest: ContentDigest,
    version: VersionRef,
) -> None:
    """Write the mandatory LAZ version sidecar exclusively via ``emit_sidecar``.

    ``request`` describes the bbox and requested year/density bounds (E16).
    ``all_campaigns=False`` selects the newest flight within year bounds;
    True selects every flight within them without coverage deduplication and
    records ``"all"`` in the sidecar's ``request.campaigns`` field.
    ``extra.nominal_density`` is the NOMINAL value from GUGiK WFS
    (``char_przestrz``); actual density is often several times higher.
    ``extra.acquisition_date`` and ``extra.full_sheet`` come from WFS when
    known. ``extra.parent_request`` is only present when passed (ADR-023 (f).1).
    """
    from kartograf.sources.registry import horizontal_crs_for_system
    from kartograf.sources.sidecar import emit_sidecar

    request: dict = {
        "bbox": bbox_coords(bbox),
        "bbox_crs": bbox.crs,
    }
    if year is not None or (min_year is not None and min_year == max_year):
        request["year"] = year if year is not None else min_year
    if min_density is not None:
        request["min_density"] = min_density
    if all_campaigns:
        request["campaigns"] = "all"
    if min_year is not None:
        request["min_year"] = min_year
    if max_year is not None:
        request["max_year"] = max_year
    extra: dict = {
        "tile_sheet": tile.sheet,
        "year": tile.year,
        "nominal_density": tile.density,
        "url": tile.url,
    }
    if tile.date is not None:
        extra["acquisition_date"] = tile.date
    if tile.full_sheet is not None:
        extra["full_sheet"] = tile.full_sheet
    if parent_request is not None:
        extra["parent_request"] = parent_request
    key = getattr(provider, "descriptor_key", None)
    emit_sidecar(
        # a provider without a descriptor (a stub) still gets a LAZ sidecar
        key if isinstance(key, str) else "pl.gugik.laz",
        target,
        request=request,
        vertical_crs=provider.vertical_crs,
        # N8: the tile carries its own CRS (PL-1992 or a PL-2000 zone), while
        # the WFS channel declares only the default — unknown CRS = channel
        horizontal_crs=horizontal_crs_for_system(tile.crs),
        extra=extra,
        digest=(digest.sha256, digest.size_bytes),
        version=version.to_extra(),
        exclusive=True,
    )


def _check_selection(
    selection: LazTileSelection,
    *,
    provider,
    output_dir: str | Path,
) -> UpdatePlan:
    """Inspect selected WFS tiles without downloading any LAZ bytes."""
    storage = FileStorage(
        output_dir, resolution=None, vertical_crs=provider.vertical_crs, product="laz"
    )
    items = tuple(
        inspect_version(
            laz_slot(storage, tile),
            track="laz_tile",
            unit=tile.sheet,
            signal="index",
            available=(
                laz_version_ref(tile).label,
                {"url": tile.url, "year": tile.year, "date": tile.date},
            ),
        )
        for tile in selection.tiles
    )
    return new_plan(store_id(output_dir), items)


def _run_laz_download(
    selection: LazTileSelection,
    *,
    provider,
    bbox: BBox,
    output_dir: str | Path,
    year: int | None = None,
    min_density: int | None = None,
    all_campaigns: bool = False,
    min_year: int | None = None,
    max_year: int | None = None,
    workers: int = 1,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    on_progress: LazProgressCallback | None = None,
    parent_request: dict | None = None,
) -> LazDownloadResult:
    """Version selected LAZ tiles, collecting per-tile download failures.

    Each tile uses its own horizontal system's segment. The default and
    ``"upgrade"`` reuse existing versions (D26); ``"force"`` downloads
    bytes again without overwriting a version. With ``"upgrade"`` and a
    plan, only still-missing positions from that plan execute. Sidecars
    retain the requested bbox, year, density and parent request.
    """
    validate_update(update)
    if plan is not None:
        require_store(plan, store_id(output_dir))
    storage = FileStorage(
        output_dir, resolution=None, vertical_crs=provider.vertical_crs, product="laz"
    )
    tiles = selection.tiles
    stale: tuple[PlanItem, ...] = ()
    if update == "upgrade" and plan is not None:
        fresh = _check_selection(
            selection, provider=provider, output_dir=output_dir
        ).items
        todo, excluded = select_planned(plan, list(fresh), "laz_tile")
        keys = {(item.segment, item.hierarchy, item.name) for item in todo}
        tiles = tuple(
            tile
            for tile in tiles
            if (
                (slot := laz_slot(storage, tile)).segment,
                slot.hierarchy,
                slot.name,
            )
            in keys
        )
        stale = tuple(excluded)
    total = len(tiles)

    def fetch(
        tile: LazTile,
    ) -> tuple[LazTile, VersionedFile | None, DownloadError | None]:
        slot = laz_slot(storage, tile)

        def download(staged: Path) -> None:
            provider.download_tile(tile.url, staged)

        try:
            file = fetch_version(
                slot,
                update,
                signal="index",
                fetch=download,
                version=laz_version_ref(tile),
                write_sidecar=lambda data, ref, digest, _http: write_laz_sidecar(
                    provider,
                    tile,
                    data,
                    bbox,
                    year=year,
                    min_density=min_density,
                    all_campaigns=all_campaigns,
                    min_year=min_year,
                    max_year=max_year,
                    parent_request=parent_request,
                    digest=digest,
                    version=ref,
                ),
            )
        except DownloadError as error:
            return tile, None, error
        return tile, file, None

    outcomes: list[tuple[LazTile, VersionedFile | None, DownloadError | None]] = []

    def record(
        outcome: tuple[LazTile, VersionedFile | None, DownloadError | None],
    ) -> None:
        outcomes.append(outcome)
        if on_progress is not None:
            on_progress(len(outcomes), total)

    if on_progress is not None:
        on_progress(0, total)
    if workers > 1 and total > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(fetch, tile) for tile in tiles]
            for future in as_completed(futures):
                record(future.result())
    else:
        for tile in tiles:
            record(fetch(tile))

    order = {id(tile): i for i, tile in enumerate(tiles)}
    outcomes.sort(key=lambda outcome: order[id(outcome[0])])
    failed = sorted(
        (
            LazTileFailure(tile=tile, error=error)
            for tile, _, error in outcomes
            if error is not None
        ),
        key=lambda failure: (failure.tile.sheet, failure.tile.url),
    )
    return LazDownloadResult(
        tiles=selection.tiles,
        files=tuple(file for _, file, _ in outcomes if file is not None),
        failed=tuple(failed),
        superseded=selection.superseded,
        stale=stale,
    )


def _validate_area(bbox: BBox | None, sheet: str | None) -> BBox | None:
    """Exactly one of ``bbox``/``sheet``, valid - before any request.

    Returns ``bbox`` with its CRS code in the registry spelling (``None`` for
    a sheet) - callers go on with it.
    """
    if (bbox is None) == (sheet is None):
        raise ValidationError(
            "LAZ PL: podaj dokladnie jedno z sheet (godlo) albo bbox (obszar)"
        )
    if sheet is not None:
        SheetParser(sheet)  # ParseError: an invalid sheet code
    if bbox is not None:
        return validate_request_bbox(bbox)
    return None


def _query_area(bbox: BBox | None, sheet: str | None) -> tuple[BBox, Polygon | None]:
    """EPSG:2180 WFS query window of the request and the sheet frame
    (``None`` for a bbox: the window is the area)."""
    if sheet is not None:
        return SheetParser(sheet).get_bbox(crs="EPSG:2180"), sheet_frame_2180(sheet)
    assert bbox is not None  # _validate_area
    return bbox_to_2180(bbox), None


@contextmanager
def _selected(
    bbox: BBox | None,
    sheet: str | None,
    *,
    vertical_crs: str,
    year: int | None,
    min_density: int | None,
    all_campaigns: bool,
    min_year: int | None,
    max_year: int | None,
    provider: GugikLazProvider | None,
    tolerance_m: float,
    cache: MetadataCache | bool,
    force: bool,
    sink: NoticeSink,
) -> Iterator[tuple[GugikLazProvider, LazTileSelection, BBox]]:
    """Provider, WFS tile selection and EPSG:2180 query window of one LAZ
    request (a sheet: tiles of its frame, not of the envelope).

    The ``LAZ_SUPERSEDED`` notice is emitted right after the selection; an
    empty selection raises ``NoCoverageError`` after that notice. Library
    argument types are checked first (STANDARDS 11.2).
    """
    for name, value in (
        ("year", year),
        ("min_year", min_year),
        ("max_year", max_year),
        ("min_density", min_density),
    ):
        if value is not None:
            require_int(value, name)
    require_bool(all_campaigns, "all_campaigns")
    area, frame = _query_area(bbox, sheet)
    with open_cache(cache, force=force, on_notice=sink.add) as metadata:
        if provider is None:
            # looked up on the module: callers patch the class at its source
            from kartograf.providers.pl import gugik_laz

            provider = gugik_laz.GugikLazProvider(
                vertical_crs=vertical_crs, cache=metadata
            )
        elif vertical_crs != provider.vertical_crs:
            raise ValidationError(
                f"vertical_crs={vertical_crs} niezgodny z providerem "
                f"({provider.vertical_crs})"
            )
        selection = provider.select_tiles(
            area,
            year=year,
            min_density=min_density,
            tolerance_m=tolerance_m,
            all_campaigns=all_campaigns,
            min_year=min_year,
            max_year=max_year,
            frame=frame,
        )
        _emit_superseded(sink, selection.superseded)
        if not selection.tiles:
            raise NoCoverageError(NO_TILES_MESSAGE)
        yield provider, selection, area


def _tile_label(tile: LazTile) -> str:
    return f"{tile.sheet} ({tile.year}, {tile.crs})"


def _emit_superseded(
    sink: NoticeSink, superseded: tuple[SupersededLazTile, ...]
) -> None:
    """``LAZ_SUPERSEDED``: tiles covered by newer ones, one line per tile.

    Tiles outside the area (an edge contact, the WFS envelope only) stay in
    ``superseded`` with reason ``"outside"`` but are not reported: they are
    not part of the requested area.
    """
    covered = [entry for entry in superseded if entry.covered_by]
    if not covered:
        return
    lines = [
        f"pominieto {count_text(len(covered), *TILES)} LAZ - obszar pokrywaja "
        "nowsze kafle "
        "(domyslnie najnowszy rocznik per obszar; inny rocznik: "
        "--year/--min-year/--max-year)"
    ]
    for entry in covered:
        covering = ", ".join(_tile_label(t) for t in entry.covered_by)
        lines.append(f"  {_tile_label(entry.tile)}: pokryty przez {covering}")
    sink.emit("info", LAZ_SUPERSEDED, "\n".join(lines))


def check_laz_area(
    bbox: BBox | None = None,
    *,
    sheet: str | None = None,
    output_dir: str | Path,
    vertical_crs: str,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    all_campaigns: bool = False,
    min_density: int | None = None,
    cache: MetadataCache | bool = True,
    on_notice: Callable[[Notice], None] | None = None,
    provider: GugikLazProvider | None = None,
    tolerance_m: float = COVERAGE_TOLERANCE_M,
) -> UpdatePlan:
    """Update plan of ``download_laz_area`` with the same arguments, no download.

    The tile selection queries the WFS (as the download does); no LAZ bytes
    are transferred. Raises the same errors as the download's selection.
    The source is always asked (``--check-updates``): the metadata cache is
    refreshed, never read.
    """
    bbox = _validate_area(bbox, sheet)
    sink = NoticeSink(on_notice)
    with _selected(
        bbox,
        sheet,
        vertical_crs=vertical_crs,
        year=year,
        min_density=min_density,
        all_campaigns=all_campaigns,
        min_year=min_year,
        max_year=max_year,
        provider=provider,
        tolerance_m=tolerance_m,
        cache=cache,
        force=True,
        sink=sink,
    ) as (selected_provider, selection, _area):
        return _check_selection(
            selection, provider=selected_provider, output_dir=output_dir
        )


def download_laz_area(
    bbox: BBox | None = None,
    *,
    sheet: str | None = None,
    output_dir: str | Path,
    vertical_crs: str,
    year: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    all_campaigns: bool = False,
    min_density: int | None = None,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    workers: int = 1,
    parent_request: dict | None = None,
    cache: MetadataCache | bool = True,
    on_progress: LazProgressCallback | None = None,
    on_notice: Callable[[Notice], None] | None = None,
    provider: GugikLazProvider | None = None,
    tolerance_m: float = COVERAGE_TOLERANCE_M,
) -> LazDownloadResult:
    """
    GUGiK LAZ tiles for an area: selection (WFS) + download + sidecars.

    Parameters
    ----------
    bbox : BBox, optional
        Area in any supported CRS; converted to EPSG:2180 (Czech CRSs via
        the pinned operation), e.g. a geometry envelope from
        ``get_overall_bbox(path, target_crs="EPSG:2180")``.
    sheet : str, optional
        Instead of ``bbox``: a PL-1992 or PL-2000 sheet code. The WFS is
        asked for the envelope of its frame, the tiles are those reaching
        into the frame itself (neighbouring sheets only touch it).
    output_dir : str or Path
        Explicit base directory for LAZ tiles and their sidecars.
    vertical_crs : str
        "EVRF2007" (current European heights) or "KRON86" (legacy
        Kronsztadt 86). Chooses the WFS service and output segment;
        an injected provider must declare the same height system.
    year, min_density
        Acquisition year / nominal-density filters. With ``year``, reference
        coverage must be available within that year before downloading.
    all_campaigns : bool, optional
        False (default) selects the newest flight within year bounds using
        ADR-029 coverage selection; True selects every flight within bounds
        without coverage deduplication (ADR-030).
    min_year, max_year : int, optional
        Closed acquisition-year bounds; an uncovered reference tile raises
        ``YearRangeError`` before any download. Exclusive with ``year``.
    update : None or "upgrade" or "force", optional
        Reuse a local version by default; ``"force"`` downloads again.
    plan : UpdatePlan, optional
        From :func:`check_laz_area`; with ``update="upgrade"`` only its
        still-missing positions execute, changed ones land in ``stale``.
    workers : int
        Parallel tile downloads (1 = sequential).
    parent_request : dict, optional
        Sidecar ``extra.parent_request`` (ADR-023 (f).1).
    cache : MetadataCache or bool
        ``True`` = default metadata cache in the current directory, a
        ``MetadataCache`` = that cache, ``False`` = none.
    on_progress, on_notice
        Progress ``(done, total)`` (``(0, total)`` before the first tile) and
        data notices (``LAZ_SUPERSEDED`` right after the selection).
    provider : GugikLazProvider, optional
        Custom provider (session); by default a new one for ``vertical_crs``.
    tolerance_m : float
        Edge tolerance of the coverage rules (``COVERAGE_TOLERANCE_M``).

    Returns
    -------
    LazDownloadResult
        Tile download failures are in ``failed`` (not an exception) —
        ``result.ok``.

    Raises
    ------
    ValidationError
        Not exactly one of ``bbox``/``sheet``, unknown/mismatched
        ``vertical_crs`` or invalid year bounds / ``update`` mode.
    ParseError
        An invalid ``sheet`` code.
    TransformError
        No safe pinned operation from a Czech CRS of ``bbox``.
    DownloadError
        WFS discovery failure or no matching year in the service.
    YearRangeError
        A reference tile has data outside the requested range only.
    NoCoverageError
        (a ``DownloadError`` subclass) no tiles in any year for the area.
    """
    bbox = _validate_area(bbox, sheet)
    validate_update(update)
    require_int(workers, "workers")
    sink = NoticeSink(on_notice)
    with _selected(
        bbox,
        sheet,
        vertical_crs=vertical_crs,
        year=year,
        min_density=min_density,
        all_campaigns=all_campaigns,
        min_year=min_year,
        max_year=max_year,
        provider=provider,
        tolerance_m=tolerance_m,
        cache=cache,
        force=update == "force",
        sink=sink,
    ) as (selected_provider, selection, area):
        result = _run_laz_download(
            selection,
            provider=selected_provider,
            bbox=area,
            output_dir=output_dir,
            year=year,
            min_density=min_density,
            all_campaigns=all_campaigns,
            min_year=min_year,
            max_year=max_year,
            workers=workers,
            update=update,
            plan=plan,
            on_progress=on_progress,
            parent_request=parent_request,
        )
    return replace(result, notices=sink.notices)
