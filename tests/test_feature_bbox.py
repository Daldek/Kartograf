"""Engine ``feature_bbox`` (ADR-042 D3/D4) on real WFS, ArcGIS REST and OGC
API Features answers.

Every response comes from ``tests/fixtures/pl/feature_bbox`` (recorded live
2026-10-15, OGC API PRNG 2026-10-16; queries, dates and live facts in its
README). The PL channels are the registry entries (``pl.gugik.prg``,
``pl.gugik.egib``) with ``page_size=2`` - the ``COUNT`` of the recorded
pages; the CZ channels (RUIAN REST, HY-NET WFS) and the PRNG OGC API channel
(``page_size=5`` = the recorded ``limit``) are built here, plans D and E add
their descriptors.
"""

import dataclasses
import gzip
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import pyogrio
import pyogrio.raw
import pytest
from pyproj import CRS

from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.sources.descriptor import FeatureBBoxParams, FeatureLayer
from kartograf.sources.registry import get_source
from kartograf.transform.gpkg import write_gpkg
from kartograf.transport.feature_bbox import count_features, fetch_features
from tests.conftest import recorded_response

FIXTURES = Path(__file__).parent / "fixtures" / "pl" / "feature_bbox"


def answer(name: str, *, status: int | None = None, body: bytes | None = None):
    """Recorded response of a fixture (``*.gz`` = the recorded body gzipped);
    ``status`` replays the same body with another HTTP status."""
    path = FIXTURES / name
    if path.suffix == ".gz":
        path, body = path.with_suffix(""), gzip.decompress(path.read_bytes())
    response = recorded_response(path, body=body)
    if status is not None:
        response.status_code = status
        response.raise_for_status.side_effect = None
    return response


class FakeService:
    """``requests.Session`` stand-in: ``route(url, params)`` gives a fixture
    name or a response; ``calls`` records every request."""

    def __init__(self, route: Callable[[str, dict], Any]) -> None:
        self.route = route
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, timeout=None, **kwargs):
        params = dict(params or {})
        self.calls.append((url, params))
        reply = self.route(url, params)
        return answer(reply) if isinstance(reply, str) else reply

    def requests(self, key: str) -> list[str]:
        """Values of one query parameter over the requests that carry it."""
        return [params[key] for _, params in self.calls if key in params]


def wfs(capabilities: str, layers: dict[str, dict]):
    """Route of a WFS: ``layers`` = type name -> schema/hits/pages fixtures."""

    def route(url, params):
        if params["REQUEST"] == "GetCapabilities":
            return capabilities
        layer = layers[params["TYPENAMES"]]
        if params["REQUEST"] == "DescribeFeatureType":
            return layer["schema"]
        if params.get("RESULTTYPE") == "hits":
            return layer["hits"]
        return layer["pages"][int(params["STARTINDEX"])]

    return route


def registry_channel(key: str) -> tuple[str, FeatureBBoxParams]:
    channel = next(
        channel
        for channel in get_source(key).channels
        if isinstance(channel.params, FeatureBBoxParams)
    )
    assert isinstance(channel.params, FeatureBBoxParams)
    return channel.endpoint, channel.params


PRG_ENDPOINT, _PRG = registry_channel("pl.gugik.prg")
PRG = dataclasses.replace(_PRG, page_size=2)
A06 = next(layer for layer in PRG.layers if layer.code == "obreb")
# PRG A06 obreby, N 244000-244400, E 566000-566400 (Krakow): hits 4, five
# rows on COUNT=2 pages (page 2 repeats the last feature of page 0).
PRG_BBOX = BBox(566000, 244000, 566400, 244400, "EPSG:2180")
PRG_A06 = {
    "schema": "prg_a06_describe.xsd",
    "hits": "prg_a06_b4_hits.xml",
    "pages": {
        0: "prg_a06_b4_c2_s0.xml",
        2: "prg_a06_b4_c2_s2.xml",
        4: "prg_a06_b4_c2_s4.xml",
        6: "prg_a06_b4_c2_s6.xml",
    },
}
A06_IDS = [
    "5ac9434d-0c44-4553-b280-ff88f5662efc",
    "88085a07-de8f-49c0-ae16-98b0993befaa",
    "c9accfd4-5e73-4a7e-b4d7-ecaaeae93051",
    "e3ca3282-d9f6-4aaa-8963-addec01bfc8c",
]

