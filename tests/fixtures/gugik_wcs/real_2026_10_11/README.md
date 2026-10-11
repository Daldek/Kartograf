# Surowe odpowiedzi WCS GUGiK `image/x-aaigrid` (2026-10-11)

Pobrane 2026-10-11 przez `requests` (jednorazowy skrypt poza repo)
z publicznych uslug WCS 2.0.1 GUGiK. Kazdy plik `*.mime` to CALE cialo
odpowiedzi HTTP bajt w bajt (bez edycji); obok `*.headers.json` z kodem
HTTP i naglowkiem `Content-Type` tej odpowiedzi.

Wspolne parametry (`Q`):
`SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=<cov>&FORMAT=image%2Fx-aaigrid`,
dalej opcjonalnie `&SCALEFACTOR=0.5` i `&SUBSET=x(<x0>,<x1>)&SUBSET=y(<y0>,<y1>)`
w EPSG:2180 (dwa miejsca po przecinku — postac z
`GugikWcsMixin._construct_wcs_url`). Wszystkie zakresy leza na siatce
arkuszy 1 m (krawedzie pikseli `k + 0,5` m).

Endpointy:
- NMT: `https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModel`
- NMPT: `https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMPT/GRID1/WCS/DigitalSurfaceModel`

| Plik | Coverage | `SCALEFACTOR` | `SUBSET` x / y | Wynik |
|---|---|---|---|---|
| `nmt_evrf2007_20x20.mime` | `DTM_PL-EVRF2007-NH` | — | 567580.50-567600.50 / 243664.50-243684.50 (`M-34-64-D-d-2-3`) | 200, ASC 20 x 20, `xllcorner 567580.5`, `cellsize 1` |
| `nmt_evrf2007_20x20_q1..q4.mime` | jw. | — | cwiartki 10 x 10 m: q1 NW (x 567580.50-567590.50, y 243674.50-243684.50), q2 NE (x 567590.50-567600.50, y jw.), q3 SW (x 567580.50-567590.50, y 243664.50-243674.50), q4 SE (x 567590.50-567600.50, y jw.) | 200, ASC 10 x 10 |
| `nmpt_evrf2007_20x20_sf05.mime` | `DSM_PL-EVRF2007-NH` | 0.5 | jak NMT | 200, ASC 20 x 20, `cellsize 1` |
| `nmpt_evrf2007_20x20_sf05_q1..q4.mime` | jw. | 0.5 | cwiartki jak NMT | 200, ASC 10 x 10 |
| `nmpt_kron86_20x20_sf05.mime` | `DSM_PL-KRON86-NH` | 0.5 | 479013.50-479033.50 / 451886.50-451906.50 (`M-34-2-A-b-4-3`) | 200, ASC 20 x 20 |
| `exception_report.xml` | `DTM_PL-NIEMA` (zly), endpoint NMT | — | jak NMT | **HTTP 404** (nie 200), `text/xml`, `ows:ExceptionReport` `NoSuchCoverage` |

Budowa odpowiedzi multipart (`Content-Type: multipart/related;
boundary=wcs`, granica bez cudzyslowu): cialo zaczyna sie od CRLF, czesci
oddziela `--wcs` z CRLF, naglowki czesci konczy pusta linia CRLF; czesci:
`image/x-aaigrid` (`result.asc`), `application/octet-stream`
(`result.asc.aux.xml`, `result.prj` — ESRI WKT `ETRS89_Poland_CS92`);
koniec `--wcs--`. ASC: linie LF, naglowek `ncols/nrows/xllcorner/
yllcorner/cellsize`, bez `NODATA_value`.

Referencje z arkuszy OpenData (`*_sheet_values.npy`, float32 20 x 20,
wiersze N->S), wyciete z arkuszy pobranych w pomiarze 2026-10-11
(`docs/research/2026-10-11-wcs-cutouts/raport.md`) z tych samych okien:

| Plik | Arkusz |
|---|---|
| `nmt_evrf2007_20x20_sheet_values.npy` | NMT EVRF2007 1 m `M-34-64-D-d-2-3` (lot 2025, najnowszy 1 m) |
| `nmpt_kron86_20x20_sf05_sheet_values.npy` | NMPT KRON86 1 m `M-34-2-A-b-4-3` (lot 2011) |
| `nmpt_evrf2007_20x20_sf05_sheet_values.npy` | NMPT EVRF2007 0,5 m `M-34-64-D-d-2-3` (lot 2025; jedyny lot NMPT EVRF2007 tego arkusza), zdecymowany do pikseli 0,5 m o srodkach na pelnych metrach (raport pkt 3) |

Sprawdzone przy nagraniu: ASC kazdego zapytania 20 x 20 == referencja
(bit w bit po rzutowaniu na float32), a cwiartki q1..q4 zlozone
`[[q1, q2], [q3, q4]]` == odpowiedz 20 x 20 (NMT i NMPT).

Testy: `tests/test_transport_aaigrid.py`, `tests/test_gugik_provider.py`,
`tests/test_gugik_nmpt.py`, `tests/test_wcs_cutout.py`.
