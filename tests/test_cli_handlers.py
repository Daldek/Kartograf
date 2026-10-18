"""Handlers of the CLI as functions of a parsed line (``argparse.Namespace``):
what a command prints and returns, without the parser and ``main``."""

import argparse

import pytest

from kartograf import get_catalog
from kartograf.catalog.cliparser import _subparsers
from kartograf.cli._handlers import HANDLERS
from kartograf.cli._parser import create_parser
from kartograf.cli.catalog_cmd import cmd_catalog
from kartograf.exceptions import ValidationError


def _catalog_text(capsys, **given) -> str:
    words = {"group": None, "command": None, "params": False, "json": False}
    code = cmd_catalog(argparse.Namespace(**{**words, **given}))
    assert code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def test_catalog_text_lists_groups_commands_summaries(capsys):
    text = _catalog_text(capsys)
    lines = text.splitlines()
    flat = " ".join(text.split())  # long summaries wrap
    catalog = get_catalog()

    for command in catalog.commands:
        line = next(line for line in lines if line.lstrip().startswith(command.id))
        assert command.kind in line and command.summary in line
        assert ("[tylko API]" in line) == (command.cli is None)
    for group in catalog.groups:
        header = next(line for line in lines if line.startswith(f"{group.name}: "))
        assert group.summary in header
        for product in group.products:
            assert f"{product.name} - {product.summary}" in flat
    assert "Komendy bez grupy:" in text
    assert "Parametry:" not in text  # the short view has no parameters


def test_catalog_group_and_command_views(capsys):
    group = _catalog_text(capsys, group="elevation")
    command = _catalog_text(capsys, group="elevation", command="download")
    download = get_catalog(command="elevation download").commands[0]

    assert "elevation download" in group and "elevation availability" in group
    assert "soil download" not in group and "Komendy bez grupy:" not in group
    assert "Parametry:" not in group
    assert download.description.split()[0] in command
    assert "FLAGA" in command and "ARGUMENT" in command and "WYMAGANY" in command
    # the table of parameters: flag, API argument, kind, required, values, text
    product = next(p for p in download.params or () if p.name == "product")
    row = next(
        line for line in command.splitlines() if line.lstrip().startswith("--product")
    )
    assert "product" in row and product.kind in row and "tak" in row
    assert "Dozwolone wartosci: " + ", ".join(product.allowed or ()) in command
    assert product.description.split(" - ")[0].split()[0] in command
    output = next(line for line in command.splitlines() if "--output, -o" in line)
    assert "output_dir" in output
    for constraint in download.constraints or ():
        assert constraint.message in command
    for example in download.examples or ():
        assert example.command_line in command
    assert "download_data -> kartograf-download/1" in command
    assert "check_data -> kartograf-plan/1" in command


def test_catalog_params_flag_adds_params_to_group_view(capsys):
    short = _catalog_text(capsys, group="soil")
    detailed = _catalog_text(capsys, group="soil", params=True)
    everything = _catalog_text(capsys, params=True)

    assert "Parametry:" not in short and "--depth" not in short
    assert detailed.count("Parametry:") == 4  # download, hsg, list-sources, list-layers
    assert "--depth" in detailed and "elevation download" not in detailed
    assert "elevation download" in everything and "find_sheets" in everything
    # a command without a group has its parameters too
    assert "<sheet>" in everything


def test_catalog_command_without_a_group(capsys):
    parse = _catalog_text(capsys, group="parse")
    api_only = _catalog_text(capsys, group="find_sheets")

    assert parse.startswith("parse: ") and "<sheet>" in parse
    assert "kartograf parse N-34-130-D-d-2-4" in parse
    assert api_only.startswith("find_sheets: ") and "tylko API" in api_only


@pytest.mark.parametrize(
    "given",
    [
        {},
        {"group": "elevation"},
        {"group": "elevation", "command": "download"},
        {"group": "soil", "params": True},
        {"params": True},
        {"group": "parse"},
    ],
    ids=["all", "group", "command", "group-params", "all-params", "no-group-command"],
)
def test_catalog_json_is_the_library_document(capsys, given):
    view = {
        "group": given.get("group"),
        "command": given.get("command"),
        "params": given.get("params") or None,
    }
    if view["command"] is not None:
        view["command"] = f"{view['group']} {view['command']}"
    if view["group"] == "parse":
        view["group"], view["command"] = None, "parse"

    printed = _catalog_text(capsys, json=True, **given)

    assert printed == get_catalog(**view).to_json()


@pytest.mark.parametrize(
    ("given", "option"),
    [
        ({"group": "nope"}, "group"),
        ({"group": "nope", "command": "download"}, "group"),
        ({"group": "elevation", "command": "nope"}, "command"),
        ({"command": "download"}, "group"),
    ],
    ids=["group", "group-and-command", "command-of-a-group", "command-without-group"],
)
def test_catalog_unknown_group_is_a_validation_error(given, option, capsys):
    with pytest.raises(ValidationError) as caught:
        _catalog_text(capsys, **given)

    assert caught.value.option == option
    if option == "group" and "command" not in given:
        assert "elevation" in caught.value.allowed
        assert "parse" in caught.value.allowed
    assert capsys.readouterr().out == ""


def _command_ids(parser) -> set[str]:
    """The ``_command_id`` every command parser of the CLI marks its lines with."""
    ids = set()
    for _, child in (
        _subparsers(parser) or argparse.Namespace(choices={})
    ).choices.items():
        inner = _subparsers(child)
        for leaf in [child] if inner is None else inner.choices.values():
            ids.add(leaf.get_default("_command_id"))
    return ids


def test_every_catalog_cli_command_has_a_handler():
    parsed = _command_ids(create_parser())
    declared = {c.id for c in get_catalog().commands if c.cli is not None}

    assert len(parsed) == 37 and None not in parsed
    assert parsed == declared
    assert parsed <= set(HANDLERS)


def test_no_handler_without_a_catalog_command():
    declared = {c.id for c in get_catalog().commands if c.cli is not None}

    assert set(HANDLERS) == declared
