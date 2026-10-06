"""
ISRIC SoilGrids provider for downloading soil property data.

This module provides the SoilGridsProvider class for downloading
soil property data from ISRIC SoilGrids via Web Coverage Service (WCS).

SoilGrids provides global soil information at 250m resolution:
- Soil texture (clay, sand, silt content)
- Soil organic carbon (SOC)
- pH, nitrogen, bulk density
- And more soil properties

Data source: https://soilgrids.org
WCS endpoint: https://maps.isric.org/mapserv

Available properties:
- bdod: Bulk density (kg/dm³)
- cec: Cation exchange capacity (cmol/kg)
- cfvo: Coarse fragments (%)
- clay: Clay content (%)
- nitrogen: Total nitrogen (g/kg)
- ocd: Organic carbon density (kg/m³)
- ocs: Organic carbon stock (t/ha)
- phh2o: pH in H2O
- sand: Sand content (%)
- silt: Silt content (%)
- soc: Soil organic carbon (g/kg)

Depth intervals: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
Statistics: mean, Q0.05, Q0.5, Q0.95, uncertainty
"""

import logging
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.base import LandCoverProvider
from kartograf.transport.http import (
    http_failure,
    http_status,
    is_retryable,
    retry_wait,
)

logger = logging.getLogger(__name__)


# Soil property descriptions
PROPERTY_DESCRIPTIONS = {
    "bdod": "Bulk density (kg/dm³)",
    "cec": "Cation exchange capacity (cmol/kg)",
    "cfvo": "Coarse fragments (%)",
    "clay": "Clay content (%)",
    "nitrogen": "Total nitrogen (g/kg)",
    "ocd": "Organic carbon density (kg/m³)",
    "ocs": "Organic carbon stock (t/ha)",
    "phh2o": "pH in H2O",
    "sand": "Sand content (%)",
    "silt": "Silt content (%)",
    "soc": "Soil organic carbon (g/kg)",
}


