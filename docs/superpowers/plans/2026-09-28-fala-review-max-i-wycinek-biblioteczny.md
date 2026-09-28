# Fala naprawcza po review max (uklad data/ + --target-crs PL) + wycinek PL w bibliotece — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zamknac 14 z 15 znalezisk review max z 2026-08-30 (w tym 3 krytyczne w torze wycinka PL) oraz 5 defektow wykrytych przy planowaniu, i udostepnic wycinek PL `--target-crs` jako API biblioteki — przed checklista live i wydaniem 0.7.0.

**Architecture:** Potok wycinka PL przenosi sie z `cli/download_cmd.py` do nowego modulu `kartograf/download/cutout.py` (funkcje + dataclassy, zero `print`/argparse); CLI zostaje cienka nakladka (komunikaty, kody wyjscia). Warstwa transportu (`transport/mosaic.py`) dostaje leniwe otwieranie zrodel, crop na siatce pikseli zrodel i normalizacje zrodel przez VRT (wymuszony CRS/dtype). Porazki arkuszy klasyfikowane sa wg PRZYCZYNY: brak danych u zrodla (`NoCoverageError`) = nodata + ostrzezenie, kazda inna porazka = blad. Tor CZ (`providers/cuzk/*`) pozostaje nietkniety.

**Tech Stack:** Python 3.12+, rasterio 1.5.0 / GDAL 3.12.1 (`merge` ze sciezkami, VRT w `/vsimem/`), pyproj 3.7.2 (`PinnedTransform`), numpy, pytest (offline), ruff, mypy.

**Spec:** raport `docs/research/2026-08-28-uklad-data-target-crs-pl/2026-08-30-code-review-max.md` (znaleziska 1-15, file:line, pomiary) + ADR-027 (`docs/DECISIONS.md`) + `docs/ARCHITECTURE.md` sekcja 4.3 + rozstrzygniecia i fakty ponizej (nadrzedne wobec raportu tam, gdzie sie roznia). Czytaj razem z planem.

---

## Kontekst (dlaczego)

Sesja 2026-08-28 wdrozyla nowy uklad `data/` (ADR-026) i `--target-crs` dla PL (ADR-027). Review max z 2026-08-30 znalazl 15 potwierdzonych defektow; trzy blokuja checkliste live i wydanie: (1) mozaika wycinka PL przesuwa tresc o ulamek piksela, (2) arkusz bez danych GUGiK wetuje caly wycinek, (3) mozaika trzyma otwarte deskryptory WSZYSTKICH arkuszy i pada powyzej ~1024 arkuszy (Linux) / ~256 (macOS) — po godzinach pobierania. CLAUDE.md i ADR-027 opisuja semantyke `--force` odwrotnie niz kod. Planowanie (pomiary na realnych arkuszach GUGiK + adwersarialny review projektu) dolozylo piec defektow spoza raportu: przesuniecie o 0,5 px takze dla bboxow calkowitych, obcinanie wysokosci do Int32, `CRS mismatch` przy arkuszach z `.prj` od Hydrografu, gubienie arkuszy przy gornej krawedzi bboxa na poludniku 19°E oraz ciche pomijanie arkuszy 1 m wydanych przez GUGiK w ukladzie PL-2000. Uzytkownik zdecydowal, ze Hydrograf ma dostac wycinek jako wywolanie biblioteki juz w 0.7.0.

## Rozstrzygniecia uzytkownika (2026-09-28) — WIAZACE

| # | Decyzja |
|---|---|
| R1 (zn. 1) | Wycinek `--target-crs EPSG:2180` lezy na **siatce arkuszy**: obszar zadania rozszerzony NA ZEWNATRZ do pelnych pikseli arkuszy (< 1 px na strone), wartosci 1:1 bez przeprobkowania, `transform: null` w sidecarze pozostaje prawda, nazwa pliku niesie wspolrzedne ZADANIA. |
| R2 (zn. 15) | **Poza zakresem, bez zmian w kodzie.** Rzadka geometria wieloobiektowa nie wystepuje w praktyce (uzytkownik pobiera godla albo bbox); dla jednego obiektu i dla bboxa "cala obwiednia" i "pierscien" daja ten sam zbior arkuszy. R-01 zostaje; koszt juz opisany w ARCHITECTURE 4.3. |
| R3 (zn. 12) | **W tej fali**: wycinek PL jako API biblioteki (`kartograf.download.cutout`, eksport w `kartograf/__init__.py`), CLI jako nakladka. |
| R4 | Wykonanie: **team-driven** (patrz "Tryb wykonania"). |
| R5 (zn. 2) | **Arkusz, dla ktorego GUGiK nie ma danych** (morze, strona czeska bboxa przygranicznego, dziury pokrycia 1 m) = **nodata + `Warning:` + lista w sidecarze (`extra.missing_sheets`)**, wycinek powstaje (kod 0). Kazda INNA porazka pobrania (siec, serwer, niepelna odpowiedz skorowidza) = kod 1 i brak pliku — chwilowy blad nigdy nie zostawia trwalej dziury. Zastepuje "kazdy failed arkusz = blad calosci" ze specu 6.1 pkt 1 / ADR-027. |
| R6 | **Scalanie PL+CZ w jedna ciagla powierzchnie przygraniczna** (wspolna siatka, EVRF2007 po obu stronach, regula zakladki) — **backlog / etap 2**, po zywym sprawdzeniu, jak GUGiK i CUZK przycinaja dane na granicy. W tej fali wycinek PL na granicy w ogole zaczyna powstawac. |

Decyzja kontrolera (bez pytania, w duchu raportu): zn. 9 — bez twardego limitu rozmiaru; kompresja pliku posredniego, fail-fast przy braku miejsca na dysku, `Info:` dla siatek > 1 GiB.

## Fakty zmierzone w planowaniu (2026-09-28) — WIAZACE, nie zgadywac na nowo

1. **Siatka pikseli realnych arkuszy GUGiK NIE jest calkowita.** Wszystkie 1977 arkuszy 5 m z cache Hydrografu (`/home/claude-agent/workspace/Hydrograf/cache/nmt/`, tylko do odczytu) maja narozniki pikseli na `5k + 2,5 m` (srodki na wielokrotnosciach 5), w obu wariantach naglowka (`xllcorner` i `xllcenter`). Sasiednie arkusze nachodza na siebie (np. `N-34-139-A-c-4-3` / `-4-4`: zakladka 70 m = 14 px, w zakladce zaden piksel nie jest wazny w obu naraz) i sa przesuniete w pionie. Przeslanka raportu "arkusze kotwiczone na calkowitych wielokrotnosciach piksela" jest FALSZYWA — siatke bierzemy z transformacji zrodel. Arkuszy 1 m offline brak (siatka 1 m -> checklista live).
2. **Blad nr 1 jest powazniejszy, niz zmierzyl raport**: przy siatce polpikselowej bbox o CALKOWITYCH wspolrzednych daje przesuniecie 0,5 px (2,5 m przy 5 m) z mieszaniem sasiednich kolumn przy remisie (48,7 % pikseli). Po przyciagnieciu cropu do siatki: 0 / 88 641 pikseli rozbieznych.
3. `rasterio.merge.merge(lista_sciezek)` daje wynik bit-w-bit identyczny z `merge(lista_otwartych_datasetow)`; rasterio 1.5.0 przy sciezkach otwiera zrodla pojedynczo, w petli PER KAWALEK wyniku (`merge.py:459-460`). Przy wielu kawalkach (male `mem_limit`) wynik z przyciagnietymi granicami pozostaje dokladny (0 rozbieznosci na 321 072 pikselach, obie kolejnosci wejsc — weryfikacja adwersarialna).
4. Otwarcie arkusza ASC: ~0,49 ms, z `rasterio.Env(AAIGRID_DATATYPE="Float32")` ~0,28 ms (1,7x, oba przebiegi przy cieplym cache; wczesniejszy pomiar "7x" mieszal zimny cache — niewazny).
5. **Obcinanie do Int32 (poza raportem):** z naglowkiem jak u GUGiK (`nodata_value -9999`, bez kropki) arkusz ASC z samymi liczbami calkowitymi GDAL czyta jako Int32; `merge` bierze dtype z PIERWSZEGO zrodla, wiec mozaika staje sie Int32 i wysokosci innych arkuszy sa obcinane (zmierzone: 100,25 -> 100). Zadnego takiego arkusza w cache nie ma, ale kolejnosc zrodel jest dzis nieustalona (`as_completed`).
6. **`CRS mismatch` przy mieszanym cache (poza raportem):** Hydrograf dopisuje `.prj` (EPSG:2180) obok arkuszy pobranych przez Kartograf (`Hydrograf/backend/utils/raster_utils.py:102-106,155`). Arkusz z `.prj` otwiera sie z CRS EPSG:2180, swiezy bez — z CRS `None`; `merge` rzuca wtedy `RasterioError: CRS mismatch` (zmierzone). Opakowanie KAZDEGO zrodla w VRT (`/vsimem/`) z jawnym `SRS`=EPSG:2180 i pasmem `Float32` scala je poprawnie — wynik bit-w-bit identyczny z mozaika arkuszy z `.prj` (zmierzone); to samo opakowanie usuwa fakt 5. Pulapka (zmierzona): `merge` bierze profil wyjscia z pierwszego zrodla, czyli VRT (`blockxsize=128`, `tiled=True`) — bez `driver="GTiff"` w `dst_kwds` zapis pada (`Writing through VRTSourcedRasterBand is not supported`); z `GTiff` (+ kompresja, bloki 512) dziala.
7. **Arkusze 1 m w ukladzie PL-2000 (poza raportem):** Hydrograf ma kod na pliki ASC NMT 1 m z GUGiK "w PUWG 1992 albo PUWG 2000 (strefy 5-8) zaleznie od regionu" (`raster_utils.py:109-118`, CHANGELOG Hydrografu 0.4.0: "Automatyczna normalizacja CRS plikow NMT"). Mechanizm po stronie Kartografa: `GugikProvider._get_opendata_url` przy braku URL z godlem bierze "pierwszy znaleziony" (`providers/pl/gugik.py:550-553`) — dla nowszych kampanii to arkusz PL-2000 zapisany pod godlem PL-1992. Wycinek wymusza EPSG:2180, wiec taki arkusz (x > 1 000 000) laduje poza obszarem i `merge` pomija go PO CICHU (dziura nodata). W cache Hydrografu (5 m) zadnego takiego pliku nie ma — czestosc dla 1 m -> checklista live.
8. **Selekcja arkuszy gubi pas przy gornej krawedzi bboxa na poludniku 19°E (poza raportem):** `core/sheet_parser.py::_transform_bbox_to_wgs84` bierze obwiednie z 4 naroznikow; w PUWG 1992 najwieksza szerokosc gornej krawedzi wypada na poludniku osiowym (x = 500 000), nie w naroznikach. Zmierzone: dla `BBox(490000, 470000, 510000, 480161)` pomijane jest 6 arkuszy, ktore faktycznie przecinaja bbox (`N-34-134-B-d-3-2`, `N-34-134-B-d-4-1`, `N-34-134-B-d-4-2`, `N-34-135-A-c-3-1`, `N-34-135-A-c-3-2`, `N-34-135-A-c-4-1`); dla bboxa szerokiego na 10 km — 0. Pas rosnie z kwadratem szerokosci (~63 m przy 50 km).
9. Realne pliki ASC GUGiK 5 m: **5,74-7,95 bajta na wartosc** (mediana 6,88; 1454 arkusze) — do szacunku miejsca na dysku.
10. `tiled=True` w `dst_kwds` mozaiki bez `blockxsize/blockysize` konczy sie `RasterBlockError` (profil AAIGrid ma `blockxsize=ncols, blockysize=1`); z `blockxsize=blockysize=512` dziala; `compress=deflate, predictor=3` trafia do opcji tworzenia GTiff; `bigtiff=IF_SAFER` jest wlasciwe (IF_NEEDED nie przelacza skompresowanego wyniku na BigTIFF).
11. mypy na `develop` (`8cf1e5a`): **32 bledy w 9 plikach** — baseline; brama: zero nowych (diff LISTY, nie liczby).

## Global Constraints

- Galaz: **develop** (praca bezposrednio, nic nie pushujemy). Conventional Commits, commit po kazdym zadaniu. Stopka commita: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Komendy zawsze przez venv: `.venv/bin/python -m pytest tests/ -q` (testy OFFLINE — `tests/conftest.py` przewraca kazdy test otwierajacy gniazdo poza loopbackiem; zadnych testow z siecia), `.venv/bin/python -m ruff check kartograf/ tests/`, `.venv/bin/python -m ruff format --check kartograf/ tests/`, `.venv/bin/python -m mypy kartograf/`.
- Punkt startowy: **1787 testow** (2026-08-28) — zmierz w Zad. 0 i zapisz w ledgerze; mypy 32 (fakt 11). Po kazdym zadaniu: pelna suita zielona, ruff check + format czyste, mypy bez NOWYCH bledow (porownuj liste `plik: komunikat` z baseline — przesuniecia linii udaja nowe bledy).
- **Dowod mutacyjny obowiazkowy** dla kazdego nowego/zmienionego testu zachowania: zepsuj kod produkcyjny w miejscu, ktorego test broni -> pokaz FAIL -> przywroc -> pokaz PASS -> `git status` czysty poza zmianami zadania. Mutacje wymienione w zadaniach sa MINIMUM. Wynik (mutacja + fragment FAIL) idzie do raportu zadania; re-reviewer powtarza co najmniej jedna mutacje samodzielnie.
- **Dokumentacja klamie czesciej niz kod**: kazde twierdzenie o zachowaniu w docs/komentarzach/docstringach weryfikuj na zywym kodzie; gotowe teksty z tego planu tez nie sa nieomylne. Liczby wpisuj tylko zmierzone.
- Dokumentacja i komentarze: polski bez znakow diakrytycznych (ASCII). Docstringi w istniejacych plikach: jezyk pliku (`download/storage.py`, `download/manager.py` — angielski; `cli/*`, `transform/*`, `transport/*`, `core/sheet_parser.py`, nowy `download/cutout.py` — polski ASCII).
- **Tor CZ zamrozony**: zadnych zmian w `kartograf/providers/cuzk/*` (zweryfikowany live, ADR-024). Zmiany we wspolnym `transport/mosaic.py` musza zachowac zachowanie wywolania CZ (`providers/cuzk/client.py:182`: bez `dst_kwds`, bez nowych parametrow) — po Zad. 2-4 uruchom `tests/test_cuzk_client.py tests/test_cuzk_dmr.py`.
- `transform/raster.py::warp_to_grid` pozostaje osobna od CZ `_warp_to_grid` (testy ADR-024 patchuja `kartograf.providers.cuzk.dmr.reproject`) i nie zmienia sie w tej fali.
- Bez shimow zgodnosciowych (feedback uzytkownika): funkcje prywatne CLI przenoszone do biblioteki znikaja z CLI, testy przepinamy. Publiczne API tylko przybywa (addytywnie), wpisy w CHANGELOG.
- Semantyka, ktorej NIE wolno zmienic: nieudana budowa wycinka PL nie kasuje poprzedniego pliku wyniku (zapis atomowy `os.replace`); `--country auto` z sukcesem jednego kraju konczy sie kodem 0 + `Warning:` (ADR-023 pkt 4-5); kazdy blad budowy wycinka w CLI = kod 1, nigdy traceback; tryby bez `--target-crs` (godlo, lista arkuszy bbox/geometry) zachowuja dotychczasowe kody wyjscia (R5 dotyczy wylacznie wycinka).
- Wycinki zbudowane PRZED ta fala maja te same nazwy plikow i bylyby pomijane jako istniejace — CHANGELOG ma powiedziec wprost: przebuduj z `--force` (bledna rejestracja z zn. 1).

## Tryb wykonania (R4)

superpowers:subagent-driven-development w wariancie "team-driven" z pamieci projektu:
- Kontroler (ta sesja) tylko koordynuje: dispatch, ledger, rulingi — zero wlasnych poprawek kodu.
- **Pre-flight planu** przez agenta **opus** PRZED Zad. 1 (kotwice file:line, wykonalnosc kodu planu, sprzecznosci miedzy zadaniami); defekty planu zbiorczo do uzytkownika przed startem.
- Tiering (podany przy kazdym zadaniu): **sonnet** — implementacja z gotowego kodu planu + review prostych zadan; **opus** — zadania z osadem i review najtrudniejszych diffow; **fable** — finalny review calej galezi (gdy "out of usage credits" -> opus).
- Po kazdej rundzie naprawczej scoped re-review; re-reviewer powtarza mutacje.
- Ledger i artefakty: `docs/research/2026-09-28-fala-review-max/` (skopiowac z workspace SDD przed jego usunieciem — w etapie 1 ledger przepadl).
- Subagenci w worktree: po skopiowaniu wynikow ZAWSZE `git diff` pliku wobec develop (subagent potrafi skasowac kod poza zakresem).

## Review Focus (wejscia, ktore najpewniej ugryza uzytkownika; testy w zadaniach-wlascicielach)

1. **Realna siatka GUGiK** (narozniki pikseli pol piksela od liczb calkowitych, arkusze nachodzace) i **bbox o calkowitych wspolrzednych** — dotychczasowe fixtury maja calkowite, stykajace sie arkusze i nie widza bledu nr 1. Wlasciciele: Zad. 3, 9.
2. **Bbox przygraniczny `--country auto --target-crs`**: arkusze po stronie czeskiej bez danych GUGiK (R5) obok chwilowej awarii pobrania innego arkusza (musi pozostac kodem 1). Wlasciciele: Zad. 6, 10.
3. **Cache wspoldzielony z Hydrografem** (czesc arkuszy z `.prj`) i **arkusz ASC z samymi liczbami calkowitymi** jako pierwszy. Wlasciciele: Zad. 4, 9.
4. **Liczba arkuszy powyzej limitu deskryptorow** (Linux 1024, macOS 256), takze przez opakowanie VRT. Wlasciciele: Zad. 2, 4.
5. **Arkusz 1 m zapisany w ukladzie PL-2000** pod godlem PL-1992 — musi dac glosny blad, nie dziure. Wlasciciel: Zad. 9. Oraz bbox szeroki na poludniku 19°E (Zad. 5) i plik geometrii w EPSG:5514/3045 z `--country pl/auto` (Zad. 12).

## Mapa plikow

| Plik | Zmiana | Zadania |
|---|---|---|
| `CLAUDE.md`, `docs/DECISIONS.md` | prawda o `--force`, zdanie R-01 w ADR-027, uzupelnienie ADR-027 | 1, 17 |
| `kartograf/transport/mosaic.py` | leniwe zrodla, `snap_to_source_grid=`, `assign_crs=`/`dtype=` (VRT) | 2, 3, 4 |
| `kartograf/core/sheet_parser.py` | obwiednia WGS84 z poludnikiem osiowym | 5 |
| `kartograf/exceptions.py`, `kartograf/providers/pl/gugik.py` | `NoCoverageError`; niepewne pokrycie; ostrzezenie przy URL innego arkusza | 6 |
| `kartograf/download/manager.py` | `DownloadResult.no_coverage`; `expand_sheets()`, `download_sheets()` | 6, 7 |
| `kartograf/download/cutout.py` (NOWY) | `PlCutout`, `PlCutoutSheets`, `PlCutoutResult`, `prepare_pl_cutout`, `select_pl_cutout_sheets`, `build_pl_cutout`, `write_pl_cutout_sidecar`, `run_pl_cutout`, `download_pl_cutout` | 8-11, 13 |
| `kartograf/cli/download_cmd.py` | cienka nakladka `_download_pl_cutout`; obwiednia geometrii w ukladzie pliku; sprzatanie katalogow CZ; LAZ przez `tile.uklad` | 8, 10-13, 15 |
| `kartograf/cli/_parser.py`, `kartograf/__init__.py` | `choices` z biblioteki; eksport API wycinka i `NoCoverageError` | 6, 8 |
| `kartograf/download/storage.py` | `prune_empty_dirs()`, `get_raw_path(uklad=)`, szablony z rejestru | 13, 15, 16 |
| `kartograf/sources/descriptor.py` | pusty wymiar -> `ValidationError` | 14 |
| `kartograf/providers/pl/gugik_laz.py` | `LazTile.uklad` | 15 |
| `tests/test_transport_mosaic.py`, `tests/test_sheet_parser.py`, `tests/test_gugik_provider.py`, `tests/test_download_manager.py`, `tests/test_pl_cutout.py`, `tests/test_cli.py`, `tests/test_storage.py`, `tests/test_sources_registry.py`, `tests/test_gugik_laz.py` | testy + dowody mutacyjne | 2-16 |
| `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `README.md`, `docs/PROGRESS.md` | synchronizacja (CHANGELOG w kazdym zadaniu, reszta w 17) | 2-17 |

**Poza zakresem** (zapisac w PROGRESS/backlogu w Zad. 17): zn. 15 (R2); scalanie PL+CZ (R6); obsluga arkuszy PL-2000 w wycinku (w tej fali tylko glosny blad — fakt 7); podwojna obwiednia, gdy uklad zadania = `--target-crs` (np. bbox i cel EPSG:5514: siatka 11,51 x 11,51 km zamiast 10 x 10 km — do rozwiazania razem z R6, bo tez dotyczy wspolnej siatki); przejscie trybow CLI bez `--target-crs` na `download_sheets` (dzis `_download_godlo_list` rzuca pierwsza porazka); tolerancja braku pokrycia w trybach bez wycinka; `warp_to_grid` zaokragla wymiary siatki (`round`), wiec moze uciac < 0,5 px na krawedzi wschodniej/poludniowej obwiedni. Znaleziska 13 i 14 zamykaja sie w Zad. 8 (duplikacja i mylace nazwy znikaja z przeniesieniem potoku do biblioteki).

## Przeglad zadan

| Zad. | Co | Zamyka | Model (impl./review) |
|---|---|---|---|
| 0 | Pomiar bazowy, commit raportu review i planu, pamiec | — | kontroler |
| 1 | CLAUDE.md + ADR-027: prawda o `--force` i selekcji R-01 | zn. 5, 6 | sonnet / sonnet |
| 2 | Mozaika otwiera zrodla leniwie (limit deskryptorow) | zn. 3 | sonnet / sonnet |
| 3 | Mozaika: crop na siatce zrodel (siatka wiekszosci + ostrzezenie) | zn. 1 (A) | sonnet / opus |
| 4 | Mozaika: normalizacja zrodel przez VRT (`assign_crs`, `dtype`) | fakty 5, 6 | opus / opus |
| 5 | Selekcja arkuszy z poludnikiem osiowym (gorna krawedz przy 19°E) | fakt 8 | sonnet / sonnet |
| 6 | `NoCoverageError` + `DownloadResult.no_coverage` + ostrzezenie przy URL innego arkusza | fundament R5, fakt 7 | sonnet / sonnet |
| 7 | `DownloadManager.expand_sheets()` / `download_sheets()` | fundament 8-11 | sonnet / sonnet |
| 8 | Wycinek PL jako API biblioteki (`download/cutout.py`), CLI jako nakladka | zn. 12, 13, 14 (R3) | opus / opus |
| 9 | Wycinek na siatce arkuszy + VRT + blad dla arkuszy PL-2000 + selekcja +1 px | zn. 1 (B), R1, fakty 5-7 | opus / opus |
| 10 | Brak danych GUGiK = nodata + `Warning:`; awaria = kod 1 | zn. 2 (R5) | opus / opus |
| 11 | Kompresja pliku posredniego, kontrola dysku, `Info:` | zn. 9 | sonnet / sonnet |
| 12 | Obwiednia geometrii w ukladzie czeskim przez operacje przypieta | zn. 4 | sonnet / sonnet |
| 13 | Porazka nie zostawia pustych `bbox/` | zn. 10 | sonnet / sonnet |
| 14 | `resolve_subdir` odrzuca pusty wymiar | zn. 7 | sonnet / sonnet |
| 15 | Uklad kafla LAZ z `LazTile.uklad` (CLI = biblioteka) | zn. 8 | sonnet / sonnet |
| 16 | Szablony segmentow `FileStorage` z rejestru | zn. 11 | sonnet / sonnet |
| 17 | Dokumentacja, E2E offline na realnych arkuszach 5 m, brama jakosci | — | opus / opus |
| — | Finalny review galezi, fala naprawcza, PROGRESS, artefakty, pamiec | — | fable (opus) |

---
### Zad. 0: Start — pomiar bazowy, commit raportu i planu (kontroler)

**Files:**
- Add: `docs/research/2026-08-28-uklad-data-target-crs-pl/2026-08-30-code-review-max.md` (dzis nieskomitowany)
- Modify: `docs/research/2026-08-28-uklad-data-target-crs-pl/README.md` (wiersz tabeli)
- Create: `docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md` (kopia tego planu)

- [ ] **Step 0: Pamiec** (kontroler): zapisz feedback z sesji planowania — pytania projektowe zadawaj po jednym watku, najpierw prostym jezykiem i na przykladzie z realnego uzycia (bbox, godlo, pogranicze); scenariusze bez praktycznego znaczenia uzytkownik odrzuca (zn. 15). Zaktualizuj `project_uklad_data_target_crs_pl.md`: plan fali 2026-09-28, R1-R6.

- [ ] **Step 1: Pomiar bazowy** (wynik do ledgera; `$SDD_WS` = katalog roboczy SDD kontrolera)

```bash
git status --short && git log --oneline -1
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -2
.venv/bin/python -m mypy kartograf/ 2>&1 | grep -E "error:" | sed -E 's/:[0-9]+: /: /' | sort > "$SDD_WS/mypy-baseline.txt"; wc -l < "$SDD_WS/mypy-baseline.txt"
```
Expected: HEAD `8cf1e5a`, jedyny nieskomitowany plik to raport review; `1787 passed` (+ deselected `live`); 32 linie bledow mypy.

- [ ] **Step 2: Wiersz w README folderu research** — dopisz do tabeli:

```markdown
| `2026-08-30-code-review-max.md` | Review max galezi (10 katow + 9 weryfikatorow): 15 potwierdzonych znalezisk z file:line i pomiarami; naprawy: `docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md` |
```

- [ ] **Step 3: Commit raportu**

```bash
git add docs/research/2026-08-28-uklad-data-target-crs-pl/
git commit -m "docs(research): raport review max 2026-08-30 (15 znalezisk)"
```

- [ ] **Step 4: Commit planu** — skopiuj ten plik do `docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md`:

```bash
git add docs/superpowers/plans/2026-09-28-fala-review-max-i-wycinek-biblioteczny.md
git commit -m "docs(plan): fala naprawcza po review max + wycinek PL w bibliotece"
```

---

### Zad. 1: Dokumentacja zgodna z kodem — `--force` i selekcja arkuszy R-01 (zn. 5, 6)

Pierwsze, bo implementerzy kolejnych zadan czytaja CLAUDE.md, a ten dzis opisuje odwrotnosc faktycznej semantyki `--force`. Model: sonnet (review: sonnet).

**Files:**
- Modify: `CLAUDE.md:297-298`
- Modify: `docs/DECISIONS.md:1034-1040` (ADR-027 Decyzja) i `docs/DECISIONS.md:1046-1048` (ADR-027 Konsekwencje)

- [ ] **Step 1: Zweryfikuj fakty na kodzie** (nie ufaj temu planowi):
  - `kartograf/cli/download_cmd.py::_build_pl_cutout` — brak `target_path.unlink`, tylko `tmp.unlink` w `finally`; `transform/raster.py:133-137` — `os.replace` + sprzatanie tylko tmp; testy `tests/test_pl_cutout.py::TestBuildPlCutout::test_failed_build_keeps_previous_result` i `tests/test_transform_raster.py::test_failed_warp_keeps_previous_destination`.
  - Tor CZ: `providers/cuzk/dmr.py::_warp_to_grid` (`except BaseException:` + `unlink`) i `providers/cuzk/client.py:186` — CZ przy awarii KASUJE plik docelowy.
  - R-01: `download_cmd.py:1980-1993` — przy warpie godla geometrii + godla `bbox_source_2180`.

- [ ] **Step 2: `CLAUDE.md`** — zamien:

stare:
```
  arkusz. Przy `--force` nieudana budowa wycinka kasuje TAKZE poprzedni plik
  wyniku ("odswiez albo nic", jak w torze CZ)
