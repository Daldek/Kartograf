# SCOPE.md - Zakres Projektu Kartograf
**Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 3.12
**Data:** 2026-09-30
**Status:** Rozwoj — v0.7.0 (Unreleased); naprawy offline po testach live 2026-09-29 sa wdrozone, ponowna weryfikacja na zywych serwisach przed wydaniem

---

## 1. Cel Projektu

**Kartograf** to narzędzie do pobierania danych przestrzennych z zasobów GUGiK i CUZK (NMT), Copernicus i ISRIC dla Polski, a od etapu 1 (v0.7.0-dev) — częściowo dla Czech (pełna parytetowość produktowa DMR, planowana dalsza dla DE/SK).

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
- **Providery danych** - abstrakcja nad różnymi serwisami (GUGiK, Copernicus, ISRIC)
- **Selekcja obszaru** - godło, TERYT, bbox, plik geometrii (SHP/GPKG)
- **Automatyczne pobieranie** - pobieranie wielu plików jedną komendą
- **Organizacja plików** - automatyczna struktura katalogów

### 1.3 Użytkownicy

1. **Deweloperzy Hydrograf/Hydrolog** - integracja jako biblioteka Python
2. **Specjaliści GIS** - CLI do pobierania danych
3. **Hydrolodzy** - dane glebowe i HSG dla metody SCS-CN

---

## 2. Zakres - Wersja 0.7.0

### 2.1 NMT (Numeryczny Model Terenu) - IN SCOPE

```python
# Funkcjonalności:
- Parser godeł PL-1992 (SheetParser): skale 1:1M do 1:10k
- Parser godeł PL-2000 (Parser2000): skale 1:10k do 1:500, 4 strefy (EPSG:2176-2179)
- Auto-detekcja systemu: SheetParser automatycznie rozpoznaje PL-1992 vs PL-2000
- Hierarchia arkuszy (get_parent, get_children, get_all_descendants)
- Bounding box arkusza (EPSG:2180, EPSG:4326, EPSG:2176-2179)
- Reverse lookup: bbox → godła (find_sheets_for_bbox, find_sheets_2000_for_bbox)
- Reverse lookup: geometry file → godła (find_sheets_for_geometry)
- Selekcja obszaru: godło, bbox, plik geometrii (SHP/GPKG)
- Pobieranie przez godło → ASC (OpenData)
- Pobieranie przez bbox → GeoTIFF (WCS): tylko NMT 1m i tylko KRON86
  (endpoint EVRF2007 wycofany przez GUGiK, HTTP 404 od 2026-08 — download_bbox
  pod EVRF2007 kończy się ValidationError) LUB automatyczne wykrywanie arkuszy
  (CLI --bbox: arkusze OpenData, oba układy wysokościowe)
- Wycinek bbox z reprojekcją lokalną: `--target-crs {EPSG:2180,EPSG:5514,
  EPSG:3045}` w trybie `--bbox`/`--geometry` — jeden scalony GeoTIFF
  (download_pl_cutout, kroki prepare/select/run_pl_cutout; opcjonalnie
  cache=MetadataCache()); EPSG:2180 = crop 1:1 na siatce arkuszy, a arkusze
  o roznych fazach daja GridMismatchError; inny target CRS = W1 (warp per
  arkusz, extra.off_grid_sheets); brak arkusza GUGiK = nodata i
  extra.missing_sheets (R5); wynik calkowicie nodata = Warning:
- Rozdzielczości: 1m (GRID1), 5m (GRID5)
- Układy wysokościowe: KRON86, EVRF2007
- Godło PL-2000 1:10000, dla którego GUGiK ma wyłącznie arkusze
  potomne, daje `NoCoverageError` z podpowiedzią `--scale 1:2000`
  (bez cichego pobrania zastępczego PL-1992)

# Źródło: GUGiK (Główny Urząd Geodezji i Kartografii)
# API: WCS, WMS GetFeatureInfo, OpenData
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
dokładnie jeden arkusz. Nieznana wartość `system=` to `ValidationError`.

### 2.2 NMT — Czechy (CUZK, etap 1, v0.7.0-dev) - IN SCOPE

```python
# Funkcjonalności (DMR — Digitalni model reliefu, odpowiednik NMT):
- DMR 5G (rozdzielczość 2m) — pobieranie po godle TM33 (siatka 2x2 km,
  EPSG:3045, obliczalna) LUB po bbox przez exportImage (ArcGIS ImageServer)
