"""Stable error codes, hints and the ``kartograf-error/1`` document (spec 6)."""

import importlib
import pkgutil
import re
from pathlib import Path

import pytest

import kartograf
from kartograf._errors import BY_CODE
from kartograf.commands import parse_command, validate_command
from kartograf.download.cutout import CUTOUT_CRS
from kartograf.download.cz_contours import contours_formats
from kartograf.download.options import BBOX_CRS_CHOICES, require_product
from kartograf.error_report import ERROR_CODES, EXIT_CODES, ErrorReport, error_report
from kartograf.exceptions import (
    CacheError,
    DownloadError,
    ForbiddenError,
    InvalidSidecarError,
    KartografError,
    MissingDependencyError,
    NoCoverageError,
    ParseError,
    UsageError,
    ValidationError,
    YearRangeError,
)
from kartograf.interrupt import Terminated
from kartograf.providers.pl.gugik_orto import cutout_resolution_labels
from kartograf.serialization import SCHEMAS
from kartograf.sources.variants import cz_models, resolution_label, variants
from kartograf.transform.crs import TransformError, TransformUnavailableError

# Table of the errors (exception, registry code, details.reason, exit code) - a
# literal on purpose: a changed code is a breaking change and must be a
# deliberate edit of this test (ERR §4 maps the old codes to these).
SPEC_ERROR_TABLE = [
    ("KartografError", "internal_error", None, 1),
    ("ValidationError", "validation_error", "invalid_input", 2),
    ("UsageError", "validation_error", "usage", 2),
    ("ParseError", "validation_error", "invalid_sheet_code", 2),
    ("ConfigError", "validation_error", "invalid_config", 2),
    ("DownloadError", "source_unavailable", None, 5),
    ("NoCoverageError", "no_data", "no_coverage", 14),
    ("YearRangeError", "no_data", "year_out_of_range", 14),
    ("CacheError", "store_unavailable", "cache", 8),
    ("StoreUnavailableError", "store_unavailable", None, 8),
    ("InvalidSidecarError", "data_error", "invalid_sidecar", 7),
    ("InvalidLayoutError", "data_error", "invalid_layout", 7),
    ("ConflictError", "conflict", None, 4),
    ("MissingDependencyError", "missing_dependency", None, 6),
    ("ForbiddenError", "forbidden", None, 12),
    ("TransformError", "calculation_error", "transform_failed", 13),
    ("TransformUnavailableError", "unsupported", "transform_unavailable", 15),
    ("OSError", "io_error", None, 9),
    ("KeyboardInterrupt", "cancelled", None, 130),
    ("Terminated", "terminated", None, 143),
    ("Exception", "internal_error", None, 1),
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
    assert cls.code in BY_CODE
    assert cls.exit_code == BY_CODE[cls.code].exit_code
    assert cls.reason is None or re.fullmatch(r"[a-z][a-z0-9_]*", cls.reason)


def test_error_classes_are_told_apart_by_code_and_reason():
    pairs = [(cls.code, cls.reason) for cls in ERROR_CLASSES]
    assert len(pairs) == len(set(pairs))


def test_error_table_equals_the_spec():
    assert [(r.exception, r.code, r.reason, r.exit_code) for r in ERROR_CODES] == (
        SPEC_ERROR_TABLE
    )
    assert [(r.code, r.name) for r in EXIT_CODES] == [
        (0, "ok"),
        (1, "internal_error"),
        (2, "validation_error"),
        (4, "conflict"),
        (5, "source_unavailable"),
        (6, "missing_dependency"),
        (7, "data_error"),
        (8, "store_unavailable"),
        (9, "io_error"),
        (10, "partial"),
        (11, "failed"),
        (12, "forbidden"),
        (13, "calculation_error"),
        (14, "no_data"),
        (15, "unsupported"),
        (130, "cancelled"),
        (143, "terminated"),
    ]
    for row in (*ERROR_CODES, *EXIT_CODES):
        assert row.meaning.isascii() and row.meaning


def test_error_table_matches_the_classes():
    """The table and the classes cannot drift apart: every class has its row."""
    rows = {r.exception: r for r in ERROR_CODES}
    for cls in ERROR_CLASSES:
        assert cls.__name__ in rows, f"{cls.__name__} has no row in ERROR_CODES"
        assert (cls.code, cls.reason, cls.exit_code) == (
            rows[cls.__name__].code,
            rows[cls.__name__].reason,
            rows[cls.__name__].exit_code,
        )
    exit_codes = {r.code for r in EXIT_CODES}
    assert {r.exit_code for r in ERROR_CODES} <= exit_codes
    for row in ERROR_CODES:
        assert BY_CODE[row.code].exit_code == row.exit_code


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
    assert CacheError("m").hint is None
    assert (KartografError("m").code, KartografError("m").reason) == (
        "internal_error",
        None,
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
    assert plain.details() == {"reason": "invalid_input"}
    assert full.options == ("sheet", "bbox")
    assert full.allowed == ("EVRF2007", "KRON86")
    assert full.details() == {
        "reason": "invalid_input",
        "option": "vertical_crs",
        "options": ["sheet", "bbox"],
        "allowed": ["EVRF2007", "KRON86"],
    }
    assert full.exit_code == 2 and full.code == "validation_error"
    with pytest.raises(TypeError, match="allowed"):
        ValidationError("m", option="product", allowed="nmt")


def test_details_encode_paths_and_skip_empty_values():
    years = YearRangeError(
        "m", sheets={"N-34": (2019, 2020)}, min_year=2021, max_year=None
    )
    coverage = NoCoverageError("m", sheet="N-34")
    sidecar = InvalidSidecarError("m", path=Path("x.meta.json"))
    transform = TransformUnavailableError("m", [("op", "why")])

    assert years.details() == {
        "reason": "year_out_of_range",
        "sheets": {"N-34": [2019, 2020]},
        "min_year": 2021,
    }
    assert coverage.details() == {"reason": "no_coverage", "sheet": "N-34"}
    assert sidecar.details() == {
        "reason": "invalid_sidecar",
        "path": (Path.cwd() / "x.meta.json").as_posix(),
    }
    assert transform.details() == {
        "reason": "transform_unavailable",
        "rejected": [["op", "why"]],
    }
    assert DownloadError("m", status_code=0).details() == {"status_code": 0}


def test_usage_error_is_a_validation_error():
    error = UsageError("nieznana flaga --x")

    assert isinstance(error, ValidationError)
    with pytest.raises(ValidationError):
        raise error
    assert (error.code, error.reason, error.exit_code) == (
        "validation_error",
        "usage",
        2,
    )
    assert isinstance(ParseError("m"), ValidationError)
    assert (ParseError("m").code, ParseError("m").reason) == (
        "validation_error",
        "invalid_sheet_code",
    )
    assert ParseError("m").exit_code == 2


def test_forbidden_error_document():
    outside = Path("/data/elsewhere").resolve()
    exc = ForbiddenError(
        "root lies outside the allowed directories",
        option="root",
        path=outside,
        allowed=("/data/kartograf", "/data/other"),
        hint="Use a path inside an allowed directory.",
    )

    assert (exc.code, exc.exit_code, exc.reason) == ("forbidden", 12, None)
    assert not isinstance(exc, ValidationError)
    assert error_report(exc, command="store overview").to_dict() == {
        "schema": "kartograf-error/1",
        "code": "forbidden",
        "title": "Not allowed",
        "message": "root lies outside the allowed directories",
        "hint": "Use a path inside an allowed directory.",
        "details": {
            "option": "root",
            "path": outside.as_posix(),
            "allowed": ["/data/kartograf", "/data/other"],
        },
        "exit_code": 12,
        "command": "store overview",
    }
    assert ForbiddenError("m").details() == {}
    with pytest.raises(TypeError, match="allowed"):
        ForbiddenError("m", allowed="/data")


def test_missing_dependency_error_names_the_install_command():
    exc = MissingDependencyError("the MCP server needs the mcp package", extra="mcp")
    own = MissingDependencyError("m", extra="mcp", hint="pip install mcp")

    assert (exc.code, exc.exit_code, exc.reason) == ("missing_dependency", 6, None)
    report = error_report(exc)
    assert report.to_dict() == {
        "schema": "kartograf-error/1",
        "code": "missing_dependency",
        "title": "Missing optional dependency",
        "message": "the MCP server needs the mcp package",
        "hint": 'uv add "kartograf[mcp]"',
        "details": {"extra": "mcp"},
        "exit_code": 6,
    }
    assert error_report(own).hint == "pip install mcp"
    assert MissingDependencyError("m").hint is None  # no extra, no command to name


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
        "title",
        "message",
        "hint",
        "details",
        "exit_code",
        "command",
    ]
    assert report.to_dict() == {
        "schema": "kartograf-error/1",
        "code": "validation_error",
        "title": "Invalid input",
        "message": "--vertical-crs wymagane",
        "hint": "Allowed values of --vertical-crs: EVRF2007, KRON86. Example: "
        "kartograf elevation download --product nmt --sheet N-34-130-D-d-2-4 "
        "--resolution 1m --vertical-crs EVRF2007 --root ./data",
        "details": {
            "reason": "invalid_input",
            "option": "vertical_crs",
            "allowed": ["EVRF2007", "KRON86"],
        },
        "exit_code": 2,
        "command": "elevation download",
    }
    assert error_report(exc).command is None
    # hint and command are left out of the document when there is none
    bare = error_report(ValidationError("m")).to_dict()
    assert "hint" not in bare and "command" not in bare
    assert bare["details"] == {"reason": "invalid_input"}


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

    assert error_report(two).hint == "Allowed values of vertical_crs: EVRF2007, KRON86."
    shown = ", ".join(f"v{i}" for i in range(40))
    assert error_report(many).hint == f"Allowed values of layer: {shown}, ..."
    assert error_report(without_allowed).hint is None
    assert error_report(without_option).hint is None


def test_validation_hint_has_flag_and_example_from_the_catalog():
    exc = ValidationError("m", option="vertical_crs", allowed=("EVRF2007", "KRON86"))

    hint = error_report(exc, command="elevation download").hint

    assert hint is not None and hint.startswith(
        "Allowed values of --vertical-crs: EVRF2007, KRON86. Example: "
        "kartograf elevation download "
    )
    example = parse_command(hint.split("Example: kartograf ", 1)[1])
    assert example.command == "elevation download"
    assert "vertical_crs" in example.options
    # without the command the flag is the name of the argument, with no example
    bare = "Allowed values of vertical_crs: EVRF2007, KRON86."
    assert error_report(exc).hint == bare
    assert error_report(exc, command="no such command").hint == bare
    assert error_report(exc, command="sheet parse").hint == (
        f"{bare} Example: kartograf sheet parse N-34-130-D-d-2-4"
    )


def test_usage_error_of_a_known_command_names_it_and_gives_an_example():
    exc = UsageError("argument --product: invalid choice", command="elevation download")

    report = error_report(exc)

    assert (exc.command, report.command) == ("elevation download",) * 2
    assert report.exit_code == 2 and report.details == {"reason": "usage"}
    assert report.hint is not None
    where, example = report.hint.split(" Example: kartograf ", 1)
    assert where == (
        "The options of the command: kartograf commands schema "
        '--command "elevation download".'
    )
    assert parse_command(example).command == "elevation download"
    assert UsageError("m").command is None


def test_usage_error_command_and_hint_sources():
    exc = UsageError("m", command="elevation download")

    # the command a caller names is the one that failed; the hint is about the
    # command whose line was wrong (the parser of a line inside ``project add``)
    nested = error_report(exc, command="project add")
    assert nested.command == "project add"
    assert nested.hint is not None
    assert nested.hint.startswith(
        'The options of the command: kartograf commands schema --command "elevation '
    )
    # without a command of its own the error is about the command that was run
    assert error_report(UsageError("m"), command="sheet parse").hint == (
        'The options of the command: kartograf commands schema --command "sheet '
        'parse". Example: kartograf sheet parse N-34-130-D-d-2-4'
    )
    # a hint set where the error is raised wins, an unknown id is no command
    own = UsageError("m", command="elevation download", hint="Wlasna podpowiedz")
    assert error_report(own).hint == "Wlasna podpowiedz"
    unknown = UsageError("m", command="no such command")
    assert error_report(unknown).hint == UsageError.DEFAULT_HINT
    assert error_report(UsageError("m")).hint == UsageError.DEFAULT_HINT


def test_validation_hint_has_an_example_without_allowed_values():
    hint = error_report(
        ValidationError("m", option="root"), command="elevation download"
    ).hint

    assert hint is not None and hint.startswith("Example: kartograf elevation ")
    assert hint.endswith("--root ./data")


def test_validation_hint_drops_the_example_that_would_not_fit():
    long_values = tuple(f"wartosc-{i:02d}-dluga" for i in range(40))
    exc = ValidationError("m", option="product", allowed=long_values)

    hint = error_report(exc, command="elevation download").hint

    assert hint is not None and len(hint) <= 400
    assert hint.startswith("Allowed values of --product: wartosc-00-dluga")
    assert "Example" not in hint


def test_validation_hint_of_several_options_has_their_flags_and_an_example():
    exc = ValidationError("m", options=("sheet", "bbox", "geometry"))

    hint = error_report(exc, command="elevation download").hint

    assert hint is not None and hint.startswith(
        "Options: --sheet, --bbox, --geometry. Example: kartograf elevation download "
    )
    example = parse_command(hint.split("Example: kartograf ", 1)[1])
    assert example.command == "elevation download" and "sheet" in example.options
    # without the command the names of the arguments stand for the flags
    assert error_report(exc).hint == "Options: sheet, bbox, geometry."
    assert error_report(exc, command="no such command").hint == (
        "Options: sheet, bbox, geometry."
    )
    # one argument named is the hint of that argument, not of the group
    single = ValidationError("m", option="sheet", options=("sheet", "bbox"))
    assert error_report(single).hint is None


def test_the_missing_area_of_a_command_line_has_a_hint_with_an_example(tmp_path):
    with pytest.raises(ValidationError) as caught:
        validate_command("elevation download", {"product": "nmt"}, root=tmp_path)

    assert caught.value.options == ("sheet", "bbox", "geometry")
    hint = error_report(caught.value, command="elevation download").hint
    assert hint is not None and hint.startswith("Options: --sheet, --bbox, --geometry.")
    assert "Example: kartograf elevation download " in hint


def test_oserror_is_io_error():
    report = error_report(FileNotFoundError(2, "No such file", "/x"))

    assert report.code == "io_error"
    assert report.title == "File system error"
    assert report.exit_code == 9
    assert report.message.startswith("FileNotFoundError: ")
    assert report.details == {"errno": "ENOENT", "path": "/x"}
    assert report.hint == "Check the path and the permissions: /x"
    bare = error_report(OSError("boom"))
    assert bare.details == {}
    assert bare.hint == (
        "Check the paths and the permissions of the directories in the arguments"
    )
    assert error_report(PermissionError(13, "denied", Path("/p"))).details == {
        "errno": "EACCES",
        "path": "/p",
    }


def test_foreign_exception_is_internal_error():
    report = error_report(KeyError("x"))

    assert report.code == "internal_error"
    assert report.exit_code == 1
    assert report.message == "KeyError: 'x'"
    assert report.details == {}
    assert report.hint is not None and "KARTOGRAF_DEBUG=1" in report.hint
    assert (
        error_report(ValueError("zażółć")).message
        == "ValueError: za\\u017c\\xf3\\u0142\\u0107"
    )


def test_keyboard_interrupt_is_cancelled():
    report = error_report(KeyboardInterrupt(), command="elevation download")

    assert (report.code, report.exit_code) == ("cancelled", 130)
    assert report.message == "interrupted (Ctrl-C)"
    assert report.command == "elevation download"


def test_sigterm_is_terminated_with_its_own_exit_code():
    report = error_report(Terminated(), command="landcover download")

    assert (report.code, report.exit_code) == ("terminated", 143)
    assert report.message == "terminated (SIGTERM)"
    assert report.command == "landcover download"
    assert report.hint is None


def test_hint_is_one_ascii_line_up_to_400_chars():
    path = "/dane/zażółć\ngęślą"
    accented = error_report(FileNotFoundError(2, "No such file", path))
    multiline = error_report(ValidationError("m", hint="a\nb\r\n  c"))
    long = error_report(ValidationError("m", hint="x" * 500))

    assert accented.hint is not None
    assert accented.hint.isascii() and "\n" not in accented.hint
    assert accented.hint.startswith(
        "Check the path and the permissions: /dane/za\\u017c"
    )
    assert multiline.hint == "a b c"
    assert long.hint is not None
    assert len(long.hint) == 400 and long.hint.endswith("...")
    assert long.hint[:-3] == "x" * 397


def test_error_report_is_registered():
    assert SCHEMAS["kartograf-error/1"] == (ErrorReport,)


def test_transform_errors_have_registry_codes():
    assert (TransformError("m").code, TransformError("m").reason) == (
        "calculation_error",
        "transform_failed",
    )
    unavailable = TransformUnavailableError("m")
    assert (unavailable.code, unavailable.reason, unavailable.exit_code) == (
        "unsupported",
        "transform_unavailable",
        15,
    )
    assert isinstance(unavailable, TransformError)


# --- option/allowed of the collection, land cover, SoilGrids and HSG validators ---
# One row per message class, called through the PUBLIC entry points: the raise must
# reach the caller before any request (the suite blocks the network).

_STORE = object()  # placeholder of the store directory (``tmp_path``)
_AREA = kartograf.BBox(450000, 550000, 450500, 550500, "EPSG:2180")
_SHEET = "N-34-130-D"
_DEPTHS = ("0-5cm", "5-15cm", "15-30cm", "30-60cm", "60-100cm", "100-200cm")
_COLLECTIONS = importlib.import_module("kartograf.download.collections")
_AREA_NAMES = ("sheet", "bbox", "geometry")


def _row(function, arguments, option, options, allowed, text):
    """A scenario: the call and the expected attributes plus a message fragment."""
    return pytest.param(
        function,
        arguments,
        (option, options, allowed),
        text,
        id=f"{function.__name__}-{text[:40]}",
    )


COLLECTION_OPTION_SCENARIOS = [
    _row(
        kartograf.download_collection,
        {"product": None, "root": _STORE, "teryt": "1261"},
        "product",
        None,
        _COLLECTIONS.collection_products(),
        "--product wymagane",
    ),
    _row(
        kartograf.download_collection,
        {"product": "xyz", "root": _STORE, "teryt": "1261"},
        "product",
        None,
        _COLLECTIONS.collection_products(),
        "Nieznany produkt 'xyz'",
    ),
    _row(
        _COLLECTIONS.require_collection_product,
        {"product": None, "group": "boundaries"},
        "product",
        None,
        _COLLECTIONS.collection_products("boundaries"),
        "--product wymagane",
    ),
    _row(
        _COLLECTIONS.require_collection_product,
        {"product": "buildings", "group": "boundaries"},
        "product",
        None,
        _COLLECTIONS.collection_products("boundaries"),
        "nieznana wartosc",
    ),
    _row(
        kartograf.download_collection,
        {"product": "buildings", "root": _STORE, "lod": 1, "year": 2024},
        None,
        ("teryt", *_AREA_NAMES),
        None,
        "Podaj dokladnie jeden wybor",
    ),
    _row(
        kartograf.check_collection,
        {
            "product": "buildings",
            "root": _STORE,
            "teryt": "1261",
            "bbox": _AREA,
            "lod": 1,
            "year": 2024,
        },
        None,
        ("teryt", "bbox"),
        None,
        "Podaj dokladnie jeden wybor",
    ),
    _row(
        kartograf.download_collection,
        {"product": "map", "root": _STORE, "bbox": _AREA, "country": "xx"},
        "country",
        None,
        ("pl", "cz", "auto"),
        "Nieznany kraj --country 'xx'",
    ),
    _row(
        kartograf.download_collection,
        {"product": "map", "root": _STORE, "bbox": _AREA},
        "country",
        None,
        ("pl", "cz", "auto"),
        "--country wymagane z --bbox/--geometry",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "buildings",
            "root": _STORE,
            "teryt": "1261",
            "lod": 2,
            "country": "cz",
        },
        None,
        ("teryt", "country"),
        None,
        "usun --country cz",
    ),
    _row(
        kartograf.download_collection,
        {"product": "buildings", "root": _STORE, "teryt": "126", "lod": 2},
        "teryt",
        None,
        None,
        "Nieprawidlowy kod TERYT",
    ),
    _row(
        kartograf.download_collection,
        {"product": "buildings", "root": _STORE, "teryt": "9901", "lod": 2},
        "teryt",
        None,
        None,
        "nie ma wojewodztwa o kodzie 99",
    ),
    _row(
        kartograf.download_collection,
        {"product": "map", "root": _STORE, "ku": "623164", "country": "pl"},
        None,
        ("ku", "country"),
        None,
        "usun --country pl",
    ),
    _row(
        kartograf.download_collection,
        {"product": "map", "root": _STORE, "ku": "12", "country": "cz"},
        "ku",
        None,
        None,
        "Nieprawidlowy kod katastralniho uzemi",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "admin",
            "root": _STORE,
            "whole_country": True,
            "country": "auto",
        },
        "country",
        None,
        ("pl", "cz"),
        "--whole-country wymaga --country pl albo --country cz",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "prices",
            "root": _STORE,
            "whole_country": True,
            "country": "cz",
        },
        "country",
        None,
        ("pl",),
        "jest dostepny tylko dla PL",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "geographic",
            "root": _STORE,
            "whole_country": True,
            "country": "cz",
            "format": "XYZ",
        },
        "format",
        None,
        ("GPKG", "FGDB"),
        "niedostepne dla --whole-country geographic (CZ)",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "topographic",
            "root": _STORE,
            "country": "pl",
            "sheet": _SHEET,
            "format": "XYZ",
        },
        "format",
        None,
        ("TIFF", "PDF"),
        "--format XYZ: not available",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "map",
            "root": _STORE,
            "country": "pl",
            "bbox": _AREA,
            "format": "SHP",
        },
        "format",
        None,
        None,
        "dotyczy tylko --product map (CZ",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "topographic",
            "root": _STORE,
            "country": "cz",
            "bbox": _AREA,
            "scale": "1:1",
        },
        "scale",
        None,
        _COLLECTIONS.collection_choice_values("topographic", "scale")["CZ"],
        "--scale 1:1: not available",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "topographic",
            "root": _STORE,
            "country": "cz",
            "bbox": _AREA,
            "sheet_system": "1965",
        },
        "sheet_system",
        None,
        ("sjtsk", "etrs89"),
        "--sheet-system 1965: not available",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "map",
            "root": _STORE,
            "country": "pl",
            "bbox": _AREA,
            "horizontal_crs": "EPSG:4326",
        },
        "horizontal_crs",
        None,
        ("EPSG:2180",),
        "sa zawsze w ukladzie uslugi EPSG:2180",
    ),
    _row(
        kartograf.download_collection,
        {"product": "buildings", "root": _STORE, "teryt": "1261"},
        "lod",
        None,
        ("1", "2"),
        "--lod required",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "buildings",
            "root": _STORE,
            "teryt": "1261",
            "lod": 2,
            "year": 2016,
        },
        "year",
        None,
        ("2017",),
        "--year 2016: not available for --lod 2",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "admin",
            "root": _STORE,
            "country": "pl",
            "bbox": _AREA,
            "level": "gmina",
            "year": 2020,
        },
        "year",
        None,
        None,
        "nie dotyczy obiektow obszaru produktu admin",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "buildings",
            "root": _STORE,
            "teryt": "1261",
            "lod": 2,
            "level": "gmina",
        },
        "level",
        None,
        None,
        "nie paczek buildings",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "map",
            "root": _STORE,
            "country": "pl",
            "bbox": _AREA,
            "level": "gmina",
        },
        "level",
        None,
        None,
        "(stala zawartosc",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "map",
            "root": _STORE,
            "country": "pl",
            "bbox": _AREA,
            "lod": 1,
        },
        "lod",
        None,
        None,
        "nie dotyczy obiektow obszaru produktu map",
    ),
    _row(
        kartograf.download_collection,
        {"product": "admin", "root": _STORE, "country": "pl", "bbox": _AREA},
        "level",
        None,
        _COLLECTIONS.collection_levels("admin")["PL"],
        "--level wymagane",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "admin",
            "root": _STORE,
            "country": "pl",
            "bbox": _AREA,
            "level": "obec",
        },
        "level",
        None,
        _COLLECTIONS.collection_levels("admin")["PL"],
        "nieznany poziom admin (PL)",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "control",
            "root": _STORE,
            "country": "pl",
            "bbox": _AREA,
            "network": "xyz",
        },
        "network",
        None,
        _COLLECTIONS.collection_choice_values("control", "network")["PL"],
        "--network xyz: niedostepne dla obszaru control (PL)",
    ),
    _row(
        kartograf.download_collection,
        {"product": "control", "root": _STORE, "country": "pl", "bbox": _AREA},
        "network",
        None,
        _COLLECTIONS.collection_choice_values("control", "network")["PL"],
        "--network wymagane dla obszaru control (PL)",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "prices",
            "root": _STORE,
            "whole_country": True,
            "country": "pl",
        },
        "whole_country",
        None,
        None,
        "nie ma pliku krajowego",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "map",
            "root": _STORE,
            "sheet": _SHEET,
            "country": "cz",
        },
        None,
        ("sheet", "country"),
        None,
        "a podano --country cz",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "map",
            "root": _STORE,
            "country": "pl",
            "bbox": kartograf.BBox(1, 1, 2, 2, "EPSG:2180"),
        },
        "bbox",
        None,
        None,
        "lies outside PL",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "buildings",
            "root": _STORE,
            "teryt": "1261",
            "lod": 2,
            "year": 2017,
            "plan": object(),
        },
        None,
        ("plan", "update"),
        None,
        "Plan aktualizacji wymaga update='upgrade'",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "buildings",
            "root": _STORE,
            "teryt": "1261",
            "lod": 2,
            "year": 2017,
            "workers": 0,
        },
        "workers",
        None,
        None,
        "workers musi byc >= 1",
    ),
]

