# Research: dane wysokosciowe i pokrycia terenu dla Slowacji (UGKK SR / GKU Bratislava)

**Data:** 2026-08-10
**Zakres:** NMT/NMPT (DMR/DMP) oraz odpowiednik BDOT10k (ZBGIS)
**Metoda:** weryfikacja na zywo (curl + rasterio + pyproj)
**Legenda:** **[T]** = przetestowane na zywo 2026-08-10 | **[D]** = tylko dokumentacja

**Errata (2026-08-18):** rekomendacja "preferuj `outputCrs=EPSG:2180` po stronie
serwera (jak `imageSR=2180` w CUZK)" (sekcja 7.5 pkt 1, wnioski koncowe) jest
niewazna — wzorcowy przyklad CUZK zostal obalony (ADR-024: serwer gubi
transformacje datum S-JTSK->ETRS89, blad tresci 135 m). Przy implementacji SK
zaufanie do reprojekcji serwerowej trzeba najpierw zweryfikowac pomiarem TRESCI
rastra (dopasowanie do referencji natywnej), nie metadanych (bounds/CRS).

---

## 1. Produkty wysokosciowe

| Produkt | Rozdzielczosc | Dokladnosc | Format | Zasieg | Status | Uklad |
|---|---|---|---|---|---|---|
| **DMR 3.5** | 10 / 25 / 50 / 100 m | brak deklaracji (fotogrametria, stary) | TIFF+TFW | caly kraj | zamkniete (pliki z 2020) | S-JTSK **EPSG:5514** + Bpv **[T]** |
| **DMR 5.0** (1. cykl LLS 2017-2023) | **1 m** | model 0,03-0,13 m w Bpv (per lokalizacja); chmura m_h<=0,15 m, m_XY<=0,30 m | TIFF+TFW | **100% SR** | **UKONCZONY** (42/42 lokalizacji, 51 042 km2 z zakladkami) **[T]** | S-JTSK[JTSK03] **EPSG:8353** + Bpv **EPSG:8357**, wariant ETRS89-TM34 + h |
| **DMP 1.0** | 1 m | j.w. | TIFF+TFW | 100% SR | ukonczony (42/42) **[T]** | j.w. |
| **DMR 6.0** (2. cykl LLS 2022-2026) | **0,5 m** | chmura m_h<=0,10 m, m_XY<=0,20 m, min. 15 pkt/m2 | TIFF+TFW | **CZESCIOWY** | **16 z 73 lokalizacji = 12 671 z 49 786 km2 (~25%)** **[T]** | j.w. |
| **DMP 2.0** | 0,5 m | j.w. | TIFF+TFW | j.w., te same 16 LOT | w toku | j.w. |
| **Chmury LIDAR (klasyfikowane)** | 1. cykl min. 5 pkt/m2 (realnie 18-41), 2. cykl min. 15 | m_h<=0,15 / 0,10 m | **LAS / LAZ** | 100% (1. cykl) | dostepne | j.w. |

**DMR 3.0** — nie jest oferowany jako osobny produkt; w ofercie GKU wystepuje wylacznie DMR 3.5 (nastepca). **[T — brak w katalogu produktow]**

Dostepne lokalizacje 2. cyklu (DMR 6.0): LOT04 Myjava, 06 Piestany, 07 Trnava, 08 Bratislava, 09 Galanta, 10 Dunajska Streda, 11 Puchov, 12 Povazska Bystrica, 13 Trencin, 16 Prievidza, 17 Nitra, 20 Nove Zamky, 27 Zilina, 29 Martin, 31 Banska Bystrica, 32 Banska Stiavnica. **Zaden LOT przy granicy z Polska (Tatry, Orawa, Spisz, Bardejov) nie ma jeszcze DMR 6.0** — tam obowiazuje DMR 5.0. **[T]**

Wolumeny (1. cykl, tabela GKU): LAS 72,8 TB, LAZ 11,3 TB, DMR 5.0 TIFF 216 GB, DMP 1.0 TIFF 170 GB. **[T — PDF]**

---

## 2. Pokrycie terenu — odpowiednik BDOT10k / ZABAGED

**ZBGIS** (Zakladna baza udajov pre GIS) — topograficzna baza obiektowa, referencyjna dla SR.

- **116 klas obiektow / 128 warstw** wg typu geometrii, 116 domen atrybutowych, 2 relacje. **[T — KTO ZBGIS v2022.00, s. 6]**
- Kodowanie **DIGEST/FACC** (kategoria A-Z + subkategoria + 3 cyfry, np. `AL015` budynek, `EC015` las, `BH140` ciek). 10 kategorii: A antropogenne, B wodstwo, C wysokopis, D povrch, E wegetacja, F granice, G lotnicze, O, S, Z. **[T]**
- **Dokladnosc**: atrybut `ACH`/`ACV` per obiekt — 1 = geodezyjna <10 cm, 2 = do 1 m, 3 = do 5 m, 997 = szacowana (max 10 m w zabudowie, 20 m poza), 998 = n/d. **[T]**
- **Progi generalizacji**: linia od 5 m dlugosci, powierzchnia od 15 m2 i szerokosci 4 m -> poziom szczegolowosci **1:5000-1:10000, wyrazniej niz BDOT10k**. **[T]**
- Od 2021 obiekty ZBGIS sa "polozone" na DMR (2/3 na DMR 5.0, 1/3 na DMR 3.5) — baza jest **3D**. **[T]**

