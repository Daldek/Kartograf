"""GUGiK sheet index over WFS: one client and one parser (ADR-041).

The NMT, NMPT and LAZ indexes are WFS 2.0 services (MapServer) with one
feature type per year (``gugik:SkorowidzNMT2025``). ``WfsIndex`` reads the
yearly types from GetCapabilities and the features of an area with ONE
``GetFeature`` for any number of types (``TYPENAMES`` comma-separated,
answered as nested collections), ``BBOX`` and ``SRSNAME`` in the URN of
EPSG:2180 with N,E axes, pages followed ONLY by the ``next`` attribute
(the server ignores ``FILTER`` - every filter is on the client side,
docs/research/2026-10-15-plan-a-b/raport.md 1). A failure is never an
empty answer: transport errors, an ``ExceptionReport`` or non-XML at 200,
a page whose ``numberReturned`` differs from its features - all raise
``DownloadError`` ("wynik bylby niepelny"); a valid empty collection (sea)
yields nothing.

``parse_index_feature`` maps the WFS fields of NMT/NMPT records on the keys
of ``SkorowidzRecord.raw`` used by ``to_source`` and ``CampaignRef``, so the
download of a sheet, the campaign flow and the availability report read one
parser. ``WfsSkorowidzLayersMixin`` gives the sheet flow of NMT/NMPT
(``SkorowidzLayersMixin``: cache, hard filter, campaigns) the WFS index.
"""

import functools
import logging
import re
import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator, Sequence
from urllib.parse import urlencode

import requests

from kartograf.core.coverage import (
    AREA_EPS,
    Polygon,
    clip_convex,
    expand_convex,
    normalize_convex,
    polygon_area,
)
from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.providers.pl.skorowidz import (
    SkorowidzLayersMixin,
    SkorowidzRecord,
    horizontal_crs_of,
    metres,
)
from kartograf.sources.variants import IndexRef
from kartograf.transport.http import MAX_RETRIES, get_with_retry

logger = logging.getLogger(__name__)

GUGIK_NS = "http://www.gugik.gov.pl"
GML_NS = "http://www.opengis.net/gml/3.2"
URN_2180 = "urn:ogc:def:crs:EPSG::2180"
# Features per GetFeature page (COUNT); further pages only through `next`.
PAGE_SIZE = 1000
INCOMPLETE = "wynik bylby niepelny, ponow pobranie"
# Half side (m) of the query square around a sheet centre (sheet lookup).
QUERY_HALF_M = 10.0
# A sheet frame overlaps an area only when it still does after its edges are
# moved inwards by this many metres: neighbouring frames share edges up to the
# 1 cm rounding of GUGiK coordinates (a 5 km x 1 cm sliver is 50 m2).
EDGE_TOLERANCE_M = 1.0
# Points per edge of a sheet frame transformed to EPSG:2180 (curved edges).
_FRAME_POINTS = 16


def localname(tag: str) -> str:
    """Local name of a possibly namespaced XML tag."""
    return tag.rsplit("}", 1)[-1]


def corner_xy(text: str, srs_name: str | None) -> tuple[float, float]:
    """An EPSG:2180 position as (Easting, Northing).

    URN/URI identifiers use the EPSG axis order (N, E); a missing ``srsName``
    inherits the requested URN. Only the legacy ``EPSG:2180`` uses (E, N).
    """
    first, second = (float(value) for value in text.split()[:2])
    if srs_name == "EPSG:2180":
        return first, second
    return second, first


def feature_footprint(feature: ET.Element) -> tuple[tuple[float, float], ...] | None:
    """Sheet/tile frame from ``gugik:msGeometry`` as a convex (E, N) polygon.

    Only a single ``gml:Polygon`` without holes: other geometry (multi,
    holes, concave polygon) gives ``None``. Axes as in ``corner_xy``.
    """
    geometry = feature.find(f"{{{GUGIK_NS}}}msGeometry")
    if geometry is None:
        return None
    polygons = list(geometry.iter(f"{{{GML_NS}}}Polygon"))
    if len(polygons) != 1 or polygons[0].find(f"{{{GML_NS}}}interior") is not None:
        return None
    polygon = polygons[0]
    pos_list = polygon.find(
        f"{{{GML_NS}}}exterior/{{{GML_NS}}}LinearRing/{{{GML_NS}}}posList"
    )
    if pos_list is None or not pos_list.text:
        return None
    try:
        values = [float(v) for v in pos_list.text.split()]
    except ValueError:
        return None
    if len(values) % 2:
        return None
    srs_name = polygon.get("srsName")
    points = [
        corner_xy(f"{values[i]} {values[i + 1]}", srs_name)
        for i in range(0, len(values), 2)
    ]
    return normalize_convex(points)


