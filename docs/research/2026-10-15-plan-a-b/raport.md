# Plany A/B: pomiary skorowidzy GUGiK i uslug CUZK (2026-10-15)

**Cel:** dane do planow A (`elevation` PL) i B (`elevation` CZ) podprojektu 3:
jakie rozdzielczosci, formaty i uklady publikuje GUGiK w skorowidzach
NMT/NMPT, ktora usluga skorowidza je pokazuje, jak szybko odpowiada,
oraz jak CUZK publikuje DMR 4G ETRS89, DMP OK, DMP 1G i LAZ.

**Metoda:** wylacznie metadane - WFS 2.0.0 (`GetCapabilities`,
`GetFeature` z `PROPERTYNAME`, `COUNT`, `STARTINDEX`, `BBOX`), WMS 1.3.0
`GetFeatureInfo` przez kod Kartografa (`query_skorowidz_layer`), ArcGIS
`ImageServer?f=json` i `/query`, ATOM CUZK, katalog metadanych CUZK (CSW)
oraz `HEAD` plikow. Jedyny pobrany plik danych: archiwum NMT 25 m
`M-34-64-D-d-2-1` (862 166 B) do sprawdzenia formatu. Skrypty i surowe
wyniki leza w `<katalog-danych>` (poza repo). Punkty kontrolne: Krakow
E 565000-569000, N 242000-246000; Pomorze E 339000-343000,
N 744800-747000 (EPSG:2180).

## 1. Pelna inwentaryzacja skorowidzy WFS NMT/NMPT (PL)

Uslugi `https://mapy.geoportal.gov.pl/wss/service/PZGIK/<usluga>/WFS/Skorowidze`,
typy obiektow `gugik:SkorowidzNMT<rok>` / `gugik:SkorowidzNMPT<rok>`
(jeden rok na warstwe, bez warstw zbiorczych). Przejrzane WSZYSTKIE
rekordy wszystkich warstw (strony po 2500-5000 rekordow, stronicowanie
po atrybucie `next`; 197 stron, ok. 8 min dla czterech uslug
rownolegle):

| Usluga | Warstwy (lata) | Rekordy | `czy_ark_wypelniony` |
|---|---|---|---|
| `NumerycznyModelTerenuEVRF2007` | 2018-2026 (9) | 399 288 | TAK 392 013, NIE 7 275 |
| `NumerycznyModelTerenuKRON86` | 2000, 2004-2019 (17) | 277 889 | TAK 274 928, NIE 2 961 |
| `NumerycznyModelPokryciaTerenuEVRF2007` | 2019-2026 (8) | 80 515 | TAK 77 119, NIE 3 396 |
| `NumerycznyModelPokryciaTerenuKRON86` | 2010-2019 (10) | 131 001 | TAK 130 699, NIE 302 |

Pola rekordu: `godlo`, `akt_data`, `akt_rok`, `dt_pzgik`, `char_przestrz`,
`uklad_xy`, `uklad_h`, `format`, `url_do_pobrania`, `nr_zglosz`,
`czy_ark_wypelniony`, `zrodlo_danych`, `blad_sr_wys`, `blad_sr_syt`,
`modul_archiwizacji`, `asortyment` + geometria arkusza (`msGeometry`).
`numberMatched` bywa `unknown`; serwer **ignoruje parametr `FILTER`**
(zapytanie `char_przestrz = 0.50 m` z `RESULTTYPE=hits` zwrocilo 2010
trafien w warstwie z 1/5/25 m), wiec filtr rozdzielczosci i formatu
jest zawsze po stronie klienta.

### 1.1 Siatki `ARC/INFO ASCII GRID` (plik `.asc`)

