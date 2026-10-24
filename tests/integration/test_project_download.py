"""``download_project``: first pin, pinned tasks, restoring on another store
(spec 4.6, ADR-040) and ``upgrade``/``force`` re-pinning (spec 4.7)."""

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf import (
    add_project_task,
    download_project,
    get_project_status,
    open_project,
    remove_project_task,
    verify_project,
)
from kartograf._version import build_version
from kartograf.download.versions import read_version
from kartograf.exceptions import DownloadError
from kartograf.project.manifest import MANIFEST_NAME
from kartograf.providers.corine import CorineProvider
from kartograf.providers.soilgrids import SoilGridsProvider
from kartograf.sources.sidecar import file_digest
from tests.conftest import FakeCorine, FakeSoilGrids
from tests.contract.test_parity import _sheet_0_5m_session
from tests.integration.test_cli import _cz_provider_mock
from tests.integration.test_hsg import RasterSoilGrids
from tests.integration.test_landcover_output_params import FakePackages
from tests.integration.test_manager_campaigns import C14, REC, FakeCampaignProvider
from tests.support.project_fixtures import (
    AUTO_CUTOUT,
    BDOT_ARCHIVE,
    BDOT_BBOX,
    BUILDINGS,
    CZ_ORTO_SHEET,
    HSG_SHEET,
    LAZ_AREA,
    PL_SHEET,
    PRG_AREA,
    ZABAGED,
    G,
    LazTiles,
    auto_pl_cz,
    bdot,
    collection_sources,
    copy_manifest,
    cz_orto_feed,
    landcover_sources,
    laz_tiles,
    new_project,
    pl_sheets,
    zabaged_area,
)
from tests.unit.test_validate_request import _shapefile

pytestmark = pytest.mark.usefixtures("frozen_clock")

CLAY = {"property": "clay", "depth": "0-5cm", "stat": "mean"}


def _manifest_bytes(project: Path) -> bytes:
    return (project / MANIFEST_NAME).read_bytes()


def _store_snapshot(store: Path) -> dict[str, bytes]:
    return {
        p.relative_to(store).as_posix(): p.read_bytes()
        for p in sorted(store.rglob("*"))
        if p.is_file()
    }


def _corine():
    return CorineProvider(session=FakeCorine(), use_proxy=False)


FIRST = {
    "pl-sheet": ("elevation download", PL_SHEET, pl_sheets, ["output"]),
    "auto-pl-cz": ("elevation download", AUTO_CUTOUT, auto_pl_cz, ["output"] * 2),
    "laz-tiles": (
        "elevation download",
        LAZ_AREA,
        lambda: laz_tiles(LazTiles(*(f"N-33-131-B-a-1-1-{i}" for i in (1, 2, 3)))),
        ["output"] * 3,
    ),
    "bdot10k-area-keep-raw": (
        "landcover download",
        {"product": "bdot10k", "bbox": BDOT_BBOX, "keep_raw": True},
        lambda: bdot(["0208", "0261"]),
        ["output", "raw", "output", "raw"],
    ),
    "soilgrids": (
        "soil download",
        {"bbox": BDOT_BBOX, **CLAY},
        lambda: landcover_sources(
            soilgrids=lambda: SoilGridsProvider(session=FakeSoilGrids())  # type: ignore[arg-type]
        ),
        ["output"],
    ),
    "corine-preview": (
        "landcover download",
        {"product": "corine", "sheet": "M-33-036-A", "year": 2018},
        lambda: landcover_sources(corine=_corine),
        ["output"],
    ),
    "hsg": (
        "soil hsg",
        {"sheet": HSG_SHEET, "depth": "0-5cm"},
        lambda: landcover_sources(soilgrids=RasterSoilGrids),
        ["output", "input", "input", "input"],
    ),
    "prg-area-level": (
        "boundaries download",
        PRG_AREA,
        collection_sources,
        ["output"],
    ),
    "buildings-teryt": ("models3d download", BUILDINGS, collection_sources, ["output"]),
    "bdot10k-archive": (
        "landcover download",
        BDOT_ARCHIVE,
        collection_sources,
        ["output"],
    ),
    # one SM5 sheet = four pinned files: the JPEG and three world files
    "cz-orto-sheet": ("imagery download", CZ_ORTO_SHEET, cz_orto_feed, ["output"] * 4),
    "zabaged-area": ("landcover download", ZABAGED, zabaged_area, ["output"]),
}