def time_position(feature: ET.Element, name: str) -> str | None:
    """Text of the ``gml:timePosition`` of a time attribute (e.g. ``akt_data``)."""
    elem = feature.find(f"{{{GUGIK_NS}}}{name}")
    if elem is None:
        return None
    for child in elem.iter(f"{{{GML_NS}}}timePosition"):
        if child.text:
            return child.text.strip()
    return elem.text.strip() if elem.text and elem.text.strip() else None


def feature_text(feature: ET.Element, name: str) -> str | None:
    """Stripped text of a ``gugik:`` attribute; ``None`` when missing or empty."""
    child = feature.find(f"{{{GUGIK_NS}}}{name}")
    if child is not None and child.text and child.text.strip():
        return child.text.strip()
    return None


def bbox_param(bbox: BBox) -> str:
    """``BBOX`` of an EPSG:2180 area in the URN axis order (N, E)."""
    return f"{bbox.min_y},{bbox.min_x},{bbox.max_y},{bbox.max_x},{URN_2180}"


_YEAR = re.compile(r"(\d{4})$")


def type_year(name: str) -> int:
    """Year of a yearly feature type (``gugik:SkorowidzNMT2025`` -> 2025)."""
    match = _YEAR.search(name)
    if match is None:
        raise ValueError(f"typ obiektu bez roku: {name!r}")
    return int(match[1])