```
nowe:
```
  arkusz. Nieudana budowa wycinka (takze z `--force`) NIE kasuje poprzedniego
  pliku wyniku — zapis jest atomowy (`os.replace`), poprzedni plik przezywa
  awarie; inaczej tor CZ, ktory przy awarii warpu/mozaiki kasuje plik docelowy
  (kod zweryfikowany live, ADR-024 — nie ruszamy go przed wydaniem)
```

- [ ] **Step 3: ADR-027, Decyzja** (`docs/DECISIONS.md:1036-1038`) — zamien:

stare:
```
docelowego). W trybie `--bbox` ten powiekszony bbox steruje TAKZE selekcja
arkuszy; w trybie `--geometry` arkusze dalej wyznacza sama geometria per
obiekt, a zapas wplywa wylacznie na crop i siatke. Wycinek z `--geometry`
```
nowe:
```
docelowego). Ten powiekszony bbox steruje TAKZE selekcja arkuszy w OBU
trybach: `--bbox` wybiera arkusze wprost z niego, a `--geometry` przy warpie
bierze SUME godel geometrii (per obiekt) i godel powiekszonego bboxa (R-01;
dla celu EPSG:2180 zapasu nie ma, wiec arkusze wyznacza sama geometria).
Wycinek z `--geometry`
```

- [ ] **Step 4: ADR-027, Konsekwencje** (`docs/DECISIONS.md:1046-1048`) — zamien:

stare:
```
tor CZ zweryfikowany live tuz przed wydaniem). Przy `--force` nieudana
budowa wycinka kasuje TAKZE poprzedni plik wyniku (semantyka "odswiez albo
nic", ta sama co w torze CZ).
```
nowe:
```
tor CZ zweryfikowany live tuz przed wydaniem). Nieudana budowa wycinka NIE
kasuje poprzedniego pliku wyniku (zapis atomowy przez `os.replace`, takze
z `--force`); tor CZ jest tu wyjatkiem i przy awarii kasuje plik docelowy.
(Korekta 2026-09-28: wczesniejsze brzmienie tego akapitu i zdania o selekcji
arkuszy w `--geometry` opisywalo odwrotnosc zachowania kodu — review max
2026-08-30, znaleziska 5-6.)
```

- [ ] **Step 5: Bledne brzmienie nie moze przetrwac gdzie indziej**

Run: `grep -rn "odswiez albo nic\|kasuje TAKZE\|wplywa wylacznie na crop" CLAUDE.md README.md docs/ --include=*.md | grep -v "docs/research/\|docs/superpowers/"`
Expected: brak wynikow (raporty w `docs/research/` i plany/specy w `docs/superpowers/` to zapis historii — bez zmian).

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md docs/DECISIONS.md
git commit -m "docs: semantyka --force i selekcja arkuszy R-01 zgodne z kodem (CLAUDE.md, ADR-027)"
```

---

### Zad. 2: `mosaic_and_crop` bez wyczerpania deskryptorow (zn. 3)

Model: sonnet (review: sonnet). Wspolna funkcja PL i CZ — wynik bez zmian.

**Files:**
- Modify: `kartograf/transport/mosaic.py`
- Test: `tests/test_transport_mosaic.py`

**Interfaces:**
- Produces: `mosaic_and_crop(inputs, bbox, output_path, *, nodata=None, dst_kwds=None) -> Path` — sygnatura bez zmian; poza wnetrzem `merge` nigdy nie trzyma otwartego wiecej niz jednego zrodla.

- [ ] **Step 1: Test padajacy** — na koniec `tests/test_transport_mosaic.py` (dodaj `import os`, `import sys` na gorze, jesli brak):

```python
@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc/self/fd")
def test_many_inputs_do_not_exhaust_file_descriptors(tmp_path):
    """Zn. 3 review max: wycinek 75 x 75 km to >1200 arkuszy, a limit
    deskryptorow to 1024 (Linux) / 256 (macOS). Mozaika nie moze trzymac
    otwartych wszystkich zrodel naraz."""
    import resource

    n = 300
    paths = [
        _write_tile(tmp_path / f"t{i:03d}.tif", 2 * i, 2, float(i), size=2)
        for i in range(n)
    ]
    # rozgrzewka: pierwsze otwarcie rastra otwiera na stale proj.db (+1 fd)
    with rasterio.open(paths[0]) as src:
        _ = src.crs
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    in_use = len(os.listdir("/proc/self/fd"))
    resource.setrlimit(resource.RLIMIT_NOFILE, (in_use + 64, hard))
    try:
        out = mosaic_and_crop(
            paths, BBox(0, 0, 2 * n, 2, "EPSG:2180"), tmp_path / "out.tif"
        )
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))

    with rasterio.open(out) as src:
        data = src.read(1)
    assert data.shape == (2, 2 * n)
    assert data[0, 0] == 0.0
    assert data[0, 2 * n - 1] == float(n - 1)
```

- [ ] **Step 2: Uruchom — musi padac**

Run: `.venv/bin/python -m pytest tests/test_transport_mosaic.py::test_many_inputs_do_not_exhaust_file_descriptors -q`
Expected: FAIL z `Too many open files` (RasterioIOError przy `rasterio.open` w `ExitStack`).

- [ ] **Step 3: Implementacja** — w `kartograf/transport/mosaic.py` usun `import contextlib`, docstring modulu uzupelnij o "drugi konsument: wycinek PL (ADR-027)", a funkcje zastap:

```python
def mosaic_and_crop(
    inputs: list[Path],
    bbox: BBox,
    output_path: Path,
    *,
    nodata: float | None = None,
    dst_kwds: dict | None = None,
) -> Path:
    """Zszyj rastry wejsciowe i przytnij do bbox; zwroc output_path.

    ``dst_kwds`` nadpisuje profil wyjscia (np. driver/CRS, gdy zrodla ASC
    ich nie maja).

    Zrodla otwierane sa POJEDYNCZO: metadane czyta petla sekwencyjna (jeden
    deskryptor naraz), a ``merge`` dostaje SCIEZKI i sam otwiera zrodla po
    jednym, per kawalek wyniku. Wycinek 75 x 75 km to >1200 arkuszy, a domyslny
    limit deskryptorow to 1024 (Linux; macOS 256) — trzymanie wszystkich
    zrodel otwartych naraz konczylo sie "Too many open files" dopiero PO
    wielogodzinnym pobraniu (review max 2026-08-30, zn. 3).
    """
    if not inputs:
        raise ValidationError("mosaic_and_crop: brak rastrow wejsciowych")

    output_path = Path(output_path)
    paths = [Path(p) for p in inputs]

    crs_set: set[str] = set()
    res_set: set[tuple[float, float]] = set()
    for path in paths:
        with rasterio.open(path) as src:
            crs_set.add(str(src.crs))
            res_set.add(src.res)
    if len(crs_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne CRS wejsc: {sorted(crs_set)}"
        )
    if len(res_set) > 1:
        raise ValidationError(
            f"mosaic_and_crop: niezgodne rozdzielczosci wejsc: {sorted(res_set)}"
        )

    # merge z dst_path sam otwiera plik do zapisu (stad mkdir PRZED
    # wywolaniem) i liczy wynik kawalkami wg mem_limit; bez dst_path
    # caly raster ladowalby do jednej tablicy w RAM — szczyt 2,63x
    # rozmiaru danych, czyli ok. 2,4 GB dla zlewni 30x30 km przy DMR 5G.
    # Profil wyjscia merge bierze z PIERWSZEGO zrodla.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kwds: dict = {}
    if nodata is not None:
        kwds["nodata"] = nodata
    if dst_kwds:
        kwds.update(dst_kwds)
    merge(
        paths,
        bounds=(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y),
        nodata=nodata,
        dst_path=str(output_path),
        dst_kwds=kwds or None,
    )
    return output_path
```

- [ ] **Step 4: Zielono + tor CZ + pelna suita**

Run: `.venv/bin/python -m pytest tests/test_transport_mosaic.py tests/test_cuzk_client.py tests/test_cuzk_dmr.py tests/test_pl_cutout.py -q` -> PASS; `.venv/bin/python -m pytest tests/ -q` -> PASS.

- [ ] **Step 5: Dowod mutacyjny** — przywroc tymczasowo `contextlib.ExitStack()` z `sources = [stack.enter_context(rasterio.open(p)) for p in paths]` i `merge(sources, ...)`: nowy test FAIL (`Too many open files`); przywroc -> PASS; `git status` czysty poza zmianami zadania.

- [ ] **Step 6: CHANGELOG** (`docs/CHANGELOG.md`, 0.7.0, `### Fixed`):

```markdown
- **Wycinek PL z >1024 arkuszy konczyl sie "Too many open files" dopiero po
  pobraniu** (review max, zn. 3). `mosaic_and_crop` otwieral wszystkie zrodla
  naraz; teraz metadane czyta po jednym pliku, a `merge` dostaje sciezki
  i otwiera zrodla leniwie (limit deskryptorow: Linux 1024, macOS 256).
```

- [ ] **Step 7: Commit**

```bash
git add kartograf/transport/mosaic.py tests/test_transport_mosaic.py docs/CHANGELOG.md
git commit -m "fix(transport): mozaika otwiera zrodla leniwie — bez wyczerpania deskryptorow"
```

---

### Zad. 3: `mosaic_and_crop(snap_to_source_grid=True)` — crop na siatce zrodel (zn. 1, czesc A)

Model: sonnet (kod gotowy); review: **opus** (arytmetyka siatki, bledy zmiennoprzecinkowe). Parametr domyslnie `False` — wywolanie CZ bez zmian. **Nie rzucamy przy niezgodnej siatce**: kontrola dzieje sie PO pobraniu, a arkusze sa w cache, wiec blad oznaczalby obszar na zawsze niemozliwy do wyciecia — zamiast tego siatka wiekszosci + ostrzezenie.

**Files:**
- Modify: `kartograf/transport/mosaic.py`
- Test: `tests/test_transport_mosaic.py`

**Interfaces:**
- Produces: `mosaic_and_crop(..., snap_to_source_grid: bool = False) -> Path`. Przy `True`: bbox rozszerzony NA ZEWNATRZ do linii siatki WIEKSZOSCI zrodel (remis: siatka pierwszego w kolejnosci wejscia); zrodla spoza niej -> `logger.warning` (lista + maks. przesuniecie w px), ich tresc merge przepisuje najblizszym sasiadem; zrodlo obrocone -> `ValidationError`.

- [ ] **Step 1: Testy padajace** — w `tests/test_transport_mosaic.py` (dodaj `import logging`, `import numpy as np`, jesli brak):

```python
def _write_lattice_tile(path, col0, row0, cols, rows, *, x0=0.5, y_top=100.5, res=1.0):
    """Kafel na siatce z narozami w x0 + k*res — jak arkusze GUGiK, ktorych
    narozniki leza pol piksela od liczb calkowitych (fakt 1 planu).
    Wartosc = 1000 * globalny_wiersz + globalna_kolumna: jednoznaczna, wiec
    kazde przesuniecie tresci widac jako rozbieznosc wartosci."""
    transform = rasterio.transform.from_origin(
        x0 + col0 * res, y_top - row0 * res, res, res
    )
    r, c = np.meshgrid(np.arange(rows) + row0, np.arange(cols) + col0, indexing="ij")
    with rasterio.open(
        path, "w", driver="GTiff", height=rows, width=cols, count=1,
        dtype="float32", crs="EPSG:2180", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write((1000.0 * r + c).astype("float32"), 1)
    return path


@pytest.mark.parametrize(
    "bbox",
    [
        BBox(3.37, 92.13, 17.61, 97.9, "EPSG:2180"),
        BBox(3.0, 92.0, 17.0, 98.0, "EPSG:2180"),  # calkowity = remis 0,5 px
    ],
    ids=["ulamkowy", "calkowity"],
)
def test_snap_copies_source_pixels_exactly(tmp_path, bbox):
    """Zn. 1: piksele wyniku = piksele zrodel (bez przesuniecia i bez
    mieszania kolumn przy remisie); zasieg = zadanie + < 1 px na strone."""
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 12, 10)
    b = _write_lattice_tile(tmp_path / "b.tif", 10, 0, 12, 10)  # zakladka 2 px
    out = mosaic_and_crop(
        [a, b], bbox, tmp_path / "out.tif", nodata=-9999.0, snap_to_source_grid=True
    )
    with rasterio.open(out) as src:
        t, data = src.transform, src.read(1)
        left, bottom, right, top = src.bounds

    col0, row0 = t.c - 0.5, 100.5 - t.f
    assert col0 == pytest.approx(round(col0), abs=1e-9)
    assert row0 == pytest.approx(round(row0), abs=1e-9)
    assert left <= bbox.min_x < left + 1.0 and right - 1.0 < bbox.max_x <= right
    assert bottom <= bbox.min_y < bottom + 1.0 and top - 1.0 < bbox.max_y <= top
    r, c = np.meshgrid(
        np.arange(data.shape[0]) + round(row0),
        np.arange(data.shape[1]) + round(col0),
        indexing="ij",
    )
    np.testing.assert_array_equal(data, (1000.0 * r + c).astype("float32"))


def test_snap_uses_majority_grid_and_warns(tmp_path, caplog):
    """Zrodlo poza siatka nie wetuje mozaiki (arkusze sa w cache — blad
    bylby trwaly); siatka = wiekszosc, nie 'pierwsze na liscie'."""
    odd = _write_lattice_tile(tmp_path / "odd.tif", 20, 0, 4, 10, x0=0.75)
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 12, 10)
    b = _write_lattice_tile(tmp_path / "b.tif", 10, 0, 12, 10)
    with caplog.at_level(logging.WARNING, logger="kartograf.transport.mosaic"):
        out = mosaic_and_crop(
            [odd, a, b], BBox(3.37, 92.13, 17.61, 97.9, "EPSG:2180"),
            tmp_path / "o.tif", snap_to_source_grid=True,
        )
    with rasterio.open(out) as src:
        assert (src.transform.c - 0.5) == pytest.approx(round(src.transform.c - 0.5), abs=1e-9)
    assert "odd.tif" in caplog.text and "0.250" in caplog.text


def test_snap_keeps_bbox_already_on_grid(tmp_path):
    """3 * 0.1 == 0.30000000000000004: iloraz 3.0000000000000004 nie moze
    dolozyc czwartej kolumny (tolerancja bledu zmiennoprzecinkowego)."""
    a = _write_lattice_tile(tmp_path / "a.tif", 0, 0, 10, 10, x0=0.0, y_top=1.0, res=0.1)
    out = mosaic_and_crop(
        [a], BBox(0.0, 0.5, 3 * 0.1, 1.0, "EPSG:2180"), tmp_path / "o.tif",
        snap_to_source_grid=True,
    )
    with rasterio.open(out) as src:
        assert (src.width, src.height) == (3, 5)


def test_snap_rejects_rotated_source(tmp_path):
    from affine import Affine

    path = tmp_path / "rot.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs="EPSG:2180", transform=Affine(1.0, 0.1, 0.0, 0.1, -1.0, 4.0),
    ) as dst:
        dst.write(np.ones((4, 4), dtype="float32"), 1)
    with pytest.raises(ValidationError, match="obrocona"):
        mosaic_and_crop(
            [path], BBox(0, 0, 4, 4, "EPSG:2180"), tmp_path / "o.tif",
            snap_to_source_grid=True,
        )
```

- [ ] **Step 2: Uruchom — musza padac** (`TypeError: ... unexpected keyword argument 'snap_to_source_grid'`).

- [ ] **Step 3: Implementacja** w `kartograf/transport/mosaic.py`:
  (a) na gorze: `import logging`, `import math`, `from collections import Counter`; `logger = logging.getLogger(__name__)`; nad `mosaic_and_crop`:

```python
# Tolerancja w pikselach: siatki zgodne i bboxy lezace na linii siatki
# z dokladnoscia bledu zmiennoprzecinkowego nie moga ani dokladac kolumny,
# ani rozdzielac zrodel na rozne siatki.
_GRID_TOL_PX = 1e-6


def _phase(value: float, step: float) -> int:
    """Polozenie linii siatki w obrebie piksela (w jednostkach tolerancji).

    Dwie siatki o tym samym kroku sa zgodne, gdy fazy sa rowne; faza tuz
    ponizej 1 to ta sama siatka co faza 0.
    """
    p = (value / step) % 1.0
    if p > 1.0 - _GRID_TOL_PX:
        p = 0.0
    return round(p / _GRID_TOL_PX)


def _snap_outward(
    bounds: tuple[float, float, float, float],
    paths: list[Path],
    transforms: list,
) -> tuple[tuple[float, float, float, float], list[tuple[Path, float, float]]]:
    """Bounds rozszerzone na zewnatrz do siatki zrodel + zrodla spoza niej.

    Siatka odniesienia = siatka WIEKSZOSCI zrodel (remis: pierwszej w
    kolejnosci wejscia). Linie pionowe ``x0 + k * rx``, poziome ``y0 + k * ry``
    (``y0`` to GORNA krawedz, ``transform.f``). Arkusze GUGiK jednego produktu
    leza na jednej siatce, ale NIE na wielokrotnosciach piksela (zmierzone na
    1977 arkuszach 5 m: narozniki na 5k + 2,5 m) — stad siatka z transformacji.
    Zrodlo spoza siatki nie jest bledem (arkusze sa juz w cache, blad bylby
    trwaly): wraca na liscie z przesunieciem w pikselach, a jego tresc merge
    przepisze metoda najblizszego sasiada.
    """
    for path, t in zip(paths, transforms):
        if t.b != 0 or t.d != 0:
            raise ValidationError(f"mosaic_and_crop: obrocona siatka zrodla {path.name}")
    rx, ry = transforms[0].a, -transforms[0].e
    keys = [(_phase(t.c, rx), _phase(t.f, ry)) for t in transforms]
    majority = Counter(keys).most_common(1)[0][0]
    ref = transforms[keys.index(majority)]
    x0, y0 = ref.c, ref.f
    off_grid = [
        (
            path,
            ((t.c - x0) / rx + 0.5) % 1.0 - 0.5,
            ((t.f - y0) / ry + 0.5) % 1.0 - 0.5,
        )
        for path, t, key in zip(paths, transforms, keys)
        if key != majority
    ]
    min_x, min_y, max_x, max_y = bounds
    snapped = (
        x0 + math.floor((min_x - x0) / rx + _GRID_TOL_PX) * rx,
        y0 + math.floor((min_y - y0) / ry + _GRID_TOL_PX) * ry,
        x0 + math.ceil((max_x - x0) / rx - _GRID_TOL_PX) * rx,
        y0 + math.ceil((max_y - y0) / ry - _GRID_TOL_PX) * ry,
    )
    return snapped, off_grid
```

  (b) w `mosaic_and_crop`: parametr `snap_to_source_grid: bool = False` (keyword-only, po `dst_kwds`); petla metadanych zbiera tez `transforms.append(src.transform)`; po walidacji CRS/res:

```python
    bounds = (bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)
    if snap_to_source_grid:
        # Bez tego siatke wyniku kotwiczy rog bbox, a merge przepisuje piksele
        # najblizszym sasiadem: tresc przesuwa sie o ulamek piksela, a przy
        # remisie (bbox calkowity na siatce GUGiK z narozami w k + 0,5) sasiednie
        # kolumny mieszaja sie (review max 2026-08-30, zn. 1; fakt 2 planu).
        bounds, off_grid = _snap_outward(bounds, paths, transforms)
        if off_grid:
            worst = max(max(abs(dx), abs(dy)) for _, dx, dy in off_grid)
            names = ", ".join(p.name for p, _, _ in off_grid[:10])
            logger.warning(
                f"mosaic_and_crop: {len(off_grid)} z {len(paths)} zrodel poza "
                f"siatka pikseli wiekszosci (maks. przesuniecie {worst:.3f} px) "
                f"— ich tresc przepisana najblizszym sasiadem: {names}"
                + (" ..." if len(off_grid) > 10 else "")
            )
```
  i `merge(paths, bounds=bounds, ...)`. Docstring: akapit o `snap_to_source_grid` (co robi, siatka wiekszosci, ostrzezenie, `ValidationError` dla zrodla obroconego).

- [ ] **Step 4: Zielono + CZ + pelna suita** — jak w Zad. 2, Step 4.

- [ ] **Step 5: Dowody mutacyjne** (FAIL -> przywroc -> PASS):
  1. `if snap_to_source_grid:` -> `if False:` — oba warianty `test_snap_copies_source_pixels_exactly` FAIL.
  2. `ref = transforms[keys.index(majority)]` -> `ref = transforms[0]` — `test_snap_uses_majority_grid_and_warns` FAIL.
  3. `math.ceil((max_x - x0) / rx - _GRID_TOL_PX)` -> `math.ceil((max_x - x0) / rx)` — `test_snap_keeps_bbox_already_on_grid` FAIL (szerokosc 4).
  4. Usun petle sprawdzajaca obrot — `test_snap_rejects_rotated_source` FAIL.

- [ ] **Step 6: Commit** (CHANGELOG w Zad. 9, gdy przyciaganie wlaczy sie w torze PL)

```bash
git add kartograf/transport/mosaic.py tests/test_transport_mosaic.py
git commit -m "feat(transport): mosaic_and_crop(snap_to_source_grid=) — crop na siatce zrodel"
```

---

### Zad. 4: `mosaic_and_crop(assign_crs=, dtype=)` — normalizacja zrodel przez VRT (fakty 5, 6)

Model: **opus** (review: opus) — XML VRT, `/vsimem/`, deskryptory. Parametry domyslnie `None` — wywolanie CZ bez zmian.

**Files:**
- Modify: `kartograf/transport/mosaic.py`
- Test: `tests/test_transport_mosaic.py`

