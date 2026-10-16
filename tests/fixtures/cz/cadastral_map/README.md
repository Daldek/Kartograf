# Prawdziwe odpowiedzi CUZK - mapa katastralna (plan E, E3; 2026-10-16)

Nagrane 2026-10-16 przez `requests` i `curl -I` (jednorazowy skrypt poza
repo; pelne paczki w `<katalog-danych>`). Jedna paczka ZIP na katastralni
uzemi (KU, kod 6 cyfr) w kazdym z czterech formatow:

| Format | Adres |
|---|---|
| SHP | `https://services.cuzk.gov.cz/shp/ku/epsg-5514/<KU>.zip` |
| DXF | `https://services.cuzk.gov.cz/dxf/ku/<KU>.zip` |
| DGN | `https://services.cuzk.gov.cz/dgn/ku/<KU>.zip` |
| VFK | `https://services.cuzk.gov.cz/vfk/stavy/aktualni/<KU>.zip` |

`files.json`: naglowki `HEAD` paczek KU 623164 (`Content-Length`,
`application/zip`, `ETag`, `Last-Modified`) i lista czlonow ZIP:

- SHP (4 537 652 B): katalog `623164/` i 105 plikow warstw (np.
  `PARCELY_KN_P`, `BUDOVY_P`, `BODOVE_POLE_B`; `.shp`, `.shx`, `.dbf`,
  `.prj`, `.cpg`);
- DXF (1 919 638 B): `623164.dxf`;
- DGN (6 465 014 B): `623164.dgn`;
- VFK (7 940 312 B): `623164.vfk`.

Kazdy format ma wlasny `ETag` i `Last-Modified` (rozne daty publikacji).
KU obszaru testy biora z warstwy RUIAN `KatastralniUzemi` i naglowkow
`HEAD` jej trzech paczek SHP nagranych w E0
(`tests/fixtures/cuzk/real_2026_10_16/ruian_7_bbox_tesin.json`,
`tests/fixtures/pl/e0/real_2026_10_16/files.json`). Nieistniejacy KU
(`999999`) odpowiada 404 (test na zywo 2026-10-16).

Testy: `tests/test_cz_cadastral_map.py`, `tests/test_parity_e3.py`,
`tests/test_project_e3.py`.
