# Review-2: deklarowane vs faktyczne dzialanie (develop 55070f8, przed 0.7.0)

**Data:** 2026-10-06
**Zakres:** CLAUDE.md (sekcja "Ograniczenia"), docs/ARCHITECTURE.md,
docs/DECISIONS.md (ADR-023..028), docs/CHANGELOG.md [0.7.0], README.md,
docs/SCOPE.md 3.2, docstringi API eksportowanego w `kartograf/__init__.py`,
teksty `--help` (`kartograf/cli/_parser.py`), komentarze w kodzie.
**Metoda:** dla kazdej sprawdzalnej deklaracji — sciezka wykonania
(plik:linia) i, gdzie sie dalo, eksperyment offline (`.venv/bin/python -I`,
mock sesji HTTP, gniazdo zablokowane w eksperymencie CLI). Skrypty i surowe
wyniki: `/tmp/claude-2001/review2/exp_*.py` (nie w repo). Zadnych zmian
w kodzie, testach ani dokumentach poza tym plikiem.

Wagi: **WYSOKA** — uzytkownik/konsument biblioteki dostaje inne zachowanie
niz obiecane w sposob wplywajacy na dane albo kod wyjscia; **SREDNIA** —
mylace; **NISKA** — literowka / nieaktualna liczba / martwy parametr.

Bilans: **1 WYSOKA, 7 SREDNIA, 9 NISKA**; 40+ deklaracji sprawdzonych
i zgodnych (sekcja na koncu).

---

## Znaleziska

### N1 (WYSOKA) — `--format SHP` dla BDOT10k zapisuje ZIP z shapefile'ami pod nazwa `.gpkg`

- **Deklaracja:** README.md "Land Cover ... Formaty - GeoPackage, Shapefile";
  `kartograf/cli/_parser.py:267-273` `--format {GPKG,SHP}` "Output format for
  BDOT10k"; `Bdot10kProvider.get_supported_formats()` (`bdot10k.py:877`)
  zwraca `["GPKG", "SHP"]`; ARCHITECTURE.md 4.8 "`<provider>_teryt_<teryt>.gpkg`".
- **Faktycznie:** `LandCoverManager._generate_output_path`
  (`landcover/manager.py:1194-1213`) ZAWSZE nadaje rozszerzenie `.gpkg`,
  niezaleznie od `format`. `Bdot10kProvider.download_by_admin_unit`
  (`bdot10k.py:208-214`) przekazuje `extract_from_zip=(format == "GPKG")`,
  wiec dla SHP `_download_with_retry` (`bdot10k.py:522-526`) zapisuje
  surowa odpowiedz (`_save_response`) do `bdot10k_teryt_1465.gpkg`. Plik
  jest archiwum ZIP z `.shp/.dbf/...`, nazywa sie `.gpkg`, dostaje sidecar
  z `dataset=pl.gugik.bdot10k`, a CLI drukuje `Downloaded to: ....gpkg`.
- **Dowod:** `exp_bdot_shp.py` (mock sesji):
  `URL: .../SHP/14/1465_SHP.zip | zwrocona sciezka: bdot10k_teryt_1465.gpkg
  | naglowek pliku: b'PK\x03\x04' | sidecar: True`. W `tests/` nie ma testu
  koncowego dla SHP (tylko `_construct_opendata_url` i lista formatow).
- **Kierunek:** KOD — albo `LandCoverManager` nadaje rozszerzenie wg
  formatu/zwracanej sciezki (`.zip` dla SHP; provider moze tez zwracac
  `output_path.with_suffix(".zip")` jak robi to dla GPKG przez
  `with_suffix(".gpkg")`), albo SHP wypada z `choices` i dokumentow.
  Dokument sam w sobie nie naprawi pliku `.gpkg`, ktory nie jest GeoPackage.

### N2 (SREDNIA) — README: "arkusz za granica konczy polecenie kodem 1" — kod to 0 + `Warning:`

- **Deklaracja:** README.md, sekcja CLI: "Na pograniczu ... uzywaj
  --target-crs: bez niego arkusz lezacy za granica konczy polecenie kodem 1."
