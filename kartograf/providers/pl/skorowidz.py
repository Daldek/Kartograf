"""Rekordy skorowidza GUGiK: parsowanie, scisly wybor i pochodzenie arkusza."""

import json
import logging
import re
import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass
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
from kartograf.transport.http import get_with_retry, make_gugik_session

logger = logging.getLogger(__name__)

_RECORD = re.compile(r"\.push\(\s*\{(.*?)\}\s*\)", re.DOTALL)
_FIELD = re.compile(r'(\w+)\s*:\s*("(?:[^"\\]|\\.)*")')
# Szablon HTML MapServera GUGiK: pusta odpowiedz (morze, zagranica) ma tylko
# naglowek z funkcja createTable (gfi/01-04 z 2026-09-29), deklaracja tablicy
# rekordow `var X = [];` pojawia sie dopiero razem z rekordami.
_TEMPLATE = re.compile(r"\bvar\s+\w+\s*=\s*\[\s*\]\s*;|\bfunction\s+createTable\s*\(")
_OGC_REPORT = re.compile(r"<(?:\w+:)?(?:ServiceException|ExceptionReport)\b")
_OGC_TEXT = re.compile(
    r"<(?:\w+:)?(?:ServiceException|ExceptionText)\b[^>]*>(.*?)</", re.DOTALL
)


def _horizontal_crs(value: str | None) -> tuple[str | None, int | None]:
    """``(uklad, strefa)`` rekordu; ``(None, None)`` = rekord bez ukladu
    (odrzucany w ``select_sheet_record``). Parser: ``parse_pl_uklad`` (D3)."""
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

    def to_source(self, endpoint: str) -> dict:
        """Metadane wybranego pliku do sidecara oraz cache rekordow."""
        return {
            "url": self.url,
            "skorowidz": endpoint,
            "layer": self.layer,
            "godlo": self.godlo,
            "aktualnosc": self.aktualnosc,
            "aktualnosc_rok": self.raw.get("aktualnoscRok") or self.aktualnosc[:4],
            "dt_pzgik": self.dt_pzgik,
            "resolution_m": self.resolution_m,
            "uklad": self.raw.get("ukladWspolrzednychPoziomych")
            or self.raw.get("ukladWspolrzednych"),
            "full_sheet": self.full_sheet,
            "numer_zgloszenia": self.raw.get("numerZgloszeniaPracy"),
            "zrodlo_danych": self.raw.get("zrDanych") or self.raw.get("zrodloDanych"),
        }

    @classmethod
    def from_source(cls, source: dict) -> "SkorowidzRecord":
        """Odtworz wybrany rekord z payloadu cache (bez ponownej selekcji)."""
        uklad, zone = _horizontal_crs(source.get("uklad") or "")
        raw = {
            key: str(source[field])
            for key, field in (
                ("ukladWspolrzednychPoziomych", "uklad"),
                ("aktualnoscRok", "aktualnosc_rok"),
                ("numerZgloszeniaPracy", "numer_zgloszenia"),
                ("zrDanych", "zrodlo_danych"),
            )
            if source.get(field) is not None
        }
        return cls(
            url=source["url"],
            godlo=source["godlo"],
            aktualnosc=source["aktualnosc"],
            dt_pzgik=source.get("dt_pzgik"),
            layer=source["layer"],
            uklad=uklad,
            zone=zone,
            resolution_m=source.get("resolution_m"),
            full_sheet=source.get("full_sheet"),
            raw=raw,
        )


def is_skorowidz_answer(text: str) -> bool:
    """Odpowiedz warstwy = szablon skorowidza GUGiK (takze pusty); inny HTML nie."""
    return _TEMPLATE.search(text) is not None


def _decode_value(literal: str) -> str:
    try:
        return json.loads(literal)
    except ValueError:  # escape spoza JSON (np. \') — wartosc doslowna
        return literal[1:-1]


