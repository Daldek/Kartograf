# fix-collections (slice D: kolekcje) - raport

Worktree `<worktree>`, galaz `fix/e2e-collections` (od develop @ bef87501).
Commity: `a6188d00` feat(notices) names_text; `3d6ec0aa` fix(bledy) przyklad hintu wg produktu; `8a3b70c8` fix(kolekcje) reszta (+ dokumentacja).
Dane live: `<katalog-danych>/fix-collections/{before,after,before-admin,after-admin,mesh-limit,trees-limit,ku-before,ku-after}`.

## Wynik per znalezisko

### D P2-1 (cadastre map auto, obszar tylko PL, aborts) - FIXED
- Przyczyna: `_jobs` budowal jednostki wszystkich czesci w jednej petli; `NoCoverageError` z `_ku_jobs` (RUIAN bez KU w czesci CZ prostokatnej obwiedni) przerywal cale zadanie przed pobraniem czesci PL. Ten sam wzorzec: `discover_teryts_for_bbox` (powiaty PRG), `_area_voivodeships`, `_tile_jobs`, `_sheet_jobs` (GFI BDOT10k, indeks arkuszy CUZK).
- Zmiana (`download/collections.py`): `_jobs` rozbite na `_part_jobs` (jedna czesc kraju) + `_jobs`, ktory zwraca `(jobs, failures)`. Przy `auto` w PL i CZ (>= 2 czesci) `NoCoverageError` (brak jednostek) i `DownloadError` (zapytanie o jednostki zawiodlo) danej czesci to `UnitFailure(<kraj>, <kraj>, tekst, kind)` - drugi kraj dziala dalej; jeden kraj (jawny `--country`, `auto` zawezone) rzuca jak dotad; brak jednostek we WSZYSTKICH krajach = jeden `NoCoverageError`/`DownloadError` z tekstami obu (`_no_units`). `run_request` dokleja te bledy na poczatek `failed`; `plan_request` robi z nich `Warning` `check_failed`.
- Testy: `tests/test_collections_auto.py` (6; 5 nie przechodzi na bef87501): obszar PL-only pobiera PL gdy CZ bez KU; `check_collection` tego samego; obszar CZ-only z bledem PL w trakcie pobierania; oba kraje bez danych = `ok False` bez `auto_partial_success`; jawny `cz` bez KU = `NoCoverageError` jak dotad; BDOT10k+ZTM bez arkuszy w obu krajach = jeden `NoCoverageError` z obu tekstami.
- Live PRZED (develop): `cadastre download --product map --country auto --format SHP --bbox 18.640,49.745,18.650,49.750 --bbox-crs EPSG:4326` -> `Error: map: obszar nie przecina zadnego katastralniho uzemi (RUIAN)`, kod 1 (1,0 s). PO: kod 0 (5,0 s), `Warning: czesc CZ zadania zakonczyla sie bledem (patrz Error) - pobrano PL; kod 0 ...`, plik `cadastre/pl_egib/bbox/474071.459_208684.2788_474794.2857_209243.4144.gpkg: nowa wersja ...`, `Error: CZ: map: obszar nie przecina ... (RUIAN)`. `--check-updates` PO: kod 0, `Warning: CZ: map: ...` + `Warning: czesc CZ zadania nie mogla zostac sprawdzona - sprawdzono PL; kod 0`, pozycja PL `nie da sie sprawdzic bez pobrania`. `--json` PO: `ok: true`, `failed: [{unit: CZ, country: CZ, kind: no_coverage}]`, `notices: [warning auto_partial_success]`.

