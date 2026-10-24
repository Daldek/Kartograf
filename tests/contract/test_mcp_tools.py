"""The tools of the MCP server as data (spec 9.3, 9.4; test row 12.7): names,
families, input schemas and annotations, all read from the command catalog. No
test here needs the MCP SDK; the ones that check a schema need ``jsonschema``."""

import dataclasses
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

import kartograf
from kartograf.catalog import data_commands, get_catalog
from kartograf.catalog import tools as tools_module
from kartograf.catalog.tools import FAMILIES, check_arguments_schema, tool_specs
from kartograf.serialization import SCHEMAS

REPO = Path(__file__).resolve().parent.parent.parent
RUN_ARGUMENTS = {"update", "plan", "workers", "summary"}
CLI_ONLY_FLAGS = {"quiet", "json", "check_updates", "upgrade", "force"}
NO_ENUM = tools_module._NO_ENUM
WORDS = tools_module._BRIEF
WORDS_FOR = tools_module._BRIEF_FOR

SPECS = {spec.name: spec for spec in tool_specs()}
CATALOG = {command.id: command for command in get_catalog(params=True).commands}
DATA_TOOLS = [spec for spec in SPECS.values() if spec.family == "data"]
# a tool that runs one command of its own (not a shared or a check tool)
SINGLE = [s for s in SPECS.values() if len(s.commands) == 1 and not s.check]


def _result_schema(spec) -> str:
    if spec.name == "check_updates":
        schema = CATALOG["elevation download"].check_result_schema
    else:
        command = CATALOG[spec.commands[0]]
        schema = command.check_result_schema if spec.check else command.result_schema
    assert schema is not None
    return schema


def _has_ok(schema: str) -> bool:
    keys = [
        cls.JSON_KEYS or tuple(f.name for f in dataclasses.fields(cast(Any, cls)))
        for cls in SCHEMAS[schema]
    ]
    return any("ok" in names for names in keys)


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


def test_tool_names_are_unique_snake_case():
    names = [spec.name for spec in tool_specs()]

    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in names)


def test_there_are_29_tools_in_six_families():
    specs = tool_specs()
    counts = {f: sum(1 for s in specs if s.family == f) for f in FAMILIES}

    assert len(specs) == 29
    assert counts == {
        "discovery": 5,
        "availability": 1,
        "data": 12,
        "check": 1,
        "project": 7,
        "store": 3,
    }
    assert [s.family for s in specs] == sorted(
        (s.family for s in specs), key=FAMILIES.index
    )


def test_every_catalog_tool_name_has_a_spec_and_only_check_updates_has_no_command():
    catalog_tools = {c.tool for c in CATALOG.values() if c.tool}

    assert catalog_tools <= set(SPECS)
    # the two checks are tools of no command of their own
    assert set(SPECS) - catalog_tools == {"check_updates", "project_check_updates"}
    assert [s.name for s in SPECS.values() if not s.commands] == ["check_updates"]
    for spec in SPECS.values():
        for command in spec.commands:
            assert command in CATALOG, spec.name
            if spec.name != "project_check_updates":
                assert CATALOG[command].tool == spec.name
    project_check = SPECS["project_check_updates"]
    assert project_check.commands == ("project download",)
    assert project_check.check and CATALOG["project download"].supports_check


def test_the_catalog_names_the_tool_that_checks_each_command():
    """``check_tool`` of a command is a tool that exists and checks that command: a
    data command by ``check_updates`` (it is in its ``tool`` enum), ``project
    download`` by ``project_check_updates``."""
    enum = SPECS["check_updates"].input_schema["properties"]["tool"]["enum"]
    checked = {c.id: c for c in CATALOG.values() if c.supports_check}

    assert {c.id for c in checked.values() if c.check_tool == "check_updates"} == {
        c.id for c in data_commands() if c.supports_check
    }
    assert [c.tool for c in checked.values() if c.check_tool == "check_updates"] == enum
    assert checked["project download"].check_tool == "project_check_updates"
    assert SPECS["project_check_updates"].commands == ("project download",)
    assert all(c.check_tool in SPECS for c in checked.values())
    # a command without a check has no tool for it
    assert [c.id for c in CATALOG.values() if c.check_tool is None] == [
        c.id for c in CATALOG.values() if not c.supports_check
    ]


