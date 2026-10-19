"""The catalog document ``kartograf-catalog/1`` and ``get_catalog`` (spec 8.1, 8.5),
built from synthetic declarations; the parts on the real declarations (the hint
example, the completeness of the declarations) come last."""

import argparse
import dataclasses
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from kartograf.catalog import build
from kartograf.catalog.build import build_catalog, data_commands, get_catalog
from kartograf.catalog.cliparser import _subparsers, build_parser, parse_command_line
from kartograf.catalog.commands import Declared, declared
from kartograf.catalog.hints import example_for
from kartograf.catalog.kinds import check_options_json, options_from_json
from kartograf.catalog.model import Catalog, CommandInfo, ParamInfo
from kartograf.catalog.spec import (
    Command,
    Constraint,
    Example,
    Group,
    Param,
    resolve,
)
from kartograf.cli._parser import create_parser
from kartograf.error_report import ERROR_CODES, EXIT_CODES
from kartograf.exceptions import ValidationError
from kartograf.project.commands import COMMANDS
from kartograf.serialization import SCHEMAS
from kartograf.sources.registry import sources_for

_PRODUCTS = ("nmt", "nmpt")


def _params() -> tuple[Param, ...]:
    return (
        Param(
            "product",
            "str",
            lambda: "Produkt (wymagany): nmt, nmpt",
            allowed=lambda: _PRODUCTS,
            choices=True,
            required=True,
            task=True,
            section="Produkt i obszar",
        ),
        Param(
            "sheet",
            "str",
            "Godlo arkusza",
            metavar="GODLO",
            normalize="strip",
            task=True,
            accepts=("pl1992", "pl2000"),
            section="Produkt i obszar",
        ),
        Param("bbox", "bbox", "Prostokat obszaru", task=True, metavar="BBOX"),
        Param(
            "bbox_crs",
            "bbox_crs",
            "Uklad --bbox",
            task=True,
            allowed=("EPSG:2180", "EPSG:4326"),
            cli_default="EPSG:2180",
        ),
        Param(
            "output_dir",
            "path",
            "Katalog magazynu",
            flag="--output",
            short="-o",
            dest="output",
            required=True,
        ),
        Param("quiet", "flag", "Bez paska postepu", argument=None, short="-q"),
    )


def _commands() -> tuple[Command, ...]:
    return (
        Command(
            "elevation download",
            "Pobierz NMT i NMPT",
            "data",
            "download_data",
            "kartograf-download/1",
            _params(),
            description="Pobierz dane do magazynu wersji",
            effects=("network", "store_write"),
            project_task=True,
            check_function="check_data",
            check_result_schema="kartograf-plan/1",
            tool="elevation_download",
            constraints=(
                Constraint(
                    "one_of",
                    ("sheet", "bbox"),
                    "Podaj dokladnie jeden obszar: --sheet albo --bbox",
                ),
            ),
            examples=(
                Example({"product": "nmt", "sheet": "N-34-130-D-d-2-4"}),
                Example(
                    {"product": "nmpt", "bbox": [1, 2, 3, 4], "bbox_crs": "EPSG:2180"},
                    title="Obszar",
                ),
            ),
        ),
        Command(
            "elevation list-sources",
            "Wypisz zrodla",
            "query",
            "list_sources",
            "kartograf-sources/1",
            (Param("group", "str", flag=None, required=True, allowed=("elevation",)),),
            tool="list_sources",
        ),
        Command(
            "cache stats",
            "Statystyki cache",
            "query",
            "get_cache_info",
            "kartograf-cache/1",
            (),
        ),
        Command(
            "parse",
            "Rozpoznaj godlo",
            "query",
            "describe_sheet",
            "kartograf-sheet/1",
            (Param("sheet", "str", "Godlo", positional=True, required=True),),
            tool="parse_sheet",
        ),
        Command(
            "find_sheets",
            "Godla obszaru",
            "query",
            "find_sheets",
            "kartograf-sheets/1",
            (Param("scale", "str", "Skala", flag=None, required=True),),
            cli=None,
            tool="find_sheets",
        ),
    )


def _groups() -> tuple[Group, ...]:
    return (
        Group(
            "elevation",
            "Wysokosci",
            "Dane wysokosciowe NMT i NMPT",
            products=lambda: [
                ("nmt", "Numeryczny Model Terenu; PL i CZ"),
                ("nmpt", "Numeryczny Model Pokrycia Terenu; PL i CZ"),
            ],
        ),
        Group("cache", "Cache metadanych", "Lokalny cache metadanych", position=2),
    )


def _build(**view) -> Catalog:
    return build_catalog(_commands(), _groups(), **view)


def _command(catalog: Catalog, command_id: str) -> CommandInfo:
    return next(c for c in catalog.commands if c.id == command_id)


@pytest.fixture
def declared_catalog(monkeypatch):
    """``get_catalog`` over the synthetic declarations, with its caches cleared
    before and after (the process caches the full catalog)."""
    monkeypatch.setattr(build, "declared", lambda: Declared(_commands(), _groups()))
    build.clear_caches()
    yield
    build.clear_caches()


