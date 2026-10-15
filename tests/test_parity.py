"""CLI = API parity (Z7, spec 6): the same request through ``kartograf.cli.main``
and through the library gives the same store (bytes of files and sidecars),
statuses, plan, data notices and errors - with the clock frozen.

Scenarios (spec 6) and their tests:

=========================================  ==========================================
scenario                                   test
=========================================  ==========================================
PL-1992 sheet 1:10000                      test_pl_sheet
PL-1992 sheet NMT 0.5m (WFS index)         test_pl_sheet_0_5m
orthophoto sheet (``imagery download``)    test_orto_sheet_through_imagery
coarser sheet code (expansion)             test_coarser_sheet_expands_with_no_cov...
PL-2000 with ``scale``                     test_pl2000_sheet_with_scale
PL area ``sheet_system=1992`` / ``2000``   test_pl_area_sheet_system
PL ``geometry``                            test_pl_geometry
campaigns (all, ``min_year``, full sheet)  test_campaign_options
PL cutout ``cutout`` + ``horizontal_crs``  test_pl_cutout
CZ sheet TM33 / SM5                        test_cz_sheet / test_cz_sm5_sheet
CZ cutout                                  test_cz_cutout
``auto`` PL+CZ, partial success            test_auto_partial_success
``auto`` narrowed to PL                    test_auto_narrowed_to_pl
LAZ sheet / bbox EPSG:4326 + min_density   test_laz_sheet / test_laz_bbox_4326_mi...
check + plan + upgrade with plan           test_check_plan_upgrade
upgrade with a stale plan                  test_upgrade_with_stale_plan
input errors (missing / bad / outside)     test_input_errors_same_type_and_text
BDOT10k, CORINE, SoilGrids, HSG            tests/test_parity_landcover.py
availability report ``--json``            test_availability_json
=========================================  ==========================================
"""

import contextlib
import io
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.core.bbox import BBox
from kartograf.core.sheet_parser import SheetParser
from kartograf.download.cutout import PlCutoutResult
from kartograf.download.data import check_data, download_data
from kartograf.exceptions import ValidationError
from kartograf.notices import AUTO_CLIPPED
from kartograf.providers.pl.gugik import GugikProvider
from tests.conftest import RecordedIndex, wfs_endpoint, wfs_fixture, wfs_response
from tests.parity import assert_notices_printed, assert_same_store, run_both
from tests.test_cli import _cz_provider_mock
from tests.test_cli_update_modes import LazCliProvider
from tests.test_geometry import _write_prj
from tests.test_manager_campaigns import C14, REC, FakeCampaignProvider

G = "N-34-139-C-a-3-1"
CZ_FACTORY = "kartograf.providers.cuzk.create_dmr_provider"


def _same(run, report, *, statuses: list[str] | None = None) -> None:
    assert_same_store(run.cli_store, run.api_store)
    assert run.cli_code == (0 if report.ok else 1)
    assert_notices_printed(run.cli_stderr, report.notices)
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
                "elevation",
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


def _sheet_0_5m_session(sheet: str):
    """WFS answers of the sheet (recorded 2026-10-15) and a small ASC inside
    its frame for the 0.5m record of 2025."""
    url = f"https://opendata.geoportal.gov.pl/NumDaneWys/NMT/84020/84020_1844081_{sheet}.asc"
    frame = SheetParser(sheet).get_bbox(crs="EPSG:2180")
    body = (
        f"ncols 2\nnrows 2\nxllcorner {frame.min_x + 10}\nyllcorner "
        f"{frame.min_y + 10}\ncellsize 0.5\nNODATA_value -9999\n1 2\n3 4\n"
    ).encode("ascii")
    index = wfs_fixture(f"sheet_nmt_evrf2007_{sheet}.xml")
    endpoint = wfs_endpoint("nmt_evrf2007")

    def get(requested, **kwargs):
        if requested.startswith(f"{endpoint}?"):
            return wfs_response(index)
        assert requested == url, requested
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.raise_for_status = Mock()
        response.headers = {}
        response.iter_content = Mock(return_value=[body])
        return response

    session = Mock(spec=requests.Session)
    session.get = Mock(side_effect=get)
    return session


@pytest.mark.usefixtures("frozen_clock")
def test_pl_sheet_0_5m(tmp_path):
    """A grid variant of the registry through the real provider and the WFS
    index: the same store, sidecar (``pl.gugik.nmt_0_5m``) and statuses."""
    sheet = "N-33-58-A-c-1-4"
    with patch(
        "kartograf.transport.http.make_gugik_session",
        return_value=_sheet_0_5m_session(sheet),
    ):
        run = run_both(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "--sheet",
                sheet,
                "--resolution",
                "0.5m",
                "--vertical-crs",
                "EVRF2007",
                "-q",
            ],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                sheet=sheet,
                resolution="0.5m",
                vertical_crs="EVRF2007",
            ),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])
    assert (run.api_store / "nmt" / "pl_1992_0.5m_evrf2007").is_dir()


