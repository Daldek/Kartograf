"""The command layer of the library (spec 8.7; KB-2..KB-5): ``parse_command``,
``validate_command``, ``format_command``, ``run_command``, ``check_command``."""

import json
import shlex
import socket
from pathlib import Path
from typing import Any

import pytest

from kartograf import (
    CommandCall,
    UpdatePlan,
    ValidationError,
    calculate_hsg,
    check_command,
    check_data,
    data_commands,
    download_data,
    format_command,
    parse_command,
    run_command,
    validate_command,
)
from kartograf.exceptions import UsageError
from kartograf.project.commands import COMMANDS, data_commands_text
from kartograf.serialization import encode
from tests.project_fixtures import (
    HSG_SHEET,
    PL_SHEET,
    G,
    landcover_sources,
    pl_sheets,
)
from tests.test_hsg import RasterSoilGrids
from tests.test_manager_campaigns import REC, FakeCampaignProvider

LINE = (
    "elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m "
    "--vertical-crs EVRF2007 -o ./data"
)
NMT = "elevation download --product nmt"


def test_parse_command_returns_only_given_options():
    expected = CommandCall(
        "elevation download",
        {
            "product": "nmt",
            "sheet": "N-34-130-D-d-2-4",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
        },
        {"output_dir": "./data"},
    )

    assert parse_command(LINE) == expected
    assert parse_command(shlex.split(LINE)) == expected


def test_parse_command_writes_the_json_form_of_every_kind():
    area = parse_command(
        f"{NMT} --resolution pl=1m,cz=2m --cutout --year 2024 --geometry rel/a.gpkg"
        " --layer zlewnia"
    )
    layers = parse_command(
        "landcover download --product bdot10k --teryt 1465 --layers SWRS,PTWP"
        " --keep-raw"
    )

    assert area.options == {
        "product": "nmt",
        "resolution": {"pl": "1m", "cz": "2m"},
        "cutout": True,
        "year": 2024,
        "geometry": "rel/a.gpkg",
        "layer": "zlewnia",
    }
    assert layers.options == {
        "product": "bdot10k",
        "teryt": "1465",
        "layers": ["SWRS", "PTWP"],
        "keep_raw": True,
    }


def test_parse_command_bbox_always_comes_with_crs():
    default = parse_command(f"{NMT} --bbox 450000,550000,451000,551000")
    degrees = parse_command(f"{NMT} --bbox 18.6,49.7,18.7,49.8 --bbox-crs EPSG:4326")
    negative = parse_command(
        [
            *NMT.split(),
            "--bbox",
            "-447000,-1114000,-446000,-1113000",
            "--bbox-crs",
            "EPSG:5514",
        ]
    )

    assert default.options["bbox"] == [450000, 550000, 451000, 551000]
    assert default.options["bbox_crs"] == "EPSG:2180"
    assert degrees.options["bbox"] == [18.6, 49.7, 18.7, 49.8]
    assert degrees.options["bbox_crs"] == "EPSG:4326"
    assert negative.options["bbox"] == [-447000, -1114000, -446000, -1113000]
    assert negative.options["bbox_crs"] == "EPSG:5514"
    # a crs without an area is a mistake, not an option of the task
    with pytest.raises(ValidationError) as lone:
        parse_command(f"{NMT} --sheet {G} --bbox-crs EPSG:4326")

    assert not isinstance(lone.value, UsageError)
    assert lone.value.option == "bbox_crs"
    assert lone.value.options == ("bbox", "bbox_crs")
    assert "--bbox-crs" in str(lone.value) and "--bbox" in str(lone.value)


def test_parse_command_bbox_with_a_wrong_number_of_values_is_a_validation_error():
    with pytest.raises(ValidationError) as caught:
        parse_command(f"{NMT} --bbox 1,2,3")

    assert not isinstance(caught.value, UsageError)
    assert "bbox" in str(caught.value)


