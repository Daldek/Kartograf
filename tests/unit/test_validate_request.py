"""Validation without network shared with the download functions (ADR-040).

``validate_data_request``, ``validate_landcover_request``,
``validate_soil_request`` and ``validate_hsg_request`` run the checks the
functions make before their first request: an invalid choice gives the same
exception type and text as the download, a valid one returns without any
request (``tests/conftest.py::_block_network``) and without writing.
"""

from pathlib import Path

import pytest

from kartograf.core.bbox import BBox
from kartograf.download.availability import check_availability
from kartograf.download.data import download_data, validate_data_request
from kartograf.exceptions import KartografError, ValidationError
from kartograf.hydrology.hsg import calculate_hsg, check_hsg, validate_hsg_request
from kartograf.landcover.manager import (
    check_landcover,
    check_soil,
    download_landcover,
    download_soil,
    validate_landcover_request,
    validate_soil_request,
)
from tests.unit.test_geometry import _write_prj

G = "N-34-139-C-a-3-1"
BBOX_PL = BBox(500000, 300000, 501000, 301000, "EPSG:2180")
# Cieszyn: a bbox crossing the PL-CZ border
BORDER = BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326")
PL_1M = {"resolution": "1m", "vertical_crs": "EVRF2007"}
# An archive variant (ADR-041): sheets of any scale come from the WFS index
TBD_25M = {"format": "TBD", "resolution": "25m", "vertical_crs": "EVRF2007"}
AUTO = {
    "country": "auto",
    "resolution": {"pl": "1m", "cz": "2m"},
    "vertical_crs": {"pl": "EVRF2007", "cz": "Bpv"},
}


def _shapefile(directory: Path) -> Path:
    """One polygon inside PL (EPSG:2180)."""
    import shapefile

    path = directory / "area.shp"
    with shapefile.Writer(str(path)) as writer:
        writer.field("name", "C", 10)
        ring = [(500000, 300000), (501000, 300000), (501000, 301000), (500000, 300000)]
        writer.poly([ring])
        writer.record("a")
    _write_prj(path.with_suffix(".prj"))
    return path


def _raised(call) -> KartografError:
    with pytest.raises(KartografError) as caught:
        call()
    return caught.value


INVALID_DATA = {
    "missing-vertical-crs": {"product": "nmt", "sheet": G, "resolution": "1m"},
    "two-areas": {"product": "nmt", "sheet": G, "bbox": BBOX_PL, **PL_1M},
    "bbox-without-country": {"product": "nmt", "bbox": BBOX_PL, **PL_1M},
    "resolution-outside-list": {
        "product": "nmt",
        "sheet": G,
        "resolution": "3m",
        "vertical_crs": "EVRF2007",
    },
    "cz-sheet-without-resolution": {
        "product": "nmt",
        "sheet": "302_5550",
        "vertical_crs": "Bpv",
    },
    "pl-area-without-sheet-system": {
        "product": "nmt",
        "bbox": BBOX_PL,
        "country": "pl",
        **PL_1M,
    },
    "laz-for-cz": {
        "product": "laz",
        "bbox": BBOX_PL,
        "country": "cz",
        "vertical_crs": "EVRF2007",
    },
    "auto-cz-without-cutout": {"product": "nmt", "bbox": BORDER, **AUTO},
    "missing-geometry-file": {
        "product": "nmt",
        "geometry": "missing.gpkg",
        "country": "pl",
        "sheet_system": "1992",
        **PL_1M,
    },
    "archive-cutout": {
        "product": "nmt",
        "bbox": BBOX_PL,
        "country": "pl",
        "cutout": True,
        "horizontal_crs": "EPSG:2180",
        **TBD_25M,
    },
}


@pytest.mark.parametrize("kwargs", INVALID_DATA.values(), ids=INVALID_DATA.keys())
def test_validate_data_request_equals_download_error(tmp_path, monkeypatch, kwargs):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    expected = _raised(lambda: download_data(root=out, cache=False, **kwargs))
    got = _raised(lambda: validate_data_request(root=out, **kwargs))
    assert type(got) is type(expected) and str(got) == str(expected)
    assert isinstance(got, ValidationError)
    assert not out.exists()


