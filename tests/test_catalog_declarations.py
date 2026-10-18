"""Declarations of the command catalog (spec 8.2-8.4): what a declaration
derives, when its providers run and which declarations are refused."""

import dataclasses
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest

import kartograf
from kartograf.catalog import commands as commands_package
from kartograf.catalog import shared
from kartograf.catalog.commands import declared, elevation
from kartograf.catalog.spec import (
    SHEET_SYSTEMS,
    Command,
    Constraint,
    Example,
    Group,
    Param,
    resolve,
)
from kartograf.core.parser_2000 import SCALE_HIERARCHY_2000
from kartograf.core.parser_registry import SYSTEMS, detect_system, ztm_sheet_system
from kartograf.core.sheet_parser import PL_BBOX_CRS, SheetParser
from kartograf.download.availability import (
    AVAILABILITY_COUNTRIES,
    AVAILABILITY_PRODUCTS,
)
from kartograf.download.collections import (
    collection_choice_values,
    collection_countries,
    collection_products,
)
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_contours import contours_formats
from kartograf.download.options import (
    BBOX_CRS_CHOICES,
    COUNTRIES,
    ELEVATION_PRODUCTS,
    IMAGERY_PRODUCTS,
    SCALES_2000,
)
from kartograf.download.orto_cutout import ORTO_CUTOUT_CRS
from kartograf.landcover.manager import LANDCOVER_PRODUCTS
from kartograf.project.commands import COMMANDS, check_options_json, options_from_json
from kartograf.providers.pl.gugik_orto import (
    ORTO_KEY,
    cutout_resolution_labels,
    image_source,
)
from kartograf.sources.registry import sources_for
from kartograf.sources.variants import parse_resolution, variants


def _command(*params: Param, **fields) -> Command:
    """A minimal valid command around ``params``."""
    values = {
        "id": "elevation download",
        "summary": "Pobierz dane",
        "kind": "data",
        "function": "download_data",
        "result_schema": "kartograf-download/1",
        "params": params,
    }
    return Command(**{**values, **fields})


def test_param_derives_flag_and_argument_from_name():
    param = Param("vertical_crs", "str")

    assert param.cli_flag == "--vertical-crs"
    assert param.api_argument == "vertical_crs"
    assert param.cli_dest == "vertical_crs"


def test_flag_none_is_api_only_and_argument_none_is_cli_only():
    api_only = Param("update", "str", flag=None)
    cli_only = Param("quiet", "flag", argument=None)
    renamed = Param("output_dir", "path", flag="--output", short="-o", dest="output")

    assert (api_only.cli_flag, api_only.api_argument) == (None, "update")
    assert (cli_only.cli_flag, cli_only.api_argument) == ("--quiet", None)
    assert (renamed.cli_flag, renamed.api_argument, renamed.cli_dest) == (
        "--output",
        "output_dir",
        "output",
    )


def test_positional_param_has_no_flag():
    sheet = Param("sheet", "str", positional=True, metavar="GODLO")

    assert sheet.cli_flag is None
    assert sheet.api_argument == "sheet"


def test_providers_are_called_late() -> None:
    calls: list[str] = []

    def allowed() -> tuple[str, ...]:
        calls.append("allowed")
        return ("nmt", "nmpt")

    def description() -> str:
        calls.append("description")
        return "Produkt (wymagany)"

    param = Param("product", "str", description, allowed=allowed, choices=True)
    command = _command(param, description=description)

    assert calls == []
    assert resolve(param.allowed) == ("nmt", "nmpt")
    assert resolve(param.description) == "Produkt (wymagany)"
    assert resolve(command.description) == "Produkt (wymagany)"
    assert calls == ["allowed", "description", "description"]
    assert resolve("plain text") == "plain text"
    assert resolve(("a", "b")) == ("a", "b")


