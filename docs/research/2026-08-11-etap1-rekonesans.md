# Rekonesans live CUZK + pyproj (etap 1, zadanie 1)

**Data:** 2026-08-11
**Zakres:** weryfikacja na zywo faktow niedomknietych w specu etapu 1 (sekcja 12), PRZED kodowaniem.
**Baza porownawcza:** `docs/research/2026-08-10-czechy-dmr-zabaged.md`
**Fixtury:** `tests/fixtures/cuzk/*.json` — zapisane bajt w bajt z odpowiedzi serwera, bez modyfikacji.

Legenda: **POTWIERDZONE** = zgodne z researchem/oczekiwaniem briefu; **ODCHYLENIE** = inaczej niz
zakladano; **DO ZMIANY** = konsekwencja dla pozniejszych zadan.

---

## Krok 1 — Metadane warstw 24 / 26 (`KladyMapovychListu/MapServer`)

Fixtury: `klady_layer24_meta.json`, `klady_layer26_meta.json` (HTTP 200).

| Fakt | Warstwa 24 (SM5 / S-JTSK) | Warstwa 26 (DMR,DMP / ETRS89) |
|---|---|---|
| `name` | `Klad listů SM 5 (Ortofoto ČR, DMR, DMP)/S-JTSK` | `Klad listů DMR, DMP/ETRS89` |
| `type` / `geometryType` | Feature Layer / `esriGeometryPolygon` | Feature Layer / `esriGeometryPolygon` |
| **`maxRecordCount`** | **2000** | **2000** |
| `extent.spatialReference` | `wkid=102067`, `latestWkid=5514` | `wkid=102067`, `latestWkid=5514` |
| `supportsPagination` | `true` | `true` |
| `supportsOrderBy` | `true` | `true` |
| `supportedQueryFormats` | `JSON, geoJSON, PBF` | `JSON, geoJSON, PBF` |
| `capabilities` | `Map,Query,Data` | `Map,Query,Data` |
| `objectIdField` | `null` (pole OID nazywa sie `OBJECTID`) | `null` (pole OID nazywa sie `OBJECTID`) |

Pola (nazwy **wielkimi literami**, dokladnie jak nizej):

- **w. 24:** `OBJECTID` (OID), `Shape`, `ID` (Double), `MAPNAME` (String), `MAPNAME_UC` (String),
  **`MAPNOM` (String)**, **`PODIL` (Double)**, `Shape_Length`, `Shape_Area`
- **w. 26:** `OBJECTID` (OID), `Shape`, `ID` (Integer), `KM10_ID` (Integer), **`MAPNOM` (String)**,
  `KM2_NUM` (Integer), **`IN_CZ` (String, dlugosc 8)**, `Shape_Length`, `Shape_Area`

**POTWIERDZONE:** `maxRecordCount = 2000`; obecnosc `MAPNOM`/`MAPNAME`/`PODIL` (w. 24) i
`MAPNOM`/`IN_CZ` (w. 26); nazwy pol wielkimi literami (research trafil).

**ODCHYLENIE (drobne):**
1. `IN_CZ` to **String**, nie flaga liczbowa/boolean.
2. **Obie warstwy** maja natywny SR **5514** (`wkid=102067`) — takze warstwa 26 "ETRS89".
   Geometrie kafli TM33 sa w bazie przechowywane w Krovaku. Ma to konsekwencje (krok 3).
3. W. 24 ma dodatkowe pole `MAPNAME_UC` (nazwa wersalikami) — nieuzywane, ale istnieje.
4. W. 26 ma dodatkowe pola `KM10_ID`, `KM2_NUM`.

**DO ZMIANY (Zad. 8, 10):** `PAGE_SIZE`/`resultRecordCount` = 2000. `orderByFields` jest wspierane
(`supportsOrderBy: true`) — warto go uzywac przy paginacji, bo bez `ORDER BY` kolejnosc stron w
ArcGIS nie jest gwarantowana. Zweryfikowane, ze `orderByFields=MAPNOM ASC` dziala (zwrocilo
`AS00, AS01, AS02`).

---

## Krok 2 — `where=MAPNOM='CTES96'` (walidacja godla SM5)

Fixtura: `klady_sm5_where_ctes96.json` (HTTP 200, 763 B).

