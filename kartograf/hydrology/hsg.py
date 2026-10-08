"""
Hydrologic Soil Group (HSG) calculation from soil texture data.

This module provides functions to:
1. Classify soil texture according to USDA texture triangle
2. Map texture classes to Hydrologic Soil Groups (A, B, C, D)
3. Process SoilGrids raster data to produce HSG maps

Texture -> HSG mapping (TEXTURE_TO_HSG) deliberately deviates from the TR-55
table for sandy_loam (B, not A) and clay_loam / silty_clay_loam (C, not D) -
see docs/DECISIONS.md ADR-025.

Reference:
- USDA-NRCS National Engineering Handbook, Part 630, Chapter 7
- SCS-CN method for runoff estimation
"""

import logging
import tempfile
from collections.abc import Callable
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


# Canonical USDA texture triangle (Soil Survey Manual) - the SINGLE source of
# truth for both the scalar and the vectorised classifier.  Each predicate gets
# float64 arrays with clay/sand/silt in percent (already normalised to sum 100)
# and returns a boolean mask.  Order matters: first matching rule wins.
_USDA_RULES: tuple[
    tuple[str, Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]], ...
] = (
    ("sand", lambda c, s, si: si + 1.5 * c < 15),
    ("loamy_sand", lambda c, s, si: (si + 1.5 * c >= 15) & (si + 2 * c < 30)),
    (
        "sandy_loam",
        lambda c, s, si: (
            ((c >= 7) & (c <= 20) & (s > 52) & (si + 2 * c >= 30))
            | ((c < 7) & (si < 50) & (si + 2 * c >= 30))
        ),
    ),
    ("silt", lambda c, s, si: (si >= 80) & (c < 12)),
    (
        "silt_loam",
        lambda c, s, si: (
            ((si >= 50) & (c >= 12) & (c < 27)) | ((si >= 50) & (si < 80) & (c < 12))
        ),
    ),
    (
        "loam",
        lambda c, s, si: (c >= 7) & (c <= 27) & (si >= 28) & (si < 50) & (s <= 52),
    ),
    ("sandy_clay_loam", lambda c, s, si: (c >= 20) & (c < 35) & (si < 28) & (s > 45)),
    ("clay_loam", lambda c, s, si: (c >= 27) & (c < 40) & (s > 20) & (s <= 45)),
    ("silty_clay_loam", lambda c, s, si: (c >= 27) & (c < 40) & (s <= 20)),
    ("sandy_clay", lambda c, s, si: (c >= 35) & (s > 45)),
    ("silty_clay", lambda c, s, si: (c >= 40) & (si >= 40)),
    ("clay", lambda c, s, si: (c >= 40) & (s <= 45) & (si < 40)),
)


