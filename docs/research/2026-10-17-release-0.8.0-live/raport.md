# Testy na zywo wydania Kartograf 0.8.0 (2026-10-16 i 2026-10-17)

Dwa testy na zywo przed wydaniem 0.8.0 i weryfikacja poprawek na galezi
`release/0.8.0`. CLI: `.venv/bin/python -m kartograf.cli.commands`
z korzenia repo albo worktree (cache metadanych w katalogu roboczym).
Dane wylacznie pod `<katalog-danych>` (poza repo, jawne `--output`, swiezy
magazyn na udziale SMB/cifs), logi `<katalog-danych>/logs/<etykieta>.log`.
Offline = `unshare -rn` (bez sieci, magazyn dostepny).

## Podsumowanie

| Test | Kod | Zakres | Znaleziska | Stan po poprawkach |
|---|---|---|---|---|
| 1. Pelny, 2026-10-16 | `develop` `8160839` (`0.8.0-dev+8160839`) | 18 polecen z 13 grup + `availability`, manifest z odtworzeniem, orto ukosna | P1: 0, P2: 2, P3: 19 | P2 naprawione; P3: 12 naprawionych, 2 decyzje (USAGE 7), 3 czesciowo, 2 otwarte (sekcja 4) |
| 2. Krotki, 2026-10-17 | `develop` `4e68fda` (`0.8.0-dev+4e68fda`) | 10 polecen z 8 grup, manifest, 6 funkcji API, regula 10 ARCHITECTURE 3.3 | P1: 0, P2: 0, P3: 9 | wszystkie naprawione |
| 3. Weryfikacja poprawek, 2026-10-17 | `release/0.8.0` | 9 polecen (sekcja 3) | - | zgodne z oczekiwaniem |

Gdzie naprawiono: galezie `fix/live-0.8.0` (FixLive), `fix/live2-0.8.0`
(FixLive2), `fix/ux-0.8.0`, `fix/docs-0.8.0`, `fix/smoke2-0.8.0`
(`15e0441`) i `release/0.8.0` (`e1516f7`); opis zmian i "Co zrobic":
`docs/CHANGELOG.md` [0.8.0].

## 1. Test pelny (2026-10-16, `develop` `8160839`)

GDAL 3.10.3, rasterio 1.5.0, pyproj 3.7.2 (PROJ 9.5.1); start z cache
metadanych repo (94 rekordy). Kazde polecenie: `kartograf <...> -o
<katalog-danych>/data`; pierwszy przebieg w 4 rownoleglych kolejkach,
drugi i `--check-updates` po kolei.

