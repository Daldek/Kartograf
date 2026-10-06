# E2E-B: orto, LAZ, wycinek, cache (C12-C15, C17)

- **Data:** 2026-10-06, agent E2E-B (Sonnet), commit `55070f8` (develop, czyste drzewo)
- **df:** `<udzial>, uzyte 128K -> po rundzie ~2,3 GB` (budzet 20 GB niewykorzystany)
- **Dane:** `<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/b/` (`raw/<Cx>/` surowe odpowiedzi, `out/`, `logs/`, `scripts/`)
- **Wyrocznia F2** zapisana przed uruchomieniem: `b/logs/ORACLE_F2_2227.txt`
- Cache SQLite repo nie byl czyszczony. Testy C15 szly z cwd w scratchpadzie (wlasny `.kartograf_cache.db`); zapytania liczone przez podmiane `requests.Session.send` (`b/scripts/cli_count.py`).
- Uwaga srodowiskowa: udzial jest `noexec` (skrypty przez `bash skrypt`).

## 1. Tabela zbiorcza

| ID | Przypadek | Werdykt |
|----|-----------|---------|
| C12-a | orto RGB 0,07 m, rocznik 2026 (M-34-90-C-b-4-4) | **UWAGA** (plik w 96,9 % czarny, `full_sheet=false`, bez ostrzezenia) |
| C12-b | orto CIR 0,07 m 2026 (API) | UWAGA (jw., 96,3 % czarne) |
| C12-c | orto RGB 0,05 m 2025 vs CIR 2024 0,25 m (N-34-139-A-c-1-1) | PASS (+ UWAGA informacyjna: RGB i CIR z roznych kampanii) |
| C12-d | orto RGB 0,10 m (N-34-130-D-d-2-4) | PASS |
| C12-e | orto PL-2000 1:5000, 0,05 m, EPSG:2178 (7.173.21.01.2) | PASS |
| C12-f | RGB i CIR tego samego arkusza w jednym katalogu | **FAIL** (skip zwraca RGB na zadanie CIR) |
| C12-g | PL-2000 1:10000 z nowszymi potomkami (7.173.21.01) | UWAGA (tylko z rekordow, bez pobrania) |
| C13-a | LAZ domyslnie, uklad 1992 + 2000 w jednym obszarze | PASS (+ UWAGA: zdublowany obszar 2022/2025) |
| C13-b | `--year 2023` | PASS |
| C13-c | `--min-density 13` / `20` | PASS |
| C13-d | `--vertical-crs KRON86` (rok 2018 zamiast 2012) | PASS |
| C13-e | `--year 2009` / `2012` (EVRF) / `2026` | PASS |
| C13-f | sidecar LAZ vs naglowek LAS | PASS (+ UWAGI drobne: `gestosc` nominalna, `request` bez `--year`/`--min-density`) |
| C14-a | wycinek z 4 arkuszy: 2026 + 2025-10-21 | PASS (`sheet_sources` zgodne z wyrocznia) |
| C14-b | wycinek w arkuszu, gdzie wygrywa ucieta kampania | **UWAGA** (all_nodata, a starsza kampania ma 100 % danych) |
| C14-c | `off_grid_sheets` | nie znaleziono (patrz sekcja 5) |
| C15 | cache rekordow (orto, NMT, brak pokrycia) | PASS; UWAGA: `--force` nie odswieza cache |
| C17 | rerun/skip, `parent_requests` | PASS; UWAGA: skip pustego wycinka milczy; "Downloaded to" przy skip |

Liczby: PASS 13 (z pozycji C12-c/d/e, C13-a..f, C14-a, C15, C17 liczone bez UWAG), UWAGA 6, FAIL 1, BLOKADA 0. (Wiersze z "PASS (+ UWAGA)" liczone jako PASS; UWAGI dodatkowe w sekcji 4.)

## 2. Wymaganie E11: wartosci pola ukladu (repr)

Zrodlo: WFS LAZ `uklad_xy` z `raw/C13/*_rows.json` (probki: Krakow, 2 w Warszawie, Poznan, Gdansk, Wroclaw, Rzeszow, Lublin: 9 obszarow, 2 uslugi, 19 roczniow) i skorowidz orto `ukladWspolrzednych` z `raw/C12/*.html`.

