# Surowe odpowiedzi WFS PRG GUGiK (2026-10-08)

Pobrane 2026-10-08 przez `curl` z publicznej uslugi
`https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries`
(WFS 2.0.0, MapServer). Pliki zapisane BEZ edycji i bez przycinania.

Wspolne parametry zapytan o powiaty (`Q`):
`SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=ms:A02_Granice_powiatow&PROPERTYNAME=JPT_KOD_JE`.
`BBOX` w EPSG:2180 podawany w kolejnosci osi (N,E):
`<minN>,<minE>,<maxN>,<maxE>,urn:ogc:def:crs:EPSG::2180`.

| Plik | Zapytanie | Obszar EPSG:2180 (E/N) | Wynik |
|---|---|---|---|
| `two_counties.xml` | `?Q&COUNT=1000&BBOX=290000,340000,300000,350000,urn:ogc:def:crs:EPSG::2180` | E 340000-350000, N 290000-300000 (okolice Barda) | HTTP 200, powiaty `0208` (klodzki) i `0224` (zabkowicki) |
| `no_counties.xml` | `?Q&COUNT=1000&BBOX=800000,450000,801000,451000,urn:ogc:def:crs:EPSG::2180` | E 450000-451000, N 800000-801000 (Baltyk) | HTTP 200, pusta kolekcja |
| `truncated_count1.xml` | `?Q&COUNT=1&BBOX=290000,340000,300000,350000,urn:ogc:def:crs:EPSG::2180` | jak `two_counties.xml` | HTTP 200, jedna strona (`0208`) z linkiem `next` |
| `error_400.xml` | `?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=ms:NIEMA&BBOX=1,1,2,2,urn:ogc:def:crs:EPSG::2180` | — | HTTP 400, `ows:ExceptionReport` (`InvalidParameterValue`, `locator="typename"`) |

Postac licznikow kolekcji `wfs:FeatureCollection` w tych odpowiedziach:

- kompletna odpowiedz z obiektami: `numberMatched` LICZBOWE, rowne
  `numberReturned` (`two_counties.xml`: `numberMatched="2"
  numberReturned="2"`; dodatkowo sprawdzone dla obszaru 200 x 250 km:
  `numberMatched="64" numberReturned="64"`), bez atrybutu `next`;
- pusta odpowiedz (morze): `numberMatched="unknown" numberReturned="0"`,
  bez `next` (`no_counties.xml`) — NIE `numberMatched="0"`;
- odpowiedz obcieta stronicowaniem (`COUNT` mniejsze niz liczba
  powiatow): `numberMatched="unknown"`, `numberReturned` = rozmiar strony
  i atrybut `next` z adresem nastepnej strony (`STARTINDEX=...`)
  (`truncated_count1.xml`; tak samo dla obszaru 200 x 250 km z `COUNT=3`).
  Obciecie zdradza wiec atrybut `next` (oraz pelna strona przy `unknown`),
  a nie porownanie `numberReturned < numberMatched`.

Inne fakty z rozpoznania na zywo:

- atrybut kodu: `ms:JPT_KOD_JE` (namespace
  `http://mapserver.gis.umn.edu/mapserver`), 4 cyfry;
- filtr `BBOX` dziala na GEOMETRII powiatu, nie na jego obwiedni: obwiednia
  powiatu klodzkiego `0208` (`wfs:boundedBy` w `truncated_count1.xml`) to
  N 250201-315708, E 300899-359417, a `BBOX` zdegenerowany do punktu
  E 345000, N 295000 (`295000,345000,295000,345000`), lezacego w tej
  obwiedni, zwraca tylko powiat sasiedni `0224` (`numberMatched="1"`);
- bledne zapytanie = HTTP 400 z `ows:ExceptionReport`.

Testy: `tests/test_prg.py`.
