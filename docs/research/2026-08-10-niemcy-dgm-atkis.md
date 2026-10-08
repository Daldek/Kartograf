# Research: dane wysokosciowe i pokrycia terenu dla Niemiec (BKG + landy)

**Data:** 2026-08-10
**Zakres:** NMT/NMPT (DGM/DOM) oraz odpowiednik BDOT10k (ATKIS Basis-DLM)
**Metoda:** weryfikacja na zywo (curl + rasterio + pyproj); 3 landy graniczne z Polska zbadane szczegolowo
**Legenda:** **[OK]** = potwierdzone realnym wywolaniem | **[DOC]** = tylko dokumentacja | **[FAIL]** = sprawdzone, nie dziala

---

## 1. Struktura dostawcow

Niemcy **nie maja odpowiednika GUGiK**. Dane produkuja landy; BKG jest agregatorem i "Zentrale Stelle Geotopographie" (ZSGT) dzialajacym w imieniu AdV — redystrybuuje dane landow, ale **glownie w malych skalach i czesto odplatnie**.

| Poziom | Produkt | Status | Dowod |
|---|---|---|---|
| BKG krajowy | DGM200, DGM1000 | **otwarty, darmowy** | [OK] pobrane |
| BKG krajowy | DLM250, DLM1000, CLC5, DTK100/1000, basemap.de | otwarty | [OK] katalog + WFS |
| BKG krajowy | **DGM1, DOM1** | **PLATNY, od 8 000 EUR** | [OK] `wcs_dgm1` -> HTTP 403 `NOACCESS_SERVICE`; metalink zawiera literalnie `wcs_dgm1__{{uuid}}` |
| BKG krajowy | DGM5, DGM25 | **"nur fuer Behoerden"** | [DOC] strona produktowa; brak w drzewie open data [OK] |
| Landy | DGM1/DOM1/LAZ | **open data, 16 roznych API** | [OK] BB/SN/MV |
| Wszystkie 16 landow | **ATKIS Basis-DLM** | **otwarty, zharmonizowany** | [OK] basemap.de |

**Kluczowy wniosek:** jednolity krajowy **otwarty** DGM1 **nie istnieje**. BKG *ma* krajowy DGM1 (kompletny, znormalizowany do strefy 32), ale za paywallem. Otwarty DGM1 trzeba brac osobno z kazdego landu.

**Wyjatek — ATKIS Basis-DLM jest zharmonizowany krajowo.** To najwazniejsze odkrycie tego researchu: `basemap.de` publikuje Basis-DLM **wszystkich 16 landow** w jednym modelu danych, **31 identycznych warstw**, jako GeoPackage per land **oraz** jako **OGC API Features po dowolnym bboxie dla calego kraju**. Odswiezane **codziennie** [OK] (pliki z datownikiem 2026-08-10, godz. 06:13-06:16).

### Landy graniczne — porownanie

| | **Brandenburgia** (LGB) | **Saksonia** (GeoSN) | **Meklemburgia-PP** (LAiV) |
|---|---|---|---|
| **WCS po bboxie** | **[OK] TAK** `bb_dgm` | **[FAIL] BRAK** (10+ nazw -> 403) | **[OK] TAK** `mv_dgm` |
| Kafle plikowe | 1x1 km ZIP | 2x2 km ZIP | 2x2 km |
| Rozdz. NMT | 1 m | 1 m | 1, 5, 25 m |
| NMPT | bDOM 1 m | DOM1 1 m | DOM1 + nDOM 1 m |
| LAZ | [OK] darmowy, **dziury** (13086/31291) | [OK] darmowy, ~16 pkt/m2 | **[FAIL] ALS platny (401)**; darmowy bDOM10 |
| Basis-DLM | **WFS po bboxie** (GML) | 1,23 GB ZIP (caly land) | 174 MB ZIP **+ WFS** |
| Licencja | **dl-de/by-2-0** | **dl-de/by-2-0** | **CC BY 4.0** |
| Hosting | Apache autoindex | **Nextcloud WebDAV** (tokeny!) | ATOM + `?dataset=` |

Rozrzut jest ogromny: trzy sasiadujace landy maja **trzy calkowicie rozne mechanizmy dostepu**, rozne licencje i rozne kladki kafli.

---

## 2. Produkty

