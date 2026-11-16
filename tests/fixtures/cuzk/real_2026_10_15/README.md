# Odpowiedzi CUZK dla planu B (2026-10-15)

Nagrane 2026-10-15 przez `requests` (jednorazowy skrypt poza repo, kopia
surowa w `<katalog-danych>`): pliki `openzu`, indeks `KladyMapovychListu`
i metadane uslug `ImageServer`. Tresc bez edycji (`response.content`).

## `openzu_head.json` - naglowki `HEAD`

`HEAD` (`allow_redirects=True`, jak `transport/http.py::head_signal`) adresow
`https://openzu.cuzk.gov.cz/opendata/<PRODUKT>/epsg-<5514|3045>/<arkusz>.zip`;
zachowane naglowki `ETag`, `Last-Modified`, `Content-Length`, `Content-Type`.

| Arkusz | Uklad | Produkty 200 | 404 |
|---|---|---|---|
| `CTES96` (SM5, "Cesky Tesin 9-6") | `epsg-5514` | `DMR5G`, `DMR4G`, `DMR4G-TIFF`, `DMP1G`, `DMPOK-TIFF`, `DMPOK-LAZ` | `DMR5G-TIFF`, `DMP1G-TIFF` |
| `CTES86` (SM5, `PODIL` 0,19) | `epsg-5514` | jak wyzej | jak wyzej |
| `760_5518` (TM33) | `epsg-3045` | jak wyzej | jak wyzej |
| `760_5516` (TM33) | `epsg-3045` | jak wyzej | jak wyzej |

Do tego dwa nieistniejace arkusze: `DMR4G-TIFF/epsg-5514/ZZZZ99.zip`
i `DMR4G-TIFF/epsg-3045/100_5000.zip`. Kazda odpowiedz 404 to `text/html`,
1245 B, bez `ETag` i `Last-Modified`. Kazda odpowiedz 200 ma `ETag`
i `Last-Modified` (sygnal `http`); `Content-Type: application/x-zip-compressed`.
Daty publikacji: DMR 5G/4G 2026-01-19/20, DMP 1G 2023-06-12, DMP OK SM5
2025-10-10, DMP OK TM33 2026-08-20.

## Pliki ZIP (`GET`)

| Plik | Adres | Zawartosc | sha256 ZIP |
|---|---|---|---|
| `openzu_DMR4G-TIFF_3045_760_5518.zip` | `DMR4G-TIFF/epsg-3045/760_5518.zip` | `760_5518.tif` (400x400 px, float32, nodata -9999, bez CRS) + `760_5518.tfw` | `cf1ac841fc31...` |
| `openzu_DMR4G_3045_760_5518.zip` | `DMR4G/epsg-3045/760_5518.zip` | `760_5518.laz` (14 190 B) | `5b84e0682bf1...` |
| `openzu_DMR4G_5514_CTES96.zip` | `DMR4G/epsg-5514/CTES96.zip` | `CTES96.laz` (181 220 B) | `37e0a67fdc08...` |

`<plik>.headers.json`: `url`, `status` i naglowki odpowiedzi `GET`
(`ETag`, `Last-Modified`, `Content-Length`, `Content-Type`; format zgodny
z `tests/conftest.py::recorded_response`). Wieksze pliki (DMP OK, DMR 5G,
DMP 1G) - tylko naglowki `HEAD`.

## Indeks `KladyMapovychListu` (`/query`, `f=json`)

Parametry jak `providers/cuzk/client.py::CuzkClient.query` (pierwsza strona,
`resultRecordCount=2000`), host `ags.cuzk.gov.cz/arcgis`:

| Plik | Zapytanie | Wynik |
|---|---|---|
| `klady_24_bbox_cieszyn.json` | warstwa 24, obwiednia `-447000,-1114000,-446000,-1113000` (EPSG:5514), `outFields=MAPNOM,MAPNAME,PODIL` | `CTES86` (`PODIL` 0,19) i `CTES87` (styk krawedzia - nadmiarowy wynik uslugi, odrzucany przez filtr klienta) |
| `klady_26_bbox_cieszyn.json` | warstwa 26, ta sama obwiednia w EPSG:3045 (`bbox_to_crs`: `760922.38..762043.52, 5516225.51..5517346.64`), `outFields=MAPNOM,IN_CZ` | `760_5516` (`IN_CZ` = `CZ`) |
| `klady_24_where_ctes86.json` | warstwa 24, `where=MAPNOM='CTES86'` | `CTES86` |

Obwiednia lezy na granicy: Cesky Tesin (CZ) i Cieszyn (PL, rynek
`-446326,-1113194`); ta sama obwiednia w EPSG:2180 (operacja przypieta
`bbox_to_2180`) = `472811.53,208336.31,473883.88,209408.66` - odpowiedzi
skorowidzy GUGiK dla czesci PL: `tests/fixtures/gugik_wfs/real_2026_10_15/
area_<usluga>_cieszyn.xml.gz`.

## Metadane `ImageServer` (`?f=json`)

`imageserver_<usluga>.json` dla `dmr5g` (piksel 2 m), `dmr4g` (5 m),
`dmp1g` (2 m) i `dmp_obrazova_korelace` (0,5 m); wszystkie `pixelType=F32`,
`maxImageWidth=15000`, `maxImageHeight=4100`, `vcsWkid=8357`, `latestWkid=5514`.

Testy: `tests/test_sources_registry.py`, `tests/test_cuzk_raster.py`,
`tests/test_cuzk_laz.py`, `tests/test_cz_laz.py`, `tests/test_availability.py`.
