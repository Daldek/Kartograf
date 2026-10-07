# Changelog

Wszystkie istotne zmiany w projekcie sa dokumentowane w tym pliku.

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - Unreleased
### Kampanie GUGiK 2026-10-07 (ADR-030 + errata 2026-10-07)
- **BREAKING (układ `data/`):** prawdziwe pliki NMT/NMPT/orto PL leżą
  wyłącznie w `<segment>/kampanie/<data>_<id>/<hierarchia godła>/<godło>.<ext>`
  (+ `.meta.json`); ścieżka standardowa `<segment>/<hierarchia>/<godło>.<ext>`
  jest dowiązaniem do najnowszej lokalnej kampanii (symlink względny, potem
  hardlink, potem kopia z `Warning:`; `extra.link` = `symlink`/`hardlink`/
  `copy`; przestawiane tylko na kampanię o kluczu `(aktualnosc, dt_pzgik, url)`
  ściśle większym niż klucz obecnego celu; ten sam cel lub klucz równy/większy
  = bez zmian).
  Brak migracji: zwykły plik w ścieżce standardowej jest nieznany, pierwsze
  uruchomienie pobiera go ponownie do `kampanie/` i zastępuje dowiązaniem
  (z sidecarem). Kopiowanie `data/` wymaga `cp -rL`/`rsync -aL`.
- **BREAKING (zachowanie):** domyślna strategia `newest` przy każdym
  uruchomieniu rozwiązuje najnowszy rekord skorowidza (cache `record_cache`
  7 dni), więc po wygaśnięciu cache pyta sieć i pobiera nowszą kampanię, jeśli
  się pojawiła; „ponowne uruchomienie bez sieci” działa tylko w oknie cache.
- **BREAKING (API):** `FileStorage.list_files()` domyślnie zwraca ścieżki
  standardowe — bez `kampanie/` i bez wiszących dowiązań
  (`list_files(campaigns=True)` = tylko `kampanie/`).
- Nowe: `--campaigns {newest,all}` (domyślnie `newest`) i `--min-year RRRR`
  (1900..2100; granica na roku `aktualnosc`, nie `dt_pzgik`; obie strategie).
  `all` pobiera każdą kampanię arkusza przechodzącą twardy filtr ADR-028 ze
  wszystkich warstw, bez limitu liczby kampanii (`logger.info` z liczbą).
  Rok z nazwy warstwy służy tylko w `all` do pominięcia zapytania; warstwa
  `Starsze` jest zawsze odpytywana. Rekord bez ustalonego roku nie spełnia
  `--min-year` (`all`: pominięty; `newest`: `NoCoverageError` „starsza niż
  min_year”). Podsumowanie `all` (bez `-q`): `Downloaded <n> campaign files
  for <m> sheets to <dir> (<k> already existed)`.
- API biblioteki: `DownloadManager(campaigns=, min_year=)`,
  `DownloadManager.last_sheet` (`SheetFetch`: `godlo`, `path`, `skipped`,
  `downloaded`, `reused`, `link`), `DownloadResult.campaign_files`,
  `DownloadResult.reused_campaign_files` (kampanie już lokalne per arkusz)
  i `DownloadResult.copied`; eksporty `kartograf.CampaignRef`,
  `kartograf.SheetFetch`; nowe moduły `download/campaigns.py`
  (`CampaignRef`, `validate_campaign_args`, `verify_file_format`) i
  `download/links.py`; `FileStorage.get_campaign_path`.
- Providery PL: `resolve_campaigns`, `download_record`, `record_source`,
  `_resolve_record(parser, timeout, query)`; skorowidz:
  `select_campaign_records`, `layer_upper_year`, `LAYER_FAMILY`.
  Nazwa warstwy GetCapabilities z rodziny produktu, ale spoza wzorca =
  `logger.warning` (warstwa nie jest odpytywana).
- Format pliku z pola `format` rekordu (nie z rozszerzenia URL); plik zawsze
  z rozszerzeniem kanonicznym (`.asc`/`.tif`; rekord 72675 z URL `.xyz` to
  AAIGrid i jest zwykłą kampanią `.asc`); brak pola (orto, stare wpisy cache)
  = format domyślny produktu. Po pobraniu weryfikacja po treści (nagłówek
  AAIGrid / sygnatura TIFF); nieznany format albo niezgodna treść = porażka
  kampanii (`DownloadError` z nazwą formatu, plik usunięty), nigdy ciche
  zapisanie pod `.asc`.
- Sidecar pliku kampanii jest obowiązkowy: `emit_sidecar(required=True)`
  (zapis atomowy); porażka zapisu = porażka kampanii (plik danych usunięty,
  dowiązanie nieprzestawione). Pozostałe sidecary zostają best-effort.
  Sidecar kampanii: `extra.campaign` = `{id, date, zgloszenie, source,
  full_sheet, dt_pzgik}`, `request.campaigns` zawsze, `request.min_year` tylko
  gdy podany; sidecar ścieżki standardowej to zwykły plik z `extra.link` i
  `extra.link_target`.
- Cache: `MetadataCache` ma tabelę `campaigns_cache` (TTL 7 dni, `--force` =
  `MetadataCache(refresh=True)`, `--min-year` poza kluczem; po skanie
  częściowym obsługuje tylko granice ≥ granicy skanu, niższa = ponowny
  skan); `kartograf cache stats` drukuje `Campaign entries`.
- Błędy i porażki: komunikat błędu pobrania pliku NMT/NMPT/orto
  (`DownloadError` z `download_to`) podaje nazwę pliku z URL zamiast godła,
  np. `84183_1852496_N-34-139-C-a-3-1.asc (OpenData): HTTP 404` (w `all`
  rozróżnia kampanie). Częściowa porażka `all` na arkuszu (także
  niepoprawna `aktualnosc` jednej kampanii) = kod 1 z pełną listą; pozostałe
  kampanie pobrane, dowiązanie na najnowszą poprawną. Porażka dowiązania
  (nawet kopii) = porażka arkusza; lista idzie dalej także przy `--workers 1`.
  Wyścig bez blokad: równoległe wywołania na tej samej ścieżce mogą chwilowo
  zostawić dowiązanie na starszej kampanii (samonaprawa przy kolejnym
  `newest`/`all`; pliki w `kampanie/` nietknięte).
- Wycinek PL `--target-crs`: zawsze `newest`, czyta arkusze przez dowiązania
  (`run_pl_cutout` nie przyjmuje `campaigns`), pomijany po samym istnieniu
  pliku wyniku; `--campaigns all` lub `--min-year` z `--target-crs` =
  `Error:` kod 1 przed siecią. Kontrola wolnego miejsca to dolne oszacowanie
  (D-3).
- CZ: opcje kampanii dotyczą tylko PL. Zadanie bez PL (godło CZ także pod
  `auto`, obszar/geometria z jawnym `--country cz`, obszar w całości czeski
  pod `auto`) = `Error: CZ (CUZK) nie ma kampanii — --campaigns
  all/--min-year dotyczą tylko PL` (kod 1, bez sieci); obszar pod `auto` z
  PL i CZ = jedno `Info:`, CZ pobierane dalej.
- LAZ: `--campaigns all` (wszystkie kafle, których rama przecina obszar, bez
  deduplikacji ADR-029; kafel przecięty tylko obwiednią pomijany jak dotąd),
  `--min-year` (dolna
  granica `akt_rok`); `--min-year` z `--year` wykluczają się. Układ LAZ bez
  zmian (bez dowiązań).
- Pojedyncze godło: „Skipped” zależy od `manager.last_sheet.skipped`
  (wcześniej pre-check istnienia pliku w CLI).
- `newest` przy awarii skorowidza GUGiK (I-1): błąd TRANSPORTU przy
  rozwiązywaniu rekordu (sieć, HTTP 429/5xx; nie brak pokrycia, nie inne 4xx
  ani raport OGC) na arkuszu z istniejącą lokalną kampanią nie jest porażką —
  arkusz pominięty z lokalnej kampanii (dowiązanie bez zmian), `Warning:`
  na stderr także z `-q` (`<godło>: skorowidz GUGiK niedostepny — uzyto
  lokalnej kampanii bez sprawdzenia nowszej (...)`; lista: jedno `Warning:`
  z godłami), kod bez zmian. `--campaigns all`, `--min-year`, `--force` i brak
  lokalnej kampanii — błąd jak dotąd. API: `SheetFetch.unverified`,
  `DownloadResult.unverified` (godło -> treść błędu). Biblioteka bez
  `MetadataCache` pyta skorowidz przy każdym `download_sheet` (także arkusza
  już pobranego) — przekaż cache providerowi (raz na 7 dni).

### LAZ 2026-10-07
- **Zmiana zachowania (ADR-029):** domyślnie (bez `--year`) LAZ pobiera
  najnowszy kafel per OBSZAR, nie per godło. Kafle są wybierane od
  najnowszego `akt_rok` (w roku: nowsza `akt_data`); starszy kafel jest
  pomijany, gdy jego część wspólna z obszarem pokrywają już wybrane kafle
  (ramy `msGeometry` w EPSG:2180, tolerancja krawędzi 1 m). Obszar w2
  (`--bbox 637400,487000,637450,487050`) pobiera tylko kafel 2025/PL-1992
  zamiast także 2022/PL-2000:S7 (250 MB) — E2E C13 „zdublowany obszar”.
  Kafel wnoszący niepokryty kawałek zostaje; kafel `czy_ark_wypelniony=NIE`
  nie wypiera starszych; kafel, którego rama nie przecina obszaru (tylko
  obwiednia), jest pomijany. `--year` — dedup pokryciowy w obrębie roku.
  Pominięte kafle CLI wypisuje jako `Info:` na stderr (także z `-q`).
- **Nowe API biblioteki (review-1 D17):** `kartograf.download.laz` —
  `download_laz_area(bbox, ...)`, `run_laz_download(selection, ...)`,
  `LazDownloadResult` (`downloaded`/`skipped`/`failed`/`superseded`),
  `LazTileFailure`; `GugikLazProvider.select_tiles(...)` zwraca
  `LazTileSelection` (`tiles`, `superseded` = `SupersededLazTile`).
  Eksport w `kartograf/__init__.py`. Pula wątków, sidecar kafla i porażki
  kafli przeniesione z `_cmd_download_laz` (CLI tylko drukuje; prywatne
  `cli/download_cmd._write_laz_sidecar` usunięte — zastępuje je
  `download.laz.write_laz_sidecar`). Porażka kafla nie jest wyjątkiem
  biblioteki (`result.failed`); CLI bez zmian: `Error:` + pełna lista, kod 1.
- `GugikLazProvider.discover_tiles` zwraca kafle wybrane regułą pokrycia
  (= `select_tiles(...).tiles`); wcześniej najnowszy per godło.
- `LazTile`: nowe pola `footprint` (rama w EPSG:2180, osie E,N), `date`
  (`akt_data`), `full_sheet` (`czy_ark_wypelniony`) — z wartościami
  domyślnymi, konstruktor pozycyjny bez zmian.
- Sidecar kafla LAZ niesie `extra.parent_request` w trybie
  `--bbox`/`--geometry` (bbox w układzie podanym, `countries: ["PL"]`) —
  ADR-023 (f).1 obejmuje LAZ; errata ADR-023 pkt 8 (review-2 N15) usunięta.
- Nowy moduł `kartograf/core/coverage.py` (przecięcie, różnica i bufor
  wypukłych wielokątów, bez nowych zależności).
- `GugikLazProvider`: jedna sesja HTTP na wątek
  (`transport.http.SessionPerThread`, jak pozostałe providery GUGiK) zamiast
  jednej `requests.Session` dzielonej przez pulę wątków pobierania kafli;
  sesja wstrzyknięta (`session=`) wygrywa zawsze. Sesja wątku powstaje przy
  pierwszym zapytaniu (testy patchują `kartograf.transport.http.make_gugik_session`).
- `download.laz.write_laz_sidecar` zapisuje przez wspólne
  `sources.sidecar.emit_sidecar` (treść sidecara bez zmian: `request.year`,
  `request.min_density`, `extra.parent_request`; provider bez
  `descriptor_key` nadal dostaje `pl.gugik.laz`). Ostrzeżenie o nieudanym
  sidecarze loguje `kartograf.sources.sidecar` (wcześniej `kartograf.download.laz`).

### Deduplikacja po review 2026-10-07
- Providery i transport (review D1): sześć kopii pętli pobierania pliku
  (`_download_with_retry`/`_make_request`/`_save_response` w GUGiK NMT/NMPT,
  orto, LAZ, BDOT10k, CORINE, SoilGrids) zastąpił jeden
  `transport.http.download_to` z hakami `validate=` (CORINE/SoilGrids:
  `reject_error_document` — raport XML/HTML WMS/WCS bez ponowień) i `save=`
  (BDOT10k GPKG: rozpakowanie ZIP). Zmiany zachowania, w których kopie się
  rozjechały:
  - **jeden backoff dla wszystkich: 2 s, potem 4 s** (`backoff_delay`);
    skorowidz GUGiK, WFS LAZ, TERYT BDOT10k i CUZK (`get_with_retry`,
    `download_to`) czekały dotąd 1 s/2 s. Wybrany wykładnik providerów:
    to on obsługiwał dotąd cały ruch plików (przeciążony serwer 5xx), a
    +3 s w najgorszym przypadku jest pomijalne wobec timeoutów 30–120 s;
  - zapis atomowy przez `os.replace` zamiast `Path.rename` (także scalanie
    GPKG BDOT10k): na Windows `rename` na istniejący plik rzuca
    `FileExistsError`, więc `--force` nad pobranym arkuszem padał;
  - komunikaty `DownloadError` po polsku jak w transporcie wspólnym
    („HTTP 404 (bez ponowien)”, „po 3 probach”) zamiast angielskich;
  - CORINE i SoilGrids: jedna sesja HTTP na wątek zamiast nowej,
    niezamykanej `requests.Session()` przy każdym pobraniu (także zapytania
    CLMS w trybie bezpośrednim);
  - katalog docelowy powstaje dopiero po udanej odpowiedzi HTTP (LAZ nie
    zostawia pustego katalogu po błędzie).
  Usunięte atrybuty klas `RETRY_BACKOFF_BASE` providerów (martwe po
  zmianie); `MAX_RETRIES` wskazuje `transport.http.MAX_RETRIES` (3).
- `transport.http.SessionPerThread` zastępuje dwie kopie
  `_session_for_thread` (mixin skorowidza GUGiK i BDOT10k); providery
  trzymają `self._sessions` zamiast `self._session` (review D2).
- `transform/bbox.py::envelope_from_2180` zastępuje
  `_transform_bbox_to_wgs84`/`_transform_bbox_to_epsg3857` w CORINE i
  SoilGrids (wynik bez zmian; review D19).
- `providers/pl/wcs.py::GugikWcsMixin`: wspólne `WCS_FORMATS`,
  `_construct_wcs_url` i `get_supported_formats` dla NMT/NMPT i orto;
  `validate_godlo` w `SkorowidzLayersMixin`; usunięte
  `GugikProvider.FORMAT_EXTENSIONS`/`get_file_extension` (kopia
  `BaseProvider.get_file_extension`, dziedziczona bez zmian; review D13).
- `transform.crs.CONTENT_POLICY` i `WARP_MARGIN_PX` zastępują prywatne
  stałe toru CZ (`providers/cuzk/dmr.py`) i lustrzane kopie wycinka PL
  (`download/cutout.py`: `WARP_MARGIN_PX`, `_HORIZONTAL_POLICY`) — jedna
  stała dla obu torów (review D9).
- CLI: jeden helper komunikatu błędu transformacji
  (`Error: ... Remedium: ...`, `_print_transform_error`) zamiast dwóch
  ręcznych kopii (geometria CZ, fabryka providera CZ); treść bez zmian
  (review D6).
- Reguła „NMT 5m (PL) tylko w EVRF2007” żyje w jednym miejscu
  (`kartograf.providers.pl.nmt_vertical_crs`) i ma jeden skutek: korektę
  do EVRF2007. CLI (`--product nmt --resolution 5m --vertical-crs KRON86`)
  drukuje teraz `Info:` na stderr (także z `-q`) zamiast korekty widocznej
  tylko w logu; fabryka `create_nmt_provider` loguje ją jak dotąd,
  `prepare_pl_cutout` nadal odrzuca niefaktyczny pion `ValidationError`.
  `DownloadManager` z providerem znającym swój pion nie loguje już
  korekty (pion i tak pochodzi z providera) (review D11).
- `DownloadManager.download_sheet` zwraca (i opisuje sidecarem) ścieżkę
  zwróconą przez provider — tak jak `download_hierarchy`/`download_sheets`;
  wcześniej zwracał ścieżkę docelową managera. Tryb sekwencyjny i równoległy
  korzystają z jednej treści „pobierz arkusz” (`_fetch_sheet`) i jednego
  raportu postępu; sekwencja statusów bez zmian (`downloading` tylko
  sekwencyjnie) (review D10).
