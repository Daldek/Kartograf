"""
Testy regresyjne wyboru rekordu i obslugi danych na SUROWYCH odpowiedziach GUGiK.

Fixtury w ``tests/fixtures/gugik_skorowidz/real_2026_10_06/`` (NMT/NMPT/orto) i
``tests/fixtures/gugik_laz/real_2026_10_06/`` (WFS LAZ) to nieedytowane body z
rundy E2E na zywo 2026-10-06 (``docs/research/2026-10-06-e2e-brzegowe-i-review/``,
wymaganie E18). Kazda warstwa skorowidza jest zwracana z pliku o jej nazwie,
dokladnie tak, jak odpowiadal serwer (kolejnosc warstw: najnowsza -> najstarsza).
Testy dotycza zachowan, ktore kod JUZ ma i ktore runda potwierdzila.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import NoCoverageError
from kartograf.providers.pl.gugik import GugikProvider
from kartograf.providers.pl.gugik_laz import GugikLazProvider
from kartograf.providers.pl.gugik_nmpt import GugikNmptProvider
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from kartograf.providers.pl.skorowidz import (
    parse_skorowidz_records,
    select_sheet_record,
)

REAL = Path(__file__).parent / "fixtures" / "gugik_skorowidz" / "real_2026_10_06"
REAL_LAZ = Path(__file__).parent / "fixtures" / "gugik_laz" / "real_2026_10_06"

EMPTY = (
    Path(__file__).parent / "fixtures" / "gugik_skorowidz" / "empty.body"
).read_text(encoding="utf-8")


def _response(body: str) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.text = body
    response.raise_for_status = Mock()
    return response


def _layer_of(url: str) -> str:
    return parse_qs(urlparse(url).query)["LAYERS"][0]


def routed_session(path_for_layer) -> Mock:
    """Sesja, ktora na GetFeatureInfo oddaje surowe body danej warstwy.

    ``path_for_layer(layer)`` zwraca sciezke pliku albo None (pusta odpowiedz).
    """
    session = Mock(spec=requests.Session)

    def get(url, **kwargs):
        path = path_for_layer(_layer_of(url))
        body = path.read_text(encoding="utf-8") if path else EMPTY
        return _response(body)

    session.get = Mock(side_effect=get)
    return session


def nmt_session(godlo: str, prefix: str) -> Mock:
    """Surowe body: ``real_2026_10_06/nmt/<godlo>/<prefix>__<warstwa>.body``."""

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


def layer_records(path: Path, layer: str):
    return parse_skorowidz_records(path.read_text(encoding="utf-8"), layer)


def queried_layers(session: Mock) -> list[str]:
    return [_layer_of(call.args[0]) for call in session.get.call_args_list]


def file_id(url: str) -> str:
    """``78954_1462161`` z ``.../78954/78954_1462161_M-33-57-C-b-4-2.asc``."""
    return "_".join(url.rsplit("/", 1)[-1].split("_")[:2])


# =============================================================================
# NMT: wybor rekordu (C1b, C3, C6, C9)
# =============================================================================


class TestNmtRecordSelectionOnRealBodies:
    def test_c1b_several_campaigns_in_one_layer_newest_wins(self):
        """M-34-66-B-a-2-1: 2019-02-16, 2022-05-31, 2023-03-29 w 2023iStarsze."""
        godlo = "M-34-66-B-a-2-1"
        records = layer_records(
            REAL / "nmt" / godlo / "nmt1_evr__SkorowidzeNMT2023iStarsze.body",
            "SkorowidzeNMT2023iStarsze",
        )
        assert sorted(r.aktualnosc for r in records) == [
            "2019-02-16",
            "2022-05-31",
            "2023-03-29",
        ]
        session = nmt_session(godlo, "nmt1_evr")
        provider = GugikProvider(session=session)
        url = provider._get_opendata_url(godlo)
        assert file_id(url) == "77381_1339240"
        assert provider.source_info(godlo)["aktualnosc"] == "2023-03-29"
        # Warstwy 2026..2024 puste -> przejscie do zbiorczej, bez bledu
        assert queried_layers(session)[-1] == "SkorowidzeNMT2023iStarsze"

    def test_c3_layer_2025_only_half_metre_falls_through_to_1m_older_layer(self):
        """M-33-57-C-b-4-2: 2025 ma TYLKO 0,5 m, 1 m jest w 2023iStarsze."""
        godlo = "M-33-57-C-b-4-2"
        newer = layer_records(
            REAL / "nmt" / godlo / "nmt1_evr__SkorowidzeNMT2025.body",
            "SkorowidzeNMT2025",
        )
        assert [r.resolution_m for r in newer] == [0.5]
        session = nmt_session(godlo, "nmt1_evr")
        provider = GugikProvider(session=session)
        record = provider._resolve_sheet(godlo)
        assert file_id(record.url) == "78954_1462161"
        assert record.resolution_m == 1.0
        assert record.aktualnosc == "2023-05-04"
        assert queried_layers(session) == [
            "SkorowidzeNMT2026",
            "SkorowidzeNMT2025",
            "SkorowidzeNMT2024",
            "SkorowidzeNMT2023iStarsze",
        ]

    def test_c3_pooled_records_pick_resolution_by_request(self):
        """Ta sama pula rekordow: 0,5 m -> 2025 (84161), 1 m -> 2023 (78954)."""
        godlo = "M-33-57-C-b-4-2"
        pool = []
        for layer in ("SkorowidzeNMT2025", "SkorowidzeNMT2023iStarsze"):
            pool += layer_records(
                REAL / "nmt" / godlo / f"nmt1_evr__{layer}.body", layer
            )
        half = select_sheet_record(pool, godlo=godlo, uklad="1992", resolution_m=0.5)
        one = select_sheet_record(pool, godlo=godlo, uklad="1992", resolution_m=1.0)
        assert file_id(half.url) == "84161_1849941"
        assert file_id(one.url) == "78954_1462161"

    def test_c6_two_records_of_same_pl2000_sheet_newest_wins(self):
        """7.125.11.19 (PL-2000:S7): 2021-10-05 (75172) i 2023-03-17 (77912)."""
        session = nmt_session("M-34-64-D-d-2-3", "nmt1_evr")
        record = GugikProvider(session=session)._resolve_sheet("7.125.11.19")
        assert file_id(record.url) == "77912_1384976"
        assert (record.uklad, record.zone) == ("2000", 7)
        assert record.aktualnosc == "2023-03-17"

    def test_c6_pl1992_sheet_in_same_body_ignores_pl2000_records(self):
        """Ten sam punkt, godlo PL-1992: wygrywa najnowsza warstwa (2025, 83137)."""
        godlo = "M-34-64-D-d-2-3"
        record = GugikProvider(session=nmt_session(godlo, "nmt1_evr"))._resolve_sheet(
            godlo
        )
        assert file_id(record.url) == "83137_1729557"
        assert record.uklad == "1992"

    def test_campaign_date_beats_dt_pzgik(self):
        """N-33-69-A-d-3-2 (2024): 2024-09-23 (81025) przed 2024-07-21 (81616),
        choc ten drugi ma pozniejsze ``dt_pzgik`` (2025-06-20)."""
        godlo = "N-33-69-A-d-3-2"
        records = layer_records(
            REAL / "nmt" / godlo / "nmt1_evr__SkorowidzeNMT2024.body",
            "SkorowidzeNMT2024",
        )
        by_id = {file_id(r.url): r for r in records}
        assert by_id["81616_1669599"].dt_pzgik > by_id["81025_1562196"].dt_pzgik
        record = GugikProvider(session=nmt_session(godlo, "nmt1_evr"))._resolve_sheet(
            godlo
        )
        assert file_id(record.url) == "81025_1562196"

    def test_c9_xyz_record_is_parsed_but_never_decides(self):
        """Rekord ``.xyz`` (72675, 2019-04-29) jest czytany (H1: bez filtra
        rozszerzenia), ale przegrywa z nowszymi."""
        godlo = "N-33-69-A-d-3-2"
        records = layer_records(
            REAL / "nmt" / godlo / "nmt1_evr__SkorowidzeNMT2023iStarsze.body",
            "SkorowidzeNMT2023iStarsze",
        )
        assert [r.url.rsplit(".", 1)[-1] for r in records].count("xyz") == 1
        assert len(records) == 3
        chosen = select_sheet_record(records, godlo=godlo, uklad="1992")
        assert file_id(chosen.url) == "75506_1144309"
        assert chosen.url.endswith(".asc")

    def test_c9_uppercase_asc_record_is_available_but_loses_to_newer_layer(self):
        """5 m N-33-115-C-d-2-2: ``.ASC`` z 2022iStarsze ma byc dostepny sam,
        lecz w calym skorowidzu wygrywa 2025-03-20 (``.asc``)."""
        godlo = "N-33-115-C-d-2-2"
        old = layer_records(
            REAL / "nmt" / godlo / "nmt5_evr__SkorowidzeNMT2022iStarsze.body",
            "SkorowidzeNMT2022iStarsze",
        )
        assert [r.url.rsplit(".", 1)[-1] for r in old] == ["ASC"]
        alone = select_sheet_record(old, godlo=godlo, uklad="1992", resolution_m=5.0)
        assert alone is not None and alone.url.endswith(".ASC")

        provider = GugikProvider(
            session=nmt_session(godlo, "nmt5_evr"), resolution="5m"
        )
        record = provider._resolve_sheet(godlo)
        assert file_id(record.url) == "83841_1816160"
        assert record.aktualnosc == "2025-03-20"

    def test_c9a_lowercase_godlo_in_record_is_normalised(self):
        """KRON86 N-33-59-C-a-1-3: rekord z ``godlo:"N-33-59-c-a-1-3"`` (male c)."""
        godlo = "N-33-59-C-a-1-3"
        body = (REAL / "nmt" / godlo / "nmt1_krn__SkorowidzeNMT2018.body").read_text(
            encoding="utf-8"
        )
        assert 'godlo:"N-33-59-c-a-1-3"' in body  # surowe body, bez edycji
        provider = GugikProvider(
            session=nmt_session(godlo, "nmt1_krn"), vertical_crs="KRON86"
        )
        record = provider._resolve_sheet(godlo)
        assert file_id(record.url) == "67106_778610"
        assert record.godlo == godlo
        assert provider.source_info(godlo)["godlo"] == godlo


# =============================================================================
# NoCoverageError: podpowiedzi (C6f, C6g, C10g)
# =============================================================================


class TestNoCoverageHintsOnRealBodies:
    def test_c6f_pl2000_1_10000_hints_descendant_scale_and_pl1992_sheet(self):
        godlo = "6.129.30"
        provider = GugikProvider(session=nmt_session(godlo, "nmt1_evr"))
        with pytest.raises(NoCoverageError) as exc:
            provider._resolve_sheet(godlo)
        message = str(exc.value)
        assert "Dostepny potomek 6.129.30.13.4" in message
        assert "--scale 1:1000" in message
        assert "Skorowidz ma ten obszar w PL-1992: M-34-63-A-c-2-1" in message
        assert exc.value.godlo == godlo

    def test_c6g_pl2000_kron86_hint_points_to_1_2000(self):
        godlo = "5.167.25"
        provider = GugikProvider(
            session=nmt_session(godlo, "nmt1_krn"), vertical_crs="KRON86"
        )
        with pytest.raises(NoCoverageError, match="--scale 1:2000") as exc:
            provider._resolve_sheet(godlo)
        assert "5.167.25.13" in str(exc.value)
        # warstwy KRON86: wszystkie sprawdzone, zanim padl brak pokrycia
        assert queried_layers(provider._sessions.injected) == [
            "SkorowidzeNMT2019",
            "SkorowidzeNMT2018",
            "SkorowidzeNMT2017iStarsze",
        ]

    def test_c10g_nmpt_only_half_metre_names_the_resolution(self):
        godlo = "N-33-77-A-d-2-2"
        provider = GugikNmptProvider(session=nmt_session(godlo, "nmpt_evr"))
        with pytest.raises(NoCoverageError) as exc:
            provider._resolve_sheet(godlo)
        assert "GUGiK ma ten arkusz w 0.5 m" in str(exc.value)
        assert "Kartograf pobiera dokladnie 1 m" in str(exc.value)


# =============================================================================
# Orto: RGB/CIR, token godla, niepelny arkusz (C12)
# =============================================================================


class TestOrtoRecordSelectionOnRealBodies:
    GODLO = "N-34-139-A-c-1-1"

    def test_c12_cir_comes_from_2024_when_newer_layer_has_only_rgb(self):
        provider = GugikOrtoProvider(session=orto_session(self.GODLO), color="CIR")
        record = provider._resolve_sheet(self.GODLO)
        assert file_id(record.url) == "81434_1416956"
        assert record.layer == "SkorowidzeOrtofotomapy2024"
        assert record.resolution_m == 0.25
        assert provider.source_info(self.GODLO)["kolor"] == "CIR"

    def test_c12_rgb_comes_from_2025_at_5_cm(self):
        provider = GugikOrtoProvider(session=orto_session(self.GODLO))
        record = provider._resolve_sheet(self.GODLO)
        assert file_id(record.url) == "83235_1485417"
        assert record.layer == "SkorowidzeOrtofotomapy2025"
        assert record.resolution_m == 0.05
        assert provider.source_info(self.GODLO)["kolor"] == "RGB"

    def test_c12_token_parent_request_never_takes_child_records(self):
        """M-34-90-C-b-4 (arkusz nadrzedny) -> jego wlasny rekord 0,75 m z 1997,
        a nie nowsze rekordy potomka M-34-90-C-b-4-4."""
        records = layer_records(
            REAL / "orto" / "M-34-90-C-b-4-4_SkorowidzeOrtofotomapyStarsze.html",
            "SkorowidzeOrtofotomapyStarsze",
        )
        parent = select_sheet_record(
            records,
            godlo="M-34-90-C-b-4",
            uklad="1992",
            predicate=lambda r: r.raw.get("kolor") == "RGB",
        )
        assert file_id(parent.url) == "77300_1184641"
        assert parent.godlo == "M-34-90-C-b-4"

    def test_c12_token_child_request_never_takes_parent_record(self):
        """Z rekordow samego rodzica M-34-90-C-b-4 zadanie M-34-90-C-b-4-4 nie
        wybiera nic (godlo to caly token, nie prefiks)."""
        records = layer_records(
            REAL / "orto" / "M-34-90-C-b-4-4_SkorowidzeOrtofotomapyStarsze.html",
            "SkorowidzeOrtofotomapyStarsze",
        )
        parents = [r for r in records if r.godlo == "M-34-90-C-b-4"]
        assert parents  # rodzic jest w surowym body
        assert (
            select_sheet_record(parents, godlo="M-34-90-C-b-4-4", uklad="1992") is None
        )
        # a prawdziwy rekord arkusza wygrywa z najnowszych: 2022-06-26 RGB (76530)
        child = select_sheet_record(
            records,
            godlo="M-34-90-C-b-4-4",
            uklad="1992",
            predicate=lambda r: r.raw.get("kolor") == "RGB",
        )
        assert file_id(child.url) == "76530_1090199"
        assert child.godlo == "M-34-90-C-b-4-4"

    def test_c12_record_with_full_sheet_false_wins_adr_028(self):
        """M-34-90-C-b-4-4: 2026 (niepelny arkusz) przed pelnym 2024 — bez
        preferencji flagi ``calyArkuszWypelnionyTrescia``."""
        godlo = "M-34-90-C-b-4-4"
        provider = GugikOrtoProvider(session=orto_session(godlo))
        record = provider._resolve_sheet(godlo)
        assert file_id(record.url) == "84466_1602825"
        assert record.full_sheet is False
        assert record.layer == "SkorowidzeOrtofotomapy2026"
        assert provider.source_info(godlo)["full_sheet"] is False

    def test_c12_pl2000_sheet_takes_own_record_not_descendants(self):
        """7.173.21.01: rekord 2021-04-28 (75063), potomki 7.173.21.01.x z 2022
        sa ignorowane (godlo to caly token)."""
        godlo = "7.173.21.01"
        provider = GugikOrtoProvider(session=orto_session(godlo))
        record = provider._resolve_sheet(godlo)
        assert file_id(record.url) == "75063_1038529"
        assert record.godlo == godlo
        assert (record.uklad, record.zone) == ("2000", 7)


# =============================================================================
# Wycinek: arkusze z roznych kampanii (C14)
# =============================================================================


class TestCutoutSheetsFromDifferentCampaigns:
    @pytest.mark.parametrize(
        ("godlo", "expected_id", "layer", "full_sheet"),
        [
            ("N-34-139-C-a-3-1", "84183_1852496", "SkorowidzeNMT2025", False),
            ("N-34-139-C-a-3-2", "83998_1841627", "SkorowidzeNMT2026", True),
            ("N-34-139-C-a-3-3", "84183_1852498", "SkorowidzeNMT2025", False),
            ("N-34-139-C-a-3-4", "83998_1841628", "SkorowidzeNMT2026", True),
        ],
    )
    def test_c14_each_sheet_gets_its_own_newest_campaign(
        self, godlo, expected_id, layer, full_sheet
    ):
        provider = GugikProvider(session=c14_session(godlo))
        record = provider._resolve_sheet(godlo)
        assert file_id(record.url) == expected_id
        assert record.layer == layer
        assert record.full_sheet is full_sheet
        source = provider.source_info(godlo)
        assert source["url"] == record.url
        assert source["full_sheet"] is full_sheet

    def test_c14_four_sheets_four_distinct_sources_two_prefixes(self):
        prefixes = set()
        urls = set()
        for godlo in (f"N-34-139-C-a-3-{n}" for n in range(1, 5)):
            record = GugikProvider(session=c14_session(godlo))._resolve_sheet(godlo)
            prefixes.add(file_id(record.url).split("_")[0])
            urls.add(record.url)
        assert prefixes == {"84183", "83998"}
        assert len(urls) == 4


# =============================================================================
# LAZ: WFS na surowych XML (C13)
# =============================================================================

W2_BBOX = BBox(637200, 486900, 637500, 487100, "EPSG:2180")


def laz_session() -> MagicMock:
    """WFS: GetCapabilities i GetFeature z surowych XML rundy 2026-10-06."""
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


class TestLazDiscoveryOnRealWfs:
    def test_c13_evrf2007_two_tiles_in_two_horizontal_systems(self):
        tiles = GugikLazProvider(session=laz_session()).discover_tiles(W2_BBOX)
        assert [(t.godlo, t.year, t.crs) for t in tiles] == [
            ("7.173.21.06.2", 2022, "PL-2000:S7"),
            ("N-34-139-A-c-1-1-3-4", 2025, "PL-1992"),
        ]
        assert [t.uklad for t in tiles] == ["2000", "1992"]
        assert [t.density for t in tiles] == [15, 12]
        assert tiles[1].url.endswith("83230_1743191_N-34-139-A-c-1-1-3-4.laz")

    def test_c13_year_2023_returns_the_single_older_tile(self):
        session = laz_session()
        tiles = GugikLazProvider(session=session).discover_tiles(W2_BBOX, year=2023)
        assert [(t.godlo, t.year) for t in tiles] == [("N-34-139-A-c-1-1-3-4", 2023)]
        assert file_id(tiles[0].url) == "78044_1403296"
        assert feature_years(session) == ["2023"]

    def test_c13_min_density_13_drops_the_12_p_m2_tile(self):
        tiles = GugikLazProvider(session=laz_session()).discover_tiles(
            W2_BBOX, min_density=13
        )
        assert [t.godlo for t in tiles] == ["7.173.21.06.2"]
        assert tiles[0].crs == "PL-2000:S7"

    def test_c13_kron86_returns_2018_tile_not_2012(self):
        session = laz_session()
        provider = GugikLazProvider(session=session, vertical_crs="KRON86")
        tiles = provider.discover_tiles(W2_BBOX)
        assert [(t.godlo, t.year) for t in tiles] == [("N-34-139-A-c-1-1-3-4", 2018)]
        assert file_id(tiles[0].url) == "70707_846000"
        # rocznik 2012 byl w usludze i zostal odpytany
        assert "2012" in feature_years(session)

    def test_c13_las_format_in_wfs_still_yields_dot_laz_filename(self):
        raw = (REAL_LAZ / "w2_KRON86_2018.xml").read_text(encoding="utf-8")
        assert "<gugik:format>LAS</gugik:format>" in raw  # surowe body
        tile = GugikLazProvider(
            session=laz_session(), vertical_crs="KRON86"
        ).discover_tiles(W2_BBOX)[0]
        assert tile.filename == "70707_846000_N-34-139-A-c-1-1-3-4.laz"
        assert tile.filename.endswith(".laz")