### D P3-1 (czesciowy sukces auto w kolekcjach = kod 1) - FIXED (regula SCOPE 3.2 / ARCHITECTURE 4.6 jak w `download_data`)
- Zmiana: `download_collection`: `ok = not stale and (not failed or _auto_partial_success(...))`; kraj z bledami przy kraju bez bledow = czesciowy sukces: `ok=True` (kod 0), `Notice` `auto_partial_success` (warning), wpisy zostaja w `failed`, linie `Error:` drukuje CLI jak dla `download_data`. Kod 1: jawny `--country`, jeden kraj, porazka wszystkich krajow. Wspolny tekst/ostrzezenie: nowe `download/area.py::emit_partial_success` (uzyte tez w `download/data.py::_dispatch_area`, ten sam tekst; testy `auto`/`partial` w `test_download_data`/`test_parity`/`test_project_download` zielone). Projekt: zadanie z czesciowym sukcesem nie jest przypinane (`complete = ok and not failed`, bez zmian w kodzie).
- Decyzja do wiadomosci: czesc bez obiektow/jednostek pod `auto` pozostaje wpisem `failed` (`kind` `no_coverage`) + `Error:` (jak CZ bez arkuszy w `download_data`) - czyli powiadomienie = `Warning` `auto_partial_success`, kod 0. Alternatywa (sam `Info:` bez wpisu w `failed`) wymagalaby nowego stanu w `kartograf-download/1`; nie robione. `--check-updates`: pozycje `check_failed` poszczegolnych plikow nadal daja `plan.ok = False` (jak `check_data`); regula dotyczy bledow ustalenia jednostek kraju.
- Live PRZED: `boundaries download --product admin --country auto --level pl=gmina,cz=obec --bbox 18.640,49.745,18.650,49.750 --bbox-crs EPSG:4326` kod 1; PO: kod 0 + ten sam `Warning:`, plik PL zapisany, `Error:` czesci CZ zostaje.

### D P3-3 (`unit_list` w jednej linii) - FIXED
- `notices.names_text` + `LISTED_UNITS = 10` (`a, ..., j i 3874 inne`, formy `inny/inne/innych`); uzyte w `_sheet_jobs` (arkusze, `bez rekordu w indeksie`, blad indeksu), `_tile_jobs`, `_ku_jobs`, powiaty. Wojewodztwa (<= 16) bez zmian. Test: `tests/test_notices.py::test_names_text_*`.
- Live (e71, mesh 560000,240000,575000,250000): linia `Info: mesh: kafle obszaru (3884): <10 kafli> i 3874 inne` (stderr calosci 663 B zamiast 120 814 znakow), potem `Error: mesh: obszar daje 3884 pliki ... limit` kod 2.

### D P3-4 (hydro `--whole-country` sugeruje `--country pl`) - FIXED
- `_resolve`: komunikat i `allowed` z krajow deskryptorow produktu (`--whole-country wymaga --country cz (plik krajowy)` dla `network`, `pl albo cz` dla `admin`); `catalog/commands/_collection.py`: ograniczenie `--whole-country` z krajow produktow grupy (hydro: `--country cz`). Test: `tests/test_ux_messages.py::test_whole_country_names_only_the_countries_of_the_product`.

### D P3-5 (`Info:` 80-95 s dla `names --product world`) - FIXED
- `sources/registry.py::_prng_source`: `response_note` tylko dla `geographic` (pomiar dotyczyl NazwaGeograficznaRP). Test: asercja w `tests/test_names.py::test_world_bbox_outside_poland_and_national_file` (pada na bef87501). USAGE 1.10 uzupelnione.

### D P3-6 (nieistniejacy TERYT) - FIXED
- `_resolve`: blad formatu bez zmian; poprawny format z nieistniejacym wojewodztwem: `--teryt 9999: nie ma wojewodztwa o kodzie 99 (dwie pierwsze cyfry kodu powiatu); dostepne: 02 (dolnoslaskie), ... 32 (zachodniopomorskie)`, `option="teryt"`. Testy: `test_ux_messages` (99, 9999, 33 + format 126), wiersz `test_errors.py` zaktualizowany.

