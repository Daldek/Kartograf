"""``hydro download --product pgw --country pl`` (ADR-059): the national archive
and the GeoPackage of an area read from it.

The published file is served by a fake session with the answer recorded on
2026-11-06 (``tests/fixtures/pl/pgw``: the real size in ``HEAD``) and the tiny
archive of ``kartograf.testing`` as its body, which has the published structure;
its fictional features lie around ``PGW_AREA``.
"""

import json
from pathlib import Path

import numpy as np
import pyogrio
import pyogrio.raw
import pytest
import shapely

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    check_collection,
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import ValidationError
from kartograf.notices import AREA_OMITTED, DOWNLOAD_SIZE, WHOLE_COUNTRY_SIZE
from kartograf.sources.descriptor import ArchiveLayersParams
from kartograf.sources.registry import get_source
from kartograf.testing import (
    PGW_ARCHIVE_SEGMENT,
    PGW_AREA,
    build_pgw_archive,
    build_pgw_store,
)
from tests.support.fake_packages import FakePackageSession, zip_bytes

FIXTURE = Path(__file__).parent.parent / "fixtures" / "pl" / "pgw" / "archive.json"
RECORDED = json.loads(FIXTURE.read_text(encoding="utf-8"))
URL = RECORDED["url"]
HEAD = RECORDED["head"]["headers"]
CHOICE = {"product": "pgw", "country": "pl", "whole_country": True, "cache": False}
AREA = {"product": "pgw", "country": "pl", "bbox": PGW_AREA, "cache": False}
COORDS = "380000_540000_390000_550000"
GDB = "Geobaza_2aPGW_ver_20230915.gdb"
PARAMS = next(
    channel.params
    for channel in get_source("pl.pgw.pgw").channels
    if isinstance(channel.params, ArchiveLayersParams)
)
CODES = ("PGW_WP", "JCWPd", "SIG")


@pytest.fixture(scope="module")
def archive(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    return build_pgw_archive(tmp_path_factory.mktemp("pgw") / "pl.zip").read_bytes()


def _published(body: bytes) -> FakePackageSession:
    """The published file: ``HEAD`` with the recorded size, ``GET`` of ``body``."""
    return FakePackageSession(
        {URL: (200, {**HEAD, "Content-Length": str(len(body))}, body)},
        heads={URL: HEAD},
    )


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(path.name + ".meta.json").read_text("utf-8"))


def _names(*codes: str) -> list[str]:
    """The GeoPackage layers of feature datasets, in the order of the registry."""
    return [layer.name for layer in PARAMS.layers if layer.code in codes]


def _layers(path: Path) -> list[str]:
    return [str(name) for name, _ in pyogrio.list_layers(path)]


def _codes(path: Path, layer: str) -> list[str]:
    """The ``MS_KOD`` of the features of a layer of the GeoPackage, in its order."""
    _, _, _, values = pyogrio.raw.read(path, layer=layer, columns=["MS_KOD"])
    return [str(code) for code in values[0]]


