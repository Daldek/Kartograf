# PRD.md - Product Requirements Document
**Kartograf - Narzędzie do Pobierania Danych NMT**

**Wersja:** 1.0  
**Data:** 2026-01-15  
**Product Owner:** Piotr  
**Tech Lead:** Piotr

---

## 1. Executive Summary

### 1.1 Problem Statement

Pobieranie danych Numerycznego Modelu Terenu (NMT) z zasobów GUGiK jest:
- **Czasochłonne** - ręczne nawigowanie przez interfejs webowy
- **Podatne na błędy** - łatwo pobłądzić w systemie godeł map
- **Nieefektywne** - pobieranie arkuszy jeden po drugim
- **Dezorganizowane** - brak automatycznej organizacji plików

### 1.2 Solution

Kartograf to narzędzie CLI + biblioteka Python które automatyzuje proces pobierania danych NMT poprzez:
1. Inteligentne parsowanie godeł map topograficznych
2. Automatyczne określanie hierarchii arkuszy
3. Masowe pobieranie z retry logic
4. Automatyczną organizację plików w logicznej strukturze

### 1.3 Target Users

| Persona | Potrzeby | Użycie |
|---------|----------|--------|
| **Deweloper GIS** (główny użytkownik) | Dane NMT dla HydroLOG, automatyzacja | Python API + CLI |
| **Specjalista Planowania Przestrzennego** | Dane topograficzne dla analiz | CLI |
| **Inni Deweloperzy** | Integracja z własnymi narzędziami | Python API |

---

## 2. Goals & Metrics

### 2.1 Business Goals

1. **Efektywność** - Zmniejszenie czasu pobierania danych NMT
2. **Reusability** - Narzędzie używane w innych projektach (np. HydroLOG)

### 2.2 Technical Goals

1. **Reliability** - Success rate ≥ 95% dla pobierania arkuszy
2. **Performance** - Parsowanie < 0.1s, pobieranie arkusza < 30s
3. **Quality** - Test coverage ≥ 80% dla core logic
4. **Maintainability** - Kod zgodny z PEP 8, Black, type hints

### 2.3 Success Metrics

| Metryka | Target MVP | Measurement |
|---------|------------|-------------|
| Parse time | < 0.1s | Unit tests |
| Download success rate | ≥ 95% | Integration tests |
| Test coverage (core) | ≥ 80% | pytest --cov |
| CLI usability | "Easy" w user testing | Feedback |
| Integration w HydroLOG | Working | Demo |

---

## 3. Core Features

### 3.1 Feature: Parser Godła

**Priority:** P0 (Critical)  
**Status:** MVP

#### Description
Parser godeł map topograficznych obsługujący układy 1992 i 2000, skale od 1:1 000 000 do 1:10 000.

#### User Stories

```
US-1.1: Parsowanie Godła
Jako użytkownik
Chcę podać godło mapy (np. "N-34-130-D-d-2-4")
Aby otrzymać informacje o skali, układzie i komponentach

Acceptance Criteria:
✓ Parser akceptuje godła w układach 1992 i 2000
✓ Parser waliduje format godła
✓ Parser zwraca skalę, układ, komponenty
✓ Nieprawidłowe godło rzuca ValueError z wyraźnym komunikatem
```

```
US-1.2: Walidacja Układu
Jako użytkownik
Chcę aby parser walidował układ współrzędnych
Aby uniknąć błędów w dalszych operacjach

Acceptance Criteria:
✓ Parser akceptuje tylko "1992" lub "2000"
✓ Parser automatycznie wybiera "1992" jeśli układ nie podany
✓ Nieprawidłowy układ rzuca ValueError
```

#### API Example
```python
parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")
print(parser.godlo)       # "N-34-130-D-D-2-4"
print(parser.scale)       # "1:10000"
print(parser.uklad)       # "1992"
print(parser.components)  # {'pas': 'N', 'slup': '34', ...}
```

