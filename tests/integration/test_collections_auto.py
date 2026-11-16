"""``--country auto`` of the collections in PL and CZ.

The countries of ``auto`` come from RECTANGULAR envelopes, so an area deep
inside one country also reaches the other one, where the source has no data
for it (a PL-only area at Cieszyn: no cadastral area in RUIAN, no CUZK map
sheet). That country is the failure of its own part; the other one still runs
and its result makes the request a success with a warning - the rule of
``download_data`` (SCOPE 3.2, ARCHITECTURE 4.6); an explicit country and the
failure of every country stay failures.

Real recorded answers of the CUZK services and the EGiB WFS; the session of
the collections is replaced by one that serves both countries.
"""

import pytest

from kartograf.core.bbox import BBox
from kartograf.download import collections as col
from kartograf.download.collections import check_collection, download_collection
from kartograf.exceptions import NoCoverageError
from kartograf.notices import AUTO_PARTIAL_SUCCESS, CHECK_FAILED
from tests.integration.test_collections_units import (
    CUZK,
    INDEX,
    MAPS_GFI,
    Response,
    Router,
    recorded,
)
from tests.integration.test_cz_cadastral_map import AREA_KU, SHP_MEMBERS, serve_package
from tests.unit.test_feature_bbox import EGIB_ENDPOINT, EGIB_RURAL, FakeService, wfs

pytestmark = pytest.mark.usefixtures("frozen_clock")

# PL side of Cieszyn (inside the envelope of CZ, no CZ territory) and the CZ
# side (Cesky Tesin, inside the envelope of PL)
PL_ONLY = BBox(18.640, 49.745, 18.650, 49.750, "EPSG:4326")
CZ_ONLY = BBox(18.600, 49.742, 18.610, 49.746, "EPSG:4326")
RUIAN_KU = "https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer/7/query"
KLADY_2 = (
    "https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/2/query"
)
CADASTRAL_MAP = {"product": "map", "country": "auto", "format": "SHP", "cache": False}


def _answer(status: int = 400) -> Response:
    return Response(status, {"Content-Type": "text/html"}, b"<html>odmowa</html>")


class BothCountries:
    """One session for the collections: the EGiB WFS of GUGiK (``egib``: the
    route of the ``FakeService``), every other service of both countries (the
    ``Router``)."""

    def __init__(self, router: Router, egib) -> None:
        self.router = router
        self.egib = FakeService(egib)

    def get(self, url, params=None, timeout=None, **kwargs):
        service = self.egib if url == EGIB_ENDPOINT else self.router
        return service.get(url, params=params, timeout=timeout, **kwargs)

    def head(self, url, **kwargs):
        return self.router.head(url, **kwargs)


@pytest.fixture
def router(monkeypatch) -> Router:
    fake = Router()
    monkeypatch.setattr(
        col,
        "_session",
        lambda: BothCountries(fake, wfs("egib_capabilities.xml", EGIB_RURAL)),
    )
    return fake


def _use_egib(monkeypatch, router: Router, egib) -> None:
    monkeypatch.setattr(col, "_session", lambda: BothCountries(router, egib))


def _no_cadastral_area(router: Router) -> None:
    router.add_prefix(RUIAN_KU, lambda: recorded(CUZK / "ruian_7_bbox_outside.json"))


def test_pl_only_area_downloads_pl_when_cz_has_no_cadastral_area(tmp_path, router):
    """Before the fix the empty RUIAN answer ended the whole request with
    ``no_coverage`` and the PL part was never asked."""
    _no_cadastral_area(router)

    report = download_collection(**CADASTRAL_MAP, bbox=PL_ONLY, root=tmp_path)

    assert report.ok
    (item,) = report.files
    assert item.country == "PL" and item.file.path.is_file()
    assert item.file.path.relative_to(tmp_path).parts[:3] == (
        "cadastre",
        "pl_egib",
        "bbox",
    )
    (failure,) = report.failed
    assert (failure.unit, failure.country, failure.kind) == ("CZ", "CZ", "no_coverage")
    assert "cadastral territory (RUIAN)" in failure.error
    (partial,) = [n for n in report.notices if n.code == AUTO_PARTIAL_SUCCESS]
    assert partial.level == "warning"
    assert "part CZ" in partial.message and "downloaded PL" in partial.message


