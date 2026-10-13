"""GUGiK index (skorowidz) records: parsing, strict selection and sheet origin."""

import json
import logging
import re
import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import (
    DownloadError,
    NoCoverageError,
    ParseError,
    ValidationError,
)
from kartograf.sources.registry import parse_pl_system
from kartograf.transport.http import SessionPerThread, download_to, get_with_retry

logger = logging.getLogger(__name__)

_RECORD = re.compile(r"\.push\(\s*\{(.*?)\}\s*\)", re.DOTALL)
_FIELD = re.compile(r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*")')
# GUGiK MapServer HTML template: an empty response (sea, abroad) has only the
# header with the createTable function (gfi/01-04 of 2026-09-29); the record
# array declaration `var X = [];` appears only together with records.
_TEMPLATE = re.compile(r"\bvar\s+\w+\s*=\s*\[\s*\]\s*;|\bfunction\s+createTable\s*\(")
_OGC_REPORT = re.compile(r"<(?:\w+:)?(?:ServiceException|ExceptionReport)\b")
_OGC_TEXT = re.compile(
    r"<(?:\w+:)?(?:ServiceException|ExceptionText)\b[^>]*>(.*?)</", re.DOTALL
)


def _horizontal_crs(value: str | None) -> tuple[str | None, int | None]:
    """``(system, zone)`` of a record; ``(None, None)`` = record without a CRS
    (rejected in ``select_sheet_record``). Parser: ``parse_pl_system`` (D3)."""
    return parse_pl_system(value) or (None, None)


def _metres(value: str | None) -> float | None:
    """'0.15' / '0,15' / '0.15 m' -> 0.15; None when missing or unparseable."""
    if value is None:
        return None
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:m)?\s*", value)
    return float(match[1].replace(",", ".")) if match else None


@dataclass(frozen=True)
class SkorowidzRecord:
    url: str
    sheet: str
    aktualnosc: str
    dt_pzgik: str | None
    layer: str
    system: str | None
    zone: int | None
    resolution_m: float | None
    full_sheet: bool | None
    raw: dict[str, str]

    @property
    def file_format(self) -> str | None:
        """The record's ``format`` field (NMT: ``ARC/INFO ASCII GRID``; orto: none)."""
        return self.raw.get("format")

    def to_source(self, endpoint: str) -> dict:
        """Metadata of the selected file for the sidecar and the record cache.

        Keys follow the sidecar schema ``kartograf-meta/1`` (English names,
        ADR-031); GUGiK record fields are mapped here, in one place.
        """
        return {
            "url": self.url,
            "index_url": endpoint,
            "layer": self.layer,
            "sheet": self.sheet,
            "acquisition_date": self.aktualnosc,
            "acquisition_year": self.raw.get("aktualnoscRok") or self.aktualnosc[:4],
            "pzgik_date": self.dt_pzgik,
            "resolution_m": self.resolution_m,
            "declared_crs": self.raw.get("ukladWspolrzednychPoziomych")
            or self.raw.get("ukladWspolrzednych"),
            "full_sheet": self.full_sheet,
            "survey_work_id": self.raw.get("numerZgloszeniaPracy"),
            "data_source": self.raw.get("zrDanych") or self.raw.get("zrodloDanych"),
            "format": self.raw.get("format"),
            "height_rmse_m": _metres(self.raw.get("bladSredniWysokosci")),
            "position_rmse_m": _metres(self.raw.get("bladSredniPolozenia")),
            "archive_module": self.raw.get("modulArchiwizacji"),
            "declared_vertical_crs": self.raw.get("ukladWspolrzednychPionowych"),
        }

    @classmethod
    def from_source(cls, source: dict) -> "SkorowidzRecord":
        """Restore the selected record from a cache payload (no reselection).

        Raises ``KeyError`` when a required key (``url``, ``sheet``,
        ``acquisition_date``, ``layer``, ``archive_module``) is missing — e.g.
        a cache entry written before ADR-031 with Polish key names, or before
        0.7.1 without the accuracy keys; callers treat that as a cache miss
        (``cached_record``). ``archive_module`` itself may be ``None``.
        """
        if "archive_module" not in source:
            # 0.7.1 key: older cache entries are a miss (cached_record)
            raise KeyError("archive_module")
        system, zone = _horizontal_crs(source.get("declared_crs") or "")
        raw = {
            key: str(source[field])
            for key, field in (
                ("ukladWspolrzednychPoziomych", "declared_crs"),
                ("aktualnoscRok", "acquisition_year"),
                ("numerZgloszeniaPracy", "survey_work_id"),
                ("zrDanych", "data_source"),
                ("format", "format"),
                ("bladSredniWysokosci", "height_rmse_m"),
                ("bladSredniPolozenia", "position_rmse_m"),
                ("modulArchiwizacji", "archive_module"),
                ("ukladWspolrzednychPionowych", "declared_vertical_crs"),
            )
            if source.get(field) is not None
        }
        return cls(
            url=source["url"],
            sheet=source["sheet"],
            aktualnosc=source["acquisition_date"],
            dt_pzgik=source.get("pzgik_date"),
            layer=source["layer"],
            system=system,
            zone=zone,
            resolution_m=source.get("resolution_m"),
            full_sheet=source.get("full_sheet"),
            raw=raw,
        )