| `repr(uklad_xy)` (LAZ) | wystapien rekordow | unikalnych kafli (URL) | segment storage | `horizontal_crs` sidecara |
|---|---|---|---|---|
| `'PL-1992'` | 246 | 242 | `laz/pl_1992_<vcrs>` (zaobserwowane) | `EPSG:2180` (zaobserwowane) |
| `'PL-2000:S6'` | 40 | 40 | `laz/pl_2000_<vcrs>` (nie pobrano; funkcje offline) | `EPSG:2177` (offline) |
| `'PL-2000:S7'` | 13 | 12 | `laz/pl_2000_evrf2007/7/173/21/06/2/` (zaobserwowane) | `EPSG:2178` (zaobserwowane; LAS GeoKey 3072 = 2178) |
| `'PL-2000'` bez strefy | **0** | 0 | (offline: `2000`) | (offline: `horizontal_crs_for_uklad` = `None` -> kanal = EPSG:2180) |
| inne / biale znaki / wielkosc liter | **0** | 0 | | |

Orto `ukladWspolrzednych` (wystapienia rekordow w plikach, z powtorzeniami): `'PL-1992'` 127, `'PL-2000:S7'` 36, `'PL-2000:S6'` 2, `'PL-2000:S8'` 2. Zadnych wartosci bez strefy ani z bialymi znakami. Sidecar orto PL-2000 S7: `EPSG:2178` (zgodne z CRS pliku, `AUTHORITY EPSG 2178`).

Wniosek: w 294 unikalnych kaflach LAZ i ~167 rekordach orto wartosc `'PL-2000'` bez strefy NIE wystepuje. Rozjazd parserow (D3) jest utajony: offline `LazTile.uklad('PL-2000')` = `2000`, a `horizontal_crs_for_uklad('PL-2000')` = `None` (sidecar dostalby EPSG:2180 przy segmencie `pl_2000`). Rozstrzygniecie: w danych na dzis nie wystepuje, ale probka to ~9 regionow (nie cala Polska).

## 3. Przypadki z dowodami

Sciezka bazowa `B=<katalog-danych>/kartograf/e2e/2026-10-06-brzegowe/b`.

### C12 orto

Surowe: `B/raw/C12/<godlo>_<warstwa>.html`, `caps.xml`, `head_orto.txt`. Warstwy: 2026, 2025, 2024, Starsze (+ Zasiegi*). Warstwa 2026 ma realne rekordy (np. M-34-90-C-b-4-4, 7.125.14.16 0,03 m PL-2000 1,06 GB, N-34-109-D-a-1-1 0,05 m); roczniki rozne od `aktualnosc` (rekord 2025-04-03 z dt_pzgik 2026-03 lezy w warstwie 2025).

| Przypadek | Wyrocznia (z rekordu) | Faktycznie | W |
|---|---|---|---|
| O1 M-34-90-C-b-4-4 RGB (CLI) | warstwa 2026, 2026-04-25, dt 2026-08-27, 0,07 m, `84466_1602825`, rc 0 | identyczne; plik 45 511 794 B, 33123x33822 px, res 0,07, EPSG:2180, 3 pasma uint8; sidecar `source` zgodny (W1-W3); rc 0, brak stderr | W1-W5, W7-W8 OK |
| O2 ten sam, CIR (API `color="CIR"`) | `84465_1602805`, CIR | zgodne | OK |
| O3 N-34-139-A-c-1-1 RGB (CLI) | 2025-04-27, 0,05 m, `83235_1485417` (1 119 359 310 B), nie 2024 | zgodne; 43948x47513 px, res 0,05; ~7,5 min (transfer) | OK |
| O4 ten sam, CIR | brak CIR w 2025 -> 2024-07-18 0,25 m `81434_1416956` | zgodne (`layer=...2024`, `resolution_m` 0,25) | OK; UWAGA info: RGB (2025, 0,05) i CIR (2024, 0,25) to rozne kampanie i rozdzielczosci, nigdzie nie sygnalizowane |
| O5 N-34-130-D-d-2-4 RGB | 2025-04-26, 0,10 m `82712_1482344` | zgodne; 22528x24326 px, res 0,1 | OK |
| O6 7.173.21.01.2 (PL-2000) | Starsze, 2022-05-09, 0,05 m `77946_1195085`, EPSG:2178 | zgodne; 16000x10000 px, bounds 7500800..7501600 x 5789500..5790000 = godlo (EPSG:2178); sciezka `orto/pl_2000/7/173/21/01/2/` | OK |