def test_parse_command_distinguishes_given_workers():
    without = parse_command(f"{NMT} --sheet {G}")
    default = parse_command(f"{NMT} --sheet {G} -w 4")
    other = parse_command(f"{NMT} --sheet {G} --workers=8")

    assert "workers" not in without.run
    assert default.run == {"workers": 4}
    assert other.run == {"workers": 8}


def test_parse_command_puts_the_flags_of_the_run_apart_from_the_options():
    call = parse_command(f"{NMT} --sheet {G} --upgrade --plan p.json -q --json")

    assert call.options == {"product": "nmt", "sheet": G}
    assert call.run == {"upgrade": True, "plan": "p.json", "quiet": True, "json": True}


@pytest.mark.parametrize(
    "line",
    [
        "",
        "frobnicate",
        "elevation",
        "elevation download --nope",
        "elevation download --product",
        "elevation download --bbox-crs EPSG:9999",
        "elevation download --check-updates --upgrade",
        f"{NMT} --help",
        "--version",
        "download --product nmt",
        "elevation download 'unclosed",
    ],
    ids=[
        "empty",
        "unknown-command",
        "group-without-command",
        "unknown-flag",
        "flag-without-value",
        "value-outside-choices",
        "exclusive-flags",
        "help",
        "version",
        "removed-command",
        "unbalanced-quote",
    ],
)
def test_parse_command_syntax_error_is_usage_error(line):
    with pytest.raises(UsageError) as caught:
        parse_command(line)

    assert caught.value.code == "usage_error" and caught.value.exit_code == 2


@pytest.mark.parametrize(
    ("line", "command"),
    [
        ("elevation download --nope", "elevation download"),
        ("elevation download --product", "elevation download"),
        ("soil hsg --depth 0-5cm --stats", "soil hsg"),
        (f"{NMT} --help", "elevation download"),
        ("elevation download 'unclosed", None),
        ("elevation frobnicate", None),
        ("elevation", None),
        ("download --product nmt", None),
        ("", None),
    ],
)
def test_usage_error_names_the_command_the_line_named(line, command):
    with pytest.raises(UsageError) as caught:
        parse_command(line)

    assert caught.value.command == command


@pytest.mark.parametrize(
    "line",
    [
        "parse N-34",
        "parse",
        "catalog",
        "elevation availability --bbox 1,2,3,4",
        "elevation list-sources",
        "soil list-layers",
        "project status",
        "cache stats",
    ],
)
def test_parse_command_rejects_non_data_commands(line):
    with pytest.raises(ValidationError) as caught:
        parse_command(line)

    error = caught.value
    assert not isinstance(error, UsageError)
    assert str(error) == (
        f"do projektu mozna dodac komendy zapisujace dane: {data_commands_text()}"
    )
    assert (error.option, error.allowed) == ("command", tuple(COMMANDS))
    assert len(error.allowed) == 12


