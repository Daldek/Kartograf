"""Value kinds and the canonical command line of the command catalog
(spec 8.3, 8.7)."""

import shlex

import pytest

from kartograf.catalog import kinds
from kartograf.catalog.formatting import example_command_line, format_command_line
from kartograf.catalog.spec import Command, Example, Param
from kartograf.cli import _args
from kartograf.exceptions import ValidationError


def _outcome(function, *args):
    """The result of a parser helper, or the type and text of its error."""
    try:
        return function(*args)
    except ValidationError as error:
        return type(error), str(error)


@pytest.mark.parametrize(
    "args",
    [
        ("530000,382000,533000,386000", "EPSG:2180"),
        (" 19.93 , 50.055,19.945,50.065", "EPSG:4326"),
        ("-447000,-1114000,-446000,-1113000", "EPSG:5514"),
        ("1,2,3", "EPSG:2180"),
        ("1,2,x,4", "EPSG:2180"),
        ("5,2,3,4", "EPSG:2180"),
        ("1,2,3,4", "EPSG:9999"),
        ("nan,2,3,4", "EPSG:2180"),
    ],
)
def test_kinds_parse_bbox_like_the_cli_helper(args):
    assert _outcome(kinds.parse_bbox_arg, *args) == _outcome(
        _args.parse_bbox_arg, *args
    )


@pytest.mark.parametrize(
    "args",
    [
        (None, "--resolution"),
        ("5m", "--resolution"),
        ("pl=1m,cz=2m", "--resolution"),
        (" PL = 1m , cz=2m ", "--vertical-crs"),
        ("pl=1m,pl=2m", "--resolution"),
        ("pl=1m,xx=2m", "--resolution"),
        ("pl=", "--resolution"),
        ("pl=1m,cz", "--resolution"),
    ],
)
def test_kinds_parse_per_country_like_the_cli_helper(args):
    assert _outcome(kinds.parse_per_country, *args) == _outcome(
        _args.parse_per_country, *args
    )


@pytest.mark.parametrize("text", ["SWRS", "SWRS,PTWP", " n , e ", ""])
def test_kinds_split_layer_codes_like_the_cli_helper(text):
    assert kinds.layer_codes(text) == _args.layer_codes(text)


# =============================================================================
# format_command_line (spec 8.7)
# =============================================================================


def _declared(*params: Param, id: str = "elevation download") -> Command:
    """A synthetic data command: the line is built from the declaration."""
    return Command(
        id,
        "Pobierz dane",
        "data",
        "download_data",
        "kartograf-download/1",
        params,
    )


_PARAMS = (
    Param("product", "str", task=True),
    Param("sheet", "str", task=True, accepts=("pl1992",)),
    Param("bbox", "bbox", task=True),
    Param("bbox_crs", "bbox_crs", task=True, cli_default="EPSG:2180"),
    Param("geometry", "path", task=True),
    Param("resolution", "per_country", task=True, short="-r"),
    Param("layers", "str_list", task=True),
    Param("year", "int", task=True),
    Param("cutout", "flag", task=True),
    Param("output_dir", "path", flag="--output", short="-o", dest="output"),
    Param("workers", "int", short="-w"),
    Param("quiet", "flag", argument=None, short="-q"),
)
_ELEVATION = _declared(*_PARAMS)


def test_flags_follow_declaration_order():
    options = {"cutout": True, "year": 2020, "resolution": "1m", "product": "nmt"}

    assert format_command_line(_ELEVATION, options) == (
        "kartograf elevation download --product nmt --resolution 1m --year 2020 "
        "--cutout"
    )


def test_bbox_omits_the_default_crs_flag():
    bbox = {"bbox": [530000, 382000, 533000, 386000], "bbox_crs": "EPSG:2180"}
    other = {"bbox": [-447000, -1114000, -446000, -1113000], "bbox_crs": "EPSG:5514"}

    assert format_command_line(_ELEVATION, bbox).endswith(
        "--bbox 530000,382000,533000,386000"
    )
    assert format_command_line(_ELEVATION, other).endswith(
        "--bbox -447000,-1114000,-446000,-1113000 --bbox-crs EPSG:5514"
    )


def test_numbers_print_without_a_trailing_zero():
    options = {"bbox": [19.93, 50.055, 19945.0, 50.0], "bbox_crs": "EPSG:4326"}

    assert format_command_line(_ELEVATION, options).endswith(
        "--bbox 19.93,50.055,19945,50 --bbox-crs EPSG:4326"
    )


def test_per_country_forms():
    plain = format_command_line(_ELEVATION, {"resolution": "5m"})
    pairs = format_command_line(_ELEVATION, {"resolution": {"cz": "2m", "pl": "1m"}})

    assert plain.endswith("--resolution 5m")
    assert pairs.endswith("--resolution pl=1m,cz=2m")


