"""Collection orchestrator on the version store (ADR-042 D2, D6-D10)."""

import json
import os
from pathlib import Path

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    check_collection,
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import NoCoverageError, ValidationError
from kartograf.notices import AUTO_NARROWED_TO_PL, UNIT_LIST, WHOLE_COUNTRY_SIZE
from kartograf.providers.pl.prg import PRG_WFS_ENDPOINT
from tests.fake_packages import (
    FakePackageSession,
    package_route,
    recorded_head,
)

PRG_FIXTURES = Path(__file__).parent / "fixtures" / "gugik_prg" / "real_2026_10_08"
# E 340000-350000, N 290000-300000: powiats 0208 and 0224 (recorded PRG answer)
AREA = BBox(340000, 290000, 350000, 300000, "EPSG:2180")
LOD1_2024 = (
    "https://opendata.geoportal.gov.pl/InneDane/Budynki3D/LOD1/2024/{woj}/{teryt}.zip"
)
LOD2 = "https://opendata.geoportal.gov.pl/InneDane/Budynki3D/LOD2/{teryt}_gml.zip"


def _prg_route() -> tuple[str, tuple[int, dict, bytes]]:
    body = (PRG_FIXTURES / "two_counties.xml").read_bytes()
    return PRG_WFS_ENDPOINT, (
        200,
        {"Content-Type": "text/xml; subtype=gml/3.2.1"},
        body,
    )


def _zip_route(url: str, members=None, content=b"kartograf"):
    _, (status, headers, body) = package_route(
        "buildings_lod1_2024_1261", members=members, content=content
    )
    return url, (status, headers, body)


@pytest.fixture
def session(monkeypatch):
    """Install a fake session for the orchestrator (routes added by the test)."""
    fake = FakePackageSession({})
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


def _lod1(tmp_path, **kwargs):
    return download_collection(
        product="buildings",
        output_dir=tmp_path,
        teryt="1261",
        lod=1,
        year=2024,
        cache=False,
        **kwargs,
    )


# --- validation (no network) ------------------------------------------------


@pytest.mark.parametrize(
    "selection",
    [
        {},
        {"teryt": "1261", "bbox": AREA},
        {"teryt": "1261", "whole_country": True, "country": "pl"},
        {"sheet": "N-34-130-D", "geometry": "x.gpkg"},
    ],
)
def test_exactly_one_selection(tmp_path, session, selection):
    with pytest.raises(ValidationError):
        download_collection(
            product="buildings", output_dir=tmp_path, lod=1, year=2024, **selection
        )
    assert session.calls == []


def test_product_and_output_are_required(tmp_path, session):
    with pytest.raises(ValidationError) as missing:
        download_collection(product=None, output_dir=tmp_path, teryt="1261")
    assert "admin" in str(missing.value) and "buildings" in str(missing.value)
    with pytest.raises(ValidationError):
        download_collection(product="landcover", output_dir=tmp_path, teryt="1261")
    with pytest.raises(ValidationError):
        download_collection(product="buildings", output_dir=None, teryt="1261", lod=2)
    assert session.calls == []


def test_variant_required_when_many(tmp_path, session):
    with pytest.raises(ValidationError) as error:
        download_collection(
            product="buildings", output_dir=tmp_path, teryt="1261", lod=1
        )
    assert "2019, 2021, 2022, 2024" in str(error.value)
    with pytest.raises(ValidationError) as no_lod:
        download_collection(product="buildings", output_dir=tmp_path, teryt="1261")
    assert "--lod" in str(no_lod.value)
    assert session.calls == []


def test_single_variant_needs_no_flag(tmp_path, session):
    request = validate_collection_request(
        product="buildings", output_dir=tmp_path, teryt="1261", lod=2
    )
    (part,) = request.parts
    assert part.variant is not None and part.variant.edition == "2017"
    assert part.segment == "models3d/pl_buildings_lod2_2017"
    with pytest.raises(ValidationError) as error:
        validate_collection_request(
            product="buildings", output_dir=tmp_path, teryt="1261", lod=2, year=2016
        )
    assert "2017" in str(error.value)
    assert session.calls == []


