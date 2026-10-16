"""CZ cadastral map (katastralni mapa) by cadastral area (KU): recorded
2026-10-16 heads and member lists of the KU 623164 packages in four formats
(``tests/fixtures/cz/cadastral_map/real_2026_10_16``), the RUIAN
``KatastralniUzemi`` layer at the Tesin envelope and the heads of its three
SHP packages (``tests/fixtures/cuzk/real_2026_10_16``,
``tests/fixtures/pl/e0/real_2026_10_16/files.json``). Package bodies are
small ZIPs built from the real member names (the three KU of the area: the
member names of KU 623164 under their own code)."""

import json
from pathlib import Path

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    check_collection,
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import ValidationError
from kartograf.notices import UNIT_LIST
from kartograf.sources import registry
from tests.fake_packages import zip_bytes
from tests.test_collections_units import CUZK, Response, Router, _key
from tests.test_collections_units import FILES as E0_FILES

pytestmark = pytest.mark.usefixtures("frozen_clock")

FIXTURES = Path(__file__).parent / "fixtures/cz/cadastral_map/real_2026_10_16"
FILES: dict = json.loads((FIXTURES / "files.json").read_text(encoding="utf-8"))
SOURCE = registry.get_source("cz.cuzk.cadastral_map")
# RUIAN: 696137 Mosty u Ceskeho Tesina, 753521 Stanislavice, 652954 Chotebuz
AREA = BBox(-452000, -1112000, -450000, -1110500, "EPSG:5514")
AREA_KU = ["652954", "696137", "753521"]
SHP_MEMBERS = [
    name.removeprefix("623164/") for name in FILES["km_shp_623164"]["members"]
]


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


def serve_package(router: Router, key: str, members: list[str]) -> str:
    """A recorded package: GET = small ZIP of ``members``, HEAD = the
    recorded headers (``ETag``, ``Last-Modified``, real size)."""
    entry = {**FILES, **E0_FILES}[key]
    body = zip_bytes(members)
    headers = {**entry["headers"], "Content-Length": str(len(body))}
    router.add(entry["url"], lambda: Response(200, headers, body))
    router.heads[_key(entry["url"])] = entry["headers"]
    return entry["url"]


@pytest.fixture
def router(monkeypatch) -> Router:
    fake = Router()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


@pytest.mark.parametrize("fmt", ["SHP", "DXF", "DGN", "VFK"])
def test_cz_km_ku_package_in_each_format(tmp_path, router, fmt):
    """``--ku 623164 --format F``: the package from the URL template of the
    format, stored 1:1 in the segment of the format (EPSG:5514 sidecar)."""
    key = f"km_{fmt.lower()}_623164"
    url = serve_package(router, key, FILES[key]["members"])

    report = download_collection(
        product="map", ku="623164", format=fmt, output_dir=tmp_path, cache=False
    )

    assert report.ok, report.failed
    (item,) = report.files
    assert item.file.path == tmp_path / f"cadastre/cz_km_{fmt.lower()}/ku/623164.zip"
    meta = _meta(item.file.version_path)
    assert meta["dataset"] == SOURCE.key
    assert meta["horizontal_crs"] == "EPSG:5514"
    assert meta["request"] == {"ku": "623164", "format": fmt}
    assert [call for call in router.calls if call[0] == "GET"] == [("GET", url)]


def test_cz_km_selection_checked_before_any_request(tmp_path):
    """No ``--format`` names the four formats; ``--ku`` is CZ only and has
    six digits; a national file does not exist - the error names the
    selections of the CZ map (an area is a bbox or a geometry, CZ has no
    collection sheet areas)."""
    with pytest.raises(
        ValidationError, match="^--format wymagane: SHP, DXF, DGN, VFK$"
    ):
        validate_collection_request(product="map", ku="623164", output_dir=tmp_path)
    with pytest.raises(ValidationError, match="--ku to kod katastralniho uzemi"):
        validate_collection_request(
            product="map", ku="623164", country="pl", format="SHP", output_dir=tmp_path
        )
    with pytest.raises(ValidationError, match="6 cyfr, np. 623164"):
        validate_collection_request(
            product="map", ku="62316", format="SHP", output_dir=tmp_path
        )
    with pytest.raises(ValidationError) as national:
        validate_collection_request(
            product="map",
            country="cz",
            whole_country=True,
            format="SHP",
            output_dir=tmp_path,
        )
    assert str(national.value) == (
        "--whole-country: map (CZ) nie ma pliku krajowego; dostepne: --ku <6 cyfr> "
        "(paczka katastralniho uzemi), --bbox/--geometry (katastralni uzemi obszaru)"
    )


def test_cz_km_area_ku_discovery_and_etag(tmp_path, router):
    """An area: its KU from RUIAN (``Info:`` with the codes), one package
    each with the area as ``extra.parent_request``; the second run compares
    the ``ETag`` by ``HEAD`` and downloads nothing."""
    router.add_recorded(CUZK / "ruian_7_bbox_tesin.json")
    urls = [
        serve_package(router, f"cz_km_shp_{code}", [f"{code}/{m}" for m in SHP_MEMBERS])
        for code in AREA_KU
    ]
    request = dict(
        product="map", country="cz", bbox=AREA, format="SHP", output_dir=tmp_path
    )

    first = download_collection(**request, cache=False)

    assert first.ok, first.failed
    assert [f.file.path.relative_to(tmp_path).as_posix() for f in first.files] == [
        f"cadastre/cz_km_shp/ku/{code}.zip" for code in AREA_KU
    ]
    (listed,) = [n for n in first.notices if n.code == UNIT_LIST]
    assert listed.text == "map: katastralni uzemi obszaru wg RUIAN (3): " + ", ".join(
        AREA_KU
    )
    meta = _meta(first.files[0].file.version_path)
    assert meta["request"] == {"ku": "652954", "format": "SHP"}
    assert meta["extra"]["parent_request"]["bbox"] == [
        -452000.0,
        -1112000.0,
        -450000.0,
        -1110500.0,
    ]
    assert (
        meta["extra"]["http"]["etag"] == E0_FILES["cz_km_shp_652954"]["headers"]["ETag"]
    )

    plan = check_collection(**request, cache=False)
    assert [(i.unit, i.status) for i in plan.items] == [
        (code, "current") for code in AREA_KU
    ]
    second = download_collection(**request, cache=False)
    assert [f.file.status for f in second.files] == ["local"] * 3
    # the default mode asks no source for local packages (ADR-036 erratum 3)
    assert all(f.file.unverified == "unchecked" for f in second.files)
    assert sum(router.gets(url) for url in urls) == 3


def test_cz_km_missing_ku_fails_alone(tmp_path, router):
    """One KU of the area without a package (HTTP 404): that unit fails as
    ``no_coverage``, the other packages are stored."""
    router.add_recorded(CUZK / "ruian_7_bbox_tesin.json")
    for code in ("652954", "753521"):
        serve_package(router, f"cz_km_shp_{code}", [f"{code}/{m}" for m in SHP_MEMBERS])
    missing = E0_FILES["cz_km_shp_696137"]["url"]
    router.add(
        missing,
        lambda: Response(404, {"Content-Type": "text/html"}, b"<html>404</html>"),
    )

    report = download_collection(
        product="map",
        country="cz",
        bbox=AREA,
        format="SHP",
        output_dir=tmp_path,
        cache=False,
    )

    assert not report.ok
    assert [f.unit for f in report.files] == ["652954", "753521"]
    (failure,) = report.failed
    assert (failure.unit, failure.kind) == ("696137", "no_coverage")
