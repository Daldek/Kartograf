"""Segments and unit slots of land cover, HSG and collections (spec 3.4,
ADR-042 D8, ADR-044 D7)."""

from pathlib import Path

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.download.storage import bbox_cutout_path, content_segment, unit_slot
from kartograf.exceptions import ValidationError
from kartograf.landcover.store import hsg_segment, selection_unit

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
        ("pl.gugik.bdot10k", ["shp", "2024"], "landcover/pl_bdot10k_shp_2024"),
        ("eu.clms.corine", ["2018"], "landcover/eu_corine_2018"),
        ("eu.clms.corine", ["1990", "preview"], "landcover/eu_corine_1990_preview"),
        (
            "global.isric.soilgrids",
            ["clay", "0-5cm", "Q0.05"],
            "soil/global_soilgrids_clay_0-5cm_q0.05",
        ),
        ("pl.gugik.prg", ["gmina"], "boundaries/pl_prg_gmina"),
        ("pl.gugik.egib", [], "cadastre/pl_egib"),
    ],
)
def test_segments_lowercase_and_tokens(key, tokens, segment):
    assert content_segment(key, tokens) == segment


def test_hsg_segment():
    assert hsg_segment("0-5cm", "mean") == "hsg/global_soilgrids_0-5cm_mean"
    assert hsg_segment("15-30cm", "Q0.5") == "hsg/global_soilgrids_15-30cm_q0.5"


@pytest.mark.parametrize("token", ["a b", "a/b", "", "x_y", "..\\x"])
def test_segment_rejects_unsafe_token(token):
    with pytest.raises(ValidationError):
        content_segment("pl.gugik.bdot10k", ["gpkg", token])


def test_teryt_slot_paths(tmp_path):
    slot = unit_slot(tmp_path, "landcover/pl_bdot10k_gpkg", ".gpkg", teryt="1465")
    assert slot.std == tmp_path / "landcover/pl_bdot10k_gpkg/teryt/1465.gpkg"
    assert slot.versions_root == tmp_path / "landcover/pl_bdot10k_gpkg/versions/teryt"
    assert (slot.segment, slot.hierarchy, slot.name) == (
        "landcover/pl_bdot10k_gpkg",
        "teryt",
        "1465.gpkg",
    )
    assert slot.related_roots == ()
    assert selection_unit(teryt="1465") == "1465"


def test_bbox_slot_matches_cutout_convention(tmp_path):
    segment = "soil/global_soilgrids_clay_0-5cm_mean"
    slot = unit_slot(tmp_path, segment, ".tif", bbox=BBOX)
    assert slot.std == bbox_cutout_path(tmp_path, segment, BBOX, ".tif")
    assert slot.std.name == "450000.5_550000_460000_560000.25.tif"
    assert slot.versions_root == tmp_path / segment / "versions" / "bbox"
    assert selection_unit(bbox=BBOX) == "450000.5_550000_460000_560000.25"


def test_unit_slot_country_and_native_bbox(tmp_path):
    """ADR-042 D8: national file under ``country/<code>``, an area result in
    the native CRS of the service (no conversion in the slot)."""
    country = unit_slot(tmp_path, "boundaries/pl_prg_shp", ".zip", country="PL")
    assert country.std == tmp_path / "boundaries/pl_prg_shp/country/pl.zip"
    assert country.versions_root == tmp_path / "boundaries/pl_prg_shp/versions/country"
    assert (country.hierarchy, country.name) == ("country", "pl.zip")

    krovak = BBox(-460000.5, -1120000, -450000, -1110000, "EPSG:5514")
    related = (tmp_path / "x" / "versions" / "bbox",)
    area = unit_slot(
        tmp_path,
        "boundaries/cz_ruian_obec",
        ".gpkg",
        bbox=krovak,
        related_roots=related,
    )
    assert area.std == (
        tmp_path
        / "boundaries/cz_ruian_obec/bbox/-460000.5_-1120000_-450000_-1110000.gpkg"
    )
    assert area.versions_root == tmp_path / "boundaries/cz_ruian_obec/versions/bbox"
    assert area.related_roots == related


