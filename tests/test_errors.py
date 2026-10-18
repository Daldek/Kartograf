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
        {"product": None, "output_dir": _STORE, "teryt": "1261"},
        "product",
        None,
        _COLLECTIONS.collection_products(),
        "--product wymagane",
    ),
    _row(
        kartograf.download_collection,
        {"product": "xyz", "output_dir": _STORE, "teryt": "1261"},
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
        {"product": "buildings", "output_dir": None, "teryt": "1261", "lod": 2},
        "output_dir",
        None,
        None,
        "--output wymagane",
    ),
    _row(
        kartograf.download_collection,
        {"product": "buildings", "output_dir": _STORE, "lod": 1, "year": 2024},
        None,
        ("teryt", *_AREA_NAMES),
        None,
        "Podaj dokladnie jeden wybor",
    ),
    _row(
        kartograf.check_collection,
        {
            "product": "buildings",
            "output_dir": _STORE,
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
        {"product": "map", "output_dir": _STORE, "bbox": _AREA, "country": "xx"},
        "country",
        None,
        ("pl", "cz", "auto"),
        "Nieznany kraj --country 'xx'",
    ),
    _row(
        kartograf.download_collection,
        {"product": "map", "output_dir": _STORE, "bbox": _AREA},
        "country",
        None,
        ("pl", "cz", "auto"),
        "--country wymagane z --bbox/--geometry",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "buildings",
            "output_dir": _STORE,
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
        {"product": "buildings", "output_dir": _STORE, "teryt": "9901", "lod": 2},
        "teryt",
        None,
        None,
        "Nieprawidlowy kod TERYT",
    ),
    _row(
        kartograf.download_collection,
        {"product": "map", "output_dir": _STORE, "ku": "623164", "country": "pl"},
        None,
        ("ku", "country"),
        None,
        "usun --country pl",
    ),
    _row(
        kartograf.download_collection,
        {"product": "map", "output_dir": _STORE, "ku": "12", "country": "cz"},
        "ku",
        None,
        None,
        "Nieprawidlowy kod katastralniho uzemi",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "admin",
            "output_dir": _STORE,
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
            "output_dir": _STORE,
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
            "output_dir": _STORE,
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
            "output_dir": _STORE,
            "country": "pl",
            "sheet": _SHEET,
            "format": "XYZ",
        },
        "format",
        None,
        ("TIFF", "PDF"),
        "--format XYZ: niedostepne",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "map",
            "output_dir": _STORE,
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
            "output_dir": _STORE,
            "country": "cz",
            "bbox": _AREA,
            "scale": "1:1",
        },
        "scale",
        None,
        _COLLECTIONS.collection_choice_values("topographic", "scale")["CZ"],
        "--scale 1:1: niedostepne",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "topographic",
            "output_dir": _STORE,
            "country": "cz",
            "bbox": _AREA,
            "sheet_system": "1965",
        },
        "sheet_system",
        None,
        ("sjtsk", "etrs89"),
        "--sheet-system 1965: niedostepne",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "map",
            "output_dir": _STORE,
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
        {"product": "buildings", "output_dir": _STORE, "teryt": "1261"},
        "lod",
        None,
        ("1", "2"),
        "--lod wymagane",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "buildings",
            "output_dir": _STORE,
            "teryt": "1261",
            "lod": 2,
            "year": 2016,
        },
        "year",
        None,
        ("2017",),
        "--year 2016: niedostepne dla --lod 2",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "admin",
            "output_dir": _STORE,
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
            "output_dir": _STORE,
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
            "output_dir": _STORE,
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
            "output_dir": _STORE,
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
        {"product": "admin", "output_dir": _STORE, "country": "pl", "bbox": _AREA},
        "level",
        None,
        _COLLECTIONS.collection_levels("admin")["PL"],
        "--level wymagane",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "admin",
            "output_dir": _STORE,
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
            "output_dir": _STORE,
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
        {"product": "control", "output_dir": _STORE, "country": "pl", "bbox": _AREA},
        "network",
        None,
        _COLLECTIONS.collection_choice_values("control", "network")["PL"],
        "--network wymagane dla obszaru control (PL)",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "prices",
            "output_dir": _STORE,
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
            "output_dir": _STORE,
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
            "output_dir": _STORE,
            "country": "pl",
            "bbox": kartograf.BBox(1, 1, 2, 2, "EPSG:2180"),
        },
        "bbox",
        None,
        None,
        "lezy poza PL",
    ),
    _row(
        kartograf.download_collection,
        {
            "product": "buildings",
            "output_dir": _STORE,
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
            "output_dir": _STORE,
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
