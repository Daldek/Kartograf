"""Products of plan C on the collection orchestrator (ADR-042 D5, D7, D8, D11).

Area results run the real ``feature_bbox`` engine and GPKG writer on the
recorded WFS answers of ``tests/fixtures/pl/feature_bbox`` (PRG A06 obreby
in Krakow, EGiB parcels and buildings of powiat 1415); only the HTTP session
is replaced. The BDOT10k archive (``landcover download --year``) runs
through ``LandCoverManager`` with the session of its provider (packages of
``tests/fixtures/pl/unit_package``); the module session of the collections
is never installed there, so a request outside the provider's session would
hit the network block of ``conftest``.
"""

import json
import os
from dataclasses import replace
from pathlib import Path

import pyogrio
import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import download_collection
from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.prg import PRG_WFS_ENDPOINT
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams
from tests.conftest import recorded_response
from tests.fake_packages import FakePackageSession, package_route, zip_bytes
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

PRG_FIXTURES = Path(__file__).parent / "fixtures" / "gugik_prg" / "real_2026_10_08"
# E 340000-350000, N 290000-300000: powiats 0208 and 0224 (recorded PRG answer)
TWO_POWIATS = BBox(340000, 290000, 350000, 300000, "EPSG:2180")
ARCHIVE = "https://opendata.geoportal.gov.pl/Archiwum/bdot10k"
SHP_MEMBERS = ["PL.PZGiK.283.1261__OT_PTWP_A.shp", "PL.PZGiK.283.1261__OT_PTWP_A.dbf"]


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


def _serve(monkeypatch, service: FakeService) -> FakeService:
    monkeypatch.setattr(col, "_session", lambda: service)
    return service


def serve_prg_obreby(monkeypatch) -> FakeService:
    """The recorded PRG A06 answers (Krakow) as the orchestrator's service;
    the PRG channel gets ``page_size`` = the ``COUNT=2`` of the recorded
    pages (the registry asks for 1000 per page)."""
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
    return _serve(
        monkeypatch, FakeService(wfs("prg_capabilities.xml", {A06.source: PRG_A06}))
    )


# --- PRG: --level of an area -----------------------------------------------------


def test_prg_level_to_layer(tmp_path, monkeypatch, frozen_clock):
    """``--level obreb`` asks only the A06 type and gives one GPKG layer of
    it, with the TERYT fields of PRG, in the slot of that level."""
    service = serve_prg_obreby(monkeypatch)

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


def test_area_result_reused_without_requests(tmp_path, monkeypatch, frozen_clock):
    """A second run uses the local version: no request at all (not even
    GetCapabilities), status ``local`` without a cheap signal."""
    service = serve_prg_obreby(monkeypatch)
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


# --- BDOT10k archive: landcover download --year (ADR-042 D11) -----------------


def _archive_url(year: int, fmt: str, teryt: str) -> str:
    return f"{ARCHIVE}/{year}/{fmt}/{teryt[:2]}/{teryt}_{fmt}_{year}.zip"


def _archive_route(year: int, fmt: str, teryt: str):
    """A small archive package with the real member names of its format."""
    members = (
        SHP_MEMBERS
        if fmt == "SHP"
        else [f"PL.PZGiK.283.{teryt}/BDOT10k/PL.PZGiK.283.{teryt}__OT_PTWP_A.xml"]
    )
    body = zip_bytes(members)
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Length": str(len(body)),
    }
    return _archive_url(year, fmt, teryt), (200, headers, body)


def _prg_route():
    body = (PRG_FIXTURES / "two_counties.xml").read_bytes()
    return PRG_WFS_ENDPOINT, (200, {"Content-Type": "text/xml"}, body)


def _bdot(tmp_path: Path, *routes) -> tuple[LandCoverManager, FakePackageSession]:
    """``LandCoverManager`` with a BDOT10k provider holding a fake session."""
    session = FakePackageSession(dict(routes))
    return LandCoverManager(tmp_path, Bdot10kProvider(session=session)), session


@pytest.mark.parametrize(
    ("options", "named"),
    [
        ({"year": 2024}, "GML, SHP"),  # a year needs the archive format
        ({"year": 2024, "format": "GPKG"}, "GML, SHP"),  # no GPKG in the archive
        ({"year": 2013, "format": "SHP"}, "2014"),  # releases 2014-2025
        ({"year": 2024, "format": "SHP", "layers": ["PTWP"]}, "--layers"),
        ({"year": 2024, "format": "GML", "keep_raw": True}, "--keep-raw"),
        ({"format": "GML"}, "--year"),  # GML only in the archive
    ],
)
def test_bdot10k_year_requires_archive_format(tmp_path, options, named):
    """The archive choice is checked before any request: the message names
    the allowed values or the flag that does not apply."""
    manager, session = _bdot(tmp_path)

    with pytest.raises(ValidationError) as error:
        manager.download(teryt="1261", **options)

    assert named in str(error.value)
    with pytest.raises(ValidationError):
        manager.validate_request(teryt="1261", **options)
    assert session.calls == []


