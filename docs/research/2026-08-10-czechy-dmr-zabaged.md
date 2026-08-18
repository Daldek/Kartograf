# Research: dane wysokosciowe i pokrycia terenu dla Czech (CUZK)

**Data:** 2026-08-10
**Zakres:** rozszerzenie Kartografa o czeski odpowiednik NMT (DMR) i BDOT10k (ZABAGED)
**Status:** research zakonczony, wszystkie endpointy zweryfikowane na zywo

**Errata (2026-08-18):**
1. Rekomendacja reprojekcji po stronie serwera (sekcja 4.2 "Reprojekcja po stronie
   serwera dziala", sekcja 9 "Alternatywa o wyzszej dokladnosci — reprojekcja po
   stronie serwera CUZK" i wniosek 3) zostala OBALONA pomiarem tresci: przy
   `imageSR=2180` serwer NIE stosuje transformacji datum S-JTSK->ETRS89
   (przesuniecie tresci 135 m), a przy `imageSR=3045` ma zmienny blad 1,25-4,92 m.
   Od ADR-024 Kartograf pobiera wylacznie natywne EPSG:5514 i reprojektuje lokalnie
   (`rasterio.warp` z przypieta operacja). Wniosek metodyczny: kontrola poprawnosci
   reprojekcji musi mierzyc TRESC rastra (dopasowanie do referencji), nie
   bounds/CRS z metadanych.
2. Drobne korekty faktow wg rekonesansu (`docs/research/2026-08-11-etap1-rekonesans.md`,
   sekcja "Blednie zalozone fakty"): arkuszy SM5 jest 16 299, nie 16 301; przy
   parametrze `noData=-9999` serwer wypelnia -9999 (zera tylko bez parametru);
   `CTES96` to "Cesky Tesin 9-6", nie 8-6; `crs=None` dotyczy takze rastrow
   z ImageServera, nie tylko plikow DMR4G-TIFF.

---

## 1. Dostawca i podstawa prawna

Wszystkie dane pochodzia z **CUZK** (Cesky urad zememericky a katastralni) / **ZU** (Zememericky urad).
Odpowiednik polskiego GUGiK.

- Od **1.07.2023** caly portfel danych plikowych ZU jest **otwartymi danymi** na jednolitej licencji
  **Creative Commons CC BY 4.0**, bezplatnie, bez rejestracji, bez limitu wolumenu.
- Feedy ATOM deklaruja `<rights>zadne podminky neplati</rights>` (brak warunkow).
- Wymagane jedynie oznaczenie zrodla (atrybucja CC BY).

To istotna roznica wzgledem GUGiK: **nie ma kluczy API, nie ma OAuth, nie ma limitow ilosciowych**.

---

## 2. Produkty wysokosciowe (odpowiedniki NMT/NMPT)

| Produkt | Odpowiednik PL | Charakter | Dokladnosc | Format |
|---|---|---|---|---|
| **DMR 5G** | NMT 1m | TIN, nieregularna siec punktow | 0,18 m teren odkryty / 0,3 m las | LAZ (punkty), raster 2 m przez ImageServer |
| **DMR 4G** | NMT 5m | regularna siatka **5 x 5 m** | 0,3 m odkryty / 1,0 m las | LAZ + **GeoTIFF** |
| **DMP 1G** | NMPT | model pokrycia (ALS) | — | LAZ |
| **DMP z obrazovej korelace (DMP OK)** | NMPT nowszy | fotogrametryczny, wysoka rozdzielczosc | — | GeoTIFF + LAZ |
| **Ortofoto CR** | Ortofotomapa | 0,125 m od 2021 (0,20 m 2016-2020) | cykl 2-letni | JPEG + JGW |

DMR 5G powstal z lotniczego skaningu laserowego 2009-2013, ukonczony 30.06.2016,
aktualizowany fotogrametrycznie i ALS. Pokrycie 100% kraju (78 866 km2), zakres wysokosci 115-1602 m.

**Uwaga:** w przeciwienstwie do Polski, czeskie DMR ma **jednolite pokrycie calego kraju**.
Nie wystepuje problem znany z GUGiK (rozne dostepnosci 1m/5m na roznych obszarach).

---

## 3. Uklady wspolrzednych

### 3.1 Poziomy

| Uklad | EPSG | Uwagi |
|---|---|---|
| **S-JTSK / Krovak East North** | **5514** | podstawowy uklad krajowy; wsp. **ujemne** (X ok. -900 000..-430 000, Y ok. -1 228 000..-935 000) |
| S-JTSK / Krovak | 5513 | wariant osi (South-West), spotykany w starszych danych |
| **ETRS89 / UTM 33N (TM33N)** | **3045** | wariant INSPIRE; oś N,E (uwaga na kolejnosc!) |

Krovak to odwzorowanie **konforemne stozkowe ukosne** — nie jest to Transverse Mercator.
Cala Republika Czeska jest w jednej strefie TM33 (takze czesc wschodnia, ktora geograficznie
nalezalaby do strefy 34) — dla ortofoto CUZK dokłada dodatkowe pliki JGW dla TM34.

### 3.2 Wysokosciowy

| Uklad | EPSG | Uwagi |
|---|---|---|
| **Bpv** (Balt po vyrovnani) | **8357** ("Baltic 1957 height") | natywny dla DMR/DMP; potwierdzone w `vcsWkid` uslug ImageServer |
| **EVRF2007 (EVRS)** | **5621** | CUZK publikuje rownolegly wariant DMR 5G w ETRS89-TM33N + EVRS |

**Wazne:** Bpv to *Baltic 1957*, a nie *Baltic 1977* (EPSG:5705, uklad postsowiecki).
Pomylka tych dwoch jest czestym bledem.

Model kwazigeoidy: **QGZU-2013** — plaszczyzna transformacyjna Bpv <-> wysokosci elipsoidalne
ETRS89/ETRF2000 nad GRS80. Dostepny jako ATOM (`https://atom.cuzk.gov.cz/QGZU/QGZU.xml`, format Blz).

---

## 4. Sposoby dostepu do danych wysokosciowych

### 4.1 ATOM + bezposrednie URL-e (zalecane do pobierania plikow)

Feedy ATOM: `https://atom.cuzk.gov.cz/{THEME}/{THEME}.xml`

Zweryfikowane tematy:

| Theme | Zawartosc | Ziarno |
|---|---|---|
| `DMR5G-SJTSK` | DMR 5G, LAZ, EPSG:5514 | arkusze SM5 |
| `DMR5G-ETRS89` | DMR 5G, LAZ, EPSG:3045 | kafle 2 x 2 km |
| `DMR4G-SJTSK` / `DMR4G-ETRS89` | DMR 4G, LAZ | SM5 / 2x2 km |
| `DMR4G-SJTSK-TIFF` | **DMR 4G, GeoTIFF 5 m** | SM5 |
| `DMP1G-SJTSK` / `DMP1G-ETRS89` | DMP 1G, LAZ | SM5 / 2x2 km |
| `DMPOK-SJTSK-TIFF`, `DMPOK-ETRS89-TIFF`, `DMPOK-*-LAZ` | DMP z korelacji obrazowej | SM5 / 2x2 km |
| `ORTOFOTO` | Ortofoto CR, JPEG + JGW | SM5 |
| `ZABAGED-GPKG`, `ZABAGED-FGDB` | ZABAGED, caly kraj w 1 pliku | — |
| `QGZU` | kwazigeoid QGZU-2013 | — |

Feed glowny zawiera po jednym `<entry>` na kafel (16 301 dla SM5, 20 308 dla siatki 2x2 km),
z `georss:polygon`. Rozmiar feedu: 24-30 MB.

**Kluczowe odkrycie:** URL-e sa w pelni przewidywalne, feedu nie trzeba parsowac:

```
https://openzu.cuzk.gov.cz/opendata/{PRODUKT}/epsg-{5514|3045}/{ARKUSZ}.zip
```

Zweryfikowane (HTTP 200):
- `.../opendata/DMR5G/epsg-5514/CTES96.zip` (~4 MB LAZ)
- `.../opendata/DMR4G-TIFF/epsg-5514/CTES96.zip` (~0,75 MB TIFF)
- `.../opendata/DMR5G/epsg-3045/756_5516.zip`
- `.../opendata/DMP1G/epsg-5514/BENE09.zip` (~3 MB)
- `.../opendata/DMPOK-TIFF/epsg-5514/BENE09.zip` (~64 MB)

Katalog `openzu.cuzk.gov.cz/opendata/` zwraca **403** — nie ma listingu, trzeba znac nazwe arkusza.

### 4.2 ArcGIS ImageServer — pobieranie po bbox (odpowiednik WCS)

`https://ags.cuzk.gov.cz/arcgis2/rest/services/{dmr5g|dmr4g|dmp1g|dmp|dmp_obrazova_korelace}/ImageServer`

- DMR 5G: raster **2 m**, `pixelType=F32`, `wkid=5514`, `vcsWkid=8357`
- `maxImageWidth=15000`, `maxImageHeight=4100`
- operacja `exportImage` zwraca **GeoTIFF float32 dla dowolnego bboxa**

Zweryfikowane wywolanie:

```
GET https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer/exportImage
    ?bbox=-447000,-1114000,-446000,-1113000
    &bboxSR=5514&imageSR=5514&size=500,500
    &format=tiff&pixelType=F32&f=image
```

**Reprojekcja po stronie serwera dziala** — `imageSR=2180` zwraca GeoTIFF juz w PL-1992
(zweryfikowane: `PROJCS["ETRF2000-PL / CS92" ... AUTHORITY["EPSG","2180"]]`, res 1 m).
Obszary poza terytorium CZ wypelniane sa zerami.

Dostepne tez uslugi analityczne GPServer: `Profile`, `Visibility`, `SlopeRange`, `SurfaceDifference`,
oraz `Transformacni/TransformaceSouradnic` (oficjalna transformacja wspolrzednych CUZK).

### 4.3 WMS

Standardowe uslugi przegladania (cieniowany relief, nachylenie, ekspozycja) — do podgladu,
nie do analiz. Nie sa potrzebne do pobierania danych, w odroznieniu od GUGiK, gdzie WMS
skorowidzow jest jedyna droga do URL-i OpenData.

---

## 5. ZABAGED — odpowiednik BDOT10k

**ZABAGED** (Zakladni baze geografickych dat) = podstawowa baza danych geograficznych CR,
dokladnosc odpowiadajaca skali 1:10 000. To bezposredni odpowiednik BDOT10k.

### 5.1 Struktura

**149 warstw** (BDOT10k ma 15). Warstwy istotne dla pokrycia/uzytkowania terenu:

| ID | Warstwa | Odpowiednik BDOT10k |
|---|---|---|
| 138 | Orna puda a ostatni dale nespecifikovane plochy | PTGN |
| 139 | Trvaly travni porost | PTTR |
| 140/141/142/144 | Lesni puda (krovinaty porost / kosodrevina / se stromy) | PTLZ |
| 135 | Ovocny sad, zahrada | PTUT |
| 136 / 137 | Vinice / Chmelnice | PTUT |
| 132 | Vodni plocha | PTWP |
| 131 | Bazina, mocal | PTGN |
| 130 | Skalni utvary | PTKM |
| 129 | Sesuv pudy, sut | PTKM |
| 118 | Povrchova tezba, lom | PTKM |
| 117 | Skladka | PTSO |
| 116 | Hrbitov | PTSO |
| 115 | Ostatni plocha v sidlech | PTZB |
| 114 | Areal ucelove zastavby | PTZB |
| 134 | Udrzovana zelen | PTZB |
| 99 | Budova jednotliva nebo blok budov (plocha) | BUBD |
| 93 | Vodni tok | SWRS |
| 112 | Brehova cara | SWKN |
| 113 | Rozvodnice | — (dzial wodny, brak w BDOT10k) |
| 79-84 | Silnice, cesty, pesiny, ulice | SKDR |
| 75-76 | Zeleznicni trat, vlecka | SKTR |

Do tego warstwy punktowe/liniowe: obiekty inzynierskie, infrastruktura, ochrona przyrody,
punkty osnowy, granice administracyjne, obiekty hydrotechniczne.

Osobna usluga: **ZABAGED_VRSTEVNICE** (warstwice) — czesc wysokosciowa ZABAGED.

### 5.2 Sposoby dostepu

**A) ATOM — caly kraj w jednym pliku (problematyczne)**