**C12-a UWAGA (dowod):** plik `B/out/orto/orto/pl_1992/M-34/90/C/b/4/4/M-34-90-C-b-4-4.tif` ma 96,9 % pikseli (0,0,0) (pomiar dokladny blokami), srednia kanalow ~3/255, max 214. Rekord ma `calyArkuszWypelnionyTrescia`=NIE (`extra.source.full_sheet=false`). Starsza kampania tego arkusza (2024-06-26 RGB 0,25 m, `81437_1434887`, 47 MB, warstwa 2024) jest kompletna (sprawdzono pobraniem w C15: `B/out/c15b`). Zgodnie z ADR-028 ("bez preferencji full_sheet") wygrywa 2026, wiec uzytkownik dostaje prawie czarny raster, rc 0, bez `Warning:`; sidecar `nodata: null` (brak tagu nodata, czern = 0). Kod dziala zgodnie z deklaracja; szkodzi uzytkownikowi (definicja UWAGA). CIR tego arkusza: 96,3 % czerni.

**C12-f FAIL (dowod):** `B/logs/` (komenda w tej sesji): po O1 (`out/orto`, RGB) wywolanie `DownloadManager(out, provider=GugikOrtoProvider(color="CIR")).download_sheet("M-34-90-C-b-4-4")` zwrocilo ten sam plik (mtime 22:28:12 bez zmian, 45 511 794 B, `SOURCE None`, 0,4 s, zero zapytan). Sidecar nadal `kolor: "RGB"`, URL `84466`. Prawdziwy CIR do osobnego katalogu: `out/orto_cir/` (URL `84465`, 45 804 722 B). Przyczyna: segment storage `orto/pl_{uklad}` nie rozroznia wariantu koloru, a skip patrzy tylko na istnienie pliku. Deklaracja (README, SCOPE, ADR-028): CIR "na jawne zadanie" - tu zadanie zwraca po cichu plik RGB. Zwrotnie: pobranie CIR do katalogu z RGB trafia pod ten sam sciezke i bylby skipniety/zderzony.

**C12-g UWAGA (tylko rekordy):** `B/raw/C12/7.173.21.01*.html`. Dla 7.173.21.01 (1:10000) wygrywa 2021-04-28 0,05 m (`75063`), a potomki 7.173.21.01.2/.4 maja 2022-05-09 (`77946`), a ten sam obszar w PL-1992 ma rekord 2025 (0,05 m). Zgodne z ADR (token calego godla), ale uzytkownik PL-2000 dostaje najstarsza kampanie. Nie pobierano.

Pasma: wszystkie TIF-y maja 3 pasma, `colorinterp` red/green/blue takze dla CIR (pliki GUGiK nie oznaczaja NIR); wariant wskazuje tylko `extra.source.kolor`. Sidecar orto: `resolution: null` (rozdzielczosc tylko w `extra.source.resolution_m`), `nodata: null`.

### C13 LAZ

Surowe: `B/raw/C13/{waw,w2,krk,poz,gdn,wro,rze,lub}_*.xml`, `*_rows.json`, `head_laz.txt`, `caps_*.xml`; naglowki LAS: `B/logs/L1_lasinfo.txt`, `L2_L4_lasinfo.txt`. Uslugi: EVRF2007 lata 2018-2026, KRON86 2010-2019.

Obszar `--bbox 637400,487000,637450,487050 --bbox-crs EPSG:2180 --country pl --product laz` (Warszawa):

