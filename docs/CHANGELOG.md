# Changelog

Wszystkie istotne zmiany w projekcie sa dokumentowane w tym pliku.

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [0.4.1] - 2026-02-08

### Fixed
- **BDOT10k: rtree spatial indices preserved during GPKG merge**
  - After merging multiple GPKG files, only the base (first) file kept its rtree index
  - New `_copy_rtree_index()` method copies rtree virtual table, data, and `gpkg_extensions` entry
  - All merged layers now retain spatial indices for fast spatial queries

### Added
- **Geometry file selection (`--geometry FILE`)**
  - Support for SHP (via pyshp) and GPKG (via sqlite3 + envelope parsing) input files
  - Per-feature bbox extraction for precise tile selection (not entire file bbox)
  - `find_sheets_for_geometry()` — public API for geometry → godla lookup
  - `get_overall_bbox()` — union bbox for landcover/soilgrids
  - CRS auto-detection from .prj (SHP) and gpkg_spatial_ref_sys (GPKG)
  - New dependency: `pyshp>=2.3.0`
- **CLI: `--geometry` and `--layer` for all download commands**
  - `kartograf download --geometry area.shp` — NMT tiles intersecting features
  - `kartograf download --geometry area.gpkg --layer catchments` — GPKG layer selection
  - `kartograf landcover download --source bdot10k --geometry area.shp`
  - `kartograf soilgrids hsg --geometry area.shp`
- **BDOT10k: hydrographic data download (`--category hydro`)**
  - New `HYDRO_LAYERS` constant: SWRS (rivers/streams), SWKN (canals), SWRM (drainage ditches), PTWP (surface waters)
  - `CATEGORY_FILTERS` mapping for category-based layer extraction from ZIP
  - `category` parameter threaded through `download_by_teryt()`, `download_by_godlo()`, `download_by_bbox()`
  - `get_available_layers(category="hydro")` returns hydrographic layers
  - Hydro layer descriptions in `get_layer_description()`
- **CLI: `--category` option for `landcover download`**
  - `kartograf landcover download --source bdot10k --teryt 2262 --category hydro`
  - Choices: `pt` (land cover, default), `hydro` (water network)
- **CLI: `landcover list-layers` shows both PT and hydro categories**

### Tests
- **636 testow** (+62 nowych)
  - 31 testow `test_geometry.py`: envelope parsing, SHP/GPKG reading, CRS transform, find_sheets_for_geometry, get_overall_bbox
  - 12 testow CLI geometry: download/landcover/soilgrids --geometry, mutual exclusivity
  - 5 testow `TestBdot10kRtreeIndex`: merge preserves indices, no geometry, no index, extensions copied, base preserved
  - 11 testow `TestBdot10kCategory`: extraction filters, category flow, layers, descriptions
  - 3 testy `TestCmdLandcoverCategory`: CLI --category hydro/default, list-layers shows hydro

---

## [0.4.0] - 2026-02-07

### Added
- **NMPT (Numeryczny Model Pokrycia Terenu / Digital Surface Model)**
  - `GugikNmptProvider` — dziedziczy z GugikProvider, nadpisuje endpointy NMPT
  - Tylko rozdzielczość 1m, vertical CRS: KRON86 lub EVRF2007
  - Download: godło → OpenData ASC, bbox → WCS GeoTIFF
- **Ortofotomapa (Standard Resolution, 25cm)**
  - `GugikOrtoProvider` — osobna klasa, format TIF
  - Brak vertical CRS (2D RGB), 9 warstw WMS (2018-2025+starsze)
  - Download: godło → OpenData TIF, bbox → WCS GeoTIFF
- **CLI `--product {nmt,nmpt,orto}` — wybór produktu w komendzie download**
  - `kartograf download N-34-130-D-d-2-4 --product nmpt` — pobiera NMPT
  - `kartograf download --bbox ... --product orto` — pobiera ortofoto
  - Domyślnie: nmt (bez zmian)
