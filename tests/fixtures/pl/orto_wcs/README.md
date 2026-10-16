# Prawdziwe odpowiedzi WCS ortofotomapy GUGiK (2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi i proby w `<katalog-danych>`) z dwoch uslug WCS 2.0.1 GUGiK.
Kazdy plik to CALE cialo odpowiedzi HTTP bajt w bajt (bez edycji); obok
`<plik>.headers.json` z kodem HTTP i `Content-Type` (konwencja
`tests/conftest.py::recorded_response`).

Endpointy i coverage:
- Standard: `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WCS/StandardResolution`,
  `COVERAGEID=Orthoimagery_StandardResolution`;
- High: `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WCS/HighResolution`,
  `COVERAGEID=Orthoimagery_High_Resolution`.

Wspolne parametry `GetCoverage` (`Q`):
`SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=<cov>&FORMAT=image%2Ftiff`,
dalej opcjonalnie `&SCALEFACTOR=<s>` i `&SUBSET=x(<x0>,<x1>)&SUBSET=y(<y0>,<y1>)`
w EPSG:2180 (dwa miejsca po przecinku - postac z
`GugikWcsMixin._construct_wcs_url`).

| Plik | Usluga | Zapytanie | Wynik |
|---|---|---|---|
| `describe_standard.xml` | Standard | `?SERVICE=WCS&VERSION=2.0.1&REQUEST=DescribeCoverage&COVERAGEID=Orthoimagery_StandardResolution` | 200; siatka krajowa EPSG:2180, `offsetVector` 0,1 m, pasma `R`, `G`, `B` |
| `describe_high.xml` | High | jw. z `COVERAGEID=Orthoimagery_High_Resolution` | 200; jak Standard (rozni sie tylko identyfikatorami) |
| `standard_0.25m_4x4.tif` | Standard | `?Q&SCALEFACTOR=0.4&SUBSET=x(566000.00,566001.00)&SUBSET=y(243000.00,243001.00)` (Krakow) | 200, GeoTIFF 4 x 4 px, piksel 0,25 m, 3 pasma uint8, EPSG:2180, bez nodata, paskowy, bez kompresji |
| `standard_0.25m_4x4_q1.tif` .. `_q4.tif` | Standard | jw., cwiartki 0,5 x 0,5 m: q1 NW (x 566000.00-566000.50, y 243000.50-243001.00), q2 NE (x 566000.50-566001.00, y jw.), q3 SW (x 566000.00-566000.50, y 243000.00-243000.50), q4 SE (x 566000.50-566001.00, y jw.) | 200, GeoTIFF 2 x 2 px kazda |
| `standard_0.25m_odd_3x3.tif` | Standard | `?Q&SCALEFACTOR=0.4&SUBSET=x(566000.00,566000.75)&SUBSET=y(243000.00,243000.75)` (bok 7,5 piksela 0,1 m) | 200, ale **zla siatka**: 2 x 3 px, piksel 0,48 x 0,26 m, naroznik NW 565999.89/243000.76 zamiast 3 x 3 px po 0,25 m |
| `high_0.1m_4x4.tif` | High | `?Q&SUBSET=x(566000.00,566000.40)&SUBSET=y(243000.00,243000.40)` (Krakow, bez `SCALEFACTOR`) | 200, GeoTIFF 4 x 4 px, piksel 0,1 m; bajty identyczne z odpowiedzia Standard na to samo zapytanie |
| `high_0.1m_4x4_nodata.tif` | High | `?Q&SUBSET=x(738960.00,738960.40)&SUBSET=y(626588.00,626588.40)` (Biebrza, poza obszarami pikseli 10 cm) | 200, GeoTIFF 4 x 4 px, wszystkie piksele 0,0,0 (Standard ma tu obraz) |
| `exception_extent.xml` | Standard | `?Q&SUBSET=x(436370.00,436370.40)&SUBSET=y(815668.00,815668.40)` (Baltyk, poza zasiegiem coverage) | **HTTP 400**, `text/xml`, `ows:ExceptionReport` `ExtentError` |

## Fakty z nagrania i prob na zywo (2026-10-16)

- **DescribeCoverage:** obie coverage maja te sama siatke krajowa: `origin`
  796521.619410 160828.393266 (y x), `offsetVector` 0,1 m, `GridEnvelope`
  0 0 - 7152015 6975927. Abstrakty `GetCapabilities`: Standard "najnowsze
  dostepne ortofotomapy dla obszaru Polski", High "wysokorozdzielcze
  ortofotomapy dla obszaru Polski o pikselu 10 cm i mniejszym"; formaty
  m.in. `image/tiff`, `image/png`, `image/jpeg`.
- **Siatka wyniku = zasieg zapytania:** serwer nie przyciaga `SUBSET` do
  siatki coverage; odpowiedz ma dokladnie zasieg zapytania i piksel
  0,1 m / `SCALEFACTOR` (0,5 m: `SCALEFACTOR=0.2`, 1 m: `0.1` - 2 x 2
  i 3 x 3 px dokladne).
- **Bok w calych pikselach 0,1 m:** przy `SCALEFACTOR=0.4` (piksel 0,25 m)
  bok 0,75 m (7,5 piksela coverage) daje zla siatke
  (`standard_0.25m_odd_3x3.tif`), a bok 0,25 m (2,5 piksela) - HTTP 400
  `msImageCreate(): ... out of memory`; boki 0,5 m, 1 m, 20 m i 40 m sa
  dokladne. Parzysta liczba pikseli 0,25 m = cala liczba pikseli coverage
  (regula parzystych kawalkow w `providers/pl/wcs.py`).
- **Kawalki nie sa bit w bit z jednym zapytaniem:** serwer przeprobkowuje
  kazde zapytanie we wlasnym zasiegu. Cwiartki zlozone `[[q1, q2], [q3, q4]]`
  != `standard_0.25m_4x4.tif`; na zywo 20 x 20 m przy 0,1 m (4 cwiartki
  10 m): rozni sie 75-93 % pikseli cwiartki, srednio 4 DN (max 89),
  najlepsze przesuniecie o cale piksele (0, 0); 40 x 40 m przy 0,25 m:
  70 % pikseli, srednio 4,4 DN (max 120). To samo zapytanie powtorzone
  daje te same bajty.
- **High poza obszarami 10 cm** odpowiada HTTP 200 z obrazem 0,0,0 (bez
  bledu i bez nodata).
- **Czasy (2026-10-16, noc):** 2 x 2 i 4 x 4 px 5-11 s, 160 x 160 px
  (0,25 m) 8 s, 200 x 200 px (0,1 m) 5 s.

Testy: `tests/test_orto_cutout.py`.
