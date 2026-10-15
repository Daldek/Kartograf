"""
LAZ tile download as a library API (review-1 D17, review-2 N15).

``kartograf.download.laz``: the thread pool, the tile sidecar and tile
failures live in the library; the CLI only prints. Offline: WFS from raw XML
recorded for exactly the queried window, file download replaced by writing a
few bytes.
"""

import json
import threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.download.area import bbox_to_2180
from kartograf.download.laz import (
    NO_TILES_MESSAGE,
    LazDownloadResult,
    _check_selection,
    _run_laz_download,
    check_laz_area,
    download_laz_area,
    laz_slot,
    laz_version_ref,
)
from kartograf.download.plan import UpdatePlan
from kartograf.download.storage import FileStorage
from kartograf.exceptions import (
    DownloadError,
    NoCoverageError,
    ValidationError,
    YearRangeError,
)
from kartograf.notices import LAZ_SUPERSEDED, Notice
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
    def test_laz_tile_lands_as_version_with_link(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        provider = FakeProvider()
        result = _run_laz_download(
            _selection(tile),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            year=2024,
            min_density=12,
        )
        expected = FileStorage(
            tmp_path, product="laz", vertical_crs="EVRF2007", resolution="1m"
        ).get_raw_path(tile.sheet, tile.filename, system="2000")
        (file,) = result.files
        assert file.status == "new" and file.path == expected
        assert file.label == "2024_81121"
        assert file.version_path == (
            tmp_path
            / "laz"
            / "pl_2000_evrf2007"
            / "versions"
            / "N-33"
            / "131"
            / "B"
            / "a"
            / "1"
            / "1"
            / "4"
            / f"2024_81121_{file.sha256[:8]}"
            / tile.filename
        )
        assert file.version_path.read_bytes() == b"LASF"
        assert expected.stat().st_ino == file.version_path.stat().st_ino
        assert expected.parts[-10:-8] == ("laz", "pl_2000_evrf2007")
        meta = _sidecar(file.version_path)
        assert meta["sha256"] == file.sha256
        assert meta["extra"]["version"] == {
            "label": "2024_81121",
            "label_source": "campaign",
        }
        assert "link" not in meta["extra"]
        assert _sidecar(expected)["extra"]["link"] == "hardlink"
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
        result = _run_laz_download(
            _selection(*tiles),
            provider=FakeProvider(),
            bbox=BBOX,
            output_dir=tmp_path,
            parent_request=PARENT,
        )
        assert len(result.files) == 2
        for file in result.files:
            assert _sidecar(file.path)["extra"]["parent_request"] == PARENT

    def test_sidecar_failure_rolls_back_version(self, tmp_path):
        """Mandatory version metadata failure does not leave a usable file."""
        from unittest.mock import patch

        tile = _tile("N-33-131-B-a-1-1-4")
        with patch(
            "kartograf.sources.sidecar.build_metadata",
            side_effect=RuntimeError("zepsuty deskryptor"),
        ):
            result = _run_laz_download(
                _selection(tile),
                provider=FakeProvider(),
                bbox=BBOX,
                output_dir=tmp_path,
            )
        assert not result.ok and not result.files
        assert "zepsuty deskryptor" in str(result.failed[0].error)
        storage = FileStorage(
            tmp_path, product="laz", vertical_crs="EVRF2007", resolution=None
        )
        slot = laz_slot(storage, tile)
        assert not slot.std.exists()
        assert not list(slot.versions_root.glob("*/" + tile.filename))

    def test_provider_without_descriptor_key_still_gets_laz_sidecar(self, tmp_path):
        """A provider without ``descriptor_key`` (str) - a sidecar with the key
        ``pl.gugik.laz``, not silence (``emit_sidecar`` itself would skip it)."""
        provider = FakeProvider()
        provider.descriptor_key = None
        result = _run_laz_download(
            _selection(_tile("N-33-131-B-a-1-1-4")),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
        )
        assert _sidecar(result.files[0].version_path)["dataset"] == "pl.gugik.laz"

    def test_failures_are_collected_not_raised(self, tmp_path):
        tiles = [_tile(f"N-33-131-B-a-1-1-{i}") for i in range(1, 5)]
        provider = FakeProvider(failing={"1-1-2", "1-1-4"})
        result = _run_laz_download(
            _selection(*tiles), provider=provider, bbox=BBOX, output_dir=tmp_path
        )
        assert len(result.files) == 2
        assert [f.tile.sheet for f in result.failed] == [
            "N-33-131-B-a-1-1-2",
            "N-33-131-B-a-1-1-4",
        ]
        assert all(isinstance(f.error, DownloadError) for f in result.failed)
        assert not result.ok
        # A failed tile leaves no committed version or sidecar.
        assert len(list(tmp_path.rglob("versions/**/*.meta.json"))) == 2

    def test_laz_force_same_content_is_unchanged(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        provider = FakeProvider()
        first = _run_laz_download(
            _selection(tile), provider=provider, bbox=BBOX, output_dir=tmp_path
        )
        forced = _run_laz_download(
            _selection(tile),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            update="force",
        )
        assert [file.status for file in (first.files[0], forced.files[0])] == [
            "new",
            "unchanged",
        ]
        assert forced.files[0].version_path == first.files[0].version_path
        assert len(provider.calls) == 2
        assert len(list(tmp_path.rglob("versions/**/*.laz.meta.json"))) == 1

    def test_laz_force_new_content_is_new_version(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        provider = FakeProvider()
        original = _run_laz_download(
            _selection(tile), provider=provider, bbox=BBOX, output_dir=tmp_path
        ).files[0]

        def revised(url, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"LASF updated")
            return target

        provider.download = revised
        changed = _run_laz_download(
            _selection(tile),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            update="force",
        ).files[0]
        assert changed.status == "new"
        assert changed.version_path != original.version_path
        assert changed.path.read_bytes() == b"LASF updated"
        assert original.version_path.read_bytes() == b"LASF"
        assert changed.path.stat().st_ino == changed.version_path.stat().st_ino

    def test_laz_default_keeps_local_tile_and_fetches_new_flight(self, tmp_path):
        first_tile = _tile("N-33-131-B-a-1-1-4")
        second_tile = replace(
            first_tile,
            url=f"https://opendata.geoportal.gov.pl/x/93455_2_{first_tile.sheet}.laz",
            year=2025,
            date="2025-08-12",
        )
        provider = FakeProvider()
        previous = _run_laz_download(
            _selection(first_tile), provider=provider, bbox=BBOX, output_dir=tmp_path
        ).files[0]
        current = _run_laz_download(
            _selection(first_tile, second_tile),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
        )
        assert [file.status for file in current.files] == ["local", "new"]
        assert current.files[0].version_path == previous.version_path
        assert current.files[1].label == "2025-08-12_93455"
        assert provider.calls == [first_tile.url, second_tile.url]
        assert current.files[0].path.exists() and current.files[1].path.exists()

    def test_check_laz_never_downloads(self, tmp_path):
        current, missing = (_tile(f"N-33-131-B-a-1-1-{i}") for i in (1, 2))
        provider = FakeProvider()
        _run_laz_download(
            _selection(current), provider=provider, bbox=BBOX, output_dir=tmp_path
        )
        provider.calls.clear()
        plan = _check_selection(
            _selection(current, missing), provider=provider, output_dir=tmp_path
        )
        assert plan.store == str(tmp_path.resolve())
        assert [(item.track, item.unit, item.status) for item in plan.items] == [
            ("laz_tile", current.sheet, "current"),
            ("laz_tile", missing.sheet, "missing"),
        ]
        assert plan.items[1].available_label == laz_version_ref(missing).label
        assert plan.items[1].available_signal == {
            "url": missing.url,
            "year": missing.year,
            "date": missing.date,
        }
        assert provider.calls == []
        assert not laz_slot(
            FileStorage(
                tmp_path, product="laz", resolution=None, vertical_crs="EVRF2007"
            ),
            missing,
        ).std.exists()

    def test_laz_upgrade_plan_stale_tile(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        provider = FakeProvider()
        plan = _check_selection(
            _selection(tile), provider=provider, output_dir=tmp_path
        )
        changed = replace(tile, url=tile.url.replace("81121", "93455"))
        outcome = _run_laz_download(
            _selection(changed),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            update="upgrade",
            plan=plan,
        )
        assert outcome.files == () and outcome.stale == plan.items
        assert provider.calls == []
        # A changed index record must also be stale even if the file name stays.
        changed_record = replace(tile, date="2025-08-12", year=2025)
        stale_record = _run_laz_download(
            _selection(changed_record),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            update="upgrade",
            plan=plan,
        )
        assert stale_record.files == () and stale_record.stale == plan.items
        removed = _run_laz_download(
            _selection(),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            update="upgrade",
            plan=plan,
        )
        assert removed.files == () and removed.stale == plan.items
        assert provider.calls == []

    def test_laz_upgrade_plan_skips_removed_items(self, tmp_path):
        first, removed = (_tile(f"N-33-131-B-a-1-1-{i}") for i in (1, 2))
        provider = FakeProvider()
        checked = _check_selection(
            _selection(first, removed), provider=provider, output_dir=tmp_path
        )
        plan = UpdatePlan(
            store=checked.store,
            checked_at=checked.checked_at,
            kartograf_version=checked.kartograf_version,
            items=checked.items[:1],
        )
        outcome = _run_laz_download(
            _selection(first, removed),
            provider=provider,
            bbox=BBOX,
            output_dir=tmp_path,
            update="upgrade",
            plan=plan,
        )
        assert [file.status for file in outcome.files] == ["new"]
        assert provider.calls == [first.url]
        assert outcome.stale == ()
        assert not laz_slot(
            FileStorage(
                tmp_path, product="laz", resolution=None, vertical_crs="EVRF2007"
            ),
            removed,
        ).std.exists()

    def test_laz_legacy_plain_file_replaced_by_link(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        storage = FileStorage(
            tmp_path, product="laz", resolution=None, vertical_crs="EVRF2007"
        )
        slot = laz_slot(storage, tile)
        slot.std.parent.mkdir(parents=True)
        slot.std.write_bytes(b"old plain tile")
        old_sidecar = slot.std.with_name(f"{slot.name}.meta.json")
        old_sidecar.write_text('{"schema":"kartograf-meta/1","extra":{}}')
        provider = FakeProvider()
        (file,) = _run_laz_download(
            _selection(tile), provider=provider, bbox=BBOX, output_dir=tmp_path
        ).files
        assert provider.calls == [tile.url] and file.status == "new"
        assert file.path.read_bytes() == b"LASF"
        assert file.path.stat().st_ino == file.version_path.stat().st_ino
        assert _sidecar(slot.std)["extra"]["link"] == "hardlink"

    def test_laz_update_check_rejected_without_network(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        provider = FakeProvider()
        with pytest.raises(ValidationError, match="check"):
            _run_laz_download(
                _selection(tile),
                provider=provider,
                bbox=BBOX,
                output_dir=tmp_path,
                update="check",
            )
        assert provider.calls == []

    def test_superseded_tiles_pass_through(self, tmp_path):
        kept = _tile("N-34-139-A-c-1-1-3-4", "PL-1992", 2025)
        old = SupersededLazTile(tile=_tile("7.173.21.06.2", "PL-2000:S7", 2022),
                                covered_by=(kept,))  # fmt: skip
        result = _run_laz_download(
            _selection(kept, superseded=[old]),
            provider=FakeProvider(),
            bbox=BBOX,
            output_dir=tmp_path,
        )
        assert result.superseded == (old,)
        assert result.tiles == (kept,)

    def test_laz_parallel_workers_one_version_per_tile(self, tmp_path: Path) -> None:
        tiles = [_tile(f"N-33-131-B-a-1-1-{i}") for i in range(1, 7)]
        progress: list[tuple[int, int]] = []
        result = _run_laz_download(
            _selection(*tiles),
            provider=FakeProvider(),
            bbox=BBOX,
            output_dir=tmp_path,
            workers=3,
            on_progress=lambda done, total: progress.append((done, total)),
        )
        assert len(result.files) == 6
        assert [file.status for file in result.files] == ["new"] * 6
        assert all(
            file.path.stat().st_ino == file.version_path.stat().st_ino
            for file in result.files
        )
        assert len(list(tmp_path.rglob("versions/**/*.laz.meta.json"))) == 6
        assert progress == [(i, 6) for i in range(0, 7)]

    def test_kron86_segment_follows_provider(self, tmp_path):
        tile = _tile("N-33-131-B-a-1-1-4")
        result = _run_laz_download(
            _selection(tile),
            provider=FakeProvider(vertical_crs="KRON86"),
            bbox=BBOX,
            output_dir=tmp_path,
        )
        (path,) = (file.path for file in result.files)
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
            provider=GugikLazProvider(session=session, vertical_crs="EVRF2007"),
            parent_request=PARENT,
            vertical_crs="EVRF2007",
        )
        assert isinstance(result, LazDownloadResult)
        assert [t.sheet for t in result.tiles] == ["N-34-139-A-c-1-1-3-4"]
        assert downloaded_urls(session) == [
            "https://opendata.geoportal.gov.pl/NumDaneWys/DanePomiaroweLAZ/"
            "83230/83230_1743191_N-34-139-A-c-1-1-3-4.laz"
        ]
        (path,) = (file.path for file in result.files)
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
            provider=GugikLazProvider(session=session, vertical_crs="EVRF2007"),
            vertical_crs="EVRF2007",
        )
        assert [(t.sheet, t.year) for t in result.tiles] == [("7.173.21.06.2", 2022)]
        assert _sidecar(result.files[0].path)["request"]["year"] == 2022

    def test_year_with_empty_service_layer_conflicts_before_download(self, tmp_path):
        session = wfs_session()
        with pytest.raises(YearRangeError) as caught:
            download_laz_area(
                W2_AREA,
                output_dir=tmp_path,
                year=2026,  # the layer exists, but no tiles here
                provider=GugikLazProvider(session=session, vertical_crs="EVRF2007"),
                vertical_crs="EVRF2007",
            )
        assert caught.value.sheets == {"N-34-139-A-c-1-1-3-4": (2022, 2023, 2025)}
        assert downloaded_urls(session) == []
        assert list(tmp_path.iterdir()) == []

    def test_check_mode_rejected_before_wfs_selection(self, tmp_path):
        session = wfs_session()
        with pytest.raises(ValidationError, match="check"):
            download_laz_area(
                W2_AREA,
                output_dir=tmp_path,
                vertical_crs="EVRF2007",
                provider=GugikLazProvider(session=session, vertical_crs="EVRF2007"),
                update="check",
            )
        session.get.assert_not_called()

    def test_vertical_crs_mismatch_with_provider_is_rejected(self, tmp_path):
        with pytest.raises(ValidationError, match="KRON86"):
            download_laz_area(
                W2_AREA,
                output_dir=tmp_path,
                vertical_crs="KRON86",
                provider=GugikLazProvider(
                    session=wfs_session(), vertical_crs="EVRF2007"
                ),
            )

    def test_bbox_epsg4326_same_tiles_as_2180(self, tmp_path):
        """A WGS84 area selects what its densified EPSG:2180 envelope selects."""
        from pyproj import Transformer

        from kartograf.core.bbox import transform_bbox

        to_wgs = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
        lon0, lat0 = to_wgs.transform(637410, 487010)
        lon1, lat1 = to_wgs.transform(637440, 487040)
        wgs = BBox(
            float(f"{lon0:.6f}"),
            float(f"{lat0:.6f}"),
            float(f"{lon1:.6f}"),
            float(f"{lat1:.6f}"),
            "EPSG:4326",
        )
        args = {"output_dir": tmp_path, "vertical_crs": "EVRF2007", "cache": False}
        from_wgs = check_laz_area(
            wgs,
            provider=GugikLazProvider(
                session=wfs_session("wgs"), vertical_crs="EVRF2007"
            ),
            **args,
        )
        from_2180 = check_laz_area(
            transform_bbox(wgs, "EPSG:2180"),
            provider=GugikLazProvider(
                session=wfs_session("wgs"), vertical_crs="EVRF2007"
            ),
            **args,
        )
        assert from_wgs.items == from_2180.items
        assert [i.unit for i in from_wgs.items]

    def test_area_wgs84_across_19e_keeps_southern_band(self):
        """K6: an envelope from densified edges - four corners lost
        ~479 m in the S for a bbox through 19E (LAZ tile selection too narrow)."""
        bbox = bbox_to_2180(BBox(18, 50, 20, 50.2, "EPSG:4326"))
        assert bbox.crs == "EPSG:2180"
        assert bbox.min_y == pytest.approx(236968.4486, abs=0.01)

    @pytest.mark.parametrize(
        "czech",
        [
            BBox(-788231, -1052442, -741087, -1013379, "EPSG:5514"),
            BBox(450000, 5540000, 455000, 5545000, "EPSG:3045"),
        ],
    )
    def test_area_from_czech_crs_never_uses_plain_transformer(self, czech):
        """Czech CRSs leave only via the pinned operation, never via an unpinned
        pyproj transformer (ballpark selection on the border strip)."""
        from unittest.mock import patch

        from kartograf.core import bbox as core_bbox
        from kartograf.providers.cuzk import dmr

        with (
            patch.object(dmr, "bbox_to_crs", wraps=dmr.bbox_to_crs) as pinned,
            patch.object(
                core_bbox, "_transformer", wraps=core_bbox._transformer
            ) as plain,
        ):
            bbox = bbox_to_2180(czech)
        assert bbox.crs == "EPSG:2180"
        assert pinned.called
        plain.assert_not_called()

    def test_bbox_epsg5514_uses_pinned_transform(self, tmp_path):
        from unittest.mock import patch

        krovak = BBox(-500000, -1100000, -499950, -1099950, "EPSG:5514")
        with patch(
            "kartograf.providers.cuzk.dmr.bbox_to_crs", return_value=W2_AREA
        ) as pinned:
            plan = check_laz_area(
                krovak,
                output_dir=tmp_path,
                vertical_crs="EVRF2007",
                cache=False,
                provider=GugikLazProvider(
                    session=wfs_session(), vertical_crs="EVRF2007"
                ),
            )
        pinned.assert_called_once_with(krovak, "EPSG:2180")
        assert [i.unit for i in plan.items] == ["N-34-139-A-c-1-1-3-4"]

    def test_check_laz_area_same_args(self, tmp_path):
        args = {
            "output_dir": tmp_path,
            "vertical_crs": "EVRF2007",
            "min_density": 4,
            "cache": False,
        }

        def provider():
            return GugikLazProvider(session=wfs_session(), vertical_crs="EVRF2007")

        before = check_laz_area(W2_AREA, provider=provider(), **args)
        result = download_laz_area(W2_AREA, provider=provider(), **args)
        after = check_laz_area(W2_AREA, provider=provider(), **args)
        assert [(i.unit, i.status) for i in before.items] == [
            ("N-34-139-A-c-1-1-3-4", "missing")
        ]
        assert [i.name for i in after.items] == [f.path.name for f in result.files]
        assert after.items[0].status == "current"

    def test_download_laz_area_plan_stale(self, tmp_path):
        args = {"output_dir": tmp_path, "vertical_crs": "EVRF2007", "cache": False}
        plan = check_laz_area(
            W2_AREA,
            provider=GugikLazProvider(session=wfs_session(), vertical_crs="EVRF2007"),
            **args,
        )
        changed = replace(plan.items[0], available_label="different")
        session = wfs_session()
        result = download_laz_area(
            W2_AREA,
            update="upgrade",
            plan=replace(plan, items=(changed,)),
            provider=GugikLazProvider(session=session, vertical_crs="EVRF2007"),
            **args,
        )
        assert result.files == () and result.stale == (changed,)
        assert downloaded_urls(session) == []

    def test_superseded_notice(self, tmp_path):
        seen: list[Notice] = []
        result = download_laz_area(
            W2_AREA,
            output_dir=tmp_path,
            vertical_crs="EVRF2007",
            cache=False,
            on_notice=seen.append,
            provider=GugikLazProvider(session=wfs_session(), vertical_crs="EVRF2007"),
        )
        (notice,) = result.notices
        assert seen == [notice]
        assert notice.level == "info" and notice.code == LAZ_SUPERSEDED
        lines = notice.text.split("\n")
        assert lines[0] == (
            "pominieto 2 kafli LAZ - obszar pokrywaja nowsze kafle (domyslnie "
            "najnowszy rocznik per obszar; inny rocznik: --year/--min-year/--max-year)"
        )
        assert (
            "  7.173.21.06.2 (2022, PL-2000:S7): pokryty przez "
            "N-34-139-A-c-1-1-3-4 (2025, PL-1992)"
        ) in lines

    def test_no_tiles_is_no_coverage_error(self, tmp_path):
        provider = MagicMock(vertical_crs="EVRF2007")
        provider.select_tiles.return_value = _selection()
        with pytest.raises(NoCoverageError) as caught:
            download_laz_area(
                W2_AREA,
                output_dir=tmp_path,
                vertical_crs="EVRF2007",
                cache=False,
                provider=provider,
            )
        assert str(caught.value) == NO_TILES_MESSAGE
        provider.download.assert_not_called()

    def test_workers_param_name(self, tmp_path):
        tiles = [_tile(f"N-33-131-B-a-1-1-{i}") for i in range(1, 5)]
        provider = FakeProvider()
        provider.select_tiles = MagicMock(return_value=_selection(*tiles))
        result = download_laz_area(
            W2_AREA,
            output_dir=tmp_path,
            vertical_crs="EVRF2007",
            workers=4,
            cache=False,
            provider=provider,  # type: ignore[arg-type]
        )
        assert len(result.files) == 4 and result.ok
        assert len(provider.calls) == 4


# =============================================================================
# CLI: a thin layer (`kartograf elevation download --product laz`)
# =============================================================================


def _cli(tmp_path, *args, area: str = "w2"):
    from unittest.mock import patch

    from kartograf.cli.commands import main

    session = wfs_session(area)
    with patch("kartograf.transport.http.make_gugik_session", return_value=session):
        rc = main(
            [
                "elevation",
                "download",
                "--product",
                "nmt",
                "-o",
                "./data",
                "--country",
                "auto",
                "--resolution",
                "pl=1m,cz=2m",
                "--vertical-crs",
                "pl=EVRF2007,cz=Bpv",
                *args,
                "--product",
                "laz",
                "-o",
                str(tmp_path),
                "-q",
            ]
        )
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

    def test_cli_local_then_force_redownloads_without_overwriting(self, tmp_path):
        first, first_session = _cli(tmp_path, *self.W2, "--country", "pl")
        second, second_session = _cli(tmp_path, *self.W2, "--country", "pl")
        forced, forced_session = _cli(tmp_path, *self.W2, "--country", "pl", "--force")
        assert (first, second, forced) == (0, 0, 0)
        assert len(downloaded_urls(first_session)) == 1
        assert downloaded_urls(second_session) == []
        assert downloaded_urls(forced_session) == downloaded_urls(first_session)
        assert len(list(tmp_path.rglob("versions/**/*.laz.meta.json"))) == 1

    def test_bbox_mode_sidecar_has_parent_request(self, tmp_path):
        rc, _ = _cli(tmp_path, *self.W2, "--country", "pl")
        assert rc == 0
        (sidecar,) = (
            p for p in tmp_path.rglob("*.meta.json") if "versions" not in p.parts
        )
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
        (sidecar,) = (
            p for p in tmp_path.rglob("*.meta.json") if "versions" not in p.parts
        )
        parent = json.loads(sidecar.read_text("utf-8"))["extra"]["parent_request"]
        assert parent["bbox_crs"] == "EPSG:4326"
        assert parent["bbox"] == [float(v) for v in bbox.split(",")]
        assert parent["countries"] == ["PL"]

    def test_sheet_mode_has_no_parent_request(self, tmp_path):
        rc, session = _cli(tmp_path, "--sheet", "N-34-139-A-c-1-1", area="sheet")
        assert rc == 0
        sidecars = [
            p for p in tmp_path.rglob("*.meta.json") if "versions" not in p.parts
        ]
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
