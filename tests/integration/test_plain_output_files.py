"""Plain output (``output_dir``, ADR-054) of the file tracks of both countries.

Each track answers with the fakes of its store tests (``test_laz_download.py``,
``test_wcs_cutout.py``, ``test_cz_sheets.py``, ``test_cz_cutout.py``,
``test_orto_cutout.py``, ``test_cz_contours.py``); what is checked is what a caller
sees of the plain write: the names, the report, the refusal of a second run before the
first byte, ``--force``, the plan and the options that need a store. The CZ LAZ track
and the PL sheets are in ``test_plain_output.py``.
"""

import hashlib
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import rasterio

from kartograf.download.cutout import check_pl_cutout, download_pl_cutout
from kartograf.download.cz_cutout import check_cz_cutout, download_cz_cutout
from kartograf.download.cz_sheets import check_cz_sheet, download_cz_sheet
from kartograf.download.data import download_data
from kartograf.download.laz import check_laz_area, download_laz_area
from kartograf.download.orto_cutout import check_image_cutout, download_image_cutout
from kartograf.exceptions import ConflictError, ValidationError
from kartograf.output import STAGING
from kartograf.providers.pl.gugik_laz import GugikLazProvider
from kartograf.providers.pl.prg import LandMask
from tests.integration.test_cz_contours import AREA as CONTOURS_AREA
from tests.integration.test_cz_contours import _url as contours_url
from tests.integration.test_cz_contours import openzu  # noqa: F401
from tests.integration.test_cz_cutout import SELECTION as CZ_CUTOUT
from tests.integration.test_cz_cutout import B as CZ_BBOX
from tests.integration.test_cz_cutout import _provider as cz_cutout_provider
from tests.integration.test_cz_sheets import _SHEET as CZ_SHEET
from tests.integration.test_cz_sheets import _TM33, SheetProvider
from tests.integration.test_cz_sheets import _factory as sheet_factory
from tests.integration.test_laz_download import downloaded_urls, wfs_session
from tests.integration.test_orto_cutout import FIXTURES as ORTO_FIXTURES
from tests.integration.test_orto_cutout import KRAKOW, ORTO, SESSION_FACTORY
from tests.integration.test_orto_cutout import _session as orto_session
from tests.integration.test_wcs_cutout import (
    ALL_LAND,
    ARGS,
    BBOX,
    MASK,
    _recorded_session,
    _square,
    _synthetic_session,
)
from tests.integration.test_wcs_cutout import _factory as wcs_factory


def listing(directory: Path) -> list[str]:
    return sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))


@pytest.fixture(autouse=True)
def default_root(monkeypatch, tmp_path):
    """The default store lies in the test directory: it must stay untouched."""
    monkeypatch.setenv("KARTOGRAF_ROOT", str(tmp_path / "default-store"))
    return tmp_path / "default-store"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# PL LAZ: the four tiles of one sheet
# --------------------------------------------------------------------------

LAZ = {"sheet": "N-34-130-D-d-2-4", "vertical_crs": "EVRF2007", "cache": False}
LAZ_BYTES = b"LASF\x01"  # what ``wfs_session`` answers for every tile


def _laz_provider(session):
    return GugikLazProvider(session=session, vertical_crs="EVRF2007")


def _laz_names(session) -> list[str]:
    """The file names of the tiles a run fetched: the names of their URLs."""
    return sorted(url.rsplit("/", 1)[-1] for url in downloaded_urls(session))


def test_plain_laz_tiles_are_flat_files_named_by_their_urls(tmp_path, default_root):
    session = wfs_session("sheet4")
    out = tmp_path / "out"

    result = download_laz_area(output_dir=out, provider=_laz_provider(session), **LAZ)

    names = _laz_names(session)
    assert result.ok and len(names) == 4
    assert listing(out) == names  # no segment, sidecar, versions/ or staging
    assert sorted(file.path.name for file in result.files) == names
    for file in result.files:
        assert (file.status, file.label, file.version_path) == (
            "written",
            "",
            file.path,
        )
        assert file.size_bytes == len(LAZ_BYTES)
        assert file.sha256 == hashlib.sha256(LAZ_BYTES).hexdigest()
    assert not default_root.exists()


