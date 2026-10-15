"""check_availability (spec 4, ADR-041) on recorded GUGiK answers.

Index: the recorded WFS answers of 2026-10-15 (``tests/fixtures/gugik_wfs/
real_2026_10_15``: areas of Krakow and Pomorze, sheets); ``RecordedIndex``
answers a sheet query with a slice of the recorded area. Land mask: the PRG
answers of ``tests/fixtures/gugik_prg/land_mask_2026_10_11`` (Krakow inland,
Pomorze coast). Expected values: plan A, "Weryfikacja" point 9 and spec 4.4
(measured 2026-10-15), with the archives downloaded since decision 13.
"""

import functools
import json
import shlex
from unittest.mock import patch

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.cli._parser import create_parser
from kartograf.cli.download_cmd import _download_arguments
from kartograf.core.bbox import BBox
from kartograf.download.availability import (
    AVAILABILITY_SCHEMA,
    AvailabilityReport,
    check_availability,
)
from kartograf.download.data import check_data, download_data
from kartograf.exceptions import DownloadError, ParseError, ValidationError
from kartograf.notices import INDEX_UNSUPPORTED
from kartograf.sources.variants import variants
from tests.conftest import (
    RecordedIndex,
    render_wfs_body,
    wfs_endpoint,
    wfs_fixture,
    wfs_record,
    wfs_response,
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
    with pytest.raises(DownloadError, match="wynik bylby niepelny"):
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
    with patch("time.sleep"), pytest.raises(DownloadError, match="niepelny"):
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
        download_data(output_dir=tmp_path, vertical_crs="EVRF2007", **common)
    with pytest.raises(ValidationError) as report:
        check_availability(**common)

    assert str(report.value) == str(api.value)


def test_choices_of_the_report_are_validated_before_network():
    session = RecordedIndex()
    with pytest.raises(ValidationError, match=r"--product 'orto': nieznana"):
        _check(session, product="orto", country="pl", bbox=KRAKOW)
    with pytest.raises(ValidationError, match="--product wymagane"):
        _check(session, product=None, country="pl", bbox=KRAKOW)
    with pytest.raises(ValidationError, match=r"--country 'cz'.*pl \(GUGiK\)"):
        _check(session, product="nmt", country="cz", bbox=KRAKOW)
    with pytest.raises(ValidationError, match="--country wymagane z --bbox"):
        _check(session, product="nmt", bbox=KRAKOW)
    with pytest.raises(ValidationError, match="CZ"):
        _check(session, product="nmt", sheet="302_5550")
    with pytest.raises(ParseError):
        _check(session, product="nmt", sheet="N-34-999-X")
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
    assert not any({"--output", "-o"} & set(shlex.split(h)) for h in hints)
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


def _validated(hint: str, output) -> None:
    args = create_parser().parse_args([*shlex.split(hint), "-o", str(output)])
    with (
        patch(
            "kartograf.download.data._create_provider_and_storage",
            side_effect=_Validated,
        ),
        patch("kartograf.download.laz.download_laz_area", side_effect=_Validated),
        pytest.raises(_Validated),
    ):
        download_data(**_download_arguments(args))


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
    init_project(project, output_dir=project / "data")
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


def test_records_outside_the_registry_are_one_info():
    report = _sheet_report("N-33-69-A-d-1-3", "E")

    (notice,) = report.notices
    assert notice.level == "info" and notice.code == INDEX_UNSUPPORTED
    assert "ARC/INFO ASCII GRID, plik .xyz 1m EVRF2007 (2019; arkusze: 1)" in (
        notice.text
    )
    assert "format rekordu niezgodny z plikiem" in notice.text
    # the inconsistent 2019 record is no combination
    assert not [
        c
        for c in report.combinations
        if (c.year, c.resolution, c.format) == (2019, "1m", "ASC")
    ]


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
    args = create_parser().parse_args([*shlex.split(hint), "-o", str(tmp_path)])
    kwargs = _download_arguments(args)
    session = RecordedIndex(_areas("nmt", "krakow"))

    with patch(SESSION, return_value=session):
        plan = check_data(**{**kwargs, "cache": False})

    assert sorted(item.unit for item in plan.items) == list(newest.sheets_full)
    assert all(
        (item.available_label or "").startswith(str(newest.year)) for item in plan.items
    )
    assert not any("opendata" in url for url in session.urls)
