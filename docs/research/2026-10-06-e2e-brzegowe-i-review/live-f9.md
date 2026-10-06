# F9: ponowny przebieg na zywo po naprawach (2026-10-06)

- **Data:** 2026-10-06, agent F9 (Sonnet), commit `b3945709252aa332c23f72eb8774677148de63b0` (develop, czyste drzewo)
- **df przed:** `<udzial>, uzyte 2,6G, wolne 98G`; po: uzyte 3,2G (F9 zajmuje 618 MB)
- **Dane:** `F=<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/f9/` (`out/f9N`, `logs/`, `scripts/`)
- **Wyrocznie:** `F/logs/ORACLE_F9.txt` (zapisane przed pierwszym uruchomieniem CLI)
- Cache: F9-1..3, 5-9 z cwd = korzen repo (cache repo, nie czyszczony); F9-4 z wlasnym cache w katalogu `scratchpad/f94` (patrz obserwacja O1).

## 1. Tabela werdyktow

| ID | Oczekiwane | Faktyczne | Werdykt |
|----|-----------|-----------|---------|
| F9-1 | CIR w `orto/pl_1992_cir/`, `kolor: CIR`, RGB nietkniety | CIR w `orto/pl_1992_cir/M-34/90/C/b/4/4/`, sidecar `kolor: CIR`, URL `84465_1602805`; RGB: sha256 `c83b8338...` i mtime bez zmian po kroku CIR | PASS |
| F9-2 | `Warning:` o niepelnej kampanii, rc 0, `full_sheet: false` | rc 0, Warning (cytat nizej), sidecar `full_sheet: false`, URL `84466_1602825` | PASS |
| F9-3 | Warning o niepelnej kampanii, `all_nodata: true`, `sheet_sources[].full_sheet`, skip powtarza ostrzezenie | wszystko zgodne, rc 0 w obu przebiegach | PASS |
| F9-4 | po `--force` rekord w cache = nowy; kolejny bez `--force` bierze nowy | stary rekord 2024 uzyty bez `--force` (81437); `--force`: 84466 + cache zaktualizowany; kolejny bez `--force`: 84466, 0 zapytan skorowidza | PASS |
| F9-5 | komunikat skip, nie `Downloaded to` | `Skipped M-34-90-C-b-4-4 - already exists at ...`, 0,36 s, rc 0 | PASS |
| F9-6 | `request.year == 2023` | `request.year: 2023` (i `min_density: 10` przy `--min-density 10`) | PASS |
| F9-7 | Warning o ukladzie pliku, EPSG:2180, `uklad: PL-2000:S7` | zgodne (cytaty nizej), URL 77912, segment `pl_2000_1m_evrf2007/7/125/11/19/` | PASS |
| F9-8 | `.zip` (PK) + sidecar obok | `bdot10k_teryt_0661.zip` (5 103 713 B = HEAD), naglowek `PK\x03\x04`, zawiera `.shp/.dbf/.prj/.cpg`, sidecar `.zip.meta.json` obok, brak `.gpkg` | PASS |
| F9-9 | regresja jak `live-2026-09-30.md` | wszystkie 5 sprawdzonych przypadkow zgodne (sekcja F9-9) | PASS |

Liczby: PASS 9, UWAGA 0, FAIL 0, BLOKADA 0. Uwagi pozaplanowe w sekcji 3 (O1-O5).

## 2. Dowody

### F9-1 / F9-2 / F9-5 (M-34-90-C-b-4-4, `F/out/f91/`)
Wyrocznia: patrz ORACLE. RGB przez CLI (15,1 s), potem `scripts/orto_api.py M-34-90-C-b-4-4 CIR <out>` w tym samym `--output`.
```
orto/pl_1992/.../M-34-90-C-b-4-4.tif          (+ .meta.json: kolor RGB, url .../84466/84466_1602825_..., full_sheet false)
orto/pl_1992_cir/.../M-34-90-C-b-4-4.tif      (+ .meta.json: kolor CIR, url .../84465/84465_1602805_..., full_sheet False)
```
stderr RGB (F9-2, `logs/F91_rgb.err`):
`Warning: najnowsza kampania GUGiK jest niepelna dla 1 arkuszy (M-34-90-C-b-4-4) — skorowidz deklaruje arkusz nie w calosci wypelniony trescia; plik moze miec duzo nodata/czerni (extra.source.full_sheet w sidecarze)`

