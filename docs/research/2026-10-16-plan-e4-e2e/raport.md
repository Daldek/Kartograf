# Plan E / E4 — weryfikacja end-to-end (2026-10-16)

## Warunki i zakres

Uruchomiono rzeczywiste komendy `kartograf landcover download` (BDOO, Data50,
Data250) na gałęzi `feat/plan-e4`, z katalogu worktree, przez Python
środowiska `.venv` (`python -m kartograf.cli.commands`). Dane, sidecary
i logi zapisano w jawnym katalogu poza repozytorium; `<katalog-danych>`
oznacza lokalizację danych, nie jest ścieżką do umieszczenia w projekcie.
Zapytania dotyczyły usług GUGiK (opendata, PRG WFS) i CUZK (ArcGIS REST,
ATOM, openzu); żadna z prób nie korzystała z atrap HTTP.

## Pobrania

| Komenda (każda `landcover download ... -o <katalog-danych>`) | Rzeczywisty wynik i pomiar |
|---|---|
| `--source bdoo --teryt 12 --year 2023` | `pl_bdoo_2023/teryt/12.zip`, wersja `2023_bd431599`; 11 514 714 B, 64 człony (jak `HEAD`), sidecar EPSG:2180, etykieta rocznika; 7 s. |
| `--source bdoo --teryt 12 --year 2015` | `pl_bdoo_2015/teryt/12.zip`, `2015_76ae2c94`; 14 610 551 B, 78 członów; osobny segment rocznika; 5 s. |
| `--source bdoo --teryt 12 --year 2023 --layers PTWP,SWRS` | `pl_bdoo_2023_ptwp-swrs/teryt/12.zip`: tylko `__OT_PTWP_A.xml` i `__OT_SWRS_L.xml`, bajty, daty i kompresja członów jak w paczce źródłowej; GDAL czyta je bez rozpakowania (`/vsizip/`): PTWP 90 poligonów, SWRS 3328 linii, EPSG:2180; 6 s. |
| `--source bdoo --bbox 523000,253000,528000,258000 --year 2023 --layers KUIK,PTWP` | `Info:` województwa obszaru wg PRG (2): 12, 24; `Info: bdoo PL 24: paczka nie ma plikow klas KUIK ...; zapisano klasy PTWP`; dwa ZIP-y (12: KUIK i PTWP, 24: PTWP), `extra.parent_request` = obszar; linia podsumowania `Nowe: 2`; 11 s. |
| `--source bdoo --sheet M-34-63-B-b --year 2023` | `Info:` województwa 12 i 24; 12 = lokalna wersja, 24 = nowa (8,4 MB). |
| `--source bdoo --teryt 12 --year 2026 --layers PTWP,SWRS` | Rocznik z plikami `.gml`: `pl_bdoo_2026_ptwp-swrs/teryt/12.zip`, `2026_ab3c1927`. |
| `--source bdoo --teryt 1261 --year 2023` | `Error: --teryt 1261: bdoo jest publikowane per wojewodztwo - podaj --teryt 12; ...`, kod 1, bez zapytań. |
| `--source bdoo --teryt 12 --year 2018` | `Error: --year 2018: niedostepne; dostepne: 2015, 2021, ..., 2026`, kod 1 (źródło: 404). |
| `--source data50 --bbox 18.566,49.757,18.572,49.761 --bbox-crs EPSG:4326` (Český Těšín) | Jeden GPKG `cz_data50/bbox/-450998.7179_-1112011.026_-450531.4728_-1111532.273.gpkg`: 69 warstw EPSG:5514, obiekty w 9 (m.in. `vodni_tok` 1, `louka_pastvina` 2, `les` 2, `vrstevnice` 6) — zgodnie z `returnCountOnly` z fixtur; obszar w EPSG:4326 w `extra.parent_request`; 13 s. |
| `--source data250` (ten sam obszar) | 116 warstw EPSG:5514, obiekty w 7 (m.in. `vodni_tok_povrchovy_staly_do_5_m` 1, `les` 2); 22 s. |
| `--source data50 --whole-country --horizontal-crs EPSG:5514` | `Warning: ... data50.zip - 515542917 B (ok. 516 MB)` przed transferem; `cz_data50_shp_5514/country/cz.zip`, wersja `2026-04-28_e1354cdd` (data `updated` feedu); 557 członów; 138 s. |
| `--source data250 --whole-country --horizontal-crs EPSG:5514` | `Warning: ... 230485722 B (ok. 230 MB)`; `cz_data250_shp_5514/country/cz.zip`, `2026-05-12_ae501843`; 448 członów (w tym rastry reliefu `.tif`); 66 s. |

## Drugi przebieg i aktualizacje

- BDOO 12/2023: kolejne uruchomienie → `lokalna wersja 2023 (bez sprawdzania;
  --check-updates)`, bez pobierania; `--force` → `bez zmian 2023` (także
  z `--layers PTWP,SWRS`: ten sam ZIP klas bajt w bajt); `--check-updates`
  → `nie da sie sprawdzic bez pobrania (2023)` (GUGiK nie wysyła `ETag`
  ani `Last-Modified`).
- BDOO obszaru z `--layers`: `lokalne: 2`, odpowiedź PRG z cache metadanych.
- Pliki krajowe Data50 i Data250: kolejne uruchomienie → `lokalna wersja`
  (sam odczyt feedu, 2–6 s); `--check-updates` → `aktualne (2026-04-28)`
  i `aktualne (2026-05-12)`.
- Obszar Data50: `--check-updates` → `nie da sie sprawdzic bez pobrania`;
  kolejne uruchomienie → lokalna wersja.

## Fakty źródeł (2026-10-16)

- BDOO: roczniki 2015 i 2021–2026; paczka województwa do 2023 nie ma pliku
  klasy bez obiektów w województwie (np. KUIK w 24/2023 — potwierdzone
  pobraniem obszaru); od 2024 pliki `.gml` i 26 klas w każdej paczce.
- Plik krajowy SHP ma własne nazwy warstw (Data50: `shp/Akvadukt.shp`,
  Data250: `DATA250_2026_SHP/AirfldA.shp`), inne niż warstwy usługi REST
  zapisywane w wyniku obszaru; Kartograf zapisuje go 1:1.
- `HEAD` plików krajowych: `Content-Length` = `length` feedu, `ETag`
  i `Last-Modified` (sygnał Kartografa: `metadata` z feedu, jak ZABAGED).

## Ryzyka

- Nowy rocznik BDOO albo zmiana klas wymaga aktualizacji rejestru (do tego
  czasu `Error:` z listą roczników/klas przed siecią).
- ZIP klas (`--layers`) to nowy kontener: treść członów jest identyczna ze
  źródłem, ale bajty ZIP-a różnią się od paczki GUGiK (sha256 w sidecarze
  opisuje zapisany plik).
