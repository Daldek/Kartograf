"""A project downloads and verifies BDOO packages as ``landcover download``
tasks: a voivodeship with chosen classes and the voivodeships of an area."""

import pytest

from kartograf.project import (
    add_project_task,
    download_project,
    init_project,
    open_project,
    verify_project,
)
from tests.test_bdoo import BORDER, TRIMMED, route, serve

pytestmark = pytest.mark.usefixtures("frozen_clock")


def test_project_downloads_and_verifies_bdoo(tmp_path, monkeypatch):
    project = tmp_path / "projekt"
    init_project(project, output_dir=project / "data")
    add_project_task(
        project,
        name="bdoo-klasy",
        command="landcover download",
        options={"source": "bdoo", "teryt": "12", "year": 2023, "layers": ["KUIK"]},
    )
    add_project_task(
        project,
        name="bdoo-obszar",
        command="landcover download",
        options={"source": "bdoo", "bbox": BORDER, "year": 2023},
    )
    serve(
        monkeypatch,
        route("bdoo_2023_12", TRIMMED.read_bytes()),
        route("bdoo_2023_24"),
    )

    result = download_project(project, cache=False)

    assert result.ok, result.errors
    pinned = [file.path for task in open_project(project).tasks for file in task.files]
    assert pinned == [
        "landcover/pl_bdoo_2023_kuik/teryt/12.zip",
        "landcover/pl_bdoo_2023/teryt/12.zip",
        "landcover/pl_bdoo_2023/teryt/24.zip",
    ]
    verified = verify_project(project)
    assert verified.ok, verified.errors
