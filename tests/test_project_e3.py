"""A project downloads and verifies the RCN export of a powiat and the CZ
cadastral map of one cadastral area as versioned tasks (``ku``, ``format``)."""

import pytest

from kartograf.download import collections as col
from kartograf.project import (
    add_project_task,
    download_project,
    init_project,
    open_project,
    verify_project,
)
from tests.test_collections_units import Response, Router, _key
from tests.test_cz_cadastral_map import FILES as KM_FILES
from tests.test_cz_cadastral_map import serve_package
from tests.test_rcn import FILES as RCN_FILES
from tests.test_rcn import RECORDED_ZIP

pytestmark = pytest.mark.usefixtures("frozen_clock")


def test_project_downloads_and_verifies_rcn_and_cz_cadastral_map(tmp_path, monkeypatch):
    project = tmp_path / "projekt"
    init_project(project, output_dir=project / "data")
    add_project_task(
        project,
        name="ceny",
        command="cadastre download",
        options={"product": "prices", "teryt": "1201"},
    )
    add_project_task(
        project,
        name="mapa-ku",
        command="cadastre download",
        options={"product": "map", "ku": "623164", "format": "SHP"},
    )
    assert [dict(task.options) for task in open_project(project).tasks] == [
        {"product": "prices", "teryt": "1201"},
        {"product": "map", "ku": "623164", "format": "SHP"},
    ]
    router = Router()
    rcn = RCN_FILES["rcn_1201"]
    body = RECORDED_ZIP.read_bytes()
    headers = {**rcn["headers"], "Content-Length": str(len(body))}
    router.add(rcn["url"], lambda: Response(200, headers, body))
    router.heads[_key(rcn["url"])] = rcn["headers"]
    serve_package(router, "km_shp_623164", KM_FILES["km_shp_623164"]["members"])
    monkeypatch.setattr(col, "_session", lambda: router)

    result = download_project(project, cache=False)

    assert result.ok, result.errors
    pinned = [file.path for task in open_project(project).tasks for file in task.files]
    assert pinned == [
        "cadastre/pl_rcn/teryt/1201.gpkg",
        "cadastre/cz_km_shp/ku/623164.zip",
    ]
    verified = verify_project(project)
    assert verified.ok, verified.errors
