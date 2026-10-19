# R2 - slice MCP: agent Claude Code (haiku) przez kartograf-mcp - raport

Data: 2026-10-19. Instalacja: wheel 0.8.0 z `git archive cf39177a` (venv `kartograf-e2e-0.8.0-r2/venv`, mcp 2.3.0, 29 narzedzi).
Serwer: `kartograf-mcp --allow-dir <katalog-danych> --cache-file <cwd>/metadata.db` (swiezy cache). Dane: `<katalog-danych>/R2/mcp/{magazyn,magazyn-projekt,projekt}`.
Agent: `claude -p --model haiku --mcp-config mcp.json --strict-mcp-config --tools "" --allowedTools mcp__kartograf --permission-mode dontAsk --no-session-persistence --output-format stream-json --verbose`, 6 zadan, kazde osobne wywolanie (kolejno, ten sam magazyn).
Skrypty/logi: `kartograf-e2e-0.8.0-r2/cwd-mcp/` (`run.sh`, `tasks.txt`, `out-t*.jsonl`, `final-t*.txt`, `summ2.py`, `parity.py`).

## Incydent metodyczny (pierwszy przebieg uniewazniony)
Pierwszy przebieg (`contaminated/`) wywolywal `run.sh` w petli `while read ... < tasks.txt`; `claude -p` czyta stdin, wiec dolaczyl do promptu reszte `tasks.txt` i kazdy agent wykonal wiele zadan naraz (14-17 wywolan narzedzi na zadanie). Wyniki odrzucone, magazyn i cache wyczyszczone, `run.sh` dostal `< /dev/null`; przebieg powtorzony od zera (ponizej). Wniosek dla rundy 1: `cwd-F/run.sh` bez `< /dev/null` jest podatny na to samo (nie sprawdzano, czy wplynelo na wyniki F).

## Wyniki per zadanie (agent)

| Zad. | Opis | Wywolania narzedzi | is_error | Tury | Czas (sciana / API) | Koszt USD | Odpowiedz agenta |
|---|---|---|---|---|---|---|---|
| t1 | dostepnosc + pobranie NMT 5 m EVRF2007 M-34-64-D-d-1-2 | 2 (`elevation_availability`, `elevation_download`) | 0 | 3 | 19,1 s / 16,2 s | 0,0046 | POPRAWNA: rok 2019, sciezka, sha256 `23d160d0...337f` |
| t2 | Cieszyn NMPT 5514, `country auto`, etykiety, `full_m2`/kampanie | 1 (`elevation_availability`, bbox + `bbox_crs` + `country: auto`) | 0 | 2 | 27,8 s / 25,5 s | 0,0042 | POPRAWNA co do danych (patrz nizej), 1 uwaga |
| t3 | `cadastre map --country auto` obszar tylko PL 18.640,49.745,18.650,49.750 / 4326 | 2 (pierwsze bez `format` -> blad, drugie z `SHP`) | 1 (oczekiwany, `invalid_input` `--format`) | 3 | 22,5 s / 20,5 s | 0,0024 | POPRAWNA: plik PL, `auto_partial_success`, blad CZ `no_coverage`; drobna nieprecyzja sciezki wersji |
| t4 | zly CRS (metry z EPSG:4326), soil clay | 2 (`soil_download` 4326 -> blad, potem 2180 -> OK) | 1 (oczekiwany, `invalid_input`, `option=bbox`) | 3 | 15,2 s / 12,3 s | 0,0027 | POPRAWNA: wyjasnil blad (metry vs stopnie, zakresy), zglosil zmiane CRS, podal 3 sposoby naprawy |
| t5 | `project init/add/download/status` NMT 5 m | 5 (`get_catalog`, `project_init`, `project_add`, `project_download`, `project_status`) | 0 | 6 | 17,0 s / 14,4 s | 0,0055 | POPRAWNA: zadanie `nmt-5m` przypiete, sha8 i rozmiar 1 680 683 B zgodne z manifestem |
| t6 | przeglad magazynu (segmenty, pliki, dataset, obrys WGS84) | 5 (`store_overview`, 3 x `store_entries`, `parse_sheet`) | 0 | 6 | 110,1 s / 106,9 s | 0,0178 | POPRAWNA co do segmentow/datasetow/rozmiarow; obrysy WGS84 PRZYBLIZONE (reczne przeliczenie, patrz P3-3) |

