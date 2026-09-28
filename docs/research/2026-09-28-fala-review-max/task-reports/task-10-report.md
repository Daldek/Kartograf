# Raport Zad. 10 — arkusz bez danych GUGiK = nodata + ostrzezenie; awaria pobrania = blad (R5, zn. 2)

**Status:** DONE
**Commit:** `2807fe5` feat(download): arkusz bez danych GUGiK = nodata + ostrzezenie w wycinku PL (R5) (BASE `2ad46cf`)
**Bramka:** pelna suita `1837 passed, 8 deselected` (bylo 1831; +6 testow); ruff check + format czyste; mypy 32 bledy, lista identyczna z baseline (`diff` pusty).

## Co zrobiono

### Kod (`kartograf/download/cutout.py`)
- `PlCutoutResult.missing_sheets: tuple[str, ...] = ()` — posortowane godla bez danych GUGiK (R5).
- `write_pl_cutout_sidecar(cutout, *, parent_request=None, missing_sheets=())` — `extra` skladany ze slownika (kod z briefu); niepuste `missing_sheets` -> `extra.missing_sheets` (lista); `extra=extra or None`.
- `run_pl_cutout` — blok `if failed: raise` zastapiony kodem z briefu 1:1: `fatal` (porazki spoza `no_coverage`) -> `DownloadError` z lista TYLKO fatalnych; `not sheet_paths` -> `ValidationError("GUGiK nie ma danych dla zadnego z N arkuszy obszaru — wycinek nie powstal")`; brak danych -> `logger.info` (NIE warning — uwaga kontrolera), `build_pl_cutout`, sidecar z `missing_sheets`, wynik z `missing_sheets`. Linia `logger.info` zawinieta (E501).
- Docstring `run_pl_cutout` (P-14): zdanie z briefu + zachowana gwarancja "Oba bledy padaja, zanim cokolwiek zostanie zbudowane" (prawda: oba `raise` stoja przed `build_pl_cutout`).
- Docstring `write_pl_cutout_sidecar`: jedno zdanie o `missing_sheets`.

### CLI (`kartograf/cli/download_cmd.py::_download_pl_cutout`)
- `Warning:` z briefu (tekst doslowny; do 10 godel + " ...", stderr, `-q` nie tlumi).
- **Umiejscowienie (odstepstwo w ramach briefu):** "po udanym `run_pl_cutout`, przed `Downloaded to`" — ALE po pustym `print()` (tylko bez `-q`). Powod: pasek postepu konczy stan "skipped" bez nowej linii (`create_progress_callback`, `print(line, end="")`), wiec `Warning:` na stderr doklejalby sie w terminalu do linii paska. Ta sama przyczyna co ruling Zad. 8 o zachowaniu pustego `print()`.
- Docstring `_download_pl_cutout`: "KAZDY blad pobrania ... kod 1" bylo po R5 nieprecyzyjne (NoCoverageError to podklasa DownloadError) — dopisane zdanie: arkusz bez danych nie jest bledem, wycinek powstaje, `Warning:` do 10 godel, pelna lista w sidecarze.

### Testy (`tests/test_pl_cutout.py`)
- Harness `_run(..., failed=(), no_coverage=(), provider=None)` -> `DownloadResult(failed=..., no_coverage=...)`; zwrot `(rc, manager, find)` bez zmian, `self.dm` bez zmian. Parametr wstawiony po `failed` — zaden wolajacy nie podaje `provider` pozycyjnie (grep: 8 wywolan, wszystkie keyword albo bez provider).
- Z briefu (tresc 1:1, sformatowane przez ruff): `TestMissingSheets` (3 testy: `test_no_coverage_sheet_becomes_nodata_with_record`, `test_transport_failure_stays_fatal` — straznik P-14, `test_all_sheets_without_data_is_an_error`), `TestDownloadPlBboxCutout::test_missing_sheet_warns_and_returns_0`, `TestBorderTwoCutouts::test_border_pl_sheet_without_data_still_gives_both_cutouts` (dlugie asercje glob rozbite na zmienne `pl_dir`/`cz_dir` — E501; semantyka ta sama).
- **Dodatkowy test (poza briefem):** `test_missing_sheets_warning_shows_10_sidecar_lists_all` — 12 arkuszy bez danych podanych w ODWROCONEJ kolejnosci: stderr `12 arkuszy`, pierwsze 10 PO SORTOWANIU + " ...", brak 11. i 12.; sidecar = pelna posortowana lista. Broni trzech zachowan nowego kodu, ktorych testy briefu nie dotykaja (sortowanie, obciecie do 10, pelna lista w sidecarze) — mutacje M6/M7 nizej.
- `test_failed_sheet_returns_1_and_no_cutout` ZOSTAJE (awaria pobrania = kod 1); zmieniony tylko docstring — "Spec 6.1: wycinek wymaga kompletu pokrycia" jest po R5 falszywe -> "R5: awaria pobrania arkusza (nie brak danych GUGiK) = kod 1, bez wycinka."