- DMR 4G (rozdzielczość 5m) — pobieranie po godle SM5 (indeks arkuszy
  KladyMapovychListu, EPSG:5514) LUB po bbox przez exportImage
- Selekcja obszaru: godło (TM33/SM5), bbox, plik geometrii — `--country
  {pl,cz,auto}`; `auto` wykrywa kraj z godła/bboxa, dzieli bbox/geometrię
  transgraniczną na osobne pliki per kraj (bez scalania — dziś scala
  konsument, np. Hydrograf; scalanie PL+CZ w jedną powierzchnię to etap 2,
  R6 — sekcja 3.1)
- Reprojekcja pozioma **lokalna** (rasterio.warp + przypięta operacja; serwer
  dostaje żądania wyłącznie w natywnym EPSG:5514 — ADR-024):
  `--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}` — tylko w trybie
  `--bbox`/`--geometry` (z godłem = błąd; symetrycznie do PL od 0.7.0);
  krok datum S-JTSK → ETRS89 przypięty do czeskich operacji EPSG:1622/1623
  (dokładność deklarowana 1,0 m; ADR-024 errata 2)
- Układ wysokościowy natywny: Bpv (Baltic 1957, EPSG:8357); opcjonalna
  transformacja do EVRF2007 (EPSG:5621, przypięta operacja 0,1 m); KRON86
  nieosiągalny (brak publicznych siatek Bpv→KRON86)
- `extra.parent_request` w sidecarach trybu bbox/geometry — grupowanie
  plików jednego zadania po obu stronach granicy PL/CZ

# Źródło: CUZK (Český úřad zeměměřický a katastrální)
# API: ArcGIS REST (query, exportImage) + pliki openzu (ZIP z TIFF+TFW)
# Licencja: CC BY 4.0
```

**Poza zakresem etapu 1 (planowane — etap 2/3):** DMP (Digitalni model
povrchu, odpowiednik NMPT), Ortofoto CZ, LAZ/LIDAR CZ (etap 2); ZABAGED
(wektorowa baza topograficzna, odpowiednik BDOT10k, 149 warstw — etap 3).
Wielokąt granicy administracyjnej (zamiast prostokątnej obwiedni kraju) —
patrz sekcja 3.2, znane ograniczenie.

### 2.3 NMPT (Numeryczny Model Pokrycia Terenu) - IN SCOPE

```python
# Funkcjonalności:
- Digital Surface Model (DSM) — teren + obiekty (drzewa, budynki)
- Pobieranie przez godło → ASC (OpenData)
- Pobieranie przez bbox → GeoTIFF (WCS) — z biblioteki (`download_bbox`);
  CLI `--bbox` pobiera arkusze OpenData
- Rozdzielczość: tylko 1m
- Układy wysokościowe: KRON86, EVRF2007
- Dziedziczenie z GugikProvider (wspólna logika pobierania)

# Źródło: GUGiK
# API: WCS, WMS GetFeatureInfo, OpenData
```

### 2.4 Ortofotomapa - IN SCOPE

```python
# Funkcjonalności:
- Zdjęcia lotnicze Standard Resolution (25cm)
- Pobieranie przez godło → TIF (OpenData)
- Pobieranie przez bbox → GeoTIFF (WCS) — z biblioteki (`download_bbox`);
  CLI `--bbox` pobiera arkusze OpenData
- Brak vertical CRS (2D RGB); domyślnie najnowszy zgodny rekord RGB z
  GetCapabilities/GetFeatureInfo; `GugikOrtoProvider(color="CIR")` wybiera
  wariant podczerwieni
- Obsługa formatów WCS: GTiff, PNG, JPEG

# Źródło: GUGiK
# API: WCS, WMS GetFeatureInfo, OpenData
```

### 2.5 LAZ (Chmury Punktów LIDAR) - IN SCOPE

```python
# Funkcjonalności:
- Chmury punktów ALS (dane pomiarowe LIDAR), format .laz
- Discovery area-based przez godło (≤1:10000) / bbox / geometry → WFS
  GetFeature, bbox i envelope w porządku osi EPSG (N,E), filtr przecięcia;
  błąd jednego rocznika przerywa odkrywanie (`DownloadError`)
- Kafle drobniejsze niż 1:10000 (jedno godło 1:10000 → wiele kafli .laz)
- url_do_pobrania brany wprost z atrybutu WFS (godło kafla nieparsowane)
- Domyślnie najnowszy kafel per obszar (ADR-029); flagi --year, --vertical-crs, --min-density
- Dwa układy wysokościowe: EVRF2007 (domyślny, 2018+), KRON86 (legacy, 2010-2019)
- Pobieranie równoległe (--workers), pomijanie istniejących plików