def test_catalog_document_keys():
    keys = [
        "schema",
        "view",
        "kartograf_version",
        "language",
        "groups",
        "commands",
        "exit_codes",
        "errors",
        "schemas",
    ]

    # every view has the same keys: the overview shortens the records, not the document
    for catalog in (_build(), _build(group="elevation"), _build(command="parse")):
        assert list(catalog.to_dict()) == keys
    assert catalog.schema == "kartograf-catalog/1"
    assert catalog.language == "pl"
    assert SCHEMAS["kartograf-catalog/1"] == (Catalog,)


def test_view_is_the_overview_until_something_is_selected_or_asked_for():
    assert _build().view == "overview"
    assert _build(params=False).view == "overview"
    assert _build(tables=True).view == "overview"
    for view in (
        {"group": "elevation"},
        {"command": "parse"},
        {"params": True},
        {"group": "elevation", "params": False},
    ):
        assert _build(**view).view == "full", view


def test_a_catalog_of_an_unknown_view_is_rejected():
    full = _build()

    with pytest.raises(ValueError, match="unknown catalog view 'short'"):
        dataclasses.replace(full, view="short")


def test_version_is_the_package_version():
    import kartograf

    assert _build().kartograf_version == kartograf.__version__


def test_overview_objects_are_complete_and_without_params():
    """The objects of the overview have every field but the parameters: a caller
    of the library reads a description without asking again."""
    catalog = _build()

    assert [c.id for c in catalog.commands] == [
        "elevation download",
        "elevation list-sources",
        "cache stats",
        "parse",
        "find_sheets",
    ]
    assert all(
        c.params is None and c.constraints is None and c.examples is None
        for c in catalog.commands
    )
    assert all(c.description and c.kind for c in catalog.commands)
    assert catalog.groups[0].description
    assert catalog.groups[0].products[0].sources is not None


def test_overview_document_is_a_short_projection():
    catalog = _build()

    document = catalog.to_dict()

    assert document["view"] == "overview"
    assert [list(g) for g in document["groups"]] == [
        ["name", "summary", "products"]
    ] * 2
    assert document["groups"][0]["products"] == ["nmt", "nmpt"]
    assert document["groups"][1]["products"] == []
    assert [list(c) for c in document["commands"]] == [
        ["id", "summary", "tool", "supports_check"]
    ] * 5
    by_id = {c["id"]: c for c in document["commands"]}
    assert by_id["elevation download"]["supports_check"] is True
    assert by_id["cache stats"]["supports_check"] is False
    assert by_id["cache stats"]["tool"] is None
    assert by_id["parse"]["tool"] == "parse_sheet"
    # the tables are asked for
    assert (document["exit_codes"], document["errors"], document["schemas"]) == (
        None,
        None,
        None,
    )


def test_overview_text_is_one_record_per_line_and_the_same_document():
    catalog = _build()

    text = catalog.to_json()
    compact = catalog.to_json(indent=None)

    assert json.loads(text) == json.loads(compact) == catalog.to_dict()
    assert text.endswith("}\n") and "\n" not in compact
    lines = text.splitlines()
    for command in catalog.to_dict()["commands"]:
        record = json.dumps(command, ensure_ascii=False, separators=(",", ":"))
        assert f"    {record}," in lines or f"    {record}" in lines
    assert max(len(line) for line in lines) < 250
    assert lines[:3] == [
        "{",
        '  "schema": "kartograf-catalog/1",',
        '  "view": "overview",',
    ]


def test_overview_text_with_tables_has_a_record_per_line_for_them_too():
    catalog = _build(tables=True)

    text = catalog.to_json()

    assert json.loads(text) == catalog.to_dict()
    assert len(text.splitlines()) > len(_build().to_json().splitlines()) + len(
        catalog.exit_codes or ()
    )


def test_other_views_are_printed_like_any_document():
    catalog = _build(command="elevation download")

    assert (
        catalog.to_json()
        == json.dumps(catalog.to_dict(), ensure_ascii=False, indent=2) + "\n"
    )
    assert catalog.to_json(indent=None) == json.dumps(
        catalog.to_dict(), ensure_ascii=False, separators=(",", ":")
    )


def test_a_full_view_document_has_every_field_of_its_objects():
    document = _build(group="elevation").to_dict()

    assert document["view"] == "full"
    assert list(document["groups"][0]) == [
        "name",
        "summary",
        "description",
        "products",
        "commands",
    ]
    assert list(document["groups"][0]["products"][0]) == [
        "name",
        "summary",
        "countries",
        "sources",
    ]
    assert "description" in document["commands"][0]
    assert document["commands"][0]["params"] is None


def test_command_view_has_params_constraints_examples():
    catalog = _build(command="elevation download")

    (command,) = catalog.commands
    assert command.id == "elevation download"
    assert command.params is not None
    assert [p.name for p in command.params] == [
        "product",
        "sheet",
        "bbox",
        "bbox_crs",
        "output_dir",
        "quiet",
    ]
    assert command.constraints is not None
    assert (command.constraints[0].type, command.constraints[0].params) == (
        "one_of",
        ("sheet", "bbox"),
    )
    assert command.examples is not None
    assert [e.command_line for e in command.examples] == [
        "kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 -o ./data",
        "kartograf elevation download --product nmpt --bbox 1,2,3,4 -o ./data",
    ]
    assert command.examples[1].title == "Obszar"
    assert command.examples[1].options["bbox"] == (1, 2, 3, 4)
    document = catalog.to_dict()
    example = document["commands"][0]["examples"][1]
    assert list(example) == ["title", "options", "command_line"]
    assert example["options"]["bbox"] == [1, 2, 3, 4]