def test_whole_country_stores_the_archive_under_its_edition(
    tmp_path, monkeypatch, frozen_clock, archive
):
    """The ZIP 1:1 in ``hydro/pl_pgw_gdb/country/pl.zip``, labelled by the edition
    of the file (2023-09-15), not by the download date; the recorded size is
    announced before the transfer; the sidecar names the source and the
    reservation of the publication."""
    session = _published(archive)
    monkeypatch.setattr(col, "_session", lambda: session)
    seen: list[tuple[str, int]] = []

    report = download_collection(
        **CHOICE,
        root=tmp_path,
        on_notice=lambda n: seen.append((n.code, session.gets(URL))),
    )

    assert report.ok
    (item,) = report.files
    assert item.file.path == tmp_path / PGW_ARCHIVE_SEGMENT / "country" / "pl.zip"
    assert item.file.path.read_bytes() == archive
    assert item.file.version_path.parent.name == f"2023-09-15_{item.file.sha256[:8]}"
    assert seen == [(WHOLE_COUNTRY_SIZE, 0)]
    assert HEAD["Content-Length"] in report.notices[0].message
    meta = _meta(item.file.version_path)
    assert (meta["dataset"], meta["product"], meta["provider"]) == (
        "pl.pgw.pgw",
        "pgw",
        "PGW Wody Polskie",
    )
    assert meta["horizontal_crs"] == "EPSG:2180"
    assert meta["request"] == {"whole_country": True}
    assert meta["extra"]["source"] == {"url": URL, "edition": "2023-09-15"}
    assert meta["extra"]["version"] == {
        "label": "2023-09-15",
        "label_source": "edition",
    }
    assert meta["license"]["url"] == RECORDED["page"]
    assert meta["license"]["attribution"].startswith(
        "Dane: PGW Wody Polskie, KZGW, IIaPGW"
    )


def test_local_archive_is_used_and_checked_without_a_request(
    tmp_path, monkeypatch, archive
):
    """Signal ``none``: without a local version the plan says ``missing``; once
    stored, a new run uses the local version and ``--check`` says
    ``unverifiable``, and neither sends a request."""
    session = _published(archive)
    monkeypatch.setattr(col, "_session", lambda: session)
    (before,) = check_collection(**CHOICE, root=tmp_path).items
    assert before.status == "missing"
    download_collection(**CHOICE, root=tmp_path)
    session.calls.clear()

    again = download_collection(**CHOICE, root=tmp_path)
    (planned,) = check_collection(**CHOICE, root=tmp_path).items

    assert [item.file.status for item in again.files] == ["local"]
    assert planned.status == "unverifiable"
    assert session.calls == []


def test_archive_of_another_edition_is_refused(tmp_path, monkeypatch):
    """The member check finds the edition date in the geodatabase name: an
    archive of another edition behind the URL fails and leaves no version."""
    other = zip_bytes(
        [
            "Geobaza_2aPGW_ver_20240101.gdb/",
            "Geobaza_2aPGW_ver_20240101.gdb/a00000001.gdbtable",
            "Geobaza_2aPGW_ver_20240101.gdb/gdb",
        ]
    )
    monkeypatch.setattr(col, "_session", lambda: _published(other))

    report = download_collection(**CHOICE, root=tmp_path)

    assert not report.ok and report.files == ()
    (failure,) = report.failed
    assert failure.kind == "download"
    assert "_ver_20230915.gdb/gdb" in failure.error
    assert list(tmp_path.rglob("*.zip")) == []


# --- the GeoPackage of an area -------------------------------------------------


def test_area_downloads_the_archive_once_and_reads_its_layers(
    tmp_path, monkeypatch, archive
):
    """The first area request downloads the archive into its slot (announced by
    ``DOWNLOAD_SIZE`` before the transfer, its sidecar naming the area as the
    request that created it) and reports it in ``inputs``; the GeoPackage holds
    the layers of the chosen dataset in the segment of the choice. A later area
    request reads the local archive and sends nothing."""
    session = _published(archive)
    monkeypatch.setattr(col, "_session", lambda: session)
    seen: list[tuple[str, int]] = []

    first = download_collection(
        **AREA,
        layers=["PGW_WP"],
        root=tmp_path,
        on_notice=lambda n: seen.append((n.code, session.gets(URL))),
    )
    calls = list(session.calls)
    second = download_collection(**AREA, layers=["sig"], root=tmp_path)

    assert first.ok and second.ok
    (stored,) = first.inputs
    assert stored.file.path == tmp_path / PGW_ARCHIVE_SEGMENT / "country" / "pl.zip"
    assert stored.file.status == "new"
    assert seen == [(AREA_OMITTED, 0), (DOWNLOAD_SIZE, 0)]
    assert "34 attribute tables" in first.notices[0].message
    assert _meta(stored.file.version_path)["extra"]["parent_request"] == {
        "bbox": [380000.0, 540000.0, 390000.0, 550000.0],
        "bbox_crs": "EPSG:2180",
        "countries": ["PL"],
    }
    (area,) = first.files
    assert area.file.path == tmp_path / "hydro/pl_pgw_pgw-wp/bbox" / f"{COORDS}.gpkg"
    assert _layers(area.file.path) == _names("PGW_WP")
    assert calls == [("HEAD", URL), ("GET", URL)]
    assert session.calls == calls
    assert [item.file.status for item in second.inputs] == ["local"]
    (other,) = second.files
    assert other.file.path == tmp_path / "hydro/pl_pgw_sig/bbox" / f"{COORDS}.gpkg"
    assert _layers(other.file.path) == _names("SIG")


