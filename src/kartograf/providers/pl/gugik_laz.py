"""
GUGiK provider for downloading LAZ point-cloud data.

This module provides the GugikLazProvider class for downloading airborne
laser scanning (ALS) point clouds — *dane pomiarowe LIDAR / chmury punktów* —
distributed by GUGiK as ``.laz`` files.

Unlike NMT / NMPT / Ortofoto (which discover OpenData URLs through WMS
``GetFeatureInfo``), LAZ tiles are discovered through a **WFS** ``GetFeature``
query. Each WFS feature already carries the full download URL
(``url_do_pobrania``) plus metadata, so no URL has to be constructed and the
fine tile sheet never has to be parsed.

Key differences from the other GUGiK products:

- Discovery is **area-based**: a bbox (derived from a sheet / ``--bbox`` /
  ``--geometry``) is sent to the WFS, which returns every LAZ tile intersecting
  it. GUGiK tiles LAZ far finer than 1:10000, so a single 1:10000 sheet maps to
  *many* LAZ tiles, each with its own (opaque) sheet.
- Two services split by height system: ``EVRF2007`` (current, years 2018+) and
  ``KRON86`` (legacy, years 2010–2019).
- A point density (``char_przestrz``, e.g. ``25 p/m2``) and acquisition year
  (``akt_rok``) distinguish overlapping tiles.

Examples
--------
>>> from kartograf import BBox
>>> provider = GugikLazProvider(vertical_crs="EVRF2007")
>>> bbox = BBox(530469, 382961, 532660, 385291, "EPSG:2180")
>>> tiles = provider.discover_tiles(bbox)
>>> for tile in tiles:
...     provider.download_tile(tile.url, Path("./laz") / f"{tile.sheet}.laz")
"""

import logging
import math
import re
import threading
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field, fields, replace
from pathlib import Path

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.core.coverage import (
    AREA_EPS,
    Polygon,
    clip_convex,
    expand_convex,
    polygon_area,
    rectangle,
    uncovered_pieces,
)
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.messages import message
from kartograf.providers.base import DataSourceProvider
from kartograf.providers.pl.skorowidz_wfs import (
    GML_NS,
    WfsIndex,
    cached_answer_by_type,
    cached_feature_types,
    corner_xy,
    feature_footprint,
    feature_text,
    time_position,
    type_year,
)
from kartograf.serialization import EncodeContext
from kartograf.sources.registry import parse_pl_system
from kartograf.sources.variants import IndexRef, variants
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
    download_to,
)

logger = logging.getLogger(__name__)

# Coverage edge tolerance (m) when selecting LAZ tiles: an older tile is
# redundant also when newer tiles miss its intersection with the area by a
# strip narrower than this value. Rationale (impl-laz.md): tile frames of
# different CRSs (PL-1992 vs PL-2000) and campaigns do not lie edge to edge,
# GUGiK rounds their coordinates to 1 cm, and the ALS point position error is
# 0.10-0.30 m (``blad_sr_syt``); a 1 m strip is 2-4 rows of points at
# 4-20 p/m2 — it does not justify downloading a 50-250 MB tile. At the same
# time 1 m is 2-3 orders of magnitude smaller than a tile (~500-1100 m), so it
# will not hide a real gap in a newer campaign.
COVERAGE_TOLERANCE_M = 1.0