def test_param_document_keys_and_values():
    command = _command(_build(command="elevation download"), "elevation download")
    assert command.params is not None
    by_name = {p.name: p for p in command.params}

    document = dataclasses.asdict(by_name["product"])
    assert list(document) == [
        "name",
        "argument",
        "flag",
        "short",
        "positional",
        "kind",
        "required",
        "task",
        "allowed",
        "default",
        "cli_default",
        "accepts",
        "section",
        "description",
    ]
    assert by_name["output_dir"] == ParamInfo(
        name="output_dir",
        argument="output_dir",
        flag="--output",
        short="-o",
        positional=False,
        kind="path",
        required=True,
        task=False,
        allowed=None,
        default=None,
        cli_default=None,
        accepts=None,
        section=None,
        description="Katalog magazynu",
    )
    assert by_name["bbox_crs"].cli_default == "EPSG:2180"
    assert by_name["sheet"].accepts == ("pl1992", "pl2000")
    quiet = by_name["quiet"]
    assert (quiet.argument, quiet.flag, quiet.short) == (None, "--quiet", "-q")
    parse = _command(_build(command="parse"), "parse")
    assert parse.params is not None
    assert (parse.params[0].flag, parse.params[0].positional) == (None, True)


def test_group_filter_and_unknown_group():
    catalog = _build(group="elevation")

    assert [g.name for g in catalog.groups] == ["elevation"]
    assert [c.id for c in catalog.commands] == [
        "elevation download",
        "elevation list-sources",
    ]
    assert all(c.params is None for c in catalog.commands)
    with pytest.raises(ValidationError) as error:
        _build(group="nope")
    assert error.value.option == "group"
    assert error.value.allowed == ("elevation", "cache")
    assert "nope" in str(error.value)


def test_unknown_command_and_command_of_another_group():
    with pytest.raises(ValidationError) as unknown:
        _build(command="elevation nope")
    with pytest.raises(ValidationError) as other:
        _build(group="cache", command="elevation download")

    assert unknown.value.option == "command"
    assert unknown.value.allowed is not None
    assert "elevation download" in unknown.value.allowed
    assert "find_sheets" in unknown.value.allowed
    assert other.value.option == "command"


def test_params_flag_overrides_the_default():
    everything = _build(params=True)
    nothing = _build(command="elevation download", params=False)
    group = _build(group="cache", params=True)

    assert all(c.params is not None for c in everything.commands)
    assert all(
        c.params is None and c.constraints is None and c.examples is None
        for c in nothing.commands
    )
    assert [c.id for c in group.commands] == ["cache stats"]
    assert group.commands[0].params == ()


def test_command_without_a_group_and_api_only_command():
    parse = _command(_build(), "parse")
    api_only = _command(_build(), "find_sheets")

    assert (parse.group, parse.name, parse.cli) == (None, "parse", "parse")
    assert (api_only.group, api_only.cli, api_only.tool) == (
        None,
        None,
        "find_sheets",
    )
    assert [g.commands for g in _build().groups] == [
        ("elevation download", "elevation list-sources"),
        ("cache stats",),
    ]


def test_supports_check_is_derived():
    catalog = _build()
    download = _command(catalog, "elevation download")
    sources = _command(catalog, "elevation list-sources")

    assert download.supports_check is True
    assert (download.check_function, download.check_result_schema) == (
        "check_data",
        "kartograf-plan/1",
    )
    assert sources.supports_check is False
    assert (sources.check_function, sources.check_result_schema) == (None, None)
    for command in catalog.commands:
        assert command.supports_check == (command.check_function is not None)


def test_exit_codes_and_errors_are_the_library_tables():
    catalog = _build(tables=True)

    assert [(r.code, r.name, r.meaning) for r in catalog.exit_codes] == [
        (r.code, r.name, r.meaning) for r in EXIT_CODES
    ]
    assert [(r.code, r.exception, r.exit_code, r.meaning) for r in catalog.errors] == [
        (r.code, r.exception, r.exit_code, r.meaning) for r in ERROR_CODES
    ]


def test_tables_are_on_request_and_in_the_whole_catalog():
    nothing = (None, None, None)

    def tables(catalog: Catalog) -> tuple[object, object, object]:
        return catalog.exit_codes, catalog.errors, catalog.schemas

    assert tables(_build()) == tables(_build(group="elevation")) == nothing
    assert tables(_build(command="parse")) == tables(_build(params=False)) == nothing
    asked = _build(tables=True)
    # the overview with the tables: the tables do not make it a full view
    assert asked.view == "overview" and all(tables(asked))
    assert all(tables(_build(command="parse", tables=True)))
    # the whole catalog (every parameter of every command) has everything ...
    whole = _build(params=True)
    assert whole.view == "full" and all(tables(whole))
    # ... unless it is told not to; a group with parameters is not the whole catalog
    assert tables(_build(params=True, tables=False)) == nothing
    assert tables(_build(group="elevation", params=True)) == nothing