# Źródło: GUGiK
# API: WFS (GetCapabilities + GetFeature), OpenData
```

### 2.6 Land Cover (Pokrycie Terenu) - IN SCOPE

```python
# BDOT10k (GUGiK):
- 15 warstw (12 pokrycia terenu PT* + 3 hydrograficzne SW*)
- Pobieranie calego pliku BDOT10k (wszystkie warstwy)
- Pobieranie przez TERYT (powiat)
- Pobieranie przez godło lub bbox
- Format: GeoPackage, Shapefile
- Automatyczne scalanie warstw z zachowaniem rtree spatial index

# CORINE Land Cover (Copernicus):
- 44 klasy pokrycia terenu
- Lata: 1990, 2000, 2006, 2012, 2018
- Pobieranie przez godło lub bbox
- Format: GeoTIFF (CLMS API) lub PNG (WMS fallback)
- OAuth2 RSA authentication (opcjonalne)
- Auth Proxy dla izolacji credentials
```

### 2.7 SoilGrids (Dane Glebowe) - IN SCOPE

```python
# ISRIC SoilGrids:
- 11 parametrów glebowych (clay, sand, silt, soc, pH, etc.)
- 6 głębokości (0-5cm do 100-200cm)
- 5 statystyk (mean, Q0.05, Q0.5, Q0.95, uncertainty)
- Rozdzielczość: 250m (globalne)
- Pobieranie przez godło lub bbox (BEZ TERYT — patrz 3.2)
- Format: GeoTIFF

# Źródło: ISRIC (International Soil Reference and Information Centre)
# API: WCS
```

### 2.8 HSG (Hydrologic Soil Groups) - IN SCOPE

```python
# Kalkulacja HSG dla metody SCS-CN:
- Klasyfikacja tekstury wg trójkąta USDA (12 klas)
- Mapowanie tekstury → HSG (A, B, C, D)
- Automatyczne pobieranie clay/sand/silt z SoilGrids
- Statystyki pokrycia dla każdej grupy
- Format wyjściowy: GeoTIFF (wartości 1-4)