def cached_record(source: object) -> SkorowidzRecord | None:
    """Record restored from a ``record_cache``/``campaigns_cache`` payload.

    ``None`` = unusable payload (not a dict, missing keys — an entry written
    before ADR-031 with Polish key names): the caller treats it as a cache
    miss, resolves the sheet again and overwrites the entry.
    """
    if not isinstance(source, dict):
        return None
    try:
        return SkorowidzRecord.from_source(source)
    except (KeyError, TypeError, ValueError):
        return None


def is_skorowidz_answer(text: str) -> bool:
    """Layer answer = GUGiK index template (also an empty one); other HTML is not."""
    return _TEMPLATE.search(text) is not None


def _decode_value(literal: str) -> str:
    try:
        return json.loads(literal)
    except ValueError:  # non-JSON escape (e.g. \') — literal value
        return literal[1:-1]


def parse_skorowidz_records(text: str, layer: str) -> list[SkorowidzRecord]:
    """`X.push({...})` records from GetFeatureInfo; URL not extension-filtered (H1)."""
    records = []
    for match in _RECORD.finditer(text):
        raw = {key: _decode_value(value) for key, value in _FIELD.findall(match[1])}
        url = raw.get("url", "")
        if not url.startswith("https://"):
            logger.warning("Warstwa %s: pominieto rekord bez URL HTTPS", layer)
            continue
        try:
            sheet = SheetParser(raw.get("godlo", "")).sheet
        except (ParseError, ValidationError):
            logger.warning(
                "Warstwa %s: nieprawidlowe godlo %r", layer, raw.get("godlo")
            )
            continue
        system, zone = _horizontal_crs(
            raw.get("ukladWspolrzednychPoziomych") or raw.get("ukladWspolrzednych", "")
        )
        resolution_text = raw.get("charakterystykaPrzestrzenna") or raw.get(
            "wielkoscPiksela", ""
        )
        resolution = _metres(resolution_text)
        full_sheet = raw.get("calyArkuszWypelnionyTrescia") or raw.get(
            "calyArkuszWyeplnionyTrescia"
        )
        record = SkorowidzRecord(
            url=url,
            sheet=sheet,
            aktualnosc=raw.get("aktualnosc", ""),
            dt_pzgik=raw.get("dt_pzgik"),
            layer=layer,
            system=system,
            zone=zone,
            resolution_m=resolution,
            full_sheet={"TAK": True, "NIE": False}.get(full_sheet or ""),
            raw=raw,
        )
        year = re.search(r"(\d{4})(iStarsze)?$", layer)
        record_year = raw.get("aktualnoscRok") or record.aktualnosc[:4]
        if year and record_year.isdigit():
            outside = (
                int(record_year) > int(year[1]) if year[2] else record_year != year[1]
            )
            if outside:
                logger.warning(
                    "Warstwa %s: rekord %s ma rok %s poza partycja warstwy",
                    layer,
                    sheet,
                    record_year,
                )
        records.append(record)
    return records


