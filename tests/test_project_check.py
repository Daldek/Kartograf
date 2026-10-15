"""Project pin checks: offline store integrity and source plans relative to pins."""

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kartograf import (
    add_project_task,
    check_project,
    download_project,
    open_project,
    project_status,
    verify_project,
)
from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import PROJECT_GEOMETRY_CHANGED
from kartograf.project.commands import task_command
from kartograf.project.manifest import MANIFEST_NAME
from tests.project_fixtures import (
    AUTO_CUTOUT,
    BDOT_ARCHIVE,
    BUILDINGS,
    HSG_SHEET,
    LAZ_AREA,
    PL_SHEET,
    PRG_AREA,
    LazTiles,
    auto_pl_cz,
    bdot,
    collection_sources,
    copy_manifest,
    landcover_sources,
    laz_tiles,
    new_project,
    pl_sheets,
)
from tests.test_cli import _cz_provider_mock
from tests.test_hsg import RasterSoilGrids
from tests.test_manager_campaigns import C14_ALL, REC, FakeCampaignProvider
from tests.test_validate_request import _shapefile

pytestmark = pytest.mark.usefixtures("frozen_clock")


def _pl(tmp_path: Path, fake: FakeCampaignProvider | None = None) -> Path:
    project = new_project(tmp_path)
    add_project_task(
        project, name="teren", command="elevation download", options=PL_SHEET
    )
    with pl_sheets(fake):
        assert download_project(project).ok
    return project


def test_check_collection_files_pair_with_pins(tmp_path):
    """Plan positions of the collection slots (``unit_slot``: bbox and teryt
    of ``boundaries``/``models3d``, the BDOT10k archive on the ``landcover``
    track) are the pinned standard paths: every pin is paired, nothing
    ``added``/``removed``; GUGiK has no cheap signal (``unverifiable``)."""
    project = new_project(tmp_path)
    tasks = {
        "granice": ("boundaries download", PRG_AREA),
        "budynki": ("models3d download", BUILDINGS),
        "archiwum": ("landcover download", BDOT_ARCHIVE),
    }
    for name, (command, options) in tasks.items():
        add_project_task(project, name=name, command=command, options=options)
    with collection_sources() as session:
        assert download_project(project).ok
        transfers = session.gets()
        before = (project / MANIFEST_NAME).read_bytes()
        report = check_project(project)
        assert session.gets() == transfers
    pins = {pin.path for task in open_project(project).tasks for pin in task.files}
    assert report.ok and len(pins) == 3
    assert {item.path for item in report.files} == pins
    assert {item.status for item in report.files} == {"unverifiable"}
    assert (project / MANIFEST_NAME).read_bytes() == before


def test_status_only_stats_files_and_reports_missing(tmp_path):
    project = _pl(tmp_path)
    pin = open_project(project).tasks[0].files[0]
    data = project / "data" / pin.version
    with patch("kartograf.project.operations.file_digest", side_effect=AssertionError):
        assert project_status(project).ok
        data.write_bytes(data.read_bytes() + b"X")
        result = project_status(project)
        assert not result.ok and result.files[0].status == "corrupt"
        data.unlink()
        result = project_status(project)
        assert not result.ok and result.files[0].status == "missing"
    other = new_project(tmp_path, "other")
    add_project_task(
        other, name="teren", command="elevation download", options=PL_SHEET
    )
    result = project_status(other)
    assert not result.ok and result.files == () and result.not_downloaded == ("teren",)


@pytest.mark.parametrize(
    "damage",
    ["data", "digest", "size", "label", "sidecar", "symlink", "standard_symlink"],
)
def test_verify_rejects_corrupt_data_and_sidecars_without_mutation(tmp_path, damage):
    project = _pl(tmp_path)
    before = (project / MANIFEST_NAME).read_bytes()
    pin = open_project(project).tasks[0].files[0]
    data = project / "data" / pin.version
    sidecar = data.with_name(data.name + ".meta.json")
    if damage == "data":
        raw = data.read_bytes()
        data.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    elif damage == "symlink":
        outside = tmp_path / "outside"
        outside.write_bytes(data.read_bytes())
        data.unlink()
        data.symlink_to(outside)
    elif damage == "standard_symlink":
        outside = tmp_path / "outside"
        outside.write_bytes(data.read_bytes())
        standard = project / "data" / pin.path
        standard.unlink()
        standard.symlink_to(outside)
    elif damage == "sidecar":
        sidecar.write_text("{", encoding="utf-8")
    else:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        if damage == "digest":
            meta["sha256"] = "0" * 64
        elif damage == "size":
            meta["size_bytes"] += 1
        else:
            meta["extra"]["version"]["label"] = "different"
        sidecar.write_text(json.dumps(meta), encoding="utf-8")
    result = verify_project(project)
    assert result.files[0].status == "corrupt" and not result.ok
    assert (project / MANIFEST_NAME).read_bytes() == before


