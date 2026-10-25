"""Survey control networks of PL and CZ and the quasi-geoid models (plan E,
E5) on recorded answers.

PL: one WFS per network (``COUNT=2`` pages of ``tests/fixtures/pl/prpog``;
the gravimetric service of the E0 fixtures), the powiat packages of the
horizontal and vertical network and the archive catalogues of a 1:100 000
sheet. CZ: the point layers of ``BodovaPole`` (``tests/fixtures/cz/
survey_control``). Quasi-geoids: the PL-geoid2021 text file (its real head
and tail) and the QGZU feeds of CUZK.
"""

import dataclasses
import functools
import json
from pathlib import Path

import pyogrio
import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import (
    check_collection,
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import ValidationError
from kartograf.notices import DOWNLOAD_SIZE, UNIT_LIST, WHOLE_COUNTRY_SIZE
from kartograf.sources import registry
from kartograf.sources.descriptor import FeatureBBoxParams
from tests.integration.test_collections_units import (
    GRAV_AREA,
    Response,
    Router,
    _gravity_routes,
    _key,
    _meta,
    recorded,
)
from tests.support.fake_packages import zip_bytes

pytestmark = pytest.mark.usefixtures("frozen_clock")

FIXTURES = Path(__file__).parent.parent / "fixtures"
PRPOG = FIXTURES / "pl" / "prpog" / "real_2026_10_16"
SURVEY = FIXTURES / "cz" / "survey_control" / "real_2026_10_16"
GEOID = FIXTURES / "pl" / "quasigeoid" / "real_2026_10_16"
QGZU = FIXTURES / "cz" / "qgzu" / "real_2026_10_16"
PRPOG_FILES: dict = json.loads((PRPOG / "files.json").read_text(encoding="utf-8"))
GEOID_FILE: dict = json.loads((GEOID / "files.json").read_text(encoding="utf-8"))[
    "geoid2021"
]
QGZU_FILE: dict = json.loads((QGZU / "files.json").read_text(encoding="utf-8"))[
    "kvazigeoid"
]
# The areas of the recorded WFS pages (N,E ranges of the README) and of the
# CZ layers (EPSG:5514, Cesky Tesin).
PL_AREAS = {
    "horizontal": BBox(560000, 240000, 575000, 250000, "EPSG:2180"),
    "vertical": BBox(567600, 240600, 568300, 241200, "EPSG:2180"),
    "magnetic": BBox(500000, 200000, 650000, 300000, "EPSG:2180"),
    "gravity": GRAV_AREA,
}
TESIN = BBox(-452000, -1113000, -449000, -1110000, "EPSG:5514")
# A border area of Cieszyn / Cesky Tesin: PL and CZ parts.
BORDER = BBox(18.55, 49.70, 18.70, 49.78, "EPSG:4326")


@pytest.fixture
def router(monkeypatch) -> Router:
    fake = Router()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _serve_recordings(router: Router, directory: Path) -> None:
    """Every recording of ``directory`` whose headers name its URL."""
    for meta in sorted(directory.glob("*.headers.json")):
        router.add_recorded(meta.with_name(meta.name.removesuffix(".headers.json")))


def _recorded_page_size(monkeypatch) -> None:
    """The WFS of the PL networks with the page size of the recordings (2)."""
    descriptor = registry.get_source("pl.gugik.control")
    channels = tuple(
        dataclasses.replace(
            channel, params=dataclasses.replace(channel.params, page_size=2)
        )
        if isinstance(channel.params, FeatureBBoxParams)
        else channel
        for channel in descriptor.channels
    )
    monkeypatch.setitem(
        registry._SOURCES,
        descriptor.key,
        dataclasses.replace(descriptor, channels=channels),
    )


def _zip_answer(body: bytes, headers: dict | None = None) -> Response:
    sent = {"Content-Type": "application/octet-stream", **(headers or {})}
    return Response(200, {**sent, "Content-Length": str(len(body))}, body)


# --- PL networks ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("network", "layers"),
    [
        ("horizontal", {"fundamentalna_pozioma": 3, "bazowa_pozioma": 3}),
        ("vertical", {"fundamentalna_wysokosciowa": 1, "bazowa_wysokosciowa": 3}),
        (
            "magnetic",
            {"fundamentalna_magnetyczna": 2, "bazowa_magnetyczna": 4, "izogony": 4},
        ),
        (
            "gravity",
            {"fundamentalna_grawimetryczna": 12, "bazowa_grawimetryczna": 6},
        ),
    ],
)
def test_pl_control_bbox_networks(tmp_path, router, monkeypatch, network, layers):
    """Each network is its own WFS and its own segment: one GeoPackage of its
    layers (points of the fundamental and base network; magnetic also the
    isogonic zones) in EPSG:2180, the N,E axes of the service turned into
    E,N coordinates."""
    if network == "gravity":  # the E0 recording of the gravimetric WFS
        _gravity_routes(router)
    else:
        _recorded_page_size(monkeypatch)
        _serve_recordings(router, PRPOG)
    area = PL_AREAS[network]
    report = download_collection(
        product="control",
        country="pl",
        bbox=area,
        network=network,
        root=tmp_path,
        cache=False,
    )
    assert report.ok, report.failed
    (item,) = report.files
    path = item.file.path
    assert path.relative_to(tmp_path).parts[:3] == (
        "geodesy",
        f"pl_control_{network}",
        "bbox",
    )
    assert _layer_counts(path) == layers
    points = next(name for name in layers if name.startswith("bazowa"))
    min_x, min_y, max_x, max_y = pyogrio.read_info(path, layer=points)["total_bounds"]
    assert area.min_x <= min_x <= max_x <= area.max_x  # eastings
    assert area.min_y <= min_y <= max_y <= area.max_y  # northings
    meta = _meta(item.file.version_path)
    assert meta["horizontal_crs"] == "EPSG:2180"
    assert meta["request"]["network"] == network


