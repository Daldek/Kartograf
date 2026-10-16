"""Project API: ``init_project``, ``open_project``, ``add_project_task``,
``remove_project_task`` (ADR-040, spec 3.1-3.2, 4.4-4.5)."""

import json
import shutil
from pathlib import Path

import pytest

from kartograf import (
    BBox,
    ValidationError,
    add_project_task,
    download_data,
    init_project,
    open_project,
    remove_project_task,
)
from kartograf.project.manifest import MANIFEST_NAME
from tests.project_fixtures import PL_SHEET, G
from tests.test_validate_request import _shapefile


def _manifest(project: Path) -> dict:
    return json.loads((project / MANIFEST_NAME).read_text(encoding="utf-8"))


def test_init_creates_store_and_refuses_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    project = init_project("projekt", output_dir="projekt/data")
    assert project.directory == tmp_path / "projekt"
    assert project.output_dir == tmp_path / "projekt" / "data"
    assert project.output_dir.is_dir() and project.tasks == ()
    assert _manifest(tmp_path / "projekt") == {
        "schema": "kartograf-project/1",
        "output_dir": "data",
        "tasks": [],
    }
    before = (tmp_path / "projekt" / MANIFEST_NAME).read_bytes()
    with pytest.raises(ValidationError) as caught:
        init_project("projekt", output_dir="inny")
    assert str(caught.value) == (
        f"projekt juz istnieje: {tmp_path / 'projekt' / MANIFEST_NAME}"
    )
    assert (tmp_path / "projekt" / MANIFEST_NAME).read_bytes() == before
    assert not (tmp_path / "inny").exists()


def test_paths_saved_relative_to_project(tmp_path, monkeypatch):
    work = tmp_path / "praca"
    work.mkdir()
    monkeypatch.chdir(work)
    area = _shapefile(work)
    shared = tmp_path / "wspolny"
    init_project("../projekt", output_dir="../magazyn")
    assert _manifest(tmp_path / "projekt")["output_dir"] == "../magazyn"
    project = add_project_task(
        "../projekt",
        name="gleby",
        command="soil hsg",
        options={"geometry": Path("area.shp"), "depth": "0-5cm"},
    )
    add_project_task(
        tmp_path / "projekt",
        name="gleby-abs",
        command="soil hsg",
        options={"geometry": area, "depth": "0-5cm"},
    )
    tasks = _manifest(tmp_path / "projekt")["tasks"]
    assert tasks[0]["options"] == {"geometry": "../praca/area.shp", "depth": "0-5cm"}
    assert tasks[1]["options"]["geometry"] == area.as_posix()
    assert project.output_dir == tmp_path / "magazyn"
    init_project(tmp_path / "drugi", output_dir=shared)
    assert _manifest(tmp_path / "drugi")["output_dir"] == shared.as_posix()


def test_moved_project_with_store_resolves(tmp_path):
    init_project(
        tmp_path / "a" / "projekt", output_dir=tmp_path / "a" / "projekt" / "data"
    )
    manifest = tmp_path / "a" / "projekt" / MANIFEST_NAME
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["output_dir"] = "data"  # relative: moves together with the project
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    shutil.move(tmp_path / "a", tmp_path / "b")
    project = open_project(tmp_path / "b" / "projekt")
    assert project.output_dir == tmp_path / "b" / "projekt" / "data"
    assert project.output_dir.is_dir()


def test_missing_store_dir_is_error(tmp_path):
    project = init_project(tmp_path / "p", output_dir=tmp_path / "magazyn")
    project.output_dir.rmdir()
    for operation in (
        lambda: add_project_task(
            tmp_path / "p", name="t", command="elevation download", options=PL_SHEET
        ),
        lambda: remove_project_task(tmp_path / "p", name="t"),
    ):
        with pytest.raises(ValidationError) as caught:
            operation()
        assert str(caught.value).startswith(
            f"magazyn projektu nie istnieje: {tmp_path / 'magazyn'}; "
        )
    assert open_project(tmp_path / "p").tasks == ()  # reading needs no store


