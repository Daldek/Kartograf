# E2E 0.8.0 przed tagiem - wycinek E: `project`, odczyt magazynu (API dla Archiwisty), `parse`, `catalog`, `cache`, warstwa komend, tryby aktualizacji

Data: 2026-10-19. Agent `E2eProjectStore`. Kod: `develop @ e019126a` (wheel z `git archive HEAD`, `kartograf 0.8.0`). Repozytorium nie bylo edytowane.

## Werdykt

**Brak P1 (zadnego blednego/cichego wyniku danych, awarii z tracebackiem, utraty danych).** `project` (init/add/remove/download/status/verify, tryby `--check-updates`/`--upgrade`/`--force`, odtwarzanie, rownolegle procesy, SIGINT, offline), warstwa komend, `parse`, `catalog`, `cache`, dokumenty JSON i parytet CLI = biblioteka dzialaja zgodnie z USAGE 8-9 i ARCHITECTURE 3.3.1/3.5/3.6.

**Dwa znaleziska P2 - oba w API odczytu magazynu (Archiwista), nie w pobieraniu:**

- **P2-1** `link_target()` zwraca `None` dla prawidlowych dowiazan twardych na udziale SMB zamontowanym bez `serverino` (nlink=1 chwilowo po odczycie pliku); ta sama przyczyna powoduje zbedny zapis sidecara dowiazania przy ponownym `elevation download`. Na lokalnym ext4 stabilnie.
- **P2-2** Kafel LAZ: `Sidecar.unit` i `file_footprint()` biora bbox ZADANIA (100 x 100 m) zamiast kafla (565 x 586 m); `iter_store(units=[sidecar.unit])` nie odnajduje kafla - sprzeczne z zapewnieniem z ARCHITECTURE 3.3.1 ("`unit` ... zamyka petle odswiezania").

Pozostale uwagi to P3 (25 pozycji, sekcja nizej; 4 z nich to rozjazdy dokumentacji). Do tagu rekomenduje: naprawic albo jawnie opisac P2-1 i P2-2 (dla Archiwisty istotne); P3 bez wplywu na tag.

## Liczby

| Miara | Wartosc |
|---|---|
| Wywolania CLI (kazde z kodem wyjscia, czasem, logiem) | 718 (626 unikalnych id; rc 0: 438, rc 1: 46, rc 2: 142), ok. 21 min czasu CLI; plus 6 procesow z `Popen` (SIGINT x2, rownolegle x4) |
| Sprawdzenia biblioteki (skrypty `t_*.py`, online + offline pod `unshare -rn`) | 493, w tym 489 PASS; 4 FAIL = dwa sprawdzenia `link_target` x 2 przebiegi (P2-1) |
| Przypadki w tabeli (scenariusze, sekcje A-K) | 133 = 109 CLI + 24 biblioteka: 102 OK, 28 OK z uwaga P3 (OK\*), 3 BLAD (P2-1, P2-2, P3-1) |
| Znaleziska | P1: 0; P2: 2; P3: 25 (w tym 4 dotyczace dokumentacji: P3-3, P3-7, P3-14, P3-19) |
| Dane na udziale | ok. 500 MB w 162 plikach (limit 1,5 GB) |

PASS (OK + OK\*) = 130/133 przypadkow, FAIL (BLAD) = 3/133.

## Zakres

Wycinek E z zadania: grupa `project` (init, add, remove, download, status, verify), API odczytu magazynu (`iter_store`, `list_segments`, `list_partitions`, `read_sidecar`, `describe_segment`, `file_footprint`, `link_target`, `pinned_transform`, `describe_store`, `list_store_entries`, `read_store_sidecar`), `parse`, `catalog`, `cache stats/clear/path`, `--version`, bledy globalne `--json` (kod 2), warstwa komend (`data_commands`, `parse_command`, `validate_command`, `format_command`, `run_command`, `check_command`), tryby aktualizacji (`--check-updates`, `--upgrade`, `--force`, `--plan`), wersjonowany magazyn (`versions/`, dowiazania, `full_sheet/`), praca offline (`unshare -rn`). Oraz literalna weryfikacja twierdzen USAGE 8 i 9, ARCHITECTURE 3.3.1/3.5/3.6/4.11 i `llms.txt` w tym zakresie.

Poza zakresem (inne wycinki): dostepnosc, szczegoly torow NMT/NMPT/orto/LAZ/CZ/granice/gleby poza tym, co potrzebne do zbudowania magazynu i zadan projektu.

## Srodowisko

- Wheel `kartograf-0.8.0` (z `git archive HEAD`, `e019126a`) z extra `[mcp]` w czystym venv Pythona 3.13; wyłącznie `venv/bin/kartograf` i `venv/bin/python` (nie `.venv` repo, nie `python -m` z repo). Zaleznosci: pyproj 3.8.0, rasterio 1.5.2, pyogrio 0.13.0, numpy 2.5.4, requests 2.34.2, mcp 2.3.0.
- cwd kazdego wywolania: `<cwd-E>` (swiezy `.kartograf_cache.db` lokalnie; operacje `project` jej nie tworza - sprawdzone). Debian 13, jadro 6.12.94.
- `<katalog-danych>` = udzial SMB (cifs vers=3.1.1, `cache=strict`, `actimeo=1`, **bez `serverino`**: hardlinki dzialaja po stronie serwera, ale numery i-wezlow sa niestabilne - `samefile` falszywe, a `st_nlink` klienta bywa chwilowo 1). Kontrole na lokalnym ext4 (syntetyczne magazyny w `<cwd-E>/synth`, jeden magazyn kontrolny usuniety).
- Uslugi na zywo: GUGiK (skorowidz WFS/WMS, `opendata.geoportal.gov.pl`, WCS), PRG WFS, CUZK (`openzu`, feed ATOM, ImageServer), ISRIC WCS, CLMS WMS (podglad). Bez `CLMS_CREDENTIALS` (decyzja uzytkownika).
- **Awarie uslug:** 3 x `Warning: WFS GetCapabilities .../NumerycznyModelTerenuEVRF2007/WFS/Skorowidze: proba 1/3 nieudana (zerwane albo odrzucone polaczenie); ponowienie za 2s` (`avail-nmt-sheet`, `u-year2022-check`, `i-resume`) - kazdy raz powtorzenie po 2 s udane, zadne wywolanie nie padlo z powodu sieci. To usluga (reset polaczenia), nie blad Kartografu. CUZK `openzu` wolne: ortofoto SM5 (64 MB) 146 s.

## Magazyn zbudowany do testow (projekt A, 14 przypiec w 10 zadaniach)

Projekt `projekt-a` -> magazyn `magazyn` (`<katalog-danych>`); zadania dodane z roznych grup, w tym wklejka z `elevation availability` (`W projekcie: kartograf project add NAZWA elevation download ... --year 2025`).

| zadanie | rola | jednostka | segment | rozmiar [B] | etykieta | sha8 | dataset (sidecar) | CRS poz./pion. |
|---|---|---|---|---|---|---|---|---|
| teren | output | M-34-64-D-d-1-2 | nmt/pl_1992_1m_evrf2007 | 37 004 903 | 2025-04-28_83137 | e041a794 | pl.gugik.nmt_1m | EPSG:2180/9651 |
| orto-wycinek | output | 566000_243000_566200_243200 | orto/pl_1992_high_0.1m | 12 012 733 | 2026-10-19 | 786b6425 | pl.gugik.orto | EPSG:2180 |
| granice | output | 566000_243000_567000_244000 | boundaries/pl_prg_gmina | 241 664 | 2026-10-19 | 9c06c4bc | pl.gugik.prg | EPSG:2180 |
| gleba-il | output | 566000_243000_567000_244000 | soil/global_soilgrids_clay_0-5cm_mean | 591 | 2.0 | f07b1e63 | global.isric.soilgrids | EPSG:4326 |
| gleby-hsg | output + 3 x input | ... | hsg/..., soil/{clay,sand,silt}... | 1080 / 3 x 591 | 2.0 | a86d345f / f07b1e63 | global.isric.soilgrids | EPSG:4326 |
| pokrycie | output | 2476 | landcover/pl_bdot10k_gpkg | 11 771 904 | 2026-10-19 | ebfdf70e | pl.gugik.bdot10k | EPSG:2180 |
| teren-cz | output | CTES96 | nmt/cz_dmr4g_bpv | 780 401 | 2026-10-19 | a1e327bb | cz.cuzk.dmr4g | EPSG:5514/8357 |
| laz | output | 83134_1728146_M-34-64-D-d-1-4-4-1.laz | laz/pl_1992_evrf2007 | 59 171 206 | 2025-04-28_83134 | 308fc022 | pl.gugik.laz | EPSG:2180/9651 |
| corine | output | 566000_243000_567000_244000 | landcover/eu_corine_2018_preview | 194 | 2026-10-19 | 31479dd1 | eu.clms.corine | EPSG:3857 |
| pogranicze | output x2 (PL + CZ) | 472994.992_209467.4453_473717.8262_210026.7252 | nmt/pl_1992_1m_evrf2007, nmt/cz_dmr5g_bpv | 2 360 198 / 405 036 | 2026-10-19 | 545a5760 / ed780a6e | pl.gugik.nmt_1m, cz.cuzk.dmr5g | EPSG:2180 |

Dla kazdego przypiecia sprawdzono: `kartograf-meta/1` (schema), `dataset`/`dataset_key`, CRS, `request`, `sha256` sidecara == SHA-256 pliku (wszystkie 14/14 zgodne). Dodatkowe magazyny: `magazyn-upg` (lot 2022 + 2025, `full_sheet/`), `magazyn-p2` (projekt przypiety do 2022 -> `--upgrade` 2025), `magazyn-cz` (ortofoto SM5, 4 pliki), `magazyn-geo` (zadanie z geometria GPKG), `magazyn-area`, `magazyn-int`, `magazyn-par` (rownolegle procesy), `magazyn-lib`/`magazyn-cli` (parytet) oraz syntetyczne magazyny w `<cwd-E>/synth` (384 sloty NMT, 1229 wpisow; magazyn z kodami problemow; manifesty uszkodzone).

