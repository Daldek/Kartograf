# SCOPE.md - Zakres Projektu Kartograf
**Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 3.28
**Data:** 2026-10-17
**Status:** Wydanie v0.8.0 (2026-10-17)

---

## 1. Cel Projektu

**Kartograf** to narzędzie do pobierania danych przestrzennych z publicznych usług GUGiK (Polska), CUZK (Czechy, od v0.7.0), Copernicus i ISRIC: modele wysokościowe i chmury punktów, ortofotomapy i obrazy, pokrycie terenu i gleby, granice, ewidencja i kataster, modele 3D, sieć wodna, nazwy geograficzne, mapy topograficzne i osnowy geodezyjne (sekcja 2). Kolejne kraje (DE, SK) — sekcja 3.1.

### 1.1 Problem

Pobieranie danych przestrzennych z różnych źródeł wymaga:
- Znajomości systemów identyfikacji (godła, TERYT, bbox)
- Nawigowania przez różne interfejsy webowe i API
- Ręcznej organizacji pobranych plików
- Różnych protokołów autentykacji (OAuth2, API keys)

### 1.2 Rozwiązanie

Kartograf automatyzuje ten proces oferując:
- **Unified API** - jednolity interfejs dla różnych źródeł danych
- **Parser godeł** - walidacja i parsowanie godeł map topograficznych
- **Providery danych** - abstrakcja nad różnymi serwisami (GUGiK, CUZK, Copernicus, ISRIC)
- **Selekcja obszaru** - godło, bbox, plik geometrii (SHP/GPKG), kod jednostki (TERYT, KU), cały kraj
- **Automatyczne pobieranie** - pobieranie wielu plików jedną komendą
- **Organizacja plików** - automatyczna struktura katalogów

### 1.3 Użytkownicy

1. **Deweloperzy Hydrograf/Hydrolog** - integracja jako biblioteka Python
2. **Specjaliści GIS** - CLI do pobierania danych
3. **Hydrolodzy** - dane glebowe i HSG dla metody SCS-CN

---

## 2. Zakres - Wersja 0.8.0

### 2.1 NMT (Numeryczny Model Terenu) - IN SCOPE

```text
# Funkcjonalności:
- Parser godeł PL-1992 (SheetParser): skale 1:1M do 1:10k
- Parser godeł PL-2000 (Parser2000): skale 1:10k do 1:500, 4 strefy (EPSG:2176-2179)
- Auto-detekcja systemu: SheetParser automatycznie rozpoznaje PL-1992 vs PL-2000
- Hierarchia arkuszy (get_parent, get_children, get_all_descendants)
- Bounding box arkusza (EPSG:2180, EPSG:4326, EPSG:2176-2179)
- Reverse lookup: bbox → godła (find_sheets_for_bbox, find_sheets_2000_for_bbox;
  bbox w EPSG:2180, EPSG:4326 albo EPSG:2176-2179 dla obu systemów)
- Reverse lookup: geometry file → godła (find_sheets_for_geometry)
- Selekcja obszaru: godło, bbox, plik geometrii (SHP/GPKG)
- Pobieranie przez godło → ASC (OpenData); rekord arkusza ze skorowidza
  WFS GUGiK (od 0.8.0; typy roczne z GetCapabilities, twardy filtr godła,
  układu, rozdzielczości i formatu — ADR-041)
- `provider.download_bbox` (poza magazynem wersji): NMT 1 m KRON86
  (TIFF float32), EVRF2007 i NMPT (ASC multipart -> jednopasmowy GeoTIFF
  float32 z wysokosciami), bbox wyrownany do siatki 1 m EPSG:2180;
  `DownloadManager.download_bbox` usuniete w 0.8.0 (D27).
  CLI `--bbox` bez `--cutout`: arkusze OpenData.
- Wycinek bbox z WCS GUGiK: `--cutout --horizontal-crs {EPSG:2180,EPSG:5514,
  EPSG:3045}` w trybie `--bbox`/`--geometry` dla NMT **i NMPT** 1 m
  (`download_pl_cutout`/`check_pl_cutout`; w CLI przez `download_data`);
  maska ladu PRG `A00 - W02 - W03` i nodata -9999 poza ladem,
  0,0 na ladzie zachowane; bbox wyrownany NA ZEWNATRZ do siatki
  arkuszy 1 m (`k + 0,5`), lokalna przypieta reprojekcja.
  WCS pokazuje kompozycje lotow serwera, niekoniecznie najnowszy
  arkusz dokladnie 1 m wg ADR-028; dla lotow 0,5 m wynik 1 m
  jest decymacja. Od 0.8.0 `bbox/<coords>.tif` bez daty jest
  dowiazaniem do wersji; domyslnie lokalna wersja bez zapytan PRG/WCS,
  `--force` pobiera ponownie (ta sama tresc = bez zmian).
  Brak wyboru kampanii/roku; inna rozdzielczość niż 1m i archiwa
  (`--format`) z `--cutout` = `Error:` — pozostają dostępne jako arkusze
  bez tej flagi.
- Rozdzielczości (rejestr wariantów `kartograf.sources.variants`, ADR-041;
  lista: `kartograf elevation list-sources`): siatki ASC EVRF2007 0.15m,
  0.5m, 0.6m, 1m, 5m, 10m; KRON86 0.5m, 1m. `--resolution` jest wymagane,
  gdy format i układ wysokości dają więcej niż jedną etykietę
- Archiwa GUGiK jako pliki źródłowe 1:1 (`--format XYZ|ASCII-NMT|TBD|TIN|
  TTN|GRD|DXF|DGN`, m.in. TBD 1–50 m): bez konwersji, wycinka i mozaiki,
  wersje w magazynie (segment z tokenem formatu, np.
  `nmt/pl_1992_tbd_25m_kron86`); arkusze (różne skale) ze skorowidza
- Układy wysokościowe: KRON86, EVRF2007 (dostępność per wariant z rejestru)
- Raport dostępności (`kartograf elevation availability` /
  `check_availability`, ADR-041): dla obszaru PL kombinacje rok × układ
  arkuszy × rozdzielczość × układ wysokości × format z kompletnością
  pełnych arkuszy (TAK) na lądzie PRG, bez pobierania danych (także NMPT
  i LAZ; USAGE 1.7, ARCHITECTURE 4.9)
- Godło PL-2000 1:10000: w CLI i `download_data` `--scale` jest wymagane
  (błąd przed siecią, lista skal); provider/`DownloadManager` wywołany
  bez skali, gdy GUGiK ma wyłącznie arkusze potomne, daje `NoCoverageError`
  z podpowiedzią `--scale 1:2000` (bez cichego pobrania zastępczego PL-1992)
- NMT 100 m (0.8.0, plan E1, ADR-043 D10): `--resolution 100m` -> pliki
  województw obszaru z feedu ATOM GUGiK (ZIP z XYZ 1:1,
  `nmt/pl_1992_100m/teryt/<woj>.zip`, wydanie 2019); układ wysokości
  nieznany (GUGiK go nie deklaruje: sidecar `vertical_crs: null`
  z adnotacją, `--vertical-crs` = błąd); bez arkuszy, lotów i wycinka
- Godła 8-członowe PL-1992 (0.8.0, plan E1): ćwiartki arkusza 7-członowego
  (`N-34-50-A-c-3-2-3`, etykieta `1:5000`; arkusze true orto)

# Źródło: GUGiK (Główny Urząd Geodezji i Kartografii)
# API: WFS (skorowidz), WCS (wycinek 1 m), OpenData
```

**Etykiety skal (PL-1992).** Etykiety skal Kartografu są o jeden poziom
drobniejsze niż nomenklatura GUGiK: 7-członowe godło (N-34-130-D-d-2-4) ma tu
etykietę `1:10000`, a u GUGiK jest modułem archiwizacji 1:5000; siatka 1-144
(etykieta `1:200000`) ma wymiary oficjalnego arkusza 1:100000 (20' x 30').
Etykiety zostają dla zgodności publicznego API i CLI `--scale`; aliasy
planowane w następnej wersji major (patrz docstring `SheetParser`).

**Konwencja krawędzi.** `find_sheets_for_bbox` / `find_sheets_for_geometry`
wymagają dodatniego pola przecięcia — stykające się krawędzie NIE są
przecięciem. Bbox równy arkuszowi w EPSG:4326 zwraca więc tylko jego własne
arkusze (`N-34-130-D` w skali 1:50000 → 4, nie 9); w EPSG:2180 (domyślny
`--bbox-crs`) obwiednia arkusza przechodzi przez szerszą obwiednię WGS84
i obejmuje fragmenty sąsiadów (16 zamiast 4). Bbox zdegenerowany do punktu →
dokładnie jeden arkusz. Nieznana wartość `sheet_system=` to `ValidationError`.

### 2.2 NMT, NMPT i LAZ — Czechy (CUZK; NMT od v0.7.0, NMPT i LAZ od 0.8.0) - IN SCOPE

```text
# Funkcjonalności (DMR — Digitalni model reliefu, odpowiednik NMT;
# DMP — Digitalni model povrchu, odpowiednik NMPT; model z --resolution):
- DMR 5G (rozdzielczość 2m) — pobieranie po godle TM33 (siatka 2x2 km,
  EPSG:3045, obliczalna) LUB po bbox przez exportImage (ArcGIS ImageServer)
- DMR 4G (rozdzielczość 5m) — pobieranie po godle SM5 (indeks arkuszy
  KladyMapovychListu, EPSG:5514; arkusz istnieje tylko w 5m, więc CLI bez
  `--resolution` pobiera 5m, a `--resolution 2m` z godłem SM5 to błąd)
  LUB po godle TM33 LUB po bbox przez exportImage
- DMP OK (NMPT 0.5m) — jak DMR 4G (arkusz SM5 bez `--resolution`, kafel
  TM33, bbox); DMP 1G (NMPT 2m) — jak DMR 5G (kafel TM33, bbox)
- Gotowe pliki openzu: arkusz SM5 (EPSG:5514, Bpv) i od 0.8.0 kafel TM33
  DMR 4G/DMP OK w EVRF2007 (plik ETRS89, EPSG:3045, bez transformacji);
  pozostałe kafle TM33 = exportImage + lokalny warp na siatkę kafla
- LAZ (`--product laz`): wymagany `--model dmr5g|dmr4g|dmp1g|dmpok`;
  plik .laz 1:1 z ZIP openzu, bez transformacji punktów — `--vertical-crs
  Bpv` = arkusze SM5 (EPSG:5514), `EVRF2007` = kafle TM33 (EPSG:3045);
  godło albo obszar (arkusze z indeksu), bez `--cutout`
- Selekcja obszaru: godło (TM33/SM5), bbox, plik geometrii — `--country
  {pl,cz,auto}`; `auto` wykrywa kraj z godła/bboxa, dzieli bbox/geometrię
  transgraniczną na osobne pliki per kraj (bez scalania — dziś scala
  konsument, np. Hydrograf; scalanie PL+CZ w jedną powierzchnię (R6) nie
  ma przypisanego wydania — sekcja 3.1). Obszar rastra sięgający CZ jest zawsze wycinkiem i wymaga
  `--cutout --horizontal-crs` (ADR-038); pod `auto` część PL jest wtedy
  wycinkiem WCS. LAZ pod `auto`: kafle PL i arkusze CZ w jednym zadaniu
- Reprojekcja pozioma **lokalna** (rasterio.warp + przypięta operacja; serwer
  dostaje żądania wyłącznie w natywnym EPSG:5514 — ADR-024):
  `--cutout --horizontal-crs {EPSG:2180,EPSG:5514,EPSG:3045}` (natywnie
  `EPSG:5514`) — tylko w trybie `--bbox`/`--geometry` (z godłem = błąd)
  krok datum S-JTSK → ETRS89 przypięty do czeskich operacji EPSG:1622/1623
  (dokładność deklarowana 1,0 m; ADR-024 errata 2)
- Układ wysokościowy natywny: Bpv (Baltic 1957, EPSG:8357), dla plików
  ETRS89 (kafle TM33, LAZ TM33) EVRF2007 (EPSG:5621); opcjonalna
  transformacja rastra Bpv → EVRF2007 (przypięta operacja 0,1 m); KRON86
  nieosiągalny (brak publicznych siatek Bpv→KRON86)
- Raport `elevation availability --country cz|auto`: arkusze indeksu
  i jedno `HEAD` na plik (data publikacji, rozmiar), bez lat nalotu
- `extra.parent_request` w sidecarach trybu bbox/geometry — grupowanie
  plików jednego zadania po obu stronach granicy PL/CZ

# Źródło: CUZK (Český úřad zeměměřický a katastrální)
# API: ArcGIS REST (query, exportImage) + pliki openzu (ZIP z TIFF+TFW albo .laz)
# Licencja: CC BY 4.0
```

Warstwice CZ (0.8.0, plan E1): `elevation download --product contours
--country cz --format SHP|DGN` - warstwice ZABAGED CUZK, ZIP arkusza SM5
z openzu 1:1 (`contours/cz_zabaged_<format>/`; S-JTSK, wysokości Bpv;
sygnał `http`), godło SM5 albo arkusze SM5 obszaru z indeksu
`KladyMapovychListu`; bez wycinka i bez kanału REST (ADR-043).

**Poza zakresem (bez przypisanego wydania):** wielokąt granicy
administracyjnej (zamiast prostokątnej obwiedni kraju) — sekcje 3.1 i 3.2.
Pozostałe dane CZ: ortofoto (2.4), dane wektorowe CUZK (2.14), Geonames
i ZTM (2.15), Bodove pole i QGZU-2013 (2.16).

### 2.3 NMPT (Numeryczny Model Pokrycia Terenu) - IN SCOPE

```text
# Funkcjonalności:
- Digital Surface Model (DSM) — teren + obiekty (drzewa, budynki)
- Pobieranie przez godło → ASC (OpenData)
- Pobieranie przez bbox z biblioteki (`provider.download_bbox`) -> GeoTIFF
  float32 z wysokosciami WCS (ASC multipart);
  CLI `--bbox` bez `--cutout` pobiera arkusze OpenData,
  z `--cutout --horizontal-crs` wycinek WCS z maska ladu
- Rozdzielczości (rejestr wariantów): siatki ASC EVRF2007 0.5m, 0.6m, 1m;
  KRON86 0.5m, 1m; archiwa XYZ 0.5m i 1m (KRON86). `--resolution`
  wymagane od 0.8.0 (BREAKING; wcześniej tylko 1m); wycinek `--cutout`
  tylko 1m
- Układy wysokościowe: KRON86, EVRF2007
- Dziedziczenie z GugikProvider (wspólna logika pobierania)

# Źródło: GUGiK
# API: WFS (skorowidz), WCS (wycinek 1 m), OpenData
```

### 2.4 Ortofotomapa - IN SCOPE

