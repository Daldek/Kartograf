# Research — klaster skorowidz GUGiK (K3, K4, S1, S4, H1, N1, N6)

Data: 2026-09-29. Faza: wylacznie research przyczyn i projekt naprawy (zero edycji
w `kartograf/`, `tests/`, `docs/` poza tym plikiem; zero zapytan sieciowych).
Decyzje wiazace: `decisions.md` (D4, D5, D6 dotycza tego klastra wprost).

Metoda: kod HEAD (`git status` czysty, `develop`), backlog `docs/PROGRESS.md:1033-1231`,
raporty L1/L2/L3/L5 i probki surowe `docs/research/2026-09-29-live-e2e-i-audyt-docs/gfi/`
(22 odpowiedzi GetFeatureInfo, w repo) oraz lokalne, NIEsledzone przez git
(`.gitignore:71`) surowe body z `e2e-data/2026-09-29-live/` (L1 `logs/`, L2
`wms_samples/`, L5 `wms_probe/` — 31 body). Przyczyny K3, K4, H1 odtworzone
OFFLINE na prawdziwym `GugikProvider._get_opendata_url` z `Mock(spec=requests.Session)`
karmionym surowymi body (sekcja 2).

Uzgodnienie z klastrem orto-laz (`ResearchOrtoLaz2`, K5): wspolny modul
`kartograf/providers/pl/skorowidz.py`, ktorego WLASCICIELEM jest ten klaster; orto
tylko go konsumuje (sekcja 3.1 — nazwy identyczne w `research-orto-laz.md`).

---

## 1. Fakty o skorowidzu GUGiK potwierdzone na surowych odpowiedziach

Struktura odpowiedzi GetFeatureInfo (`INFO_FORMAT=text/html`, HTTP 200) jest szablonem
HTML MapServera z tablica JS; rekordy to wywolania `push({...})` (jeden rekord = jedno
`push`), pola jako pary `klucz:"wartosc"`:

| Produkt | Deklaracja tablicy (obecna TAKZE w pustej odpowiedzi) | Rekord |
|---|---|---|
| NMT (1 m, 5 m; KRON86/EVRF2007) i NMPT | `var skor_NMT_wg_akt = [];` | `skor_NMT_wg_akt.push({url:"...",godlo:"...", aktualnosc:"YYYY-MM-DD", format:"ARC/INFO ASCII GRID", charakterystykaPrzestrzenna:"1.00 m", bladSredniWysokosci:"0.15", bladSredniPolozenia:"0.30", ukladWspolrzednychPoziomych:"PL-1992", ukladWspolrzednychPionowych:"PL-EVRF2007-NH", calyArkuszWypelnionyTrescia:"TAK", modulArchiwizacji:"1:5000", numerZgloszeniaPracy:"GI-FOTO.6202.10.2022", aktualnoscRok:"2022", zrDanych:"Skaning laserowy", dt_pzgik:"2022-12-16"})` (NMPT: bez `zrDanych` — L1 `03_nmt_nmpt_entries`) |
| Orto | `var skorDo5cm = [];` | `skorDo5cm.push({url:"...tif",godlo:"...", aktualnosc:"2024-06-21", wielkoscPiksela:"0.25", ukladWspolrzednych:"PL-1992", calyArkuszWyeplnionyTrescia:"TAK" (literowka GUGiK), modulArchiwizacji:"1:5000", rozmiarPlikuMB:"41", zrodloDanych:"Zdj. cyfrowe", kolor:"RGB", numerZgloszeniaPracy:"...", aktualnoscRok:"2024", dt_pzgik:"2025-04-14"})` (L1 `01_orto_2024_featureinfo.html`) |

Fakty istotne dla projektu (kazdy z probka):

1. **Wartosci pol.** `charakterystykaPrzestrzenna` ∈ {`"0.50 m"`, `"1.00 m"`, `"5.00 m"`}
   (92 rekordy probki kraju L2 `sample_country_1m.json`: 79 x 1.00, 13 x 0.50; 5 m
   w `gfi/05`, L5); `ukladWspolrzednychPoziomych` ∈ {`"PL-1992"`, `"PL-2000:S5"`..`"PL-2000:S8"`}
   (80 + 1 + 8 + 2 + 1); `ukladWspolrzednychPionowych` ∈ {`"PL-EVRF2007-NH"`, `"PL-KRON86-NH"`};
   `aktualnosc` zawsze ISO `YYYY-MM-DD`; `calyArkuszWypelnionyTrescia` ∈ {`TAK`, `NIE`}
   (`NIE` dla plikow 0,5 m Szczecina: L2 `logs/szczecin_c24_records.txt`).
2. **Jedno zapytanie punktowe zwraca rekordy ROZNYCH godel** — kazdy arkusz zawierajacy
   punkt, w obu ukladach: dla punktu w `N-34-139-A-c-1-1` (Warszawa) warstwa
   `SkorowidzeNMT2023iStarsze` oddaje `N-34-139-A-c-1-1` (2019, 2023), `7.173.21.06`
   (PL-2000:S7, 1,00 m) i `7.173.21.06.3` (PL-2000:S7, 0,50 m — arkusz POTOMNY 1:1000
   arkusza `7.173.21.06`). Stad podciag `"7.173.21.06" in url` trafia w potomka
   (K4/BUG-L2-3).
3. **Wewnatrz warstwy rekordy ida ROSNACO po dacie** (JS strony sortuje dopiero do
   wyswietlenia; `compare()` w szablonie): `2023iStarsze` dla Warszawy: 2019-04-18,
   2021-04-28, 2022-05-09, 2023-09-05. Stad "pierwszy URL z godlem" = NAJSTARSZA kampania.
4. **Warstwa = rok aktualnosci (partycja).** Sprawdzone offline na 92 rekordach probki
   kraju (12 lokalizacji, 1 m EVRF2007 + KRON86): 0 naruszen reguly
   `aktualnoscRok == rok warstwy` (dla `<rok>iStarsze`: `<= rok`). Warstwa nowsza zawiera
   wiec zawsze nowsze rekordy niz kazda starsza (podstawa optymalizacji w 3.2).
5. **Pusta odpowiedz** (morze, DE, CZ): ten sam szablon HTML, `var skor_NMT_wg_akt = [];`,
   ZERO `push(` (`gfi/01-04, 06-09, 17-20`), bez znacznikow OGC. Zla nazwa warstwy: HTTP
   200 `text/xml` `<ServiceException code="LayerNotDefined">` (`gfi/14-16, 21`).
6. **H1 POTWIERDZONE.** Rekordy z rozszerzeniem `.ASC` wielkimi literami istnieja
   (`76969_1298029_N-33-126-C-c-3-2.ASC`, `76969_1298032_N-33-126-C-c-4-2.ASC`;
   `charakterystykaPrzestrzenna:"5.00 m"`, `aktualnosc:"2022-07-24"`, warstwa
   `SkorowidzeNMT2022iStarsze` endpointu 5 m; body: `e2e-data/.../L5-pogranicze-de/wms_probe/slubice_c32_center_SkorowidzeNMT2022iStarsze.html`).
