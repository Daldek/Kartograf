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
from kartograf.sources.registry import parse_pl_uklad
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
    """``(uklad, zone)`` of a record; ``(None, None)`` = record without a CRS
    (rejected in ``select_sheet_record``). Parser: ``parse_pl_uklad`` (D3)."""
    return parse_pl_uklad(value) or (None, None)


@dataclass(frozen=True)
class SkorowidzRecord:
    url: str
    godlo: str
    aktualnosc: str
    dt_pzgik: str | None
    layer: str
    uklad: str | None
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
            "sheet": self.godlo,
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
        }

    @classmethod
    def from_source(cls, source: dict) -> "SkorowidzRecord":
        """Restore the selected record from a cache payload (no reselection).

        Raises ``KeyError`` when a required key (``url``, ``sheet``,
        ``acquisition_date``, ``layer``) is missing — e.g. a cache entry
        written before ADR-031 with Polish key names; callers treat that
        as a cache miss (``cached_record``).
        """
        uklad, zone = _horizontal_crs(source.get("declared_crs") or "")
        raw = {
            key: str(source[field])
            for key, field in (
                ("ukladWspolrzednychPoziomych", "declared_crs"),
                ("aktualnoscRok", "acquisition_year"),
                ("numerZgloszeniaPracy", "survey_work_id"),
                ("zrDanych", "data_source"),
                ("format", "format"),
            )
            if source.get(field) is not None
        }
        return cls(
            url=source["url"],
            godlo=source["sheet"],
            aktualnosc=source["acquisition_date"],
            dt_pzgik=source.get("pzgik_date"),
            layer=source["layer"],
            uklad=uklad,
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
            godlo = SheetParser(raw.get("godlo", "")).godlo
        except (ParseError, ValidationError):
            logger.warning(
                "Warstwa %s: nieprawidlowe godlo %r", layer, raw.get("godlo")
            )
            continue
        uklad, zone = _horizontal_crs(
            raw.get("ukladWspolrzednychPoziomych") or raw.get("ukladWspolrzednych", "")
        )
        resolution_text = raw.get("charakterystykaPrzestrzenna") or raw.get(
            "wielkoscPiksela", ""
        )
        resolution_match = re.fullmatch(
            r"\s*(\d+(?:[.,]\d+)?)\s*(?:m)?\s*", resolution_text
        )
        resolution = (
            float(resolution_match[1].replace(",", ".")) if resolution_match else None
        )
        full_sheet = raw.get("calyArkuszWypelnionyTrescia") or raw.get(
            "calyArkuszWyeplnionyTrescia"
        )
        record = SkorowidzRecord(
            url=url,
            godlo=godlo,
            aktualnosc=raw.get("aktualnosc", ""),
            dt_pzgik=raw.get("dt_pzgik"),
            layer=layer,
            uklad=uklad,
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
                    godlo,
                    record_year,
                )
        records.append(record)
    return records


def _matches(
    record: SkorowidzRecord,
    *,
    godlo: str,
    uklad: str,
    zone: int | None,
    resolution_m: float | None,
    predicate: Callable[[SkorowidzRecord], bool] | None,
) -> bool:
    """ADR-028 hard filter shared by single-record selection and campaign lists.

    ``godlo`` must already be normalized; called once per record (the warning
    about a missing CRS/resolution is not duplicated).
    """
    if record.uklad is None or record.resolution_m is None:
        logger.warning(
            "Warstwa %s: rekord %s bez ukladu lub rozdzielczosci — pominieto",
            record.layer,
            record.godlo,
        )
        return False
    if record.godlo != godlo or record.uklad != uklad:
        return False
    if uklad == "2000" and record.zone != zone:
        return False
    if resolution_m is not None and abs(record.resolution_m - resolution_m) >= 1e-6:
        return False
    return predicate is None or predicate(record)


def _campaign_key(record: SkorowidzRecord) -> tuple[str, str, str]:
    return (record.aktualnosc, record.dt_pzgik or "", record.url)


def select_sheet_record(
    records: Iterable[SkorowidzRecord],
    *,
    godlo: str,
    uklad: str,
    zone: int | None = None,
    resolution_m: float | None = None,
    predicate: Callable[[SkorowidzRecord], bool] | None = None,
) -> SkorowidzRecord | None:
    """Pick the newest campaign meeting ALL requirements of the request."""
    godlo = SheetParser(godlo).godlo
    matching = [
        record
        for record in records
        if _matches(
            record,
            godlo=godlo,
            uklad=uklad,
            zone=zone,
            resolution_m=resolution_m,
            predicate=predicate,
        )
    ]
    return max(matching, key=_campaign_key, default=None)


def select_campaign_records(
    records: Iterable[SkorowidzRecord],
    *,
    godlo: str,
    uklad: str,
    zone: int | None = None,
    resolution_m: float | None = None,
    predicate: Callable[[SkorowidzRecord], bool] | None = None,
) -> list[SkorowidzRecord]:
    """All records passing the ``select_sheet_record`` filter, without
    duplicate URLs, descending by ``(aktualnosc, dt_pzgik, url)``."""
    godlo = SheetParser(godlo).godlo
    unique: dict[str, SkorowidzRecord] = {}
    for record in records:
        if _matches(
            record,
            godlo=godlo,
            uklad=uklad,
            zone=zone,
            resolution_m=resolution_m,
            predicate=predicate,
        ):
            unique.setdefault(record.url, record)
    return sorted(unique.values(), key=_campaign_key, reverse=True)


def layer_upper_year(pattern: re.Pattern[str], name: str) -> int | None:
    """Upper year from a layer name (``LAYER_PATTERN`` group 1): ``2019`` -> 2019,
    ``2017iStarsze`` -> 2017; ``Starsze`` or a name outside the pattern -> ``None``."""
    match = pattern.fullmatch(name)
    if match is None or match.group(1) is None:
        return None
    return int(match.group(1))


def query_skorowidz_layer(
    session: requests.Session,
    endpoint: str,
    layer: str,
    *,
    query_bbox: str,
    godlo: str,
    timeout: float,
    retries: int = 3,
) -> list[SkorowidzRecord]:
    """Query one layer; a failure never means no coverage."""
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
    description = f"{godlo}: warstwa {layer}"
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
            f"{description}: raport wyjatku OGC: {excerpt}", godlo=godlo
        )
    if not is_skorowidz_answer(text):
        raise DownloadError(
            f"{description}: odpowiedz nie jest szablonem skorowidza GUGiK", godlo=godlo
        )
    return parse_skorowidz_records(text, layer)


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
    return int(parser.godlo.split(".")[0]) if parser.uklad == "2000" else None