def test_a_second_laz_run_names_every_existing_tile_before_the_first_byte(tmp_path):
    out = tmp_path / "out"
    first = wfs_session("sheet4")
    download_laz_area(output_dir=out, provider=_laz_provider(first), **LAZ)
    names = _laz_names(first)
    (out / names[0]).write_bytes(b"edited")

    again = wfs_session("sheet4")
    with pytest.raises(ConflictError) as error:
        download_laz_area(output_dir=out, provider=_laz_provider(again), **LAZ)

    assert error.value.reason == "output_exists"
    assert sorted(error.value.details()["paths"]) == [str(out / n) for n in names]
    assert downloaded_urls(again) == []  # the WFS was asked, no tile was fetched
    assert (out / names[0]).read_bytes() == b"edited"

    forced = download_laz_area(
        output_dir=out,
        update="force",
        provider=_laz_provider(wfs_session("sheet4")),
        **LAZ,
    )

    assert [file.status for file in forced.files] == ["replaced"] * 4
    assert (out / names[0]).read_bytes() == LAZ_BYTES
    assert listing(out) == names


def test_the_laz_plan_lists_each_tile_with_its_action_and_fetches_none(tmp_path):
    out = tmp_path / "out"
    session = wfs_session("sheet4")

    before = check_laz_area(output_dir=out, provider=_laz_provider(session), **LAZ)
    download_laz_area(output_dir=out, provider=_laz_provider(session), **LAZ)
    after = check_laz_area(output_dir=out, provider=_laz_provider(session), **LAZ)

    names = _laz_names(session)
    assert (before.mode, before.root, before.output_dir) == (
        "plain",
        None,
        str(out.resolve()),
    )
    assert [(i.action, i.status) for i in before.items] == [("write", "missing")] * 4
    assert sorted(i.path.name for i in before.items) == names
    assert [(i.action, i.reason) for i in after.items] == [
        ("conflict", "output_exists")
    ] * 4
    assert len(downloaded_urls(session)) == 4  # only the run fetched tiles
    assert not out.joinpath(STAGING).exists()


def test_every_campaign_needs_the_store_and_is_refused_before_the_wfs(tmp_path):
    session = wfs_session("sheet4")
    out = tmp_path / "out"

    with pytest.raises(ValidationError) as error:
        download_laz_area(
            output_dir=out, all_campaigns=True, provider=_laz_provider(session), **LAZ
        )

    assert (error.value.reason, error.value.option) == (
        "store_only_option",
        "--all-campaigns",
    )
    session.get.assert_not_called()
    assert not out.exists()


# --------------------------------------------------------------------------
# PL cutout (WCS): one file, the counts of the run
# --------------------------------------------------------------------------


def _pl_values(xs, ys):
    return np.where(xs < 567585.5, 0.0, 7.0)


def test_a_plain_pl_cutout_has_the_store_name_raster_and_mask_counts(
    tmp_path, default_root
):
    # land = the western half of the window; on land 5 zero columns (test_wcs_cutout)
    land = LandMask((_square(500000, 200000, 567590.5, 300000),), ())
    out = tmp_path / "out"
    with wcs_factory(_synthetic_session(_pl_values)), patch(MASK, return_value=land):
        plain = download_pl_cutout(bbox=BBOX, output_dir=out, cache=False, **ARGS)
    with wcs_factory(_synthetic_session(_pl_values)), patch(MASK, return_value=land):
        stored = download_pl_cutout(
            bbox=BBOX, root=tmp_path / "store", cache=False, **ARGS
        )

    assert plain.file is not None and stored.file is not None
    assert plain.file.path == out / stored.file.path.name
    assert (plain.file.status, plain.file.label) == ("written", "")
    assert plain.file.version_path == plain.file.path
    counts = (plain.masked_pixels, plain.zero_pixels, plain.all_nodata)
    assert counts == (stored.masked_pixels, stored.zero_pixels, stored.all_nodata)
    assert counts == (200, 100, False)  # no sidecar to read them from
    with rasterio.open(plain.file.path) as a, rasterio.open(stored.file.path) as b:
        np.testing.assert_array_equal(a.read(1), b.read(1))
        assert a.nodata == b.nodata and a.crs == b.crs
    assert plain.file.sha256 == sha256(plain.file.path) == stored.file.sha256
    assert listing(out) == [plain.file.path.name]
    assert not default_root.exists()


