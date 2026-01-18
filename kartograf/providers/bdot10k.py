"""
BDOT10k provider for downloading land cover data.

This module provides the Bdot10kProvider class for downloading
land cover data from the Polish BDOT10k database (Baza Danych
Obiektów Topograficznych) maintained by GUGiK.

BDOT10k contains land cover classes (PT - Pokrycie Terenu):
- PTLZ: Tereny leśne (forests)
- PTWP: Wody powierzchniowe (surface waters)
- PTRK: Roślinność krzewiasta (shrub vegetation)
- PTUT: Uprawy trwałe (permanent crops)
- PTGN: Grunty nieużytkowe (unused land)
- PTKM: Tereny komunikacyjne (transportation areas)
- PTPL: Place (squares/plazas)
- PTSO: Składowiska (landfills)
- PTWZ: Tereny zabagnione (wetlands)
"""

import logging
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.landcover_base import LandCoverProvider

logger = logging.getLogger(__name__)


# Mapping of województwo TERYT codes to names used in OpenData URLs
WOJEWODZTWO_NAMES = {
    "02": "dolnoslaskie",
    "04": "kujawsko-pomorskie",
    "06": "lubelskie",
    "08": "lubuskie",
    "10": "lodzkie",
    "12": "malopolskie",
    "14": "mazowieckie",
    "16": "opolskie",
    "18": "podkarpackie",
    "20": "podlaskie",
    "22": "pomorskie",
    "24": "slaskie",
    "26": "swietokrzyskie",
    "28": "warminsko-mazurskie",
    "30": "wielkopolskie",
    "32": "zachodniopomorskie",
}


