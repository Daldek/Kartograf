# E2E magazynu wersjonowanego na zywo (plan 3/3, Task 11)

Data: 2026-10-12. Galaz `feat/versioned-store` (`f7d5533` + dokumentacja
Task 10), CLI `.venv/bin/kartograf` z korzenia repo (cache metadanych w
korzeniu repo), kazde polecenie z jawnym `--output` w
`<katalog-danych>/kartograf/e2e/2026-10-12-plan3-live/` (udzial SMB bez
`serverino`), polecenia sekwencyjnie. Skrypt regresji `regress.sh` i log
`regress.log` leza obok danych. Bez `CLMS_CREDENTIALS` (odlozone przez
uzytkownika). Kodu nie zmieniano.

## Wynik

| Scenariusz | Kroki | Wynik |
|---|---|---|
| 1 BDOT10k `--teryt 1465` (GPKG) | pobranie, rerun, `--check-updates --plan`, `--force` | PASS: `landcover/pl_bdot10k_gpkg/teryt/1465.gpkg: nowa wersja 2026-10-12_f3550257` (42 s, paczka 88 MB, GPKG 332 MB) -> `lokalna wersja 2026-10-12 (bez sprawdzania; --check-updates)` bez zapytania o paczke -> `1465: nie da sie sprawdzic bez pobrania (2026-10-12)` + plan -> `bez zmian 2026-10-12` (GPKG scalony z tej samej paczki ma ten sam sha256); jedna wersja w `versions/teryt/`, nlink 2 |
| 1b BDOT10k `--bbox 626000,480000,628000,482000` (2 powiaty: 1421, 1465) | pobranie | PASS: `1421.gpkg: nowa wersja 2026-10-12_38da4056`, `1465.gpkg: lokalna wersja ... (bez sprawdzania; --check-updates)`, podsumowanie `Nowe: 1, ..., lokalne: 1, bledy: 0`; sidecar wersji 1421 z `extra.parent_request` = bbox (`countries: ["PL"]`), wersja 1465 (z `--teryt`) bez `parent_request` |
| 2 SoilGrids `clay 0-5cm mean`, ten sam bbox | pobranie, rerun, `--check-updates`, `--upgrade`, `--force` | PASS: `soil/global_soilgrids_clay_0-5cm_mean/bbox/626000_480000_628000_482000.tif: nowa wersja 2.0_717f0989` -> `lokalna wersja 2.0` (biblioteka z licznikiem zapytan: 1 GetCapabilities, 0 GetCoverage) -> `626000_480000_628000_482000: aktualne (2.0)` -> `lokalna wersja 2.0` -> `bez zmian 2.0` |
| 3 CORINE `--year 2018 --sheet N-34-130-D` bez credentials | pobranie, rerun, `--check-updates`; `pytest -m live tests/test_edition.py` | PASS: `Info: CORINE 2018: podglad WMS (...)`, `landcover/eu_corine_2018_preview/N-34/130/D/N-34-130-D.png: nowa wersja 2026-10-12_429b36b9` -> `lokalna wersja 2026-10-12 (bez sprawdzania; --check-updates)` -> `nie da sie sprawdzic bez pobrania`; brak `landcover/eu_corine_2018/`; testy live wydan SoilGrids (clay/sand/silt = to samo wydanie) i CLMS 2018: 2 passed |
| 4 HSG `--bbox 626000,480000,628000,482000 --depth 0-5cm` | pobranie, rerun, `--force`, `--check-updates --plan` | PASS: trzy wejscia `nowa wersja 2.0_<sha8>` + `hsg/global_soilgrids_0-5cm_mean/bbox/...tif: nowa wersja 2.0_470ef3d9` -> wejscia `lokalna wersja 2.0`, HSG `uzyta ponownie 2.0` -> wejscia `bez zmian 2.0`, HSG `uzyta ponownie 2.0` -> `clay/sand/silt/hsg <wsp>: aktualne (2.0)`, plan: 3 x (`landcover`, `current`) + (`hsg`, `current`); sidecar HSG: `extra.version` = `2.0`/`edition`, `source_files` = sciezki wersji wejsc z sha256 i etykieta |
| 5 regresja planow 1/3 i 2/3 | arkusz PL `N-34-130-D-d-2-4`, LAZ (bbox), SM5 `CTES96`, wycinek PL `--target-crs EPSG:2180`, `--country auto --check-updates --plan` -> `--upgrade --plan` -> rerun | PASS: arkusz `nowa wersja 2025-04-26_82710_fdd30535` -> `lokalna wersja`; LAZ `nowa wersja 2024-09-08_81240_3a5ecfd2` -> `lokalna wersja`, liczniki; SM5 `nowa wersja 2026-10-12_a1e327bb` -> `aktualne`; wycinek `nowa wersja` -> `lokalna wersja (bez sprawdzania; --check-updates)`; auto: plan z dwiema pozycjami `do pobrania`, `--upgrade --plan` pobral obie (wycinek PL po jednym `Read timed out` GUGiK — ponowienie udane), rerun: dwie `lokalna wersja` |

## Obserwacje

- `stat` sciezki standardowej BDOT10k tuz po zapisie na udziale SMB
  pokazal nlink 1 (cache atrybutow klienta CIFS, jak w raporcie planu 2/3);
  po chwili 2, i-wezly rozne (udzial bez `serverino`).
- CORINE bez credentials: `Info:` o podgladzie jest drukowane takze przy
  ponownym uruchomieniu (bez pobrania) — informuje, ze wynik to podglad.
- Pobranie CLMS z credentials nie bylo sprawdzane (credentials odlozone);
  odczyt wydania z publicznego katalogu CLMS dziala (test live).
