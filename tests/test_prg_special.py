"""PRG special boundaries: recorded 2026-10-16 OGC API answers and ZIP HEADs.

The area tests answer the real collection catalog, the recorded court
polygon (SadRejonowy) and, for every other collection, the recorded answer
of a collection without objects in the area (KomendaStolecznaPolicji) -
one recorded item response per collection is 43 more responses per area.
"""

import json
from dataclasses import replace
from pathlib import Path

import pyogrio
import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import AREA_OMITTED, WHOLE_COUNTRY_SIZE
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams
from kartograf.transport.feature_bbox import fetch_features
from tests.conftest import recorded_response
from tests.fake_packages import FakePackageSession, zip_bytes

FIXTURES = Path(__file__).parent / "fixtures" / "pl" / "prg_special"
BBOX = BBox(19.93, 50.055, 19.945, 50.065, "EPSG:4326")
SOURCE = registry.get_source("pl.gugik.prg_special")
FEATURE = SOURCE.channels[0]
assert isinstance(FEATURE.params, FeatureBBoxParams)
CATALOG = json.loads((FIXTURES / "collections.json").read_text(encoding="utf-8"))
PACKAGES = json.loads((FIXTURES / "packages.json").read_text(encoding="utf-8"))
# administrative boundaries (plan C, product admin) and the census districts
# (the service answers an area in minutes; national file only)
ADMIN = {
    "GranicaPanstwa",
    "GranicaWojewodztwa",
    "GranicaPowiatu",
    "GranicaGminy",
    "GranicaJednostkiEwidencyjnej",
    "GranicaObrebuEwidencyjnego",
}
CENSUS = "GranicaObwoduSpisowego"


class SpecialService:
    def __init__(self, catalog=CATALOG, *, empty_others: bool = False):
        self.catalog = catalog
        self.empty_others = empty_others
        self.calls: list[str] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        if url == f"{FEATURE.endpoint}/collections":
            body = json.dumps(self.catalog).encode()
            return recorded_response(FIXTURES / "collections.json", body=body)
        items = {"f": "json", "bbox": "19.93,50.055,19.945,50.065", "limit": "10000"}
        if url == f"{FEATURE.endpoint}/collections/SadRejonowy/items":
            assert params == items
            return recorded_response(FIXTURES / "sad_rejonowy.json")
        if self.empty_others and url.endswith("/items"):
            assert params == items
            return recorded_response(FIXTURES / "komenda_stoleczna_empty.json")
        raise AssertionError(f"Unexpected OGC API request: {url}")


def test_special_collections_contract(tmp_path):
    """No administrative collection and no census district collection is
    fetched; a missing special collection fails with its name before asking
    for any item."""
    layers = FEATURE.params.layers
    published = {entry["id"] for entry in CATALOG["collections"]}
    assert len(layers) == 44
    assert {layer.source for layer in layers} == published - ADMIN - {CENSUS}
    omitted = next(layer for layer in layers if layer.source == "UrzadSkarbowy")
    service = SpecialService(
        {
            "collections": [
                c for c in CATALOG["collections"] if c["id"] != omitted.source
            ]
        }
    )
    with pytest.raises(DownloadError, match=omitted.source):
        fetch_features(
            service,
            FEATURE.endpoint,
            FEATURE.params,
            layers,
            BBOX._replace(crs="OGC:CRS84"),
            tmp_path,
            timeout=10,
        )
    assert service.calls == [f"{FEATURE.endpoint}/collections"]


def test_special_area_creates_versioned_gpkg(tmp_path, monkeypatch, frozen_clock):
    """Recorded court polygon becomes a real CRS84 GeoPackage in the bbox slot."""
    court = next(
        layer for layer in FEATURE.params.layers if layer.source == "SadRejonowy"
    )
    descriptor = replace(
        SOURCE,
        channels=(replace(FEATURE, params=replace(FEATURE.params, layers=(court,))),)
        + SOURCE.channels[1:],
    )
    monkeypatch.setitem(registry._SOURCES, SOURCE.key, descriptor)
    service = SpecialService()
    monkeypatch.setattr(col, "_session", lambda: service)
    request = dict(
        product="special", output_dir=tmp_path, country="pl", bbox=BBOX, cache=False
    )

    report = download_collection(**request)

    assert report.ok, report.failed
    (unit_file,) = report.files
    path = unit_file.file.path
    assert (
        path
        == tmp_path / "boundaries/pl_prg_special/bbox/19.93_50.055_19.945_50.065.gpkg"
    )
    info = pyogrio.read_info(path, layer="SadRejonowy", force_total_bounds=True)
    assert info["features"] == 1
    assert "CRS84" in str(info["crs"])
    assert info["geometry_type"] == "MultiPolygon"
    assert "powierzchnia" in info["fields"]
    meta = json.loads(Path(f"{unit_file.file.version_path}.meta.json").read_text())
    assert meta["dataset"] == SOURCE.key
    assert meta["horizontal_crs"] == "OGC:CRS84"
    assert meta["request"]["bbox"] == [19.93, 50.055, 19.945, 50.065]
    assert meta["extra"]["source"]["layers"][0]["features"] == 1
    assert service.calls == [
        f"{FEATURE.endpoint}/collections",
        f"{FEATURE.endpoint}/collections/SadRejonowy/items",
    ]
    again = download_collection(**request)
    assert again.files[0].file.status == "local"
    assert len(service.calls) == 2