Razem: 17 wywolan narzedzi, 2 `is_error` (oba oczekiwane, oba naprawione przez agenta jednym ponowieniem), 23 tury, koszt 0,0372 USD. stderr serwera/CLI (`err-t*.log`): puste we wszystkich zadaniach.

### Weryfikacja niezalezna (venv python, pyogrio/rasterio/pyproj/hashlib)
- sha256 na dysku = sha w odpowiedzi agenta i w sidecarze (`.meta.json`) dla wszystkich 3 plikow; link i `versions/` bajtowo rowne:
  - NMT `M-34-64-D-d-1-2.asc` `23d160d0bc394cec6a8db9d5dd212820349c8377e574513e6da4aac2bc59337f`, 1 680 683 B, nagłówek ASC 454x469, cellsize 5 (identyczny hash jak w rundzie 1);
  - EGiB `...474071.459_208684.2788_474794.2857_209243.4144.gpkg` `c432a7fe3ea2b0d2aeb7aab0cd6f7c370ced82aff8a0d581852cab6b363265e3` (= hash rundy 1 `d15-cadmap-pl-only`), 401 408 B, warstwy `dzialki` 545 i `budynki` 199 obiektow, EPSG:2180 (zgodne z odpowiedzia t6);
  - SoilGrids clay 0-5 cm `346cf3c6a310b37d9feec79ffc2b69c94a7647733fc0510ce4a5e7edfceb4034`, 639 B, GeoTIFF int16 8x13 EPSG:4326 (wartosci 0..100, nie same zera; identyczny hash jak w rundzie 1).
- Projekt: manifest `kartograf-project/1`, zadanie `nmt-5m`, sha256 i rozmiar jak wyzej; magazyn projektu zawiera ten sam plik (sha rowny). `project verify` (CLI i MCP) rc 0.
- `parse_sheet`/`store_entries` zgodne z biblioteka (`iter_store`, `file_footprint`).

## Tabela znalezisk (finding, powtorzenie, przed, po, werdykt)

