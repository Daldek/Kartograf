# SCOPE.md - Zakres Projektu Kartograf
**Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 3.8
**Data:** 2026-08-22
**Status:** Rozwoj — v0.7.0 (Unreleased), etap 1 (CZ/CUZK) zmergowany do `develop` 2026-08-12; ostatni wydany tag: v0.6.1

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
- Rozdzielczości: 1m (GRID1), 5m (GRID5)
- Układy wysokościowe: KRON86, EVRF2007

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
przecięciem. Bbox równy arkuszowi zwraca więc tylko jego własne arkusze
(`N-34-130-D` w skali 1:50000 → 4, nie 9), a bbox zdegenerowany do punktu →
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
  transgraniczną na osobne pliki per kraj (bez scalania — zadanie Hydrografu)
- Reprojekcja pozioma **lokalna** (rasterio.warp + przypięta operacja; serwer
  dostaje żądania wyłącznie w natywnym EPSG:5514 — ADR-024):
  `--target-crs {EPSG:2180,EPSG:5514,EPSG:3045}` — tylko w trybie
  `--bbox`/`--geometry` (z godłem = błąd)
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
- Pobieranie przez bbox → GeoTIFF (WCS)
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
- Pobieranie przez bbox → GeoTIFF (WCS)
- Brak vertical CRS (2D RGB)
- 4 warstwy WMS (2026, 2025, 2024 + Starsze — roczniki 2018-2023
  skonsolidowane przez GUGiK w jedną warstwę `SkorowidzeOrtofotomapyStarsze`)
- Obsługa formatów WCS: GTiff, PNG, JPEG

# Źródło: GUGiK
# API: WCS, WMS GetFeatureInfo, OpenData
```

### 2.5 LAZ (Chmury Punktów LIDAR) - IN SCOPE

```python
# Funkcjonalności:
- Chmury punktów ALS (dane pomiarowe LIDAR), format .laz
- Discovery area-based przez godło (≤1:10000) / bbox / geometry → WFS GetFeature
- Kafle drobniejsze niż 1:10000 (jedno godło 1:10000 → wiele kafli .laz)
- url_do_pobrania brany wprost z atrybutu WFS (godło kafla nieparsowane)
- Domyślnie newest-per-tile; flagi --year, --vertical-crs, --min-density
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
    KartografError, ParseError, ValidationError, DownloadError,
)
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
  SoilGrids przez godło, 120 s dla BDOT10k (wszystkie tryby), CORINE przez
  TERYT oraz SoilGrids przez bbox i HSG
- Max 3 próby retry (nie konfigurowalne)
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
  są przecięciem (wymagane dodatnie pole) — bbox równy arkuszowi zwraca tylko
  jego arkusze, a bbox zdegenerowany do punktu → dokładnie jeden arkusz

# CZ (CUZK, etap 1) — dodatkowe ograniczenia:
- Produkt CZ w etapie 1: wyłącznie nmt (DMR 5G/4G) — nmpt/orto/laz w etapie 2
- exportImage: limit ASYMETRYCZNY 15000x4100 px — większe bboxy kafelkowane
  po stronie klienta (mosaic_and_crop)
- KRON86 nieosiągalny dla CZ (brak publicznych siatek Bpv→KRON86) — jedyna
  transformacja pionowa to Bpv→EVRF2007 (EPSG:5621)
- --target-crs działa tylko z --bbox/--geometry; z godłem CZ = ValidationError
- Asymetria trybu --bbox: PL zwraca listę arkuszy (wiele plików), CZ zwraca
  jeden plik (wycinek exportImage, pobierany natywnie w 5514 i reprojektowany
  lokalnie, gdy zażądano innego układu)
- CountryProfile.extent_wgs84 dla CZ to PROSTOKĄT (obwiednia), nie wielokąt
  granicy — --country auto w pasie na zachód od 18,86°E i na południe od
  51,06°N (m.in. Opole, Wałbrzych, Rybnik, południowe obrzeża Wrocławia;
  Kraków, Rzeszów i centrum Wrocławia są już poza prostokątem) wysyła
  zapytanie do CUZK także dla bboxów leżących w całości w Polsce (wynik:
  dodatkowy raster/sidecar wypełniony nodata, nie błąd). Symetrycznie
  prostokąt PL (14,07..24,20°E, 49,00..54,90°N) pokrywa większość Czech, więc
  auto w Pradze, Brnie czy Ostrawie odpytuje także GUGiK — naprawa (wielokąt
  granicy) planowana w etapie 2 (patrz ADR-023)
