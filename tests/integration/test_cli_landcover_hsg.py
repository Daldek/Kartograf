"""``landcover download``, ``soil download`` and ``soil hsg`` on the version
store (CLI).

Update modes, plan files and status lines (spec 4.2, 4.4, 4.5) through
``main`` with fake sources (no network).
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from kartograf.cli.commands import main
from kartograf.core.bbox import BBox
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.hydrology.hsg import HSGCalculator
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kPackage, Bdot10kProvider
from tests.conftest import FakeCorine, FakeSoilGrids
from tests.integration.test_hsg import RasterSoilGrids
from tests.support.errors import without_error_document
from tests.support.project_fixtures import landcover_sources

BBOX_ARG = "770000,509000,772000,511000"
COORDS = "770000_509000_772000_511000"
SOIL = ["--property", "clay", "--depth", "0-5cm", "--stat", "mean"]
SOIL += ["--bbox", BBOX_ARG]
CLAY = f"soil/global_soilgrids_clay_0-5cm_mean/bbox/{COORDS}.tif"


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    """The CLI metadata cache lands in the cwd."""
    monkeypatch.chdir(tmp_path)


def _session(fake):
    """Every provider session of the call is ``fake``."""
    return patch("kartograf.transport.http.SessionPerThread.get", return_value=fake)


def _lc(tmp_path, *argv):
    """``landcover download`` (``argv`` with ``--product``) into ``<tmp>/out``."""
    return main(["landcover", "download", *argv, "--root", str(tmp_path / "out")])


def _soil(tmp_path, *argv):
    """``soil download`` (SoilGrids) into ``<tmp>/out``."""
    return main(["soil", "download", *argv, "--root", str(tmp_path / "out")])


def _hsg(tmp_path, *argv):
    return main(
        ["soil", "hsg", "--bbox", BBOX_ARG, "--depth", "0-5cm"]
        + ["--root", str(tmp_path / "out"), *argv]
    )


# --- landcover download and soil download ---------------------------------------


@pytest.mark.parametrize(
    "flags", [["--check-updates", "--upgrade"], ["--upgrade", "--force"]]
)
def test_landcover_update_flags_exclusive(tmp_path, flags, capsys):
    with pytest.raises(SystemExit) as exc:
        _soil(tmp_path, *SOIL, *flags)
    assert exc.value.code == 2
    assert "not allowed with" in capsys.readouterr().err


@pytest.mark.parametrize("command", [["landcover", "download"], ["soil", "hsg"]])
def test_plan_without_mode_is_error(tmp_path, command, capsys):
    rc = main([*command, "--plan", str(tmp_path / "p.json"), "--root", str(tmp_path)])
    assert rc == 2
    assert "Error: --plan wymaga --check-updates albo --upgrade" in (
        capsys.readouterr().err
    )


def test_landcover_check_writes_plan(tmp_path, capsys):
    fake = FakeSoilGrids("2.0")
    plan_file = tmp_path / "plan.json"
    with _session(fake):
        rc = _soil(tmp_path, *SOIL, "--check-updates", "--plan", str(plan_file))
    assert rc == 0
    assert fake.coverages == 0
    assert f"{CLAY}: do pobrania (2.0)" in capsys.readouterr().out
    items = json.loads(plan_file.read_text())["items"]
    assert [(i["track"], i["status"]) for i in items] == [("landcover", "missing")]
    assert not (tmp_path / "out" / "soil").exists()


def test_landcover_soilgrids_status_default_asks_no_edition(tmp_path, capsys):
    with _session(FakeSoilGrids("2.0")):
        assert _soil(tmp_path, *SOIL) == 0
    first = capsys.readouterr().out
    assert f"{CLAY}: nowa wersja 2.0_" in first
    assert "Downloaded to:" not in first
    newer = FakeSoilGrids("2.1")
    with _session(newer):
        assert _soil(tmp_path, *SOIL) == 0
    out = capsys.readouterr().out
    # the default mode asks no source for a local version (ADR-036 erratum 3)
    assert f"{CLAY}: lokalna wersja 2.0 (bez sprawdzania; --check-updates)" in out
    assert newer.capabilities == 0


def test_landcover_upgrade_plan_stale_exit_1(tmp_path, capsys):
    plan_file = tmp_path / "plan.json"
    with _session(FakeSoilGrids("2.0")):
        _soil(tmp_path, *SOIL)
    with _session(FakeSoilGrids("2.1")):
        _soil(tmp_path, *SOIL, "--check-updates", "--plan", str(plan_file))
    capsys.readouterr()
    fake = FakeSoilGrids("2.2")
    with _session(fake):
        rc = _soil(tmp_path, *SOIL, "--upgrade", "--plan", str(plan_file))
    assert rc == 10
    assert fake.coverages == 0
    assert f"Error: {CLAY}: zrodlo zmienilo sie od planu (2.1)" in (
        capsys.readouterr().err
    )


def test_landcover_status_lines_and_summary(tmp_path, capsys, caplog):
    def package(code, output_path, **kwargs):
        if code == "0224":
            raise DownloadError("BDOT10k TERYT 0224: HTTP 500")
        output_path.write_bytes(code.encode())
        return Bdot10kPackage(path=output_path, teryt=code, url="u", format="GPKG")

    with (
        patch(
            "kartograf.providers.pl.bdot10k.discover_teryts_for_bbox",
            return_value=["0208", "0224"],
        ),
        patch.object(Bdot10kProvider, "download_package", side_effect=package),
    ):
        rc = _lc(tmp_path, "--product", "bdot10k", "--bbox", BBOX_ARG)
    assert rc == 10
    captured = capsys.readouterr()
    assert "landcover/pl_bdot10k_gpkg/teryt/0208.gpkg: nowa wersja " in captured.out
    error = "Error: 0224: BDOT10k TERYT 0224: HTTP 500"
    assert captured.err.splitlines().count(error) == 1
    assert (
        "Nowe: 1, nowa etykieta: 0, bez zmian: 0, lokalne: 0, bledy: 1 "
        f"({tmp_path / 'out'})"
    ) in captured.out
    assert not any(
        record.name == "kartograf.landcover.manager"
        and record.levelno >= logging.WARNING
        for record in caplog.records
    )


def test_landcover_bdot_rerun_unchecked_line(tmp_path, capsys):
    def package(code, output_path, **kwargs):
        output_path.write_bytes(b"gpkg")
        return Bdot10kPackage(path=output_path, teryt=code, url="u", format="GPKG")

    with patch.object(Bdot10kProvider, "download_package", side_effect=package) as pkg:
        assert _lc(tmp_path, "--product", "bdot10k", "--teryt", "1465") == 0
        assert _lc(tmp_path, "--product", "bdot10k", "--teryt", "1465") == 0
        assert (
            _lc(tmp_path, "--product", "bdot10k", "--teryt", "1465", "--upgrade") == 0
        )
    assert pkg.call_count == 1
    captured = capsys.readouterr()
    assert "landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: lokalna wersja " in captured.out
    assert "(bez sprawdzania; --check-updates)" in captured.out
    assert "Info: landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: lokalna wersja" in (
        captured.err
    )


def test_landcover_check_keep_raw_lines_name_each_file(tmp_path, capsys):
    """GPKG and raw ZIP of one TERYT: two distinct plan lines (backlog 0.8.0)."""
    with patch(
        "kartograf.providers.pl.bdot10k.discover_teryts_for_bbox",
        return_value=["0208"],
    ):
        argv = ["--product", "bdot10k", "--bbox", BBOX_ARG, "--keep-raw"]
        rc = _lc(tmp_path, *argv, "--check-updates")
    assert rc == 0
    assert capsys.readouterr().out.splitlines() == [
        "landcover/pl_bdot10k_gpkg/teryt/0208.gpkg: do pobrania",
        "landcover/pl_bdot10k_gpkg_zip/teryt/0208.zip: do pobrania",
    ]


def test_landcover_corine_preview_line(tmp_path, capsys, caplog):
    with (
        _session(FakeCorine()),
        patch.object(CorineProvider, "has_clms_token", new=False),
    ):
        rc = _lc(tmp_path, "--product", "corine", "--year", "2018", "--bbox", BBOX_ARG)
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == (
        "Info: CORINE 2018: podglad WMS (stylizowany PNG, nie dane; dane CLMS "
        "wymagaja CLMS_CREDENTIALS)\n"
    )
    assert (
        f"landcover/eu_corine_2018_preview/bbox/{COORDS}.png: nowa wersja "
        in captured.out
    )
    assert not any(
        record.name == "kartograf.providers.corine"
        and record.levelno >= logging.WARNING
        for record in caplog.records
    )


def test_corine_preview_not_emitted_for_invalid_sheet(tmp_path, capsys):
    with patch.object(CorineProvider, "has_clms_token", new=False):
        manager = LandCoverManager("corine", cache=False, root=tmp_path / "api")
        with pytest.raises(ValidationError) as exc:
            manager.download(sheet="XYZ", year=2018)
        assert (
            _lc(tmp_path, "--product", "corine", "--sheet", "XYZ", "--year", "2018")
            == 2
        )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        without_error_document(captured.err) == f"Error: {exc.value.localized('pl')}\n"
    )


def test_hsg_invalid_sheet_has_no_header(tmp_path, capsys):
    with pytest.raises(ValidationError) as exc:
        HSGCalculator(cache=False, root=tmp_path / "api").calculate_hsg(
            sheet="XYZ", depth="0-5cm"
        )
    assert (
        main(
            [
                "soil",
                "hsg",
                "--sheet",
                "XYZ",
                "--depth",
                "0-5cm",
                "--root",
                str(tmp_path / "cli"),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        without_error_document(captured.err) == f"Error: {exc.value.localized('pl')}\n"
    )


@pytest.mark.parametrize("mode", ["check", "download"])
def test_invalid_teryt_matches_cli_and_api(tmp_path, capsys, mode):
    manager = LandCoverManager("bdot10k", cache=False, root=tmp_path / "api")
    with pytest.raises(
        ValidationError,
        match="^--teryt 14: BDOT10k is published per county - give --teryt <4 digits>",
    ) as exc:
        getattr(manager, mode)(teryt="14")
    flags = ["--check-updates"] if mode == "check" else []
    assert _lc(tmp_path, "--product", "bdot10k", "--teryt", "14", *flags) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        without_error_document(captured.err) == f"Error: {exc.value.localized('pl')}\n"
    )


@pytest.mark.parametrize(
    ("coordinates", "bbox"),
    [
        ("2,1,1,2", BBox(2, 1, 1, 2, "EPSG:2180")),
        ("nan,1,2,2", BBox(float("nan"), 1, 2, 2, "EPSG:2180")),
    ],
)
@pytest.mark.parametrize("mode", ["check", "download"])
def test_invalid_landcover_bbox_matches_cli_and_api(
    tmp_path, capsys, coordinates, bbox, mode
):
    manager = LandCoverManager("bdot10k", cache=False, root=tmp_path / "api")
    with pytest.raises(ValidationError) as exc:
        getattr(manager, mode)(bbox=bbox)
    flags = ["--check-updates"] if mode == "check" else []
    assert _lc(tmp_path, "--product", "bdot10k", "--bbox", coordinates, *flags) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        without_error_document(captured.err) == f"Error: {exc.value.localized('pl')}\n"
    )


@pytest.mark.parametrize(
    ("coordinates", "bbox"),
    [
        ("2,1,1,2", BBox(2, 1, 1, 2, "EPSG:2180")),
        ("nan,1,2,2", BBox(float("nan"), 1, 2, 2, "EPSG:2180")),
    ],
)
@pytest.mark.parametrize("mode", ["check_hsg", "calculate_hsg"])
def test_invalid_hsg_bbox_matches_cli_and_api(
    tmp_path, capsys, coordinates, bbox, mode
):
    calc = HSGCalculator(cache=False, root=tmp_path / "api")
    with pytest.raises(ValidationError) as exc:
        getattr(calc, mode)(bbox=bbox, depth="0-5cm")
    flags = ["--check-updates"] if mode == "check_hsg" else []
    assert (
        main(
            [
                "soil",
                "hsg",
                "--bbox",
                coordinates,
                "--depth",
                "0-5cm",
                "--root",
                str(tmp_path / "cli"),
                *flags,
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        without_error_document(captured.err) == f"Error: {exc.value.localized('pl')}\n"
    )


@pytest.mark.parametrize("mode", ["check", "download"])
def test_unsupported_bbox_crs_rejected_before_transform(tmp_path, mode):
    manager = LandCoverManager("corine", cache=False, root=tmp_path / "api")
    with pytest.raises(ValidationError, match="Invalid bbox:") as exc:
        getattr(manager, mode)(bbox=BBox(0, 0, 1, 1, "EPSG:999999"), year=2018)
    assert "EPSG:999999" in str(exc.value)


@pytest.mark.parametrize("mode", ["check_hsg", "calculate_hsg"])
def test_hsg_unsupported_bbox_crs_rejected_before_transform(tmp_path, mode):
    calc = HSGCalculator(cache=False, root=tmp_path / "api")
    with pytest.raises(ValidationError, match="Invalid bbox:") as exc:
        getattr(calc, mode)(bbox=BBox(0, 0, 1, 1, "EPSG:999999"), depth="0-5cm")
    assert "EPSG:999999" in str(exc.value)


# --- soil hsg -----------------------------------------------------------------


def test_hsg_cli_output_tif_rejected(tmp_path, capsys):
    fake = FakeSoilGrids()
    with _session(fake):
        rc = main(
            ["soil", "hsg", "--bbox", BBOX_ARG, "--depth", "0-5cm"]
            + ["--root", str(tmp_path / "hsg.tif")]
        )
    assert rc == 2
    assert fake.capabilities == 0
    with pytest.raises(ValidationError) as error:
        HSGCalculator(root=tmp_path / "hsg.tif")
    assert (
        without_error_document(capsys.readouterr().err)
        == f"Error: {error.value.localized('pl')}\n"
    )


def test_hsg_cli_keep_intermediate_removed(tmp_path):
    with pytest.raises(SystemExit) as exc:
        _hsg(tmp_path, "--keep-intermediate")
    assert exc.value.code == 2


def test_hsg_cli_reused_line(tmp_path, capsys):
    with _session(FakeSoilGrids("2.0")):
        assert _hsg(tmp_path) == 0
    first = capsys.readouterr().out
    hsg = f"hsg/global_soilgrids_0-5cm_mean/bbox/{COORDS}.tif"
    assert f"{hsg}: nowa wersja 2.0_" in first
    assert f"{CLAY}: nowa wersja 2.0_" in first
    fake = FakeSoilGrids("2.0")
    with _session(fake):
        assert _hsg(tmp_path, "--force") == 0
    out = capsys.readouterr().out
    assert f"{CLAY}: bez zmian 2.0" in out
    assert f"{hsg}: uzyta ponownie 2.0" in out
    assert fake.coverages == 3


def test_hsg_cli_check_plan_tracks(tmp_path, capsys):
    plan_file = tmp_path / "plan.json"
    fake = FakeSoilGrids("2.0")
    with _session(fake):
        rc = _hsg(tmp_path, "--check-updates", "--plan", str(plan_file))
    assert rc == 0 and fake.coverages == 0
    out = capsys.readouterr().out
    for segment in ("clay_0-5cm_mean", "sand_0-5cm_mean", "silt_0-5cm_mean"):
        line = f"soil/global_soilgrids_{segment}/bbox/{COORDS}.tif: do pobrania (2.0)"
        assert line in out
    assert f"hsg/global_soilgrids_0-5cm_mean/bbox/{COORDS}.tif: do pobrania" in out
    items = json.loads(plan_file.read_text())["items"]
    assert [i["track"] for i in items] == ["landcover"] * 3 + ["hsg"]
    assert {i["unit"] for i in items} == {COORDS}
    with _session(FakeSoilGrids("2.0")):
        assert _hsg(tmp_path, "--upgrade", "--plan", str(plan_file)) == 0
    assert "hsg/global_soilgrids_0-5cm_mean" in capsys.readouterr().out


class _GridSoilGrids(RasterSoilGrids):
    """SoilGrids loam on its own EPSG:4326 grid of 0.0025 deg cells, which
    reaches beyond the request area as the real service does."""

    LOAM = {"clay": 200, "sand": 400, "silt": 400}

    def download_by_bbox(self, bbox, output_path, timeout=120, *, property, **kw):
        import math

        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        from kartograf.core.bbox import transform_bbox

        step = 0.0025
        wgs = transform_bbox(bbox, "EPSG:4326")
        west = math.floor(wgs.min_x / step) * step
        north = math.ceil(wgs.max_y / step) * step
        width = math.ceil((wgs.max_x - west) / step)
        height = math.ceil((north - wgs.min_y) / step)
        target = Path(output_path).with_suffix(".tif")
        with rasterio.open(
            target,
            "w",
            driver="GTiff",
            dtype="float32",
            width=width,
            height=height,
            count=1,
            crs="EPSG:4326",
            transform=from_origin(west, north, step, step),
            nodata=0,
        ) as dst:
            dst.write(np.full((1, height, width), self.LOAM[property], "float32"))
        return target


def test_hsg_cli_summary_from_store_path(tmp_path, capsys):
    """The summary covers the request area (bbox 2 x 2 km = 400 ha), not the
    whole SoilGrids raster reaching beyond it."""
    with landcover_sources(soilgrids=_GridSoilGrids):
        assert _hsg(tmp_path, "--summary") == 0
    out = capsys.readouterr().out
    assert "Statystyki HSG obszaru zadania (grupy: % powierzchni z danymi):" in out
    assert "Grupa B: " in out or "Grupa A: " in out
    assert "  Brak danych: " in out and "% obszaru zadania (" in out
    (total,) = [line for line in out.splitlines() if "Obszar zadania:" in line]
    assert float(total.split()[-2]) == pytest.approx(400.0, rel=0.01)
    store = Path(tmp_path / "out" / "hsg/global_soilgrids_0-5cm_mean/bbox")
    assert (store / f"{COORDS}.tif").exists()


def test_hsg_unexpected_error_uses_main_barrier(tmp_path, capsys, monkeypatch):
    with patch(_HSG, side_effect=RuntimeError("nieoczekiwany blad")):
        assert _hsg(tmp_path) == 1
        (line, hint) = without_error_document(capsys.readouterr().err).splitlines()
        assert line == "Error: RuntimeError: nieoczekiwany blad"
        assert hint == "Ustaw KARTOGRAF_DEBUG=1, aby zobaczyc pelny traceback."
        monkeypatch.setenv("KARTOGRAF_DEBUG", "1")
        with pytest.raises(RuntimeError, match="nieoczekiwany blad"):
            _hsg(tmp_path)


# --- R7 flags: --layers, --keep-raw, --bbox-crs, --workers, --quiet ----------

_LANDCOVER = "kartograf.cli.landcover_cmd.download_landcover"
_HSG = "kartograf.cli.soil_cmd.calculate_hsg"


def _bdot(tmp_path, *flags):
    return [
        "landcover",
        "download",
        "--product",
        "bdot10k",
        "--root",
        str(tmp_path),
        *flags,
    ]


def test_layers_bad_code_is_library_error_before_network(tmp_path, capsys):
    with patch(
        "kartograf.providers.pl.bdot10k.Bdot10kProvider.download_package"
    ) as get:
        rc = main(_bdot(tmp_path, "--teryt", "1465", "--layers", "SWRS,swrs1"))
    assert rc == 2
    get.assert_not_called()
    (line,) = without_error_document(capsys.readouterr().err).splitlines()
    assert line.startswith("Error: ") and "SWRS1" in line


@pytest.mark.parametrize("flag", ["--layers", "--keep-raw"])
def test_bdot_only_flags_rejected_for_other_sources(tmp_path, capsys, flag):
    argv = [
        "landcover",
        "download",
        "--product",
        "corine",
        "--year",
        "2018",
        "--sheet",
        "N-34-130-D",
        "--root",
        str(tmp_path),
        flag,
        *(["SWRS"] if flag == "--layers" else []),
    ]
    assert main(argv) == 2
    assert f"Error: {flag} dziala tylko z --product bdot10k" in capsys.readouterr().err


def _landcover_report():
    from kartograf.landcover.manager import LandCoverReport

    return LandCoverReport((), (), (), (), (), True)


def test_landcover_flags_reach_the_api(tmp_path):
    with patch(_LANDCOVER, return_value=_landcover_report()) as call:
        assert main(_bdot(tmp_path, "--teryt", "1465")) == 0
        assert call.call_args.kwargs["workers"] == 1
        assert main(_bdot(tmp_path, "--teryt", "1465", "--workers", "3")) == 0
        assert call.call_args.kwargs["workers"] == 3
        argv = _bdot(tmp_path, "--geometry", "obszar.gpkg", "--layer", "obszar")
        assert main(argv) == 0
        assert call.call_args.kwargs["layer"] == "obszar"
        argv = _bdot(tmp_path, "--bbox", "18.6,49.7,18.7,49.8")
        assert main([*argv, "--bbox-crs", "EPSG:4326"]) == 0
        assert call.call_args.kwargs["bbox"] == BBox(
            18.6, 49.7, 18.7, 49.8, "EPSG:4326"
        )


def test_landcover_quiet_drops_status_lines_keeps_notices(tmp_path, capsys):
    def package(code, output_path, **kwargs):
        output_path.write_bytes(code.encode())
        return Bdot10kPackage(path=output_path, teryt=code, url="u", format="GPKG")

    def run(*flags):
        out = tmp_path / ("quiet" if flags else "loud")
        with (
            patch(
                "kartograf.providers.pl.bdot10k.discover_teryts_for_bbox",
                return_value=["0208", "0224"],
            ),
            patch.object(Bdot10kProvider, "download_package", side_effect=package),
        ):
            rc = main(
                ["landcover", "download", "--product", "bdot10k", "--bbox", BBOX_ARG]
                + ["--root", str(out), *flags]
            )
        assert rc == 0
        return capsys.readouterr()

    loud = run()
    assert "nowa wersja" in loud.out and "Nowe: 2" in loud.out
    quiet = run("-q")
    assert quiet.out == ""
    assert quiet.err == loud.err


def test_hsg_quiet_prints_nothing_on_stdout(tmp_path, capsys):
    with _session(FakeSoilGrids("2.0")):
        assert _hsg(tmp_path) == 0
    assert "Legenda:" in capsys.readouterr().out
    with _session(FakeSoilGrids("2.0")):
        assert _hsg(tmp_path, "-q", "--upgrade") == 0
    assert capsys.readouterr().out == ""


def test_hsg_bbox_crs_and_layer_reach_the_api(tmp_path):
    from kartograf.hydrology.hsg import HsgReport

    with patch(_HSG) as call:
        call.return_value = HsgReport((), (), (), (), (), True)
        argv = ["soil", "hsg", "--bbox", "18.6,49.7,18.7,49.8"]
        argv += ["--bbox-crs", "EPSG:4326", "--depth", "0-5cm", "--layer", "x"]
        assert main([*argv, "--root", str(tmp_path / "out")]) == 0
    assert call.call_args.kwargs["bbox"] == BBox(18.6, 49.7, 18.7, 49.8, "EPSG:4326")
    assert call.call_args.kwargs["layer"] == "x"


def test_soil_download_failure_line_and_exit_code(tmp_path, capsys):
    with _session(FakeSoilGrids(404)):
        assert _soil(tmp_path, "--bbox", BBOX_ARG, *SOIL) == 11
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(
        f"Error: {COORDS}: SoilGrids GetCapabilities clay: HTTP 404"
    )
    assert not (tmp_path / "out").exists()


def test_hsg_failed_input_no_legend_no_raster(tmp_path, capsys):
    provider = RasterSoilGrids({"silt": DownloadError("WCS 500")})
    with landcover_sources(soilgrids=lambda: provider):
        assert _hsg(tmp_path, "--summary") == 11
    captured = capsys.readouterr()
    assert captured.err == f"Error: silt {COORDS}: WCS 500\n"
    assert captured.out.count("nowa wersja") == 2
    assert "Legenda" not in captured.out and "Statystyki" not in captured.out
    assert not (tmp_path / "out" / "hsg").exists()
