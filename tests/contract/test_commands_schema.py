"""``kartograf-commands/1`` and ``kartograf-command-list/1`` of the real declarations
(AGI-2.4, AGI-4.1, DOC-1.7): every command validates against the vendored Nogat schema,
on the default page and on the page of a form (ADR-063), the list against its schema,
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
from kartograf.messages import fold, localize

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas" / "nogat"
NAMES = [command.id for command in declared().commands]
# DOC-1.7: the default page of a CLI or MCP result (compact JSON, as a client gets it)
PAGE_BUDGET = 20_000
# DOC-1.7: the most a page may have: the page of a form (``--form``, ADR-063 J2)
FORM_BUDGET = 50_000


def _load(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry() -> Registry:
    """The vendored schemas by ``$id``: ``commands-1`` points into ``error-1`` (the
    registry codes) and ``command-list-1`` into ``commands-1``."""
    schemas = [
        _load(n) for n in ("result-1", "error-1", "commands-1", "command-list-1")
    ]
    return Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )


@pytest.fixture(scope="module")
def validator(registry) -> jsonschema.Draft202012Validator:
    """The schema of the catalog."""
    return jsonschema.Draft202012Validator(_load("commands-1"), registry=registry)


@pytest.mark.parametrize("form", [False, True], ids=["default", "form"])
@pytest.mark.parametrize("name", NAMES)
def test_the_schema_of_every_command_validates_against_commands_1(
    name, form, validator
):
    document = json.loads(command_schema(name, form=form).to_json(indent=None))

    validator.validate(document)
    (entry,) = document["commands"]
    assert document["schema"] == "kartograf-commands/1"
    assert entry["name"] == name
    assert entry["examples"] and entry["i18n"]["pl"]["summary"]


def test_the_list_validates_against_command_list_1(registry):
    validator = jsonschema.Draft202012Validator(
        _load("command-list-1"), registry=registry
    )
    document = json.loads(list_commands().to_json(indent=None))

    validator.validate(document)
    # what a proxy (Latarnik) routes by: every row says its effects and its route
    assert all({"effects", "rest"} <= set(row) for row in document["commands"])


@pytest.mark.parametrize("name", NAMES)
def test_the_schema_of_a_command_is_within_the_page_budget(name):
    assert len(command_schema(name).to_json(indent=None)) <= PAGE_BUDGET
    assert len(command_schema(name, form=True).to_json(indent=None)) <= FORM_BUDGET


def test_the_largest_schema_is_elevation_download_and_has_room_to_grow():
    sizes = {n: len(command_schema(n).to_json(indent=None)) for n in NAMES}

    assert max(sizes, key=sizes.__getitem__) == "elevation download"
    assert sizes["elevation download"] <= PAGE_BUDGET * 0.90


def test_the_list_is_within_the_page_budget():
    document = list_commands()

    assert len(document.to_json(indent=None)) <= PAGE_BUDGET
    assert len(document.commands) == len(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_the_page_of_a_form_adds_only_the_sections_and_the_polish_texts(name):
    """``--form`` (ADR-063, J2): each option of the default page with its section
    (the English title of its ``--help`` section) and ``i18n.pl``: the Polish
    description, section and the meaning of every allowed value by the value as text,
    with their Polish letters, which only a terminal folds (ADR-053 amendment 1). The
    default page has none of them."""
    command = next(c for c in declared().commands if c.id == name)
    sections = {param.name: param.section for param in command.params}
    default = json.loads(command_schema(name).to_json(indent=None))["commands"][0]
    form = json.loads(command_schema(name, form=True).to_json(indent=None))
    (entry,) = form["commands"]

    for plain, option in zip(default["options"], entry["options"], strict=True):
        where = option["name"]
        polish = option.pop("i18n")["pl"]
        section = sections[where]
        english = None if section is None else localize(section, "en")
        assert option.pop("section", None) == english, where
        assert option == plain, where  # nothing else changes
        assert polish.get("section") == (
            None if section is None else localize(section, "pl")
        )
        assert polish["description"] and fold(polish["description"]).isascii(), where
        values = [str(item["value"]) for item in plain.get("enum", ())]
        assert list(polish.get("enum", {})) == values, where
        assert all(
            text and fold(text).isascii() for text in polish.get("enum", {}).values()
        )
    assert {k: v for k, v in entry.items() if k != "options"} == {
        k: v for k, v in default.items() if k != "options"
    }


@pytest.mark.parametrize("name", NAMES)
def test_the_rules_of_every_command_name_only_its_options(name):
    """A form reads the rules as fields (AGI-2.3): each names other options of the
    same command, never a flag only the CLI has (``--upgrade``); the alternatives of
    the command's choice are the options of one ``one_of`` group."""
    (entry,) = command_schema(name).commands
    options = {option.name: option for option in entry.options}

    for option in entry.options:
        named = {*option.requires, *option.excludes}
        named |= {*(option.applies_to or {}), *(option.required_when or {})}
        assert named <= options.keys() - {option.name}, option.name
    chosen = [option for alternative in entry.one_of for option in alternative]
    assert set(chosen) <= options.keys()
    assert len({options[option].one_of for option in chosen}) <= 1


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
