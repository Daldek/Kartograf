"""
Land cover result naming and sidecar parameters (U3).

Every parameter that changes the content of a land cover result is part of
the file name and of the sidecar ``request``: two downloads with different
parameters never share one file (before 0.7.0 ``--property sand`` silently
overwrote the ``--property clay`` result for the same bbox).
"""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from kartograf.core.sheet_parser import BBox
from kartograf.landcover.manager import LandCoverManager
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.providers.soilgrids import SoilGridsProvider

BBOX = BBox(770000, 509000, 772000, 511000, "EPSG:2180")
BBOX_ARG = "770000,509000,772000,511000"
COORDS = "770000_509000_772000_511000"


def _tiny_geotiff(nodata: float | None, value: int) -> bytes:
    """A 2x2 Int16 GeoTIFF (EPSG:4326) with the given nodata and fill value."""
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            width=2,
            height=2,
            count=1,
            dtype="int16",
            crs="EPSG:4326",
            transform=from_origin(19.0, 50.0, 0.01, 0.01),
            nodata=nodata,
        ) as ds:
            ds.write(np.full((1, 2, 2), value, dtype="int16"))
        return bytes(mem.read())


def _fake_download_to(payload: bytes):
    """Stand-in for ``transport.http.download_to``: writes ``payload`` to the target."""

    def _download(session, url, path, **kwargs):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    return _download


def _sidecar(path: Path) -> dict:
    return json.loads((path.parent / f"{path.name}.meta.json").read_text())


def _first_pixel(path: Path) -> int:
    with rasterio.open(path) as ds:
        return int(ds.read(1)[0, 0])


class TestSoilGridsOutputParams:
    """SoilGrids: property/depth/stat in the file name and in the sidecar."""

    def _download(self, tmp_path, value: int = 1, nodata=-32768, **kwargs) -> Path:
        manager = LandCoverManager(output_dir=tmp_path, provider=SoilGridsProvider())
        with patch(
            "kartograf.providers.soilgrids.download_to",
            side_effect=_fake_download_to(_tiny_geotiff(nodata, value)),
        ):
            return manager.download(bbox=BBOX, **kwargs)

    def test_defaults_are_in_the_name(self, tmp_path):
        path = self._download(tmp_path)
        assert path == tmp_path / f"soilgrids_soc_0-5cm_mean_bbox_{COORDS}.tif"

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            ({"property": "clay"}, {"property": "sand"}),
            ({"depth": "0-5cm"}, {"depth": "5-15cm"}),
            ({"stat": "mean"}, {"stat": "Q0.05"}),
        ],
    )
    def test_different_params_keep_both_files(self, tmp_path, first, second):
        a = self._download(tmp_path, value=11, **first)
        b = self._download(tmp_path, value=22, **second)
        assert a != b
        assert _first_pixel(a) == 11
        assert _first_pixel(b) == 22

    def test_quantile_stat_keeps_tif_extension(self, tmp_path):
        path = self._download(tmp_path, property="clay", stat="Q0.95")
        assert path.name == f"soilgrids_clay_0-5cm_Q0.95_bbox_{COORDS}.tif"

    def test_same_params_same_path(self, tmp_path):
        a = self._download(tmp_path, property="clay", depth="15-30cm")
        b = self._download(tmp_path, property="clay", depth="15-30cm")
        assert a == b
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            a.name,
            f"{a.name}.meta.json",
        ]

    def test_sidecar_records_params_and_nodata(self, tmp_path):
        path = self._download(tmp_path, property="clay", depth="5-15cm", stat="Q0.5")
        meta = _sidecar(path)
        assert meta["request"] == {
            "bbox": [770000.0, 509000.0, 772000.0, 511000.0],
            "bbox_crs": "EPSG:2180",
            "property": "clay",
            "depth": "5-15cm",
            "stat": "Q0.5",
        }
        assert meta["nodata"] == -32768

    def test_sidecar_records_defaults(self, tmp_path):
        request = _sidecar(self._download(tmp_path))["request"]
        assert (request["property"], request["depth"], request["stat"]) == (
            "soc",
            "0-5cm",
            "mean",
        )

    def test_file_without_nodata_gives_null(self, tmp_path):
        assert _sidecar(self._download(tmp_path, nodata=None))["nodata"] is None

    def test_godlo_mode(self, tmp_path):
        manager = LandCoverManager(output_dir=tmp_path, provider=SoilGridsProvider())
        with patch(
            "kartograf.providers.soilgrids.download_to",
            side_effect=_fake_download_to(_tiny_geotiff(-32768, 1)),
        ):
            path = manager.download_by_godlo("N-34-130-D", property="silt")
        assert path.name == "soilgrids_silt_0-5cm_mean_godlo_N-34-130-D.tif"
        assert _sidecar(path)["request"] == {
            "sheet": "N-34-130-D",
            "property": "silt",
            "depth": "0-5cm",
            "stat": "mean",
        }

    def test_download_and_download_by_bbox_same_path(self, tmp_path):
        manager = LandCoverManager(output_dir=tmp_path, provider=SoilGridsProvider())
        with patch(
            "kartograf.providers.soilgrids.download_to",
            side_effect=_fake_download_to(_tiny_geotiff(None, 1)),
        ):
            a = manager.download(bbox=BBOX, property="clay")
            b = manager.download_by_bbox(BBOX, property="clay")
        assert a == b


