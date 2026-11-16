# Pliki krajowe CUZK (RUIAN, HY-NET) - naglowki i czlony ZIP (2026-10-16)

`packages.json`: dla kazdego pliku krajowego URL, naglowki odpowiedzi `HEAD`
(`Content-Length`, `Content-Type`, `ETag`, `Last-Modified`, `Accept-Ranges`)
i nazwy czlonow ZIP w kolejnosci katalogu centralnego. Nagrane 2026-10-16
przez `requests` z `User-Agent: kartograf/...`: `HEAD`, potem `GET` z
`Range: bytes=-262144` (koniec pliku z katalogiem centralnym) - bez
pobierania calego pliku.

| Wpis | URL | Rozmiar | Czlony |
|---|---|---|---|
| `ruian_country` | `https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip` | 253 018 058 B | 61 (katalog `1/` z SHP: `VUSC_P`, ..., `ZSJ_P`) |
| `hynet_country` | `https://openzu.cuzk.gov.cz/opendata/HY-NET/HY-NET.zip` | 194 208 037 B | `HY-NET/`, `HY-NET/HY-NET.gpkg` |

Testy buduja male ZIP-y z tymi nazwami czlonow (`tests/fake_packages.py::zip_bytes`);
`HEAD` podaje prawdziwy rozmiar (komunikat `WHOLE_COUNTRY_SIZE`).
Testy: `tests/test_collections_cz.py`.