def _layer_counts(path: Path) -> dict[str, int]:
    return {
        str(name): pyogrio.read_info(path, layer=str(name))["features"]
        for name, _ in pyogrio.list_layers(path)
    }


def test_pl_control_packages_and_archives(tmp_path, router):
    """A powiat gives the package of the horizontal or vertical network; the
    gravimetric network exists only for an area (the error names it); an
    archive of a sheet code is the package of its 1:100 000 sheet, announced
    with its size before the transfer."""
    for network, key in (
        ("horizontal", "horizontal_1201"),
        ("vertical", "vertical_1201"),
    ):
        entry = PRPOG_FILES[key]
        body = zip_bytes(entry["members"])
        router.add(entry["url"], functools.partial(_zip_answer, body))
        report = download_collection(
            product="control",
            teryt="1201",
            network=network,
            root=tmp_path,
            cache=False,
        )
        assert report.ok, report.failed
        (item,) = report.files
        assert item.file.path == (
            tmp_path / f"geodesy/pl_control_{network}_xls/teryt/1201.zip"
        )
        assert item.file.path.read_bytes() == body
        meta = _meta(item.file.version_path)
        assert meta["request"] == {"teryt": "1201", "network": network}
        assert meta["extra"]["source"]["url"] == entry["url"]

    calls = len(router.calls)
    with pytest.raises(ValidationError) as area_only:
        download_collection(
            product="control",
            teryt="1201",
            network="gravity",
            root=tmp_path,
            cache=False,
        )
    assert "--network gravity" in str(area_only.value)
    assert "available only for --bbox/--sheet/--geometry" in str(area_only.value)
    assert "--teryt: horizontal, vertical" in str(area_only.value)
    assert len(router.calls) == calls

    archive = PRPOG_FILES["kartoteki1942_M-34-64"]
    shape = PRPOG_FILES["kartoteki1942_N-33-58"]["members"]  # catalogue cards
    body = zip_bytes(shape)
    router.add(archive["url"], lambda: _zip_answer(body))
    router.heads[_key(archive["url"])] = archive["headers"]
    seen: list[tuple[str, int]] = []
    report = download_collection(
        product="control",
        sheet="M-34-064-D",
        network="archive-1942",
        root=tmp_path,
        cache=False,
        on_notice=lambda n: seen.append((n.code, router.gets(archive["url"]))),
    )
    assert report.ok, report.failed
    assert seen == [(UNIT_LIST, 0), (DOWNLOAD_SIZE, 0)]
    assert "1069061020 B" in report.notices[1].message
    (item,) = report.files
    assert item.unit == "M-34-64"
    assert item.file.path == (
        tmp_path / "geodesy/pl_control_archive-1942/M-34/64/M-34-64.zip"
    )