| Id | Powtorzenie | Przed (runda 1) | Po (runda 2) | Werdykt |
|---|---|---|---|---|
| D P2-1 (cadastre map `auto`, obszar tylko PL) | agent: `cadastre_download` product map, country auto, bbox 18.640,49.745,18.650,49.750 EPSG:4326 (t3) | CLI: `Error: map: obszar nie przecina zadnego katastralniho uzemi (RUIAN)`, rc 1, brak pliku PL | `kartograf-download/1`, `ok: true`; `files[0]` PL `cadastre/pl_egib/bbox/474071.459_208684.2788_474794.2857_209243.4144.gpkg` status `new`; `failed: [{unit: CZ, country: CZ, kind: no_coverage, error: "map: obszar nie przecina ... (RUIAN)"}]`; `notices: [warning auto_partial_success]`. Agent poprawnie wyjasnil: czesciowy sukces, PL pobrane, CZ bez KU = oczekiwane | PASS |
| C P2-8 (zly CRS bbox -> blad wewnetrzny) | agent: `soil_download` bbox `[626000,480000,628000,482000]` + `bbox_crs EPSG:4326` (t4) | `OverflowError`/`inf` w zapytaniu | `is_error: true`, `kartograf-error/1` `invalid_input`, `details.option=bbox`, komunikat: "wspolrzedne (...) leza poza zakresem EPSG:4326 (dlugosc -180..180, szerokosc -90..90). Sprawdz --bbox-crs (domyslnie EPSG:2180; ...) i kolejnosc osi", `hint` z `--bbox-crs`; agent wyjasnil przyczyne i naprawil (2180); parytet z CLI rc 2 | PASS |
| D/F: Cieszyn NMPT, KD (full_m2, campaign_coverage) przez MCP | agent: `elevation_availability` nmpt, `country auto`, bbox 5514 (t2) | runda 1 (F t5): 2 wywolania osobno (pl, cz), brak pytania o KD | jedno wywolanie `auto` -> `areas` PL (area_m2 = land_m2 = 716 577) i CZ (1 000 000), 7 kombinacji `complete: true` (PL 5, CZ 2), pola `full_m2` i `campaign_coverage` (PL: kampanie GK-FOTO.6201.11.2024, GI-FOTO.6201.11.2022, GI-FOTO.6202.37.2021, NM-34-011/11 x2; CZ: `campaign_coverage: []`), `sheets_full`, `download_hint`, `notices: cz_service_only`. Agent uzyl wszystkich tych pol w odpowiedzi (tabela PL/CZ, `full_m2`, liczba kampanii), poprawnie rozpoznal najspojniejsza pare (PL 2022/2024 + CZ 2026, EVRF2007) | PASS (P3-2 nizej) |
| A P2-2 / stderr pyproj `Best transformation...` | CLI `availability --country auto --bbox-crs EPSG:5514 --json` | warning na stderr w `--json` | stderr 0 B (CLI), `err-t2.log` pusty (serwer MCP) | PASS |
| F t6 (projekt przez MCP: `project_add`, nazwa zadania) | t5 z nazwa `nmt-5m` (mala litera) | F t6: pierwszy `project_add` z wielka litera = `is_error` | 0 bledow; `project_init` -> `project_add` -> `project_download` -> `project_status` bez bledow, 6 tur | PASS (nazwy z wielkimi literami nie sprawdzane) |
| F t7 / store (segmenty, dataset) | t6: `store_overview` + `store_entries` | F t7: 5 wywolan, odpowiedz poprawna | 5 wywolan; segmenty, `dataset_key`, rozmiary, sha8, etykiety, warstwy GPKG (545/199) poprawne | PASS (obrysy: P3-3, bez zmiany wzgledem rundy 1) |

## Parytet dokumentow MCP == CLI `--json` (5 par, `parity.py`)
`structuredContent` == `content[0].text` (JSON) == dokument CLI (po usunieciu `checked_at`), te same klucze w tej samej kolejnosci; `is_error` zgodne z kodem wyjscia CLI:

| Para | CLI rc | MCP `is_error` | Rowne |
|---|---|---|---|
| `elevation_availability` nmpt, auto, Cieszyn 5514 (`kartograf-availability/1`) | 0 | false | tak |
| `project_status` (`kartograf-project-check/1`) | 0 | false | tak |
| `project_verify` (`kartograf-project-check/1`) | 0 | false | tak |
| `soil_download` zly CRS (`kartograf-error/1`) | 2 | true | tak |
| `soil_download` powtorzenie lokalne (`kartograf-download/1`) | 0 | false | tak |
Dodatkowo: `store_overview` (`kartograf-store-overview/1`) == `kartograf.describe_store(...).to_json()` (tak; narzedzia `store_*` nie maja odpowiednika CLI).

## Nowe regresje
Brak. Wszystko, co dzialalo w rundzie 1 (NMT 5 m EVRF2007, project init/add/download/status, store, Cieszyn), dziala; hashe plikow identyczne jak w rundzie 1.

## Nowe znaleziska

### P1
Brak.

### P2
Brak.

