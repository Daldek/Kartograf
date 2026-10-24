"""
GUGiK provider of NMT sheets: every grid resolution and the archive formats.

The provider serves ONE variant of the product (ADR-041,
``kartograf.sources.variants``): resolution, height system and file format
chosen at construction. Two download modes:

- Sheet code -> the newest record of the variant in the WFS sheet index
  (skorowidz) -> the file from OpenData: ASC grids in every resolution GUGiK
  publishes, archive formats (XYZ, ASCII-NMT, TBD, TIN, TTN, GRD, DXF, DGN)
  as the original file (no conversion);
- BBox -> WCS (1 m grid variants only; EVRF2007 heights requested as
  image/x-aaigrid and written as GeoTIFF float32).

The format and the resolution are hard filters of the record (ADR-028):
the same sheet and delivery is often published in two formats.
"""

import logging
import threading
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.bbox import BBox
from kartograf.core.coverage import Polygon
from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import (
    DownloadError,
    NoCoverageError,
    ValidationError,
)
from kartograf.providers.base import BaseProvider
from kartograf.providers.pl.skorowidz import (
    SkorowidzQuery,
    SkorowidzRecord,
    coverage_hints,
    no_coverage_error,
)
from kartograf.providers.pl.skorowidz_wfs import (
    WfsSkorowidzLayersMixin,
    area_envelope,
    feature_footprint,
    index_records,
    overlaps_area,
    parse_index_feature,
    sheet_frame_2180,
    sheet_query_bbox,
    type_year,
)
from kartograf.providers.pl.wcs import HEIGHT_AAIGRID, HEIGHT_GTIFF, GugikWcsMixin
from kartograf.sources.descriptor import TransportKind
from kartograf.sources.registry import get_source
from kartograf.sources.variants import (
    ProductVariant,
    file_format,
    find_variant,
    resolution_label,
    source_format,
    variants,
)
from kartograf.transport.chunks import GridSpec
from kartograf.transport.http import (
    MAX_RETRIES,
    SessionPerThread,
)

logger = logging.getLogger(__name__)


def _zone(parser: SheetParser) -> int | None:
    return int(parser.sheet.split(".")[0]) if parser.sheet_system == "2000" else None


