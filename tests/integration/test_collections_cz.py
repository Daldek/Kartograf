"""CZ collections of plan D (ADR-042 D12, D15-D17) on real CUZK answers.

Fixtures: ``tests/fixtures/cz/feature_bbox`` (ZABAGED REST and HY-NET WFS,
recorded 2026-10-15, README there), ``tests/fixtures/pl/feature_bbox``
(RUIAN layer 12 and the HY-NET GetCapabilities of plan C),
``tests/fixtures/cz/atom`` (ZABAGED-GPKG feeds) and
``tests/fixtures/cz/unit_package`` (``HEAD`` and ZIP members of the RUIAN and
HY-NET national files).
"""

import dataclasses
import gzip
import json
import re
import unicodedata
from pathlib import Path

import pyogrio
import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    check_collection,
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.notices import AREA_OMITTED, WHOLE_COUNTRY_SIZE
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams, FeatureLayer
from tests.conftest import recorded_response
from tests.support.fake_packages import FakePackageSession, FakeResponse, zip_bytes

FIXTURES = Path(__file__).parent.parent / "fixtures"
CZ = FIXTURES / "cz" / "feature_bbox"
PL = FIXTURES / "pl" / "feature_bbox"
ATOM = FIXTURES / "cz" / "atom"
HYNET = "https://geoportal.cuzk.gov.cz/geoserver/hy-n/wfs"
RUIAN = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer"
ZABAGED = "https://ags.cuzk.gov.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer"
ZABAGED_SERVICE = "https://atom.cuzk.gov.cz/ZABAGED-GPKG/ZABAGED-GPKG.xml"
ZABAGED_FEED = "https://atom.cuzk.gov.cz/ZABAGED-GPKG/datasetFeeds/CZ-00025712-CUZK_ZABAGED-GPKG_1.xml"
ZABAGED_5514 = "https://openzu.cuzk.gov.cz/opendata/ZABAGED-GPKG/epsg-5514/ZABAGED-5514-gpkg-20261004.zip"
# HEAD headers (real size and ETag) and ZIP member names, recorded 2026-10-16
NATIONAL = json.loads(
    (FIXTURES / "cz" / "unit_package" / "packages.json").read_text(encoding="utf-8")
)
# 500 x 500 m at Cesky Tesin (EPSG:5514): HY-NET 3 links, 1 node, 0 crossings
AREA = BBox(-451000, -1112000, -450500, -1111500, "EPSG:5514")
_SHORT = {
    "hy-n:WatercourseLink": "watercourselink",
    "hy-n:HydroNode": "hydronode",
    "hy-n:WatercourseSeparatedCrossing": "crossing",
}


def answer(path: Path, body: bytes | None = None):
    if path.suffix == ".gz":
        path, body = path.with_suffix(""), gzip.decompress(path.read_bytes())
    return recorded_response(path, body=body)


class FakeCuzk:
    """``requests.Session`` stand-in for CUZK services; ``calls`` = (url,
    params) of every GET in order; ``extra`` = URL -> response factory."""

    def __init__(self, extra: dict | None = None) -> None:
        self.extra = dict(extra or {})
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, timeout=None, headers=None, stream=False):
        params = dict(params or {})
        self.calls.append((url, params))
        if url in self.extra:
            return self.extra[url]()
        if url.startswith(f"{ZABAGED}/"):
            return answer(self._zabaged(url.removeprefix(f"{ZABAGED}/"), params))
        if url == HYNET:
            return answer(self._hynet(params))
        if url == f"{RUIAN}/12":
            return answer(PL / "ruian_layer12_info.json")
        if url == f"{RUIAN}/12/query":
            if params.get("returnCountOnly") == "true":
                return answer(PL / "ruian_l12_count.json")
            return answer(PL / f"ruian_l12_r2_o{params['resultOffset']}.json.gz")
        raise AssertionError(f"Nieoczekiwane zapytanie: {url} {params}")

    @staticmethod
    def _hynet(params: dict) -> Path:
        if params["REQUEST"] == "GetCapabilities":
            return PL / "hynet_capabilities.xml"
        short = _SHORT[params["TYPENAMES"]]
        if params["REQUEST"] == "DescribeFeatureType":
            return CZ / f"hynet_{short}_describe.xsd"
        assert params["BBOX"] == (
            "-451000,-1112000,-450500,-1111500,urn:ogc:def:crs:EPSG::5514"
        )
        if params.get("RESULTTYPE") == "hits":
            return CZ / f"hynet_{short}_b5_hits.xml"
        return CZ / f"hynet_{short}_b5_c2_s{params['STARTINDEX']}.xml"

    @staticmethod
    def _zabaged(path: str, params: dict) -> Path:
        layer, _, query = path.partition("/")
        if not query:
            return CZ / f"zabaged_l{layer}_info.json"
        assert params["geometry"] == "-451000,-1112000,-450500,-1111500"
        if params.get("returnCountOnly") == "true":
            return CZ / f"zabaged_l{layer}_b5_count.json"
        return CZ / f"zabaged_l{layer}_b5_r2_o{params['resultOffset']}.json.gz"


