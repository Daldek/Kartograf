"""Geographic names: real PRNG API pages, world extent and PRNG national themes."""

import dataclasses
import json
from pathlib import Path

import pyogrio
import pytest
from pyproj import CRS

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    check_collection,
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import ValidationError
from kartograf.notices import SLOW_SOURCE, WHOLE_COUNTRY_SIZE
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams
from tests.fake_packages import FakePackageSession, zip_bytes
from tests.test_collections_units import FILES, Response, Router
from tests.test_feature_bbox import FakeService, prng

pytestmark = pytest.mark.usefixtures("frozen_clock")
WORLD = Path(__file__).parent / "fixtures/pl/prng_world/real_2026_10_16/new_york.json"
COLLECTIONS = Path(__file__).parent / "fixtures/pl/feature_bbox/prng_collections.json"
GEONAMES = Path(__file__).parent / "fixtures/cz/geonames/real_2026_10_16"
CZ_BBOX = BBox(-452000, -1112000, -450000, -1110000, "EPSG:5514")


def _prng_page_size(monkeypatch, page_size: int) -> None:
    descriptor = registry.get_source("pl.gugik.prng")
    channel = descriptor.channels[0]
    assert isinstance(channel.params, FeatureBBoxParams)
    selected = dataclasses.replace(
        channel, params=dataclasses.replace(channel.params, page_size=page_size)
    )
    monkeypatch.setitem(
        registry._SOURCES,
        descriptor.key,
        dataclasses.replace(descriptor, channels=(selected, *descriptor.channels[1:])),
    )


def test_prng_bbox_paging_to_one_geopackage(tmp_path, monkeypatch):
    """Two recorded API pages produce nine distinct named places in CRS84."""
    _prng_page_size(monkeypatch, 5)
    session = FakeService(prng())
    monkeypatch.setattr(col, "_session", lambda: session)
    report = download_collection(
        product="geographic",
        country="pl",
        bbox=BBox(19.93, 50.055, 19.945, 50.065, "EPSG:4326"),
        output_dir=tmp_path,
        cache=False,
    )
    assert report.ok, report.failed
    (item,) = report.files
    assert item.file.path.stem.startswith("19.93_50.055_19.945_50.065")
    info = pyogrio.read_info(item.file.path, layer="prng")
    assert info["features"] == 9
    assert CRS.from_wkt(info["crs"]).to_authority() == ("OGC", "CRS84")
    assert len([url for url, _ in session.calls if "/items" in url]) == 2


def test_prng_area_announces_slow_service(tmp_path, monkeypatch):
    """Live test 0.8.0: PRNG answered 9 objects in 88-92 s without a word.
    The area request says so (``Info``, measured time) before the query."""
    _prng_page_size(monkeypatch, 5)
    session = FakeService(prng())
    monkeypatch.setattr(col, "_session", lambda: session)
    seen: list[tuple[str, int]] = []
    report = download_collection(
        product="geographic",
        country="pl",
        bbox=BBox(19.93, 50.055, 19.945, 50.065, "EPSG:4326"),
        output_dir=tmp_path,
        cache=False,
        on_notice=lambda n: seen.append((n.code, len(session.calls))),
    )
    assert report.ok, report.failed
    (notice,) = [n for n in report.notices if n.code == SLOW_SOURCE]
    assert notice.level == "info"
    assert notice.text.startswith("geographic: zapytanie OGC API PRNG - usluga ")
    assert "80-95 s" in notice.text
    # announced before the first page of items
    calls_then = dict(seen)[SLOW_SOURCE]
    assert not any("/items" in url for url, _ in session.calls[:calls_then])


def test_prng_pl1992_bbox_uses_lonlat_query(tmp_path):
    """An EPSG:2180 area becomes the CRS84 service bbox."""
    area = BBox(565950, 243950, 566050, 244050, "EPSG:2180")
    request = validate_collection_request(
        product="geographic", country="pl", bbox=area, output_dir=tmp_path
    )
    part = request.parts[0]
    assert part.area is not None
    assert part.area.crs == "OGC:CRS84"
    assert 19 < part.area.min_x < part.area.max_x < 21
    assert 49 < part.area.min_y < part.area.max_y < 51


