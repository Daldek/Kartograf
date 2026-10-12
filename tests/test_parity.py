"""CLI = API parity (Z7, spec 6): the same request through ``kartograf.cli.main``
and through the library gives the same store (bytes of files and sidecars),
statuses, plan, data notices and errors - with the clock frozen.

Scenarios (spec 6) and their tests:

=====================================  ==========================================
scenario                               test
=====================================  ==========================================
PL-1992 sheet 1:10000                  test_pl_sheet
CZ sheet TM33 / SM5                    test_cz_sheet
CZ cutout                              test_cz_cutout
``auto`` PL+CZ, partial success        test_auto_partial_success
LAZ                                    test_laz_sheet
check + plan + upgrade with plan       test_check_plan_upgrade
input errors (missing / bad / outside) test_input_errors_same_type_and_text
BDOT10k, CORINE, SoilGrids, HSG        tests/test_parity_landcover.py
=====================================  ==========================================
"""

from unittest.mock import patch

import pytest

from kartograf.core.bbox import BBox
from kartograf.download.data import check_data, download_data
from kartograf.notices import Notice
from tests.parity import assert_same_store, run_both
from tests.test_cli import _cz_provider_mock
from tests.test_cli_update_modes import LazCliProvider
from tests.test_manager_campaigns import C14, FakeCampaignProvider

G = "N-34-139-C-a-3-1"
CZ_FACTORY = "kartograf.providers.cuzk.create_dmr_provider"


def _notice_lines(notices: tuple[Notice, ...]) -> list[str]:
    return [f"{'Info' if n.level == 'info' else 'Warning'}: {n.text}" for n in notices]


def _cli_notice_lines(stderr: str, notices: tuple[Notice, ...]) -> list[str]:
    """The CLI stderr lines that are notices (multi-line texts kept whole)."""
    expected = _notice_lines(notices)
    return [line for line in expected if line in stderr]


def _same(run, report, *, statuses: list[str] | None = None) -> None:
    assert_same_store(run.cli_store, run.api_store)
    assert run.cli_code == (0 if report.ok else 1)
    assert _cli_notice_lines(run.cli_stderr, report.notices) == _notice_lines(
        report.notices
    )
    if statuses is not None:
        assert [f.file.status for f in report.files] == statuses


@pytest.mark.usefixtures("frozen_clock")
def test_pl_sheet(tmp_path):
    fake = FakeCampaignProvider(C14)
    with patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(fake, None),
    ):
        run = run_both(
            [
                "download",
                "--product",
                "nmt",
                "--sheet",
                G,
                "--resolution",
                "1m",
                "--vertical-crs",
                "EVRF2007",
                "-q",
            ],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                sheet=G,
                resolution="1m",
                vertical_crs="EVRF2007",
            ),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
@pytest.mark.parametrize(("sheet", "resolution"), [("302_5550", "2m")])
def test_cz_sheet(tmp_path, sheet, resolution):
    with patch(CZ_FACTORY, return_value=_cz_provider_mock(resolution)):
        run = run_both(
            [
                "download",
                "--product",
                "nmt",
                "--sheet",
                sheet,
                "--resolution",
                resolution,
                "--vertical-crs",
                "Bpv",
                "-q",
            ],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                sheet=sheet,
                resolution=resolution,
                vertical_crs="Bpv",
            ),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
def test_cz_cutout(tmp_path):
    bbox = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")
    with patch(CZ_FACTORY, return_value=_cz_provider_mock()):
        run = run_both(
            [
                "download",
                "--product",
                "nmt",
                "--bbox=-447000,-1114000,-446000,-1113000",
                "--bbox-crs",
                "EPSG:5514",
                "--country",
                "cz",
                "--resolution",
                "2m",
                "--vertical-crs",
                "Bpv",
                "-q",
            ],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                bbox=bbox,
                country="cz",
                resolution="2m",
                vertical_crs="Bpv",
            ),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