@pytest.mark.parametrize("case", FIRST.values(), ids=FIRST.keys())
def test_first_download_pins_every_file(tmp_path, frozen_clock, case):
    command, options, sources, roles = case
    project = new_project(tmp_path)
    add_project_task(project, name="zadanie", command=command, options=options)
    with sources(), patch.object(CorineProvider, "has_clms_token", new=False):
        report = download_project(project)
    (result,) = report.tasks
    assert report.ok and result.outcome == "pinned" and result.errors == ()
    (task,) = report.project.tasks
    assert task.files == result.pinned and result.unpinned == ()
    assert [pin.role for pin in task.files] == roles
    assert task.pinned_at == frozen_clock.isoformat(timespec="seconds")
    assert task.kartograf_version == build_version()
    store = report.project.output_dir
    for pin in task.files:
        data = store / pin.version
        assert file_digest(data) == (pin.sha256, pin.size_bytes)
        version = read_version(data.parent, data.name)
        assert version is not None and version.meta["size_bytes"] == pin.size_bytes
        assert version.label == pin.label and (store / pin.path).is_file()
    assert open_project(project) == report.project


def test_registry_variant_task_pins_file_of_its_segment(tmp_path):
    """A grid variant of the registry (NMT 0.5m, WFS index, ADR-041) is an
    ordinary task: its pin is the sheet in the segment of that variant."""
    sheet = "N-33-58-A-c-1-4"
    project = new_project(tmp_path)
    add_project_task(
        project,
        name="teren",
        command="elevation download",
        options={
            "product": "nmt",
            "sheet": sheet,
            "resolution": "0.5m",
            "vertical_crs": "EVRF2007",
        },
    )
    with patch(
        "kartograf.transport.http.make_gugik_session",
        return_value=_sheet_0_5m_session(sheet),
    ):
        report = download_project(project)
    assert report.ok
    (pin,) = report.project.tasks[0].files
    assert pin.path == f"nmt/pl_1992_0.5m_evrf2007/N-33/58/A/c/1/4/{sheet}.asc"
    assert pin.label == "2025-01-30_84020"


def test_incomplete_task_pins_nothing_and_retry_reuses_store(tmp_path):
    project = new_project(tmp_path)
    options = {"product": "bdot10k", "bbox": BDOT_BBOX}
    add_project_task(
        project, name="pokrycie", command="landcover download", options=options
    )
    packages = FakePackages(fail={"0224"})
    with bdot(["0208", "0224", "0261"], packages):
        report = download_project(project)
    (result,) = report.tasks
    assert not report.ok and result.outcome == "failed"
    assert result.errors == ("0224: BDOT10k TERYT 0224: HTTP 500",)
    assert report.project.tasks[0].files == ()
    packages.fail.clear()
    with bdot(["0208", "0224", "0261"], packages):
        retry = download_project(project)
    assert retry.ok and retry.tasks[0].outcome == "pinned"
    assert [pin.unit for pin in retry.project.tasks[0].files] == [
        "0208",
        "0224",
        "0261",
    ]
    assert packages.calls == ["0208", "0224", "0261", "0224"]


