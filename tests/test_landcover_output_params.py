"""
Land cover in the version store (spec 3.4, D29-D32).

Content parameters name the segment and the sidecar ``request`` (two
downloads with different parameters never share a file, U3); every file is
a version with a hardlink at the standard path; SoilGrids/CORINE versions
are labelled by the source edition, BDOT10k and the CORINE preview by the
download date.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import rasterio

from kartograf.core.sheet_parser import BBox
from kartograf.download.plan import UpdatePlan
from kartograf.download.versions import VersionRef, list_versions
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.landcover.manager import LandCoverManager
from kartograf.notices import UNVERIFIED_LOCAL, Notice
from kartograf.providers.corine import CorineProvider
from kartograf.providers.pl.bdot10k import Bdot10kPackage, Bdot10kProvider
from kartograf.providers.soilgrids import SoilGridsProvider
from tests.conftest import FakeCorine, FakeSoilGrids, tiny_geotiff

BBOX = BBox(770000, 509000, 772000, 511000, "EPSG:2180")
COORDS = "770000_509000_772000_511000"
CLAY = {"property": "clay", "depth": "0-5cm", "stat": "mean"}
SOIL_SEG = "soil/global_soilgrids_clay_0-5cm_mean"


def _sidecar(path: Path) -> dict:
    return json.loads((path.parent / f"{path.name}.meta.json").read_text())


def _first_pixel(path: Path) -> int:
    with rasterio.open(path) as ds:
        return int(ds.read(1)[0, 0])


def _soil(tmp_path, session: FakeSoilGrids) -> LandCoverManager:
    return LandCoverManager(tmp_path, SoilGridsProvider(session=session))


def _corine(tmp_path, session: FakeCorine) -> LandCoverManager:
    return LandCoverManager(tmp_path, CorineProvider(session=session, use_proxy=False))


# --- SoilGrids --------------------------------------------------------------


class TestSoilGridsStore:
    def test_soilgrids_lands_as_edition_version(self, tmp_path):
        session = FakeSoilGrids("2.0")
        result = _soil(tmp_path, session).download(sheet="N-34-130-D", **CLAY)
        (item,) = result.files
        file = item.file
        assert item.unit == "N-34-130-D"
        assert file.path == tmp_path / SOIL_SEG / "N-34/130/D/N-34-130-D.tif"
        assert file.status == "new" and file.label == "2.0"
        assert file.version_path.parent.name == f"2.0_{file.sha256[:8]}"
        assert file.version_path.parent.parent == (
            tmp_path / SOIL_SEG / "versions/N-34/130/D"
        )
        assert os.path.samefile(file.path, file.version_path)
        meta = _sidecar(file.version_path)
        assert meta["extra"]["version"] == {"label": "2.0", "label_source": "edition"}
        assert meta["extra"]["edition"]["id"] == "2.0"
        assert meta["extra"]["edition"]["title"] == "SoilGrids250m 2.0 - Clay content"
        assert meta["request"] == {"sheet": "N-34-130-D", **CLAY}
        assert meta["nodata"] == -32768
        assert (session.capabilities, session.coverages) == (1, 1)

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            ({"property": "clay"}, {"property": "sand"}),
            ({"depth": "0-5cm"}, {"depth": "5-15cm"}),
            ({"stat": "mean"}, {"stat": "Q0.05"}),
        ],
    )
    def test_different_params_keep_both_files(self, tmp_path, first, second):
        session = FakeSoilGrids(values={"clay": 11, "sand": 22})
        manager = _soil(tmp_path, session)
        a = manager.download(bbox=BBOX, **{**CLAY, **first}).files[0].file
        b = manager.download(bbox=BBOX, **{**CLAY, **second}).files[0].file
        assert a.path != b.path
        assert a.path.parent.parent != b.path.parent.parent  # own segments
        assert a.path.name == b.path.name == f"{COORDS}.tif"

    def test_quantile_stat_segment_lowercase(self, tmp_path):
        manager = _soil(tmp_path, FakeSoilGrids())
        result = manager.download(bbox=BBOX, **{**CLAY, "stat": "Q0.95"})
        file = result.files[0].file
        assert file.path == (
            tmp_path / "soil/global_soilgrids_clay_0-5cm_q0.95/bbox" / f"{COORDS}.tif"
        )
        assert _sidecar(file.version_path)["request"]["stat"] == "Q0.95"

    def test_soilgrids_default_local_asks_no_capabilities(self, tmp_path):
        # the default mode asks no source for a local version (ADR-036 erratum 3)
        _soil(tmp_path, FakeSoilGrids("2.0")).download(bbox=BBOX, **CLAY)
        session = FakeSoilGrids("2.0")
        result = _soil(tmp_path, session).download(bbox=BBOX, **CLAY)
        file = result.files[0].file
        assert (file.status, file.label) == ("local", "2.0")
        assert file.newer is None and file.unverified == "unchecked"
        assert (session.capabilities, session.coverages) == (0, 0)

    def test_soilgrids_new_edition_check_sees_it_upgrade_downloads(self, tmp_path):
        _soil(tmp_path, FakeSoilGrids("2.0", {"clay": 1})).download(bbox=BBOX, **CLAY)
        session = FakeSoilGrids("2.1", {"clay": 7})
        manager = _soil(tmp_path, session)
        kept = manager.download(bbox=BBOX, **CLAY).files[0].file
        assert (kept.status, kept.label, kept.newer) == ("local", "2.0", None)
        (item,) = manager.check(bbox=BBOX, **CLAY).items
        assert (item.status, item.available_label) == ("newer", "2.1")
        assert session.coverages == 0
        upgraded = manager.download(bbox=BBOX, update="upgrade", **CLAY).files[0].file
        assert (upgraded.status, upgraded.label) == ("new", "2.1")
        assert session.coverages == 1
        assert _first_pixel(upgraded.path) == 7
        assert (
            len(list_versions(upgraded.version_path.parent.parent, upgraded.path.name))
            == 2
        )

    def test_soilgrids_edition_unavailable_without_local_is_error(self, tmp_path):
        session = FakeSoilGrids(404)
        with pytest.raises(DownloadError, match="GetCapabilities"):
            _soil(tmp_path, session).download(bbox=BBOX, **CLAY)
        assert session.coverages == 0
        assert not (tmp_path / "soil").exists()

    def test_soilgrids_edition_unavailable_with_local(self, tmp_path):
        """Offline with a local version: the default mode uses it without a
        request or warning; ``upgrade`` needs the edition - an error."""
        _soil(tmp_path, FakeSoilGrids("2.0")).download(bbox=BBOX, **CLAY)
        session = FakeSoilGrids(404)
        manager = _soil(tmp_path, session)
        observed = []
        result = manager.download(bbox=BBOX, on_notice=observed.append, **CLAY)
        file = result.files[0].file
        assert (file.status, file.unverified) == ("local", "unchecked")
        assert result.notices == () and observed == []
        assert session.capabilities == 0
        with pytest.raises(DownloadError):
            manager.download(bbox=BBOX, update="upgrade", **CLAY)
        assert session.coverages == 0

    def test_soilgrids_force_same_content_unchanged(self, tmp_path):
        first = (
            _soil(tmp_path, FakeSoilGrids("2.0"))
            .download(bbox=BBOX, **CLAY)
            .files[0]
            .file
        )
        session = FakeSoilGrids("2.0")
        again = _soil(tmp_path, session).download(bbox=BBOX, update="force", **CLAY)
        assert (again.files[0].file.status, again.files[0].file.version_path) == (
            "unchanged",
            first.version_path,
        )
        assert session.coverages == 1

    def test_check_soilgrids_never_downloads(self, tmp_path):
        def status(edition):
            session = FakeSoilGrids(edition)
            plan = _soil(tmp_path, session).check(bbox=BBOX, **CLAY)
            assert session.coverages == 0
            (item,) = plan.items
            assert (item.track, item.unit) == ("landcover", COORDS)
            assert item.segment == SOIL_SEG and item.hierarchy == "bbox"
            return item

        missing = status("2.0")
        assert (missing.status, missing.available_label) == ("missing", "2.0")
        assert missing.available_signal == {"edition": "2.0"}
        _soil(tmp_path, FakeSoilGrids("2.0")).download(bbox=BBOX, **CLAY)
        assert status("2.0").status == "current"
        assert status("2.1").status == "newer"
        assert status(404).status == "check_failed"

    def test_upgrade_plan_stale_and_removed_items(self, tmp_path):
        _soil(tmp_path, FakeSoilGrids("2.0")).download(bbox=BBOX, **CLAY)
        plan = _soil(tmp_path, FakeSoilGrids("2.1")).check(bbox=BBOX, **CLAY)
        assert plan.items[0].status == "newer"
        # the source moved on since the plan: stale, nothing downloaded
        session = FakeSoilGrids("2.2")
        result = _soil(tmp_path, session).download(
            bbox=BBOX, update="upgrade", plan=plan, **CLAY
        )
        assert result.files[0].file.status == "local"
        assert result.files[0].file.label == "2.0"
        assert [i.available_label for i in result.stale] == ["2.1"]
        assert session.coverages == 0
        # a position removed from the plan file is never executed
        empty = UpdatePlan.from_json(plan.to_json().replace('"newer"', '"current"'))
        session = FakeSoilGrids("2.1")
        result = _soil(tmp_path, session).download(
            bbox=BBOX, update="upgrade", plan=empty, **CLAY
        )
        assert result.files[0].file.label == "2.0" and session.coverages == 0
        # the planned position, unchanged source: executed
        session = FakeSoilGrids("2.1")
        result = _soil(tmp_path, session).download(
            bbox=BBOX, update="upgrade", plan=plan, **CLAY
        )
        # same pixels under the new edition: own version directory (D23)
        file = result.files[0].file
        assert (file.status, file.label) == ("relabeled", "2.1")
        assert result.stale == () and result.ok

    def test_plan_requires_upgrade_and_own_store(self, tmp_path):
        plan = _soil(tmp_path, FakeSoilGrids()).check(bbox=BBOX, **CLAY)
        with pytest.raises(ValidationError):
            _soil(tmp_path, FakeSoilGrids()).download(bbox=BBOX, plan=plan, **CLAY)
        with pytest.raises(ValidationError, match="innego magazynu"):
            _soil(tmp_path / "other", FakeSoilGrids()).download(
                bbox=BBOX, update="upgrade", plan=plan, **CLAY
            )

    def test_soilgrids_teryt_not_supported_before_network(self, tmp_path):
        session = FakeSoilGrids()
        with pytest.raises(
            ValidationError, match="--teryt dziala tylko z --product bdot10k"
        ):
            _soil(tmp_path, session).download(teryt="1465", **CLAY)
        assert session.capabilities == 0


# --- CORINE -----------------------------------------------------------------


class TestCorineStore:
    def _clms_tiff(self, provider):
        def fake(bbox, out, year, timeout):
            target = out.with_suffix(".tif")
            target.write_bytes(tiny_geotiff(-128, 3))
            return target

        return patch.object(provider, "_download_via_clms", side_effect=fake)

    def test_corine_clms_segment_and_edition(self, tmp_path):
        session = FakeCorine("V2020_20u1")
        manager = _corine(tmp_path, session)
        with (
            patch.object(CorineProvider, "has_clms_token", new=True),
            self._clms_tiff(manager.provider),
        ):
            file = manager.download(sheet="M-33-036-A", year=2018).files[0].file
        assert (
            file.path == tmp_path / "landcover/eu_corine_2018/M-33/36/A/M-33-36-A.tif"
        )
        assert (file.status, file.label) == ("new", "V2020_20u1")
        meta = _sidecar(file.version_path)
        assert (
            meta["extra"]["edition"]["dataset_uid"]
            == (CorineProvider.CLMS_DATASET_UIDS[2018])
        )
        assert meta["request"] == {"sheet": "M-33-36-A", "year": 2018}
        assert meta["horizontal_crs"] == "EPSG:3035"
        assert meta["nodata"] == -128
        assert "fallback" not in meta["extra"]
        assert session.catalogue == 1

    def test_corine_preview_separate_segment_downloaded_label(self, tmp_path):
        session = FakeCorine()
        with patch.object(CorineProvider, "has_clms_token", new=False):
            file = (
                _corine(tmp_path, session).download(bbox=BBOX, year=2018).files[0].file
            )
            assert file.path == (
                tmp_path / "landcover/eu_corine_2018_preview/bbox" / f"{COORDS}.png"
            )
            assert file.label == VersionRef.downloaded().label
            meta = _sidecar(file.version_path)
            assert meta["extra"]["version"]["label_source"] == "downloaded"
            assert meta["extra"]["fallback"] == "wms_png"
            assert meta["horizontal_crs"] == "EPSG:3857"
            assert "edition" not in meta["extra"]
            assert session.catalogue == 0  # no edition for a preview
            # rerun: local, no signal (none)
            again = (
                _corine(tmp_path, session).download(bbox=BBOX, year=2018).files[0].file
            )
            assert (again.status, again.unverified) == ("local", "none")
            assert session.previews == 1
        assert not (tmp_path / "landcover/eu_corine_2018").exists()

    def test_corine_1990_preview_only(self, tmp_path):
        with patch.object(CorineProvider, "has_clms_token", new=True):
            file = (
                _corine(tmp_path, FakeCorine())
                .download(bbox=BBOX, year=1990)
                .files[0]
                .file
            )
        assert file.path.parent.parent.name == "eu_corine_1990_preview"
        assert _sidecar(file.version_path)["horizontal_crs"] == "EPSG:4326"

    def test_corine_teryt_not_supported(self, tmp_path):
        with pytest.raises(
            ValidationError, match="--teryt dziala tylko z --product bdot10k"
        ):
            _corine(tmp_path, FakeCorine()).download(teryt="1465", year=2018)


# --- general ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "kwargs"),
    [
        ("soilgrids", CLAY),
        ("corine", {"year": 2018}),
        ("bdot10k", {}),
    ],
)
def test_manager_has_no_output_path(tmp_path, source, kwargs):
    manager = LandCoverManager(tmp_path, source)
    with pytest.raises(TypeError, match="output_path"):
        manager.download(bbox=BBOX, output_path=tmp_path / "x", **kwargs)
    assert list(tmp_path.iterdir()) == []


def test_no_dir_created_on_init(tmp_path):
    for source in ("bdot10k", "corine", "soilgrids"):
        LandCoverManager(tmp_path / "a" / "b", source)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("source", "options", "missing"),
    [
        ("corine", {}, "--year wymagane dla corine:"),
        (
            "soilgrids",
            {"depth": "0-5cm", "stat": "mean"},
            "--property wymagane:",
        ),
        (
            "soilgrids",
            {"property": "clay", "stat": "mean"},
            "--depth wymagane:",
        ),
        (
            "soilgrids",
            {"property": "clay", "depth": "0-5cm"},
            "--stat wymagane:",
        ),
    ],
)
@pytest.mark.parametrize("method", ["download", "check"])
def test_missing_required_option_is_validation_error(
    tmp_path, source, options, missing, method
):
    manager = LandCoverManager(tmp_path, source)
    with pytest.raises(ValidationError) as caught:
        getattr(manager, method)(bbox=BBOX, **options)
    assert str(caught.value).startswith(missing)


# --- BDOT10k --------------------------------------------------------------------


class FakePackages:
    """``Bdot10kProvider.download_package`` stand-in; counts downloads."""

    def __init__(self, fail: set[str] | None = None):
        self.calls: list[str] = []
        self.fail = fail or set()

    def __call__(
        self,
        code,
        output_path,
        *,
        format="GPKG",
        layers=None,
        keep_raw=False,
        raw_path=None,
        timeout=None,
    ):
        self.calls.append(code)
        if code in self.fail:
            raise DownloadError(f"BDOT10k TERYT {code}: HTTP 500")
        target = output_path.with_suffix(".zip") if format == "SHP" else output_path
        target.write_bytes(f"{format} {code} {layers}".encode())
        if keep_raw:
            raw_path.write_bytes(f"zip {code}".encode())
        return Bdot10kPackage(
            path=target,
            teryt=code,
            url=f"https://x/{code}_{format}.zip",
            format=format,
            http={"etag": None, "last_modified": None, "content_length": 10},
            raw_path=raw_path if keep_raw else None,
        )


def _bdot(tmp_path, packages: FakePackages, teryts=("1465",)):
    provider = Bdot10kProvider()
    patch.object(provider, "download_package", side_effect=packages).start()
    patch.object(provider, "teryts_for_area", return_value=list(teryts)).start()
    return LandCoverManager(tmp_path, provider)


class TestBdot10kStore:
    def teardown_method(self):
        patch.stopall()

    def test_bdot_gpkg_version_and_link(self, tmp_path):
        result = _bdot(tmp_path, FakePackages()).download(teryt="1465")
        (item,) = result.files
        file = item.file
        assert item.unit == "1465" and item.raw is None
        assert file.path == tmp_path / "landcover/pl_bdot10k_gpkg/teryt/1465.gpkg"
        assert file.version_path.parent.parent == (
            tmp_path / "landcover/pl_bdot10k_gpkg/versions/teryt"
        )
        assert os.path.samefile(file.path, file.version_path)
        meta = _sidecar(file.version_path)
        assert meta["request"] == {"teryt": "1465", "format": "GPKG"}
        assert meta["extra"]["source"] == {
            "url": "https://x/1465_GPKG.zip",
            "teryt": "1465",
            "format": "GPKG",
        }
        assert meta["extra"]["http"]["content_length"] == 10
        assert meta["extra"]["version"]["label_source"] == "downloaded"
        assert "source_files" not in meta["extra"]

    def test_bdot_upgrade_unverified_notice_once_for_each_store_file(self, tmp_path):
        manager = _bdot(tmp_path, FakePackages())
        manager.download(teryt="1465", keep_raw=True)
        observed = []
        result = manager.download(
            teryt="1465", keep_raw=True, update="upgrade", on_notice=observed.append
        )
        assert result.notices == tuple(observed)
        files = (result.files[0].file, result.files[0].raw)
        assert result.notices == tuple(
            Notice(
                "info",
                UNVERIFIED_LOCAL,
                f"{file.path.relative_to(tmp_path).as_posix()}: lokalna wersja "
                f"{file.label} niesprawdzona - zrodlo bez taniego sygnalu; "
                "pobierz ponownie: --force",
            )
            for file in files
        )
        assert all(file.status == "local" for file in files)

    def test_bdot_layers_segment_lowercase_sorted(self, tmp_path):
        file = (
            _bdot(tmp_path, FakePackages())
            .download(teryt="1465", layers=["SWRS", "PTWP", "SWRS"])
            .files[0]
            .file
        )
        assert file.path == (
            tmp_path / "landcover/pl_bdot10k_gpkg_ptwp-swrs/teryt/1465.gpkg"
        )
        assert _sidecar(file.version_path)["request"]["layers"] == ["PTWP", "SWRS"]

    def test_bdot_bad_layer_rejected_before_network(self, tmp_path):
        packages = FakePackages()
        with pytest.raises(ValidationError, match="warstw"):
            _bdot(tmp_path, packages).download(teryt="1465", layers=["ptwp_a"])
        assert packages.calls == []

    def test_bdot_shp_segment_zip(self, tmp_path):
        file = (
            _bdot(tmp_path, FakePackages())
            .download(teryt="1465", format="SHP")
            .files[0]
            .file
        )
        assert file.path == tmp_path / "landcover/pl_bdot10k_shp/teryt/1465.zip"
        assert _sidecar(file.version_path)["request"]["format"] == "SHP"

    def test_bdot_keep_raw_zip_own_version_and_source_files(self, tmp_path):
        result = _bdot(tmp_path, FakePackages()).download(
            teryt="1465", keep_raw=True, layers=["PTWP"]
        )
        (item,) = result.files
        raw = item.raw
        assert raw is not None
        assert raw.path == tmp_path / "landcover/pl_bdot10k_gpkg_zip/teryt/1465.zip"
        assert raw.path.read_bytes() == b"zip 1465"
        raw_meta = _sidecar(raw.version_path)
        assert raw_meta["request"] == {"teryt": "1465", "format": "GPKG"}
        meta = _sidecar(item.file.version_path)
        assert meta["extra"]["source_files"] == [
            {
                "name": "package",
                "file": raw.version_path.relative_to(tmp_path).as_posix(),
                "sha256": raw.sha256,
            }
        ]
        assert "raw_file" not in meta["extra"]["source"]

    def test_bdot_keep_raw_missing_zip_triggers_one_download(self, tmp_path):
        packages = FakePackages()
        manager = _bdot(tmp_path, packages)
        manager.download(teryt="1465")
        result = manager.download(teryt="1465", keep_raw=True)
        assert packages.calls == ["1465", "1465"]
        (item,) = result.files
        assert item.file.status == "unchanged"
        assert item.raw is not None and item.raw.status == "new"

    def test_bdot_default_local_without_package_request(self, tmp_path):
        packages = FakePackages()
        manager = _bdot(tmp_path, packages)
        manager.download(teryt="1465", keep_raw=True)
        result = manager.download(teryt="1465", keep_raw=True)
        assert packages.calls == ["1465"]
        (item,) = result.files
        assert (item.file.status, item.file.unverified) == ("local", "none")
        assert item.raw is not None and item.raw.status == "local"

    def test_bdot_force_same_content_unchanged_next_day(self, tmp_path):
        manager = _bdot(tmp_path, FakePackages())
        first = manager.download(teryt="1465").files[0].file
        nxt = VersionRef("2099-01-02", "downloaded")
        with patch.object(VersionRef, "downloaded", staticmethod(lambda now=None: nxt)):
            again = manager.download(teryt="1465", update="force").files[0].file
        assert (again.status, again.label) == ("unchanged", first.label)
        assert len(list_versions(first.version_path.parent.parent, "1465.gpkg")) == 1

    def test_bdot_upgrade_is_local_unverified_none(self, tmp_path):
        packages = FakePackages()
        manager = _bdot(tmp_path, packages)
        manager.download(teryt="1465")
        file = manager.download(teryt="1465", update="upgrade").files[0].file
        assert (file.status, file.unverified) == ("local", "none")
        assert packages.calls == ["1465"]

    def test_check_bdot_never_downloads(self, tmp_path):
        packages = FakePackages()
        manager = _bdot(tmp_path, packages)
        manager.download(teryt="1465")
        plan = manager.check(teryt="1465", keep_raw=True)
        assert [(i.segment, i.status) for i in plan.items] == [
            ("landcover/pl_bdot10k_gpkg", "unverifiable"),
            ("landcover/pl_bdot10k_gpkg_zip", "missing"),
        ]
        assert {i.unit for i in plan.items} == {"1465"}
        area = manager.check(bbox=BBOX)
        assert [i.unit for i in area.items] == ["1465"]
        assert packages.calls == ["1465"]

    def test_bdot_one_county_failure_others_downloaded_ok_false(self, tmp_path):
        packages = FakePackages(fail={"0224"})
        area = _bdot(tmp_path, packages, ["0208", "0224", "0261"]).download(bbox=BBOX)
        assert [r.unit for r in area.files] == ["0208", "0261"]
        assert [f.unit for f in area.failed] == ["0224"]
        assert "HTTP 500" in area.failed[0].error
        assert packages.calls == ["0208", "0224", "0261"]
        assert not (tmp_path / "landcover/pl_bdot10k_gpkg/teryt/0224.gpkg").exists()
        assert not area.ok

    def test_bdot_area_parent_request_in_version_sidecar(self, tmp_path):
        manager = _bdot(tmp_path, FakePackages(), ["0208"])
        by_sheet = manager.download(sheet="M-33-048-A").files[0].file
        meta = _sidecar(by_sheet.version_path)
        assert meta["request"] == {"teryt": "0208", "format": "GPKG"}
        assert meta["extra"]["parent_request"] == {
            "sheet": "M-33-48-A",
            "countries": ["PL"],
        }
        area = manager.download(bbox=BBOX, update="force")
        meta = _sidecar(area.files[0].file.version_path)
        assert area.files[0].file.status == "unchanged"
        # same content = the version of the first download keeps its sidecar
        assert meta["extra"]["parent_request"]["sheet"] == "M-33-48-A"

    def test_bdot_bbox_in_4326_accepted(self, tmp_path):
        file = (
            _bdot(tmp_path, FakePackages(), ["0208"])
            .download(bbox=BBox(16.70, 50.45, 16.80, 50.55, "EPSG:4326"))
            .files[0]
            .file
        )
        assert file.path.name == "0208.gpkg"
        assert _sidecar(file.version_path)["extra"]["parent_request"]["bbox_crs"] == (
            "EPSG:4326"
        )

    def test_bdot_bbox_downloads_every_county(self, tmp_path):
        """An area of 2 powiats gives 2 files (as the CLI always did)."""
        packages = FakePackages()
        area = _bdot(tmp_path, packages, ["0208", "0224"]).download(bbox=BBOX)
        assert [r.unit for r in area.files] == ["0208", "0224"]
        assert area.failed == () and area.ok
        assert packages.calls == ["0208", "0224"]

    def test_bdot_failure_leaves_no_version_and_no_staging(self, tmp_path):
        packages = FakePackages(fail={"1465"})
        with pytest.raises(DownloadError):
            _bdot(tmp_path, packages).download(teryt="1465", keep_raw=True)
        assert list(tmp_path.iterdir()) == []

    def test_no_county_raises_no_coverage(self, tmp_path):
        from kartograf.exceptions import NoCoverageError

        with pytest.raises(NoCoverageError):
            _bdot(tmp_path, FakePackages(), []).download(bbox=BBOX)


# --- command level: download / check (S3) -----------------------------------


class TestCommandLevel:
    def teardown_method(self):
        patch.stopall()

    def test_teryt_single_element(self, tmp_path):
        area = _bdot(tmp_path, FakePackages()).download(teryt="1465")
        assert [r.unit for r in area.files] == ["1465"]
        assert area.failed == () and area.stale == () and area.notices == ()
        assert area.ok

    def test_soilgrids_bbox_epsg4326(self, tmp_path):
        """A WGS84 bbox lands in the slot of its EPSG:2180 envelope."""
        from kartograf.core.bbox import transform_bbox

        wgs = BBox(23.40, 54.05, 23.43, 54.07, "EPSG:4326")
        area = _soil(tmp_path, FakeSoilGrids("2.0")).download(bbox=wgs, **CLAY)
        in_2180 = _soil(tmp_path, FakeSoilGrids("2.0")).download(
            bbox=transform_bbox(wgs, "EPSG:2180"), **CLAY
        )
        (first,) = area.files
        (second,) = in_2180.files
        assert first.file.path == second.file.path
        assert first.file.path.parent.name == "bbox"
        assert second.file.status == "local"
        assert _sidecar(first.file.version_path)["request"]["bbox_crs"] == "EPSG:2180"

    def test_geometry_envelope_selection(self, tmp_path):
        """``geometry`` = the EPSG:2180 envelope of the file (get_overall_bbox)."""
        shp = tmp_path / "area.shp"
        shp.touch()
        with patch(
            "kartograf.core.geometry.get_overall_bbox", return_value=BBOX
        ) as envelope:
            by_geometry = _soil(tmp_path, FakeSoilGrids("2.0")).download(
                geometry=shp, **CLAY
            )
        by_bbox = _soil(tmp_path, FakeSoilGrids("2.0")).download(bbox=BBOX, **CLAY)
        assert envelope.call_args.kwargs["target_crs"] == "EPSG:2180"
        assert by_geometry.files[0].file.path == by_bbox.files[0].file.path
        assert by_bbox.files[0].file.status == "local"

    def test_geometry_gpkg_many_layers_notice(self, tmp_path):
        from kartograf.notices import GEOMETRY_LAYER_DEFAULT, Notice
        from tests.conftest import write_gpkg_layers

        gpkg = write_gpkg_layers(tmp_path / "area.gpkg", ["layer_a", "layer_b"])
        seen: list[Notice] = []
        with patch(
            "kartograf.core.geometry.get_overall_bbox", return_value=BBOX
        ) as envelope:
            area = _soil(tmp_path, FakeSoilGrids("2.0")).download(
                geometry=gpkg, on_notice=seen.append, **CLAY
            )
        expected = Notice(
            "info",
            GEOMETRY_LAYER_DEFAULT,
            "area.gpkg: liczba warstw 2, uzyto pierwszej 'layer_a' (pozostale: "
            "layer_b); inna warstwa: --layer NAZWA",
        )
        assert area.notices == (expected,) and seen == [expected]
        assert envelope.call_args.kwargs["layer"] == "layer_a"

    def test_corine_preview_notice(self, tmp_path):
        from kartograf.notices import CORINE_PREVIEW, Notice

        seen: list[Notice] = []
        with patch.object(CorineProvider, "has_clms_token", new=False):
            area = _corine(tmp_path, FakeCorine()).download(
                bbox=BBOX, year=2018, on_notice=seen.append
            )
        expected = Notice(
            "info",
            CORINE_PREVIEW,
            "CORINE 2018: podglad WMS (stylizowany PNG, nie dane; dane CLMS "
            "wymagaja CLMS_CREDENTIALS)",
        )
        assert area.notices == (expected,) and seen == [expected]
        assert seen[0] == area.notices[0]

    def test_check_matches_download_selection(self, tmp_path):
        """``check`` plans exactly the files ``download`` writes (BDOT10k area)."""
        manager = _bdot(tmp_path, FakePackages(), ["0208", "0224"])
        plan = manager.check(sheet="M-33-048-A", keep_raw=True)
        area = manager.download(sheet="M-33-048-A", keep_raw=True)
        planned = {(i.segment, i.hierarchy, i.name) for i in plan.items}
        written = {
            (
                f.path.parent.parent.relative_to(tmp_path).as_posix(),
                f.path.parent.name,
                f.path.name,
            )
            for r in area.files
            for f in (r.file, r.raw)
            if f is not None
        }
        assert planned == written and len(planned) == 4
