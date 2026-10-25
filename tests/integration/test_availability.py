"""check_availability (spec 4, ADR-041; CZ and ``auto``: plan B, decisions
9-10) on recorded GUGiK and CUZK answers.

Index: the recorded WFS answers of 2026-10-15 (``tests/fixtures/gugik_wfs/
real_2026_10_15``: areas of Krakow, Pomorze and the PL part of Cieszyn,
sheets); ``RecordedIndex`` answers a sheet query with a slice of the
recorded area. Land mask: the PRG answers of
``tests/fixtures/gugik_prg/land_mask_2026_10_11`` (Krakow and Cieszyn
inland, Pomorze coast). CZ: the CUZK answers of 2026-10-15
(``tests/fixtures/cuzk/real_2026_10_15``: ``KladyMapovychListu`` for the
Cieszyn/Cesky Tesin border area, openzu ``HEAD`` headers) replayed by
``CuzkSession``. Expected values: plan A, "Weryfikacja" point 9 and spec 4.4
(measured 2026-10-15), with the archives downloaded since decision 13.
"""

import dataclasses
import functools
import json
import shlex
from unittest.mock import patch

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.cli._args import library_arguments
from kartograf.cli._parser import create_parser
from kartograf.core.bbox import BBox
from kartograf.download.availability import (
    AVAILABILITY_SCHEMA,
    AvailabilityArea,
    AvailabilityReport,
    check_availability,
)
from kartograf.download.data import check_data, download_data, validate_data_request
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.notices import (
    AUTO_NARROWED_TO_PL,
    CHECK_FAILED,
    CZ_SERVICE_ONLY,
    INDEX_UNSUPPORTED,
)
from kartograf.providers.cuzk.raster import bbox_to_crs
from kartograf.sources.variants import variants
from kartograf.transport.http import MAX_RETRIES
from tests.conftest import (
    RecordedIndex,
    render_wfs_body,
    wfs_endpoint,
    wfs_fixture,
    wfs_record,
    wfs_response,
)
from tests.integration.test_cuzk_laz import (
    CIESZYN,
    CIESZYN_3045,
    OPENZU,
    CuzkSession,
    _response,
    recorded_json,
)

KRAKOW = BBox(565000, 242000, 569000, 246000, "EPSG:2180")
POMORZE = BBox(339000, 744800, 343000, 747000, "EPSG:2180")
# The land of the Pomorze bbox spans E 340037-343000, N 744800-745663
# (PRG A00 minus W02/W03, 2026-10-11): the bbox without the sea part.
POMORZE_LAND = BBox(340037, 744800, 343000, 745663, "EPSG:2180")
POMORZE_2025_PARTIAL = (
    "N-33-58-A-c-1-3",
    "N-33-58-A-c-1-4",
    "N-33-58-A-c-2-3",
    "N-33-58-A-c-3-1",
)
SESSION = "kartograf.transport.http.make_gugik_session"
PRG = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries"


def _areas(product: str, place: str) -> dict[str, list[str]]:
    return {
        f"{product}_{vcrs}": [f"area_{product}_{vcrs}_{place}.xml.gz"]
        for vcrs in ("evrf2007", "kron86")
    }


def _check(session, **kwargs) -> AvailabilityReport:
    with patch(SESSION, return_value=session):
        return check_availability(**{"cache": False, **kwargs})


def _krakow(product: str = "nmt", **kwargs) -> tuple[AvailabilityReport, RecordedIndex]:
    session = RecordedIndex(_areas(product, "krakow"))
    report = _check(session, product=product, country="pl", bbox=KRAKOW, **kwargs)
    return report, session


def _pomorze(
    product: str = "nmt", bbox: BBox = POMORZE
) -> tuple[AvailabilityReport, RecordedIndex]:
    session = RecordedIndex(_areas(product, "pomorze"), coast=True)
    report = _check(session, product=product, country="pl", bbox=bbox)
    return report, session


@functools.cache
def _report(product: str, place: str) -> AvailabilityReport:
    """The report of a recorded area, computed once per run (immutable;
    tests asserting requests build their own)."""
    return (_krakow(product) if place == "krakow" else _pomorze(product))[0]


def _combo(report, year, horizontal, resolution, vcrs="EVRF2007", fmt="ASC"):
    found = [
        c
        for c in report.combinations
        if (c.year, c.horizontal, c.resolution, c.vertical_crs, c.format)
        == (year, horizontal, resolution, vcrs, fmt)
    ]
    assert len(found) == 1, (year, horizontal, resolution, vcrs, fmt)
    return found[0]


# =============================================================================
# Spec 4.4 on the recorded answers
# =============================================================================


def test_krakow_complete_combinations():
    report = _report("nmt", "krakow")

    for year in (2025, 2024, 2023, 2022, 2019):
        combo = _combo(report, year, "PL-1992", "1m")
        assert combo.complete and len(combo.sheets_full) == 6
        assert combo.sheets_partial == () and not combo.uncovered
        assert combo.source == "pl.gugik.nmt_1m"
    for year in (2023, 2021):
        combo = _combo(report, year, "PL-2000", "1m")
        assert combo.complete and len(combo.sheets_full) == 15
    assert _combo(report, 2019, "PL-1992", "5m").complete
    # 2018 has only archives (XYZ 1 m and 5 m, TBD 25 m), downloaded as
    # source files: combinations in their formats, none of them complete
    archives_2018 = {
        (c.format, c.resolution, len(c.sheets_full), c.complete)
        for c in report.combinations
        if c.year == 2018
    }
    assert archives_2018 == {
        ("XYZ", "1m", 4, False),
        ("XYZ", "5m", 2, False),
        ("TBD", "25m", 2, False),
    }
    assert [n.code for n in report.notices] == []
    (area,) = report.areas
    assert (area.country, area.crs, area.area_m2, area.land_m2) == (
        "PL",
        "EPSG:2180",
        16_000_000.0,
        16_000_000.0,
    )


def test_pomorze_partial_and_uncovered():
    report = _report("nmt", "pomorze")

    newest = _combo(report, 2025, "PL-1992", "0.5m")
    assert not newest.complete
    assert newest.sheets_partial == POMORZE_2025_PARTIAL
    assert newest.sheets_full == () and not newest.uncovered
    grid_2022 = _combo(report, 2022, "PL-1992", "1m")
    assert not grid_2022.complete and len(grid_2022.sheets_full) == 3
    assert grid_2022.uncovered and 8_700 <= grid_2022.uncovered_m2 <= 8_900
    (area,) = report.areas
    assert 863_000 <= area.land_m2 <= 864_500
    assert area.area_m2 == 8_800_000.0

    # the sea part of the bbox changes nothing
    land_only, _ = _pomorze(bbox=POMORZE_LAND)
    clipped = _combo(land_only, 2022, "PL-1992", "1m")
    assert clipped.uncovered_m2 == grid_2022.uncovered_m2
    assert land_only.areas[0].land_m2 == area.land_m2


