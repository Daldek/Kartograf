# Prawdziwe odpowiedzi WFS, ArcGIS REST i OGC API Features dla silnika `feature_bbox` (2026-10-15, 2026-10-16)

Nagrane 2026-10-15 przez `requests` (jednorazowy skrypt poza repo; surowe
odpowiedzi i proby w `<katalog-danych>`) z czterech uslug: PRG i EGiB GUGiK
(MapServer, WFS 2.0.0), RUIAN CUZK (ArcGIS REST 11.5) i HY-NET CUZK
(GeoServer, WFS 2.0.0); 2026-10-16 doszlo OGC API Features PRNG GUGiK
(sekcja "PRNG"). Obok kazdej odpowiedzi `<plik>.headers.json` z kodem HTTP,
`Content-Type` i - gdy byl - `ETag` (konwencja
`tests/conftest.py::recorded_response`).

Pliki sa BEZ edycji, z trzema wyjatkami:

- `prg_capabilities.xml` - z 52 elementow `FeatureType` zostaly A01-A06
  (reszta dokumentu bajt w bajt jak w odpowiedzi; 76 474 B -> 23 400 B);
- `hynet_capabilities.xml` - usuniety `fes:Filter_Capabilities` (lista
  funkcji, 86 KB); reszta bez zmian;
- `ruian_l12_r2_o*.json.gz` - cala odpowiedz skompresowana gzip (`mtime=0`);
  naglowki w `ruian_l12_r2_o*.json.headers.json`.

Testy: `tests/test_feature_bbox.py`, `tests/test_gpkg_writer.py`.

## PRG (`https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries`)

Wspolne parametry (`Q`): `SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=ms:A06_Granice_obrebow_ewidencyjnych&SRSNAME=urn:ogc:def:crs:EPSG::2180`.
`BBOX` w EPSG:2180 w kolejnosci osi (N,E): `<minN>,<minE>,<maxN>,<maxE>,urn:ogc:def:crs:EPSG::2180`.

| Plik | Zapytanie | Wynik |
|---|---|---|
| `prg_capabilities.xml` | `?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetCapabilities` | 200; DefaultCRS kazdego typu `urn:ogc:def:crs:EPSG::2180`; brak ograniczenia `CountDefault` |
| `prg_a06_describe.xsd` | `?SERVICE=WFS&VERSION=2.0.0&REQUEST=DescribeFeatureType&TYPENAMES=ms:A06_Granice_obrebow_ewidencyjnych` | 200; `msGeometry` = `gml:GeometryPropertyType`, wszystkie pola `string`, `import` tylko schematu GML |
| `prg_a06_b4_hits.xml` | `?Q&BBOX=244000,566000,244400,566400,urn:ogc:def:crs:EPSG::2180&RESULTTYPE=hits` (Krakow) | `numberMatched="4"` |
| `prg_a06_b4_c2_s0.xml` | `?Q&BBOX=...jw...&COUNT=2&STARTINDEX=0` | 2 obiekty (`c9accfd4...`, `88085a07...`), `numberMatched="unknown"`, **bez `next`** |
| `prg_a06_b4_c2_s2.xml` | jw., `STARTINDEX=2` | 2 obiekty: **ten sam `88085a07...`** i `e3ca3282...`; z `next` |
| `prg_a06_b4_c2_s4.xml` | jw., `STARTINDEX=4` | 1 obiekt (`5ac9434d...`) - 4. unikalny dopiero tutaj; `numberMatched="5"` |
| `prg_a06_b4_c2_s6.xml` | jw., `STARTINDEX=6` | 0 obiektow |
| `prg_a06_sea_hits.xml` | `?Q&BBOX=800000,450000,801000,451000,urn:ogc:def:crs:EPSG::2180&RESULTTYPE=hits` (Baltyk) | `numberMatched="0"` |
| `prg_a06_sea_c2_s0.xml` | jw. bez `RESULTTYPE`, `COUNT=2&STARTINDEX=0` | `numberMatched="unknown" numberReturned="0"` (w testach jako odpowiedz `hits` bez liczby) |
| `prg_exception_bad_typename.xml` | `?Q` z `TYPENAMES=ms:NIEMA`, `RESULTTYPE=hits` | **HTTP 400**, `ows:ExceptionReport` (`InvalidParameterValue`, `locator="typename"`) |

## EGiB (`https://mapy.geoportal.gov.pl/wss/service/PZGIK/EGIB/WFS/UslugaZbiorcza`)

`Q` jak dla PRG, z `TYPENAMES=ms:dzialki` albo `ms:budynki`.

