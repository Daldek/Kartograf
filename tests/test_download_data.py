"""``download_data`` / ``check_data``: ``kartograf elevation download`` and
``kartograf imagery download`` as a library function (spec 4.1): validation,
countries, report and notices."""

from unittest.mock import patch

import pytest

from kartograf.core.bbox import BBox
from kartograf.download.cutout import (
    PlCutoutResult,
    check_pl_cutout,
    download_pl_cutout,
)
from kartograf.download.cz_cutout import check_cz_cutout, download_cz_cutout
from kartograf.download.data import UnitFile, check_data, download_data
from kartograf.download.laz import (
    LazDownloadResult,
    check_laz_area,
    download_laz_area,
)
from kartograf.download.manager import DownloadProgress
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.notices import (
    AUTO_CLIPPED,
    AUTO_PARTIAL_SUCCESS,
    CHECK_FAILED,
    NO_COVERAGE_SOME,
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
        (
            {"sheet_system": "1993"},
            "--sheet-system '1993': nieznana wartosc - dostepne: 1992",
        ),
        (
            {"cutout": True, "horizontal_crs": "EPSG:3857"},
            "--horizontal-crs 'EPSG:3857': nieznana wartosc - dostepne: EPSG:2180",
        ),
        (
            {
                "country": "cz",
                "resolution": "2m",
                "vertical_crs": "Bpv",
                "sheet_system": None,
                "cutout": True,
                "horizontal_crs": "EPSG:3857",
            },
            "--horizontal-crs 'EPSG:3857': nieznana wartosc - dostepne: EPSG:2180",
        ),
        (
            {"sheet": "N-34-130-D-d-2-4", "bbox": None, "cutout": True},
            "--cutout dziala tylko z --bbox/--geometry",
        ),
        (
            {"sheet_system": None, "cutout": True},
            "--horizontal-crs wymagane z --cutout (uklad wycinka): EPSG:2180",
        ),
        (
            {"horizontal_crs": "EPSG:2180"},
            "--horizontal-crs dziala tylko z --cutout",
        ),
        (
            {"product": "orto", "vertical_crs": None, "cutout": True},
            "--cutout dziala tylko z --product nmt albo nmpt",
        ),
        (
            {
                "country": "cz",
                "resolution": "2m",
                "vertical_crs": "Bpv",
                "sheet_system": None,
                "bbox": BBox(-740000, -1050000, -739000, -1049000, "EPSG:5514"),
            },
            "obszar CZ (CUZK) jest pobierany tylko jako jeden wycinek - dodaj "
            "--cutout --horizontal-crs",
        ),
        (
            {
                "country": "auto",
                "resolution": {"pl": "1m", "cz": "2m"},
                "vertical_crs": {"pl": "EVRF2007", "cz": "Bpv"},
                "bbox": BBox(15.85, 50.45, 15.95, 50.55, "EPSG:4326"),
            },
            "obszar siega CZ, a CUZK daje dla obszaru tylko jeden wycinek",
        ),
        (
            {"bbox": BBox(10, 10, 5, 5, "EPSG:2180")},
            "Nieprawidlowy bbox: bbox odwrocony",
        ),
        (
            {"bbox": BBox(1, 2, 3, 4, "bogus")},
            "Nieprawidlowy bbox: nieobslugiwany uklad 'bogus'",
        ),
        (
            {"bbox": BBox(1, 2, 3, 4, "EPSG:9999")},
            "Nieprawidlowy bbox: nieobslugiwany uklad 'EPSG:9999'",
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
        "sheet_system": "1992",
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
            cutout=True,
            horizontal_crs="EPSG:2180",
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
            cutout=True,
            horizontal_crs="EPSG:3045",
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
            cutout=True,
            horizontal_crs="EPSG:2180",
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
            cutout=True,
            horizontal_crs="EPSG:5514",
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
            cutout=True,
            horizontal_crs="EPSG:3045",
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


@pytest.mark.parametrize("operation", [download_data, check_data])
@pytest.mark.parametrize("flag", ["resolution", "vertical_crs"])
@pytest.mark.parametrize("invalid", [7, ["pl=1m"]])
def test_per_country_wrong_type_fails_before_source(tmp_path, operation, flag, invalid):
    selection = {
        "product": "nmt",
        "output_dir": tmp_path,
        "bbox": BBox(530000, 380000, 530100, 380100, "EPSG:2180"),
        "country": "pl",
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "sheet_system": "1992",
        "cache": False,
        flag: invalid,
    }
    with (
        patch("kartograf.download.data._create_provider_and_storage") as provider,
        pytest.raises(
            ValidationError,
            match=f"--{flag.replace('_', '-')}: nieprawidlowa wartosc",
        ),
    ):
        operation(**selection)
    provider.assert_not_called()


_BBOX_TRACKS = (
    (
        download_data,
        {
            "product": "nmt",
            "country": "pl",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
            "sheet_system": "1992",
        },
    ),
    (
        check_data,
        {
            "product": "nmt",
            "country": "pl",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
            "sheet_system": "1992",
        },
    ),
    (
        check_pl_cutout,
        {"horizontal_crs": "EPSG:2180", "vertical_crs": "EVRF2007", "product": "nmt"},
    ),
    (
        download_pl_cutout,
        {"horizontal_crs": "EPSG:2180", "vertical_crs": "EVRF2007", "product": "nmt"},
    ),
    (
        check_cz_cutout,
        {"horizontal_crs": "EPSG:5514", "vertical_crs": "Bpv", "resolution": "2m"},
    ),
    (
        download_cz_cutout,
        {"horizontal_crs": "EPSG:5514", "vertical_crs": "Bpv", "resolution": "2m"},
    ),
    (check_laz_area, {"vertical_crs": "EVRF2007"}),
    (download_laz_area, {"vertical_crs": "EVRF2007"}),
)


@pytest.mark.parametrize("operation,choices", _BBOX_TRACKS)
@pytest.mark.parametrize(
    ("bbox", "reason"),
    [
        (BBox(1, 2, 3, 4, "bogus"), "nieobslugiwany uklad 'bogus'"),
        (BBox(1, 2, 3, 4, "EPSG:9999"), "nieobslugiwany uklad 'EPSG:9999'"),
        (BBox(1, 2, 3, 4, "epsg:2180"), "nieobslugiwany uklad 'epsg:2180'"),
        (BBox(10, 10, 5, 5, "EPSG:2180"), "bbox odwrocony"),
    ],
)
def test_all_public_bbox_tracks_reject_invalid_input_before_network(
    tmp_path, operation, choices, bbox, reason
):
    with (
        patch("socket.socket.connect", side_effect=AssertionError("network")),
        pytest.raises(ValidationError) as exc,
    ):
        operation(bbox=bbox, output_dir=tmp_path, cache=False, **choices)
    assert str(exc.value).startswith(f"Nieprawidlowy bbox: {reason}")


@pytest.mark.parametrize("operation", [check_cz_cutout, download_cz_cutout])
def test_cz_cutout_unknown_horizontal_crs_is_validation_error(tmp_path, operation):
    with (
        patch(CZ_FACTORY) as factory,
        pytest.raises(
            ValidationError, match="Nieobslugiwany uklad docelowy wycinka CZ"
        ),
    ):
        operation(
            BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514"),
            output_dir=tmp_path,
            horizontal_crs="EPSG:9999",
            vertical_crs="Bpv",
            resolution="2m",
            cache=False,
        )
    factory.assert_not_called()


def test_pl_sheet_list_failure_contains_per_sheet_cause(tmp_path):
    from kartograf.download.storage import FileStorage

    failed = "N-34-139-C-a-3-2"
    missing = "N-34-139-C-a-3-3"
    fake = FakeCampaignProvider(C14, errors={failed: DownloadError("zrodlo HTTP 503")})
    storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
    with (
        patch(
            "kartograf.download.data._create_provider_and_storage",
            return_value=(fake, storage),
        ),
        patch(
            "kartograf.download.data.find_sheets_for_bbox",
            return_value=[G, failed, missing],
        ),
    ):
        report = download_data(
            product="nmt",
            output_dir=tmp_path,
            bbox=BBox(530000, 380000, 530100, 380100, "EPSG:2180"),
            country="pl",
            resolution="1m",
            vertical_crs="EVRF2007",
            sheet_system="1992",
            cache=False,
            workers=2,
        )
    assert not report.ok
    assert len(report.files) == 1
    assert len(report.failed) == 1
    assert report.failed[0].kind == "download"
    assert f"{failed}: zrodlo HTTP 503" in report.failed[0].error
    assert "GUGiK nie ma danych" in next(
        n.text for n in report.notices if n.code == NO_COVERAGE_SOME
    )


def test_check_data_auto_partial_names_failed_country_without_download_claim(tmp_path):
    notices: list[Notice] = []
    with patch(CZ_FACTORY, side_effect=DownloadError("CUZK 503")):
        plan = check_data(
            product="nmt",
            output_dir=tmp_path,
            bbox=BORDER,
            cutout=True,
            horizontal_crs="EPSG:3045",
            cache=False,
            on_notice=notices.append,
            **AUTO,
        )
    assert [item.track for item in plan.items] == ["pl_cutout"]
    partial = next(n for n in notices if n.code == AUTO_PARTIAL_SUCCESS)
    assert "sprawdzono PL" in partial.text and "pobrano" not in partial.text
    failed = [n for n in notices if n.code == CHECK_FAILED]
    assert len(failed) == 1 and failed[0].text == "CZ: CUZK 503"
