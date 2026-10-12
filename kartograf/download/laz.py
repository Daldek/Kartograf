"""
Downloading LAZ tiles for an area — library layer (review-1 D17).

Pattern: ``download/cutout.py`` — the CLI (``kartograf download --product
laz``) is a thin layer over this module: it prints messages and translates
the result into an exit code. There is no ``print`` or argparse here.

Flow: bbox EPSG:2180 -> ``GugikLazProvider.select_tiles`` (WFS, tile
selection from the newest vintage without duplicating the area) ->
``run_laz_download`` (parallel downloads into ``versions/``, mandatory
version sidecars and standard hardlinks; tile failures collected).

Example::

    from kartograf import BBox, download_laz_area

    result = download_laz_area(
        BBox(637400, 487000, 637450, 487050, "EPSG:2180"),
        output_dir="./data", vertical_crs="EVRF2007",
        max_workers=4,
    )
    for skipped in result.superseded:
        print(skipped.tile.sheet, "covered by", skipped.covered_by)
    if result.failed:
        ...  # retry: locally versioned tiles are reused by default
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kartograf._version import build_version
from kartograf.core.sheet_parser import BBox
from kartograf.download.fetch import (
    FileSlot,
    UpdateMode,
    VersionedFile,
    fetch_version,
    inspect_version,
    validate_update,
)
from kartograf.download.plan import (
    PlanItem,
    UpdatePlan,
    require_store,
    select_planned,
    store_id,
)
from kartograf.download.storage import FileStorage
from kartograf.download.versions import ContentDigest, VersionRef
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.providers.pl.gugik_laz import (
    COVERAGE_TOLERANCE_M,
    GugikLazProvider,
    LazTile,
    LazTileSelection,
    SupersededLazTile,
)

# (processed tiles, tiles selected for execution) — called in the caller's thread
LazProgressCallback = Callable[[int, int], None]

NO_TILES_MESSAGE = (
    "No LAZ tiles found for the given area (sprawdz obszar, --year, "
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
    """

    tiles: tuple[LazTile, ...]
    files: tuple[VersionedFile, ...] = ()
    failed: tuple[LazTileFailure, ...] = ()
    superseded: tuple[SupersededLazTile, ...] = ()
    stale: tuple[PlanItem, ...] = ()

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
        "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
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


def check_laz_updates(
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
    return UpdatePlan(
        store=store_id(output_dir),
        checked_at=datetime.now(UTC).isoformat(timespec="seconds"),
        kartograf_version=build_version(),
        items=items,
    )


def run_laz_download(
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
    max_workers: int = 1,
    update: UpdateMode | None = None,
    plan: UpdatePlan | None = None,
    on_progress: LazProgressCallback | None = None,
    parent_request: dict | None = None,
) -> LazDownloadResult:
    """Version selected LAZ tiles, collecting per-tile download failures.

    Each tile uses its own horizontal system's segment. The default and
    ``"upgrade"`` reuse existing versions (D26); ``"force"`` downloads
    bytes again without overwriting a version. With ``"upgrade"`` and a
    plan, only still-missing positions from that plan execute. ``"check"``
    is available through :func:`check_laz_updates`, not this function.
    Sidecars retain the requested bbox, year, density and parent request.
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
        fresh = check_laz_updates(
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
            provider.download(tile.url, staged)

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

    if max_workers > 1 and total > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
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


def download_laz_area(
    bbox: BBox,
    *,
    output_dir: str | Path,
    vertical_crs: str,
    year: int | None = None,
    min_density: int | None = None,
    all_campaigns: bool = False,
    min_year: int | None = None,
    max_year: int | None = None,
    max_workers: int = 1,
    update: UpdateMode | None = None,
    on_progress: LazProgressCallback | None = None,
    parent_request: dict | None = None,
    provider: GugikLazProvider | None = None,
    tolerance_m: float = COVERAGE_TOLERANCE_M,
) -> LazDownloadResult:
    """
    GUGiK LAZ tiles for an area: selection (WFS) + download + sidecars.

    Parameters
    ----------
    bbox : BBox
        Area in EPSG:2180 (e.g. ``SheetParser.get_bbox(crs="EPSG:2180")``
        or ``get_overall_bbox(path, target_crs="EPSG:2180")``).
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
        Use :func:`check_laz_updates` for a download-free update plan.
    parent_request : dict, optional
        Sidecar ``extra.parent_request`` (ADR-023 (f).1) — the CLI passes it
        in ``--bbox``/``--geometry`` mode.
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
    ValueError
        ``bbox`` not in EPSG:2180, or an unknown / mismatched ``vertical_crs``.
    ValidationError
        Invalid year bounds, ``year`` with a bound, or invalid update mode.
    DownloadError
        WFS discovery failure or no matching year in the service.
    YearRangeError
        A reference tile has data outside the requested range only.
    NoCoverageError
        (a ``DownloadError`` subclass) no tiles in any year for the area.
    """
    validate_update(update)
    if provider is None:
        provider = GugikLazProvider(vertical_crs=vertical_crs)
    elif vertical_crs != provider.vertical_crs:
        raise ValueError(
            f"vertical_crs={vertical_crs} niezgodny z providerem "
            f"({provider.vertical_crs})"
        )
    selection = provider.select_tiles(
        bbox,
        year=year,
        min_density=min_density,
        tolerance_m=tolerance_m,
        all_campaigns=all_campaigns,
        min_year=min_year,
        max_year=max_year,
    )
    if not selection.tiles:
        raise NoCoverageError(NO_TILES_MESSAGE)
    return run_laz_download(
        selection,
        provider=provider,
        bbox=bbox,
        output_dir=output_dir,
        year=year,
        min_density=min_density,
        all_campaigns=all_campaigns,
        min_year=min_year,
        max_year=max_year,
        max_workers=max_workers,
        update=update,
        on_progress=on_progress,
        parent_request=parent_request,
    )