EGIB_ENDPOINT, _EGIB = registry_channel("pl.gugik.egib")
EGIB = dataclasses.replace(_EGIB, page_size=2)
# EGiB, N 588600-588800, E 654800-655000 (powiat 1415): 2 parcels, 0 buildings.
EGIB_RURAL_BBOX = BBox(654800, 588600, 655000, 588800, "EPSG:2180")
EGIB_RURAL = {
    "ms:dzialki": {
        "schema": "egib_dzialki_describe.xsd",
        "hits": "egib_dzialki_br_hits.xml",
        "pages": {0: "egib_dzialki_br_c2_s0.xml"},
    },
    "ms:budynki": {
        "schema": "egib_budynki_describe.xsd",
        "hits": "egib_budynki_br_hits.xml",
        "pages": {0: "egib_budynki_br_c2_s0.xml"},
    },
}

RUIAN_ENDPOINT = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer"
OBEC = FeatureLayer(code="obec", source="12", name="Obec", id_field="objectid")
RUIAN = FeatureBBoxParams(
    protocol="arcgis",
    native_crs="EPSG:5514",
    axis_order="xy",
    page_size=2,
    layers=(OBEC,),
    selection="level",
    order_field="objectid",
)
# RUIAN layer 12 (obce), X -455000..-450000, Y -1115000..-1110000: 4 obce.
RUIAN_BBOX = BBox(-455000, -1115000, -450000, -1110000, "EPSG:5514")

HYNET_ENDPOINT = "https://geoportal.cuzk.gov.cz/geoserver/hy-n/wfs"
HYDRO_NODE = FeatureLayer(
    code="node", source="hy-n:HydroNode", name="HydroNode", id_field="gml_id"
)
HYNET = FeatureBBoxParams(
    protocol="wfs",
    native_crs="EPSG:5514",
    axis_order="xy",
    page_size=1000,
    layers=(HYDRO_NODE,),
    selection="all",
)
HYNET_BBOX = BBox(-452000, -1112000, -451000, -1111000, "EPSG:5514")
HYNET_HITS = {
    "-452000,-1112000,-451000,-1111000": "hynet_hydronode_xy_hits.xml",
    "-1112000,-452000,-1111000,-451000": "hynet_hydronode_yx_hits.xml",
}


def hynet(url, params):
    if params["REQUEST"] == "GetCapabilities":
        return "hynet_capabilities.xml"
    numbers, _, crs = params["BBOX"].partition(",urn:")
    assert crs == "ogc:def:crs:EPSG::5514"
    return HYNET_HITS[numbers]


def ruian(count: str = "ruian_l12_count.json"):
    """Route of the RUIAN layer 12: layer JSON, count and GeoJSON pages."""

    def route(url, params):
        if url == f"{RUIAN_ENDPOINT}/12":
            return "ruian_layer12_info.json"
        assert url == f"{RUIAN_ENDPOINT}/12/query"
        if params.get("returnCountOnly") == "true":
            return count
        return f"ruian_l12_r2_o{params['resultOffset']}.json.gz"

    return route


PRNG_ENDPOINT = "https://ogcapi.geoportal.gov.pl/res/ims/maps/PRNG/apiFeatures"
PRNG_RP = FeatureLayer(
    code="rp", source="NazwaGeograficznaRP", name="NazwaGeograficznaRP", id_field="id"
)
PRNG = FeatureBBoxParams(
    protocol="ogcapi",
    native_crs="OGC:CRS84",
    axis_order="xy",
    page_size=5,
    layers=(PRNG_RP,),
    selection="all",
    timeout=300,
)
PRNG_COLLECTIONS = (f"{PRNG_ENDPOINT}/collections", {"f": "json"})
PRNG_ITEMS = f"{PRNG_ENDPOINT}/collections/NazwaGeograficznaRP/items"
# PRNG names, lon 19.93-19.945, lat 50.055-50.065 (Krakow): numberMatched 9 on
# limit=5 pages - the first (5 names) and its ``next`` (offset=5, 4 names).
PRNG_BBOX = BBox(19.93, 50.055, 19.945, 50.065, "OGC:CRS84")
PRNG_NEXT = f"{PRNG_ITEMS}?f=json&offset=5&limit=5&bbox=19.93,50.055,19.945,50.065"
PRNG_PAGES = {
    ("19.93,50.055,19.945,50.065", "5", "0"): "prng_rp_krk_l5_o0.json",
    ("19.93,50.055,19.945,50.065", "5", "5"): "prng_rp_krk_l5_o5.json",
    ("19.93,50.055,19.945,50.065", "1", "0"): "prng_rp_krk_l1_o0.json",
    ("14,54.9,14.01,54.91", "5", "0"): "prng_rp_sea_l5_o0.json",
}


