# Surowe odpowiedzi WFS skorowidzy GUGiK NMT/NMPT/LAZ (2026-10-15, plan A)

Pobrane 2026-10-15 przez `requests` (jednorazowy skrypt poza repo, kopia
surowa w `<katalog-danych>`), wylacznie metadane - zadnych plikow danych.
Pliki `.xml` BEZ edycji tresci (`response.content`); pliki `area_*.xml.gz`
to cale odpowiedzi skompresowane gzip (`mtime=0`). Kazda odpowiedz ma HTTP
200 i `Content-Type: text/xml; subtype="gml/3.2.1"; charset=UTF-8`, poza
`exception_report.xml` (HTTP 400, `text/xml`).

Uslugi: `https://mapy.geoportal.gov.pl/wss/service/PZGIK/<usluga>/WFS/Skorowidze`
(`<usluga>`: `NumerycznyModelTerenu{EVRF2007,KRON86}`,
`NumerycznyModelPokryciaTerenu{EVRF2007,KRON86}`,
`DanePomiaroweLidar{EVRF2007,KRON86}`); w nazwach plikow `nmt_evrf2007`,
`nmt_kron86`, `nmpt_evrf2007`, `nmpt_kron86`, `laz_evrf2007`, `laz_kron86`.

Wspolne parametry `GetFeature`: `SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature`,
`TYPENAMES` = WSZYSTKIE typy roczne uslugi z GetCapabilities (nazwy z
prefiksem `gugik:`, od najnowszego, rozdzielone przecinkiem),
`SRSNAME=urn:ogc:def:crs:EPSG::2180`, `COUNT=1000`, `BBOX` w EPSG:2180
w kolejnosci osi (N,E): `<minN>,<minE>,<maxN>,<maxE>,urn:ogc:def:crs:EPSG::2180`.
Wiele typow w jednym zapytaniu daje kolekcje zagniezdzone (`wfs:member` ->
`wfs:FeatureCollection` per typ); `numberReturned` zewnetrznej kolekcji =
liczba obiektow wszystkich typow.

| Plik | Zapytanie | Wynik / przypadek |
|---|---|---|
| `caps_<usluga>.xml` | `GetCapabilities` (dokument caly, bez przycinania) | typy roczne: NMT EVRF2007 2018-2026, NMT KRON86 2000, 2004-2019, NMPT EVRF2007 2019-2026, NMPT KRON86 2010-2019, LAZ EVRF2007 2018-2026, LAZ KRON86 2010-2019 |
| `sheet_<usluga>_<godlo>.xml` | `BBOX` = kwadrat 20 m w srodku ramy godla (`SheetParser.get_bbox(crs="EPSG:2180")`, srodek +-10 m) | rekordy wszystkich arkuszy (kazdej skali), ktorych rama zawiera punkt |
| `area_<usluga>_krakow.xml.gz` | `BBOX=242000,565000,246000,569000` (Krakow, E 565-569 km, N 242-246 km) | NMT EVRF2007 80 obiektow, NMT KRON86 40, NMPT EVRF2007 42, NMPT KRON86 24, LAZ EVRF2007 156, LAZ KRON86 126 |
| `area_<usluga>_pomorze.xml.gz` | `BBOX=744800,339000,747000,343000` (Pomorze, E 339-343 km, N 744,8-747 km) | NMT EVRF2007 26, NMT KRON86 24, NMPT EVRF2007 7, NMPT KRON86 6, LAZ EVRF2007 29, LAZ KRON86 8 |
| `page_nmt_evrf2007_pomorze_count10_{1,2,3}.xml` | jak `area_nmt_evrf2007_pomorze`, ale `COUNT=10`; strony 2 i 3 = adres z atrybutu `next` poprzedniej strony (parametr sesji serwera i `STARTINDEX`) | 10 + 10 + 6 obiektow; strony 1-2 `numberMatched="unknown"` i `next`, strona 3 `numberMatched="26"` bez `next` |
| `exception_report.xml` | `TYPENAMES=gugik:SkorowidzNMT1900`, `BBOX` Krakowa | HTTP 400, `ows:ExceptionReport` (`InvalidParameterValue`, `locator="typename"`) |

