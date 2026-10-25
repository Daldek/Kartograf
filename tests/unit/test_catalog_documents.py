"""The catalog documents ``kartograf-command-list/1`` and ``kartograf-commands/1``
(AGI-2.4, spec 8.1, 8.5), built from synthetic declarations; the parts on the real
declarations are in ``tests/contract/test_commands_schema.py``."""

import dataclasses
import json

import pytest

from kartograf.catalog import build
from kartograf.catalog.build import (
    build_entries,
    build_list,
    command_schema,
    declared_options,
    effects,
    is_option,
    list_commands,
)
from kartograf.catalog.commands import Declared
from kartograf.catalog.model import CommandCatalog, CommandList, OptionEntry
from kartograf.catalog.spec import (
    Command,
    Constraint,
    Example,
    Group,
    Param,
)
from kartograf.exceptions import ValidationError
from kartograf.serialization import SCHEMAS

_PRODUCTS = ("nmt", "nmpt")


def _params() -> tuple[Param, ...]:
    return (
        Param(
            "product",
            "str",
            lambda: "Product (required).",
            allowed=lambda: _PRODUCTS,
            choices=True,
            required=True,
            task=True,
            description_pl=lambda: "Produkt (wymagany)",
        ),
        Param(
            "sheet",
            "str",
            "Sheet code.",
            metavar="GODLO",
            normalize="strip",
            task=True,
            accepts=("pl1992", "pl2000"),
            description_pl="Godlo arkusza",
            examples=("N-34-130-D-d-2-4",),
        ),
        Param(
            "bbox",
            "bbox",
            "Area rectangle.",
            task=True,
            metavar="BBOX",
            description_pl="Prostokat obszaru",
        ),
        Param(
            "bbox_crs",
            "bbox_crs",
            "CRS of the rectangle.",
            task=True,
            allowed=("EPSG:2180", "EPSG:4326"),
            cli_default="EPSG:2180",
            description_pl="Uklad --bbox",
        ),
        Param(
            "resolution",
            "per_country",
            "Grid resolution.",
            task=True,
            allowed=("1m", "5m"),
            description_pl="Rozdzielczosc",
        ),
        Param(
            "format",
            "str_list",
            "File formats.",
            task=True,
            allowed=("ASC", "XYZ"),
            description_pl="Lata",
        ),
        Param(
            "limit",
            "int",
            "Most entries.",
            default=10,
            minimum=1,
            maximum=100,
            unit="entries",
            description_pl="Limit",
        ),
        Param(
            "all_campaigns",
            "flag",
            "Every flight.",
            default=False,
            description_pl="Wszystkie loty",
        ),
        Param(
            "root",
            "path",
            "Store directory.",
            flag="--root",
            short="-o",
            dest="output",
            required=True,
            description_pl="Katalog magazynu",
            path_role="root",
        ),
        Param(
            "check_updates",
            "flag",
            "Plan without effects.",
            argument=None,
            description_pl="Plan bez skutkow",
        ),
        Param(
            "group",
            "str",
            "The group of the sources.",
            flag=None,
            fixed="elevation",
            description_pl="Grupa",
        ),
        Param(
            "quiet",
            "flag",
            "No progress bar.",
            argument=None,
            short="-q",
            description_pl="Bez paska postepu",
        ),
    )