LANDCOVER_OPTION_SCENARIOS = [
    _row(
        kartograf.download_landcover,
        {"product": None, "root": _STORE, "teryt": "1465"},
        "product",
        None,
        ("bdot10k", "bdoo", "corine", "zabaged", "data50", "data250"),
        "--product required",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "soilgrids", "root": _STORE, "teryt": "1465"},
        "product",
        None,
        ("bdot10k", "bdoo", "corine", "zabaged", "data50", "data250"),
        "unknown value",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "bdot10k", "root": _STORE},
        None,
        ("teryt", *_AREA_NAMES),
        None,
        "Give exactly one selection for --product bdot10k",
    ),
    _row(
        kartograf.check_landcover,
        {
            "product": "corine",
            "root": _STORE,
            "year": 2018,
            "sheet": _SHEET,
            "bbox": _AREA,
        },
        None,
        ("sheet", "bbox"),
        None,
        "Give exactly one selection for --product corine",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "corine", "root": _STORE, "year": 2018},
        None,
        _AREA_NAMES,
        None,
        "Give exactly one selection for --product corine",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "corine", "root": _STORE, "sheet": _SHEET},
        "year",
        None,
        ("2018", "2012", "2006", "2000", "1990"),
        "--year required for corine",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "corine", "root": _STORE, "sheet": _SHEET, "year": 2019},
        "year",
        None,
        ("2018", "2012", "2006", "2000", "1990"),
        "--year 2019: not available for --product corine; available: 2018, 2012, ",
    ),
    _row(
        kartograf.download_landcover,
        {
            "product": "corine",
            "root": _STORE,
            "sheet": _SHEET,
            "year": 2018,
            "format": "SHP",
        },
        "format",
        None,
        None,
        "--format only works with --product bdot10k",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "bdot10k", "root": _STORE, "teryt": "1465", "format": "GML"},
        "format",
        None,
        ("GPKG", "SHP"),
        "GML only with --year",
    ),
    _row(
        kartograf.download_landcover,
        {
            "product": "bdot10k",
            "root": _STORE,
            "teryt": "1465",
            "format": "SHP",
            "layers": ["PTWP"],
        },
        None,
        ("layers", "format"),
        None,
        "--layers applies only to --format GPKG",
    ),
    _row(
        kartograf.download_landcover,
        {
            "product": "bdot10k",
            "root": _STORE,
            "teryt": "1465",
            "year": 2020,
            "format": "GML",
            "layers": ["PTWP"],
        },
        "layers",
        None,
        None,
        "does not apply to the BDOT10k archive",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "bdot10k", "root": _STORE, "teryt": "1465", "year": 2020},
        "format",
        None,
        ("GML", "SHP"),
        "--format required for --year 2020",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "bdot10k", "root": _STORE, "teryt": "14"},
        "teryt",
        None,
        None,
        "is published per county",
    ),
    _row(
        kartograf.download_landcover,
        {"product": "corine", "root": _STORE, "teryt": "1465", "year": 2018},
        "teryt",
        None,
        None,
        "--teryt works only with",
    ),
    _row(
        kartograf.download_landcover,
        {
            "product": "corine",
            "root": _STORE,
            "sheet": _SHEET,
            "year": 2018,
            "layers": ["PTWP"],
        },
        "layers",
        None,
        None,
        "--layers only works with --product bdot10k or bdoo",
    ),
    _row(
        kartograf.download_landcover,
        {
            "product": "zabaged",
            "root": _STORE,
            "whole_country": True,
            "horizontal_crs": "EPSG:1",
        },
        "horizontal_crs",
        None,
        ("EPSG:5514", "EPSG:3045"),
        "the dataset is not published in this CRS",
    ),
    _row(
        kartograf.download_landcover,
        {
            "product": "bdot10k",
            "root": _STORE,
            "teryt": "1465",
            "plan": object(),
        },
        None,
        ("plan", "update"),
        None,
        "The update plan requires update='upgrade'",
    ),
    _row(
        kartograf.download_soil,
        {"root": _STORE, "sheet": _SHEET, "depth": "0-5cm", "stat": "mean"},
        "property",
        None,
        (
            "bdod",
            "cec",
            "cfvo",
            "clay",
            "nitrogen",
            "ocd",
            "ocs",
            "phh2o",
            "sand",
            "silt",
            "soc",
        ),
        "--property required",
    ),
    _row(
        kartograf.download_soil,
        {
            "root": _STORE,
            "sheet": _SHEET,
            "property": "clay",
            "depth": "1m",
            "stat": "mean",
        },
        "depth",
        None,
        _DEPTHS,
        "Invalid depth: 1m",
    ),
    _row(
        kartograf.download_soil,
        {"root": _STORE, "sheet": _SHEET, "property": "clay", "depth": "0-5cm"},
        "stat",
        None,
        ("mean", "Q0.05", "Q0.5", "Q0.95", "uncertainty"),
        "--stat required",
    ),
    _row(
        kartograf.check_soil,
        {
            "root": _STORE,
            "sheet": _SHEET,
            "property": "x",
            "depth": "0-5cm",
            "stat": "mean",
        },
        "property",
        None,
        (
            "bdod",
            "cec",
            "cfvo",
            "clay",
            "nitrogen",
            "ocd",
            "ocs",
            "phh2o",
            "sand",
            "silt",
            "soc",
        ),
        "Invalid property: x",
    ),
    _row(
        kartograf.download_soil,
        {
            "root": _STORE,
            "property": "clay",
            "depth": "0-5cm",
            "stat": "mean",
        },
        None,
        _AREA_NAMES,
        None,
        "Give exactly one selection",
    ),
    _row(
        kartograf.calculate_hsg,
        {"root": Path("hsg.tif"), "sheet": _SHEET, "depth": "0-5cm"},
        "root",
        None,
        None,
        "--root is a store directory",
    ),
    _row(
        kartograf.calculate_hsg,
        {"root": _STORE, "sheet": _SHEET},
        "depth",
        None,
        _DEPTHS,
        "--depth required",
    ),
    _row(
        kartograf.calculate_hsg,
        {"root": _STORE, "sheet": _SHEET, "depth": "1m"},
        "depth",
        None,
        _DEPTHS,
        "Invalid depth: 1m",
    ),
    _row(
        kartograf.check_hsg,
        {"root": _STORE, "depth": "0-5cm"},
        None,
        _AREA_NAMES,
        None,
        "Give exactly one selection",
    ),
    _row(
        kartograf.calculate_hsg,
        {"root": _STORE, "sheet": _SHEET, "depth": "0-5cm", "plan": object()},
        None,
        ("plan", "update"),
        None,
        "The update plan requires update='upgrade'",
    ),
]