def parse_skorowidz_records(text: str, layer: str) -> list[SkorowidzRecord]:
    """Rekordy `X.push({...})` z GetFeatureInfo; URL bez filtra rozszerzenia (H1)."""
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


def select_sheet_record(
    records: Iterable[SkorowidzRecord],
    *,
    godlo: str,
    uklad: str,
    zone: int | None = None,
    resolution_m: float | None = None,
    predicate: Callable[[SkorowidzRecord], bool] | None = None,
) -> SkorowidzRecord | None:
    """Wybierz najnowsza kampanie spelniajaca WSZYSTKIE wymagania zadania."""
    godlo = SheetParser(godlo).godlo
    chosen = None
    for record in records:
        if record.uklad is None or record.resolution_m is None:
            logger.warning(
                "Warstwa %s: rekord %s bez ukladu lub rozdzielczosci — pominieto",
                record.layer,
                record.godlo,
            )
            continue
        if record.godlo != godlo or record.uklad != uklad:
            continue
        if uklad == "2000" and record.zone != zone:
            continue
        if resolution_m is not None and abs(record.resolution_m - resolution_m) >= 1e-6:
            continue
        if predicate is not None and not predicate(record):
            continue
        if chosen is None or (record.aktualnosc, record.dt_pzgik or "", record.url) > (
            chosen.aktualnosc,
            chosen.dt_pzgik or "",
            chosen.url,
        ):
            chosen = record
    return chosen


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
    """Zapytaj jedna warstwe; awaria nigdy nie oznacza braku pokrycia."""
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


