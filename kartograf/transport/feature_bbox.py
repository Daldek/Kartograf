"""
Engine ``feature_bbox`` (ADR-042 D3/D4): features of an area from WFS 2.0
or an ArcGIS REST layer, saved page by page for ``transform.gpkg``.

Completeness comes from a number, never from links. Before the first page
the service metadata is fetched fresh (no metadata cache, D3): WFS
``GetCapabilities`` once per ``fetch_features`` (every layer exists as a
FeatureType whose DefaultCRS has the EPSG code of ``native_crs``, the
``CountDefault`` limit is not below ``page_size``) and ``DescribeFeatureType``
per layer (the XSD saved for GDAL); ArcGIS ``<layer>?f=json`` per layer (no
``error``, the layer CRS - ``latestWkid``/``wkid`` of ``extent``, else of
``sourceSpatialReference`` - has the native code, the id and order fields
exist, ``maxRecordCount`` is not below ``page_size``). N comes from WFS
``RESULTTYPE=hits`` (``numberMatched``; ``unknown`` = ``DownloadError``) or
ArcGIS ``returnCountOnly``. N = 0 in every layer is ``NoCoverageError``
without pages. Pages are requested by position - WFS ``STARTINDEX``/``COUNT``,
ArcGIS ``resultOffset``/``resultRecordCount`` with ``orderByFields`` - and
``next`` links are ignored (MapServer drops ``next`` from middle pages,
GeoServer puts it on the last page).

Page loop (measured live 2026-10-15): MapServer (GUGiK PRG, EGiB) repeats a
feature across a page boundary, so a stream of N features may have N+1 rows
and the last unique feature may sit past position N-1. PRG A06 in BBOX
N 244000-244400, E 566000-566400: hits 4, ``COUNT=2`` pages 0/2/4 give
2+2+1 = 5 rows (page 2 starts with the last feature of page 0, the 4th
unique feature comes at ``STARTINDEX=4``); PRG A03 in N 220000-270000,
E 550000-590000: hits 39, ``COUNT=13`` repeats row 25 as row 26 and the
39th unique feature comes at ``STARTINDEX=39``. Hence: pages from 0 in steps
of ``page_size``; stop as soon as the unique ids reach N; past the N planned
positions continue only while the previous page was full and added new ids.
A short page with fewer than N unique ids, a page past N without new ids or
more than N unique ids is a ``DownloadError`` (an incomplete or changing
answer). Without duplicates exactly the N planned positions are requested.
A WFS layer with N = 0 next to non-empty ones still gets its (empty) page
``STARTINDEX=0``: GDAL builds the layer schema from the XSD and a document.
An empty ArcGIS layer needs no page (schema = layer JSON).

BBOX: WFS ``BBOX=<a>,<b>,<c>,<d>,urn:ogc:def:crs:EPSG::<code>`` in the
channel ``axis_order`` (``yx`` = northing first: EPSG:2180 per EPSG; ``xy``:
EPSG:5514 X,Y; a swapped order silently gives another area or nothing),
``SRSNAME`` = the same URN; ArcGIS envelopes are always x,y. Coordinates are
rounded OUTWARD to whole millimetres. An HTML answer, XML whose root is not
the expected document (``ows:ExceptionReport``) or JSON with ``error`` at
HTTP 200 is a ``DownloadError``; HTTP failures and retries come from
``transport.http.get_with_retry``. Every page is written to
``pages_dir/<layer.name>/<start>.gml|.json`` as it arrives (one page in
memory at a time).
"""

import json
import logging
import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from pathlib import Path

import requests

from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.sources.descriptor import FeatureBBoxParams, FeatureLayer
from kartograf.transport.http import get_with_retry

logger = logging.getLogger(__name__)

_WFS = "{http://www.opengis.net/wfs/2.0}"
_OWS = "{http://www.opengis.net/ows/1.1}"
_GML_ID_ATTRIBUTE = "{http://www.opengis.net/gml/3.2}id"
_XSD_SCHEMA = "{http://www.w3.org/2001/XMLSchema}schema"
_CAPABILITIES = f"{_WFS}WFS_Capabilities"
_COLLECTION = f"{_WFS}FeatureCollection"
_MEMBER = f"{_WFS}member"
_WFS_BASE = {"SERVICE": "WFS", "VERSION": "2.0.0"}
# GDAL exposes the gml:id attribute of a feature as the field "gml_id" (EGiB:
# "dzialki.<ID_DZIALKI>"); any other id field is a property element.
_GML_ID_FIELD = "gml_id"