### Dokumentacja
- `CLAUDE.md` (punkt `--target-crs` dla PL): tekst z briefu doslownie w miejsce "failed arkusz = kod 1".
- `docs/CHANGELOG.md` `### Changed`: tekst z briefu + jedno zdanie (API: `PlCutoutResult.missing_sheets`; obszar bez danych w zadnym arkuszu = `ValidationError`). Wpis wstawiony zaraz po wpisie o siatce arkuszy (oba o wycinku).
- `docs/CHANGELOG.md` `### Added` (**poza briefem, ten sam plik**): nawias "failed arkusz = kod 1" przy `--target-crs` dla PL byl po tej zmianie falszywy i sprzeczny z nowym wpisem Changed w tym samym wydaniu 0.7.0 -> "awaria pobrania arkusza = kod 1, arkusz bez danych GUGiK = nodata — patrz Changed".
- `docs/DECISIONS.md`: uzupelnienie ADR-027 — **tekst briefu poprawiony po weryfikacji na kodzie** (ponizej).

## Weryfikacja uzupelnienia ADR-027 zdanie po zdaniu

| # | Zdanie briefu | Weryfikacja | Decyzja |
|---|---|---|---|
| 1 | `NoCoverageError` — wszystkie warstwy skorowidza odpowiedzialy i zadna nie ma arkusza | `providers/pl/gugik.py:571-596`: `NoCoverageError` tylko gdy `transport_errors == 0` (HTTP-blad warstwy = `RequestException` = blad transportu) i zadna warstwa nie dala URL; wczesniej wraca URL z cache | prawda, bez zmian |
| 2 | nie wetuje wycinka: nodata, CLI `Warning:`, sidecar `extra.missing_sheets` | kod tej zmiany + testy; nodata = inicjalizacja `merge` tam, gdzie nie siega zaden pobrany arkusz | prawda; dopisane "(API biblioteki: `PlCutoutResult.missing_sheets`)" |
| 3 | Kazda inna porazka ... **nadal konczy zadanie kodem 1** | Nieprecyzyjne: pod `--country auto` porazka PL przy sukcesie CZ = kod 0 + `Warning:` (`cli/download_cmd.py:534-544`, `_dispatch_area`; zmierzone w RED testu pogranicza: "Warning: nie pobrano danych z PL ... pobrano CZ") | -> "nadal przerywa wycinek przed budowa, kodem 1" + osobne zdanie o `--country auto` (ADR-023 pkt 4-5) |
| 4 | chwilowy blad ... plik pomijany jako istniejacy | `run_pl_cutout`: `force=False` + istniejacy plik -> `skipped=True` (tez CLI i `download_pl_cutout`) | prawda, bez zmian |
| — | (brak w briefie) przypadek "zaden arkusz nie ma danych" | nowy `ValidationError` w `run_pl_cutout`; CLI -> kod 1 | dopisane zdanie |
| 5 | Zastepuje "kazdy failed arkusz = blad calosci" (spec 6.1 pkt 1) | spec `2026-08-28-uklad-data-i-target-crs-pl-design.md:181-182` (6.1 pkt 1) ✓; to samo zdanie stoi w Decyzji ADR-027 (`DECISIONS.md:1023-1024`) | dopisane "(Decyzja wyzej, spec 6.1 pkt 1)" |
| 6 | bbox przygraniczny **zawsze** obejmuje arkusze po stronie czeskiej, ktorych GUGiK nie ma | "zawsze" nieweryfikowalne i watpliwe: maly bbox na granicy moze trafic tylko w arkusze przecinajace granice (GUGiK je ma). Weryfikowalne: selekcja to czysta matematyka siatki (`find_sheets_for_bbox`, ADR-010; review zn. 2: "bbox na Baltyku zwraca 9 arkuszy") | -> "selekcja arkuszy to czysta matematyka siatki godel, wiec obszar zadania (z zapasem) siega arkuszy spoza pokrycia GUGiK — na morzu, w dziurach pokrycia 1 m, po czeskiej stronie bboxa przygranicznego" |
| 7 | dotad `--country auto --target-crs` na granicy **nie dawal wycinka PL w ogole** | Prawda tylko warunkowo (gdy choc jeden arkusz byl bez danych): stary kod `if failed: raise DownloadError` | -> "jeden taki arkusz wetowal dotad caly wycinek, wiec ... na granicy dawal wtedy sam wycinek CZ" |