@pytest.mark.parametrize(
    ("product", "teryt", "extra"),
    [
        ("admin", "1261", {}),  # PRG publishes voivodeship packages only
        ("map", "12", {}),  # EGiB export by powiat (the voivodeship one is 1.4 GB)
        ("buildings", "12", {"lod": 2}),
        ("buildings", "126", {"lod": 2}),
        ("buildings", "9901", {"lod": 2}),  # no voivodeship 99
        ("buildings", "1261", {"lod": 2, "country": "cz"}),
    ],
)
def test_teryt_length_matches_unit(tmp_path, session, product, teryt, extra):
    with pytest.raises(ValidationError):
        validate_collection_request(
            product=product, output_dir=tmp_path, teryt=teryt, **extra
        )
    assert session.calls == []


def test_teryt_hint_names_available_selections(tmp_path):
    with pytest.raises(ValidationError) as error:
        validate_collection_request(product="admin", output_dir=tmp_path, teryt="1261")
    assert "--teryt <2 cyfry>" in str(error.value)
    assert "--whole-country" in str(error.value)


def test_selection_hint_names_what_an_area_downloads(tmp_path):
    """An area of EGiB is the WFS result, of 3D models the powiat packages:
    the hint never offers the same flags with two meanings (live 2026-10-15:
    ``cadastre download --teryt 12`` listed both)."""
    with pytest.raises(ValidationError) as egib:
        validate_collection_request(product="map", output_dir=tmp_path, teryt="12")
    assert "--bbox/--sheet/--geometry (obiekty obszaru)" in str(egib.value)
    assert "paczki powiatow obszaru" not in str(egib.value)
    with pytest.raises(ValidationError) as buildings:
        validate_collection_request(
            product="buildings",
            output_dir=tmp_path,
            country="pl",
            whole_country=True,
            lod=2,
        )
    assert "--bbox/--sheet/--geometry (paczki powiatow obszaru)" in str(buildings.value)
    assert "obiekty obszaru" not in str(buildings.value)


def test_choices_of_other_products_rejected(tmp_path):
    with pytest.raises(ValidationError):
        validate_collection_request(
            product="admin", output_dir=tmp_path, teryt="12", year=2024
        )
    with pytest.raises(ValidationError):
        validate_collection_request(
            product="admin", output_dir=tmp_path, teryt="12", level="gmina"
        )
    with pytest.raises(ValidationError):
        validate_collection_request(
            product="map", output_dir=tmp_path, country="pl", bbox=AREA, level="gmina"
        )
    with pytest.raises(ValidationError):
        validate_collection_request(
            product="buildings",
            output_dir=tmp_path,
            whole_country=True,
            country="pl",
            lod=1,
            year=2024,
        )


def test_level_required_and_checked_for_area(tmp_path):
    with pytest.raises(ValidationError) as missing:
        validate_collection_request(
            product="admin", output_dir=tmp_path, country="pl", bbox=AREA
        )
    assert "gmina" in str(missing.value)
    with pytest.raises(ValidationError):
        validate_collection_request(
            product="admin", output_dir=tmp_path, country="pl", bbox=AREA, level="obec"
        )
    request = validate_collection_request(
        product="admin",
        output_dir=tmp_path,
        country="pl",
        bbox=AREA,
        level={"pl": "gmina"},
    )
    (part,) = request.parts
    assert [layer.name for layer in part.layers] == ["A03_Granice_gmin"]
    assert (part.segment, part.area, part.parent) == (
        "boundaries/pl_prg_gmina",
        AREA,
        None,
    )


def test_area_in_other_crs_is_native_with_parent(tmp_path):
    wgs = BBox(19.90, 50.05, 19.92, 50.06, "EPSG:4326")
    request = validate_collection_request(
        product="map", output_dir=tmp_path, country="pl", bbox=wgs
    )
    (part,) = request.parts
    assert part.area is not None and part.area.crs == "EPSG:2180"
    assert part.parent == {
        "bbox": [19.9, 50.05, 19.92, 50.06],
        "bbox_crs": "EPSG:4326",
        "countries": ["PL"],
    }
    assert part.segment == "cadastre/pl_egib"


