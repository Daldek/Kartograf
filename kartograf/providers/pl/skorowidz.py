"""Rekordy skorowidza GUGiK: parsowanie, scisly wybor i pochodzenie arkusza."""

import json
import logging
import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urlencode

import requests

from kartograf.core.sheet_parser import SheetParser
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.transport.http import get_with_retry

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


def _horizontal_crs(value: str) -> tuple[str | None, int | None]:
    if value == "PL-1992":
        return "1992", None
    match = re.fullmatch(r"PL-2000:S([5-8])", value)
    return ("2000", int(match[1])) if match else (None, None)


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
