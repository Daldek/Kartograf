# E2E na zywo po ADR-030 — czesc B (LAZ, CZ, pogranicze, landcover/gleby), 2026-10-07

Kod: develop ec19478. Dane: `<katalog-danych>/kartograf/e2e/2026-10-07-adr030-full-B/data` (1,5 GB).

## Przypadki

| # | Produkt | XY / pion | Obszar | Komenda (skrot) | Wynik | Fakty |
|---|---|---|---|---|---|---|
| 1 | laz newest | PL-1992 / EVRF2007 | bbox 637200,486900,637500,487100 | `--product laz --country pl` | PASS | 1 kafel 2025/PL-1992 (`laz/pl_1992_evrf2007/...83230_1743191_...`), `Info:` o 3 pominietych kaflach (2022 PL-2000 x2, 2023 PL-1992), 50 MB, sidecar `extra.parent_request`, brak `request.campaigns`; powtorka = `0 tiles (1 skipped)` |
| 2 | laz `--year 2022` | PL-2000:S7 / EVRF2007 | j.w. | `--year 2022` | PASS | 2 kafle `laz/pl_2000_evrf2007/7/173/21/06/{1,2}`, sidecar `horizontal_crs EPSG:2178`, `request.year 2022`; ~250 MB/kafel |
| 3 | laz `--campaigns all` | PL-1992 | j.w. | `--campaigns all` | PASS | Found 4 (2x PL-2000:S7 2022, PL-1992 2023 i 2025), pobrano 1 nowy (2023), 3 skip; sidecar 2023 `request.campaigns: all`; selekcja biblioteka: sup=0 |
| 4 | laz `--campaigns all --min-year 2024` | PL-1992 | j.w. | | PASS | Found 1 (2025), skip |
| 5 | laz `--year` + `--min-year` | - | j.w. | `--year 2022 --min-year 2020` | PASS | `Error: --min-year i --year wykluczaja sie (LAZ)`, kod 1 |
| 6 | laz `--min-year 2030` | - | j.w. | | PASS | `Error: No LAZ tiles found ... (sprawdz obszar, --year, --min-year ...)`, kod 1 |
| 7 | laz KRON86 + `--min-year 2015` | PL-1992 / EPSG:9650 | bbox 714741,245725,714841,245825 (Rzeszow) | `--vertical-crs KRON86 --min-year 2015` | PASS | 2 kafle 2017 w `laz/pl_1992_kron86/M-34/{68/D,69/C}`, sidecar `vertical_crs EPSG:9650`, `request.min_year 2015`, parent_request; nagl. LASF |
| 8 | laz druga strefa PL-2000 | PL-2000:S6 / EVRF2007 | bbox 477257,720713,477357,720813 (Gdansk) | `--year 2022` | PASS | 1 kafel `6.220.26.02.1`, `laz/pl_2000_evrf2007/6/...`, `horizontal_crs EPSG:2177`; dedup w roku 2022 pominal PL-1992 2022 (sup=1) |
| 9 | nmt CZ TM33 | EPSG:3045 / Bpv (8357) | 302_5550 | `--country cz` | PASS | `nmt/cz_dmr5g_bpv/302/5550`, 1000x1000, 2 m, nodata -9999, 6,5% waznych (kafel graniczny — Niemcy), sidecar zgodny; powtorka Skipped |
| 10 | nmt CZ TM33 EVRF2007 | 3045 / EPSG:5621 | 302_5550 | `--vertical-crs EVRF2007` | PASS | `nmt/cz_dmr5g_evrf2007/...`, roznica do Bpv 0,1323-0,1324 m (stala), `transform.vertical` = pinned Bpv->EVRF2007 |
| 11 | nmt CZ SM5 | 5514 / Bpv | CTES96 | `--resolution 5m` | PASS | `nmt/cz_dmr4g_bpv/CTES/96`, 400x500, 5 m, 99,9% waznych |
| 12 | nmt CZ bbox + target | 2180 / Bpv | bbox 18.55,49.60,18.60,49.65 (4326) | `--country cz --target-crs EPSG:2180` | PASS | `nmt/cz_dmr5g_bpv/bbox/467492..tif`, 2789x1821, 2 m, 100% waznych, horizontal_crs 2180 |
| 13 | nmt CZ bbox 5514 ujemny | 5514 / Bpv | `--bbox=-447000,-1114000,-446000,-1113000` | `--resolution 5m` | PASS | 200x200, 5 m, 51,7% waznych (granica), parent_request countries CZ |
| 14 | blokady CZ | | | `--campaigns all` (godlo), `--min-year 2020` (bbox), `--vertical-crs KRON86` | PASS | `Error: CZ (CUZK) nie ma kampanii ...` kod 1 (x2); `Error: KRON86 nie jest osiagalny dla CZ (siatki GUGiK niepubliczne)` kod 1 |
| 15 | pogranicze auto newest | CZ 5514/Bpv + PL-1992/EVRF2007 | bbox 18.60,49.752,18.65,49.768 (4326) | `--bbox ... --bbox-crs EPSG:4326` | PASS | wycinek CZ `nmt/cz_dmr5g_bpv/bbox/-448602..tif` + 2 arkusze PL M-34-74-C-a-4-4, M-34-74-C-b-3-3; wspolny `parent_request` countries [CZ, PL]; sidecar PL `link: hardlink`, `link_target` -> kampanie/2025-06-22_83852 |
| 16 | pogranicze `--campaigns all` | | j.w. | `--campaigns all` | PASS | `Info: --campaigns/--min-year dotycza tylko czesci PL ...` raz; CZ `Skipped`; `Downloaded 10 campaign files for 2 sheets ... (2 already existed)` = 12 plikow .asc w 6 kampaniach (74523, 74969, 75091, 75748, 79991, 83852) zgodne z dyskiem; sidecar kampanii: `extra.campaign`, `request.campaigns: all` |
| 17 | pogranicze target+EVRF | 2180 / CZ EPSG:5621, PL EPSG:9651 | j.w. | `--target-crs EPSG:2180 --vertical-crs EVRF2007` | PASS | dwa wycinki: `cz_dmr5g_evrf2007/bbox/471194.66_209462.30_...tif` (2 m, 898x1804, 30,9% waznych) i `pl_1992_1m_evrf2007/bbox/...` (1 m, 82,5%), te same bounds x, wspolny parent_request; arkusze PL `○` (juz byly) |
| 18 | bdot10k GPKG | | TERYT 1465 | `landcover download --source bdot10k --teryt 1465` | FAIL | patrz BLAD 1 |
| 19 | bdot10k SHP | EPSG:2180 | TERYT 1465 | `--format SHP` | PASS | zip 82 MB, testzip OK, 350 plikow, sidecar |
| 20 | corine 2018 | WMS PNG 3857 | N-34-130-D | | PASS | fallback: `extra.fallback=wms_png`, PNG poprawny (11,9 kB), komunikat o braku credentials |
| 21 | soilgrids soc | 4326 | N-34-130-D | | PASS | GTiff 77x123 int16, 0-1423, sidecar (nodata null) |
| 22 | hsg --stats | 4326 | N-34-130-D | | PASS | GTiff 77x123 uint8 1-3, nodata 0; statystyki A 2,2% / B 97,8% / C 0% |
| 23 | list-sources, list-layers soilgrids, cache stats | | | | PASS | `Record entries: 14, Campaign entries: 527`; cache stats dziala |