@pytest.mark.usefixtures("frozen_clock")
def test_availability_json(tmp_path, monkeypatch):
    """``elevation availability --json`` prints exactly the JSON of
    ``check_availability`` and its notices on stderr (Pomorze, coast)."""
    from kartograf.cli import main
    from kartograf.download.availability import check_availability

    monkeypatch.chdir(tmp_path)
    areas = {
        f"nmt_{vcrs}": [f"area_nmt_{vcrs}_pomorze.xml.gz"]
        for vcrs in ("evrf2007", "kron86")
    }
    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        patch(
            "kartograf.transport.http.make_gugik_session",
            return_value=RecordedIndex(areas, coast=True),
        ),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
    ):
        code = main(
            [
                "elevation",
                "availability",
                "--product",
                "nmt",
                "--country",
                "pl",
                "--bbox",
                "339000,744800,343000,747000",
                "--json",
                "--force",
            ]
        )
    with patch(
        "kartograf.transport.http.make_gugik_session",
        return_value=RecordedIndex(areas, coast=True),
    ):
        report = check_availability(
            product="nmt",
            country="pl",
            bbox=BBox(339000, 744800, 343000, 747000, "EPSG:2180"),
            force=True,
        )

    assert code == 0
    assert stdout.getvalue() == report.to_json()
    assert_notices_printed(stderr.getvalue(), report.notices)


@pytest.mark.usefixtures("frozen_clock")
def test_orto_sheet_through_imagery(tmp_path):
    """``imagery download`` = ``download_data(product="orto")`` (ADR-039):
    the group passes no resolution or vertical CRS."""
    fake = FakeCampaignProvider(C14)
    with patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(fake, None),
    ):
        run = run_both(
            ["imagery", "download", "--product", "orto", "--sheet", G, "-q"],
            lambda out: download_data(product="orto", output_dir=out, sheet=G),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
@pytest.mark.parametrize(("sheet", "resolution"), [("302_5550", "2m")])
def test_cz_sheet(tmp_path, sheet, resolution):
    with patch(CZ_FACTORY, return_value=_cz_provider_mock(resolution)):
        run = run_both(
            [
                "elevation",
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
                "elevation",
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
                "--cutout",
                "--horizontal-crs",
                "EPSG:5514",
                "-q",
            ],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                bbox=bbox,
                country="cz",
                resolution="2m",
                vertical_crs="Bpv",
                cutout=True,
                horizontal_crs="EPSG:5514",
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
                "elevation",
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
                "--cutout",
                "--horizontal-crs",
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
                cutout=True,
                horizontal_crs="EPSG:3045",
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
                "elevation",
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
                "elevation",
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
                "elevation",
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
        ["elevation", "download", "--product", "nmt", *argv],
        lambda out: download_data(product="nmt", output_dir=out, **kwargs),
        tmp_path,
    )
    assert run.cli_code == 1
    assert type(run.api_error).__name__ == "ValidationError"
    assert run.cli_stderr.strip() == f"Error: {run.api_error}"
    assert not run.cli_store.exists() and not run.api_store.exists()


@pytest.mark.parametrize("check", [False, True], ids=["download", "check"])
@pytest.mark.parametrize(
    ("bbox_text", "bbox"),
    [
        ("10,10,5,5", BBox(10, 10, 5, 5, "EPSG:2180")),
        ("nan,1,2,3", BBox(float("nan"), 1, 2, 3, "EPSG:2180")),
        (
            "750000,5500000,750100,5500100",
            BBox(750000, 5500000, 750100, 5500100, "EPSG:2177"),
        ),
    ],
    ids=["inverted", "nan", "unsupported-sheet-crs"],
)
def test_bbox_input_errors_match_cli_and_api(tmp_path, check, bbox_text, bbox):
    options = {
        "product": "nmt",
        "bbox": bbox,
        "country": "pl",
        "sheet_system": "1992",
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "cache": False,
    }
    argv = [
        "elevation",
        "download",
        "--product",
        "nmt",
        f"--bbox={bbox_text}",
        "--bbox-crs",
        bbox.crs,
        "--country",
        "pl",
        "--sheet-system",
        "1992",
        "--resolution",
        "1m",
        "--vertical-crs",
        "EVRF2007",
        "-q",
    ]
    if check:
        argv.append("--check-updates")
    operation = check_data if check else download_data
    run = run_both(argv, lambda out: operation(output_dir=out, **options), tmp_path)
    assert run.cli_code == 1
    assert type(run.api_error) is ValidationError
    assert run.cli_stderr == f"Error: {run.api_error}\n"
    assert run.cli_stdout == ""
    assert not run.cli_store.exists() and not run.api_store.exists()


# --- spec 6 scenarios (Task 15) ----------------------------------------------

PL_SHEET_ARGS = ["--resolution", "1m", "--vertical-crs", "EVRF2007"]
PL_SHEET_KW = {"resolution": "1m", "vertical_crs": "EVRF2007"}


class AnySheetProvider(FakeCampaignProvider):
    """Campaign provider with one record (84183) for every sheet code."""

    def resolve_campaigns(self, sheet, **kwargs):
        record = REC["84183"]
        url = record.url.replace(G, sheet)
        return [replace(record, sheet=sheet, url=url)]


def _pl_store(fake):
    return patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(fake, None),
    )


