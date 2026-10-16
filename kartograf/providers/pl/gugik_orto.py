"""
GUGiK provider for downloading Orthophotomap data.

This module provides the GugikOrtoProvider class for downloading
orthophoto (aerial imagery) data from the Polish GUGiK services.

Orthophotos (resolution per campaign, e.g. 25 cm, 10 cm) are available as
GeoTIFF via WMS indexes (skorowidze) → OpenData and WCS.

Unlike NMT/NMPT, orthophotos:
- Have no vertical CRS (2D RGB imagery)
- Use a single WMS endpoint (no KRON86/EVRF2007 split)
- Download as TIF (not ASC)
- Come in colour variants (RGB, CIR, B/W) published under the same sheet;
  the provider downloads exactly one variant (explicit ``color``)

WCS: ``download_bbox`` without ``coverage`` is the raw Standard Resolution
request with the bbox as given (one request at the 0.1 m coverage step, a
file outside the store). With ``coverage`` and ``resolution`` it serves the
area cutout of the store (``kartograf.download.orto_cutout``, ADR-042 D14):
the endpoint and coverage of the registry channel (``WcsCutoutParams`` of
``pl.gugik.orto``: Standard or High), a result grid at multiples of the
chosen pixel (``SCALEFACTOR`` = 0.1 m / pixel) and chunks within the budget of
the channel counted in 0.1 m coverage pixels, stitched without resampling.
"""

import logging
import re
from dataclasses import replace
from pathlib import Path
from typing import Literal

import requests

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import NoCoverageError, ValidationError
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.skorowidz import (
    SkorowidzLayersMixin,
    SkorowidzQuery,
    SkorowidzRecord,
    coverage_hints,
    no_coverage_error,
)
from kartograf.providers.pl.wcs import GugikWcsMixin
from kartograf.sources.descriptor import AccessChannel, WcsCutoutParams
from kartograf.sources.registry import get_source
from kartograf.sources.variants import parse_resolution, resolution_label
from kartograf.transport.chunks import GridSpec
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
)

logger = logging.getLogger(__name__)

ORTO_KEY = "pl.gugik.orto"

# ``coverage`` of the WCS cutout = ``WcsCutoutParams.variant`` of the registry.
OrtoCoverage = Literal["standard", "high"]


def wcs_cutout_channels() -> tuple[AccessChannel, ...]:
    """WCS cutout channels of the orthophotomap, registry order (ADR-042 D14)."""
    return tuple(
        channel
        for channel in get_source(ORTO_KEY).channels
        if isinstance(channel.params, WcsCutoutParams)
    )


def _params(channel: AccessChannel) -> WcsCutoutParams:
    params = channel.params
    assert isinstance(params, WcsCutoutParams)  # wcs_cutout_channels only
    return params


def coverage_choices() -> str:
    """``standard (...), high (...)``: the ``--coverage`` values with their
    meaning (channel ``notes``), from the registry."""
    return ", ".join(f"{_params(c).variant} ({c.notes})" for c in wcs_cutout_channels())


def _unknown_coverage(coverage: object) -> str:
    return f"--coverage {coverage!r}: nieznana wartosc - dostepne: {coverage_choices()}"


def wcs_cutout_channel(coverage: str) -> AccessChannel:
    """The WCS cutout channel of ``coverage``.

    Raises
    ------
    ValidationError
        No such channel (the message lists the registry choices).
    """
    for channel in wcs_cutout_channels():
        if _params(channel).variant == coverage:
            return channel
    raise ValidationError(_unknown_coverage(coverage))


def cutout_resolution_labels(coverage: str) -> list[str]:
    """Labels K2 of the cutout pixels of ``coverage`` (``0.1m``, ``0.25m``, ...)."""
    return [
        resolution_label(v) for v in _params(wcs_cutout_channel(coverage)).resolutions
    ]


def cutout_choice_error(coverage: object, resolution: object) -> str | None:
    """Error text of a WCS cutout choice (``None`` = valid; texts name the
    CLI flags, lists from the registry)."""
    if coverage is None:
        return f"--coverage wymagane z --cutout --product orto: {coverage_choices()}"
    variants = [_params(c).variant for c in wcs_cutout_channels()]
    if not isinstance(coverage, str) or coverage not in variants:
        return _unknown_coverage(coverage)
    labels = cutout_resolution_labels(coverage)
    if resolution is None:
        return (
            "--resolution wymagane z --cutout --product orto (piksel wycinka): "
            f"{', '.join(labels)}"
        )
    if not isinstance(resolution, str) or resolution not in labels:
        return (
            f"--resolution {resolution!r}: niedostepne dla wycinka ortofotomapy "
            f"{coverage} - dostepne: {', '.join(labels)}"
        )
    return None


