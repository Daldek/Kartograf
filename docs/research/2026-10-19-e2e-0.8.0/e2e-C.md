# E2E 0.8.0 - plasterek C: `landcover` (bdot10k, bdoo, corine, zabaged, data50, data250) i `soil` (download, hsg, list-*)

Data: 2026-10-19. Agent: E2eLandcover. Raport po polsku (ASCII). Sciezka magazynu danych w raporcie: `<katalog-danych>`.

## 1. Zakres

Czysta instalacja wheel 0.8.0 (z `git archive HEAD` = develop e019126a, z extra `[mcp]`), komendy grup `landcover` i `soil`
(`download`, `hsg`, `list-sources`, `list-layers`), zywe uslugi: GUGiK (opendata BDOT10k/BDOO, PRG WFS), CUZK (ArcGIS REST ZABAGED/DATA50/DATA250,
feedy ATOM, plik krajowy Data250), EEA Discomap i DLR (WMS CORINE), Copernicus CLMS (tylko publiczny katalog), ISRIC (WCS SoilGrids).
Przypadki typowe (pierwsze pobranie, powtorzenie lokalne, `--check-updates`, `--upgrade`, `--force`, `--json`, `--plan`, `--help`),
brzegowe (morze, zagranica, granica PL-CZ, niepoprawne wejscie, granice lat, bbox 4326 / zla kolejnosc osi / zly CRS, bardzo maly i bardzo duzy obszar,
Ctrl-C, rownoleglosc, powtorzenie offline, bledy sciezek), zgodnosc biblioteka-CLI-MCP, weryfikacja tresci (GPKG, GeoTIFF, HSG niezaleznym klasyfikatorem),
audyt dokumentacji (USAGE, README, llms.txt, PRD, ARCHITECTURE, CHANGELOG, `--help`, katalog).

Nie edytowano repo. Nie uruchamiano testow repo ani brany. Skrypty pomocnicze tylko w katalogu roboczym plasterka (`k.sh`, `soil_matrix.py`, `lib_parity.py`,
`mcp_smoke.py`, `hsg_check.py`, logi `logs/*.{cmd,out,err,meta}` - 363 zalogowane wywolania CLI + ok. 80 wywolan przez skrypty).

Wynik: **98 przypadkow** (kazdy to grupa powiazanych wywolan; ok. 450 wywolan CLI/API/MCP lacznie): **67 PASS**, **22 PASS z uwagami P3**, **9 FAIL** (znaleziska P2).
Znaleziska: **P1: 0, P2: 8, P3: 26** (sekcja 4).

## 2. Srodowisko

- Wheel `kartograf-0.8.0-py3-none-any.whl` w venv (Python 3.13.5), rasterio 1.5.2, pyogrio 0.13.0, pyshp, pyproj 3.8.0, `mcp` 2.3.0; systemowe `ogrinfo`/`gdalinfo`/`sqlite3` do kontroli tresci.
  Zawsze `<venv>/bin/kartograf` i `<venv>/bin/python` z katalogu roboczego plasterka (cache `.kartograf_cache.db` lokalny, nigdy na udziale).
- Dane: `<katalog-danych>` (udzial SMB; koniec przebiegu ok. 630 MB wg `du`, szczyt ok. 1,4 GB; udzial bez `serverino` liczy dowiazania podwojnie).
  Po weryfikacji usunieto cieżkie pliki (BDOT10k 1465 332 MB, surowe ZIP-y 170 MB, GML 2018 112 MB). Offline: `unshare -rn`.
- Brak `CLMS_CREDENTIALS` (decyzja uzytkownika). Do sciezek bledow uzyto sztucznych poswiadczen (poprawny JSON z kluczem wygenerowanym lokalnie).
- Stan uslug: PRG WFS niestabilny (2x zerwane polaczenie: ostrzezenie ponowienia w BS01, `RemoteDisconnected` przy zapytaniu bezposrednim - uslugi, nie Kartografa);
  plik krajowy CUZK Data250 ok. 0,27 MB/s (230 MB = 857 s); EEA, DLR, ISRIC, opendata GUGiK bez zastrzezen.
- Powtarzalnosc wzgledem dokumentacji (sha8 wersji): BDOT10k 1465 `2026-10-19_f3550257` (= USAGE `..._f3550257`), archiwum GML 2018 `2018_b8b23714`/`2018_f8f5ead1` (=),
  Data50 obszaru `_7000764f` (=), Data250 krajowy `2026-05-12_ae501843` (=). SoilGrids clay doc. bbox `2.0_346cf3c6` (USAGE: `2.0_717f0989`), HSG `2.0_f4951196`
  (USAGE: `2.0_470ef3d9`) - bajty z ISRIC sie zmienily, piksele i statystyki te same (85 z 104 zer, B 71,03 ha, brak danych 329,48 ha, obszar 400,51 ha): przyklady z sha8 w USAGE nieaktualne.

## 3. Tabela przypadkow

Skrot komend: `LD` = `kartograf landcover download`, `SD` = `kartograf soil download`, `SH` = `kartograf soil hsg`, `-o` = `-o <katalog-danych>`.
Werdykt: PASS, PASS* (dziala, ale jest uwaga P3), FAIL (znalezisko P2). ID logow w nawiasach (`logs/<ID>.*`).

### A. Odkrywanie, pomoc, stare flagi (bez sieci)

| ID | Przypadek | Wynik | Oczekiwane / rzeczywiste | Werdykt |
|---|---|---|---|---|
| A01 | `landcover list-sources` tekst + `--json` (LS01) | 0, 0,7 s, 6 zrodel, `kartograf-sources/1`, `schema` pierwszy | zgodne z USAGE; klucze `bdoo` `year` [2015,2021-2026] | PASS |
| A02 | `soil list-sources` tekst + `--json` (LS02) | 0, 1 zrodlo `global.isric.soilgrids`, `select` property/depth/stat = null | zgodne | PASS |
| A03 | `landcover list-layers --product` x6 tekst/json (LL-*) | 0; bdot10k 15 warstw, bdoo 7 rocznikow, corine 5 lat, zabaged 22, data50 69, data250 116 | liczby jak w USAGE/PRD (poza uwaga P3-16) | PASS |
| A04 | `soil list-layers` tekst + json (LS03) | 0; 11 wlasciwosci, 6 glebokosci, 5 statystyk | zgodne (jednostki: P2-4) | PASS |
| A05 | `landcover list-layers --json` bez `--product` (LT01, LL-none) | 2, `invalid_input`, `details.option=product`, `allowed` | zgodne z kontraktem, ale to przyklad z `llms.txt:67` (P3-01) | PASS* |
| A06 | `list-layers --product foo`, `--source corine` (LL-bad, LL-src) | 2, `usage_error`; komunikat argparse po angielsku | znane P3 (P3-19) | PASS* |
| A07 | stare komendy/flagi: `--source`, `-s`, `--godlo`, `soilgrids hsg`, `download`, `--product soilgrids`, `soil hsg --stats`, `--stat`, `--prod`, `landcover down` (BT11/12/14, LG01-07, HE04/07) | wszystkie 2 z podpowiedzia nowej nazwy; brak skrotow flag | zgodne z CHANGELOG | PASS |
| A08 | `--help` landcover download, soil download, soil hsg, list-layers, list-sources | 0; sekcje, przyklady, wartosci dozwolone | czytelne; uwagi: P3-17 (`--layer`), PRD/USAGE jednostki (P2-4) | PASS* |
| A09 | `catalog` (get_catalog) landcover download / soil download / soil hsg | parametry, ograniczenia, przyklady (4/2/1), `idempotent`, `effects`, `project_task` | zgodne z parserem; brak przykladu Data50/250, archiwum, `--layers`, `--whole-country` | PASS |

### B. BDOT10k

