"""
Campaigns in the GUGiK providers (ADR-030): ``resolve_campaigns``,
``download_record``, ``record_source`` on RAW index (skorowidz) responses.

Fixtures: ``tests/fixtures/gugik_skorowidz/real_2026_10_06/`` (E2E round
2026-10-06); GetCapabilities layers from the autouse stub in
``tests/conftest.py``.
"""

import re
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

REAL = Path(__file__).parent / "fixtures" / "gugik_skorowidz" / "real_2026_10_06"
EMPTY = (
    Path(__file__).parent / "fixtures" / "gugik_skorowidz" / "empty.body"
).read_text(encoding="utf-8")

G = "N-34-139-C-a-3-1"
NMPT_EVRF2007 = GugikNmptProvider.WMS_SKOROWIDZE_ENDPOINTS["1m"]["EVRF2007"]


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


def nmt_session(godlo: str, prefix: str) -> Mock:
    def path_for_layer(layer):
        path = REAL / "nmt" / godlo / f"{prefix}__{layer}.body"
        return path if path.exists() else None

    return routed_session(path_for_layer)


def orto_session(godlo: str) -> Mock:
    def path_for_layer(layer):
        path = REAL / "orto" / f"{godlo}_{layer}.html"
        return path if path.exists() else None

    return routed_session(path_for_layer)


def c14_session(godlo: str) -> Mock:
    def path_for_layer(layer):
        path = REAL / "nmt" / "c14" / f"{godlo}_EVRF2007_{layer}.html"
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


def test_newest_is_adr028_record_c14():
    p = GugikProvider(session=c14_session(G))
    [r] = p.resolve_campaigns(G)
    assert file_id(r.url) == "84183_1852496"


def test_newest_min_year_older_newest_is_no_coverage_with_date():
    with pytest.raises(NoCoverageError, match=r"2025-10-21.*min_year=2026"):
        GugikProvider(session=c14_session(G)).resolve_campaigns(G, min_year=2026)


def test_newest_min_year_does_not_skip_layers():
    """Q5: newest queries the 2023iStarsze layer despite the 2024 bound."""
    godlo = "M-34-66-B-a-2-1"
    s = nmt_session(godlo, "nmt1_evr")
    with pytest.raises(NoCoverageError, match=r"ma date 2023-03-29.*min_year=2024"):
        GugikProvider(session=s).resolve_campaigns(godlo, min_year=2024)
    assert queried_layers(s)[-1] == "SkorowidzeNMT2023iStarsze"


# =============================================================================
# all
# =============================================================================


def test_provider_does_not_log_campaign_count_at_info(caplog):
    """M-7: only the manager logs the campaign count at INFO."""
    import logging

    with caplog.at_level(logging.INFO):
        GugikProvider(session=c14_session(G)).resolve_campaigns(G, campaigns="all")
    assert not [
        r
        for r in caplog.records
        if r.levelno >= logging.INFO and "kampanii" in r.getMessage()
    ]


def test_all_lists_every_matching_campaign_from_all_layers():
    s = c14_session(G)
    recs = GugikProvider(session=s).resolve_campaigns(G, campaigns="all")
    assert ids(recs) == ["84183", "83233", "78047", "73021"]
    assert queried_layers(s) == [
        "SkorowidzeNMT2026",
        "SkorowidzeNMT2025",
        "SkorowidzeNMT2024",
        "SkorowidzeNMT2023iStarsze",
    ]


def test_all_min_year_skips_cumulative_layer_below_bound():
    s = c14_session(G)
    recs = GugikProvider(session=s).resolve_campaigns(G, campaigns="all", min_year=2024)
    assert "SkorowidzeNMT2023iStarsze" not in queried_layers(s)
    assert [r.aktualnosc for r in recs] == ["2025-10-21", "2025-04-27"]


def test_all_min_year_2023_queries_2023iStarsze_and_filters_by_aktualnosc(tmp_path):
    recs = GugikProvider(session=c14_session(G)).resolve_campaigns(
        G, campaigns="all", min_year=2023
    )
    assert [r.aktualnosc[:4] for r in recs] == ["2025", "2025", "2023"]
    # The cut-off from the acquisition-date year, not dt_pzgik: 84183 (2025-10-21,
    # dt_pzgik 2026-07-10) does not pass min_year=2026 -> 0 campaigns, not 1.
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(session=c14_session(G), cache=cache).resolve_campaigns(
        G, campaigns="all"
    )
    s2 = Mock(spec=requests.Session)
    with pytest.raises(NoCoverageError):
        GugikProvider(session=s2, cache=cache).resolve_campaigns(
            G, campaigns="all", min_year=2026
        )
    assert s2.get.call_count == 0


