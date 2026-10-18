"""Stable error codes, hints and the ``kartograf-error/1`` document (spec 6)."""

import importlib
import pkgutil
import re
from pathlib import Path

import pytest

import kartograf
from kartograf.error_report import ERROR_CODES, EXIT_CODES, ErrorReport, error_report
from kartograf.exceptions import (
    CacheError,
    DownloadError,
    InvalidSidecarError,
    KartografError,
    NoCoverageError,
    ParseError,
    UsageError,
    ValidationError,
    YearRangeError,
)
from kartograf.serialization import SCHEMAS
from kartograf.transform.crs import TransformError, TransformUnavailableError

# Table 6.2 of the spec (code, exception, exit code) - a literal on purpose: a
# changed code is a breaking change and must be a deliberate edit of this test.
SPEC_ERROR_TABLE = [
    ("kartograf_error", "KartografError", 1),
    ("invalid_input", "ValidationError", 2),
    ("usage_error", "UsageError", 2),
    ("invalid_sheet_code", "ParseError", 2),
    ("download_failed", "DownloadError", 1),
    ("no_coverage", "NoCoverageError", 1),
    ("year_out_of_range", "YearRangeError", 1),
    ("cache_error", "CacheError", 1),
    ("invalid_sidecar", "InvalidSidecarError", 1),
    ("transform_failed", "TransformError", 1),
    ("transform_unavailable", "TransformUnavailableError", 1),
    ("io_error", "OSError", 1),
    ("interrupted", "KeyboardInterrupt", 130),
    ("internal_error", "Exception", 1),
]


def _kartograf_error_classes() -> list[type[KartografError]]:
    """Every ``KartografError`` class defined anywhere in the package."""
    for info in pkgutil.walk_packages(kartograf.__path__, "kartograf."):
        if not info.name.endswith(".__main__"):
            importlib.import_module(info.name)
    found: set[type[KartografError]] = {KartografError}
    pending: list[type[KartografError]] = [KartografError]
    while pending:
        for subclass in pending.pop().__subclasses__():
            if subclass.__module__.startswith("kartograf.") and subclass not in found:
                found.add(subclass)
                pending.append(subclass)
    return sorted(found, key=lambda cls: cls.__name__)


ERROR_CLASSES = _kartograf_error_classes()


@pytest.mark.parametrize("cls", ERROR_CLASSES, ids=lambda cls: cls.__name__)
def test_every_kartograf_error_class_has_its_own_code(cls):
    """``code`` is defined by the class itself: a new subclass that forgets it
    would report its parent's code, and consumers would not tell them apart."""
    assert "code" in cls.__dict__
    assert re.fullmatch(r"[a-z][a-z0-9_]*", cls.code)


def test_error_codes_are_unique():
    codes = [cls.code for cls in ERROR_CLASSES]
    assert len(codes) == len(set(codes))


def test_error_code_table_equals_the_spec():
    assert [(r.code, r.exception, r.exit_code) for r in ERROR_CODES] == (
        SPEC_ERROR_TABLE
    )
    assert [(r.code, r.name) for r in EXIT_CODES] == [
        (0, "ok"),
        (1, "failed"),
        (2, "usage"),
        (130, "interrupted"),
    ]
    for row in (*ERROR_CODES, *EXIT_CODES):
        assert row.meaning.isascii() and row.meaning


def test_error_code_table_matches_the_classes():
    """The table and the classes cannot drift apart: every class has its row."""
    rows = {r.exception: r for r in ERROR_CODES}
    for cls in ERROR_CLASSES:
        assert cls.__name__ in rows, f"{cls.__name__} has no row in ERROR_CODES"
        assert (cls.code, cls.exit_code) == (
            rows[cls.__name__].code,
            rows[cls.__name__].exit_code,
        )
    exit_codes = {r.code for r in EXIT_CODES}
    assert {r.exit_code for r in ERROR_CODES} <= exit_codes