Rerun (F9-5, `logs/F95_rerun.out`, 0,36 s, rc 0):
`Skipped M-34-90-C-b-4-4 - already exists at .../orto/pl_1992/M-34/90/C/b/4/4/M-34-90-C-b-4-4.tif` + powtorzone Warning o niepelnej kampanii (z sidecara). Brak `Downloaded to`.
Uwaga: po zakonczeniu F9-1 dodatkowo uruchomilem (nieplanowo) `--force -q`, ktory pobral RGB ponownie; dowod "RGB nietkniety" pochodzi sprzed tego kroku (sha/mtime w `logs/F91_rgb.mtime`).

### F9-3 (`F/out/f93/`)
Komenda: `download --bbox 637000,473000,637100,473100 --target-crs EPSG:2180 -o .../f93`, rc 0, 1,2 s. Arkusz zrodlowy: `84183_1852496_N-34-139-C-a-3-1.asc` (ncols 255, nrows 422, xllcenter 638819, czyli okno poza zadaniem).
stderr: `Warning: wycinek w calosci nodata — najnowsza kampania GUGiK jest niepelna dla 1 arkuszy (N-34-139-C-a-3-1) i nie pokrywa obszaru zadania (starsza kampania moze miec dane; extra.sheet_sources[].full_sheet)`
Sidecar wycinka `extra`: `"all_nodata": true`, `"sheet_sources": [{"godlo":"N-34-139-C-a-3-1","url":".../84183_1852496_...","layer":"SkorowidzeNMT2025","aktualnosc":"2025-10-21","full_sheet":false}]`, `nodata -9999.0`, EPSG:2180, pion EPSG:9651.
Rerun: `Skipped - already exists at ...` + to samo Warning z dopiskiem `(z sidecara istniejacego wycinka)`, rc 0, 0,37 s.

### F9-4 (cache, `F/logs/F94.log`, `F/scripts/f94.py`)
Cwd = `scratchpad/f94` (lokalny `.kartograf_cache.db`). Zimny przebieg zapisal rekord 2026; `MetadataCache.set_record("orto","RGB","none",godlo, ...)` podmienil go na rekord 2024 (`81437_1434887`, `SkorowidzeOrtofotomapy2024`, 0,25 m).
| krok | zadanie | zapytania | URL w sidecarze | URL w cache po kroku |
|---|---|---|---|---|
| b | bez `--force` | FILE 1 (0 skorowidza) | 81437 (2024-06-26) | 81437 |
| c | `--force` | CAPS 1, GFI 1 (2026), FILE 1 | 84466 (2026-04-25) | 84466 |
| d | bez `--force`, nowy katalog | FILE 1 (0 skorowidza) | 84466 | 84466 |
Porownanie z E2E-B C15 (B3 wracal do 2024): naprawa E14 dziala.

### F9-6 LAZ (`F/out/f96/`, `f96b/`)
`--bbox 637400,487000,637450,487050 --bbox-crs EPSG:2180 --country pl --product laz --year 2023`: 1 kafel `78044_1403296_N-34-139-A-c-1-1-3-4.laz` (zgodnie z wyrocznia), 61,7 s, rc 0. Sidecar `request`: `{'bbox': [...], 'bbox_crs': 'EPSG:2180', 'year': 2023}`. Z `--min-density 10`: `request` = `{..., 'year': 2023, 'min_density': 10}`. (Dokumentacja o nominalnej gestosci E16 nie byla sprawdzana na zywo; to tekst.)

### F9-7 (`F/out/f97/`)
`download 7.125.11.19`, rc 0, 5,4 s. stderr:
```
Sidecar .../7.125.11.19.asc: godlo 7.125.11.19 wskazuje EPSG:2178, ale wspolrzedne pliku (x = 567976) sa w EPSG:2180 — zapisano uklad pliku
Warning: 1 arkuszy GUGiK opublikowano w innym ukladzie niz wskazuje godlo: 7.125.11.19 (godlo: EPSG:2178, plik: EPSG:2180) — sidecar opisuje uklad pliku (horizontal_crs); deklaracja rekordu w extra.source.uklad
```
Plik: `xllcenter 567975.95 cellsize 0.9993671653521061` (naglowek ASC = EPSG:2180). Sidecar: `horizontal_crs EPSG:2180`, `vertical_crs EPSG:9651`, `extra.source.uklad "PL-2000:S7"`, URL `77912_1384976`, `aktualnosc 2023-03-17`. Sciezka `nmt/pl_2000_1m_evrf2007/7/125/11/19/` (uklad z godla, ADR-026).