| Produkt | Rozdz. | Dokladnosc H | Format | Zasieg | Cykl |
|---|---|---|---|---|---|
| **BKG DGM200** | 200 m | **+-3-10 m** (poz. +-5 m) | GeoTIFF float64 / GridASCII / XYZ | caly kraj, 1 plik | nieregularny |
| BKG DGM1000 | 1000 m | — | j.w. | caly kraj, 1 plik | nieregularny |
| BKG DGM1 | 1 m | — | GeoTIFF LZW float32 | caly kraj | nieregularny |
| BB DGM1 | 1 m | <= +-0,3 m [DOC] | GeoTIFF float32 LZW + XYZ | BB + Berlin, 31291 kafli | per kafel |
| SN DGM1 | 1 m | +-0,15 m [DOC] | GeoTIFF float32 LZW | Saksonia, 4989 kafli 2 km | ALS co **6 lat** |
| MV DGM1/5/25 | 1/5/25 m | +-0,2-0,5 m | GeoTIFF float32 + XYZ | MV, 6407 kafli | ~10 lat |
| BB bDOM / SN DOM1 / MV DOM1 | 1 m | — | GeoTIFF float32 | per land | 3 lata (MV) |
| SN LSC | ~16 pkt/m2 | — | LAZ (LAS 1.2) | Saksonia | 6 lat |
| BB ALS | ~1,27 pkt/m2 | — | LAZ (LAS 1.4, PDRF 6) | **42% BB, brak Berlina** | rocznie partiami |
| MV bDOM10 | ~97 pkt/m2 | — | LAZ (fotogram., nie LIDAR) | MV | 3 lata |
| **ATKIS Basis-DLM** | ~1:10 000 | — | **GPKG / SHP / NAS / GML** | **caly kraj** | **dziennie** (basemap.de) |

**Dane BKG koncza sie dokladnie na granicy panstwa** [OK]: kafel 10x10 km na Odrze pod Frankfurtem = 15,5% nodata (-9999). Zlewnie transgraniczne wymagaja zszycia zrodel DE + PL.

---

## 3. Sposoby dostepu

### BKG — WCS po dowolnym bboxie DZIALA (otwarty, bez klucza)

```
https://sgx.geodatenzentrum.de/wcs_dgm200_inspire?SERVICE=WCS&VERSION=2.0.1
  &REQUEST=GetCoverage&COVERAGEID=dgm200_inspire__EL.GridCoverage
  &FORMAT=image/tiff&SUBSET=E(870000,880000)&SUBSET=N(5810000,5820000)
  &geotiff:compression=LZW
```
[OK] HTTP 200, `image/tiff`, -> rasterio: **EPSG:25832, 50x50, float64, res 200 m, nodata -9999**.

Zmierzone zachowanie:
- **Etykiety osi to `E`/`N`, nie `x`/`y`** — `SUBSET=x(...)` -> `InvalidAxisLabel` [OK]
- `SUBSETTINGCRS` + `OUTPUTCRS` = EPSG:25833 **dziala**, ale **resampluje** do 215,5 m [OK] -> lepiej pobierac natywnie i reprojektowac lokalnie
- **`geotiff:compression=LZW` dziala: 7 872 963 B -> 1 001 025 B (7,9x)** [OK]
- **Brak limitu rozmiaru**: caly kraj w jednym zadaniu -> **3207x4331 px, 132 MB** [OK]
- `SCALESIZE` **[FAIL]** HTTP 404 — brak resamplingu po stronie serwera
- **WMS nie zwraca wysokosci** [OK]: `wms_dgm200&LAYERS=hoehe&FORMAT=image/geotiff` -> uint8, 4 pasma, obraz renderowany

### ATKIS Basis-DLM — OGC API Features po bboxie, caly kraj

```
https://api.basemap.de/basisviews/collections/vegetationsflaeche_bdlm/items
  ?bbox=14.54,52.34,14.56,52.36&limit=100&f=json
```
[OK] HTTP 200 `application/geo+json`, 6,4 s, `numberMatched` obecne, `id=DEBBAP0100000iEv` (BB). Bbox 0,3 x 0,3 stopnia -> 4351 obiektow, 13,5 MB, 16,6 s [OK].
**31 kolekcji**, zasieg `5.99,47.30,15.02,54.98` (caly kraj). **CRS tylko CRS84 i EPSG:3857** [OK] — `crs=...25833` -> HTTP 400.