def prng(replace: dict[str, Any] | None = None):
    """Route of the PRNG OGC API: ``/collections`` and items pages by
    ``bbox``/``limit``/``offset`` (query parameters or the ``next`` URL);
    ``replace`` maps a fixture name to the answer served instead."""

    def route(url, params):
        if url == PRNG_COLLECTIONS[0]:
            name = "prng_collections.json"
        else:
            base, _, query = url.partition("?")
            assert base == PRNG_ITEMS
            values = {**dict(parse_qsl(query)), **params}
            key = (values["bbox"], values["limit"], values.get("offset", "0"))
            name = PRNG_PAGES[key]
        return (replace or {}).get(name, name)

    return route


def edited(name: str, change: Callable[[dict], Any]):
    """Recorded JSON answer with its body changed in place by ``change``."""
    payload = json.loads((FIXTURES / name).read_bytes())
    change(payload)
    return answer(name, body=json.dumps(payload, ensure_ascii=False).encode())


def _without_next(payload: dict) -> None:
    payload["links"] = [link for link in payload["links"] if link["rel"] != "next"]


def _foreign_next(payload: dict) -> None:
    for link in payload["links"]:
        if link["rel"] == "next":
            link["href"] = link["href"].replace("geoportal.gov.pl", "example.com")


def test_wfs_axis_order_in_bbox():
    """BBOX numbers follow ``axis_order``: PRG ``yx`` (EPSG:2180 N,E, widened
    outward to whole mm), HY-NET ``xy`` (EPSG:5514 X,Y). The swapped HY-NET
    request gets the real silent answer: 0 features instead of 11."""
    service = FakeService(wfs("prg_capabilities.xml", {A06.source: PRG_A06}))
    bbox = BBox(566000.0004, 243999.9996, 566400.0001, 244400.0, "EPSG:2180")

    assert count_features(service, PRG_ENDPOINT, PRG, A06, bbox, timeout=5) == 4
    _, params = service.calls[0]
    assert params["BBOX"] == (
        "243999.999,566000,244400,566400.001,urn:ogc:def:crs:EPSG::2180"
    )
    assert params["SRSNAME"] == "urn:ogc:def:crs:EPSG::2180"
    assert params["RESULTTYPE"] == "hits"

    service = FakeService(hynet)
    assert (
        count_features(
            service, HYNET_ENDPOINT, HYNET, HYDRO_NODE, HYNET_BBOX, timeout=5
        )
        == 11
    )
    swapped = dataclasses.replace(HYNET, axis_order="yx")
    assert (
        count_features(
            service, HYNET_ENDPOINT, swapped, HYDRO_NODE, HYNET_BBOX, timeout=5
        )
        == 0
    )


def test_completeness_uses_hits_not_next(tmp_path):
    """PRG A06: page 0 has no ``next``, page 2 repeats the last feature of
    page 0 and the 4th of hits=4 comes only at STARTINDEX=4 (past the 4
    planned positions): the loop follows hits, not links, and the GPKG has
    exactly the 4 unique features."""
    service = FakeService(wfs("prg_capabilities.xml", {A06.source: PRG_A06}))

    pages = fetch_features(
        service, PRG_ENDPOINT, PRG, [A06], PRG_BBOX, tmp_path / "pages", timeout=5
    )

    assert service.requests("STARTINDEX") == ["0", "2", "4"]
    assert pages.layers[0].matched == 4
    summary = write_gpkg(tmp_path / "result.gpkg", pages, params=PRG)
    assert summary.features == {A06.name: 4}
    _, _, _, fields = pyogrio.raw.read(tmp_path / "result.gpkg", columns=["IIP_IDENTY"])
    assert list(fields[0]) == A06_IDS


def test_missing_features_is_download_error(tmp_path):
    """hits=4, but the stream ends (empty page at STARTINDEX=4) with 3 unique."""
    layer = {**PRG_A06, "pages": {**PRG_A06["pages"], 4: "prg_a06_b4_c2_s6.xml"}}
    service = FakeService(wfs("prg_capabilities.xml", {A06.source: layer}))

    with pytest.raises(DownloadError) as error:
        fetch_features(
            service, PRG_ENDPOINT, PRG, [A06], PRG_BBOX, tmp_path / "pages", timeout=5
        )

    assert not isinstance(error.value, NoCoverageError)
    assert service.requests("STARTINDEX") == ["0", "2", "4"]


