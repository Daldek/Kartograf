"""Index records giving the file of one unit (sheet or tile) (ADR-043).

Two kinds of index (``IndexSource.kind``):

- ``wms_gfi``: one WMS 1.3.0 GetFeatureInfo at the centre of a PL sheet,
  read by ``IndexSource.parser``. ``map_links`` is the HTML table of the
  BDOT10k map sheets (``PobieranieArkuszeMapBDOT10k``, layers ``Mapy10k`` ..
  ``Mapy100k``): sheet code, one link per format (PDF, GeoTIFF) and the base
  date "Stan bazy BDOT10k na dzien" (recorded 2026-10-16; 1:10000 gives a
  bare date, 1:25000-1:100000 a date with ``00:00:00``). A point outside the
  layer is an empty body (0 B) - no record.
- ``wfs``: the features of an EPSG:2180 area of one feature type
  (``WfsIndex``: pages only through ``next``, checked); every feature is the
  record of one tile. Fields are read by local name (the mesh index publishes
  the ``https://www.gugik.gov.pl`` namespace, NMT ``http://``).

A failure is never an empty result: anything else than the documented
answers is a ``DownloadError`` ("wynik bylby niepelny"); only a single
unusable WFS feature is skipped with a warning naming its ``gml:id``.
"""

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import urlencode, urlparse

import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.providers.pl.skorowidz_wfs import (
    GML_NS,
    QUERY_HALF_M,
    WfsIndex,
    localname,
)
from kartograf.sources.descriptor import IndexSource
from kartograf.sources.edition import edition_label
from kartograf.sources.registry import parse_pl_system
from kartograf.transport.http import get_with_retry

logger = logging.getLogger(__name__)

INCOMPLETE = "wynik bylby niepelny"
# Pixel grid of the GetFeatureInfo query (the point is the centre pixel).
_GFI_SIZE = 100
_OGC_REPORT = re.compile(r"<(?:\w+:)?(?:ServiceException|ExceptionReport)\b")
_OGC_TEXT = re.compile(
    r"<(?:\w+:)?(?:ServiceException|ExceptionText)\b[^>]*>(.*?)</", re.DOTALL
)
# Header cells of the map sheet table (compared casefolded, without ":").
_SHEET_HEADER = "god\u0142o"
_DATE_HEADER = "stan bazy"
# Base date as published: "2026-05-27" (1:10000) or "2025-01-31 00:00:00".
_BASE_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:[ T]\d{2}:\d{2}:\d{2})?")
_LINK_FORMATS = {".pdf": "PDF", ".tif": "TIFF", ".tiff": "TIFF"}


@dataclass(frozen=True)
class IndexRecord:
    """One index record: the file(s) of one unit and its version.

    ``unit``: the canonical PL sheet code (``SheetParser(...).sheet``) of a
    GFI record, the tile id (``unit_field``, e.g. ``"74230_55482"``) of a WFS
    record - or, without ``unit_field``, the name of its file without the
    suffix (``"78944_6777_74230_55482"``). ``urls``: file format in upper
    case (``"PDF"``, ``"TIFF"``) -> HTTPS URL, ``{"": url}`` for a record with
    one URL (``url_field``).
    ``label``: version label (D29, ``edition_label``). ``year``: year of the
    data (``year_field``; ``map_links``: year of the base date). ``zone``:
    slot directory of a tile from ``zone_field`` (``"PL-2000:S7"`` ->
    ``"2000/7"``, ``"PL-1992"`` -> ``"1992"``, ADR-044 D7); ``None`` without
    ``zone_field``. ``raw``: source fields as published (sidecar
    ``extra.source``).
    """

    unit: str
    urls: Mapping[str, str]
    label: str
    year: int | None
    zone: str | None
    raw: Mapping[str, str]


