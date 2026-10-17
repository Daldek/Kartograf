"""Public input validation uses KartografError without ValueError inheritance."""

from pathlib import Path

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.download.laz import download_laz_area
from kartograf.exceptions import KartografError, ValidationError
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.soilgrids import SoilGridsProvider


@pytest.mark.parametrize(
    "case",
    ["laz_vertical_crs", "vertical_crs", "soil_property", "bdot_format", "corine_year"],
)
def test_input_errors_are_kartograf_errors(case: str, tmp_path: Path) -> None:
    bbox_pl = BBox(450000, 550000, 460000, 560000, "EPSG:2180")

    def invalid() -> object:
        if case == "laz_vertical_crs":
            return download_laz_area(
                bbox=bbox_pl, output_dir=tmp_path, vertical_crs="bad", cache=False
            )
        if case == "vertical_crs":
            return GugikProvider(resolution="1m", vertical_crs="bad")
        if case == "soil_property":
            return SoilGridsProvider().edition("bad")
        if case == "bdot_format":
            return Bdot10kProvider().download_by_teryt(
                "1465", tmp_path / "out.gpkg", format="bad"
            )
        return CorineProvider().download_by_bbox(
            bbox_pl, tmp_path / "out.png", year=2020
        )

    with pytest.raises(ValidationError) as exc:
        invalid()
    assert isinstance(exc.value, KartografError)
    assert not isinstance(exc.value, ValueError)