def test_schemas_list_follows_the_registry_and_names_the_producers(monkeypatch):
    registry = {
        "kartograf-sheet/1": (),
        "kartograf-download/1": (),
        "kartograf-test-undocumented/1": (),
        "kartograf-plan/1": (),
        "kartograf-error/1": (),
    }
    descriptions = {
        "kartograf-download/1": "Wynik komendy danych",
        "kartograf-plan/1": "Plan aktualizacji",
        "kartograf-sheet/1": "Opis godla",
        "kartograf-error/1": "Blad komendy",
    }
    monkeypatch.setattr(build, "SCHEMAS", registry)
    monkeypatch.setattr(build, "SCHEMA_DESCRIPTIONS", descriptions)

    catalog = _build(tables=True)

    # registry order; a schema without a description is not part of the catalog
    assert [(s.schema, s.description, s.produced_by) for s in catalog.schemas] == [
        ("kartograf-sheet/1", "Opis godla", ("parse",)),
        ("kartograf-download/1", "Wynik komendy danych", ("elevation download",)),
        # the check twin of a command produces its plan schema too
        ("kartograf-plan/1", "Plan aktualizacji", ("elevation download",)),
        ("kartograf-error/1", "Blad komendy", ()),
    ]


def test_every_library_schema_has_a_description():
    described = {s.schema for s in _build(tables=True).schemas}

    library = {s for s in SCHEMAS if not s.startswith("kartograf-test-")}
    assert library <= described
    assert "kartograf-catalog/1" in described


def test_full_catalog_is_built_once(declared_catalog, monkeypatch):
    built = []
    original = build._build_full

    def counting(commands, groups):
        built.append(1)
        return original(commands, groups)

    monkeypatch.setattr(build, "_build_full", counting)

    short = get_catalog()
    one = get_catalog(command="parse")
    group = get_catalog(group="elevation")
    everything = get_catalog(params=True)
    data = data_commands()

    assert built == [1]
    assert get_catalog() is short
    assert get_catalog(command="parse") is one
    assert one.commands[0].params is not None
    assert short.commands[0].params is None
    assert [c.id for c in group.commands] == [
        "elevation download",
        "elevation list-sources",
    ]
    assert all(c.params is not None for c in everything.commands)
    assert [c.id for c in data] == ["elevation download"]


def test_data_commands_have_params_and_are_project_tasks(declared_catalog):
    commands = data_commands()

    assert [c.id for c in commands] == ["elevation download"]
    assert all(c.project_task and c.params for c in commands)
    assert commands[0].examples is not None


def test_provider_values_reach_the_document():
    command = _command(_build(command="elevation download"), "elevation download")
    assert command.params is not None
    product = command.params[0]
    group = _build().groups[0]

    assert product.allowed == _PRODUCTS
    assert product.description == "Produkt (wymagany): nmt, nmpt"
    assert [p.name for p in group.products] == ["nmt", "nmpt"]
    assert group.products[0].summary == "Numeryczny Model Terenu; PL i CZ"


def test_products_get_countries_and_sources_from_the_registry():
    nmt = _build().groups[0].products[0]

    registered = sources_for(product="nmt")
    assert nmt.sources == tuple(source.key for source in registered)
    assert nmt.countries == ("pl", "cz")
    assert {"pl.gugik.nmt_1m", "cz.cuzk.dmr5g"} <= set(nmt.sources)


def test_catalog_is_immutable_data():
    catalog = _build(command="elevation download")
    example = catalog.commands[0].examples[0]  # type: ignore[index]

    with pytest.raises(dataclasses.FrozenInstanceError):
        catalog.language = "en"  # type: ignore[misc]
    with pytest.raises(TypeError):
        example.options["product"] = "nmpt"  # type: ignore[index]
    assert isinstance(catalog.commands, tuple)


def test_constraints_must_reference_declared_params():
    bad_param = dataclasses.replace(
        _commands()[0],
        constraints=(Constraint("requires", ("nope",), "x", "sheet"),),
    )
    bad_when = dataclasses.replace(
        _commands()[0],
        constraints=(Constraint("applies_to", (), "x", "sheet", {"nope": True}),),
    )
    bad_example = dataclasses.replace(_commands()[0], examples=(Example({"nope": 1}),))

    for command in (bad_param, bad_when, bad_example):
        with pytest.raises(ValueError, match="nope"):
            build_catalog((command,), _groups()[:1], command=command.id)


def test_declarations_of_a_group_without_commands_are_refused():
    with pytest.raises(ValueError, match="cache"):
        build_catalog(_commands()[:1], _groups())


# =============================================================================
# example_for: the example of an error hint (spec 6.3, part (b))
# =============================================================================

_DECLARED = declared()
_CLI_WITH_EXAMPLES = [
    (command, param)
    for command in _DECLARED.commands
    if command.cli is not None and command.examples
    for param in command.params
]


def _lines(command_id: str) -> list[str]:
    """The command lines of the examples of a command, as the catalog gives them."""
    (command,) = get_catalog(command=command_id).commands
    assert command.examples is not None
    return [example.command_line for example in command.examples]


