# Prawdziwe odpowiedzi uslug ATOM CUZK dla silnika `atom_files` (2026-10-15)

Nagrane 2026-10-15 (`curl`, jawny limit czasu; surowe odpowiedzi i pelny
feed ORTOFOTO w `<katalog-danych>`). Obok kazdej odpowiedzi
`<plik>.headers.json`: kod HTTP, `Content-Type` oraz - gdy serwer je podal -
`ETag` i `Last-Modified` (konwencja `tests/conftest.py::recorded_response`).
Pliki maja konce linii serwera (CRLF w feedach ORTOFOTO) i BOM UTF-8 na
poczatku feedow - bez zmian.

| Plik | Zapytanie | Uwagi |
|---|---|---|
| `ortofoto_service.xml` | `GET https://atom.cuzk.gov.cz/ORTOFOTO/ORTOFOTO.xml` | **przyciety**: naglowek feedu bajt w bajt, z 16 301 wpisow zostaly 3 (`WRTO24.2025.BENE09`, `WRTO24.2025.AS91`, `WRTO24.2024.CTES96`, w kolejnosci feedu); caly feed 23 707 340 B, `ETag` `"64a6104edbc8dc1:0"` |
| `ortofoto_ctes96.xml` | `GET .../ORTOFOTO/datasetFeeds/CZ-00025712-CUZK_ORTOFOTO_WRTO24.2024.CTES96.xml` | link `https://openzu.cuzk.cz/opendata/ORTOFOTO/WRTO24.2024.CTES96.zip` (stara domena `cuzk.cz`), `length` 63 870 664, `updated` 2025-02-06T14:00:09+02:00 |
| `ortofoto_as91.xml` | `GET .../datasetFeeds/CZ-00025712-CUZK_ORTOFOTO_WRTO24.2025.AS91.xml` | arkusz As (2 litery), `length` 55 308 158, `updated` 2026-02-24T09:03:19+02:00 |
| `zabaged_service.xml` | `GET https://atom.cuzk.gov.cz/ZABAGED-GPKG/ZABAGED-GPKG.xml` | jeden zbior, kategorie ukladow EPSG:3045 i EPSG:5514 |
| `zabaged_dataset.xml` | `GET .../ZABAGED-GPKG/datasetFeeds/CZ-00025712-CUZK_ZABAGED-GPKG_1.xml` | dwa pliki: `epsg-5514/ZABAGED-5514-gpkg-20261004.zip` (5 805 826 649 B) i `epsg-3045/ZABAGED-3045-gpkg-20261004.zip` (6 742 892 709 B) |
| `atom_root.html` | `GET https://atom.cuzk.gov.cz/` | **HTTP 200**, `text/html` (strona uslug ATOM) - odpowiedz, ktora nie jest feedem |
| `missing_feed.html` | `GET .../datasetFeeds/CZ-00025712-CUZK_ORTOFOTO_WRTO24.2025.CTES96.xml` (nie istnieje) | **HTTP 404**, `text/html` |

## Fakty z nagrania (2026-10-15)

- Feed ORTOFOTO: 16 301 wpisow = 16 301 roznych arkuszy (jeden aktualny
  plik na arkusz), lata 2025 (8593) i 2024 (7708), 99 arkuszy As
  (`AS22` ... `AS94`); kazdy wpis ma jedna kategorie EPSG:5514. Id wpisu
  = link `rel="alternate"` feedu zbioru; `updated` wpisu uslugi =
  `updated` wpisu pliku w feedzie zbioru.
- Warunkowy GET feedu ORTOFOTO z `If-None-Match: "64a6104edbc8dc1:0"`
  daje **HTTP 304** bez tresci.
- ZIP arkusza (centralny katalog, `Range`): czlony
  `WRTO24.2024.CTES96.jpg` (deflate, 63 868 659 B po rozpakowaniu),
  `.jgw`, `.TM33N.jgw`, `.TM34N.jgw`; `ETag` i `Last-Modified` pliku na
  `openzu.cuzk.cz` obecne.

Testy: `tests/test_atom.py`.
