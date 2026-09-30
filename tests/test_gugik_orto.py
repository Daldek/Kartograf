"""
Testy jednostkowe dla modułu gugik_orto provider.

GugikOrtoProvider konsumuje wspolny modul skorowidza (K5, D4, D5):
- download(godlo) → skorowidz (warstwy od najnowszej) → OpenData (TIF)
- wybor pliku: godlo jako caly token, uklad z formatu godla, wariant koloru
  (domyslnie RGB) jako filtr twardy, potem najnowsza `aktualnosc`
- download_bbox(bbox) → WCS (GeoTIFF/PNG/JPEG)

Probki w ``tests/fixtures/gugik_skorowidz/``: ``orto_2024.html`` (surowa
odpowiedz GUGiK: CIR przed RGB) i ``orto_starsze.html`` (warstwa zbiorcza,
rekordy rosnaco po dacie, godla PL-1992 i PL-2000, arkusz nadrzedny).
"""

import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from kartograf.cache.metadata import MetadataCache
from kartograf.core.sheet_parser import BBox
from kartograf.exceptions import DownloadError, NoCoverageError
from kartograf.providers.pl.gugik_orto import GugikOrtoProvider
from tests.conftest import render_gfi_body

FIXTURES = Path(__file__).parent / "fixtures" / "gugik_skorowidz"
ENDPOINT = GugikOrtoProvider.WMS_SKOROWIDZE_ENDPOINT
LAYERS = [
    "SkorowidzeOrtofotomapy2026",
    "SkorowidzeOrtofotomapy2025",
    "SkorowidzeOrtofotomapy2024",
    "SkorowidzeOrtofotomapyStarsze",
]
GODLO = "M-34-76-A-a-1-1"
RGB_2024 = "https://opendata.geoportal.gov.pl/ortofotomapa/81423/81423_1371958_M-34-76-A-a-1-1.tif"
CIR_2024 = "https://opendata.geoportal.gov.pl/ortofotomapa/81422/81422_1368112_M-34-76-A-a-1-1.tif"
SESSION_FACTORY = "kartograf.providers.pl.skorowidz.make_gugik_session"