### P3
1. **P3-1 `cadastre download --product map --country auto` wymaga `--format` takze dla obszaru tylko w PL.** Pierwsze wywolanie agenta (bez `format`) = `is_error` `invalid_input` (`--format wymagane: SHP, DXF, DGN, VFK`); format dotyczy tylko czesci CZ, a plik PL (EGiB GPKG) go ignoruje (agent zauwazyl: "ustawilem SHP, ale dla PL zapisany plik to .gpkg"). `hint` ma przyklad z CZ (`--ku 623164 --format SHP`), choc wywolanie mialo `country auto` + `bbox`. Skutek: jedna dodatkowa tura agenta; blad jest czytelny i agent naprawil go sam. Do rozwazenia: wymog formatu dopiero gdy czesc CZ ma jednostki, albo hint z `--country auto --bbox ... --format SHP`.
2. **P3-2 pola raportu dostepnosci nie niosa semantyki dla agenta.** Agent (t2, bez wywolania `get_catalog`) nie umial pogodzic `complete: true`, `uncovered_m2: 0` i `full_m2` 992 606 < `area_m2` 1 000 000 dla CZ ("Nie umiem tego pogodzic z raportem") oraz zinterpretowal `campaign_coverage: []` jako "0 kampanii - CUZK nie ma identyfikatora kampanii" (trafnie, ale z domyslu). USAGE 1.7 opisuje to (CZ: `full_m2 < land_m2`, gdy obszar wychodzi poza arkusze; `area_m2` CZ = prostokat, przy granicy obejmuje PL; `sheet_records`/`campaign_coverage` puste), ale `grep full_m2` w `llms.txt`, `kartograf/catalog` i `mcp_server.py` = 0 trafien, a opis narzedzia `elevation_availability` nie wyjasnia pol. Dodatkowo `areas` pod `auto` sumuja sie do 1 716 577 m2 przy prostokacie 1 000 000 m2 (PL przyciete maska ladu PRG, CZ = caly prostokat; udokumentowane w USAGE, nie w dokumencie). Sugestia: krotkie opisy pol (albo `get_catalog` `schemas`) dla `full_m2`, `campaign_coverage`, `area_m2` CZ.
3. **P3-3 narzedzia MCP `store_*` nie zwracaja obrysu WGS84.** Prosba "obrys w WGS84" (jak w rundzie 1 F t7) nie ma narzedzia: `store_entries` zwraca sidecary (bbox w `request`, CRS natywny), a `file_footprint` jest tylko w bibliotece. Agent przeliczyl obrysy recznie i uczciwie to zaznaczyl; wartosci przyblizone: EGiB podal 18,639-18,649 E (prawdziwe 18,640-18,650), soil 20,842-20,871 E / 52,172-52,190 N (prawdziwe 20,843-20,873 / 52,171-52,190), NMT 19,906-19,937 / 50,0625-50,0838 (prawdziwe 19,906-19,9375 / 50,0625-50,0833). Bez zmian wzgledem rundy 1; to luka funkcjonalna interfejsu agenta (`file_footprint` = tylko biblioteka), nie blad.
4. **P3-4 uwaga o jakosci odpowiedzi agenta (nie blad Kartografa):** w t3 agent skrocil sciezke kopii wersji do `.../magazyn/cadastre/versions/bbox/2026-10-19_c432a7fe/` (brak segmentu `pl_egib/`); sciezka pliku glownego podana poprawnie. W t2 agent bez prosby zaproponowal podzial PL/CZ powierzchni (283 000 m2 po stronie CZ) wyprowadzony z `full_m2`/`area_m2` i zaznaczyl, ze to wniosek.
5. **P3-5 latencja t6:** 110 s (106,9 s API) przy 5 wywolaniach i ok. 15 KB wynikow `store_entries` (3 x sidecar pelny); inne zadania 15-28 s. Wolny jest model (tura odpowiedzi), nie serwer (`store_*` < 0,1 s w `parity.py`); sidecary w `store_entries` sa dlugie (EGiB 4,3 KB, NMT 7,9 KB), co zwieksza koszt (0,0178 USD = 48% kosztu przebiegu).

## Podsumowanie liczbowe
- Zadan agenta: 6, odpowiedzi poprawne: 6/6 (t6: obrysy przyblizone, zaznaczone przez agenta).
- Wywolan narzedzi: 17; `is_error`: 2 (oba oczekiwane: t3 `--format`, t4 zly CRS); tur: 23; koszt 0,0372 USD; czas 2-110 s.
- Parytet MCP == CLI: 5/5 (+ 1 wzgledem biblioteki).
- Znaleziska z rundy 1 potwierdzone naprawione: 2/2 testowane przez agenta (D P2-1, C P2-8) + stderr pyproj; regresje: 0.
- Nowe: P1 0, P2 0, P3 5.