def test_archive_sheet_without_package_is_a_unit_failure(tmp_path, router):
    """The sheets of an area are units: a sheet the archive does not publish
    (404) fails alone, the other one is stored."""
    found = PRPOG_FILES["kronsztadt60_M-34-64"]
    router.add(found["url"], lambda: _zip_answer(zip_bytes(found["members"])))
    absent = found["url"].replace("M-34-64.zip", "M-34-65.zip")
    router.add(absent, lambda: Response(404, {"Content-Type": "text/html"}, b"<html/>"))
    report = download_collection(
        product="control",
        country="pl",
        bbox=PL_AREAS["horizontal"],
        network="archive-kronsztadt60",
        root=tmp_path,
        cache=False,
    )
    assert [item.unit for item in report.files] == ["M-34-64"]
    (failure,) = report.failed
    assert (failure.unit, failure.kind) == ("M-34-65", "no_coverage")
    stored = report.files[0].file.path
    assert (
        stored
        == tmp_path / "geodesy/pl_control_archive-kronsztadt60/M-34/64/M-34-64.zip"
    )


# --- CZ networks ---------------------------------------------------------------------


def test_cz_control_layers(tmp_path, router):
    """A CZ network is the union of its point layers: ``vertical`` asks only
    layer 44, ``horizontal`` the six ZPBP layers (the points determined in
    ETRS89 are not in the main layers); the GeoPackage keeps the layer
    names of the source in EPSG:5514."""
    _serve_recordings(router, SURVEY)
    vertical = download_collection(
        product="control",
        country="cz",
        bbox=TESIN,
        network="vertical",
        root=tmp_path,
        cache=False,
    )
    assert vertical.ok, vertical.failed
    asked = {
        url.split("/MapServer/", 1)[1].split("/")[0].split("?")[0]
        for _, url in router.calls
    }
    assert asked == {"44"}
    (item,) = vertical.files
    assert item.file.path.relative_to(tmp_path).parts[:2] == (
        "geodesy",
        "cz_control_vertical",
    )
    assert _layer_counts(item.file.path) == {"bod_zvbp": 10}
    meta = _meta(item.file.version_path)
    assert (meta["horizontal_crs"], meta["request"]["network"]) == (
        "EPSG:5514",
        "vertical",
    )

    router.calls.clear()
    horizontal = download_collection(
        product="control",
        country="cz",
        bbox=TESIN,
        network="horizontal",
        root=tmp_path,
        cache=False,
    )
    assert horizontal.ok, horizontal.failed
    asked = {
        url.split("/MapServer/", 1)[1].split("/")[0].split("?")[0]
        for _, url in router.calls
    }
    assert asked == {"18", "20", "2", "4", "6", "8"}
    counts = _layer_counts(horizontal.files[0].file.path)
    assert counts["bod_zpbp"] == counts["pridruzeny_bod_k_bodu_zpbp"] == 1
    assert counts["bod_zpbp_urceny_v_etrs89"] == 1


def test_network_required_with_the_values_of_each_country(tmp_path, router):
    """No ``--network``: the values of the country; an area of PL and CZ
    (``auto``) names the values of each country and those of both (one value
    applies to every country of the request); nothing is asked."""
    with pytest.raises(ValidationError) as cz:
        validate_collection_request(
            product="control", country="cz", bbox=TESIN, root=tmp_path
        )
    assert "--network required" in str(cz.value)
    assert (
        "gnss, horizontal, densification, horizontal-detailed, vertical, "
        "vertical-detailed, gravity" in str(cz.value)
    )
    with pytest.raises(ValidationError) as both:
        validate_collection_request(
            product="control", country="auto", bbox=BORDER, root=tmp_path
        )
    text = str(both.value)
    assert "PL: horizontal, vertical, gravity, magnetic, archive-1942" in text
    assert "(CZ): gnss, horizontal, densification" in text
    assert "common: horizontal, vertical, gravity" in text
    request = validate_collection_request(
        product="control",
        country="auto",
        bbox=BORDER,
        network="vertical",
        root=tmp_path,
    )
    assert sorted(part.segment for part in request.parts) == [
        "geodesy/cz_control_vertical",
        "geodesy/pl_control_vertical",
    ]
    assert router.calls == []


