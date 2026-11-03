"""A store root that a write refuses is the error of the command (DEV-19.13, DEV-19.14).

A root with the layout of a store and no marker is ``store_unavailable``
(``no_marker``), a root that holds other files is ``conflict`` (``not_empty``) and a
root inside another store is ``conflict`` (``nested_store``). Every track that writes
the store refuses it before any request or unit of work, with its own registry code
and ``details.reason``: the refusal used to come out of a worker thread of a sheet
list as a failed unit of the code ``source_unavailable`` (kind ``download``), so the
code and the reason were lost. The plan of a root that is a conflict lists it as the
one position of the track ``store`` (an ``ok`` plan, DEV-19.10); one that is
``store_unavailable`` fails the plan as it fails the run.

No track has a fake source here: the refusal has to come first, so a request of any
kind is a defect, and ``asked`` records it.
"""

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

import pytest
import requests

from kartograf.cli.commands import main
from kartograf.download.collections import check_collection, download_collection
from kartograf.download.cutout import check_pl_cutout, download_pl_cutout
from kartograf.download.cz_contours import (
    check_cz_contours_sheet,
    download_cz_contours_sheet,
)
from kartograf.download.cz_cutout import check_cz_cutout, download_cz_cutout
from kartograf.download.cz_laz import check_cz_laz, download_cz_laz
from kartograf.download.cz_orto import check_cz_orto_sheet, download_cz_orto_sheet
from kartograf.download.cz_sheets import check_cz_sheet, download_cz_sheet
from kartograf.download.data import check_data, download_data
from kartograf.download.laz import check_laz_area, download_laz_area
from kartograf.download.manager import DownloadManager
from kartograf.download.orto_cutout import check_image_cutout, download_image_cutout
from kartograf.download.plan import UpdatePlan
from kartograf.exceptions import (
    ConflictError,
    KartografError,
    StoreUnavailableError,
)
from kartograf.hydrology.hsg import HSGCalculator, calculate_hsg, check_hsg
from kartograf.landcover.manager import (
    LandCoverManager,
    check_landcover,
    check_soil,
    download_landcover,
    download_soil,
)
from kartograf.marker import MARKER
from kartograf.testing import build_fixture_store
from tests.integration.test_collections import AREA
from tests.integration.test_cz_contours import AREA as CONTOURS_AREA
from tests.integration.test_cz_cutout import B as CZ_BBOX
from tests.integration.test_hsg import BBOX as SOIL_BBOX
from tests.integration.test_manager_campaigns import C14, FakeCampaignProvider, G
from tests.integration.test_orto_cutout import KRAKOW
from tests.integration.test_store_marker import seed_unmarked_store
from tests.integration.test_wcs_cutout import BBOX as PL_BBOX
from tests.support.errors import error_document

SHEETS = "N-34-139-C-a-3"  # the four sheets 3-1 to 3-4: a list, fetched in parallel
SHEET = "N-34-130-D-d-2-4"
CZ_SHEET = "CTES96"


class Refusal(NamedTuple):
    """How a store root is refused: the error class, its code, exit code and reason."""

    prepare: Callable[[Path], Path]
    error: type[KartografError]
    code: str
    exit_code: int
    reason: str


def unmarked(base: Path) -> Path:
    """The layout of a store of 0.8.0-dev: one version and no marker."""
    seed_unmarked_store(base / "root")
    return base / "root"


def busy(base: Path) -> Path:
    """A folder that holds a file of its own: no store, not empty."""
    (base / "root").mkdir()
    (base / "root" / "notes.txt").write_text("mine", encoding="utf-8")
    return base / "root"


def inside(base: Path) -> Path:
    """A folder that does not exist yet, in a store."""
    return build_fixture_store(base / "outer").root / "inner"


REFUSALS = {
    "no_marker": Refusal(
        unmarked, StoreUnavailableError, "store_unavailable", 8, "no_marker"
    ),
    "not_empty": Refusal(busy, ConflictError, "conflict", 4, "not_empty"),
    "nested_store": Refusal(inside, ConflictError, "conflict", 4, "nested_store"),
}
# the refusals that are a ``conflict``: the plan lists them
CONFLICTS = ("not_empty", "nested_store")


def tree(base: Path) -> list[str]:
    return sorted(str(path.relative_to(base)) for path in base.rglob("*"))


@pytest.fixture
def asked(monkeypatch) -> list[str]:
    """Every request any track makes, which the refusal must come before."""
    requests_made: list[str] = []

    def send(self, request, **kwargs):
        requests_made.append(f"{request.method} {request.url}")
        raise requests.ConnectionError("no request is expected")

    monkeypatch.setattr(requests.Session, "send", send)
    return requests_made


class Track(NamedTuple):
    """One track: its command-level function and the check of it, for a root."""

    download: Callable[[Path], Any]
    check: Callable[[Path], UpdatePlan]


