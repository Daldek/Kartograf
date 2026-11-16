# Prawdziwe odpowiedzi true orto GUGiK (plan E, E1; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo). Cialo
odpowiedzi bez edycji; obok `<plik>.headers.json` z kodem HTTP
i `Content-Type`.

## Skorowidz arkuszy (WMS)

Usluga `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/TrueOrtho`,
warstwa `Skorowidze` (druga warstwa `PrawdziwaOrtofotomapa` to obraz).
`GetFeatureInfo` jak w `SkorowidzLayersMixin._query_bbox` (BBOX 20 x 20 m,
osie N,E, EPSG:2180).

| Plik | Punkt | Wynik |
|---|---|---|
| `gfi_true_N-34-50-A-c-3-2-<1..4>.html` | srodki czterech cwiartek arkusza `N-34-50-A-c-3-2` (Gdansk) | po jednym rekordzie `N-34-50-A-c-3-2-<n>` 2020-05-21 (zgloszenie DFT.7201.031.2020, kampania 73912), PL-1992, modul 1:2500, `wielkoscPiksela` 0.05, bez `dt_pzgik` i bez `calyArkuszWypelnionyTrescia`; numeracja cwiartek jak na wyzszych poziomach: 1 NW, 2 NE, 3 SW, 4 SE |
| `gfi_true_krakow.html` | srodek `M-34-64-D-d-1-4` (Krakow) | sam szablon, bez rekordow (true orto obejmuje wybrane miasta) |

`files.json`: `HEAD` pliku `N-34-50-A-c-3-2-3` - 296 853 152 B,
`application/octet-stream`, bez `ETag`.

## Wycinek (WCS)

Usluga `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WCS/TrueOrto`,
coverage `True_Orthoimagery`.

| Plik | Zapytanie | Wynik |
|---|---|---|
| `describe_true.xml` | `DescribeCoverage` 2.0.1 | siatka krajowa EPSG:2180, `offsetVector` 0,05 m, `origin` 796521.644410 160828.368266 (y x), pasma R, G, B |
| `true_0.05m_20x20.tif` | `GetCoverage` 2.0.1, `FORMAT=image/tiff`, `SUBSET=x(470177.00,470178.00)&SUBSET=y(740336.00,740337.00)` (Gdansk) | GeoTIFF 20 x 20 px, piksel 0,05 m, 3 pasma uint8, EPSG:2180, bez nodata; naroznik = zasieg zapytania |
| `true_0.1m_10x10.tif` | jw. z `SCALEFACTOR=0.5` | 10 x 10 px, piksel 0,1 m |
| `true_0.05m_krakow.tif` | `SUBSET=x(566000.00,566001.00)&SUBSET=y(243000.00,243001.00)` (Krakow) | 20 x 20 px, wszystkie piksele 0,0,0 (poza miastami true orto) |

Testy: `tests/test_imagery_products.py`.
