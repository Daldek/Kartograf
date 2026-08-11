"""Testy SheetIndex / Sm5Sheet — indeks arkuszy KladyMapovychListu (offline).

Fixtury `tests/fixtures/cuzk/*.json` to zapis realnych odpowiedzi uslugi
(rekonesans Zad. 1) — sa zrodlem prawdy dla ksztaltu odpowiedzi i wartosci
atrybutow (MAPNAME "Cesky Tesin 9-6", PODIL 0.99 dla CTES96).
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kartograf.cache import MetadataCache
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import ParseError, ValidationError
from kartograf.providers.cuzk.sheets import (
    KLADY_ENDPOINT,
    SM5_CRS,
    SM5_LAYER,
    TM33_CRS,
    TM33_LAYER,
    SheetIndex,
    SheetInfo,
    Sm5Sheet,
)

FIXTURES = Path(__file__).parent / "fixtures" / "cuzk"

# Koperty uzyte w rekonesansie do wygenerowania fixtur.
BBOX_SM5 = BBox(-450000, -1105000, -440000, -1095000, SM5_CRS)
BBOX_TM33_OVERSEL = BBox(744000, 5534000, 746000, 5536000, TM33_CRS)
BBOX_TM33_BRIEF = BBox(744000, 5540000, 760000, 5556000, TM33_CRS)


def _session_returning(*payloads):
    """Mock requests.Session zwracajacy kolejne payloady JSON."""
    session = Mock()
    responses = []
    for p in payloads:
        r = Mock()
        r.raise_for_status = Mock()
        r.json.return_value = p
        responses.append(r)
    session.get.side_effect = responses
    return session


def _fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _sm5_feature(mapnom, west, south, east, north, name="Test", podil=1.0):
    """Syntetyczny feature warstwy 24 (prostokat)."""
    return {
        "attributes": {"MAPNOM": mapnom, "MAPNAME": name, "PODIL": podil},
        "geometry": {
            "rings": [
                [
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]
            ]
        },
    }


def _collection(*features):
    return {"features": list(features)}


class TestSm5Sheet:
    def test_sm5_sheet_from_fixture(self):
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        index = SheetIndex(session=session)
        info = index.sm5_sheet("CTES96")
        assert isinstance(info, SheetInfo)
        assert info.godlo == "CTES96"
        assert info.name  # MAPNAME obecne
        assert info.podil is not None and 0.0 < info.podil <= 1.0
        assert info.in_cz is None
        assert info.bbox.crs == "EPSG:5514"
        assert info.bbox.min_x < info.bbox.max_x
        # zapytanie poszlo do warstwy 24 z where po MAPNOM
        (url,), kwargs = session.get.call_args
        assert url == f"{KLADY_ENDPOINT}/{SM5_LAYER}/query"
        assert "MAPNOM" in kwargs["params"]["where"]

    def test_sm5_sheet_values_match_fixture(self):
        """Wartosci z realnej odpowiedzi (nie ze starego researchu: 9-6, 0.99)."""
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        info = SheetIndex(session=session).sm5_sheet("CTES96")
        assert info.name == "Český Těšín 9-6"
        assert info.podil == pytest.approx(0.99)
        assert info.bbox.min_x == pytest.approx(-450000, abs=0.01)
        assert info.bbox.min_y == pytest.approx(-1114000, abs=0.01)
        assert info.bbox.max_x == pytest.approx(-447500, abs=0.01)
        assert info.bbox.max_y == pytest.approx(-1112000, abs=0.01)

    def test_sm5_sheet_query_params(self):
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        SheetIndex(session=session).sm5_sheet("CTES96")
        params = session.get.call_args.kwargs["params"]
        assert params["where"] == "MAPNOM='CTES96'"
        assert params["outSR"] == "5514"
        assert params["returnGeometry"] == "true"
        for field in ("MAPNOM", "MAPNAME", "PODIL"):
            assert field in params["outFields"]

    def test_unknown_mapnom_raises_validation_error(self):
        session = _session_returning({"features": []})
        index = SheetIndex(session=session)
        with pytest.raises(ValidationError, match="ZZZZ99"):
            index.sm5_sheet("ZZZZ99")

    def test_malformed_mapnom_rejected_before_network(self):
        session = Mock()
        index = SheetIndex(session=session)
        with pytest.raises(ValidationError):
            index.sm5_sheet("ctes96")  # male litery — nie przechodzi wzorca
        session.get.assert_not_called()

    def test_feature_without_geometry_raises_parse_error(self):
        session = _session_returning(_collection({"attributes": {"MAPNOM": "CTES96"}}))
        with pytest.raises(ParseError, match="CTES96"):
            SheetIndex(session=session).sm5_sheet("CTES96")

    def test_without_cache_every_call_queries(self):
        session = _session_returning(
            _fixture("klady_sm5_where_ctes96.json"),
            _fixture("klady_sm5_where_ctes96.json"),
        )
        index = SheetIndex(session=session)
        assert index.sm5_sheet("CTES96") == index.sm5_sheet("CTES96")
        assert session.get.call_count == 2

    def test_cache_hit_skips_network(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "c.db")
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        index = SheetIndex(session=session, cache=cache)
        first = index.sm5_sheet("CTES96")
        second = index.sm5_sheet("CTES96")
        assert first == second
        assert session.get.call_count == 1
        assert cache.stats()["sheet_count"] == 1
        cache.close()

    def test_cache_shared_between_instances(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "c.db")
        session1 = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        SheetIndex(session=session1, cache=cache).sm5_sheet("CTES96")
        session2 = Mock()
        info = SheetIndex(session=session2, cache=cache).sm5_sheet("CTES96")
        assert info.godlo == "CTES96"
        session2.get.assert_not_called()
        cache.close()

    def test_cache_payload_is_json_round_trip_of_info(self):
        """To, co trafia do set_sheet, odtwarza dokladnie ten sam SheetInfo."""
        cache = Mock()
        cache.get_sheet.return_value = None
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        info = SheetIndex(session=session, cache=cache).sm5_sheet("CTES96")

        cache.get_sheet.assert_called_once_with("cz_sm5", "CTES96")
        system, godlo, payload = cache.set_sheet.call_args.args
        assert (system, godlo) == ("cz_sm5", "CTES96")
        # payload musi przejsc przez JSON (tak zapisuje go MetadataCache)
        decoded = json.loads(json.dumps(payload, ensure_ascii=False))

        replay_cache = Mock()
        replay_cache.get_sheet.return_value = decoded
        replay_session = Mock()
        replayed = SheetIndex(session=replay_session, cache=replay_cache).sm5_sheet(
            "CTES96"
        )
        assert replayed == info
        replay_session.get.assert_not_called()

    def test_corrupt_cache_payload_falls_back_to_query(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "c.db")
        cache.set_sheet("cz_sm5", "CTES96", {"godlo": "CTES96"})  # bez bbox
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        info = SheetIndex(session=session, cache=cache).sm5_sheet("CTES96")
        assert info.bbox.crs == SM5_CRS
        assert session.get.call_count == 1
        cache.close()


class TestBboxQueries:
    def test_sm5_sheets_for_bbox(self):
        session = _session_returning(_fixture("klady_sm5_bbox.json"))
        index = SheetIndex(session=session)
        infos = index.sm5_sheets_for_bbox(BBOX_SM5)
        assert len(infos) >= 1
        assert all(i.bbox.crs == "EPSG:5514" for i in infos)
        params = session.get.call_args.kwargs["params"]
        assert params["geometryType"] == "esriGeometryEnvelope"
        assert params["inSR"] == "5514"
        assert params["spatialRel"] == "esriSpatialRelIntersects"

    def test_sm5_sheets_for_bbox_drops_edge_touching_sheets(self):
        """13 features z uslugi -> 7 przecinajacych koperte wnetrzem (Zad. 1, 3b).

        Odrzucone arkusze maja wschodnia krawedz dokladnie na xmin koperty.
        """
        fixture = _fixture("klady_sm5_bbox.json")
        assert len(fixture["features"]) == 13
        session = _session_returning(fixture)
        infos = SheetIndex(session=session).sm5_sheets_for_bbox(BBOX_SM5)
        assert [i.godlo for i in infos] == [
            "CTES80",
            "CTES90",
            "CTES91",
            "CTES92",
            "DMAR97",
            "DMAR98",
            "DMAR99",
        ]

    def test_tm33_tiles_for_bbox(self):
        """Koperta = dokladnie 1 kafel; usluga zwraca 9 (sasiedztwo 3x3)."""
        fixture = _fixture("klady_tm33_bbox_oversel.json")
        assert len(fixture["features"]) == 9
        session = _session_returning(fixture)
        index = SheetIndex(session=session)
        infos = index.tm33_tiles_for_bbox(BBOX_TM33_OVERSEL)
        assert [i.godlo for i in infos] == ["744_5534"]
        first = infos[0]
        assert first.in_cz in (True, False)
        assert first.podil is None
        assert first.name is None
        assert first.bbox.crs == "EPSG:3045"
        (url,), kwargs = session.get.call_args
        assert url == f"{KLADY_ENDPOINT}/{TM33_LAYER}/query"
        assert kwargs["params"]["outSR"] == "3045"
        assert "IN_CZ" in kwargs["params"]["outFields"]

    def test_tm33_tiles_for_bbox_drops_krovak_halo(self):
        """Fixtura z briefu: jedyny zwrocony kafel lezy 2 km na S od koperty.

        Halo powstaje z reprojekcji koperty 3045 -> Krovak po stronie serwera
        (rekonesans Zad. 1, dowod 3) — filtr klienta musi je usunac.
        """
        session = _session_returning(_fixture("klady_tm33_bbox.json"))
        assert SheetIndex(session=session).tm33_tiles_for_bbox(BBOX_TM33_BRIEF) == []

    def test_filter_tolerates_arcgis_coordinate_noise(self):
        """Styk krawedzia (~1e-4 m szumu) odpada; realne przeciecie zostaje."""
        payload = _collection(
            _sm5_feature("AAAA01", -452500, -1105000, -449999.9995, -1095000),
            _sm5_feature("AAAA02", -452500, -1105000, -449999.0, -1095000),
            _sm5_feature("AAAA03", -448000, -1095000.0005, -446000, -1090000),
            _sm5_feature("AAAA04", -448000, -1095999.0, -446000, -1090000),
        )
        session = _session_returning(payload)
        infos = SheetIndex(session=session).sm5_sheets_for_bbox(BBOX_SM5)
        assert [i.godlo for i in infos] == ["AAAA02", "AAAA04"]

    def test_multi_ring_geometry_uses_envelope_of_all_rings(self):
        """Wielokat wieloczesciowy/z dziurami: obwiednia wszystkich pierscieni."""
        feature = _sm5_feature("BBBB01", -449000, -1104000, -448000, -1103000)
        feature["geometry"]["rings"].append(
            [
                [-446000, -1099000],
                [-445000, -1099000],
                [-445000, -1098000],
                [-446000, -1098000],
                [-446000, -1099000],
            ]
        )
        session = _session_returning(_collection(feature))
        infos = SheetIndex(session=session).sm5_sheets_for_bbox(BBOX_SM5)
        assert infos[0].bbox == BBox(-449000, -1104000, -445000, -1098000, SM5_CRS)

    @pytest.mark.parametrize(
        "method,bbox",
        [
            ("sm5_sheets_for_bbox", BBOX_TM33_OVERSEL),
            ("tm33_tiles_for_bbox", BBOX_SM5),
        ],
    )
    def test_wrong_bbox_crs_rejected_before_network(self, method, bbox):
        session = Mock()
        index = SheetIndex(session=session)
        with pytest.raises(ValidationError, match="EPSG:"):
            getattr(index, method)(bbox)
        session.get.assert_not_called()

    @pytest.mark.parametrize(
        "bbox",
        [
            BBox(-450000, -1105000, -450000, -1095000, SM5_CRS),
            BBox(-450000, -1095000, -440000, -1095000, SM5_CRS),
            BBox(-440000, -1105000, -450000, -1095000, SM5_CRS),
        ],
    )
    def test_degenerate_bbox_rejected_before_network(self, bbox):
        session = Mock()
        index = SheetIndex(session=session)
        with pytest.raises(ValidationError):
            index.sm5_sheets_for_bbox(bbox)
        session.get.assert_not_called()

    def test_bbox_queries_do_not_touch_cache(self, tmp_path):
        """Cache trzyma pojedyncze arkusze (klucz godlo) — nie wyniki bbox."""
        cache = MetadataCache(db_path=tmp_path / "c.db")
        session = _session_returning(_fixture("klady_sm5_bbox.json"))
        SheetIndex(session=session, cache=cache).sm5_sheets_for_bbox(BBOX_SM5)
        assert cache.stats()["sheet_count"] == 0
        cache.close()


class TestSm5SheetParserObject:
    def test_attributes(self):
        sheet = Sm5Sheet("CTES96")
        assert sheet.godlo == "CTES96"
        assert sheet.uklad == "cz_sm5"
        assert repr(sheet) == "Sm5Sheet('CTES96')"

    def test_whitespace_stripped(self):
        assert Sm5Sheet("  CTES96 ").godlo == "CTES96"

    @pytest.mark.parametrize(
        "godlo", ["302_5550", "ctes96", "CTES9", "CTES961", "", 123, None]
    )
    def test_invalid_godlo_raises_parse_error(self, godlo):
        with pytest.raises(ParseError):
            Sm5Sheet(godlo)

    def test_get_bbox_is_lazy_and_delegates(self):
        """Konstrukcja bez IO; get_bbox dopiero pyta indeks."""
        session = _session_returning(_fixture("klady_sm5_where_ctes96.json"))
        index = SheetIndex(session=session)
        sheet = Sm5Sheet("CTES96", index=index)
        session.get.assert_not_called()
        bbox = sheet.get_bbox()
        assert bbox.crs == "EPSG:5514"
        assert session.get.call_count == 1

    def test_get_bbox_without_index_builds_cached_index_lazily(self):
        """Bez wstrzyknietego indeksu: budowa dopiero w get_bbox, z cache."""
        with (
            patch("kartograf.providers.cuzk.sheets.SheetIndex") as index_cls,
            patch("kartograf.providers.cuzk.sheets.MetadataCache") as cache_cls,
        ):
            sheet = Sm5Sheet("CTES96")
            index_cls.assert_not_called()
            cache_cls.assert_not_called()
            bbox = sheet.get_bbox()
            index_cls.assert_called_once_with(cache=cache_cls.return_value)
            index_cls.return_value.sm5_sheet.assert_called_once_with("CTES96")
            assert bbox is index_cls.return_value.sm5_sheet.return_value.bbox