```text
# Funkcjonalności:
- Zdjęcia lotnicze Standard Resolution (rozdzielczość wg kampanii, np. 25 cm, 10 cm)
- Pobieranie przez godło → TIF (OpenData)
- Pobieranie przez bbox → GeoTIFF (WCS) — z biblioteki (`provider.download_bbox`, poza magazynem);
  CLI `--bbox` pobiera arkusze OpenData
- Brak vertical CRS (2D RGB); najnowszy zgodny rekord wariantu `color`
  (`RGB`/`CIR`/`B/W`, wymagany w API; CLI pobiera RGB) z
  GetCapabilities/GetFeatureInfo; `GugikOrtoProvider(color="CIR")` wybiera
  wariant podczerwieni
- Obsługa formatów WCS: GTiff, PNG, JPEG
- Wycinek w magazynie (0.8.0, ADR-042 D14): `imagery download --product orto
  --country pl --bbox|--geometry --cutout --horizontal-crs EPSG:2180
  --coverage standard|high --resolution 0.1m|0.25m|0.5m|1m` -> jeden GeoTIFF
  RGB `orto/pl_1992_<coverage>_<res>/bbox/<coords>.tif` (WCS Standard/High,
  siatka 0,1 m, kawałki 200 x 200 m, bez przepróbkowania i maski lądu;
  `download_image_cutout`/`check_image_cutout` z `product="orto"`)
- Ortofoto CZ (0.8.0, ADR-042 D13): `--country cz` (arkusz SM5 albo obszar)
  -> JPEG + `.jgw`/`.TM33N.jgw`/`.TM34N.jgw` z ATOM CUZK 1:1 w
  `orto/cz_sjtsk/`, tylko aktualny rocznik (`download_cz_orto_sheet`)
- Obrazy GUGiK planu E1 (0.8.0, ADR-043): `imagery download --product
  intensity` (obrazy intensywności LIDAR, 1 pasmo 0,25 m, arkusze PL-1992
  i PL-2000), `--product true-orto` (prawdziwa ortofotomapa wybranych
  miast, godła 8-członowe PL-1992; wycinek WCS `True_Orthoimagery`
  `--resolution 0.05m`-`1m`) i `--product oblique-orto` (ortofotomapa
  ukośna, arkusze PL-2000, arkusz = 4 pliki kierunków, `--direction`);
  tor arkuszy ortofotomapy (kampanie, `--year`, sygnał `index`), plik
  ponad 100 MiB zapowiadany rozmiarem z `HEAD`

# Źródło: GUGiK (PL), CUZK (CZ)
# API: WCS, WMS GetFeatureInfo, OpenData; ATOM CUZK
```

### 2.5 LAZ (Chmury Punktów LIDAR) - IN SCOPE

```text
# Funkcjonalności:
- Chmury punktów ALS (dane pomiarowe LIDAR), format .laz
- Discovery area-based przez godło (≤1:10000) / bbox / geometry → WFS
  GetFeature, bbox i envelope w porządku osi EPSG (N,E), filtr przecięcia;
  błąd jednego rocznika przerywa odkrywanie (`DownloadError`)
- Kafle drobniejsze niż 1:10000 (jedno godło 1:10000 → wiele kafli .laz)
- url_do_pobrania brany wprost z atrybutu WFS (godło kafla nieparsowane)
- Domyślnie najnowszy kafel per obszar (ADR-029); flagi --year/--min-year/--max-year
  (przedział lat, ADR-032), --vertical-crs, --min-density, --all-campaigns (sekcja 2.12)
- Dwa układy wysokościowe (wybór wymagany od 0.8.0): EVRF2007 (2018+), KRON86 (legacy, 2010-2019)
- Pobieranie równoległe (--workers); kafle jako wersje w magazynie
  (ADR-036 D26): kafel z lokalną wersją nie jest pobierany ponownie,
  nowszy nalot (inne pliki) pobiera się domyślnie; --check-updates,
  --upgrade, --force, --plan
- Biblioteka: download_data(product="laz", ...) (= CLI) albo
  download_laz_area (bbox w dowolnym układzie; wybór + pobranie + sidecary,
  wynik LazDownloadResult: files/failed/superseded/stale/notices) i
  check_laz_area (plan bez pobierania)
- Porażka choć jednego kafla = Error: z pełną listą, kod 1 (pobrane zostają)
- CZ (plan B, sekcja 2.2): download_cz_laz/check_cz_laz (model=, godło
  albo bbox; CzLazResult: sheets/files/failed/stale/notices); porażka
  pliku = Error: dla arkusza, kod 1 (pozostałe zostają)

# Źródło: GUGiK (CZ: CUZK, sekcja 2.2)
# API: WFS (GetCapabilities + GetFeature), OpenData (CZ: KladyMapovychListu + openzu)
```

### 2.6 Land Cover (Pokrycie Terenu) - IN SCOPE

```text
# BDOT10k (GUGiK):
- 15 warstw (12 pokrycia terenu PT* + 3 hydrograficzne SW*)
- Pobieranie całego pakietu powiatu; w GPKG opcjonalny filtr warstw
  (`--layers`/`layers=`, np. SWRS,PTWP) i oryginalny ZIP (`--keep-raw`)
- Pobieranie przez TERYT (powiat)
- Pobieranie przez godło, bbox (dowolny obsługiwany układ, `--bbox-crs`)
  lub geometrię — pakiet KAŻDEGO powiatu obszaru (`--workers` równolegle)
- Format: GeoPackage (domyślny) albo Shapefile (archiwum .zip, bez rozpakowania)
- Automatyczne scalanie warstw z zachowaniem rtree spatial index; GPKG
  składany w lokalnym katalogu tymczasowym i przenoszony do magazynu
  (SQLite nie pisze na udziale sieciowym — działa na CIFS/SMB bez blokad
  zakresów bajtów)
- Magazyn wersji (0.8.0): landcover/pl_bdot10k_gpkg[_<warstwy>]/teryt/<T>,
  sygnał: brak (lokalna wersja niesprawdzona, --force pobiera); keep_raw =
  osobna wersja ZIP; obszar = każdy powiat (`LandCoverReport`), błąd per powiat
- Archiwum roczników (0.8.0, ADR-042 D11): `--year 2014..2025` (stan
  z początku roku) z wymaganym `--format GML|SHP` — oryginalna paczka
  powiatu ZIP 1:1 w landcover/pl_bdot10k_<format>_<rok>/teryt/<T>.zip
  (np. `pl_bdot10k_shp_2024/teryt/1261.zip`); obszar = paczki każdego
  powiatu (PRG); etykieta wersji = rocznik, sygnał: brak; GPKG, `--layers`,
  `--keep-raw` z `--year` = błąd, `--format GML` bez `--year` = błąd
  z podpowiedzią; identyczny rocznik (ten sam SHA-256 w innym wydaniu
  powiatu) bez duplikatu — dowiązanie twarde, status `relabeled` (D7);
  brak paczki powiatu (404) = NoCoverageError tego powiatu

# BDOO (GUGiK, 1:250 000) — `--product bdoo` (pl.gugik.bdoo, 0.8.0, ADR-043):
- paczka GML województwa na rocznik (`--year` wymagany: 2015, 2021-2026),
  ZIP 1:1 -> landcover/pl_bdoo_<rok>/teryt/<woj>.zip; `--teryt` 2 cyfry
  (kod powiatu = błąd z podpowiedzią), obszar (--bbox/--sheet/--geometry)
  = paczki województw jego powiatów wg PRG
- `--layers` = ZIP plików wybranych klas rocznika (lista: landcover
  list-layers --product bdoo) -> landcover/pl_bdoo_<rok>_<klasy>/; klasa
  bez pliku w paczce = Info (classes_absent), klasa spoza rocznika = błąd
- etykieta wersji = rocznik, sygnał: brak

# CORINE Land Cover (Copernicus):
- 44 klasy pokrycia terenu
- Lata: 1990, 2000, 2006, 2012, 2018
- Pobieranie przez godło, bbox lub geometrię (bez TERYT)
- Format: GeoTIFF (CLMS API) lub PNG (WMS fallback: EEA Discomap, dla 1990
  DLR; sidecar extra.fallback = "wms_png")
- OAuth2 RSA authentication (opcjonalne; CLMS_CREDENTIALS na każdym systemie,
  Keychain tylko macOS)
- Auth Proxy dla izolacji credentials
- Magazyn wersji (0.8.0): CLMS w landcover/eu_corine_<rok>/ z etykietą
  wydania z katalogu CLMS (sygnał metadata), podgląd WMS osobno
  w landcover/eu_corine_<rok>_preview/ (etykieta = data pobrania)

# ZABAGED, Data50 i Data250 (CZ) w `landcover download --product`: sekcja 2.14
# Wszystkie źródła land cover: sidecar wersji <plik>.meta.json (sekcja 2.11)
```

### 2.7 SoilGrids (Dane Glebowe) - IN SCOPE

```text
# ISRIC SoilGrids:
- 11 parametrów glebowych (clay, sand, silt, soc, pH, etc.)
- 6 głębokości (0-5cm do 100-200cm)
- 5 statystyk (mean, Q0.05, Q0.5, Q0.95, uncertainty)
- Rozdzielczość: 250m (globalne)
- Pobieranie przez godło, bbox lub geometrię (BEZ TERYT — patrz 3.2)
- Format: GeoTIFF
- Magazyn wersji (0.8.0): soil/global_soilgrids_<wł>_<gł>_<stat>/,
  etykieta = wydanie SoilGrids z GetCapabilities (sygnał metadata)

# Źródło: ISRIC (International Soil Reference and Information Centre)
# API: WCS
```

### 2.8 HSG (Hydrologic Soil Groups) - IN SCOPE

```text
# Kalkulacja HSG dla metody SCS-CN:
- Klasyfikacja tekstury wg trójkąta USDA (12 klas)
- Mapowanie tekstury → HSG (A, B, C, D)
- Wejścia clay/sand/silt = wersje SoilGrids w tym samym magazynie
  (brakujące pobierane); te same wejścia = wersja HSG użyta ponownie
- Statystyki pokrycia dla każdej grupy
- Format wyjściowy: GeoTIFF (wartości 1-4, 0 = nodata) w
  hsg/global_soilgrids_<gł>_<stat>/
- Selekcja: --sheet, --bbox, --geometry
- Sidecar wersji <plik>.meta.json (extra.derived = "hsg", warstwy źródłowe,
  głębokość, statystyka, kody klas, source_files z sha256 wejść)

# Moduł: kartograf.hydrology.hsg
```

### 2.9 CLI Interface - IN SCOPE