def _pl(tmp_path, fake, cli: list[str], **api):
    """``elevation download`` of PL sheets through CLI and ``download_data``."""
    with _pl_store(fake):
        return run_both(
            ["elevation", "download", "--product", "nmt", *cli, "-q"],
            lambda out: download_data(product="nmt", output_dir=out, **api),
            tmp_path,
        )


def _inner(sheet: str, *, crs: str = "EPSG:2180") -> BBox:
    """A bbox strictly inside the sheet frame (selects that sheet only)."""
    b = SheetParser(sheet).get_bbox(crs=crs)
    dx, dy = (b.max_x - b.min_x) / 4, (b.max_y - b.min_y) / 4
    return BBox(b.min_x + dx, b.min_y + dy, b.max_x - dx, b.max_y - dy, crs)


def _bbox_arg(b: BBox) -> str:
    return f"--bbox={b.min_x},{b.min_y},{b.max_x},{b.max_y}"


@pytest.mark.usefixtures("frozen_clock")
def test_coarser_sheet_expands_with_no_coverage_notices(tmp_path):
    parent = G.rsplit("-", 1)[0]  # 1:25000 -> 4 sheets, data only for G
    run = _pl(
        tmp_path,
        FakeCampaignProvider(C14),
        ["--sheet", parent, *PL_SHEET_ARGS],
        sheet=parent,
        **PL_SHEET_KW,
    )
    report = run.api_result
    _same(run, report)
    assert [f.unit for f in report.files] == [G]
    assert report.notices  # NO_COVERAGE_SOME for the other three


@pytest.mark.usefixtures("frozen_clock")
def test_pl2000_sheet_with_scale(tmp_path):
    run = _pl(
        tmp_path,
        AnySheetProvider(C14),
        ["--sheet", "7.171.21", "--scale", "1:5000", *PL_SHEET_ARGS],
        sheet="7.171.21",
        scale="1:5000",
        **PL_SHEET_KW,
    )
    _same(run, run.api_result)
    assert len(run.api_result.files) == 4


@pytest.mark.usefixtures("frozen_clock")
@pytest.mark.parametrize("sheet_system", ["1992", "2000"])
def test_pl_area_sheet_system(tmp_path, sheet_system):
    bbox = _inner(G)
    scale = ["--scale", "1:5000"] if sheet_system == "2000" else []
    run = _pl(
        tmp_path,
        AnySheetProvider(C14),
        [_bbox_arg(bbox), "--country", "pl", "--sheet-system", sheet_system, *scale]
        + PL_SHEET_ARGS,
        bbox=bbox,
        country="pl",
        sheet_system=sheet_system,
        scale="1:5000" if sheet_system == "2000" else None,
        **PL_SHEET_KW,
    )
    _same(run, run.api_result)
    assert run.api_result.files


@pytest.mark.usefixtures("frozen_clock")
def test_pl_geometry(tmp_path):
    shp = tmp_path / "area.shp"
    shp.touch()
    _write_prj(tmp_path / "area.prj")
    with (
        patch("kartograf.core.geometry.get_overall_bbox", return_value=_inner(G)),
        patch("kartograf.core.geometry.find_sheets_for_geometry", return_value=[G]),
    ):
        run = _pl(
            tmp_path,
            FakeCampaignProvider(C14),
            ["--geometry", str(shp), "--country", "pl", "--sheet-system", "1992"]
            + PL_SHEET_ARGS,
            geometry=shp,
            country="pl",
            sheet_system="1992",
            **PL_SHEET_KW,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
@pytest.mark.parametrize(
    ("cli", "api"),
    [
        (["--all-campaigns"], {"all_campaigns": True}),
        (["--min-year", "2020"], {"min_year": 2020}),
        (["--full-sheet"], {"full_sheet": True}),
    ],
    ids=["all-campaigns", "min-year", "full-sheet"],
)
def test_campaign_options(tmp_path, cli, api):
    run = _pl(
        tmp_path,
        FakeCampaignProvider(C14),
        ["--sheet", G, *PL_SHEET_ARGS, *cli],
        sheet=G,
        **PL_SHEET_KW,
        **api,
    )
    _same(run, run.api_result)
    assert run.api_result.files


@pytest.mark.usefixtures("frozen_clock")
def test_pl_cutout(tmp_path):
    from tests.test_wcs_cutout import ALL_LAND, BBOX, MASK, _synthetic_session

    def provider(*_args, **_kwargs):
        return GugikProvider(
            session=_synthetic_session(lambda xs, ys: xs + ys),
            vertical_crs="EVRF2007",
            resolution="1m",
        )

    with (
        patch(MASK, return_value=ALL_LAND),
        patch("kartograf.providers.pl.create_nmt_provider", side_effect=provider),
    ):
        run = run_both(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                _bbox_arg(BBOX),
                "--country",
                "pl",
            ]
            + ["--cutout", "--horizontal-crs", "EPSG:2180", *PL_SHEET_ARGS, "-q"],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                bbox=BBOX,
                country="pl",
                cutout=True,
                horizontal_crs="EPSG:2180",
                **PL_SHEET_KW,
            ),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
