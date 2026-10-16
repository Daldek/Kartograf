"""BDOO: the voivodeship GML packages of GUGiK opendata (plan E, E4).

Fixtures ``tests/fixtures/pl/bdoo`` (recorded 2026-10-16, README there): the
headers and ZIP member lists of four packages and the 404 of an unpublished
release, the class codes of all 112 packages and a real package of 12/2023
trimmed to six files (classes KUIK and SKPP). The PRG powiats of the Krakow
and Jaworzno areas are the recordings of ``tests/fixtures/pl/nmt_100m``.
The other package bodies are small ZIPs built with the recorded member names
(``tests/fake_packages.py``).
"""

import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from kartograf.download import collections as col
from kartograf.exceptions import DownloadError, NoCoverageError, ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.notices import CLASSES_ABSENT, UNIT_LIST
from kartograf.providers.pl.prg import PRG_WFS_ENDPOINT
from kartograf.sources.descriptor import UnitPackageParams
from kartograf.sources.registry import get_source
from tests.conftest import recorded_response
from tests.fake_packages import FakePackageSession, FakeResponse, Route, zip_bytes
from tests.test_nmt_100m import BORDER, KRAKOW, PRG
from tests.test_nmt_100m import FIXTURES as NMT_100M

pytestmark = pytest.mark.usefixtures("frozen_clock")

FIXTURES = Path(__file__).parent / "fixtures" / "pl" / "bdoo"
PACKAGES: dict = json.loads((FIXTURES / "packages.json").read_text(encoding="utf-8"))
CLASSES: dict = json.loads((FIXTURES / "classes.json").read_text(encoding="utf-8"))
TRIMMED = FIXTURES / "real_2026_10_16" / "PL.PZGiK.201.12_2023_trimmed.zip"
YEARS = "2015, 2021, 2022, 2023, 2024, 2025, 2026"


def route(name: str, body: bytes | None = None) -> tuple[str, Route]:
    """The recorded package ``name``: its URL and an answer with ``body``
    (``None``: a small ZIP of the recorded members); a recorded error is
    replayed."""
    entry = PACKAGES[name]
    headers = dict(entry["headers"])
    if "status" in entry:
        return entry["url"], (entry["status"], headers, entry["body"].encode())
    if body is None:
        body = zip_bytes(entry["members"])
    return entry["url"], (200, {**headers, "Content-Length": str(len(body))}, body)


def missing(name: str) -> tuple[str, Route]:
    """The package ``name`` answered by the recorded 404 of the source."""
    _, answer = route("bdoo_2018_12_missing")
    return PACKAGES[name]["url"], answer


class FakeOpendata(FakePackageSession):
    """The packages of ``routes`` and the recorded PRG powiats of the areas
    ``KRAKOW`` and ``BORDER`` (PRG is a GET with query parameters)."""

    def get(self, url: str, params=None, **kwargs) -> FakeResponse:
        if url != PRG_WFS_ENDPOINT:
            return super().get(url, **kwargs)
        self.calls.append(("GET", url))
        bbox = params["BBOX"].removesuffix(",urn:ogc:def:crs:EPSG::2180")
        return recorded_response(NMT_100M / PRG[bbox])


def serve(monkeypatch, *routes: tuple[str, Route]) -> FakeOpendata:
    fake = FakeOpendata(dict(routes))
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


def _members(data: bytes) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.infolist()


@pytest.fixture
def bdoo(tmp_path) -> LandCoverManager:
    return LandCoverManager(tmp_path, "bdoo", cache=False)


# --- registry ------------------------------------------------------------------


def test_release_classes_are_the_union_of_the_recorded_packages():
    """``--layers`` of a release accepts the classes of any of its 16
    voivodeship packages: up to 2023 a package has no file of a class without
    objects there (KUIK is missing in 24/2023), from 2024 each has all 26."""
    params = get_source("pl.gugik.bdoo").channels[0].params
    assert isinstance(params, UnitPackageParams) and params.unit == "woj"
    published = {dict(v.choice)["year"]: v.classes for v in params.variants}
    assert published.keys() == CLASSES["classes"].keys()
    for year, packages in CLASSES["classes"].items():
        assert len(packages) == 16
        union = sorted({code for codes in packages.values() for code in codes})
        assert list(published[year]) == union, year
    assert "KUIK" not in CLASSES["classes"]["2023"]["24"]
    assert len(published["2015"]) == 44
    assert len(published["2023"]) == 37
    assert len(published["2026"]) == 26


