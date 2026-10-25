"""A project downloads and verifies the E1 elevation products as tasks."""

import pytest

from kartograf.download import collections as col
from kartograf.download import cz_contours
from kartograf.project import (
    add_project_task,
    download_project,
    init_project,
    verify_project,
)
from tests.integration.test_cz_contours import FakeOpenzu
from tests.integration.test_nmt_100m import KRAKOW, FakeGugik

pytestmark = pytest.mark.usefixtures("frozen_clock")


def test_project_nmt_100m_voivodeship_and_contours(tmp_path, monkeypatch):
    """``elevation download`` tasks: NMT 100 m of an area (the voivodeship
    file) and the contours of an SM5 sheet (``format``); both verified."""
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    add_project_task(
        project,
        name="nmt-100m",
        command="elevation download",
        options={
            "product": "nmt",
            "resolution": "100m",
            "country": "pl",
            "bbox": KRAKOW,
        },
    )
    add_project_task(
        project,
        name="warstwice",
        command="elevation download",
        options={"product": "contours", "format": "SHP", "sheet": "CTES96"},
    )
    monkeypatch.setattr(col, "_session", FakeGugik)
    openzu = FakeOpenzu()
    monkeypatch.setattr(cz_contours, "_session", lambda: openzu)

    result = download_project(project, cache=False)
    assert result.ok, result.errors
    verified = verify_project(project)
    assert verified.ok, verified.errors
    data = project / "data"
    assert sorted(
        path.relative_to(data).as_posix()
        for path in data.rglob("*.zip")
        if "versions" not in path.parts
    ) == ["contours/cz_zabaged_shp/CTES/96/CTES96.zip", "nmt/pl_1992_100m/teryt/12.zip"]