def _normalize_pct(
    clay, sand, silt
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Normalise clay/sand/silt to percentages summing to 100 (float64).

    Returns the three normalised arrays plus the raw total, so callers can tell
    apart real soil from the "no input at all" case (total == 0).
    """
    clay = np.asarray(clay, dtype=np.float64)
    sand = np.asarray(sand, dtype=np.float64)
    silt = np.asarray(silt, dtype=np.float64)

    total = clay + sand + silt
    valid = total > 0

    normalised = tuple(
        np.divide(part, total, out=np.zeros_like(part), where=valid) * 100
        for part in (clay, sand, silt)
    )

    return normalised[0], normalised[1], normalised[2], total


def classify_usda_texture(clay: float, sand: float, silt: float) -> str:
    """
    Classify soil texture according to the USDA texture triangle.

    Canonical USDA texture triangle (Soil Survey Manual), single rule list
    shared with the vectorised variant.

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
    Inputs are normalised to sum to 100% before classification, so any
    consistent unit works (e.g. g/kg).  Inputs summing to 0 (no data) return
    "loam".
    """
    code = int(
        classify_usda_texture_array(
            np.array([clay]), np.array([sand]), np.array([silt])
        )[0]
    )
    return TEXTURE_NAMES[code]


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

    Uses the same canonical rule list (`_USDA_RULES`) as the scalar
    `classify_usda_texture`, evaluated in float64.

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
        Array of texture class codes (1-12); cells whose inputs sum to 0
        (no data) get "loam".
    """
    clay_n, sand_n, silt_n, total = _normalize_pct(clay, sand, silt)

    masks = [rule(clay_n, sand_n, silt_n) for _, rule in _USDA_RULES]
    codes = [TEXTURE_CLASSES[name] for name, _ in _USDA_RULES]

    selected = np.select(masks, codes, default=TEXTURE_CLASSES["loam"])

    # The rules partition the whole simplex, but cells with a zero total are
    # not soil at all - pin them to "loam" explicitly instead of letting the
    # normalised zeros fall into the "sand" rule.
    return np.where(total > 0, selected, TEXTURE_CLASSES["loam"]).astype(np.uint8)


def _nodata_mask(arr: np.ndarray, nodata: float | None) -> np.ndarray:
    """
    Boolean mask of cells that carry no usable value.

    Covers NaN/Inf (which survive any arithmetic and would otherwise be
    classified as soil) plus the raster's own nodata tag, when it has one.
    """
    mask = ~np.isfinite(arr)
    if nodata is not None:
        mask |= arr == nodata
    return mask


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


def _geographic_row_cell_areas(src) -> np.ndarray:
    """
    Geodetic area (m2) of one cell in every row of a geographic raster.

    For a CRS in degrees the affine determinant is square degrees, not square
    metres.  Cell area on the ellipsoid depends on latitude only (all cells in
    a row are congruent), so one polygon per row is enough.

    Parameters
    ----------
    src : rasterio.DatasetReader
        Open raster whose CRS is geographic.

    Returns
    -------
    np.ndarray
        Array of shape (height,) with the area in m2 of a single cell in
        each row, top row first.
    """
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    areas = np.empty(src.height, dtype=np.float64)

    for row in range(src.height):
        lon0, top = src.transform * (0, row)
        lon1, bottom = src.transform * (1, row + 1)
        area, _ = geod.polygon_area_perimeter(
            [lon0, lon1, lon1, lon0], [bottom, bottom, top, top]
        )
        areas[row] = abs(area)

    return areas


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
        Calculate HSG raster for a map sheet (sheet code).

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
            # Canonical sheet code in the sidecar, as for NMT and land cover (A7)
            sheet=parser.godlo,
        )

    def calculate_hsg_by_bbox(
        self,
        bbox,
        output_path: Path,
        depth: str = "0-5cm",
        stat: str = "mean",
        keep_intermediate: bool = False,
        timeout: int = 120,
        sheet: str | None = None,
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
        sheet : str, optional
            Sheet code the bbox was derived from; recorded in the sidecar as
            ``request.sheet`` (set by :meth:`calculate_hsg_by_godlo`)

        Returns
        -------
        Path
            Path to the output HSG GeoTIFF
        """
        import rasterio

        output_path = Path(output_path)

        # Use temporary directory for intermediate files
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)

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
                clay_nd = clay_src.nodata
                profile = clay_src.profile.copy()

            with rasterio.open(sand_path) as sand_src:
                sand = sand_src.read(1).astype(np.float32)
                sand_nd = sand_src.nodata

            with rasterio.open(silt_path) as silt_src:
                silt = silt_src.read(1).astype(np.float32)
                silt_nd = silt_src.nodata

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

            # Handle nodata.  Computed from the RAW source values (before the
            # g/kg -> % conversion), because the classifier falls back to
            # "loam" for anything it cannot place - so the absence of data has
            # to be detected here, not inferred from the result.
            nodata_mask = (
                _nodata_mask(clay, clay_nd)
                | _nodata_mask(sand, sand_nd)
                | _nodata_mask(silt, silt_nd)
            )
            # Legacy convention: SoilGrids leaves gaps as all-zero triplets.
            nodata_mask |= (clay == 0) & (sand == 0) & (silt == 0)
            hsg[nodata_mask] = 0

            # Write output
            logger.info(f"Writing HSG raster to {output_path}...")

            profile.update(
                dtype=rasterio.uint8,
                count=1,
                nodata=0,
                compress="deflate",
            )

            hsg_crs = profile.get("crs")
            # Create the output directory only now, right before writing, so a
            # failed download leaves no empty directory behind.
            output_path.parent.mkdir(parents=True, exist_ok=True)
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

        self._write_sidecar(output_path, bbox, depth, stat, hsg_crs, sheet)

        logger.info(f"HSG calculation complete: {output_path}")
        return output_path

    @staticmethod
    def _write_sidecar(
        output_path: Path,
        bbox,
        depth: str,
        stat: str,
        crs,
        sheet: str | None = None,
    ) -> None:
        """Best-effort sidecar of the result (computed from SoilGrids layers)."""
        from kartograf.sources.sidecar import emit_sidecar

        request: dict = {
            "bbox": [bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y],
            "bbox_crs": getattr(bbox, "crs", None),
        }
        if sheet is not None:
            # The user asked for a sheet code; the bbox is derived from it.
            request["sheet"] = sheet

        emit_sidecar(
            "global.isric.soilgrids",
            output_path,
            request=request,
            horizontal_crs=str(crs) if crs else None,
            capability="bbox_raster",
            nodata=0,
            extra={
                "derived": "hsg",
                "source_layers": ["clay", "sand", "silt"],
                "depth": depth,
                "stat": stat,
                "classes": "1=A, 2=B, 3=C, 4=D",
            },
        )

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
            Per-group dict with keys: count, area_m2, area_ha, percent,
            description.

        Notes
        -----
        Areas are in square metres / hectares regardless of the raster CRS:
        for a geographic CRS (SoilGrids output is EPSG:4326) cell areas are
        computed geodetically per raster row, not from the affine
        determinant, which would give square degrees.
        """
        import rasterio

        with rasterio.open(hsg_path) as src:
            hsg = src.read(1)
            if src.crs is not None and src.crs.is_geographic:
                # transform[0]*transform[4] would be square DEGREES here
                row_area = _geographic_row_cell_areas(src)
            else:
                row_area = np.full(
                    src.height, abs(src.transform[0] * src.transform[4])
                )  # m²

        # Count pixels for each HSG
        total_valid = np.sum(hsg > 0)
        stats = {}

        for name, value in HSG_VALUES.items():
            per_row = np.sum(hsg == value, axis=1)
            count = np.sum(per_row)
            area_m2 = float(np.sum(per_row * row_area))
            pct = (count / total_valid * 100) if total_valid > 0 else 0

            stats[name] = {
                "count": int(count),
                "area_m2": float(area_m2),
                "area_ha": float(area_m2 / 10000),
                "percent": float(pct),
                "description": HSG_DESCRIPTIONS[name],
            }

        return stats