### D P3-7 / C P3-02 / A P3-17 (hint `Przyklad:` bierze pierwszy przyklad) - FIXED ogolnie
- `catalog/hints.py::example_for(command, option, given=None)`: przy `given["product"]` tylko przyklady tego produktu (gdy przyklady komendy rozrozniaja produkty; produkt bez przykladu = brak przykladu, nie obcy), potem pokazujacy opcje, potem kraj (rowny > bez kraju > inny), potem rodzaj wyboru obszaru (teryt/ku/sheet/bbox/geometry/whole_country). Bez `given` zachowanie bez zmian. Plumbing: `error_report(exc, command=, given=)` -> `_library_hint` -> `_option_hint`/`_options_hint`; CLI `main`/`_fail` przekazuje `vars(parsed_args)`; MCP `call_tool` przekazuje `arguments`.
- Nowe przyklady katalogu (zeby produkt mial dopasowany przyklad): `boundaries` `admin --country auto --level pl=gmina,cz=obec` na granicy, `special`, `geomorphology`; `models3d` `trees`; `names` `world`.
- Testy: `test_catalog.py` (2), `test_cli_errors.py` (CLI --json), `test_mcp_server.py` (ten sam wywolanie przez MCP) - wszystkie padaja na bef87501.
- Live PO: `models3d download --product trees --country pl --bbox 560000,240000,575000,250000 --json` -> `hint: "Opcje: --sheet, --bbox, --geometry. Przyklad: kartograf models3d download --product trees --teryt 1261 -o ./data"` (PRZED: przyklad `buildings`).

### D P3-10 (powtorzenie offline mapy CZ po obszarze) - FIXED
- `providers/cuzk/ruian.py::cadastral_areas_for_bbox(..., cache=None)`: odpowiedz (takze pusta) w `MetadataCache.index_area_cache` (klucz `ruian-ku|<warstwa>|<crs>|<mm>`), TTL 7 dni, `--force`/`--upgrade`/`--check-updates` (cache w trybie odswiezania) pytaja usluge i nadpisuja; `_ku_jobs` przekazuje `metadata`. Testy: `tests/test_cuzk_units.py` (trafienie bez sesji, pusta odpowiedz, odswiezanie; padaja na bef87501).
- Live (`cadastre ... --country cz --format SHP --bbox=-452000,-1112000,-450000,-1110500 --bbox-crs EPSG:5514`, powtorzenie pod `unshare -rn`): PRZED kod 1 `Error: Zapytanie https://ags.cuzk.gov.cz/.../RUIAN/MapServer/7/query: pobranie nieudane po 3 probach`; PO kod 0, 3 x `lokalna wersja 2026-10-19 (bez sprawdzania; --check-updates)`.

### D P3-11 (45 vs 44) - FIXED
- `catalog/commands/boundaries.py`: opis `--product special`: 44 rodzaje w wyniku obszaru, obwody spisowe tylko w pliku krajowym (zgodnie z USAGE/README/ARCHITECTURE, 44 warstwy deskryptora).

### Dokumentacja (e2e-D "Uwagi do dokumentacji")
1. USAGE 1.9: domyslnie bez `HEAD` (RUIAN plik krajowy, mapa katastralna CZ) - poprawione, spojne z 4.3; rozmiar RUIAN SHP 251 MB.
2. USAGE 1.8 "2 plikow": juz poprawione w bef87501 (`2 pliki`) - bez zmian.
3. Rozmiary plikow krajowych: tylko RUIAN SHP (251 MB); adresy SHP bez zmian (pomiar z daty).
4. ARCHITECTURE 3.2: klucze `request` `ku`, `tile`, `sheet`; katalog `names`: opis `--horizontal-crs` dla obszaru (rowny natywnemu przyjmowany).
5. `llms.txt`: wszystkie narzedzia MCP grup danych wymienione (148 linii < 150, `tests/test_llms_txt.py` zielony).
6. USAGE 1.9 nowy akapit "`--country auto` w kolekcjach"; ARCHITECTURE 4.6 pkt 3 i 4.10 (regula, `_jobs`, cache KU, `names_text`); USAGE tabela `Notice`: `auto_partial_success` takze kolekcje; USAGE 1.10: `Info:` PRNG tylko `geographic`.
- Nie ruszane (zakaz): `docs/CHANGELOG.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`.

