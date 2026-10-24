"""
Pytest configuration and shared fixtures.

This module contains pytest fixtures and configuration that are shared
across all test modules.
"""

import functools
import gzip
import ipaddress
import json
import os
import socket
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse
from xml.sax.saxutils import escape

import pytest

# =============================================================================
# Network isolation
# =============================================================================


def _is_local_address(address: object) -> bool:
    """
    Tell whether a socket address points at the local machine.

    Non-tuple addresses (AF_UNIX paths, bytes) never leave the machine,
    so they are treated as local.

    Parameters
    ----------
    address : object
        Address passed to ``socket.socket.connect``.

    Returns
    -------
    bool
        True if the address is loopback/unspecified or a non-IP socket.
    """
    if not isinstance(address, tuple) or not address:
        return True

    host = address[0]
    if isinstance(host, bytes | bytearray):
        host = bytes(host).decode("ascii", errors="ignore")
    if not isinstance(host, str):
        return False
    if host in ("localhost", "localhost.localdomain", ""):
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip.is_unspecified


@pytest.fixture(autouse=True)
def _block_network(request, monkeypatch):
    """
    Fail any test that opens a non-loopback socket.

    Unit tests must run offline: a test that reaches a production server
    (GUGiK, CUZK, ISRIC, ...) is slow, flaky and its result depends on the
    state of that server. Tests marked ``live`` are exempt.

    Loopback connections are allowed on purpose — some tests spin up a real
    ``HTTPServer`` on 127.0.0.1 (see ``tests/unit/test_auth_proxy.py``).

    The guard raises ``RuntimeError``, not ``OSError``: ``requests`` wraps
    ``OSError`` into ``ConnectionError``, which production fallbacks catch,
    so the offending call would stay invisible.
    """
    if request.node.get_closest_marker("live"):
        yield
        return

    real_connect = socket.socket.connect
    nodeid = request.node.nodeid

    def guarded_connect(self, address):
        if _is_local_address(address):
            return real_connect(self, address)
        raise RuntimeError(
            f"Network access blocked in unit tests ({nodeid}): connect to {address!r}"
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield


@pytest.fixture(autouse=True)
def user_environment(monkeypatch, tmp_path_factory):
    """Keep the user environment of the machine out of every test (DEV-18).

    No ``KARTOGRAF_*`` or ``NOGAT_*`` variable of the machine applies, and the user
    directories (``nogat.toml``, data, cache) point into a per-test directory: the
    default metadata cache (``cache=True``) and the settings file never touch the
    real ones. A test that wants a setting sets the variable or writes the file; the
    fixture gives the directory of the three (``config``, ``data``, ``cache``).
    """
    import platformdirs

    for name in list(os.environ):
        if name.startswith(("KARTOGRAF_", "NOGAT_")):
            monkeypatch.delenv(name)
    home = tmp_path_factory.mktemp("user")
    monkeypatch.setattr(
        platformdirs, "user_config_path", lambda *a, **k: home / "config"
    )
    monkeypatch.setattr(platformdirs, "user_data_path", lambda *a, **k: home / "data")
    monkeypatch.setattr(platformdirs, "user_cache_path", lambda *a, **k: home / "cache")
    yield home


@pytest.fixture(autouse=True)
def _offline_package_sizes(monkeypatch):
    """No network for the volume check of a BDOT10k area.

    ``LandCoverManager`` asks the size of every powiat package by ``HEAD``
    (``within_volume``): a test that does not fake the answer gets "size not
    known" instead of a connection. Tests of the limit itself fake
    ``collections._head_length``.
    """
    from kartograf.landcover import manager

    real = manager.within_volume

    class NoSizeSession:
        def head(self, url, **kwargs):
            return _body_response(b"", "application/octet-stream")

    def within_volume(*args, **kwargs):
        return real(*args, **{**kwargs, "sessions": NoSizeSession})

    monkeypatch.setattr(manager, "within_volume", within_volume)
    yield


# =============================================================================
# Offline WMS GetCapabilities (orthophoto index)
# =============================================================================


@pytest.fixture(autouse=True)
def _offline_wms_layers(request):
    """Orthophoto index layers without network (GetCapabilities stub).

    Layer discovery tests use the ``real_wms_layers`` marker. NMT/NMPT read
    the WFS index (``_offline_wfs_types``).
    """
    if request.node.get_closest_marker("real_wms_layers"):
        yield
        return

    from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

    with patch.object(
        GugikOrtoProvider,
        "_fetch_wms_layers",
        return_value=[
            "SkorowidzeOrtofotomapy2026",
            "SkorowidzeOrtofotomapy2025",
            "SkorowidzeOrtofotomapy2024",
            "SkorowidzeOrtofotomapyStarsze",
        ],
    ):
        yield


# =============================================================================
# Offline WFS sheet index (NMT/NMPT/LAZ, ADR-041)
# =============================================================================

WFS_FIXTURES = Path(__file__).parent / "fixtures" / "gugik_wfs" / "real_2026_10_15"

_PZGIK = "https://mapy.geoportal.gov.pl/wss/service/PZGIK"
_WFS_SERVICES = {
    "nmt": ("NumerycznyModelTerenu", "SkorowidzNMT"),
    "nmpt": ("NumerycznyModelPokryciaTerenu", "SkorowidzNMPT"),
    "laz": ("DanePomiaroweLidar", "SkorowidzDanychPomiarowychLIDAR"),
}
# Services whose feature types the autouse stub serves (LAZ tests answer
# GetCapabilities in their own sessions)
_STUBBED_WFS = ("nmt_evrf2007", "nmt_kron86", "nmpt_evrf2007", "nmpt_kron86")
_GUGIK_NS = "http://www.gugik.gov.pl"
_GML_NS = "http://www.opengis.net/gml/3.2"
_WFS_NS = "http://www.opengis.net/wfs/2.0"
_URN_2180 = "urn:ogc:def:crs:EPSG::2180"


def wfs_endpoint(tag: str) -> str:
    """WFS index endpoint of a fixture tag (``"nmt_evrf2007"``, ``"laz_kron86"``)."""
    product, vertical_crs = tag.split("_")
    return f"{_PZGIK}/{_WFS_SERVICES[product][0]}{vertical_crs.upper()}/WFS/Skorowidze"


def wfs_fixture(name: str) -> str:
    """Text of a recorded WFS answer in ``WFS_FIXTURES`` (``.gz`` decompressed)."""
    path = WFS_FIXTURES / name
    data = path.read_bytes()
    if path.suffix == ".gz":
        data = gzip.decompress(data)
    return data.decode("utf-8")


@functools.cache
def wfs_types(tag: str) -> tuple[str, ...]:
    """Yearly feature types (newest first) of the recorded GetCapabilities."""
    from kartograf.providers.pl.skorowidz_wfs import parse_feature_types

    root = ET.fromstring(wfs_fixture(f"caps_{tag}.xml"))
    return tuple(parse_feature_types(root, _WFS_SERVICES[tag.split("_")[0]][1]))


@pytest.fixture(autouse=True)
def _offline_wfs_types(request):
    """Feature types of the NMT/NMPT index services without network.

    The types of the recorded GetCapabilities of 2026-10-15 (``caps_*.xml``,
    e.g. NMT EVRF2007 2026..2018); LAZ services are not stubbed. Tests of the
    type discovery itself use the ``real_wfs_types`` marker.
    """
    if request.node.get_closest_marker("real_wfs_types"):
        yield
        return

    from kartograf.providers.pl.skorowidz_wfs import WfsIndex

    stubbed = {wfs_endpoint(tag): tag for tag in _STUBBED_WFS}
    original = WfsIndex._fetch_types

    def fetch_types(index) -> list[str]:
        tag = stubbed.get(index.endpoint)
        return list(wfs_types(tag)) if tag is not None else original(index)

    with patch.object(WfsIndex, "_fetch_types", fetch_types):
        yield


def wfs_record(
    sheet: str,
    *,
    resolution: str | None = "1.00 m",
    system: str = "PL-1992",
    akt_data: str = "2024-09-03",
    url: str | None = None,
    layer: str | None = None,
    product: str = "NMT",
    footprint: list[tuple[float, float]] | None = None,
    **fields: str | None,
) -> dict:
    """NMT/NMPT WFS index record with the fields of the GUGiK answers (2026-10-15).

    ``layer``: feature type (default ``Skorowidz<product><year of akt_data>``);
    ``footprint``: (E, N) frame in EPSG:2180 (default: the envelope of the
    sheet frame); ``fields`` add or override ``gugik:`` fields (``format``,
    ``czy_ark_wypelniony``, ``nr_zglosz``, ``dt_pzgik``, ``uklad_h``...),
    ``None`` drops a field.
    """
    record: dict = {
        "layer": layer or f"Skorowidz{product}{akt_data[:4]}",
        "footprint": footprint,
        "godlo": sheet,
        "akt_rok": akt_data[:4],
        "asortyment": product,
        "format": "ARC/INFO ASCII GRID",
        "char_przestrz": resolution,
        "uklad_xy": system,
        "uklad_h": "PL-EVRF2007-NH",
        "akt_data": akt_data,
        "czy_ark_wypelniony": "TAK",
        "url_do_pobrania": url
        or f"https://opendata.geoportal.gov.pl/NumDaneWys/{product}/78955/"
        f"78955_1_{sheet}.asc",
        "dt_pzgik": akt_data,
    }
    record.update(fields)
    return record


def _sheet_ring(sheet: object) -> list[tuple[float, float]] | None:
    """Envelope of a sheet frame in EPSG:2180 as an (E, N) ring; ``None`` for
    a code outside ``SheetParser``."""
    from kartograf.core.sheet_parser import SheetParser

    try:
        b = SheetParser(str(sheet)).get_bbox(crs="EPSG:2180")
    except Exception:
        return None
    return [
        (b.min_x, b.min_y),
        (b.max_x, b.min_y),
        (b.max_x, b.max_y),
        (b.min_x, b.max_y),
    ]


def _wfs_feature_xml(record: dict, number: int) -> str:
    layer = record["layer"]
    fid = f"{layer}.{number}"
    parts = [f'<wfs:member><gugik:{layer} gml:id="{fid}">']
    ring = record.get("footprint") or _sheet_ring(record.get("godlo"))
    if ring:
        xs = [x for x, _ in ring]
        ys = [y for _, y in ring]
        pos = " ".join(f"{y:.2f} {x:.2f}" for x, y in [*ring, ring[0]])
        parts.append(
            f'<gml:boundedBy><gml:Envelope srsName="{_URN_2180}">'
            f"<gml:lowerCorner>{min(ys):.2f} {min(xs):.2f}</gml:lowerCorner>"
            f"<gml:upperCorner>{max(ys):.2f} {max(xs):.2f}</gml:upperCorner>"
            "</gml:Envelope></gml:boundedBy>"
            f'<gugik:msGeometry><gml:Polygon gml:id="{fid}.1" srsName="{_URN_2180}">'
            "<gml:exterior><gml:LinearRing>"
            f'<gml:posList srsDimension="2">{pos}</gml:posList>'
            "</gml:LinearRing></gml:exterior></gml:Polygon></gugik:msGeometry>"
        )
    for key, value in record.items():
        if key in ("layer", "footprint") or value is None:
            continue
        text = escape(str(value))
        if key in ("akt_data", "dt_pzgik"):
            parts.append(
                f'<gugik:{key} gml:id="{fid}.{key}"><gml:timePosition>{text}'
                f"</gml:timePosition></gugik:{key}>"
            )
        else:
            parts.append(f"<gugik:{key}>{text}</gugik:{key}>")
    parts.append(f"</gugik:{layer}></wfs:member>")
    return "".join(parts)


def render_wfs_body(records: list[dict], *, next_url: str | None = None) -> str:
    """GML answer of a GUGiK WFS GetFeature (``wfs_record`` dicts).

    Like the server: one nested collection per feature type, the outer
    ``numberReturned`` = every feature; an empty answer has
    ``numberMatched="unknown"``; ``next_url`` sets the ``next`` attribute.
    """
    by_type: dict[str, list[dict]] = {}
    for record in records:
        by_type.setdefault(record["layer"], []).append(record)
    members = []
    number = 0
    for group in by_type.values():
        features = []
        for record in group:
            number += 1
            features.append(_wfs_feature_xml(record, number))
        members.append(
            f'<wfs:member><wfs:FeatureCollection numberMatched="{len(group)}" '
            f'numberReturned="{len(group)}">{"".join(features)}'
            "</wfs:FeatureCollection></wfs:member>"
        )
    matched = str(len(records)) if records else "unknown"
    following = f' next="{escape(next_url, {chr(34): "&quot;"})}"' if next_url else ""
    return (
        "<?xml version='1.0' encoding=\"UTF-8\" ?>\n"
        f'<wfs:FeatureCollection xmlns:gugik="{_GUGIK_NS}" xmlns:gml="{_GML_NS}" '
        f'xmlns:wfs="{_WFS_NS}" numberMatched="{matched}" '
        f'numberReturned="{len(records)}"{following}>{"".join(members)}'
        "</wfs:FeatureCollection>"
    )


def wfs_response(body: str, status: int = 200):
    """Fake HTTP answer of a WFS request (GetFeature/GetCapabilities)."""
    from unittest.mock import Mock

    import requests

    response = Mock(spec=requests.Response)
    response.status_code = status
    response.text = body
    response.content = body.encode("utf-8")
    response.headers = {"Content-Type": 'text/xml; subtype="gml/3.2.1"; charset=UTF-8'}
    response.raise_for_status = Mock()
    if status >= 400:
        error = requests.HTTPError(f"{status} Error", response=response)
        response.raise_for_status.side_effect = error
    return response


def wfs_requests(session, endpoint: str | None = None) -> list[dict[str, str]]:
    """Parameters of the WFS GetFeature calls on a ``Mock`` session (only those
    sent to ``endpoint`` when given), in call order."""
    found = []
    for call in session.get.call_args_list:
        url = call.args[0]
        if endpoint is not None and not url.startswith(f"{endpoint}?"):
            continue
        params = {
            key: values[0] for key, values in parse_qs(urlparse(url).query).items()
        }
        if params.get("REQUEST") == "GetFeature":
            found.append(params)
    return found


_PRG_FIXTURES = (
    Path(__file__).parent / "fixtures" / "gugik_prg" / "land_mask_2026_10_11"
)
_PRG_ENDPOINT = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"
)


