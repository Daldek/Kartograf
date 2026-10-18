"""CLI = API parity (ADR-037) for ``boundaries``, ``cadastre``, ``models3d``
and ``hydro download``: the same request through ``kartograf.cli.main`` and
through ``download_collection``/``check_collection`` gives the same store
(bytes of files and sidecars), statuses, plan, data notices and errors -
frozen clock.

Scenarios: PRG objects of an area (``--level``), PRG national file (size
notice), RUIAN objects of an area (CZ), HY-NET national file (HEAD and GET),
EGiB export of a powiat, 3D models of a powiat, 3D models of an area with a
powiat without a package, ``--check-updates --plan`` + ``--upgrade --plan``,
input errors. BDOT10k ``--year`` and ZABAGED: ``tests/test_parity_landcover.py``.
"""

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import check_collection, download_collection
from kartograf.download.plan import UpdatePlan
from kartograf.exceptions import ValidationError
from kartograf.notices import UNIT_LIST, WHOLE_COUNTRY_SIZE
from tests.fake_packages import (
    FakePackageSession,
    package_route,
    recorded_head,
    zip_bytes,
)
from tests.parity import assert_notices_printed, assert_same_store, run_both
from tests.test_collections_cz import NATIONAL, FakeCuzk, _page_size
from tests.test_collections_products import (
    TWO_POWIATS,
    _prg_route,
    serve_prg_obreby,
)
from tests.test_feature_bbox import PRG_BBOX

pytestmark = pytest.mark.usefixtures("frozen_clock")

LOD2 = "https://opendata.geoportal.gov.pl/InneDane/Budynki3D/LOD2/{teryt}_gml.zip"


def _serve(monkeypatch, *routes) -> FakePackageSession:
    session = FakePackageSession(dict(routes))
    monkeypatch.setattr(col, "_session", lambda: session)
    return session


def _same(run, *, statuses: list[str]) -> None:
    report = run.api_result
    assert_same_store(run.cli_store, run.api_store)
    assert run.cli_code == (0 if report.ok else 1)
    assert_notices_printed(run.cli_stderr, report.notices)
    assert [item.file.status for item in report.files] == statuses


def test_prg_area_level(tmp_path, monkeypatch):
    serve_prg_obreby(monkeypatch)
    run = run_both(
        [
            "boundaries",
            "download",
            "--product",
            "admin",
            "--country",
            "pl",
            "--level",
            "obreb",
            "--bbox",
            "566000,244000,566400,244400",
        ],
        lambda out: download_collection(
            product="admin", output_dir=out, country="pl", level="obreb", bbox=PRG_BBOX
        ),
        tmp_path,
    )
    _same(run, statuses=["new"])


def test_prg_whole_country_reports_size(tmp_path, monkeypatch):
    url, response = package_route("prg_country")
    session = _serve(monkeypatch, (url, response))
    session.heads[url] = recorded_head("prg_country")[1]
    run = run_both(
        [
            "boundaries",
            "download",
            "--product",
            "admin",
            "--country",
            "pl",
            "--whole-country",
        ],
        lambda out: download_collection(
            product="admin", output_dir=out, country="pl", whole_country=True
        ),
        tmp_path,
    )
    _same(run, statuses=["new"])
    assert [n.code for n in run.api_result.notices] == [WHOLE_COUNTRY_SIZE]


def test_ruian_area_level(tmp_path, monkeypatch):
    """RUIAN obce of a CZ area (recorded layer 12, pages of 2)."""
    _page_size(monkeypatch, "cz.cuzk.ruian", 2)
    monkeypatch.setattr(col, "_session", lambda: FakeCuzk())
    run = run_both(
        [
            "boundaries",
            "download",
            "--product",
            "admin",
            "--country",
            "cz",
            "--level",
            "obec",
            "--bbox=-455000,-1115000,-450000,-1110000",
            "--bbox-crs",
            "EPSG:5514",
        ],
        lambda out: download_collection(
            product="admin",
            output_dir=out,
            country="cz",
            level="obec",
            bbox=BBox(-455000, -1115000, -450000, -1110000, "EPSG:5514"),
        ),
        tmp_path,
    )
    _same(run, statuses=["new"])


def test_hynet_whole_country_reports_size(tmp_path, monkeypatch):
    """The national HY-NET file: its size from ``HEAD`` (recorded headers,
    tests/fixtures/cz/unit_package) before the ``GET`` of a small ZIP with
    the real member names."""
    entry = NATIONAL["hynet_country"]
    url, head = entry["url"], entry["headers"]
    body = zip_bytes(entry["members"])
    session = _serve(
        monkeypatch, (url, (200, {**head, "Content-Length": str(len(body))}, body))
    )
    session.heads[url] = head
    run = run_both(
        [
            "hydro",
            "download",
            "--product",
            "network",
            "--country",
            "cz",
            "--whole-country",
        ],
        lambda out: download_collection(
            product="network", output_dir=out, country="cz", whole_country=True
        ),
        tmp_path,
    )
    _same(run, statuses=["new"])
    assert [n.code for n in run.api_result.notices] == [WHOLE_COUNTRY_SIZE]
    assert "194208037 B" in run.api_result.notices[0].text
    assert session.calls == [("HEAD", url), ("GET", url)] * 2


