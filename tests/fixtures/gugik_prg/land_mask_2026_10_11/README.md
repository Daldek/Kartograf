# Surowe odpowiedzi WFS PRG GUGiK — maska ladu PL (2026-10-11)

Pobrane 2026-10-11 przez `requests` (jednorazowy skrypt poza repo)
z `https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries`
(WFS 2.0.0, MapServer). Pliki BEZ edycji; `A00_Granice_panstwa.xml.gz`
to cala odpowiedz skompresowana gzip (`mtime=0`). Obok `*.headers.json`
z kodem HTTP i `Content-Type`.

Wspolne parametry (`Q`): `SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature`.
`BBOX` w EPSG:2180 w kolejnosci osi (N,E):
`<minN>,<minE>,<maxN>,<maxE>,urn:ogc:def:crs:EPSG::2180`.

| Plik | Zapytanie | Wynik |
|---|---|---|
| `A00_Granice_panstwa.xml.gz` | `?Q&TYPENAMES=ms:A00_Granice_panstwa` (bez `BBOX`) | 200, 2 047 024 B przed kompresja, 1 obiekt, `gml:Polygon` (1 `exterior`), `numberMatched="1" numberReturned="1"` |
| `W02_Morze_terytorialne_RP_bbox_coast.xml` | `?Q&TYPENAMES=ms:W02_Morze_terytorialne_RP&BBOX=735000,465000,765000,490000,urn:ogc:def:crs:EPSG::2180` (E 465-490 km, N 735-765 km: Gdynia, Zatoka Pucka, Hel) | 200, 1 obiekt, `gml:Polygon` |
| `W03_Morskie_wody_wewnetrzne_bbox_coast.xml` | jw. z `ms:W03_Morskie_wody_wewnetrzne` | 200, 1 obiekt, `gml:MultiSurface` (1 `surfaceMember`, 1 `exterior`, 58 `interior`) |
| `W02_Morze_terytorialne_RP_bbox_inland.xml` | `?Q&TYPENAMES=ms:W02_Morze_terytorialne_RP&BBOX=500000,600000,502000,602000,urn:ogc:def:crs:EPSG::2180` (E 600-602 km, N 500-502 km, w glebi ladu) | 200, `numberMatched="0" numberReturned="0"` |
| `W03_Morskie_wody_wewnetrzne_bbox_inland.xml` | jw. z `ms:W03_Morskie_wody_wewnetrzne` | 200, `numberMatched="0" numberReturned="0"` |
| `exception_report.xml` | `?Q&TYPENAMES=ms:NIEMA&BBOX=500000,600000,502000,602000,urn:ogc:def:crs:EPSG::2180` | **HTTP 400**, `ows:ExceptionReport` (`InvalidParameterValue`, `locator="typename"`) |

Fakty z nagrania:

- `BBOX` nie przycina geometrii: W02/W03 dla okna przybrzeznego to cale
  obiekty (ten sam rozmiar odpowiedzi dla okna N 750-760 km, E 470-490 km);
  `A00` zawsze caly poligon kraju (z morzem terytorialnym).
- `posList` w kolejnosci osi (N,E), `srsDimension="2"`, srsName
  `urn:ogc:def:crs:EPSG::2180`.
- Pusta odpowiedz W02/W03 poza wybrzezem ma `numberMatched="0"` (inaczej
  niz pusta odpowiedz warstwy powiatow: `unknown`).

Testy: `tests/test_prg.py`, `tests/test_wcs_cutout.py`.
