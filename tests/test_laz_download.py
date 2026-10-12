"""
LAZ tile download as a library API (review-1 D17, review-2 N15).

``kartograf.download.laz``: the thread pool, the tile sidecar and tile
failures live in the library; the CLI only prints. Offline: WFS from raw XML
recorded for exactly the queried window, file download replaced by writing a
few bytes.
"""

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from kartograf import download_laz_area, run_laz_download
from kartograf.core.sheet_parser import BBox
from kartograf.download.laz import LazDownloadResult
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError, YearRangeError
from kartograf.providers.pl.gugik_laz import (
    GugikLazProvider,
    LazTile,
    LazTileSelection,
    SupersededLazTile,
)

LAZ_FIXTURES = Path(__file__).parent / "fixtures" / "gugik_laz"
REAL_LAZ = LAZ_FIXTURES / "real_2026_10_06"
W2_AREA = BBox(637400, 487000, 637450, 487050, "EPSG:2180")
PARENT = {"bbox": [637400, 487000, 637450, 487050], "bbox_crs": "EPSG:2180",
          "countries": ["PL"]}  # fmt: skip
# recorded area -> (directory, file prefix, query window N,E in EPSG:2180)
_WINDOWS = {
    # the 2026-10-06 round (C13): W2_AREA
    "w2": (REAL_LAZ, "w2", (487000, 637400, 487050, 637450)),
    # 2026-10-11: test_parent_request_keeps_bbox_in_given_crs (EPSG:4326 bbox)
    "wgs": (
        LAZ_FIXTURES / "real_2026_10_11",
        "wgs",
        (487009.9919, 637409.2163, 487039.9756, 637440.8126),
    ),
    # 2026-10-11: sheet N-34-139-A-c-1-1 (sheet mode)
    "sheet": (
        LAZ_FIXTURES / "real_2026_10_11",
        "sheet",
        (486674.8545, 636487.0308, 489050.3833, 638684.3633),
    ),
}


