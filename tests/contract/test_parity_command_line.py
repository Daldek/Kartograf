"""CLI and public API read and write the same line of a call (``commands parse`` and
``commands format``, ADR-063 decision 6): the text the CLI prints, the envelope of
``--json``, the call through the command layer and the error of a broken input."""

import json

import pytest

from kartograf import (
    ValidationError,
    read_command_line,
    run_command,
    write_command_line,
)
from kartograf.cli import main
from kartograf.envelope import wrap
from kartograf.error_report import error_report

LINE = (
    "kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4"
    " --resolution 1m --vertical-crs EVRF2007 --root ./data --upgrade -w 4"
)
OPTIONS = {
    "product": "nmt",
    "sheet": "N-34-130-D-d-2-4",
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
    "root": "./data",
    "update": "upgrade",
    "workers": 4,
}


def _cli(argv, capsys) -> tuple[int, str, str]:
    code = main(["commands", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_parse_prints_the_line_and_the_document_of_the_library(capsys):
    code, out, err = _cli(["parse", "--line", f"{LINE} --json -q"], capsys)
    json_code, envelope, _ = _cli(["parse", "--line", LINE, "--json"], capsys)

    document = read_command_line(LINE)
    layer = run_command("commands parse", {"line": LINE})
    assert (code, err, json_code) == (0, "", 0)
    assert out == f"{document.line}\n" == f"{LINE}\n"
    assert envelope == wrap("commands parse", document).to_json() == layer.to_json()


def test_format_prints_the_line_and_the_document_of_the_library(capsys):
    argv = ["format", "--command", "elevation download"]
    argv += ["--options", json.dumps(OPTIONS)]

    code, out, err = _cli(argv, capsys)
    json_code, envelope, _ = _cli([*argv, "--json"], capsys)

    document = write_command_line("elevation download", options=OPTIONS)
    layer = run_command(
        "commands format", {"command": "elevation download", "options": OPTIONS}
    )
    assert (code, err, json_code) == (0, "", 0)
    assert out == f"{document.line}\n" == f"{LINE}\n"
    assert envelope == wrap("commands format", document).to_json() == layer.to_json()


def test_format_without_options_is_the_bare_command(capsys):
    code, out, _ = _cli(["format", "--command", "cache stats"], capsys)

    assert code == 0
    assert (
        out
        == f"{write_command_line('cache stats').line}\n"
        == "kartograf cache stats\n"
    )


@pytest.mark.parametrize(
    ("options", "option"),
    [
        ({"product": "nmt", "teryt": "1465"}, "teryt"),
        ({"product": "nmt", "plan": {"schema": "kartograf-plan/1"}}, "plan"),
    ],
    ids=["foreign-option", "plan-document"],
)
def test_format_refuses_what_the_library_refuses_with_its_error(
    options, option, capsys
):
    argv = ["format", "--command", "elevation download"]
    argv += ["--options", json.dumps(options), "--json"]

    code, out, err = _cli(argv, capsys)

    with pytest.raises(ValidationError) as caught:
        write_command_line("elevation download", options=options)
    expected = error_report(caught.value).to_dict()
    printed = json.loads(err.splitlines()[-1])
    assert out == ""
    assert code == expected["exit_code"]
    assert printed["details"]["option"] == option
    assert {k: printed[k] for k in ("code", "message", "details")} == {
        k: expected[k] for k in ("code", "message", "details")
    }


def test_format_options_that_are_no_json_object_are_refused_as_options(capsys):
    argv = ["format", "--command", "cache stats", "--options", "[1, 2]", "--json"]

    code, out, err = _cli(argv, capsys)

    printed = json.loads(err.splitlines()[-1])
    assert (code, out) == (2, "")
    assert (printed["code"], printed["details"]["option"]) == (
        "validation_error",
        "options",
    )