def test_special_area_leaves_out_census_districts(tmp_path, monkeypatch, frozen_clock):
    """The area result has the 44 collections of the descriptor: the census
    districts (the service answered a small area in 158 s to over 400 s on
    2026-10-16) are never asked, and the result says so with an ``Info``
    naming the national file that has them."""
    service = SpecialService(empty_others=True)
    monkeypatch.setattr(col, "_session", lambda: service)
    notices = []

    report = download_collection(
        product="special",
        output_dir=tmp_path,
        country="pl",
        bbox=BBOX,
        cache=False,
        on_notice=notices.append,
    )

    assert report.ok, report.failed
    asked = {url.split("/")[-2] for url in service.calls if url.endswith("/items")}
    assert asked == {layer.source for layer in FEATURE.params.layers}
    assert CENSUS not in asked
    path = report.files[0].file.path
    layers = [name for name, _ in pyogrio.list_layers(path)]
    assert len(layers) == 44 and CENSUS not in layers
    assert pyogrio.read_info(path, layer="SadRejonowy")["features"] == 1
    (omitted,) = [n for n in report.notices if n.code == AREA_OMITTED]
    assert omitted.level == "info"
    assert omitted.text.startswith("special: wynik obszaru bez obwodow spisowych")
    assert CENSUS in omitted.text and "--whole-country" in omitted.text
    assert notices == list(report.notices)


def test_special_requires_selection_and_explicit_country_format(tmp_path):
    with pytest.raises(ValidationError, match="--bbox"):
        validate_collection_request(product="special", output_dir=tmp_path)
    with pytest.raises(ValidationError, match="--format wymagane.*SHP, GML"):
        validate_collection_request(
            product="special",
            output_dir=tmp_path,
            country="pl",
            whole_country=True,
        )
    with pytest.raises(ValidationError, match="--format"):
        validate_collection_request(
            product="special",
            output_dir=tmp_path,
            country="pl",
            bbox=BBOX,
            format="SHP",
        )


@pytest.mark.parametrize(("format", "suffix"), [("SHP", "shp"), ("GML", "xml")])
def test_special_country_package(tmp_path, monkeypatch, frozen_clock, format, suffix):
    """Published national ZIP (its real member names: 45 kinds incl. the
    census districts R02) and sidecar follow the selected source format;
    the recorded >100 MiB HEAD is announced before any GET."""
    source = PACKAGES[suffix]
    url = source["url"]
    body = zip_bytes(source["members"])
    fake = FakePackageSession(
        {
            url: (
                200,
                {
                    "Content-Type": source["content_type"],
                    "Content-Length": str(len(body)),
                },
                body,
            )
        },
        heads={url: {"Content-Length": str(source["length"])}},
    )
    monkeypatch.setattr(col, "_session", lambda: fake)
    seen = []

    def observe(notice):
        seen.append((notice.code, fake.gets(url)))

    report = download_collection(
        product="special",
        output_dir=tmp_path,
        country="pl",
        whole_country=True,
        format=format,
        cache=False,
        on_notice=observe,
    )

    assert report.ok, report.failed
    assert seen[0] == (WHOLE_COUNTRY_SIZE, 0)
    assert str(source["length"]) in report.notices[0].text
    assert fake.calls == [("HEAD", url), ("GET", url)]
    (unit_file,) = report.files
    assert unit_file.file.path == (
        tmp_path / f"boundaries/pl_prg_special_{format.lower()}/country/pl.zip"
    )
    meta = json.loads(Path(f"{unit_file.file.version_path}.meta.json").read_text())
    assert meta["request"] == {"whole_country": True, "format": format}
    assert meta["dataset"] == SOURCE.key