def test_pl_only_area_check_plans_pl_and_warns_about_cz(tmp_path, router):
    _no_cadastral_area(router)

    plan = check_collection(**CADASTRAL_MAP, bbox=PL_ONLY, root=tmp_path)

    assert plan.ok
    assert {item.segment for item in plan.items} == {"cadastre/pl_egib"}
    warnings = [n for n in plan.notices if n.level == "warning"]
    assert [n.code for n in warnings] == [CHECK_FAILED, AUTO_PARTIAL_SUCCESS]
    assert warnings[0].message.startswith("CZ: map: the area does not intersect")
    assert "could not be checked" in warnings[1].message


def test_cz_only_area_keeps_cz_when_the_pl_part_fails(tmp_path, monkeypatch):
    """A failure of a unit at run time is the same rule: the CZ packages are
    stored, the PL objects failed - code 0 with the warning, the failure
    stays in ``failed``."""
    router = Router()
    _use_egib(monkeypatch, router, lambda url, params: _answer(400))
    router.add_prefix(RUIAN_KU, lambda: recorded(CUZK / "ruian_7_bbox_tesin.json"))
    for code in AREA_KU:
        serve_package(router, f"cz_km_shp_{code}", [f"{code}/{m}" for m in SHP_MEMBERS])

    report = download_collection(**CADASTRAL_MAP, bbox=CZ_ONLY, root=tmp_path)

    assert report.ok
    assert [f.unit for f in report.files] == AREA_KU
    assert {f.country for f in report.files} == {"CZ"}
    (failure,) = report.failed
    assert (failure.country, failure.kind) == ("PL", "download")
    (partial,) = [n for n in report.notices if n.code == AUTO_PARTIAL_SUCCESS]
    assert (
        "part PL of the task" in partial.message and "downloaded CZ" in partial.message
    )


def test_every_country_failing_is_a_failure(tmp_path, monkeypatch):
    router = Router()
    _use_egib(monkeypatch, router, lambda url, params: _answer(400))
    _no_cadastral_area(router)

    report = download_collection(**CADASTRAL_MAP, bbox=PL_ONLY, root=tmp_path)

    assert not report.ok and report.files == ()
    assert {(f.country, f.kind) for f in report.failed} == {
        ("CZ", "no_coverage"),
        ("PL", "download"),
    }
    assert not [n for n in report.notices if n.code == AUTO_PARTIAL_SUCCESS]


def test_explicit_country_without_units_stays_no_coverage(tmp_path, router):
    """The same empty answer of RUIAN under ``--country cz`` is the error it
    always was: there is no other country to fall back on."""
    _no_cadastral_area(router)

    with pytest.raises(NoCoverageError, match="any cadastral territory"):
        download_collection(
            **{**CADASTRAL_MAP, "country": "cz"}, bbox=CZ_ONLY, root=tmp_path
        )


def test_no_units_in_any_country_is_one_no_coverage_error(tmp_path, router):
    """Map sheets of BDOT10k (no record in the index of GUGiK) and of ZTM (no
    sheet in the CUZK index) at once: nothing to download in either country."""
    router.add_prefix(
        f"{MAPS_GFI}?", lambda: recorded(INDEX / "gfi_mapy10k_outside.html")
    )
    router.add_prefix(KLADY_2, lambda: recorded(CUZK / "klady_2_bbox_outside.json"))

    with pytest.raises(NoCoverageError) as caught:
        download_collection(
            product="topographic",
            country="auto",
            bbox=PL_ONLY,
            scale="1:10000",
            format="TIFF",
            sheet_system="sjtsk",
            root=tmp_path,
            cache=False,
        )

    text = str(caught.value)
    assert "the index has no records" in text
    assert "the area does not intersect any sheet" in text
