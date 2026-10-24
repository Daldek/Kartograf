"""The tools of the MCP server as data (AGI-5.2 to AGI-5.5, AGI-5.8, AGI-5.12).

Names, families, input schemas, annotations and the modes of the server, all read from
the command catalog. No test here needs the MCP SDK; the ones that check a schema need
``jsonschema``.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import kartograf
from kartograf._output_schema import OUTPUT_SCHEMA
from kartograf.catalog import tools as tools_module
from kartograf.catalog.build import command_entries, declared_options
from kartograf.catalog.commands import declared
from kartograf.catalog.spec import CORE_MAX
from kartograf.catalog.tools import (
    ALWAYS_LOAD_COMMANDS,
    DESCRIPTION_MAX,
    FAMILIES,
    PLAN_ONLY_NOTE,
    RUN_OPTIONS,
    check_families,
    hidden_tools,
    parse_families,
    task_paths,
    tool_specs,
)
from kartograf.exceptions import ValidationError
from kartograf.project.commands import COMMANDS

REPO = Path(__file__).resolve().parent.parent.parent
CATALOG = {command.id: command for command in declared().commands}
ENTRIES = {entry.name: entry for entry in command_entries()}
TOOL_COMMANDS = [command for command in CATALOG.values() if command.family]
DATA_COMMANDS = [command for command in CATALOG.values() if command.project_task]
CHECKED = [command for command in TOOL_COMMANDS if command.supports_check]
WRITING = {"project init", "project add", "project remove"}
CORE = {
    "commands list",
    "commands schema",
    "sheet find",
    "elevation availability",
    "elevation download",
    "imagery download",
    "landcover download",
    "soil download",
    "soil hsg",
    "store overview",
}
WRITES = {spec.name: spec for spec in tool_specs(allow_writes=True)}
PLANS = {spec.name: spec for spec in tool_specs(allow_writes=False)}
POLISH_LETTERS = re.compile("[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")


def _name(command: str) -> str:
    return CATALOG[command].operation_id


def _descriptions(schema):
    """Every ``description`` of a JSON Schema, at any depth."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "description":
                yield value
            else:
                yield from _descriptions(value)
    elif isinstance(schema, list):
        for item in schema:
            yield from _descriptions(item)


def _text(spec) -> str:
    """Everything a client reads of a tool, as text."""
    return json.dumps(
        [spec.title, spec.description, spec.input_schema], ensure_ascii=False
    )


# -- names and families -------------------------------------------------------------


def test_every_command_with_a_family_is_one_tool_in_the_order_of_the_catalog():
    expected = [command.operation_id for command in TOOL_COMMANDS]

    assert len(expected) == 39
    assert list(WRITES) == expected
    # the commands of the cache and the settings are no tools
    assert {c.id for c in CATALOG.values() if not c.family} == {
        "cache stats",
        "cache clear",
        "cache path",
        "config show",
    }
    assert [s.name for s in tool_specs(allow_writes=True)] == expected  # deterministic


def test_names_are_the_operation_ids_within_48_characters():
    for name in WRITES:
        assert re.fullmatch(r"kartograf_[a-z0-9_]+", name), name
        assert len(name) <= 48, name
    for command in TOOL_COMMANDS:
        spec = WRITES[command.operation_id]
        assert spec.command == command.id
        assert spec.function in kartograf.__all__, command.id
        assert spec.check_function == command.check_function
        if spec.check_function is not None:
            assert spec.check_function in kartograf.__all__, command.id


def test_the_families_are_those_of_the_catalog_with_core_apart():
    counts = {
        family: sum(1 for s in WRITES.values() if family in s.families)
        for family in FAMILIES
    }

    assert FAMILIES == (
        "discovery",
        "availability",
        "data",
        "project",
        "store",
        "core",
    )
    assert counts == {
        "discovery": 17,
        "availability": 1,
        "data": 12,
        "project": 6,
        "store": 3,
        "core": 10,
    }
    for spec in WRITES.values():
        assert spec.families == CATALOG[spec.command].families


