"""
LAZ range selection and sidecars on raw WFS XML recorded 2026-10-10 for W2_BBOX.

The w2 area has 2022/PL-2000:S7 tiles (two sheets, together covering the area)
and 2023/2025/PL-1992 tiles of one sheet.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.download.laz import (
    download_laz_area,
    laz_version_ref,
    write_laz_sidecar,
)
from kartograf.download.versions import read_content
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.providers.pl.gugik_laz import GugikLazProvider

REAL_LAZ = Path(__file__).parent.parent / "fixtures" / "gugik_laz" / "real_2026_10_10"
W2_BBOX = BBox(637200, 486900, 637500, 487100, "EPSG:2180")


def laz_session(*, replay_any_bbox: bool = False) -> MagicMock:
    """WFS: GetCapabilities and GetFeature from raw XML recorded for ``W2_BBOX``.

    ``replay_any_bbox`` serves the W2_BBOX bodies for another query window
    (a deliberate replay, not what the server answers for that window).
    """
    session = MagicMock()

    def get(url, **kwargs):
        query = parse_qs(urlparse(url).query)
        vcrs = "KRON86" if "LidarKRON86" in url else "EVRF2007"
        if query["REQUEST"][0] == "GetCapabilities":
            path = REAL_LAZ / f"caps_{vcrs}.xml"
        else:
            if not replay_any_bbox:
                # the bodies answer exactly this query window (axes N,E)
                assert query["BBOX"][0].startswith("486900,637200,487100,637500,")
            year = query["TYPENAMES"][0][-4:]
            path = REAL_LAZ / f"w2_{vcrs}_{year}.xml"
        response = MagicMock()
        response.text = path.read_text(encoding="utf-8")
        response.raise_for_status = MagicMock()
        return response

    session.get = MagicMock(side_effect=get)
    return session


def feature_years(session: MagicMock) -> list[str]:
    return [
        parse_qs(urlparse(call.args[0]).query)["TYPENAMES"][0][-4:]
        for call in session.get.call_args_list
        if "GetFeature" in call.args[0]
    ]


def test_c13_all_returns_both_systems_tiles():
    selection = GugikLazProvider(
        session=laz_session(), vertical_crs="EVRF2007"
    ).select_tiles(W2_BBOX, all_campaigns=True)
    keys = {(t.year, t.crs) for t in selection.tiles}
    assert (2022, "PL-2000:S7") in keys
    assert (2025, "PL-1992") in keys
    assert {t.system for t in selection.tiles} == {"1992", "2000"}
    assert not [s for s in selection.superseded if s.reason == "covered"]


def test_c13_newest_unchanged_single_tile():
    selection = GugikLazProvider(
        session=laz_session(), vertical_crs="EVRF2007"
    ).select_tiles(W2_BBOX)
    assert [(t.sheet, t.year) for t in selection.tiles] == [
        ("N-34-139-A-c-1-1-3-4", 2025)
    ]
    assert {s.reason for s in selection.superseded} == {"covered"}


def test_range_queries_every_service_year():
    session = laz_session()
    selection = GugikLazProvider(session=session, vertical_crs="EVRF2007").select_tiles(
        W2_BBOX, all_campaigns=True, min_year=2025
    )
    assert feature_years(session) == [str(y) for y in range(2026, 2017, -1)]
    assert {t.year for t in selection.tiles} == {2025}


def test_discover_tiles_max_year_uses_reference_coverage():
    tiles = GugikLazProvider(
        session=laz_session(), vertical_crs="EVRF2007"
    ).discover_tiles(W2_BBOX, max_year=2023)
    assert [(tile.sheet, tile.year) for tile in tiles] == [
        ("N-34-139-A-c-1-1-3-4", 2023)
    ]


def test_min_year_applies_to_newest_too():
    session = laz_session()
    provider = GugikLazProvider(session=session, vertical_crs="EVRF2007")
    selection = provider.select_tiles(W2_BBOX, min_year=2024)
    assert [(t.sheet, t.year) for t in selection.tiles] == [
        ("N-34-139-A-c-1-1-3-4", 2025)
    ]
    assert feature_years(session) == [str(y) for y in range(2026, 2017, -1)]


def test_min_year_above_service_years_rejected_without_get_feature():
    session = laz_session()
    with pytest.raises(
        DownloadError, match=("range.*2099.*no vintage in service EVRF2007")
    ):
        GugikLazProvider(session=session, vertical_crs="EVRF2007").select_tiles(
            W2_BBOX, all_campaigns=True, min_year=2099
        )
    assert feature_years(session) == []


@pytest.mark.parametrize(
    "bounds",
    [
        {"year": 2023, "min_year": 2024},
        {"year": 2023, "max_year": 2024},
        {"min_year": 2025, "max_year": 2023},
    ],
)
def test_laz_year_and_range_exclusive(bounds):
    session = laz_session()
    with pytest.raises(ValidationError):
        GugikLazProvider(session=session, vertical_crs="EVRF2007").select_tiles(
            W2_BBOX, **bounds
        )
    session.get.assert_not_called()


def test_all_still_drops_outside_tiles():
    # SW corner of the PL-2000 tile envelope: its footprint misses the area.
    # The live service filters such tiles itself (2026-10-10); replaying the
    # W2_BBOX bodies checks the client-side footprint filter behind it.
    area = BBox(637334, 486800, 637340, 486806, "EPSG:2180")
    selection = GugikLazProvider(
        session=laz_session(replay_any_bbox=True), vertical_crs="EVRF2007"
    ).select_tiles(area, all_campaigns=True)
    assert "7.173.21.06.2" not in {tile.sheet for tile in selection.tiles}
    (entry,) = (
        skipped
        for skipped in selection.superseded
        if skipped.tile.sheet == "7.173.21.06.2"
    )
    assert entry.reason == "outside"


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(path.name + ".meta.json").read_text("utf-8"))


class _Provider:
    descriptor_key = "pl.gugik.laz"
    vertical_crs = "EVRF2007"


def test_laz_sidecar_acquisition_date_and_max_year(tmp_path):
    bbox = W2_BBOX
    (tile,) = (
        GugikLazProvider(session=laz_session(), vertical_crs="EVRF2007")
        .select_tiles(bbox, year=2023)
        .tiles
    )
    target = tmp_path / "a.laz"
    target.write_bytes(b"LASF")
    digest = read_content(target, ext=".laz", coverage=False)
    version = laz_version_ref(tile)
    write_laz_sidecar(
        _Provider(),
        tile,
        target,
        bbox,
        all_campaigns=True,
        min_year=2022,
        max_year=2023,
        digest=digest,
        version=version,
    )
    meta = _meta(target)
    assert meta["request"]["campaigns"] == "all"
    assert meta["request"]["min_year"] == 2022
    assert meta["request"]["max_year"] == 2023
    assert "year" not in meta["request"]
    assert meta["extra"]["acquisition_date"] == "2023-09-05"
    assert meta["extra"]["full_sheet"] is True

    exact = tmp_path / "b.laz"
    exact.write_bytes(b"LASF")
    write_laz_sidecar(
        _Provider(),
        tile,
        exact,
        bbox,
        min_year=2023,
        max_year=2023,
        digest=digest,
        version=version,
    )
    assert _meta(exact)["request"]["year"] == 2023

    plain = tmp_path / "c.laz"
    plain.write_bytes(b"LASF")
    write_laz_sidecar(
        _Provider(), tile, plain, bbox, year=2023, digest=digest, version=version
    )
    request = _meta(plain)["request"]
    assert request["year"] == 2023
    assert "campaigns" not in request
    assert "min_year" not in request
    assert "max_year" not in request


def test_download_laz_area_all_writes_campaigns_to_sidecars(tmp_path):
    provider = GugikLazProvider(session=laz_session(), vertical_crs="EVRF2007")
    provider.download_tile = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda url, target, **kw: (
            target.parent.mkdir(parents=True, exist_ok=True),
            target.write_bytes(b"LASF"),
        )
    )
    result = download_laz_area(
        bbox=W2_BBOX,
        root=tmp_path,
        provider=provider,
        all_campaigns=True,
        min_year=2022,
        max_year=2023,
        vertical_crs="EVRF2007",
    )
    assert {(tile.year, tile.crs) for tile in result.tiles} == {
        (2022, "PL-2000:S7"),
        (2023, "PL-1992"),
    }
    for file in result.files:
        request = _meta(file.version_path)["request"]
        assert request["campaigns"] == "all"
        assert request["min_year"] == 2022
        assert request["max_year"] == 2023


@pytest.mark.parametrize("bad", ["2020", True, 1800])
def test_invalid_min_year_rejected_before_network(bad):
    """M-3: ``select_tiles`` validates ``min_year`` like ``DownloadManager``."""
    session = laz_session()
    with pytest.raises(ValidationError, match="min_year"):
        GugikLazProvider(session=session, vertical_crs="EVRF2007").select_tiles(
            W2_BBOX, min_year=bad
        )
    session.get.assert_not_called()