- **Faktycznie:** tryb listy arkuszy ma tolerancje R5 (S2, 2026-09-30):
  `_finish_pl_sheets` (`cli/download_cmd.py:1056-1109`) — `NoCoverageError`
  arkusza daje `Warning:` i kod 0, gdy pobrano >= 1 plik. Kod 1 tylko gdy
  WSZYSTKIE arkusze sa bez danych, przy twardej awarii albo dla pojedynczego
  arkusza. Tak tez mowia CLAUDE.md ("Lista arkuszy PL ... >= 1 plik i tylko
  braki pokrycia -> kod 0"), ARCHITECTURE 4.2, ADR-027 (uzupelnienie
  2026-09-30) i CHANGELOG.
- **Dowod:** `exp_misc.py`: `1 ok + 1 no_coverage -> rc=0 stderr: Warning:
  GUGiK nie ma danych dla 1 z 2 arkuszy (B) — pominiete ...`;
  `0 ok + 2 no_coverage -> rc=1`; `1 ok + 1 hard failure -> rc=1`.
- **Kierunek:** DOKUMENT (README) — zdanie pochodzi sprzed S2; kanoniczne
  dokumenty opisuja kod poprawnie. Argument za `--target-crs` na pograniczu
  (nodata zamiast brakujacego pliku) pozostaje, ale bez "kodu 1".

### N3 (SREDNIA) — GetCapabilities skorowidza GUGiK ma timeout 10 s, nie 30/60 s

- **Deklaracja:** CLAUDE.md "Timeouty domyslne: 30 s dla NMT/NMPT (GUGiK)
  ...; 60 s dla Ortofoto"; SCOPE.md 3.2 identycznie. ARCHITECTURE 4.1:
  awaria warstwy = `DownloadError` "bez cichego zejscia".
- **Faktycznie:** `SkorowidzLayersMixin._fetch_wms_layers(self, wms_endpoint,
  timeout: int = 10)` (`providers/pl/skorowidz.py:377`), wolane z `_layers()`
  (`skorowidz.py:413-418`) BEZ przekazania timeoutu providera. Pierwsze
  zapytanie kazdego toru NMT/NMPT/orto (discovery warstw) ma wiec 10 s na
  probe (3 proby), a jego porazka to twardy `DownloadError` calego zadania —
  w trybie listy kazdy arkusz konczy jako `failed` (kod 1), w wycinku PL
  wycinek nie powstaje.
- **Dowod:** `exp_defaults.py`: `SkorowidzLayersMixin._fetch_wms_layers ->
  10` obok `GugikProvider.download -> 30`, `GugikOrtoProvider.download -> 60`.
- **Kierunek:** KOD (przekazac `DEFAULT_TIMEOUT` providera do `_layers` /
  `_fetch_wms_layers`) albo DOKUMENT (dopisac "GetCapabilities skorowidza:
  10 s"). GUGiK bywa wolny przy GetCapabilities, wiec kod jest lepszym
  kierunkiem — deklarowane 30/60 s sugeruja, ze tyle ma kazda odpowiedz toru.

### N4 (SREDNIA) — "3 proby" w ARCHITECTURE/ADR-028/CLAUDE.md sa bezwarunkowe, a od 9bcc040 4xx konczy od razu

- **Deklaracja:** ARCHITECTURE.md 4.1 "Zapytania i pobrania maja 3 proby
  z backoffem"; 4.3 krok 4 "awaria ktorejkolwiek pytanej warstwy daje
  `DownloadError` (retry 3 razy)"; ADR-028 "awaria dowolnej odpytywanej
  warstwy po 3 probach = `DownloadError`"; CLAUDE.md "Skorowidz GUGiK ...
  Odpowiedz transportowa ma trzy proby z backoffem"; `download_pl_cutout`
  docstring (`download/cutout.py:884-886`) "zerwane zapytanie warstwy
  skorowidza po 3 probach".
- **Faktycznie:** `transport/http.py:37-42 is_retryable` — tylko blad sieci,
  429 i 5xx sa ponawiane; inne 4xx (403/404 z WMS, 404 pliku OpenData)
  koncza przy pierwszej probie (`get_with_retry` `http.py:100-106`,
  `_download_with_retry` w `gugik.py/gugik_orto.py/gugik_laz.py/bdot10k.py`).
  Commit 9bcc040 zaktualizowal tylko `ARCHITECTURE.md:159` i CHANGELOG;
  pozostale zdania zostaly w brzmieniu "3 proby".
- **Dowod:** `exp_retry.py`: `get_with_retry 404 -> proby=1`,
  `503 -> proby=3 sleep=[1, 2]`, `429 Retry-After=7 -> sleep=[7.0, 7.0]`;
  `GugikProvider._download_with_retry 404 -> proby=1`, `500 -> proby=3`.
- **Kierunek:** DOKUMENT — "do 3 prob (siec, 429, 5xx; inne 4xx bez
  ponowien)" w ARCHITECTURE 4.1/4.3, errata ADR-028, CLAUDE.md i docstring
  `download_pl_cutout`. Polityka kodu jest zamierzona (CHANGELOG).