def _recorded_features(text: str) -> list[tuple[str, tuple[float, ...], ET.Element]]:
    """``(type, (min E, min N, max E, max N), feature)`` of a recorded answer."""
    found: list[tuple[str, tuple[float, ...], ET.Element]] = []
    for elem in ET.fromstring(text).iter():
        tag = elem.tag if isinstance(elem.tag, str) else ""
        if not tag.startswith(f"{{{_GUGIK_NS}}}Skorowidz"):
            continue
        envelope = elem.find(f"{{{_GML_NS}}}boundedBy/{{{_GML_NS}}}Envelope")
        assert envelope is not None, tag
        lower = envelope.findtext(f"{{{_GML_NS}}}lowerCorner", "").split()
        upper = envelope.findtext(f"{{{_GML_NS}}}upperCorner", "").split()
        # URN EPSG::2180 corners are (N, E)
        box = (float(lower[1]), float(lower[0]), float(upper[1]), float(upper[0]))
        found.append((tag.rsplit("}", 1)[-1], box, elem))
    return found


class RecordedIndex:
    """``requests.Session`` stand-in for the GUGiK WFS indexes and the PRG land
    mask, answering from recorded answers; a data file is never served.

    ``areas`` maps a fixture tag (``"nmt_evrf2007"``) to recorded GetFeature
    answers (``area_<tag>_krakow.xml.gz``...); a GetFeature gets the recorded
    features of its TYPENAMES whose envelope intersects its BBOX, re-rendered
    as one page (a sheet query is a slice of the recorded area). A service
    without areas answers an empty collection. GetCapabilities:
    ``caps_<tag>.xml``. PRG: A00 (the whole country) and the W02/W03 answers
    of the coast (``coast=True``) or of an inland area. ``fail`` maps a URL
    prefix to a response (``wfs_response``) or an exception raised for it.
    ``urls``: every URL asked, in order; any other URL is an AssertionError.
    """

    def __init__(
        self,
        areas: dict[str, list[str]] | None = None,
        *,
        coast: bool = False,
        fail: dict | None = None,
    ) -> None:
        ET.register_namespace("gugik", _GUGIK_NS)
        ET.register_namespace("gml", _GML_NS)
        ET.register_namespace("wfs", _WFS_NS)
        self._features = {
            wfs_endpoint(tag): [
                feature
                for name in names
                for feature in _recorded_features(wfs_fixture(name))
            ]
            for tag, names in (areas or {}).items()
        }
        self._coast = coast
        self._fail = fail or {}
        self.urls: list[str] = []

    def get(self, url: str, timeout=None, params=None, **kwargs):
        if params:
            url = f"{url}?{urlencode(params)}"
        self.urls.append(url)
        for prefix, outcome in self._fail.items():
            if url.startswith(prefix):
                if isinstance(outcome, BaseException):
                    raise outcome
                return outcome
        if url.startswith(f"{_PRG_ENDPOINT}?"):
            return self._prg(url)
        endpoint, _, query = url.partition("?")
        tag = next(
            (
                tag
                for tag in ("nmt", "nmpt", "laz")
                for vcrs in ("evrf2007", "kron86")
                if endpoint == wfs_endpoint(f"{tag}_{vcrs}")
            ),
            None,
        )
        if tag is None:
            raise AssertionError(f"RecordedIndex: unexpected request {url}")
        params_of = {k: v[0] for k, v in parse_qs(query).items()}
        if params_of.get("REQUEST") == "GetCapabilities":
            vcrs = endpoint.split("/")[-3].removeprefix(_WFS_SERVICES[tag][0]).lower()
            return wfs_response(wfs_fixture(f"caps_{tag}_{vcrs}.xml"))
        assert params_of.get("REQUEST") == "GetFeature", url
        return wfs_response(self._get_feature(endpoint, params_of))

    def _get_feature(self, endpoint: str, params: dict[str, str]) -> str:
        types = {name.split(":")[-1] for name in params["TYPENAMES"].split(",")}
        min_n, min_e, max_n, max_e = (float(v) for v in params["BBOX"].split(",")[:4])
        chosen: dict[str, list[ET.Element]] = {}
        for layer, (x0, y0, x1, y1), feature in self._features.get(endpoint, []):
            if (
                layer in types
                and x0 <= max_e
                and x1 >= min_e
                and y0 <= max_n
                and y1 >= min_n
            ):
                chosen.setdefault(layer, []).append(feature)
        total = sum(len(group) for group in chosen.values())
        members = "".join(
            f'<wfs:member><wfs:FeatureCollection numberMatched="{len(group)}" '
            f'numberReturned="{len(group)}">'
            + "".join(
                f"<wfs:member>{ET.tostring(f, encoding='unicode')}</wfs:member>"
                for f in group
            )
            + "</wfs:FeatureCollection></wfs:member>"
            for group in chosen.values()
        )
        return (
            "<?xml version='1.0' encoding=\"UTF-8\" ?>\n"
            f'<wfs:FeatureCollection xmlns:gugik="{_GUGIK_NS}" xmlns:gml="{_GML_NS}" '
            f'xmlns:wfs="{_WFS_NS}" numberMatched="{total if total else "unknown"}" '
            f'numberReturned="{total}">{members}</wfs:FeatureCollection>'
        )

    def _prg(self, url: str):
        from unittest.mock import Mock

        layer = parse_qs(urlparse(url).query)["TYPENAMES"][0]
        if layer == "ms:A00_Granice_panstwa":
            body = gzip.decompress(
                (_PRG_FIXTURES / "A00_Granice_panstwa.xml.gz").read_bytes()
            )
        else:
            where = "coast" if self._coast else "inland"
            body = (_PRG_FIXTURES / f"{layer[3:]}_bbox_{where}.xml").read_bytes()
        response = Mock()
        response.status_code = 200
        response.content = body
        response.text = body.decode("utf-8")
        response.raise_for_status = Mock()
        return response