def data(**options: Any) -> Track:
    return Track(
        lambda root: download_data(root=root, cache=False, **options),
        lambda root: check_data(root=root, cache=False, **options),
    )


PL_SHEETS: dict[str, Any] = {
    "product": "nmt",
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
}
BDOT: dict[str, Any] = {"product": "bdot10k", "teryt": "0262", "cache": False}
SOIL: dict[str, Any] = {
    "property": "clay",
    "depth": "0-5cm",
    "stat": "mean",
    "cache": False,
}
BUILDINGS: dict[str, Any] = {
    "product": "buildings",
    "country": "pl",
    "bbox": AREA,
    "lod": 1,
    "year": 2024,
}
PL_CUTOUT: dict[str, Any] = {
    "horizontal_crs": "EPSG:2180",
    "vertical_crs": "EVRF2007",
    "product": "nmt",
}
CZ_CUTOUT: dict[str, Any] = {
    "product": "nmt",
    "horizontal_crs": "EPSG:2180",
    "vertical_crs": "EVRF2007",
    "resolution": "2m",
}
ORTO: dict[str, Any] = {
    "product": "orto",
    "horizontal_crs": "EPSG:2180",
    "coverage": "standard",
    "resolution": "0.25m",
}

TRACKS: dict[str, Track] = {
    # ``download_data`` / ``check_data``: elevation and imagery
    "pl_sheets_in_parallel": data(sheet=SHEETS, **PL_SHEETS),
    "pl_sheet": data(sheet=G, **PL_SHEETS),
    "pl_laz": data(product="laz", sheet=SHEET, vertical_crs="EVRF2007"),
    "pl_cutout": data(
        bbox=PL_BBOX, country="pl", cutout=True, **PL_CUTOUT, resolution="1m"
    ),
    "cz_contours": data(
        product="contours", format="SHP", country="cz", bbox=CONTOURS_AREA
    ),
    # the track functions
    "laz": Track(
        lambda root: download_laz_area(
            sheet=SHEET, root=root, vertical_crs="EVRF2007", cache=False
        ),
        lambda root: check_laz_area(
            sheet=SHEET, root=root, vertical_crs="EVRF2007", cache=False
        ),
    ),
    "pl_wcs_cutout": Track(
        lambda root: download_pl_cutout(
            bbox=PL_BBOX, root=root, cache=False, **PL_CUTOUT
        ),
        lambda root: check_pl_cutout(bbox=PL_BBOX, root=root, cache=False, **PL_CUTOUT),
    ),
    "image_cutout": Track(
        lambda root: download_image_cutout(bbox=KRAKOW, root=root, cache=False, **ORTO),
        lambda root: check_image_cutout(bbox=KRAKOW, root=root, cache=False, **ORTO),
    ),
    "cz_cutout": Track(
        lambda root: download_cz_cutout(
            bbox=CZ_BBOX, root=root, cache=False, **CZ_CUTOUT
        ),
        lambda root: check_cz_cutout(bbox=CZ_BBOX, root=root, cache=False, **CZ_CUTOUT),
    ),
    "cz_sheet": Track(
        lambda root: download_cz_sheet(
            sheet=CZ_SHEET, root=root, product="nmt", vertical_crs="Bpv", cache=False
        ),
        lambda root: check_cz_sheet(
            sheet=CZ_SHEET, root=root, product="nmt", vertical_crs="Bpv", cache=False
        ),
    ),
    "cz_laz": Track(
        lambda root: download_cz_laz(
            sheet=CZ_SHEET, root=root, model="dmr4g", vertical_crs="Bpv", cache=False
        ),
        lambda root: check_cz_laz(
            sheet=CZ_SHEET, root=root, model="dmr4g", vertical_crs="Bpv", cache=False
        ),
    ),
    "cz_orto": Track(
        lambda root: download_cz_orto_sheet(sheet=CZ_SHEET, root=root, cache=False),
        lambda root: check_cz_orto_sheet(sheet=CZ_SHEET, root=root, cache=False),
    ),
    "cz_contours_sheet": Track(
        lambda root: download_cz_contours_sheet(
            CZ_SHEET, format="SHP", root=root, cache=False
        ),
        lambda root: check_cz_contours_sheet(CZ_SHEET, format="SHP", root=root),
    ),
    # collections, land cover, soil, HSG
    "collection": Track(
        lambda root: download_collection(root=root, cache=False, **BUILDINGS),
        lambda root: check_collection(root=root, cache=False, **BUILDINGS),
    ),
    "landcover": Track(
        lambda root: download_landcover(root=root, **BDOT),
        lambda root: check_landcover(root=root, **BDOT),
    ),
    "soil": Track(
        lambda root: download_soil(root=root, bbox=SOIL_BBOX, **SOIL),
        lambda root: check_soil(root=root, bbox=SOIL_BBOX, **SOIL),
    ),
    "hsg": Track(
        lambda root: calculate_hsg(
            root=root, bbox=SOIL_BBOX, depth="0-5cm", cache=False
        ),
        lambda root: check_hsg(root=root, bbox=SOIL_BBOX, depth="0-5cm", cache=False),
    ),
}


