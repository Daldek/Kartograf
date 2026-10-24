"""
Campaigns in the GUGiK providers (ADR-030): ``resolve_campaigns``,
``download_record``, ``record_source`` on RAW index (skorowidz) responses.

NMT/NMPT: WFS answers recorded 2026-10-15
(``tests/fixtures/gugik_wfs/real_2026_10_15/``) replayed by ``recorded_wfs``
of ``tests/unit/test_real_gugik_responses.py``; feature types of the services from
the autouse stub in ``tests/conftest.py``. Orthophoto: WMS bodies of
``tests/fixtures/gugik_skorowidz/real_2026_10_06/`` (E2E round 2026-10-06)
and ``real_2026_10_10/`` (year-range round); GetCapabilities layers from the
autouse stub.
"""

import re
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.exceptions import (
    DownloadError,
    NoCoverageError,
    YearRangeError,
)
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.sources.variants import source_format
from tests.conftest import wfs_endpoint, wfs_fixture, wfs_requests, wfs_types
from tests.unit.test_real_gugik_responses import EMPTY_WFS, recorded_wfs

REAL = Path(__file__).parent.parent / "fixtures" / "gugik_skorowidz" / "real_2026_10_06"
REAL_10_10 = REAL.parent / "real_2026_10_10"
EMPTY = (
    Path(__file__).parent.parent / "fixtures" / "gugik_skorowidz" / "empty.body"
).read_text(encoding="utf-8")

# NMT 1 m EVRF2007 grids of the recorded answers. G: 2021, 2022, two flights
# of 2024 and the 2019 grid of campaign 72675 published under a `.xyz` name;
# H: 2019 and 2022-2025.
G = "N-33-69-A-d-1-3"
H = "M-34-64-D-d-2-1"
NMT_EVRF2007 = wfs_endpoint("nmt_evrf2007")


def _key(sheet: str) -> tuple[str, str, str, str]:
    """Metadata cache key of a sheet of the NMT 1 m EVRF2007 variant."""
    return ("pl.gugik.nmt_1m", "1m", "EVRF2007", sheet)


def _response(body: str) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.text = body
    response.raise_for_status = Mock()
    return response


def _layer_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["LAYERS"][0]


def routed_session(path_for_layer) -> Mock:
    """GetFeatureInfo -> the raw layer body; an OpenData file -> ``b"DATA"``."""
    session = Mock(spec=requests.Session)

    def get(url, **kwargs):
        if url.startswith("https://opendata.geoportal.gov.pl/"):
            response = _response("")
            response.iter_content = Mock(return_value=[b"DATA"])
            return response
        path = path_for_layer(_layer_of(url))
        body = path.read_text(encoding="utf-8") if path else EMPTY
        return _response(body)

    session.get = Mock(side_effect=get)
    return session


def orto_session(sheet: str, base: Path = REAL) -> Mock:
    def path_for_layer(layer):
        path = base / "orto" / f"{sheet}_{layer}.html"
        return path if path.exists() else None

    return routed_session(path_for_layer)


def queried_layers(session: Mock) -> list[str]:
    return [
        _layer_of(call.args[0])
        for call in session.get.call_args_list
        if "LAYERS=" in call.args[0]
    ]


def file_id(url: str) -> str:
    """``78954_1462161`` from ``.../78954/78954_1462161_M-33-57-C-b-4-2.asc``."""
    return "_".join(url.rsplit("/", 1)[-1].split("_")[:2])


def ids(records) -> list[str]:
    return [file_id(r.url).split("_")[0] for r in records]


# =============================================================================
# newest = ADR-028
# =============================================================================


