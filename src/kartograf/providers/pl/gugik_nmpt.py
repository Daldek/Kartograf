"""
GUGiK provider for downloading Digital Surface Model (NMPT) data.

NMPT includes terrain AND surface objects (buildings, trees) - unlike NMT
which is bare-earth only.

Uses the same mechanisms as NMT (WFS sheet index -> OpenData file, WCS ->
GeoTIFF float32 1 m, heights requested as image/x-aaigrid) with its own
index services, endpoints and coverage IDs. The variants (0.5m, 0.6m, 1m
grids, XYZ archives in KRON86) come from the registry
(``kartograf.sources.variants``).
"""

from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.wcs import HEIGHT_AAIGRID
from kartograf.transport.chunks import ChunkLimits, GridSpec


class GugikNmptProvider(GugikProvider):
    """
    Provider of one NMPT variant from GUGiK (sheets from the WFS index, WCS 1 m).

    Inherits the download logic from GugikProvider; ``resolution`` is
    required (0.5m, 0.6m, 1m grids - 0.8.0: no default), WCS bbox downloads
    exist only for the 1m grid.

    Examples
    --------
    >>> provider = GugikNmptProvider(vertical_crs="EVRF2007", resolution="0.5m")
    >>> provider.download("N-33-58-A-d-1-2", Path("./sheet.asc"))
    >>>
    >>> from kartograf import BBox
    >>> bbox = BBox(450000, 550000, 451000, 551000, "EPSG:2180")
    >>> GugikNmptProvider(vertical_crs="EVRF2007", resolution="1m").download_bbox(
    ...     bbox, Path("./area.tif")
    ... )
    """

    PRODUCT = "nmpt"

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

    # NMPT coverage IDs for WCS
    COVERAGE_IDS = {
        "KRON86": "DSM_PL-KRON86-NH",
        "EVRF2007": "DSM_PL-EVRF2007-NH",
    }

    # The NMPT image/tiff is 3-band uint8 RGB, not heights: heights come only as
    # image/x-aaigrid. The coverage step is 0.5 m; the result is 1 m on the 1 m
    # sheet grid via SCALEFACTOR=0.5 - bit for bit the 1 m NMPT sheets and an
    # exact decimation of 0.5 m content (pixel centred on a whole metre), no
    # averaging (docs/research/2026-10-11-wcs-cutouts/raport.md, point 3).
    WCS_HEIGHT_FORMAT = {"KRON86": HEIGHT_AAIGRID, "EVRF2007": HEIGHT_AAIGRID}
    WCS_GRID = GridSpec(step=1.0, origin_x=0.5, origin_y=0.5)
    WCS_NATIVE_STEP = 0.5

    # 4 Mpx of coverage = 1 Mpx of result per ASC chunk. Live 2026-10-11 hangs
    # (no byte for 300 s) hit 0.25-16 Mpx chunks alike, so every chunk is one more
    # draw at a 120 s hang; a 4 Mpx chunk answered in 15-26 s like a 1 Mpx one,
    # 8 Mpx took up to 104 s (docs/research/2026-10-11-nmpt-asc-tuning/raport.md).
    WCS_CHUNK_LIMITS_AAIGRID = ChunkLimits(
        max_width=40_000, max_height=40_000, max_pixels=4_000_000
    )

    @property
    def name(self) -> str:
        """Return provider name."""
        return "GUGiK NMPT"
