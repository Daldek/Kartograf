# Raport: fix-pl-sheets (E2E 0.8.0, plasterek A/B/C: arkusze PL, opcje, availability, bbox)

Branch `fix/e2e-pl-sheets` (od develop @ bef87501), worktree `<worktree>`.
Brama: `scripts/gate.sh` ZIELONA (`GATE OK (201 s)`: ruff check, ruff format --check, mypy, pytest offline `7185 passed, 18 deselected`).

Commity (Conventional Commits, bez Co-Authored-By, autor Daldek):

| Hash | Opis |
|---|---|
| `7a30718f` | fix(download): sprawdzenie arkuszy bez danych i rodzaje porazek jak w pobraniu (manager.py, data.py + testy) |
| `b0898002` | fix(bbox): walidacja zakresu EPSG:4326 i bboxa o zerowej powierzchni przed siecia (options.py, countries.py, arguments.py, download_cmd.py + testy) |
| `729ca686` | fix(availability): obwiednia kraju, obszar bez ladu i --min-density w bledzie LAZ |
| `3aaafed2` | docs: przyklady USAGE 1.1 sprawdzone na zywo, stany danych w sprawdzeniu, kinds, availability |

Dane live: `<katalog-danych>/fix-pl-sheets/` (`<katalog-danych>`; tylko tryb `--check-updates` i walidacje, zero pobran danych). Zadnych plikow poza tym katalogiem i `cwd` (worktree).

## Wyniki per znalezisko

### e2e-A P2-3 - `--check-updates`/plan: arkusz bez danych = `check_failed` (rc 1) - FIXED
- Przyczyna: `DownloadManager.inspect_sheets` zwraca `SheetInspection(error=NoCoverageError)`, a `updates._items` mapowal kazdy `error` na pozycje `check_failed`; pobranie tego samego obszaru traktuje `NoCoverageError` jako stan danych (`NO_COVERAGE_SOME`, kod 0).
- Decyzja projektowa: arkusz bez danych to **stan danych, nie pozycja planu** (brak pliku zrodla; `ItemStatus` bez nowej wartosci -> `project check`/`FileCheck` bez zmian i bez falszywych `added`). Parytet z pobraniem: >= 1 arkusz z danymi -> `Warning: GUGiK nie ma danych dla N z M arkuszy (...)` + hinty `Info:` (te same funkcje tekstu co pobranie), `plan.ok` = true, kod 0; zaden arkusz z danymi -> `NoCoverageError` (pojedynczy arkusz: jego wlasny blad z podpowiedzia; lista: `GUGiK nie ma danych dla zadnego z N arkuszy obszaru`), kod 1; `check_failed` zostaje tylko dla awarii skorowidza (siec/5xx).
- Zmiana: `kartograf/download/manager.py` - `DownloadManager.check_sheets(sheets, *, on_no_coverage=None)` (klasyfikacja bledow inspekcji, `no_coverage_text(total)`), `_download_planned` oznacza `no_coverage`; `kartograf/download/data.py` - `_check_no_coverage`/`_no_coverage_warning`/`_coverage_hints` (wspolne z `_finish_pl_sheets`), `_check_error` + `_Run.causes` (check_data rzuca blad pierwszej porazki, wiec kod bledu = `no_coverage`/`year_out_of_range`, nie `download_failed`), `_plan_modes` wewnatrz `try` w `_download_pl_code`.
- Testy: `tests/test_updates.py` (4 testy: arkusz bez danych nie jest pozycja, pojedynczy arkusz, wszystkie bez danych, konflikt lat jako jeden blad), `tests/test_download_data.py` (partial coverage = plan ok + to samo ostrzezenie co pobranie, wszystkie bez danych, `check_failed` zostaje dla awarii indeksu).
- Live PRZED (develop, 2026-10-19): `kartograf elevation download --sheet N-34-130-D --product nmt --resolution 5m --vertical-crs EVRF2007 -o <katalog-danych>/before-check --check-updates` -> **rc=1**, 64 linie, 39 x `nie udalo sie sprawdzic: Brak danych NMT 5m dla N-34-130-D-a-1-1 ...`, 25 x `do pobrania`.
- Live PO: to samo polecenie -> **rc=0**, stdout 25 linii `do pobrania`, stderr `Warning: GUGiK nie ma danych dla 39 z 64 arkuszy (N-34-130-D-a-1-1, ... ...) - pominiete (...); sprawdzono 25` + 2 x `Info: Skorowidz GUGiK ma ten arkusz w NMT 1m ...`; `--json`: `kartograf-plan/1`, `ok: true`, 25 pozycji `missing`, `notices`: `no_coverage_some` + 2 x `no_coverage_hint`. To pierwszy przyklad USAGE 1.1.
- Live PO (konflikt lat, D3): `--bbox 530000,382000,533000,386000 --min-year 2023 --max-year 2024 ... --check-updates` -> rc=1, **jeden** `Error: brak danych z lat 2023-2024 dla 3 z 9 arkuszy - nic nie pobrano:` (bylo: 3 pozycje `check_failed`, `dla 1 z 1 arkuszy`); z `--min-year 2022` -> rc=0.