- Ortofotomapa: podpowiedź `NoCoverageError` o arkuszu w innym układzie
  ma pełną postać jak w NMT (`<godło> (<skala>) — użyj tego godła lub
  --system X --scale Y`); wspólne `skorowidz.coverage_hints` (review D14).
- Wewnętrznie: jedna fabryka segmentu providera
  `download.storage.storage_for_provider` (CLI, `DownloadManager`, wycinek
  PL, tor CZ — review D18); jedno opakowanie best-effort sidecara
  `sources.sidecar.emit_sidecar` z formatem operacji `pinned_label`
  i nazwą wycinka `download.storage.bbox_cutout_path` (wycinek PL i CZ —
  review D7); jeden nagłówek listy arkuszy CLI `_print_sheet_list`
  (review D15). Ścieżki plików i treść sidecarów bez zmian.

### Parsery 2026-10-07
Uproszczenie parserów wg `docs/research/2026-10-06-e2e-brzegowe-i-review/ocena-parserow.md`
(kroki K1–K5, K7a; raport `impl-parsery.md`; K6, K7b, K9 — raport
`impl-porzadki.md`).

**BREAKING**
- Usunięte `kartograf.providers.cuzk.Sm5Sheet` (także
  `providers.cuzk.sheets.Sm5Sheet`) — jedynym producentem była fabryka
  rejestru, której nikt nie wołał. Arkusz SM5 po godle: `SheetIndex.sm5_sheet`.
- `core.parser_registry`: usunięte `register_system`, `_REGISTRY`
  i `SheetSystem.parser_factory`; rejestr to literał `SYSTEMS`.
  `detect_system` zwraca `SheetSystem` (nigdy `None` — `pl1992` jest
  fallbackiem). Wzorce godeł CZ: `parser_registry.CZ_TM33_PATTERN`
  i `CZ_SM5_PATTERN` (zamiast `parser_tm33._GODLO_RE`, `sheets._SM5_RE`).
  `kartograf/__init__.py` bez zmian; Hydrograf/Hydrolog nie importują tych nazw.
- `find_sheets_for_bbox` / `find_sheets_2000_for_bbox` zgłaszają
  `ValidationError` dla bboxa odwróconego (`min > max`) albo z NaN/inf —
  dotąd zwracały arkusz-śmieć (`BBox(10, 10, 5, 5)` -> `L-33-1-D-c-4-3`)
  albo kończyły się `ValueError`. Bbox-punkt nadal dozwolony.
- `kartograf.cli.commands` (fasada) nie re-eksportuje już prywatnych
  `_create_provider_and_storage` i `_resolve_laz_bbox` — importować
  z `kartograf.cli.download_cmd` (używały ich tylko testy; K9).
- Usunięte prywatne `core.geometry._transform_bbox` (4 narożniki),
  `download.cutout._sheet_frame_transformer`/`_sheet_frame_2180`,
  `_CZ_CRS`, `cli.download_cmd._CZ_CRS_WKIDS` i `providers.cuzk.dmr._EDGE_SAMPLES`
  — zastępują je `core.bbox.transform_bbox` i `is_czech_crs` (K6).

**Fixed**
- `find_sheets_for_bbox(..., system="2000")` z bboxa WGS84 przecinającego
  południk osiowy strefy (15/18/21/24°E) gubił cały wiersz arkuszy:
  `BBox(17.6, 50.535, 18.4, 50.555, "EPSG:4326")` dawał 8 arkuszy (tylko
  `6.136.*`) zamiast 16 (brak `6.135.17`–`6.135.24`). Obwiednia strefowa
  liczona z zagęszczonych krawędzi zamiast 4 narożników.
- Obwiednie bboxów między układami w `core` (`SheetParser.get_bbox`,
  `Parser2000.get_bbox`, selekcja arkuszy PL-1992/PL-2000, czytniki
  SHP/GPKG `read_feature_bboxes`/`get_overall_bbox`/`find_sheets_for_geometry`)
  liczone są jedną funkcją `core.bbox.transform_bbox` (zagęszczenie 21
  punktów/krawędź): arkusze 1:10000 bez zmian (1e-6 m), arkusze grube
  przez 19°E (np. `N-34`) dostają poprawną dolną krawędź (-468 m),
  obiekt SHP/GPKG przez 19°E czytany do WGS84 nie traci ~65 m na północy.
- `SheetParser.get_bbox("EPSG:2180")` buduje transformer raz na proces
  (cache), a nie przy każdym wywołaniu: 200 wywołań 1371 ms -> 8 ms.
  Czytniki SHP/GPKG: jeden transformer na warstwę zamiast na obiekt.
- Białe znaki wokół godła: `detect_system`, `path_parts`
  i `SheetIndex.sm5_sheet` obcinają je spójnie z parserami; CLI obcina
  pozycyjne godło `download`/`parse` w argparse — `kartograf download
  " 302_5550"` nie trafia już do toru PL z mylącym
  `Nieprawidlowe godlo PL-1992`.
- `kartograf landcover download --bbox` i `kartograf soilgrids hsg --bbox`:
  bbox odwrócony, NaN/inf albo zła liczba wartości kończy się
  `Error: Invalid bbox format: <powód>. Expected: ...` na stderr i kodem 1
  (dotąd odwrócony/NaN przechodził do pobierania); podpowiedź `Expected`
  nie idzie już na stdout. Nowe `cli._parser.parse_bbox_arg`.
- `kartograf download --bbox` (tory PL, CZ i LAZ) parsuje bbox tym samym
  `parse_bbox_arg`: bbox odwrócony nie daje już arkusza-śmiecia, NaN nie
  kończy się `Error: ValueError: ...`, podpowiedź idzie z błędem na stderr
  (K7b).
- Wycinek PL (`--target-crs`, `prepare_pl_cutout`/`download_pl_cutout`)
  i selekcja kafli LAZ z bboxa WGS84 przecinającego 19°E: obwiednia
  w EPSG:2180 z zagęszczonych krawędzi zamiast 4 narożników —
  `BBox(18, 50, 20, 50.2, "EPSG:4326")` ma `min_y` 236968,4 zamiast
  237447,4 (~479 m pasa na S); nazwa pliku wycinka niesie poprawny zasięg.
  Rozpoznawanie/przycinanie krajów (`--country auto`) liczy obwiednię
  WGS84 tak samo. Obwiednie CZ (`bbox_to_crs`, 9 -> 21 próbek na krawędź)
  bit w bit bez zmian dla zmierzonych bboxów (K6).
- `CuzkDmrProvider.download` obcina białe znaki godła na wejściu:
  `download(" CTES96")` z biblioteki buduje poprawny URL openzu (dotąd
  rejestr rozpoznawał SM5 po `strip()`, a URL dostawał godło ze spacją).

**Added**
- `kartograf.core.bbox`: `BBox` (przeniesiona z `sheet_parser` —
  `kartograf.BBox`, `core.sheet_parser.BBox`, `core.geometry.BBox` to ta
  sama klasa), `validate_bbox`, `transform_bbox` (cache transformerów,
  operacja przypięta przez `transformer=` — duck typing), `is_czech_crs`.

### Runda review/E2E 2026-10-06
- Tor CZ (`CuzkDmrProvider`, `--target-crs` i kafel TM33) używa wspólnego
  `transform/raster.warp_to_grid` zamiast własnej kopii
  `providers/cuzk/dmr.py::_warp_to_grid`. Nieudana reprojekcja (np. z
  `--force`) NIE kasuje już poprzedniego wycinka/kafla — tak jak w torze PL.
  Wynik warpu bit w bit bez zmian (review D8/N7).
- CORINE i SoilGrids (`_download_with_retry`) stosują politykę ponowień
  z `transport/http.py`: 4xx poza 429 (np. 404 przy błędnej nazwie
  pokrycia WCS) kończy od razu, bez 3 prób i 6 s czekania; `Retry-After`
  wydłuża przerwę; `DownloadError.status_code` niesie kod HTTP (wcześniej
  zawsze `None`). Backoff bez zmian (2 s, 4 s) (review D1/N9).
- `CuzkClient.query` (indeks arkuszy SM5/TM33) i zapytanie TERYT BDOT10k
  (`Bdot10kProvider._get_teryt_for_point`) idą przez
  `transport.http.get_with_retry`: błąd sieci, 429 i 5xx są ponawiane
  (wcześniej jedna próba), 404 kończy od razu ze `status_code`. Błąd
  treści (JSON) nie jest ponawiany. `get_with_retry` przyjmuje opcjonalne
  `params=` (review N5).
- BDOT10k `--format SHP` zapisuje archiwum ZIP z shapefile'ami jako `.zip`
  (np. `bdot10k_teryt_1465.zip`, sidecar obok), a nie pod nazwą `.gpkg`,
  która udawała GeoPackage. `Bdot10kProvider.download_by_admin_unit`
  (także przez bbox/godło) zwraca ścieżkę `.zip`; CLI drukuje faktyczną
  ścieżkę (review N1).
- `kartograf landcover download` z błędnym `--property`/`--depth`/`--stat`
  (SoilGrids) albo `--year` (CORINE) kończy się `Error: <treść>` i kodem 1
  przed siecią — bez `ValueError:` i podpowiedzi `KARTOGRAF_DEBUG`, która
  sugerowała awarię programu (review N8).
- LAZ: porażka pobrania kafli daje `Error: N z M kafli LAZ nie pobrano ...`
  z PEŁNĄ listą nieudanych kafli (wcześniej `Warning:` przy kodzie 1 i tylko
  5 pierwszych). Kod wyjścia bez zmian: 1 (review N6).
- Orto: wariant koloru jest częścią ścieżki pliku. RGB zostaje
  w `orto/pl_<uklad>/` (bez migracji), CIR trafia do `orto/pl_<uklad>_cir/`,
  B/W do `orto/pl_<uklad>_bw/`. Wcześniej `GugikOrtoProvider(color="CIR")`
  przy istniejącym pliku RGB tego arkusza zwracał po cichu RGB (skip).
  Nowe: `BaseProvider.storage_variant`, `FileStorage(variant=...)`
  (E2E-B C12-f, E12).
- Niepełny arkusz widoczny: gdy wybrany rekord skorowidza ma
  `full_sheet: false` (najnowsza kampania nie wypełnia arkusza), CLI
  drukuje `Warning:` w torze godła, listy arkuszy i wycinka (także przy
  skip). `extra.sheet_sources` wycinka ma pole `full_sheet`,
  `PlCutoutResult.partial_sheets` listuje takie arkusze, a pusty wycinek
  z nich ostrzega o niepełnej kampanii zamiast „brak danych GUGiK”.
  Reguła wyboru (ADR-028: najnowsza kampania) bez zmian (E2E-B C12-a/C14-b,
  E2E-A C5, E13).
- `--force` w torach PL omija ODCZYT cache rekordów skorowidza, ale
  zapisuje świeżo wybrany rekord (i potwierdzony brak pokrycia) — kolejny
  przebieg bez `--force` dostaje nowy rekord zamiast starego sprzed zmiany
  kampanii. Nowe: `MetadataCache(refresh=True)` (odczyty = chybienie,
  zapisy normalnie); CLI przekazuje go zamiast `cache=None`
  (E2E-B C15, E14).
- Skip: pojedyncze godło pominięte jako istniejące drukuje
  `Skipped <godlo> - already exists at ...` zamiast `Downloaded to`.
  Pusty wycinek PL zapisuje w sidecarze `extra.all_nodata: true`;
  pominięcie takiego wycinka odtwarza `PlCutoutResult.all_nodata` z sidecara
  (bez czytania rastra), a CLI powtarza `Warning:` (E2E-B C17, E15).
- LAZ: sidecar `request` zapisuje `year` i `min_density`, gdy podano
  `--year`/`--min-density` (wcześniej tylko bbox). Dokumentacja: `gestosc`
  i `--min-density` to gęstość nominalna z WFS GUGiK (E2E-B C13-f, E16).
- GetCapabilities skorowidza GUGiK (odkrywanie warstw NMT/NMPT/orto) ma
  timeout providera — 30 s NMT/NMPT, 60 s orto, albo `timeout=` przekazany
  do `download()` — zamiast zaszytych 10 s (review N3, E10).
- Jeden parser wartości układu GUGiK: `sources.registry.parse_pl_uklad`
  (`PL-1992`, `PL-2000:S5..S8`, białe znaki na brzegach obcinane) używany
  przez rekordy skorowidza, `horizontal_crs_for_uklad` (sidecar) i
  `LazTile.uklad`. Nietypowa wartość (np. `PL-2000` bez strefy) jest
  odrzucana spójnie: rekord skorowidza bez układu, kafel LAZ pominięty
  w discovery (ostrzeżenie w logu), **BREAKING:** `LazTile.uklad` rzuca
  `ValidationError` zamiast zgadywać z formatu godła (wcześniej segment
  `pl_2000` przy sidecarze EPSG:2180). Realne dane GUGiK mają wyłącznie
  wartości rozpoznawane (E2E 2026-10-06, E11) (review-1 D3).
- Dokumentacja i test (bez zmiany kodu): arkusze PL-2000 strefy 7
  publikowane przez GUGiK we współrzędnych EPSG:2180 — sidecar opisuje
  układ pliku (EPSG:2180), `extra.source.uklad` deklarację rekordu, plik
  w segmencie wg godła; fixtura z surowego nagłówka
  `tests/fixtures/gugik_asc/77912_1384976_7.125.11.19.head.asc` (E2E-A
  C6b/C6h, E17).
- Arkusz PL w innym układzie niż wskazuje godło (np. PL-2000 strefy 7
  opublikowany w EPSG:2180): CLI drukuje `Warning: N arkuszy GUGiK
  opublikowano w innym ukladzie niz wskazuje godlo: <godlo> (godlo: ...,
  plik: ...)` na stderr — tor godła, listy `--bbox`/`--geometry`
  i hierarchii, także przy skip i `-q`; fakt czytany z sidecara
  (`horizontal_crs` vs układ z godła). Kod wyjścia bez zmian (0).
  Wcześniej był tylko komunikat loggera bez prefiksu (E17).
- `KARTOGRAF_DEBUG=1` daje pełny traceback także dla `KartografError`
  docierającego do bariery `main` — wcześniej zawsze skracany do
  `Error: ...` wbrew opisowi zmiennej (review N17).
- `--force` w torze CZ otwiera `MetadataCache(refresh=True)` jak w PL:
  indeks arkuszy SM5 (`sheet_cache`, TTL 30 d) jest odpytywany na nowo
  i zapisywany. Wcześniej `--force` pobierał ponownie tylko plik,
  a indeks szedł z cache (review-1 D16).
- `Bdot10kProvider.DEFAULT_TIMEOUT` = 120 s i jest domyślną wartością
  `download_by_admin_unit/godlo/bbox` (wcześniej martwa stała 60 s obok
  sygnatur ze 120 s; zachowanie bez zmian) (review N11).
- Errata dokumentacji (review-2): README — arkusz za granicą w trybie
  listy to `Warning:` i kod 0, nie kod 1 (N2), liczby testów (N12);
  „3 próby” doprecyzowane jako ponowienia tylko dla sieci/429/5xx w
  CLAUDE.md, SCOPE, ARCHITECTURE, docstringu `download_pl_cutout`
  i erracie ADR-028 (N4); lista timeoutów bez martwego „CORINE przez
  TERYT” (N10); krawędź `cli -> transport` w ARCHITECTURE 2 (N13);
  rozszerzenie pliku landcover nadaje provider (N14); errata ADR-023
  (f).1 — LAZ bez `parent_request` (N15); docstringi `LandCoverManager`
  i `MetadataCache` (N16).

### Polityka ponowień HTTP i sesja BDOT10k (2026-10-06)
- Pobieranie GUGiK (NMT/NMPT/orto/LAZ/BDOT10k) oraz wspólny transport
  (`get_with_retry`, `download_to` — skorowidz, WFS LAZ, CUZK) ponawia
  tylko błędy sieci, HTTP 429 i 5xx. Pozostałe 4xx (np. 404) kończą
  pobieranie od razu, bez 3 prób i 6 s czekania; komunikat podaje
  `HTTP <kod> (bez ponowien)` / `(not retried)`.
- Nagłówek `Retry-After` (sekundy albo data HTTP) wydłuża przerwę przed
  ponowieniem ponad backoff, z górną granicą 60 s (`MAX_RETRY_AFTER`).
- `DownloadError.status_code` niesie kod HTTP ostatniej próby (wcześniej
  zawsze `None` w tych torach). Nowe w `kartograf.transport.http`:
  `is_retryable`, `retry_wait`, `http_status`, `http_failure`.
- `Bdot10kProvider` bez wstrzykniętej sesji używa jednej sesji GUGiK na
  wątek (`make_gugik_session`: keep-alive, `User-Agent: kartograf/<wersja>`)
  dla zapytań TERYT i pobrań — wcześniej nowa `requests.Session()` na każde
  wywołanie.