def _matches(
    record: SkorowidzRecord,
    *,
    sheet: str,
    system: str,
    zone: int | None,
    resolution_m: float | None,
    predicate: Callable[[SkorowidzRecord], bool] | None,
) -> bool:
    """ADR-028 hard filter shared by single-record selection and campaign lists.

    ``sheet`` must already be normalized; called once per record (the warning
    about a missing CRS/resolution is not duplicated).
    """
    if record.system is None or record.resolution_m is None:
        logger.warning(
            "Warstwa %s: rekord %s bez ukladu lub rozdzielczosci - pominieto",
            record.layer,
            record.sheet,
        )
        return False
    if record.sheet != sheet or record.system != system:
        return False
    if system == "2000" and record.zone != zone:
        return False
    if resolution_m is not None and abs(record.resolution_m - resolution_m) >= 1e-6:
        return False
    return predicate is None or predicate(record)


def _campaign_key(record: SkorowidzRecord) -> tuple[str, str, str]:
    return (record.aktualnosc, record.dt_pzgik or "", record.url)


def select_sheet_record(
    records: Iterable[SkorowidzRecord],
    *,
    sheet: str,
    system: str,
    zone: int | None = None,
    resolution_m: float | None = None,
    predicate: Callable[[SkorowidzRecord], bool] | None = None,
) -> SkorowidzRecord | None:
    """Pick the newest campaign meeting ALL requirements of the request."""
    sheet = SheetParser(sheet).sheet
    matching = [
        record
        for record in records
        if _matches(
            record,
            sheet=sheet,
            system=system,
            zone=zone,
            resolution_m=resolution_m,
            predicate=predicate,
        )
    ]
    return max(matching, key=_campaign_key, default=None)


def select_campaign_records(
    records: Iterable[SkorowidzRecord],
    *,
    sheet: str,
    system: str,
    zone: int | None = None,
    resolution_m: float | None = None,
    predicate: Callable[[SkorowidzRecord], bool] | None = None,
) -> list[SkorowidzRecord]:
    """All records passing the ``select_sheet_record`` filter, without
    duplicate URLs, descending by ``(aktualnosc, dt_pzgik, url)``."""
    sheet = SheetParser(sheet).sheet
    unique: dict[str, SkorowidzRecord] = {}
    for record in records:
        if _matches(
            record,
            sheet=sheet,
            system=system,
            zone=zone,
            resolution_m=resolution_m,
            predicate=predicate,
        ):
            unique.setdefault(record.url, record)
    return sorted(unique.values(), key=_campaign_key, reverse=True)


def query_skorowidz_layer(
    session: requests.Session,
    endpoint: str,
    layer: str,
    *,
    query_bbox: str,
    sheet: str,
    timeout: float,
    retries: int = 3,
    label: str | None = None,
) -> list[SkorowidzRecord]:
    """Query one layer; a failure never means no coverage.

    ``layer`` may list several layers (``a,b``: one answer with the records
    of all of them). ``label`` (default ``layer``) becomes
    ``SkorowidzRecord.layer``; with several layers pass a label without a
    trailing year, so the per-layer year check of the parser stays off.
    """
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": layer,
        "QUERY_LAYERS": layer,
        "INFO_FORMAT": "text/html",
        "CRS": "EPSG:2180",
        "BBOX": query_bbox,
        "WIDTH": 100,
        "HEIGHT": 100,
        "I": 50,
        "J": 50,
    }
    description = f"{sheet}: warstwa {layer}"
    response = get_with_retry(
        session,
        f"{endpoint}?{urlencode(params)}",
        timeout=timeout,
        retries=retries,
        description=description,
    )
    text = response.text
    if _OGC_REPORT.search(text):
        match = _OGC_TEXT.search(text)
        excerpt = " ".join((match[1] if match else text).split())[:200]
        raise DownloadError(
            f"{description}: raport wyjatku OGC: {excerpt}", sheet=sheet
        )
    if not is_skorowidz_answer(text):
        raise DownloadError(
            f"{description}: odpowiedz nie jest szablonem skorowidza GUGiK", sheet=sheet
        )
    return parse_skorowidz_records(text, label or layer)


@dataclass(frozen=True)
class SkorowidzQuery:
    """Parameters of sheet resolution at a provider (hook ``_skorowidz_query``)."""

    cache_key: tuple[str, str, str, str]
    endpoint: str | None
    no_coverage: Callable[[SheetParser, list[SkorowidzRecord]], NoCoverageError]
    resolution_m: float | None = None
    predicate: Callable[[SkorowidzRecord], bool] | None = None
    source_extra: dict | None = None


