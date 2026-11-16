# Rekordy indeksow arkuszy i kafli (`transport/index_records.py`, plan E, E0)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi i proby w `<katalog-danych>`). Obok kazdej odpowiedzi
`<plik>.headers.json` z kodem HTTP i `Content-Type` (konwencja
`tests/conftest.py::recorded_response`); zadna odpowiedz nie miala `ETag`
ani `Last-Modified`. Wszystkie pliki sa BEZ edycji (male odpowiedzi w
calosci). Testy: `tests/test_index_records.py` (warianty bledne powstaja w
tescie z tych plikow: inny `numberReturned`, `next` na obcy host, tabela bez
wiersza daty, uklad `PL-2000` bez strefy).

## Wizualizacje BDOT10k - GetFeatureInfo

Usluga `https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT/WMS/PobieranieArkuszeMapBDOT10k`.
Wspolne parametry (`Q`): `SERVICE=WMS&VERSION=1.3.0&REQUEST=GetFeatureInfo&LAYERS=<w>&QUERY_LAYERS=<w>&INFO_FORMAT=text/html&CRS=EPSG:2180&WIDTH=100&HEIGHT=100&I=50&J=50`,
`BBOX` = kwadrat +-10 m wokol srodka ramki arkusza w EPSG:2180 w kolejnosci
osi N,E (jak `gfi_records`).

| Plik | Warstwa, `BBOX` (N,E) | Wynik (czas) |
|---|---|---|
| `gfi_mapy10k_M-34-64-D-d-1.html` | `Mapy10k`, `244299.1228408157,564835.0728594385,244319.1228408157,564855.0728594385` (srodek `M-34-64-D-d-1`) | 200 `text/html` bez charsetu, 2340 B UTF-8 (z polskimi znakami); tabela: `Godlo: M-34-064-D-d-1`, link PDF, link GeoTIFF, `Stan bazy BDOT10k na dzien: 2026-05-27` (0,50 s) |
| `gfi_mapy25k_M-34-64-D-d.html` | `Mapy25k`, `242012.49734463077,567102.9776740388,242032.49734463077,567122.9776740388` | tabela `M-34-064-D-d`; naglowek `Pobierz plik:` przy PDF i **pusty `<th>`** przy GeoTIFF; data `2026-06-29 00:00:00` (0,24 s) |
| `gfi_mapy50k_M-34-64-D.html` | `Mapy50k`, `246595.1271380596,562586.4253746092,246615.1271380596,562606.4253746092` | tabela `M-34-064-D`; `Pobierz plik:` (PDF), `Pobierz plik GeoTIFF:`; data `2025-03-02 00:00:00` (0,48 s) |
| `gfi_mapy100k_M-34-64.html` | `Mapy100k`, `255783.03443038138,553599.6734852287,255803.03443038138,553619.6734852287` | tabela `M-34-064` (tytul z nazwa arkusza, `Arkusz - M-34-064  KRAKOW - ZACH.` z polskimi znakami), PDF i GeoTIFF w `.../Wizualizacja_BDOT10k_100000/M-34/`; data `2025-01-31 00:00:00` (0,37 s) |
| `gfi_mapy10k_outside.html` | `Mapy10k`, `499990.0,99990.0,500010.0,100010.0` (poza Polska) | 200 `text/html`, **0 B** (0,22 s) |
| `gfi_exception_bad_layer.xml` | `LAYERS=QUERY_LAYERS=NieMa`, `BBOX=244590,566190,244610,566210` | **200** `text/xml; charset=UTF-8`, `ServiceExceptionReport` `LayerNotDefined` |

Fakty:

- Ksztalt tabeli jest wspolny dla wszystkich skal: `<table class="styled-table">`,
  wiersze `<th>naglowek</th> <td>wartosc</td>`, godlo w niezamknietym `<a >`.
  Rozni sie: naglowki wierszy linkow (1:25000 - pusty `<th>` przy GeoTIFF),
  data (1:10000 sama data, 1:25000-1:100000 z `00:00:00`). Format pliku
  wynika z rozszerzenia linku (`.pdf`, `.tif`), nie z naglowka.
- Godlo publikowane z trzycyfrowym numerem arkusza 1:100000 (`M-34-064-D-d-1`);
  jednostka = godlo kanoniczne `M-34-64-D-d-1`.
- Kazda skala ma inna date stanu bazy dla tego samego obszaru (2026-05-27,
  2026-06-29, 2025-03-02, 2025-01-31).

