"""Plain output (``output_dir``, ADR-054) of the collections, land cover, soil and HSG.

The same service answers as the store tests of each track; what is checked is what a
caller sees of the plain write: the names, the report, the refusal of a second run,
``--force``, the plan and, for the HSG, that the inputs are not kept.
"""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from kartograf.download import collections
from kartograf.download.collections import check_collection, download_collection
from kartograf.exceptions import ConflictError, DownloadError, ValidationError
from kartograf.hydrology.hsg import HSGCalculator, calculate_hsg, check_hsg
from kartograf.landcover.manager import (
    LandCoverManager,
    check_soil,
    download_landcover,
    download_soil,
)
from kartograf.output import STAGING
from kartograf.providers.pl.bdot10k import Bdot10kProvider
from kartograf.transport.http import SessionPerThread
from tests.integration.test_collections import (
    AREA,
    LOD1_2024,
    _prg_route,
    _zip_route,
)
from tests.integration.test_hsg import BBOX, COORDS, RasterSoilGrids, _hsg
from tests.integration.test_landcover import _bdot_zip, _zip_session
from tests.support.fake_packages import FakePackageSession

# The line SG of ISRIC SoilGrids: it names no year and no day.
SG = (
    "Źródło: ISRIC – World Soil Information, SoilGrids, licencja CC BY 4.0 "
    "(https://creativecommons.org/licenses/by/4.0/); dane przetworzone"
)


def listing(directory: Path) -> list[str]:
    return sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))


def attribution(directory: Path) -> list[str]:
    return (directory / "ATTRIBUTION.txt").read_text(encoding="utf-8").splitlines()


@pytest.fixture(autouse=True)
def default_root(monkeypatch, tmp_path):
    """The default store lies in the test directory: it must stay untouched."""
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path / "default-store"))
    return tmp_path / "default-store"


@pytest.fixture
def session(monkeypatch):
    """A fake HTTP session for the collection engine (routes added by the test)."""
    fake = FakePackageSession({})
    monkeypatch.setattr(collections, "_session", lambda: fake)
    return fake


# --------------------------------------------------------------------------
# Collections
# --------------------------------------------------------------------------

URL_0208 = LOD1_2024.format(woj="02", teryt="0208")
URL_0224 = LOD1_2024.format(woj="02", teryt="0224")
AREA_OF_TWO_POWIATS = {
    "product": "buildings",
    "country": "pl",
    "bbox": AREA,
    "lod": 1,
    "year": 2024,
    "cache": False,
}


def _two_powiats(session):
    session.routes.update([_prg_route(), _zip_route(URL_0208), _zip_route(URL_0224)])


def test_a_plain_collection_is_one_file_per_unit_named_as_in_the_store(
    tmp_path, default_root, session, frozen_clock
):
    _two_powiats(session)
    out = tmp_path / "out"

    report = download_collection(output_dir=out, **AREA_OF_TWO_POWIATS)

    assert report.ok and report.failed == ()
    assert (report.mode, report.root, report.output_dir) == ("plain", None, out)
    assert [(f.unit, f.file.path, f.file.status) for f in report.files] == [
        ("0208", out / "0208.zip", "written"),
        ("0224", out / "0224.zip", "written"),
        ("ATTRIBUTION.txt", out / "ATTRIBUTION.txt", "written"),
    ]
    for unit_file in report.files[:2]:
        assert unit_file.file.label == "" and unit_file.file.version_path == (
            unit_file.file.path
        )
        assert unit_file.file.size_bytes == unit_file.file.path.stat().st_size
    # no sidecar, no versions/; one line G for both files of the year 2024
    assert listing(out) == ["0208.zip", "0224.zip", "ATTRIBUTION.txt"]
    assert attribution(out) == [
        "Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, Modele 3D budynków "
        "(wytworzono 2024, pozyskano 2026-10-12); dane przetworzone"
    ]
    assert not default_root.exists()
    document = report.to_dict()
    assert document["mode"] == "plain" and document["root"] is None
    assert document["output_dir"] == out.as_posix()
    assert document["attribution"] == attribution(out)
    assert document["terms_notice"] == []


