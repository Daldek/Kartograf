"""The catalog document ``kartograf-catalog/1`` and ``get_catalog`` (spec 8.1, 8.5),
built from synthetic declarations."""

import dataclasses

import pytest

from kartograf.catalog import build
from kartograf.catalog.build import build_catalog, data_commands, get_catalog
from kartograf.catalog.commands import Declared
from kartograf.catalog.model import Catalog, CommandInfo, ParamInfo
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.error_report import ERROR_CODES, EXIT_CODES
from kartograf.exceptions import ValidationError
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
    catalog = _build()

    assert list(catalog.to_dict()) == [
        "schema",
        "kartograf_version",
        "language",
        "groups",
        "commands",
        "exit_codes",
        "errors",
        "schemas",
    ]
    assert catalog.schema == "kartograf-catalog/1"
    assert catalog.language == "pl"
    assert SCHEMAS["kartograf-catalog/1"] == (Catalog,)


def test_version_is_the_package_version():
    import kartograf

    assert _build().kartograf_version == kartograf.__version__


def test_default_view_has_no_params():
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
    document = catalog.to_dict()
    assert all(
        c["params"] is None and c["constraints"] is None and c["examples"] is None
        for c in document["commands"]
    )


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
    catalog = _build()

    assert [(r.code, r.name, r.meaning) for r in catalog.exit_codes] == [
        (r.code, r.name, r.meaning) for r in EXIT_CODES
    ]
    assert [(r.code, r.exception, r.exit_code, r.meaning) for r in catalog.errors] == [
        (r.code, r.exception, r.exit_code, r.meaning) for r in ERROR_CODES
    ]


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

    catalog = _build()

    # registry order; a schema without a description is not part of the catalog
    assert [(s.schema, s.description, s.produced_by) for s in catalog.schemas] == [
        ("kartograf-sheet/1", "Opis godla", ("parse",)),
        ("kartograf-download/1", "Wynik komendy danych", ("elevation download",)),
        # the check twin of a command produces its plan schema too
        ("kartograf-plan/1", "Plan aktualizacji", ("elevation download",)),
        ("kartograf-error/1", "Blad komendy", ()),
    ]


def test_every_library_schema_has_a_description():
    described = {s.schema for s in _build().schemas}

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