def test_country_rules(tmp_path):
    with pytest.raises(ValidationError):  # area without --country
        validate_collection_request(product="map", output_dir=tmp_path, bbox=AREA)
    with pytest.raises(ValidationError):  # whole country needs pl/cz, not auto
        validate_collection_request(
            product="admin", output_dir=tmp_path, whole_country=True, country="auto"
        )
    with pytest.raises(ValidationError, match="tylko dla PL"):  # RCN: PL only
        validate_collection_request(
            product="prices", output_dir=tmp_path, whole_country=True, country="cz"
        )
    with pytest.raises(ValidationError):  # sheet of another country than --country
        validate_collection_request(
            product="map", output_dir=tmp_path, sheet="N-34-130-D", country="cz"
        )


def test_sheet_area_has_sheet_parent(tmp_path):
    request = validate_collection_request(
        product="admin", output_dir=tmp_path, sheet="M-34-064-D", level="powiat"
    )
    (part,) = request.parts
    assert part.parent == {"sheet": "M-34-64-D", "countries": ["PL"]}
    assert part.area is not None and part.area.crs == "EPSG:2180"


def test_horizontal_crs_only_the_published_one(tmp_path):
    validate_collection_request(
        product="admin",
        output_dir=tmp_path,
        whole_country=True,
        country="pl",
        horizontal_crs="EPSG:2180",
    )
    with pytest.raises(ValidationError):
        validate_collection_request(
            product="admin",
            output_dir=tmp_path,
            whole_country=True,
            country="pl",
            horizontal_crs="EPSG:2177",
        )


# --- packages on the store ----------------------------------------------------


def test_teryt_package_slot_sidecar_and_version(tmp_path, session, frozen_clock):
    url = LOD1_2024.format(woj="12", teryt="1261")
    session.routes.update([_zip_route(url)])
    report = _lod1(tmp_path)
    assert report.ok and report.failed == ()
    (unit_file,) = report.files
    assert (unit_file.unit, unit_file.country) == ("1261", "PL")
    file = unit_file.file
    assert file.path == tmp_path / "models3d/pl_buildings_lod1_2024/teryt/1261.zip"
    assert (file.status, file.label) == ("new", "2024")
    assert os.stat(file.path).st_ino == os.stat(file.version_path).st_ino
    meta = _meta(file.version_path)
    assert meta["dataset"] == "pl.gugik.buildings"
    assert meta["request"] == {"teryt": "1261", "lod": 1, "year": 2024}
    assert (meta["horizontal_crs"], meta["vertical_crs"]) == ("EPSG:2180", "EPSG:9651")
    assert meta["extra"]["source"] == {"url": url, "edition": "2024"}
    assert meta["extra"]["version"] == {"label": "2024", "label_source": "edition"}
    assert meta["extra"]["http"]["content_length"] == file.path.stat().st_size
    assert "parent_request" not in meta["extra"]


def test_area_without_feature_channel_uses_powiats(tmp_path, session, frozen_clock):
    session.routes.update(
        [
            _prg_route(),
            _zip_route(LOD1_2024.format(woj="02", teryt="0208")),
            _zip_route(LOD1_2024.format(woj="02", teryt="0224")),
        ]
    )
    notices = []
    report = download_collection(
        product="buildings",
        output_dir=tmp_path,
        country="pl",
        bbox=AREA,
        lod=1,
        year=2024,
        cache=False,
        on_notice=notices.append,
    )
    assert report.ok
    assert [f.unit for f in report.files] == ["0208", "0224"]
    assert [n.code for n in report.notices] == [UNIT_LIST]
    assert notices == list(report.notices)
    meta = _meta(report.files[0].file.version_path)
    assert meta["request"] == {"teryt": "0208", "lod": 1, "year": 2024}
    assert meta["extra"]["parent_request"] == {
        "bbox": [340000.0, 290000.0, 350000.0, 300000.0],
        "bbox_crs": "EPSG:2180",
        "countries": ["PL"],
    }