def test_egib_teryt_export(tmp_path, monkeypatch):
    _serve(monkeypatch, package_route("egib_1261", content=b"SQLite format 3\x00"))
    run = run_both(
        ["cadastre", "download", "--product", "map", "--teryt", "1261"],
        lambda out: download_collection(product="map", output_dir=out, teryt="1261"),
        tmp_path,
    )
    _same(run, statuses=["new"])


def test_buildings_teryt(tmp_path, monkeypatch):
    _serve(monkeypatch, package_route("buildings_lod1_2024_1261"))
    run = run_both(
        [
            "models3d",
            "download",
            "--product",
            "buildings",
            "--teryt",
            "1261",
            "--lod",
            "1",
            "--year",
            "2024",
        ],
        lambda out: download_collection(
            product="buildings", output_dir=out, teryt="1261", lod=1, year=2024
        ),
        tmp_path,
    )
    _same(run, statuses=["new"])


def test_buildings_area_with_missing_powiat(tmp_path, monkeypatch):
    _, built = package_route("buildings_lod2_2017_1261")
    _, missing = package_route("buildings_lod2_2017_3262_missing")
    _serve(
        monkeypatch,
        _prg_route(),
        (LOD2.format(teryt="0208"), built),
        (LOD2.format(teryt="0224"), missing),
    )
    run = run_both(
        [
            "models3d",
            "download",
            "--product",
            "buildings",
            "--lod",
            "2",
            "--country",
            "pl",
            "--bbox",
            "340000,290000,350000,300000",
        ],
        lambda out: download_collection(
            product="buildings", output_dir=out, lod=2, country="pl", bbox=TWO_POWIATS
        ),
        tmp_path,
    )
    _same(run, statuses=["new"])
    assert [n.code for n in run.api_result.notices] == [UNIT_LIST]
    assert [f.unit for f in run.api_result.failed] == ["0224"]
    assert f"Error: 0224: {run.api_result.failed[0].error}\n" in run.cli_stderr


def test_check_plan_upgrade(tmp_path, monkeypatch):
    _serve(monkeypatch, package_route("buildings_lod1_2024_1261"))
    choice = {"product": "buildings", "teryt": "1261", "lod": 1, "year": 2024}
    argv = [
        "models3d",
        "download",
        "--product",
        "buildings",
        "--teryt",
        "1261",
        "--lod",
        "1",
        "--year",
        "2024",
    ]
    plan_file = tmp_path / "plan.json"
    checked = run_both(
        [*argv, "--check-updates", "--plan", str(plan_file)],
        lambda out: check_collection(output_dir=out, **choice),
        tmp_path,
    )
    assert checked.cli_code == 0
    cli_plan = UpdatePlan.from_json(plan_file.read_text(encoding="utf-8"))
    api_plan = checked.api_result
    assert cli_plan.items == api_plan.items
    upgraded = run_both(
        [*argv, "--upgrade", "--plan", str(plan_file)],
        lambda out: download_collection(
            output_dir=out, **choice, update="upgrade", plan=api_plan
        ),
        tmp_path,
    )
    _same(upgraded, statuses=["new"])


@pytest.mark.parametrize(
    ("argv", "kwargs"),
    [
        (  # PRG publishes voivodeship packages, not powiat ones
            ["boundaries", "download", "--product", "admin", "--teryt", "1261"],
            {"product": "admin", "teryt": "1261"},
        ),
        (  # LoD1 has several releases: --year required
            [
                "models3d",
                "download",
                "--product",
                "buildings",
                "--teryt",
                "1261",
                "--lod",
                "1",
            ],
            {"product": "buildings", "teryt": "1261", "lod": 1},
        ),
        (  # an area needs --country
            ["cadastre", "download", "--product", "map", "--bbox", "1,2,3,4"],
            {"product": "map", "bbox": BBox(1, 2, 3, 4, "EPSG:2180")},
        ),
        (  # a level of an area is required for PRG
            [
                "boundaries",
                "download",
                "--product",
                "admin",
                "--country",
                "pl",
                "--bbox",
                "566000,244000,566400,244400",
            ],
            {"product": "admin", "country": "pl", "bbox": PRG_BBOX},
        ),
    ],
)
def test_input_errors_same_type_and_text(tmp_path, monkeypatch, argv, kwargs):
    session = _serve(monkeypatch)
    run = run_both(
        argv, lambda out: download_collection(output_dir=out, **kwargs), tmp_path
    )
    assert isinstance(run.api_error, ValidationError)
    assert run.cli_code == 2
    assert run.cli_stderr == f"Error: {run.api_error}\n"
    assert session.calls == []
    assert not run.cli_store.exists() and not run.api_store.exists()