| Produkt, uklad wysokosci | Rozdzielczosc | Uklad | Rekordy | Lata |
|---|---|---|---|---|
| NMT EVRF2007 | 0,15 m | PL-2000 | 88 | 2023 |
| | 0,5 m | PL-1992 / PL-2000 | 1 815 / 17 202 | 2021-2026 / 2018-2025 |
| | 0,6 m | PL-1992 | 59 | 2022-2024 |
| | 1 m | PL-1992 / PL-2000 | 141 942 / 10 057 | 2019-2026 / 2018-2026 |
| | 5 m | PL-1992 / PL-2000 | 131 214 / 12 | 2019-2025 / 2021 |
| | 10 m | PL-2000 | 12 | 2021 |
| NMT KRON86 | 0,5 m | PL-2000 | 7 251 | 2018-2019 |
| | 1 m | PL-1992 / PL-2000 | 69 113 / 28 994 | 2010-2018 / 2016-2019 |
| NMPT EVRF2007 | 0,5 m | PL-1992 / PL-2000 | 13 093 / 15 793 | 2019-2026 / 2020-2025 |
| | 0,6 m | PL-1992 | 26 | 2024 |
| | 1 m | PL-1992 / PL-2000 | 51 040 / 563 | 2019-2025 / 2020 |
| NMPT KRON86 | 0,5 m | PL-1992 / PL-2000 | 4 374 / 79 | 2010-2018 / 2019 |
| | 1 m | PL-1992 | 61 107 | 2010-2018 |

NMT 5 m jako siatka `.asc` istnieje wylacznie w EVRF2007 - regula
"5m tylko EVRF2007" jest prawdziwa dla siatek. 42 rekordy NMT EVRF2007
2019 maja `format = ARC/INFO ASCII GRID`, ale URL konczy sie `.xyz`
(np. `72675_858106_N-33-69-A-d-1-3.xyz`) - rekord niespojny.

### 1.2 Formaty archiwalne (nie siatka `.asc`)

| Format (`format`) | Plik | Rozdzielczosci (`char_przestrz`) | Glownie |
|---|---|---|---|
| `ASCII XYZ GRID` | `<godlo>.xyz.zip`, `.zip` | 0,5; 1; 5 m | EVRF2007 2018-2020, KRON86 2010-2018 (te same arkusze i zgloszenia co `.asc`) |
| `ASCII NMT` | `<godlo>.zip`, `NMT-<godlo>.zip` | 0,5; 1; 5; 10 m | EVRF2007 2019, KRON86 5 m 2019 |
| `ASCII TBD` | `<godlo>_asc.zip`, `.zip` | 1; 5; 10; 15; 20; 25; 30; 40; 50 m | EVRF2007 2018-2020, KRON86 2000-2019 |
| `ESRI TIN` | `<godlo>_tin.zip` | brak | KRON86 2000-2010 |
| `Intergraph TTN` | `<godlo>.ttn` | brak | KRON86 2000-2010 |
| `Intergraph GRD` | `<godlo>.grd` | 5 m | KRON86 2009-2017 |
| `Warstwice DXF` / `DGN` | `.dxf` / `.dgn` | 25 m | KRON86 2004-2005 |

Archiwum `ASCII TBD` 25 m `70952_856359_M-34-64-D-d-2-1_asc.zip`: szesc
plikow `.ASC` (punkty `X Y Z` w `_p`, puste `_j` i `_z`), bez naglowka
`ncols/nrows/cellsize` - to nie raster Arc/Info. Rekordy archiwalne
starszych lat KRON86 sa czesto w arkuszach 1:25000 (godlo 6-czlonowe,
np. `N-34-58-D-c-3`), a nie 1:10000. W 18 003 (NMT EVRF2007), 87 100
(NMT KRON86) i 64 663 (NMPT KRON86) parach warstwa-arkusz ten sam
arkusz i to samo zgloszenie maja dwa pliki w roznych formatach
(np. `.asc` + `.xyz.zip`, `.xyz.zip` + `_asc.zip`).

### 1.3 WMS a WFS

Kartograf pobiera dzis rekordy arkuszy NMT/NMPT z WMS `GetFeatureInfo`:
`NMT|NMPT/WMS/SkorowidzeUkladEVRF2007` (warstwy 2026, 2025, 2024,
`2023iStarsze`), `.../SkorowidzeUkladKRON86` (2019, 2018,
`2017iStarsze`) i `NMT/WMS/SheetsGrid5mEVRF2007` (5 m). Sprawdzenie
na arkuszach z obu uslug:

- WMS `SkorowidzeUklad*` zwraca siatki `.asc` 0,15 m, 0,5 m, 0,6 m i 1 m
  (`7.159.25.12.2`, `N-33-77-B-c-3-3`, `6.130.26.07.1.2` KRON86), nie
  zwraca 5 m, 10 m ani zadnego formatu archiwalnego; `SheetsGrid5mEVRF2007`
  zwraca 5 m, nie zwraca 10 m (`6.125.25`: WFS ma 5 m i 10 m 2021).
- Dla `M-33-59-D-a-2-1` i `M-34-64-D-d-2-1` zbior rekordow `.asc` 1 m
  i 5 m z WMS jest identyczny ze zbiorem `.asc` z WFS (te same URL);
  WFS ma dodatkowo rekordy archiwalne (XYZ 2018, ASCII NMT 2019, TBD 25 m).
- Czas: `GetFeature` z `BBOX` 4x4 km (Krakow) na kazda z 9 warstw NMT
  EVRF2007 - 0,2-0,3 s na warstwe, 1,8 s razem; `BBOX` w osiach N,E
  z URN `urn:ogc:def:crs:EPSG::2180` (jak LAZ). Jedno zapytanie z
  `TYPENAMES` wszystkich 17 warstw NMT KRON86 (kwadrat 20 m w srodku
  `M-34-64-D-d-2-1`) - 0,69 s, obiekty z czterech warstw, `numberMatched`
  podane; arkusz na morzu `N-33-46-C-c-3-2` - `numberReturned=0`,
  `numberMatched=unknown` (poprawna pusta odpowiedz).

Wniosek dla planu A: WFS jest nadzbiorem WMS dla siatek i jedynym
zrodlem 10 m oraz raportu dostepnosci; pobieranie i raport na jednym
indeksie nie moga sie rozjechac.

### 1.4 Oczekiwane wyniki raportu dostepnosci (punkty kontrolne)

Metoda jak `pokrycie.md`: rekordy siatek `.asc` z jednego zapytania
obszarowego na usluge (wszystkie warstwy), obrysy arkuszy z `msGeometry`,
rasteryzacja na siatce 1 m (srodki pikseli), lad z
`providers/pl/prg.py::fetch_land_mask` (A00 - W02 - W03).

| Obszar | Usluga | Kombinacja | TAK / NIE | Komplet | Ladu bez arkusza |
|---|---|---|---|---|---|
| Krakow (lad 16 000 000 m2) | NMT EVRF2007 | PL-1992 1 m: 2025, 2024, 2023, 2022, 2019 | 6 / 0 kazda | tak | 0 |
| | | PL-2000 1 m: 2023, 2021 | 15 / 0 kazda | tak | 0 |
| | | PL-1992 5 m 2019 | 6 / 0 | tak | 0 |
| | NMT KRON86 | PL-1992 1 m: 2017, 2012 | 6 / 0 kazda | tak | 0 |
| | NMPT EVRF2007 | PL-1992 0,5 m: 2025, 2023; PL-2000 0,5 m: 2023, 2021 | 6 albo 15 / 0 | tak | 0 |
| | NMPT KRON86 | PL-1992 0,5 m: 2017, 2012 | 6 / 0 kazda | tak | 0 |
| Pomorze (lad 863 767 m2) | NMT EVRF2007 | PL-1992 0,5 m 2025 | 0 / 4 | nie | 0 |
| | | PL-1992 1 m 2022 | 3 / 0 | nie | 8 782 m2 |
| | | PL-1992 0,5 m 2022, 2021 | 1 / 3 kazda | nie | 0 |
| | | PL-1992 5 m 2025 / 2023 | 3 / 0, 3 / 2 | nie | 8 782 m2 |
| | NMT KRON86 | PL-1992 1 m 2011 | 3 / 0 | nie | 8 782 m2 |
| | NMPT EVRF2007 | PL-1992 0,5 m 2025; 1 m 2022 | 0 / 4; 3 / 0 | nie | 0; 8 782 m2 |