def test_check_updates_enum_is_the_twelve_data_tools():
    enum = SPECS["check_updates"].input_schema["properties"]["tool"]["enum"]
    checkable = [c.tool for c in data_commands() if c.supports_check]

    assert len(enum) == 12
    assert enum == checkable  # the order of COMMANDS
    assert enum == [s.name for s in DATA_TOOLS]


def test_check_arguments_schema_drops_the_run_arguments():
    for spec in DATA_TOOLS:
        schema = check_arguments_schema(spec.name)
        data_properties = spec.input_schema["properties"]

        assert set(schema["properties"]) == set(data_properties) - RUN_ARGUMENTS
        assert schema["additionalProperties"] is False
        assert "output_dir" in schema["required"]
        assert set(schema["required"]) <= set(schema["properties"])
        if "bbox" in schema["properties"]:
            assert schema["dependentRequired"] == {"bbox": ["bbox_crs"]}
    # the summary of a run is not an argument of a check either
    assert "summary" in SPECS["soil_hsg"].input_schema["properties"]
    assert "summary" not in check_arguments_schema("soil_hsg")["properties"]


def test_check_arguments_schema_is_a_copy_and_knows_data_tools_only():
    check_arguments_schema("elevation_download")["properties"].clear()

    assert check_arguments_schema("elevation_download")["properties"]
    for name in ("get_catalog", "check_updates", "nope"):
        with pytest.raises(ValueError, match="nie jest narzedziem danych"):
            check_arguments_schema(name)


def test_input_schemas_are_valid_draft_2020_12():
    validator = pytest.importorskip("jsonschema").Draft202012Validator

    for spec in tool_specs():
        validator.check_schema(spec.input_schema)
    for spec in DATA_TOOLS:
        validator.check_schema(check_arguments_schema(spec.name))


@pytest.mark.parametrize("spec", SINGLE, ids=lambda s: s.name)
def test_schemas_follow_catalog_params(spec):
    command = CATALOG[spec.commands[0]]
    exposed = [p for p in command.params if p.argument]
    schema = spec.input_schema
    properties = schema["properties"]

    assert list(properties) == [p.argument for p in exposed]
    assert schema.get("required", []) == [p.argument for p in exposed if p.required]
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    if spec.family == "data":
        assert "output_dir" in schema["required"]
        assert CLI_ONLY_FLAGS.isdisjoint(properties)
        assert list(spec.task_options) == [p.argument for p in exposed if p.task]
    for param in exposed:
        prop = properties[param.argument]
        if param.kind in ("str", "bbox_crs") and param.allowed is not None:
            if (spec.name, param.name) in NO_ENUM:
                assert "enum" not in prop, param.name
            else:
                assert prop["enum"] == list(param.allowed), param.name
        if param.kind == "bbox":
            assert prop["type"] == "array" and prop["items"] == {"type": "number"}
            assert prop["minItems"] == prop["maxItems"] == 4
            assert "bbox_crs" in properties
            assert schema["dependentRequired"] == {"bbox": ["bbox_crs"]}
        if param.kind == "path":
            assert prop["type"] == "string"
        if param.kind == "per_country":
            string, mapping = prop["anyOf"]
            assert string == {"type": "string"}
            assert set(mapping["properties"]) == {"pl", "cz"}
            assert mapping["additionalProperties"] is False
        if param.kind == "plan":
            assert prop["type"] == "object"
        if param.kind == "flag":
            assert prop["type"] == "boolean"
        if param.name == "workers":
            assert prop["type"] == "integer" and prop["minimum"] == 1
        if param.name == "update":
            assert prop["enum"] == ["upgrade", "force"]
    if "bbox" not in properties:
        assert "dependentRequired" not in schema


def test_every_argument_has_a_kind_and_the_function_is_in_the_library():
    for spec in tool_specs():
        assert set(spec.kinds) == set(spec.input_schema["properties"]), spec.name
        assert set(spec.task_options) <= set(spec.kinds)
        if spec.name == "check_updates":
            assert spec.function is None
        else:
            assert spec.function in kartograf.__all__, spec.name