def test_shared_param_can_be_overridden():
    product = dataclasses.replace(
        shared.PRODUCT,
        description="Produkt grupy",
        allowed=("nmt", "nmpt"),
        required=False,
    )

    assert product.description == "Produkt grupy"
    assert product.allowed == ("nmt", "nmpt")
    assert product.required is False
    # the shared declaration stays as it was
    assert shared.PRODUCT.required is True
    assert shared.PRODUCT.allowed is None


def test_required_needs_an_api_argument():
    with pytest.raises(ValueError, match="argument"):
        Param("quiet", "flag", argument=None, required=True)

    assert Param("sheet", "str", required=True).required is True


@pytest.mark.parametrize(
    "fields",
    [
        {"name": "Bad-Name", "kind": "str"},
        {"name": "x", "kind": "float"},
        {"name": "x", "kind": "str", "flag": "-x"},
        {"name": "x", "kind": "str", "short": "-xx"},
        {"name": "x", "kind": "str", "flag": None, "short": "-x"},
        {"name": "x", "kind": "str", "choices": True},
        {"name": "x", "kind": "str", "normalize": "title"},
        {"name": "x", "kind": "str", "nargs": "*"},
        {"name": "x", "kind": "str", "positional": True, "flag": "--x"},
        {"name": "x", "kind": "str", "positional": True, "dest": "y"},
        {"name": "x", "kind": "str", "exclusive": "update", "flag": None},
        {"name": "x", "kind": "str", "accepts": ("pl1992",)},
        {"name": "sheet", "kind": "str", "accepts": ("pl1993",)},
        {"name": "x", "kind": "str", "task": True, "argument": None},
    ],
)
def test_invalid_declaration_of_a_param_is_refused(fields):
    with pytest.raises(ValueError):
        Param(**fields)


def test_command_derives_group_name_and_check_support():
    plain = _command(Param("product", "str"))
    with_check = _command(
        Param("product", "str"),
        check_function="check_data",
        check_result_schema="kartograf-plan/1",
    )
    root = _command(id="parse", function="describe_sheet", kind="query")
    api_only = _command(id="find_sheets", cli=None, kind="query")

    assert (plain.group, plain.name, plain.cli_words) == (
        "elevation",
        "download",
        "elevation download",
    )
    assert plain.supports_check is False
    assert with_check.supports_check is True
    assert (root.group, root.name, root.cli_words) == (None, "parse", "parse")
    assert (api_only.group, api_only.cli_words) == (None, None)


@pytest.mark.parametrize(
    "fields",
    [
        {"id": "Elevation Download"},
        {"id": "a b c"},
        {"check_function": "check_data"},
        {"check_result_schema": "kartograf-plan/1"},
        {"project_task": True, "kind": "query"},
        {"kind": "other"},
        {"effects": ("teleport",)},
        {"result_schema": "download"},
    ],
)
def test_invalid_declaration_of_a_command_is_refused(fields):
    with pytest.raises(ValueError):
        _command(Param("product", "str"), **fields)


def test_command_params_must_have_unique_names():
    with pytest.raises(ValueError, match="product"):
        _command(Param("product", "str"), Param("product", "int"))


def test_api_only_command_declares_no_cli_flag():
    with pytest.raises(ValueError, match="flag"):
        _command(Param("segment", "str"), id="store_entries", cli=None)

    api_only = _command(
        Param("segment", "str", flag=None), id="store_entries", cli=None
    )
    assert api_only.params[0].cli_flag is None


def test_constraint_and_example_are_plain_data():
    constraint = Constraint(
        "requires", ("horizontal_crs",), "--cutout wymaga --horizontal-crs", "cutout"
    )
    example = Example({"product": "nmt"}, run={"quiet": True})

    assert (constraint.type, constraint.param, constraint.params) == (
        "requires",
        "cutout",
        ("horizontal_crs",),
    )
    assert constraint.when is None
    assert example.title is None
    assert example.options == {"product": "nmt"}


