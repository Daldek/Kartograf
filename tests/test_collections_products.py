"""Products of plan C on the collection orchestrator (ADR-042 D5, D8, D11).

Area results run the real ``feature_bbox`` engine and GPKG writer on the
recorded WFS answers of ``tests/fixtures/pl/feature_bbox`` (PRG A06 obreby
in Krakow, EGiB parcels and buildings of powiat 1415); only the HTTP session
is replaced.
"""

import json
from dataclasses import replace
from pathlib import Path

import pyogrio
import pytest

from kartograf.download import collections as col
from kartograf.download.collections import download_collection
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams
from tests.conftest import recorded_response
from tests.test_feature_bbox import (
    A06,
    EGIB_ENDPOINT,
    EGIB_RURAL,
    EGIB_RURAL_BBOX,
    FIXTURES,
    PRG_A06,
    PRG_BBOX,
    PRG_ENDPOINT,
    FakeService,
    wfs,
)


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


def _serve(monkeypatch, service: FakeService) -> FakeService:
    monkeypatch.setattr(col, "_session", lambda: service)
    return service


@pytest.fixture
def prg_pages_of_two(monkeypatch):
    """The PRG WFS channel with ``page_size`` = the ``COUNT=2`` of the
    recorded pages (the registry asks for 1000 per page)."""
    descriptor = registry.get_source("pl.gugik.prg")
    channels = tuple(
        replace(channel, params=replace(channel.params, page_size=2))
        if isinstance(channel.params, FeatureBBoxParams)
        else channel
        for channel in descriptor.channels
    )
    monkeypatch.setitem(
        registry._SOURCES, descriptor.key, replace(descriptor, channels=channels)
    )


# --- PRG: --level of an area -----------------------------------------------------


def test_prg_level_to_layer(tmp_path, monkeypatch, frozen_clock, prg_pages_of_two):
    """``--level obreb`` asks only the A06 type and gives one GPKG layer of
    it, with the TERYT fields of PRG, in the slot of that level."""
    service = _serve(
        monkeypatch, FakeService(wfs("prg_capabilities.xml", {A06.source: PRG_A06}))
    )

    report = download_collection(
        product="admin",
        output_dir=tmp_path,
        country="pl",
        level="obreb",
        bbox=PRG_BBOX,
        cache=False,
    )

    assert report.ok
    (unit_file,) = report.files
    file = unit_file.file
    assert unit_file.unit == "566000_244000_566400_244400"
    assert file.path == (
        tmp_path / "boundaries/pl_prg_obreb/bbox/566000_244000_566400_244400.gpkg"
    )
    assert (file.status, file.label) == ("new", "2026-10-12")
    assert set(service.requests("TYPENAMES")) == {A06.source}
    assert [name for name, _ in pyogrio.list_layers(file.path)] == [A06.name]
    info = pyogrio.read_info(file.path)
    assert info["features"] == 4
    assert {"JPT_KOD_JE", "IIP_IDENTY"} <= set(info["fields"])
    meta = _meta(file.version_path)
    assert meta["dataset"] == "pl.gugik.prg"
    assert meta["request"] == {
        "bbox": [566000.0, 244000.0, 566400.0, 244400.0],
        "bbox_crs": "EPSG:2180",
        "level": "obreb",
    }
    assert meta["horizontal_crs"] == "EPSG:2180"
    assert meta["extra"]["source"] == {
        "service": PRG_ENDPOINT,
        "protocol": "wfs",
        "layers": [
            {"code": "obreb", "source": A06.source, "name": A06.name, "features": 4}
        ],
    }
    assert meta["extra"]["version"] == {
        "label": "2026-10-12",
        "label_source": "downloaded",
    }
    assert "parent_request" not in meta["extra"]


