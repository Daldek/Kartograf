# Bodove pole CUZK - prawdziwe odpowiedzi (plan E, E5; 2026-10-16)

Nagrane 2026-10-16 zapytaniami silnika `feature_bbox` (ArcGIS REST,
`page_size` 1000; jednorazowy skrypt poza repo). Usluga
`https://ags.cuzk.gov.cz/arcgis/rest/services/BodovaPole/MapServer`
(11.5, EPSG:5514, `maxRecordCount` 2000). Obwiednia
`-452000,-1113000,-449000,-1110000` (EPSG:5514, Cesky Tesin).

| Plik | Zawartosc |
|---|---|
| `service.json` | `?f=json` przyciete do `currentVersion`, `spatialReference`, `maxRecordCount` i listy warstw (`id`, `name`, `parentLayerId`, `subLayerIds`, `type`, `geometryType`) |
| `layer_<id>.json` | `/<id>?f=json` warstw 2, 4, 6, 8, 18, 20, 44 (bez edycji) |
| `layer_<id>_tesin_count.json` | `returnCountOnly`: 44 - 10, 18 - 1, 20 - 1, 2 - 1, 4/6/8 - 0 |
| `layer_<id>_tesin_r1000_o0.json` | strona GeoJSON (`orderByFields=OBJECTID`) warstw 44, 18, 20, 2 |

Warstwy danych (nieparzyste = etykiety "Cisla ...", pomijane; "Zruseny"
10-17 i 30-37 = punkty zniesione, pomijane): 0 CZEPOS; ZPBP 18 i 20 oraz
2, 4, 6, 8 (wyznaczone w ETRS89 / RTK); ZhB 38 i 40 oraz 22, 24, 26, 28;
PPBP 42; ZVBP 44; PVBP 46; ZTBP 48. Sprawdzenie 2026-10-16 na calym kraju
(wspolrzedne Y,X i pary ZTLTL+CISLO): warstwy 2-9 i 22-29 NIE sa
podzbiorami 18/20 i 38/40 (zero wspolnych punktow; np. ZhB w ETRS89 30 689
punktow, ZhB 9460) - siec to suma warstw. Pole `ID` jest numeracja warstwy
(nie identyfikuje punktu miedzy warstwami); identyfikator obiektu: `OBJECTID`.