### Fala naprawcza 2026-09-29/30 — migracja
- Przy wyborze arkusza GUGiK `NoCoverageError` zastępuje cichy plik
  PL-1992 pod godłem PL-2000, plik 0,5 m pod żądaniem 1 m lub
  arkusz potomny; dla PL-2000 1:10000 z samymi potomkami użyj
  `--scale 1:2000`. Awaria nowszej warstwy skorowidza lub jednego
  rocznika LAZ `discover_tiles` zwraca `DownloadError` zamiast
  cichego przejścia do starszej kampanii / wyniku pustego.
- `MetadataCache.get_url/set_url` zastąpiono `get_record/set_record`
  (`{"source": ...}` lub `{"no_coverage": true, "message": ...}`); trafienie
  negatywne odtwarza pełną podpowiedź braku pokrycia. Stara tabela SQLite
  `url_cache` jest usuwana przy otwarciu, `stats()["record_count"]`
  i `kartograf cache stats` (`Record entries`) liczą nowe rekordy.
  `--force` omija cache rekordów, `download_pl_cutout(cache=)` daje
  bibliotece opcjonalny cache.
- Usunięto zaszyte `WMS_LAYERS` i `FALLBACK_YEARS`: discovery warstw
  i lat bazuje na GetCapabilities; awaria daje `DownloadError`.
  `GugikOrtoProvider(color="RGB")` domyślnie wybiera RGB, a
  `color="CIR"` żąda podczerwieni.
- `GridMismatchError(ValidationError)` z `.off_grid` zastępuje błędny
  wycinek EPSG:2180 z arkuszy o różnych fazach; inny `--target-crs`
  używa W1 (warp per arkusz). Lista arkuszy i hierarchia godła z R5:
  `NoCoverageError` -> `DownloadProgress.status == "no_coverage"`,
  `Warning:` i kod 0 przy co najmniej jednym pliku; brak wszystkich
  lub twarda awaria -> kod 1 z pełną listą niepowodzeń.
- Sidecar dodaje `extra.source` (arkusz), `sheet_sources` (wycinek),
  `parent_requests` (arkusze wykorzystane ponownie) i
  `off_grid_sheets` (W1); arkusze PL-2000 dostają rzeczywisty
  `horizontal_crs` EPSG:2176–2179. `PlCutoutResult` dodaje
  `all_nodata` i `off_grid_sheets`; pominięty wycinek odtwarza
  brakujące/odchylone arkusze z sidecara. 16 testów `live` zamiast 8
  (nieuruchomione w tej fali).
- Istniejące rastry CZ i wycinki PL -> EPSG:5514 z sidecarem
  `S-JTSK to ETRS89 (3)` były liczone słowacką operacją i mogą być
  przesunięte o 1–5 m; CLI drukuje `Info:` przy ich pominięciu,
  ale nie przebudowuje ich automatycznie: uruchom ponownie z `--force`.

### Fixed — fala naprawcza 2026-09-29/30
- **K1:** BBOX i envelope LAZ WFS respektują osie (N,E), a straż
  przecięcia odrzuca kafle spoza żądanego obszaru.
- **K2:** Pin czeskiej operacji EPSG:1622/1623 (1,0 m) zastępuje
  słowacką EPSG:4829, usuwając przesunięcie reprojektowanego CZ
  i wycinka PL -> 5514.
- **K3:** Nieudane zapytanie nowszej warstwy kończy się `DownloadError`
  po ponowieniach zamiast cicho pobierać starszą kampanię.
- **K4:** Ścisły filtr godła, układu, rozdzielczości i daty wybiera
  właściwy arkusz zamiast pierwszego częściowo zgodnego URL-a.
- **K5:** Orto domyślnie wybiera najnowszy rekord RGB zamiast CIR
  lub najstarszej edycji w warstwie zbiorczej.
- **K6:** CUZK dzieli `exportImage` przy budżecie 4 Mpx na żądanie,
  więc duże wycinki nie trafiają do limitu serwera ~8 Mpx.
- **S1:** Zapytania GetCapabilities/GetFeatureInfo korzystają z sesji
  per wątek i retry, aby zerwane połączenie nie kończyło zadania od razu.
- **S2:** R5 obejmuje listę arkuszy i hierarchię: brak danych jednego
  arkusza nie przerywa pobierania pozostałych.
- **S3:** `--country auto` drukuje `Info:` o rzeczywistym przycięciu i utracie
  obszaru (nie dla części PL `--geometry` bez `--target-crs`, która wyznacza
  arkusze z całej geometrii); w trybie listy `--bbox` sidecar ma
  `request.godlo`, a nie `request.bbox`. Nieobcięte krawędzie PL nie są
  poszerzane przez round-trip CRS.
- **S4:** Zniknął fallback na przestarzałe, zaszyte warstwy NMPT;
  brak prawidłowej odpowiedzi serwera jest błędem, nie niepewnym
  brakiem danych.
- **S5:** Niezgodna faza arkuszy NMT 5 m powoduje jawny
  `GridMismatchError` w EPSG:2180, a dla innego CRS uruchamia W1,
  bez złych pikseli i szwów nodata z poprzedniej mozaiki.
- **N1:** Uszkodzony szablon GetFeatureInfo nie jest już uznawany za
  pustą odpowiedź i fałszywy brak pokrycia.
- **N2:** CLI ostrzega o wycinku PL/CZ w całości nodata, zachowując
  kod 0 dla poprawnie pobranego, lecz pustego rastra.
- **N3:** Snap od naroża NW daje dokładny piksel 2 m/5 m również
  dla pojedynczego wycinka CUZK.
- **N4:** Pominięte arkusze dopisują nowe żądania do `parent_requests`,
  a pominięty wycinek odczytuje `missing_sheets` i `off_grid_sheets`
  z sidecara.
- **N5:** Osiem testów WMS PL-2000 ma asercje wobec prawdziwych
  rekordów/CRS zamiast samych połączeń (łącznie 16 testów `live`).
- **N6:** CLI podpina cache rekordów do pobierania PL, aby kolejny
  przebieg bez `--force` nie pytał ponownie skorowidza.
- **N7:** Awaria discovery rocznika LAZ zgłasza `DownloadError` z rokiem,
  a jawnie nieistniejący `--year` podaje lata z GetCapabilities bez sugestii
  ponawiania; `No LAZ tiles found` oznacza komplet poprawnych odpowiedzi.
- **N8:** Sidecar arkusza/kafla PL-2000 zapisuje EPSG odpowiedniej
  strefy zamiast EPSG:2180.
- **N9:** Kontrola miejsca na dysku wykorzystuje policzone wcześniej
  brakujące arkusze zamiast przeliczać je przed uruchomieniem wycinka.
- **H1:** Parser rekordów rozpoznaje URL-e arkuszy `.ASC` niezależnie
  od wielkości liter, aby nie zgubić dostępnych danych.


### Breaking Changes
- **Przejscie z 0.6.1 — co zrobic (m.in. Hydrograf):**
  - **Istniejacy cache `data/`** — Kartograf nie migruje go sam, a sciezki
    z 0.6.1 przestaja byc widziane jako pobrane (`skip_existing` pobierze
    wszystko ponownie). Przed upgradem przenies katalogi: z `nmt_5m/`
    hierarchie godel PL-1992 (`N-34/...`, `M-33/...`) do
    `nmt/pl_1992_5m_evrf2007/`, a hierarchie PL-2000 (`5/`..`8/`) do
    `nmt/pl_2000_5m_evrf2007/`; z `nmt_1m/` analogicznie do
    `nmt/pl_<uklad>_1m_<vcrs>/`, gdzie `<vcrs>` trzeba znac z wlasnej
    konfiguracji (0.6.1 nie pisal sidecarow, a arkusze KRON86 i EVRF2007
    dzielily w nim jeden katalog; domyslny byl EVRF2007) — przed
    przeniesieniem sprawdz `cellsize` w naglowku ASC (w cache Hydrografu
    katalog `nmt_1m/` zawiera pliki 5 m). Analogicznie `nmpt/`, `orto/`, `laz/`
    (tabela nizej). Pliki przeniesione nie dostaja sidecarow (pobranie
    pominiete jako istniejace nie pisze sidecara).
  - **Importy** — przeniesione moduly providerow nie maja shimow:
    `from kartograf.providers.bdot10k import Bdot10kProvider` konczy sie
    `ModuleNotFoundError`; uzyj `from kartograf import Bdot10kProvider` albo
    `kartograf.providers.pl.bdot10k` (pelna tabela nizej: `gugik`,
    `gugik_nmpt`, `gugik_orto`, `gugik_laz`, `bdot10k`, `landcover_base`).
    Prywatne `Bdot10kProvider._get_teryt_for_point()` nadal istnieje.
  - **Jeden raster NMT dla obszaru** — zamiast skladac mozaike samemu
    (albo z `kartograf.transport.mosaic.mosaic_and_crop`, ktore NIE jest
    eksportowane w `kartograf` i jest wewnetrznym krokiem) uzyj publicznego
    `kartograf.download_pl_cutout` (EVRF2007/KRON86, 1 m/5 m, cel
    EPSG:2180/5514/3045; arkusz bez danych = nodata + `missing_sheets`);
    z wlasnym providerem, sesja albo `MetadataCache` — kroki
    `prepare_pl_cutout` -> `select_pl_cutout_sheets` ->
    `run_pl_cutout(provider=...)`.
  - **Pozostale zmiany widoczne dla konsumenta:** sidecar `<plik>.meta.json`
    obok kazdego pobranego pliku; `NoCoverageError` jest podklasa
    `DownloadError` (`except DownloadError` lapie oba);
    `vertical_crs_code("EVRF2007")` = `EPSG:5621`; `import kartograf` laduje
    `rasterio`; w CLI domyslne `--country auto` (tabele i opisy nizej).
- **Nowy uklad `data/` — segmenty `<produkt>/<kraj>_<uklad>[_<wariant>][_<vcrs>]`**
  (ADR-026, decyzje D1-D8; kanoniczny opis: `docs/ARCHITECTURE.md` sekcja 3).
  Kazdy segment koduje jawnie kraj, uklad poziomy (PL: 1992/2000 — domkniecie
  odroczonego ADR-017) i pionowy (kron86/evrf2007/bpv; orto bez pionowego).
  Tabela migracji:

  | Stara sciezka | Nowa sciezka |
  |---|---|
  | `nmt_1m/` (godla 1992) | `nmt/pl_1992_1m_<vcrs>/` |
  | `nmt_1m/` (godla kropkowe 2000) | `nmt/pl_2000_1m_<vcrs>/` |
  | `nmt_5m/` | `nmt/pl_<uklad>_5m_evrf2007/` |
  | `nmpt/` | `nmpt/pl_<uklad>_1m_<vcrs>/` |
  | `orto/` | `orto/pl_<uklad>/` |
  | `laz/` | `laz/pl_<uklad>_<vcrs>/` |
  | `cz_dmr5g/` (tylko 0.7.0-dev) | `nmt/cz_dmr5g_<vcrs>/` |
  | `cz_dmr4g/` (tylko 0.7.0-dev) | `nmt/cz_dmr4g_<vcrs>/` |

  `<uklad>` bierze sie z formatu godla KAZDEGO pliku z osobna (kropki ->
  `2000`, myslniki -> `1992`) — stary `nmt_5m/`, `nmpt/`, `orto/` i `laz/`
  trzymaly oba systemy razem, wiec jeden stary katalog rozchodzi sie przy
  migracji na dwa segmenty. `<vcrs>` przy migracji recznej odczytaj
  z sidecara (`vertical_crs`);
  pliki sprzed etapu 0 nie maja sidecarow — wtedy re-download albo wiedza
  wlasna uzytkownika. Kartograf nie migruje `data/` automatycznie: pliki
  w starym ukladzie przestaja byc widziane jako pobrane. `landcover/` bez zmian.
- **`SourceDescriptor.storage_subdir` zmienia semantyke: literal -> szablon**
  z placeholderami `{uklad}`/`{vcrs}` (ADR-026). Konsument czytajacy pole
  wprost dostanie szablon — uzywaj `resolve_subdir()`.
- **Glebokie sciezki importu providerow** (bez shimow — decyzja z review
  specu etapu 0; publiczne API `from kartograf import ...` BEZ zmian):

  | Stary import | Nowy import |
  |---|---|
  | `kartograf.providers.gugik` | `kartograf.providers.pl.gugik` |
  | `kartograf.providers.gugik_nmpt` | `kartograf.providers.pl.gugik_nmpt` |
  | `kartograf.providers.gugik_orto` | `kartograf.providers.pl.gugik_orto` |
  | `kartograf.providers.gugik_laz` | `kartograf.providers.pl.gugik_laz` |
  | `kartograf.providers.bdot10k` | `kartograf.providers.pl.bdot10k` |
  | `kartograf.providers.landcover_base` | `kartograf.providers.base` |

  Dodatkowo: wrapper zgodnosciowy `download_by_teryt` (w `LandCoverProvider`)
  zweza pozycyjna arnosc wzgledem dotychczasowych podklas — przyjmuje pozycyjnie
  tylko `teryt`, `output_path`, `timeout`; kazdy kolejny argument (np. `format`
  w `Bdot10kProvider.download_by_admin_unit`) przekazany pozycyjnie (4. argument)
  konczy sie `TypeError`. Przekazuj takie argumenty jako keyword (`format=...`).
- **Sidecary CZ: `transform.horizontal` zmienia format i zakres** (ADR-024).
  Bylo `"server:EPSG:<kod>"` (tylko przy `--target-crs`), jest
  `"pinned: <opis operacji> (<dokladnosc> m)"` — i pojawia sie takze dla kafli
  TM33 pobranych godlem, ktore dotad mialy `transform: null`. Konsumenci
  parsujacy prefiks `server:` musza zostac dostosowani; format jest teraz
  wspolny dla obu osi (`transform.vertical` mial go od poczatku).
- **`vertical_crs_code("EVRF2007")` zwraca teraz `EPSG:5621`** (ogolnoeuropejski
  EVRF2007), nie `EPSG:9651` (dawna wartosc dla realizacji polskiej). Powod:
  `EVRF2007` jest teraz nazwa RODZINY ukladow, wspolna dla PL i CZ. Realizacja
  polska dostepna pod nowa nazwa `EVRF2007-PL`. Sidecary PL bez zmian tresci
  (mapowanie rodzina→realizacja przez nowa funkcje `resolve_vertical_crs`).
  Dotyczy: Hydrograf/Hydrolog, jesli woluja `vertical_crs_code` bezposrednio.

  | Nazwa (CLI/API) | Stary kod (< 0.7.0) | Nowy kod (>= 0.7.0) |
  |---|---|---|
  | `KRON86` | `EPSG:9650` | `EPSG:9650` (bez zmian) |
  | `EVRF2007` | `EPSG:9651` (realizacja PL) | `EPSG:5621` (rodzina, ogolnoeuropejski) |
  | `EVRF2007-PL` | — (nie istniala) | `EPSG:9651` (nowa nazwa realizacji polskiej) |
  | `Bpv` | — (nie istniala, CZ) | `EPSG:8357` (Baltic 1957, CUZK) |

- **`SoilGridsProvider.download_by_teryt()` rzuca `NotImplementedError`** —
  dotad zwracal jako sukces dane dla stalego obszaru 60x60 km wokol srodka
  WOJEWODZTWA (2-cyfrowy prefiks TERYT), identyczne dla kazdej gminy w tym
  wojewodztwie. Uzyj `download_by_bbox()` albo `download_by_godlo()`.
  (audyt 0.7.0: A4-3)
- **`LandCoverManager.download_by_teryt/download_by_bbox/download_by_godlo`
  bez `output_path` nazywaja pliki tak jak `download()`** — bylo
  `CORINE Land Cover_N-34-130-D.gpkg` (spacje w nazwie, etykieta zrodla),
  jest `corine_land_cover_godlo_N-34-130-D.gpkg` (baza nazwy; rozszerzenie
  zapisanego pliku nadaje provider — CORINE `.tif`/`.png`, SoilGrids `.tif`;
  errata 2026-10-06, review N14). Skrypty skladajace sciezke
  wyniku z nazwy zrodla wymagaja poprawki. (audyt 0.7.0: A5-2)
- **`GugikProvider.download_bbox(vertical_crs="EVRF2007")` konczy sie
  `ValidationError`** z remedium — GUGiK wycofal endpoint WCS
  `DigitalTerrainModelFormatTIFFEVRF2007` (404 takze dla GetCapabilities),
  wiec WCS NMT 1m dziala wylacznie w KRON86; kanal WCS deskryptora
  `pl.gugik.nmt_1m` deklaruje juz tylko `EPSG:9650`. Dotad zapytanie
  wychodzilo w swiat i wracalo bledem transportu. (audyt 0.7.0: A1-4)