def wfs_session(area: str = "w2") -> MagicMock:
    """GetCapabilities/GetFeature from raw XML; .laz files -> a few bytes.

    GetFeature must ask for the window ``area`` was recorded for: the bodies
    are what the service answered for that window, not for any other.
    """
    directory, prefix, window = _WINDOWS[area]
    session = MagicMock()

    def get(url, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        if url.endswith(".laz"):
            response.iter_content = MagicMock(return_value=[b"LASF", b"\x01"])
            return response
        query = parse_qs(urlparse(url).query)
        vcrs = "KRON86" if "LidarKRON86" in url else "EVRF2007"
        if query["REQUEST"][0] == "GetCapabilities":
            path = REAL_LAZ / f"caps_{vcrs}.xml"
        else:
            bbox = [float(v) for v in query["BBOX"][0].split(",")[:4]]
            assert bbox == pytest.approx(window, abs=1e-3)
            path = directory / f"{prefix}_{vcrs}_{query['TYPENAMES'][0][-4:]}.xml"
        response.text = path.read_text(encoding="utf-8")
        return response

    session.get = MagicMock(side_effect=get)
    return session


def downloaded_urls(session: MagicMock) -> list[str]:
    return [c.args[0] for c in session.get.call_args_list if c.args[0].endswith(".laz")]


def _tile(sheet: str, crs: str = "PL-2000:S6", year: int = 2024) -> LazTile:
    return LazTile(
        sheet=sheet,
        url=f"https://opendata.geoportal.gov.pl/x/81121_1_{sheet}.laz",
        year=year,
        density=25,
        crs=crs,
        min_x=530500,
        min_y=382500,
        max_x=531000,
        max_y=383000,
    )


class FakeProvider:
    """Provider whose ``download`` writes bytes; selected sheet codes fail."""

    descriptor_key = "pl.gugik.laz"

    def __init__(self, vertical_crs="EVRF2007", failing=()) -> None:
        self.vertical_crs = vertical_crs
        self.failing = set(failing)
        self.calls: list[str] = []
        self.threads: set[int | None] = set()
        self._lock = threading.Lock()

    def download(self, url, target, **kwargs):
        with self._lock:
            self.calls.append(url)
            self.threads.add(threading.current_thread().ident)
        if any(g in url for g in self.failing):
            raise DownloadError(f"HTTP 503 dla {url}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"LASF")
        return target


BBOX = BBox(530000, 382000, 533000, 386000, "EPSG:2180")


def _selection(*tiles, superseded=()):
    return LazTileSelection(tiles=tuple(tiles), superseded=tuple(superseded))


def _sidecar(path: Path) -> dict:
    return json.loads(path.with_name(path.name + ".meta.json").read_text("utf-8"))


# =============================================================================
# run_laz_download
# =============================================================================


class TestRunLazDownload:
    def test_tiles_land_in_storage_with_sidecar(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        provider = FakeProvider()
        result = run_laz_download(
            _selection(tile),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            year=2024,
            min_density=12,
        )
        expected = FileStorage(
            tmp_path, product="laz", vertical_crs="EVRF2007"
        ).get_raw_path(tile.sheet, tile.filename, system="2000")
        assert result.downloaded == (expected,)
        assert expected.parts[-10:-8] == ("laz", "pl_2000_evrf2007")
        meta = _sidecar(expected)
        assert meta["dataset"] == "pl.gugik.laz"
        assert meta["horizontal_crs"] == "EPSG:2177"  # PL-2000:S6
        assert meta["request"]["bbox"] == [530000, 382000, 533000, 386000]
        assert meta["request"]["year"] == 2024  # wave B (E16) preserved
        assert meta["request"]["min_density"] == 12
        # ADR-031: English keys only (tile_sheet / year / nominal_density)
        assert {k: meta["extra"][k] for k in ("tile_sheet", "year")} == {
            "tile_sheet": tile.sheet,
            "year": tile.year,
        }
        assert meta["extra"]["nominal_density"] == tile.density
        assert not {"godlo_kafla", "rok", "gestosc"} & set(meta["extra"])
        assert "parent_request" not in meta["extra"]  # not given

    def test_parent_request_written_to_every_tile_sidecar(self, tmp_path):
        """N15: ADR-023 (f).1 — LAZ tiles from an area carry the grouping key."""
        tiles = [_tile("N-33-131-B-a-1-1-4"), _tile("M-34-1-A-a-1-1-1", "PL-1992")]
        result = run_laz_download(
            _selection(*tiles),
            provider=FakeProvider(),
            bbox=BBOX,
            output_dir=tmp_path,
            parent_request=PARENT,
        )
        assert len(result.downloaded) == 2
        for path in result.downloaded:
            assert _sidecar(path)["extra"]["parent_request"] == PARENT

    def test_sidecar_failure_does_not_abort_download(self, tmp_path, caplog):
        """Sidecar through the shared ``emit_sidecar``: a metadata build failure is
        a log warning, the tile stays downloaded (D7, best-effort policy)."""
        from unittest.mock import patch

        tile = _tile("N-33-131-B-a-1-1-4")
        with (
            patch(
                "kartograf.sources.sidecar.build_metadata",
                side_effect=RuntimeError("zepsuty deskryptor"),
            ),
            caplog.at_level("WARNING", logger="kartograf.sources.sidecar"),
        ):
            result = run_laz_download(
                _selection(tile),
                provider=FakeProvider(),
                bbox=BBOX,
                output_dir=tmp_path,
            )
        (path,) = result.downloaded
        assert path.exists()
        assert not path.with_name(path.name + ".meta.json").exists()
        assert "zepsuty deskryptor" in caplog.text

    def test_provider_without_descriptor_key_still_gets_laz_sidecar(self, tmp_path):
        """A provider without ``descriptor_key`` (str) - a sidecar with the key
        ``pl.gugik.laz``, not silence (``emit_sidecar`` itself would skip it)."""
        provider = FakeProvider()
        provider.descriptor_key = None
        result = run_laz_download(
            _selection(_tile("N-33-131-B-a-1-1-4")),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
        )
        assert _sidecar(result.downloaded[0])["dataset"] == "pl.gugik.laz"

    def test_failures_are_collected_not_raised(self, tmp_path):
        tiles = [_tile(f"N-33-131-B-a-1-1-{i}") for i in range(1, 5)]
        provider = FakeProvider(failing={"1-1-2", "1-1-4"})
        result = run_laz_download(
            _selection(*tiles), provider=provider, bbox=BBOX, output_dir=tmp_path
        )
        assert len(result.downloaded) == 2
        assert [f.tile.sheet for f in result.failed] == [
            "N-33-131-B-a-1-1-2",
            "N-33-131-B-a-1-1-4",
        ]
        assert all(isinstance(f.error, DownloadError) for f in result.failed)
        assert not result.ok
        # a failed tile leaves no sidecar
        assert len(list(tmp_path.rglob("*.meta.json"))) == 2

    def test_existing_tiles_are_skipped_unless_force(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        provider = FakeProvider()
        first = run_laz_download(
            _selection(tile), provider=provider, bbox=BBOX, output_dir=tmp_path
        )
        again = run_laz_download(
            _selection(tile), provider=provider, bbox=BBOX, output_dir=tmp_path
        )
        assert again.skipped == first.downloaded
        assert again.downloaded == ()
        assert len(provider.calls) == 1
        forced = run_laz_download(
            _selection(tile),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            force=True,
        )
        assert forced.downloaded == first.downloaded
        assert len(provider.calls) == 2

    def test_superseded_tiles_pass_through(self, tmp_path):
        kept = _tile("N-34-139-A-c-1-1-3-4", "PL-1992", 2025)
        old = SupersededLazTile(tile=_tile("7.173.21.06.2", "PL-2000:S7", 2022),
                                covered_by=(kept,))  # fmt: skip
        result = run_laz_download(
            _selection(kept, superseded=[old]),
            provider=FakeProvider(),
            bbox=BBOX,
            output_dir=tmp_path,
        )
        assert result.superseded == (old,)
        assert result.tiles == (kept,)

    def test_parallel_workers_and_progress(self, tmp_path: Path) -> None:
        tiles = [_tile(f"N-33-131-B-a-1-1-{i}") for i in range(1, 7)]
        progress: list[tuple[int, int]] = []
        result = run_laz_download(
            _selection(*tiles),
            provider=FakeProvider(),
            bbox=BBOX,
            output_dir=tmp_path,
            max_workers=3,
            on_progress=lambda done, total: progress.append((done, total)),
        )
        assert len(result.downloaded) == 6
        assert progress == [(i, 6) for i in range(1, 7)]

    def test_kron86_segment_follows_provider(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        result = run_laz_download(
            _selection(tile),
            provider=FakeProvider(vertical_crs="KRON86"),
            bbox=BBOX,
            output_dir=tmp_path,
        )
        (path,) = result.downloaded
        assert "pl_2000_kron86" in path.parts
        assert _sidecar(path)["vertical_crs"] == "EPSG:9650"


# =============================================================================
# download_laz_area (end-to-end on the raw WFS w2)
# =============================================================================


class TestDownloadLazArea:
    def test_w2_downloads_only_the_newest_tile(self, tmp_path):
        session = wfs_session()
        result = download_laz_area(
            W2_AREA,
            output_dir=tmp_path,
            provider=GugikLazProvider(session=session),
            parent_request=PARENT,
        )
        assert isinstance(result, LazDownloadResult)
        assert [t.sheet for t in result.tiles] == ["N-34-139-A-c-1-1-3-4"]
        assert downloaded_urls(session) == [
            "https://opendata.geoportal.gov.pl/NumDaneWys/DanePomiaroweLAZ/"
            "83230/83230_1743191_N-34-139-A-c-1-1-3-4.laz"
        ]
        (path,) = result.downloaded
        assert path.parts[-11:-9] == ("laz", "pl_1992_evrf2007")
        assert sorted((s.tile.sheet, s.tile.year) for s in result.superseded) == [
            ("7.173.21.06.2", 2022),
            ("N-34-139-A-c-1-1-3-4", 2023),
        ]
        meta = _sidecar(path)
        assert meta["extra"]["year"] == 2025
        assert meta["extra"]["parent_request"] == PARENT
        assert not list((tmp_path / "laz").glob("pl_2000_*"))

    def test_year_downloads_that_year_only(self, tmp_path):
        session = wfs_session()
        result = download_laz_area(
            W2_AREA,
            output_dir=tmp_path,
            year=2022,
            provider=GugikLazProvider(session=session),
        )
        assert [(t.sheet, t.year) for t in result.tiles] == [("7.173.21.06.2", 2022)]
        assert _sidecar(result.downloaded[0])["request"]["year"] == 2022

    def test_year_with_empty_service_layer_conflicts_before_download(self, tmp_path):
        session = wfs_session()
        with pytest.raises(YearRangeError) as caught:
            download_laz_area(
                W2_AREA,
                output_dir=tmp_path,
                year=2026,  # the layer exists, but no tiles here
                provider=GugikLazProvider(session=session),
            )
        assert caught.value.sheets == {"N-34-139-A-c-1-1-3-4": (2022, 2023, 2025)}
        assert downloaded_urls(session) == []
        assert list(tmp_path.iterdir()) == []

    def test_vertical_crs_mismatch_with_provider_is_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="KRON86"):
            download_laz_area(
                W2_AREA,
                output_dir=tmp_path,
                vertical_crs="KRON86",
                provider=GugikLazProvider(session=wfs_session()),
            )


# =============================================================================
# CLI: a thin layer (`kartograf download --product laz`)
# =============================================================================


def _cli(tmp_path, *args, area: str = "w2"):
    from unittest.mock import patch

    from kartograf.cli.commands import main

    session = wfs_session(area)
    with patch("kartograf.transport.http.make_gugik_session", return_value=session):
        rc = main(["download", *args, "--product", "laz", "-o", str(tmp_path), "-q"])
    return rc, session


class TestCliOnRealWfs:
    W2 = ["--bbox", "637400,487000,637450,487050", "--bbox-crs", "EPSG:2180"]

    def test_w2_downloads_newest_and_reports_superseded(self, tmp_path, capsys):
        rc, session = _cli(tmp_path, *self.W2, "--country", "pl")
        err = capsys.readouterr().err
        assert rc == 0
        assert [u.rsplit("/", 1)[-1] for u in downloaded_urls(session)] == [
            "83230_1743191_N-34-139-A-c-1-1-3-4.laz"
        ]
        # Info on stderr despite -q; full list of skipped tiles with the covering tile
        assert "Info: pominieto 2 kafli LAZ" in err
        assert (
            "7.173.21.06.2 (2022, PL-2000:S7): pokryty przez "
            "N-34-139-A-c-1-1-3-4 (2025, PL-1992)"
        ) in err
        assert "N-34-139-A-c-1-1-3-4 (2023, PL-1992): pokryty przez" in err
        assert not (tmp_path / "laz" / "pl_2000_evrf2007").exists()

    def test_bbox_mode_sidecar_has_parent_request(self, tmp_path):
        rc, _ = _cli(tmp_path, *self.W2, "--country", "pl")
        assert rc == 0
        (sidecar,) = tmp_path.rglob("*.meta.json")
        extra = json.loads(sidecar.read_text("utf-8"))["extra"]
        assert extra["parent_request"] == {
            "bbox": [637400.0, 487000.0, 637450.0, 487050.0],
            "bbox_crs": "EPSG:2180",
            "countries": ["PL"],
        }

    def test_parent_request_keeps_bbox_in_given_crs(self, tmp_path):
        """Like the NMT paths: parent_request carries the GIVEN bbox, not EPSG:2180."""
        from pyproj import Transformer

        to_wgs = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
        lon0, lat0 = to_wgs.transform(637410, 487010)
        lon1, lat1 = to_wgs.transform(637440, 487040)
        bbox = f"{lon0:.6f},{lat0:.6f},{lon1:.6f},{lat1:.6f}"
        rc, _ = _cli(tmp_path, "--bbox", bbox, "--bbox-crs", "EPSG:4326", area="wgs")
        assert rc == 0
        (sidecar,) = tmp_path.rglob("*.meta.json")
        parent = json.loads(sidecar.read_text("utf-8"))["extra"]["parent_request"]
        assert parent["bbox_crs"] == "EPSG:4326"
        assert parent["bbox"] == [float(v) for v in bbox.split(",")]
        assert parent["countries"] == ["PL"]

    def test_sheet_mode_has_no_parent_request(self, tmp_path):
        rc, session = _cli(tmp_path, "--sheet", "N-34-139-A-c-1-1", area="sheet")
        assert rc == 0
        sidecars = list(tmp_path.rglob("*.meta.json"))
        assert len(sidecars) == len(downloaded_urls(session)) > 1
        for sidecar in sidecars:
            extra = json.loads(sidecar.read_text("utf-8"))["extra"]
            assert "parent_request" not in extra

    def test_year_downloads_older_system_without_info(self, tmp_path, capsys):
        rc, session = _cli(tmp_path, *self.W2, "--country", "pl", "--year", "2022")
        assert rc == 0
        assert [u.rsplit("/", 1)[-1] for u in downloaded_urls(session)] == [
            "77941_1396678_7.173.21.06.2.laz"
        ]
        assert "Info: pominieto" not in capsys.readouterr().err