class TestCorineOutputParams:
    """CORINE: year in the file name and in the sidecar."""

    def _download(self, tmp_path, godlo: str | None = None, **kwargs) -> Path:
        manager = LandCoverManager(
            output_dir=tmp_path, provider=CorineProvider(use_proxy=False)
        )
        with patch(
            "kartograf.providers.corine.download_to",
            side_effect=_fake_download_to(b"\x89PNG fake"),
        ):
            if godlo is not None:
                return manager.download(godlo=godlo, **kwargs)
            return manager.download(bbox=BBOX, **kwargs)

    def test_different_years_keep_both_files(self, tmp_path):
        a = self._download(tmp_path, year=2018)
        b = self._download(tmp_path, year=2012)
        assert a.name == f"corine_2018_bbox_{COORDS}.png"
        assert b.name == f"corine_2012_bbox_{COORDS}.png"
        assert a.exists() and b.exists()

    def test_default_year_in_name_and_sidecar(self, tmp_path):
        path = self._download(tmp_path)
        assert path.name == f"corine_2018_bbox_{COORDS}.png"
        assert _sidecar(path)["request"]["year"] == 2018

    def test_godlo_mode(self, tmp_path):
        path = self._download(tmp_path, godlo="N-34-130-D", year=2006)
        assert path.name == "corine_2006_godlo_N-34-130-D.png"
        assert _sidecar(path)["request"] == {"sheet": "N-34-130-D", "year": 2006}

    def test_same_year_same_path(self, tmp_path):
        assert self._download(tmp_path, year=2000) == self._download(
            tmp_path, year=2000
        )

    def test_godlo_leading_zeros_canonical(self, tmp_path):
        """A7: land cover names and sidecars use the canonical godlo."""
        path = self._download(tmp_path, godlo="M-33-036-A", year=2006)
        assert path.name == "corine_2006_godlo_M-33-36-A.png"
        assert _sidecar(path)["request"]["sheet"] == "M-33-36-A"

    def test_clms_geotiff_name_and_nodata_from_file(self, tmp_path):
        provider = CorineProvider(use_proxy=False)
        manager = LandCoverManager(output_dir=tmp_path, provider=provider)

        def _fake(bbox, out, **kwargs):
            target = out.with_suffix(".tif")
            target.write_bytes(_tiny_geotiff(-128, 3))
            return target

        with patch.object(provider, "download_by_bbox", side_effect=_fake):
            path = manager.download(bbox=BBOX, year=2012)
        assert path.name == f"corine_2012_bbox_{COORDS}.tif"
        meta = _sidecar(path)
        assert meta["nodata"] == -128
        assert meta["request"]["year"] == 2012