7. **GetCapabilities dzis:** NMT 1 m EVRF2007 `2026, 2025, 2024, 2023iStarsze`; NMT 5 m
   `2025, 2024, 2023, 2022iStarsze` (`gfi/index.json` `caps`); NMPT EVRF2007
   `SkorowidzeNMPT2026, 2025, 2024, 2023iStarsze` (L1 BUG-L1-9; nazwy w logach L1);
   orto `SkorowidzeOrtofotomapy2026, 2025, 2024, Starsze`.
8. **Godla PL-2000 w skorowidzu** wystepuja jako moduly 1:5000 (`7.124.7.4`), 1:2000
   (`5.167.25.17`, `7.173.21.06`, `6.177.11.05`) i 1:1000 (`6.220.25.05.1`,
   `8.152.08.23.4`, `7.173.21.06.3`); w 92 rekordach probki NIE ma zadnego godla
   PL-2000 w skali 1:10000 (`5.167.25`). W probce nie ma tez zadnego rekordu PL-2000 o
   rozdzielczosci 5 m. `SheetParser` daje dla nich `uklad="2000"` i skale
   `1:5000`/`1:2000`/`1:1000`, normalizacja tokenu zachowuje zapis GUGiK
   (`SheetParser("6.220.25.05.1").godlo == "6.220.25.05.1"`; PL-1992: wielkosc liter
   normalizowana, `n-34-130-d-d-2-4` -> `N-34-130-D-d-2-4`).

---

## 2. Bledy — przyczyna potwierdzona na kodzie i projekt naprawy

### 2.1 K3 — zerwane zapytanie nowszej warstwy = po cichu starsza kampania

**Przyczyna (potwierdzona).** `kartograf/providers/pl/gugik.py:571-647`: petla po
warstwach od najnowszej; kazda warstwa to jedno `session.get(url, timeout=timeout)`
(`:594`) BEZ ponowien; awaria idzie do `except requests.RequestException` ->
`transport_errors += 1; last_error = e; continue` (`:643-647`), a raport OGC
z HTTP 200 -> `transport_errors += 1 ... continue` (`:633-641`). Pierwszy URL z
kolejnej (starszej) warstwy KONCZY funkcje `return found_url` (`:604-610`) bez
sprawdzenia `transport_errors`; licznik dziala tylko, gdy ZADNA warstwa nie dala URL-a
(`:649-666`). Repro offline (sesja-atrapa: `L2025` -> `ConnectionError`, `L2024` ->
body `gfi/05` z rekordem 2025-05-20): zwrocony URL `.../83885_1835900_N-33-48-C-a-3-4.asc`,
jedyny slad `WARNING ... WMS query failed for layer L2025: RemoteDisconnected`. Skutek
utrwala `_cache_url` (`:609`, `:676-685`, TTL 7 dni) i `skip_existing` managera
(`download/manager.py:516-517`, `:329-331`). Sidecar arkusza nie niesie URL-a ani daty:
`manager.py:520` `self._write_sidecar(path, {"godlo": descendant_godlo})` -> `:852-870`
buduje `extra` wylacznie z `self._sidecar_extra`; `provider.download()` zwraca sam `Path`
(`providers/base.py:73-102`), wiec rekord skorowidza NIE ma dzis drogi do sidecara.
Hipoteza backlogu potwierdzona w calosci.

