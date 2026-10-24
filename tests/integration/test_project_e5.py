"""A project downloads and verifies E5 products as versioned tasks: the
package of a PL control network (``network``), the CZ quasi-geoid
(``whole_country``) and the mesh tiles of an area (``models3d download``
without new options)."""

import functools

import pytest

from kartograf.download import collections as col
from kartograf.project import (
    add_project_task,
    download_project,
    init_project,
    open_project,
    verify_project,
)
from tests.integration.test_collections_units import MESH_AREA, Router
from tests.integration.test_geodesy import (
    PRPOG_FILES,
    QGZU_FILE,
    _serve_qgzu,
    _zip_answer,
)
from tests.integration.test_mesh_trees import _serve_pages, _serve_tiles
from tests.support.fake_packages import zip_bytes

pytestmark = pytest.mark.usefixtures("frozen_clock")


def test_project_downloads_and_verifies_control_geoid_and_mesh(tmp_path, monkeypatch):
    project = tmp_path / "projekt"
    init_project(project, output_dir=project / "data")
    tasks = {
        "osnowa": (
            "geodesy download",
            {"product": "control", "teryt": "1201", "network": "horizontal"},
        ),
        "kvazigeoid": (
            "geodesy download",
            {"product": "geoid", "country": "cz", "whole_country": True},
        ),
        "mesh": (
            "models3d download",
            {"product": "mesh", "country": "pl", "bbox": MESH_AREA},
        ),
    }
    for name, (command, options) in tasks.items():
        add_project_task(project, name=name, command=command, options=options)
    stored = [dict(task.options) for task in open_project(project).tasks]
    assert stored[:2] == [
        {"product": "control", "teryt": "1201", "network": "horizontal"},
        {"product": "geoid", "country": "cz", "whole_country": True},
    ]
    router = Router()
    package = PRPOG_FILES["horizontal_1201"]
    router.add(
        package["url"], functools.partial(_zip_answer, zip_bytes(package["members"]))
    )
    _serve_qgzu(router, zip_bytes(QGZU_FILE["members"]))
    _serve_pages(router, monkeypatch)
    _serve_tiles(router)
    monkeypatch.setattr(col, "_session", lambda: router)

    result = download_project(project, cache=False)

    assert result.ok, result.errors
    pinned = [
        [file.path for file in task.files] for task in open_project(project).tasks
    ]
    assert pinned[:2] == [
        ["geodesy/pl_control_horizontal_xls/teryt/1201.zip"],
        ["geodesy/cz_qgzu2013_bpv/country/cz.zip"],
    ]
    assert len(pinned[2]) == 4
    assert all(path.startswith("models3d/pl_mesh/2000/7/") for path in pinned[2])
    verified = verify_project(project)
    assert verified.ok, verified.errors