def sample(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def orto_record(
    godlo: str = GODLO,
    *,
    kolor: str = "RGB",
    aktualnosc: str = "2024-06-21",
    uklad: str = "PL-1992",
    url: str | None = None,
    **fields: str,
) -> dict:
    """Rekord skorowidza orto o polach jak w odpowiedzi GUGiK (2026-09-29)."""
    record = {
        "url": url
        or f"https://opendata.geoportal.gov.pl/ortofotomapa/81423/81423_1_{godlo}.tif",
        "godlo": godlo,
        "aktualnosc": aktualnosc,
        "wielkoscPiksela": "0.25",
        "ukladWspolrzednych": uklad,
        "calyArkuszWyeplnionyTrescia": "TAK",
        "modulArchiwizacji": "1:5000",
        "rozmiarPlikuMB": "41",
        "zrodloDanych": "Zdj. cyfrowe",
        "kolor": kolor,
        "numerZgloszeniaPracy": "DFT.7201.014.2024",
        "aktualnoscRok": aktualnosc[:4],
        "dt_pzgik": "2025-04-14",
    }
    record.update(fields)
    return record


def orto_body(records: list[dict]) -> str:
    return render_gfi_body(records, var="skorDo5cm")


def gfi_response(body: str) -> Mock:
    """Atrapa odpowiedzi HTTP 200 skorowidza (GetFeatureInfo / GetCapabilities)."""
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.text = body
    response.raise_for_status = Mock()
    return response


def file_response(chunks: list[bytes] | None = None) -> Mock:
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.raise_for_status = Mock()
    response.iter_content = Mock(return_value=chunks or [b"TIFF header data\x00"])
    return response


def queried_layers(session: Mock) -> list[str]:
    from urllib.parse import parse_qs, urlparse

    return [
        parse_qs(urlparse(call.args[0]).query)["LAYERS"][0]
        for call in session.get.call_args_list
        if "GetFeatureInfo" in call.args[0]
    ]


class TestGugikOrtoProviderInit:
    """Testy inicjalizacji GugikOrtoProvider."""

    def test_init_no_args(self):
        """Test tworzenia providera bez argumentów (domyślne wartości)."""
        provider = GugikOrtoProvider()
        assert provider._session is None
        assert provider.color == "RGB"

    def test_init_with_session(self):
        """Test tworzenia providera z własną sesją HTTP."""
        session = Mock(spec=requests.Session)
        provider = GugikOrtoProvider(session=session)
        assert provider._session is session

    def test_color_kwarg(self):
        """Wariant koloru to kwarg biblioteki (bez flagi CLI)."""
        assert GugikOrtoProvider(color="CIR").color == "CIR"

    def test_no_vertical_crs(self):
        """Test że provider nie ma atrybutu vertical_crs (w odróżnieniu od NMT/NMPT)."""
        provider = GugikOrtoProvider()
        assert not hasattr(provider, "vertical_crs")

    def test_no_resolution(self):
        """Test że provider nie ma atrybutu resolution (w odróżnieniu od NMT)."""
        provider = GugikOrtoProvider()
        assert not hasattr(provider, "resolution")


class TestGugikOrtoProviderProperties:
    """Testy właściwości GugikOrtoProvider."""

    def test_name(self):
        """Test nazwy providera."""
        provider = GugikOrtoProvider()
        assert provider.name == "GUGiK Ortofotomapa"

    def test_base_url(self):
        """Test bazowego URL geoportal."""
        provider = GugikOrtoProvider()
        assert provider.base_url == "https://mapy.geoportal.gov.pl"

    def test_default_extension(self):
        """Test domyślnego rozszerzenia pliku."""
        provider = GugikOrtoProvider()
        assert provider.default_extension == ".tif"

    def test_repr(self):
        """Test metody __repr__ — zawiera nazwę klasy."""
        provider = GugikOrtoProvider()
        repr_str = repr(provider)
        assert "GugikOrtoProvider" in repr_str

    def test_str(self):
        """Test metody __str__ — zawiera nazwę providera."""
        provider = GugikOrtoProvider()
        str_repr = str(provider)
        assert "GUGiK Ortofotomapa" in str_repr


class TestGugikOrtoProviderDownload:
    """Testy pobierania przez godło (skorowidz → OpenData)."""

    @pytest.fixture
    def session(self):
        """Sesja: warstwa 2026 ma arkusz (CIR przed RGB), potem plik."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[gfi_response(sample("orto_2024.html")), file_response()]
        )
        return session

    def test_download_success(self, tmp_path, session):
        """download(godlo) pyta skorowidz, pobiera URL RGB i zapisuje plik."""
        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "sheet.tif"

        result = provider.download(GODLO, output_path)

        assert result == output_path
        assert output_path.exists()
        first_call_url = session.get.call_args_list[0][0][0]
        assert "GetFeatureInfo" in first_call_url
        assert session.get.call_args_list[1][0][0] == RGB_2024

    def test_download_creates_directory(self, tmp_path, session):
        """Katalog docelowy powstaje dopiero przy zapisie pliku."""
        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "subdir" / "nested" / "sheet.tif"

        result = provider.download(GODLO, output_path)

        assert result == output_path
        assert output_path.parent.exists()

    def test_download_saves_content(self, tmp_path, session):
        """Test że download zapisuje zawartość pliku na dysk."""
        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "sheet.tif"

        provider.download(GODLO, output_path)

        assert b"TIFF header data" in output_path.read_bytes()

    def test_no_coverage_leaves_no_directory(self, tmp_path):
        """N1: arkusz bez danych nie zostawia pustego katalogu."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(orto_body([])))
        output = tmp_path / "not-created" / "sheet.tif"

        with pytest.raises(NoCoverageError):
            GugikOrtoProvider(session=session).download(GODLO, output)

        assert not output.parent.exists()


class TestGugikOrtoProviderSelection:
    """K5: wariant RGB + najnowsza kampania, godlo jako caly token, uklad z godla."""

    @staticmethod
    def provider_with(*bodies: str) -> tuple[GugikOrtoProvider, Mock]:
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[gfi_response(body) for body in bodies])
        return GugikOrtoProvider(session=session), session

    def test_picks_rgb_not_first_record(self):
        """Surowa odpowiedz GUGiK (CIR przed RGB) -> URL RGB, nie pierwszy w HTML."""
        provider, session = self.provider_with(sample("orto_2024.html"))

        assert provider._get_opendata_url(GODLO) == RGB_2024
        assert session.get.call_count == 1

    def test_source_info_carries_kolor_and_campaign(self):
        """extra.source (D5): url, warstwa, aktualnosc, piksel i kolor pliku."""
        provider, _ = self.provider_with(sample("orto_2024.html"))
        provider._get_opendata_url(GODLO)

        source = provider.source_info(GODLO)
        assert source["url"] == RGB_2024
        assert source["kolor"] == "RGB"
        assert source["aktualnosc"] == "2024-06-21"
        assert source["layer"] == "SkorowidzeOrtofotomapy2026"
        assert source["resolution_m"] == 0.25
        assert source["uklad"] == "PL-1992"
        assert source["skorowidz"] == ENDPOINT

    def test_starsze_picks_newest_rgb_not_oldest(self):
        """Warstwa zbiorcza rosnaco po dacie -> najnowsze RGB, nie 1997/2003 B-W."""
        empty = orto_body([])
        provider, session = self.provider_with(
            empty, empty, empty, sample("orto_starsze.html")
        )

        url = provider._get_opendata_url(GODLO)

        assert url.endswith("76530_1087101_M-34-76-A-a-1-1.tif")
        assert queried_layers(session) == LAYERS
        assert provider.source_info(GODLO)["aktualnosc"] == "2022-06-03"

    def test_pl2000_godlo_gets_pl2000_record(self):
        """Godlo PL-2000 dostaje rekord PL-2000, nie CIR PL-1992 z pierwszej warstwy."""
        provider, _ = self.provider_with(
            sample("orto_2024.html"),
            orto_body([]),
            orto_body([]),
            sample("orto_starsze.html"),
        )

        url = provider._get_opendata_url("7.124.07.24")

        assert url.endswith("64878_364829_7.124.07.24.tif")
        assert provider.source_info("7.124.07.24")["uklad"] == "PL-2000:S7"

    def test_pl1992_godlo_never_takes_pl2000_or_parent_sheet(self):
        """Arkusz nadrzedny (M-34-76-A-a-1) i rekord PL-2000 nie zastepuja arkusza."""
        body = orto_body(
            [
                orto_record(
                    "M-34-76-A-a-1",
                    aktualnosc="1997-01-01",
                    url="https://opendata.geoportal.gov.pl/ortofotomapa/77300/77300_1185016_M-34-76-A-a-1.tif",
                ),
                orto_record(
                    "7.124.07.24",
                    uklad="PL-2000:S7",
                    aktualnosc="2015-04-23",
                    url="https://opendata.geoportal.gov.pl/ortofotomapa/64878/64878_364829_7.124.07.24.tif",
                ),
            ]
        )
        provider, _ = self.provider_with(*[body] * 4)

        with pytest.raises(NoCoverageError) as exc:
            provider._get_opendata_url(GODLO)

        message = str(exc.value)
        assert "Brak ortofotomapy RGB dla M-34-76-A-a-1-1" in message
        assert "PL-2000: 7.124.07.24" in message

    def test_only_cir_and_bw_raises_no_coverage_with_variants(self):
        """Tylko CIR/B-W = NoCoverageError z lista wariantow (kolor + data)."""
        body = orto_body(
            [
                orto_record(kolor="B/W", aktualnosc="2003-01-01"),
                orto_record(kolor="CIR", aktualnosc="2024-06-21", url=CIR_2024),
            ]
        )
        provider, _ = self.provider_with(*[body] * 4)

        with pytest.raises(NoCoverageError, match="Dostepne warianty") as exc:
            provider._get_opendata_url(GODLO)

        message = str(exc.value)
        assert "B/W 2003-01-01, CIR 2024-06-21" in message
        assert exc.value.godlo == GODLO

    def test_color_kwarg_selects_other_variant(self):
        """color="CIR" pobiera CIR — kolor to filtr twardy, nie preferencja."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(sample("orto_2024.html")))

        provider = GugikOrtoProvider(session=session, color="CIR")

        assert provider._get_opendata_url(GODLO) == CIR_2024
        assert provider.source_info(GODLO)["kolor"] == "CIR"

    def test_stops_at_first_layer_with_matching_variant(self):
        """P2: rekord w warstwie rocznej konczy petle — starsze warstwy niepytane."""
        provider, session = self.provider_with(
            orto_body([]),
            orto_body([orto_record(aktualnosc="2025-07-02")]),
        )

        provider._get_opendata_url(GODLO)

        assert queried_layers(session) == LAYERS[:2]

    def test_continues_past_layer_with_only_other_variant(self):
        """Warstwa z samym CIR nie konczy szukania RGB w starszych warstwach."""
        rgb_2025 = orto_record(aktualnosc="2025-07-02")
        provider, session = self.provider_with(
            orto_body([orto_record(kolor="CIR", aktualnosc="2026-05-01")]),
            orto_body([rgb_2025]),
        )

        assert provider._get_opendata_url(GODLO) == rgb_2025["url"]
        assert queried_layers(session) == LAYERS[:2]

    def test_all_layers_empty_is_no_coverage(self):
        """Puste odpowiedzi wszystkich warstw = NoCoverageError po polsku."""
        provider, session = self.provider_with(*[orto_body([])] * 4)

        with pytest.raises(NoCoverageError, match="Brak ortofotomapy RGB"):
            provider._get_opendata_url(GODLO)

        assert queried_layers(session) == LAYERS

    def test_newer_layer_failure_is_error_not_older_campaign(self):
        """K3 dla orto: zerwana warstwa = DownloadError, nie URL ze starszej."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset")] * 3
            + [gfi_response(sample("orto_2024.html"))]
        )
        provider = GugikOrtoProvider(session=session)

        with patch("time.sleep") as sleep, pytest.raises(DownloadError) as exc:
            provider._get_opendata_url(GODLO)

        assert not isinstance(exc.value, NoCoverageError)
        assert "SkorowidzeOrtofotomapy2026" in str(exc.value)
        assert session.get.call_count == 3
        assert sleep.call_count == 2

    def test_ogc_exception_is_error_not_no_coverage(self):
        """Raport wyjatku OGC (np. zla warstwa) nie jest brakiem pokrycia."""
        provider, session = self.provider_with(sample("ogc_exception.body"))

        with pytest.raises(DownloadError) as exc:
            provider._get_opendata_url(GODLO)

        assert not isinstance(exc.value, NoCoverageError)
        assert session.get.call_count == 1