| Wyrocznia | Faktycznie |
|---|---|
| L1 domyslnie: 2 kafle: `7.173.21.06.2` (2022, 15 p/m2, `PL-2000:S7`, `77941_1396678`) + `N-34-139-A-c-1-1-3-4` (2025 a nie 2023, 12 p/m2, `PL-1992`, `83230_1743191`); rc 0 | zgodne; sciezki `laz/pl_2000_evrf2007/7/173/21/06/2/` i `laz/pl_1992_evrf2007/N-34/139/A/c/1/1/3/4/`; 131 s |
| L2 `--year 2023`: 1 kafel `78044_1403296` | zgodne (203 MB, 84 s) |
| L3 `--min-density 13`: tylko kafel 2022; `20`: `Error: No LAZ tiles found...` rc 1 | zgodne (skip istniejacego; rc 1 bez sieci pobran) |
| L4 `--vertical-crs KRON86`: 1 kafel rok 2018 (nie 2012) `70707_846000`, `laz/pl_1992_kron86/`, EPSG:9650 | zgodne; WFS podaje `format=LAS` mimo `.laz`, plik to LAZ (fmt 3, laszip) |
| L5 `--year 2009`/`2012` (EVRF): `rocznik ... nie istnieje w usludze EVRF2007 (dostepne: 2026..2018)` rc 1; `--year 2026`: warstwa istnieje, 0 obiektow -> `No LAZ tiles found` rc 1 | zgodne |

Weryfikacja LAS vs sidecar (W4/W5): kafel 2022: LAS 1.2, GeoKey 3072=2178, X 7500800..7501600 (EPSG:2178), 50 658 462 pkt; sidecar `EPSG:2178`, `EPSG:9651`. Kafle 1992: GeoKey 3072=2180 (2025, 2023), 2018 KRON86 bez GeoKey (WKT puste): CRS pliku nieweryfikowalny, sidecar `EPSG:2180`/`EPSG:9650` z WFS. Zakres XY pliku pokrywa bbox kafla z WFS (PASS W8). Pionu nie ma w naglowkach (brak GeoKey 4096), pion tylko z `uklad_h` WFS.

UWAGI LAZ (nie FAIL):
1. Zdublowany obszar: dedup po `godlo` nie laczy kafli roznych ukladow; ten sam punkt dostaje kafel 2022/PL-2000 (250 MB, 15 p/m2) i 2025/PL-1992 (50 MB). Docstring mowi o dedup "per godlo", wiec zgodne, ale "najnowszy rok" nie jest gwarantowany na obszar.
2. `gestosc` w sidecarze = nominalna z `char_przestrz`; faktycznie kafel 2022 ~119 p/m2 (50,66 mln pkt / ~0,42 km2), kafel 2023 ~92 p/m2 przy nominale 12. `--min-density` filtruje wg nominalu.
3. Sidecar `request` zawiera tylko bbox: brak `year`/`min_density` (rok tylko w `extra.rok`).
4. LAZ nie uzywa cache rekordow (parametr `cache` jest placeholderem) - C15 dla LAZ nie dotyczy.

### C14 wycinek (nmt 1 m EVRF2007, `--target-crs EPSG:2180`)

Surowe: `B/raw/C14/N-34-139-C-a-3-*_EVRF2007_*.html`, `raw/C14/direct/*.asc`.