def test_group_has_a_position_in_the_help_list():
    plain = Group("elevation", "Wysokosci", "Dane wysokosciowe")
    last = Group("cache", "Cache", "Cache metadanych", position=2)

    assert plain.position < last.position


# =============================================================================
# The declared commands: every module of kartograf/catalog/commands/
# =============================================================================

_DECLARED = declared()
_IDS = [command.id for command in _DECLARED.commands]
_DATA = [command for command in _DECLARED.commands if command.project_task]
_EXAMPLES = [(c, i) for c in _DATA for i in range(len(c.examples))]
_EXAMPLE_IDS = [f"{c.id}#{i}" for c, i in _EXAMPLES]
# the registry values a command offers: each must come from a provider
_REGISTRY_PARAMS = (
    "product",
    "country",
    "resolution",
    "vertical_crs",
    "format",
    "model",
    "scale",
    "sheet_system",
    "bbox_crs",
    "horizontal_crs",
    "coverage",
    "direction",
)


def test_elevation_and_imagery_commands_are_declared():
    assert {
        "elevation download",
        "elevation list-sources",
        "elevation availability",
        "imagery download",
        "imagery list-sources",
    } <= set(_IDS)


_PROJECT_COMMANDS = (
    "project init",
    "project add",
    "project remove",
    "project download",
    "project status",
    "project verify",
)
_API_ONLY = ("find_sheets", "store_overview", "store_entries", "store_sidecar")


def test_project_cache_parse_catalog_and_api_only_commands_are_declared():
    assert {
        *_PROJECT_COMMANDS,
        "cache stats",
        "cache path",
        "cache clear",
        "parse",
        "catalog",
        *_API_ONLY,
    } <= set(_IDS)
    # only the API has these four: no CLI words, no flag, no parser
    assert [c.id for c in _DECLARED.commands if c.cli is None] == list(_API_ONLY)
    assert [g.name for g in _DECLARED.groups if g.name in ("project", "cache")] == [
        "project",
        "cache",
    ]
    assert next(g for g in _DECLARED.groups if g.name == "cache").position == 2


@pytest.mark.parametrize("command_id", _PROJECT_COMMANDS)
def test_project_commands_take_the_project_directory_like_the_cli_did(command_id):
    params = {p.name: p for p in _COMMAND_BY_ID[command_id].params}

    project_dir = params["project_dir"]
    assert (project_dir.cli_flag, project_dir.cli_dest) == ("--project", "project")
    assert (project_dir.cli_default, project_dir.default) == (".", None)
    assert (project_dir.kind, project_dir.required) == ("path", True)
    assert project_dir.section is None  # the help of a project command has no sections


def test_project_add_takes_a_data_command_of_the_manifest_and_its_options():
    params = {p.name: p for p in _COMMAND_BY_ID["project add"].params}

    assert resolve(params["command"].allowed) == list(COMMANDS)
    assert callable(params["command"].allowed)  # read from the declarations, no copy
    assert (params["command"].cli_flag, params["command"].required) == (None, True)
    assert (params["options"].kind, params["options"].required) == ("options", True)
    assert (params["options"].cli_flag, params["options"].task) == (None, False)
    # the CLI words after the name are the command and its options
    assert (params["name"].positional, params["name"].required) == (True, True)
    assert (params["arguments"].nargs, params["arguments"].argument) == (
        "REMAINDER",
        None,
    )


def test_project_download_has_the_update_modes_but_no_plan():
    download = _COMMAND_BY_ID["project download"]
    params = {p.name: p for p in download.params}

    assert (download.check_function, download.check_result_schema) == (
        "check_project",
        "kartograf-project-check/1",
    )
    assert download.supports_check and not download.project_task
    assert "plan" not in params
    assert {
        name: params[name].exclusive for name in ("check_updates", "upgrade", "force")
    } == {
        "check_updates": "update",
        "upgrade": "update",
        "force": "update",
    }
    assert (params["update"].cli_flag, resolve(params["update"].allowed)) == (
        None,
        ["upgrade", "force"],
    )
    assert (params["workers"].default, params["workers"].cli_default) == (None, None)
    assert (params["tasks"].positional, params["tasks"].nargs) == (True, "*")