| ID | Przypadek | Wynik | Oczekiwane / rzeczywiste | Werdykt |
|---|---|---|---|---|
| B01 | `LD --product bdot10k --teryt 2476 -o` (najmniejszy powiat: Swietochlowice, ZIP 3,4 MB) (BD01) | 0, 3,4 s, `landcover/pl_bdot10k_gpkg/teryt/2476.gpkg: nowa wersja 2026-10-19_ebfdf70e`; GPKG 11,8 MB, 58 warstw EPSG:2180, `PRAGMA integrity_check`=ok | sidecar `kartograf-meta/1`, `dataset=pl.gugik.bdot10k`, `product=bdot10k`, `request={teryt,format}`, `sha256`=plik; liczby wierszy 58/58 tabel = surowa paczka | PASS |
| B02 | powtorzenie (BD02) | 0, 0,85 s, `lokalna wersja 2026-10-19 (bez sprawdzania; --check-updates)` | zgodne | PASS |
| B03 | `--check-updates` (BD03) | 0, `nie da sie sprawdzic bez pobrania (2026-10-19)` | zgodne z USAGE 4.3 | PASS |
| B04 | `--upgrade` (BD04) | 0, `lokalna wersja` + `Info:` o `--force` | zgodne | PASS |
| B05 | `--force` (BD05) | 0, 4,6 s, `bez zmian 2026-10-19` | scalenie GPKG deterministyczne | PASS |
| B06 | `--json` (lokalna) i `--check-updates --json` (BD06/07) | 0; `kartograf-download/1` (`unverified:"none"`), `kartograf-plan/1` status `unverifiable`; stderr pusty | zgodne | PASS |
| B07 | `--layers SWRS,PTWP`, potem `--keep-raw` (BD10/11) | 0; segment `pl_bdot10k_gpkg_ptwp-swrs` (155 KB, OT_PTWP_A 37, OT_SWRS_L 12), surowy ZIP `pl_bdot10k_gpkg_zip` = nowa wersja | `request.layers` w sidecarze; GPKG "bez zmian" przy `--keep-raw` | PASS |
| B08 | `--format SHP` (BD12) | 0, `pl_bdot10k_shp/teryt/2476.zip` (2,9 MB) | zgodne | PASS |
| B09 | archiwum: 2016-2025 SHP, 2018 GML, 2023 = 2022 (BD13/14, AY*) | 0; `pl_bdot10k_shp_<rok>`, 2023: `nowa etykieta 2023 (plik identyczny z 2022)`; sidecar `extra.source.url`=`Archiwum/...`, `edition` | zgodne z USAGE 1.8 | PASS |
| B10 | granice lat archiwum: 2013, 2026, 0, -1, 99999999999; 2014/2015 dla 2476 (BE11/12, YB, AY2014/15) | 2 + `niedostepne dla --format SHP; dostepne: 2014..2025`; 2014/2015 dla 2476: 1 `Zrodlo nie publikuje paczki ... (HTTP 404)` (inne powiaty maja paczke - HEAD) | zgodne z opisem 404 w USAGE | PASS |
| B11 | niepoprawne kombinacje: `--layers BUBD/XXXX/swrs/SWRS,SWRS/""/"SWRS,"`, `--layers`+SHP, `--keep-raw`+SHP, `--year` bez/z GPKG, `--year`+`--layers`/`--keep-raw`, `--format GML` bez roku (BE01-15) | 2 z komunikatem (poza `XXXX`: patrz B19); `BUBD` i male litery przyjete; pusty kod: `Nieprawidlowe kody warstw BDOT10k:  (4 litery...)` | komunikaty jasne; `--json` bez `details.option` (P3-03, P3-24) | PASS* |
| B12 | niepoprawny TERYT: `9999`, `0000`, `24`, `abcd`, `12345`, `""`, `2499` (BT01-06, BT15/16) | 2 (`Nieznany kod wojewodztwa: 99. Dostepne kody: ['02', ...]` - repr listy, znane); `2499`: 1, `HTTP 404 (bez ponowien)` | zgodne; P3-23 | PASS* |
| B13 | obszar `--bbox 18.90,50.29,18.93,50.31 --bbox-crs EPSG:4326` (2463+2476), `--workers 2`, `-q`, powtorzenie (BA02-04) | 0; `2463: nowa wersja`, `2476: lokalna`, `Nowe: 1, ... lokalne: 1`; sidecar 2463 `extra.parent_request={bbox,bbox_crs,countries:[PL]}` | zgodne z USAGE 1.5 | PASS |
| B14 | `--sheet M-34-62-B-b-3-1` (PL-1992), `6.179.12.20` (PL-2000), `N-34-130-D-d-2-4`, `ZZZ-99`, `CTES96` (BH01-06) | powiaty 2472+2476 oraz 3021 potwierdzone NIEZALEZNYM odpytaniem PRG (punkty siatki); zle godlo: 2 | zgodne | PASS |
| B15 | `--geometry` SHP (EPSG:2180), GPKG z 2 warstwami (`Info:` domyslnej warstwy, `geometry_layer_default` w `notices`), `--layer`, `--layer nope`, brak pliku, `.dbf`, brak `.prj`, pusty plik (BG01-07, QJ*) | 0/2 z komunikatami | zgodne | PASS |
| B16 | morze (54,9N), Czechy (Ostrawa), Berlin, zamienione osie (50.29,18.90), odwrocony bbox, 3 wartosci, "a,b,c,d", punkt, 10x10 m (BS02/03, BX01-08) | morze/zagranica/zamienione osie: 1 `no_coverage` `BDOT10k: obszar nie przecina zadnego powiatu (PRG)`; bledy skladni: 2 | BDOO dla tego samego bbox daje 2 + podpowiedz osi (P3-05) | PASS* |
| B17 | granica PL-CZ (Cieszyn 18.60,49.73,18.67,49.77) `--check-updates` (BS05) | tylko powiat 2403 (PL), brak `Warning:` o czesci poza PL | zgodne z zalozeniem | PASS |
| B18 | offline (`unshare -rn`): lokalny teryt, obszar z cache PRG, `--check-updates` teryt, nowy teryt, `--force`, obszar morze, `--json` (BO01-11) | lokalne: 0; `--check-updates` teryt: 0 (`nie da sie sprawdzic`); nowy/`--force`: 1 po 3 probach 6,7 s `brak sieci albo DNS`; obszar `--check-updates/--upgrade/--force`: 1 `zapytanie PRG (powiaty)`; `--json` offline: dokument + 2 linie `Warning:` ponowien na stderr | zgodne z USAGE 4.3 | PASS |
| B19 | `--layers` klasa nieobecna w paczce: `--teryt 2264 --layers SWKN,PTWP`; obszar Sopot+Gdansk `--layers SWKN,PTWP`; `--layers XXXX` (LY01-04, BE02) | 1 `Paczka BDOT10k nie zawiera warstw: SWKN` (Sopot nie ma PTSO, PTWZ, SWKN); obszar: 2261 OK, 2264 blad, `bledy: 1`, kod 1; `XXXX`: pobiera cala paczke i dopiero wtedy kod 1 | BDOO w tej samej sytuacji: `Info:` + zapis obecnych klas | **FAIL (P2-7)** |
| B20 | `LD --product bdot10k --teryt 1465 --output ... --json` (przyklad `llms.txt`) (LL01/02) | 0, 47,8 s, GPKG 332 MB, 70 warstw, sha8 `f3550257` = USAGE | zgodne; po weryfikacji skasowane | PASS |
| B21 | Ctrl-C (SIGINT po 4 s), tekst i `--json`, `--workers 1` (IN01-03) | exit 130 w 0,1 s, `Error: przerwano (Ctrl-C)`, JSON `interrupted`/`exit_code:130`; brak plikow w magazynie | zgodne z 9.3 | PASS |
| B22 | Ctrl-C przy `--workers 2`, obszar 12 powiatow (bbox 18.80,50.20,19.05,50.40) | SIGINT w 5 s, proces konczy sie po **76,9 s**, exit 130, **12 wersji zatwierdzonych po Ctrl-C** (z `--workers 1`: 0,1 s, 0 plikow) | oczekiwane: przerwanie w ulamku sekundy | **FAIL (P2-5)** |
| B23 | 2 rownolegle procesy tego samego powiatu + 2 rownolegle `soil download` (CC-a..d) | wszystkie exit 0; jeden `nowa wersja`, drugi `bez zmian`; sha256 sidecarow = pliki; w jednym stderr linia `Pominieto wersje bez czytelnego sidecara ...` bez prefiksu | stan koncowy spojny; P3-11 | PASS* |
| B24 | obszar calej Polski `--bbox 100000,100000,800000,800000` (LM01/LM03) | `--check-updates`: 378 pozycji, brak limitu/`Info:`; zwykle pobranie rusza od razu (`1/378 > 0201`); suma HEAD 378 paczek = **18,01 GB**, 23 pliki > 100 MiB | USAGE 1.8: limit 100 plikow / 10 GB "przed pobraniem" (BDOT10k nie wymieniony) | **FAIL (P2-6)** |
| B25 | metry z `--bbox-crs EPSG:4326`: `--bbox 626000,480000,628000,482000 --bbox-crs EPSG:4326`; `19,91,20,92` (WC, WJ1/3) | 1 `Error: OverflowError: cannot convert float infinity to integer`, `--json`: `internal_error` | oczekiwane: 2 + podpowiedz `--bbox-crs`/kolejnosc osi (jak BDOO, HSG) | **FAIL (P2-8)** |
| B26 | przyklady USAGE: archiwum 2018 GML `--bbox 557000,244000,559000,246000 --workers 2`; `--layers SWRS,PTWP --keep-raw --workers 4 -q` (DX01-04) | 0; etykiety `2018_b8b23714`, `2018_f8f5ead1` (=USAGE); drugi przyklad: 2 powiaty (0208 112 MB, 0224 59 MB), segmenty `..._ptwp-swrs` + `..._gpkg_zip`; komentarz USAGE "4 powiaty rownolegle" = 4 watki, 2 powiaty | zgodne | PASS |
| B27 | `--check-updates --plan` -> edycja planu -> `--upgrade --plan`; plan innej komendy (PP01-03, PL05) | pobrany tylko 2476; plan soil w `landcover`: `Error: ...: zrodlo zmienilo sie od planu (None)` (kod 1) | dziala; tekst z `None` (P3-22) | PASS* |
| B28 | biblioteka vs CLI: `download_landcover(bdot10k, 2264)` nowy/lokalny, `check_landcover` (lib_parity) | `to_dict()` == `--json` (klucze, kolejnosc, wartosci; po normalizacji sciezki) | zgodne | PASS |

