# Odpowiedzi CUZK dla jednostek planu E (2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo, kopia
surowa w `<katalog-danych>`): indeks `KladyMapovychListu` (warstwy 2 i 14)
i warstwa RUIAN `KatastralniUzemi` (7). Host `ags.cuzk.gov.cz/arcgis`.
Odpowiedzi `/query` bez edycji (`response.content`); metadane warstw
(`*_meta.json`) przyciete do `currentVersion`, `id`, `name`, `type`,
`geometryType`, `sourceSpatialReference`, `spatialReference`, `fields`
(tylko `name` i `type`), `maxRecordCount` i
`advancedQueryCapabilities.supportsPagination`.

`<plik>.headers.json`: `url` (pelne zapytanie), `status`, `Content-Type`
i `ETag` (format `tests/conftest.py::recorded_response`). Zadna odpowiedz
nie ma `Last-Modified`. Testy (`tests/test_cuzk_units.py`) odpowiadaja tylko
na zapytanie identyczne z `url` nagrania (adres i wszystkie parametry).

## Parametry zapytan

Jak `providers/cuzk/client.py::CuzkClient.query`: `f=json`, `outFields`,
`returnGeometry`, `resultOffset`, `resultRecordCount` (2000, w stronicowaniu
2), dla obwiedni `geometry=<minx,miny,maxx,maxy>`,
`geometryType=esriGeometryEnvelope`, `inSR`,
`spatialRel=esriSpatialRelIntersects`; `outSR` = `inSR` dla indeksu arkuszy.

## `KladyMapovychListu`

| Plik | Zapytanie | Wynik |
|---|---|---|
| `klady_2_meta.json` | `/2?f=json` | "Klad listu ZTM 10/S-JTSK", `sourceSpatialReference` 102067 (`latestWkid` 5514), `maxRecordCount` 2000 |
| `klady_14_meta.json` | `/14?f=json` | "Klad listu ZTM 10/ETRS89", `sourceSpatialReference` 3045, `spatialReference` (mapy) 5514 |
| `klady_2_bbox_tesin.json` | `/2/query`, obwiednia `-452000,-1112000,-449000,-1110000` (EPSG:5514), `outFields=MAPNOM,MAPNAME` | 4 arkusze 5 x 4 km: `0510-C-15`, `0510-D-11` (przeciecie wnetrzem) i `0510-C-20`, `0510-D-16` (styk krawedzia `y=-1112000` - nadmiarowy wynik uslugi) |
| `klady_2_bbox_tesin_page0.json` | jak wyzej, `resultRecordCount=2`, `resultOffset=0` | `0510-D-11`, `0510-D-16`, `exceededTransferLimit: true` |
| `klady_2_bbox_tesin_page2.json` | jak wyzej, `resultOffset=2` | `0510-C-15`, `0510-C-20`, bez `exceededTransferLimit` |
| `klady_2_bbox_outside.json` | `/2/query`, obwiednia `-400000,-1100000,-399000,-1099000` (Polska) | `features: []` |
| `klady_2_where_0510-D-11.json` | `/2/query`, `where=MAPNOM='0510-D-11'`, `outSR=5514` | `0510-D-11` ("Cesky Tesin 0510-D-11") |
| `klady_2_where_unknown.json` | `/2/query`, `where=MAPNOM='0000-Z-99'` | `features: []` |
| `klady_14_bbox_tesin.json` | `/14/query`, obwiednia `763000,5517000,766000,5520000` (EPSG:3045), `outFields=MAPNOM,MAPNAME` | `NM-34-07-1-D-15` i `NM-34-07-1-D-10` ("Havirov ...") |

Fakty: geometrie warstwy 2 to prostokaty (9 wierzcholkow, wspolrzedne
calkowite); warstwa 14 w EPSG:3045 to czworoboki o 13 wierzcholkach
(arkusze ok. 5 x 4 km, obwiednie sasiednich arkuszy nachodza na siebie
o ok. 230 m). Warstwe 14 trzeba pytac z `outSR=3045` - bez `outSR`
geometria wraca w ukladzie mapy (102067/5514; sprawdzone tego dnia). Na
wschod od `x=764200` (EPSG:3045) nie ma arkuszy (Polska). Kazda odpowiedz
`/query` w 0,08-0,15 s.

## RUIAN `KatastralniUzemi` (`RUIAN/MapServer/7`)

| Plik | Zapytanie | Wynik |
|---|---|---|
| `ruian_7_meta.json` | `/7?f=json` | pola `kod` (`esriFieldTypeInteger`) i `nazev`, `sourceSpatialReference` 5514, `maxRecordCount` 1000000 |
| `ruian_7_bbox_tesin.json` | `/7/query`, obwiednia `-452000,-1112000,-450000,-1110500` (`inSR=5514`), `outFields=kod,nazev`, `returnGeometry=false`, bez `outSR` | 3 KU w kolejnosci uslugi: 696137 "Mosty u Ceskeho Tesina", 753521 "Stanislavice", 652954 "Chotebuz" |
| `ruian_7_bbox_outside.json` | jak wyzej, obwiednia `-400000,-1100000,-399000,-1099000` (Polska) | `features: []` |

Fakty: `kod` przychodzi jako liczba calkowita (6 cyfr), nie tekst; kolejnosc
obiektow nie jest posortowana. Obwiednia `-452000,-1112000,-449000,-1110000`
daje 6 KU (dodatkowo 600121, 652962, 652971). Odpowiedz w 0,12-0,13 s,
metadane warstwy 0,31 s.
