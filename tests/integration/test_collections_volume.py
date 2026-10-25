"""Volume limit of an area request (decision of 2026-10-15, ADR-043 errata 3).

An area whose files to download number more than ``VOLUME_FILES`` or weigh
more than ``VOLUME_BYTES`` is refused before the first transfer. The channel
here is a PL map sheet series computed from the extent (no index), so the
number of files follows the area; the sizes are ``HEAD`` answers.
"""

import dataclasses
import functools

import pytest

from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import find_sheets_for_bbox, series_scale
from kartograf.download.collections import (
    VOLUME_BYTES,
    VOLUME_FILES,
    check_collection,
    download_collection,
)
from kartograf.exceptions import ValidationError
from kartograf.sources.descriptor import PackageVariant, SheetGrid, UnitPackageParams
from tests.integration.test_collections_units import (
    OPENDATA,
    Response,
    Router,
    _key,
    files_channel,
    install,
    source,
)
from tests.support.fake_packages import zip_bytes

pytestmark = pytest.mark.usefixtures("frozen_clock")

TEMPLATE = f"{OPENDATA}/test/volume/{{sheet}}.zip"
VOLUME = source(
    "pl.test.volume",
    "e5volume",
    "PL",
    "maps/pl_test_volume",
    files_channel(
        UnitPackageParams(
            unit="sheet",
            variants=(
                PackageVariant(
                    choice=(),
                    url_template=TEMPLATE,
                    sheet_grid=SheetGrid(system="1992", parts=6),
                ),
            ),
        ),
        "none",
        cap="sheet_files",
    ),
)
# Krakow: 6 sheets of the 1:10000 series (M-34-64-D-d-1 among them); 40 km
# and 50 km squares: 100 and 144 sheets.
SIX = BBox(560000, 240000, 568000, 246000, "EPSG:2180")
SQUARE_40 = BBox(560000, 240000, 600000, 280000, "EPSG:2180")
SQUARE_50 = BBox(560000, 240000, 610000, 290000, "EPSG:2180")
ONE_SHEET = "M-34-64-D-d-1"
GB = 10**9


def _sheets(area: BBox) -> list[str]:
    return find_sheets_for_bbox(area, series_scale(6), "1992")


@pytest.fixture
def router(monkeypatch) -> Router:
    """The sheet files of the test channel: ``HEAD`` gives the size set by
    ``serve``, ``GET`` a small ZIP."""
    from kartograf.download import collections as col

    install(monkeypatch, VOLUME)
    fake = Router()
    monkeypatch.setattr(col, "_session", lambda: fake)
    return fake


def _zip_answer(body: bytes) -> Response:
    headers = {"Content-Type": "application/zip", "Content-Length": str(len(body))}
    return Response(200, headers, body)


def serve(router: Router, sheets: list[str], size: int) -> None:
    for sheet in sheets:
        url = TEMPLATE.format(sheet=sheet)
        router.heads[_key(url)] = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(size),
        }
        router.add(url, functools.partial(_zip_answer, zip_bytes([f"{sheet}.tif"])))


def _download(tmp_path, **choice):
    return download_collection(
        product="e5volume", country="pl", root=tmp_path, cache=False, **choice
    )


def _heads(router: Router) -> list[str]:
    return [url for method, url in router.calls if method == "HEAD"]