**Dostep do wektora:**
1. **ArcGIS REST MapServer `/query`** — 92 opublikowane warstwy, dziala po bboxie, `outSR` dowolny (przetestowane `outSR=2180`!), `f=json|geojson|pbf`, paginacja `resultOffset`. **To jest praktyczna droga i jest darmowa (CC BY 4.0). [T]**
2. Pelny zrzut wektora ZBGIS — **tylko na zamowienie i odplatnie** (cennik per jednostka; gminy i miasta bezplatnie). Publicznie jest tylko *vzorka* (probka). **[T/D]**
3. INSPIRE WFS — **tylko** `gn` (nazwy geograficzne) i `cp`/`cp_uo` (dzialki). Dla `bu` (budynki), `hy` (hydrografia), `tn` (transport) **WFS nie istnieje, tylko WMS**. **[T]**
4. **ZBGIS Raster** (rastrowa reprezentacja wektora) 1:5000/10000/25000/50000, TIFF, EPSG:8353 — pliki calego kraju (93/35/7/2 GB) lub max 20 arkuszy przez MAPKA. **[T]**

---

## 3. Sposoby dostepu

### 3.1 Raster po dowolnym bboxie — **WCS INSPIRE (GeoServer)** — DZIALA **[T]**

```
https://inspirews.skgeodesy.sk/geoserver/el/ows
  ?service=WCS&version=2.0.1&request=GetCoverage
  &coverageId=el__EL.GridCoverage&format=image/tiff
  &subset=E(434000,435000)&subset=N(5450000,5451000)
```
Zwrocilo: GeoTIFF 1000x1000 px, float32, res 1 m, `EPSG:3046`, nodata `3.4e38`, wartosci 1212-2006 m (Tatry).

- Pokrycie: cala SR, siatka **423518 x 207589 px, 1 m** (E 191148-614666, N 5289631-5497220 w EPSG:3046). **[T]**
- **`outputCrs` DZIALA**: `...&outputCrs=http://www.opengis.net/def/crs/EPSG/0/8353` -> GeoTIFF w JTSK03; `.../EPSG/0/2180` -> **GeoTIFF prosto w PL-1992** (res ~1,026 m po reprojekcji). **[T]**
- **`scaleFactor` dziala** (`&scaleFactor=0.2` -> 5 m). `scalesize` nie (blad "Scale Axis Undefined"). **[T]**
- `subsettingCrs` **nie dziala** (`Invalid axis label` dla E/N, X/Y, Y/X) — bbox trzeba przeliczyc do EPSG:3046 po stronie klienta. **[T]**
- Rozmiary: 3000x3000 px = 38 MB / 19 s; 6000x6000 = 151 MB / 72 s; **10000x10000 = 419 MB / 193 s — nadal HTTP 200**. Nie natrafiono na limit. **[T]**
- **UWAGA KRYTYCZNA: ta usluga serwuje wysokosci ELIPSOIDALNE ETRS89 (h), nie Bpv.** Zweryfikowane: WCS 1109,12 m vs DMR 5.0/Bpv 1066,81 m w tym samym punkcie -> **roznica +42,31 m** (i +42,51 m w drugim punkcie), zgodna z kwazigeoida SK (42,60/42,67 m). **[T]**

**DMP 1.0 przez WCS NIE JEST dostepne** — workspace `el_dsm` ma tylko WMS, `Service WCS is disabled`. **[T]**

### 3.2 Wartosc piksela w **Bpv** — ArcGIS REST `identify` **[T]**
```
https://zbgis.skgeodesy.sk/zbgis/rest/services/LLS_DMR5/MapServer/identify
  ?geometry=20.13368,49.11728&geometryType=esriGeometryPoint&sr=4326
  &layers=all&tolerance=1&mapExtent=...&imageDisplay=400,400,96&f=json
```
Zwraca `{"layerName":"DMR 5.0","Stretch.Pixel Value":"1066.807983"}` — **to jest Bpv**. Punktowo, nie po bboxie. Analogicznie `LLS_DMP1_cache` (3 warstwy: teren cieniowany, wysoka wegetacja, budynki) i `LLS_DMR6`.

### 3.3 **Brak ArcGIS ImageServer** — kluczowa roznica wobec Czech **[T]**
Katalog `https://zbgis.skgeodesy.sk/zbgis/rest/services?f=json` zawiera **51 uslug, wszystkie `MapServer`** + folder `Utilities` z `RasterUtilities/GPServer` (zadania `DownloadRaster` itd., asynchroniczne, bez publicznego image service). Sprawdzono rowniez instancje `arcgis`, `zbgisimg`, `img`, `ags`, `services.*`, `mapy.*`, `gis.*` — brak. `kataster.skgeodesy.sk/eskn/rest/services` -> 403 dla katalogu.
**Wniosek: operacji `exportImage` po bboxie (jak w CUZK) na Slowacji NIE MA.**

### 3.4 Wektor po bboxie — ArcGIS REST `/query` **[T]**
```
https://zbgis.skgeodesy.sk/zbgis/rest/services/ZBGIS/MapServer/47/query
  ?geometry=20.10,49.10,20.20,49.15&geometryType=esriGeometryEnvelope&inSR=4326
  &spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=true
  &outSR=2180&f=json
```
Wyniki testu (bbox ~7x5 km, `outSR=2180`): Les 472 obiekty, Budova 453, Vodny tok 88, Cesta 526, Vrstevnica 1000 + `exceededTransferLimit=true`.
`returnCountOnly=true` -> `{"count":1450}`; `resultOffset=1000&resultRecordCount=1000` -> 466 obiektow; `f=geojson` -> poprawny FeatureCollection z `crs EPSG:2180`. **[T]**