def test_example_for_prefers_an_example_using_the_option():
    lines = _lines("elevation download")

    cutout = example_for("elevation download", "cutout")
    vertical = example_for("elevation download", "vertical_crs")
    crs = example_for("elevation download", "bbox_crs")

    assert vertical == ("--vertical-crs", lines[0])
    # the first example that uses the option, not the first example
    assert cutout[0] == "--cutout"
    assert cutout[1] in lines[1:] and "--cutout --horizontal-crs" in str(cutout[1])
    # an example that leaves the CRS out (the default of the flag) does not show it
    assert "--bbox " in lines[1] and "--bbox-crs" not in lines[1]
    assert crs[0] == "--bbox-crs"
    assert "--bbox-crs EPSG:5514" in str(crs[1])


def test_example_for_falls_back_to_the_first_example():
    lines = _lines("elevation download")

    unused = example_for("elevation download", "min_density")
    api_only = example_for("elevation download", "update")
    store = example_for("elevation download", "output_dir")

    assert all("--min-density" not in line for line in lines)
    assert unused == ("--min-density", lines[0])
    # an argument only the API has: no flag, but the example is still shown
    assert api_only == (None, lines[0])
    assert store == ("--output", lines[0]) and lines[0].endswith(" -o ./data")


def test_example_for_unknown_command_or_option():
    first = _lines("elevation download")[0]

    assert example_for("no such command", "product") == (None, None)
    assert example_for(None, "product") == (None, None)
    assert example_for(None, None) == (None, None)
    # an unknown argument of a known command: no flag, the first example
    assert example_for("elevation download", "nope") == (None, first)
    assert example_for("elevation download", None) == (None, first)


def test_example_for_is_an_example_of_the_product_of_the_call():
    # E2E 0.8.0 D P3-7: the first example of the command, whatever the product
    lines = _lines("models3d download")
    trees = example_for("models3d download", "bbox", {"product": "trees"})[1]
    mesh = example_for("models3d download", "bbox", {"product": "mesh"})[1]
    # the example of another product shows the argument but is not the product's
    year = example_for("landcover download", "year", {"product": "bdot10k"})[1]
    other = example_for("landcover download", "year", {"product": "bdoo"})[1]

    assert trees == next(line for line in lines if "--product trees" in line)
    assert mesh == next(line for line in lines if "--product mesh" in line)
    assert year is not None and "--product bdot10k" in year and "--year" not in year
    assert other is not None and "--product bdoo" in other and "--year" in other
    # a product none of the examples shows has no example: another one misleads
    assert example_for("elevation download", "resolution", {"product": "nmpt"}) == (
        "--resolution",
        None,
    )
    # a call without a product, or a command whose examples have none: as before
    assert example_for("models3d download", "bbox", {}) == (
        "--bbox",
        example_for("models3d download", "bbox")[1],
    )
    assert example_for("parse", "sheet", {"product": "x"}) == (
        None,
        "kartograf parse N-34-130-D-d-2-4",
    )


def test_example_for_takes_the_country_and_the_selection_of_the_call_next():
    # E2E 0.8.0 D P3-7: --country auto --level gmina got an example with --country pl
    auto = example_for(
        "boundaries download", "level", {"product": "admin", "country": "auto"}
    )[1]
    cz = example_for(
        "boundaries download", "level", {"product": "admin", "country": "cz"}
    )[1]
    by_unit = example_for(
        "boundaries download", "product", {"product": "admin", "teryt": "12"}
    )[1]

    assert auto is not None and "--country auto" in auto and "--level pl=" in auto
    assert cz is not None and "--country cz" in cz and "--level obec" in cz
    # the argument of the error decides first, the selection of the call then
    assert by_unit is not None and "--teryt 12" in by_unit


def test_example_for_positional_api_only_and_example_less_commands():
    # a positional argument has no flag; its example shows the value
    assert example_for("parse", "sheet") == (None, "kartograf parse N-34-130-D-d-2-4")
    # a command only the API has: no flag and no command line
    assert example_for("find_sheets", "scale") == (None, None)
    assert example_for("find_sheets", "nope") == (None, None)
    # a command without examples: the flag only
    assert example_for("project status", "project_dir") == ("--project", None)


@pytest.mark.parametrize(
    ("command", "param"),
    _CLI_WITH_EXAMPLES,
    ids=[f"{c.id}:{p.name}" for c, p in _CLI_WITH_EXAMPLES],
)
def test_example_for_every_declared_option(command, param):
    lines = _lines(command.id)

    flag, line = example_for(command.id, param.name)

    assert flag == param.cli_flag
    assert line in lines
    words = {w for w in (param.cli_flag, param.short) if w}
    if words:
        shown = [text for text in lines if words & set(shlex.split(text))]
        assert line == (shown[0] if shown else lines[0])


def test_example_command_line_is_valid():
    """Every line ``example_for`` can return parses with the real parser as the
    command it was asked for."""
    parser = build_parser(_DECLARED.commands, _DECLARED.groups, usage_errors=True)

    for command, param in _CLI_WITH_EXAMPLES:
        _, line = example_for(command.id, param.name)
        assert line is not None
        words = shlex.split(line)
        parsed = parse_command_line(parser, words[1:])
        assert words[0] == "kartograf"
        assert parsed._command_id == command.id


# =============================================================================
# The real declarations as a whole (spec 8.5, 12.5)
# =============================================================================

