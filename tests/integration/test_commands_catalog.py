"""The command layer drives every command of the catalog (AGI-2.1).

``parse_command``, ``validate_command``, ``format_command``, ``run_command`` and
``check_command`` take any command of ``kartograf commands list``, not only the data
commands of a project task: what they call, check and write comes from the declaration
of the command (``kartograf.catalog``). The tests run every command through the layer
and against the CLI (the envelope ``--json`` prints), and check the checks against
the declarations themselves.
"""

import json
import shlex
from pathlib import Path
from typing import Any

import pytest

from kartograf import (
    UpdatePlan,
    ValidationError,
    check_command,
    command_schema,
    format_command,
    init_project,
    init_store,
    list_commands,
    parse_command,
    run_command,
    validate_command,
)
from kartograf.catalog.build import allowed_values, command_entries, declared_options
from kartograf.catalog.commands import declared
from kartograf.catalog.formatting import example_command_line
from kartograf.catalog.spec import RUN_OPTIONS, TARGET_OPTIONS, Command
from kartograf.cli import main
from kartograf.exceptions import (
    ConflictError,
    InvalidLayoutError,
    StoreUnavailableError,
)
from kartograf.marker import MARKER, store_refusal
from kartograf.project.commands import COMMANDS
from kartograf.testing import build_fixture_store
from tests.contract.test_cli_json import OFFLINE, _json_add, _offline_lines, _project
from tests.support.project_fixtures import pl_sheets

CATALOG = {command.id: command for command in declared().commands}
# What runs offline has a command line in the CLI tests of ``--json``. The other
# commands are the twelve data commands (``test_commands_layer``, the parity tests)
# and ``elevation availability`` (``test_availability``, ``test_cli_json``).
NETWORK = {"elevation availability", *COMMANDS}
PLANNED = {command.id for command in CATALOG.values() if command.check_function}
# The commands that the generic check of a call applies to: the data commands of a
# project task have the checks of their own function.
GENERIC = [c for c in CATALOG.values() if not c.project_task]


def _targets(run: dict[str, object]) -> dict[str, Any]:
    """The write targets of a parsed line, as the keywords of the command layer."""
    return {name: run[name] for name in TARGET_OPTIONS if name in run}


def _environment(base: Path) -> dict[str, list[str]]:
    """A project and a store in ``base``: the line of every offline command."""
    base.mkdir()
    return _offline_lines(_project(base), base)


def _named(text: str, base: Path) -> object:
    """The document of a text with the directory of its run named."""
    return json.loads(text.replace(str(base), "<base>"))


def _base(command: Command) -> dict[str, object]:
    """The options of the first example of a command: a valid call."""
    line = example_command_line(command, command.examples[0])
    return dict(parse_command(line).options)


def test_every_command_of_the_catalog_is_driven_by_a_test():
    assert set(OFFLINE) | NETWORK == set(CATALOG)
    assert not set(OFFLINE) & NETWORK


@pytest.mark.usefixtures("frozen_clock")
@pytest.mark.parametrize("command", OFFLINE)
def test_run_command_gives_the_envelope_the_cli_prints(
    command, tmp_path, monkeypatch, capsys
):
    """The document of every read-only command, the marker of ``store init`` and the
    commands of a project: ``run_command`` of the line the CLI is given has the
    envelope ``--json`` prints (two copies of the project and of the store)."""
    monkeypatch.chdir(tmp_path)
    cli_lines = _environment(tmp_path / "cli")
    api_lines = _environment(tmp_path / "api")
    argv = cli_lines[command]
    with pl_sheets():
        code = main(_json_add(argv) if command == "project add" else [*argv, "--json"])
    printed = capsys.readouterr().out
    call = parse_command(api_lines[command])
    with pl_sheets():
        envelope = run_command(call.command, call.options, **_targets(call.run))

    assert (envelope.command, envelope.check) == (command, False)
    assert envelope.exit_code == code
    assert _named(envelope.to_json(), tmp_path / "api") == _named(
        printed, tmp_path / "cli"
    )