```
https://openzu.cuzk.gov.cz/opendata/ZABAGED-GPKG/epsg-5514/ZABAGED-5514-gpkg-20260706.zip  ->  5,80 GB
https://openzu.cuzk.gov.cz/opendata/ZABAGED-GPKG/epsg-3045/ZABAGED-3045-gpkg-20260706.zip  ->  6,73 GB
```

Brak podzialu na powiaty/arkusze — w odroznieniu od BDOT10k (per TERYT).
**Dla Kartografa to sciezka nieakceptowalna** przy pobieraniu malego obszaru.
Nazwa pliku zawiera date wydania, wiec wymaga odczytu feedu.

**B) ArcGIS REST MapServer — zapytanie po bboxie (zalecane)**

```
https://ags.cuzk.gov.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer/{layerId}/query
```

- `maxRecordCount = 2000`, paginacja przez `resultOffset` / `resultRecordCount`
- flaga `exceededTransferLimit` w odpowiedzi sygnalizuje kolejna strone
- `f=geojson`, `f=json`, filtr `geometry` + `geometryType=esriGeometryEnvelope`
- **`outSR=2180` — reprojekcja po stronie serwera dziala**

Zweryfikowane zapytanie (warstwa 138, okolice Czeskiego Cieszyna) zwrocilo 40 obiektow;
z `outSR=2180` geometria przyszla juz w PL-1992, z atrybutami `fid_zbg`, `typ_pudy_k`, `typ_pudy_p`.