def _assert_option_scenario(function, arguments, expected, text, tmp_path):
    arguments = {
        name: tmp_path if value is _STORE else value
        for name, value in arguments.items()
    }
    with pytest.raises(ValidationError) as caught:
        function(**arguments)
    error = caught.value
    assert (error.option, error.options, error.allowed) == expected
    assert text in str(error)


@pytest.mark.parametrize(
    ("function", "arguments", "expected", "text"), COLLECTION_OPTION_SCENARIOS
)
def test_collection_input_error_names_the_option(
    function, arguments, expected, text, tmp_path
):
    _assert_option_scenario(function, arguments, expected, text, tmp_path)


@pytest.mark.parametrize(
    ("function", "arguments", "expected", "text"), LANDCOVER_OPTION_SCENARIOS
)
def test_landcover_soil_and_hsg_input_error_names_the_option(
    function, arguments, expected, text, tmp_path
):
    _assert_option_scenario(function, arguments, expected, text, tmp_path)


# --- option/allowed of the data validators (download_data, check_data) ---------
# The same rule as above: one row per message class, through the public entry
# points; ``allowed`` comes from the registries the message lists.

_PL_SHEET = "N-34-130-D-d-2-4"
_DATA_PRODUCTS = (
    "nmt",
    "nmpt",
    "orto",
    "laz",
    "contours",
    "intensity",
    "true-orto",
    "oblique-orto",
)
_NMT = {
    "product": "nmt",
    "root": _STORE,
    "sheet": _PL_SHEET,
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
}
_NMT_AREA = {
    "product": "nmt",
    "root": _STORE,
    "bbox": _AREA,
    "country": "pl",
    "sheet_system": "1992",
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
}
_ORTO_CUTOUT = {
    "product": "orto",
    "root": _STORE,
    "bbox": _AREA,
    "country": "pl",
    "cutout": True,
    "horizontal_crs": "EPSG:2180",
}
_ORTO_KEY = "pl.gugik.orto"