- **C14-a** `--bbox 639000,472800,639200,472900` -> 4 arkusze. Wyrocznia z rekordow: a-3-1 `84183_1852496` (2025-10-21, NIE pelny), a-3-2 `83998_1841627` (2026-04-05), a-3-3 `84183_1852498` (2025-10-21, NIE), a-3-4 `83998_1841628` (2026-04-05). Faktycznie `extra.sheet_sources` = dokladnie te 4 URL i `layer`/`aktualnosc` (`out/c14/.../bbox/639000_472800_639200_472900.tif.meta.json`); wycinek 201x101 px, res 1,0, EPSG:2180, `nodata -9999`, 100 % waznych pikseli; rc 0; 37 s. PASS. (`sheet_sources` nie niesie `full_sheet` ani `dt_pzgik`, kolejnosc = kolejnosc ukonczenia.)
- **C14-b UWAGA:** arkusz a-3-1 ma dwa rekordy w warstwie 2025: pelny 2025-04-27 (`83233_1744736`, 36 MB, 2204x2377, 94,6 % waznych) i nowszy ucięty 2025-10-21 (`84183_1852496`, **691 194 B, 255x422 px**, xllcenter 638819, 41 % waznych; zakres to male okno, nie godlo - W8 dla pliku zrodlowego nie spelnione). Wygrywa ucięty (ADR-028). `--bbox 637000,473000,637100,473100` (wewnatrz a-3-1, poza oknem): oracle z plikow zrodlowych: ucięty 0 % waznych, pelny 100 %. CLI: rc 0, `Warning: wycinek w calosci nodata ... (brak danych GUGiK / obszar poza pokryciem)` zgodnie z deklaracja all_nodata, ale tresc komunikatu jest mylaca (GUGiK ma dane w starszej kampanii). Sidecar (`out/c14b/.../bbox/637000_473000_637100_473100.tif.meta.json`): brak flagi `all_nodata`, brak `missing_sheets` (to nie brak arkusza), `sheet_sources` bez `full_sheet`. To jest przypadek C5 w trybie wycinka.
- **C14-c** `off_grid_sheets` / `missing_sheets`: nie wystapily w tej rundzie (siatka 1 m jednej kampanii/sasiednich kampanii zgodna w EPSG:2180; wczesniejsza runda pokryla S5 5 m).

### C15 cache rekordow

Logi: `B/logs/C15_A.log`, `C15_B.log`, `C15_D.log`, `C15_N.log`.

| Krok | Zapytania | Wynik |
|---|---|---|
| A1 orto zimny | CAPS 1, GFI 1 (warstwa 2026 koncy), FILE 1 | OK |
| A2 rerun (plik jest) | 0, 0,0 s | skip |
| A3 plik skasowany, bez `--force` | **tylko FILE 1**, 0 skorowidz | ten sam plik (sha256 `c83b8338...` = A1/O1) |
| A4 `--force` | CAPS 1, GFI 1, FILE 1 | ten sam sha |
| D1/D2/D3 brak pokrycia (N-33-44-C-a-1-4, morze) | zimny: CAPS 1 + GFI 4 (cztery warstwy); cieply: **0** zapytan, ten sam `Error: Brak ortofotomapy RGB...` rc 1; `--force`: ponownie CAPS+GFI 4 | PASS |
| N1-N4 NMT wycinek (4 arkusze) | zimny: CAPS 1, GFI 6, FILE 4; N2 (arkusze sa) 0 zapytan; N3 (skasowany a-3-1+wycinek): FILE 1 bez skorowidza; `--force`: CAPS 1, GFI 6, FILE 4, ASC bit w bit takie same | PASS |

**UWAGA (cache):** `--force` omija cache (CLI przekazuje `cache=None`), ale go NIE odswieza. Dowod: wstrzyknieto przestarzaly rekord (2024) do cache -> B1 (bez `--force`) pobiera 2024 (`81437`), B2 (`--force`, inny katalog) pobiera aktualne 2026 (`84466`), B3 (bez `--force`, inny katalog) znowu 2024 (`out/c15b`, `c15c`, `c15d`). Zgodne z literalnym "omija cache", ale po "zmianie kampanii" uzytkownik musi dawac `--force` przy kazdym przebiegu do wygasniecia TTL 7 d.

### C17 rerun/skip

