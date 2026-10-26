"""GUGiK index (skorowidz) records: parsing, strict selection and sheet origin."""

import json
import logging
import re
import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
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
from kartograf.messages import message, reason
from kartograf.sources.registry import parse_pl_system
from kartograf.transport.http import (
    SessionPerThread,
    download_to,
    get_with_retry,
    head_signal,
)

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


def horizontal_crs_of(value: str | None) -> tuple[str | None, int | None]:
    """Return the ``(system, zone)`` of a record.

    ``(None, None)`` = record without a CRS
    (rejected in ``select_sheet_record``). Parser: ``parse_pl_system`` (D3).
    Shared by the WMS (orto) and WFS (NMT/NMPT) record parsers.
    """
    return parse_pl_system(value) or (None, None)


def metres(value: str | None) -> float | None:
    """'0.15' / '0,15' / '0.15 m' -> 0.15; None when missing or unparseable."""
    if value is None:
        return None
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:m)?\s*", value)
    return float(match[1].replace(",", ".")) if match else None


@dataclass(frozen=True)
class SkorowidzRecord:
    """One record of a GUGiK sheet index layer."""

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

    def to_source(self, endpoint: str) -> dict[str, Any]:
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
            "height_rmse_m": metres(self.raw.get("bladSredniWysokosci")),
            "position_rmse_m": metres(self.raw.get("bladSredniPolozenia")),
            "archive_module": self.raw.get("modulArchiwizacji"),
            "declared_vertical_crs": self.raw.get("ukladWspolrzednychPionowych"),
        }

    @classmethod
    def from_source(cls, source: dict[str, Any]) -> "SkorowidzRecord":
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
        system, zone = horizontal_crs_of(source.get("declared_crs") or "")
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
        decoded: str = json.loads(literal)
        return decoded
    except ValueError:  # non-JSON escape (e.g. \') — literal value
        return literal[1:-1]