```bash
# Komendy:
kartograf parse <godlo>                    # info o godle (PL-1992 lub PL-2000)
kartograf parse 6.179.12.20               # PL-2000 auto-detekcja
kartograf elevation download --sheet <godlo> --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # pobierz NMT
kartograf elevation download --sheet <godlo> --product nmpt --resolution 1m --vertical-crs EVRF2007 -o ./data # pobierz NMPT (--resolution wymagane od 0.8.0)
kartograf imagery download --sheet <godlo> --product orto -o ./data # pobierz ortofoto
kartograf elevation download --sheet <godlo> --product laz --vertical-crs EVRF2007 -o ./data # pobierz chmury punktów LAZ (wiele kafli)
kartograf elevation download --bbox ... --product laz --year 2024 --min-density 12 --country pl --vertical-crs EVRF2007 -o ./data
kartograf elevation download --bbox min_x,min_y,max_x,max_y --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data # NMT dla bbox
kartograf elevation download --bbox ... --sheet-system 2000 --scale 1:2000 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 -o ./data # NMT w ukladzie PL-2000 (arkusze 1:2000)
kartograf imagery download --bbox ... --product orto --country pl --sheet-system 1992 -o ./data # ortofoto dla bbox
kartograf imagery download --bbox ... --product orto --country pl --cutout --horizontal-crs EPSG:2180 --coverage standard --resolution 0.25m -o ./data # wycinek WCS
kartograf imagery download --sheet CTES96 --product orto -o ./data # ortofoto CZ (arkusz SM5: JPEG + 3 JGW)
kartograf landcover download --product zabaged --bbox=... --bbox-crs EPSG:5514 -o ./data # ZABAGED (22 warstwy, EPSG:5514); --whole-country --horizontal-crs EPSG:5514|EPSG:3045
kartograf boundaries download --product admin --country cz --level obec --bbox=... --bbox-crs EPSG:5514 -o ./data # RUIAN; auto: --level pl=gmina,cz=obec
kartograf hydro download --product network --country cz --bbox=... --bbox-crs EPSG:5514 -o ./data # HY-NET; --whole-country (EPSG:3045)
kartograf elevation download --geometry area.shp --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data # NMT z pliku geometrii
kartograf elevation download --geometry area.gpkg --layer catchments --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data
kartograf elevation download --sheet <godlo> --resolution 5m --product nmt --vertical-crs EVRF2007 -o ./data # NMT 5m
kartograf elevation download --sheet <godlo> --resolution 0.5m --product nmt --vertical-crs EVRF2007 -o ./data # NMT 0.5m (etykiety z rejestru wariantow; elevation list-sources)
kartograf elevation download --bbox ... --country pl --sheet-system 1992 --product nmt --format TBD --resolution 25m --vertical-crs KRON86 -o ./data # archiwum GUGiK jako plik zrodlowy (ADR-041)
kartograf elevation list-sources                   # warianty NMT/NMPT/LAZ z rejestru (gotowe flagi), bez sieci
kartograf elevation availability --product nmt --country pl --bbox ... # raport dostepnosci: komplet pelnych arkuszy per rok/uklad/rozdzielczosc/format, bez pobierania
kartograf elevation availability --product nmpt --sheet <godlo> --details # godla arkuszy niepelnych i polecenia pobrania; --json = check_availability
kartograf elevation download --sheet 302_5550 --country cz --product nmt --resolution 2m --vertical-crs Bpv -o ./data # DMR 5G (CZ), godlo TM33
kartograf elevation download --sheet CTES96 --product nmt --vertical-crs Bpv -o ./data # DMR 4G (CZ, 5m), godlo SM5, kraj z godla
kartograf elevation download --sheet CTES96 --product nmpt --resolution 0.5m --vertical-crs Bpv -o ./data # DMP OK CZ, arkusz SM5
kartograf elevation download --sheet 760_5518 --country cz --product nmpt --resolution 0.5m --vertical-crs EVRF2007 -o ./data # DMP OK natywny kafel TM33
kartograf elevation download --sheet CTES96 --country cz --product laz --model dmr5g --vertical-crs Bpv -o ./data # LAZ CZ z ZIP, bez transformacji
kartograf elevation availability --product laz --country cz --sheet CTES96 # raport CZ bez pobierania plikow
kartograf elevation download --bbox ... --bbox-crs EPSG:4326 --country auto --cutout --horizontal-crs EPSG:5514 --product nmt --resolution pl=1m,cz=2m --vertical-crs pl=EVRF2007,cz=Bpv -o ./data # bbox transgraniczny -> wycinek per kraj
kartograf elevation download --bbox ... --country cz --cutout --horizontal-crs EPSG:2180 --product nmt --resolution 2m --vertical-crs Bpv -o ./data # reprojekcja lokalna (pinned)
kartograf elevation download --bbox ... --country pl --cutout --horizontal-crs EPSG:2180 --product nmt --vertical-crs EVRF2007 -o ./data # wycinek NMT/NMPT 1 m WCS + maska PRG (ADR-035)
kartograf elevation download --sheet 302_5550 --country cz --vertical-crs EVRF2007 --product nmt --resolution 2m -o ./data # Bpv -> EVRF2007 (EPSG:5621)
kartograf elevation download --sheet <godlo> --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # wszystkie kampanie GUGiK arkusza (ADR-030)
kartograf elevation download --sheet <godlo> --year 2025 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # najnowszy lot z roku (ADR-032)
kartograf elevation download --sheet <godlo> --year 2025 --all-campaigns --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # wszystkie loty z roku
kartograf elevation download --sheet <godlo> --min-year 2024 --product nmt --resolution 1m --vertical-crs EVRF2007 -o ./data # najnowszy lot, nie starszy niż rok
kartograf elevation download --bbox ... --max-year 2022 --product nmt --country pl --resolution 1m --vertical-crs EVRF2007 --sheet-system 1992 -o ./data # najnowszy lot do roku (dowiązanie nigdy wstecz)
kartograf elevation download --bbox ... --product laz --all-campaigns --country pl --vertical-crs EVRF2007 -o ./data # LAZ bez deduplikacji pokrycia
kartograf landcover download --product bdot10k --teryt <kod> -o ./data  # obszar: --bbox [--bbox-crs] / --sheet / --geometry; --layers, --keep-raw, --workers, -q
kartograf landcover download --product bdot10k --teryt 1261 --year 2024 --format SHP -o ./data # archiwum roczników BDOT10k (2014-2025, GML|SHP, ZIP 1:1)
kartograf landcover download --product corine --sheet <arkusz> -o ./data --year 2018
kartograf soil download --property <param> -o ./data --depth 0-5cm --stat mean # --sheet/--bbox (bez --teryt)
kartograf landcover list-sources
kartograf landcover list-layers --product <produkt>
kartograf soil hsg --sheet <arkusz> -o ./data --depth 0-5cm # oblicz HSG z wersji SoilGrids
kartograf boundaries download --product admin --country pl --level gmina --bbox ... -o ./data # granice PRG obszaru (GPKG z WFS); --teryt 12 / --whole-country --country pl
kartograf boundaries list-sources
kartograf cadastre download --product map --teryt 1261 -o ./data # EGiB powiatu (GPKG); obszar: --country pl --bbox/--sheet/--geometry
kartograf cadastre list-sources
kartograf models3d download --product buildings --lod 1 --year 2024 --teryt 1261 -o ./data # modele 3D CityGML; --lod 2 (2017) bez --year
kartograf models3d list-sources
kartograf elevation download --product contours --country cz --format SHP --sheet CTES96 -o ./data # warstwice ZABAGED CZ (ZIP arkusza SM5; SHP|DGN)
kartograf elevation download --product nmt --resolution 100m --country pl --bbox ... -o ./data # NMT 100 m: pliki XYZ województw z feedu ATOM
kartograf imagery download --product intensity --sheet <godlo> -o ./data # obrazy intensywności LIDAR; także --product true-orto, oblique-orto (--direction)
kartograf landcover download --product bdoo --teryt 12 --year 2023 -o ./data # BDOO: paczka GML województwa; --layers wybrane klasy
kartograf landcover download --product data50 --bbox=... --bbox-crs EPSG:5514 -o ./data # Data50/Data250 CZ; --whole-country --horizontal-crs EPSG:5514|EPSG:3045
kartograf boundaries download --product addresses --country pl --bbox ... -o ./data # punkty adresowe i ulice PRG; --teryt <4 cyfry>; --whole-country --format SHP|GML
kartograf boundaries download --product special --country pl --bbox ... -o ./data # 44 rodzaje granic specjalnych PRG (OGC API); --whole-country --format SHP|GML
kartograf boundaries download --product geomorphology --country cz --level celek --bbox=... --bbox-crs EPSG:5514 -o ./data # jednostki geomorfologiczne CZ
kartograf cadastre download --product prices --teryt 1261 -o ./data # RCN: eksport powiatu (4 cyfry) albo województwa (2 cyfry)
kartograf cadastre download --product map --ku 623164 --format SHP -o ./data # mapa katastralna CZ (SHP|DXF|DGN|VFK); obszar: KU wg RUIAN
kartograf models3d download --product mesh --country pl --bbox ... -o ./data # mesh miast (kafle OBJ); --product trees --teryt <kod> (drzewa CityGML)
kartograf names download --product geographic --country pl --bbox ... -o ./data # PRNG (CZ: Geonames); --product world; --whole-country --format
kartograf names list-sources
kartograf maps download --product topographic --country pl --sheet <godlo> --scale 1:10000 --format TIFF -o ./data # wizualizacje BDOT10k (CZ: ZTM)
kartograf maps list-sources
kartograf geodesy download --product control --country pl --network vertical --bbox ... -o ./data # punkty osnowy; --teryt (paczka powiatu), archiwa arkuszy
kartograf geodesy download --product geoid --country pl --whole-country -o ./data # PL-geoid2021 (CZ: QGZU-2013)
kartograf geodesy list-sources
kartograf project init --output ~/dane/kartograf # manifest projektu ze wspolnym magazynem
kartograf project add teren elevation download --product nmt --sheet <godlo> --resolution 1m --vertical-crs EVRF2007
kartograf project download                 # przypnij wersje zadan; --check-updates/--upgrade/--force
kartograf project status                   # istnienie i rozmiar, bez czytania danych
kartograf project verify                   # SHA-256 plikow i sidecarow
kartograf cache stats|clear|path           # cache metadanych (SQLite)
# Pełna lista opcji: kartograf <grupa> <komenda> --help
```

### 2.10 Python API - IN SCOPE

```python
# Public API — źródło prawdy: kartograf/__init__.py (__all__); lista poniżej
# jest z nim zgodna i aktualizowana razem z nim.
from kartograf import (
    # Cache
    MetadataCache,
    # Notices
    Notice,
    # Core
    SheetParser, Parser2000, ParserTM33, BBox, find_sheets_for_bbox,
    find_sheets_2000_for_bbox, find_sheets_for_geometry, get_overall_bbox,
    transform_bbox, parent_request_for,
    # Download (command level: `kartograf elevation download` / `imagery download`, spec 4.1)
    download_data, check_data, DataReport, UnitFile, UnitFailure,
    # Download (collections: `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download`, ADR-042)
    download_collection, check_collection, CollectionReport,
    # Download (orthophoto: CZ SM5 sheet; PL image cutout, ADR-042 D13-D14, ADR-044)
    download_cz_orto_sheet, check_cz_orto_sheet, CzOrtoResult,
    download_image_cutout, check_image_cutout, ImageCutoutResult,
    # Availability report (`kartograf elevation availability`, ADR-041)
    check_availability, AvailabilityReport, AvailabilityCombination,
    AvailabilityArea,
    # Download (NMT)
    DownloadManager, DownloadProgress, DownloadResult, CampaignRef, FileStorage,
    # Download (versioned store, update plan)
    UpdateMode, VersionedFile, VersionRef, PlanItem, UpdatePlan,
    # Download (PL cutout: WCS ADR-035)
    PlCutoutResult, check_pl_cutout, download_pl_cutout,
    # Download (CZ cutout, countries)
    CountryPart, countries_for_bbox, split_bbox_by_country, CzCutoutResult,
    check_cz_cutout, download_cz_cutout,
    # Download (CZ sheet: SM5 sheet / TM33 tile, R4)
    CzSheetResult, check_cz_sheet, download_cz_sheet,
    # Download (LAZ CZ: modele, SM5/TM33, HTTP, plan)
    CzLazResult, CzLazFailure, check_cz_laz, download_cz_laz,
    # Download (LAZ PL: WFS, kampanie)
    LazDownloadResult, LazTileFailure, check_laz_area, download_laz_area,
    # Land cover and soil (command level, ADR-044)
    download_landcover, check_landcover, LandCoverReport,
    download_soil, check_soil, SoilReport, Edition,
    # Providers
    BaseProvider, GugikProvider, GugikNmptProvider, GugikOrtoProvider,
    GugikLazProvider, LazTile, LazTileSelection, SupersededLazTile,
    LandCoverProvider, Bdot10kProvider, Bdot10kPackage, CorineProvider,
    SoilGridsProvider, CuzkRasterProvider, create_cz_raster_provider,
    CuzkLazProvider,
    # TERYT (PRG)
    discover_teryts_for_bbox, teryt_for_point,
    # Hydrology
    calculate_hsg, check_hsg, HsgReport, hsg_statistics, hsg_from_rasters,
    # Project manifest (kartograf-project/1, ADR-040)
    init_project, open_project, add_project_task, remove_project_task,
    download_project, check_project, get_project_status, verify_project,
    Project, ProjectTask, PinnedFile, ProjectReport, TaskResult,
    ProjectCheck, FileCheck,
    # Transport and mosaic (stable since 0.7.1)
    get_with_retry, make_gugik_session, mosaic_and_crop, check_source_grid,
    # Store reading without writing (Archiwista, ADR-045, ARCHITECTURE 3.3.1)
    list_segments, iter_store, StoreEntry, read_sidecar, Sidecar,
    describe_segment, SegmentInfo, file_footprint, Footprint, link_target,
    pinned_transform, PinnedTransform,
    # Exceptions
    KartografError, ParseError, ValidationError, DownloadError, NoCoverageError,
    YearRangeError, CacheError, InvalidSidecarError,
    # Version
    __version__,
)
# Rejestr wariantow NMT/NMPT/LAZ (ADR-041) — modul danych poza __all__:
# from kartograf.sources.variants import variants, ProductVariant, IndexRef
```

### 2.11 Układ danych na dysku - IN SCOPE

- `data/<produkt>/<kraj>_<układ>[_<wariant>][_<vcrs>]/...` (ADR-026);
  kanoniczna tabela segmentów i migracja 0.6.x→0.7.0:
  `docs/ARCHITECTURE.md` sekcja 3
- Wycinki CZ i wycinki PL NMT/NMPT 1 m (tylko z `--cutout`; bez
  tej flagi PL zapisuje arkusze w hierarchii godel) w
  `<segment>/bbox/<coords>.tif` — dowiazanie do wersji w
  `<segment>/versions/bbox/` (D15)
- `<układ>` w segmencie (`pl_1992` vs `pl_2000`) rozstrzyga format godła
  każdego pliku z osobna — jeden stary katalog (np. `orto/`) rozchodzi się
  przy migracji na dwa segmenty; wyjątek: kafle LAZ — układ z `uklad_xy`
  kafla (`LazTile.system`), dopiero w drugiej kolejności z formatu godła
- Magazyn wersjonowany (ADR-036, od 0.8.0; każdy produkt: arkusze PL NMT/NMPT/orto,
  kafle LAZ, arkusze i wycinki CZ, wycinki PL, land cover, HSG i kolekcje): prawdziwe pliki w
  `<segment>/versions/<hierarchia>/<data>_<id>_<sha8>/...`, niezmienne
  (sidecar wersji pisany raz, zapis wylaczny), sciezka standardowa =
  hardlink do najnowszej lokalnej wersji (bez kopii i symlinkow; system
  plikow z hardlinkami wymagany); `kampanie/` z 0.7.x bez migracji;
  tryby `--check-updates`/`--upgrade`/`--force`, plan `kartograf-plan/1`
  dla kazdego toru `elevation download`, `imagery download`, `landcover download`, `soil download` i `soil hsg`
  oraz `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download`
  (tor `collection`) (sygnal swiezosci per kanal: skorowidz albo rekord
  indeksu, `ETag`/`Last-Modified` plikow CUZK, wydanie z feedu ATOM,
  SoilGrids i CORINE CLMS; brak dla WCS/`exportImage`, BDOT10k i wiekszosci
  kolekcji GUGiK)
- Drugie dowiązanie `<segment>/full_sheet/<hierarchia>/<godło>.<ext>` do
  najnowszego lokalnego lotu pełnego (ADR-033); `list_files()` je pomija,
  `delete()` usuwa oba dowiązania
- Land cover i HSG w segmentach `landcover/`, `soil/`, `hsg/` (spec 3.4,
  ARCHITECTURE 3.3 regula 8); `--output` = korzen magazynu
- Kolekcje (ADR-042 D8, rozszerzenie reguły 8):
  `<grupa>/<kraj>_<źródło>[_<tokeny>]/{teryt/<T>|bbox/<coords>|country/<kod>|ku/<kod>|<hierarchia godła>|<strefa>/<plik>}<ext>`,
  wersje w `<segment>/versions/<ta sama hierarchia>/`. Tokeny (`[a-z0-9.-]`)
  = wariant treści (poziom, LoD, rocznik, sieć, skala, format); wynik obszaru (zawsze GPKG
  w układzie natywnym usługi, `coords` w tym układzie) bez tokenu formatu,
  paczka i plik krajowy z tokenem formatu źródła, gdy produkt ma kilka
  formatów albo także wynik obszaru. Przykłady:
  `boundaries/pl_prg_gmina/bbox/<coords>.gpkg`, `boundaries/pl_prg_gml/teryt/12.zip`,
  `boundaries/pl_prg_shp/country/pl.zip`, `cadastre/pl_egib_gpkg/teryt/1261.gpkg`,
  `cadastre/pl_egib/bbox/<coords>.gpkg`, `cadastre/cz_cadastral-map_shp/ku/623164.zip`,
  `models3d/pl_buildings_lod1_2024/teryt/1261.zip`,
  `models3d/pl_mesh/2000/7/78944_6777_74230_55482.zip`,
  `names/pl_prng_shp/country/pl_miejscowosci.zip`,
  `maps/pl_bdot10k_10000_tiff/M-34/64/D/d/1/M-34-64-D-d-1.tif`,
  `geodesy/pl_control_vertical/bbox/<coords>.gpkg`,
  `landcover/pl_bdot10k_shp_2024/teryt/1261.zip`; różne treści nigdy
  nie dzielą slotu (pełne drzewo: ARCHITECTURE 3.3)
- Każde udane pobranie (CLI, DownloadManager, download_landcover,
  download_soil, calculate_hsg, download_pl_cutout, download_laz_area,
  download_collection) ma sidecar `<plik>.meta.json` (schemat
  `kartograf-meta/1`, best-effort); sidecar
  wersji jest obowiązkowy (porażka zapisu = brak wersji)