Arkusze (`sheet_*`), przypadki testowe planu A:

- NMT EVRF2007: `N-33-58-A-c-1-4` (0.5m 2025 NIE `84020_1844081_...asc`;
  1m 2022; 5m; XYZ 5m 2020), `N-33-58-A-c-1-3` (wylacznie 0.5m: 2021, 2022,
  2025), `M-34-64-D-d-2-1` (1m/5m `.asc`, XYZ 5m i TBD 25m 2018, ASCII NMT
  5m 2019; PL-2000 `7.125.11.04` 1m w punkcie), `N-33-69-A-d-1-3` (rekord
  `ARC/INFO ASCII GRID` z URL `.xyz` 2019 - niespojny; ASCII NMT 0.5m;
  `NMT-N3369Ad13.xyz.zip`), `N-33-77-B-c-3-3` (0.5m, 0.6m, 1m, 5m, XYZ 5m,
  ASCII NMT 1m `NMT-N-33-77-B-c-3-3.zip`), `N-33-77-D-a-1-2` (podobnie),
  `7.159.25.12.2` (0.15m 2023), `6.125.25` (5m i 10m PL-2000 2021 NIE),
  `M-34-1-B-c-2-4` (XYZ 1m `.zip.zip`), `N-34-121-C-b-3-3` (XYZ 5m
  `NMT-N34121Cb33.xyz.zip`, TBD 15m), `M-34-29-A-b-4-2` (TBD 25m, XYZ 5m,
  ASCII NMT 5m), `N-33-46-C-c-3-2` (morze: `numberReturned="0"`,
  `numberMatched="unknown"`).
- NMT KRON86: `6.130.26.07.1.2` (0.5m PL-2000 2018 `70042_814868_...asc`;
  TIN/TTN/TBD 2009 arkusza 1:25000 `M-34-62-A-a-2`), `M-34-64-D-d-2-1` (1m
  2012 i 2017 `.asc` + XYZ; TBD 15m, TIN, TTN 2009 arkusza `M-34-64-D-d-2`;
  XYZ 1m 2015 arkusza `M-34-64-D-d-2`), `N-34-58-D-c-3` (TBD 30m, TIN, TTN
  2000; TBD 25m 2010; XYZ 1m 2014/2016), `M-34-10-B-a-1` (GRD 5m 2009),
  `M-33-24-B-b-1` (warstwice DXF 2004), `N-33-103-B-b-4` (warstwice DGN
  2004), `6.163.35.16.4` (TBD 5m PL-2000 2019 `.zip`), `N-33-58-A-c-1-4`.
- NMPT EVRF2007: `N-33-58-A-d-1-2` (0.5m 2025 NIE `84018_...`, 1m 2022),
  `N-33-77-B-c-3-3` (0.5m 2022/2024, 0.6m 2024).
- NMPT KRON86: `N-34-50-C-d-3-4` (0.5m `.asc` i XYZ 0.5m 2010, 2018).

Maska ladu PRG dla obu obszarow: odpowiedzi W02/W03 nagrane 2026-10-15
tymi samymi zapytaniami co `providers/pl/prg.py::fetch_land_mask` sa bajtowo
rowne (poza atrybutem `timeStamp`) plikom `tests/fixtures/gugik_prg/
land_mask_2026_10_11/` (BBOX nie przycina geometrii): Pomorze =
`*_bbox_coast.xml`, Krakow = `*_bbox_inland.xml` (puste); A00 = caly kraj
(`A00_Granice_panstwa.xml.gz`). Testy uzywaja tamtych plikow.

Testy: `tests/test_skorowidz_wfs.py`, `tests/test_gugik_provider.py`,
`tests/test_gugik_nmpt.py`, `tests/test_availability.py`,
`tests/test_cli_availability.py`, `tests/test_parity.py`.
