# Prawdziwe odpowiedzi skorowidza obrazow intensywnosci GUGiK (plan E, E1; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo). Cialo
odpowiedzi bez edycji (po dekompresji gzip transportu); obok
`<plik>.headers.json` z kodem HTTP i `Content-Type`.

Usluga `https://mapy.geoportal.gov.pl/wss/service/PZGIK/OI/WMS/SkorowidzeObrazowIntensywnosci`,
warstwa `SkorowidzeOI` (druga warstwa uslugi, `SkorowidzeOIZasieg`, to zasieg
bez rekordow). `GetFeatureInfo` 1.3.0, `INFO_FORMAT=text/html`,
`CRS=EPSG:2180`, `WIDTH=HEIGHT=100`, `I=J=50`, `BBOX` 20 x 20 m (osie N,E)
wokol srodka arkusza - zapytanie `SkorowidzLayersMixin._query_bbox`.

| Plik | Punkt | Wynik |
|---|---|---|
| `gfi_oi_M-34-64-D-d-1-4.html` | srodek `M-34-64-D-d-1-4` (Krakow) | 3 rekordy `skor.push`: `M-34-64-D-d-1-4` 2023-09-08 (78993) i 2025-04-28 (83138), PL-1992, modul 1:5000; `7.125.11.17` 2023-03-17 (77913), PL-2000:S7, modul 1:2000; `wielkoscPiksela` 0.25, bez `calyArkuszWypelnionyTrescia` |
| `gfi_oi_outside.html` | `800000,400000,800020,400020` (poza Polska) | sam szablon (`function createTable`), bez rekordow |

`files.json`: naglowki `HEAD` trzech plikow (2025: 84 985 518 B, 2023:
85 089 428 B, PL-2000: 25 624 682 B; `application/octet-stream`, bez `ETag`).
Plik 2025 pobrany w calosci 2026-10-13 (raport katalogu, `probki.md`):
GeoTIFF 1 pasmo Byte, piksel 0,25 m, EPSG:2180.

Testy: `tests/test_imagery_products.py`.