def test_shared_tools_require_group():
    for name in ("list_sources", "list_layers"):
        spec = SPECS[name]
        commands = [c for c in CATALOG.values() if c.tool == name]
        schema = spec.input_schema

        assert spec.commands == tuple(c.id for c in commands)
        assert schema["required"] == ["group"]
        assert schema["properties"]["group"]["enum"] == [c.group for c in commands]
        assert set(schema["properties"]) == {"group", "product"}
        # the values of ``product`` depend on the group: the library names them
        assert "enum" not in schema["properties"]["product"]
    assert len(SPECS["list_sources"].commands) == 11
    assert SPECS["list_layers"].input_schema["properties"]["group"]["enum"] == [
        "landcover",
        "soil",
    ]


def test_project_add_has_command_and_options():
    schema = SPECS["project_add"].input_schema
    properties = schema["properties"]

    assert properties["command"]["enum"] == [c.id for c in data_commands()]
    assert properties["options"]["type"] == "object"
    assert {"project_dir", "name", "command", "options"} <= set(schema["required"])
    assert "arguments" not in properties  # the words of a CLI line


def test_project_tools_select_tasks_and_the_check_takes_no_run_argument():
    download = SPECS["project_download"].input_schema["properties"]
    check = SPECS["project_check_updates"].input_schema

    assert {"update", "workers", "tasks"} <= set(download)
    assert set(check["properties"]) == {"project_dir", "tasks"}
    assert check["required"] == ["project_dir"]


@pytest.mark.parametrize("spec", SINGLE, ids=lambda s: s.name)
def test_annotations_follow_kind_and_effects(spec):
    command = CATALOG[spec.commands[0]]
    hints = spec.annotations

    assert hints.read_only_hint == (command.kind == "query")
    assert hints.open_world_hint == ("network" in command.effects)
    if hints.read_only_hint:
        assert hints.destructive_hint is None and hints.idempotent_hint is None
    else:
        # a protocol default of "destructive" is wrong for a store that never
        # overwrites: the write tools say so
        assert hints.destructive_hint is command.destructive
        assert hints.idempotent_hint is command.idempotent


def test_annotations_of_the_data_tools_and_the_checks():
    for spec in DATA_TOOLS:
        assert (spec.annotations.read_only_hint, spec.annotations.destructive_hint) == (
            False,
            False,
        )
        assert spec.annotations.idempotent_hint is True
        assert spec.annotations.open_world_hint is True
    assert SPECS["project_remove"].annotations.destructive_hint is True
    for name in ("check_updates", "project_check_updates"):
        hints = SPECS[name].annotations
        assert (hints.read_only_hint, hints.open_world_hint) == (True, True)
    assert SPECS["elevation_availability"].annotations.open_world_hint is True
    assert SPECS["parse_sheet"].annotations.open_world_hint is False


def test_descriptions_are_ascii_and_start_with_the_summary():
    for spec in tool_specs():
        assert spec.description.isascii(), spec.name
        assert all(text.isascii() for text in _descriptions(spec.input_schema))
        assert not hasattr(spec, "title")  # the first sentence is the summary
        # ``ok: false`` is explained once, in the instructions of the server
        assert "ok=false" not in spec.description, spec.name
        assert "--" not in spec.description, spec.name  # a call has no flags
    for spec in SINGLE:
        if spec.name == "get_catalog":
            continue
        summary = CATALOG[spec.commands[0]].summary
        assert spec.description.startswith(summary.rstrip(".")), spec.name
        if spec.family != "data":
            # the document a tool returns; the twelve data tools all return one
            assert f"Wynik: {_result_schema(spec)}" in spec.description, spec.name


def test_data_tools_send_to_the_catalog_for_their_parameters():
    for spec in DATA_TOOLS:
        command = spec.commands[0]

        assert f'get_catalog(command="{command}")' in spec.description, spec.name
        assert "Wynik:" not in spec.description
    assert "get_catalog(command=<command>)" in SPECS["project_add"].description
    catalog = SPECS["get_catalog"].description
    for word in ("command=", "group=", "tables=", "przeglad"):
        assert word in catalog