### N5 (SREDNIA) — dwa zapytania GUGiK/CUZK nie maja zadnych ponowien

- **Deklaracja:** CLAUDE.md/SCOPE "Max 3 proby retry (nie konfigurowalne)";
  CHANGELOG [0.7.0] "Pobieranie GUGiK (NMT/NMPT/orto/LAZ/BDOT10k) oraz
  wspolny transport (`get_with_retry`, `download_to` — skorowidz, WFS LAZ,
  CUZK) ponawia tylko bledy sieci, HTTP 429 i 5xx"; ARCHITECTURE 4.1
  "Zapytania i pobrania maja 3 proby".
- **Faktycznie:**
  1. `CuzkClient.query` (`providers/cuzk/client.py:80-84`) — jedno
     `session.get`, kazdy `RequestException` od razu `DownloadError`.
     Uzywa go `SheetIndex` (`providers/cuzk/sheets.py:95,115,127`): godlo
     SM5 (`CTES96`), indeks arkuszy. `exportImage`/`fetch_file` ida przez
     `download_to` (3 proby) — CHANGELOG mowi o "CUZK" ogolnie.
  2. `Bdot10kProvider._get_teryt_for_point` (`providers/pl/bdot10k.py:339,
     367-397`) — jedno `session.get` GetFeatureInfo (ULDK/WMS Powiaty),
     `RequestException` -> `DownloadError`. To pierwszy krok BDOT10k przez
     `--bbox`/`--godlo`/`--geometry`; chwilowy blad sieci konczy zadanie
     kodem 1 bez ponowienia, mimo ze samo pobranie ZIP-a ma 3 proby.
- **Dowod:** `exp_misc.py`: `CuzkClient.query ConnectionError -> proby=1
  DownloadError`. Dla `_get_teryt_for_point` — sciezka wykonania (brak
  petli, brak `get_with_retry`).
- **Kierunek:** KOD — przepiac oba przez `transport.http.get_with_retry`
  (polityka 429/5xx/Retry-After dostaje sie za darmo). Alternatywnie
  DOKUMENT: wylaczyc je jawnie z "3 prob".

### N6 (SREDNIA) — LAZ: porazka kafli to `Warning:` + kod 1 i tylko 5 pierwszych kafli

- **Deklaracja:** konwencja komunikatow: ARCHITECTURE 4.6 / ADR-023 pkt 4
  ("porazka ... daje kod 0 i `Warning:`; kod 1 ... "), `_finish_pl_sheets`
  (`download_cmd.py:1070-1074`: twarda awaria -> `Error:` "z PELNA lista");
  CLAUDE.md "kazda twarda awaria pobrania -> kod 1 z pelna lista porazek".
  Dla LAZ CLAUDE.md/ARCHITECTURE 4.7 opisuja tylko discovery (`DownloadError`
  z informacja o niepelnym wyniku); kodu wyjscia pobrania kafli nie opisuje
  zaden dokument.
- **Faktycznie:** `_cmd_download_laz` (`download_cmd.py:1627-1631`):
  `print(f"Warning: {len(failed)} tiles failed to download")`, lista
  `failed[:5]`, `return 1`. Prefiks `Warning:` przy kodzie 1 lamie
  konwencje "Warning = kod 0 / Error = kod 1", a przy 20 porazkach
  uzytkownik nie dostaje listy kafli do ponowienia.
