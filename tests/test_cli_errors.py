"""``main``: the exit codes 0/1/2/130 and the ``kartograf-error/1`` document of
every kind of failure, in text and in the ``--json`` mode (spec 6.5, 6.6, 7.1)."""

import io
import json
import logging
import sys
from unittest.mock import Mock, patch

import pytest

from kartograf.cli._handlers import HANDLERS
from kartograf.cli.commands import main
from kartograf.commands import parse_command
from kartograf.download.data import DataReport, UnitFailure
from kartograf.download.plan import new_plan
from kartograf.exceptions import DownloadError, UsageError, ValidationError
from kartograf.transform.crs import TransformError, TransformUnavailableError

SHEET = "N-34-130-D-d-2-4"
OUTPUT_REQUIRED = "--output wymagane: katalog magazynu (pliki w <KATALOG>/nmt/...)"
# a complete PL elevation request but for the store (``-o``)
ELEVATION = [
    "elevation",
    "download",
    "--product",
    "nmt",
    "--sheet",
    SHEET,
    "--resolution",
    "1m",
    "--vertical-crs",
    "EVRF2007",
]


def _run(capsys, argv: list[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _handler_fails(error):
    """``kartograf parse`` fails with ``error``: its handler in the registry of
    the CLI is replaced for the length of the ``with`` block."""
    return patch.dict(HANDLERS, {"parse": Mock(side_effect=error)})


# -- text mode ---------------------------------------------------------------


def test_input_error_exits_2_in_text_mode(capsys):
    code, out, err = _run(capsys, ELEVATION)

    assert code == 2
    assert out == ""
    assert err == f"Error: {OUTPUT_REQUIRED}\n"


def test_source_failure_exits_1(capsys, tmp_path):
    failure = DownloadError("HTTP 503 dla https://example.org/zrodlo")
    with patch("kartograf.cli.download_cmd.download_data", side_effect=failure):
        code, out, err = _run(capsys, [*ELEVATION, "-o", str(tmp_path)])

    assert code == 1
    assert err == "Error: HTTP 503 dla https://example.org/zrodlo\n"


def test_ok_false_exits_1(capsys, tmp_path):
    report = DataReport(
        files=(),
        failed=(UnitFailure(SHEET, "PL", "brak odpowiedzi zrodla", "download"),),
        stale=(),
        superseded=(),
        notices=(),
        ok=False,
    )
    with patch("kartograf.cli.download_cmd.download_data", return_value=report):
        code, out, err = _run(capsys, [*ELEVATION, "-o", str(tmp_path)])

    assert code == 1
    assert err == "Error: brak odpowiedzi zrodla\n"


def test_text_usage_error_is_unchanged(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["elevation", "download", "--bogus"])

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.out == ""
    assert captured.err.startswith("usage: kartograf elevation download")
    assert "error: nieznana opcja --bogus" in captured.err


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (
            TransformUnavailableError("brak operacji", remedy="zainstaluj siatki"),
            "Error: brak operacji Remedium: zainstaluj siatki\n",
        ),
        (TransformError("wynik nieskonczony"), "Error: wynik nieskonczony\n"),
    ],
)
def test_transform_failure_exits_1_and_text_has_the_remedy(capsys, error, text):
    """The remedy of an unavailable operation follows the message in every
    command, not only in the downloads of elevation and imagery."""
    with _handler_fails(error):
        code, out, err = _run(capsys, ["parse", "N-34"])

    assert code == 1
    assert out == ""
    assert err == text


# -- the --json mode ---------------------------------------------------------