Uwaga o danych: gleby/HSG dla bbox 566000,243000,567000,244000 (centrum Krakowa) to rastry 4 x 6 px z **samymi zerami** (clay=sand=silt, identyczne sha8; HSG w calosci nodata) - tak odpowiada ISRIC (sprawdzone niezaleznym zapytaniem WCS; teren wiejski `626000,480000,628000,482000` ma wartosci 87-94); zgodnie z USAGE 7 ("SoilGrids zwraca w obszarach maskowanych 0"). Zadania projektu pozostawiaja to bez komunikatu (patrz P3-16).

## Tabela przypadkow

Legenda: kolumna `#` = id wywolania w logu (`<cwd-E>/logs/<id>.{cmd,out,err,rc,time}`; `(+N)` = N wariantow z tej samej rodziny, rc i czasy zsumowane). Ocena: **OK** zgodne z oczekiwaniem/dokumentacja; **OK\*** zgodne, z uwaga P3 (numer odsyla do sekcji znalezisk); **BLAD** niezgodne. `<katalog-danych>` = sciezka udzialu; `<cwd-E>` = katalog roboczy. Czasy to czas calego wywolania (proces + siec).


#### A. parse (offline)

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| parse-pl1992 | `kartograf parse N-34-130-D-d-2-4` | PL-1992 1:10000: skala, czlony, uklad | rc 0; 0.6 s: Godlo/Skala 1:10000/Uklad 1992/7 czlonow | OK |
| parse-pl1992-json | `kartograf parse N-34-130-D-d-2-4 --json` | kartograf-sheet/1, schema pierwszy | rc 0; 0.6 s: 908 B, 1 dokument, stderr pusty; bounds EPSG:2180 | OK |
| parse-pl2000 | `kartograf parse 6.179.12.20` | PL-2000 1:2000, strefa 6, EPSG:2177 | rc 0; 0.6 s: OK; tekst powtarza 'strefa'/'Strefa' (znane, PROGRESS) | OK* (P3-22) |
| parse-sm5 | `kartograf parse CTES96` | CZ SM5, EPSG:5514, bez zasiegu offline | rc 0; 0.6 s: OK; `bounds: null` (rama z indeksu CUZK) | OK |
| parse-tm33 (+3) | `kartograf parse 302_5550` | TM33 (EPSG:3045, zasieg), 2-literowe SM5 AS91, ZTM sjtsk i etrs89 | rc 0,0,0,0; 2.4 s: wszystkie rc 0, poprawny uklad i lista komend | OK |
| parse-hier (+5) | `kartograf parse N-34-130-D --hierarchy` | --hierarchy / --children / --descendants (PL) | rc 0,0,0,0,0,0; 4.0 s: hierarchia 1:100000->1:1000000; 4 potomne; 64 arkusze do 1:10000 | OK |
| parse-lower | `kartograf parse n-34-130-d-d-2-4` | godlo malymi literami | rc 0; 0.6 s: znormalizowane do N-34-130-D-d-2-4, rc 0 | OK |
| parse-cz-hier (+2) | `kartograf parse CTES96 --hierarchy` | flagi hierarchii dla CZ | rc 2,2,2; 1.7 s: rc 2, `invalid_input`, `details.option` (children), komunikat 'tylko godel PL' | OK |
| parse-bad-zzz (+1) | `kartograf parse ZZZ` | zle godlo ZZZ | rc 2,2; 1.1 s: rc 2; JSON `invalid_sheet_code`, hint z formatami godel | OK* (P3-10) |
| parse-bad-extra-level (+5) | `kartograf parse N-34-130-D-d-2-4-9-9-9` | godla spoza nomenklatury / puste / 6.179 | rc 2,2,2,2,2,2; 3.4 s: rc 2 (ParseError), komunikaty z zakresami ('dozwolone: 33-35', '01-25') | OK* (P3-10) |
| parse-bad-desc (+1) | `kartograf parse N-34-130-D --descendants 1:99` | zla skala docelowa | rc 2,2; 1.1 s: rc 2; lista dozwolonych skal / 'musi byc wieksza' | OK |
| parse-noarg (+5) | `kartograf parse` | brak argumentu / nieznana flaga / 2 argumenty / -q | rc 2,2,2,2,2,2; 3.2 s: rc 2; `usage_error`; `-q` odrzucone z lista komend, ktore je maja | OK* (P3-9) |

#### B. catalog (offline)

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| cat-text (+1) | `kartograf catalog` | przeglad: 13 grup, 41 komend; JSON rekordy w 1 linii | rc 0,0; 1.2 s: 7629 znakow (jak USAGE), widok overview, 38 narzedzi MCP, 13 supports_check | OK |
| cat-group (+2) | `kartograf catalog elevation` | grupa (tekst/JSON/--params) | rc 0,0,0; 1.7 s: 6573 B JSON (full), tekst z parametrami dla `soil --params` | OK |
| cat-cmd (+2) | `kartograf catalog elevation download` | opis komendy: parametry, ograniczenia, przyklady | rc 0,0,0; 1.7 s: elevation download: 29754 znakow, 30 parametrow, 4 przyklady (jak USAGE) | OK |
| cat-cmd-parse (+5) | `kartograf catalog parse` | komendy manage/query i tylko-API (project add, parse, find_sheets, store_overview) | rc 0,0,0,0,0,0; 3.7 s: rc 0; `cli: null` dla API-only; funkcje i result_schema zgodne z USAGE 9.1 | OK |
| cat-params-json | `kartograf catalog --params --json` | caly katalog z tabelami | rc 0; 0.6 s: 299368 znakow; exit_codes 4, errors 14, schemas 16; widok full | OK |
| cat-bad-group (+3) | `kartograf catalog nonexistent` | nieznana grupa / komenda | rc 2,2,2,2; 2.3 s: rc 2; `invalid_input` z `details.option`+`allowed` i hintem 'Dozwolone wartosci...' | OK |
| cat-three (+2) | `kartograf catalog elevation download extra` | 3. argument / sama nazwa komendy / zla flaga | rc 2,2,2; 1.9 s: rc 2; `usage_error`; `command: null` dla `--nope`; usage calego programu zamiast `catalog` | OK* (P3-11) |
| par-cat-ov (+6) | `kartograf catalog --json` | CLI --json == get_catalog().to_json() (7 widokow) | rc 0,0,0,0,0,0,0; 4.4 s: bajtowo rowne (7/7) | OK |
| ca-g-boundaries-plain | `kartograf catalog boundaries` | przeglad 13 grup x 4 warianty (tekst, --params, --json, --params --json) | rc 0; 0.7 s: 52/52 wywolan rc 0, stderr pusty (sweep `catalog <grupa>`) | OK |
| ca-c-elevation_download-t | `kartograf catalog elevation download` | 41 komend x tekst i JSON | rc 0; 0.7 s: 82/82 rc 0 (sweep `catalog <komenda>`) | OK |
| ca-h-parse | `kartograf parse --help` | `--help` 37 lisci | rc 0; 0.9 s: 37/37 rc 0 i `--json` w pomocy; 12 lisci (list-sources/list-layers/cache/project remove|status|verify bez `Przyklady`) | OK* (P3-21) |

#### C. cache i --version

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| cache-path-0 (+5) | `kartograf cache path` | bez pliku bazy | rc 0,0,0,0,0,0; 3.4 s: path: sama sciezka; stats: `exists:false`, 'plik jeszcze nie utworzony'; clear: `cleared:true` bez bazy | OK* (P3-13) |
| cc-stats-1 (+3) | `kartograf cache stats` | po availability (2,3 MB), clear, stats | rc 0,0,0,0; 2.6 s: stats: rekordy 1, kampanie 1, obszary skorowidza 5; po clear baza 61 KB pusta, `exists:true` | OK |
| cc-path-corrupt (+5) | `kartograf cache path` | uszkodzona baza (tekst zamiast SQLite) | rc 0,0,1,1,0,0; 3.5 s: path rc 0 (nie otwiera bazy); stats rc 1 `cache_error` + hint 'kartograf cache clear'; clear usuwa plik (`Usunieto nieczytelny plik cache`) | OK |
| cc-avail-corrupt | `kartograf elevation availability --product nmt --sheet M-34-64-D-d-1-2 --json` | availability przy uszkodzonej bazie | rc 0; 4.3 s: rc 0; dokument z `notices` `cache_disabled` (praca bez cache) | OK |
| cc-stats-dir (+1) | `kartograf cache stats --json` | katalog w miejscu pliku bazy | rc 1,1; 1.2 s: stats rc 1 `cache_error`; clear rc 1 z hintem 'Usun plik recznie' | OK |
| cc-ro-stats (+2) | `kartograf cache stats --json` | cwd tylko do odczytu | rc 0,0,0; 6.5 s: parse/stats rc 0; availability rc 0 z `cache_disabled` ('nieczytelny ... unable to open database file') | OK* (P3-13) |
| par-cache-stats (+1) | `kartograf cache stats --json` | CLI --json == get_cache_info()/get_cache_path() | rc 0,0; 1.2 s: rowne (2/2) | OK |
| ver-run | `kartograf --version` | `kartograf --version` | rc 0; 0.6 s: `kartograf 0.8.0` (== __version__ == catalog.kartograf_version == sidecar.kartograf_version) | OK |