### F9-8 (`F/out/f98/`)
TERYT 0661 (HEAD: 200, Content-Length 5 103 713; inne sprawdzone: 0262 5,9 MB, 0463 13,8 MB). `landcover download --source bdot10k --teryt 0661 --format SHP`, rc 0, 2,4 s. Pliki: `bdot10k_teryt_0661.zip` (5 103 713 B, naglowek `b'PK\x03\x04'`) i `bdot10k_teryt_0661.zip.meta.json` (`dataset pl.gugik.bdot10k`, EPSG:2180, `request {"teryt":"0661"}`).

### F9-9 regresja (`F/out/f99/`, `F/logs/F99_*`)
- godlo N-34-130-D-d-2-4 1m: rc 0, sidecar EPSG:2180/EPSG:9651, nodata -9999, URL `82710_1715397`, aktualnosc 2025-04-26, ASC 2252x2432 res 1; rerun `Skipped ... already exists`.
- wycinek `--bbox 639000,472800,639200,472900 --target-crs EPSG:2180` (4 arkusze): 201x101 px, res 1,0, EPSG:2180, nodata -9999, 100 % waznych; `sheet_sources` = 4 URL jak w E2E-B C14-a (a-3-1/-3 `84183_*` full_sheet false; a-3-2/-4 `83998_*` true); `Warning: najnowsza kampania GUGiK jest niepelna dla 2 arkuszy wycinka (N-34-139-C-a-3-1, N-34-139-C-a-3-3) ...`; rerun skip + ostrzezenie.
- Krakow 5 m `--bbox 536000,233000,541000,238000 --target-crs EPSG:2180`: rc 1, `Error: 8 z 9 arkuszy lezy na innej siatce pikseli ... (maks. przesuniecie 0.412 px) ... --target-crs EPSG:5514 albo EPSG:3045 ...` (zgodne z S5/12 z live-2026-09-30).
- ten sam z `EPSG:5514`: rc 0, `Info: 11 arkuszy o innej fazie siatki przeprobkowanych osobno (W1; ...)`, sidecar `off_grid_sheets` = 11, EPSG:5514, 5m (zgodne z S5/13).
- Dodatkowo: NMPT 1m N-34-139-A-c-1-1: rc 1 `Brak danych NMPT 1m ... GUGiK ma ten arkusz w 0.5 m`; PL-2000 `7.174.21` bbox: rc 1, hint `--scale 1:2000` i alternatywa PL-1992 (poprawne wg CLAUDE.md).

## 3. Nowe obserwacje (poza zakresem F9)

- **O1.** Cache SQLite WAL na udziale CIFS jest nieuzywalny: CLI z cwd w `f9/scripts/` (na katalog danych) zakonczylo sie `Error: OperationalError: database is locked`, pusty `.kartograf_cache.db` o 0 B. Potwierdza zalecenie CLAUDE.md (cache lokalnie); kontrakt F9 zalecal ten katalog, wiec do poprawy w kontrakcie. F9-4 przeprowadzony z lokalnym cwd w scratchpadzie.
- **O2.** `MetadataCache.__del__` (`kartograf/cache/metadata.py:440`) przy zamknieciu interpretera w skrypcie `python -I` drukuje `ImportError: sys.meta_path is None, Python is likely shutting down` (po `close()`); kosmetyczne.
- **O3.** Sidecar BDOT10k SHP nie zapisuje formatu (`request` = tylko `teryt`, `extra` = `{}`); przy ponownym uruchomieniu tej samej komendy wypisuje `Downloaded to` w 2,3 s (zdaje sie pobierac ponownie, bez `Skipped`) — nie badane dalej.
- **O4.** Dla wycinka z niepelnymi arkuszami (639000,472800,...) sidecar nie ma `all_nodata` (poprawnie, 100 % waznych), ale komunikat stdout o all_nodata w F9-3 jest wypisywany dwukrotnie (linia `Wycinek ... jest w calosci nodata` na stdout oraz `Warning:` na stderr, o troche innej tresci) — dubel informacyjny.
- **O5.** Wycinek F9-3 pochodzi z arkusza uciętego (255x422 px): starsza kampania ma dane (E2E-B C14-b); reguly wyboru ADR-028 nie zmieniono (decyzja uzytkownika), widocznosc E13 dziala.