@pytest.mark.parametrize(
    ("name", "year"),
    [("bdoo_2015_12", "2015"), ("bdoo_2023_12", "2023"), ("bdoo_2026_12", "2026")],
)
def test_class_pattern_reads_the_recorded_file_names(name, year):
    """The class of a member is the ``OT_<KOD>`` of its file name (2015 with
    the prefix ``PL.PZGIK``, ``.gml`` from 2024); composite objects
    (``__OT_Ciek``), the user file, metadata and XSD are no class files."""
    params = get_source("pl.gugik.bdoo").channels[0].params
    assert isinstance(params, UnitPackageParams) and params.class_pattern
    pattern = re.compile(params.class_pattern)
    found = {
        match.group("code")
        for member in PACKAGES[name]["members"]
        if (match := pattern.search(member.rsplit("/", 1)[-1]))
    }
    assert sorted(found) == CLASSES["classes"][year]["12"]
    assert not any(
        pattern.search(member)
        for member in PACKAGES[name]["members"]
        if "__OT_Ciek" in member or "Uzytkownik" in member or "/XSD/" in member
    )


# --- choice before any request --------------------------------------------------


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({}, f"--year wymagane: {YEARS}$"),
        # the source answers 404 for 2014 and 2016-2020 (packages.json)
        ({"year": 2018}, f"--year 2018: niedostepne; dostepne: {YEARS}$"),
        ({"year": "2023"}, "--year musi byc liczba calkowita"),
    ],
)
def test_bdoo_year_required(bdoo, monkeypatch, options, message):
    fake = serve(monkeypatch)
    with pytest.raises(ValidationError, match=message):
        bdoo.download(teryt="12", **options)
    with pytest.raises(ValidationError, match=message):
        bdoo.check(teryt="12", **options)
    assert fake.calls == []


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"teryt": "1261"}, "bdoo jest publikowane per wojewodztwo - podaj --teryt 12"),
        ({"teryt": "1"}, "Nieprawidlowy kod TERYT '1'"),
        ({"teryt": "12", "format": "GML"}, "--format dziala tylko z --product bdot10k"),
        ({"whole_country": True}, "--whole-country dziala tylko z --product zabaged"),
    ],
)
def test_bdoo_selection_errors(bdoo, monkeypatch, options, message):
    """A powiat code names the voivodeship to ask for; BDOO has no national
    file and no format choice."""
    fake = serve(monkeypatch)
    with pytest.raises(ValidationError, match=message):
        bdoo.download(year=2023, **options)
    assert fake.calls == []


# --- packages ---------------------------------------------------------------------


def test_bdoo_teryt_package_as_published(bdoo, monkeypatch, tmp_path):
    """``--teryt 12 --year 2023``: the package 1:1 in the slot of its
    release, labelled by the year; its size asked before the transfer (no
    notice below 100 MiB)."""
    url, answer = route("bdoo_2023_12", TRIMMED.read_bytes())
    fake = serve(monkeypatch, (url, answer))

    result = bdoo.download(teryt="12", year=2023)

    assert result.ok and not result.notices
    (item,) = result.files
    assert item.unit == "12" and item.file is not None
    file = item.file
    assert file.path == tmp_path / "landcover/pl_bdoo_2023/teryt/12.zip"
    assert (file.status, file.label) == ("new", "2023")
    assert file.path.read_bytes() == answer[2]
    meta = _meta(file.version_path)
    assert (meta["dataset"], meta["product"]) == ("pl.gugik.bdoo", "landcover")
    assert meta["request"] == {"teryt": "12", "year": 2023}
    assert meta["horizontal_crs"] == "EPSG:2180"
    assert meta["extra"]["source"] == {"url": url, "edition": "2023"}
    assert meta["extra"]["version"] == {"label": "2023", "label_source": "edition"}
    assert fake.calls == [("HEAD", url), ("GET", url)]