- **`find_sheets_for_bbox()` — reverse lookup: bbox → godła arkuszy**
  - Algorytm hierarchicznego przycinania (matematyczny, bez WFS)
  - Obsługa EPSG:2180 i EPSG:4326
  - Dowolna skala docelowa (1:1M do 1:10k)
  - Zoptymalizowane wyszukiwanie 1:200k (siatka 12x12)
- **CLI `kartograf download --bbox` — pobieranie NMT dla bbox**
  - `--bbox min_x,min_y,max_x,max_y` — współrzędne bbox
  - `--bbox-crs {EPSG:2180,EPSG:4326}` — CRS bbox (domyślnie EPSG:2180)
  - `godlo` staje się opcjonalny (godlo XOR --bbox)
  - Automatyczne wykrywanie arkuszy i pobieranie w pętli
- **Automatyczne rozwijanie godeł do 1:10000 w `download_sheet()`**
  - `download_sheet("N-34-130-D-d-2")` (1:25000) → automatycznie pobiera 4 arkusze 1:10000
  - `download_sheet("N-34-130-D-d")` (1:50000) → pobiera 16 arkuszy 1:10000
  - Dla godeł 1:10000 zachowanie bez zmian (pojedynczy plik)
  - Nowy parametr `on_progress` — callback postępu przy rozwijaniu hierarchii
  - Zwracany typ: `Path` (1:10000) lub `list[Path]` (coarser scales)
  - CLI dostosowane — wyświetla liczbę pobranych plików przy rozwijaniu

### Tests
- **574 testow, pokrycie 83.95% (cel 80% osiagniety)**
  - Nowy `tests/test_gugik_nmpt.py` — 21 testow dla GugikNmptProvider
  - Nowy `tests/test_gugik_orto.py` — 25 testow dla GugikOrtoProvider
  - Nowy `tests/test_auth_client.py` — 30 testow dla AuthProxyClient
  - Nowy `tests/test_auth_proxy.py` — 24 testy dla CLMSCredentials, ProxyHandler
  - Rozszerzony `tests/test_cli.py` — +12 testow (product CLI), +11 testow (landcover/soilgrids CLI)
  - Rozszerzony `tests/test_storage.py` — +8 testow (product storage)
  - Rozszerzony `tests/test_download_manager.py` — +3 testy (default_ext)
  - Rozszerzony `tests/test_landcover.py` — +38 testow
  - Rozszerzony `tests/test_hsg.py` — +6 testow

### Fixed
- Poprawiony komunikat błędu przy braku pokrycia NMT 5m — zamiast technicznego "No ASC file found in any WMS layer" wyświetla czytelną informację o braku pokrycia danego obszaru w GUGiK

### Changed
- **FileStorage: podkatalogi `1m`/`5m` → `nmt_1m`/`nmt_5m`**
  - Nowy parametr `product` w FileStorage (np. product="nmpt", product="orto")
  - Struktura: `data/nmt_1m/...`, `data/nmt_5m/...`, `data/nmpt/...`, `data/orto/...`
- **DownloadManager: dynamiczne rozszerzenie pliku**
  - `_default_ext` pobierane z `provider.default_extension` zamiast hardcoded `.asc`
- **BaseProvider: nowa property `default_extension`** (domyślnie `.asc`)
- Migracja z black + flake8 na ruff (pyproject.toml)
- Usuniecie .flake8, dodanie .editorconfig
- Standaryzacja dokumentacji wg shared/standards
- Przepisanie CLAUDE.md (7 sekcji, ~148 linii)
- Przepisanie PROGRESS.md (4 sekcje, skondensowane z 785 linii)
- Rozbudowanie DEVELOPMENT_STANDARDS.md (722 linii, 15 sekcji wg shared/standards)
- Rozbudowanie IMPLEMENTATION_PROMPT.md (284 linii, 11 sekcji, aktualny kontekst v0.3.2)
- Aktualizacja README.md, PRD.md, SCOPE.md
- Auto-naprawa kodu przez `ruff check --fix` (63 poprawki: importy, type annotations)

