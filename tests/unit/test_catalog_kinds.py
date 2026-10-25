"""Conversion of options between the JSON form and the library arguments
(``kartograf.catalog.kinds``): the task options of a project and the arguments of
a command call (spec 8.7)."""

from pathlib import Path

import pytest

from kartograf.catalog.kinds import (
    check_options_json,
    convert_arguments,
    layer_codes,
    options_from_json,
    options_to_json,
    parse_per_country,
)
from kartograf.catalog.spec import Kind
from kartograf.core.bbox import BBox
from kartograf.download.plan import UpdatePlan
from kartograf.exceptions import ValidationError
from kartograf.project.commands import COMMANDS
from tests.support.project_fixtures import HSG_SHEET, PL_SHEET

ELEVATION = COMMANDS["elevation download"].options
LANDCOVER = COMMANDS["landcover download"].options
SOIL = COMMANDS["soil download"].options
HYDRO = COMMANDS["hydro download"].options
KRAKOW_5514 = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")

# one parameter of every kind the library takes from the JSON form
KINDS: dict[str, Kind] = {
    "product": "str",
    "year": "int",
    "bbox": "bbox",
    "bbox_crs": "bbox_crs",
    "geometry": "path",
    "resolution": "per_country",
    "layers": "str_list",
    "cutout": "flag",
    "plan": "plan",
    "options": "options",
}


def test_convert_arguments_by_kind(tmp_path):
    plan = UpdatePlan(
        store="/data",
        checked_at="2026-10-18T10:00:00+00:00",
        kartograf_version="x",
        items=(),
    )
    arguments = convert_arguments(
        KINDS,
        {
            "product": "nmt",
            "bbox": [1, 2.5, 3, 4],
            "bbox_crs": "EPSG:2180",
            "geometry": "obszar/zlewnia.gpkg",
            "resolution": {"pl": "1m", "cz": "2m"},
            "layers": ["SWRS", "PTWP"],
            "cutout": True,
            "year": 2024,
            "plan": plan.to_dict(),
            "options": {"product": "nmt"},
        },
        base_dir=tmp_path,
    )

    assert list(arguments) == [
        "product",
        "bbox",
        "geometry",
        "resolution",
        "layers",
        "cutout",
        "year",
        "plan",
        "options",
    ]
    assert arguments["bbox"] == BBox(1, 2.5, 3, 4, "EPSG:2180")
    assert arguments["geometry"] == tmp_path / "obszar" / "zlewnia.gpkg"
    assert arguments["resolution"] == {"pl": "1m", "cz": "2m"}
    assert arguments["layers"] == ("SWRS", "PTWP")
    assert arguments["cutout"] is True and arguments["year"] == 2024
    assert arguments["plan"] == plan
    assert arguments["options"] == {"product": "nmt"}
    assert convert_arguments(KINDS, {"resolution": "1m"}) == {"resolution": "1m"}


def test_convert_arguments_paths_and_not_given_values(tmp_path):
    absolute = str(tmp_path / "a.gpkg")
    assert convert_arguments(KINDS, {"geometry": "a/b.gpkg"}) == {
        "geometry": Path("a/b.gpkg")
    }
    assert convert_arguments(KINDS, {"geometry": absolute}, base_dir=Path("/x")) == {
        "geometry": Path(absolute)
    }
    assert convert_arguments(KINDS, {"geometry": Path(absolute)}) == {
        "geometry": Path(absolute)
    }
    # null and a false flag are "not given": they are left out
    assert convert_arguments(KINDS, {"product": None, "cutout": False}) == {}


@pytest.mark.parametrize(
    ("data", "option"),
    [
        ({"vertical_crs": "EVRF2007"}, "vertical_crs"),
        ({"product": 1}, "product"),
        ({"year": "2024"}, "year"),
        ({"year": True}, "year"),
        ({"cutout": "yes"}, "cutout"),
        ({"geometry": ""}, "geometry"),
        ({"resolution": ["1m"]}, "resolution"),
        ({"layers": "SWRS"}, "layers"),
        ({"bbox": [1, 2, 3, 4]}, "bbox_crs"),
        ({"bbox_crs": "EPSG:2180"}, "bbox_crs"),
        ({"bbox": [1, 2, 3], "bbox_crs": "EPSG:2180"}, "bbox"),
        ({"bbox": [1, 2, 3, float("nan")], "bbox_crs": "EPSG:2180"}, "bbox"),
        ({"plan": {"schema": "kartograf-plan/2"}}, "plan"),
        ({"plan": []}, "plan"),
        ({"options": []}, "options"),
    ],
)
def test_convert_arguments_names_the_wrong_option(data, option):
    with pytest.raises(ValidationError) as caught:
        convert_arguments(KINDS, data)

    assert caught.value.option == option