Alternatywa plikowa (per land, GeoPackage, EPSG:4326, `accept-ranges: bytes`):
```
https://basemap.de/dienste/opendata/basisviews/basisviews_bdlm_{BB|SN|MV|...}_EPSG4326_{RRRR-MM-DD}.gpkg
```
[OK] BB 593 MB, SN 864 MB, MV 360 MB. Schemat zweryfikowany na HB (37 MB): 31 warstw `*_bdlm`, kolumny `id, land, objektart, klasse, name, funktion, ...`. Klasyfikacja gotowa pod CN/HSG: `Landwirtschaft/Gruenland`, `Wald/Laubholz`, `Moor`, `Wohnbauflaeche`, `IndustrieUndGewerbeflaeche`, `StehendesGewaesser` itd. [OK]

### Landy — najkrotsze dzialajace wywolania

```
# Brandenburgia — WCS
https://isk.geobasis-bb.de/ows/dgm_wcs?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage
  &COVERAGEID=bb_dgm&SUBSET=x(250000,250300)&SUBSET=y(5888000,5888300)&FORMAT=image/tiff
  # [OK] 300x300 float32, nodata -9999, bounds dokladnie jak zadano
  # PULAPKA: rasterio crs = None -> trzeba recznie przypisac EPSG:25833

# Meklemburgia — WCS
https://www.geodaten-mv.de/dienste/dgm_wcs?service=WCS&version=2.0.1&request=GetCoverage
  &coverageId=mv_dgm&subset=x(300000,300500)&subset=y(5980000,5980500)&format=image/tiff
  # [OK] 500x500 float32, EPSG:25833 osadzony poprawnie, min 5.822 max 13.452

# Saksonia — TYLKO kafle (brak WCS)
https://geocloud.landesvermessung.sachsen.de/public.php/dav/files/JCcXyifaNdLDnxZ/dgm1_33410_5654_2_sn_tiff.zip
  # [OK] GET/Range -> 206.  HEAD -> 401 (!)
```

**Odpowiedz na pytanie "raster po dowolnym bboxie czy tylko arkusze":** BKG (200 m), Brandenburgia i MV — **tak, WCS**. Saksonia — **nie, tylko kafle 2x2 km + wlasne mozaikowanie**.

---

## 4. Ograniczenia

| Ograniczenie | Ustalenie |
|---|---|
| Klucz API / rejestracja | **Nigdzie nie wymagane** dla danych otwartych [OK] — wszystkie testy anonimowe |
| BKG DGM1/DOM1 | **Paywall** — URL wymaga tokenu `wcs_dgm1__{{uuid}}` [OK] |
| MV ALS (surowy LIDAR) | **HTTP 401 Basic realm="als_download"** [OK] — platny; darmowy zamiennik bDOM10 |
| Limity rozmiaru WCS | Nie wykryto. BKG: caly kraj 132 MB. BB: 12000x12000 = **576 MB, 123 s**. MV: 8000x8000 = 256 MB |
| **Odpowiedzi WCS nieskompresowane** | 4-8 B/px -> kafelkuj do ~2000-4000 px; BKG akceptuje `geotiff:compression=LZW` |
| Stronicowanie WFS | **BB: `ImplementsResultPaging=FALSE`**, `CountDefault` 100k/300k -> dziel po bboxie |
| Luki w pokryciu | **BB ALS: 13086/31291 kafli** (42%, brak Berlina) [OK]; SN: 8 kafli DGM1 nie istnieje |
| Rate limiting | Nie napotkano nigdzie (pobrania 150-420 MB, brak naglowkow `X-RateLimit-*`) |

**Ciche bledy (najgrozniejsze):**
- **BB WFS**: `BBOX=...,EPSG:25833` -> `numberMatched=0` **bez bledu**; wymagane `urn:ogc:def:crs:EPSG::25833` [OK]
- **MV WFS**: odwrotnie — wymagane krotkie `EPSG:25833`; forma `urn:` -> cicho 0 [OK]
- **SN**: `HEAD` -> 401, `GET` -> 206; `geodienste.sachsen.de` zwraca 403 zarowno dla blokady jak i dla nieistniejacej sciezki
- **BB LAZ**: naglowek deklaruje EPSG:3045 (os N-E), a dane sa zapisane E,N -> wymus 25833
- **SN**: SHARE_ID Nextcloud sa tokenami z HTML — moga byc rotowane, pobieraj runtime z `batchConfig.products`

---

## 5. Licencje