def test_add_records_library_arguments_in_json_form(tmp_path):
    init_project(tmp_path / "p", output_dir=tmp_path / "data")
    project = add_project_task(
        tmp_path / "p",
        name="krakow-nmt",
        command="elevation download",
        options={
            "product": "nmt",
            "bbox": BBox(566000, 243000, 569000, 246000, "EPSG:2180"),
            "country": "pl",
            "sheet_system": "1992",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
            "year": 2025,
            "all_campaigns": False,
            "layer": None,
        },
    )
    (task,) = _manifest(tmp_path / "p")["tasks"]
    assert task == {
        "name": "krakow-nmt",
        "command": "elevation download",
        "options": {
            "product": "nmt",
            "bbox": [566000, 243000, 569000, 246000],
            "bbox_crs": "EPSG:2180",
            "country": "pl",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
            "sheet_system": "1992",
            "year": 2025,
        },
        "pinned_at": None,
        "kartograf_version": None,
        "files": [],
    }
    assert project.tasks[0].pinned_at is None and project.tasks[0].files == ()


def test_add_validates_without_network(tmp_path):
    init_project(tmp_path / "p", output_dir=tmp_path / "data")
    before = (tmp_path / "p" / MANIFEST_NAME).read_bytes()
    choice = {"product": "nmt", "sheet": G, "resolution": "1m"}  # no vertical CRS
    with pytest.raises(ValidationError) as library:
        download_data(output_dir=tmp_path / "data", cache=False, **choice)
    with pytest.raises(ValidationError) as caught:
        add_project_task(
            tmp_path / "p", name="teren", command="elevation download", options=choice
        )
    assert str(caught.value) == str(library.value)
    assert (tmp_path / "p" / MANIFEST_NAME).read_bytes() == before
    assert list((tmp_path / "data").iterdir()) == []


@pytest.mark.parametrize("name", ["Teren", "-teren", "te ren", "t" * 65, ""])
def test_add_bad_name(tmp_path, name):
    init_project(tmp_path / "p", output_dir=tmp_path / "data")
    with pytest.raises(ValidationError):
        add_project_task(
            tmp_path / "p", name=name, command="elevation download", options=PL_SHEET
        )
    assert open_project(tmp_path / "p").tasks == ()


def test_add_duplicate_name_keeps_first_task(tmp_path, monkeypatch):
    init_project(tmp_path / "p", output_dir=tmp_path / "data")
    add_project_task(
        tmp_path / "p", name="teren", command="elevation download", options=PL_SHEET
    )
    before = (tmp_path / "p" / MANIFEST_NAME).read_bytes()
    with pytest.raises(ValidationError) as caught:
        add_project_task(
            tmp_path / "p",
            name="teren",
            command="soil hsg",
            options={"sheet": "N-34-130-D", "depth": "0-5cm"},
        )
    # the hint works where it is printed: --project unless that is the project
    assert str(caught.value) == (
        "zadanie teren juz istnieje; usun je (kartograf project remove --project "
        f"{tmp_path / 'p'} teren) albo wybierz inna nazwe"
    )
    monkeypatch.chdir(tmp_path / "p")
    with pytest.raises(ValidationError) as here:
        add_project_task(".", name="teren", command="elevation download", options={})
    assert "(kartograf project remove teren)" in str(here.value)
    assert (tmp_path / "p" / MANIFEST_NAME).read_bytes() == before


def test_add_missing_geometry_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    init_project("p", output_dir="data")
    with pytest.raises(ValidationError) as caught:
        add_project_task(
            "p",
            name="gleby",
            command="soil hsg",
            options={"geometry": "brak.gpkg", "depth": "0-5cm"},
        )
    assert str(caught.value) == f"Brak pliku: {tmp_path / 'brak.gpkg'}"
    assert open_project("p").tasks == ()


def test_add_rejects_non_data_command_and_foreign_option(tmp_path):
    init_project(tmp_path / "p", output_dir=tmp_path / "data")
    with pytest.raises(ValidationError):
        add_project_task(
            tmp_path / "p", name="t", command="elevation list-sources", options={}
        )
    with pytest.raises(ValidationError):
        add_project_task(
            tmp_path / "p",
            name="t",
            command="landcover download",
            options={"product": "bdot10k", "teryt": "1465", "vertical_crs": "EVRF2007"},
        )
    assert open_project(tmp_path / "p").tasks == ()


def test_remove_unknown_task_names_the_tasks(tmp_path):
    init_project(tmp_path / "p", output_dir=tmp_path / "data")
    add_project_task(
        tmp_path / "p", name="teren", command="elevation download", options=PL_SHEET
    )
    with pytest.raises(ValidationError) as caught:
        remove_project_task(tmp_path / "p", name="terne")
    assert str(caught.value) == "nieznane zadanie 'terne'; zadania projektu: teren"
    assert remove_project_task(tmp_path / "p", name="teren").tasks == ()