def test_core_is_the_ten_tools_of_the_main_tasks():
    core = [s for s in WRITES.values() if "core" in s.families]

    assert {s.command for s in core} == CORE
    assert len(core) <= CORE_MAX
    assert [s.name for s in tool_specs(("core",), allow_writes=True)] == [
        s.name for s in core
    ]


def test_the_family_filter_keeps_the_order_of_the_catalog():
    selected = tool_specs(("data", "discovery"), allow_writes=True)

    assert {s.families[0] for s in selected} == {"data", "discovery"}
    assert [s.name for s in selected] == [
        s.name for s in WRITES.values() if s.families[0] in ("data", "discovery")
    ]
    assert tool_specs(None, allow_writes=True) == tool_specs(allow_writes=True)
    assert (
        len(tool_specs(("discovery", "availability", "data"), allow_writes=True)) == 30
    )


@pytest.mark.parametrize("names", [("discovery", "nope", "x"), ()])
def test_an_unknown_or_empty_family_is_a_validation_error(names):
    for call in (check_families, lambda n: tool_specs(n, allow_writes=True)):
        with pytest.raises(ValidationError) as caught:
            call(names)

        assert caught.value.option == "families"
        assert caught.value.allowed == FAMILIES
        assert "unknown tool family" in str(caught.value)
    with pytest.raises(ValidationError, match="'nope', 'x'"):
        parse_families("data, nope,x")
    assert parse_families("data, core") == ("data", "core")


# -- the mode of the server -----------------------------------------------------------


def test_a_server_without_writes_offers_plans_and_hides_the_writes_without_a_check():
    assert len(PLANS) == 36
    assert hidden_tools(allow_writes=False) == {
        _name(command): command for command in sorted(WRITING)
    }
    assert hidden_tools(allow_writes=True) == {}
    assert not WRITING & {s.command for s in PLANS.values()}
    assert set(WRITES) - set(PLANS) == {_name(command) for command in WRITING}
    # a family limits what is hidden too
    assert hidden_tools(("core",), allow_writes=False) == {}
    assert set(hidden_tools(("project",), allow_writes=False)) == {
        _name(command) for command in WRITING
    }


def test_the_commands_that_write_and_have_a_check_are_plans_without_writes():
    plans = {name for name, spec in PLANS.items() if spec.plan_only}

    assert plans == {command.operation_id for command in CHECKED}
    assert len(plans) == 13  # the twelve data commands and project download
    assert not any(spec.plan_only for spec in WRITES.values())
    for command in CHECKED:
        full, plan = WRITES[command.operation_id], PLANS[command.operation_id]
        options = set(full.input_schema["properties"])
        assert plan.refused == options & set(RUN_OPTIONS)
        assert plan.refused  # every command with a check has an option of a run
        assert set(plan.input_schema["properties"]) == options - plan.refused
        assert plan.input_schema["properties"]["check_updates"]["const"] is True
        assert plan.input_schema["properties"]["check_updates"]["default"] is True
        assert "const" not in full.input_schema["properties"]["check_updates"]
        assert plan.description.endswith(PLAN_ONLY_NOTE)
        assert plan.description.startswith(full.description)
        assert plan.kinds.keys() == full.kinds.keys() - plan.refused
        assert plan.annotations.read_only_hint is True
        assert plan.annotations.destructive_hint is False
    # the other tools are the same in both modes
    for name, spec in PLANS.items():
        if not spec.plan_only:
            assert spec == WRITES[name]


def test_the_run_options_are_update_plan_workers_and_summary():
    seen = set()
    for command in CHECKED:
        seen |= set(PLANS[command.operation_id].refused)

    assert seen == set(RUN_OPTIONS)
    assert PLANS["kartograf_project_download"].refused == {"update", "workers"}
    assert PLANS["kartograf_soil_hsg"].refused == {"update", "plan", "summary"}
    # a plan keeps the store and the task: what the check reads
    assert {"output_dir", "product"} <= set(
        PLANS["kartograf_elevation_download"].input_schema["properties"]
    )
    assert {"project_dir", "tasks"} <= set(
        PLANS["kartograf_project_download"].input_schema["properties"]
    )


