"""
Tests of the ``kartograf.providers.pl.skorowidz`` module (K3, K4, H1; D4, D5, D9).

The samples in ``tests/fixtures/gugik_skorowidz/`` are raw GUGiK GetFeatureInfo
responses from the 2026-09-29 live tests
(``docs/research/2026-09-29-live-e2e-i-audyt-docs/``, the ``gfi/`` and
``e2e-data/`` directories): an empty response (sea), a 5 m record, an
upper-case ``.ASC`` record (Slubice), two Szczecin records (0.50 m before
1.00 m), four Warsaw records in a collective layer (ascending by date,
PL-1992 and PL-2000 sheet codes), orto CIR+RGB and an OGC exception report.
"""

import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.exceptions import DownloadError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.providers.pl.skorowidz import (
    SkorowidzRecord,
    SourceInfoMixin,
    is_skorowidz_answer,
    layer_upper_year,
    parse_skorowidz_records,
    query_skorowidz_layer,
    select_sheet_record,
)
from tests.conftest import gfi_record, render_gfi_body

FIXTURES = Path(__file__).parent / "fixtures" / "gugik_skorowidz"
ENDPOINT = (
    "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WMS/SkorowidzeUkladEVRF2007"
)


def sample(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def response(body: str, status: int = 200) -> Mock:
    resp = Mock()
    resp.status_code = status
    resp.text = body
    resp.raise_for_status = Mock()
    return resp


# =============================================================================
# is_skorowidz_answer
# =============================================================================


class TestIsSkorowidzAnswer:
    def test_empty_gugik_answer_is_a_template(self):
        """Sea (gfi/01): a template header without a record array declaration."""
        assert is_skorowidz_answer(sample("empty.body"))

    @pytest.mark.parametrize(
        "name", ["land5m_2025.body", "orto_2024.html", "szczecin_c24_2024.body"]
    )
    def test_answers_with_records_are_templates(self, name):
        assert is_skorowidz_answer(sample(name))

    @pytest.mark.parametrize(
        "body",
        [
            "",
            "<html><body><h1>502 Bad Gateway</h1></body></html>",
            sample("ogc_exception.body"),
        ],
    )
    def test_other_html_is_not_an_answer(self, body):
        assert not is_skorowidz_answer(body)


# =============================================================================
# parse_skorowidz_records
# =============================================================================


class TestParseSkorowidzRecords:
    def test_empty_answer_has_no_records(self):
        assert parse_skorowidz_records(sample("empty.body"), "SkorowidzeNMT2025") == []

    def test_reads_every_field_of_a_real_record(self):
        (record,) = parse_skorowidz_records(
            sample("land5m_2025.body"), "SkorowidzeNMT2025"
        )
        assert record.url.endswith("83885_1835900_N-33-48-C-a-3-4.asc")
        assert record.godlo == "N-33-48-C-a-3-4"
        assert record.aktualnosc == "2025-05-20"
        assert record.layer == "SkorowidzeNMT2025"
        assert (record.uklad, record.zone) == ("1992", None)
        assert record.resolution_m == 5.0
        assert record.full_sheet is True
        assert record.raw["format"] == "ARC/INFO ASCII GRID"
        assert record.raw["ukladWspolrzednychPionowych"] == "PL-EVRF2007-NH"

    def test_uppercase_asc_url_is_kept_verbatim(self):
        """H1: the source extension does not filter the record and is not normalised."""
        (record,) = parse_skorowidz_records(
            sample("slubice_c32_2022iStarsze.html"), "SkorowidzeNMT2022iStarsze"
        )
        assert record.url.endswith("76969_1298029_N-33-126-C-c-3-2.ASC")
        assert record.resolution_m == 5.0

    def test_keeps_html_order_and_pl2000_zone(self):
        records = parse_skorowidz_records(
            sample("warszawa_2023iStarsze.body"), "SkorowidzeNMT2023iStarsze"
        )
        assert [r.aktualnosc for r in records] == [
            "2019-04-18",
            "2021-04-28",
            "2022-05-09",
            "2023-09-05",
        ]
        assert [r.godlo for r in records] == [
            "N-34-139-A-c-1-1",
            "7.173.21.06",
            "7.173.21.06.3",
            "N-34-139-A-c-1-1",
        ]
        assert (records[1].uklad, records[1].zone) == ("2000", 7)
        assert records[2].resolution_m == 0.5

    def test_orto_fields_map_to_the_same_record(self):
        """Orto: ``wielkoscPiksela``/``ukladWspolrzednych``/the ``Wyeplniony`` typo."""
        records = parse_skorowidz_records(
            sample("orto_2024.html"), "SkorowidzeOrtofotomapy2024"
        )
        assert [r.raw["kolor"] for r in records] == ["CIR", "RGB"]
        assert {r.resolution_m for r in records} == {0.25}
        assert {r.uklad for r in records} == {"1992"}
        assert {r.full_sheet for r in records} == {True}

    def test_record_without_https_url_is_dropped(self, caplog):
        body = render_gfi_body(
            [
                gfi_record(
                    "N-34-130-D-d-2-4", url="ftp://opendata.geoportal.gov.pl/x.asc"
                )
            ]
        )
        with caplog.at_level("WARNING"):
            assert parse_skorowidz_records(body, "L") == []
        assert "URL HTTPS" in caplog.text

    def test_record_with_unparseable_godlo_is_dropped(self, caplog):
        record = gfi_record("N-34-130-D-d-2-4")
        record["godlo"] = "???"
        with caplog.at_level("WARNING"):
            assert parse_skorowidz_records(render_gfi_body([record]), "L") == []
        assert "nieprawidlowe godlo" in caplog.text

    def test_missing_resolution_and_system_become_none(self):
        body = render_gfi_body(
            [
                {
                    "url": "https://opendata.geoportal.gov.pl/a.asc",
                    "godlo": "N-34-130-D-d-2-4",
                    "aktualnosc": "2024-01-02",
                }
            ]
        )
        (record,) = parse_skorowidz_records(body, "L")
        assert record.resolution_m is None
        assert record.uklad is None
        assert record.full_sheet is None
        assert record.dt_pzgik is None

    def test_godlo_is_normalized_like_sheet_parser(self):
        body = render_gfi_body([gfi_record("n-34-130-d-d-2-4")])
        (record,) = parse_skorowidz_records(body, "L")
        assert record.godlo == "N-34-130-D-d-2-4"

    def test_partition_violation_is_only_a_warning(self, caplog):
        """P2: a record with a year outside the layer partition stays, but visibly."""
        body = render_gfi_body(
            [gfi_record("N-34-130-D-d-2-4", aktualnosc="2025-03-01")]
        )
        with caplog.at_level("WARNING"):
            assert len(parse_skorowidz_records(body, "SkorowidzeNMT2024")) == 1
            assert len(parse_skorowidz_records(body, "SkorowidzeNMT2023iStarsze")) == 1
        assert caplog.text.count("poza partycja") == 2

    def test_records_inside_partition_do_not_warn(self, caplog):
        body = render_gfi_body(
            [gfi_record("N-34-130-D-d-2-4", aktualnosc="2022-03-01")]
        )
        with caplog.at_level("WARNING"):
            parse_skorowidz_records(body, "SkorowidzeNMT2022")
            parse_skorowidz_records(body, "SkorowidzeNMT2023iStarsze")
            parse_skorowidz_records(body, "SkorowidzeOrtofotomapyStarsze")
        assert "poza partycja" not in caplog.text


# =============================================================================
# select_sheet_record
# =============================================================================


def _records(*specs: dict, layer: str = "L") -> list[SkorowidzRecord]:
    return parse_skorowidz_records(render_gfi_body(list(specs)), layer)


class TestSelectSheetRecord:
    def test_szczecin_exact_resolution_beats_html_order(self):
        """K4: 0,50 m comes first in the HTML — the only 1,00 m record wins."""
        records = parse_skorowidz_records(
            sample("szczecin_c24_2024.body"), "SkorowidzeNMT2024"
        )
        chosen = select_sheet_record(
            records, godlo="N-33-90-C-c-2-4", uklad="1992", resolution_m=1.0
        )
        assert chosen is not None
        assert "80225_1536688" in chosen.url
        assert chosen.full_sheet is True

    def test_warszawa_latest_campaign_not_first_in_html(self):
        """K4: a collective layer grows by date - 2023 wins, not 2019."""
        records = parse_skorowidz_records(
            sample("warszawa_2023iStarsze.body"), "SkorowidzeNMT2023iStarsze"
        )
        chosen = select_sheet_record(
            records, godlo="N-34-139-A-c-1-1", uklad="1992", resolution_m=1.0
        )
        assert chosen is not None
        assert "78047_1404533" in chosen.url
        assert chosen.aktualnosc == "2023-09-05"

    def test_pl2000_needs_whole_token_and_zone(self):
        """K4: ``7.173.21.06.3`` is not ``7.173.21.06``; the zone must match."""
        records = parse_skorowidz_records(
            sample("warszawa_2023iStarsze.body"), "SkorowidzeNMT2023iStarsze"
        )
        chosen = select_sheet_record(
            records, godlo="7.173.21.06", uklad="2000", zone=7, resolution_m=1.0
        )
        assert chosen is not None and chosen.godlo == "7.173.21.06"
        assert (
            select_sheet_record(
                records, godlo="7.173.21.06", uklad="2000", zone=6, resolution_m=1.0
            )
            is None
        )
        assert (
            select_sheet_record(
                records, godlo="7.173.21", uklad="2000", zone=7, resolution_m=1.0
            )
            is None
        )

    def test_other_system_record_never_matches(self):
        """K4: a PL-1992 record is not a PL-2000 sheet (and vice versa)."""
        records = _records(gfi_record("N-33-48-C-a-3-4", resolution="5.00 m"))
        assert (
            select_sheet_record(
                records, godlo="7.124.7.4", uklad="2000", zone=7, resolution_m=5.0
            )
            is None
        )
        records = _records(gfi_record("7.124.7.4", uklad="PL-2000:S7"))
        assert (
            select_sheet_record(
                records, godlo="7.124.7.4", uklad="1992", resolution_m=1.0
            )
            is None
        )

    def test_resolution_filter_is_exact(self):
        records = _records(
            gfi_record("N-34-130-D-d-2-4", resolution="0.50 m"),
            gfi_record("N-34-130-D-d-2-4", resolution="5.00 m"),
        )
        assert (
            select_sheet_record(
                records, godlo="N-34-130-D-d-2-4", uklad="1992", resolution_m=1.0
            )
            is None
        )
        chosen = select_sheet_record(
            records, godlo="N-34-130-D-d-2-4", uklad="1992", resolution_m=5.0
        )
        assert chosen is not None and chosen.resolution_m == 5.0

    def test_no_resolution_filter_when_none(self):
        records = _records(gfi_record("N-34-130-D-d-2-4", resolution="0.25 m"))
        chosen = select_sheet_record(records, godlo="N-34-130-D-d-2-4", uklad="1992")
        assert chosen is not None

    def test_predicate_filters_records(self):
        records = parse_skorowidz_records(
            sample("orto_2024.html"), "SkorowidzeOrtofotomapy2024"
        )
        chosen = select_sheet_record(
            records,
            godlo="M-34-76-A-a-1-1",
            uklad="1992",
            predicate=lambda r: r.raw.get("kolor") == "RGB",
        )
        assert chosen is not None and "81423_1371958" in chosen.url

    def test_records_without_resolution_or_system_are_rejected(self, caplog):
        """P6: a missing resolution/CRS field = the record rejected with a warning."""
        body = render_gfi_body(
            [
                {
                    "url": "https://opendata.geoportal.gov.pl/a.asc",
                    "godlo": "N-34-130-D-d-2-4",
                    "aktualnosc": "2024-01-02",
                    "charakterystykaPrzestrzenna": "1.00 m",
                },
                {
                    "url": "https://opendata.geoportal.gov.pl/b.asc",
                    "godlo": "N-34-130-D-d-2-4",
                    "aktualnosc": "2024-01-02",
                    "ukladWspolrzednychPoziomych": "PL-1992",
                },
            ]
        )
        records = parse_skorowidz_records(body, "L")
        with caplog.at_level("WARNING"):
            assert (
                select_sheet_record(records, godlo="N-34-130-D-d-2-4", uklad="1992")
                is None
            )
        assert caplog.text.count("bez ukladu lub rozdzielczosci") == 2

    def test_newest_wins_regardless_of_full_sheet(self):
        """D9: newest acquisition date, even if ``calyArkuszWypelnionyTrescia: NIE``."""
        records = _records(
            gfi_record(
                "N-34-130-D-d-2-4", aktualnosc="2024-09-03", url="https://x/full.asc"
            ),
            gfi_record(
                "N-34-130-D-d-2-4",
                aktualnosc="2025-02-01",
                url="https://x/partial.asc",
                calyArkuszWypelnionyTrescia="NIE",
            ),
        )
        chosen = select_sheet_record(
            records, godlo="N-34-130-D-d-2-4", uklad="1992", resolution_m=1.0
        )
        assert chosen is not None and chosen.url == "https://x/partial.asc"
        assert chosen.full_sheet is False

    def test_tie_breaks_on_dt_pzgik_then_url(self):
        records = _records(
            gfi_record(
                "N-34-130-D-d-2-4", url="https://x/b.asc", dt_pzgik="2024-10-01"
            ),
            gfi_record(
                "N-34-130-D-d-2-4", url="https://x/a.asc", dt_pzgik="2024-12-01"
            ),
            gfi_record(
                "N-34-130-D-d-2-4", url="https://x/c.asc", dt_pzgik="2024-12-01"
            ),
        )
        chosen = select_sheet_record(
            records, godlo="N-34-130-D-d-2-4", uklad="1992", resolution_m=1.0
        )
        assert chosen is not None and chosen.url == "https://x/c.asc"

    def test_requested_godlo_is_normalized(self):
        records = _records(gfi_record("N-34-130-D-d-2-4"))
        assert (
            select_sheet_record(records, godlo="n-34-130-d-d-2-4", uklad="1992")
            is not None
        )


# =============================================================================
# SkorowidzRecord.to_source / from_source
# =============================================================================


class TestSourcePayload:
    def test_to_source_carries_provenance(self):
        (record,) = parse_skorowidz_records(
            sample("land5m_2025.body"), "SkorowidzeNMT2025"
        )
        source = record.to_source(ENDPOINT)
        assert source == {
            "url": record.url,
            "index_url": ENDPOINT,
            "layer": "SkorowidzeNMT2025",
            "sheet": "N-33-48-C-a-3-4",
            "acquisition_date": "2025-05-20",
            "acquisition_year": "2025",
            "pzgik_date": record.raw["dt_pzgik"],
            "resolution_m": 5.0,
            "declared_crs": "PL-1992",
            "full_sheet": True,
            "survey_work_id": record.raw["numerZgloszeniaPracy"],
            "data_source": record.raw["zrDanych"],
            "format": "ARC/INFO ASCII GRID",
        }

    def test_from_source_round_trips_selection_fields(self):
        records = parse_skorowidz_records(
            sample("warszawa_2023iStarsze.body"), "SkorowidzeNMT2023iStarsze"
        )
        record = records[1]  # 7.173.21.06, PL-2000:S7
        restored = SkorowidzRecord.from_source(record.to_source(ENDPOINT))
        assert (restored.url, restored.godlo, restored.layer) == (
            record.url,
            record.godlo,
            record.layer,
        )
        assert (restored.uklad, restored.zone, restored.resolution_m) == (
            "2000",
            7,
            1.0,
        )
        assert restored.aktualnosc == "2021-04-28"
        assert restored.to_source(ENDPOINT) == record.to_source(ENDPOINT)


# =============================================================================
# query_skorowidz_layer
# =============================================================================


class TestQuerySkorowidzLayer:
    def _query(self, session, retries=3):
        return query_skorowidz_layer(
            session,
            ENDPOINT,
            "SkorowidzeNMT2026",
            query_bbox="1,2,3,4",
            godlo="N-34-130-D-d-2-4",
            timeout=30,
            retries=retries,
        )

    def test_builds_getfeatureinfo_request(self):
        session = Mock(spec=requests.Session)
        session.get.return_value = response(render_gfi_body([]))
        assert self._query(session) == []
        url = session.get.call_args.args[0]
        assert url.startswith(ENDPOINT + "?")
        for part in (
            "REQUEST=GetFeatureInfo",
            "LAYERS=SkorowidzeNMT2026",
            "QUERY_LAYERS=SkorowidzeNMT2026",
            "INFO_FORMAT=text%2Fhtml",
            "CRS=EPSG%3A2180",
            "BBOX=1%2C2%2C3%2C4",
            "I=50",
            "J=50",
        ):
            assert part in url
        assert session.get.call_args.kwargs == {"timeout": 30}

    def test_returns_parsed_records(self):
        session = Mock(spec=requests.Session)
        session.get.return_value = response(sample("szczecin_c24_2024.body"))
        records = self._query(session)
        assert [r.resolution_m for r in records] == [0.5, 1.0]
        assert {r.layer for r in records} == {"SkorowidzeNMT2026"}

    def test_retries_same_layer_then_succeeds(self):
        session = Mock(spec=requests.Session)
        session.get.side_effect = [
            requests.ConnectionError("reset"),
            response(render_gfi_body([gfi_record("N-34-130-D-d-2-4")])),
        ]
        with patch("kartograf.transport.http.time.sleep") as sleep:
            records = self._query(session)
        assert len(records) == 1
        assert session.get.call_count == 2
        assert sleep.call_count == 1

    def test_exhausted_retries_raise_download_error_with_context(self):
        """K3: a broken layer query = an error naming code and layer, not a no-sheet."""
        session = Mock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("reset")
        with (
            patch("kartograf.transport.http.time.sleep"),
            pytest.raises(DownloadError) as exc,
        ):
            self._query(session)
        assert session.get.call_count == 3
        assert "N-34-130-D-d-2-4" in str(exc.value)
        assert "SkorowidzeNMT2026" in str(exc.value)
        assert exc.value.godlo is None or exc.value.godlo == "N-34-130-D-d-2-4"

    def test_http_error_is_retried(self):
        session = Mock(spec=requests.Session)
        bad = response("", status=503)
        bad.raise_for_status.side_effect = requests.HTTPError("503")
        session.get.side_effect = [bad, response(render_gfi_body([]))]
        with patch("kartograf.transport.http.time.sleep"):
            assert self._query(session) == []
        assert session.get.call_count == 2

    def test_ogc_exception_report_fails_without_retry(self):
        """An OGC report with HTTP 200 (a wrong layer) is deterministic - 1 attempt."""
        session = Mock(spec=requests.Session)
        session.get.return_value = response(sample("ogc_exception.body"))
        with (
            patch("kartograf.transport.http.time.sleep") as sleep,
            pytest.raises(DownloadError, match="raport wyjatku OGC") as exc,
        ):
            self._query(session)
        assert session.get.call_count == 1
        assert sleep.call_count == 0
        assert "Invalid layer" in str(exc.value)
        assert exc.value.godlo == "N-34-130-D-d-2-4"

    def test_non_template_html_is_not_an_answer(self):
        """P7: an HTTP 200 error page without OGC markers is an error, not nodata."""
        session = Mock(spec=requests.Session)
        session.get.return_value = response("<html><body>502 Bad Gateway</body></html>")
        with pytest.raises(DownloadError, match="nie jest szablonem skorowidza"):
            self._query(session)
        assert session.get.call_count == 1

    def test_retries_parameter_is_honoured(self):
        session = Mock(spec=requests.Session)
        session.get.side_effect = requests.ConnectionError("reset")
        with patch("kartograf.transport.http.time.sleep"), pytest.raises(DownloadError):
            self._query(session, retries=1)
        assert session.get.call_count == 1


# =============================================================================
# SourceInfoMixin
# =============================================================================


class TestSourceInfoMixin:
    class Holder(SourceInfoMixin):
        pass

    def test_unknown_godlo_is_none(self):
        assert self.Holder().source_info("N-34-130-D-d-2-4") is None

    def test_remembers_per_godlo_and_normalizes_key(self):
        holder = self.Holder()
        holder._remember_source("n-34-130-d-d-2-4", {"url": "https://x/a.asc"})
        holder._remember_source("N-34-130-D-d-2-3", {"url": "https://x/b.asc"})
        assert holder.source_info("N-34-130-D-d-2-4") == {"url": "https://x/a.asc"}
        assert holder.source_info("N-34-130-D-d-2-3") == {"url": "https://x/b.asc"}

    def test_returns_copies(self):
        holder = self.Holder()
        source = {"url": "https://x/a.asc"}
        holder._remember_source("N-34-130-D-d-2-4", source)
        source["url"] = "mutated"
        first = holder.source_info("N-34-130-D-d-2-4")
        first["url"] = "mutated-again"
        assert holder.source_info("N-34-130-D-d-2-4") == {"url": "https://x/a.asc"}

    def test_threads_keep_their_own_sheets(self):
        holder = self.Holder()
        godla = [f"N-34-130-D-d-2-{i}" for i in (1, 2, 3, 4)]

        def remember(godlo):
            for _ in range(200):
                holder._remember_source(godlo, {"godlo": godlo})

        threads = [threading.Thread(target=remember, args=(g,)) for g in godla]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert [holder.source_info(g)["godlo"] for g in godla] == godla


def _hint_record(godlo, uklad, zone=None, resolution_m=1.0):
    return SkorowidzRecord(
        url=f"https://example.invalid/{godlo}.asc",
        godlo=godlo,
        aktualnosc="2024-01-01",
        dt_pzgik=None,
        layer="L",
        uklad=uklad,
        zone=zone,
        resolution_m=resolution_m,
        full_sheet=True,
        raw={"kolor": "RGB"},
    )


class TestCoverageHints:
    """D14: ``NoCoverageError`` hints shared by NMT and orto."""

    _PL2000 = "6.129.30"
    _RECORDS = (
        _hint_record("6.129.30.13.4", "2000", zone=6),
        _hint_record("M-34-63-A-c-2-1", "1992"),
    )
    _EXPECTED = {
        "Dostepny potomek 6.129.30.13.4 — uzyj --scale 1:1000",
        "Skorowidz ma ten obszar w PL-1992: M-34-63-A-c-2-1 (1:10000) — uzyj "
        "tego godla lub --system 1992 --scale 1:10000",
    }

    def test_helper(self):
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.providers.pl.skorowidz import coverage_hints

        hints = coverage_hints(SheetParser(self._PL2000), self._RECORDS)
        assert hints == self._EXPECTED

    @pytest.mark.parametrize("product", ["nmt", "orto"])
    def test_providers_share_hints(self, product):
        """Orto had a shorter hint about another CRS (without ``--system``/
        ``--scale``) - after unification both providers say the same."""
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.providers.pl.gugik import GugikProvider
        from kartograf.providers.pl.gugik_orto import GugikOrtoProvider

        cls = GugikProvider if product == "nmt" else GugikOrtoProvider
        provider = cls(session=Mock())
        error = provider._no_coverage(SheetParser(self._PL2000), list(self._RECORDS))
        message = str(error)
        for hint in self._EXPECTED:
            assert hint in message
        assert error.godlo == self._PL2000
        # stable hint order (sorted), separated by "; "
        assert message.endswith("; ".join(sorted(self._EXPECTED)))
        # the same structurally (the CLI does not parse the message)
        assert error.hints == tuple(sorted(self._EXPECTED))

    def test_error_without_hints_has_empty_hints(self):
        from kartograf.core.sheet_parser import SheetParser
        from kartograf.providers.pl.skorowidz import no_coverage_error

        error = no_coverage_error(SheetParser(self._PL2000), "Brak. Cos", [])
        assert error.hints == ()
        assert str(error) == "Brak. Cos"


@pytest.mark.parametrize(
    "cls,name,year",
    [
        (GugikProvider, "SkorowidzeNMT2019", 2019),
        (GugikProvider, "SkorowidzeNMT2017iStarsze", 2017),
        (GugikNmptProvider, "SkorowidzeNMPT2023iStarsze", 2023),
        (GugikOrtoProvider, "SkorowidzeOrtofotomapy2026", 2026),
        (GugikOrtoProvider, "SkorowidzeOrtofotomapyStarsze", None),
        (GugikProvider, "SkorowidzeNMT2027Nowe", None),
    ],
)
def test_layer_upper_year(cls, name, year):
    assert layer_upper_year(cls.LAYER_PATTERN, name) == year
