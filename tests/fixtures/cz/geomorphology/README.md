# Prawdziwe odpowiedzi CUZK - jednostki geomorfologiczne (plan E, E3; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi w `<katalog-danych>`). Usluga ArcGIS REST
`https://ags.cuzk.gov.cz/arcgis/rest/services/GeomorfologickeJednotky/MapServer`
(wersja 11.5). `<plik>.headers.json`: `url` (pelne zapytanie), `status`,
`Content-Type` i `ETag` (konwencja `tests/conftest.py::recorded_response`).

| Plik | Zapytanie | Wynik |
|---|---|---|
| `service.json` | `?f=json`, przyciete do `currentVersion`, `spatialReference` i listy warstw (`id`, `name`, `type`, `geometryType`, `parentLayerId`) | 33 warstwy: 0-21 adnotacje (`Annotation Layer` i podwarstwy `Default`), 22-25 mozaika cieniowanego reliefu, 33-39 poligony jednostek `GJ_01_subprovincie`...`GJ_07_casti` (39 = `GJ_03_celek`) |
| `layer_39.json` | `/39?f=json`, przyciete do `id`, `name`, `type`, `geometryType`, `sourceSpatialReference`, `extent`, `fields` (`name`, `type`), `maxRecordCount` i `advancedQueryCapabilities` (stronicowanie, `orderBy`) | poligony, uklad 102067 (`latestWkid` 5514), `maxRecordCount` 2000, pola `OBJECTID`, `CELEK_K`, `CELEK_P`, ... |
| `layer_39_tesin_count.json` | `/39/query`, obwiednia `-452000,-1112000,-450000,-1110000` (`inSR=5514`), `returnCountOnly=true` | `{"count":1}` |
| `layer_39_tesin_r1000_o0.json.gz` | jw., `outSR=5514`, `outFields=*`, `orderByFields=OBJECTID`, `resultOffset=0`, `resultRecordCount=1000`, `f=geojson` (cialo bez edycji, spakowane gzip) | jeden celek `Podbeskydská pahorkatina` z pelna geometria |

Poziom `--level` = warstwa: `subprovincie` 33, `oblast` 34, `celek` 39,
`podcelek` 35, `okrsek` 36, `podokrsek` 37, `cast` 38 (kolejnosc od
najwiekszych jednostek). Adnotacje i mozaika nie sa danymi produktu.

Testy: `tests/test_cz_geomorphology.py`, `tests/test_parity_e3.py`.