def test_full_m2_is_the_land_in_full_sheets():
    """KD-2: ``complete`` <=> ``full_m2 == land_m2``; an incomplete
    combination: the land in its full sheets (lower bound), never more than
    the land in any of its sheets (upper bound, ``land_m2 - uncovered_m2``)."""
    land = _report("nmt", "pomorze").areas[0].land_m2
    for report in (_report("nmt", "krakow"), _report("nmt", "pomorze")):
        (area,) = report.areas
        for combo in report.combinations:
            assert (combo.full_m2 == area.land_m2) == combo.complete
            assert 0 <= combo.full_m2 <= area.land_m2 - combo.uncovered_m2
    pomorze = _report("nmt", "pomorze")
    # every sheet of 2022 1 m is full: only the land outside its sheets lacks
    grid_2022 = _combo(pomorze, 2022, "PL-1992", "1m")
    assert grid_2022.full_m2 == land - grid_2022.uncovered_m2
    # only partial sheets: nothing is surely covered, though no land is
    # outside the sheets
    newest = _combo(pomorze, 2025, "PL-1992", "0.5m")
    assert newest.full_m2 == 0.0 and newest.uncovered_m2 == 0.0


def test_full_m2_of_a_sheet_request_ignores_the_rim():
    """A sheet request measures without the rim of its frame (``_inner``),
    while ``land_m2`` is the whole frame: a complete combination still has
    ``full_m2 == land_m2`` and one of partial records only has 0 - the rim
    never counts as covered on its own."""
    report = _sheet_report("N-33-58-A-c-1-4", "E")
    (area,) = report.areas
    assert {(c.complete, c.full_m2) for c in report.combinations} == {
        (True, area.land_m2),
        (False, 0.0),
    }


def test_nmpt_and_kron86_from_their_services():
    report, session = _krakow("nmpt")

    for year in (2017, 2012):
        combo = _combo(report, year, "PL-1992", "0.5m", "KRON86")
        assert combo.complete and combo.source == "pl.gugik.nmpt_0_5m"
    assert _combo(report, 2025, "PL-1992", "0.5m").complete
    asked = {url.split("?")[0] for url in session.urls if "/Skorowidze?" in url}
    assert asked == {wfs_endpoint("nmpt_evrf2007"), wfs_endpoint("nmpt_kron86")}


def test_laz_full_tiles_only():
    report = _report("laz", "pomorze")

    newest = _combo(report, 2025, "PL-1992", None, fmt="LAZ")
    # 11 partial tiles: the land they cover does not make the year complete
    assert not newest.complete
    assert newest.sheets_partial and not set(newest.sheets_partial) & set(
        newest.sheets_full
    )
    assert newest.densities == (5,) and newest.source == "pl.gugik.laz"
    assert newest.resolution is None
    krakow = _report("laz", "krakow")
    assert _combo(krakow, 2025, "PL-1992", None, fmt="LAZ").complete


def test_laz_sheet_reports_the_tiles_of_its_frame():
    """Live test 0.8.0 (P2-1): like the download, a LAZ sheet is its frame -
    not the envelope with the 8 neighbouring 1:2500 tiles and +2.5 % area."""
    session = RecordedIndex(_areas("laz", "krakow"))
    report = _check(session, product="laz", sheet="M-34-64-D-d-1-4-2")

    newest = _combo(report, 2025, "PL-1992", None, fmt="LAZ")
    assert newest.complete
    assert newest.sheets_full == tuple(f"M-34-64-D-d-1-4-2-{i}" for i in range(1, 5))
    (area,) = report.areas
    assert 1_294_000 <= area.area_m2 <= 1_295_500  # the frame, envelope 1 326 743


# =============================================================================
# Contract
# =============================================================================


def test_availability_never_downloads():
    """Only index and PRG requests; any other URL fails in RecordedIndex."""
    report, session = _krakow()

    assert report.combinations
    assert all(
        url.startswith(("https://mapy.geoportal.gov.pl/wss/service/PZGIK/", PRG))
        for url in session.urls
    )
    assert not any("opendata" in url for url in session.urls)


def test_failure_is_error_not_empty():
    exception = wfs_response(wfs_fixture("exception_report.xml"), status=400)
    with pytest.raises(DownloadError, match="the result would be incomplete"):
        _check(
            RecordedIndex(
                _areas("nmt", "krakow"),
                fail={
                    f"{wfs_endpoint('nmt_kron86')}?SERVICE=WFS&VERSION=2.0.0"
                    "&REQUEST=GetFeature": exception
                },
            ),
            product="nmt",
            country="pl",
            bbox=KRAKOW,
        )

    first_page = render_wfs_body(
        [
            wfs_record(
                "M-34-64-D-d-2-1", akt_data="2025-04-01", layer="SkorowidzNMT2025"
            )
        ],
        next_url=f"{wfs_endpoint('nmt_evrf2007')}?STARTINDEX=1",
    )
    broken = RecordedIndex(
        fail={
            f"{wfs_endpoint('nmt_evrf2007')}?STARTINDEX=1": requests.ConnectionError(
                "reset"
            ),
            f"{wfs_endpoint('nmt_evrf2007')}?SERVICE=WFS&VERSION=2.0.0"
            "&REQUEST=GetFeature&TYPENAMES=gugik%3ASkorowidzNMT2025": wfs_response(
                first_page
            ),
        }
    )
    with patch("time.sleep"), pytest.raises(DownloadError, match="incomplete"):
        _check(broken, product="nmt", country="pl", bbox=KRAKOW, year=2025)

    with pytest.raises(DownloadError, match="PRG"):
        _check(
            RecordedIndex(fail={PRG: wfs_response("<html>blad</html>")}),
            product="nmt",
            country="pl",
            bbox=KRAKOW,
        )

    empty = _check(RecordedIndex(), product="nmt", country="pl", bbox=KRAKOW)
    assert empty.combinations == () and empty.ok


