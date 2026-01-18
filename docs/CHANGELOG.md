# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-01-18

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

### Technical Details

- 285 testów (42 dla landcover)
- Formatowanie: black, flake8

### Sources

- BDOT10k: https://www.geoportal.gov.pl/en/data/topographic-objects-database-bdot10k/
- CORINE Land Cover: https://land.copernicus.eu/en/products/corine-land-cover
- EEA Discomap: https://image.discomap.eea.europa.eu
- DLR EOC: https://geoservice.dlr.de/eoc/land/wms

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

[0.3.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.3.0
[0.2.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.2.0
[0.1.0]: https://github.com/Daldek/Kartograf/releases/tag/v0.1.0