def _pl_labels(product: str) -> tuple[str, ...]:
    """The grid resolutions of the PL variants in the product format."""
    steps = {
        v.resolution_m
        for v in variants(product=product, country="PL")
        if not v.source_file and v.resolution_m is not None
    }
    return tuple(resolution_label(step) for step in sorted(steps))


OPTION_SCENARIOS = [
    _row(
        kartograf.download_data,
        {**_NMT, "product": None},
        "product",
        None,
        _DATA_PRODUCTS,
        "--product wymagane",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "product": "xyz"},
        "product",
        None,
        _DATA_PRODUCTS,
        "nieznana wartosc",
    ),
    _row(
        kartograf.check_data,
        {**_NMT, "product": None},
        "product",
        None,
        _DATA_PRODUCTS,
        "--product wymagane",
    ),
    _row(
        require_product,
        {"product": "orto", "products": ("nmt", "nmpt")},
        "product",
        None,
        ("nmt", "nmpt"),
        "nieznana wartosc",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "vertical_crs": None},
        "vertical_crs",
        None,
        ("EVRF2007", "KRON86"),
        "--vertical-crs wymagane dla --product nmt (PL)",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "vertical_crs": "XYZ"},
        "vertical_crs",
        None,
        ("EVRF2007", "KRON86"),
        "nie jest ukladem wysokosci PL",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "resolution": None},
        "resolution",
        None,
        _pl_labels("nmt"),
        "--resolution required for NMT PL",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "resolution": "7m"},
        "resolution",
        None,
        _pl_labels("nmt"),
        "PL has no resolution 7m",
    ),
    _row(
        kartograf.download_data,
        {"product": "nmt", "root": _STORE},
        None,
        _AREA_NAMES,
        None,
        "Podaj wybor obszaru",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "bbox": _AREA},
        None,
        ("sheet", "bbox"),
        None,
        "Podaj dokladnie jeden wybor",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "bbox": kartograf.BBox(5, 5, 1, 1, "EPSG:2180")},
        "bbox",
        None,
        None,
        "bbox is inverted",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "bbox": kartograf.BBox(5, 5, 5, 5, "EPSG:2180")},
        "bbox",
        None,
        None,
        "with zero area",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "bbox": kartograf.BBox(1, 5, 4, 5, "EPSG:2180")},
        "bbox",
        None,
        None,
        "with zero area",
    ),
    _row(
        kartograf.download_data,
        {
            **_NMT_AREA,
            "bbox": kartograf.BBox(626000, 480000, 628000, 482000, "EPSG:4326"),
        },
        "bbox",
        None,
        None,
        "Invalid bbox: coordinates",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "bbox": kartograf.BBox(19, 91, 20, 92, "EPSG:4326")},
        "bbox",
        None,
        None,
        "Invalid bbox: coordinates",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "workers": 0},
        "workers",
        None,
        None,
        "--workers musi byc >= 1, podano 0",
    ),
    _row(
        kartograf.check_data,
        {
            **_NMT_AREA,
            "bbox": kartograf.BBox(626000, 480000, 628000, 482000, "EPSG:4326"),
        },
        "bbox",
        None,
        None,
        "Invalid bbox: coordinates",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "bbox": kartograf.BBox(1, 2, 3, 4, "EPSG:9999")},
        "bbox",
        None,
        BBOX_CRS_CHOICES,
        "unsupported CRS",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "sheet_system": "1965"},
        "sheet_system",
        None,
        ("1992", "2000"),
        "nieznana wartosc",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "sheet_system": None},
        "sheet_system",
        None,
        ("1992", "2000"),
        "--sheet-system wymagane",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "scale": "1:9999", "sheet_system": "2000"},
        "scale",
        None,
        ("1:5000", "1:2000", "1:1000", "1:500"),
        "Nieznana skala PL-2000",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "sheet_system": "2000"},
        "scale",
        None,
        ("1:5000", "1:2000", "1:1000", "1:500"),
        "--scale wymagane dla arkuszy PL-2000",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "country": "xx"},
        "country",
        None,
        ("pl", "cz", "auto"),
        "nieznana wartosc",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "country": None},
        "country",
        None,
        ("pl", "cz", "auto"),
        "--country wymagane z --bbox/--geometry",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "min_year": 2025, "max_year": 2020},
        None,
        ("min_year", "max_year"),
        None,
        "nie moze byc wiekszy",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "year": 1800},
        "year",
        None,
        None,
        "--year musi byc liczba calkowita",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "year": "2018"},
        "year",
        None,
        None,
        "--year musi byc liczba calkowita",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "max_year": 2100 + 1},
        "max_year",
        None,
        None,
        "--max-year musi byc liczba calkowita",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "year": 2020, "min_year": 2019},
        None,
        ("year", "min_year"),
        None,
        "--year wyklucza sie",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "cutout": "no"},
        "cutout",
        None,
        None,
        "musi byc przelacznikiem",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "min_density": "5"},
        "min_density",
        None,
        None,
        "--min-density musi byc liczba calkowita",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "workers": "2"},
        "workers",
        None,
        None,
        "--workers musi byc liczba calkowita",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "layer": "obszar"},
        None,
        ("layer", "geometry"),
        None,
        "--layer dotyczy tylko --geometry",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "resolution": {"xx": "1m"}},
        "resolution",
        None,
        None,
        "nieprawidlowa wartosc",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "cutout": True, "horizontal_crs": "EPSG:2180"},
        None,
        ("cutout", "sheet"),
        None,
        "--cutout dziala tylko z --bbox/--geometry",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "cutout": True},
        "horizontal_crs",
        None,
        CUTOUT_CRS,
        "--horizontal-crs wymagane z --cutout",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "horizontal_crs": "EPSG:2180"},
        None,
        ("horizontal_crs", "cutout"),
        None,
        "dziala tylko z --cutout",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "cutout": True, "horizontal_crs": "EPSG:1"},
        "horizontal_crs",
        None,
        CUTOUT_CRS,
        "nieznana wartosc",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "cutout": True, "horizontal_crs": "EPSG:2180", "year": 2020},
        None,
        ("year", "cutout"),
        None,
        "--year nie dziala z --cutout",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "model": "dmr5g"},
        None,
        ("model", "product"),
        None,
        "--model dotyczy tylko --product laz",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "resolution": "1m", "product": "laz"},
        "resolution",
        None,
        None,
        "--resolution nie dotyczy LAZ",
    ),
    _row(
        kartograf.download_data,
        {"product": "orto", "root": _STORE, "sheet": _PL_SHEET, "format": "ASC"},
        "format",
        None,
        None,
        "--format dotyczy tylko --product nmt i nmpt",
    ),
    _row(
        kartograf.download_data,
        {**_NMT_AREA, "resolution": "100m", "sheet_system": "1992"},
        None,
        ("sheet_system", "resolution"),
        None,
        "nie dotyczy --resolution 100m",
    ),
    _row(
        kartograf.download_data,
        {"product": "contours", "root": _STORE, "sheet": "CTES96"},
        "format",
        None,
        contours_formats(),
        "--format wymagane dla --product contours",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "contours",
            "root": _STORE,
            "sheet": "CTES96",
            "format": "SHP",
            "resolution": "5m",
        },
        "resolution",
        None,
        None,
        "--resolution nie dotyczy --product contours",
    ),
    _row(
        kartograf.download_data,
        {"product": "nmt", "root": _STORE, "sheet": "CTES96"},
        "vertical_crs",
        None,
        ("Bpv", "EVRF2007"),
        "--vertical-crs wymagane dla NMT CZ",
    ),
    _row(
        kartograf.download_data,
        {"product": "nmt", "root": _STORE, "sheet": "CTES96", "format": "ASC"},
        "format",
        None,
        None,
        "--format dotyczy w CZ tylko --product contours",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "nmt",
            "root": _STORE,
            "sheet": "CTES96",
            "vertical_crs": "Bpv",
            "resolution": "7m",
        },
        "resolution",
        None,
        ("2m", "5m"),
        "CZ has no 7m resolution",
    ),
    _row(
        kartograf.download_data,
        {"product": "laz", "root": _STORE, "sheet": "CTES96"},
        "model",
        None,
        cz_models(),
        "--model required for --product laz in CZ",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "orto",
            "root": _STORE,
            "sheet": "CTES96",
            "vertical_crs": "Bpv",
        },
        "vertical_crs",
        None,
        None,
        "--vertical-crs nie dotyczy --product orto",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "nmt",
            "root": _STORE,
            "bbox": _AREA,
            "country": "cz",
            "vertical_crs": "Bpv",
            "resolution": "5m",
        },
        None,
        ("cutout", "horizontal_crs"),
        None,
        "dodaj --cutout --horizontal-crs",
    ),
    _row(
        kartograf.download_data,
        {**_ORTO_CUTOUT, "resolution": "0.1m"},
        "coverage",
        None,
        ("standard", "high"),
        "--coverage required with --cutout --product orto",
    ),
    _row(
        kartograf.download_data,
        {**_ORTO_CUTOUT, "coverage": "standard", "resolution": "7m"},
        "resolution",
        None,
        tuple(cutout_resolution_labels(_ORTO_KEY, "standard")),
        "not available for the standard orthophoto cutout",
    ),
    _row(
        kartograf.download_data,
        {
            **_ORTO_CUTOUT,
            "coverage": "standard",
            "resolution": cutout_resolution_labels(_ORTO_KEY, "standard")[0],
            "horizontal_crs": "EPSG:5514",
        },
        "horizontal_crs",
        None,
        ("EPSG:2180",),
        "wycinek ortofotomapy tylko EPSG:2180",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "oblique-orto",
            "root": _STORE,
            "sheet": "7.125.11.08",
            "direction": "x",
        },
        "direction",
        None,
        ("n", "e", "s", "w"),
        "--direction 'x': nieznana wartosc",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "direction": "n"},
        None,
        ("direction", "product"),
        None,
        "--direction dotyczy tylko --product",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "update": "bogus"},
        "update",
        None,
        ("upgrade", "force"),
        "Nieznany tryb update",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "update": "check"},
        "update",
        None,
        ("upgrade", "force"),
        "update='check' niczego nie pobiera",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "plan": object()},
        None,
        ("plan", "update"),
        None,
        "Plan aktualizacji wymaga update='upgrade'",
    ),
    _row(
        kartograf.download_data,
        {**_NMT, "country": "cz"},
        None,
        ("sheet", "country"),
        None,
        "nalezy do systemu",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "contours",
            "root": _STORE,
            "sheet": _PL_SHEET,
            "format": "SHP",
        },
        None,
        ("product", "sheet"),
        None,
        "nie ma danych PL",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "laz",
            "root": _STORE,
            "sheet": _PL_SHEET,
            "vertical_crs": "EVRF2007",
            "model": "dmr5g",
        },
        None,
        ("model", "sheet"),
        None,
        "pomin --model dla PL",
    ),
    _row(
        kartograf.download_data,
        {
            **_NMT_AREA,
            "country": "pl",
            "bbox": kartograf.BBox(0, 0, 10, 10, "EPSG:2180"),
        },
        "bbox",
        None,
        None,
        "lies outside PL",
    ),
    _row(
        kartograf.download_data,
        {
            **_NMT_AREA,
            "country": "auto",
            "bbox": kartograf.BBox(0, 0, 10, 10, "EPSG:2180"),
        },
        "bbox",
        None,
        None,
        "obszar nie przecina zasiegu zadnego znanego kraju",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "nmt",
            "root": _STORE,
            "sheet": "CTES96",
            "vertical_crs": "Bpv",
            "year": 2020,
        },
        "year",
        None,
        None,
        "CZ (CUZK) nie ma kampanii",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "nmt",
            "root": _STORE,
            "sheet": "CTES96",
            "vertical_crs": "Bpv",
            "all_campaigns": True,
            "min_year": 2020,
        },
        None,
        ("all_campaigns", "min_year"),
        None,
        "CZ (CUZK) nie ma kampanii",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "contours",
            "root": _STORE,
            "bbox": _AREA,
            "country": "pl",
            "format": "SHP",
        },
        None,
        ("product", "country"),
        None,
        "jest dostepny tylko dla CZ",
    ),
    _row(
        kartograf.download_data,
        {
            "product": "laz",
            "root": _STORE,
            "bbox": kartograf.BBox(18.6300, 49.7450, 18.6303, 49.7452, "EPSG:4326"),
            "country": "auto",
            "vertical_crs": "EVRF2007",
        },
        "model",
        None,
        cz_models(),
        "obszar siega CZ: podaj --model",
    ),
    _row(
        kartograf.check_availability,
        {"product": None, "sheet": _PL_SHEET, "country": "pl", "cache": False},
        "product",
        None,
        ("nmt", "nmpt", "laz"),
        "--product wymagane",
    ),
    _row(
        kartograf.check_availability,
        {"product": "orto", "sheet": _PL_SHEET, "cache": False},
        "product",
        None,
        ("nmt", "nmpt", "laz"),
        "nieznana wartosc",
    ),
    _row(
        kartograf.check_availability,
        {"product": "nmt", "bbox": _AREA, "cache": False},
        "country",
        None,
        ("pl", "cz", "auto"),
        "--country wymagane z --bbox/--geometry",
    ),
    _row(
        kartograf.check_availability,
        {"product": "nmt", "sheet": _PL_SHEET, "country": "xx", "cache": False},
        "country",
        None,
        ("pl", "cz", "auto"),
        "raport dostepnosci obejmuje",
    ),
    _row(
        kartograf.check_availability,
        {"product": "nmt", "sheet": _PL_SHEET, "country": "cz", "cache": False},
        None,
        ("sheet", "country"),
        None,
        "nalezy do systemu",
    ),
    _row(
        kartograf.check_availability,
        {"product": "nmt", "bbox": _AREA, "sheet": _PL_SHEET, "cache": False},
        None,
        ("sheet", "bbox"),
        None,
        "Podaj dokladnie jeden wybor",
    ),
    _row(
        kartograf.check_availability,
        {
            "product": "nmt",
            "sheet": _PL_SHEET,
            "min_year": 2025,
            "max_year": 2020,
            "cache": False,
        },
        None,
        ("min_year", "max_year"),
        None,
        "nie moze byc wiekszy",
    ),
    _row(
        kartograf.check_availability,
        {"product": "nmt", "sheet": _PL_SHEET, "min_year": 1800, "cache": False},
        "min_year",
        None,
        None,
        "--min-year musi byc liczba calkowita",
    ),
    _row(
        kartograf.check_availability,
        {"product": "nmt", "sheet": "CTES96", "year": 2020, "cache": False},
        "year",
        None,
        None,
        "CZ (CUZK) nie publikuje lat nalotu",
    ),
    _row(
        kartograf.check_availability,
        {
            "product": "nmt",
            "sheet": "CTES96",
            "min_year": 2020,
            "max_year": 2021,
            "cache": False,
        },
        None,
        ("min_year", "max_year"),
        None,
        "CZ (CUZK) nie publikuje lat nalotu",
    ),
    _row(
        kartograf.check_availability,
        {"product": "nmt", "sheet": _PL_SHEET, "year": 1901, "cache": False},
        "year",
        None,
        None,
        "nie ma rocznika",
    ),
    _row(
        kartograf.check_availability,
        {
            "product": "nmt",
            "sheet": _PL_SHEET,
            "min_year": 1901,
            "max_year": 1905,
            "cache": False,
        },
        None,
        ("min_year", "max_year"),
        None,
        "nie ma rocznika",
    ),
    _row(
        kartograf.check_availability,
        {
            "product": "nmt",
            "bbox": kartograf.BBox(5, 5, 1, 1, "EPSG:2180"),
            "country": "pl",
            "cache": False,
        },
        "bbox",
        None,
        None,
        "bbox is inverted",
    ),
    _row(
        kartograf.check_availability,
        {
            "product": "nmt",
            "bbox": kartograf.BBox(565000, 242000, 569000, 246000, "EPSG:2180"),
            "country": "cz",
            "cache": False,
        },
        "bbox",
        None,
        None,
        "lies outside CZ",
    ),
    _row(
        kartograf.check_availability,
        {
            "product": "nmt",
            "bbox": kartograf.BBox(9.9, 53.5, 10.0, 53.6, "EPSG:4326"),
            "country": "pl",
            "cache": False,
        },
        "bbox",
        None,
        None,
        "lies outside PL",
    ),
    _row(
        kartograf.check_availability,
        {
            "product": "nmt",
            "bbox": kartograf.BBox(5, 5, 5, 5, "EPSG:2180"),
            "country": "pl",
            "cache": False,
        },
        "bbox",
        None,
        None,
        "with zero area",
    ),
]