#### Technical Notes
- Regex patterns dla każdej skali
- Case-insensitive parsing (konwersja do uppercase)
- Immutable po inicjalizacji

---

### 3.2 Feature: Hierarchia Arkuszy

**Priority:** P0 (Critical)  
**Status:** MVP

#### Description
Generowanie hierarchii arkuszy - ścieżka w górę (do 1:1M) i w dół (do zadanej skali).

#### User Stories

```
US-2.1: Ścieżka w Górę
Jako użytkownik
Chcę otrzymać wszystkie arkusze nadrzędne
Aby zrozumieć pełną hierarchię arkusza

Acceptance Criteria:
✓ get_hierarchy_up() zwraca listę od bieżącego do 1:1M
✓ Lista zawiera SheetParser dla każdego poziomu
✓ Kolejność: od najmniejszej do największej skali
```

```
US-2.2: Ścieżka w Dół
Jako użytkownik
Chcę otrzymać wszystkie arkusze podrzędne do zadanej skali
Aby pobrać kompletny zestaw danych

Acceptance Criteria:
✓ get_all_descendants(scale) zwraca wszystkie potomne arkusze
✓ Rekursywne przeszukiwanie do target_scale
✓ Walidacja: target_scale musi być > bieżąca skala
```

#### API Example
```python
parser = SheetParser("N-34-130-D")

# Hierarchia w górę
hierarchy = parser.get_hierarchy_up()
# → [SheetParser("N-34-130-D"), SheetParser("N-34-130"), ...]

# Wszystkie potomki do 1:10k
descendants = parser.get_all_descendants("1:10000")
# → [SheetParser("N-34-130-D-a-1-1"), SheetParser("N-34-130-D-a-1-2"), ...]
print(len(descendants))  # 256 (4^4)
```

#### Technical Notes
- Mapowanie podziałów: 1:500k → 4, 1:200k → 36, inne → 4
- Lazy evaluation dla dużych hierarchii
- Recursive traversal z memoization

---

### 3.3 Feature: Download Manager

**Priority:** P0 (Critical)  
**Status:** MVP

#### Description
Zarządzanie pobieraniem plików NMT z GUGiK z obsługą retry, progress tracking i resumowania.

#### User Stories

```
US-3.1: Pobieranie Pojedynczego Arkusza
Jako użytkownik
Chcę pobrać plik NMT dla konkretnego godła
Aby otrzymać dane wysokościowe dla tego obszaru

Acceptance Criteria:
✓ download_sheet(godlo, format) pobiera plik z GUGiK
✓ Obsługa formatów: GTiff, AAIGrid, XYZ
✓ Retry logic: max 3 próby z exponential backoff
✓ Zwraca ścieżkę do pobranego pliku
✓ Rzuca DownloadError jeśli pobieranie się nie powiodło
```

```
US-3.2: Pobieranie Hierarchii
Jako użytkownik
Chcę pobrać wszystkie arkusze od danego godła do zadanej skali
Aby otrzymać kompletny zestaw danych

Acceptance Criteria:
✓ download_hierarchy(godlo, target_scale, format) pobiera wszystkie potomki
✓ Progress tracking (ile pobranych / total)
✓ Skip już pobranych plików (resumowanie)
✓ Kontynuacja po przerwaniu
✓ Zwraca listę ścieżek do pobranych plików
```

```
US-3.3: Organizacja Plików
Jako użytkownik
Chcę aby pobrane pliki były automatycznie zorganizowane
Aby łatwo je odnaleźć i używać

Acceptance Criteria:
✓ Struktura katalogów odzwierciedla hierarchię godła
✓ Nazwa pliku = pełne godło + rozszerzenie
✓ Różne formaty w tym samym katalogu
✓ Automatyczne tworzenie katalogów
```

#### API Example
```python
manager = DownloadManager(output_dir="./data")

# Pojedynczy arkusz
path = manager.download_sheet(
    godlo="N-34-130-D-d-2-4",
    format="GTiff"
)
# → "./data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif"

# Cała hierarchia
paths = manager.download_hierarchy(
    godlo="N-34-130-D",
    target_scale="1:10000",
    format="GTiff",
    on_progress=lambda current, total: print(f"{current}/{total}")
)
# → lista 256 ścieżek
```