| # | Polecenie | 1. przebieg | t1 | t2 | t2 offline (kod) | `--check-updates` |
|---|---|---|---|---|---|---|
| 1 | `elevation download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007` | `nowa wersja 2025-04-26_82710_fdd30535` (ASC 38 MB, `full_sheet/`) | 27,9 s | 1,3 s | 1,2 s (0) | `aktualne` z cache, takze offline (P2-2) |
| 2 | `elevation download --bbox 530000,382000,533000,386000 --country pl --product nmt --cutout --horizontal-crs EPSG:2180 --vertical-crs EVRF2007` | 3000 x 4000 px, 16 zapytan WCS, 4 ponowienia | 667,1 s | 1,0 s | 1,0 s (0) | `nie da sie sprawdzic bez pobrania` |
| 3 | `elevation download --sheet CTES96 --product nmt --vertical-crs Bpv` | DMR 4G 5 m, 0,8 MB | 1,6 s | 0,8 s | 6,6 s (0, `Warning` po 3 probach HEAD) | `aktualne` (ETag) |
| 4 | `elevation download --bbox 771500,508985,771700,509185 --country pl --product laz --vertical-crs EVRF2007` | 1 kafel, 108 MB | 45,5 s | 3,5 s | kod 1 | `aktualne` 9,5 s |
| 5 | `imagery download --sheet N-34-130-D-d-2-4 --product orto` | 300 MB, `Warning: ... duzy plik` | 110,3 s | 6,2 s | 6,0 s (0) | `aktualne` |
| 6 | `imagery download --product orto --sheet CTES96` | JPG 64 MB + 3 x JGW | 22,5 s | 1,5 s | 7,4 s (0, `Warning` ATOM) | `aktualne` x 4 |
| 7 | `landcover download --source bdot10k --teryt 1465` | GPKG 332 MB | 41,1 s | 3,5 s | 3,5 s (0) | `nie da sie sprawdzic` |
| 8 | `landcover download --source corine --year 2018 --sheet N-34-130-D` | podglad WMS PNG + `Info:` o CLMS | 1,3 s | 0,5 s | 0,5 s (0) | `nie da sie sprawdzic` |
| 9 | `soil download --bbox 626000,480000,628000,482000 --property clay --depth 0-5cm --stat mean` | GeoTIFF 13 x 8 px EPSG:4326 | 1,2 s | 0,8 s | 6,6 s (0, `Warning`) | `aktualne` |
| 10 | `soil hsg --bbox 626000,480000,628000,482000 --depth 0-5cm --stats` | clay lokalny, sand/silt nowe, HSG | 2,1 s | 1,1 s | 18,8 s (0) | `aktualne` x 4 |
| 11 | `boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000` | GPKG 2,1 MB | 5,1 s | 0,6 s | 0,6 s (0) | `nie da sie sprawdzic` |
| 12 | `cadastre download --product map --country pl --bbox 565000,243000,567000,245000` | GPKG 3,5 MB | 19,6 s | 0,6 s | 0,6 s (0) | `nie da sie sprawdzic` |
| 13 | `models3d download --product buildings --lod 2 --country pl --bbox 566000,243000,566500,243500` | ZIP 60 MB (powiat 1261) | 22,5 s | 1,1 s | 1,1 s (0) | `nie da sie sprawdzic` |
| 14 | `hydro download --product network --country cz "--bbox=-470000,-1130000,-440000,-1100000" --bbox-crs EPSG:5514` | GPKG 6,5 MB | 23,1 s | 0,6 s | 0,6 s (0) | `nie da sie sprawdzic` |
| 15 | `names download --product geographic --country pl --bbox 19.93,50.055,19.945,50.065 --bbox-crs EPSG:4326` | GPKG, 9 obiektow | 88,0 s | 0,5 s | 0,6 s (0) | `nie da sie sprawdzic` |
| 16 | `maps download --product topographic --country pl --sheet M-34-064-D-d-1 --scale 1:10000 --format TIFF` | TIFF 67 MB | 25,2 s | 1,9 s | kod 1 | `aktualne` |
| 17 | `geodesy download --product control --country pl --network vertical --bbox 560000,240000,575000,250000` | GPKG 0,2 MB | 7,0 s | 0,5 s | 0,5 s (0) | `nie da sie sprawdzic` |
| 18 | `elevation availability --product nmt --country pl --bbox 565000,242000,569000,246000` | 20 kombinacji 2009-2025 z liniami `Pobranie`/`W projekcie` | 6,0 s | 1,9 s | 2,0 s (0) | - |

Dodatkowo: orto ukosna `--sheet 7.125.11.08 --direction n` (302 MB, 96,6 s)
i `--sheet 6.223.25.11.4 --direction n` (116 MB, 49,2 s); podpowiedzi
`availability` (`--year 2025`: 6 arkuszy; archiwum `--format TTN
--vertical-crs KRON86 --year 2009`: 4 arkusze) sprawdzone
`--check-updates`. Polecenia 7 i 10 uzywaly nazw flag sprzed ADR-044
(`--source`, `--stats`).

**Manifest** (`--project <katalog-danych>/projekt --output
<katalog-danych>/magazyn-projekt`): `init`, `add` (6 zadan z 6 grup),
`download` (`przypiete 6 ... bledy 0`, 13 plikow, 74,6 s), `status`,
`verify`, ponowne `download` online i offline (`bez zmian 6`), odtworzenie
na pustym magazynie (`odtworzone 6`, SHA-256 zgodne, takze z zegarem +3 dni),
wykrycie uszkodzonego pliku i bledy wejscia (`Error:` po polsku, kod 1)
- OK.

