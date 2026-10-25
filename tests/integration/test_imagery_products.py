"""Image products of the GUGiK WMS sheet indexes (plan E, E1): intensity
images, the true orthophotomap (8-part sheets and the WCS cutout) and the
oblique orthophotomap (one file per view direction).

Fixtures ``tests/fixtures/pl/{intensity,orto_true,orto_oblique}`` (recorded
2026-10-16, README there): GetFeatureInfo answers of the indexes, ``HEAD``
sizes of the sheet files and the true orthophotomap WCS answers. The file
bodies are small GeoTIFFs inside the sheet frame (the real ones are
85-300 MB).
"""

import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.data import check_data, download_data, validate_data_request
from kartograf.download.orto_cutout import download_image_cutout
from kartograf.exceptions import NoCoverageError, ValidationError
from kartograf.notices import DOWNLOAD_SIZE, NO_COVERAGE_HINT
from kartograf.providers.pl.skorowidz import SkorowidzLayersMixin
from tests.conftest import recorded_response
from tests.support.fake_packages import FakeResponse

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pl"
SESSION_FACTORY = "kartograf.transport.http.make_gugik_session"
OI = "SkorowidzeOI"
TRUE = "Skorowidze"
OBLIQUE = "SkorowidzeOrtofotomapyUkosnej"
DIRECTIONS = {"n": "Polnoc", "e": "Wschod", "s": "Poludnie", "w": "Zachod"}
INTENSITY_SHEET = "M-34-64-D-d-1-4"
TRUE_SHEET = "N-34-50-A-c-3-2"
OBLIQUE_SHEET = "7.125.11.08"


def _sizes(product: str) -> dict[str, int]:
    files = json.loads((FIXTURES / product / "files.json").read_text("utf-8"))
    return {f["url"]: int(f["headers"]["Content-Length"]) for f in files.values()}


SIZES = {**_sizes("intensity"), **_sizes("orto_true"), **_sizes("orto_oblique")}


def _tif(sheet: str) -> bytes:
    """A 2 x 2 px uint8 GeoTIFF at the NW corner of the sheet frame (native
    CRS of the sheet code)."""
    parser = SheetParser(sheet)
    frame = (
        parser.get_bbox()
        if parser.sheet_system == "2000"
        else parser.get_bbox("EPSG:2180")
    )
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff",
            width=2,
            height=2,
            count=1,
            dtype="uint8",
            crs=frame.crs,
            transform=from_origin(frame.min_x, frame.max_y, 1, 1),
        ) as dst:
            dst.write(np.full((1, 2, 2), 7, dtype="uint8"))
        return memory.read()


class FakeImages:
    """``requests.Session`` stand-in of the GUGiK image indexes: GFI answers
    per (layer, sheet at the query point), the template without records
    elsewhere; file GETs give a small GeoTIFF of the sheet named by the URL,
    ``HEAD`` the recorded size (the true orthophotomap: every file the
    recorded one); WCS GetCoverage the recorded answers."""

    def __init__(self, gfi: dict[tuple[str, str], str], outside: str) -> None:
        self.gfi = gfi
        self.outside = outside
        self.calls: list[str] = []
        self.heads: list[str] = []
        self.coverage = "orto_true/true_0.05m_20x20.tif"

    def get(self, url, params=None, timeout=None, headers=None, stream=False):
        self.calls.append(url)
        query = parse_qs(urlparse(url).query)
        if query.get("REQUEST") == ["GetFeatureInfo"]:
            layer, bbox = query["LAYERS"][0], query["BBOX"][0]
            for (wanted, sheet), name in self.gfi.items():
                point = SkorowidzLayersMixin._query_bbox(SheetParser(sheet))
                if wanted == layer and bbox == point:
                    return recorded_response(FIXTURES / name)
            return recorded_response(FIXTURES / self.outside)
        if query.get("REQUEST") == ["GetCoverage"]:
            return recorded_response(FIXTURES / self.coverage)
        stem = Path(urlparse(url).path).stem
        if stem[-2] == "_" and stem[-1] in "NESW":
            stem = stem[:-2]
        return FakeResponse(
            200, {"Content-Type": "application/octet-stream"}, _tif(stem.split("_")[-1])
        )

    def head(self, url, timeout=None, allow_redirects=True):
        self.heads.append(url)
        size = SIZES.get(url, 296853152 if "/TrueOrtho/" in url else 0)
        return FakeResponse(200, {"Content-Length": str(size)}, b"")

    def file_gets(self) -> list[str]:
        return [url for url in self.calls if "opendata.geoportal.gov.pl" in url]


