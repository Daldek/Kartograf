"""The catalog document ``kartograf-catalog/1`` and ``get_catalog`` (spec 8.1, 8.5),
built from synthetic declarations; the parts on the real declarations (the hint
example, the completeness of the declarations) come last."""

import dataclasses
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from kartograf.catalog import build
from kartograf.catalog.build import build_catalog, data_commands, get_catalog
from kartograf.catalog.cliparser import build_parser, parse_command_line
from kartograf.catalog.commands import Declared, declared
from kartograf.catalog.hints import example_for
from kartograf.catalog.model import Catalog, CommandInfo, ParamInfo
from kartograf.catalog.spec import Command, Constraint, Example, Group, Param
from kartograf.cli import _parser as old_parser
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


def _leaf_words(parser, path=()):
    """The words of every command (a parser without commands) of an argparse tree."""
    action = old_parser._subparsers(parser)
    if action is None:
        yield path
        return
    for name, child in action.choices.items():
        yield from _leaf_words(child, (*path, name))


def test_every_old_leaf_command_is_declared():
    """Transitional (the old parser goes away in T5): the 36 commands of the old
    CLI are declared, and with ``catalog`` they are the 37 of the new one."""
    old = {" ".join(words) for words in _leaf_words(old_parser.create_parser())}
    declared_cli = {c.cli_words for c in _DECLARED.commands if c.cli_words is not None}
    new = build_parser(_DECLARED.commands, _DECLARED.groups)

    assert len(old) == 36
    assert declared_cli == old | {"catalog"}
    assert len(declared_cli) == 37
    assert {" ".join(words) for words in _leaf_words(new)} == declared_cli


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
    # the tables are in every view
    short = get_catalog()
    for view in (soil, get_catalog(command="parse")):
        assert view.exit_codes == short.exit_codes
        assert view.errors == short.errors and view.schemas == short.schemas
    assert [r.code for r in short.exit_codes] == [0, 1, 2, 130]

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