def test_a_second_plain_pl_cutout_is_refused_before_the_mask_and_force_replaces(
    tmp_path,
):
    out = tmp_path / "out"
    with wcs_factory(_recorded_session()), patch(MASK, return_value=ALL_LAND):
        first = download_pl_cutout(bbox=BBOX, output_dir=out, cache=False, **ARGS)
    assert first.file is not None
    target = first.file.path
    target.write_bytes(b"edited")

    session = _recorded_session()
    with (
        wcs_factory(session),
        patch(MASK) as mask,
        pytest.raises(ConflictError) as error,
    ):
        download_pl_cutout(bbox=BBOX, output_dir=out, cache=False, **ARGS)

    assert error.value.reason == "output_exists"
    assert error.value.details()["paths"] == [str(target)]
    session.get.assert_not_called()
    mask.assert_not_called()
    assert target.read_bytes() == b"edited"

    with wcs_factory(_recorded_session()), patch(MASK, return_value=ALL_LAND):
        forced = download_pl_cutout(
            bbox=BBOX, output_dir=out, update="force", cache=False, **ARGS
        )

    assert forced.file is not None and forced.file.status == "replaced"
    assert target.read_bytes() != b"edited"
    assert listing(out) == [target.name]


def test_the_plain_pl_cutout_plan_asks_neither_the_mask_nor_the_service(tmp_path):
    out = tmp_path / "out"
    with patch(MASK) as mask:
        before = check_pl_cutout(bbox=BBOX, output_dir=out, cache=False, **ARGS)
    with wcs_factory(_recorded_session()), patch(MASK, return_value=ALL_LAND):
        done = download_pl_cutout(bbox=BBOX, output_dir=out, cache=False, **ARGS)
    with patch(MASK) as mask:
        after = check_pl_cutout(bbox=BBOX, output_dir=out, cache=False, **ARGS)

    assert done.file is not None
    assert (before.mode, before.root, before.output_dir) == (
        "plain",
        None,
        str(out.resolve()),
    )
    (planned,) = before.items
    assert (planned.action, planned.status, planned.path) == (
        "write",
        "missing",
        done.file.path,
    )
    (refused,) = after.items
    assert (refused.action, refused.reason) == ("conflict", "output_exists")
    mask.assert_not_called()
    assert not out.joinpath(STAGING).exists()


def test_a_plain_pl_cutout_refuses_what_acts_on_versions_before_any_request(tmp_path):
    session = _recorded_session()
    with wcs_factory(session), patch(MASK) as mask:
        with pytest.raises(ValidationError) as upgrade:
            download_pl_cutout(
                bbox=BBOX,
                output_dir=tmp_path / "out",
                update="upgrade",
                cache=False,
                **ARGS,
            )
        with pytest.raises(ValidationError) as both:
            download_pl_cutout(
                bbox=BBOX,
                output_dir=tmp_path / "out",
                root=tmp_path / "store",
                cache=False,
                **ARGS,
            )

    assert (upgrade.value.reason, upgrade.value.option) == (
        "store_only_option",
        "--upgrade",
    )
    assert both.value.reason == "exclusive_options"
    session.get.assert_not_called()
    mask.assert_not_called()
    assert not (tmp_path / "out").exists()


# --------------------------------------------------------------------------
# CZ sheets: a file route (SM5) and an ImageServer tile (TM33)
# --------------------------------------------------------------------------

SHEETS = {"product": "nmt", "vertical_crs": "Bpv", "cache": False}