class TestGugikOrtoProviderCache:
    """MetadataCache: klucz (orto, <kolor>, none, godlo); payload source/no_coverage."""

    @pytest.fixture
    def cache(self, tmp_path):
        cache = MetadataCache(db_path=tmp_path / "cache.db")
        yield cache
        cache.close()

    @pytest.fixture
    def source(self):
        provider = GugikOrtoProvider(
            session=Mock(get=Mock(return_value=gfi_response(sample("orto_2024.html"))))
        )
        provider._get_opendata_url(GODLO)
        return provider.source_info(GODLO)

    def test_cache_hit_source_skips_network(self, cache, source):
        """Trafienie `source` = zero sieci; URL i source_info z payloadu."""
        cache.set_record("orto", "RGB", "none", GODLO, {"source": source})
        session = Mock(spec=requests.Session)
        provider = GugikOrtoProvider(session=session, cache=cache)

        assert provider._get_opendata_url(GODLO) == RGB_2024
        session.get.assert_not_called()
        assert provider.source_info(GODLO) == source

    def test_cache_hit_no_coverage_raises_without_network(self, cache):
        cache.set_record("orto", "RGB", "none", GODLO, {"no_coverage": True})
        session = Mock(spec=requests.Session)
        provider = GugikOrtoProvider(session=session, cache=cache)

        with pytest.raises(NoCoverageError, match=GODLO):
            provider._get_opendata_url(GODLO)
        session.get.assert_not_called()

    def test_negative_cache_preserves_variant_hint(self, cache):
        body = orto_body(
            [orto_record(kolor="CIR", aktualnosc="2024-06-21", url=CIR_2024)]
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(body))
        provider = GugikOrtoProvider(session=session, cache=cache)

        with pytest.raises(NoCoverageError) as first:
            provider._get_opendata_url(GODLO)
        calls = session.get.call_count
        with pytest.raises(NoCoverageError) as cached:
            provider._get_opendata_url(GODLO)
        assert session.get.call_count == calls
        assert str(cached.value) == str(first.value)
        assert "CIR 2024-06-21" in str(cached.value)

    def test_cache_miss_stores_source_with_kolor(self, cache):
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(sample("orto_2024.html")))
        provider = GugikOrtoProvider(session=session, cache=cache)

        assert provider._get_opendata_url(GODLO) == RGB_2024

        cached = cache.get_record("orto", "RGB", "none", GODLO)
        assert cached["source"]["url"] == RGB_2024
        assert cached["source"]["kolor"] == "RGB"
        assert cached["source"]["layer"] == "SkorowidzeOrtofotomapy2026"
        assert provider.source_info(GODLO) == cached["source"]

    def test_cache_key_distinguishes_color(self, cache, source):
        """Wpis RGB nie obsluguje providera CIR — inny plik, inny klucz."""
        cache.set_record("orto", "RGB", "none", GODLO, {"source": source})
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(sample("orto_2024.html")))
        provider = GugikOrtoProvider(session=session, cache=cache, color="CIR")

        assert provider._get_opendata_url(GODLO) == CIR_2024

        assert session.get.call_count == 1
        assert cache.get_record("orto", "CIR", "none", GODLO)["source"]["url"] == (
            CIR_2024
        )
        assert cache.get_record("orto", "RGB", "none", GODLO) == {"source": source}

    def test_all_layers_empty_stores_no_coverage(self, cache):
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(orto_body([])))
        provider = GugikOrtoProvider(session=session, cache=cache)

        with pytest.raises(NoCoverageError) as exc:
            provider._get_opendata_url(GODLO)

        assert cache.get_record("orto", "RGB", "none", GODLO) == {
            "no_coverage": True,
            "message": str(exc.value),
        }

    def test_query_failure_is_not_cached(self, cache):
        """K3-safe: awaria sieci = DownloadError, cache zostaje pusty."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=[requests.ConnectionError("boom")] * 3)
        provider = GugikOrtoProvider(session=session, cache=cache)

        with patch("time.sleep"), pytest.raises(DownloadError):
            provider._get_opendata_url(GODLO)

        assert cache.get_record("orto", "RGB", "none", GODLO) is None

    def test_no_cache_backward_compat(self):
        """cache=None: to samo rozstrzygniecie, bez zapisu."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(sample("orto_2024.html")))

        assert GugikOrtoProvider(session=session)._get_opendata_url(GODLO) == RGB_2024