### 3.5 OGC WMS/WMTS/WFS (ArcGIS-backed, host `zbgisws.skgeodesy.sk`) **[T — 7 z 7 zweryfikowanych]**
Wzorzec: `https://zbgisws.skgeodesy.sk/{nazwa}/service.svc/get?service={wms|wfs|wmts}&request=GetCapabilities`.
Obslugiwane CRS w GetCapabilities: `CRS:84, 4326, 4258, 3857, 102100, 102067, 3045, 3046, 32633, 32634, **5514**, **8353**`.
GetMap zweryfikowany: `zbgis_wms_featureinfo` (PNG 600x600) i `zbgis_dmr_wms` (PNG 289 kB, realny cieniowany relief).

### 3.6 ATOM (INSPIRE) **[T]**
`https://inspirews.skgeodesy.sk/atom/f3d323e2-1a59-4e20-abdd-65526038dc48_dlsFeed.atom` -> dataFeed -> **tylko dwa linki: caly kraj** (`DTM5_0_etrs89-tm34_h.zip` 197 GB, `DSM1_0_etrs89-tm34_h.zip`). ATOM nie daje podzialu na arkusze. `<rights>` = CC BY 4.0.

### 3.7 Pliki bezposrednie — `opendata.skgeodesy.sk` **[T]**
Listing katalogu **403 (nginx)**, ale pliki po pelnym URL dzialaja, `HEAD` zwraca `Content-Length` i `Last-Modified`.
- **Granulacja: caly kraj (1. cykl) albo caly LOT (2. cykl).** Brak plikow per arkusz.
- Sprawdzone rozmiary: `DMR5_0_sjtsk03_bpv.zip` = 197 707 257 567 B (184 GiB), `DTM5_0_etrs89-tm34_h.zip` = 196 930 690 205 B, `LOT31_DMR6_sjtsk03_bpv.zip` = 14 885 113 536 B, `dmr3_5-10.zip` = 2 431 870 103 B, `dmr3_5-100.zip` = 46 090 430 B.
- **Pobrano i sprawdzono `dmr3_5-100.zip`**: `dmr3_5_100.tif` — `crs=EPSG:5514` **osadzony w GeoTIFF** (w przeciwienstwie do czeskiego DMR4G), float32, nodata `-3.4028231e+38`, 4269x2043 px, res 100 m, bounds (-591854, -1336506, -164954, -1132206), max 2622,9 m. **Gotcha: plik `.tfw` uzywa przecinka dziesietnego (`100,0000000000`)** — naiwny parser TFW sie wywroci; GDAL czyta z tagow GeoTIFF i ignoruje tfw. **[T]**

### 3.8 MAPKA (klient mapowy) — wycinki **[D, z oficjalnej strony]**
- DMR 5.0 / DMP 1.0 / DMR 6.0 / DMP 2.0: wycinki **do 400 km2**
- Klasyfikowana chmura punktow: **do 4 km2**
- ZBGIS Raster / Ortofoto: **max 20 arkuszy naraz**
Nie udalo sie zidentyfikowac publicznego REST API tego eksportu (aplikacja Angular, lazy-chunki, i18n zewnetrzne; w bundlu tylko `/mapka/proxy/`). **NIEPOTWIERDZONE — brak udokumentowanego programistycznego endpointu.**

---

## 4. Ograniczenia

| Ograniczenie | Wartosc | Status |
|---|---|---|
| ArcGIS REST `maxRecordCount` | **1000** + flaga `exceededTransferLimit`; paginacja `resultOffset` dziala | **[T]** |
| **WAF blokuje parametr `where=`** | kazde `where=...` -> strona "Kataster Portal / Request Rejected" (HTTP 503 lub HTML). Dziala `geometry=`, `objectIds=`, `returnCountOnly` | **[T]** |
| Dlugie URL-e | `objectIds` z 400 ID -> `Request Rejected` | **[T]** |
| Rejestracja / klucz API / OAuth | **BRAK** dla wszystkich uslug i plikow open data | **[T]** |
| WCS — limit rozmiaru | nie napotkano do 10000x10000 px (419 MB, 193 s) | **[T]** |
| WCS — `subsettingCrs` | nie dziala | **[T]** |
| DMP 1.0 przez WCS | wylaczone (`Service WCS is disabled`) | **[T]** |
| Luka w pokryciu DMR 6.0 | 57 z 73 lokalizacji jeszcze niedostepnych; **brak pasa przygranicznego z PL** | **[T]** |
| LAZ/LAS online | **BRAK** — tylko odbior osobisty (Bratislava / Presov) lub MAPKA do 4 km2 | **[D]** |
| Pelny wektor ZBGIS | odplatny, na zamowienie | **[D]** |
| Granulacja plikow DMR/DMP | caly kraj (184 GB) lub caly LOT (9-15 GB) | **[T]** |
| Stabilnosc | `zbgis.skgeodesy.sk` okresowo zwraca strone "duzy ruch" (503) na niektorych sciezkach; `geoportal.sk` ma **niewazny certyfikat** (altnames = gku.sk), przekierowany na `www.gku.sk` | **[T]** |

---

## 5. Licencje