def test_get_catalog_has_four_arguments_and_lists_no_commands():
    schema = SPECS["get_catalog"].input_schema
    properties = schema["properties"]

    assert list(properties) == ["group", "command", "params", "tables"]
    assert properties["group"]["enum"] == [g.name for g in get_catalog().groups]
    assert properties["tables"]["type"] == "boolean"
    assert "required" not in schema
    # the 41 ids are the overview's: a second copy in every tools/list is waste
    assert "enum" not in properties["command"]


def _says(text: str, value: str) -> bool:
    """The text has the value as a word (``1:1000`` is not in ``1:10000``)."""
    return re.search(rf"(?<![\w.:]){re.escape(value)}(?![\w.:])", text) is not None


def test_no_description_names_a_flag_or_lists_the_allowed_values():
    """A tool call has no flags (``--bbox``), and the allowed values are the
    ``enum``: a description that repeats them is the catalog's text."""
    for spec in tool_specs():
        for name, prop in spec.input_schema["properties"].items():
            text = prop.get("description", "")
            values = prop.get("enum") or prop.get("items", {}).get("enum") or []

            assert "--" not in text, (spec.name, name)
            assert sum(_says(text, str(value)) for value in values) <= 1, (
                spec.name,
                name,
            )
            assert len(text) <= 80, (spec.name, name, text)
    properties = SPECS["elevation_download"].input_schema["properties"]
    assert "description" not in properties["plan"]


def test_every_argument_has_wording_and_no_wording_is_stale():
    """A new argument of the catalog needs words for a tool call (or an explicit
    ``None``), and an argument that is gone takes its words with it."""
    used = {(spec.name, name) for spec in tool_specs() for name in spec.kinds}
    names = {name for _, name in used}

    assert [name for name in WORDS if name not in names] == []
    assert [pair for pair in WORDS_FOR if pair not in used] == []
    # the wording of one tool is only for an argument that means something else
    for pair, text in WORDS_FOR.items():
        assert text != WORDS.get(pair[1]), pair


def test_a_path_is_a_string_and_the_instructions_say_it_is_absolute():
    from kartograf.mcp_server import INSTRUCTIONS

    paths = {
        (spec.name, name)
        for spec in tool_specs()
        for name, kind in spec.kinds.items()
        if kind == "path"
    }

    assert paths
    for tool, name in paths:
        assert SPECS[tool].input_schema["properties"][name]["type"] == "string"
        assert name in INSTRUCTIONS, (tool, name)
    assert "bezwzgledn" in INSTRUCTIONS


def test_tools_list_is_small():
    """What a client puts in the context at the start: the budget of the agent
    interface is 30 000 characters for the 29 tools (it was 65 883)."""

    def camel(name: str) -> str:
        first, *rest = name.split("_")
        return first + "".join(word.capitalize() for word in rest)

    wire = [
        {
            "name": spec.name,
            "description": spec.description,
            "inputSchema": spec.input_schema,
            "annotations": {
                camel(key): value
                for key, value in dataclasses.asdict(spec.annotations).items()
                if value is not None
            },
        }
        for spec in tool_specs()
    ]

    size = len(json.dumps(wire, ensure_ascii=False, separators=(",", ":")))

    assert size <= 30_000, size


def test_family_filter():
    selected = tool_specs(("discovery", "data"))
    everything = tool_specs()

    assert len(selected) == 17
    assert {s.family for s in selected} == {"discovery", "data"}
    # the order of the families, not of the request
    assert [s.name for s in tool_specs(("data", "discovery"))] == [
        s.name for s in selected
    ]
    assert tool_specs(None) == everything
    assert len(tool_specs(("discovery", "availability", "data", "check"))) == 19
    with pytest.raises(ValueError, match="nieznana rodzina narzedzi: nope, x"):
        tool_specs(("discovery", "nope", "x"))


def test_tools_module_needs_neither_mcp_nor_jsonschema():
    code = (
        "import sys\n"
        "sys.modules['mcp'] = None\n"
        "import kartograf.catalog.tools as tools\n"
        "assert len(tools.tool_specs()) == 29\n"
        "assert 'jsonschema' not in sys.modules\n"
    )

    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True
    )

    assert done.returncode == 0, done.stderr
