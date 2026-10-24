"""The hint example of the catalog (spec 6.3), the parser built from the real
declarations and the constraints the library enforces (spec 8.4, 12.5); the documents
of the catalog are in ``test_catalog_documents.py``."""

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from kartograf.catalog import command_schema, list_commands
from kartograf.catalog.cliparser import _subparsers, build_parser, parse_command_line
from kartograf.catalog.commands import declared
from kartograf.catalog.hints import example_for
from kartograf.catalog.kinds import check_options_json, options_from_json
from kartograf.catalog.spec import (
    Command,
    Constraint,
    Example,
    Param,
    resolve,
)
from kartograf.cli._parser import create_parser
from kartograf.exceptions import ValidationError
from kartograf.project.commands import COMMANDS

# =============================================================================
# example_for: the example of an error hint (spec 6.3, part (b))
# =============================================================================

_DECLARED = declared()
_CLI_WITH_EXAMPLES = [
    (command, param)
    for command in _DECLARED.commands
    if command.examples
    for param in command.params
]


def _lines(command_id: str) -> list[str]:
    """The command lines of the examples of a command, as the catalog gives them."""
    (command,) = command_schema(command_id).commands
    return [example.call for example in command.examples]


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
    assert example_for("sheet parse", "sheet", {"product": "x"}) == (
        None,
        "kartograf sheet parse N-34-130-D-d-2-4",
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


def _example_of(command, option, **given):
    """The flags of the example line of the hint of a failed call: ``{flag: the
    word after it}`` (a flag without a value maps to the next flag)."""
    line = example_for(command, option, given)[1]
    assert line is not None
    words = line.split()
    return {word: words[i + 1] for i, word in enumerate(words[:-1]) if word[:2] == "--"}


def test_example_for_elevation_and_imagery_is_of_the_country_and_mode_of_the_call():
    # E2E 0.8.0 N-P3-2: a PL NMT area got a CZ cutout, a CZ LAZ the PL LAZ line
    # (no --model) and a PL sheet list of orthophotos the cutout example
    sheets = _example_of("elevation download", "bbox", product="nmt", country="pl")
    cutout = _example_of(
        "elevation download", "bbox", product="nmt", country="pl", cutout=True
    )
    model = _example_of("elevation download", "model", product="laz", country="cz")
    density = _example_of(
        "elevation download", "min_density", product="laz", country="cz"
    )
    orto_cz = _example_of("imagery download", "bbox", product="orto", country="cz")
    orto_sheets = _example_of(
        "imagery download", "bbox", product="orto", country="pl", cutout=False
    )
    orto_cutout = _example_of(
        "imagery download", "bbox", product="orto", country="pl", cutout=True
    )

    assert (
        sheets["--country"] == "pl" and "--bbox" in sheets and "--cutout" not in sheets
    )
    assert cutout["--country"] == "pl" and "--cutout" in cutout and "--bbox" in cutout
    for words in (model, density):
        assert words["--country"] == "cz" and "--model" in words
    assert orto_cz["--country"] == "cz" and "--bbox" in orto_cz
    assert orto_sheets["--country"] == "pl" and "--cutout" not in orto_sheets
    assert orto_cutout["--country"] == "pl" and "--cutout" in orto_cutout


def test_example_for_positional_and_unknown_arguments():
    # a positional argument has no flag; its example shows the value
    assert example_for("sheet parse", "sheet") == (
        None,
        "kartograf sheet parse N-34-130-D-d-2-4",
    )
    # an unknown argument has no flag; the first example of the command is shown
    assert example_for("sheet find", "scale")[0] == "--scale"
    assert example_for("sheet find", "nope") == (
        None,
        example_for("sheet find", "bbox")[1],
    )
    # an argument the only example of a command does not show: its first example
    assert example_for("project status", "project_dir") == (
        "--project",
        "kartograf project status",
    )


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
    "sheet",
    "soil",
    "store",
    "cache",
    "commands",
    "config",
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
    exclusive groups of the declarations - and no other flag."""
    leaves = dict(_leaf_parsers(create_parser()))
    commands = {c.id: c for c in _DECLARED.commands}

    assert len(commands) == 43 and set(leaves) == set(commands)
    for command_id, command in commands.items():
        leaf = leaves[command_id]
        expected_flags = {
            flag for p in command.params for flag in (p.cli_flag, p.short) if flag
        }
        flags = {
            flag
            for action in leaf._actions
            for flag in action.option_strings
            if flag not in ("-h", "--help")
        }
        assert flags == expected_flags, command_id
        exclusive = {
            frozenset(p.cli_dest for p in command.params if p.exclusive == name)
            for name in {p.exclusive for p in command.params if p.exclusive}
        }
        assert _exclusive_groups(leaf) == exclusive, command_id
        positional = list(leaf._get_positional_actions())
        assert [a.dest for a in positional] == [
            p.name for p in command.params if p.positional
        ], command_id
        for param in command.params:
            if param.positional:
                action = next(a for a in positional if a.dest == param.name)
                nargs = {"REMAINDER": argparse.REMAINDER}.get(
                    param.nargs or "", param.nargs
                )
                assert action.nargs == nargs, (command_id, param.name)
                continue
            if param.cli_flag is None:
                continue
            action = leaf._option_string_actions[param.cli_flag]
            where = (command_id, param.name)
            assert action.dest == param.cli_dest, where
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
            if param.choices:
                assert action.choices is not None
                assert list(action.choices) == list(resolve(param.allowed) or ()), where
            else:
                assert action.choices is None, where


def test_data_commands_are_the_twelve_in_COMMANDS_order():
    commands = [c for c in _DECLARED.commands if c.project_task]

    assert [c.id for c in commands] == list(COMMANDS)
    assert len(commands) == 12
    for command in commands:
        names = {p.name for p in command.params}
        # the options of a task and the flags of a run
        assert {"output_dir", "update"} <= names
        assert {p.name for p in command.params if p.task} == set(
            COMMANDS[command.id].options
        )
        assert command.examples


def test_the_list_has_every_group_and_command():
    document = list_commands()

    assert [g.name for g in document.groups] == list(_GROUPS)
    assert [c.name for c in document.commands] == [c.id for c in _DECLARED.commands]
    assert len(document.commands) == 43
    for group in document.groups:
        assert [c.name for c in document.commands if c.name.startswith(group.name)]
    assert {c.name for c in document.commands if "core" in c.families} == {
        "elevation download",
        "elevation availability",
        "imagery download",
        "landcover download",
        "soil download",
        "soil hsg",
        "commands list",
        "commands schema",
        "sheet find",
        "store overview",
    }


def test_the_list_is_a_short_and_complete_list_of_groups_products_and_commands():
    """What an agent reads first is within the page budget (DOC-1.7: 20,000
    characters, also indented as the CLI prints it) and nothing is lost: every group
    with its products and every command with its summary is in it, the options are
    one query away."""
    document = list_commands()
    data = document.to_dict()

    assert len(document.to_json(indent=None)) <= 20_000
    assert len(document.to_json()) <= 20_000
    assert [g["name"] for g in data["groups"]] == list(_GROUPS)  # type: ignore[attr-defined]
    for group, declared_group in zip(
        document.groups,
        sorted(_DECLARED.groups, key=lambda g: (g.position, g.name)),
        strict=True,
    ):
        assert group.products == tuple(n for n, _ in resolve(declared_group.products))
        assert group.summary == declared_group.summary
    for row in document.commands:
        full = command_schema(row.name).commands[0]
        assert (row.operation_id, row.summary, row.check) == (
            full.operation_id,
            full.summary,
            full.check,
        )
        assert row.read_only == full.effects.read_only
        # what left the list: the options, the rules, the examples
        assert full.options is not None and full.examples


def test_a_command_is_found_by_its_name_and_by_its_operation_id():
    for command in _DECLARED.commands:
        by_name = command_schema(command.id)
        by_operation = command_schema(command.operation_id)

        assert by_name == by_operation
        assert by_name.commands[0].name == command.id
    with pytest.raises(ValidationError) as unknown:
        command_schema("sheet nope")

    assert unknown.value.option == "command"
    assert unknown.value.allowed == tuple(c.id for c in _DECLARED.commands)


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
        "kartograf.catalog.list_commands()\n"
        "kartograf.catalog.command_schema('elevation download')\n"
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
        cwd=Path(__file__).resolve().parent.parent.parent,
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
