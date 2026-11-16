"""CLI and public API produce identical versioned stores for the E1 products
(NMT 100 m, CZ contours, the oblique orthophotomap)."""

import pytest

from kartograf.download import collections as col
from kartograf.download import cz_contours
from kartograf.download.data import check_data, download_data
from tests.integration.test_cz_contours import FakeOpenzu
from tests.integration.test_imagery_products import OBLIQUE_SHEET
from tests.integration.test_imagery_products import images as images  # noqa: F401 - fixture
from tests.integration.test_nmt_100m import KRAKOW, FakeGugik
from tests.support.parity import assert_notices_printed, assert_same_store, run_both

pytestmark = pytest.mark.usefixtures("frozen_clock")


def _same(run, statuses: list[str]) -> None:
    assert run.cli_code == 0, run.cli_stderr
    assert run.api_result.ok, run.api_result.failed
    assert_same_store(run.cli_store, run.api_store)
    assert_notices_printed(run.cli_stderr, run.api_result.notices)
    assert [unit.file.status for unit in run.api_result.files] == statuses


def test_nmt_100m_voivodeship(tmp_path, monkeypatch):
    """``elevation download --product nmt --resolution 100m`` = ``download_data``:
    the ZIP of voivodeship 12 for an area in Krakow."""
    gugik = FakeGugik()  # one ZIP for both runs (its member timestamp)
    monkeypatch.setattr(col, "_session", lambda: gugik)
    run = run_both(
        [
            "elevation",
            "download",
            "--product",
            "nmt",
            "--resolution",
            "100m",
            "--country",
            "pl",
            "--bbox=564000,241000,570000,247000",
            "--bbox-crs",
            "EPSG:2180",
            "-q",
        ],
        lambda out: download_data(
            product="nmt", resolution="100m", country="pl", bbox=KRAKOW, root=out
        ),
        tmp_path,
    )
    _same(run, ["new"])


def test_contours_sheet(tmp_path, monkeypatch):
    """``elevation download --product contours --format DGN --sheet CTES96`` =
    ``download_data(product="contours", format="DGN", ...)``."""
    fake = FakeOpenzu()
    monkeypatch.setattr(cz_contours, "_session", lambda: fake)
    run = run_both(
        [
            "elevation",
            "download",
            "--product",
            "contours",
            "--format",
            "DGN",
            "--sheet",
            "CTES96",
            "-q",
        ],
        lambda out: download_data(
            product="contours", format="DGN", sheet="CTES96", root=out
        ),
        tmp_path,
    )
    _same(run, ["new"])


@pytest.mark.usefixtures("images")
def test_oblique_direction_and_check_lines(tmp_path):
    """``imagery download --product oblique-orto --direction n`` =
    ``download_data(direction="n")``: one file of the sheet; the check and
    the download of all four directions print one line per file, both named
    by the path below ``--root`` (one format of the status lines)."""
    argv = ["imagery", "download", "--product", "oblique-orto", "--sheet"]
    run = run_both(
        [*argv, OBLIQUE_SHEET, "--direction", "n", "-q"],
        lambda out: download_data(
            product="oblique-orto", sheet=OBLIQUE_SHEET, direction="n", root=out
        ),
        tmp_path,
    )
    _same(run, ["new"])
    assert run.api_result.files[0].file.path.name == f"{OBLIQUE_SHEET}_n.tif"

    checked = run_both(
        [*argv, OBLIQUE_SHEET, "--check"],
        lambda out: check_data(product="oblique-orto", sheet=OBLIQUE_SHEET, root=out),
        tmp_path,
    )
    lines = checked.cli_stdout.splitlines()
    assert [line.split(": ")[0] for line in lines] == [
        "/".join((item.segment, item.hierarchy, item.name))
        for item in checked.api_result.items
    ]
    assert [line.split(": ")[0].rsplit("/", 1)[1] for line in lines] == [
        f"{OBLIQUE_SHEET}_{code}.tif" for code in ("n", "e", "s", "w")
    ]
    assert [item.status for item in checked.api_result.items] == [
        "current",
        "missing",
        "missing",
        "missing",
    ]

    every = run_both(
        [*argv, OBLIQUE_SHEET],
        lambda out: download_data(
            product="oblique-orto", sheet=OBLIQUE_SHEET, root=out
        ),
        tmp_path,
    )
    _same(every, ["local", "new", "new", "new"])
    status = [line for line in every.cli_stdout.splitlines() if ".tif: " in line]
    assert [line.split(": ")[0] for line in status] == [
        "/".join((item.segment, item.hierarchy, item.name))
        for item in checked.api_result.items
    ]
