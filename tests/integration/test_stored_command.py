"""The command of a stored file (``command_for_file``, KB-6, ADR-057)."""

import json

import pytest

from kartograf import (
    CommandNotRebuildableError,
    InvalidSidecarError,
    ValidationError,
    command_for_file,
    error_report,
    format_command,
    parse_command,
    read_sidecar,
    validate_command,
)
from kartograf.marker import prepare_store
from kartograf.testing import PL_SHEET, build_fixture_store, make_sidecar

_PL_BOX = {"bbox": [500000.0, 600000.0, 501000.0, 601000.0], "bbox_crs": "EPSG:2180"}
_CZ_BOX = {
    "bbox": [-600000.0, -1100000.0, -599000.0, -1099000.0],
    "bbox_crs": "EPSG:5514",
}


def _sidecar(tmp_path, dataset, request, *, extra=None, vertical=None, product=None):
    """Read, as ``read_sidecar`` does, a sidecar the real emitter wrote."""
    meta = make_sidecar(dataset, request=request, extra=extra, vertical_crs=vertical)
    if product is not None:
        meta["product"] = product
    path = tmp_path / f"{dataset}.meta.json"
    path.write_text(json.dumps(meta), encoding="utf-8")
    return read_sidecar(path)


def _assert_selects_again(call, root):
    """The call is valid for the store and its command line reads back into it."""
    validate_command(call.command, call.options, root=root)
    assert parse_command(format_command(call.command, call.options)) == call
    assert call.run == {}


def test_command_for_file_pl_sheet_versions_pin_their_campaign_year(tmp_path):
    store = build_fixture_store(tmp_path / "data")
    pl = store.files[0]

    calls = [command_for_file(read_sidecar(v.path)) for v in pl.versions]

    for call in calls:
        _assert_selects_again(call, store.root)
        assert call.options["sheet"] == PL_SHEET
        assert call.options["vertical_crs"] == "EVRF2007"
        assert call.options["resolution"] == "1m"
        # two flights of 2025: the year alone would select only the newer one
        assert call.options["all_campaigns"] is True
    assert [call.options["year"] for call in calls] == [2022, 2025, 2025]


def test_command_for_file_cz_sheet_pins_the_height_system(tmp_path):
    store = build_fixture_store(tmp_path / "data")

    call = command_for_file(read_sidecar(store.files[1].versions[0].path))

    _assert_selects_again(call, store.root)
    assert call.options == {
        "product": "nmt",
        "sheet": "CTES96",
        "resolution": "5m",
        "vertical_crs": "Bpv",
    }


@pytest.mark.parametrize(
    ("dataset", "request_", "extra", "vertical", "expected"),
    [
        pytest.param(
            "pl.gugik.nmt_tbd_25m",
            {"sheet": PL_SHEET, "campaigns": "newest"},
            {"source": {"acquisition_year": "2003"}, "campaign": {"id": "1"}},
            "KRON86",
            {"format": "TBD", "vertical_crs": "KRON86", "year": 2003},
            id="pl-archive-sheet",
        ),
        pytest.param(
            "pl.gugik.oblique_orto",
            {"sheet": "7.125.11.08", "campaigns": "newest"},
            {"source": {"acquisition_year": "2023", "direction": "n"}},
            None,
            {"direction": ["n"], "year": 2023, "all_campaigns": True},
            id="pl-oblique-sheet",
        ),
        pytest.param(
            "cz.cuzk.zabaged_contours_shp",
            {"sheet": "CTES96", "format": "SHP"},
            None,
            "Bpv",
            {"product": "contours", "format": "SHP", "vertical_crs": "Bpv"},
            id="cz-contours-sheet",
        ),
        pytest.param(
            "cz.cuzk.orto",
            {"sheet": "CTES96"},
            None,
            None,
            {"product": "orto", "sheet": "CTES96"},
            id="cz-orthophoto-sheet",
        ),
        pytest.param(
            "pl.gugik.nmt_1m",
            _PL_BOX,
            None,
            "EVRF2007",
            {"country": "pl", "cutout": True, "horizontal_crs": "EPSG:2180"},
            id="pl-wcs-cutout",
        ),
        pytest.param(
            "cz.cuzk.dmr5g",
            _CZ_BOX,
            None,
            "EVRF2007",
            {
                "country": "cz",
                "horizontal_crs": "EPSG:5514",
                "vertical_crs": "EVRF2007",
            },
            id="cz-cutout",
        ),
        pytest.param(
            "pl.gugik.orto",
            {**_PL_BOX, "coverage": "high", "resolution": "0.1m"},
            None,
            None,
            {"coverage": "high", "resolution": "0.1m", "cutout": True},
            id="pl-orthophoto-cutout",
        ),
        pytest.param(
            "pl.gugik.laz",
            {**_PL_BOX, "min_density": 4, "min_year": 2019},
            {"year": 2021, "tile_sheet": "N-34-130-D-d-2-4-1"},
            "EVRF2007",
            {"bbox": _PL_BOX["bbox"], "year": 2021, "all_campaigns": True},
            id="pl-laz-tile",
        ),
        pytest.param(
            "cz.cuzk.dmr5g_laz",
            {"sheet": "302_5550"},
            None,
            "EVRF2007",
            {"model": "dmr5g", "vertical_crs": "EVRF2007"},
            id="cz-laz-sheet",
        ),
        pytest.param(
            "pl.gugik.bdot10k",
            {"teryt": "1261", "format": "SHP", "year": 2020},
            None,
            None,
            {"product": "bdot10k", "teryt": "1261", "year": 2020},
            id="landcover-teryt",
        ),
        pytest.param(
            "pl.gugik.buildings",
            {"teryt": "1261", "lod": 1, "year": 2022},
            None,
            None,
            {"country": "pl", "teryt": "1261", "lod": 1, "year": 2022},
            id="collection-teryt",
        ),
        pytest.param(
            "cz.cuzk.cadastral_map",
            {"ku": "600016", "format": "SHP"},
            None,
            None,
            {"country": "cz", "ku": "600016", "format": "SHP"},
            id="cz-collection-ku",
        ),
        pytest.param(
            "pl.gugik.prg",
            {"whole_country": True},
            None,
            None,
            {"product": "admin", "whole_country": True},
            id="collection-whole-country",
        ),
    ],
)
def test_command_for_file_rebuilds_a_call_that_selects_the_file(
    tmp_path, dataset, request_, extra, vertical, expected
):
    root = tmp_path / "data"
    root.mkdir()
    prepare_store(root)
    sidecar = _sidecar(tmp_path, dataset, request_, extra=extra, vertical=vertical)

    call = command_for_file(sidecar)

    _assert_selects_again(call, root)
    assert expected.items() <= call.options.items()