@pytest.mark.parametrize("command", OFFLINE)
def test_validate_and_format_command_take_the_line_of_every_offline_command(
    command, tmp_path
):
    call = parse_command(_environment(tmp_path / "base")[command])

    assert validate_command(call.command, call.options, **_targets(call.run)) is None
    line = format_command(call.command, call.options, run=call.run)
    assert shlex.split(line)[:3] == ["kartograf", *command.split()]
    assert parse_command(line) == call


@pytest.mark.parametrize("command", list(CATALOG.values()), ids=lambda c: c.id)
def test_every_example_of_the_catalog_is_a_call_of_the_layer(command):
    """The line of each declared example is read and accepted: the options of a call
    are options of the schema of the command."""
    names = {option.name for option in declared_options(command)}
    assert command.examples
    for example in command.examples:
        call = parse_command(example_command_line(command, example))

        assert call.command == command.id
        assert set(call.options) <= names
        assert (
            validate_command(call.command, call.options, **_targets(call.run)) is None
        )


# -- check_command: the plan of the commands that have one -----------------------------


@pytest.mark.parametrize("command", [c for c in CATALOG if c not in PLANNED])
def test_check_command_of_a_command_without_a_check_is_a_validation_error(command):
    with pytest.raises(ValidationError) as caught:
        check_command(command, {})

    error = caught.value
    assert (error.reason, error.option) == ("no_check", "check")
    assert command in str(error)
    assert error.hint and "check" in error.hint


def test_the_commands_with_a_plan_are_the_ones_that_say_check_in_the_catalog():
    listed = {row.name: row.check for row in list_commands().commands}
    entry = command_schema("store init").commands[0]

    assert {name for name, check in listed.items() if check} == PLANNED
    assert {*COMMANDS, "project download", "store init"} == PLANNED
    assert (entry.check, entry.function) == ("store init", "init_store")
    assert "check" in {option.name for option in entry.options}


# -- store init: the marker is written, check plans it -----------------------------


@pytest.mark.usefixtures("frozen_clock")
def test_store_init_writes_the_marker_and_check_plans_it_without_writing(tmp_path):
    root = tmp_path / "data"

    planned = check_command("store init", {}, root=root)

    assert not root.exists()
    assert (planned.command, planned.check, planned.status) == (
        "store init",
        True,
        "ok",
    )
    assert isinstance(planned.result, UpdatePlan)
    assert (planned.result.mode, planned.result.root) == ("store", str(root))
    (item,) = planned.result.items
    assert (item.track, item.name, item.status, item.action) == (
        "store",
        MARKER,
        "missing",
        "write",
    )
    assert item.path == root / MARKER

    written = run_command("store init", {}, root=root)

    assert (root / MARKER).is_file()
    assert (written.command, written.check, written.status) == (
        "store init",
        False,
        "ok",
    )
    assert written.result.created is True  # type: ignore[attr-defined]
    assert written.result.marker == root / MARKER  # type: ignore[attr-defined]

    again = check_command("store init", {}, root=root)
    repeated = run_command("store init", {}, root=root)

    assert isinstance(again.result, UpdatePlan)
    assert [(i.status, i.action) for i in again.result.items] == [("current", None)]
    assert repeated.result.created is False  # type: ignore[attr-defined]


def test_check_command_of_store_init_plans_a_layout_that_run_command_marks(tmp_path):
    root = tmp_path / "old"
    build_fixture_store(root)
    (root / MARKER).unlink()
    assert isinstance(store_refusal(root), StoreUnavailableError)  # no_marker

    planned = check_command("store init", {}, root=root)
    run_command("store init", {}, root=root)

    assert isinstance(planned.result, UpdatePlan)
    assert [(i.status, i.action) for i in planned.result.items] == [
        ("missing", "write")
    ]
    assert not (root / "kartograf-store.json.tmp").exists()
    assert store_refusal(root) is None


