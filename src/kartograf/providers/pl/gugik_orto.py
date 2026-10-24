"""
GUGiK image providers: sheets from a WMS sheet index and the WCS cutout.

``GugikImageProvider`` serves every GUGiK image product whose sheets are
listed by a WMS sheet index (skorowidz): the descriptor of the product
(``SheetIndexParams`` of its ``WMS_SHEET_INDEX`` channel, ``WcsCutoutParams``
of its cutout channels) gives the index endpoint and layers, the sheet
systems and the PL-1992 sheet level, the view directions of an oblique image
and the segment of the store - one code for the orthophotomap, the intensity
images, the true orthophotomap and the oblique orthophotomap (plan E1, no
copy of the provider). ``GugikOrtoProvider`` is the orthophotomap: its
yearly index layers come from GetCapabilities and it adds the colour
variants (RGB, CIR, B/W published under the same sheet; exactly one variant,
explicit ``color``).

Unlike NMT/NMPT, images:
- Have no vertical CRS (2D imagery)
- Use a single WMS index endpoint per product (no KRON86/EVRF2007 split)
- Download as TIF (not ASC)

WCS: the orthophotomap ``download_bbox`` without ``coverage`` is the raw
Standard Resolution request with the bbox as given (one request at the
0.1 m coverage step, a file outside the store). With ``resolution`` (and
``coverage`` for a product with several cutout channels: orthophotomap
Standard or High; the true orthophotomap has one) it serves the area cutout
of the store (``kartograf.download.orto_cutout``, ADR-042 D14): the endpoint
and coverage of the registry channel, a result grid at multiples of the
chosen pixel (``SCALEFACTOR`` = coverage step / pixel) and chunks within the
budget of the channel counted in coverage pixels, stitched without
resampling.
"""

import logging
import re
from dataclasses import replace
from pathlib import Path
from typing import Literal

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser, series_scale
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
from kartograf.sources.descriptor import (
    AccessChannel,
    SheetIndexParams,
    SourceDescriptor,
    WcsCutoutParams,
)
from kartograf.sources.registry import get_source, sources_for
from kartograf.sources.variants import parse_resolution, resolution_label
from kartograf.transport.chunks import GridSpec
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
)

logger = logging.getLogger(__name__)

ORTO_KEY = "pl.gugik.orto"

# ``coverage`` of the orthophotomap WCS cutout = ``WcsCutoutParams.variant``.
OrtoCoverage = Literal["standard", "high"]


def image_source(product: object) -> SourceDescriptor | None:
    """Return the PL source of an image product on a GUGiK WMS sheet index.

    The products are ``orto``, ``intensity``, ``true-orto``, ``oblique-orto``;
    ``None`` for any other product.
    """
    if not isinstance(product, str):
        return None
    return next(
        (
            d
            for d in sources_for(country="PL", product=product)
            if any(isinstance(c.params, SheetIndexParams) for c in d.channels)
        ),
        None,
    )


def sheet_index_channel(key: str) -> AccessChannel:
    """Return the WMS sheet index channel of source ``key`` (``SheetIndexParams``).

    Raises
    ------
    ValidationError
        The source publishes no sheets on a WMS sheet index.
    """
    for channel in get_source(key).channels:
        if isinstance(channel.params, SheetIndexParams):
            return channel
    raise ValidationError(f"Zrodlo {key} nie ma skorowidza arkuszy WMS")


def sheet_index(key: str) -> SheetIndexParams:
    """``SheetIndexParams`` of the sheet index of source ``key``."""
    params = sheet_index_channel(key).params
    assert isinstance(params, SheetIndexParams)  # sheet_index_channel only
    return params


def wcs_cutout_channels(key: str) -> tuple[AccessChannel, ...]:
    """WCS cutout channels of source ``key``, registry order (ADR-042 D14)."""
    return tuple(
        channel
        for channel in get_source(key).channels
        if isinstance(channel.params, WcsCutoutParams)
    )


def _params(channel: AccessChannel) -> WcsCutoutParams:
    params = channel.params
    assert isinstance(params, WcsCutoutParams)  # wcs_cutout_channels only
    return params