# Moduł: kartograf.hydrology.hsg
```

### 2.9 CLI Interface - IN SCOPE

```bash
# Komendy:
kartograf parse <godlo>                    # info o godle (PL-1992 lub PL-2000)
kartograf parse 6.179.12.20               # PL-2000 auto-detekcja
kartograf download <godlo>                 # pobierz NMT
kartograf download <godlo> --product nmpt  # pobierz NMPT
kartograf download <godlo> --product orto  # pobierz ortofoto
kartograf download <godlo> --product laz   # pobierz chmury punktów LAZ (wiele kafli)
kartograf download --bbox ... --product laz --year 2024 --min-density 12
kartograf download --bbox min_x,min_y,max_x,max_y  # NMT dla bbox
kartograf download --bbox ... --system 2000  # NMT w ukladzie PL-2000
kartograf download --bbox ... --product orto  # ortofoto dla bbox
kartograf download --geometry area.shp         # NMT z pliku geometrii
kartograf download --geometry area.gpkg --layer catchments
kartograf download <godlo> --resolution 5m # NMT 5m
kartograf download 302_5550 --country cz               # DMR 5G (CZ), godlo TM33
kartograf download CTES96 --resolution 5m               # DMR 4G (CZ), godlo SM5, kraj auto
kartograf download --bbox ... --bbox-crs EPSG:4326 --country auto   # bbox transgraniczny -> pliki per kraj
kartograf download --bbox ... --country cz --target-crs EPSG:2180   # reprojekcja lokalna (pinned)
kartograf download --bbox ... --country pl --target-crs EPSG:2180   # wycinek PL: jeden GeoTIFF (ADR-027)
kartograf download 302_5550 --country cz --vertical-crs EVRF2007    # Bpv -> EVRF2007 (EPSG:5621)
kartograf landcover download --source bdot10k --teryt <kod>
kartograf landcover download --source corine --godlo <godlo>
kartograf landcover download --source soilgrids --property <param>  # --godlo/--bbox (bez --teryt)
kartograf landcover list-sources
kartograf landcover list-layers --source <source>
kartograf soilgrids hsg --godlo <godlo>    # oblicz HSG
kartograf cache stats|clear|path           # cache metadanych (SQLite)
```

### 2.10 Python API - IN SCOPE

```python
# Public API (kartograf/__init__.py):
from kartograf import (
    # Core
    SheetParser, Parser2000, ParserTM33, BBox,
    find_sheets_for_bbox, find_sheets_2000_for_bbox, find_sheets_for_geometry,
    # Download (NMT/NMPT/Orto/LAZ)
    DownloadManager, DownloadProgress, DownloadResult, FileStorage,
    # Download — wycinek PL (ADR-027)
    PlCutout, PlCutoutResult, PlCutoutSheets,
    download_pl_cutout, prepare_pl_cutout, run_pl_cutout, select_pl_cutout_sheets,
    # Cache
    MetadataCache,
    # Land Cover
    LandCoverManager,
    # Providers
    BaseProvider, GugikProvider, GugikNmptProvider, GugikOrtoProvider,
    GugikLazProvider, LazTile,
    LandCoverProvider, Bdot10kProvider, CorineProvider, SoilGridsProvider,
    # Providers — CZ (CUZK, etap 1)
    CuzkDmrProvider, create_dmr_provider,
    # Hydrology
    HSGCalculator,
    # Exceptions
    KartografError, ParseError, ValidationError, DownloadError, NoCoverageError,
)
```

### 2.11 Układ danych na dysku - IN SCOPE

- `data/<produkt>/<kraj>_<układ>[_<wariant>][_<vcrs>]/...` (ADR-026);
  kanoniczna tabela segmentów i migracja 0.6.x→0.7.0:
  `docs/ARCHITECTURE.md` sekcja 3
- Wycinki w `<segment>/bbox/<coords><ext>`: każde `--bbox`/`--geometry` CZ
  oraz `--bbox`/`--geometry` PL **tylko z `--target-crs`** (bez tej flagi PL
  zapisuje arkusze w hierarchii godeł)
- `<układ>` w segmencie (`pl_1992` vs `pl_2000`) rozstrzyga format godła
  każdego pliku z osobna — jeden stary katalog (np. `orto/`) rozchodzi się
  przy migracji na dwa segmenty; wyjątek: kafle LAZ — układ z `uklad_xy`
  kafla (`LazTile.uklad`), dopiero w drugiej kolejności z formatu godła
- Kampanie GUGiK (ADR-030): prawdziwe pliki NMT/NMPT/orto PL w
  `<segment>/kampanie/<data>_<id>/...`, ścieżka standardowa = dowiązanie do
  najnowszej lokalnej kampanii (symlink → hardlink → kopia); brak migracji
- `landcover/` bez zmian (własny default `--output`)

### 2.12 Kampanie GUGiK (ADR-030) - IN SCOPE

```python
# Strategie (tylko PL; CZ zawsze bieżąca mozaika):
- --campaigns newest (domyślnie): najnowszy rekord skorowidza (ADR-028),
  sprawdzany przy każdym uruchomieniu po wygaśnięciu cache (7 dni)
- --campaigns all: każda kampania arkusza po twardym filtrze ADR-028, bez limitu
- --min-year RRRR: dolna granica roku pozyskania (aktualnosc), obie strategie
- LAZ: --campaigns all (kafle z ramą przecinającą obszar, bez deduplikacji ADR-029), --min-year (akt_rok)
- Wycinek --target-crs: zawsze newest (all/--min-year = Error:)
- API: DownloadManager(campaigns=, min_year=), SheetFetch, CampaignRef
```

---

## 3. Out of Scope - Wersja 0.7.0

### 3.1 Funkcjonalności Zaplanowane - FUTURE

```python
# Etap 2 (CZ, po etapie 1):
- DMP (Digitalni model povrchu) — odpowiednik NMPT
- Ortofoto CZ, LAZ/LIDAR CZ
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
- Wycinek PL --target-crs z arkuszy PL-2000 (reprojekcja arkuszy,
  mozaika międzystrefowa; dziś błąd z opisem)

# Kampanie — poza zakresem 0.7.0 (odrzucone w ADR-030):
- --campaign <id> (wybór jednej kampanii), strategie coverage i mosaic
- Narzędzie składania kampanii w jedną powierzchnię — 0.7.1
- Kampanie dla CZ (CUZK nie publikuje historii) — backlog po 0.7.0

# Etap 3 (CZ):
- ZABAGED — wektorowa baza topograficzna (149 warstw), odpowiednik BDOT10k

# Później — inne kraje:
- Niemcy (DE) — federacja 17 modeli krajów związkowych (BKG/basemap.de)
- Słowacja (SK) — DMR 5.0, ZBGIS (uwaga: WCS zwraca wysokości elipsoidalne)

