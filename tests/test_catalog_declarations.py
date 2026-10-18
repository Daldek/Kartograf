"""Declarations of the command catalog (spec 8.2-8.4): what a declaration
derives, when its providers run and which declarations are refused."""

import dataclasses

import pytest

from kartograf.catalog import shared
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param, resolve


def _command(*params: Param, **fields) -> Command:
    """A minimal valid command around ``params``."""
    values = {
        "id": "elevation download",
        "summary": "Pobierz dane",
        "kind": "data",
        "function": "download_data",
        "result_schema": "kartograf-download/1",
        "params": params,
    }
    return Command(**{**values, **fields})


def test_param_derives_flag_and_argument_from_name():
    param = Param("vertical_crs", "str")

    assert param.cli_flag == "--vertical-crs"
    assert param.api_argument == "vertical_crs"
    assert param.cli_dest == "vertical_crs"


def test_flag_none_is_api_only_and_argument_none_is_cli_only():
    api_only = Param("update", "str", flag=None)
    cli_only = Param("quiet", "flag", argument=None)
    renamed = Param("output_dir", "path", flag="--output", short="-o", dest="output")

    assert (api_only.cli_flag, api_only.api_argument) == (None, "update")
    assert (cli_only.cli_flag, cli_only.api_argument) == ("--quiet", None)
    assert (renamed.cli_flag, renamed.api_argument, renamed.cli_dest) == (
        "--output",
        "output_dir",
        "output",
    )


def test_positional_param_has_no_flag():
    sheet = Param("sheet", "str", positional=True, metavar="GODLO")

    assert sheet.cli_flag is None
    assert sheet.api_argument == "sheet"


def test_providers_are_called_late() -> None:
    calls: list[str] = []

    def allowed() -> tuple[str, ...]:
        calls.append("allowed")
        return ("nmt", "nmpt")

    def description() -> str:
        calls.append("description")
        return "Produkt (wymagany)"

    param = Param("product", "str", description, allowed=allowed, choices=True)
    command = _command(param, description=description)

    assert calls == []
    assert resolve(param.allowed) == ("nmt", "nmpt")
    assert resolve(param.description) == "Produkt (wymagany)"
    assert resolve(command.description) == "Produkt (wymagany)"
    assert calls == ["allowed", "description", "description"]
    assert resolve("plain text") == "plain text"
    assert resolve(("a", "b")) == ("a", "b")


def test_shared_param_can_be_overridden():
    product = dataclasses.replace(
        shared.PRODUCT,
        description="Produkt grupy",
        allowed=("nmt", "nmpt"),
        required=False,
    )

    assert product.description == "Produkt grupy"
    assert product.allowed == ("nmt", "nmpt")
    assert product.required is False
    # the shared declaration stays as it was
    assert shared.PRODUCT.required is True
    assert shared.PRODUCT.allowed is None


def test_required_needs_an_api_argument():
    with pytest.raises(ValueError, match="argument"):
        Param("quiet", "flag", argument=None, required=True)

    assert Param("sheet", "str", required=True).required is True


@pytest.mark.parametrize(
    "fields",
    [
        {"name": "Bad-Name", "kind": "str"},
        {"name": "x", "kind": "float"},
        {"name": "x", "kind": "str", "flag": "-x"},
        {"name": "x", "kind": "str", "short": "-xx"},
        {"name": "x", "kind": "str", "flag": None, "short": "-x"},
        {"name": "x", "kind": "str", "choices": True},
        {"name": "x", "kind": "str", "normalize": "title"},
        {"name": "x", "kind": "str", "nargs": "*"},
        {"name": "x", "kind": "str", "positional": True, "flag": "--x"},
        {"name": "x", "kind": "str", "positional": True, "dest": "y"},
        {"name": "x", "kind": "str", "exclusive": "update", "flag": None},
        {"name": "x", "kind": "str", "accepts": ("pl1992",)},
        {"name": "sheet", "kind": "str", "accepts": ("pl1993",)},
        {"name": "x", "kind": "str", "task": True, "argument": None},
    ],
)
def test_invalid_declaration_of_a_param_is_refused(fields):
    with pytest.raises(ValueError):
        Param(**fields)


def test_command_derives_group_name_and_check_support():
    plain = _command(Param("product", "str"))
    with_check = _command(
        Param("product", "str"),
        check_function="check_data",
        check_result_schema="kartograf-plan/1",
    )
    root = _command(id="parse", function="describe_sheet", kind="query")
    api_only = _command(id="find_sheets", cli=None, kind="query")

    assert (plain.group, plain.name, plain.cli_words) == (
        "elevation",
        "download",
        "elevation download",
    )
    assert plain.supports_check is False
    assert with_check.supports_check is True
    assert (root.group, root.name, root.cli_words) == (None, "parse", "parse")
    assert (api_only.group, api_only.cli_words) == (None, None)


@pytest.mark.parametrize(
    "fields",
    [
        {"id": "Elevation Download"},
        {"id": "a b c"},
        {"check_function": "check_data"},
        {"check_result_schema": "kartograf-plan/1"},
        {"project_task": True, "kind": "query"},
        {"kind": "other"},
        {"effects": ("teleport",)},
        {"result_schema": "download"},
    ],
)
def test_invalid_declaration_of_a_command_is_refused(fields):
    with pytest.raises(ValueError):
        _command(Param("product", "str"), **fields)


def test_command_params_must_have_unique_names():
    with pytest.raises(ValueError, match="product"):
        _command(Param("product", "str"), Param("product", "int"))


def test_api_only_command_declares_no_cli_flag():
    with pytest.raises(ValueError, match="flag"):
        _command(Param("segment", "str"), id="store_entries", cli=None)

    api_only = _command(
        Param("segment", "str", flag=None), id="store_entries", cli=None
    )
    assert api_only.params[0].cli_flag is None


def test_constraint_and_example_are_plain_data():
    constraint = Constraint(
        "requires", ("horizontal_crs",), "--cutout wymaga --horizontal-crs", "cutout"
    )
    example = Example({"product": "nmt"}, run={"quiet": True})

    assert (constraint.type, constraint.param, constraint.params) == (
        "requires",
        "cutout",
        ("horizontal_crs",),
    )
    assert constraint.when is None
    assert example.title is None
    assert example.options == {"product": "nmt"}


def test_group_has_a_position_in_the_help_list():
    plain = Group("elevation", "Wysokosci", "Dane wysokosciowe")
    last = Group("cache", "Cache", "Cache metadanych", position=2)

    assert plain.position < last.position