def test_all_min_year_empty_reports_newest_date(tmp_path):
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(session=c14_session(G), cache=cache).resolve_campaigns(
        G, campaigns="all"
    )
    s2 = Mock(spec=requests.Session)
    with pytest.raises(NoCoverageError) as exc:
        GugikProvider(session=s2, cache=cache).resolve_campaigns(
            G, campaigns="all", min_year=2026
        )
    assert str(exc.value) == f"Brak kampanii {G} od roku 2026 (najnowsza: 2025-10-21)"
    assert s2.get.call_count == 0


def test_all_no_records_is_no_coverage_with_provider_hints():
    godlo = "N-33-77-A-d-2-2"
    with pytest.raises(NoCoverageError) as newest:
        GugikProvider(session=routed_session(lambda layer: None)).resolve_campaigns(
            godlo
        )
    with pytest.raises(NoCoverageError) as every:
        GugikProvider(session=routed_session(lambda layer: None)).resolve_campaigns(
            godlo, campaigns="all"
        )
    assert str(every.value) == str(newest.value)
    assert "Brak danych NMT 1m" in str(every.value)


def test_orto_all_min_year_always_queries_starsze():
    s = orto_session("M-34-90-C-b-4-4")
    recs = GugikOrtoProvider(session=s).resolve_campaigns(
        "M-34-90-C-b-4-4", campaigns="all", min_year=2024
    )
    assert "SkorowidzeOrtofotomapyStarsze" in queried_layers(s)
    assert ids(recs) == ["84466", "81437"]


def test_all_lists_real_xyz_campaign_72675():
    s = nmt_session("N-33-69-A-d-3-2", "nmt1_evr")
    recs = GugikProvider(session=s).resolve_campaigns(
        "N-33-69-A-d-3-2", campaigns="all"
    )
    assert ids(recs) == ["81025", "81616", "75506", "74160", "72675"]
    assert recs[-1].url.endswith(".xyz")
    assert recs[-1].file_format == "ARC/INFO ASCII GRID"


# =============================================================================
# all: cache campaigns_cache
# =============================================================================


def test_all_cache_hit_no_network(tmp_path):
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(session=c14_session(G), cache=cache).resolve_campaigns(
        G, campaigns="all"
    )
    s2 = Mock(spec=requests.Session)
    recs = GugikProvider(session=s2, cache=cache).resolve_campaigns(G, campaigns="all")
    assert s2.get.call_count == 0 and len(recs) == 4


def test_all_from_cache_keeps_format(tmp_path):
    godlo = "N-33-69-A-d-3-2"
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(
        session=nmt_session(godlo, "nmt1_evr"), cache=cache
    ).resolve_campaigns(godlo, campaigns="all")
    s2 = Mock(spec=requests.Session)
    recs = GugikProvider(session=s2, cache=cache).resolve_campaigns(
        godlo, campaigns="all"
    )
    assert s2.get.call_count == 0
    assert ids(recs)[-1] == "72675"
    assert recs[-1].file_format == "ARC/INFO ASCII GRID"


def test_all_cache_partial_scan_valid_only_for_higher_bound(tmp_path):
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(session=c14_session(G), cache=cache).resolve_campaigns(
        G, campaigns="all", min_year=2024
    )
    assert cache.get_campaigns("nmt", "1m", "EVRF2007", G)["scanned_from"] == 2024

    s2 = Mock(spec=requests.Session)
    recs = GugikProvider(session=s2, cache=cache).resolve_campaigns(
        G, campaigns="all", min_year=2025
    )
    assert s2.get.call_count == 0
    assert ids(recs) == ["84183", "83233"]

    s3 = c14_session(G)
    recs = GugikProvider(session=s3, cache=cache).resolve_campaigns(G, campaigns="all")
    assert "SkorowidzeNMT2023iStarsze" in queried_layers(s3)
    assert ids(recs) == ["84183", "83233", "78047", "73021"]
    assert cache.get_campaigns("nmt", "1m", "EVRF2007", G)["scanned_from"] is None