**C) OGC WFS 2.0.0**

```
https://ags.cuzk.gov.cz/arcgis/services/ZABAGED_POLOHOPIS/MapServer/WFSServer
```

- GML 3.2 / GML3 / GML2 / GeoJSON (+ warianty GZIP/ZIP)
- **limit 1000 obiektow** na zapytanie (mniej niz REST)
- deklaruje wylacznie `urn:ogc:def:crs:EPSG::5514` — brak reprojekcji po stronie serwera

**Wniosek:** ArcGIS REST jest lepszy od WFS (wiekszy limit + reprojekcja). WFS tylko jesli
zalezy nam na czystym OGC.

---

## 6. Godla / klad arkuszy

### 6.1 SM5 (Statni mapa 1:5 000)

- **16 301 arkuszy**, kazdy **2 x 2,5 km** (5 km2)
- Klad rownolegly do osi S-JTSK
- Nomenklatura: nazwa arkusza SM50 + podzial na 100 czesci, np. `Cesky Tesin 8-6`
- Kod pliku: `CTES86`, `BENE09`, `OSTR08` — 4 litery nazwy miasta + 2 cyfry

**Nomenklatura NIE jest arytmetyczna** — zalezy od nazwy miasta arkusza SM50.
Wymagany indeks arkuszy (patrz 6.3).