@pytest.mark.parametrize(
    ("function", "arguments", "expected", "text"), OPTION_SCENARIOS
)
def test_input_error_names_the_option(function, arguments, expected, text, tmp_path):
    _assert_option_scenario(function, arguments, expected, text, tmp_path)


@pytest.mark.parametrize("function", [kartograf.download_data, kartograf.check_data])
def test_malformed_sheet_is_a_parse_error_naming_the_sheet(function, tmp_path):
    """The sheet code is parsed by ``SheetParser`` (``ParseError``); the error
    of the caller's argument carries ``option="sheet"``."""
    arguments = {**_NMT, "root": tmp_path, "sheet": "XYZ"}

    with pytest.raises(ParseError) as caught:
        function(**arguments)

    assert caught.value.option == "sheet"
    assert (caught.value.code, caught.value.reason) == (
        "validation_error",
        "invalid_sheet_code",
    )


def test_malformed_sheet_of_the_availability_report_is_a_parse_error(tmp_path):
    for sheet in ("XYZ", "302_5551"):  # not a PL code; a TM33 tile off the 2 km grid
        country = "pl" if sheet == "XYZ" else "cz"
        with pytest.raises(ParseError) as caught:
            kartograf.check_availability(
                product="nmt", sheet=sheet, country=country, cache=False
            )

        assert caught.value.option == "sheet"


