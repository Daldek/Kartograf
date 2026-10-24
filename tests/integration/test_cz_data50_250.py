"""Data50 and Data250 of CUZK: the object layers of an area (ArcGIS REST)
and the national SHP ZIP of the ATOM feed (plan E, E4).

Fixtures ``tests/fixtures/cz/data50_250`` (recorded 2026-10-16, README
there): the layer lists of both MapServer services, the layers of the Cesky
Tesin envelope in pages of one object, the service and dataset feeds and
the member names of both national files. The national file bodies are small
ZIPs built with those names (the real files have 230-757 MB).
"""

import json
from pathlib import Path

import pyogrio
import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.notices import WHOLE_COUNTRY_SIZE, size_text
from tests.integration.test_collections_cz import _code, _page_size, answer
from tests.support.fake_packages import FakeResponse, zip_bytes

pytestmark = pytest.mark.usefixtures("frozen_clock")

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cz" / "data50_250"
NATIONAL: dict = json.loads((FIXTURES / "national.json").read_text(encoding="utf-8"))
REST = "https://ags.cuzk.gov.cz/arcgis/rest/services"
ATOM = "https://atom.cuzk.gov.cz"
# 18.566,49.757,18.572,49.761 (EPSG:4326, Cesky Tesin) and its EPSG:5514
# envelope, as the recorded queries ask it (README)
AREA = BBox(18.566, 49.757, 18.572, 49.761, "EPSG:4326")
TESIN = "-450998.718,-1112011.026,-450531.472,-1111532.273"
# the area result is stored under the EPSG:5514 envelope of the request
STORED = "-450998.7179_-1112011.026_-450531.4728_-1111532.273"


class Dataset:
    """What the recordings of one dataset hold: the recorded layers (id ->
    GPKG layer and its objects at Cesky Tesin), the edition of the national
    file in EPSG:5514 and its real size."""

    def __init__(
        self,
        name: str,
        layers: dict[str, tuple[str, int]],
        objects: int,
        label: str,
        length: int,
    ) -> None:
        self.name = name
        self.key = f"cz.cuzk.{name}"
        self.layers = layers
        self.objects = objects
        self.label = label
        self.length = length
        title = {"data50": "Data50", "data250": "Data250"}[name]
        self.service = f"{REST}/{name.upper()}/MapServer"
        self.service_feed = f"{ATOM}/{title}/{title}.xml"
        self.dataset_feed = (
            f"{ATOM}/{title}/datasetFeeds/CZ-00025712-CUZK_{title}_1.xml"
        )
        self.file = f"https://openzu.cuzk.gov.cz/opendata/{title}/epsg-5514/{name}.zip"


DATA50 = Dataset(
    "data50",
    {
        "62": ("vodni_plocha", 0),
        "63": ("vodni_tok", 1),
        "66": ("louka_pastvina", 2),
        "67": ("les", 2),
    },
    objects=69,
    label="2026-04-28",
    length=515_542_917,
)
DATA250 = Dataset(
    "data250",
    {
        "99": ("vodni_tok_povrchovy_staly_do_5_m", 1),
        "108": ("vodni_plocha", 0),
        "117": ("les", 2),
    },
    objects=116,
    label="2026-05-12",
    length=230_485_722,
)
DATASETS = pytest.mark.parametrize("data", [DATA50, DATA250], ids=lambda d: d.name)


class FakeCuzk:
    """``requests.Session`` stand-in of one dataset: the recorded REST
    answers of the Tesin envelope, the ATOM feeds and the national file
    (``body``; the dataset feed announces its length). ``calls`` = (url,
    params) of every GET; an unknown request fails the test."""

    def __init__(self, data: Dataset, body: bytes = b"") -> None:
        self.data = data
        self.body = body
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None, timeout=None, headers=None, stream=False):
        params = dict(params or {})
        self.calls.append((url, params))
        data = self.data
        if url.startswith(f"{data.service}/"):
            return answer(self._rest(url.removeprefix(f"{data.service}/"), params))
        if url == data.service_feed:
            return answer(FIXTURES / f"{data.name}_service.xml")
        if url == data.dataset_feed:
            feed = FIXTURES / f"{data.name}_dataset.xml"
            recorded = f'length="{data.length}"'.encode()
            served = f'length="{len(self.body)}"'.encode()
            return answer(feed, body=feed.read_bytes().replace(recorded, served))
        if url == data.file:
            size = {"Content-Length": str(len(self.body))}
            return FakeResponse(
                200, {**NATIONAL[data.name]["headers"], **size}, self.body
            )
        raise AssertionError(f"Nieoczekiwane zapytanie: {url} {params}")

    def head(self, url, **_kwargs):
        raise AssertionError(f"HEAD niepotrzebny (rozmiar z feedu): {url}")

    def _rest(self, path: str, params: dict) -> Path:
        layer, _, query = path.partition("/")
        prefix = f"{self.data.name}_l{layer}"
        if not query:
            assert params == {"f": "json"}
            return FIXTURES / f"{prefix}_info.json"
        assert (params["geometry"], params["inSR"]) == (TESIN, "5514")
        if params.get("returnCountOnly") == "true":
            return FIXTURES / f"{prefix}_tesin_count.json"
        assert (params["outSR"], params["resultRecordCount"]) == ("5514", "1")
        return FIXTURES / f"{prefix}_tesin_r1_o{params['resultOffset']}.json.gz"

    def file_gets(self) -> int:
        return sum(1 for url, _ in self.calls if url == self.data.file)


def serve(monkeypatch, data: Dataset, body: bytes = b"") -> FakeCuzk:
    fake = FakeCuzk(data, body)
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