### C. BDOO

| ID | Przypadek | Wynik | Oczekiwane / rzeczywiste | Werdykt |
|---|---|---|---|---|
| C01 | `LD --product bdoo --teryt 16 --year 2023`; powtorzenie; `--check-updates`; `--force` (OO01-04) | 0; `pl_bdoo_2023/teryt/16.zip` 4,5 MB `2023_6c3d8b1e`; lokalna; `nie da sie sprawdzic bez pobrania (2023)`; `bez zmian 2023` | zgodne z USAGE 1.5 | PASS |
| C02 | `--layers PTWP,SWRS`; `PTWP,KUIK`; rocznik 2024 `PTWP,TCPK`; male litery (OO05/06/08, OE11) | ZIP z 2 plikami `__OT_*` bajt w bajt jak w paczce (sha256 potwierdzone); KUIK: `Info: paczka nie ma plikow klas KUIK`; 2024 `.gml`; `ptwp` przyjete | zgodne | PASS |
| C03 | bledy: brak/`2014`/`2016`/`2027`/`0`/`-1`; `--teryt 1261`, `99`, `03`; klasa `XXXX`/`KUIK` w 2024; `--format`/`--keep-raw`/`--whole-country` (OE01-14) | 2; podpowiedz `--teryt 12`, lista klas rocznika | zgodne (tekst `99`: "wojewodztwo ... albo powiat" - P3-23) | PASS* |
| C04 | wszystkie klasy nieobecne `--layers KUIK` (OZ01/02) | 1, `kind:"no_coverage"`, `paczka nie ma plikow klas KUIK` | zgodne z USAGE | PASS |
| C05 | obszar 2 wojewodztw (przyklad USAGE) `--layers KUIK,PTWP`, `--workers 2`, `--check-updates` (OA01-03) | 0; `Info: bdoo: wojewodztwa obszaru wg PRG (2): 12 (malopolskie), 24 (slaskie)` + `classes_absent`; `Nowe: 2` | zgodne z USAGE | PASS |
| C06 | `--sheet N-34-130-D --check-updates`; morze; CZ; Berlin (OA04-06, BX02) | arkusz: wojewodztwa 14+20; morze/Berlin: **2** `--bbox lezy poza PL ... kolejnosc osi`; CZ (Ostrawa): 1 `nie przecina zadnego wojewodztwa` | niespojne z BDOT10k (B16) - P3-05 | PASS* |
| C07 | biblioteka `download_landcover(bdoo, 16, 2024, layers)` vs CLI | identyczne | zgodne | PASS |

### D. CORINE (bez `CLMS_CREDENTIALS`)

| ID | Przypadek | Wynik | Oczekiwane / rzeczywiste | Werdykt |
|---|---|---|---|---|
| D01 | `LD --product corine --year 2018 --sheet N-34-130-D-d-2-4`; powtorzenie; `--check-updates`; `--upgrade`; `--force` (CO01-05) | 0; `Info: CORINE 2018: podglad WMS (stylizowany PNG, nie dane; dane CLMS wymagaja CLMS_CREDENTIALS)` na stderr (takze przy lokalnej); PNG 22x24 px RGBA (100 m/px), sidecar `extra.fallback=wms_png`, `horizontal_crs=EPSG:3857`; `--check-updates`: `nie da sie sprawdzic bez pobrania`; `--force`: `bez zmian` | komunikat jasny; P3-20 (maly, bez georeferencji) | PASS |
| D02 | `--bbox 18.4,49.6,18.9,49.9 --bbox-crs EPSG:4326` lata 2018 i 1990 (CY2018, CY1990, CZ1990) | 2018: PNG 361x336, 100 % nieprzezroczysty (poprawne); **1990 dla PL: PNG 361x336 w 100 % przezroczysty zapisany jako `nowa wersja`, exit 0, bez `Warning:`** (DLR WMS nie ma CLC1990 dla PL - sprawdzone bezposrednio; dla CZ jest) | oczekiwane: ostrzezenie albo `no_coverage` bez wersji (jak true orto) | **FAIL (P2-2)** |
| D03 | lata 2012, 2006, 2000 (WMS) (CY2012/06/00, CY2012j) | **1** `Error: ...: WMS returned error response: <?xml ...<ServiceException code="LayerNotDefined">Parameter 'layers' contains unacceptable layer names.`; `--json`: `failed[].error` z XML | `--help`/`list-layers`: "2012, 2006, 2000 (... bez nich podglad WMS)" | **FAIL (P2-1)** |
| D04 | bledy: brak `--year`, 2019, 1989, 0, brak obszaru, `--layers/--format/--keep-raw/--whole-country/--teryt`, `--sheet CTES96` (CE01-12, YB) | 2; `Nieprawidlowy rok: 2019. Dostepne lata: [2018, 2012, 2006, 2000, 1990]`; `--workers 2` przyjete bez efektu | P3-09, P3-04 | PASS* |
| D05 | obszary: CZ bbox 4326, EPSG:5514, geometria SHP, 450 km (PNG 4096x4096, 8,9 s), Baltyk 55N (18 kolorow, poprawne), Kijow i USA (CS01-03, CB01/02, CZ*) | 0; poza zasiegiem CLC (Kijow, USA 1886x1874 px): PNG w 100 % przezroczysty, bez ostrzezenia | patrz P2-2 | PASS* |
| D06 | bez poswiadczen vs `CLMS_CREDENTIALS`: `not json at all`, `{}`, poprawny JSON ze sztucznym kluczem (CC01-05) | `not json`/`{}`: ciche podglad WMS i komunikat "dane CLMS wymagaja CLMS_CREDENTIALS" mimo ustawionej zmiennej; sztuczny klucz: 1, `Proxy request failed: {"error": "Failed to get access token"}` + `Error: ...: Zadanie przez proxy nie powiodlo sie`, w `--json` ta linia tez na stderr | komunikat mylacy, kontrakt `--json` (P3-08) | PASS* |
| D07 | `--check-updates` ze sztucznymi poswiadczeniami: 2018/2012/2006/2000 (CK*) | 0; `.../eu_corine_<rok>/.../*.tif: do pobrania (V2020_20u1)` (wydanie z publicznego katalogu CLMS bez tokenu); 1990: sciezka podgladu | zgodne z ARCHITECTURE 4.8 | PASS |
| D08 | offline: lokalny podglad (0), `--check-updates` (0), nowy arkusz (1 po 6,7 s; komunikat z angielskim `for bbox` i wspolrzednymi 2180) (OF09-11) | zgodne z USAGE | P3-25 | PASS* |
| D09 | biblioteka `download_landcover(corine, 2018, sheet)`: `notices` `corine_preview` == `--json` | identyczne | zgodne | PASS |