### 6.2 Siatka ETRS89/TM33N 2 x 2 km

- **20 308 kafli**, nomenklatura `{E_km}_{N_km}` = **naroznik SW**, np. `302_5550`
  => E 302 000..304 000, N 5 550 000..5 552 000 (zweryfikowane wzgledem `georss:polygon`)
- **W pelni obliczalna** — nie wymaga indeksu. To analogia do PL-2000 w Kartografie.

### 6.3 Usluga indeksu arkuszy (skorowidz)

```
https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer
```

| Warstwa | Zawartosc |
|---|---|
| **24** | Klad listu SM 5 (Ortofoto, DMR, DMP) / S-JTSK |
| **26** | Klad listu DMR, DMP / ETRS89 |
| 0-23 | Klady ZTM 5..250 w S-JTSK i ETRS89 |
| 32-41 | Klady ZM 10..200 |

Warstwa 24 — atrybuty: `MAPNOM` (= `CTES86`, dokladnie nazwa pliku w openzu), `MAPNAME`
(= `Cesky Tesin 8-6`), `PODIL` (udzial arkusza w terytorium CZ — istotne dla arkuszy przygranicznych).
Warstwa 26 — `MAPNOM` (= `756_5516`), `IN_CZ`.

To bezposredni odpowiednik skorowidzow WMS GUGiK, ale **w formie zapytywalnej po bboxie**,
co jest znacznie wygodniejsze niz `GetFeatureInfo` w GUGiK.