class GugikOrtoProvider(SkorowidzLayersMixin, GugikWcsMixin, BaseProvider):
    """
    Provider for downloading Orthophotomap data from GUGiK.

    Supports two download modes:
    - By sheet code: downloads from OpenData as TIF
    - By bbox (bounding box): downloads from WCS as GeoTIFF (raw Standard
      request, or the cutout grid of ``coverage``/``resolution``)

    Examples
    --------
    >>> provider = GugikOrtoProvider(color="RGB")
    >>> provider.download("N-34-130-D-d-2-4", Path("./sheet.tif"))
    >>>
    >>> from kartograf import BBox
    >>> bbox = BBox(
    ...     min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
    ... )
    >>> provider.download_bbox(bbox, Path("./area.tif"))
    >>> small = BBox(566000, 243000, 566200, 243200, crs="EPSG:2180")
    >>> cutout = GugikOrtoProvider(color="RGB", coverage="high", resolution="0.1m")
    >>> cutout.download_bbox(small, Path("./area_high.tif"))
    """

    BASE_URL = "https://mapy.geoportal.gov.pl"

    WCS_ENDPOINT = f"{BASE_URL}/wss/service/PZGIK/ORTO/WCS/StandardResolution"
    COVERAGE_ID = "Orthoimagery_StandardResolution"

    DOWNLOAD_LABEL = "Ortofoto OpenData"

    WMS_INDEX_ENDPOINT = (
        f"{BASE_URL}/wss/service/PZGIK/ORTO/WMS/SkorowidzeWgAktualnosci"
    )

    # Index layer names: group 1 = year, group 2 = aggregate layer without a
    # year ("Starsze" — GUGiK merged the 2023..2018 layers into one). Layers
    # "SkorowidzeOrtofotomapyZasiegi*" (extents, no URLs) do not match the pattern.
    LAYER_PATTERN = re.compile(r"^SkorowidzeOrtofotomapy(?:(\d{4})|(Starsze))$")
    LAYER_FAMILY = re.compile(r"^SkorowidzeOrtofotomapy(?!Zasiegi)")

    # RGB uses the original unsuffixed storage segment.
    DEFAULT_COLOR = "RGB"

    # record_cache key: the resolution slot carries the colour variant (orto has no
    # resolution flag, and RGB and CIR of the same sheet are different files)
    _CACHE_PRODUCT = "orto"

    # Settings
    DEFAULT_TIMEOUT = 60  # Ortofoto files are larger
    MAX_RETRIES = MAX_RETRIES

    # Read timeout of one cutout chunk (s): MapServer sends no byte before the
    # whole chunk is rendered - live 2026-10-15 4 Mpx of coverage (200 x 200 m)
    # took 64 s and 2000 x 2000 px at SCALEFACTOR=0.4 176 s (Standard).
    WCS_CUTOUT_READ_TIMEOUT = 300

    def __init__(
        self,
        session: requests.Session | None = None,
        cache=None,
        *,
        color: str,
        coverage: OrtoCoverage | None = None,
        resolution: str | None = None,
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
        color : str
            Colour variant as published by GUGiK: "RGB" (natural colour),
            "CIR" (colour infrared) or "B/W" (greyscale). A sheet without
            the requested variant raises ``NoCoverageError``; no variant
            substitution is made.
        coverage : {"standard", "high"}, optional
            WCS coverage of an area cutout (``WcsCutoutParams`` channels of
            ``pl.gugik.orto``): "standard" (newest orthophotomaps) or "high"
            (pixel 10 cm and finer; pixels 0,0,0 elsewhere). ``download_bbox``
            then aligns the area to multiples of ``resolution`` and fetches it
            in chunks. ``None``: the raw Standard request with the bbox as given.
        resolution : str, optional
            Cutout pixel, a label K2 of the channel ("0.1m", "0.25m", "0.5m",
            "1m"); required with ``coverage`` and only with it.

        Raises
        ------
        ValidationError
            ``coverage`` or ``resolution`` outside the registry channel, one
            without the other, or ``color`` other than RGB with ``coverage``
            (the WCS serves the RGB composition only).
        """
        super().__init__()
        self._sessions = SessionPerThread(session)
        self._cache = cache
        self._color = color
        self.descriptor_key = ORTO_KEY
        self._cutout: AccessChannel | None = None
        if coverage is None and resolution is None:
            return
        if coverage is None:
            raise ValidationError(
                "--resolution ortofotomapy dotyczy tylko wycinka WCS - podaj "
                f"--coverage: {coverage_choices()}"
            )
        error = cutout_choice_error(coverage, resolution)
        if error is not None:
            raise ValidationError(error)
        if color != self.DEFAULT_COLOR:
            raise ValidationError(
                f"wycinek WCS ortofotomapy ma tylko kompozycje {self.DEFAULT_COLOR} "
                f"- podano color={color!r}"
            )
        step = parse_resolution(resolution) if resolution is not None else None
        assert step is not None  # cutout_choice_error accepted the label
        self._cutout = wcs_cutout_channel(coverage)
        params = _params(self._cutout)
        # Result grid at multiples of the pixel (SCALEFACTOR = native / pixel)
        # and the request budget in coverage pixels (plan_wcs_chunks).
        self.WCS_GRID = GridSpec(step=float(step))
        self.WCS_NATIVE_STEP = float(params.native_step)
        self.WCS_CHUNK_LIMITS = replace(
            GugikWcsMixin.WCS_CHUNK_LIMITS, max_pixels=params.max_native_pixels
        )

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
        """Return the explicitly requested RGB, CIR or B/W variant."""
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
        sheet: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download orthophoto for a map sheet from OpenData.

        Parameters
        ----------
        sheet : str
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
            sheet's coordinate system (other variants are listed in the
            message, never substituted).
        DownloadError
            If any index layer query fails after retries, its answer is
            invalid, or the TIF download fails after retries. An older
            campaign is never substituted after a failed query.
        """
        return self.download_record(
            self._resolve_sheet(sheet, timeout), Path(output_path), timeout
        )

    def _get_opendata_url(self, sheet: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Return the URL of the newest index record in the requested colour."""
        return self._resolve_sheet(sheet, timeout).url

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Cache key per colour variant; hard CRS + colour filter."""
        return SkorowidzQuery(
            cache_key=(self._CACHE_PRODUCT, self._color, "none", parser.sheet),
            endpoint=self.WMS_INDEX_ENDPOINT,
            # Pixel size is not a filter: orto has no resolution flag.
            predicate=lambda record: record.raw.get("kolor") == self._color,
            source_extra={"color": self._color},
            no_coverage=self._no_coverage,
        )

    def _no_coverage(
        self, parser: SheetParser, records: list[SkorowidzRecord]
    ) -> NoCoverageError:
        zone = (
            int(parser.sheet.split(".")[0]) if parser.sheet_system == "2000" else None
        )
        variants = sorted(
            (record.aktualnosc, record.raw.get("kolor") or "?")
            for record in records
            if record.sheet == parser.sheet
            and record.system == parser.sheet_system
            and record.zone == zone
        )
        message = (
            f"Brak ortofotomapy {self._color} dla {parser.sheet} "
            f"(uklad PL-{parser.sheet_system})"
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

        Without ``coverage`` (the raw API): one Standard Resolution request
        with the bbox as given, at the 0.1 m coverage step. With ``coverage``
        and ``resolution``: the bbox aligned OUTWARD to multiples of the pixel
        (widened by at most 1 px east and south to an even size, cropped
        back), requested from the channel's service with ``SCALEFACTOR`` when
        the pixel differs from 0.1 m, in chunks within the channel budget of
        coverage pixels, each chunk waiting at least
        ``WCS_CUTOUT_READ_TIMEOUT`` s for data, stitched without resampling.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the file should be saved
        format : str, optional
            Output format: "GTiff", "PNG", or "JPEG" (default: "GTiff"); a
            cutout (``coverage``) is GTiff only
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
        ValidationError
            If format is not supported or bbox CRS is not EPSG:2180
        """
        if bbox.crs != "EPSG:2180":
            raise ValidationError(
                f"bbox musi byc w EPSG:2180, podano {bbox.crs}. "
                "Przelicz: SheetParser.get_bbox(crs='EPSG:2180')."
            )

        if format not in self.WCS_FORMATS:
            raise ValidationError(
                f"Nieobslugiwany format WCS: '{format}'. "
                f"Obslugiwane formaty: {list(self.WCS_FORMATS.keys())}"
            )
        if self._cutout is not None:
            if format != "GTiff":
                raise ValidationError(
                    f"Wycinek WCS ortofotomapy (coverage) jest tylko GTiff - podano "
                    f"format {format!r}; PNG/JPEG: provider bez coverage"
                )
            timeout = max(timeout, self.WCS_CUTOUT_READ_TIMEOUT)

        return self._download_wcs(
            bbox,
            Path(output_path),
            format,
            timeout,
            f"ortofoto bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
            f"({bbox.max_x:.0f},{bbox.max_y:.0f})",
        )

    def _wcs_target(self) -> tuple[str, str]:
        """Endpoint and coverage of the WCS cutout channel; without one the
        fixed Standard Resolution service of the raw ``download_bbox``."""
        if self._cutout is None:
            return self.WCS_ENDPOINT, self.COVERAGE_ID
        return self._cutout.endpoint, _params(self._cutout).coverage_id