_EPSG_FORMS = (
    re.compile(r"EPSG:(\d+)", re.IGNORECASE),
    re.compile(r"urn:ogc:def:crs:EPSG:[^:]*:(\d+)", re.IGNORECASE),
    re.compile(r"https?://www\.opengis\.net/def/crs/EPSG/[^/]+/(\d+)", re.IGNORECASE),
    re.compile(r"https?://www\.opengis\.net/gml/srs/epsg\.xml#(\d+)", re.IGNORECASE),
)
_DIGITS = re.compile(r"[0-9]+")

# One fetched page: its file, the number of rows and the ids of its features.
_Page = tuple[Path, int, list[Hashable]]


@dataclass(frozen=True)
class LayerPages:
    """Saved answer of one source layer.

    ``matched`` = N from ``RESULTTYPE=hits`` / ``returnCountOnly``;
    ``pages`` = page files in ``STARTINDEX``/``resultOffset`` order (GML or
    GeoJSON; ``()`` for an empty ArcGIS layer); ``schema`` = the saved service
    description of the layer: WFS ``DescribeFeatureType`` XSD, ArcGIS the
    layer JSON (``<layer>?f=json``; its ``geometryType`` types an empty
    layer); ``fields`` = ArcGIS ``(name, esriFieldType)`` of that JSON, ``()``
    for WFS.
    """

    layer: FeatureLayer
    matched: int
    pages: tuple[Path, ...]
    schema: Path | None
    fields: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class FeaturePages:
    """Pages of every requested layer, in the order of the ``layers`` argument."""

    layers: tuple[LayerPages, ...]


def count_features(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layer: FeatureLayer,
    bbox: BBox,
    *,
    timeout: float,
) -> int:
    """Number of features of ``layer`` intersecting ``bbox`` (``native_crs``).

    WFS ``RESULTTYPE=hits`` (``numberMatched``), ArcGIS ``returnCountOnly``.

    Raises
    ------
    DownloadError
        HTTP/network failure, an error document, ``numberMatched="unknown"``
        or no count in the answer.
    ValueError
        ``bbox`` not in ``params.native_crs`` or inconsistent channel
        parameters (programmer error).
    """
    code = _check_request(params, bbox)
    if params.protocol == "wfs":
        return _wfs_hits(session, endpoint, params, layer, bbox, code, timeout)
    return _arcgis_count(session, endpoint, layer, bbox, code, timeout)


def fetch_features(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layers: Sequence[FeatureLayer],
    bbox: BBox,
    pages_dir: Path,
    *,
    timeout: float,
) -> FeaturePages:
    """Fetch every feature of ``layers`` intersecting ``bbox`` into ``pages_dir``.

    Creates ``pages_dir/<layer.name>/`` with the pages and the schema; the
    caller owns (and removes) ``pages_dir``.

    Raises
    ------
    NoCoverageError
        Valid answers with N = 0 in every layer (no page is fetched).
    DownloadError
        A layer missing from the service, another DefaultCRS / layer CRS,
        a service page limit below ``page_size``, an error document, an
        unknown count, an incomplete or inconsistent page stream.
    ValueError
        No layers, repeated layer names, ``bbox`` not in ``native_crs`` or
        inconsistent channel parameters (programmer error).
    """
    code = _check_request(params, bbox)
    layers = tuple(layers)
    if not layers:
        raise ValueError("Brak warstw do pobrania")
    names = [layer.name for layer in layers]
    if len(set(names)) != len(names):
        raise ValueError(f"Powtorzone nazwy warstw: {names}")

    infos: list[bytes] = []
    if params.protocol == "wfs":
        _check_capabilities(session, endpoint, params, layers, code, timeout)
    else:
        infos = [
            _arcgis_layer(session, endpoint, params, layer, code, timeout)
            for layer in layers
        ]
    matched = [
        count_features(session, endpoint, params, layer, bbox, timeout=timeout)
        for layer in layers
    ]
    if not any(matched):
        raise NoCoverageError(
            f"{_service(params, endpoint)}: brak obiektow w obszarze "
            f"(warstwy: {', '.join(layer.source for layer in layers)})"
        )
    result = []
    for index, (layer, total) in enumerate(zip(layers, matched, strict=True)):
        layer_dir = Path(pages_dir) / layer.name
        layer_dir.mkdir(parents=True, exist_ok=True)
        context = f"{_service(params, endpoint)} ({layer.source})"
        if params.protocol == "wfs":
            pages = _wfs_layer(
                session, endpoint, params, layer, total, bbox, code, layer_dir, timeout
            )
        else:
            pages = _arcgis_layer_pages(
                session,
                endpoint,
                params,
                layer,
                total,
                infos[index],
                bbox,
                code,
                layer_dir,
                timeout,
            )
        logger.info("%s: %s obiektow, %s stron", context, total, len(pages.pages))
        result.append(pages)
    return FeaturePages(tuple(result))


