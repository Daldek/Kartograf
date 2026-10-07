"""
Pobieranie kafli LAZ dla obszaru — warstwa biblioteczna (review-1 D17).

Wzor: ``download/cutout.py`` — CLI (``kartograf download --product laz``)
jest nakladka na ten modul: wypisuje komunikaty i tlumaczy wynik na kod
wyjscia. Tu nie ma ``print`` ani argparse.

Przeplyw: bbox EPSG:2180 -> ``GugikLazProvider.select_tiles`` (WFS, wybor
kafli od najnowszego rocznika bez dublowania obszaru) -> ``run_laz_download``
(pula watkow, sidecar ``<plik>.laz.meta.json`` per kafel, porazki kafli
zbierane, nie rzucane).

Przyklad::

    from kartograf import BBox, download_laz_area

    result = download_laz_area(
        BBox(637400, 487000, 637450, 487050, "EPSG:2180"),
        output_dir="./data",
        max_workers=4,
    )
    for skipped in result.superseded:
        print(skipped.tile.godlo, "pokryty przez", skipped.covered_by)
    if result.failed:
        ...  # ponow: kafle juz pobrane sa pomijane (force=False)
"""

import logging
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

logger = logging.getLogger(__name__)

# (pobrane lub pominiete kafle, liczba kafli) — wolane w watku wolajacego
LazProgressCallback = Callable[[int, int], None]

NO_TILES_MESSAGE = (
    "No LAZ tiles found for the given area (sprawdz obszar, --year "
    "i --vertical-crs; wszystkie roczniki WFS odpowiedzialy)"
)


@dataclass(frozen=True)
class LazTileFailure:
    """Kafel, ktorego nie udalo sie pobrac, i blad pobrania."""

    tile: LazTile
    error: DownloadError


@dataclass(frozen=True)
class LazDownloadResult:
    """
    Wynik ``run_laz_download`` / ``download_laz_area``.

    ``tiles`` — kafle wybrane do pobrania (po godle); kazdy trafia do
    dokladnie jednej z list ``downloaded`` (pobrany teraz), ``skipped``
    (plik juz byl, ``force=False``) albo ``failed``. ``superseded`` — kafle
    pominiete przy wyborze (pokryte nowszymi kaflami albo poza obszarem).
    """

    tiles: tuple[LazTile, ...]
    downloaded: tuple[Path, ...] = ()
    skipped: tuple[Path, ...] = ()
    failed: tuple[LazTileFailure, ...] = ()
    superseded: tuple[SupersededLazTile, ...] = ()

    @property
    def ok(self) -> bool:
        """True, gdy zaden kafel nie zawiodl."""
        return not self.failed


def write_laz_sidecar(
    provider,
    tile: LazTile,
    target: Path,
    bbox: BBox,
    *,
    year: int | None = None,
    min_density: int | None = None,
    parent_request: dict | None = None,
) -> None:
    """Best-effort sidecar kafla LAZ (blad zapisu = ostrzezenie w logu).

    ``request`` opisuje faktyczne zadanie: bbox oraz filtry ``year``
    i ``min_density``, gdy podane (E16). ``extra.gestosc`` i ``min_density``
    to wartosc NOMINALNA z WFS GUGiK (``char_przestrz``) — faktyczna gestosc
    kafla bywa kilkukrotnie wyzsza. ``extra.parent_request`` — tylko gdy
    podany (ADR-023 (f).1: tryb ``--bbox``/``--geometry``).
    """
    try:
        from kartograf.sources.registry import get_source, horizontal_crs_for_uklad
        from kartograf.sources.sidecar import build_metadata, write_sidecar

        key = getattr(provider, "descriptor_key", None)
        request: dict = {
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": bbox.crs,
        }
        if year is not None:
            request["year"] = year
        if min_density is not None:
            request["min_density"] = min_density
        extra: dict = {
            "godlo_kafla": tile.godlo,
            "rok": tile.year,
            "gestosc": tile.density,
            "url": tile.url,
        }
        if parent_request is not None:
            extra["parent_request"] = parent_request
        meta = build_metadata(
            get_source(key if isinstance(key, str) else "pl.gugik.laz"),
            request=request,
            vertical_crs=provider.vertical_crs,
            # N8: kafel niesie wlasny uklad (PL-1992 albo strefa PL-2000),
            # a kanal WFS deklaruje tylko domyslny — nieznany uklad = kanal
            horizontal_crs=horizontal_crs_for_uklad(tile.crs),
            extra=extra,
        )
        write_sidecar(target, meta)
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        logger.warning(f"Nie udalo sie zapisac sidecara dla {target}: {e}")