def test_a_second_plain_collection_run_names_every_file_and_fetches_nothing(
    tmp_path, session, frozen_clock
):
    _two_powiats(session)
    out = tmp_path / "out"
    download_collection(output_dir=out, **AREA_OF_TWO_POWIATS)
    fetched = session.gets()

    with pytest.raises(ConflictError) as error:
        download_collection(output_dir=out, **AREA_OF_TWO_POWIATS)

    assert error.value.reason == "output_exists"
    assert error.value.details()["paths"] == [
        str(out / "0208.zip"),
        str(out / "0224.zip"),
    ]
    assert session.gets(URL_0208) == 1 and session.gets(URL_0224) == 1
    assert session.gets() == fetched + 1  # only the PRG query of the units again
    forced = download_collection(output_dir=out, update="force", **AREA_OF_TWO_POWIATS)
    # the same line on the same day: ATTRIBUTION.txt is left and not reported
    assert [f.file.status for f in forced.files] == ["replaced", "replaced"]
    assert listing(out) == ["0208.zip", "0224.zip", "ATTRIBUTION.txt"]


def test_the_plain_collection_plan_says_write_replace_or_conflict(
    tmp_path, session, frozen_clock
):
    _two_powiats(session)
    out = tmp_path / "out"

    before = check_collection(output_dir=out, **AREA_OF_TWO_POWIATS)
    download_collection(output_dir=out, **AREA_OF_TWO_POWIATS)
    refused = check_collection(output_dir=out, **AREA_OF_TWO_POWIATS)
    forced = check_collection(output_dir=out, force=True, **AREA_OF_TWO_POWIATS)

    assert (before.mode, before.root, before.output_dir) == (
        "plain",
        None,
        out.resolve().as_posix(),
    )
    assert [(i.name, i.action) for i in before.items] == [
        ("0208.zip", "write"),
        ("0224.zip", "write"),
        ("ATTRIBUTION.txt", "write"),
    ]
    assert [(i.action, i.reason) for i in refused.items] == [
        ("conflict", "output_exists")
    ] * 2
    # the line G names the day of the download: an existing file is replaced
    assert [(i.name, i.action, i.status) for i in forced.items][2:] == [
        ("ATTRIBUTION.txt", "replace", "unverifiable")
    ]
    assert [i.action for i in forced.items[:2]] == ["replace", "replace"]
    assert session.gets(URL_0208) == 1  # a plan fetches no data
    assert not out.joinpath(STAGING).exists()


def test_a_plain_collection_refuses_what_acts_on_versions_before_any_request(
    tmp_path, session
):
    out = tmp_path / "out"

    with pytest.raises(ValidationError) as upgrade:
        download_collection(output_dir=out, update="upgrade", **AREA_OF_TWO_POWIATS)
    with pytest.raises(ValidationError) as both:
        download_collection(output_dir=out, root=tmp_path / "s", **AREA_OF_TWO_POWIATS)

    assert (upgrade.value.reason, upgrade.value.option) == (
        "store_only_option",
        "--upgrade",
    )
    assert both.value.reason == "exclusive_options"
    assert session.calls == [] and not out.exists()


# --------------------------------------------------------------------------
# Land cover: BDOT10k with keep_raw, soil
# --------------------------------------------------------------------------


def _bdot_manager(tmp_path, out):
    body = _bdot_zip(tmp_path, ["OT_PTWP_A"])
    manager = LandCoverManager("bdot10k", output_dir=out, cache=False)
    provider = manager.provider
    assert isinstance(provider, Bdot10kProvider)
    provider._sessions = SessionPerThread(_zip_session(body))
    return manager, body


