"""A6: country split of an area in the library (moved from the CLI)."""

from kartograf.core.bbox import BBox
from kartograf.download.countries import (
    CountryPart,
    countries_for_bbox,
    split_bbox_by_country,
)

KLODZKO = BBox(16.3, 50.2, 16.9, 50.6, "EPSG:4326")  # PL-CZ border area
WARSAW = BBox(20.9, 52.1, 21.1, 52.3, "EPSG:4326")


def test_border_area_has_both_countries():
    assert countries_for_bbox(KLODZKO) == ("CZ", "PL")


def test_inland_area_has_one_country():
    assert countries_for_bbox(WARSAW) == ("PL",)


def test_split_returns_parts_in_requested_crs():
    parts = split_bbox_by_country(KLODZKO, cz_crs="EPSG:2180")
    assert set(parts) == {"CZ", "PL"}
    assert all(isinstance(p, CountryPart) for p in parts.values())
    assert parts["CZ"].bbox.crs == "EPSG:2180"
    assert parts["PL"].bbox.crs == "EPSG:4326"


def test_cli_uses_library_functions():
    from kartograf.cli import download_cmd
    from kartograf.download import countries

    assert download_cmd._countries_for_bbox is countries.countries_for_bbox
    assert download_cmd._country_bbox is countries.country_bbox