_GROUPS = (
    "boundaries",
    "cadastre",
    "elevation",
    "geodesy",
    "hydro",
    "imagery",
    "landcover",
    "maps",
    "models3d",
    "names",
    "project",
    "soil",
    "cache",
)
_NO_GROUP = (
    "parse",
    "catalog",
    "find_sheets",
    "store_overview",
    "store_entries",
    "store_sidecar",
)


def _leaf_parsers(parser, path=()):
    """Every command (a parser without commands) of an argparse tree, by words."""
    action = _subparsers(parser)
    if action is None:
        yield " ".join(path), parser
        return
    for name, child in action.choices.items():
        yield from _leaf_parsers(child, (*path, name))


def _exclusive_groups(parser) -> set[frozenset[str]]:
    return {
        frozenset(a.dest for a in group._group_actions)
        for group in parser._mutually_exclusive_groups
    }


def test_real_parser_matches_the_catalog():
    """Spec 12.5 a: the parser of the CLI has, for every command of the catalog,
    the flags with the ``dest``, type, default, choices, argument count and
    exclusive groups of the catalog and the declarations - and no other flag."""
    leaves = dict(_leaf_parsers(create_parser()))
    commands = {c.id: c for c in get_catalog(params=True).commands if c.cli}
    declarations = {c.id: c for c in _DECLARED.commands}

    assert len(commands) == 37 and set(leaves) == set(commands)
    for command_id, command in commands.items():
        leaf, declaration = leaves[command_id], declarations[command_id]
        expected_flags = {
            flag for p in command.params or () for flag in (p.flag, p.short) if flag
        }
        flags = {
            flag
            for action in leaf._actions
            for flag in action.option_strings
            if flag not in ("-h", "--help")
        }
        assert flags == expected_flags, command_id
        exclusive = {
            frozenset(p.cli_dest for p in declaration.params if p.exclusive == name)
            for name in {p.exclusive for p in declaration.params if p.exclusive}
        }
        assert _exclusive_groups(leaf) == exclusive, command_id
        positional = [a for a in leaf._get_positional_actions()]
        assert [a.dest for a in positional] == [
            p.name for p in command.params or () if p.positional
        ], command_id
        for param, declared_param in zip(
            command.params or (), declaration.params, strict=True
        ):
            assert param.name == declared_param.name
            if param.positional:
                action = next(a for a in positional if a.dest == param.name)
                nargs = {"REMAINDER": argparse.REMAINDER}.get(
                    declared_param.nargs or "", declared_param.nargs
                )
                assert action.nargs == nargs, (command_id, param.name)
                continue
            if param.flag is None:
                continue
            action = leaf._option_string_actions[param.flag]
            where = (command_id, param.name)
            assert action.dest == declared_param.cli_dest, where
            assert not action.required, where  # the library reports what is missing
            if param.short:
                assert param.short in action.option_strings, where
            if param.kind == "flag":
                assert isinstance(action, argparse._StoreTrueAction), where
                continue
            if param.kind == "int":
                assert action.type is int, where
            default = (
                param.cli_default if param.cli_default is not None else param.default
            )
            assert action.default == default, where
            if declared_param.choices:
                assert action.choices is not None
                assert list(action.choices) == list(param.allowed or ()), where
            else:
                assert action.choices is None, where


def test_data_commands_are_the_twelve_in_COMMANDS_order():
    commands = data_commands()

    assert [c.id for c in commands] == list(COMMANDS)
    assert len(commands) == 12
    assert [c.id for c in get_catalog().commands if c.project_task] == list(COMMANDS)
    for command in commands:
        assert command.project_task and command.params is not None
        names = {p.name for p in command.params}
        # the options of a task and the flags of a run
        assert {"output_dir", "update"} <= names
        assert {p.name for p in command.params if p.task} == set(
            COMMANDS[command.id].options
        )
        assert command.examples


def test_catalog_has_every_group_and_command():
    short = get_catalog()
    full = get_catalog(params=True)

    assert [g.name for g in short.groups] == list(_GROUPS)
    assert len(short.commands) == len(full.commands) == 41
    assert [c.id for c in short.commands if c.group is None] == list(_NO_GROUP)
    assert [c.id for c in short.commands if c.cli is None] == list(_NO_GROUP[2:])
    assert all(c.params is None for c in short.commands)
    assert all(
        c.params is not None and c.constraints is not None and c.examples is not None
        for c in full.commands
    )
    # the commands of a group are those whose id starts with it, none of the others
    for group in short.groups:
        assert group.commands == tuple(
            c.id for c in short.commands if c.group == group.name
        )


def test_overview_is_a_short_and_complete_list_of_groups_products_and_commands():
    """What an agent reads first is under 8000 characters (it was 47 807; the CLI
    prints the same document, indented: it was 62 389), and nothing is lost: every
    group, product and command is in it, the rest is one query away."""
    catalog = get_catalog()
    document = catalog.to_dict()
    everything = get_catalog(params=True)

    assert len(catalog.to_json(indent=None)) <= 8000
    assert len(catalog.to_json()) <= 8000
    assert [g["name"] for g in document["groups"]] == list(_GROUPS)
    for group, row in zip(catalog.groups, document["groups"], strict=True):
        assert row["products"] == [p.name for p in group.products]
        assert row["summary"] == group.summary
    assert [c["id"] for c in document["commands"]] == [
        c.id for c in everything.commands
    ]
    for row in document["commands"]:
        full = get_catalog(command=row["id"]).commands[0]
        assert (row["summary"], row["tool"], row["supports_check"]) == (
            full.summary,
            full.tool,
            full.supports_check,
        )
        # what left the overview: the description and the parameters
        assert full.description and full.params is not None
    for group in catalog.groups:
        detail = get_catalog(group=group.name).groups[0]
        assert detail.description and detail.products == group.products