def _wfs_layer(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layer: FeatureLayer,
    total: int,
    bbox: BBox,
    code: str,
    layer_dir: Path,
    timeout: float,
) -> LayerPages:
    """XSD and pages of one WFS layer (page 0 also when ``total`` is 0)."""
    schema = _wfs_schema(session, endpoint, layer, layer_dir, timeout)

    def fetch(start: int) -> _Page:
        return _wfs_page(
            session, endpoint, params, layer, bbox, code, start, layer_dir, timeout
        )

    context = f"WFS {endpoint} ({layer.source})"
    pages = _page_loop(fetch, total, params.page_size, context)
    return LayerPages(layer, total, pages, schema, ())


def _arcgis_layer_pages(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layer: FeatureLayer,
    total: int,
    info: bytes,
    bbox: BBox,
    code: str,
    layer_dir: Path,
    timeout: float,
) -> LayerPages:
    """Layer JSON and pages of one ArcGIS layer (no page when ``total`` is 0)."""
    schema = layer_dir / "layer.json"
    schema.write_bytes(info)
    fields = tuple(
        (field["name"], field["type"]) for field in json.loads(info)["fields"]
    )

    def fetch(start: int) -> _Page:
        return _arcgis_page(
            session, endpoint, params, layer, bbox, code, start, layer_dir, timeout
        )

    context = f"ArcGIS {_layer_url(endpoint, layer)}"
    pages = _page_loop(fetch, total, params.page_size, context) if total else ()
    return LayerPages(layer, total, pages, schema, fields)


def _page_loop(
    fetch: Callable[[int], _Page], total: int, page_size: int, context: str
) -> tuple[Path, ...]:
    """Pages from position 0 until the unique ids reach ``total`` (module doc)."""
    pages: list[Path] = []
    seen: set[Hashable] = set()
    start = 0
    while True:
        path, rows, ids = fetch(start)
        pages.append(path)
        before = len(seen)
        seen.update(ids)
        if len(seen) > total:
            raise DownloadError(
                f"{context}: strony daja {len(seen)} roznych obiektow, "
                f"a zapytanie o liczbe {total} (dane zmienily sie w trakcie)"
            )
        if len(seen) == total:
            return tuple(pages)
        start += page_size
        if rows < page_size or (start >= total and len(seen) == before):
            raise DownloadError(
                f"{context}: niepelna odpowiedz - {len(seen)} z {total} obiektow "
                f"(koniec stron na pozycji {start - page_size + rows})"
            )


def _check_request(params: FeatureBBoxParams, bbox: BBox) -> str:
    """Native EPSG code; programmer errors of the call are ``ValueError``."""
    code = _epsg_code(params.native_crs)
    if code is None:
        raise ValueError(f"Uklad natywny {params.native_crs!r} nie jest kodem EPSG")
    if _epsg_code(bbox.crs) != code:
        raise ValueError(
            f"bbox w ukladzie {bbox.crs!r}, oczekiwano {params.native_crs!r}"
        )
    if params.page_size <= 0:
        raise ValueError(f"page_size musi byc dodatnie: {params.page_size}")
    if params.protocol == "arcgis":
        if not params.order_field:
            raise ValueError("Kanal ArcGIS wymaga order_field (orderByFields)")
        if params.axis_order != "xy":
            raise ValueError("Obwiednia ArcGIS ma zawsze kolejnosc osi x,y")
    elif params.protocol != "wfs":
        raise ValueError(f"Nieznany protokol {params.protocol!r}")
    return code


def _epsg_code(crs: str) -> str | None:
    """EPSG code of a CRS label (``EPSG:2180``, ``urn:ogc:def:crs:EPSG::2180``,
    ``http://www.opengis.net/def/crs/EPSG/0/2180`` -> ``"2180"``); ``None``
    for any other label."""
    text = crs.strip()
    for form in _EPSG_FORMS:
        match = form.fullmatch(text)
        if match:
            return str(int(match.group(1)))
    return None


def _service(params: FeatureBBoxParams, endpoint: str) -> str:
    return f"{'WFS' if params.protocol == 'wfs' else 'ArcGIS'} {endpoint}"