- --country domyślnie = auto (nowość 0.7.0): na obszarze spornym flagi bez
  odpowiednika czeskiego (--product nmpt|orto, --system, --vertical-crs
  KRON86, --resolution 1m) ROZSTRZYGAJĄ kraj do pl z komunikatem Info: na
  stderr, zamiast przewracać zadanie; wyjątkiem jest --product laz, który ma
  własny przepływ i na obszarze sięgającym CZ nadal kończy się błędem
  z podpowiedzią --country pl
- Częściowy sukces w trybie auto (jeden kraj pobrany, drugi bez danych) to
  kod wyjścia 0 + Warning: na stderr; kod 1 zostaje dla jawnego --country
  i dla porażki wszystkich krajów (ADR-023 pkt 4-5). Info:/Warning: idą na
  stderr, więc -q ich NIE tłumi
- extra.parent_request.bbox_crs różni się per tryb dla tego samego pliku
  geometrii (jawny --country cz: CRS pliku; auto/pl: EPSG:2180) — znane
  ograniczenie klucza grupowania, do ujednolicenia w etapie 2
- extra.parent_request.countries = kraje PRÓBOWANE, nie pobrane (przy
  awarii jednego kraju w trybie auto sidecary drugiego nadal niosą oba kody)
```

---

## 4. Architektura

### 4.1 Moduły

```
kartograf/
├── __init__.py           # Public API exports
├── exceptions.py         # KartografError, ParseError, ValidationError, DownloadError
├── core/                 # Logika bazowa
│   ├── sheet_parser.py      # SheetParser — parser godeł map topograficznych, BBox
│   ├── parser_2000.py       # Parser2000 — parser godeł PL-2000
│   ├── parser_tm33.py       # ParserTM33 — obliczalna siatka kafli CZ 2x2 km (EPSG:3045)
│   ├── parser_registry.py   # Rejestr systemów godeł (pl1992, pl2000, cz_tm33, cz_sm5)
│   └── geometry.py          # SHP/GPKG reading, find_sheets_for_geometry, get_overall_bbox
├── sources/               # Deskryptory źródeł jako dane (zero IO przy imporcie)
│   ├── descriptor.py        # SourceDescriptor, AccessChannel (+endpoint), TransportKind, LicenseInfo, CountryProfile
│   ├── registry.py          # Rejestr PL/CZ/EU/GLOBAL — get_source, sources_for, get_country, all_countries, vertical_crs_code, resolve_vertical_crs
│   └── sidecar.py           # ResultMetadata, build_metadata (capability=, nodata=), write_sidecar (<plik>.meta.json)
├── transform/             # Transformacje CRS
│   └── crs.py                # TransformerGroup (allow_ballpark=False, probe pod polityką sieci); PinnedTransform.transform polimorficzne
├── transport/             # Wspólny transport pobierania
│   ├── http.py               # download_to — atomic write + retry
│   └── mosaic.py             # mosaic_and_crop — merge kafli (rasterio) + przycięcie
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
│   │   ├── sheets.py            # SheetIndex/SheetInfo/Sm5Sheet — indeks arkuszy SM5/TM33
│   │   ├── dmr.py               # CuzkDmrProvider — DMR 5G/4G
│   │   └── __init__.py          # create_dmr_provider() — fabryka domyślnych CZ
│   ├── corine.py             # CorineProvider
│   └── soilgrids.py          # SoilGridsProvider
├── cache/                 # Cache metadanych
│   └── metadata.py           # MetadataCache — SQLite WAL (URL/TERYT TTL 7d, Sheet TTL 30d)
├── download/              # Download management (NMT/NMPT/Orto; CZ ma własny przepływ w CLI)
│   ├── manager.py            # DownloadManager (sidecar_extra=...)
│   └── storage.py            # FileStorage (subdir sterowany deskryptorem)
├── landcover/             # Land Cover management
│   └── manager.py
├── hydrology/             # Obliczenia hydrologiczne
│   └── hsg.py                # HSGCalculator
├── auth/                  # Autentykacja (CLMS)
│   ├── proxy.py               # Auth Proxy server
│   └── client.py               # Auth Proxy client
└── cli/                   # CLI interface (podzielony na moduły per komenda)
    ├── _parser.py             # argparse — top-level + subkomendy (--country, --target-crs)
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
- Integracja z Hydrograf/Hydrolog działa
```

### 6.2 Jakościowe

```
- 1716 testów przechodzi
- Pokrycie testami 93% (cel 80% osiągnięty)
- Kod zgodny z ruff (check + format)
- mypy bez nowego długu względem baseline
- Type hints wszędzie
- Dokumentacja aktualna
- E2E na żywych danych: 11/11 PASS (etap 1, CZ+PL)
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

---

**Wersja dokumentu:** 3.8
**Data ostatniej aktualizacji:** 2026-08-22
**Status:** Rozwoj — v0.7.0 (Unreleased), etap 1 zmergowany do `develop` 2026-08-12