def test_auto_partial_success_not_pinned(tmp_path):
    cz = _cz_provider_mock()
    cz.download_bbox.side_effect = DownloadError("CUZK 503")
    project = new_project(tmp_path)
    add_project_task(
        project, name="teren", command="elevation download", options=AUTO_CUTOUT
    )
    seen = []
    with auto_pl_cz(cz):
        report = download_project(project, on_notice=seen.append)
    (result,) = report.tasks
    assert result.outcome == "failed" and result.errors == ("CUZK 503",)
    assert report.project.tasks[0].files == () and not report.ok
    # library notices pass with their code, prefixed with the task name
    (notice,) = seen
    assert report.notices == (notice,) and notice.code == "auto_partial_success"
    assert notice.message.startswith("teren: czesc CZ zadania zakonczyla sie bledem")


def test_written_after_each_task(tmp_path):
    """An interrupted run keeps the tasks already pinned in the manifest."""
    project = new_project(tmp_path)
    add_project_task(
        project, name="teren", command="elevation download", options=PL_SHEET
    )
    add_project_task(
        project,
        name="gleby",
        command="soil download",
        options={"sheet": HSG_SHEET, **CLAY},
    )

    def interrupted():
        raise KeyboardInterrupt

    with (
        pl_sheets(),
        landcover_sources(soilgrids=interrupted),
        pytest.raises(KeyboardInterrupt),
    ):
        download_project(project)
    teren, gleby = open_project(project).tasks
    assert teren.files and gleby.files == ()


def test_no_metadata_cache_in_project_dir(tmp_path, monkeypatch):
    project = new_project(tmp_path)
    monkeypatch.chdir(project)
    add_project_task(".", name="teren", command="elevation download", options=PL_SHEET)
    with pl_sheets():
        assert download_project(".").ok
    assert sorted(os.listdir(project)) == ["data", MANIFEST_NAME]


def test_unknown_task_and_mode_are_errors_before_download(tmp_path):
    from kartograf.exceptions import ValidationError

    project = new_project(tmp_path)
    add_project_task(
        project, name="teren", command="elevation download", options=PL_SHEET
    )
    for call in (
        lambda: download_project(project, tasks=["terne"]),
        lambda: download_project(project, update="check"),  # type: ignore[arg-type]
    ):
        with pytest.raises(ValidationError):
            call()
    assert list((project / "data").iterdir()) == []


# --- pinned tasks -----------------------------------------------------------------


def _pinned_pl(tmp_path: Path, fake: FakeCampaignProvider | None = None) -> Path:
    project = new_project(tmp_path)
    add_project_task(
        project, name="teren", command="elevation download", options=PL_SHEET
    )
    with pl_sheets(fake):
        assert download_project(project).ok
    return project


def test_pinned_task_is_offline_noop(tmp_path):
    project = _pinned_pl(tmp_path)
    before = _manifest_bytes(project)
    with patch(
        "kartograf.download.data._create_provider_and_storage",
        side_effect=AssertionError("zrodlo nie powinno byc uzyte"),
    ):
        report = download_project(project)
    assert report.ok and report.tasks[0].outcome == "unchanged"
    assert _manifest_bytes(project) == before


def test_second_project_newer_version_keeps_first_pins(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    first = _pinned_pl(tmp_path, fake)
    before = _manifest_bytes(first)
    (old,) = open_project(first).tasks[0].files
    second = tmp_path / "drugi"
    second.mkdir()
    (second / MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema": "kartograf-project/1",
                "output_dir": "../projekt/data",
                "tasks": [],
            }
        ),
        encoding="utf-8",
    )
    add_project_task(
        second, name="teren", command="elevation download", options=PL_SHEET
    )
    fake.records = {"newest": [REC["84183"]]}
    with pl_sheets(fake):
        report = download_project(second, update="upgrade")
    (new,) = report.project.tasks[0].files
    assert new.path == old.path and new.label.startswith("2025-10-21_84183")
    assert _manifest_bytes(first) == before
    store = tmp_path / "projekt" / "data"
    assert os.path.samefile(store / old.path, store / new.version)
    assert file_digest(store / old.version)[0] == old.sha256
    assert verify_project(first).ok  # standard path moved, the pinned version did not
    with pl_sheets(fake):
        assert download_project(first).tasks[0].outcome == "unchanged"