def test_all_failed_layer_is_download_error_and_not_cached(tmp_path):
    def get(url, **kwargs):
        layer = _layer_of(url)
        if layer == "SkorowidzeNMT2024":
            response = _response("")
            response.status_code = 503
            response.headers = {}
            response.raise_for_status = Mock(
                side_effect=requests.HTTPError("503", response=response)
            )
            return response
        path = REAL / "nmt" / "c14" / f"{G}_EVRF2007_{layer}.html"
        return _response(path.read_text(encoding="utf-8") if path.exists() else EMPTY)

    session = Mock(spec=requests.Session)
    session.get = Mock(side_effect=get)
    cache = MetadataCache(tmp_path / "c.db")
    with patch("time.sleep"), pytest.raises(DownloadError) as exc:
        GugikProvider(session=session, cache=cache).resolve_campaigns(
            G, campaigns="all"
        )
    assert not isinstance(exc.value, NoCoverageError)
    assert cache.get_campaigns("nmt", "1m", "EVRF2007", G) is None


def test_all_cached_partial_no_coverage_message_uses_current_bound(tmp_path):
    """D-2: no_coverage with scanned_from=2026 valid for 2027, text from 2027."""
    cache = MetadataCache(tmp_path / "c.db")
    s = c14_session(G)
    with pytest.raises(NoCoverageError, match="od roku 2026"):
        GugikProvider(session=s, cache=cache).resolve_campaigns(
            G, campaigns="all", min_year=2026
        )
    assert queried_layers(s) == ["SkorowidzeNMT2026"]
    entry = cache.get_campaigns("nmt", "1m", "EVRF2007", G)
    assert entry["no_coverage"] is True and entry["scanned_from"] == 2026

    s2 = Mock(spec=requests.Session)
    with pytest.raises(NoCoverageError) as exc:
        GugikProvider(session=s2, cache=cache).resolve_campaigns(
            G, campaigns="all", min_year=2027
        )
    assert "od roku 2027" in str(exc.value)
    assert "2026" not in str(exc.value)
    assert s2.get.call_count == 0


# =============================================================================
# record_source, download_record, download
# =============================================================================


def test_record_source_carries_endpoint_and_orto_color():
    p = GugikOrtoProvider(session=orto_session("M-34-90-C-b-4-4"))
    [r] = p.resolve_campaigns("M-34-90-C-b-4-4")
    src = p.record_source(r)
    assert src["index_url"] == GugikOrtoProvider.WMS_SKOROWIDZE_ENDPOINT
    assert src["color"] == "RGB"


def test_download_record_fetches_record_url(tmp_path):
    s = c14_session(G)
    p = GugikProvider(session=s)
    record = p.resolve_campaigns(G, campaigns="all")[1]
    out = p.download_record(record, tmp_path / "x" / "a.asc")
    assert out == tmp_path / "x" / "a.asc"
    assert out.read_bytes() == b"DATA"
    assert s.get.call_args.args[0] == record.url
    assert file_id(record.url).startswith("83233_")


def test_download_unchanged_api_downloads_newest(tmp_path):
    s = c14_session(G)
    out = GugikProvider(session=s).download(G, tmp_path / "sheet.asc")
    assert out.read_bytes() == b"DATA"
    assert file_id(s.get.call_args.args[0]) == "84183_1852496"


def test_nmpt_inherits_campaigns(tmp_path):
    godlo = "N-33-77-A-d-2-2"
    s = nmt_session(godlo, "nmpt_evr")
    cache = MetadataCache(tmp_path / "c.db")
    with pytest.raises(NoCoverageError) as exc:
        GugikNmptProvider(session=s, cache=cache).resolve_campaigns(
            godlo, campaigns="all"
        )
    assert "GUGiK ma ten arkusz w 0.5 m" in str(exc.value)
    assert s.get.call_count > 0
    # NMPT asks NMPT indexes only (its own and, for the variant hint, the
    # other vertical CRS) - never NMT
    assert all("/NMPT/" in c.args[0] for c in s.get.call_args_list)
    assert cache.get_campaigns("nmpt", "1m", "EVRF2007", godlo)["no_coverage"] is True
    assert cache.get_campaigns("nmt", "1m", "EVRF2007", godlo) is None


def test_supports_campaigns_flag():
    assert GugikProvider.supports_campaigns is True
    assert GugikOrtoProvider.supports_campaigns is True


# =============================================================================
# Fix round 1
# =============================================================================