### Added
- Konfiguracja ruff (linter + formatter) w pyproject.toml
- Plik .editorconfig
- Sekcja [project.optional-dependencies] dev w pyproject.toml
- docs/DECISIONS.md — rejestr 9 decyzji architektonicznych (ADR)

### Removed
- Plik .flake8 (konfiguracja pokryta przez ruff)
- Sekcja [tool.black] z pyproject.toml

---

## [0.3.2] - 2026-01-21

### Changed - Storage Structure and Default Vertical CRS

- **Domyślny układ wysokościowy zmieniony na EVRF2007**
  - `GugikProvider`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - `DownloadManager`: domyślny `vertical_crs` zmieniony z `"KRON86"` na `"EVRF2007"`
  - CLI: `--vertical-crs` domyślnie `EVRF2007`
  - Kronsztadt 86 (KRON86) jest przestarzały i dostępny jako opcja legacy

- **Nowa struktura katalogów z rozdzielczością**
  - `FileStorage`: nowy parametr `resolution` (domyślnie `"1m"`)
  - Pliki NMT są teraz rozdzielone według rozdzielczości:
    ```
    data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 1m
    data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc   # dla 5m
    ```
  - `DownloadManager` automatycznie przekazuje `resolution` do `FileStorage`
  - Domyślne rozszerzenie pliku zmienione z `.tif` na `.asc`

### Breaking Changes

- **Struktura katalogów** - pliki NMT są teraz zapisywane w podkatalogu `1m/` lub `5m/`
  - Stara ścieżka: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`
  - Nowa ścieżka: `data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc`

- **Domyślny vertical_crs** - zmieniony z `KRON86` na `EVRF2007`
  - Aby używać starego układu: `--vertical-crs KRON86`

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (EVRF2007 domyślnie)
kartograf download N-34-130-D-d-2-4
# → data/1m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m
# → data/5m/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc

# Użyj starego układu Kronsztadt (legacy)
kartograf download N-34-130-D-d-2-4 --vertical-crs KRON86
```

---

## [0.3.1] - 2026-01-21

### Added - NMT Resolution Selection

- **Wybór rozdzielczości NMT** - Obsługa danych NMT w dwóch rozdzielczościach
  - `1m` (GRID1) - wysoka rozdzielczość, domyślna
  - `5m` (GRID5) - niższa rozdzielczość, tylko dla EVRF2007

- **GugikProvider** - Nowy parametr `resolution`
  - `GugikProvider(resolution="5m", vertical_crs="EVRF2007")`
  - Nowe endpointy WMS dla 5m: `SheetsGrid5mEVRF2007`
  - Automatyczna walidacja: 5m wymaga EVRF2007
  - Nowe metody: `get_supported_resolutions()`, `is_wcs_available()`
  - `download_bbox()` rzuca ValueError dla 5m (WCS niedostępne)

- **DownloadManager** - Nowy parametr `resolution`
  - `DownloadManager(resolution="5m")` - automatycznie wymusza EVRF2007

- **CLI** - Nowa opcja `--resolution`
  - `kartograf download N-34-130-D --resolution 5m`
  - Skrót: `-r 5m`

**Ograniczenia 5m:**
- Dostępne tylko w układzie EVRF2007
- Brak obsługi WCS (download_bbox) - tylko arkusze OpenData

**Przykłady użycia:**
```bash
# Pobierz NMT 1m (domyślnie)
kartograf download N-34-130-D-d-2-4

# Pobierz NMT 5m
kartograf download N-34-130-D-d-2-4 --resolution 5m

# Pobierz hierarchię w 5m
kartograf download N-34-130-D --scale 1:10000 -r 5m
```

### Changed

- **Testy** - 365 testów (18 nowych dla resolution)

### Fixed - Cross-Project Compatibility (2026-01-21)

- **Public API exports** - Uzupełniono brakujące eksporty w głównym module
  - Dodano `SoilGridsProvider` do `kartograf/__init__.py`
  - Dodano `HSGCalculator` do `kartograf/__init__.py`
  - Teraz możliwy import: `from kartograf import SoilGridsProvider, HSGCalculator`