def _quarters() -> list[str]:
    return [f"{TRUE_SHEET}-{n}" for n in (1, 2, 3, 4)]


@pytest.fixture
def images():
    gfi = {
        (OI, INTENSITY_SHEET): "intensity/gfi_oi_M-34-64-D-d-1-4.html",
        (OI, "7.125.11.17"): "intensity/gfi_oi_M-34-64-D-d-1-4.html",
        **{(TRUE, sheet): f"orto_true/gfi_true_{sheet}.html" for sheet in _quarters()},
        **{
            (f"{OBLIQUE}-{name}", OBLIQUE_SHEET): (
                f"orto_oblique/gfi_oblique_{code}_{OBLIQUE_SHEET}.html"
            )
            for code, name in DIRECTIONS.items()
        },
    }
    fake = FakeImages(gfi, "orto_true/gfi_true_krakow.html")
    with patch(SESSION_FACTORY, return_value=fake):
        yield fake


def _meta(path: Path) -> dict:
    return json.loads(Path(f"{path}.meta.json").read_text(encoding="utf-8"))


ARGS = {"cache": False, "workers": 1}


def test_intensity_campaigns_like_orto(tmp_path, images):
    """Intensity sheets are campaigns as orthophotomap sheets: the newest
    flight by default, ``year`` picks another, ``all_campaigns`` keeps both
    in ``versions/``; a PL-2000 record of the same layer lands in its own
    segment."""
    out = tmp_path / "data"
    newest = download_data(
        product="intensity", sheet=INTENSITY_SHEET, output_dir=out, **ARGS
    )
    older = download_data(
        product="intensity", sheet=INTENSITY_SHEET, year=2023, output_dir=out, **ARGS
    )
    both = download_data(
        product="intensity",
        sheet=INTENSITY_SHEET,
        all_campaigns=True,
        output_dir=tmp_path / "all",
        **ARGS,
    )
    zone7 = download_data(
        product="intensity", sheet="7.125.11.17", output_dir=out, **ARGS
    )

    assert newest.ok and older.ok and both.ok and zone7.ok
    (first,) = newest.files
    assert first.file.path == (
        out / "intensity/pl_1992/M-34/64/D/d/1/4/M-34-64-D-d-1-4.tif"
    )
    assert first.file.label == "2025-04-28_83138"
    assert [f.file.label for f in older.files] == ["2023-09-08_78993"]
    assert sorted(f.file.label for f in both.files) == [
        "2023-09-08_78993",
        "2025-04-28_83138",
    ]
    meta = _meta(first.file.path)
    assert (meta["dataset"], meta["product"]) == ("pl.gugik.intensity", "intensity")
    with rasterio.open(first.file.path) as src:
        assert src.count == 1
    (pl2000,) = zone7.files
    assert pl2000.file.path == out / "intensity/pl_2000/7/125/11/17/7.125.11.17.tif"
    # 85 MB per sheet: below the DOWNLOAD_SIZE limit
    assert DOWNLOAD_SIZE not in {n.code for n in newest.notices}