- **Dowod:** sciezka wykonania (kod wyzej); brak deklaracji w dokumentach =
  luka, nie sprzecznosc literalna.
- **Kierunek:** KOD (`Error:` + pelna lista, jak w `_finish_pl_sheets`)
  i jedno zdanie w ARCHITECTURE 4.7 / CLAUDE.md o kodzie wyjscia LAZ.

### N7 (SREDNIA) — nieudana przebudowa CZ KASUJE poprzedni wynik; ARCHITECTURE nazywa to "zbedne"

- **Deklaracja:** ARCHITECTURE.md "Nieudana budowa a poprzedni wynik":
  "Wlasne `except BaseException: dst.unlink(...)` ma dalej wylacznie tor CZ
  (`providers/cuzk/dmr.py::_warp_to_grid`) — tam jest ono rownie zbedne
  (zapis idzie przez plik tymczasowy)"; docstring `_warp_to_grid`
  (`dmr.py:517-518`) "Zapis jest atomowy: plik docelowy powstaje dopiero
  z gotowej kopii tymczasowej". ADR-027 (Konsekwencje) mowi natomiast
  wprost: "tor CZ jest tu wyjatkiem i przy awarii kasuje plik docelowy".
- **Faktycznie:** `dmr.py:556-559` — `os.replace(tmp, dst)` w `try`,
  a w `except BaseException: dst_path.unlink(missing_ok=True)`. Przy
  `--force` (albo po recznym usunieciu tylko sidecara) nieudany warp
  (siec przy `exportImage` jest wczesniej, ale blad GDAL/dysku juz nie)
  usuwa POPRZEDNI, poprawny plik `bbox/<coords>.tif` lub kafel TM33.
  `unlink` nie jest "zbedny" — jest szkodliwy; ADR-027 opisuje to
  poprawnie, ARCHITECTURE i docstring bagatelizuja.
- **Dowod:** `exp_cz_warp.py`: istniejacy `bbox_result.tif`, zrodlo
  nieczytelne -> `RasterioIOError`; "poprzedni plik docelowy istnieje po
  nieudanym warpie CZ: False".