**Interfaces:**
- Produces: `mosaic_and_crop(..., assign_crs: str | None = None, dtype: str | None = None) -> Path`. Gdy ktorys podany: kazde zrodlo (jednopasmowe) owijane jest w VRT 1:1 w `/vsimem/` (`rasterio.io.MemoryFile`) z `SRS` = `assign_crs` (albo wlasny CRS zrodla) i typem pasma = `dtype` (albo wlasny); `merge` dostaje nazwy VRT. Zrodlo z WLASNYM CRS roznym od `assign_crs` (porownanie `pyproj.CRS.equals(..., ignore_axis_order=True)`) -> `ValidationError` ("wymuszany"); zrodlo bez CRS (ASC bez `.prj`) — dozwolone. Zrodlo wielopasmowe przy owijaniu -> `ValidationError`.

- [ ] **Step 1: Testy padajace** — w `tests/test_transport_mosaic.py`:

```python
def _write_asc_text(path, xll, yll, rows, *, cellsize=1.0, nodata_header="-9999"):
    """ASC jak u GUGiK: naglowek z `nodata_value -9999` BEZ kropki (fakt 5)."""
    header = (
        f"ncols {len(rows[0])}\nnrows {len(rows)}\nxllcorner {xll}\n"
        f"yllcorner {yll}\ncellsize {cellsize}\nnodata_value {nodata_header}\n"
    )
    path.write_text(header + "\n".join(" ".join(r) for r in rows) + "\n")
    return path


def _write_prj(asc_path, epsg):
    from pyproj import CRS

    asc_path.with_suffix(".prj").write_text(CRS.from_epsg(epsg).to_wkt("WKT1_GDAL"))


def test_assign_crs_merges_sources_with_and_without_prj(tmp_path):
    """Fakt 6: Hydrograf dopisuje .prj do czesci arkuszy; merge rzucal
    'CRS mismatch'. Z assign_crs zrodla dostaja jawny SRS przez VRT."""
    a = _write_asc_text(tmp_path / "a.asc", 0.5, 0.5, [["1.5"] * 4] * 4)
    b = _write_asc_text(tmp_path / "b.asc", 4.5, 0.5, [["2.5"] * 4] * 4)
    _write_prj(a, 2180)
    with rasterio.open(a) as sa, rasterio.open(b) as sb:
        assert sa.crs is not None and sb.crs is None  # warunek sensownosci testu
    bbox = BBox(0.5, 0.5, 8.5, 4.5, "EPSG:2180")
    with pytest.raises(ValidationError, match="niezgodne CRS"):
        mosaic_and_crop([a, b], bbox, tmp_path / "x.tif")
    out = mosaic_and_crop([a, b], bbox, tmp_path / "o.tif", assign_crs="EPSG:2180")
    with rasterio.open(out) as src:
        data = src.read(1)
        assert src.crs.to_epsg() == 2180
        assert src.driver == "GTiff"  # profil z pierwszego zrodla to VRT
    assert data[0, 0] == 1.5 and data[0, -1] == 2.5


def test_assign_crs_rejects_source_with_other_crs(tmp_path):
    a = _write_asc_text(tmp_path / "a.asc", 0.5, 0.5, [["1.5"] * 4] * 4)
    _write_prj(a, 2177)
    with pytest.raises(ValidationError, match="wymuszany"):
        mosaic_and_crop(
            [a], BBox(0.5, 0.5, 4.5, 4.5, "EPSG:2180"), tmp_path / "o.tif",
            assign_crs="EPSG:2180",
        )


def test_dtype_float32_keeps_decimals_when_first_source_is_integer(tmp_path):
    """Fakt 5: ASC z samymi liczbami calkowitymi GDAL czyta jako Int32,
    a merge bierze dtype z PIERWSZEGO zrodla — wysokosci innych arkuszy
    bylyby obciete."""
    a = _write_asc_text(tmp_path / "a.asc", 0.5, 0.5, [["100"] * 4] * 4)
    b = _write_asc_text(tmp_path / "b.asc", 4.5, 0.5, [["100.25"] * 4] * 4)
    with rasterio.open(a) as sa:
        assert sa.dtypes[0] == "int32"  # warunek sensownosci testu
    out = mosaic_and_crop(
        [a, b], BBox(0.5, 0.5, 8.5, 4.5, "EPSG:2180"), tmp_path / "o.tif",
        assign_crs="EPSG:2180", dtype="float32",
    )
    with rasterio.open(out) as src:
        data = src.read(1)
        assert src.dtypes[0] == "float32"
    assert data[0, -1] == pytest.approx(100.25)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc/self/fd")
def test_vrt_wrapping_does_not_exhaust_file_descriptors(tmp_path):
    """Owijanie w VRT tez nie moze trzymac otwartych wszystkich zrodel."""
    import resource

    n = 300
    paths = [
        _write_tile(tmp_path / f"t{i:03d}.tif", 2 * i, 2, float(i), size=2)
        for i in range(n)
    ]
    with rasterio.open(paths[0]) as src:
        _ = src.crs
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    in_use = len(os.listdir("/proc/self/fd"))
    # zapas 160: pula zbiorow GDAL (GDAL_MAX_DATASET_POOL_SIZE, domyslnie 100)
    # moze trzymac otwarte zrodla VRT — zmierz faktyczne zuzycie i wpisz do raportu
    resource.setrlimit(resource.RLIMIT_NOFILE, (in_use + 160, hard))
    try:
        out = mosaic_and_crop(
            paths, BBox(0, 0, 2 * n, 2, "EPSG:2180"), tmp_path / "out.tif",
            assign_crs="EPSG:2180", dtype="float32",
        )
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
    with rasterio.open(out) as src:
        assert src.read(1)[0, 2 * n - 1] == float(n - 1)
```

- [ ] **Step 2: Uruchom — musza padac** (`unexpected keyword argument 'assign_crs'`).

- [ ] **Step 3: Implementacja** w `kartograf/transport/mosaic.py`:
  (a) importy: `import os`, `from xml.sax.saxutils import escape`, `from pyproj import CRS`, `from rasterio.io import MemoryFile`; stale i helper:

```python
# typ numpy/rasterio -> nazwa typu GDAL w XML VRT
_VRT_TYPES = {
    "uint8": "Byte", "int16": "Int16", "uint16": "UInt16", "int32": "Int32",
    "uint32": "UInt32", "float32": "Float32", "float64": "Float64",
}


def _vrt_xml(path: Path, meta: dict, *, crs_wkt: str | None, dtype: str, nodata) -> str:
    """Jednopasmowy VRT 1:1 nad zrodlem: wymuszony SRS i typ pasma.

    Sciezka zrodla absolutna (``relativeToVRT="0"``) — VRT zyje w
    ``/vsimem/``, wzgledna nie mialaby do czego sie odnosic.
    """
    t = meta["transform"]
    srs = f"<SRS>{escape(crs_wkt)}</SRS>" if crs_wkt else ""
    nodata_xml = f"<NoDataValue>{nodata!r}</NoDataValue>" if nodata is not None else ""
    source = escape(os.path.abspath(path))
    return (
        f'<VRTDataset rasterXSize="{meta["width"]}" rasterYSize="{meta["height"]}">'
        f"{srs}<GeoTransform>{t.c!r}, {t.a!r}, {t.b!r}, {t.f!r}, {t.d!r}, {t.e!r}"
        f'</GeoTransform><VRTRasterBand dataType="{_VRT_TYPES[dtype]}" band="1">'
        f'{nodata_xml}<SimpleSource><SourceFilename relativeToVRT="0">{source}'
        "</SourceFilename><SourceBand>1</SourceBand></SimpleSource>"
        "</VRTRasterBand></VRTDataset>"
    )
```

  (b) w `mosaic_and_crop`: parametry `assign_crs: str | None = None, dtype: str | None = None` (keyword-only). Petla metadanych zbiera per zrodlo slownik `meta = {"crs", "transform", "width", "height", "count", "dtype", "nodata"}` (plus `res` do `res_set`). Walidacja:
  - bez `assign_crs`: kontrola `crs_set` jak dotad;
  - z `assign_crs`: `target = CRS.from_user_input(assign_crs)`; kazde zrodlo z `meta["crs"] is not None` i `not CRS.from_user_input(meta["crs"].to_wkt()).equals(target, ignore_axis_order=True)` -> `ValidationError(f"mosaic_and_crop: zrodlo {path.name} ma CRS {meta['crs']}, a wymuszany jest {assign_crs}")`; kontroli `crs_set` nie ma (CRS `None` obok EPSG:2180 jest dozwolony);
  - przy owijaniu (`assign_crs or dtype`): `meta["count"] != 1` -> `ValidationError`; typ spoza `_VRT_TYPES` -> `ValidationError`.
  Przy owijaniu `kwds.setdefault("driver", "GTiff")` — `merge` bierze profil wyjscia z PIERWSZEGO zrodla, a to bylby VRT (bez tego wynik bez `dst_kwds` zapisalby sie sterownikiem VRT). Owijanie (tuz przed `merge`, po przyciaganiu z Zad. 3 — transformacje VRT = transformacje zrodel, wiec przyciaganie liczone na oryginalach jest wazne):

```python
    memfiles: list[MemoryFile] = []
    try:
        if assign_crs is not None or dtype is not None:
            forced_wkt = CRS.from_user_input(assign_crs).to_wkt() if assign_crs else None
            sources: list = []
            for path, meta in zip(paths, metas):
                wkt = forced_wkt or (meta["crs"].to_wkt() if meta["crs"] else None)
                xml = _vrt_xml(
                    path, meta, crs_wkt=wkt, dtype=dtype or meta["dtype"],
                    nodata=nodata if nodata is not None else meta["nodata"],
                )
                memfile = MemoryFile(xml.encode(), ext=".vrt")
                memfiles.append(memfile)
                sources.append(memfile.name)
        else:
            sources = paths
        merge(sources, bounds=bounds, nodata=nodata, dst_path=str(output_path), dst_kwds=kwds or None)
    finally:
        for memfile in memfiles:
            memfile.close()
```
  Docstring: akapit o `assign_crs`/`dtype` (po co: `.prj` od Hydrografu, Int32; co odrzuca).

- [ ] **Step 4: Zielono + CZ + pelna suita.** Do raportu: faktyczne zuzycie deskryptorow w `test_vrt_wrapping_does_not_exhaust_file_descriptors` (np. obnizaj zapas, az padnie) — jesli VRT trzyma > 100 zrodel otwartych, STOP i zglos kontrolerowi (ruling przed dalsza praca).

- [ ] **Step 5: Dowody mutacyjne:**
  1. Zamiast `sources.append(memfile.name)` podawaj `path` (bez VRT), zostawiajac pominieta kontrole `crs_set` — `test_assign_crs_merges_sources_with_and_without_prj` FAIL (`CRS mismatch`).
  2. `dtype=dtype or meta["dtype"]` -> `dtype=meta["dtype"]` — test Int32 FAIL (100.0).
  3. Usun kontrole "wymuszany" — `test_assign_crs_rejects_source_with_other_crs` FAIL.
  4. Otwieraj wszystkie VRT naraz przed `merge` (lista `rasterio.open(mf.name)` w `ExitStack`) — test deskryptorow FAIL.
  5. Usun `kwds.setdefault("driver", "GTiff")` — asercja `src.driver == "GTiff"` FAIL.

- [ ] **Step 6: Commit** (CHANGELOG w Zad. 9)

```bash
git add kartograf/transport/mosaic.py tests/test_transport_mosaic.py
git commit -m "feat(transport): mosaic_and_crop(assign_crs=, dtype=) — normalizacja zrodel przez VRT"
```

---
### Zad. 5: Selekcja arkuszy nie gubi pasa przy gornej krawedzi na poludniku 19°E (fakt 8)

Model: sonnet (review: sonnet). Blad selekcji dotyczy KAZDEGO trybu bbox/geometria (nie tylko wycinka): arkusze przecinajace bbox waskim pasem przy gornej krawedzi nie sa wybierane — wycinek ma tam nodata, lista arkuszy jest niepelna.

**Files:**
- Modify: `kartograf/core/sheet_parser.py:927-959` (`_transform_bbox_to_wgs84`)
- Test: `tests/test_sheet_parser.py` (klasa `TestFindSheetsForBBox`, ok. l. 995)

- [ ] **Step 1: Test padajacy** — w `TestFindSheetsForBBox`:

```python
    def test_top_edge_across_central_meridian_keeps_sheets(self):
        """Fakt 8 planu 2026-09-28: w PUWG 1992 najwieksza szerokosc gornej
        krawedzi wypada na poludniku osiowym (x = 500 000), nie w naroznikach.
        Obwiednia z 4 naroznikow gubila 6 arkuszy, ktore faktycznie przecinaja
        ponizszy bbox waskim pasem przy gornej krawedzi."""
        import numpy as np
        from pyproj import Transformer

        bbox = BBox(490000, 470000, 510000, 480161, "EPSG:2180")
        expected = {
            "N-34-134-B-d-3-2", "N-34-134-B-d-4-1", "N-34-134-B-d-4-2",
            "N-34-135-A-c-3-1", "N-34-135-A-c-3-2", "N-34-135-A-c-4-1",
        }
        # warunek sensownosci: kazdy z arkuszy zawiera punkt z wnetrza bboxa
        to_wgs = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
        xs = np.linspace(bbox.min_x + 1, bbox.max_x - 1, 4001)
        lon, lat = to_wgs.transform(xs, np.full_like(xs, bbox.max_y - 0.01))
        for godlo in expected:
            s = SheetParser(godlo).get_bbox("EPSG:4326")
            inside = (lon > s.min_x) & (lon < s.max_x) & (lat > s.min_y) & (lat < s.max_y)
            assert inside.any(), godlo

        assert expected <= set(find_sheets_for_bbox(bbox, "1:10000"))
```

- [ ] **Step 2: Uruchom — musi padac** (6 brakujacych godel).

- [ ] **Step 3: Implementacja** — w `kartograf/core/sheet_parser.py` nad funkcja stala, cialo funkcji:

```python
# Poludnik osiowy PUWG 1992 (EPSG:2180): false easting 500 000 m <=> 19°E.
_PL1992_CENTRAL_X = 500_000.0


def _transform_bbox_to_wgs84(bbox: BBox) -> BBox:
    """
    Transformuje BBox z EPSG:2180 do EPSG:4326.

    Narozniki NIE wystarczaja: w PUWG 1992 rownolezniki sa lukami i wzdluz
    linii stalego y szerokosc geograficzna jest NAJWIEKSZA na poludniku
    osiowym (x = 500 000 m, 19°E), malejac monotonicznie z odlegloscia od
    niego. Dla bboxa przecinajacego ten poludnik obwiednia z 4 naroznikow
    gubila pas przy gornej krawedzi (zmierzone 2026-09-28: 6 arkuszy 1:10000
    dla bboxa szerokiego na 20 km; pas rosnie z kwadratem szerokosci, ~63 m
    przy 50 km). Punkt na poludniku osiowym na obu krawedziach poziomych
    daje ekstrema dokladnie; dlugosc geograficzna i krawedzie pionowe maja
    ekstrema w naroznikach.

    Parameters
    ----------
    bbox : BBox
        Bbox w EPSG:2180

    Returns
    -------
    BBox
        Bbox w EPSG:4326 (min_x=west_lon, min_y=south_lat, ...)
    """
    transformer = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)

    points_2180 = [
        (bbox.min_x, bbox.min_y),  # SW
        (bbox.min_x, bbox.max_y),  # NW
        (bbox.max_x, bbox.min_y),  # SE
        (bbox.max_x, bbox.max_y),  # NE
    ]
    if bbox.min_x < _PL1992_CENTRAL_X < bbox.max_x:
        points_2180 += [
            (_PL1992_CENTRAL_X, bbox.min_y),
            (_PL1992_CENTRAL_X, bbox.max_y),
        ]

    points_4326 = [transformer.transform(x, y) for x, y in points_2180]

    return BBox(
        min_x=min(p[0] for p in points_4326),
        min_y=min(p[1] for p in points_4326),
        max_x=max(p[0] for p in points_4326),
        max_y=max(p[1] for p in points_4326),
        crs="EPSG:4326",
    )
```

- [ ] **Step 4: Zielono + pelna suita.** Jesli padaja istniejace testy z bboxem przecinajacym x = 500 000 (nowe arkusze na liscie), przeanalizuj kazdy przypadek: nowy arkusz musi faktycznie przecinac bbox (ta sama kontrola co w warunku sensownosci); zaktualizuj oczekiwania i opisz w raporcie.

- [ ] **Step 5: Dowod mutacyjny** — usun dopisywanie punktow poludnika: test FAIL; przywroc -> PASS.

- [ ] **Step 6: CHANGELOG** (`### Fixed`):

```markdown
- **Selekcja arkuszy gubila pas przy gornej krawedzi bboxa na poludniku 19°E.**
  Obwiednia WGS84 liczona z 4 naroznikow pomijala maksimum szerokosci
  geograficznej lezace na poludniku osiowym PUWG 1992; dla bboxa szerokiego na
  20 km pomijanych bylo 6 arkuszy przecinajacych bbox (pas ~63 m przy 50 km).
  Dotyczy `find_sheets_for_bbox`/`find_sheets_for_geometry` i wszystkich
  trybow `--bbox`/`--geometry`.
```

- [ ] **Step 7: Commit**

```bash
git add kartograf/core/sheet_parser.py tests/test_sheet_parser.py docs/CHANGELOG.md
git commit -m "fix(core): selekcja arkuszy uwzglednia poludnik osiowy przy gornej krawedzi bboxa"
```

---

### Zad. 6: `NoCoverageError` — brak danych u zrodla odrozniony od awarii (fundament R5)

Model: sonnet (review: sonnet). Zmienia sie klasyfikacja, nie kody wyjscia trybow bez wycinka (`NoCoverageError` jest `DownloadError`).

**Files:**
- Modify: `kartograf/exceptions.py` (nowa klasa po `DownloadError`), `kartograf/__init__.py` (eksport)
- Modify: `kartograf/providers/pl/gugik.py:542-575` (`_get_opendata_url`: fallback URL + koncowe `raise`)
- Modify: `kartograf/download/manager.py` (`DownloadResult`, `_download_single_sheet_task`, `_download_hierarchy_sequential`, `_download_hierarchy_parallel`)
- Test: `tests/test_gugik_provider.py` (klasa testow `_get_opendata_url`, ok. l. 455-540), `tests/test_download_manager.py`

**Interfaces:**
- Produces: `kartograf.exceptions.NoCoverageError(DownloadError)`; `GugikProvider._get_opendata_url` rzuca `NoCoverageError` WYLACZNIE gdy wszystkie warstwy skorowidza odpowiedzialy i zadna nie ma arkusza; gdy czesc warstw padla na transporcie, a reszta nie ma arkusza — zwykly `DownloadError` ("brak pokrycia niepewny"); `DownloadResult.no_coverage: list[str]` — podzbior `failed` (godla z `NoCoverageError`).

- [ ] **Step 1: Testy padajace.** W `tests/test_gugik_provider.py`:
  (a) w `test_get_opendata_url_not_found` dopisz `from kartograf.exceptions import NoCoverageError` i `assert isinstance(exc_info.value, NoCoverageError)`;
  (b) test `test_get_opendata_url_partial_transport_error_keeps_no_coverage_message` ZMIEN (swiadoma zmiana decyzji z audytu 619679d — przy R5 chwilowa awaria warstwy z danymi nie moze zamienic sie w trwala dziure nodata):

```python
    def test_get_opendata_url_partial_transport_error_is_not_no_coverage(
        self, mock_wms_response_no_url
    ):
        """Czesc warstw padla, reszta bez arkusza: brak pokrycia jest NIEPEWNY
        — to zwykly DownloadError, nie NoCoverageError (R5, plan 2026-09-28)."""
        from kartograf.exceptions import NoCoverageError

        session = Mock(spec=requests.Session)
        session.get = Mock(
            side_effect=[
                requests.HTTPError("500 Server Error"),
                mock_wms_response_no_url,
                mock_wms_response_no_url,
            ]
        )
        provider = GugikProvider(session=session)
        provider._validated_layers[("1m", "EVRF2007")] = ["L1", "L2", "L3"]

        with pytest.raises(DownloadError) as exc_info:
            provider._get_opendata_url("N-34-130-D-d-2-4")

        assert not isinstance(exc_info.value, NoCoverageError)
        assert "niepewny" in str(exc_info.value)
        assert "500" in str(exc_info.value)
```
  (c) nowy test ostrzezenia przy URL innego arkusza (fakt 7):

```python
    def test_fallback_url_of_other_sheet_warns(self, caplog):
        """Skorowidz zwrocil URL bez tego godla (np. arkusz PL-2000 nowszej
        kampanii) — plik trafi pod godlo PL-1992, wiec to musi byc widac."""
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.text = (
            '<html><script>var data = {url:"https://opendata.geoportal.gov.pl'
            '/NumDaneWys/NMT/99999/99999_1_6.179.12.20.asc"};</script></html>'
        )
        session = Mock(spec=requests.Session)
        session.get = Mock(return_value=response)
        provider = GugikProvider(session=session)
        provider._validated_layers[("1m", "EVRF2007")] = ["L1"]

        with caplog.at_level("WARNING"):
            url = provider._get_opendata_url("N-34-130-D-d-2-4")

        assert url.endswith("6.179.12.20.asc")
        assert "N-34-130-D-d-2-4" in caplog.text and "6.179.12.20" in caplog.text
```
  W `tests/test_download_manager.py` nowa klasa:

```python
class TestDownloadResultNoCoverage:
    """R5: brak danych u zrodla odrozniony od awarii pobrania."""

    @pytest.fixture
    def provider(self):
        from kartograf.exceptions import NoCoverageError

        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")

        def download(godlo, path, timeout=30):
            if godlo.endswith("-1"):
                raise NoCoverageError(f"No NMT 1m data available for {godlo}", godlo=godlo)
            if godlo.endswith("-2"):
                raise DownloadError(f"timeout {godlo}", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = download
        return provider

    @pytest.mark.parametrize("workers", [1, 4])
    def test_no_coverage_is_subset_of_failed(self, tmp_path, provider, workers):
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        manager.download_hierarchy("N-34-130-D-d-2", "1:10000", max_workers=workers)
        result = manager.last_result
        assert sorted(result.failed) == ["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"]
        assert result.no_coverage == ["N-34-130-D-d-2-1"]
        assert len(result.succeeded) == 2
```

- [ ] **Step 2: Uruchom — musza padac** (`ImportError: NoCoverageError`, brak `no_coverage`).

- [ ] **Step 3: Implementacja.**
  (a) `kartograf/exceptions.py`, po `DownloadError`:

```python
class NoCoverageError(DownloadError):
    """
    The source has no data for the requested sheet.

    Raised when every index (skorowidz) layer answered and none of them
    contains the sheet — a state of the data, not a transport failure:
    retrying will not help. Raster builders (PL cutout, ADR-027 addendum
    2026-09-28) treat it as nodata; every other DownloadError stays fatal.
    """
```
  (b) `kartograf/__init__.py`: import i `__all__` (`"NoCoverageError"` w sekcji Exceptions).
  (c) `kartograf/providers/pl/gugik.py` — fallback (l. ~550-553) zamiast `logger.debug(...)`:

```python
                    # Fallback: URL bez tego godla. Dla nowszych kampanii bywa to
                    # arkusz PL-2000 (inny zasieg i uklad), zapisywany pod godlem
                    # PL-1992 — wycinek --target-crs odrzuca taki arkusz glosno
                    # (plan 2026-09-28, fakt 7), lista arkuszy przyjmuje go bez zmian.
                    logger.warning(
                        f"{godlo}: skorowidz zwrocil URL innego arkusza ({urls[0]}) "
                        "— plik moze byc innym arkuszem, np. w ukladzie PL-2000"
                    )
```
  i koncowka funkcji (po petli, l. ~561-575):

```python
        if transport_errors == len(wms_layers):
            raise DownloadError(  # bez zmian: cala usluga niedostepna
                f"GUGiK WMS skorowidz unavailable for {godlo}: "
                f"all {transport_errors} layer queries failed "
                f"(last error: {last_error})",
                godlo=godlo,
            )

        if transport_errors:
            # Czesc warstw nie odpowiedziala — arkusz moze lezec wlasnie w nich.
            # To NIE jest brak pokrycia: wycinek potraktowalby go jako nodata
            # i chwilowa awaria zostawilaby trwala dziure (R5).
            raise DownloadError(
                f"GUGiK WMS skorowidz: {transport_errors} z {len(wms_layers)} "
                f"warstw nie odpowiedzialo dla {godlo}, pozostale nie maja "
                f"arkusza — brak pokrycia niepewny (ostatni blad: {last_error})",
                godlo=godlo,
            )

        raise NoCoverageError(
            f"No NMT {self._resolution} data available for {godlo} "
            f"(vertical_crs={self._vertical_crs}). "
            f"This area may not have {self._resolution} coverage in GUGiK. "
            f"Check https://mapy.geoportal.gov.pl for data availability.",
            godlo=godlo,
        )
```
  Docstring `Raises` funkcji: dopisz `NoCoverageError`. Import `NoCoverageError` z `kartograf.exceptions`.
  (d) `kartograf/download/manager.py`: import `NoCoverageError`; w `DownloadResult` pole `no_coverage: list[str] = field(default_factory=list)` + opis w docstringu ("subset of ``failed``: sheets the source has no data for (``NoCoverageError``)"); `total` bez zmian (`failed` juz je liczy).
  `_download_single_sheet_task` — przed `except DownloadError`:

```python
        except NoCoverageError as e:
            logger.warning(f"No data for {descendant_godlo}: {e}")
            return (descendant_godlo, None, "no_coverage", str(e))
```
  `_download_hierarchy_sequential` — przed istniejacym `except DownloadError as e:`:

```python
            except NoCoverageError as e:
                # R5: brak danych u zrodla — porazka listy, ale rozpoznawalna
                result.failed.append(current_godlo)
                result.no_coverage.append(current_godlo)
                logger.warning(f"No data for {current_godlo}: {e}")

                if on_progress:
                    on_progress(
                        DownloadProgress(
                            current=i,
                            total=total,
                            godlo=current_godlo,
                            status="failed",
                            message=str(e),
                        )
                    )
```
  `_download_hierarchy_parallel` — w sekcji pod lockiem zamiast `elif status == "failed": result.failed.append(current_godlo)`:

```python
                    elif status in ("failed", "no_coverage"):
                        result.failed.append(current_godlo)
                        if status == "no_coverage":
                            result.no_coverage.append(current_godlo)
```
  a w callbacku postepu zamiast `elif status == "failed":` — `elif status in ("failed", "no_coverage"):` (raportowany `status="failed"` z `message`; statusy `DownloadProgress` bez zmian).

- [ ] **Step 4: Zielono + pelna suita** (sprawdz testy CLI z komunikatem "may not have coverage" — tryby bez wycinka musza miec te same kody wyjscia).

- [ ] **Step 5: Dowody mutacyjne:** (1) koncowe `raise NoCoverageError` -> `raise DownloadError` — test (a) i test managera FAIL; (2) usun galaz `if transport_errors:` — test (b) FAIL; (3) w `_download_hierarchy_parallel` nie dopisuj do `no_coverage` — wariant `[4]` FAIL, a w sekwencyjnym — `[1]` FAIL (dwie osobne mutacje, bo to dwie sciezki); (4) przywroc `logger.debug` przy fallbacku — test (c) FAIL.

- [ ] **Step 6: CHANGELOG** — `### Added`: "`NoCoverageError(DownloadError)` — zrodlo nie ma danych dla arkusza (wszystkie warstwy skorowidza odpowiedzialy); `DownloadResult.no_coverage` — podzbior `failed`." `### Changed`: "Czesciowa awaria warstw skorowidza GUGiK przy braku arkusza w pozostalych to teraz 'brak pokrycia niepewny' (`DownloadError`), nie brak pokrycia; URL innego arkusza z fallbacku skorowidza loguje ostrzezenie (arkusze PL-2000 pod godlem PL-1992)."

- [ ] **Step 7: Commit**

```bash
git add kartograf/exceptions.py kartograf/__init__.py kartograf/providers/pl/gugik.py kartograf/download/manager.py tests/test_gugik_provider.py tests/test_download_manager.py docs/CHANGELOG.md
git commit -m "feat(download): NoCoverageError — brak danych GUGiK odrozniony od awarii pobrania"
```

---

### Zad. 7: `DownloadManager.expand_sheets()` + `download_sheets()` — lista arkuszy z porazkami w `last_result`

Model: sonnet (review: sonnet). Fundament biblioteki wycinka (Zad. 8, 10, 11): dzis jedyna lista-z-porazkami to prywatne CLI `_download_godlo_list`, ktore w trybie rownoleglym RZUCA pierwsza porazka (pozostale gina). Nowe metody uzywaja maszynerii hierarchii (postep, `DownloadResult` z `no_coverage` z Zad. 6). Tryby CLI bez wycinka NIE przechodza na nie w tej fali (poza zakresem).

**Files:**
- Modify: `kartograf/download/manager.py` (dwie nowe metody po `download_hierarchy`)
- Test: `tests/test_download_manager.py` (nowa klasa `TestDownloadManagerDownloadSheets`)

**Interfaces:**
- Produces: `DownloadManager.expand_sheets(godla: list[str]) -> list[str]` (staticmethod) — liscie: PL-1992 grubsze niz 1:10000 rozwiniete do 1:10000, reszta bez zmian; znormalizowane (`SheetParser(...).godlo`), bez duplikatow, kolejnosc pierwszego wystapienia; `ParseError` za niepoprawne godlo. `DownloadManager.download_sheets(godla: list[str], skip_existing: bool = True, on_progress: ProgressCallback | None = None, max_workers: int | None = None) -> list[Path]` — porazki NIGDY nie rzucaja: `last_result.failed` / `.no_coverage` / `.total` jak w `download_hierarchy`; `ParseError` PRZED jakimkolwiek pobraniem.

- [ ] **Step 1: Testy padajace** — do `tests/test_download_manager.py`:

```python
class TestDownloadManagerDownloadSheets:
    """download_sheets(): lista godel -> liscie 1:10000, porazki w last_result."""

    @pytest.fixture
    def provider(self):
        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")
        provider.calls = []
        provider.fail = set()

        def download(godlo, path, timeout=30):
            provider.calls.append(godlo)
            if godlo in provider.fail:
                raise DownloadError(f"blad {godlo}", godlo=godlo)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"data")
            return path

        provider.download = download
        return provider

    def test_expand_sheets_leaves_dedup_order(self):
        assert DownloadManager.expand_sheets(
            ["N-34-130-D-d-2-4", "N-34-130-D-d-2", "6.179.12.20"]
        ) == [
            "N-34-130-D-d-2-4", "N-34-130-D-d-2-1", "N-34-130-D-d-2-2",
            "N-34-130-D-d-2-3", "6.179.12.20",
        ]

    @pytest.mark.parametrize("workers", [1, 4])
    def test_expands_coarse_and_dedupes(self, tmp_path, provider, workers):
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        paths = manager.download_sheets(
            ["N-34-130-D-d-2", "N-34-130-D-d-2-4", "N-34-130-D-d-2-4"],
            max_workers=workers,
        )
        assert len(paths) == 4
        assert sorted(provider.calls) == [f"N-34-130-D-d-2-{i}" for i in (1, 2, 3, 4)]
        assert manager.last_result.total == 4 and manager.last_result.failed == []

    @pytest.mark.parametrize("workers", [1, 4])
    def test_failures_collected_not_raised(self, tmp_path, provider, workers):
        provider.fail = {"N-34-130-D-d-2-1", "N-34-130-D-d-2-3"}
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        paths = manager.download_sheets(["N-34-130-D-d-2"], max_workers=workers)
        assert len(paths) == 2
        assert sorted(manager.last_result.failed) == ["N-34-130-D-d-2-1", "N-34-130-D-d-2-3"]
        assert manager.last_result.total == 4

    def test_skip_existing(self, tmp_path, provider):
        existing = FileStorage(tmp_path).get_path("N-34-130-D-d-2-1", ".asc")
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"old")
        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        manager.download_sheets(["N-34-130-D-d-2-1", "N-34-130-D-d-2-2"])
        assert provider.calls == ["N-34-130-D-d-2-2"]
        assert manager.last_result.skipped == ["N-34-130-D-d-2-1"]

    def test_invalid_godlo_raises_before_any_download(self, tmp_path, provider):
        from kartograf.exceptions import ParseError

        manager = DownloadManager(output_dir=tmp_path, provider=provider)
        with pytest.raises(ParseError):
            manager.download_sheets(["N-34-130-D-d-2-1", "XYZ"])
        assert provider.calls == []
```

- [ ] **Step 2: Uruchom — musza padac** (`AttributeError`).

- [ ] **Step 3: Implementacja** — w `kartograf/download/manager.py` po `download_hierarchy`:

```python
    @staticmethod
    def expand_sheets(godla: list[str]) -> list[str]:
        """
        Leaf sheets actually requested from the provider for a list of godla.

        PL-1992 godla coarser than 1:10000 expand to their 1:10000
        descendants (like :meth:`download_sheet`); 1:10000 and PL-2000 godla
        stay as they are. Identifiers are normalized, duplicates dropped,
        first-seen order kept.

        Raises
        ------
        ParseError
            If any godlo is invalid
        """
        leaves: list[str] = []
        seen: set[str] = set()
        for godlo in godla:
            parser = SheetParser(godlo)
            if parser.uklad != "2000" and parser.scale != "1:10000":
                expanded = [d.godlo for d in parser.get_all_descendants("1:10000")]
            else:
                expanded = [parser.godlo]
            for leaf in expanded:
                if leaf not in seen:
                    seen.add(leaf)
                    leaves.append(leaf)
        return leaves

    def download_sheets(
        self,
        godla: list[str],
        skip_existing: bool = True,
        on_progress: ProgressCallback | None = None,
        max_workers: int | None = None,
    ) -> list[Path]:
        """
        Download a list of sheets (see :meth:`expand_sheets`) without raising.

        Unlike calling :meth:`download_sheet` in a loop, per-sheet failures
        never raise: they are collected in ``self.last_result`` exactly like
        in :meth:`download_hierarchy` (``failed``; ``no_coverage`` for sheets
        the source has no data for).

        Returns
        -------
        list[Path]
            Downloaded AND skipped (pre-existing) files

        Raises
        ------
        ParseError
            If any godlo is invalid — raised before any download starts
        """
        self.last_result = None
        leaves = [SheetParser(g) for g in self.expand_sheets(godla)]
        total = len(leaves)
        workers = max_workers if max_workers is not None else self._max_workers
        logger.info(f"Starting sheet list download: {total} sheets, workers={workers}")
        if workers <= 1:
            return self._download_hierarchy_sequential(
                leaves, total, skip_existing, on_progress
            )
        return self._download_hierarchy_parallel(
            leaves, total, skip_existing, on_progress, workers
        )
```

- [ ] **Step 4: Zielono + pelna suita.**

- [ ] **Step 5: Dowody mutacyjne:** (1) w `expand_sheets` dodawaj zawsze (bez `seen`) — dwa testy FAIL; (2) wywoluj `self.expand_sheets` dopiero po `self.last_result = None` ale leniwie w petli pobierania (tak, by `ParseError` padal po pierwszym pobraniu) — `test_invalid_godlo_raises_before_any_download` FAIL; (3) `_download_single_sheet_task`: `except DownloadError` -> `raise` — `test_failures_collected_not_raised[4]` FAIL.

- [ ] **Step 6: CHANGELOG** (`### Added`):

```markdown
- `DownloadManager.download_sheets(godla, ...)` i `DownloadManager.expand_sheets(godla)`
  — pobranie listy godel (grubsze PL-1992 rozwijane do 1:10000, duplikaty raz);
  porazki pojedynczych arkuszy zbierane w `last_result` (`failed`, `no_coverage`)
  zamiast przerywac cala liste.
```

- [ ] **Step 7: Commit**

```bash
git add kartograf/download/manager.py tests/test_download_manager.py docs/CHANGELOG.md
git commit -m "feat(download): DownloadManager.download_sheets/expand_sheets — lista arkuszy z porazkami w last_result"
```

---
### Zad. 8: Wycinek PL jako API biblioteki — `kartograf/download/cutout.py` (zn. 12, 13, 14; R3)

Model: **opus** (review: **opus**). Refaktor ZACHOWUJACY zachowanie (poza jednym zamierzonym wyjatkiem nizej): potok z `cli/download_cmd.py:929-1185` i blokow wycinka w `_download_pl_bbox` / `_download_pl_geometry` przechodzi do biblioteki; CLI wola ja przez jedna nakladke `_download_pl_cutout`. Znika duplikacja token-w-token (zn. 13), martwy guard `bbox is None` (zn. 13) i mylaca nazwa `bbox_2180` parametru cropu (zn. 14). Naprawy zachowania (siatka, tolerancja, rozmiar) przychodza w Zad. 9-11 — tu NIE.

Zamierzone zmiany zachowania (jedyne): (a) porazka arkusza w trybie wycinka konczy sie komunikatem z lista WSZYSTKICH nieudanych arkuszy (`download_sheets`), a nie pierwszym wyjatkiem z puli watkow — kod wyjscia bez zmian (1); (b) z wyjscia CLI znika posrednia linia "Building cutout from N sheets ..." i "Downloaded N files to ..." (pobranie i budowa to jedno wywolanie biblioteki; postep arkuszy pokazuje `on_progress`); (c) w trybie `--geometry` z `--target-crs` kolejnosc: przygotowanie wycinka -> skrot "plik istnieje" -> selekcja arkuszy (dotad selekcja geometrii szla pierwsza).

**Files:**
- Create: `kartograf/download/cutout.py`
- Modify: `kartograf/cli/download_cmd.py` (usun `_PL_NODATA`, `_PL_PIXEL_SIZES`, `_PL_WARP_MARGIN_PX`, `_PL_HORIZONTAL_POLICY`, `_PlCutout`, `_prepare_pl_cutout`, `_build_pl_cutout`, `_write_pl_cutout_sidecar`, `_finalize_pl_cutout`; dodaj `_download_pl_cutout`; przerob `_download_pl_bbox` i `_download_pl_geometry`; usun nieuzywane importy, m.in. `TransformPolicy`, `replace`, `dataclass`, jesli juz zbedne)
- Modify: `kartograf/cli/_parser.py:113-121` (`choices=list(SUPPORTED_TARGET_CRS)`), `kartograf/__init__.py` (eksport)
- Test: `tests/test_pl_cutout.py` (przepiecie + nowa klasa `TestLibraryApi`), `tests/test_cli.py` (przepiecie patchy wycinka, jesli sa)
- Docs: `docs/CHANGELOG.md`, `README.md`, `CLAUDE.md` (drzewo modulow)

**Interfaces (Produces — kolejne zadania na nich stoja):**
- `PlCutout` (frozen dataclass): `target_crs: str`, `resolution: str`, `vertical_crs: str` (faktyczny), `output_dir: Path`, `bbox_2180: BBox`, `bbox_source_2180: BBox`, `bbox_target: BBox`, `pinned: PinnedTransform | None`, `target_path: Path`; property `pixel_size -> float`.
- `PlCutoutSheets` (frozen): `godla: tuple[str, ...]`.
- `PlCutoutResult` (frozen): `path: Path`, `skipped: bool = False`, `sheet_paths: tuple[Path, ...] = ()`.
- `prepare_pl_cutout(bbox, target_crs, *, output_dir="./data", resolution="1m", vertical_crs="EVRF2007") -> PlCutout` — zero sieci; `TransformError` (brak operacji przypietej), `ValidationError` (parametry).
- `select_pl_cutout_sheets(cutout, *, geometry=None, layer=None, scale="1:10000") -> PlCutoutSheets` — zero sieci; pusta selekcja -> `ValidationError("No sheets found for the given bbox|geometry")`.
- `build_pl_cutout(sheet_paths, crop_bbox_2180, bbox_target, pixel_size, pinned, target_path) -> None`.
- `write_pl_cutout_sidecar(cutout, *, parent_request=None) -> None` (best-effort).
- `run_pl_cutout(cutout, sheets, *, provider=None, storage=None, max_workers=1, force=False, on_progress=None, parent_request=None) -> PlCutoutResult`.
- `download_pl_cutout(bbox, target_crs, *, output_dir="./data", resolution="1m", vertical_crs="EVRF2007", geometry=None, layer=None, scale="1:10000", max_workers=1, force=False, on_progress=None, parent_request=None) -> PlCutoutResult`.
- Stale: `PL_NODATA`, `PIXEL_SIZES`, `SUPPORTED_TARGET_CRS`, `WARP_MARGIN_PX`.
- CLI: `_download_pl_cutout(args, bbox, parent_request, geometry: Path | None = None) -> int`; `_download_pl_geometry(args, filepath, parent_request, bbox: BBox)` (bbox WYMAGANY).

- [ ] **Step 1: Modul biblioteczny** — utworz `kartograf/download/cutout.py`:

```python
"""
Scalony wycinek NMT PL w zadanym ukladzie (ADR-027) — warstwa biblioteczna.

Arkusze GUGiK pobierane sa normalnie do swoich segmentow (dzialaja jako
cache), mozaika jest przycinana do obszaru zadania (przy reprojekcji — z
zapasem), a dla ukladu innego niz EPSG:2180 tresc trafia na siatke wyniku
lokalnym warpem z WYMUSZONA operacja przypieta (ADR-024/027). Wynik to JEDEN
GeoTIFF ``<output_dir>/nmt/pl_1992_<res>_<vcrs>/bbox/<coords>.tif`` + sidecar.

CLI (``kartograf download --bbox/--geometry --target-crs``) jest nakladka na
ten modul: wypisuje komunikaty i tlumaczy wyjatki na kody wyjscia. Tu nie ma
``print`` ani argparse.

Przyklad::

    from kartograf import BBox, download_pl_cutout

    result = download_pl_cutout(
        BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
        "EPSG:5514",
        output_dir="./data",
        max_workers=4,
    )
    print(result.path)
"""

import logging
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path

from kartograf.core.sheet_parser import BBox, find_sheets_for_bbox
from kartograf.download.manager import DownloadManager, ProgressCallback
from kartograf.download.storage import FileStorage
from kartograf.exceptions import DownloadError, ValidationError
from kartograf.transform.crs import PinnedTransform, TransformPolicy

logger = logging.getLogger(__name__)

# nodata arkuszy ASC GUGiK
PL_NODATA = -9999.0
# piksel siatki wyniku per rozdzielczosc NMT PL
PIXEL_SIZES = {"1m": 1.0, "5m": 5.0}
# uklady docelowe z przypieta operacja EPSG:2180 -> cel (KNOWN_PATHS, ADR-027)
SUPPORTED_TARGET_CRS = ("EPSG:2180", "EPSG:5514", "EPSG:3045")
# Zapas obwiedni zrodla w pikselach — lustro _WARP_MARGIN_PX toru CZ
# (providers/cuzk/dmr.py): pokrywa niepewnosc operacji obwiedniowej i halo
# interpolatora bilinear (1 px) na krawedziach siatki wyniku.
WARP_MARGIN_PX = 4
# Polityka operacji reprojektujacej TRESC wycinka — lustro _HORIZONTAL_POLICY
# toru CZ; probe_point dokladany per zadanie (srodek bboxa).
_HORIZONTAL_POLICY = TransformPolicy(min_accuracy_m=1.0, allow_network_grids=False)
# uklady czeskie opuszczamy wylacznie przypieta operacja (ADR-024)
_CZ_CRS = frozenset({"EPSG:5514", "EPSG:3045"})
_VERTICAL_CRS = ("EVRF2007", "KRON86")


@dataclass(frozen=True)
class PlCutout:
    """Przygotowany (fail-fast, bez sieci) wycinek NMT PL."""

    target_crs: str
    resolution: str
    vertical_crs: str  # FAKTYCZNY pion (po regule 5m => EVRF2007)
    output_dir: Path
    bbox_2180: BBox  # dokladne zadanie w EPSG:2180
    bbox_source_2180: BBox  # zadanie + zapas na warp: selekcja arkuszy i crop mozaiki
    bbox_target: BBox  # siatka wyniku (uklad docelowy)
    pinned: PinnedTransform | None  # None dla EPSG:2180 (sam crop)
    target_path: Path

    @property
    def pixel_size(self) -> float:
        """Piksel siatki wyniku (m)."""
        return PIXEL_SIZES[self.resolution]


@dataclass(frozen=True)
class PlCutoutSheets:
    """Arkusze do pobrania dla wycinka (godla w skali selekcji)."""

    godla: tuple[str, ...]


@dataclass(frozen=True)
class PlCutoutResult:
    """Wynik ``run_pl_cutout`` / ``download_pl_cutout``."""

    path: Path
    skipped: bool = False  # plik juz istnial (force=False) — bez sieci
    sheet_paths: tuple[Path, ...] = ()  # arkusze uzyte do mozaiki


def _bbox_to_2180(bbox: BBox) -> BBox:
    """Zadanie w EPSG:2180: uklady czeskie przypieta operacja, reszta jak dotad.

    Uklady PL/WGS84 — swiadomie domyslny transformer, jak w calym przeplywie PL;
    CLI podaje tu juz bbox znormalizowany przez ``_country_bbox``.
    """
    if bbox.crs == "EPSG:2180":
        return bbox
    if bbox.crs in _CZ_CRS:
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        return bbox_to_crs(bbox, "EPSG:2180")
    from pyproj import CRS

    from kartograf.core.geometry import _transform_bbox

    return _transform_bbox(
        bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y,
        CRS.from_user_input(bbox.crs), "EPSG:2180",
    )


def prepare_pl_cutout(
    bbox: BBox,
    target_crs: str,
    *,
    output_dir: str | Path = "./data",
    resolution: str = "1m",
    vertical_crs: str = "EVRF2007",
) -> PlCutout:
    """Fail-fast przygotowanie wycinka: operacja, bboxy i sciezka wyniku.

    Zero sieci. ``TransformError``, gdy dla pary EPSG:2180 -> ``target_crs``
    nie ma przypietej operacji (ADR-024/027); ``ValidationError`` na zle
    parametry. ``vertical_crs`` to pion FAKTYCZNY: przy 5m tylko EVRF2007
    (``download_pl_cutout`` stosuje regule fabryki providera sam).

    Wycinek jest zawsze GeoTIFF (``.tif``) — ``default_extension``
    deskryptora (``.asc``) dotyczy arkuszy, nie wycinka.
    """
    if target_crs not in SUPPORTED_TARGET_CRS:
        raise ValidationError(
            f"Nieobslugiwany uklad docelowy wycinka PL: {target_crs} "
            f"(dostepne: {', '.join(SUPPORTED_TARGET_CRS)})"
        )
    if resolution not in PIXEL_SIZES:
        raise ValidationError(f"Rozdzielczosc NMT PL: 1m albo 5m (podano {resolution})")
    if vertical_crs not in _VERTICAL_CRS:
        raise ValidationError(f"Uklad wysokosci NMT PL: EVRF2007 albo KRON86 (podano {vertical_crs})")
    if resolution == "5m" and vertical_crs != "EVRF2007":
        raise ValidationError("NMT 5m jest dostepny wylacznie w EVRF2007")

    from kartograf.providers.cuzk.dmr import bbox_to_crs
    from kartograf.sources.registry import get_source

    # import lokalny: testy podmieniaja operacje w module transform.crs
    from kartograf.transform.crs import build_pinned_transform

    bbox_2180 = _bbox_to_2180(bbox)
    pinned = None
    bbox_target = bbox_2180
    bbox_source_2180 = bbox_2180
    if target_crs != "EPSG:2180":
        center = (
            (bbox_2180.min_x + bbox_2180.max_x) / 2,
            (bbox_2180.min_y + bbox_2180.max_y) / 2,
        )
        # polityka jak _HORIZONTAL_POLICY toru CZ + probe w srodku zadania
        pinned = build_pinned_transform(
            "EPSG:2180", target_crs, replace(_HORIZONTAL_POLICY, probe_point=center)
        )
        bbox_target = bbox_to_crs(bbox_2180, target_crs, pinned)
        # Zrodlo musi pokryc CALA siatke wyniku: obwiednia celu wraca do 2180
        # wieksza niz zadanie (obrot ukladu), a interpolator potrzebuje halo.
        # Lustro _native_request_bbox toru CZ. Bez `pinned` — operacja
        # przypieta jest KIERUNKOWA (2180 -> target), tak samo robi CZ.
        back = bbox_to_crs(bbox_target, "EPSG:2180")
        margin = WARP_MARGIN_PX * PIXEL_SIZES[resolution]
        bbox_source_2180 = BBox(
            back.min_x - margin, back.min_y - margin,
            back.max_x + margin, back.max_y + margin, "EPSG:2180",
        )

    key = "pl.gugik.nmt_5m" if resolution == "5m" else "pl.gugik.nmt_1m"
    subdir = get_source(key).resolve_subdir(uklad="1992", vertical_crs=vertical_crs)
    coords = "_".join(
        format(v, ".10g")
        for v in (bbox_target.min_x, bbox_target.min_y, bbox_target.max_x, bbox_target.max_y)
    )
    return PlCutout(
        target_crs=target_crs,
        resolution=resolution,
        vertical_crs=vertical_crs,
        output_dir=Path(output_dir),
        bbox_2180=bbox_2180,
        bbox_source_2180=bbox_source_2180,
        bbox_target=bbox_target,
        pinned=pinned,
        target_path=Path(output_dir) / subdir / "bbox" / f"{coords}.tif",
    )


def select_pl_cutout_sheets(
    cutout: PlCutout,
    *,
    geometry: str | Path | None = None,
    layer: str | None = None,
    scale: str = "1:10000",
) -> PlCutoutSheets:
    """Arkusze wycinka (zero sieci).

    Tryb bbox: arkusze obwiedni zrodla (zadanie + zapas). Tryb geometrii:
    arkusze per obiekt, a przy warpie SUMA z arkuszami obwiedni zrodla (R-01:
    wynik obejmuje CALA obwiednie, bez maskowania do obiektow — bez sumy na
    krawedziach zostawalaby ramka nodata; ARCHITECTURE 4.3).
    """
    if geometry is None:
        godla = find_sheets_for_bbox(cutout.bbox_source_2180, scale, system="1992")
        what = "bbox"
    else:
        from kartograf.core.geometry import find_sheets_for_geometry

        godla = find_sheets_for_geometry(
            Path(geometry), target_scale=scale, layer=layer, system="1992"
        )
        if cutout.pinned is not None:
            godla = sorted(
                set(godla)
                | set(find_sheets_for_bbox(cutout.bbox_source_2180, scale, system="1992"))
            )
        what = "geometry"
    if not godla:
        raise ValidationError(f"No sheets found for the given {what}")
    return PlCutoutSheets(godla=tuple(godla))


def build_pl_cutout(
    sheet_paths: list[Path],
    crop_bbox_2180: BBox,
    bbox_target: BBox,
    pixel_size: float,
    pinned: PinnedTransform | None,
    target_path: Path,
) -> None:
    """Zszyj arkusze, przytnij do ``crop_bbox_2180``; opcjonalny lokalny warp.

    ``crop_bbox_2180`` to obwiednia ZRODLA (przy warpie: zadanie + zapas),
    nie dokladne zadanie. Mozaika wymusza GTiff + EPSG:2180 (arkusze ASC nie
    niosa CRS). ``pinned is None`` = cel EPSG:2180: sam crop (atomowy
    ``os.replace``). Obie sciezki zapisu sa atomowe (druga domyka wewnetrzny
    ``os.replace`` w ``warp_to_grid``), wiec przerwana budowa NIE zostawia
    polzapisanego pliku pod ``target_path`` — i nie kasuje poprzedniego wyniku.
    """
    from kartograf.transport.mosaic import mosaic_and_crop

    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = target_path.with_name(
        f"{target_path.name}.{os.getpid()}_{threading.get_ident()}.mosaic.tif"
    )
    try:
        mosaic_and_crop(
            sheet_paths,
            crop_bbox_2180,
            tmp,
            nodata=PL_NODATA,
            dst_kwds={"driver": "GTiff", "crs": "EPSG:2180"},
        )
        if pinned is None:
            os.replace(tmp, target_path)
        else:
            from kartograf.transform.raster import warp_to_grid

            warp_to_grid(
                tmp, target_path, bbox_target, pixel_size, pinned,
                src_crs="EPSG:2180", nodata=PL_NODATA,
            )
    finally:
        tmp.unlink(missing_ok=True)


def write_pl_cutout_sidecar(cutout: PlCutout, *, parent_request: dict | None = None) -> None:
    """Best-effort sidecar wycinka (blad nie przerywa pobrania).

    ``capability="sheet_files"``: dane pochodza z arkuszy OpenData — kanal
    ``bbox_raster`` nie istnieje dla 5m, a dla 1m deklaruje wylacznie KRON86
    (ADR-027, odstepstwo od litery spec 6.1 pkt 5).
    """
    try:
        from kartograf.sources.registry import get_source
        from kartograf.sources.sidecar import build_metadata, write_sidecar

        key = "pl.gugik.nmt_5m" if cutout.resolution == "5m" else "pl.gugik.nmt_1m"
        b = cutout.bbox_target
        meta = build_metadata(
            get_source(key),
            request={"bbox": [b.min_x, b.min_y, b.max_x, b.max_y], "bbox_crs": cutout.target_crs},
            vertical_crs=cutout.vertical_crs,
            capability="sheet_files",
            nodata=PL_NODATA,
            extra={"parent_request": parent_request} if parent_request else None,
        )
        meta.horizontal_crs = cutout.target_crs
        meta.transform = (
            {"horizontal": f"pinned: {cutout.pinned.description} ({cutout.pinned.accuracy_m} m)"}
            if cutout.pinned is not None
            else None
        )
        write_sidecar(cutout.target_path, meta)
    except Exception as e:  # noqa: BLE001 — sidecar nigdy nie przerywa pobrania
        logger.warning(f"Nie udalo sie zapisac sidecara dla {cutout.target_path}: {e}")


def run_pl_cutout(
    cutout: PlCutout,
    sheets: PlCutoutSheets,
    *,
    provider=None,
    storage: FileStorage | None = None,
    max_workers: int = 1,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
    parent_request: dict | None = None,
) -> PlCutoutResult:
    """Pobierz arkusze, zbuduj wycinek, zapisz sidecar.

    ``force=False`` + istniejacy plik wyniku -> ``skipped=True`` bez sieci.
    Arkusze z cache sa uzywane ponownie (``skip_existing = not force``).
    Kazdy nieudany arkusz -> ``DownloadError`` z lista, zanim cokolwiek
    zostanie zbudowane. ``provider``/``storage`` domyslnie z fabryki NMT
    i ``FileStorage`` segmentu arkuszy (CLI wstrzykuje wlasne).
    """
    if not force and cutout.target_path.exists():
        return PlCutoutResult(path=cutout.target_path, skipped=True)
    if provider is None:
        from kartograf.providers.pl import create_nmt_provider

        provider = create_nmt_provider(
            vertical_crs=cutout.vertical_crs, resolution=cutout.resolution
        )
    if storage is None:
        storage = FileStorage(
            cutout.output_dir, resolution=cutout.resolution, vertical_crs=cutout.vertical_crs
        )
    manager = DownloadManager(
        output_dir=cutout.output_dir,
        provider=provider,
        storage=storage,
        vertical_crs=cutout.vertical_crs,
        resolution=cutout.resolution,
        max_workers=max_workers,
        sidecar_extra={"parent_request": parent_request} if parent_request else None,
    )
    sheet_paths = manager.download_sheets(
        list(sheets.godla), skip_existing=not force, on_progress=on_progress
    )
    summary = manager.last_result
    failed = list(summary.failed) if summary is not None else []
    if failed:
        total = summary.total if summary is not None else len(failed)
        raise DownloadError(
            f"{len(failed)} of {total} sheets failed: {', '.join(failed)} "
            "(wycinek wymaga kompletu arkuszy)"
        )
    build_pl_cutout(
        list(sheet_paths), cutout.bbox_source_2180, cutout.bbox_target,
        cutout.pixel_size, cutout.pinned, cutout.target_path,
    )
    write_pl_cutout_sidecar(cutout, parent_request=parent_request)
    return PlCutoutResult(path=cutout.target_path, sheet_paths=tuple(sheet_paths))


def download_pl_cutout(
    bbox: BBox,
    target_crs: str,
    *,
    output_dir: str | Path = "./data",
    resolution: str = "1m",
    vertical_crs: str = "EVRF2007",
    geometry: str | Path | None = None,
    layer: str | None = None,
    scale: str = "1:10000",
    max_workers: int = 1,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
    parent_request: dict | None = None,
) -> PlCutoutResult:
    """Jeden scalony GeoTIFF NMT PL w ``target_crs`` dla bboxa albo geometrii.

    Tryb geometrii: ``bbox`` to obwiednia geometrii (np.
    ``get_overall_bbox(path, target_crs="EPSG:2180")``), ``geometry`` — plik
    SHP/GPKG wyznaczajacy arkusze per obiekt (R-01 przy warpie). Regula
    fabryki NMT: 5m => EVRF2007 (z ostrzezeniem w logu).
    """
    if resolution not in PIXEL_SIZES:
        raise ValidationError(f"Rozdzielczosc NMT PL: 1m albo 5m (podano {resolution})")
    if vertical_crs not in _VERTICAL_CRS:
        raise ValidationError(f"Uklad wysokosci NMT PL: EVRF2007 albo KRON86 (podano {vertical_crs})")
    from kartograf.providers.pl import create_nmt_provider

    provider = create_nmt_provider(vertical_crs=vertical_crs, resolution=resolution)
    cutout = prepare_pl_cutout(
        bbox, target_crs, output_dir=output_dir, resolution=resolution,
        vertical_crs=provider.vertical_crs,
    )
    if not force and cutout.target_path.exists():
        return PlCutoutResult(path=cutout.target_path, skipped=True)
    sheets = select_pl_cutout_sheets(cutout, geometry=geometry, layer=layer, scale=scale)
    return run_pl_cutout(
        cutout, sheets, provider=provider, max_workers=max_workers, force=force,
        on_progress=on_progress, parent_request=parent_request,
    )
```