class GugikProvider(WfsSkorowidzLayersMixin, GugikWcsMixin, BaseProvider):
    """
    Provider of one NMT variant from GUGiK (sheets from the WFS index, WCS 1 m).

    The variant comes from the registry (``kartograf.sources.variants``):
    ``resolution`` is a label K2 (``"0.5m"``, ``"1m"``, ...; ``None`` only
    for formats without a resolution - TIN, TTN - or when the format and
    height system leave exactly one), ``vertical_crs`` ``"EVRF2007"`` or
    ``"KRON86"``, ``format`` a token of ``kartograf.sources.variants.FORMATS``
    (``"ASC"`` = the grid). A combination outside the registry raises
    ``ValidationError`` naming the available values.

    Examples
    --------
    >>> provider = GugikProvider(vertical_crs="EVRF2007", resolution="0.5m")
    >>> provider.download("N-33-58-A-c-1-4", Path("./sheet.asc"))
    >>>
    >>> # Bbox -> GeoTIFF float32 from WCS (1m grid variants only)
    >>> provider = GugikProvider(vertical_crs="KRON86", resolution="1m")
    >>> from kartograf import BBox
    >>> bbox = BBox(450000, 550000, 451000, 551000, "EPSG:2180")
    >>> provider.download_bbox(bbox, Path("./area.tif"))
    >>>
    >>> # Archive: the original TBD 25 m file (ZIP)
    >>> provider = GugikProvider(vertical_crs="KRON86", resolution="25m", format="TBD")
    >>> provider.download("M-34-64-D-d-2", Path("./sheet.zip"))
    """

    # Product of the variant registry served by this class (NMPT overrides)
    PRODUCT = "nmt"

    # Base URL for GUGiK services
    BASE_URL = "https://mapy.geoportal.gov.pl"

    # WCS endpoints for NMT data (by vertical CRS) - 1m grid variants only.
    # KRON86 heights come as float32 GeoTIFF from the TIFF endpoint; EVRF2007
    # heights only as image/x-aaigrid from DigitalTerrainModel (its image/tiff is
    # RGB) - docs/research/2026-10-11-wcs-cutouts/raport.md, point 1.
    WCS_ENDPOINTS = {
        "KRON86": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/"
        "DigitalTerrainModelFormatTIFF",
        "EVRF2007": f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModel",
    }

    # Vertical CRS whose WCS endpoint GUGiK withdrew: download_bbox fails before
    # the network. None today (the EVRF2007 entry pointed at a non-existent
    # endpoint until 0.7.2); kept as the mechanism for future withdrawals.
    WITHDRAWN_WCS_VERTICAL_CRS: tuple[str, ...] = ()

    # Coverage IDs for WCS (by vertical CRS) - 1m grid variants only
    COVERAGE_IDS = {
        "KRON86": "DTM_PL-KRON86-NH_TIFF",
        "EVRF2007": "DTM_PL-EVRF2007-NH",
    }

    # How heights of each vertical CRS are requested (GugikWcsMixin.HEIGHT_*).
    WCS_HEIGHT_FORMAT = {"KRON86": HEIGHT_GTIFF, "EVRF2007": HEIGHT_AAIGRID}

    # NMT 1 m sheet grid: step 1 m, pixel edges at k + 0.5 m - measured in 9
    # regions of Poland and identical to the OpenData sheets
    # (docs/research/2026-10-10-wcs-limits/raport.md, points 4 and 7).
    WCS_GRID: GridSpec | None = GridSpec(step=1.0, origin_x=0.5, origin_y=0.5)
    WCS_NATIVE_STEP: float | None = 1.0

    # Default settings
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = MAX_RETRIES

    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        vertical_crs: str,
        resolution: str | None,
        format: str = "ASC",
        cache: MetadataCache | None = None,
    ):
        """
        Initialize the provider of one variant.

        Parameters
        ----------
        session : requests.Session, optional
            HTTP session to use for requests.
        vertical_crs : str
            "EVRF2007" (current heights) or "KRON86" (legacy Kronsztadt 86).
        resolution : str or None
            Label K2 of the variant ("0.15m", "0.5m", "0.6m", "1m", "5m",
            "10m"; archives also "15m".."50m"); None for TIN/TTN or when
            the format and height system leave one variant.
        format : str
            "ASC" (grid, default) or an archive token ("XYZ", "ASCII-NMT",
            "TBD", "TIN", "TTN", "GRD", "DXF", "DGN").
        cache : MetadataCache, optional
            Metadata cache for index records; None disables caching.

        Raises
        ------
        ValidationError
            The combination is not a registered variant (the message lists
            the available resolutions/height systems/formats).
        """
        self.variant: ProductVariant = find_variant(
            product=self.PRODUCT,
            country="PL",
            resolution=resolution,
            vertical_crs=vertical_crs,
            format=format,
        )
        super().__init__()
        self._sessions = SessionPerThread(session)
        self._vertical_crs = vertical_crs
        self._resolution = self.variant.label
        self._cache = cache
        # Index services the provider may ask: every height system of the
        # product (P10 hints ask the other one)
        self._index_refs = {
            v.index_ref.endpoint: v.index_ref
            for v in variants(product=self.PRODUCT, country="PL")
            if v.index_ref is not None
        }
        # Variant index endpoints that failed (P10): skipped from then on
        self._failed_variants: set[str] = set()
        self._failed_variants_lock = threading.Lock()
        self.descriptor_key = self.variant.source

    @property
    def vertical_crs(self) -> str:
        """Return current vertical CRS."""
        return self._vertical_crs

    @property
    def resolution(self) -> str | None:
        """Resolution label K2 of the variant (``None``: TIN/TTN)."""
        return self._resolution

    @property
    def format(self) -> str:
        """File format token of the variant (``"ASC"`` = grid)."""
        return self.variant.format

    @property
    def name(self) -> str:
        """Return provider name."""
        return "GUGiK"

    @property
    def default_extension(self) -> str:
        """Extension of the variant's files (``.asc`` grids, archives per format)."""
        return file_format(self.variant.format).extension

    @property
    def base_url(self) -> str:
        """Return base URL for GUGiK service."""
        return self.BASE_URL

    def describe(self, variant: ProductVariant | None = None) -> str:
        """``NMT 0.5m``, ``NMT TBD 25m``, ``NMT TIN`` - a variant in messages."""
        v = variant or self.variant
        parts = [self.PRODUCT.upper()]
        if v.source_file:
            parts.append(v.format)
        if v.label is not None:
            parts.append(v.label)
        return " ".join(parts)

    # =========================================================================
    # Download by sheet code -> OpenData
    # =========================================================================

    def download(
        self,
        sheet: str,
        output_path: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download the variant's file of a map sheet from OpenData.

        Parameters
        ----------
        sheet : str
            Map sheet identifier (e.g., "N-34-130-D-d-2-4")
        output_path : Path
            Where the file is saved (``default_extension`` of the variant)
        timeout : int, optional
            Request timeout in seconds (default: 30)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        NoCoverageError
            Subclass of ``DownloadError``: the index answered and has no
            record of the variant for this sheet (sea, the Czech side of a
            border bbox, another resolution or format only). Hints name the
            variants the index has (``--resolution``, ``--format``,
            ``--vertical-crs``). ``DownloadManager`` records such sheets in
            ``DownloadResult.no_coverage``; the PL cutout fills them with
            nodata (ADR-027).
        DownloadError
            The index query fails after retries or its answer is invalid, or
            the file download fails after retries. An older campaign is never
            substituted after a failed query. Also when the record declares
            another vertical datum than ``vertical_crs``
            (``verify_record_vertical_crs``; nothing is downloaded).
        """
        # local import: the kartograf.download package imports manager -> providers.pl
        from kartograf.download.campaigns import verify_record_vertical_crs

        record = self._resolve_sheet(sheet, timeout)
        verify_record_vertical_crs(record, self._vertical_crs, sheet)
        return self.download_record(record, Path(output_path), timeout)

    def _get_opendata_url(self, sheet: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Return the URL of the strictly matching, newest index record."""
        return self._resolve_sheet(sheet, timeout).url

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Cache key, WFS endpoint and hard filter of the variant."""
        variant = self.variant
        assert variant.index_ref is not None  # PL sheet variants have an index
        return SkorowidzQuery(
            cache_key=(
                variant.source,
                variant.label or "-",
                self._vertical_crs,
                parser.sheet,
            ),
            endpoint=variant.index_ref.endpoint,
            resolution_m=(
                float(variant.resolution_m)
                if variant.resolution_m is not None
                else None
            ),
            predicate=self._in_format,
            require_resolution=variant.resolution_m is not None,
            no_coverage=self._no_coverage,
        )

    def _in_format(self, record: SkorowidzRecord) -> bool:
        """Check whether the record matches the variant's format.

        The record's ``format`` AND URL give the variant's format token.
        """
        return source_format(record.file_format, record.url) == self.variant.format

    def record_variant(
        self, record: SkorowidzRecord, vertical_crs: str
    ) -> ProductVariant | None:
        """Return the registered variant of an index record of this product.

        ``None``: inconsistent record or a combination outside the registry.
        """
        token = source_format(record.file_format, record.url)
        if token is None:
            return None
        label = (
            None
            if record.resolution_m is None
            else resolution_label(Decimal(repr(record.resolution_m)))
        )
        found = variants(
            product=self.PRODUCT,
            country="PL",
            vertical_crs=vertical_crs,
            format=token,
        )
        return next((v for v in found if v.label == label), None)

    def _hint(self, variant: ProductVariant) -> str:
        """Hint naming another variant of the sheet (no sheet code in the text)."""
        flags = []
        if variant.format != self.variant.format:
            flags.append(f"--format {variant.format}")
        if variant.label is not None and variant.label != self.variant.label:
            flags.append(f"--resolution {variant.label}")
        if variant.vertical_crs != self._vertical_crs:
            flags.append(f"--vertical-crs {variant.vertical_crs}")
        return (
            f"Skorowidz GUGiK ma ten arkusz w {self.describe(variant)} "
            f"{variant.vertical_crs} - uzyj {' '.join(flags)}"
        )

    def _no_coverage(
        self, parser: SheetParser, records: list[SkorowidzRecord]
    ) -> NoCoverageError:
        """No record of the variant: hints from the same answer, P10 by WFS.

        Other variants of the sheet in the answer (the WFS query holds every
        format and resolution of the point) give hints without network: the
        same format first, other formats only when the format has none; an
        inconsistent record (``format`` vs URL) is named once. The other
        height system costs one query (``_variant_hints``).
        """
        zone = _zone(parser)
        own = [
            r
            for r in records
            if r.sheet == parser.sheet
            and r.system == parser.sheet_system
            and (zone is None or r.zone == zone)
        ]
        wanted = self.variant.resolution_m
        matching = [
            r
            for r in records
            if self._in_format(r)
            and (
                wanted is None
                or (
                    r.resolution_m is not None
                    and abs(r.resolution_m - float(wanted)) < 1e-6
                )
            )
        ]
        hints = coverage_hints(parser, matching)
        others = {
            v
            for r in own
            if (v := self.record_variant(r, self._vertical_crs)) is not None
            and v != self.variant
        }
        same_format = {v for v in others if v.format == self.variant.format}
        hints |= {self._hint(v) for v in (same_format or others)}
        if not others:
            unsupported = sorted(
                {
                    f"{r.file_format or 'bez formatu'} "
                    f"(plik {r.url.rsplit('/', 1)[-1].rsplit('.', 1)[-1]})"
                    for r in own
                    if self.record_variant(r, self._vertical_crs) is None
                }
            )
            if unsupported:
                hints.add(
                    "Skorowidz GUGiK ma dla tego arkusza tylko rekordy, ktorych "
                    f"Kartograf nie pobiera: {', '.join(unsupported)} (format "
                    "rekordu niezgodny z plikiem albo wariant spoza rejestru)"
                )
        hints |= self._variant_hints(parser)
        return no_coverage_error(
            parser,
            f"Brak danych {self.describe()} dla {parser.sheet} "
            f"(uklad PL-{parser.sheet_system}, {self._vertical_crs})",
            hints,
        )

    def _other_services(self) -> list[tuple[str, str]]:
        """``(endpoint, vertical CRS)`` of the other height systems of the format."""
        found: dict[str, str] = {}
        for v in variants(
            product=self.PRODUCT, country="PL", format=self.variant.format
        ):
            vertical_crs = v.vertical_crs
            if (
                vertical_crs is not None
                and vertical_crs != self._vertical_crs
                and v.index_ref is not None
            ):
                found.setdefault(v.index_ref.endpoint, vertical_crs)
        return list(found.items())

    def _variant_hints(self, parser: SheetParser) -> set[str]:
        """Return hints naming the variants of the format in the OTHER height system.

        Those whose index has the sheet (P10, 0.7.2; WFS since 0.8.0).

        One GetFeature with every yearly type of that service around the
        sheet centre; a record passes the same hard filter as a download
        (sheet code, horizontal CRS, zone, format). Advisory: a failed query
        is logged and gives no hint - it never turns the no-coverage result
        into an error. One attempt per query and a failed service is skipped
        for the rest of the provider's life, so an outage of an index the
        user did not ask for costs one timeout, not one per sheet. The hint
        text has no sheet code, so the CLI shows one line for many sheets.
        """
        hints: set[str] = set()
        zone = _zone(parser)
        for endpoint, vertical_crs in self._other_services():
            with self._failed_variants_lock:
                if endpoint in self._failed_variants:
                    continue
            try:
                types = self._layers(endpoint)[0].split(",")
                records = index_records(
                    self._wfs_index(endpoint, retries=1),
                    sheet_query_bbox(parser),
                    types,
                )
            except DownloadError as e:
                with self._failed_variants_lock:
                    self._failed_variants.add(endpoint)
                logger.warning(
                    "%s: nie sprawdzono ukladu %s (podpowiedz pominieta, "
                    "usluga pomijana do konca zadania): %s",
                    parser.sheet,
                    vertical_crs,
                    e,
                )
                continue
            for record in records:
                if (
                    record.sheet != parser.sheet
                    or record.system != parser.sheet_system
                    or (zone is not None and record.zone != zone)
                ):
                    continue
                variant = self.record_variant(record, vertical_crs)
                if variant is not None and variant.format == self.variant.format:
                    hints.add(self._hint(variant))
        return hints

    # =========================================================================
    # Sheets of an area from the index (archive formats)
    # =========================================================================

    def index_sheets(
        self,
        areas: Sequence[Polygon],
        *,
        system: str,
        min_year: int | None = None,
        max_year: int | None = None,
    ) -> list[str]:
        """Sheet codes of the variant's records overlapping ``areas``.

        Archive formats are published on sheets of several scales (1:25000
        and 1:10000 frames of the same variant, PL-2000 sheets), so their
        sheets come from the index, not from the sheet grid: one GetFeature
        for the envelope of ``areas`` (convex EPSG:2180 polygons, (E, N)),
        types and records within the year bounds, the variant's format and
        resolution, horizontal system ``system`` ("1992" or "2000"); a
        record counts when its frame overlaps an area by more than an edge
        sliver (``overlaps_area``). Sorted sheet codes; ``[]`` = the index
        has no such record (a valid answer).

        Raises
        ------
        DownloadError
            The index query fails (never an empty result).
        """
        # local import: the kartograf.download package imports manager -> providers.pl
        from kartograf.download.campaigns import in_year_range, record_year

        variant = self.variant
        assert variant.index_ref is not None
        endpoint = variant.index_ref.endpoint
        ranged = min_year is not None or max_year is not None
        types = [
            t
            for t in self._layers(endpoint)[0].split(",")
            if not ranged or in_year_range(type_year(t), min_year, max_year)
        ]
        if not types or not areas:
            return []
        wanted = variant.resolution_m
        found: set[str] = set()
        index = self._wfs_index(endpoint)
        for feature in index.features(area_envelope(areas), types):
            record = parse_index_feature(feature)
            if (
                record is None
                or record.system != system
                or not self._in_format(record)
                or (
                    ranged
                    and not in_year_range(record_year(record), min_year, max_year)
                )
            ):
                continue
            if wanted is not None and (
                record.resolution_m is None
                or abs(record.resolution_m - float(wanted)) >= 1e-6
            ):
                continue
            frame = feature_footprint(feature) or sheet_frame_2180(record.sheet)
            if any(overlaps_area(frame, area) for area in areas):
                found.add(record.sheet)
        return sorted(found)

    # =========================================================================
    # Download by bbox -> WCS (GeoTIFF/PNG/JPEG)
    # =========================================================================

    def has_wcs(self) -> bool:
        """Check whether the variant's descriptor has a WCS channel (1 m grids)."""
        return any(
            channel.transport == TransportKind.WCS
            for channel in get_source(self.variant.source).channels
        )

    def download_bbox(
        self,
        bbox: BBox,
        output_path: Path,
        format: str = "GTiff",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Path:
        """
        Download the area of a bounding box from WCS (1 m grid variants).

        Use this method when you need data for an arbitrary area
        (not aligned to standard map sheets).

        Parameters
        ----------
        bbox : BBox
            Bounding box in EPSG:2180 coordinates
        output_path : Path
            Path where the file should be saved
        format : str, optional
            Output format: "GTiff", "PNG", or "JPEG" (default: "GTiff")
        timeout : int, optional
            Request timeout in seconds (default: 30)

        Returns
        -------
        Path
            Path to the downloaded file

        Raises
        ------
        DownloadError
            If the download fails
        ValidationError
            If the variant has no WCS channel (only the 1 m grid has one),
            format is not supported, bbox CRS is not EPSG:2180, or the
            vertical CRS is in ``WITHDRAWN_WCS_VERTICAL_CRS`` (none today)

        Notes
        -----
        GeoTIFF: the file extent is the bbox expanded OUTWARD to the 1 m sheet
        grid (``WCS_GRID``: pixel edges at k + 0.5 m, < 1 px per side), because
        the server resamples to the requested grid and an off-grid bbox would
        shift the content by a fraction of a pixel; on that grid the content
        equals the OpenData 1 m sheets of the flight the server shows. The area
        is fetched in chunks (``plan_wcs_chunks``) and stitched without
        resampling (ADR-034). Heights are float32 with no nodata: KRON86 as
        GeoTIFF (16 Mpx chunks), EVRF2007 as ``image/x-aaigrid`` converted to
        GeoTIFF in EPSG:2180 (1 Mpx chunks, ~20 s/Mpx). PNG/JPEG: one request
        with the bbox as given (preview). An OGC exception report is raised as
        ``DownloadError``, never saved.
        """
        if not self.has_wcs():
            raise ValidationError(
                f"Pobieranie WCS (download_bbox) jest dostepne tylko dla siatki "
                f"{self.PRODUCT.upper()} 1m - {self.describe()} pobierz przez "
                "download() (arkusze)"
            )

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

        if self._vertical_crs in self.WITHDRAWN_WCS_VERTICAL_CRS:
            raise ValidationError(
                f"WCS {self.PRODUCT.upper()} 1m dla {self._vertical_crs} "
                "nie jest "
                "dostepny (usluga wycofana przez GUGiK). Pobierz arkusze przez "
                "godlo."
            )

        return self._download_wcs(
            bbox,
            Path(output_path),
            format,
            timeout,
            f"bbox ({bbox.min_x:.0f},{bbox.min_y:.0f})-"
            f"({bbox.max_x:.0f},{bbox.max_y:.0f})",
        )

    def _wcs_target(self) -> tuple[str, str]:
        """WCS endpoint and coverage for the provider's vertical CRS."""
        return (
            self.WCS_ENDPOINTS[self._vertical_crs],
            self.COVERAGE_IDS[self._vertical_crs],
        )

    def _wcs_height_format(self) -> str:
        """``HEIGHT_GTIFF`` or ``HEIGHT_AAIGRID`` for the provider's vertical CRS."""
        return self.WCS_HEIGHT_FORMAT[self._vertical_crs]

    def is_wcs_available(self) -> bool:
        """
        Check if WCS download is available for current configuration.

        WCS exists only for the 1 m grid variant (registry: a WCS channel of
        the descriptor) and not for a vertical CRS listed in
        ``WITHDRAWN_WCS_VERTICAL_CRS`` (none today).
        """
        return self.has_wcs() and self._vertical_crs not in (
            self.WITHDRAWN_WCS_VERTICAL_CRS
        )