def test_area_sidecar_names_the_archive_version_and_the_layers(tmp_path):
    """The GeoPackage is labelled by the edition of the archive; its sidecar names
    the archive version it was read from (``extra.source_files``, the key of its
    reuse), the chosen datasets as published and every layer with its features."""
    store = build_pgw_store(tmp_path / "data")
    (version,) = store.archive.versions

    report = download_collection(**AREA, layers=["jcwpd", "PGW_WP"], root=store.root)

    (area,) = report.files
    assert area.file.path.parent.parent.name == "pl_pgw_jcwpd-pgw-wp"
    assert area.file.version_path.parent.name == f"2023-09-15_{area.file.sha256[:8]}"
    meta = _meta(area.file.version_path)
    assert meta["request"] == {
        "bbox": [380000.0, 540000.0, 390000.0, 550000.0],
        "bbox_crs": "EPSG:2180",
        "layers": ["PGW_WP", "JCWPd"],
    }
    assert (meta["dataset"], meta["horizontal_crs"], meta["license"]["id"]) == (
        "pl.pgw.pgw",
        "EPSG:2180",
        "PL-APGW",
    )
    extra = meta["extra"]
    assert extra["version"] == {"label": "2023-09-15", "label_source": "edition"}
    assert extra["source_files"] == [
        {
            "name": "archive",
            "file": version.path.relative_to(store.root).as_posix(),
            "sha256": version.sha256,
            "label": "2023-09-15",
        }
    ]
    source = extra["source"]
    assert (source["url"], source["edition"], source["member"]) == (
        URL,
        "2023-09-15",
        GDB,
    )
    assert [layer["name"] for layer in source["layers"]] == _names("PGW_WP", "JCWPd")
    counts = {
        layer["name"]: pyogrio.read_info(area.file.path, layer=layer["name"])[
            "features"
        ]
        for layer in source["layers"]
    }
    assert {layer["name"]: layer["features"] for layer in source["layers"]} == counts
    assert counts["zlewnie_jcwp_rzecznych"] == 3
    assert "parent_request" not in extra


def test_same_area_reuses_the_geopackage_of_the_same_archive(
    tmp_path, monkeypatch, archive
):
    """A version written from an archive of the same sha256 is reused, also when
    ``update="force"`` downloads the archive again (the same bytes)."""
    monkeypatch.setattr(col, "_session", lambda: _published(archive))
    store = build_pgw_store(tmp_path / "data")
    first = download_collection(**AREA, root=store.root)

    again = download_collection(**AREA, root=store.root)
    forced = download_collection(**AREA, root=store.root, update="force")

    (written,) = first.files
    assert written.file.status == "new"
    assert _layers(written.file.path) == _names(*CODES)
    for report in (again, forced):
        (area,) = report.files
        assert area.file.status == "reused"
        assert area.file.version_path == written.file.version_path
    assert [item.file.status for item in forced.inputs] == ["unchanged"]
    assert len(list(written.file.version_path.parent.parent.iterdir())) == 1