def test_more_features_than_hits_is_download_error(tmp_path):
    """Pages with more unique features than hits (the data changed between
    the count and the pages): hits rewritten to 1, page 0 has 2 features."""
    hits = (FIXTURES / "prg_a06_b4_hits.xml").read_bytes()
    one = hits.replace(b'numberMatched="4"', b'numberMatched="1"')
    assert one != hits
    layer = {
        **PRG_A06,
        "hits": recorded_response(FIXTURES / "prg_a06_b4_hits.xml", body=one),
    }
    service = FakeService(wfs("prg_capabilities.xml", {A06.source: layer}))

    with pytest.raises(DownloadError):
        fetch_features(
            service, PRG_ENDPOINT, PRG, [A06], PRG_BBOX, tmp_path / "pages", timeout=5
        )

    assert service.requests("STARTINDEX") == ["0"]


def test_unknown_hits_is_download_error(tmp_path):
    """``numberMatched="unknown"`` (a recorded GetFeature page served as the
    hits answer) is a service failure, not an empty area; no page follows."""
    layer = {**PRG_A06, "hits": "prg_a06_sea_c2_s0.xml"}
    service = FakeService(wfs("prg_capabilities.xml", {A06.source: layer}))

    with pytest.raises(DownloadError) as error:
        fetch_features(
            service, PRG_ENDPOINT, PRG, [A06], PRG_BBOX, tmp_path / "pages", timeout=5
        )

    assert not isinstance(error.value, NoCoverageError)
    assert service.requests("STARTINDEX") == []


def _wfs_case(overrides: dict, capabilities: str = "prg_capabilities.xml"):
    layer = {**PRG_A06, **overrides}
    return (
        FakeService(wfs(capabilities, {A06.source: layer})),
        PRG_ENDPOINT,
        PRG,
        [A06],
        PRG_BBOX,
    )


def _arcgis_case(route):
    return FakeService(route), RUIAN_ENDPOINT, RUIAN, [OBEC], RUIAN_BBOX


def _ogcapi_case(replace: dict[str, Any]):
    return FakeService(prng(replace)), PRNG_ENDPOINT, PRNG, [PRNG_RP], PRNG_BBOX


ERROR_CASES = {
    # EGiB UslugaZbiorcza without SERVICE: HTML page at HTTP 200
    "capabilities_html": lambda: _wfs_case({}, capabilities="egib_no_service.html"),
    # unknown type name: ows:ExceptionReport at HTTP 400
    "hits_exception_report_400": lambda: _wfs_case(
        {"hits": "prg_exception_bad_typename.xml"}
    ),
    # the same ExceptionReport body at HTTP 200 instead of a page
    "page_exception_report_200": lambda: _wfs_case(
        {
            "pages": {
                0: answer("prg_exception_bad_typename.xml", status=200),
            }
        }
    ),
    # ArcGIS JSON {"error": ...} at HTTP 200 (returnCountOnly with f=geojson)
    "arcgis_error_json_200": lambda: _arcgis_case(
        ruian(count="ruian_l12_count_geojson_error.json")
    ),
    # HTML page at HTTP 200 instead of a GeoJSON page
    "arcgis_page_html": lambda: _arcgis_case(
        lambda url, params: (
            "egib_no_service.html" if "resultOffset" in params else ruian()(url, params)
        )
    ),
    # OGC API: HTML page at HTTP 200 instead of /collections
    "ogcapi_collections_html": lambda: _ogcapi_case(
        {"prng_collections.json": "egib_no_service.html"}
    ),
    # OGC API: unknown collection on items - HTTP 400 with a JSON error (the
    # collection listed by /collections disappeared before the first page)
    "ogcapi_items_error_400": lambda: _ogcapi_case(
        {"prng_rp_krk_l5_o0.json": "prng_error_no_collection.json"}
    ),
}


