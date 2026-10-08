# E2E pelny A (2026-10-07, develop d589c88) — polskie rastry z torem kampanii

Dane: `<katalog-danych>/kartograf/e2e/2026-10-07-adr030-full-A/data` (~840 MB wg `du`). Skrypty/logi: katalog tymczasowy `scratchpad/e2eA` (logi `logs/c*.log`).
Weryfikacja plikow skryptem `verify.py`: kampanie/ + sidecar (`extra.campaign`, `request.campaigns/min_year`), sciezka standardowa = hardlink do NAJNOWSZEJ lokalnej kampanii (ten sam i-wezel, nlink 2, `extra.link=hardlink`, `link_target`), brak symlinkow (`find -type l` = 0), CRS poziomy/pionowy w sidecarze zgodny z segmentem, rasterio czyta plik.

## Tabela przypadkow

| # | Produkt | XY | Pion | Godlo/obszar | Komenda (skrot) | Wynik | Fakty |
|---|---|---|---|---|---|---|---|
| 1a | NMT 1m | PL-1992 | EVRF2007 | N-34-50-C-d-3-3 (3 kampanie) | newest; powtorka; `--campaigns all`; powtorka `all` | PASS | newest: `Downloaded to`, powtorka `Skipped`; `all`: "2 campaign files ... (1 already existed)", powtorka "0 ... (3 already existed)"; hardlink na 2024-10-01 |
| 1b | NMT 1m | PL-1992 | EVRF2007 | N-34-50-C-d-3-3 | `--min-year 2030` (newest i `all`) | PASS | kod 1; `Error: Najnowsza kampania ... starsza niz min_year=2030` / `Brak kampanii ... od roku 2030 (najnowsza: 2024-10-01)` |
| 1c | NMT 1m | PL-1992 | EVRF2007 | N-33-130-D-d-1-2 (6 kamp.) | `all --min-year 2024` (pierwszy przebieg), newest, powtorka | PASS | 2 pliki (2024, 2025), standard -> 2025 (all-first, link na najnowsza); newest = Skipped; powtorka "0 (2 already existed)" |
| 1d | NMT 1m | PL-2000 S7 | EVRF2007 | 7.125.11.13 (1:2000, 2 kamp.) | newest, Skipped, `all --min-year 2023` (0 nowych), `all` (+2021) | PASS | EPSG:2178, hardlink na 2023-03-17 po dopobraniu starszej |
| 1e | NMT 1m | PL-2000 S7 | EVRF2007 | 7.173.21.13 | `all` | PASS | 1 kampania 2021, EPSG:2178 |
| 1f | NMT 1m | PL-2000 S8 | EVRF2007 | 8.193.13.13.4 (1:1000) | `all` | PASS | EPSG:2179 |
| 1g | NMT 1m | PL-2000 S5, S6 | EVRF2007 | skan 1:2000 w 12 obszarach (Szczecin, Poznan, Gdansk, Gorzow, Zielona Gora, Wroclaw, Katowice, Torun...) | metadane | SKIP | skorowidz nie ma NMT 1m PL-2000 w S5/S6 (wszedzie "Skorowidz ma ten obszar w PL-1992") |
| 2a | NMT 1m | PL-1992 | KRON86 | N-34-50-C-d-3-3 (2 kamp.) | `--vertical-crs KRON86 --campaigns all` -> newest(Skipped) -> `all --min-year 2018` | PASS | segment `nmt/pl_1992_1m_kron86`, v=EPSG:9650, hardlink na 2018-03-18 |
| 2b | NMT 1m | PL-2000 S8 | KRON86 | 8.193.13.13.4 | newest; `all --min-year 2019` | PASS | segment `nmt/pl_2000_1m_kron86`; min-year > najnowszej = Error kod 1 (2018-11-30) |
| 3a | NMT 5m | PL-1992 | EVRF2007 | N-33-130-D-d-1-2 | newest, Skipped, `all` | PASS | `nmt/pl_1992_5m_evrf2007`, siatka 5 m; "1 campaign files (1 already existed)" |
| 3b | NMT 5m | PL-1992 | KRON86 zadane | N-34-50-C-d-3-3 | `-r 5m --vertical-crs KRON86 --campaigns all [--min-year 2023]` | PASS | `Info: NMT 5m (PL) jest dostepny tylko w EVRF2007 — --vertical-crs KRON86 zamieniony na EVRF2007` (CLAUDE.md zgodnie); pobiera EVRF2007 |
| 3c | NMT 5m | PL-2000 | EVRF2007 | 7.125.11.13 | newest | PASS (oczek. brak) | `Error: Brak danych NMT 5m ... Skorowidz ma ten obszar w PL-1992: ... --system 1992`, kod 1 |
| 3d | NMT 5m | PL-1992 | EVRF2007 | N-33-130-D-d-1-2 | `--force` | PASS | pobiera ponownie, hardlink zachowany (nowy i-wezel, link spojny) |
| 4a | NMPT 1m | PL-1992 | EVRF2007 | M-34-41-A-a-1-2 (2 kamp.) | newest, Skipped, `all --min-year 2023` (0 nowych), `all`, `all --min-year 2024` | PASS | hardlink na 2023-05-05; ostatni = Error kod 1 |
| 4b | NMPT 1m | PL-1992 | KRON86 | M-34-75-A-d-2-4 (1 kamp.) | `all`, newest | PASS | `nmpt/pl_1992_1m_kron86`, v=EPSG:9650; brak arkusza NMPT KRON86 z >1 kampania (skan 4 obszarow) |
| 4c | NMPT 1m | PL-2000 | oba | 7.125.11.13, 7.173.21.13, 8.193.13.13.4 + skan | metadane/CLI | SKIP | `Brak danych NMPT 1m ... (PL-2000)`; GUGiK ma te arkusze tylko w 0,5 m (Kartograf wymaga 1 m). CLI: Error kod 1 |
| 5a | Orto RGB | PL-1992 | - | M-34-41-A-a-1-2 (9 kamp.) | newest; Skipped; `all --min-year 2022`; powtorka | PASS | 4 kampanie (2022..2025), "3 campaign files (1 already existed)", powtorka "0 (4 already existed)", hardlink na 2025-04-30; TIF EPSG:2180 0,25 m |
| 5b | Orto RGB | PL-2000 S8 | - | 8.193.13.13.4 (2 kamp., 5 cm) | newest; `all` | PASS | `orto/pl_2000`, hardlink na 2024-03-30 (raster zglasza CRS `ESRI:102177`, sidecar EPSG:2179) |
| 6a | Orto CIR (biblioteka) | PL-1992 | - | N-34-50-C-d-3-3 | `DownloadManager(provider=GugikOrtoProvider(color="CIR"))` newest, powtorka, `campaigns="all"`, `all+min_year=2013` | PASS | segment `orto/pl_1992_cir`; newest CIR = 2021-09-08 (RGB ma 2024 — brak mieszania kolorow), 4 kampanie CIR (2010..2021), powtorka skipped=True, min_year=2013 reused=3 |
| 6b | Orto B/W (biblioteka) | PL-1992 | - | N-34-50-C-d-3-3 | newest, powtorka, `all`, `all+min_year=2013` | PASS | `orto/pl_1992_bw`, 1 kampania 2004; `min_year=2013` -> NoCoverageError "od roku 2013 (najnowsza: 2004-01-01)" |
| 7a | NMT lista `--bbox` | PL-1992 | EVRF2007 | bbox 477600,719900,477700,720000 (2 arkusze) | newest; `all`; powtorka `all` | PASS | "Downloaded 1 files (1 already existed)"; "2 campaign files for 2 sheets (4 already existed)"; "0 ... (6 already existed)" (zgodne z dyskiem) |
| 7b | NMT lista `--bbox --system 2000` | PL-2000 S8 | EVRF2007 | bbox EPSG:2179 | domyslne `--scale 1:10000` | PASS (oczek. brak) | `Error: GUGiK nie ma danych ...` + `Info:` z podpowiedzia `--scale 1:1000`, kod 1 |
| 7c | NMT lista `--bbox --system 2000 --scale 1:1000 --campaigns all` | PL-2000 S8 | EVRF2007 | j.w. | | PASS | 1 arkusz 8.193.13.13.4, "0 campaign files (1 already existed)" |
| 7d | NMPT lista `--bbox --campaigns all --min-year 2023` | PL-1992 | EVRF2007 | bbox 572380,346300,572420,346340 | | PASS | 2 arkusze, "1 campaign files for 2 sheets (1 already existed)" |
| 7e | NMT `--geometry area.shp` (pyshp + .prj EPSG:2180) | PL-1992 | EVRF2007 | 2 arkusze N-34-50-C-d-3-3/4 oraz swiezy obszar M-34-41-A-a-1-2/1-4 | newest | PASS | "Downloaded 2 files (0 already existed)" na swiezym; powtorka "0 files (2 already existed)" |
| 8a | Wycinek CLI | PL-1992 | EVRF2007 | bbox 477600..477700 | `--target-crs EPSG:2180` (+ powtorka) | PASS | `bbox/477600_719900_477700_720000.tif`, 101x101, 1 m, EPSG:2180; powtorka `Skipped - already exists`; `extra.sheet_sources` z newest 2024 + `parent_request` |
| 8b | Wycinek CLI | | | j.w. | `--target-crs EPSG:5514` / `EPSG:3045` | PASS | pliki w `bbox/` z nazwa w ukladzie docelowym, kod 0 |
| 8c | Wycinek CLI | | | j.w. | `--target-crs EPSG:2177` i `EPSG:4326` | PASS (oczek. odmowa) | argparse: `invalid choice ... (choose from EPSG:2180, EPSG:5514, EPSG:3045)`, kod 2 |
| 8d | Wycinek biblioteka `download_pl_cutout` | | | bbox 477610..477690 -> EPSG:2180; ten sam obszar -> 5514 (skipped=True, ten sam plik co CLI); 2177 | | PASS | wycinek z biblioteki identyczny z oknem CLI (`np.array_equal`); 2177 -> `ValidationError ... (dostepne: EPSG:2180, EPSG:5514, EPSG:3045)` |
| 8e | Blokady | | | `--target-crs` + `--campaigns all` / `--min-year 2020` / `--product nmpt` | | PASS | trzy komunikaty `Error:` (m.in. "laczenie kampanii: narzedzie 0.7.1"), kod 1, bez sieci; `--campaigns newest` + target-crs dziala (Skipped) |
| 9 | Fallback I-1 (skorowidz niedostepny) | PL-1992/2000 | EVRF2007, KRON86 | NMPT M-34-41-A-a-1-2, NMPT KRON86 M-34-75-A-d-2-4, orto M-34-41-A-a-1-2 i 8.193.13.13.4, NMT N-34-50-C-d-3-3 | `socket.socket.connect` -> `OSError`, `DownloadManager(provider bez cache).download_sheet` | PASS | wszystkie: `last_sheet.skipped=True`, `unverified="GUGiK WMS GetCapabilities ... pobranie nieudane po 3 probach ..."`, dl=0, dowiazanie nietkniete, `WARNING kartograf.download.manager: ... skorowidz GUGiK niedostepny`. Negatywne: `campaigns="all"` oraz arkusz nieobecny lokalnie -> `DownloadError` (bez cichego fallbacku) |