### e2e-A P3-3 / e2e-B P3-1 - `failed[].kind` `download` zamiast `no_coverage` dla pojedynczego `--sheet` - FIXED
- Przyczyna: `_download_pl_code` lapal `DownloadError` -> `"download"` (inaczej niz sciezka wycinka).
- Zmiana: jedna funkcja `_failure_kind(error, default)` w `data.py` (`NoCoverageError` -> `no_coverage`, `YearRangeError` -> `year_out_of_range`, reszta `default`), uzyta we wszystkich miejscach, gdzie `except DownloadError` zapisuje porazke: arkusz PL, lista, archiwum, pliki ATOM, wycinek PL, tory CZ (arkusz/wycinek, LAZ, orto, warstwice) i rozdzielanie krajow (`default="country"`).
- Test: `test_single_sheet_without_data_is_a_no_coverage_failure` (download: `[(sheet, "no_coverage")]`, check: `NoCoverageError`).

### e2e-B P3-2 - rok poza zakresem: `kind` `download`, brak `year_out_of_range`; komunikat per arkusz w check - FIXED (decyzja: kod, nie dokumentacja)
- Uzasadnienie: tabela kodow bledow (USAGE 9.3) jest poprawna, a `failed[].kind` nie mial dla danych odpowiednika; spojnosc z innymi torami: `no_coverage` jest juz nazwa kodu `NoCoverageError`, wiec `YearRangeError` -> `year_out_of_range` (dodatkowa wartosc wyliczenia `FailureKind`, zgodna z zasada addytywnosci `/1`). Dotyczy tez LAZ/`auto` (`country` zostaje dla innych bledow).
- Check: `check_sheets` zbiera konflikty lat wszystkich arkuszy w jeden `year_range_error(..., total=liczba_arkuszy)` jak `_checked_range` (komunikat `dla N z M arkuszy`, `details.sheets`, hinty) zamiast `check_failed` per arkusz.
- Test: `test_year_conflict_is_year_out_of_range_in_the_download_and_the_check` (download wieloarkuszowy i pojedynczy `--sheet` -> `year_out_of_range`; check -> jeden `YearRangeError`, `dla 2 z 4 arkuszy`).
- Docs: USAGE 9.3 (akapit o `failed[].kind`), USAGE 4.3.