def test_check_command_of_store_init_lists_a_conflict_and_raises_the_rest(tmp_path):
    """DEV-19.10: the plan lists a root that is a ``conflict`` as its one position (the
    plan is ``ok``, nothing is asked); the run and any other refusal raise."""
    other = tmp_path / "other"
    other.mkdir()
    (other / "notes.txt").write_text("not a store", encoding="utf-8")
    store = tmp_path / "store"
    init_store(store)
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / MARKER).write_text("{}", encoding="utf-8")

    plans = {
        "not_empty": check_command("store init", {}, root=other),
        "nested_store": check_command("store init", {}, root=store / "inner"),
    }
    for reason, root in (("not_empty", other), ("nested_store", store / "inner")):
        with pytest.raises(ConflictError) as refused:
            run_command("store init", {}, root=root)
        planned = plans[reason]

        assert refused.value.reason == reason
        assert isinstance(planned.result, UpdatePlan)
        (item,) = planned.result.items
        assert (planned.status, planned.exit_code) == ("ok", 0)
        assert (item.track, item.action, item.reason) == ("store", "conflict", reason)
        assert item.path == root.resolve()
    with pytest.raises(InvalidLayoutError):
        check_command("store init", {}, root=broken)
    with pytest.raises(InvalidLayoutError):
        run_command("store init", {}, root=broken)
    assert not (store / "inner").exists() and not (other / MARKER).exists()


@pytest.mark.parametrize("function", [validate_command, run_command, check_command])
def test_store_init_is_store_only_in_every_function(function, tmp_path):
    with pytest.raises(ValidationError) as caught:
        function("store init", {}, output_dir=tmp_path / "plain")

    error = caught.value
    assert (error.reason, error.option) == ("store_only_option", "output_dir")
    assert "--root" in str(error.hint)
    assert list(tmp_path.iterdir()) == []


# -- the options of a call, read from the declaration ----------------------------------


@pytest.mark.parametrize("command", list(CATALOG.values()), ids=lambda c: c.id)
def test_the_options_of_a_call_are_the_arguments_that_are_no_target_or_run_option(
    command,
):
    names = {param.name for param in command.call_options}

    assert not names & {*TARGET_OPTIONS, *RUN_OPTIONS}
    assert all(param.fixed is None for param in command.call_options)
    if command.project_task:
        assert names == set(command.task_options)
    # every option can be written on a line: as a flag, as a word, or - the data
    # command of ``project add`` - as the words after the task name
    for param in command.call_options:
        assert param.cli_flag or param.positional or command.id == "project add"


@pytest.mark.parametrize("command", GENERIC, ids=lambda c: c.id)
def test_an_unknown_option_or_a_target_the_command_has_not_is_refused(command):
    base = _base(command)
    has = {param.name for param in command.params}

    with pytest.raises(ValidationError) as unknown:
        validate_command(command.id, {**base, "no_such_option": 1})
    with pytest.raises(ValidationError) as flag:
        validate_command(command.id, {**base, "json": True})  # a flag, no option
    assert unknown.value.option == "no_such_option"
    assert flag.value.option == "json"
    for name in TARGET_OPTIONS:
        if name not in has:
            with pytest.raises(ValidationError) as target:
                validate_command(command.id, base, **{name: "x"})

            assert target.value.option == name


@pytest.mark.parametrize("command", GENERIC, ids=lambda c: c.id)
def test_a_required_option_is_required(command):
    base = _base(command)

    for param in command.call_options:
        if not param.required:
            continue
        with pytest.raises(ValidationError) as caught:
            validate_command(
                command.id, {k: v for k, v in base.items() if k != param.name}
            )

        assert caught.value.option == param.name
        assert param.name in str(caught.value) and command.id in str(caught.value)


WRONG = {
    "str": 5,
    "int": "7",
    "flag": "yes",
    "path": "",
    "str_list": "a,b",
    "bbox": [1, 2, 3],
    "options": "x",
}