class SourceInfoMixin:
    """Pochodzenie per godlo, niezalezne od kolejnosci zakonczenia watkow."""

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
    """Sesja HTTP na watek i warstwy skorowidza WMS odkrywane per endpoint.

    Klasa pochodna deklaruje ``LAYER_PATTERN`` o dwoch grupach: grupa 1 = rok
    warstwy (pusta dla warstwy bez roku), grupa 2 = znacznik warstwy zbiorczej
    (``iStarsze``/``Starsze``, pusta dla warstwy rocznej) — oraz ustawia
    ``self._session`` (sesja powierzona przez wolajacego albo ``None``).
    """

    LAYER_PATTERN: re.Pattern[str]
    _session: requests.Session | None
    _cache: MetadataCache | None
    MAX_RETRIES: int
    DEFAULT_TIMEOUT: int

    def _resolve_record(
        self,
        parser: SheetParser,
        timeout: int,
        *,
        cache_key: tuple[str, str, str, str],
        endpoint: str | None,
        no_coverage: Callable[[SheetParser, list[SkorowidzRecord]], NoCoverageError],
        resolution_m: float | None = None,
        predicate: Callable[[SkorowidzRecord], bool] | None = None,
        source_extra: dict | None = None,
    ) -> SkorowidzRecord:
        """Rozwiaz arkusz po warstwach: cache, filtr produktu i podpowiedz braku."""
        godlo = parser.godlo
        if self._cache is not None:
            cached = self._cache.get_record(*cache_key)
            if cached is not None:
                if cached.get("no_coverage"):
                    raise NoCoverageError(
                        cached.get("message") or str(no_coverage(parser, [])),
                        godlo=godlo,
                    )
                source = cached["source"]
                self._remember_source(godlo, source)
                return SkorowidzRecord.from_source(source)

        if endpoint is None:
            raise DownloadError(
                f"Brak endpointu WMS dla {cache_key[1]}, {cache_key[2]}",
                godlo=godlo,
            )
        layers = self._layers(endpoint, timeout)
        bbox = parser.get_bbox(crs="EPSG:2180")
        x = (bbox.min_x + bbox.max_x) / 2
        y = (bbox.min_y + bbox.max_y) / 2
        query_bbox = f"{y - 10},{x - 10},{y + 10},{x + 10}"
        rejected: list[SkorowidzRecord] = []
        for layer in layers:
            records = query_skorowidz_layer(
                self._session_for_thread(),
                endpoint,
                layer,
                query_bbox=query_bbox,
                godlo=godlo,
                timeout=timeout,
                retries=self.MAX_RETRIES,
            )
            chosen = select_sheet_record(
                records,
                godlo=godlo,
                uklad=parser.uklad,
                zone=int(godlo.split(".")[0]) if parser.uklad == "2000" else None,
                resolution_m=resolution_m,
                predicate=predicate,
            )
            if chosen is not None:
                source = chosen.to_source(endpoint)
                if source_extra:
                    source.update(source_extra)
                self._remember_source(godlo, source)
                if self._cache is not None:
                    self._cache.set_record(*cache_key, {"source": source})
                return chosen
            rejected.extend(records)
        error = no_coverage(parser, rejected)
        if self._cache is not None:
            self._cache.set_record(
                *cache_key, {"no_coverage": True, "message": str(error)}
            )
        raise error

    def __init__(self) -> None:
        super().__init__()
        self._local = threading.local()
        self._layers_lock = threading.Lock()
        self._validated_layers: dict[str, list[str]] = {}

    def _session_for_thread(self) -> requests.Session:
        """Jedna sesja na watek albo sesja powierzona przez wolajacego."""
        if self._session is not None:
            return self._session
        if not hasattr(self._local, "session"):
            self._local.session = make_gugik_session()
        return self._local.session

    def _fetch_wms_layers(
        self, wms_endpoint: str, timeout: float | None = None
    ) -> list[str]:
        """Odkryj warstwy produktu; blad uslugi nie ma zaszytego fallbacku.

        ``timeout`` domyslnie = ``DEFAULT_TIMEOUT`` providera (30 s NMT/NMPT,
        60 s orto; N3) — porazka GetCapabilities konczy caly tor, wiec nie
        moze miec krotszego limitu niz pobranie arkusza.
        """
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT
        params = {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetCapabilities"}
        response = get_with_retry(
            self._session_for_thread(),
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
        # {nazwa: (bez roku, zbiorcza, -rok)} — roczne od najnowszej, zbiorcza
        # na koncu, warstwa bez roku ("Starsze") za wszystkimi rocznymi
        layers: dict[str, tuple[bool, bool, int]] = {}
        for elem in root.iter():
            if elem.tag.rsplit("}", 1)[-1] != "Name" or not elem.text:
                continue
            match = self.LAYER_PATTERN.fullmatch(elem.text)
            if match:
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
        """Memoizuj tylko sukces, raz na endpoint; zapytania chroni lock.

        ``timeout`` (domyslnie ``DEFAULT_TIMEOUT`` providera) trafia do
        GetCapabilities — ten sam co dla zapytan warstw w ``_resolve_record``.
        """
        with self._layers_lock:
            if endpoint not in self._validated_layers:
                self._validated_layers[endpoint] = self._fetch_wms_layers(
                    endpoint, timeout
                )
            return self._validated_layers[endpoint]


def coverage_hints(parser: SheetParser, records: Iterable[SkorowidzRecord]) -> set[str]:
    """Podpowiedzi ``NoCoverageError`` wspolne dla NMT/NMPT i orto (D14).

    Potomek PL-2000 zadanego godla -> ``--scale`` potomka; rekord w innym
    ukladzie -> jego godlo albo ``--system``/``--scale``. ``records`` sa juz
    przefiltrowane przez providera (rozdzielczosc NMT); podpowiedzi wlasne
    providera (rozdzielczosc, warianty koloru orto) zostaja u niego.
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
    """``NoCoverageError`` z podpowiedziami dopisanymi w stalej kolejnosci."""
    ordered = sorted(hints)
    if ordered:
        message += ". " + "; ".join(ordered)
    return NoCoverageError(message, godlo=parser.godlo)
