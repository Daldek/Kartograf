# Ortofoto CUZK dla toru `cz_orto` (2026-10-16)

Nagrane 2026-10-16 (`requests`, jawny limit czasu; surowe odpowiedzi
i pelny feed ORTOFOTO w `<katalog-danych>`). Obok odpowiedzi HTTP
`<plik>.headers.json`: kod HTTP, `Content-Type` oraz `ETag`
i `Last-Modified` (konwencja `tests/conftest.py::recorded_response`).
Feedy maja konce linii serwera (CRLF) i BOM UTF-8 - bez zmian. Feedy
zbiorow CTES96 i AS91 oraz strona 404 brakujacego feedu: `../atom/`
(README tam); rekord indeksu CTES96: `../../cuzk/klady_sm5_where_ctes96.json`.

| Plik | Zapytanie | Uwagi |
|---|---|---|
| `ortofoto_service.xml` | `GET https://atom.cuzk.gov.cz/ORTOFOTO/ORTOFOTO.xml` | **przyciety**: naglowek feedu bajt w bajt, z 16 301 wpisow zostaly 3 (`WRTO24.2025.AS91`, `WRTO24.2024.CTES86`, `WRTO24.2024.CTES96`, w kolejnosci feedu, bajt w bajt); caly feed 23 707 340 B, `ETag` `"64a6104edbc8dc1:0"` |
| `ortofoto_ctes86.xml` | `GET .../ORTOFOTO/datasetFeeds/CZ-00025712-CUZK_ORTOFOTO_WRTO24.2024.CTES86.xml` | link `https://openzu.cuzk.cz/opendata/ORTOFOTO/WRTO24.2024.CTES86.zip`, `length` 16 025 095, `updated` 2025-02-06T13:58:55+02:00 |
| `klady_sm5_bbox_ctes96_ctes86.json` | `GET https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/24/query` z `geometry=-448500.0,-1113500.0,-446500.0,-1112500.0`, `inSR=outSR=5514`, `spatialRel=esriSpatialRelIntersects`, `outFields=MAPNOM,MAPNAME,PODIL` | arkusze CTES86 (PODIL 0,19) i CTES96 (0,99) |
| `klady_sm5_where_ctes86.json`, `klady_sm5_where_as91.json` | to samo zapytanie z `where=MAPNOM='<godlo>'` (bez `geometry`) | MAPNAME `Český Těšín 8-6`, `Aš 9-1` |
| `WRTO24.2024.CTES96.zip`, `WRTO24.2024.CTES86.zip`, `WRTO24.2025.AS91.zip` | ZIP arkusza (opis nizej) | `.headers.json`: prawdziwe `ETag`, `Last-Modified`, `Content-Type` pliku z `openzu.cuzk.cz` |

## ZIP arkusza

Prawdziwy ZIP ma 16-64 MB (CTES96: 63 870 664 B, CTES86: 16 025 095 B,
AS91: 55 308 158 B) - nie trafia do repozytorium. Fixtura ma **prawdziwe
nazwy i kolejnosc czlonow** z katalogu centralnego oraz **prawdziwe pliki
JGW**, a zamiast zdjecia - JPEG 8 x 8 px zapisany przez `rasterio`
(sterownik JPEG, bez georeferencji, rozny dla kazdego arkusza). Czlony
skompresowane deflate jak w oryginale.

Nagranie bez pobierania calego pliku (zapytania `Range`):

1. `HEAD` pliku: `Content-Length`, `Accept-Ranges: bytes`.
2. `GET` z `Range: bytes=-65536`: rekord konca katalogu centralnego
   (`PK\x05\x06`) - rozmiar i przesuniecie katalogu centralnego; z niego
   nazwy, metody, CRC, rozmiary i przesuniecia naglowkow lokalnych czlonow.
3. Dla kazdego `.jgw`: `GET` z `Range` naglowka lokalnego (30 B + nazwa +
   pole dodatkowe) i danych; rozpakowanie (deflate), kontrola CRC32
   i rozmiaru z katalogu centralnego.

Czlony (kolejnosc katalogu centralnego): CTES96 i CTES86 - `.jpg`, `.jgw`,
`.TM33N.jgw`, `.TM34N.jgw`; AS91 - `.jgw`, `.jpg`, `.TM33N.jgw`,
`.TM34N.jgw`. JGW maja konce linii CRLF; `.jgw` (S-JTSK) piksel 0,125 m
bez obrotu, pliki TM bez zera wiodacego (`.124011`) i bez konca linii na
koncu.

**Uklad plikow TM (pomiar 2026-10-16):** srodek lewego gornego piksela
z `.jgw` (EPSG:5514) przeliczony przez `pyproj` do EPSG:3045 (ETRS89 / UTM
33N) i EPSG:3046 (ETRS89 / UTM 34N) zgadza sie z wyrazami C, F plikow
`.TM33N.jgw` i `.TM34N.jgw` z dokladnoscia do 0,03 m (CTES96, CTES86,
AS91; dla AS91 strefa 34 daje ujemne E) - stad `world_files` w sidecarze
JPEG: `.jgw` EPSG:5514, `.TM33N.jgw` EPSG:3045, `.TM34N.jgw` EPSG:3046.

W testach `length` feedu zbioru jest zamieniane na rozmiar fixtury ZIP
(silnik porownuje go z pobranym plikiem). Testy: `tests/test_cz_orto.py`.