### E. Produkty CZ (ZABAGED, Data50, Data250)

| ID | Przypadek | Wynik | Oczekiwane / rzeczywiste | Werdykt |
|---|---|---|---|---|
| E01 | `LD --product zabaged --bbox=-460000,-1120000,-459000,-1119000 --bbox-crs EPSG:5514` + powtorzenie/`--check-updates`/`--upgrade`/`--force` (ZB01-05) | 0, 12,9 s, GPKG 770 KB, 22 warstw EPSG:5514 (opisy `Vodni tok (93)`), pelne geometrie; `nie da sie sprawdzic`; `--force`: `bez zmian` (15,7 s); `Info:` `area_omitted` | zgodne z USAGE 1.9; zapis `--bbox X,..` (spacja) tez dziala (ZB02) | PASS |
| E02 | przyklad README 10x10 km (ZL01) | 0, 80,9 s, 16 MB, 21 890 obiektow (11 688 budynkow) | zgodne | PASS |
| E03 | `LD --product data50 --bbox 18.566,49.757,18.572,49.761 --bbox-crs EPSG:4326` (D501/02/05) | 0, 23,4 s, 69 warstw (9 niepustych), sha8 `7000764f` = USAGE, `parent_request` 4326; `--force`: `bez zmian` | zgodne | PASS |
| E04 | Data250 ten sam bbox (D503/04) | 0, 35,9 s, 116 warstw (7 niepustych), 2,6 MB | zgodne | PASS |
| E05 | Data250 plik krajowy `--whole-country --horizontal-crs EPSG:5514` (WC10-14) | 0, **857 s**, `Warning: data250 CZ: plik krajowy ... 230485722 B (ok. 230 MB)`, `nowa wersja 2026-05-12_ae501843` (= USAGE), ZIP 448 skladnikow, `unzip -t` OK; `--check-updates`: `aktualne (2026-05-12)`; `--upgrade`: `lokalna wersja`; `--json` plan `current` | zgodne z USAGE 1.9 | PASS |
| E06 | `--whole-country --check-updates` dla zabaged/data50/data250 x 5514/3045 (WC-*) | 0, `do pobrania (2026-10-04 / 2026-04-28 / 2026-05-12)` | wydania zgodne z ARCHITECTURE 4.8 | PASS |
| E07 | bledy: `--whole-country` bez `--horizontal-crs`, z 4326; `--teryt`, `--sheet`, `--format`, `--layers`, `--keep-raw`, `--year`; obszar + `--whole-country`; obszar + `--horizontal-crs EPSG:3045` / `5514` (ZE01-16) | wszystkie 2 z komunikatem; `--horizontal-crs EPSG:5514` z obszarem **przyjete** (3045: blad) | USAGE 1.9/ARCH 4.8: "z obszarem = Error" (P3-04) | PASS* |
| E08 | bbox poza CZ: EPSG:2180 Polska, 4326 Warszawa, Slowacja (ZP02-04) | 2, `--bbox (...) lezy poza CZ ... Sprawdz --bbox-crs ... kolejnosc osi`, `details.option=bbox` | zgodne | PASS |
| E09 | granica PL-CZ (Cieszyn) ZABAGED (ZP01) | 0, 28,7 s, dane tylko CZ | zgodne | PASS |
| E10 | ujemne wspolrzedne `--bbox=-...` i `--bbox -...`; bbox EPSG:4326 -> obwiednia 5514 w nazwie pliku | oba zapisy dzialaja; nazwa pliku zaczyna sie od `-` (narzedzia CLI wymagaja `./`) | zgodne z USAGE | PASS |
| E11 | offline: lokalne obszary i Data250 krajowy (0); `--check-updates` krajowy: 1, `ATOM ...: pobranie nieudane po 3 probach` (OF12-16) | zgodne | zgodne | PASS |
| E12 | obszar 100x100 km zabaged/data50 (po 25 s przerwany) | brak limitu/estymaty czasu; 10 km = 81 s | P3-21 | PASS* |

### F. SoilGrids (`soil download`)

| ID | Przypadek | Wynik | Oczekiwane / rzeczywiste | Werdykt |
|---|---|---|---|---|
| F01 | `SD --bbox 626000,480000,628000,482000 --property clay --depth 0-5cm --stat mean` + powtorzenie, `--check-updates`, `--upgrade`, `--force` (SG01-05) | 0; 2,4 s, `nowa wersja 2.0_346cf3c6`; lokalna; `aktualne (2.0)`; `lokalna wersja 2.0`; `bez zmian 2.0` | zgodne (sha8 inny niz w USAGE - patrz Srodowisko) | PASS |
| F02 | weryfikacja rastra | 13x8 px int16 EPSG:4326, `nodata` brak (sidecar null), 85/104 zer (maska, USAGE 7); piksele, transformacja i zasieg rowne bezposredniemu zapytaniu WCS; sidecar `extra.edition` (`id 2.0`, tytul) | zgodne | PASS |
| F03 | 11 wlasciwosci x 0-5cm mean, obszar wiejski 19.50,52.00,19.52,52.02 (soil_matrix) | 9 poprawnych (bdod, cec, cfvo, clay, nitrogen, phh2o, sand, silt, soc; 8x9 px); **`ocd`: 1 `SoilGrids GetCapabilities ocd: brak wydania w tytule 'Soilgrids property: Organic carbon density'`; `ocs`: 1 `HTTP 404 ... COVERAGEID=ocs_0-5cm_mean`** (kazda glebokosc/statystyka tak samo; `--depth 0-30cm`: 2) | PRD/`list-layers`: 11 x 6 x 5 | **FAIL (P2-3)** |
| F04 | 6 glebokosci clay mean | 0; profil clay rosnie z glebokoscia (75-101 -> 120-205) | sensowne | PASS |
| F05 | 5 statystyk clay 0-5cm | 0; Q0.05 (3-9) < Q0.5 (46-69) < mean (75-101) < Q0.95 (206-411); uncertainty 39-76 | porzadek kwantyli poprawny | PASS |
| F06 | jednostki wartosci | wartosci to calkowite "mapped units" ISRIC: clay/sand/silt g/kg (87 = 8,7 %), phh2o x10 (47-57), soc 530-822, nitrogen 579-733, bdod 109-127, cec 235-298, cfvo 49-78 | `list-layers`/`--help`/PRD 3.7: "clay (%)", "nitrogen (g/kg)", "soc (g/kg)", "bdod (kg/dm3)", "cec (cmol/kg)"; sidecar bez skali | **FAIL (P2-4)** |
| F07 | bledy: `--property CLAY/foo`, `--depth 0-10cm`, `--stat MEAN/q0.5`, brak `--property/--depth/--stat`, brak obszaru, brak `-o` (SE09-15) | 2; `Nieprawidlowa glebokosc: ... Dostepne: ...`; `--json`: `details.option`+`allowed`+przyklad | zgodne | PASS |
| F08 | obszary: `--sheet` PL-1992 1:100k/1:10k, PL-2000 `6.179.12.20`, `N-34` (1:1 mln), `--geometry` SHP/GPKG, bbox CZ 5514, Praga 4326, CZ godla (SE02/06/07/08, SS01-05, QJ01-04) | 0; sciezki `.../N-34/130/D/N-34-130-D.tif`; `CTES96`/`302_5550`: 2 | zgodne | PASS |
| F09 | skrajne: Baltyk (42x45 px same zera), zamienione osie 52,19.5 (dane z Arabii, bez ostrzezenia), okno 10/50/100 m (HTTP 400), 150-500 m (OK, 1x1..2x3 px) (SE01/03/04, ST*) | 0 bez ostrzezenia dla zer/osi; `Error: ... HTTP 400 (bez ponowien): 400 Client Error: Bad Request for url: https://maps.isric.org/...` | P3-06, P3-07 | PASS* |
| F10 | obszar 300 km i 700 km (SL01/02) | 0; 1,6 MB w 4,2 s; 8,9 MB w 8,1 s | brak limitu, dziala | PASS |
| F11 | bbox w metrach z `--bbox-crs EPSG:4326` (WC, WJ2) | wyslane zapytanie `SUBSET=long(inf,-inf)&SUBSET=lat(nan,nan)` do ISRIC, 404, jednostka `inf_inf_inf_inf` (exit 1) | oczekiwane: 2 przed siecia | **FAIL (P2-8)** |
| F12 | offline: lokalna 0; `--check-updates` 1 (`nie udalo sie sprawdzic: ... po 3 probach`); `--upgrade`/`--force`/nowy: 1 (OF01-05) | zgodne z USAGE 4.3 | PASS |
| F13 | plan: `--check-updates --plan` (plik == stdout `--json`), `--upgrade --plan`, plan zly JSON (2), brak pliku (2), `--plan` bez trybu (2), `--check-updates --upgrade` (2) (PL01-09) | zgodne; plan innego obszaru: ciche 0 bez wyjscia (znane U5) | CHANGELOG mowi o kodzie 1 (patrz sekcja 5) | PASS |
| F14 | `-p -d -q`; `-o` wzgledny (dowiazanie), z spacjami i `ołędzi ąę`, nieistniejacy rodzic (tworzony); `-o` = plik (1 `NotADirectoryError`), katalog tylko do odczytu (1 `PermissionError` po pobraniu), `/proc/nohome` (`io_error`) (SH01, PA01-07) | zgodne z 9.3 (`io_error` exit 1) | P3-13 | PASS* |
| F15 | `--json` blad wejscia: `kartograf-error/1` z `option`/`allowed`/`hint`, stderr pusty | zgodne | PASS |
| F16 | biblioteka `download_soil`/`check_soil` == CLI `--json`; MCP `soil_download`, `check_updates` | identyczne | PASS |