# =============================================================================
# Shared data fixtures
# =============================================================================


def render_gfi_body(records: list[dict], var: str = "skor_NMT_wg_akt") -> str:
    """Render a MapServer template like GUGiK: an empty response has only the header
    with ``createTable`` (gfi/01), the array declaration appears with records."""
    header = "<script>function createTable (rows) { return rows; }</script>\n"
    if not records:
        return header
    pushes = [
        f"{var}.push({{"
        + ",".join(
            f"{key}:{json.dumps(value, ensure_ascii=False)}"
            for key, value in record.items()
        )
        + "});"
        for record in records
    ]
    return header + f"<script>var {var} = [];\n" + "\n".join(pushes) + "</script>"


def gfi_record(
    sheet: str,
    *,
    resolution: str = "1.00 m",
    system: str = "PL-1992",
    aktualnosc: str = "2024-09-03",
    url: str | None = None,
    **fields: str,
) -> dict:
    """NMT/NMPT index record with fields as in the GUGiK response (2026-09-29)."""
    record = {
        "url": url
        or f"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/78955/78955_1_{sheet}.asc",
        "godlo": sheet,
        "aktualnosc": aktualnosc,
        "format": "ARC/INFO ASCII GRID",
        "charakterystykaPrzestrzenna": resolution,
        "ukladWspolrzednychPoziomych": system,
        "ukladWspolrzednychPionowych": "PL-EVRF2007-NH",
        "calyArkuszWypelnionyTrescia": "TAK",
        "aktualnoscRok": aktualnosc[:4],
        "dt_pzgik": aktualnosc,
    }
    record.update(fields)
    return record


