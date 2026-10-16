"""Data commands of project tasks: options, validation, result families
(``kartograf/project/commands.py``, ADR-040)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.core.bbox import BBox
from kartograf.download.collections import download_collection
from kartograf.download.cutout import PlCutoutResult
from kartograf.download.data import download_data
from kartograf.exceptions import DownloadError, KartografError, ValidationError
from kartograf.hydrology import HSGCalculator
from kartograf.landcover.manager import LandCoverManager
from kartograf.project.commands import (
    COMMANDS,
    check_options_json,
    options_from_json,
    options_to_json,
)
from tests.project_fixtures import (
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
from tests.test_cli import _cz_provider_mock
from tests.test_hsg import RasterSoilGrids
from tests.test_landcover_output_params import FakePackages

ELEVATION = COMMANDS["elevation download"]
IMAGERY = COMMANDS["imagery download"]
LANDCOVER = COMMANDS["landcover download"]
SOIL = COMMANDS["soil download"]
HSG = COMMANDS["soil hsg"]
HYDRO = COMMANDS["hydro download"]
KRAKOW_5514 = BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514")


def _run(command, out: Path, options: dict):
    return command.download(
        out, options, update=None, cache=False, on_progress=None, on_notice=None
    )


def _raised(call) -> KartografError:
    with pytest.raises(KartografError) as caught:
        call()
    return caught.value


# --- options --------------------------------------------------------------------


def test_options_json_roundtrip(tmp_path):
    project = tmp_path / "projekt"
    elevation = {
        "vertical_crs": "EVRF2007",
        "cutout": True,
        "product": "nmt",
        "full_sheet": False,
        "bbox": KRAKOW_5514,
        "year": None,
        "resolution": {"pl": "1m", "cz": "2m"},
        "country": "auto",
        "horizontal_crs": "EPSG:5514",
    }
    data = options_to_json(ELEVATION, elevation)
    assert list(data.items()) == [
        ("product", "nmt"),
        ("bbox", [-447000, -1114000, -446000, -1113000]),
        ("bbox_crs", "EPSG:5514"),
        ("country", "auto"),
        ("resolution", {"pl": "1m", "cz": "2m"}),
        ("vertical_crs", "EVRF2007"),
        ("cutout", True),
        ("horizontal_crs", "EPSG:5514"),
    ]
    expected = {k: v for k, v in elevation.items() if v is not None and v is not False}
    assert options_from_json(ELEVATION, data, project_dir=project) == expected

    absolute = (tmp_path / "obszary" / "b.gpkg").resolve()
    for given, saved, read in (
        (
            Path("obszar/zlewnia.gpkg"),
            "obszar/zlewnia.gpkg",
            project / "obszar/zlewnia.gpkg",
        ),
        (absolute, absolute.as_posix(), absolute),
    ):
        landcover = {
            "source": "bdot10k",
            "geometry": given,
            "layers": ("SWRS", "PTWP"),
            "keep_raw": True,
        }
        data = options_to_json(LANDCOVER, landcover)
        assert data == {
            "source": "bdot10k",
            "geometry": saved,
            "layers": ["SWRS", "PTWP"],
            "keep_raw": True,
        }
        assert check_options_json(LANDCOVER, data) is None
        assert options_from_json(LANDCOVER, data, project_dir=project) == {
            **landcover,
            "geometry": read,
        }


@pytest.mark.parametrize(
    ("command", "options"),
    [
        (LANDCOVER, {"source": "bdot10k", "teryt": "1465", "vertical_crs": "EVRF2007"}),
        (SOIL, {"sheet": HSG_SHEET, "timeout": 30}),
        (ELEVATION, {**PL_SHEET, "output_dir": "data"}),
        (ELEVATION, {**PL_SHEET, "update": "upgrade"}),
        (ELEVATION, {**PL_SHEET, "workers": 2}),
        (ELEVATION, {**PL_SHEET, "bbox_crs": "EPSG:2180"}),
        (ELEVATION, {**PL_SHEET, "year": "2024"}),
        (ELEVATION, {**PL_SHEET, "year": True}),
        (ELEVATION, {**PL_SHEET, "bbox": [1, 2, 3, 4]}),
        (ELEVATION, {**PL_SHEET, "resolution": {"pl": 1}}),
        (LANDCOVER, {"source": "bdot10k", "teryt": "1465", "layers": "SWRS"}),
        (HYDRO, {"product": "network", "teryt": "1261"}),
    ],
    ids=[
        "flag-of-another-group",
        "timeout",
        "output-dir",
        "update",
        "workers",
        "bbox-crs-alone",
        "year-text",
        "year-bool",
        "bbox-list",
        "per-country-number",
        "layers-text",
        "hydro-teryt",
    ],
)
def test_options_reject_unknown_and_foreign(command, options):
    with pytest.raises(ValidationError):
        options_to_json(command, options)


@pytest.mark.parametrize(
    ("command", "options", "library"),
    [
        (
            LANDCOVER,
            {"source": "soilgrids", "bbox": BDOT_BBOX},
            "--source 'soilgrids': nieznana wartosc",
        ),
        (IMAGERY, {"product": "nmt", "sheet": G}, "--product 'nmt': nieznana wartosc"),
        (ELEVATION, {"sheet": G}, "--product wymagane: nmt ("),
        (LANDCOVER, {"teryt": "1465"}, "--source wymagane: bdot10k ("),
    ],
    ids=["soilgrids-in-landcover", "nmt-in-imagery", "no-product", "no-source"],
)
def test_choice_of_another_command_rejected(tmp_path, command, options, library):
    data = options_to_json(command, options)
    error = _raised(lambda: command.validate(tmp_path / "out", data))
    assert isinstance(error, ValidationError) and str(error).startswith(library)
    with pytest.raises(ValidationError):
        command.check(tmp_path / "out", data, cache=False, on_notice=None)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "data",
    [
        {"product": None},
        {"cutout": False},
        {"bbox": [1, 2, 3, 4]},
        {"bbox_crs": "EPSG:2180"},
        {"bbox": [1, 2, 3], "bbox_crs": "EPSG:2180"},
        {"bbox": [1, 2, 3, float("nan")], "bbox_crs": "EPSG:2180"},
        {"year": "2024"},
        {"geometry": ""},
        {"resolution": ["1m"]},
        {"source": "bdot10k"},
        [],
    ],
)
def test_check_options_json_rejects(data):
    assert check_options_json(ELEVATION, data) is not None


# --- validation = the library's own checks ---------------------------------------

_BBOX = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
CLAY = {"property": "clay", "depth": "0-5cm", "stat": "mean"}
VALIDATION = {
    "elevation download": (
        PL_SHEET,
        {"product": "nmt", "sheet": G, "resolution": "1m"},
        lambda out, o: download_data(output_dir=out, cache=False, **o),
    ),
    "imagery download": (
        {"product": "orto", "sheet": G},
        {"product": "orto", "sheet": G, "year": 2024, "min_year": 2020},
        lambda out, o: download_data(output_dir=out, cache=False, **o),
    ),
    "landcover download": (
        {"source": "bdot10k", "teryt": "1465"},
        {"source": "corine", "bbox": _BBOX},
        lambda out, o: LandCoverManager(out, o.pop("source"), cache=False).download(
            **o
        ),
    ),
    "soil download": (
        {"bbox": _BBOX, **CLAY},
        {"bbox": _BBOX, "property": "clay", "depth": "0-5cm"},
        lambda out, o: LandCoverManager(out, "soilgrids", cache=False).download(**o),
    ),
    "soil hsg": (
        {"sheet": HSG_SHEET, "depth": "0-5cm"},
        {"sheet": HSG_SHEET},
        lambda out, o: HSGCalculator(out, cache=False).calculate_hsg(
            **{"depth": None, **o}
        ),
    ),
    "boundaries download": (
        {"product": "admin", "teryt": "12"},
        {"product": "admin", "teryt": "1261"},
        lambda out, o: download_collection(output_dir=out, cache=False, **o),
    ),
    "cadastre download": (
        {"product": "map", "country": "pl", "bbox": _BBOX},
        {"product": "map", "bbox": _BBOX},
        lambda out, o: download_collection(output_dir=out, cache=False, **o),
    ),
    "models3d download": (
        {"product": "buildings", "teryt": "1261", "lod": 2},
        {"product": "buildings", "teryt": "1261", "lod": 1},
        lambda out, o: download_collection(output_dir=out, cache=False, **o),
    ),
    "hydro download": (
        {"product": "network", "country": "cz", "whole_country": True},
        {"product": "network", "country": "pl", "whole_country": True},
        lambda out, o: download_collection(output_dir=out, cache=False, **o),
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
        result = _run(LANDCOVER, tmp_path, {"source": "bdot10k", "bbox": BDOT_BBOX})
    files = LANDCOVER.files(result)
    assert not files.complete
    assert _roles(files) == [("output", "0208"), ("output", "0261")]
    assert files.errors == ("0224: BDOT10k TERYT 0224: HTTP 500",)


def test_files_bdot_keep_raw_has_raw_role(tmp_path):
    with bdot(["1465"]):
        result = _run(
            LANDCOVER,
            tmp_path,
            {"source": "bdot10k", "teryt": "1465", "keep_raw": True},
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