| Plik | Zapytanie | Wynik |
|---|---|---|
| `egib_capabilities.xml` | `GetCapabilities` | 200; typy `ms:dzialki`, `ms:budynki`, DefaultCRS `urn:ogc:def:crs:EPSG::2180`, `CountDefault=1000` |
| `egib_dzialki_describe.xsd`, `egib_budynki_describe.xsd` | `DescribeFeatureType` | 200; `geom` = `gml:SurfacePropertyType`, pola `string`; `DATA` tylko w `dzialki` |
| `egib_dzialki_bw_c2_s0.xml`, `egib_dzialki_bw_c2_s2.xml` | `?Q&BBOX=487160,637100,487185,637125,urn:ogc:def:crs:EPSG::2180&COUNT=2&STARTINDEX=0` i `=2` (Warszawa, 1465; `hits` = 3) | 2 (z `next`) + 1 (`numberMatched="3"`); `DATA` = `2026-10-14` |
| `egib_budynki_bw_c2_s0.xml` | jw. dla `ms:budynki` (`hits` = 1) | 1 budynek `budynki.146510_8.0309.18_BUD` zapisany jako **dwa elementy `<ms:geom>`** (dwie czesci) |
| `egib_dzialki_br_hits.xml`, `egib_dzialki_br_c2_s0.xml` | `?Q&BBOX=588600,654800,588800,655000,urn:ogc:def:crs:EPSG::2180` + `RESULTTYPE=hits` / `COUNT=2&STARTINDEX=0` (powiat 1415) | `numberMatched="2"`; strona: 2 dzialki bez `next`, `DATA` = `2026-10-15` |
| `egib_budynki_br_hits.xml`, `egib_budynki_br_c2_s0.xml` | jw. dla `ms:budynki` | `numberMatched="0"`; strona: `numberMatched="unknown" numberReturned="0"` |
| `egib_no_service.html` | `UslugaZbiorcza` bez parametrow | **HTTP 200**, `text/html` (strona informacyjna EGiB) |

## RUIAN (`https://ags.cuzk.gov.cz/arcgis/rest/services/RUIAN/MapServer`)

Filtr (`F`): `geometry=-455000,-1115000,-450000,-1110000&geometryType=esriGeometryEnvelope&inSR=5514&spatialRel=esriSpatialRelIntersects`.

| Plik | Zapytanie | Wynik |
|---|---|---|
| `ruian_layer12_info.json` | `/12?f=json` | warstwa `Obec`, `esriGeometryPolygon`, `maxRecordCount` 1 000 000, `extent.spatialReference` i `sourceSpatialReference`: `wkid` 102067, `latestWkid` 5514; pola m.in. `objectid` (OID), `kod` (Integer), `nazev` (String), `okres` (SmallInteger), `platiod` (Date), `shape` (Geometry), `st_area(shape)` (Double) |
| `ruian_l12_count.json` | `/12/query?F&returnCountOnly=true&f=json` | `{"count":4}` |
| `ruian_l12_count_sea.json` | jw. z `geometry=-300000,-1300000,-299000,-1299000` (poza CZ) | `{"count":0}` |
| `ruian_l12_count_geojson_error.json` | `/12/query?F&returnCountOnly=true&f=geojson` | **HTTP 200** z `{"error":{"code":400,"message":"Requested format is not supported.",...}}` |
| `ruian_l12_r2_o0.json.gz`, `ruian_l12_r2_o2.json.gz` | `/12/query?F&outSR=5514&outFields=*&orderByFields=objectid&resultOffset=0` (i `=2`) `&resultRecordCount=2&returnGeometry=true&f=geojson` | 2 + 2 obce (`objectid` 6169, 6189 / 12391, 13310), `crs` `EPSG:5514`, daty w ms od epoki; strona 0 z `exceededTransferLimit: true` |

## HY-NET (`https://geoportal.cuzk.gov.cz/geoserver/hy-n/wfs`)

| Plik | Zapytanie | Wynik |
|---|---|---|
| `hynet_capabilities.xml` | `GetCapabilities` (przyciete, patrz wyzej) | typy `hy-n:HydroNode`, `hy-n:WatercourseLink`, `hy-n:WatercourseSeparatedCrossing`; DefaultCRS `http://www.opengis.net/def/crs/EPSG/0/5514`; `CountDefault=1000` |
| `hynet_hydronode_xy_hits.xml` | `?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=hy-n:HydroNode&SRSNAME=urn:ogc:def:crs:EPSG::5514&BBOX=-452000,-1112000,-451000,-1111000,urn:ogc:def:crs:EPSG::5514&RESULTTYPE=hits` (X,Y) | `numberMatched="11"` (odpowiedz `hits` tez ma `next`) |
| `hynet_hydronode_yx_hits.xml` | jw. z osiami zamienionymi: `BBOX=-1112000,-452000,-1111000,-451000,...` | `numberMatched="0"`, bez bledu |