def _mm(value: float, rounding: Callable[[float], int]) -> str:
    """Coordinate rounded to whole millimetres by ``math.floor``/``math.ceil``
    (outward rounding never shrinks the area; trailing zeros dropped)."""
    text = f"{rounding(round(value * 1000, 6)) / 1000:.3f}"
    return text.rstrip("0").rstrip(".")


def _bbox_numbers(bbox: BBox, axis_order: str) -> str:
    """The four BBOX numbers in the service axis order, widened to mm."""
    min_x, min_y = _mm(bbox.min_x, math.floor), _mm(bbox.min_y, math.floor)
    max_x, max_y = _mm(bbox.max_x, math.ceil), _mm(bbox.max_y, math.ceil)
    if axis_order == "yx":
        return f"{min_y},{min_x},{max_y},{max_x}"
    return f"{min_x},{min_y},{max_x},{max_y}"


# --- WFS --------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _content_type(response: requests.Response) -> str:
    return str(response.headers.get("Content-Type", ""))


def _xml_root(response: requests.Response, context: str) -> ET.Element:
    try:
        return ET.fromstring(response.content)
    except ET.ParseError as e:
        raise DownloadError(
            f"{context}: odpowiedz nie jest dokumentem XML "
            f"({_content_type(response)}): {e}"
        ) from e


def _service_error(root: ET.Element, context: str) -> DownloadError:
    """Error of an unexpected document (``ows:ExceptionReport``, XHTML page)."""
    text = " ".join(t.strip() for t in root.itertext() if t.strip())[:300]
    return DownloadError(f"{context}: blad uslugi ({_local(root.tag)}): {text}")


def _check_capabilities(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layers: tuple[FeatureLayer, ...],
    code: str,
    timeout: float,
) -> None:
    """Every layer is a FeatureType of the service with DefaultCRS ``code``
    and the service page limit (``CountDefault``) admits ``page_size``."""
    context = f"WFS {endpoint} (GetCapabilities)"
    response = get_with_retry(
        session,
        endpoint,
        timeout=timeout,
        description=context,
        params={**_WFS_BASE, "REQUEST": "GetCapabilities"},
    )
    root = _xml_root(response, context)
    if root.tag != _CAPABILITIES:
        raise _service_error(root, context)
    default_crs = {
        (feature_type.findtext(f"{_WFS}Name") or "").strip(): (
            feature_type.findtext(f"{_WFS}DefaultCRS") or ""
        ).strip()
        for feature_type in root.iter(f"{_WFS}FeatureType")
    }
    for layer in layers:
        if layer.source not in default_crs:
            raise DownloadError(
                f"{context}: usluga nie publikuje typu obiektow {layer.source}"
            )
        declared = default_crs[layer.source]
        if _epsg_code(declared) != code:
            raise DownloadError(
                f"{context}: uklad domyslny {layer.source} to {declared!r}, "
                f"oczekiwano {params.native_crs}"
            )
    limits = []
    for constraint in root.iter(f"{_OWS}Constraint"):
        value = (constraint.findtext(f"{_OWS}DefaultValue") or "").strip()
        if constraint.get("name") == "CountDefault" and _DIGITS.fullmatch(value):
            limits.append(int(value))
    if limits and params.page_size > min(limits):
        raise DownloadError(
            f"{context}: usluga zwraca najwyzej {min(limits)} obiektow na strone, "
            f"a kanal zada {params.page_size}"
        )


def _wfs_schema(
    session: requests.Session,
    endpoint: str,
    layer: FeatureLayer,
    layer_dir: Path,
    timeout: float,
) -> Path:
    """``DescribeFeatureType`` of the layer saved as ``schema.xsd``."""
    context = f"WFS {endpoint} (DescribeFeatureType {layer.source})"
    response = get_with_retry(
        session,
        endpoint,
        timeout=timeout,
        description=context,
        params={
            **_WFS_BASE,
            "REQUEST": "DescribeFeatureType",
            "TYPENAMES": layer.source,
        },
    )
    root = _xml_root(response, context)
    if root.tag != _XSD_SCHEMA:
        raise _service_error(root, context)
    target = layer_dir / "schema.xsd"
    target.write_bytes(response.content)
    return target