def run_laz_download(
    selection: LazTileSelection,
    *,
    provider,
    bbox: BBox,
    output_dir: str | Path = "./data",
    year: int | None = None,
    min_density: int | None = None,
    max_workers: int = 1,
    force: bool = False,
    on_progress: LazProgressCallback | None = None,
    parent_request: dict | None = None,
) -> LazDownloadResult:
    """
    Pobierz wybrane kafle LAZ (rownolegle) i zapisz sidecary.

    Kafel trafia do ``FileStorage(output_dir, product="laz",
    vertical_crs=provider.vertical_crs)`` — segment ``{uklad}`` per kafel
    (``LazTile.uklad``), wiec jedno zadanie moze pisac do ``pl_1992_*``
    i ``pl_2000_*``. Istniejacy plik jest pomijany bez sieci, chyba ze
    ``force=True``. Porazka pobrania kafla (``DownloadError``) NIE przerywa
    pozostalych: trafia do ``failed`` (posortowane po godle i URL), a kafle
    udane zostaja na dysku. Inne wyjatki (np. ``OSError`` zapisu) przerywaja
    wywolanie.

    ``bbox``, ``year``, ``min_density`` i ``parent_request`` opisuja zadanie
    w sidecarach (``request`` i ``extra.parent_request``).
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
    max_workers: int = 1,
    force: bool = False,
    on_progress: LazProgressCallback | None = None,
    parent_request: dict | None = None,
    provider: GugikLazProvider | None = None,
    tolerance_m: float = COVERAGE_TOLERANCE_M,
) -> LazDownloadResult:
    """
    Kafle LAZ GUGiK dla obszaru: wybor (WFS) + pobranie + sidecary.

    Parameters
    ----------
    bbox : BBox
        Obszar w EPSG:2180 (np. ``SheetParser(godlo).get_bbox(crs="EPSG:2180")``
        albo ``get_overall_bbox(path, target_crs="EPSG:2180")``).
    vertical_crs : str, optional
        ``"EVRF2007"`` (domyslnie) albo ``"KRON86"`` — usluga WFS i segment
        ``laz/pl_<uklad>_<vcrs>``. Z wlasnym ``provider`` domyslnie jego pion;
        jawna, inna wartosc to ``ValueError``.
    year, min_density
        Filtry WFS (jak ``GugikLazProvider.select_tiles``). Bez ``year``
        kafle sa wybierane od najnowszego rocznika, a starszy kafel jest
        pomijany, gdy jego czesc wspolna z obszarem pokrywaja nowsze
        (``result.superseded``); z ``year`` — tylko ten rocznik.
    parent_request : dict, optional
        ``extra.parent_request`` sidecarow (ADR-023 (f).1) — CLI podaje go
        w trybie ``--bbox``/``--geometry``.
    provider : GugikLazProvider, optional
        Wlasny provider (sesja); domyslnie nowy dla ``vertical_crs``.
    tolerance_m : float
        Tolerancja krawedzi regul pokrycia (``COVERAGE_TOLERANCE_M``).

    Returns
    -------
    LazDownloadResult
        Porazki pobrania kafli sa w ``failed`` (nie wyjatek) — ``result.ok``.

    Raises
    ------
    ValueError
        ``bbox`` nie w EPSG:2180 albo nieznany / niezgodny ``vertical_crs``.
    DownloadError
        Awaria discovery WFS (wynik bylby niepelny) albo nieistniejacy
        ``year``.
    NoCoverageError
        (podklasa ``DownloadError``) WFS odpowiedzial, ale nie ma kafli dla
        obszaru i filtrow.
    """
    if provider is None:
        provider = GugikLazProvider(vertical_crs=vertical_crs or "EVRF2007")
    elif vertical_crs is not None and vertical_crs != provider.vertical_crs:
        raise ValueError(
            f"vertical_crs={vertical_crs} niezgodny z providerem "
            f"({provider.vertical_crs})"
        )
    selection = provider.select_tiles(
        bbox, year=year, min_density=min_density, tolerance_m=tolerance_m
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
        max_workers=max_workers,
        force=force,
        on_progress=on_progress,
        parent_request=parent_request,
    )