def test_area_check_judges_the_geopackage_by_the_local_archive(
    tmp_path, monkeypatch, archive
):
    """``--check`` gives the archive and the GeoPackage: ``missing`` twice without
    an archive; with the archive ``unverifiable`` and ``missing`` until a version
    was written from it, then ``current``. ``--upgrade --plan`` writes the planned
    GeoPackage from the local archive. No request is sent."""
    store = build_pgw_store(tmp_path / "data")
    empty = tmp_path / "empty"
    session = _published(archive)
    monkeypatch.setattr(col, "_session", lambda: session)
    choice = {**AREA, "layers": ["PGW_WP"]}

    def statuses(root: Path) -> list[tuple[str, str]]:
        plan = check_collection(**choice, root=root)
        return [(item.segment, item.status) for item in plan.items]

    before = statuses(empty)
    plan = check_collection(**choice, root=store.root)
    upgraded = download_collection(
        **choice, root=store.root, update="upgrade", plan=plan
    )
    after = statuses(store.root)

    assert before == [
        (PGW_ARCHIVE_SEGMENT, "missing"),
        ("hydro/pl_pgw_pgw-wp", "missing"),
    ]
    assert [(item.segment, item.status) for item in plan.items] == [
        (PGW_ARCHIVE_SEGMENT, "unverifiable"),
        ("hydro/pl_pgw_pgw-wp", "missing"),
    ]
    assert upgraded.ok and upgraded.stale == ()
    assert [item.file.status for item in upgraded.files] == ["new"]
    assert [item.file.status for item in upgraded.inputs] == ["local"]
    assert after == [
        (PGW_ARCHIVE_SEGMENT, "unverifiable"),
        ("hydro/pl_pgw_pgw-wp", "current"),
    ]
    assert session.calls == []


def test_plain_area_writes_only_the_geopackage(tmp_path, monkeypatch, archive):
    """``-o DIR``: the archive is fetched into the staging directory and removed
    with it; the directory gets ``<coords>.gpkg`` alone, the same bytes as the
    store file, and the plan has only that target."""
    session = _published(archive)
    monkeypatch.setattr(col, "_session", lambda: session)
    out = tmp_path / "out"
    store = build_pgw_store(tmp_path / "data")
    choice = {**AREA, "layers": ["PGW_WP"]}

    plan = check_collection(**choice, output_dir=out)
    report = download_collection(**choice, output_dir=out)
    stored = download_collection(**choice, root=store.root)

    assert [(item.name, item.action) for item in plan.items] == [
        (f"{COORDS}.gpkg", "write")
    ]
    assert report.ok and report.inputs == ()
    (area,) = report.files
    assert area.file.status == "written"
    assert sorted(path.name for path in out.iterdir()) == [f"{COORDS}.gpkg"]
    assert area.file.path.read_bytes() == stored.files[0].file.path.read_bytes()
    assert session.gets(URL) == 1


def test_geometry_area_is_its_envelope(tmp_path):
    """``--geometry`` reads the features of its envelope (ADR-059 B2): a
    catchment on the north edge of the envelope stays although the triangle
    touches it nowhere; the request is recorded as ``parent_request``."""
    store = build_pgw_store(tmp_path / "data")
    triangle = shapely.Polygon([(380000, 540000), (390000, 540000), (380000, 550000)])
    geometry = tmp_path / "area.gpkg"
    pyogrio.raw.write(
        geometry,
        np.array([shapely.to_wkb(triangle)], dtype=object),
        [],
        [],
        layer="area",
        driver="GPKG",
        geometry_type="Polygon",
        crs="EPSG:2180",
    )

    report = download_collection(
        product="pgw",
        country="pl",
        geometry=geometry,
        layers=["PGW_WP"],
        root=store.root,
        cache=False,
    )

    (area,) = report.files
    assert area.file.path.name == f"{COORDS}.gpkg"
    assert _codes(area.file.path, "zlewnie_jcwp_rzecznych") == [
        "RW600019000001",
        "RW600019000002",
        "RW600019000003",
    ]
    assert "parent_request" in _meta(area.file.version_path)["extra"]