def test_check_updates_is_an_option_of_the_commands_with_a_check_only():
    for command in TOOL_COMMANDS:
        properties = WRITES[command.operation_id].input_schema["properties"]

        assert ("check_updates" in properties) == command.supports_check, command.id
    assert "kartograf_check_updates" not in WRITES
    assert "kartograf_project_check_updates" not in WRITES


# -- input schemas --------------------------------------------------------------------


def _every_schema():
    for specs in (WRITES, PLANS):
        yield from specs.values()


def test_input_schemas_are_valid_closed_draft_2020_12_objects():
    validator = pytest.importorskip("jsonschema").Draft202012Validator

    for spec in _every_schema():
        schema = spec.input_schema
        validator.check_schema(schema)
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        # clients that hand the schema to a model API reject these at the top level
        for keyword in ("oneOf", "anyOf", "allOf", "not", "if"):
            assert keyword not in schema, (spec.name, keyword)
        for name, definition in schema["properties"].items():
            assert definition.get("description"), (spec.name, name)


@pytest.mark.parametrize("command", TOOL_COMMANDS, ids=lambda c: c.id)
def test_a_schema_has_the_options_of_the_command(command):
    entry = ENTRIES[command.id]
    schema = WRITES[command.operation_id].input_schema
    options = declared_options(command)

    assert list(schema["properties"]) == [p.name for p in options]
    assert schema.get("required", []) == [o.name for o in entry.options if o.required]
    for option in entry.options:
        prop = schema["properties"][option.name]
        assert prop["description"] == option.description
        if option.default is not None:
            assert prop["default"] == option.default
        if option.minimum is not None:
            assert prop["minimum"] == option.minimum
        if option.examples:
            assert prop["examples"] == list(option.examples)
        if option.enum and (command.id, option.name) != ("commands schema", "command"):
            values = [e.value for e in option.enum]
            flat = json.dumps(prop)
            assert all(json.dumps(v) in flat for v in values), option.name
    assert {("commands schema", "command")} == tools_module._NO_ENUM
    assert (
        "enum"
        not in WRITES["kartograf_commands_schema"].input_schema["properties"]["command"]
    )


@pytest.mark.parametrize("command", TOOL_COMMANDS, ids=lambda c: c.id)
def test_every_property_has_the_json_type_of_its_kind(command):
    schema = WRITES[command.operation_id].input_schema
    properties = schema["properties"]

    for param in declared_options(command):
        prop = properties[param.name]
        match param.kind:
            case "str" | "bbox_crs" | "path":
                assert prop["type"] == "string"
            case "int":
                assert prop["type"] == "integer"
            case "flag":
                assert prop["type"] == "boolean"
            case "bbox":
                assert prop["type"] == "array" and prop["items"] == {"type": "number"}
                assert prop["minItems"] == prop["maxItems"] == 4
            case "per_country":
                string, mapping = prop["anyOf"]
                assert string["type"] == "string"
                assert set(mapping["properties"]) == {"pl", "cz"}
                assert mapping["additionalProperties"] is False
            case "str_list":
                assert prop["type"] == "array" and prop["items"]["type"] == "string"
            case "plan" | "options":
                assert prop["type"] == "object"
    assert ("dependentRequired" in schema) == ("bbox" in properties)
    if "bbox" in properties:
        assert schema["dependentRequired"] == {"bbox": ["bbox_crs"]}


def test_the_allowed_values_of_a_per_country_option_reach_both_forms():
    prop = WRITES["kartograf_elevation_download"].input_schema["properties"][
        "vertical_crs"
    ]
    string, mapping = prop["anyOf"]

    assert string["enum"] == mapping["properties"]["pl"]["enum"]
    assert mapping["properties"]["cz"]["enum"] == string["enum"]
    assert {"EVRF2007", "KRON86", "Bpv"} == set(string["enum"])