def parse_skorowidz_records(text: str, layer: str) -> list[SkorowidzRecord]:
    """`X.push({...})` records from GetFeatureInfo; URL not extension-filtered (H1)."""
    records = []
    for match in _RECORD.finditer(text):
        raw = {key: _decode_value(value) for key, value in _FIELD.findall(match[1])}
        url = raw.get("url", "")
        if not url.startswith("https://"):
            logger.warning(message("providers.record_no_https_url", layer=layer))
            continue
        try:
            sheet = SheetParser(raw.get("godlo", "")).sheet
        except (ParseError, ValidationError):
            logger.warning(
                message(
                    "providers.invalid_sheet_code", layer=layer, code=raw.get("godlo")
                )
            )
            continue
        system, zone = horizontal_crs_of(
            raw.get("ukladWspolrzednychPoziomych") or raw.get("ukladWspolrzednych", "")
        )
        resolution_text = raw.get("charakterystykaPrzestrzenna") or raw.get(
            "wielkoscPiksela", ""
        )
        resolution = metres(resolution_text)
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
                    message(
                        "providers.record_year_outside_partition",
                        layer=layer,
                        sheet=sheet,
                        record_year=record_year,
                    ),
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
    require_resolution: bool = True,
) -> bool:
    """ADR-028 hard filter shared by single-record selection and campaign lists.

    ``sheet`` must already be normalized. Order: sheet code, the product
    predicate (file format, orto colour), then CRS and resolution - a WFS
    answer holds every format of the queried point, so records of another
    sheet or format are skipped silently. A record of the sheet and product
    without a CRS, or without a resolution where the product has one
    (``require_resolution``; TIN/TTN archives have none), is rejected with a
    warning (P6); called once per record, the warning is not duplicated.
    """
    if record.sheet != sheet:
        return False
    if predicate is not None and not predicate(record):
        return False
    if record.system is None or (require_resolution and record.resolution_m is None):
        logger.warning(
            message(
                "providers.record_no_crs_resolution",
                layer=record.layer,
                sheet=record.sheet,
            ),
        )
        return False
    if record.system != system:
        return False
    if system == "2000" and record.zone != zone:
        return False
    return resolution_m is None or (
        record.resolution_m is not None
        and abs(record.resolution_m - resolution_m) < 1e-6
    )


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
    require_resolution: bool = True,
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
            require_resolution=require_resolution,
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
    require_resolution: bool = True,
) -> list[SkorowidzRecord]:
    """Return all records passing the ``select_sheet_record`` filter.

    Without duplicate URLs, descending by ``(aktualnosc, dt_pzgik, url)``.
    """
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
            require_resolution=require_resolution,
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
    description = message("transport.gfi_context", sheet=sheet, layer=layer)
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
            message(
                "providers.ogc_exception_report",
                description=description,
                excerpt=excerpt,
            ),
            sheet=sheet,
        )
    if not is_skorowidz_answer(text):
        raise DownloadError(
            message("providers.not_sheet_index_template", description=description),
            sheet=sheet,
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
    source_extra: dict[str, Any] | None = None
    # False only for products without a resolution in the index (TIN/TTN)
    require_resolution: bool = True


def _zone(parser: SheetParser) -> int | None:
    """PL-2000 zone of the sheet code (record filter); PL-1992 -> ``None``."""
    return int(parser.sheet.split(".")[0]) if parser.sheet_system == "2000" else None


def _filters(parser: SheetParser, query: SkorowidzQuery) -> dict[str, Any]:
    """Return the hard filter of a sheet's records (``select_sheet_record``)."""
    return {
        "sheet": parser.sheet,
        "system": parser.sheet_system,
        "zone": _zone(parser),
        "resolution_m": query.resolution_m,
        "predicate": query.predicate,
        "require_resolution": query.require_resolution,
    }


def _newest_first(records: list[SkorowidzRecord]) -> list[SkorowidzRecord]:
    """Return the campaigns without a repeated URL (the first kept), newest first."""
    return sorted(
        {record.url: record for record in reversed(records)}.values(),
        key=_campaign_key,
        reverse=True,
    )


def _cached_no_coverage_message(sheet: str) -> str:
    """Return the message of a cached no-coverage entry written without one.

    Written before 2026-10-07. A cache hit never calls the provider's ``no_coverage`` -
    that may query the network (variant hints, P10).
    """
    return message("providers.cached_no_coverage", sheet=sheet)


# Flags renamed in 0.8.0 (ADR-038): a cached hint naming one is outdated.
_OLD_FLAGS = ("--system ", "--target-crs")


def _current_texts(cached: dict[str, Any]) -> bool:
    """Whether a cached no-coverage entry carries current texts.

    Entries written before 0.8.0 may hold a message or hints with Polish
    diacritics or an em dash (they would break ``Notice``, ASCII only) or
    a flag renamed in 0.8.0 (``--system``); such an entry is a cache miss
    and the index is asked again.
    """
    texts = [cached.get("message") or "", *(cached.get("hints") or ())]
    return all(
        isinstance(t, str) and t.isascii() and not any(f in t for f in _OLD_FLAGS)
        for t in texts
    )


class SourceInfoMixin:
    """Origin per sheet code, independent of thread completion order."""

    def __init__(self) -> None:
        super().__init__()
        self._sources: dict[str, dict[str, Any]] = {}
        self._sources_lock = threading.Lock()

    def _remember_source(self, sheet: str, source: dict[str, Any]) -> None:
        with self._sources_lock:
            self._sources[SheetParser(sheet).sheet] = dict(source)

    def source_info(self, sheet: str) -> dict[str, Any] | None:
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
    # HEAD of a record file before its transfer (``DownloadManager``:
    # ``DOWNLOAD_SIZE`` above 100 MiB, K9): image providers only - a list of
    # NMT sheets would pay ~0.5 s per sheet for files far below the limit.
    announces_size: bool = False

    def _skorowidz_query(self, parser: SheetParser) -> SkorowidzQuery:
        """Return the cache key, endpoint and product filter for a sheet.

        Provider hook.
        """
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
        """Return the records of one layer at the sheet's centre point."""
        return query_skorowidz_layer(
            self._sessions.get(),
            endpoint,
            layer,
            query_bbox=query_bbox,
            sheet=parser.sheet,
            timeout=timeout,
            retries=self.MAX_RETRIES,
        )

    def _cached_layer(
        self, parser: SheetParser, endpoint: str, layer: str
    ) -> list[SkorowidzRecord] | None:
        """Return the sheet's records of a layer group from a cached answer.

        Provider hook (``WfsSkorowidzLayersMixin``: an area answer of the index
        that holds the sheet, ADR-056); ``None`` = ask the index. Records read
        here write no entry of the sheet: the answer keeps its own age.
        """
        return None

    @staticmethod
    def _missing_endpoint(query: SkorowidzQuery, sheet: str) -> DownloadError:
        return DownloadError(
            message(
                "providers.missing_index_endpoint",
                product=query.cache_key[1],
                variant=query.cache_key[2],
            ),
            sheet=sheet,
        )

    def _resolve_record(
        self, parser: SheetParser, timeout: int, query: SkorowidzQuery
    ) -> SkorowidzRecord:
        """Resolve a sheet over layers: cache, product filter and no-coverage hint.

        The record cache, then per layer group a cached answer that holds the
        sheet (``_cached_layer``), then the index; a group whose cached answer
        has no matching record asks the index, which gives the hints.
        """
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
        filters = _filters(parser, query)
        rejected: list[SkorowidzRecord] = []
        query_bbox = self._query_bbox(parser)
        for layer in self._layers(query.endpoint, timeout):
            held = self._cached_layer(parser, query.endpoint, layer)
            chosen = None if held is None else select_sheet_record(held, **filters)
            if chosen is not None:
                self._remember_source(sheet, self.record_source(chosen))
                return chosen
            records = self._query_layer(
                parser, query.endpoint, layer, timeout, query_bbox
            )
            chosen = select_sheet_record(records, **filters)
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
        pre-ADR-031 payload. Then cached answers that hold the sheet in every
        layer group (``_cached_layer``) when they have a matching record, else
        the index. A failed layer never writes to the cache. File format
        remains outside the provider's hard filter (errata 2 N-2).
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
        filters = _filters(parser, query)
        layers = self._layers(query.endpoint, timeout)
        held = [self._cached_layer(parser, query.endpoint, layer) for layer in layers]
        answered = [records for records in held if records is not None]
        if len(answered) == len(held):
            found = _newest_first(
                [
                    record
                    for records in answered
                    for record in select_campaign_records(records, **filters)
                ]
            )
            if found:
                return found
        found = []
        rejected: list[SkorowidzRecord] = []
        query_bbox = self._query_bbox(parser)
        for layer in layers:
            records = self._query_layer(
                parser, query.endpoint, layer, timeout, query_bbox
            )
            found.extend(select_campaign_records(records, **filters))
            # rejected serves only the hints when found is empty, i.e. when no
            # layer matched anything — then it holds all records
            rejected.extend(records)
        found = _newest_first(found)
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
                    raise NoCoverageError(
                        message("providers.no_campaign", sheet=sheet), sheet=sheet
                    )
                raise year_range_error({sheet: years}, min_year, max_year, total=1)
        if not all_campaigns:
            return [kept[0]]
        # the manager logs the campaign count at INFO (`_fetch_campaigns`, M-7)
        logger.debug(f"{sheet}: {len(kept)} campaigns")
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

    def record_source(self, record: SkorowidzRecord) -> dict[str, Any]:
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

    def record_length(self, record: SkorowidzRecord) -> int | None:
        """Return the ``Content-Length`` of the record file from ``HEAD``.

        ``None`` when the server gives none or the request fails (the download that
        follows reports its own failure).
        """
        try:
            signal = head_signal(
                self._sessions.get(),
                record.url,
                timeout=self.DEFAULT_TIMEOUT,
                retries=self.MAX_RETRIES,
                description=f"HEAD {record.url.rsplit('/', 1)[-1]}",
            )
        except DownloadError as e:
            logger.debug("HEAD %s: %s", record.url, e)
            return None
        length: int | None = signal["content_length"]
        return length

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
                message(
                    "providers.wms_caps_invalid_xml",
                    wms_endpoint=wms_endpoint,
                    error=reason(exc),
                )
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
                        message(
                            "providers.wms_layer_pattern_mismatch",
                            layer_name=elem.text,
                            pattern=self.LAYER_PATTERN.pattern,
                        ),
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
                message("providers.wms_no_index_layers", wms_endpoint=wms_endpoint)
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
    ``--sheet-system``/``--scale``. ``records`` are already filtered by the provider
    (NMT resolution); the provider's own hints (resolution, orto colour
    variants) stay with it.
    """
    hints: set[str] = set()
    for record in records:
        if parser.sheet_system == "2000" and record.sheet.startswith(
            parser.sheet + "."
        ):
            scale = SheetParser(record.sheet).scale
            hints.add(
                message(
                    "providers.descendant_sheet_available",
                    sheet=record.sheet,
                    scale=scale,
                )
            )
        elif record.system is not None and record.system != parser.sheet_system:
            scale = SheetParser(record.sheet).scale
            # PL-1992 sheets come only at 1:10000 (no --scale); PL-2000 needs it
            flags = f"--sheet-system {record.system}"
            if record.system == "2000":
                flags += f" --scale {scale}"
            hints.add(
                message(
                    "providers.index_other_system_hint",
                    system=record.system,
                    sheet=record.sheet,
                    scale=scale,
                    flags=flags,
                )
            )
    return hints


def no_coverage_error(
    parser: SheetParser, text: str, hints: Iterable[str]
) -> NoCoverageError:
    """``NoCoverageError`` with hints appended in a fixed order."""
    ordered = sorted(hints)
    if ordered:
        text = message("providers.no_coverage_hints", text=text, hints=ordered)
    return NoCoverageError(text, sheet=parser.sheet, hints=tuple(ordered))