**Orto ukosna `7.125.11.08_N` (pozycja otwarta z planu E):** GeoTIFF ma
parametry odwzorowania PL-2000 strefy 7 z etykieta datum WGS84 i bez kodu
EPSG; `gdalsrsinfo` zgaduje EPSG:32634 z pewnoscia 25 % (UTM 34N, bledne
dopasowanie). Wspolrzedne i rekord skorowidza (`PL-2000:S7`) potwierdzaja
EPSG:2178, wiec sidecar jest poprawny, a brak ostrzezenia - wlasciwy.
Kampania Gdansk 2024 ma poprawny tag EPSG:2177.

**Kody wyjscia:** walidacja 1, blad parsera 2, blad sieci/zrodla 1,
sukces z `Warning:` 0; bledy walidacji przed siecia, bez katalogow
produktow pod `--output`.

### Znaleziska i stan

| Pozycja | Stan | Gdzie |
|---|---|---|
| P2-1 LAZ `--sheet`: kafle z obwiedni ramy w EPSG:2180 i z kontaktow milimetrowych (13 kafli, 1,83 GB zamiast 4) | naprawione: kafle z ramy godla, kafel musi siegac w obszar glebiej niz 1 m; na zywo 4 kafle, `availability` 4,93 km2 | FixLive `b045c4f` |
| P2-2 `--check-updates` arkuszy PL odpowiadal z cache (TTL 7 dni), offline `aktualne` | naprawione: sprawdzenie zawsze pyta zrodlo, cache odswiezany; offline `nie udalo sie sprawdzic`, kod 1 | FixLive `5e01458` |
| P3-1 angielskie slowa (`resolution:`, `product:`, `to 1:2000`, `Pobieranie kafle LAZ`, opisy HSG) | naprawione: `rozdzielczosc:`, `produkt:`, `w skali`, `Pobieranie wycinka CZ`, `Pobieranie kafli LAZ`, opisy HSG po polsku | `fix/ux-0.8.0`, `15e0441`, `e1516f7` |
| P3-2 ponowienia bez prefiksu z surowym wyjatkiem; `ponow pobranie` w `--check-updates` | naprawione: `Warning: ... proba 1/3 nieudana (<przyczyna>)`; linia sprawdzenia konczy sie `wynik bylby niepelny` | FixLive `37d0f0e`, `e1516f7` |
| P3-3 pasek postepu bez TTY w logach, ikony bez legendy | otwarte | sekcja 4 |
| P3-4 nazwy API i reprezentacja Pythona w komunikatach | czesciowo: wybory jako flagi (`--teryt <4 cyfry> ..., --bbox/--sheet/--geometry`), `soil hsg -o plik.tif` = `--output to katalog magazynu`; zostaje `Dostepne kody: ['02', ...]` | `fix/ux-0.8.0`; sekcja 4 |
| P3-5 brak komendy = kod 0 | naprawione: pomoc na stderr, kod 2 | FixLive `37d0f0e` |
| P3-6 Ctrl-C = traceback | naprawione: `Error: przerwano (Ctrl-C)`, kod 130 (pusty katalog produktu zostaje) | FixLive `37d0f0e` |
| P3-7 argparse: skroty flag, ujemny `--bbox` po spacji, `invalid choice` po angielsku | czesciowo: bez skrotow, `--bbox -447000,...` dziala; zostaje `invalid choice` | `fix/ux-0.8.0`; sekcja 4 |
| P3-8 ponowne uruchomienie offline | czesciowo: tryb domyslny bez zapytan o sygnal (mapy, arkusze i orto CZ, SoilGrids; errata 3 ADR-036), mesh z rekordow indeksu w cache, podsumowanie LAZ dopiero po sukcesie; zostaje LAZ PL `--bbox` i zadania projektu z PRG/skorowidzem (wybor plikow pyta zrodlo, projekt bez cache metadanych) | FixLive2 `d342210`, `15e0441`; sekcja 4 |
| P3-9 rozny podmiot linii statusu | naprawione: sciezka pod `--output` w pobraniu i `--check-updates`, w projekcie `jednostka (plik)` | FixLive2 `d342210`, `15e0441` |
| P3-10 wycinek PL w calosci poza ladem: 6 zapytan WCS i plik nodata | naprawione: `Error:` przed WCS (maska PRG), bez wersji | FixLive2 `d342210` |
| P3-11 statystyki HSG bez braku danych; SoilGrids oddaje 0, nie -32768 | naprawione: linia `Brak danych`, procenty z powierzchni z danymi, obszar zadania; zera SoilGrids - decyzja: plik bez zmian, opis w USAGE 7 | FixLive2, `15e0441` |
| P3-12 wolne uslugi bez informacji | naprawione: `Info:` z szacowanym czasem przed seria WCS i przed zapytaniem PRNG; limit obszaru (drzewa 3D) bez osobnej zmiany | FixLive2 `d342210` |
| P3-13 SMB/cifs: pelny odczyt pliku dla kazdego dowiazania | decyzja: tylko USAGE 7 (bez skrotu w kodzie) | FixLive2 |
| P3-14 podpowiedzi projektu gubia `--project` | naprawione: `kartograf project add --project <KATALOG> NAZWA ...` | `69ae191` (`fix/ux-0.8.0`) |
| P3-15 odtworzenie innego dnia zmienia `version`/`label` | naprawione: zgodna SHA-256 = przypieta wersja, manifest bez zmian | FixLive2 `b68b882` |
| P3-16 USAGE 8 bez `geodesy download` | naprawione | `fix/docs-0.8.0` |
| P3-17 orto ukosna Krakow 2021 bez kodu EPSG | decyzja: USAGE 7 (VRT z `-a_srs EPSG:2178`), bez zmiany pliku | FixLive `7f2402d` |
| P3-18 `--check-updates --plan` do nieistniejacego katalogu - blad po sprawdzeniu zrodla | naprawione: katalog planu sprawdzany przed siecia | FixLive `37d0f0e` |
| P3-19 podpowiedz wariantu `ten arkusz` przy wielu arkuszach | otwarte | sekcja 4 |

