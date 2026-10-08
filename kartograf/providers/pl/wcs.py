"""GUGiK WCS 2.0.1 GetCoverage — shared by NMT/NMPT 1 m and orthophotomaps (D13)."""

from urllib.parse import urlencode

from kartograf.core.sheet_parser import BBox


class GugikWcsMixin:
    """Format -> GetCoverage URL; the derived class supplies endpoint and coverage.

    NMT/NMPT choose the endpoint and coverage by vertical CRS, orto has a
    single fixed one — the rest of the request (version, SUBSET in
    EPSG:2180, formats) is shared.
    """

    WCS_FORMATS = {
        "GTiff": "image/tiff",
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }

    def _wcs_target(self) -> tuple[str, str]:
        """(WCS endpoint, COVERAGEID) for the provider's current configuration."""
        raise NotImplementedError

    def _construct_wcs_url(self, bbox: BBox, format: str) -> str:
        """GetCoverage URL for a bbox in EPSG:2180 and a ``WCS_FORMATS`` format."""
        endpoint, coverage_id = self._wcs_target()
        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": coverage_id,
            "FORMAT": self.WCS_FORMATS[format],
        }
        base_url = f"{endpoint}?{urlencode(params)}"
        subset_x = f"SUBSET=x({bbox.min_x:.2f},{bbox.max_x:.2f})"
        subset_y = f"SUBSET=y({bbox.min_y:.2f},{bbox.max_y:.2f})"
        return f"{base_url}&{subset_x}&{subset_y}"

    def get_supported_formats(self) -> list[str]:
        """Return list of supported WCS formats."""
        return list(self.WCS_FORMATS.keys())
