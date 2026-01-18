"""
Hydrologic Soil Group (HSG) calculation from soil texture data.

This module provides functions to:
1. Classify soil texture according to USDA texture triangle
2. Map texture classes to Hydrologic Soil Groups (A, B, C, D)
3. Process SoilGrids raster data to produce HSG maps

HSG Classification (USDA-NRCS):
- Group A: High infiltration rate (sand, loamy sand, sandy loam)
- Group B: Moderate infiltration rate (silt loam, loam)
- Group C: Slow infiltration rate (sandy clay loam)
- Group D: Very slow infiltration rate (clay loam, silty clay, clay)

Reference:
- USDA-NRCS National Engineering Handbook, Part 630, Chapter 7
- SCS-CN method for runoff estimation
"""

import logging
import tempfile
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


# USDA Soil Texture Classes
TEXTURE_CLASSES = {
    "sand": 1,
    "loamy_sand": 2,
    "sandy_loam": 3,
    "loam": 4,
    "silt_loam": 5,
    "silt": 6,
    "sandy_clay_loam": 7,
    "clay_loam": 8,
    "silty_clay_loam": 9,
    "sandy_clay": 10,
    "silty_clay": 11,
    "clay": 12,
}

# Reverse mapping for display
TEXTURE_NAMES = {v: k for k, v in TEXTURE_CLASSES.items()}

# Hydrologic Soil Groups
HSG_VALUES = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
}

# HSG Descriptions
HSG_DESCRIPTIONS = {
    "A": "High infiltration rate - sandy soils with low runoff potential",
    "B": "Moderate infiltration rate - loamy soils with moderate runoff",
    "C": "Slow infiltration rate - clay loam soils with high runoff",
    "D": "Very slow infiltration rate - clay soils with very high runoff",
}

# Mapping from USDA texture class to HSG
# Based on USDA-NRCS guidelines
TEXTURE_TO_HSG = {
    "sand": "A",
    "loamy_sand": "A",
    "sandy_loam": "B",  # Can be A/B depending on structure
    "loam": "B",
    "silt_loam": "B",
    "silt": "B",
    "sandy_clay_loam": "C",
    "clay_loam": "C",  # Can be C/D
    "silty_clay_loam": "C",
    "sandy_clay": "D",
    "silty_clay": "D",
    "clay": "D",
}


def classify_usda_texture(clay: float, sand: float, silt: float) -> str:
    """
    Classify soil texture according to USDA texture triangle.

    Parameters
    ----------
    clay : float
        Clay content in percent (0-100)
    sand : float
        Sand content in percent (0-100)
    silt : float
        Silt content in percent (0-100)

    Returns
    -------
    str
        USDA texture class name

    Notes
    -----
    The classification follows the standard USDA soil texture triangle.
    Input values should sum to approximately 100%.
    """
    # Normalize to ensure sum = 100
    total = clay + sand + silt
    if total > 0:
        clay = clay / total * 100
        sand = sand / total * 100
        silt = silt / total * 100

    # USDA Texture Triangle Classification
    # Order matters - check most restrictive classes first

    # Sand: clay <= 10%, sand >= 85%
    if clay <= 10 and sand >= 85:
        return "sand"

    # Loamy sand: clay <= 15%, sand 70-90%
    if clay <= 15 and sand >= 70:
        return "loamy_sand"

    # Silt: silt >= 80%, clay < 12%
    if silt >= 80 and clay < 12:
        return "silt"

    # Clay: clay >= 40%
    if clay >= 40:
        if silt >= 40:
            return "silty_clay"
        elif sand >= 45:
            return "sandy_clay"
        else:
            return "clay"

    # Sandy clay: clay 35-40%, sand >= 45%
    if clay >= 35 and sand >= 45:
        return "sandy_clay"

    # Silty clay: clay 40-60%, silt >= 40%
    if clay >= 40 and silt >= 40:
        return "silty_clay"

    # Sandy clay loam: clay 20-35%, sand >= 45%
    if clay >= 20 and clay < 35 and sand >= 45:
        return "sandy_clay_loam"

    # Clay loam: clay 27-40%, sand 20-45%
    if clay >= 27 and clay < 40 and sand >= 20 and sand <= 45:
        return "clay_loam"

    # Silty clay loam: clay 27-40%, sand < 20%
    if clay >= 27 and clay < 40 and sand < 20:
        return "silty_clay_loam"

    # Silt loam: silt >= 50% and clay < 27% (but not silt)
    if silt >= 50 and clay < 27:
        return "silt_loam"

    # Sandy loam: clay < 20%, sand >= 43%
    if clay < 20 and sand >= 43:
        return "sandy_loam"

    # Loam: clay 7-27%, sand 23-52%, silt 28-50%
    if clay >= 7 and clay < 27 and sand >= 23 and sand <= 52:
        return "loam"

    # Default to loam if classification is ambiguous
    return "loam"


