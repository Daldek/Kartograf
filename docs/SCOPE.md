# SCOPE.md - Zakres Projektu Kartograf
**Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 3.3
**Data:** 2026-03-02
**Status:** Production (v0.4.1)

---

## 1. Cel Projektu

**Kartograf** to narzędzie do pobierania danych przestrzennych z zasobów GUGiK, Copernicus i ISRIC dla Polski.

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

## 2. Zakres - Wersja 0.4.x

### 2.1 NMT (Numeryczny Model Terenu) - IN SCOPE

```python
# Funkcjonalności:
- Parser godeł w układach 1992 i 2000
- Obsługa skal: 1:1 000 000 do 1:10 000
- Hierarchia arkuszy (get_parent, get_children, get_all_descendants)
- Bounding box arkusza (EPSG:2180, EPSG:4326)
- Reverse lookup: bbox → godła (find_sheets_for_bbox)
- Reverse lookup: geometry file → godła (find_sheets_for_geometry)
- Selekcja obszaru: godło, bbox, plik geometrii (SHP/GPKG)
- Pobieranie przez godło → ASC (OpenData)
- Pobieranie przez bbox → GeoTIFF (WCS) lub automatyczne wykrywanie arkuszy
- Rozdzielczości: 1m (GRID1), 5m (GRID5)
- Układy wysokościowe: KRON86, EVRF2007

# Źródło: GUGiK (Główny Urząd Geodezji i Kartografii)
# API: WCS, WMS GetFeatureInfo, OpenData
```

### 2.2 NMPT (Numeryczny Model Pokrycia Terenu) - IN SCOPE

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

### 2.3 Ortofotomapa - IN SCOPE

```python
# Funkcjonalności:
- Zdjęcia lotnicze Standard Resolution (25cm)
- Pobieranie przez godło → TIF (OpenData)
- Pobieranie przez bbox → GeoTIFF (WCS)
- Brak vertical CRS (2D RGB)
- 9 warstw WMS (2018-2025+starsze)
- Obsługa formatów WCS: GTiff, PNG, JPEG

# Źródło: GUGiK
# API: WCS, WMS GetFeatureInfo, OpenData
```

### 2.4 Land Cover (Pokrycie Terenu) - IN SCOPE

```python
# BDOT10k (GUGiK):
- 15 warstw (12 pokrycia terenu PT* + 3 hydrograficzne SW*)
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

### 2.5 SoilGrids (Dane Glebowe) - IN SCOPE

```python
# ISRIC SoilGrids:
- 11 parametrów glebowych (clay, sand, silt, soc, pH, etc.)
- 6 głębokości (0-5cm do 100-200cm)
- 5 statystyk (mean, Q0.05, Q0.5, Q0.95, uncertainty)
- Rozdzielczość: 250m (globalne)
- Pobieranie przez godło, bbox lub TERYT
- Format: GeoTIFF

# Źródło: ISRIC (International Soil Reference and Information Centre)
# API: WCS
```

### 2.6 HSG (Hydrologic Soil Groups) - IN SCOPE

```python
# Kalkulacja HSG dla metody SCS-CN:
- Klasyfikacja tekstury wg trójkąta USDA (12 klas)
- Mapowanie tekstury → HSG (A, B, C, D)
- Automatyczne pobieranie clay/sand/silt z SoilGrids
- Statystyki pokrycia dla każdej grupy
- Format wyjściowy: GeoTIFF (wartości 1-4)

# Moduł: kartograf.hydrology.hsg
```

### 2.7 CLI Interface - IN SCOPE

```bash
# Komendy:
kartograf parse <godlo>                    # info o godle
kartograf download <godlo>                 # pobierz NMT
kartograf download <godlo> --product nmpt  # pobierz NMPT
kartograf download <godlo> --product orto  # pobierz ortofoto
kartograf download --bbox min_x,min_y,max_x,max_y  # NMT dla bbox
kartograf download --bbox ... --product orto  # ortofoto dla bbox
kartograf download --geometry area.shp         # NMT z pliku geometrii
kartograf download --geometry area.gpkg --layer catchments
kartograf download <godlo> --resolution 5m # NMT 5m
kartograf landcover download --source bdot10k --teryt <kod>
kartograf landcover download --source corine --godlo <godlo>
kartograf landcover download --source soilgrids --property <param>
kartograf landcover list-sources
kartograf landcover list-layers --source <source>
kartograf soilgrids hsg --godlo <godlo>    # oblicz HSG
```

### 2.8 Python API - IN SCOPE

```python
# Public API (kartograf/__init__.py):
from kartograf import (
    # Core
    SheetParser, BBox, find_sheets_for_bbox, find_sheets_for_geometry,
    # Download (NMT/NMPT/Orto)
    DownloadManager, DownloadProgress, FileStorage,
    # Land Cover
    LandCoverManager,
    # Providers
    BaseProvider, GugikProvider, GugikNmptProvider, GugikOrtoProvider,
    LandCoverProvider, Bdot10kProvider, CorineProvider, SoilGridsProvider,
    # Hydrology
    HSGCalculator,
    # Exceptions
    KartografError, ParseError, ValidationError, DownloadError,
)
```

---

## 3. Out of Scope - Wersja 0.4.x

### 3.1 Funkcjonalności Zaplanowane - FUTURE

```python
# Wersja 0.5+:
- Pobieranie równoległe (multi-threading)
- Cache dla metadanych
- Automatyczne mozaikowanie (merge arkuszy)