def test_command_for_file_bdot10k_gpkg_keeps_the_raw_package(tmp_path):
    """The raw ZIP and the GPKG of a powiat share one request: the call selects both."""
    sidecar = _sidecar(
        tmp_path, "pl.gugik.bdot10k", {"teryt": "1261", "format": "GPKG"}
    )

    call = command_for_file(sidecar)

    assert call.options["keep_raw"] is True


@pytest.mark.parametrize(
    ("dataset", "request_", "extra", "vertical", "product", "family", "field"),
    [
        pytest.param(
            "pl.gugik.bdot10k",
            _PL_BOX,
            None,
            None,
            None,
            "area",
            None,
            id="landcover-box",
        ),
        pytest.param(
            "eu.clms.corine",
            {**_PL_BOX, "year": 2018},
            None,
            None,
            None,
            "area",
            None,
            id="corine-box",
        ),
        pytest.param(
            "cz.cuzk.ruian",
            {**_CZ_BOX, "level": "obec"},
            None,
            None,
            None,
            "area",
            None,
            id="cz-collection-box",
        ),
        pytest.param(
            "pl.gugik.mesh",
            {"tile": "2000/7/78944_6777_74230_55482"},
            None,
            None,
            None,
            "area",
            None,
            id="collection-area-tile",
        ),
        pytest.param(
            "pl.gugik.nmt_100m",
            {"teryt": "12"},
            None,
            None,
            None,
            "area",
            None,
            id="nmt-100m-voivodeship",
        ),
        pytest.param(
            "global.isric.soilgrids",
            {"sheet": "N-34-130-D"},
            None,
            None,
            "hsg",
            "hsg",
            None,
            id="soil-hsg",
        ),
        pytest.param(
            "pl.gugik.nmt_1m",
            {
                "bbox": [-500000.0, -1100000.0, -499000.0, -1099000.0],
                "bbox_crs": "EPSG:5514",
            },
            None,
            "EVRF2007",
            None,
            "cutout",
            None,
            id="pl-cutout-reprojected",
        ),
        pytest.param(
            "pl.gugik.nmt_1m",
            {"sheet": PL_SHEET, "campaigns": "newest"},
            None,
            "EVRF2007",
            None,
            "sheet",
            "extra.source.acquisition_year",
            id="campaign-without-year",
        ),
        pytest.param(
            "pl.gugik.laz",
            _PL_BOX,
            None,
            "EVRF2007",
            None,
            "laz",
            "extra.year",
            id="laz-without-tile-year",
        ),
    ],
)
def test_command_for_file_refuses_a_file_no_command_selects_again(
    tmp_path, dataset, request_, extra, vertical, product, family, field
):
    sidecar = _sidecar(
        tmp_path, dataset, request_, extra=extra, vertical=vertical, product=product
    )

    with pytest.raises(CommandNotRebuildableError) as caught:
        command_for_file(sidecar)

    report = error_report(caught.value)
    assert report.code == "unsupported"
    assert report.exit_code == 15
    assert report.details["reason"] == "command_not_rebuildable"
    assert report.details["family"] == family
    assert report.details.get("field") == field
    assert report.hint


def test_command_for_file_refuses_a_sidecar_without_request(tmp_path):
    meta = make_sidecar()
    del meta["request"]
    path = tmp_path / "x.asc.meta.json"
    path.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(CommandNotRebuildableError) as caught:
        command_for_file(read_sidecar(path))

    assert caught.value.field == "request"


@pytest.mark.parametrize(
    ("request_", "field"),
    [
        ({"bbox": [1.0, 2.0, 3.0], "bbox_crs": "EPSG:5514"}, "request.bbox"),
        ({"sheet": 7}, "request.sheet"),
    ],
)
def test_command_for_file_malformed_field_is_a_data_error(tmp_path, request_, field):
    sidecar = _sidecar(tmp_path, "cz.cuzk.dmr5g", request_, vertical="Bpv")

    with pytest.raises(InvalidSidecarError) as caught:
        command_for_file(sidecar)

    report = error_report(caught.value)
    assert report.code == "data_error"
    assert report.details == {"reason": "invalid_sidecar", "field": field}


def test_command_for_file_takes_only_a_read_sidecar():
    with pytest.raises(ValidationError) as caught:
        command_for_file(make_sidecar())  # the raw dict, not read_sidecar's view

    assert caught.value.option == "sidecar"
