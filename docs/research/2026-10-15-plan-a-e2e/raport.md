# E2E planu A na zywo (2026-10-15): warianty NMT/NMPT, archiwa, `elevation availability`

Galaz `feat/plan-a-elevation-pl` po rebase na `develop` z manifestem projektu
(`212edd3`). CLI z korzenia worktree (`python -m kartograf.cli.commands`),
cache metadanych w korzeniu worktree, dane wylacznie w `<katalog-danych>`
(jawne `-o`). Plan: `docs/superpowers/plans/2026-10-15-plan-a-elevation-pl.md`
(Task 9), decyzje: ADR-041 z uzupelnieniem.

## Brama (koncowe drzewo)

`pytest tests/ -m "not live"`: 4331 passed, 18 deselected (ok. 85 s);
`ruff check .` czysto; `ruff format --check .` 188 plikow bez zmian;
`mypy kartograf/ tests/` 0 bledow w 186 plikach.

## Wyniki

| Krok | Polecenie (skrot) | Wynik |
|---|---|---|
| E2E-1 NMT 0.5m | `elevation download --product nmt --sheet N-33-58-A-c-1-4 --resolution 0.5m --vertical-crs EVRF2007` | `nmt/pl_1992_0.5m_evrf2007/N-33/58/A/c/1/4/N-33-58-A-c-1-4.asc`, ASC 4202x2600, cellsize 0.50, sha256 `f5f7c69bd748` = `probki.md`, wersja `2025-01-30_84020_f5f7c69b`, sidecar `dataset pl.gugik.nmt_0_5m`, `extra.source.layer SkorowidzNMT2025`, `index_url` = WFS NMT EVRF2007; `Warning:` niepelny najnowszy lot (`--full-sheet`); 40 s |
| E2E-2 NMPT 0.5m | `--product nmpt --sheet N-33-58-A-d-1-2 --resolution 0.5m --vertical-crs EVRF2007` | `nmpt/pl_1992_0.5m_evrf2007/...`, ASC 4128x2701, cellsize 0.50, sha256 `2fa45202dafc`, wersja `2025-01-30_84018_2fa45202`. Ten sam URL co w `probki.md` (`84018_1843926_...asc`), ale inna tresc: 2026-10-13 51,1 MB, 4191x2364, `5e2cdf7e29f1`; 2026-10-15 61 194 511 B (= `Content-Length` serwera), 4128x2701 - GUGiK podmienil plik pod tym samym adresem (brak `Last-Modified`/`ETag`); nowa suma zapisana tutaj |
| E2E-3 KRON86 0.5m, 0.6m, 0.15m | `6.130.26.07.1.2` KRON86 0.5m; `N-33-77-B-c-3-3` EVRF2007 0.6m; `7.159.25.12.2` EVRF2007 0.15m | segmenty `pl_2000_0.5m_kron86`, `pl_1992_0.6m_evrf2007`, `pl_2000_0.15m_evrf2007`; cellsize z naglowka ASC 0.5 / 0.6 / 0.1500 = etykieta; ASC 800x500, 3681x4086, 5333x3333; `dataset` `pl.gugik.nmt_0_5m`, `nmt_0_6m`, `nmt_0_15m`; 3 s, 31 s, 43 s |
| E2E-4 bledy przed siecia | `--cutout --resolution 0.5m`; NMT 5m KRON86; `--product nmpt` bez `--resolution`; `--resolution 0,5m`; dodatkowo `--cutout --format TBD`, `--format TBD --scale 1:5000` | kazde `Error:` z lista z rejestru, kod 1, katalog wyniku nie powstal (np. `Error: --resolution wymagane dla NMPT PL: EVRF2007: 0.5m, 0.6m, 1m; KRON86: 0.5m, 1m`) |
| E2E-5 raport | `elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000` i Pomorze `339000,744800,343000,747000` (`--force`) | Krakow: 2025, 2024, 2023, 2022, 2019 PL-1992 1m kompletne (6/0), 2023 i 2021 PL-2000 1m (15/0), 2019 5m (6/0) - jak pkt 9 planu; rocznik 2018 = kombinacje archiwow XYZ/TBD (decyzja 13), niekompletne. Pomorze (lad 86,38 ha): NMT 2025 0.5m 0/4 "nie: 4 niepelne", 2022 1m 3/0 "brak arkuszy dla 0,88 ha" (8 782 m2), NMPT 2025 0.5m 0/4 - jak pkt 9; najnowsza kompletna kombinacja Pomorza to archiwum TBD 25m KRON86 2010. Czas z siecia 5,3-7,4 s na raport (16 km2 / 8,8 km2), z cache 0,6-1,5 s. `--json` = `check_availability(...).to_json()` bajtowo (zamrozony zegar, ten sam cache) dla NMT, NMPT i LAZ obu obszarow; podproces CLI = API poza `checked_at` |
| E2E-6 raport = pobranie | podpowiedz najnowszej kompletnej kombinacji Krakowa (`--sheet-system 1992 --resolution 1m --vertical-crs EVRF2007 --year 2025`) + `-o` | pobrane godla = `sheets_full` kombinacji (M-34-64-D-d-1-2, -1-4, -2-1, -2-3, -3-2, -4-1), wersje `2025-04-28_83137_*`, rok = rok kombinacji; 53 s |
| E2E-7 LAZ | `--product laz` Pomorze; zapytania nagrane przez opakowanie `requests.Session.request` | 2025 PL-1992 10 TAK / 11 NIE, niekompletna; zapytania: 2 x WFS LIDAR EVRF2007, 2 x WFS LIDAR KRON86, 3 x WFS PRG, 0 x opendata; po raportach `git status` czysty (raport nie ma `--output`, zapisuje tylko cache) |
| E2E-8 wycinek 1m | `--cutout --horizontal-crs EPSG:2180 --bbox 566000,243000,566500,243500` NMT i NMPT EVRF2007, kod `develop` (`212edd3`) i planu A | pliki bajtowo rowne: NMT `790df2d528619523...`, NMPT `e01648fbef06157f...`; sidecary rowne poza `downloaded_at` |
| Archiwum (decyzja 13) | podpowiedz Pomorza: `--format TBD --resolution 25m --vertical-crs KRON86 --year 2010` | 3 arkusze ze skorowidza (`N-33-58-A-c-1..3`), `nmt/pl_1992_tbd_25m_kron86/.../<godlo>.zip`, ZIP kompletne (`testzip` bez bledow, pliki `NMT-*.ASC` jak u zrodla), sidecar `dataset pl.gugik.nmt_tbd_25m`, `full_sheet/`; ponownie: 3 x lokalna wersja; `--check-updates`: 3 x aktualne |