def test_year_bounds_select_layers():
    report, session = _krakow(year=2025)

    queries = [u for u in session.urls if "/Skorowidze?" in u and "GetFeature" in u]
    # KRON86 has no 2025 layer: one query, to EVRF2007, with one type
    assert len(queries) == 1
    assert queries[0].startswith(wfs_endpoint("nmt_evrf2007"))
    assert "TYPENAMES=gugik%3ASkorowidzNMT2025&" in queries[0]
    assert {c.year for c in report.combinations} == {2025}

    with pytest.raises(ValidationError) as error:
        _krakow(min_year=2030)
    text = str(error.value)
    assert "od roku 2030" in text
    assert "EVRF2007: 2026, 2025" in text and "KRON86: 2019, 2018" in text


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"sheet": "N-34-130-D-d-2-4", "bbox": KRAKOW}, id="two-areas"),
        pytest.param({}, id="no-area"),
        pytest.param(
            {"bbox": BBox(569000, 242000, 565000, 246000, "EPSG:2180")}, id="bad-bbox"
        ),
        pytest.param({"bbox": BBox(1, 2, 3, 4, "EPSG:9999")}, id="bbox-crs"),
        pytest.param(
            {"bbox": KRAKOW, "year": 2025, "min_year": 2020}, id="year-and-min"
        ),
        pytest.param(
            {"bbox": KRAKOW, "min_year": 2025, "max_year": 2020}, id="year-order"
        ),
    ],
)
def test_input_errors_same_as_download_data(tmp_path, kwargs):
    common = {"product": "nmt", "country": "pl", **kwargs}
    with pytest.raises(ValidationError) as api:
        download_data(root=tmp_path, vertical_crs="EVRF2007", **common)
    with pytest.raises(ValidationError) as report:
        check_availability(**common)

    assert str(report.value) == str(api.value)


def test_choices_of_the_report_are_validated_before_network():
    session = RecordedIndex()
    with pytest.raises(ValidationError, match=r"--product 'orto': nieznana"):
        _check(session, product="orto", country="pl", bbox=KRAKOW)
    with pytest.raises(ValidationError, match="--product wymagane"):
        _check(session, product=None, country="pl", bbox=KRAKOW)
    with pytest.raises(
        ValidationError, match=r"--country 'de'.*pl \(GUGiK\), cz \(CUZK\), auto"
    ):
        _check(session, product="nmt", country="de", bbox=KRAKOW)
    with pytest.raises(ValidationError, match="--country wymagane z --bbox"):
        _check(session, product="nmt", bbox=KRAKOW)
    with pytest.raises(
        ValidationError, match=r"systemu TM33 \(kraj CZ\), a podano --country pl"
    ):
        _check(session, product="nmt", country="pl", sheet="302_5550")
    with pytest.raises(ParseError):
        _check(session, product="nmt", sheet="N-34-999-X")
    with pytest.raises(ParseError, match="must be even"):
        _check(session, product="nmt", sheet="301_5550")
    assert session.urls == []


def test_cache_and_force(tmp_path):
    cache = MetadataCache(tmp_path / "cache.db")
    first, session = _krakow(cache=cache)
    assert session.urls

    offline = RecordedIndex(fail={"https://": AssertionError("network")})
    again = _check(offline, product="nmt", country="pl", bbox=KRAKOW, cache=cache)
    assert offline.urls == []
    assert again.combinations == first.combinations
    assert again.areas == first.areas

    refreshed = RecordedIndex(_areas("nmt", "krakow"))
    forced = _check(
        refreshed, product="nmt", country="pl", bbox=KRAKOW, cache=cache, force=True
    )
    assert refreshed.urls and forced.combinations == first.combinations
    cache.close()


def test_hint_without_output_and_full_sheet():
    krakow = _report("nmt", "krakow")
    pomorze = _report("nmt", "pomorze")

    hints = [
        h for r in (krakow, pomorze) for c in r.combinations for h in c.download_hint
    ]
    assert all(h.startswith("elevation download --product nmt ") for h in hints)
    assert not any({"--root"} & set(shlex.split(h)) for h in hints)
    assert _combo(krakow, 2025, "PL-1992", "1m").download_hint == (
        "elevation download --product nmt --country pl --bbox "
        "565000,242000,569000,246000 --sheet-system 1992 --resolution 1m "
        "--vertical-crs EVRF2007 --year 2025",
    )
    # PL-2000: --scale of the sheets of the combination
    (pl2000,) = _combo(krakow, 2023, "PL-2000", "1m").download_hint
    assert "--sheet-system 2000 --scale 1:2000 " in pl2000
    # a sheet whose newest record of 2023 is partial while a full one exists
    assert (
        _combo(pomorze, 2023, "PL-1992", "5m")
        .download_hint[0]
        .endswith("--year 2023 --full-sheet")
    )
    assert "--full-sheet" not in _combo(pomorze, 2022, "PL-1992", "1m").download_hint[0]
    # archives name their format, LAZ has no sheet system or resolution
    archive = _combo(krakow, 2018, "PL-1992", "25m", fmt="TBD").download_hint[0]
    assert "--format TBD --resolution 25m" in archive
    laz = _report("laz", "krakow")
    assert _combo(laz, 2025, "PL-1992", None, fmt="LAZ").download_hint == (
        "elevation download --product laz --country pl --bbox "
        "565000,242000,569000,246000 --vertical-crs EVRF2007 --year 2025",
    )


class _Validated(Exception):
    """The request passed every check of download_data before the network."""


def _arguments(hint: str, output) -> dict:
    """The library arguments of a hint command, as ``kartograf`` reads its flags."""
    args = create_parser().parse_args([*shlex.split(hint), "--root", str(output)])
    return {**library_arguments(args), "root": args.root}


def _validated(hint: str, output) -> None:
    with (
        patch(
            "kartograf.download.data._create_provider_and_storage",
            side_effect=_Validated,
        ),
        patch("kartograf.download.laz.download_laz_area", side_effect=_Validated),
        pytest.raises(_Validated),
    ):
        download_data(**_arguments(hint, output))


@functools.cache
def _hints() -> tuple[str, ...]:
    """Hints of every shape: bbox (PL-1992, PL-2000 with ``--scale``,
    ``--full-sheet``, archives with ``--format``), NMPT, LAZ and a sheet."""
    reports = [
        _report("nmt", "krakow"),
        _report("nmt", "pomorze"),
        _report("nmpt", "krakow"),
        _report("laz", "pomorze"),
    ]
    session = RecordedIndex(
        {
            "nmt_evrf2007": ["sheet_nmt_evrf2007_M-34-64-D-d-2-1.xml"],
            "nmt_kron86": ["sheet_nmt_kron86_M-34-64-D-d-2-1.xml"],
        }
    )
    reports.append(_check(session, product="nmt", sheet="M-34-64-D-d-2-1"))
    return tuple(h for r in reports for c in r.combinations for h in c.download_hint)