@pytest.mark.parametrize("case", sorted(ERROR_CASES))
def test_html_and_exception_report_are_download_errors(case, tmp_path):
    service, endpoint, params, layers, bbox = ERROR_CASES[case]()

    with pytest.raises(DownloadError) as error:
        fetch_features(
            service, endpoint, params, layers, bbox, tmp_path / "pages", timeout=5
        )

    assert not isinstance(error.value, NoCoverageError)
    if case.endswith("_400"):
        assert error.value.status_code == 400


CAPABILITY_CASES = {
    # the layer is not a FeatureType of the service any more
    "missing_type": lambda: (
        dataclasses.replace(A06, source="ms:A99_Brak_typu"),
        PRG,
        "prg_capabilities.xml",
    ),
    # the service DefaultCRS (HY-NET: EPSG 5514) is not the channel CRS
    "other_default_crs": lambda: (
        HYDRO_NODE,
        dataclasses.replace(HYNET, native_crs="EPSG:2180", axis_order="yx"),
        "hynet_capabilities.xml",
    ),
    # page size above the service CountDefault (EGiB: 1000)
    "page_above_count_default": lambda: (
        EGIB.layers[0],
        dataclasses.replace(EGIB, page_size=1001),
        "egib_capabilities.xml",
    ),
}


@pytest.mark.parametrize("case", sorted(CAPABILITY_CASES))
def test_capabilities_change_is_download_error(case, tmp_path):
    """The service state is checked before the first GetFeature: nothing
    but GetCapabilities is requested, no substitute type or CRS is taken."""
    layer, params, capabilities = CAPABILITY_CASES[case]()
    service = FakeService(lambda url, query: capabilities)
    bbox = BBox(566000, 244000, 566400, 244400, "EPSG:2180")

    with pytest.raises(DownloadError):
        fetch_features(
            service, "https://wfs.example", params, [layer], bbox, tmp_path, timeout=5
        )

    assert service.requests("REQUEST") == ["GetCapabilities"]


NO_COVERAGE_CASES = {
    # PRG at sea: hits numberMatched="0" (DefaultCRS as urn:ogc:def:crs)
    "prg_sea": lambda: (
        FakeService(
            wfs(
                "prg_capabilities.xml",
                {A06.source: {**PRG_A06, "hits": "prg_a06_sea_hits.xml"}},
            )
        ),
        PRG_ENDPOINT,
        PRG,
        [A06],
        BBox(450000, 800000, 451000, 801000, "EPSG:2180"),
    ),
    # HY-NET asked with swapped axes: the real silent 0 (DefaultCRS given as
    # http://www.opengis.net/def/crs/EPSG/0/5514 = the same code as EPSG:5514)
    "hynet_swapped_axes": lambda: (
        FakeService(hynet),
        HYNET_ENDPOINT,
        dataclasses.replace(HYNET, axis_order="yx"),
        [HYDRO_NODE],
        HYNET_BBOX,
    ),
    # RUIAN returnCountOnly {"count": 0}
    "ruian_count_zero": lambda: (
        FakeService(ruian(count="ruian_l12_count_sea.json")),
        RUIAN_ENDPOINT,
        RUIAN,
        [OBEC],
        RUIAN_BBOX,
    ),
}


@pytest.mark.parametrize("case", sorted(NO_COVERAGE_CASES))
def test_all_layers_empty_is_no_coverage(case, tmp_path):
    """N = 0 in every layer: ``NoCoverageError`` before any page."""
    service, endpoint, params, layers, bbox = NO_COVERAGE_CASES[case]()

    with pytest.raises(NoCoverageError):
        fetch_features(
            service, endpoint, params, layers, bbox, tmp_path / "pages", timeout=5
        )

    assert service.requests("STARTINDEX") == []
    assert service.requests("resultOffset") == []
    assert not (tmp_path / "pages").exists()