# Wersja 1.0+:
- GUI interface
- Integracja z PostGIS
- REST API server
```

### 3.2 Ograniczenia Techniczne

```
- Brak weryfikacji integralności plików (checksums)
- Timeouty domyślne: 30 s dla NMT/NMPT (GUGiK) i dla discovery WFS w LAZ,
  60 s dla Ortofoto, pobierania kafli LAZ, CORINE (bbox/godło), CUZK oraz
  SoilGrids przez godło, 120 s dla BDOT10k (wszystkie tryby) oraz SoilGrids
  przez bbox i HSG (CORINE/SoilGrids przez TERYT: NotImplementedError);
  GetCapabilities skorowidza GUGiK dziedziczy timeout providera
- Max 3 próby retry (nie konfigurowalne); ponawiane tylko błędy sieci,
  HTTP 429 i 5xx — inne 4xx (np. 404) kończą od razu
- Synchroniczne pobieranie w obrębie jednego pliku (równoległość tylko
  między plikami, przez ThreadPoolExecutor/--workers)
- NMT 5m (PL) wymaga EVRF2007
- WCS (download_bbox) dla NMT działa tylko dla 1m i tylko w KRON86 —
  endpoint EVRF2007 wycofany przez GUGiK (404 od 2026-08), pod EVRF2007 jest
  ValidationError przed wyjściem w sieć; WCS NMPT i Ortofoto nie są tym objęte
- SoilGrids: tylko WGS84 bbox (transformacja automatyczna)
- SoilGrids: brak selekcji po TERYT — `--teryt` dotyczy wyłącznie bdot10k,
  a `SoilGridsProvider.download_by_teryt` rzuca NotImplementedError (wcześniej
  cicho zwracał kwadrat 60x60 km wokół środka województwa); użyj --bbox/--godlo
- find_sheets_for_bbox/find_sheets_for_geometry: stykające się krawędzie NIE
  są przecięciem (wymagane dodatnie pole) — bbox równy arkuszowi w EPSG:4326
  zwraca tylko jego arkusze (w EPSG:2180 także fragmenty sąsiadów), a bbox
  zdegenerowany do punktu → dokładnie jeden arkusz
- Skorowidz GUGiK: retry (do 3 prób: sieć, 429, 5xx), sesja per wątek; awaria warstwy /
  szablonu przerywa z DownloadError, bez degradacji kampanii. Rekord musi
  mieć całe godło, zgodny układ i rozdzielczość; w pierwszej warstwie
  z pasującymi rekordami wygrywa najnowsza data. Brak rekordu daje
  NoCoverageError; extra.source / extra.sheet_sources zachowują pochodzenie.
  Cache PL zapisuje pełen rekord albo brak pokrycia (TTL 7 dni); --force pomija
  odczyt i zapisuje świeży wpis (w CZ tak samo dla indeksu arkuszy SM5)

# CZ (CUZK, etap 1) — dodatkowe ograniczenia:
- Produkt CZ w etapie 1: wyłącznie nmt (DMR 5G/4G) — nmpt/orto/laz w etapie 2
- exportImage: sufity usługi 15000x4100 px, praktyczny limit ~8 Mpx;
  klient kafelkuje według budżetu 4 Mpx na żądanie, snap NW daje piksel
  dokładnie 2 m/5 m, a krawędź E/S może różnić się o <= 1/2 px
- KRON86 nieosiągalny dla CZ (brak publicznych siatek Bpv→KRON86) — jedyna
  transformacja pionowa to Bpv→EVRF2007 (EPSG:5621)
- --target-crs działa tylko z --bbox/--geometry; z godłem CZ = ValidationError
- --target-crs dla PL: tylko nmt i system 1992 (nmpt/orto — etap 2; mozaika
  międzystrefowa PL-2000 — etap 2); arkusz bez danych GUGiK (NoCoverageError:
  morze, zagraniczna strona bboxa — CZ, DE, SK/UA/BY/LT/RU) = nodata +
  Warning: + extra.missing_sheets, każda inna porażka pobrania arkusza i brak
  danych we WSZYSTKICH arkuszach = kod 1 dla części PL (pod --country auto
  przy sukcesie CZ: kod 0 + Warning:, patrz niżej) — R5, 2026-09-28,
  potwierdzone na żywo 2026-09-29; missing_sheets wymienia tylko arkusze bez
  pliku — nodata bywa też wewnątrz pobranych arkuszy przybrzeżnych
  i przygranicznych (PL-SK: do 82 % arkusza); arkusz we współrzędnych PL-2000
  = błąd; scalanie PL+CZ w jedną powierzchnię przygraniczną — etap 2 (R6)