- [ ] **Step 2: CLI jako nakladka** — w `kartograf/cli/download_cmd.py`:
  (a) usun blok `# Wycinek PL --target-crs (ADR-027)` (stale + `_PlCutout` + `_prepare_pl_cutout` + `_build_pl_cutout` + `_write_pl_cutout_sidecar` + `_finalize_pl_cutout`) i wstaw w jego miejsce:

```python
def _download_pl_cutout(
    args: argparse.Namespace,
    bbox: BBox,
    parent_request: dict,
    geometry: Path | None = None,
) -> int:
    """Polski wycinek --target-crs (ADR-027): nakladka CLI na download/cutout.py.

    Wolane po ``_resolve_pl_sentinels``. Kazdy blad = kod 1 z komunikatem,
    nigdy traceback: wyjatek wyciekajacy poza petle krajow ``_dispatch_area``
    zlamalby kontrakt czesciowego sukcesu (ADR-023 pkt 4-5).
    """
    from kartograf.download.cutout import (
        prepare_pl_cutout,
        run_pl_cutout,
        select_pl_cutout_sheets,
    )
    from kartograf.transform.crs import TransformError

    output_dir = Path(args.output)
    provider, storage = _create_provider_and_storage(
        getattr(args, "product", "nmt"), output_dir, args.vertical_crs, args.resolution
    )
    try:
        # fail-fast: operacja przypieta budowana PRZED jakakolwiek siecia
        cutout = prepare_pl_cutout(
            bbox,
            args.target_crs,
            output_dir=output_dir,
            resolution=args.resolution,
            vertical_crs=getattr(provider, "vertical_crs", args.vertical_crs),
        )
    except TransformError as e:
        return _print_transform_error(e)
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if not args.force and cutout.target_path.exists():
        if not args.quiet:
            print(f"Skipped - already exists at {cutout.target_path}")
        return 0

    target_scale = args.scale or "1:10000"
    try:
        sheets = select_pl_cutout_sheets(
            cutout, geometry=geometry, layer=getattr(args, "layer", None), scale=target_scale
        )
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        what = "bbox" if geometry is None else f"geometry {geometry.name}"
        godla = list(sheets.godla)
        print(
            f"Found {len(godla)} sheets at {target_scale} "
            f"for {what} (resolution: {args.resolution})"
        )
        if len(godla) <= 10:
            print(f"  Sheets: {', '.join(godla)}")
        else:
            print(f"  Sheets: {', '.join(godla[:3] + ['...'] + godla[-2:])}")
        print()

    try:
        result = run_pl_cutout(
            cutout,
            sheets,
            provider=provider,
            storage=storage,
            max_workers=getattr(args, "workers", 4),
            force=args.force,
            on_progress=create_progress_callback(args.quiet),
            parent_request=parent_request,
        )
    except Exception as e:  # noqa: BLE001 — kod 1 zamiast tracebacku (ADR-023)
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"Downloaded to {result.path}")
    return 0
```
  (b) `_download_pl_bbox`: zaraz po `if _resolve_pl_sentinels(args): return 1` dodaj `if args.target_crs is not None: return _download_pl_cutout(args, bbox, parent_request)`; z reszty funkcji usun wszystko, co dotyczylo `cutout` (selekcja wprost z `bbox`, bez finalize). Docstring: zdanie o `--target-crs` -> "z `--target-crs` (ADR-027) — `_download_pl_cutout` (biblioteka `download/cutout.py`)".
  (c) `_download_pl_geometry(args, filepath, parent_request, bbox: BBox)` — `bbox` wymagany; po sentinelach `if args.target_crs is not None: return _download_pl_cutout(args, bbox, parent_request, geometry=filepath)`; usun martwy guard `if bbox is None: raise ValidationError(...)` i caly blok wycinka/R-01 (przeniesiony do `select_pl_cutout_sheets`). Docstring odpowiednio.
  (d) `kartograf/cli/_parser.py`: `from kartograf.download.cutout import SUPPORTED_TARGET_CRS` i `choices=list(SUPPORTED_TARGET_CRS)`.
  (e) `kartograf/__init__.py`: import z `kartograf.download.cutout` i `__all__` (nowa sekcja `# Download (wycinek PL, ADR-027)`): `PlCutout`, `PlCutoutResult`, `PlCutoutSheets`, `download_pl_cutout`, `prepare_pl_cutout`, `run_pl_cutout`, `select_pl_cutout_sheets`.

- [ ] **Step 3: Przepiecie testow** (zachowaj WSZYSTKIE asercje; zmieniaja sie tylko cele patchy/importy):
  - `tests/test_pl_cutout.py`: importy `_build_pl_cutout`, `_prepare_pl_cutout` -> `build_pl_cutout`, `prepare_pl_cutout` z `kartograf.download.cutout`; `_build_pl_cutout(` -> `build_pl_cutout(` (te same argumenty pozycyjne); `_prepare_pl_cutout(args, bbox, "EVRF2007")` -> `prepare_pl_cutout(bbox, args.target_crs, output_dir=args.output, resolution=args.resolution or "1m", vertical_crs="EVRF2007")`.
  - Na poziomie modulu, obok `_DL = "kartograf.cli.download_cmd"` (`tests/test_pl_cutout.py:271`), dodaj `_CUT = "kartograf.download.cutout"` — uzywaja go takze Zad. 9-11.
  - Harness `TestDownloadPlBboxCutout._run` (i analogiczne w `TestGeometryCutout`, `TestBorderTwoCutouts`): zamiast patchy `f"{_DL}.find_sheets_for_bbox"`, `f"{_DL}.DownloadManager"`, `f"{_DL}._download_godlo_list"`:

```python
    def _run(self, tmp_path, args, sheets, failed=(), provider=None):
        from kartograf.download.manager import DownloadResult

        provider = provider or SimpleNamespace(vertical_crs="EVRF2007")
        manager = Mock()
        manager.download_sheets.return_value = list(sheets)
        manager.last_result = DownloadResult(failed=list(failed))
        with (
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-1", "N-2"]) as find,
            patch(f"{_DL}._create_provider_and_storage", return_value=(provider, Mock())),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = _download_pl_bbox(args, _BBOX_2180, _PARENT)
        return rc, manager, find
```
    Asercje na starym `dl` (mock `_download_godlo_list`) tlumacz na `manager.download_sheets` (np. `dl.assert_not_called()` -> `manager.download_sheets.assert_not_called()`; lista godel z `call_args.args[1]` -> `call_args.args[0]`).
  - `test_unexpected_raster_error_returns_1`: patch `_build_pl_cutout` -> `f"{_CUT}.build_pl_cutout"`.
  - `tests/test_cli.py`: `grep -n "_build_pl_cutout\|_finalize_pl_cutout\|_prepare_pl_cutout\|_PlCutout\|_PL_NODATA\|_PL_PIXEL" tests/` — kazde trafienie przepnij analogicznie; testy trybow BEZ `--target-crs` zostaja bez zmian.

- [ ] **Step 4: Nowe testy API** — w `tests/test_pl_cutout.py`:

```python
class TestLibraryApi:
    """R3: wycinek PL jako API biblioteki (bez argparse)."""

    _SHEETS = {"N-34-130-D-d-2-3": (530000, 382000), "N-34-130-D-d-2-4": (530100, 382000)}

    def _provider(self):
        provider = Mock()
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "1m"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        provider.default_extension = ".asc"
        provider.calls = []

        def download(godlo, path, timeout=30):
            provider.calls.append(godlo)
            west, south = self._SHEETS[godlo]
            return _write_sheet_asc(path, west, south)

        provider.download = download
        return provider

    def test_download_pl_cutout_end_to_end_skip_and_force(self, tmp_path):
        from kartograf import download_pl_cutout

        provider = self._provider()
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        with (
            patch("kartograf.providers.pl.create_nmt_provider", return_value=provider),
            patch(
                "kartograf.download.cutout.find_sheets_for_bbox",
                return_value=list(self._SHEETS),
            ),
        ):
            first = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
            second = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path)
            third = download_pl_cutout(bbox, "EPSG:2180", output_dir=tmp_path, force=True)

        assert first.path.exists() and not first.skipped
        assert first.path.with_name(first.path.name + ".meta.json").exists()
        assert second.skipped and second.path == first.path
        assert not third.skipped
        assert sorted(provider.calls) == sorted(list(self._SHEETS) * 2)

    def test_public_exports(self):
        import kartograf

        for name in (
            "PlCutout", "PlCutoutResult", "PlCutoutSheets", "download_pl_cutout",
            "prepare_pl_cutout", "run_pl_cutout", "select_pl_cutout_sheets",
        ):
            assert name in kartograf.__all__ and hasattr(kartograf, name)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"target_crs": "EPSG:4326"},
            {"resolution": "2m"},
            {"resolution": "5m", "vertical_crs": "KRON86"},
            {"vertical_crs": "Bpv"},
        ],
    )
    def test_prepare_rejects_bad_params(self, tmp_path, kwargs):
        from kartograf.download.cutout import prepare_pl_cutout
        from kartograf.exceptions import ValidationError

        params = {"target_crs": "EPSG:2180", **kwargs}
        target = params.pop("target_crs")
        with pytest.raises(ValidationError):
            prepare_pl_cutout(_BBOX_2180, target, output_dir=tmp_path, **params)
```
  (Sprawdz nazwe sidecara na zywym `write_sidecar` — jesli to nie `<plik>.meta.json`, popraw asercje, nie kod.)

- [ ] **Step 5: Zielono + pelna suita + ruff + mypy** (`_download_pl_geometry` z wymaganym `bbox` — mypy pokaze wolajacych bez argumentu).

- [ ] **Step 6: Dowody mutacyjne** (kazda: FAIL -> przywroc -> PASS):
  1. `run_pl_cutout`: usun skrot `if not force and cutout.target_path.exists()` oraz w `download_pl_cutout` tez — `test_download_pl_cutout_end_to_end_skip_and_force` FAIL.
  2. `run_pl_cutout`: `skip_existing=not force` -> `skip_existing=force` — ten sam test FAIL (liczba pobran).
  3. `select_pl_cutout_sheets`: `cutout.bbox_source_2180` -> `cutout.bbox_2180` (w trybie bbox i w sumie R-01) — co najmniej jeden przepiety test selekcji z zapasem FAIL (np. asercja `sent.min_x < _BBOX_2180.min_x` w `test_geometry_target_5514_covers_whole_envelope`); zapisz, ktore — dowod, ze przepiete testy dalej gryza.
  4. CLI: pomin `parent_request=parent_request` w `run_pl_cutout(...)` — test sidecara z `parent_request` FAIL.

- [ ] **Step 7: Dokumentacja**
  - `docs/CHANGELOG.md` `### Added`:

```markdown
- **Wycinek PL jako API biblioteki** (`kartograf.download.cutout`, eksport
  w `kartograf`): `download_pl_cutout(bbox, target_crs, ...)` — jeden scalony
  GeoTIFF NMT PL (arkusze GUGiK -> mozaika -> lokalny warp przypieta
  operacja), oraz kroki `prepare_pl_cutout` (fail-fast, bez sieci) /
  `select_pl_cutout_sheets` / `run_pl_cutout` i typy `PlCutout`,
  `PlCutoutSheets`, `PlCutoutResult`. CLI `--target-crs` dla PL jest nakladka
  na te funkcje.
```
  - `README.md` — w podsekcji `#### Jako biblioteka Python` (`README.md:83`) dopisz na koncu bloku przykladow:

```python
# Scalony wycinek NMT PL w zadanym ukladzie (jeden GeoTIFF + sidecar)
from kartograf import BBox, download_pl_cutout

result = download_pl_cutout(
    BBox(530000, 382000, 533000, 386000, "EPSG:2180"),
    "EPSG:5514",
    output_dir="./data",
    max_workers=4,
)
print(result.path)
```
  - `CLAUDE.md` — w drzewie modulow pod `download/`: `│   ├── cutout.py         # Wycinek PL --target-crs jako API (ADR-027): prepare/select/run/download_pl_cutout`.

- [ ] **Step 8: Commit**

```bash
git add kartograf/download/cutout.py kartograf/cli/download_cmd.py kartograf/cli/_parser.py kartograf/__init__.py tests/test_pl_cutout.py tests/test_cli.py docs/CHANGELOG.md README.md CLAUDE.md
git commit -m "refactor(download): wycinek PL jako API biblioteki (download/cutout.py), CLI jako nakladka"
```

---
### Zad. 9: Wycinek PL na siatce arkuszy + normalizacja + glosny blad dla arkuszy PL-2000 (zn. 1 czesc B; R1; fakty 1-2, 5-7)

Model: **opus** (review: **opus**). Wlacza w torze PL mechanizmy z Zad. 3-4 i dodaje dwie ochrony.

**Files:**
- Modify: `kartograf/download/cutout.py` (`build_pl_cutout`, `select_pl_cutout_sheets`, nowy `_reject_pl2000_sheets`)
- Test: `tests/test_pl_cutout.py`
- Docs: `docs/CHANGELOG.md`, `CLAUDE.md` (punkt o `--target-crs` dla PL)

**Interfaces:**
- Consumes: `mosaic_and_crop(..., snap_to_source_grid=, assign_crs=, dtype=)` (Zad. 3-4).
- Produces: `build_pl_cutout` — mozaika na siatce arkuszy (wiekszosci), zrodla owiniete w VRT (EPSG:2180, Float32), wejscia posortowane; arkusz o `bounds.left >= 1_000_000` -> `ValidationError` z "PL-2000". `select_pl_cutout_sheets` — selekcja z obwiedni zrodla powiekszonej o 1 piksel (bbox i suma R-01).

- [ ] **Step 1: Testy padajace** — w `tests/test_pl_cutout.py` helper i testy:

```python
def _write_grid_sheet(path, col0, cols, rows, value, *, x0=529950.5, y_top=382150.5,
                      pixel=1.0, nodata_header="-9999.0", fmt="{:.4f}"):
    """Arkusz ASC na siatce jak u GUGiK: narozniki pikseli pol piksela od liczb
    calkowitych (fakt 1 planu 2026-09-28). value(xs, ys) -> wartosci (srodki pikseli)."""
    xs = x0 + (np.arange(cols) + col0 + 0.5) * pixel
    ys = y_top - (np.arange(rows) + 0.5) * pixel
    gx, gy = np.meshgrid(xs, ys)
    data = value(gx, gy)
    header = (
        f"ncols {cols}\nnrows {rows}\nxllcorner {x0 + col0 * pixel}\n"
        f"yllcorner {y_top - rows * pixel}\ncellsize {pixel}\n"
        f"nodata_value {nodata_header}\n"
    )
    body = "\n".join(" ".join(fmt.format(v) for v in row) for row in data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body + "\n", encoding="ascii")
    return path


def _ids(gx, gy):
    """Jednoznaczna wartosc per piksel globalnej siatki (x0 = 529950.5, y_top = 382150.5)."""
    return 1000.0 * np.floor(382150.5 - gy) + np.floor(gx - 529950.5)


def _erode(mask, n):
    """Erozja maski o n pikseli (4-sasiedztwo), bez scipy; brzegi rastra = False."""
    out = mask.copy()
    for _ in range(n):
        shrunk = out.copy()
        shrunk[1:, :] &= out[:-1, :]
        shrunk[:-1, :] &= out[1:, :]
        shrunk[:, 1:] &= out[:, :-1]
        shrunk[:, :-1] &= out[:, 1:]
        shrunk[0, :] = False
        shrunk[-1, :] = False
        shrunk[:, 0] = False
        shrunk[:, -1] = False
        out = shrunk
    return out


class TestSheetGrid:
    """Zn. 1 / R1: wycinek na siatce arkuszy, bez przesuniecia tresci."""

    def _sheets(self, tmp_path, value):
        a = _write_grid_sheet(tmp_path / "a.asc", 0, 160, 200, value)
        b = _write_grid_sheet(tmp_path / "b.asc", 150, 160, 200, value)  # zakladka 10 px
        return [a, b]

    @pytest.mark.parametrize(
        "bbox",
        [
            BBox(530010.37, 382010.61, 530150.29, 382085.43, "EPSG:2180"),
            BBox(530010, 382010, 530150, 382086, "EPSG:2180"),
        ],
        ids=["ulamkowy", "calkowity"],
    )
    def test_target_2180_on_sheet_grid_exact_values(self, tmp_path, bbox):
        from kartograf.download.cutout import build_pl_cutout

        sheets = self._sheets(tmp_path, _ids)
        target = tmp_path / "out.tif"
        build_pl_cutout(sheets, bbox, bbox, 1.0, None, target)
        with rasterio.open(target) as ds:
            t, data = ds.transform, ds.read(1)
            left, bottom, right, top = ds.bounds
        assert (t.c - 0.5) == pytest.approx(round(t.c - 0.5), abs=1e-6)
        assert (t.f - 0.5) == pytest.approx(round(t.f - 0.5), abs=1e-6)
        assert left <= bbox.min_x < left + 1 and right - 1 < bbox.max_x <= right
        assert bottom <= bbox.min_y < bottom + 1 and top - 1 < bbox.max_y <= top
        gx, gy = np.meshgrid(t.c + (np.arange(data.shape[1]) + 0.5), t.f - (np.arange(data.shape[0]) + 0.5))
        np.testing.assert_array_equal(data, _ids(gx, gy).astype("float32"))

    def test_target_5514_warp_has_no_subpixel_shift(self, tmp_path):
        """Rampa liniowa: bilinear odtwarza ja dokladnie, wiec kazde przesuniecie
        tresci wychodzi jako blad wartosci (nachylenia 0,3 i 0,7 m/m)."""
        from pyproj.enums import TransformDirection

        from kartograf.download.cutout import build_pl_cutout, prepare_pl_cutout

        def ramp(gx, gy):
            return 0.3 * (gx - 529950.0) + 0.7 * (gy - 381950.0)

        sheets = self._sheets(tmp_path, ramp)
        cut = prepare_pl_cutout(
            BBox(530010.37, 382010.61, 530150.29, 382085.43, "EPSG:2180"),
            "EPSG:5514", output_dir=tmp_path, resolution="1m", vertical_crs="EVRF2007",
        )
        build_pl_cutout(sheets, cut.bbox_source_2180, cut.bbox_target, 1.0, cut.pinned, cut.target_path)
        with rasterio.open(cut.target_path) as ds:
            t, data = ds.transform, ds.read(1)
        valid = data != _NODATA
        # pomin 2 px przy granicy danych (halo interpolatora)
        core = _erode(valid, 2)
        rows, cols = np.nonzero(core)
        xs, ys = t * (cols + 0.5, rows + 0.5)
        x2180, y2180 = cut.pinned._transformer.transform(xs, ys, direction=TransformDirection.INVERSE)
        err = np.abs(data[rows, cols] - ramp(np.asarray(x2180), np.asarray(y2180)))
        assert err.mean() < 0.02 and err.max() < 0.05, (err.mean(), err.max())
```
  **Step 1a — progi rampy:** `0.02`/`0.05` m: ZMIERZ blad przed naprawa (mutacja `snap_to_source_grid=False`) i po; oczekiwane przed ~0,1-0,5 m, po < 0,001 m. Jesli blad przed naprawa < 5x prog — zmien ulamkowe czesci bboxa tak, by przesuniecie cropu wzgledem siatki bylo bliskie 0,4 px (opisz w raporcie); jesli po naprawie blad > prog — STOP, zglos kontrolerowi.

```python
    def test_mixed_prj_cache_builds(self, tmp_path):
        """Fakt 6: arkusz z .prj (Hydrograf) obok arkusza bez .prj."""
        from pyproj import CRS

        from kartograf.download.cutout import build_pl_cutout

        sheets = self._sheets(tmp_path, _ids)
        sheets[0].with_suffix(".prj").write_text(CRS.from_epsg(2180).to_wkt("WKT1_GDAL"))
        bbox = BBox(530010, 382010, 530150, 382086, "EPSG:2180")
        build_pl_cutout(sheets, bbox, bbox, 1.0, None, tmp_path / "o.tif")
        with rasterio.open(tmp_path / "o.tif") as ds:
            assert not (ds.read(1) == _NODATA).any()

    def test_integer_first_sheet_keeps_decimals(self, tmp_path):
        """Fakt 5: pierwszy (po sortowaniu) arkusz z samymi liczbami calkowitymi."""
        from kartograf.download.cutout import build_pl_cutout

        a = _write_grid_sheet(tmp_path / "a.asc", 0, 160, 200, lambda gx, gy: gx * 0 + 100,
                              nodata_header="-9999", fmt="{:.0f}")
        b = _write_grid_sheet(tmp_path / "b.asc", 150, 160, 200, lambda gx, gy: gx * 0 + 100.25,
                              nodata_header="-9999")
        with rasterio.open(a) as ds:
            assert ds.dtypes[0] == "int32"  # warunek sensownosci
        bbox = BBox(530010, 382010, 530250, 382086, "EPSG:2180")
        build_pl_cutout([b, a], bbox, bbox, 1.0, None, tmp_path / "o.tif")
        with rasterio.open(tmp_path / "o.tif") as ds:
            assert ds.read(1)[0, -1] == pytest.approx(100.25)

    def test_pl2000_sheet_rejected_loudly(self, tmp_path):
        """Fakt 7: arkusz we wspolrzednych PL-2000 pod godlem PL-1992 — blad
        z opisem zamiast cichej dziury nodata."""
        from kartograf.download.cutout import build_pl_cutout
        from kartograf.exceptions import ValidationError

        good = _write_grid_sheet(tmp_path / "a.asc", 0, 160, 200, _ids)
        foreign = _write_grid_sheet(tmp_path / "b.asc", 0, 160, 200, _ids, x0=6500000.5)
        bbox = BBox(530010, 382010, 530150, 382086, "EPSG:2180")
        with pytest.raises(ValidationError, match="PL-2000"):
            build_pl_cutout([good, foreign], bbox, bbox, 1.0, None, tmp_path / "o.tif")
        assert not (tmp_path / "o.tif").exists()

    def test_selection_expanded_by_one_pixel(self, tmp_path):
        """Crop przyciagany na zewnatrz (< 1 px) — selekcja z zapasem 1 px,
        zeby brzegowy piksel nie wpadl w arkusz spoza listy."""
        from kartograf.download.cutout import prepare_pl_cutout, select_pl_cutout_sheets

        cut = prepare_pl_cutout(_BBOX_2180, "EPSG:2180", output_dir=tmp_path,
                                resolution="5m", vertical_crs="EVRF2007")
        with patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-34-130-D-d-2-4"]) as find:
            select_pl_cutout_sheets(cut)
        sent = find.call_args.args[0]
        src = cut.bbox_source_2180
        assert (sent.min_x, sent.min_y, sent.max_x, sent.max_y) == (
            src.min_x - 5.0, src.min_y - 5.0, src.max_x + 5.0, src.max_y + 5.0,
        )
```
  Oraz test CLI (w `TestDownloadPlBboxCutout`, harness `_run` z Zad. 8):

```python
    def test_pl2000_sheet_returns_1_with_reason(self, tmp_path, capsys):
        foreign = _write_grid_sheet(tmp_path / "b.asc", 0, 160, 200, _ids, x0=6500000.5)
        rc, *_ = self._run(tmp_path, _pl_args(tmp_path), [foreign])
        assert rc == 1
        assert "PL-2000" in capsys.readouterr().err
```

- [ ] **Step 2: Uruchom — musza padac** (przesuniecie / `CRS mismatch` / Int32 / brak bledu PL-2000 / selekcja bez zapasu).

- [ ] **Step 3: Implementacja** w `kartograf/download/cutout.py`:
  (a) nad `build_pl_cutout`:

```python
# x >= 1 000 000 m to wspolrzedne strefowe PL-2000 (strefa = cyfra milionow,
# EPSG:2176-2179 dla stref 5-8); PUWG 1992 miesci sie ponizej.
_PL2000_MIN_X = 1_000_000.0


def _reject_pl2000_sheets(sheet_paths: list[Path]) -> None:
    """Glosny blad zamiast cichej dziury (fakt 7 planu 2026-09-28).

    Skorowidz GUGiK potrafi zwrocic dla godla PL-1992 arkusz nowszej kampanii
    w ukladzie PL-2000 (fallback URL w ``GugikProvider._get_opendata_url``).
    Mozaika wymusza EPSG:2180, wiec taki arkusz wyladowalby poza obszarem
    i ``merge`` pominalby go bez slowa. Reprojekcja takich arkuszy to etap 2.
    """
    import rasterio

    foreign: list[tuple[Path, int]] = []
    for path in sheet_paths:
        with rasterio.open(path) as src:
            if src.bounds.left >= _PL2000_MIN_X:
                foreign.append((Path(path), int(src.bounds.left // 1_000_000)))
    if foreign:
        listing = ", ".join(
            f"{p.name} (strefa {zone}, EPSG:{2171 + zone})" for p, zone in foreign[:5]
        )
        raise ValidationError(
            f"{len(foreign)} arkusz(y) ma wspolrzedne PL-2000 zamiast PL-1992: "
            f"{listing}{' ...' if len(foreign) > 5 else ''} — skorowidz GUGiK "
            "wydal dla godla PL-1992 arkusz ukladu 2000 i wycinek pominalby go po "
            "cichu (dziura nodata). Wycinek z takich arkuszy to etap 2; pobierz "
            "obszar jako arkusze (bez --target-crs), np. z --system 2000."
        )
```
  (b) `build_pl_cutout`: na poczatku `_reject_pl2000_sheets(sheet_paths)`; wywolanie mozaiki:

```python
        mosaic_and_crop(
            sorted(Path(p) for p in sheet_paths),
            crop_bbox_2180,
            tmp,
            nodata=PL_NODATA,
            dst_kwds={"driver": "GTiff", "crs": "EPSG:2180"},
            # siatka arkuszy (R1), arkusze w VRT: EPSG:2180 + Float32 — fakty 1-2, 5-6
            snap_to_source_grid=True,
            assign_crs="EPSG:2180",
            dtype="float32",
        )
```
  Docstring `build_pl_cutout`: akapit o siatce arkuszy (EPSG:2180: obszar rozszerzony na zewnatrz < 1 px, wartosci 1:1), VRT, sortowaniu i odrzucaniu arkuszy PL-2000.
  (c) `select_pl_cutout_sheets`: selekcja (w obu miejscach — bbox i suma R-01) z obwiedni powiekszonej o `cutout.pixel_size`:

```python
    px = cutout.pixel_size
    src = cutout.bbox_source_2180
    # Crop przyciagany jest NA ZEWNATRZ do siatki arkuszy (< 1 px): selekcja
    # z zapasem 1 px, zeby brzegowy piksel nie wpadl w arkusz spoza listy.
    selection = BBox(src.min_x - px, src.min_y - px, src.max_x + px, src.max_y + px, "EPSG:2180")
```

- [ ] **Step 4: Zielono + pelna suita** (istniejace testy z arkuszami na siatce calkowitej i bboxem calkowitym musza przejsc bez zmian — tam przyciaganie jest no-opem).

- [ ] **Step 5: Dowody mutacyjne:** (1) `snap_to_source_grid=False` — oba warianty `test_target_2180_on_sheet_grid_exact_values` i `test_target_5514_warp_has_no_subpixel_shift` FAIL (zapisz zmierzony blad rampy przed/po); (2) `assign_crs=None` — `test_mixed_prj_cache_builds` FAIL; (3) `dtype=None` — `test_integer_first_sheet_keeps_decimals` FAIL; (4) usun wywolanie `_reject_pl2000_sheets` — oba testy PL-2000 FAIL; (5) selekcja z `cutout.bbox_source_2180` bez zapasu — `test_selection_expanded_by_one_pixel` FAIL.

- [ ] **Step 6: Dokumentacja**
  - `CHANGELOG` `### Fixed`:

```markdown
- **Wycinek PL przesuwal tresc o ulamek piksela** (review max, zn. 1): crop
  mozaiki kotwiczony w rogu zadania + kopiowanie najblizszym sasiadem. Arkusze
  GUGiK maja narozniki pikseli pol piksela od liczb calkowitych, wiec problem
  dotyczyl takze bboxow o CALKOWITYCH wspolrzednych (0,5 px = 2,5 m przy 5 m,
  z mieszaniem sasiednich kolumn). Crop jest teraz przyciagany do siatki
  arkuszy. **Wycinki zbudowane wczesniejsza wersja 0.7.0-dev przebuduj
  z `--force`** (maja te same nazwy plikow, wiec bez tego zostalyby pominiete
  jako istniejace).
- Mozaika wycinka PL: arkusz ASC z samymi liczbami calkowitymi zamienial cala
  mozaike w Int32 (obcinajac wysokosci pozostalych arkuszy), a arkusze z plikiem
  `.prj` (np. dopisanym przez Hydrograf) obok arkuszy bez niego konczyly sie
  `CRS mismatch`. Arkusze sa teraz owijane w VRT z jawnym EPSG:2180 i Float32.
```
    `### Changed`:

```markdown
- Wycinek `--target-crs EPSG:2180` lezy na siatce pikseli arkuszy GUGiK:
  obszar zadania rozszerzony na zewnatrz o < 1 px, wartosci 1:1 z arkuszy
  (bez przeprobkowania, `transform: null`); nazwa pliku niesie wspolrzedne
  zadania. Arkusz zapisany przez GUGiK w ukladzie PL-2000 pod godlem PL-1992
  konczy budowe wycinka bledem z opisem (dotad: cicha dziura nodata).
```
  - `CLAUDE.md` (punkt `--target-crs` dla PL): "`EPSG:2180` = sam crop (`transform: null`)" -> "`EPSG:2180` = sam crop na siatce arkuszy GUGiK (obszar rozszerzony na zewnatrz < 1 px, wartosci 1:1, `transform: null`)"; dopisz: "arkusz GUGiK we wspolrzednych PL-2000 (fallback skorowidza) = blad z opisem; wycinek z takich arkuszy to etap 2".

- [ ] **Step 7: Commit**

```bash
git add kartograf/download/cutout.py tests/test_pl_cutout.py docs/CHANGELOG.md CLAUDE.md
git commit -m "fix(download): wycinek PL na siatce arkuszy, arkusze w VRT (EPSG:2180/Float32), blad dla arkuszy PL-2000"
```

---
### Zad. 10: Arkusz bez danych GUGiK = nodata + ostrzezenie; awaria pobrania = blad (zn. 2; R5)

Model: **opus** (review: **opus**). Zastepuje "kazdy failed arkusz = blad calosci" (spec 6.1 pkt 1, ADR-027) — tylko w wycinku. Dzieki temu bbox przygraniczny `--country auto --target-crs` daje wycinek PL (strona czeska = nodata) obok wycinka CZ.

**Files:**
- Modify: `kartograf/download/cutout.py` (`PlCutoutResult`, `write_pl_cutout_sidecar`, `run_pl_cutout`)
- Modify: `kartograf/cli/download_cmd.py` (`_download_pl_cutout` — `Warning:`)
- Test: `tests/test_pl_cutout.py`
- Docs: `docs/CHANGELOG.md`, `CLAUDE.md`, `docs/DECISIONS.md` (uzupelnienie ADR-027)

**Interfaces:**
- Consumes: `DownloadResult.no_coverage` (Zad. 6), `download_sheets` (Zad. 7).
- Produces: `PlCutoutResult.missing_sheets: tuple[str, ...] = ()` (posortowane godla bez danych); `write_pl_cutout_sidecar(cutout, *, parent_request=None, missing_sheets=())` -> `extra.missing_sheets`; `run_pl_cutout` rzuca `DownloadError` TYLKO dla porazek spoza `no_coverage`, `ValidationError` gdy zaden arkusz nie ma danych.

- [ ] **Step 1: Testy padajace** — w `tests/test_pl_cutout.py`:

```python
class TestMissingSheets:
    """R5: brak danych GUGiK = nodata + ostrzezenie; awaria pobrania = blad."""

    def _provider(self, *, no_coverage=(), broken=()):
        from kartograf.exceptions import DownloadError, NoCoverageError

        provider = Mock()
        provider.vertical_crs = "EVRF2007"
        provider.resolution = "1m"
        provider.descriptor_key = "pl.gugik.nmt_1m"
        provider.default_extension = ".asc"

        def download(godlo, path, timeout=30):
            if godlo in no_coverage:
                raise NoCoverageError(f"No NMT 1m data available for {godlo}", godlo=godlo)
            if godlo in broken:
                raise DownloadError(f"timeout {godlo}", godlo=godlo)
            west, south = TestLibraryApi._SHEETS[godlo]
            return _write_sheet_asc(path, west, south)

        provider.download = download
        return provider

    def _cutout(self, tmp_path):
        from kartograf.download.cutout import PlCutoutSheets, prepare_pl_cutout

        cut = prepare_pl_cutout(
            BBox(530010, 382010, 530190, 382090, "EPSG:2180"), "EPSG:2180",
            output_dir=tmp_path,
        )
        return cut, PlCutoutSheets(godla=tuple(TestLibraryApi._SHEETS))

    def test_no_coverage_sheet_becomes_nodata_with_record(self, tmp_path):
        from kartograf.download.cutout import run_pl_cutout

        cut, sheets = self._cutout(tmp_path)
        result = run_pl_cutout(
            cut, sheets, provider=self._provider(no_coverage={"N-34-130-D-d-2-4"})
        )
        assert result.missing_sheets == ("N-34-130-D-d-2-4",)
        with rasterio.open(result.path) as ds:
            data = ds.read(1)
        assert (data[:, -50:] == _NODATA).all() and (data[:, :50] != _NODATA).all()
        meta = json.loads(result.path.with_name(result.path.name + ".meta.json").read_text())
        assert meta["extra"]["missing_sheets"] == ["N-34-130-D-d-2-4"]

    def test_transport_failure_stays_fatal(self, tmp_path):
        from kartograf.download.cutout import run_pl_cutout
        from kartograf.exceptions import DownloadError

        cut, sheets = self._cutout(tmp_path)
        with pytest.raises(DownloadError, match="N-34-130-D-d-2-4"):
            run_pl_cutout(cut, sheets, provider=self._provider(broken={"N-34-130-D-d-2-4"}))
        assert not cut.target_path.exists()

    def test_all_sheets_without_data_is_an_error(self, tmp_path):
        from kartograf.download.cutout import run_pl_cutout
        from kartograf.exceptions import ValidationError

        cut, sheets = self._cutout(tmp_path)
        with pytest.raises(ValidationError, match="nie ma danych"):
            run_pl_cutout(
                cut, sheets, provider=self._provider(no_coverage=set(TestLibraryApi._SHEETS))
            )
        assert not cut.target_path.exists()
```
  Harness CLI `_run` (Zad. 8) dostaje parametr `no_coverage=()` -> `DownloadResult(failed=list(failed), no_coverage=list(no_coverage))`; nowy test w `TestDownloadPlBboxCutout`:

```python
    def test_missing_sheet_warns_and_returns_0(self, tmp_path, capsys):
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, *_ = self._run(
            tmp_path, _pl_args(tmp_path), sheets, failed=["N-2"], no_coverage=["N-2"]
        )
        assert rc == 0
        err = capsys.readouterr().err
        assert "Warning:" in err and "N-2" in err
```
  (Istniejacy `test_failed_sheet_returns_1_and_no_cutout` — `failed=["N-2"]` bez `no_coverage` — ZOSTAJE: to awaria pobrania, kod 1.) Wariant pogranicza w `TestBorderTwoCutouts` (po przepieciu z Zad. 8 test `test_two_cutouts_share_parent_request` patchuje `f"{_CUT}.find_sheets_for_bbox"` i `f"{_CUT}.DownloadManager"`; ten sam uklad patchy):

```python
    def test_border_pl_sheet_without_data_still_gives_both_cutouts(self, tmp_path, capsys):
        """R5: strona czeska bboxa przygranicznego nie ma danych GUGiK —
        wycinek PL powstaje (nodata tam), wycinek CZ tez, kod 0."""
        from pyproj import CRS

        from kartograf.core.geometry import _transform_bbox
        from kartograf.download.manager import DownloadResult

        b = _transform_bbox(
            18.80, 49.70, 18.801, 49.7005, CRS.from_user_input("EPSG:4326"), "EPSG:2180"
        )
        sheet = _write_sheet_asc(
            tmp_path / "sheet.asc", b.min_x - 100, b.min_y - 100, size=60, pixel=5.0
        )
        manager = Mock()
        manager.download_sheets.return_value = [sheet]
        manager.last_result = DownloadResult(
            failed=["N-34-130-D-d-2-1"], no_coverage=["N-34-130-D-d-2-1"]
        )
        with (
            patch("kartograf.providers.cuzk.create_dmr_provider", return_value=self._cz_provider()),
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-34-130-D"]),
            patch(
                f"{_DL}._create_provider_and_storage",
                return_value=(SimpleNamespace(vertical_crs="EVRF2007"), Mock()),
            ),
            patch(f"{_CUT}.DownloadManager", return_value=manager),
        ):
            rc = main(
                ["download", "--bbox", self._BBOX, "--bbox-crs", "EPSG:4326",
                 "--resolution", "5m", "--target-crs", "EPSG:2180",
                 "--vertical-crs", "EVRF2007", "-o", str(tmp_path)]
            )

        assert rc == 0
        assert len(list((tmp_path / "nmt" / "pl_1992_5m_evrf2007" / "bbox").glob("*.tif"))) == 1
        assert len(list((tmp_path / "nmt" / "cz_dmr4g_evrf2007" / "bbox").glob("*.tif"))) == 1
        err = capsys.readouterr().err
        assert "Warning:" in err and "N-34-130-D-d-2-1" in err
```

- [ ] **Step 2: Uruchom — musza padac** (brak `missing_sheets`; `no_coverage` traktowane jak blad).

- [ ] **Step 3: Implementacja** w `kartograf/download/cutout.py`:
  (a) `PlCutoutResult`: pole `missing_sheets: tuple[str, ...] = ()  # arkusze bez danych GUGiK (R5) -> nodata`.
  (b) `write_pl_cutout_sidecar(cutout, *, parent_request=None, missing_sheets=())`:

```python
        extra: dict = {}
        if parent_request:
            extra["parent_request"] = parent_request
        if missing_sheets:
            # R5: arkusze, dla ktorych GUGiK nie ma danych — tam wycinek ma nodata
            extra["missing_sheets"] = list(missing_sheets)
```
    i `extra=extra or None` w `build_metadata(...)`.
  (c) `run_pl_cutout` — zamiast bloku `if failed: raise ...`:

```python
    summary = manager.last_result
    failed = list(summary.failed) if summary is not None else []
    no_data = set(summary.no_coverage) if summary is not None else set()
    fatal = [g for g in failed if g not in no_data]
    missing = tuple(sorted(g for g in failed if g in no_data))
    if fatal:
        # R5: tylko brak danych u zrodla bywa nodata. Kazda inna porazka
        # (siec, serwer, niepelna odpowiedz skorowidza) konczy zadanie — chwilowy
        # blad nie moze zostawic trwalej dziury w pliku, ktory potem jest
        # pomijany jako istniejacy.
        total = summary.total if summary is not None else len(failed)
        raise DownloadError(
            f"{len(fatal)} z {total} arkuszy nie pobrano (blad pobrania, nie brak "
            f"danych): {', '.join(fatal)} — wycinek nie powstal; ponow pobranie"
        )
    if not sheet_paths:
        raise ValidationError(
            f"GUGiK nie ma danych dla zadnego z {len(missing)} arkuszy obszaru "
            "— wycinek nie powstal"
        )
    if missing:
        # info, nie warning: komunikat dla uzytkownika wypisuje CLI, a dane
        # niesie wynik (missing_sheets) i sidecar
        logger.info(f"Brak danych GUGiK dla {len(missing)} arkuszy wycinka: {', '.join(missing)}")
```
    dalej `build_pl_cutout(...)`, `write_pl_cutout_sidecar(cutout, parent_request=parent_request, missing_sheets=missing)` i `return PlCutoutResult(path=..., sheet_paths=tuple(sheet_paths), missing_sheets=missing)`.
  (d) `kartograf/cli/download_cmd.py::_download_pl_cutout` — po udanym `run_pl_cutout`, przed "Downloaded to":

```python
    if result.missing_sheets:
        shown = ", ".join(result.missing_sheets[:10])
        more = " ..." if len(result.missing_sheets) > 10 else ""
        print(
            f"Warning: GUGiK nie ma danych dla {len(result.missing_sheets)} arkuszy "
            f"wycinka ({shown}{more}) — w tych miejscach wycinek ma nodata "
            "(lista w sidecarze: extra.missing_sheets)",
            file=sys.stderr,
        )
```

- [ ] **Step 4: Zielono + pelna suita.**

- [ ] **Step 5: Dowody mutacyjne:** (1) `fatal = failed` — `test_no_coverage_sheet_becomes_nodata_with_record` i `test_missing_sheet_warns_and_returns_0` FAIL; (2) `fatal = []` — `test_transport_failure_stays_fatal` FAIL; (3) usun wpis `missing_sheets` do sidecara — asercja sidecara FAIL; (4) usun `Warning:` w CLI — test CLI FAIL; (5) usun `if not sheet_paths` — `test_all_sheets_without_data_is_an_error` FAIL (albo inny blad — opisz, jaki).