def test_the_options_of_an_area_name_the_alternatives_in_their_descriptions():
    properties = WRITES["kartograf_elevation_download"].input_schema["properties"]

    for name in ("sheet", "bbox", "geometry"):
        assert (
            "Give exactly one of `sheet`, `bbox`, `geometry`."
            in (properties[name]["description"])
        )
    assert "exactly one" not in properties["product"]["description"]


def test_the_catalog_tools_take_no_argument_and_the_command_to_describe():
    listing = WRITES["kartograf_commands_list"].input_schema
    schema = WRITES["kartograf_commands_schema"].input_schema

    assert listing["properties"] == {}
    assert "required" not in listing
    assert list(schema["properties"]) == ["command"]
    assert schema["required"] == ["command"]
    # the 43 names are the list's: a second copy in every tools/list is waste
    assert "enum" not in schema["properties"]["command"]


def test_the_list_and_layer_tools_take_their_group_from_the_command():
    for command in CATALOG.values():
        if not command.id.endswith(("list-sources", "list-layers")):
            continue
        spec = WRITES[command.operation_id]

        assert spec.fixed == {"group": command.group}
        assert "group" not in spec.input_schema["properties"]
        assert spec.function in ("list_sources", "list_layers")
    assert set(
        WRITES["kartograf_elevation_list_sources"].input_schema["properties"]
    ) == {"product"}


def test_project_add_takes_a_command_and_its_options():
    schema = WRITES["kartograf_project_add"].input_schema
    properties = schema["properties"]

    assert properties["command"]["enum"] == [c.id for c in DATA_COMMANDS]
    assert properties["options"]["type"] == "object"
    assert {"project_dir", "name", "command", "options"} <= set(schema["required"])
    assert "arguments" not in properties  # the words of a CLI line


def test_every_argument_has_a_kind_and_the_data_tools_know_their_task_options():
    for spec in WRITES.values():
        properties = set(spec.input_schema["properties"]) - {"check_updates"}

        assert set(spec.kinds) == properties, spec.name
        assert set(spec.paths) <= set(spec.kinds)
        assert all(spec.kinds[name] == "path" for name in spec.paths)
    for command in DATA_COMMANDS:
        spec = WRITES[command.operation_id]

        assert set(spec.task_options) == set(COMMANDS[command.id].options)
        assert "output_dir" in spec.input_schema["required"]
        assert not {"quiet", "json", "upgrade", "force"} & set(spec.kinds)
    assert all(
        not s.task_options
        for s in WRITES.values()
        if s.command not in {c.id for c in DATA_COMMANDS}
    )


def test_every_path_has_a_role_and_nested_task_paths_are_known():
    roles = {role for spec in WRITES.values() for role in spec.paths.values()}

    assert roles == {"input", "output", "root"}
    assert WRITES["kartograf_store_overview"].paths == {"output_dir": "root"}
    assert WRITES["kartograf_project_init"].paths == {
        "project_dir": "output",
        "output_dir": "root",
    }
    assert task_paths("elevation download") == {"geometry": "input"}
    with pytest.raises(KeyError):
        task_paths("nope nope")


# -- descriptions, titles and annotations ----------------------------------------------


def test_a_description_is_the_summary_the_description_and_the_rules_in_600_characters():
    for spec in _every_schema():
        entry = ENTRIES[spec.command]

        assert spec.title == entry.summary
        assert spec.description.startswith(entry.summary + "\n\n" + entry.description)
        for rule in entry.rules:
            assert rule in spec.description
        assert len(spec.description) <= DESCRIPTION_MAX, spec.name
        assert len(entry.summary) <= 100
        assert spec.annotations.title == spec.title