def _page_size(
    monkeypatch, key: str, size: int, sources: set[str] | None = None
) -> None:
    """The registry entry with the area channel paging by ``size`` (the
    COUNT/resultRecordCount of the recorded pages); ``sources`` keeps only
    the layers with these source ids (the recorded ones)."""
    source = registry.get_source(key)

    def recorded(params: FeatureBBoxParams) -> FeatureBBoxParams:
        layers = tuple(
            layer
            for layer in params.layers
            if sources is None or layer.source in sources
        )
        return dataclasses.replace(params, page_size=size, layers=layers)

    channels = tuple(
        dataclasses.replace(ch, params=recorded(ch.params))
        if isinstance(ch.params, FeatureBBoxParams)
        else ch
        for ch in source.channels
    )
    monkeypatch.setitem(
        registry._SOURCES, key, dataclasses.replace(source, channels=channels)
    )


def serve_zabaged(monkeypatch) -> FakeCuzk:
    """ZABAGED of ``AREA`` without network: the recorded layers only (93
    lines, 132 without objects, 138 polygons in pages of 2) and ``FakeCuzk``
    as the session of the collection engine."""
    _page_size(monkeypatch, "cz.cuzk.zabaged", 2, sources={"93", "132", "138"})
    fake = FakeCuzk()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