Ksztalt odpowiedzi (klucze najwyzszego poziomu):
`displayFieldName`, `fieldAliases`, `geometryType`, `spatialReference`, `fields`, `features`.

- `spatialReference`: `{"wkid": 102067, "latestWkid": 5514}` — **serwer zwraca `wkid=102067`,
  a EPSG:5514 tylko w `latestWkid`**.
- 1 feature, `attributes` = `{"MAPNOM": "CTES96", "MAPNAME": "Český Těšín 9-6", "PODIL": 0.99}`
- `geometry` ma wylacznie klucz `rings`; 1 pierscien, 5 punktow (prostokat domkniety).
- Zasieg arkusza: X od `-450000` do `-447500`, Y od `-1114000` do `-1112000`
  => **arkusz SM5 = 2500 m (X) x 2000 m (Y)**.

Nieistniejace godlo (`MAPNOM='XXXX99'`): HTTP **200**, pelna koperta z `fields`/`fieldAliases`,
`"features": []`. **Nie ma bledu HTTP ani obiektu `error`** — pusta lista to jedyny sygnal.

**POTWIERDZONE:** 1 feature; `MAPNOM == "CTES96"`; `geometry.rings`; nieistniejace godlo => `features: []`.

**ODCHYLENIE:**
1. **`PODIL` = 0.99, a nie ~0.5.** Brief zakladal, ze CTES96 to arkusz przygraniczny w ~polowie
   poza CZ — nieprawda, CTES96 lezy niemal w calosci w CZ. (Weryfikacja: plik `CTES96.tif` z openzu
   ma tylko 161 pikseli `-9999` na 200 000 = 0,08 %.)
2. **`MAPNAME` = `Český Těšín 9-6`, a nie `Cesky Tesin 8-6`.** Research (sekcja 6.3) blednie
   sparowal `CTES86` <-> `Cesky Tesin 8-6` z kodem `CTES96`. Regula faktyczna:
   `MAPNOM` = 4 litery nazwy miasta + **cyfra kolumny** + **cyfra wiersza**, zgodne z sufiksem
   `MAPNAME`: `CTES86` -> `Český Těšín 8-6`, `CTES96` -> `Český Těšín 9-6`.
3. **`MAPNAME` zawiera czeskie diakrytyki (UTF-8)** — `Český Těšín`, `Bohumín`. Odpowiedz jest
   UTF-8, ale ArcGIS **nie deklaruje charsetu** w `Content-Type` konsekwentnie.

**DO ZMIANY (Zad. 8, 10):**
- Klient MUSI wymuszac `response.encoding = "utf-8"` (albo parsowac `response.content`), inaczej
  `requests` zgadnie latin-1 i `MAPNAME` bedzie zepsute.
- Walidacja godla SM5: `features == []` => `ValidationError` (a nie blad HTTP).
- W sidecarze/normalizacji nie zakladac ASCII w `MAPNAME`.

---

## Krok 3 — Zapytania bbox warstw 24 i 26

Fixtury: `klady_sm5_bbox.json` (13 features), `klady_tm33_bbox.json` (1 feature),
`klady_tm33_bbox_oversel.json` (9 features — fixtura dodana ponad brief, uzasadnienie nizej).

Parametry z briefu **dzialaja bez zmian** — `geometry` jako `xmin,ymin,xmax,ymax` w formie
skroconej (CSV), `geometryType=esriGeometryEnvelope`, `inSR`, `spatialRel`, `outFields`,
`returnGeometry`, `outSR`. Forma `geometry` jako obiekt JSON tez dziala i daje identyczny wynik.

### 3a. `exceededTransferLimit`

**Klucz pojawia sie TYLKO gdy sa dalsze wyniki; przy komplecie jest CALKOWICIE NIEOBECNY**
(nie `false`). Zweryfikowane:

| Zapytanie | features | `exceededTransferLimit` |
|---|---|---|
| bbox w. 24 (13 arkuszy) | 13 | **brak klucza** |
| bbox w. 26 (1 kafel) | 1 | **brak klucza** |
| `where=1=1` w. 24 (16 299 arkuszy) | 2000 | **`true`** |
| `where=1=1` + `resultRecordCount=5`, `resultOffset=0` | 5 | **`true`** |
| `where=1=1` + `resultRecordCount=5`, `resultOffset=5` | 5 | **`true`** |