def write_gpkg_layers(path: Path, layers: list[str]) -> Path:
    """GeoPackage catalogue with the given feature tables and no features.

    Enough for ``core.geometry.resolve_layer`` (the CLI resolves the layer before
    the readers) in CLI tests that mock the geometry readers themselves.
    """
    import sqlite3

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT)")
        conn.executemany(
            "INSERT INTO gpkg_contents VALUES (?, 'features')",
            [(name,) for name in layers],
        )
        conn.commit()
    finally:
        conn.close()
    return path


WCS_FIXTURES = Path(__file__).parent / "fixtures" / "gugik_wcs" / "real_2026_10_11"


def recorded_response(path: Path, body: bytes | None = None):
    """Mock ``requests.Response`` replaying a recorded body and its headers.

    ``<file>.headers.json`` next to the body holds the HTTP status,
    ``Content-Type`` and - when recorded - ``ETag``/``Last-Modified``
    (fixture README); ``body`` overrides the recorded bytes.
    ``iter_content`` yields small blocks, so streaming readers see several.
    """
    from unittest.mock import Mock

    import requests

    meta = json.loads(path.with_name(f"{path.name}.headers.json").read_text())
    content = path.read_bytes() if body is None else body
    response = Mock()
    response.status_code = meta["status"]
    response.headers = {key: value for key, value in meta.items() if key != "status"}
    response.content = content
    response.text = content.decode("utf-8", errors="replace")
    response.iter_content = lambda chunk_size=1: (
        content[i : i + 1000] for i in range(0, len(content), 1000)
    )
    if meta["status"] >= 400:
        error = requests.HTTPError(f"{meta['status']} Error", response=response)
        response.raise_for_status.side_effect = error
    return response