---

## 7. Sprowadzenie danych czeskich do polskiego ukladu odniesienia

### 7.1 Poziomo: S-JTSK (EPSG:5514) -> PL-1992 (EPSG:2180)

PROJ/pyproj obsluguje to bez dodatkowych plikow. Dostepne operacje (zweryfikowane, PROJ 9.5.1):

| Dokladnosc | Operacja | Uzywalna w CZ? |
|---|---|---|
| 0,051 m | via `S-JTSK [JTSK03]`, siatka `sk_gku_JTSK03_to_JTSK.tif` | **NIE** — siatka slowacka, poza SK zwraca `inf` |
| **0,5 m** | `S-JTSK to ETRS89 (3)` + `ETRF2000-PL` + CS92, Helmert 7-param. | **TAK — najlepsza realnie dostepna** |
| 1,0 m | `S-JTSK to ETRS89 (1)` | tak (**domyslny wybor PROJ**) |
| 1,0 m | `S-JTSK to ETRS89 (4)` | tak |
| 2,0 m | via WGS 84 (5) | tak |
| 7,0 m | via WGS 84 (3) | tak |

**Pulapka nr 1:** operacja o najlepszej deklarowanej dokladnosci (0,051 m) opiera sie na
siatce **slowackiej** (`sk_gku_*`). Dla punktow w Czechach transformacja zwraca `inf`,
przy czym PROJ raportuje ja jako "dostepna". Trzeba to jawnie odfiltrowac.

**Pulapka nr 2:** PROJ domyslnie wybiera operacje 1,0 m, nie 0,5 m. Roznica miedzy nimi
to ok. **1,1 m** w polnocnej wspolrzednej (zmierzone dla punktu przy Czeskim Cieszynie:
`473063,755 / 208804,981` vs `473063,707 / 208803,837`). Rozrzut miedzy wszystkimi
operacjami bezsiatkowymi siega **3 m**.

=> **Transformacje trzeba przypiac jawnie**, nie polegac na domyslnym wyborze PROJ.

**Pulapka nr 3:** EPSG:5514 ma osie X (easting), Y (northing) i wspolrzedne ujemne.
Zawsze `always_xy=True` albo swiadoma obsluga kolejnosci osi.

**Alternatywa o wyzszej dokladnosci — reprojekcja po stronie serwera CUZK.**
Zarowno ImageServer (`imageSR=2180`) jak i MapServer (`outSR=2180`) reprojektuja same,
uzywajac wewnetrznej transformacji ESRI/CUZK. To eliminuje problem doboru operacji PROJ
po naszej stronie. Dodatkowo CUZK udostepnia oficjalna usluge
`arcgis2/rest/services/Transformacni/TransformaceSouradnic` (GPServer).

### 7.2 Pionowo: Bpv (EPSG:8357) -> uklady polskie

| Cel | EPSG | Status w PROJ | Dokladnosc |
|---|---|---|---|
| **EVRF2007** | 5621 | **dostepna** (`Baltic 1957 height to EVRF2007 height (1)`) | **0,1 m** |
| Kronsztadt'86 | 9650 | **brak** — tylko ballpark | — |
| EVRF2007-PL | 9651 | **brak** — tylko ballpark | — |

Zmierzone przesuniecie **Bpv -> EVRF2007** na terytorium CZ: **+0,117 do +0,143 m**
(rosnie z poludnia na polnoc; pas przygraniczny z Polska ok. **+0,128 do +0,143 m**).