- **Kierunek:** KOD (usunac `dst_path.unlink` — zapis i tak jest przez tmp
  + `os.replace`, wiec gwarancja "stary plik przezywa awarie" bylaby wspolna
  dla PL i CZ; `--help --force` juz ja obiecuje, tylko z dopiskiem "PL")
  albo DOKUMENT (ARCHITECTURE: "tam kasuje poprzedni wynik — wyjatek
  ADR-027"). Tor CZ po D1 nie jest juz zamrozony (ADR-024 errata 2 pkt 5).

### N8 (SREDNIA) — `landcover download` z blednym `--property`/`--year`/`--depth`/`--stat` konczy sie "Error: ValueError: ..." z podpowiedzia KARTOGRAF_DEBUG

- **Deklaracja:** `cmd_landcover_download` docstring/`--help`: "Options:
  bdod, cec, ..." i "Exit code (0 for success, 1 for error)";
  CLAUDE.md: `KARTOGRAF_DEBUG=1` to "pelny traceback zamiast skroconego
  `Error: ...`" — podpowiedz o DEBUG sugeruje blad wewnetrzny.
- **Faktycznie:** providery walidują parametry `ValueError`
  (`soilgrids.py:208-225`, `corine.py:355-361`), a `cmd_landcover_download`
  (`cli/landcover_cmd.py:617-625`) lapie tylko `NotImplementedError`,
  `DownloadError`, `ParseError`, `ValidationError`. `ValueError` leci do
  bariery `main` (`cli/commands.py:99-104`): `Error: ValueError: Invalid
  property: foo ...` + "Ustaw KARTOGRAF_DEBUG=1, aby zobaczyc pelny
  traceback." Kod 1 jest poprawny, dzieje sie przed siecia; mylacy jest
  komunikat (blad uzytkownika przedstawiony jak awaria programu).
- **Dowod:** `exp_cli.py` (gniazdo zablokowane): `landcover download
  --source soilgrids --godlo N-34-130-D --property foo -> rc=1, stderr:
  Error: ValueError: Invalid property: foo. Available: ... | Ustaw
  KARTOGRAF_DEBUG=1 ...`; tak samo `--source corine --year 1999`.
- **Kierunek:** KOD — dopisac `ValueError` do `except` w
  `cmd_landcover_download` (jak `ValidationError`), albo providery powinny
  rzucac `ValidationError` (spojnie z reszta CLI).

### N9 (NISKA) — CORINE/SoilGrids ponawiaja 404 trzykrotnie (6 s) i nie niosa `status_code`

- **Deklaracja:** CHANGELOG [0.7.0] (nowa polityka) jest jawnie zawezony do
  GUGiK + wspolnego transportu, wiec to nie sprzecznosc; CLAUDE.md "Max 3
  proby retry" pozostaje prawdziwe. Mylace jest tylko to, ze
  `DownloadError.status_code` ("kod HTTP ostatniej proby") istnieje w
  `exceptions.py:56-57` dla wszystkich torow, a w tych dwoch zawsze `None`.
- **Faktycznie:** `corine.py:929-964` i `soilgrids.py:441-476` — wlasne
  petle `for attempt in range(1, MAX_RETRIES + 1)` bez `is_retryable`/
  `retry_wait`/`http_failure`.
- **Dowod:** `exp_retry.py`: `CorineProvider._download_with_retry 404 ->
  proby=3 sleep=[2, 4] -> DownloadError status_code=None`; SoilGrids tak samo.
- **Kierunek:** KOD (przepiac na helpery z `transport/http.py`, jak GUGiK)
  — albo zostawic i dopisac do CHANGELOG/ARCHITECTURE, ze CORINE/SoilGrids
  maja stara polityke.

### N10 (NISKA) — "120 s dla CORINE przez TERYT" to timeout martwej sciezki

- **Deklaracja:** CLAUDE.md i SCOPE.md 3.2: "120 s dla BDOT10k (wszystkie
  tryby), CORINE przez TERYT oraz SoilGrids przez bbox i HSG".
- **Faktycznie:** `CorineProvider.download_by_teryt` (`corine.py:730-746`)
  zawsze rzuca `NotImplementedError` (CLI: `Error: CORINE Land Cover does
  not support TERYT downloads`, kod 1 — `exp_cli.py`). Domyslne `timeout=120`
  istnieje w sygnaturze, ale nigdy nie jest uzyte.
- **Kierunek:** DOKUMENT — usunac "CORINE przez TERYT" z listy timeoutow
  (SoilGrids przez TERYT jest juz w SCOPE opisany jako NotImplementedError).

### N11 (NISKA) — `Bdot10kProvider.DEFAULT_TIMEOUT = 60` jest martwa stala

- **Deklaracja:** CLAUDE.md "120 s dla BDOT10k (wszystkie tryby)" —
  zgodne z sygnaturami (`download_by_teryt/godlo/bbox` = 120,
  `exp_defaults.py`).
- **Faktycznie:** `bdot10k.py:123` deklaruje `DEFAULT_TIMEOUT = 60`, do
  ktorego nic sie nie odwoluje (grep: jedyne wystapienie to definicja).
  Czytelnik kodu widzi "60", dokument "120".
- **Kierunek:** KOD — usunac stala albo uzyc jej jako domyslnej (wtedy
  dokument na 60). Dzis sygnatury sa zrodlem prawdy.

### N12 (NISKA) — README: liczby testow nieaktualne (2057/2058 vs 2105)

- **Deklaracja:** README.md: "zweryfikowano offline (2058 testów)",
  "tests/ # Testy (2057 offline + 16 live)", "Po fali naprawczej: 2057
  testów offline i 16 testów live".
- **Faktycznie:** `pytest --collect-only`: **2105** offline (`-m "not
  live"`) + **16** live = 2121. CLAUDE.md "16 testow sieciowych" zgodne.
- **Kierunek:** DOKUMENT (README; dwa rozne stare numery w jednym pliku).