## PRNG (`https://ogcapi.geoportal.gov.pl/res/ims/maps/PRNG/apiFeatures`)

OGC API Features, nagrane 2026-10-16 (`requests`, parametry w kolejnosci
silnika `f`, `bbox`, `limit`; `requests` koduje przecinki `bbox` jako `%2C`).
`I` = `/collections/NazwaGeograficznaRP/items`. Pliki bez edycji; naglowki
odpowiedzi 200 maja `ETag`, zadna nie ma `Last-Modified`.

| Plik | Zapytanie | Czas | Wynik |
|---|---|---|---|
| `prng_collections.json` | `/collections?f=json` | 0,36 s | 200 `application/json`; 2 kolekcje: `PolskaNazwaGeograficznaSwiata` (przechowywanie EPSG:4326) i `NazwaGeograficznaRP` (EPSG:2180); `crs` obu tylko `http://www.opengis.net/def/crs/OGC/1.3/CRS84` |
| `prng_rp_krk_l5_o0.json` | `I?f=json&bbox=19.93,50.055,19.945,50.065&limit=5` (Krakow, lon,lat) | 93,4 s | 200 `application/geo+json`; `numberMatched` 9, `numberReturned` 5; `next` = `I?f=json&offset=5&limit=5&bbox=19.93,50.055,19.945,50.065` |
| `prng_rp_krk_l5_o5.json` | dokladnie `href` linku `next` powyzej | 79,6 s | `numberMatched` 9, `numberReturned` 4 (razem 9 roznych `id`); `previous` z `offset=0`, bez `next` |
| `prng_rp_krk_l1_o0.json` | `I?f=json&bbox=19.93,50.055,19.945,50.065&limit=1` | 78,5 s | `numberMatched` 9, `numberReturned` 1; `next` z `offset=1&limit=1` |
| `prng_rp_sea_l5_o0.json` | `I?f=json&bbox=14,54.9,14.01,54.91&limit=5` (Baltyk) | 93,7 s | `numberMatched` 0, `numberReturned` 0, `features` puste, bez `next` |
| `prng_error_no_collection.json` | `/collections/NieMa/items?f=json&bbox=19.93,50.055,19.945,50.065&limit=5` | 0,31 s | **HTTP 400** `application/json`: `{"error":{"instance":"s-ims-02","message":"No map item PRNG.NieMa","code":600010,"values":["PRNG","NieMa"]}}` |

## Fakty z nagrania i prob na zywo (2026-10-15)

- **Duplikat MapServera przesuwa ostatni obiekt za pozycje N-1.** PRG A06
  (fixtury): `hits` 4, strony `COUNT=2` daja 2+2+1 = 5 wierszy, 4. unikalny
  obiekt dopiero na `STARTINDEX=4`; strony "do pokrycia N pozycji" (0 i 2)
  daja 3 unikalne - falszywy blad. PRG A03 w `BBOX=220000,550000,270000,590000`
  (N,E): `hits` 39; `COUNT=10` - strony 0/10/20/30 = 40 wierszy, duplikat
  w wierszach 19/20 (koniec strony 10, poczatek strony 20), strony 10 i 30
  bez `next`, strona 40 pusta; `COUNT=13` - duplikat w wierszach 25/26,
  39. unikalny obiekt na `STARTINDEX=39` (strona z `numberMatched="40"`);
  `COUNT=5` - duplikat 19/20. Strony `GetFeature` maja `numberMatched="unknown"`
  poza ostatnia (liczba wierszy strumienia z duplikatem). Silnik: strony od 0
  co `page_size`, koniec przy N unikalnych; za N pozycji tylko dopoki
  poprzednia strona byla pelna i dodala nowe id.
- **`hits` nie zawyza N.** PRG A02, `BBOX=243000,565000,245000,567000`
  (Krakow): `hits` 1; `COUNT=1` `STARTINDEX=0` i `=1` zwracaja ten sam powiat,
  `STARTINDEX=2` - 0; `COUNT=1000` - 1 obiekt (`numberMatched="1"`).
- **Pusty obszar:** `hits` = `numberMatched="0"` (PRG A03/A06 i EGiB budynki
  na Baltyku), a strona `GetFeature` tego obszaru `numberMatched="unknown"`.
- **Zamiana osi bez bledu:** PRG A03 z bboxem E,N daje 21 obiektow (inny
  obszar), HY-NET z Y,X - 0.