- **`find_sheets_for_bbox()`/`find_sheets_for_geometry()`: stykajace sie
  krawedzie nie sa przecieciem** — liczy sie dodatnie pole przeciecia, wiec
  bbox rowny arkuszowi w jego ukladzie (EPSG:4326 dla PL-1992, strefa
  2176-2179 dla PL-2000) zwraca TYLKO jego arkusze (bbox w EPSG:2180
  przechodzi przez szersza obwiednie WGS84 i zwraca takze sasiadow — np.
  9 godel dla `N-34-130-D-d-2-4`):

  | zapytanie | bylo | jest |
  |---|---|---|
  | bbox arkusza `N-34-130-D`, `--scale 1:50000` | 9 godel | 4 (`N-34-130-D-a..d`) |
  | bbox arkusza `N-34-130-D-d-2-4` (1:10000) | 4 godla | 1 |
  | bbox arkusza `6.179.12.20` (PL-2000, `--scale 1:2000`) | 9 godel | 1 |
  | punkt / bbox zdegenerowany (<= ~2e-9 jednostki) | `[]` (PL-1992) / 4 godla (PL-2000) | 1 arkusz (ten na E/N od linii siatki) |

  Dziala tak samo na linii siatki i na granicy stref PL-2000. Dodatkowo
  nieznana wartosc `system=` konczy sie `ValidationError` zamiast cichego
  fallbacku do PL-1992. (audyt 0.7.0: A1-7, A9-1)
- **`get_parent()`/`get_children()`/`get_all_descendants()` i
  `parse --hierarchy` dla 1:1000000 <-> 1:500000: poprawna geometria
  cwiartek** — cwiartka jest liczona z pozycji arkusza 1:200000 w siatce
  12x12 (bloki 6x6: A = NW, B = NE, C = SW, D = SE), a nie z pasow po 36
  kolejnych numerow. 72 ze 144 arkuszy 1:200000 dostaje innego rodzica niz
  w 0.6.x, a `get_all_descendants()` arkusza 1:500000 zwraca wlasciwa cwiartke
  zamiast poziomego pasa. (audyt 0.7.0: A1-1)
- **HSG: kanoniczne progi trojkata USDA** (ADR-025) — skosne granice normy
  (`silt + 1.5*clay`, `silt + 2*clay`) zastapily przyblizenia liniami
  pionowymi/poziomymi, a reguly stoja w jednym miejscu, wiec
  `classify_usda_texture()` (skalar) i `classify_usda_texture_array()`
  (tablica, uzywana przez `calculate_hsg_by_bbox`) daja identyczne wyniki
  (rownowaznosc przypieta testem na calym symplexie co 1%). Skutek policzony
  na 5151 punktach symplexu, format "bylo -> jest":

  | zmiana HSG | punktow | udzial symplexu | zmiana tekstury |
  |---|---|---|---|
  | A -> B | 136 | 2,64% | `loamy_sand` -> `sandy_loam` |
  | C -> B | 85 | 1,65% | `sandy_clay_loam` -> `loam` (36), `sandy_clay_loam` -> `sandy_loam` (28), `clay_loam` -> `loam` (21) |
  | D -> C | 5 | 0,10% | `sandy_clay` -> `clay_loam` |
  | **razem** | **226** | **4,39%** | (klasa tekstury zmienia sie dla 427 punktow = 8,29%) |

  Kazda zmiana jest o dokladnie jedna grupe. `TEXTURE_TO_HSG` zostaje bez
  zmian (swiadome, teraz udokumentowane odstepstwo od TR-55 — patrz ADR-025).
  (audyt 0.7.0: A4-4, A4-8)
- **Auth proxy: usuniety endpoint `/token` i
  `AuthProxyClient.get_access_token()`** — oddawaly surowy token do procesu
  klienta, co przeczy roli proxy (izolacja credentials, ADR-002). Dodatkowo
  token trafia wylacznie do hostow `*.copernicus.eu` i `*.eea.europa.eu`:
  `/proxy` i `/download` przyjmuja tylko `https`, a `/proxy` odrzuca (403)
  kazdy host spoza tej listy (dotad proxy pobieralo z dowolnego URL-a
  podanego przez klienta). (audyt 0.7.0: A4-10)
- **Usuniety format `GML`** — `--format GML` (CLI), pozycja w
  `landcover list-sources` i wpis w `get_supported_formats()`; format nigdy
  nie byl zaimplementowany, zadanie i tak konczylo sie plikiem GPKG.
  (audyt 0.7.0: A6-2)
- **Fasada `cli/commands.py` nie re-eksportuje juz 9 nazw** — m.in.
  `cmd_landcover_download`, `cmd_landcover_list_layers`,
  `cmd_landcover_list_sources`, `cmd_soilgrids_hsg`; import z fasady konczy sie
  `ImportError`, kanoniczne sa moduly `cli/*_cmd.py` (szczegoly w Removed).
  (audyt 0.7.0: A5-1)
- **Zmiany zachowania widoczne dla skryptow** (tresc wpisow w Changed/Fixed):
  - pobranie hierarchii z porazkami konczy sie kodem 1, nie 0 (Fixed, A2-3);
  - `DownloadManager(provider=GugikNmptProvider())` bez `storage=` pisze do
    `nmpt/pl_<uklad>_1m_<vcrs>/`, nie do segmentu NMT (Fixed, A2-2);
  - domyslne `--country auto` doklada dla zadan w poludniowej Polsce plik
    i sidecar z CUZK (Changed, A6-3);
  - selekcja arkuszy z bboxa EPSG:2180 przecinajacego 19°E zwraca wiecej
    arkuszy (Fixed, poludnik osiowy).

### Added
- **Wycinek PL jako API biblioteki** (`kartograf.download.cutout`, eksport
  w `kartograf`): `download_pl_cutout(bbox, target_crs, ...)` — jeden scalony
  GeoTIFF NMT PL (arkusze GUGiK -> mozaika -> lokalny warp przypieta
  operacja), oraz kroki `prepare_pl_cutout` (fail-fast, bez sieci) /
  `select_pl_cutout_sheets` / `run_pl_cutout` i typy `PlCutout`,
  `PlCutoutSheets`, `PlCutoutResult`. CLI `--target-crs` dla PL jest nakladka
  na te funkcje. `run_pl_cutout` z wstrzyknietym providerem o innym pionie
  albo rozdzielczosci niz wycinek konczy sie `ValidationError` przed
  pobraniem (arkusze trafilyby do cudzego segmentu wspolnego cache).
- `DownloadManager.download_sheets(godla, ...)` i `DownloadManager.expand_sheets(godla)`
  — pobranie listy godel (grubsze PL-1992 rozwijane do 1:10000, duplikaty raz);
  porazki pojedynczych arkuszy zbierane w `last_result` (`failed`, `no_coverage`)
  zamiast przerywac cala liste.
- `NoCoverageError(DownloadError)` — zrodlo nie ma danych dla arkusza
  (wszystkie warstwy skorowidza odpowiedzialy); `DownloadResult.no_coverage`
  — podzbior `failed`.
- **`--target-crs` dla PL w trybie `--bbox`/`--geometry`** (ADR-027): jeden
  scalony wycinek `nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif` (mozaika
  arkuszy + crop + lokalny warp przypieta operacja; `EPSG:2180` = sam crop
  na siatce arkuszy, `transform: null`; awaria pobrania arkusza = kod 1,
  arkusz bez danych GUGiK = nodata — patrz Changed). W trybie `--geometry`
  wycinek obejmuje CALA obwiednie geometrii (bez maskowania do obiektow), a przy
  reprojekcji arkusze to SUMA godel geometrii i godel obwiedni z zapasem —
  obwiednia jest wiec wypelniona danymi, nie ramka `nodata` (koszt: przy
  rzadkiej geometrii wieloobiektowej pobieraja sie arkusze calej obwiedni).
  Na pograniczu `--country auto --target-crs` daje dwa wycinki PL+CZ ze
  wspolnym `extra.parent_request`. Wylaczenia (czytelne bledy): godlo,
  `--product nmpt|orto|laz`, `--system 2000`. Nieudana budowa wycinka NIE
  niszczy poprzedniego pliku wyniku — obie sciezki zapisu sa atomowe.
- `SourceDescriptor.resolve_subdir(uklad=, vertical_crs=)` — wypelnianie
  szablonu segmentu (czesciowe legalne; vcrs lowercased)
- `FileStorage(vertical_crs=)` — nowy parametr (default `"EVRF2007"`);
  `{uklad}` rozwiazywany per godlo (kropki=2000, myslniki=1992),
  nierozwiazany placeholder = `ValidationError` (pusty string liczy sie jako
  brak wymiaru, wiec tez konczy sie `ValidationError`, a nie segmentem
  `pl_1992_1m_`)
- `LazTile.uklad` i `FileStorage.get_raw_path(..., uklad=)` — API biblioteki
  daje ten sam segment co CLI, gdy wolajacy przekaze `uklad=tile.uklad`; bez
  tego (dotychczasowe wywolanie) uklad wynika z formatu godla, wiec kafel
  `PL-2000:*` z godlem myslnikowym nadal trafia do `laz/pl_1992_*` (review
  max, zn. 8)
- `kartograf.transform.raster.warp_to_grid` — lokalna reprojekcja rastra
  z wymuszona operacja przypieta (wzorzec ADR-024 dla torow PL)
- `mosaic_and_crop(dst_kwds=)` — wymuszenie sterownika/CRS wyniku
  (wejscia ASC bez CRS -> GeoTIFF z EPSG:2180)
- `mosaic_and_crop(snap_to_source_grid=, assign_crs=, dtype=)` — crop
  rozszerzany na zewnatrz do siatki pikseli zrodel (siatka wiekszosci; zrodlo
  spoza niej = ostrzezenie w logu) oraz owijanie kazdego zrodla w VRT
  z wymuszonym SRS i typem pasma (nodata wlasne zrodla; wynik domyslnie
  GTiff bez kafli). Domyslnie wylaczone — tor CZ bez zmian; uzywa ich wycinek
  PL (patrz Changed/Fixed)
- `docs/ARCHITECTURE.md` — kanoniczny opis architektury, kontraktow
  i ukladu `data/`
- **Etap 0 — architektura zrodel wielokrajowych (przygotowanie pod CZ/DE/SK)**
  - `kartograf/sources/` — deskryptory zrodel (SourceDescriptor, AccessChannel,
    TransportKind, LicenseInfo, CountryProfile) + rejestr (`get_source`,
    `sources_for`, `get_country`, `vertical_crs_code`); zero IO przy imporcie
  - **Sidecar metadanych**: po kazdym udanym pobraniu powstaje
    `<plik>.meta.json` (schema `kartograf-meta/1`: dataset, CRS-y, nodata,
    licencja, request, wersja) — kontrakt dla Hydrografa; blad zapisu sidecara
    nie przerywa pobrania
  - `kartograf/transform/crs.py` — twarda polityka transformacji:
    `TransformerGroup(allow_ballpark=False)`, filtr dokladnosci, probe
    odrzucajacy siatki obcych krajow (inf), kontrola isfinite,
    `TransformError`/`TransformUnavailableError` z remedium; `KNOWN_PATHS`
  - `kartograf/transport/` — `download_to()` (atomic write + retry) i
    `mosaic_and_crop()` (rasterio.merge + przyciecie, propagacja nodata)
  - `kartograf/core/parser_registry.py` — rejestr systemow godel (pl1992,
    pl2000); `SheetParser` i `FileStorage` deleguja do rejestru (wyniki
    identyczne)
  - `providers/pl/__init__.py`: fabryka `create_nmt_provider()` — jedno
    miejsce polskich domyslow NMT (w tym regula 5m => EVRF2007)
  - `FileStorage(subdir=...)` — opcjonalny podkatalog sterowany deskryptorem
  - `LandCoverProvider.download_by_admin_unit`/`validate_admin_unit`
    (kanoniczne) + `download_by_teryt`/`validate_teryt`/`source_url` jako
    dzialajace aliasy zgodnosciowe
  - CLI podzielone na moduly (`cli/_parser.py`, `parse_cmd.py`,
    `download_cmd.py`, `landcover_cmd.py`, `soilgrids_cmd.py`,
    `cache_cmd.py`); `cli/commands.py` zostaje fasada zgodnosci (entry point
    bez zmian)
- **Etap 1 — Czechy (CUZK)**
  - `providers/cuzk/` — `CuzkClient` (pierwszy silnik sterowany deskryptorem:
    `AccessChannel.endpoint`; `query()` z paginacja i filtrem nadmiarowego
    wyboru po stronie klienta, `export_image()` z kafelkowaniem 15000x4100 px
    + nadpisaniem CRS, `fetch_file()` z ZIP openzu → TIFF+TFW), `SheetIndex`/
    `SheetInfo`/`Sm5Sheet` (indeks arkuszy SM5/TM33 z KladyMapovychListu),
    `CuzkDmrProvider` + fabryka `create_dmr_provider` — DMR 5G/4G (CUZK),
    godla TM33/SM5, bbox przez exportImage, opcjonalna transformacja
    Bpv->EVRF2007 (EPSG:8357 -> EPSG:5621, przypieta operacja 0,1 m, offset
    +0,11..+0,15 m rosnacy S→N); endpointy wylacznie z deskryptorow, naprawa
    metadanych CRS w plikach DMR4G-TIFF i w wynikach exportImage
  - `core/parser_tm33.py` — `ParserTM33`: obliczalna siatka kafli TM33
    2x2 km (EPSG:3045, godlo `{E_km}_{N_km}` = naroznik SW), wzorowana na
    `Parser2000`; zarejestrowana w `parser_registry` jako `cz_tm33`/`cz_sm5`
    (przed fallbackiem pl1992)
  - `AccessChannel.endpoint` — nowe pole deskryptora: jedyne zrodlo URL-i dla
    silnikow sterowanych deskryptorem (CZ); kanaly PL maja `endpoint=""`
    (zrodlem prawdy pozostaja stale providerow z etapu 0)
  - `sources/registry.py`: deskryptory `cz.cuzk.dmr5g`/`cz.cuzk.dmr4g`,
    `CountryProfile` dla CZ (obwiednia prostokatna EPSG:4326), `all_countries()`
  - `MetadataCache`: nowa tabela `sheet_cache` (indeks SM5, TTL 30 dni —
    praktycznie staly); `cache stats` pokazuje tez liczbe wpisow Sheet
  - `sources/sidecar.build_metadata(capability=, nodata=)` — jawna selekcja
    kanalu po capability (zamiast wylacznie heurystyki bbox/nie-bbox) i jawne
    nadpisanie `nodata` (potrzebne, bo usluga `exportImage` CUZK zwraca
    `noDataValue: null` na poziomie ImageServera)
  - `DownloadManager(sidecar_extra=...)` — addytywny parametr konstruktora:
    dodatkowe pola scalane do `extra` kazdego sidecara (uzyty przez CLI PL w
    trybie bbox/geometry do wpiecia `parent_request`, patrz nizej)
  - CLI `--country {pl,cz,auto}` z auto-podzialem bboxa/geometrii
    transgranicznej: obszar trafia do zrodel KAZDEGO przecietego kraju (w trybie
    auto przyciety do jego obwiedni), a opcje nierozwiazywalne dla ktoregos
    z krajow (dzis np. `--resolution 2m` albo `--vertical-crs Bpv` na obszarze
    siegajacym PL) sa odrzucane PRZED pobraniem, z podpowiedzia jawnego
    `--country`. Pierwotne odrzucanie opcji tylko-PL (`--resolution 1m`,
    `--system`) i `--target-crs` z PL jest ZASTAPIONE: opcje tylko-PL
    rozstrzygaja `auto` do `pl` (audyt 0.7.0, ADR-023 pkt 5), a `--target-crs`
    dziala po obu stronach granicy (ADR-027)
  - CLI `--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}` — reprojekcja wyniku CZ
    w trybie `--bbox`/`--geometry`, wykonywana lokalnie przypieta operacja
    (pierwotnie serwerowo przez `imageSR`; zmienione fixem ADR-024 — patrz
    Changed/Fixed nizej); godlo + `--target-crs` = blad (ADR-023 (f) pkt 2;
    dla PL — wylaczenia w pozycji `--target-crs` dla PL wyzej);
    `--vertical-crs {Bpv,EVRF2007,KRON86}` rozszerzone o CZ
  - `extra.parent_request` w sidecarach trybu bbox/geometry (oryginalny bbox
    zadania, jego uklad i **probowane** — niekoniecznie pobrane — kraje) —
    grupowanie plikow jednego zadania, takze po obu stronach granicy; tryb
    godlowy sidecarow nie zmienia (nigdy nie dostaje `parent_request`), a tor
    `--product laz` ma wlasny przeplyw i niesie w `extra` pola kafla
    (backlog)
  - `--product laz` w trybie obszarowym `--country auto`: obszar siegajacy CZ
    konczy sie bledem z podpowiedzia `--country pl` (bez cichego pomijania kraju)