def test_area_progress_per_unit_as_sheet_list(tmp_path, session, frozen_clock):
    """``on_progress``: per powiat ``downloading`` right before its transfer,
    then ``completed``; a local version is ``skipped`` without a transfer."""
    session.routes.update(
        [
            _prg_route(),
            _zip_route(LOD1_2024.format(woj="02", teryt="0208")),
            _zip_route(LOD1_2024.format(woj="02", teryt="0224")),
        ]
    )
    choice = {
        "product": "buildings",
        "output_dir": tmp_path,
        "country": "pl",
        "bbox": AREA,
        "lod": 1,
        "year": 2024,
        "cache": False,
    }
    events: list = []

    def seen(p):
        events.append((p.current, p.total, p.sheet, p.status))

    assert download_collection(**choice, on_progress=seen).ok
    assert events == [
        (1, 2, "0208", "downloading"),
        (1, 2, "0208", "completed"),
        (2, 2, "0224", "downloading"),
        (2, 2, "0224", "completed"),
    ]
    events.clear()
    # in parallel: one event per finished unit, in completion order
    assert download_collection(**choice, workers=2, on_progress=seen).ok
    assert [(current, total, status) for current, total, _, status in events] == [
        (1, 2, "skipped"),
        (2, 2, "skipped"),
    ]
    assert sorted(unit for _, _, unit, _ in events) == ["0208", "0224"]


def test_auto_narrows_to_countries_with_the_product(tmp_path, session, frozen_clock):
    session.routes.update(
        [
            _prg_route(),
            _zip_route(LOD1_2024.format(woj="02", teryt="0208")),
            _zip_route(LOD1_2024.format(woj="02", teryt="0224")),
        ]
    )
    report = download_collection(
        product="buildings",
        output_dir=tmp_path,
        country="auto",
        bbox=AREA,
        lod=1,
        year=2024,
        cache=False,
    )
    assert report.notices[0].code == AUTO_NARROWED_TO_PL
    assert len(report.files) == 2


def test_unit_failure_isolated(tmp_path, session, frozen_clock):
    """LoD2 does not cover every powiat: 404 of one is its failure only."""
    _, missing = package_route("buildings_lod2_2017_3262_missing")
    session.routes.update(
        [
            _prg_route(),
            _zip_route(LOD2.format(teryt="0208")),
            (LOD2.format(teryt="0224"), missing),
        ]
    )
    report = download_collection(
        product="buildings",
        output_dir=tmp_path,
        country="pl",
        bbox=AREA,
        lod=2,
        cache=False,
    )
    assert not report.ok
    assert [f.unit for f in report.files] == ["0208"]
    (failure,) = report.failed
    assert (failure.unit, failure.country, failure.kind) == (
        "0224",
        "PL",
        "no_coverage",
    )
    assert not (tmp_path / "models3d/pl_buildings_lod2_2017/teryt/0224.zip").exists()


def test_area_without_powiats_is_no_coverage(tmp_path, session):
    body = (PRG_FIXTURES / "no_counties.xml").read_bytes()
    session.routes[PRG_WFS_ENDPOINT] = (200, {"Content-Type": "text/xml"}, body)
    with pytest.raises(NoCoverageError):
        download_collection(
            product="buildings",
            output_dir=tmp_path,
            country="pl",
            # Baltic Sea inside the PL envelope (a bbox outside it fails before PRG)
            bbox=BBox(450000, 780000, 451000, 781000, "EPSG:2180"),
            lod=2,
            cache=False,
        )