@pytest.mark.parametrize(
    ("sheet", "canonical", "parts"),
    [
        ("N-34-130-D", "N-34-130-D", ("N-34", "130", "D")),
        ("M-33-036-A", "M-33-36-A", ("M-33", "36", "A")),
    ],
)
def test_sheet_slot_uses_sheet_hierarchy(tmp_path, sheet, canonical, parts):
    segment = "landcover/eu_corine_2018"
    slot = unit_slot(tmp_path, segment, ".tif", sheet=sheet)
    assert slot.std == tmp_path.joinpath(segment, *parts, f"{canonical}.tif")
    assert slot.versions_root == tmp_path.joinpath(segment, "versions", *parts)
    assert slot.hierarchy == "/".join(parts)
    assert selection_unit(sheet=sheet) == canonical


@pytest.mark.parametrize(
    ("mapnom", "parts"),
    [
        ("0301-B-07-4", ("0301", "B", "07", "4")),  # ZTM5 S-JTSK
        ("0510-D-11", ("0510", "D", "11")),  # ZTM10
        ("0104-B-c", ("0104", "B", "c")),  # ZTM25
        ("0607-D", ("0607", "D")),  # ZTM50
        ("0607", ("0607",)),  # ZTM100
        ("11", ("11",)),  # ZTM250
        ("NM-33-11-4-A-20-2", ("NM-33", "11", "4", "A", "20", "2")),  # ZTM5 ETRS89
        ("NM-34-07-1-D-15", ("NM-34", "07", "1", "D", "15")),  # ZTM10
        ("NM-33-02", ("NM-33", "02")),  # ZTM250
    ],
)
def test_cuzk_map_sheet_slot_uses_sheet_hierarchy(tmp_path, mapnom, parts):
    """ADR-044 D7: a ZTM sheet lies in the hierarchy of its code like every
    sheet - each part a directory, the 1:1 000 000 sheet of an ETRS89 code
    in one (as ``N-34`` of PL-1992) - not flat among thousands of sheets."""
    segment = "maps/cz_ztm_10000_sjtsk_tiff"
    slot = unit_slot(tmp_path, segment, ".zip", mapnom=mapnom)
    assert slot.std == tmp_path.joinpath(segment, *parts, f"{mapnom}.zip")
    assert slot.versions_root == tmp_path.joinpath(segment, "versions", *parts)
    assert slot.hierarchy == "/".join(parts)


@pytest.mark.parametrize("mapnom", ["0510--11", "-0510", "0510-", "0510 D 11"])
def test_cuzk_map_sheet_slot_rejects_empty_parts(tmp_path, mapnom):
    """A code with an empty part would give an empty directory name."""
    with pytest.raises(ValidationError):
        unit_slot(tmp_path, "maps/cz_ztm_10000_sjtsk_tiff", ".zip", mapnom=mapnom)


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"teryt": "1465", "sheet": "N-34-130-D"}, {"teryt": "1465", "bbox": BBOX}],
)
def test_unit_slot_requires_exactly_one(tmp_path, kwargs):
    with pytest.raises(ValidationError):
        unit_slot(Path(tmp_path), "s", ".tif", **kwargs)
    with pytest.raises(ValidationError):
        selection_unit(**kwargs)


@pytest.mark.parametrize(
    "kwargs", [{"teryt": "../12"}, {"teryt": "1"}, {"country": "pol"}, {"country": ""}]
)
def test_unit_slot_rejects_unsafe_unit_names(tmp_path, kwargs):
    """Unit names become path elements: only TERYT digits and country codes."""
    with pytest.raises(ValidationError):
        unit_slot(tmp_path, "s", ".zip", **kwargs)
