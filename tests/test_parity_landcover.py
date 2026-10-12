"""CLI = API parity (Z7, spec 6) for ``landcover download`` and
``soilgrids hsg``: same store bytes, statuses, plan and notices, frozen clock.

Scenarios: BDOT10k ``teryt``, BDOT10k area of several powiats (one failing),
CORINE CLMS and WMS preview, SoilGrids, HSG ``bbox`` and ``geometry``,
``--check-updates --plan`` + ``--upgrade --plan``.
"""

from unittest.mock import patch

import pytest

from kartograf.core.bbox import BBox
from kartograf.download.plan import UpdatePlan
from kartograf.hydrology import HSGCalculator
from kartograf.landcover.manager import LandCoverManager
from kartograf.notices import Notice
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.soilgrids import SoilGridsProvider
from tests.conftest import FakeCorine, FakeSoilGrids, tiny_geotiff, write_gpkg_layers
from tests.parity import assert_same_store, run_both
from tests.test_hsg import RasterSoilGrids
from tests.test_landcover_output_params import FakePackages

BBOX = BBox(770000, 509000, 772000, 511000, "EPSG:2180")
BBOX_ARG = "770000,509000,772000,511000"
CLAY = {"property": "clay", "depth": "0-5cm", "stat": "mean"}
CLAY_ARGS = ["--property", "clay", "--depth", "0-5cm", "--stat", "mean"]

pytestmark = pytest.mark.usefixtures("frozen_clock")


def _notice_lines(notices: tuple[Notice, ...]) -> list[str]:
    return [f"{'Info' if n.level == 'info' else 'Warning'}: {n.text}" for n in notices]


def _same(run, notices: tuple[Notice, ...], ok: bool) -> None:
    assert_same_store(run.cli_store, run.api_store)
    assert run.cli_code == (0 if ok else 1)
    lines = _notice_lines(notices)
    assert [line for line in lines if line in run.cli_stderr] == lines


def _providers(**by_name):
    """``LandCoverManager`` by name -> a fresh no-network provider."""
    return patch.object(
        LandCoverManager,
        "_get_provider_by_name",
        staticmethod(lambda name, cache=None: by_name[name]()),
    )


def _bdot(teryts, packages):
    return (
        patch.object(Bdot10kProvider, "download_package", side_effect=packages),
        patch.object(Bdot10kProvider, "teryts_for_area", return_value=list(teryts)),
    )


def _landcover(tmp_path, source, cli_args, **api_kwargs):
    return run_both(
        ["landcover", "download", "--source", source, *cli_args],
        lambda out: LandCoverManager(out, source).download(**api_kwargs),
        tmp_path,
    )


def test_bdot_teryt(tmp_path):
    download, teryts = _bdot(["1465"], FakePackages())
    with download, teryts:
        run = _landcover(tmp_path, "bdot10k", ["--teryt", "1465"], teryt="1465")
    _same(run, run.api_result.notices, run.api_result.ok)
    assert [r.file.status for r in run.api_result.files] == ["new"]


def test_bdot_area_of_powiats_one_failing(tmp_path):
    download, teryts = _bdot(["0208", "0224", "0261"], FakePackages(fail={"0224"}))
    with download, teryts:
        run = _landcover(
            tmp_path,
            "bdot10k",
            ["--bbox", BBOX_ARG, "--layers", "SWRS,PTWP", "--keep-raw"],
            bbox=BBOX,
            layers=("SWRS", "PTWP"),
            keep_raw=True,
        )
    result = run.api_result
    _same(run, result.notices, result.ok)
    assert not result.ok and [f.unit for f in result.failed] == ["0224"]
    assert f"Error: 0224: {result.failed[0].error}" in run.cli_stderr


def _clms_tiff(bbox, out, year, timeout):
    target = out.with_suffix(".tif")
    target.write_bytes(tiny_geotiff(-128, 3))
    return target


@pytest.mark.parametrize("clms", [True, False], ids=["clms", "preview"])
def test_corine(tmp_path, clms):
    with (
        _providers(
            corine=lambda: CorineProvider(session=FakeCorine(), use_proxy=False)
        ),
        patch.object(CorineProvider, "has_clms_token", new=clms),
        patch.object(CorineProvider, "_download_via_clms", side_effect=_clms_tiff),
    ):
        run = _landcover(
            tmp_path,
            "corine",
            ["--sheet", "M-33-036-A", "--year", "2018"],
            sheet="M-33-036-A",
            year=2018,
        )
    _same(run, run.api_result.notices, run.api_result.ok)
    assert bool(run.api_result.notices) is not clms


def test_soilgrids(tmp_path):
    with _providers(soilgrids=lambda: SoilGridsProvider(session=FakeSoilGrids())):
        run = _landcover(
            tmp_path, "soilgrids", ["--bbox", BBOX_ARG, *CLAY_ARGS], bbox=BBOX, **CLAY
        )
    _same(run, run.api_result.notices, run.api_result.ok)


def _hsg(tmp_path, cli_args, **api_kwargs):
    with _providers(soilgrids=RasterSoilGrids):
        return run_both(
            ["soilgrids", "hsg", "--depth", "0-5cm", "-q", *cli_args],
            lambda out: HSGCalculator(out).calculate_hsg(depth="0-5cm", **api_kwargs),
            tmp_path,
        )


def test_hsg_bbox(tmp_path):
    run = _hsg(tmp_path, ["--bbox", BBOX_ARG], bbox=BBOX)
    _same(run, run.api_result.notices, run.api_result.ok)
    assert run.api_result.file.status == "new"


def test_hsg_geometry(tmp_path):
    gpkg = write_gpkg_layers(tmp_path / "area.gpkg", ["zlewnia", "inna"])
    with patch("kartograf.core.geometry.get_overall_bbox", return_value=BBOX):
        run = _hsg(tmp_path, ["--geometry", str(gpkg)], geometry=gpkg)
    _same(run, run.api_result.notices, run.api_result.ok)
    assert run.api_result.notices  # GEOMETRY_LAYER_DEFAULT on both sides


def test_check_plan_upgrade(tmp_path):
    """``--check-updates --plan`` = ``check``; ``--upgrade --plan`` =
    ``download(update="upgrade", plan=...)`` - same plan and store."""
    plan_file = tmp_path / "plan.json"
    soil = _providers(soilgrids=lambda: SoilGridsProvider(session=FakeSoilGrids()))
    args = ["--bbox", BBOX_ARG, *CLAY_ARGS]
    with soil:
        checked = run_both(
            ["landcover", "download", "--source", "soilgrids", *args]
            + ["--check-updates", "--plan", str(plan_file)],
            lambda out: LandCoverManager(out, "soilgrids").check(bbox=BBOX, **CLAY),
            tmp_path,
        )
        api_plan = checked.api_result
        cli_plan = UpdatePlan.from_json(plan_file.read_text(encoding="utf-8"))
        assert cli_plan.items == api_plan.items
        upgraded = run_both(
            ["landcover", "download", "--source", "soilgrids", *args]
            + ["--upgrade", "--plan", str(plan_file)],
            lambda out: LandCoverManager(out, "soilgrids").download(
                bbox=BBOX, update="upgrade", plan=api_plan, **CLAY
            ),
            tmp_path,
        )
    _same(upgraded, upgraded.api_result.notices, upgraded.api_result.ok)