def _record_year(record: SkorowidzRecord) -> int | None:
    """Campaign year as in the parser (``aktualnoscRok`` or ``aktualnosc``, not
    ``dt_pzgik``) — the ``min_year`` boundary; undetermined -> ``None``."""
    year = record.raw.get("aktualnoscRok") or record.aktualnosc[:4]
    return int(year) if year.isdigit() else None


def _meets_min_year(record: SkorowidzRecord, min_year: int | None) -> bool:
    """Record meets the boundary; an undetermined year meets no boundary."""
    if min_year is None:
        return True
    year = _record_year(record)
    return year is not None and year >= min_year


def _covers(scanned_from: int | None, min_year: int | None) -> bool:
    """Entry scanned from ``scanned_from`` (``None`` = full) covers the boundary."""
    return scanned_from is None or (min_year is not None and scanned_from <= min_year)


def _partial_scan_no_coverage(godlo: str, min_year: int | None) -> NoCoverageError:
    """No campaign in a partial scan — single source of the message (D-2)."""
    return NoCoverageError(
        f"Brak kampanii {godlo} od roku {min_year} "
        f"(warstwy starsze niz {min_year} pominiete)",
        godlo=godlo,
    )


class SourceInfoMixin:
    """Origin per sheet code, independent of thread completion order."""

    def __init__(self) -> None:
        super().__init__()
        self._sources: dict[str, dict] = {}
        self._sources_lock = threading.Lock()

    def _remember_source(self, godlo: str, source: dict) -> None:
        with self._sources_lock:
            self._sources[SheetParser(godlo).godlo] = dict(source)

    def source_info(self, godlo: str) -> dict | None:
        with self._sources_lock:
            source = self._sources.get(SheetParser(godlo).godlo)
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

    def _resolve_sheet(self, godlo: str, timeout: int | None = None) -> SkorowidzRecord:
        """Cache -> layers newest first -> hard filter -> newest campaign."""
        parser = SheetParser(godlo)
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
            godlo=parser.godlo,
            timeout=timeout,
            retries=self.MAX_RETRIES,
        )

    @staticmethod
    def _missing_endpoint(query: SkorowidzQuery, godlo: str) -> DownloadError:
        return DownloadError(
            f"Brak endpointu WMS dla {query.cache_key[1]}, {query.cache_key[2]}",
            godlo=godlo,
        )

    def _resolve_record(
        self, parser: SheetParser, timeout: int, query: SkorowidzQuery
    ) -> SkorowidzRecord:
        """Resolve a sheet over layers: cache, product filter and no-coverage hint."""
        godlo = parser.godlo
        if self._cache is not None:
            cached = self._cache.get_record(*query.cache_key)
            if cached is not None:
                if cached.get("no_coverage"):
                    raise NoCoverageError(
                        cached.get("message") or str(query.no_coverage(parser, [])),
                        godlo=godlo,
                        hints=tuple(cached.get("hints") or ()),
                    )
                source = cached.get("source")
                record = cached_record(source)
                if record is not None and isinstance(source, dict):
                    self._remember_source(godlo, source)
                    return record
                # pre-ADR-031 payload (Polish keys) = cache miss
                logger.debug("%s: unreadable record_cache entry — refreshing", godlo)

        if query.endpoint is None:
            raise self._missing_endpoint(query, godlo)
        rejected: list[SkorowidzRecord] = []
        query_bbox = self._query_bbox(parser)
        for layer in self._layers(query.endpoint, timeout):
            records = self._query_layer(
                parser, query.endpoint, layer, timeout, query_bbox
            )
            chosen = select_sheet_record(
                records,
                godlo=godlo,
                uklad=parser.uklad,
                zone=_zone(parser),
                resolution_m=query.resolution_m,
                predicate=query.predicate,
            )
            if chosen is not None:
                source = self.record_source(chosen)
                self._remember_source(godlo, source)
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
        *,
        min_year: int | None,
    ) -> list[SkorowidzRecord]:
        """All campaigns of a sheet from all layers (newest first).

        With ``min_year`` a layer whose upper year from the name is < the
        boundary is not queried (a layer without a year — always). A
        ``campaigns_cache`` entry from a partial scan (``scanned_from``) is
        valid only for boundaries ``>= scanned_from``. A layer failure =
        ``DownloadError``, nothing goes to the cache. The provider does not
        filter the file format (errata 2 N-2).
        """
        godlo = parser.godlo
        if self._cache is not None:
            cached = self._cache.get_campaigns(*query.cache_key)
            if cached is not None and _covers(cached.get("scanned_from"), min_year):
                if cached.get("no_coverage"):
                    if cached.get("scanned_from") is not None:
                        # D-2: message from the CURRENT boundary, not the stored one
                        raise _partial_scan_no_coverage(godlo, min_year)
                    raise NoCoverageError(
                        cached.get("message") or str(query.no_coverage(parser, [])),
                        godlo=godlo,
                        hints=tuple(cached.get("hints") or ()),
                    )
                sources = cached.get("sources")
                restored = [cached_record(s) for s in sources or ()]
                if sources and all(r is not None for r in restored):
                    return [r for r in restored if r is not None]
                # pre-ADR-031 payload (Polish keys) = cache miss
                logger.debug("%s: unreadable campaigns_cache entry — refreshing", godlo)

        if query.endpoint is None:
            raise self._missing_endpoint(query, godlo)
        found: list[SkorowidzRecord] = []
        rejected: list[SkorowidzRecord] = []
        skipped = False
        query_bbox = self._query_bbox(parser)
        for layer in self._layers(query.endpoint, timeout):
            upper = layer_upper_year(self.LAYER_PATTERN, layer)
            if min_year is not None and upper is not None and upper < min_year:
                skipped = True
                logger.debug(
                    "Warstwa %s pominieta (rok %s < %s)", layer, upper, min_year
                )
                continue
            records = self._query_layer(
                parser, query.endpoint, layer, timeout, query_bbox
            )
            matched = select_campaign_records(
                records,
                godlo=godlo,
                uklad=parser.uklad,
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
        scanned_from = min_year if skipped else None
        if not found:
            error = (
                _partial_scan_no_coverage(godlo, min_year)
                if skipped and min_year is not None
                else query.no_coverage(parser, rejected)
            )
            if self._cache is not None:
                self._cache.set_campaigns(
                    *query.cache_key,
                    {
                        "no_coverage": True,
                        "message": str(error),
                        **({"hints": list(error.hints)} if error.hints else {}),
                        "scanned_from": scanned_from,
                    },
                )
            raise error
        if self._cache is not None:
            self._cache.set_campaigns(
                *query.cache_key,
                {
                    "sources": [self.record_source(r) for r in found],
                    "scanned_from": scanned_from,
                },
            )
        return found

    def resolve_campaigns(
        self,
        godlo: str,
        *,
        campaigns: str = "newest",
        min_year: int | None = None,
        timeout: int | None = None,
    ) -> list[SkorowidzRecord]:
        """Campaigns of a sheet per the ADR-030 strategy (newest first).

        ``newest`` = one ADR-028 record (unchanged); with ``min_year`` an
        older one = ``NoCoverageError`` with its date; ``all`` = every record
        passing the hard filter from all layers; with ``min_year`` only
        campaigns with ``aktualnosc`` year >= the boundary.
        """
        # local import: the kartograf.download package imports manager -> providers.pl
        from kartograf.download.campaigns import validate_campaign_args

        validate_campaign_args(campaigns, min_year)
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        parser = SheetParser(godlo)
        godlo = parser.godlo
        query = self._skorowidz_query(parser)
        if campaigns == "newest":
            record = self._resolve_record(parser, timeout, query)
            if not _meets_min_year(record, min_year):
                raise NoCoverageError(
                    f"Najnowsza kampania {godlo} ma date {record.aktualnosc} — "
                    f"starsza niz min_year={min_year} (--min-year)",
                    godlo=godlo,
                )
            return [record]
        found = self._resolve_all(parser, timeout, query, min_year=min_year)
        kept = [r for r in found if _meets_min_year(r, min_year)]
        if not kept:
            raise NoCoverageError(
                f"Brak kampanii {godlo} od roku {min_year} "
                f"(najnowsza: {found[0].aktualnosc})",
                godlo=godlo,
            )
        # the manager logs the campaign count at INFO (`_fetch_campaigns`, M-7)
        logger.debug("%s: %s kampanii", godlo, len(kept))
        return kept

    def record_source(self, record: SkorowidzRecord) -> dict:
        """Record metadata (``to_source``) with the endpoint and ``source_extra``."""
        query = self._skorowidz_query(SheetParser(record.godlo))
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
            # file name from the URL (campaign id + godlo) tells campaigns apart in logs
            description=f"{record.url.rsplit('/', 1)[-1]} ({self.DOWNLOAD_LABEL})",
        )

    def __init__(self) -> None:
        super().__init__()
        self._layers_lock = threading.Lock()
        self._validated_layers: dict[str, list[str]] = {}

    def validate_godlo(self, godlo: str) -> bool:
        """Sheet code parsable by ``SheetParser`` (PL-1992 or PL-2000)."""
        try:
            SheetParser(godlo)
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
                        "do wzorca %s — NIE odpytywana",
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
        if parser.uklad == "2000" and record.godlo.startswith(parser.godlo + "."):
            scale = SheetParser(record.godlo).scale
            hints.add(f"Dostepny potomek {record.godlo} — uzyj --scale {scale}")
        elif record.uklad is not None and record.uklad != parser.uklad:
            scale = SheetParser(record.godlo).scale
            hints.add(
                f"Skorowidz ma ten obszar w PL-{record.uklad}: "
                f"{record.godlo} ({scale}) — uzyj tego godla lub "
                f"--system {record.uklad} --scale {scale}"
            )
    return hints


def no_coverage_error(
    parser: SheetParser, message: str, hints: Iterable[str]
) -> NoCoverageError:
    """``NoCoverageError`` with hints appended in a fixed order."""
    ordered = sorted(hints)
    if ordered:
        message += ". " + "; ".join(ordered)
    return NoCoverageError(message, godlo=parser.godlo, hints=tuple(ordered))