def _commands() -> tuple[Command, ...]:
    return (
        Command(
            "elevation download",
            "Download NMT and NMPT",
            "data",
            "download_data",
            "kartograf-download/1",
            _params(),
            description="Download the data into a versioned store.",
            effects=("network", "store_write"),
            project_task=True,
            check_function="check_data",
            check_result_schema="kartograf-plan/1",
            constraints=(
                Constraint(
                    "one_of",
                    ("sheet", "bbox"),
                    "Podaj dokladnie jeden obszar: --sheet albo --bbox",
                ),
                Constraint("requires", ("bbox_crs",), "bbox_crs z bbox", "bbox"),
            ),
            examples=(
                Example({"product": "nmt", "sheet": "N-34-130-D-d-2-4"}, title="Sheet"),
                Example(
                    {"product": "nmpt", "bbox": [1, 2, 3, 4], "bbox_crs": "EPSG:2180"},
                    title="Area",
                    result={"schema": "kartograf-download/1", "ok": True},
                ),
            ),
            summary_pl="Pobierz NMT i NMPT",
            description_pl="Pobierz dane do magazynu wersji",
            rules=("Check first.",),
            rules_pl=("Najpierw sprawdz.",),
            errors=("validation_error", "io_error"),
            family="data",
            core=True,
        ),
        Command(
            "elevation list-sources",
            "List the sources",
            "query",
            "list_sources",
            "kartograf-sources/1",
            (_params()[10],),
            summary_pl="Wypisz zrodla",
            description="The registered sources.",
            description_pl="Zrodla z rejestru",
            examples=(Example({}, title="The sources"),),
            family="discovery",
            cardinality="bounded",
        ),
        Command(
            "cache clear",
            "Delete every cache entry",
            "manage",
            "clear_cache",
            "kartograf-cache/1",
            (),
            description="Delete the cache.",
            effects=("cache_delete",),
            destructive=True,
            summary_pl="Usun cache",
            description_pl="Usun wpisy cache",
            examples=(Example({}, title="Clear"),),
        ),
        Command(
            "sheet parse",
            "Recognise a sheet code",
            "query",
            "describe_sheet",
            "kartograf-sheet/1",
            (
                Param(
                    "sheet",
                    "str",
                    "Sheet code.",
                    positional=True,
                    required=True,
                    description_pl="Godlo",
                ),
            ),
            description="Offline.",
            summary_pl="Rozpoznaj godlo",
            description_pl="Bez sieci",
            examples=(Example({"sheet": "N-34-130-D"}, title="A sheet"),),
            family="discovery",
        ),
    )


def _groups() -> tuple[Group, ...]:
    return (
        Group(
            "elevation",
            "Elevation",
            "NMT and NMPT",
            products=lambda: [("nmt", "Terrain model"), ("nmpt", "Surface model")],
            summary_pl="Wysokosci",
            description_pl="Dane wysokosciowe",
        ),
        Group(
            "sheet",
            "Sheet codes",
            "Sheet codes",
            summary_pl="Godla",
            description_pl="Godla arkuszy",
        ),
        Group(
            "cache",
            "Cache",
            "The metadata cache",
            position=2,
            summary_pl="Cache",
            description_pl="Cache metadanych",
        ),
    )


@pytest.fixture
def synthetic(monkeypatch):
    """``list_commands`` and ``command_schema`` over the synthetic declarations, with
    the caches cleared before and after (the process builds the documents once)."""
    monkeypatch.setattr(build, "declared", lambda: Declared(_commands(), _groups()))
    build.clear_caches()
    yield
    build.clear_caches()


def _entry(name: str):
    return next(e for e in build_entries(_commands(), _groups()) if e.name == name)


def test_the_list_has_every_group_and_command_in_catalog_order(synthetic):
    document = list_commands()

    assert isinstance(document, CommandList)
    assert document.schema == "kartograf-command-list/1"
    assert SCHEMAS["kartograf-command-list/1"] == (CommandList,)
    assert (document.tool, document.version) == ("kartograf", build._version())
    # the groups of ``kartograf --help``: the position first, then the name
    assert [g.name for g in document.groups] == ["elevation", "sheet", "cache"]
    assert [c.name for c in document.commands] == [
        "elevation download",
        "elevation list-sources",
        "cache clear",
        "sheet parse",
    ]
    assert list(document.to_dict()) == [
        "schema",
        "tool",
        "version",
        "groups",
        "commands",
    ]


def test_a_row_of_the_list_is_short_and_says_what_the_command_does_to_the_world(
    synthetic,
):
    rows = {c.name: c for c in list_commands().commands}
    download = rows["elevation download"]

    assert dataclasses.asdict(download) == {
        "name": "elevation download",
        "operation_id": "kartograf_elevation_download",
        "summary": "Download NMT and NMPT",
        "families": ("data", "core"),
        "read_only": False,
        "check": "elevation download",  # the plan is the command with check_updates
    }
    assert (rows["cache clear"].read_only, rows["cache clear"].families) == (False, ())
    assert (rows["sheet parse"].read_only, rows["sheet parse"].check) == (True, None)
    assert rows["sheet parse"].operation_id == "kartograf_sheet_parse"
    assert rows["elevation list-sources"].operation_id == (
        "kartograf_elevation_list_sources"
    )