### G. HSG (`soil hsg`)

| ID | Przypadek | Wynik | Oczekiwane / rzeczywiste | Werdykt |
|---|---|---|---|---|
| G01 | `SH --bbox 626000,480000,628000,482000 --depth 0-5cm --summary` (clay lokalny, sand/silt nowe) (HG01-06) | 0, 2,6 s, HSG `2.0_f4951196`; B 100 % (71,03 ha), brak danych 82,3 % (329,48 ha), obszar 400,51 ha; powtorzenie `uzyta ponownie 2.0` (1,1 s); `--check-updates`: 4x `aktualne (2.0)`; `--upgrade`, `--force` (wejscia `bez zmian`, HSG `uzyta ponownie`) | zgodne z USAGE 1.5/5 | PASS |
| G02 | `--json --summary`, `--check-updates --json` (HJ01/02) | `kartograf-download/1` z `summary` (A-D + `nodata`, `percent`, `area_ha`, opisy po polsku), `status:"reused"`; plan: 3 pozycje `landcover` + `hsg` | zgodne | PASS |
| G03 | niezalezny klasyfikator USDA (clay/sand/silt -> HSG) vs raster (hsg_check.py): 13x8 px, 30x30 km (22 116 px), Zulawy 54,0-54,3N (28 098 px; klasy B 2045, C 23487, D 543) | 0 niezgodnosci / 18 / 13: wszystkie na dokladnych granicach g/kg (`silt+2*clay=300`, `clay=270`, `clay=400`), czyli wynik decyduje szum float32 | oczekiwane: deterministyczne reguly | PASS* (P3-10) |
| G04 | inne glebokosci (100-200 cm), `--sheet` 1:100k, PL-2000, N-34 (1:1 mln, 15 s, 1,1 GB RSS), `--geometry`, bbox CZ 5514 (`Obszar zadania: 116,78 ha` dla 1 km2), Baltyk (`Brak danych: 100,0 %`) (HZ01-05, SS06, HX01) | 0; sciezki hierarchii godla w `hsg/` | zgodne; P3-12 (obszar zadania = obwiednia 2180), P3-07 | PASS* |
| G05 | bledy: `-o plik.tif`, brak `--depth`, `--depth 0-10cm`, `--stats`, `--stat`, brak obszaru, brak `-o`, `--layer` bez `--geometry`, nieistniejaca warstwa (HE01-07, HL02/03) | 2 z komunikatami | zgodne | PASS |
| G06 | offline: lokalne HSG z `--summary` (0); `--check-updates` (1 po **18,7 s**, 3 x 6,6 s sekwencyjnie); nowy obszar (1, 3 bledy) (OF06-08) | zgodne | P3-14 | PASS* |
| G07 | plan HSG: `--check-updates --plan`, `--upgrade --plan`; czesciowo lokalne wejscia (HL01: clay `aktualne`, sand/silt/hsg `do pobrania`) | zgodne z ARCHITECTURE 4.8 | PASS |
| G08 | sidecar HSG | `product:"hsg"`, `nodata:0`, `extra.derived=hsg`, `source_files` (sciezki wersji + sha256 + `label`), `classes`, `request` | zgodne | PASS |
| G09 | biblioteka `calculate_hsg(summary=True)`/`check_hsg` == CLI; MCP `soil_hsg` | identyczne | PASS |
| G10 | GeoTIFF HSG | uint8, nodata 0, EPSG:4326, siatka = clay/sand/silt, tagi warstwy | zgodne | PASS |

### H. Przekrojowe

| ID | Przypadek | Wynik | Werdykt |
|---|---|---|---|
| H01 | zgodnosc biblioteka-CLI: 18 porownan (`download_landcover` bdot10k/bdoo/corine, `check_landcover`, `download_soil`, `check_soil`, `calculate_hsg` nowy/reused, `check_hsg`, `list_layers` x5, `list_sources` x2, `error_report`) | 18/18 identyczne (klucze, kolejnosc, wartosci) | PASS |
| H02 | serwer MCP przez stdio (29 narzedzi): `list_layers`, `list_sources`, `landcover_download`, `soil_download`, `soil_hsg`, `check_updates`, 3 bledy (zly teryt, poza `--allow-dir`, zla wlasciwosc), `bbox` bez `bbox_crs` | 11/11: dokument == CLI, `is_error` zgodne z kodem CLI | PASS |
| H03 | odczyt magazynu (`describe_store`, `list_store_entries`, `read_store_sidecar`) po danych plasterka | wszystkie segmenty `known:true`, wpisy `link`/`version`, sidecar czytelny; nazwy "GPKG"/"SHP" (biezace) vs "gml"/"shp" (archiwum) | PASS* (P3-15) |
| H04 | audyt stderr w 52 wywolaniach `--json` | 49 puste; 2 z ponowieniami `Warning:` (dozwolone); 1 naruszenie: `Proxy request failed: ...` (CC04) | PASS* (P3-08) |
| H05 | 4 procesy rownolegle na tym samym magazynie i cache (CC-a..d, parity) | brak blokad bazy, brak uszkodzen | PASS |
| H06 | cwd tylko do odczytu | 0, `Warning:` `cache_disabled` (w `--json` w `notices`) | PASS* (P3-18) |
| H07 | `llms.txt` komendy plasterka wykonane dosłownie | `bdot10k --teryt 1465 --json` OK; `soil download ... --json` OK; `soil hsg ... --summary --json` OK; `landcover list-layers --json` blad (2) | PASS* (P3-01) |

Podsumowanie: A 9, B 28, C 7, D 9, E 12, F 16, G 10, H 7 = **98**.

## 4. Znaleziska

### P1 (zle dane / cichy zly wynik / awaria / utrata danych)

Brak. (Najblizsze: P2-2 - pusty podglad CORINE zapisany jako poprawna wersja; to podglad "nie dane" i usluga naprawde nie ma danych, wiec P2.)

### P2 (funkcja zepsuta albo mylaca w typowym przypadku)

**P2-1. CORINE: podglad WMS dla lat 2012, 2006, 2000 nie dziala (surowy blad XML po angielsku).**
- Powtorzenie (bez `CLMS_CREDENTIALS`): `kartograf landcover download --product corine --year 2012 --sheet N-34-130-D-d-2-4 -o <katalog-danych>` (tak samo 2006, 2000; `--bbox`, tez `--json`).
- Rzeczywiste: exit 1, `Error: N-34-130-D-d-2-4: WMS returned error response: <?xml ...><ServiceException code="LayerNotDefined">Parameter 'layers' contains unacceptable layer names.`
  (w `--json` `failed[].error` z calym XML z nowymi liniami). 2018 i 1990 dzialaja.
