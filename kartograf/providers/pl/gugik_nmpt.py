"""
GUGiK provider for downloading Digital Surface Model (NMPT) data.

This module provides the GugikNmptProvider class for downloading
NMPT data from the Polish GUGiK services.

NMPT includes terrain AND surface objects (buildings, trees) — unlike NMT
which is bare-earth only.

Uses the same mechanisms as NMT (WMS indexes (skorowidze) → OpenData ASC,
WCS → GeoTIFF float32 1 m, heights requested as image/x-aaigrid) but with
different endpoints and coverage IDs.

Supported resolutions:
- 1m only (no 5m for NMPT)
"""

import re

from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.wcs import HEIGHT_AAIGRID
from kartograf.transport.chunks import GridSpec


class GugikNmptProvider(GugikProvider):
    """
    Provider for downloading Digital Surface Model (NMPT) data from GUGiK.

    Inherits all download logic from GugikProvider, overriding only
    the endpoints, layer names, and coverage IDs for NMPT.

    Supports two vertical coordinate systems:
    - EVRF2007 (default) - European Vertical Reference Frame 2007
    - KRON86 - legacy Kronsztadt 86

    Only 1m resolution is available for NMPT.

    Examples
    --------
    >>> provider = GugikNmptProvider()
    >>> provider.download("N-34-130-D-d-2-4", Path("./sheet.asc"))
    >>>
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_bbox(bbox, Path("./area.tif"))
    """

    # NMPT supports only 1m resolution
    SUPPORTED_RESOLUTIONS = ["1m"]

    # Single WCS endpoint for NMPT (same for both vertical CRS)
    WCS_ENDPOINTS = {
        "KRON86": (
            "https://mapy.geoportal.gov.pl"
            "/wss/service/PZGIK/NMPT/GRID1/WCS/DigitalSurfaceModel"
        ),
        "EVRF2007": (
            "https://mapy.geoportal.gov.pl"
            "/wss/service/PZGIK/NMPT/GRID1/WCS/DigitalSurfaceModel"
        ),
    }

    # WMS endpoints for NMPT indexes (1m only)
    WMS_SKOROWIDZE_ENDPOINTS = {
        "1m": {
            "KRON86": (
                "https://mapy.geoportal.gov.pl"
                "/wss/service/PZGIK/NMPT/WMS/SkorowidzeUkladKRON86"
            ),
            "EVRF2007": (
                "https://mapy.geoportal.gov.pl"
                "/wss/service/PZGIK/NMPT/WMS/SkorowidzeUkladEVRF2007"
            ),
        },
    }

    LAYER_PATTERN = re.compile(r"^SkorowidzeNMPT(\d{4})(iStarsze)?$")
    LAYER_FAMILY = re.compile(r"^SkorowidzeNMPT")

    # NMPT coverage IDs for WCS
    COVERAGE_IDS = {
        "KRON86": "DSM_PL-KRON86-NH",
        "EVRF2007": "DSM_PL-EVRF2007-NH",
    }

    # Only 1m vertical CRS supported
    SUPPORTED_VERTICAL_CRS_5M: list[str] = []  # no 5m at all

    # The NMPT image/tiff is 3-band uint8 RGB, not heights: heights come only as
    # image/x-aaigrid. The coverage step is 0.5 m; the result is 1 m on the 1 m
    # sheet grid via SCALEFACTOR=0.5 - bit for bit the 1 m NMPT sheets and an
    # exact decimation of 0.5 m content (pixel centred on a whole metre), no
    # averaging (docs/research/2026-10-11-wcs-cutouts/raport.md, point 3).
    WCS_HEIGHT_FORMAT = {"KRON86": HEIGHT_AAIGRID, "EVRF2007": HEIGHT_AAIGRID}
    WCS_GRID = GridSpec(step=1.0, origin_x=0.5, origin_y=0.5)
    WCS_NATIVE_STEP = 0.5

    # Product identifier for cache key (overrides GugikProvider's "nmt")
    _CACHE_PRODUCT = "nmpt"

    @property
    def name(self) -> str:
        """Return provider name."""
        return "GUGiK NMPT"

    def __init__(self, session=None, vertical_crs="EVRF2007", cache=None):
        """
        Initialize GUGiK NMPT provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        vertical_crs : str, optional
            Vertical CRS: "KRON86" or "EVRF2007" (default: "EVRF2007").
        cache : MetadataCache, optional
            Metadata cache instance for caching WMS lookup results.
            If None, no caching is performed (default behavior).
        """
        super().__init__(
            session=session, vertical_crs=vertical_crs, resolution="1m", cache=cache
        )
        self.descriptor_key = "pl.gugik.nmpt"