### Fixed - QA Review (2026-01-21)

- **Synchronizacja wersji** - Ujednolicono wersję we wszystkich plikach
  - `pyproject.toml`: 0.3.0 → 0.3.1
  - `kartograf/__init__.py`: 0.3.0-dev → 0.3.1
  - `README.md`: zaktualizowano status i liczbę testów

- **Synchronizacja zależności** - Uzupełniono brakujące zależności
  - `pyproject.toml`: dodano `rasterio>=1.3.0`, `numpy>=1.24.0`
  - `requirements.txt`: dodano `PyJWT[crypto]>=2.8.0`

- **Testy** - Naprawiono test wersji w `test_integration.py`

- **Dokumentacja** - Dodano sekcję QA Review do `PROGRESS.md`

---

## [0.3.0] - 2026-01-18

### Added - SoilGrids i Hydrologic Soil Groups (HSG)

- **SoilGridsProvider** - Provider dla ISRIC SoilGrids (dane glebowe)
  - Globalne dane glebowe w rozdzielczości 250m
  - WCS Endpoint: `https://maps.isric.org/mapserv`
  - **11 parametrów glebowych:**
    - `bdod` - Gęstość objętościowa (kg/dm³)
    - `cec` - Pojemność wymiany kationowej (cmol/kg)
    - `cfvo` - Fragmenty gruboziarniste (%)
    - `clay` - Zawartość gliny (%)
    - `nitrogen` - Azot całkowity (g/kg)
    - `ocd` - Gęstość węgla organicznego (kg/m³)
    - `ocs` - Zasób węgla organicznego (t/ha)
    - `phh2o` - pH w H2O
    - `sand` - Zawartość piasku (%)
    - `silt` - Zawartość pyłu (%)
    - `soc` - Węgiel organiczny (g/kg)
  - **6 głębokości:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
  - **5 statystyk:** mean, Q0.05, Q0.5, Q0.95, uncertainty
  - Transformacja CRS: EPSG:2180 → WGS84

- **HSGCalculator** - Kalkulacja Hydrologic Soil Groups dla metody SCS-CN
  - `kartograf/hydrology/hsg.py` - moduł hydrologiczny
  - Klasyfikacja tekstury gleby wg trójkąta USDA (12 klas)
  - Mapowanie tekstury do HSG (A, B, C, D)
  - **Grupy hydrologiczne:**
    - A - wysoka infiltracja (piasek, piasek gliniasty)
    - B - umiarkowana infiltracja (glina piaszczysta, glina)
    - C - wolna infiltracja (glina ilasta)
    - D - bardzo wolna infiltracja (ił)
  - Automatyczne pobieranie clay/sand/silt z SoilGrids
  - Statystyki pokrycia dla każdej grupy HSG

- **CLI soilgrids** - Nowe komendy CLI
  - `kartograf landcover download --source soilgrids --property <param> --depth <głębokość>`
  - `kartograf landcover list-layers --source soilgrids`
  - `kartograf soilgrids hsg --godlo <godło>` - kalkulacja HSG
  - Opcje HSG: `--depth`, `--output`, `--keep-intermediate`, `--stats`

**Przykłady użycia:**
```bash
# Pobierz węgiel organiczny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc

# Pobierz zawartość gliny
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Oblicz HSG dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats
```

### Added - Land Cover (Pokrycie Terenu)

- **LandCoverProvider** - Nowa abstrakcja dla providerów danych pokrycia terenu
  - Metody: `download_by_teryt()`, `download_by_bbox()`, `download_by_godlo()`
  - Wspólny interfejs dla różnych źródeł danych