VALID_DATA = {
    "pl-sheet": {"product": "nmt", "sheet": G, **PL_1M},
    "pl-coarser-sheet": {"product": "nmt", "sheet": "N-34-139-C-a-3", **PL_1M},
    "pl-2000-scale": {"product": "orto", "sheet": "7.171.21", "scale": "1:2000"},
    "pl-bbox-sheets": {
        "product": "nmt",
        "bbox": BBOX_PL,
        "country": "pl",
        "sheet_system": "1992",
        **PL_1M,
    },
    "pl-geometry-sheets": {
        "product": "nmt",
        "geometry": "area.shp",
        "country": "pl",
        "sheet_system": "1992",
        **PL_1M,
    },
    "pl-cutout": {
        "product": "nmt",
        "bbox": BBOX_PL,
        "country": "pl",
        "cutout": True,
        "horizontal_crs": "EPSG:2180",
        **PL_1M,
    },
    "cz-tm33-sheet": {
        "product": "nmt",
        "sheet": "302_5550",
        "resolution": "2m",
        "vertical_crs": "Bpv",
    },
    "cz-cutout": {
        "product": "nmt",
        "bbox": BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514"),
        "country": "cz",
        "resolution": "2m",
        "vertical_crs": "Bpv",
        "cutout": True,
        "horizontal_crs": "EPSG:5514",
    },
    "auto-pl-cz-cutout": {
        "product": "nmt",
        "bbox": BORDER,
        **AUTO,
        "cutout": True,
        "horizontal_crs": "EPSG:3045",
    },
    "laz-sheet": {
        "product": "laz",
        "sheet": "N-34-130-D-d-2-4",
        "vertical_crs": "EVRF2007",
    },
    "pl-archive-sheet": {"product": "nmt", "sheet": G, **TBD_25M},
    "pl-archive-bbox": {
        "product": "nmt",
        "bbox": BBOX_PL,
        "country": "pl",
        "sheet_system": "1992",
        **TBD_25M,
    },
    "pl-archive-geometry": {
        "product": "nmt",
        "geometry": "area.shp",
        "country": "pl",
        "sheet_system": "1992",
        **TBD_25M,
    },
}


@pytest.mark.parametrize("kwargs", VALID_DATA.values(), ids=VALID_DATA.keys())
def test_validate_data_request_valid_stops_before_source(tmp_path, monkeypatch, kwargs):
    """No request (network guard), no store, no metadata cache in the cwd."""
    monkeypatch.chdir(tmp_path)
    _shapefile(tmp_path)
    out = tmp_path / "out"
    assert validate_data_request(root=out, **kwargs) is None
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "area.dbf",
        "area.prj",
        "area.shp",
        "area.shx",
    ]


LANDCOVER_INVALID = [
    ("corine", {"bbox": BBOX_PL}),
    ("bdot10k", {"teryt": "1465", "format": "SHP", "layers": ("PTWP",)}),
    ("bdot10k", {"teryt": "14x5"}),
    ("bdot10k", {"teryt": "1465", "bbox": BBOX_PL}),
    ("bdot10k", {"teryt": "1465", "year": 2018}),
    ("corine", {"teryt": "1465", "year": 2018}),
    (
        "soilgrids",
        {"bbox": BBOX_PL, "property": "clay", "depth": "7cm", "stat": "mean"},
    ),
]


@pytest.mark.parametrize("method", ["download", "check"])
@pytest.mark.parametrize(
    ("source", "kwargs"),
    LANDCOVER_INVALID,
    ids=[
        "corine-without-year",
        "layers-with-shp",
        "bad-teryt",
        "two-choices",
        "option-of-another-source",
        "teryt-of-corine",
        "bad-depth",
    ],
)
def test_landcover_validate_request_equals_download_error(
    tmp_path, source, kwargs, method
):
    out = tmp_path / "out"
    if source == "soilgrids":
        calls = {"download": download_soil, "check": check_soil}
        validate = validate_soil_request
        choices = kwargs
    else:
        calls = {"download": download_landcover, "check": check_landcover}
        validate = validate_landcover_request
        choices = {"product": source, **kwargs}
    expected = _raised(lambda: calls[method](root=out, cache=False, **choices))
    got = _raised(lambda: validate(root=out, **choices))
    assert type(got) is type(expected) and str(got) == str(expected)
    assert isinstance(got, ValidationError)
    assert not out.exists()


def test_landcover_validate_request_valid_reads_only_geometry(tmp_path):
    out = tmp_path / "out"
    area = _shapefile(tmp_path)
    for source, options in (
        ("bdot10k", {"layers": ("PTWP",), "keep_raw": True}),
        ("corine", {"year": 2018}),
        ("soilgrids", {"property": "clay", "depth": "0-5cm", "stat": "mean"}),
    ):
        if source == "soilgrids":
            assert validate_soil_request(root=out, geometry=area, **options) is None
        else:
            assert (
                validate_landcover_request(
                    product=source, root=out, geometry=area, **options
                )
                is None
            )
    assert validate_landcover_request(product="bdot10k", root=out, teryt="1465") is None
    assert not out.exists()


HSG_INVALID = {
    "bad-depth": {"bbox": BBOX_PL, "depth": "7cm"},
    "missing-depth": {"sheet": "N-34-130-D", "depth": None},
    "two-choices": {"sheet": "N-34-130-D", "bbox": BBOX_PL, "depth": "0-5cm"},
    "no-choice": {"depth": "0-5cm"},
}