def _code(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore")
    return re.sub(r"[^a-z0-9]+", "_", ascii_name.decode().lower()).strip("_")


def test_zabaged_layers_config_matches_service():
    """22 land cover and hydrography layers: the REST layer id, its code =
    the service name without diacritics (no BDOT10k mapping, ADR-042 D15)."""
    service = json.loads((CZ / "zabaged_pjson.json").read_text(encoding="utf-8"))
    by_id = {str(layer["id"]): layer for layer in service["layers"]}
    layers = col.collection_layers("cz.cuzk.zabaged")
    assert len(layers) == 22
    for layer in layers:
        found = by_id[layer.source]
        assert found["type"] == "Feature Layer"
        assert found["geometryType"] in ("esriGeometryPolyline", "esriGeometryPolygon")
        assert layer.code == layer.name == _code(found["name"])
        assert layer.id_field == "fid_zbg"
    lines = {
        layer.code
        for layer in layers
        if by_id[layer.source]["geometryType"] == "esriGeometryPolyline"
    }
    assert lines == {"vodni_tok", "brehova_cara"}


def test_zabaged_whole_country_requires_crs(tmp_path, monkeypatch, frozen_clock):
    """The national GPKG exists in EPSG:5514 and EPSG:3045: the choice is
    required before any request; the size of the feed is announced before
    the transfer; the edition of the feed labels the version."""
    manager = LandCoverManager("zabaged", cache=False, root=tmp_path)
    with pytest.raises(ValidationError, match="EPSG:5514, EPSG:3045"):
        manager.download(whole_country=True)
    with pytest.raises(ValidationError, match="--teryt"):
        manager.download(teryt="1261")
    with pytest.raises(ValidationError, match="--product bdot10k"):
        manager.download(bbox=AREA, format="SHP")

    body = zip_bytes(["ZABAGED_RESULTS.gpkg"])
    events: list[str] = []
    _zabaged_country(monkeypatch, body, events)
    result = manager.download(
        whole_country=True,
        horizontal_crs="EPSG:5514",
        on_notice=lambda n: events.append(n.code),
    )

    (item,) = result.files
    assert item.file is not None
    assert item.file.path == tmp_path / "landcover/cz_zabaged_gpkg_5514/country/cz.zip"
    assert item.file.label == "2026-10-04"
    assert item.file.path.read_bytes() == body
    assert events.index(WHOLE_COUNTRY_SIZE) < events.index("GET")
    meta = _meta(item.file.path)
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert meta["request"] == {"whole_country": True, "horizontal_crs": "EPSG:5514"}
    assert meta["extra"]["source"]["edition"] == "2026-10-04"
    assert meta["extra"]["version"]["label_source"] == "edition"


def _zabaged_country(monkeypatch, body: bytes, events: list[str]) -> dict[str, bytes]:
    """ZABAGED-GPKG feeds and the EPSG:5514 national file (``body``, its size
    in the feed ``length``); a GET of the file appends ``"GET"`` to
    ``events``. Returns the dataset feed bytes by name (``"dataset"``) - a
    test may publish a new edition by replacing them."""
    feed = (ATOM / "zabaged_dataset.xml").read_bytes()
    feeds = {
        "dataset": feed.replace(
            b'length="5805826649"', f'length="{len(body)}"'.encode()
        )
    }

    def national_file() -> FakeResponse:
        events.append("GET")
        return FakeResponse(200, {"Content-Length": str(len(body))}, body)

    fake = FakeCuzk(
        {
            ZABAGED_SERVICE: lambda: answer(ATOM / "zabaged_service.xml"),
            ZABAGED_FEED: lambda: answer(
                ATOM / "zabaged_dataset.xml", body=feeds["dataset"]
            ),
            ZABAGED_5514: national_file,
        }
    )
    monkeypatch.setattr(col, "_session", lambda: fake)
    return feeds


def test_zabaged_whole_country_check_by_edition(tmp_path, monkeypatch, frozen_clock):
    """``--check`` of the national file reads only the ATOM feeds:
    the same ``updated`` of the file entry = ``current``, a later one =
    ``newer`` (labelled by the new date); the file itself is never fetched."""
    events: list[str] = []
    feeds = _zabaged_country(monkeypatch, zip_bytes(["ZABAGED_RESULTS.gpkg"]), events)
    manager = LandCoverManager("zabaged", cache=False, root=tmp_path)
    choice = {"whole_country": True, "horizontal_crs": "EPSG:5514"}
    assert [i.status for i in manager.check(**choice).items] == ["missing"]
    manager.download(**choice)
    assert events == ["GET"]

    plan = manager.check(**choice)
    (item,) = plan.items
    assert (item.track, item.status, item.local_label) == (
        "landcover",
        "current",
        "2026-10-04",
    )

    feeds["dataset"] = feeds["dataset"].replace(
        b"<updated>2026-10-04T18:51:04+02:00</updated>",
        b"<updated>2026-10-11T18:00:00+02:00</updated>",
    )
    (item,) = manager.check(**choice).items
    assert (item.status, item.local_label, item.available_label) == (
        "newer",
        "2026-10-04",
        "2026-10-11",
    )
    assert events == ["GET"]


def test_zabaged_bbox_gpkg(tmp_path, monkeypatch, frozen_clock):
    """An area -> one GPKG in EPSG:5514 with one layer per ZABAGED layer
    named by its code, complete against ``returnCountOnly`` (2 + 1 objects in
    two pages), an empty layer keeps its schema, the layer description names
    the service layer and its id; an area has no cheap update signal
    (``unverifiable`` without a request)."""
    fake = serve_zabaged(monkeypatch)
    manager = LandCoverManager("zabaged", cache=False, root=tmp_path)

    notices: list = []
    area = manager.download(bbox=AREA, on_notice=notices.append)
    (item,) = area.files
    # the land cover source names the message, not the "landcover" group
    (omitted,) = [n for n in area.notices if n.code == AREA_OMITTED]
    assert omitted.level == "info"
    assert omitted.message.startswith("zabaged: the area result has 22 land cover")
    assert "--whole-country --horizontal-crs EPSG:5514|EPSG:3045" in omitted.message
    assert notices == list(area.notices)

    path = item.file.path
    assert path == (
        tmp_path / "landcover/cz_zabaged/bbox/-451000_-1112000_-450500_-1111500.gpkg"
    )
    counts = {
        name: pyogrio.read_info(path, layer=name)["features"]
        for name, _ in pyogrio.list_layers(path)
    }
    assert counts == {
        "vodni_tok": 2,
        "vodni_plocha": 0,
        "orna_puda_a_ostatni_dale_nespecifikovane_plochy": 3,
    }
    empty = pyogrio.read_info(path, layer="vodni_plocha")
    assert empty["crs"] == "EPSG:5514" and "fid_zbg" in list(empty["fields"])
    assert pyogrio.read_info(path, layer="vodni_tok")["layer_metadata"] == {
        "DESCRIPTION": "Vodní tok (93)"
    }
    meta = _meta(path)
    assert (meta["dataset"], meta["horizontal_crs"]) == ("cz.cuzk.zabaged", "EPSG:5514")
    assert meta["product"] == "zabaged"

    fake.calls.clear()
    (planned,) = manager.check(bbox=AREA).items
    assert (planned.track, planned.status) == ("landcover", "unverifiable")
    assert fake.calls == []


@pytest.mark.parametrize(
    ("name", "product", "stored", "crs"),
    [
        (
            "ruian_country",
            "admin",
            "boundaries/cz_ruian_shp/country/cz.zip",
            "EPSG:5514",
        ),
        ("hynet_country", "network", "hydro/cz_hynet_gpkg/country/cz.zip", "EPSG:3045"),
    ],
)
def test_national_file_http_signal(tmp_path, monkeypatch, name, product, stored, crs):
    """RUIAN and HY-NET national files (signal ``http``): the real size from
    ``HEAD`` announced before the transfer, the ZIP stored 1:1 with the CRS
    of the file; ``--check`` asks only ``HEAD`` - the same ``ETag`` =
    ``current``, another = ``newer``; the default run keeps the local file,
    ``--upgrade`` stores the new one next to it. No frozen clock: of two
    versions with one label (the day of the download) the later is newest."""
    entry = NATIONAL[name]
    url, head = entry["url"], entry["headers"]
    body = zip_bytes(entry["members"])
    session = FakePackageSession(
        {url: (200, {**head, "Content-Length": str(len(body))}, body)},
        heads={url: head},
    )
    monkeypatch.setattr(col, "_session", lambda: session)
    choice = {
        "product": product,
        "country": "cz",
        "whole_country": True,
        "root": tmp_path,
        "cache": False,
    }
    seen: list[tuple[str, int]] = []

    report = download_collection(
        **choice, on_notice=lambda n: seen.append((n.code, session.gets(url)))
    )

    assert report.ok
    (item,) = report.files
    assert item.file.path == tmp_path / stored
    assert item.file.path.read_bytes() == body
    assert seen == [(WHOLE_COUNTRY_SIZE, 0)]
    assert head["Content-Length"] in report.notices[0].message
    meta = _meta(item.file.version_path)
    assert meta["horizontal_crs"] == crs
    assert meta["extra"]["http"]["etag"] == head["ETag"]

    session.calls.clear()
    (current,) = check_collection(**choice).items
    assert current.status == "current"
    assert session.calls == [("HEAD", url)]

    session.heads[url] = {**head, "ETag": '"nowe-wydanie"'}
    (newer,) = check_collection(**choice).items
    assert newer.status == "newer"
    kept = download_collection(**choice)
    assert [f.file.status for f in kept.files] == ["local"]
    assert session.gets(url) == 0  # no transfer since the first download

    new_body = zip_bytes(entry["members"], content=b"nowe wydanie")
    session.routes[url] = (
        200,
        {**head, "ETag": '"nowe-wydanie"', "Content-Length": str(len(new_body))},
        new_body,
    )
    upgraded = download_collection(**choice, update="upgrade")
    (fresh,) = upgraded.files
    assert fresh.file.path.read_bytes() == new_body
    assert fresh.file.version_path != item.file.version_path
    assert item.file.version_path.read_bytes() == body


def test_hynet_links_and_nodes_and_misleading_next(tmp_path, monkeypatch, frozen_clock):
    """Completeness from ``hits``: the last WatercourseLink page (1 feature)
    carries a ``next`` link (http, STARTINDEX=4) that is never followed; the
    area result is the geometric network (links and nodes) - the crossings
    without geometry are in the national file only (``AREA_OMITTED``)."""
    _page_size(monkeypatch, "cz.cuzk.hynet", 2)
    fake = FakeCuzk()
    monkeypatch.setattr(col, "_session", lambda: fake)

    report = download_collection(
        product="network", country="cz", bbox=AREA, root=tmp_path, cache=False
    )

    assert report.ok, report.failed
    (omitted,) = [n for n in report.notices if n.code == AREA_OMITTED]
    assert omitted.level == "info"
    assert omitted.message.startswith(
        "network: area result without grade-separated crossings"
    )
    assert "WatercourseSeparatedCrossing" in omitted.message
    assert "--whole-country --country cz" in omitted.message
    (item,) = report.files
    path = item.file.path
    assert (
        path == tmp_path / "hydro/cz_hynet/bbox/-451000_-1112000_-450500_-1111500.gpkg"
    )
    counts = {
        name: pyogrio.read_info(path, layer=name)["features"]
        for name, _ in pyogrio.list_layers(path)
    }
    assert counts == {"WatercourseLink": 3, "HydroNode": 1}
    assert pyogrio.read_info(path, layer="WatercourseLink")["crs"] == "EPSG:5514"
    starts = [p["STARTINDEX"] for u, p in fake.calls if "STARTINDEX" in p]
    assert "4" not in starts
    meta = _meta(path)
    assert meta["horizontal_crs"] == "EPSG:5514"
    layers = {x["name"]: x["features"] for x in meta["extra"]["source"]["layers"]}
    assert layers == counts


def test_wfs_type_without_objects_is_empty_layer(tmp_path, monkeypatch, frozen_clock):
    """A WFS type without objects in the area (recorded: GeoServer answers for
    WatercourseSeparatedCrossing - 0 hits, an empty page, no XSD schema) is an
    empty GPKG layer with the id field: the layers of the file do not depend
    on the area."""
    source = registry.get_source("cz.cuzk.hynet")
    empty = FeatureLayer(
        code="WatercourseSeparatedCrossing",
        source="hy-n:WatercourseSeparatedCrossing",
        name="WatercourseSeparatedCrossing",
        id_field="gml_id",
    )
    channels = tuple(
        dataclasses.replace(
            ch,
            params=dataclasses.replace(
                ch.params, page_size=2, layers=(*ch.params.layers, empty)
            ),
        )
        if isinstance(ch.params, FeatureBBoxParams)
        else ch
        for ch in source.channels
    )
    monkeypatch.setitem(
        registry._SOURCES,
        "cz.cuzk.hynet",
        dataclasses.replace(source, channels=channels),
    )
    monkeypatch.setattr(col, "_session", lambda: FakeCuzk())

    report = download_collection(
        product="network", country="cz", bbox=AREA, root=tmp_path, cache=False
    )

    path = report.files[0].file.path
    info = pyogrio.read_info(path, layer="WatercourseSeparatedCrossing")
    assert info["features"] == 0
    assert list(info["fields"]) == ["gml_id"]


def test_hynet_whole_country_is_epsg_3045(tmp_path):
    with pytest.raises(ValidationError, match="EPSG:3045"):
        validate_collection_request(
            product="network",
            country="cz",
            whole_country=True,
            horizontal_crs="EPSG:5514",
            root=tmp_path,
        )
    request = validate_collection_request(
        product="network", country="cz", whole_country=True, root=tmp_path
    )
    (part,) = request.parts
    assert part.segment == "hydro/cz_hynet_gpkg"
    assert part.channel.horizontal_crs == "EPSG:3045"


def test_ruian_obec_by_kod(tmp_path, monkeypatch, frozen_clock):
    _page_size(monkeypatch, "cz.cuzk.ruian", 2)
    monkeypatch.setattr(col, "_session", lambda: FakeCuzk())
    area = BBox(-455000, -1115000, -450000, -1110000, "EPSG:5514")

    report = download_collection(
        product="admin",
        country="cz",
        level="obec",
        bbox=area,
        root=tmp_path,
        cache=False,
    )

    (item,) = report.files
    path = item.file.path
    assert path == (
        tmp_path
        / "boundaries/cz_ruian_obec/bbox/-455000_-1115000_-450000_-1110000.gpkg"
    )
    info = pyogrio.read_info(path, layer="Obec")
    assert info["features"] == 4
    assert info["layer_metadata"] == {"DESCRIPTION": "Obec (12)"}
    meta, _, _, values = pyogrio.raw.read(path, layer="Obec", read_geometry=False)
    kody = list(values[list(meta["fields"]).index("kod")])
    assert len(kody) == 4 and kody == sorted(kody)


def test_auto_level_per_country(tmp_path):
    border = BBox(18.5, 49.6, 18.8, 49.9, "EPSG:4326")
    with pytest.raises(ValidationError, match=r"pl=<level>,cz=<level>"):
        check_collection(
            product="admin",
            country="auto",
            level="gmina",
            bbox=border,
            root=tmp_path,
            cache=False,
        )
    plan = check_collection(
        product="admin",
        country="auto",
        level={"pl": "gmina", "cz": "obec"},
        bbox=border,
        root=tmp_path,
        cache=False,
    )
    assert sorted(item.segment for item in plan.items) == [
        "boundaries/cz_ruian_obec",
        "boundaries/pl_prg_gmina",
    ]