def test_prng_whole_country_two_themes(tmp_path, monkeypatch):
    """The GML export contains both national datasets and size notices before GET."""
    entries = (FILES["prng_miejscowosci_gml"], FILES["prng_obiekty_gml"])
    routes = {}
    heads = {}
    for entry in entries:
        url = entry["url"]
        body = zip_bytes(entry["members"])
        routes[url] = (
            200,
            {**entry["headers"], "Content-Length": str(len(body))},
            body,
        )
        heads[url] = entry["headers"]
    session = FakePackageSession(routes, heads)
    monkeypatch.setattr(col, "_session", lambda: session)
    report = download_collection(
        product="geographic",
        country="pl",
        whole_country=True,
        format="GML",
        output_dir=tmp_path,
        cache=False,
    )
    assert report.ok, report.failed
    assert {item.unit for item in report.files} == {
        "pl_miejscowosci",
        "pl_obiekty-fizjograficzne",
    }
    assert {item.file.path.name for item in report.files} == {
        "pl_miejscowosci.zip",
        "pl_obiekty-fizjograficzne.zip",
    }
    assert len([n for n in report.notices if n.code == WHOLE_COUNTRY_SIZE]) == 2
    assert [method for method, _ in session.calls] == ["HEAD", "GET"] * 2
    with pytest.raises(ValidationError, match="dokladnie jeden wybor"):
        validate_collection_request(product="geographic", output_dir=tmp_path)


def test_world_bbox_outside_poland_and_national_file(tmp_path, monkeypatch):
    """The source country PL does not clip world names to Polish coordinates."""
    url = "https://ogcapi.geoportal.gov.pl/res/ims/maps/PRNG/apiFeatures"
    bbox = BBox(-74.02, 40.69, -73.92, 40.79, "EPSG:4326")
    session = Router()
    session.add(
        f"{url}/collections",
        lambda: Response(
            200, {"Content-Type": "application/json"}, COLLECTIONS.read_bytes()
        ),
        {"f": "json"},
    )
    session.add(
        f"{url}/collections/PolskaNazwaGeograficznaSwiata/items",
        lambda: Response(200, {"Content-Type": "application/json"}, WORLD.read_bytes()),
        {"f": "json", "bbox": "-74.02,40.69,-73.92,40.79", "limit": "10000"},
    )
    monkeypatch.setattr(col, "_session", lambda: session)
    report = download_collection(
        product="world", country="pl", bbox=bbox, output_dir=tmp_path, cache=False
    )
    assert report.ok, report.failed
    assert (
        pyogrio.read_info(report.files[0].file.path, layer="prng_world")["features"]
        == 7
    )
    meta = json.loads(
        Path(f"{report.files[0].file.version_path}.meta.json").read_text()
    )
    assert meta["request"]["bbox_crs"] == "OGC:CRS84"
    assert session.gets(f"{url}/collections/PolskaNazwaGeograficznaSwiata/items") == 1
    with pytest.raises(ValidationError, match="tylko dla PL"):
        check_collection(product="world", country="cz", bbox=bbox, output_dir=tmp_path)
    national = validate_collection_request(
        product="world",
        country="pl",
        whole_country=True,
        format="SHP",
        output_dir=tmp_path,
    )
    assert national.parts[0].segment == "names/pl_prng_world_shp"


def _geonames_first_layer(monkeypatch) -> None:
    """Restrict the recorded query to its published layer 0 (of 25)."""
    descriptor = registry.get_source("cz.cuzk.geonames")
    channel = descriptor.channels[0]
    assert isinstance(channel.params, FeatureBBoxParams)
    first = dataclasses.replace(
        channel,
        params=dataclasses.replace(
            channel.params, layers=channel.params.layers[:1], page_size=1
        ),
    )
    monkeypatch.setitem(
        registry._SOURCES,
        descriptor.key,
        dataclasses.replace(descriptor, channels=(first, *descriptor.channels[1:])),
    )