def test_all_cache_partial_scan_does_not_serve_lower_bound(tmp_path):
    """An entry with scanned_from=2024 does not serve min_year=2023 - a rescan."""
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(session=c14_session(G), cache=cache).resolve_campaigns(
        G, campaigns="all", min_year=2024
    )
    assert cache.get_campaigns("nmt", "1m", "EVRF2007", G)["scanned_from"] == 2024

    s2 = c14_session(G)
    recs = GugikProvider(session=s2, cache=cache).resolve_campaigns(
        G, campaigns="all", min_year=2023
    )
    assert "SkorowidzeNMT2023iStarsze" in queried_layers(s2)
    assert ids(recs) == ["84183", "83233", "78047"]
    # with min_year=2023 no layer is skipped -> a full scan
    assert cache.get_campaigns("nmt", "1m", "EVRF2007", G)["scanned_from"] is None


def test_all_cached_partial_no_coverage_does_not_serve_lower_bound(tmp_path):
    cache = MetadataCache(tmp_path / "c.db")
    with pytest.raises(NoCoverageError, match="od roku 2024"):
        GugikProvider(
            session=routed_session(lambda layer: None), cache=cache
        ).resolve_campaigns(G, campaigns="all", min_year=2024)
    assert cache.get_campaigns("nmt", "1m", "EVRF2007", G)["scanned_from"] == 2024

    s2 = routed_session(lambda layer: None)
    with pytest.raises(NoCoverageError) as exc:
        GugikProvider(session=s2, cache=cache).resolve_campaigns(
            G, campaigns="all", min_year=2023
        )
    assert "SkorowidzeNMT2023iStarsze" in queried_layers(s2)
    assert "od roku" not in str(exc.value)
    assert "Brak danych NMT 1m" in str(exc.value)


def _c14_copy(tmp_path: Path, blank_ids: set[str]) -> Mock:
    """A copy of the real c14 bodies in tmp_path with the record year cleared."""
    copy = tmp_path / "c14"
    copy.mkdir()
    for src in (REAL / "nmt" / "c14").glob(f"{G}_EVRF2007_*.html"):
        lines = []
        for line in src.read_text(encoding="utf-8").splitlines(keepends=True):
            if any(f"/{i}_" in line for i in blank_ids) and ".push({" in line:
                line = re.sub(r'aktualnosc:"[^"]*"', 'aktualnosc:""', line)
                line = re.sub(r'aktualnoscRok:"[^"]*"', 'aktualnoscRok:""', line)
            lines.append(line)
        (copy / src.name).write_text("".join(lines), encoding="utf-8")

    def path_for_layer(layer):
        path = copy / f"{G}_EVRF2007_{layer}.html"
        return path if path.exists() else None

    return routed_session(path_for_layer)


def test_all_record_without_year_is_dropped_by_min_year(tmp_path):
    s = _c14_copy(tmp_path, {"84183"})
    recs = GugikProvider(session=s).resolve_campaigns(G, campaigns="all", min_year=2024)
    assert ids(recs) == ["83233"]


def test_newest_record_without_year_fails_min_year(tmp_path):
    s = _c14_copy(tmp_path, {"84183", "83233"})
    with pytest.raises(NoCoverageError, match="starsza niz min_year=2024"):
        GugikProvider(session=s).resolve_campaigns(G, min_year=2024)


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
    GugikProvider(session=c14_session(G), cache=cache).resolve_campaigns(G)
    fresh = cache.get_record("nmt", "1m", "EVRF2007", G)["source"]
    cache.set_record("nmt", "1m", "EVRF2007", G, {"source": _pre_adr031(fresh)})

    session = c14_session(G)
    provider = GugikProvider(session=session, cache=cache)
    (record,) = provider.resolve_campaigns(G)

    assert queried_layers(session)  # cache miss -> index queried again
    assert ids([record]) == ["84183"]
    assert cache.get_record("nmt", "1m", "EVRF2007", G)["source"] == fresh
    assert provider.source_info(G) == fresh


def test_pre_adr031_campaigns_cache_entry_is_a_miss_and_is_overwritten(tmp_path):
    cache = MetadataCache(tmp_path / "c.db")
    GugikProvider(session=c14_session(G), cache=cache).resolve_campaigns(
        G, campaigns="all"
    )
    fresh = cache.get_campaigns("nmt", "1m", "EVRF2007", G)["sources"]
    cache.set_campaigns(
        "nmt",
        "1m",
        "EVRF2007",
        G,
        {"sources": [_pre_adr031(s) for s in fresh], "scanned_from": None},
    )

    session = c14_session(G)
    recs = GugikProvider(session=session, cache=cache).resolve_campaigns(
        G, campaigns="all"
    )

    assert queried_layers(session)
    assert ids(recs) == ["84183", "83233", "78047", "73021"]
    assert cache.get_campaigns("nmt", "1m", "EVRF2007", G)["sources"] == fresh
