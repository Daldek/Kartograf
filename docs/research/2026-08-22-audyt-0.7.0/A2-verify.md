# A2-verify — weryfikacja ustalen A2 (providery PL, download, cache)

Weryfikator: V2. Zakres: wszystkie ustalenia [Critical] i [Important] z `A2-report.md`
(A2-1..A2-9). [Minor] (A2-10..A2-16) pominiete zgodnie z VERIFY_FORMAT.md.

Srodowisko reprodukcji: `.venv/bin/python` = CPython 3.13.5 (build z GIL:
`sys._is_gil_enabled() == True`, `Py_GIL_DISABLED=0`), sqlite3 3.46.1,
`sqlite3.threadsafety == 3`. Wszystko offline, zero zapytan do sieci, zero zmian
w plikach repo (snippety w scratchpadzie).

### A2-1 — MetadataCache: nieblokowane odczyty na wspoldzielonym polaczeniu SQLite zwracaja URL innego arkusza
- Werdykt: CONFIRMED
- Reprodukcja: `v2_a2_1.py` — 300 wpisow `G0..G299`, 8 watkow x 2000 `get_url()`,
  ZERO zapisow rownolegle, jedna instancja `MetadataCache` w tmp. Trzy przebiegi:
  ```
  TOTAL=16000 OK=2004 ZLA_WARTOSC=9339 (w tym None=8184) wyjatki={'TypeError':1307,'InterfaceError':2369,'ValueError':978,'SystemError':2,'DatabaseError':1}
  przyklady zlych: [('G238','https://opendata/G124.asc'), ('G245','https://opendata/G253.asc'), ('G247','https://opendata/G18.asc')]
  TOTAL=16000 OK=2151 ZLA_WARTOSC=9177 ... | TOTAL=16000 OK=2303 ZLA_WARTOSC=9000 ...
  ```
  Kontrola naprawy (`v2_a2_1b.py`, odczyt pod `with c._write_lock:`): `OK=16000 ZLE=0 wyjatki={}`.
  Niski wolumen, 4 watki (odpowiednik CLI `--workers 4`) x 5 odczytow: 2-7 zlych na 20 —
  blad NIE wymaga duzego obciazenia.
  Przyczyna zrodlowa (`v2_root.py`, czysty sqlite3 bez Kartografa):
  ```
  A) domyslny statement cache, ten sam tekst SQL we wszystkich watkach: OK=7238 ZLE=6279 wyjatki={'InterfaceError':2481}
  B) ten sam conn, KAZDY watek inny tekst SQL                        : OK=16000 ZLE=0
  C) sqlite3.connect(..., cached_statements=0)                       : OK=16000 ZLE=0
  ```