def test_hint_runs_validation(tmp_path):
    hints = _hints()
    assert len(hints) > 50
    for hint in hints:
        _validated(hint, tmp_path)


def test_hint_accepted_by_project_add(tmp_path, monkeypatch):
    """Every hint pasted after ``kartograf project add NAZWA`` is a project
    task (manifest spec 4.10): the project validation, without network."""
    from kartograf import init_project, open_project
    from kartograf.cli import main

    monkeypatch.chdir(tmp_path)
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    hints = _hints()
    for number, hint in enumerate(hints):
        add = ["project", "add", "--project", str(project), f"zadanie{number}"]
        assert main([*add, *shlex.split(hint)]) == 0, hint
    assert len(open_project(project).tasks) == len(hints)
    assert list((project / "data").iterdir()) == []


@pytest.mark.usefixtures("frozen_clock")
def test_json_round_trip_and_order():
    report, _ = _krakow()
    again, _ = _krakow()

    text = report.to_json()
    assert text == again.to_json() and text.endswith("}\n")
    payload = json.loads(text)
    assert payload["schema"] == AVAILABILITY_SCHEMA
    assert payload["checked_at"] == "2026-10-12T08:30:45+00:00"
    assert payload["request"] == {
        "product": "nmt",
        "country": "pl",
        "bbox": [565000.0, 242000.0, 569000.0, 246000.0],
        "bbox_crs": "EPSG:2180",
        "min_year": None,
        "max_year": None,
    }
    years = [c["year"] for c in payload["combinations"]]
    assert years == sorted(years, reverse=True)
    first = payload["combinations"][0]
    assert first["sheets_missing"] == [] and first["size_bytes"] is None


@pytest.mark.usefixtures("frozen_clock")
def test_availability_json_has_schema_first_and_same_content():
    """The shared encoder writes the document of 0.8.0-dev; only ``schema`` moves
    from the last key to the first."""
    report, _ = _krakow()

    payload = json.loads(report.to_json())

    assert list(payload) == [
        "schema",
        "request",
        "checked_at",
        "areas",
        "combinations",
        "failed",
        "notices",
        "ok",
    ]
    previous = json.loads(json.dumps(dataclasses.asdict(report)))  # the 0.8.0-dev text
    assert payload == {**previous, "schema": AVAILABILITY_SCHEMA}
    assert report.to_dict() == payload
    assert report.schema == AVAILABILITY_SCHEMA


# =============================================================================
# Sheet and geometry requests
# =============================================================================


def _sheet_report(sheet: str, *services: str):
    tag = {"E": "evrf2007", "K": "kron86"}
    session = RecordedIndex(
        {f"nmt_{tag[s]}": [f"sheet_nmt_{tag[s]}_{sheet}.xml"] for s in services}
    )
    return _check(session, product="nmt", sheet=sheet)


def test_sheet_request_counts_its_own_frame():
    """The sheet's own record covers its frame (GUGiK frame vs the frame
    computed from the code: centimetres), neighbours sharing an edge do not
    count; a record on a PL-2000 sheet is downloaded by its own code."""
    report = _sheet_report("M-34-64-D-d-2-1", "E", "K")

    grid = _combo(report, 2025, "PL-1992", "1m")
    assert grid.complete and not grid.uncovered
    assert grid.sheets_full == ("M-34-64-D-d-2-1",)
    assert grid.download_hint == (
        "elevation download --product nmt --sheet M-34-64-D-d-2-1 --resolution 1m "
        "--vertical-crs EVRF2007 --year 2025",
    )
    # TBD of the 1:25000 frame M-34-64-D-d-2 covers the sheet too
    tbd = _combo(report, 2009, "PL-1992", "15m", "KRON86", "TBD")
    assert tbd.sheets_full == ("M-34-64-D-d-2",) and tbd.complete
    other_system = _combo(report, 2023, "PL-2000", "1m")
    assert other_system.download_hint == (
        "elevation download --product nmt --sheet 7.125.11.04 --resolution 1m "
        "--vertical-crs EVRF2007 --year 2023",
    )
    assert report.request["sheet"] == "M-34-64-D-d-2-1"


_QUARTERS = tuple(f"N-33-142-B-b-4-1-{quarter}" for quarter in range(1, 5))


def test_8_part_records_are_downloadable_combinations():
    """Since plan E1 the 8-part codes are sheets of ``SheetParser``: the 2019
    grids published per quarter of a 7-part sheet and the ASCII NMT 10 m
    archive are combinations; a grid of quarters is downloaded per quarter
    code (a 7-part request would plan a sheet without a record)."""
    report = _sheet_report("N-33-142-B-b-4-1", "E")

    assert report.notices == ()
    grid = _combo(report, 2019, "PL-1992", "1m")
    assert grid.sheets_full == _QUARTERS
    assert grid.download_hint == tuple(
        f"elevation download --product nmt --sheet {sheet} --resolution 1m "
        "--vertical-crs EVRF2007 --year 2019"
        for sheet in _QUARTERS
    )
    archive = _combo(report, 2019, "PL-1992", "10m", fmt="ASCII-NMT")
    assert archive.sheets_full == _QUARTERS
    assert archive.download_hint == (
        "elevation download --product nmt --sheet N-33-142-B-b-4-1 --format "
        "ASCII-NMT --resolution 10m --vertical-crs EVRF2007 --year 2019",
    )


def test_records_outside_the_registry_are_one_info():
    """Records of a variant outside the registry (the recorded ASCII NMT
    records declaring 12 m instead of 10 m) are named in one Info and are
    no combination."""
    session = RecordedIndex(
        {"nmt_evrf2007": ["sheet_nmt_evrf2007_N-33-142-B-b-4-1.xml"]}
    )
    for _, _, feature in session._features[wfs_endpoint("nmt_evrf2007")]:
        fields = {element.tag.rsplit("}", 1)[-1]: element for element in feature}
        if fields["format"].text == "ASCII NMT":
            fields["char_przestrz"].text = "12.0 m"

    report = _check(session, product="nmt", sheet="N-33-142-B-b-4-1")

    (notice,) = report.notices
    assert notice.level == "info" and notice.code == INDEX_UNSUPPORTED
    assert (
        "ASCII NMT 12m EVRF2007 (2019; arkusze: 4) - wariant spoza rejestru"
        in notice.message
    )
    assert {c.format for c in report.combinations if c.year == 2019} == {
        "ASC",
        "XYZ",
    }