## Nowy fakt GUGiK i poprawka (ADR-041 R6)

Plan zakladal, ze 42 rekordy NMT EVRF2007 2019 z formatem siatki i URL `.xyz`
sa niespojne. Zapytanie WFS 2019 dla arkuszy N-33-57, N-33-69 i N-33-81 daje
dokladnie 42 takie rekordy (wszystkie kampanii 72675, N-33-69), a pierwsze
bajty kazdego pliku (HTTP Range) to naglowek AAIGrid (`ncols ... nrows ...`).
0.7.x pobieralo je jako `.asc`; plan A po raz pierwszy je odrzucal (`--year
2019` dla tych arkuszy = brak danych, raport: falszywe `Info:`). Poprawka:
rejestr przyjmuje dla siatki ASC URL `.asc` i `.xyz` (tresc nadal sprawdza
`verify_file_format`). Na zywo po poprawce: raport `N-33-69-A-d-1-3 --year
2019` pokazuje siatke 1m (1/0, bez `Info:`), pobranie daje
`nmt/pl_1992_1m_evrf2007/.../N-33-69-A-d-1-3.asc`, wersja `2019-04-29_72675_0ff05b57`.

## Uwagi

- Kazdy pobrany arkusz 0.5m/0.6m/0.15m mial niepelny najnowszy lot (`Warning:`
  z podpowiedzia `--full-sheet`) - zgodnie ze skorowidzem.
- Komunikat `--cutout --resolution 0.5m` powtarza "pomin --cutout (arkusze bez
  --cutout)" - czytelny, do ewentualnego skrocenia.
- Wycinki E2E-8 trwaly dluzej (4 wycinki w ok. 6 min, WCS GUGiK), raporty
  i arkusze bez zastrzezen.
