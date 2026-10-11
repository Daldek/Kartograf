# Test na zywo przed wydaniem 0.7.2 (2026-10-11)

`develop` (HEAD `108c4f2`, `kartograf 0.7.2-dev+108c4f2`), bez zmian
w kodzie. CLI uruchamiane z korzenia repo (cache metadanych lokalnie), dane
w `<katalog-danych>/kartograf/e2e/2026-10-11-test-przed-0.7.2/` z jawnym
`--output`, osobny katalog na scenariusz. Skrypty jednorazowe poza repo.
Host GUGiK niestabilny jak przy strojeniu ASC (raport
`docs/research/2026-10-11-nmpt-asc-tuning/raport.md`): zerwania polaczen
przechodzily w ponowieniach `download_to`.

## Brama offline

| Komenda | Wynik |
|---|---|
| `pytest tests/ -m "not live"` | 3262 passed, 16 deselected |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 126 files already formatted |
| `mypy kartograf/ tests/` | no issues found in 124 source files |

## Wyniki CLI

| # | Scenariusz (`kartograf ...`) | Wynik | Ocena |
|---|---|---|---|
| 1a | `download N-34-130-D-d-2-4 --year 2024` | kod 0, 18 s; kampania `2024-05-27_81449`, sidecar `request`: `campaigns: newest`, `min_year`/`max_year`/`year: 2024`; `sha256` zgodne | PASS |
| 1b | jw. `--year 2023` | kod 1, `Error: brak danych z roku 2023 dla 1 z 1 arkuszy — nic nie pobrano:` / `dostepne roczniki 2022, 2024, 2025` / podpowiedz `--min-year 2023 ... albo --max-year 2023 ...` | PASS |
| 1c | jw. bez flag roku | kod 0; kampania `2025-04-26_82710`, sciezka standardowa i `full_sheet/` na 82710 | PASS |
| 1d | jw. `--year 2024` po 1c | kod 0, `Skipped` (81449 lokalnie); `Info: 2 dowiazan wskazuje lokalny lot spoza tego zadania ...` z liniami `full_sheet/` i `sciezka standardowa -> dowiazanie 2025-04-26_82710` | PASS |
| 1e | jw. `--min-year 2023 --max-year 2025 --campaigns all` | kod 0, `Downloaded 2 campaign files for 1 sheets ... (0 already existed)` (81449, 82710); sidecary `campaigns: all`, `min_year 2023`, `max_year 2025`, `extra.available_years [2022, 2024, 2025]` | PASS |
| 2a | `download N-34-139-C-a-3-1` | kod 0; `Warning: ... pelny lot nie pobrany: N-34-139-C-a-3-1 — uzyj --full-sheet` | PASS |
| 2b | jw. `--full-sheet` | kod 0, `Downloaded 1 campaign files ... (1 already existed)`; standard i `full_sheet/` rozne inode, `extra.link_target` -> `kampanie/2025-04-27_83233/...`; `Warning: ... pelny lot w <segment>/full_sheet/` | PASS |
| 2c | jw. `--product laz --full-sheet` | kod 1, `Error: --full-sheet dziala tylko z NMT/NMPT/orto (podano laz) ...` przed siecia | PASS |
| 3 | `download N-34-130-D-d-1-1 --resolution 5m` | kod 1 (pojedynczy arkusz bez danych), `Error: Brak danych NMT 5m ... Skorowidz GUGiK ma ten arkusz w NMT 1m EVRF2007 — uzyj --resolution 1m; ... NMT 1m KRON86 — uzyj --resolution 1m --vertical-crs KRON86` | PASS |
| 4a | `download --bbox 567500,242500,568000,243000 --country pl --target-crs EPSG:2180` | kod 0, 133 s (jedno zerwanie, ponowione); `nmt/pl_1992_1m_evrf2007/bbox/567500_242500_568000_243000_20261011.tif`, 1 pasmo float32, 501 x 501, poczatek (567499,5; 242499,5); `extra.source.format` `image/x-aaigrid`, `composition: server`, `extra.mask.masked_pixels 0`; `sha256` zgodne | PASS |
| 4b | jw. `--product nmpt` | kod 0, 31 s; `nmpt/pl_1992_1m_evrf2007/bbox/..._20261011.tif`, float32 501 x 501 | PASS |
| 4c | `--bbox 479000,451000,479500,451500 ... --product nmpt --vertical-crs KRON86` | kod 0, 17 s; `nmpt/pl_1992_1m_kron86/bbox/..._20261011.tif`, float32 501 x 501, `image/x-aaigrid` | PASS |
| 4d | jw. NMT `--target-crs EPSG:5514 --vertical-crs KRON86` | 1. przebieg: kod 1, 3 x `RemoteDisconnected` (host); 2. przebieg: kod 0, 10 s; 537 x 537 EPSG:5514, `transform.horizontal` `pinned: ...`, `image/tiff`, `vertical_crs` EPSG:9650 | PASS (host) |
| 4e | 4a z `--resolution 5m` | kod 1, `Error: wycinki --target-crs sa tylko 1 m (WCS GUGiK); ...` przed siecia | PASS |
| 4f | 4a z `--year 2024` | kod 1, `Error: --year nie dziala z --target-crs — wycinek z WCS GUGiK ma kompozycje lotow serwera ...` | PASS |
| 5 | `download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326` (auto) | kod 0, 79 s; `Info: --country auto bez --vertical-crs: czesc PL w EVRF2007, czesc CZ w Bpv ...`; PL: 2 arkusze `M-34-74-C-a-4-4`, `-C-b-3-3` (kampania 83852, z `full_sheet/`), CZ: wycinek `nmt/cz_dmr5g_bpv/bbox/...tif` | PASS |
| 6a | `download --geometry two_layers.gpkg --country pl --vertical-crs KRON86` (warstwy `zlewnia`, `punkty`) | kod 0; `Info: two_layers.gpkg: liczba warstw 2, uzyto pierwszej 'zlewnia' (pozostale: punkty); inna warstwa: --layer NAZWA`; arkusz `M-34-2-A-b-4-3` | PASS |
| 6b | jw. `--layer punkty --country pl` | kod 0, bez `Info:`; arkusz `M-34-64-D-d-2-3` | PASS |
| 7a | `download --bbox 637200,486900,637500,487100 --product laz --year 2024` | kod 1, `Error: brak kafli LAZ z roku 2024 dla 1 z 1 kafli obszaru — nic nie pobrano:` / `N-34-139-A-c-1-1-3-4 (2025, PL-1992): dostepne roczniki 2022, 2023, 2025` / obie podpowiedzi | PASS |
| 7b | `download --bbox 637400,487000,637450,487050 --product laz --max-year 2023` | kod 0, 88 s; 1 kafel 2023 `N-34-139-A-c-1-1-3-4`; `Info: pominieto 1 kafli LAZ` (2022 pokryty przez 2023) | PASS |
| 8 | `download N-33-130-D-d-1-4 --product orto --year 2025` | kod 0, 23 s; `Warning:` E13 z podpowiedzia `--full-sheet` | PASS |
| 9 | `parse M-３３-８-A` (cyfry pelnej szerokosci) | kod 1, `Error: Nieprawidłowe godło: 'M-３３-８-A' ...` | PASS |
| 10 | `landcover download --source bdot10k --bbox 340000,290000,350000,300000` | kod 0, 77 s; `bdot10k_teryt_0208.gpkg`, `bdot10k_teryt_0224.gpkg` | PASS |
| 11 | `cache stats` | kod 0, `TERYT entries: 1` | PASS |