def test_empty_layer_next_to_nonempty_keeps_schema(tmp_path):
    """EGiB, 2 parcels and 0 buildings: one fresh GetCapabilities, the empty
    layer still gets its schema and empty page 0, and the GPKG has the layer
    with the XSD fields and no features."""
    service = FakeService(wfs("egib_capabilities.xml", EGIB_RURAL))

    pages = fetch_features(
        service,
        EGIB_ENDPOINT,
        EGIB,
        EGIB.layers,
        EGIB_RURAL_BBOX,
        tmp_path / "pages",
        timeout=5,
    )

    requests = [
        (params["REQUEST"], params.get("TYPENAMES"), params.get("STARTINDEX"))
        for _, params in service.calls
    ]
    assert requests == [
        ("GetCapabilities", None, None),
        ("GetFeature", "ms:dzialki", None),
        ("GetFeature", "ms:budynki", None),
        ("DescribeFeatureType", "ms:dzialki", None),
        ("GetFeature", "ms:dzialki", "0"),
        ("DescribeFeatureType", "ms:budynki", None),
        ("GetFeature", "ms:budynki", "0"),
    ]
    assert [layer.matched for layer in pages.layers] == [2, 0]

    summary = write_gpkg(tmp_path / "result.gpkg", pages, params=EGIB)

    assert summary.features == {"dzialki": 2, "budynki": 0}
    buildings = pyogrio.read_info(tmp_path / "result.gpkg", layer="budynki")
    assert buildings["features"] == 0
    assert buildings["geometry_type"] == "MultiPolygon"
    assert list(buildings["fields"]) == [
        "gml_id",
        "ID_BUDYNKU",
        "RODZAJ",
        "KONDYGNACJE_NADZIEMNE",
        "KONDYGNACJE_PODZIEMNE",
    ]


def test_arcgis_pages_use_offset_and_order(tmp_path):
    """RUIAN layer 12: layer JSON, ``returnCountOnly`` (4), then
    ``resultOffset`` pages 0 and 2 ordered by ``objectid``; the GPKG holds
    the 4 obce in objectid order."""
    service = FakeService(ruian())

    pages = fetch_features(
        service,
        RUIAN_ENDPOINT,
        RUIAN,
        [OBEC],
        RUIAN_BBOX,
        tmp_path / "pages",
        timeout=5,
    )

    url, info = service.calls[0]
    assert (url, info) == (f"{RUIAN_ENDPOINT}/12", {"f": "json"})
    _, count = service.calls[1]
    assert count == {
        "geometry": "-455000,-1115000,-450000,-1110000",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "5514",
        "spatialRel": "esriSpatialRelIntersects",
        "returnCountOnly": "true",
        "f": "json",
    }
    queries = [params for _, params in service.calls[2:]]
    assert [query["resultOffset"] for query in queries] == ["0", "2"]
    assert {
        (
            query["orderByFields"],
            query["resultRecordCount"],
            query["outSR"],
            query["outFields"],
            query["f"],
        )
        for query in queries
    } == {("objectid", "2", "5514", "*", "geojson")}
    assert ("objectid", "esriFieldTypeOID") in pages.layers[0].fields

    summary = write_gpkg(tmp_path / "result.gpkg", pages, params=RUIAN)

    assert summary.features == {"Obec": 4}
    _, _, _, fields = pyogrio.raw.read(tmp_path / "result.gpkg", columns=["objectid"])
    assert list(fields[0]) == [6169, 6189, 12391, 13310]


def _fetch_prng(service: FakeService, pages_dir: Path, bbox: BBox = PRNG_BBOX):
    return fetch_features(
        service, PRNG_ENDPOINT, PRNG, [PRNG_RP], bbox, pages_dir, timeout=5
    )


def test_ogcapi_pages_and_crs84(tmp_path):
    """PRNG: ``/collections``, the first page by ``bbox`` (lon,lat CRS84,
    widened outward) and ``limit``, the second only by its ``next`` link; one
    CRS84 GPKG layer with the 9 names once each. A ``next`` off the service
    host or a ``numberReturned`` other than the page features is a
    ``DownloadError``; a bbox labelled in another CRS is a programmer error."""
    service = FakeService(prng())
    bbox = BBox(19.93000004, 50.05500003, 19.94499996, 50.06499997, "OGC:CRS84")

    pages = _fetch_prng(service, tmp_path / "pages", bbox)

    assert service.calls == [
        PRNG_COLLECTIONS,
        (PRNG_ITEMS, {"f": "json", "bbox": "19.93,50.055,19.945,50.065", "limit": "5"}),
        (PRNG_NEXT, {}),
    ]
    assert pages.layers[0].matched == 9
    summary = write_gpkg(tmp_path / "result.gpkg", pages, params=PRNG)
    assert summary.features == {"NazwaGeograficznaRP": 9}
    info = pyogrio.read_info(tmp_path / "result.gpkg", force_total_bounds=True)
    assert CRS.from_user_input(info["crs"]) == CRS.from_user_input("OGC:CRS84")
    min_x, min_y, max_x, max_y = info["total_bounds"]
    assert 19.93 <= min_x <= max_x <= 19.945  # x = longitude
    assert 50.055 <= min_y <= max_y <= 50.065  # y = latitude
    _, _, _, fields = pyogrio.raw.read(tmp_path / "result.gpkg", columns=["id"])
    assert len(set(fields[0])) == len(fields[0]) == 9

    service = FakeService(
        prng(
            {"prng_rp_krk_l5_o0.json": edited("prng_rp_krk_l5_o0.json", _foreign_next)}
        )
    )
    with pytest.raises(DownloadError):
        _fetch_prng(service, tmp_path / "foreign")
    assert len(service.calls) == 2  # nothing sent off the service

    def overstated(payload: dict) -> None:
        payload["numberReturned"] = len(payload["features"]) + 1

    service = FakeService(
        prng({"prng_rp_krk_l5_o5.json": edited("prng_rp_krk_l5_o5.json", overstated)})
    )
    with pytest.raises(DownloadError):
        _fetch_prng(service, tmp_path / "overstated")

    service = FakeService(prng())
    with pytest.raises(ValueError):
        _fetch_prng(service, tmp_path / "epsg", PRNG_BBOX._replace(crs="EPSG:4326"))
    assert service.calls == []