#### D. Bledy globalne (--json)

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| g-unknown-cmd (+4) | `kartograf frobnicate` | nieznana komenda / podkomenda | rc 2,2,2,2,2; 3.1 s: rc 2; JSON `usage_error`, `command: null`, hint 'catalog <grupa> <komenda> --params'; komunikaty argparse po angielsku | OK* (P3-9) |
| g-bad-flag-dl (+5) | `kartograf elevation download --bogus --json` | zla flaga / zla wartosc / brak wartosci / skrot `--prod` | rc 2,2,2,2,2,2; 3.6 s: rc 2; `usage_error` z `command: elevation download`, hint z przykladem; skroty flag wylaczone | OK* (P3-9) |
| g-json-first (+3) | `kartograf --json parse N-34-130-D-d-2-4` | `kartograf --json parse ..` / `--json --version` / `--help --json` / `--opcja=wartosc` | rc 2,0,0,0; 2.8 s: `--json` przed komenda: rc 2 z podpowiedzia gdzie ja podac; `--json --version` drukuje wersje rc 0; `--help --json` pomoc rc 0 | OK |
| g-noargs (+6) | `kartograf` | bez komendy / sama grupa / sam `project add` | rc 2,2,2,2,2,2,2; 4.2 s: rc 2; pomoc na stderr / `usage_error` w JSON | OK |
| d-debug-json (+1) | `kartograf parse ZZZ --json` | KARTOGRAF_DEBUG=1 przy bledzie wejscia | rc 1,1; 1.2 s: traceback na stderr, wyjatek podniesiony takze w --json (rc 1, stdout pusty) - zgodnie z USAGE 9.2 | OK |

#### E. project init / add / remove (offline, bledy wejscia)

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| p-init-noout (+4) | `kartograf project init --project <katalog-danych>/projekt-a` | init bez -o / -o = plik / ponowny init | rc 2,2,2,2,2; 3.0 s: rc 2 `invalid_input`; nic nie utworzone przy bledzie (brak katalogu projektu); 'projekt juz istnieje' | OK |
| p-init-ok | `kartograf project init --project <katalog-danych>/projekt-a --output <katalog-danych>/magazyn` | init + manifest + magazyn | rc 0; 0.7 s: manifest `kartograf-project/1`, `tasks: []`, magazyn utworzony | OK |
| pa-notdata (+1) | `kartograf project add --project <katalog-danych>/projekt-a bad elevation availability --product nmt --sheet M-34-64-D-d-1-2 --json` | add komendy niedanej (`elevation availability`) | rc 2,2; 1.1 s: rc 2; lista 12 komend danych; `details.option=command`+`allowed` | OK |
| pa-novcrs (+1) | `kartograf project add --project <katalog-danych>/projekt-a t1 elevation download --product nmt --sheet M-34-64-D-d-1-2 --resolution 1m` | brak --vertical-crs | rc 2,2; 1.3 s: rc 2; `details.option=vertical_crs`, allowed EVRF2007/KRON86, hint z `project add teren ...` | OK |
| pa-bad-sheet (+6) | `kartograf project add --project <katalog-danych>/projekt-a t3 elevation download --product nmt --sheet ZZZ --resolution 1m --vertica...` | zle godlo / rozdzielczosc 7m / bbox odwrocony / CRS 9999 / brak obszaru / dwa obszary | rc 2,2,2,2,2,2,2; 4.9 s: wszystkie rc 2, przed siecia, komunikaty z lista dozwolonych wartosci (res: `0.15m,0.5m,0.6m,1m,5m,10m,100m`) | OK* (P3-9) |
| pa-upgrade (+9) | `kartograf project add --project <katalog-danych>/projekt-a t2 elevation download --product nmt --sheet M-34-64-D-d-1-2 --resolution ...` | opcje uruchomienia po nazwie zadania | rc 2; 6.9 s: rc 2 `invalid_input` z `details.option` (upgrade/force/check_updates/plan/workers/summary/json/output_dir); `--project` po NAZWA odrzucone | OK |
| pa-q | `kartograf project add --project <katalog-danych>/projekt-a t2 elevation download --product nmt --sheet M-34-64-D-d-1-2 --resolution ...` | `-q` po nazwie zadania | rc 0; 0.7 s: rc 0, zadanie dodane, `-q` po cichu pominiete (nie trafia do manifestu), a `--workers` odrzucone | OK* (P3-4) |
| pa-output-same (+1) | `kartograf project add --project <katalog-danych>/projekt-a --json t1 elevation download --product nmt --sheet M-34-64-D-d-1-2 --reso...` | `-o` rowne magazynowi projektu / separator `--` | rc 0,0; 1.5 s: przyjete (rc 0) | OK |
| pa-dup (+1) | `kartograf project add --project <katalog-danych>/projekt-a t1 elevation download --product nmt --sheet M-34-64-D-d-1-2 --resolution ...` | duplikat nazwy | rc 2,2; 1.3 s: rc 2 `invalid_input`, `details.option=name`, podpowiedz `project remove` | OK |
| pa-bad-name-space (+6) | `kartograf project add --project '<katalog-danych>/projekt-a' 'Zla Nazwa' elevation download --product nmt --sheet M-34-64-D-d-1-2 --...` | nazwy zadan (spacja, ../x, pusta, TEREN, -x, 65 i 64 znaki) | rc 2,2,2,2,2,2,0; 4.6 s: rc 2 z regula nazwy (male litery/cyfry/-/_ do 64 znakow); 64 znaki OK | OK |
| pa-noname (+6) | `kartograf project add --project <katalog-danych>/projekt-a` | brak nazwy / komendy / projektu; `--project` = plik manifestu | rc 2,2,2,2,2,2,2; 4.2 s: rc 2; komunikaty 'podaj komende danych', 'brak projektu w ...'; dla pliku: 'Not a directory' (surowy blad OS) | OK* (P3-15) |
| pa-teren-hint | `kartograf project add --project <katalog-danych>/projekt-a teren elevation download --product nmt --sheet M-34-64-D-d-1-2 --resoluti...` | wklejka z `elevation availability` ('W projekcie: kartograf project add NAZWA ...') | rc 0; 0.7 s: wklejony ogon `elevation download ... --year 2025` przyjety bez zmian; `year` zapisany jako liczba 2025 | OK |
| pa-orto (+5) | `kartograf project add --project <katalog-danych>/projekt-a orto-wycinek imagery download --product orto --country pl --bbox 566000,2...` | 6 zadan z roznych grup (orto cutout, granice, gleby, HSG, BDOT10k, CZ NMT) | rc 0,0,0,0,0,0; 4.3 s: rc 0, 0 zapytan sieciowych (offline dziala); `bbox` zapisany z `bbox_crs` EPSG:2180 | OK |
| pr-t2 (+2) | `kartograf project remove --project <katalog-danych>/projekt-a t2` | remove | rc 0,0,0; 2.2 s: rc 0 'pliki zostaly w magazynie' | OK |
| pr-t2-again (+2) | `kartograf project remove --project <katalog-danych>/projekt-a t2` | remove nieistniejacego / bez nazwy | rc 2,2,2; 2.0 s: rc 2; `details.option=name` | OK |
| pb-init (+2) | `kartograf project init --project <katalog-danych>/projekt-b --output <katalog-danych>/magazyn --json` | init/add/remove --json (projekt B) vs biblioteka | rc 0,0,0; 2.3 s: `kartograf-project-state/1`, rowne `init_project/add_project_task/remove_project_task().to_dict()` (po normalizacji katalogu); manifest po add+remove == swiezy | OK |