#### Technical Notes
- requests.Session() dla connection reuse
- Chunked download dla dużych plików (>10MB)
- Atomic writes (download to .tmp, rename on success)
- Progress callback: `on_progress(current: int, total: int)`
- Logging wszystkich operacji

---

### 3.4 Feature: CLI Interface

**Priority:** P0 (Critical)  
**Status:** MVP

#### Description
Command-line interface dla podstawowych operacji bez konieczności pisania kodu Python.

#### User Stories

```
US-4.1: CLI Parse
Jako użytkownik
Chcę wyświetlić informacje o godle przez CLI
Aby szybko sprawdzić skalę i hierarchię

Acceptance Criteria:
✓ kartograf parse <godlo> wyświetla info
✓ Opcja --hierarchy pokazuje ścieżkę w górę
✓ Opcja --descendants <scale> pokazuje liczbę potomków
```

```
US-4.2: CLI Download
Jako użytkownik
Chcę pobrać dane przez CLI
Aby nie pisać kodu Python

Acceptance Criteria:
✓ kartograf download <godlo> pobiera jeden arkusz
✓ Opcja --scale <scale> pobiera hierarchię
✓ Opcja --format <format> wybiera format
✓ Opcja --output <dir> ustawia katalog docelowy
✓ Progress bar w konsoli
```

#### CLI Commands
```bash
# Parsowanie
kartograf parse N-34-130-D-d-2-4
# Output:
# Godło: N-34-130-D-D-2-4
# Skala: 1:10000
# Układ: 1992

kartograf parse N-34-130-D --hierarchy
# Output:
# Hierarchia:
#   N-34-130-D (1:100000)
#   N-34-130 (1:200000)
#   N-34 (1:1000000)

# Pobieranie
kartograf download N-34-130-D-d-2-4
# Output:
# Downloading N-34-130-D-d-2-4.tif...
# [████████████████████] 100% (12.3 MB)
# Saved to: ./data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif

kartograf download N-34-130-D --scale 1:10000 --format AAIGrid
# Output:
# Downloading 256 sheets...
# [████████████████████] 100% (256/256)
# Completed: 256 sheets, 3.2 GB
```

#### Technical Notes
- argparse dla parsing arguments
- Rich/tqdm dla progress bars (opcjonalne dependency)
- Fallback do simple print jeśli Rich niedostępne
- Exit codes: 0 (success), 1 (error), 2 (invalid args)

---

### 3.5 Feature: Python API (Biblioteka)

**Priority:** P0 (Critical)  
**Status:** MVP

#### Description
Clean Python API do użycia jako biblioteka w innych projektach (np. HydroLOG).

#### User Stories

```
US-5.1: Import jako Biblioteka
Jako deweloper
Chcę zaimportować Kartograf w moim projekcie
Aby wykorzystać jego funkcjonalność programatycznie

Acceptance Criteria:
✓ from kartograf import SheetParser, DownloadManager działa
✓ Wszystkie klasy mają type hints
✓ Wszystkie public funkcje mają docstrings
✓ Brak side effects przy imporcie
```

#### API Example
```python
# W projekcie HydroLOG
from kartograf import SheetParser, DownloadManager

def prepare_nmt_data(area_bbox):
    # Określ godła dla obszaru (uproszczenie)
    godlo = determine_sheets_for_bbox(area_bbox)
    
    # Pobierz dane
    parser = SheetParser(godlo)
    manager = DownloadManager(output_dir="./nmt_cache")
    
    paths = manager.download_hierarchy(
        parser,
        target_scale="1:10000",
        format="GTiff"
    )
    
    return paths
```

#### Technical Notes
- Entry points w setup.py/pyproject.toml
- Semantic versioning
- Backwards compatibility po 1.0
- Minimal external dependencies