STORE_OPTION_SCENARIOS = [
    _row(
        kartograf.iter_store,
        {"root": _STORE, "segment": "zly"},
        "segment",
        None,
        None,
        "Invalid store segment",
    ),
    _row(
        kartograf.iter_store,
        {"root": _STORE, "units": ["x"]},
        "units",
        None,
        None,
        "units needs segment",
    ),
    _row(
        kartograf.iter_store,
        {
            "root": _STORE,
            "segment": "nmt/pl_1992_1m_evrf2007",
            "units": ["versions"],
        },
        "units",
        None,
        None,
        "Invalid store unit",
    ),
    _row(
        kartograf.iter_store,
        {
            "root": _STORE,
            "segment": "nmt/pl_1992_1m_evrf2007",
            "units": "N-33-130-D-d-2-4",
        },
        "units",
        None,
        None,
        "give a collection of unit names",
    ),
    _row(
        kartograf.iter_store,
        {
            "root": _STORE,
            "segment": "nmt/pl_1992_1m_evrf2007",
            "skip_versions": "nmt/x",
        },
        "skip_versions",
        None,
        None,
        "give a collection of version directory paths",
    ),
    _row(
        kartograf.iter_store,
        {"root": _STORE, "partition": "."},
        "partition",
        None,
        None,
        "partition needs segment",
    ),
    _row(
        kartograf.iter_store,
        {
            "root": _STORE,
            "segment": "nmt/pl_1992_1m_evrf2007",
            "partition": "../x",
        },
        "partition",
        None,
        None,
        "Invalid part of a segment",
    ),
    _row(
        kartograf.iter_store,
        {
            "root": _STORE,
            "segment": "nmt/pl_1992_1m_evrf2007",
            "units": ["N-34-130-D-d-2-4"],
            "partition": ".",
        },
        None,
        ("units", "partition"),
        None,
        "units or partition",
    ),
    _row(
        kartograf.list_partitions,
        {"root": _STORE, "segment": "nmt/pl_1992_1m_evrf2007", "target": 0},
        "target",
        None,
        None,
        "give a positive number of parts",
    ),
]