Wersja zacommitowana: `docs/DECISIONS.md:1055-1070`.

## RED (przed implementacja)

```
.venv/bin/python -m pytest tests/test_pl_cutout.py -q -m "not live" -k "TestMissingSheets or missing_sheet or border_pl_sheet_without_data or failed_sheet_returns_1 or error_lists_all_failed"
E   assert 1 == 0
Error: 1 of 1 sheets failed: N-2 (wycinek wymaga kompletu arkuszy)
E   assert 1 == 0
Error: 12 of 12 sheets failed: N-11, N-10, ..., N-00 (wycinek wymaga kompletu arkuszy)
E   AssertionError: assert 0 == 1          # brak pliku w nmt/pl_1992_5m_evrf2007/bbox
Error: 1 of 1 sheets failed: N-34-130-D-d-2-1 (wycinek wymaga kompletu arkuszy)
Warning: nie pobrano danych z PL dla tego obszaru (brak pokrycia albo awaria zrodla — patrz Error wyzej) — pobrano CZ (...)
E   kartograf.exceptions.DownloadError: 1 of 2 sheets failed: N-34-130-D-d-2-4 (wycinek wymaga kompletu arkuszy)
E   kartograf.exceptions.DownloadError: 2 of 2 sheets failed: N-34-130-D-d-2-3, N-34-130-D-d-2-4 (wycinek wymaga kompletu arkuszy)
FAILED ...::test_missing_sheet_warns_and_returns_0
FAILED ...::test_missing_sheets_warning_shows_10_sidecar_lists_all
FAILED ...::test_border_pl_sheet_without_data_still_gives_both_cutouts
FAILED ...::test_no_coverage_sheet_becomes_nodata_with_record
FAILED ...::test_all_sheets_without_data_is_an_error
================== 5 failed, 3 passed, 47 deselected in 0.53s ==================
```
3 passed = straznik `test_transport_failure_stays_fatal` (zielony PRZED zmiana — zgodnie z P-14) + dwa istniejace testy porazki.

## GREEN

```
.venv/bin/python -m pytest tests/test_pl_cutout.py -q -m "not live" -k "<jak wyzej>"
======================= 8 passed, 47 deselected in 0.38s =======================
.venv/bin/python -m pytest tests/test_pl_cutout.py -q -m "not live"
============================== 55 passed in 1.82s ==============================   # bylo 49
.venv/bin/python -m pytest tests/ -q -m "not live"
===================== 1837 passed, 8 deselected in 25.36s ======================   # bylo 1831
```

Realny komunikat (skrypt demo w scratchpadzie, 12 arkuszy bez danych, bez `-q`):
```
Warning: GUGiK nie ma danych dla 12 arkuszy wycinka (N-34-130-D-d-00, ..., N-34-130-D-d-09 ...) — w tych miejscach wycinek ma nodata (lista w sidecarze: extra.missing_sheets)
```