Razem: 22 PASS, 1 FAIL (BDOT10k GPKG na CIFS), 0 SKIP.

## BLEDY

1. `kartograf landcover download --source bdot10k --teryt 1465 -o <katalog-danych>/kartograf/e2e/2026-10-07-adr030-full-B/data/landcover` (domyslny `--format GPKG`)
   - Oczekiwane: `bdot10k_teryt_1465.gpkg` + sidecar. Faktyczne: `Error: OperationalError: database is locked`, kod 1, powtarzalne (3/3 prob, rowniez z `KARTOGRAF_DEBUG=1`).
   - Traceback: `bdot10k.py:541 _extract_gpkg_from_zip -> :579 _merge_gpkg_files -> :639 _copy_gpkg_layer: cursor.execute(create_sql)`.
   - Przyczyna (hipoteza, niezweryfikowana na dysku lokalnym — dane tylko na katalog danych): `_merge_gpkg_files` buduje wynikowy GPKG (SQLite) bezposrednio w `--output`, a udzial CIFS nie obsluguje blokad SQLite (jak WAL cache). Nie jest to regresja ADR-030, ale uzytkownik z `-o` na CIFS/SMB ma nieczytelny blad. Obejscie: `--format SHP` (dziala) albo budowa GPKG w katalogu tymczasowym lokalnym + `os.replace`/kopia.
   - Zadnych sladow po porazce (brak polowicznego .gpkg ani journala).

## OBSERWACJE

- `soilgrids hsg` zapisuje `hsg/hsg_N-34-130-D.tif` BEZ sidecara `.meta.json` (regula: kazde udane pobranie ma sidecar; HSG to wynik obliczen, wiec byc moze swiadome — do decyzji; sidecary maja corine/soilgrids/bdot10k).
- Sidecar CZ po `--vertical-crs EVRF2007` ma `vertical_source: "native"` (opisuje kanal zrodla), a faktyczna transformacje pionowa niesie `transform.vertical`; pole moze mylic.
- CIFS: `stat` raportuje `st_nlink=1` dla sciezki standardowej i kampanii mimo tego samego i-wezla (`os.path.samestat` True, np. 5380) — hardlink dziala, ale licznik z CIFS jest zaniżony; kontrola przez numer i-wezla.
- Brak symlinkow w danych (`find -type l` = 0).
- LAZ: nazwa pliku niesie id kampanii (`<id>_<nr>_<godlo>.laz`), wiec 2023 i 2025 tego samego godla (PL-1992) nie koliduja; sidecar kafla pobranego bez `--campaigns` nie dostaje `request.campaigns`; po pozniejszym `all` kafel 2025 jest skip, wiec sidecar zachowuje stare `request`.
- Tryb `all` w LAZ zwraca kafle PL-2000:S7 2022 i PL-1992 2022/2023 z tego samego obszaru (bez deduplikacji) — zgodnie z opisem `--campaigns`.
- Skip wycinka bbox (CZ) drukuje `Skipped - already exists at ...` bez godla/nazwy (poprawne, nie ma godla).
- Dane GUGiK: Rzeszow dla KRON86 ma najnowszy rocznik 2017, dla EVRF2007 2025 (rozne kampanie wg ukladu pionowego); kafle LAZ 50-260 MB (gestosc 12-15).
- Info o pominietych kaflach LAZ ma pelna liste z powodem (pokryty przez ...) — czytelne.
- Blokady CZ (`--campaigns`/`--min-year`/KRON86) zwracaja blad natychmiast (ok. sekundy); nie mierzono ruchu sieciowego.

## Rozmiar danych

`du -sh <katalog-danych>/kartograf/e2e/2026-10-07-adr030-full-B` = 1,5 GB (w tym kampanie NMT PL ~420 MB, LAZ ~0,9 GB).