def test_whole_country_requires_flag_and_reports_size(tmp_path, session, frozen_clock):
    url, response = package_route("prg_country")
    _, recorded = recorded_head("prg_country")
    session.routes[url] = response
    session.heads[url] = recorded
    seen = []

    def on_notice(notice):
        seen.append((notice.code, session.gets(url)))

    report = download_collection(
        product="admin",
        output_dir=tmp_path,
        country="pl",
        whole_country=True,
        cache=False,
        on_notice=on_notice,
    )
    assert report.ok
    assert seen == [(WHOLE_COUNTRY_SIZE, 0)]  # announced before the transfer
    assert "377419459" in report.notices[0].text
    assert session.calls == [("HEAD", url), ("GET", url)]
    (unit_file,) = report.files
    assert unit_file.unit == "pl"
    assert unit_file.file.path == tmp_path / "boundaries/pl_prg_shp/country/pl.zip"
    meta = _meta(unit_file.file.version_path)
    assert meta["request"] == {"whole_country": True}
    assert meta["extra"]["version"]["label_source"] == "downloaded"


def test_voivodeship_package(tmp_path, session, frozen_clock):
    url, response = package_route("prg_woj_12")
    session.routes[url] = response
    report = download_collection(
        product="admin", output_dir=tmp_path, teryt="12", cache=False
    )
    (unit_file,) = report.files
    assert unit_file.file.path == tmp_path / "boundaries/pl_prg_gml/teryt/12.zip"
    assert _meta(unit_file.file.version_path)["request"] == {"teryt": "12"}


def test_egib_export_unpacked(tmp_path, session, frozen_clock):
    url, response = package_route("egib_1261", content=b"SQLite format 3\x00")
    session.routes[url] = response
    report = download_collection(
        product="map", output_dir=tmp_path, teryt="1261", cache=False
    )
    (unit_file,) = report.files
    path = unit_file.file.path
    assert path == tmp_path / "cadastre/pl_egib_gpkg/teryt/1261.gpkg"
    assert path.read_bytes().startswith(b"SQLite format 3\x00")
    meta = _meta(unit_file.file.version_path)
    assert meta["extra"]["source"] == {"url": url, "member": "1261.gpkg"}
    assert meta["horizontal_crs"] == "EPSG:2180" and meta["vertical_crs"] is None


def test_local_version_reused(tmp_path, session, frozen_clock):
    session.routes.update([_zip_route(LOD1_2024.format(woj="12", teryt="1261"))])
    first = _lod1(tmp_path)
    again = _lod1(tmp_path)
    assert session.gets() == 1  # no second data transfer
    (unit_file,) = again.files
    assert unit_file.file.status == "local"
    assert unit_file.file.unverified == "none"
    assert unit_file.file.version_path == first.files[0].file.version_path


def test_force_same_bytes_unchanged(tmp_path, session, frozen_clock):
    session.routes.update([_zip_route(LOD1_2024.format(woj="12", teryt="1261"))])
    first = _lod1(tmp_path)
    forced = _lod1(tmp_path, update="force")
    assert session.gets() == 2
    assert forced.files[0].file.status == "unchanged"
    assert forced.files[0].file.version_path == first.files[0].file.version_path


def test_force_new_bytes_new_version(tmp_path, session, frozen_clock):
    url = LOD1_2024.format(woj="12", teryt="1261")
    session.routes.update([_zip_route(url)])
    first = _lod1(tmp_path)
    old_sidecar = Path(f"{first.files[0].file.version_path}.meta.json").read_bytes()
    session.routes.update([_zip_route(url, content=b"nowa tresc")])
    forced = _lod1(tmp_path, update="force")
    new = forced.files[0].file
    assert new.status == "new"
    assert new.version_path != first.files[0].file.version_path
    assert (
        Path(f"{first.files[0].file.version_path}.meta.json").read_bytes()
        == old_sidecar
    )
    assert new.path.read_bytes() == new.version_path.read_bytes()


