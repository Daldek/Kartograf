"""``kartograf-commands/1`` and ``kartograf-command-list/1`` of the real declarations
(AGI-2.4, AGI-4.1, DOC-1.7): every command validates against the vendored Nogat schema,
the documents stay within the page budget and every example call parses with the real
parser and is the canonical line of its call."""

import json
import shlex
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from kartograf import command_schema, format_command, list_commands, parse_command
from kartograf.catalog.cliparser import parse_command_line
from kartograf.catalog.commands import declared
from kartograf.cli._parser import create_parser

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas" / "nogat"
NAMES = [command.id for command in declared().commands]
# DOC-1.7: the default page of a CLI or MCP result (compact JSON, as a client gets it)
PAGE_BUDGET = 20_000


def _load(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator() -> jsonschema.Draft202012Validator:
    """The schema of the catalog; it points into ``error-1`` (the registry codes)."""
    schemas = [_load(n) for n in ("result-1", "error-1", "commands-1")]
    registry: Registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    return jsonschema.Draft202012Validator(_load("commands-1"), registry=registry)


@pytest.mark.parametrize("name", NAMES)
def test_the_schema_of_every_command_validates_against_commands_1(name, validator):
    document = json.loads(command_schema(name).to_json(indent=None))

    validator.validate(document)
    (entry,) = document["commands"]
    assert document["schema"] == "kartograf-commands/1"
    assert entry["name"] == name
    assert entry["examples"] and entry["i18n"]["pl"]["summary"]


@pytest.mark.parametrize("name", NAMES)
def test_the_schema_of_a_command_is_within_the_page_budget(name):
    assert len(command_schema(name).to_json(indent=None)) <= PAGE_BUDGET


def test_the_largest_schema_is_elevation_download_and_has_room_to_grow():
    sizes = {n: len(command_schema(n).to_json(indent=None)) for n in NAMES}

    assert max(sizes, key=sizes.__getitem__) == "elevation download"
    assert sizes["elevation download"] <= PAGE_BUDGET * 0.85


def test_the_list_is_within_the_page_budget():
    document = list_commands()

    assert len(document.to_json(indent=None)) <= PAGE_BUDGET
    assert len(document.commands) == len(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_the_call_of_every_example_parses_with_the_real_parser(name):
    parser = create_parser(usage_errors=True)
    (entry,) = command_schema(name).commands

    for example in entry.examples:
        words = shlex.split(example.call)
        assert words[0] == "kartograf", example.call
        parsed = parse_command_line(parser, words[1:])
        assert parsed._command_id == name, example.call


@pytest.mark.parametrize("name", NAMES)
def test_the_call_of_every_example_is_the_line_format_command_writes(name):
    """An example is canonical: the line ``format_command`` writes for the call it
    reads back into, the order of the flags too, so a tool that exchanges lines
    (Archiwista) compares them as text."""
    (entry,) = command_schema(name).commands

    for example in entry.examples:
        call = parse_command(example.call)
        line = format_command(call.command, call.options, run=call.run)
        assert line == example.call


@pytest.mark.parametrize("name", NAMES)
def test_every_option_is_an_argument_of_the_function_or_the_plan_option(name):
    command = next(c for c in declared().commands if c.id == name)
    (entry,) = command_schema(name).commands
    arguments = {p.api_argument for p in command.params if p.api_argument}

    assert {o.name for o in entry.options} <= arguments | {"check"}
    assert ("check" in {o.name for o in entry.options}) == (command.supports_check)
    assert (entry.check == name) == command.supports_check