def _wfs_query(
    params: FeatureBBoxParams, layer: FeatureLayer, bbox: BBox, code: str
) -> dict[str, str]:
    urn = f"urn:ogc:def:crs:EPSG::{code}"
    return {
        **_WFS_BASE,
        "REQUEST": "GetFeature",
        "TYPENAMES": layer.source,
        "SRSNAME": urn,
        "BBOX": f"{_bbox_numbers(bbox, params.axis_order)},{urn}",
    }


def _wfs_hits(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layer: FeatureLayer,
    bbox: BBox,
    code: str,
    timeout: float,
) -> int:
    context = f"WFS {endpoint} ({layer.source}, RESULTTYPE=hits)"
    response = get_with_retry(
        session,
        endpoint,
        timeout=timeout,
        description=context,
        params={**_wfs_query(params, layer, bbox, code), "RESULTTYPE": "hits"},
    )
    root = _xml_root(response, context)
    if root.tag != _COLLECTION:
        raise _service_error(root, context)
    matched = root.get("numberMatched", "")
    if not _DIGITS.fullmatch(matched):
        raise DownloadError(
            f"{context}: usluga nie podala liczby obiektow (numberMatched={matched!r})"
        )
    return int(matched)


def _wfs_page(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layer: FeatureLayer,
    bbox: BBox,
    code: str,
    start: int,
    layer_dir: Path,
    timeout: float,
) -> _Page:
    context = f"WFS {endpoint} ({layer.source}, STARTINDEX={start})"
    response = get_with_retry(
        session,
        endpoint,
        timeout=timeout,
        description=context,
        params={
            **_wfs_query(params, layer, bbox, code),
            "COUNT": str(params.page_size),
            "STARTINDEX": str(start),
        },
    )
    target = layer_dir / f"{start}.gml"
    target.write_bytes(response.content)
    rows, ids = _scan_page(target, layer.id_field, context, _content_type(response))
    return target, rows, ids


def _scan_page(
    path: Path, id_field: str, context: str, content_type: str
) -> tuple[int, list[Hashable]]:
    """Rows and feature ids of a saved ``GetFeature`` page in one streaming pass.

    The root must be ``wfs:FeatureCollection`` whose ``numberReturned`` equals
    the number of ``wfs:member`` elements, each with one identified feature.
    """
    ids: list[Hashable] = []
    members = 0
    try:
        with open(path, "rb") as handle:
            events = ET.iterparse(handle, events=("start", "end"))
            _, root = next(events)
            if root.tag != _COLLECTION:
                raise _service_error(ET.parse(path).getroot(), context)
            depth = 1
            in_member = False
            for event, element in events:
                if event == "start":
                    depth += 1
                    if depth == 2:
                        in_member = element.tag == _MEMBER
                    continue
                if depth == 3 and in_member:
                    ids.append(_feature_id(element, id_field, context))
                elif depth == 2 and in_member:
                    members += 1
                    root.remove(element)  # bounded memory: drop parsed members
                depth -= 1
    except ET.ParseError as e:
        raise DownloadError(
            f"{context}: odpowiedz nie jest dokumentem XML ({content_type}): {e}"
        ) from e
    returned = root.get("numberReturned", "")
    if not _DIGITS.fullmatch(returned) or int(returned) != members:
        raise DownloadError(
            f"{context}: niepelna strona (numberReturned={returned!r}, "
            f"obiektow {members})"
        )
    if len(ids) != members:
        raise DownloadError(f"{context}: element wfs:member bez obiektu")
    return members, ids


def _feature_id(feature: ET.Element, id_field: str, context: str) -> str:
    if id_field == _GML_ID_FIELD:
        value = feature.get(_GML_ID_ATTRIBUTE)
    else:
        value = next(
            (child.text for child in feature if _local(child.tag) == id_field), None
        )
    value = (value or "").strip()
    if not value:
        raise DownloadError(
            f"{context}: obiekt {_local(feature.tag)} bez identyfikatora {id_field}"
        )
    return value


# --- ArcGIS REST ------------------------------------------------------------


def _layer_url(endpoint: str, layer: FeatureLayer) -> str:
    return f"{endpoint.rstrip('/')}/{layer.source}"


def _arcgis_json(response: requests.Response, context: str) -> dict:
    """JSON object of an ArcGIS answer; ``error`` (also at HTTP 200) or
    anything that is not a JSON object is a ``DownloadError``."""
    try:
        payload = json.loads(response.content)
    except (ValueError, UnicodeDecodeError) as e:
        raise DownloadError(
            f"{context}: odpowiedz nie jest JSON ({_content_type(response)}): {e}"
        ) from e
    if not isinstance(payload, dict):
        raise DownloadError(f"{context}: odpowiedz nie jest obiektem JSON")
    error = payload.get("error")
    if error is not None:
        message = error.get("message") if isinstance(error, dict) else error
        details = error.get("details") if isinstance(error, dict) else None
        raise DownloadError(f"{context}: blad uslugi ArcGIS: {message} {details or ''}")
    return payload