def test_ogcapi_count_is_number_matched():
    """``count_features`` asks for one page with ``limit=1`` and returns its
    ``numberMatched`` (9), not the one name on the page."""
    service = FakeService(prng())

    count = count_features(service, PRNG_ENDPOINT, PRNG, PRNG_RP, PRNG_BBOX, timeout=5)

    assert count == 9
    assert service.calls == [
        (PRNG_ITEMS, {"f": "json", "bbox": "19.93,50.055,19.945,50.065", "limit": "1"})
    ]


OGCAPI_STREAM_CASES = {
    # the second page reports another numberMatched (the data changed)
    "number_matched_changed": lambda: (
        {
            "prng_rp_krk_l5_o5.json": edited(
                "prng_rp_krk_l5_o5.json", lambda page: page.update(numberMatched=10)
            )
        },
        3,
    ),
    # offset ignored: the next page repeats the first one and its next link
    "page_without_new_ids": lambda: (
        {"prng_rp_krk_l5_o5.json": "prng_rp_krk_l5_o0.json"},
        3,
    ),
    # no next link after 5 of the 9 names
    "no_next_before_n": lambda: (
        {"prng_rp_krk_l5_o0.json": edited("prng_rp_krk_l5_o0.json", _without_next)},
        2,
    ),
}


@pytest.mark.parametrize("case", sorted(OGCAPI_STREAM_CASES))
def test_ogcapi_inconsistent_stream_is_download_error(case, tmp_path):
    """An OGC API page stream that cannot reach numberMatched unique ids
    fails at once, without further requests."""
    replace, requests = OGCAPI_STREAM_CASES[case]()
    service = FakeService(prng(replace))

    with pytest.raises(DownloadError) as error:
        _fetch_prng(service, tmp_path / "pages")

    assert not isinstance(error.value, NoCoverageError)
    assert len(service.calls) == requests


def test_ogcapi_sea_is_no_coverage(tmp_path):
    """numberMatched 0 on the first page (Baltic Sea): ``NoCoverageError``
    and no request after that page (OGC API has no separate count)."""
    service = FakeService(prng())
    sea = BBox(14.0, 54.9, 14.01, 54.91, "OGC:CRS84")

    with pytest.raises(NoCoverageError):
        _fetch_prng(service, tmp_path / "pages", sea)

    assert service.calls == [
        PRNG_COLLECTIONS,
        (PRNG_ITEMS, {"f": "json", "bbox": "14,54.9,14.01,54.91", "limit": "5"}),
    ]


def test_ogcapi_missing_collection_is_download_error(tmp_path):
    """A layer whose collection ``/collections`` does not list: a
    ``DownloadError`` naming it, before any items request."""
    missing = dataclasses.replace(PRNG_RP, source="NazwaGeograficznaPL", name="pl")
    service = FakeService(prng())

    with pytest.raises(DownloadError, match="NazwaGeograficznaPL") as error:
        fetch_features(
            service,
            PRNG_ENDPOINT,
            PRNG,
            [PRNG_RP, missing],
            PRNG_BBOX,
            tmp_path / "pages",
            timeout=5,
        )

    assert "NazwaGeograficznaRP" not in str(error.value)
    assert service.calls == [PRNG_COLLECTIONS]