@pytest.mark.parametrize("command", GENERIC, ids=lambda c: c.id)
def test_a_value_of_the_wrong_kind_is_refused_by_the_name_of_its_option(command):
    base = _base(command)

    for param in command.call_options:
        if param.kind not in WRONG:
            continue
        call = {**base, param.name: WRONG[param.kind]}
        if param.kind == "bbox":
            call["bbox_crs"] = "EPSG:2180"
        with pytest.raises(ValidationError) as caught:
            validate_command(command.id, call)

        assert caught.value.option == param.name, (command.id, param.kind)


@pytest.mark.parametrize("command", GENERIC, ids=lambda c: c.id)
def test_an_option_is_limited_to_its_allowed_values_and_its_bounds(command):
    options = {
        option.name: option
        for entry in command_entries()
        if entry.name == command.id
        for option in entry.options
    }
    # the area of a call with a ``bbox_crs`` is one bbox, whatever the example had
    area = {k: v for k, v in _base(command).items() if k not in ("sheet", "geometry")}
    base = {**area, "bbox": [565000, 242000, 566000, 243000], "bbox_crs": "EPSG:2180"}
    base = base if "bbox" in {p.name for p in command.call_options} else area

    for param in command.call_options:
        values = allowed_values(command, options[param.name])
        if values is not None and param.kind in ("str", "int", "bbox_crs"):
            outside = -12345 if param.kind == "int" else "no-such-value"
            with pytest.raises(ValidationError) as caught:
                validate_command(command.id, {**base, param.name: outside})

            assert caught.value.option == param.name
            assert caught.value.allowed == tuple(str(v) for v in values)
        if param.kind == "int" and param.minimum is not None:
            with pytest.raises(ValidationError) as low:
                validate_command(command.id, {**base, param.name: param.minimum - 1})

            assert low.value.option == param.name
            assert str(param.minimum) in str(low.value)


def test_the_rules_among_the_options_of_a_command_are_checked():
    area = {"scale": "1:10000", "sheet_system": "1992"}
    box = {"bbox": [565000, 242000, 566000, 243000], "bbox_crs": "EPSG:2180"}
    sheet = {"product": "nmt", "sheet": "N-34-130-D-d-2-4"}
    broken = [
        ("sheet find", area, ("bbox", "geometry")),  # none of the area
        ("sheet find", {**area, **box, "geometry": "a.gpkg"}, ("bbox", "geometry")),
        ("sheet find", {**area, **box, "layer": "x"}, ("layer", "geometry")),
        ("elevation availability", {"product": "nmt"}, ("sheet", "bbox", "geometry")),
        ("elevation availability", {**sheet, **box}, ("sheet", "bbox", "geometry")),
        (
            "elevation availability",
            {**sheet, "year": 2022, "min_year": 2020},
            ("year", "min_year", "max_year"),
        ),
    ]
    for command, options, names in broken:
        with pytest.raises(ValidationError) as caught:
            validate_command(command, options)

        assert caught.value.options == names, (command, options)
    validate_command("sheet find", {**area, **box})
    validate_command("sheet find", {**area, "geometry": "a.gpkg", "layer": "x"})
    validate_command("elevation availability", {**sheet, "year": 2022})
    # the kinds of rule that the declarations use outside the data commands: a new
    # one is tested above
    assert {c.type for command in GENERIC for c in command.constraints} == {
        "one_of",
        "excludes",
        "requires",
    }


# -- the targets and the options of a run ----------------------------------------------