def test_str_list_joined_with_commas():
    line = format_command_line(_ELEVATION, {"layers": ["SWRS", "PTWP"]})

    assert line.endswith("--layers SWRS,PTWP")


def test_path_is_shell_quoted():
    line = format_command_line(_ELEVATION, {"geometry": "zlewnia (1).gpkg"})

    assert line.endswith("--geometry 'zlewnia (1).gpkg'")
    assert shlex.split(line)[-1] == "zlewnia (1).gpkg"


def test_flag_kind_prints_the_bare_flag_and_false_none_are_omitted():
    on = format_command_line(_ELEVATION, {"cutout": True})
    off = format_command_line(_ELEVATION, {"cutout": False, "year": None})

    assert on.endswith("elevation download --cutout")
    assert off == "kartograf elevation download"


def test_run_options_append_output_as_short_flag():
    line = format_command_line(
        _ELEVATION,
        {"product": "nmt", "year": 2020},
        run={"output_dir": "./data", "workers": 2, "quiet": True},
    )

    assert line == (
        "kartograf elevation download --product nmt --year 2020 -o ./data -w 2 -q"
    )


def test_positional_arguments_stay_where_they_are_declared():
    parse = _declared(
        Param("sheet", "str", positional=True),
        Param("hierarchy", "flag"),
        Param("descendants", "str"),
        id="parse",
    )
    project = _declared(
        Param("project_dir", "path", flag="--project", dest="project", cli_default="."),
        Param("name", "str", positional=True),
        Param("arguments", "str_list", positional=True, nargs="REMAINDER"),
        Param("tasks", "str_list", positional=True, nargs="*"),
        id="project add",
    )

    assert (
        format_command_line(parse, {"sheet": "N-34-130-D", "descendants": "1:10000"})
        == "kartograf parse N-34-130-D --descendants 1:10000"
    )
    assert format_command_line(
        project,
        {"name": "teren", "arguments": ["elevation", "download", "--product", "nmt"]},
        run={"project_dir": "/p q", "tasks": ["a", "b"]},
    ) == (
        "kartograf project add --project '/p q' teren elevation download "
        "--product nmt a b"
    )
    assert format_command_line(project, {"name": "x"}, run={"project_dir": "."}) == (
        "kartograf project add x"
    )


def test_the_line_parses_back_to_the_given_values():
    options = {
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": {"pl": "1m", "cz": "2m"},
        "geometry": "a b.gpkg",
    }

    words = shlex.split(format_command_line(_ELEVATION, options))

    assert words[:3] == ["kartograf", "elevation", "download"]
    assert words[3:] == [
        "--product",
        "nmt",
        "--sheet",
        "N-34-130-D-d-2-4",
        "--geometry",
        "a b.gpkg",
        "--resolution",
        "pl=1m,cz=2m",
    ]


@pytest.mark.parametrize(
    ("options", "run"),
    [
        ({"nope": 1}, None),
        ({"product": "nmt"}, {"product": "nmpt"}),
        ({"cutout": "yes"}, None),
        ({"bbox": [1, 2, 3], "bbox_crs": "EPSG:2180"}, None),
        ({"resolution": 5}, None),
        ({"year": "2020"}, None),
    ],
)
def test_a_value_without_a_command_line_form_is_refused(options, run):
    with pytest.raises(ValueError):
        format_command_line(_ELEVATION, options, run)


def test_api_only_parameter_and_command_have_no_command_line():
    with_update = _declared(Param("product", "str"), Param("update", "str", flag=None))
    api_only = Command(
        "find_sheets",
        "Godla",
        "query",
        "find_sheets",
        "kartograf-sheets/1",
        (),
        cli=None,
    )

    with pytest.raises(ValueError, match="update"):
        format_command_line(with_update, {"update": "force"})
    with pytest.raises(ValueError, match="find_sheets"):
        format_command_line(api_only, {})


def test_example_command_line_adds_the_store_directory():
    example = Example({"product": "nmt", "year": 2020}, run={"quiet": True})
    stored = Example({"product": "nmt"}, run={"output_dir": "~/dane"})
    without_store = _declared(Param("product", "str"), id="elevation list-sources")

    assert example_command_line(_ELEVATION, example) == (
        "kartograf elevation download --product nmt --year 2020 -o ./data -q"
    )
    assert example_command_line(_ELEVATION, stored) == (
        "kartograf elevation download --product nmt -o '~/dane'"
    )
    assert example_command_line(without_store, Example({"product": "nmt"})) == (
        "kartograf elevation list-sources --product nmt"
    )