ORTO_WMS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities xmlns="http://www.opengis.net/wms" version="1.3.0">
  <Capability><Layer><Layer>
    <Name>SkorowidzeOrtofotomapy2024</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapyStarsze</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapy2026</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapy2025</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapyZasiegi2026</Name>
  </Layer><Layer>
    <Name>SkorowidzeOrtofotomapyZasiegiStarsze</Name>
  </Layer><Layer>
    <Name>SkorowidzeNMT2026</Name>
  </Layer></Layer></Capability>
</WMS_Capabilities>
"""


@pytest.mark.real_wms_layers
class TestGugikOrtoLayerDiscovery:
    """GetCapabilities przez sesje watku, filtr LAYER_PATTERN, bez zaszytej listy."""

    def test_fetch_orto_layers_sorts_and_excludes_zasiegi(self):
        """Roczne malejaco, Starsze na koncu; Zasiegi i inne produkty pominiete."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(ORTO_WMS_XML))

        result = GugikOrtoProvider(session=session)._fetch_wms_layers(ENDPOINT)

        assert result == LAYERS
        assert "GetCapabilities" in session.get.call_args.args[0]

    def test_no_matching_layers_raises_download_error(self):
        xml = ORTO_WMS_XML.replace("SkorowidzeOrtofotomapy", "SkorowidzeInne")
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(xml))

        with pytest.raises(DownloadError, match="nie publikuje warstw"):
            GugikOrtoProvider(session=session)._fetch_wms_layers(ENDPOINT)

    def test_get_opendata_url_fails_before_get_feature_info(self):
        """Awaria GetCapabilities po 3 probach = DownloadError, zero GetFeatureInfo."""
        session = Mock(spec=requests.Session)
        session.get = Mock(side_effect=requests.ConnectionError("reset"))
        provider = GugikOrtoProvider(session=session)

        with patch("time.sleep"), pytest.raises(DownloadError) as exc:
            provider._get_opendata_url(GODLO)

        assert not isinstance(exc.value, NoCoverageError)
        assert session.get.call_count == 3
        assert queried_layers(session) == []

    def test_layers_memoizes_success_only(self):
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[requests.ConnectionError("reset")] * 3
            + [gfi_response(ORTO_WMS_XML)]
        )
        provider = GugikOrtoProvider(session=session)

        with patch("time.sleep"), pytest.raises(DownloadError):
            provider._layers(ENDPOINT)
        assert provider._layers(ENDPOINT) == LAYERS
        assert provider._layers(ENDPOINT) == LAYERS

        assert session.get.call_count == 4