`B/logs/C17_before.txt`, `C17_after_a.txt`, `C17_after_b.txt` (sha256 + mtime wszystkich plikow `out/c14`).
- C17a identyczne zadanie: `Skipped - already exists`, rc 0, 0,46 s; **zadnych zmian** w sha/mtime plikow (wycinek, ASC, sidecary). PASS.
- C17b inne `--bbox` na tych samych 4 arkuszach: wszystkie `○` (reuse), ASC bez zmian; sidecary 4 arkuszy dostaly `extra.parent_requests=[{bbox 639050,472800,639150,472880,...}]` przy zachowanym `parent_request` (oryginalny); nowy wycinek ma wlasny `parent_request`. PASS (zgodne z CLAUDE.md).
- C17c rerun pustego wycinka (C14-b): `Skipped - already exists`, rc 0, **bez `Warning:`**; plik w calosci nodata zostaje cicho. Zgodne z "skipped nie czyta ponownie rastra", ale brak sladu w sidecarze (UWAGA).
- Kosmetyka: godlo pojedynczego arkusza przy skip (A2, orto) wypisuje `Downloaded to <plik>` (`cli/download_cmd.py:1000` wypisuje to niezaleznie od skip; inne galezie maja `Skipped`). UWAGA.

## 4. Lista FAIL / UWAGA

- FAIL C12-f: CIR i RGB tego samego arkusza dziela sciezke; zadanie CIR przy istniejacym RGB cicho zwraca RGB.
- UWAGA C12-a: najnowszy rekord `full_sheet=false` daje 96,9 % czarnego orto (rc 0, brak ostrzezenia, sidecar `nodata null`).
- UWAGA C14-b: wygrywa 691 KB ucięty arkusz NMT (okno 255x422); wycinek all_nodata mimo pelnych danych w starszej kampanii; komunikat "brak danych GUGiK" mylacy; sidecar bez `all_nodata`/`full_sheet`.
- UWAGA C15: `--force` nie odswieza cache rekordow.
- UWAGA C17: skip pustego wycinka milczy; `Downloaded to` przy skip.
- UWAGA C12-g / C13: PL-2000 1:10000 bierze starsza kampanie niz potomki; LAZ dubluje obszar kaflami 2022/PL-2000 i 2025/PL-1992; `gestosc` nominalna; `request` sidecara LAZ bez `--year`/`--min-density`.

## 5. Nie znaleziono w danych

- `PL-2000` bez strefy (i inne warianty zapisu `uklad_xy`): 0 z 294 unikalnych kafli / 301 rekordow LAZ w 9 obszarach.
- Orto: dwa rekordy tej samej kampanii i barwy o roznej rozdzielczosci (0,05/0,10/0,25) w jednym arkuszu: nie wystapily; rozdzielczosci roznia sie kampaniami. Orto `B/W` tylko w "Starsze" (nie pobierano).
- Remis `aktualnosc` w orto: 0 z 11 sprawdzonych arkuszy (M-34-76-A-a-1-1, N-34-139-A-c-1-1, N-34-130-D-d-2-4, N-34-139-C-a-2-2, M-34-51-C-d-1-1, M-34-90-C-b-4-4, 7.173.21.01, 7.173.21.01.2, 7.125.14.16, + 2 inne).
- `off_grid_sheets`, `missing_sheets` w wycinku 1 m EPSG:2180: 0 z 2 wycinkow.
- LAZ z ta sama `godlo` w dwoch kampaniach tego samego roku: 0 (pary: 2012/2023 Krakow, 2018/2023/2025 Warszawa).
- Sondowanie 2026 w warstwie orto: 11 punktow z zasiegu 2026, 7 z rekordami.

## 6. Propozycje dla rejestru wymagan i testow offline

Nowe wymagania (propozycje): E12 orto/LAZ - wariant (RGB/CIR) jest czescia tozsamosci pliku (sciezka lub skip sprawdza `extra.source.kolor`); E13 rekord `full_sheet=false` jest widoczny dla uzytkownika (Warning albo pole w sidecarze / `sheet_sources`); E14 `--force` odswieza cache; E15 sidecar rejestruje `all_nodata`.