| Zrodlo | Licencja | Atrybucja | Rejestracja |
|---|---|---|---|
| **BKG open data** | **GeoZG / GeoNutzV** — "geldleistungsfrei", komercyjnie i niekomercyjnie [OK] | `(c) GeoBasis-DE / BKG <rok>`, przy zmianach `(Daten veraendert)` | nie |
| BKG DGM1/DOM1 | odplatna licencja przez ZSGT, **od 8 000 EUR** | — | **tak** |
| **Brandenburgia** | **dl-de/by-2-0** [OK] | `(c) GeoBasis-DE/LGB, dl-de/by-2-0` | nie |
| **Saksonia** | **dl-de/by-2-0** [OK] (z feedu ATOM) | `Quelle: GeoSN, dl-de/by-2-0` | nie |
| **Meklemburgia-PP** | **CC BY 4.0** [OK] (open data od 09.06.2024) | `(c) GeoBasis-DE/M-V/CC BY 4.0` | nie |
| basemap.de Basis-DLM | dl-de/**zero**-2-0 lub dl-de/by-2-0 per land; HB = CC BY 4.0 [DOC] | per land | nie |

Wszystkie licencje otwarte sa kompatybilne z komercyjnym uzyciem. **Nie ma jednej licencji federalnej** — trzeba trzymac ja per zrodlo (inaczej niz CUZK, gdzie caly portfel to CC BY 4.0).

---

## 6. Uklady wspolrzednych

### Poziomy — podzial stref jest realny i wazny

| Landy | Strefa | EPSG |
|---|---|---|
| **BB, BE, MV, SN** (+ ST czesciowo) | **UTM 33N** | **25833** |
| pozostale 11 landow | UTM 32N | 25832 |
| **BKG (wszystkie produkty)** | **UTM 32N, easting rozszerzony** | **25832** |

**Wszystkie landy graniczace z Polska uzywaja EPSG:25833** — to upraszcza sprawe dla Kartografa.

**BKG normalizuje CALY kraj do strefy 32** [OK]: kafle DGM1 to wylacznie `dgm1_32_*` (sprawdzone 4 metalinki), a DGM200 ma bounds easting **279 900 - 922 100 m** — czyli wschodnie Niemcy maja eastingi > 834 km (poza normalnym zakresem UTM).

**Pulapka wariantow CRS** [OK, zweryfikowane w pyproj]:
| EPSG | Nazwa | Cecha |
|---|---|---|
| 25832 / 25833 | ETRS89 / UTM 32N / 33N | normalne, E,N |
| **4647 / 5650** | UTM (**zE-N**) | **easting z prefiksem strefy**: 469 349 -> **33 469 349** |
| 3044 / 3045 | UTM (N-E) | **odwrocona kolejnosc osi** |
| 5652 / 5653 | UTM (N-zE) | oba naraz |

W metadanych landow spotyka sie zapis `ETRS89_UTM33z` — literka `z` oznacza wlasnie prefiks strefy.

### Wysokosciowy

| System | EPSG | Gdzie |
|---|---|---|
| **DHHN2016** (NHN, pegel Amsterdam) | **7837** | **aktualny standard**: BKG DGM200 [OK, dokumentacja PDF w paczce], BB DGM1 [OK, compound CRS w TIF], SN [OK], MV [OK] |
| DHHN92 | 5783 | starsze DGM5 (BB, MV, SH, SL) [OK, metadane BKG] |
| SNN76 | 5785 | dane b. NRD sprzed harmonizacji |

BB DGM1 ma **pelny compound CRS osadzony w GeoTIFF** [OK]:
`COMPD_CS["ETRS89 / UTM zone 33N + DHHN2016 height", ... AUTHORITY["EPSG","7837"]]` — wzorowe, rzadkosc.

---

## 7. Transformacja do ukladu polskiego — wyniki praktyczne

**pyproj 3.7.2 / PROJ 9.5.1**, `allow_ballpark=False`, `pyproj.network.set_network_enabled(True)`.

### 7.1 Poziomy — trywialny, dokladnosc 0,0 m, bez siatek

```
EPSG:25833 -> EPSG:2180 : 1 operacja, acc = 0.0 m
  "Inverse of UTM zone 33N + Inverse of ETRF2000-PL to ETRS89 (1) + Poland CS92"
```
[OK] Round-trip na 3 punktach granicznych: **blad 0,000 mm**.
Powod: oba uklady siedza na ETRS89 — to czysta zmiana odwzorowania, bez transformacji datum. **Zadnych siatek, zadnego pobierania.** Radykalnie prosciej niz Czechy (S-JTSK/Krovak).

Przykladowo: Frankfurt (Oder) UTM33 (469349, 5800063) -> **PL-1992 (507549.59, 197061.76)**.

### 7.2 Wysokosciowy — tu jest problem

**Wprost do ukladow polskich: BRAK operacji.**

| Para | Dostepne | Wymagane siatki | Status siatek |
|---|---|---|---|
| 7837 -> **9650** (KRON86) | **0** | `de_2019m/z.asc` + `pl86_2019m/z.asc` | **niedostepne, `open_license=False`, brak URL** |
| 7837 -> **9651** (EVRF2007-PL) | **0** | `de_2019m/z.asc` + `pl07_2019m/z.asc` | **j.w.** |
| 7837 -> **5621** (EVRF2007) | **1, acc 0,1 m** | **BRAK** | — |
| 5783 (DHHN92) -> 5621 | 1, acc 0,1 m | brak | — |
| 5785 (SNN76) -> cokolwiek PL | **0** | — | brak definicji EPSG |
| 5621 -> 9651 | **0** (tylko ballpark) | — | EPSG nie definiuje relacji |
| 9651 -> 9650 | 0 | `gugik-evrf2007.txt` | **niedostepna** (znany problem po stronie PL) |

**Jedyna czysta sciezka: DHHN2016 -> EVRF2007 (EPSG:5621).** To prosty `+proj=vertoffset` (dh=0,014 m w punkcie 51,05N/10,22E, `slope_lat=-0.01`), **bez zadnych siatek**. Rozpietosc po calych Niemczech: **-0,0073 - +0,0342 m (0,042 m)** [OK].

Zmierzone przesuniecia dla h = 50,000 m:

| Punkt | -> EVRF2007 (5621) | -> EVRF2007-PL (9651) | -> KRON86 (9650) |
|---|---|---|---|
| Frankfurt (Oder) | 50,0070 (+7,0 mm) | 50,0145 | 49,8538 (**-146 mm**) |
| Loecknitz / Szczecin | 50,0010 (+1,0 mm) | 50,0057 | **`inf`** |
| Goerlitz | 50,0135 (+13,5 mm) | 49,9997 | 49,8613 (-138,7 mm) |
| Guben | 50,0094 (+9,4 mm) | 50,0001 | **`inf`** |
| Ahlbeck / Uznam | 49,9987 (-1,3 mm) | 49,9767 | 49,8384 (-161,6 mm) |

### 7.3 Dwie powazne pulapki — obie potwierdzone eksperymentalnie

**(a) `inf` przy KRON86.** `Transformer.from_crs` na compound CRS znajduje sciezke przez modele geoidy (late binding, acc 0,13 m):
```
inv utm33 -> vgridshift de_bkg_gcg2016.tif -> inv vgridshift pl_gugik_geoid2011-PL-KRON86-NH.tif -> tmerc
```
Wszystkie trzy siatki **sa w PROJ CDN** [OK]. Ale polska siatka KRON86 jest **maskowana do terytorium Polski**: bbox 14,045-24,205 / 48,995-54,885, **nodata -32768, tylko 71,8% komorek ma dane** [OK]. Po stronie niemieckiej -> nodata -> **`inf`**.
Siatka `pl_gugik_geoid2021-PL-EVRF2007-NH.tif` ma **`nodata = None`** i bbox 12,995-25,005 — dlatego EVRF2007-PL dziala wszedzie (ale na zachod od granicy sa to wartosci ekstrapolowane, traktowac ostroznie).

> **Konkluzja: przeliczenie niemieckiego NMT do KRON86 (EPSG:9650) nie jest wiarygodnie mozliwe** — polski model geoidy nie jest zdefiniowany nad Niemcami.

**(b) Cicha degradacja do ballpark przy braku sieci.** Z `set_network_enabled(False)`, `Transformer.from_crs(..., allow_ballpark=True)` zwraca dla **wszystkich** punktow **dokladnie h = 50,0000 (dh = 0,0000)** — czyli identycznosc, **bez zadnego bledu ani ostrzezenia** [OK]. Uzytkownik dostaje wynik zanizony o ~15 cm i nie ma o tym pojecia.
> Kartograf **musi** budowac transformer przez `TransformerGroup(..., allow_ballpark=False)`, jawnie odrzucac przypadek `len(transformers)==0` oraz kontrolowac `math.isinf()` na wyniku.

**Praktyczne obejscie dla KRON86** [OK, zmierzone na 20 000 losowych komorkach obu siatek]:
```
h(EVRF2007-PL) - h(KRON86) = +0,1606 m   (sigma 0,0149; zakres 0,056 - 0,443)
```
czyli `h_KRON86 ~= h_DHHN2016 - 0,16 m` z niepewnoscia ~1,5 cm — ale ta zaleznosc jest kalibrowana **tylko nad Polska**.

**Rekomendacja:** dla danych niemieckich uzywac **EPSG:5621 (EVRF2007)** jako ukladu docelowego. Roznica DHHN2016 -> EVRF2007 to **1-14 mm**, czyli ponizej dokladnosci samego NMT (0,15-0,3 m). Praktycznie: **niemieckie wysokosci mozna traktowac jako EVRF2007 bez konwersji.**

---

## 8. Klad arkuszy — wszedzie arytmetyczny, nigdzie nie trzeba indeksu

| Zrodlo | Wzorzec | Kafel | Wzor |
|---|---|---|---|
| **BKG DGM1** | `dgm1_32_{E_km}_{N_km}_1.tif` | 1 km | **zawsze strefa 32**, `E//1000`, `N//1000` |
| **Brandenburgia** | `dgm_33{EEE}-{NNNN}.zip` | 1 km | `f"33{int(x//1000):03d}-{int(y//1000):04d}"` |
| **Saksonia** | `dgm1_33{E}_{N}_2_sn_tiff.zip` | 2 km | `floor(c/2000)*2`, E 3-cyfr, N 4-cyfr |
| **Meklemburgia** | `dgm1_33_{E}_{N}_2_gtiff.tif` | 2 km | `floor(c/2000)*2` |
| MV bDOM | `bdom10_33_{E/100}_{N/100}_05.laz` | 500 m | jednostki 100 m |

Wszystkie zweryfikowane predykcyjnie: wyliczona nazwa -> HTTP 200 [OK] (np. Rostock `dgm1_33_306_5996_2_gtiff.tif`; SN `dgm1_33411_5655...` -> 404, bo nieparzysty km — zgodnie ze wzorem).

**Uslugi indeksu istnieja, ale sluza tylko do sprawdzenia POKRYCIA i AKTUALNOSCI, nie do wyliczenia nazwy:**
- BB: WFS `blattschnitte_wfs` (13 siatek; atrybut `kachelnummer` = nazwa pliku) + CSV `bb_dgm_aktualitaet.csv` (31 292 linie, 1 request) [OK]
- SN: **shapefile 152 kB** `Shape_km2_33_UTM.zip` (4989 kafli) + WMS GetFeatureInfo z `application/geo+json` [OK]
- MV: feedy ATOM z `bbox` per kafel [OK]

**TK25 (Messtischblatt)** — uzywany przez DTK i czesc dystrybucji ATKIS (`dtk10_2448-no.zip`, `2936-SO Breese`). Wzor wyprowadzony z geometrii WFS Brandenburgii [OK]:
```
numer = RRCC (4 cyfry);  arkusz = 6' szer. x 10' dlug.
gorna szerokosc   = 56 st 00' - RR x 6'
zachodnia dlugosc = 5 st 40' + CC x 10'
```
Sprawdzone na 2833 Doemitz / 2933 Gusborn / 2834 Gorlosen — zmierzone rozmiary **dokladnie 6,00' x 10,00'**, zgodnosc ~5" (roznica datum Bessel->WGS84). Cwiartki: `-nw/-no/-sw/-so`. **Rowniez w pelni obliczalny.**

---

## Zweryfikowane endpointy (gotowe do uzycia)

```bash
# ---------- BKG: krajowy, otwarty ----------
# DGM200 - caly kraj, jeden plik (36 MB zip -> 3211x4331, EPSG:25832, DHHN2016)
https://daten.gdz.bkg.bund.de/produkte/dgm/dgm200/aktuell/dgm200.utm32s.geotiff.zip
https://daten.gdz.bkg.bund.de/produkte/dgm/dgm1000/aktuell/dgm1000.utm32s.geotiff.zip
# DGM200 WCS - DOWOLNY BBOX, bez klucza, LZW, bez limitu rozmiaru
https://sgx.geodatenzentrum.de/wcs_dgm200_inspire?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=dgm200_inspire__EL.GridCoverage&FORMAT=image/tiff&SUBSET=E(870000,880000)&SUBSET=N(5810000,5820000)&geotiff:compression=LZW
https://sgx.geodatenzentrum.de/wms_dgm200?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0   # tylko podglad
https://sgx.geodatenzentrum.de/wfs_dlm250?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0

# ---------- ATKIS Basis-DLM: KRAJOWY, otwarty, po bboxie ----------
https://api.basemap.de/basisviews/collections                                    # 31 warstw
https://api.basemap.de/basisviews/collections/{warstwa}/items?bbox=14.5,52.3,14.6,52.4&f=json
https://basemap.de/dienste/opendata/basisviews/                                  # listing GPKG per land
https://basemap.de/dienste/opendata/basisviews/basisviews_bdlm_BB_EPSG4326_2026-08-10.gpkg

# ---------- Brandenburgia ----------
https://isk.geobasis-bb.de/ows/dgm_wcs?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=bb_dgm&SUBSET=x(250000,250300)&SUBSET=y(5888000,5888300)&FORMAT=image/tiff
https://isk.geobasis-bb.de/ows/bdom_wcs        # CoverageId bb_bdom  (NMPT)
https://isk.geobasis-bb.de/ows/dop20c_wcs      # CoverageId bb_dop20c_1 (orto 0,2 m)
https://isk.geobasis-bb.de/ows/blattschnitte_wfs?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0
https://isk.geobasis-bb.de/ows/atkisbdlm_sf_wfs?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0
https://data.geobasis-bb.de/geobasis/daten/dgm/tif/dgm_33250-5888.zip
https://data.geobasis-bb.de/geobasis/information/aktualitaeten/bb_dgm_aktualitaet.csv

# ---------- Meklemburgia-Pomorze Przednie ----------
https://www.geodaten-mv.de/dienste/dgm_wcs?service=WCS&version=2.0.1&request=GetCoverage&coverageId=mv_dgm&subset=x(300000,300500)&subset=y(5980000,5980500)&format=image/tiff
https://www.geodaten-mv.de/dienste/dom_wcs     # mv_dom1
https://www.geodaten-mv.de/dienste/ndom_wcs    # mv_ndom
https://www.geodaten-mv.de/dienste/atkis_bdlm_wfs_sf?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0
https://www.geodaten-mv.de/dienste/basisdlm_download?index=0&dataset=24ace62b-2ea6-44df-a72b-0e24f9f076de&file=MV_BasisDLM_25833.zip
https://www.geodaten-mv.de/dienste/dgm_atom

# ---------- Saksonia (brak WCS!) ----------
https://www.geodaten.sachsen.de/download/Shape_km2_33_UTM.zip                    # skorowidz 152 kB
https://www.geodaten.sachsen.de/batch-download-4719.html                         # zrodlo SHARE_ID
https://geocloud.landesvermessung.sachsen.de/public.php/dav/files/JCcXyifaNdLDnxZ/dgm1_33410_5654_2_sn_tiff.zip
https://geodienste.sachsen.de/wms_geosn_aktualitaet-gbd/guest?SERVICE=WMS&REQUEST=GetCapabilities
https://geodienste.sachsen.de/wms_geosn_hoehe/guest?SERVICE=WMS&REQUEST=GetCapabilities

# ---------- NIE dziala ----------
https://sgx.geodatenzentrum.de/wcs_dgm1        # 403 NOACCESS_SERVICE (platny, wymaga UUID)
https://geodienste.sachsen.de/wcs_geosn_dgm1   # 403 - WCS wysokosciowy w SN nie istnieje
https://www.geodaten-mv.de/dienste/als_download?...  # 401 Basic - ALS platny
```

---

## Wnioski dla architektury

**Model polski (GUGiK):** jeden dostawca, dostep dwustopniowy — WMS skorowidzow -> URL pliku -> pobranie po godle. Godlo jest jednostka pierwszej klasy; potrzebny parser (`SheetParser`, `Parser2000`) i `MetadataCache` na mapowanie godlo->URL.

**Model czeski (CUZK):** jeden dostawca, jedna licencja, REST po bboxie + pliki po arkuszach SM5. Bez kluczy i limitow.

**Model niemiecki: to nie jest jeden model, tylko federacja 17 modeli.** Roznice strukturalne:

1. **Rozdzielenie warstwy krajowej i landowej wg skali, nie wg funkcji.** BKG daje za darmo tylko to, co zgrubne (200 m / 1000 m / 1:250k); wszystko co dokladne jest albo platne (BKG DGM1: 8 000 EUR), albo rozproszone po landach. **Nie ma odpowiednika "GUGiK dla calego kraju".** Wybor zrodla zalezy od zadanej rozdzielczosci **i** od lokalizacji — to nowy wymiar, ktorego nie ma ani w PL ani w CZ.

2. **Godla nie istnieja — jest czysta arytmetyka na UTM.** To *upraszcza* sprawe wzgledem Polski: zaden `SheetParser`, zaden `MetadataCache` na URL-e, zaden WMS GetFeatureInfo. Nazwa pliku = funkcja `(x, y)`. Ale kazdy land ma **inny** wzor (1 km vs 2 km, `33250-5888` vs `33410_5654_2_sn`) -> abstrakcja potrzebuje **strategii nazewnictwa kafla per zrodlo**, nie jednego parsera.

3. **WCS jako pierwszorzedny sposob dostepu — ale nie wszedzie.** BKG, BB i MV daja prawdziwy `download_bbox()` bez limitow rozmiaru. Saksonia nie ma go wcale. To wymusza w abstrakcji **jawna deklaracje zdolnosci zrodla** (`supports_bbox: bool`) i **generyczny fallback** "pobierz kafle -> zszyj -> przytnij", ktory Kartograf i tak juz ma czesciowo dla NMT z GUGiK. Odwrotnie niz w PL, gdzie brak WCS jest wyjatkiem (5 m) — w DE to rownoprawny wariant.

4. **Skorowidz zmienia znaczenie.** W GUGiK skorowidz jest **niezbedny** (daje URL). W Niemczech URL jest obliczalny, wiec skorowidz sluzy wylacznie do odpowiedzi na "czy ten kafel istnieje i z ktorego roku jest". Najtansza forma bywa statycznym plikiem (SN: shapefile 152 kB; BB: CSV 1,4 MB) zamiast uslugi. `MetadataCache` powinien wiec cache'owac **maski pokrycia i daty**, a nie URL-e — to inne zastosowanie tej samej klasy.

5. **Pokrycie terenu jest tu latwiejsze niz w Polsce.** basemap.de daje **krajowy, dzienny, jednolity 31-warstwowy ATKIS Basis-DLM z zapytaniem po bboxie** (OGC API Features). To lepiej niz BDOT10k (pobierany w calosci per TERYT, ADR-016) i lepiej niz ZABAGED. Warto rozwazyc, czy `LandCoverProvider` nie powinien zyskac wariantu "zapytanie po bboxie" obok istniejacego "pobierz caly plik".

6. **Uklad wysokosciowy przestaje byc parametrem wyboru, a staje sie metadana do walidacji.** W GUGiK uzytkownik *wybiera* KRON86 albo EVRF2007. W Niemczech dostaje DHHN2016 i koniec. Za to dochodzi problem, ktorego w PL nie ma: **nie da sie tego wiarygodnie przeliczyc na KRON86** (brak polskiej geoidy nad Niemcami -> `inf`), a PROJ przy braku sieci **cicho zwraca identycznosc**. Abstrakcja musi (a) przechowywac `vertical_crs` jako atrybut zbioru, (b) walidowac transformacje przez `TransformerGroup(allow_ballpark=False)` i (c) traktowac `inf` jako blad, nie jako dane.

7. **Licencja i uwierzytelnianie przestaja byc globalne.** PL i CZ maja po jednej regule. DE ma dl-de/by-2-0, dl-de/zero-2-0, CC BY 4.0, GeoNutzV i paywalle **wewnatrz jednego kraju**. Metadane licencji i wymaganego `Quellenvermerk` musza wisiec **przy zrodle**, a nie przy kraju — inaczej nie da sie poprawnie oznaczyc produktu pochodnego.

**Sugerowany ksztalt wspolnej abstrakcji:** zrodlo danych opisane deklaratywnie — `crs_horizontal`, `crs_vertical`, `tile_grid` (rozmiar + wzor nazwy), `capabilities` (`bbox` / `tiles` / oba), `coverage_index` (URL + typ), `license`, `attribution`, `auth`. Providery przestaja byc klasami "jeden kraj = jedna klasa", a staja sie **kilkoma silnikami transportu** (WCS 2.0.1, WCS 1.0.0, kafel-po-URL, ATOM, OGC API Features, WebDAV) sterowanymi przez taki opis. Niemcy same w sobie wymagaja 4 z tych 6 silnikow, wiec sa dobrym testem, czy abstrakcja jest wystarczajaco ogolna — a Polska i Czechy staja sie wtedy jej szczegolnymi, prostszymi przypadkami.

**Uwaga o zakresie:** szczegolowo zbadane 3 landy graniczne z Polska. Pozostalych 13 nie weryfikowano — z tabeli metadanych BKG wiadomo tylko, jakich CRS i ukladow wysokosciowych uzywaja; ich API dostepu pozostaja niesprawdzone [DOC].