### e2e-A P3-2 / e2e-B P3-5 - `--workers 0/-1` po cichu w elevation/imagery - FIXED
- Przyczyna: CLI `workers = getattr(args, "workers", 4) or 1` (0 -> 1), `download_data` sprawdzal tylko typ; `DownloadManager` obcina `max(1, workers)`.
- Zmiana: `download/arguments.py::require_workers(value, name="--workers")` (kod 2, `option="workers"`, tekst `--workers musi byc >= 1, podano N`), uzyty w `data.py::_start`; usuniete `or 1` w `cli/download_cmd.py`. Nie ruszalem `collections.py`/`project/operations.py` (maja wlasne sprawdzenia; helper mozna tam podpiac - pliki innych plasterkow) ani `LandCoverManager` (FixLandcoverSoil).
- Test: wiersz w `tests/test_errors.py` (`download_data(workers=0)`).
- Live PO (offline `unshare -rn`): `elevation download ... --workers 0 --json` -> rc=2 `kartograf-error/1` `invalid_input`, `"--workers musi byc >= 1, podano 0"`; `imagery download ... --workers -3` -> rc=2; `maps ... --workers 0` bez zmian (rc=2).

### e2e-C P2-8 - bbox z zlym CRS (metry z `--bbox-crs EPSG:4326`) -> bledy wewnetrzne - FIXED
- Przyczyna: `validate_request_bbox` sprawdzal tylko skonczonosc i `min <= max`; metry jako stopnie dawaly `inf`/`nan` dopiero w providerach (BDOT10k `OverflowError`, CORINE `ValueError`, SoilGrids `SUBSET=long(inf,-inf)`).
- Zmiana (jedno wspolne miejsce, z ktorego korzystaja wszystkie grupy: elevation/imagery, kolekcje, landcover/soil/hsg, availability, wycinki, LAZ): `download/options.py::validate_request_bbox` - EPSG:4326: dlugosc w +-180, szerokosc w +-90, inaczej `ValidationError(option="bbox", hint=BBOX_CRS_REMEDY)` (kod 2, `details.option=bbox`); tekst naprawczy `BBOX_CRS_REMEDY` w `download/countries.py` (ten sam co `outside_country` dla BDOO/ZABAGED/HSG - zdeduplikowany). `core.bbox.validate_bbox` bez zmian (punkt dozwolony dla `find_sheets_for_bbox`). Uzgodnione z FixLandcoverSoil (nie dodaja wlasnej kontroli).
- Testy: `tests/test_errors.py` (download_data/check_data, zakres, szerokosc 91-92), `tests/test_cli.py::TestParseBboxArg` (`test_metres_given_as_degrees_are_refused_with_the_remedy`); istniejacy `test_all_public_bbox_tracks_reject_invalid_input_before_network` nadal przechodzi.
- Live PO (offline, rc=2, stdout puste): `landcover download --product bdot10k|corine --bbox 626000,480000,628000,482000 --bbox-crs EPSG:4326`, `soil download ...`, `soil hsg --bbox 19,91,20,92 --bbox-crs EPSG:4326` -> `Error: Nieprawidlowy bbox: wspolrzedne (...) leza poza zakresem EPSG:4326 (dlugosc -180..180, szerokosc -90..90). Sprawdz --bbox-crs (...) i kolejnosc osi (...)`. PRZED (z raportu E2E-C, nie powtarzane na develop): rc=1 `OverflowError`/`ValueError`/zapytanie z `inf`.

### e2e-B P3-8 - bbox zerowej powierzchni przyjety - FIXED
- Zmiana: ten sam `validate_request_bbox`: `min_x == max_x` albo `min_y == max_y` -> `Nieprawidlowy bbox: bbox o zerowej powierzchni (min == max): ...` (kod 2, `option=bbox`).
- **Zmiana zachowania do odnotowania:** `--bbox x,y,x,y` (punkt) nie jest juz przyjmowany w zadnej komendzie (bylo: arkusz zawierajacy punkt / wycinek 1x1 px); punkt wskazuje sie `--geometry` (plik z punktem omija `validate_request_bbox` w torze listy arkuszy; w torach wycinka i LAZ obwiednia punktu przechodzi przez te kontrole i jest odrzucana). Test `TestParseBboxArg::test_point_allowed` zastapiony `test_zero_area_is_rejected` (przypieta zmieniana celowo regula).
- Testy: `tests/test_errors.py` (punkt i linia, download_data i check_availability), `tests/test_cli.py`.
- Live PO (offline): `imagery download --product orto --country pl --bbox 566000,243000,566000,243000 --cutout ...` -> rc=2 `bbox o zerowej powierzchni` (PRZED: plik 1x1 px, rc 0).