def test_newest_is_adr028_record():
    p = GugikProvider(session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m")
    [r] = p.resolve_campaigns(G)
    assert file_id(r.url) == "81025_1562189"


def test_newest_min_year_after_newest_campaign_is_year_range_error():
    with pytest.raises(YearRangeError) as exc:
        GugikProvider(
            session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(G, min_year=2025)
    assert exc.value.sheets == {G: (2019, 2021, 2022, 2024)}
    assert "--min-year 2024" in exc.value.hints[0]


def test_newest_min_year_does_not_narrow_the_index_query():
    s = recorded_wfs()
    with pytest.raises(YearRangeError) as exc:
        GugikProvider(
            session=s, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(H, min_year=2026)
    assert exc.value.sheets == {H: (2019, 2022, 2023, 2024, 2025)}
    # one GetFeature with every yearly type: a record counts by its
    # acquisition year, not by the type that publishes it
    assert [query["TYPENAMES"] for query in wfs_requests(s)] == [
        ",".join(wfs_types("nmt_evrf2007"))
    ]


# =============================================================================
# all
# =============================================================================


def test_provider_does_not_log_campaign_count_at_info(caplog):
    """M-7: only the manager logs the campaign count at INFO."""
    import logging

    with caplog.at_level(logging.INFO):
        GugikProvider(
            session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(G, all_campaigns=True)
    assert not [
        r
        for r in caplog.records
        if r.levelno >= logging.INFO and "kampanii" in r.getMessage()
    ]


def test_all_lists_every_matching_campaign_from_one_query():
    s = recorded_wfs()
    recs = GugikProvider(
        session=s, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(G, all_campaigns=True)
    # 72675 (2019): an ASC grid under a `.xyz` name (record format decides)
    assert ids(recs) == ["81025", "81616", "75506", "74160", "72675"]
    assert len(wfs_requests(s)) == 1


@pytest.mark.parametrize(
    "sheet,resolution,year,expected",
    [
        (G, "1m", 2024, ["81025", "81616"]),
        # 5 m: the partial sheet of September before the full one of April
        ("N-33-58-A-c-1-4", "5m", 2023, ["81479", "79032"]),
    ],
)
def test_resolve_campaigns_one_year_returns_both_flights(
    sheet, resolution, year, expected
):
    records = GugikProvider(
        session=recorded_wfs(), vertical_crs="EVRF2007", resolution=resolution
    ).resolve_campaigns(sheet, all_campaigns=True, min_year=year, max_year=year)
    assert ids(records) == expected


def test_resolve_campaigns_bounds_filter_years_campaigns_sets_count():
    """Model A: bounds restrict years; ``newest`` (default) = newest within them."""
    provider = GugikProvider(
        session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
    )
    assert ids(provider.resolve_campaigns(H, min_year=2025, max_year=2025)) == ["83137"]
    assert ids(provider.resolve_campaigns(H, max_year=2024)) == ["81428"]
    assert ids(provider.resolve_campaigns(H, all_campaigns=True, max_year=2022)) == [
        "76531",
        "73228",
    ]
    assert ids(provider.resolve_campaigns(H, min_year=2023)) == ["83137"]


def test_newest_with_min_year_matches_newest_without_range():
    session = recorded_wfs()
    for sheet, resolution in (
        (G, "1m"),
        (H, "1m"),
        ("N-33-58-A-c-1-4", "0.5m"),
        ("N-33-58-A-c-1-4", "5m"),
        ("N-33-77-D-a-1-2", "0.5m"),
    ):
        provider = GugikProvider(
            session=session, vertical_crs="EVRF2007", resolution=resolution
        )
        assert (
            provider.resolve_campaigns(sheet, min_year=2019)[0].url
            == provider.resolve_campaigns(sheet)[0].url
        ), (sheet, resolution)


def test_resolve_campaigns_year_2023_conflict_lists_years():
    with pytest.raises(YearRangeError) as exc:
        GugikProvider(
            session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(G, min_year=2023, max_year=2023)
    assert exc.value.sheets == {G: (2019, 2021, 2022, 2024)}


@pytest.mark.parametrize(
    "sheet,expected",
    [(G, ["75506"]), (H, ["76531"])],
)
def test_resolve_campaigns_max_year_2022(sheet, expected):
    records = GugikProvider(
        session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(sheet, max_year=2022)
    assert ids(records) == expected


def test_resolve_campaigns_range_queries_every_type_no_partial_scan(tmp_path):
    every_type = [",".join(wfs_types("nmt_evrf2007"))]
    cache = MetadataCache(tmp_path / "c.db")
    session = recorded_wfs()
    provider = GugikProvider(
        session=session, cache=cache, vertical_crs="EVRF2007", resolution="1m"
    )
    assert ids(provider.resolve_campaigns(H, min_year=2025)) == ["83137"]
    assert [query["TYPENAMES"] for query in wfs_requests(session)] == every_type
    payload = cache.get_campaigns(*_key(H))
    assert "scanned_from" not in payload
    cache.set_campaigns(*_key(H), {"sources": payload["sources"], "scanned_from": 2024})
    requery = recorded_wfs()
    assert ids(
        GugikProvider(
            session=requery, cache=cache, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(H, min_year=2025)
    ) == ["83137"]
    assert [query["TYPENAMES"] for query in wfs_requests(requery)] == every_type
    assert "scanned_from" not in cache.get_campaigns(*_key(H))


def test_available_years():
    provider = GugikProvider(
        session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
    )
    assert provider.available_years(H) == (2019, 2022, 2023, 2024, 2025)


def test_orto_cir_year_2025_conflict_rgb_has_it():
    sheet = "N-34-139-A-c-1-1"
    session = orto_session(sheet)
    with pytest.raises(YearRangeError) as exc:
        GugikOrtoProvider(session=session, color="CIR").resolve_campaigns(
            sheet, min_year=2025, max_year=2025
        )
    assert exc.value.sheets == {sheet: (2011, 2014, 2017, 2022, 2024)}
    assert 2025 in GugikOrtoProvider(
        session=orto_session(sheet), color="RGB"
    ).available_years(sheet)


def test_orto_year_2025_two_rgb_flights_same_pixel_newest_first():
    """T14 for orto: two 0.25 m RGB flights in 2025, newest (NIE) first."""
    sheet = "N-33-130-D-d-1-4"
    recs = GugikOrtoProvider(
        session=orto_session(sheet, base=REAL_10_10), color="RGB"
    ).resolve_campaigns(sheet, all_campaigns=True, min_year=2025, max_year=2025)
    assert [
        (file_id(r.url), r.aktualnosc, r.resolution_m, r.full_sheet) for r in recs
    ] == [
        ("83982_1592962", "2025-09-09", 0.25, False),
        ("83832_1514596", "2025-04-26", 0.25, True),
    ]


def test_all_min_year_filters_by_acquisition_year_not_pzgik_date(tmp_path):
    recs = GugikProvider(
        session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(H, all_campaigns=True, min_year=2023)
    assert [r.aktualnosc[:4] for r in recs] == ["2025", "2024", "2023"]
    # The cut-off from the acquisition-date year, not dt_pzgik: 81616 (2024-07-21,
    # dt_pzgik 2025-06-20) does not pass min_year=2025 -> 0 campaigns, not 1.
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(
        session=recorded_wfs(), cache=cache, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(G, all_campaigns=True)
    s2 = Mock(spec=requests.Session)
    with pytest.raises(YearRangeError) as exc:
        GugikProvider(
            session=s2, cache=cache, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(G, all_campaigns=True, min_year=2025)
    assert exc.value.sheets == {G: (2019, 2021, 2022, 2024)}
    assert s2.get.call_count == 0


def test_all_min_year_empty_lists_available_years(tmp_path):
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(
        session=recorded_wfs(), cache=cache, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(H, all_campaigns=True)
    s2 = Mock(spec=requests.Session)
    with pytest.raises(YearRangeError) as exc:
        GugikProvider(
            session=s2, cache=cache, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(H, all_campaigns=True, min_year=2026)
    assert exc.value.sheets == {H: (2019, 2022, 2023, 2024, 2025)}
    assert "od roku 2026" in str(exc.value)
    assert s2.get.call_count == 0


def test_all_no_records_is_no_coverage_with_provider_hints():
    """N-33-46-C-c-3-2 (sea): the recorded answer is an empty collection."""
    sheet = "N-33-46-C-c-3-2"
    answers = {("nmt_kron86", sheet): EMPTY_WFS}
    with pytest.raises(NoCoverageError) as newest:
        GugikProvider(
            session=recorded_wfs(answers), vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(sheet)
    with pytest.raises(NoCoverageError) as every:
        GugikProvider(
            session=recorded_wfs(answers), vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(sheet, all_campaigns=True)
    assert str(every.value) == str(newest.value)
    assert "Brak danych NMT 1m dla N-33-46-C-c-3-2" in str(every.value)


def test_orto_all_min_year_always_queries_starsze():
    s = orto_session("M-34-90-C-b-4-4")
    recs = GugikOrtoProvider(session=s, color="RGB").resolve_campaigns(
        "M-34-90-C-b-4-4", all_campaigns=True, min_year=2024
    )
    assert "SkorowidzeOrtofotomapyStarsze" in queried_layers(s)
    assert ids(recs) == ["84466", "81437"]


# =============================================================================
# all: cache campaigns_cache
# =============================================================================


def test_all_cache_hit_no_network(tmp_path):
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(
        session=recorded_wfs(), cache=cache, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(G, all_campaigns=True)
    s2 = Mock(spec=requests.Session)
    recs = GugikProvider(
        session=s2, cache=cache, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(G, all_campaigns=True)
    assert s2.get.call_count == 0 and len(recs) == 5


def test_all_from_cache_keeps_format(tmp_path):
    """KRON86 XYZ 1 m archives of H (2012, 2017): the record ``format`` - it
    decides the extension of the stored file - survives the campaigns cache."""
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(
        session=recorded_wfs(),
        cache=cache,
        vertical_crs="KRON86",
        resolution="1m",
        format="XYZ",
    ).resolve_campaigns(H, all_campaigns=True)
    s2 = Mock(spec=requests.Session)
    recs = GugikProvider(
        session=s2, cache=cache, vertical_crs="KRON86", resolution="1m", format="XYZ"
    ).resolve_campaigns(H, all_campaigns=True)
    assert s2.get.call_count == 0
    assert ids(recs) == ["67252", "4263"]
    assert {(r.file_format, source_format(r.file_format, r.url)) for r in recs} == {
        ("ASCII XYZ GRID", "XYZ")
    }


def test_all_failed_index_query_is_download_error_and_not_cached(tmp_path):
    session = recorded_wfs(fail=("nmt_evrf2007",))
    cache = MetadataCache(tmp_path / "c.db")
    with patch("time.sleep"), pytest.raises(DownloadError) as exc:
        GugikProvider(
            session=session, cache=cache, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(G, all_campaigns=True)
    assert not isinstance(exc.value, NoCoverageError)
    assert cache.get_campaigns(*_key(G)) is None


# =============================================================================
# record_source, download_record, download
# =============================================================================


def test_record_source_carries_endpoint_and_orto_color():
    p = GugikOrtoProvider(session=orto_session("M-34-90-C-b-4-4"), color="RGB")
    [r] = p.resolve_campaigns("M-34-90-C-b-4-4")
    src = p.record_source(r)
    assert src["index_url"] == GugikOrtoProvider.WMS_INDEX_ENDPOINT
    assert src["color"] == "RGB"


def test_record_source_carries_wfs_endpoint_and_feature_type():
    p = GugikProvider(session=recorded_wfs(), vertical_crs="EVRF2007", resolution="1m")
    record = p.resolve_campaigns(G, all_campaigns=True)[2]
    src = p.record_source(record)
    assert (src["url"], src["index_url"], src["layer"]) == (
        record.url,
        NMT_EVRF2007,
        "SkorowidzNMT2022",
    )


def test_download_record_fetches_record_url(tmp_path):
    s = recorded_wfs()
    p = GugikProvider(session=s, vertical_crs="EVRF2007", resolution="1m")
    record = p.resolve_campaigns(G, all_campaigns=True)[1]
    out = p.download_record(record, tmp_path / "x" / "a.asc")
    assert out == tmp_path / "x" / "a.asc"
    assert out.read_bytes() == b"DATA"
    assert s.get.call_args.args[0] == record.url
    assert file_id(record.url) == "81616_1669592"


def test_download_unchanged_api_downloads_newest(tmp_path):
    s = recorded_wfs()
    out = GugikProvider(session=s, vertical_crs="EVRF2007", resolution="1m").download(
        G, tmp_path / "sheet.asc"
    )
    assert out.read_bytes() == b"DATA"
    assert file_id(s.get.call_args.args[0]) == "81025_1562189"


def test_nmpt_inherits_campaigns(tmp_path):
    """NMPT N-33-77-B-c-3-3: 0.5 m grids of 2022 and 2024, 0.6 m of 2024."""
    sheet = "N-33-77-B-c-3-3"
    s = recorded_wfs({("nmpt_kron86", sheet): EMPTY_WFS})
    cache = MetadataCache(tmp_path / "c.db")
    recs = GugikNmptProvider(
        session=s, cache=cache, vertical_crs="EVRF2007", resolution="0.5m"
    ).resolve_campaigns(sheet, all_campaigns=True)
    assert ids(recs) == ["80195", "76003"]
    with pytest.raises(NoCoverageError) as exc:
        GugikNmptProvider(
            session=s, cache=cache, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(sheet, all_campaigns=True)
    assert "NMPT 0.5m EVRF2007 - uzyj --resolution 0.5m" in str(exc.value)
    # NMPT asks NMPT services only (its own and, for the variant hint, the
    # other height system) - never NMT
    assert {c.args[0].split("?")[0] for c in s.get.call_args_list} == {
        wfs_endpoint("nmpt_evrf2007"),
        wfs_endpoint("nmpt_kron86"),
    }
    no_coverage = cache.get_campaigns("pl.gugik.nmpt", "1m", "EVRF2007", sheet)
    assert no_coverage["no_coverage"] is True
    assert cache.get_campaigns(*_key(sheet)) is None


def test_supports_campaigns_flag():
    assert GugikProvider.supports_campaigns is True
    assert GugikOrtoProvider.supports_campaigns is True


# =============================================================================
# Fix round 1
# =============================================================================

# One feature (``gugik:Skorowidz<product><year>`` element) of a recorded answer
_FEATURE = re.compile(r'<gugik:(Skorowidz\w+) gml:id="[^"]*">.*?</gugik:\1>', re.DOTALL)


def _blank_years(blank_ids: set[str]) -> Mock:
    """The recorded answer of G with the year of the given records cleared."""

    def blank(match: re.Match[str]) -> str:
        feature = match.group(0)
        if not any(f"/{i}_" in feature for i in blank_ids):
            return feature
        feature = re.sub(r"<gugik:akt_rok>\d{4}<", "<gugik:akt_rok><", feature)
        return re.sub(
            r"(<gugik:akt_data [^>]*><gml:timePosition>)[^<]*", r"\1", feature
        )

    body = _FEATURE.sub(blank, wfs_fixture(f"sheet_nmt_evrf2007_{G}.xml"))
    assert body.count("<gugik:akt_rok></gugik:akt_rok>") == len(blank_ids)
    return recorded_wfs({("nmt_evrf2007", G): body})


def test_all_record_without_year_is_dropped_by_min_year():
    s = _blank_years({"81025"})
    recs = GugikProvider(
        session=s, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(G, all_campaigns=True, min_year=2024)
    assert ids(recs) == ["81616"]
    with pytest.raises(YearRangeError) as exc:
        GugikProvider(
            session=s, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(G, all_campaigns=True, min_year=2025)
    assert exc.value.sheets == {G: (2019, 2021, 2022, 2024)}


def test_records_without_any_year_are_no_coverage_not_conflict():
    """Spec 4.2 BRAK: no year to compare with = no data, as in the manager."""
    s = _blank_years({"81025", "81616", "75506", "74160", "72675"})
    with pytest.raises(NoCoverageError, match=f"Brak kampanii {G}"):
        GugikProvider(
            session=s, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(G, min_year=2024, max_year=2024)


def test_newest_record_without_year_fails_min_year():
    s = _blank_years({"81025", "81616"})
    with pytest.raises(YearRangeError) as exc:
        GugikProvider(
            session=s, vertical_crs="EVRF2007", resolution="1m"
        ).resolve_campaigns(G, min_year=2024)
    assert exc.value.sheets == {G: (2019, 2021, 2022)}


# =============================================================================
# ADR-031: cache entries written before the switch to English sidecar keys
# =============================================================================

_PRE_ADR031_KEYS = {
    "index_url": "skorowidz",
    "sheet": "godlo",
    "acquisition_date": "aktualnosc",
    "acquisition_year": "aktualnosc_rok",
    "pzgik_date": "dt_pzgik",
    "declared_crs": "uklad",
    "survey_work_id": "numer_zgloszenia",
    "data_source": "zrodlo_danych",
}


def _pre_adr031(source: dict) -> dict:
    """``to_source`` payload as stored before ADR-031 (Polish key names)."""
    return {_PRE_ADR031_KEYS.get(key, key): value for key, value in source.items()}


def test_pre_adr031_record_cache_entry_is_a_miss_and_is_overwritten(tmp_path):
    """Old ``record_cache`` payload: no KeyError, sheet resolved again, entry
    rewritten with English keys (``source_info`` never sees Polish keys)."""
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(
        session=recorded_wfs(), cache=cache, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(G)
    fresh = cache.get_record(*_key(G))["source"]
    cache.set_record(*_key(G), {"source": _pre_adr031(fresh)})

    session = recorded_wfs()
    provider = GugikProvider(
        session=session, cache=cache, vertical_crs="EVRF2007", resolution="1m"
    )
    (record,) = provider.resolve_campaigns(G)

    assert len(wfs_requests(session)) == 1  # cache miss -> index queried again
    assert ids([record]) == ["81025"]
    assert cache.get_record(*_key(G))["source"] == fresh
    assert provider.source_info(G) == fresh


def test_pre_adr031_campaigns_cache_entry_is_a_miss_and_is_overwritten(tmp_path):
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(
        session=recorded_wfs(), cache=cache, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(G, all_campaigns=True)
    fresh = cache.get_campaigns(*_key(G))["sources"]
    cache.set_campaigns(*_key(G), {"sources": [_pre_adr031(s) for s in fresh]})

    session = recorded_wfs()
    recs = GugikProvider(
        session=session, cache=cache, vertical_crs="EVRF2007", resolution="1m"
    ).resolve_campaigns(G, all_campaigns=True)

    assert len(wfs_requests(session)) == 1
    assert ids(recs) == ["81025", "81616", "75506", "74160", "72675"]
    assert cache.get_campaigns(*_key(G))["sources"] == fresh