# Required data choices of the GUGiK providers (0.8.0: no defaults) for tests
# parametrized over provider classes.
_PROVIDER_CHOICES = {
    "GugikProvider": {"vertical_crs": "EVRF2007", "resolution": "1m"},
    "GugikNmptProvider": {"vertical_crs": "EVRF2007", "resolution": "1m"},
    "GugikOrtoProvider": {"color": "RGB"},
    "GugikLazProvider": {"vertical_crs": "EVRF2007"},
}


def make_provider(cls, **kwargs):
    """Instantiate ``cls`` with its required data choices (EVRF2007, 1m, RGB)."""
    return cls(**{**_PROVIDER_CHOICES.get(cls.__name__, {}), **kwargs})


def multipart_asc_body(values, xll: float, yll: float, cellsize: float = 1.0) -> bytes:
    """A GUGiK-shaped ``multipart/related; boundary=wcs`` body with one ASC grid.

    Same framing as the recorded responses (fixture README): CRLF part headers,
    LF ASC lines, an ``.prj`` part after the grid.
    """
    rows, cols = values.shape
    header = (
        f"ncols        {cols}\nnrows        {rows}\n"
        f"xllcorner    {xll:.12f}\nyllcorner    {yll:.12f}\n"
        f"cellsize     {cellsize:.12f}\n"
    )
    grid = "\n".join(" " + " ".join(repr(float(v)) for v in row) for row in values)
    part = b"\r\n--wcs\r\nContent-Type: %s\r\nContent-ID: coverage/%s\r\n\r\n"
    return (
        part % (b"image/x-aaigrid", b"result.asc")
        + (header + grid + "\n").encode()
        + part % (b"application/octet-stream", b"result.prj")
        + b'PROJCS["ETRS89_Poland_CS92"]'
        + b"\r\n--wcs--\r\n"
    )