- Istniejący wycinek jest pomijany bez sieci; biblioteka
  PlCutoutResult(skipped=True) odtwarza missing_sheets/off_grid_sheets
  z sidecara, CLI przypomina Warning: o brakach. --force ponownie pobiera
  także arkusze i omija odczyt cache rekordów (świeży rekord zapisuje); tańszy rebuild: usunąć tylko wycinek.
  Nieudana przebudowa nie kasuje poprzedniego pliku. Kontrola miejsca na
  dysku korzysta z wcześniej ustalonego zbioru brakujących arkuszy;
  Info: dla wyniku >= 1 GiB, bez twardego limitu rozmiaru
- Lista arkuszy PL (--bbox/--geometry bez --target-crs oraz hierarchia
  godła) próbuje wszystkie arkusze niezależnie od --workers. R5:
  NoCoverageError -> pominięcie, Warning: i status no_coverage;
  >= 1 plik, bez twardej awarii = kod 0; wszystkie arkusze bez danych
  albo dowolna awaria inna niż brak pokrycia = kod 1 (lista wszystkich
  awarii). Pojedynczy arkusz bez danych = kod 1
- Asymetria trybu --bbox: PL bez --target-crs zwraca listę arkuszy (wiele
  plików), CZ zawsze jeden plik (wycinek exportImage, pobierany natywnie
  w 5514 i reprojektowany lokalnie, gdy zażądano innego układu); z
  --target-crs PL także daje jeden plik (ADR-027)
- CountryProfile.extent_wgs84 dla CZ to PROSTOKĄT (obwiednia), nie wielokąt
  granicy — --country auto w pasie na zachód od 18,86°E i na południe od
  51,06°N (m.in. Opole, Wałbrzych, Rybnik, południowe obrzeża Wrocławia;
  Kraków, Rzeszów i centrum Wrocławia są już poza prostokątem) wysyła
  zapytanie do CUZK także dla bboxów leżących w całości w Polsce, a także
  w Saksonii poniżej 51,06°N i w pasie Bogatyni (dodatkowy raster
  cały nodata = Warning: na stderr i kod 0). Symetrycznie prostokąt PL
  (14,07..24,20°E, 49,00..54,90°N) pokrywa
  większość Czech, więc auto w Pradze, Brnie czy Ostrawie odpytuje także
  GUGiK — naprawa (wielokąt granicy) planowana w etapie 2 (patrz ADR-023)
- --country domyślnie = auto (nowość 0.7.0): na obszarze spornym flagi bez
  odpowiednika czeskiego (--product nmpt|orto, --system, --vertical-crs
  KRON86, --resolution 1m) ROZSTRZYGAJĄ kraj do pl z komunikatem Info: na
  stderr, zamiast przewracać zadanie; wyjątkiem jest --product laz, który ma
  własny przepływ i na obszarze sięgającym CZ nadal kończy się błędem
  z podpowiedzią --country pl
- --country auto przycina część zadania każdego kraju do prostokąta,
  wypisuje `Info:` o przycięciu i o obszarze pominiętym poza obiema
  obwiedniami. Nazwa pliku i request.bbox niosą część przyciętą,
  extra.parent_request oryginalne zadanie; nietknięte krawędzie PL zachowują
  oryginalne współrzędne (bez poszerzania na tych krawędziach).
  Jawne --country pl nie przycina, --geometry bez --target-crs wyznacza
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
  (EPSG:5514 albo --target-crs), auto/pl — EPSG:2180, a plik w EPSG:5514/3045
  — układ pliku (od 2026-09-28: obwiednia opuszcza Krovaka przypiętą
  operacją); plik w EPSG:5514 bez --target-crs daje więc ten sam bbox_crs we
  wszystkich trybach — znane ograniczenie klucza grupowania, do ujednolicenia
  w etapie 2
- extra.parent_request.countries = kraje PRÓBOWANE, nie pobrane (przy
  awarii jednego kraju w trybie auto sidecary drugiego nadal niosą oba kody)