---

## 4. Architecture Overview

### 4.1 Component Diagram

```
┌─────────────────────────────────────────────┐
│             User Interface                  │
├──────────────┬──────────────────────────────┤
│  CLI         │  Python API                  │
└──────┬───────┴─────────┬────────────────────┘
       │                 │
       v                 v
┌─────────────────────────────────────────────┐
│          Download Manager                   │
│  - download_sheet()                         │
│  - download_hierarchy()                     │
│  - progress tracking                        │
│  - retry logic                              │
└──────┬──────────────────┬───────────────────┘
       │                  │
       v                  v
┌──────────────┐   ┌─────────────────────────┐
│ SheetParser  │   │  GugikClient            │
│ - parse      │   │  - construct_url()      │
│ - hierarchy  │   │  - download()           │
│ - validate   │   │  - retry()              │
└──────────────┘   └──────┬──────────────────┘
                          │
                          v
                   ┌──────────────────┐
                   │  HTTP (requests) │
                   │  GUGiK WCS/WMS   │
                   └──────────────────┘
```

### 4.2 Data Flow

```
1. User → CLI/API → SheetParser
   Input: godlo string
   Output: SheetParser object

2. SheetParser → hierarchy generation
   Input: target_scale
   Output: List[SheetParser]

3. DownloadManager → GugikClient
   Input: List[godlo], format
   Output: Download tasks

4. GugikClient → HTTP Request → GUGiK
   Input: godlo, format
   Output: file bytes

5. Storage → Filesystem
   Input: file bytes, godlo
   Output: file path
```

### 4.3 Directory Structure

```
kartograf/
├── src/
│   └── kartograf/
│       ├── __init__.py           # Public API exports
│       ├── core/
│       │   ├── __init__.py
│       │   ├── sheet_parser.py   # SheetParser, SheetInfo
│       │   └── hierarchy.py      # Hierarchy operations
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py           # BaseProvider (abstract)
│       │   └── gugik.py          # GugikClient
│       ├── download/
│       │   ├── __init__.py
│       │   ├── manager.py        # DownloadManager
│       │   └── storage.py        # FileStorage
│       └── cli/
│           ├── __init__.py
│           └── commands.py       # CLI commands
├── tests/
│   ├── test_sheet_parser.py
│   ├── test_gugik_client.py
│   ├── test_download_manager.py
│   └── test_cli.py
├── docs/
│   ├── SCOPE.md
│   ├── PRD.md
│   └── API_REFERENCE.md
├── .gitignore
├── .flake8
├── pyproject.toml / setup.py
├── requirements.txt
├── README.md
├── CLAUDE.md
├── IMPLEMENTATION_PROMPT.md
└── DEVELOPMENT_STANDARDS.md
```

---

## 5. Technical Specifications

### 5.1 GUGiK Integration

#### WCS Endpoints
```python
# Base URL
BASE_URL = "https://mapy.geoportal.gov.pl"

# NMT WCS Services
WCS_GEOTIFF = f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
WCS_ASCII = f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainMode"

# Request pattern
# GetCoverage z bbox arkusza
```

#### Format Mapping
```python
FORMAT_MAPPING = {
    "GTiff": {
        "service_url": WCS_GEOTIFF,
        "extension": ".tif",
        "mime_type": "image/tiff"
    },
    "AAIGrid": {
        "service_url": WCS_ASCII,
        "extension": ".asc",
        "mime_type": "application/x-ascii-grid"
    },
    "XYZ": {
        "service_url": WCS_ASCII,  # Same service
        "extension": ".xyz",
        "mime_type": "text/plain"
    }
}
```

### 5.2 Error Handling

```python
# Custom Exceptions
class KartografError(Exception):
    """Base exception for Kartograf."""

class ParseError(KartografError):
    """Error parsing godło."""

class DownloadError(KartografError):
    """Error downloading data."""

class ValidationError(KartografError):
    """Error validating input."""

# Retry Strategy
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # seconds (exponential backoff)
TIMEOUT = 30  # seconds per request
```