### e2e-A P3-4 - availability bez walidacji "obszar poza obwiednia kraju" - FIXED
- Zmiana: `download/availability.py::_explicit_area` (wolane z `_parts`): dla `--country pl|cz` z `--bbox`/`--geometry` `outside_country(...)` jak `_dispatch_area` (ten sam tekst, `option=bbox|geometry`); godlo PL i `auto` bez zmian.
- Testy: `tests/test_errors.py` (CZ + bbox Krakowa, PL + bbox Hamburga, zero-area w availability).
- Live PRZED: `availability --product nmt --country cz --bbox 565000,242000,569000,246000` -> rc 0 `Brak arkuszy NMT dla obszaru w indeksie CUZK`, `obszar 18,47 km2`; `--country pl --bbox 9.9,53.5,10.0,53.6 --bbox-crs EPSG:4326` -> rc 0 `obszar 0,00 ha`. PO: rc=2, `Error: --bbox (EPSG:2180) lezy poza CZ (w EPSG:4326: 19.91,50.04,19.96,50.08). Sprawdz --bbox-crs ...` i `--json` `kartograf-error/1` `details.option=bbox`.

### e2e-A P3-16 - availability obszaru calkiem na morzu - FIXED (wybrana opcja: Info + komunikat, invariant zostaje)
- Decyzja: **`complete` bez zmian** (pusty lad jest w calosci pokryty: `full_m2 == land_m2 == 0`, wiec inwariant `complete <=> full_m2 == land_m2` pozostaje prawdziwy dla kazdego obszaru); rozwiazanie to komunikat, nie zmiana danych: `Info:` kod **`no_land`** (nowa stala `kartograf/notices.py::NO_LAND`, emitowana z `_check_pl`, gdy sa kombinacje, a `land_px == 0`), kolumna KOMPLET `brak ladu` zamiast `tak`, stopka `Obszar nie ma ladu PL (morze albo poza granica panstwa) - nie ma czego pobierac, wiec bez podpowiedzi pobrania (...)` zamiast `Najnowsza kompletna kombinacja ... Pobranie`. JSON: `complete: true`, `areas[].land_m2: 0.0`, notice `no_land`.
- Alternatywa odrzucona: `complete = false` dla `land_m2 == 0` zlamalaby udokumentowany inwariant (i test `test_full_m2_is_the_land_in_full_sheets`); jesli koordynator woli twardsza semantyke - zmiana to jedna linia w `_combination` (`complete=missing.full == 0 and land_px > 0`) + doprecyzowanie USAGE 1.7.
- Test: `tests/test_cli_availability.py::test_area_without_land_says_so_and_proposes_no_download` (maska PRG morze, Krakow: `land_m2 == 0`, wszystkie `complete`, jedno `no_land`, tabela `brak ladu`, brak `Najnowsza kompletna kombinacja`/`Pobranie`).
- Live PRZED: `availability --product nmt --country pl --bbox 340000,746000,342000,747000` -> `obszar 2,00 km2, w tym lad 0,00 ha`, 15 kombinacji `tak` (takze `0/2` arkuszy), stopka `Najnowsza kompletna kombinacja: 2025 PL-1992 0.5m EVRF2007 ASC` + `Pobranie ...`. PO: rc=0, 15 x `brak ladu`, stderr `Info: obszar nie ma ladu PL (morze terytorialne albo obszar poza granica panstwa) - ...`.
- Docs: USAGE 1.7 (definicja `area_m2`/`land_m2`, obszar bez ladu - D7 z raportu E2E-A).