## Bramka jakosci
- `.venv/bin/python -m ruff check kartograf/ tests/` -> `All checks passed!`
- `.venv/bin/python -m ruff format --check kartograf/ tests/` -> `87 files already formatted`
- `.venv/bin/python -m mypy kartograf/` -> `Found 32 errors in 9 files`; `mypy ... | grep error: | sed -E 's/:[0-9]+: /: /' | sort` vs `mypy-baseline.txt` -> `diff` pusty (rc=0) — zero nowych bledow.

## Dowody mutacyjne (PO commicie `2807fe5`; przywracanie `git checkout -- <plik>`)

Skrypt: `scratchpad/mutate.py` (kazda mutacja sprawdza, ze cel wystepuje w pliku DOKLADNIE raz; po kazdej: przywrocenie, ponowny przebieg = PASS, `git status --porcelain` pusty). Komenda testow per mutacja: `.venv/bin/python -m pytest -q -m "not live" <wymienione testy>`. Wynik: **9/9 zabitych, 9/9 przywroconych do PASS, drzewo czyste, HEAD bez zmian.**

| # | Mutacja | Testy | Fragment FAIL | Po przywroceniu |
|---|---|---|---|---|
| M1 (brief 1) | `fatal = failed` | nodata_with_record, warns_and_returns_0, shows_10, border | `DownloadError: 1 z 2 arkuszy nie pobrano (blad pobrania, nie brak danych): N-34-130-D-d-2-4`; `assert 1 == 0` x2; border: `assert 0 == 1` (brak pliku PL) — 4 failed | 4 passed |
| M2 (brief 2) | `fatal = []` | transport_failure_stays_fatal, failed_sheet_returns_1, error_lists_all_failed | `Failed: DID NOT RAISE <class 'kartograf.exceptions.DownloadError'>`; `assert 0 == 1`; `assert ('N-1' in 'Error: GUGiK nie ma danych dla zadnego z 0 arkuszy obszaru ...')` — 3 failed | 3 passed |
| M3 (brief 3) | `extra["missing_sheets"] = ...` -> `pass` | nodata_with_record, shows_10 | `KeyError: 'missing_sheets'` x2 — 2 failed | 2 passed |
| M4 (brief 4) | blok `Warning:` w CLI wylaczony (`if False:`) | warns_and_returns_0, shows_10, border | `assert ('Warning:' in '')` x2; `assert '12 arkuszy' in ''` — 3 failed | 3 passed |
| M5 (brief 5) | `if not sheet_paths:` -> `if False:` | all_sheets_without_data_is_an_error | **inny blad:** `ValidationError: mosaic_and_crop: brak rastrow wejsciowych` -> `Regex pattern did not match. Expected regex: 'nie ma danych'` — 1 failed | 1 passed |
| M6 | `missing` bez `sorted` | shows_10 | `assert ('N-00, N-01' in 'Warning: ... (N-11, N-10, N-09, ..., N-02 ...) ...')` | 1 passed |
| M7 | Warning bez `[:10]` | shows_10 | `... (N-00, ..., N-09, N-10, N-11 ...)` -> asercja `N-09 ...`/`N-10` pada | 1 passed |
| M8 | Warning pod `and not args.quiet` | warns_and_returns_0 (`quiet=True`) | `assert ('Warning:' in '')` | 1 passed |
| M9 | `PlCutoutResult(...)` bez `missing_sheets=missing` | nodata_with_record, warns_and_returns_0 | `assert () == ('N-34-130-D-d-2-4',)`; `assert ('Warning:' in '')` | 2 passed |