### 2.12 Kampanie GUGiK (ADR-030) - IN SCOPE

```text
# Strategie (tylko PL; CZ zawsze bieżąca mozaika):
- Bez `--all-campaigns` (domyślnie): najnowszy rekord skorowidza (ADR-028)
  w zakresie lat, sprawdzany przy każdym uruchomieniu po wygaśnięciu cache (7 dni)
- `--all-campaigns`: każda kampania arkusza (w zakresie lat) po twardym filtrze ADR-028
- Rok danych (ADR-032; NMT/NMPT/orto: aktualnosc, LAZ: akt_rok):
  --year RRRR = --min-year RRRR --max-year RRRR; flagi roku wyznaczają tylko
  dopuszczalne lata, --all-campaigns liczbę lotów (model A; każda kombinacja dozwolona)
- Najpierw sprawdzenie pełnej listy kampanii każdego arkusza, potem pobranie:
  arkusz z danymi tylko z innych lat = Error: z latami i podpowiedzią, nic nie
  pobrane; arkusz bez danych = Warning: (pominięty); awaria skorowidza = Error:
  (wyjątek: lokalna wersja, punkt niżej)
- Kilka lotów w przedziale (all): pomiar pokrycia gdy najnowszy niepełny;
  Info: + extra.better_coverage, dowiązanie bez zmian (najnowszy)
- Drugie dowiązanie full_sheet/ (ADR-033): najnowszy lokalny lot z
  calyArkuszWypelnionyTrescia = TAK (pełny = w granicach Polski), obok
  ścieżki standardowej; --full-sheet dociąga najwyżej jeden lot na arkusz,
  gdy najnowszy w zakresie nie jest pełny (z --all-campaigns bez skutku); Warning: E13
  wskazuje full_sheet/ albo podpowiada --full-sheet
- LAZ: --all-campaigns (kafle z ramą przecinającą obszar, bez deduplikacji ADR-029);
  przedział lat z kontrolą pokrycia kafli referencji (ADR-032 P8); --year
  wyklucza się z --min-year/--max-year (Error:)
- Wycinek WCS `--cutout`: kompozycja serwera bez wyboru roku
  lub kampanii (--all-campaigns/--year/--min-year/--max-year/--full-sheet =
  Error:); LAZ z --full-sheet = Error:
- CZ nie ma kampanii ani wyboru roku: zadanie bez części PL z --all-campaigns,
  flagą roku albo --full-sheet = Error: przed siecią; obszar PL+CZ pod auto
  wymaga --cutout (ADR-038), który odrzuca te flagi - arkusze PL: --country pl
- Weryfikacja treści pliku kampanii (nagłówek AAIGrid / sygnatura TIFF;
  archiwa ADR-041: kompletny ZIP, sygnatura TTN, nagłówek Intergraph,
  DXF), format z pola `format` rekordu; sidecar kampanii obowiązkowy
- Skorowidz GUGiK niedostępny (błąd transportu) w trybie domyślnym (bez
  --upgrade/--force): arkusz z lokalnej wersji + Warning:, kod bez zmian —
  bez flag roku dla każdej strategii (także --all-campaigns), gdy ścieżka
  standardowa wskazuje lokalną wersję (errata 5 ADR-030); z flagami roku,
  gdy KAŻDY arkusz zadania ma lokalną wersję z zakresu lat (ADR-036 D14).
  Brak lokalnej wersji, --upgrade albo --force = błąd
- API: DownloadManager(year=, all_campaigns: bool = False, min_year=, max_year=,
  full_sheet=), .check_year_range(), YearRangeError, available_years
  (providery GUGiK), DownloadResult (.unverified, .reused_campaign_files,
  .better_coverage, .full_links, .without_full), FileStorage.get_full_sheet_path,
  CampaignRef; download_data(year=, min_year=, max_year=, all_campaigns=,
  full_sheet=) = flagi CLI
```

### 2.13 Granice, ewidencja, ceny i modele 3D (GUGiK, ADR-042, ADR-043) - IN SCOPE

```text
# Grupy CLI (ADR-039, ADR-042 D9): boundaries, cadastre, models3d — każda
# z download i list-sources; biblioteka: download_collection/check_collection
# (= CLI, ADR-037), tor planu `collection`. Nowy produkt kolekcji = wpis
# deskryptora z parametrami kanału, bez providera (DEVELOPMENT_STANDARDS 17.5).
# Produkty CZ tych grup (RUIAN, geomorfologia, mapa katastralna): sekcja 2.14.

# Granice PRG — `boundaries download --product admin` (pl.gugik.prg):
- --teryt <2 cyfry>: paczka województwa (GML wszystkich poziomów), ZIP 1:1
  -> boundaries/pl_prg_gml/teryt/12.zip
- --whole-country --country pl: plik krajowy SHP (ok. 377 MB; rozmiar
  w Warning: przed transferem) -> boundaries/pl_prg_shp/country/pl.zip
- obszar (--bbox/--sheet/--geometry, --country pl) z wymaganym --level
  wojewodztwo|powiat|gmina|jednostka-ewidencyjna|obreb: jeden GeoPackage
  z WFS, pełne geometrie jednostek przecinających obszar (bez przycinania),
  EPSG:2180 -> boundaries/pl_prg_gmina/bbox/<coords>.gpkg

# Punkty adresowe i ulice PRG — `boundaries download --product addresses`
# (pl.gugik.prg_addresses, 0.8.0):
- obszar (--country pl) -> jeden GPKG EPSG:2180 z warstwami punktów
  adresowych i ulic (WFS KIN GUGiK) -> boundaries/pl_prg_addresses/bbox/<coords>.gpkg
- --teryt <4 cyfry>: paczka SHP powiatu 1:1 -> boundaries/pl_prg_addresses_shp/teryt/1261.zip
  (paczek województw nie ma: --teryt <2 cyfry> = błąd z listą wyborów)
- --whole-country --format SHP|GML: plik krajowy (ok. 564 / 804 MB)

# Granice specjalne PRG — `boundaries download --product special` (pl.gugik.prg_special, 0.8.0):
- obszar (--country pl) -> jeden GPKG OGC:CRS84 z 44 rodzajami granic (sądy,
  policja, administracja skarbowa, lasy, wody, obszary morskie, ...), warstwa
  na rodzaj, z OGC API PRG (minuty: każda kolekcja osobno)
  -> boundaries/pl_prg_special/bbox/<coords>.gpkg; obwody spisowe poza
  wynikiem obszaru (usługa odpowiada minutami) — Info (area_omitted)
  wskazuje plik krajowy
- --whole-country --format SHP|GML: plik krajowy (ok. 734 MB dla SHP);
  --teryt = błąd

# EGiB (mapa ewidencyjna) — `cadastre download --product map` (pl.gugik.egib):
- --teryt <4 cyfry>: eksport powiatu (warstwy dzialki, budynki, transakcje;
  odświeżany co dobę), GPKG rozpakowany z ZIP
  -> cadastre/pl_egib_gpkg/teryt/1261.gpkg
- obszar (--country pl): działki i budynki z usługi zbiorczej WFS w jednym
  GPKG EPSG:2180 -> cadastre/pl_egib/bbox/<coords>.gpkg; powiaty bez
  integracji z usługą = luki, atrybuty zastrzeżone = `brak_uprawnien`;
  pole DATA poza plikiem, jego wartości w sidecarze
  (extra.source.dropped_fields)

# RCN (rejestr cen nieruchomości) — `cadastre download --product prices`
# (pl.gugik.rcn, 0.8.0):
- --teryt <4 cyfry> (powiat) albo <2 cyfry> (województwo), obszar = eksport
  każdego powiatu -> GPKG EPSG:2180 z warstwami transakcje_dzialki,
  transakcje_budynki, transakcje_lokale, rozpakowany z ZIP lokalnie
  z kontrolą warstw -> cadastre/pl_rcn/teryt/1261.gpkg; odświeżany co dobę

# Modele 3D budynków (CityGML) — `models3d download --product buildings`
# (pl.gugik.buildings):
- --teryt <4 cyfry> albo obszar (--country pl): paczki każdego powiatu
  obszaru wg PRG; paczka powiatu ZIP 1:1
- wydanie: --lod 1 --year 2019|2021|2022|2024 albo --lod 2 (jedyne wydanie
  2017, --year można pominąć) -> models3d/pl_buildings_lod1_2024/teryt/1261.zip
- układ wysokości z danych w sidecarze: LoD1 2019 i LoD2 2017 = EPSG:9650
  (PL-KRON86-NH), LoD1 2021/2022/2024 = EPSG:9651 (PL-EVRF2007-NH)
- LoD2 nie pokrywa kraju: brak paczki powiatu = błąd tego powiatu

# Mesh 3D miast — `models3d download --product mesh` (pl.gugik.mesh, 0.8.0):
- kafle indeksu WFS GUGiK przecinające obszar (--bbox/--sheet/--geometry),
  każdy jako oryginalny ZIP (OBJ, MTL, tekstury JPG, ok. 40-60 MB)
  -> models3d/pl_mesh/<układ>[/<strefa>]/<plik rekordu>.zip (katalog = układ
  rekordu 1992 albo 2000/<strefa>; wysokości EPSG:9651); kafel = plik jednego rekordu
  (moduł z kilku prac = kilka plików), --year filtruje rekordy
- etykieta wersji = data i numer zgłoszenia pracy z rekordu, sygnał index
  (--check-updates bez pobrania)

# Modele 3D drzew — `models3d download --product trees` (pl.gugik.trees, 0.8.0):
- CityGML LoD1 2023 (EPSG:2180, bez układu wysokości): paczka powiatu
  (--teryt) albo paczki powiatów obszaru, 0,3-25 GB każda (Warning
  z rozmiarem) -> models3d/pl_trees_lod1_2023/teryt/3063.zip; --lod 1
  i --year 2023 można pominąć

# Wspólne:
- dokładnie jeden wybór (--teryt / obszar / --whole-country); wariant
  (poziom, LoD, rok, format) wymagany, gdy źródło publikuje więcej niż
  jeden — brak wartości domyślnych wpływających na dane
- --country pl|cz|auto wymagane z --bbox/--geometry, z --teryt tylko pl;
  models3d tylko PL
- --check-updates | --upgrade | --force, --plan, --workers (domyślnie 1), -q;
  pozycje zadań projektu (`kartograf project add <nazwa> boundaries download ...`)
- sygnał aktualności none (GUGiK nie podaje ETag/Last-Modified, wynik WFS
  to migawka; wyjątek: mesh — index): --check-updates raportuje „nie da się
  sprawdzić bez pobrania”, nową treść daje --force (ta sama treść = bez
  zmian, inna = nowa wersja)
- etykieta wersji: rok modeli 3D (np. 2024), mesh — data i zgłoszenie
  pracy; PRG, adresy, granice specjalne, EGiB i RCN — data pobrania
- limit obszaru (ADR-043 errata 3): obszar, który pobrałby więcej niż 100
  plików albo więcej niż 10 GB (suma HEAD albo długości z feedu ATOM;
  ponad 100 plików — szacunek z 5), kończy się błędem przed pobraniem
  z liczbą plików, rozmiarem i podpowiedzią (zawęź obszar, wybierz
  jednostkę --teryt/--ku, wykonaj plan z częścią pozycji); liczą się pliki
  bez lokalnej wersji; jednostka i --whole-country bez limitu; dotyczy
  wszystkich kolekcji (sekcje 2.13-2.16, BDOO, ZABAGED, Data50, Data250,
  NMT 100 m)
- komunikaty Notice: unit_list (jednostki obszaru wg PRG/RUIAN),
  whole_country_size (rozmiar pliku krajowego przed transferem),
  download_size (plik jednostki ponad 100 MiB), area_omitted

# Źródło: GUGiK (PRG, EGiB, RCN, modele 3D budynków i drzew, mesh)
# API: WFS 2.0 (obiekty obszaru, indeks mesh), OGC API Features (granice
# specjalne), OpenData (paczki ZIP jednostek, pliki krajowe)
```

### 2.14 Dane CZ: ZABAGED, Data50, Data250, RUIAN, geomorfologia, mapa katastralna, HY-NET (CUZK, ADR-042 D15-D17, ADR-043) - IN SCOPE

```text
# Wspólne: obszar (--bbox/--geometry, --country cz albo auto) = jeden GPKG
# obiektów przecinających obszar w EPSG:5514 (pełne geometrie); plik krajowy
# tylko z --whole-country, ZIP CUZK 1:1, rozmiar w Warning przed transferem;
# godło jako obszar i --teryt tylko PL. Silnik plików z feedu ATOM:
# transport/atom.py (atom_files, indeks feedu w cache z ETag).

# ZABAGED — `landcover download --product zabaged` (cz.cuzk.zabaged):
- obszar -> landcover/cz_zabaged/bbox/<coords>.gpkg: 22 warstwy pokrycia
  terenu i wód (REST ZABAGED_POLOHOPIS; kody = nazwy ASCII warstw usługi),
  bez przeliczania klas na kody BDOT10k; lista: landcover list-layers --product zabaged
- --whole-country --horizontal-crs EPSG:5514|EPSG:3045 -> plik krajowy GPKG
  z feedu ATOM (5,8/6,7 GB) w landcover/cz_zabaged_gpkg_<epsg>/country/cz.zip;
  warstwy pełnej bazy pod nazwami CUZK (inne niż wynik obszaru); sygnał metadata

# Data50 i Data250 — `landcover download --product data50|data250` (cz.cuzk.data50/data250, 0.8.0):
- obszar -> landcover/cz_data50/bbox/<coords>.gpkg: wszystkie warstwy
  obiektowe usługi REST (Data50: 69, Data250: 116) w EPSG:5514
- --whole-country --horizontal-crs EPSG:5514|EPSG:3045 -> krajowy ZIP SHP
  z feedu ATOM 1:1 -> landcover/cz_data50_shp_<epsg>/country/cz.zip; sygnał metadata

# RUIAN — `boundaries download --product admin --country cz|auto` (cz.cuzk.ruian):
- --level kraj|okres|obec|katastralni-uzemi -> boundaries/cz_ruian_<poziom>/bbox/;
  pod auto poziom per kraj (--level pl=gmina,cz=obec) -> pliki PRG i RUIAN
- --whole-country --country cz -> boundaries/cz_ruian_shp/country/cz.zip (SHP, http)

# Jednostki geomorfologiczne — `boundaries download --product geomorphology
# --country cz` (cz.cuzk.geomorphology, 0.8.0):
- obszar z wymaganym --level subprovincie|oblast|celek|podcelek|okrsek|podokrsek|cast
  -> boundaries/cz_geomorphology_<poziom>/bbox/<coords>.gpkg (REST, EPSG:5514);
  bez pliku krajowego

