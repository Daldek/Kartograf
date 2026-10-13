"""``download_data`` / ``check_data``: the ``kartograf download`` command as a
library function (spec 4.1): validation, countries, report and notices."""

from unittest.mock import patch

import pytest

from kartograf.core.bbox import BBox
from kartograf.download.cutout import PlCutoutResult
from kartograf.download.data import UnitFile, check_data, download_data
from kartograf.download.laz import LazDownloadResult
from kartograf.download.manager import DownloadProgress
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import (
    AUTO_CLIPPED,
    AUTO_PARTIAL_SUCCESS,
    Notice,
)
from tests.test_cli import _cz_provider_mock
from tests.test_manager_campaigns import C14, REC, FakeCampaignProvider

G = "N-34-139-C-a-3-1"
# Cieszyn: a bbox crossing the PL-CZ border
BORDER = BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326")
AUTO = {
    "country": "auto",
    "resolution": {"pl": "1m", "cz": "2m"},
    "vertical_crs": {"pl": "EVRF2007", "cz": "Bpv"},
}
CZ_FACTORY = "kartograf.providers.cuzk.create_dmr_provider"


def _pl_sheets(fake):
    return patch(
        "kartograf.download.data._create_provider_and_storage",
        return_value=(fake, None),
    )


def test_pl_sheet_report_files_and_ok(tmp_path):
    with _pl_sheets(FakeCampaignProvider(C14)):
        report = download_data(
            product="nmt",
            output_dir=tmp_path,
            sheet=G,
            resolution="1m",
            vertical_crs="EVRF2007",
            cache=False,
        )
    assert report.ok and report.failed == ()
    (unit_file,) = report.files
    assert isinstance(unit_file, UnitFile)
    assert (unit_file.unit, unit_file.country) == (G, "PL")
    assert unit_file.file.status == "new"
    assert unit_file.file.label.startswith("2025-10-21_84183")


@pytest.mark.parametrize(
    ("kwargs", "text"),
    [
        ({"product": None}, "--product wymagane"),
        ({"vertical_crs": None}, "--vertical-crs wymagane dla --product nmt"),
        ({"year": 2020, "min_year": 2019}, "--year wyklucza sie"),
        ({"min_density": 4}, "--min-density dziala tylko z --product laz"),
    ],
)
def test_validation_errors_before_any_download(tmp_path, kwargs, text):
    fake = FakeCampaignProvider(C14)
    arguments = {
        "product": "nmt",
        "output_dir": tmp_path,
        "sheet": G,
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "cache": False,
        **kwargs,
    }
    with _pl_sheets(fake), pytest.raises(ValidationError, match=text):
        download_data(**arguments)
    assert fake.downloads == []


def test_area_outside_countries_is_validation_error(tmp_path):
    with pytest.raises(ValidationError, match="nie przecina zasiegu"):
        download_data(
            product="nmt",
            output_dir=tmp_path,
            bbox=BBox(2.0, 40.0, 2.1, 40.1, "EPSG:4326"),
            cache=False,
            **AUTO,
        )


@pytest.mark.parametrize("operation", [download_data, check_data])
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"product": "foo"}, "--product 'foo': nieznana wartosc - dostepne: nmt"),
        ({"country": "xx"}, "--country 'xx': nieznana wartosc - dostepne: pl"),
        ({"country": "PL"}, "--country 'PL': nieznana wartosc - dostepne: pl"),
        ({"system": "1993"}, "--system '1993': nieznana wartosc - dostepne: 1992"),
        (
            {"target_crs": "EPSG:3857"},
            "--target-crs 'EPSG:3857': nieznana wartosc - dostepne: EPSG:2180",
        ),
        (
            {
                "country": "cz",
                "resolution": "2m",
                "vertical_crs": "Bpv",
                "system": None,
                "target_crs": "EPSG:3857",
            },
            "--target-crs 'EPSG:3857': nieznana wartosc - dostepne: EPSG:2180",
        ),
        (
            {"bbox": BBox(10, 10, 5, 5, "EPSG:2180")},
            "Nieprawidlowy bbox: bbox odwrocony",
        ),
        (
            {"bbox": BBox(float("nan"), 0, 5, 5, "EPSG:2180")},
            "Nieprawidlowy bbox: wspolrzedne bboxa musza byc skonczone",
        ),
        (
            {"bbox": BBox(750000, 5500000, 750100, 5500100, "EPSG:2177")},
            "Nieobslugiwany CRS",
        ),
    ],
)
def test_invalid_choices_and_bboxes_fail_before_source(
    tmp_path, operation, overrides, message
):
    selection = {
        "product": "nmt",
        "output_dir": tmp_path,
        "bbox": BBox(530000, 380000, 530100, 380100, "EPSG:2180"),
        "country": "pl",
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "system": "1992",
        "cache": False,
        **overrides,
    }
    with (
        patch("kartograf.download.data._create_provider_and_storage") as pl_provider,
        patch(CZ_FACTORY) as cz_provider,
        pytest.raises(ValidationError) as exc,
    ):
        operation(**selection)
    assert type(exc.value) is ValidationError
    assert str(exc.value).startswith(message)
    pl_provider.assert_not_called()
    cz_provider.assert_not_called()


