"""Land cover and HSG segments and slots (versioned store spec 3.4)."""

from pathlib import Path

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.download.storage import bbox_cutout_path
from kartograf.exceptions import ValidationError
from kartograf.landcover.store import (
    hsg_segment,
    landcover_segment,
    selection_slot,
    selection_unit,
)

BBOX = BBox(450000.5, 550000, 460000, 560000.25, "EPSG:2180")


@pytest.mark.parametrize(
    ("key", "tokens", "segment"),
    [
        ("pl.gugik.bdot10k", ["gpkg"], "landcover/pl_bdot10k_gpkg"),
        (
            "pl.gugik.bdot10k",
            ["gpkg", "PTWP-SWRS"],
            "landcover/pl_bdot10k_gpkg_ptwp-swrs",
        ),
        ("pl.gugik.bdot10k", ["gpkg", "zip"], "landcover/pl_bdot10k_gpkg_zip"),
        ("pl.gugik.bdot10k", ["shp"], "landcover/pl_bdot10k_shp"),
        ("eu.clms.corine", ["2018"], "landcover/eu_corine_2018"),
        ("eu.clms.corine", ["1990", "preview"], "landcover/eu_corine_1990_preview"),
        (
            "global.isric.soilgrids",
            ["clay", "0-5cm", "Q0.05"],
            "soil/global_soilgrids_clay_0-5cm_q0.05",
        ),
    ],
)
def test_segments_lowercase_and_tokens(key, tokens, segment):
    assert landcover_segment(key, tokens) == segment


def test_hsg_segment():
    assert hsg_segment("0-5cm", "mean") == "hsg/global_soilgrids_0-5cm_mean"
    assert hsg_segment("15-30cm", "Q0.5") == "hsg/global_soilgrids_15-30cm_q0.5"


@pytest.mark.parametrize("token", ["a b", "a/b", "", "x_y", "..\\x"])
def test_segment_rejects_unsafe_token(token):
    with pytest.raises(ValidationError):
        landcover_segment("pl.gugik.bdot10k", ["gpkg", token])


def test_teryt_slot_paths(tmp_path):
    slot = selection_slot(tmp_path, "landcover/pl_bdot10k_gpkg", ".gpkg", teryt="1465")
    assert slot.std == tmp_path / "landcover/pl_bdot10k_gpkg/teryt/1465.gpkg"
    assert slot.versions_root == tmp_path / "landcover/pl_bdot10k_gpkg/versions/teryt"
    assert (slot.segment, slot.hierarchy, slot.name) == (
        "landcover/pl_bdot10k_gpkg",
        "teryt",
        "1465.gpkg",
    )
    assert selection_unit(teryt="1465") == "1465"


def test_bbox_slot_matches_cutout_convention(tmp_path):
    segment = "soil/global_soilgrids_clay_0-5cm_mean"
    slot = selection_slot(tmp_path, segment, ".tif", bbox=BBOX)
    assert slot.std == bbox_cutout_path(tmp_path, segment, BBOX, ".tif")
    assert slot.std.name == "450000.5_550000_460000_560000.25.tif"
    assert slot.versions_root == tmp_path / segment / "versions" / "bbox"
    assert selection_unit(bbox=BBOX) == "450000.5_550000_460000_560000.25"


def test_bbox_slot_requires_2180(tmp_path):
    with pytest.raises(ValidationError):
        selection_slot(
            tmp_path, "s", ".tif", bbox=BBox(19.0, 50.0, 19.1, 50.1, "EPSG:4326")
        )


@pytest.mark.parametrize(
    ("sheet", "canonical", "parts"),
    [
        ("N-34-130-D", "N-34-130-D", ("N-34", "130", "D")),
        ("M-33-036-A", "M-33-36-A", ("M-33", "36", "A")),
    ],
)
def test_sheet_slot_uses_sheet_hierarchy(tmp_path, sheet, canonical, parts):
    segment = "landcover/eu_corine_2018"
    slot = selection_slot(tmp_path, segment, ".tif", sheet=sheet)
    assert slot.std == tmp_path.joinpath(segment, *parts, f"{canonical}.tif")
    assert slot.versions_root == tmp_path.joinpath(segment, "versions", *parts)
    assert slot.hierarchy == "/".join(parts)
    assert selection_unit(sheet=sheet) == canonical


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"teryt": "1465", "sheet": "N-34-130-D"}, {"teryt": "1465", "bbox": BBOX}],
)
def test_selection_slot_requires_exactly_one(tmp_path, kwargs):
    with pytest.raises(ValidationError):
        selection_slot(Path(tmp_path), "s", ".tif", **kwargs)
    with pytest.raises(ValidationError):
        selection_unit(**kwargs)