SIGNAL_FIXTURES = Path(__file__).parent / "fixtures" / "signals" / "real_2026_10_12"


def tiny_geotiff(nodata: float | None, value: int) -> bytes:
    """A 2x2 Int16 GeoTIFF (EPSG:4326) with the given nodata and fill value."""
    import numpy as np
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            width=2,
            height=2,
            count=1,
            dtype="int16",
            crs="EPSG:4326",
            transform=from_origin(19.0, 50.0, 0.01, 0.01),
            nodata=nodata,
        ) as ds:
            ds.write(np.full((1, 2, 2), value, dtype="int16"))
        return bytes(mem.read())


def _body_response(body: bytes, content_type: str, status: int = 200):
    from unittest.mock import Mock

    import requests

    response = Mock()
    response.status_code = status
    response.headers = {"Content-Type": content_type}
    response.content = body
    response.iter_content = lambda chunk_size=1: iter([body])
    if status >= 400:
        error = requests.HTTPError(f"{status} Error", response=response)
        response.raise_for_status.side_effect = error
    return response


class FakeSoilGrids:
    """``requests.Session`` stand-in for SoilGrids: GetCapabilities + GetCoverage.

    ``edition``: the edition announced by GetCapabilities (recorded 2.0
    response with the title rewritten), or an HTTP status (int) for a failed
    request. ``values``: pixel value per property of the served GeoTIFF.
    Counts ``capabilities`` and ``coverages`` requests.
    """

    CAPABILITIES = (
        SIGNAL_FIXTURES / "isric_soilgrids_capabilities_get.xml"
    ).read_bytes()

    def __init__(self, edition: str | int = "2.0", values: dict | None = None):
        self.edition = edition
        self.values = dict(values or {})
        self.capabilities = 0
        self.coverages = 0

    def get(self, url, **kwargs):
        import re

        prop = re.search(r"map=/map/(\w+)\.map", url).group(1)  # type: ignore[union-attr]
        if "GetCapabilities" in url:
            self.capabilities += 1
            if isinstance(self.edition, int):
                return _body_response(b"", "text/html", self.edition)
            body = self.CAPABILITIES.replace(
                b"SoilGrids250m 2.0 - ", f"SoilGrids250m {self.edition} - ".encode()
            )
            return _body_response(body, "text/xml")
        self.coverages += 1
        return _body_response(
            tiny_geotiff(-32768, self.values.get(prop, 1)), "image/tiff"
        )


