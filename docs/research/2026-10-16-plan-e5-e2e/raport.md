# Plan E / E5 — weryfikacja end-to-end (2026-10-16)

## Warunki i zakres

Uruchomiono rzeczywiste komendy `kartograf models3d download` (mesh 3D,
drzewa) i `kartograf geodesy download` (osnowy PL i CZ, quasi-geoidy) na
gałęzi `feat/plan-e5`, z katalogu worktree, przez Python środowiska `.venv`
(`python -m kartograf.cli.commands`). Dane, sidecary i logi zapisano
w jawnym katalogu poza repozytorium; `<katalog-danych>` oznacza lokalizację
danych, nie jest ścieżką do umieszczenia w projekcie. Zapytania dotyczyły
usług GUGiK (WFS indeksu mesh, WFS osnów, opendata, PRG WFS) i CUZK
(ArcGIS REST `BodovaPole`, ATOM QGZU, openzu); żadna z prób nie korzystała
z atrap HTTP. Zmiany planu względem pierwotnej listy kroku "Live" (decyzja
poprzedniego wykonawcy E5, przyjęta przez koordynatora): drzewa 3063
(325 MB) zamiast 2261 (3,4 GB), archiwum 1942 arkusza N-33-58 (2,8 MB)
zamiast M-34-64 (1,07 GB; rozmiar tylko z `HEAD`).

## Pobrania