def test_catalog_command_offers_the_groups_and_the_commands_of_the_catalog():
    params = {p.name: p for p in _COMMAND_BY_ID["catalog"].params}

    groups = resolve(params["group"].allowed)
    assert groups == [g.name for g in _DECLARED.groups]
    assert groups[-1] == "cache" and "project" in groups
    assert resolve(params["command"].allowed) == _IDS
    assert (params["group"].positional, params["group"].nargs) == (True, "?")
    assert (params["command"].positional, params["command"].nargs) == (True, "?")
    assert (params["params"].kind, params["params"].default) == ("flag", None)


def test_the_sheet_search_requires_the_choice_of_sheets_and_one_area():
    find = _COMMAND_BY_ID["find_sheets"]
    params = {p.name: p for p in find.params}

    assert {name for name, p in params.items() if p.required} == {
        "scale",
        "sheet_system",
    }
    assert [(c.type, c.params) for c in find.constraints] == [
        ("one_of", ("bbox", "geometry")),
        ("requires", ("geometry",)),
    ]
    assert (params["bbox"].kind, params["bbox_crs"].kind) == ("bbox", "bbox_crs")
    assert find.cli is None and not find.examples


def test_the_store_reads_require_what_the_spec_requires():
    required = {
        command_id: {p.name for p in _COMMAND_BY_ID[command_id].params if p.required}
        for command_id in ("store_overview", "store_entries", "store_sidecar")
    }

    assert required == {
        "store_overview": {"output_dir"},
        "store_entries": {"output_dir", "segment", "limit"},
        "store_sidecar": {"path"},
    }


def test_sheet_systems_are_those_of_the_parser_registry():
    assert set(SHEET_SYSTEMS) == {system.id for system in SYSTEMS} | {"cz_ztm"}


@pytest.mark.parametrize("command", _DECLARED.commands, ids=_IDS)
def test_task_options_equal_manifest_options(command):
    """The task parameters of a data command are the options of its manifest
    entry (the order is not compared: spec 8.3 item 7)."""
    if not command.project_task:
        assert command.id not in COMMANDS
        assert [p.name for p in command.params if p.task] == []
        return
    declared_options = {p.name: p.kind for p in command.params if p.task}
    assert declared_options == dict(COMMANDS[command.id].options)


@pytest.mark.parametrize(("command", "index"), _EXAMPLES, ids=_EXAMPLE_IDS)
def test_examples_pass_task_validation(command, index, tmp_path):
    options = dict(command.examples[index].options)
    task = COMMANDS[command.id]

    assert check_options_json(task, options) is None
    task.validate(tmp_path, options_from_json(task, options, project_dir=tmp_path))


def _countries_of(command: Command) -> set[str]:
    """PL and CZ among the countries of the sources of the command's products."""
    product = next((p for p in command.params if p.name == "product"), None)
    names = resolve(product.allowed) if product and product.allowed else ()
    found = {d.country for name in names for d in sources_for(product=name)}
    return found & {"PL", "CZ"}


def _example_countries(example: Example) -> set[str]:
    """The countries an example targets: its ``country``, the country of its sheet
    code, a CZ cadastral area or PL unit, or the only country of its product."""
    options = example.options
    country = options.get("country")
    if country in ("pl", "cz"):
        return {str(country).upper()}
    if country == "auto":
        return {"PL", "CZ"}
    sheet = options.get("sheet")
    if isinstance(sheet, str):
        if ztm_sheet_system(sheet) is not None:
            return {"CZ"}
        return {detect_system(sheet).country}
    if "ku" in options:
        return {"CZ"}
    if "teryt" in options:
        return {"PL"}
    found = {d.country for d in sources_for(product=str(options.get("product")))}
    found &= {"PL", "CZ"}
    return found if len(found) == 1 else set()