Brakujace transformacje do ukladow polskich wymagaja siatek GUGiK **`pl86_2019z.asc`**
(Kronsztadt'86 <-> EVRF2019) i **`pl07_2019z.asc`** (EVRF2007-PL <-> EVRF2019).
PROJ raportuje je jako `open_license=False, direct_download=False` — **nie ma ich na
cdn.proj.org** i nie da sie ich pobrac automatycznie.

**Rekomendowana sciezka pionowa:**

```
Bpv (8357)  --[EPSG op, 0,1 m]-->  EVRF2007 (5621)  ~=  EVRF2007-PL (9651)
```

Poniewaz Kartograf juz dzis pracuje na NMT GUGiK w EVRF2007, sprowadzenie danych czeskich
do EVRF2007 daje **spojnosc wysokosciowa z polska czescia danych bez zadnych brakujacych siatek**.
EVRF2007-PL jest krajowa realizacja EVRF2007 — roznice sa rzedu centymetrow, znacznie ponizej
dokladnosci samego DMR 5G (0,18 m).

Dla trybu KRON86 nie ma automatycznej sciezki. Opcje:
- (a) wymagac od uzytkownika recznego zainstalowania siatek GUGiK do katalogu PROJ,
- (b) zastosowac stale przesuniecie przyblizone i **jawnie to zaraportowac**,
- (c) nie wspierac KRON86 dla danych czeskich i wymuszac EVRF2007.

Rekomendacja: **(c) z opcja (a)** — wymuszac EVRF2007, a jesli uzytkownik dostarczy siatki,
pozwolic PROJ na pelna sciezke.

### 7.3 Pulapka: DMR 4G GeoTIFF nie ma osadzonego CRS

Pobrany `CTES96.tif` z `DMR4G-TIFF`: `crs = None`, georeferencja wylacznie w pliku
sidecar `.tfw`, `nodata = -9999`, `float32`, 500 x 400 px @ 5 m.
Przy wczytywaniu trzeba **jawnie przypisac EPSG:5514**, inaczej reprojekcja sie nie powiedzie.

---

## 8. Ograniczenia — podsumowanie

| Ograniczenie | Szczegoly |
|---|---|
| ZABAGED plikowo | tylko caly kraj, 5,8 / 6,7 GB — brak podzialu na jednostki administracyjne |
| ArcGIS REST | 2000 obiektow/zapytanie, wymagana paginacja |
| WFS | 1000 obiektow/zapytanie, brak reprojekcji |
| ImageServer | maks. 15000 x 4100 px na zadanie |
| `openzu` | brak listingu katalogow (403), wymagana znajomosc nazwy arkusza |
| Nomenklatura SM5 | nieobliczalna, wymaga uslugi indeksu |
| Siatki wysokosciowe PL | `pl86_2019z` / `pl07_2019z` niedostepne publicznie |
| Transformacja pozioma | brak otwartej siatki dla CZ; najlepiej 0,5 m (Helmert) lub reprojekcja serwerowa |
| Feedy ATOM | 24-30 MB, kosztowne do parsowania — lepiej uzywac indeksu arkuszy |

Czego **nie ma** jako ograniczenia (w odroznieniu od GUGiK): brak kluczy API, brak OAuth,
brak limitow wolumenu, brak luk w pokryciu, brak problemu "1m jest, 5m nie ma".

---

## 9. Wnioski dla architektury Kartografa

Mapowanie na istniejace abstrakcje:

| Kartograf | Odpowiednik czeski |
|---|---|
| `GugikProvider` (NMT) | `CuzkDmrProvider` — DMR 5G (raster 2 m / LAZ) i DMR 4G (5 m TIFF) |
| `GugikNmptProvider` | `CuzkDmpProvider` — DMP 1G / DMP OK |
| `GugikOrtoProvider` | `CuzkOrtoProvider` — Ortofoto CR, JPEG, arkusze SM5 |
| `GugikLazProvider` | pokryte przez `CuzkDmrProvider` (LAZ to natywny format DMR) |
| `Bdot10kProvider` | `ZabagedProvider` — ArcGIS REST po bboxie zamiast pobierania pliku |
| skorowidze WMS GUGiK | `KladyMapovychListu` MapServer (warstwy 24 i 26) |
| `SheetParser` / `Parser2000` | parser SM5 (wymaga indeksu) + parser siatki TM33 (obliczalny) |
| `MetadataCache` | cache indeksu arkuszy SM5 — idealny kandydat, indeks jest statyczny |

Trzy obserwacje projektowe:

1. **Siatka ETRS89/TM33 2x2 km jest obliczalna** i strukturalnie odpowiada PL-2000 —
   mozna ja obsluzyc bez zadnych zapytan sieciowych, dokladnie tak jak `Parser2000`.
2. **`exportImage` po bboxie** jest znacznie prostszy niz sciezka arkuszowa i pokrywa
   glowny przypadek uzycia (analiza transgraniczna dla zadanego obszaru). Sciezka arkuszowa
   ma sens tylko dla LAZ i ortofoto.
3. **Reprojekcja po stronie serwera CUZK** (`imageSR` / `outSR`) rozwiazuje problem transformacji
   poziomej lepiej niz cokolwiek dostepnego lokalnie w PROJ. Zostaje tylko transformacja
   pionowa Bpv -> EVRF2007, ktora PROJ wykonuje z dokladnoscia 0,1 m.

---

## 10. Zweryfikowane endpointy (skrot)

```
# Indeks arkuszy
https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/24/query   # SM5
https://ags.cuzk.gov.cz/arcgis/rest/services/KladyMapovychListu/MapServer/26/query   # TM33 2x2 km

# Rastry wysokosciowe po bboxie
https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr5g/ImageServer/exportImage
https://ags.cuzk.gov.cz/arcgis2/rest/services/dmr4g/ImageServer/exportImage
https://ags.cuzk.gov.cz/arcgis2/rest/services/dmp1g/ImageServer/exportImage
https://ags.cuzk.gov.cz/arcgis2/rest/services/dmp_obrazova_korelace/ImageServer/exportImage

# Pliki (LAZ / TIFF / JPEG)
https://openzu.cuzk.gov.cz/opendata/{DMR5G|DMR4G|DMR4G-TIFF|DMP1G|DMPOK-TIFF}/epsg-{5514|3045}/{ARKUSZ}.zip

# ZABAGED
https://ags.cuzk.gov.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer/{0..151}/query
https://ags.cuzk.gov.cz/arcgis/services/ZABAGED_POLOHOPIS/MapServer/WFSServer          # WFS 2.0.0
https://ags.cuzk.gov.cz/arcgis/rest/services/ZABAGED_VRSTEVNICE/MapServer              # warstwice

# ATOM
https://atom.cuzk.gov.cz/{THEME}/{THEME}.xml
https://atom.cuzk.gov.cz/describe.ashx?theme={THEME}                                    # OpenSearch, max 100 wynikow
```

---

## 11. Zrodla

- [Geoportal CUZK](https://geoportal.cuzk.cz/)
- [Stahovaci sluzby ATOM](https://atom.cuzk.gov.cz/)
- [DMR 5G — techniczna zprava (PDF)](https://geoportal.cuzk.gov.cz/Dokumenty/TECHNICKA_ZPRAVA_DMR_5G.pdf)
- [DMR 5G / ETRS89-TMzn, EVRS — metadane](https://geoportal.cuzk.cz/Default.aspx?mode=TextMeta&metadataXSL=full&side=vyskopis&metadataID=CZ-CUZK-DMR5G-ETRS89-V)
- [ZABAGED — polohopis](https://geoportal.cuzk.cz/Default.aspx?mode=TextMeta&metadataID=CZ-CUZK-ZABAGED-VP&metadataXSL=full&side=zabaged)
- [WFS ZABAGED — metadane uslugi](https://geoportal.cuzk.cz/Default.aspx?mode=TextMeta&side=wfs&metadataID=CZ-CUZK-WFS-ZABAGED&metadataXSL=metadata.sluzba)
- [Ortofoto CR — informacje](https://geoportal.cuzk.cz/Default.aspx?mode=TextMeta&text=ortofoto_info&side=ortofoto&menu=23)
- [Narodni katalog otevrenych dat (NKOD)](https://data.gov.cz/)