def test_bdot10k_year_teryt_slot_and_sidecar(tmp_path, frozen_clock):
    """``--teryt 1261 --year 2024 --format SHP``: the package 1:1 in the slot
    of its format and year, labelled by the year."""
    url, response = package_route("bdot10k_2024_shp_1261")
    manager, session = _bdot(tmp_path, (url, response))

    result = manager.download(teryt="1261", year=2024, format="SHP")

    assert result.ok
    (item,) = result.files
    file = item.file
    assert file is not None and (item.unit, item.raw) == ("1261", None)
    assert file.path == tmp_path / "landcover/pl_bdot10k_shp_2024/teryt/1261.zip"
    assert (file.status, file.label) == ("new", "2024")
    assert file.path.read_bytes() == response[2]
    assert os.stat(file.path).st_ino == os.stat(file.version_path).st_ino
    meta = _meta(file.version_path)
    assert (meta["dataset"], meta["product"]) == ("pl.gugik.bdot10k", "landcover")
    assert meta["request"] == {"teryt": "1261", "format": "SHP", "year": 2024}
    assert meta["horizontal_crs"] == "EPSG:2180"
    assert meta["extra"]["source"] == {"url": url, "edition": "2024"}
    assert meta["extra"]["version"] == {"label": "2024", "label_source": "edition"}
    assert "parent_request" not in meta["extra"]
    assert session.calls == [("GET", url)]


def test_bdot10k_year_area_powiats(tmp_path, frozen_clock):
    """An area: the archive package of every powiat of PRG with the area in
    ``extra.parent_request``; a powiat without a package (404) fails alone."""
    _, missing = package_route("buildings_lod2_2017_3262_missing")
    manager, _ = _bdot(
        tmp_path,
        _prg_route(),
        _archive_route(2018, "GML", "0208"),
        (_archive_url(2018, "GML", "0224"), missing),
    )

    result = manager.download(bbox=TWO_POWIATS, year=2018, format="GML")

    assert not result.ok
    assert [item.unit for item in result.files] == ["0208"]
    assert [failure.unit for failure in result.failed] == ["0224"]
    stored = result.files[0].file
    assert stored is not None
    assert stored.path == tmp_path / "landcover/pl_bdot10k_gml_2018/teryt/0208.zip"
    meta = _meta(stored.version_path)
    assert meta["request"] == {"teryt": "0208", "format": "GML", "year": 2018}
    assert meta["extra"]["parent_request"] == {
        "bbox": [340000.0, 290000.0, 350000.0, 300000.0],
        "bbox_crs": "EPSG:2180",
        "countries": ["PL"],
    }
    assert not (tmp_path / "landcover/pl_bdot10k_gml_2018/teryt/0224.zip").exists()


def test_bdot10k_identical_years_stored_once(tmp_path, frozen_clock):
    """Two yearly releases with the same bytes share one inode (ADR-042 D7)."""
    manager, _ = _bdot(
        tmp_path,
        _archive_route(2022, "SHP", "1261"),
        _archive_route(2023, "SHP", "1261"),
    )

    older = manager.download(teryt="1261", year=2022, format="SHP").files[0].file
    newer = manager.download(teryt="1261", year=2023, format="SHP").files[0].file

    assert older is not None and newer is not None
    assert (newer.status, newer.label, newer.same_as) == ("relabeled", "2023", "2022")
    assert newer.path == tmp_path / "landcover/pl_bdot10k_shp_2023/teryt/1261.zip"
    assert os.stat(newer.version_path).st_ino == os.stat(older.version_path).st_ino
    meta = _meta(newer.version_path)
    assert (meta["request"]["year"], meta["extra"]["version"]["label"]) == (
        2023,
        "2023",
    )


def test_bdot10k_archive_check_and_plan(tmp_path, frozen_clock):
    """``check`` with a year: a position on the ``landcover`` track without
    any request; the plan is executed with ``upgrade``."""
    url, response = package_route("bdot10k_2024_gml_1261")
    manager, session = _bdot(tmp_path, (url, response))
    choice = {"teryt": "1261", "year": 2024, "format": "GML"}

    plan = manager.check(**choice)

    (item,) = plan.items
    assert (item.track, item.unit, item.status) == ("landcover", "1261", "missing")
    assert (item.segment, item.hierarchy, item.name) == (
        "landcover/pl_bdot10k_gml_2024",
        "teryt",
        "1261.zip",
    )
    assert session.calls == []
    done = manager.download(**choice, update="upgrade", plan=plan)
    assert done.ok and done.files[0].file is not None
    assert done.files[0].file.status == "new"
    (again,) = manager.check(**choice).items
    assert (again.status, again.local_label) == ("unverifiable", "2024")
    assert session.gets() == 1


# --- 3D building models: vertical CRS of the release -------------------------


def test_buildings_lod2_vertical_crs_in_sidecar(tmp_path, monkeypatch, frozen_clock):
    """LoD2 2017 GML is in PL-KRON86-NH: the sidecar says EPSG:9650."""
    url, response = package_route("buildings_lod2_2017_1261")
    monkeypatch.setattr(col, "_session", lambda: FakePackageSession({url: response}))

    report = download_collection(
        product="buildings", output_dir=tmp_path, teryt="1261", lod=2, cache=False
    )

    meta = _meta(report.files[0].file.version_path)
    assert meta["vertical_crs"] == "EPSG:9650"
    assert meta["extra"]["version"] == {"label": "2017", "label_source": "edition"}
