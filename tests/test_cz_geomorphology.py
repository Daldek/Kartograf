"""CZ geomorphological units: recorded 2026-10-16 ArcGIS REST answers of
``GeomorfologickeJednotky/MapServer`` (service layers, layer 39 ``celek`` at
the Cesky Tesin envelope)."""

import gzip
import json
from pathlib import Path

import pyogrio
import pytest
from pyproj import CRS

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import ValidationError
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams
from tests.test_collections_units import Response, Router

pytestmark = pytest.mark.usefixtures("frozen_clock")

FIXTURES = Path(__file__).parent / "fixtures/cz/geomorphology/real_2026_10_16"
SERVICE = (
    "https://ags.cuzk.gov.cz/arcgis/rest/services/GeomorfologickeJednotky/MapServer"
)
TESIN = BBox(-452000, -1112000, -450000, -1110000, "EPSG:5514")
LEVELS = "subprovincie, oblast, celek, podcelek, okrsek, podokrsek, cast"


@pytest.fixture
def service(monkeypatch) -> Router:
    fake = Router()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _answer(name: str):
    path = FIXTURES / name
    recorded = path.with_name(f"{name.removesuffix('.gz')}.headers.json")
    meta = json.loads(recorded.read_text())
    body = path.read_bytes()
    if path.suffix == ".gz":
        body = gzip.decompress(body)
    headers = {k: v for k, v in meta.items() if k not in ("status", "url")}
    return lambda: Response(meta["status"], headers, body)


def serve_celek(router: Router) -> None:
    """Layer 39 at the Tesin envelope: metadata, count and the one page."""
    area = {
        "geometry": "-452000,-1112000,-450000,-1110000",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "5514",
        "spatialRel": "esriSpatialRelIntersects",
    }
    router.add(f"{SERVICE}/39", _answer("layer_39.json"), {"f": "json"})
    router.add(
        f"{SERVICE}/39/query",
        _answer("layer_39_tesin_count.json"),
        {**area, "returnCountOnly": "true", "f": "json"},
    )
    router.add(
        f"{SERVICE}/39/query",
        _answer("layer_39_tesin_r1000_o0.json.gz"),
        {
            **area,
            "outSR": "5514",
            "outFields": "*",
            "orderByFields": "OBJECTID",
            "resultOffset": "0",
            "resultRecordCount": "1000",
            "returnGeometry": "true",
            "f": "geojson",
        },
    )


def test_geomorphology_levels_are_the_feature_layers_of_the_service():
    """Each --level is one top-level polygon layer of the published service,
    coarse to fine; the annotation (0-21) and relief mosaic (22-25) layers
    are never part of the product."""
    service = json.loads((FIXTURES / "service.json").read_text(encoding="utf-8"))
    names = {str(layer["id"]): layer["name"] for layer in service["layers"]}
    data = {
        str(layer["id"])
        for layer in service["layers"]
        if layer["type"] == "Feature Layer" and layer["parentLayerId"] == -1
    }
    channel = registry.get_source("cz.cuzk.geomorphology").channels[0]
    assert isinstance(channel.params, FeatureBBoxParams)
    layers = channel.params.layers
    assert {layer.source for layer in layers} == data
    assert [(layer.code, names[layer.source]) for layer in layers] == [
        ("subprovincie", "GJ_01_subprovincie"),
        ("oblast", "GJ_02_oblasti"),
        ("celek", "GJ_03_celek"),
        ("podcelek", "GJ_04_podcelek"),
        ("okrsek", "GJ_05_okrsek"),
        ("podokrsek", "GJ_06_podokrsek"),
        ("cast", "GJ_07_casti"),
    ]


def test_geomorphology_level_required(tmp_path):
    with pytest.raises(ValidationError, match=f"--level wymagane .*: {LEVELS}$"):
        validate_collection_request(
            product="geomorphology", country="cz", bbox=TESIN, output_dir=tmp_path
        )
    with pytest.raises(ValidationError, match=f"--level gmina: .*dostepne: {LEVELS}"):
        validate_collection_request(
            product="geomorphology",
            country="cz",
            bbox=TESIN,
            level="gmina",
            output_dir=tmp_path,
        )
    with pytest.raises(ValidationError, match="tylko dla CZ"):
        validate_collection_request(
            product="geomorphology",
            country="pl",
            bbox=BBox(566000, 243000, 567000, 244000, "EPSG:2180"),
            level="celek",
            output_dir=tmp_path,
        )


def test_geomorphology_celek_asks_only_layer_39(tmp_path, service):
    """``--level celek``: one GeoPackage layer from layer 39 in EPSG:5514; no
    other layer of the service is asked."""
    serve_celek(service)

    report = download_collection(
        product="geomorphology",
        country="cz",
        bbox=TESIN,
        level="celek",
        output_dir=tmp_path,
        cache=False,
    )

    assert report.ok, report.failed
    (item,) = report.files
    assert item.file.path == (
        tmp_path
        / "boundaries/cz_geomorphology_celek/bbox"
        / "-452000_-1112000_-450000_-1110000.gpkg"
    )
    info = pyogrio.read_info(item.file.path, layer="celek")
    assert info["features"] == 1
    assert CRS.from_user_input(info["crs"]).to_epsg() == 5514
    meta, _, _, values = pyogrio.raw.read(
        item.file.path, layer="celek", read_geometry=False
    )
    assert list(values[list(meta["fields"]).index("CELEK_P")]) == [
        "Podbeskydská pahorkatina"
    ]
    sidecar = json.loads(Path(f"{item.file.version_path}.meta.json").read_text())
    assert sidecar["dataset"] == "cz.cuzk.geomorphology"
    assert {url for _, url in service.calls} == {
        f"{SERVICE}/39",
        f"{SERVICE}/39/query",
    }
    assert service.gets() == 3