def test_bdoo_years_separate_slots(bdoo, monkeypatch, tmp_path):
    """Each release has its own slot; the same bytes again are ``unchanged``
    under ``force`` and the local version without a request otherwise; the
    plan has no cheap signal (``unverifiable``)."""
    fake = serve(monkeypatch, route("bdoo_2015_12"), route("bdoo_2023_12"))

    old = bdoo.download(teryt="12", year=2015).files[0].file
    new = bdoo.download(teryt="12", year=2023).files[0].file
    again = bdoo.download(teryt="12", year=2023, update="force").files[0].file
    calls = len(fake.calls)
    local = bdoo.download(teryt="12", year=2023).files[0].file

    assert old is not None and new is not None and again is not None
    assert old.path == tmp_path / "landcover/pl_bdoo_2015/teryt/12.zip"
    assert new.path == tmp_path / "landcover/pl_bdoo_2023/teryt/12.zip"
    assert [(f.status, f.label) for f in (old, new, again)] == [
        ("new", "2015"),
        ("new", "2023"),
        ("unchanged", "2023"),
    ]
    assert local is not None and local.status == "local"
    assert len(fake.calls) == calls
    (item,) = bdoo.check(teryt="12", year=2023).items
    assert (item.track, item.status, item.local_label) == (
        "landcover",
        "unverifiable",
        "2023",
    )
    assert len(fake.calls) == calls


@pytest.mark.parametrize(("area", "units"), [(KRAKOW, ["12"]), (BORDER, ["12", "24"])])
def test_bdoo_woj_units(bdoo, monkeypatch, area, units):
    """An area = the packages of its voivodeships (the first two digits of
    its PRG powiats): Krakow lies in 12, the Jaworzno border reaches 12 and
    24; the plan reads no package."""
    fake = serve(monkeypatch)
    notices = []

    plan = bdoo.check(bbox=area, year=2023, on_notice=notices.append)

    assert [item.unit for item in plan.items] == units
    assert {(i.track, i.status) for i in plan.items} == {("landcover", "missing")}
    assert {item.segment for item in plan.items} == {"landcover/pl_bdoo_2023"}
    assert [n.code for n in notices] == [UNIT_LIST]
    assert notices[0].text.startswith(
        f"bdoo: wojewodztwa obszaru wg PRG ({len(units)})"
    )
    assert "12 (malopolskie)" in notices[0].text
    assert fake.calls == [("GET", PRG_WFS_ENDPOINT)]


def test_bdoo_area_voivodeship_without_package_fails_alone(bdoo, monkeypatch, tmp_path):
    """A voivodeship whose package the source does not publish (404) lands in
    ``failed``; the other one is stored with the area in
    ``extra.parent_request``."""
    serve(monkeypatch, route("bdoo_2023_12"), missing("bdoo_2023_24"))

    result = bdoo.download(bbox=BORDER, year=2023, workers=2)

    assert not result.ok
    assert [item.unit for item in result.files] == ["12"]
    (failure,) = result.failed
    assert failure.unit == "24" and "(HTTP 404)" in failure.error
    stored = result.files[0].file
    assert stored is not None
    assert stored.path == tmp_path / "landcover/pl_bdoo_2023/teryt/12.zip"
    meta = _meta(stored.version_path)
    assert meta["request"] == {"teryt": "12", "year": 2023}
    assert meta["extra"]["parent_request"] == {
        "bbox": [523000.0, 253000.0, 528000.0, 258000.0],
        "bbox_crs": "EPSG:2180",
        "countries": ["PL"],
    }
    assert not (tmp_path / "landcover/pl_bdoo_2023/teryt/24.zip").exists()


def test_bdoo_teryt_without_package_is_no_coverage(bdoo, monkeypatch, tmp_path):
    serve(monkeypatch, missing("bdoo_2023_12"))
    with pytest.raises(NoCoverageError, match=r"\(HTTP 404\)"):
        bdoo.download(teryt="12", year=2023)
    assert not (tmp_path / "landcover").exists()


def test_bdoo_package_without_class_files_is_not_data(bdoo, monkeypatch, tmp_path):
    """A ZIP holding only the user file, metadata and XSD of a package is not
    BDOO data: nothing is stored."""
    names = [m for m in PACKAGES["bdoo_2023_12"]["members"] if "__OT_" not in m]
    serve(monkeypatch, route("bdoo_2023_12", zip_bytes(names)))
    with pytest.raises(DownloadError, match="paczka bez plikow klas obiektow"):
        bdoo.download(teryt="12", year=2023)
    assert not list(tmp_path.rglob("*.zip"))


# --- --layers -----------------------------------------------------------------------