class TestGugikOrtoProviderSession:
    """Sesja wstrzyknieta obsluguje wszystko; bez niej jedna sesja na watek."""

    def test_uses_provided_session_for_index_and_file(self, tmp_path):
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[gfi_response(sample("orto_2024.html")), file_response()]
        )

        with patch(SESSION_FACTORY) as factory:
            GugikOrtoProvider(session=session).download(GODLO, tmp_path / "s.tif")

        factory.assert_not_called()
        assert session.get.call_count == 2
        assert session.get.call_args_list[1].kwargs["stream"] is True

    def test_one_session_per_thread(self):
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=gfi_response(sample("orto_2024.html")))

        with patch(SESSION_FACTORY, return_value=session) as factory:
            provider = GugikOrtoProvider()
            provider._get_opendata_url(GODLO)
            provider._get_opendata_url(GODLO)

        factory.assert_called_once()
        assert session.get.call_count == 2

    def test_separate_session_per_thread(self):
        sessions: list[Mock] = []
        results: list[str] = []
        errors: list[Exception] = []

        def new_session():
            session = Mock(spec=requests.Session)
            session.get = Mock(return_value=gfi_response(sample("orto_2024.html")))
            sessions.append(session)
            return session

        with patch(SESSION_FACTORY, side_effect=new_session) as factory:
            provider = GugikOrtoProvider()

            def worker():
                try:
                    results.append(provider._get_opendata_url(GODLO))
                except Exception as exc:  # noqa: BLE001 — zbieramy do asercji
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        assert errors == []
        assert factory.call_count == 2
        assert [session.get.call_count for session in sessions] == [1, 1]
        assert results == [RGB_2024] * 2