def test_existing_constructors_keep_working_and_take_hint():
    download = DownloadError("m", sheet="x", status_code=404, hint="h1")
    coverage = NoCoverageError("m", "N-34", 200, ("a", "b"), hint="h2")
    years = YearRangeError(
        "m", sheets={"N-34": (2019, 2020)}, min_year=2021, max_year=None, hint="h3"
    )
    sidecar = InvalidSidecarError("m", path=Path("x.meta.json"), hint="h4")
    transform = TransformUnavailableError("m", [("op", "why")], "remedy", hint="h5")

    assert (download.sheet, download.status_code, download.hint) == ("x", 404, "h1")
    assert (coverage.sheet, coverage.hints, coverage.hint) == ("N-34", ("a", "b"), "h2")
    assert (years.sheets, years.min_year, years.max_year) == (
        {"N-34": (2019, 2020)},
        2021,
        None,
    )
    assert years.hint == "h3" and years.hints == ()
    assert sidecar.path == Path("x.meta.json") and sidecar.hint == "h4"
    assert (transform.rejected, transform.remedy, transform.hint) == (
        [("op", "why")],
        "remedy",
        "h5",
    )
    # the plain forms of 0.7 are unchanged
    assert DownloadError("m").hint is None and str(DownloadError("m")) == "m"
    assert NoCoverageError("m").hints == ()
    assert TransformUnavailableError("m").rejected == []
    assert (
        CacheError("m").hint is None and KartografError("m").code == "kartograf_error"
    )


def test_validation_error_attributes_and_details():
    plain = ValidationError("m")
    full = ValidationError(
        "m",
        option="vertical_crs",
        options=["sheet", "bbox"],
        allowed=["EVRF2007", "KRON86"],
    )

    assert (plain.option, plain.options, plain.allowed) == (None, None, None)
    assert plain.details() == {}
    assert full.options == ("sheet", "bbox")
    assert full.allowed == ("EVRF2007", "KRON86")
    assert full.details() == {
        "option": "vertical_crs",
        "options": ["sheet", "bbox"],
        "allowed": ["EVRF2007", "KRON86"],
    }
    assert full.exit_code == 2 and full.code == "invalid_input"
    with pytest.raises(TypeError, match="allowed"):
        ValidationError("m", option="product", allowed="nmt")


def test_details_encode_paths_and_skip_empty_values():
    years = YearRangeError(
        "m", sheets={"N-34": (2019, 2020)}, min_year=2021, max_year=None
    )
    coverage = NoCoverageError("m", sheet="N-34")
    sidecar = InvalidSidecarError("m", path=Path("x.meta.json"))
    transform = TransformUnavailableError("m", [("op", "why")])

    assert years.details() == {"sheets": {"N-34": [2019, 2020]}, "min_year": 2021}
    assert coverage.details() == {"sheet": "N-34"}
    assert sidecar.details() == {"path": (Path.cwd() / "x.meta.json").as_posix()}
    assert transform.details() == {"rejected": [["op", "why"]]}
    assert DownloadError("m", status_code=0).details() == {"status_code": 0}


def test_usage_error_is_a_validation_error():
    error = UsageError("nieznana flaga --x")

    assert isinstance(error, ValidationError)
    with pytest.raises(ValidationError):
        raise error
    assert (error.code, error.exit_code) == ("usage_error", 2)
    assert isinstance(ParseError("m"), ValidationError)
    assert (ParseError("m").code, ParseError("m").exit_code) == (
        "invalid_sheet_code",
        2,
    )


def test_error_report_document():
    exc = ValidationError(
        "--vertical-crs wymagane",
        option="vertical_crs",
        allowed=("EVRF2007", "KRON86"),
    )

    report = error_report(exc, command="elevation download")

    assert isinstance(report, ErrorReport)
    assert list(report.to_dict()) == [
        "schema",
        "code",
        "message",
        "hint",
        "exception",
        "exit_code",
        "command",
        "details",
    ]
    assert report.to_dict() == {
        "schema": "kartograf-error/1",
        "code": "invalid_input",
        "message": "--vertical-crs wymagane",
        "hint": "Dozwolone wartosci vertical_crs: EVRF2007, KRON86.",
        "exception": "ValidationError",
        "exit_code": 2,
        "command": "elevation download",
        "details": {"option": "vertical_crs", "allowed": ["EVRF2007", "KRON86"]},
    }
    assert error_report(exc).command is None


