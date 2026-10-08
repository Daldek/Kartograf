"""
Downloading LAZ tiles for an area — library layer (review-1 D17).

Pattern: ``download/cutout.py`` — the CLI (``kartograf download --product
laz``) is a thin layer over this module: it prints messages and translates
the result into an exit code. There is no ``print`` or argparse here.

Flow: bbox EPSG:2180 -> ``GugikLazProvider.select_tiles`` (WFS, tile
selection from the newest vintage without duplicating the area) ->
``run_laz_download`` (thread pool, ``<file>.laz.meta.json`` sidecar per
tile, tile failures collected, not raised).

Przyklad::

    from kartograf import BBox, download_laz_area

    result = download_laz_area(
        BBox(637400, 487000, 637450, 487050, "EPSG:2180"),
        output_dir="./data",
        max_workers=4,
    )
    for skipped in result.superseded:
        print(skipped.tile.godlo, "covered by", skipped.covered_by)
    if result.failed:
        ...  # retry: tiles already downloaded are skipped (force=False)
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from kartograf.core.sheet_parser import BBox
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.providers.pl.gugik_laz import (
    COVERAGE_TOLERANCE_M,
    GugikLazProvider,
    LazTile,
    LazTileSelection,
    SupersededLazTile,
)

# (downloaded or skipped tiles, tile count) — called in the caller's thread
LazProgressCallback = Callable[[int, int], None]

NO_TILES_MESSAGE = (
    "No LAZ tiles found for the given area (sprawdz obszar, --year, "
    "--min-year i --vertical-crs; wszystkie roczniki WFS odpowiedzialy)"
)


@dataclass(frozen=True)
class LazTileFailure:
    """A tile that could not be downloaded, and the download error."""

    tile: LazTile
    error: DownloadError


@dataclass(frozen=True)
class LazDownloadResult:
    """
    Result of ``run_laz_download`` / ``download_laz_area``.

    ``tiles`` — tiles selected for download (by godlo); each ends up in
    exactly one of the lists ``downloaded`` (downloaded now), ``skipped``
    (file already existed, ``force=False``) or ``failed``. ``superseded`` —
    tiles dropped during selection (covered by newer tiles or outside the
    area).
    """

    tiles: tuple[LazTile, ...]
    downloaded: tuple[Path, ...] = ()
    skipped: tuple[Path, ...] = ()
    failed: tuple[LazTileFailure, ...] = ()
    superseded: tuple[SupersededLazTile, ...] = ()

    @property
    def ok(self) -> bool:
        """True when no tile failed."""
        return not self.failed


def write_laz_sidecar(
    provider,
    tile: LazTile,
    target: Path,
    bbox: BBox,
    *,
    year: int | None = None,
    min_density: int | None = None,
    campaigns: str = "newest",
    min_year: int | None = None,
    parent_request: dict | None = None,
) -> None:
    """Best-effort LAZ tile sidecar via ``emit_sidecar`` (error = warning in log).

    ``request`` describes the actual request: the bbox and the ``year`` and
    ``min_density`` filters, when given (E16). ``extra.nominal_density`` and
    ``min_density`` are the NOMINAL value from the GUGiK WFS
    (``char_przestrz``) — the actual tile density is often several times
    higher. ``request.campaigns`` only for ``"all"`` (``newest`` = ADR-029,
    unchanged), ``request.min_year`` when given (ADR-030).
    ``extra.parent_request`` — only when given (ADR-023 (f).1: ``--bbox``/
    ``--geometry`` mode).
    """
    from kartograf.sources.registry import horizontal_crs_for_uklad
    from kartograf.sources.sidecar import emit_sidecar

    request: dict = {
        "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
        "bbox_crs": bbox.crs,
    }
    if year is not None:
        request["year"] = year
    if min_density is not None:
        request["min_density"] = min_density
    if campaigns == "all":
        request["campaigns"] = campaigns
    if min_year is not None:
        request["min_year"] = min_year
    extra: dict = {
        "tile_sheet": tile.godlo,
        "year": tile.year,
        "nominal_density": tile.density,
        "url": tile.url,
    }
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
        horizontal_crs=horizontal_crs_for_uklad(tile.crs),
        extra=extra,
    )


def run_laz_download(
    selection: LazTileSelection,
    *,
    provider,
    bbox: BBox,
    output_dir: str | Path = "./data",
    year: int | None = None,
    min_density: int | None = None,
    campaigns: str = "newest",
    min_year: int | None = None,
    max_workers: int = 1,
    force: bool = False,
    on_progress: LazProgressCallback | None = None,
    parent_request: dict | None = None,
) -> LazDownloadResult:
    """
    Download the selected LAZ tiles (in parallel) and write sidecars.

    A tile goes to ``FileStorage(output_dir, product="laz",
    vertical_crs=provider.vertical_crs)`` — the ``{uklad}`` segment per tile
    (``LazTile.uklad``), so one request may write to ``pl_1992_*`` and
    ``pl_2000_*``. An existing file is skipped without network access,
    unless ``force=True``. A tile download failure (``DownloadError``) does
    NOT abort the others: it goes to ``failed`` (sorted by godlo and URL),
    and successful tiles stay on disk. Other exceptions (e.g. a write
    ``OSError``) abort the call.

    ``bbox``, ``year``, ``min_density``, ``campaigns``, ``min_year`` and
    ``parent_request`` describe the request in the sidecars (``request`` and
    ``extra.parent_request``).
    """
    storage = FileStorage(output_dir, product="laz", vertical_crs=provider.vertical_crs)
    tiles = selection.tiles
    total = len(tiles)

    def fetch(tile: LazTile) -> tuple[str, LazTile, Path | None, DownloadError | None]:
        target = storage.get_raw_path(tile.godlo, tile.filename, uklad=tile.uklad)
        if not force and target.exists():
            return "skip", tile, target, None
        try:
            provider.download(tile.url, target)
        except DownloadError as e:
            return "fail", tile, None, e
        write_laz_sidecar(
            provider,
            tile,
            target,
            bbox,
            year=year,
            min_density=min_density,
            campaigns=campaigns,
            min_year=min_year,
            parent_request=parent_request,
        )
        return "ok", tile, target, None

    outcomes: list[tuple[str, LazTile, Path | None, DownloadError | None]] = []

    def record(outcome) -> None:
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
    outcomes.sort(key=lambda o: order[id(o[1])])
    failed = sorted(
        (
            LazTileFailure(tile=t, error=e)
            for s, t, _, e in outcomes
            if s == "fail" and e
        ),
        key=lambda f: (f.tile.godlo, f.tile.url),
    )
    return LazDownloadResult(
        tiles=tiles,
        downloaded=tuple(p for s, _, p, _ in outcomes if s == "ok" and p is not None),
        skipped=tuple(p for s, _, p, _ in outcomes if s == "skip" and p is not None),
        failed=tuple(failed),
        superseded=selection.superseded,
    )


def download_laz_area(
    bbox: BBox,
    *,
    output_dir: str | Path = "./data",
    vertical_crs: str | None = None,
    year: int | None = None,
    min_density: int | None = None,
    campaigns: str = "newest",
    min_year: int | None = None,
    max_workers: int = 1,
    force: bool = False,
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
        Area in EPSG:2180 (e.g. ``SheetParser(godlo).get_bbox(crs="EPSG:2180")``
        or ``get_overall_bbox(path, target_crs="EPSG:2180")``).
    vertical_crs : str, optional
        ``"EVRF2007"`` (default) or ``"KRON86"`` — the WFS service and the
        ``laz/pl_<uklad>_<vcrs>`` segment. With a custom ``provider`` it
        defaults to its vertical CRS; an explicit, different value is a
        ``ValueError``.
    year, min_density
        WFS filters (as in ``GugikLazProvider.select_tiles``). Without
        ``year`` tiles are selected from the newest vintage, and an older
        tile is dropped when its intersection with the area is covered by
        newer ones (``result.superseded``); with ``year`` — only that
        vintage.
    campaigns : {"newest", "all"}
        ``"newest"`` — ADR-029 selection; ``"all"`` — every tile
        intersecting the area, without deduplication (ADR-030).
    min_year : int, optional
        Lower bound on ``akt_rok`` (older vintages are not queried);
        mutually exclusive with ``year`` (``ValidationError``).
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
        Unknown ``campaigns``, or ``year`` together with ``min_year``.
    DownloadError
        WFS discovery failure (the result would be incomplete) or a
        nonexistent ``year``.
    NoCoverageError
        (a ``DownloadError`` subclass) the WFS responded, but there are no
        tiles for the area and filters.
    """
    if provider is None:
        provider = GugikLazProvider(vertical_crs=vertical_crs or "EVRF2007")
    elif vertical_crs is not None and vertical_crs != provider.vertical_crs:
        raise ValueError(
            f"vertical_crs={vertical_crs} niezgodny z providerem "
            f"({provider.vertical_crs})"
        )
    selection = provider.select_tiles(
        bbox,
        year=year,
        min_density=min_density,
        tolerance_m=tolerance_m,
        campaigns=campaigns,
        min_year=min_year,
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
        campaigns=campaigns,
        min_year=min_year,
        max_workers=max_workers,
        force=force,
        on_progress=on_progress,
        parent_request=parent_request,
    )
