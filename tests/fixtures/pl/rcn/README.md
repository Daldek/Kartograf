# Prawdziwy eksport RCN - rejestr cen nieruchomosci (plan E, E3; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; pelny
plik w `<katalog-danych>`). Adres:
`https://opendata.geoportal.gov.pl/InneDane/latest_exports/rcn_transakcje_ceny/GPKG/<TERYT>_transakcje_ceny.gpkg.zip`
(powiat: 4 cyfry, wojewodztwo: 2 cyfry).

`1201_transakcje_ceny.gpkg.zip`: prawdziwy eksport powiatu 1201 przyciety do
trzech obiektow kazdej warstwy, z tym samym schematem i nazwa czlonu,
spakowany jak zrodlo (jeden czlon
`1201_transakcje_ceny.gpkg`). Warstwy `gpkg_contents`: `transakcje_dzialki`,
`transakcje_budynki`, `transakcje_lokale` (EPSG:2180; pola m.in. `gid`,
`serwis_rcn`, `teryt`, `tran_lokalny_id_iip`). Pelny plik 2026-10-16:
ZIP 10 406 723 B, GPKG 30 060 544 B (dzialki 30 750, budynki 11 157,
lokale 3 914 obiektow).

`files.json`: naglowki `HEAD` (`application/octet-stream`, bez `ETag`
i `Last-Modified`) eksportow `1201` (10 406 723 B, lista czlonow), `1261`
(301 623 607 B) i wojewodztwa `12` (604 038 367 B). Plik `latest_exports`
jest podmieniany co dobe (1261: 236 404 584 B 2026-10-15), wiec zrodlo nie ma
taniego sygnalu aktualnosci.

Testy: `tests/test_rcn.py`, `tests/test_parity_e3.py`,
`tests/test_project_e3.py`.