- [ ] **Step 6: Dokumentacja**
  - `CLAUDE.md` (punkt `--target-crs` dla PL): "failed arkusz = kod 1" -> "arkusz bez danych GUGiK (`NoCoverageError`: morze, strona czeska bboxa przygranicznego, dziury pokrycia) = nodata + `Warning:` + `extra.missing_sheets` w sidecarze; kazda inna porazka pobrania = kod 1 (R5, 2026-09-28)".
  - `docs/DECISIONS.md`, na koncu ADR-027 nowy akapit:

```markdown
**Uzupelnienie 2026-09-28 (R5, review max zn. 2):** arkusz, dla ktorego GUGiK
nie ma danych (`NoCoverageError` — wszystkie warstwy skorowidza odpowiedzialy
i zadna nie ma arkusza), nie wetuje wycinka: w jego miejscu jest nodata,
CLI wypisuje `Warning:`, a sidecar niesie `extra.missing_sheets`. Kazda inna
porazka pobrania (siec, serwer, czesciowa awaria skorowidza) nadal konczy
zadanie kodem 1 — chwilowy blad nie moze zostawic trwalej dziury w pliku,
ktory potem jest pomijany jako istniejacy. Zastepuje "kazdy failed arkusz =
blad calosci" (spec 6.1 pkt 1). Powod: bbox przygraniczny zawsze obejmuje
arkusze po stronie czeskiej, ktorych GUGiK nie ma — dotad `--country auto
--target-crs` na granicy nie dawal wycinka PL w ogole.
```
  - `CHANGELOG` `### Changed`: "Wycinek PL: arkusz bez danych GUGiK (`NoCoverageError`) daje nodata + `Warning:` + `extra.missing_sheets` w sidecarze zamiast kodu 1; awarie pobrania nadal koncza sie kodem 1. Na pograniczu `--country auto --target-crs` powstaje teraz takze wycinek PL."

- [ ] **Step 7: Commit**

```bash
git add kartograf/download/cutout.py kartograf/cli/download_cmd.py tests/test_pl_cutout.py docs/CHANGELOG.md CLAUDE.md docs/DECISIONS.md
git commit -m "feat(download): arkusz bez danych GUGiK = nodata + ostrzezenie w wycinku PL (R5)"
```

---

### Zad. 11: Rozmiar wycinka — kompresja pliku posredniego, kontrola miejsca na dysku, `Info:` (zn. 9)

Model: sonnet (review: sonnet).

**Files:**
- Modify: `kartograf/download/cutout.py` (`PlCutout.grid_shape`/`estimated_bytes`, `estimate_pl_cutout_bytes`, `check_pl_cutout_disk_space`, `build_pl_cutout`, `run_pl_cutout`)
- Modify: `kartograf/cli/download_cmd.py` (`_download_pl_cutout` — `Info:`)
- Test: `tests/test_pl_cutout.py`
- Docs: `docs/CHANGELOG.md`

**Interfaces:**
- Produces: `PlCutout.grid_shape -> tuple[int, int]` (wysokosc, szerokosc — jak `warp_to_grid`: `max(1, round(bok / px))`); `PlCutout.estimated_bytes -> int` (float32 bez kompresji); `estimate_pl_cutout_bytes(cutout, sheets, *, storage=None) -> tuple[int, int]` (bajty, liczba arkuszy do pobrania); `check_pl_cutout_disk_space(cutout, sheets, *, storage=None) -> None` (`ValidationError`); `run_pl_cutout` wola kontrole PRZED pobraniem.

- [ ] **Step 1: Testy padajace:**

```python
class TestCutoutSize:
    """Zn. 9: bez twardego limitu, ale bez odkrywania pelnego dysku po godzinach."""

    def test_disk_check_blocks_before_download(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "shutil.disk_usage", lambda path: SimpleNamespace(total=0, used=0, free=0)
        )
        sheets = [_write_sheet_asc(tmp_path / "s1.asc", 530000, 382000)]
        rc, manager, _ = TestDownloadPlBboxCutout()._run(tmp_path, _pl_args(tmp_path), sheets)
        assert rc == 1
        assert "Za malo miejsca" in capsys.readouterr().err
        manager.download_sheets.assert_not_called()

    def test_estimate_counts_only_pending_sheets(self, tmp_path):
        from kartograf.download.cutout import (
            PlCutoutSheets, estimate_pl_cutout_bytes, prepare_pl_cutout,
        )
        from kartograf.download.storage import FileStorage

        cut = prepare_pl_cutout(_BBOX_2180, "EPSG:2180", output_dir=tmp_path)
        sheets = PlCutoutSheets(godla=("N-34-130-D-d-2-3", "N-34-130-D-d-2-4"))
        storage = FileStorage(tmp_path, resolution="1m", vertical_crs="EVRF2007")
        both, pending_both = estimate_pl_cutout_bytes(cut, sheets, storage=storage)
        cached = storage.get_path("N-34-130-D-d-2-3", ".asc")
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(b"x")
        one, pending_one = estimate_pl_cutout_bytes(cut, sheets, storage=storage)
        assert (pending_both, pending_one) == (2, 1)
        assert cut.estimated_bytes < one < both

    def test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe(self, tmp_path):
        from kartograf.download.cutout import build_pl_cutout
        from kartograf.transport import mosaic as mosaic_mod

        west = _write_sheet_asc(tmp_path / "w.asc", 530000, 382000, apex=_APEX)
        east = _write_sheet_asc(tmp_path / "e.asc", 530100, 382000, apex=_APEX)
        bbox = BBox(530010, 382010, 530190, 382090, "EPSG:2180")
        pinned = _pinned_2180_to("EPSG:5514")
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        with patch.object(mosaic_mod, "mosaic_and_crop", wraps=mosaic_mod.mosaic_and_crop) as spy:
            build_pl_cutout([west, east], bbox, bbox_to_crs(bbox, "EPSG:5514", pinned),
                            1.0, pinned, tmp_path / "w.tif")
            build_pl_cutout([west, east], bbox, bbox, 1.0, None, tmp_path / "c.tif")
        warp_kwds = spy.call_args_list[0].kwargs["dst_kwds"]
        crop_kwds = spy.call_args_list[1].kwargs["dst_kwds"]
        assert warp_kwds["compress"] == "deflate" and warp_kwds["predictor"] == 3
        assert warp_kwds["tiled"] is True and warp_kwds["blockxsize"] == 512
        assert warp_kwds["bigtiff"] == "IF_SAFER"
        assert "compress" not in crop_kwds  # EPSG:2180: plik posredni JEST wynikiem

    def test_large_grid_prints_info(self, tmp_path, capsys):
        from kartograf.download.cutout import PlCutoutResult

        args = _pl_args(tmp_path, bbox="400000,300000,440000,330000")  # 40 x 30 km @ 1 m
        big = BBox(400000, 300000, 440000, 330000, "EPSG:2180")
        with (
            patch(f"{_CUT}.find_sheets_for_bbox", return_value=["N-1"]),
            patch(f"{_DL}._create_provider_and_storage",
                  return_value=(SimpleNamespace(vertical_crs="EVRF2007"), Mock())),
            patch(f"{_CUT}.run_pl_cutout",
                  return_value=PlCutoutResult(path=tmp_path / "x.tif")),
        ):
            rc = _download_pl_bbox(args, big, _PARENT)
        assert rc == 0
        err = capsys.readouterr().err
        assert "Info:" in err and "GiB" in err
```
  (Uwaga: `_download_pl_cutout` importuje `run_pl_cutout` lokalnie z `kartograf.download.cutout`, wiec patch `f"{_CUT}.run_pl_cutout"` dziala. Jesli `TestDownloadPlBboxCutout()._run` nie da sie wywolac poza klasa, przenies test do tej klasy.)

- [ ] **Step 2: Uruchom — musza padac.**

- [ ] **Step 3: Implementacja** w `kartograf/download/cutout.py`:
  (a) stala i wlasciwosci:

```python
# Dolne oszacowanie rozmiaru arkusza ASC na dysku: 5,74-7,95 B na wartosc
# w realnych plikach GUGiK 5 m (fakt 9 planu 2026-09-28) — bierzemy mniej,
# zeby kontrola nie odrzucala zadan, ktore sie zmieszcza.
_ASC_BYTES_PER_VALUE = 5.5
```
  w `PlCutout`:

```python
    @property
    def grid_shape(self) -> tuple[int, int]:
        """(wysokosc, szerokosc) siatki wyniku w pikselach — jak w ``warp_to_grid``."""
        b, px = self.bbox_target, self.pixel_size
        return (
            max(1, round((b.max_y - b.min_y) / px)),
            max(1, round((b.max_x - b.min_x) / px)),
        )

    @property
    def estimated_bytes(self) -> int:
        """Rozmiar wyniku float32 bez kompresji (bajty)."""
        height, width = self.grid_shape
        return height * width * 4
```
  (b) funkcje (przed `run_pl_cutout`):

```python
def estimate_pl_cutout_bytes(
    cutout: PlCutout, sheets: PlCutoutSheets, *, storage: FileStorage | None = None
) -> tuple[int, int]:
    """(bajty, liczba arkuszy do pobrania) — DOLNE oszacowanie potrzeb dysku.

    Wynik float32 bez kompresji + arkusze jeszcze nie pobrane po 5,5 B na
    wartosc. Plik posredni mozaiki (skompresowany) i narzut systemu plikow NIE
    sa liczone: to kontrola "na pewno nie wystarczy", nie gwarancja.
    """
    from kartograf.core.sheet_parser import SheetParser

    storage = storage or FileStorage(
        cutout.output_dir, resolution=cutout.resolution, vertical_crs=cutout.vertical_crs
    )
    px = cutout.pixel_size
    need = cutout.estimated_bytes
    pending = 0
    for leaf in DownloadManager.expand_sheets(list(sheets.godla)):
        if storage.get_path(leaf, ".asc").exists():
            continue
        pending += 1
        frame = SheetParser(leaf).get_bbox("EPSG:2180")
        need += int(
            (frame.max_x - frame.min_x) * (frame.max_y - frame.min_y)
            / (px * px) * _ASC_BYTES_PER_VALUE
        )
    return need, pending


def check_pl_cutout_disk_space(
    cutout: PlCutout, sheets: PlCutoutSheets, *, storage: FileStorage | None = None
) -> None:
    """``ValidationError``, gdy na dysku NA PEWNO zabraknie miejsca (przed siecia)."""
    import shutil

    need, pending = estimate_pl_cutout_bytes(cutout, sheets, storage=storage)
    probe = cutout.target_path.parent
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    if free < need:
        height, width = cutout.grid_shape
        raise ValidationError(
            f"Za malo miejsca na dysku dla wycinka: potrzeba co najmniej "
            f"~{need / 2**30:.1f} GiB (siatka {width} x {height} px float32 + "
            f"{pending} arkuszy do pobrania), wolne ~{free / 2**30:.1f} GiB w {probe}"
        )
```
  (c) `run_pl_cutout`: po ustaleniu `storage`, przed `DownloadManager(...)`: `check_pl_cutout_disk_space(cutout, sheets, storage=storage)`.
  (d) `build_pl_cutout`: zamiast stalego `dst_kwds=...`:

```python
    dst_kwds: dict = {"driver": "GTiff", "crs": "EPSG:2180"}
    if pinned is not None:
        # Plik POSREDNI (warp czyta go raz i kasuje): deflate + predyktor
        # zmiennoprzecinkowy daje 2-3x mniej dla NMT. Kafle 512 px — profil
        # AAIGrid ma blockysize=1, a tiled bez rozmiarow konczy sie
        # RasterBlockError; BIGTIFF=IF_SAFER, bo przy kompresji GDAL nie zna
        # rozmiaru z gory (fakt 10 planu 2026-09-28).
        dst_kwds.update(
            compress="deflate", predictor=3, tiled=True,
            blockxsize=512, blockysize=512, bigtiff="IF_SAFER",
        )
```
  (e) CLI `_download_pl_cutout` — po bloku "Found N sheets", przed `run_pl_cutout`:

```python
    if cutout.estimated_bytes >= 2**30:
        height, width = cutout.grid_shape
        print(
            f"Info: wycinek ~{cutout.estimated_bytes / 2**30:.1f} GiB "
            f"({width} x {height} px float32)",
            file=sys.stderr,
        )
```

- [ ] **Step 4: Zielono + pelna suita.** Uwaga: w harnessie CLI `DownloadManager` jest MagicMockiem, wiec `DownloadManager.expand_sheets(...)` zwraca pusty iterator — kontrola liczy wtedy sam wynik; to zamierzone (testy CLI nie parsuja fikcyjnych godel "N-1").

- [ ] **Step 5: Dowody mutacyjne:** (1) usun wywolanie `check_pl_cutout_disk_space` — `test_disk_check_blocks_before_download` FAIL; (2) licz takze arkusze z cache — `test_estimate_counts_only_pending_sheets` FAIL; (3) usun `dst_kwds.update(...)` — `test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe` FAIL; (4) usun `Info:` — `test_large_grid_prints_info` FAIL. (Bloki 512 zostaja jawnie: po Zad. 9 profil pierwszego zrodla to VRT, wiec `RasterBlockError` z faktu 10 moze sie juz nie pojawic — zmierz i zapisz w raporcie, ale nie jest to wymagany dowod.)

- [ ] **Step 6: CHANGELOG** (`### Changed`): "Wycinek PL: plik posredni mozaiki przy warpie jest kompresowany (deflate, kafle 512 px, BigTIFF gdy trzeba); przed pobraniem kontrola miejsca na dysku (dolne oszacowanie: wynik + arkusze do pobrania) i `Info:` dla wycinkow >= 1 GiB. Twardego limitu rozmiaru nie ma."

- [ ] **Step 7: Commit**

```bash
git add kartograf/download/cutout.py kartograf/cli/download_cmd.py tests/test_pl_cutout.py docs/CHANGELOG.md
git commit -m "feat(download): wycinek PL — kompresja pliku posredniego, kontrola miejsca na dysku, Info dla duzych siatek"
```

---

### Zad. 12: Obwiednia geometrii w ukladzie czeskim przez operacje przypieta (zn. 4)

Model: sonnet (review: sonnet).

**Files:**
- Modify: `kartograf/cli/download_cmd.py` (`_cmd_download_geometry`, nowy `_geometry_envelope` obok `_resolve_cz_geometry_bbox`)
- Test: `tests/test_cli.py` (obok testow geometrii CZ, ok. l. 3650-3760; helper `_write_krovak_shp` z l. ~3406)

**Interfaces:**
- Produces: `_geometry_envelope(filepath: Path, layer: str | None) -> BBox` — plik w EPSG:5514/3045: obwiednia w ukladzie PLIKU z etykieta `"EPSG:5514"`/`"EPSG:3045"` (skok do 2180 zrobi przypieta operacja w `_country_bbox:311`); inny uklad — jak dotad `get_overall_bbox(..., target_crs="EPSG:2180")`.

- [ ] **Step 1: Test padajacy** — w `tests/test_cli.py`, w klasie z testami geometrii CZ (helper `_write_krovak_shp(directory)` z l. ~3406 zwraca sciezke `.shp` w EPSG:5514; `main` z `kartograf.cli.commands`, jak w calym pliku):

```python
    def test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl(self, tmp_path):
        """Zn. 4 review max: plik geometrii w EPSG:5514 z --country pl — obwiednia
        PL powstaje przypieta operacja (jak --bbox w ukladzie czeskim), nie
        domyslnym transformerem z core/geometry (~1,2 m roznicy)."""
        from kartograf.providers.cuzk.dmr import bbox_to_crs

        shp = _write_krovak_shp(tmp_path)
        captured = {}

        def fake_pl_geometry(args, filepath, parent_request, bbox):
            captured.update(bbox=bbox, parent=parent_request)
            return 0

        with patch(
            "kartograf.cli.download_cmd._download_pl_geometry", side_effect=fake_pl_geometry
        ):
            rc = main(
                ["download", "--geometry", str(shp), "--country", "pl",
                 "-o", str(tmp_path / "out")]
            )

        assert rc == 0
        expected = bbox_to_crs(
            BBox(-447000, -1114000, -446000, -1113000, "EPSG:5514"), "EPSG:2180"
        )
        got = captured["bbox"]
        assert got.crs == "EPSG:2180"
        assert (got.min_x, got.min_y, got.max_x, got.max_y) == pytest.approx(
            (expected.min_x, expected.min_y, expected.max_x, expected.max_y), abs=1e-6
        )
        assert captured["parent"]["bbox_crs"] == "EPSG:5514"
```
  Warunek sensownosci (do raportu): zmierz roznice miedzy `expected` a `get_overall_bbox(shp, target_crs="EPSG:2180")` — musi byc > 0,01 m, inaczej test nie odroznia sciezek (wtedy powieksz geometrie/przesun ja i opisz).

- [ ] **Step 2: Uruchom — musi padac.**

- [ ] **Step 3: Implementacja** — w `kartograf/cli/download_cmd.py` obok `_resolve_cz_geometry_bbox`:

```python
def _geometry_envelope(filepath: Path, layer: str | None) -> BBox:
    """Obwiednia geometrii dla dyspozycji krajow (``--country auto``/``pl``).

    Plik w ukladzie czeskim (EPSG:5514/3045): obwiednia W UKLADZIE PLIKU
    z etykieta KODU EPSG — skok do EPSG:2180 wykona przypieta operacja
    w ``_country_bbox`` (review max 2026-08-30, zn. 4: domyslny transformer
    z ``core/geometry`` przesuwal siatke wyniku o ~1,2 m). Etykieta WKT by nie
    wystarczyla: ``wkid()`` jej nie rozpoznaje i skok przypiety zostalby
    pominiety. Pozostale uklady — jak dotad, wprost do EPSG:2180.
    """
    from kartograf.core.geometry import get_overall_bbox, read_source_crs

    source_crs = read_source_crs(filepath, layer=layer)
    epsg = source_crs.to_epsg()
    if epsg is not None and str(epsg) in _CZ_CRS_WKIDS:
        # obwiednia w ukladzie pliku (tozsamosc — zero transformacji)
        env = get_overall_bbox(filepath, layer=layer, target_crs=source_crs.to_wkt())
        return BBox(env.min_x, env.min_y, env.max_x, env.max_y, f"EPSG:{epsg}")
    return get_overall_bbox(filepath, layer=layer, target_crs="EPSG:2180")
```
  W `_cmd_download_geometry` zamien `overall = get_overall_bbox(filepath, layer=..., target_crs="EPSG:2180")` na `overall = _geometry_envelope(filepath, getattr(args, "layer", None))` (ten sam `try/except ValidationError`); docstring funkcji: zdanie o obwiedni w ukladzie pliku dla CRS czeskich. Nieuzywany import `get_overall_bbox` w tej funkcji usun.

- [ ] **Step 4: Zielono + pelna suita** (szczegolnie testy `--country auto` z geometria i testy `parent_request`: dla pliku w ukladzie czeskim `parent_request.bbox_crs` to teraz uklad pliku — jesli jakis test zakladal EPSG:2180, oceń, czy to zalozenie bylo zamierzone, i opisz w raporcie).

- [ ] **Step 5: Dowod mutacyjny** — `_geometry_envelope` zawsze zwraca `get_overall_bbox(..., "EPSG:2180")`: test FAIL; przywroc -> PASS.

- [ ] **Step 6: CHANGELOG** (`### Fixed`): "Plik geometrii w ukladzie czeskim (EPSG:5514/3045) z `--country pl|auto`: obwiednia opuszcza Krovaka przypieta operacja (jak `--bbox`), nie domyslnym transformerem — dotad siatka i nazwa wycinka PL byly przesuniete o ~1,2 m (review max, zn. 4). `parent_request.bbox_crs` niesie wtedy uklad pliku."

- [ ] **Step 7: Commit**

```bash
git add kartograf/cli/download_cmd.py tests/test_cli.py docs/CHANGELOG.md
git commit -m "fix(cli): obwiednia geometrii w ukladzie czeskim opuszcza Krovaka przypieta operacja"
```

---

### Zad. 13: Porazka nie zostawia pustego drzewa `<segment>/bbox/` (zn. 10)

Model: sonnet (review: sonnet).

**Files:**
- Modify: `kartograf/download/storage.py` (nowa funkcja modulu `prune_empty_dirs`)
- Modify: `kartograf/cli/download_cmd.py` (`_cz_download_bbox`, ok. l. 1722-1728)
- Modify: `kartograf/download/cutout.py` (`run_pl_cutout`: budowa w `try`)
- Test: `tests/test_storage.py`, `tests/test_cli.py` (`test_bbox_download_error_returns_1`, ok. l. 3325), `tests/test_pl_cutout.py`

**Interfaces:**
- Produces: `prune_empty_dirs(start: Path, stop: Path) -> None` — usuwa `start` i kolejnych rodzicow, dopoki sa puste; nigdy `stop` ani nic poza nim.

- [ ] **Step 1: Testy padajace.** `tests/test_storage.py`:

```python
class TestPruneEmptyDirs:
    def test_removes_empty_chain_but_not_stop(self, tmp_path):
        from kartograf.download.storage import prune_empty_dirs

        leaf = tmp_path / "nmt" / "cz_dmr5g_bpv" / "bbox"
        leaf.mkdir(parents=True)
        prune_empty_dirs(leaf, tmp_path)
        assert not (tmp_path / "nmt").exists() and tmp_path.exists()

    def test_stops_at_non_empty_parent(self, tmp_path):
        from kartograf.download.storage import prune_empty_dirs

        leaf = tmp_path / "nmt" / "seg" / "bbox"
        leaf.mkdir(parents=True)
        (tmp_path / "nmt" / "seg" / "arkusz.asc").write_text("x")
        prune_empty_dirs(leaf, tmp_path)
        assert not leaf.exists() and (tmp_path / "nmt" / "seg").exists()

    def test_never_touches_outside_stop(self, tmp_path):
        from kartograf.download.storage import prune_empty_dirs

        outside = tmp_path / "a" / "b"
        outside.mkdir(parents=True)
        prune_empty_dirs(outside, tmp_path / "other")
        assert outside.exists()
```
  `tests/test_cli.py::test_bbox_download_error_returns_1` — dopisz `assert not (tmp_path / "nmt").exists()` (lustro testu godlowego z l. ~3206). `tests/test_pl_cutout.py`:

```python
    def test_failed_build_leaves_no_empty_bbox_dir(self, tmp_path):
        """Zn. 10: nieudana budowa bez poprzedniego wyniku nie zostawia pustego bbox/."""
        from kartograf.download.cutout import run_pl_cutout

        cut, sheets = TestMissingSheets()._cutout(tmp_path)
        with patch("kartograf.transport.mosaic.mosaic_and_crop", side_effect=RuntimeError("zepsuty arkusz")):
            with pytest.raises(RuntimeError):
                run_pl_cutout(cut, sheets, provider=TestMissingSheets()._provider())
        assert not cut.target_path.parent.exists()
        assert cut.target_path.parent.parent.exists()  # segment z arkuszami zostaje
```

- [ ] **Step 2: Uruchom — musza padac.**

- [ ] **Step 3: Implementacja.**
  (a) `kartograf/download/storage.py` (funkcja modulu, po klasie):

```python
def prune_empty_dirs(start: Path, stop: Path) -> None:
    """
    Remove ``start`` and its parents while they are empty — never ``stop``.

    Used after a failed download/build: the target directory is created before
    writing, and a failure must not leave empty ``<segment>/bbox/`` trees behind
    (review max 2026-08-30, finding 10). Directories outside ``stop`` are never
    touched.
    """
    stop = Path(stop).resolve()
    current = Path(start).resolve()
    while current != stop and stop in current.parents:
        try:
            current.rmdir()  # succeeds only when empty
        except OSError:
            return
        current = current.parent
```
  (b) `_cz_download_bbox` (tor CLI, providery CZ bez zmian):

```python
    # provider tworzy katalogi dopiero przy fetchu — sidecar wymaga ich zawsze
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        provider.download_bbox(bbox, target)
    except (DownloadError, ValidationError) as e:
        # zn. 10: porazka nie zostawia pustego drzewa <segment>/bbox/
        prune_empty_dirs(target.parent, Path(args.output))
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except BaseException:
        prune_empty_dirs(target.parent, Path(args.output))
        raise
```
    (import `prune_empty_dirs` lokalnie z `kartograf.download.storage`).
  (c) `run_pl_cutout` — wywolanie `build_pl_cutout(...)` w:

```python
    try:
        build_pl_cutout(...)
    except BaseException:
        # zn. 10: nieudana budowa nie zostawia pustego drzewa <segment>/bbox/
        # (katalog z poprzednim wynikiem nie jest pusty — zostaje)
        prune_empty_dirs(cutout.target_path.parent, cutout.output_dir)
        raise
```

- [ ] **Step 4: Zielono + pelna suita** (`test_failed_build_keeps_previous_result` dalej zielony: katalog z poprzednim plikiem nie jest pusty).