- **Bdot10kProvider** - Provider dla BDOT10k (GUGiK)
  - Pobieranie paczek powiatowych przez TERYT
  - Pobieranie przez WMS GetFeatureInfo dla URL paczki
  - Pobieranie przez godło arkusza (konwersja na bbox)
  - **12 warstw pokrycia terenu (PT*):**
    - PTGN - Grunty nieużytkowe
    - PTKM - Tereny komunikacyjne
    - PTLZ - Tereny leśne
    - PTNZ - Tereny niezabudowane
    - PTPL - Place
    - PTRK - Roślinność krzewiasta
    - PTSO - Składowiska
    - PTTR - Tereny rolne
    - PTUT - Uprawy trwałe
    - PTWP - Wody powierzchniowe
    - PTWZ - Tereny zabagnione
    - PTZB - Tereny zabudowane
  - Automatyczne scalanie warstw PT* z ZIP do jednego GeoPackage
  - Format wyjściowy: GeoPackage (.gpkg), SHP

- **CorineProvider** - Provider dla CORINE Land Cover (Copernicus)
  - Europejska klasyfikacja pokrycia terenu (44 klasy)
  - Dostępne lata: 1990, 2000, 2006, 2012, 2018
  - **Trzy źródła danych (w kolejności priorytetu):**
    1. **CLMS API** - GeoTIFF z kodami klas (wymaga OAuth2)
    2. **EEA Discomap WMS** - Podgląd PNG (lata 2000-2018)
    3. **DLR WMS** - Fallback dla 1990
  - OAuth2 RSA authentication dla CLMS API
  - Przechowywanie credentials w macOS Keychain (serwis: `clms-token`)

- **LandCoverManager** - Zarządzanie pobieraniem danych pokrycia terenu
  - Dispatch do odpowiedniego providera
  - Obsługa wielu metod selekcji obszaru

- **CLI landcover** - Nowe komendy CLI
  - `kartograf landcover download --source bdot10k --teryt <kod>`
  - `kartograf landcover download --source corine --year <rok> --godlo <godło>`
  - `kartograf landcover list-sources`
  - `kartograf landcover list-layers --source bdot10k`

### CLMS API Authentication - Auth Proxy

CorineProvider używa **Auth Proxy** dla bezpiecznej autentykacji CLMS API:

**Architektura bezpieczeństwa:**
```
CorineProvider → localhost HTTP → AuthProxy (subprocess) → Keychain → CLMS API
```

- Credentials (klucz prywatny RSA) są izolowane w osobnym procesie
- Główna aplikacja nigdy nie widzi credentials
- Tylko odpowiedzi API są przekazywane do aplikacji

**Nowe moduły:**
- `kartograf/auth/proxy.py` - serwer HTTP izolujący credentials
- `kartograf/auth/client.py` - klient automatycznie uruchamiający proxy

**Konfiguracja:**
1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (JSON)
3. Zapisz do Keychain:
   ```bash
   security add-generic-password -a "$USER" -s "clms-token" -w '<json_credentials>'
   ```

**Tryby pracy:**
```python
# Domyślny (bezpieczny) - używa proxy
provider = CorineProvider()

# Bezpośredni (dla testów) - credentials widoczne
provider = CorineProvider(clms_credentials={...}, use_proxy=False)
```

**Uwaga:** Jeśli credentials nie są skonfigurowane, CorineProvider automatycznie używa WMS (podgląd PNG zamiast GeoTIFF z kodami klas).

### Dependencies

- Dodano `PyJWT[crypto]>=2.8.0` - JWT generation dla OAuth2
- Dodano `rasterio>=1.3.0` - przetwarzanie rastrów GeoTIFF
- Dodano `numpy>=1.24.0` - operacje na tablicach

### Technical Details

- 347 testów (42 dla landcover, 28 dla soilgrids, 34 dla HSG)
- Formatowanie: black, flake8

### Sources

- BDOT10k: https://www.geoportal.gov.pl/en/data/topographic-objects-database-bdot10k/
- CORINE Land Cover: https://land.copernicus.eu/en/products/corine-land-cover
- EEA Discomap: https://image.discomap.eea.europa.eu
- DLR EOC: https://geoservice.dlr.de/eoc/land/wms
- ISRIC SoilGrids: https://soilgrids.org/
- SoilGrids Documentation: https://docs.isric.org/globaldata/soilgrids/

---

## [0.2.0] - 2026-01-18

