"""CZ collections of plan D (ADR-042 D12, D15-D17) on real CUZK answers.

Fixtures: ``tests/fixtures/cz/feature_bbox`` (ZABAGED REST and HY-NET WFS,
recorded 2026-10-15, README there), ``tests/fixtures/pl/feature_bbox``
(RUIAN layer 12 and the HY-NET GetCapabilities of plan C) and
``tests/fixtures/cz/atom`` (ZABAGED-GPKG feeds).
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
from kartograf.notices import WHOLE_COUNTRY_SIZE
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams
from tests.conftest import recorded_response
from tests.fake_packages import FakeResponse, zip_bytes

FIXTURES = Path(__file__).parent / "fixtures"
CZ = FIXTURES / "cz" / "feature_bbox"
PL = FIXTURES / "pl" / "feature_bbox"
ATOM = FIXTURES / "cz" / "atom"
HYNET = "https://geoportal.cuzk.gov.cz/geoserver/hy-n/wfs"
RUIAN = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer"
ZABAGED_FEED = "https://atom.cuzk.gov.cz/ZABAGED-GPKG/datasetFeeds/CZ-00025712-CUZK_ZABAGED-GPKG_1.xml"
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


def _page_size(monkeypatch, key: str, size: int) -> None:
    """The registry entry with the area channel paging by ``size`` (the
    COUNT/resultRecordCount of the recorded pages)."""
    source = registry.get_source(key)
    channels = tuple(
        dataclasses.replace(ch, params=dataclasses.replace(ch.params, page_size=size))
        if isinstance(ch.params, FeatureBBoxParams)
        else ch
        for ch in source.channels
    )
    monkeypatch.setitem(
        registry._SOURCES, key, dataclasses.replace(source, channels=channels)
    )


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
    manager = LandCoverManager(tmp_path, "zabaged", cache=False)
    with pytest.raises(ValidationError, match="EPSG:5514, EPSG:3045"):
        manager.download(whole_country=True)
    with pytest.raises(ValidationError, match="--teryt"):
        manager.download(teryt="1261")
    with pytest.raises(ValidationError, match="--source bdot10k"):
        manager.download(bbox=AREA, format="SHP")

    body = zip_bytes(["ZABAGED_RESULTS.gpkg"])
    feed = (ATOM / "zabaged_dataset.xml").read_bytes()
    feed = feed.replace(b'length="5805826649"', f'length="{len(body)}"'.encode())
    url = "https://openzu.cuzk.gov.cz/opendata/ZABAGED-GPKG/epsg-5514/ZABAGED-5514-gpkg-20261004.zip"
    events: list[str] = []
    fake = FakeCuzk(
        {
            "https://atom.cuzk.gov.cz/ZABAGED-GPKG/ZABAGED-GPKG.xml": lambda: answer(
                ATOM / "zabaged_service.xml"
            ),
            ZABAGED_FEED: lambda: answer(ATOM / "zabaged_dataset.xml", body=feed),
            url: lambda: (
                events.append("GET")
                or FakeResponse(200, {"Content-Length": str(len(body))}, body)
            ),
        }
    )
    monkeypatch.setattr(col, "_session", lambda: fake)
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


def test_hynet_three_layers_and_misleading_next(tmp_path, monkeypatch, frozen_clock):
    """Completeness from ``hits``: the last WatercourseLink page (1 feature)
    carries a ``next`` link (http, STARTINDEX=4) that is never followed; the
    empty crossing type (no XSD schema at GeoServer) is an empty layer."""
    _page_size(monkeypatch, "cz.cuzk.hy_net", 2)
    fake = FakeCuzk()
    monkeypatch.setattr(col, "_session", lambda: fake)

    report = download_collection(
        product="network", country="cz", bbox=AREA, output_dir=tmp_path, cache=False
    )

    assert report.ok, report.failed
    (item,) = report.files
    path = item.file.path
    assert (
        path == tmp_path / "hydro/cz_hynet/bbox/-451000_-1112000_-450500_-1111500.gpkg"
    )
    counts = {
        name: pyogrio.read_info(path, layer=name)["features"]
        for name, _ in pyogrio.list_layers(path)
    }
    assert counts == {
        "WatercourseLink": 3,
        "HydroNode": 1,
        "WatercourseSeparatedCrossing": 0,
    }
    assert pyogrio.read_info(path, layer="WatercourseLink")["crs"] == "EPSG:5514"
    starts = [p["STARTINDEX"] for u, p in fake.calls if "STARTINDEX" in p]
    assert "4" not in starts
    meta = _meta(path)
    assert meta["horizontal_crs"] == "EPSG:5514"
    layers = {x["name"]: x["features"] for x in meta["extra"]["source"]["layers"]}
    assert layers == counts


def test_hynet_whole_country_is_epsg_3045(tmp_path):
    with pytest.raises(ValidationError, match="EPSG:3045"):
        validate_collection_request(
            product="network",
            country="cz",
            whole_country=True,
            horizontal_crs="EPSG:5514",
            output_dir=tmp_path,
        )
    request = validate_collection_request(
        product="network", country="cz", whole_country=True, output_dir=tmp_path
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
        output_dir=tmp_path,
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
    with pytest.raises(ValidationError, match=r"pl=<poziom>,cz=<poziom>"):
        check_collection(
            product="admin",
            country="auto",
            level="gmina",
            bbox=border,
            output_dir=tmp_path,
            cache=False,
        )
    plan = check_collection(
        product="admin",
        country="auto",
        level={"pl": "gmina", "cz": "obec"},
        bbox=border,
        output_dir=tmp_path,
        cache=False,
    )
    assert sorted(item.segment for item in plan.items) == [
        "boundaries/cz_ruian_obec",
        "boundaries/pl_prg_gmina",
    ]