- Oczekiwane: podglad dla kazdego roku z `--help`/`list-layers` ("2018, 2012, 2006, 2000 ... bez nich podglad WMS") albo czytelny blad po polsku.
- Przyczyna (sprawdzone na zywo): GetCapabilities `.../Corine/CLC2012_WM/MapServer/WMSServer` ma warstwy `Corine_Land_Cover_2012_raster59601`, CLC2006 `..._2006_raster43084`,
  CLC2000 `..._2000_raster11306`; tylko CLC2018_WM ma warstwe `12`. Kod: `kartograf/providers/corine.py` - stala `EEA_RASTER_LAYER = "12"` uzywana w
  `_construct_eea_wms_url` dla wszystkich lat. Nazwy warstw zawieraja liczbowy sufiks (moga sie zmieniac) - czytac z GetCapabilities.

**P2-2. CORINE: calkowicie przezroczysty podglad (brak danych) zapisywany jako poprawna wersja, bez ostrzezenia.**
- Powtorzenie: `LD --product corine --year 1990 --bbox 18.4,49.6,18.9,49.9 --bbox-crs EPSG:4326 -o` -> exit 0, `nowa wersja 2026-10-19_d7005406`, PNG 361x336 z kanalem alfa 0 % nieprzezroczystych
  (DLR WMS: CLC1990 bez danych dla PL - zapytanie bezposrednie to potwierdza; dla CZ dane sa). Tak samo `--year 2018 --bbox 30.4,50.4,30.6,50.6 --bbox-crs EPSG:4326` (Kijow) i `-100,40,-99,41` (USA, 1886x1874 px).
- Oczekiwane: `Warning:`/`Notice` (jak `all_nodata` dla wycinkow) albo `no_coverage` bez zapisu wersji (wzor: poprawka true-orto w 0.8.0).
- Kod: `corine.py::_download_via_wms` (brak kontroli tresci poza `reject_error_document`).

**P2-3. SoilGrids: `--property ocd` i `--property ocs` nie dzialaja (2 z 11 reklamowanych wlasciwosci).**
- `SD --bbox 19.50,52.00,19.52,52.02 --bbox-crs EPSG:4326 --property ocd --depth 0-5cm --stat mean -o` -> exit 1
  `SoilGrids GetCapabilities ocd: brak wydania w tytule 'Soilgrids property: Organic carbon density' (oczekiwano 'SoilGrids250m <wydanie> - ...')` (tak samo `--check-updates`: exit 1).
- `... --property ocs --depth 0-5cm|15-30cm|100-200cm` -> exit 1 `HTTP 404 ... COVERAGEID=ocs_0-5cm_mean`; `--depth 0-30cm` -> 2 (niedozwolone).
- Przyczyna (GetCapabilities ISRIC): `ocd.map` ma tytul bez prefiksu `SoilGrids250m 2.0 - `, a `ocs.map` publikuje tylko `ocs_0-30cm_{mean,Q0.05,Q0.5,Q0.95,uncertainty}`.
  Kod: `kartograf/providers/soilgrids.py` - `_EDITION_RE = r"^SoilGrids250m (\S+) - "` i `coverage_id = f"{property}_{depth}_{stat}"`.
- Oczekiwane: wszystkie wlasciwosci z `soil list-layers`/PRD 3.7/USAGE 5 uzywalne albo wylaczone z walidacji (np. `ocs` tylko `0-30cm`, wydanie `ocd` z innego zrodla).

**P2-4. SoilGrids: jednostki w dokumentacji i `list-layers` nie zgadzaja sie z wartosciami w plikach; brak skali w sidecarze.**
- Pliki to calkowite "mapped units" ISRIC: obszar wiejski 19.50-19.52E/52.00-52.02N: clay 75-101 (to g/kg = 7,5-10,1 %; HSG sam dzieli przez 10, `CONVERSION_FACTOR` w `hydrology/hsg.py`),
  phh2o 47-57 (pH x10), soc 530-822, nitrogen 579-733, bdod 109-127, cec 235-298, cfvo 49-78.
- `soil list-layers`, `soil download --help`, PRD 3.7 i USAGE 5 podaja: clay (%), sand (%), silt (%), nitrogen (g/kg), soc (g/kg), bdod (kg/dm3), cec (cmol/kg), cfvo (%), phh2o (bez jednostki);
  tylko opis HSG mowi o g/kg. Sidecar: `nodata: null`, brak `scale`/`unit`; maska = 0 (USAGE 7 opisuje).
- Skutek: konsument czytajacy `list-layers` (np. Hydrolog, Retman) odczyta clay 88 jako 88 % (10x za duzo), phh2o 50 jako pH 50. [INFERENCE] dokladne wspolczynniki dla wlasciwosci poza clay/sand/silt
  wynikaja z konwencji ISRIC i zgodnosci rzedow wielkosci; potwierdzone tylko dla clay/sand/silt (HSG).
- Oczekiwane: opis jednostek i wspolczynnika (albo `extra.units`/`scale` w sidecarze) zgodny z plikiem.

**P2-5. Ctrl-C nie przerywa pobierania wielu jednostek z `--workers > 1` (proces dziala dalej i zatwierdza wersje).**
- Powtorzenie (Popen + `send_signal(SIGINT)` po 5 s): `LD --product bdot10k --bbox 18.80,50.20,19.05,50.40 --bbox-crs EPSG:4326 --workers 2 --json -o` (12 powiatow).
  Wynik: koniec procesu **76,9 s po SIGINT**, exit 130 i `kartograf-error/1` `interrupted`, ale 12 plikow GPKG zatwierdzonych po Ctrl-C. Z `--workers 1`: koniec po 0,1 s, 0 plikow.
- Przyczyna: `kartograf/landcover/manager.py::_each_powiat` (ok. linii 485): `with ThreadPoolExecutor(...) as pool:` + `as_completed` - `__exit__` czeka na wszystkie zakolejkowane zadania
  (brak `shutdown(wait=False, cancel_futures=True)` przy `KeyboardInterrupt`). Ten sam wzorzec (niezweryfikowany): `download/collections.py:3247`, `download/laz.py:331`, `download/cz_laz.py:305`, `download/manager.py:1955`.
  (Przekazano E2eCollections.)
- Oczekiwane: przerwanie w ulamku sekundy bez nowych zapisow (USAGE 9.3: "130 = przerwane").

**P2-6. BDOT10k z obszaru nie ma limitu 100 plikow / 10 GB ani listy powiatow; bbox calej Polski startuje 378 pobran (18 GB).**
- `LD --product bdot10k --bbox 100000,100000,800000,800000 -o` -> bez bledu/`Info:`; pobieranie rusza od razu (`1/378 > 0201`); `--check-updates` wypisuje 378 pozycji.
  Suma `Content-Length` 378 paczek GPKG (HEAD) = 18,01 GB (max 289 MB, 23 pliki > 100 MiB).
- USAGE 1.8 ("Limit obszaru (od 0.8.0)"): obszar, ktory pobralby > 100 plikow albo > 10 GB, konczy sie `Error:` (kod 2) przed pobraniem; limit "dotyczy wszystkich kolekcji, takze ZABAGED, BDOO, Data50 i Data250 w landcover"
  (BDOT10k nie jest wymieniony i nie jest "kolekcja" w kodzie). BDOO bez limitu ma `Info: unit_list`, BDOT10k obszaru nie wypisuje nawet listy powiatow.
- Kod: `landcover/manager.py::_download_counties`/`_area_teryts` (sciezka BDOT10k poza `download/collections.py`, gdzie jest limit).
- Oczekiwane: ten sam limit (rozmiary z `HEAD`) i `Info:` z lista powiatow dla BDOT10k, albo jawne zastrzezenie w USAGE/`--help`.

