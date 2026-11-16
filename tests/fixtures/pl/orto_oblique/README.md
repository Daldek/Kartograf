# Prawdziwe odpowiedzi skorowidza ortofotomapy ukosnej GUGiK (plan E, E1; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo). Cialo
odpowiedzi bez edycji; obok `<plik>.headers.json` z kodem HTTP
i `Content-Type`.

Usluga `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/SkorowidzeOrtofotomapyUkosnej`,
cztery warstwy - jedna na kierunek: `SkorowidzeOrtofotomapyUkosnej-Polnoc`,
`-Wschod`, `-Poludnie`, `-Zachod`. `GetFeatureInfo` jak w
`SkorowidzLayersMixin._query_bbox` (BBOX 20 x 20 m, osie N,E, EPSG:2180).

| Plik | Warstwa, punkt | Wynik |
|---|---|---|
| `gfi_oblique_<n,e,s,w>_7.125.11.08.html` | warstwa kierunku, srodek `7.125.11.08` (Krakow) | po jednym rekordzie: `godlo` 7.125.11.08, `kierunek` N/E/S/W, 2021-10-03, kampania 78945, `charakterystykaPrzestrzenna` 0.05, PL-2000:S7, modul 1:2000, `calyArkuszWypelnionyTrescia` TAK, `kolor` RGB, `dt_pzgik` 2024-02-09; URL `..._7.125.11.08_<N,E,S,W>.tif` |
| `gfi_oblique_n_gdansk.html` | Polnoc, srodek `N-34-50-A-c-3-2` (Gdansk) | rekord `6.224.25.03.1` (modul 1:1000, PL-2000:S6, 2024-05-14) - arkusze ukosne maja rozne skale PL-2000 |
| `gfi_oblique_n_outside.html` | Polnoc, `738960,626588` (Biebrza) | sam szablon, bez rekordow |

`files.json`: `HEAD` czterech plikow arkusza `7.125.11.08` (N 301 669 662 B,
E 274 260 638 B, S 273 570 294 B, W 271 280 590 B; `application/octet-stream`,
bez `ETag`).

Testy: `tests/test_imagery_products.py`.