### e2e-A P3-9 - LAZ `--min-density` odfiltrowujace wszystko - FIXED
- Zmiana: `providers/pl/gugik_laz.py::LazTileSelection.below_density` (kafle odrzucone przez `min_density`, wypelniane w `select_tiles`), `download/laz.py::no_tiles_message(selection, min_density)`: `Brak kafli LAZ dla podanego obszaru: --min-density 12 odrzucilo 13 kafli obszaru (najwyzsza gestosc nominalna 4 pkt/m2) - obniz albo pomin --min-density`; bez odrzuconych kafli zostaje dotychczasowy `NO_TILES_MESSAGE`.
- Testy: `tests/test_gugik_laz.py` (`below_density`), `tests/test_laz_download.py` (komunikat z flaga i bez odrzuconych kafli).
- Live PRZED/PO: `--sheet N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12 --vertical-crs EVRF2007 --check-updates` -> rc=1; PO tekst jak wyzej (13 kafli, 4 pkt/m2).

### Docs - przyklady USAGE 1.1 (D1-D3) - FIXED
Zamienione na dzialajace z biezacym skorowidzem (kazdy sprawdzony na zywo `--check-updates`, rc 0):
- D1: `kartograf elevation download --bbox 637400,487000,637450,487050 --product laz --min-density 12 --vertical-crs EVRF2007 --country pl -o ./data` (Warszawa, 2025 EVRF2007, 12 pkt/m2; `availability` `densities: [12]`; poprzedni przyklad Krakow ma 4 pkt/m2).
- D2: `--sheet 6.179.12.20 --product nmt --resolution 0.5m --vertical-crs EVRF2007` (`do pobrania (2021-09-08_77247)`; 1 m nie istnieje dla tego arkusza).
- D3: `--bbox 530000,382000,533000,386000 --min-year 2022 --max-year 2024 ...` (9 arkuszy; 2023-2024 daje 3 arkusze tylko z 2022 -> `year_out_of_range`, opisane w 4.1).
Pozostale zmiany dokumentacji: USAGE 1.1 (akapit o bledzie `--min-density`), 1.7 (obwiednia kraju, obszar bez ladu), 4.3 (sprawdzenie arkuszy bez danych i konfliktu lat), 9.3 (`failed[].kind`); ARCHITECTURE 4.1 (stany danych w `check_sheets`), 4.2.

## Proponowany wpis do docs/CHANGELOG.md (po polsku, ASCII, styl [0.8.0]; NIE edytowalem pliku)

```
### Poprawki po E2E (plasterek arkuszy PL, availability i bbox)
- `--check-updates` i plan (`check_data`, `project download --check-updates`) traktuja arkusz bez danych w skorowidzu jak pobranie: to stan danych, nie pozycja planu ani `check_failed`. Obszar z dziurami pokrycia (np. `--sheet N-34-130-D --resolution 5m`) daje kod 0 i `Warning: GUGiK nie ma danych dla N z M arkuszy ...` (`no_coverage_some`, `ok: true`); brak danych we wszystkich arkuszach to `no_coverage` (kod 1); arkusze z danymi tylko poza zakresem lat to JEDEN blad `year_out_of_range` dla wszystkich arkuszy (nie `dla 1 z 1 arkuszy` per arkusz). `DownloadManager.check_sheets(sheets, on_no_coverage=)`; `check_failed` zostaje dla awarii skorowidza.
- `failed[].kind` w `kartograf-download/1`: pojedynczy `--sheet` bez rekordu to `no_coverage` (bylo `download`); nowa wartosc `year_out_of_range` (kod `YearRangeError`) takze dla LAZ i `--country auto` (dodatkowa wartosc wyliczenia).
- `--workers 0` i ujemne w `elevation download`/`imagery download` (CLI i `download_data`): kod 2, `details.option=workers` (bylo po cichu 1).
- `--bbox` w kazdej komendzie z obszarem: wspolrzedne spoza zakresu EPSG:4326 (metry z `--bbox-crs EPSG:4326`, bledne osie) i bbox o zerowej powierzchni (`min == max`) to kod 2 przed siecia z `details.option=bbox` i podpowiedzia o `--bbox-crs` i kolejnosci osi (wczesniej `OverflowError`, `ValueError` albo zapytanie z `inf`). Zmiana: `--bbox x,y,x,y` (punkt) nie jest przyjmowany; punkt podaje sie przez `--geometry`.
- `elevation availability`: `--country pl|cz` z `--bbox`/`--geometry` poza obwiednia kraju to kod 2 jak w `elevation download`; obszar bez ladu PL daje `Info:` `no_land`, `KOMPLET` = `brak ladu` i stopke bez podpowiedzi pobrania.
- LAZ: pusty wybor kafli po `--min-density` wskazuje flage, liczbe odrzuconych kafli i najwyzsza gestosc nominalna.
- Dokumentacja: przyklady USAGE 1.1 (LAZ `--min-density`, PL-2000 `--resolution 0.5m`, zakres lat 2022-2024) sprawdzone na zywo.
```

