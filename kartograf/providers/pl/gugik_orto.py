"""
GUGiK provider for downloading Orthophotomap data.

This module provides the GugikOrtoProvider class for downloading
orthophoto (aerial imagery) data from the Polish GUGiK services.

Standard Resolution orthophotos (25cm) are available as GeoTIFF
via WMS indexes (skorowidze) → OpenData and WCS.

Unlike NMT/NMPT, orthophotos:
- Have no vertical CRS (2D RGB imagery)
- Use a single WMS endpoint (no KRON86/EVRF2007 split)
- Download as TIF (not ASC)
- Come in colour variants (RGB, CIR, B/W) published under the same godlo;
  the provider downloads exactly one variant (``color``, default RGB)
"""

import logging
import re
from pathlib import Path

import requests

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import NoCoverageError
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.skorowidz import (
    SkorowidzLayersMixin,
    SkorowidzQuery,
    SkorowidzRecord,
    coverage_hints,
    no_coverage_error,
)
from kartograf.providers.pl.wcs import GugikWcsMixin
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
    download_to,
)

logger = logging.getLogger(__name__)


class GugikOrtoProvider(SkorowidzLayersMixin, GugikWcsMixin, BaseProvider):
    """
    Provider for downloading Orthophotomap data from GUGiK.

    Supports two download modes:
    - By sheet code (godlo): downloads from OpenData as TIF
    - By bbox (bounding box): downloads from WCS as GeoTIFF

    Examples
    --------
    >>> provider = GugikOrtoProvider()
    >>> provider.download("N-34-130-D-d-2-4", Path("./sheet.tif"))
    >>>
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_bbox(bbox, Path("./area.tif"))
    """

    BASE_URL = "https://mapy.geoportal.gov.pl"

    WCS_ENDPOINT = f"{BASE_URL}/wss/service/PZGIK/ORTO/WCS/StandardResolution"
    COVERAGE_ID = "Orthoimagery_StandardResolution"

    DOWNLOAD_LABEL = "Ortofoto OpenData"

    WMS_SKOROWIDZE_ENDPOINT = (
        f"{BASE_URL}/wss/service/PZGIK/ORTO/WMS/SkorowidzeWgAktualnosci"
    )

    # Index layer names: group 1 = year, group 2 = aggregate layer without a
    # year ("Starsze" — GUGiK merged the 2023..2018 layers into one). Layers
    # "SkorowidzeOrtofotomapyZasiegi*" (extents, no URLs) do not match the pattern.
    LAYER_PATTERN = re.compile(r"^SkorowidzeOrtofotomapy(?:(\d{4})|(Starsze))$")
    LAYER_FAMILY = re.compile(r"^SkorowidzeOrtofotomapy(?!Zasiegi)")

    # Colour variant downloaded by default; CIR/B-W only via the `color` kwarg
    DEFAULT_COLOR = "RGB"

    # record_cache key: the resolution slot carries the colour variant (orto has no
    # resolution flag, and RGB and CIR of the same sheet are different files)
    _CACHE_PRODUCT = "orto"

    # Settings
    DEFAULT_TIMEOUT = 60  # Ortofoto files are larger
    MAX_RETRIES = MAX_RETRIES

    def __init__(
        self,
        session: requests.Session | None = None,
        cache=None,
        color: str = DEFAULT_COLOR,
    ):
        """
        Initialize the GUGiK orthophoto map (Ortofotomapa) provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        cache : MetadataCache, optional
            Metadata cache instance for caching index (skorowidz) lookups.
            If None, no caching is performed (default behavior).
        color : str, optional
            Colour variant to download as published by GUGiK: "RGB"
            (default), "CIR" or "B/W". A sheet without this variant is
            ``NoCoverageError`` — other variants are never substituted.
        """
        super().__init__()
        self._sessions = SessionPerThread(session)
        self._cache = cache
        self._color = color
        self.descriptor_key = "pl.gugik.orto"

    @property
    def name(self) -> str:
        """Return provider name."""
        return "GUGiK Ortofotomapa"

    @property
    def base_url(self) -> str:
        """Return base URL for GUGiK service."""
        return self.BASE_URL

    @property
    def default_extension(self) -> str:
        """Return default file extension for orthophoto data."""
        return ".tif"

    @property
    def color(self) -> str:
        """Colour variant this provider downloads (RGB by default)."""
        return self._color

    @property
    def storage_variant(self) -> str | None:
        """Variant segment (E12): RGB without suffix, CIR -> "cir", B/W -> "bw".

        RGB stays in ``orto/pl_<crs>/`` (no migration of pre-E12 files);
        other variants get ``orto/pl_<crs>_<variant>/``.
        """
        if self._color == self.DEFAULT_COLOR:
            return None
        return re.sub(r"[^a-z0-9]", "", self._color.lower())

    # =========================================================================
    # Download by sheet code → OpenData (TIF)
    # =========================================================================

    def download(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download orthophoto for a map sheet (godlo) from OpenData.

        Parameters
        ----------
        godlo : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        output_path : Path
            Path where the TIF file should be saved
        timeout : int, optional
            Request timeout in seconds (default: 60)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        NoCoverageError
            Subclass of ``DownloadError``: every index layer answered and
            none has this sheet in the requested colour variant and the
            godlo's coordinate system (other variants are listed in the
            message, never substituted).
        DownloadError
            If any index layer query fails after retries, its answer is
            invalid, or the TIF download fails after retries. An older
            campaign is never substituted after a failed query.
        """
        return self.download_record(
            self._resolve_sheet(godlo, timeout), Path(output_path), timeout
        )

    def _get_opendata_url(self, godlo: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Return the URL of the newest index record in the requested colour."""
        return self._resolve_sheet(godlo, timeout).url

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Cache key per colour variant; hard CRS + colour filter."""
        return SkorowidzQuery(
            cache_key=(self._CACHE_PRODUCT, self._color, "none", parser.godlo),
            endpoint=self.WMS_SKOROWIDZE_ENDPOINT,
            # Pixel size is not a filter: orto has no resolution flag.
            predicate=lambda record: record.raw.get("kolor") == self._color,
            source_extra={"color": self._color},
            no_coverage=self._no_coverage,
        )

    def _no_coverage(
        self, parser: SheetParser, records: list[SkorowidzRecord]
    ) -> NoCoverageError:
        zone = int(parser.godlo.split(".")[0]) if parser.uklad == "2000" else None
        variants = sorted(
            (record.aktualnosc, record.raw.get("kolor") or "?")
            for record in records
            if record.godlo == parser.godlo
            and record.uklad == parser.uklad
            and record.zone == zone
        )
        message = (
            f"Brak ortofotomapy {self._color} dla {parser.godlo} "
            f"(uklad PL-{parser.uklad})"
        )
        if variants:
            message += ". Dostepne warianty tego arkusza: " + ", ".join(
                f"{kolor} {aktualnosc}" for aktualnosc, kolor in variants
            )
        return no_coverage_error(parser, message, coverage_hints(parser, records))

    # =========================================================================
    # Download by bbox → WCS (GeoTIFF)
    # =========================================================================

    def download_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download orthophoto for a bounding box from WCS.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the file should be saved
        format : str, optional
            Output format: "GTiff", "PNG", or "JPEG" (default: "GTiff")
        timeout : int, optional
            Request timeout in seconds (default: 60)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If the download fails
        ValueError
            If format is not supported or bbox CRS is not EPSG:2180
        """
        if bbox.crs != "EPSG:2180":
            raise ValueError(
                f"BBox must be in EPSG:2180, got {bbox.crs}. "
                f"Use SheetParser.get_bbox(crs='EPSG:2180') to convert."
            )

        if format not in self.WCS_FORMATS:
            raise ValueError(
                f"Unsupported WCS format: '{format}'. "
                f"Supported formats: {list(self.WCS_FORMATS.keys())}"
            )

        output_path = Path(output_path)

        url = self._construct_wcs_url(bbox, format)

        return download_to(
            self._sessions.get(),
            url,
            output_path,
            timeout=timeout,
            retries=self.MAX_RETRIES,
            description=(
                f"ortofoto bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
                f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
            ),
        )

    def _wcs_target(self) -> tuple[str, str]:
        """The single fixed orthophotomap endpoint and coverage (Standard Res.)."""
        return self.WCS_ENDPOINT, self.COVERAGE_ID