def test_auto_partial_success(tmp_path):
    """Border bbox, CZ fails: code 0 and the same partial-success notice."""
    from kartograf.download.cutout import PlCutoutResult
    from kartograf.exceptions import DownloadError

    cz = _cz_provider_mock()
    cz.download_bbox.side_effect = DownloadError("CUZK 503")
    with (
        patch(CZ_FACTORY, return_value=cz),
        patch(
            "kartograf.download.cutout.download_pl_cutout",
            return_value=PlCutoutResult(None),
        ),
    ):
        run = run_both(
            [
                "download",
                "--product",
                "nmt",
                "--bbox",
                "18.60,49.73,18.66,49.76",
                "--bbox-crs",
                "EPSG:4326",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                "--target-crs",
                "EPSG:3045",
                "-q",
            ],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                bbox=BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326"),
                country="auto",
                resolution={"pl": "1m", "cz": "2m"},
                vertical_crs={"pl": "EVRF2007", "cz": "Bpv"},
                target_crs="EPSG:3045",
            ),
            tmp_path,
        )
    report = run.api_result
    _same(run, report)
    assert report.ok and run.cli_code == 0
    assert "Error: CUZK 503" in run.cli_stderr


@pytest.mark.usefixtures("frozen_clock")
def test_laz_sheet(tmp_path):
    with patch(
        "kartograf.providers.pl.gugik_laz.GugikLazProvider",
        side_effect=lambda **_kw: LazCliProvider(),
    ):
        run = run_both(
            [
                "download",
                "--product",
                "laz",
                "--sheet",
                "N-34-130-D-d-2-4",
                "--vertical-crs",
                "EVRF2007",
                "-q",
            ],
            lambda out: download_data(
                product="laz",
                output_dir=out,
                sheet="N-34-130-D-d-2-4",
                vertical_crs="EVRF2007",
            ),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
def test_check_plan_upgrade(tmp_path):
    """``--check-updates --plan`` = ``check_data``; ``--upgrade --plan`` =
    ``download_data(update="upgrade", plan=...)`` - same plan items and store."""
    fake = FakeCampaignProvider(C14)
    sheet_args = ["--sheet", G, "--resolution", "1m", "--vertical-crs", "EVRF2007"]
    selection = {
        "product": "nmt",
        "sheet": G,
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
    }
    plan_file = tmp_path / "plan.json"
    with patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(fake, None),
    ):
        checked = run_both(
            [
                "download",
                "--product",
                "nmt",
                *sheet_args,
                "--check-updates",
                "--plan",
                str(plan_file),
            ],
            lambda out: check_data(output_dir=out, **selection),
            tmp_path,
        )
        from kartograf.download.plan import UpdatePlan

        cli_plan = UpdatePlan.from_json(plan_file.read_text(encoding="utf-8"))
        api_plan = checked.api_result
        assert cli_plan.items == api_plan.items
        upgraded = run_both(
            [
                "download",
                "--product",
                "nmt",
                *sheet_args,
                "--upgrade",
                "--plan",
                str(plan_file),
                "-q",
            ],
            lambda out: download_data(
                output_dir=out, update="upgrade", plan=api_plan, **selection
            ),
            tmp_path,
        )
    _same(upgraded, upgraded.api_result, statuses=["new"])


@pytest.mark.parametrize(
    ("argv", "kwargs"),
    [
        (
            ["--sheet", G, "--resolution", "1m"],
            {"sheet": G, "resolution": "1m"},
        ),
        (
            ["--sheet", G, "--resolution", "3m", "--vertical-crs", "EVRF2007"],
            {"sheet": G, "resolution": "3m", "vertical_crs": "EVRF2007"},
        ),
        (
            ["--bbox", "2.0,40.0,2.1,40.1", "--bbox-crs", "EPSG:4326"]
            + ["--country", "auto", "--resolution", "1m", "--vertical-crs", "EVRF2007"],
            {
                "bbox": BBox(2.0, 40.0, 2.1, 40.1, "EPSG:4326"),
                "country": "auto",
                "resolution": "1m",
                "vertical_crs": "EVRF2007",
            },
        ),
    ],
    ids=["missing", "bad-value", "outside"],
)
def test_input_errors_same_type_and_text(tmp_path, argv, kwargs):
    run = run_both(
        ["download", "--product", "nmt", *argv],
        lambda out: download_data(product="nmt", output_dir=out, **kwargs),
        tmp_path,
    )
    assert run.cli_code == 1
    assert type(run.api_error).__name__ == "ValidationError"
    assert run.cli_stderr.strip() == f"Error: {run.api_error}"
    assert not run.cli_store.exists() and not run.api_store.exists()