Paginacja `resultOffset` / `resultRecordCount` dziala (strona 2 zwrocila inne obiekty niz strona 1).
`returnCountOnly=true` dziala: w. 24 => **16 299**, w. 26 => **20 308**.

**ODCHYLENIE:** research podawal 16 301 arkuszy SM5 (liczba `<entry>` w feedzie ATOM); usluga
indeksu zwraca **16 299**. Roznica 2 — nie badana, ale nie wolno zakladac rownosci feed <-> indeks.
Liczba kafli TM33 (20 308) zgadza sie dokladnie.

**DO ZMIANY (Zad. 8):** warunek petli paginacji to `data.get("exceededTransferLimit") is True`
(lub `bool(...)`), **nigdy** `data["exceededTransferLimit"]` — klucza zwykle nie ma.

### 3b. NADMIAROWY WYBOR — najwazniejsze ustalenie kroku

**`spatialRel=esriSpatialRelIntersects` zwraca takze arkusze, ktore z kopertą stykaja sie tylko
krawedzia lub narozem, oraz (dla `inSR` != natywnego 5514) arkusze faktycznie NIE przecinajace koperty.**

Dowod 1 — warstwa 24, koperta `-450000,-1105000,-440000,-1095000` (`klady_sm5_bbox.json`):
z 13 zwroconych arkuszy **tylko 7 przecina koperte scisle**; 6 (`OSTR00`, `OSTR01`, `OSTR02`,
`BOHU07`, `BOHU08`, `BOHU09`) ma wschodnia krawedz dokladnie na `x = -450000` = `xmin` koperty,
czyli styka sie bez czesci wspolnej o dodatnim polu.

Dowod 2 — warstwa 26, koperta o rozmiarze **dokladnie jednego kafla**
(`744000,5534000,746000,5536000`, `inSR=3045`, fixtura `klady_tm33_bbox_oversel.json`):
zwrocono **9 kafli** (pelne sasiedztwo 3x3), z czego scisle przecina koperte **1**.

Dowod 3 — warstwa 26, koperta z briefu `744000,5540000,760000,5556000` (`inSR=3045`,
`klady_tm33_bbox.json`): zwrocono **1 kafel `744_5536`**, ktorego zasieg to
`744000..746000 / 5536000..5538000` — czyli **2 km na poludnie od `ymin` koperty; nie styka sie
z nia wcale**. Przyczyna: geometrie w. 26 sa natywnie w Krovaku (krok 1), wiec serwer reprojektuje
koperte 3045 -> 5514 i uzywa jej **obwiedni rownoleglej do osi** w Krovaku. Rotacja Krovaka
(ok. 7 stopni) rozdyma koperte o ~`sin(rot) * rozmiar` — dla 16 km daje to ~2 km halo.
Kontrola: koperta 16x16 km w srodku CZ (`460000,5540000,476000,5556000`, `inSR=3045`) zwrocila
**103 kafle** zamiast 64 scisle przecinajacych (100 = ring stykajacy 10x10, +3 z rotacji).

Uwaga: koperta z briefu lezy juz **poza terytorium CZ** (kolumna 744 konczy sie na `744_5536`;
`where=MAPNOM LIKE '744_55%'` daje kafle `744_5500`..`744_5536`). Fixtura jest wiec poprawnym
zapisem realnej odpowiedzi, ale jako przyklad "typowego" zapytania jest nietypowa — dlatego
dolozono `klady_tm33_bbox_oversel.json`, ktora pokazuje nadmiarowy wybor na kopercie w pelni
wewnatrz CZ.

**DO ZMIANY (Zad. 10 — kluczowe):** `SheetIndex` **musi filtrowac wynik po stronie klienta**:
odrzucac arkusze, ktorych zasieg nie przecina zadanej koperty **scisle** (bez stykania sie
krawedziami — zgodnie z konwencja `_bboxes_intersect()` z `core/sheet_parser.py`, ktora uzywa `<`).
Zasieg mozna wziac z `geometry.rings` (dlatego `returnGeometry=true` ma sens) albo — dla TM33 —
policzyc z `MAPNOM` przez `ParserTM33` (Zad. 6). Bez filtra dla malego bboxa pobierzemy 9x
za duzo danych.