def texture_to_hsg(texture_class: str) -> str:
    """
    Map USDA texture class to Hydrologic Soil Group.

    Parameters
    ----------
    texture_class : str
        USDA texture class name

    Returns
    -------
    str
        Hydrologic Soil Group (A, B, C, or D)
    """
    return TEXTURE_TO_HSG.get(texture_class, "B")


def classify_usda_texture_array(
    clay: np.ndarray, sand: np.ndarray, silt: np.ndarray
) -> np.ndarray:
    """
    Classify soil texture for arrays (vectorized).

    Parameters
    ----------
    clay : np.ndarray
        Clay content array in percent (0-100)
    sand : np.ndarray
        Sand content array in percent (0-100)
    silt : np.ndarray
        Silt content array in percent (0-100)

    Returns
    -------
    np.ndarray
        Array of texture class codes (1-12)
    """
    # Initialize with default (loam = 4)
    result = np.full_like(clay, TEXTURE_CLASSES["loam"], dtype=np.uint8)

    # Normalize
    total = clay + sand + silt
    valid = total > 0
    clay_n = np.where(valid, clay / total * 100, 0)
    sand_n = np.where(valid, sand / total * 100, 0)
    silt_n = np.where(valid, silt / total * 100, 0)

    # Classification rules - apply in reverse order (last overrides)
    # This mimics the scalar if-else chain

    # Loam (default, already set)

    # Sandy loam: clay < 20%, sand >= 43%
    mask = (clay_n < 20) & (sand_n >= 43)
    result[mask] = TEXTURE_CLASSES["sandy_loam"]

    # Silt loam: silt >= 50% and clay < 27%
    mask = (silt_n >= 50) & (clay_n < 27)
    result[mask] = TEXTURE_CLASSES["silt_loam"]

    # Silty clay loam: clay 27-40%, sand < 20%
    mask = (clay_n >= 27) & (clay_n < 40) & (sand_n < 20)
    result[mask] = TEXTURE_CLASSES["silty_clay_loam"]

    # Clay loam: clay 27-40%, sand 20-45%
    mask = (clay_n >= 27) & (clay_n < 40) & (sand_n >= 20) & (sand_n <= 45)
    result[mask] = TEXTURE_CLASSES["clay_loam"]

    # Sandy clay loam: clay 20-35%, sand >= 45%
    mask = (clay_n >= 20) & (clay_n < 35) & (sand_n >= 45)
    result[mask] = TEXTURE_CLASSES["sandy_clay_loam"]

    # Sandy clay: clay 35-40%, sand >= 45%
    mask = (clay_n >= 35) & (clay_n < 40) & (sand_n >= 45)
    result[mask] = TEXTURE_CLASSES["sandy_clay"]

    # Clay, silty clay, sandy clay for clay >= 40%
    mask = (clay_n >= 40) & (silt_n < 40) & (sand_n < 45)
    result[mask] = TEXTURE_CLASSES["clay"]

    mask = (clay_n >= 40) & (sand_n >= 45)
    result[mask] = TEXTURE_CLASSES["sandy_clay"]

    mask = (clay_n >= 40) & (silt_n >= 40)
    result[mask] = TEXTURE_CLASSES["silty_clay"]

    # Silt: silt >= 80%, clay < 12% (overrides silt_loam)
    mask = (silt_n >= 80) & (clay_n < 12)
    result[mask] = TEXTURE_CLASSES["silt"]

    # Loamy sand: clay <= 15%, sand >= 70% (overrides sandy_loam)
    mask = (clay_n <= 15) & (sand_n >= 70)
    result[mask] = TEXTURE_CLASSES["loamy_sand"]

    # Sand: clay <= 10%, sand >= 85% (overrides loamy_sand)
    mask = (clay_n <= 10) & (sand_n >= 85)
    result[mask] = TEXTURE_CLASSES["sand"]

    return result