### 5.3 Logging

```python
import logging

logger = logging.getLogger("kartograf")

# Levels:
logger.debug("Parsing godlo: N-34-130-D")         # Development
logger.info("Downloaded N-34-130-D.tif")          # Normal ops
logger.warning("Retry attempt 2/3")               # Warnings
logger.error("Failed to download N-34-130-D: {e}")  # Errors
logger.critical("Configuration error")            # Critical
```

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Requirement | Target | Rationale |
|-------------|--------|-----------|
| Parse time | < 0.1s | User perception |
| Download time | < 30s | Network dependent |
| Memory usage | < 100MB | Lightweight tool |
| CPU usage | < 50% single core | Background friendly |

### 6.2 Reliability

```
✓ Success rate ≥ 95% dla pobierania arkuszy
✓ Graceful degradation przy network errors
✓ Atomowe operacje zapisu (tmp → rename)
✓ Resumowanie przerwanych pobrań
```

### 6.3 Usability

```
✓ CLI intuicyjne dla użytkowników znających bash
✓ Python API czytelne z autocomplete (type hints)
✓ Komunikaty błędów jasne i actionable
✓ Progress indicators dla długich operacji
```

### 6.4 Maintainability

```
✓ Test coverage ≥ 80% (core logic)
✓ Docstrings wszędzie
✓ Type hints wszędzie
✓ Code zgodny z PEP 8, Black, Flake8
✓ Modularny design (loose coupling)
```

---

## 7. Dependencies

### 7.1 Runtime Dependencies

```
Python 3.12+
requests >= 2.31.0    # HTTP client
```

### 7.2 Development Dependencies

```
pytest >= 7.4.0       # Testing
pytest-cov >= 4.1.0   # Coverage
black >= 23.7.0       # Formatting
flake8 >= 6.1.0       # Linting
mypy >= 1.5.0         # Type checking (optional)
```

### 7.3 Optional Dependencies

```
rich >= 13.5.0        # Pretty CLI (fallback to simple print)
tqdm >= 4.66.0        # Progress bars (fallback to simple print)
```

---

## 8. Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| GUGiK API change | High | Medium | Abstract provider interface, version checks |
| Network failures | Medium | High | Retry logic, resuming, clear error messages |
| Large hierarchy (10k+ sheets) | Medium | Low | Progress tracking, warn user, chunking |
| Disk space full | High | Low | Check available space before download |
| Invalid godło from user | Low | Medium | Comprehensive validation, helpful errors |

---

## 9. Future Enhancements (Post-MVP)

### Version 1.1 - Optimizations
- [ ] Parallel downloads (multi-threading)
- [ ] Connection pooling
- [ ] Metadata cache (SQLite)
- [ ] Integrity checking (checksums)

### Version 1.2 - BBox Support
- [ ] Download by bounding box (instead of godło)
- [ ] Automatic mosaic creation (requires GDAL)
- [ ] Smart tile selection

### Version 2.0 - Advanced
- [ ] GUI interface (web or desktop)
- [ ] Support for other data types (ortophoto, LIDAR)
- [ ] PostGIS integration
- [ ] Cloud storage upload (S3, GCS)

---

## 10. Open Questions

| Question | Status | Decision Date | Decision |
|----------|--------|---------------|----------|
| Czy cache metadanych arkuszy? | Resolved | 2026-01-15 | No - MVP keeps it simple |
| Czy progress bars wymagane? | Resolved | 2026-01-15 | Yes but optional (fallback) |
| Czy async/await dla downloads? | Resolved | 2026-01-15 | No - MVP synchronous |
| Domyślny układ jeśli nie podany? | Resolved | 2026-01-15 | 1992 |

---

**Wersja dokumentu:** 1.0  
**Data ostatniej aktualizacji:** 2026-01-15  
**Status:** Approved - Ready for Implementation  

---

*This is a living document. Updates require approval from Product Owner and Tech Lead.*
