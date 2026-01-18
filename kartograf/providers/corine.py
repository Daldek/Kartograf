"""
CORINE Land Cover provider for downloading land cover data.

This module provides the CorineProvider class for downloading
CORINE Land Cover data from the Copernicus Land Monitoring Service
and Polish GIOŚ (Główny Inspektorat Ochrony Środowiska) services.

CORINE Land Cover is a pan-European land cover inventory with 44
thematic classes, available for years: 1990, 2000, 2006, 2012, 2018.

Data sources:
- GIOŚ WMS: http://mapy.gios.gov.pl/arcgis/services/WMS/CLC_2018/MapServer/WMSServer
- Copernicus: https://land.copernicus.eu/en/products/corine-land-cover
"""

import logging
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError
from kartograf.providers.landcover_base import LandCoverProvider

logger = logging.getLogger(__name__)


class CorineProvider(LandCoverProvider):
    """
    Provider for downloading CORINE Land Cover data.

    CORINE (Coordination of Information on the Environment) Land Cover
    is a standardized European land cover classification system with
    44 classes. Data is available at 100m resolution.

    Supports two download modes:
    - By bbox: downloads data via WMS/WCS service
    - By godło: converts to bbox and downloads via WMS/WCS

    TERYT downloads are NOT supported (use bbox or godło instead).

    Available years: 1990, 2000, 2006, 2012, 2018

    Examples
    --------
    >>> provider = CorineProvider()
    >>>
    >>> # Download by bbox
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_by_bbox(bbox, Path("./data/area.tif"), year=2018)
    >>>
    >>> # Download by godło
    >>> provider.download_by_godlo("N-34-130-D", Path("./data/sheet.tif"), year=2018)
    """

    # GIOŚ WMS base URL and endpoints by year
    GIOS_WMS_BASE = "http://mapy.gios.gov.pl/arcgis/services/WMS"
    GIOS_WMS_ENDPOINTS = {
        2018: f"{GIOS_WMS_BASE}/CLC_2018/MapServer/WMSServer",
        2012: f"{GIOS_WMS_BASE}/CLC_2012/MapServer/WMSServer",
        2006: f"{GIOS_WMS_BASE}/CLC_2006/MapServer/WMSServer",
        2000: f"{GIOS_WMS_BASE}/CLC_2000/MapServer/WMSServer",
        1990: f"{GIOS_WMS_BASE}/CLC_1990/MapServer/WMSServer",
    }

    # Available years
    AVAILABLE_YEARS = [2018, 2012, 2006, 2000, 1990]

    # WMS layer names for different years at GIOŚ
    WMS_LAYERS = {
        2018: "0",  # CLC 2018
        2012: "0",  # CLC 2012
        2006: "0",  # CLC 2006
        2000: "0",  # CLC 2000
        1990: "0",  # CLC 1990
    }

    # Default settings
    DEFAULT_TIMEOUT = 60
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2
    DEFAULT_YEAR = 2018

    # Output format settings
    WMS_FORMAT = "image/png"
    WMS_DPI = 96
    WMS_RESOLUTION = 100  # meters per pixel (CLC native resolution)

    def __init__(self, session: Optional[requests.Session] = None):
        """
        Initialize CORINE provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        """
        self._session = session

    @property
    def name(self) -> str:
        """Return provider name."""
        return "CORINE Land Cover"

    @property
    def source_url(self) -> str:
        """Return source URL."""
        return "https://land.copernicus.eu/en/products/corine-land-cover"

    # =========================================================================
    # Download by bbox → WMS
    # =========================================================================

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        year: int = DEFAULT_YEAR,
        **kwargs,
    ) -> Path:
        """
        Download CORINE Land Cover data for a bounding box via WMS.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)
        year : int, optional
            Reference year: 1990, 2000, 2006, 2012, or 2018 (default: 2018)
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        ValueError
            If bbox CRS is not EPSG:2180 or year is invalid
        DownloadError
            If the download fails
        """
        if bbox.crs != "EPSG:2180":
            raise ValueError(
                f"BBox must be in EPSG:2180, got {bbox.crs}. "
                f"Use SheetParser.get_bbox(crs='EPSG:2180') to convert."
            )

        if year not in self.AVAILABLE_YEARS:
            raise ValueError(
                f"Invalid year: {year}. " f"Available years: {self.AVAILABLE_YEARS}"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Calculate image dimensions based on bbox size and resolution
        width_m = bbox.max_x - bbox.min_x
        height_m = bbox.max_y - bbox.min_y
        width_px = max(1, int(width_m / self.WMS_RESOLUTION))
        height_px = max(1, int(height_m / self.WMS_RESOLUTION))

        # Limit max size to prevent huge requests
        max_size = 4096
        if width_px > max_size:
            width_px = max_size
        if height_px > max_size:
            height_px = max_size

        url = self._construct_wms_url(bbox, year, width_px, height_px)

        return self._download_with_retry(
            url=url,
            output_path=output_path.with_suffix(".png"),
            timeout=timeout,
            description=(
                f"CLC {year} for bbox "
                f"({bbox.min_x:.0f},{bbox.min_y:.0f})-"
                f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
            ),
        )

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        year: int = DEFAULT_YEAR,
        **kwargs,
    ) -> Path:
        """
        Download CORINE Land Cover data for a map sheet (godło).

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)
        year : int, optional
            Reference year: 1990, 2000, 2006, 2012, or 2018 (default: 2018)
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded file
        """
        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(godlo)
        bbox = parser.get_bbox(crs="EPSG:2180")

        return self.download_by_bbox(
            bbox=bbox,
            output_path=output_path,
            timeout=timeout,
            year=year,
            **kwargs,
        )

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path,
        timeout: int = 120,
        **kwargs,
    ) -> Path:
        """
        CORINE does not support TERYT downloads.

        Raises
        ------
        NotImplementedError
            Always raised - use download_by_bbox or download_by_godlo instead
        """
        raise NotImplementedError(
            "CORINE Land Cover does not support TERYT downloads. "
            "Use download_by_bbox() or download_by_godlo() instead."
        )

    def _construct_wms_url(
        self,
        bbox: BBox,
        year: int,
        width: int,
        height: int,
    ) -> str:
        """
        Construct WMS GetMap URL.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180
        year : int
            Reference year
        width : int
            Image width in pixels
        height : int
            Image height in pixels

        Returns
        -------
        str
            Full WMS URL
        """
        endpoint = self.GIOS_WMS_ENDPOINTS[year]
        layer = self.WMS_LAYERS[year]

        # WMS 1.3.0 with EPSG:2180 uses y,x order for BBOX
        wms_bbox = f"{bbox.min_y},{bbox.min_x},{bbox.max_y},{bbox.max_x}"

        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": layer,
            "STYLES": "",
            "CRS": "EPSG:2180",
            "BBOX": wms_bbox,
            "WIDTH": width,
            "HEIGHT": height,
            "FORMAT": self.WMS_FORMAT,
            "DPI": self.WMS_DPI,
            "TRANSPARENT": "TRUE",
        }

        return f"{endpoint}?{urlencode(params)}"

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
        last_error = None
        session = self._session or requests.Session()

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(
                    f"Downloading {description} (attempt {attempt}/{self.MAX_RETRIES})"
                )

                response = session.get(url, timeout=timeout, stream=True)
                response.raise_for_status()

                # Check if response is actually an image
                content_type = response.headers.get("Content-Type", "")
                if "xml" in content_type.lower() or "html" in content_type.lower():
                    # WMS error response
                    error_text = response.text[:500]
                    raise DownloadError(f"WMS returned error response: {error_text}")

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
            f"Failed to download {description} after {self.MAX_RETRIES} attempts: "
            f"{last_error}",
        )

    def _save_response(self, response: requests.Response, output_path: Path) -> None:
        """Save HTTP response to file atomically."""
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

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
        Return list of available CORINE classes.

        Returns list of year strings as "layers" since CORINE
        provides different datasets per year.
        """
        return [f"CLC_{year}" for year in self.AVAILABLE_YEARS]

    def get_available_years(self) -> list[int]:
        """Return list of available reference years."""
        return self.AVAILABLE_YEARS.copy()

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return ["PNG", "GTiff"]

    def get_clc_classes(self) -> dict[str, str]:
        """
        Return CORINE Land Cover classification.

        Returns
        -------
        dict[str, str]
            Dictionary mapping class codes to descriptions
        """
        return {
            # Level 1: Artificial surfaces
            "111": "Continuous urban fabric",
            "112": "Discontinuous urban fabric",
            "121": "Industrial or commercial units",
            "122": "Road and rail networks",
            "123": "Port areas",
            "124": "Airports",
            "131": "Mineral extraction sites",
            "132": "Dump sites",
            "133": "Construction sites",
            "141": "Green urban areas",
            "142": "Sport and leisure facilities",
            # Level 1: Agricultural areas
            "211": "Non-irrigated arable land",
            "212": "Permanently irrigated land",
            "213": "Rice fields",
            "221": "Vineyards",
            "222": "Fruit trees and berry plantations",
            "223": "Olive groves",
            "231": "Pastures",
            "241": "Annual crops associated with permanent crops",
            "242": "Complex cultivation patterns",
            "243": "Agriculture with natural vegetation",
            "244": "Agro-forestry areas",
            # Level 1: Forest and semi-natural areas
            "311": "Broad-leaved forest",
            "312": "Coniferous forest",
            "313": "Mixed forest",
            "321": "Natural grasslands",
            "322": "Moors and heathland",
            "323": "Sclerophyllous vegetation",
            "324": "Transitional woodland-shrub",
            "331": "Beaches, dunes, sands",
            "332": "Bare rocks",
            "333": "Sparsely vegetated areas",
            "334": "Burnt areas",
            "335": "Glaciers and perpetual snow",
            # Level 1: Wetlands
            "411": "Inland marshes",
            "412": "Peat bogs",
            "421": "Salt marshes",
            "422": "Salines",
            "423": "Intertidal flats",
            # Level 1: Water bodies
            "511": "Water courses",
            "512": "Water bodies",
            "521": "Coastal lagoons",
            "522": "Estuaries",
            "523": "Sea and ocean",
        }