def _layer_wkid(info: dict) -> str | None:
    """EPSG code of the layer: ``extent`` first, else ``sourceSpatialReference``."""
    extent = info.get("extent")
    holders = (
        extent.get("spatialReference") if isinstance(extent, dict) else None,
        info.get("sourceSpatialReference"),
    )
    for holder in holders:
        if isinstance(holder, dict):
            for key in ("latestWkid", "wkid"):
                value = holder.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    return str(value)
    return None


def _arcgis_layer(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layer: FeatureLayer,
    code: str,
    timeout: float,
) -> bytes:
    """Layer JSON (``?f=json``) checked against the channel; its raw bytes."""
    url = _layer_url(endpoint, layer)
    context = f"ArcGIS {url}"
    response = get_with_retry(
        session, url, timeout=timeout, description=context, params={"f": "json"}
    )
    info = _arcgis_json(response, context)
    fields = info.get("fields")
    if not isinstance(fields, list) or not all(
        isinstance(field, dict)
        and isinstance(field.get("name"), str)
        and isinstance(field.get("type"), str)
        for field in fields
    ):
        raise DownloadError(f"{context}: opis warstwy bez listy pol (fields)")
    names = {field["name"] for field in fields}
    for required in (layer.id_field, params.order_field):
        if required not in names:
            raise DownloadError(f"{context}: warstwa nie ma pola {required}")
    wkid = _layer_wkid(info)
    if wkid != code:
        raise DownloadError(
            f"{context}: uklad warstwy EPSG:{wkid}, oczekiwano {params.native_crs}"
        )
    limit = info.get("maxRecordCount")
    if isinstance(limit, int) and params.page_size > limit:
        raise DownloadError(
            f"{context}: usluga zwraca najwyzej {limit} obiektow na strone, "
            f"a kanal zada {params.page_size}"
        )
    return response.content


def _arcgis_filter(bbox: BBox, code: str) -> dict[str, str]:
    return {
        "geometry": _bbox_numbers(bbox, "xy"),
        "geometryType": "esriGeometryEnvelope",
        "inSR": code,
        "spatialRel": "esriSpatialRelIntersects",
    }


def _arcgis_count(
    session: requests.Session,
    endpoint: str,
    layer: FeatureLayer,
    bbox: BBox,
    code: str,
    timeout: float,
) -> int:
    url = f"{_layer_url(endpoint, layer)}/query"
    context = f"ArcGIS {url} (returnCountOnly)"
    response = get_with_retry(
        session,
        url,
        timeout=timeout,
        description=context,
        params={**_arcgis_filter(bbox, code), "returnCountOnly": "true", "f": "json"},
    )
    count = _arcgis_json(response, context).get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise DownloadError(f"{context}: usluga nie podala liczby obiektow ({count!r})")
    return count


def _arcgis_page(
    session: requests.Session,
    endpoint: str,
    params: FeatureBBoxParams,
    layer: FeatureLayer,
    bbox: BBox,
    code: str,
    start: int,
    layer_dir: Path,
    timeout: float,
) -> _Page:
    url = f"{_layer_url(endpoint, layer)}/query"
    context = f"ArcGIS {url} (resultOffset={start})"
    response = get_with_retry(
        session,
        url,
        timeout=timeout,
        description=context,
        params={
            **_arcgis_filter(bbox, code),
            "outSR": code,
            "outFields": "*",
            "orderByFields": str(params.order_field),
            "resultOffset": str(start),
            "resultRecordCount": str(params.page_size),
            "returnGeometry": "true",
            "f": "geojson",
        },
    )
    target = layer_dir / f"{start}.json"
    target.write_bytes(response.content)
    payload = _arcgis_json(response, context)
    features = payload.get("features")
    if payload.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise DownloadError(f"{context}: odpowiedz nie jest kolekcja GeoJSON")
    ids: list[Hashable] = []
    for feature in features:
        properties = feature.get("properties") if isinstance(feature, dict) else None
        value = properties.get(layer.id_field) if isinstance(properties, dict) else None
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            raise DownloadError(
                f"{context}: obiekt bez identyfikatora {layer.id_field} ({value!r})"
            )
        ids.append(value)
    return target, len(features), ids