### N13 (NISKA) — ARCHITECTURE 2: "CLI nie importuje juz `transport` wcale"

- **Deklaracja:** ARCHITECTURE.md sekcja 2 (graf "ZMIERZONY na drzewie
  importow": `cli ──> download, landcover, hydrology, providers, sources,
  transform, core, cache`) i uwaga "CLI od 2026-09-28 nie importuje juz
  `transport` wcale".
- **Faktycznie:** `cli/download_cmd.py:1654` — `from
  kartograf.transport.mosaic import has_valid_pixels` (import leniwy
  w `_warn_cz_all_nodata`, N2 z fali naprawczej). Krawedz `cli -> transport`
  istnieje.
- **Kierunek:** DOKUMENT (graf + zdanie), albo KOD: przeniesc kontrole
  "caly nodata" CZ do providera/biblioteki, jak `all_nodata` w torze PL.

### N14 (NISKA) — nazwy plikow landcover "`.gpkg`" dla CORINE/SoilGrids

- **Deklaracja:** ARCHITECTURE 4.8 "`<provider>_teryt_<teryt>.gpkg`,
  `<provider>_bbox_...gpkg` albo `<provider>_godlo_<godlo>.gpkg`"; CHANGELOG
  "jest `corine_land_cover_godlo_N-34-130-D.gpkg`".
- **Faktycznie:** `_generate_output_path` daje `.gpkg`, ale provider
  podmienia rozszerzenie: CORINE `with_suffix(".png")` (WMS, `corine.py:422`)
  / `with_suffix(".tif")` (CLMS, `corine.py:532,630`), SoilGrids
  `with_suffix(".tif")` (`soilgrids.py:314`). Zwracana sciezka i sidecar
  dotycza pliku `.png`/`.tif`. (Dla BDOT10k SHP — patrz N1, tam podmiany
  nie ma.)
- **Kierunek:** DOKUMENT ("baza nazwy `<provider>_godlo_<godlo>`,
  rozszerzenie wg zrodla: `.gpkg` / `.tif` / `.png`").

### N15 (NISKA) — ADR-023 (f).1: `extra.parent_request` "zawsze w trybie --bbox/--geometry"

- **Deklaracja:** DECISIONS.md ADR-023 (f) pkt 1: "`extra.parent_request`
  jest zapisywany **zawsze** w trybie `--bbox`/`--geometry` (auto I jawny
  `--country`)".
- **Faktycznie:** tor LAZ (`_write_laz_sidecar`, `download_cmd.py:1478-1508`)
  nie zapisuje `parent_request` w zadnym trybie. ARCHITECTURE 3.4 i README
  (tabela sidecara) juz to przyznaja ("poza torem LAZ"), ADR nie ma erraty.
- **Kierunek:** DOKUMENT — errata w ADR-023 (jak pkt 7), albo KOD
  (dopisac `parent_request` w `_write_laz_sidecar` — `_build_parent_request`
  jest gotowe), co domknie klucz grupowania dla Hydrografu.

### N16 (NISKA) — docstringi: lista providerow i zakres cache

- `LandCoverManager` (`landcover/manager.py:842-844, 900, 937`): "Provider
  instance or name ("bdot10k", "corine")" — pomija `soilgrids`, ktory jest
  w `PROVIDERS` i w CLI.
- `MetadataCache` docstring klasy (`cache/metadata.py:46-47`): "Caches WMS
  lookup results (skorowidz records and TERYT codes)" — pomija
  `sheet_cache` (CZ, 30 dni), ktory docstring MODULU i CLAUDE.md opisuja.
- **Kierunek:** DOKUMENT (docstringi).

### N17 (NISKA) — `KARTOGRAF_DEBUG=1` nie daje tracebacku dla `KartografError`

- **Deklaracja:** CLAUDE.md "`KARTOGRAF_DEBUG=1` — pelny traceback zamiast
  skroconego `Error: ...` z CLI".
- **Faktycznie:** `cli/commands.py:95-104` — `KartografError` jest zawsze
  skracany do `Error: <msg>` (pierwszy `except`, bez sprawdzania zmiennej);
  DEBUG dziala tylko dla pozostalych wyjatkow. Dla wyjatkow Kartografu
  docierajacych do bariery (rzadkie — wiekszosc jest tlumaczona nizej)
  tracebacku nie ma.
- **Dowod:** `exp_misc.py` z `KARTOGRAF_DEBUG=1`: `ValidationError` ->
  `rc=1 stderr='Error: boom-kartograf'` (bez tracebacku); `RuntimeError`
  -> przepuszczony z tracebackiem.
- **Kierunek:** DOKUMENT (doprecyzowac "dla bledow spoza `KartografError`")
  albo KOD (w trybie DEBUG `raise` takze dla `KartografError`).

---

## Deklaracje sprawdzone i ZGODNE

Timeouty (`exp_defaults.py`, `inspect.signature`):
- NMT/NMPT arkusz i WCS 30 s (`gugik.py:149,241,359`; NMPT dziedziczy);
  orto 60 s (`gugik_orto.py:91`); LAZ discovery/GetCapabilities 30 s
  (`WFS_TIMEOUT`), kafel 60 s; BDOT10k 120 s we wszystkich trybach;
  CORINE bbox/godlo 60 s; SoilGrids bbox 120 s, przez godlo 60 s
  (`base.py:313`), HSG 120 s (`hsg.py:360,406`); CUZK 60 s
  (`dmr.py:62`, `CuzkDmrProvider()._client._timeout`, `SheetIndex`).

Retry (`exp_retry.py`):
- Wspolny transport i tory GUGiK (NMT/orto/LAZ/BDOT10k): 404 -> 1 proba,
  500/503 -> 3 proby z backoffem, 429 z `Retry-After: 7` -> przerwy 7 s,
  `DownloadError.status_code` = kod ostatniej proby, `MAX_RETRY_AFTER=60`.

Kody wyjscia i walidacje CLI (`exp_cli.py`, gniazdo zablokowane — zadna
sciezka nie dotknela sieci):
- bbox poza obwiedniami PL/CZ -> `Error:` kod 1; `--target-crs` z godlem PL
  i CZ -> kod 1; godlo CZ + `--country pl` (i odwrotnie) -> kod 1; orto +
  `--vertical-crs`, nmpt + 5m, PL + 2m, CZ + 1m, CZ + orto/laz ("etap 2"),
  CZ + KRON86 (remedium), `--target-crs` + `--system 2000` / `--product nmpt`
  -> kod 1 z deklarowanymi komunikatami; bledny bbox, brak/nadmiar selekcji
  -> kod 1; CORINE/SoilGrids przez TERYT -> `NotImplementedError` jako
  `Error:` kod 1; `cache stats` drukuje `Record entries`/`TERYT`/`Sheet`.
- Tryb listy/hierarchii (`exp_misc.py`, `_finish_pl_sheets`): >=1 plik +
  braki pokrycia -> `Warning:` kod 0; same braki -> `Error:` kod 1; twarda
  awaria -> `Error:` z lista, kod 1. Regula `auto` (kod 0 + `Warning:` przy
  sukcesie jednego kraju, `max(exit_codes)` dla jawnego `--country`) —
  sciezka `_dispatch_area` (`download_cmd.py:773-783`).
- `--country auto` domyslne; `--workers` 4 w CLI, `DownloadManager(
  max_workers=1)` w bibliotece; `--vertical-crs`/`--resolution`/`--system`
  jako sentinele `None` rozwiazywane per kraj (PL: 1m/EVRF2007/1992, CZ:
  2m/Bpv) — ADR-023 (g).

Storage i sidecar (`exp_storage_cache.py`):
- Sciezki zgodne z tabela ARCHITECTURE 3.3 dla NMT 1m/5m, KRON86/EVRF2007,
  PL-1992/PL-2000, NMPT, orto (bez `{vcrs}`), LAZ (`uklad=` jawne vs
  z formatu godla), CZ dmr5g/dmr4g; `vertical_crs=None` -> `ValidationError`
  z nazwa wymiaru.
- Sidecar arkusza: `horizontal_crs` z ukladu pliku (PL-2000 z plikiem
  w EPSG:2180 -> ostrzezenie i uklad pliku, N8), `vertical_crs=EPSG:9651`
  dla EVRF2007 (rodzina -> realizacja), `nodata` z naglowka ASC,
  `transform=null`, `extra.source` z `source_info`, `extra.parent_request`;
  pominiety arkusz dopisuje `extra.parent_requests` bez zmiany
  `parent_request` (N4).
- `vertical_crs_code`: EVRF2007 -> 5621, EVRF2007-PL -> 9651, KRON86 ->
  9650, Bpv -> 8357 (tabela CHANGELOG).

Cache:
- `record_cache`/`teryt_cache` TTL 7 dni, `sheet_cache` 30 dni (trafienie
  +29 d, brak +31 d), `stats()` ma `record_count/teryt_count/sheet_count`,
  plik `.kartograf_cache.db` w cwd; `--force` = brak cache w torach PL
  (`_pl_metadata_cache`).

Pozostale:
- `find_sheets_for_bbox`: bbox rowny arkuszowi w EPSG:4326 -> 1 godlo,
  w EPSG:2180 -> 9; `system="1965"` -> `ValidationError`.
- `DownloadManager.download_bbox` pod EVRF2007 -> `ValidationError` bez
  sieci (mock sesji nie zostal wywolany); 5m -> `ValueError`; deskryptor
  `pl.gugik.nmt_1m` ma kanal WCS tylko z `EPSG:9650`.
- LAZ `--year` nieistniejacy -> `rocznik 1999 nie istnieje w usludze
  EVRF2007 (dostepne: 2024, 2023)` bez sugestii ponowienia; osie WFS (N,E)
  w `_query_layer`; `cache=` w `GugikLazProvider` opisany jako placeholder.
- `AuthProxyClient.is_available()` na non-macOS bez `CLMS_CREDENTIALS`
  zwraca False bez podprocesu (`auth/client.py:256-258`).
- HSG: `sandy_loam=B`, `clay_loam=C`, `silty_clay_loam=C` (ADR-025);
  CUZK `MAX_EXPORT_WIDTH/HEIGHT/PIXELS` = 15000/4100/4 000 000;
  `SUPPORTED_TARGET_CRS` = (2180, 5514, 3045) wspolne dla CLI `choices`;
  `WARP_MARGIN_PX=4`; obwiednie PL/CZ jak w ADR-023 pkt 4.
- Wycinek PL (`download/cutout.py`): fail-fast przed siecia
  (`prepare_pl_cutout`), skip bez sieci z `missing_sheets/off_grid_sheets`
  z sidecara, `_require_matching_provider` przed pobraniem, kontrola dysku
  z policzonymi brakami (N9), `GridMismatchError(ValidationError)`,
  `_reject_pl2000_sheets`, zapis atomowy bez kasowania poprzedniego pliku
  (PL), `extra.sheet_sources/missing_sheets/off_grid_sheets/parent_request`.
- `download_hierarchy` docstring "N-34-130-D-d -> 16 arkuszy" (zmierzone 16);
  16 testow `live` (CHANGELOG/CLAUDE.md); `kartograf --version` = 0.7.0-dev;
  `landcover` `--geometry` liczy obwiednie w EPSG:2180
  (`get_overall_bbox(target_crs="EPSG:2180")`).

---

## Podsumowanie

| Waga | Liczba | Numery |
|---|---|---|
| WYSOKA | 1 | N1 |
| SREDNIA | 7 | N2, N3, N4, N5, N6, N7, N8 |
| NISKA | 9 | N9–N17 |

Top 5 do decyzji przed 0.7.0: **N1** (SHP = ZIP pod `.gpkg`, kod),
**N7** (CZ `--force` kasuje poprzedni wynik przy awarii; ADR-027 vs
ARCHITECTURE, decyzja kod/dokument), **N3** (GetCapabilities 10 s
niedokumentowane, kod), **N5** (brak ponowien w `CuzkClient.query`
i TERYT BDOT10k, kod), **N4** (bezwarunkowe "3 proby" w czterech
dokumentach po 9bcc040, dokument). N2 (README "kod 1" na pograniczu) to
jednozdaniowa poprawka README.
