# Paczki jednostek GUGiK (silnik `unit_package`, plan C)

Zapis 2026-10-15 (`HEAD`/`GET`, `opendata.geoportal.gov.pl`). `packages.json`
trzyma dla kazdej paczki prawdziwy URL, naglowki odpowiedzi (`Content-Type`,
`Content-Length`; GUGiK nie wysyla `ETag` ani `Last-Modified`) i prawdziwe
nazwy czlonow ZIP (podzbior):

- archiwum BDOT10k 2024 SHP i GML powiatu 1261 (nazwy czlonow SHP z probki
  2026-10-13, GML z planu C); `2024/GPKG/...` = 404;
- modele 3D LoD1 2024 i LoD2 2017 powiatu 1261 (LoD2: katalog `Modele_3D/`);
- PRG: paczka wojewodztwa 12 (5 plikow GML) i plik krajowy (poczatek ZIP -
  pierwsze czlony SHP z naglowkow lokalnych; caly plik nie byl pobierany);
- eksport EGiB powiatu 1261 (jeden `1261.gpkg`);
- brak paczki LoD2 powiatu 3262 (Szczecin): HTTP 404, `text/html`, tresc
  odpowiedzi 1:1.

Testy skladaja z tych nazw male ZIP-y (tresc czlonow sztuczna) - bajty
duzych paczek nie trafiaja do repozytorium. Surowe odpowiedzi: `<katalog-danych>`.
