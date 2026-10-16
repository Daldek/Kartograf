# Osnowy podstawowe GUGiK (PRPOG) - prawdziwe odpowiedzi (plan E, E5; 2026-10-16)

Nagrane 2026-10-16 przez `requests` zapytaniami silnika `feature_bbox`
(`COUNT=2`, `STARTINDEX` od 0; jednorazowy skrypt poza repo). Uslugi WFS
2.0.0 (MapServer, EPSG:2180, osie N,E, bez `CountDefault`):
`https://mapy.geoportal.gov.pl/wss/service/PZGIK/<usluga>/WFS` (adres bez
`/WFS` nie odpowiada). Obiekty nie maja `gml:id` - punkt identyfikuje
`nr_punktu` (unikalny w kazdej warstwie), strefe izogon
`zakres_wartosci_deklinacji` (9 obiektow w kraju). Siec grawimetryczna:
fixtury E0 `tests/fixtures/pl/e0/real_2026_10_16/grav_*`.

| Prefiks pliku | Usluga, warstwy | Obszar (N,E) | Obiekty |
|---|---|---|---|
| `horizontal_` | `PodstawowaOsnowaGeodezyjnaPozioma`: `ms:Fundamentalna_pozioma`, `ms:Bazowa_pozioma` | 240000-250000, 560000-575000 | 3 i 3 |
| `vertical_` | `PodstawowaOsnowaGeodezyjnaWysokosciowa`: `ms:Fundamentalna_wysokosciowa`, `ms:Bazowa_wysokosciowa` | 240600-241200, 567600-568300 | 1 i 3 |
| `magnetic_` | `OsnowaMagnetyczna`: `ms:Fundamentalna_magnetyczna`, `ms:Bazowa_magnetyczna`, `ms:izogony` (bez `ms:izogony_etykiety`) | 200000-300000, 500000-650000 | 2, 4 i 4 |

Na kazda usluge: `<siec>_capabilities.xml`, na warstwe `_describe.xsd`,
`_hits.xml` (`RESULTTYPE=hits`) i strony `_c2_s<STARTINDEX>.xml`; obok
kazdej `.headers.json` (`url`, `status`, `Content-Type`). Odpowiedzi bez
edycji z jednym wyjatkiem: w `magnetic_izogony_c2_s0.xml`
i `magnetic_izogony_c2_s2.xml` geometria kazdej strefy (MultiSurface do
28 025 wierzcholkow w pierscieniu, strony 1,1 MB i 272 KB) jest przycieta do
trojkata z trzech pierwszych wierzcholkow pierwszego pierscienia; atrybuty,
liczniki i reszta dokumentu bez zmian.

`files.json`: URL, naglowki `HEAD` i listy czlonow paczek powiatu 1201
(`bdpog/Pozioma/1201_PodstawowaOsnowaPozioma.zip`, 2 883 814 B: opisy
topograficzne JPG i 8 wykazow XLS; `bdpog/Wysokosciowa/...`, 14 190 226 B:
81 JPG i 3 XLS) oraz archiwow arkusza 1:100000
`bdpog/MaterialyArchiwalne/Katalogi_<Kartoteki1942|Kronsztadt60>/<godlo>.zip`:
Kronsztadt60 M-34-64 (26 007 952 B: PDF i TIFF), Kartoteki1942 M-34-64
(1 069 061 020 B, bez listy czlonow) i N-33-58 (2 764 933 B: karty PDF
w katalogu `kartoteki/`); godlo z zerem wiodacym (`M-34-064`) = 404.