def test_true_orto_sheets_and_size_notice(tmp_path, images):
    """An area of true orto is its 8-part sheets; each file is announced by
    ``DOWNLOAD_SIZE`` (HEAD 296 853 152 B) before its GET. Sheets without
    records (Krakow) fail as no coverage with the hint that true orto covers
    selected cities."""
    frame = SheetParser(TRUE_SHEET).get_bbox(crs="EPSG:2180")
    area = BBox(
        frame.min_x + 10,
        frame.min_y + 10,
        frame.max_x - 10,
        frame.max_y - 10,
        "EPSG:2180",
    )
    gets_at_notice: list[int] = []

    def on_notice(notice) -> None:
        if notice.code == DOWNLOAD_SIZE:
            gets_at_notice.append(len(images.file_gets()))

    report = download_data(
        product="true-orto",
        bbox=area,
        country="pl",
        output_dir=tmp_path / "data",
        on_notice=on_notice,
        **ARGS,
    )

    assert report.ok
    assert sorted(f.unit for f in report.files) == _quarters()
    assert all(
        "/true-orto/pl_1992/N-34/50/A/c/3/2/" in str(f.file.path) for f in report.files
    )
    assert gets_at_notice == [0, 1, 2, 3]  # each notice before its own GET
    size = [n.message for n in report.notices if n.code == DOWNLOAD_SIZE][0]
    assert "296853152 B" in size and "true-orto PL" in size

    krakow = download_data(
        product="true-orto", sheet="M-34-64-D-d-1-4", output_dir=tmp_path / "k", **ARGS
    )
    assert not krakow.ok
    assert [f.kind for f in krakow.failed] == ["no_coverage"]
    hints = [n.message for n in krakow.notices if n.code == NO_COVERAGE_HINT]
    assert any("covers only selected cities" in hint for hint in hints)


def test_true_orto_cutout_native_grid(tmp_path, images):
    """The true orto cutout asks coverage True_Orthoimagery on its 0.05 m grid
    (no SCALEFACTOR) and lands in ``true-orto/pl_1992_0.05m``; it has one
    service - no ``coverage`` - and pixels from the registry."""
    cutout = {
        "product": "true-orto",
        "bbox": BBox(470177, 740336, 470178, 740337, "EPSG:2180"),
        "country": "pl",
        "cutout": True,
        "horizontal_crs": "EPSG:2180",
    }
    report = download_data(
        **cutout, resolution="0.05m", output_dir=tmp_path / "data", **ARGS
    )

    assert report.ok
    (unit,) = report.files
    assert unit.unit == "470177_740336_470178_740337"  # coords, as area units
    assert unit.file.path == (
        tmp_path / "data/true-orto/pl_1992_0.05m/bbox" / f"{unit.unit}.tif"
    )
    with rasterio.open(unit.file.path) as src:
        assert (src.count, src.width, src.crs.to_epsg()) == (3, 20, 2180)
    (request,) = [u for u in images.calls if "GetCoverage" in u]
    query = parse_qs(urlparse(request).query)
    assert query["COVERAGEID"] == ["True_Orthoimagery"]
    assert "SCALEFACTOR" not in query
    assert "coverage" not in _meta(unit.file.path)["request"]

    with pytest.raises(ValidationError, match="omit --coverage"):
        validate_data_request(
            **cutout, coverage="true", resolution="0.05m", output_dir=tmp_path
        )
    with pytest.raises(ValidationError, match="0.05m, 0.1m, 0.25m, 0.5m, 1m"):
        validate_data_request(**cutout, resolution="0.2m", output_dir=tmp_path)


def test_true_orto_cutout_outside_cities_is_no_coverage(tmp_path, images):
    """Outside the cities the true orto WCS answers 0,0,0 (recorded Krakow):
    ``NoCoverageError`` and no version, no link and no staging left; in
    ``download_data`` a ``no_coverage`` failure of PL."""
    images.coverage = "orto_true/true_0.05m_krakow.tif"
    krakow = BBox(566000, 243000, 566001, 243001, "EPSG:2180")
    out = tmp_path / "data"
    with pytest.raises(NoCoverageError, match="wybrane miasta"):
        download_image_cutout(
            product="true-orto",
            bbox=krakow,
            horizontal_crs="EPSG:2180",
            output_dir=out,
            resolution="0.05m",
            cache=False,
        )
    assert [p for p in out.rglob("*") if p.is_file()] == []

    report = download_data(
        product="true-orto",
        bbox=krakow,
        country="pl",
        cutout=True,
        horizontal_crs="EPSG:2180",
        resolution="0.05m",
        output_dir=out,
        **ARGS,
    )
    assert report.files == ()
    assert [(f.unit, f.kind) for f in report.failed] == [("PL", "no_coverage")]
    assert [p for p in out.rglob("*") if p.is_file()] == []