def test_a_plain_cz_sheet_is_one_file_named_by_the_sheet_and_asks_no_signal(
    tmp_path, default_root
):
    provider = SheetProvider()
    out = tmp_path / "out"

    with sheet_factory(provider):
        result = download_cz_sheet(sheet=CZ_SHEET, output_dir=out, **SHEETS)

    file = result.file
    assert file is not None
    assert file.path == out / f"{CZ_SHEET}.tif"
    assert (file.status, file.label, file.version_path) == ("written", "", file.path)
    assert file.size_bytes == file.path.stat().st_size
    assert file.sha256 == sha256(file.path)
    assert (provider.fetches, provider.heads) == (1, 0)  # no HEAD in plain mode
    assert listing(out) == [f"{CZ_SHEET}.tif"]
    assert not default_root.exists()


def test_a_plain_cz_tile_of_the_image_server_is_named_by_its_tile(tmp_path):
    provider = SheetProvider(sm5=False)
    out = tmp_path / "out"

    with sheet_factory(provider):
        result = download_cz_sheet(
            sheet=_TM33, output_dir=out, resolution="2m", **SHEETS
        )

    assert result.file is not None and result.file.path == out / f"{_TM33}.tif"
    assert result.file.status == "written"
    assert listing(out) == [f"{_TM33}.tif"]


def test_a_second_plain_cz_sheet_is_refused_before_the_transfer_and_force_replaces(
    tmp_path,
):
    provider = SheetProvider()
    out = tmp_path / "out"
    with sheet_factory(provider):
        download_cz_sheet(sheet=CZ_SHEET, output_dir=out, **SHEETS)
    target = out / f"{CZ_SHEET}.tif"
    target.write_bytes(b"edited")

    with sheet_factory(provider), pytest.raises(ConflictError) as error:
        download_cz_sheet(sheet=CZ_SHEET, output_dir=out, **SHEETS)

    assert error.value.reason == "output_exists"
    assert error.value.details()["paths"] == [str(target)]
    assert (provider.fetches, provider.heads) == (1, 0)
    assert target.read_bytes() == b"edited"

    with sheet_factory(provider):
        forced = download_cz_sheet(
            sheet=CZ_SHEET, output_dir=out, update="force", **SHEETS
        )

    assert forced.file is not None and forced.file.status == "replaced"
    assert (provider.fetches, provider.heads) == (2, 0)
    assert target.read_bytes() != b"edited"
    assert listing(out) == [target.name]


def test_the_plain_cz_sheet_plan_probes_nothing(tmp_path):
    provider = SheetProvider()
    out = tmp_path / "out"
    with sheet_factory(provider):
        before = check_cz_sheet(sheet=CZ_SHEET, output_dir=out, **SHEETS)
        download_cz_sheet(sheet=CZ_SHEET, output_dir=out, **SHEETS)
        after = check_cz_sheet(sheet=CZ_SHEET, output_dir=out, **SHEETS)

    (planned,) = before.items
    assert (planned.action, planned.status, planned.path, planned.track) == (
        "write",
        "missing",
        out / f"{CZ_SHEET}.tif",
        "cz_sheet",
    )
    (refused,) = after.items
    assert (refused.action, refused.reason) == ("conflict", "output_exists")
    assert (provider.fetches, provider.heads) == (1, 0)
    assert not out.joinpath(STAGING).exists()


# --------------------------------------------------------------------------
# CZ cutout (ImageServer)
# --------------------------------------------------------------------------


def _cz_provider_factory(monkeypatch, provider):
    monkeypatch.setattr(
        "kartograf.providers.cuzk.create_cz_raster_provider", lambda **_kw: provider
    )


def test_a_plain_cz_cutout_has_the_store_name_and_still_flags_an_empty_raster(
    tmp_path, monkeypatch, default_root
):
    out = tmp_path / "out"
    provider = cz_cutout_provider(-9999.0)
    _cz_provider_factory(monkeypatch, provider)
    notices = []

    plain = download_cz_cutout(
        bbox=CZ_BBOX, output_dir=out, cache=False, on_notice=notices.append, **CZ_CUTOUT
    )
    stored = download_cz_cutout(
        bbox=CZ_BBOX, root=tmp_path / "store", cache=False, **CZ_CUTOUT
    )

    assert plain.file is not None and stored.file is not None
    assert plain.file.path == out / stored.file.path.name
    assert (plain.file.status, plain.file.label) == ("written", "")
    assert plain.file.version_path == plain.file.path
    assert plain.file.sha256 == sha256(plain.file.path)
    assert plain.all_nodata is stored.all_nodata is True  # no sidecar to read it from
    assert [n.code for n in notices] == ["all_nodata"]
    assert str(plain.file.path) in notices[0].message
    assert listing(out) == [plain.file.path.name]
    assert not default_root.exists()