# Mapa katastralna — `cadastre download --product map --country cz`
# (cz.cuzk.cadastral_map, 0.8.0):
- --ku <6 cyfr> (katastralni uzemi) albo obszar = KU obszaru wg RUIAN (Info
  z listą KU); --format SHP|DXF|DGN|VFK wymagane -> paczka KU ZIP 1:1
  -> cadastre/cz_cadastral-map_<format>/ku/623164.zip; sygnał http (ETag/Last-Modified)
- format VKM poza 0.8.0 (sekcja 3.1)

# HY-NET — grupa `hydro`, `download --product network --country cz` (cz.cuzk.hynet):
- obszar -> hydro/cz_hynet/bbox/<coords>.gpkg: WatercourseLink i HydroNode
  (WatercourseSeparatedCrossing bez geometrii i z hits 0 - tylko plik krajowy)
- --whole-country -> hydro/cz_hynet_gpkg/country/cz.zip (GPKG w EPSG:3045, http)

# Źródło: CUZK (CC BY 4.0)
# API: ArcGIS REST (ZABAGED, Data50, Data250, RUIAN, geomorfologia), WFS 2.0
# GeoServer (HY-NET), ATOM, openzu, services.cuzk.gov.cz (mapa katastralna)
```

### 2.15 Nazwy geograficzne i mapy topograficzne (GUGiK, CUZK, ADR-043) - IN SCOPE

```text
# Grupy CLI `names` i `maps` (download, list-sources; download_collection,
# zadania projektu); segmenty data/names/ i data/maps/.

# Nazwy — `names download --product geographic|world`:
- geographic --country pl (pl.gugik.prng, PRNG RP): obszar -> GPKG OGC:CRS84
  (OGC API Features; strona do 180 s) -> names/pl_prng/bbox/<coords>.gpkg;
  --whole-country --format GML|SHP|XLSX -> dwa pliki krajowe ZIP 1:1
  (names/pl_prng_<format>/country/pl_miejscowosci.zip, pl_obiekty-fizjograficzne.zip)
- world --country pl (pl.gugik.prng_world): polskie nazwy geograficzne
  świata — obszar także poza Polską, plik krajowy jeden (pl_swiat.zip)
- geographic --country cz (cz.cuzk.geonames, Geonames): obszar -> GPKG
  EPSG:5514 (25 warstw, REST) -> names/cz_geonames/bbox/<coords>.gpkg;
  --whole-country --format GPKG|FGDB --horizontal-crs EPSG:5514|EPSG:3045
  -> ZIP z feedu ATOM 1:1 (names/cz_geonames_<format>_<epsg>/country/cz.zip;
  wydanie = etykieta, sygnał metadata)
- wyniki obszaru bez taniego sygnału (none; nowa treść: --force)

# Mapy — `maps download --product topographic` (gotowe arkusze, nie baza wektorowa):
- --country pl (pl.gugik.bdot10k_maps): wizualizacje BDOT10k, --scale
  1:10000|1:25000|1:50000|1:100000 i --format TIFF|PDF wymagane, arkusz
  (--sheet) albo arkusze obszaru -> maps/pl_bdot10k_<skala>_<format>/<hierarchia>/<godło>.<ext>;
  data "Stan bazy" z indeksu (WMS GetFeatureInfo) = etykieta i sygnał index
- --country cz (cz.cuzk.ztm): ZTM w skalach 1:5000-1:250000, układ arkuszy
  S-JTSK albo ETRS89 z godła (obszar: --sheet-system sjtsk|etrs89), formaty
  S-JTSK: TIFF, PDF, DGN, SHP, ETRS89: TIFF, PDF; ZIP 1:1 (PDF jako .pdf)
  -> maps/cz_ztm_<skala>_<układ>_<format>/<hierarchia godła>/<godło>.zip; sygnał http

# Źródło: GUGiK (PRNG, wizualizacje BDOT10k), CUZK (Geonames, ZTM)
# API: OGC API Features, WMS GetFeatureInfo (indeks map), ArcGIS REST, ATOM, OpenData, openzu
```

### 2.16 Osnowy geodezyjne i quasi-geoidy (GUGiK, CUZK, ADR-043) - IN SCOPE

```text
# Grupa CLI `geodesy` (download, list-sources; download_collection, zadania
# projektu z opcją network).

# Osnowy — `geodesy download --product control --network <sieć>` (--network wymagane):
- PL (pl.gugik.control): horizontal|vertical|gravity|magnetic — obszar
  (--bbox/--sheet/--geometry) -> GPKG punktów sieci z WFS (warstwy
  fundamentalna_* i bazowa_*, EPSG:2180) -> geodesy/pl_control_<sieć>/bbox/<coords>.gpkg;
  --teryt <4 cyfry> z horizontal|vertical -> paczka powiatu (wykazy XLS,
  opisy JPG) 1:1 -> geodesy/pl_control_<sieć>_xls/teryt/<T>.zip;
  archive-1942|archive-kronsztadt60 -> skany arkuszy 1:100 000 (PDF, TIFF;
  --sheet dowolnej skali albo arkusze obszaru)
  -> geodesy/pl_control_archive-1942/N-33/58/N-33-58.zip
- CZ (cz.cuzk.control, Bodove pole): gnss|horizontal|densification|
  horizontal-detailed|vertical|vertical-detailed|gravity, tylko obszar
  -> GPKG warstw sieci w EPSG:5514 (sieć = suma jej warstw)
  -> geodesy/cz_control_<sieć>/bbox/<coords>.gpkg
- --country auto: jedna wartość --network dla obu krajów (wspólne:
  horizontal, vertical, gravity); sygnał none (nowa treść: --force)

# Quasi-geoidy — `geodesy download --product geoid --whole-country` (obszar = błąd):
- PL (pl.gugik.geoid2021): PL-geoid2021 dla PL-EVRF2007-NH (TXT 1:1, 42 MB)
  -> geodesy/pl_geoid2021_evrf2007/country/pl.txt; sygnał none
- CZ (cz.cuzk.qgzu2013): QGZU-2013 (ZIP 17 siatek TXT dla Bpv, 58 MB) z feedu
  ATOM -> geodesy/cz_qgzu2013_bpv/country/cz.zip; wydanie = etykieta, sygnał metadata
- modele są danymi: Kartograf nie stosuje ich do innych danych

# Źródło: GUGiK (osnowy podstawowe, PL-geoid2021), CUZK (Bodove pole, QGZU-2013)
# API: WFS (sieci PL), ArcGIS REST (Bodove pole), ATOM, OpenData
```

---

## 3. Out of Scope - Wersja 0.8.0

### 3.1 Funkcjonalności Zaplanowane - FUTURE

```text
# Plany A-E katalogu (produkty GUGiK i ČÚZK) są w zakresie 0.8.0 (sekcja 2).
# Dalsze zadania CZ (bez przypisanego wydania):
- Wielokąt granicy administracyjnej CZ zamiast prostokątnej obwiedni
  (CountryProfile.extent_wgs84) — usuwa fałszywe zapytania do CUZK dla
  bboxów leżących w całości w Polsce (patrz 3.2)
- Ujednolicenie extra.parent_request.bbox_crs między trybami jawny/auto
- Scalanie wycinków PL+CZ w jedną ciągłą powierzchnię przygraniczną
  (wspólna siatka, EVRF2007 po obu stronach, reguła zakładki) — R6; dane
  wejściowe zmierzone na żywo 2026-09-29: GUGiK wydaje dane ~200 m w głąb CZ,
  CUZK ~118 m w głąb PL, pas wspólny ~310-350 m bez szczeliny (poza dziurami
  pokrycia GUGiK), różnice wysokości PL−CZ w pasie −0,19..+0,14 m (mediany
  zależne od zbioru), siatki PL i CZ niewspólne

# Kampanie — poza zakresem (ADR-030):
- --campaign <id> (wybór jednej kampanii), strategie coverage i mosaic
- Narzędzie składania kampanii w jedną powierzchnię — bez przypisanego
  wydania (nie weszło do 0.7.1; ADR-030 errata 6)
- Kampanie dla CZ (CUZK nie publikuje historii) — bez przypisanego wydania

# Dane CZ poza zakresem 0.8.0:
- Archiwalne ortofoto CUZK (płatne) — tylko aktualny rocznik arkusza
- Wycinek ortofotomapy w innym układzie niż EPSG:2180 (bez przepróbkowania)
- Mapa katastralna CZ w formacie VKM: pilotaż CUZK (10 KU), KU spoza pilota
  (np. 623164) odpowiada 404 — piąty format `cadastre download --product map
  --country cz --format VKM`, gdy CUZK rozszerzy publikację (backlog PROGRESS)

# Kolekcje GUGiK (ADR-042) — poza zakresem:
- Paczka wojewódzka EGiB (ok. 1,4 GB): `cadastre --teryt <2 cyfry>` = błąd
  z podpowiedzią `--teryt <4 cyfry>`
- Pliki krajowe modeli 3D budynków (3,5-4,1 GB): `models3d --whole-country` = błąd
- Mapowanie klas ZABAGED na kody BDOT10k

# Później — inne kraje:
- Niemcy (DE) — federacja 17 modeli krajów związkowych (BKG/basemap.de)
- Słowacja (SK) — DMR 5.0, ZBGIS (uwaga: WCS zwraca wysokości elipsoidalne)

# Wersja 1.0+:
- GUI: wtyczka QGIS i GUI webowe — roadmapa w sekcji 3.3
- Integracja z PostGIS
- REST API server
```

### 3.2 Ograniczenia Techniczne

```
- Źródła nie publikują sum kontrolnych: Kartograf liczy SHA-256 przy zapisie
  wersji (sidecar, ADR-036), a `kartograf project verify` je sprawdza; treść
  pobrania jest sprawdzana tylko co do formatu (verify_file_format: nagłówek
  AAIGrid / sygnatura TIFF, ADR-030; archiwa GUGiK: ZIP/TTN/Intergraph/DXF,
  ADR-041; paczki kolekcji: katalog ZIP i wymagane człony, ADR-042)
- Timeouty domyślne: 30 s dla NMT/NMPT (GUGiK) i dla discovery WFS w LAZ,
  60 s dla Ortofoto, pobierania kafli LAZ, CORINE (bbox/godło), CUZK oraz
  SoilGrids przez godło, 120 s dla BDOT10k (wszystkie tryby) oraz SoilGrids
  przez bbox i HSG (CORINE/SoilGrids przez TERYT: NotImplementedError);
  GetCapabilities skorowidza GUGiK dziedziczy timeout providera (30 s
  NMT/NMPT, 60 s orto); raport dostępności: 30 s na zapytanie skorowidza
  WFS i PRG. Źródło prawdy — stałe w kodzie:
  GugikProvider.DEFAULT_TIMEOUT (NMT; NMPT dziedziczy),
  GugikOrtoProvider.DEFAULT_TIMEOUT, GugikLazProvider.DEFAULT_TIMEOUT (kafle)
  i .WFS_TIMEOUT (discovery), CorineProvider.DEFAULT_TIMEOUT,
  SoilGridsProvider.DEFAULT_TIMEOUT (bbox; godło: domyślne 60 s
  z LandCoverProvider.download_by_sheet), Bdot10kProvider.DEFAULT_TIMEOUT
  (zapytanie TERYT w PRG, teryts_for_area: 30 s), _DEFAULT_TIMEOUT
  w providers/cuzk/raster.py, limit HSG wynika z limitow SoilGrids
  (bez parametru `timeout` funkcji komendy ani `collections.run_request`;
  kanal kolekcji moze deklarowac `FeatureBBoxParams.timeout`, ADR-044 D6).
- Max 3 próby retry (nie konfigurowalne); ponawiane tylko błędy sieci,
  HTTP 429 i 5xx — inne 4xx (np. 404) kończą od razu z DownloadError.status_code;
  przerwa 2 s, potem 4 s, Retry-After wydłuża ją maks. do 60 s; jedno
  miejsce dla wszystkich providerów: transport/http.py (download_to,
  get_with_retry; stałe i szczegóły: DEVELOPMENT_STANDARDS 13.4)
- Synchroniczne pobieranie w obrębie jednego pliku (równoległość tylko
  między plikami, przez ThreadPoolExecutor/--workers; domyślnie 4 workery
  w CLI i download_data(workers=4), 1 w DownloadManager(workers=1))
- Warianty NMT/NMPT PL (rozdzielczość × układ wysokości × format) tylko
  z rejestru wariantów (ADR-041), m.in. NMT 0.15m, 0.6m, 5m i 10m tylko
  EVRF2007; inna kombinacja = Error: przed siecią z listą dostępnych
- WCS (`provider.download_bbox`) NMT i NMPT daje wysokosci 1 m float32
  w obu ukladach wysokosciowych; pozostałe rozdzielczości i archiwa
  tylko z OpenData (arkusze)
- Wycinki PL WCS `--cutout` tylko 1 m (siatka ASC; `--resolution` inna
  niż 1m albo `--format` = Error:), bez wyboru kampanii/roku;
  serwer decyduje o locie, ktory moze roznic sie od lotu arkusza
- Rekordy skorowidza, których Kartograf nie pobiera (godło spoza układów
  PL-1992/PL-2000, format albo wariant spoza rejestru, brak adresu https
  lub układu), raport dostępności wymienia w jednym Info: (index_unsupported);
  godła 8-członowe PL-1992 pobierają się od 0.8.0 (sekcja 2.1)
- Archiwa GUGiK (`--format`) są plikami źródłowymi bez konwersji, wycinka,
  mozaiki i pomiaru pokrycia; `--scale` i `--cutout` z archiwum = Error:
- Raport dostępności PL (`elevation availability`) ufa deklaracji
  `calyArkuszWypelnionyTrescia` (nie mierzy treści arkuszy NIE);
  maska lądu rasteryzowana na siatce 1 m w pasach 4 Mpx — dla
  dużych obszarów wolny (16 km2: 5–7 s z siecią, 0,6–1,5 s
  z cache metadanych, pomiar 2026-10-15). Raport CZ sprawdza
  tylko nagłówki HTTP plików, nie ich zawartość ani rok nalotu.
- SoilGrids: tylko WGS84 bbox (transformacja automatyczna)
- SoilGrids: brak selekcji po TERYT — `--teryt` dotyczy BDOT10k, BDOO i kolekcji,
  a `SoilGridsProvider.download_by_teryt` rzuca NotImplementedError (wcześniej
  cicho zwracał kwadrat 60x60 km wokół środka województwa); użyj --bbox/--sheet
- find_sheets_for_bbox/find_sheets_for_geometry: stykające się krawędzie NIE
  są przecięciem (wymagane dodatnie pole) — bbox równy arkuszowi w EPSG:4326
  zwraca tylko jego arkusze (w EPSG:2180 także fragmenty sąsiadów), a bbox
  zdegenerowany do punktu → dokładnie jeden arkusz