class Bdot10kProvider(LandCoverProvider):
    """
    Provider for downloading land cover data from BDOT10k.

    BDOT10k (Baza Danych Obiektów Topograficznych 1:10000) is the Polish
    topographic database maintained by GUGiK. It contains detailed land
    cover information for the entire country.

    Supports three download modes:
    - By TERYT code: downloads pre-packaged county (powiat) data
    - By bbox: downloads data via WFS service
    - By godło: converts to bbox and downloads via WFS

    Examples
    --------
    >>> provider = Bdot10kProvider()
    >>>
    >>> # Download by TERYT (powiat code)
    >>> provider.download_by_teryt("1465", Path("./data/powiat_1465.gpkg"))
    >>>
    >>> # Download by bbox
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_by_bbox(bbox, Path("./data/area.gpkg"))
    >>>
    >>> # Download by godło
    >>> provider.download_by_godlo("N-34-130-D", Path("./data/sheet.gpkg"))
    """

    # OpenData base URLs for BDOT10k packages (schemat 2021)
    OPENDATA_URLS = {
        "GPKG": "https://opendata.geoportal.gov.pl/bdot10k/schemat2021/GPKG",
        "SHP": "https://opendata.geoportal.gov.pl/bdot10k/schemat2021/SHP",
        "GML": "https://opendata.geoportal.gov.pl/bdot10k/schemat2021",
    }

    # WFS endpoint for BDOT10k
    WFS_ENDPOINT = (
        "https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT/WFS/PobieranieBDOT10k"
    )

    # Land cover layer names in BDOT10k
    PT_LAYERS = [
        "PTLZ",  # Tereny leśne (forests)
        "PTWP",  # Wody powierzchniowe (surface waters)
        "PTRK",  # Roślinność krzewiasta (shrub vegetation)
        "PTUT",  # Uprawy trwałe (permanent crops)
        "PTGN",  # Grunty nieużytkowe (unused land)
        "PTKM",  # Tereny komunikacyjne (transportation)
        "PTPL",  # Place (squares/plazas)
        "PTSO",  # Składowiska (landfills)
        "PTWZ",  # Tereny zabagnione (wetlands)
    ]

    # Default settings
    DEFAULT_TIMEOUT = 60
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2

    def __init__(self, session: Optional[requests.Session] = None):
        """
        Initialize BDOT10k provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        """
        self._session = session

    @property
    def name(self) -> str:
        """Return provider name."""
        return "BDOT10k"

    @property
    def source_url(self) -> str:
        """Return source URL."""
        return "https://www.geoportal.gov.pl/dane/bdot10k"

    # =========================================================================
    # Download by TERYT → OpenData packages
    # =========================================================================

    def download_by_teryt(
        self,
        teryt: str,
        output_path: Path,
        timeout: int = 120,
        format: str = "GPKG",
        **kwargs,
    ) -> Path:
        """
        Download BDOT10k data package for a powiat (county) by TERYT code.

        Downloads pre-packaged data from OpenData. This is the fastest method
        for downloading large areas as files are pre-generated.

        Parameters
        ----------
        teryt : str
            4-digit TERYT code for powiat (e.g., "1465" for powiat
            warszawski zachodni)
        output_path : Path
            Path where the file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 120)
        format : str, optional
            Output format: "GPKG" or "SHP" (default: "GPKG")
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        ValidationError
            If TERYT code is invalid
        DownloadError
            If the download fails
        """
        if not self.validate_teryt(teryt):
            raise ValidationError(f"Invalid TERYT code: {teryt}")

        if format not in ["GPKG", "SHP"]:
            raise ValueError(f"Unsupported format: {format}. Use 'GPKG' or 'SHP'")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Construct OpenData URL
        url = self._construct_opendata_url(teryt, format)

        return self._download_with_retry(
            url=url,
            output_path=output_path,
            timeout=timeout,
            description=f"BDOT10k TERYT {teryt}",
            extract_from_zip=(format == "GPKG"),
        )

    def _construct_opendata_url(self, teryt: str, format: str) -> str:
        """
        Construct OpenData URL for BDOT10k package.

        URL pattern: .../bdot10k/schemat2021/{FORMAT}/{woj}/{teryt}.zip

        Parameters
        ----------
        teryt : str
            4-digit TERYT code
        format : str
            Output format (GPKG, SHP, or GML)

        Returns
        -------
        str
            Full OpenData URL
        """
        woj_code = teryt[:2]
        woj_name = WOJEWODZTWO_NAMES.get(woj_code)

        if not woj_name:
            raise ValidationError(
                f"Unknown województwo code: {woj_code}. "
                f"Valid codes: {list(WOJEWODZTWO_NAMES.keys())}"
            )

        base_url = self.OPENDATA_URLS.get(format, self.OPENDATA_URLS["GPKG"])

        return f"{base_url}/{woj_name}/{teryt}.zip"

    # =========================================================================
    # Download by bbox → WFS
    # =========================================================================

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
        layers: Optional[list[str]] = None,
        **kwargs,
    ) -> Path:
        """
        Download BDOT10k land cover data for a bounding box via WFS.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the GML file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)
        layers : list[str], optional
            List of PT layers to download (default: all PT layers)
        **kwargs
            Additional options (unused)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        ValueError
            If bbox CRS is not EPSG:2180
        DownloadError
            If the download fails
        """
        if bbox.crs != "EPSG:2180":
            raise ValueError(
                f"BBox must be in EPSG:2180, got {bbox.crs}. "
                f"Use SheetParser.get_bbox(crs='EPSG:2180') to convert."
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use specified layers or default to all PT layers
        target_layers = layers or self.PT_LAYERS

        # Download each layer and combine
        all_data = []
        session = self._session or requests.Session()

        for layer in target_layers:
            try:
                url = self._construct_wfs_url(bbox, layer)
                logger.debug(f"Downloading WFS layer {layer}")

                response = session.get(url, timeout=timeout)
                response.raise_for_status()

                if response.content:
                    all_data.append((layer, response.content))

            except requests.RequestException as e:
                logger.warning(f"Failed to download layer {layer}: {e}")
                continue

        if not all_data:
            raise DownloadError(
                f"No data found for bbox "
                f"({bbox.min_x:.0f},{bbox.min_y:.0f})-"
                f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
            )

        # Save combined GML data
        self._save_wfs_response(all_data, output_path)

        logger.info(
            f"Downloaded {len(all_data)} layers for bbox "
            f"({bbox.min_x:.0f},{bbox.min_y:.0f})-"
            f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
        )

        return output_path

    def _construct_wfs_url(self, bbox: BBox, layer: str) -> str:
        """
        Construct WFS GetFeature URL.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180
        layer : str
            Layer name (e.g., "PTLZ")

        Returns
        -------
        str
            Full WFS URL
        """
        # WFS 2.0.0 BBOX filter
        bbox_filter = f"{bbox.min_x},{bbox.min_y},{bbox.max_x},{bbox.max_y},EPSG:2180"

        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": layer,
            "BBOX": bbox_filter,
            "OUTPUTFORMAT": "application/gml+xml; version=3.2",
        }

        return f"{self.WFS_ENDPOINT}?{urlencode(params)}"

    def _save_wfs_response(
        self, data: list[tuple[str, bytes]], output_path: Path
    ) -> None:
        """
        Save WFS response data to file.

        For simplicity, saves as GML. Each layer is saved separately
        with layer name as filename suffix.

        Parameters
        ----------
        data : list[tuple[str, bytes]]
            List of (layer_name, gml_content) tuples
        output_path : Path
            Base output path
        """
        if len(data) == 1:
            # Single layer - save directly
            layer_name, content = data[0]
            output_path = output_path.with_suffix(".gml")
            output_path.write_bytes(content)
        else:
            # Multiple layers - save each with suffix
            output_dir = output_path.parent
            base_name = output_path.stem

            for layer_name, content in data:
                layer_path = output_dir / f"{base_name}_{layer_name}.gml"
                layer_path.write_bytes(content)

    # =========================================================================
    # Common utilities
    # =========================================================================

    def _download_with_retry(
        self,
        url: str,
        output_path: Path,
        timeout: int,
        description: str,
        extract_from_zip: bool = False,
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
        extract_from_zip : bool, optional
            If True, extract GPKG from downloaded ZIP

        Returns
        -------
        Path
            Path to downloaded/extracted file

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

                if extract_from_zip:
                    self._extract_gpkg_from_zip(response, output_path)
                else:
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

    def _extract_gpkg_from_zip(
        self, response: requests.Response, output_path: Path
    ) -> None:
        """
        Extract GeoPackage file from downloaded ZIP.

        Parameters
        ----------
        response : requests.Response
            HTTP response with ZIP content
        output_path : Path
            Target path for extracted GPKG
        """
        # Read ZIP into memory
        zip_data = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            zip_data.write(chunk)
        zip_data.seek(0)

        try:
            with zipfile.ZipFile(zip_data, "r") as zf:
                # Find GPKG file in archive
                gpkg_files = [f for f in zf.namelist() if f.endswith(".gpkg")]

                if not gpkg_files:
                    # Try to find any usable file
                    all_files = zf.namelist()
                    raise DownloadError(
                        f"No GPKG file found in ZIP. Contents: {all_files}"
                    )

                # Extract first GPKG file
                gpkg_name = gpkg_files[0]
                logger.debug(f"Extracting {gpkg_name} from ZIP")

                # Extract to temp file then rename
                temp_path = output_path.with_suffix(".gpkg.tmp")
                try:
                    with zf.open(gpkg_name) as src, open(temp_path, "wb") as dst:
                        dst.write(src.read())
                    temp_path.rename(output_path.with_suffix(".gpkg"))
                except Exception:
                    if temp_path.exists():
                        temp_path.unlink()
                    raise

        except zipfile.BadZipFile as e:
            raise DownloadError(f"Invalid ZIP file: {e}")

    # =========================================================================
    # Info methods
    # =========================================================================

    def get_available_layers(self) -> list[str]:
        """Return list of available land cover layers."""
        return self.PT_LAYERS.copy()

    def get_supported_formats(self) -> list[str]:
        """Return list of supported output formats."""
        return ["GPKG", "SHP", "GML"]

    def get_layer_description(self, layer: str) -> str:
        """
        Get human-readable description for layer.

        Parameters
        ----------
        layer : str
            Layer code (e.g., "PTLZ")

        Returns
        -------
        str
            Layer description in Polish
        """
        descriptions = {
            "PTLZ": "Tereny leśne",
            "PTWP": "Wody powierzchniowe",
            "PTRK": "Roślinność krzewiasta",
            "PTUT": "Uprawy trwałe",
            "PTGN": "Grunty nieużytkowe",
            "PTKM": "Tereny komunikacyjne",
            "PTPL": "Place",
            "PTSO": "Składowiska",
            "PTWZ": "Tereny zabagnione",
        }
        return descriptions.get(layer, layer)