def test_hint_sources_in_order():
    own = NoCoverageError("m", hints=("a", "b"), hint="own hint")
    coverage = NoCoverageError("m", hints=("a", "b"))
    years = YearRangeError(
        "m",
        sheets={},
        min_year=None,
        max_year=None,
        hints=("--min-year 2019", "--max-year 2020"),
    )
    remedy = TransformUnavailableError("m", remedy="Zainstaluj siatki PROJ")
    quiet = NoCoverageError("m")

    assert error_report(own).hint == "own hint"
    assert error_report(coverage).hint == "a; b"
    assert error_report(years).hint == "--min-year 2019; --max-year 2020"
    assert error_report(remedy).hint == "Zainstaluj siatki PROJ"
    assert error_report(quiet).hint is None
    assert error_report(ValidationError("m")).hint is None
    for exc in (
        CacheError("m"),
        InvalidSidecarError("m", path=Path("p")),
        UsageError("m"),
    ):
        assert exc.DEFAULT_HINT
        assert error_report(exc).hint == exc.DEFAULT_HINT
    assert error_report(ParseError("m")).hint == ParseError.DEFAULT_HINT
    # a hint set where the error is raised wins over the class default
    assert error_report(CacheError("m", hint="Zamknij inny proces")).hint == (
        "Zamknij inny proces"
    )


def test_validation_hint_lists_allowed_values_with_option_name():
    two = ValidationError("m", option="vertical_crs", allowed=("EVRF2007", "KRON86"))
    many = ValidationError(
        "m", option="layer", allowed=tuple(f"v{i}" for i in range(45))
    )
    without_allowed = ValidationError("m", option="product")
    without_option = ValidationError("m", allowed=("a", "b"))

    assert (
        error_report(two).hint == "Dozwolone wartosci vertical_crs: EVRF2007, KRON86."
    )
    shown = ", ".join(f"v{i}" for i in range(40))
    assert error_report(many).hint == f"Dozwolone wartosci layer: {shown}, ..."
    assert error_report(without_allowed).hint is None
    assert error_report(without_option).hint is None


def test_oserror_is_io_error():
    report = error_report(FileNotFoundError(2, "No such file", "/x"))

    assert report.code == "io_error"
    assert report.exit_code == 1
    assert report.exception == "FileNotFoundError"
    assert report.message.startswith("FileNotFoundError: ")
    assert report.details == {"errno": "ENOENT", "path": "/x"}
    assert report.hint == "Sprawdz sciezke i uprawnienia: /x"
    bare = error_report(OSError("boom"))
    assert bare.details == {}
    assert bare.hint == "Sprawdz sciezki i uprawnienia katalogow z argumentow"
    assert error_report(PermissionError(13, "denied", Path("/p"))).details == {
        "errno": "EACCES",
        "path": "/p",
    }


def test_foreign_exception_is_internal_error():
    report = error_report(KeyError("x"))

    assert report.code == "internal_error"
    assert report.exit_code == 1
    assert report.exception == "KeyError"
    assert report.message == "KeyError: 'x'"
    assert report.details == {}
    assert report.hint is not None and "KARTOGRAF_DEBUG=1" in report.hint
    assert (
        error_report(ValueError("zażółć")).message
        == "ValueError: za\\u017c\\xf3\\u0142\\u0107"
    )


def test_keyboard_interrupt_is_interrupted():
    report = error_report(KeyboardInterrupt(), command="elevation download")

    assert (report.code, report.exit_code) == ("interrupted", 130)
    assert report.exception == "KeyboardInterrupt"
    assert report.message == "przerwano (Ctrl-C)"
    assert report.command == "elevation download"


def test_hint_is_one_ascii_line_up_to_400_chars():
    path = "/dane/zażółć\ngęślą"
    accented = error_report(FileNotFoundError(2, "No such file", path))
    multiline = error_report(ValidationError("m", hint="a\nb\r\n  c"))
    long = error_report(ValidationError("m", hint="x" * 500))

    assert accented.hint is not None
    assert accented.hint.isascii() and "\n" not in accented.hint
    assert accented.hint.startswith("Sprawdz sciezke i uprawnienia: /dane/za\\u017c")
    assert multiline.hint == "a b c"
    assert long.hint is not None
    assert len(long.hint) == 400 and long.hint.endswith("...")
    assert long.hint[:-3] == "x" * 397


def test_error_report_is_registered():
    assert SCHEMAS["kartograf-error/1"] == (ErrorReport,)


def test_transform_errors_have_codes():
    assert TransformError("m").code == "transform_failed"
    assert TransformUnavailableError("m").code == "transform_unavailable"
    assert isinstance(TransformUnavailableError("m"), TransformError)
