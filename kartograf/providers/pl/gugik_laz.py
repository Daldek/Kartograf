"""
GUGiK provider for downloading LAZ point-cloud data.

This module provides the GugikLazProvider class for downloading airborne
laser scanning (ALS) point clouds — *dane pomiarowe LIDAR / chmury punktów* —
distributed by GUGiK as ``.laz`` files.

Unlike NMT / NMPT / Ortofoto (which discover OpenData URLs through WMS
``GetFeatureInfo``), LAZ tiles are discovered through a **WFS** ``GetFeature``
query. Each WFS feature already carries the full download URL
(``url_do_pobrania``) plus metadata, so no URL has to be constructed and the
fine tile godło never has to be parsed.

Key differences from the other GUGiK products:

- Discovery is **area-based**: a bbox (derived from a godło / ``--bbox`` /
  ``--geometry``) is sent to the WFS, which returns every LAZ tile intersecting
  it. GUGiK tiles LAZ far finer than 1:10000, so a single 1:10000 sheet maps to
  *many* LAZ tiles, each with its own (opaque) godło.
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
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# XML namespaces used in the WFS GML responses
_GUGIK_NS = "http://www.gugik.gov.pl"
_GML_NS = "http://www.opengis.net/gml/3.2"


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

    @property
    def filename(self) -> str:
        """Return the original OpenData file name (preserves density/seq id)."""
        return self.url.rstrip("/").rsplit("/", 1)[-1]


class GugikLazProvider(BaseProvider):
    """
    Provider for downloading LAZ point-cloud data from GUGiK via WFS.

    Discovery is area-based: :meth:`discover_tiles` queries the WFS skorowidze
    for every tile intersecting a bbox; :meth:`download` fetches a single tile
    by its URL. The fine tile godło is treated as an opaque label and is never
    passed to ``SheetParser``.

    Parameters
    ----------
    session : requests.Session, optional
        HTTP session for downloads. A dedicated session is always used for
        WFS metadata requests so it cannot interfere with mocked download
        sessions in tests.
    vertical_crs : str, optional
        Default height system: ``"EVRF2007"`` (current, default) or
        ``"KRON86"`` (legacy). Selects which WFS service is queried.
    cache : MetadataCache, optional
        Unused placeholder for API symmetry with the other providers.
    """

    BASE_URL = "https://mapy.geoportal.gov.pl"

    # WFS skorowidze services by height system (verified 2026-06-24).
    # The matching WMS services are 401-gated and unusable; WFS is open.
    WFS_ENDPOINTS = {
        "EVRF2007": f"{BASE_URL}/wss/service/PZGIK/"
        "DanePomiaroweLidarEVRF2007/WFS/Skorowidze",
        "KRON86": f"{BASE_URL}/wss/service/PZGIK/"
        "DanePomiaroweLidarKRON86/WFS/Skorowidze",
    }

    # Per-year feature types are named "<prefix><year>"
    LAYER_PREFIX = "SkorowidzDanychPomiarowychLIDAR"

    # Fallback year lists if WFS GetCapabilities is unreachable (newest first).
    # Verified via GetCapabilities 2026-06-24.
    FALLBACK_YEARS = {
        "EVRF2007": [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018],
        "KRON86": [2019, 2018, 2017, 2016, 2015, 2014, 2013, 2012, 2011, 2010],
    }

    SUPPORTED_VERTICAL_CRS = ["EVRF2007", "KRON86"]

    DEFAULT_TIMEOUT = 60  # LAZ files are large
    WFS_TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2
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
        self._session = session
        self._vertical_crs = vertical_crs
        self._cache = cache
        # In-memory cache of available years per height system
        self._available_years: dict[str, list[int]] = {}
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
        ValueError
            If no LIDAR feature types are found.
        requests.RequestException
            On network errors.
        """
        endpoint = self.WFS_ENDPOINTS[vertical_crs]
        # Dedicated session to avoid interfering with the download session
        session = requests.Session()
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetCapabilities",
        }
        response = session.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        years: set[int] = set()
        for elem in root.iter():
            if _localname(elem.tag) == "Name" and elem.text:
                match = re.search(rf"{self.LAYER_PREFIX}(\d{{4}})", elem.text)
                if match:
                    years.add(int(match.group(1)))

        if not years:
            raise ValueError("No LIDAR feature types found in GetCapabilities")

        return sorted(years, reverse=True)

    def _get_available_years(
        self, vertical_crs: str, timeout: int = WFS_TIMEOUT
    ) -> list[int]:
        """
        Get available years, fetched once per height system and cached.

        Falls back to :data:`FALLBACK_YEARS` on any error so discovery keeps
        working offline.
        """
        cached = self._available_years.get(vertical_crs)
        if cached is not None:
            return cached

        try:
            years = self._fetch_available_years(vertical_crs, timeout)
        except (requests.RequestException, ValueError, ET.ParseError) as e:
            logger.warning(
                "WFS GetCapabilities failed for %s (%s); using fallback years.",
                vertical_crs,
                e,
            )
            years = list(self.FALLBACK_YEARS[vertical_crs])

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
        Discover LAZ tiles intersecting ``bbox`` via WFS.

        Parameters
        ----------
        bbox : BBox
            Area of interest in EPSG:2180.
        year : int, optional
            Restrict to a single acquisition year. When omitted, all available
            years are queried and overlapping tiles are deduplicated keeping the
            newest ``akt_rok`` per godło.
        min_density : int, optional
            Drop tiles whose point density is below this value (points/m²).
        vertical_crs : str, optional
            Override the default height system for this query.
        timeout : int, optional
            Per-request timeout for WFS calls.

        Returns
        -------
        list[LazTile]
            Tiles intersecting the bbox, sorted by godło.

        Raises
        ------
        ValueError
            If ``bbox`` is not in EPSG:2180.
        """
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

        years = [year] if year is not None else self._get_available_years(vcrs, timeout)
        endpoint = self.WFS_ENDPOINTS[vcrs]
        session = self._session or requests.Session()

        # Deduplicate by godło, keeping the newest acquisition year
        best: dict[str, LazTile] = {}
        for yr in years:
            for tile in self._query_layer(session, endpoint, yr, bbox, timeout):
                if min_density is not None and (
                    tile.density is None or tile.density < min_density
                ):
                    continue
                existing = best.get(tile.godlo)
                if existing is None or (tile.year or 0) > (existing.year or 0):
                    best[tile.godlo] = tile

        return sorted(best.values(), key=lambda t: t.godlo)

    def _query_layer(
        self,
        session: requests.Session,
        endpoint: str,
        year: int,
        bbox: BBox,
        timeout: int,
    ):
        """Yield tiles from one year-layer, following WFS pagination."""
        layer = f"{self.LAYER_PREFIX}{year}"
        # WFS expects the bbox in the same axis order as Kartograf's BBox
        # (min_x, min_y, max_x, max_y) with the urn CRS appended; the returned
        # gml:Envelope corners are in that same (x, y) frame. Verified live.
        bbox_param = (
            f"{bbox.min_x},{bbox.min_y},{bbox.max_x},{bbox.max_y},"
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
            try:
                response = session.get(url, timeout=timeout)
                response.raise_for_status()
            except requests.RequestException as e:
                logger.warning("WFS GetFeature failed for %s: %s", layer, e)
                return

            try:
                root = ET.fromstring(response.text)
            except ET.ParseError as e:
                logger.warning("WFS response parse error for %s: %s", layer, e)
                return

            if _localname(root.tag) == "ExceptionReport":
                # Layer likely not present for this service/year — skip quietly
                logger.debug("WFS exception for %s (skipping)", layer)
                return

            returned = 0
            for tile in self._parse_features(root):
                returned += 1
                if self._intersects(tile, bbox):
                    yield tile

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
            lc = env.find(f"{{{_GML_NS}}}lowerCorner")
            uc = env.find(f"{{{_GML_NS}}}upperCorner")
            if lc is not None and lc.text:
                lower = tuple(float(v) for v in lc.text.split())
            if uc is not None and uc.text:
                upper = tuple(float(v) for v in uc.text.split())
            break

        if lower and upper and len(lower) == 2 and len(upper) == 2:
            min_x, min_y = lower
            max_x, max_y = upper
        else:
            min_x = min_y = max_x = max_y = math.nan

        return LazTile(
            godlo=godlo,
            url=url,
            year=year,
            density=density,
            crs=text("uklad_xy"),
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y,
        )

    @staticmethod
    def _intersects(tile: LazTile, bbox: BBox) -> bool:
        """
        Return True if the tile envelope intersects the query bbox.

        Acts as a client-side safety net against WFS axis-order quirks. Tiles
        without geometry (NaN extent) are kept rather than dropped.
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
        URL (obtained from :meth:`discover_tiles`), not a godło — LAZ tiles are
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
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return self._download_with_retry(
            url=url,
            output_path=output_path,
            timeout=timeout,
            description=output_path.name,
        )

    # =========================================================================
    # Common download utilities (mirrors GugikOrtoProvider)
    # =========================================================================

    def _download_with_retry(
        self,
        url: str,
        output_path: Path,
        timeout: int,
        description: str,
    ) -> Path:
        """Download a file with automatic retry on failure."""
        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(
                    f"Downloading {description} (attempt {attempt}/{self.MAX_RETRIES})"
                )
                response = self._make_request(url, timeout)
                self._save_response(response, output_path)
                logger.info(f"Successfully downloaded {description} to {output_path}")
                return output_path

            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    f"Download failed for {description} (attempt {attempt}): {e}"
                )
                if attempt < self.MAX_RETRIES:
                    wait_time = self.RETRY_BACKOFF_BASE**attempt
                    logger.debug(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

        raise DownloadError(
            f"Failed to download {description} after "
            f"{self.MAX_RETRIES} attempts: {last_error}",
        )

    def _make_request(self, url: str, timeout: int) -> requests.Response:
        """Make a streaming HTTP GET request."""
        session = self._session or requests.Session()
        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        return response

    def _save_response(self, response: requests.Response, output_path: Path) -> None:
        """
        Save an HTTP response to a file atomically.

        Uses a unique temp filename per process/thread to prevent collisions
        when multiple threads download concurrently.
        """
        thread_id = threading.current_thread().ident
        temp_suffix = f"{output_path.suffix}.{os.getpid()}_{thread_id}.tmp"
        temp_path = output_path.with_suffix(temp_suffix)

        try:
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            temp_path.rename(output_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise


def _localname(tag: str) -> str:
    """Return the local name of a possibly namespaced XML tag."""
    return tag.rsplit("}", 1)[-1]