Uwagi do mutacji:
- **M5:** bez straznika `mosaic_and_crop([])` i tak rzuca `ValidationError` — test zabija mutanta WYLACZNIE przez `match="nie ma danych"` (ten `match` jest nosny; bez niego mutant by przezyl). Przy okazji bez straznika `build_pl_cutout` robi `mkdir` katalogu `bbox/` przed awaria (klasa zn. 10) — straznik tego unika, ale zaden test tego nie asertuje.
- **Test pogranicza:** same asercje stderr (`"Warning:"` i godlo) sa slabe — RED pokazuje, ze STARY kod tez je spelnial ("Error: 1 of 1 sheets failed: N-34-130-D-d-2-1" + "Warning: nie pobrano danych z PL"). Test bronia asercje liczby plikow PL (M1). Asercja stderr gryzie dopiero przy M4 (oba kraje OK -> brak ostrzezenia z `_dispatch_area`).

## Pliki
- `kartograf/download/cutout.py`
- `kartograf/cli/download_cmd.py`
- `tests/test_pl_cutout.py`
- `CLAUDE.md`
- `docs/CHANGELOG.md`
- `docs/DECISIONS.md`

## Samoocena i watpliwosci
1. **Odstepstwa od briefu (wszystkie opisane wyzej):** tekst uzupelnienia ADR-027 poprawiony w 3 miejscach + 2 dopiski (tabela weryfikacji); `Warning:` po pustym `print()`; docstring CLI; dodatkowy test + M6-M9; nawias w `### Added` CHANGELOG; zdanie dopisane do wpisu `### Changed`.
2. **Znane falszywe zdania zostawione dla Zad. 17** (plan przydziela je tam jawnie; poza lista plikow tego zadania): `docs/ARCHITECTURE.md:386` ("wycinek wymaga kompletu pokrycia" — przepis sekcji 4.3 z R5, Zad. 17 Step 1) i `docs/SCOPE.md:339` ("failed arkusz = kod 1" — grep `failed arkusz`, Zad. 17 Step 3).
3. **Duplikacja na stderr w realnym CLI (przed ta zmiana, poza zakresem):** `DownloadManager` (Zad. 6) loguje `logger.warning("No data for <godlo>: ...")` PER arkusz, a CLI nie konfiguruje logowania — wiec handler `lastResort` Pythona wypisze te linie na stderr obok podsumowania `Warning:` z CLI. Podsumowanie biblioteki jest INFO (zgodnie z uwaga kontrolera), wiec podsumowanie nie dubluje sie; linie per arkusz tak. Kandydat na minor (np. `info` w managerze albo swiadoma akceptacja).
4. **Przypadek zdegenerowany (tylko biblioteka):** `run_pl_cutout` z `PlCutoutSheets(godla=())` konczy sie "GUGiK nie ma danych dla zadnego z 0 arkuszy obszaru" (tekst widoczny w wyjsciu M2) — mylace, ale nieosiagalne z `select_pl_cutout_sheets`/CLI (pusta lista = wczesniejszy `ValidationError`). Komunikat z briefu zostawiony doslownie.
5. **Wynik `skipped=True` ma `missing_sheets=()`** (bez sieci — lista zyje w sidecarze istniejacego pliku). Zgodne z kontraktem skrotu, warte zdania w ARCHITECTURE 4.3 (Zad. 17).
6. **Kolizja nazw:** `DownloadManager.get_missing_sheets()` (= arkusze jeszcze nie na dysku) vs `PlCutoutResult.missing_sheets` (= arkusze bez danych GUGiK). Nazwa narzucona przez R5 (`extra.missing_sheets`) — tylko sygnal.
7. **Checklista live:** sciezka R5 zaklada, ze skorowidz dla arkusza spoza pokrycia NIE zwraca zadnego URL. Jesli punkt srodka takiego arkusza trafi w poligon innego arkusza (np. PL-2000, fakt 7), `_get_opendata_url` pojdzie fallbackiem "URL innego arkusza" (`gugik.py:554-563`), a nie `NoCoverageError` — dla PL-2000 wycinek konczy sie wtedy glosnym bledem `_reject_pl2000_sheets`. Warto sprawdzic na zywo arkusz lezacy w calosci po czeskiej stronie granicy.
8. Kosmetyka (tekst briefu doslowny): "dla 1 arkuszy" przy liczbie 1.