def test_the_texts_a_client_reads_are_english_without_flags_or_steering():
    for spec in _every_schema():
        text = _text(spec)

        assert not POLISH_LETTERS.search(text), spec.name
        assert "check-updates" not in text
        for banned in ("always recommend", "best tool for", "ignore previous"):
            assert banned not in text.lower(), spec.name


@pytest.mark.parametrize("command", TOOL_COMMANDS, ids=lambda c: c.id)
def test_the_annotations_follow_the_effects_of_the_command(command):
    entry = ENTRIES[command.id]
    spec = WRITES[command.operation_id]
    hints = spec.annotations

    assert hints.read_only_hint is entry.effects.read_only
    assert hints.destructive_hint is (
        entry.effects.destructive and not hints.read_only_hint
    )
    assert hints.idempotent_hint is entry.effects.idempotent
    assert hints.open_world_hint is ("network" in command.effects)


def test_the_annotations_of_the_tools_that_matter():
    for command in DATA_COMMANDS:
        hints = WRITES[command.operation_id].annotations

        # a protocol default of "destructive" is wrong for a store that never
        # overwrites: the write tools say so
        assert (hints.read_only_hint, hints.destructive_hint) == (False, False)
        assert (hints.idempotent_hint, hints.open_world_hint) == (True, True)
    assert WRITES["kartograf_project_remove"].annotations.destructive_hint is True
    assert WRITES["kartograf_project_add"].annotations.idempotent_hint is False
    assert WRITES["kartograf_elevation_availability"].annotations.read_only_hint is True
    assert (
        WRITES["kartograf_elevation_availability"].annotations.open_world_hint is True
    )
    assert WRITES["kartograf_sheet_parse"].annotations.open_world_hint is False
    # the mode: a plan reads, whatever the command can do
    plan = PLANS["kartograf_project_download"].annotations
    assert (plan.read_only_hint, plan.destructive_hint) == (True, False)
    assert WRITES["kartograf_project_download"].annotations.read_only_hint is False


def test_only_the_two_catalog_tools_are_loaded_up_front():
    for specs in (WRITES, PLANS):
        always = [s.command for s in specs.values() if s.always_load]

        assert always == list(ALWAYS_LOAD_COMMANDS)
    assert tools_module.ALWAYS_LOAD_KEY == "anthropic/alwaysLoad"


def test_every_tool_answers_with_the_result_envelope():
    for spec in _every_schema():
        assert spec.output_schema is OUTPUT_SCHEMA
    assert OUTPUT_SCHEMA["title"] == "kartograf-result/1"


def test_a_mode_is_not_a_cache_of_another():
    first = tool_specs(allow_writes=False)
    again = tool_specs(allow_writes=False)

    assert first is again  # built once per process
    assert tool_specs(allow_writes=True) is not first
    tools_module.clear_caches()
    assert tool_specs(allow_writes=False) is not first
    assert tool_specs(allow_writes=False) == first


def test_tools_list_without_the_output_schema_stays_in_its_budget():
    """What a client puts in the context for the options of every tool: the
    descriptions are the catalog's, so the list is long, and ``--tools core`` is the
    short form (AGI-5.12)."""

    def size(specs) -> int:
        wire = [
            {
                "name": s.name,
                "title": s.title,
                "description": s.description,
                "inputSchema": s.input_schema,
            }
            for s in specs
        ]
        return len(json.dumps(wire, ensure_ascii=False, separators=(",", ":")))

    assert size(tool_specs(allow_writes=True)) <= 95_000
    assert size(tool_specs(("core",), allow_writes=True)) <= 40_000


def test_tools_module_needs_neither_mcp_nor_jsonschema():
    code = (
        "import sys\n"
        "sys.modules['mcp'] = None\n"
        "import kartograf.catalog.tools as tools\n"
        "assert len(tools.tool_specs(allow_writes=True)) == 39\n"
        "assert 'jsonschema' not in sys.modules\n"
    )

    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True
    )

    assert done.returncode == 0, done.stderr