def test_cz_sm5_sheet(tmp_path):
    from kartograf.providers.cuzk.sheets import SheetInfo

    provider = _cz_provider_mock("5m")
    provider.sheet_index.sm5_sheet.return_value = SheetInfo(
        sheet="CTES96",
        name="Cesky Tesin 9-6",
        bbox=BBox(-450000, -1114000, -447500, -1112000, "EPSG:5514"),
        podil=0.99,
        in_cz=None,
    )
    with patch(CZ_FACTORY, return_value=provider):
        run = run_both(
            ["elevation", "download", "--product", "nmt", "--sheet", "CTES96"]
            + ["--vertical-crs", "Bpv", "-q"],
            lambda out: download_data(
                product="nmt", output_dir=out, sheet="CTES96", vertical_crs="Bpv"
            ),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
def test_auto_narrowed_to_pl(tmp_path):
    """Rozewie: ``auto`` without CZ, PL part clipped - same notices and store."""
    bbox = BBox(455000, 773000, 459000, 784000, "EPSG:2180")
    with patch(
        "kartograf.download.cutout.download_pl_cutout",
        return_value=PlCutoutResult(None),
    ):
        run = run_both(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                _bbox_arg(bbox),
                "--country",
                "auto",
            ]
            + ["--cutout", "--horizontal-crs", "EPSG:2180", *PL_SHEET_ARGS, "-q"],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                bbox=bbox,
                country="auto",
                cutout=True,
                horizontal_crs="EPSG:2180",
                **PL_SHEET_KW,
            ),
            tmp_path,
        )
    _same(run, run.api_result)
    assert any(n.code == AUTO_CLIPPED for n in run.api_result.notices)


@pytest.mark.usefixtures("frozen_clock")
def test_laz_bbox_4326_min_density(tmp_path):
    bbox = BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326")
    with patch(
        "kartograf.providers.pl.gugik_laz.GugikLazProvider",
        side_effect=lambda **_kw: LazCliProvider(),
    ):
        run = run_both(
            [
                "elevation",
                "download",
                "--product",
                "laz",
                "--bbox",
                "18.60,49.73,18.66,49.76",
            ]
            + ["--bbox-crs", "EPSG:4326", "--country", "pl"]
            + ["--vertical-crs", "EVRF2007", "--min-density", "4", "-q"],
            lambda out: download_data(
                product="laz",
                output_dir=out,
                bbox=bbox,
                country="pl",
                vertical_crs="EVRF2007",
                min_density=4,
            ),
            tmp_path,
        )
    _same(run, run.api_result, statuses=["new"])


@pytest.mark.usefixtures("frozen_clock")
def test_upgrade_with_stale_plan(tmp_path):
    """The source changed after the check: same stale positions, code 1."""
    fake = FakeCampaignProvider({"newest": [REC["83233"]], "all": C14["all"]})
    plan_file = tmp_path / "plan.json"
    sheet = ["--sheet", G, *PL_SHEET_ARGS]
    with _pl_store(fake):
        checked = run_both(
            ["elevation", "download", "--product", "nmt", *sheet, "--check-updates"]
            + ["--plan", str(plan_file)],
            lambda out: check_data(
                product="nmt", output_dir=out, sheet=G, **PL_SHEET_KW
            ),
            tmp_path,
        )
        fake.records = C14
        upgraded = run_both(
            ["elevation", "download", "--product", "nmt", *sheet, "--upgrade"]
            + ["--plan", str(plan_file), "-q"],
            lambda out: download_data(
                product="nmt",
                output_dir=out,
                sheet=G,
                update="upgrade",
                plan=checked.api_result,
                **PL_SHEET_KW,
            ),
            tmp_path,
        )
    report = upgraded.api_result
    _same(upgraded, report)
    assert report.stale and not report.ok and upgraded.cli_code == 1