## 2. Test krotki po zmianach API i nazw (2026-10-17, `develop` `4e68fda`)

Nowy magazyn: `<katalog-danych>/data` (scenariusz),
`<katalog-danych>/magazyn-projekt` (manifest), `<katalog-danych>/api-data`
(API); razem ok. 262 MB. Pierwszy przebieg wszystkie kod 0 (4-22 s), drugi
online kod 0 (0,7-1,5 s), offline 9/10 kod 0, `--check-updates` wszystkie
kod 0.

| # | Polecenie (`-o <katalog-danych>/data`) | 1. przebieg | t1 | t2 | `--check-updates` |
|---|---|---|---|---|---|
| 1 | `landcover download --product bdot10k --teryt 1863` | `landcover/pl_bdot10k_gpkg/teryt/1863.gpkg: nowa wersja` | 21,7 s | 1,5 s (`bez sprawdzania; --check-updates`) | `nie da sie sprawdzic bez pobrania` |
| 2 | `landcover download --product zabaged --bbox=-460000,-1120000,-459000,-1119000 --bbox-crs EPSG:5514` | `landcover/cz_zabaged/bbox/...gpkg: nowa wersja` + `Info:` (22 warstwy) | 8,0 s | 0,8 s | `nie da sie sprawdzic` |
| 3 | `soil download --property clay --depth 0-5cm --stat mean --bbox 626000,480000,628000,482000` | `soil/global_soilgrids_clay_0-5cm_mean/bbox/...tif: nowa wersja 2.0_717f0989` | 6,4 s | 0,7 s | `aktualne (2.0)` |
| 4 | `soil hsg --depth 0-5cm --bbox 626000,480000,628000,482000 --summary` | `hsg/global_soilgrids_0-5cm_mean/bbox/...tif: nowa wersja 2.0_470ef3d9`, B 100 % (76,90 ha), `Brak danych: 81.7% calego obszaru (344.01 ha)` | 4,1 s | 1,0 s (`uzyta ponownie`) | 4 x `aktualne (2.0)` |
| 5 | `imagery download --product true-orto --country pl --bbox 566200,244650,566300,244750 --cutout --horizontal-crs EPSG:2180 --resolution 0.05m` (Krakow) | `nowa wersja` z `Warning: wycinek w calosci bez obrazu`, sidecar `extra.all_nodata` | 19,1 s | 0,8 s | `nie da sie sprawdzic` |
| 5b | to samo z `--bbox 470100,740100,470200,740200` (Gdansk) | `true-orto/pl_1992_0.05m/bbox/470100_740100_470200_740200.tif: nowa wersja` | 14,1 s | 1,0 s | `nie da sie sprawdzic` |
| 6 | `models3d download --product mesh --country pl --bbox 566200,244650,566250,244700` | `models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip: nowa wersja` | 20,6 s | 1,5 s; offline kod 1 | `aktualne` |
| 7 | `geodesy download --product control --country pl --network vertical --bbox 560000,240000,575000,250000` | `geodesy/pl_control_vertical/bbox/...gpkg: nowa wersja` | 7,1 s | 0,7 s | `nie da sie sprawdzic` |
| 8 | `boundaries download --product admin --country pl --level gmina --bbox 550000,220000,590000,270000` | `boundaries/pl_prg_gmina/bbox/...gpkg: nowa wersja` | 6,4 s | 0,7 s | `nie da sie sprawdzic` |
| 9 | `elevation download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007` | `nmt/pl_1992_1m_evrf2007/.../N-34-130-D-d-2-4.asc: nowa wersja 2025-04-26_82710_fdd30535` | 22,2 s | 1,4 s | `aktualne`; offline `nie udalo sie sprawdzic`, kod 1 (P2-2 naprawione) |