class WfsIndex:
    """One WFS index service (``endpoint``) with yearly types ``<prefix><year>``.

    ``session_factory`` returns the session of the calling thread
    (``SessionPerThread.get``); ``timeout``/``retries`` go to every request.
    Feature types are memoized after the first successful GetCapabilities.
    """

    def __init__(
        self,
        session_factory: Callable[[], requests.Session],
        endpoint: str,
        layer_prefix: str,
        *,
        timeout: float,
        retries: int = MAX_RETRIES,
    ):
        self._session_factory = session_factory
        self._endpoint = endpoint
        self._prefix = layer_prefix
        self._timeout = timeout
        self._retries = retries
        self._types: list[str] | None = None
        self._lock = threading.Lock()
        self._feature_tag = f"{{{GUGIK_NS}}}{layer_prefix}"

    @property
    def endpoint(self) -> str:
        """WFS address of the service."""
        return self._endpoint

    @property
    def layer_prefix(self) -> str:
        """Name prefix of the yearly feature types."""
        return self._prefix

    def _xml(self, url: str, description: str) -> ET.Element:
        """Parsed answer; any failure is a ``DownloadError``, never empty."""
        try:
            response = get_with_retry(
                self._session_factory(),
                url,
                timeout=self._timeout,
                retries=self._retries,
                description=description,
            )
        except DownloadError as e:
            raise DownloadError(f"{e} - {INCOMPLETE}") from e
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as e:
            raise DownloadError(
                f"{description}: odpowiedz WFS nieczytelna: {e} - {INCOMPLETE}"
            ) from e
        if localname(root.tag) == "ExceptionReport":
            details = "; ".join(
                elem.text.strip()
                for elem in root.iter()
                if localname(elem.tag) == "ExceptionText" and elem.text
            )
            raise DownloadError(
                f"{description}: ExceptionReport: {details} - {INCOMPLETE}"
            )
        return root

    def feature_types(self) -> list[str]:
        """Yearly feature types of the service, newest first (as published).

        A type of the product family outside ``<prefix><year>`` is logged
        and not queried; no yearly type at all is a ``DownloadError``.
        """
        with self._lock:
            if self._types is None:
                self._types = self._fetch_types()
            return list(self._types)

    def _fetch_types(self) -> list[str]:
        params = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetCapabilities"}
        description = f"WFS GetCapabilities {self._endpoint}"
        root = self._xml(f"{self._endpoint}?{urlencode(params)}", description)
        pattern = re.compile(rf"(?:\w+:)?{re.escape(self._prefix)}(\d{{4}})")
        family = re.compile(rf"(?:\w+:)?{re.escape(self._prefix)}")
        found: dict[str, int] = {}
        for elem in root.iter():
            if localname(elem.tag) != "FeatureType":
                continue
            for name in elem:
                if localname(name.tag) != "Name" or not name.text:
                    continue
                text = name.text.strip()
                match = pattern.fullmatch(text)
                if match is not None:
                    found[text] = int(match[1])
                elif family.match(text):
                    logger.warning(
                        "Typ obiektu %s z rodziny %s nie pasuje do wzorca "
                        "<prefiks><rok> - NIE odpytywany",
                        text,
                        self._prefix,
                    )
        if not found:
            raise DownloadError(
                f"{description}: brak typow obiektow {self._prefix}<rok> - {INCOMPLETE}"
            )
        return sorted(found, key=lambda t: -found[t])

    def features(self, bbox: BBox, types: Sequence[str]) -> Iterator[ET.Element]:
        """Features of ``types`` intersecting an EPSG:2180 ``bbox`` (all pages).

        One ``GetFeature`` with every type; further pages only through the
        ``next`` attribute of the answer (it must point at this service).
        """
        if bbox.crs != "EPSG:2180":
            raise ValidationError(f"obszar musi byc w EPSG:2180, podano {bbox.crs}")
        if not types:
            return
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": ",".join(types),
            "SRSNAME": URN_2180,
            "BBOX": bbox_param(bbox),
            "COUNT": str(PAGE_SIZE),
        }
        shown = types[0] if len(types) == 1 else f"{len(types)} typow {self._prefix}"
        url: str | None = f"{self._endpoint}?{urlencode(params)}"
        seen: set[str] = set()
        page = 0
        while url is not None:
            if url in seen:
                raise DownloadError(
                    f"WFS {self._endpoint}: petla stronicowania - {INCOMPLETE}"
                )
            seen.add(url)
            page += 1
            description = f"WFS GetFeature {shown} (strona {page})"
            root = self._xml(url, description)
            if localname(root.tag) != "FeatureCollection":
                raise DownloadError(
                    f"{description}: odpowiedz nie jest kolekcja obiektow "
                    f"({localname(root.tag)}) - {INCOMPLETE}"
                )
            found = [elem for elem in root.iter() if self._is_feature(elem)]
            returned = root.get("numberReturned", "")
            if not returned.isdigit() or int(returned) != len(found):
                raise DownloadError(
                    f"{description}: numberReturned={returned!r}, obiektow "
                    f"{len(found)} - {INCOMPLETE}"
                )
            yield from found
            following = root.get("next")
            if following and not following.startswith(f"{self._endpoint}?"):
                raise DownloadError(
                    f"{description}: strona next spoza uslugi ({following}) - "
                    f"{INCOMPLETE}"
                )
            url = following or None

    def _is_feature(self, elem: ET.Element) -> bool:
        tag = elem.tag
        return isinstance(tag, str) and tag.startswith(self._feature_tag)


