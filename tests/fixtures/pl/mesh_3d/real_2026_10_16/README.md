# Mesh 3D GUGiK - prawdziwe odpowiedzi (plan E, E5; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi i pobrany kafel w `<katalog-danych>`). Indeks: WFS
`https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WFS/ModeleSiatkowe3D`,
typ `gugik:SkorowidzModeleSiatkowe3D` (strony dla obszaru 4 kafli sa
w `tests/fixtures/pl/index_records/mesh_p1.xml`, `mesh_p2.xml`).

| Plik | Zawartosc |
|---|---|
| `wfs_122_p0.xml.gz` (+ `.headers.json` bez `.gz`) | jedna strona `GetFeature` (`COUNT=1000`, zapytanie jak `WfsIndex`) dla `BBOX=244000,566000,246000,568000` (N,E, Krakow): 122 rekordy kafli; cialo bez edycji, spakowane gzip |
| `files.json` | `tile_<modul>`: URL i naglowki `HEAD` czterech kafli z `mesh_p1/p2` (40-57 MB), dla `78944_6777_74230_55482.zip` takze lista czlonow ZIP (4 JPG, MTL, OBJ, bez katalogu); `area_122`: `Content-Length` z `HEAD` kazdego ze 122 kafli strony (razem 5 683 846 402 B) |

Fakty z calego indeksu (132 745 rekordow, `PROPERTYNAME` + obwiednie,
2026-10-16): `modul` nie jest identyfikatorem kafla - 26 633 wartosci
(`Tile-x-y-1-1`) nazywa kafle w kilku miejscach (rozne prace i miasta,
takze w jednym katalogu URL); 138 miejsc ma dwa rekordy jednego roku
(mesh ze zdjec 0,05 m i ze skaningu 0,10 m jednej pracy); zadne miejsce
nie ma rekordow kilku lat. Unikalna jest nazwa pliku URL
(`<katalog>_<id>_<modul>.zip`). Wszystkie rekordy: `uklad_h`
PL-EVRF2007-NH; `uklad_xy` PL-1992, PL-2000:S5, S6, S7. Plik kafla Krakowa:
OBJ we wspolrzednych PL-2000:S7 (E z prefiksem strefy 7) i wysokosciach.