Podsumowanie: PASS 29 wierszy / FAIL 0 / SKIP 2 (1g NMT PL-2000 S5/S6, 4c NMPT PL-2000).

## BLEDY

Brak bledow funkcjonalnych ADR-030 w tym przebiegu.

## OBSERWACJE

1. (UX, niski) `Error:` poprzedzony pusta linia na stderr (np. `--min-year` ponad najnowsza) — widoczne w kazdym przypadku bledu kampanii/NoCoverage (zapewne pozostalosc po pasku postepu).
2. (UX, niski) W trybie `--campaigns all`, gdy wszystkie pliki sa lokalne, CLI nie drukuje `Downloading ...` (tylko podsumowanie) — a gdy cos pobiera, drukuje; spojne, ale roznica miedzy przebiegami.
3. (Spojnosc sidecara) `request.campaigns` plikow kampanii odzwierciedla tryb PIERWSZEGO pobrania (np. `newest` dla najnowszej, ktora potem uczestniczy w `all`); nie jest aktualizowane przy ponownym uzyciu. Nie szkodzi (dane kampanii poprawne), ale `request.campaigns` nie mowi, w jakim trybie plik zostal "potwierdzony".
4. (Biblioteka) Przy zamknieciu interpretera `MetadataCache.__del__` zglasza `ImportError: sys.meta_path is None, Python is likely shutting down` (Exception ignored) w skryptach uzywajacych `MetadataCache()` bez jawnego `close()`; kosmetyka.
5. (Dane GUGiK) AAIGrid (.asc) nie niesie CRS (rasterio `crs=None`) — CRS tylko w sidecarze; orto S8 PL-2000 TIF zglasza `ESRI:102177`, B/W 1992 ma WKT "Transverse Mercator; WGS84" (wlasne georeferencje GUGiK), a nie EPSG:2180/2179.
6. (Dane GUGiK) NMT 1 m PL-2000 jest rzadkie: znaleziono tylko S7 (7.125.11.13, 7.173.21.13) i S8 (8.193.13.13.4, 1:1000); arkusze PL-2000 NMPT 1 m brak (GUGiK 0,5 m). NMPT 1 m KRON86 ma jedna kampanie na arkusz (w skanowanych obszarach); NMPT EVRF2007 wielokampanijny np. M-34-41-A-a-1-2..1-4.
7. (Dane) CLI pozwala tylko na `--target-crs` EPSG:2180/5514/3045 (nie 2177/4326) — zgodnie z help; biblioteka tak samo.
8. Orto 5 cm (np. N-34-50-C-d-3-3 2024) = ~1 GB/arkusz; w tescie uzyto 0,25 m i 1:1000.

## Rozmiar danych

`du -sh` katalogu przebiegu: ~840 MB (nmt 193 MB, nmpt 74 MB, orto 465 MB, reszta wycinki/sidecary).