@pytest.mark.parametrize(
    ("function", "arguments", "expected", "text"), STORE_OPTION_SCENARIOS
)
def test_store_input_error_names_the_option(
    function, arguments, expected, text, tmp_path
):
    _assert_option_scenario(function, arguments, expected, text, tmp_path)


def test_store_segment_that_is_a_symlink_names_the_segment(tmp_path):
    (tmp_path / "nmt").mkdir()
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "nmt" / "pl_1992_1m_evrf2007").symlink_to(
        tmp_path / "elsewhere", target_is_directory=True
    )

    with pytest.raises(ValidationError) as caught:
        kartograf.iter_store(tmp_path, segment="nmt/pl_1992_1m_evrf2007")

    assert caught.value.option == "segment"


def test_project_task_name_and_command_errors_name_the_option(tmp_path):
    project = kartograf.init_project(tmp_path / "p", root=tmp_path / "p" / "data")

    with pytest.raises(ValidationError) as bad_name:
        kartograf.add_project_task(
            project.directory,
            name="zla nazwa",
            command="soil hsg",
            options={"depth": "0-5cm"},
        )
    with pytest.raises(ValidationError) as bad_command:
        kartograf.add_project_task(
            project.directory, name="ok", command="project status", options={}
        )
    with pytest.raises(ValidationError) as unknown:
        kartograf.remove_project_task(project.directory, name="brak")

    assert (bad_name.value.option, bad_name.value.allowed) == ("name", None)
    assert bad_command.value.option == "command"
    assert "elevation download" in (bad_command.value.allowed or ())
    assert "project status" not in (bad_command.value.allowed or ())
    assert (unknown.value.option, unknown.value.allowed) == ("name", None)


def test_project_download_update_and_workers_name_the_option(tmp_path):
    project = kartograf.init_project(tmp_path / "p", root=tmp_path / "p" / "data")

    with pytest.raises(ValidationError) as bad_update:
        kartograf.download_project(project.directory, update="x")
    with pytest.raises(ValidationError) as bad_workers:
        kartograf.download_project(project.directory, workers=0)

    assert (bad_update.value.option, bad_update.value.allowed) == (
        "update",
        ("upgrade", "force"),
    )
    assert bad_workers.value.option == "workers"
