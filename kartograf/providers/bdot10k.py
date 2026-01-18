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

    # OpenData base URL for BDOT10k packages
    OPENDATA_BASE = "https://opendata.geoportal.gov.pl/bdot10k"

    # URL patterns for different formats (schemat 2021)
    # Pattern: {base}/schemat2021/{subdir}/{woj_code}/{teryt}_{suffix}.zip
    OPENDATA_PATTERNS = {
        "GPKG": "{base}/schemat2021/GPKG/{woj}/{teryt}_GPKG.zip",
        "SHP": "{base}/schemat2021/SHP/{woj}/{teryt}_SHP.zip",
        "GML": "{base}/schemat2021/{woj}/{teryt}_GML.zip",
    }

    # WMS endpoint for BDOT10k downloads (used to get OpenData URLs)
    WMS_ENDPOINT = (
        "https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT/WMS/PobieranieBDOT10k"
    )

    # Land cover layer names in BDOT10k
    PT_LAYERS = [
        "PTGN",  # Grunty nieużytkowe (unused land)
        "PTKM",  # Tereny komunikacyjne (transportation)
        "PTLZ",  # Tereny leśne (forests)
        "PTNZ",  # Tereny niezabudowane (unbuilt areas)
        "PTPL",  # Place (squares/plazas)
        "PTRK",  # Roślinność krzewiasta (shrub vegetation)
        "PTSO",  # Składowiska (landfills)
        "PTTR",  # Tereny rolne (agricultural land)
        "PTUT",  # Uprawy trwałe (permanent crops)
        "PTWP",  # Wody powierzchniowe (surface waters)
        "PTWZ",  # Tereny zabagnione (wetlands)
        "PTZB",  # Tereny zabudowane (built-up areas)
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

        URL pattern: .../bdot10k/schemat2021/{subdir}/{woj}/{teryt}_{suffix}.zip

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

        if woj_code not in WOJEWODZTWO_NAMES:
            raise ValidationError(
                f"Unknown województwo code: {woj_code}. "
                f"Valid codes: {list(WOJEWODZTWO_NAMES.keys())}"
            )

        pattern = self.OPENDATA_PATTERNS.get(format, self.OPENDATA_PATTERNS["GPKG"])

        return pattern.format(base=self.OPENDATA_BASE, woj=woj_code, teryt=teryt)

    # =========================================================================
    # Download by godło → OpenData (via TERYT lookup)
    # =========================================================================

    def download_by_godlo(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = 120,
        format: str = "GPKG",
        **kwargs,
    ) -> Path:
        """
        Download BDOT10k data for a map sheet (godło).

        Finds the powiat (county) TERYT code for the given godło
        and downloads the entire county package. This is the recommended
        method as it provides complete data coverage.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D")
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
        """
        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(godlo)
        bbox = parser.get_bbox(crs="EPSG:2180")

        # Get center point of the map sheet
        center_x = (bbox.min_x + bbox.max_x) / 2
        center_y = (bbox.min_y + bbox.max_y) / 2

        # Find TERYT code for this location via WMS GetFeatureInfo
        teryt = self._get_teryt_for_point(center_x, center_y, timeout)

        logger.info(f"Godło {godlo} is in powiat {teryt}, downloading county package")

        # Download the entire county package
        return self.download_by_teryt(teryt, output_path, timeout, format=format)

    def _get_teryt_for_point(
        self,
        x: float,
        y: float,
        timeout: int = 30,
    ) -> str:
        """
        Get powiat TERYT code for a point using WMS GetFeatureInfo.

        Parameters
        ----------
        x : float
            X coordinate in EPSG:2180
        y : float
            Y coordinate in EPSG:2180
        timeout : int
            Request timeout

        Returns
        -------
        str
            4-digit TERYT code for the powiat

        Raises
        ------
        DownloadError
            If TERYT code cannot be determined
        """
        import re

        session = self._session or requests.Session()

        # Create small bbox around the point
        buffer = 100  # meters
        # WMS 1.3.0 with EPSG:2180 uses y,x order
        query_bbox = f"{y - buffer},{x - buffer},{y + buffer},{x + buffer}"

        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetFeatureInfo",
            "LAYERS": "Powiaty",
            "QUERY_LAYERS": "Powiaty",
            "INFO_FORMAT": "text/html",
            "CRS": "EPSG:2180",
            "BBOX": query_bbox,
            "WIDTH": 100,
            "HEIGHT": 100,
            "I": 50,
            "J": 50,
        }

        from urllib.parse import urlencode

        url = f"{self.WMS_ENDPOINT}?{urlencode(params)}"
        logger.debug(f"Querying WMS for TERYT at ({x:.2f}, {y:.2f})")

        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()

            # Extract TERYT from GPKG URL pattern: .../GPKG/{woj}/{teryt}_GPKG.zip
            gpkg_pattern = r"/GPKG/\d{2}/(\d{4})_GPKG\.zip"
            match = re.search(gpkg_pattern, response.text)

            if match:
                teryt = match.group(1)
                logger.debug(f"Found TERYT: {teryt}")
                return teryt

            # Alternative: extract from SHP URL pattern
            shp_pattern = r"/SHP/\d{2}/(\d{4})_SHP\.zip"
            match = re.search(shp_pattern, response.text)

            if match:
                teryt = match.group(1)
                logger.debug(f"Found TERYT: {teryt}")
                return teryt

            raise DownloadError(
                f"Could not determine TERYT for point ({x:.2f}, {y:.2f}). "
                f"The location may be outside Poland or in a water body."
            )

        except requests.RequestException as e:
            raise DownloadError(f"WMS GetFeatureInfo failed: {e}")

    # =========================================================================
    # Download by bbox → Download county package
    # =========================================================================

    def download_by_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        timeout: int = 120,
        format: str = "GPKG",
        **kwargs,
    ) -> Path:
        """
        Download BDOT10k land cover data for a bounding box.

        Finds the powiat (county) containing the center of the bbox
        and downloads the entire county package. This provides complete
        data coverage for the area.

        Note: The returned data covers the entire county, not just the bbox.
        Use GIS software to clip to the exact bbox if needed.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
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

        # Get center point of the bbox
        center_x = (bbox.min_x + bbox.max_x) / 2
        center_y = (bbox.min_y + bbox.max_y) / 2

        # Find TERYT code for this location
        teryt = self._get_teryt_for_point(center_x, center_y, timeout)

        logger.info(f"Bbox center is in powiat {teryt}, downloading county package")

        # Download the entire county package
        return self.download_by_teryt(teryt, output_path, timeout, format=format)

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
        Extract and merge land cover (PT*) layers from downloaded ZIP.

        BDOT10k packages contain separate GPKG files for each layer.
        This method extracts only PT* (land cover) layers and merges
        them into a single GeoPackage file.

        Parameters
        ----------
        response : requests.Response
            HTTP response with ZIP content
        output_path : Path
            Target path for merged GPKG
        """
        import sqlite3
        import tempfile
        import shutil

        # Read ZIP into memory
        zip_data = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            zip_data.write(chunk)
        zip_data.seek(0)

        try:
            with zipfile.ZipFile(zip_data, "r") as zf:
                # Find PT* (land cover) GPKG files in archive
                all_gpkg = [f for f in zf.namelist() if f.endswith(".gpkg")]
                pt_gpkg = [f for f in all_gpkg if "_PT" in f.upper()]

                if not pt_gpkg:
                    # Fallback: if no PT* layers, check for any GPKG
                    if not all_gpkg:
                        raise DownloadError(
                            f"No GPKG files found in ZIP. Contents: {zf.namelist()}"
                        )
                    # Use all GPKG files if no PT* specific ones
                    pt_gpkg = all_gpkg
                    logger.warning(
                        f"No PT* layers found, extracting all {len(all_gpkg)} layers"
                    )

                logger.debug(f"Found {len(pt_gpkg)} PT* layers to merge")

                # Create temp directory for extraction
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)

                    # Extract PT* files
                    extracted_files = []
                    for gpkg_file in pt_gpkg:
                        # Extract to temp directory
                        extracted_path = tmpdir_path / Path(gpkg_file).name
                        with zf.open(gpkg_file) as src:
                            with open(extracted_path, "wb") as dst:
                                dst.write(src.read())
                        extracted_files.append(extracted_path)
                        logger.debug(f"Extracted {Path(gpkg_file).name}")

                    # Merge all PT* files into single GPKG
                    output_gpkg = output_path.with_suffix(".gpkg")
                    self._merge_gpkg_files(extracted_files, output_gpkg)

        except zipfile.BadZipFile as e:
            raise DownloadError(f"Invalid ZIP file: {e}")

    def _merge_gpkg_files(self, source_files: list[Path], output_path: Path) -> None:
        """
        Merge multiple GeoPackage files into one.

        Each source file is expected to have a single data table.
        All tables are copied to the output file, preserving geometry.

        Parameters
        ----------
        source_files : list[Path]
            List of source GPKG files to merge
        output_path : Path
            Output merged GPKG file
        """
        import sqlite3

        if not source_files:
            raise DownloadError("No files to merge")

        temp_path = output_path.with_suffix(".gpkg.tmp")

        try:
            # Copy first file as base (includes GPKG metadata structure)
            first_file = source_files[0]
            with open(first_file, "rb") as src, open(temp_path, "wb") as dst:
                dst.write(src.read())

            logger.debug(f"Using {first_file.name} as base GPKG")

            # Merge remaining files
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()

            for source_file in source_files[1:]:
                self._copy_gpkg_layer(cursor, source_file)

            conn.commit()
            conn.close()

            # Atomic rename
            temp_path.rename(output_path)
            logger.info(f"Merged {len(source_files)} layers into {output_path}")

        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _copy_gpkg_layer(self, cursor, source_path: Path) -> None:
        """
        Copy a layer from source GPKG to destination (via cursor).

        Parameters
        ----------
        cursor : sqlite3.Cursor
            Cursor to destination database
        source_path : Path
            Source GPKG file
        """
        import sqlite3

        # Attach source database
        cursor.execute(f"ATTACH DATABASE '{source_path}' AS src")

        try:
            # Get data table name (exclude gpkg_* and rtree_* tables)
            cursor.execute(
                """
                SELECT name FROM src.sqlite_master
                WHERE type='table'
                AND name NOT LIKE 'gpkg_%'
                AND name NOT LIKE 'rtree_%'
                AND name NOT LIKE 'sqlite_%'
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

            for table_name in tables:
                # Check if table already exists in destination
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                if cursor.fetchone():
                    logger.debug(f"Table {table_name} already exists, skipping")
                    continue

                # Get table schema from source
                cursor.execute(
                    f"SELECT sql FROM src.sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                create_sql = cursor.fetchone()[0]

                # Create table in destination
                cursor.execute(create_sql)

                # Copy data
                cursor.execute(
                    f"INSERT INTO {table_name} SELECT * FROM src.{table_name}"
                )

                # Copy gpkg_contents entry
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO gpkg_contents
                    SELECT * FROM src.gpkg_contents WHERE table_name=?
                    """,
                    (table_name,),
                )

                # Copy gpkg_geometry_columns entry
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO gpkg_geometry_columns
                    SELECT * FROM src.gpkg_geometry_columns WHERE table_name=?
                    """,
                    (table_name,),
                )

                logger.debug(f"Copied layer {table_name}")

            # Commit before detaching to release locks
            cursor.connection.commit()

        finally:
            cursor.execute("DETACH DATABASE src")

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
            "PTGN": "Grunty nieużytkowe",
            "PTKM": "Tereny komunikacyjne",
            "PTLZ": "Tereny leśne",
            "PTNZ": "Tereny niezabudowane",
            "PTPL": "Place",
            "PTRK": "Roślinność krzewiasta",
            "PTSO": "Składowiska",
            "PTTR": "Tereny rolne",
            "PTUT": "Uprawy trwałe",
            "PTWP": "Wody powierzchniowe",
            "PTWZ": "Tereny zabagnione",
            "PTZB": "Tereny zabudowane",
        }
        return descriptions.get(layer, layer)