| Komenda (każda z `-o <katalog-danych>`) | Rzeczywisty wynik i pomiar |
|---|---|
| `models3d download --product mesh --country pl --bbox 566200,244650,566250,244700` (Kraków) | `Info: mesh: kafle obszaru (1): s7/78944_6777_74230_55482`; `models3d/pl_mesh/s7/78944_6777_74230_55482.zip`, wersja `2021-10-03_DFT.7201.043.2023_7950f585` (etykieta = data i numer zgłoszenia pracy z rekordu); 46 179 000 B, 6 członów (4 JPG, MTL, OBJ 64 MB), `unzip -t` bez błędów; wierzchołki OBJ w PL-2000 strefa 7 (E 7 422 999, N 5 548 200, H 204 m); sidecar `EPSG:2178` + `EPSG:9651`, `extra.source.record` (`modul` 74230_55482, `uklad_h` PL-EVRF2007-NH), `extra.parent_request` = obszar; 17 s. |
| `models3d download --product trees --teryt 3063` | `Warning: trees PL 3063: duzy plik .../LOD1/2023/30/3063.zip - 324674789 B (ok. 325 MB)` przed transferem; `models3d/pl_trees_lod1_2023/teryt/3063.zip`, wersja `2023_25a77518`; 40 plików GML CityGML (5,3 GB po rozpakowaniu), `unzip -t` bez błędów; 99 s. |
| `geodesy download --product control --country pl --network horizontal\|vertical\|magnetic --bbox 560000,240000,575000,250000` (Kraków) | trzy GeoPackage `geodesy/pl_control_<siec>/bbox/560000_240000_575000_250000.gpkg` w EPSG:2180: pozioma 3 + 3 punkty (`fundamentalna_pozioma`, `bazowa_pozioma`), wysokościowa 1 + 150, magnetyczna 0 + 0 punktów i 1 strefa `izogony`; 7–9 s każda. |
| `geodesy download --product control --country pl --network gravity --bbox 560000,240000,575000,250000` | `Error: 560000_240000_575000_250000: WFS .../OsnowaGrawimetryczna/WFS: brak obiektow w obszarze (...)`, kod 1 — sieć grawimetryczna nie ma punktu w tym obszarze. |
| `... --network gravity --bbox 500000,200000,650000,300000` | `geodesy/pl_control_gravity/bbox/500000_200000_650000_300000.gpkg`: 12 + 6 punktów (jak fixtura E0); 6 s. |
| `geodesy download --product control --network horizontal\|vertical --teryt 1201` | `geodesy/pl_control_horizontal_package/teryt/1201.zip` (2 883 814 B, 17 członów: opisy JPG i 8 wykazów XLS) i `pl_control_vertical_package/teryt/1201.zip` (14 190 226 B, 85 członów); `unzip -t` bez błędów; 6 s każda. |
| `geodesy download --product control --network gravity --teryt 1201` | `Error: --network gravity: control (PL) - dostepne tylko dla --bbox/--sheet/--geometry (obiekty obszaru); dla --teryt: horizontal, vertical`, kod 1, bez zapytań. |
| `geodesy download --product control --network archive-kronsztadt60 --sheet M-34-064-D` | `Info: control: arkusze (1): M-34-64`; `geodesy/pl_control_archive-kronsztadt60/M-34/64/M-34-64.zip` (26 007 952 B: PDF 30,7 MB i TIFF 1,3 MB); 9 s. |
| `geodesy download --product control --network archive-1942 --sheet N-33-58` | `geodesy/pl_control_archive-1942/N-33/58/N-33-58.zip` (2 764 933 B: dwie karty PDF w `kartoteki/`); 2 s. |
| `geodesy download --product control --country cz --network vertical --bbox=-452000,-1113000,-449000,-1110000 --bbox-crs EPSG:5514` (Český Těšín) | `geodesy/cz_control_vertical/bbox/-452000_-1113000_-449000_-1110000.gpkg`: warstwa `bod_zvbp`, 10 punktów (jak `returnCountOnly` fixtury), EPSG:5514; 1,2 s. |
| `... --country cz --network horizontal` (ten sam obszar) | sześć warstw ZPBP (`bod_zpbp` 1, `pridruzeny_bod_k_bodu_zpbp` 1, `bod_zpbp_urceny_v_etrs89` 1, trzy warstwy RTK/ETRS89 puste); 2 s. |
| `geodesy download --product control --country auto --network vertical --bbox 18.55,49.70,18.70,49.78 --bbox-crs EPSG:4326` (Cieszyn) | dwa pliki: `cz_control_vertical/bbox/<EPSG:5514>.gpkg` (`bod_zvbp` 126) i `pl_control_vertical/bbox/<EPSG:2180>.gpkg` (1 + 13); `Nowe: 2`; 7 s. |
| `... --country auto` bez `--network` | `Error: --network wymagane dla obszaru control (CZ): gnss, horizontal, ... (zadanie PL+CZ: jedna wartosc dla obu krajow - PL: horizontal, vertical, gravity, magnetic, archive-1942, archive-kronsztadt60; wspolne: horizontal, vertical, gravity)`, kod 1. |
| `geodesy download --product geoid --country pl --whole-country` | `Warning: geoid PL: plik krajowy .../Model_quasi-geoidy-geoid2021-PL-EVRF2007-NH.txt - 42328086 B (ok. 42 MB)` przed transferem; `geodesy/pl_geoid2021_evrf2007/country/pl.txt`, wersja `2026-10-16_d695cf81`; SHA-256 `d695cf81…5ea6` = raport E i fixtura (plik bez zmian); nagłówek `Szerokosc Dlugosc Zeta`, wiersze CRLF; sidecar `EPSG:9702`, `vertical_crs: null`; 14 s. |
| `geodesy download --product geoid --country cz --whole-country` | `Warning: geoid CZ: plik krajowy https://openzu.cuzk.cz/opendata/QGZU/KVAZIGEOID.zip - 58190406 B (ok. 58 MB)`; `geodesy/cz_qgzu2013/country/cz.zip`, wersja `2021-02-22_aacfba6b` (data wpisu feedu ATOM); SHA-256 `aacfba6b…dfa3` = raport E; sidecar `EPSG:4258`; 12 s. |
| `geodesy download --product geoid --country pl --bbox 560000,240000,575000,250000` | `Error: geoid (PL) nie ma danych dla obszaru; dostepne: --whole-country (plik krajowy)`, kod 1, bez zapytań. |

## Odmowy przed pobraniem (limit obszaru)