def _zone(parser: SheetParser) -> int | None:
    """PL-2000 zone of the sheet code (record filter); PL-1992 -> ``None``."""
    return int(parser.sheet.split(".")[0]) if parser.system == "2000" else None


def _cached_no_coverage_message(sheet: str) -> str:
    """Message of a cached no-coverage entry written without one (before
    2026-10-07). A cache hit never calls the provider's ``no_coverage`` -
    that may query the network (variant hints, P10)."""
    return f"Brak danych dla {sheet} (z cache metadanych)"


def _current_texts(cached: dict) -> bool:
    """Whether a cached no-coverage entry carries current (ASCII) texts.

    Entries written before 0.8.0 may hold a message or hints with Polish
    diacritics or an em dash; they would break ``Notice`` (ASCII only), so
    such an entry is a cache miss and the index is asked again.
    """
    texts = [cached.get("message") or "", *(cached.get("hints") or ())]
    return all(isinstance(t, str) and t.isascii() for t in texts)


class SourceInfoMixin:
    """Origin per sheet code, independent of thread completion order."""

    def __init__(self) -> None:
        super().__init__()
        self._sources: dict[str, dict] = {}
        self._sources_lock = threading.Lock()

    def _remember_source(self, sheet: str, source: dict) -> None:
        with self._sources_lock:
            self._sources[SheetParser(sheet).sheet] = dict(source)

    def source_info(self, sheet: str) -> dict | None:
        """Origin of the sheet's index record (URL, layer, acquisition date).

        Filled by the single-record flow (``_resolve_record``: ``download``,
        ``get_download_url`` and ``resolve_campaigns(all_campaigns=False)``).
        With ``all_campaigns=True`` (``DownloadManager(all_campaigns=True)``)
        it is None: there is no single record. In the campaign flow the origin of a
        sheet is its sidecar (``extra.source``, ``extra.campaign``) - the
        standard path sidecar describes the campaign the link actually points
        to, which can be older than the newest record when its download
        failed.
        """
        with self._sources_lock:
            source = self._sources.get(SheetParser(sheet).sheet)
            return dict(source) if source is not None else None