def test_validate_command_is_offline_and_names_the_option(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("validate_command opened a connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    store = tmp_path / "not-created"

    assert validate_command("elevation download", PL_SHEET, output_dir=store) is None
    assert validate_command("elevation download", PL_SHEET) is None
    assert not store.exists()
    without_vertical_crs = {k: v for k, v in PL_SHEET.items() if k != "vertical_crs"}
    with pytest.raises(ValidationError) as missing:
        validate_command("elevation download", without_vertical_crs)
    with pytest.raises(ValidationError) as no_area:
        validate_command("elevation download", {"product": "nmt"})
    with pytest.raises(ValidationError) as unknown:
        validate_command("elevation download", {**PL_SHEET, "output_dir": "data"})
    with pytest.raises(ValidationError) as wrong_form:
        validate_command("elevation download", {**PL_SHEET, "year": "2024"})

    assert missing.value.option == "vertical_crs"
    assert no_area.value.options == ("sheet", "bbox", "geometry")
    assert (unknown.value.option, wrong_form.value.option) == ("output_dir", "year")


@pytest.mark.parametrize(
    "call",
    [
        lambda name: validate_command(name, {}),
        lambda name: format_command(name, {}),
        lambda name: run_command(name, {}, output_dir="."),
        lambda name: check_command(name, {}, output_dir="."),
    ],
    ids=["validate", "format", "run", "check"],
)
@pytest.mark.parametrize("name", ["elevation list-sources", "no such command", "parse"])
def test_unknown_command_names_the_option(call, name):
    with pytest.raises(ValidationError) as caught:
        call(name)

    assert caught.value.option == "command"
    assert caught.value.allowed == tuple(COMMANDS)


def test_format_command_rejects_options_that_do_not_belong():
    with pytest.raises(ValidationError) as foreign:
        format_command("elevation download", {"product": "nmt", "teryt": "1465"})
    with pytest.raises(ValidationError) as twice:
        format_command(
            "elevation download",
            {"product": "nmt", "workers": 2},
            run={"workers": 2},
        )

    assert foreign.value.option == "teryt"
    assert twice.value.option == "workers"


@pytest.mark.parametrize(
    ("run", "option", "text"),
    [
        (
            {"workers": "4"},
            "workers",
            "opcja workers: oczekiwano liczba calkowita, podano '4'",
        ),
        (
            {"workers": True},
            "workers",
            "opcja workers: oczekiwano liczba calkowita, podano True",
        ),
        (
            {"upgrade": "tak"},
            "upgrade",
            "opcja upgrade: oczekiwano true, podano 'tak'",
        ),
        (
            {"output_dir": 5},
            "output_dir",
            "opcja output_dir: oczekiwano niepusta sciezka (napis), podano 5",
        ),
        (
            {"plan": {"items": []}},
            "plan",
            "opcja plan: oczekiwano niepusta sciezka (napis), podano {'items': []}",
        ),
        # the library argument ``update`` has no flag: the flags are --upgrade
        # and --force; a task option does not belong among the flags of a run
        ({"update": "upgrade"}, "update", "nieznana opcja 'update'"),
        ({"sheet": G}, "sheet", "nieznana opcja 'sheet'"),
    ],
    ids=[
        "workers-text",
        "workers-bool",
        "flag-text",
        "output-dir-number",
        "plan-document",
        "api-only-update",
        "task-option",
    ],
)
def test_format_command_run_flags_are_validated_like_options(run, option, text):
    with pytest.raises(ValidationError) as caught:
        format_command("elevation download", {"product": "nmt"}, run=run)

    assert caught.value.option == option
    assert str(caught.value).startswith(text)


def test_format_command_writes_the_flags_of_a_valid_run():
    line = format_command(
        "elevation download",
        {"product": "nmt", "sheet": G},
        run={
            "output_dir": Path("data"),
            "plan": "plan.json",
            "workers": 4,
            "upgrade": True,
            "force": False,
            "quiet": None,
        },
    )

    call = parse_command(line[len("kartograf ") :])
    assert call.run == {
        "output_dir": "data",
        "plan": "plan.json",
        "workers": 4,
        "upgrade": True,
    }


_EXAMPLES = [
    pytest.param(command.id, example, id=f"{command.id}#{index}")
    for command in data_commands()
    for index, example in enumerate(command.examples or ())
]


def test_every_data_command_has_catalog_examples():
    assert {p.values[0] for p in _EXAMPLES} == set(COMMANDS)


@pytest.mark.parametrize(("command", "example"), _EXAMPLES)
def test_format_parse_round_trip_for_every_catalog_example(command, example):
    options: dict[str, Any] = encode(example.options)  # type: ignore[assignment]
    run = {"output_dir": "./data"}

    line = format_command(command, options, run=run)
    call = parse_command(line[len("kartograf ") :])

    assert (call.command, call.options, call.run) == (command, options, run)
    assert parse_command(example.command_line[len("kartograf ") :]).options == options
    validate_command(command, options)


def _normal(document, store: Path) -> str:
    """The document as text, with the store directory named."""
    return json.dumps(document.to_dict()).replace(str(store), "<store>")


@pytest.mark.usefixtures("frozen_clock")
def test_run_command_equals_download_data(tmp_path):
    with pl_sheets():
        called = run_command(
            "elevation download", PL_SHEET, output_dir=tmp_path / "a", cache=False
        )
    with pl_sheets():
        direct = download_data(**PL_SHEET, output_dir=tmp_path / "b", cache=False)

    assert [f.file.status for f in called.files] == ["new"]  # type: ignore[attr-defined]
    assert _normal(called, tmp_path / "a") == _normal(direct, tmp_path / "b")


@pytest.mark.usefixtures("frozen_clock")
def test_check_command_equals_check_data(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    with pl_sheets(fake):
        run_command("elevation download", PL_SHEET, output_dir=tmp_path, cache=False)
    fake.records = {"newest": [REC["84183"]]}
    with pl_sheets(fake):
        plan = check_command(
            "elevation download", PL_SHEET, output_dir=tmp_path, cache=False
        )
    with pl_sheets(fake):
        direct = check_data(**PL_SHEET, output_dir=tmp_path, cache=False)

    assert isinstance(plan, UpdatePlan)
    assert [item.status for item in plan.items] == ["newer"]
    assert _normal(plan, tmp_path) == _normal(direct, tmp_path)


@pytest.mark.usefixtures("frozen_clock")
def test_run_command_passes_update_and_plan_to_the_function(tmp_path):
    fake = FakeCampaignProvider({"newest": [REC["83233"]]})
    with pl_sheets(fake):
        run_command("elevation download", PL_SHEET, output_dir=tmp_path, cache=False)
    fake.records = {"newest": [REC["84183"]]}
    with pl_sheets(fake):
        plan = check_command(
            "elevation download", PL_SHEET, output_dir=tmp_path, cache=False
        )
    with pl_sheets(fake):
        kept = run_command(
            "elevation download", PL_SHEET, output_dir=tmp_path, cache=False
        )
        upgraded = run_command(
            "elevation download",
            PL_SHEET,
            output_dir=tmp_path,
            update="upgrade",
            plan=plan,
            cache=False,
        )

    assert [f.file.status for f in kept.files] == ["local"]  # type: ignore[attr-defined]
    (new,) = upgraded.files  # type: ignore[attr-defined]
    assert new.file.status == "new" and new.file.label.startswith("2025-10-21_84183")
    with pl_sheets(fake), pytest.raises(ValidationError) as without_upgrade:
        run_command(
            "elevation download", PL_SHEET, output_dir=tmp_path, plan=plan, cache=False
        )
    assert without_upgrade.value.options == ("plan", "update")


def test_run_command_summary_is_for_soil_hsg_only(tmp_path):
    hsg = {"sheet": HSG_SHEET, "depth": "0-5cm"}
    with landcover_sources(soilgrids=RasterSoilGrids):
        with_summary = run_command(
            "soil hsg", hsg, output_dir=tmp_path / "a", summary=True, cache=False
        )
        without = run_command("soil hsg", hsg, output_dir=tmp_path / "b", cache=False)
    with landcover_sources(soilgrids=RasterSoilGrids):
        direct = calculate_hsg(
            output_dir=tmp_path / "c", cache=False, summary=True, **hsg
        )
    with pytest.raises(ValidationError) as caught:
        run_command("elevation download", PL_SHEET, output_dir=tmp_path, summary=True)

    assert without.summary is None  # type: ignore[attr-defined]
    assert with_summary.summary == direct.summary  # type: ignore[attr-defined]
    assert set(with_summary.summary) == {"A", "B", "C", "D", "nodata"}  # type: ignore[attr-defined]
    assert caught.value.option == "summary"
    assert not (tmp_path / "data").exists()


def test_run_and_check_need_the_store(tmp_path):
    for call in (run_command, check_command):
        with pytest.raises(ValidationError) as caught:
            call("elevation download", PL_SHEET, output_dir="")
        assert caught.value.option == "output_dir"