def gfi_records(
    session: requests.Session,
    source: IndexSource,
    layer: str,
    sheet: str,
    *,
    timeout: float,
) -> list[IndexRecord]:
    """Records of ``layer`` at the centre of the PL sheet ``sheet``.

    WMS 1.3.0 GetFeatureInfo (``LAYERS=QUERY_LAYERS=layer``), EPSG:2180 with
    N,E axes, a ``QUERY_HALF_M`` square around the centre of the sheet frame,
    the centre pixel of a 100 x 100 image; the answer is read by
    ``records_from_gfi``. An invalid sheet code or source is a
    ``ValidationError`` before any request.
    """
    _check_gfi_source(source)
    parser = SheetParser(sheet)
    frame = parser.get_bbox(crs="EPSG:2180")
    east = (frame.min_x + frame.max_x) / 2
    north = (frame.min_y + frame.max_y) / 2
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": layer,
        "QUERY_LAYERS": layer,
        "INFO_FORMAT": "text/html",
        "CRS": "EPSG:2180",
        "BBOX": (
            f"{north - QUERY_HALF_M},{east - QUERY_HALF_M},"
            f"{north + QUERY_HALF_M},{east + QUERY_HALF_M}"
        ),
        "WIDTH": _GFI_SIZE,
        "HEIGHT": _GFI_SIZE,
        "I": _GFI_SIZE // 2,
        "J": _GFI_SIZE // 2,
    }
    context = f"{parser.sheet}: warstwa {layer}"
    response = get_with_retry(
        session,
        f"{source.endpoint}?{urlencode(params)}",
        timeout=timeout,
        description=context,
    )
    return records_from_gfi(
        response.content, source=source, layer=layer, context=context
    )


def records_from_gfi(
    content: bytes, *, source: IndexSource, layer: str, context: str
) -> list[IndexRecord]:
    """Records of one GetFeatureInfo answer of ``layer`` (``source.parser``).

    ``map_links``: an empty answer (point outside the layer) -> ``[]``; one
    record per map sheet table. An OGC exception or any other content (HTML
    without the table, a table without the base date, an HTTPS link or a
    valid sheet code) is a ``DownloadError`` - never an empty result.
    """
    _check_gfi_source(source)
    if not content.strip():
        return []
    try:
        # GUGiK sends text/html without a charset; the page is UTF-8
        text = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise _incomplete(f"{context}: odpowiedz GFI nie jest UTF-8 ({e})") from e
    if _OGC_REPORT.search(text):
        match = _OGC_TEXT.search(text)
        excerpt = " ".join((match[1] if match else text).split())[:200]
        raise _incomplete(f"{context}: raport wyjatku OGC: {excerpt}")
    reader = _TableReader()
    reader.feed(text)
    reader.close()
    tables = [rows for rows in reader.tables if _row(rows, _SHEET_HEADER)]
    if not tables:
        raise _incomplete(f"{context}: odpowiedz bez tabeli arkusza warstwy {layer}")
    return [_map_links_record(rows, context) for rows in tables]


def wfs_records(
    session_factory: Callable[[], requests.Session],
    source: IndexSource,
    layer: str,
    bbox: BBox,
    *,
    timeout: float,
    cache: MetadataCache | None = None,
) -> list[IndexRecord]:
    """Records of the features of type ``layer`` in an EPSG:2180 ``bbox``.

    ``WfsIndex`` reads every page (``next`` only, ``numberReturned`` and the
    host of ``next`` checked; ``ExceptionReport`` or non-XML at 200 ->
    ``DownloadError``); ``records_from_wfs`` maps the features. ``cache``:
    the records of the area are kept in the metadata cache
    (``index_area_cache``, its TTL) like the records of the PL sheet
    indexes - a repeated area asks no service; a refreshing cache
    (``--check-updates``, ``--upgrade``, ``--force``) asks again.
    """
    _check_wfs_source(source)
    key = f"wfs-records|{source.endpoint}|{layer}|{_mm(bbox)}"
    if cache is not None:
        restored = _restore_records(cache.get_index_area(key))
        if restored is not None:
            return restored
    index = WfsIndex(
        session_factory, source.endpoint, layer.rsplit(":", 1)[-1], timeout=timeout
    )
    records = records_from_wfs(index.features(bbox, [layer]), source=source)
    if cache is not None:
        cache.set_index_area(key, [asdict(record) for record in records])
    return records