@pytest.mark.parametrize("operation", [download_data, check_data])
def test_pl_cutout_input_error_propagates_instead_of_country_failure(
    tmp_path, operation
):
    name = "download_pl_cutout" if operation is download_data else "check_pl_cutout"
    with (
        patch(
            f"kartograf.download.cutout.{name}",
            side_effect=ValidationError("zly bbox wycinka"),
        ),
        pytest.raises(ValidationError, match="^zly bbox wycinka$"),
    ):
        operation(
            product="nmt",
            output_dir=tmp_path,
            bbox=BBox(530000, 380000, 530100, 380100, "EPSG:2180"),
            country="pl",
            resolution="1m",
            vertical_crs="EVRF2007",
            target_crs="EPSG:2180",
            cache=False,
        )


def test_laz_start_progress_uses_resolved_pl_vertical_crs(tmp_path):
    events: list[DownloadProgress] = []
    with patch(
        "kartograf.download.laz.download_laz_area",
        return_value=LazDownloadResult(tiles=()),
    ):
        report = download_data(
            product="laz",
            output_dir=tmp_path,
            sheet=G,
            vertical_crs={"pl": "KRON86", "cz": "Bpv"},
            on_progress=events.append,
            cache=False,
        )
    assert report.ok
    assert events == [DownloadProgress(0, 1, "kafle LAZ", "start", "WFS GUGiK, KRON86")]


def _border_tracks(order: list[str], *, cz_error: Exception | None = None):
    """PL cutout and CZ cutout of the border bbox recorded in call order."""

    def pl(*_args, **_kwargs):
        order.append("pl-download")
        return PlCutoutResult(None)

    cz = _cz_provider_mock()

    def cz_download(*_args, **_kwargs):
        order.append("cz-download")
        if cz_error is not None:
            raise cz_error
        raise AssertionError("not reached in these tests")

    cz.download_bbox.side_effect = cz_download
    return (
        patch("kartograf.download.cutout.download_pl_cutout", side_effect=pl),
        patch(CZ_FACTORY, return_value=cz),
    )


def test_partial_success_auto_ok_true_with_notice(tmp_path):
    order: list[str] = []
    seen: list[Notice] = []
    pl, cz = _border_tracks(order, cz_error=DownloadError("CUZK 503"))
    with pl, cz:
        report = download_data(
            product="nmt",
            output_dir=tmp_path,
            bbox=BORDER,
            target_crs="EPSG:3045",
            on_notice=seen.append,
            cache=False,
            **AUTO,
        )
    assert report.ok
    assert [(f.country, f.kind) for f in report.failed] == [("CZ", "download")]
    assert "CUZK 503" in report.failed[0].error
    partial = [n for n in report.notices if n.code == AUTO_PARTIAL_SUCCESS]
    assert len(partial) == 1 and "pobrano PL" in partial[0].text
    assert seen == list(report.notices)


def test_notices_before_first_download(tmp_path):
    """Review focus 3: clipping notices reach ``on_notice`` before any download.

    Rozewie: the PL part is clipped at the northern PL envelope edge."""
    order: list[str] = []
    pl, cz = _border_tracks(order)
    with pl, cz:
        report = download_data(
            product="nmt",
            output_dir=tmp_path,
            bbox=BBox(455000, 773000, 459000, 784000, "EPSG:2180"),
            target_crs="EPSG:2180",
            on_notice=lambda n: order.append(n.code),
            cache=False,
            **AUTO,
        )
    assert order.index(AUTO_CLIPPED) < order.index("pl-download")
    assert "cz-download" not in order and report.ok


def test_explicit_country_failure_ok_false(tmp_path):
    cz = _cz_provider_mock()
    cz.download_bbox.side_effect = DownloadError("CUZK 503")
    with patch(CZ_FACTORY, return_value=cz):
        report = download_data(
            product="nmt",
            output_dir=tmp_path,
            bbox=BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514"),
            country="cz",
            resolution="2m",
            vertical_crs="Bpv",
            cache=False,
        )
    assert not report.ok
    assert [(f.unit, f.kind, f.error) for f in report.failed] == [
        ("CZ", "download", "CUZK 503")
    ]
    assert not any(n.code == AUTO_PARTIAL_SUCCESS for n in report.notices)


def test_check_data_auto_one_merged_plan(tmp_path):
    """PL+CZ under ``auto``: ONE plan with the positions of both countries."""
    with patch(CZ_FACTORY, return_value=_cz_provider_mock()):
        plan = check_data(
            product="nmt",
            output_dir=tmp_path,
            bbox=BORDER,
            target_crs="EPSG:3045",
            cache=False,
            **AUTO,
        )
    assert sorted(i.track for i in plan.items) == ["cz_cutout", "pl_cutout"]
    assert {i.status for i in plan.items} == {"missing"}


def test_check_then_upgrade_with_plan_downloads_planned(tmp_path):
    fake = FakeCampaignProvider(C14)
    selection = {
        "product": "nmt",
        "output_dir": tmp_path,
        "sheet": G,
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "cache": False,
    }
    with _pl_sheets(fake):
        plan = check_data(**selection)
        assert [i.status for i in plan.items] == ["missing"]
        report = download_data(**selection, update="upgrade", plan=plan)
    assert report.ok and [f.unit for f in report.files] == [G]
    assert fake.downloads == [REC["84183"].url]
