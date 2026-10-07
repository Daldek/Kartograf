"""
GUGiK provider for downloading Orthophotomap data.

This module provides the GugikOrtoProvider class for downloading
orthophoto (aerial imagery) data from the Polish GUGiK services.

Standard Resolution orthophotos (25cm) are available as GeoTIFF
via WMS skorowidze → OpenData and WCS.

Unlike NMT/NMPT, orthophotos:
- Have no vertical CRS (2D RGB imagery)
- Use a single WMS endpoint (no KRON86/EVRF2007 split)
- Download as TIF (not ASC)
- Come in colour variants (RGB, CIR, B/W) published under the same godlo;
  the provider downloads exactly one variant (``color``, default RGB)
"""

import logging
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import NoCoverageError, ParseError
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.skorowidz import SkorowidzLayersMixin, SkorowidzRecord
from kartograf.transport.http import (
    SessionPerThread,
    http_failure,
    http_status,
    is_retryable,
    retry_wait,
)

logger = logging.getLogger(__name__)


class GugikOrtoProvider(SkorowidzLayersMixin, BaseProvider):
    """
    Provider for downloading Orthophotomap data from GUGiK.

    Supports two download modes:
    - By godło (map sheet ID): downloads from OpenData as TIF
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

    WMS_SKOROWIDZE_ENDPOINT = (
        f"{BASE_URL}/wss/service/PZGIK/ORTO/WMS/SkorowidzeWgAktualnosci"
    )

    # Nazwy warstw skorowidza: grupa 1 = rok, grupa 2 = warstwa zbiorcza bez
    # roku ("Starsze" — GUGiK scalil warstwy 2023..2018 w jedna). Warstwy
    # "SkorowidzeOrtofotomapyZasiegi*" (zasiegi, bez URL-i) nie pasuja do wzorca.
    LAYER_PATTERN = re.compile(r"^SkorowidzeOrtofotomapy(?:(\d{4})|(Starsze))$")

    # Wariant koloru pobierany domyslnie; CIR/B-W tylko przez kwarg `color`
    DEFAULT_COLOR = "RGB"

    # Klucz record_cache: slot rozdzielczosci niesie wariant koloru (orto nie
    # ma flagi rozdzielczosci, a RGB i CIR tego samego arkusza to inne pliki)
    _CACHE_PRODUCT = "orto"

    # WCS formats
    WCS_FORMATS = {
        "GTiff": "image/tiff",
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }

    # Settings
    DEFAULT_TIMEOUT = 60  # Ortofoto files are larger
    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 2

    def __init__(
        self,
        session: requests.Session | None = None,
        cache=None,
        color: str = DEFAULT_COLOR,
    ):
        """
        Initialize GUGiK Ortofotomapa provider.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        cache : MetadataCache, optional
            Metadata cache instance for caching skorowidz lookups.
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
        """Segment wariantu (E12): RGB bez sufiksu, CIR -> "cir", B/W -> "bw".

        RGB zostaje w ``orto/pl_<uklad>/`` (bez migracji plikow sprzed E12);
        inne warianty dostaja ``orto/pl_<uklad>_<wariant>/``.
        """
        if self._color == self.DEFAULT_COLOR:
            return None
        return re.sub(r"[^a-z0-9]", "", self._color.lower())

    # =========================================================================
    # Download by godło → OpenData (TIF)
    # =========================================================================

    def download(
        self,
        godlo: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download orthophoto for a map sheet (godło) from OpenData.

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
            Subclass of ``DownloadError``: every skorowidz layer answered and
            none has this sheet in the requested colour variant and the
            godlo's coordinate system (other variants are listed in the
            message, never substituted).
        DownloadError
            If any skorowidz layer query fails after retries, its answer is
            invalid, or the TIF download fails after retries. An older
            campaign is never substituted after a failed query.
        """
        output_path = Path(output_path)

        record = self._resolve_sheet(godlo, timeout)

        return self._download_with_retry(
            url=record.url,
            output_path=output_path,
            timeout=timeout,
            description=f"{godlo} (Ortofoto OpenData)",
        )

    def _get_opendata_url(self, godlo: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Zwroc URL najnowszego rekordu skorowidza w zadanym wariancie koloru."""
        return self._resolve_sheet(godlo, timeout).url

    def _resolve_sheet(
        self, godlo: str, timeout: int = DEFAULT_TIMEOUT
    ) -> SkorowidzRecord:
        """Cache -> warstwy od najnowszej -> twardy filtr uklad+kolor -> najnowsza."""
        parser = SheetParser(godlo)
        return self._resolve_record(
            parser,
            timeout,
            cache_key=(self._CACHE_PRODUCT, self._color, "none", parser.godlo),
            endpoint=self.WMS_SKOROWIDZE_ENDPOINT,
            # Piksel nie jest filtrem: orto nie ma flagi rozdzielczosci.
            predicate=lambda record: record.raw.get("kolor") == self._color,
            source_extra={"kolor": self._color},
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
        hints = set()
        for record in records:
            if parser.uklad == "2000" and record.godlo.startswith(parser.godlo + "."):
                scale = SheetParser(record.godlo).scale
                hints.add(f"Dostepny potomek {record.godlo} — uzyj --scale {scale}")
            elif record.uklad is not None and record.uklad != parser.uklad:
                hints.add(
                    f"Skorowidz ma ten obszar w PL-{record.uklad}: "
                    f"{record.godlo} — uzyj tego godla"
                )
        message = (
            f"Brak ortofotomapy {self._color} dla {parser.godlo} "
            f"(uklad PL-{parser.uklad})"
        )
        if variants:
            message += ". Dostepne warianty tego arkusza: " + ", ".join(
                f"{kolor} {aktualnosc}" for aktualnosc, kolor in variants
            )
        if hints:
            message += ". " + "; ".join(sorted(hints))
        return NoCoverageError(message, godlo=parser.godlo)

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

        return self._download_with_retry(
            url=url,
            output_path=output_path,
            timeout=timeout,
            description=(
                f"ortofoto bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
                f"({bbox.max_x:.0f},{bbox.max_y:.0f})"
            ),
        )

    def _construct_wcs_url(self, bbox: BBox, format: str) -> str:
        """Construct WCS GetCoverage URL."""
        params = {
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": self.COVERAGE_ID,
            "FORMAT": self.WCS_FORMATS[format],
        }

        base_url = f"{self.WCS_ENDPOINT}?{urlencode(params)}"
        subset_x = f"SUBSET=x({bbox.min_x:.2f},{bbox.max_x:.2f})"
        subset_y = f"SUBSET=y({bbox.min_y:.2f},{bbox.max_y:.2f})"

        return f"{base_url}&{subset_x}&{subset_y}"

    # =========================================================================
    # Common utilities
    # =========================================================================

    def _download_with_retry(
        self,
        url: str,
        output_path: Path,
        timeout: int,
        description: str,
    ) -> Path:
        """Download file with automatic retry on failure."""
        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(
                    f"Downloading {description} (attempt {attempt}/{self.MAX_RETRIES})"
                )

                response = self._make_request(url, timeout)
                self._save_response(response, output_path)

                logger.info(f"Successfully downloaded {description} to {output_path}")
                return output_path

            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    f"Download failed for {description} (attempt {attempt}): {e}"
                )
                if not is_retryable(e):
                    raise http_failure(
                        f"Failed to download {description}: "
                        f"HTTP {http_status(e)} (not retried): {e}",
                        e,
                    ) from e

                if attempt < self.MAX_RETRIES:
                    wait_time = retry_wait(e, self.RETRY_BACKOFF_BASE**attempt)
                    logger.debug(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

        raise http_failure(
            f"Failed to download {description} after "
            f"{self.MAX_RETRIES} attempts: {last_error}",
            last_error,
        )

    def _make_request(self, url: str, timeout: int) -> requests.Response:
        """Pobierz strumien na sesji watku (sesja wstrzyknieta: dba wolajacy)."""
        response = self._sessions.get().get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        return response

    def _save_response(self, response: requests.Response, output_path: Path) -> None:
        """
        Save HTTP response to file atomically.

        The target directory is created here, after the skorowidz has
        answered — a sheet without data leaves no empty directory behind.
        Uses a unique temp filename per process/thread to prevent
        collisions when multiple threads download concurrently.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        thread_id = threading.current_thread().ident
        temp_suffix = f"{output_path.suffix}.{os.getpid()}_{thread_id}.tmp"
        temp_path = output_path.with_suffix(temp_suffix)

        try:
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            temp_path.rename(output_path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    # =========================================================================
    # Info methods
    # =========================================================================

    def get_supported_formats(self) -> list[str]:
        """Return list of supported WCS formats."""
        return list(self.WCS_FORMATS.keys())

    def validate_godlo(self, godlo: str) -> bool:
        """Validate godło format."""
        try:
            SheetParser(godlo)
            return True
        except ParseError:
            return False