def test_json_input_error_is_an_error_document(capsys):
    code, out, err = _run(capsys, [*ELEVATION, "--json"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["schema"] == "kartograf-error/1"
    assert document["code"] == "invalid_input"
    assert document["message"] == OUTPUT_REQUIRED
    assert document["exception"] == "ValidationError"
    assert document["exit_code"] == 2
    assert document["command"] == "elevation download"
    assert document["details"] == {"option": "output_dir"}
    # the hint is a command line of the catalog that works as it stands
    example = document["hint"].removeprefix("Przyklad: kartograf ")
    assert example != document["hint"]
    assert parse_command(example).command == "elevation download"


def test_json_input_error_lists_allowed_values_and_an_example(capsys, tmp_path):
    argv = [x for x in ELEVATION if x not in ("--vertical-crs", "EVRF2007")]
    code, out, err = _run(capsys, [*argv, "-o", str(tmp_path), "--json"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["details"] == {
        "option": "vertical_crs",
        "allowed": ["EVRF2007", "KRON86"],
    }
    assert document["hint"].startswith(
        "Dozwolone wartosci --vertical-crs: EVRF2007, KRON86. "
        "Przyklad: kartograf elevation download "
    )


def test_json_argparse_error_is_usage_error(capsys):
    code, out, err = _run(capsys, ["elevation", "download", "--bogus", "--json"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["code"] == "usage_error"
    assert document["exception"] == "UsageError"
    assert document["exit_code"] == 2
    assert "nieznana opcja --bogus" in document["message"]


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--product", "foo"], "invalid choice: 'foo'"),
        (["--bogus"], "nieznana opcja --bogus"),
        (["--product"], "expected one argument"),
    ],
    ids=["value-outside-choices", "unknown-flag", "flag-without-value"],
)
def test_json_usage_error_of_a_known_command_names_it_and_gives_an_example(
    capsys, flags, message
):
    code, out, err = _run(capsys, ["elevation", "download", *flags, "--json"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["code"] == "usage_error"
    assert message in document["message"]
    assert document["command"] == "elevation download"
    where, example = document["hint"].split(" Przyklad: kartograf ", 1)
    assert where == "Parametry komendy: kartograf catalog elevation download."
    assert parse_command(example).command == "elevation download"


def test_json_usage_error_without_a_command_has_the_generic_hint(capsys):
    code, out, err = _run(capsys, ["elevation", "frobnicate", "--json"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["code"] == "usage_error"
    assert document["command"] is None
    assert document["hint"] == UsageError.DEFAULT_HINT


def test_json_usage_error_in_a_task_line_is_about_the_line_not_the_task(
    capsys, tmp_path
):
    argv = ["project", "add", "--json", "--project", str(tmp_path), "teren"]
    code, out, err = _run(capsys, [*argv, "elevation", "download", "--bogus"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["code"] == "usage_error"
    assert document["command"] == "project add"
    assert document["hint"].startswith(
        "Parametry komendy: kartograf catalog elevation download. Przyklad: "
    )


def test_json_removed_command_is_usage_error(capsys):
    code, out, err = _run(capsys, ["download", "--product", "nmt", "--json"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["code"] == "usage_error"
    assert "kartograf elevation download" in document["message"]


def test_json_flag_before_the_command_is_a_usage_error(capsys):
    code, out, err = _run(capsys, ["--json", "elevation", "list-sources"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["code"] == "usage_error"
    # one short hint: where the flag goes, not the list of all 37 commands
    assert "nieznana opcja --json" in document["message"]
    assert "kartograf elevation list-sources --json" in document["message"]
    assert len(document["message"]) < 200


def test_json_parse_error_uses_invalid_sheet_code(capsys):
    code, out, err = _run(capsys, ["parse", "NIE-GODLO", "--json"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["code"] == "invalid_sheet_code"
    assert document["exception"] == "ParseError"
    assert document["command"] == "parse"
    assert document["details"] == {"option": "sheet"}
    assert document["hint"].startswith("Formaty godel: ")


def test_json_interrupt_is_130(capsys):
    with _handler_fails(KeyboardInterrupt):
        code, out, err = _run(capsys, ["parse", "N-34-130-D", "--json"])

    document = json.loads(out)
    assert code == 130 and err == ""
    assert document["code"] == "interrupted"
    assert document["exit_code"] == 130
    assert document["message"] == "przerwano (Ctrl-C)"
    assert document["command"] == "parse"


def test_oserror_is_io_error_in_json_mode(capsys, tmp_path):
    """The plan cannot be written (its path is a directory): the failure of the
    store, not a mistake of the command line - code 1, ``io_error``."""
    plan_file = tmp_path / "plan.json"
    plan_file.mkdir()
    checked = new_plan(tmp_path, [])
    argv = [*ELEVATION, "-o", str(tmp_path), "--check-updates", "--json"]
    with patch("kartograf.cli.download_cmd.check_data", return_value=checked):
        code, out, err = _run(capsys, [*argv, "--plan", str(plan_file)])

    document = json.loads(out)
    assert code == 1 and err == ""
    assert document["code"] == "io_error"
    assert document["exit_code"] == 1
    assert document["exception"] == "IsADirectoryError"
    assert document["details"] == {"errno": "EISDIR", "path": str(plan_file)}


def test_internal_error_in_json_mode_and_debug_reraises(capsys, monkeypatch):
    with _handler_fails(RuntimeError("boom")):
        code, out, err = _run(capsys, ["parse", "N-34", "--json"])

    document = json.loads(out)
    assert code == 1 and err == ""
    assert document["code"] == "internal_error"
    assert document["exception"] == "RuntimeError"
    assert document["message"] == "RuntimeError: boom"
    assert "KARTOGRAF_DEBUG" in document["hint"]

    monkeypatch.setenv("KARTOGRAF_DEBUG", "1")
    with (
        _handler_fails(RuntimeError("boom")),
        pytest.raises(RuntimeError, match="boom"),
    ):
        main(["parse", "N-34", "--json"])
    assert capsys.readouterr().out == ""


def test_json_mode_sets_utf8_stdout(monkeypatch):
    """The document is UTF-8 whatever the locale of the stream (spec 7.1)."""
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="ascii"))
    with _handler_fails(ValidationError("zly znak: \u017c")):
        code = main(["parse", "N-34", "--json"])
    sys.stdout.flush()

    assert code == 2
    assert json.loads(raw.getvalue().decode("utf-8"))["message"] == "zly znak: \u017c"


def test_http_retry_lines_stay_on_stderr(capsys):
    """D6: the retry lines of the HTTP transport are outside the contract of the
    mode - stderr has them, stdout is still the one document."""

    def retried_then_failed(args):
        logging.getLogger("kartograf.transport.http").warning("HTTP 503, ponawiam 1/3")
        raise ValidationError("zle")

    with patch.dict(HANDLERS, {"parse": retried_then_failed}):
        code, out, err = _run(capsys, ["parse", "N-34", "--json"])

    assert code == 2
    assert json.loads(out)["message"] == "zle"
    assert err == "Warning: HTTP 503, ponawiam 1/3\n"


def _skipped_version_listing(tmp_path):
    """A ``parse`` handler listing a version directory with no readable sidecar:
    the library logs "Pominieto wersje bez czytelnego sidecara" for it."""
    from kartograf.download.versions import list_versions

    directory = tmp_path / "versions" / "bbox" / "2026-10-19_0123abcd"
    directory.mkdir(parents=True)
    (directory / "plik.tif").write_bytes(b"x")

    def handler(args):
        assert list_versions(directory.parent, "plik.tif") == []
        raise ValidationError("zle")

    return handler


def test_library_warnings_are_not_on_stderr_in_json_mode(capsys, tmp_path, monkeypatch):
    """USAGE 9.2: with ``--json`` stderr is empty - a library log record (here the
    skipped version of a store listing) is not printed as a bare line."""
    # no handler above the 'kartograf' branch -> logging.lastResort writes to
    # stderr, as in a real CLI run (pytest's root handler would hide it)
    monkeypatch.setattr(logging.getLogger("kartograf"), "propagate", False)
    with patch.dict(HANDLERS, {"parse": _skipped_version_listing(tmp_path)}):
        code, out, err = _run(capsys, ["parse", "N-34", "--json"])

    assert code == 2
    assert json.loads(out)["message"] == "zle"
    assert err == ""


def test_library_warnings_are_prefixed_in_text_mode(capsys, tmp_path, monkeypatch):
    """Text mode: the same record is a ``Warning:`` line, not a bare message."""
    monkeypatch.setattr(logging.getLogger("kartograf"), "propagate", False)
    with patch.dict(HANDLERS, {"parse": _skipped_version_listing(tmp_path)}):
        code, out, err = _run(capsys, ["parse", "N-34"])

    assert code == 2
    lines = err.splitlines()
    assert lines[0].startswith("Warning: Pominieto wersje bez czytelnego sidecara")
    assert lines[1] == "Error: zle"


def test_library_warnings_pass_with_debug_in_json_mode(capsys, tmp_path, monkeypatch):
    """``KARTOGRAF_DEBUG`` lets the library records through also in ``--json``."""
    monkeypatch.setenv("KARTOGRAF_DEBUG", "1")
    with (
        patch.dict(HANDLERS, {"parse": _skipped_version_listing(tmp_path)}),
        pytest.raises(ValidationError),
    ):
        main(["parse", "N-34", "--json"])

    assert capsys.readouterr().err.startswith(
        "Warning: Pominieto wersje bez czytelnego sidecara"
    )


# -- the handlers raise their input errors (no own "Error:" line) -------------


@pytest.mark.parametrize(
    ("argv", "option"),
    [
        (["landcover", "download"], "product"),
        (["landcover", "download", "--product", "corine"], "output_dir"),
        (["landcover", "list-layers"], "product"),
        (["soil", "download"], "output_dir"),
        (["soil", "hsg"], "output_dir"),
        (["parse", "NIE-GODLO"], "sheet"),
        (["parse", "CTES96", "--hierarchy"], "hierarchy"),
        (["parse", "N-34-130-D", "--descendants", "1:77"], "descendants"),
        (["catalog", "nie-ma-takiej-grupy"], "group"),
    ],
)
def test_input_errors_of_the_handlers_name_the_option(capsys, argv, option):
    code, out, err = _run(capsys, [*argv, "--json"])

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["exit_code"] == 2
    assert document["details"]["option"] == option


@pytest.mark.parametrize(
    "plan_error",
    ["unreadable", "foreign_schema", "directory_missing", "no_mode"],
)
def test_plan_file_errors_are_input_errors_of_the_plan(capsys, tmp_path, plan_error):
    store = ["-o", str(tmp_path)]
    plan_file = tmp_path / "plan.json"
    if plan_error == "foreign_schema":
        plan_file.write_text('{"schema": "kartograf-sheet/1"}', encoding="utf-8")
    mode = {
        "unreadable": ["--upgrade"],
        "foreign_schema": ["--upgrade"],
        "directory_missing": ["--check-updates"],
        "no_mode": [],
    }[plan_error]
    if plan_error == "directory_missing":
        plan_file = tmp_path / "brak" / "plan.json"

    code, out, err = _run(
        capsys, [*ELEVATION, *store, *mode, "--plan", str(plan_file), "--json"]
    )

    document = json.loads(out)
    assert code == 2 and err == ""
    assert document["code"] == "invalid_input"
    assert document["details"] == {"option": "plan"}
