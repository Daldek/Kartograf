"""PRG address points and streets: recorded 2026-10-16 answers of the KIN WFS
(GeoServer, N,E axes) and the heads and member lists of the packages
(``tests/fixtures/pl/prg_addresses/real_2026_10_16``). Package bodies are
small ZIPs built from the real member names."""

import dataclasses
import json
from pathlib import Path

import pyogrio
import pyogrio.raw
import pytest
from pyproj import CRS

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import ValidationError
from kartograf.notices import WHOLE_COUNTRY_SIZE
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams
from tests.integration.test_collections_units import Router
from tests.support.fake_packages import FakePackageSession, zip_bytes

pytestmark = pytest.mark.usefixtures("frozen_clock")

FIXTURES = Path(__file__).parent.parent / "fixtures/pl/prg_addresses/real_2026_10_16"
FILES: dict = json.loads((FIXTURES / "files.json").read_text(encoding="utf-8"))
SOURCE = registry.get_source("pl.gugik.prg_addresses")
# Krakow, E 567100-567150 / N 244150-244200: 3 address points, 2 streets
AREA = BBox(567100, 244150, 567150, 244200, "EPSG:2180")
URN = "urn:ogc:def:crs:EPSG::2180"


class KinWfs(Router):
    """The recorded KIN answers, each for its exact query; ``params`` = the
    query of every GET in order."""

    def __init__(self) -> None:
        super().__init__()
        self.params: list[dict] = []
        for path in sorted(FIXTURES.iterdir()):
            if path.suffix in (".xml", ".xsd"):
                self.add_recorded(path)

    def get(self, url, params=None, timeout=None, **kwargs):
        self.params.append(dict(params or {}))
        return super().get(url, params=params, timeout=timeout, **kwargs)


def serve_kin(monkeypatch) -> KinWfs:
    """The recorded KIN WFS as the orchestrator's session; the WFS channel
    pages by the recorded ``COUNT=2`` (the registry asks for 1000)."""
    channels = tuple(
        dataclasses.replace(ch, params=dataclasses.replace(ch.params, page_size=2))
        if isinstance(ch.params, FeatureBBoxParams)
        else ch
        for ch in SOURCE.channels
    )
    monkeypatch.setitem(
        registry._SOURCES, SOURCE.key, dataclasses.replace(SOURCE, channels=channels)
    )
    service = KinWfs()
    monkeypatch.setattr(col, "_session", lambda: service)
    return service


@pytest.fixture
def kin(monkeypatch) -> KinWfs:
    return serve_kin(monkeypatch)


def _package(key: str) -> tuple[str, FakePackageSession]:
    """The file of ``files.json`` as a small ZIP of its real members; ``HEAD``
    gives the recorded headers (real size)."""
    entry = FILES[key]
    body = zip_bytes(entry["members"])
    headers = {**entry["headers"], "Content-Length": str(len(body))}
    session = FakePackageSession(
        {entry["url"]: (200, headers, body)}, heads={entry["url"]: entry["headers"]}
    )
    return entry["url"], session


def test_addresses_area_asks_north_east_and_writes_two_layers(tmp_path, kin):
    """An area of Krakow: every GetFeature has the envelope N,E (EPSG:2180
    axis order of the GeoServer; the same envelope sent E,N matches nothing,
    recorded hits 0); one GeoPackage with the address points and the
    streets crossing the area, in EPSG:2180."""
    report = download_collection(
        product="addresses", country="pl", bbox=AREA, output_dir=tmp_path, cache=False
    )

    assert report.ok, report.failed
    (item,) = report.files
    assert item.file.path == (
        tmp_path / "boundaries/pl_prg_addresses/bbox/567100_244150_567150_244200.gpkg"
    )
    counts = {
        name: pyogrio.read_info(item.file.path, layer=name)["features"]
        for name, _ in pyogrio.list_layers(item.file.path)
    }
    assert counts == {"punkty_adresowe": 3, "ulice": 2}
    info = pyogrio.read_info(item.file.path, layer="punkty_adresowe")
    assert CRS.from_user_input(info["crs"]).to_epsg() == 2180
    assert info["geometry_type"] == "MultiPoint"  # the writer promotes to multi
    meta, _, _, values = pyogrio.raw.read(
        item.file.path, layer="punkty_adresowe", read_geometry=False
    )
    ids = values[list(meta["fields"]).index("gml_id")]
    assert list(ids) == [
        "A07_Punkty_adresowe.3941826",
        "A07_Punkty_adresowe.3942580",
        "A07_Punkty_adresowe.3942581",
    ]
    envelopes = {p["BBOX"] for p in kin.params if p.get("REQUEST") == "GetFeature"}
    assert envelopes == {f"244150,567100,244200,567150,{URN}"}
    sidecar = json.loads(Path(f"{item.file.version_path}.meta.json").read_text())
    assert sidecar["dataset"] == SOURCE.key
    assert sidecar["horizontal_crs"] == "EPSG:2180"
    assert [layer["features"] for layer in sidecar["extra"]["source"]["layers"]] == [
        3,
        2,
    ]