## Mesh 3D - WFS

Usluga `https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/WFS/ModeleSiatkowe3D`,
typ `gugik:SkorowidzModeleSiatkowe3D`.

| Plik | Zapytanie | Wynik (czas) |
|---|---|---|
| `mesh_p1.xml` | `?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=gugik%3ASkorowidzModeleSiatkowe3D&SRSNAME=urn%3Aogc%3Adef%3Acrs%3AEPSG%3A%3A2180&BBOX=244500.0%2C566100.0%2C244700.0%2C566300.0%2Curn%3Aogc%3Adef%3Acrs%3AEPSG%3A%3A2180&COUNT=2` (Krakow; ten sam URL co `WfsIndex._pages` przy `PAGE_SIZE=2` i `BBox(566100.0, 244500.0, 566300.0, 244700.0)`) | 200, `numberMatched="unknown" numberReturned="2"`, kafle `74230_55482` (`gml:id` `SkorowidzModeleSiatkowe3D.6777`), `74228_55482` (`.6776`); `next` = jw. + `&STARTINDEX=2` (0,34 s) |
| `mesh_p2.xml` | `next` z `mesh_p1.xml` | 200, `numberReturned="2"`, kafle `74230_55480` (`.6953`), `74228_55480` (`.6952`); **bez `next`** (0,35 s) |
| `mesh_no_params.html` | adres uslugi bez parametrow | **200** `text/html`, strona informacyjna WFS (w testach: HTML zamiast XML i HTML bez tabeli arkusza) |

Fakty:

- Przestrzen nazw typu: `https://www.gugik.gov.pl` (indeksy NMT/NMPT/LAZ:
  `http://www.gugik.gov.pl`) - `WfsIndex` porownuje nazwy lokalne.
- Pola obiektu (kolejnosc z odpowiedzi): `boundedBy`, `msGeometry`, `akt_rok`,
  `Zrodlo_danych`, `Charakterystyka_przestrzenna_zrodla_danych` (`0.05 m`),
  `uklad_xy` (`PL-2000:S7`), `uklad_h` (`PL-EVRF2007-NH`),
  `Blad_sredni_polozenia`, `Blad_sredni_wysokosci`, `Numer_zgloszenia_pracy`
  (`DFT.7201.043.2023`), `format` (`OBJ`), `Aktualnosc` (`2021-10-03`, zwykly
  tekst, nie `gml:TimeInstant`), `modul` (id kafla), `Modul_archiwizacji`
  (`200`), `URL_do_pobrania`
  (`https://opendata.geoportal.gov.pl/DaneFotogrametryczne/Mesh/78944/78944_6777_74230_55482.zip`),
  `Data_wlaczenia_do_PZGiK`.
- `numberMatched`: strony `GetFeature` - `unknown`; `RESULTTYPE=hits` dla
  obszaru fixtur - `4`, dla `BBOX=244000,566000,245000,567000` - 37 (to samo
  w odpowiedzi `COUNT=1000`: `numberMatched="37"`), Krakow
  `BBOX=240000,560000,250000,575000` - 3884 (0,64 s), cala Polska
  `100000,100000,900000,900000` - 132 745 (0,95 s).
- Jeden rekord na kafel: w 3884 obiektach Krakowa (`COUNT=5000`, serwer
  oddal wszystkie na jednej stronie bez `next`; 7,5 MB w 2,5 s) kazdy `modul`
  wystepuje raz; wszystkie `akt_rok=2021`, `Aktualnosc=2021-10-03`,
  `Numer_zgloszenia_pracy=DFT.7201.043.2023`, `uklad_xy=PL-2000:S7`. Kilku
  lat jednego kafla nie zaobserwowano.
- Kolejnosc stron `COUNT=2` nie jest kolejnoscia odpowiedzi `COUNT=1000`
  (w `BBOX=244000,566000,245000,567000` strona 2 dala `.7121`, `.6776`,
  a odpowiedz pelna ma na pozycjach 3-4 `.7461`, `.7293`).
- Gdy sesja niesie ciasteczko uslugi (`Set-Cookie: gahLaQu1eeYooCu=...`),
  MapServer dopisuje do `next` parametr `gahLaQu1eeYooCu=<liczba>` - na
  kazdej kolejnej stronie jeszcze raz (powtorzony parametr); `next` wciaz
  zaczyna sie od adresu uslugi. Fixtury nagrano bez ciasteczka.