## Proponowany wpis CHANGELOG (Polski, ASCII)
- `--country auto` w kolekcjach (`boundaries`, `cadastre`, `names`, `maps`, `geodesy`): kraj bez jednostek obszaru (np. polski obszar przy granicy bez katastralniho uzemi w RUIAN) albo z nieudanym zapytaniem o jednostki nie przerywa zadania - drugi kraj jest pobierany. Czesciowy sukces konczy sie kodem 0 z `Warning:` `auto_partial_success` (ta sama regula co `elevation` i `imagery`), wpis zostaje w `failed`; `--check-updates` daje `Warning:` `check_failed` i `auto_partial_success`. Kod 1 dla jawnego `--country` i porazki wszystkich krajow.
- Mapa katastralna CZ po obszarze: KU wg RUIAN (takze pusta odpowiedz) w cache metadanych (TTL 7 dni, `--force`/`--upgrade`/`--check-updates` pytaja usluge) - powtorzenie dziala bez sieci.
- `Info:` `unit_list` nazywa co najwyzej 10 jednostek (`... i 3874 inne`); mesh z obszarem ponad limit nie drukuje juz linii 120 KB.
- Komunikaty: nieistniejace wojewodztwo w `--teryt` mowi, ze kodu nie ma, i podaje liste wojewodztw; `--whole-country` bez kraju nazywa kraje produktu (hydro: tylko `--country cz`); `Info:` o 80-95 s tylko dla `names --product geographic`; pomoc `boundaries`: 44 rodzaje granic specjalnych w wyniku obszaru.
- `hint` w `kartograf-error/1` (CLI i MCP): `Przyklad:` z produktu, kraju i wyboru obszaru wywolania (`error_report(..., given=)`, `example_for(..., given)`); nowe przyklady katalogu (`admin --country auto`, `special`, `geomorphology`, `trees`, `world`).
- Dokumentacja: USAGE 1.9 (domyslnie bez `HEAD`), ARCHITECTURE 3.2 (`ku`, `tile`, `sheet`), llms.txt (narzedzia MCP grup kolekcji).

## Proponowana errata ADR
ADR-023 pkt 4-5 / ADR-042: regula czesciowego sukcesu `--country auto` (kod 0 + `Warning:` `auto_partial_success`; kod 1 dla jawnego kraju i porazki wszystkich krajow) obejmuje takze kolekcje (2026-10-19, E2E 0.8.0 D P3-1); kraj, w ktorym obszar nie ma jednostek (RUIAN KU, powiaty PRG, arkusze, kafle) albo zapytanie o nie zawiodlo, jest bledem tego kraju (`UnitFailure` kraju), nie przerwaniem zadania (D P2-1).

## Uwagi dla koordynatora
- Wspolne pliki (mozliwe konflikty merge): `kartograf/cli/commands.py` (FixStderr: ja zmieniam tylko `_fail`/`main` - `given`), `download/collections.py` (FixLandcoverSoil: `within_volume`; FixCancel: blok puli w `run_request` - moje zmiany w innych hunkach), `llms.txt` (FixLandcoverSoil), `docs/USAGE.md` 1.8/1.9/1.10, `docs/ARCHITECTURE.md` 3.2/4.6/4.10, `error_report.py`, `download/data.py` (jedna zmiana: `emit_partial_success`).
- `names_text` jest publiczny w `kartograf.notices` - FixLandcoverSoil ma go uzyc dla BDOT10k (ten sam tekst listy powiatow).
- Wpadka procesowa: jedna edycja `notices.py` trafila przez sciezke wzgledna do glownego checkoutu (`<repo>`); cofnieta od razu tym samym narzedziem (tag z powrotem 7528, `git status` glownego checkoutu czysty), reszta pracy tylko w worktree.
- Nie zrobione / poza slice: P3-12 (szacunek czasu EGiB), P2-2 (Ctrl-C, FixCancel), P3-2/8/9.

## Brama
`scripts/gate.sh` z korzenia worktree (po commitach `3d6ec0aa`, `8a3b70c8`): ruff check - OK; ruff format --check - OK; mypy (306 plikow) - OK; pytest offline - 7204 passed, 18 deselected, 0 failed (184,9 s). Pierwsze uruchomienie wykrylo blad mypy (`UnitFailure.kind` jako `str`) - poprawione (`FailureKind`) przed ostatnim przebiegiem.