def coverage_choices(key: str) -> str:
    """Return the ``--coverage`` values of the cutout of ``key`` with their meaning.

    The form is ``standard (...), high (...)``; the meaning is the channel ``notes``,
    from the registry.
    """
    return ", ".join(
        f"{_params(c).variant} ({c.notes})" for c in wcs_cutout_channels(key)
    )


def _coverage_error(key: str, coverage: object) -> ValidationError | None:
    """Return the error of ``coverage`` for the cutout of ``key`` (``None`` = valid).

    It is required with several cutout channels, none with one.
    """
    channels = wcs_cutout_channels(key)
    product = get_source(key).product
    if len(channels) == 1:
        if coverage is None:
            return None
        return ValidationError(
            f"--coverage {coverage!r}: --product {product} ma jedna usluge WCS "
            f"wycinka ({channels[0].notes}) - bez --coverage",
            option="coverage",
        )
    allowed = tuple(_params(c).variant for c in channels)
    if coverage is None:
        return ValidationError(
            f"--coverage wymagane z --cutout --product {product}: "
            + coverage_choices(key),
            option="coverage",
            allowed=allowed,
        )
    if coverage not in allowed:
        return ValidationError(
            f"--coverage {coverage!r}: nieznana wartosc - dostepne: "
            f"{coverage_choices(key)}",
            option="coverage",
            allowed=allowed,
        )
    return None


def wcs_cutout_channel(key: str, coverage: str | None) -> AccessChannel:
    """Return the WCS cutout channel of source ``key`` chosen by ``coverage``.

    ``None``: the only channel of a source with one.

    Raises
    ------
    ValidationError
        No such channel (the message lists the registry choices).
    """
    error = _coverage_error(key, coverage)
    if error is not None:
        raise error
    channels = wcs_cutout_channels(key)
    if coverage is None:
        return channels[0]
    return next(c for c in channels if _params(c).variant == coverage)


def cutout_resolution_labels(key: str, coverage: str | None) -> list[str]:
    """Return the K2 labels of the cutout pixels of ``key`` and ``coverage``.

    For example ``0.1m``, ``0.25m``.
    """
    return [
        resolution_label(v)
        for v in _params(wcs_cutout_channel(key, coverage)).resolutions
    ]


def cutout_choice_error(
    key: str, coverage: object, resolution: object
) -> ValidationError | None:
    """Return the error of a WCS cutout choice of source ``key`` (``None`` = valid).

    Texts name the CLI flags, lists from the registry; ``option`` and
    ``allowed`` name the argument and its values.
    """
    error = _coverage_error(key, coverage)
    if error is not None:
        return error
    assert coverage is None or isinstance(coverage, str)  # _coverage_error
    product = get_source(key).product
    labels = cutout_resolution_labels(key, coverage)
    if resolution is None:
        return ValidationError(
            f"--resolution wymagane z --cutout --product {product} (piksel "
            f"wycinka): {', '.join(labels)}",
            option="resolution",
            allowed=tuple(labels),
        )
    if not isinstance(resolution, str) or resolution not in labels:
        variant = _params(wcs_cutout_channel(key, coverage)).variant
        return ValidationError(
            f"--resolution {resolution!r}: niedostepne dla wycinka ortofotomapy "
            f"{variant} - dostepne: {', '.join(labels)}",
            option="resolution",
            allowed=tuple(labels),
        )
    return None


def image_directions(product: object) -> tuple[str, ...]:
    """Return the view directions of an image product.

    ``n``, ``e``, ``s``, ``w`` of the oblique orthophotomap, registry order; ``()``
    for a product without.
    """
    source = image_source(product)
    if source is None:
        return ()
    return tuple(code for code, _ in sheet_index(source.key).directions)


