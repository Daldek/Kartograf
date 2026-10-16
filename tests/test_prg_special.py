"""PRG special boundaries: recorded 2026-10-16 OGC API answers and ZIP HEADs.

The area test limits the descriptor to one real collection (SadRejonowy), as
querying all 45 collections would need 45 recorded item responses per area.
The catalog test verifies the complete set independently of this small area.
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
from kartograf.notices import WHOLE_COUNTRY_SIZE
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


class SpecialService:
    def __init__(self, catalog=CATALOG):
        self.catalog = catalog
        self.calls: list[str] = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        if url == f"{FEATURE.endpoint}/collections":
            body = json.dumps(self.catalog).encode()
            return recorded_response(FIXTURES / "collections.json", body=body)
        if url == f"{FEATURE.endpoint}/collections/SadRejonowy/items":
            assert params == {
                "f": "json",
                "bbox": "19.93,50.055,19.945,50.065",
                "limit": "10000",
            }
            return recorded_response(FIXTURES / "sad_rejonowy.json")
        raise AssertionError(f"Unexpected OGC API request: {url}")


def test_special_collections_contract(tmp_path):
    """No administrative collection is fetched; a missing special collection
    fails with its name before asking for any item."""
    layers = FEATURE.params.layers
    published = {entry["id"] for entry in CATALOG["collections"]}
    assert len(layers) == 45
    assert {layer.source for layer in layers} == published - {
        "GranicaPanstwa",
        "GranicaWojewodztwa",
        "GranicaPowiatu",
        "GranicaGminy",
        "GranicaJednostkiEwidencyjnej",
        "GranicaObrebuEwidencyjnego",
    }
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


@pytest.mark.parametrize(
    "format,suffix,member",
    [
        ("SHP", "shp", "SadRejonowy.shp"),
        ("GML", "xml", "SadRejonowy.gml"),
    ],
)
def test_special_country_package(
    tmp_path, monkeypatch, frozen_clock, format, suffix, member
):
    """Published national ZIP and sidecar follow the selected source format;
    the recorded >100 MiB HEAD is announced before any GET."""
    source = PACKAGES[suffix]
    url = source["url"]
    body = zip_bytes([member])
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