def test_grid_published_under_xyz_name_is_a_combination():
    """Campaign 72675 publishes its 2019 grids under a ``.xyz`` name (an
    AAIGrid inside): a grid of the sheet, no Info."""
    report = _sheet_report("N-33-69-A-d-1-3", "E")

    assert report.notices == ()
    grid = _combo(report, 2019, "PL-1992", "1m")
    assert grid.complete and grid.sheets_full == ("N-33-69-A-d-1-3",)


def test_every_combination_is_a_registered_variant():
    reports = [
        _report("nmt", "krakow"),
        _report("nmt", "pomorze"),
        _report("nmpt", "krakow"),
    ]

    registered = {v.source for v in variants(country="PL")}
    assert {c.source for r in reports for c in r.combinations} <= registered


def test_geometry_request_measures_feature_envelopes(tmp_path):
    import shapefile
    from pyproj import CRS

    path = tmp_path / "obszar.shp"
    with shapefile.Writer(str(path)) as writer:
        writer.field("name", "C", 10)
        for x0, y0 in ((565000, 242000), (568000, 245000)):
            writer.poly(
                [
                    [
                        (x0, y0),
                        (x0 + 1000, y0),
                        (x0 + 1000, y0 + 1000),
                        (x0, y0 + 1000),
                        (x0, y0),
                    ]
                ]
            )
            writer.record("a")
    path.with_suffix(".prj").write_text(CRS.from_epsg(2180).to_wkt())
    session = RecordedIndex(_areas("nmt", "krakow"))

    report = _check(session, product="nmt", country="pl", geometry=path)

    (area,) = report.areas
    assert area.area_m2 == 2_000_000.0
    combo = _combo(report, 2025, "PL-1992", "1m")
    assert combo.complete and len(combo.sheets_full) < 6
    assert combo.download_hint[0].startswith(
        f"elevation download --product nmt --country pl --geometry {path} "
        "--sheet-system 1992"
    )
    assert report.request["geometry"] == str(path)


# =============================================================================
# Report = download (Review Focus 1)
# =============================================================================


def test_report_sheets_equal_download_selection(tmp_path):
    """``check_data`` with the hint of the newest complete combination plans
    exactly its full sheets, with records of its year (one index, one parser)."""
    report = _report("nmt", "krakow")
    newest = next(c for c in report.combinations if c.complete)
    (hint,) = newest.download_hint
    kwargs = _arguments(hint, tmp_path)
    session = RecordedIndex(_areas("nmt", "krakow"))

    with patch(SESSION, return_value=session):
        plan = check_data(**{**kwargs, "cache": False})

    assert sorted(item.unit for item in plan.items) == list(newest.sheets_full)
    assert all(
        (item.available_label or "").startswith(str(newest.year)) for item in plan.items
    )
    assert not any("opendata" in url for url in session.urls)


@pytest.mark.parametrize(
    ("product", "place", "key"),
    [
        pytest.param("nmt", "krakow", (2025, "PL-1992", "1m"), id="nmt-complete"),
        pytest.param("nmt", "pomorze", (2023, "PL-1992", "5m"), id="nmt-full-sheet"),
        pytest.param(
            "laz", "krakow", (2025, "PL-1992", None, "EVRF2007", "LAZ"), id="laz"
        ),
    ],
)
def test_sheet_records_are_what_the_hint_downloads(tmp_path, product, place, key):
    """KD-1: ``sheet_records`` are exactly the records ``check_data`` plans
    for the hint commands - NMT with ``--full-sheet`` the newest (partial)
    and the newest full record of a sheet, LAZ the tiles of the coverage
    selection."""
    combo = _combo(_report(product, place), *key)
    planned = set()
    for hint in combo.download_hint:
        session = RecordedIndex(_areas(product, place), coast=place == "pomorze")
        with patch(SESSION, return_value=session):
            plan = check_data(**{**_arguments(hint, tmp_path), "cache": False})
        planned |= {item.available_signal["url"] for item in plan.items}

    urls = [record.url for record in combo.sheet_records]
    assert sorted(urls) == sorted(planned) and len(urls) == len(planned)
    sheets = [record.sheet for record in combo.sheet_records]
    assert sheets == sorted(sheets)


def test_full_sheet_records_and_campaigns_on_their_own():
    """Pomorze 2023 5 m: the newest records of its sheets (DFT.7201.028.2023)
    are partial, the full ones (DFT.7201.002.2023) come with ``--full-sheet``
    - newest first; neither campaign alone covers the land, the partial one
    covers none of it."""
    combo = _combo(_report("nmt", "pomorze"), 2023, "PL-1992", "5m")

    by_sheet: dict[str, list] = {}
    for record in combo.sheet_records:
        by_sheet.setdefault(record.sheet, []).append(record)
    assert set(by_sheet) == set(combo.sheets_full)
    for records in by_sheet.values():
        assert records[-1].full_sheet is True
        assert records[-1].campaign == "DFT.7201.002.2023"
        dates = [r.acquisition_date or "" for r in records]
        assert dates == sorted(dates, reverse=True)
    assert sum(len(r) == 2 for r in by_sheet.values()) == 2
    assert [(c.campaign, c.complete) for c in combo.campaign_coverage] == [
        ("DFT.7201.002.2023", False),
        ("DFT.7201.028.2023", False),
    ]
    full, partial = combo.campaign_coverage
    assert full.full_m2 == combo.full_m2 and partial.full_m2 == 0.0


def test_check_asks_the_index_despite_cached_records(tmp_path):
    """Live test 0.8.0 (P2-2): ``--check-updates`` always asks the source - a
    sheet record in the metadata cache (TTL 7 days) is refreshed, not read,
    so a flight published since the last query is found."""
    report = _report("nmt", "krakow")
    newest = next(c for c in report.combinations if c.complete)
    (hint,) = newest.download_hint
    kwargs = {
        **_arguments(hint, tmp_path),
        "cache": MetadataCache(tmp_path / "cache.db"),
    }
    asked = []
    for _ in range(2):
        session = RecordedIndex(_areas("nmt", "krakow"))
        with patch(SESSION, return_value=session):
            check_data(**kwargs)
        asked.append([url for url in session.urls if "GetFeature" in url])

    assert asked[0] and asked[1] == asked[0]