class TestGugikOrtoProviderDownloadBbox:
    """Testy pobierania przez bbox (WCS)."""

    @pytest.fixture
    def mock_wcs_response(self):
        """Mock odpowiedzi WCS."""
        return file_response([b"TIFF data..."])

    @pytest.fixture
    def sample_bbox(self):
        """Przykładowy bbox w EPSG:2180."""
        return BBox(
            min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180"
        )

    def test_download_bbox_success(self, tmp_path, mock_wcs_response, sample_bbox):
        """Test że download_bbox pobiera dane przez WCS."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "area.tif"

        result = provider.download_bbox(sample_bbox, output_path)

        assert result == output_path
        assert output_path.exists()

        call_url = session.get.call_args[0][0]
        assert "WCS" in call_url
        assert "SUBSET=x(" in call_url
        assert "SUBSET=y(" in call_url

    def test_download_bbox_url_contains_coverage_id(
        self, tmp_path, mock_wcs_response, sample_bbox
    ):
        """Test że URL WCS zawiera COVERAGEID=Orthoimagery_StandardResolution."""
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=mock_wcs_response)

        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "nested" / "area.tif"

        provider.download_bbox(sample_bbox, output_path)

        call_url = session.get.call_args[0][0]
        assert "Orthoimagery_StandardResolution" in call_url
        assert output_path.exists()

    def test_download_bbox_invalid_crs(self, tmp_path):
        """Test błędu dla bbox z nieprawidłowym CRS (nie EPSG:2180)."""
        provider = GugikOrtoProvider()
        output_path = tmp_path / "area.tif"

        wrong_crs_bbox = BBox(
            min_x=18.0, min_y=52.0, max_x=19.0, max_y=53.0, crs="EPSG:4326"
        )

        with pytest.raises(ValueError, match="EPSG:2180"):
            provider.download_bbox(wrong_crs_bbox, output_path)

    def test_download_bbox_invalid_format(self, tmp_path, sample_bbox):
        """Test błędu dla nieobsługiwanego formatu WCS."""
        provider = GugikOrtoProvider()
        output_path = tmp_path / "area.xyz"

        with pytest.raises(ValueError, match="Unsupported WCS format"):
            provider.download_bbox(sample_bbox, output_path, format="InvalidFormat")


class TestGugikOrtoProviderRetry:
    """Testy retry i obsługi błędów pobierania pliku."""

    @staticmethod
    def failing_response() -> Mock:
        response = Mock(spec=requests.Response)
        response.raise_for_status.side_effect = requests.RequestException("Error")
        return response

    def test_download_retry_on_failure(self, tmp_path):
        """Test ponawiania próby po błędzie — 1. nieudana, 2. udana."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                gfi_response(sample("orto_2024.html")),
                self.failing_response(),
                file_response(),
            ]
        )
        provider = GugikOrtoProvider(session=session)
        output_path = tmp_path / "test.tif"

        with patch("time.sleep"):
            result = provider.download(GODLO, output_path)

        assert result == output_path
        assert session.get.call_count == 3

    def test_download_retry_exhausted(self, tmp_path):
        """Test błędu DownloadError po wyczerpaniu wszystkich prób."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[gfi_response(sample("orto_2024.html"))]
            + [self.failing_response()] * 3
        )
        provider = GugikOrtoProvider(session=session)

        with patch("time.sleep"), pytest.raises(DownloadError):
            provider.download(GODLO, tmp_path / "test.tif")

    def test_download_exponential_backoff(self, tmp_path):
        """Test exponential backoff — czasy oczekiwania [2, 4] sekund."""
        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[gfi_response(sample("orto_2024.html"))]
            + [self.failing_response()] * 3
        )
        provider = GugikOrtoProvider(session=session)

        sleep_times = []
        with (
            patch("time.sleep", side_effect=lambda t: sleep_times.append(t)),
            pytest.raises(DownloadError),
        ):
            provider.download(GODLO, tmp_path / "test.tif")

        # Exponential backoff: 2^1=2, 2^2=4 seconds
        assert sleep_times == [2, 4]


class TestGugikOrtoProviderInfo:
    """Testy metod informacyjnych."""

    def test_supported_formats(self):
        """Test listy obsługiwanych formatów WCS."""
        provider = GugikOrtoProvider()
        formats = provider.get_supported_formats()

        assert formats == ["GTiff", "PNG", "JPEG"]

    def test_validate_valid_godlo(self):
        """Test walidacji poprawnego godła — zwraca True."""
        provider = GugikOrtoProvider()

        assert provider.validate_godlo("N-34-130-D") is True
        assert provider.validate_godlo("N-34-130-D-d-2-4") is True
        assert provider.validate_godlo("M-33-A") is True

    def test_validate_invalid_godlo(self):
        """Test walidacji niepoprawnego godła — zwraca False."""
        provider = GugikOrtoProvider()

        assert provider.validate_godlo("INVALID") is False
        assert provider.validate_godlo("") is False
        assert provider.validate_godlo("123") is False