@dataclass
class LazTile:
    """
    A single LAZ point-cloud tile discovered via WFS.

    Attributes
    ----------
    sheet : str
        Tile identifier as published by GUGiK (opaque — finer than 1:10000,
        PL-1992 or PL-2000 form). Used only for labelling / storage.
    url : str
        Full OpenData download URL for the ``.laz`` file.
    year : int or None
        Acquisition year (``akt_rok``).
    density : int or None
        Nominal point density in points/m² parsed from ``char_przestrz``.
    crs : str or None
        Horizontal CRS string (``uklad_xy``, e.g. ``PL-2000:S6``).
    min_x, min_y, max_x, max_y : float
        Tile extent in EPSG:2180 (NaN if the feature had no geometry).
    footprint : tuple of (x, y), optional
        Tile frame from ``msGeometry`` in EPSG:2180, axes (E, N), a convex
        CCW polygon without a closing vertex. ``None`` when the WFS gave no
        geometry or it is not a single convex polygon.
    date : str, optional
        Acquisition date ``akt_data`` (ISO ``YYYY-MM-DD``) — decides the order
        of tiles of the same year.
    full_sheet : bool, optional
        ``czy_ark_wypelniony`` (``TAK``/``NIE``). A tile with ``False`` does
        not "cover" the area during tile selection: its footprint is the sheet
        frame, and the data fills it only partially.
    """

    sheet: str
    url: str
    year: int | None
    density: int | None
    crs: str | None
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    footprint: tuple[tuple[float, float], ...] | None = None
    date: str | None = None
    full_sheet: bool | None = None

    @property
    def filename(self) -> str:
        """Return the original OpenData file name (preserves density/seq id)."""
        return self.url.rstrip("/").rsplit("/", 1)[-1]

    @property
    def system(self) -> str:
        """Horizontal system of the tile for the storage segment: "1992" or "2000".

        Single source of truth for the CLI and the library (review max
        2026-08-30, finding 8), parsed from ``crs`` (``uklad_xy``) by
        ``sources.registry.parse_pl_system`` — the same parser as the index
        (skorowidz) records and ``horizontal_crs_for_system`` (sidecar), review-1
        D3. An unrecognized or missing ``uklad_xy`` (e.g. ``"PL-2000"``
        without a zone) raises ``ValidationError``: guessing from the sheet format used
        to put such a tile into ``pl_2000`` with an EPSG:2180 sidecar.
        ``discover_tiles`` never returns such tiles (they are skipped).
        """
        parsed = parse_pl_system(self.crs)
        if parsed is None:
            raise ValidationError(
                message("providers.tile_unknown_xy_crs", sheet=self.sheet, crs=self.crs)
            )
        return parsed[0]

    def __json__(self, ctx: EncodeContext) -> dict[str, object]:
        """JSON object of the fields (``kartograf.serialization`` hook).

        An extent the WFS feature did not have (NaN in memory) is ``null``:
        NaN is no JSON value.
        """
        data: dict[str, object] = {f.name: getattr(self, f.name) for f in fields(self)}
        for name in ("min_x", "min_y", "max_x", "max_y"):
            value = data[name]
            if isinstance(value, float) and math.isnan(value):
                data[name] = None
        return data


@dataclass(frozen=True)
class SupersededLazTile:
    """
    A tile skipped during selection, with the reason.

    ``covered_by`` — selected tiles (newer, or earlier in the order of the
    same year) that together cover the tile's intersection with the area
    (within ``COVERAGE_TOLERANCE_M``). Empty tuple: the tile does not reach
    into the area - only its edge touches it (a neighbouring sheet of a
    sheet request) or only the WFS envelope intersected it.
    """

    tile: LazTile
    covered_by: tuple[LazTile, ...] = ()

    @property
    def reason(self) -> str:
        """``"covered"`` (covered by newer tiles) or ``"outside"``."""
        return "covered" if self.covered_by else "outside"


@dataclass(frozen=True)
class LazTileSelection:
    """Tile selection result.

    ``tiles`` to download (by sheet) and ``superseded``;
    ``below_density``: the tiles of the area dropped by ``min_density`` before
    the selection (``select_tiles`` only).
    """

    tiles: tuple[LazTile, ...]
    superseded: tuple[SupersededLazTile, ...] = field(default=())
    below_density: tuple[LazTile, ...] = field(default=())


def _tile_order_key(
    tile: LazTile,
) -> tuple[int, tuple[int, ...], float, str, str]:
    """Greedy order: newest year, newest date, then stable."""
    return (
        -(tile.year or 0),
        _negated_date(tile.date),
        -(tile.density or 0),
        tile.sheet,
        tile.url,
    )


def _negated_date(date: str | None) -> tuple[int, ...]:
    """``"2025-08-12"`` -> ``(-2025, -8, -12)``; no date goes to the end of the year."""
    if not date:
        return (0,)
    try:
        return tuple(-int(part) for part in date.split("-")[:3])
    except ValueError:
        return (0,)


def _finite_envelope(tile: LazTile) -> bool:
    return not any(
        math.isnan(v) for v in (tile.min_x, tile.min_y, tile.max_x, tile.max_y)
    )


def _shift(poly: Iterable[tuple[float, float]], ox: float, oy: float) -> Polygon:
    return tuple((x - ox, y - oy) for x, y in poly)


def _tile_region(tile: LazTile, ox: float, oy: float) -> Polygon | None:
    """Tile extent (local): footprint, else envelope; None without geometry."""
    if tile.footprint is not None:
        return _shift(tile.footprint, ox, oy)
    if _finite_envelope(tile):
        return rectangle(
            tile.min_x - ox, tile.min_y - oy, tile.max_x - ox, tile.max_y - oy
        )
    return None