class FakeCorine:
    """``requests.Session`` stand-in for CORINE: CLMS catalogue + WMS preview.

    ``edition``: ``characteristics_release_major_version`` of the catalogue
    record (recorded 2018 answer), or an HTTP status (int). Counts
    ``catalogue`` and ``previews`` requests.
    """

    CATALOGUE = json.loads(
        (SIGNAL_FIXTURES / "clms_corine_2018_search.json").read_text()
    )

    def __init__(
        self, edition: str | int = "V2020_20u1", preview: bytes = b"\x89PNG x"
    ):
        self.edition = edition
        self.preview = preview
        self.catalogue = 0
        self.previews = 0

    def get(self, url, **kwargs):
        if "GetCapabilities" in url:  # the WMS layers of the year (EEA service)
            year = url.split("/CLC")[1][:4]
            return _body_response(
                (
                    '<WMS_Capabilities xmlns="http://www.opengis.net/wms"><Capability>'
                    f"<Layer><Layer><Name>12</Name><Title>Corine Land Cover {year} "
                    "raster</Title></Layer></Layer></Capability></WMS_Capabilities>"
                ).encode(),
                "text/xml",
            )
        if "@search" in url:
            self.catalogue += 1
            if isinstance(self.edition, int):
                return _body_response(b"", "text/html", self.edition)
            record = {
                **self.CATALOGUE["items"][0],
                "characteristics_release_major_version": self.edition,
            }
            response = _body_response(b"", "application/json")
            response.json.return_value = {"items": [record], "items_total": 1}
            return response
        self.previews += 1
        return _body_response(self.preview, "image/png")


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Freeze result timestamps while leaving TTL and cleanup clocks real."""
    instant = datetime(2026, 10, 12, 8, 30, 45, 123456, tzinfo=UTC)
    monkeypatch.setattr("kartograf._clock.now", lambda: instant)
    return instant


@pytest.fixture
def sample_sheets() -> dict:
    """
    Provide sample sheet identifiers for each scale.

    Returns
    -------
    dict
        Dictionary mapping scale names to sample sheet identifiers
    """
    return {
        "1:1000000": "N-34",
        "1:500000": "N-34-A",
        "1:200000": "N-34-130",
        "1:100000": "N-34-130-D",
        "1:50000": "N-34-130-D-d",
        "1:25000": "N-34-130-D-d-2",
        "1:10000": "N-34-130-D-d-2-4",
    }


@pytest.fixture
def test_data_dir(tmp_path) -> Path:
    """
    Create a temporary test data directory.

    Returns
    -------
    Path
        Path to the temporary test data directory
    """
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_tif_data() -> bytes:
    """
    Provide mock TIFF data for testing downloads.

    Returns
    -------
    bytes
        Mock TIFF file content (minimal valid header)
    """
    # Minimal TIFF header (little-endian, 42 magic number)
    return b"II*\x00\x08\x00\x00\x00" + b"\x00" * 100