- Skorowidz GUGiK: retry (do 3 prób: sieć, 429, 5xx), sesja per wątek; awaria warstwy /
  szablonu przerywa z DownloadError, bez degradacji kampanii. NMT/NMPT:
  skorowidz WFS (od 0.8.0); serwer ignoruje FILTER, stronicowanie tylko po
  `next`, odpowiedź kilku typów z `next` odrzucana i odpytywana per typ
  (serwer stronicuje kilka typów niespójnie); niespójna strona = DownloadError
  („wynik bylby niepelny”), nigdy pusty wynik. Orto: WMS GetFeatureInfo.
  Rekord musi mieć całe godło, zgodny układ, rozdzielczość i (NMT/NMPT)
  format zgodny z URL; najnowsza data wygrywa. Brak rekordu daje
  NoCoverageError; extra.source zachowuje pochodzenie.
  Cache PL zapisuje pełen rekord albo brak pokrycia (TTL 7 dni); --force pomija
  odczyt i zapisuje świeży wpis (w CZ tak samo dla indeksu arkuszy SM5)

# CZ (CUZK; NMT od v0.7.0, pozostałe produkty od 0.8.0) — dodatkowe ograniczenia:
- Produkty CZ: nmt (DMR 5G/4G), nmpt (DMP OK/1G), laz (cztery modele,
  --model), contours (warstwice ZABAGED), orto (arkusze SM5, tylko aktualny
  rocznik), ZABAGED, Data50, Data250, RUIAN, geomorfologia, mapa
  katastralna (SHP/DXF/DGN/VFK), HY-NET, Geonames, ZTM, Bodove pole, QGZU-2013
- exportImage: sufity usługi 15000x4100 px, praktyczny limit ~8 Mpx;
  klient kafelkuje według budżetu 4 Mpx na żądanie, snap NW daje piksel
  dokładnie 0,5 m/2 m/5 m (krok modelu), a krawędź E/S może różnić się o <= 1/2 px
- KRON86 nieosiągalny dla CZ (brak publicznych siatek Bpv→KRON86) — jedyna
  transformacja pionowa to Bpv→EVRF2007 (EPSG:5621)
- --cutout działa tylko z --bbox/--geometry; z godłem CZ = ValidationError;
  obszar rastra CZ bez --cutout = ValidationError (ADR-038); LAZ z --cutout = błąd
- `--cutout` dla PL: NMT/NMPT 1 m z WCS, segment PL-1992
  (`--sheet-system 2000` = blad); orto/LAZ, NMT/NMPT poza 1 m i archiwa z `--cutout`
  = blad. Obszar poza maska ladu PRG `A00 - W02 - W03` = nodata
  -9999; wysokosc 0,0 na ladzie zostaje. Caly wycinek nodata =
  Warning: i kod 0. WCS wybiera lot na serwerze, inny niz
  najnowszy arkusz dokladnie 1 m wg ADR-028 (sekcja 2.1)
- Wycinek WCS (od 0.8.0): domyslnie lokalna wersja bez zapytan PRG
  i WCS (brak taniego sygnalu swiezosci), `--force` pobiera ponownie;
  nowa wersja powstaje obok starej, poprzednia wersja i dowiazanie
  zostaja przy awarii; `--workers`, `--scale` bez wplywu.
  `Info:` podaje liczbe zadan WCS dla wielu kawalkow lub wyniku
  >= 1 GiB (gdy wycinek jest pobierany), bez twardego limitu rozmiaru
- Lista arkuszy PL (--bbox/--geometry bez --cutout oraz hierarchia
  godła) próbuje wszystkie arkusze niezależnie od --workers. R5:
  NoCoverageError -> pominięcie, Warning: i status no_coverage;
  >= 1 plik, bez twardej awarii = kod 0; wszystkie arkusze bez danych
  albo dowolna awaria inna niż brak pokrycia = kod 1 (lista wszystkich
  awarii). Pojedynczy arkusz bez danych = kod 1
- Tryb --bbox rastra jest jawny (ADR-038): PL bez --cutout zwraca listę arkuszy
  (wiele plików), z --cutout jeden plik; raster CZ ma tylko wycinek (exportImage,
  pobierany natywnie w 5514 i reprojektowany lokalnie, gdy zażądano innego
  układu), więc obszar rastra CZ wymaga --cutout. Pod auto obszar PL+CZ nie daje
  arkuszy PL obok wycinka CZ (arkusze PL: --country pl). LAZ CZ (od 0.8.0)
  nie ma wycinka: obszar to arkusze z indeksu CUZK, bez --cutout
- CountryProfile.extent_wgs84 dla CZ to PROSTOKĄT (obwiednia), nie wielokąt
  granicy — --country auto w pasie na zachód od 18,86°E i na południe od
  51,06°N (m.in. Opole, Wałbrzych, Rybnik, południowe obrzeża Wrocławia;
  Kraków, Rzeszów i centrum Wrocławia są już poza prostokątem) wysyła
  zapytanie do CUZK także dla bboxów leżących w całości w Polsce, a także
  w Saksonii poniżej 51,06°N i w pasie Bogatyni (dodatkowy raster
  cały nodata = Warning: na stderr i kod 0). Symetrycznie prostokąt PL
  (14,07..24,20°E, 49,00..54,90°N) pokrywa
  większość Czech, więc auto w Pradze, Brnie czy Ostrawie odpytuje także
  GUGiK — naprawa (wielokąt granicy) bez przypisanego wydania (sekcja 3.1, ADR-023)
- --country (wymagane z --bbox/--geometry od 0.8.0; wcześniej domyślnie
  auto): pod auto na obszarze spornym wartości bez odpowiednika czeskiego
  (--vertical-crs KRON86, rozdzielczość bez odpowiednika CZ, np.
  --resolution 1m albo 0.5m dla NMT — NMPT 0.5m to DMP OK, --format
  w zwykłej postaci, --coverage i --resolution wycinka ortofotomapy)
  ROZSTRZYGAJĄ kraj do pl z komunikatem Info: na
  stderr, zamiast przewracać zadanie; dla --product laz także --year,
  --min-year, --max-year, --all-campaigns i --min-density. Bez nich LAZ
  na obszarze sięgającym CZ pobiera kafle PL i arkusze CZ (wymaga --model;
  bez niego błąd z podpowiedzią --country pl)
- --country auto przycina część zadania każdego kraju do prostokąta,
  wypisuje `Info:` o przycięciu i o obszarze pominiętym poza obiema
  obwiedniami. Nazwa pliku i request.bbox niosą część przyciętą,
  extra.parent_request oryginalne zadanie; nietknięte krawędzie PL zachowują
  oryginalne współrzędne (bez poszerzania na tych krawędziach).
  Jawne --country pl nie przycina, --geometry bez --cutout wyznacza
  arkusze PL z geometrii; bbox całkiem poza krajami = błąd przed siecią.
  Na granicach DE/SK/UA/BY/LT/RU auto odpytuje PL z przycięciem;
  wewnątrz prostokąta CZ dochodzi CUZK (bez wymogu poligonu granicy)
- Częściowy sukces w trybie auto (jeden kraj pobrany, drugi nieudany — brak
  danych albo awaria źródła) to kod wyjścia 0 + Warning: na stderr; kod 1
  zostaje dla jawnego --country i dla porażki wszystkich krajów (ADR-023 pkt
  4-5). Kod 0 nie gwarantuje więc pliku z każdego kraju. Info:/Warning: idą
  na stderr, więc -q ich NIE tłumi
- extra.parent_request.bbox_crs zależy od trybu, gdy plik geometrii nie jest
  w układzie żądania CZ: jawne --country cz niesie układ żądania CZ
  (--horizontal-crs), auto/pl — EPSG:2180, a plik w EPSG:5514/3045
  — układ pliku (od 2026-09-28: obwiednia opuszcza Krovaka przypiętą
  operacją); plik w EPSG:5514 z --horizontal-crs EPSG:5514 daje więc ten sam bbox_crs we
  wszystkich trybach — znane ograniczenie klucza grupowania, do ujednolicenia
  (sekcja 3.1, bez przypisanego wydania)
- extra.parent_request.countries = kraje PRÓBOWANE, nie pobrane (przy
  awarii jednego kraju w trybie auto sidecary drugiego nadal niosą oba kody)

# Kolekcje (boundaries, cadastre, models3d, hydro, names, maps, geodesy,
# archiwum BDOT10k, BDOO, ZABAGED, Data50, Data250; ADR-042, ADR-043):
- PRG `--teryt <4 cyfry>` = błąd (PRG publikuje paczki wojewódzkie; obszar
  powiatu przez --bbox/--geometry); EGiB i adresy PRG `--teryt <2 cyfry>`
  = błąd z podpowiedzią `--teryt <4 cyfry>`; granice specjalne bez
  `--teryt`; `models3d --whole-country` = błąd
- `models3d` tylko PL (`--country cz` = błąd); CZ: RUIAN i geomorfologia
  (`boundaries`), mapa katastralna (`cadastre`), HY-NET (`hydro`) — sekcja 2.14
- LoD2 (jedyne wydanie 2017) nie pokrywa kraju, drzewa 3D nie każdego
  powiatu: brak paczki powiatu = błąd tego powiatu
- Limit obszaru: ponad 100 plików albo 10 GB = błąd przed pobraniem (sekcja
  2.13); bez flagi obejścia — zawężenie obszaru, jednostka albo plan
- Granice specjalne PRG obszaru: minuty (OGC API odpytywane per kolekcja,
  limit 120 s z ponowieniem); obwody spisowe tylko w pliku krajowym
- RCN: rozpakowanie i kontrola warstw w lokalnym katalogu tymczasowym
  (`TMPDIR`; eksport województwa rzędu 1,8 GB)
- Strony WFS GUGiK: kilka sekund na stronę 1000 obiektów (na żywo
  2026-10-15: 2–4 s); kompletność z liczby obiektów (`RESULTTYPE=hits`),
  niepełna seria stron = DownloadError; wynik obszaru składany w pamięci
  (cała warstwa naraz)
- Bajty GPKG wyniku obszaru są powtarzalne w obrębie jednej wersji GDAL
  (pyogrio); inna wersja GDAL może dać inne bajty tej samej treści
- EGiB obszaru: luki w powiatach bez integracji z usługą zbiorczą,
  atrybuty zastrzeżone = `brak_uprawnien`
- Sygnał aktualności none (poza kanałami z indeksem, `ETag` CUZK i feedem
  ATOM): --check-updates nie wykrywa nowszych danych, nową treść daje tylko --force
- Timeouty: 60 s na zapytanie WFS, 120 s na paczkę, 30 s na HEAD
  i zapytanie PRG (SERVICE_TIMEOUT, PACKAGE_TIMEOUT, PROBE_TIMEOUT
  w download/collections.py)
