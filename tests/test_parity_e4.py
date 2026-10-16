"""CLI and public API produce identical versioned stores for the E4 sources
(``landcover download --source bdoo|data50|data250`` =
``LandCoverManager(out, source).download``): BDOO of a voivodeship and of an
area with ``--layers``, Data50 objects of an area, the Data250 national file,
and the same first error for invalid choices (recorded answers of
``tests/test_bdoo.py`` and ``tests/test_cz_data50_250.py``)."""

import pytest

from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.notices import CLASSES_ABSENT, UNIT_LIST, WHOLE_COUNTRY_SIZE
from tests.fake_packages import zip_bytes
from tests.parity import assert_notices_printed, assert_same_store, run_both
from tests.test_bdoo import BORDER, TRIMMED, route, serve
from tests.test_collections_cz import _page_size
from tests.test_cz_data50_250 import AREA, DATA50, DATA250, NATIONAL
from tests.test_cz_data50_250 import serve as serve_cuzk

pytestmark = pytest.mark.usefixtures("frozen_clock")


def _landcover(tmp_path, source: str, cli_args: list[str], **api_kwargs):
    return run_both(
        ["landcover", "download", "--source", source, *cli_args],
        lambda out: LandCoverManager(out, source).download(**api_kwargs),
        tmp_path,
    )


def _same(run, statuses: list[str]) -> None:
    assert run.cli_code == 0, run.cli_stderr
    assert run.api_result.ok, run.api_result.failed
    assert_same_store(run.cli_store, run.api_store)
    assert_notices_printed(run.cli_stderr, run.api_result.notices)
    assert [item.file.status for item in run.api_result.files] == statuses


def test_bdoo_teryt(tmp_path, monkeypatch):
    serve(monkeypatch, route("bdoo_2023_12", TRIMMED.read_bytes()))
    run = _landcover(
        tmp_path, "bdoo", ["--teryt", "12", "--year", "2023"], teryt="12", year=2023
    )
    _same(run, ["new"])
    assert run.cli_stdout.splitlines() == [
        "landcover/pl_bdoo_2023/teryt/12.zip: nowa wersja 2023_"
        + run.api_result.files[0].file.sha256[:8]
    ]


def test_bdoo_area_layers(tmp_path, monkeypatch):
    """An area of two voivodeships with ``--layers``: the class files of
    each package, an ``Info`` for the class a package has no file of (KUIK
    in 24, PTWP in the trimmed 12) and one summary line."""
    serve(
        monkeypatch,
        route("bdoo_2023_12", TRIMMED.read_bytes()),
        route("bdoo_2023_24"),
    )
    run = _landcover(
        tmp_path,
        "bdoo",
        [
            "--bbox",
            "523000,253000,528000,258000",
            "--year",
            "2023",
            "--layers",
            "PTWP,KUIK",
        ],
        bbox=BORDER,
        year=2023,
        layers=["PTWP", "KUIK"],
    )
    _same(run, ["new", "new"])
    assert [n.code for n in run.api_result.notices] == [
        UNIT_LIST,
        CLASSES_ABSENT,
        CLASSES_ABSENT,
    ]
    assert run.cli_stdout.splitlines()[-1] == (
        "Nowe: 2, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 0 "
        f"({run.cli_store})"
    )


def test_data50_area(tmp_path, monkeypatch):
    _page_size(monkeypatch, DATA50.key, 1, sources=set(DATA50.layers))
    serve_cuzk(monkeypatch, DATA50)
    run = _landcover(
        tmp_path,
        "data50",
        ["--bbox", "18.566,49.757,18.572,49.761", "--bbox-crs", "EPSG:4326"],
        bbox=AREA,
    )
    _same(run, ["new"])


def test_data250_whole_country(tmp_path, monkeypatch):
    serve_cuzk(monkeypatch, DATA250, zip_bytes(NATIONAL["data250"]["members"]))
    run = _landcover(
        tmp_path,
        "data250",
        ["--whole-country", "--horizontal-crs", "EPSG:5514"],
        whole_country=True,
        horizontal_crs="EPSG:5514",
    )
    _same(run, ["new"])
    assert [n.code for n in run.api_result.notices] == [WHOLE_COUNTRY_SIZE]


@pytest.mark.parametrize(
    ("source", "flags", "options"),
    [
        ("bdoo", ["--teryt", "12"], {"teryt": "12"}),  # --year required
        ("bdoo", ["--teryt", "12", "--year", "2018"], {"teryt": "12", "year": 2018}),
        (
            "bdoo",
            ["--teryt", "1261", "--year", "2023"],
            {"teryt": "1261", "year": 2023},
        ),
        (
            "bdoo",
            ["--teryt", "12", "--year", "2024", "--layers", "KUIK"],
            {"teryt": "12", "year": 2024, "layers": ("KUIK",)},
        ),
        (
            "bdoo",
            ["--teryt", "12", "--year", "2023", "--format", "GML"],
            {"teryt": "12", "year": 2023, "format": "GML"},
        ),
        ("bdoo", ["--whole-country"], {"whole_country": True}),
        ("data50", ["--whole-country"], {"whole_country": True}),
        ("data250", ["--teryt", "12"], {"teryt": "12"}),
        (
            "data50",
            ["--bbox", "18.566,49.757,18.572,49.761", "--bbox-crs", "EPSG:4326"]
            + ["--layers", "les"],
            {"bbox": AREA, "layers": ("les",)},
        ),
    ],
)
def test_invalid_options_match_cli_and_api(
    tmp_path, monkeypatch, source, flags, options
):
    fake = serve(monkeypatch)
    run = _landcover(tmp_path, source, flags, **options)
    assert run.cli_code == 1 and isinstance(run.api_error, ValidationError)
    assert run.cli_stderr == f"Error: {run.api_error}\n"
    assert not run.cli_store.exists() and not run.api_store.exists()
    assert fake.calls == []