def test_the_groups_of_the_list_name_their_products_from_the_provider(synthetic):
    groups = {g.name: g for g in list_commands().groups}

    assert groups["elevation"].products == ("nmt", "nmpt")
    assert groups["elevation"].summary == "Elevation"
    assert groups["sheet"].products == ()
    assert list(groups["cache"].__dict__) == ["name", "summary", "products"]


def test_the_list_is_built_once_and_a_schema_reuses_its_entries(synthetic, monkeypatch):
    built = []
    original = build.command_entry

    def counting(command, summaries):
        built.append(command.id)
        return original(command, summaries)

    monkeypatch.setattr(build, "command_entry", counting)

    first = list_commands()
    second = list_commands()
    one = command_schema("sheet parse")
    other = command_schema("kartograf_sheet_parse")

    assert first is second
    assert one.commands[0] is other.commands[0]
    assert len(built) == 4  # every command once


def test_command_schema_takes_the_name_or_the_operation_id(synthetic):
    by_name = command_schema("elevation download")
    by_operation = command_schema("kartograf_elevation_download")

    assert isinstance(by_name, CommandCatalog)
    assert by_name.schema == "kartograf-commands/1"
    assert SCHEMAS["kartograf-commands/1"] == (CommandCatalog,)
    assert by_name == by_operation
    assert [c.name for c in by_name.commands] == ["elevation download"]
    assert (by_name.tool, by_name.version) == ("kartograf", build._version())
    assert list(by_name.to_dict()) == ["schema", "tool", "version", "commands"]


@pytest.mark.parametrize(
    "given", ["elevation nope", "elevation", "", "KARTOGRAF_X", None]
)
def test_command_schema_of_an_unknown_command_names_the_known_ones(synthetic, given):
    with pytest.raises(ValidationError) as caught:
        command_schema(given)

    error = caught.value
    assert error.option == "command"
    assert error.allowed == (
        "elevation download",
        "elevation list-sources",
        "cache clear",
        "sheet parse",
    )
    assert "kartograf commands list" in (error.hint or "")
    assert ("nie podano" if given is None else repr(given)) in str(error)


def test_an_option_has_an_argument_of_the_function_or_is_the_plan_option(synthetic):
    command = _commands()[0]
    params = {p.name: p for p in command.params}

    assert {name for name, p in params.items() if is_option(command, p)} == {
        "product",
        "sheet",
        "bbox",
        "bbox_crs",
        "resolution",
        "format",
        "limit",
        "all_campaigns",
        "root",
        "check_updates",  # no function takes it, the command has a check
    }
    assert [p.name for p in declared_options(command)][-1] == "check_updates"
    # without a check the plan option is no option; a fixed argument never is
    sources = _commands()[1]
    assert not any(is_option(sources, p) for p in sources.params)
    without_check = dataclasses.replace(
        command, check_function=None, check_result_schema=None
    )
    assert "check_updates" not in {p.name for p in declared_options(without_check)}


def test_the_options_of_a_command_are_typed_and_bounded(synthetic):
    options = {o.name: o for o in _entry("elevation download").options}

    assert [o.name for o in _entry("elevation download").options] == [
        "product",
        "sheet",
        "bbox",
        "bbox_crs",
        "resolution",
        "format",
        "limit",
        "all_campaigns",
        "root",
        "check_updates",
    ]
    assert (options["product"].type, options["product"].required) == ("string", True)
    assert options["bbox"].type == "array" and options["bbox"].items == "number"
    assert options["bbox"].unit == "m, or degrees for EPSG:4326"
    assert options["bbox_crs"].type == "string"
    assert options["resolution"].type == "string"  # or {"pl": ..., "cz": ...}
    assert (options["format"].type, options["format"].items) == ("array", "string")
    assert (options["limit"].type, options["limit"].unit) == ("integer", "entries")
    assert (options["limit"].minimum, options["limit"].maximum) == (1, 100)
    assert (options["limit"].default, options["all_campaigns"].default) == (10, False)
    assert options["all_campaigns"].type == "boolean"
    assert options["sheet"].examples == ("N-34-130-D-d-2-4",)
    assert options["root"].path_role == "root"
    assert options["product"].path_role is None
    assert options["check_updates"].type == "boolean"
    assert options["check_updates"].description == "Plan without effects."