class TestBdot10kOutputParams:
    """BDOT10k: the format already differs by extension; the sidecar records it."""

    def test_format_in_sidecar(self, tmp_path):
        provider = Bdot10kProvider()
        manager = LandCoverManager(output_dir=tmp_path, provider=provider)

        def _fake(teryt, out, timeout=None, format="GPKG", **kwargs):
            target = out.with_suffix(".zip") if format == "SHP" else out
            target.write_bytes(b"x")
            return target

        with patch.object(provider, "download_by_admin_unit", side_effect=_fake):
            gpkg = manager.download(teryt="1465")
            shp = manager.download(teryt="1465", format="SHP")
        assert gpkg.name == "bdot10k_teryt_1465.gpkg"
        assert shp.name == "bdot10k_teryt_1465.zip"
        assert _sidecar(gpkg)["request"] == {"teryt": "1465", "format": "GPKG"}
        assert _sidecar(shp)["request"] == {"teryt": "1465", "format": "SHP"}


class TestLandCoverCliOutputParams:
    """``kartograf landcover download`` end to end through ``main``."""

    def _soilgrids(self, tmp_path, *extra: str, value: int = 1) -> int:
        from kartograf.cli.commands import main

        with patch(
            "kartograf.providers.soilgrids.download_to",
            side_effect=_fake_download_to(_tiny_geotiff(-32768, value)),
        ):
            return main(
                [
                    "landcover",
                    "download",
                    "--source",
                    "soilgrids",
                    "--bbox",
                    BBOX_ARG,
                    "-o",
                    str(tmp_path / "out"),
                    *extra,
                ]
            )

    def test_clay_then_sand_two_files(self, tmp_path, capsys):
        assert self._soilgrids(tmp_path, "--property", "clay", value=11) == 0
        assert self._soilgrids(tmp_path, "--property", "sand", value=22) == 0
        out = tmp_path / "out"
        clay = out / f"soilgrids_clay_0-5cm_mean_bbox_{COORDS}.tif"
        sand = out / f"soilgrids_sand_0-5cm_mean_bbox_{COORDS}.tif"
        assert _first_pixel(clay) == 11
        assert _first_pixel(sand) == 22
        assert _sidecar(clay)["request"]["property"] == "clay"
        assert _sidecar(sand)["request"]["property"] == "sand"
        assert f"Downloaded to: {sand}" in capsys.readouterr().out

    def test_depth_and_stat_from_cli(self, tmp_path):
        assert self._soilgrids(tmp_path, "--depth", "30-60cm", "--stat", "Q0.05") == 0
        path = tmp_path / "out" / f"soilgrids_soc_30-60cm_Q0.05_bbox_{COORDS}.tif"
        request = _sidecar(path)["request"]
        assert (request["depth"], request["stat"]) == ("30-60cm", "Q0.05")

    def test_corine_years_two_files(self, tmp_path, monkeypatch):
        from kartograf.cli.commands import main

        monkeypatch.delenv("CLMS_CREDENTIALS", raising=False)
        with (
            patch(
                "kartograf.providers.corine.download_to",
                side_effect=_fake_download_to(b"\x89PNG fake"),
            ),
            patch.object(CorineProvider, "has_clms_token", new=False),
        ):
            for year in ("2018", "2012"):
                rc = main(
                    [
                        "landcover",
                        "download",
                        "--source",
                        "corine",
                        "--bbox",
                        BBOX_ARG,
                        "--year",
                        year,
                        "-o",
                        str(tmp_path / "out"),
                    ]
                )
                assert rc == 0
        assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
            f"corine_2012_bbox_{COORDS}.png",
            f"corine_2012_bbox_{COORDS}.png.meta.json",
            f"corine_2018_bbox_{COORDS}.png",
            f"corine_2018_bbox_{COORDS}.png.meta.json",
        ]