def _mm(bbox: BBox) -> str:
    """Cache key part: the envelope in whole millimetres."""
    return ",".join(
        str(round(value * 1000))
        for value in (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    )


def _restore_records(payload: object) -> list[IndexRecord] | None:
    """Records of a cache payload; ``None`` (a miss) for an unreadable one."""
    if not isinstance(payload, list):
        return None
    records = []
    for item in payload:
        try:
            record = IndexRecord(**item)
        except TypeError:
            return None
        if not (
            isinstance(record.unit, str)
            and isinstance(record.label, str)
            and isinstance(record.urls, dict)
            and isinstance(record.raw, dict)
            and (record.year is None or isinstance(record.year, int))
            and (record.zone is None or isinstance(record.zone, str))
        ):
            return None
        records.append(record)
    return records


def records_from_wfs(
    features: Iterable[ET.Element], *, source: IndexSource
) -> list[IndexRecord]:
    """Records of WFS features (fields by local name, ``source`` fields).

    An unusable feature (no unit, no HTTPS URL, no label value, a label
    outside D29, a year that is not a number, an unknown zone) is skipped with
    a warning naming its ``gml:id``.
    """
    _check_wfs_source(source)
    records = []
    for feature in features:
        fid = feature.get(f"{{{GML_NS}}}id") or "?"
        try:
            records.append(_wfs_record(feature, source))
        except _Unusable as e:
            logger.warning(
                "Indeks %s: obiekt %s pominiety (%s)", source.endpoint, fid, e
            )
    return records


class _Unusable(Exception):
    """A WFS feature that cannot become a record (reason in Polish)."""


def _wfs_record(feature: ET.Element, source: IndexSource) -> IndexRecord:
    raw = _feature_fields(feature)
    url = raw.get(source.url_field or "", "")
    if not url.startswith("https://"):
        raise _Unusable(f"brak adresu HTTPS w polu {source.url_field}")
    if source.unit_field is None:
        unit = PurePosixPath(urlparse(url).path).stem
        if not unit:
            raise _Unusable(f"adres {url} bez nazwy pliku")
    else:
        unit = raw.get(source.unit_field, "")
        if not unit:
            raise _Unusable(f"brak pola {source.unit_field}")
    parts = [raw[name] for name in source.label_fields if raw.get(name)]
    if not parts:
        raise _Unusable(f"brak wartosci pol etykiety {', '.join(source.label_fields)}")
    try:
        label = edition_label("_".join(parts), what=f"kafel {unit}")
    except DownloadError as e:
        raise _Unusable(str(e)) from e
    year: int | None = None
    if source.year_field is not None and (text := raw.get(source.year_field)):
        if not text.isdigit():
            raise _Unusable(f"rok {text!r} w polu {source.year_field} nie jest liczba")
        year = int(text)
    zone: str | None = None
    if source.zone_field is not None:
        zone = _zone_slot(raw.get(source.zone_field))
        if zone is None:
            raise _Unusable(
                f"nieznany uklad {raw.get(source.zone_field)!r} "
                f"w polu {source.zone_field}"
            )
    return IndexRecord(
        unit=unit, urls={"": url}, label=label, year=year, zone=zone, raw=raw
    )


def _feature_fields(feature: ET.Element) -> dict[str, str]:
    """Simple fields of a feature by local name (geometry and envelope skipped).

    A time field published as ``gml:TimeInstant`` gives its ``timePosition``.
    """
    fields: dict[str, str] = {}
    for child in feature:
        if not isinstance(child.tag, str):
            continue
        if len(child):
            positions = [
                elem.text.strip()
                for elem in child.iter(f"{{{GML_NS}}}timePosition")
                if elem.text and elem.text.strip()
            ]
            if not positions:
                continue  # geometry, gml:boundedBy
            value = positions[0]
        else:
            value = (child.text or "").strip()
        if value:
            fields[localname(child.tag)] = value
    return fields


def _zone_slot(value: str | None) -> str | None:
    """Slot directory of a GUGiK CRS (ADR-044 D7): the PL system as in the
    segments, a PL-2000 zone below it as in the PL-2000 sheet codes
    (``PL-2000:S7`` -> ``2000/7``, ``PL-1992`` -> ``1992``); ``None`` for an
    unknown value."""
    parsed = parse_pl_system(value)
    if parsed is None:
        return None
    system, zone = parsed
    return f"{system}/{zone}" if zone is not None else system


def _map_links_record(rows: list["_Row"], context: str) -> IndexRecord:
    """Record of one BDOT10k map sheet table."""
    sheet_row = _row(rows, _SHEET_HEADER)
    published = sheet_row.text if sheet_row is not None else ""
    try:
        unit = SheetParser(published).sheet
    except (ParseError, ValidationError) as e:
        raise _incomplete(f"{context}: nieprawidlowe godlo {published!r}") from e
    date_row = _row(rows, _DATE_HEADER)
    stated = date_row.text if date_row is not None else ""
    match = _BASE_DATE.fullmatch(stated)
    if match is None:
        raise _incomplete(f"{context}: arkusz {published} bez daty stanu bazy")
    urls: dict[str, str] = {}
    for row in rows:
        for href in row.links:
            kind = _LINK_FORMATS.get(_extension(href))
            if kind is None:
                continue
            if not href.startswith("https://"):
                raise _incomplete(f"{context}: link {href!r} bez HTTPS")
            if urls.setdefault(kind, href) != href:
                raise _incomplete(f"{context}: arkusz {published} ma dwa linki {kind}")
    if not urls:
        raise _incomplete(f"{context}: arkusz {published} bez linku PDF/GeoTIFF")
    raw = {"godlo": published, "stan_bazy": stated}
    raw.update({f"url_{kind.lower()}": href for kind, href in urls.items()})
    return IndexRecord(
        unit=unit,
        urls=urls,
        label=edition_label(match[1], what=context),
        year=int(match[1][:4]),
        zone=None,
        raw=raw,
    )


def _extension(href: str) -> str:
    path = urlparse(href).path.lower()
    dot = path.rfind(".")
    return path[dot:] if dot > path.rfind("/") else ""


def _row(rows: list["_Row"], header: str) -> "_Row | None":
    """First row whose header cell starts with ``header`` (casefolded)."""
    for row in rows:
        if row.header.casefold().strip().rstrip(":").strip().startswith(header):
            return row
    return None


def _check_gfi_source(source: IndexSource) -> None:
    if source.kind != "wms_gfi" or source.parser != "map_links":
        raise ValidationError(
            f"indeks {source.endpoint}: odczyt GFI wymaga kind='wms_gfi' i "
            f"parser='map_links' (podano {source.kind!r}, {source.parser!r})"
        )


def _check_wfs_source(source: IndexSource) -> None:
    if source.kind != "wfs" or source.url_field is None:
        raise ValidationError(
            f"indeks {source.endpoint}: odczyt WFS wymaga kind='wfs' i url_field "
            f"(podano {source.kind!r}, {source.url_field!r})"
        )


def _incomplete(message: str) -> DownloadError:
    return DownloadError(f"{message} - {INCOMPLETE}")


@dataclass
class _Row:
    """One table row: header cell text, data cell text, data cell links."""

    header: str = ""
    text: str = ""
    links: list[str] = field(default_factory=list)


class _TableReader(HTMLParser):
    """Rows (``th`` header, ``td`` text and ``href``s) of every HTML table.

    Tolerates the unclosed ``<a >`` of the GUGiK template.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[_Row]] = []
        self._depth = 0
        self._row: _Row | None = None
        self._cell: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._depth += 1
            self.tables.append([])
        elif tag == "tr" and self._depth:
            self._end_cell()
            self._row = _Row()
            self.tables[-1].append(self._row)
        elif tag in ("th", "td") and self._row is not None:
            self._end_cell()
            self._cell = tag
            self._parts = []
        elif tag == "a" and self._cell == "td" and self._row is not None:
            href = dict(attrs).get("href")
            if href:
                self._row.links.append(href.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag in ("th", "td"):
            self._end_cell()
        elif tag == "tr":
            self._end_cell()
            self._row = None
        elif tag == "table" and self._depth:
            self._end_cell()
            self._row = None
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._parts.append(data)

    def _end_cell(self) -> None:
        if self._cell is None or self._row is None:
            self._cell = None
            return
        text = " ".join("".join(self._parts).split())
        if self._cell == "th":
            self._row.header = text
        else:
            self._row.text = text
        self._cell = None