# =============================================================================
# CZ and ``auto`` (plan B, decisions 9-10)
# =============================================================================

CTES86_DMPOK = f"{OPENZU}/DMPOK-TIFF/epsg-5514/CTES86.zip"
TILE_DMPOK = f"{OPENZU}/DMPOK-TIFF/epsg-3045/760_5516.zip"
CIESZYN_AREA = "--bbox=-447000,-1114000,-446000,-1113000 --bbox-crs EPSG:5514"
LAZ_MODELS = ("dmr5g", "dmr4g", "dmp1g", "dmpok")


class _FailingHead(CuzkSession):
    """``CuzkSession`` whose ``HEAD`` of ``url`` fails with an HTTP status or
    an exception (a timeout); other requests are the recorded answers."""

    def __init__(self, url: str, outcome: int | Exception = 503) -> None:
        super().__init__()
        self.failing = url
        self.outcome = outcome

    def head(self, url: str, timeout=None, allow_redirects=True, **kwargs):
        if url != self.failing:
            return super().head(url, timeout=timeout, allow_redirects=allow_redirects)
        self._record("HEAD", url)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return _response(self.outcome, {})


class _Border:
    """The GUGiK answers of the PL part of Cieszyn (``RecordedIndex``) and the
    CUZK answers (``CuzkSession``) behind one session: ``country="auto"``."""

    def __init__(self, product: str, cz: CuzkSession | None = None) -> None:
        self.pl = RecordedIndex(_areas(product, "cieszyn"))
        self.cz = cz if cz is not None else CuzkSession()

    def get(self, url: str, **kwargs):
        return (self.cz if "cuzk.gov.cz" in url else self.pl).get(url, **kwargs)

    def head(self, url: str, **kwargs):
        return self.cz.head(url, **kwargs)


def _cz(
    product: str, session: CuzkSession | None = None, **kwargs
) -> tuple[AvailabilityReport, CuzkSession]:
    """The report of the Cieszyn area with ``country="cz"`` (EPSG:5514)."""
    session = session if session is not None else CuzkSession()
    report = _check(session, product=product, country="cz", bbox=CIESZYN, **kwargs)
    return report, session


# Frame of the SM5 sheet CTES86 in the recorded index answer (EPSG:5514).
_CTES86_RING = recorded_json("klady_24_where_ctes86.json")["features"][0]["geometry"][
    "rings"
][0]
CTES86_FRAME = BBox(
    min(x for x, _ in _CTES86_RING),
    min(y for _, y in _CTES86_RING),
    max(x for x, _ in _CTES86_RING),
    max(y for _, y in _CTES86_RING),
    "EPSG:5514",
)


def _code_report(product: str) -> tuple[AvailabilityReport, CuzkSession]:
    """The report of the SM5 code ``CTES86``: its sheet by name (recorded),
    the TM33 query of its frame answered with the recorded tile of the
    border area (``760_5516`` lies in the frame)."""
    envelope = bbox_to_crs(CTES86_FRAME, "EPSG:3045")
    session = CuzkSession(
        envelopes={
            (26, tuple(envelope[:4])): recorded_json("klady_26_bbox_cieszyn.json")
        }
    )
    return _check(session, product=product, sheet="CTES86"), session


@functools.cache
def _cz_hints() -> tuple[str, ...]:
    """CZ hints of every shape: raster sheets (SM5, TM33), LAZ of an area
    and LAZ of a sheet code."""
    reports = [_cz(product)[0] for product in ("nmt", "nmpt", "laz")]
    reports.append(_code_report("laz")[0])
    return tuple(h for r in reports for c in r.combinations for h in c.download_hint)


def test_cz_nmpt_combinations():
    """DMP OK in both pairs of its files: the index sheets of the area
    (``CTES86``; ``CTES87`` only touches it), dates and sizes from ``HEAD``."""
    report, _ = _cz("nmpt")

    s_jtsk, tm33 = report.combinations
    assert (s_jtsk.source, s_jtsk.horizontal, s_jtsk.resolution) == (
        "cz.cuzk.dmpok",
        "S-JTSK",
        "0.5m",
    )
    assert (s_jtsk.vertical_crs, s_jtsk.format) == ("Bpv", "TIFF")
    assert s_jtsk.sheets_full == ("CTES86",) and s_jtsk.complete
    assert s_jtsk.published == ("2025-10-10", "2025-10-10")
    assert s_jtsk.size_bytes == 16_660_209
    assert (tm33.horizontal, tm33.vertical_crs, tm33.sheets_full) == (
        "ETRS89-TM33",
        "EVRF2007",
        ("760_5516",),
    )
    assert tm33.published == ("2026-08-20", "2026-08-20")
    assert tm33.size_bytes == 29_625_401
    for combo in report.combinations:
        assert combo.country == "CZ" and combo.year is None
        assert combo.acquisition_dates is None and combo.campaigns == ()
        assert combo.sheets_missing == () and not combo.uncovered
    (notice,) = report.notices
    assert (notice.level, notice.code) == ("info", CZ_SERVICE_ONLY)
    assert "DMP 1G (2m)" in notice.message and "--model dmp1g" in notice.message
    assert report.areas == (
        AvailabilityArea(
            "CZ",
            "EPSG:5514",
            (-447000.0, -1114000.0, -446000.0, -1113000.0),
            1_000_000.0,
            1_000_000.0,
        ),
    )
    assert report.ok and report.request["country"] == "cz"


def test_cz_missing_file_is_incomplete():
    report, _ = _cz("nmpt", CuzkSession(missing=(CTES86_DMPOK,)))

    s_jtsk, tm33 = report.combinations
    assert s_jtsk.sheets_full == () and s_jtsk.sheets_missing == ("CTES86",)
    assert not s_jtsk.complete and s_jtsk.uncovered
    # the whole area lies in the frame of CTES86
    assert s_jtsk.uncovered_m2 == 1_000_000.0 and s_jtsk.full_m2 == 0.0
    assert s_jtsk.download_hint == () and s_jtsk.published is None
    assert tm33.complete and tm33.sheets_full == ("760_5516",)
    # complete = every index sheet has a file; the NE corner of the area lies
    # outside every TM33 tile, so the area in tiles with a file is smaller
    assert 0.99 * 1_000_000.0 < tm33.full_m2 < 1_000_000.0
    assert tm33.sheet_records == () and tm33.campaign_coverage == ()