def test_remove_keeps_store_files(tmp_path):
    project = _pinned_pl(tmp_path)
    store = project / "data"
    before = _store_snapshot(store)
    assert remove_project_task(project, name="teren").tasks == ()
    assert _store_snapshot(store) == before


# --- restoring on another store ------------------------------------------------------


def test_restore_on_empty_store_same_content(tmp_path, monkeypatch):
    project = new_project(tmp_path)
    add_project_task(
        project, name="teren", command="elevation download", options=PL_SHEET
    )
    add_project_task(
        project,
        name="pokrycie",
        command="landcover download",
        options={"product": "bdot10k", "teryt": "1465"},
    )
    with pl_sheets(), bdot(["1465"]):
        assert download_project(project).ok
    pinned = open_project(project).tasks
    colleague = copy_manifest(project, tmp_path / "kolega")
    later = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    monkeypatch.setattr("kartograf._clock.now", lambda: later)
    with pl_sheets(), bdot(["1465"]):
        report = download_project(colleague)
    assert report.ok
    assert [r.outcome for r in report.tasks] == ["restored", "restored"]
    # the same SHA-256 on another day: the bytes go back under the pinned
    # version, the manifest keeps version and label (live test 0.8.0)
    assert report.project.tasks == pinned
    (old,) = pinned[1].files
    assert old.label == "2026-10-12"
    assert report.tasks[1].pinned == (old,) and report.tasks[1].unpinned == ()
    assert file_digest(colleague / "data" / old.version)[0] == old.sha256
    assert verify_project(colleague).ok


def test_restore_conflict_keeps_pin(tmp_path):
    project = _pinned_pl(tmp_path)
    colleague = copy_manifest(project, tmp_path / "kolega")
    before = _manifest_bytes(colleague)
    changed = FakeCampaignProvider({"newest": [REC["84183"]]})
    changed.version = "v2"  # the source serves other bytes under the same campaign
    with pl_sheets(changed):
        report = download_project(colleague)
    (result,) = report.tasks
    assert result.outcome == "failed" and not report.ok
    assert result.errors[0].startswith(f"{G}: zrodlo ma inna tresc niz przypieta")
    assert _manifest_bytes(colleague) == before
    (pin,) = report.project.tasks[0].files
    stored = [
        p for p in (colleague / "data").rglob(f"{G}.asc") if "versions" in p.parts
    ]
    assert len(stored) == 1 and file_digest(stored[0])[0] != pin.sha256


def test_restore_partial_keeps_restored_pins(tmp_path, monkeypatch):
    project = new_project(tmp_path)
    add_project_task(
        project,
        name="pokrycie",
        command="landcover download",
        options={"product": "bdot10k", "bbox": BDOT_BBOX},
    )
    with bdot(["0208", "0261"]):
        assert download_project(project).ok
    colleague = copy_manifest(project, tmp_path / "kolega")
    later = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    monkeypatch.setattr("kartograf._clock.now", lambda: later)
    with bdot(["0208", "0261"], FakePackages(fail={"0261"})):
        report = download_project(colleague)
    (result,) = report.tasks
    assert result.outcome == "failed"
    assert [pin.unit for pin in result.pinned] == ["0208"]
    first, second = report.project.tasks[0].files
    assert (first.unit, first.label) == ("0208", "2026-10-12")  # the pin as it was
    assert (colleague / "data" / first.version).is_file()
    assert (second.unit, second.label) == ("0261", "2026-10-12")  # unchanged pin