@pytest.mark.parametrize("command", _DATA, ids=[c.id for c in _DATA])
def test_examples_cover_pl_and_cz(command):
    """A data command shows an example of every country its products have."""
    targeted = [_example_countries(example) for example in command.examples]

    for country in sorted(_countries_of(command)):
        assert any(country in found for found in targeted), country


_SCALES_1992 = list(SheetParser.SCALE_HIERARCHY)
_COMMAND_BY_ID = {command.id: command for command in _DECLARED.commands}
_COLLECTION_GROUPS = (
    "boundaries",
    "cadastre",
    "models3d",
    "hydro",
    "names",
    "maps",
    "geodesy",
)
_PRODUCTS_OF = {
    "elevation download": ELEVATION_PRODUCTS,
    "elevation availability": AVAILABILITY_PRODUCTS,
    "elevation list-sources": ELEVATION_PRODUCTS,
    "imagery download": IMAGERY_PRODUCTS,
    "imagery list-sources": IMAGERY_PRODUCTS,
    "landcover download": LANDCOVER_PRODUCTS,
    "landcover list-sources": LANDCOVER_PRODUCTS,
    "landcover list-layers": LANDCOVER_PRODUCTS,
    "soil list-sources": ("soil",),
}


def _collected(group: str, key: str) -> set[str]:
    """The values of the option ``key`` over the products of a collection group."""
    return {
        value
        for product in collection_products(group)
        for values in collection_choice_values(product, key).values()
        for value in values
    }


def _expected_allowed(command_id: str, name: str) -> list[str] | set[str]:
    """The allowed values of a registry parameter, read from the registry in
    another way than the declaration does (a set: the order is the registry's)."""
    if command_id == "find_sheets":  # the sheet search takes the Polish CRSs
        scales_2000 = [s for s in SCALE_HIERARCHY_2000 if s not in _SCALES_1992]
        return {
            "bbox_crs": list(PL_BBOX_CRS),
            "scale": [*_SCALES_1992, *scales_2000],
            "sheet_system": list(SheetParser.VALID_SYSTEMS),
        }[name]
    group = command_id.split()[0]
    collection = group in _COLLECTION_GROUPS
    if name == "bbox_crs":
        return list(BBOX_CRS_CHOICES)
    if name in ("scale", "sheet_system", "format") and collection:
        return _collected(group, name)
    if name == "scale":
        return list(SCALES_2000)
    if name == "sheet_system":
        return ["1992", "2000"]
    if name == "country":
        if command_id == "elevation availability":
            return list(AVAILABILITY_COUNTRIES)
        if collection:
            return [*collection_countries(collection_products(group)), "auto"]
        return list(COUNTRIES)
    if name == "product":
        if collection:
            return list(collection_products(group))
        return list(_PRODUCTS_OF[command_id])
    if group == "landcover" and name == "format":
        return ["GPKG", "SHP", "GML"]
    if group == "landcover" and name == "horizontal_crs":
        return ["EPSG:5514", "EPSG:3045"]
    if name == "resolution" and command_id == "elevation download":
        labels = {v.label for p in ("nmt", "nmpt") for v in variants(product=p)}
        return sorted(
            (label for label in labels if label is not None),
            key=lambda label: parse_resolution(label) or 0,
        )
    if name == "resolution":  # the WCS pixels of the orthophotomap and true orto
        true_orto = image_source("true-orto")
        assert true_orto is not None
        return {
            *cutout_resolution_labels(ORTO_KEY, "standard"),
            *cutout_resolution_labels(ORTO_KEY, "high"),
            *cutout_resolution_labels(true_orto.key, None),
        }
    if name == "vertical_crs":
        return {v.vertical_crs for v in variants() if v.vertical_crs}
    if name == "model":
        return {v.model for v in variants(product="laz", country="CZ") if v.model}
    if name == "format":
        formats = {
            v.format
            for product in ("nmt", "nmpt")
            for v in variants(product=product, country="PL")
        }
        return formats | set(contours_formats())
    if name == "horizontal_crs":
        return (
            list(CUTOUT_CRS)
            if command_id == "elevation download"
            else [ORTO_CUTOUT_CRS]
        )
    if name == "coverage":
        return {"standard", "high"}
    if name == "direction":
        return ["n", "e", "s", "w"]
    raise KeyError((command_id, name))