@DATASETS
def test_layers_are_the_object_layers_of_the_service(data):
    """Every object layer of the MapServer service and nothing else (the
    shaded relief rasters of DATA250 are no data); layer code = the CUZK
    name without diacritics (no BDOT10k mapping)."""
    service = json.loads(
        (FIXTURES / f"{data.name}_pjson.json").read_text(encoding="utf-8")
    )
    by_id = {str(layer["id"]): layer for layer in service["layers"]}
    objects = {i for i, layer in by_id.items() if layer["type"] == "Feature Layer"}
    layers = col.collection_layers(data.key)
    assert len(layers) == len(objects) == data.objects
    assert [layer.source for layer in layers] == sorted(objects, key=int)
    for layer in layers:
        assert layer.code == layer.name == _code(by_id[layer.source]["name"])
        assert layer.id_field == "OBJECTID"
    assert len({layer.code for layer in layers}) == data.objects
    rasters = {i for i, layer in by_id.items() if layer["type"] == "Raster Layer"}
    assert rasters == ({"5", "6"} if data is DATA250 else set())
    assert service["maxRecordCount"] == 2000


@DATASETS
def test_bbox_feature_layers(data, monkeypatch, tmp_path):
    """An area in EPSG:4326 is asked as its EPSG:5514 envelope; one GPKG
    table per layer in EPSG:5514, complete against ``returnCountOnly``
    (pages of one object), an empty layer keeps its schema; no cheap signal
    of an area."""
    _page_size(monkeypatch, data.key, 1, sources=set(data.layers))
    fake = serve(monkeypatch, data)
    manager = LandCoverManager(tmp_path, data.name, cache=False)

    result = manager.download(bbox=AREA)

    assert result.ok
    (item,) = result.files
    path = item.file.path
    assert path == tmp_path / f"landcover/cz_{data.name}/bbox/{STORED}.gpkg"
    counts = {
        name: pyogrio.read_info(path, layer=name)["features"]
        for name, _ in pyogrio.list_layers(path)
    }
    assert counts == dict(data.layers.values())
    for name in counts:
        info = pyogrio.read_info(path, layer=name)
        assert info["crs"] == "EPSG:5514" and "OBJECTID" in list(info["fields"])
    meta = _meta(item.file.version_path)
    assert (meta["dataset"], meta["horizontal_crs"]) == (data.key, "EPSG:5514")
    assert meta["request"]["bbox_crs"] == "EPSG:5514"
    assert meta["extra"]["parent_request"] == {
        "bbox": [18.566, 49.757, 18.572, 49.761],
        "bbox_crs": "EPSG:4326",
        "countries": ["CZ"],
    }
    pages = sum(1 for _, params in fake.calls if "resultOffset" in params)
    assert pages == sum(objects for _, objects in data.layers.values())

    fake.calls.clear()
    (planned,) = manager.check(bbox=AREA).items
    assert (planned.track, planned.status) == ("landcover", "unverifiable")
    assert fake.calls == []


@DATASETS
def test_whole_country_crs(data, monkeypatch, tmp_path):
    """The national file exists in EPSG:5514 and EPSG:3045: the choice is
    required before any request. ``check`` reads the edition of the real
    feeds; the size of the feed is announced before the transfer, the ZIP
    is stored 1:1 and labelled by the ``updated`` of its entry."""
    body = zip_bytes(NATIONAL[data.name]["members"])
    fake = serve(monkeypatch, data, body)
    manager = LandCoverManager(tmp_path, data.name, cache=False)
    with pytest.raises(ValidationError, match="wymagane .*: EPSG:5514, EPSG:3045$"):
        manager.download(whole_country=True)
    with pytest.raises(ValidationError, match="EPSG:2180: zbior nie jest publikowany"):
        manager.download(whole_country=True, horizontal_crs="EPSG:2180")
    assert fake.calls == []

    choice = {"whole_country": True, "horizontal_crs": "EPSG:5514"}
    (planned,) = manager.check(**choice).items
    assert (planned.status, planned.available_label) == ("missing", data.label)
    assert fake.file_gets() == 0

    events: list[str] = []
    result = manager.download(**choice, on_notice=lambda n: events.append(n.text))

    (item,) = result.files
    assert (
        item.file.path == tmp_path / f"landcover/cz_{data.name}_shp_5514/country/cz.zip"
    )
    assert (item.file.status, item.file.label) == ("new", data.label)
    assert item.file.path.read_bytes() == body
    assert [n.code for n in result.notices] == [WHOLE_COUNTRY_SIZE]
    assert events == [
        f"{data.name} CZ: plik krajowy {data.file} - {size_text(len(body))}"
    ]
    meta = _meta(item.file.path)
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert meta["request"] == choice
    assert meta["extra"]["source"]["edition"] == data.label
    assert meta["extra"]["version"]["label_source"] == "edition"
    (current,) = manager.check(**choice).items
    assert (current.status, current.local_label) == ("current", data.label)
    assert fake.file_gets() == 1


@DATASETS
def test_area_options(data, monkeypatch, tmp_path):
    """An area is always in the CRS of the service; TERYT units, years and
    classes belong to other sources."""
    fake = serve(monkeypatch, data)
    manager = LandCoverManager(tmp_path, data.name, cache=False)
    for options, message in (
        ({"bbox": AREA, "horizontal_crs": "EPSG:3045"}, "--horizontal-crs"),
        ({"teryt": "12"}, "--teryt dziala tylko z --product bdot10k"),
        ({"bbox": AREA, "year": 2023}, "--year dziala tylko z --product"),
        ({"bbox": AREA, "layers": ["les"]}, "--layers dziala tylko z --product"),
    ):
        with pytest.raises(ValidationError, match=message):
            manager.download(**options)
    assert fake.calls == []