def test_the_choice_of_the_area_is_the_one_of_group(synthetic):
    options = {o.name: o for o in _entry("elevation download").options}

    assert {name for name, o in options.items() if o.one_of} == {"sheet", "bbox"}
    assert options["sheet"].one_of == options["bbox"].one_of == "area"
    assert (
        options["sheet"].description
        == "Sheet code. Give exactly one of `sheet`, `bbox`."
    )
    assert options["bbox"].description.endswith(" Give exactly one of `sheet`, `bbox`.")
    assert options["bbox_crs"].description == "CRS of the rectangle."  # not a member


def test_two_choices_of_an_area_in_one_command_are_refused():
    command = dataclasses.replace(
        _commands()[0],
        constraints=(
            Constraint("one_of", ("sheet", "bbox"), "x"),
            Constraint("one_of", ("product", "bbox"), "y"),
        ),
    )

    with pytest.raises(ValueError, match="one_of"):
        build_entries((command,), _groups()[:1])


def test_the_allowed_values_come_from_the_provider_with_their_meanings(synthetic):
    options = {o.name: o for o in _entry("elevation download").options}

    assert [(v.value, v.meaning) for v in options["product"].enum or ()] == [
        ("nmt", "Digital terrain model (bare earth); PL and CZ."),
        (
            "nmpt",
            "Digital surface model (with the objects on the ground); PL and CZ.",
        ),
    ]
    assert [v.value for v in options["bbox_crs"].enum or ()] == [
        "EPSG:2180",
        "EPSG:4326",
    ]
    assert [v.value for v in options["resolution"].enum or ()] == ["1m", "5m"]
    assert options["sheet"].enum is None and options["limit"].enum is None


def test_a_value_without_a_meaning_is_not_published():
    command = dataclasses.replace(
        _commands()[0],
        params=(
            dataclasses.replace(_commands()[0].params[0], allowed=("nmt", "no-such")),
        ),
        constraints=(),
        examples=(Example({"product": "nmt"}, title="x"),),
    )

    with pytest.raises(KeyError, match="no-such"):
        build_entries((command,), _groups()[:1])


def test_the_commands_the_schema_names_say_themselves(synthetic):
    schema = dataclasses.replace(
        _commands()[3],
        id="commands schema",
        function="command_schema",
        params=(
            Param(
                "command",
                "str",
                "The command.",
                allowed=lambda: [c.id for c in _commands()],
                required=True,
                description_pl="Komenda",
            ),
        ),
        examples=(Example({"command": "sheet parse"}, title="A command"),),
    )
    groups = (*_groups(), Group("commands", "Commands", "The catalog"))
    entries = build_entries((*_commands(), schema), groups)

    (command,) = entries[-1].options
    assert [(v.value, v.meaning) for v in command.enum or ()][:2] == [
        ("elevation download", "Download NMT and NMPT"),
        ("elevation list-sources", "List the sources"),
    ]


def test_effects_say_what_a_command_changes(synthetic):
    entries = {e.name: e.effects for e in build_entries(_commands(), _groups())}

    assert dataclasses.asdict(entries["elevation download"]) == {
        "read_only": False,
        "writes": "add",
        "idempotent": True,
        "network": True,
        "destructive": False,
    }
    assert dataclasses.asdict(entries["elevation list-sources"]) == {
        "read_only": True,
        "writes": "none",
        "idempotent": True,
        "network": False,
        "destructive": False,
    }
    assert (entries["cache clear"].writes, entries["cache clear"].destructive) == (
        "delete",
        True,
    )