class SkorowidzLayersMixin(SourceInfoMixin):
    """HTTP session per thread and WMS index layers discovered per endpoint.

    The derived class declares a two-group ``LAYER_PATTERN``: group 1 = layer
    year (empty for a layer without a year), group 2 = aggregate-layer marker
    (``iStarsze``/``Starsze``, empty for a yearly layer) — and sets
    ``self._sessions`` (``SessionPerThread`` with a session supplied by the
    caller or ``None``).
    """

    LAYER_PATTERN: re.Pattern[str]
    LAYER_FAMILY: re.Pattern[str]
    _sessions: SessionPerThread
    _cache: MetadataCache | None
    MAX_RETRIES: int
    DEFAULT_TIMEOUT: int

    supports_campaigns: bool = True
    # Download description in logs/messages: "<file from URL> (<label>)"
    DOWNLOAD_LABEL = "OpenData"

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Provider hook: cache key, endpoint and product filter for a sheet."""
        raise NotImplementedError

    def _resolve_sheet(self, sheet: str, timeout: int | None = None) -> SkorowidzRecord:
        """Cache -> layers newest first -> hard filter -> newest campaign."""
        parser = SheetParser(sheet)
        return self._resolve_record(
            parser,
            self.DEFAULT_TIMEOUT if timeout is None else timeout,
            self._skorowidz_query(parser),
        )

    @staticmethod
    def _query_bbox(parser: SheetParser) -> str:
        """GetFeatureInfo query bbox (N,E axes) around the sheet centre."""
        bbox = parser.get_bbox(crs="EPSG:2180")
        x = (bbox.min_x + bbox.max_x) / 2
        y = (bbox.min_y + bbox.max_y) / 2
        return f"{y - 10},{x - 10},{y + 10},{x + 10}"

    def _query_layer(
        self,
        parser: SheetParser,
        endpoint: str,
        layer: str,
        timeout: int,
        query_bbox: str,
    ) -> list[SkorowidzRecord]:
        """Records of one layer at the sheet's centre point."""
        return query_skorowidz_layer(
            self._sessions.get(),
            endpoint,
            layer,
            query_bbox=query_bbox,
            sheet=parser.sheet,
            timeout=timeout,
            retries=self.MAX_RETRIES,
        )

    @staticmethod
    def _missing_endpoint(query: SkorowidzQuery, sheet: str) -> DownloadError:
        return DownloadError(
            f"Brak endpointu WMS dla {query.cache_key[1]}, {query.cache_key[2]}",
            sheet=sheet,
        )

    def _resolve_record(
        self, parser: SheetParser, timeout: int, query: SkorowidzQuery
    ) -> SkorowidzRecord:
        """Resolve a sheet over layers: cache, product filter and no-coverage hint."""
        sheet = parser.sheet
        if self._cache is not None:
            cached = self._cache.get_record(*query.cache_key)
            if cached is not None:
                if cached.get("no_coverage") and _current_texts(cached):
                    raise NoCoverageError(
                        cached.get("message") or _cached_no_coverage_message(sheet),
                        sheet=sheet,
                        hints=tuple(cached.get("hints") or ()),
                    )
                source = cached.get("source")
                record = cached_record(source)
                if record is not None and isinstance(source, dict):
                    self._remember_source(sheet, source)
                    return record
                # pre-ADR-031 payload (Polish keys) = cache miss
                logger.debug("%s: unreadable record_cache entry - refreshing", sheet)

        if query.endpoint is None:
            raise self._missing_endpoint(query, sheet)
        rejected: list[SkorowidzRecord] = []
        query_bbox = self._query_bbox(parser)
        for layer in self._layers(query.endpoint, timeout):
            records = self._query_layer(
                parser, query.endpoint, layer, timeout, query_bbox
            )
            chosen = select_sheet_record(
                records,
                sheet=sheet,
                system=parser.system,
                zone=_zone(parser),
                resolution_m=query.resolution_m,
                predicate=query.predicate,
            )
            if chosen is not None:
                source = self.record_source(chosen)
                self._remember_source(sheet, source)
                if self._cache is not None:
                    self._cache.set_record(*query.cache_key, {"source": source})
                return chosen
            rejected.extend(records)
        error = query.no_coverage(parser, rejected)
        if self._cache is not None:
            self._cache.set_record(
                *query.cache_key,
                {
                    "no_coverage": True,
                    "message": str(error),
                    **({"hints": list(error.hints)} if error.hints else {}),
                },
            )
        raise error

    def _resolve_all(
        self,
        parser: SheetParser,
        timeout: int,
        query: SkorowidzQuery,
    ) -> list[SkorowidzRecord]:
        """All campaigns of a sheet from every layer (newest first).

        A partially scanned ``campaigns_cache`` entry is stale (P5), as is a
        pre-ADR-031 payload. A failed layer never writes to the cache. File
        format remains outside the provider's hard filter (errata 2 N-2).
        """
        sheet = parser.sheet
        if self._cache is not None:
            cached = self._cache.get_campaigns(*query.cache_key)
            if cached is not None and cached.get("scanned_from") is None:
                if cached.get("no_coverage") and _current_texts(cached):
                    raise NoCoverageError(
                        cached.get("message") or _cached_no_coverage_message(sheet),
                        sheet=sheet,
                        hints=tuple(cached.get("hints") or ()),
                    )
                sources = cached.get("sources")
                restored = [cached_record(s) for s in sources or ()]
                if sources and all(r is not None for r in restored):
                    return [r for r in restored if r is not None]
                # pre-ADR-031 payload (Polish keys) = cache miss
                logger.debug("%s: unreadable campaigns_cache entry - refreshing", sheet)

        if query.endpoint is None:
            raise self._missing_endpoint(query, sheet)
        found: list[SkorowidzRecord] = []
        rejected: list[SkorowidzRecord] = []
        query_bbox = self._query_bbox(parser)
        for layer in self._layers(query.endpoint, timeout):
            records = self._query_layer(
                parser, query.endpoint, layer, timeout, query_bbox
            )
            matched = select_campaign_records(
                records,
                sheet=sheet,
                system=parser.system,
                zone=_zone(parser),
                resolution_m=query.resolution_m,
                predicate=query.predicate,
            )
            found.extend(matched)
            # rejected serves only the hints when found is empty, i.e. when no
            # layer matched anything — then it holds all records
            rejected.extend(records)
        found = sorted(
            {r.url: r for r in reversed(found)}.values(),
            key=_campaign_key,
            reverse=True,
        )
        if not found:
            error = query.no_coverage(parser, rejected)
            if self._cache is not None:
                self._cache.set_campaigns(
                    *query.cache_key,
                    {
                        "no_coverage": True,
                        "message": str(error),
                        **({"hints": list(error.hints)} if error.hints else {}),
                    },
                )
            raise error
        if self._cache is not None:
            self._cache.set_campaigns(
                *query.cache_key,
                {"sources": [self.record_source(r) for r in found]},
            )
        return found

    def resolve_campaigns(
        self,
        sheet: str,
        *,
        all_campaigns: bool = False,
        min_year: int | None = None,
        max_year: int | None = None,
        timeout: int | None = None,
    ) -> list[SkorowidzRecord]:
        """Campaigns of a sheet in a closed year range (newest first).

        ``all_campaigns=False`` selects the newest flight within year bounds;
        True selects every flight within bounds. Without bounds, False retains
        the single-record cache. With a bound, the full campaign list supplies
        both selected records and all available years on a range conflict.
        LAZ with True does not deduplicate coverage.
        """
        # local import: the kartograf.download package imports manager -> providers.pl
        from kartograf.download.campaigns import (
            in_year_range,
            record_year,
            validate_year_bounds,
            year_range_error,
        )

        validate_year_bounds(min_year, max_year)
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        parser = SheetParser(sheet)
        sheet = parser.sheet
        query = self._skorowidz_query(parser)
        if min_year is None and max_year is None and not all_campaigns:
            return [self._resolve_record(parser, timeout, query)]
        found = self._resolve_all(parser, timeout, query)
        if min_year is None and max_year is None:
            kept = found
        else:
            kept = [
                record
                for record in found
                if in_year_range(record_year(record), min_year, max_year)
            ]
            if not kept:
                years = tuple(
                    sorted(
                        {
                            year
                            for record in found
                            if (year := record_year(record)) is not None
                        }
                    )
                )
                if not years:
                    raise NoCoverageError(f"Brak kampanii {sheet}", sheet=sheet)
                raise year_range_error({sheet: years}, min_year, max_year, total=1)
        if not all_campaigns:
            return [kept[0]]
        # the manager logs the campaign count at INFO (`_fetch_campaigns`, M-7)
        logger.debug("%s: %s kampanii", sheet, len(kept))
        return kept

    def available_years(
        self, sheet: str, timeout: int | None = None
    ) -> tuple[int, ...]:
        """Ascending distinct acquisition years of a sheet's complete campaign list."""
        # local import avoids the download -> manager -> providers import cycle
        from kartograf.download.campaigns import record_year

        parser = SheetParser(sheet)
        found = self._resolve_all(
            parser,
            self.DEFAULT_TIMEOUT if timeout is None else timeout,
            self._skorowidz_query(parser),
        )
        return tuple(
            sorted(
                {year for record in found if (year := record_year(record)) is not None}
            )
        )

    def record_source(self, record: SkorowidzRecord) -> dict:
        """Record metadata (``to_source``) with the endpoint and ``source_extra``."""
        query = self._skorowidz_query(SheetParser(record.sheet))
        source = record.to_source(query.endpoint or "")
        if query.source_extra:
            source.update(query.source_extra)
        return source

    def download_record(
        self,
        record: SkorowidzRecord,
        output_path: Path,
        timeout: int | None = None,
    ) -> Path:
        """Download the file of the given record (campaign) to ``output_path``."""
        return download_to(
            self._sessions.get(),
            record.url,
            Path(output_path),
            timeout=self.DEFAULT_TIMEOUT if timeout is None else timeout,
            retries=self.MAX_RETRIES,
            # file name from the URL (campaign id + sheet) tells campaigns apart in logs
            description=f"{record.url.rsplit('/', 1)[-1]} ({self.DOWNLOAD_LABEL})",
        )

    def __init__(self) -> None:
        super().__init__()
        self._layers_lock = threading.Lock()
        self._validated_layers: dict[str, list[str]] = {}

    def validate_sheet(self, sheet: str) -> bool:
        """Sheet code parsable by ``SheetParser`` (PL-1992 or PL-2000)."""
        try:
            SheetParser(sheet)
            return True
        except ParseError:
            return False

    def _fetch_wms_layers(
        self, wms_endpoint: str, timeout: float | None = None
    ) -> list[str]:
        """Discover the product's layers; a service error has no hardcoded fallback.

        ``timeout`` defaults to the provider's ``DEFAULT_TIMEOUT`` (30 s
        NMT/NMPT, 60 s orto; N3) — a GetCapabilities failure ends the whole
        path, so it must not have a shorter limit than the sheet download.
        """
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        params = {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetCapabilities"}
        response = get_with_retry(
            self._sessions.get(),
            f"{wms_endpoint}?{urlencode(params)}",
            timeout=timeout,
            description=f"GUGiK WMS GetCapabilities {wms_endpoint}",
        )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise DownloadError(
                f"GUGiK WMS GetCapabilities {wms_endpoint}: nieprawidlowy XML: {exc}"
            ) from exc
        # {name: (no year, aggregate, -year)} — yearly newest first, aggregate
        # last, the layer without a year ("Starsze") after all yearly ones
        layers: dict[str, tuple[bool, bool, int]] = {}
        for elem in root.iter():
            if elem.tag.rsplit("}", 1)[-1] != "Name" or not elem.text:
                continue
            match = self.LAYER_PATTERN.fullmatch(elem.text)
            if match is None:
                if self.LAYER_FAMILY.match(elem.text):
                    logger.warning(
                        "Warstwa GetCapabilities %s z rodziny produktu nie pasuje "
                        "do wzorca %s - NIE odpytywana",
                        elem.text,
                        self.LAYER_PATTERN.pattern,
                    )
            else:
                year, cumulative = match.group(1), match.group(2)
                layers[elem.text] = (
                    year is None,
                    cumulative is not None,
                    -int(year) if year else 0,
                )
        if not layers:
            raise DownloadError(
                f"GUGiK WMS GetCapabilities {wms_endpoint}: "
                "endpoint nie publikuje warstw skorowidza dla tego produktu"
            )
        return sorted(layers, key=layers.__getitem__)

    def _layers(self, endpoint: str, timeout: float | None = None) -> list[str]:
        """Memoize only success, once per endpoint; a lock guards the queries.

        ``timeout`` (default: the provider's ``DEFAULT_TIMEOUT``) goes to
        GetCapabilities — the same as for layer queries in ``_resolve_record``.
        """
        with self._layers_lock:
            if endpoint not in self._validated_layers:
                self._validated_layers[endpoint] = self._fetch_wms_layers(
                    endpoint, timeout
                )
            return self._validated_layers[endpoint]


def coverage_hints(parser: SheetParser, records: Iterable[SkorowidzRecord]) -> set[str]:
    """``NoCoverageError`` hints shared by NMT/NMPT and orto (D14).

    A PL-2000 descendant of the requested sheet code -> the descendant's
    ``--scale``; a record in another CRS -> its sheet code or
    ``--system``/``--scale``. ``records`` are already filtered by the provider
    (NMT resolution); the provider's own hints (resolution, orto colour
    variants) stay with it.
    """
    hints = set()
    for record in records:
        if parser.system == "2000" and record.sheet.startswith(parser.sheet + "."):
            scale = SheetParser(record.sheet).scale
            hints.add(f"Dostepny potomek {record.sheet} - uzyj --scale {scale}")
        elif record.system is not None and record.system != parser.system:
            scale = SheetParser(record.sheet).scale
            # PL-1992 sheets come only at 1:10000 (no --scale); PL-2000 needs it
            flags = f"--system {record.system}"
            if record.system == "2000":
                flags += f" --scale {scale}"
            hints.add(
                f"Skorowidz ma ten obszar w PL-{record.system}: "
                f"{record.sheet} ({scale}) - uzyj tego godla lub {flags}"
            )
    return hints


def no_coverage_error(
    parser: SheetParser, message: str, hints: Iterable[str]
) -> NoCoverageError:
    """``NoCoverageError`` with hints appended in a fixed order."""
    ordered = sorted(hints)
    if ordered:
        message += ". " + "; ".join(ordered)
    return NoCoverageError(message, sheet=parser.sheet, hints=tuple(ordered))
