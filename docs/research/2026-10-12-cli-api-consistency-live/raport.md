# Weryfikacja na zywo: spojnosc CLI i API (2026-10-12)

Plan: `docs/superpowers/plans/2026-10-12-cli-api-consistency.md`, Task 17.
Galaz `chore/cli-api-consistency` (stan po `c44c026`). Dane w
`<katalog-danych>/cli-api-2026-10-12/<scenariusz>/{cli,api}` (sciezka od
uzytkownika, poza repo; STANDARDS 6.4). Uruchomienie z korzenia repo
(wspolny cache metadanych `.kartograf_cache.db`).

## Metoda

Kazdy scenariusz dwa razy, ta sama minuta: CLI przez
`.venv/bin/kartograf ... -o <...>/cli` (podproces) i biblioteka
(`download_data`, `check_data`, `LandCoverManager`, `HSGCalculator`)
z wyjsciem `<...>/api`. Porownanie drzew: kazdy plik (dane, sidecary wersji
i dowiazan, `full_sheet/`) - `sha256`; pliki JSON (sidecary, plan) jako
JSON bez `downloaded_at` i `checked_at` (zegar nie jest zamrozony). Dodatkowo:
kod wyjscia CLI = `0 if wynik.ok else 1`, kazdy `Notice` wyniku API jako
linia `Info:`/`Warning:` na stderr CLI. Skrypt jednorazowy poza repo.

## Wyniki

| # | Scenariusz | Komenda CLI (skrot) | Kod CLI | `ok` API | Notice API / na stderr CLI | Roznice drzew |
|---|---|---|---|---|---|---|
| 1 | Arkusz PL NMT 1 m | `download --product nmt --sheet N-34-130-D-d-2-4 --resolution 1m --vertical-crs EVRF2007` | 0 | True | 0 / - | 0 |
| 2 | Obszar PL `--system 1992` | `download --bbox 637400,487000,638400,488000 --country pl --system 1992 ...` | 0 | True | 0 / - | 0 (arkusz + `full_sheet/`) |
| 3 | Wycinek PL `--target-crs EPSG:2180` | `download --bbox 530000,382000,530500,382500 --country pl --target-crs EPSG:2180 ...` | 0 | True | 0 / - | 0 |
| 4 | Arkusz CZ SM5 | `download --sheet CTES96 --vertical-crs Bpv` | 0 | True | 0 / - | 0 |
| 5 | `--country auto` na pograniczu (Cieszyn) | `download --bbox 18.62,49.74,18.63,49.75 --bbox-crs EPSG:4326 --country auto --target-crs EPSG:2180 --resolution pl=1m,cz=2m --vertical-crs EVRF2007` | 0 | True | 0 / - | 0 (wycinek PL i CZ) |
| 6 | LAZ, maly bbox EPSG:4326 | `download --product laz --bbox 21.0,52.23,21.001,52.2305 --bbox-crs EPSG:4326 --country pl --vertical-crs EVRF2007` | 0 | True | 1 / 1 (`laz_superseded`, 6 kafli) | 0 (2 kafle, 282 MB) |
| 7 | BDOT10k, obszar 2 powiatow | `landcover download --source bdot10k --bbox 626000,480000,628000,482000 --layers SWRS,PTWP` | 0 | True | 0 / - | 0 (1421, 1465) |
| 8 | SoilGrids | `landcover download --source soilgrids --bbox 626000,480000,628000,482000 --property clay --depth 0-5cm --stat mean` | 0 | True | 0 / - | 0 |
| 9 | HSG `--geometry` (SHP EPSG:2180) | `soilgrids hsg --geometry <...>/zlewnia.shp --depth 0-5cm` | 0 | True | 0 / - | 0 (3 wejscia + HSG) |
| 10 | `--check-updates --plan` -> `--upgrade --plan` | arkusz z (1) w nowym magazynie | 0 / 0 | True | - | plan: te same pozycje (1, `missing`); po `--upgrade` 0 roznic |

Uwagi z przebiegu: pojedyncze timeouty PRG i WFS GUGiK (ponowione,
`proba 1/3 nieudana ... ponowienie za 2s` na stderr CLI z logowania
transportu) - bez wplywu na wynik.

## Niezgodnosci i poprawki

- Scenariusz 10, pierwsza proba: plik planu w katalogu, ktory nie istnial
  -> `Error: FileNotFoundError: ...` z podpowiedzia `KARTOGRAF_DEBUG`
  (nieobsluzony `OSError` przy zapisie planu w CLI; blad CLI, nie roznica
  CLI/API). Poprawka `c44c026` (`fix(cli): blad zapisu pliku --plan jako
  jedna linia Error:`, test regresji
  `tests/test_cli_update_modes.py::test_plan_file_in_missing_directory_is_one_error_line`).
  Na zywo po poprawce: `Error: nie udalo sie zapisac planu <...>/brak/plan.json:
  [Errno 2] ...`, kod 1, magazyn nie powstaje.
- Roznic CLI/API w danych, sidecarach, statusach, planie i komunikatach:
  0 we wszystkich scenariuszach.

Rozbieznosci wykryte wczesniej offline (testy zgodnosci, Task 13 i 15):
bbox sidecara z liczb calkowitych vs zmiennoprzecinkowych
(`core.bbox.bbox_coords`) i kolejnosc wyniku arkuszy rownoleglych
(`93eee02`) - na zywo nie wystapily.