Arkusze `NIE` Pomorza 2025: `N-33-58-A-c-1-3`, `N-33-58-A-c-1-4`,
`N-33-58-A-c-2-3`, `N-33-58-A-c-3-1` (zgloszenie `DFT.7201.024.2024`,
`akt_data` 2025-01-30). Krakow 2018 nie ma siatek `.asc` - tylko archiwa
(XYZ 1 m x4, XYZ 5 m x2, TBD 25 m x2) i ASCII NMT 5 m 2019 (x6); KRON86
dodatkowo XYZ 2012-2017, TBD 15 m, TIN i TTN 2009.

### 1.5 Nazwy plikow a regula B4

`verify_record_url` (`kartograf/download/campaigns.py:511`) bierze ostatni
czlon `_` z nazwy pliku bez ostatniego rozszerzenia. Dla siatek
(`83137_1729555_M-34-64-D-d-2-1.asc`, `70043_816450_6.130.26.07.1.2.asc`)
daje godlo; dla archiwow nie (`.xyz.zip`, `_asc.zip`, `_tin.zip`,
`NMT-<godlo>.zip`). Dopoki pobierane sa tylko siatki `.asc`, regula
zostaje bez zmian.

## 2. Pozostale ustalenia PL (z sond 2026-10-15)

- Arkusze 0,5 m z probek katalogu: NMT `N-33-58-A-c-1-4` (zgloszenie
  84020, 4202x2600 px, piksel 0,5 m) i NMPT `N-33-58-A-d-1-2` (84018);
  WMS i WFS zwracaja je w warstwie 2025.
- Wycinek WCS (`docs/research/2026-10-11-wcs-cutouts/raport.md` 2-3) daje
  technicznie 0,5 m, ale jest kompozycja lotow serwera; spec 3.2 zostawia
  `--cutout` w 1 m.
- `pokrycie.md` (dodatek): pelne kafle LAZ tej samej kampanii nie wyznaczaja
  zasiegu NMT/NMPT; raport LAZ ocenia wylacznie kafle LAZ.

## 3. CUZK (CZ)

### 3.1 ImageServer

`https://ags.cuzk.gov.cz/arcgis2/rest/services/<model>/ImageServer?f=json`:
`dmr5g` 2 m, `dmr4g` 5 m, `dmp1g` 2 m, `dmp_obrazova_korelace` 0,5 m,
`dmp` 0,5 m; wszystkie `pixelType=F32`, `wkid=5514`, `vcsWkid=8357`,
`maxImageWidth=15000`, `maxImageHeight=4100`. `dmp` ma ten sam opis
uslugi (DMP OK) i ten sam katalog rastrow co `dmp_obrazova_korelace` -
alias. `/query` katalogu (`outFields=*`, punkt w `CTES96`) zwraca tylko
pozycje mozaiki (`Name`, `LowPS`, `HighPS`, `Category`) - **bez dat
nalotu**; z ImageServer nie da sie zbudowac tabeli lotow CZ.

### 3.2 Pliki `openzu` (HEAD, 2026-10-15)

`https://openzu.cuzk.gov.cz/opendata/<PRODUKT>/epsg-<5514|3045>/<arkusz>.zip`
(host `openzu.cuzk.cz` daje te same naglowki); SM5 dla `epsg-5514`,
kafel TM33 2x2 km dla `epsg-3045`:

| Produkt | `epsg-5514` (SM5 `CTES96`) | `epsg-3045` (TM33 `760_5518`) | Zawartosc ZIP |
|---|---|---|---|
| `DMR5G` | 3 199 272 B, LM 2026-01-19 | 265 558 B, LM 2026-01-19 | jeden `.laz` |
| `DMR4G` | 181 248 B | 14 166 B | jeden `.laz` |
| `DMR4G-TIFF` | 752 795 B | 59 307 B | `.tif` + `.tfw` |
| `DMP1G` | 3 780 167 B, LM 2023-06-12 | 252 698 B | jeden `.laz` |
| `DMPOK-TIFF` | 65 832 922 B, LM 2025-10-10 | 4 196 915 B, LM 2026-08-20 | `.tif` + `.tfw` |
| `DMPOK-LAZ` | 350 156 715 B | 26 587 004 B | jeden `.laz` |