```

---

## 4. Architektura

### 4.1 Moduły

```
kartograf/
├── __init__.py           # Public API exports
├── exceptions.py         # KartografError, ParseError, ValidationError, DownloadError, NoCoverageError
├── core/                 # Logika bazowa
│   ├── bbox.py              # BBox, validate_bbox, transform_bbox, is_czech_crs
│   ├── sheet_parser.py      # SheetParser — parser godeł map topograficznych
│   ├── parser_2000.py       # Parser2000 — parser godeł PL-2000
│   ├── parser_tm33.py       # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045)
│   ├── parser_registry.py   # Rejestr systemów godeł (pl1992, pl2000, cz_tm33, cz_sm5)
│   └── geometry.py          # SHP/GPKG reading, find_sheets_for_geometry, get_overall_bbox
├── sources/               # Deskryptory źródeł jako dane (zero IO przy imporcie)
│   ├── descriptor.py        # SourceDescriptor, AccessChannel (+endpoint), TransportKind, LicenseInfo, CountryProfile
│   ├── registry.py          # Rejestr PL/CZ/EU/GLOBAL — get_source, sources_for, get_country, all_countries, vertical_crs_code, resolve_vertical_crs
│   └── sidecar.py           # ResultMetadata, build_metadata (capability=, nodata=), write_sidecar (<plik>.meta.json)
├── transform/             # Transformacje CRS i rastrów
│   ├── crs.py                # TransformerGroup (allow_ballpark=False, probe pod polityką sieci); PinnedTransform.transform polimorficzne
│   └── raster.py             # warp_to_grid — lokalny warp na siatkę, operacja WYMUSZONA (ADR-027)
├── transport/             # Wspólny transport pobierania
│   ├── http.py               # download_to — atomic write + retry
│   └── mosaic.py             # mosaic_and_crop — merge kafli (rasterio) + przycięcie (opcjonalnie na siatce zrodel, zrodla w VRT)
├── providers/             # Providery danych
│   ├── base.py               # DataSourceProvider (ABC), BaseProvider (NMT), LandCoverProvider
│   ├── pl/                   # Providery polskie
│   │   ├── gugik.py             # GugikProvider (NMT)
│   │   ├── gugik_nmpt.py        # GugikNmptProvider (NMPT/DSM)
│   │   ├── gugik_orto.py        # GugikOrtoProvider (Ortofotomapa)
│   │   ├── gugik_laz.py         # GugikLazProvider (chmury punktów LAZ, WFS)
│   │   ├── bdot10k.py           # Bdot10kProvider
│   │   └── __init__.py          # create_nmt_provider() — fabryka domyślnych NMT
│   ├── cuzk/                  # Providery czeskie (CUZK, etap 1)
│   │   ├── client.py            # CuzkClient — silnik sterowany deskryptorem (ArcGIS REST + openzu)
│   │   ├── sheets.py            # SheetIndex/SheetInfo — indeks arkuszy SM5/TM33
│   │   ├── dmr.py               # CuzkDmrProvider — DMR 5G/4G
│   │   └── __init__.py          # create_dmr_provider() — fabryka domyślnych CZ
│   ├── corine.py             # CorineProvider
│   └── soilgrids.py          # SoilGridsProvider
├── cache/                 # Cache metadanych
│   └── metadata.py           # MetadataCache — SQLite WAL (URL/TERYT TTL 7d, Sheet TTL 30d)
├── download/              # Download management (NMT/NMPT/Orto; CZ ma własny przepływ w CLI)
│   ├── cutout.py             # Wycinek PL --target-crs jako API (download_pl_cutout; prepare/select/run)
│   ├── manager.py            # DownloadManager (sidecar_extra=..., download_sheets/expand_sheets)
│   └── storage.py            # FileStorage(vertical_crs=) — segmenty z szablonów deskryptora (ADR-026)
├── landcover/             # Land Cover management
│   └── manager.py
├── hydrology/             # Obliczenia hydrologiczne
│   └── hsg.py                # HSGCalculator
├── auth/                  # Autentykacja (CLMS)
│   ├── proxy.py               # Auth Proxy server
│   └── client.py               # Auth Proxy client
└── cli/                   # CLI interface (podzielony na moduły per komenda)
    ├── _parser.py             # argparse — top-level + subkomendy (--country, --target-crs PL/CZ)
    ├── parse_cmd.py           # `kartograf parse`
    ├── download_cmd.py        # `kartograf download` (godło / bbox / geometry / LAZ / CZ)
    ├── landcover_cmd.py       # `kartograf landcover`
    ├── soilgrids_cmd.py       # `kartograf soilgrids`
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
```

---

## 5. Źródła Danych

| Źródło | Typ danych | API | Autentykacja |
|--------|-----------|-----|--------------|
| GUGiK | NMT, NMPT, Ortofoto, LAZ, BDOT10k | WCS, WMS, WFS, OpenData | Brak |
| CUZK (etap 1) | NMT/DMR 5G/4G (Czechy) | ArcGIS REST (query, exportImage) + pliki openzu | Brak |
| Copernicus CLMS | CORINE | REST API | OAuth2 RSA |
| EEA Discomap | CORINE (podgląd) | WMS | Brak |
| ISRIC SoilGrids | Gleba | WCS | Brak |

---

## 6. Success Criteria

### 6.1 Funkcjonalne

```
- Parser poprawnie parsuje godła 1:1M - 1:10k (PL-1992), PL-2000, TM33/SM5 (CZ)
- NMT pobiera się w rozdzielczościach 1m i 5m (PL), 2m i 5m (CZ)
- BDOT10k pobiera się przez TERYT i godło
- CORINE pobiera się przez godło (GeoTIFF lub PNG fallback)
- SoilGrids pobiera dane glebowe
- HSG oblicza grupy hydrologiczne z danych SoilGrids
- DMR CZ (CUZK) pobiera się przez godło (TM33/SM5) i bbox (exportImage),
  z opcjonalną reprojekcją poziomą (--target-crs) i pionową (--vertical-crs)