def test_cz_no_file_at_all():
    """No sheet has a file: the size is unknown (``None``, as in PL), and a
    TM33 tile is measured against the S-JTSK rectangle of the area - its
    envelope in EPSG:3045 is larger, the uncovered part never is."""
    report, _ = _cz("nmpt", CuzkSession(missing=(CTES86_DMPOK, TILE_DMPOK)))

    (area,) = report.areas
    s_jtsk, tm33 = report.combinations
    for combo in (s_jtsk, tm33):
        assert combo.sheets_full == () and combo.size_bytes is None
        assert combo.published is None and not combo.complete
    assert s_jtsk.uncovered_m2 == area.area_m2 == 1_000_000.0
    # the NE corner of the area lies east of 760_5516, where CZ has no tile
    assert 0.99 * area.area_m2 < tm33.uncovered_m2 < area.area_m2


def test_cz_part_without_sheets_has_no_model_notice():
    """A CZ area without any CUZK sheet (e.g. an ``auto`` part in PL inside
    the CZ envelope) has no CZ data: no combinations and no notice about the
    service-only models."""
    empty = {"features": []}
    session = CuzkSession(
        envelopes={
            (24, (CIESZYN.min_x, CIESZYN.min_y, CIESZYN.max_x, CIESZYN.max_y)): empty,
            (26, CIESZYN_3045): empty,
        }
    )
    report, _ = _cz("nmpt", session)

    assert report.combinations == () and report.notices == ()
    assert report.ok


@pytest.mark.parametrize(
    ("outcome", "status", "attempts"),
    [
        pytest.param(503, 503, MAX_RETRIES, id="503"),
        pytest.param(403, 403, 1, id="403"),
        pytest.param(requests.Timeout("read timeout"), None, MAX_RETRIES, id="timeout"),
    ],
)
def test_cz_server_error_is_error(outcome, status, attempts):
    """Only 404 means "no file": any other failure is an error of the report,
    retried as every request - never an incomplete combination."""
    session = _FailingHead(CTES86_DMPOK, outcome)

    with patch("time.sleep"), pytest.raises(DownloadError) as error:
        _cz("nmpt", session)

    assert error.value.status_code == status
    assert session.of("HEAD").count(CTES86_DMPOK) == attempts


def test_cz_laz_eight_combinations():
    report, session = _cz("laz")

    assert [
        (c.source, c.horizontal, c.vertical_crs, c.sheets_full)
        for c in report.combinations
    ] == [
        (f"cz.cuzk.{model}_laz", horizontal, vertical_crs, sheets)
        for model in LAZ_MODELS
        for horizontal, vertical_crs, sheets in (
            ("S-JTSK", "Bpv", ("CTES86",)),
            ("ETRS89-TM33", "EVRF2007", ("760_5516",)),
        )
    ]
    assert all(
        c.complete and c.format == "LAZ" and c.resolution is None
        for c in report.combinations
    )
    dmr5g = report.combinations[0]
    assert dmr5g.size_bytes == 698_424
    assert dmr5g.published == ("2026-01-19", "2026-01-19")
    # every model has LAZ files: no service-only notice
    assert report.notices == ()
    # one index query per sheet system, one HEAD per file
    assert len(session.of("QUERY")) == 2 and len(session.of("HEAD")) == 8


def test_cz_sheet_code_is_its_frame():
    """An SM5 code: its own sheet by name from the index (no bbox query of
    its system), the TM33 tiles of its frame, the frame as the area."""
    report, session = _code_report("laz")

    assert report.request == {
        "product": "laz",
        "country": "cz",
        "sheet": "CTES86",
        "min_year": None,
        "max_year": None,
    }
    (area,) = report.areas
    assert area.bounds == tuple(CTES86_FRAME[:4]) and area.area_m2 == 5_000_000.0
    s_jtsk, tm33 = report.combinations[:2]
    assert s_jtsk.sheets_full == ("CTES86",) and tm33.sheets_full == ("760_5516",)
    assert [q for q in session.of("QUERY") if q.startswith("24:")] == [
        "24:MAPNOM='CTES86'"
    ]
    # a code reaches only its own sheet system: commands per sheet
    assert s_jtsk.download_hint == (
        "elevation download --product laz --sheet CTES86 --model dmr5g "
        "--vertical-crs Bpv",
    )
    assert tm33.download_hint == (
        "elevation download --product laz --sheet 760_5516 --model dmr5g "
        "--vertical-crs EVRF2007",
    )


def test_cz_availability_never_gets_files():
    """Only index queries and ``HEAD`` of the openzu files; a ``GET`` of a
    file would be recorded (``CuzkSession.get`` without query parameters)."""
    for product in ("nmt", "nmpt", "laz"):
        report, session = _cz(product)

        assert report.combinations
        assert session.of("GET") == []
        assert {kind for kind, _ in session.calls} == {"QUERY", "HEAD"}
        assert all(url.startswith(f"{OPENZU}/") for url in session.of("HEAD"))


def test_cz_hints(tmp_path):
    """Rasters: one command per sheet with a file; LAZ: one command of the
    area of the request (``--country cz``, ``--model``); no ``--root``."""
    nmt, _ = _cz("nmt")
    nmpt, _ = _cz("nmpt")
    laz, _ = _cz("laz")

    assert [c.download_hint for c in nmt.combinations] == [
        (
            "elevation download --product nmt --sheet CTES86 --resolution 5m "
            "--vertical-crs Bpv",
        ),
        (
            "elevation download --product nmt --sheet 760_5516 --resolution 5m "
            "--vertical-crs EVRF2007",
        ),
    ]
    assert [c.download_hint for c in nmpt.combinations] == [
        (
            "elevation download --product nmpt --sheet CTES86 --resolution 0.5m "
            "--vertical-crs Bpv",
        ),
        (
            "elevation download --product nmpt --sheet 760_5516 --resolution 0.5m "
            "--vertical-crs EVRF2007",
        ),
    ]
    assert [c.download_hint for c in laz.combinations] == [
        (
            f"elevation download --product laz --country cz {CIESZYN_AREA} "
            f"--model {model} --vertical-crs {vertical_crs}",
        )
        for model in LAZ_MODELS
        for vertical_crs in ("Bpv", "EVRF2007")
    ]
    assert not any({"--root"} & set(shlex.split(h)) for h in _cz_hints())
    # every command passes the checks of download_data before the network
    for hint in _cz_hints():
        validate_data_request(**_arguments(hint, tmp_path))