## Wyniki biblioteki

| # | Wywolanie | Wynik | Ocena |
|---|---|---|---|
| L1 | `DownloadManager(min_year=2023, max_year=2023).check_year_range(["N-34-130-D-d-2-4"])`; `provider.available_years(...)` | `YearRangeCheck(conflicts={'N-34-130-D-d-2-4': (2022, 2024, 2025)}, failed={})`; `(2022, 2024, 2025)` | PASS |
| L2 | `download_pl_cutout(BBox(567600,242600,567900,242900), "EPSG:2180", product="nmpt", max_workers=2)` | wynik `.../nmpt/pl_1992_1m_evrf2007/bbox/567600_242600_567900_242900_20261011.tif`, float32 301 x 301, nodata -9999, `masked_pixels 0`; `DeprecationWarning: download_pl_cutout(max_workers=...) has no effect since 0.7.2 (WCS cutout) and will be removed in 0.8.0`; `extra.source.composition: server`, `extra.mask` PRG, `sha256` zgodne | PASS |
| L3 | `GugikNmptProvider.download_bbox` 2000 x 1000 px (raport strojenia ASC pkt 3) | 2 kawalki, 246 s; bit w bit z jednym zapytaniem | PASS |

## Wniosek

Brak FAIL. Jedyna porazka (4d, pierwszy przebieg) to trzy kolejne
zerwania polaczenia przez host GUGiK; powtorka przeszla bez zmian
w kodzie. Zmiany 0.7.2 objete testem (wybor roku i przedzial,
`Info:` o dowiazaniu spoza zadania, `full_sheet/` i `--full-sheet`,
podpowiedz wariantu, wycinki NMT/NMPT z WCS z maska PRG i bledy przed
siecia, `Info:` d1 i d2, LAZ z flagami roku, orto `--year`, godla spoza
ASCII, BDOT10k z PRG, `check_year_range`, `download_pl_cutout(product=)`
z `DeprecationWarning`, kawalki ASC NMPT) dzialaja na zywo zgodnie
z `docs/CHANGELOG.md` [0.7.2]. `develop` nie wymaga zmian przed wydaniem.
