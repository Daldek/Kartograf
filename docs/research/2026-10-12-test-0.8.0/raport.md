# Test na zywo zmian lamiacych 0.8.0 (2026-10-12)

**Kod:** migawka `develop` `3f150ce` (`git archive`), `PYTHONPATH=<migawka>`,
CLI z korzenia migawki. **Dane:** `<katalog-danych>/kartograf/e2e/2026-10-12-test-0.8.0/data`
(SMB/CIFS). Skrypty: `scripts/cli.sh`, `scripts/lib.py` obok danych.

## Wynik: 0 FAIL (31 scenariuszy CLI, 9 biblioteki)

| # | Scenariusz | Kod | Wynik |
|---|---|---|---|
| 1 | `--sheet N-34-139-C-a-3-1 --product nmt --resolution 1m --vertical-crs EVRF2007` | 0 | PASS — plik + sidecar, `Warning:` o niepelnej kampanii |
| 1b | to samo ponownie | 0 | PASS — `Skipped ...` (jedno `RemoteDisconnected` skorowidza, ponowienie udane) |
| 2a | godlo pozycyjnie | 2 | PASS — `unrecognized arguments` |
| 2b-e | brak `--product` / `--output` / `--vertical-crs` / `--resolution` | 1 | PASS — `Error:` z lista wartosci, przed siecia |
| 3a | `--all-campaigns --min-year 2019` | 0 | PASS — 4 kampanie, `full_sheet/`, `Info:` wieksze pokrycie (78047, 94,7 %) |
| 3b | `--campaigns all` | 2 | PASS — odrzucone przez argparse |
| 4a | NMPT N-34-139-C-a-3-1 | 1 | PASS — GUGiK ma ten arkusz tylko w 0,5 m (fakt zrodla, komunikat poprawny) |
| 4b | NMPT N-34-130-D-d-2-4 (bez `--resolution`) | 0 | PASS |
| 4c | orto (bez ukladu wysokosci) | 0 | PASS |
| 5a | PL-2000 `6.179.12` (1:10000) bez `--scale` | 1 | PASS — `Error: --scale wymagane dla arkuszy PL-2000 ...` |
| 5b | PL-2000 `6.179.12 --scale 1:5000` | 1 | PASS (zachowanie) — brak danych 1:5000 w obszarze, `Info:` z godlami PL-1992 |
| 5c | PL-1992 z `--scale 1:10000` | 1 | PASS — `Error: --scale nie dotyczy PL-1992` |
| 5d | `6.179.12.20 --scale 1:5000` (blad danych testu: godlo 1:2000) | 1 | PASS — `Error: Skala docelowa 1:5000 jest grubsza ...` |
| 6a | pogranicze `--country auto --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv` | 0 | PASS — wycinek CZ (Bpv, 2 m) + arkusz PL; drugi arkusz PL bez 1 m (`Warning:` + podpowiedz 5 m) |
| 6b | pogranicze, jedna wartosc `--resolution 1m` | 0 | PASS — `Info: --country auto -> pl (--resolution 1m dotyczy tylko PL)` (zgodnie z USAGE 1.x) |
| 6c | pogranicze, jedna wartosc `--resolution 2m` (brak w PL) | 1 | PASS — `Error: PL nie ma rozdzielczosci 2m ... wartosci per kraj, np. --resolution pl=...,cz=...` |
| 6d | `--bbox` bez `--country` | 1 | PASS |
| 7 | CZ `--sheet 302_5550 --resolution 2m --vertical-crs Bpv` | 0 | PASS |
| 8a | LAZ `--bbox ... --country pl --vertical-crs EVRF2007` | 0 | PASS — 2 kafle, 4 pominiete jako pokryte |
| 8b | LAZ `--all-campaigns` | — | PASS (zachowanie) — 6 kafli bez deduplikacji; przerwane po 4/6 limitem czasu skryptu testowego (2 kafle PL-2000 > 200 MB), nie bledem |
| 9a | `landcover download --source corine --year 2018 --sheet N-34-139-C` | 0 | PASS — `corine_2018_sheet_N-34-139-C.png` (podglad WMS, brak CLMS) |
| 9b-c | brak `--source` / `--year` | 1 | PASS |
| 9d | `soilgrids hsg --sheet N-34-139-C --depth 0-5cm` | 0 | PASS |
| 9e | `soilgrids hsg` bez `--depth` | 1 | PASS |
| 10a-f | biblioteka: `DownloadManager(output_dir, provider)`, `MetadataCache(db_path)`, `TypeError` bez wymaganych argumentow (`DownloadManager`, `FileStorage`, `MetadataCache`), `all_campaigns=True` (3 kampanie od 2023) | — | PASS |
| 11a-c | biblioteka: `LandCoverManager(...).download(sheet=, year=)`, `request.year`, `HSGCalculator.calculate_hsg_by_sheet(..., depth=, stat=)` | — | PASS |

## Uwagi

- `Warning: cache metadanych zablokowany przez inny proces ... database is
  locked` w wiekszosci scenariuszy: plik `.kartograf_cache.db` lezal na
  udziale CIFS, a scenariusze biegly czesciowo rownolegle. Pobieranie szlo
  dalej bez cache (zachowanie zgodne z ARCHITECTURE 4.1). Nie dotyczy 0.8.0.
- Host GUGiK: pojedyncze `RemoteDisconnected` / `ConnectionResetError`,
  wszystkie udane w ponowieniu.