def test_a_second_plain_cz_cutout_is_refused_before_the_service_and_force_replaces(
    tmp_path, monkeypatch
):
    out = tmp_path / "out"
    provider = cz_cutout_provider(300.0)
    _cz_provider_factory(monkeypatch, provider)
    first = download_cz_cutout(bbox=CZ_BBOX, output_dir=out, cache=False, **CZ_CUTOUT)
    assert first.file is not None
    target = first.file.path
    target.write_bytes(b"edited")

    with pytest.raises(ConflictError) as error:
        download_cz_cutout(bbox=CZ_BBOX, output_dir=out, cache=False, **CZ_CUTOUT)

    assert error.value.reason == "output_exists"
    assert error.value.details()["paths"] == [str(target)]
    provider.download_bbox.assert_called_once()
    assert target.read_bytes() == b"edited"

    forced = download_cz_cutout(
        bbox=CZ_BBOX, output_dir=out, update="force", cache=False, **CZ_CUTOUT
    )

    assert forced.file is not None and forced.file.status == "replaced"
    assert provider.download_bbox.call_count == 2
    assert target.read_bytes() != b"edited"
    assert listing(out) == [target.name]


def test_the_plain_cz_cutout_plan_says_write_then_conflict(tmp_path, monkeypatch):
    out = tmp_path / "out"
    provider = cz_cutout_provider(1.0)
    _cz_provider_factory(monkeypatch, provider)

    before = check_cz_cutout(bbox=CZ_BBOX, output_dir=out, cache=False, **CZ_CUTOUT)
    done = download_cz_cutout(bbox=CZ_BBOX, output_dir=out, cache=False, **CZ_CUTOUT)
    after = check_cz_cutout(bbox=CZ_BBOX, output_dir=out, cache=False, **CZ_CUTOUT)

    assert done.file is not None
    (planned,) = before.items
    assert (planned.action, planned.status, planned.path, planned.track) == (
        "write",
        "missing",
        done.file.path,
        "cz_cutout",
    )
    (refused,) = after.items
    assert (refused.action, refused.reason) == ("conflict", "output_exists")
    provider.download_bbox.assert_called_once()
    assert not out.joinpath(STAGING).exists()


# --------------------------------------------------------------------------
# PL orthophotomap cutout (WCS)
# --------------------------------------------------------------------------


def test_a_plain_image_cutout_is_the_server_geotiff_under_the_store_name(
    tmp_path, default_root
):
    out = tmp_path / "out"
    with patch(SESSION_FACTORY, return_value=orto_session()):
        plain = download_image_cutout(bbox=KRAKOW, output_dir=out, cache=False, **ORTO)
    with patch(SESSION_FACTORY, return_value=orto_session()):
        stored = download_image_cutout(
            bbox=KRAKOW, root=tmp_path / "store", cache=False, **ORTO
        )

    assert plain.file is not None and stored.file is not None
    assert plain.file.path == out / stored.file.path.name
    assert (plain.file.status, plain.file.label) == ("written", "")
    assert plain.file.version_path == plain.file.path
    # one chunk: the server's GeoTIFF byte for byte
    recorded = (ORTO_FIXTURES / "standard_0.25m_4x4.tif").read_bytes()
    assert plain.file.path.read_bytes() == recorded
    assert plain.file.sha256 == hashlib.sha256(recorded).hexdigest()
    assert listing(out) == [plain.file.path.name]
    assert not default_root.exists()