def _significant(poly: Polygon) -> bool:
    return len(poly) >= 3 and abs(polygon_area(poly)) > AREA_EPS


def _local_area(area: BBox | Polygon) -> tuple[float, float, Polygon]:
    """Local origin and the area as a local convex CCW polygon.

    ``area``: an EPSG:2180 ``BBox`` or a convex CCW (E, N) polygon in
    EPSG:2180 (a sheet frame, ``skorowidz_wfs.sheet_frame_2180``). Local
    coordinates: values of ~10^5-10^6 m eat up precision.
    """
    if isinstance(area, BBox):
        if area.crs != "EPSG:2180":
            raise ValidationError(message("providers.area_crs_not_2180", crs=area.crs))
        return (
            area.min_x,
            area.min_y,
            rectangle(0.0, 0.0, area.max_x - area.min_x, area.max_y - area.min_y),
        )
    ox = min(x for x, _ in area)
    oy = min(y for _, y in area)
    return ox, oy, _shift(area, ox, oy)


def _width(poly: Polygon) -> float:
    """Smallest width of a convex polygon (a supporting line holds an edge)."""
    width = math.inf
    for i, (x0, y0) in enumerate(poly):
        x1, y1 = poly[(i + 1) % len(poly)]
        length = math.hypot(x1 - x0, y1 - y0)
        if length > 0:
            far = max(abs((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) for x, y in poly)
            width = min(width, far / length)
    return width


def _edge_rim(area: Polygon, tolerance_m: float) -> float:
    """Return the rim of the reach rule: ``tolerance_m``, or 0 for a narrow area.

    An area at most twice as wide has no inner part - any overlap counts.
    """
    return tolerance_m if _width(area) > 2 * tolerance_m else 0.0


def _reaches(region: Polygon, area: Polygon, rim_m: float) -> bool:
    """Check whether the tile region overlaps the area by more than an edge sliver.

    The region with its edges moved ``rim_m`` inwards must still overlap the
    area (the ``overlaps_area`` rule of the sheet indexes): a neighbouring
    sheet shares an edge with the frame of a sheet request and touches it
    only (GUGiK frames are rounded to 1 cm, frame edges are curves in
    EPSG:2180). A region at most twice ``rim_m`` wide is taken whole.
    """
    if rim_m > 0 and _width(region) > 2 * rim_m:
        region = expand_convex(region, -rim_m)
    return _significant(clip_convex(region, area))


def _bounds(poly: Polygon) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _add_full_cover(
    tile: LazTile,
    ox: float,
    oy: float,
    tolerance_m: float,
    covers: list[tuple[LazTile, Polygon, tuple[float, float, float, float]]],
    full_by_sheet: dict[str, LazTile],
) -> None:
    """Index a full tile's footprint and sheet code for the shared coverage rule."""
    if tile.full_sheet is False:
        return
    full_by_sheet.setdefault(tile.sheet, tile)
    if tile.footprint is not None:
        grown = expand_convex(_shift(tile.footprint, ox, oy), tolerance_m)
        covers.append((tile, grown, _bounds(grown)))


def _uncovered_parts(
    tile: LazTile,
    part: Polygon | None,
    covers: list[tuple[LazTile, Polygon, tuple[float, float, float, float]]],
    full_by_sheet: Mapping[str, LazTile],
) -> tuple[list[Polygon] | None, tuple[LazTile, ...]]:
    """Return uncovered area and relevant covers; None means geometry is unknown.

    A full tile with the same sheet code covers even when its geometry is
    unavailable. Otherwise only full tiles with footprints count, expanded by
    the caller's tolerance. Both greedy selection and range checking use this
    exact rule.
    """
    same = full_by_sheet.get(tile.sheet)
    if same is not None:
        return [], (same,)
    if part is None:
        return None, ()
    if not _significant(part):
        return None, ()
    px0, py0, px1, py1 = _bounds(part)
    relevant = [
        (other, grown)
        for other, grown, (gx0, gy0, gx1, gy1) in covers
        if gx0 < px1
        and gx1 > px0
        and gy0 < py1
        and gy1 > py0
        and _significant(clip_convex(part, grown))
    ]
    return (
        uncovered_pieces(part, [grown for _, grown in relevant]),
        tuple(other for other, _ in relevant),
    )


def select_newest_cover(
    tiles: Iterable[LazTile],
    area: BBox | Polygon,
    tolerance_m: float = COVERAGE_TOLERANCE_M,
) -> LazTileSelection:
    """
    Greedy selection of LAZ tiles from the newest: no area duplication.

    Tiles are scanned from the newest ``year`` (within a year: newer ``date``,
    higher density, sheet, URL). A tile is skipped if its intersection with
    ``area`` is already covered by the union of previously selected tiles,
    each expanded by ``tolerance_m`` (a strip narrower than the tolerance does
    not save the tile); a tile contributing an uncovered piece stays. All in
    EPSG:2180 — PL-1992 and PL-2000 tiles are compared in one CRS.

    Caution rules (doubt = download):

    - the tile extent is its ``footprint``; without it the envelope (excess =
      the tile stays more easily),
    - a tile must reach more than ``tolerance_m`` into the area: one that
      only touches it along an edge (the neighbouring sheet of a sheet frame)
      goes to ``superseded`` as ``"outside"``; an area at most twice as wide
      as the tolerance takes every overlapping tile,
    - only tiles with ``full_sheet`` other than ``False`` cover, and only
      with their ``footprint`` (the envelope of a rotated frame sticks out
      beyond it by even ~15 m) or with the same sheet (the same sheet frame —
      this is how a tile without geometry covers too),
    - a tile without any geometry (NaN) stays, unless a full tile with the
      same sheet has already been selected.

    ``area``: an EPSG:2180 ``BBox`` or a convex CCW (E, N) polygon in
    EPSG:2180 (the frame of a sheet request), like the WFS tiles.
    """
    ox, oy, area_poly = _local_area(area)
    rim = _edge_rim(area_poly, tolerance_m)

    kept: list[LazTile] = []
    # (tile, expanded extent, envelope of the expanded extent)
    covers: list[tuple[LazTile, Polygon, tuple[float, float, float, float]]] = []
    superseded: list[SupersededLazTile] = []
    # selected full tiles by sheet: the same sheet = the same sheet frame
    full_by_sheet: dict[str, LazTile] = {}
    for tile in sorted(tiles, key=_tile_order_key):
        region = _tile_region(tile, ox, oy)
        if region is not None and not _reaches(region, area_poly, rim):
            superseded.append(SupersededLazTile(tile=tile))  # outside the area
            continue
        part = clip_convex(region, area_poly) if region is not None else None
        remaining, covered_by = _uncovered_parts(tile, part, covers, full_by_sheet)
        if remaining == []:
            superseded.append(SupersededLazTile(tile=tile, covered_by=covered_by))
            continue
        kept.append(tile)  # unknown geometry stays (doubt = download)
        _add_full_cover(tile, ox, oy, tolerance_m, covers, full_by_sheet)
    return LazTileSelection(
        tiles=tuple(sorted(kept, key=lambda t: (t.sheet, t.url))),
        superseded=tuple(
            sorted(superseded, key=lambda s: (s.tile.sheet, -(s.tile.year or 0)))
        ),
    )


def select_all_intersecting(
    tiles: Iterable[LazTile],
    area: BBox | Polygon,
    tolerance_m: float = COVERAGE_TOLERANCE_M,
) -> LazTileSelection:
    """
    All LAZ tiles reaching into ``area`` (no deduplication).

    With ``all_campaigns=True`` (ADR-030), tiles covered by newer ones are
    not skipped (unlike :func:`select_newest_cover`). The tile extent is its
    ``footprint`` (envelope without it); a tile that reaches no more than
    ``tolerance_m`` into the area (an edge contact, or only the WFS envelope
    intersected it) goes to ``superseded`` with an empty ``covered_by``
    (reason ``"outside"``). A tile without any geometry (NaN) stays.
    ``area`` as in :func:`select_newest_cover`.
    """
    ox, oy, area_poly = _local_area(area)
    rim = _edge_rim(area_poly, tolerance_m)

    kept: list[LazTile] = []
    superseded: list[SupersededLazTile] = []
    for tile in tiles:
        region = _tile_region(tile, ox, oy)
        if region is None:
            kept.append(tile)  # cannot be judged without geometry — download
            continue
        if not _reaches(region, area_poly, rim):
            superseded.append(SupersededLazTile(tile=tile))  # outside the area
            continue
        kept.append(tile)
    return LazTileSelection(
        tiles=tuple(sorted(kept, key=lambda t: (t.sheet, t.url))),
        superseded=tuple(
            sorted(superseded, key=lambda s: (s.tile.sheet, -(s.tile.year or 0)))
        ),
    )


def _reference_year_conflicts(
    reference: LazTileSelection,
    selected: LazTileSelection,
    found: list[LazTile],
    area: BBox | Polygon,
    min_year: int | None,
    max_year: int | None,
    tolerance_m: float,
) -> tuple[dict[str, tuple[int, ...]], dict[str, str], dict[str, frozenset[int]]]:
    """Find reference tiles whose area the chosen years do not fully cover.

    Also returns, per conflicting tile, the years whose intersecting tiles are
    all partial sheets (``czy_ark_wypelniony=NIE``): they exist but cannot cover.
    """
    # Local import avoids the download -> manager -> provider import cycle.
    from kartograf.download.campaigns import in_year_range

    ox, oy, area_poly = _local_area(area)
    covers: list[tuple[LazTile, Polygon, tuple[float, float, float, float]]] = []
    full_by_sheet: dict[str, LazTile] = {}
    for tile in selected.tiles:
        _add_full_cover(tile, ox, oy, tolerance_m, covers, full_by_sheet)

    conflicts: dict[str, tuple[int, ...]] = {}
    labels: dict[str, str] = {}
    partial_years: dict[str, frozenset[int]] = {}
    regions: list[tuple[LazTile, Polygon | None]] | None = None
    for tile in reference.tiles:
        if in_year_range(tile.year, min_year, max_year):
            continue
        region = _tile_region(tile, ox, oy)
        part = clip_convex(region, area_poly) if region is not None else None
        remaining, _ = _uncovered_parts(tile, part, covers, full_by_sheet)
        if remaining == []:
            continue
        if regions is None:
            regions = [(other, _tile_region(other, ox, oy)) for other in found]
        # year -> True while every intersecting tile of that year is partial
        partial_only: dict[int, bool] = {}
        for other, other_region in regions:
            if other.year is None:
                continue
            touches = (remaining is None and other.sheet == tile.sheet) or (
                remaining is not None
                and other_region is not None
                and any(
                    _significant(clip_convex(piece, other_region))
                    for piece in remaining
                )
            )
            if touches:
                partial_only[other.year] = partial_only.get(other.year, True) and (
                    other.full_sheet is False
                )
        conflicts[tile.sheet] = tuple(sorted(partial_only))
        labels[tile.sheet] = f"({tile.year}, {tile.crs})"
        partial = frozenset(y for y, only in partial_only.items() if only)
        if partial:
            partial_years[tile.sheet] = partial
    return conflicts, labels, partial_years


def _laz_indexes() -> dict[str, IndexRef]:
    """WFS index of the LAZ variants per height system (variant registry)."""
    return {
        v.vertical_crs: v.index_ref
        for v in variants(product="laz", country="PL")
        if v.index_ref is not None and v.vertical_crs is not None
    }


def laz_tile(elem: ET.Element) -> LazTile | None:
    """Build a ``LazTile`` of one WFS feature of the LAZ index.

    ``None``: no URL or sheet, or an unrecognized ``uklad_xy``. Shared by the tile
    discovery and the availability report.
    """
    url = feature_text(elem, "url_do_pobrania")
    sheet = feature_text(elem, "godlo")
    if not url or not sheet:
        return None
    crs = feature_text(elem, "uklad_xy")
    if parse_pl_system(crs) is None:
        # D3: the same parser as the index and the sidecar — a tile without
        # a recognized CRS is skipped (like an index record) rather than
        # guessed from the sheet (pl_2000 segment + EPSG:2180 sidecar)
        logger.warning(
            message("providers.tile_unknown_xy_crs_skipped", sheet=sheet, crs=crs)
        )
        return None

    year_text = feature_text(elem, "akt_rok")
    year = int(year_text) if year_text and year_text.isdigit() else None

    density = None
    density_text = feature_text(elem, "char_przestrz")
    if density_text:
        match = re.search(r"(\d+)", density_text)
        if match:
            density = int(match.group(1))

    lower = upper = None
    for env in elem.iter(f"{{{GML_NS}}}Envelope"):
        srs_name = env.get("srsName")
        lc = env.find(f"{{{GML_NS}}}lowerCorner")
        uc = env.find(f"{{{GML_NS}}}upperCorner")
        if lc is not None and lc.text:
            lower = corner_xy(lc.text, srs_name)
        if uc is not None and uc.text:
            upper = corner_xy(uc.text, srs_name)
        break

    if lower is not None and upper is not None:
        min_x, min_y = lower
        max_x, max_y = upper
    else:
        min_x = min_y = max_x = max_y = math.nan

    full_text = feature_text(elem, "czy_ark_wypelniony")
    full_sheet = {"TAK": True, "NIE": False}.get((full_text or "").upper())

    return LazTile(
        sheet=sheet,
        url=url,
        year=year,
        density=density,
        crs=crs,
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
        footprint=feature_footprint(elem),
        date=time_position(elem, "akt_data"),
        full_sheet=full_sheet,
    )


class GugikLazProvider(DataSourceProvider):
    """
    Provider for downloading LAZ point-cloud data from GUGiK via WFS.

    Discovery is area-based: :meth:`discover_tiles` queries the WFS index
    (skorowidze) for every tile intersecting a bbox; :meth:`download_tile`
    fetches a single tile by its URL. Not a ``BaseProvider``: there is no
    download by sheet code (A5-7) - the fine tile sheet is treated as an
    opaque label and is never
    passed to ``SheetParser``. The index services and their yearly types come
    from the variant registry (``variants(product="laz")``) and the shared
    WFS client (``providers/pl/skorowidz_wfs.py::WfsIndex``).

    Parameters
    ----------
    session : requests.Session, optional
        HTTP session for WFS metadata requests and tile downloads. Defaults
        to a shared-connection GUGiK session.
    vertical_crs : str
        "EVRF2007" (current European heights) or "KRON86" (legacy heights).
        Selects which WFS service is queried and the storage segment.
    cache : MetadataCache, optional
        Unused placeholder for API symmetry with the other providers.
    """

    BASE_URL = "https://mapy.geoportal.gov.pl"

    DEFAULT_TIMEOUT = 60  # LAZ files are large
    WFS_TIMEOUT = 30
    MAX_RETRIES = MAX_RETRIES

    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        vertical_crs: str,
        cache: MetadataCache | None = None,
    ):
        self._indexes = _laz_indexes()
        if vertical_crs not in self._indexes:
            raise ValidationError(
                message(
                    "providers.unsupported_vertical_crs_init",
                    vertical_crs=vertical_crs,
                    indexes=sorted(self._indexes),
                )
            )
        # One session per thread (the CLI pool downloads tiles in parallel,
        # and requests.Session is not thread-safe); an injected session wins —
        # the caller is responsible for using it from multiple threads.
        self._sessions = SessionPerThread(session)
        self._vertical_crs = vertical_crs
        self._cache = cache
        # In-memory cache of available years per height system
        self._available_years: dict[str, list[int]] = {}
        self._years_lock = threading.Lock()
        # Cached index answers of an area by type (endpoint, bbox) - read once.
        self._held: dict[tuple[str, BBox], dict[str, list[ET.Element]] | None] = {}
        self.descriptor_key = "pl.gugik.laz"

    @property
    def name(self) -> str:
        """Return provider name."""
        return message("providers.provider_name")

    @property
    def base_url(self) -> str:
        """Return base URL for GUGiK service."""
        return self.BASE_URL

    @property
    def default_extension(self) -> str:
        """Return default file extension for LAZ data."""
        return ".laz"

    @property
    def vertical_crs(self) -> str:
        """Return the default height system used for discovery."""
        return self._vertical_crs

    def _index(self, vertical_crs: str, timeout: float) -> WfsIndex:
        """WFS index of a height system (``MAX_RETRIES`` attempts per request)."""
        ref = self._indexes[vertical_crs]
        return WfsIndex(
            self._sessions.get,
            ref.endpoint,
            ref.layer_prefix,
            timeout=timeout,
            retries=self.MAX_RETRIES,
        )

    # =========================================================================
    # Year discovery (WFS GetCapabilities)
    # =========================================================================

    def _fetch_available_years(
        self, vertical_crs: str, timeout: int = WFS_TIMEOUT
    ) -> list[int]:
        """
        Fetch available acquisition years from WFS GetCapabilities.

        Returns a list of years (descending) parsed from the
        ``SkorowidzDanychPomiarowychLIDAR<year>`` feature-type names - the
        cached answer of GetCapabilities when there is one (ADR-056).

        Raises
        ------
        DownloadError
            If the request fails or no LIDAR feature types are found.
        """
        types = cached_feature_types(self._index(vertical_crs, timeout), self._cache)
        return sorted({type_year(name) for name in types}, reverse=True)

    def _get_available_years(
        self, vertical_crs: str, timeout: int = WFS_TIMEOUT
    ) -> list[int]:
        """Get years cached per height system, caching only successful responses."""
        with self._years_lock:
            cached = self._available_years.get(vertical_crs)
            if cached is not None:
                return cached

            years = self._fetch_available_years(vertical_crs, timeout)
            self._available_years[vertical_crs] = years
            return years

    # =========================================================================
    # Tile discovery (WFS GetFeature)
    # =========================================================================

    def discover_tiles(
        self,
        bbox: BBox,
        year: int | None = None,
        min_density: int | None = None,
        vertical_crs: str | None = None,
        timeout: int = WFS_TIMEOUT,
        *,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> list[LazTile]:
        """
        Discover the LAZ tiles to download for ``bbox`` (sorted by sheet).

        Shortcut for ``select_tiles(...).tiles`` — see :meth:`select_tiles`
        for the selection rule (newest tile per area, no duplicated area
        across years / horizontal systems) and the raised errors. Use
        :meth:`select_tiles` to also learn which tiles were skipped and why.
        """
        return list(
            self.select_tiles(
                bbox,
                year=year,
                min_density=min_density,
                vertical_crs=vertical_crs,
                timeout=timeout,
                min_year=min_year,
                max_year=max_year,
            ).tiles
        )

    def select_tiles(
        self,
        bbox: BBox,
        year: int | None = None,
        min_density: int | None = None,
        vertical_crs: str | None = None,
        timeout: int = WFS_TIMEOUT,
        tolerance_m: float = COVERAGE_TOLERANCE_M,
        *,
        all_campaigns: bool = False,
        min_year: int | None = None,
        max_year: int | None = None,
        frame: Polygon | None = None,
    ) -> LazTileSelection:
        """
        Query WFS for tiles intersecting ``bbox`` and pick those to download.

        Every available year is queried when a range is requested, including
        years outside it: they establish the reference coverage and the years
        reported in conflicts. Tiles below ``min_density`` are dropped first.
        Without a range, selection follows the usual ADR-029 coverage rule.
        With a range, every reference tile must be covered by full tiles from
        the range (the same 1 m-tolerant rule); otherwise nothing is downloaded.

        Parameters
        ----------
        bbox : BBox
            Area of interest in EPSG:2180 (the WFS query window).
        year : int, optional
            Exact acquisition year (equivalent to ``min_year=max_year``).
        min_density : int, optional
            Drop tiles whose nominal point density is below this value
            (points/m²) — before the coverage rule.
        vertical_crs : str, optional
            Override the default height system for this query.
        timeout : int, optional
            Per-request timeout for WFS calls.
        tolerance_m : float, optional
            Edge tolerance of the selection (default ``COVERAGE_TOLERANCE_M``
            = 1 m; ``0`` = exact): a tile must reach deeper into the area,
            and a strip of the area narrower than it does not keep an older
            tile.
        all_campaigns : bool, optional
            False (default) selects the newest flights within year bounds
            under the ADR-029 coverage rule; True selects every tile in bounds
            reaching into the area (:func:`select_all_intersecting`), without
            coverage-based deduplication (ADR-030).
        min_year, max_year : int, optional
            Closed acquisition-year bounds; exclusive with ``year``.
        frame : tuple of (x, y), optional
            Sheet frame inside ``bbox``: a convex CCW (E, N) polygon in
            EPSG:2180 (``skorowidz_wfs.sheet_frame_2180``). The WFS is asked
            for ``bbox``, the tiles are selected for the frame - a rotated
            PL-1992 frame is smaller than its envelope, and the neighbouring
            sheets only touch it.

        Returns
        -------
        LazTileSelection
            ``tiles`` to download (sorted by sheet) and ``superseded`` —
            skipped tiles with the tiles covering them.

        Raises
        ------
        ValidationError
            If ``bbox`` is not in EPSG:2180, the year bounds are invalid, or
            ``year`` is combined with ``min_year``/``max_year``.
        DownloadError
            WFS discovery failure or a range without a year in the service.
        YearRangeError
            The requested years leave some reference tile area uncovered.
        """
        # Local import: the kartograf.download package imports manager -> providers.pl
        from kartograf.download.campaigns import (
            in_year_range,
            validate_year_bounds,
            year_range_error,
            year_range_label,
        )

        if year is not None and (min_year is not None or max_year is not None):
            raise ValidationError(message("providers.year_excludes_range"))
        lo, hi = (year, year) if year is not None else (min_year, max_year)
        validate_year_bounds(lo, hi)
        if bbox.crs != "EPSG:2180":
            raise ValidationError(message("providers.bbox_crs_not_2180", crs=bbox.crs))

        vcrs = vertical_crs or self._vertical_crs
        if vcrs not in self._indexes:
            raise ValidationError(
                message(
                    "providers.unsupported_vertical_crs",
                    vcrs=vcrs,
                    indexes=sorted(self._indexes),
                )
            )

        available_years = self._get_available_years(vcrs, timeout)
        # `--year Y` reaches the provider as [Y, Y] (CLI): same wording as year=
        if lo is not None and lo == hi and lo not in available_years:
            raise DownloadError(
                message(
                    "providers.vintage_not_in_service",
                    lo=lo,
                    vcrs=vcrs,
                    years=", ".join(map(str, available_years)),
                )
            )
        has_range = lo is not None or hi is not None
        if has_range and not any(in_year_range(y, lo, hi) for y in available_years):
            label = (
                f"{lo}-{hi}"
                if lo is not None and hi is not None
                else year_range_label(lo, hi)
            )
            raise DownloadError(
                message(
                    "providers.range_no_vintage",
                    label=label,
                    vcrs=vcrs,
                    years=", ".join(map(str, available_years)),
                )
            )
        found: list[LazTile] = []
        below: list[LazTile] = []
        for yr in available_years:
            for tile in self._query_layer(vcrs, yr, bbox, timeout):
                if min_density is not None and (
                    tile.density is None or tile.density < min_density
                ):
                    below.append(tile)
                    continue
                found.append(tile)

        candidates = (
            [tile for tile in found if in_year_range(tile.year, lo, hi)]
            if has_range
            else found
        )
        area = bbox if frame is None else frame
        selection = (
            select_all_intersecting(candidates, area, tolerance_m)
            if all_campaigns
            else select_newest_cover(candidates, area, tolerance_m)
        )
        if has_range:
            reference = select_newest_cover(found, area, tolerance_m)
            conflicts, labels, partial_years = _reference_year_conflicts(
                reference, selection, found, area, lo, hi, tolerance_m
            )
            if conflicts:
                raise year_range_error(
                    conflicts,
                    lo,
                    hi,
                    total=len(reference.tiles),
                    unit=message("providers.unit_area_tiles"),
                    subject=message("providers.subject_laz_tiles"),
                    labels=labels,
                    partial_years=partial_years,
                )
        return replace(selection, below_density=tuple(below))

    def _query_layer(
        self,
        vertical_crs: str,
        year: int,
        bbox: BBox,
        timeout: int,
    ) -> Iterator[LazTile]:
        """Tiles of one yearly type (every page, ``WfsIndex.features``).

        A cached answer for the same bbox that holds the type stands for the
        query (``cached_answer_by_type``: the availability report's, ADR-056).
        A response whose tiles all miss the bbox means an axis-order mismatch
        (the server answered in E,N), never "no tiles": ``DownloadError``.
        """
        index = self._index(vertical_crs, timeout)
        layer = f"{index.layer_prefix}{year}"
        key = (index.endpoint, bbox)
        if key not in self._held:
            self._held[key] = cached_answer_by_type(self._cache, *key)
        held = self._held[key]
        features: Iterable[ET.Element] = (
            held[layer]
            if held is not None and layer in held
            else index.features(bbox, [f"gugik:{layer}"])
        )
        returned = kept = 0
        for feature in features:
            tile = laz_tile(feature)
            if tile is None:
                continue
            returned += 1
            if self._intersects(tile, bbox):
                kept += 1
                yield tile
        if returned and not kept:
            raise DownloadError(
                message(
                    "providers.wfs_axis_order_mismatch", layer=layer, returned=returned
                )
            )

    @staticmethod
    def _intersects(tile: LazTile, bbox: BBox) -> bool:
        """
        Return True if the tile envelope intersects the query bbox.

        Tiles without geometry (NaN extent) are kept rather than dropped.
        """
        if any(math.isnan(v) for v in (tile.min_x, tile.min_y, tile.max_x, tile.max_y)):
            return True
        return (
            tile.min_x <= bbox.max_x
            and tile.max_x >= bbox.min_x
            and tile.min_y <= bbox.max_y
            and tile.max_y >= bbox.min_y
        )

    # =========================================================================
    # Download a single tile (by URL)
    # =========================================================================

    def download_tile(
        self,
        url: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download a single LAZ tile from its OpenData URL.

        Note
        ----
        The argument is the tile's download URL (obtained from
        :meth:`discover_tiles`), not a sheet — LAZ tiles are identified by
        opaque finer-than-1:10000 ids that are not parseable.

        Parameters
        ----------
        url : str
            OpenData ``.laz`` URL (``LazTile.url``).
        output_path : Path
            Destination file path.
        timeout : int, optional
            Request timeout in seconds (default: 60).

        Returns
        -------
        Path
            Path to the downloaded file.

        Raises
        ------
        DownloadError
            If the download fails after all retries.
        """
        return download_to(
            self._sessions.get(),
            url,
            Path(output_path),
            timeout=timeout,
            retries=self.MAX_RETRIES,
            description=output_path.name,
        )