#### F. project download / status / verify

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| ps-before (+4) | `kartograf project status --project <katalog-danych>/projekt-a` | przed pierwszym pobraniem | rc 1,1,1,1,1; 2.8 s: rc 1; `teren: nie pobrane (pobierz: kartograf project download --project ... teren)`; JSON `ok:false`, `not_downloaded` = 7 zadan; `-q` pusty | OK |
| ps-unknown-task (+1) | `kartograf project status --project <katalog-danych>/projekt-a nope` | nieznane zadanie w status | rc 2,2; 1.1 s: rc 2, `details.option=tasks` | OK |
| pc-before (+3) | `kartograf project download --project <katalog-danych>/projekt-a --check-updates teren-cz` | --check-updates przed pierwszym pobraniem | rc 0,0,0,0; 2.5 s: rc 0, `ok:true`, `not_downloaded` wszystkie (inna semantyka `ok` niz status) | OK* (P3-19) |
| pd-first | `kartograf project download --project <katalog-danych>/projekt-a` | pierwsze pobranie 7 zadan (NMT 37 MB, orto 12 MB, granice, gleba, HSG(4), BDOT10k 11,8 MB, CZ SM5) | rc 0; 54.3 s: rc 0, 54,3 s; `przypiete 7`; 15 plikow danych (+sidecary), linie `zadanie: jednostka (plik): przypieto <etykieta>` | OK |
| ps-after (+5) | `kartograf project status --project <katalog-danych>/projekt-a` | status/verify po pobraniu (+ --json, -q) | rc 0,0,0,0,0,0; 6.0 s: rc 0; 10 plikow `ok`; status 0,5-0,7 s, verify 1,4 s (62 MB SHA-256); manifest bajtowo bez zmian | OK |
| pd-second | `kartograf project download --project <katalog-danych>/projekt-a` | ponowne download | rc 0; 0.6 s: `bez zmian 7`, 0,6 s, manifest bez zmian, 0 zapytan | OK |
| pc-check (+1) | `kartograf project download --project <katalog-danych>/projekt-a --check-updates` | --check-updates | rc 0,0; 13.5 s: NMT/gleby/CZ `aktualne` (index/metadata/http); orto-wycinek, granice, BDOT10k `nie da sie sprawdzic bez pobrania (--force)`; rc 0; manifest bez zmian | OK |
| pc-upgrade | `kartograf project download --project <katalog-danych>/projekt-a --upgrade` | --upgrade bez nowszych danych | rc 0; 6.0 s: `bez zmian 7`; 3 x `Info: ... lokalna wersja niesprawdzona - zrodlo bez taniego sygnalu; pobierz ponownie: --force` | OK |
| pf-force | `kartograf project download --project <katalog-danych>/projekt-a --force granice orto-wycinek` | --force dla toru bez sygnalu (granice, orto-wycinek) | rc 0; 28.5 s: 28,5 s, `bez zmian` (ta sama tresc), manifest bez zmian | OK |
| w-4 (+10) | `kartograf project download --project <katalog-danych>/projekt-a --workers 4 teren` | --workers, konflikt flag, kolejnosc argumentow, duplikaty nazw | rc 0,2; 6.7 s: `--workers 0/-2`: rc 2 `option=workers`; `abc`/konflikt flag: rc 2 `usage_error` (angielski); `-w 1000` przyjete; nazwy pozycyjne przed/po --project dzialaja | OK |
| q-check (+4) | `kartograf project download --project <katalog-danych>/projekt-par --check-updates -q` | -q (z --json i bez) | rc 0,0,0,0,0; 10.2 s: rc 0, stdout pusty; z --json dokument bez zmian | OK |
| d-remove-pinned (+5) | `kartograf project remove --project <katalog-danych>/projekt-a gleba-il` | remove zadania z przypieciem, re-download, ponowne add | rc 0,0,0,0,0,0; 4.9 s: inne zadania nietkniete; re-add + download: `przypieto` te same sha/label/version, nowy `pinned_at`; zadanie na koncu listy | OK |
| nc-status (+4) | `kartograf project status --project <katalog-danych>/projekt-a -q` | cache SQLite w cwd | rc 0,0,0,0,0; 8.9 s: operacje projektu nie tworza `.kartograf_cache.db`; bezposrednie `--check-updates` tworzy (zgodnie z USAGE 8.4) | OK |
| laz-add (+4) | `kartograf project add --project <katalog-danych>/projekt-a laz elevation download --product laz --country pl --bbox 566000,243000,56...` | zadanie LAZ z podpowiedzi availability (tiny bbox 100 x 100 m, kafel 59 MB) | rc 0,0,0,0,0; 33.4 s: rc 0, 28 s, 1 plik `83134_1728146_M-34-64-D-d-1-4-4-1.laz` przypiety; verify OK; check `aktualne` | OK |
| co-add (+4) | `kartograf project add --project <katalog-danych>/projekt-a corine landcover download --product corine --year 2018 --bbox 566000,2430...` | CORINE bez CLMS_CREDENTIALS jako zadanie | rc 0,0,0,0,0; 4.2 s: przypiety podglad PNG 194 B z `Info: ... podglad WMS (stylizowany PNG, nie dane; dane CLMS wymagaja CLMS_CREDENTIALS)`; status ok; check: nie da sie sprawdzic | OK* (P3-17) |
| z-add-orto (+4) | `kartograf project add --project <katalog-danych>/projekt-cz orto_cz imagery download --product orto --sheet CTES96` | ortofoto CZ SM5 CTES96 (4 pliki) | rc 0,0,0,0,0; 150.4 s: przypiete 4 pliki (JPEG 63,9 MB + 3 JGW), linie `orto_cz: CTES96 (CTES96.jgw)` rozroznialne; 146 s (CUZK wolne); check 4 x `aktualne` | OK |
| au-add (+4) | `kartograf project add --project <katalog-danych>/projekt-a pogranicze elevation download --product nmt --country auto --bbox 18.625,...` | pogranicze --country auto --cutout (pl=1m,cz=2m) | rc 0,0,0,0,0; 36.7 s: 2 pliki (PL 2,36 MB, CZ 405 KB wszystko nodata + Warning); linie status/verify identyczne dla obu plikow | OK* (P3-5) |

#### G. Integralnosc, odtwarzanie, uszkodzenia

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| c-status-bitflip (+3) | `kartograf project status --project <katalog-danych>/projekt-a teren-cz` | odwrocony 1 bit w pliku wersji (CZ SM5, 780 KB) | rc 0,1,1,0; 3.1 s: status ok (rozmiar ten sam - zgodnie z USAGE); verify rc 1 `corrupt` 'suma SHA-256 danych jest inna niz przypieta'; reszta zadan ok | OK |
| c2-verify-bitflip (+2) | `kartograf project verify --project <katalog-danych>/projekt-a teren-cz` | `--force` na uszkodzonym pliku | rc 1,0,1; 3.3 s: pobiera ZIP ponownie, ale 'bez zmian' i plik nadal uszkodzony (verify rc 1) | BLAD (P3-1) |
| c3-status-missing (+3) | `kartograf project status --project <katalog-danych>/projekt-a teren-cz` | usuniety katalog wersji -> odtworzenie | rc 1,1,0,0; 6.5 s: status/verify rc 1 'brak przypietej wersji'; download `odtworzono (1 plik)`, ta sama suma, verify ok | OK |
| c4a-status (+1) | `kartograf project status --project <katalog-danych>/projekt-a teren-cz` | obciety plik wersji | rc 1,1; 1.3 s: status i verify rc 1 'ma inny rozmiar'; komunikat podaje 'usun uszkodzony katalog wersji i uruchom project download' | OK |
| c4b-status (+1) | `kartograf project status --project <katalog-danych>/projekt-a teren-cz` | sidecar wersji z podmieniona suma | rc 0,1; 1.2 s: status ok (rc 0); verify rc 1 'sidecar wersji niezgodny z nazwa wersji'; na stderr surowa linia 'Pominieto wersje o niezgodnym sha256' | OK* (P3-2) |
| c4c-status (+1) | `kartograf project status --project <katalog-danych>/projekt-a teren-cz` | skasowany sidecar wersji | rc 1,1; 1.2 s: status i verify rc 1 'brak przypietej wersji' | OK |
| c4d-status (+2) | `kartograf project status --project <katalog-danych>/projekt-a teren-cz` | sciezka standardowa podmieniona kopia (zerwane dowiazanie) | rc 0,0,0; 1.8 s: status/verify ok (zgodnie z USAGE: verify nie wykrywa nadmiarowych kopii); `elevation download` ('lokalna wersja') po cichu odtwarza hardlink | OK |
| rc-status (+4) | `kartograf project status --project <katalog-danych>/projekt-par s4` | przypieta suma != tresc u zrodla (podmiana sha w manifescie + brak plikow) | rc 1,1,0,0,0; 4.2 s: download rc 1 'zrodlo ma inna tresc niz przypieta ... przypiecie bez zmian'; manifest bez zmian; `--upgrade` przyjmuje nowa tresc; (drugie download: bez weryfikacji tresci 'bez zmian' - zgodnie z projektem) | OK |
| z-verify-corrupt-jgw (+1) | `kartograf project verify --project <katalog-danych>/projekt-cz` | uszkodzony 1 z 4 plikow ortofoto CZ | rc 1,1; 1.9 s: verify rc 1 wskazuje dokladnie plik `CTES96.TM33N.jgw`; pozostale 3 `ok` | OK |
| g-status (+6) | `kartograf project status --project <katalog-danych>/projekt-geo` | geometria (GPKG) przypieta z `geometry_sha256`; zmiana jej bajtow | rc 0,0,0,0,0,0,0; 6.6 s: download/status/verify bez zmian i bez ostrzezenia; --check-updates `Warning: plik geometrii zmienil sie od przypiecia`; --upgrade przyjmuje (nowy `geometry_sha256`) | OK* (P3-6) |
| g-add-rel-cwd-miss (+3) | `kartograf project add --project <katalog-danych>/projekt-geo geo elevation download --product nmt --country pl --geometry obszar.geo...` | `--geometry` wzgledny | rc 2,2,0,0; 2.7 s: sciezka czytana wzgledem cwd (nie projektu); .geojson odrzucone ('Obslugiwane: .gpkg, .shp'); zapis wzgledem projektu: `obszar.gpkg` albo `../../../../..` przy pliku poza drzewem projektu | OK* (P3-7) |
| r-init (+8) | `kartograf project init --project <katalog-danych>/projekty/rel --output ../../magazyn` | `--output` wzgledny, projekt przeniesiony, nowy magazyn | rc 0,2; 20.0 s: `--output ../../magazyn` czytany wzgledem CWD (powstal magazyn poza udzialem - moja pomylka, usuniety), zapisany jako lancuch `../..` wzgledem projektu; po przeniesieniu projektu rc 2 'magazyn projektu nie istnieje ... popraw output_dir' zgodnie z USAGE 8.3; nowy magazyn tworzony rekurencyjnie | OK* (P3-7) |
| i-init (+4) | `kartograf project init --project <katalog-danych>/projekt-int --output <katalog-danych>/magazyn-int` | SIGINT po 9 s pobierania (NMT 1 m 37 MB), potem wznowienie | rc 0,0,1,0,0; 25.8 s: text: rc 130 `Error: przerwano (Ctrl-C)`; --json: `kartograf-error/1` `interrupted` rc 130, stderr pusty; magazyn: tylko pusty `versions/.incoming`, manifest bez przypiec, brak `.kartograf-project.lock`; wznowienie `przypieto`, verify ok | OK |
| par-init (+2) | `kartograf project init --project <katalog-danych>/projekt-par --output <katalog-danych>/magazyn-par` | 4 rownolegle procesy `project download` (rozne zadania + to samo zadanie 2x) | rc 0,0,0; 2.2 s: rozne zadania: wszystkie 5 pinow scalone, manifest poprawny JSON, brak locka; to samo zadanie (s4) 2x: jeden proces przypina, drugi rc 1 'zadanie zmienione w tym czasie przez inny proces; nic nie zapisano - ponow polecenie' | OK |
| ro-download (+4) | `kartograf project download --project <cwd-E>/synth/rop` | magazyn tylko do odczytu / katalog manifestu tylko do odczytu | rc 1,1,1,1,0; 7.7 s: rc 1 `io_error` EACCES z hintem (JSON) / `Error: PermissionError` (tekst); manifest bez zmian; przy RO manifescie dane sa pobrane, a potem 'nie mozna zablokowac projektu' (rc 1); po naprawie przypiecie bez ponownego pobrania | OK* (P3-24) |
| pl-is-dir (+1) | `kartograf soil download --bbox 626000,480000,628000,482000 --property clay --depth 0-5cm --stat mean -o <katalog-danych>/magazyn-cli...` | `--check-updates --plan KATALOG` | rc 1,1; 2.9 s: po sprawdzeniu sieci: `IsADirectoryError` rc 1 (`io_error` w JSON); w przeciwienstwie do braku katalogu (rc 2 z gory) | OK* (P3-8) |