**P2-7. BDOT10k `--layers`: klasa nieobecna w paczce powiatu = blad powiatu (inaczej niz BDOO), a bledny kod wykrywany po pobraniu calej paczki.**
- `LD --product bdot10k --teryt 2264 --layers SWKN,PTWP -o` -> exit 1 `Error: 2264: Paczka BDOT10k nie zawiera warstw: SWKN` (Sopot nie ma PTSO, PTWZ, SWKN).
  Obszar `--bbox 18.55,54.42,18.62,54.46 --bbox-crs EPSG:4326 --layers SWKN,PTWP`: 2261 zapisany, 2264 blad, `bledy: 1`, kod 1, 29 s.
  `--layers XXXX`: kod 1 dopiero po pobraniu calej paczki (3 MB; dla duzego powiatu 88+ MB), `--json`: `kind:"download"` (nie `no_coverage`).
- BDOO w tej samej sytuacji: `Info: ... paczka nie ma plikow klas KUIK (brak takich obiektow); zapisano klasy PTWP`. Warstwy hydrograficzne z przykladu USAGE (`SWRS,SWKN,SWRM,PTWP`) sa
  typowym wyborem konsumenta (Hydrograf); brak SWKN/SWRM w czesci powiatow oznacza brak obiektow, nie blad.
- ARCHITECTURE 4.8 opisuje to jako `DownloadError` (zamierzone), wiec to rozjazd projektowy BDOT10k vs BDOO - do decyzji.
- Kod: `providers/pl/bdot10k.py` (`_extract_gpkg_from_zip`, komunikat `Paczka BDOT10k nie zawiera warstw`).

**P2-8. Zly CRS bbox (metry z `--bbox-crs EPSG:4326`) daje wyjatki wewnetrzne albo zapytanie z `inf`/`nan`; tylko BDOO, ZABAGED i HSG zglaszaja czytelny blad.**
- `LD --product bdot10k --bbox 626000,480000,628000,482000 --bbox-crs EPSG:4326 -o`: exit 1 `Error: OverflowError: cannot convert float infinity to integer`; `--json`: `internal_error`, `hint` "Zglos blad..."; `KARTOGRAF_DEBUG=1`: `prg.py::_mm` (`discover_teryts_for_bbox` -> `_query`).
  Tak samo `--bbox 19,91,20,92` (szerokosc > 90).
- `LD --product corine --year 2018 --bbox 626000,480000,628000,482000 --bbox-crs EPSG:4326 -o`: exit 1 `Error: ValueError: cannot convert float NaN to integer` (`corine.py::_download_via_wms`).
- `SD ... --bbox 626000,480000,628000,482000 --bbox-crs EPSG:4326 ...`: **wyslane zapytanie** `SUBSET=long(inf,-inf)&SUBSET=lat(nan,nan)` do ISRIC (404), jednostka `inf_inf_inf_inf`.
- Dobrze: BDOO i ZABAGED/Data (exit 2 `--bbox (EPSG:4326) lezy poza PL/CZ ... Sprawdz --bbox-crs ... kolejnosc osi`), HSG (exit 2 `wspolrzedne bboxa musza byc skonczone`).
- Oczekiwane: walidacja zakresu/skonczonosci przed siecia (exit 2, `details.option=bbox`) dla kazdego produktu - to typowa pomylka uzytkownika.

### P3 (UX / tekst / dokumentacja)

- **P3-01.** `llms.txt:67`: `kartograf landcover list-layers --json` konczy sie kodem 2 (`--product wymagane`); to pierwszy plik czytany przez agentow. Poprawic na `--product bdoo --json` lub dodac `soil list-layers --json`.
- **P3-02.** `hint` bledu wejscia bierze "Przyklad:" z pierwszego przykladu katalogu niezaleznie od produktu i opcji: `--year 2013 --format SHP` (bdot10k) -> przyklad `--product bdoo --teryt 12 --year 2023`;
  `--horizontal-crs EPSG:3045` z obszarem -> przyklad `--product bdot10k --teryt 1465`. Przyklady katalogu dla `landcover download` to tylko 4 (brak Data50/250, archiwum, `--layers`, `--whole-country`).
- **P3-03.** Bledy walidacji z poziomu providera nie niosa `details.option`/`hint` (`--layers ""` -> `details: {}`, `hint: null`; blad roku CORINE bez nazwy flagi; `--teryt` bez `option`), w przeciwienstwie do `soil`.
- **P3-04.** `--year 2019` CORINE: `Nieprawidlowy rok: 2019. Dostepne lata: [2018, 2012, 2006, 2000, 1990]` (repr listy Pythona, bez nazwy flagi) vs BDOO/BDOT10k `--year 2013: niedostepne; dostepne: ...`; `--workers 2` z `corine`/`zabaged` przyjete i ignorowane (flaga dotyczy tylko obszaru BDOT10k/BDOO wg `--help`).
- **P3-05.** Spojnosc obszaru poza krajem: BDOT10k (morze, Berlin, zamienione osie) -> exit 1 `no_coverage` bez podpowiedzi osi; BDOO ten sam bbox -> exit 2 `lezy poza PL ... kolejnosc osi`. Zamienione osie przy `soil`/`corine` przechodza bez ostrzezenia (dane z innej czesci swiata).
- **P3-06.** `soil download` dla okna < ok. 150 m (10, 50, 100 m): surowe `HTTP 400 (bez ponowien): 400 Client Error: Bad Request for url: https://maps.isric.org/mapserv?...` (dlugi URL), nigdzie nie opisano minimum (piksel 250 m; 150 m daje 1x1 px). Warto wyrownac okno do piksela albo powiedziec, ze obszar jest mniejszy niz piksel.
- **P3-07.** Wynik bez danych bez ostrzezenia: `soil download`/`soil hsg` nad morzem to wersja z samymi zerami (42x45 px), HSG `Brak danych 100 %` widoczne tylko z `--summary`; brak `Notice` typu `all_nodata` jak w innych torach.
- **P3-08.** CLMS: zla zmienna (`CLMS_CREDENTIALS='not json at all'`, `'{}'`) jest po cichu traktowana jak brak, a `Info:` mowi "dane CLMS wymagaja CLMS_CREDENTIALS" mimo ustawienia; poprawny JSON z nieprawidlowym kluczem: `Error: ...: Zadanie przez proxy nie powiodlo sie`
  i na stderr `Proxy request failed: {"error": "Failed to get access token"}` - rowniez w `--json` (kontrakt 9.2 dopuszcza tylko ponowienia i traceback).