def test_a_target_and_the_options_of_a_run_are_given_by_name(tmp_path):
    root = tmp_path / "store"
    init_store(root)

    overview = run_command("store overview", {}, root=root)
    with pytest.raises(ValidationError) as in_options:
        run_command("store overview", {"root": str(root)})
    with pytest.raises(ValidationError) as twice:
        run_command("store overview", {}, root=root, output_dir=root)
    with pytest.raises(ValidationError) as no_summary:
        run_command("store overview", {}, root=root, summary=True)
    with pytest.raises(ValidationError) as no_workers:
        run_command("store overview", {}, root=root, workers=2)
    with pytest.raises(ValidationError) as low:
        run_command("project download", {"project_dir": "."}, workers=0)
    with pytest.raises(ValidationError) as mode:
        run_command("project download", {"project_dir": "."}, update="check")  # type: ignore[arg-type]

    assert overview.result.root == root  # type: ignore[attr-defined]
    assert in_options.value.option == "root"
    assert (twice.value.reason, twice.value.option) == ("exclusive_options", "root")
    assert (no_summary.value.option, no_workers.value.option) == ("summary", "workers")
    assert (low.value.option, mode.value.option) == ("workers", "update")


def test_a_command_is_known_by_its_name_or_its_operation_id():
    named = run_command("sheet parse", {"sheet": "N-34-130-D"})
    by_id = run_command("kartograf_sheet_parse", {"sheet": "N-34-130-D"})

    assert by_id.command == "sheet parse"
    assert by_id.to_dict() == named.to_dict()
    assert format_command("kartograf_sheet_parse", {"sheet": "N-34-130-D"}) == (
        "kartograf sheet parse N-34-130-D"
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda name: validate_command(name, {}),
        lambda name: format_command(name, {}),
        lambda name: run_command(name, {}, root="."),
        lambda name: check_command(name, {}, root="."),
    ],
    ids=["validate", "format", "run", "check"],
)
def test_an_unknown_command_names_the_commands_of_the_catalog(call):
    with pytest.raises(ValidationError) as caught:
        call("no such command")

    assert caught.value.option == "command"
    assert caught.value.allowed == tuple(CATALOG)


# -- project add: its task is a data command carried as ``command`` and ``options`` ----


def test_project_add_is_one_call_of_the_layer_in_both_directions():
    words = (
        "teren elevation download --product nmt --sheet N-34-130-D-d-2-4 "
        "--resolution 1m --vertical-crs EVRF2007"
    )
    options = {
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
    }

    call = parse_command(f"project add --project p {words}")

    assert call.command == "project add" and call.run == {}
    assert call.options == {
        "project_dir": "p",
        "name": "teren",
        "command": "elevation download",
        "options": options,
    }
    line = format_command(call.command, call.options)
    assert line == f"kartograf project add --project p {words}"
    assert parse_command(line) == call
    validate_command(call.command, call.options)
    with pytest.raises(ValidationError) as nested:
        validate_command(call.command, {**call.options, "options": {"product": "x"}})
    assert nested.value.option == "product"


@pytest.mark.parametrize(
    ("line", "option"),
    [
        ("project add t sheet parse N-34", "command"),
        ("project add t elevation download --product nmt --upgrade", "upgrade"),
        ("project add t elevation download --product nmt --root ./data", "root"),
        ("project add t elevation download --product nmt --json", "json"),
    ],
)
def test_project_add_takes_only_a_data_command_without_the_flags_of_a_run(line, option):
    with pytest.raises(ValidationError) as caught:
        parse_command(line)

    assert caught.value.option == option


def test_project_add_and_remove_change_the_manifest_as_run_command(tmp_path):
    project = tmp_path / "project"
    init_project(project, root=tmp_path / "store")
    task = {
        "project_dir": str(project),
        "name": "teren",
        "command": "elevation download",
        "options": {
            "product": "nmt",
            "sheet": "N-34-130-D-d-2-4",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
        },
    }

    added = run_command("project add", task)
    removed = run_command(
        "project remove", {"project_dir": str(project), "name": "teren"}
    )

    assert [t.name for t in added.result.tasks] == ["teren"]  # type: ignore[attr-defined]
    assert removed.result.tasks == ()  # type: ignore[attr-defined]
    assert added.to_dict()["result"]["schema"] == "kartograf-project-state/1"