def test_restore_needs_same_geometry(tmp_path):
    project = new_project(tmp_path)
    area = _shapefile(project)
    add_project_task(
        project,
        name="pokrycie",
        command="landcover download",
        options={"product": "bdot10k", "geometry": os.path.relpath(area)},
    )
    with bdot(["0208"]):
        assert download_project(project).ok
    task = open_project(project).tasks[0]
    assert sorted(task.geometry_sha256 or {}) == [
        "area.dbf",
        "area.prj",
        "area.shp",
        "area.shx",
    ]
    colleague = copy_manifest(project, tmp_path / "kolega")
    for part in ("area.shp", "area.shx", "area.dbf"):
        (colleague / part).write_bytes((project / part).read_bytes())
    (colleague / "area.prj").write_text("inny uklad", encoding="utf-8")
    packages = FakePackages()
    with bdot(["0208"], packages):
        report = download_project(colleague)
    (result,) = report.tasks
    assert result.outcome == "failed" and packages.calls == []
    assert result.errors[0].startswith("plik geometrii area.shp zmienil sie")


# --- upgrade / force ---------------------------------------------------------------


def _later(monkeypatch) -> datetime:
    moment = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    monkeypatch.setattr("kartograf._clock.now", lambda: moment)
    return moment


def test_upgrade_repins_whole_task(tmp_path, monkeypatch):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    project = _pinned_pl(tmp_path, fake)
    (old,) = open_project(project).tasks[0].files
    fake.records = {"newest": [REC["84183"]]}
    moment = _later(monkeypatch)
    with pl_sheets(fake):
        report = download_project(project, update="upgrade")
    (result,) = report.tasks
    (task,) = report.project.tasks
    assert result.outcome == "updated" and result.unpinned == (old,)
    assert result.pinned == task.files and task.files[0].label.startswith("2025-10-21")
    assert task.pinned_at == moment.isoformat(timespec="seconds")
    assert (project / "data" / old.version).is_file()  # old version stays


def test_upgrade_failure_keeps_all_pins(tmp_path):
    project = new_project(tmp_path)
    options = {"product": "bdot10k", "bbox": BDOT_BBOX}
    add_project_task(
        project, name="pokrycie", command="landcover download", options=options
    )
    with bdot(["0208", "0261"]):
        assert download_project(project).ok
    before = _manifest_bytes(project)
    with bdot(["0208", "0261"], FakePackages(fail={"0261"})):
        report = download_project(project, update="force")
    assert report.tasks[0].outcome == "failed" and not report.ok
    assert _manifest_bytes(project) == before


