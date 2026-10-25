"""A project can download and verify names and maps as versioned tasks."""

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.project import (
    add_project_task,
    download_project,
    init_project,
    verify_project,
)
from tests.integration.test_collections_units import (
    CUZK,
    FILES,
    Response,
    Router,
    _key,
)
from tests.integration.test_names import COLLECTIONS, WORLD
from tests.support.fake_packages import zip_bytes

pytestmark = pytest.mark.usefixtures("frozen_clock")


def test_project_downloads_and_verifies_world_names_and_ztm_sheet(
    tmp_path, monkeypatch
):
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    add_project_task(
        project,
        name="nazwy-swiata",
        command="names download",
        options={
            "product": "world",
            "country": "pl",
            "bbox": BBox(-74.02, 40.69, -73.92, 40.79, "EPSG:4326"),
        },
    )
    add_project_task(
        project,
        name="mapa-cz",
        command="maps download",
        options={
            "product": "topographic",
            "country": "cz",
            "sheet": "0510-D-11",
            "scale": "1:10000",
            "format": "TIFF",
        },
    )
    session = Router()
    endpoint = "https://ogcapi.geoportal.gov.pl/res/ims/maps/PRNG/apiFeatures"
    session.add(
        f"{endpoint}/collections",
        lambda: Response(
            200, {"Content-Type": "application/json"}, COLLECTIONS.read_bytes()
        ),
        {"f": "json"},
    )
    session.add(
        f"{endpoint}/collections/PolskaNazwaGeograficznaSwiata/items",
        lambda: Response(200, {"Content-Type": "application/json"}, WORLD.read_bytes()),
        {"f": "json", "bbox": "-74.02,40.69,-73.92,40.79", "limit": "10000"},
    )
    session.add_recorded(CUZK / "klady_2_where_0510-D-11.json")
    entry = FILES["cz_ztm10_tiff_0510-D-11"]
    body = zip_bytes(["0510D11.tif", "0510D11.tfw"])
    session.add(
        entry["url"],
        lambda: Response(
            200, {**entry["headers"], "Content-Length": str(len(body))}, body
        ),
    )
    session.heads[_key(entry["url"])] = entry["headers"]
    monkeypatch.setattr(col, "_session", lambda: session)

    result = download_project(project, cache=False)
    assert result.ok, result.errors
    verified = verify_project(project)
    assert verified.ok, verified.errors
    files = [
        path
        for path in (project / "data").rglob("*")
        if path.suffix in (".gpkg", ".zip") and "versions" not in path.parts
    ]
    assert {path.suffix for path in files} == {".gpkg", ".zip"}
    assert len(files) == 2
    assert {path.parent.relative_to(project / "data").as_posix() for path in files} == {
        "names/pl_prng_world/bbox",
        "maps/cz_ztm_10000_sjtsk_tiff/0510/D/11",
    }