def test_area_without_features_fails_with_no_coverage(tmp_path):
    """No feature of the chosen layers in the area: a ``no_coverage`` failure of
    the area and no file."""
    store = build_pgw_store(tmp_path / "data")
    far = BBox(700000.0, 200000.0, 701000.0, 201000.0, "EPSG:2180")

    report = download_collection(**{**AREA, "bbox": far}, root=store.root)

    assert not report.ok and report.files == ()
    (failure,) = report.failed
    assert (failure.unit, failure.kind) == (
        "700000_200000_701000_201000",
        "no_coverage",
    )
    assert list(store.root.rglob("*.gpkg")) == []


def test_area_whose_archive_fails_has_no_geopackage(tmp_path, monkeypatch):
    """The source no longer publishes the file (404): one ``no_coverage`` failure
    of the archive, and the area is not written."""
    session = FakePackageSession({URL: (404, {}, b"")})
    monkeypatch.setattr(col, "_session", lambda: session)

    report = download_collection(**AREA, root=tmp_path)

    assert not report.ok and report.files == () and report.inputs == ()
    assert [(f.unit, f.kind) for f in report.failed] == [("pl", "no_coverage")]
    assert list(tmp_path.rglob("*.gpkg")) == list(tmp_path.rglob("*.zip")) == []


@pytest.mark.parametrize(
    ("layers", "segment", "choice", "codes"),
    [
        (None, "hydro/pl_pgw", {}, CODES),
        (["PGW_WP"], "hydro/pl_pgw_pgw-wp", {"layers": ["PGW_WP"]}, ("PGW_WP",)),
        (
            ["sig", " pgw_wp", "SIG"],
            "hydro/pl_pgw_pgw-wp-sig",
            {"layers": ["PGW_WP", "SIG"]},
            ("PGW_WP", "SIG"),
        ),
        (
            ["JCWPD", "SIG", "PGW_WP"],
            "hydro/pl_pgw_jcwpd-pgw-wp-sig",
            {"layers": ["PGW_WP", "JCWPd", "SIG"]},
            CODES,
        ),
    ],
    ids=["all", "one", "two-any-case", "three"],
)
def test_layers_choose_the_segment_and_the_request(
    tmp_path, layers, segment, choice, codes
):
    """A choice of datasets is one segment token (sorted, lowercase, ``_`` as
    ``-``) and the request lists them as published; without it every layer."""
    request = validate_collection_request(
        product="pgw", country="pl", bbox=PGW_AREA, layers=layers, root=tmp_path
    )

    (part,) = request.parts
    assert part.segment == segment
    assert part.choice == choice
    assert [layer.name for layer in part.layers] == _names(*codes)


@pytest.mark.parametrize(
    ("choice", "problem"),
    [
        ({**AREA, "layers": []}, "at least one"),
        ({**AREA, "layers": ["PGW_WP", "RZGW"]}, "RZGW"),
        ({**CHOICE, "layers": ["PGW_WP"]}, "national file"),
        (
            {
                "product": "network",
                "country": "cz",
                "bbox": BBox(-470000, -1130000, -440000, -1100000, "EPSG:5514"),
                "layers": ["PGW_WP"],
            },
            "network",
        ),
    ],
    ids=["empty", "unknown", "whole-country", "network"],
)
def test_layers_refused_before_any_request(tmp_path, monkeypatch, choice, problem):
    session = FakePackageSession({})
    monkeypatch.setattr(col, "_session", lambda: session)

    with pytest.raises(ValidationError, match=problem) as raised:
        download_collection(**choice, root=tmp_path)

    assert "layers" in (raised.value.option, *(raised.value.options or ()))
    assert session.calls == []
    assert not any(tmp_path.iterdir())