| Wzorzec | Surowa fixtura (pelna sciezka) | Asercja testu offline |
|---|---|---|
| C12-f CIR vs RGB, skip | `B/raw/C12/M-34-90-C-b-4-4_SkorowidzeOrtofotomapy2026.html` (RGB+CIR 0,07 m 2026) | `GugikOrtoProvider(color="CIR")` + istniejacy plik RGB w sciezce: wynik NIE jest po cichu plikiem RGB (rozne sciezki albo blad/`Info`); sidecar `kolor` = `CIR` |
| C12-a `full_sheet=false` | jw. (`calyArkuszWypelnionyTrescia` NIE) | `select_sheet_record` zwraca rekord 2026, a CLI/manager emituje `Warning:` o niepelnym arkuszu (po wprowadzeniu E13); `extra.source.full_sheet is False` |
| C12 brak CIR w nowszej warstwie | `B/raw/C12/N-34-139-A-c-1-1_SkorowidzeOrtofotomapy2025.html` + `..._2024.html` | CIR -> `layer=...2024`, `resolution_m=0.25`; RGB -> `layer=...2025`, `0.05` |
| C12 token godla | `B/raw/C12/M-34-90-C-b-4-4_SkorowidzeOrtofotomapyStarsze.html` (zawiera `M-34-90-C-b-4-4-4` i `M-34-90-C-b-4`) | zadanie `M-34-90-C-b-4-4` nigdy nie wybiera rekordow potomnych/nadrzednych |
| C12 PL-2000 1:10000 | `B/raw/C12/7.173.21.01_SkorowidzeOrtofotomapyStarsze.html` | wybor `75063_1038529` (2021), a potomki 2022 ignorowane; ewentualnie hint (po decyzji) |
| C13 dwa uklady w jednym obszarze | `B/raw/C13/w2_EVRF2007_2022.xml`, `w2_EVRF2007_2025.xml`, `w2_EVRF2007_2023.xml`, `w2_KRON86_2018.xml`, `w2_KRON86_2012.xml` | `discover_tiles` EVRF: 2 kafle (`7.173.21.06.2` rok 2022, `N-34-139-A-c-1-1-3-4` rok 2025); `--year 2023` 1 kafel `78044_1403296`; KRON86: rok 2018; `min_density=13` -> tylko PL-2000 |
| C13 format `LAS` mimo `.laz` | `B/raw/C13/w2_KRON86_2018.xml` | `LazTile.filename` konczy sie `.laz`; sidecar bez bledu |
| E11 wartosci `uklad_xy` | `B/raw/C13/waw_EVRF2007_2022.xml` (`PL-2000:S7`), `B/raw/C13/poz_EVRF2007_2021.xml` (`PL-2000:S6`), `krk_EVRF2007_2023.xml` (`PL-1992`) | test parametryzowany: `LazTile.uklad` i `horizontal_crs_for_uklad` zgodne dla `PL-1992`/`PL-2000:S6..S8`; test kontraktowy: `LazTile.uklad(x)=="2000"` => `horizontal_crs_for_uklad(x)` nie jest `None` (dla `'PL-2000'` bez strefy aktualnie pada - rozjazd D3, nie wystepuje w danych) |
| C14 rozne kampanie w jednym wycinku | `B/raw/C14/N-34-139-C-a-3-{1,2,3,4}_EVRF2007_SkorowidzeNMT*.html` | `sheet_sources` = 4 URL (a-3-1/-3 `84183`, a-3-2/-4 `83998`); kolejnosc nieistotna |
| C14-b/C5 ucięty arkusz | te same `a-3-1` HTML + naglowek `B/raw/C14/direct/84183_1852496_N-34-139-C-a-3-1.asc` (255x422, xllcenter 638819) | wycinek poza oknem: `all_nodata=True`, `Warning:`; po E15 sidecar ma `all_nodata`; rerun (skip) powtarza ostrzezenie; test mutacyjny: usuniecie `full_sheet` z kolejnosci nie zmienia wyboru (ADR-028) |
| C15 `--force` | stan `b/logs/C15_B.log` (stary rekord w cache) | po `--force` `cache.get_record(...)` zwraca nowy rekord (po E14); obecnie zwraca stary |
| C15 brak pokrycia | `B/logs/C15_D.log` | cieply `NoCoverageError` ta sama tresc, 0 zapytan |
| C17 skip a komunikat | `B/logs/C17a.out`, `C17c.out` | skip pojedynczego godla nie wypisuje `Downloaded to` (wypisuje `Skipped ...`); skip pustego wycinka powtarza `Warning:` |