class SoilGridsProvider(LandCoverProvider):
    """
    Provider for downloading soil data from ISRIC SoilGrids.

    SoilGrids is a global gridded soil information system providing
    predictions of soil properties at 250m resolution. Data is accessed
    via OGC Web Coverage Service (WCS).

    Supports two download modes:
    - By bbox: downloads data for specified bounding box
    - By godło: converts map sheet ID to bbox and downloads

    TERYT (administrative unit) selection is not supported - SoilGrids is a
    global raster service and has no notion of Polish administrative
    boundaries.

    Examples
    --------
    >>> provider = SoilGridsProvider()
    >>>
    >>> # Download soil organic carbon by bbox
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_by_bbox(
    ...     bbox, Path("./soc.tif"), property="soc", depth="0-5cm"
    ... )
    >>>
    >>> # Download clay content by godło
    >>> provider.download_by_godlo(
    ...     "N-34-130-D", Path("./clay.tif"), property="clay", depth="15-30cm"
    ... )
    """

    # WCS endpoint base URL
    WCS_BASE = "https://maps.isric.org/mapserv"

    # Available soil properties
    PROPERTIES = [
        "bdod",
        "cec",
        "cfvo",
        "clay",
        "nitrogen",
        "ocd",
        "ocs",
        "phh2o",
        "sand",
        "silt",
        "soc",
    ]

    # Available depth intervals
    DEPTHS = ["0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm"]

    # Available statistics
    STATS = ["mean", "Q0.05", "Q0.5", "Q0.95", "uncertainty"]

    # Default settings
    DEFAULT_TIMEOUT = 120
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2
    DEFAULT_PROPERTY = "soc"
    DEFAULT_DEPTH = "0-5cm"
    DEFAULT_STAT = "mean"

    def __init__(self, session: requests.Session | None = None, cache=None):
        """
        Initialize SoilGrids provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        cache : MetadataCache, optional
            Metadata cache instance. Currently unused for SoilGrids
            (WCS URLs are computed, not looked up), but accepted for
            API consistency with other providers.
        """
        self._session = session
        self._cache = cache
        self.descriptor_key = "global.isric.soilgrids"

    @property
    def name(self) -> str:
        """Return provider name."""
        return "SoilGrids"

    @property
    def base_url(self) -> str:
        """Return source URL."""
        return "https://soilgrids.org"

    # =========================================================================
    # Download by bbox → WCS
    # =========================================================================

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        property: str = DEFAULT_PROPERTY,
        depth: str = DEFAULT_DEPTH,
        stat: str = DEFAULT_STAT,
        **kwargs,
    ) -> Path:
        """
        Download soil property data for a bounding box via WCS.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the GeoTIFF should be saved
        timeout : int, optional
            Request timeout in seconds (default: 120)
        property : str, optional
            Soil property to download (default: "soc")
            Options: bdod, cec, cfvo, clay, nitrogen, ocd, ocs, phh2o, sand, silt, soc
        depth : str, optional
            Depth interval (default: "0-5cm")
            Options: 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
        stat : str, optional
            Statistic to download (default: "mean")
            Options: mean, Q0.05, Q0.5, Q0.95, uncertainty
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded GeoTIFF file

        Raises
        ------
        ValueError
            If bbox CRS is not EPSG:2180 or parameters are invalid
        DownloadError
            If the download fails
        """
        # Validate CRS
        if bbox.crs != "EPSG:2180":
            raise ValueError(
                f"BBox must be in EPSG:2180, got {bbox.crs}. "
                f"Use SheetParser.get_bbox(crs='EPSG:2180') to convert."
            )

        # Validate property
        if property not in self.PROPERTIES:
            raise ValueError(
                f"Invalid property: {property}. Available: {', '.join(self.PROPERTIES)}"
            )

        # Validate depth
        if depth not in self.DEPTHS:
            raise ValueError(
                f"Invalid depth: {depth}. Available: {', '.join(self.DEPTHS)}"
            )

        # Validate stat
        if stat not in self.STATS:
            raise ValueError(
                f"Invalid stat: {stat}. Available: {', '.join(self.STATS)}"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Transform bbox to WGS84 for WCS
        bbox_wgs84 = self._transform_bbox_to_wgs84(bbox)

        # Download via WCS
        return self._download_via_wcs(
            bbox_wgs84=bbox_wgs84,
            output_path=output_path,
            property=property,
            depth=depth,
            stat=stat,
            timeout=timeout,
        )

    def _transform_bbox_to_wgs84(self, bbox: BBox) -> tuple[float, float, float, float]:
        """
        Transform EPSG:2180 bounding box to WGS84 (EPSG:4326).

        Envelope of the whole rectangle (edges densified), not just two
        corners: the EPSG:2180 grid is rotated against the meridians, so
        the SW/NE pair alone cuts off the north and south strips.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180

        Returns
        -------
        tuple
            (min_lon, min_lat, max_lon, max_lat) in WGS84
        """
        from pyproj import Transformer

        transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

        return transformer.transform_bounds(
            bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y, densify_pts=21
        )

    def _download_via_wcs(
        self,
        bbox_wgs84: tuple[float, float, float, float],
        output_path: Path,
        property: str,
        depth: str,
        stat: str,
        timeout: int,
    ) -> Path:
        """
        Download GeoTIFF via WCS GetCoverage request.

        Parameters
        ----------
        bbox_wgs84 : tuple
            (min_lon, min_lat, max_lon, max_lat) in WGS84
        output_path : Path
            Target path for GeoTIFF
        property : str
            Soil property code
        depth : str
            Depth interval
        stat : str
            Statistic type
        timeout : int
            Request timeout

        Returns
        -------
        Path
            Path to downloaded GeoTIFF
        """
        url = self._construct_wcs_url(bbox_wgs84, property, depth, stat)

        description = f"SoilGrids {property} {depth} {stat}"
        logger.info(f"Downloading {description} via WCS...")

        return self._download_with_retry(
            url=url,
            output_path=output_path.with_suffix(".tif"),
            timeout=timeout,
            description=description,
        )

    def _construct_wcs_url(
        self,
        bbox_wgs84: tuple[float, float, float, float],
        property: str,
        depth: str,
        stat: str,
    ) -> str:
        """
        Construct WCS GetCoverage URL.

        Coverage ID format: {property}_{depth}_{stat}
        Example: soc_0-5cm_mean

        Parameters
        ----------
        bbox_wgs84 : tuple
            (min_lon, min_lat, max_lon, max_lat)
        property : str
            Soil property code
        depth : str
            Depth interval
        stat : str
            Statistic type

        Returns
        -------
        str
            Full WCS URL
        """
        min_lon, min_lat, max_lon, max_lat = bbox_wgs84

        # Coverage ID format for SoilGrids
        coverage_id = f"{property}_{depth}_{stat}"

        # WCS 2.0.1 GetCoverage request
        # Note: SoilGrids uses specific URL format with map parameter
        base_url = f"{self.WCS_BASE}?map=/map/{property}.map"

        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": coverage_id,
            "FORMAT": "image/tiff",
            "SUBSETTINGCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
            "OUTPUTCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
        }

        # Build URL with SUBSET parameters (must be separate for X and Y)
        url = f"{base_url}&{urlencode(params)}"
        url += f"&SUBSET=long({min_lon},{max_lon})"
        url += f"&SUBSET=lat({min_lat},{max_lat})"

        logger.debug(f"WCS URL: {url}")
        return url

    # =========================================================================
    # Download by TERYT
    # =========================================================================

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        **kwargs,
    ) -> Path:
        """
        SoilGrids does not support TERYT (administrative unit) selection.

        Raises NotImplementedError always. Earlier versions silently returned
        data for a fixed 60x60 km square around a hardcoded wojewodztwo
        centre, which had nothing to do with the requested powiat.

        Raises
        ------
        NotImplementedError
            Always - use download_by_bbox() or download_by_godlo() instead
        """
        raise NotImplementedError(
            "SoilGrids does not support TERYT selection - use --bbox or "
            "--godlo (download_by_bbox / download_by_godlo)"
        )

    # =========================================================================
    # Common utilities
    # =========================================================================

    def _download_with_retry(
        self,
        url: str,
        output_path: Path,
        timeout: int,
        description: str,
    ) -> Path:
        """
        Download file with automatic retry on failure.

        Parameters
        ----------
        url : str
            URL to download
        output_path : Path
            Target path
        timeout : int
            Request timeout
        description : str
            Description for logging

        Returns
        -------
        Path
            Path to downloaded file

        Raises
        ------
        DownloadError
            If download fails after all retries
        """
        last_error: requests.RequestException | None = None
        session = self._session or requests.Session()

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(
                    f"Downloading {description} (attempt {attempt}/{self.MAX_RETRIES})"
                )

                response = session.get(url, timeout=timeout, stream=True)
                response.raise_for_status()

                # Check if response is actually a TIFF
                content_type = response.headers.get("Content-Type", "")
                if "xml" in content_type.lower() or "html" in content_type.lower():
                    # WCS error response
                    error_text = response.text[:500]
                    raise DownloadError(f"WCS returned error response: {error_text}")

                self._save_response(response, output_path)

                logger.info(f"Successfully downloaded {description} to {output_path}")
                return output_path

            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    f"Download failed for {description} (attempt {attempt}): {e}"
                )

                if not is_retryable(e):
                    raise http_failure(
                        f"Failed to download {description}: "
                        f"HTTP {http_status(e)} (not retried): {e}",
                        e,
                    ) from e

                if attempt < self.MAX_RETRIES:
                    wait_time = retry_wait(e, self.RETRY_BACKOFF_BASE**attempt)
                    logger.debug(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

        raise http_failure(
            f"Failed to download {description} after {self.MAX_RETRIES} attempts: "
            f"{last_error}",
            last_error,
        )

    def _save_response(self, response: requests.Response, output_path: Path) -> None:
        """
        Save HTTP response to file atomically.

        Uses a unique temp filename per process/thread to prevent
        collisions when multiple threads download concurrently.
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

    # =========================================================================
    # Info methods
    # =========================================================================

    def get_available_layers(self) -> list[str]:
        """
        Return list of available soil properties.

        Returns
        -------
        list[str]
            List of property codes
        """
        return self.PROPERTIES.copy()

    def get_available_properties(self) -> list[str]:
        """
        Return list of available soil properties (alias for get_available_layers).

        Returns
        -------
        list[str]
            List of property codes
        """
        return self.PROPERTIES.copy()

    def get_available_depths(self) -> list[str]:
        """
        Return list of available depth intervals.

        Returns
        -------
        list[str]
            List of depth intervals
        """
        return self.DEPTHS.copy()

    def get_available_stats(self) -> list[str]:
        """
        Return list of available statistics.

        Returns
        -------
        list[str]
            List of statistic types
        """
        return self.STATS.copy()

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return ["GTiff"]

    def get_property_description(self, property: str) -> str:
        """
        Get human-readable description for a soil property.

        Parameters
        ----------
        property : str
            Property code (e.g., "soc")

        Returns
        -------
        str
            Property description
        """
        return PROPERTY_DESCRIPTIONS.get(property, property)