def test_bdot10k_with_keep_raw_writes_the_gpkg_the_original_zip_and_the_lines(
    tmp_path, frozen_clock
):
    out = tmp_path / "out"
    manager, body = _bdot_manager(tmp_path, out)

    report = manager.download(teryt="0262", keep_raw=True)

    assert report.ok and (report.mode, report.root) == ("plain", None)
    data, lines = report.files
    (raw,) = report.raw
    assert (data.file.path, data.file.status) == (out / "0262.gpkg", "written")
    assert (raw.file.path, raw.file.status) == (out / "0262.zip", "written")
    assert raw.file.path.read_bytes() == body
    assert (lines.file.path, lines.file.status) == (out / "ATTRIBUTION.txt", "written")
    # no sidecar names the package; one line G for the GeoPackage and its original
    assert listing(out) == ["0262.gpkg", "0262.zip", "ATTRIBUTION.txt"]
    assert attribution(out) == [
        "Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, BDOT10k "
        "(wytworzono b.d., pozyskano 2026-10-12); dane przetworzone"
    ]
    plan = manager.check(teryt="0262", keep_raw=True)
    assert [(i.name, i.action, i.reason) for i in plan.items] == [
        ("0262.gpkg", "conflict", "output_exists"),
        ("0262.zip", "conflict", "output_exists"),
    ]


def test_bdot10k_plain_is_refused_whole_when_one_file_exists(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "0262.zip").write_bytes(b"mine")
    manager, _ = _bdot_manager(tmp_path, out)
    provider = manager.provider

    with pytest.raises(ConflictError) as error:
        manager.download(teryt="0262", keep_raw=True)

    assert error.value.details()["paths"] == [str(out / "0262.zip")]
    assert (out / "0262.zip").read_bytes() == b"mine"
    assert listing(out) == ["0262.zip"]
    assert provider._sessions.get().get.call_count == 0  # nothing was fetched
    forced = manager.download(teryt="0262", keep_raw=True, update="force")
    assert [(f.unit, f.file.status) for f in forced.files] == [
        ("0262", "written"),
        ("ATTRIBUTION.txt", "written"),
    ]
    assert [f.file.status for f in forced.raw] == ["replaced"]


