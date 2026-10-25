"""``main``: the exit codes and the ``kartograf-error/1`` document of every kind of
failure, in text and in the ``--json`` mode (spec 6.5, 6.6, 7.1; AGI-3.2, AGI-3.3).

An error writes nothing to stdout; the last line of stderr is its document in both
modes. The outcomes 10 and 11 (a result with ``ok: false``) are no errors: no error
document, the report on stdout with ``--json``."""

import io
import json
import logging
import os
import signal
import sys
import time
from unittest.mock import Mock, patch

import pytest

from kartograf.cli._handlers import HANDLERS
from kartograf.cli._json import emit_result
from kartograf.cli.commands import main
from kartograf.commands import parse_command
from kartograf.download.data import DataReport, UnitFailure
from kartograf.download.plan import new_plan
from kartograf.exceptions import DownloadError, UsageError, ValidationError
from kartograf.source_info import SourceList
from kartograf.transform.crs import TransformError, TransformUnavailableError
from tests.support.errors import error_document, without_error_document
from tests.support.interrupt_fakes import PATIENCE_S

SHEET = "N-34-130-D-d-2-4"
# a complete PL elevation request but for the store (none: the default store)
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


# the same request without the vertical CRS: an input error before any store is touched
NO_VERTICAL_CRS = [x for x in ELEVATION if x not in ("--vertical-crs", "EVRF2007")]
VERTICAL_CRS_REQUIRED = (
    "--vertical-crs wymagane dla --product nmt (PL): EVRF2007 (PL-EVRF2007-NH, "
    "uklad obowiazujacy), KRON86 (PL-KRON86-NH, uklad historyczny)"
)