- **Nowy produkt: LAZ — chmury punktow LIDAR (dane pomiarowe ALS) z GUGiK**
  - `GugikLazProvider` (`kartograf/providers/pl/gugik_laz.py`) — pobieranie plikow
    `.laz` przez **WFS** (`DanePomiaroweLidarEVRF2007` / `DanePomiaroweLidarKRON86`)
  - Discovery **area-based**: godlo (<=1:10000) / `--bbox` / `--geometry` → bbox
    EPSG:2180 → `discover_tiles()` (WFS GetFeature) → pobranie wszystkich kafli
  - Kafle LAZ sa drobniejsze niz 1:10000 (jedno godlo 1:10000 → wiele kafli);
    godlo kafla jest **nieparsowalne** i traktowane jako etykieta — `url_do_pobrania`
    bierzemy wprost z atrybutu WFS, bez konstruowania URL i bez `SheetParser`
  - WFS zwraca metadane: rok (`akt_rok`), gestosc (`char_przestrz`), CRS, geometria
  - Domyslnie: EVRF2007, **najnowszy rok per kafel** (dedup po godle); flagi
    `--year`, `--vertical-crs`, `--min-density` do nadpisania
  - CLI: `kartograf download <godlo|--bbox|--geometry> --product laz [...]`,
    pobieranie rownolegle (`--workers`), pomijanie istniejacych plikow
  - `GugikLazProvider._fetch_available_years()` / `_get_available_years()` —
    lista lat z WFS GetCapabilities, in-memory cache, fallback na hardcoded
  - `FileStorage.get_raw_path()` — sciezka dla nieparsowalnego (drobnego) godla
    bez `SheetParser`; pliki w
    `laz/pl_<uklad>_<vcrs>/<hierarchia godla>/<oryginalna nazwa>.laz`
  - Eksport: `GugikLazProvider`, `LazTile` w `kartograf/__init__.py`
  - Weryfikacja: pobrano realne pliki LAZ (magic `LASF`) E2E; 41 nowych testow
- **Walidacja warstw WMS przez GetCapabilities dla Ortofotomapy**
  - `GugikOrtoProvider._fetch_wms_layers()` i `_get_validated_layers()` — analogicznie
    do GugikProvider; dotad orto NIE mialo zadnego fallbacku (twarda lista)
  - Lazy, in-memory cache per instancja; graceful fallback do `WMS_LAYERS` przy bledzie
  - Filtruje prefiks `SkorowidzeOrtofotomapy`, wyklucza warianty `Zasiegi`,
    sortuje malejaco po roczniku (warstwa `Starsze` na koncu)
- **Audyt przedwydaniowy 0.7.0**
  - `DownloadManager.last_result` — podsumowanie `DownloadResult` (succeeded /
    failed / skipped / no_coverage) ostatniego `download_hierarchy()` /
    `download_sheets()`; kasowane na wejsciu do `download_sheet()`,
    `download_hierarchy()` i `download_sheets()`, wiec nigdy nie oddaje
    wyniku poprzedniego zadania. CLI ustala z niego kod wyjscia (A2-5)
  - `CLMS_CREDENTIALS` jest wreszcie czytane: zmienna srodowiskowa trafia do
    podprocesu auth proxy (env przed Keychain), wiec CORINE GeoTIFF dziala
    takze na Linux i Windows — dotad jedynym dzialajacym zrodlem byl Keychain
    macOS (A4-1)
  - `KARTOGRAF_DEBUG=1` — pelny traceback zamiast skroconego komunikatu bledu
    CLI (patrz Fixed: bariera w `main()`) (N1-1)
  - `--country auto` rozstrzyga sie do `pl` z komunikatem `Info:` na stderr,
    gdy obszar lezy w obwiedniach obu krajow, a podane opcje nie maja
    odpowiednika czeskiego (`--product nmpt|orto`, `--system`,
    `--vertical-crs KRON86`, `--resolution 1m`) — patrz Changed
    (N6-2, ADR-023 pkt 5)
  - `--bbox-crs` przyjmuje takze `EPSG:5514` (S-JTSK, natywny uklad CZ)
    i `EPSG:3045` (ETRS89 / UTM 33N, siatka TM33) — dotad w CHANGELOG-u
    wymienione byly tylko uklady polskie (A6-16)

### Changed
- Wycinek `--target-crs EPSG:2180` lezy na siatce pikseli arkuszy GUGiK:
  obszar zadania rozszerzony na zewnatrz o < 1 px, wartosci 1:1 z arkuszy
  (bez przeprobkowania, `transform: null`); nazwa pliku niesie wspolrzedne
  zadania. Selekcja arkuszy wycinka (`select_pl_cutout_sheets`) ma zapas
  1 piksela (tryb bbox i suma R-01), zeby crop przyciagniety na zewnatrz nie
  siegal arkusza spoza listy; `--geometry` z `EPSG:2180` (bez sumy R-01) tego
  zapasu nie ma — skrajna kolumna albo wiersz wyniku moze tam byc nodata
  (`docs/ARCHITECTURE.md` 4.3). Arkusz wydany przez skorowidz GUGiK
  w ukladzie PL-2000 pod godlem PL-1992 konczy budowe wycinka (kazdego
  `--target-crs`) bledem z opisem (dotad: cicha dziura nodata).
- Wycinek PL: arkusz bez danych GUGiK (`NoCoverageError`) daje nodata +
  `Warning:` + `extra.missing_sheets` w sidecarze zamiast kodu 1; awarie
  pobrania nadal koncza sie kodem 1. Na pograniczu `--country auto
  --target-crs` powstaje teraz takze wycinek PL. API biblioteki: lista
  w `PlCutoutResult.missing_sheets`; obszar, dla ktorego danych nie ma zaden
  arkusz, konczy sie `ValidationError` (ADR-027, uzupelnienie R5).
- Wycinek PL: plik posredni mozaiki przy warpie jest kompresowany (deflate,
  kafle 512 px, BigTIFF gdy trzeba); przed pobraniem kontrola miejsca na
  dysku (dolne oszacowanie: wynik + arkusze do pobrania) i `Info:` dla
  wycinkow >= 1 GiB. Twardego limitu rozmiaru nie ma.
- `FileStorage` bierze szablony segmentow z deskryptorow rejestru zamiast
  wlasnych kopii (jedno zrodlo prawdy, ADR-026; review max, zn. 11).
- Czesciowa awaria warstw skorowidza GUGiK przy braku arkusza w pozostalych
  to teraz "brak pokrycia niepewny" (`DownloadError`), nie brak pokrycia;
  URL innego arkusza z fallbacku skorowidza loguje ostrzezenie (arkusze
  PL-2000 pod godlem PL-1992).
- `DownloadManager` bierze uklad pionowy segmentu z PROVIDERA, nie z wlasnej
  flagi `vertical_crs=` — `DownloadManager(provider=GugikProvider(
  vertical_crs="KRON86"))` pisal dotad do `nmt/pl_1992_1m_evrf2007/` obok
  sidecara deklarujacego `EPSG:9650` (dotyczy API biblioteki, nie CLI)
- Wycinki `--bbox` CZ trafiaja do `<output>/<subdir>/bbox/<coords>.tif`
  (np. `data/nmt/cz_dmr5g_bpv/bbox/-447000_-1114000_-446000_-1113000.tif`)
  zamiast plasko do korzenia katalogu wyjsciowego z podkatalogiem w nazwie
  pliku (`cz_dmr5g_<coords>.tif`) — kazdy inny bbox to nowy plik, wiec plaski
  uklad zasmiecal korzen `data/`; uklad plaski nigdy nie zostal wydany
  (oba warianty tylko w 0.7.0-dev) (segment wg ADR-026)
- LAZ: segment storage wyznaczany per kafel z `uklad_xy`
  (`laz/pl_<uklad>_<vcrs>/`); fallback: format godla, ostatecznie `2000`
  z ostrzezeniem w logu
- CLI: sentinele `None` dla `--resolution`/`--vertical-crs`/`--system`
  rozwiazywane dopiero po ustaleniu kraju docelowego (PL: 1m/EVRF2007/1992
  bez zmian; CZ: 2m/Bpv, `--system` nie dotyczy) — zamiast twardo zakodowanych
  domyslnych PL, ktore nie mialy sensu dla CZ
- `PinnedTransform.transform` (`transform/crs.py`) jest teraz **polimorficzne**
  — przyjmuje skalary LUB tablice `numpy` (`np.isfinite` zamiast
  `math.isfinite`, ktory rzucal `TypeError` na `numpy.ndarray`); potrzebne do
  transformacji pionowej calego rastra per-piksel (DMR CZ → EVRF2007)
- `build_pinned_transform`: probe na punkcie kontrolnym wykonywany teraz
  **wewnatrz** kontekstu `network.set_network_enabled(...)`, nie po jego
  przywroceniu (poprawka semantyki "probe pod polityka sieci" odroczonej
  z etapu 0)
- Sidecary PL w trybie `--bbox`/`--geometry` (takze `--country pl`/`auto`)
  dostaja teraz dodatkowo `extra.parent_request` — nowe pole, tresc
  pozostalych pol bez zmian; wspolny klucz grupowania z sidecarami CZ dla
  tego samego zadania (poza `--product laz`, ktory ma wlasny przeplyw
  i niesie w `extra` pola kafla — backlog)
- **Sidecary CZ: `transform.horizontal` niesie operacje przypieta zamiast
  serwerowej** (ADR-024) — `"pinned: <opis operacji> (<dokladnosc> m)"`,
  symetrycznie do `transform.vertical`, zamiast `"server:EPSG:<kod>"` bez pola
  dokladnosci. Pole pojawia sie takze dla kafli TM33 pobranych godlem, ktore
  dotad mialy `transform: null` (kafel lezy w EPSG:3045, a dane CUZK w
  EPSG:5514 — reprojekcja zachodzi i jest teraz opisana). Sciezka SM5
  (DMR 4G, pliki openzu w 5514) nadal ma `transform` bez czesci poziomej.
- `PinnedTransform` niesie pare ukladow (`src_crs`/`dst_crs`) i udostepnia
  `gdal_operation()` — te sama operacje jako pipeline PROJ dla GDAL-owego
  `COORDINATE_OPERATION`, z korekta kolejnosci osi (cel northing-first bez
  `axisswap` daje raster w calosci nodata)
- `import kartograf` laduje teraz eagerly `rasterio` (GDAL/PROJ bindings) —
  eksporty CZ w `__init__.py` importuja `providers/cuzk/client.py`, ktory
  importuje `rasterio` na poziomie modulu; zmierzony koszt +55–65 ms
  (~185 ms → ~244 ms). Zepsuty GDAL/PROJ (np. brakujaca biblioteka natywna)
  psuje teraz sam `import kartograf`, nie dopiero pierwsze wywolanie funkcji
  rastrowej — istotne dla Hydrografu/Hydrologu, ktore importuja Kartograf
  jako zaleznosc (patrz ADR-023, "Ustalenia dodatkowe" pkt 2)
- **`pyproject.toml`: wersja dynamiczna z `kartograf.__version__`** —
  usuniety rozjazd `version = "0.6.1"` (pyproject) vs `__version__ =
  "0.7.0-dev"` (`kartograf/__init__.py`); teraz jedno zrodlo prawdy
  (`dynamic = ["version"]` + `[tool.setuptools.dynamic] version = {attr =
  "kartograf.__version__"}`); `[tool.setuptools.packages.find]` dostaje
  `include = ["kartograf*"]`, wiec `tests/` nie trafia do dystrybucji;
  opis i keywords rozszerzone o CUZK/DMR/LAZ; usuniete `requirements.txt`
  i `requirements-dev.txt` — jedynym zrodlem zaleznosci jest `pyproject.toml`
  (audyt 0.7.0: A6-4, A6-5, A6-6)
- **`pyproject.toml`: licencja jako wyrazenie SPDX (PEP 639)** — `license =
  "MIT"` + `license-files = ["LICENSE"]` zamiast tabeli `{text = "MIT"}`;
  klasyfikator `License :: OSI Approved :: MIT License` usuniety (przestarzaly
  przy SPDX); `authors` z prawdziwymi danymi zamiast placeholdera. Floor
  build-systemu podniesiony do `setuptools>=77.0.3` (pierwsza wersja
  poprawnie obslugujaca PEP 639; `wheel` usuniety z `requires` — zbedny od
  setuptools 70). Konsekwencje: build bez izolacji wymaga setuptools >= 77;
  dystrybucje maja teraz `Metadata-Version: 2.4` z `License-Expression: MIT`
  i plikiem LICENSE w `dist-info/licenses/` — upload na PyPI wymaga
  twine >= 6.x. Zweryfikowane buildem sdist+wheel
- **Domyslnym krajem jest `--country auto`** — NOWA semantyka wzgledem 0.6.1,
  gdzie opcji `--country` nie bylo i kazde zadanie szlo do GUGiK-a. Dla
  `--bbox`/`--geometry` bez jawnego `--country` znaczy to:
  - obszar przecinajacy obwiednie dwoch krajow jest pobierany z KAZDEGO z nich
    (osobne pliki i sidecary, wspolny `extra.parent_request`);
  - obwiednia CZ jest PROSTOKATNA (siega 18,86 E i 51,06 N), wiec zadanie
    z poludniowej Polski dostaje dodatkowo plik i sidecar z CUZK; poza
    faktyczna granica wyjdzie raster same-nodata, a nie blad — obejscie to
    jawne `--country pl`;
  - opcje bez odpowiednika czeskiego (`--product nmpt|orto`, `--system`,
    `--vertical-crs KRON86`, `--resolution 1m`) ROZSTRZYGAJA kraj do `pl`
    (`Info: --country auto -> pl (...)` na stderr, `-q` tego nie tlumi)
    zamiast przewracac zadanie kodem 1 — dotychczasowe odrzucenie bylo
    regresja wzgledem 0.6.1 w calej poludniowej Polsce.

  (audyt 0.7.0: A6-3, N6-2; ADR-023 pkt 4-5)
- Auto-split `--country auto`: porazka jednego kraju przy sukcesie drugiego
  konczy sie kodem 0 i `Warning: nie pobrano danych z <kraj> ...` na stderr
  (tresc neutralna: brak pokrycia albo awaria zrodla) — bylo:
  kod 1 mimo pobranych plikow. Kod 1 zostaje dla jawnego `--country` i dla
  przypadku, w ktorym padly wszystkie kraje. (audyt 0.7.0: A3-2, ADR-023 pkt 4)
- `mosaic_and_crop()` pisze wynik przez `merge(dst_path=...)` zamiast trzymac
  scalona tablice w RAM — szczyt zuzycia pamieci spada z ~2,6x do ~1,06x
  rozmiaru rastra wynikowego (istotne dla duzych bboxow CZ).
  (audyt 0.7.0: A3-4)
- Statystyki HSG (`soilgrids hsg --stats`) licza powierzchnie geodezyjnie dla
  rastrow w EPSG:4326 — bylo: pole liczone w stopniach kwadratowych, wiec CLI
  pokazywalo `0.00 ha`. (audyt 0.7.0: A4-6)
- Listy godel rozwijanych do hierarchii w trybie `--bbox`/`--geometry` sa
  pobierane sekwencyjnie (rownoleglosc zostaje wewnatrz kazdej hierarchii),
  zeby dalo sie zebrac `last_result` kazdego godla; znika przy okazji
  zwielokrotnienie watkow (dotad do `--workers`^2 rownoczesnych zadan do
  GUGiK-a). (audyt 0.7.0: A2-3)
- Teksty `--help` opisuja CZ/CUZK, warstwy SW w BDOT10k, SoilGrids, LAZ, HSG
  i `sheet_cache` — dotad milczaly o czesci zaimplementowanych funkcji.
  (audyt 0.7.0: A6-13)

### Removed
- Martwy kod wykryty w audycie przedwydaniowym: blok Keychain/CLMS
  w `providers/corine.py` (`KEYCHAIN_SERVICE`, `get_credentials_from_keychain`,
  `save_credentials_to_keychain`, `get_clms_credentials` — credentials
  z `CLMS_CREDENTIALS` konsumuje wylacznie podproces auth proxy),
  `CorineProvider.DLR_YEARS` oraz 9 nieuzywanych re-eksportow z fasady
  `cli/commands.py` (`_cmd_download_bbox`, `_cmd_download_geometry`,
  `_cmd_download_laz`, `_download_godlo_list`, `_write_laz_sidecar`,
  `cmd_landcover_download`, `cmd_landcover_list_layers`,
  `cmd_landcover_list_sources`, `cmd_soilgrids_hsg`) — cztery ostatnie sa
  publiczne, wiec import z fasady konczy sie teraz `ImportError` (patrz
  Breaking Changes). W fasadzie zostaja `main`, `create_parser` i piec
  dispatcherow komend (`cmd_parse`, `cmd_download`, `cmd_landcover`,
  `cmd_soilgrids`, `cmd_cache`) oraz dotychczasowe helpery formatujace.
  (audyt 0.7.0: A5-1)
- Nieosiagalna galaz `--product laz` w dyspozycji obszarowej `download_cmd.py`
  (LAZ ma wlasny przeplyw `_cmd_download_laz`) i martwe fallbacki
  `getattr(args, "vertical_crs", "KRON86")`. (audyt 0.7.0: N5-1)
- Format `GML` (`--format`, `landcover list-sources`, `get_supported_formats()`)
  — patrz Breaking Changes. (audyt 0.7.0: A6-2)