- [ ] **Step 5: Dowody mutacyjne:** (1) usun `prune_empty_dirs` w `_cz_download_bbox` — test CLI FAIL; (2) usun `try/except` w `run_pl_cutout` — `test_failed_build_leaves_no_empty_bbox_dir` FAIL; (3) w `prune_empty_dirs` warunek `while stop in current.parents or current == stop:` — `test_removes_empty_chain_but_not_stop` FAIL (usuwa `stop`).

- [ ] **Step 6: CHANGELOG** (`### Fixed`): "Nieudany wycinek CZ (bbox) i nieudana budowa wycinka PL nie zostawiaja pustych katalogow `<segment>/bbox/` (review max, zn. 10)."

- [ ] **Step 7: Commit**

```bash
git add kartograf/download/storage.py kartograf/cli/download_cmd.py kartograf/download/cutout.py tests/test_storage.py tests/test_cli.py tests/test_pl_cutout.py docs/CHANGELOG.md
git commit -m "fix(download): porazka wycinka nie zostawia pustych katalogow bbox/"
```

---
### Zad. 14: `resolve_subdir` odrzuca pusty wymiar (zn. 7)

Model: sonnet (review: sonnet).

**Files:**
- Modify: `kartograf/sources/descriptor.py:83-101`
- Test: `tests/test_sources_registry.py` (klasa `TestResolveSubdir`, ok. l. 384), `tests/test_download_manager.py` (klasa `TestDownloadManagerStorageFromDescriptor`, ok. l. 128)

**Interfaces:**
- Produces: `SourceDescriptor.resolve_subdir(uklad="" | vertical_crs="")` -> `ValidationError("Pusty wymiar segmentu storage ...")`; `None` nadal = "wypelnij pozniej".

- [ ] **Step 1: Testy padajace:**

```python
    @pytest.mark.parametrize(
        "kwargs", [{"vertical_crs": ""}, {"vertical_crs": "  "}, {"uklad": ""}]
    )
    def test_empty_dimension_raises(self, kwargs):
        """Zn. 7: pusty string to blad wolajacego, nie brak wymiaru — dotad
        dawal cichy segment `nmt/pl_{uklad}_1m_` (FileStorage zamyka te sama
        pulapke falsy-checkiem)."""
        from kartograf.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Pusty wymiar"):
            get_source("pl.gugik.nmt_1m").resolve_subdir(**kwargs)
```
  (w `TestResolveSubdir`; dopasuj sposob pobrania deskryptora do tej klasy) oraz w `tests/test_download_manager.py`:

```python
    def test_provider_with_empty_vertical_crs_raises(self, tmp_path):
        """Zn. 7 przez publiczne API: wlasny provider z vertical_crs=''."""
        from kartograf.exceptions import ValidationError

        provider = Mock(spec=GugikProvider)
        type(provider).default_extension = PropertyMock(return_value=".asc")
        provider.vertical_crs = ""
        provider.descriptor_key = "pl.gugik.nmt_1m"
        with pytest.raises(ValidationError, match="Pusty wymiar"):
            DownloadManager(output_dir=tmp_path, provider=provider)
```

- [ ] **Step 2: Uruchom — musza padac.**

- [ ] **Step 3: Implementacja** — `kartograf/sources/descriptor.py`: import `from kartograf.exceptions import ValidationError`; w `resolve_subdir` po kontroli `storage_subdir is None`:

```python
        for name, value in (("uklad", uklad), ("vcrs", vertical_crs)):
            if value is not None and not value.strip():
                # Pusty string to blad wolajacego, nie "brak wymiaru" (to None):
                # replace("{vcrs}", "") dawal cichy segment `nmt/pl_1992_1m_`
                # (review max 2026-08-30, zn. 7; lustro falsy-checku FileStorage).
                raise ValidationError(
                    f"Pusty wymiar segmentu storage '{name}' (zrodlo '{self.key}') "
                    "— podaj wartosc albo None"
                )
```
  Docstring: zdanie o pustym stringu.

- [ ] **Step 4: Zielono + pelna suita.**

- [ ] **Step 5: Dowod mutacyjny** — usun petle: oba testy FAIL; przywroc -> PASS.

- [ ] **Step 6: CHANGELOG** (`### Fixed`): "`SourceDescriptor.resolve_subdir(vertical_crs='')` (takze przez `DownloadManager` z providerem o pustym `vertical_crs`) konczy sie `ValidationError` zamiast cichego segmentu `nmt/pl_1992_1m_` (review max, zn. 7)."

- [ ] **Step 7: Commit**

```bash
git add kartograf/sources/descriptor.py tests/test_sources_registry.py tests/test_download_manager.py docs/CHANGELOG.md
git commit -m "fix(sources): resolve_subdir odrzuca pusty wymiar segmentu"
```

---

### Zad. 15: Uklad kafla LAZ — jedno zrodlo prawdy dla CLI i biblioteki (zn. 8)

Model: sonnet (review: sonnet).

**Files:**
- Modify: `kartograf/providers/pl/gugik_laz.py` (`LazTile.uklad`)
- Modify: `kartograf/download/storage.py` (`get_raw_path(..., uklad=)`, `_resolved_subdir(identifier, uklad=None)`)
- Modify: `kartograf/cli/download_cmd.py` (`_cmd_download_laz`: jeden `FileStorage(product="laz")` + `uklad=tile.uklad`; usun `_laz_uklad`)
- Test: `tests/test_gugik_laz.py` (nowa klasa `TestLazTileUklad` = przeniesione przypadki z `tests/test_cli.py::TestLazUklad`, l. ~2461-2513 — te usun), `tests/test_storage.py`, `tests/test_cli.py`
- Docs: `CLAUDE.md:112-114`, `docs/ARCHITECTURE.md` sekcja 3.1 (wiersz `{uklad}` jawnie), `docs/CHANGELOG.md`

**Interfaces:**
- Produces: `LazTile.uklad -> str` ("1992" | "2000"; kaskada: `crs` (`uklad_xy`) -> format godla -> "2000" z ostrzezeniem); `FileStorage.get_raw_path(identifier, filename, *, uklad: str | None = None)` — `uklad` podany wypelnia `{uklad}` (dozwolone "1992"/"2000", inaczej `ValidationError`), `None` = wykrycie z identyfikatora jak dotad.

- [ ] **Step 1: Testy padajace.** `tests/test_gugik_laz.py::TestLazTileUklad` — te same szesc przypadkow co `TestLazUklad` (crs PL-2000 wygrywa z godlem myslnikowym; `PL-1992`; `crs=None` + godlo z kropkami; `crs=None` + godlo myslnikowe; nierozpoznany `crs` -> format godla; wszystko zawodzi -> "2000" + ostrzezenie z godlem w logu), wolane jako `LazTile(...).uklad` (konstruktor jak w istniejacych testach tego pliku). `tests/test_storage.py`:

```python
    def test_laz_uklad_from_tile_overrides_identifier(self, tmp_path):
        """Zn. 8: kafel PL-2000:S6 z godlem myslnikowym laduje w pl_2000 takze
        przez API biblioteki (dotad biblioteka dawala pl_1992, a CLI pl_2000)."""
        storage = FileStorage(tmp_path, product="laz")
        path = storage.get_raw_path("N-33-131-B-a-1-1-4", "a.laz", uklad="2000")
        assert tuple(path.parts[-10:-8]) == ("laz", "pl_2000_evrf2007")

    def test_laz_unknown_uklad_rejected(self, tmp_path):
        with pytest.raises(ValidationError):
            FileStorage(tmp_path, product="laz").get_raw_path("N-33-131-B-a-1-1-4", "a.laz", uklad="1965")
```
  `tests/test_cli.py` — w testach sciezek LAZ (`TestCmdDownloadLaz`) dodaj asercje spojnosci: dla kafla z fixtury (`uklad_xy` `PL-2000:S6`, godlo myslnikowe) plik trafia DOKLADNIE tam, gdzie `FileStorage(out, product="laz", vertical_crs=...).get_raw_path(tile.godlo, tile.filename, uklad=tile.uklad)`.

- [ ] **Step 2: Uruchom — musza padac.**

- [ ] **Step 3: Implementacja.**
  (a) `LazTile` (docstringi pliku po angielsku):

```python
    @property
    def uklad(self) -> str:
        """Horizontal system of the tile for the storage segment: "1992" or "2000".

        Single source of truth for the CLI and the library (review max
        2026-08-30, finding 8). Cascade: (1) ``crs`` (``uklad_xy``:
        ``"PL-2000:*"`` / ``"PL-1992*"``); (2) godlo format (dots = 2000,
        dashes = 1992); (3) ``"2000"`` with a warning — current GUGiK tiles are
        cut in PL-2000.
        """
        crs = (self.crs or "").strip()
        if crs.startswith("PL-2000"):
            return "2000"
        if crs.startswith("PL-1992"):
            return "1992"
        if "." in self.godlo:
            return "2000"
        if "-" in self.godlo:
            return "1992"
        logger.warning(
            f"Kafel {self.godlo}: nierozpoznany uklad_xy '{self.crs}' — przyjmuje 2000"
        )
        return "2000"
```
    (sprawdz, czy modul ma `logger`; jesli nie — `logger = logging.getLogger(__name__)`).
  (b) `FileStorage`:

```python
    def _resolved_subdir(self, identifier: str, uklad: str | None = None) -> str:
        """Segment for the identifier: {uklad} given explicitly or from the sheet system."""
        subdir = self._subdir
        if "{uklad}" in subdir:
            if uklad is None:
                system = parser_registry.detect_system(identifier)
                uklad = "2000" if system is not None and system.id == "pl2000" else "1992"
            subdir = subdir.replace("{uklad}", uklad)
        return self._ensure_resolved(subdir)
```
    `get_raw_path(self, identifier, filename, *, uklad=None)`: `if uklad is not None and uklad not in ("1992", "2000"): raise ValidationError(...)`; `self._resolved_subdir(identifier, uklad)`. Docstring: parametr `uklad` ("for LAZ tiles pass ``tile.uklad`` — the tile's ``uklad_xy`` decides, not the godlo format") i przyklad `storage.get_raw_path(tile.godlo, tile.filename, uklad=tile.uklad)`.
  (c) `_cmd_download_laz`: zamiast slownika `storages` i `_storage_for` — jeden `storage = FileStorage(output_dir, product="laz", vertical_crs=vertical_crs)` i `target = storage.get_raw_path(tile.godlo, tile.filename, uklad=tile.uklad)`; usun `_laz_uklad`.

- [ ] **Step 4: Zielono + pelna suita.**

- [ ] **Step 5: Dowody mutacyjne:** (1) `get_raw_path` ignoruje `uklad` — `test_laz_uklad_from_tile_overrides_identifier` i asercja spojnosci CLI FAIL; (2) CLI bez `uklad=tile.uklad` — asercja spojnosci FAIL; (3) w `LazTile.uklad` sprawdzaj format godla PRZED `crs` — `TestLazTileUklad` FAIL.

- [ ] **Step 6: Dokumentacja** — `CLAUDE.md:112-114`: po "(`pl_1992` vs `pl_2000` rozstrzyga format godla KAZDEGO pliku" dopisz "; wyjatek: kafle LAZ — `uklad_xy` kafla (`LazTile.uklad`)"; `docs/ARCHITECTURE.md` 3.1, wiersz `{uklad}` (jawnie): `_laz_uklad(tile)` -> `LazTile.uklad` przez `FileStorage.get_raw_path(..., uklad=)`; `CHANGELOG` `### Added`: "`LazTile.uklad` i `FileStorage.get_raw_path(..., uklad=)` — biblioteka zapisuje kafle LAZ w tym samym segmencie co CLI (dotad kafel `PL-2000:*` z godlem myslnikowym trafial przez API do `laz/pl_1992_*`; review max, zn. 8)".

- [ ] **Step 7: Commit**

```bash
git add kartograf/providers/pl/gugik_laz.py kartograf/download/storage.py kartograf/cli/download_cmd.py tests/test_gugik_laz.py tests/test_storage.py tests/test_cli.py CLAUDE.md docs/ARCHITECTURE.md docs/CHANGELOG.md
git commit -m "fix(storage): uklad kafla LAZ z LazTile.uklad — jeden segment dla CLI i biblioteki"
```

---

### Zad. 16: Szablony segmentow `FileStorage` z rejestru zrodel (zn. 11)

Model: sonnet (review: sonnet).

**Files:**
- Modify: `kartograf/download/storage.py:110-150` (mapy -> klucze deskryptorow; docstring `resolution`)
- Test: `tests/test_storage.py` (klasa `TestFileStorageSegments`, ok. l. 660)

**Interfaces:**
- Produces: `FileStorage._RESOLUTION_SOURCES = {"1m": "pl.gugik.nmt_1m", "5m": "pl.gugik.nmt_5m"}`, `_PRODUCT_SOURCES = {"nmpt": "pl.gugik.nmpt", "orto": "pl.gugik.orto", "laz": "pl.gugik.laz"}`; szablon = `get_source(key).storage_subdir`; nieznany `product`/rozdzielczosc — passthrough jak dotad.

- [ ] **Step 1: Test padajacy:**

```python
    @pytest.mark.parametrize(
        ("kwargs", "key", "godlo", "expected"),
        [
            ({"resolution": "1m"}, "pl.gugik.nmt_1m", "N-34-130-D-d-2-4", "nmt/test_1992_evrf2007"),
            ({"product": "nmpt"}, "pl.gugik.nmpt", "N-34-130-D-d-2-4", "nmpt/test_1992_evrf2007"),
        ],
    )
    def test_segment_templates_come_from_registry(self, tmp_path, monkeypatch, kwargs, key, godlo, expected):
        """Zn. 11: jedno zrodlo prawdy — szablon z deskryptora, nie kopia w FileStorage
        (ADR-026: nowe zrodlo = nowy wpis deskryptora, zero zmian w kodzie sciezek)."""
        from dataclasses import replace

        from kartograf.download import storage as storage_mod
        from kartograf.sources.registry import get_source as real_get_source

        def fake_get_source(k):
            d = real_get_source(k)
            if k == key:
                return replace(d, storage_subdir=expected.split("/")[0] + "/test_{uklad}_{vcrs}")
            return d

        monkeypatch.setattr(storage_mod, "get_source", fake_get_source)
        path = FileStorage(tmp_path, **kwargs).get_path(godlo, ".asc")
        assert expected in path.as_posix()
```

- [ ] **Step 2: Uruchom — musi padac** (`AttributeError: ... has no attribute 'get_source'`).

- [ ] **Step 3: Implementacja** — `kartograf/download/storage.py`: `from kartograf.sources.registry import get_source` na gorze (bez cyklu: `sources` nie importuje `download`); zamiast `_RESOLUTION_SUBDIRS`/`_PRODUCT_SUBDIRS`:

```python
    # Segment templates come from the source descriptors (ADR-026: a new
    # source is a new descriptor entry, no path code) — resolution/product
    # map to the descriptor KEY, not to a copy of its template.
    _RESOLUTION_SOURCES = {"1m": "pl.gugik.nmt_1m", "5m": "pl.gugik.nmt_5m"}
    _PRODUCT_SOURCES = {
        "nmpt": "pl.gugik.nmpt",
        "orto": "pl.gugik.orto",
        "laz": "pl.gugik.laz",
    }

    @staticmethod
    def _descriptor_template(key: str) -> str:
        """Segment template of a registered source."""
        template = get_source(key).storage_subdir
        if template is None:
            raise ValueError(f"Source '{key}' has no storage_subdir")
        return template
```
  i w `_subdir`:

```python
        if self._subdir_override:
            template = self._subdir_override
        elif self._product:
            key = self._PRODUCT_SOURCES.get(self._product)
            template = self._descriptor_template(key) if key else self._product
        else:
            key = self._RESOLUTION_SOURCES.get(self._resolution)
            template = self._descriptor_template(key) if key else self._resolution
```
  Docstring wlasciwosci `resolution` (i sekcji Attributes klasy): "empty only when the segment comes from `product`" (przy jawnym `subdir` pole zachowuje rozdzielczosc — zmierz na kodzie i opisz zgodnie z faktem).

- [ ] **Step 4: Zielono + pelna suita** (testy rownosci w `tests/test_sources_registry.py::TestDescriptorProviderConsistency` zostaja — sa teraz tautologiczne, ale nieszkodliwe; nie usuwaj).

- [ ] **Step 5: Dowod mutacyjny** — przywroc kopie szablonu dla `"1m"` (np. `template = "nmt/pl_{uklad}_1m_{vcrs}"`): wariant `resolution` FAIL; analogicznie `nmpt`.

- [ ] **Step 6: CHANGELOG** (`### Changed`): "`FileStorage` bierze szablony segmentow z deskryptorow rejestru zamiast wlasnych kopii (jedno zrodlo prawdy, ADR-026; review max, zn. 11)."

- [ ] **Step 7: Commit**

```bash
git add kartograf/download/storage.py tests/test_storage.py docs/CHANGELOG.md
git commit -m "refactor(storage): szablony segmentow FileStorage z rejestru zrodel"
```

---

### Zad. 17: Synchronizacja dokumentacji + weryfikacja E2E offline na realnych arkuszach + brama jakosci

Model: **opus** (review: opus). Kazde twierdzenie w dokumentach weryfikuj na zywym kodzie (Global Constraints).

**Files:**
- Modify: `docs/ARCHITECTURE.md` (sekcja 4.3 — przepisz calosc), `docs/DECISIONS.md` (ADR-027: drugie uzupelnienie 2026-09-28), `CLAUDE.md` (przeglad punktow o `--target-crs`, drzewo modulow), `README.md`, `docs/CHANGELOG.md` (`### Tests`, spojnosc sekcji), `docs/SCOPE.md` (jesli wymienia wycinek PL / API biblioteki)

- [ ] **Step 1: `docs/ARCHITECTURE.md` 4.3** — przepisz na stan po fali: (1) API biblioteki `kartograf.download.cutout` (`download_pl_cutout`; kroki `prepare_pl_cutout` -> `select_pl_cutout_sheets` -> `run_pl_cutout`) i CLI jako nakladka; (2) fail-fast przed siecia; (3) zapas zrodla + selekcja z dodatkowym 1 px; R-01 bez zmian (R2 — z krotkim uzasadnieniem: dla jednego obiektu i bboxa "cala obwiednia" = "pierscien"); (4) arkusze jako cache; R5: `NoCoverageError` = nodata + `Warning:` + `extra.missing_sheets`, inne porazki = kod 1; (5) mozaika: siatka arkuszy (siatka wiekszosci, ostrzezenie dla odstajacych), VRT z EPSG:2180/Float32, sortowanie, odrzucenie arkuszy PL-2000; (6) warp bez zmian; dla EPSG:2180 wynik = obszar rozszerzony < 1 px na siatce arkuszy; (7) kompresja pliku posredniego, kontrola dysku, `Info:`; (8) "Nieudana budowa a poprzedni wynik" (zachowaj) + sprzatanie pustych `bbox/`. Liczby tylko zmierzone (fakty planu, pomiary z raportow zadan).
- [ ] **Step 2: ADR-027** — akapit "Uzupelnienie 2026-09-28 (R1, R3, fakty 5-8)": siatka arkuszy dla EPSG:2180 (i crop mozaiki przy warpie), normalizacja VRT, glosny blad dla arkuszy PL-2000 (reprojekcja = etap 2), API biblioteki, R-01 bez zmian (R2), scalanie PL+CZ = etap 2 (R6).
- [ ] **Step 3: `CLAUDE.md`, `README.md`, `docs/SCOPE.md`** — przeglad pod katem sprzecznosci z kodem po falach 1-16 (grep: `failed arkusz`, `sam crop`, `_laz_uklad`, `_prepare_pl_cutout`, `_build_pl_cutout`, `_finalize_pl_cutout`, `odswiez albo nic`); kazde trafienie popraw albo uzasadnij w raporcie.
- [ ] **Step 4: Weryfikacja E2E offline na realnych arkuszach 5 m** (skrypt w katalogu roboczym SDD, NIE w repo; cache Hydrografu wylacznie do odczytu): `download_pl_cutout` z providerem, ktorego `download(godlo, path)` KOPIUJE `.../Hydrograf/cache/nmt/nmt_5m/<hierarchia godla>/<godlo>.asc` do `path`, dla bboxa w obszarze arkuszy `N-34-139-A-c-4-*` (obejmujacego szew arkuszy): (a) cel EPSG:2180 — poczatek siatki `mod 5 == 2,5`, wartosci wyniku rowne wartosciom arkusza zawierajacego srodek piksela (0 rozbieznosci), brak nodata wewnatrz zasiegu danych; (b) cel EPSG:5514 — porownanie z niezaleznym warpem (`rasterio.warp.reproject` kazdego arkusza z ta sama operacja przypieta na te sama siatke) — sredni i maks. |roznica| na pikselach waznych w obu; (c) arkusz bez pliku w cache -> provider rzuca `NoCoverageError` -> `missing_sheets` i nodata w jego miejscu. Wyniki (liczby) do ledgera i do PROGRESS.
- [ ] **Step 5: Brama jakosci**

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest tests/ --cov=kartograf -q 2>&1 | tail -3
.venv/bin/python -m ruff check kartograf/ tests/ && .venv/bin/python -m ruff format --check kartograf/ tests/
.venv/bin/python -m mypy kartograf/ 2>&1 | grep -E "error:" | sed -E 's/:[0-9]+: /: /' | sort > "$SDD_WS/mypy-after.txt"; diff "$SDD_WS/mypy-baseline.txt" "$SDD_WS/mypy-after.txt"
```
Expected: wszystkie testy PASS (liczbe zapisz), ruff czysty, `diff` bez NOWYCH linii (zniknac moga). `CHANGELOG` `### Tests`: dopisz stan (liczba testow, pokrycie) z tego pomiaru.
- [ ] **Step 6: Commit**

```bash
git add docs/ CLAUDE.md README.md
git commit -m "docs: synchronizacja po fali review max — wycinek PL (siatka arkuszy, R5, API biblioteki)"
```

---

## Zakonczenie (kontroler, po Zad. 17)

1. **Finalny review calej galezi** (fable; gdy niedostepny — opus) od commitu po Zad. 0 do HEAD: defekty miedzyzadaniowe, zgodnosc z R1-R6, kod vs dokumentacja. Fala naprawcza z dowodami mutacyjnymi + scoped re-review (re-reviewer powtarza mutacje).
2. **`docs/PROGRESS.md`**: nowa podsekcja "Ostatnia sesja" (co zrobiono, decyzje R1-R6, fakty 1-11, stan: testy/pokrycie/mypy); "Nastepne kroki": pkt 12 (checklista live) uzupelnic o: (f) siatka pikseli arkuszy 1 m EVRF2007 i KRON86 — jedna siatka? (skrypt faz jak w fakcie 1); (g) arkusze 1 m w ukladzie PL-2000 pod godlami PL-1992 — czestosc (ostrzezenia fallbacku skorowidza, bledy PL-2000 wycinka); (h) pogranicze `--country auto --target-crs` na zywo: wycinek PL z nodata po stronie CZ + wycinek CZ, jak wyglada styk na granicy (dane wejsciowe do R6); (i) duzy wycinek (>= 1000 arkuszy): czas, pamiec, deskryptory; (j) bbox nad morzem (np. Leba): `missing_sheets`. Backlog: R6 (scalanie PL+CZ, etap 2), reprojekcja arkuszy PL-2000 w wycinku, podwojna obwiednia przy ukladzie zadania = `--target-crs`, tryby CLI bez wycinka na `download_sheets`, tolerancja braku pokrycia poza wycinkiem, `round` w `warp_to_grid`, obwiednia WGS84 z 4 naroznikow takze w providerach landcover (`corine`/`soilgrids` `_transform_bbox_to_wgs84`) — do sprawdzenia.
3. **Artefakty**: ledger, raport pre-flight, raporty review i fali naprawczej -> `docs/research/2026-09-28-fala-review-max/` + `README.md` (wzor: `docs/research/2026-08-28-uklad-data-target-crs-pl/README.md`).
4. **Pamiec**: aktualizacja `project_uklad_data_target_crs_pl.md` (stan po fali, R1-R6, fakty 1, 5-8 jako drogie do odtworzenia), indeks `MEMORY.md`.
5. Commit zamykajacy: `docs(progress): domkniecie fali review max + wycinek PL w bibliotece`. Bez push (decyzja uzytkownika).

## Weryfikacja koncowa (jak sprawdzic calosc)

- `.venv/bin/python -m pytest tests/ -q` — zielono; `ruff check`/`format --check` czyste; mypy bez nowych bledow (diff listy).
- Zad. 17 Step 4 — E2E offline na realnych arkuszach 5 m: siatka `mod 5 = 2,5`, 0 rozbieznosci wartosci dla EPSG:2180, zgodnosc z niezaleznym warpem dla EPSG:5514, `missing_sheets` dla arkusza bez danych.
- Reczny smoke CLI (offline, bez sieci): `kartograf download --help` pokazuje `--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}`; `python -c "from kartograf import download_pl_cutout, NoCoverageError"`.
- Zywe sprawdzenie (poza ta fala): checklista live w PROGRESS pkt 12 (a)-(j).