```

---

### 3.3 Roadmapa do v1.0.0

Kierunek zatwierdzony 2026-10-08. Każdy podprojekt ma własny spec i plan;
podprojekty 2 i 3 wchodzą razem do 0.8.0 (decyzja użytkownika 2026-10-15);
szczegóły rozstrzygają ich ADR, nie ta sekcja.

**Cel v1.0.0:**

1. **Komplet publicznych danych GUGiK** — wszystkie produkty, które GUGiK
   udostępnia publicznie i bez logowania, o ile pozwalają na to usługi.
   Pełny katalog jest warunkiem wejścia, nie wyróżnikiem.
2. **Gotowe dane jako wyróżnik** — dla każdego produktu wynik dopasowany do
   obszaru zadania (wycinek, scalenie, reprojekcja tam, gdzie mają sens)
   z sidecarem pochodzenia, a nie tylko surowe arkusze i paczki.
3. **Manager danych** — wspólny magazyn zespołu, z którego kolejne projekty
   biorą dane zamiast pobierać je ponownie, z zapisem, jakich wersji danych
   użył każdy projekt.
4. **Wtyczka QGIS** i **GUI webowe** jako nakładki na bibliotekę.
5. **Wyłącznie angielskie identyfikatory** w API, CLI i sidecarze (ADR-031).

**Odbiorcy nakładek:** najpierw użytkownik i jego zespół (instalacja
lokalna, GUI webowe uruchamiane na `localhost`), po przetestowaniu —
publikacja (repozytorium wtyczek QGIS, publiczna instancja GUI webowego).

**Zasady:**

- Nakładki (QGIS, web) wołają wyłącznie publiczne API biblioteki
  (`kartograf/__init__.py`); nie mają własnej logiki pobierania ani obróbki.
- Magazyn nigdy nie nadpisuje danych po cichu: każdy produkt ma niezmienne
  wersje (ADR-036, od 0.8.0); ścieżka standardowa wskazuje najnowszą
  lokalną wersję.
- Sidecar pozostaje niezmiennym opisem pochodzenia pliku. Powiązanie
  projektu z danymi zapisuje manifest projektu (projekt → dane: konkretne
  pliki, wersje i sumy kontrolne); informacja „które projekty używają tego
  pliku” to indeks budowany z manifestów, nie wpis w sidecarze.
- Magazyn może leżeć na udziale sieciowym bez blokad zakresów bajtów, więc
  wspólny katalog nie może być bazą SQLite na udziale; źródłem prawdy są
  sidecary i manifesty, indeks i cache metadanych są lokalne.
- Manifest projektu jest nowym formatem, więc od początku używa angielskich
  kluczy (bez migracji ADR-031).

**Podprojekty i kolejność:**

| # | Podprojekt | Zakres | Zależy od |
|---|------------|--------|-----------|
| 1 | Magazyn wersjonowany | zrobione (0.8.0, ADR-036): niezmienne wersje dla wszystkich produktów (dotąd tylko kampanie NMT/NMPT/orto PL); plany 1/3 (arkusze PL), 2/3 (LAZ, CZ, wycinki) i 3/3 (land cover, HSG), produkty planów C-E od razu w magazynie (E2E na żywo: `docs/research/2026-10-12-store-e2e/raport.md`); CLMS z credentials niesprawdzony na żywo | — |
| 2 | Manifest projektu | zrobione (0.8.0): plik `kartograf-project.json` (`kartograf-project/1`) w katalogu projektu — zadania (komendy danych grup ADR-039 z opcjami) i przypięte wersje plików z magazynu z sumami SHA-256; grupa CLI `project`: `init`, `add`, `remove`, `download` (także `--check-updates`, `--upgrade`, `--force`), `status`, `verify`; odtworzenie danych na nowym magazynie tylko przy identycznych sumach. E2E: `docs/research/2026-10-15-project-e2e/raport.md`. Spec: `docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`; plan: `docs/superpowers/plans/2026-10-15-manifest-projektu.md`; ADR-040 | 1; grupy komend CLI (ADR-039) |
| 3 | Katalog GUGiK i gotowe dane | zrobione (0.8.0, plany A-E, decyzja użytkownika 2026-10-15): produkty GUGiK i ČÚZK z katalogu, każdy wersjonowany i z sidecarem, z wycinkiem tam, gdzie usługa go daje (sekcje 2.1-2.16). A: `elevation` PL — rejestr wariantów, siatki NMT/NMPT we wszystkich rozdzielczościach GUGiK, archiwa GUGiK jako pliki źródłowe, skorowidz WFS, raport dostępności (ADR-041); B: `elevation` CZ — DMP OK/1G, kafle TM33 ETRS89, LAZ ČÚZK, raport CZ; C: archiwum BDOT10k, PRG, EGiB, modele 3D budynków (ADR-042); D: ortofoto CZ, wycinek ortofotomapy PL, ZABAGED, RUIAN, HY-NET (ADR-042 D12-D17); E: obrazy GUGiK, warstwice CZ, NMT 100 m, nazwy, mapy, adresy i granice specjalne PRG, RCN, BDOO, Data50/250, geomorfologia, mapa katastralna CZ, mesh, drzewa, osnowy, quasi-geoidy (ADR-043). Poza 0.8.0: VKM, archiwalne ortofoto CUZK (sekcja 3.1). Inwentaryzacja: `docs/research/2026-10-13-katalog-produktow/raport.md`; spec: `docs/superpowers/specs/2026-10-13-katalog-produktow-design.md`; plany: `docs/superpowers/plans/2026-10-15-plan-{a,b,c,d,e}-*.md` | 1; grupy komend CLI (0.8.0) |
| 4 | Wtyczka QGIS | pobieranie z poziomu QGIS dla obszaru z mapy albo warstwy; repozytorium: to albo osobne, do decyzji w specu | 2, częściowo 3 |
| 5 | GUI webowe | lokalny manager danych: przeglądarka magazynu i manifestów projektów, informacja o nowszych danych | 2 |
| — | ADR-031 (angielskie identyfikatory) | API i CLI po angielsku w 0.8.0 bez aliasów (errata 1) | zrobione (0.8.0) |
| — | Publikacja nakładek | po przetestowaniu 4 i 5 lokalnie | 4, 5 |

Weryfikacja na żywo planów B-E: `docs/research/2026-10-16-plan-b-e2e/`,
`2026-10-15-plan-d-e2e/` oraz `2026-10-16-plan-e1-e2e/` do `2026-10-16-plan-e5-e2e/`
(raporty `raport.md`). Produkty spoza planów A-E trafią do kolejnych wydań
i mogą iść równolegle z 4 i 5.

---

## 4. Architektura

### 4.1 Moduły

Drzewo odpowiada katalogowi `kartograf/` (źródło prawdy: sam katalog); opis
szczegółowy — `docs/ARCHITECTURE.md`.

```
kartograf/
├── __init__.py           # Public API exports
├── _clock.py             # now() — jedno źródło czasu wyników (zamrażane w testach zgodności)
├── _version.py           # build_version() — identyfikator wersji
├── notices.py            # Notice, NoticeSink, kody komunikatów o danych (ADR-037)
├── exceptions.py         # KartografError, ValidationError -> ParseError, DownloadError -> NoCoverageError/YearRangeError, CacheError, InvalidSidecarError
├── store.py              # Odczyt magazynu bez zapisu (ADR-045): list_segments, list_partitions, iter_store, read_sidecar, describe_segment, link_target
├── store_geometry.py     # file_footprint (obrys natywny i WGS84), pinned_transform (operacja przypięta, per wątek)
├── core/                 # Logika bazowa
│   ├── bbox.py              # BBox, validate_bbox, transform_bbox, is_czech_crs
│   ├── sheet_parser.py      # SheetParser — parser godeł map topograficznych
│   ├── parser_2000.py       # Parser2000 — parser godeł PL-2000
│   ├── parser_tm33.py       # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045)
│   ├── parser_registry.py   # Rejestr systemów godeł (pl1992, pl2000, cz_tm33, cz_sm5)
│   ├── geometry.py          # SHP/GPKG reading, find_sheets_for_geometry, get_overall_bbox
│   └── coverage.py          # Wypukłe wielokąty (przecięcie/różnica/bufor) — wybór kafli LAZ (ADR-029)
├── sources/               # Deskryptory źródeł jako dane (zero IO przy imporcie)
│   ├── descriptor.py        # SourceDescriptor (+variants), AccessChannel (+endpoint, +params: UnitPackageParams/FeatureBBoxParams, ADR-042), TransportKind, LicenseInfo, CountryProfile
│   ├── registry.py          # Rejestr PL/CZ/EU/GLOBAL — get_source, sources_for, get_country, all_countries, vertical_crs_code, resolve_vertical_crs; deskryptory NMT/NMPT per (produkt, format, rozdzielczość)
│   ├── variants.py          # Rejestr wariantów (ADR-041): ProductVariant, IndexRef, FORMATS, variants(), etykiety K2, source_format
│   ├── edition.py           # Edition — wydanie źródła (sygnał metadata: SoilGrids, CORINE CLMS)
│   └── sidecar.py           # ResultMetadata, build_metadata (capability=, nodata=), write_sidecar (<plik>.meta.json)
├── transform/             # Transformacje CRS i rastrów, zapis GPKG kolekcji
│   ├── bbox.py               # envelope_from_2180 — obwiednia bboxa EPSG:2180 w innym CRS (CORINE, SoilGrids)
│   ├── gpkg.py               # write_gpkg — deterministyczny GPKG wyniku feature_bbox (pyogrio, ADR-042 D5)
│   ├── crs.py                # TransformerGroup (allow_ballpark=False, probe pod polityką sieci); PinnedTransform.transform polimorficzne
│   └── raster.py             # warp_to_grid — lokalny warp na siatkę, operacja WYMUSZONA (ADR-027)
├── transport/             # Wspólny transport pobierania
│   ├── http.py               # download_to (atomic write + retry), get_with_retry, sesje, sygnały HTTP
│   ├── aaigrid.py            # odczyt odpowiedzi ASC (AAIGrid) WCS
│   ├── chunks.py             # kawałki zapytań obszarowych na siatce źródła (ADR-034)
│   ├── feature_bbox.py       # silnik feature_bbox: obiekty obszaru z WFS 2.0 / ArcGIS REST (liczba obiektów, strony, kompletność; ADR-042 D3/D4)
│   ├── mosaic.py             # mosaic_and_crop — merge kafli (rasterio) + przycięcie (opcjonalnie na siatce zrodel, zrodla w VRT)
│   ├── unit_package.py       # silnik unit_package: plik jednostki z szablonu URL ({teryt}, {woj}, {sheet}, {ku}, {theme}) albo z rekordu indeksu (warianty, wymagane człony, unpack; ADR-042 D1, ADR-043)
│   ├── atom.py               # silnik atom_files: pliki z feedu ATOM (CUZK, GUGiK), wydanie z updated, indeks feedu w cache z ETag (ADR-042 D12)
│   └── index_records.py      # rekordy indeksów plików: tabela linków WMS GetFeatureInfo, rekordy WFS (ADR-043)
├── providers/             # Providery danych
│   ├── base.py               # DataSourceProvider (ABC), BaseProvider (NMT), LandCoverProvider
│   ├── pl/                   # Providery polskie
│   │   ├── gugik.py             # GugikProvider (NMT)
│   │   ├── gugik_nmpt.py        # GugikNmptProvider (NMPT/DSM)
│   │   ├── gugik_orto.py        # GugikImageProvider — arkusze obrazów (ortofotomapa: GugikOrtoProvider, intensywność, true orto, orto ukośna); wycinek WCS z kanałów rejestru
│   │   ├── gugik_laz.py         # GugikLazProvider (chmury punktów LAZ, WFS przez WfsIndex; select_tiles)
│   │   ├── skorowidz.py         # Skorowidz GUGiK: rekordy, twardy filtr, wybór kampanii (ADR-028/030); WMS GetFeatureInfo dla orto
│   │   ├── skorowidz_wfs.py     # Skorowidz WFS NMT/NMPT/LAZ (ADR-041): WfsIndex, parse_index_feature, obrysy arkuszy
│   │   ├── wcs.py               # GugikWcsMixin — wspólny URL WCS GetCoverage (NMT/NMPT 1m, orto)
│   │   ├── bdot10k.py           # Bdot10kProvider
│   │   ├── prg.py               # WFS PRG: maska lądu (wycinek PL, raport dostępności), TERYT dla obszaru/punktu
│   │   └── __init__.py          # create_nmt_provider() — fabryka providera NMT (vertical_crs, resolution wymagane)
│   ├── cuzk/                  # Providery czeskie (CUZK, plan B)
│   │   ├── client.py            # CuzkClient — ArcGIS REST + ZIP openzu
│   │   ├── sheets.py            # SheetIndex/SheetInfo — indeks SM5/TM33
│   │   ├── raster.py            # CuzkRasterProvider — NMT DMR i NMPT DMP
│   │   ├── laz.py               # CuzkLazProvider — cztery modele LAZ
│   │   ├── ruian.py             # KU obszaru z RUIAN (cadastral_areas_for_bbox) — mapa katastralna CZ
│   │   └── __init__.py          # create_cz_raster_provider(product, resolution, ...)
│   ├── corine.py             # CorineProvider
│   └── soilgrids.py          # SoilGridsProvider
├── cache/                 # Cache metadanych
│   ├── defaults.py           # open_cache — wspólny cache CLI i biblioteki (<cwd>/.kartograf_cache.db)
│   └── metadata.py           # MetadataCache — SQLite WAL: record_cache, campaigns_cache, teryt_cache, teryt_bbox_cache, index_area_cache, atom_cache (TTL 7d), sheet_cache (TTL 30d)
├── download/              # Pobieranie: komenda download w bibliotece (data.py) i tory
│   ├── data.py               # download_data/check_data = `kartograf elevation download` / `imagery download` (ADR-037)
│   ├── options.py            # Walidacja wyborów zadania (teksty jak w --help; warianty z rejestru)
│   ├── arguments.py          # Kontrola typów argumentów biblioteki (require_int/str/bool/codes, timeout; STANDARDS 11.2)
│   ├── availability.py       # Raport dostępności: check_availability, AvailabilityReport (ADR-041)
│   ├── collections.py        # download_collection/check_collection = `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download` (ADR-042); limit obszaru; kolekcje landcover
│   ├── cz_orto.py            # Ortofoto CZ: download_cz_orto_sheet/check_cz_orto_sheet (ADR-042 D13)
│   ├── cz_contours.py        # Warstwice ZABAGED CZ: ZIP arkusza SM5 1:1 (download_cz_contours_sheet, ADR-043)
│   ├── orto_cutout.py        # Wycinek obrazu PL WCS (ortofotomapa, true orto): download_image_cutout/check_image_cutout (ADR-042 D14, ADR-044)
│   ├── area.py               # Obszar: bbox_to_2180, geometria, parent_request, przycięcie auto
│   ├── campaigns.py          # Kampanie GUGiK (ADR-030): CampaignRef, format z rekordu, verify_file_format
│   ├── countries.py          # Podział obszaru na kraje (countries_for_bbox, split_bbox_by_country)
│   ├── fetch.py              # Polityka plików bez kampanii: fetch_version, VersionedFile
│   ├── plan.py               # Plan aktualizacji kartograf-plan/1 (PlanItem, UpdatePlan)
│   ├── links.py              # Dowiązanie ścieżki standardowej do wersji (wyłącznie hardlink, nigdy wstecz)
│   ├── cutout.py             # Wycinek PL --cutout (download_pl_cutout/check_pl_cutout)
│   ├── cz_cutout.py          # Wycinek CZ (download_cz_cutout/check_cz_cutout)
│   ├── cz_sheets.py          # Arkusz CZ TM33/SM5 (download_cz_sheet/check_cz_sheet)
│   ├── cz_laz.py            # LAZ CZ: download_cz_laz/check_cz_laz
│   ├── laz.py                # Kafle LAZ (download_laz_area/check_laz_area; ADR-029)
│   ├── manager.py            # DownloadManager (all_campaigns=, min_year=, sidecar_extra=; download_sheets/expand_sheets)
│   ├── storage.py            # FileStorage(vertical_crs=) — segmenty z szablonów deskryptora (ADR-026); content_segment/unit_slot (land cover, kolekcje; ADR-042 D8)
│   ├── updates.py            # Pozycje planu arkuszy PL
│   └── versions.py           # Magazyn wersjonowany (ADR-036): zapis wyłączny, etykiety, lista wersji
├── landcover/             # Land Cover w magazynie wersji
│   ├── manager.py            # download_landcover/check_landcover, download_soil/check_soil; wewnętrzny LandCoverManager
│   └── store.py              # segment HSG i wybór jednostki land cover (spec 3.4)
├── hydrology/             # Obliczenia hydrologiczne
│   └── hsg.py                # calculate_hsg/check_hsg, hsg_statistics; wewnętrzny HSGCalculator (wersje wejść, reused)
├── project/               # Manifest projektu kartograf-project/1 (ADR-040)
│   ├── model.py              # Project, ProjectTask, PinnedFile, ProjectReport, TaskResult, ProjectCheck, FileCheck
│   ├── commands.py           # COMMANDS: komendy danych w zadaniach (opcje JSON, walidacja bez sieci, pobranie, przypięcia)
│   ├── manifest.py           # odczyt, walidacja i atomowy zapis manifestu
│   └── operations.py         # API: init_project, open_project, add/remove_project_task, download_project, check_project, get_project_status, verify_project
├── auth/                  # Autentykacja (CLMS)
│   ├── proxy.py               # Auth Proxy server
│   └── client.py               # Auth Proxy client
└── cli/                   # CLI: tylko tłumaczenie flag i wypisanie wyniku (ADR-037)
    ├── _parser.py             # argparse — parser główny (parse, cache, błąd usuniętych komend)
    ├── _args.py               # wspólne flagi (obszar, tryby aktualizacji, --quiet)
    ├── groups/                # grupy komend wg typu danych (ADR-039): elevation, imagery, landcover, soil, boundaries, cadastre, models3d, hydro, names, maps, geodesy, project
    │                          #   (jeden moduł = jedna grupa z register(); wykrywane automatycznie)
    │                          #   _collection.py: wspólny kształt download/list-sources grup kolekcji (add_collection_commands)
    ├── parse_cmd.py           # `kartograf parse`
    ├── download_cmd.py        # `elevation download` / `imagery download` -> download_data/check_data
    ├── availability_cmd.py    # `elevation availability` -> check_availability (tabela, --details, --json)
    ├── landcover_cmd.py       # `landcover download` -> download_landcover/check_landcover
    ├── collection_cmd.py      # `boundaries`/`cadastre`/`models3d`/`hydro`/`names`/`maps`/`geodesy download` -> download_collection/check_collection
    ├── soil_cmd.py            # `soil download` -> download_soil/check_soil; `soil hsg` -> calculate_hsg/check_hsg
    ├── project_cmd.py         # `kartograf project` -> API projektu (ADR-040)
    ├── cache_cmd.py           # `kartograf cache`
    └── commands.py            # Fasada zgodności — re-eksport + entry point `main`
