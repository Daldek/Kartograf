"""Library argument types (rules for code in CLAUDE.md): a value of a wrong type is a
``ValidationError`` before any network or file access, never converted and
never a late ``TypeError``/``ValueError`` from a provider (backlog "Do
0.8.0", 2026-10-15). The CLI parses its flags itself, so it never reaches
these errors."""

from unittest.mock import Mock

import pytest

from kartograf.core.bbox import BBox
from kartograf.download.availability import check_availability
from kartograf.download.collections import check_collection, download_collection
from kartograf.download.cz_laz import download_cz_laz
from kartograf.download.data import check_data, download_data
from kartograf.download.laz import check_laz_area, download_laz_area
from kartograf.download.manager import DownloadManager
from kartograf.exceptions import ValidationError
from kartograf.landcover.manager import LandCoverManager

SHEET = "N-34-130-D-d-2-4"
AREA = BBox(450000, 550000, 451000, 551000, "EPSG:2180")
SHEET_REQUEST = {
    "product": "nmt",
    "sheet": SHEET,
    "resolution": "1m",
    "vertical_crs": "EVRF2007",
}


@pytest.mark.parametrize(
    ("argument", "flag"),
    [
        ({"year": "2018"}, "--year"),
        ({"min_year": 2018.0}, "--min-year"),
        ({"all_campaigns": "yes"}, "--all-campaigns"),
        ({"full_sheet": 1}, "--full-sheet"),
        ({"cutout": "false"}, "--cutout"),
    ],
)
@pytest.mark.parametrize("call", [download_data, check_data])
def test_download_data_rejects_wrong_types(tmp_path, call, argument, flag):
    with pytest.raises(ValidationError, match=flag):
        call(**SHEET_REQUEST, root=tmp_path, **argument)
    assert not any(tmp_path.iterdir())


def test_download_data_rejects_text_density_and_workers(tmp_path):
    laz = {"product": "laz", "sheet": SHEET, "vertical_crs": "EVRF2007"}
    with pytest.raises(ValidationError, match="--min-density .*'10'"):
        download_data(**laz, root=tmp_path, min_density="10")
    with pytest.raises(ValidationError, match="--workers .*'4'"):
        download_data(**SHEET_REQUEST, root=tmp_path, workers="4")


def test_layers_text_is_not_read_character_by_character(tmp_path):
    manager = LandCoverManager("bdot10k", cache=False, root=tmp_path)
    with pytest.raises(ValidationError, match="--layers: podaj liste kodow"):
        manager.download(teryt="1465", layers="SWRS,PTWP")
    with pytest.raises(ValidationError, match="--layers: podaj liste kodow"):
        manager.check(teryt="1465", layers="SWRS")


@pytest.mark.parametrize(
    ("source", "options", "match"),
    [
        ("corine", {"year": "2018"}, "--year .*'2018'"),
        ("bdot10k", {"keep_raw": "true"}, "--keep-raw"),
        ("bdot10k", {"layers": ["SWRS", 7]}, "kody musza byc napisami"),
    ],
)
def test_landcover_rejects_wrong_option_types(tmp_path, source, options, match):
    manager = LandCoverManager(source, cache=False, root=tmp_path)
    selection = {"teryt": "1465"} if source == "bdot10k" else {"bbox": AREA}
    with pytest.raises(ValidationError, match=match):
        manager.download(**selection, **options)


def test_landcover_rejects_text_workers(tmp_path):
    manager = LandCoverManager("bdot10k", cache=False, root=tmp_path)
    with pytest.raises(ValidationError, match="--workers"):
        manager.download(teryt="1465", workers="2")


@pytest.mark.parametrize(
    ("argument", "name"),
    [
        ({"workers": "4"}, "workers"),
        ({"all_campaigns": "no"}, "all_campaigns"),
        ({"full_sheet": None}, "full_sheet"),
    ],
)
def test_download_manager_rejects_wrong_types(tmp_path, argument, name):
    with pytest.raises(ValidationError, match=name):
        DownloadManager(Mock(), root=tmp_path, **argument)


@pytest.mark.parametrize(
    ("argument", "name"),
    [
        ({"year": "2024"}, "year"),
        ({"min_density": "12"}, "min_density"),
        ({"all_campaigns": "no"}, "all_campaigns"),
    ],
)
@pytest.mark.parametrize("call", [download_laz_area, check_laz_area])
def test_laz_area_rejects_wrong_types_before_wfs(tmp_path, call, argument, name):
    with pytest.raises(ValidationError, match=name):
        call(bbox=AREA, root=tmp_path, vertical_crs="EVRF2007", **argument)


def test_laz_area_rejects_text_workers(tmp_path):
    with pytest.raises(ValidationError, match="workers"):
        download_laz_area(
            bbox=AREA, root=tmp_path, vertical_crs="EVRF2007", workers="2"
        )


def test_cz_laz_rejects_text_workers(tmp_path):
    with pytest.raises(ValidationError, match="workers .*'2'"):
        download_cz_laz(
            model="dmr5g",
            vertical_crs="EVRF2007",
            root=tmp_path,
            sheet="760_5518",
            workers="2",
        )
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("argument", "flag"),
    [
        ({"year": "2021"}, "--year"),
        ({"lod": 1.0, "year": 2021}, "--lod"),
        ({"whole_country": "no"}, "--whole-country"),
    ],
)
@pytest.mark.parametrize("call", [download_collection, check_collection])
def test_collection_rejects_wrong_types(tmp_path, call, argument, flag):
    request = {"product": "buildings", "teryt": "1465", "lod": 1} | argument
    with pytest.raises(ValidationError, match=flag):
        call(root=tmp_path, cache=False, **request)
    assert not any(tmp_path.iterdir())


def test_collection_rejects_text_workers(tmp_path):
    with pytest.raises(ValidationError, match="--workers .*'2'"):
        download_collection(
            product="buildings",
            root=tmp_path,
            teryt="1465",
            lod=1,
            year=2021,
            workers="2",
            cache=False,
        )
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("argument", "flag"),
    [({"year": "2018"}, "--year"), ({"force": "no"}, "--force")],
)
def test_availability_rejects_wrong_types(argument, flag):
    with pytest.raises(ValidationError, match=flag):
        check_availability(product="nmt", sheet=SHEET, cache=False, **argument)


def test_bdot10k_archive_rejects_float_year(tmp_path):
    manager = LandCoverManager("bdot10k", cache=False, root=tmp_path)
    with pytest.raises(ValidationError, match="--year .*2020.0"):
        manager.download(teryt="1465", year=2020.0, format="SHP")