def test_editions_relabeled_across_slots(tmp_path, session, frozen_clock):
    """Identical yearly releases share the bytes (ADR-042 D7)."""
    lod1_2021 = (
        "https://opendata.geoportal.gov.pl/InneDane/Budynki3D/LOD1/2021/12/1261.zip"
    )
    lod1_2022 = (
        "https://opendata.geoportal.gov.pl/InneDane/Budynki3D/LOD1/2022/12/1261.zip"
    )
    session.routes.update([_zip_route(lod1_2021), _zip_route(lod1_2022)])
    older = download_collection(
        product="buildings",
        output_dir=tmp_path,
        teryt="1261",
        lod=1,
        year=2021,
        cache=False,
    )
    newer = download_collection(
        product="buildings",
        output_dir=tmp_path,
        teryt="1261",
        lod=1,
        year=2022,
        cache=False,
    )
    old, new = older.files[0].file, newer.files[0].file
    assert (new.status, new.label, new.same_as) == ("relabeled", "2022", "2021")
    assert os.stat(new.version_path).st_ino == os.stat(old.version_path).st_ino
    assert new.path == tmp_path / "models3d/pl_buildings_lod1_2022/teryt/1261.zip"
    assert _meta(new.version_path)["extra"]["version"]["label"] == "2022"


def test_check_collection_never_downloads(tmp_path, session, frozen_clock):
    plan = check_collection(
        product="buildings",
        output_dir=tmp_path,
        teryt="1261",
        lod=1,
        year=2024,
        cache=False,
    )
    (item,) = plan.items
    assert (item.track, item.unit, item.status) == ("collection", "1261", "missing")
    assert (item.segment, item.hierarchy, item.name) == (
        "models3d/pl_buildings_lod1_2024",
        "teryt",
        "1261.zip",
    )
    assert session.calls == []
    session.routes.update([_zip_route(LOD1_2024.format(woj="12", teryt="1261"))])
    _lod1(tmp_path)
    calls = len(session.calls)
    (again,) = check_collection(
        product="buildings",
        output_dir=tmp_path,
        teryt="1261",
        lod=1,
        year=2024,
        cache=False,
    ).items
    assert (again.status, again.local_label) == ("unverifiable", "2024")
    assert len(session.calls) == calls


def test_upgrade_with_plan_executes_planned_and_reports_stale(
    tmp_path, session, frozen_clock
):
    url = LOD1_2024.format(woj="12", teryt="1261")
    session.routes.update([_zip_route(url)])
    plan = check_collection(
        product="buildings",
        output_dir=tmp_path,
        teryt="1261",
        lod=1,
        year=2024,
        cache=False,
    )
    done = _lod1(tmp_path, update="upgrade", plan=plan)
    assert done.ok and done.files[0].file.status == "new"

    other = check_collection(
        product="buildings",
        output_dir=tmp_path,
        teryt="1261",
        lod=1,
        year=2022,
        cache=False,
    )
    before = session.gets()
    stale = _lod1(tmp_path, update="upgrade", plan=other)
    assert not stale.ok
    assert [item.segment for item in stale.stale] == ["models3d/pl_buildings_lod1_2022"]
    assert session.gets() == before  # nothing downloaded from a stale plan


def test_plan_needs_upgrade_and_same_store(tmp_path, session):
    plan = check_collection(
        product="buildings", output_dir=tmp_path, teryt="1261", lod=2, cache=False
    )
    with pytest.raises(ValidationError):
        download_collection(
            product="buildings", output_dir=tmp_path, teryt="1261", lod=2, plan=plan
        )
    with pytest.raises(ValidationError):
        download_collection(
            product="buildings",
            output_dir=tmp_path / "inny",
            teryt="1261",
            lod=2,
            update="upgrade",
            plan=plan,
        )


def test_workers_download_units_in_parallel(tmp_path, session, frozen_clock):
    session.routes.update(
        [
            _prg_route(),
            _zip_route(LOD1_2024.format(woj="02", teryt="0208")),
            _zip_route(LOD1_2024.format(woj="02", teryt="0224")),
        ]
    )
    report = download_collection(
        product="buildings",
        output_dir=tmp_path,
        country="pl",
        bbox=AREA,
        lod=1,
        year=2024,
        workers=2,
        cache=False,
    )
    assert [f.unit for f in report.files] == ["0208", "0224"]