## Proponowana errata ADR (do docs/DECISIONS.md; NIE edytowalem)
- ADR-046 (interfejs dla agentow), errata: `UnitFailure.kind` w `kartograf-download/1` ma wartosci `no_coverage`, `year_out_of_range`, `download`, `country`; stany danych (`NoCoverageError`, `YearRangeError`) maja w raporcie te same nazwy co kody bledow `kartograf-error/1`, a `check_data` zglasza je jako wyjatki tych klas, gdy plan jest pusty.
- ADR-036 (tryby i plan) / ADR-030 (kampanie), errata: `DownloadManager.check_sheets` odtwarza stany danych pobrania - arkusz bez danych nie jest pozycja planu (`on_no_coverage`), konflikt lat to jeden `YearRangeError`, `check_failed` tylko dla awarii skorowidza.
- ADR-041/availability (jesli istnieje wpis o raporcie): obszar bez ladu PL ma `complete: true` (inwariant `complete <=> full_m2 == land_m2`), sygnal to `Info` `no_land`; `--country pl|cz` sprawdza obwiednie kraju jak pobranie.

## Czego NIE zrobilem / uwagi dla koordynatora
- Nie ruszalem `download/collections.py`, `project/operations.py` (wlasne sprawdzenia `workers >= 1` z tekstem `workers musi byc >= 1` bez `--`; mozna podpiac `require_workers`), `landcover/manager.py`, `hydrology/hsg.py`, `providers/{corine,soilgrids}.py` (FixLandcoverSoil); `--workers 0` w `landcover download` bez kolekcji (BDOT10k/CORINE) nadal nie jest walidowane - to ich plaster. `DownloadManager(workers=0)` nadal obcina do 1 (klasa biblioteczna pod `download_data`).
- `--workers` w `--help` nadal nie podaje `>= 1`; `BBOX_HELP` nie opisuje nowych regul (komunikaty bledow sa w USAGE 1.7/9.3).
- Konflikty przy scalaniu: `kartograf/notices.py` (jedna nowa stala `NO_LAND` po `CZ_SERVICE_ONLY`), `kartograf/download/data.py` (duzy plik, moje zmiany: FailureKind, `_Run.fail(cause=)`, `_failure_kind`, `_check_error`, `_plan_modes`, `_no_coverage_warning`, `_coverage_hints`), docs `USAGE.md` 1.1/1.7/4.3/9.3 i `ARCHITECTURE.md` 4.1/4.2.
- PRZED dla P2-8, `--workers`, zero-area pochodzi z raportow E2E (nie powtarzalem na commicie develop; obecny kod odrzuca je przed siecia); PRZED dla P2-3, P3-4, P3-16 zreprodukowane na zywo przed zmianami.
- Nowych skutkow ubocznych nie stwierdzilem w calym zestawie offline (7185 testow). Moje throwaway skrypty/helpery leza poza repo (`~/scratch/fix-pl-sheets/`).
