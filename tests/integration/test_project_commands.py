"""Data commands of project tasks: options, validation, result families
(``kartograf/project/commands.py``, ADR-040)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.catalog.kinds import options_to_json
from kartograf.core.bbox import BBox
from kartograf.download.collections import download_collection
from kartograf.download.cutout import PlCutoutResult
from kartograf.download.data import download_data
from kartograf.exceptions import DownloadError, KartografError, ValidationError
from kartograf.hydrology import calculate_hsg
from kartograf.landcover.manager import download_landcover, download_soil
from kartograf.project.commands import COMMANDS
from tests.integration.test_cli import _cz_provider_mock
from tests.integration.test_hsg import RasterSoilGrids
from tests.integration.test_landcover_output_params import FakePackages
from tests.support.project_fixtures import (
    BDOT_BBOX,
    CZ_FACTORY,
    HSG_SHEET,
    LAZ_AREA,
    PL_SHEET,
    G,
    LazTiles,
    bdot,
    landcover_sources,
    laz_tiles,
    pl_sheets,
)

ELEVATION = COMMANDS["elevation download"]
IMAGERY = COMMANDS["imagery download"]
LANDCOVER = COMMANDS["landcover download"]
SOIL = COMMANDS["soil download"]
HSG = COMMANDS["soil hsg"]
HYDRO = COMMANDS["hydro download"]
KRAKOW_5514 = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")


def _run(command, out: Path, options: dict):
    return command.download(
        out,
        options,
        update=None,
        plan=None,
        workers=None,
        summary=False,
        cache=False,
        on_progress=None,
        on_notice=None,
    )


def _raised(call) -> KartografError:
    with pytest.raises(KartografError) as caught:
        call()
    return caught.value


# --- options --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "options", "library"),
    [
        (
            LANDCOVER,
            {"product": "soilgrids", "bbox": BDOT_BBOX},
            "--product 'soilgrids': unknown value",
        ),
        (IMAGERY, {"product": "nmt", "sheet": G}, "--product 'nmt': nieznana wartosc"),
        (ELEVATION, {"sheet": G}, "--product wymagane: nmt ("),
        (LANDCOVER, {"teryt": "1465"}, "--product required: bdot10k ("),
    ],
    ids=["soilgrids-in-landcover", "nmt-in-imagery", "no-product", "no-landcover"],
)
def test_choice_of_another_command_rejected(tmp_path, command, options, library):
    data = options_to_json(command.options, options)
    error = _raised(lambda: command.validate(tmp_path / "out", data))
    assert isinstance(error, ValidationError) and str(error).startswith(library)
    with pytest.raises(ValidationError):
        command.check(tmp_path / "out", data, cache=False, on_notice=None)
    assert not (tmp_path / "out").exists()


# --- validation = the library's own checks ---------------------------------------

_BBOX = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
CLAY = {"property": "clay", "depth": "0-5cm", "stat": "mean"}
VALIDATION = {
    "elevation download": (
        PL_SHEET,
        {"product": "nmt", "sheet": G, "resolution": "1m"},
        lambda out, o: download_data(root=out, cache=False, **o),
    ),
    "imagery download": (
        {"product": "orto", "sheet": G},
        {"product": "orto", "sheet": G, "year": 2024, "min_year": 2020},
        lambda out, o: download_data(root=out, cache=False, **o),
    ),
    "landcover download": (
        {"product": "bdot10k", "teryt": "1465"},
        {"product": "corine", "bbox": _BBOX},
        lambda out, o: download_landcover(root=out, cache=False, **o),
    ),
    "soil download": (
        {"bbox": _BBOX, **CLAY},
        {"bbox": _BBOX, "property": "clay", "depth": "0-5cm"},
        lambda out, o: download_soil(root=out, cache=False, **o),
    ),
    "soil hsg": (
        {"sheet": HSG_SHEET, "depth": "0-5cm"},
        {"sheet": HSG_SHEET},
        lambda out, o: calculate_hsg(root=out, cache=False, **o),
    ),
    "boundaries download": (
        {"product": "admin", "teryt": "12"},
        {"product": "admin", "teryt": "1261"},
        lambda out, o: download_collection(root=out, cache=False, **o),
    ),
    "cadastre download": (
        {"product": "map", "country": "pl", "bbox": _BBOX},
        {"product": "map", "bbox": _BBOX},
        lambda out, o: download_collection(root=out, cache=False, **o),
    ),
    "models3d download": (
        {"product": "buildings", "teryt": "1261", "lod": 2},
        {"product": "buildings", "teryt": "1261", "lod": 1},
        lambda out, o: download_collection(root=out, cache=False, **o),
    ),
    "hydro download": (
        {"product": "network", "country": "cz", "whole_country": True},
        {"product": "network", "country": "pl", "whole_country": True},
        lambda out, o: download_collection(root=out, cache=False, **o),
    ),
}


@pytest.mark.parametrize("name", list(VALIDATION))
def test_validate_matches_library(tmp_path, monkeypatch, name):
    monkeypatch.chdir(tmp_path)
    command = COMMANDS[name]
    valid, invalid, library = VALIDATION[name]
    out = tmp_path / "out"
    assert command.validate(out, dict(valid)) is None
    expected = _raised(lambda: library(out, dict(invalid)))
    got = _raised(lambda: command.validate(out, dict(invalid)))
    assert type(got) is type(expected) and str(got) == str(expected)
    assert list(tmp_path.iterdir()) == []


# --- result families -----------------------------------------------------------


def _roles(files) -> list[tuple[str, str]]:
    return [(role, unit) for role, unit, _ in files.files]


def test_files_pl_sheet_and_laz_tiles(tmp_path):
    with pl_sheets():
        sheet = ELEVATION.files(_run(ELEVATION, tmp_path, PL_SHEET))
    with laz_tiles(LazTiles("N-33-131-B-a-1-1-1", "N-33-131-B-a-1-1-2")):
        tiles = ELEVATION.files(_run(ELEVATION, tmp_path, LAZ_AREA))
    assert sheet.complete and _roles(sheet) == [("output", G)]
    assert tiles.complete and _roles(tiles) == [
        ("output", "81121_1_N-33-131-B-a-1-1-1.laz"),
        ("output", "81121_1_N-33-131-B-a-1-1-2.laz"),
    ]
    for files in (sheet, tiles):
        for _, _, file in files.files:
            assert file.version_path.is_file() and file.path.is_file()


def test_files_auto_partial_success_incomplete(tmp_path):
    cz = _cz_provider_mock()
    cz.download_bbox.side_effect = DownloadError("CUZK 503")
    options = {
        "product": "nmt",
        "bbox": BBox(18.60, 49.73, 18.66, 49.76, "EPSG:4326"),
        "country": "auto",
        "resolution": {"pl": "1m", "cz": "2m"},
        "vertical_crs": {"pl": "EVRF2007", "cz": "Bpv"},
        "cutout": True,
        "horizontal_crs": "EPSG:3045",
    }
    with (
        patch(CZ_FACTORY, return_value=cz),
        patch(
            "kartograf.download.cutout.download_pl_cutout",
            return_value=PlCutoutResult(None),
        ),
    ):
        report = _run(ELEVATION, tmp_path, options)
    files = ELEVATION.files(report)
    assert report.ok  # the CLI exit rule: one country succeeded
    assert not files.complete and files.errors == ("CUZK 503",)


def test_files_bdot_area_failed_powiat_incomplete(tmp_path):
    with bdot(["0208", "0224", "0261"], FakePackages(fail={"0224"})):
        result = _run(LANDCOVER, tmp_path, {"product": "bdot10k", "bbox": BDOT_BBOX})
    files = LANDCOVER.files(result)
    assert not files.complete
    assert _roles(files) == [("output", "0208"), ("output", "0261")]
    assert files.errors == ("0224: BDOT10k TERYT 0224: HTTP 500",)


def test_files_bdot_keep_raw_has_raw_role(tmp_path):
    with bdot(["1465"]):
        result = _run(
            LANDCOVER,
            tmp_path,
            {"product": "bdot10k", "teryt": "1465", "keep_raw": True},
        )
    files = LANDCOVER.files(result)
    assert files.complete and _roles(files) == [("output", "1465"), ("raw", "1465")]


def test_files_hsg_output_and_three_inputs(tmp_path):
    with landcover_sources(soilgrids=RasterSoilGrids):
        result = _run(HSG, tmp_path, {"sheet": HSG_SHEET, "depth": "0-5cm"})
    files = HSG.files(result)
    assert files.complete and _roles(files) == [
        ("output", HSG_SHEET),
        ("input", f"clay {HSG_SHEET}"),
        ("input", f"sand {HSG_SHEET}"),
        ("input", f"silt {HSG_SHEET}"),
    ]


def test_files_hsg_failed_input_incomplete(tmp_path):
    provider = RasterSoilGrids({"silt": DownloadError("WCS 500")})
    with landcover_sources(soilgrids=lambda: provider):
        result = _run(HSG, tmp_path, {"sheet": HSG_SHEET, "depth": "0-5cm"})
    files = HSG.files(result)
    assert not files.complete
    assert _roles(files) == [
        ("input", f"clay {HSG_SHEET}"),
        ("input", f"sand {HSG_SHEET}"),
    ]
    assert files.errors == (f"silt {HSG_SHEET}: WCS 500",)