def test_land_cover_and_soil_take_output_dir_as_the_store_functions_take_root(
    tmp_path,
):
    out = tmp_path / "out"
    soil = RasterSoilGrids()
    with patch.object(
        LandCoverManager,
        "_get_provider_by_name",
        staticmethod(lambda name, cache=None: soil),
    ):
        report = download_soil(
            output_dir=out,
            bbox=BBOX,
            property="clay",
            depth="0-5cm",
            stat="mean",
            cache=False,
        )
        plan = check_soil(
            output_dir=out,
            bbox=BBOX,
            property="clay",
            depth="0-5cm",
            stat="mean",
            force=True,
            cache=False,
        )

    raster, lines = report.files
    assert (report.mode, raster.file.path, raster.file.status) == (
        "plain",
        out / f"{COORDS}.tif",
        "written",
    )
    assert lines.file.path == out / "ATTRIBUTION.txt"
    assert listing(out) == [f"{COORDS}.tif", "ATTRIBUTION.txt"]
    assert attribution(out) == [SG]
    # the file holds the line SG, which names no day: the plan does not replace it
    assert [i.action for i in plan.items] == ["replace"]
    assert soil.capabilities == 0  # the edition labels a version: a plain file has none
    with pytest.raises(ValidationError) as error:
        download_landcover(
            product="corine", year=2018, bbox=BBOX, output_dir=out, plan=plan
        )
    assert error.value.reason == "store_only_option"
    store = tmp_path / "store"
    store.mkdir()
    (store / "kartograf-store.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ConflictError) as in_store:  # before the first request
        download_landcover(
            product="bdot10k", teryt="0262", output_dir=store / "sub", cache=False
        )
    assert in_store.value.reason == "output_in_store"
    assert listing(store) == ["kartograf-store.json"]


# --------------------------------------------------------------------------
# HSG: the inputs go to the staging directory, only the result is written
# --------------------------------------------------------------------------


def test_the_hsg_and_its_line_are_the_only_files_of_a_plain_write(
    tmp_path, default_root
):
    out = tmp_path / "out"
    soil = RasterSoilGrids()

    report = HSGCalculator(soil, output_dir=out).calculate_hsg(bbox=BBOX, depth="0-5cm")

    assert report.ok and report.failed == () and report.inputs == ()
    assert (report.mode, report.root, report.output_dir) == ("plain", None, out)
    hsg, lines = report.files
    assert (hsg.file.path, hsg.file.status, hsg.file.label) == (
        out / f"{COORDS}.tif",
        "written",
        "",
    )
    assert np.all(_hsg(hsg.file.path) == 2)  # loam -> B
    assert soil.downloads == ["clay", "sand", "silt"]
    assert lines.file.path == out / "ATTRIBUTION.txt"
    # no input, no staging, no sidecar; the inputs add no line to the one of the HSG
    assert listing(out) == [f"{COORDS}.tif", "ATTRIBUTION.txt"]
    assert attribution(out) == [SG]
    assert not default_root.exists()


def test_a_second_hsg_run_is_refused_before_the_inputs_are_fetched(tmp_path):
    out = tmp_path / "out"
    HSGCalculator(RasterSoilGrids(), output_dir=out).calculate_hsg(
        bbox=BBOX, depth="0-5cm"
    )
    before = (out / f"{COORDS}.tif").read_bytes()
    again = RasterSoilGrids()

    with pytest.raises(ConflictError) as error:
        HSGCalculator(again, output_dir=out).calculate_hsg(bbox=BBOX, depth="0-5cm")

    assert error.value.details()["paths"] == [str(out / f"{COORDS}.tif")]
    assert again.downloads == []
    forced = HSGCalculator(again, output_dir=out).calculate_hsg(
        bbox=BBOX, depth="0-5cm", update="force"
    )
    assert [f.file.status for f in forced.files] == ["replaced"]
    assert (out / f"{COORDS}.tif").read_bytes() == before
    assert listing(out) == [f"{COORDS}.tif", "ATTRIBUTION.txt"]


def test_a_failed_hsg_input_leaves_no_result_and_no_staging_directory(tmp_path):
    out = tmp_path / "out"
    failing = RasterSoilGrids(rasters={"sand": DownloadError("brak odpowiedzi")})

    report = HSGCalculator(failing, output_dir=out).calculate_hsg(
        bbox=BBOX, depth="0-5cm"
    )

    assert not report.ok and report.files == ()
    assert [f.unit for f in report.failed] == [f"sand {COORDS}"]
    assert listing(out) == []


def test_the_hsg_plan_has_one_target_and_asks_the_source_nothing(tmp_path):
    out = tmp_path / "out"
    soil = RasterSoilGrids()
    HSGCalculator(soil, output_dir=out).calculate_hsg(bbox=BBOX, depth="0-5cm")

    with patch.object(
        LandCoverManager,
        "_get_provider_by_name",
        staticmethod(lambda name, cache=None: soil),
    ):
        refused = check_hsg(output_dir=out, bbox=BBOX, depth="0-5cm", cache=False)
        forced = check_hsg(
            output_dir=out, bbox=BBOX, depth="0-5cm", force=True, cache=False
        )
        new = check_hsg(output_dir=out / "new", bbox=BBOX, depth="0-5cm", cache=False)

    assert [(i.name, i.action, i.reason) for i in refused.items] == [
        (f"{COORDS}.tif", "conflict", "output_exists")
    ]
    assert [i.action for i in forced.items] == ["replace"]
    assert [(i.name, i.action) for i in new.items] == [
        (f"{COORDS}.tif", "write"),
        ("ATTRIBUTION.txt", "write"),
    ]
    assert (refused.mode, new.items[0].track) == ("plain", "hsg")
    assert soil.capabilities == 0  # no edition is asked for a plan of plain files
    assert not (out / "new").exists()


def test_calculate_hsg_function_reports_and_summarises_a_plain_write(tmp_path):
    out = tmp_path / "out"
    with patch.object(
        LandCoverManager,
        "_get_provider_by_name",
        staticmethod(lambda name, cache=None: RasterSoilGrids()),
    ):
        report = calculate_hsg(
            output_dir=out, bbox=BBOX, depth="0-5cm", summary=True, cache=False
        )
        with pytest.raises(ValidationError) as error:
            calculate_hsg(
                output_dir=out / "x", bbox=BBOX, depth="0-5cm", update="upgrade"
            )

    assert report.summary is not None and report.summary["B"]["percent"] == 100.0
    assert report.to_dict()["output_dir"] == out.as_posix()
    assert error.value.reason == "store_only_option"
    assert not (out / "x").exists()