### 3c. Pozostale obserwacje

- `outSR=3045` w odpowiedzi daje `spatialReference: {"wkid": 3045, "latestWkid": 3045}`
  (bez ESRI-owego aliasu), `outSR=5514` daje `{"wkid": 102067, "latestWkid": 5514}`.
- Wspolrzedne w `rings` maja bledy rzedu `1e-4` m (np. `-449999.999308413`) — to artefakt
  siatkowania ArcGIS. **Porownania zasiegow musza byc z tolerancja**, nie na rownosc.
- **`IN_CZ` ma tylko jedna wartosc rozna: `"CZ"`** (`returnDistinctValues=true` na w. 26 =>
  jeden rekord `{"IN_CZ": "CZ"}` dla wszystkich 20 308 kafli). **`IN_CZ` nie jest dyskryminatorem** —
  warstwa 26 zawiera wylacznie kafle w CZ. Nie budowac na nim logiki filtrowania (Zad. 10).
- W. 24 ma za to `PODIL` z realnym rozrzutem (`0.04`, `0.17`, `0.19`, `0.22`, `0.25`, `0.28`,
  `0.3`, `0.44`, `0.58`, `0.81`, `0.99`, `1`) — to jest wlasciwy wskaznik "ile arkusza jest w CZ".

---

## Krok 4 — `exportImage` z `noData` (dmr5g i dmr4g)

Koperta `-447000,-1114000,-446000,-1113000` (SR 5514) — obszar przygraniczny; wg indeksu
przecinaja go arkusze `CTES86` (`PODIL` 0,19) i `CTES87` (`PODIL` 0,28).

| | dmr5g | dmr4g |
|---|---|---|
| HTTP / `Content-Type` | 200 / `image/tiff` | 200 / `image/tiff` |
| rozmiar odpowiedzi | 722 390 B | 132 470 B |
| poprawny TIFF | tak (500x500, float32) | tak (200x200, float32) |
| **`nodata` w GeoTIFF** | **`-9999.0`** | **`-9999.0`** |
| `min` / `max` | `-9999.0` / `292.579` | `-9999.0` / `292.455` |
| pikseli `-9999` | 120 842 / 250 000 = **48,3 %** | 19 315 / 40 000 = **48,3 %** |
| pikseli `== 0` | **0** | **0** |
| `NaN` | 0 | 0 |
| `bounds` | dokladnie zadana koperta | dokladnie zadana koperta |
| `res` | (2,0; 2,0) | (5,0; 5,0) |
| `tags()` | `{'DataType': 'Generic', 'AREA_OR_POINT': 'Area'}` | jw. |

**POTWIERDZONE:**
1. **`dmr4g/ImageServer/exportImage` DZIALA** — fallback ze specu (DMR4G tylko plikowo,
   `--resolution 5m` w trybie bbox => `ValidationError`) **NIE jest potrzebny**.