def _geonames_session() -> Router:
    """Recorded layer 0 metadata, count and GeoJSON at a Czech bbox."""
    session = Router()
    url = "https://ags.cuzk.gov.cz/arcgis/rest/services/GEONAMES/Geonames/MapServer/0"

    def answer(name: str):
        return lambda: Response(
            200, {"Content-Type": "application/json"}, (GEONAMES / name).read_bytes()
        )

    session.add(url, answer("layer_0.json"), {"f": "json"})
    area = {
        "geometry": "-452000,-1112000,-450000,-1110000",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "5514",
        "spatialRel": "esriSpatialRelIntersects",
    }
    session.add(
        f"{url}/query",
        answer("layer_0_count.json"),
        {**area, "returnCountOnly": "true", "f": "json"},
    )
    session.add(
        f"{url}/query",
        answer("layer_0_page0.json"),
        {
            **area,
            "outSR": "5514",
            "outFields": "*",
            "orderByFields": "OBJECTID",
            "resultOffset": "0",
            "resultRecordCount": "1",
            "returnGeometry": "true",
            "f": "geojson",
        },
    )
    return session


def test_geonames_area_rest_to_geopackage(tmp_path, monkeypatch):
    """A named Czech object keeps the native EPSG:5514 and source attributes."""
    _geonames_first_layer(monkeypatch)
    session = _geonames_session()
    monkeypatch.setattr(col, "_session", lambda: session)
    report = download_collection(
        product="geographic",
        country="cz",
        bbox=CZ_BBOX,
        output_dir=tmp_path,
        cache=False,
    )
    assert report.ok, report.failed
    path = report.files[0].file.path
    assert pyogrio.read_info(path, layer="mesta_obce")["features"] == 1
    assert (
        CRS.from_user_input(
            pyogrio.read_info(path, layer="mesta_obce")["crs"]
        ).to_epsg()
        == 5514
    )
    meta = json.loads(
        Path(f"{report.files[0].file.version_path}.meta.json").read_text()
    )
    assert meta["dataset"] == "cz.cuzk.geonames"
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert session.gets() == 3


def test_geonames_missing_published_layer_fails_download(tmp_path, monkeypatch):
    """A removed service layer must not silently produce an incomplete GPKG."""
    _geonames_first_layer(monkeypatch)
    session = _geonames_session()
    layer = "https://ags.cuzk.gov.cz/arcgis/rest/services/GEONAMES/Geonames/MapServer/0"
    session.add(layer, lambda: Response(404, {}, b"not found"), {"f": "json"})
    monkeypatch.setattr(col, "_session", lambda: session)
    report = download_collection(
        product="geographic",
        country="cz",
        bbox=CZ_BBOX,
        output_dir=tmp_path,
        cache=False,
    )
    assert report.files == ()
    assert len(report.failed) == 1
    assert report.failed[0].kind == "download"
    assert not report.ok


def test_geonames_atom_requires_crs_and_uses_published_edition(tmp_path, monkeypatch):
    """The two actual ATOM feeds choose the requested CRS before file transfer."""
    options = {
        "product": "geographic",
        "country": "cz",
        "whole_country": True,
        "format": "GPKG",
        "output_dir": tmp_path,
    }
    with pytest.raises(ValidationError, match="EPSG:5514, EPSG:3045"):
        validate_collection_request(**options)
    feed = "https://atom.cuzk.gov.cz/GEONAMES-GPKG/GEONAMES-GPKG.xml"
    dataset = (
        "https://atom.cuzk.gov.cz/GEONAMES-GPKG/datasetFeeds/"
        "CZ-00025712-CUZK_GEONAMES-GPKG_1.xml"
    )
    session = FakePackageSession(
        {
            feed: (
                200,
                {"Content-Type": "application/atom+xml"},
                (GEONAMES / "service.xml").read_bytes(),
            ),
            dataset: (
                200,
                {"Content-Type": "application/atom+xml"},
                (GEONAMES / "dataset.xml").read_bytes(),
            ),
        }
    )
    monkeypatch.setattr(col, "_session", lambda: session)
    plan = check_collection(**options, horizontal_crs="EPSG:5514", cache=False)
    (item,) = plan.items
    assert item.status == "missing"
    assert item.available_label == "2026-09-30"
    assert item.segment == "names/cz_geonames_gpkg_5514"
    assert session.calls == [("GET", feed), ("GET", dataset)]
