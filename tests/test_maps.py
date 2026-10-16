"""BDOT10k map index and CZ ZTM sheet choices on recorded service responses."""

import pytest

from kartograf.download import collections as col
from kartograf.download.collections import (
    check_collection,
    download_collection,
    validate_collection_request,
)
from kartograf.exceptions import ValidationError
from tests.test_collections_units import (
    CUZK,
    FILES,
    INDEX,
    MAPS_GFI,
    Router,
    _key,
    file_answer,
    head_of,
    recorded,
)

pytestmark = pytest.mark.usefixtures("frozen_clock")


def test_bdot10k_sheet_formats_have_independent_versions(tmp_path, monkeypatch):
    """A GFI link supplies each original file; the sheet is canonicalized and
    the index date, not the HTTP response, drives update checks."""
    router = Router()
    monkeypatch.setattr(col, "_session", lambda: router)
    router.add_prefix(
        f"{MAPS_GFI}?", lambda: recorded(INDEX / "gfi_mapy10k_M-34-64-D-d-1.html")
    )
    for key in ("map10k_tiff", "map10k_pdf"):
        router.add(FILES[key]["url"], file_answer(key, head_of(key)))
    choices = {
        "product": "topographic",
        "output_dir": tmp_path,
        "sheet": "M-34-064-D-d-1",
        "scale": "1:10000",
        "cache": False,
    }
    files = {}
    for fmt in ("TIFF", "PDF"):
        report = download_collection(**choices, format=fmt)
        assert report.ok, report.failed
        files[fmt] = report.files[0].file
        assert files[fmt].label == "2026-05-27"
        assert files[fmt].path.stem == "M-34-64-D-d-1"
        assert f"maps/pl_bdot10k_10000_{fmt.lower()}" in str(files[fmt].path)
        plan = check_collection(**choices, format=fmt)
        assert plan.items[0].status == "current"
        assert plan.items[0].available_label == "2026-05-27"
    assert files["TIFF"].path.suffix == ".tif"
    assert files["PDF"].path.suffix == ".pdf"
    assert files["TIFF"].path != files["PDF"].path
    assert router.gets(FILES["map10k_tiff"]["url"]) == 1
    assert router.gets(FILES["map10k_pdf"]["url"]) == 1


def test_ztm_system_inferred_and_crs_of_each_sheet(tmp_path):
    """A CZ sheet code determines its grid, never an implicit map format/scale."""
    cases = (
        ("0301-B-01", "sjtsk", "TIFF", "EPSG:5514", ".zip"),
        ("NM-33-11-4-A-20", "etrs89", "PDF", "EPSG:3045", ".pdf"),
    )
    for sheet, system, fmt, crs, ext in cases:
        part = validate_collection_request(
            product="topographic",
            output_dir=tmp_path,
            sheet=sheet,
            scale="1:10000",
            format=fmt,
        ).parts[0]
        assert part.choice["sheet_system"] == system
        assert part.variant is not None and part.variant.sheet_grid is not None
        assert part.variant.sheet_grid.crs == crs
        assert part.ext == ext
        assert part.segment == f"maps/cz_ztm_10000_{system}_{fmt.lower()}"
    with pytest.raises(ValidationError, match="--sheet-system etrs89"):
        validate_collection_request(
            product="topographic",
            output_dir=tmp_path,
            sheet="0301-B-01",
            scale="1:10000",
            format="TIFF",
            sheet_system="etrs89",
        )
    with pytest.raises(ValidationError, match="TIFF, PDF"):
        validate_collection_request(
            product="topographic",
            output_dir=tmp_path,
            sheet="NM-33-11-4-A-20",
            scale="1:10000",
            format="SHP",
        )
    with pytest.raises(ValidationError, match="1:5000"):
        validate_collection_request(
            product="topographic",
            output_dir=tmp_path,
            sheet="0301-B-01",
            scale="1:2000",
            format="TIFF",
        )


def test_ztm_http_check_queries_selected_index_layer(tmp_path, monkeypatch):
    """ZTM10 S-JTSK validates the sheet in layer 2, then checks HTTP signal."""
    session = Router()
    monkeypatch.setattr(col, "_session", lambda: session)
    session.add_recorded(CUZK / "klady_2_where_0510-D-11.json")
    entry = FILES["cz_ztm10_tiff_0510-D-11"]
    session.heads[_key(entry["url"])] = entry["headers"]
    plan = check_collection(
        product="topographic",
        output_dir=tmp_path,
        sheet="0510-D-11",
        scale="1:10000",
        format="TIFF",
        cache=False,
    )
    (item,) = plan.items
    assert item.unit == "0510-D-11"
    assert item.segment == "maps/cz_ztm_10000_sjtsk_tiff"
    assert item.status == "missing"
    assert session.calls[-1] == ("HEAD", entry["url"])


@pytest.mark.parametrize(
    ("options", "missing"),
    [({"format": "TIFF"}, "--scale"), ({"scale": "1:10000"}, "--format")],
)
def test_map_selection_requires_scale_and_format(tmp_path, options, missing):
    with pytest.raises(ValidationError, match=missing):
        validate_collection_request(
            product="topographic",
            output_dir=tmp_path,
            sheet="M-34-064-D-d-1",
            **options,
        )