def test_a_second_plain_image_cutout_is_refused_before_the_service_and_force_replaces(
    tmp_path,
):
    out = tmp_path / "out"
    with patch(SESSION_FACTORY, return_value=orto_session()):
        first = download_image_cutout(bbox=KRAKOW, output_dir=out, cache=False, **ORTO)
    assert first.file is not None
    target = first.file.path
    target.write_bytes(b"edited")

    with patch(SESSION_FACTORY) as factory, pytest.raises(ConflictError) as error:
        download_image_cutout(bbox=KRAKOW, output_dir=out, cache=False, **ORTO)

    assert error.value.reason == "output_exists"
    assert error.value.details()["paths"] == [str(target)]
    factory.assert_not_called()
    assert target.read_bytes() == b"edited"

    forced_session = orto_session()
    with patch(SESSION_FACTORY, return_value=forced_session):
        forced = download_image_cutout(
            bbox=KRAKOW, output_dir=out, update="force", cache=False, **ORTO
        )

    assert forced.file is not None and forced.file.status == "replaced"
    assert forced_session.get.call_count == 1
    assert (
        target.read_bytes() == (ORTO_FIXTURES / "standard_0.25m_4x4.tif").read_bytes()
    )
    assert listing(out) == [target.name]


def test_the_plain_image_cutout_plan_contacts_no_service(tmp_path):
    out = tmp_path / "out"
    with patch(SESSION_FACTORY) as factory:
        before = check_image_cutout(bbox=KRAKOW, output_dir=out, cache=False, **ORTO)
    with patch(SESSION_FACTORY, return_value=orto_session()):
        done = download_image_cutout(bbox=KRAKOW, output_dir=out, cache=False, **ORTO)
    with patch(SESSION_FACTORY) as factory:
        after = check_image_cutout(bbox=KRAKOW, output_dir=out, cache=False, **ORTO)

    assert done.file is not None
    (planned,) = before.items
    assert (planned.action, planned.status, planned.path, planned.track) == (
        "write",
        "missing",
        done.file.path,
        "pl_cutout",
    )
    (refused,) = after.items
    assert (refused.action, refused.reason) == ("conflict", "output_exists")
    factory.assert_not_called()
    assert not out.joinpath(STAGING).exists()


# --------------------------------------------------------------------------
# CZ contours: the published ZIP, one per SM5 sheet
# --------------------------------------------------------------------------

CONTOURS = {"product": "contours", "format": "SHP", "cache": False}


def test_a_plain_contour_sheet_is_the_published_zip_named_by_the_sheet(
    tmp_path,
    openzu,  # noqa: F811
    default_root,
):
    out = tmp_path / "out"

    report = download_data(sheet="CTES96", output_dir=out, **CONTOURS)

    assert report.ok
    (unit,) = report.files
    zipped = openzu.files[contours_url("SHP", "CTES96")][0]
    assert unit.file.path == out / "CTES96.zip"
    assert unit.file.path.read_bytes() == zipped  # not unpacked
    assert (unit.file.status, unit.file.label) == ("written", "")
    assert unit.file.sha256 == hashlib.sha256(zipped).hexdigest()
    assert listing(out) == ["CTES96.zip"]
    assert ("HEAD", contours_url("SHP", "CTES96")) not in openzu.calls
    assert not default_root.exists()


def test_a_second_plain_contour_run_names_every_zip_before_the_first_byte(
    tmp_path,
    openzu,  # noqa: F811
):
    out = tmp_path / "out"
    request = {"country": "cz", "bbox": CONTOURS_AREA, "output_dir": out, **CONTOURS}
    first = download_data(**request)
    assert sorted(unit.unit for unit in first.files) == ["CTES86", "CTES96"]
    assert listing(out) == ["CTES86.zip", "CTES96.zip"]
    fetched = len(openzu.zip_gets())

    with pytest.raises(ConflictError) as error:
        download_data(**request)

    assert error.value.reason == "output_exists"
    assert sorted(error.value.details()["paths"]) == [
        str(out / "CTES86.zip"),
        str(out / "CTES96.zip"),
    ]
    assert len(openzu.zip_gets()) == fetched  # nothing was transferred again

    forced = download_data(update="force", **request)

    assert [unit.file.status for unit in forced.files] == ["replaced", "replaced"]
    assert len(openzu.zip_gets()) == fetched + 2
    assert listing(out) == ["CTES86.zip", "CTES96.zip"]