def test_options_round_trip(tmp_path):
    project = tmp_path / "projekt"
    elevation = {
        "vertical_crs": "EVRF2007",
        "cutout": True,
        "product": "nmt",
        "full_sheet": False,
        "bbox": KRAKOW_5514,
        "year": None,
        "resolution": {"pl": "1m", "cz": "2m"},
        "country": "auto",
        "horizontal_crs": "EPSG:5514",
    }
    data = options_to_json(ELEVATION, elevation)
    assert list(data.items()) == [
        ("product", "nmt"),
        ("country", "auto"),
        ("bbox", [-447000, -1114000, -446000, -1113000]),
        ("bbox_crs", "EPSG:5514"),
        ("resolution", {"pl": "1m", "cz": "2m"}),
        ("vertical_crs", "EVRF2007"),
        ("cutout", True),
        ("horizontal_crs", "EPSG:5514"),
    ]
    expected = {k: v for k, v in elevation.items() if v is not None and v is not False}
    assert options_from_json(ELEVATION, data, base_dir=project) == expected

    absolute = (tmp_path / "obszary" / "b.gpkg").resolve()
    for given, saved, read in (
        (
            Path("obszar/zlewnia.gpkg"),
            "obszar/zlewnia.gpkg",
            project / "obszar/zlewnia.gpkg",
        ),
        (absolute, absolute.as_posix(), absolute),
    ):
        landcover = {
            "product": "bdot10k",
            "geometry": given,
            "layers": ("SWRS", "PTWP"),
            "keep_raw": True,
        }
        data = options_to_json(LANDCOVER, landcover)
        assert data == {
            "product": "bdot10k",
            "geometry": saved,
            "layers": ["SWRS", "PTWP"],
            "keep_raw": True,
        }
        assert check_options_json(LANDCOVER, data) is None
        assert options_from_json(LANDCOVER, data, base_dir=project) == {
            **landcover,
            "geometry": read,
        }


@pytest.mark.parametrize(
    ("kinds", "options"),
    [
        (
            LANDCOVER,
            {"product": "bdot10k", "teryt": "1465", "vertical_crs": "EVRF2007"},
        ),
        (SOIL, {"sheet": HSG_SHEET, "timeout": 30}),
        (ELEVATION, {**PL_SHEET, "output_dir": "data"}),
        (ELEVATION, {**PL_SHEET, "update": "upgrade"}),
        (ELEVATION, {**PL_SHEET, "workers": 2}),
        (ELEVATION, {**PL_SHEET, "bbox_crs": "EPSG:2180"}),
        (ELEVATION, {**PL_SHEET, "year": "2024"}),
        (ELEVATION, {**PL_SHEET, "year": True}),
        (ELEVATION, {**PL_SHEET, "bbox": [1, 2, 3, 4]}),
        (ELEVATION, {**PL_SHEET, "resolution": {"pl": 1}}),
        (LANDCOVER, {"product": "bdot10k", "teryt": "1465", "layers": "SWRS"}),
        (HYDRO, {"product": "network", "teryt": "1261"}),
    ],
    ids=[
        "flag-of-another-group",
        "timeout",
        "output-dir",
        "update",
        "workers",
        "bbox-crs-alone",
        "year-text",
        "year-bool",
        "bbox-list",
        "per-country-number",
        "layers-text",
        "hydro-teryt",
    ],
)
def test_options_reject_unknown_and_foreign(kinds, options):
    with pytest.raises(ValidationError):
        options_to_json(kinds, options)


@pytest.mark.parametrize(
    "data",
    [
        {"product": None},
        {"cutout": False},
        {"bbox": [1, 2, 3, 4]},
        {"bbox_crs": "EPSG:2180"},
        {"bbox": [1, 2, 3], "bbox_crs": "EPSG:2180"},
        {"bbox": [1, 2, 3, float("nan")], "bbox_crs": "EPSG:2180"},
        {"year": "2024"},
        {"geometry": ""},
        {"resolution": ["1m"]},
        {"keep_raw": True},
        [],
    ],
)
def test_check_options_json_errors(data):
    assert check_options_json(ELEVATION, data) is not None


def test_check_options_json_names_the_command():
    text = check_options_json(
        ELEVATION, {"keep_raw": True}, command="elevation download"
    )

    assert text is not None and "elevation download" in text
    assert "keep_raw" in text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("5m", "5m"),
        ("pl=1m", {"pl": "1m"}),
        ("pl=1m,cz=2m", {"pl": "1m", "cz": "2m"}),
        (" PL = 1m , cz=2m ", {"pl": "1m", "cz": "2m"}),
    ],
)
def test_parse_per_country_reads_one_value_or_country_pairs(raw, expected):
    assert parse_per_country(raw, "--resolution") == expected


@pytest.mark.parametrize(
    "raw", ["pl=1m,pl=2m", "pl=1m,xx=2m", "pl=", "pl=1m,cz", "=1m"]
)
def test_parse_per_country_names_the_flag_of_a_malformed_value(raw):
    with pytest.raises(ValidationError) as caught:
        parse_per_country(raw, "--vertical-crs")

    assert str(caught.value).startswith(f"--vertical-crs: invalid value {raw!r}")
    assert "--vertical-crs pl=...,cz=..." in str(caught.value)


@pytest.mark.parametrize(
    ("text", "codes"),
    [("SWRS", ("SWRS",)), ("SWRS,PTWP", ("SWRS", "PTWP")), (" n , e ", ("n", "e"))],
)
def test_layer_codes_split_on_commas(text, codes):
    assert layer_codes(text) == codes