### Fixed
- **Reprojekcja tresci CZ szla przez serwer CUZK i gubila transformacje datum**
  (ADR-024). `--target-crs EPSG:2180` zwracal raster przesuniety o **135 m**
  (dE 119, dN 64,5 — `exportImage&imageSR=2180` traktowal S-JTSK jak ETRS89),
  a domyslna sciezka godlowa TM33 (`imageSR=3045`) — o **1,25 m** na poludnie
  (errata 2026-09-29: te 1,25 m — i 4,92 m w zachodnich Czechach —
  odpowiadaja roznicy operacji EPSG:1622 - EPSG:4829, wiec najpewniej to
  lokalna, slowacka operacja przypieta przesuwa tresc CZ; ADR-024, errata).
  Zaden z tych bledow nie byl widoczny w metadanych: zasieg, CRS, rozdzielczosc
  i nodata byly poprawne, a sidecar niosl tylko `transform.horizontal =
  "server:EPSG:<kod>"` bez dokladnosci. Kontrola przypietych transformow
  obejmowala wylacznie obwiednie zadania (zgodna do 0,07 m) — tresc pikseli
  szla obok niej.
  Serwer dostaje teraz zadania **wylacznie w ukladzie natywnym `EPSG:5514`**,
  a reprojekcje wykonuje `rasterio.warp` z **wymuszonym** pipeline'em
  przypietej operacji (`COORDINATE_OPERATION`) — dla obu sciezek rastrowych.
  Kafelkowanie i mozaikowanie zostaja po stronie natywnej (przed warpem), wiec
  szwy kafli nie sa utrwalane przez interpolacje; nodata nie wchodzi do
  interpolacji, zapis pozostaje atomowy, a zasieg i rozmiar wyniku sa
  identyczne jak dotad. Brak bezpiecznej operacji poziomej przerywa teraz
  w konstruktorze providera, przed transferem.
- CLI z `--resolution 5m --vertical-crs KRON86` tworzy teraz provider skorygowany
  do EVRF2007 przez fabryke `create_nmt_provider` (wczesniej provider dostawal
  niewspierana kombinacje). Skorygowana wartosc jest tez przekazywana do
  `DownloadManager`, wiec ostrzezenie o zmianie ukladu pionowego pojawia sie
  raz, a nie dwa razy.
- Sidecar CORINE na sciezce fallbacku PNG (brak credentials CLMS) deklaruje
  faktyczny CRS podgladu WMS — `EPSG:3857` (EEA Discomap) lub `EPSG:4326`
  (DLR, rok 1990) — zamiast `EPSG:3035` wlasciwego wylacznie dla GeoTIFF z
  CLMS; dochodzi `extra.fallback = "wms_png"` z adnotacja "podglad WMS, nie dane".
- `FileStorage.delete()` usuwa takze sidecar `.meta.json` pliku danych
  (wczesniej zostawal osierocony).
- **NMT 1m/EVRF2007: zaktualizowane nazwy warstw WMS (nowe roczniki)**
  - `WMS_LAYERS["1m"]["EVRF2007"]`: `[2025, 2024, 2023, 2022iStarsze]` →
    `[2026, 2025, 2024, 2023iStarsze]`
  - Dodana brakujaca warstwa `SkorowidzeNMT2026`
  - Usuniete nieistniejace juz warstwy `SkorowidzeNMT2023` i `SkorowidzeNMT2022iStarsze`
    (GetFeatureInfo zwracalo "Invalid layer(s) given in the LAYERS parameter")
  - Zweryfikowane przez GetCapabilities endpointu `SkorowidzeUkladEVRF2007` (2026-06-24)
  - Wykryte podczas rozpoznania danych dla godla M-34-27-B-b-1-2 (Kielchinow)
  - `1m/KRON86` (`SkorowidzeUkladKRON86`) i `5m/EVRF2007` (`SheetsGrid5mEVRF2007`)
    zweryfikowane — bez zmian; endpoint 5m nadal udostepnia starsze roczniki
    (`[2025, 2024, 2023, 2022iStarsze]`) i nie zostal przesuniety do 2026 jak 1m
  - Mechanizm `_get_validated_layers()` (GetCapabilities + fallback z v0.6.1) i tak
    auto-korygowal te liste w runtime; aktualizacja usuwa rozbieznosc i warning
- **Ortofotomapa: naprawione i odswiezone nazwy warstw WMS**
  - `WMS_LAYERS` (GugikOrtoProvider): `[2025, 2024, 2023, 2022, 2021, 2020, 2019,
    2018, Starsze]` → `[2026, 2025, 2024, Starsze]`
  - GUGiK skonsolidowal starsze warstwy rocznikowe (2023..2018) w jedna
    `SkorowidzeOrtofotomapyStarsze` — zapytania o usuniete warstwy zwracaly
    "Invalid layer(s) given in the LAYERS parameter"; brakowalo tez `2026`
  - Zweryfikowane przez GetCapabilities endpointu `SkorowidzeWgAktualnosci` (2026-06-24)
  - Warstwy `SkorowidzeOrtofotomapyZasiegi*` (zasiegi, bez URL OpenData) sa pomijane
- **Kafelkowanie `exportImage` (CZ) gubilo wiersz i przesuwalo tresc** —
  kafle sa teraz kotwiczone w narozniku NW zadania, wiec ostatni wiersz
  mozaiki nie jest juz wypelniony `-9999`, a przesuniecia tresci miedzy
  kaflami (dotad -1,4 .. +0,6 m) mieszcza sie w 1 px. (audyt 0.7.0: A3-1)
- Uszkodzony kafel `exportImage` konczy sie `DownloadError` (z posprzatanym
  plikiem wynikowym) zamiast wyjatku rasterio wyciekajacego do uzytkownika.
  (audyt 0.7.0: A3-3)
- **Kazde pobranie CZ padalo na `inf`, jesli w systemie byla lokalna siatka
  `sk_gku`** — polityki poziome CZ nie przekazywaly `probe_point`, wiec filtr
  transformacji nie odrzucal operacji zwracajacej `inf` poza obszarem waznosci
  siatki obcego kraju. (audyt 0.7.0: A1-2)
- Transformacja pionowa odrzuca raster bez geotransformacji zamiast cicho
  przesuwac wysokosci o wartosc policzona dla wspolrzednych pikselowych.
  (audyt 0.7.0: A3-5)
- `MetadataCache`: odczyty ida pod tym samym lockiem co zapisy — rownolegle
  odczyty na wspoldzielonym polaczeniu SQLite potrafily oddac wiersz innego
  klucza (URL innego godla). (audyt 0.7.0: A2-1)
- `DownloadManager(provider=...)` bez jawnego `storage=` bierze podkatalog
  z deskryptora providera; bylo: zawsze segment NMT 1m, wiec NMPT pisal do
  katalogu NMT i przy `--force` nadpisywal jego pliki. (audyt 0.7.0: A2-2)
- Pobranie hierarchii z porazkami konczy sie kodem 1 i komunikatem
  `Error: N of M sheets failed` — bylo: kod 0 mimo brakujacych arkuszy; dotyczy
  trybu godlowego oraz `--bbox`/`--geometry`. (audyt 0.7.0: A2-3)
- `Bdot10kProvider` zwraca sciezke faktycznie zapisanego pliku `.gpkg`
  (dotad deklarowana sciezka rozjezdzala sie z zapisana, wiec sidecar ladowal
  obok nieistniejacego pliku). (audyt 0.7.0: A2-6)
- Awaria wszystkich warstw WMS jest raportowana jako niedostepnosc uslugi,
  a nie jako "brak pokrycia dla godla" — bledna diagnoza kierowala uzytkownika
  w zla strone. (audyt 0.7.0: A2-9)
- CLI odrzuca `--product nmpt --resolution 5m` oraz `--product orto
  --vertical-crs ...` zamiast cicho je ignorowac (wynik nie odpowiadal
  poleceniu). (audyt 0.7.0: V2-N1)
- `--geometry`: punktowe SHP daja bbox zdegenerowany zamiast `AttributeError`;
  GPKG bez obwiedni w naglowku czyta punkt z WKB (takze warianty Z/M i EWKB
  z flaga SRID), pusta geometria jest pomijana, a nieobslugiwany typ konczy
  sie `ValidationError` zamiast cichego pominiecia rekordu.
  (audyt 0.7.0: A1-3, A1-5)
- SoilGrids i CORINE: obwiednia bboxa liczona przez `transform_bounds()`
  zamiast dwoch naroznikow — zamawiany obszar byl o ~10% za waski; CORINE
  liczy tez proporcje obrazu WMS zawsze z obwiedni metrycznej (galaz DLR
  dla roku 1990 tracila 1,7x rozdzielczosci pionowej). (audyt 0.7.0: A4-7)
- HSG: piksele nodata (`-32768`, `NaN`, wartosc nodata rastra) dostaja 0
  ("brak danych"), a nie grupe B — dziury w danych wygladaly dotad jak
  poprawna klasyfikacja. (audyt 0.7.0: A4-5)
- Auth proxy i klient: urwany strumien nie dokleja juz odpowiedzi 502 do ciala
  pobieranego rastra (pobranie bez `Content-Length` jest ramkowane jako
  chunked, bajty ida surowe), a `download_file()` pisze przez plik tymczasowy
  i sprawdza `Content-Length`, wiec urwane pobranie nie udaje sukcesu — bylo:
  `True` i uszkodzony GeoTIFF. (audyt 0.7.0: A4-2)
- `AuthProxyClient`: start proxy pod lockiem (rownolegly CORINE mieszal
  GeoTIFF z PNG), pod tym samym lockiem powstaje tez sam singleton, a uchwyt
  do podprocesu i watek drenujacy stderr sa stanem KLASOWYM — dwa watki nie
  wystartuja juz dwoch proxy; po `kill()` podproces jest odbierany (`wait`,
  bez zombie), a strumieniowana odpowiedz `/download` zamykana; brak
  credentials nie uruchamia juz podprocesu, odczyt portu ma timeout, a stderr
  podprocesu jest drenowany (pelny bufor blokowal proxy).
  (audyt 0.7.0: N4-1, A4-10 czesciowo, A4-11, A4-13, A4-14)
- Auth proxy `/download`: host `https` spoza allowlisty jest forwardowany
  BEZ naglowka `Authorization`, zamiast konczyc sie 403 — presigned
  `DownloadURL` z CLMS bywa na hoscie CDN poza `*.copernicus.eu`, a tokenu
  tam nie potrzeba; token nadal nie opuszcza allowlisty, a schemat inny niz
  `https` dalej konczy sie 403. (audyt 0.7.0: A4-10)
- Deskryptory CZ maja `server_reprojection=False` — pole opisuje stan
  faktyczny po ADR-024 (serwer CUZK dostaje wylacznie uklad natywny).
  (audyt 0.7.0: A1-6)
- `main()` ma bariere na wyjatki: blad spoza `KartografError` konczy sie
  linia `Error: <Typ>: <komunikat>` z podpowiedzia `KARTOGRAF_DEBUG=1`
  i kodem 1, zamiast tracebackiem Pythona. (audyt 0.7.0: N1-1)
- **Wycinek PL z >1024 arkuszy konczyl sie "Too many open files" dopiero po
  pobraniu** (review max, zn. 3). `mosaic_and_crop` otwieral wszystkie zrodla
  naraz; teraz metadane czyta po jednym pliku, a `merge` dostaje sciezki
  i otwiera zrodla leniwie (limit deskryptorow: Linux 1024, macOS 256).
- **Selekcja arkuszy PL-1992 z bboxa EPSG:2180 gubila pas przy gornej
  krawedzi bboxa na poludniku 19°E.** Obwiednia WGS84 liczona z 4 naroznikow
  pomijala maksimum szerokosci geograficznej lezace na poludniku osiowym
  PUWG 1992; dla bboxa szerokiego na 20 km pomijanych bylo 6 arkuszy
  przecinajacych bbox (pas ~63 m przy 50 km). Naprawa wprowadza tez znana
  nadmiarowa selekcje: obwiednia WGS84 jest SZERSZA niz przeciecie bboxa
  w EPSG:2180, wiec moga pojawic sie arkusze spoza bboxa (zmierzone: +4
  arkusze dla bboxa uzytego w testach tego zadania). Dotyczy
  `find_sheets_for_bbox`/`find_sheets_for_geometry` z bboxem w EPSG:2180
  (`--system 2000` uzywa osobnej obwiedni w `parser_2000` — nie objete tu,
  patrz backlog).
- **Wycinek PL przesuwal tresc o ulamek piksela** (review max, zn. 1): crop
  mozaiki kotwiczony w rogu zadania + kopiowanie najblizszym sasiadem. Arkusze
  GUGiK maja narozniki pikseli w polowie miedzy wielokrotnosciami piksela
  (5 m: na 5k + 2,5 m, zmierzone na 1977 arkuszach; 1 m: na k + 0,5 m —
  potwierdzone na zywo 2026-09-29 na 84 arkuszach; czesc arkuszy 5 m
  kampanii 2022 ma inna faze, patrz ADR-027), wiec problem dotyczyl takze bboxow
  o CALKOWITYCH wspolrzednych (np. wielokrotnosci 5 m przy 5 m: 0,5 px =
  2,5 m, z mieszaniem sasiednich kolumn). Crop jest teraz przyciagany do
  siatki arkuszy. **Wycinki zbudowane wczesniejsza wersja 0.7.0-dev przebuduj
  z `--force`** (maja te same nazwy plikow, wiec bez tego zostalyby pominiete
  jako istniejace). `--force` pobiera ponownie takze arkusze; tanszy wariant:
  usun stary plik wycinka i uruchom komende bez `--force` — arkusze z cache
  zostana uzyte ponownie.
- Mozaika wycinka PL: arkusz ASC z samymi liczbami calkowitymi, gdy trafil na
  poczatek listy zrodel (przy pobieraniu rownoleglym: kolejnosc ukonczenia
  pobran), zamienial cala mozaike w Int32 (obcinajac wysokosci pozostalych
  arkuszy), a arkusze z plikiem `.prj` (np. dopisanym przez Hydrograf) obok
  arkuszy bez niego konczyly sie bledem `niezgodne CRS wejsc`. Arkusze sa
  teraz owijane w VRT z jawnym EPSG:2180 i Float32, a lista zrodel jest
  sortowana.
- Plik geometrii w ukladzie czeskim (EPSG:5514/3045) z `--country pl|auto`:
  obwiednia opuszcza Krovaka przypieta operacja (jak `--bbox`), nie
  domyslnym transformerem — dotad siatka i nazwa wycinka PL byly przesuniete
  o ~1,2 m (review max, zn. 4). `parent_request.bbox_crs` niesie wtedy uklad
  pliku.
- Nieudany wycinek CZ (bbox) i nieudana budowa wycinka PL nie zostawiaja
  pustych katalogow `<segment>/bbox/` (review max, zn. 10).
- `SourceDescriptor.resolve_subdir(vertical_crs='')` (takze przez
  `DownloadManager` z providerem o pustym `vertical_crs`) konczy sie
  `ValidationError` zamiast cichego segmentu `nmt/pl_1992_1m_` (review max,
  zn. 7).
- Skorowidz GUGiK: odpowiedz bez URL arkusza, ktorej tresc to raport wyjatku
  OGC (`ServiceExceptionReport`, `ows:ExceptionReport` — serwery WMS, np.
  MapServer, zwracaja go z HTTP 200, np. `LayerNotDefined` dla nieaktualnej
  nazwy warstwy, gdy GetCapabilities sie nie udal), liczy sie jako nieudane
  zapytanie tej warstwy, a nie jako brak arkusza. Dotad, gdy tak
  odpowiedzialy wszystkie warstwy, powstawal `NoCoverageError`, czyli pod R5
  nodata + `extra.missing_sheets` w wycinku, ktory kolejne przebiegi pomijaja
  jako istniejacy; teraz wszystkie warstwy -> "unavailable", czesc -> "brak
  pokrycia niepewny" (`DownloadError`, kod 1). URL w odpowiedzi nadal wygrywa;
  strona bledu z HTTP 200 bez znacznikow OGC nadal liczy sie jako brak arkusza
  (sprawdzone na zywo 2026-09-29: pusta odpowiedz skorowidza to szablon HTML
  MapServera bez znacznikow OGC, a zla warstwa — HTTP 200 `text/xml`
  z `LayerNotDefined`). (finalny review fali review max, I-2)
- API wycinka PL (`prepare_pl_cutout`, `download_pl_cutout`): bbox w ukladzie
  czeskim z etykieta malymi literami albo ze spacjami (`"epsg:5514"`) opuszcza
  Krovaka przypieta operacja, jak `"EPSG:5514"` — dotad szedl po cichu
  domyslnym transformerem (bbox 1 x 1 km pod Cieszynem: obwiednia przesunieta
  o 1,06 m). CLI nie bylo dotkniete (`--bbox-crs` przyjmuje tylko kody
  wielkimi literami). (finalny review fali review max, m-2)