def parse_index_feature(feature: ET.Element) -> SkorowidzRecord | None:
    """``SkorowidzRecord`` of one NMT/NMPT feature; ``None`` when unusable.

    WFS fields map on the ``raw`` keys of the index record: ``url_do_pobrania``
    -> ``url``, ``godlo`` -> ``sheet`` (canonical), ``akt_data`` ->
    ``aktualnosc``, ``akt_rok`` -> ``aktualnoscRok``, ``dt_pzgik``,
    ``uklad_xy`` -> ``ukladWspolrzednychPoziomych``, ``uklad_h`` ->
    ``ukladWspolrzednychPionowych``, ``char_przestrz`` ->
    ``charakterystykaPrzestrzenna`` (``resolution_m``), ``czy_ark_wypelniony``
    -> ``calyArkuszWypelnionyTrescia`` (``full_sheet``), ``nr_zglosz`` ->
    ``numerZgloszeniaPracy``, ``zrodlo_danych`` -> ``zrodloDanych``,
    ``format``, ``blad_sr_wys`` -> ``bladSredniWysokosci``, ``blad_sr_syt``
    -> ``bladSredniPolozenia``, ``modul_archiwizacji`` -> ``modulArchiwizacji``;
    ``layer`` = the feature type (``SkorowidzNMT2025``). A feature without
    an HTTPS URL or with a sheet code outside ``SheetParser`` gives ``None``
    (``index_feature_issue`` names the reason).
    """
    if index_feature_issue(feature) is not None:
        return None
    layer = localname(feature.tag)
    url = feature_text(feature, "url_do_pobrania") or ""
    sheet = SheetParser(feature_text(feature, "godlo") or "").sheet
    declared_crs = feature_text(feature, "uklad_xy")
    system, zone = horizontal_crs_of(declared_crs)
    resolution_text = feature_text(feature, "char_przestrz")
    full_text = feature_text(feature, "czy_ark_wypelniony")
    date = time_position(feature, "akt_data") or ""
    raw = {
        key: value
        for key, value in (
            ("url", url),
            ("godlo", feature_text(feature, "godlo")),
            ("aktualnosc", date),
            ("aktualnoscRok", feature_text(feature, "akt_rok")),
            ("dt_pzgik", time_position(feature, "dt_pzgik")),
            ("ukladWspolrzednychPoziomych", declared_crs),
            ("ukladWspolrzednychPionowych", feature_text(feature, "uklad_h")),
            ("charakterystykaPrzestrzenna", resolution_text),
            ("calyArkuszWypelnionyTrescia", full_text),
            ("numerZgloszeniaPracy", feature_text(feature, "nr_zglosz")),
            ("zrodloDanych", feature_text(feature, "zrodlo_danych")),
            ("format", feature_text(feature, "format")),
            ("bladSredniWysokosci", feature_text(feature, "blad_sr_wys")),
            ("bladSredniPolozenia", feature_text(feature, "blad_sr_syt")),
            ("modulArchiwizacji", feature_text(feature, "modul_archiwizacji")),
        )
        if value
    }
    record = SkorowidzRecord(
        url=url,
        sheet=sheet,
        aktualnosc=date,
        dt_pzgik=raw.get("dt_pzgik"),
        layer=layer,
        system=system,
        zone=zone,
        resolution_m=metres(resolution_text),
        full_sheet={"TAK": True, "NIE": False}.get((full_text or "").upper()),
        raw=raw,
    )
    year = raw.get("aktualnoscRok") or date[:4]
    match = _YEAR.search(layer)
    if match and year.isdigit() and year != match[1]:
        logger.warning(
            "Warstwa %s: rekord %s ma rok %s poza partycja warstwy", layer, sheet, year
        )
    return record


def index_feature_issue(feature: ET.Element) -> str | None:
    """Why a feature cannot become a record (``None`` = usable).

    ``"url"``: no HTTPS ``url_do_pobrania``; ``"sheet"``: ``godlo`` outside
    the sheet systems of ``SheetParser`` (e.g. 8-part PL-1992 codes).
    """
    url = feature_text(feature, "url_do_pobrania") or ""
    if not url.startswith("https://"):
        return "url"
    try:
        SheetParser(feature_text(feature, "godlo") or "")
    except (ParseError, ValidationError):
        return "sheet"
    return None


def sheet_query_bbox(parser: SheetParser) -> BBox:
    """``QUERY_HALF_M`` square around the centre of a sheet in EPSG:2180."""
    frame = parser.get_bbox(crs="EPSG:2180")
    x = (frame.min_x + frame.max_x) / 2
    y = (frame.min_y + frame.max_y) / 2
    return BBox(
        x - QUERY_HALF_M,
        y - QUERY_HALF_M,
        x + QUERY_HALF_M,
        y + QUERY_HALF_M,
        "EPSG:2180",
    )


class WfsSkorowidzLayersMixin(SkorowidzLayersMixin):
    """Sheet records of NMT/NMPT from the WFS index of the provider's variant.

    ``_layers`` gives ONE group: every yearly type of the service, queried by
    one ``GetFeature`` around the sheet centre (``_query_layer``); cache,
    hard filter (``SkorowidzQuery``), campaigns and no-coverage hints stay in
    ``SkorowidzLayersMixin``. The derived class sets ``self._sessions`` and
    ``self._index_refs`` (endpoint -> ``IndexRef`` of the services it may ask).
    """

    _index_refs: dict[str, IndexRef]

    def __init__(self) -> None:
        super().__init__()
        self._wfs_lock = threading.Lock()
        self._wfs: dict[str, WfsIndex] = {}

    def _wfs_index(self, endpoint: str, retries: int | None = None) -> WfsIndex:
        """``WfsIndex`` of a known service (one per endpoint and retry policy)."""
        attempts = self.MAX_RETRIES if retries is None else retries
        key = f"{endpoint}|{attempts}"
        with self._wfs_lock:
            index = self._wfs.get(key)
            if index is None:
                ref = self._index_refs[endpoint]
                index = WfsIndex(
                    self._sessions.get,
                    ref.endpoint,
                    ref.layer_prefix,
                    timeout=self.DEFAULT_TIMEOUT,
                    retries=attempts,
                )
                self._wfs[key] = index
            return index

    def _layers(self, endpoint: str, timeout: float | None = None) -> list[str]:
        """One query group: every yearly type of the service (newest first)."""
        with self._layers_lock:
            if endpoint not in self._validated_layers:
                types = self._wfs_index(endpoint).feature_types()
                self._validated_layers[endpoint] = [",".join(types)]
            return self._validated_layers[endpoint]

    def _query_layer(
        self,
        parser: SheetParser,
        endpoint: str,
        layer: str,
        timeout: int,
        query_bbox: str,
    ) -> list[SkorowidzRecord]:
        """Records of every type of ``layer`` around the sheet centre."""
        index = self._wfs_index(endpoint)
        return index_records(index, sheet_query_bbox(parser), layer.split(","))