@pytest.mark.parametrize("method", ["calculate_hsg", "check_hsg"])
@pytest.mark.parametrize("kwargs", HSG_INVALID.values(), ids=HSG_INVALID.keys())
def test_hsg_validate_request_rejects_depth_and_selection(tmp_path, kwargs, method):
    out = tmp_path / "out"
    calls = {"calculate_hsg": calculate_hsg, "check_hsg": check_hsg}
    expected = _raised(lambda: calls[method](root=out, cache=False, **kwargs))
    got = _raised(lambda: validate_hsg_request(root=out, **kwargs))
    assert type(got) is type(expected) and str(got) == str(expected)
    assert isinstance(got, ValidationError)
    assert validate_hsg_request(root=out, bbox=BBOX_PL, depth="0-5cm") is None
    assert not out.exists()


# A point in --geometry (E2E 0.8.0 N-P3-4): its envelope has no area.
PL_POINT = (566250.0, 243250.0, 2180)
CZ_POINT = (-450000.0, -1111000.0, 5514)


def _point_shapefile(directory: Path, point: tuple[float, float, int]) -> Path:
    """A shapefile with one point of the CRS ``point[2]``."""
    import shapefile

    x, y, epsg = point
    path = directory / f"point_{epsg}.shp"
    with shapefile.Writer(str(path), shapeType=shapefile.POINT) as writer:
        writer.field("name", "C", 10)
        writer.point(x, y)
        writer.record("a")
    _write_prj(path.with_suffix(".prj"), epsg)
    return path


NEEDS_AREA = {
    "pl-nmt-cutout": (
        PL_POINT,
        {"product": "nmt", "country": "pl", "cutout": True, **PL_1M}
        | {"horizontal_crs": "EPSG:2180"},
    ),
    "pl-orto-cutout": (
        PL_POINT,
        {
            "product": "orto",
            "country": "pl",
            "cutout": True,
            "horizontal_crs": "EPSG:2180",
            "coverage": "standard",
            "resolution": "0.25m",
        },
    ),
    "pl-laz": (
        PL_POINT,
        {"product": "laz", "country": "pl", "vertical_crs": "EVRF2007"},
    ),
    "auto-nmt-cutout": (
        PL_POINT,
        {**AUTO, "product": "nmt", "cutout": True, "horizontal_crs": "EPSG:2180"},
    ),
    "cz-nmt-cutout": (
        CZ_POINT,
        {
            "product": "nmt",
            "country": "cz",
            "cutout": True,
            "horizontal_crs": "EPSG:5514",
            "resolution": "5m",
            "vertical_crs": "Bpv",
        },
    ),
    "cz-laz": (
        CZ_POINT,
        {
            "product": "laz",
            "country": "cz",
            "model": "dmr5g",
            "vertical_crs": "Bpv",
        },
    ),
}


@pytest.mark.parametrize(("point", "kwargs"), NEEDS_AREA.values(), ids=NEEDS_AREA)
def test_a_point_geometry_is_refused_where_the_track_needs_an_area(
    tmp_path, point, kwargs
):
    """A cutout and the LAZ tiles are made for an area: the point is refused
    before the network and the error names ``--geometry`` (it named ``bbox``, an
    option the call never had), the same for the download and the validation."""
    area = _point_shapefile(tmp_path, point)
    out = tmp_path / "out"
    expected = _raised(
        lambda: download_data(root=out, geometry=area, cache=False, **kwargs)
    )
    got = _raised(lambda: validate_data_request(root=out, geometry=area, **kwargs))
    assert type(got) is type(expected) and str(got) == str(expected)
    assert isinstance(got, ValidationError) and got.option == "geometry"
    assert "--geometry" in str(got)
    assert not out.exists()


def test_a_point_geometry_still_picks_the_sheet_it_lies_in(tmp_path):
    """Sheets, units and pixels are what a point lies in: no area needed."""
    area = _point_shapefile(tmp_path, PL_POINT)
    kwargs = {"product": "nmt", "country": "pl", "sheet_system": "1992", **PL_1M}
    assert validate_data_request(root=tmp_path / "out", geometry=area, **kwargs) is None


def test_hsg_refuses_a_point_geometry(tmp_path):
    area = _point_shapefile(tmp_path, PL_POINT)
    out = tmp_path / "out"
    kwargs = {"root": out, "geometry": area, "depth": "0-5cm"}
    got = _raised(lambda: validate_hsg_request(**kwargs))
    assert isinstance(got, ValidationError) and got.option == "geometry"
    for call in (calculate_hsg, check_hsg):
        expected = _raised(lambda call=call: call(cache=False, **kwargs))
        assert type(got) is type(expected) and str(got) == str(expected)
    assert not out.exists()


@pytest.mark.parametrize(
    ("product", "country", "point"),
    [
        ("nmt", "pl", PL_POINT),
        ("laz", "pl", PL_POINT),
        ("nmt", "cz", CZ_POINT),
        ("nmt", "auto", PL_POINT),
    ],
)
def test_availability_refuses_a_point_geometry(tmp_path, product, country, point):
    """The report is about the coverage of an area: a point gave ``obszar 0,00 ha``
    and ``brak ladu`` for land."""
    area = _point_shapefile(tmp_path, point)
    got = _raised(
        lambda: check_availability(
            product=product, country=country, geometry=area, cache=False
        )
    )
    assert isinstance(got, ValidationError) and got.option == "geometry"