# --------------------------------------------------------------------------
# The run: the error of the command, before any request
# --------------------------------------------------------------------------


@pytest.mark.parametrize("track", TRACKS)
@pytest.mark.parametrize("refusal", REFUSALS)
def test_a_run_into_a_refused_store_root_is_the_error_of_the_command_before_a_request(
    tmp_path, asked, track, refusal
):
    expected = REFUSALS[refusal]
    root = expected.prepare(tmp_path)
    before = tree(tmp_path)

    with pytest.raises(expected.error) as caught:
        TRACKS[track].download(root)

    error = caught.value
    assert (error.code, error.exit_code, error.reason) == (
        expected.code,
        expected.exit_code,
        expected.reason,
    )
    assert error.details()["path"] == str(root.resolve())
    assert asked == []
    assert tree(tmp_path) == before  # not a byte, not the marker


# --------------------------------------------------------------------------
# The plan: a conflict is listed, the rest fails as the run does
# --------------------------------------------------------------------------


@pytest.mark.parametrize("track", TRACKS)
@pytest.mark.parametrize("refusal", CONFLICTS)
def test_the_plan_of_a_conflicting_store_root_lists_the_conflict_and_asks_nothing(
    tmp_path, asked, track, refusal
):
    root = REFUSALS[refusal].prepare(tmp_path)
    before = tree(tmp_path)

    plan = TRACKS[track].check(root)

    (item,) = plan.items
    assert (item.track, item.status, item.action, item.reason) == (
        "store",
        "unverifiable",
        "conflict",
        REFUSALS[refusal].reason,
    )
    assert item.path == root.resolve() and item.name == item.unit == str(root.resolve())
    assert item.error is not None and MARKER in item.error
    assert (plan.mode, plan.root, plan.output_dir) == (
        "store",
        str(root.resolve()),
        None,
    )
    assert plan.ok  # a plan that lists a conflict is a result: only the run fails
    assert asked == []
    assert tree(tmp_path) == before


@pytest.mark.parametrize("track", TRACKS)
def test_the_plan_of_an_unmarked_store_root_fails_as_the_run_does_before_a_request(
    tmp_path, asked, track
):
    root = unmarked(tmp_path)

    with pytest.raises(StoreUnavailableError) as caught:
        TRACKS[track].check(root)

    assert caught.value.reason == "no_marker"
    assert f"kartograf store init --root {root.resolve()}" in caught.value.hint
    assert asked == []
    assert not (root / MARKER).exists()


# --------------------------------------------------------------------------
# What is not refused
# --------------------------------------------------------------------------


def test_a_request_is_judged_before_the_root_it_names(tmp_path, asked):
    root = busy(tmp_path)

    with pytest.raises(KartografError) as run:
        download_data(product="nmt", sheet=G, root=root, cache=False)  # no resolution
    with pytest.raises(KartografError) as plan:
        check_data(product="nmt", sheet=G, root=root, cache=False)

    assert run.value.code == plan.value.code == "validation_error"
    assert asked == []


@pytest.mark.parametrize("track", ["pl_sheet", "cz_sheet", "collection"])
@pytest.mark.parametrize("kind", ["new", "empty"])
def test_a_new_or_empty_store_root_is_not_refused(tmp_path, asked, track, kind):
    root = tmp_path / kind
    if kind == "empty":
        root.mkdir()

    with contextlib.suppress(Exception):  # the request that the test does not answer
        TRACKS[track].download(root)

    assert asked  # the call went on to its first request
    assert not (root / MARKER).exists()  # a download that fails leaves no marker


# --------------------------------------------------------------------------
# The sheet list that used to hide the refusal: the manager
# --------------------------------------------------------------------------


def test_a_manager_refuses_a_list_of_sheets_instead_of_failing_each_sheet(tmp_path):
    root = unmarked(tmp_path)
    fake = FakeCampaignProvider(C14)
    sheets = [f"{SHEETS}-{part}" for part in range(1, 5)]

    with pytest.raises(StoreUnavailableError):
        DownloadManager(fake, root=root, workers=4).download_sheets(sheets)
    with pytest.raises(StoreUnavailableError):
        DownloadManager(fake, root=root, workers=4).download_hierarchy(
            SHEETS, "1:10000"
        )

    assert fake.resolve_calls == [] and fake.downloads == []