#### H. Tryby aktualizacji i wersjonowany magazyn (bezposrednie komendy)

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| s-local | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 --year 2025 -o <katalog-d...` | ponowne pobranie arkusza | rc 0; 3.0 s: `lokalna wersja 2025-04-28_83137`, 3,0 s, bez sieci po stronie danych | OK |
| s-check | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 --year 2025 -o <katalog-d...` | --check-updates | rc 0; 1.2 s: `aktualne (2025-04-28_83137)` | OK |
| s-check-plan | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 --year 2025 -o <katalog-d...` | --check-updates --plan plan.json | rc 0; 1.2 s: plan `kartograf-plan/1` (store, items[track=pl_sheet,status=current], ok:true); `Info: zapisano plan` na stderr | OK |
| s-upgrade-plan | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 --year 2025 -o <katalog-d...` | --upgrade --plan (pozycja `current`) | rc 0; 0.7 s: rc 0, nic nie wydrukowane (brak komunikatu 'plan bez pozycji do wykonania') | OK* (P3-25) |
| s-upgrade (+1) | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 --year 2025 -o <katalog-d...` | --upgrade / --force tej samej tresci | rc 0,0; 24.4 s: `lokalna wersja` / `bez zmian 2025-04-28_83137` (22 s: pobranie 37 MB) | OK |
| u-year2022 (+3) | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 -o <katalog-danych>/magaz...` | magazyn B: lot 2022, potem domyslnie / check / plan | rc 0,0,0,0; 24.4 s: `nowa wersja 2022-06-03_76531_f706c965`; domyslnie `lokalna wersja ...; dostepna nowsza 2025-04-28_83137 (--upgrade)` + Info; check `nowsza: 2025-04-28_83137 (lokalna 2022-06-03_76531)`; plan status `newer` | OK |
| u-apply-stale (+1) | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 -o <katalog-danych>/magaz...` | plan nieaktualny (zmieniony `available_label`) | rc 1,1; 3.0 s: rc 1 `zrodlo zmienilo sie od planu`; JSON `kartograf-download/1` `ok:false`, `stale` zawiera pozycje | OK |
| u-apply-otherstore (+8) | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 -o <katalog-danych>/magaz...` | plan innego magazynu / zly JSON / zly schemat / brak pliku / --plan bez trybu / konflikty flag | rc 2; 5.3 s: wszystkie rc 2 (`option=plan`), wzajemne wykluczanie `--check-updates/--upgrade/--force` | OK* (P3-9) |
| u-apply-plan | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 -o <katalog-danych>/magaz...` | --upgrade --plan (status newer) | rc 0; 17.6 s: `nowa wersja 2025-04-28_83137_e041a794` (17,6 s); katalog: 2 wersje w versions/, sciezka standardowa i full_sheet/ -> 2025 | OK |
| u-after-default (+3) | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 -o <katalog-danych>/magaz...` | po aktualizacji: domyslnie / check / `--year 2022` | rc 0,0,0,0; 7.5 s: `lokalna wersja 2025`; `aktualne`; `--year 2022`: lokalna 2022 + `Info: 2 dowiazan wskazuje lokalny lot spoza tego zadania` (dowiazanie nie cofa sie); check `aktualne (2022...)` | OK |
| po-seed2022 (+8) | `kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 --year 2022 -o <katalog-d...` | projekt z magazynem majacym tylko lot 2022 (zadanie bez --year) | rc 0; 110.1 s: przypiety lot lokalny 2022 + Info o nowszym; `--check-updates` `nowsza: 2025 (przypieta 2022)` rc 0 `ok:true`; `--upgrade` pobiera 2025 i przepina; stara wersja zostaje w versions/ | OK* (P3-14) |
| area-nmt5m | `kartograf elevation download --product nmt --country pl --bbox 565900,244250,566300,244450 --sheet-system 1992 --resolution 5m --ver...` | NMT 5 m dla bbox (2 arkusze) - sidecary | rc 0; 3.6 s: `request={sheet}`, `extra.parent_request={bbox,...}`; footprinty = dokladne arkusze | OK |
| s-bdot-shp (+1) | `kartograf landcover download --product bdot10k --teryt 2476 --format SHP -o <katalog-danych>/magazyn` | BDOT10k powiat 2476 `--format SHP` (ZIP) | rc 0,0; 11.2 s: `nowa wersja 2026-10-19_2e2aea65`; potem `lokalna wersja` (bez sieci) | OK |

#### I. Offline (unshare -rn)

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| o-status (+3) | `[offline] kartograf project status --project <katalog-danych>/projekt-a` | status/verify/download przypietych plikow | rc 0,0,0,0; 4.1 s: rc 0 bez sieci, 0,6-1,5 s; download `bez zmian 7` | OK |
| o-check (+3) | `[offline] kartograf project download --project <katalog-danych>/projekt-a --check-updates` | --check-updates / --upgrade / --force bez sieci | rc 1,1,1,1; 119.7 s: rc 1 po 3 probach (2 s + 4 s wstrzymania na zapytanie, lacznie 37 s): `Error: <zadanie>: blad sprawdzenia: ... (brak sieci albo DNS)`; zadania bez sygnalu nadal `nie da sie sprawdzic`; JSON `check_failed`, `ok:false`; manifest bez zmian | OK |
| o-add-remove (+4) | `[offline] kartograf project add --project <katalog-danych>/projekt-a off-1 soil download --bbox 566000,243000,567000,244000 --proper...` | add/remove/parse/catalog/cache offline | rc 0,0,0,0,0; 3.3 s: rc 0 (add sprawdza wybory bez sieci) | OK |
| o-direct-local (+4) | `[offline] kartograf elevation download --sheet M-34-64-D-d-1-2 --product nmt --resolution 1m --vertical-crs EVRF2007 --year 2025 -o ...` | bezposrednie komendy offline | rc 0,1,1,1,1; 27.9 s: lokalna wersja rc 0; check: `nie udalo sie sprawdzic ...` rc 1 / `check_failed`; nowy arkusz: `Error:` rc 1 / `kartograf-download/1` `failed[kind=download]`; katalog magazynu nie utworzony | OK |

#### J. Rozne

| # | Komenda (pierwszy wariant) | Oczekiwane | Wynik (rc; czas) | Ocena |
|---|---|---|---|---|
| pl-missing-dir (+5) | `kartograf soil download --bbox 626000,480000,628000,482000 --property clay --depth 0-5cm --stat mean -o <katalog-danych>/magazyn-cli...` | --plan: brak katalogu / rodzic = plik / poprawny | rc 2,2,2,2,0,0; 4.3 s: rc 2 `option=plan` z gory; plik planu == dokument na stdout bajtowo; brak `Info: zapisano plan` w --json | OK |
| u-init (+5) | `kartograf project init --project '<cwd-E>/synth/ścieżka z spacją ąęółżźćń/projekt Ł' --output '<cwd-E>/synth/ścieżka z spacją ąęółżź...` | sciezki z polskimi znakami i spacjami | rc 0,0,0,0,0,0; 5.9 s: projekt, magazyn, sidecary, JSON i API dzialaja (manifest UTF-8 bez ucieczek) | OK |
| u-verify-C (+1) | `kartograf project verify --project '<cwd-E>/synth/ścieżka z spacją ąęółżźćń/projekt Ł'` | LC_ALL=C + PYTHONUTF8=0 + PYTHONCOERCECLOCALE=0 + sciezka nie-ASCII | rc 2,2; 1.2 s: rc 2 'magazyn projektu nie istnieje' (sciezka nie da sie zakodowac); `catalog --json` dziala | OK* (P3-23) |
| man-bad-json (+8) | `kartograf project status --project synth/man/bad-json --json` | uszkodzone manifesty (24 warianty; tu 9 pierwszych) | rc 0,2; 9.7 s: rc 2 `invalid_input`, bez tracebacku; CRLF przyjety; BOM odrzucony komunikatem Pythona | OK* (P3-15) |
| man-task-cmd-availability (+13) | `kartograf project status --project synth/man/task-cmd-availability --json` | pozostale 14 wariantow: zla komenda, duplikaty, `..`, `.incoming`, sha, rozmiar, opcje, rola, sciezki | rc 2; 10.8 s: wszystkie rc 2 z konkretnym komunikatem (pole + oczekiwanie) | OK |
| man-option-bad-value | `kartograf project status --project synth/man/option-bad-value --json` | opcja z niedozwolona wartoscia w manifescie (`property: zzz`) | rc 0; 0.6 s: status rc 0 (wartosci opcji sprawdza dopiero add/download) | OK |
| dl-add-teren (+5) | `kartograf project add teren elevation download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007 --year...` | przyklady z USAGE 8.1 i 9.2 uzyte dosłownie | rc 0,0,0,1,1,0; 4.0 s: przyjete; `status -q` rc 1 pusty (idiom `status -q || download`) | OK |

#### K. Biblioteka: odczyt magazynu, warstwa komend, parytet