### Changed - Nowa architektura pobierania

**Uproszczona logika pobierania:**
- **Godło → OpenData (ASC)** - pobieranie arkusza przez godło zawsze daje plik ASC
- **BBox → WCS (GeoTIFF)** - pobieranie przez bounding box daje GeoTIFF/PNG/JPEG

**Zmiany API:**
- `download_sheet(godlo)` - zawsze pobiera ASC (usunięto parametr `format`)
- `download_hierarchy(godlo, target_scale)` - pobiera wszystkie arkusze jako ASC
- `download_bbox(bbox, filename, format)` - **nowa metoda** dla pobierania przez bbox
- Usunięto `construct_url()` z publicznego API
- `DownloadManager` nie przyjmuje już parametru `format` w konstruktorze

### Added

- **Pobieranie ASC przez OpenData** - Automatyczne wyszukiwanie URL przez WMS GetFeatureInfo
  - Zapytania do warstw: `SkorowidzeNMT2019`, `SkorowidzeNMT2018`, `SkorowidzeNMT2017iStarsze`
  - Pobieranie z `opendata.geoportal.gov.pl`

- **SheetParser.get_bbox()** - Obliczanie bounding box arkusza
  - Obsługiwane CRS: `EPSG:2180` (PL-1992), `EPSG:4326` (WGS84)
  - Transformacja współrzędnych przez `pyproj`

- **BBox** - Nowy typ danych w public API

- **GugikProvider.download_bbox()** - Pobieranie przez bounding box z WCS

### Dependencies

- Dodano `pyproj>=3.6.0` do wymagań

### Technical Details

- 245 testów

## [0.1.0] - 2026-01-17

### Added

- **SheetParser** - Parser for Polish topographic map sheet identifiers (godlo)
  - Support for scales 1:1,000,000 to 1:10,000
  - Support for "1992" coordinate system layout
  - Hierarchy navigation: `get_parent()`, `get_children()`, `get_hierarchy_up()`
  - Descendant enumeration: `get_all_descendants(target_scale)`
  - Special handling for 1:500k to 1:200k division (36 sheets per section)

- **DownloadManager** - Coordinated download of NMT data
  - Single sheet download: `download_sheet(godlo)`
  - Hierarchy download: `download_hierarchy(godlo, target_scale)`
  - Progress callbacks with `DownloadProgress` dataclass
  - Skip existing files option for resumable downloads
  - Missing sheets detection: `get_missing_sheets()`

- **GugikProvider** - Integration with GUGiK WCS service
  - GeoTIFF and Arc/Info ASCII Grid format support
  - Retry logic with exponential backoff (3 attempts)
  - 30-second timeout per request

- **FileStorage** - Hierarchical file storage management
  - Automatic directory structure based on godlo components
  - Atomic writes (temp file + rename)
  - Path generation: `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif`

- **CLI** - Command-line interface
  - `kartograf parse <godlo>` - Display sheet information
  - `kartograf parse <godlo> --hierarchy` - Show hierarchy to 1:1M
  - `kartograf parse <godlo> --children` - Show direct children
  - `kartograf download <godlo>` - Download single sheet
  - `kartograf download <godlo> --scale <scale>` - Download hierarchy
  - Options: `--format`, `--output`, `--force`, `--quiet`

- **Public API** - Clean imports from main module
  - `from kartograf import SheetParser, DownloadManager`
  - All exceptions: `KartografError`, `ParseError`, `ValidationError`, `DownloadError`
  - Providers: `BaseProvider`, `GugikProvider`

- **Test Coverage** - 97% coverage with 235 tests
  - Unit tests for all modules
  - Integration tests for complete workflows

### Technical Details

- Python 3.12+ required
- Single dependency: `requests>=2.31.0`
- Project structure follows src layout
- Configured with black, flake8, pytest

[Unreleased]: https://github.com/Daldek/Kartograf/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/Daldek/Kartograf/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/Daldek/Kartograf/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.2
[0.3.1]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.1
[0.3.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.0
[0.2.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.2.0
[0.1.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.1.0
