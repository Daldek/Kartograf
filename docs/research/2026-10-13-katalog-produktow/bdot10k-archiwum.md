# BDOT10k archiwalny - formaty, rytm aktualizacji, paczki roczne (2026-10-13)

**Pytania (decyzja 9.3 specu):** (1) czy archiwum ma GPKG; (2) jak czesto
aktualizowany jest BDOT10k i czy archiwum to faktycznie jedna paczka na
rok.

**Zrodla:** WMS `https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT10k/WMS/DaneArchiwalne`
(warstwa `powiaty`, linki w `GetFeatureInfo`), WFS
`https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT/WFS/PobieranieBDOT10k`
(`ms:BDOT10k_powiaty`: `TERYT`, `Data_aktualizacji`, `URL_GML`), pliki
`https://opendata.geoportal.gov.pl/Archiwum/bdot10k/<rok>/<FMT>/<woj>/<teryt>_<FMT>_<rok>.zip`.
Probki: `pl.gugik.bdot10k_archive` w `probki.md`.

## 1. Formaty archiwum

- `GetFeatureInfo` dla 4 powiatow z roznych wojewodztw (1261 krakowski,
  0401 aleksandrowski, 1465 Warszawa, 3262 Szczecin): po 24 linki = lata
  2014-2025 x {GML, SHP}; zadnego innego formatu.
- `HEAD` na warianty GPKG (`<rok>/GPKG/12/1261_GPKG_<rok>.zip`,
  `<rok>/GPKG/12/1261_GPKG.zip`, `<rok>/gpkg/...`) dla 2014 i 2021-2025:
  wszystkie 404. Listing katalogu `Archiwum/bdot10k/2024/`: 404 (brak
  listingu).
- Wniosek: **archiwum = tylko GML i SHP** (GPKG jest wylacznie dla
  aktualnych danych, `bdot10k/schemat2021/GPKG/`).
- Kody warstw: archiwum 2014 (SHP) ma 71 klas `OT_*`, aktualny GPKG 69;
  wszystkie aktualne sa w 2014, 2014 ma dodatkowo `OT_BUCM_A`, `OT_KUHU_P`.

## 2. Rytm aktualizacji i paczki roczne

- Aktualne dane: `Data_aktualizacji` 380 powiatow - 2021: 2, 2022: 32,
  2023: 184, 2024: 158, 2025: 1, 2026: 3 (03.2026: 1, 08.2026: 2).
  Aktualizacja jest per powiat, nieregularna, w praktyce co 2-3 lata;
  powiat 1261: 2024-04-22.
- Archiwum: **jedna paczka na rok i format** dla kazdego roku 2014-2025
  (4 powiaty sprawdzone). Rok paczki to rocznik archiwum, nie data
  aktualizacji powiatu:
  - 1261: paczki 2022 i 2023 sa bajtowo identyczne (SHP sha256
    `6c64b1d33782...`, 46 762 581 B) - w 2023 powiat nie byl
    aktualizowany; 2021 i 2024 roznia sie (inne sha256).
  - Daty wpisow w ZIP: paczki 2014-2023 spakowane 2023-03-13 (archiwum
    utworzone hurtowo wstecz), 2024 - 2024-02-12, czyli przed aktualizacja
    1261 z 2024-04-22: paczka roku R = stan z poczatku roku R.
  - `HEAD` plikow archiwum nie zwraca `Last-Modified` ani `ETag`.
- Aktualna paczka GPKG ma wpisy ZIP z 2026-10-03 (przepakowanie po stronie
  GUGiK niezaleznie od `Data_aktualizacji`).

## 3. Wnioski do specu (decyzja 9.3)

1. `--year R` w `landcover --source bdot10k` = paczka archiwalna rocznika
   R (stan z poczatku roku R); format zrodlowy: `--format GML|SHP`;
   `--year` z GPKG (domyslnym dla aktualnych) = `Error:` z lista formatow
   archiwum; `--layers` filtruje pliki SHP/GML paczki po kodach `OT_*`.
2. Rok w segmencie jest zgodny ze sposobem udostepniania przez GUGiK
   (jedna paczka na rocznik): `landcover/pl_bdot10k_<format>_<rok>/teryt/<T>`.
3. Identyczne paczki kolejnych rocznikow (brak aktualizacji powiatu) w
   magazynie to ta sama tresc - mechanizm `relabeled` (ADR-036 D23), bez
   duplikatu danych.
4. Brak sygnalu swiezosci (`none`); rocznik archiwum sie nie zmienia,
   cicha poprawke u zrodla wykrywa tylko `--force` (ADR-036 4.1).
5. Wybor powiatow z dzisiejszego PRG: kod TERYT zmieniony od roku R daje
   404 dla tego powiatu (blad per powiat) - tylko opis w dokumentacji.