def index_records(
    index: WfsIndex, bbox: BBox, types: Sequence[str]
) -> list[SkorowidzRecord]:
    """Parsed records of ``types`` in ``bbox`` (unusable features skipped)."""
    return [
        record
        for feature in index.features(bbox, types)
        if (record := parse_index_feature(feature)) is not None
    ]


@functools.lru_cache(maxsize=8)
def _to_2180(source_crs: str):
    from pyproj import Transformer

    return Transformer.from_crs(source_crs, "EPSG:2180", always_xy=True)


def convex_hull(points: Sequence[tuple[float, float]]) -> Polygon:
    """Convex hull (CCW, Andrew's monotone chain) of at least three points."""
    pts = sorted(set(points))

    def cross(o, a, b) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return tuple(lower[:-1] + upper[:-1])


def sheet_frame_2180(sheet: str) -> Polygon:
    """Frame of a sheet code as a convex (E, N) polygon in EPSG:2180.

    The frame is a rectangle in the CRS of the sheet system (PL-1992:
    WGS84 degrees, PL-2000: the zone CRS); its densified edges are curves
    in EPSG:2180, one of them bent inwards, so the frame is the convex hull
    of the curves - wider than the frame by the bend of that edge (about
    0.1 m for a 1:10000 sheet, 0.5 m for 1:25000, below ``EDGE_TOLERANCE_M``).
    """
    parser = SheetParser(sheet)
    native = (
        parser.get_bbox()
        if parser.sheet_system == "2000"
        else parser.get_bbox("EPSG:4326")
    )
    corners = (
        (native.min_x, native.min_y),
        (native.max_x, native.min_y),
        (native.max_x, native.max_y),
        (native.min_x, native.max_y),
    )
    xs: list[float] = []
    ys: list[float] = []
    for i, (x0, y0) in enumerate(corners):
        x1, y1 = corners[(i + 1) % 4]
        for step in range(_FRAME_POINTS):
            t = step / _FRAME_POINTS
            xs.append(x0 + t * (x1 - x0))
            ys.append(y0 + t * (y1 - y0))
    east, north = _to_2180(native.crs).transform(xs, ys)
    return convex_hull(list(zip(east, north, strict=True)))


def area_envelope(areas: Sequence[Polygon]) -> BBox:
    """EPSG:2180 envelope of convex (E, N) polygons."""
    xs = [x for area in areas for x, _ in area]
    ys = [y for area in areas for _, y in area]
    return BBox(min(xs), min(ys), max(xs), max(ys), "EPSG:2180")


def overlaps_area(frame: Polygon, area: Polygon) -> bool:
    """A sheet frame overlaps an area by more than an edge sliver.

    The frame with its edges moved ``EDGE_TOLERANCE_M`` inwards must still
    intersect the convex area (both (E, N) in EPSG:2180, compared in local
    coordinates). Shared by the archive sheet selection and the
    availability report: a neighbour sharing an edge never counts.
    """
    ox, oy = area[0]
    local_frame = tuple((x - ox, y - oy) for x, y in frame)
    local_area = tuple((x - ox, y - oy) for x, y in area)
    inner = expand_convex(local_frame, -EDGE_TOLERANCE_M)
    if polygon_area(inner) <= AREA_EPS:
        return False  # a frame narrower than twice the tolerance
    part = clip_convex(inner, local_area)
    return len(part) >= 3 and abs(polygon_area(part)) > AREA_EPS