@pytest.mark.parametrize("command", _DECLARED.commands, ids=_IDS)
def test_allowed_comes_from_a_provider_not_a_copy(command):
    for param in command.params:
        if param.name not in _REGISTRY_PARAMS or param.allowed is None:
            continue
        assert callable(param.allowed), f"{command.id}.{param.name}: a copy"
        expected = _expected_allowed(command.id, param.name)
        got = resolve(param.allowed)
        if isinstance(expected, set):
            assert set(got) == expected, (command.id, param.name)
        else:
            assert list(got) == expected, (command.id, param.name)


def test_a_provider_reads_the_registry_when_it_is_called(monkeypatch):
    """The values are those of the registry at the time of the call: a variant
    registered later is offered (no copy of the lists)."""
    real = elevation.variants

    def with_test_variant(**filters):
        found = real(**filters)
        return (*found, dataclasses.replace(found[0], vertical_crs="TESTCRS"))

    vertical = next(
        p
        for p in _COMMAND_BY_ID["elevation download"].params
        if p.name == "vertical_crs"
    )
    assert "TESTCRS" not in resolve(vertical.allowed)

    monkeypatch.setattr(elevation, "variants", with_test_variant)

    assert "TESTCRS" in resolve(vertical.allowed)


def _texts(command: Command) -> list[str]:
    texts = [command.summary, resolve(command.description)]
    for param in command.params:
        texts += [resolve(param.description), param.section or "", param.metavar or ""]
    texts += [constraint.message for constraint in command.constraints]
    texts += [example.title or "" for example in command.examples]
    return texts


@pytest.mark.parametrize("command", _DECLARED.commands, ids=_IDS)
def test_texts_are_ascii_and_summary_is_short(command):
    assert len(command.summary) <= 120
    assert command.summary and resolve(command.description)
    for text in _texts(command):
        assert text.isascii(), text
    for param in command.params:
        assert resolve(param.description), f"{command.id}.{param.name}: no description"


def test_group_texts_are_ascii():
    for group in _DECLARED.groups:
        assert group.summary.isascii() and group.description.isascii()
        for name, summary in resolve(group.products):
            assert name.isascii() and summary.isascii() and summary


@pytest.mark.parametrize("command", _DECLARED.commands, ids=_IDS)
def test_constraints_reference_declared_params(command):
    names = {param.name for param in command.params}

    for constraint in command.constraints:
        for name in (constraint.param, *constraint.params, *(constraint.when or {})):
            assert name is None or name in names, (command.id, constraint, name)
    for example in command.examples:
        assert set(example.options) | set(example.run) <= names


def _library_function(name: str):
    """The function of a command: exported by ``kartograf`` (spec 12.5 c)."""
    assert name in kartograf.__all__, f"{name} is not in kartograf.__all__"
    function = getattr(kartograf, name)
    assert callable(function), name
    return function


def _default(parameter: inspect.Parameter) -> object:
    return None if parameter.default is inspect.Parameter.empty else parameter.default