Dodatkowo: `--upgrade` (soil, nmt) = `lokalna wersja`, kod 0 (pyta
zrodlo); stare `landcover --source`/`soil hsg --stats` = kod 2 z polska
podpowiedzia. Manifest: `init`, `add` x 3, `download` (`przypiete 3`),
`status`, `verify` OK; ponowny `download` online i offline `bez zmian 3`;
`add ... soil hsg --summary` = `Error: --summary nie jest czescia zadania`.
API: `download_landcover`, `download_soil`, `calculate_hsg`,
`hsg_statistics`, `download_image_cutout`, `get_project_status` - typy
wynikow spojne, drugie wywolanie `local`/`reused` bez sieci, bledy
`ValidationError` po polsku. Katalogi i klucze `dataset` 9 produktow
zgodne z regula 10 ARCHITECTURE 3.3.

### Znaleziska i stan

| Pozycja | Stan | Gdzie |
|---|---|---|
| P3-1 mesh `--bbox` offline kod 1 mimo lokalnego kafla | naprawione: rekordy indeksu obszaru w cache metadanych (TTL 7 dni); na zywo offline kod 0 (sekcja 3) | `15e0441` |
| P3-2 status projektu: sciezka jako jednostka wycinka | naprawione: `UnitFile.unit` wycinka = wspolrzedne | `15e0441` |
| P3-3 sidecar `product` land cover/HSG != `--product` | naprawione: `bdot10k`, `zabaged`, ..., HSG `hsg` | `15e0441` |
| P3-4 podsumowanie HSG dla calego rastra (420,91 ha przy bbox 400 ha) | naprawione: statystyki obszaru zadania, linia `Obszar zadania` (sekcja 3) | `15e0441` |
| P3-5 opisy grup HSG po angielsku | naprawione | `15e0441` |
| P3-6 `update="check"` wskazuje `check_sheets()` | naprawione: funkcja `check_*` toru | `15e0441` |
| P3-7 `download_image_cutout(bbox, ...)` pozycyjny, `coverage` wymagany | naprawione: argumenty nazwane, `coverage=None`; decyzja koordynatora: argumenty tylko nazwane we WSZYSTKICH funkcjach pobrania i sprawdzenia z `__all__` (errata 1 ADR-044) | `15e0441`, `e1516f7` |
| P3-8 true orto poza miastami: czarny plik jako wersja, `Warning` dopiero po 19 s | naprawione: `NoCoverageError` przed zapisem wersji; decyzja koordynatora: tak samo ortofotomapa `high`/`standard` w calosci 0,0,0 (errata 6 ADR-042). Listy miast nie ma - usluga nie publikuje zasiegu wycinka | `15e0441`, `e1516f7` |
| P3-9 pozostalosci testu 1: `(resolution: 1m)`, `ponow pobranie` w `--check-updates`, `RuntimeWarning` przy `python -m` | naprawione | `e1516f7`, `15e0441` |

## 3. Weryfikacja poprawek na zywo (2026-10-17, `release/0.8.0`)

Swiezy magazyn `<katalog-danych>/verify/data` (141 MB z logami), CLI
z korzenia worktree.