@pytest.mark.parametrize(
    ("declared_effects", "read_only"),
    [
        ((), True),
        (("network",), True),
        (("store_write",), False),
        (("project_write",), False),
        (("cache_write",), False),
        (("cache_delete",), False),
    ],
)
def test_a_command_is_read_only_unless_it_writes_somewhere(declared_effects, read_only):
    command = dataclasses.replace(
        _commands()[1], effects=declared_effects, destructive=False
    )

    assert effects(command).read_only is read_only
    assert (effects(command).writes == "none") is read_only


def test_a_read_only_command_is_never_destructive():
    command = dataclasses.replace(_commands()[1], effects=(), destructive=True)

    assert effects(command).destructive is False


def test_the_examples_have_the_call_a_result_excerpt_and_the_title(synthetic):
    first, second = _entry("elevation download").examples

    assert first.call == (
        "kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 -o ./data"
    )
    assert first.title == "Sheet"
    assert first.result["schema"] == "kartograf-download/1"  # the excerpt of the schema
    assert second.call.endswith("--product nmpt --bbox 1,2,3,4 -o ./data")
    assert second.result == {"schema": "kartograf-download/1", "ok": True}


def test_the_texts_are_english_with_the_polish_ones_in_i18n(synthetic):
    entry = _entry("elevation download")

    assert (entry.summary, entry.description) == (
        "Download NMT and NMPT",
        "Download the data into a versioned store.",
    )
    assert entry.rules == ("Check first.",)
    assert dataclasses.asdict(entry.i18n) == {
        "pl": {
            "summary": "Pobierz NMT i NMPT",
            "description": "Pobierz dane do magazynu wersji",
            "rules": ("Najpierw sprawdz.",),
        }
    }
    assert entry.errors == ("validation_error", "io_error")
    assert (entry.function, entry.result.schema) == (
        "download_data",
        "kartograf-download/1",
    )
    assert (entry.result.cardinality, entry.families) == ("single", ("data", "core"))
    assert _entry("elevation list-sources").result.cardinality == "bounded"


def test_a_provider_description_is_resolved_when_the_document_is_built(synthetic):
    options = {o.name: o for o in _entry("elevation download").options}

    assert options["product"].description == "Product (required)."


def test_option_json_leaves_out_the_keys_without_a_value():
    bare = OptionEntry("limit", "integer", False, "Most entries.")
    sparse = OptionEntry("limit", "integer", True, "Most.", minimum=1, default=0)

    assert bare.__json__(None) == {  # type: ignore[arg-type]
        "name": "limit",
        "type": "integer",
        "required": False,
        "description": "Most entries.",
    }
    # a default that is false or zero is a value; the keys keep their order
    assert list(sparse.__json__(None)) == [  # type: ignore[arg-type]
        "name",
        "type",
        "required",
        "default",
        "min",
        "description",
    ]


def test_documents_are_immutable_data(synthetic):
    document = command_schema("elevation download")
    (entry,) = document.commands

    with pytest.raises(dataclasses.FrozenInstanceError):
        document.tool = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.options[0].name = "other"  # type: ignore[misc]
    assert isinstance(document.commands, tuple) and isinstance(entry.options, tuple)
    assert json.loads(document.to_json()) == json.loads(document.to_json(indent=None))


@pytest.mark.parametrize(
    "fields",
    [
        {"constraints": (Constraint("requires", ("nope",), "x", "sheet"),)},
        {"constraints": (Constraint("applies_to", (), "x", "sheet", {"nope": True}),)},
        {"examples": (Example({"nope": 1}),)},
        {"examples": (Example({}, run={"nope": True}),)},
    ],
    ids=["param", "when", "example", "run"],
)
def test_constraints_and_examples_must_reference_declared_params(fields):
    command = dataclasses.replace(_commands()[0], **fields)

    with pytest.raises(ValueError, match="nope"):
        build_entries((command,), _groups()[:1])


def test_declarations_of_a_group_without_commands_are_refused():
    with pytest.raises(ValueError, match="cache"):
        build_list(_commands()[:1], (_groups()[0], _groups()[2]), "0")


def test_the_list_of_other_declarations_has_their_version():
    document = build_list(_commands(), _groups(), "9.9")

    assert document.version == "9.9"