@pytest.mark.parametrize("command", _DECLARED.commands, ids=_IDS)
def test_arguments_match_the_signature_of_the_function(command):
    """Every argument of a command is a parameter of its function, a parameter
    without a default is required, the defaults agree and the function takes
    keyword arguments (the first one may name the object)."""
    arguments = {
        p.api_argument: p
        for p in command.params
        if p.api_argument is not None and p.kind != "bbox_crs"
    }
    for name in (command.function, command.check_function):
        if name is None:
            continue
        function = _library_function(name)
        parameters = inspect.signature(function).parameters
        # the check twin takes the task options and the store, not the run options
        wanted = {
            argument: param
            for argument, param in arguments.items()
            if name == command.function or param.task or argument == "output_dir"
        }
        for argument, param in wanted.items():
            assert argument in parameters, f"{name} has no argument {argument}"
            assert param.default == _default(parameters[argument]), (name, argument)
        for position, (argument, parameter) in enumerate(parameters.items()):
            if parameter.default is inspect.Parameter.empty:
                assert argument in arguments and arguments[argument].required, (
                    f"{name}: {argument} has no default, so it is required"
                )
            if position > 0 or parameter.kind is inspect.Parameter.KEYWORD_ONLY:
                assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, (
                    name,
                    argument,
                )


@pytest.mark.parametrize("command", _DECLARED.commands, ids=_IDS)
def test_result_schemas_are_registered(command):
    """The schema a command names is that of a document class of the library, and
    the catalog describes it and lists the command among its producers."""
    from kartograf.catalog import get_catalog
    from kartograf.serialization import SCHEMAS

    described = {info.schema: info for info in get_catalog().schemas}
    for schema in (command.result_schema, command.check_result_schema):
        if schema is None:
            continue
        assert schema in SCHEMAS, f"{command.id}: {schema} is not registered"
        assert schema in described, f"{command.id}: {schema} has no description"
        assert command.id in described[schema].produced_by


def test_every_described_schema_has_a_producer_but_the_error_document():
    """A document nobody returns is a dead type or a missing command."""
    from kartograf.catalog import get_catalog

    unproduced = {info.schema for info in get_catalog().schemas if not info.produced_by}

    assert unproduced == {"kartograf-error/1"}


def test_declaration_modules_do_not_call_providers_at_import(monkeypatch):
    """Importing a declaration module computes nothing from the registry: every
    function that reads it is replaced by one that fails, and each module is
    executed afresh."""
    stubs = {
        "kartograf.sources.registry": ("sources_for", "all_sources", "get_source"),
        "kartograf.sources.variants": (
            "variants",
            "cz_model_text",
            "cz_resolution_text",
            "format_tokens",
        ),
        "kartograf.download.options": (
            "resolution_text",
            "vertical_crs_text",
            "format_text",
            "cz_resolution_help",
            "store_files",
            "product_directory",
        ),
        "kartograf.download.cz_contours": ("contours_formats",),
        "kartograf.download.collections": (
            "collection_products",
            "collection_product_choices",
            "collection_countries",
            "collection_choice_values",
            "collection_level_choices",
            "collection_variant_choices",
        ),
        "kartograf.landcover.manager": (
            "bdot10k_archive_choices",
            "bdoo_year_choices",
            "corine_year_choices",
            "soil_choices",
        ),
        "kartograf.download.orto_cutout": (
            "orto_coverage_choices",
            "cutout_resolution_choices",
        ),
        "kartograf.providers.pl.gugik_orto": (
            "wcs_cutout_channels",
            "image_source",
            "image_directions",
        ),
    }

    def failing(name):
        def call(*args, **kwargs):
            raise AssertionError(f"{name} called while a declaration was imported")

        return call

    for module_name, names in stubs.items():
        module = importlib.import_module(module_name)
        for name in names:
            monkeypatch.setattr(module, name, failing(name))
    package = Path(commands_package.__file__).parent
    for path in sorted(package.glob("[a-z]*.py")):
        spec = importlib.util.spec_from_file_location(f"_probe_{path.stem}", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.COMMANDS