def test_cz_hints_accepted_by_project_add(tmp_path, monkeypatch):
    """Every CZ hint pasted after ``kartograf project add NAZWA`` is a
    project task (validation without network, nothing written)."""
    from kartograf import init_project, open_project
    from kartograf.cli import main

    monkeypatch.chdir(tmp_path)
    project = tmp_path / "projekt"
    init_project(project, root=project / "data")
    hints = _cz_hints()
    for number, hint in enumerate(hints):
        add = ["project", "add", "--project", str(project), f"cz{number}"]
        assert main([*add, *shlex.split(hint)]) == 0, hint
    assert len(open_project(project).tasks) == len(hints)
    assert list((project / "data").iterdir()) == []


def test_cz_cache_and_force(tmp_path):
    cache = MetadataCache(tmp_path / "cache.db")
    first, session = _cz("nmpt", CuzkSession(missing=(CTES86_DMPOK,)), cache=cache)
    assert session.of("QUERY") and session.of("HEAD")

    # index sheets and HEAD answers (also a 404) come from the cache
    again, offline = _cz("nmpt", cache=cache)
    assert offline.calls == []
    assert again.combinations == first.combinations

    forced, refreshed = _cz("nmpt", cache=cache, force=True)
    assert refreshed.of("QUERY") and refreshed.of("HEAD")
    assert forced.combinations[0].sheets_full == ("CTES86",)
    cache.close()


def test_year_flags_are_pl_only():
    """CUZK publishes no survey years: CZ alone rejects the year flags, an
    ``auto`` area in both countries is narrowed to PL."""
    session = CuzkSession()
    plzen = BBox(13.37, 49.74, 13.39, 49.75, "EPSG:4326")  # outside PL envelope
    for kwargs in (
        {"country": "cz", "bbox": CIESZYN},
        {"sheet": "CTES86"},
        {"country": "auto", "bbox": plzen},
    ):
        with pytest.raises(ValidationError, match="nie publikuje lat nalotu"):
            _check(session, product="nmt", year=2024, **kwargs)
    assert session.calls == []

    border = _Border("nmt")
    report = _check(border, product="nmt", country="auto", bbox=CIESZYN, year=2024)

    assert [area.country for area in report.areas] == ["PL"]
    assert {c.year for c in report.combinations} == {2024}
    (notice,) = report.notices
    assert notice.code == AUTO_NARROWED_TO_PL
    assert notice.message == "--country auto -> pl (--year 2024 dotyczy tylko PL)"
    assert border.cz.calls == []


def test_auto_both_countries():
    """The border area of Cieszyn/Cesky Tesin: the PL part from the GUGiK
    index (its land), the CZ part from the CUZK files, one report."""
    report = _check(_Border("nmpt"), product="nmpt", country="auto", bbox=CIESZYN)

    assert report.ok and report.request["country"] == "auto"
    pl, cz = report.areas
    assert (pl.country, pl.crs, cz.country, cz.crs) == (
        "PL",
        "EPSG:2180",
        "CZ",
        "EPSG:5514",
    )
    # the land of PL in the area; the CZ part = the whole bbox (rectangles)
    assert 0 < pl.land_m2 < 1_000_000 and cz.area_m2 == 1_000_000.0
    countries = [c.country for c in report.combinations]
    assert countries == sorted(countries, key=["PL", "CZ"].index)
    assert set(countries) == {"PL", "CZ"}
    newest = report.combinations[0]
    assert (newest.year, newest.horizontal, newest.resolution, newest.complete) == (
        2024,
        "PL-1992",
        "0.5m",
        True,
    )
    # the grid of the bbox also holds M-34-74-C-c-2-2 (CZ, no GUGiK record):
    # one command per sheet with a record instead of the area command
    assert newest.download_hint == tuple(
        f"elevation download --product nmpt --sheet {sheet} --resolution 0.5m "
        "--vertical-crs EVRF2007 --year 2024"
        for sheet in newest.sheets_full
    )
    s_jtsk = next(c for c in report.combinations if c.country == "CZ")
    assert s_jtsk.sheets_full == ("CTES86",) and s_jtsk.complete
    assert [n.code for n in report.notices] == [CZ_SERVICE_ONLY]


def test_border_hint_plans_only_sheets_with_records(tmp_path):
    """Coordinator decision 2026-10-16 (live E2E of plan B at Cieszyn): the
    area command of the PL part also planned the grid sheet M-34-74-C-c-2-2
    in CZ without a GUGiK record - ``check_failed`` ("Brak danych"), exit 1.
    The hint commands plan exactly the sheets of the combination."""
    report = _check(_Border("nmpt"), product="nmpt", country="auto", bbox=CIESZYN)
    newest = report.combinations[0]
    planned = []
    for hint in newest.download_hint:
        session = RecordedIndex(_areas("nmpt", "cieszyn"))
        with patch(SESSION, return_value=session):
            plan = check_data(**{**_arguments(hint, tmp_path), "cache": False})
        planned += [(item.unit, item.status) for item in plan.items]

    assert sorted(planned) == [(sheet, "missing") for sheet in newest.sheets_full]


def test_auto_one_country_failed():
    """A country that could not be checked while the other one was: the
    report of the other one, a warning and ``ok=False``; both = an error."""
    session = _Border("nmpt", _FailingHead(TILE_DMPOK))
    with patch("time.sleep"):
        report = _check(session, product="nmpt", country="auto", bbox=CIESZYN)

    assert not report.ok
    assert [area.country for area in report.areas] == ["PL"]
    assert {c.country for c in report.combinations} == {"PL"}
    (failed,) = report.notices
    assert (failed.level, failed.code) == ("warning", CHECK_FAILED)
    assert failed.message.startswith(
        "--country auto: nie udalo sie sprawdzic czesci CZ"
    )
    assert failed.message.endswith("raport obejmuje tylko PL")
    (country,) = report.failed
    assert (country.unit, country.country, country.kind) == ("CZ", "CZ", "country")
    assert (country.code, country.reason) == ("source_unavailable", None)
    assert country.error and country.error.isascii()

    both = _Border("nmpt", _FailingHead(TILE_DMPOK))
    both.pl = RecordedIndex(fail={PRG: wfs_response("<html>blad</html>")})
    with patch("time.sleep"), pytest.raises(DownloadError, match="PRG"):
        _check(both, product="nmpt", country="auto", bbox=CIESZYN)
