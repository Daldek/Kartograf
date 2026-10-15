# Prawdziwe odpowiedzi ZABAGED (ArcGIS REST) i HY-NET (WFS) dla planu D (2026-10-15)

Nagrane 2026-10-15 przez `requests` z naglowkiem `User-Agent: kartograf/...`
(surowe odpowiedzi w `<katalog-danych>`). Obok kazdej odpowiedzi
`<plik>.headers.json` (kod HTTP, `Content-Type`; konwencja
`tests/conftest.py::recorded_response`). Strony GeoJSON ZABAGED zapisane jako
`*.json.gz` (cala odpowiedz, gzip `mtime=0`). Bez edycji. RUIAN (warstwa 12)
i `GetCapabilities` HY-NET pochodza z planu C: `tests/fixtures/pl/feature_bbox/`.

Obszar wszystkich zapytan (EPSG:5514, X,Y): `BB = -451000,-1112000,-450500,-1111500`
(Cesky Tesin, 500 x 500 m).

| Plik | Zapytanie | Wynik |
|---|---|---|
| `zabaged_pjson.json` | `ZABAGED_POLOHOPIS/MapServer?f=pjson` | 149 warstw, `maxRecordCount` 2000, ArcGIS 11.5 |
| `zabaged_l{93,132,138}_info.json` | `/<id>?f=json` | warstwy `Vodní tok` (linie), `Vodní plocha`, `Orná půda a ostatní dále nespecifikované plochy`; pola `OBJECTID`, `fid_zbg`, ... |
| `zabaged_l{93,132,138}_b5_count.json` | `/<id>/query?geometry=BB&geometryType=esriGeometryEnvelope&inSR=5514&spatialRel=esriSpatialRelIntersects&returnCountOnly=true&f=json` | 2 / 0 / 3 |
| `zabaged_l93_b5_r2_o0.json.gz`, `zabaged_l138_b5_r2_o{0,2}.json.gz` | jw. + `outSR=5514&outFields=*&orderByFields=OBJECTID&resultOffset=<o>&resultRecordCount=2&returnGeometry=true&f=geojson` | 2 / 2 + 1 obiekty |
| `hynet_{watercourselink,hydronode,crossing}_describe.xsd` | `hy-n/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=DescribeFeatureType&TYPENAMES=hy-n:<typ>` | **tylko `xsd:include`** zdalnego `HydroNetwork.xsd` INSPIRE |
| `hynet_*_b5_hits.xml` | `REQUEST=GetFeature&TYPENAMES=hy-n:<typ>&SRSNAME=urn:ogc:def:crs:EPSG::5514&BBOX=BB,urn:ogc:def:crs:EPSG::5514&RESULTTYPE=hits` | WatercourseLink 3, HydroNode 1, WatercourseSeparatedCrossing 0 |
| `hynet_*_b5_c2_s<start>.xml` | jw. bez `RESULTTYPE`, `COUNT=2&STARTINDEX=<start>` | WatercourseLink 2 + 1 (strona 2 ma **mylacy `next`** `http://...STARTINDEX=4`), HydroNode 1, crossing 0 |

## Fakty z nagrania i prob na zywo (2026-10-15)

- HY-NET (GeoServer) odpowiada na zapytanie z domyslnym `User-Agent` curl
  przekierowaniem 302 na `Dokumenty/Podminky.pdf`; z `kartograf/...`,
  `python-requests` albo przegladarkowym - dane.
- GDAL czyta strony HY-NET tak samo z XSD (wtedy pobiera schemat INSPIRE,
  0,3-0,4 s na strone) i bez XSD - pola z dokumentu. Pusty typ
  (`WatercourseSeparatedCrossing`, 0 obiektow) nie otwiera sie wcale
  (`DataLayerError`). Pola zaleza od tresci strony: strona z 1 wezlem nie ma
  `hydroNodeCategory`, strony po 1000 wezlow - maja. Na obszarze 30 x 30 km
  (`-470000,-1130000,-440000,-1100000`) wszystkie 4 strony WatercourseLink
  i HydroNode mialy te same pola.
- RUIAN warstwy 17/15/12/7 (`VyssiUzemneSamospravnyCelek`, `Okres`, `Obec`,
  `KatastralniUzemi`): pola `objectid` i `kod`; obszar 30 x 30 km: 1 / 3 / 68
  / 126 obiektow.
- Pliki krajowe: RUIAN `shp/stat/epsg-5514/1.zip` 253 018 058 B (`ETag`,
  `Last-Modified` 2026-10-15; 61 czlonow w katalogu `1/`), HY-NET
  `HY-NET.zip` 194 208 037 B (`ETag`, czlon `HY-NET/HY-NET.gpkg`).

Testy: `tests/test_collections_cz.py`.