def test_more_files_than_the_limit_refused_before_any_transfer(tmp_path, router):
    """144 sheets: refused with the number of files, the size estimated from
    five of them and the hint - no file is downloaded and only the sample is
    asked for its size."""
    sheets = _sheets(SQUARE_50)
    assert len(sheets) == 144
    serve(router, sheets, 60_000_000)

    with pytest.raises(ValidationError) as refused:
        _download(tmp_path, bbox=SQUARE_50)

    text = str(refused.value)
    assert text.startswith("e5volume: obszar daje 144 pliki do pobrania, ")
    assert "szacunkowo ok. 8,6 GB (sredni rozmiar 5 z 144 plikow wg HEAD" in text
    assert f"limit jednego zadania to {VOLUME_FILES} plikow i 10 GB" in text
    assert "Zawez obszar (--bbox, --sheet, --geometry)" in text
    assert "--check-updates --plan PLIK, potem --upgrade --plan PLIK" in text
    assert router.gets() == 0
    heads = _heads(router)
    assert len(heads) == 5
    assert heads[0] == TEMPLATE.format(sheet=sheets[0])
    assert heads[-1] == TEMPLATE.format(sheet=sheets[-1])
    assert not list(tmp_path.rglob("*.zip"))


def test_exactly_the_file_limit_is_downloaded(tmp_path, router):
    """100 files of 60 MB: within both limits, each file asked once by
    ``HEAD`` (the size notice reuses the answer) and downloaded once."""
    sheets = _sheets(SQUARE_40)
    assert len(sheets) == VOLUME_FILES
    serve(router, sheets, 60_000_000)

    report = _download(tmp_path, bbox=SQUARE_40)

    assert report.ok, report.failed
    assert len(report.files) == VOLUME_FILES
    urls = {TEMPLATE.format(sheet=sheet) for sheet in sheets}
    assert sorted(_heads(router)) == sorted(urls)
    assert router.gets() == VOLUME_FILES


def test_more_bytes_than_the_limit_refused(tmp_path, router):
    """Six files of 2 GB (12 GB) exceed the byte limit although there are
    few of them."""
    serve(router, _sheets(SIX), 2 * GB)

    with pytest.raises(ValidationError) as refused:
        _download(tmp_path, bbox=SIX)

    assert str(refused.value).startswith(
        "e5volume: obszar daje 6 plikow do pobrania, razem ok. 12,0 GB wg HEAD - "
        "limit jednego zadania"
    )
    assert router.gets() == 0


def test_local_files_do_not_count_but_force_counts_all(tmp_path, router):
    """The files already in the store are not downloaded again, so they do
    not count: after one sheet the other five weigh exactly the limit and
    are downloaded; ``force`` downloads all six again (12 GB) - refused."""
    sheets = _sheets(SIX)
    serve(router, sheets, 2 * GB)
    first = _download(tmp_path, sheet=ONE_SHEET)
    assert first.ok and [f.unit for f in first.files] == [ONE_SHEET]
    router.calls.clear()

    report = _download(tmp_path, bbox=SIX)

    assert report.ok, report.failed
    statuses = {f.unit: f.file.status for f in report.files}
    assert statuses.pop(ONE_SHEET) == "local"
    assert set(statuses.values()) == {"new"}
    assert 5 * 2 * GB == VOLUME_BYTES
    fetched = {TEMPLATE.format(sheet=sheet) for sheet in sheets if sheet != ONE_SHEET}
    assert sorted(_heads(router)) == sorted(fetched)  # once each, none for local
    assert router.gets() == 5

    with pytest.raises(ValidationError, match="obszar daje 6 plikow do pobrania"):
        _download(tmp_path, bbox=SIX, update="force")


def test_plan_of_fewer_positions_is_within_the_limit(tmp_path, router):
    """The hint of the refusal: a plan keeping four of the six positions
    (8 GB) is executed with ``upgrade`` - only its positions count."""
    serve(router, _sheets(SIX), 2 * GB)
    plan = check_collection(
        product="e5volume", country="pl", bbox=SIX, root=tmp_path, cache=False
    )
    assert [item.status for item in plan.items] == ["missing"] * 6
    kept = dataclasses.replace(plan, items=plan.items[:4])

    report = _download(tmp_path, bbox=SIX, update="upgrade", plan=kept)

    assert report.ok, report.failed
    assert sorted(f.unit for f in report.files) == sorted(
        item.unit for item in kept.items
    )
    assert router.gets() == 4