- **Identyfikatory:** obiekty PRG nie maja `gml:id` (komentarz MapServera "No
  featureid defined"; `gml:id=".1"` maja geometrie) - GDAL daje puste
  `gml_id`, klucz `IIP_IDENTY`; duplikat PRG jest identyczny (pola i bajty
  WKB). EGiB: `gml:id` = `dzialki.<ID_DZIALKI>` / `budynki.<ID_BUDYNKU>`.
- **EGiB `DATA` zalezy od powiatu**, nie tylko od chwili odpowiedzi:
  Warszawa (1465) `2026-10-14`, Krakow (1261) i powiat 1415 `2026-10-15`
  (wszystko pobrane 2026-10-15). `budynki` nie maja pola `DATA`.
- **EGiB bez krzywych:** 80 stron z 40 losowych bboxow 400 x 400 m (dzialki
  i budynki, `COUNT=200`), 8 miast i 1000 dzialek Krakowa - tylko
  `gml:Polygon`/`gml:LinearRing`; GDAL 3.12.4 z XSD typuje warstwy jako
  `Polygon` (nie `CurvePolygon`). Obiekty wieloczesciowe to powtorzone
  elementy `<ms:geom>` (1 z 80 stron probki: 41 obiektow, 42 geometrie;
  budynek z fixtury) - bez `GML_FETCH_ALL_GEOMETRIES=YES` GDAL zostawia
  tylko ostatnia czesc.
- **GDAL bez sieci:** strony PRG i EGiB czytane z `XSD=<schemat>`,
  `WRITE_GFS=NO`, `DOWNLOAD_SCHEMA=NO` daja ten sam wynik w przestrzeni bez
  sieci (`unshare -rn`). Schemat HY-NET to tylko `xsd:include` zdalnego
  schematu INSPIRE - GDAL pobiera go, gdy ma siec (ok. 0,5 s), bez sieci
  odczytuje pola z dokumentu.
- **GPKG tylko na dysku lokalnym:** zapis SQLite na sieciowym wolumenie
  danych konczy sie bledem `Failed to start transaction`.
- **Deterministyczne bajty na zywo:** PRG A06 z `page_size` 1000 i 2 dal ten
  sam GPKG (ten sam sha256); powtorne pobrania PRG, EGiB (Warszawa) i RUIAN -
  te same bajty.

## Fakty z nagrania OGC API (2026-10-16)

- **Kazde zapytanie `items` PRNG trwa 78-95 s, niezaleznie od `limit`**
  (`limit=1`: 78,5 s; `limit=5`: 79,6-94,8 s; pomiar planu E: 73-93 s,
  `limit=10000` przyjety). `/collections` i blad nieznanej kolekcji - ponizej
  0,4 s. 6 rownoleglych zapytan `items` (5 bboxow Krakowa i Baltyk) skonczylo
  sie razem po 92,6-94,8 s: usluga nie kolejkuje zapytan. Dlatego silnik nie
  pyta osobno o liczbe: N = `numberMatched` pierwszej strony.
- **OGC API PRG jest szybkie:** `.../PRG/apiFeatures/collections/SadRejonowy/items`
  z tym samym `bbox` i `limit=2` - 3,5 s (1 obiekt `MultiPolygon`, `id` =
  `ID-<uuid>`, pole `powierzchnia` typu float); `/collections` PRG - 51
  kolekcji w 0,58 s (6 granic administracyjnych `Granica{Panstwa,...}` i 45
  innych), `crs` kazdej tylko CRS84.
- **Link `next`** ma schemat i host uslugi, parametry `f`, `offset`, `limit`,
  `bbox` (przecinki niekodowane, `bbox` jak w zapytaniu); ostatnia strona ma
  `previous`, nie ma `next`. `numberMatched` jest na kazdej stronie.
- **Obiekty PRNG:** `id` GeoJSON = `ID-<idPRNG>` (napis; ten sam w
  `idLokalny`), `idPRNG` - liczba calkowita, reszta pol - napisy albo `null`
  (np. `nazwaOboczna` `null` we wszystkich 9); geometria `MultiPoint` z jednym
  punktem lon,lat. Pole `timeStamp` (chwila odpowiedzi) jest poza
  `properties`.
- **Uklad:** wyjscie tylko CRS84 (lista `crs` kolekcji). GPKG zapisany przez
  GDAL 3.12.4 z `crs="OGC:CRS84"` ma wlasny SRS (`srs_id` 100000, WKT
  z `AUTHORITY["OGC","CRS84"]`).
- **Silnik na zywo:** `fetch_features` (`page_size=5`, bbox Krakowa jw.) -
  `/collections` i 2 strony `items` w 190,8 s; GPKG z 9 nazwami
  (`MultiPoint`, CRS84).