def test_catalog_filters_and_errors():
    soil = get_catalog(group="soil")
    one = {i: get_catalog(command=i).commands[0] for i in ("parse", "find_sheets")}

    assert [g.name for g in soil.groups] == ["soil"]
    assert [c.id for c in soil.commands] == [
        "soil download",
        "soil hsg",
        "soil list-sources",
        "soil list-layers",
    ]
    assert all(c.params is None for c in soil.commands)
    assert [c.id for c in get_catalog(group="soil", params=True).commands] == [
        c.id for c in soil.commands
    ]
    assert all(c.params for c in get_catalog(group="soil", params=True).commands)
    # one command: with its parameters, whether it has a group or a CLI or not
    assert one["parse"].group is None and one["parse"].params
    assert one["find_sheets"].cli is None and one["find_sheets"].params
    assert get_catalog(command="parse", params=False).commands[0].params is None
    # the tables only on request: not in a group, a command or the overview
    for view in (soil, get_catalog(command="parse"), get_catalog()):
        assert (view.exit_codes, view.errors, view.schemas) == (None, None, None)
    tables = get_catalog(group="soil", tables=True)
    assert [r.code for r in tables.exit_codes] == [0, 1, 2, 130, 143]
    assert tables.errors and tables.schemas
    short = get_catalog()

    with pytest.raises(ValidationError) as group:
        get_catalog(group="nope")
    with pytest.raises(ValidationError) as command:
        get_catalog(command="nope")
    with pytest.raises(ValidationError) as other_group:
        get_catalog(group="soil", command="elevation download")
    with pytest.raises(ValidationError) as api_only:
        get_catalog(group="soil", command="find_sheets")

    assert (group.value.option, group.value.allowed) == ("group", _GROUPS)
    assert command.value.option == "command"
    assert command.value.allowed == tuple(c.id for c in short.commands)
    assert other_group.value.option == "command"
    assert api_only.value.option == "command"
    assert api_only.value.allowed == tuple(c.id for c in soil.commands)


def test_catalog_does_not_import_cli_or_mcp():
    """In a clean process the catalog - declarations, parser, hints, the sheet
    documents that read it - loads neither ``kartograf.cli`` nor ``mcp``."""
    code = (
        "import sys\n"
        "import kartograf.catalog, kartograf.catalog.build, "
        "kartograf.catalog.cliparser, kartograf.catalog.hints, "
        "kartograf.catalog.formatting, kartograf.catalog.kinds, "
        "kartograf.catalog.model, kartograf.catalog.shared, "
        "kartograf.catalog.spec, kartograf.sheet_info\n"
        "from kartograf.catalog.commands import declared\n"
        "declared()\n"
        "kartograf.catalog.get_catalog(params=True)\n"
        "kartograf.catalog.hints.example_for('elevation download', 'cutout')\n"
        "kartograf.sheet_info.describe_sheet('N-34-130-D-d-2-4')\n"
        "loaded = sorted(\n"
        "    name for name in sys.modules\n"
        "    if name.split('.')[0] == 'mcp' or name.startswith('kartograf.cli')\n"
        ")\n"
        "print(loaded)\n"
        "sys.exit(1 if loaded else 0)\n"
    )

    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stdout + done.stderr


# =============================================================================
# The constraints of the declarations are enforced by the library (spec 8.4)
# =============================================================================

_SAMPLES: dict[str, object] = {
    "sheet": "N-34-130-D-d-2-4",
    "teryt": "1465",
    "ku": "623164",
    "geometry": "area.gpkg",
    "whole_country": True,
    "bbox": [500000, 500000, 501000, 501000],
    "year": 2020,
    "horizontal_crs": "EPSG:5514",
}


def _sample(param: Param) -> object:
    """A value of a parameter that is valid on its own (the call fails for the
    constraint under test, not for the value)."""
    if param.name in _SAMPLES:
        return _SAMPLES[param.name]
    allowed = resolve(param.allowed)
    if allowed:
        return [allowed[0]] if param.kind == "str_list" else allowed[0]
    return {"flag": True, "int": 1, "path": "x.gpkg", "str_list": ["A"]}.get(
        param.kind, "1m" if param.kind == "per_country" else "x"
    )


def _holds(when: object, options: dict[str, object]) -> bool:
    """The ``when`` of a constraint holds for a call: a parameter given
    (``True``) or having one of the listed values."""
    assert isinstance(when, dict)
    for name, wanted in when.items():
        value = options.get(name)
        if wanted is True and value in (None, False):
            return False
        if isinstance(wanted, list) and value not in wanted:
            return False
    return True