Kazda odpowiedz 200 ma `ETag` i `Last-Modified` (sygnal `http`).
`DMR5G-TIFF` i `DMP1G-TIFF` - 404 (rastrow arkuszowych tych modeli nie
ma; tylko ImageServer). Nieznany arkusz - 404 `text/html` (1245 B).
TIFF TM33 (`DMR4G-TIFF/epsg-3045/760_5518`): 400x400 px, float32,
nodata -9999, **bez CRS w pliku** - georeferencja w `.tfw`, CRS z
nazwy uslugi (EPSG:3045), tak jak dzisiejsze arkusze SM5 (EPSG:5514
nadawany przez `_assign_crs`).

### 3.3 Uklad wysokosci plikow ETRS89

Metadane zbiorow `CZ-CUZK-DMR5G-ETRS89-V` i `CZ-CUZK-DMR4G-ETRS89-V`
(katalog `geoportal.gov.cz`, CSW `GetRecordById`): `referenceSystemIdentifier`
= `EPSG:3045` (ETRS89 / TM33N) i `EPSG:5621` (EVRF2007 height), opis
"height system EVRS". Pliki `epsg-3045` maja wiec wysokosci EVRF2007
natywnie, a `epsg-5514` - Bpv (EPSG:8357). Kartograf zapisuje dzis
EVRF2007 dla CZ jako transformacje Bpv -> EVRF2007 (EPSG:5621).

### 3.4 ATOM a `Last-Modified`

Feedy uslug ATOM (`https://atom.cuzk.gov.cz/<TEMAT>/<TEMAT>.xml`) maja po
jednym wpisie na arkusz (feed zbioru `datasetFeeds/...<arkusz>.xml` z linkiem
do pliku i `length`); rozmiar feedu uslugi 24-31 MB. Porownanie dla tych
samych plikow: `<updated>` wpisu = `Last-Modified` pliku co do sekundy
(DMR5G `BENE09`, DMP1G `BENE09`, DMPOK-TIFF `302_5550`), w zimie z bledna
strefa (`2026-01-20T08:42:33+02:00` wobec `Tue, 20 Jan 2026 07:42:33 GMT`
dla `DMR4G-TIFF/epsg-3045/302_5550`). ATOM nie wnosi informacji ponad
`HEAD` pliku; to data publikacji, nie nalotu.

### 3.5 Indeks arkuszy

`KladyMapovychListu/MapServer` warstwa 24 (SM5, pola `MAPNOM`, `MAPNAME`,
`PODIL` - udzial arkusza w terytorium CZ) i 26 (TM33, `MAPNOM`, `IN_CZ`).
`PODIL` nie mowi nic o pelnosci danych produktu; dostepnosc pliku
potwierdza tylko `HEAD`.

## 4. Wnioski dla planow

1. Plan A: wszystkie siatki `.asc` NMT/NMPT z tabeli 1.1 (0,15; 0,5; 0,6;
   1; 5; 10 m; w KRON86 0,5 i 1 m), rekordy z WFS (pobieranie i raport),
   filtr rozdzielczosci, formatu i rozszerzenia URL po stronie klienta.
2. Formaty archiwalne z tabeli 1.2 sa osobnym produktem (inne formaty,
   inne skale arkuszy, inne nazwy plikow) - poza zaakceptowanym zakresem
   specu (3.2); raport dostepnosci je pokazuje jako informacje,
   pobieranie wymaga decyzji uzytkownika.
3. Plan B: DMR 4G i DMP OK maja pliki TM33 z wysokosciami EVRF2007
   natywnie; DMP 1G i DMR 5G - tylko ImageServer i LAZ; DMP OK
   z ImageServer `dmp_obrazova_korelace` (bez aliasu `dmp`); raport CZ
   z indeksu arkuszy i `HEAD` (bez ATOM, bez lat nalotu).