def test_area_result_reused_without_requests(
    tmp_path, monkeypatch, frozen_clock, prg_pages_of_two
):
    """A second run uses the local version: no request at all (not even
    GetCapabilities), status ``local`` without a cheap signal."""
    service = _serve(
        monkeypatch, FakeService(wfs("prg_capabilities.xml", {A06.source: PRG_A06}))
    )
    choice = {
        "product": "admin",
        "output_dir": tmp_path,
        "country": "pl",
        "level": "obreb",
        "bbox": PRG_BBOX,
        "cache": False,
    }
    first = download_collection(**choice)
    calls = len(service.calls)

    again = download_collection(**choice)

    assert len(service.calls) == calls
    (unit_file,) = again.files
    assert (unit_file.file.status, unit_file.file.unverified) == ("local", "none")
    assert unit_file.file.version_path == first.files[0].file.version_path


# --- EGiB: both layers of an area ---------------------------------------------


def test_egib_bbox_two_layers_without_data_field(tmp_path, monkeypatch, frozen_clock):
    """EGiB of an area: layers ``dzialki`` (2 parcels) and ``budynki`` (none,
    schema only); ``DATA`` stays out of the GPKG and its values go to
    ``extra.source.dropped_fields``."""
    _serve(monkeypatch, FakeService(wfs("egib_capabilities.xml", EGIB_RURAL)))

    report = download_collection(
        product="map",
        output_dir=tmp_path,
        country="pl",
        bbox=EGIB_RURAL_BBOX,
        cache=False,
    )

    (unit_file,) = report.files
    path = unit_file.file.path
    assert path == tmp_path / "cadastre/pl_egib/bbox/654800_588600_655000_588800.gpkg"
    assert [name for name, _ in pyogrio.list_layers(path)] == ["dzialki", "budynki"]
    parcels = pyogrio.read_info(path, layer="dzialki")
    assert parcels["features"] == 2
    assert "DATA" not in parcels["fields"] and "ID_DZIALKI" in parcels["fields"]
    assert pyogrio.read_info(path, layer="budynki")["features"] == 0
    meta = _meta(unit_file.file.version_path)
    assert meta["request"] == {
        "bbox": [654800.0, 588600.0, 655000.0, 588800.0],
        "bbox_crs": "EPSG:2180",
    }
    source = meta["extra"]["source"]
    assert source["service"] == EGIB_ENDPOINT
    assert [(layer["code"], layer["features"]) for layer in source["layers"]] == [
        ("dzialki", 2),
        ("budynki", 0),
    ]
    assert source["dropped_fields"] == {"DATA": ["2026-10-15"]}


def test_new_data_date_alone_is_not_a_new_version(tmp_path, monkeypatch, frozen_clock):
    """The same parcels with another ``DATA`` (the powiat refreshed): the
    same GPKG bytes, ``unchanged`` under ``--force``; the sidecar of the
    version keeps the values of its first download."""
    _serve(monkeypatch, FakeService(wfs("egib_capabilities.xml", EGIB_RURAL)))
    choice = {
        "product": "map",
        "output_dir": tmp_path,
        "country": "pl",
        "bbox": EGIB_RURAL_BBOX,
        "cache": False,
    }
    first = download_collection(**choice).files[0].file
    page = (FIXTURES / "egib_dzialki_br_c2_s0.xml").read_bytes()
    refreshed = page.replace(b"<ms:DATA>2026-10-15<", b"<ms:DATA>2026-10-16<")
    assert refreshed != page
    parcels = {
        **EGIB_RURAL["ms:dzialki"],
        "pages": {
            0: recorded_response(FIXTURES / "egib_dzialki_br_c2_s0.xml", body=refreshed)
        },
    }
    _serve(
        monkeypatch,
        FakeService(
            wfs("egib_capabilities.xml", {**EGIB_RURAL, "ms:dzialki": parcels})
        ),
    )

    forced = download_collection(**choice, update="force").files[0].file

    assert forced.status == "unchanged"
    assert forced.version_path == first.version_path
    source = _meta(forced.version_path)["extra"]["source"]
    assert source["dropped_fields"] == {"DATA": ["2026-10-15"]}