| Polecenie (`-o <katalog-danych>/verify/data`) | Wynik | Czas |
|---|---|---|
| `elevation download --sheet CTES96 --product nmt --vertical-crs Bpv` | `Pobieranie CTES96 (CZ, rozdzielczosc: 5m)...`, `nowa wersja` | 3,9 s |
| `elevation download --sheet N-34-130-D-d-2-4 --product nmt --resolution 1m --vertical-crs EVRF2007` | `Pobieranie N-34-130-D-d-2-4 (rozdzielczosc: 1m)...`, `nowa wersja 2025-04-26_82710_fdd30535` | 18,6 s |
| to samo z `--check-updates`, offline | kod 1, `...N-34-130-D-d-2-4.asc: nie udalo sie sprawdzic: WFS GetCapabilities ...: pobranie nieudane po 3 probach (brak sieci albo DNS (nieznana nazwa serwera)) - wynik bylby niepelny` (bez `ponow pobranie`) | 6,8 s |
| `imagery download --product true-orto --country pl --bbox 566200,244650,566300,244750 --cutout --horizontal-crs EPSG:2180 --resolution 0.05m` (Krakow) | kod 1, `Error: wycinek true orto: WCS GUGiK nie ma w tym obszarze prawdziwej ortofotomapy - obejmuje tylko wybrane miasta, np. Gdansk, a obraz obszaru jest w calosci 0,0,0; wersja nie powstala, zmien --bbox`; brak plikow i katalogow `true-orto/` | 6,6 s |
| `imagery download --product orto --country pl --bbox 738900,626500,739000,626600 --cutout --horizontal-crs EPSG:2180 --coverage high --resolution 0.1m` | kod 1, `Error: wycinek ortofotomapy high: WCS GUGiK nie ma w tym obszarze ortofotomapy o pikselu 10 cm i mniejszym, a obraz obszaru jest w calosci 0,0,0; wersja nie powstala, zmien --bbox albo uzyj --coverage standard`; brak plikow `orto/pl_1992_high_*` | 3,5 s |
| to samo z `--coverage standard --resolution 0.25m` | `orto/pl_1992_standard_0.25m/bbox/738900_626500_739000_626600.tif: nowa wersja` | 2,8 s |
| `soil hsg --depth 0-5cm --bbox 626000,480000,628000,482000 --summary` | 3 wejscia i HSG `nowa wersja`; `Statystyki HSG obszaru zadania (grupy: % powierzchni z danymi)`, `Grupa B: 100.0% (71.03 ha)` z opisem po polsku, `Brak danych: 82.3% obszaru zadania (329.48 ha)`, `Obszar zadania: 400.51 ha` (powierzchnia na elipsoidzie bboxa 2 x 2 km w EPSG:2180) | 7,8 s |
| `models3d download --product mesh --country pl --bbox 566200,244650,566250,244700` | `models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip: nowa wersja 2021-10-03_DFT.7201.043.2023_7950f585` | 21,9 s |
| to samo, offline (drugi przebieg) | kod 0, `lokalna wersja 2021-10-03_DFT.7201.043.2023` (test 2: kod 1 po 6,7 s) | 1,5 s |

Argumenty nazwane API (`download_pl_cutout(bbox, ...)` = `TypeError`) sa
sprawdzane offline (`tests/test_public_api.py`), bez wywolania na zywo.

## 4. Otwarte po testach (backlog `docs/PROGRESS.md`)

- Pasek postepu bez TTY (linie `\r[====---]` w logach i potokach) i ikony
  `> + o x 0` bez legendy (test 1, P3-3).
- `--teryt 9999`: `Dostepne kody: ['02', '04', ...]` - lista Pythona
  zamiast `02, 04, ...` (P3-4).
- Bledy parsera po angielsku: `invalid choice: 'dtm' (choose from ...)`
  (P3-7).
- Offline: LAZ PL `--bbox` (wybor kafli pyta WFS, bez cache) i zadania
  `project download` wymagajace PRG/skorowidza (projekt bez cache
  metadanych) koncza sie kodem 1 (P3-8).
- Podpowiedz wariantu `Skorowidz GUGiK ma ten arkusz w NMT 1m ...`
  powtarzana dla kazdego z kilku arkuszy (P3-19; propozycja: jedna linia
  z liczba arkuszy).