**Naprawa (D5 + K3).**
- Zapytanie warstwy z ponowieniami (3 proby, backoff 1/2/4 s, jak `_download_with_retry`
  `gugik.py:862-883`) na sesji keep-alive (S1, 2.3). Po wyczerpaniu prob albo przy
  raporcie OGC (bez ponowien — odpowiedz deterministyczna) = `DownloadError`
  natychmiast, KONIEC `continue`. Nie ma juz stanu "czesc warstw padla": kazda porazka
  warstwy przerywa rozwiazywanie arkusza (`transport_errors`, `last_error`, dwa
  komunikaty `:649-666` znikaja; zostaje jeden `DownloadError` "warstwa X: ... po 3
  probach" z godlem — dzis komunikat `WMS query failed for layer` nie ma godla, L2 m1).
- `NoCoverageError` tylko, gdy WSZYSTKIE warstwy odpowiedzialy szablonem bez pasujacego
  rekordu (jak dzis `:668`, ale przez selekcje z 2.2).
- Sidecar: `BaseProvider.source_info(godlo) -> dict | None` (nieabstrakcyjna, domyslnie
  `None`; `providers/base.py`), `GugikProvider` trzyma wybrane rekordy w
  `self._sources: dict[str, dict]` pod `threading.Lock` (klucz godlo — NIE "ostatni",
  bo `DownloadManager` pobiera w puli watkow na JEDNYM providerze:
  `manager.py:492-529`). `DownloadManager._write_sidecar(path, request, source)` wola po
  `provider.download()` `provider.source_info(godlo)` i wpisuje `extra["source"]` tylko,
  gdy `isinstance(source, dict)` (wzorzec jak `descriptor_key` przy `Mock`, `:858-860`).
  Zawartosc `extra.source` (klucze snake_case, addytywnie do `kartograf-meta/1`):
  `url`, `skorowidz` (endpoint WMS), `layer`, `godlo` (z rekordu), `aktualnosc`,
  `aktualnosc_rok`, `dt_pzgik`, `resolution_m` (float), `uklad` (surowe `PL-1992` /
  `PL-2000:S7`), `full_sheet` (bool), `numer_zgloszenia`, `zrodlo_danych` (None dla
  NMPT). Wycinek: `write_pl_cutout_sidecar` dostaje `extra.sheet_sources` — lista
  `{godlo, url, layer, aktualnosc}` czytana best-effort z sidecarow arkuszy mozaiki
  (`<arkusz>.asc.meta.json` -> `extra.source`; `null` dla arkuszy bez sidecara, np.
  z cache sprzed 0.7.0) — pytanie P5.
- Cache (N6, 2.7): zapis WYLACZNIE po komplecie odpowiedzi (przy nowej petli to
  automatyczne — do selekcji dochodzi tylko przebieg bez bledu).

**Testy offline.** `tests/test_gugik_provider.py::TestGugikProviderGetOpendataUrl`:
- failing-before/passing-after: sesja-atrapa `[ConnectionError, ConnectionError,
  ConnectionError, body-z-rekordem]` przy warstwach `["L2025","L2024"]` ->
  `pytest.raises(DownloadError)` NIE `NoCoverageError`, komunikat z godlem i nazwa
  warstwy; `session.get.call_count == 3` (3 proby L2025, L2024 nieodpytana);
  `time.sleep` spatchowany.
- `[ConnectionError, body-z-rekordem]` -> URL z L2025 (ponowienie zadzialalo), 2 wywolania.
- raport OGC (`_OGC_EXCEPTION_REPORT` juz w tescie `:477-482`) -> `DownloadError` po 1 probie.
- Do USUNIECIA/ZMIANY (pinuja `continue`): `test_get_opendata_url_partial_transport_error_is_not_no_coverage`
  (`:549-572`, asercja `"niepewny"`), `test_ogc_exception_on_one_layer_is_uncertain_not_no_coverage`
  (`:605-627`), `test_get_opendata_url_all_layers_transport_error_reports_service_failure`
  (`:530-547`, asercja `"all 3 layer queries failed"`, `call_count == 3` — po zmianie
  pierwsza warstwa po 3 probach konczy), `test_ogc_exception_report_on_all_layers_is_service_failure`
  (`:574-603`, `call_count == 3`, `"L3" in message`). Semantyka "brak pokrycia niepewny"
  znika z kodu i z ADR-020/ADR-027 (R5) — zastepuje ja "kazda porazka warstwy = blad".
- `tests/test_download_manager.py::TestSidecarWritten`: nowy test — provider-atrapa z
  `source_info()` zwracajacym dict -> `extra.source` w JSON; `Mock(spec=GugikProvider)`
  (zwraca `Mock`) -> brak klucza `source`.

### 2.2 K4 — wybor pliku: podciag, kolejnosc HTML, fallback PL-2000 <-> PL-1992

**Przyczyna (potwierdzona, wszystkie trzy objawy).** `gugik.py:599-602` regex
`url:"(https://opendata[^"]+\.asc)"` czyta WYLACZNIE URL-e — pola
`charakterystykaPrzestrzenna`, `aktualnosc`, `ukladWspolrzednychPoziomych`, `godlo`
sa w odpowiedzi (sekcja 1) i nie sa czytane. `:606-610` `if godlo in found_url`
(podciag) zwraca PIERWSZY URL w kolejnosci HTML (rosnaco po dacie, fakt 3) -> plik
0,5 m przed 1 m (Szczecin: `84007_..._N-33-90-C-c-2-4.asc` 0,50 m `NIE` przed
`80225_...` 1,00 m `TAK`), w warstwie zbiorczej najstarsza kampania, a dla godla
`5.167.25` potomek `5.167.25.13` (repro offline: body z rekordem `godlo:"5.167.25.13"`
-> zwrocony `.../72980_1_5.167.25.13.asc`). `:612-622` fallback `return urls[0]` dla URL
bez godla -> arkusz PL-1992 pod godlem PL-2000 (repro offline: godlo `7.124.7.4`,
body `gfi/05` -> zwrocony `..._N-33-48-C-a-3-4.asc` z `logger.warning`
"skorowidz zwrocil URL innego arkusza"). Orto: identyczny wzorzec
`gugik_orto.py:373-384` (fallback na poziomie DEBUG) — klaster orto-laz. Wycinek
nie ma strazy rozdzielczosci arkusza (`_reject_pl2000_sheets` `cutout.py:287-312`
sprawdza tylko `bounds.left >= 1e6`), stad "1m" w 0,5 m albo 100 % nodata z kodem 0
(BUG-L2-2 repro 1-2) i `niezgodne rozdzielczosci wejsc` (repro 3).

**Naprawa (D4) — regula deterministyczna** (implementacja w `skorowidz.py`, 3.1):
1. `parse_skorowidz_records(text, layer)` -> lista `SkorowidzRecord` (regex
   `\.push\(\{(.*?)\}\)` z `re.S` + pary `(\w+):"([^"]*)"`); URL brany z pola `url` BEZ
   filtra rozszerzenia (H1, 2.5).
2. `select_sheet_record(records, *, godlo, uklad, zone, resolution_m, predicate)`:
   filtr TWARDY — `rec.godlo == SheetParser(godlo).godlo` (caly token, po normalizacji
   obu stron przez `SheetParser`; rekord z godlem nieparsowalnym odpada), `rec.uklad ==
   parser.uklad` (`"1992"`/`"2000"` z `ukladWspolrzednychPoziomych`; dla PL-2000 takze
   `rec.zone == int(godlo.split(".")[0])`), `abs(rec.resolution_m - resolution_m) < 1e-6`
   (`"1.00 m"` -> 1.0; NMT 1m: 1.0, NMT 5m: 5.0, NMPT: 1.0; orto: `resolution_m=None`
   = bez filtra, predykat `kolor == "RGB"`); rekord BEZ pola rozdzielczosci albo ukladu
   = odrzucony + `logger.warning` (P6). Z pozostalych max po kluczu
   `(aktualnosc, dt_pzgik, url)` — deterministyczny remis.
3. Brak pasujacego rekordu we WSZYSTKICH warstwach = `NoCoverageError` (nodata w
   wycinku / pominiecie w liscie po D2). KONIEC fallbacku `urls[0]` i podciagu.
   Komunikat `NoCoverageError` dostaje podpowiedz, gdy odrzucone rekordy tego punktu
   maja: (a) ta sama rozdzielczosc w innym ukladzie ("skorowidz ma ten obszar tylko w
   PL-2000: 7.124.7.4 (1:5000) — uzyj godla PL-2000 / `--system 2000 --scale 1:5000`"),
   (b) godla potomne PL-2000 zadanego godla (`5.167.25.13`, `.17` -> "uzyj
   `--scale 1:2000`"), (c) inna rozdzielczosc (0,5 m: "GUGiK ma ten arkusz tylko w
   0,50 m — Kartograf pobiera dokladnie 1 m/5 m"). To sama tresc komunikatu, bez
   zmiany semantyki (P4).
4. `download/cutout.py:306-311`: `_reject_pl2000_sheets` ZOSTAJE jako straz plikow z
   cache pobranych przed naprawa (skorowidz juz nie wyda takiego pliku), a remedium
   "pobierz obszar jako arkusze ..., np. z --system 2000" zastepuje: "plik pochodzi z
   wczesniejszej wersji Kartografa (cichy fallback skorowidza, usuniety w 0.7.0) —
   usun go i ponow: <sciezki>". Docstring `:288-294` ("fallback URL w
   `_get_opendata_url`") do aktualizacji.
5. Kolejnosc warstw i wczesne zakonczenie: warstwy od najnowszej; pierwsza warstwa
   z pasujacym rekordem konczy (fakt 4: warstwa nowsza = nowsze rekordy), ale WEWNATRZ
   warstwy wygrywa max po `aktualnosc` (nie kolejnosc HTML). Nowsze warstwy musialy
   odpowiedziec — gwarantuje to 2.1. Alternatywa (wszystkie warstwy zawsze) — P2.

**Testy offline** (`tests/test_skorowidz.py` NOWY + `tests/fixtures/gugik_skorowidz/`):
- Fixture'y: `05_land5m_SkorowidzeNMT2025.body` (1 rekord 5 m), `01_sea5m_...body`
  (pusty szablon), `14_bogus5m_...body` (OGC `LayerNotDefined`) — kopie z `gfi/`;
  `slubice_c32_2022iStarsze.html` (jedyny rekord `.ASC`, kopia z `e2e-data/`, ktorego
  git NIE sledzi — skopiowac do `tests/fixtures/` w fali wdrozeniowej);
  `szczecin_c24_2024.body` — szablon z `gfi/05` z DWOMA `push(...)` o polach 1:1 z
  `L2 logs/szczecin_c24_records.txt` (0,50 m `NIE` 2024-08-28 przed 1,00 m `TAK`
  2024-09-03); `warszawa_2023iStarsze.body` — 4 rekordy z fakt 2 (2019, 2023 dla
  `N-34-139-A-c-1-1` + `7.173.21.06` + `7.173.21.06.3`); `orto_2024.html` (CIR+RGB,
  z L1 `01_orto_2024_featureinfo.html`, dla klastra orto). Pomocnik
  `render_gfi_body(records: list[dict], var="skor_NMT_wg_akt")` w
  `tests/conftest.py` — szablon `var X = [];` + `X.push({...});` — do testow
  providera/managera (dzisiejsze atrapy `{url:"..."}` bez `push(` i pol przestana
  parsowac: `test_gugik_provider.py:169-172, :381-382, :408-409, :430-431, :489-493`,
  `test_gugik_nmpt.py:174-177`, `test_metadata_cache.py:373-381, :483, :521, :536`,
  `test_wms_layer_validation.py:435-439` — wszystkie do przepisania na pomocnik).
- Failing-before/passing-after na prawdziwym providerze: Szczecin -> URL `80225_...`
  (1 m) nie `84007_...`; Warszawa `2023iStarsze` -> `78047_1404533` (2023-09-05), nie
  `73021_914857` (2019); godlo `5.167.25` z rekordem `5.167.25.13` -> `NoCoverageError`
  z podpowiedzia `--scale 1:2000`; godlo `7.124.7.4` z rekordem PL-1992 ->
  `NoCoverageError` (bez `logger.warning` "innego arkusza"); NMT 1m z rekordem
  `charakterystykaPrzestrzenna:"5.00 m"` -> `NoCoverageError`; remis dat -> `dt_pzgik`.
- Do USUNIECIA: `test_fallback_url_of_other_sheet_warns` (`test_gugik_provider.py:670-688`
  pinuje fallback); `test_pl_cutout.py:552-563` i `:783-784` zostaja (asercja tylko
  `"PL-2000"` w komunikacie), ale tresc remedium zmienic razem z komunikatem.

### 2.3 S1 — GetFeatureInfo/GetCapabilities bez ponowien i bez wspolnej sesji

**Przyczyna (potwierdzona).** `gugik.py:541` `session = self._session or requests.Session()`
— bez wstrzyknietej sesji (CLI: `cli/download_cmd.py:60-98` nie podaje sesji;
`create_nmt_provider` `providers/pl/__init__.py:26-47` przekazuje `session=None`)
kazde wywolanie `_get_opendata_url` (= kazdy arkusz) otwiera NOWA sesje = nowe
polaczenie TCP/TLS; `:594` jedno `session.get` bez ponowien; `_make_request` `:900`
znow nowa sesja per pobranie pliku (docstring `:894-898` przedstawia to jako
"thread-safety"); `_fetch_wms_layers` `:300` nowa sesja bez ponowien (komentarz
`:298-299`: "to avoid interfering with the main session's mock side_effects in tests"
— nieaktualny od fixture `_offline_wms_layers` w `tests/conftest.py:125-174`, ktora
patchuje `_fetch_wms_layers` w calosci). Nigdzie w `kartograf/` nie ma `HTTPAdapter`
ani `urllib3.Retry` (grep). Dowod roznicowy L3 B1: ta sama biblioteka na jednej sesji
keep-alive: 72/72 zapytan bez bledu w minutach, w ktorych CLI mialo 0-30 % zerwan
(prawie zawsze na PIERWSZYM zapytaniu nowej sesji).

**Naprawa.**
- `kartograf/transport/http.py`: `make_gugik_session() -> requests.Session`
  (`HTTPAdapter(pool_connections=4, pool_maxsize=8)`, naglowek `User-Agent:
  kartograf/<ver>`; BEZ `urllib3.Retry` — P9) i `get_with_retry(session, url, *,
  timeout, retries=3, description) -> requests.Response` (ten sam wzorzec co
  `download_to` `:42-62`: `RequestException` -> backoff `RETRY_BACKOFF_BASE**attempt`,
  po wyczerpaniu `DownloadError`; `raise_for_status` w srodku, wiec 5xx tez sie ponawia).
- `GugikProvider.__init__(session=None)`: wstrzyknieta sesja uzywana jak dotad
  (odpowiedzialnosc wolajacego — Hydrograf wstrzykuje wlasna, `hydrograf-uwagi-migracyjne.md:89`);
  bez niej `self._local = threading.local()` i `_session_for_thread()` tworzy JEDNA
  sesje na watek roboczy (`threading.local`), wspolna dla GetCapabilities,
  GetFeatureInfo i pobran (`_make_request`, `_fetch_wms_layers` przechodza na nia —
  koniec `requests.Session()` w `:300`, `:541`, `:900`). Uzasadnienie: `requests.Session`
  nie jest oficjalnie thread-safe (mutowalny cookie jar/naglowki; pule urllib3 sa),
  a `DownloadManager` dzieli JEDEN provider miedzy `max_workers` watkow
  (`manager.py:492-529`, ADR-018) — sesja per watek daje keep-alive (4 polaczenia
  zamiast N arkuszy x (warstwy + plik)) bez wspoldzielenia stanu. Wycinek L3 Hel:
  25 arkuszy x do 4 warstw + 11 plikow = ~110 polaczen -> 2 (workers 2).
- GetFeatureInfo: `get_with_retry(..., retries=3)`; raport OGC w odpowiedzi = blad bez
  ponowien (2.1). GetCapabilities: `get_with_retry(..., timeout=10, retries=3)`.
- `DownloadManager` NIE wstrzykuje sesji (nie ma jej dzis: `manager.py:211-213`) —
  sesja jest wewnetrzna providera; zero zmian w managerze poza sidecarem (2.1).

**Testy offline.** `tests/test_transport_http.py`: `get_with_retry` — `[ConnectionError,
resp]` -> resp + 1 `sleep`; `HTTPError` z `raise_for_status` x3 -> `DownloadError`;
`make_gugik_session` — adapter zamontowany dla `https://`, naglowek UA.
`tests/test_gugik_provider.py::TestGugikProviderSession`: bez `session=` dwa wywolania
w jednym watku uzywaja TEJ SAMEJ sesji (patch `kartograf.providers.pl.gugik.make_gugik_session`,
`call_count == 1`), dwa watki -> dwie sesje; wstrzyknieta sesja nadal uzywana do
GetCapabilities (pada dzisiejsze zalozenie testow `test_wms_layer_validation.py:117-118,
:150-154` patchujacych `requests.Session` — przepisac na sesje wstrzyknieta).

### 2.4 S4 — lista warstw NMPT EVRF2007 nieaktualna; fallback na zaszyta liste

**Przyczyna (potwierdzona).** `gugik_nmpt.py:82-87` `"EVRF2007": ["SkorowidzeNMPT2025",
"SkorowidzeNMPT2024", "SkorowidzeNMPT2023", "SkorowidzeNMPT2022iStarsze"]` wobec
GetCapabilities `2026, 2025, 2024, 2023iStarsze` (fakt 7). Mechanizm ADR-020
`gugik.py:338-396`: `_get_validated_layers` porownuje zbiory (`:377`) i przy
rozbieznosci ostrzega (`:378-383`, kazde pobranie NMPT) i uzywa odkrytych; przy
`RequestException/ValueError/ParseError` GetCapabilities (`:390-396`) — `logger.warning`
+ zaszyta lista, bez ponowien (`:306` jedno `session.get`). Z zaszyta lista NMPT dwie
warstwy daja `LayerNotDefined` (HTTP 200) -> dzis `transport_errors` (`:633-641`)
-> "brak pokrycia niepewny" dla arkusza tylko w 2026/2023iStarsze lub bez danych,
a arkusz z edycja 2026 i 2024 dostaje po cichu 2024 (L1 `B1b_nmpt_hardcoded_layers.log`,
symulacja z korekty KNOWN-BUGS). Wynik in-memory `_validated_layers` (`:242`) bez
locka: w puli watkow N watkow rownolegle wola GetCapabilities przy pierwszym arkuszu.

**Naprawa (decyzja: awaria GetCapabilities = blad, nie zaszyta lista).**
- Usunac `WMS_LAYERS` z `GugikProvider` (`gugik.py:125-153`) i `GugikNmptProvider`
  (`:74-89`); w ich miejsce wzorzec nazw warstw per produkt:
  `LAYER_PATTERN = re.compile(r"^SkorowidzeNMT\d{4}(iStarsze)?$")` (NMT),
  `r"^SkorowidzeNMPT\d{4}(iStarsze)?$"` (NMPT); orto (klaster orto-laz):
  `r"^SkorowidzeOrtofotomapy(\d{4}|Starsze)$"`. `_fetch_wms_layers` filtruje po wzorcu
  (dzis `startswith("Skorowidze")` `:318`), sortuje jak dzis (`:325-334`, rok malejaco,
  `iStarsze` na koncu), pusta lista = `DownloadError` "endpoint X nie publikuje warstw
  Skorowidze*" (dzis `ValueError` `:321`).
- `_get_validated_layers(resolution, vertical_crs)` -> `_layers(endpoint)`: pod
  `threading.Lock` (jeden GetCapabilities na endpoint i instancje; reszta watkow czeka),
  `get_with_retry(timeout=10, retries=3)`; sukces memoizowany jak dzis; porazka ->
  `DownloadError("GUGiK WMS GetCapabilities <endpoint> niedostepny po 3 probach: ...")`
  — bez memoizacji porazki (kolejny arkusz sprobuje ponownie; w wycinku pierwszy taki
  blad i tak konczy zadanie kodem 1 — R5; w liscie po D2 kazdy arkusz zglosi porazke) — P10.
  Znika `logger.warning` "different layers than hardcoded" (kazde pobranie NMPT) i
  "Using hardcoded WMS_LAYERS as fallback".
- Odkryta lista NIE trafia do SQLite (jedno zapytanie na proces; P3).

**Testy offline.** `tests/conftest.py::_nmt_endpoint_layers` (`:97-122`) buduje stub z
`WMS_LAYERS` -> zastapic jawna tabela `_STUB_LAYERS = {endpoint: [...]}` (te same
listy, przeniesione z kodu do testow; NMPT EVRF2007 = `2026..2023iStarsze` wg fakt 7).
`tests/test_wms_layer_validation.py`: usunac `TestHardcodedLayerNames` (`:240-300`,
straz zaszytych list), `test_returns_hardcoded_on_match`, `test_falls_back_on_network_error`,
`test_falls_back_on_valueerror` (`:332-380`); dodac: GetCapabilities `ConnectionError`
x3 -> `DownloadError` (a `_get_opendata_url` nie wykonuje zadnego GetFeatureInfo);
`[ConnectionError, xml]` -> lista OK; filtr wzorca odrzuca `ZasiegiNMT2025`; NMPT
wzorzec nie przyjmuje `SkorowidzeNMT2025`; lock: 4 watki -> 1 wywolanie `_fetch_wms_layers`.
`tests/test_gugik_nmpt.py:127-131, :153-158` (iteruja `WMS_LAYERS`) — usunac.
Dokumentacja: ADR-020 errata ("fallback na zaszyte warstwy usuniety; zaden zaszyty
rocznik w kodzie").

### 2.5 H1 — regex pomija `.ASC`

**Hipoteza POTWIERDZONA na kodzie i probce.** `gugik.py:599-602`
`re.findall(r'url:"(https://opendata[^"]+\.asc)"', text)` (bez `re.I`) na
`slubice_c32_center_SkorowidzeNMT2022iStarsze.html` (jedyny rekord:
`..._N-33-126-C-c-3-2.ASC`, 5,00 m, PL-1992, 2022-07-24) zwraca `[]`; repro offline na
prawdziwym providerze (warstwy `[pusty, pusty, pusty, body-.ASC]`) konczy sie
`NoCoverageError: No NMT 5m data available for N-33-126-C-c-3-2` — w wycinku
`--target-crs` bylaby to cicha dziura nodata + `missing_sheets`, w liscie (po D2)
pominiecie. Zasieg: rekordy kampanii 76969 (2022, endpoint 5 m, `2022iStarsze`);
w L5 kazdy taki arkusz mial nowszy rekord `.asc`, wiec objaw nie wystapil na zywo.

**Naprawa.** Parser rekordow (2.2) bierze URL z pola `url` bez filtra rozszerzenia
— rozszerzenie zrodla jest nieistotne, plik i tak laduje pod nazwa z `FileStorage`
(`<godlo>.asc`), a `read_asc_nodata` patrzy na sufiks pliku docelowego
(`sources/sidecar.py:104`). Straz: `url` musi zaczynac sie od `https://` (inaczej
rekord odrzucony z warningiem). Test: fixture `slubice_c32` -> URL `.ASC` zwrocony;
`parse_skorowidz_records` zachowuje wielkosc liter.

### 2.6 N1 — puste katalogi po arkuszach bez danych

**Przyczyna (potwierdzona).** `gugik.py:454-458`: `output_path.parent.mkdir(parents=True,
exist_ok=True)` PRZED `self._get_opendata_url(godlo, timeout)`; przy `NoCoverageError`
zostaje puste drzewo `M-33/44/C/d/2/1/` (L4: 18 drzew). To samo w `download_bbox`
`:777-778` (mkdir przed WCS) i w orto `gugik_orto.py:281-282`, LAZ `gugik_laz.py:536-537`
(klaster orto-laz). `prune_empty_dirs` (`download/storage.py:511`) sprzata tylko
`<segment>/bbox/` po nieudanej budowie (`cutout.py:633`, `download_cmd.py:1558,1562`).

**Naprawa.** Usunac `mkdir` z `download()` (`:455`) i `download_bbox()` (`:778`);
katalog tworzy `_save_response` (`:905-924`) tuz przed otwarciem pliku tymczasowego
— po rozwiazaniu URL-a i po udanym `_make_request`. Arkusz bez danych nie dotyka dysku.
Test: `test_gugik_provider.py` — `NoCoverageError` z `download()` -> `not
output_path.parent.exists()`; istniejacy `test_download_godlo_creates_directory`
(`:208`) zostaje (katalog powstaje przy sukcesie).

### 2.7 N6 — `MetadataCache` niepodlaczony w torach PL

**Przyczyna (potwierdzona).** `cli/download_cmd.py:60-98` `_create_provider_and_storage`
tworzy `GugikNmptProvider(vertical_crs=...)`, `GugikOrtoProvider()`,
`create_nmt_provider(vertical_crs, resolution)` — bez `cache=` (4 miejsca wywolania:
`:715`, `:987`, `:1109`, `:1782`); `download/manager.py:211-213` `create_nmt_provider(
vertical_crs=..., resolution=...)`; `download/cutout.py:572-574` i `:705`
`create_nmt_provider(vertical_crs=..., resolution=...)`. `MetadataCache()` w CLI
tworzy tylko tor CZ (`:1647`, `finally: cache.close()` `:1680`). Cache URL-i
(`cache/metadata.py:95-105` `url_cache`, `:134-234`) klucz `(godlo, resolution,
vertical_crs, product)` -> sam URL, TTL 7 dni; `set_url` wolany z `_cache_url`
(`gugik.py:609, 621`) takze dla URL-a z fallbacku i po cichej degradacji (K3) —
dlatego bez naprawy K3 podlaczenie cache UTRWALALOBY starsza kampanie na 7 dni.

**Naprawa (minimalna, zgodna z D6).**
- `MetadataCache`: tabela `record_cache(product, resolution, vertical_crs, godlo,
  payload TEXT, cached_at)` z `get_record(product, resolution, vertical_crs, godlo) ->
  dict | None` / `set_record(..., payload: dict)`; `url_cache` + `get_url/set_url`
  USUNIETE (cutover; `_create_tables` robi `DROP TABLE IF EXISTS url_cache` —
  jedyna migracja pliku `.kartograf_cache.db`), `stats()` `url_count` -> `record_count`
  (`cli/cache_cmd.py:40`), `clear`/`prune_expired` na nowej tabeli. Payload:
  `{"source": <extra.source>}` (sukces) albo `{"no_coverage": true}` (komplet
  odpowiedzi bez pasujacego rekordu — P3). Zapis tylko po pelnym, udanym przebiegu
  wszystkich zapytanych warstw (2.1) — cache nie moze zawierac wyniku
  "po awarii". Odczyt: trafienie `source` -> `_sources[godlo]` + URL (sidecar D5
  dziala takze z cache), trafienie `no_coverage` -> `NoCoverageError` bez sieci.
  GetCapabilities NIE jest cache'owane w SQLite (jedno zapytanie na proces).
- TTL: 7 dni (`DEFAULT_TTL_SECONDS`, bez zmian). `--force`: CLI przekazuje `cache=None`
  (rekordy nie sa czytane ani zapisywane — najprostsza, przewidywalna inwalidacja;
  P4), `kartograf cache clear` czysci wszystko jak dzis.
- CLI: `_create_provider_and_storage(product, output_dir, vertical_crs, resolution,
  cache=None)` przekazuje `cache` do trzech fabryk; `cmd_download` (galaz PL) tworzy
  `cache = None if args.force else MetadataCache()` i zamyka w `finally` (wzor CZ
  `:1647-1680`). Biblioteka: `DownloadManager(cache=...)`? NIE — provider jest
  parametrem; `download_pl_cutout(..., cache: MetadataCache | None = None)` przekazuje
  do `create_nmt_provider(cache=cache)` (`cutout.py:705`); `run_pl_cutout` bez zmian
  (provider wstrzykiwany). `DownloadManager` bez `provider=` (`manager.py:211`) — bez
  cache (jak dzis; Hydrograf wstrzykuje provider z cache — `hydrograf-uwagi-migracyjne.md:89-90`).

**Testy offline.** `tests/test_metadata_cache.py`: `TestMetadataCacheUrl*` (`:70-175`)
-> na `get_record/set_record` (JSON round-trip, TTL, klucze), `test_cache_hit_skips_wms`
(`:383-401`) z payloadem `{"source": {...}}` -> `session.get` nie wolany,
`provider.source_info(godlo)` == source; `{"no_coverage": true}` -> `NoCoverageError`
bez sieci; miss + komplet odpowiedzi -> `set_record` z `source`; miss + awaria warstwy
-> `DownloadError` i `get_record` nadal `None` (K3-safe, failing-before: dzis
`_cache_url` zapisuje URL starszej warstwy). `tests/test_cli.py`: `--force` ->
`_create_provider_and_storage` dostaje `cache=None`; bez `--force` -> `MetadataCache`
w `tmp_path` (monkeypatch cwd) i `close()` wolane. `tests/test_pl_cutout.py`:
`download_pl_cutout(cache=...)` przekazuje do fabryki (patch `create_nmt_provider`).

---

## 3. Wspolny projekt

### 3.1 `kartograf/providers/pl/skorowidz.py` (NOWY; wlasciciel: ten klaster; orto konsumuje)

```python
@dataclass(frozen=True)
class SkorowidzRecord:
    url: str
    godlo: str
    aktualnosc: str            # "YYYY-MM-DD"
    dt_pzgik: str | None
    layer: str
    uklad: str | None          # "1992" | "2000" (z "PL-1992" / "PL-2000:S7")
    zone: int | None           # 7 dla "PL-2000:S7"
    resolution_m: float | None # z charakterystykaPrzestrzenna "1.00 m" ALBO wielkoscPiksela "0.25"
    full_sheet: bool | None    # calyArkuszWypelnionyTrescia / calyArkuszWyeplnionyTrescia
    raw: dict[str, str]        # wszystkie pary rekordu (kolor, format, zrDanych, ...)
    def to_source(self, endpoint: str) -> dict: ...   # extra.source (2.1)

def parse_skorowidz_records(text: str, layer: str) -> list[SkorowidzRecord]
def select_sheet_record(records, *, godlo, uklad, zone=None, resolution_m=None,
                        predicate=None) -> SkorowidzRecord | None
def is_skorowidz_answer(text: str) -> bool     # szablon `var \w+ = [];` obecny (P7)
def query_skorowidz_layer(session, endpoint, layer, *, query_bbox, godlo, timeout,
                          retries=3) -> list[SkorowidzRecord]
    # get_with_retry; raport OGC -> DownloadError bez ponowien; brak szablonu -> DownloadError
class SourceInfoMixin:        # _remember_source(godlo, dict) pod Lock; source_info(godlo)
```

`GugikProvider` (dziedziczy NMPT) i `GugikOrtoProvider` uzywaja tych samych funkcji;
`GugikProvider._get_opendata_url(godlo, timeout) -> str` zostaje (testowany szeroko)
jako cienka nakladka na nowe `_resolve_sheet(godlo, timeout) -> SkorowidzRecord`
(cache -> warstwy -> petla -> selekcja -> `_remember_source` -> `set_record`);
`download()` wola `_resolve_sheet`.

### 3.2 Przeplyw `_resolve_sheet` (docelowy)

1. `parser = SheetParser(godlo)`; klucz cache `(product, resolution, vertical_crs, parser.godlo)`.
2. Cache: `source` -> zapamietaj, zwroc; `no_coverage` -> `NoCoverageError`.
3. `endpoint = WMS_SKOROWIDZE_ENDPOINTS[res][vcrs]` (brak = `DownloadError`, jak `:547-553`).
4. `layers = self._layers(endpoint)` — GetCapabilities z ponowieniami, lock, memo; blad = `DownloadError`.
5. Dla warstwy od najnowszej: `records = query_skorowidz_layer(...)` (kazda porazka =
   `DownloadError` z godlem i warstwa); `chosen = select_sheet_record(...)`; jest ->
   zapamietaj, `set_record({"source": ...})`, zwroc. Nie ma -> zbierz odrzucone rekordy
   do podpowiedzi i idz dalej.
6. Po wszystkich warstwach: `set_record({"no_coverage": true})`, `NoCoverageError`
   z podpowiedzia (2.2 pkt 3).

Koszt sieci per arkusz ladowy: bez zmian wobec dzis (pierwsza warstwa z rekordem
konczy); per arkusz bez danych: bez zmian (wszystkie warstwy). Zysk: keep-alive
i ponowienia (S1), cache miedzy przebiegami (N6).

### 3.3 Zmiany kontraktu (co widza wolajacy)

| Wolajacy | Dzis | Po naprawie |
|---|---|---|
| CLI godlo/lista/wycinek | godlo PL-2000 -> po cichu plik PL-1992 (kod 0); plik 0,5 m jako "1m"; po zerwaniu warstwy starsza kampania | `NoCoverageError` z podpowiedzia (wycinek: nodata + `Warning:`; lista: wg D2); dokladnie 1 m/5 m; zerwana warstwa po 3 probach = `Error:` kod 1 (wycinek) / porazka arkusza (lista, D2). Bez `--force` drugi przebieg nie pyta skorowidza (cache). Znika ostrzezenie GetCapabilities przy kazdym NMPT |
| `download_pl_cutout` / `run_pl_cutout` | j.w.; `missing_sheets` tez dla arkuszy, ktore GUGiK ma tylko w 0,5 m / PL-2000 | j.w.; nowy kwarg `download_pl_cutout(cache=)`; sidecar wycinka `extra.sheet_sources`; komunikat `_reject_pl2000_sheets` = "usun plik z cache" |
| `DownloadManager` / Hydrograf | sidecar arkusza `request={"godlo"}` bez URL-a | + `extra.source` (D5); `GugikProvider(session=, cache=)` bez zmian sygnatury; `MetadataCache.get_url/set_url` -> `get_record/set_record` (BREAKING dla bezposrednich uzytkownikow API cache, nie dla przekazujacych obiekt); `DownloadError` zamiast cichej degradacji przy awarii skorowidza (Hydrograf sesja 93, blad (1)) |
| `kartograf cache stats` | `URL entries` | `Record entries` (`record_count`) |
| Sidecar `.meta.json` | `extra: {parent_request?, missing_sheets?, ...}` | + `extra.source` (arkusz), `extra.sheet_sources` (wycinek); `schema` bez zmian (addytywne) |

---

## 4. Ryzyka i pozostale pytania projektowe (nierozstrzygniete przez D1-D6)

**P1. Arkusz niepelny (`calyArkuszWypelnionyTrescia: NIE`) a "najnowsza kampania".**
Nowszy rekord czesciowy (np. dorazne nalotowanie fragmentu) wygralby z pelnym starszym
i zostawil nodata tam, gdzie GUGiK MA dane (kloci sie z duchem R5). Opcje: (A) D4
doslownie — najnowszy bez wzgledu na `NIE`; (B) preferuj `TAK`: najnowszy pelny, a
czesciowy tylko, gdy zaden pelny nie pasuje (+ `logger.info`); (C) najnowszy + `Warning:`
przy `NIE`. **Rekomendacja: B** (w probkach `NIE` maja wylacznie pliki 0,5 m, wiec po
filtrze rozdzielczosci B == A w 100 % zaobserwowanych przypadkow; B chroni przed
przyszlym przypadkiem). Wymaga potwierdzenia uzytkownika, bo D4 mowi "najnowsza".

**P2. Wczesne zakonczenie na pierwszej warstwie z rekordem vs zawsze wszystkie warstwy.**
(A) wczesne zakonczenie — koszt jak dzis, opiera sie na partycji warstwa=rok (0/92
naruszen); (B) zawsze wszystkie — 2-4x wiecej zapytan na arkusz ladowy, odporne na
ewentualne zle zaszeregowanie rekordu przez GUGiK. **Rekomendacja: A**, z asercja
w kodzie (rekord z `aktualnoscRok` > rok warstwy nie-`iStarsze` -> warning), test
partycji na fixture.

**P3. Cache negatywny (`no_coverage`).** (A) tak, TTL 7 dni — morze/zagranica przestaje
kosztowac 4 zapytania na arkusz przy kazdym przebiegu (L3: "rada ponow pobranie
powtarza caly zestaw"); (B) nie — nowa kampania widoczna od razu; (C) tak, krotszy TTL
(1 dzien). **Rekomendacja: A** (`--force` i `cache clear` omijaja; nowe kampanie GUGiK
publikuje raz na miesiace).

**P4. `--force` a cache.** (A) `cache=None` (bez odczytu i zapisu; najprostsze);
(B) provider z flaga `refresh=True` (bez odczytu, z zapisem — kolejny przebieg bez
`--force` korzysta); (C) `MetadataCache.invalidate(product, ...)` przed pobraniem.
**Rekomendacja: A** (jedna linia w CLI, brak nowej flagi w providerze).

**P5. Zrodla w sidecarze wycinka.** (A) tylko `extra.missing_sheets` jak dzis (zrodla
w sidecarach arkuszy); (B) `extra.sheet_sources` z sidecarow arkuszy (best-effort,
`null` dla arkuszy bez sidecara); (C) pelne `extra.source` per arkusz (rozmiar). 
**Rekomendacja: B** — konsument (Hydrograf) widzi kampanie wycinka bez chodzenia po
katalogu arkuszy; koszt: 1 odczyt JSON na arkusz.

**P6. Rekord bez pola rozdzielczosci/ukladu.** (A) odrzuc + warning (scisle D4);
(B) przyjmij (ryzyko powrotu K4). **Rekomendacja: A**; wszystkie 20+ zaobserwowanych
rekordow NMT/NMPT (2011-2025) maja oba pola.

**P7. Straz pozytywna szablonu.** Dzis "brak URL i brak znacznikow OGC" = brak arkusza
(`:629-631` "straz tylko negatywna"). Propozycja: odpowiedz liczy sie jako "warstwa
odpowiedziala" tylko, gdy zawiera deklaracje `var \w+ = [];` (obecna w kazdej z 18
pustych/pelnych odpowiedzi NMT i w orto); inny HTML z 200 (np. strona bledu
proxy/MapServera bez OGC) = `DownloadError` (niepewne), nie nodata. **Rekomendacja:
tak** — zmiana szablonu przez GUGiK bedzie glosna (kod 1), nie cicha (100 % nodata).

**P8. Nazwa/rozdzial `_get_opendata_url`.** Zostawic jako nakladke na `_resolve_sheet`
(mniej zmian w ~30 testach) — rekomendacja; alternatywa: pelna zmiana nazwy w testach.

**P9. Ponowienia: `urllib3.Retry` na adapterze vs petla aplikacyjna.** Adapter: niewidoczny
dla testow z `Mock(spec=Session)`, nie obejmuje bledow po naglowkach ani `raise_for_status`
5xx, dubluje sie z petla plikow (`_download_with_retry` 3x). **Rekomendacja: wylacznie
petla aplikacyjna (`get_with_retry`)** — testowalna, jeden mechanizm, ta sama liczba
prob co pliki.

**P10. Memoizacja porazki GetCapabilities w instancji.** (A) nie memoizowac — kazdy
arkusz ponawia (N arkuszy x 3 proby zanim zadanie padnie: w wycinku `run_pl_cutout`
i tak konczy po pierwszej porazce fatalnej, ale pula dokancza biezace zadania);
(B) memoizowac na czas instancji (szybki fail dla reszty arkuszy, ale chwilowa awaria
w sekundzie 0 blokuje caly przebieg). **Rekomendacja: A + lock** (jeden GetCapabilities
naraz), bo D2/R5 i tak zamieniaja porazke w kod 1.

**Ryzyka.**
- Godla PL-2000 1:10000 (`5.167.25`; lista `--system 2000` bez `--scale`) beda po D4
  zwykle `NoCoverageError` (fakt 8: GUGiK publikuje PL-2000 jako moduly 1:5000/1:2000/
  1:1000) — to jest poprawne, ale zauwazalne (L1 C4: 4 pliki -> 0 plikow i kod 1 po D2);
  podpowiedz `--scale 1:2000` w komunikacie + CHANGELOG (BREAKING zachowania).
  Rozwijanie godla PL-2000 do potomkow z rekordami skorowidza = etap 2 (poza fala).
- Wiecej twardych bledow przy chwiejnym GUGiK (zerwana warstwa = `DownloadError` po
  3 probach zamiast cichej degradacji) — zamierzone (D5); ponowienia + keep-alive
  (L3: 72/72) maja to zrownowazyc; potwierdzic na zywo scenariuszami L3/L5.
- Usuniecie zaszytych warstw: praca offline bez GetCapabilities niemozliwa (dzis
  "dziala" z nieaktualna lista); testy Hydrografu z wlasna sesja musza podawac
  GetCapabilities (albo `provider._validated_layers[...]` jak testy Kartografa).
- Zmiana `MetadataCache` API i tabeli — bezposredni uzytkownicy `get_url` (poza repo)
  dostana `AttributeError`; w repo brak takich poza providerami i testami.
- Parser regexowy na JS: rekord z `"` w wartosci (np. w `numerZgloszeniaPracy`)
  urwalby pare — w 100+ zaobserwowanych rekordach brak cudzyslowow; straz P7 +
  `url` musi byc `https://`.

---

## 5. Szacunek zakresu

Pliki `kartograf/` dotkniete przez ten klaster (kolizje z innymi klastrami oznaczone):
- NOWY `kartograf/providers/pl/skorowidz.py` — parser, selekcja, petla warstw z retry, `SourceInfoMixin`.
- `kartograf/providers/pl/gugik.py` — `_resolve_sheet`, sesja per watek, `_layers` (lock, retry, bez `WMS_LAYERS`), `LAYER_PATTERN`, leniwy mkdir, `source_info`, cache rekordow; docstringi `:444-447`, `:501-514`, `:894-898`, komentarze `:298-299`, `:612-616`, `:624-632`.
- `kartograf/providers/pl/gugik_nmpt.py` — usuniecie `WMS_LAYERS` (`:74-89`), `LAYER_PATTERN`.
- `kartograf/providers/pl/gugik_orto.py` — KOLIZJA z klastrem orto-laz (K5): konsument `skorowidz.py`, ten sam wzorzec sesji/warstw/mkdir; wlasciciel edycji: orto-laz wg uzgodnionego API.
- `kartograf/providers/base.py` — `source_info()` (nieabstrakcyjna).
- `kartograf/transport/http.py` — `make_gugik_session`, `get_with_retry` (LAZ tez skorzysta — orto-laz).
- `kartograf/cache/metadata.py` — `record_cache`, `get_record/set_record`, drop `url_cache`, `stats`.
- `kartograf/cli/cache_cmd.py` — etykieta `record_count`.
- `kartograf/download/manager.py` — `_write_sidecar(..., source)` (`:519-520`, `:575-576`, `:335-336`, `:852-870`).
- `kartograf/download/cutout.py` — komunikat `_reject_pl2000_sheets` (`:287-312`), `download_pl_cutout(cache=)` (`:645-726`), `extra.sheet_sources` w `write_pl_cutout_sidecar`; KOLIZJA z klastrem CLI (S5/D3 w `cutout.py`/`mosaic.py`) — rozlaczne funkcje.
- `kartograf/cli/download_cmd.py` — `_create_provider_and_storage(cache=)` (`:60-98`), cykl zycia `MetadataCache` na galezi PL (`cmd_download` `:619+`); KOLIZJA z klastrem CLI (S2/S3 w tym samym pliku: `_download_godlo_list`, `_dispatch_area`) — rozlaczne funkcje, jeden integrator.
- `kartograf/providers/pl/__init__.py` — bez zmian sygnatury (`cache=` juz jest).
- Testy: `tests/conftest.py` (stub warstw, `render_gfi_body`), NOWE `tests/test_skorowidz.py` + `tests/fixtures/gugik_skorowidz/`, `tests/test_gugik_provider.py`, `tests/test_gugik_nmpt.py`, `tests/test_wms_layer_validation.py`, `tests/test_metadata_cache.py`, `tests/test_download_manager.py`, `tests/test_pl_cutout.py`, `tests/test_transport_http.py`, `tests/test_cli.py` (cache wiring).
- Dokumentacja: `docs/ARCHITECTURE.md` 4.2/4.3 (`:396-410`, `:604-625`), `docs/DECISIONS.md` errata ADR-019 (`:376-382`), ADR-020 (`:399`, `:405-419`), ADR-027 R5 ("brak pokrycia niepewny" znika), nowy ADR "wybor rekordu skorowidza + extra.source", `docs/CHANGELOG.md`, `CLAUDE.md` (sekcje o K3/K4/S1/S4/N1/N6, `download_pl_cutout`), `docs/PROGRESS.md` (tabela bledow), `docs/SCOPE.md` (PL-2000 1:10000).

Zmiana kontraktu publicznego: TAK — (1) `NoCoverageError` zamiast cichego pliku
PL-1992/0,5 m/potomka; (2) `DownloadError` zamiast cichej degradacji kampanii;
(3) `MetadataCache.get_url/set_url` -> `get_record/set_record` + `stats()["record_count"]`;
(4) `download_pl_cutout(cache=)`, `BaseProvider.source_info()`; (5) sidecar `extra.source`
/ `extra.sheet_sources` (addytywne); (6) brak zaszytych warstw — praca bez
GetCapabilities niemozliwa.
