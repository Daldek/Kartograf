# Paczki BDOO GUGiK (plan E, E4) - nagranie 2026-10-16

`GET`/`HEAD` `https://opendata.geoportal.gov.pl/bdoo/<rok>/PL.PZGiK.201.<woj>.zip`
(`curl`, 2026-10-16). Pobrano wszystkie 112 paczek (16 wojewodztw x 7
rocznikow); surowe pliki: `<katalog-danych>`. Serwer nie wysyla `ETag` ani
`Last-Modified` (sygnal `none`) i ignoruje `Range`.

| Plik | Zawartosc |
|---|---|
| `packages.json` | paczki 12/2023, 24/2023, 12/2015 i 12/2026: prawdziwy URL, naglowki `HEAD` (`Content-Type`, `Content-Length`) i pelna lista czlonow ZIP (kolejnosc katalogu centralnego); `bdoo_2018_12_missing`: odpowiedz `GET` 404 (`text/html`, tresc 1:1) |
| `classes.json` | `classes`: kody klas (`__OT_<KOD>_<typ>.`) w paczce kazdego wojewodztwa i rocznika; `content_length`: rozmiar kazdej paczki w bajtach |
| `real_2026_10_16/PL.PZGiK.201.12_2023_trimmed.zip` | prawdziwa paczka 12/2023 przycieta do 6 plikow (klasy KUIK i SKPP, obiekt zlozony `OT_Elektrownia`, `Uzytkownik12.xml`, metadane KU, XSD) i 4 katalogow; nazwy, kolejnosc, daty i kompresja czlonow jak w zrodle, tresc plikow bajt w bajt |

## Fakty z nagrania

- Roczniki 2015, 2021, 2022, 2023, 2024, 2025, 2026 (`HEAD` 200); 2014,
  2016-2020 i 2027: 404 (`text/html`, tresc `plik nie istnieje: <sciezka>`).
  Pliku krajowego w tym schemacie brak.
- Paczka wojewodztwa 12: 14 610 551 B (2015), 13 193 789 B (2021),
  13 098 998 B (2022), 11 514 714 B (2023), 9 264 609 B (2024),
  9 242 883 B (2025), 9 389 217 B (2026).
- 2015-2023: pliki GML z rozszerzeniem `.xml` w katalogu
  `PL.PZGiK.201.<woj>/BDOO/` (2015: przedrostek `PL.PZGIK`), obok nich
  obiekty zlozone (`__OT_Ciek.xml`, `__OT_SzlakDrogowy.xml`, ...),
  `Uzytkownik<woj>.xml`, `METADANE/` i `XSD/`. 2024-2026: pliki `.gml`
  i (2025-2026) `XSD/`.
- Klasy rocznika (suma po 16 wojewodztwach): 2015 - 44, 2021-2023 - 37,
  2024-2026 - 26. W latach 2015-2023 paczka wojewodztwa nie ma pliku klasy,
  ktorej obiektow tam nie ma (np. `PTPL` jest w 2023 tylko w paczkach 22
  i 24, `KUIK` nie ma w 10, 16, 20, 24 i 26; `classes.json`); 2024-2026:
  kazda paczka ma wszystkie 26 klas.
- Uklad wspolrzednych plikow GML: `srsName="EPSG:2180"` (2D).

Testy: `tests/test_bdoo.py`, `tests/test_parity_e4.py`, `tests/test_project_e4.py`.
