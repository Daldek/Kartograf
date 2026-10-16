# Prawdziwe odpowiedzi Data50 i Data250 CUZK (plan E, E4) - nagranie 2026-10-16

Nagrane 2026-10-16 przez `requests` (`User-Agent: kartograf/0.8.0`; surowe
odpowiedzi w `<katalog-danych>`). Obok kazdej odpowiedzi
`<plik>.headers.json` (kod HTTP, `Content-Type`, `ETag`/`Last-Modified`, gdy
serwer je podal; konwencja `tests/conftest.py::recorded_response`). Strony
GeoJSON zapisane jako `*.json.gz` (cala odpowiedz, gzip `mtime=0`). Bez edycji;
feedy ATOM z BOM UTF-8 (Data50: feed zbioru) - bez zmian.

Obszar zapytan (EPSG:5514, X,Y): `TESIN = -450998.718,-1112011.026,-450531.472,-1111532.273`
= obwiednia EPSG:5514 obszaru `18.566,49.757,18.572,49.761` (EPSG:4326,
Cesky Tesin) liczona przez Kartograf (`country_bbox` + operacja przypieta,
zaokraglenie na zewnatrz do mm).

| Plik | Zapytanie | Wynik |
|---|---|---|
| `data50_pjson.json`, `data250_pjson.json` | `ags.cuzk.gov.cz/arcgis/rest/services/DATA50/MapServer?f=pjson` (`DATA250`) | Data50: 69 warstw obiektowych (0-68); Data250: 118 warstw, w tym 116 obiektowych i 2 rastrowe (5, 6: relief); `maxRecordCount` 2000, EPSG:5514 (`latestWkid`) |
| `data50_l{62,63,66,67}_info.json`, `data250_l{99,108,117}_info.json` | `/<id>?f=json` | pola `OBJECTID`, `Shape`, atrybuty warstwy, `DATA50_K`/`DATA50_P` |
| `*_l<id>_tesin_count.json` | `/<id>/query?geometry=TESIN&geometryType=esriGeometryEnvelope&inSR=5514&spatialRel=esriSpatialRelIntersects&returnCountOnly=true&f=json` | Data50: 62 `Vodni plocha` 0, 63 `Vodni tok` 1, 66 `Louka, pastvina` 2, 67 `Les` 2; Data250: 99 `Vodni tok povrchovy staly do 5 m` 1, 108 `Vodni plocha` 0, 117 `Les` 2 |
| `*_l<id>_tesin_r1_o<o>.json.gz` | jw. + `outSR=5514&outFields=*&orderByFields=OBJECTID&resultOffset=<o>&resultRecordCount=1&returnGeometry=true&f=geojson` | jeden obiekt na strone; pierwsze strony warstw 66 i 67 (Data50) oraz 117 (Data250) maja `exceededTransferLimit: true` |
| `data50_service.xml`, `data250_service.xml` | `atom.cuzk.gov.cz/Data50/Data50.xml` (`Data250`) | jeden zbior `CUZK_Data50_1` (`CUZK_Data250_1`), kategorie EPSG:5514 i EPSG:3045 |
| `data50_dataset.xml`, `data250_dataset.xml` | `.../datasetFeeds/CZ-00025712-CUZK_Data50_1.xml` (`Data250`) | dwa pliki SHP ZIP: `openzu/Data50/epsg-5514/data50.zip` (`length` 515 542 917, `updated` 2026-04-28T10:09:14+02:00) i `epsg-3045/data50.zip` (756 987 213); Data250: 230 485 722 (2026-05-12T10:16:28+02:00) i 320 374 437 |
| `national.json` | `HEAD` `openzu.cuzk.gov.cz/opendata/<Data50/Data250>/epsg-5514/<data50/data250>.zip` i katalog centralny pliku pobranego przez Kartograf (E2E 2026-10-16) | `url`, naglowki `HEAD` (`Content-Type`, `Content-Length`, `Last-Modified`, `ETag`) i pelna lista czlonow ZIP w kolejnosci katalogu: Data50 557 (`!readme.txt`, katalog SHP, projekty ArcGIS, `shp/`), Data250 448 (`DATA250_2026_SHP/`, w tym rastry reliefu `.tif`) |

## Fakty z nagrania (2026-10-16)

- `HEAD` plikow krajowych: `Content-Length` rowne `length` feedu,
  `Content-Type: application/x-zip-compressed`, `ETag` i `Last-Modified`
  (Data50 5514: 2026-04-28 08:09:14 GMT = `updated` wpisu feedu).
- Warstwy obszaru: wszystkie warstwy obiektowe uslugi (69 / 116), nazwy
  warstw GPKG = nazwa CUZK bez znakow diakrytycznych, malymi literami,
  ciagi spoza `[a-z0-9]` jako `_` (konwencja ZABAGED); bez przeliczania klas
  na kody BDOT10k. Warstwy rastrowe Data250 (relief) nie sa danymi obszaru.
- Strony z `resultRecordCount=2000` maja `exceededTransferLimit`, gdy
  warstwa ma wiecej obiektow niz strona; silnik liczy strony z
  `returnCountOnly`, nie z tej flagi.
- Plik krajowy SHP ma wlasne nazwy warstw (Data50: nazwy CUZK, np.
  `shp/Akvadukt.shp`; Data250: kody angielskie, np. `AirfldA.shp`), inne niz
  warstwy uslugi REST; Kartograf zapisuje go 1:1.

Testy: `tests/test_cz_data50_250.py`, `tests/test_parity_e4.py`.