2. **Obszar poza CZ = `-9999`, nie 0.** To poprawka wzgledem researchu (sekcja 4.2: "obszary poza
   terytorium CZ wypelniane sa zerami") — zera pojawialy sie tam, gdzie *nie* podano `noData`;
   z `noData=-9999&noDataInterpretation=esriNoDataMatchAny` serwer wypelnia `-9999`.
3. **Tag `nodata` w GeoTIFF JEST ustawiany przez serwer** (`src.nodata == -9999.0`) — dodatkowy
   krok "dopisz nodata w trybie `r+`" w Zad. 9 **nie jest wymagany dla poprawnosci**.

**ODCHYLENIE — powazne (CRS):**

`src.crs` dla `imageSR=5514` to:

```
LOCAL_CS["S-JTSK / Krovak East North",UNIT["metre",1,AUTHORITY["EPSG","9001"]],
         AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","5514"]]
```

To **`LOCAL_CS` (uklad lokalny/inzynierski), nie `PROJCS`**. Skutki zmierzone:
- `src.crs.to_epsg()` => **`None`**
- `src.crs.is_projected` => **`False`**, `is_geographic` => `False`
- `src.crs.linear_units` => `'unknown'`

Czyli **GeoTIFF z `exportImage` w 5514 jest bezuzyteczny do reprojekcji przez GDAL/rasterio bez
recznego nadpisania CRS**. To ten sam problem, co opisany w researchu 7.3 dla plikow DMR4G-TIFF
(`crs = None`), tylko w innej postaci.

**DO ZMIANY (Zad. 9):** po pobraniu `exportImage` **zawsze** nadpisac CRS jawnie
(`rasterio.open(..., "r+")` i `dst.crs = CRS.from_epsg(<imageSR>)`). Krok jest wymagany
**nie dla `nodata` (ten jest OK), tylko dla CRS**. Dotyczy 5514 i 3045 (patrz krok 5).

**Metadane uslug ImageServer** (`?f=json`, zebrane dodatkowo — konieczne do kafelkowania w Zad. 9):

| | dmr5g | dmr4g |
|---|---|---|
| `pixelType` / `bandCount` | `F32` / 1 | `F32` / 1 |
| `pixelSizeX/Y` | **2 / 2** | **5 / 5** |
| **`maxImageWidth` / `maxImageHeight`** | **15000 / 4100** | **15000 / 4100** |
| `spatialReference` | `wkid=102067`, `latestWkid=5514`, **`vcsWkid=8357`**, `latestVcsWkid=8357` | jw. |
| `minValues` / `maxValues` | 9,76 / 1603,58 | 9,76 / 1603,27 |
| `noDataValue` | `null` | `null` |
| `capabilities` | `Catalog,Mensuration,Image,Metadata` | jw. |

**DO ZMIANY (Zad. 9):** limit jest **asymetryczny** — 15000 px szerokosci, ale tylko
**4100 px wysokosci**. Kafelkowanie musi liczyc oba wymiary osobno (nie jeden kwadratowy limit).
`noDataValue` uslugi to `null`, wiec parametr `noData` w zadaniu jest **obowiazkowy** — bez niego
dostaniemy zera (jak w researchu).

`vcsWkid = 8357` potwierdza natywny uklad wysokosciowy **Bpv** — zgodnie z researchem.

---

## Krok 5 — `exportImage` kafla TM33 w 3045

> **Adnotacja (2026-08-18):** tresc odpowiedzi serwera przy `imageSR=3045` miala pozniej zmierzone przesuniecie 1,25-4,92 m wzgledem natywnej referencji 5514 (ADR-024); werdykty tego kroku pozostaja wazne w zakresie, ktory kontrolowaly (bounds/CRS/rozmiar).

Koperta `302000,5550000,304000,5552000`, `bboxSR=3045`, `imageSR=3045`, `size=1000,1000`.

- HTTP 200, `image/tiff`, 525 979 B.
- `bounds` = **`(302000.0, 5550000.0, 304000.0, 5552000.0)`** — dokladnie jak zadano.
  **Kolejnosc `bbox` to E,N (`xmin,ymin,xmax,ymax`)** mimo ze EPSG:3045 ma oficjalnie osie N,E.
- `res` = **(2,0; 2,0)** — zgodnie z oczekiwaniem.
- `nodata` = **`-9999.0`**; 935 278 / 1 000 000 pikseli = 93,5 % to `-9999`, `max` = 475,60,
  pikseli `== 0`: **0**.
- `src.crs` to poprawny **`PROJCS`**:
  `PROJCS["ETRS89 / UTM zone 33N (N-E)", ... AUTHORITY["EPSG","3045"]]`, z parametrami TM
  (`central_meridian=15`, `scale_factor=0.9996`, `false_easting=500000`) i
  `AXIS["Easting",EAST], AXIS["Northing",NORTH]`.

**POTWIERDZONE:** bounds, `res` (2,2), `nodata`, brak zer.

**ODCHYLENIE:**
1. **`src.crs.to_epsg()` => `None`** takze tutaj, mimo poprawnego `PROJCS` z `AUTHORITY["EPSG","3045"]`.
   Powod: WKT nazywa uklad `"(N-E)"`, ale deklaruje osie `Easting EAST, Northing NORTH` —
   wewnetrzna sprzecznosc, przez ktora GDAL nie dopasowuje kodu EPSG. `is_projected` = `True`
   (w odroznieniu od 5514, gdzie `LOCAL_CS` daje `False`).
2. Kafel `302_5550` **istnieje** w w. 26 (`IN_CZ='CZ'`), ale lezy przy zachodniej granicy z Niemcami —
   stad 93,5 % `noData`. Do testow "kafel z danymi" lepiej wybrac kafel ze srodka kraju.

**DO ZMIANY (Zad. 9):** wniosek z kroku 4 obowiazuje **dla obu SR** — CRS nadpisujemy zawsze,
bo `to_epsg()` nie zwraca kodu ani dla 5514 (`LOCAL_CS`), ani dla 3045 (niedopasowany `PROJCS`).
Sprawdzanie "czy plik ma juz dobry CRS" przez `to_epsg()` **nie zadziala**.

---

## Krok 6 — Zachowanie HTTP `openzu`

`HEAD https://openzu.cuzk.gov.cz/opendata/DMR4G-TIFF/epsg-5514/CTES96.zip`:

```
HTTP/1.1 200 OK
Content-Length: 752795
Content-Type: application/x-zip-compressed
Last-Modified: Mon, 19 Jan 2026 14:10:33 GMT
Accept-Ranges: bytes
ETag: "d19f2c604d89dc1:0"
SRV: OD2
Strict-Transport-Security: max-age=15555000
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
X-Frame-Options: SAMEORIGIN
```

- **Brak przekierowan** (`num_redirects: 0`, `-L` konczy na tym samym URL, kod 200).
- **`Accept-Ranges: bytes`** — zweryfikowane realnie: `curl -r 0-99` => **HTTP 206**, 100 B.
- `Content-Type` to `application/x-zip-compressed` (nie `application/zip`).
- Nieistniejacy arkusz (`XXXX99.zip`): **HTTP 404**, cialo to **strona HTML IIS**
  (`<title>404 - File or directory not found.</title>`, `charset=iso-8859-1`).

**POTWIERDZONE:** 404 dla nieistniejacego arkusza; obecnosc `Content-Length` i `Accept-Ranges`.

**DO ZMIANY (Zad. 8, 12):**
- 404 => `DownloadError`/`ValidationError`; **nie parsowac ciala jako ZIP** (to HTML).
- Walidacja typu: sprawdzac `Content-Type` startujacy od `application/` i **magic ZIP `PK\x03\x04`**,
  a nie rowność `application/zip`.
- `Accept-Ranges: bytes` + `ETag` + `Last-Modified` sa dostepne — wznawianie/warunkowe pobieranie
  jest mozliwe, ale nie jest wymagane w etapie 1.

**Zawartosc ZIP (sprawdzone dodatkowo — bezposrednie wejscie dla Zad. 8):**

```
CTES96.tfw      92 B
CTES96.tif  779970 B
```

- `CTES96.tif`: **`crs = None`** (potwierdza research 7.3), `nodata = -9999.0` (**jest ustawione**),
  `float32`, `500 x 400` px, `res` (5,0; 5,0), po zaczytaniu `.tfw`
  `bounds = (-450000, -1114000, -447500, -1112000)` — zgodne co do metra z geometria `CTES96`
  z warstwy 24. Pikseli `-9999`: **161 / 200 000** (0,08 %, zgodne z `PODIL = 0.99`).
- `CTES96.tfw`: `5.0 / 0 / 0 / -5.0 / -449997.5 / -1112002.5` (srodek lewego-gornego piksela).
- Brak `.prj` w archiwum.

**DO ZMIANY (Zad. 8):** po rozpakowaniu trzeba **rozpakowac oba pliki obok siebie** (rasterio czyta
`.tfw` automatycznie tylko gdy lezy przy `.tif`) i **jawnie przypisac EPSG:5514** — bo `crs = None`.
`nodata` w pliku juz jest, nie trzeba dopisywac.

---

## Krok 7 — Semantyka pyproj dla 8357 -> 5621

Wykonane w `.venv` przez istniejacy `kartograf.transform.crs.build_pinned_transform` —
**import i sygnatura zgadzaja sie z briefem** (`build_pinned_transform(src, dst, TransformPolicy(...))`,
atrybuty `.description`, `.accuracy_m`, `._transformer`).

```
op: Baltic 1957 height to EVRF2007 height (1)   accuracy_m: 0.1
skalar: p.transform(18.62, 49.75, 300.0) -> (18.62, 49.75, 300.1276632676322)
tablice: p._transformer.transform(xs, ys, zs)
         -> (array([18.62, 14.5]), array([49.75, 50.9]), array([300.12766327, 300.14378672]))
area_of_use: Czechia, bounds (12.09, 48.58, 18.86, 51.06)
```

**POTWIERDZONE:** operacja `Baltic 1957 height to EVRF2007 height (1)`, `accuracy_m = 0.1`,
offset `+0,1277 m` dla punktu przy Cieszynie (mieści sie w oczekiwanym `+0,117..+0,143`),
wywolanie tablicowe na `_transformer` dziala i zwraca `numpy.ndarray`.

### 7a. Kolejnosc argumentow

**`always_xy=True` jest ustawione** (`crs.py:128`: `TransformerGroup(src, dst, always_xy=True,
allow_ballpark=False)`), wiec kolejnosc to **`(lon, lat, h)`** — najpierw dlugosc geograficzna.

**PULAPKA:** zamiana argumentow **nie powoduje bledu** — zwraca cichy zly wynik:

| wywolanie | wynik z |
|---|---|
| `p.transform(18.62, 49.75, 300.0)` (lon, lat) | `300.1277` (offset **+0,128**) |
| `p.transform(49.75, 18.62, 300.0)` (lat, lon) | `299.6912` (offset **-0,309**) |

Blad ~0,44 m — wiecej niz dokladnosc DMR 5G (0,18 m), a nic nie sygnalizuje pomylki.

### 7b. Wielkosc i kierunek offsetu

Offset zalezy **wylacznie od szerokosci geograficznej** i jest liniowy; od dlugosci **nie zalezy w ogole**:

| lat (przy lon=15,0) | offset |
|---|---|
| 48,6 (pd. granica CZ) | **+0,11154 m** |
| 49,0 | +0,11715 m |
| 49,5 | +0,12416 m |
| 50,0 | +0,13117 m |
| 50,5 | +0,13818 m |
| 51,0 | +0,14519 m |
| 51,2 (pn. granica CZ) | **+0,14799 m** |

Przy `lat = 49,9` staly offset `+0,12977 m` dla **kazdego** `lon` z zakresu 12,1..18,9.

**POTWIERDZONE:** offset **rosnie z poludnia na polnoc**, gradient **~+0,01402 m / stopien
szerokosci**; zakres na terytorium CZ: **+0,112 .. +0,148 m** (research podawal +0,117..+0,143 —
zgodne co do rzedu, faktyczny zakres jest odrobine szerszy na krancach kraju).

### 7c. Brak ochrony poza obszarem uzycia

Transformacja **nie zwraca `inf`/`NaN` poza `area_of_use`**, tylko ekstrapoluje po cichu:

- Warszawa (`21.0, 52.2, 300.0`) => `300.1620` (offset +0,162) — punkt jest poza CZ, a wynik jest skonczony.
- `(0.0, 0.0, 300.0)` => `299.4301` — nadal skonczony.

**DO ZMIANY (Zad. 5, 12):** kontrola zasiegu jest **nasza** odpowiedzialnoscia — mechanizm `probe`
z `crs.py` odrzuca operacje siatkowe zwracajace `inf` (przypadek `sk_gku`), ale **nie chroni przed
ekstrapolacja** operacji bezsiatkowych. Jesli to istotne, walidowac bbox wzgledem
`transformer.area_of_use` przed uzyciem.

### 7d. `PinnedTransform.transform` nie przyjmuje tablic — potwierdzenie potrzeby Zad. 5

```
p.transform(np.array([18.62, 14.5]), np.array([49.75, 50.9]), np.array([300.0, 300.0]))
=> TypeError: only 0-dimensional arrays can be converted to Python scalars
```

Przyczyna (`crs.py:67`): `if not all(math.isfinite(v) for v in result)` — `math.isfinite`
na `numpy.ndarray` rzuca `TypeError`. Sam `_transformer.transform` z tablicami dziala bez zarzutu
(dlatego brief uzywa `p._transformer`).

**DO ZMIANY (Zad. 5):** `PinnedTransform.transform` ma byc polimorficzny — wykrywac tablice
i uzywac `numpy.isfinite(...).all()` zamiast `math.isfinite` (a sygnature rozszerzyc poza `float`).

---

## Podsumowanie — co trafia do ktorego zadania

| Zadanie | Ustalenie |
|---|---|
| **Zad. 5** | `PinnedTransform.transform` pada na `numpy` (`math.isfinite`) — 7d. Kolejnosc `(lon, lat, h)`, `always_xy=True` — 7a. Brak ochrony poza `area_of_use` — 7c. |
| **Zad. 6** | Kafel TM33 = 2x2 km, `MAPNOM = {E_km}_{N_km}` = naroznik SW; zweryfikowane na `744_5536`, `302_5550`, `744_5534`. Zakres kolumny 744: `5500..5536`. |
| **Zad. 8** | `maxRecordCount = 2000`; petla paginacji na `exceededTransferLimit is True` (klucz **nieobecny** = koniec); `orderByFields` wspierane; wymusic UTF-8 na odpowiedzi (diakrytyki w `MAPNAME`); openzu 404 => HTML (nie ZIP); ZIP zawiera `.tif` + `.tfw`, `crs = None` => przypisac EPSG:5514, `nodata` juz jest. |
| **Zad. 9** | `dmr4g exportImage DZIALA` (fallback niepotrzebny); `nodata` **jest** ustawiane przez serwer; **CRS trzeba nadpisac zawsze** (5514 => `LOCAL_CS`, 3045 => `PROJCS` bez dopasowania EPSG; `to_epsg()` = `None` w obu); limit kafelkowania **15000 x 4100** (asymetryczny); parametr `noData` obowiazkowy (`noDataValue` uslugi = `null`); `bbox` w kolejnosci E,N takze dla 3045. |
| **Zad. 10** | Pola: `MAPNOM`, `MAPNAME`, `PODIL` (w. 24) / `MAPNOM`, `IN_CZ` (w. 26), wielkimi literami; `spatialReference` w odpowiedzi = `wkid 102067` / `latestWkid 5514`; **konieczny filtr po stronie klienta** — serwer zwraca arkusze stykajace sie krawedzia oraz (dla `inSR != 5514`) halo z reprojekcji Krovaka ~`sin(7 st.) * rozmiar`; `IN_CZ` ma jedna wartosc `'CZ'` => bezuzyteczny jako filtr; `PODIL` to wlasciwy wskaznik udzialu w CZ; nieistniejace godlo => HTTP 200 + `features: []`; wspolrzedne z bledem ~1e-4 m => porownania z tolerancja. |
| **Zad. 12** | Wysokosc: Bpv (`vcsWkid=8357`) -> EVRF2007 (5621), offset `+0,112..+0,148 m`, gradient `+0,0140 m/st. szerokosci`; kolejnosc `(lon, lat, h)`. |
| **Zad. 15 / 12** | **Nie** trzeba dodawac `ValidationError` dla `--resolution 5m` w trybie bbox CZ — `dmr4g/exportImage` dziala. |
| **Zad. 20 (E2E)** | Kafel `302_5550` to 93,5 % `noData` (granica z DE) — do testow "z danymi" wybrac kafel ze srodka kraju. Koperta TM33 z briefu (`744000,5540000,...`) lezy poza CZ. |

## Blednie zalozone fakty (korekty do wczesniejszego researchu / briefu)

1. `CTES96` **nie jest** arkuszem ~50 % poza CZ — `PODIL = 0.99`. Bbox przygraniczny z kroku 4
   (48,3 % `noData`) przecina `CTES86` (0,19) i `CTES87` (0,28).
2. `CTES96` to `Český Těšín` **9-6**, nie **8-6** (research 6.3).
3. Obszary poza CZ w `exportImage` **nie sa** wypelniane zerami, jesli podamy `noData` — sa `-9999`.
4. Liczba arkuszy SM5 w indeksie to **16 299**, nie 16 301.
5. `exportImage` **nie zwraca** CRS nadajacego sie do reprojekcji — to nie dotyczy tylko plikow
   z openzu (research 7.3), ale takze rastrow z ImageServera.