def test_oblique_directions_are_files(tmp_path, images):
    """An oblique sheet is four files ``_n``, ``_e``, ``_s``, ``_w`` in one
    segment; ``direction`` chooses some; a wrong code or another product is
    an error before any request."""
    out = tmp_path / "data"
    every = download_data(
        product="oblique-orto", sheet=OBLIQUE_SHEET, output_dir=out, **ARGS
    )
    two = download_data(
        product="oblique-orto",
        sheet=OBLIQUE_SHEET,
        direction=["e", "n"],
        output_dir=tmp_path / "two",
        **ARGS,
    )

    assert every.ok and two.ok
    base = out / "oblique-orto/pl_2000/7/125/11/08"
    assert [f.file.path for f in every.files] == [
        base / f"{OBLIQUE_SHEET}_{code}.tif" for code in "nesw"
    ]
    assert [f.file.path.name for f in two.files] == [
        f"{OBLIQUE_SHEET}_n.tif",
        f"{OBLIQUE_SHEET}_e.tif",
    ]
    assert _meta(every.files[0].file.path)["extra"]["source"]["direction"] == "n"
    assert len([n for n in every.notices if n.code == DOWNLOAD_SIZE]) == 4

    with pytest.raises(ValidationError, match="--direction 'x'"):
        validate_data_request(
            product="oblique-orto", sheet=OBLIQUE_SHEET, direction="x", output_dir=out
        )
    with pytest.raises(ValidationError, match="--direction dotyczy tylko"):
        validate_data_request(
            product="orto", sheet=INTENSITY_SHEET, direction="n", output_dir=out
        )


def test_oblique_plan_upgrade_keeps_each_direction(tmp_path, images):
    """A plan of an oblique sheet has a position per direction; the upgrade
    executes each in its own manager - none of them becomes stale."""
    out = tmp_path / "data"
    plan = check_data(
        product="oblique-orto", sheet=OBLIQUE_SHEET, output_dir=out, cache=False
    )
    report = download_data(
        product="oblique-orto",
        sheet=OBLIQUE_SHEET,
        output_dir=out,
        update="upgrade",
        plan=plan,
        **ARGS,
    )

    assert [item.name for item in plan.items] == [
        f"{OBLIQUE_SHEET}_{code}.tif" for code in "nesw"
    ]
    assert {item.status for item in plan.items} == {"missing"}
    assert report.ok and not report.stale
    assert [f.file.status for f in report.files] == ["new"] * 4


@pytest.mark.parametrize(
    ("product", "sheet", "allowed"),
    [
        ("intensity", INTENSITY_SHEET, False),
        ("true-orto", f"{TRUE_SHEET}-3", False),
        ("oblique-orto", OBLIQUE_SHEET, True),
    ],
)
def test_full_sheet_only_with_record_flag(tmp_path, product, sheet, allowed):
    """``full_sheet`` needs records declaring a full sheet: intensity and true
    orto records have none, oblique ones do."""
    request = {"product": product, "sheet": sheet, "full_sheet": True}
    if allowed:
        validate_data_request(**request, output_dir=tmp_path)
        return
    with pytest.raises(ValidationError, match="calyArkuszWypelnionyTrescia"):
        validate_data_request(**request, output_dir=tmp_path)


@pytest.mark.parametrize(
    ("request_", "fragment"),
    [
        ({"product": "oblique-orto", "sheet": INTENSITY_SHEET}, "tylko PL-2000"),
        ({"product": "true-orto", "sheet": OBLIQUE_SHEET}, "tylko PL-1992"),
        (
            {"product": "intensity", "sheet": INTENSITY_SHEET, "cutout": True},
            "--cutout dziala tylko z --bbox/--geometry",
        ),
        (
            {
                "product": "intensity",
                "bbox": BBox(566000, 243000, 566100, 243100, "EPSG:2180"),
                "country": "pl",
                "cutout": True,
            },
            "--cutout dziala tylko z --product nmt, nmpt, orto albo true-orto",
        ),
        (
            {"product": "intensity", "sheet": "CTES96"},
            "--product intensity nie ma danych CZ",
        ),
    ],
)
def test_image_choices_fail_before_source(tmp_path, request_, fragment):
    with pytest.raises(ValidationError, match=fragment):
        validate_data_request(**request_, output_dir=tmp_path)