# Wersja 1.0+:
- GUI interface
- Pobieranie danych LIDAR
- Integracja z PostGIS
- REST API server
```

### 3.2 Ograniczenia Techniczne

```
- Brak weryfikacji integralności plików (checksums)
- Timeout: 30s dla GUGiK, 60s dla Land Cover
- Max 3 próby retry (nie konfigurowalne)
- Synchroniczne pobieranie (bez async)
- NMT 5m wymaga EVRF2007
- SoilGrids: tylko WGS84 bbox (transformacja automatyczna)
```

---

## 4. Architektura

### 4.1 Moduły

```
kartograf/
├── core/                  # Parser godeł, BBox, geometria
│   ├── sheet_parser.py
│   └── geometry.py        # SHP/GPKG reading, find_sheets_for_geometry
├── providers/             # Providery danych
│   ├── base.py            # BaseProvider (NMT)
│   ├── gugik.py           # GugikProvider (NMT)
│   ├── gugik_nmpt.py      # GugikNmptProvider (NMPT/DSM)
│   ├── gugik_orto.py      # GugikOrtoProvider (Ortofotomapa)
│   ├── landcover_base.py  # LandCoverProvider (abstrakcja)
│   ├── bdot10k.py         # Bdot10kProvider
│   ├── corine.py          # CorineProvider
│   └── soilgrids.py       # SoilGridsProvider
├── download/              # Download management (NMT/NMPT/Orto)
│   ├── manager.py
│   └── storage.py
├── landcover/             # Land Cover management
│   └── manager.py
├── hydrology/             # Obliczenia hydrologiczne
│   └── hsg.py             # HSGCalculator
├── auth/                  # Autentykacja (CLMS)
│   ├── proxy.py           # Auth Proxy server
│   └── client.py          # Auth Proxy client
└── cli/                   # CLI interface
    └── commands.py
```

### 4.2 Zależności

```
Python 3.12+
requests >= 2.31.0     # HTTP client
pyproj >= 3.6.0        # CRS transformations
PyJWT[crypto] >= 2.8.0 # OAuth2 JWT (CLMS)
rasterio >= 1.3.0      # GeoTIFF processing (HSG)
numpy >= 1.24.0        # Array operations (HSG)
pyshp >= 2.3.0         # Shapefile reading
```

---

## 5. Źródła Danych

| Źródło | Typ danych | API | Autentykacja |
|--------|-----------|-----|--------------|
| GUGiK | NMT, NMPT, Ortofoto, BDOT10k | WCS, WMS, OpenData | Brak |
| Copernicus CLMS | CORINE | REST API | OAuth2 RSA |
| EEA Discomap | CORINE (podgląd) | WMS | Brak |
| ISRIC SoilGrids | Gleba | WCS | Brak |

---

## 6. Success Criteria

### 6.1 Funkcjonalne

```
- Parser poprawnie parsuje godła 1:1M - 1:10k
- NMT pobiera się w rozdzielczościach 1m i 5m
- BDOT10k pobiera się przez TERYT i godło
- CORINE pobiera się przez godło (GeoTIFF lub PNG fallback)
- SoilGrids pobiera dane glebowe
- HSG oblicza grupy hydrologiczne z danych SoilGrids
- Integracja z Hydrograf/Hydrolog działa
```

### 6.2 Jakościowe

```
- 835 testów przechodzi
- Pokrycie testami ~84% (cel 80% osiągnięty)
- Kod zgodny z ruff
- Type hints wszędzie
- Dokumentacja aktualna
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

---

**Wersja dokumentu:** 3.3
**Data ostatniej aktualizacji:** 2026-03-02
**Status:** Production - v0.4.1
