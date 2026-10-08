"""
GUGiK provider for downloading LAZ point-cloud data.

This module provides the GugikLazProvider class for downloading airborne
laser scanning (ALS) point clouds — *dane pomiarowe LIDAR / chmury punktów* —
distributed by GUGiK as ``.laz`` files.

Unlike NMT / NMPT / Ortofoto (which discover OpenData URLs through WMS
``GetFeatureInfo``), LAZ tiles are discovered through a **WFS** ``GetFeature``
query. Each WFS feature already carries the full download URL
(``url_do_pobrania``) plus metadata, so no URL has to be constructed and the
fine tile godlo never has to be parsed.

Key differences from the other GUGiK products:

- Discovery is **area-based**: a bbox (derived from a godlo / ``--bbox`` /
  ``--geometry``) is sent to the WFS, which returns every LAZ tile intersecting
  it. GUGiK tiles LAZ far finer than 1:10000, so a single 1:10000 sheet maps to
  *many* LAZ tiles, each with its own (opaque) godlo.
- Two services split by height system: ``EVRF2007`` (current, years 2018+) and
  ``KRON86`` (legacy, years 2010–2019).
- A point density (``char_przestrz``, e.g. ``25 p/m2``) and acquisition year
  (``akt_rok``) distinguish overlapping tiles.

Examples
--------
>>> from kartograf import BBox
>>> provider = GugikLazProvider()
>>> bbox = BBox(530469, 382961, 532660, 385291, "EPSG:2180")
>>> tiles = provider.discover_tiles(bbox)
>>> for tile in tiles:
...     provider.download(tile.url, Path("./laz") / f"{tile.godlo}.laz")
"""

import logging
import math
import re
import threading
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.core.coverage import (
    AREA_EPS,
    Polygon,
    clip_convex,
    expand_convex,
    normalize_convex,
    polygon_area,
    rectangle,
    uncovered_pieces,
)
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.sources.registry import parse_pl_uklad
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
    download_to,
    get_with_retry,
)

logger = logging.getLogger(__name__)

# XML namespaces used in the WFS GML responses
_GUGIK_NS = "http://www.gugik.gov.pl"
_GML_NS = "http://www.opengis.net/gml/3.2"

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
    godlo : str
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

    godlo: str
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
    def uklad(self) -> str:
        """Horizontal system of the tile for the storage segment: "1992" or "2000".

        Single source of truth for the CLI and the library (review max
        2026-08-30, finding 8), parsed from ``crs`` (``uklad_xy``) by
        ``sources.registry.parse_pl_uklad`` — the same parser as the index
        (skorowidz) records and ``horizontal_crs_for_uklad`` (sidecar), review-1
        D3. An unrecognized or missing ``uklad_xy`` (e.g. ``"PL-2000"``
        without a zone) raises ``ValidationError``: guessing from the godlo format used
        to put such a tile into ``pl_2000`` with an EPSG:2180 sidecar.
        ``discover_tiles`` never returns such tiles (they are skipped).
        """
        parsed = parse_pl_uklad(self.crs)
        if parsed is None:
            raise ValidationError(
                f"Kafel {self.godlo}: nierozpoznany uklad_xy {self.crs!r} "
                "(oczekiwano 'PL-1992' albo 'PL-2000:S5'..'S8')"
            )
        return parsed[0]


@dataclass(frozen=True)
class SupersededLazTile:
    """
    A tile skipped during selection, with the reason.

    ``covered_by`` — selected tiles (newer, or earlier in the order of the
    same year) that together cover the tile's intersection with the area
    (within ``COVERAGE_TOLERANCE_M``). Empty tuple: the tile polygon does not
    intersect the area at all (only the WFS envelope did).
    """

    tile: LazTile
    covered_by: tuple[LazTile, ...] = ()

    @property
    def reason(self) -> str:
        """``"covered"`` (covered by newer tiles) or ``"outside"``."""
        return "covered" if self.covered_by else "outside"


@dataclass(frozen=True)
class LazTileSelection:
    """Tile selection result: ``tiles`` to download (by godlo) and ``superseded``."""

    tiles: tuple[LazTile, ...]
    superseded: tuple[SupersededLazTile, ...] = field(default=())