def _run(capsys, argv: list[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _handler_fails(error):
    """``kartograf sheet parse`` fails with ``error``: its handler in the registry of
    the CLI is replaced for the length of the ``with`` block."""
    return patch.dict(HANDLERS, {"sheet parse": Mock(side_effect=error)})


# -- text mode ---------------------------------------------------------------


def test_input_error_exits_2_in_text_mode(capsys):
    code, out, err = _run(capsys, NO_VERTICAL_CRS)

    assert code == 2
    assert out == ""
    assert without_error_document(err) == f"Error: {VERTICAL_CRS_REQUIRED}\n"
    assert error_document(err)["message"] == VERTICAL_CRS_REQUIRED


def test_source_failure_exits_5(capsys, tmp_path):
    failure = DownloadError("HTTP 503 dla https://example.org/zrodlo")
    with patch("kartograf.cli.download_cmd.download_data", side_effect=failure):
        code, out, err = _run(capsys, [*ELEVATION, "--root", str(tmp_path)])

    assert code == 5
    assert without_error_document(err) == (
        "Error: HTTP 503 dla https://example.org/zrodlo\n"
    )
    assert error_document(err)["code"] == "source_unavailable"


def test_ok_false_exits_11_and_prints_no_error_document(capsys, tmp_path):
    report = DataReport(
        files=(),
        failed=(UnitFailure(SHEET, "PL", "brak odpowiedzi zrodla", "download"),),
        stale=(),
        superseded=(),
        notices=(),
        ok=False,
    )
    with patch("kartograf.cli.download_cmd.download_data", return_value=report):
        code, out, err = _run(capsys, [*ELEVATION, "--root", str(tmp_path)])

    assert code == 11
    assert out == ""
    # a failed unit is an outcome (ERR §1), not an error: its line, no document
    assert err == "Error: brak odpowiedzi zrodla\n"


def test_text_usage_error_is_unchanged(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["elevation", "download", "--bogus"])

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.out == ""
    assert captured.err.startswith("usage: kartograf elevation download")
    assert "error: nieznana opcja --bogus" in captured.err
    # the usage and the line of argparse stay; the document is the last line
    document = error_document(captured.err)
    assert (document["code"], document["details"]["reason"]) == (
        "validation_error",
        "usage",
    )
    assert document["command"] == "elevation download"


@pytest.mark.parametrize(
    ("error", "text", "exit_code"),
    [
        (
            TransformUnavailableError("brak operacji", remedy="zainstaluj siatki"),
            "Error: brak operacji Remedium: zainstaluj siatki\n",
            15,
        ),
        (TransformError("wynik nieskonczony"), "Error: wynik nieskonczony\n", 13),
    ],
)
def test_transform_failure_exits_13_or_15_and_text_has_the_remedy(
    capsys, error, text, exit_code
):
    """The remedy of an unavailable operation follows the message in every
    command, not only in the downloads of elevation and imagery."""
    with _handler_fails(error):
        code, out, err = _run(capsys, ["sheet", "parse", "N-34"])

    assert code == exit_code
    assert out == ""
    assert without_error_document(err) == text
    assert error_document(err)["exit_code"] == exit_code


# -- the --json mode ---------------------------------------------------------


def test_json_input_error_is_an_error_document(capsys):
    code, out, err = _run(capsys, [*NO_VERTICAL_CRS, "--json"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["schema"] == "kartograf-error/1"
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "invalid_input"
    assert document["message"] == VERTICAL_CRS_REQUIRED
    assert document["exit_code"] == 2
    assert document["command"] == "elevation download"
    assert document["details"] == {
        "reason": "invalid_input",
        "option": "vertical_crs",
        "allowed": ["EVRF2007", "KRON86"],
    }
    # the hint is a command line of the catalog that works as it stands
    example = document["hint"].split("Example: kartograf ", 1)[1]
    assert parse_command(example).command == "elevation download"


def test_json_input_error_lists_allowed_values_and_an_example(capsys, tmp_path):
    argv = [x for x in ELEVATION if x not in ("--vertical-crs", "EVRF2007")]
    code, out, err = _run(capsys, [*argv, "--root", str(tmp_path), "--json"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["details"] == {
        "reason": "invalid_input",
        "option": "vertical_crs",
        "allowed": ["EVRF2007", "KRON86"],
    }
    assert document["hint"].startswith(
        "Allowed values of --vertical-crs: EVRF2007, KRON86. "
        "Example: kartograf elevation download "
    )


def test_json_input_error_hint_example_is_of_the_product_and_country_of_the_line(
    capsys, tmp_path
):
    # E2E 0.8.0 D P3-7: the hint took the first example of the command
    argv = ["boundaries", "download", "--product", "admin", "--country", "auto"]
    argv += ["--level", "gmina", "--bbox", "18.6,49.7,18.7,49.8"]
    argv += ["--bbox-crs", "EPSG:4326", "--root", str(tmp_path), "--json"]

    code, out, err = _run(capsys, argv)

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["details"]["option"] == "level"
    example = parse_command(document["hint"].split("Example: kartograf ", 1)[1])
    assert example.command == "boundaries download"
    assert example.options["product"] == "admin"
    assert example.options["country"] == "auto"


def test_json_argparse_error_is_usage_error(capsys):
    code, out, err = _run(capsys, ["elevation", "download", "--bogus", "--json"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "usage"
    assert document["exit_code"] == 2
    assert "unknown option --bogus" in document["message"]


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--product", "foo"], "invalid choice: 'foo'"),
        (["--bogus"], "unknown option --bogus"),
        (["--product"], "expected one argument"),
    ],
    ids=["value-outside-choices", "unknown-flag", "flag-without-value"],
)
def test_json_usage_error_of_a_known_command_names_it_and_gives_an_example(
    capsys, flags, message
):
    code, out, err = _run(capsys, ["elevation", "download", *flags, "--json"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "usage"
    assert message in document["message"]
    assert document["command"] == "elevation download"
    where, example = document["hint"].split(" Example: kartograf ", 1)
    assert where == (
        "The options of the command: kartograf commands schema "
        '--command "elevation download".'
    )
    assert parse_command(example).command == "elevation download"


def test_json_usage_error_without_a_command_has_the_generic_hint(capsys):
    code, out, err = _run(capsys, ["elevation", "frobnicate", "--json"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "usage"
    assert "command" not in document
    assert document["hint"] == UsageError.DEFAULT_HINT


def test_json_usage_error_in_a_task_line_is_about_the_line_not_the_task(
    capsys, tmp_path
):
    argv = ["project", "add", "--json", "--project", str(tmp_path), "teren"]
    code, out, err = _run(capsys, [*argv, "elevation", "download", "--bogus"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "usage"
    assert document["command"] == "project add"
    assert document["hint"].startswith(
        "The options of the command: kartograf commands schema "
        '--command "elevation download".'
        " Example: "
    )


def test_json_removed_command_is_usage_error(capsys):
    code, out, err = _run(capsys, ["download", "--product", "nmt", "--json"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "usage"
    assert "kartograf elevation download" in document["message"]


def test_json_flag_before_the_command_is_a_usage_error(capsys):
    code, out, err = _run(capsys, ["--json", "elevation", "list-sources"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "usage"
    # one short hint: where the flag goes, not the list of all 37 commands
    assert "unknown option --json" in document["message"]
    assert "kartograf elevation list-sources --json" in document["message"]
    assert len(document["message"]) < 200


def test_json_parse_error_uses_invalid_sheet_code(capsys):
    code, out, err = _run(capsys, ["sheet", "parse", "NIE-GODLO", "--json"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "invalid_sheet_code"
    assert document["command"] == "sheet parse"
    assert document["details"] == {"reason": "invalid_sheet_code", "option": "sheet"}
    assert document["hint"].startswith("Sheet code formats: ")


def test_json_interrupt_is_130(capsys):
    with _handler_fails(KeyboardInterrupt):
        code, out, err = _run(capsys, ["sheet", "parse", "N-34-130-D", "--json"])

    document = error_document(err)
    assert code == 130 and out == ""
    assert document["code"] == "cancelled"
    assert document["exit_code"] == 130
    assert document["message"] == "interrupted (Ctrl-C)"
    assert document["command"] == "sheet parse"


@pytest.fixture
def sigterm_during_parse():
    """``kartograf sheet parse`` that gets a real SIGTERM (``timeout``, ``docker
    stop``) in the middle of its work; the handler of ``main`` ends it."""
    if os.name == "nt" or signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL:
        pytest.skip("SIGTERM is handled by the test runner")

    def handler(args):
        # a regression (no handler) must fail here, not kill the test run
        assert signal.getsignal(signal.SIGTERM) is not signal.SIG_DFL
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(PATIENCE_S)  # the handler raises here, in the main thread
        raise AssertionError("SIGTERM did not interrupt the command")

    with patch.dict(HANDLERS, {"sheet parse": handler}):
        yield
    assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL  # given back


def test_sigterm_is_143_with_the_error_document_in_json_mode(
    capsys, sigterm_during_parse
):
    code, out, err = _run(capsys, ["sheet", "parse", "N-34-130-D", "--json"])

    document = error_document(err)
    assert code == 143 and out == ""
    assert document["code"] == "terminated"
    assert document["exit_code"] == 143
    assert document["message"] == "terminated (SIGTERM)"
    assert document["command"] == "sheet parse"


def test_sigterm_is_143_with_one_error_line_in_text_mode(capsys, sigterm_during_parse):
    code, out, err = _run(capsys, ["sheet", "parse", "N-34-130-D"])

    assert code == 143 and out == ""
    assert without_error_document(err) == "Error: przerwano (SIGTERM)\n"
    assert error_document(err)["code"] == "terminated"


def test_oserror_is_io_error_in_json_mode(capsys, tmp_path):
    """The plan cannot be written (the write fails with an ``OSError``): the
    failure of the store, not a mistake of the command line - code 9,
    ``io_error``. (A directory in place of the plan file is rejected before
    any work: ``test_plan_file_that_is_a_directory_is_one_error_line``.)"""
    plan_file = tmp_path / "plan.json"
    checked = new_plan(tmp_path, [])
    argv = [*ELEVATION, "--root", str(tmp_path), "--check", "--json"]
    failure = IsADirectoryError(21, "Is a directory", str(plan_file))
    with (
        patch("kartograf.cli.download_cmd.check_data", return_value=checked),
        patch("pathlib.Path.write_text", side_effect=failure),
    ):
        code, out, err = _run(capsys, [*argv, "--plan", str(plan_file)])

    document = error_document(err)
    assert code == 9 and out == ""
    assert document["code"] == "io_error"
    assert document["exit_code"] == 9
    assert document["details"] == {"errno": "EISDIR", "path": str(plan_file)}


def test_internal_error_in_json_mode_and_debug_reraises(capsys, monkeypatch):
    with _handler_fails(RuntimeError("boom")):
        code, out, err = _run(capsys, ["sheet", "parse", "N-34", "--json"])

    document = error_document(err)
    assert code == 1 and out == ""
    assert document["code"] == "internal_error"
    assert document["message"] == "RuntimeError: boom"
    assert "KARTOGRAF_DEBUG" in document["hint"]

    monkeypatch.setenv("KARTOGRAF_DEBUG", "1")
    with (
        _handler_fails(RuntimeError("boom")),
        pytest.raises(RuntimeError, match="boom"),
    ):
        main(["sheet", "parse", "N-34", "--json"])
    assert capsys.readouterr().out == ""


def test_json_mode_sets_utf8_stdout(monkeypatch):
    """The envelope is UTF-8 whatever the locale of the stream (spec 7.1)."""
    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="ascii"))
    sources = SourceList(group="elevation", products=("zl\u0105d",), sources=())

    def handler(args):
        return emit_result("elevation list-sources", sources)

    with patch.dict(HANDLERS, {"sheet parse": handler}):
        code = main(["sheet", "parse", "N-34", "--json"])
    sys.stdout.flush()

    assert code == 0
    envelope = json.loads(raw.getvalue().decode("utf-8"))
    assert envelope["result"]["products"] == ["zl\u0105d"]


def test_the_error_document_is_ascii_whatever_the_encoding_of_stderr(capsys):
    """A character outside ASCII is a JSON escape: stderr cannot refuse it."""
    with _handler_fails(ValidationError("zly znak: \u017c")):
        code, out, err = _run(capsys, ["sheet", "parse", "N-34", "--json"])

    assert code == 2 and out == ""
    assert err.isascii()
    assert error_document(err)["message"] == "zly znak: \u017c"


def test_http_retry_lines_stay_on_stderr(capsys):
    """D6: the retry lines of the HTTP transport are outside the contract of the
    mode - stderr has them, stdout is still the one document."""

    def retried_then_failed(args):
        logging.getLogger("kartograf.transport.http").warning("HTTP 503, ponawiam 1/3")
        raise ValidationError("zle")

    with patch.dict(HANDLERS, {"sheet parse": retried_then_failed}):
        code, out, err = _run(capsys, ["sheet", "parse", "N-34", "--json"])

    assert code == 2 and out == ""
    assert error_document(err)["message"] == "zle"
    assert without_error_document(err) == "Warning: HTTP 503, ponawiam 1/3\n"


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
    """USAGE 9.2: with ``--json`` stderr is the error document alone - a library log
    record (here the skipped version of a store listing) is not printed as a bare
    line."""
    # no handler above the 'kartograf' branch -> logging.lastResort writes to
    # stderr, as in a real CLI run (pytest's root handler would hide it)
    monkeypatch.setattr(logging.getLogger("kartograf"), "propagate", False)
    with patch.dict(HANDLERS, {"sheet parse": _skipped_version_listing(tmp_path)}):
        code, out, err = _run(capsys, ["sheet", "parse", "N-34", "--json"])

    assert code == 2 and out == ""
    assert error_document(err)["message"] == "zle"
    assert without_error_document(err) == ""


def test_library_warnings_are_prefixed_in_text_mode(capsys, tmp_path, monkeypatch):
    """Text mode: the same record is a ``Warning:`` line, not a bare message."""
    monkeypatch.setattr(logging.getLogger("kartograf"), "propagate", False)
    with patch.dict(HANDLERS, {"sheet parse": _skipped_version_listing(tmp_path)}):
        code, out, err = _run(capsys, ["sheet", "parse", "N-34"])

    assert code == 2
    lines = without_error_document(err).splitlines()
    assert lines[0].startswith("Warning: Pominieto wersje bez czytelnego sidecara")
    assert lines[1:] == ["Error: zle"]
    assert error_document(err)["message"] == "zle"


def test_library_warnings_pass_with_debug_in_json_mode(capsys, tmp_path, monkeypatch):
    """``KARTOGRAF_DEBUG`` lets the library records through also in ``--json``."""
    monkeypatch.setenv("KARTOGRAF_DEBUG", "1")
    with (
        patch.dict(HANDLERS, {"sheet parse": _skipped_version_listing(tmp_path)}),
        pytest.raises(ValidationError),
    ):
        main(["sheet", "parse", "N-34", "--json"])

    assert capsys.readouterr().err.startswith(
        "Warning: Pominieto wersje bez czytelnego sidecara"
    )


# -- the handlers raise their input errors (no own "Error:" line) -------------


@pytest.mark.parametrize(
    ("argv", "option"),
    [
        (["landcover", "download"], "product"),
        (["landcover", "download", "--product", "corine"], "year"),
        (["landcover", "list-layers"], "product"),
        (["soil", "download"], "property"),
        (["soil", "hsg", "--sheet", "N-34-130-D"], "depth"),
        (["sheet", "parse", "NIE-GODLO"], "sheet"),
        (["sheet", "parse", "CTES96", "--hierarchy"], "hierarchy"),
        (["sheet", "parse", "N-34-130-D", "--descendants", "1:77"], "descendants"),
        (["commands", "schema", "--command", "nie-ma-takiej-komendy"], "command"),
        (["commands", "schema"], "command"),
    ],
)
def test_input_errors_of_the_handlers_name_the_option(capsys, argv, option):
    code, out, err = _run(capsys, [*argv, "--json"])

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["exit_code"] == 2
    assert document["details"]["option"] == option


@pytest.mark.parametrize(
    "plan_error",
    ["unreadable", "foreign_schema", "directory_missing", "no_mode"],
)
def test_plan_file_errors_are_input_errors_of_the_plan(capsys, tmp_path, plan_error):
    store = ["--root", str(tmp_path)]
    plan_file = tmp_path / "plan.json"
    if plan_error == "foreign_schema":
        plan_file.write_text('{"schema": "kartograf-sheet/1"}', encoding="utf-8")
    mode = {
        "unreadable": ["--upgrade"],
        "foreign_schema": ["--upgrade"],
        "directory_missing": ["--check"],
        "no_mode": [],
    }[plan_error]
    if plan_error == "directory_missing":
        plan_file = tmp_path / "brak" / "plan.json"

    code, out, err = _run(
        capsys, [*ELEVATION, *store, *mode, "--plan", str(plan_file), "--json"]
    )

    document = error_document(err)
    assert code == 2 and out == ""
    assert document["code"] == "validation_error"
    assert document["details"] == {"reason": "invalid_input", "option": "plan"}