def test_verify_copy_of_store_with_hardlinks(tmp_path):
    project = _pl(tmp_path)
    copied = copy_manifest(project, tmp_path / "copy")
    shutil.copytree(
        project / "data", copied / "data", dirs_exist_ok=True, copy_function=os.link
    )
    result = verify_project(copied)
    assert result.ok
    assert all(item.status == "ok" for item in result.files)


def test_check_compares_with_pin_not_current_store_version(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    project = _pl(tmp_path, fake)
    old = open_project(project).tasks[0].files[0]
    copied = copy_manifest(project, tmp_path / "second")
    doc = json.loads((copied / MANIFEST_NAME).read_text(encoding="utf-8"))
    doc["output_dir"] = "../projekt/data"
    (copied / MANIFEST_NAME).write_text(json.dumps(doc), encoding="utf-8")
    fake.records = {"newest": [REC["84183"]]}
    with pl_sheets(fake):
        assert download_project(copied, update="upgrade").ok
        before = (project / MANIFEST_NAME).read_bytes()
        result = check_project(project)
    assert result.ok and result.files[0].status == "newer"
    assert result.files[0].pinned_label == old.label
    assert result.files[0].available_label != old.label
    assert (project / MANIFEST_NAME).read_bytes() == before
    assert verify_project(project).ok


def test_check_matches_campaigns_with_same_standard_path_by_label(tmp_path):
    project = new_project(tmp_path)
    add_project_task(
        project,
        name="teren",
        command="elevation download",
        options={**PL_SHEET, "all_campaigns": True},
    )
    fake = FakeCampaignProvider({"newest": [REC["84183"]], "all": C14_ALL})
    with pl_sheets(fake):
        assert download_project(project).ok
        pins = open_project(project).tasks[0].files
        assert len(pins) > 1 and len({pin.path for pin in pins}) == 1
        report = check_project(project)
    assert report.ok
    assert len(report.files) == len(pins)
    assert [item.status for item in report.files] == ["current"] * len(pins)
    assert {item.pinned_label for item in report.files} == {pin.label for pin in pins}


def test_check_cz_sm5_sheet_uses_http_signal(tmp_path):
    from kartograf.providers.cuzk.sheets import SheetInfo

    project = new_project(tmp_path)
    add_project_task(
        project,
        name="cz",
        command="elevation download",
        options={
            "product": "nmt",
            "sheet": "CTES96",
            "country": "cz",
            "vertical_crs": "Bpv",
        },
    )
    provider = _cz_provider_mock(resolution="5m")
    provider.sheet_index.sm5_sheet.return_value = SheetInfo(
        sheet="CTES96",
        name="Cesky Tesin 9-6",
        bbox=BBox(-450000, -1114000, -447500, -1112000, "EPSG:5514"),
        podil=0.99,
        in_cz=None,
    )
    with patch("kartograf.providers.cuzk.create_dmr_provider", return_value=provider):
        assert download_project(project).ok
        before = (project / MANIFEST_NAME).read_bytes()
        report = check_project(project)
    assert report.ok and len(report.files) == 1
    assert report.files[0].status == "current"
    assert report.files[0].path == open_project(project).tasks[0].files[0].path
    assert (project / MANIFEST_NAME).read_bytes() == before


def test_check_bbox_cutout_matches_both_country_pins(tmp_path):
    project = new_project(tmp_path)
    add_project_task(
        project, name="granica", command="elevation download", options=AUTO_CUTOUT
    )
    with auto_pl_cz():
        assert download_project(project).ok
        before = (project / MANIFEST_NAME).read_bytes()
        result = check_project(project)
    assert result.ok and len(result.files) == 2
    assert [item.status for item in result.files] == ["unverifiable", "unverifiable"]
    assert {item.path for item in result.files} == {
        pin.path for pin in open_project(project).tasks[0].files
    }
    assert (project / MANIFEST_NAME).read_bytes() == before


def test_check_hsg_new_input_edition_is_newer_without_computation(tmp_path):
    project = new_project(tmp_path)
    add_project_task(
        project,
        name="gleby",
        command="soil hsg",
        options={"sheet": HSG_SHEET, "depth": "0-5cm"},
    )
    source = RasterSoilGrids()
    with landcover_sources(soilgrids=lambda: source):
        assert download_project(project).ok
        source.editions["clay"] = "3.0"
        downloads_before = list(source.downloads)
        report = check_project(project)
    assert report.ok
    assert source.downloads == downloads_before
    assert any(
        item.path.startswith("hsg/") and item.status == "newer" for item in report.files
    )
    assert any(
        item.path.startswith("soil/") and item.status == "newer"
        for item in report.files
    )


def test_check_hsg_failed_input_signal_reports_failure_without_download(tmp_path):
    project = new_project(tmp_path)
    add_project_task(
        project,
        name="gleby",
        command="soil hsg",
        options={"sheet": HSG_SHEET, "depth": "0-5cm"},
    )
    source = RasterSoilGrids()
    with landcover_sources(soilgrids=lambda: source):
        assert download_project(project).ok
        source.editions["clay"] = DownloadError("HTTP 503")
        downloads_before = list(source.downloads)
        report = check_project(project)
    assert not report.ok
    assert source.downloads == downloads_before
    assert {item.status for item in report.files} == {"check_failed", "current"}


def test_check_tracks_new_files_removed_files_unverifiable_and_failures(tmp_path):
    project = new_project(tmp_path)
    add_project_task(
        project, name="laz", command="elevation download", options=LAZ_AREA
    )
    add_project_task(
        project,
        name="pokrycie",
        command="landcover download",
        options={"source": "bdot10k", "teryt": "1465"},
    )
    tiles = LazTiles("N-33-131-B-a-1-1-1", "N-33-131-B-a-1-1-2")
    with laz_tiles(tiles), bdot(["1465"]):
        assert download_project(project).ok
    before = (project / MANIFEST_NAME).read_bytes()
    tiles.sheets = ["N-33-131-B-a-1-1-2", "N-33-131-B-a-1-1-3"]
    with laz_tiles(tiles), bdot(["1465"]):
        report = check_project(project)
    assert {item.status for item in report.files if item.task == "laz"} == {
        "removed",
        "current",
        "added",
    }
    assert {item.status for item in report.files if item.task == "pokrycie"} == {
        "unverifiable"
    }
    assert report.ok and (project / MANIFEST_NAME).read_bytes() == before
    failed_command = replace(
        task_command("elevation download"),
        check=Mock(side_effect=DownloadError("HTTP 503")),
    )
    with patch(
        "kartograf.project.operations.task_command", return_value=failed_command
    ):
        failure = check_project(project, tasks=["laz"])
    assert not failure.ok and all(
        item.status == "check_failed" for item in failure.files
    )
    assert (project / MANIFEST_NAME).read_bytes() == before


def test_check_missing_pin_and_skips_not_downloaded_without_network(tmp_path):
    project = _pl(tmp_path)
    add_project_task(
        project, name="next", command="elevation download", options=PL_SHEET
    )
    pin = open_project(project).tasks[0].files[0]
    (project / "data" / pin.version).unlink()
    with pl_sheets():
        result = check_project(project)
    assert result.not_downloaded == ("next",)
    assert len(result.files) == 1 and result.files[0].status == "missing"
    with patch("kartograf.project.operations.task_command", side_effect=AssertionError):
        result = check_project(project, tasks=["next"])
    assert result.ok and result.files == () and result.not_downloaded == ("next",)


def test_check_changed_geometry_warns_and_keeps_pins(tmp_path):
    import shapefile

    project = new_project(tmp_path)
    area = _shapefile(project)
    add_project_task(
        project,
        name="pokrycie",
        command="landcover download",
        options={"source": "bdot10k", "geometry": os.path.relpath(area)},
    )
    with bdot(["0208"]):
        assert download_project(project).ok
    before = (project / MANIFEST_NAME).read_bytes()
    with shapefile.Writer(str(area)) as writer:
        writer.field("name", "C", 10)
        writer.poly(
            [[(500000, 300000), (502000, 300000), (502000, 302000), (500000, 300000)]]
        )
        writer.record("b")
    seen = []
    with bdot(["0208"]):
        report = check_project(project, on_notice=seen.append)
    assert any(n.code == PROJECT_GEOMETRY_CHANGED for n in report.notices)
    assert report.notices == tuple(seen)
    assert report.ok and (project / MANIFEST_NAME).read_bytes() == before


def test_unknown_task_is_validation_error(tmp_path):
    project = _pl(tmp_path)
    for call in (project_status, verify_project, check_project):
        with pytest.raises(ValidationError):
            call(project, tasks=["missing"])
