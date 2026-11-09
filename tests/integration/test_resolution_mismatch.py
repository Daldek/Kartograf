"""A downloaded grid of another cell size than its index record declares (ADR-060).

GUGiK serves 1 m grids under records of the NMT 5 m index (campaign 75114 and four
others, PROGRESS item 28). The cell size of the file (the ``.asc`` header, the
GeoTIFF transform) is compared with ``resolution_m`` of the record before the file
is written: a mismatch is a failed unit with the code ``data_error`` and the reason
``resolution_mismatch``, and nothing enters the store or the output directory.

The grids are 3 x 3 headers inside the frame of the sheet; the provider is a real
``GugikProvider`` (5 m, EVRF2007) whose index answer and transfer are replaced, so
nothing goes to the network.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.core.sheet_parser import SheetParser
from kartograf.download.campaigns import verify_cell_size
from kartograf.download.data import download_data
from kartograf.exceptions import ResolutionMismatchError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.skorowidz import SkorowidzRecord

SHEET = "N-33-119-A-d-4-3"
PARENT = "N-33-119-A-d-4"  # four 1:5000 sheets of the 5 m variant, SHEET the third
URL = "https://opendata.geoportal.gov.pl/NumDaneWys/NMT/75114/75114_1133574_{}.asc"


def record(sheet: str):
    """An NMT 5 m index record of the sheet (campaign 75114, flown 2021-09-07)."""
    return SkorowidzRecord(
        url=URL.format(sheet),
        sheet=sheet,
        aktualnosc="2021-09-07",
        dt_pzgik="2021-12-31",
        layer="SkorowidzNMT2021",
        system="1992",
        zone=None,
        resolution_m=5.0,
        full_sheet=True,
        raw={
            "format": "ARC/INFO ASCII GRID",
            "aktualnoscRok": "2021",
            "ukladWspolrzednychPoziomych": "PL-1992",
            "ukladWspolrzednychPionowych": "PL-EVRF2007-NH",
        },
    )


def header(sheet: str, cell_lines: str) -> bytes:
    """A 3 x 3 AAIGrid inside the frame of the sheet with the given cell size lines."""
    frame = SheetParser(sheet).get_bbox()
    return (
        f"ncols 3\nnrows 3\nxllcorner {frame.min_x + 100}\n"
        f"yllcorner {frame.min_y + 100}\n{cell_lines}\nNODATA_value -9999\n"
        "1 2 3\n4 5 6\n7 8 9\n"
    ).encode()


def staged(tmp_path: Path, body: bytes, name: str = f"{SHEET}.asc") -> Path:
    path = tmp_path / name
    path.write_bytes(body)
    return path


@pytest.mark.parametrize(
    "cell_lines",
    ["CELLSIZE 5", "cellsize 5.0", "cellsize 5.00", "dx 5\ndy 5.00"],
    ids=["CELLSIZE 5", "cellsize 5.0", "cellsize 5.00", "dx dy"],
)
def test_verify_cell_size_declared_5m_header_passes(tmp_path, cell_lines):
    path = staged(tmp_path, header(SHEET, cell_lines))

    verify_cell_size(path, ".asc", record(SHEET), sheet=SHEET, campaign="c")


def test_verify_cell_size_1m_header_under_5m_record_raises_with_facts(tmp_path):
    path = staged(tmp_path, header(SHEET, "cellsize 1.00"))
    rec = record(SHEET)

    with pytest.raises(ResolutionMismatchError) as caught:
        verify_cell_size(
            path,
            ".asc",
            rec,
            sheet=SHEET,
            campaign="2021-09-07_75114",
            years=(2020, 2021, 2023, 2025),
        )

    error = caught.value
    assert (error.code, error.reason, error.exit_code) == (
        "data_error",
        "resolution_mismatch",
        7,
    )
    assert error.details() == {
        "reason": "resolution_mismatch",
        "sheet": SHEET,
        "campaign": "2021-09-07_75114",
        "url": rec.url,
        "declared_m": 5.0,
        "found_m": 1.0,
    }
    # the hint names the flags and the other years of the sheet, not its own
    assert error.hint is not None
    assert "--year" in error.hint and "--max-year" in error.hint
    assert "2020, 2023, 2025" in error.hint


def test_verify_cell_size_one_axis_off_raises(tmp_path):
    path = staged(tmp_path, header(SHEET, "dx 5\ndy 1"))

    with pytest.raises(ResolutionMismatchError) as caught:
        verify_cell_size(path, ".asc", record(SHEET), sheet=SHEET, campaign="c")

    assert caught.value.found_m == 1.0


def test_verify_cell_size_within_a_millimetre_passes(tmp_path):
    path = staged(tmp_path, header(SHEET, "cellsize 5.0009"))

    verify_cell_size(path, ".asc", record(SHEET), sheet=SHEET, campaign="c")


def test_verify_cell_size_large_pl2000_5m_grid_passes(tmp_path):
    """A PL-2000 5 m sheet of 6.6 to 10.9 MB (campaign 73929) is genuine: only the
    header decides, not the size of the grid."""
    path = staged(
        tmp_path,
        b"ncols 1800\nnrows 1200\nxllcorner 6559000.00\nyllcorner 5571000.00\n"
        b"cellsize 5.00\nnodata_value -9999\n",
        "6.179.12.20.asc",
    )

    verify_cell_size(path, ".asc", record(SHEET), sheet="6.179.12.20", campaign="c")


@pytest.mark.parametrize(("cell", "fails"), [(5.0, False), (1.0, True)])
def test_verify_cell_size_geotiff_reads_the_transform(tmp_path, cell, fails):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    frame = SheetParser(SHEET).get_bbox()
    path = tmp_path / f"{SHEET}.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=3,
        height=3,
        count=1,
        dtype="float32",
        crs="EPSG:2180",
        transform=from_origin(frame.min_x, frame.max_y, cell, cell),
    ) as dataset:
        dataset.write(np.ones((1, 3, 3), dtype="float32"))

    if fails:
        with pytest.raises(ResolutionMismatchError) as caught:
            verify_cell_size(path, ".tif", record(SHEET), sheet=SHEET, campaign="c")
        assert (caught.value.declared_m, caught.value.found_m) == (5.0, 1.0)
    else:
        verify_cell_size(path, ".tif", record(SHEET), sheet=SHEET, campaign="c")


class _Source:
    """The index answer and the files of the patched ``GugikProvider``."""

    def __init__(self, bodies: dict[str, bytes]):
        self.bodies = bodies

    def resolve_campaigns(self, provider, sheet, **_):
        return [record(sheet)]

    def download_record(self, provider, rec, path, timeout=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.bodies[rec.sheet])
        return path


def run(tmp_path: Path, bodies: dict[str, bytes], **target):
    source = _Source(bodies)
    with (
        patch.object(
            GugikProvider,
            "resolve_campaigns",
            autospec=True,
            side_effect=source.resolve_campaigns,
        ),
        patch.object(
            GugikProvider,
            "download_record",
            autospec=True,
            side_effect=source.download_record,
        ),
    ):
        return download_data(
            product="nmt",
            resolution="5m",
            vertical_crs="EVRF2007",
            cache=False,
            **target,
        )


def files_under(directory: Path) -> list[str]:
    return sorted(
        str(p.relative_to(directory))
        for p in directory.rglob("*")
        if p.is_file() and p.name != "kartograf-store.json"
    )


@pytest.mark.parametrize("mode", ["root", "output_dir"])
def test_download_1m_grid_under_5m_record_is_a_failed_unit_and_writes_nothing(
    tmp_path, mode
):
    target = tmp_path / "target"

    report = run(
        tmp_path,
        {SHEET: header(SHEET, "cellsize 1.00")},
        sheet=SHEET,
        **{mode: target},
    )

    assert not report.ok and report.files == ()
    (failure,) = report.failed
    assert (failure.unit, failure.kind, failure.code, failure.reason) == (
        SHEET,
        "resolution_mismatch",
        "data_error",
        "resolution_mismatch",
    )
    # the unit carries only a message: the hint that names another flight is in it
    assert "--year" in failure.error and "--max-year" in failure.error
    # no version, no standard path, no full_sheet/ link, no sidecar, no plain file
    assert not target.exists() or files_under(target) == []


@pytest.mark.parametrize("cell_lines", ["CELLSIZE 5", "cellsize 5.0", "cellsize 5.00"])
def test_download_5m_grid_is_stored(tmp_path, cell_lines):
    report = run(
        tmp_path, {SHEET: header(SHEET, cell_lines)}, sheet=SHEET, root=tmp_path / "s"
    )

    assert report.ok and report.failed == ()
    assert [f.unit for f in report.files] == [SHEET]


def test_download_list_fails_only_the_1m_sheet(tmp_path):
    """A sheet list keeps the 5 m sheets and fails the 1 m one as its own unit."""
    root = tmp_path / "s"
    leaves = [f"{PARENT}-{n}" for n in range(1, 5)]
    bad = SHEET
    bodies = {
        leaf: header(leaf, "cellsize 1.00" if leaf == bad else "cellsize 5.00")
        for leaf in leaves
    }

    report = run(tmp_path, bodies, sheet=PARENT, root=root)

    assert not report.ok
    assert sorted(f.unit for f in report.files) == [s for s in leaves if s != bad]
    assert [(f.unit, f.code, f.reason) for f in report.failed] == [
        (bad, "data_error", "resolution_mismatch")
    ]
    stored = files_under(root)
    assert stored and not any(bad in name for name in stored)