| # | Wywolanie | Oczekiwane | Wynik | Ocena |
|---|---|---|---|---|
| K1 | `list_segments(D)` | posortowane `<produkt>/<wariant>`, bez symlinkow i `.x`, brak katalogu = OSError | 13 segmentow, posortowane; `FileNotFoundError`/`NotADirectoryError` dla braku/pliku; symlink-segment pominiety | OK |
| K2 | `describe_segment(s) x13 + nieznane` | nazwa ludzka, known=True; nieznany = known=False | 13/13 known (nazwy wg deskryptora + wariant); `nmt/pl_1992_9m_foo`, `orto/pl_1992_true` -> known=False | OK |
| K3 | `iter_store(D) (pelny skan)` | kolejnosc: link, full_sheet, version; brak problemow; `version_path` leksykalny | 14 link + 14 version + 1 full_sheet, 0 problemow; kolejnosc w segmencie zachowana; 1229 wpisow syntetycznych w 0,14 s | OK |
| K4 | `iter_store(segment=, units=)` | jednostki: godlo, teryt, teryt/<k>, <coords>, bbox/<coords>, SM5 | wszystkie formy znajduja wpis; zarezerwowane (`versions`,`full_sheet`,`kampanie`), >255 B, `..`, absolutny, 1-czlonowy segment -> `ValidationError` | OK |
| K5 | `list_partitions + iter_store(partition=)` | suma czesci == pelny skan, bez duplikatow | 13 segmentow rzeczywistych oraz magazyn syntetyczny 384 slotow (target 1/8/32/200 -> 2/13/49/385 czesci): suma == skan; skan rownolegly 8 watkow == sekwencyjny | OK |
| K6 | `iter_store(skip_versions=...) (lista i mapowanie)` | pominiete wersje: skipped=True, sidecar=None; reszta czytana | OK; na syntetycznym magazynie wszystkie wersje pominiete 461/461, linki nadal z sidecarem | OK |
| K7 | `read_sidecar(dane|meta) i bledy` | ten sam wynik z pliku danych i sidecara; `InvalidSidecarError` z `path` i hintem | OK; brak pliku / zly JSON / obcy schemat / tablica / pusty plik -> InvalidSidecarError (hint z `error_report`: '<plik>.meta.json') | OK |
| K8 | `read_sidecar - starsze/uszkodzone formy` | klucze dev 0.8.0 i polskie sprzed ADR-031 mapowane, raw bez zmian | 11/11 kluczy dev -> `dataset_key`; `godlo/aktualnosc` -> unit/data_date/data_year; zle typy -> None; BOM i sidecar 5 MB czytane; NaN bez awarii (12/12) | OK |
| K9 | `link_target(link) na udziale SMB bez serverino` | ten sam wynik dla kazdego wiarygodnego dowiazania twardego | kolejne wywolania zaraz po odczycie pliku: 0/14 potwierdzonych (`None`); co 3 s: 12-13/14; kontrola na lokalnym ext4: 3 x 2/2 stabilnie (samefile). Sprawdzenie nlink>=2 zawodzi, gdy klient cifs raportuje st_nlink=1 po odczycie | BLAD (P2-1) |
| K10 | `file_footprint(entry) (arkusz, bbox, naglowek, jednostka)` | WGS84 dlugosc/szerokosc; zrodlo request/sheet/header/unit | 38/38: arkusz = dokladny prostokat 1/32 x 1/48 st.; wycinek = request; GPKG/ASC/GeoTIFF = header (CTES96 EPSG:5514 -> 18.58 E 49.74 N); ZIP powiatu: `None` bez sieci, `unit` z PRG z `network=True` (0,9 s) == obrys z GPKG; z cache offline dziala; offline `network=True` -> DownloadError | OK |
| K11 | `file_footprint(entry LAZ)` | obrys kafla (naglowek LAS lub `tile_sheet`) | zwraca bbox ZADANIA 100 x 100 m (source=request); naglowek LAS: 565 x 586 m. `Sidecar.unit` = `566000_243000_566100_243100` i `iter_store(units=[unit])` NIE znajduje kafla (`units=['M-34-64-D-d-1-4-4-1']` znajduje) | BLAD (P2-2) |
| K12 | `pinned_transform x9 par, 8-16 watkow` | pinezka bez ballpark; spojnie z watkami | 2180/5514/3045/2177 <-> 4326, 2180 <-> 5514 (krok datum CZ: roznica 3,9 m wzgl. domyslnego PROJ); 16 watkow x200 identyczne wyniki | OK |
| K13 | `watki: iter_store, read_sidecar, describe_segment, file_footprint` | wywolania rownolegle bez bledow i z tymi samymi wynikami | iter_store per segment 8 watkow x5; read_sidecar 16 watkow; file_footprint 16 watkow x20 (GDAL, GPKG, LAZ) == sekwencyjnie (5/5 + 5/5) | OK |
| K14 | `describe_store / list_store_entries / read_store_sidecar` | dokumenty `kartograf-store-*/1`, klucze, limit/truncated, to_json | 33/33: klucze i kolejnosc, `limit`/`truncated` (limit=0/-1/'5' -> ValidationError), filtr `units`, `Sidecar.raw` pominiety, to_json deterministyczny, UTF-8 (`·` bez `\u00b7`), `to_json(indent=None)` bez nowej linii | OK |
| K15 | `problemy na magazynie syntetycznym` | missing_sidecar, invalid_sidecar, unknown_segment, legacy_campaigns, stale_incoming; symlink-segment odrzucony | 14/14: kazdy kod wykryty, zdrowe wpisy rodzenstwa nie wyparte, `describe_store` oznacza `known=false` | OK |
| K16 | `te same zestawy pod `unshare -rn`` | odczyt magazynu bez sieci | 203/205 (2 = link_target jak wyzej); online: 249/251 | OK |
| K17 | `data_commands(); parse_command(string|lista|z `kartograf `|ogon z availability|bbox ujemny)` | CommandCall(command, options, run) | 12 komend; `kartograf ` na poczatku przyjmowane (lista i napis); ogon podpowiedzi -> `year` jako int; `--bbox=-447000,...` i `--bbox -447000,...`; `bbox_crs` zawsze dopisywany; klucze `run`: `upgrade`/`force`/`check_updates`/`quiet`/`json`/`output_dir`/`workers`/`plan` (nie `update`) | OK* (P3-3) |
| K18 | `validate_command(...)` | bez sieci; ValidationError z option/allowed | 11/11 przypadkow: brak vertical_crs (`option`, `allowed` EVRF2007/KRON86, hint), nieznana komenda/opcja, bbox bez bbox_crs, rok jako napis, zle godlo, bbox odwrocony; poprawne -> None | OK |
| K19 | `format_command / okrazenie parse(format())` | odwrotnosc parse_command | OK dla opcji z ujemnym bbox i sciezka ze spacja; 51 przykladow katalogu: validate + okrazenie 51/51 | OK |
| K20 | `run_command / check_command vs CLI (soil bbox 626000,480000,628000,482000)` | ten sam dokument co `download --json`/`--check-updates --json` | 12/12: check (missing), run (new), run (local), check (current) rowne CLI po normalizacji sciezki magazynu i `checked_at`; `update='upgrade'` z planem, `update='force'` (`unchanged`); bledy: ValidationError | OK |
| K21 | `parytet CLI --json == to_json() biblioteki` | bajtowo | parse x6, catalog x7, cache stats/path, project status/verify; project init/add/remove == init_project/add_project_task/remove_project_task (po normalizacji katalogu) - 18/18 + 13/13 | OK |
| K22 | `tabele 9.3 w USAGE == catalog.tables; error_report` | kody wyjscia i bledow rowne | 4 kody wyjscia, 14 kodow bledow zgodne; error_report: io_error (ENOENT, hint ze sciezka), internal_error, interrupted (130), no_coverage (hints) OK | OK |
| K23 | `komendy danych w llms.txt, USAGE, README` | parse_command + validate_command offline | 182 linii: 177 OK; 5 oczekiwanych odrzucen (3 wymagaja plikow `area.shp`/`zlewnia.gpkg`, 2 to celowe przyklady bledow) | OK |
| K24 | `USAGE 8.4: API projektu (init/add/status/verify/open/remove + bledy)` | typy Project/ProjectCheck; ValidationError przy blednych wejsciach | 20/20; `get_project_status` przed pobraniem `ok=False`, `not_downloaded=('teren',)` | OK |

## Znaleziska

### P1

Brak.

### P2

**P2-1. `link_target()` zwraca `None` dla prawidlowych dowiazan twardych na SMB bez `serverino`** (oraz zbedny zapis sidecara dowiazania przy `elevation download`).

- Powtorzenie (udzial cifs bez `serverino`, magazyn z dowiazaniami; stan spoczynku min. 5 s):

```python
from kartograf import iter_store, link_target
links = [e for e in iter_store(STORE) if e.kind == "link"]
link_target(links[0].path)    # spokojny plik: sciezka wersji
link_target(links[0].path)    # tuz po pierwszym wywolaniu: None
# albo: file_footprint(e) czytajacy naglowek (GPKG, CZ SM5) i zaraz link_target(e.path) -> None
```