def test_a_manager_plans_a_conflicting_root_and_refuses_an_unmarked_one(tmp_path):
    fake = FakeCampaignProvider(C14)

    plan = DownloadManager(fake, root=busy(tmp_path)).check_sheets([G])
    with pytest.raises(StoreUnavailableError):
        DownloadManager(fake, root=unmarked(tmp_path / "other")).check_sheets([G])

    assert [(i.track, i.action, i.reason) for i in plan.items] == [
        ("store", "conflict", "not_empty")
    ]
    assert fake.resolve_calls == []


def test_land_cover_and_hsg_objects_refuse_their_store_root_too(tmp_path):
    root = inside(tmp_path)

    with pytest.raises(ConflictError) as manager:
        LandCoverManager("bdot10k", root=root, cache=False).download(teryt="0262")
    with pytest.raises(ConflictError) as calculator:
        HSGCalculator(root=root, cache=False).calculate_hsg(
            bbox=SOIL_BBOX, depth="0-5cm"
        )
    planned = HSGCalculator(root=root, cache=False).check_hsg(
        bbox=SOIL_BBOX, depth="0-5cm"
    )

    assert manager.value.reason == calculator.value.reason == "nested_store"
    assert [(i.track, i.reason) for i in planned.items] == [("store", "nested_store")]
    assert not root.exists()


# --------------------------------------------------------------------------
# A plain directory in a store is refused too (output_in_store)
# --------------------------------------------------------------------------


def test_a_plain_run_into_a_store_is_the_conflict_output_in_store_before_a_request(
    tmp_path, asked
):
    out = build_fixture_store(tmp_path / "store").root / "out"

    with pytest.raises(ConflictError) as caught:
        download_data(sheet=SHEETS, output_dir=out, cache=False, **PL_SHEETS)

    error = caught.value
    assert (error.code, error.reason) == ("conflict", "output_in_store")
    assert error.details()["paths"] == [str(out)]
    assert error.hint is not None and "--root" in error.hint
    assert asked == []  # the directory says it, no list of targets is needed
    assert not out.exists()


# --------------------------------------------------------------------------
# The CLI: the error document and the exit code, the plan and exit 0
# --------------------------------------------------------------------------


def run(capsys, *argv: str | Path) -> tuple[int, str, str]:
    code = main([str(word) for word in argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


NMT = [
    *("elevation", "download", "--product", "nmt", "--sheet", SHEETS),
    *("--resolution", "1m", "--vertical-crs", "EVRF2007", "--json"),
]


@pytest.mark.parametrize("refusal", REFUSALS)
def test_the_cli_exits_with_the_code_of_the_refusal_and_prints_its_document(
    capsys, tmp_path, asked, refusal
):
    expected = REFUSALS[refusal]
    root = expected.prepare(tmp_path)

    code, out, err = run(capsys, *NMT, "--root", root)

    document = error_document(err)
    assert (code, out) == (expected.exit_code, "")
    assert (document["code"], document["details"]["reason"]) == (
        expected.code,
        expected.reason,
    )
    assert document["exit_code"] == expected.exit_code
    assert document["command"] == "elevation download"
    assert asked == []


@pytest.mark.parametrize("refusal", CONFLICTS)
def test_the_cli_check_of_a_conflicting_root_prints_the_plan_and_exits_0(
    capsys, tmp_path, asked, refusal
):
    root = REFUSALS[refusal].prepare(tmp_path)

    code, out, err = run(capsys, *NMT, "--root", root, "--check")

    envelope = json.loads(out)
    plan = envelope["result"]
    assert (code, err, envelope["status"], envelope["check"]) == (0, "", "ok", True)
    assert [(i["track"], i["action"], i["reason"]) for i in plan["items"]] == [
        ("store", "conflict", REFUSALS[refusal].reason)
    ]
    assert plan["ok"] is True and plan["root"] == str(root.resolve())
    assert [(i["id"], i["status"]) for i in envelope["items"]] == [
        (str(root.resolve()), "ok")
    ]
    assert asked == []


def test_the_cli_check_in_words_says_why_the_root_is_a_conflict(
    capsys, tmp_path, asked
):
    root = inside(tmp_path)

    code, out, err = run(
        capsys,
        *NMT[:-1],
        "--root",
        root,
        "--check",
        "--lang",
        "en",
    )

    assert (code, err) == (0, "")
    assert out == (
        f"{root.resolve()}: conflict: the store root is in, holds or has another "
        "store (a store does not nest)\n"
    )


def test_the_cli_check_of_an_unmarked_root_fails_with_its_hint(capsys, tmp_path, asked):
    root = unmarked(tmp_path)

    code, out, err = run(capsys, *NMT, "--root", root, "--check")

    document = error_document(err)
    assert (code, out) == (8, "")
    assert (document["code"], document["details"]["reason"]) == (
        "store_unavailable",
        "no_marker",
    )
    assert document["hint"].startswith(f"kartograf store init --root {root.resolve()}")
