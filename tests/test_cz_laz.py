"""LAZ CZ track (``download_cz_laz``/``check_cz_laz``) on the versioned store.

The provider talks to ``CuzkSession`` of ``tests/test_cuzk_laz.py`` - the
recorded CUZK answers of 2026-10-15 (``tests/fixtures/cuzk/real_2026_10_15``):
the openzu ZIP is stored as its single ``.laz`` member, byte for byte.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf import CzLazFailure, check_cz_laz, download_cz_laz
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import NoCoverageError, ValidationError
from kartograf.providers.cuzk.laz import CuzkLazProvider
from tests.test_cuzk_laz import (
    CIESZYN,
    CIESZYN_3045,
    CTES86_URL,
    CTES96_URL,
    CUZK_FIXTURES,
    TM33_URL,
    CuzkSession,
    recorded_heads,
    recorded_json,
    zip_member,
)

CTES96_ETAG = '"b18eccf24d89dc1:0"'


@contextmanager
def recorded(session: CuzkSession) -> Iterator[CuzkSession]:
    """Providers of the track talk to ``session``."""

    def provider(model, session_=None, cache=None, *, vertical_crs):
        return CuzkLazProvider(model, session, cache, vertical_crs=vertical_crs)

    with patch("kartograf.providers.cuzk.laz.CuzkLazProvider", side_effect=provider):
        yield session


def sidecar(path: Path) -> dict:
    return json.loads(path.with_name(f"{path.name}.meta.json").read_text("utf-8"))


def test_laz_file_bytes_equal_zip_member(tmp_path):
    with recorded(CuzkSession()) as session:
        result = download_cz_laz(
            model="dmr4g",
            vertical_crs="Bpv",
            output_dir=tmp_path,
            sheet="CTES96",
            cache=False,
        )

    assert result.ok and result.sheets == ("CTES96",)
    (file,) = result.files
    assert file.status == "new"
    assert file.path == tmp_path / "laz/cz_dmr4g_bpv/CTES/96/CTES96.laz"
    assert file.path.read_bytes() == zip_member(CTES96_URL)
    assert session.of("GET") == [CTES96_URL]
    meta = sidecar(file.version_path)
    assert meta["dataset"] == "cz.cuzk.dmr4g_laz"
    assert meta["request"] == {"sheet": "CTES96"}
    assert (meta["horizontal_crs"], meta["vertical_crs"]) == ("EPSG:5514", "EPSG:8357")
    assert meta.get("transform") is None
    assert meta["extra"]["http"]["etag"] == CTES96_ETAG
    assert meta["extra"]["mapname"] == "Český Těšín 9-6"
    assert meta["extra"]["cz_share"] == pytest.approx(0.99)
    assert "parent_request" not in meta["extra"]


def test_laz_tm33_evrf2007(tmp_path):
    with recorded(CuzkSession()) as session:
        result = download_cz_laz(
            model="dmr4g",
            vertical_crs="EVRF2007",
            output_dir=tmp_path,
            sheet="760_5518",
            cache=False,
        )

    (file,) = result.files
    assert file.path == tmp_path / "laz/cz_dmr4g_evrf2007/760/5518/760_5518.laz"
    assert file.path.read_bytes() == zip_member(TM33_URL)
    assert session.calls == [("GET", TM33_URL)]  # a TM33 code needs no index
    meta = sidecar(file.version_path)
    assert (meta["horizontal_crs"], meta["vertical_crs"]) == ("EPSG:3045", "EPSG:5621")
    assert meta.get("transform") is None
    assert "mapname" not in meta["extra"] and "cz_share" not in meta["extra"]


@pytest.mark.parametrize(
    ("vertical_crs", "sheet"), [("EVRF2007", "CTES96"), ("Bpv", "760_5518")]
)
def test_laz_wrong_pair_rejected(vertical_crs, sheet, tmp_path):
    for call in (download_cz_laz, check_cz_laz):
        with (
            recorded(CuzkSession()) as session,
            pytest.raises(ValidationError, match="chmury punktow bez transformacji"),
        ):
            call(
                model="dmr4g",
                vertical_crs=vertical_crs,
                output_dir=tmp_path,
                sheet=sheet,
                cache=False,
            )
        assert session.calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "selection", [{}, {"sheet": "CTES96", "bbox": CIESZYN}], ids=["none", "both"]
)
def test_exactly_one_selection(selection, tmp_path):
    with (
        recorded(CuzkSession()) as session,
        pytest.raises(ValidationError, match="dokladnie jedno"),
    ):
        download_cz_laz(
            model="dmr4g", vertical_crs="Bpv", output_dir=tmp_path, **selection
        )
    assert session.calls == []


def test_laz_404_is_sheet_failure(tmp_path):
    """One sheet without a file fails alone; the other one is stored."""
    area = BBox(-448000, -1114000, -446000, -1113000, "EPSG:5514")
    # The index answer of this area: the recorded CTES96 feature (by MAPNOM)
    # with the recorded Cieszyn features (CTES86, CTES87 touching the edge).
    answer = recorded_json("klady_24_bbox_cieszyn.json")
    ctes96 = json.loads((CUZK_FIXTURES / "klady_sm5_where_ctes96.json").read_text())
    answer["features"] = ctes96["features"] + answer["features"]
    envelope = (area.min_x, area.min_y, area.max_x, area.max_y)
    progress: list[tuple[int, int]] = []
    parent = {"bbox": [-448000.0, -1114000.0, -446000.0, -1113000.0]}
    session = CuzkSession(missing=(CTES86_URL,), envelopes={(24, envelope): answer})
    with recorded(session):
        result = download_cz_laz(
            model="dmr4g",
            vertical_crs="Bpv",
            output_dir=tmp_path,
            bbox=area,
            parent_request=parent,
            workers=2,
            cache=False,
            on_progress=lambda done, total: progress.append((done, total)),
        )

    assert result.sheets == ("CTES86", "CTES96")
    assert not result.ok
    (failure,) = result.failed
    assert isinstance(failure, CzLazFailure) and failure.sheet == "CTES86"
    assert failure.error.status_code == 404
    assert "zweryfikuj godlo w indeksie KladyMapovychListu" in str(failure.error)
    (file,) = result.files
    assert file.path.read_bytes() == zip_member(CTES96_URL)
    assert sidecar(file.version_path)["extra"]["parent_request"] == parent
    assert not (tmp_path / "laz/cz_dmr4g_bpv/CTES/86").exists()
    assert progress == [(0, 2), (1, 2), (2, 2)]


def test_laz_area_without_sheets_is_no_coverage(tmp_path):
    answer = recorded_json("klady_26_bbox_cieszyn.json")
    answer["features"] = []
    session = CuzkSession(envelopes={(26, CIESZYN_3045): answer})
    with recorded(session), pytest.raises(NoCoverageError, match="KladyMapovychListu"):
        download_cz_laz(
            model="dmp1g",
            vertical_crs="EVRF2007",
            output_dir=tmp_path,
            bbox=CIESZYN,
            cache=False,
        )
    assert session.of("GET") == session.of("HEAD") == []


def test_cz_laz_check_and_upgrade_plan(tmp_path):
    common = {
        "model": "dmr4g",
        "vertical_crs": "Bpv",
        "output_dir": tmp_path,
        "sheet": "CTES96",
        "cache": False,
    }
    with recorded(CuzkSession()) as session:
        plan = check_cz_laz(**common)
    assert session.calls == [("HEAD", CTES96_URL)]
    (item,) = plan.items
    assert (item.track, item.unit, item.status) == ("cz_laz", "CTES96", "missing")
    assert (item.segment, item.hierarchy) == ("laz/cz_dmr4g_bpv", "CTES/96")
    assert item.available_signal["etag"] == CTES96_ETAG

    # The source changed since the plan: the position is stale, nothing fetched.
    with recorded(CuzkSession(etags={CTES96_URL: '"republished:0"'})) as session:
        changed = download_cz_laz(**common, update="upgrade", plan=plan)
    assert (changed.files, changed.stale) == ((), plan.items)
    assert session.of("GET") == []

    with recorded(CuzkSession()) as session:
        done = download_cz_laz(**common, update="upgrade", plan=plan)
    assert [f.status for f in done.files] == ["new"] and done.stale == ()
    assert session.of("HEAD") == [CTES96_URL] and session.of("GET") == [CTES96_URL]

    with recorded(CuzkSession()) as session:
        again = download_cz_laz(**common)
    assert [f.status for f in again.files] == ["local"]
    assert session.calls == [("HEAD", CTES96_URL)]

    with recorded(CuzkSession()) as session:
        (current,) = check_cz_laz(**common).items
        nothing = download_cz_laz(**common, update="upgrade", plan=plan)
    assert current.status == "current"
    assert nothing.files == () and session.of("GET") == []
    assert recorded_heads()[CTES96_URL][1]["ETag"] == CTES96_ETAG