- **CC BY 4.0** dla wszystkiego, co interesujace: DMR 5.0, DMP 1.0, DMR 6.0, DMP 2.0, DMR 3.5, ZBGIS Raster, Ortofotomozaika, klady arkuszy, granice administracyjne, nazwy geograficzne, wszystkie WMS/WMTS/WFS. Autor: UGKK SR / GKU Bratislava. **[T — deklaracja na stronie produktu + `<rights>https://creativecommons.org/licenses/by/4.0/deed.sk</rights>` w feedzie ATOM]**
- Bez rejestracji, bez klucza, bez limitu wolumenu. **[T]**
- **Platne**: pelny wektor ZBGIS na zamowienie (cennik GKU per jednostka; gminy/miasta bezplatnie). Klasyfikowane chmury LAZ — bezplatne, ale odbior offline na nosniku. **[D]**

---

## 6. Uklady wspolrzednych

### Poziomo
| EPSG | Nazwa | Obszar | Uzycie na SK |
|---|---|---|---|
| **8353** | **S-JTSK [JTSK03] / Krovak East North** | **tylko Slowacja** | **AKTUALNY, od 2021 obowiazujacy dla ZBGIS, DMR 5.0/6.0, DMP** |
| 8351 / 8352 | S-JTSK [JTSK03] geog. / Krovak (South-West) | tylko SK | warianty |
| 5514 | S-JTSK / Krovak East North | CZ + SK | **stara realizacja** — DMR 3.5, ortofotomozaika, granice administracyjne |
| 3046 | ETRS89 / UTM 34N (**os N,E**) | — | INSPIRE WCS/WMS (`el`, `el_dsm`, `oi`) |
| 25834 | ETRS89 / UTM 34N (os E,N) | — | bezpieczniejszy wariant do obliczen |