- Bbox/geometria transgraniczna PL/CZ dzieli się na osobne pliki per kraj
  (--country auto), bez scalania, ze wspólnym extra.parent_request
- Wycinek NMT PL (--target-crs / download_pl_cutout): jeden GeoTIFF na
  siatce arkuszy (EPSG:2180) albo w EPSG:5514/3045; arkusz bez danych =
  nodata + extra.missing_sheets
- Integracja z Hydrograf/Hydrolog działa
```

### 6.2 Jakościowe

```
- 2057 testów offline przechodzi (`pytest -m "not live"`); 16 testów live
  wymaga sieci i nie należy do bramki offline
- Kod zgodny z ruff (check + format), mypy bez nowego długu względem baseline
- Dokumentacja aktualna; po naprawach potrzebne ponowne E2E na żywych
  serwisach dla scenariuszy L1-L7
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
| 2026-08-18 | 3.7 | Przegląd spójności dokumentacji: status mergu etapu 1, nagłówek sekcji 2 (0.5.0→0.7.0), komenda `cache` w 2.9, brakujące eksporty w 2.10, liczba testów 1402 |
| 2026-08-22 | 3.8 | Korekty spójności po audycie przedwydaniowym 0.7.0: WCS NMT tylko 1m/KRON86, 4 warstwy WMS ortofoto, SoilGrids bez TERYT, timeouty per źródło, konwencja krawędzi i etykiety skal, semantyka `--country auto` (zasięg prostokąta CZ/PL, Info/Warning, częściowy sukces), liczby 1716/93% |
| 2026-08-28 | 3.9 | Układ data/ per produkt (ADR-026), --target-crs dla PL (ADR-027), sekcja 2.11, liczby 1775/93% (brama jakosci) |
| 2026-09-28 | 3.10 | Fala review max: wycinek PL jako API biblioteki (download_pl_cutout), siatka arkuszy, R5 (NoCoverageError -> nodata + extra.missing_sheets), eksporty w 2.10, drzewo modulow, etap 2: scalanie PL+CZ i wycinek z arkuszy PL-2000; liczby 1861/92,9% (po fali naprawczej finalnego review) |
| 2026-09-29 | 3.11 | Historyczne testy na żywo i audyt przed falą naprawczą: diagnozy LAZ, S-JTSK, skorowidza, orto, limitu CUZK i dyspozycji kraju; dowody zachowania na morzu i pograniczach oraz wejście do R6 |
| 2026-09-30 | 3.12 | Aktualizacja po fali naprawczej: filtr rekordow GUGiK i cache, R5 w liscie/hierarchii, W1/blad fazy w 2180, pin EPSG:1622/1623, budzet 4 Mpx, osie LAZ; 2057 offline + 16 live nieuruchomionych |
| 2026-10-07 | 3.13 | Kampanie GUGiK (ADR-030): sekcja 2.12, uklad `kampanie/` z dowiazaniem w 2.11, odrzucone strategie w 3.1 |

---

**Wersja dokumentu:** 3.13
**Data ostatniej aktualizacji:** 2026-10-07
**Status:** Rozwoj — v0.7.0 (Unreleased), etap 1 zmergowany do `develop` 2026-08-12