### Tests
- **1861 testow offline, pokrycie 92,9%** (pomiar 2026-09-28:
  `pytest tests/ -m "not live"` — 1861 passed, 8 deselected; 8 testow `live`
  wymaga sieci i nie nalezy do bramki). Historia: 1142 po mergu etapu 0,
  1402 po etapie 1, 1716 po audycie przedwydaniowym 0.7.0 (1708 po 26
  zadaniach + 8 w fali naprawczej po finalnym review), 1787 lacznie z 8
  `live` (1779 offline) po ukladzie `data/` i `--target-crs` PL, 1861
  offline po fali review max (1854 po 18 zadaniach + 7 w fali naprawczej
  po finalnym review; lacznie +82). ruff i `ruff format` czyste, mypy 32
  bledy (baseline sprzed etapu 0: 33; fala review max bez nowych bledow)
- **Testy na zywych danych (2026-09-29)** — centrum kraju, pas morski,
  pogranicza PL-CZ, PL-DE, PL-SK/UA/BY/LT/RU, duzy wycinek (offline) — 7
  raportow w `docs/research/2026-09-29-live-e2e-i-audyt-docs/`; wyniki
  i bledy wykryte na zywo: `docs/PROGRESS.md`.
- **Fala review max (2026-09-28)** — nowe i zmienione testy m.in.
  w `tests/test_pl_cutout.py` (API biblioteki, siatka arkuszy, VRT, R5,
  rozmiar i dysk), `tests/test_transport_mosaic.py` (leniwe otwieranie
  zrodel, crop na siatce zrodel, owijanie w VRT), `test_download_manager.py`
  (`download_sheets`/`expand_sheets`, `no_coverage`), `test_storage.py`,
  `test_sheet_parser.py`, `test_cli.py`; kazdy test zachowania z dowodem
  mutacyjnym. E2E offline na realnych arkuszach 5 m z cache Hydrografu
  (provider kopiujacy arkusze, poza tym zero podmian): cel EPSG:2180 —
  0 z 80 601 pikseli rozbieznych z arkuszem zawierajacym srodek piksela,
  siatka `mod 5 = 2,5 m`; cel EPSG:5514 — wzgledem niezaleznego warpu GDAL
  kazdego arkusza srednio 2,7 mm (maks. 0,15 m poza szwem arkuszy, patrz
  `docs/ARCHITECTURE.md` 4.3); arkusz nieobecny w cache -> `missing_sheets`
  i nodata wylacznie w jego miejscu
- **Etap 0 — walidacja warstw WMS**
  - `tests/test_wms_layer_validation.py` — nowa klasa `TestHardcodedLayerNames`
    (5 testow): regresyjne strazniki nazw warstw zweryfikowanych z GetCapabilities
    (KRON86, 1m EVRF2007, 5m EVRF2007, divergencja 5m vs 1m, kolejnosc newest-first)
  - Zaktualizowany `test_returns_discovered_layers_on_mismatch` — uzywa hipotetycznego
    przyszlego zestawu rocznikow, aby galaz mismatch byla niezalezna od hardcoded
  - `tests/test_wms_layer_validation.py` — nowa klasa `TestOrtoLayerValidation`
    (7 testow): parsowanie/sortowanie GetCapabilities orto, wykluczanie `Zasiegi`,
    mismatch/match/fallback/cache, straznik nazw warstw
  - `tests/test_gugik_orto.py` — autouse fixture stubujaca GetCapabilities (offline),
    zaktualizowany `test_get_opendata_url_tries_all_layers` (9 → 4 warstwy)
- **Etap 1 — Czechy (CUZK)**
  - +260 testow wzgledem stanu po mergu etapu 0 (1142 -> 1402), w tym +18
    testow regresji fixu ADR-024 i +3 przypiecia sciezki godlowej
  - E2E na zywych danych CUZK + regresja PL: **11/11 PASS**
    (`docs/research/2026-08-11-etap1-e2e.md`) — godlo TM33 (dmr5g, Bpv),
    godlo SM5 (dmr4g, kraj auto-wykryty), bbox przygraniczny `--country auto`
    (osobne pliki PL/CZ, wspolny `parent_request`), `--target-crs EPSG:2180`,
    transformacja pionowa `--vertical-crs EVRF2007` (offset zmierzony na zywo
    +0,132366 m, zgodny z modelem), `--vertical-crs KRON86` (blad z remedium),
    regresja PL (godlo, `landcover list-sources`, `cache stats`)
- **Audyt przedwydaniowy 0.7.0**
  - blokada sieci w `tests/conftest.py` i globalny stub GetCapabilities —
    20 testow przestalo odpytywac serwery GUGiK; lokalny autouse fixture
    w `tests/test_gugik_orto.py` zastapiony tym globalnym, a realnych nazw
    warstw pilnuje osobny marker `real_wms_layers` (A8-1)
  - `test_get_opendata_url_tries_all_layers` niezalezny od liczby warstw
    GUGiK (A8-2)
  - nowe testy `--workers 1` w trybie `--bbox`/`--geometry` (petla sekwencyjna
    zbiera wszystkie sciezki, A8-5) i skrotu transformacji geometrii podanej
    juz w ukladzie zadania CZ (A8-6)
  - kazda naprawa bledu z audytu ma test przypinajacy (RED przed fixem, GREEN po)

## [0.6.1] - 2026-03-24

### Fixed
- **NMT 5m: naprawione nazwy warstw WMS**
  - `WMS_LAYERS["5m"]["EVRF2007"]`: `SkorowidzeNMT2022` → `SkorowidzeNMT2022iStarsze`
  - Usunieta nieistniejaca warstwa `SkorowidzeNMT2021iStarsze`
  - Dodana brakujaca warstwa `SkorowidzeNMT2025`
  - Bledne nazwy powodowaly brak wynikow przy pobieraniu NMT 5m mimo dostepnosci danych

### Added
- **Walidacja warstw WMS przez GetCapabilities**
  - `_fetch_wms_layers()` — pobiera liste dostepnych warstw z WMS GetCapabilities
  - `_get_validated_layers()` — porownuje hardcoded warstwy z live WMS, auto-aktualizacja przy rozbieznosci
  - Lazy validation: tylko przy pierwszym wywolaniu `_get_opendata_url()`
  - Graceful fallback: jesli GetCapabilities niedostepne, uzywa hardcoded warstw
  - Warning logowany przy wykryciu rozbieznosci miedzy hardcoded a live
  - In-memory cache per instancja providera (bez lock, benign duplicate OK)
  - Osobny timeout 10s dla GetCapabilities
  - Dziala dla GugikProvider (NMT) i GugikNmptProvider (NMPT) przez dziedziczenie
  - GugikOrtoProvider nieobslugiwany (inna hierarchia dziedziczenia)

### Tests
- **1007 testow** (+17 nowych)
  - Nowy `tests/test_wms_layer_validation.py` — 17 testow dla walidacji warstw WMS

---

## [0.6.0] - 2026-03-03

### Added
- **Parallel downloads with ThreadPoolExecutor**
  - `DownloadManager(max_workers=4)` — configurable thread pool for hierarchy downloads
  - `DownloadResult` dataclass — structured results with succeeded/failed/skipped tracking
  - `_download_hierarchy_parallel()` — concurrent sheet downloads with progress callbacks
  - `LandCoverManager.download_batch()` — parallel batch download for land cover data
  - CLI: `--workers`/`-w` flag on `kartograf download` (default: 4)
  - Thread-safe temp filenames in all providers (`pid_threadid.tmp` pattern)
- **SQLite metadata cache (MetadataCache)**
  - `kartograf/cache/metadata.py` — SQLite WAL mode, TTL 7 days, thread-safe writes
  - URL cache for GUGiK OpenData lookups (NMT, NMPT, Orto)
  - TERYT cache for BDOT10k point-to-TERYT resolution
  - `prune_expired()` — automatic cleanup of stale entries
  - Integrated with GugikProvider, GugikNmptProvider, GugikOrtoProvider, Bdot10kProvider
  - CLI: `kartograf cache stats|clear|path`
- **PL-2000 BBox verification tests**
  - 67 new tests: reference values, hierarchy consistency, live WMS, edge cases
  - `@pytest.mark.live` marker for GUGiK WMS integration tests
- **Public API: eksport MetadataCache i DownloadResult**
  - `from kartograf import MetadataCache, DownloadResult`

### Tests
- **990 testow** (+155 nowych)

---

## [0.5.0] - 2026-03-02

### Added
- **PL-2000 sheet naming system — full support**
  - `Parser2000` class for parsing PL-2000 godla (format `zone.row.column[.subdivisions]`)
  - 5 skal: 1:10000, 1:5000, 1:2000, 1:1000, 1:500
  - 4 strefy merydianowe: 5 (EPSG:2176), 6 (EPSG:2177), 7 (EPSG:2178), 8 (EPSG:2179)
  - BBox calculation z transformacja CRS (pyproj)
  - Hierarchia: get_parent(), get_children(), get_all_descendants(), get_hierarchy_up()
  - `find_sheets_2000_for_bbox()` — BBox to PL-2000 godla lookup
- **SheetParser auto-detekcja PL-1992 vs PL-2000**
  - `SheetParser("6.179.12")` automatycznie rozpoznaje PL-2000
  - `SheetParser("N-34-130-D")` automatycznie rozpoznaje PL-1992
  - Walidacja zgodnosci uklad/format
- **find_sheets_for_bbox: parametr system="1992"|"2000"**
  - `find_sheets_for_bbox(bbox, system="2000")` zwraca godla PL-2000
  - `find_sheets_for_geometry()` rowniez obsluguje parametr system
- **CLI: pelna obsluga PL-2000**
  - `kartograf parse 6.179.12.20` — auto-detekcja, wyswietla strefe i CRS
  - `kartograf download --bbox ... --system 2000` — pobieranie z godlami PL-2000
  - `--bbox-crs` rozszerzony o EPSG:2176-2179
- **FileStorage: obsluga sciezek PL-2000**
  - Struktura katalogow: `nmt_2000_1m/6/179/12/20/6.179.12.20.asc`
    (uwaga 2026-08-22: podkatalog `nmt_2000_1m` nie zostal zrealizowany —
    arkusze PL-2000 ladowaly w `nmt_<res>/` obok PL-1992, patrz ADR-017
    i docstring `FileStorage`; rozdzielenie katalogow odlozone.
    **Domkniete w 0.7.0** — ADR-026 dal PL-2000 wlasne segmenty
    `nmt/pl_2000_<res>_<vcrs>/`; patrz Breaking Changes 0.7.0)
- **Public API: eksport Parser2000 i find_sheets_2000_for_bbox**
  - `from kartograf import Parser2000, find_sheets_2000_for_bbox`

### Removed
- **BDOT10k: usunięto filtrowanie po kategorii (--category pt/hydro)**
  - Pobierany jest cały plik BDOT10k bez podziału na kategorie
  - Usunięto stałe `PT_LAYERS`, `HYDRO_LAYERS`, `CATEGORY_FILTERS`
  - Usunięto parametr `category` z `download_by_teryt()`, `_download_with_retry()`, `_extract_gpkg_from_zip()`
  - Usunięto argument CLI `--category`
  - `_extract_gpkg_from_zip()` wyciąga i scala wszystkie warstwy GPKG z ZIP
  - `get_available_layers()` zwraca wszystkie 15 warstw (PT* + SW*)

### Fixed
- **download_sheet(): PL-2000 sub-10k godla pobierane bezposrednio**
  - Godla PL-2000 w skalach 1:5000, 1:2000, 1:1000, 1:500 sa teraz pobierane
    jako pojedyncze pliki, bez proby rozwijania do 1:10000
- **CLI: dynamiczne etykiety skal**
  - `format_hierarchy()` — naglowek "from current to X" zamiast hardcoded "1:1000000"
  - `format_children()` — "finest scale X" zamiast hardcoded "1:10000"

### Tests
- **835 testow** (+199 nowych; w trakcie prac bylo 849 — 14 testow
  `--category` usunieto w tej samej wersji razem z flaga, ADR-016)

---

## [0.4.1] - 2026-02-08

### Fixed
- **BDOT10k: rtree spatial indices preserved during GPKG merge**
  - After merging multiple GPKG files, only the base (first) file kept its rtree index
  - New `_copy_rtree_index()` method copies rtree virtual table, data, and `gpkg_extensions` entry
  - All merged layers now retain spatial indices for fast spatial queries

### Added
- **Geometry file selection (`--geometry FILE`)**
  - Support for SHP (via pyshp) and GPKG (via sqlite3 + envelope parsing) input files
  - Per-feature bbox extraction for precise tile selection (not entire file bbox)
  - `find_sheets_for_geometry()` — public API for geometry → godla lookup
  - `get_overall_bbox()` — union bbox for landcover/soilgrids
  - CRS auto-detection from .prj (SHP) and gpkg_spatial_ref_sys (GPKG)
  - New dependency: `pyshp>=2.3.0`
- **CLI: `--geometry` and `--layer` for all download commands**
  - `kartograf download --geometry area.shp` — NMT tiles intersecting features
  - `kartograf download --geometry area.gpkg --layer catchments` — GPKG layer selection
  - `kartograf landcover download --source bdot10k --geometry area.shp`
  - `kartograf soilgrids hsg --geometry area.shp`

### Tests
- **636 testow** (+62 nowych)
  - 31 testow `test_geometry.py`: envelope parsing, SHP/GPKG reading, CRS transform, find_sheets_for_geometry, get_overall_bbox
  - 12 testow CLI geometry: download/landcover/soilgrids --geometry, mutual exclusivity
  - 5 testow `TestBdot10kRtreeIndex`: merge preserves indices, no geometry, no index, extensions copied, base preserved

---

## [0.4.0] - 2026-02-07

### Added
- **NMPT (Numeryczny Model Pokrycia Terenu / Digital Surface Model)**
  - `GugikNmptProvider` — dziedziczy z GugikProvider, nadpisuje endpointy NMPT
  - Tylko rozdzielczość 1m, vertical CRS: KRON86 lub EVRF2007
  - Download: godło → OpenData ASC, bbox → WCS GeoTIFF
- **Ortofotomapa (Standard Resolution, 25cm)**
  - `GugikOrtoProvider` — osobna klasa, format TIF
  - Brak vertical CRS (2D RGB), 9 warstw WMS (2018-2025+starsze)
  - Download: godło → OpenData TIF, bbox → WCS GeoTIFF
- **CLI `--product {nmt,nmpt,orto}` — wybór produktu w komendzie download**
  - `kartograf download N-34-130-D-d-2-4 --product nmpt` — pobiera NMPT
  - `kartograf download --bbox ... --product orto` — pobiera ortofoto
  - Domyślnie: nmt (bez zmian)
- **`find_sheets_for_bbox()` — reverse lookup: bbox → godła arkuszy**
  - Algorytm hierarchicznego przycinania (matematyczny, bez WFS)
  - Obsługa EPSG:2180 i EPSG:4326
  - Dowolna skala docelowa (1:1M do 1:10k)
  - Zoptymalizowane wyszukiwanie 1:200k (siatka 12x12)
- **CLI `kartograf download --bbox` — pobieranie NMT dla bbox**
  - `--bbox min_x,min_y,max_x,max_y` — współrzędne bbox
  - `--bbox-crs {EPSG:2180,EPSG:4326}` — CRS bbox (domyślnie EPSG:2180)
  - `godlo` staje się opcjonalny (godlo XOR --bbox)
  - Automatyczne wykrywanie arkuszy i pobieranie w pętli
- **Automatyczne rozwijanie godeł do 1:10000 w `download_sheet()`**
  - `download_sheet("N-34-130-D-d-2")` (1:25000) → automatycznie pobiera 4 arkusze 1:10000
  - `download_sheet("N-34-130-D-d")` (1:50000) → pobiera 16 arkuszy 1:10000
  - Dla godeł 1:10000 zachowanie bez zmian (pojedynczy plik)
  - Nowy parametr `on_progress` — callback postępu przy rozwijaniu hierarchii
  - Zwracany typ: `Path` (1:10000) lub `list[Path]` (coarser scales)
  - CLI dostosowane — wyświetla liczbę pobranych plików przy rozwijaniu

### Tests
- **574 testow, pokrycie 83.95% (cel 80% osiagniety)**
  - Nowy `tests/test_gugik_nmpt.py` — 21 testow dla GugikNmptProvider
  - Nowy `tests/test_gugik_orto.py` — 25 testow dla GugikOrtoProvider
  - Nowy `tests/test_auth_client.py` — 30 testow dla AuthProxyClient
  - Nowy `tests/test_auth_proxy.py` — 24 testy dla CLMSCredentials, ProxyHandler
  - Rozszerzony `tests/test_cli.py` — +12 testow (product CLI), +11 testow (landcover/soilgrids CLI)
  - Rozszerzony `tests/test_storage.py` — +8 testow (product storage)
  - Rozszerzony `tests/test_download_manager.py` — +3 testy (default_ext)
  - Rozszerzony `tests/test_landcover.py` — +38 testow
  - Rozszerzony `tests/test_hsg.py` — +6 testow