- **P3-09.** `--horizontal-crs EPSG:5514` z `--bbox` (zabaged/data50/data250) jest przyjete (3045 -> blad); USAGE 1.9 i ARCHITECTURE 4.8 mowia "z obszarem = Error".
- **P3-10.** HSG: wartosci dokladnie na granicach trojkata USDA (calkowite g/kg: `silt+2*clay=300`, `clay=270`, `clay=400`) klasyfikuje szum float32 (`hsg.py` czyta `astype(np.float32)` i dzieli przez 10 przed float64): 18/22 116 i 13/28 098 pikseli rozni sie od niezaleznej implementacji float64, 0,05-0,08 %. Roznice A<->B i C<->D. Rozwiazanie: arytmetyka calkowita na g/kg albo float64.
- **P3-11.** Przy dwoch rownoleglych procesach ta sama jednostka: druga instancja drukuje na stderr linie bez prefiksu `Pominieto wersje bez czytelnego sidecara: <katalog> (naprawi ja nastepny zapis tej samej tresci)`; stan koncowy poprawny.
- **P3-12.** `soil hsg --summary` dla bbox w innym CRS niz EPSG:2180 liczy `Obszar zadania` z obwiedni w 2180: 1 km2 w EPSG:5514 = 116,78 ha (bbox 4326 0,1 x 0,1 st. na 55N: 7241,76 ha vs ok. 7110 ha); procenty proporcjonalne, ale "obszar" nie jest obszarem zadanym przez uzytkownika.
- **P3-13.** `-o` wskazujacy plik albo katalog tylko do odczytu: `Error: NotADirectoryError: [Errno 20] Not a directory: '.../afile/soil/...'` / `PermissionError` (system po angielsku, sciezka wewnetrzna) i to po pobraniu danych (1,6 s vs 0,5 s). Kontrola `-o` przed siecia dalaby 2 i krotki komunikat.
- **P3-14.** Offline `--check-updates` w `soil hsg` czeka 3 x 6,6 s (kolejne pozycje po kolei, 18,7 s); pierwszy blad sieci mogl by skrocic reszte.
- **P3-15.** Nazwy w `describe_store`: "BDOT10k ... GPKG"/"SHP" (biezace) vs "gml"/"shp" malymi (archiwum) - niespojna wielkosc liter.
- **P3-16.** `landcover list-layers --product bdot10k` i PRD 3.5 ("15 warstw - caly pakiet zrodlowy") vs rzeczywistosc: scalony GPKG ma 58 (powiat 2476) do 70 (1465) tabel (BU*, KU*, OI*, SK*, ...), `--layers` przyjmuje kazdy kod obecny w paczce (np. `BUBD`); ARCHITECTURE 4.8 mowi o 63 plikach. Podac, ze lista to wybor "pokrycie terenu i hydrografia".
- **P3-17.** `--layer` (warstwa pliku `--geometry`) vs `--layers` (klasy danych) - `--help`: "Warstwa GPKG (domyslnie pierwsza...)" nie mowi, ze chodzi o plik obszaru.
- **P3-18.** Katalog roboczy tylko do odczytu: `Warning: cache metadanych nieczytelny (...): unable to open database file - praca bez cache; uzyj kartograf cache clear albo usun plik` - plik nie jest nieczytelny, katalog jest tylko do odczytu; podpowiedz `cache clear` nie pomoze.
- **P3-19.** (znane, otwarte z poprzednich raportow) argparse po angielsku (`invalid choice`, `invalid int value`); pasek postepu jako linie na stdout bez TTY (`[=====---] 1/2 > 2463`, w `-q` znika).
- **P3-20.** Podglad CORINE ma 100 m/px (sztuka 22x24 px dla arkusza 1:10000), bez georeferencji (brak world file; sidecar ma `horizontal_crs` 3857 i `request.bbox` w 2180, a nie obwiednie obrazu); dla `--sheet N-34-130-D-d-2-4` tresc jest ledwie rozpoznawalna.
- **P3-21.** Obszary CZ (ZABAGED/Data50/Data250) bez estymaty czasu/ostrzezenia: 10 x 10 km = 81 s i 16 MB (21 890 obiektow), 100 x 100 km nie konczy sie w 25 s i nie ma limitu; nazwy plikow obszaru zaczynaja sie od `-` (narzedzia CLI, np. `ogrinfo -so plik`, wymagaja `./` lub `--`).
- **P3-22.** `--upgrade --plan` z planem innego produktu: `Error: landcover/pl_bdot10k_gpkg/teryt/2476.gpkg: zrodlo zmienilo sie od planu (None) - sprawdz ponownie` (wyciek `None`, mylaca przyczyna), a z planem innego obszaru tego samego produktu - ciche 0 bez zadnego wyjscia (znane U5).
- **P3-23.** `Nieznany kod wojewodztwa: 99. Dostepne kody: ['02', ...]` (repr listy, znane); `--teryt 99` dla `bdoo`: "wojewodztwo (2 cyfry) albo powiat (4 cyfry)", choc powiat jest odrzucany innym komunikatem (`--teryt 1261`).
- **P3-24.** `--layers ""`/`"SWRS,"`: `Nieprawidlowe kody warstw BDOT10k:  (4 litery, np. PTWP, SWRS)` z pusta wartoscia - powinno byc "pusty kod warstwy".
- **P3-25.** Offline, nowy arkusz CORINE: `Pobranie CLC 2018 for bbox (769784,510734)-(772035,513167) nieudane` - angielskie "for bbox" i wspolrzedne wewnetrzne 2180 zamiast godla.
- **P3-26.** `--check-updates` w trybie domyslnym BDOT10k/BDOO/podgladu CORINE/obszarow CUZK: linia `lokalna wersja ... (bez sprawdzania; --check-updates)` sugeruje flage, ktora odpowie tylko `nie da sie sprawdzic bez pobrania` (zgodne z USAGE 4.3, ale mylace; wystarczy "pobierz ponownie: --force").

## 5. Uwagi do dokumentacji

- `llms.txt:67` - patrz P3-01.
- `docs/USAGE.md` 1.5, `docs/PRD.md` 3.7, `soil list-layers`, `soil download --help` - jednostki SoilGrids (P2-4); USAGE 5 mowi "11 parametrow x 6 glebokosci x 5 statystyk" (w praktyce 9 wlasciwosci, `ocs` tylko 0-30 cm).
- USAGE 1.5/PRD 3.6/`list-layers --product corine`/`--help --year`: lata 2012, 2006, 2000 z podgladem WMS nie dzialaja (P2-1), a 1990 dla PL daje pusty obraz (P2-2); USAGE 7 mowi, ze CLMS "nie bylo sprawdzone na zywo" - zgodnie, odczyt wydania z katalogu CLMS dziala (potwierdzone: `V2020_20u1` dla 2018/2012/2006/2000).
- USAGE 1.8 ("Limit obszaru") - dopisac, czy dotyczy BDOT10k (P2-6).
- USAGE 1.9 i ARCHITECTURE 4.8: `--horizontal-crs` z obszarem = blad tylko dla EPSG:3045 (P3-09).
- PRD 3.5 "15 warstw - caly pakiet zrodlowy" i ARCHITECTURE 4.8 "63 pliki" vs 58-70 (P3-16).
- CHANGELOG [0.8.0] (Przeglad spojnosci UX): "`--plan` bez `--check-updates`/`--upgrade` to `Error:` z kodem 1" i "`project init` bez `--output`: kod 1" - rzeczywisty kod to 2 (PL03, BT10: `--output wymagane` = 2), zgodnie z USAGE 9.3; wpis nieaktualny po zmianie agentowej.
- USAGE 1.5: sha8 SoilGrids/HSG (`2.0_717f0989`, `2.0_470ef3d9`) niereprodukowalne (ISRIC zmienil bajty GeoTIFF, tresc ta sama); komentarz "# 4 powiaty rownolegle" opisuje `--workers 4` dla 2 powiatow (0208 = 112 MB + 0224 = 59 MB), nie jest lekkim przykladem.
- ARCHITECTURE 4.8 (tabela sygnalow `metadata`): "wydanie niedostepne = domyslnie `unverified=check_failed` (CLI `Warning:`)" - po errata 3 tryb domyslny nie pyta zrodla (USAGE 4.3, F12): do uzgodnienia.
- USAGE 1.5/README: przyklady dzialaja dokladnie (README `soil hsg --sheet N-34-130-D --summary`, `zabaged "--bbox=-460000,..."`; USAGE 1.9 Data50/Data250, archiwum 2018 GML); etykiety i nazwy plikow zgodne.
- `catalog`: brak przykladow dla Data50/Data250, archiwum BDOT10k (`--year/--format`), `--layers`, `--whole-country`, `soil hsg --geometry`.

## 6. Czego nie dalo sie sprawdzic

- Pobranie CORINE z CLMS (GeoTIFF) - brak `CLMS_CREDENTIALS` (decyzja uzytkownika); sprawdzone: komunikat i podglad WMS, odczyt wydania z publicznego katalogu (ze sztucznymi poswiadczeniami), blad tokenu.
- `--upgrade` z faktycznie nowszym wydaniem SoilGrids/CLMS/feedu ATOM (brak nowszego wydania; sprawdzone sciezki `aktualne`/`lokalna`/`bez zmian`/`uzyta ponownie`) oraz wykrywanie nowych wydan BDOT10k.
- Pliki krajowe ZABAGED (5,8/6,7 GB), Data50 (516/757 MB), Data250 3045 (320 MB): tylko `--check-updates`; pobrany tylko Data250 EPSG:5514 (230 MB, 857 s).
- Interaktywny TTY: pasek postepu i prawdziwy Ctrl-C z klawiatury (uzyto sygnalu SIGINT); semantyka dowiazan twardych na innym systemie plikow niz SMB.
- Dokladne wspolczynniki jednostek SoilGrids poza clay/sand/silt (wnioskowanie z rzedow wielkosci i konwencji ISRIC); tresc `ocd`/`ocs` (nie da sie pobrac).
- Zgodnosc tresci BDOT10k z geoportalem (sprawdzono: scalony GPKG == paczka zrodlowa, liczby wierszy 58/58 tabel; wybor powiatow z PRG potwierdzony niezaleznie dla dwoch arkuszy).
- `project add` zadan landcover/soil oraz pozostale grupy (poza plasterkiem C).