def texture_to_hsg_array(texture: np.ndarray) -> np.ndarray:
    """
    Map texture class array to HSG array.

    Parameters
    ----------
    texture : np.ndarray
        Array of texture class codes (1-12)

    Returns
    -------
    np.ndarray
        Array of HSG codes (1-4 for A-D)
    """
    # Mapping array: texture code (1-12) -> HSG code (1-4)
    mapping = np.array(
        [
            0,  # 0 - no data
            1,  # 1 - sand -> A
            1,  # 2 - loamy_sand -> A
            2,  # 3 - sandy_loam -> B
            2,  # 4 - loam -> B
            2,  # 5 - silt_loam -> B
            2,  # 6 - silt -> B
            3,  # 7 - sandy_clay_loam -> C
            3,  # 8 - clay_loam -> C
            3,  # 9 - silty_clay_loam -> C
            4,  # 10 - sandy_clay -> D
            4,  # 11 - silty_clay -> D
            4,  # 12 - clay -> D
        ],
        dtype=np.uint8,
    )

    return mapping[texture]


class HSGCalculator:
    """
    Calculator for Hydrologic Soil Groups from SoilGrids data.

    This class downloads clay, sand, and silt data from SoilGrids,
    classifies the soil texture, and produces HSG rasters.

    Examples
    --------
    >>> from kartograf.hydrology import HSGCalculator
    >>> calc = HSGCalculator()
    >>> calc.calculate_hsg_by_godlo("N-34-130-D", Path("./hsg.tif"))
    """

    # SoilGrids conversion factors
    # Data is stored as g/kg, divide by 10 for percentage
    CONVERSION_FACTOR = 10.0

    def __init__(self, provider=None):
        """
        Initialize HSG calculator.

        Parameters
        ----------
        provider : SoilGridsProvider, optional
            Provider to use for downloading. Creates new one if not provided.
        """
        self._provider = provider

    @property
    def provider(self):
        """Lazy-load SoilGridsProvider."""
        if self._provider is None:
            from kartograf.providers.soilgrids import SoilGridsProvider

            self._provider = SoilGridsProvider()
        return self._provider

    def calculate_hsg_by_godlo(
        self,
        godlo: str,
        output_path: Path,
        depth: str = "0-5cm",
        stat: str = "mean",
        keep_intermediate: bool = False,
        timeout: int = 120,
    ) -> Path:
        """
        Calculate HSG raster for a map sheet (godło).

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D")
        output_path : Path
            Path for output HSG GeoTIFF
        depth : str, optional
            Depth interval (default: "0-5cm")
        stat : str, optional
            Statistic to use (default: "mean")
        keep_intermediate : bool, optional
            Keep intermediate clay/sand/silt files (default: False)
        timeout : int, optional
            Download timeout in seconds (default: 120)

        Returns
        -------
        Path
            Path to the output HSG GeoTIFF
        """
        from kartograf.core.sheet_parser import SheetParser

        parser = SheetParser(godlo)
        bbox = parser.get_bbox(crs="EPSG:2180")

        return self.calculate_hsg_by_bbox(
            bbox=bbox,
            output_path=output_path,
            depth=depth,
            stat=stat,
            keep_intermediate=keep_intermediate,
            timeout=timeout,
        )

    def calculate_hsg_by_bbox(
        self,
        bbox,
        output_path: Path,
        depth: str = "0-5cm",
        stat: str = "mean",
        keep_intermediate: bool = False,
        timeout: int = 120,
    ) -> Path:
        """
        Calculate HSG raster for a bounding box.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180
        output_path : Path
            Path for output HSG GeoTIFF
        depth : str, optional
            Depth interval (default: "0-5cm")
        stat : str, optional
            Statistic to use (default: "mean")
        keep_intermediate : bool, optional
            Keep intermediate clay/sand/silt files (default: False)
        timeout : int, optional
            Download timeout in seconds (default: 120)

        Returns
        -------
        Path
            Path to the output HSG GeoTIFF
        """
        import rasterio

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use temporary directory for intermediate files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Download clay, sand, silt
            logger.info("Downloading soil texture data from SoilGrids...")

            clay_path = tmpdir / "clay.tif"
            sand_path = tmpdir / "sand.tif"
            silt_path = tmpdir / "silt.tif"

            logger.info("  Downloading clay content...")
            self.provider.download_by_bbox(
                bbox,
                clay_path,
                timeout=timeout,
                property="clay",
                depth=depth,
                stat=stat,
            )

            logger.info("  Downloading sand content...")
            self.provider.download_by_bbox(
                bbox,
                sand_path,
                timeout=timeout,
                property="sand",
                depth=depth,
                stat=stat,
            )

            logger.info("  Downloading silt content...")
            self.provider.download_by_bbox(
                bbox,
                silt_path,
                timeout=timeout,
                property="silt",
                depth=depth,
                stat=stat,
            )

            # Read rasters
            logger.info("Processing texture data...")

            with rasterio.open(clay_path) as clay_src:
                clay = clay_src.read(1).astype(np.float32)
                profile = clay_src.profile.copy()

            with rasterio.open(sand_path) as sand_src:
                sand = sand_src.read(1).astype(np.float32)

            with rasterio.open(silt_path) as silt_src:
                silt = silt_src.read(1).astype(np.float32)

            # Convert from g/kg to percentage
            clay_pct = clay / self.CONVERSION_FACTOR
            sand_pct = sand / self.CONVERSION_FACTOR
            silt_pct = silt / self.CONVERSION_FACTOR

            # Classify texture
            logger.info("Classifying soil texture...")
            texture = classify_usda_texture_array(clay_pct, sand_pct, silt_pct)

            # Map to HSG
            logger.info("Mapping to Hydrologic Soil Groups...")
            hsg = texture_to_hsg_array(texture)

            # Handle nodata
            nodata_mask = (clay == 0) & (sand == 0) & (silt == 0)
            hsg[nodata_mask] = 0

            # Write output
            logger.info(f"Writing HSG raster to {output_path}...")

            profile.update(
                dtype=rasterio.uint8,
                count=1,
                nodata=0,
                compress="deflate",
            )

            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(hsg, 1)

                # Add descriptions
                dst.update_tags(
                    1,
                    LAYER_NAME="Hydrologic Soil Group",
                    LAYER_DESCRIPTION="HSG classification: 1=A, 2=B, 3=C, 4=D",
                )

            # Copy intermediate files if requested
            if keep_intermediate:
                import shutil

                out_dir = output_path.parent
                shutil.copy(clay_path, out_dir / "clay.tif")
                shutil.copy(sand_path, out_dir / "sand.tif")
                shutil.copy(silt_path, out_dir / "silt.tif")
                logger.info(f"Intermediate files saved to {out_dir}")

        logger.info(f"HSG calculation complete: {output_path}")
        return output_path

    def get_hsg_statistics(self, hsg_path: Path) -> dict:
        """
        Calculate statistics for an HSG raster.

        Parameters
        ----------
        hsg_path : Path
            Path to HSG GeoTIFF

        Returns
        -------
        dict
            Dictionary with HSG statistics
        """
        import rasterio

        with rasterio.open(hsg_path) as src:
            hsg = src.read(1)
            pixel_area = abs(src.transform[0] * src.transform[4])  # m²

        # Count pixels for each HSG
        total_valid = np.sum(hsg > 0)
        stats = {}

        for name, value in HSG_VALUES.items():
            count = np.sum(hsg == value)
            area_m2 = count * pixel_area
            pct = (count / total_valid * 100) if total_valid > 0 else 0

            stats[name] = {
                "count": int(count),
                "area_m2": float(area_m2),
                "area_ha": float(area_m2 / 10000),
                "percent": float(pct),
                "description": HSG_DESCRIPTIONS[name],
            }

        return stats