def test_upgrade_takes_newer_local_version_without_download(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    first = _pinned_pl(tmp_path, fake)
    second = copy_manifest(first, tmp_path / "drugi")
    doc = json.loads((second / MANIFEST_NAME).read_text(encoding="utf-8"))
    doc["output_dir"] = "../projekt/data"  # the same store
    (second / MANIFEST_NAME).write_text(json.dumps(doc), encoding="utf-8")
    fake.records = {"newest": [REC["84183"]]}
    with pl_sheets(fake):
        assert download_project(second, update="upgrade").ok
        downloads = list(fake.downloads)
        report = download_project(first, update="upgrade")
    assert fake.downloads == downloads  # 84183 taken from the store
    assert report.tasks[0].outcome == "updated"
    assert report.project.tasks[0].files == open_project(second).tasks[0].files


def test_upgrade_without_signal_keeps_pin(tmp_path):
    project = new_project(tmp_path)
    add_project_task(
        project,
        name="pokrycie",
        command="landcover download",
        options={"product": "bdot10k", "teryt": "1465"},
    )
    with bdot(["1465"]):
        assert download_project(project).ok
    before = _manifest_bytes(project)
    packages = FakePackages()
    with bdot(["1465"], packages):
        report = download_project(project, update="upgrade")
    assert report.tasks[0].outcome == "unchanged" and packages.calls == []
    (notice,) = report.notices
    assert notice.code == "unverified_local"
    assert notice.message.startswith(
        "pokrycie: landcover/pl_bdot10k_gpkg/teryt/1465.gpkg"
    )
    assert _manifest_bytes(project) == before


class ChangedPackages(FakePackages):
    """BDOT10k packages with other content than ``FakePackages``."""

    def __call__(self, code, output_path, **kwargs):
        package = super().__call__(code, output_path, **kwargs)
        package.path.write_bytes(b"nowe wydanie " + package.path.read_bytes())
        return package


def test_force_same_content_keeps_pin_new_content_repins(tmp_path, monkeypatch):
    project = new_project(tmp_path)
    add_project_task(
        project,
        name="pokrycie",
        command="landcover download",
        options={"product": "bdot10k", "teryt": "1465"},
    )
    with bdot(["1465"]):
        assert download_project(project).ok
    before = _manifest_bytes(project)
    (old,) = open_project(project).tasks[0].files
    _later(monkeypatch)
    packages = FakePackages()
    with bdot(["1465"], packages):
        same = download_project(project, update="force")
    assert packages.calls == ["1465"]  # downloaded again: the same bytes
    assert same.tasks[0].outcome == "unchanged"
    assert _manifest_bytes(project) == before
    with bdot(["1465"], ChangedPackages()):
        changed = download_project(project, update="force")
    (result,) = changed.tasks
    (new,) = changed.project.tasks[0].files
    assert result.outcome == "updated" and result.unpinned == (old,)
    assert new.sha256 != old.sha256 and new.label == "2026-11-03"


def _corrupt_pinned_pl(tmp_path: Path, damage: str):
    """A pinned PL sheet whose version file (also the standard path: the same
    inode) is damaged: ``flip`` keeps its size, ``truncate`` does not."""
    project = _pinned_pl(tmp_path)
    store = project / "data"
    (pin,) = open_project(project).tasks[0].files
    version, standard = store / pin.version, store / pin.path
    good = version.read_bytes()
    bad = good[:-1] + bytes([good[-1] ^ 1]) if damage == "flip" else good[:-5]
    version.write_bytes(bad)
    return project, pin, version, standard, good, bad


@pytest.mark.parametrize("damage", ["flip", "truncate"])
def test_force_repairs_a_corrupt_pinned_version(tmp_path, damage):
    """E2E 0.8.0 P3-1: ``--force`` took the same bytes for 'bez zmian' and left
    the corrupt version; it sets it aside and makes it again, pin unchanged."""
    project, pin, version, standard, good, bad = _corrupt_pinned_pl(tmp_path, damage)
    manifest = _manifest_bytes(project)
    assert not verify_project(project).ok

    with pl_sheets():
        report = download_project(project, update="force")

    assert report.ok and [t.outcome for t in report.tasks] == ["restored"]
    assert report.tasks[0].pinned == (pin,)
    assert _manifest_bytes(project) == manifest
    assert verify_project(project).ok
    assert version.read_bytes() == standard.read_bytes() == good
    assert os.path.samefile(version, standard)
    (aside,) = (p for p in version.parent.parent.iterdir() if p.name.startswith("."))
    assert aside.name.startswith(f".{version.parent.name}.corrupt-")
    assert (aside / version.name).read_bytes() == bad  # nothing was deleted


def test_force_leaves_intact_versions_alone(tmp_path):
    project = _pinned_pl(tmp_path)
    with pl_sheets():
        report = download_project(project, update="force")
    assert report.tasks[0].outcome == "unchanged"
    assert not list((project / "data").rglob(".*corrupt*"))


def test_force_without_a_source_leaves_the_repair_to_the_next_download(tmp_path):
    project, pin, version, _, good, _ = _corrupt_pinned_pl(tmp_path, "flip")
    manifest = _manifest_bytes(project)
    unreachable = FakeCampaignProvider(C14, fail_urls={C14["newest"][0].url})
    with pl_sheets(unreachable):
        report = download_project(project, update="force")
    assert not report.ok and report.tasks[0].outcome == "failed"
    assert _manifest_bytes(project) == manifest
    assert [f.status for f in get_project_status(project).files] == ["missing"]

    with pl_sheets():
        report = download_project(project)
    assert report.tasks[0].outcome == "restored"
    assert verify_project(project).ok and version.read_bytes() == good


def test_force_never_moves_a_version_that_lies_outside_the_store(tmp_path):
    project, pin, version, _, _, bad = _corrupt_pinned_pl(tmp_path, "flip")
    hierarchy = version.parent.parent  # versions/<hierarchy>, holds <label>_<sha8>
    outside = tmp_path / "poza"
    shutil.move(hierarchy, outside)
    hierarchy.symlink_to(outside, target_is_directory=True)
    with pl_sheets():
        report = download_project(project, update="force")
    (result,) = report.tasks
    assert result.outcome == "failed" and "wykracza poza magazyn" in result.errors[0]
    assert (outside / version.parent.name / version.name).read_bytes() == bad
    assert not list(outside.glob(".*corrupt*"))


@pytest.mark.parametrize("damage", ["flip", "truncate"])
def test_status_and_verify_offer_the_repair_of_a_corrupt_version(tmp_path, damage):
    """Both ways to find damage (size: ``status``; bytes: ``verify``) say how
    to repair it: the command that works (``test_force_repairs...``)."""
    project, *_ = _corrupt_pinned_pl(tmp_path, damage)
    (check,) = (
        get_project_status(project) if damage == "truncate" else verify_project(project)
    ).files
    assert check.status == "corrupt" and "--force teren" in check.detail


def test_upgrade_adds_and_removes_files(tmp_path):
    project = new_project(tmp_path)
    add_project_task(
        project, name="laz", command="elevation download", options=LAZ_AREA
    )
    tiles = LazTiles("N-33-131-B-a-1-1-1", "N-33-131-B-a-1-1-2")
    with laz_tiles(tiles):
        assert download_project(project).ok
    first, second = open_project(project).tasks[0].files
    tiles.sheets = ["N-33-131-B-a-1-1-2", "N-33-131-B-a-1-1-3"]
    with laz_tiles(tiles):
        report = download_project(project, update="upgrade")
    (result,) = report.tasks
    kept, added = report.project.tasks[0].files
    assert result.outcome == "updated"
    assert kept == second and added.unit == "81121_1_N-33-131-B-a-1-1-3.laz"
    assert result.pinned == (added,) and result.unpinned == (first,)
    assert (project / "data" / first.version).is_file()


def test_upgrade_only_named_task(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    project = _pinned_pl(tmp_path, fake)
    add_project_task(
        project, name="laz", command="elevation download", options=LAZ_AREA
    )
    tiles = LazTiles("N-33-131-B-a-1-1-1")
    with laz_tiles(tiles):
        assert download_project(project, tasks=["laz"]).ok
    laz_before = open_project(project).tasks[1]
    fake.records = {"newest": [REC["84183"]]}
    tiles.sheets = ["N-33-131-B-a-1-1-2"]
    with pl_sheets(fake), laz_tiles(tiles):
        report = download_project(project, update="upgrade", tasks=["teren"])
    assert [r.name for r in report.tasks] == ["teren"]
    assert report.tasks[0].outcome == "updated"
    assert report.project.tasks[1] == laz_before


def test_upgrade_accepts_changed_geometry(tmp_path):
    import shapefile

    project = new_project(tmp_path)
    area = _shapefile(project)
    add_project_task(
        project,
        name="pokrycie",
        command="landcover download",
        options={"product": "bdot10k", "geometry": os.path.relpath(area)},
    )
    with bdot(["0208"]):
        assert download_project(project).ok
    old = open_project(project).tasks[0]
    with shapefile.Writer(str(area)) as writer:
        writer.field("name", "C", 10)
        ring = [(500000, 300000), (502000, 300000), (502000, 302000), (500000, 300000)]
        writer.poly([ring])
        writer.record("b")
    with bdot(["0208"]):
        # without a mode a pinned task stays as it is (no network)
        assert download_project(project).tasks[0].outcome == "unchanged"
        report = download_project(project, update="upgrade")
    (task,) = report.project.tasks
    assert report.tasks[0].outcome == "updated"
    assert task.files == old.files and task.geometry_sha256 != old.geometry_sha256
