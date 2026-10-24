"""Handlers of the CLI as functions of a parsed line (``argparse.Namespace``):
what a command prints and returns, without the parser and ``main``."""

import argparse

import pytest

from kartograf import command_schema, list_commands
from kartograf.catalog.cliparser import _subparsers
from kartograf.catalog.commands import declared
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.spec import resolve
from kartograf.cli._handlers import HANDLERS
from kartograf.cli._parser import create_parser
from kartograf.cli.catalog_cmd import cmd_commands_list, cmd_commands_schema
from kartograf.envelope import wrap
from kartograf.exceptions import ValidationError


def _list_text(capsys, **given) -> str:
    words = {"json": False, "_command_id": "commands list"}
    assert cmd_commands_list(argparse.Namespace(**{**words, **given})) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def _schema_text(capsys, command, **given) -> str:
    words = {"command": command, "json": False, "_command_id": "commands schema"}
    assert cmd_commands_schema(argparse.Namespace(**{**words, **given})) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out


def test_list_text_lists_groups_commands_summaries(capsys):
    text = _list_text(capsys)
    lines = text.splitlines()
    flat = " ".join(text.split())  # long summaries wrap

    for command in declared().commands:
        line = next(line for line in lines if line.lstrip().startswith(command.id))
        assert command.kind in line and command.summary_pl in line
    for group in declared().groups:
        header = next(line for line in lines if line.startswith(f"{group.name}: "))
        assert group.summary_pl in header
        for name, summary in resolve(group.products):
            assert f"{name} - {summary}" in flat
    assert "Parametry:" not in text  # the list has no parameters
    assert 'kartograf commands schema --command "<grupa> <komenda>"' in flat


def test_list_text_has_the_products_of_a_group(capsys):
    flat = " ".join(_list_text(capsys).split())

    assert "nmt - Numeryczny Model Terenu; PL i CZ" in flat
    assert "Produkty:" in flat


def test_schema_text_describes_one_command(capsys):
    text = _schema_text(capsys, "elevation download")
    command = next(c for c in declared().commands if c.id == "elevation download")

    assert text.startswith(f"elevation download: {command.summary_pl}\n")
    assert "FLAGA" in text and "ARGUMENT" in text and "WYMAGANY" in text
    # the table of parameters: flag, API argument, kind, required, values, text
    row = next(
        line for line in text.splitlines() if line.lstrip().startswith("--product")
    )
    assert "product" in row and "str" in row and "tak" in row
    product = next(p for p in command.params if p.name == "product")
    assert "Dozwolone wartosci: " + ", ".join(resolve(product.allowed) or ()) in text
    output = next(line for line in text.splitlines() if "--output, -o" in line)
    assert "output_dir" in output
    for constraint in command.constraints:
        assert constraint.message_pl in text
    for rule in command.rules_pl:
        assert rule in text
    for example in command.examples:
        assert example_command_line(command, example) in text
        assert example.title_pl in text
    assert "download_data -> kartograf-download/1" in text
    assert "check_data -> kartograf-plan/1" in text
    assert "operation_id: kartograf_elevation_download" in text


def test_schema_text_takes_the_operation_id_too(capsys):
    by_name = _schema_text(capsys, "sheet find")
    by_operation = _schema_text(capsys, "kartograf_sheet_find")

    assert by_name == by_operation
    assert by_name.startswith("sheet find: ")
    assert "kartograf sheet find --bbox" in by_name
    assert "<sheet>" in _schema_text(capsys, "sheet parse")


def test_list_json_is_the_envelope_of_the_library_document(capsys):
    printed = _list_text(capsys, json=True)

    assert printed == wrap("commands list", list_commands()).to_json()


@pytest.mark.parametrize("command", ["elevation download", "kartograf_soil_hsg"])
def test_schema_json_is_the_envelope_of_the_library_document(capsys, command):
    printed = _schema_text(capsys, command, json=True)

    assert printed == wrap("commands schema", command_schema(command)).to_json()


@pytest.mark.parametrize("given", [None, "nope", "elevation", "soil"])
def test_schema_of_an_unknown_or_missing_command_is_a_validation_error(given, capsys):
    with pytest.raises(ValidationError) as caught:
        _schema_text(capsys, given)

    assert caught.value.option == "command"
    assert caught.value.allowed is not None
    assert "elevation download" in caught.value.allowed
    assert "commands schema" in caught.value.allowed
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


def test_every_catalog_command_has_a_handler_and_the_other_way_round():
    parsed = _command_ids(create_parser())
    declared_ids = {c.id for c in declared().commands}

    assert len(parsed) == 43 and None not in parsed
    assert parsed == declared_ids
    assert set(HANDLERS) == declared_ids