| Komenda | Wynik |
|---|---|
| `models3d download --product mesh --country pl --bbox 566000,244000,568000,246000` (Kraków, 2 x 2 km) | `Info:` 122 kafle obszaru; `Error: mesh: obszar daje 121 plikow do pobrania, szacunkowo ok. 5,7 GB (sredni rozmiar 5 z 121 plikow wg HEAD) - limit jednego zadania to 100 plikow i 10 GB. Zawez obszar ...`, kod 1; kafel pobrany wcześniej (lokalna wersja) nie jest liczony; żaden kafel nie został pobrany; 2,9 s. |
| `models3d download --product trees --country pl --bbox 560000,240000,575000,250000` | `Info: trees: powiaty obszaru wg PRG (2): 1206, 1261`; `Error: trees: obszar daje 2 plikow do pobrania, razem ok. 13,7 GB wg HEAD - limit ... wybierz jednostke (--teryt <4 cyfry>) ...`, kod 1; tylko `HEAD` paczek (64 s), bez transferu. |

## Drugi przebieg i aktualizacje

- Mesh: kolejne uruchomienie → `lokalna wersja 2021-10-03_DFT.7201.043.2023`
  (indeks WFS, bez pobrania pliku, 1,3 s); `--check-updates` →
  `s7/78944_6777_74230_55482: aktualne (2021-10-03_DFT.7201.043.2023)`
  (sygnał `index`: etykieta rekordu).
- Drzewa 3063: `lokalna wersja 2023 (bez sprawdzania; --check-updates)`;
  `--check-updates` → `nie da sie sprawdzic bez pobrania (2023)`.
- Osnowy PL (obszar, paczka 1201, archiwum M-34-64), Bodove pole
  i PL-geoid2021: `lokalna wersja 2026-10-16 (bez sprawdzania;
  --check-updates)`, 0,5–0,9 s.
- PL-geoid2021 z `--force`: ponowny transfer (14 s) → `bez zmian 2026-10-16`.
- QGZU: kolejne uruchomienie → `lokalna wersja 2021-02-22` (tylko feedy,
  1,3 s); `--check-updates` → `cz: aktualne (2021-02-22)`.

## Fakty źródeł (2026-10-16)

- Plik kafla mesh to OBJ we współrzędnych strefy PL-2000 rekordu (z
  prefiksem strefy w E) i wysokościach PL-EVRF2007-NH; ZIP nie ma katalogu.
- Paczka drzew: pliki `<TERYT>_<godło 1:500>.gml` (CityGML LoD1,
  `srsName="EPSG:2180"` bez układu wysokości); `HEAD` paczek 1206 i 1261
  (razem 13,7 GB) trwał 64 s.
- Osnowa grawimetryczna i magnetyczna są rzadkie: w obszarze 15 x 10 km
  Krakowa nie ma ich punktów (magnetyczna: tylko strefa izogon).
- Archiwum Kronsztadt60 `M-34-64` ma PDF z godłem `M-34-064` w nazwie, ale
  adres paczki jest bez zera wiodącego (`M-34-64.zip`; `M-34-064.zip` = 404).
- QGZU: feed usługi na `atom.cuzk.gov.cz` linkuje feed zbioru i plik na
  hostach `atom.cuzk.cz` i `openzu.cuzk.cz`; data wydania 2021-02-22 bez
  zmian od 2021.

## Ryzyka

- Paczki drzew mają 0,3–25 GB: obszar prawie zawsze przekracza 10 GB
  (`--teryt` pobiera jedną paczkę po `Warning` z rozmiarem).
- Mesh miast to setki kafli po ok. 40–60 MB: obszar powyżej 100 kafli
  trzeba zawęzić albo wykonać planem z częścią pozycji.
- Archiwum 1942 arkusza `M-34-64` (1,07 GB) nie zostało pobrane w całości
  (rozmiar tylko z `HEAD`, test offline sprawdza `Warning` przed
  transferem).