# --- quasi-geoids -------------------------------------------------------------------


def test_geoid_whole_country_only(tmp_path, router):
    """A quasi-geoid model is one national file: an area is an input error
    naming ``--whole-country``; PL stores the text file 1:1 after its size
    notice (an HTML answer is not the model), CZ the ZIP of the ATOM feed
    labelled by the feed's date; a check asks no file."""
    with pytest.raises(ValidationError) as area:
        validate_collection_request(
            product="geoid",
            country="pl",
            bbox=PL_AREAS["vertical"],
            root=tmp_path,
        )
    assert "--whole-country" in str(area.value)

    text = (GEOID / GEOID_FILE["head"]).read_bytes() + (
        GEOID / GEOID_FILE["tail"]
    ).read_bytes()
    answer = {"body": text, "type": "application/octet-stream"}
    router.add(
        GEOID_FILE["url"],
        lambda: Response(
            200,
            {
                "Content-Type": answer["type"],
                "Content-Length": str(len(answer["body"])),
            },
            answer["body"],
        ),
    )
    router.heads[_key(GEOID_FILE["url"])] = GEOID_FILE["headers"]
    pl = download_collection(
        product="geoid",
        country="pl",
        whole_country=True,
        root=tmp_path,
        cache=False,
    )
    assert pl.ok, pl.failed
    (size,) = [n.message for n in pl.notices if n.code == WHOLE_COUNTRY_SIZE]
    assert "42328086 B" in size
    (item,) = pl.files
    assert item.file.path == tmp_path / "geodesy/pl_geoid2021_evrf2007/country/pl.txt"
    assert item.file.path.read_bytes() == text
    meta = _meta(item.file.version_path)
    assert (meta["horizontal_crs"], meta["vertical_crs"]) == ("EPSG:9702", None)

    answer["body"], answer["type"] = b"<html><body>Blad</body></html>", "text/plain"
    broken = download_collection(
        product="geoid",
        country="pl",
        whole_country=True,
        root=tmp_path,
        update="force",
        cache=False,
    )
    (failure,) = broken.failed
    assert failure.kind == "download"
    assert len(list((tmp_path / "geodesy/pl_geoid2021_evrf2007").rglob("*.txt"))) == 2

    body = zip_bytes(QGZU_FILE["members"])
    _serve_qgzu(router, body)
    cz = download_collection(
        product="geoid",
        country="cz",
        whole_country=True,
        root=tmp_path,
        cache=False,
    )
    assert cz.ok, cz.failed
    (item,) = cz.files
    assert item.file.path == tmp_path / "geodesy/cz_qgzu2013_bpv/country/cz.zip"
    assert item.file.path.read_bytes() == body
    assert item.file.label == "2021-02-22"
    meta = _meta(item.file.version_path)
    assert meta["horizontal_crs"] == "EPSG:4258"

    gets = router.gets(QGZU_FILE["url"])
    (current,) = check_collection(
        product="geoid",
        country="cz",
        whole_country=True,
        root=tmp_path,
        cache=False,
    ).items
    assert (current.status, current.available_label) == ("current", "2021-02-22")
    assert router.gets(QGZU_FILE["url"]) == gets


def _serve_qgzu(router: Router, body: bytes) -> None:
    """The service and dataset feeds of QGZU and the file ``body`` (the
    dataset feed names its length instead of the 58 MB of the real file)."""
    router.add_recorded(QGZU / "qgzu_service.xml")
    dataset = QGZU / "qgzu_dataset.xml"
    meta = json.loads((QGZU / "qgzu_dataset.xml.headers.json").read_text())
    length = f'length="{QGZU_FILE["headers"]["Content-Length"]}"'.encode()
    feed = dataset.read_bytes().replace(length, f'length="{len(body)}"'.encode())
    router.add(meta["url"], lambda: recorded(dataset, feed))
    router.add(QGZU_FILE["url"], lambda: _zip_answer(body, QGZU_FILE["headers"]))
