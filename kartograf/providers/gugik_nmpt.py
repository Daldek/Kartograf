"""
GUGiK provider for downloading NMPT (Digital Surface Model) data.

This module provides the GugikNmptProvider class for downloading
NMPT data from the Polish GUGiK services.

NMPT includes terrain AND surface objects (buildings, trees) — unlike NMT
which is bare-earth only.

Uses the same mechanisms as NMT (WMS skorowidze → OpenData ASC, WCS → GeoTIFF)
but with different endpoints and coverage IDs.

Supported resolutions:
- 1m only (no 5m for NMPT)
"""

from kartograf.providers.gugik import GugikProvider


class GugikNmptProvider(GugikProvider):
    """
    Provider for downloading NMPT (Digital Surface Model) data from GUGiK.

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

    # WMS endpoints for NMPT skorowidze (1m only)
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

    # NMPT layers (ordered newest to oldest)
    WMS_LAYERS = {
        "1m": {
            "KRON86": [
                "SkorowidzeNMPT2019",
                "SkorowidzeNMPT2018",
                "SkorowidzeNMPT2017iStarsze",
            ],
            "EVRF2007": [
                "SkorowidzeNMPT2025",
                "SkorowidzeNMPT2024",
                "SkorowidzeNMPT2023",
                "SkorowidzeNMPT2022iStarsze",
            ],
        },
    }

    # NMPT coverage IDs for WCS
    COVERAGE_IDS = {
        "KRON86": "DSM_PL-KRON86-NH",
        "EVRF2007": "DSM_PL-EVRF2007-NH",
    }

    # Only 1m vertical CRS supported
    SUPPORTED_VERTICAL_CRS_5M: list[str] = []  # no 5m at all

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
