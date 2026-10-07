"""WCS 2.0.1 GetCoverage GUGiK — wspolny dla NMT/NMPT 1 m i ortofotomapy (D13)."""

from urllib.parse import urlencode

from kartograf.core.sheet_parser import BBox


class GugikWcsMixin:
    """Format -> URL GetCoverage; klasa pochodna podaje endpoint i coverage.

    NMT/NMPT wybieraja endpoint i coverage po ukladzie wysokosci, orto ma
    jeden staly — reszta zapytania (wersja, SUBSET w EPSG:2180, formaty) jest
    wspolna.
    """

    WCS_FORMATS = {
        "GTiff": "image/tiff",
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }

    def _wcs_target(self) -> tuple[str, str]:
        """(endpoint WCS, COVERAGEID) dla biezacej konfiguracji providera."""
        raise NotImplementedError

    def _construct_wcs_url(self, bbox: BBox, format: str) -> str:
        """URL GetCoverage dla bboxa w EPSG:2180 i formatu z ``WCS_FORMATS``."""
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
