# Prawdziwe odpowiedzi PRG - punkty adresowe i ulice (plan E, E3; 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi i pelne paczki w `<katalog-danych>`). Cialo kazdej odpowiedzi WFS
bez edycji (poza przycieciem `capabilities.xml`); obok
`<plik>.headers.json` z `url` (pelne zapytanie), kodem HTTP i `Content-Type`
(konwencja `tests/conftest.py::recorded_response`).

## WFS `KrajowaIntegracjaNumeracjiAdresowej` (KIN, GeoServer)

Host `mapy.geoportal.gov.pl/wss/ext/wfs/KrajowaIntegracjaNumeracjiAdresowej`,
WFS 2.0.0, typy `adresyUlice:A07_Punkty_adresowe` i `adresyUlice:A08_Ulice`.

| Plik | Zapytanie | Wynik |
|---|---|---|
| `capabilities.xml` | `GetCapabilities` (przyciete do dwoch typow i ograniczen operacji) | DefaultCRS `urn:ogc:def:crs:EPSG::2180` obu typow, `CountDefault` 10000 |
| `a07_describe.xsd`, `a08_describe.xsd` | `DescribeFeatureType` typu | schemat pol (m.in. `NUMER_PORZADKOWY`, `KOD_POCZTOWY`, `ID_IIP`; geometria `GEOMETRIA`) |
| `a07_b50_hits.xml` | A07, `RESULTTYPE=hits`, `BBOX=244150,567100,244200,567150` (N,E; Krakow, 50 x 50 m) | `numberMatched="3"` |
| `a07_b50_en_hits.xml` | jw., ta sama obwiednia w kolejnosci E,N (`567100,244150,567150,244200`) | `numberMatched="0"` - zamiana osi nie daje bledu, tylko pusty wynik |
| `a07_b50_c2_s0.xml`, `a07_b50_c2_s2.xml` | A07, `COUNT=2`, `STARTINDEX=0` i `2` | 2 + 1 punkty (`gml:id` `A07_Punkty_adresowe.3941826`, `.3942580`, `.3942581`) |
| `a08_b50_hits.xml`, `a08_b50_c2_s0.xml` | A08, `hits` i `COUNT=2`, `STARTINDEX=0` | `numberMatched="2"`, 2 ulice |

Fakty: kazdy obiekt ma `gml:id` (identyfikator warstwy GPKG `gml_id`); osie
EPSG:2180 w kolejnosci N,E (jak w PRG i EGiB). Odpowiedz w ok. 0,3-0,5 s.

## Paczki (`files.json`)

- `powiat_1261`: `https://opendata.geoportal.gov.pl/prg/adresy/PunktyAdresowe/12/1261.zip`
  - naglowki `HEAD` (6 066 872 B, `application/octet-stream`, bez `ETag`
  i `Last-Modified`) i 20 czlonow ZIP (`PRG_PunktyAdresowe_1261`,
  `PRG_Ulice_1261`, `PRG_Place_1261`, `PRG_Miejscowosc_1261`; `.shp`,
  `.shx`, `.dbf`, `.prj`, `.cpg`);
- `country_shp`: plik krajowy SHP `.../PunktyAdresowe/POLSKA.zip`
  (563 815 148 B) - 19 czlonow `PRG_PunktyAdresowe_POLSKA`,
  `PRG_Ulice_POLSKA`, `PRG_Place_POLSKA`, `PRG_Miejscowosci_POLSKA`
  (lista z pelnego pliku pobranego przez CLI; `.dbf` punktow ma
  7 060 915 004 B, wiec ZIP jest w formacie ZIP64);
- `country_gml`: plik krajowy GML `.../prg/adresy/PRG-punkty_adresowe.zip`
  (804 071 557 B) - 16 plikow GML wojewodztw (schemat PRGAD) z data
  i godzina eksportu w nazwie;
- `woj_12`: `.../PunktyAdresowe/12.zip` - HTTP 404 `text/html` (GUGiK nie
  publikuje paczek wojewodztw).

Testy skladaja z list czlonow male ZIP-y - pelne paczki nie trafiaja do
repozytorium.

Testy: `tests/test_prg_addresses.py`, `tests/test_parity_e3.py`.