### Fixed
- Poprawiony komunikat błędu przy braku pokrycia NMT 5m — zamiast technicznego "No ASC file found in any WMS layer" wyświetla czytelną informację o braku pokrycia danego obszaru w GUGiK

### Changed
- **FileStorage: podkatalogi `1m`/`5m` → `nmt_1m`/`nmt_5m`**
  - Nowy parametr `product` w FileStorage (np. product="nmpt", product="orto")
  - Struktura: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`
- **DownloadManager: dynamiczne rozszerzenie pliku**
  - `_default_ext` pobierane z `provider.default_extension` zamiast hardcoded `.asc`
- **BaseProvider: nowa property `default_extension`** (domyślnie `.asc`)
- Migracja z black + flake8 na ruff (pyproject.toml)
- Usuniecie .flake8, dodanie .editorconfig
- Standaryzacja dokumentacji wg shared/standards
- Przepisanie CLAUDE.md (7 sekcji, ~148 linii)
- Przepisanie PROGRESS.md (4 sekcje, skondensowane z 785 linii)
- Rozbudowanie DEVELOPMENT_STANDARDS.md (722 linii, 15 sekcji wg shared/standards)
- Rozbudowanie IMPLEMENTATION_PROMPT.md (284 linii, 11 sekcji, aktualny kontekst v0.3.2)
- Aktualizacja README.md, PRD.md, SCOPE.md
- Auto-naprawa kodu przez `ruff check --fix` (63 poprawki: importy, type annotations)

### Added
- Konfiguracja ruff (linter + formatter) w pyproject.toml
- Plik .editorconfig
- Sekcja [project.optional-dependencies] dev w pyproject.toml
- docs/DECISIONS.md — rejestr 9 decyzji architektonicznych (ADR)

### Removed
- Plik .flake8 (konfiguracja pokryta przez ruff)
- Sekcja [tool.black] z pyproject.toml

---

## [0.3.2] - 2026-01-21

### Changed - Storage Structure and Default Vertical CRS

- **Domyślny układ wysokościowy zmieniony na EVRF2007**
  - `GugikProvider`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - `DownloadManager`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - CLI: `--vertical-crs` domyślnie `EVRF2007`
  - Kronsztadt 86 (KRON86) jest przestarzały i dostępny jako opcja legacy

- **Nowa struktura katalogów z rozdzielczością**
  - `FileStorage`: nowy parametr `resolution` (domyślnie `"1m"`)
  - Pliki NMT są teraz rozdzielone według rozdzielczości:
    ```
    data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 1m
    data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 5m
    ```
  - `DownloadManager` automatycznie przekazuje `resolution` do `FileStorage`
  - Domyślne rozszerzenie pliku zmienione z `.tif` na `.asc`

### Breaking Changes

- **Struktura katalogów** - pliki NMT są teraz zapisywane w podkatalogu `1m/` lub `5m/`
  - Stara ścieżka: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
  - Nowa ścieżka: `data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`

- **Domyślny vertical_crs** - zmieniony z `KRON86` na `EVRF2007`
  - Aby używać starego układu: `--vertical-crs KRON86`

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (EVRF2007 domyślnie)
kartograf download N-34-130-D-d-2-4
# → data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m
# → data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Użyj starego układu Kronsztadt (legacy)
kartograf download N-34-130-D-d-2-4 --vertical-crs KRON86
```

---

## [0.3.1] - 2026-01-21

### Added - NMT Resolution Selection

- **Wybór rozdzielczości NMT** - Obsługa danych NMT w dwóch rozdzielczościach
  - `1m` (GRID1) - wysoka rozdzielczość, domyślna
  - `5m` (GRID5) - niższa rozdzielczość, tylko dla EVRF2007

- **GugikProvider** - Nowy parametr `resolution`
  - `GugikProvider(resolution="5m", vertical_crs="EVRF2007")`
  - Nowe endpointy WMS dla 5m: `SheetsGrid5mEVRF2007`
  - Automatyczna walidacja: 5m wymaga EVRF2007
  - Nowe metody: `get_supported_resolutions()`, `is_wcs_available()`
  - `download_bbox()` rzuca ValueError dla 5m (WCS niedostępne)

- **DownloadManager** - Nowy parametr `resolution`
  - `DownloadManager(resolution="5m")` - automatycznie wymusza EVRF2007

- **CLI** - Nowa opcja `--resolution`
  - `kartograf download N-34-130-D --resolution 5m`
  - Skrót: `-r 5m`

**Ograniczenia 5m:**
- Dostępne tylko w układzie EVRF2007
- Brak obsługi WCS (download_bbox) - tylko arkusze OpenData

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (domyślnie)
kartograf download N-34-130-D-d-2-4

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m

# Pobierz hierarchię w 5m
kartograf download N-34-130-D --scale 1:10000 -r 5m
```

### Changed

- **Testy** - 365 testów (18 nowych dla resolution)

### Fixed - Cross-Project Compatibility (2026-01-21)

- **Public API exports** - Uzupełniono brakujące eksporty w głównym module
  - Dodano `SoilGridsProvider` do `kartograf/__init__.py`
  - Dodano `HSGCalculator` do `kartograf/__init__.py`
  - Teraz możliwy import: `from kartograf import SoilGridsProvider, HSGCalculator`

### Fixed - QA Review (2026-01-21)

- **Synchronizacja wersji** - Ujednolicono wersję we wszystkich plikach
  - `pyproject.toml`: 0.3.0 → 0.3.1
  - `kartograf/__init__.py`: 0.3.0-dev → 0.3.1
  - `README.md`: zaktualizowano status i liczbę testów

- **Synchronizacja zależności** - Uzupełniono brakujące zależności
  - `pyproject.toml`: dodano `rasterio>=1.3.0`, `numpy>=1.24.0`
  - `requirements.txt`: dodano `PyJWT[crypto]>=2.8.0`

- **Testy** - Naprawiono test wersji w `test_integration.py`

- **Dokumentacja** - Dodano sekcję QA Review do `PROGRESS.md`

---

## [0.3.0] - 2026-01-18

### Added - SoilGrids i Hydrologic Soil Groups (HSG)

- **SoilGridsProvider** - Provider dla ISRIC SoilGrids (dane glebowe)
  - Globalne dane glebowe w rozdzielczości 250m
  - WCS Endpoint: `https://maps.isric.org/mapserv`
  - **11 parametrów glebowych:**
    - `bdod` - Gęstość objętościowa (kg/dm³)
    - `cec` - Pojemność wymiany kationowej (cmol/kg)
    - `cfvo` - Fragmenty gruboziarniste (%)
    - `clay` - Zawartość gliny (%)
    - `nitrogen` - Azot całkowity (g/kg)
    - `ocd` - Gęstość węgla organicznego (kg/m³)
    - `ocs` - Zasób węgla organicznego (t/ha)
    - `phh2o` - pH w H2O
    - `sand` - Zawartość piasku (%)
    - `silt` - Zawartość pyłu (%)
    - `soc` - Węgiel organiczny (g/kg)
  - **6 głębokości:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
  - **5 statystyk:** mean, Q0.05, Q0.5, Q0.95, uncertainty
  - Transformacja CRS: EPSG:2180 → WGS84

- **HSGCalculator** - Kalkulacja Hydrologic Soil Groups dla metody SCS-CN
  - `kartograf/hydrology/hsg.py` - moduł hydrologiczny
  - Klasyfikacja tekstury gleby wg trójkąta USDA (12 klas)
  - Mapowanie tekstury do HSG (A, B, C, D)
  - **Grupy hydrologiczne:**
    - A - wysoka infiltracja (piasek, piasek gliniasty)
    - B - umiarkowana infiltracja (glina piaszczysta, glina)
    - C - wolna infiltracja (glina ilasta)
    - D - bardzo wolna infiltracja (ił)
  - Automatyczne pobieranie clay/sand/silt z SoilGrids
  - Statystyki pokrycia dla każdej grupy HSG

- **CLI soilgrids** - Nowe komendy CLI
  - `kartograf landcover download --source soilgrids --property <param> --depth <głębokość>`
  - `kartograf landcover list-layers --source soilgrids`
  - `kartograf soilgrids hsg --godlo <godło>` - kalkulacja HSG
  - Opcje HSG: `--depth`, `--output`, `--keep-intermediate`, `--stats`

**Przykłady użycia:**
```bash
# Pobierz węgiel organiczny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc

# Pobierz zawartość gliny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Oblicz HSG dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats
```

### Added - Land Cover (Pokrycie Terenu)

- **LandCoverProvider** - Nowa abstrakcja dla providerów danych pokrycia terenu
  - Metody: `download_by_teryt()`, `download_by_bbox()`, `download_by_godlo()`
  - Wspólny interfejs dla różnych źródeł danych

- **Bdot10kProvider** - Provider dla BDOT10k (GUGiK)
  - Pobieranie paczek powiatowych przez TERYT
  - Pobieranie przez WMS GetFeatureInfo dla URL paczki
  - Pobieranie przez godło arkusza (konwersja na bbox)
  - **12 warstw pokrycia terenu (PT*):**
    - PTGN - Grunty nieużytkowe
    - PTKM - Tereny komunikacyjne
    - PTLZ - Tereny leśne
    - PTNZ - Tereny niezabudowane
    - PTPL - Place
    - PTRK - Roślinność krzewiasta
    - PTSO - Składowiska
    - PTTR - Tereny rolne
    - PTUT - Uprawy trwałe
    - PTWP - Wody powierzchniowe
    - PTWZ - Tereny zabagnione
    - PTZB - Tereny zabudowane
  - Automatyczne scalanie warstw PT* z ZIP do jednego GeoPackage
  - Format wyjściowy: GeoPackage (.gpkg), SHP

- **CorineProvider** - Provider dla CORINE Land Cover (Copernicus)
  - Europejska klasyfikacja pokrycia terenu (44 klasy)
  - Dostępne lata: 1990, 2000, 2006, 2012, 2018
  - **Trzy źródła danych (w kolejności priorytetu):**
    1. **CLMS API** - GeoTIFF z kodami klas (wymaga OAuth2)
    2. **EEA Discomap WMS** - Podgląd PNG (lata 2000-2018)
    3. **DLR WMS** - Fallback dla 1990
  - OAuth2 RSA authentication dla CLMS API
  - Przechowywanie credentials w macOS Keychain (serwis: `clms-token`)

- **LandCoverManager** - Zarządzanie pobieraniem danych pokrycia terenu
  - Dispatch do odpowiedniego providera
  - Obsługa wielu metod selekcji obszaru

- **CLI landcover** - Nowe komendy CLI
  - `kartograf landcover download --source bdot10k --teryt <kod>`
  - `kartograf landcover download --source corine --year <rok> --godlo <godło>`
  - `kartograf landcover list-sources`
  - `kartograf landcover list-layers --source bdot10k`

### CLMS API Authentication - Auth Proxy

CorineProvider używa **Auth Proxy** dla bezpiecznej autentykacji CLMS API:

**Architektura bezpieczeństwa:**
```
CorineProvider → localhost HTTP → AuthProxy (subprocess) → Keychain → CLMS API
```

- Credentials (klucz prywatny RSA) są izolowane w osobnym procesie
- Główna aplikacja nigdy nie widzi credentials
- Tylko odpowiedzi API są przekazywane do aplikacji

**Nowe moduły:**
- `kartograf/auth/proxy.py` - serwer HTTP izolujący credentials
- `kartograf/auth/client.py` - klient automatycznie uruchamiający proxy

**Konfiguracja:**
1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (JSON)
3. Zapisz do Keychain:
   ```bash
   security add-generic-password -a "$USER" -s "clms-token" -w '<json_credentials>'
   ```

**Tryby pracy:**
```python
# Domyślny (bezpieczny) - używa proxy
provider = CorineProvider()

# Bezpośredni (dla testów) - credentials widoczne
provider = CorineProvider(clms_credentials={...}, use_proxy=False)
```

**Uwaga:** Jeśli credentials nie są skonfigurowane, CorineProvider automatycznie używa WMS (podgląd PNG zamiast GeoTIFF z kodami klas).

### Dependencies

- Dodano `PyJWT[crypto]>=2.8.0` - JWT generation dla OAuth2
- Dodano `rasterio>=1.3.0` - przetwarzanie rastrów GeoTIFF
- Dodano `numpy>=1.24.0` - operacje na tablicach

### Technical Details

- 347 testów (42 dla landcover, 28 dla soilgrids, 34 dla HSG)
- Formatowanie: black, flake8

### Sources

- BDOT10k: https://www.geoportal.gov.pl/en/data/topographic-objects-database-bdot10k/
- CORINE Land Cover: https://land.copernicus.eu/en/products/corine-land-cover
- EEA Discomap: https://image.discomap.eea.europa.eu
- DLR EOC: https://geoservice.dlr.de/eoc/land/wms
- ISRIC SoilGrids: https://soilgrids.org/
- SoilGrids Documentation: https://docs.isric.org/globaldata/soilgrids/

---

## [0.2.0] - 2026-01-18

### Changed - Nowa architektura pobierania

**Uproszczona logika pobierania:**
- **Godło → OpenData (ASC)** - pobieranie arkusza przez godło zawsze daje plik ASC
- **BBox → WCS (GeoTIFF)** - pobieranie przez bounding box daje GeoTIFF/PNG/JPEG

**Zmiany API:**
- `download_sheet(godlo)` - zawsze pobiera ASC (usunięto parametr `format`)
- `download_hierarchy(godlo, target_scale)` - pobiera wszystkie arkusze jako ASC
- `download_bbox(bbox, filename, format)` - **nowa metoda** dla pobierania przez bbox
- Usunięto `construct_url()` z publicznego API
- `DownloadManager` nie przyjmuje już parametru `format` w konstruktorze

### Added

- **Pobieranie ASC przez OpenData** - Automatyczne wyszukiwanie URL przez WMS GetFeatureInfo
  - Zapytania do warstw: `SkorowidzeNMT2019`, `SkorowidzeNMT2018`, `SkorowidzeNMT2017iStarsze`
  - Pobieranie z `opendata.geoportal.gov.pl`

- **SheetParser.get_bbox()** - Obliczanie bounding box arkusza
  - Obsługiwane CRS: `EPSG:2180` (PL-1992), `EPSG:4326` (WGS84)
  - Transformacja współrzędnych przez `pyproj`

- **BBox** - Nowy typ danych w public API

- **GugikProvider.download_bbox()** - Pobieranie przez bounding box z WCS

### Dependencies

- Dodano `pyproj>=3.6.0` do wymagań

### Technical Details

- 245 testów

## [0.1.0] - 2026-01-17

### Added

- **SheetParser** - Parser for Polish topographic map sheet identifiers (godlo)
  - Support for scales 1:1,000,000 to 1:10,000
  - Support for "1992" coordinate system layout
  - Hierarchy navigation: `get_parent()`, `get_children()`, `get_hierarchy_up()`
  - Descendant enumeration: `get_all_descendants(target_scale)`
  - Special handling for 1:500k to 1:200k division (36 sheets per section)

- **DownloadManager** - Coordinated download of NMT data
  - Single sheet download: `download_sheet(godlo)`
  - Hierarchy download: `download_hierarchy(godlo, target_scale)`
  - Progress callbacks with `DownloadProgress` dataclass
  - Skip existing files option for resumable downloads
  - Missing sheets detection: `get_missing_sheets()`

- **GugikProvider** - Integration with GUGiK WCS service
  - GeoTIFF and Arc/Info ASCII Grid format support
  - Retry logic with exponential backoff (3 attempts)
  - 30-second timeout per request

- **FileStorage** - Hierarchical file storage management
  - Automatic directory structure based on godlo components
  - Atomic writes (temp file + rename)
  - Path generation: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif`

- **CLI** - Command-line interface
  - `kartograf parse <godlo>` - Display sheet information
  - `kartograf parse <godlo> --hierarchy` - Show hierarchy to 1:1M
  - `kartograf parse <godlo> --children` - Show direct children
  - `kartograf download <godlo>` - Download single sheet
  - `kartograf download <godlo> --scale <scale>` - Download hierarchy
  - Options: `--format`, `--output`, `--force`, `--quiet`

- **Public API** - Clean imports from main module
  - `from kartograf import SheetParser, DownloadManager`
  - All exceptions: `KartografError`, `ParseError`, `ValidationError`, `DownloadError`
  - Providers: `BaseProvider`, `GugikProvider`

- **Test Coverage** - 97% coverage with 235 tests
  - Unit tests for all modules
  - Integration tests for complete workflows

### Technical Details

- Python 3.12+ required
- Single dependency: `requests>=2.31.0`
- Project structure follows src layout
- Configured with black, flake8, pytest

[0.7.0]: https://github.com/Daldek/Kartograf/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/Daldek/Kartograf/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/Daldek/Kartograf/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Daldek/Kartograf/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/Daldek/Kartograf/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Daldek/Kartograf/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.2
[0.3.1]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.1
[0.3.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.0
[0.2.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.2.0
[0.1.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.1.0