def _tile_order_key(tile: LazTile) -> tuple:
    """Greedy order: newest year, newest date, then stable."""
    return (
        -(tile.year or 0),
        _negated_date(tile.date),
        -(tile.density or 0),
        tile.godlo,
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


def _bounds(poly: Polygon) -> tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def select_newest_cover(
    tiles: Iterable[LazTile],
    area: BBox,
    tolerance_m: float = COVERAGE_TOLERANCE_M,
) -> LazTileSelection:
    """
    Greedy selection of LAZ tiles from the newest: no area duplication.

    Tiles are scanned from the newest ``year`` (within a year: newer ``date``,
    higher density, godlo, URL). A tile is skipped if its intersection with
    ``area`` is already covered by the union of previously selected tiles,
    each expanded by ``tolerance_m`` (a strip narrower than the tolerance does
    not save the tile); a tile contributing an uncovered piece stays. All in
    EPSG:2180 — PL-1992 and PL-2000 tiles are compared in one CRS.

    Caution rules (doubt = download):

    - the tile extent is its ``footprint``; without it the envelope (excess =
      the tile stays more easily),
    - only tiles with ``full_sheet`` other than ``False`` cover, and only
      with their ``footprint`` (the envelope of a rotated frame sticks out
      beyond it by even ~15 m) or with the same godlo (the same sheet frame —
      this is how a tile without geometry covers too),
    - a tile without any geometry (NaN) stays, unless a full tile with the
      same godlo has already been selected.

    ``area`` must be in EPSG:2180 (like the WFS tiles).
    """
    if area.crs != "EPSG:2180":
        raise ValueError(f"area must be in EPSG:2180, got {area.crs}")
    # Local coordinate origin: coordinates of ~10^5-10^6 m eat up precision.
    ox, oy = area.min_x, area.min_y
    area_poly = rectangle(0.0, 0.0, area.max_x - ox, area.max_y - oy)

    kept: list[LazTile] = []
    # (tile, expanded extent, envelope of the expanded extent)
    covers: list[tuple[LazTile, Polygon, tuple[float, float, float, float]]] = []
    superseded: list[SupersededLazTile] = []
    # selected full tiles by godlo: the same godlo = the same sheet frame
    full_by_godlo: dict[str, LazTile] = {}
    for tile in sorted(tiles, key=_tile_order_key):
        same = full_by_godlo.get(tile.godlo)
        if same is not None:
            superseded.append(SupersededLazTile(tile=tile, covered_by=(same,)))
            continue
        region = _tile_region(tile, ox, oy)
        if region is None:
            kept.append(tile)  # cannot be judged without geometry — download
            if tile.full_sheet is not False:
                full_by_godlo.setdefault(tile.godlo, tile)
            continue
        part = clip_convex(region, area_poly)
        if not _significant(part):
            superseded.append(SupersededLazTile(tile=tile))  # envelope only
            continue
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
        if not uncovered_pieces(part, [grown for _, grown in relevant]):
            superseded.append(
                SupersededLazTile(
                    tile=tile, covered_by=tuple(other for other, _ in relevant)
                )
            )
            continue
        kept.append(tile)
        if tile.full_sheet is False:
            continue
        full_by_godlo.setdefault(tile.godlo, tile)
        if tile.footprint is not None:
            grown = expand_convex(_shift(tile.footprint, ox, oy), tolerance_m)
            covers.append((tile, grown, _bounds(grown)))

    return LazTileSelection(
        tiles=tuple(sorted(kept, key=lambda t: (t.godlo, t.url))),
        superseded=tuple(
            sorted(superseded, key=lambda s: (s.tile.godlo, -(s.tile.year or 0)))
        ),
    )


def select_all_intersecting(tiles: Iterable[LazTile], area: BBox) -> LazTileSelection:
    """
    All LAZ tiles whose extent intersects ``area`` (no deduplication).

    Strategy ``campaigns="all"`` (ADR-030): no skipping of a tile covered by
    a newer one (unlike :func:`select_newest_cover`). The tile extent is its
    ``footprint`` (envelope without it); a tile whose polygon has no positive
    shared area with the area (only the WFS envelope intersected it) goes to
    ``superseded`` with an empty ``covered_by`` (reason ``"outside"``).
    A tile without any geometry (NaN) stays. ``area`` in EPSG:2180.
    """
    if area.crs != "EPSG:2180":
        raise ValueError(f"area must be in EPSG:2180, got {area.crs}")
    ox, oy = area.min_x, area.min_y
    area_poly = rectangle(0.0, 0.0, area.max_x - ox, area.max_y - oy)

    kept: list[LazTile] = []
    superseded: list[SupersededLazTile] = []
    for tile in tiles:
        region = _tile_region(tile, ox, oy)
        if region is None:
            kept.append(tile)  # cannot be judged without geometry — download
            continue
        if not _significant(clip_convex(region, area_poly)):
            superseded.append(SupersededLazTile(tile=tile))  # envelope only
            continue
        kept.append(tile)
    return LazTileSelection(
        tiles=tuple(sorted(kept, key=lambda t: (t.godlo, t.url))),
        superseded=tuple(
            sorted(superseded, key=lambda s: (s.tile.godlo, -(s.tile.year or 0)))
        ),
    )


class GugikLazProvider(BaseProvider):
    """
    Provider for downloading LAZ point-cloud data from GUGiK via WFS.

    Discovery is area-based: :meth:`discover_tiles` queries the WFS index
    (skorowidze) for every tile intersecting a bbox; :meth:`download` fetches
    a single tile by its URL. The fine tile godlo is treated as an opaque label
    and is never
    passed to ``SheetParser``.

    Parameters
    ----------
    session : requests.Session, optional
        HTTP session for WFS metadata requests and tile downloads. Defaults
        to a shared-connection GUGiK session.
    vertical_crs : str, optional
        Default height system: ``"EVRF2007"`` (current, default) or
        ``"KRON86"`` (legacy). Selects which WFS service is queried.
    cache : MetadataCache, optional
        Unused placeholder for API symmetry with the other providers.
    """

    BASE_URL = "https://mapy.geoportal.gov.pl"

    # WFS index (skorowidze) services by height system (verified 2026-06-24).
    # The matching WMS services are 401-gated and unusable; WFS is open.
    WFS_ENDPOINTS = {
        "EVRF2007": f"{BASE_URL}/wss/service/PZGIK/"
        "DanePomiaroweLidarEVRF2007/WFS/Skorowidze",
        "KRON86": f"{BASE_URL}/wss/service/PZGIK/"
        "DanePomiaroweLidarKRON86/WFS/Skorowidze",
    }

    # Per-year feature types are named "<prefix><year>"
    LAYER_PREFIX = "SkorowidzDanychPomiarowychLIDAR"

    SUPPORTED_VERTICAL_CRS = ["EVRF2007", "KRON86"]

    DEFAULT_TIMEOUT = 60  # LAZ files are large
    WFS_TIMEOUT = 30
    MAX_RETRIES = MAX_RETRIES
    PAGE_SIZE = 1000  # WFS pagination COUNT

    _CACHE_PRODUCT = "laz"

    def __init__(
        self,
        session: requests.Session | None = None,
        vertical_crs: str = "EVRF2007",
        cache=None,
    ):
        if vertical_crs not in self.SUPPORTED_VERTICAL_CRS:
            raise ValueError(
                f"Unsupported vertical_crs: '{vertical_crs}'. "
                f"Supported: {self.SUPPORTED_VERTICAL_CRS}"
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
        self.descriptor_key = "pl.gugik.laz"

    @property
    def name(self) -> str:
        """Return provider name."""
        return "GUGiK LAZ (chmura punktów)"

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

    def _get_wfs_xml(self, url: str, timeout: int, description: str) -> ET.Element:
        """Fetch WFS XML without turning a failed request into missing coverage."""
        try:
            response = get_with_retry(
                self._sessions.get(),
                url,
                timeout=timeout,
                retries=3,
                description=description,
            )
        except DownloadError as e:
            raise DownloadError(f"{e} — wynik bylby niepelny, ponow pobranie") from e

        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            raise DownloadError(
                f"{description}: odpowiedz WFS nieczytelna: {e} — "
                "wynik bylby niepelny, ponow pobranie"
            ) from e

        if _localname(root.tag) == "ExceptionReport":
            details = "; ".join(
                elem.text.strip()
                for elem in root.iter()
                if _localname(elem.tag) == "ExceptionText" and elem.text
            )
            raise DownloadError(
                f"{description}: ExceptionReport: {details} — "
                "wynik bylby niepelny, ponow pobranie"
            )
        return root

    # =========================================================================
    # Year discovery (WFS GetCapabilities)
    # =========================================================================

    def _fetch_available_years(
        self, vertical_crs: str, timeout: int = WFS_TIMEOUT
    ) -> list[int]:
        """
        Fetch available acquisition years from WFS GetCapabilities.

        Returns a list of years (descending) parsed from the
        ``SkorowidzDanychPomiarowychLIDAR<year>`` feature-type names.

        Raises
        ------
        DownloadError
            If the request fails or no LIDAR feature types are found.
        """
        endpoint = self.WFS_ENDPOINTS[vertical_crs]
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetCapabilities",
        }
        description = f"WFS GetCapabilities ({vertical_crs})"
        root = self._get_wfs_xml(
            f"{endpoint}?{urlencode(params)}", timeout, description
        )
        years: set[int] = set()
        for elem in root.iter():
            if _localname(elem.tag) == "Name" and elem.text:
                match = re.search(rf"{self.LAYER_PREFIX}(\d{{4}})", elem.text)
                if match:
                    years.add(int(match.group(1)))

        if not years:
            raise DownloadError(
                f"{description}: brak typow obiektow LIDAR — "
                "wynik bylby niepelny, ponow pobranie"
            )

        return sorted(years, reverse=True)

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
    ) -> list[LazTile]:
        """
        Discover the LAZ tiles to download for ``bbox`` (sorted by godlo).

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
        campaigns: str = "newest",
        min_year: int | None = None,
    ) -> LazTileSelection:
        """
        Query WFS for tiles intersecting ``bbox`` and pick those to download.

        Every available year (or only ``year``) is queried; tiles below
        ``min_density`` are dropped first. The rest is chosen greedily by
        :func:`select_newest_cover`: from the newest year, a tile is skipped
        when its overlap with ``bbox`` is already covered by the tiles chosen
        before it (in EPSG:2180, edges with ``tolerance_m``), so one place
        does not get both a 2022/PL-2000 and a 2025/PL-1992 tile. With
        ``year`` the same rule deduplicates within that year only.

        Parameters
        ----------
        bbox : BBox
            Area of interest in EPSG:2180.
        year : int, optional
            Restrict to a single acquisition year.
        min_density : int, optional
            Drop tiles whose nominal point density is below this value
            (points/m²) — before the coverage rule.
        vertical_crs : str, optional
            Override the default height system for this query.
        timeout : int, optional
            Per-request timeout for WFS calls.
        tolerance_m : float, optional
            Edge tolerance of the coverage rule (default
            ``COVERAGE_TOLERANCE_M`` = 1 m; ``0`` = exact).
        campaigns : {"newest", "all"}
            ``"newest"`` (default) — the rule above (ADR-029); ``"all"`` —
            every tile intersecting ``bbox`` (:func:`select_all_intersecting`),
            no coverage-based skipping (ADR-030).
        min_year : int, optional
            Lower bound of ``akt_rok``: year layers below it are not queried.
            Exclusive with ``year``.

        Returns
        -------
        LazTileSelection
            ``tiles`` to download (sorted by godlo) and ``superseded`` —
            skipped tiles with the tiles covering them.

        Raises
        ------
        ValueError
            If ``bbox`` is not in EPSG:2180.
        ValidationError
            Unknown ``campaigns``, invalid ``min_year`` (not an int, bool,
            outside 1900..2100) or ``year`` together with ``min_year``.
        DownloadError
            If WFS discovery fails, returns unreadable XML or an exception,
            or all returned tiles miss the requested bbox. Partial results
            are never returned.
        """
        # local import: the kartograf.download package imports manager -> providers.pl
        from kartograf.download.campaigns import validate_campaign_args

        validate_campaign_args(campaigns, min_year)
        if year is not None and min_year is not None:
            raise ValidationError("year i min_year wykluczaja sie")
        if bbox.crs != "EPSG:2180":
            raise ValueError(
                f"bbox must be in EPSG:2180, got {bbox.crs}. "
                f"Transform it first (e.g. SheetParser.get_bbox(crs='EPSG:2180'))."
            )

        vcrs = vertical_crs or self._vertical_crs
        if vcrs not in self.SUPPORTED_VERTICAL_CRS:
            raise ValueError(
                f"Unsupported vertical_crs: '{vcrs}'. "
                f"Supported: {self.SUPPORTED_VERTICAL_CRS}"
            )

        available_years = self._get_available_years(vcrs, timeout)
        if year is not None and year not in available_years:
            raise DownloadError(
                f"rocznik {year} nie istnieje w usludze {vcrs} "
                f"(dostepne: {', '.join(map(str, available_years))})"
            )
        years = [year] if year is not None else available_years
        if min_year is not None:
            years = [y for y in years if y >= min_year]
        endpoint = self.WFS_ENDPOINTS[vcrs]

        found: list[LazTile] = []
        for yr in years:
            for tile in self._query_layer(endpoint, yr, bbox, timeout):
                if min_density is not None and (
                    tile.density is None or tile.density < min_density
                ):
                    continue
                found.append(tile)

        if campaigns == "all":
            return select_all_intersecting(found, bbox)
        return select_newest_cover(found, bbox, tolerance_m)

    def _query_layer(
        self,
        endpoint: str,
        year: int,
        bbox: BBox,
        timeout: int,
    ):
        """Yield tiles from one year-layer, following WFS pagination."""
        layer = f"{self.LAYER_PREFIX}{year}"
        # The URN uses EPSG:2180 axis order (Northing, Easting), while BBox
        # stores (Easting, Northing).
        bbox_param = (
            f"{bbox.min_y},{bbox.min_x},{bbox.max_y},{bbox.max_x},"
            "urn:ogc:def:crs:EPSG::2180"
        )
        start = 0
        while True:
            params = {
                "SERVICE": "WFS",
                "VERSION": "2.0.0",
                "REQUEST": "GetFeature",
                "TYPENAMES": f"gugik:{layer}",
                "SRSNAME": "urn:ogc:def:crs:EPSG::2180",
                "COUNT": str(self.PAGE_SIZE),
                "STARTINDEX": str(start),
                "BBOX": bbox_param,
            }
            url = f"{endpoint}?{urlencode(params)}"
            root = self._get_wfs_xml(
                url, timeout, f"WFS GetFeature dla rocznika {year} ({layer})"
            )

            returned = kept = 0
            for tile in self._parse_features(root):
                returned += 1
                if self._intersects(tile, bbox):
                    kept += 1
                    yield tile
            if returned and not kept:
                raise DownloadError(
                    f"WFS {layer}: serwer zwrocil {returned} kafli, zaden nie "
                    "przecina zadanego bboxa — niezgodnosc kolejnosci osi "
                    "(zglos blad)"
                )

            # numberReturned is reliable; fall back to the counted features
            number_returned = root.get("numberReturned")
            page_count = (
                int(number_returned)
                if number_returned and number_returned.isdigit()
                else returned
            )
            if page_count < self.PAGE_SIZE:
                break
            start += self.PAGE_SIZE

    def _parse_features(self, root: ET.Element):
        """Yield LazTile for each WFS feature member in the collection."""
        prefix = f"{{{_GUGIK_NS}}}"
        for elem in root.iter():
            if elem.tag.startswith(prefix) and _localname(elem.tag).startswith(
                self.LAYER_PREFIX
            ):
                tile = self._feature_to_tile(elem)
                if tile is not None:
                    yield tile

    def _feature_to_tile(self, elem: ET.Element) -> LazTile | None:
        """Convert one WFS feature element into a LazTile (None if no URL)."""

        def text(name: str) -> str | None:
            child = elem.find(f"{{{_GUGIK_NS}}}{name}")
            if child is not None and child.text:
                return child.text.strip()
            return None

        url = text("url_do_pobrania")
        godlo = text("godlo")
        if not url or not godlo:
            return None
        crs = text("uklad_xy")
        if parse_pl_uklad(crs) is None:
            # D3: the same parser as the index and the sidecar — a tile without
            # a recognized CRS is skipped (like an index record) rather than
            # guessed from the godlo (pl_2000 segment + EPSG:2180 sidecar)
            logger.warning(f"Kafel {godlo}: nierozpoznany uklad_xy {crs!r} — pominiety")
            return None

        year_text = text("akt_rok")
        year = int(year_text) if year_text and year_text.isdigit() else None

        density = None
        density_text = text("char_przestrz")
        if density_text:
            match = re.search(r"(\d+)", density_text)
            if match:
                density = int(match.group(1))

        lower = upper = None
        for env in elem.iter(f"{{{_GML_NS}}}Envelope"):
            srs_name = env.get("srsName")
            lc = env.find(f"{{{_GML_NS}}}lowerCorner")
            uc = env.find(f"{{{_GML_NS}}}upperCorner")
            if lc is not None and lc.text:
                lower = _corner_xy(lc.text, srs_name)
            if uc is not None and uc.text:
                upper = _corner_xy(uc.text, srs_name)
            break

        if lower is not None and upper is not None:
            min_x, min_y = lower
            max_x, max_y = upper
        else:
            min_x = min_y = max_x = max_y = math.nan

        full_text = text("czy_ark_wypelniony")
        full_sheet = {"TAK": True, "NIE": False}.get((full_text or "").upper())

        return LazTile(
            godlo=godlo,
            url=url,
            year=year,
            density=density,
            crs=crs,
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y,
            footprint=_footprint(elem),
            date=_time_position(elem, "akt_data"),
            full_sheet=full_sheet,
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

    def download(
        self,
        url: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download a single LAZ tile from its OpenData URL.

        Note
        ----
        Unlike the other providers, the first argument is the tile's download
        URL (obtained from :meth:`discover_tiles`), not a godlo — LAZ tiles are
        identified by opaque finer-than-1:10000 ids that are not parseable.

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


def _localname(tag: str) -> str:
    """Return the local name of a possibly namespaced XML tag."""
    return tag.rsplit("}", 1)[-1]


def _corner_xy(text: str, srs_name: str | None) -> tuple[float, float]:
    """Convert an EPSG:2180 envelope corner to (Easting, Northing)."""
    first, second = (float(value) for value in text.split()[:2])
    if srs_name == "EPSG:2180":
        return first, second
    # URN/URI identifiers use EPSG axis order; missing srsName inherits the
    # requested URN. Only the legacy short identifier uses (E, N).
    return second, first


def _footprint(feature: ET.Element) -> tuple[tuple[float, float], ...] | None:
    """
    Tile frame from ``gugik:msGeometry`` as a convex (E, N) polygon, or None.

    Only a single ``gml:Polygon`` without holes: other geometry (multi,
    holes, concave polygon) gives ``None`` and the tile covers no others
    (the caution rule of tile selection). Axes as in ``_corner_xy``:
    URN/missing ``srsName`` = (N, E), short ``EPSG:2180`` = (E, N).
    """
    geometry = feature.find(f"{{{_GUGIK_NS}}}msGeometry")
    if geometry is None:
        return None
    polygons = list(geometry.iter(f"{{{_GML_NS}}}Polygon"))
    if len(polygons) != 1 or polygons[0].find(f"{{{_GML_NS}}}interior") is not None:
        return None
    polygon = polygons[0]
    pos_list = polygon.find(
        f"{{{_GML_NS}}}exterior/{{{_GML_NS}}}LinearRing/{{{_GML_NS}}}posList"
    )
    if pos_list is None or not pos_list.text:
        return None
    try:
        values = [float(v) for v in pos_list.text.split()]
    except ValueError:
        return None
    if len(values) % 2:
        return None
    srs_name = polygon.get("srsName")
    points = [
        _corner_xy(f"{values[i]} {values[i + 1]}", srs_name)
        for i in range(0, len(values), 2)
    ]
    return normalize_convex(points)


def _time_position(feature: ET.Element, name: str) -> str | None:
    """Text of the ``gml:timePosition`` of a time attribute (e.g. ``akt_data``)."""
    elem = feature.find(f"{{{_GUGIK_NS}}}{name}")
    if elem is None:
        return None
    for child in elem.iter(f"{{{_GML_NS}}}timePosition"):
        if child.text:
            return child.text.strip()
    return elem.text.strip() if elem.text and elem.text.strip() else None