- Zaobserwowano: petla po dowiazaniach magazynu bez przerw: 0/14 potwierdzonych (`None`) w obu przebiegach koncowych (wczesniej 2/9, 1/10, 11/14, 12/14 - zaleznie od czasu od ostatniego odczytu plikow); co 3 s: 12-13/14 (dowiazanie `landcover/pl_bdot10k_shp` trzymalo nlink=1 jeszcze 50 s po odczycie). Klient cifs po odczycie pliku zglasza `st_nlink == 1` (1-2 s, czasem ~50 s), dla drugiej sciezki (wersji) 2. Pomiar: `stat` link/wersja `(2,2)` w spoczynku, `(1,2)` zaraz po `open+read`, `(2,2)` po 2 s. `samefile` zawsze False (brak stabilnych i-wezlow), wiec potwierdzenie trescia wymaga `st_nlink >= 2` dla OBU plikow. Kontrola na lokalnym ext4: 3 x 2/2 (`samefile` True), stabilnie.
- Skutek uboczny (`rl-A`/`rl-B`): po odczycie pliku dowiazania `kartograf elevation download --sheet CTES96 ... -o <magazyn>` (sciezka "lokalna wersja") **przepisal sidecar dowiazania** (mtime `.meta.json` zmieniony, ten sam rozmiar) - zbedny zapis do magazynu; bez wczesniejszego odczytu (A) brak zapisu.
- Oczekiwane: wynik stabilny dla dowiazania, ktore spelnia warunki trescia (rozmiar + SHA-256 + sidecar `extra.link == hardlink`), albo udokumentowane ograniczenie. USAGE 4 mowi tylko, ze na SMB klient "moze przejsciowo raportowac bledna liczbe dowiazan, przez co nawet rsync -aH skopiuje je jako osobne pliki" - nic o `link_target`/`ensure_link`.
- Lokalizacja: `kartograf/download/links.py::_same_content_hardlink` (`l_stat.st_nlink < 2 or t_stat.st_nlink < 2 -> False`), wolane z `linked_version`, ktore uzywaja `store.py::link_target` i `ensure_link`. Mozliwe poprawki: traktowac `nlink == 1` jako niejednoznaczne i ponowic `stat` po >= 2 s albo pominac warunek nlink, gdy rozmiar i SHA-256 sa rowne, a sidecar deklaruje hardlink (kosztem uznania kopii za dowiazanie).

**P2-2. Kafel LAZ: `Sidecar.unit` i `file_footprint()` pochodza z bbox ZADANIA, nie z kafla.**

- Powtorzenie:

```
kartograf project add laz elevation download --product laz --country pl --bbox 566000,243000,566100,243100 --vertical-crs EVRF2007 --year 2025
kartograf project download laz     # kafel 83134_1728146_M-34-64-D-d-1-4-4-1.laz, 59 MB
```
```python
e = next(e for e in iter_store(STORE, segment="laz/pl_1992_evrf2007") if e.kind == "link")
e.sidecar.unit                                  # '566000_243000_566100_243100'  (bbox zadania)
list(iter_store(STORE, segment=e.segment, units=[e.sidecar.unit]))   # []  - petla odswiezania z ARCHITECTURE 3.3.1 nie dziala
list(iter_store(STORE, segment=e.segment, units=[e.sidecar.extra["tile_sheet"]]))  # ['link', 'version'] (M-34-64-D-d-1-4-4-1)
file_footprint(e)                               # source='request', 566000..566100 x 243000..243100 (100 x 100 m)
# naglowek LAS 1.2 tego pliku: X 565977.27..566542.61, Y 242585.65..243171.50 (565 x 586 m, 8 057 389 pkt)
```

- Oczekiwane (ARCHITECTURE 3.3.1): `file_footprint` zwraca "pierwsze WIARYGODNE zrodlo", a `unit` z indeksu "zamyka petle odswiezania `iter_store(units=[unit])`". Dla kafla LAZ obrys ma byc kafla (naglowek LAS albo `extra.tile_sheet`), `unit` = godlo kafla. Przy zadaniu obszarowym z wieloma kaflami wszystkie dostalyby ten sam obrys = obszar zadania, a konsument (Archiwista) zbudowalby bledny indeks pokrycia (falszywe negatywy dla punktow w kaflu poza bbox zadania).
- Arkusze NMT z `--bbox` sa poprawne (`request={sheet}`, obszar w `extra.parent_request`; obrys = dokladny arkusz), wiec blad dotyczy zapisu `request` kafli LAZ + kolejnosci w odczycie.
- Lokalizacja: `kartograf/store.py::_unit` (L333-357: `request.teryt|ku|sheet|tile`, `extra.source.sheet`, potem bbox - nie czyta `extra.tile_sheet`), `kartograf/store_geometry.py::file_footprint` (L595-600: `request.bbox` przed godlem i naglowkiem), zapis `request` kafla w `kartograf/download/laz.py::download_laz_area`.

### P3

Uwagi o dokumentacji oznaczono (doc); pelniejsze opisy w sekcji "Uwagi do dokumentacji".

1. **P3-1 `--force` nie naprawia uszkodzonego pliku wersji** (`c2-force`): po odwroceniu 1 bitu w przypietym pliku `project download --force teren-cz` pobiera ZIP ponownie, ale drukuje `bez zmian`, plik zostaje uszkodzony, `verify` nadal rc 1. Komunikat `verify` dla niezgodnej SHA-256 mowi tylko "przywroc katalog wersji z kopii magazynu" (`project/operations.py::_store_check`, ostatnia galaz `except`), podczas gdy komunikat o rozmiarze (`_corrupt_text`) dodaje "albo usun uszkodzony katalog wersji i uruchom project download ..." - ta sciezka dziala (`c3-download-restore`: `odtworzono`, SHA zgodna). Oczekiwane: ten sam opis naprawy w obu komunikatach; ewentualnie `--force` nadpisujacy wersje, ktorej bajty nie zgadzaja sie z sidecarem.
2. **P3-2 Kontrakt "stderr pusty" w `--json` (USAGE 9.2 pkt 2) naruszony przez dwa teksty spoza `notices`:** (a) `project verify --json` z podmienionym sidecarem wersji: surowa linia loggera `Pominieto wersje o niezgodnym sha256: <sciezka>` (`download/versions.py:214` `_warn_once`) bez prefiksu `Warning:`; (b) `elevation availability --product nmt --country auto --bbox 18.625,49.752,18.635,49.757 --bbox-crs EPSG:4326 --json` wypisuje `UserWarning` pyproj ("Best transformation is not available due to missing Grid(... cz_cuzk_table_-y-x_3_v1710.tif ...)") z `kartograf/transform/crs.py::build_pinned_transform` (`TransformerGroup(...)`; polityka celowo pomija siatki). Oba bez wplywu na dokument i kod wyjscia.
3. **P3-3 (doc) Klucze `CommandCall.run`:** USAGE 9.5 (tabela, wiersz `parse_command`: "`output_dir`, `update`..., `workers`, `plan`, `json`") i ARCHITECTURE 4.11 ("`output_dir`, `update`, `plan`, `workers`, `summary`") podaja `update`; faktyczne klucze to `upgrade`/`force`/`check_updates` (+ `quiet`, `json`, `summary`, `output_dir`, `workers`, `plan`), zgodnie z docstringiem `commands.py::CommandCall`. `run_command` przyjmuje `update="upgrade"|"force"`, wiec konsument musi sam mapowac.
4. **P3-4 `project add ... -q` po nazwie zadania jest po cichu pomijane** (`pa-q`, rc 0; nie trafia do manifestu), a `--workers`, `--summary`, `--json`, `--upgrade`... koncza sie `invalid_input`. `cli/project_cmd.py::_reject_run_options` nie obejmuje `quiet`.
5. **P3-5 Linie `status`/`verify`/`download` nie rozrozniaja plikow PL i CZ jednego zadania `--country auto --cutout`** (`au-*`): obie linie `pogranicze: 472994.992_..._210026.7252 (472994.992_..._210026.7252.tif): ok` identyczne (ten sam `unit` i ta sama nazwa pliku; roznica tylko w `path`/segmencie w JSON). USAGE 8.1 zapewnia rozroznialnosc plikow jednej jednostki (`cli/project_cmd.py::_unit_file`). Poza tym wycinek CZ tego bbox jest w calosci nodata (`Warning:` przy pobraniu; bbox lezy w PL, `auto` uzywa prostokatnych obwiedni) i zostaje przypiety jak kazdy inny.
6. **P3-6 `status`/`verify`/`download` nie sprawdzaja `geometry_sha256`:** po zmianie bajtow pliku geometrii zadania (`g-*`) `status`, `verify` i `download` mowia `ok`/`bez zmian` bez ostrzezenia; `--check-updates` ostrzega ("plik geometrii zmienil sie od przypiecia"), `--upgrade` przyjmuje nowy skrot. USAGE 8.3 mowi tylko, ze zmiana "blokuje zwykle odtworzenie".
7. **P3-7 (doc) Wzgledne `--output` (`project init`) i `--geometry` (`project add`) sa czytane wzgledem CWD, nie katalogu projektu** (`r-init`, `g-add-rel-cwd-miss`), a zapisywane wzgledem projektu; dla sciezki poza drzewem projektu manifest dostaje lancuch `../../../../../../../../home/...`. USAGE 8.3 ("podane wzglednie sa zapisane wzgledem katalogu projektu (nie biezacego katalogu odczytu)") nie mowi, wzgledem czego sa interpretowane przy `--project X` != CWD; ja przez to utworzylem magazyn poza udzialem (usuniety). `--geometry plik.geojson` odrzucone ("Obslugiwane: .gpkg, .shp").
8. **P3-8 `--check-updates --plan KATALOG`:** blad dopiero po sprawdzeniu sieci i wydrukowaniu linii stanu (`IsADirectoryError`, rc 1, `io_error` w JSON); brak katalogu nadrzednego jest odrzucany z gory (rc 2 `invalid_input`, `option=plan`). Walidacja w `cli/download_cmd.py` (~L249-255) sprawdza tylko `Path(plan_file).parent.is_dir()`.
9. **P3-9 Komunikaty skladni po angielsku** (`message` w `kartograf-error/1` i tekst): `the following arguments are required: NAZWA`, `argument --product: invalid choice: 'foo' (choose from ...)`, `argument --upgrade: not allowed with argument --check-updates`, `invalid int value`, `expected one argument` - USAGE 9.3 obiecuje komunikat "po polsku, ASCII". Wiersz `usage:` w tekscie tez po angielsku.
10. **P3-10 Brak separatora przed dopiskiem o godlach CZ** w bledach `parse`: `... (dozwolone: 33-35) Godla CZ: SM5 ...`, `Godlo nie moze byc puste Godla CZ: ...`, `... strefa.pas.slup[.subdivisions] Godla CZ: ...`.
11. **P3-11 Drobnostki `catalog`:** `catalog elevation download extra` -> usage calego programu zamiast `catalog`; `catalog --nope --json` -> `command: null` (znana komenda `catalog`); `catalog download` (sama nazwa podkomendy) - blad (zgodnie z `--help`: tylko po GRUPIE).
12. **P3-12 Podpowiedz po `project init`:** `Dodaj zadanie: kartograf project add --project X NAZWA <grupa> download ...` (ma byc `<grupa> <komenda>`; `soil hsg` nie ma `download`) - `cli/project_cmd.py::cmd_project_init`.
13. **P3-13 `cache`:** `cache clear` bez pliku bazy drukuje `Cache wyczyszczony.`/`cleared: true`; `cache_disabled` dla katalogu tylko do odczytu mowi "cache metadanych nieczytelny ... unable to open database file" (to brak zapisu, nie nieczytelnosc).
14. **P3-14 (doc) USAGE 8.2** "Bez `--year` wybierasz najnowszy lot w chwili pobrania": gdy magazyn ma juz starszy lot lokalny, pierwsze `project download` przypina LOKALNY (starszy) lot (`po-download`: 2022 + `Info: dostepna nowsza kampania ... pobierz: --upgrade`), nie najnowszy ze zrodla - zgodnie z trybem domyslnym (USAGE 4.3), ale nie z tym zdaniem.
15. **P3-15 Komunikaty o manifescie:** `--project <plik kartograf-project.json>` -> `nie mozna odczytac .../kartograf-project.json/kartograf-project.json: [Errno 20] Not a directory`; manifest z BOM -> `nieprawidlowy JSON: Unexpected UTF-8 BOM (decode using utf-8-sig)` (mozna byloby czytac `utf-8-sig`). Pozostale 22 uszkodzone warianty manifestu daja czytelne rc 2 bez tracebacku.
16. **P3-16 Gleby/HSG w obszarze maskowanym (zera):** zadania `gleba-il`/`gleby-hsg` pobieraja i przypinaja rastry samych zer bez zadnego komunikatu w `project download` (i bez `--summary`); jest to udokumentowane w USAGE 7, ale agent korzystajacy z `project` nie dostaje sygnalu.
17. **P3-17 CORINE bez `CLMS_CREDENTIALS` w projekcie:** zadanie `landcover download --product corine` przypina podglad PNG (194 B) z jednorazowym `Info:` na stderr; `status`/`verify` i manifest nie oznaczaja pliku jako podgladu (rozszerzenie `.png`, etykieta data); po ustawieniu poswiadczen `project download` nadal `bez zmian`.
18. **P3-18 `Info:` przy `--upgrade` ma niespojny podmiot:** `Info: orto-wycinek: 566000_243000_566200_243200: lokalna wersja ...` (jednostka) vs `Info: granice: boundaries/pl_prg_gmina/bbox/....gpkg: lokalna wersja ...` (sciezka).
19. **P3-19 (doc) `ok` w `kartograf-project-check/1`:** `status`/`verify` -> `ok:false` dla niepobranego zadania, a `project download --check-updates` na tym samym projekcie -> `ok:true` z `not_downloaded` = wszystkie zadania (rc 0). Tak jest zdefiniowane w docstringu `project/model.py::ProjectCheck`, ale USAGE 9 tego nie opisuje; skrypt `... --check-updates && ...` uzna projekt bez przypiec za sprawdzony.
20. **P3-20 Pasek postepu na stdout bez TTY:** `project download`/`elevation download` w trybie tekstowym wypisuja na stdout puste linie i pasek (`[=====] 1/1 + M-34-...`), takze gdy stdout jest potokiem (`-q` wylacza); przy LAZ dwie puste linie i `1/1 kafli`.
21. **P3-21 `--help`:** 19 z 37 lisci (11 x `list-sources`, 2 x `list-layers`, 3 x `cache *`, `project remove|status|verify`) bez bloku `Przyklady`.
22. **P3-22 `parse` PL-2000 (tekst):** powtorzone `strefa: 6` i `Strefa: 6`, `Natywny CRS` pod `Czlony` - znane (PROGRESS, test `test_cli.py` pilnuje tekstu).
23. **P3-23 Srodowisko nie-UTF-8:** `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` + sciezka z polskimi znakami -> `magazyn projektu nie istnieje: ...\u015bcie...` (nie da sie zakodowac sciezki; komunikat mylacy). Dokumenty JSON w tym srodowisku poprawne.
24. **P3-24 Manifest tylko do odczytu:** `project download` najpierw pobiera dane, a dopiero potem zglasza `nie mozna zablokowac projektu (.kartograf-project.lock): Permission denied` (rc 1); po naprawie uprawnien kolejny `download` przypina bez ponownego pobrania (idempotentne, tylko stratny czas).
25. **P3-25 `--upgrade --plan PLIK`, gdy wszystkie pozycje planu to `current`:** rc 0 i zero wydruku (`s-upgrade-plan`) - brak komunikatu "plan bez pozycji do wykonania".