class GugikImageProvider(SkorowidzLayersMixin, GugikWcsMixin, BaseProvider):
    """
    Sheets of a GUGiK image product from its WMS sheet index; its WCS cutout.

    ``source`` is the descriptor key of the product; everything else comes
    from the registry. A sheet is resolved like every GUGiK sheet (cache ->
    index layers -> hard filter -> newest campaign) and its GeoTIFF is
    downloaded from OpenData; a product with view directions (the oblique
    orthophotomap) has one provider per ``direction`` - one file per
    direction, named with the suffix ``_<direction>`` in the store.

    Examples
    --------
    >>> provider = GugikImageProvider("pl.gugik.intensity")
    >>> provider.download("M-34-64-D-d-1-4", Path("./sheet.tif"))
    >>> north = GugikImageProvider("pl.gugik.oblique_orto", direction="n")
    >>> north.download("7.125.11.08", Path("./7.125.11.08_n.tif"))
    >>> cutout = GugikImageProvider("pl.gugik.true_orto", resolution="0.05m")
    >>> cutout.download_bbox(
    ...     BBox(470177, 740336, 470178, 740337, crs="EPSG:2180"), Path("./a.tif")
    ... )
    """

    BASE_URL = "https://mapy.geoportal.gov.pl"

    DOWNLOAD_LABEL = "OpenData"

    # Settings
    DEFAULT_TIMEOUT = 60  # image files are larger
    MAX_RETRIES = MAX_RETRIES

    # Read timeout of one cutout chunk (s): MapServer sends no byte before the
    # whole chunk is rendered - live 2026-10-15 4 Mpx of coverage (200 x 200 m)
    # took 64 s and 2000 x 2000 px at SCALEFACTOR=0.4 176 s (Standard).
    WCS_CUTOUT_READ_TIMEOUT = 300

    # (endpoint, COVERAGEID) of ``download_bbox`` without a cutout channel;
    # ``None``: the product has no raw WCS request.
    RAW_WCS_TARGET: tuple[str, str] | None = None

    # Image sheets are large (85-300 MB, raport E): HEAD before the transfer,
    # ``DOWNLOAD_SIZE`` above 100 MiB (K9).
    announces_size = True

    def __init__(
        self,
        source: str,
        session: requests.Session | None = None,
        cache: MetadataCache | None = None,
        *,
        direction: str | None = None,
        coverage: str | None = None,
        resolution: str | None = None,
    ):
        """
        Initialize a GUGiK image provider.

        Parameters
        ----------
        source : str
            Descriptor key of the product (``pl.gugik.orto``,
            ``pl.gugik.intensity``, ``pl.gugik.true_orto``,
            ``pl.gugik.oblique_orto``).
        session : requests.Session, optional
            HTTP session to use for requests.
        cache : MetadataCache, optional
            Metadata cache instance for caching index (skorowidz) lookups.
            If None, no caching is performed (default behavior).
        direction : str, optional
            View direction of an oblique image (``n``, ``e``, ``s``, ``w``):
            required for a product with directions, rejected for the others.
        coverage : str, optional
            WCS coverage of an area cutout (``WcsCutoutParams.variant`` of a
            source with several cutout channels); ``None`` for a source with
            one. ``download_bbox`` then aligns the area to multiples of
            ``resolution`` and fetches it in chunks.
        resolution : str, optional
            Cutout pixel, a label K2 of the channel (e.g. "0.05m", "0.25m");
            required for a cutout.

        Raises
        ------
        ValidationError
            A source without a sheet index, a missing or unknown direction,
            ``coverage`` or ``resolution`` outside the registry channel or
            one without the other where the source needs both.
        """
        super().__init__()
        self._sessions = SessionPerThread(session)
        self._cache = cache
        self.descriptor_key = source
        self._descriptor = get_source(source)
        self._index_channel = sheet_index_channel(source)
        self._index = sheet_index(source)
        self._direction = self._checked_direction(direction)
        self._cutout: AccessChannel | None = None
        if coverage is None and resolution is None:
            return
        product = self._descriptor.product
        channels = wcs_cutout_channels(source)
        if not channels:
            raise ValidationError(
                f"--product {product} nie ma wycinka WCS - pomin --coverage i "
                "--resolution",
                options=("coverage", "resolution"),
            )
        if coverage is None and len(channels) > 1:
            raise ValidationError(
                f"--resolution --product {product} dotyczy tylko wycinka WCS - "
                f"podaj --coverage: {coverage_choices(source)}",
                option="coverage",
                allowed=tuple(_params(c).variant for c in channels),
            )
        error = cutout_choice_error(source, coverage, resolution)
        if error is not None:
            raise error
        step = parse_resolution(resolution) if resolution is not None else None
        assert step is not None  # cutout_choice_error accepted the label
        self._cutout = wcs_cutout_channel(source, coverage)
        params = _params(self._cutout)
        # Result grid at multiples of the pixel (SCALEFACTOR = native / pixel)
        # and the request budget in coverage pixels (plan_wcs_chunks).
        self.WCS_GRID = GridSpec(step=float(step))
        self.WCS_NATIVE_STEP = float(params.native_step)
        self.WCS_CHUNK_LIMITS = replace(
            GugikWcsMixin.WCS_CHUNK_LIMITS, max_pixels=params.max_native_pixels
        )

    def _checked_direction(self, direction: object) -> str | None:
        """``direction`` of the request, checked against the source."""
        codes = [code for code, _ in self._index.directions]
        product = self._descriptor.product
        if not codes:
            if direction is not None:
                raise ValidationError(
                    f"--direction dotyczy tylko orto ukosnej - --product {product} "
                    "nie ma kierunkow"
                )
            return None
        if direction not in codes:
            raise ValidationError(
                f"--product {product}: kierunek {direction!r} - dostepne: "
                f"{', '.join(codes)}"
            )
        assert isinstance(direction, str)  # one of the codes
        return direction

    @property
    def name(self) -> str:
        """Return provider name."""
        return f"GUGiK {self._descriptor.name}"

    @property
    def base_url(self) -> str:
        """Return base URL for GUGiK service."""
        return self.BASE_URL

    @property
    def default_extension(self) -> str:
        """Return default file extension of the product (``.tif``)."""
        return self._descriptor.default_extension

    @property
    def direction(self) -> str | None:
        """View direction of the files of this provider (``None``: none)."""
        return self._direction

    @property
    def storage_suffix(self) -> str | None:
        """Return the file name suffix in the store.

        ``_<direction>`` of an oblique image (the four files of a sheet share one
        segment); the record file name ends with it too
        (``..._7.125.11.08_N.tif``, compared without case).
        """
        return f"_{self._direction}" if self._direction is not None else None

    @property
    def sheet_scale(self) -> str:
        """Return the PL-1992 sheet level of the records.

        ``1:5000`` = the 8-part codes of the true orthophotomap.
        """
        return series_scale(self._index.sheet_parts)

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
        Download the image of a map sheet from OpenData.

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
            none has this sheet (in the requested variant and direction and
            the sheet's coordinate system; other variants are listed in the
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
        """Return the URL of the newest index record of the request."""
        return self._resolve_sheet(sheet, timeout).url

    def _layers(self, endpoint: str, timeout: float | None = None) -> list[str]:
        """Return the index layers.

        The layer of the direction, the fixed layers of the
        descriptor, or (none fixed) the yearly layers of GetCapabilities.
        """
        if self._direction is not None:
            return [dict(self._index.directions)[self._direction]]
        if self._index.layers:
            return list(self._index.layers)
        return super()._layers(endpoint, timeout)

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Cache key per product and direction; the direction as a hard filter."""
        direction = self._direction
        return SkorowidzQuery(
            cache_key=(
                self._descriptor.product,
                direction or "none",
                "none",
                parser.sheet,
            ),
            endpoint=self._index_channel.endpoint,
            predicate=(
                None
                if direction is None
                else lambda record: record.raw.get("kierunek") == direction.upper()
            ),
            source_extra={"direction": direction} if direction is not None else None,
            no_coverage=self._no_coverage,
        )

    def _no_coverage(
        self, parser: SheetParser, records: list[SkorowidzRecord]
    ) -> NoCoverageError:
        what = f"--product {self._descriptor.product}"
        if self._direction is not None:
            what += f" (kierunek {self._direction})"
        message = (
            f"Brak danych {what} dla {parser.sheet} (uklad PL-{parser.sheet_system})"
        )
        hints = coverage_hints(parser, records)
        if self._index.extent is not None:
            hints.add(self._index.extent)
        return no_coverage_error(parser, message, hints)

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
        Download the image of a bounding box from WCS.

        With a cutout channel (``resolution``): the bbox aligned OUTWARD to
        multiples of the pixel (widened by at most 1 px east and south to an
        even size, cropped back), requested from the channel's service with
        ``SCALEFACTOR`` when the pixel differs from the coverage step, in
        chunks within the channel budget of coverage pixels, each chunk
        waiting at least ``WCS_CUTOUT_READ_TIMEOUT`` s for data, stitched
        without resampling. Without one: the raw request of the product
        (``RAW_WCS_TARGET``, the orthophotomap Standard Resolution) with the
        bbox as given.

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the file should be saved
        format : str, optional
            Output format: "GTiff", "PNG", or "JPEG" (default: "GTiff"); a
            cutout is GTiff only
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
            If format is not supported, bbox CRS is not EPSG:2180 or the
            provider has neither a cutout channel nor a raw WCS request
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
        if self._cutout is None:
            if self.RAW_WCS_TARGET is None:
                raise ValidationError(
                    f"--product {self._descriptor.product}: obszar WCS tylko jako "
                    "wycinek (podaj resolution wycinka)"
                )
        else:
            if format != "GTiff":
                raise ValidationError(
                    f"Wycinek WCS (coverage) jest tylko GTiff - podano "
                    f"format {format!r}; PNG/JPEG: provider bez coverage"
                )
            timeout = max(timeout, self.WCS_CUTOUT_READ_TIMEOUT)

        return self._download_wcs(
            bbox,
            Path(output_path),
            format,
            timeout,
            f"{self._descriptor.product} bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
            f"({bbox.max_x:.0f},{bbox.max_y:.0f})",
        )

    def _wcs_target(self) -> tuple[str, str]:
        """Return the endpoint and coverage of the WCS cutout channel.

        Without one the raw request of the product (``download_bbox`` checked it
        exists).
        """
        if self._cutout is None:
            assert self.RAW_WCS_TARGET is not None  # download_bbox checked it
            return self.RAW_WCS_TARGET
        return self._cutout.endpoint, _params(self._cutout).coverage_id


class GugikOrtoProvider(GugikImageProvider):
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

    WCS_ENDPOINT = (
        f"{GugikImageProvider.BASE_URL}/wss/service/PZGIK/ORTO/WCS/StandardResolution"
    )
    COVERAGE_ID = "Orthoimagery_StandardResolution"
    RAW_WCS_TARGET = (WCS_ENDPOINT, COVERAGE_ID)

    DOWNLOAD_LABEL = "Ortofoto OpenData"

    # The index of the registry channel (``SheetIndexParams`` of pl.gugik.orto).
    WMS_INDEX_ENDPOINT = sheet_index_channel(ORTO_KEY).endpoint

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

    def __init__(
        self,
        session: requests.Session | None = None,
        cache: MetadataCache | None = None,
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
        self._color = color
        super().__init__(
            ORTO_KEY, session, cache, coverage=coverage, resolution=resolution
        )
        if self._cutout is not None and color != self.DEFAULT_COLOR:
            raise ValidationError(
                f"wycinek WCS ortofotomapy ma tylko kompozycje {self.DEFAULT_COLOR} "
                f"- podano color={color!r}"
            )

    @property
    def name(self) -> str:
        """Return provider name."""
        return "GUGiK Ortofotomapa"

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

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Cache key per colour variant; hard CRS + colour filter."""
        return SkorowidzQuery(
            cache_key=(self._CACHE_PRODUCT, self._color, "none", parser.sheet),
            endpoint=self._index_channel.endpoint,
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


def image_provider(
    product: str,
    *,
    cache: MetadataCache | None = None,
    direction: str | None = None,
    session: requests.Session | None = None,
) -> GugikImageProvider:
    """Provide the sheets of an image product (``download_data``).

    The RGB composition of the orthophotomap (``product="orto"``), the other
    image products by their descriptor, one ``direction`` of an oblique image.

    Raises
    ------
    ValidationError
        Not an image product of a sheet index, or a wrong ``direction``.
    """
    source = image_source(product)
    if source is None:
        raise ValidationError(f"Nieobslugiwany produkt obrazow PL: {product}")
    if source.key == ORTO_KEY:
        if direction is not None:
            raise ValidationError(
                "--direction dotyczy tylko orto ukosnej - --product orto nie ma "
                "kierunkow"
            )
        return GugikOrtoProvider(session, cache, color=GugikOrtoProvider.DEFAULT_COLOR)
    return GugikImageProvider(source.key, session, cache, direction=direction)