def test_bdoo_layers_filter(bdoo, monkeypatch, tmp_path):
    """``--layers SKPP,KUIK`` keeps the files of those classes in a ZIP of
    their own segment: names, order, dates and bytes of the source members;
    the same package filtered again gives the same bytes (``unchanged``)."""
    source = TRIMMED.read_bytes()
    url, answer = route("bdoo_2023_12", source)
    serve(monkeypatch, (url, answer))

    result = bdoo.download(teryt="12", year=2023, layers=["SKPP", "KUIK"])

    assert result.ok and not result.notices
    file = result.files[0].file
    assert file is not None
    assert file.path == tmp_path / "landcover/pl_bdoo_2023_kuik-skpp/teryt/12.zip"
    kept = _members(file.path.read_bytes())
    original = {info.filename: info for info in _members(source)}
    assert [info.filename for info in kept] == [
        "PL.PZGiK.201.12/BDOO/PL.PZGiK.201.12__OT_KUIK_A.xml",
        "PL.PZGiK.201.12/BDOO/PL.PZGiK.201.12__OT_SKPP_L.xml",
    ]
    with (
        zipfile.ZipFile(file.path) as stored,
        zipfile.ZipFile(io.BytesIO(source)) as published,
    ):
        for info in kept:
            assert stored.read(info) == published.read(info.filename)
            assert info.date_time == original[info.filename].date_time
            assert info.compress_type == original[info.filename].compress_type
    meta = _meta(file.version_path)
    assert meta["request"] == {"teryt": "12", "year": 2023, "layers": ["KUIK", "SKPP"]}
    assert meta["extra"]["source"]["classes"] == ["KUIK", "SKPP"]
    assert not (tmp_path / "landcover/pl_bdoo_2023").exists()

    again = bdoo.download(
        teryt="12", year=2023, layers=["KUIK", "SKPP"], update="force"
    )
    assert again.files[0].file is not None
    assert again.files[0].file.status == "unchanged"


def test_bdoo_layers_class_absent(bdoo, monkeypatch, tmp_path):
    """A chosen class without a file in the package (no such objects in the
    voivodeship) is an ``Info``; none of the chosen classes = no coverage of
    that voivodeship, nothing stored."""
    serve(monkeypatch, route("bdoo_2023_12", TRIMMED.read_bytes()))
    notices = []

    result = bdoo.download(
        teryt="12", year=2023, layers=["PTWP", "KUIK"], on_notice=notices.append
    )

    file = result.files[0].file
    assert file is not None
    assert file.path == tmp_path / "landcover/pl_bdoo_2023_kuik-ptwp/teryt/12.zip"
    assert [
        info.filename.rsplit("__", 1)[-1] for info in _members(file.path.read_bytes())
    ] == ["OT_KUIK_A.xml"]
    assert [n.code for n in notices] == [CLASSES_ABSENT]
    assert notices[0].level == "info"
    assert "plikow klas PTWP" in notices[0].text
    assert "zapisano klasy KUIK" in notices[0].text
    assert _meta(file.version_path)["extra"]["source"]["classes"] == ["KUIK"]

    with pytest.raises(NoCoverageError, match="nie ma plikow klas PTWP"):
        bdoo.download(teryt="12", year=2023, layers=["PTWP"])
    assert not (tmp_path / "landcover/pl_bdoo_2023_ptwp").exists()


@pytest.mark.parametrize(
    ("year", "layers", "message"),
    [
        (2023, ["XXXX"], "--layers XXXX: brak takich klas w bdoo --year 2023; "),
        # KUIK is a class of 2015-2023 only; the message lists the release's own
        (
            2024,
            ["KUIK", "PTWP"],
            "--layers KUIK: brak takich klas w bdoo --year 2024; "
            "dostepne: ADJA, ADMS, BUUO, KUKO, KUPG, KUPW,",
        ),
        (2023, [], "--layers: podaj co najmniej jedna klase bdoo --year 2023; "),
        (2023, "PTWP", "--layers: podaj liste kodow"),
    ],
)
def test_bdoo_unknown_class_before_any_request(
    bdoo, monkeypatch, year, layers, message
):
    fake = serve(monkeypatch)
    with pytest.raises(ValidationError, match=message):
        bdoo.download(teryt="12", year=year, layers=layers)
    assert fake.calls == []
