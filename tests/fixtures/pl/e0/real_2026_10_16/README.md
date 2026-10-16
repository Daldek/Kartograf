# Prawdziwe odpowiedzi dla kontraktu kolekcji planu E (Task E0, 2026-10-16)

Nagrane 2026-10-16 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi w `<katalog-danych>`). Obok kazdej odpowiedzi WFS
`<plik>.headers.json` z kodem HTTP i `Content-Type` (konwencja
`tests/conftest.py::recorded_response`). Pliki WFS sa bez edycji.

Testy: `tests/test_collections_units.py`, `tests/test_unit_package.py`.
Testy korzystaja tez z fixtur pakietow E0: `tests/fixtures/pl/index_records/`
(GFI `Mapy10k`, strony WFS mesh 3D), `tests/fixtures/cuzk/real_2026_10_16/`
(RUIAN 7, `KladyMapovychListu` 2) i `tests/fixtures/pl/feature_bbox/`
(OGC API PRNG).

## Osnowa grawimetryczna (WFS, wybor kanalu po `--network`)

Usluga `https://mapy.geoportal.gov.pl/wss/service/PZGIK/OsnowaGrawimetryczna/WFS`
(MapServer, WFS 2.0.0; adres bez `/WFS` nie odpowiada). Wspolne parametry
(`Q`): `SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&SRSNAME=urn:ogc:def:crs:EPSG::2180&BBOX=200000,500000,300000,650000,urn:ogc:def:crs:EPSG::2180`
(osie N,E; obszar wokol Krakowa).

| Plik | Zapytanie | Wynik |
|---|---|---|
| `grav_capabilities.xml` | `GetCapabilities` | typy `ms:Fundamentalna_grawimetryczna`, `ms:Bazowa_grawimetryczna`; DefaultCRS `urn:ogc:def:crs:EPSG::2180`; bez `CountDefault` |
| `grav_fundamentalna_describe.xsd`, `grav_bazowa_describe.xsd` | `DescribeFeatureType` | schematy MapServera (import GML) |
| `grav_fundamentalna_hits.xml` | `Q&TYPENAMES=ms:Fundamentalna_grawimetryczna&RESULTTYPE=hits` | `numberMatched="12"` |
| `grav_fundamentalna_c1000_s0.xml` | jw. bez `RESULTTYPE`, `COUNT=1000&STARTINDEX=0` | 12 punktow, bez `next` |
| `grav_bazowa_hits.xml` | `Q&TYPENAMES=ms:Bazowa_grawimetryczna&RESULTTYPE=hits` | `numberMatched="6"` |
| `grav_bazowa_c1000_s0.xml` | jw., `COUNT=1000&STARTINDEX=0` | 6 punktow, bez `next` |

Fakt z nagrania: serwer zrywa czasem polaczenie bez odpowiedzi
(`RemoteDisconnected`, curl kod 56 po ok. 10 s); ponowienie tego samego
zapytania odpowiada 200 (wspolna polityka ponowien `transport/http.py`).

## Pliki (`files.json`)

`files.json` trzyma prawdziwy URL i naglowki odpowiedzi (`HEAD` albo
poczatek `GET`; GUGiK `opendata` nie wysyla `ETag` ani `Last-Modified`,
CUZK wysyla oba). Testy skladaja z nich male odpowiedzi - duze pliki nie
trafiaja do repozytorium:

- `map10k_tiff`, `map10k_pdf` - wizualizacja BDOT10k 1:10000 arkusza
  `M-34-064-D-d-1` (GeoTIFF 66 592 473 B, PDF 56 875 203 B); pliki `*.head`
  to pierwsze 256 bajtow odpowiedzi (`II*\0`, `%PDF-1.4`);
- `geoid2021_txt` - model quasi-geoidy PL-geoid2021 (42 328 086 B); `*.head`
  to pierwsze 512 bajtow (naglowek `Szerokosc Dlugosc Zeta`, wiersze CRLF);
- `rcn_1261` - RCN powiatu 1261, GPKG w ZIP: `Content-Length` 301 623 607 B
  (2026-10-15: 236 404 584 B - plik `latest_exports` jest podmieniany);
- `prng_miejscowosci_gml`, `prng_obiekty_gml` - pliki krajowe PRNG GML
  (20 358 653 B i 26 414 682 B) z pelna lista czlonow ZIP (pobrane w
  calosci; pierwszy czlon to pusty plik z data eksportu w nazwie);
- `cz_km_shp_623164` - mapa katastralna CZ, KU 623164, SHP: naglowki
  `HEAD` (`ETag`, `Last-Modified`) i podzbior 106 czlonow ZIP (katalog
  `623164/`, warstwy `BUDOVY_B`, `PARCELY_KN_P`).
- `cz_km_shp_652954`, `cz_km_shp_696137`, `cz_km_shp_753521` - naglowki
  `HEAD` (`ETag`, `Last-Modified`) paczek SHP trzech KU z odpowiedzi RUIAN
  `ruian_7_bbox_tesin.json` (sprawdzenie aktualnosci bez pobierania);
- `cz_ztm10_tiff_0510-C-15`, `cz_ztm10_tiff_0510-D-11` - naglowki `HEAD`
  arkuszy ZTM10 S-JTSK TIFF (`openzu .../ZTM10-SJTSK-TIFF/<MAPNOM>.zip`,
  38 888 699 B i 13 959 425 B, `ETag`, `Last-Modified`).
