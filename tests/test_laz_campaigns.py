"""
LAZ: the ``campaigns="all"`` strategy and ``min_year`` (ADR-030 j, library).

Offline: WFS from the raw XML of the 2026-10-06 round (area w2: tiles 2022/PL-2000:S7,
2023 and 2025/PL-1992). ``newest`` = ADR-029 unchanged (regression).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest

from kartograf.core.sheet_parser import BBox
from kartograf.download.laz import download_laz_area, write_laz_sidecar
from kartograf.exceptions import NoCoverageError, ValidationError
from kartograf.providers.pl.gugik_laz import GugikLazProvider, LazTile

REAL_LAZ = Path(__file__).parent / "fixtures" / "gugik_laz" / "real_2026_10_06"
W2_BBOX = BBox(637200, 486900, 637500, 487100, "EPSG:2180")


def laz_session() -> MagicMock:
    """WFS: GetCapabilities and GetFeature from raw XML of the 2026-10-06 round."""
    session = MagicMock()

    def get(url, **kwargs):
        query = parse_qs(urlparse(url).query)
        vcrs = "KRON86" if "LidarKRON86" in url else "EVRF2007"
        if query["REQUEST"][0] == "GetCapabilities":
            path = REAL_LAZ / f"caps_{vcrs}.xml"
        else:
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
    selection = GugikLazProvider(session=laz_session()).select_tiles(
        W2_BBOX, campaigns="all"
    )
    keys = {(t.year, t.crs) for t in selection.tiles}
    assert (2022, "PL-2000:S7") in keys
    assert (2025, "PL-1992") in keys
    assert {t.uklad for t in selection.tiles} == {"1992", "2000"}
    assert not [s for s in selection.superseded if s.reason == "covered"]


def test_c13_newest_unchanged_single_tile():
    selection = GugikLazProvider(session=laz_session()).select_tiles(
        W2_BBOX, campaigns="newest"
    )
    assert [(t.godlo, t.year) for t in selection.tiles] == [
        ("N-34-139-A-c-1-1-3-4", 2025)
    ]
    assert {s.reason for s in selection.superseded} == {"covered"}


def test_min_year_skips_older_year_layers():
    session = laz_session()
    selection = GugikLazProvider(session=session).select_tiles(
        W2_BBOX, campaigns="all", min_year=2025
    )
    years = feature_years(session)
    assert years and all(int(y) >= 2025 for y in years)
    assert "2025" in years
    assert {t.year for t in selection.tiles} == {2025}


def test_min_year_applies_to_newest_too():
    session = laz_session()
    provider = GugikLazProvider(session=session)
    selection = provider.select_tiles(W2_BBOX, min_year=2024)
    assert [(t.godlo, t.year) for t in selection.tiles] == [
        ("N-34-139-A-c-1-1-3-4", 2025)
    ]
    assert all(int(y) >= 2024 for y in feature_years(session))


def test_min_year_above_all_years_returns_empty_selection():
    session = laz_session()
    selection = GugikLazProvider(session=session).select_tiles(
        W2_BBOX, campaigns="all", min_year=2099
    )
    assert selection.tiles == ()
    assert selection.superseded == ()
    assert feature_years(session) == []


def test_year_and_min_year_are_exclusive():
    provider = GugikLazProvider(session=laz_session())
    with pytest.raises(ValidationError, match="wykluczaja"):
        provider.select_tiles(W2_BBOX, year=2023, min_year=2024)


def test_unknown_campaigns_value_rejected():
    provider = GugikLazProvider(session=laz_session())
    with pytest.raises(ValidationError, match="Nieznana strategia kampanii"):
        provider.select_tiles(W2_BBOX, campaigns="coverage")


def test_all_still_drops_outside_tiles():
    # SW corner of the PL-2000 tile envelope: the envelope intersects the area, the
    # polygon does not
    area = BBox(637334, 486800, 637340, 486806, "EPSG:2180")
    selection = GugikLazProvider(session=laz_session()).select_tiles(
        area, year=2022, campaigns="all"
    )
    assert selection.tiles == ()
    (entry,) = selection.superseded
    assert entry.tile.godlo == "7.173.21.06.2"
    assert entry.reason == "outside"


def _tile() -> LazTile:
    return LazTile(
        godlo="N-33-131-B-a-1-1-4",
        url="https://opendata.geoportal.gov.pl/x/81121_1_N-33-131-B-a-1-1-4.laz",
        year=2024,
        density=25,
        crs="PL-2000:S6",
        min_x=530500,
        min_y=382500,
        max_x=531000,
        max_y=383000,
    )


def _meta(path: Path) -> dict:
    return json.loads(path.with_name(path.name + ".meta.json").read_text("utf-8"))


class _Provider:
    descriptor_key = "pl.gugik.laz"
    vertical_crs = "EVRF2007"


def test_sidecar_request_records_campaigns_and_min_year(tmp_path):
    bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
    target = tmp_path / "a.laz"
    write_laz_sidecar(
        _Provider(), _tile(), target, bbox, campaigns="all", min_year=2024
    )
    request = _meta(target)["request"]
    assert request["campaigns"] == "all"
    assert request["min_year"] == 2024

    plain = tmp_path / "b.laz"
    write_laz_sidecar(_Provider(), _tile(), plain, bbox)
    request = _meta(plain)["request"]
    assert "campaigns" not in request  # newest = unchanged relative to ADR-029
    assert "min_year" not in request


def test_download_laz_area_passes_campaigns(tmp_path):
    provider = MagicMock()
    provider.vertical_crs = "EVRF2007"
    provider.select_tiles.return_value = MagicMock(tiles=(), superseded=())
    with pytest.raises(NoCoverageError):
        download_laz_area(
            W2_BBOX,
            output_dir=tmp_path,
            provider=provider,
            campaigns="all",
            min_year=2024,
        )
    kwargs = provider.select_tiles.call_args.kwargs
    assert kwargs["campaigns"] == "all"
    assert kwargs["min_year"] == 2024


def test_download_laz_area_all_writes_campaigns_to_sidecars(tmp_path):
    provider = GugikLazProvider(session=laz_session())
    provider.download = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda url, target, **kw: (
            target.parent.mkdir(parents=True, exist_ok=True),
            target.write_bytes(b"LASF"),
        )
    )
    result = download_laz_area(
        W2_BBOX,
        output_dir=tmp_path,
        provider=provider,
        campaigns="all",
        min_year=2022,
    )
    assert len(result.downloaded) >= 2
    for path in result.downloaded:
        request = _meta(path)["request"]
        assert request["campaigns"] == "all"
        assert request["min_year"] == 2022


@pytest.mark.parametrize("bad", ["2020", True, 1800])
def test_invalid_min_year_rejected_before_network(bad):
    """M-3: ``select_tiles`` validates ``min_year`` like ``DownloadManager``."""
    session = laz_session()
    with pytest.raises(ValidationError, match="min_year"):
        GugikLazProvider(session=session).select_tiles(W2_BBOX, min_year=bad)
    session.get.assert_not_called()