def test_addresses_powiat_package_is_stored_as_published(tmp_path, monkeypatch):
    """``--teryt 1261``: the SHP package of the powiat, ZIP 1:1 (points,
    streets, squares, localities); a second run uses the local version."""
    url, session = _package("powiat_1261")
    monkeypatch.setattr(col, "_session", lambda: session)
    request = dict(product="addresses", teryt="1261", output_dir=tmp_path, cache=False)

    report = download_collection(**request)

    assert report.ok, report.failed
    (item,) = report.files
    assert item.file.path == tmp_path / "boundaries/pl_prg_addresses_shp/teryt/1261.zip"
    sidecar = json.loads(Path(f"{item.file.version_path}.meta.json").read_text())
    assert sidecar["request"] == {"teryt": "1261"}
    assert sidecar["dataset"] == SOURCE.key
    assert session.calls == [("HEAD", url), ("GET", url)]
    assert download_collection(**request).files[0].file.status == "local"
    assert session.gets() == 1


def test_addresses_selections_named_before_any_request(tmp_path):
    """GUGiK publishes powiat packages only (the voivodeship URL is 404):
    ``--teryt 12`` names the selections the product has; a national file
    needs ``--format``; ``--format`` belongs to the national file only."""
    with pytest.raises(ValidationError) as voivodeship:
        validate_collection_request(
            product="addresses", teryt="12", output_dir=tmp_path
        )
    assert str(voivodeship.value).startswith(
        "--teryt 12: addresses nie ma paczek wojewodztw; dostepne: "
    )
    assert "--teryt <4 cyfry> (paczka powiatu)" in str(voivodeship.value)
    with pytest.raises(ValidationError, match="--format wymagane: SHP, GML$"):
        validate_collection_request(
            product="addresses", country="pl", whole_country=True, output_dir=tmp_path
        )
    with pytest.raises(ValidationError, match="--format"):
        validate_collection_request(
            product="addresses",
            country="pl",
            bbox=AREA,
            format="SHP",
            output_dir=tmp_path,
        )


@pytest.mark.parametrize(
    ("key", "fmt", "segment"),
    [
        ("country_shp", "SHP", "pl_prg_addresses_shp"),
        ("country_gml", "GML", "pl_prg_addresses_gml"),
    ],
)
def test_addresses_national_file_size_before_transfer(
    tmp_path, monkeypatch, key, fmt, segment
):
    """``--whole-country --format``: the recorded size of the national file
    (SHP ``POLSKA.zip``, GML ``PRG-punkty_adresowe.zip`` with 16 voivodeship
    GML files) is announced before the GET; the ZIP is stored 1:1."""
    url, session = _package(key)
    monkeypatch.setattr(col, "_session", lambda: session)
    seen = []

    report = download_collection(
        product="addresses",
        country="pl",
        whole_country=True,
        format=fmt,
        output_dir=tmp_path,
        cache=False,
        on_notice=lambda notice: seen.append((notice.code, session.gets(url))),
    )

    assert report.ok, report.failed
    assert seen == [(WHOLE_COUNTRY_SIZE, 0)]
    assert f"{FILES[key]['headers']['Content-Length']} B" in report.notices[0].text
    (item,) = report.files
    assert item.file.path == tmp_path / f"boundaries/{segment}/country/pl.zip"
    sidecar = json.loads(Path(f"{item.file.version_path}.meta.json").read_text())
    assert sidecar["request"] == {"whole_country": True, "format": fmt}
    assert session.calls == [("HEAD", url), ("GET", url)]