- Uzasadnienie: audytor mial racje co do skutku i zanizyl opis przyczyny. `sqlite3.threadsafety == 3`
  dotyczy biblioteki C (tryb serialized), a nie **per-connection cache przygotowanych zapytan** w CPython:
  dwa watki wykonujace ten sam tekst SQL na jednym `Connection` dostaja ten sam `sqlite3_stmt`
  i nadpisuja sobie bindingi w trakcie krokowania — stad zwrot wiersza innego godla. Zachowanie
  jest wprost sprzeczne z ADR-019 ("WAL mode umozliwia rownoczesne odczyty z ThreadPoolExecutor")
  i z docstringiem modulu, wiec to bug, nie decyzja projektowa. Osiagalnosc potwierdzona: CLI PL
  nie wstrzykuje cache do providerow (`grep -rn "cache=" kartograf/cli/*.py` -> tylko galaz CZ,
  jednowatkowa), ale `create_nmt_provider(cache=MetadataCache())` + `DownloadManager(max_workers>1)`
  to udokumentowane, publiczne API (i typowy wzorzec integracji Hydrografa).
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/cache/metadata.py` — objac `with self._write_lock:` cale odczyty
  (`get_url` 151-158, `get_teryt` 236-240, `get_sheet` 289-293, a takze `stats()`), tak zeby
  `execute`+`fetchone` byly niepodzielne; wariant minimalny `cached_statements=0` w `connect()`
  usuwa korupcje, ale nie uszczelnia sekwencji "odczyt -> DELETE wygaslego wpisu", wiec lock jest
  bezpieczniejszy. Test przypinajacy: nowy `TestThreadSafety::test_concurrent_get_url_returns_own_value`
  (8 watkow x N odczytow roznych kluczy, asercja `got == oczekiwany` i brak wyjatkow) — dzis takiego
  testu nie ma (klasa testuje wylacznie zapisy). Szacunek: S (<30 linii). Ryzyko regresji: niskie
  (lock juz istnieje; odczyty sa krotkie, brak zagniezdzen — sprawdzone: `get_url` bierze lock dopiero
  po `fetchone`, wiec trzeba przebudowac te galaz na jeden blok, bez rekurencyjnego zajmowania locka).

### A2-2 — DownloadManager z jawnym `provider=` a bez `storage=` zapisuje NMPT/Orto do katalogu NMT i moze zwrocic plik NMT jako NMPT
- Werdykt: CONFIRMED
- Reprodukcja: `v2_a2_2.py` (`DownloadManager(output_dir=tmp, provider=GugikNmptProvider())`):
  ```
  NMT : nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc
  NMPT: nmt_1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   (KOLIZJA: True; ORTO ladu je w nmt_1m/*.tif)
  download_sheet(NMPT) -> ...N-34-130-D-d-2-4.asc | tresc: NMT DATA | provider.download wolany?: False | sidecar: False
  po realnym pobraniu NMPT (skip_existing=False) plik NMT zostaje NADPISANY trescia NMPT
  ```
- Uzasadnienie: potwierdzone w obie strony — przy `skip_existing=True` user dostaje cudzy produkt
  bez pobrania i bez sidecara, przy `--force`/`skip_existing=False` NMPT **nadpisuje** dane NMT
  (utrata danych). Zaden ADR tego nie usprawiedliwia; ADR-005/ADR-013 mowia wprost, ze podkatalog
  ma rozdzielac produkty, wiec to naruszenie wlasnej decyzji, a nie swiadomy kompromis. CLI jest
  odporne (`_create_provider_and_storage` zawsze zwraca pare) — dziura dotyczy publicznego API
  biblioteki, gdzie `provider=` jest udokumentowanym parametrem, a `GugikNmptProvider`/`GugikOrtoProvider`
  sa reklamowane w README:107 jako publiczne API.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/download/manager.py`:186 — gdy `storage is None`, wyprowadzic podkatalog
  z `get_source(provider.descriptor_key).storage_subdir` (rejestr ma juz komplet: nmt_1m/nmt_5m/nmpt/
  orto/laz/cz_dmr5g/cz_dmr4g — zweryfikowane), z fallbackiem na dzisiejsze `resolution` gdy provider
  nie ma `descriptor_key`. Dla domyslnego providera wynik jest identyczny jak dzis (`pl.gugik.nmt_1m
  -> nmt_1m`), wiec sciezki sie nie zmieniaja. Test przypinajacy: `test_download_manager.py` —
  `DownloadManager(provider=GugikNmptProvider())._storage._subdir == "nmpt"` + brak kolizji sciezek
  NMT/NMPT. Szacunek: S. Ryzyko regresji: niskie.

### A2-3 — `download_hierarchy` obiecuje `Raises DownloadError`, a polyka bledy — 100% niepowodzen konczy sie exit code 0
- Werdykt: CONFIRMED
- Reprodukcja: `v2_a2_3.py` — `main(["download", ...])` z providerem-mockiem rzucajacym `DownloadError`:
  ```
  godlo=N-34-130-D-d-2   workers=4 -> exit=0, pobranych plikow=0
  godlo=N-34-130-D-d-2   workers=1 -> exit=0, pobranych plikow=0
  godlo=N-34-130-D-d-2-4 workers=4 -> exit=1, pobranych plikow=0
  ```
  Bez `-q` uzytkownik widzi "Downloaded 0 files to ..." i cztery znaczniki `✗`, ale kod wyjscia
  to nadal 0. Osobno (`v2_a2_34.py`) potwierdzony blad licznika: 4 arkusze pominiete, nic nie
  pobrane -> log `Hierarchy download complete: 4/4 successful, 0 failed`.
- Uzasadnienie: kontrakt CLI zlamany (skrypt/pipeline dostaje sukces przy zerowym wyniku), a docstring
  `download_hierarchy` deklaruje wyjatek, ktorego metoda nigdy nie rzuca. `download N-34-130-D-d-2`
  (godlo grubsze niz 1:10000) to typowe wywolanie, wiec sciezka jest realna, nie brzegowa.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/download/manager.py` (docstring 305-313 + zliczanie w obu petlach) i
  `kartograf/cli/download_cmd.py` (`cmd_download`, galezie `--scale` i rozwinieta `download_sheet`).
  Minimalnie i bez zmiany typu zwracanego: zbudowac `DownloadResult` w obu petlach hierarchii,
  wystawic go jako atrybut managera (patrz A2-5) i w CLI zwrocic 1, gdy `result.failed` jest niepuste;
  przy okazji przestac liczyc `skipped` jako "successful" w logu. Test przypinajacy: `test_cli.py` —
  nowy test "hierarchia z samymi porazkami -> exit 1" oraz istniejacy `test_download_hierarchy`
  (mock ma juz `count_sheets`, wiec zostaje zielony). Szacunek: S/M. Ryzyko regresji: niskie.

### A2-4 — Rozjazd obslugi bledow: tryb sekwencyjny przerywa cala hierarchie na wyjatku spoza DownloadError, rownolegly go izoluje
- Werdykt: CONFIRMED
- Reprodukcja: `v2_a2_34.py` (provider rzuca `ConnectionResetError` na pierwszym z czterech arkuszy):
  ```
  workers=1: WYJATEK ConnectionResetError: nagly reset TCP; prob=1 (reszta arkuszy NIE probowana)
  workers=4: OK, zwrocono 3/4, prob=4
  ```
- Uzasadnienie: rozjazd realny i dokladnie taki, jak opisano. ALE kierunek ujednolicenia to decyzja
  projektowa, nie oczywisty bugfix: realnym wyzwalaczem jest `OSError` z `_save_response` (brak miejsca
  na dysku), a wtedy **przerwanie** calej hierarchii jest zachowaniem lepszym niz dzisiejsze
  "leć dalej" trybu rownoleglego — proponowana przez audytora naprawa (lapac `Exception` w obu trybach)
  pogorszylaby ten przypadek. Drugi wymieniony wyzwalacz (`TypeError`/`ValueError`/`InterfaceError`
  z cache'a) znika calkowicie po naprawie A2-1. Refaktor dotyka obu petli i logiki progresu tuz przed
  wydaniem.
- Naprawa przed wydaniem 0.7.0: NIE (odlozyc)
- Zakres naprawy: n/d (do etapu 2: ADR o polityce wyjatkow + jedna wspolna petla oparta na
  `_download_single_sheet_task`).

### A2-5 — `DownloadResult` jest w publicznym `__all__`, ale nigdy nie powstaje
- Werdykt: CONFIRMED
- Reprodukcja:
  ```
  $ grep -rn "DownloadResult" --include=*.py kartograf/ tests/
  kartograf/__init__.py:31,67 (eksport) | kartograf/download/manager.py:60 (definicja)
  tests/test_parallel_download.py:20,28,33,44,54 (konstrukcja wylacznie w testach)
  ```
  Zero wystapien `DownloadResult(` w `kartograf/`.
- Uzasadnienie: to nie tylko martwy typ w `__all__` — ADR-018 wymienia go wprost w Konsekwencjach
  ("DownloadResult zamiast list[Path] dla structured results"), wiec kod nie realizuje przyjetej
  decyzji, a testy jednostkowe konstruujace obiekt recznie maskuja ten fakt.
- Naprawa przed wydaniem 0.7.0: TAK (w wariancie NIE-lamiacym API)
- Zakres naprawy: `kartograf/download/manager.py` — obie petle hierarchii wypelniaja `DownloadResult`
  (succeeded/failed/skipped) i zapisuja go np. jako `self.last_result`; typ zwracany
  `download_hierarchy` zostaje `list[Path]` (zmiana typu = breaking API, do 0.8.0). CLI czyta
  `last_result` dla kodu wyjscia (A2-3). Test przypinajacy: `test_parallel_download.py` — po
  hierarchii z 1 porazka `manager.last_result.failed == [godlo]`. Szacunek: M. Ryzyko regresji: niskie
  (zmiana czysto addytywna).

### A2-6 — `Bdot10kProvider` zwraca sciezke do pliku, ktorego nie utworzyl
- Werdykt: CONFIRMED
- Reprodukcja: `v2_a2_6.py` — sztuczny ZIP z jednym GPKG (sqlite), `session` = `MagicMock`,
  `download_by_admin_unit("1465", tmp/"out/powiat_1465.zip")`:
  ```
  zwrocono : /tmp/.../out/powiat_1465.zip
  istnieje : False
  w katalogu: ['powiat_1465.gpkg']
  ```
- Uzasadnienie: potwierdzone co do joty — `_extract_gpkg_from_zip` pisze pod `with_suffix(".gpkg")`
  (bdot10k.py:609), a `_download_with_retry` zwraca `output_path` (515). Przez CLI nieosiagalne
  (`LandCoverManager._generate_output_path` generuje wylacznie nazwy `.gpkg` — sprawdzone,
  manager.py:405-417), wiec to luka publicznego API providera; sidecar LandCoverManagera przypialby
  sie do nieistniejacego pliku, gdyby wywolujacy podal inne rozszerzenie.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/providers/pl/bdot10k.py` — `_extract_gpkg_from_zip` zwraca faktycznie
  zapisana sciezke, `_download_with_retry` zwraca ja zamiast `output_path` (dla `extract_from_zip=False`
  bez zmian). Test przypinajacy: `test_landcover.py`/testy bdot10k — `download_by_admin_unit(...,
  tmp/"x.zip").exists() is True`. Szacunek: S. Ryzyko regresji: niskie (istniejace wywolania podaja
  juz `.gpkg`, wiec zwracana wartosc sie nie zmienia).

### A2-7 — Fallback `urls[0]` w `_get_opendata_url` akceptuje i cache'uje URL cudzego arkusza
- Werdykt: DOWNGRADE(Minor)
- Reprodukcja: `v2_a2_79.py` — mechanika dziala tak, jak opisano (odpowiedz WMS spreparowana tak,
  by zawierala wylacznie URL arkusza spod Krakowa):
  ```
  zwrocony URL: 74253_1234567_M-34-63-A-a-1-1.asc | set_url wolany z kluczem godla: N-34-130-D-d-2-4
  gdy w odpowiedzi jest tez URL z zadanym godlem -> wybierany jest ten dokladny (74253_2_N-34-130-D-d-2-4.asc)
  ```
- Uzasadnienie: audytor pokazal mechanike, ale przeoczyl geometrie zapytania. `_get_opendata_url`
  (gugik.py:462-470) pyta WMS **punktowo w srodku zadanego arkusza** (`buffer=10` m, `WIDTH/HEIGHT=100`,
  `I=J=50`) i nie ustawia `FEATURE_COUNT`, wiec serwer zwraca zwykle jedna ceche — te, ktorej zasieg
  zawiera srodek arkusza. "URL cudzego arkusza oddalonego o 400 km" wymaga wiec zepsutego skorowidza,
  a nie jest normalnym skutkiem fallbacku; fallback istnieje dlatego, ze nazwa pliku dostawczego bywa
  inna niz godlo (m.in. PL-2000, gdzie godlo ma kropki). Proponowana przez audytora naprawa
  ("nie cache'owac fallbacku") wylaczylaby cache dokladnie dla tych przypadkow, w ktorych jest
  najbardziej potrzebny — a cache i tak przechowuje wartosc, ktora ponowne zapytanie odtworzyloby
  identycznie. Zostaje realny, ale kosmetyczny brak: `logger.debug` zamiast `warning`.
- Naprawa przed wydaniem 0.7.0: NIE (odlozyc)
- Zakres naprawy: n/d (opcjonalnie w etapie 2: podniesc log do `warning` i — jesli kiedys pojawi sie
  `FEATURE_COUNT>1` — weryfikacja przeciecia zasiegu wzorem `GugikLazProvider._intersects`).

### A2-8 — Domyslny endpoint WCS NMT EVRF2007 jest martwy, a `download_bbox` uzywa go domyslnie; README/SCOPE/CLAUDE.md o tym milcza
- Werdykt: CONFIRMED (czesc dokumentacyjna; stan uslugi nieweryfikowalny offline)
- Reprodukcja:
  ```
  $ .venv/bin/python -c "...GugikProvider().vertical_crs, WCS_ENDPOINTS"
  domyslny vertical_crs: EVRF2007
  WCS EVRF2007: .../PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFFEVRF2007   (wg PROGRESS.md:170-177 = HTTP 404)
  $ grep -rn "WCS" README.md docs/SCOPE.md CLAUDE.md   # zadnej wzmianki o martwym EVRF2007;
    CLAUDE.md:202 mowi wylacznie o braku WCS dla 5m; README.md:89-91 pokazuje quickstart
    manager = DownloadManager(output_dir="./data"); manager.download_bbox(area, "my_area.tif")
  ```
- Uzasadnienie: rozjazd kod<->dokumentacja potwierdzony przez porownanie tekstow: przyklad
  z README trafia w domyslny EVRF2007, czyli w endpoint opisany we wlasnym PROGRESS.md jako 404.
  Doprecyzowanie osiagalnosci, ktorego w raporcie brak: **CLI w ogole nie wola PL `download_bbox`** —
  tryb `--bbox` dla PL idzie przez `find_sheets_for_bbox` + OpenData (`_download_pl_bbox`,
  download_cmd.py:739-758), wiec problem dotyczy wylacznie biblioteki i przykladu w README.
  Samego 404 nie potwierdzilem (zakaz sieci), zrodlem pozostaje PROGRESS.md z 2026-08-11.
- Naprawa przed wydaniem 0.7.0: DOCS-ONLY
- Zakres naprawy: `README.md` (adnotacja przy przykladzie `download_bbox` — dzialajacy wariant to
  `DownloadManager(vertical_crs="KRON86")`), `docs/SCOPE.md` (sekcja NMT PL) i `CLAUDE.md` sekcja
  "Ograniczenia" (dopisac obok istniejacego zdania o 5m). Przed wpisem zrobic jeden zywy `curl`
  na endpoint — jesli GUGiK go przywrocil, ustalenie znika. Walidacja endpointu w kodzie (analogiczna
  do `_get_validated_layers`) wymaga sieci w testach — odlozyc. Szacunek: S. Ryzyko regresji: niskie
  (tylko docs).

### A2-9 — Bledy serwera WMS (5xx) sa raportowane uzytkownikowi jako "brak pokrycia danymi"
- Werdykt: CONFIRMED
- Reprodukcja: `v2_a2_79.py` (`session.get.side_effect = requests.HTTPError("500 Server Error")`,
  3 warstwy):
  ```
  WMS query failed for layer L1/L2/L3: 500 Server Error        <- logger.warning na stderr
  DownloadError: No NMT 1m data available for N-34-130-D-d-2-4 (vertical_crs=EVRF2007). This area may not have 1m coverage...
  liczba prob (warstw): 3
  ```
- Uzasadnienie: potwierdzone; komunikat koncowy kieruje diagnoze na brak pokrycia, mimo ze zadna
  warstwa nie odpowiedziala. Okolicznosc lagodzaca, ktorej raport nie odnotowal: biblioteka nie
  konfiguruje logowania, wiec `logger.warning` trafia na stderr przez `logging.lastResort` i uzytkownik
  jednak widzi slad awarii — dlatego to mylacy komunikat, a nie calkowicie cicha porazka.
  Severity [Important] utrzymana.
- Naprawa przed wydaniem 0.7.0: TAK
- Zakres naprawy: `kartograf/providers/pl/gugik.py`:541-551 i `gugik_orto.py`:377-386 — zliczac bledy
  transportowe osobno; gdy `bledy_transportowe == liczba_warstw`, rzucic `DownloadError` z trescia
  o awarii uslugi i ostatnim bledem w komunikacie, w przeciwnym razie zostawic dzisiejszy tekst.
  Test przypinajacy: nowy test w `test_gugik_provider.py`/`test_gugik_orto.py` ("wszystkie warstwy
  rzucaja RequestException -> komunikat o awarii uslugi"); istniejace `test_get_opendata_url_not_found`
  uzywaja poprawnej odpowiedzi bez URL-a, wiec pozostaja zielone. Szacunek: S. Ryzyko regresji: niskie.

## Tabela
| ID | Werdykt | Naprawa 0.7.0 | Rozmiar | Ryzyko |
|----|---------|---------------|---------|--------|
| A2-1 | CONFIRMED | TAK | S | niskie |
| A2-2 | CONFIRMED | TAK | S | niskie |
| A2-3 | CONFIRMED | TAK | S/M | niskie |
| A2-4 | CONFIRMED | NIE (odlozyc) | — | — |
| A2-5 | CONFIRMED | TAK (bez zmiany typu zwracanego) | M | niskie |
| A2-6 | CONFIRMED | TAK | S | niskie |
| A2-7 | DOWNGRADE(Minor) | NIE (odlozyc) | — | — |
| A2-8 | CONFIRMED | DOCS-ONLY | S | niskie |
| A2-9 | CONFIRMED | TAK | S | niskie |

## Nowe ustalenia przy okazji (max 3, tylko jesli Critical/Important i z dowodem)

### V2-N1 [Important] CLI po cichu ignoruje `--resolution` dla `--product nmpt` (i `--vertical-crs` dla `--product orto`)
- Plik: `kartograf/cli/download_cmd.py`:64-78 (`_create_provider_and_storage`), `kartograf/providers/pl/gugik_nmpt.py`:123
- Twierdzenie: `kartograf download <godlo> --product nmpt --resolution 5m` konczy sie sukcesem
  i pobiera NMPT **1m**, bez ostrzezenia — mimo ze NMPT 5m nie istnieje; analogicznie
  `--product orto --vertical-crs KRON86` ignoruje uklad pionowy (Orto go nie ma).
- Dowod (`v2_new1b.py`, `main([...])` z podstawionym `DownloadManager`, prawdziwa fabryka providera):
  ```
  exit: 0
  provider: GugikNmptProvider | faktyczna rozdzielczosc providera: 1m
  manager resolution= 5m | storage subdir= nmpt
  ```
  oraz (`v2_new1.py`): `--product orto --vertical-crs KRON86 -> GugikOrtoProvider, vcrs=-` (flaga
  nie dociera nigdzie).
- Weryfikacja: dwa uruchomione snippety offline (wyzej); `grep -n "nmpt" kartograf/cli/download_cmd.py`
  pokazuje brak jakiejkolwiek walidacji pary product/resolution.
- Kontrast wewnatrz tego samego pliku: galaz CZ odrzuca niemozliwe kombinacje twardo
  ("Error: CZ nie ma rozdzielczosci 1m", download_cmd.py:1247-1252) i tak samo robi
  `_resolve_pl_sentinels` dla `--resolution 2m` — czyli standard projektu jest inny niz zachowanie
  galezi PL dla nmpt/orto.
- Proponowana naprawa: w `cmd_download` (galaz PL) odrzucic `--resolution 5m` dla `--product nmpt`
  i `--vertical-crs` dla `--product orto` komunikatem `Error: ...` (exit 1), symetrycznie do walidacji
  CZ. Szacunek: S. Ryzyko regresji: niskie (zaden istniejacy test nie uzywa tych kombinacji).