class _Call:
    """The task options of a call derived from an example, with the edits that
    keep it consistent: a parameter of an area choice replaces the other areas
    (a ``bbox`` carries its ``bbox_crs``) and brings what it requires."""

    def __init__(self, command: Command, example: Example) -> None:
        self.command = command
        self.options: dict[str, object] = dict(example.options)
        self.params = {p.name: p for p in command.params}
        self.touched: set[str] = set()

    def drop(self, *names: str) -> None:
        for name in names:
            self.options.pop(name, None)
            self.touched.add(name)

    def add(self, name: str) -> None:
        self.options[name] = _sample(self.params[name])
        self.touched.add(name)
        for constraint in self.command.constraints:
            if constraint.type == "one_of" and name in constraint.params:
                for other in constraint.params:
                    if other != name:
                        self.options.pop(other, None)
            if constraint.type == "requires" and constraint.param == name:
                for needed in constraint.params:
                    if needed not in self.options:
                        self.add(needed)
        self.settle()

    def settle(self) -> None:
        if "bbox" in self.options:
            self.options.setdefault("bbox_crs", "EPSG:2180")
        else:
            self.options.pop("bbox_crs", None)


def _base(command: Command, name: str, *, applies: bool) -> _Call:
    """A call of the command to add ``name`` to: from the first example that has
    it (``applies``) or lacks it and where its ``applies_to`` condition fails
    (``not applies``), else from an example where the condition holds."""
    conditions = [
        c.when
        for c in command.constraints
        if c.type == "applies_to" and c.param == name and c.when
    ]
    for example in command.examples:
        options = dict(example.options)
        if (name in options) == applies and all(
            _holds(when, options) == applies for when in conditions
        ):
            return _Call(command, example)
    for example in command.examples:
        if all(_holds(when, dict(example.options)) for when in conditions):
            return _Call(command, example)
    raise AssertionError(f"{command.id}: no example to derive a call with {name}")


def _violations(command: Command, constraint: Constraint):
    """``(label, base, violation)`` calls of a constraint: ``base`` satisfies it
    (the library accepts it) and ``violation`` differs from it only by the edit
    that breaks the constraint; the edits are recorded in ``touched``."""
    first = _Call(command, command.examples[0])
    if constraint.type == "one_of":
        stripped = _Call(command, command.examples[0])
        stripped.drop(*constraint.params)
        stripped.settle()
        yield "none", first, stripped
        pair = _Call(command, command.examples[0])
        pair.drop(*constraint.params)
        pair.touched.clear()
        for name in constraint.params[:2]:
            pair.options[name] = _sample(pair.params[name])
            pair.touched.add(name)
        pair.settle()
        yield "two", first, pair
    elif constraint.type == "requires":
        assert constraint.param is not None
        base = _base(command, constraint.param, applies=True)
        if constraint.param not in base.options:
            base.add(constraint.param)
        violation = _Call(command, Example(dict(base.options)))
        violation.drop(*constraint.params)
        yield "missing", base, violation
    elif constraint.type == "excludes":
        assert constraint.param is not None
        base = _base(command, constraint.param, applies=True)
        if constraint.param not in base.options:
            base.add(constraint.param)
        violation = _Call(command, Example(dict(base.options)))
        for name in constraint.params:
            violation.add(name)
        yield "both", base, violation
    elif constraint.type == "applies_to":
        assert constraint.param is not None
        base = _base(command, constraint.param, applies=False)
        violation = _Call(command, Example(dict(base.options)))
        violation.add(constraint.param)
        yield "outside", base, violation


_CASES = [
    (command, constraint, label, base, violation)
    for command in _DECLARED.commands
    if command.project_task
    for constraint in command.constraints
    if constraint.type in ("one_of", "requires", "excludes", "applies_to")
    for label, base, violation in _violations(command, constraint)
]


# Track A names the whole area group (``sheet``, ``bbox``, ``geometry``) when a
# request has no area (``_selection_names`` of ``download/collections.py``), also
# for a product that takes no sheet code: ``hydro`` declares ``bbox``, ``geometry``
# and ``whole_country``. Known and tolerated here; the entry goes when Track A
# lists only what the product takes.
_AREA_GROUP_EXTRA = {("hydro download", "one_of"): {"sheet"}}


def _named(error: ValidationError) -> set[str]:
    return set(error.options or ()) | ({error.option} if error.option else set())


@pytest.mark.parametrize(
    ("command", "constraint", "base", "violation"),
    [case[:2] + case[3:] for case in _CASES],
    ids=[f"{c.id}:{k.type}:{label}" for c, k, label, _, _ in _CASES],
)
def test_constraint_violations_raise_validation_error_naming_the_option(
    command, constraint, base, violation, tmp_path
):
    """A call derived from an example that breaks one declared constraint is
    refused by ``validate`` without network, and the error names an option of
    the constraint that the edit touched; the call before the edit passes."""
    task = COMMANDS[command.id]

    def validate(call: _Call) -> None:
        assert check_options_json(task.options, call.options) is None, call.options
        task.validate(
            tmp_path, options_from_json(task.options, call.options, base_dir=tmp_path)
        )

    validate(base)
    with pytest.raises(ValidationError) as error:
        validate(violation)

    names = {constraint.param, *constraint.params, *(constraint.when or {})}
    names -= {None}
    named = _named(error.value) - _AREA_GROUP_EXTRA.get(
        (command.id, constraint.type), set()
    )
    assert named, f"{command.id}: the error names no option: {error.value}"
    assert named <= names, (named, names, str(error.value))
    assert named & violation.touched, (named, violation.touched, str(error.value))