```

### 4.2 Zależności

```
Python 3.12+
requests >= 2.31.0     # HTTP client
pyproj >= 3.6.0        # CRS transformations
PyJWT[crypto] >= 2.8.0 # OAuth2 JWT (CLMS)
rasterio >= 1.3.0      # GeoTIFF processing (HSG, CZ exportImage/openzu)
numpy >= 1.24.0        # Array operations (HSG, transformacja pionowa per-piksel CZ)
pyshp >= 2.3.0         # Shapefile reading
pyogrio >= 0.10        # GDAL wektorowy: zapis GPKG wyników obszaru kolekcji (ADR-042)
```

---

## 5. Źródła Danych

| Źródło | Typ danych | API | Autentykacja |
|--------|-----------|-----|--------------|
| GUGiK | NMT, NMPT, ortofotomapa, obrazy (intensywność, true orto, orto ukośna), LAZ, BDOT10k (z archiwum roczników), BDOO | WCS, WMS, WFS, ATOM, OpenData | Brak |
| GUGiK PRG | Granice jednostek, punkty adresowe i ulice, granice specjalne | WFS 2.0, OGC API Features, OpenData (paczki ZIP, pliki krajowe) | Brak |
| GUGiK EGiB i RCN | Mapa ewidencyjna (działki, budynki), rejestr cen nieruchomości | WFS 2.0 (usługa zbiorcza), OpenData (eksport powiatu/województwa) | Brak |
| GUGiK modele 3D | Budynki CityGML LoD1/LoD2, drzewa CityGML LoD1, mesh miast (OBJ) | WFS (indeks mesh), OpenData (paczki ZIP) | Brak |
| GUGiK PRNG i mapy | Nazwy geograficzne RP i świata, wizualizacje map BDOT10k | OGC API Features, WMS GetFeatureInfo (indeks), OpenData | Brak |
| GUGiK osnowy | Osnowy pozioma, wysokościowa, grawimetryczna, magnetyczna (z archiwami), PL-geoid2021 | WFS, OpenData | Brak |
| CUZK | NMT, NMPT, LAZ, ortofoto, warstwice, ZABAGED, Data50, Data250, RUIAN, HY-NET, geomorfologia, mapa katastralna, Geonames, ZTM, Bodove pole, QGZU-2013, raport dostępności CZ | ArcGIS REST (query, exportImage), WFS 2.0 (HY-NET), ATOM, indeks arkuszy + pliki openzu i services.cuzk.gov.cz | Brak |
| Copernicus CLMS | CORINE | REST API | OAuth2 RSA |
| EEA Discomap | CORINE (podgląd) | WMS | Brak |
| DLR | CORINE 1990 (podgląd, fallback) | WMS | Brak |
| ISRIC SoilGrids | Gleba | WCS | Brak |

---

## 6. Success Criteria

### 6.1 Funkcjonalne

```
- Parser poprawnie parsuje godła 1:1M - 1:5k (PL-1992, z godłami 8-członowymi), PL-2000, TM33/SM5 (CZ)
- NMT pobiera się we wszystkich rozdzielczościach siatek GUGiK z rejestru
  wariantów (PL: 0.15m, 0.5m, 0.6m, 1m, 5m, 10m; NMPT 0.5m, 0.6m, 1m)
  i jako archiwa GUGiK (pliki źródłowe), 2m i 5m (CZ)
- Raport dostępności (elevation availability / check_availability) podaje
  dla obszaru PL kombinacje z kompletem pełnych arkuszy bez pobierania danych
- BDOT10k pobiera się przez TERYT, godło, bbox i geometrię (każdy powiat obszaru)
- CORINE pobiera się przez godło (GeoTIFF lub PNG fallback)
- SoilGrids pobiera dane glebowe
- HSG oblicza grupy hydrologiczne z danych SoilGrids
- DMR i DMP CZ pobiera się przez godło TM33/SM5 albo wycinek
  (`--cutout`), z natywnymi plikami 5514/Bpv lub 3045/EVRF2007
  i lokalną przypiętą transformacją dla pozostałych par
- LAZ CZ pobiera `.laz` 1:1 ze źródła po godle/obszarze; `--model`
  wybiera wariant, `--country auto` pobiera niezależne kafle PL i CZ
  ze wspólnym `extra.parent_request`, bez scalania
- Raport dostępności CZ i `auto` sprawdza warianty i pliki (`HEAD`),
  bez pobierania danych; brak pliku nie udaje sukcesu
- Wycinek NMT/NMPT PL 1 m (--cutout / download_pl_cutout): jeden GeoTIFF
  z WCS GUGiK na siatce arkuszy (EPSG:2180) albo w EPSG:5514/3045; poza
  ladem PL (maska PRG) nodata -9999
- Kampanie GUGiK: --all-campaigns, --year/--min-year/--max-year; wersje
  w versions/, ścieżka standardowa jako dowiązanie twarde do najnowszej;
  --check-updates/--upgrade/--force i plan aktualizacji (ADR-036)
- LAZ: wybór kafli wg pokrycia obszaru (ADR-029), API download_laz_area
- Granice PRG, EGiB i modele 3D budynków pobierają się przez TERYT
  i obszar (download_collection), archiwum BDOT10k przez TERYT i obszar
  (`--year`, `download_landcover`); wersje w versions/ i sidecar każdego pliku
- Produkty planów D i E (ortofoto CZ, wycinek ortofotomapy PL, obrazy
  GUGiK, warstwice CZ, NMT 100 m, BDOO, ZABAGED, Data50, Data250, RUIAN,
  HY-NET, geomorfologia, mapa katastralna CZ, adresy i granice specjalne
  PRG, RCN, mesh, drzewa, nazwy, mapy, osnowy, quasi-geoidy) pobierają się
  z CLI i biblioteki z wersjami i sidecarem; obszar kolekcji ponad 100
  plików albo 10 GB kończy się błędem przed pobraniem
- Integracja z Hydrograf/Hydrolog działa
```

### 6.2 Jakościowe

```
- Wszystkie testy offline przechodzą (`pytest -m "not live"`); testy
  z markerem `live` wymagają sieci i nie należą do bramki offline
- Pokrycie nie niższe niż próg `fail_under` w `pyproject.toml`
- Kod zgodny z ruff (`ruff check .` i `ruff format --check .` czyste),
  `mypy kartograf/ tests/` bez błędów
- Dokumentacja zgodna z kodem; zmiany zachowania wobec usług GUGiK/CUZK
  weryfikowane na żywo przed wydaniem (raporty w `docs/research/`)
```

---

## 7. Historia Zmian

| Data | Wersja | Zmiana |
|------|--------|--------|
| 2026-01-15 | 1.0 | Initial MVP (NMT only) |
| 2026-01-18 | 1.1 | Added Land Cover, SoilGrids, HSG |
| 2026-01-21 | 2.0 | Updated to reflect v0.3.1 features |
| 2026-02-07 | 3.0 | Added NMPT, Ortofotomapa, updated storage structure |
| 2026-02-08 | 3.1 | BDOT10k hydro category, rtree fix |
| 2026-02-08 | 3.2 | Geometry file selection (--geometry SHP/GPKG) |
| 2026-03-02 | 3.3 | Removed BDOT10k category filtering (download full package) |
| 2026-03-02 | 3.4 | PL-2000 support, bump to v0.5.0 |
| 2026-03-24 | 3.5 | WMS layer validation, 5m bugfix, bump to v0.6.1 |
| 2026-08-11 | 3.6 | Etap 0 (sources/transform/transport/providers-pl, CLI split, LAZ) + etap 1 (CZ/CUZK: DMR 5G/4G, --country/--target-crs, ADR-023); drzewo modułów i sekcje odświeżone |
| 2026-08-18 | 3.7 | Przegląd spójności dokumentacji: status mergu etapu 1, nagłówek sekcji 2 (0.5.0→0.7.0), komenda `cache` w 2.9, brakujące eksporty w 2.10 |
| 2026-08-22 | 3.8 | Korekty spójności po audycie przedwydaniowym 0.7.0: WCS NMT tylko 1m/KRON86, 4 warstwy WMS ortofoto, SoilGrids bez TERYT, timeouty per źródło, konwencja krawędzi i etykiety skal, semantyka `--country auto` (zasięg prostokąta CZ/PL, Info/Warning, częściowy sukces) |
| 2026-08-28 | 3.9 | Układ data/ per produkt (ADR-026), --target-crs dla PL (ADR-027), sekcja 2.11 |
| 2026-09-28 | 3.10 | Fala review max: wycinek PL jako API biblioteki (download_pl_cutout), siatka arkuszy, R5 (NoCoverageError -> nodata + extra.missing_sheets), eksporty w 2.10, drzewo modulow, etap 2: scalanie PL+CZ i wycinek z arkuszy PL-2000 |
| 2026-09-29 | 3.11 | Historyczne testy na żywo i audyt przed falą naprawczą: diagnozy LAZ, S-JTSK, skorowidza, orto, limitu CUZK i dyspozycji kraju; dowody zachowania na morzu i pograniczach oraz wejście do R6 |
| 2026-09-30 | 3.12 | Aktualizacja po fali naprawczej: filtr rekordow GUGiK i cache, R5 w liscie/hierarchii, W1/blad fazy w 2180, pin EPSG:1622/1623, budzet 4 Mpx, osie LAZ |
| 2026-10-07 | 3.13 | Kampanie GUGiK (ADR-030): sekcja 2.12, uklad `kampanie/` z dowiazaniem w 2.11, odrzucone strategie w 3.1 |
| 2026-10-08 | 3.14 | Przegląd dokumentacji: errata 5 ADR-030 (lokalna kampania przy awarii skorowidza), CZ i --min-year x --year w 2.12, sidecary (HSG, zasada ogólna), GPKG BDOT10k składany lokalnie, pełna lista eksportów w 2.10, drzewo modułów i tabele cache w 4.1, DLR w 5, bez wartości ulotnych w 6.2 i historii |
| 2026-10-08 | 3.15 | Roadmapa do v1.0.0 (sekcja 3.3): komplet publicznych danych GUGiK, gotowe dane, manager danych (magazyn wersjonowany, manifest projektu), wtyczka QGIS, GUI webowe |
| 2026-10-09 | 3.16 | Narzędzie składania kampanii (3.1) bez przypisanego wydania — nie weszło do 0.7.1 (ADR-030 errata 6) |
| 2026-10-10 | 3.17 | Wybór roku danych (ADR-032): --year/--min-year/--max-year dla NMT/NMPT/orto/LAZ w 2.12, CZ i wycinki bez roku; model A (rok = filtr lat, --campaigns = liczba lotów) |
| 2026-10-10 | 3.18 | Drugie dowiązanie `full_sheet/` i `--full-sheet` (ADR-033) w 2.11 i 2.12 |
| 2026-10-11 | 3.19 | Wydanie v0.7.2: wycinki NMT/NMPT PL z WCS GUGiK z maską lądu PRG (ADR-035), kawałki zapytań obszarowych na siatce źródła (ADR-034), status |
| 2026-10-12 | 3.20 | Magazyn wersjonowany plan 2/3 (ADR-036): LAZ, CZ i wycinki `bbox/` bez daty w wersjach, tryby update dla każdego toru, `DownloadManager.download_bbox` usunięte |
| 2026-10-13 | 3.21 | Pełna weryfikacja z kodem 0.8.0-dev (ADR-037): status i nagłówki 0.8.0, `--scale` dla PL-2000, BDOT10k/CORINE/SoilGrids przez geometrię i filtr warstw, fallback przy niedostępnym skorowidzu (D14), API kampanii, drzewo modułów (brakujące moduły, wyjątki), kryteria 6.1 |
| 2026-10-13 | 3.22 | Jawny tryb wycinka (ADR-038): `--cutout` + `--horizontal-crs` zamiast `--target-crs`, `--sheet-system` zamiast `--system`; obszar CZ wymaga `--cutout` |
| 2026-10-13 | 3.23 | Podprojekt 3: odwołanie do inwentaryzacji GUGiK/ČÚZK i zaakceptowanego specu (kolejność planów A–E) |
| 2026-10-15 | 3.24 | Plan A (ADR-041): rejestr wariantów NMT/NMPT (siatki 0.15–10 m, NMPT z `--resolution`), archiwa GUGiK jako pliki źródłowe (`--format`), skorowidz WFS, raport dostępności `elevation availability`/`check_availability` (2.1, 2.3, 2.9, 2.10, 3.2, 3.3, 4.1, 6.1) |
| 2026-10-15 | 3.25 | Plan C podprojektu 3 (ADR-042): granice PRG, EGiB i modele 3D budynków (grupy `boundaries`, `cadastre`, `models3d`, sekcja 2.13), archiwum roczników BDOT10k (2.6), `download_collection`/`check_collection`, układ segmentów kolekcji (2.11), ograniczenia (3.1, 3.2), moduły i `pyogrio` (4), źródła (5) |
| 2026-10-16 | 3.26 | Plan D (ADR-042 D12-D17): ortofoto CZ i wycinek ortofotomapy PL (2.4), dane CZ ZABAGED, RUIAN, HY-NET i grupa `hydro` (2.14), CLI i API (2.9, 2.10), ograniczenia (3.1, 3.2), moduły (4.1) |
| 2026-10-16 | 3.27 | Plany B i E (ADR-041, ADR-043) i przegląd przed wydaniem 0.8.0: cel (1), BDOO (2.6), adresy i granice specjalne PRG, RCN, mesh, drzewa i limit obszaru (2.13), Data50/250, geomorfologia i mapa katastralna CZ (2.14), nazwy i mapy (2.15), osnowy i quasi-geoidy (2.16), CLI (2.9), układ kolekcji (2.11), VKM i nieaktualne zadania (3.1), sumy kontrolne, godła 8-członowe i ograniczenia kolekcji (3.2), roadmapa (3.3), moduły, źródła i kryteria (4-6); bloki list jako `text` |
| 2026-10-17 | 3.28 | Wydanie v0.8.0: magazyn wersjonowany (ADR-036), manifest projektu (ADR-040), katalog GUGiK/ČÚZK — plany A–E (ADR-041–043), grupy CLI i ujednolicone API (ADR-039, ADR-044), status |

---

**Wersja dokumentu:** 3.28
**Data ostatniej aktualizacji:** 2026-10-17
**Status:** Wydanie v0.8.0 (2026-10-17)