## Uwagi do dokumentacji

| Gdzie | Uwaga |
|---|---|
| USAGE 9.5 (tabela `parse_command`), ARCHITECTURE 4.11 (L~3744) | `run` ma klucze `upgrade`/`force`/`check_updates`/`quiet`/`json`/`summary`/`output_dir`/`workers`/`plan`, nie `update` (P3-3). |
| ARCHITECTURE 3.3.1 (`file_footprint`, `Sidecar.unit`), USAGE 9 (`store_entries`) | `request.bbox` jest "wiarygodny" tylko, gdy plik JEST obszarem zadania (wycinki, kolekcje); dla kafli LAZ nie jest (P2-2). Petla `iter_store(units=[sidecar.unit])` nie dziala dla LAZ. |
| USAGE 4 ("Wymagane hardlinki"), USAGE 7 (SMB bez `serverino`), ARCHITECTURE 3.3.1 (`link_target`) | Dopisac: na cifs bez `serverino` `st_nlink` pliku chwilowo (1-2 s, czasem do ok. 50 s) = 1 po odczycie, wiec `link_target` bywa `None`, a `ensure_link` przepisuje sidecar dowiazania (P2-1). |
| USAGE 8.2 | "Bez `--year` wybierasz najnowszy lot w chwili pobrania" - przy lokalnym starszym locie projekt przypina lokalny (P3-14). |
| USAGE 8.3 | Okreslic, wzgledem czego czyta sie wzgledne `--output`/`--geometry` z linii polecen (CWD), a wzgledem czego zapisuje (projekt); lancuch `../..` dla sciezki poza drzewem projektu (P3-7). Dodac, ze `status`/`verify` nie sprawdzaja `geometry_sha256` (P3-6). |
| USAGE 8.1/8.2 | Dopisac, jak naprawic uszkodzony plik wersji: `verify` -> usunac katalog wersji -> `project download` (nie `--force`) (P3-1). |
| USAGE 9.1/9.3 | `ok` w `kartograf-project-check/1` ma inne znaczenie dla `status`/`verify` i `--check-updates` (P3-19). Opisac, ze komunikat skladni po angielsku (P3-9) albo to poprawic. |
| USAGE 9.2 | Wyjatki od "stderr pusty": dopisac albo usunac `Pominieto wersje o niezgodnym sha256` i `UserWarning` pyproj (P3-2). Przyklad `parse --json` ma w `bounds.bbox` cyfry wyrazajace PROJ `508419.16283969115` vs rzeczywiste `508419.1628396921` (przyklad ilustracyjny). |
| `project init` (CLI) | Hint `NAZWA <grupa> download ...` -> `<grupa> <komenda>` (P3-12). |

## Czego nie dalo sie sprawdzic

- Magazyn na udziale z `serverino` (udzial `data` montowany tylko do odczytu; katalog `test` pusty) - brak magazynu do skanu; P2-1 sprawdzony tylko na cifs bez `serverino` (+ kontrola lokalnego ext4). Skala 50 tys. slotow (Archiwista) nie byla odtwarzana (syntetyczny magazyn 384 slotow / 1229 wpisow; pomiary kosztu z ARCHITECTURE nie weryfikowane).
- CLMS: pobranie rastra CORINE (brak `CLMS_CREDENTIALS`); sprawdzony tylko podglad WMS i komunikat.
- Serwer MCP (`store_overview`, `store_entries`, `store_sidecar`, `project_*`) - nie testowany w tym wycinku (dokumenty sprawdzone przez API biblioteki; parytet bajtowy `describe_store`/`list_store_entries`/`read_store_sidecar` z dokumentem MCP wymagalby klienta).
- Scenariusz "zrodlo ma inna tresc niz przypieta" tylko symulowany (edycja `sha256` przypiecia + usuniete pliki), bez prawdziwej zmiany po stronie uslugi; prawdziwy "nowszy lot" odtworzony przez magazyn z lotem 2022 i zrodlem 2025.
- Tory poza zakresem wycinka nie byly eksplorowane (ortofotomapa PL arkusze ~300 MB, LAZ CZ, `--country auto` LAZ, models3d/maps/geodesy w projekcie).
- Windows/macOS (dowiazania NTFS, CRLF-owe sciezki), `rsync -aH` kopie magazynu (opisane w poprzednim raporcie 2026-10-15).

## Artefakty (poza repozytorium)

- Logi wywolan CLI (`<id>.{cmd,out,err,rc,time}`, `results.jsonl`) i sprawdzenia biblioteki (`*.chk.jsonl`): `<scratch>/cwd-E/logs/`; skrypty jednorazowe: `<cwd-E>/t_*.py`, `drv.py`, `chk.py`, `r.sh`, `run_all_libs.sh`; generator tabeli: `<cwd-E>/report/`.
- Dane: `<katalog-danych>` (podkatalogi `magazyn*`, `projekt-*`, `plan-*.json`).