**Czym JTSK03 rozni sie od S-JTSK [T]:** ta sama elipsoida Bessela i ta sama projekcja Krovaka — **rozni sie wylacznie realizacja datum**. JTSK03 to przeliczenie sieci JTSK (2011) sztywno zwiazane z ETRS89 **7-parametrowym Helmertem o dokladnosci 0,001 m** (EPSG:8367: dX=485,021 dY=169,465 dZ=483,839; rX=-7,786342" rY=-4,397554" rZ=-4,102655"). Stare S-JTSK nie ma takiego zwiazku — do ETRS89 tylko przyblizenia 0,5-1,0 m albo droga przez siatke.
Przejscie JTSK03 <-> S-JTSK to **EPSG:8364, metoda NADCON, dokladnosc 0,05 m, siatka `sk_gku_JTSK03_to_JTSK.tif`** — czyli niejednorodne, interpolowane przesuniecie, **nie** Helmert.
Zmierzone roznice 8353 vs 5514 na SR: **0,19 m (Orawa) - 1,47 m (Bratyslawa)**, kierunek zmienny. **[T]**

### Pionowo
**Bpv = EPSG:8357 "Baltic 1957 height" — identyczny kod jak dla Czech.** Potwierdzone dwojako: (a) baza EPSG w pyproj (datum Baltic 1957, area "Czechia; Slovakia"; przeglad `query_crs_info` dla Slovakia nie zawiera zadnego kodu "SK-only"), (b) **wprost w KTO ZBGIS s. 6**: *"povodny Baltic (kod EPSG: 5705) bol nahradeny vyskovym systemom Baltic_1957_height s kodom EPSG:8357"*. **EPSG:5705 (Baltic 1977) jest bledny dla SK.** **[T]**

---

## 7. Transformacja do ukladu polskiego (pyproj 3.7.2 / PROJ 9.5.1, network=True, allow_ballpark=False)

### 7.1 Poziomo
**`EPSG:8353 -> EPSG:2180`: 2 operacje, obie `is_available=True`, obie acc = 0,001 m, ZADNA nie wymaga siatki.** Rozrzut miedzy nimi: **0,006 m**. Wybor operacji nie ma znaczenia. **[T]**

**`EPSG:5514 -> EPSG:2180`: 7 operacji, acc od 7,0 do 0,051 m.** Najlepsze (op. 3 i 4, acc **0,051 m**) uzywaja siatki `sk_gku_JTSK03_to_JTSK.tif`. **Rozrzut miedzy operacjami: 5,4 m (Bratyslawa) - 11,9 m (Koszyce).** `allow_ballpark=False` NIE chroni — operacje o acc 7,0 m sa "dostepne". Trzeba **jawnie** przypiac operacje z siatka. **[T]**

Kontrola: `8353 -> 5514(siatka) -> 2180(op. z siatka)` vs `8353 -> 2180(acc 0,001)` = **0,0000 m** dla wszystkich punktow. Przez domyslna operacje 5514->2180 blad wynosi 4,0-11,9 m.

### 7.2 Siatka `sk_gku_JTSK03_to_JTSK.tif` — **DZIALA na Slowacji** **[T]**
- `available=True, direct_download=True, open_license=True`, `https://cdn.proj.org/sk_gku_JTSK03_to_JTSK.tif` (183 kB), CC BY 4.0, GKU Bratislava, ze zrodla `Slovakia_JTSK03_to_JTSK.gsb` (2016).
- Odczytana rasterio: 257x126 px, CRS `EPSG:8351`, **bounds lon 16,3875-22,8125 / lat 47,5916-49,7084**, 2 pasma (dLat, dLon w sekundach luku), zakres dLat -0,0245..+0,0390", dLon -0,0539..+0,0801".
- **Pokrywa cala Slowacje** (SK: 16,83-22,57 / 47,73-49,61). Praha (14,42E) jest **poza bboxem** -> `inf` — to wyjasnia obserwacje z badania czeskiego. Brno (16,61E) miesci sie w bboxie, ale to ekstrapolacja poza `area_of_use` — **nie uzywac dla CZ**.

Zmierzone przesuniecia 8353 vs 5514 przy granicy z PL: Tatry (49,20N 19,98E) **0,489 m**, Orawa (49,50N 19,55E) **0,192 m**, Bardejov (49,35N 21,20E) **0,887 m**.

### 7.3 Pionowo
| Zrodlo -> cel | Operacje dostepne | acc | Siatki | Wynik |
|---|---|---|---|---|
| 8357 -> **5621** (EVRF2007) | 1 | **0,1 m** | brak (`vertoffset dh=0.13 slope_lat=0.026`) | **DZIALA**, przesuniecie **+0,120..+0,124 m** |
| 8357 -> **9650** (Kronsztadt'86) | **0** | `pl86_2019z/m.asc` — `available=False, open_license=False, url=''` | **NIEDOSTEPNE** |
| 8357 -> **9651** (EVRF2007-PL) | **0** | `pl07_2019z/m.asc` — j.w. | **NIEDOSTEPNE** |
| `8353+8357 -> 2180+9650` / `2180+9651` | **0 operacji w ogole** | — | **BRAK** |
| `8353+8357 -> 2180+5621` | 2 | 0,101 | — | **DZIALA** |

**Cicha pulapka [T]:** z `allow_ballpark=True` dla 8357->9650/9651 pojawia sie ballpark (acc=-1,0), ktory **zwraca dH = +0,000 m** — czyli po cichu nic nie robi.

**Obejscie ktore dziala — dwa kroki przez h elipsoidalne [T]:**
`Bpv --[sk_gku_Slovakia_ETRS89h_to_Baltic1957.tif]--> ETRS89h --[pl_gugik_geoid*]--> KRON86 / EVRF2007-PL`

| Punkt | H_Bpv | -> KRON86 (9650) | -> EVRF2007-PL (9651) | -> EVRF2007 (5621) |
|---|---|---|---|---|
| Tatry 49,20/19,98 | 1457,112 | 1456,912 (**-0,200**) | 1457,212 (**+0,100**) | 1457,232 (+0,120) |
| Orawa 49,50/19,55 | 658,140 | 658,138 (-0,002) | 658,289 (+0,149) | 658,264 (+0,124) |
| Bardejov 49,35/21,20 | 311,236 | 311,182 (-0,054) | 311,320 (+0,084) | 311,358 (+0,122) |
| pkt 49,117/20,134 | 1062,8 | **inf** | 1062,905 (+0,105) | 1062,919 (+0,119) |

`pl_gugik_geoid2011-PL-KRON86-NH.tif` ma nodata ponizej ~**49,15N** -> dla wiekszosci Slowacji **KRON86 zwroci `inf`**. `pl_gugik_geoid2021-PL-EVRF2007-NH.tif` (bbox 12,995-25,005 / 47,995-56,005) **pokrywa cala Slowacje**.

### 7.4 ETRS89h -> Bpv (potrzebne, bo WCS daje h elipsoidalne)
Siatki na cdn.proj.org, CC BY 4.0, GKU: `sk_gku_Slovakia_ETRS89h_to_Baltic1957.tif` (780x450, EPSG:4937, bounds 16,50-23,00 / 47,50-50,00, wartosci 33,14-45,83 m) i `sk_gku_Slovakia_ETRS89h_to_EVRF2007.tif`. **[T]**

**PULAPKA [T]:** `TransformerGroup("EPSG:4937","EPSG:8357")` zwraca **2 operacje o tej samej acc 0,03 m**, i **pierwsza jest czeska** (`cz_cuzk_CR-2005.tif`) -> dla punktow SK **`inf`**. Trzeba filtrowac po `"sk_gku" in t.definition`.

**Weryfikacja empiryczna [T]:** w punkcie lon=20,13368 lat=49,11728 WCS (`el`) = 1109,12 m, `LLS_DMR5/identify` (Bpv) = **1066,81 m** -> roznica **42,31 m**; drugi punkt 1176,30 vs 1133,79 -> **42,51 m**. Model SK daje 42,60 / 42,67 m. **Zgodnosc do ~0,2 m potwierdza: WCS = DMR 5.0 w h_ETRS89, ArcGIS = DMR 5.0 w Bpv.** (Porownanie z warstwa "vyskova kota" ZBGIS dawalo pozorne 45-46 m — kot topograficznych nie nalezy uzywac jako referencji, maja ACV do 5 m.)

### 7.5 Rekomendowana sciezka dla Kartografa
1. **Preferuj `outputCrs=EPSG:2180` po stronie serwera WCS** — omija caly problem doboru operacji PROJ (jak `imageSR=2180` w CUZK).
2. Jesli transformujesz lokalnie: uzywaj **8353**, nie 5514. Gdy dostaniesz 5514 — jawnie przypnij operacje z `sk_gku_JTSK03_to_JTSK.tif`.
3. `PROJ_NETWORK=ON` / `pyproj.network.set_network_enabled(True)` jest **wymagane**.
4. Pionowo: dane z **plikow/ArcGIS = Bpv**, dane z **WCS = h_ETRS89** — nie mieszac. Docelowo dla PL wymuszac **EVRF2007-PL (9651)** lub EVRF2007 (5621); **KRON86 nie dziala ponizej ~49,15N**.

---

## 8. Klad arkuszy

| Klad | Rozmiar arkusza | Nomenklatura | Obliczalna? |
|---|---|---|---|
| **SMO5 / ZBGIS Raster 1:5000** | **2500 x 2000 m** (S-JTSK03) | `"<Miasto> C-R"`, np. `Poprad 7-6` | **Geometria TAK, nazwa NIE** |
| ZBGIS Raster 1:10000 | 5000 x 4000 m | `"<Miasto> NN"`, np. `Poprad 16` | j.w. |
| Ortofoto 1:5000 | 2500 x 2000 m | j.w. (`STAV_ROK` = rok) | j.w. |
| ZM 10 | ~5100 x 4077 m (Gauss-Kruger) | `27-33-12` | prawdopodobnie tak (nie badane) |
| ZM 25/50/100/200, TM 25/50 | — | analogiczna | — |

**Struktura SMO5 wyprowadzona z danych [T]:** blok nazwany miastem = **10 x 10 arkuszy = 25 km x 20 km**. Kolumna `C` rosnie na **zachod** (bardziej ujemne X), wiersz `R` rosnie na **poludnie** (bardziej ujemne Y); `C=0,R=0` to arkusz przy naroznikuk NE bloku. Dla bloku Poprad naroznik NE = (X=-325000, Y=-1180000). W bbox 0,7 x 0,3 stopnia znaleziono 405 arkuszy w 9 blokach: Poprad(100), Kezmarok(70), Spissky Stiavnik(60), Liptovsky Hradok(50), Spisska Nova Ves(42), Polomka(30), Lendak(24), Stara Lubovna(21), Liesek(8).
**To jest ten sam system co czeski SM5** (2 x 2,5 km, nazwa miasta + cyfry) — wspolne dziedzictwo czechoslowackie.

**Uslugi indeksu arkuszy — istnieja i dzialaja [T]:**
- `.../ZBGIS_klady_export/MapServer/{0|1|2|3}` — klady ZBGIS Raster 5000/10000/25000/50000, atrybuty `NAZOV_ML`, `NAME_ASCII`, `STAV_ROK`; layer 4 = Ortofoto 5000
- `.../Klady_ZM/MapServer/{0..5}`, `.../Klady_TM`, `.../Klad_SMO5`, `.../Klady_ML` (14 warstw), `.../Klady_RGB`
- Pliki SHP/GDB/GPKG/DGN/DXF: `https://www.gku.sk/files/gku/produkty-sluzby/na-stiahnutie/klad_zbgis_{5000|10000|25000|50000}_{shp|gdb|gpkg}.zip`, `klad_zm{10|25|50|100|200}_*.zip`

**Indeks lokalizacji LLS (najwazniejszy dla dostepnosci DMR):**
- `LLS_DMR5/MapServer/0` — 42 lokalizacje 1. cyklu; atrybuty: `Cislo_lokality`, `Nazov_lokality`, `Vymera`, `Obdobie_sken`, `Poskytovanie`, `Vyskova_presnost`, `Polohova_presnost`, `Priemerna_hustota`, `Vyskova_presnost_DMR`, `Dostupnost_DMR/DMP/klasif` **[T]**
- `LLS_DMR6/MapServer/0` — 73 lokalizacji 2. cyklu **[T]**
- Pliki: `prehlad_lokalit_lls_{1|2}_cyklus.zip`, footprints LAS: `opendata.skgeodesy.sk/static/LLS/Footprints/{1|2}_cyklus/las_footprints_s-jtsk03_*_shp.zip`

**Pliki DMR/DMP NIE sa udostepniane per arkusz** — tylko caly kraj / caly LOT. Nazewnictwo kafli wewnatrz ZIP-a niezweryfikowane (nie da sie bez pobrania 184 GB). **NIEPOTWIERDZONE.**

---

## Zweryfikowane endpointy (gotowe do uzycia)

```bash
# --- KATALOG USLUG ArcGIS REST (51 uslug, wszystkie MapServer) ---
https://zbgis.skgeodesy.sk/zbgis/rest/services?f=json

# --- DMR 5.0 RASTER PO BBOXIE (ETRS89 h!) ---
https://inspirews.skgeodesy.sk/geoserver/el/ows?service=WCS&version=2.0.1&request=GetCapabilities
https://inspirews.skgeodesy.sk/geoserver/el/ows?service=WCS&version=2.0.1&request=DescribeCoverage&coverageId=el__EL.GridCoverage
https://inspirews.skgeodesy.sk/geoserver/el/ows?service=WCS&version=2.0.1&request=GetCoverage&coverageId=el__EL.GridCoverage&format=image/tiff&subset=E(434000,435000)&subset=N(5450000,5451000)
# ... + &outputCrs=http://www.opengis.net/def/crs/EPSG/0/2180   (prosto w PL-1992)
# ... + &outputCrs=http://www.opengis.net/def/crs/EPSG/0/8353   (JTSK03)
# ... + &scaleFactor=0.2                                        (downsampling do 5 m)

# --- DMR 5.0 / DMP 1.0 / DMR 6.0 WARTOSC PIKSELA W Bpv (punktowo) ---
https://zbgis.skgeodesy.sk/zbgis/rest/services/LLS_DMR5/MapServer/identify?geometry=20.13368,49.11728&geometryType=esriGeometryPoint&sr=4326&layers=all&tolerance=1&mapExtent=20.132,49.116,20.135,49.118&imageDisplay=400,400,96&returnGeometry=false&f=json
https://zbgis.skgeodesy.sk/zbgis/rest/services/LLS_DMP1_cache/MapServer/identify?...
https://zbgis.skgeodesy.sk/zbgis/rest/services/LLS_DMR6/MapServer/identify?...

# --- INDEKS DOSTEPNOSCI LLS ---
https://zbgis.skgeodesy.sk/zbgis/rest/services/LLS_DMR5/MapServer/0/query?geometry=16.5,47.5,23.0,49.8&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=false&f=json
https://zbgis.skgeodesy.sk/zbgis/rest/services/LLS_DMR6/MapServer/0/query?...

# --- ZBGIS (odpowiednik BDOT10k), 92 warstwy, reprojekcja serwerowa ---
https://zbgis.skgeodesy.sk/zbgis/rest/services/ZBGIS/MapServer?f=json
https://zbgis.skgeodesy.sk/zbgis/rest/services/ZBGIS/MapServer/47/query?geometry=20.10,49.10,20.20,49.15&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=*&returnGeometry=true&outSR=2180&f=geojson
# warstwy kluczowe: 22 Cesta, 35 Vodny tok, 41 Budova, 47 Les, 48 Luka, 58 Orna poda,
#   60 Sad/zahrada, 70 Trava, 72 Vinica, 73 Vodna plocha, 85 Vrstevnica, 103 Kroviny, 20 Vyskova kota
# paginacja: &resultOffset=1000&resultRecordCount=1000 ; licznik: &returnCountOnly=true
# UWAGA: WAF blokuje where= i dlugie URL-e; retry na odpowiedzi HTML ("duzy ruch")

# --- KLADY ARKUSZY ---
https://zbgis.skgeodesy.sk/zbgis/rest/services/ZBGIS_klady_export/MapServer/1/query?geometry=...&outSR=8353&f=json
https://zbgis.skgeodesy.sk/zbgis/rest/services/Klady_ZM/MapServer/4/query?...
https://zbgis.skgeodesy.sk/zbgis/rest/services/Klad_SMO5/MapServer/1/query?...

# --- OGC WMS / WMTS / WFS (CC BY 4.0, CRS m.in. 5514, 8353, 3857) ---
https://zbgisws.skgeodesy.sk/zbgis_wms_featureinfo/service.svc/get?service=wms&request=GetCapabilities
https://zbgisws.skgeodesy.sk/zbgis_dmr_wms/service.svc/get?service=wms&request=GetCapabilities
https://zbgisws.skgeodesy.sk/zbgis_vyskopis_wms_featureinfo/service.svc/get?service=wms&request=GetCapabilities
https://zbgisws.skgeodesy.sk/zbgis_ortofoto_wms/service.svc/get?service=wms&request=GetCapabilities
https://zbgisws.skgeodesy.sk/klady_mapovych_listov_wms/service.svc/get?service=wms&request=GetCapabilities
https://zbgisws.skgeodesy.sk/zbgis_wmts_sjtsk/service.svc/get?service=wmts&request=GetCapabilities
https://zbgisws.skgeodesy.sk/zbgis_administrativne_hranice_wfs/service.svc/get?service=wfs&request=GetCapabilities

# --- INSPIRE GeoServer (workspaces: el, el_dsm, oi, au, bu, cp, cp_uo, gn, hy, tn) ---
https://inspirews.skgeodesy.sk/geoserver/{ws}/ows?service=WMS&version=1.3.0&request=GetCapabilities
https://inspirews.skgeodesy.sk/geoserver/gn/ows?service=WFS&version=2.0.0&request=GetCapabilities
https://inspirews.skgeodesy.sk/atom/f3d323e2-1a59-4e20-abdd-65526038dc48_dlsFeed.atom

# --- KATALOG METADANYCH (CSW, pycsw) ---
https://rpi.gov.sk/csw?service=CSW&request=GetCapabilities&version=2.0.2

# --- PLIKI (listing katalogu = 403, pelne URL dzialaja) ---
https://opendata.skgeodesy.sk/static/LLS/DMR5/DMR5_0_sjtsk03_bpv.zip                 # 184 GiB
https://opendata.skgeodesy.sk/static/LLS/DMP1/DMP1_0_sjtsk03_bpv.zip                 # 144 GB
https://opendata.skgeodesy.sk/static/INSPIRE/Elevation/DTM5_0_etrs89-tm34_h.zip      # 183 GiB
https://opendata.skgeodesy.sk/static/LLS/2_cyklus/LOT{NN}/LOT{NN}_{DMR6,DMP2}_{sjtsk03_bpv,etrs89_tm34}.zip
https://opendata.skgeodesy.sk/static/DMR3_5/dmr3_5-{10,25,50,100}.zip                # 2.4 GB / 401 MB / 102 MB / 46 MB
https://opendata.skgeodesy.sk/static/ZBGIS_Raster/zbgis_raster_{5000,10000,25000,50000}_2023.zip
https://opendata.skgeodesy.sk/static/LLS/Footprints/1_cyklus/las_footprints_s-jtsk03_1_cyklus_shp.zip
https://www.gku.sk/files/gku/produkty-sluzby/na-stiahnutie/klad_zbgis_10000_gpkg.zip
https://www.gku.sk/files/gku/produkty-sluzby/na-stiahnutie/prehlad_lokalit_lls_{1,2}_cyklus.zip
```

---

## Wnioski dla architektury

### Co jest strukturalnie takie samo jak w Czechach
| Aspekt | CZ (CUZK) | SK (UGKK) |
|---|---|---|
| Uklad poziomy | S-JTSK Krovak EN | ten sam Krovak, ale **inna realizacja datum** |
| Uklad pionowy | Bpv = **EPSG:8357** | **EPSG:8357 — identyczny** |
| Licencja | CC BY 4.0, bez kluczy | **CC BY 4.0, bez kluczy** |
| Klad arkuszy 1:5000 | SM5 2x2,5 km, miasto + cyfry, nieobliczalny | **SMO5 2,5x2 km, miasto + `C-R`, ten sam system** |
| Uslugi wektorowe | ArcGIS REST `/query` z `outSR` | **ArcGIS REST `/query` z `outSR` — identyczny wzorzec** |
| Limit REST | 2000 + `exceededTransferLimit` | **1000 + `exceededTransferLimit`** |
| Baza topograficzna | ZABAGED 149 warstw | **ZBGIS 116 klas / 128 warstw / 92 opublikowane** |

### Czym sie rozni — 5 istotnych roznic
1. **Brak ArcGIS ImageServer.** W CZ `exportImage` po bboxie jest glownym kanalem dla DMR5G/DMP1G. Na SK go nie ma. Zamiast tego jest **WCS 2.0.1 na GeoServerze INSPIRE** — funkcjonalnie rownowazny (bbox + `outputCrs` + `scaleFactor`), ale inny protokol i inne parametry.
2. **Rozdwojenie ukladu wysokosciowego miedzy kanalami.** WCS daje **h elipsoidalne ETRS89**, ArcGIS/pliki daja **Bpv**. W CZ tego problemu nie ma. To wymaga w abstrakcji jawnego pola `vertical_datum` **per kanal dostepu**, a nie per produkt, oraz opcjonalnej konwersji przez `sk_gku_Slovakia_ETRS89h_to_Baltic1957.tif`.
3. **Rozdwojenie ukladu poziomego 5514 vs 8353.** Kartograf musi rozrozniac: DMR 3.5 i ortofoto = 5514, DMR 5.0/6.0/DMP/ZBGIS Raster = 8353. Roznica 0,2-1,5 m. Nie da sie potraktowac "S-JTSK" jako jednego CRS dla CZ i SK.
4. **Brak plikow per arkusz.** W CZ `openzu.cuzk.gov.cz/opendata/{PRODUKT}/epsg-{5514|3045}/{ARKUSZ}.zip` — URL w pelni przewidywalny i granulacja arkuszowa. Na SK jest **caly kraj (184 GB) albo caly LOT (9-15 GB)**. Dla obszaru zlewni to nieuzywalne -> **jedyna sensowna droga dla rastra to WCS**, a nie pliki. Odwrotnie niz w CZ.
5. **Brak online LAZ.** GUGiK ma WFS + linki do LAZ, CUZK ma pliki, SK ma **odbior osobisty na nosniku**. Produkt "LAZ" dla SK trzeba w Kartografie oznaczyc jako niedostepny programistycznie.

### Konsekwencje dla wspolnej abstrakcji zrodel
- Abstrakcja **`BaseProvider` + `download_bbox()` sprawdzi sie**, ale musi dopuszczac **dwie implementacje transportu rastra: ArcGIS `exportImage` (CZ) i OGC `WCS 2.0.1 GetCoverage` (SK)**. Warto wyodrebnic transport rastra po bboxie jako osobna strategie, zamiast wiazac providera z jednym protokolem.
- **Reprojekcja po stronie serwera jest wspolnym mianownikiem** dla obu krajow (`imageSR`/`outSR` w CZ, `outputCrs` w SK) i dla obu jest **zdecydowanie preferowana** — omija ryzyko doboru operacji PROJ. To powinno byc domyslne zachowanie w calym toolchainie.
- **Model wysokosciowy trzeba wyniesc do metadanych wyniku.** Minimum: `horizontal_crs`, `vertical_crs`, `vertical_source` (grid/serwer). Bez tego dane SK z WCS wpadna do Hydrografa z bledem 42 m.
- **Warstwa "klad arkuszy" jest wspolna koncepcyjnie**: CZ SM5 i SK SMO5 to ten sam system nieobliczalny -> jedna implementacja indeksu arkuszy odpytujaca ArcGIS REST (`Klad_SMO5` / `KladyMapovychListu`) obsluzy oba kraje. To najlepszy kandydat na wspolny kod.
- **Warstwa "indeks dostepnosci"** (`LLS_DMR5/0`, `LLS_DMR6/0`) jest analogiczna do skorowidzow GUGiK — ten sam wzorzec "sprawdz zanim pobierzesz". Dla SK jest prostszy: pokrycie DMR 5.0 = 100%, wiec sprawdzanie potrzebne tylko dla DMR 6.0.
- **Mapowanie semantyczne ZBGIS -> BDOT10k** jest wykonalne przez kody FACC (`EC015` las, `EA010` orna poda, `BH140` ciek, `AL015` budynek), podobnie jak dla ZABAGED. Warto zaprojektowac wspolny slownik klas pokrycia terenu i mapowac na niego PL/CZ/SK.
- **Uwaga operacyjna**: WAF na `zbgis.skgeodesy.sk` blokuje `where=` i dlugie URL-e. Klient musi uzywac wylacznie zapytan przestrzennych + `resultOffset`, i miec retry na odpowiedzi HTML (strona "duzy ruch") — inaczej `.json()` rzuci `JSONDecodeError`.
