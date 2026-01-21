# PRD.md - Product Requirements Document
**Kartograf - Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 2.0
**Data:** 2026-01-21
**Product Owner:** Piotr
**Status:** Production (v0.3.1)

---

## 1. Executive Summary

### 1.1 Problem Statement

Pobieranie danych przestrzennych z różnych źródeł (GUGiK, Copernicus, ISRIC) jest:
- **Czasochłonne** - różne interfejsy webowe i protokoły API
- **Skomplikowane** - wymagana znajomość systemów identyfikacji (godła, TERYT, bbox)
- **Nieefektywne** - pobieranie plików jeden po drugim
- **Niejednolite** - różne formaty i autentykacja dla każdego źródła

### 1.2 Solution

Kartograf to narzędzie CLI + biblioteka Python oferujące:
1. **Unified API** - jednolity interfejs dla NMT, Land Cover, SoilGrids
2. **Multiple Providers** - GUGiK, BDOT10k, CORINE, SoilGrids
3. **Intelligent Selection** - godło, TERYT, bbox
4. **Automatic Processing** - scalanie warstw, kalkulacja HSG
5. **Secure Auth** - Auth Proxy dla izolacji credentials

### 1.3 Target Users

| Persona | Potrzeby | Użycie |
|---------|----------|--------|
| **Deweloper Hydrograf/Hydrolog** | Dane NMT, gleba, HSG dla obliczeń | Python API |
| **Specjalista GIS** | Dane topograficzne, pokrycie terenu | CLI |
| **Hydrolog** | HSG dla metody SCS-CN | CLI + Python API |

---

## 2. Goals & Metrics

### 2.1 Technical Goals

| Cel | Target | Status |
|-----|--------|--------|
| Test coverage (core) | >= 80% | 57% (w trakcie) |
| Reliability | >= 95% success rate | Osiągnięty |
| Performance | Download < 60s | Osiągnięty |
| Code quality | black + flake8 | Osiągnięty |

### 2.2 Integration Goals

| Cel | Status |
|-----|--------|
| Integracja z Hydrograf | Gotowy |
| Integracja z Hydrolog | Gotowy |
| Public API exports | Kompletny |

---

## 3. Core Features

### 3.1 Feature: NMT (Numeryczny Model Terenu)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Pobieranie danych wysokościowych NMT z GUGiK w rozdzielczościach 1m i 5m.

#### Capabilities
```python
# Parser godeł
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)       # "1:10000"
print(parser.get_bbox())  # BBox(min_x=..., max_x=..., ...)

# Hierarchia arkuszy
hierarchy = parser.get_hierarchy_up()
descendants = parser.get_all_descendants("1:10000")

# Pobieranie przez godło (ASC)
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")

# Pobieranie przez bbox (GeoTIFF)
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
path = manager.download_bbox(bbox, "area.tif")

# Rozdzielczość 5m (tylko EVRF2007)
manager_5m = DownloadManager(resolution="5m")
path = manager_5m.download_sheet("N-34-130-D-d-2-4")
```

#### CLI Commands
```bash
kartograf parse N-34-130-D-d-2-4
kartograf parse N-34-130-D --hierarchy
kartograf download N-34-130-D-d-2-4
kartograf download N-34-130-D --scale 1:10000
kartograf download N-34-130-D --resolution 5m
```

---

### 3.2 Feature: BDOT10k (Land Cover - GUGiK)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie danych pokrycia terenu z polskiej bazy BDOT10k.

#### Capabilities
```python
from kartograf import LandCoverManager, Bdot10kProvider

lc = LandCoverManager()
lc.set_provider("bdot10k")

# Pobieranie przez TERYT (powiat)
lc.download(teryt="1465", output_dir="./data")

# Pobieranie przez godło
lc.download(godlo="N-34-130-D", output_dir="./data")
```

#### Warstwy PT* (12 warstw)
| Warstwa | Opis |
|---------|------|
| PTGN | Grunty nieużytkowe |
| PTKM | Tereny komunikacyjne |
| PTLZ | Tereny leśne |
| PTNZ | Tereny niezabudowane |
| PTPL | Place |
| PTRK | Roślinność krzewiasta |
| PTSO | Składowiska |
| PTTR | Tereny rolne |
| PTUT | Uprawy trwałe |
| PTWP | Wody powierzchniowe |
| PTWZ | Tereny zabagnione |
| PTZB | Tereny zabudowane |

#### CLI Commands
```bash
kartograf landcover download --source bdot10k --teryt 1465
kartograf landcover download --source bdot10k --godlo N-34-130-D
kartograf landcover list-layers --source bdot10k
```

---

### 3.3 Feature: CORINE Land Cover (Copernicus)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie europejskiej klasyfikacji pokrycia terenu CORINE (44 klasy).

#### Capabilities
```python
from kartograf import LandCoverManager, CorineProvider

lc = LandCoverManager()
lc.set_provider("corine")

# Pobieranie przez godło
lc.download(godlo="N-34-130-D", year=2018, output_dir="./data")
```

#### Dostępne lata
- 1990, 2000, 2006, 2012, 2018

#### Źródła danych (priorytet)
1. **CLMS API** - GeoTIFF z kodami klas (wymaga OAuth2)
2. **EEA Discomap WMS** - podgląd PNG (fallback)
3. **DLR WMS** - fallback dla 1990

#### Auth Proxy (bezpieczeństwo)
```
CorineProvider → localhost HTTP → AuthProxy subprocess → Keychain → CLMS API
```
Credentials nigdy nie opuszczają procesu Auth Proxy.

#### CLI Commands
```bash
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D
kartograf landcover list-layers --source corine
```

---

### 3.4 Feature: SoilGrids (Dane Glebowe)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie globalnych danych glebowych z ISRIC SoilGrids (rozdzielczość 250m).

#### Capabilities
```python
from kartograf import LandCoverManager, SoilGridsProvider

lc = LandCoverManager()
lc.set_provider("soilgrids")

# Pobieranie węgla organicznego
lc.download(
    godlo="N-34-130-D",
    property="soc",
    depth="0-5cm",
    stat="mean",
    output_dir="./data"
)

# Pobieranie zawartości gliny
lc.download(
    godlo="N-34-130-D",
    property="clay",
    depth="15-30cm"
)
```

#### Dostępne parametry (11)
| Parametr | Opis | Jednostka |
|----------|------|-----------|
| bdod | Gęstość objętościowa | kg/dm³ |
| cec | Pojemność wymiany kationowej | cmol/kg |
| cfvo | Fragmenty gruboziarniste | % |
| clay | Zawartość gliny | % |
| nitrogen | Azot całkowity | g/kg |
| ocd | Gęstość węgla organicznego | kg/m³ |
| ocs | Zasób węgla organicznego | t/ha |
| phh2o | pH w H2O | - |
| sand | Zawartość piasku | % |
| silt | Zawartość pyłu | % |
| soc | Węgiel organiczny | g/kg |

#### Głębokości (6)
0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm

#### Statystyki (5)
mean, Q0.05, Q0.5, Q0.95, uncertainty

#### CLI Commands
```bash
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm
kartograf landcover list-layers --source soilgrids
```

---

### 3.5 Feature: HSG (Hydrologic Soil Groups)

**Priority:** P1
**Status:** Production

#### Description
Kalkulacja grup hydrologicznych gleb (HSG) dla metody SCS-CN na podstawie danych tekstury z SoilGrids.

#### Capabilities
```python
from kartograf import HSGCalculator
from pathlib import Path

calc = HSGCalculator()

# Oblicz HSG dla godła
calc.calculate_hsg_by_godlo("N-34-130-D", Path("./hsg.tif"))

# Statystyki HSG
stats = calc.get_hsg_statistics(Path("./hsg.tif"))
for group, data in stats.items():
    print(f"Grupa {group}: {data['percent']:.1f}%")
```

#### Grupy hydrologiczne
| Grupa | Infiltracja | Tekstury | Potencjał odpływu |
|-------|-------------|----------|-------------------|
| A | Wysoka | piasek, piasek gliniasty | Niski |
| B | Umiarkowana | glina piaszczysta, glina | Umiarkowany |
| C | Wolna | glina ilasta | Wysoki |
| D | Bardzo wolna | ił | Bardzo wysoki |

#### Format wyjściowy
Raster GeoTIFF z wartościami:
- 1 = Grupa A
- 2 = Grupa B
- 3 = Grupa C
- 4 = Grupa D
- 0 = NoData

#### CLI Commands
```bash
kartograf soilgrids hsg --godlo N-34-130-D
kartograf soilgrids hsg --godlo N-34-130-D --stats
kartograf soilgrids hsg --godlo N-34-130-D --depth 15-30cm --output /tmp/hsg.tif
kartograf soilgrids hsg --godlo N-34-130-D --keep-intermediate
```

---

## 4. Architecture

### 4.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface                           │
├──────────────────────┬──────────────────────────────────────┤
│        CLI           │           Python API                 │
└──────────┬───────────┴─────────────┬────────────────────────┘
           │                         │
           v                         v
┌─────────────────────────────────────────────────────────────┐
│                     Managers                                │
├────────────────────────┬────────────────────────────────────┤
│   DownloadManager      │      LandCoverManager              │
│   (NMT)                │      (BDOT10k, CORINE, SoilGrids)  │
└──────────┬─────────────┴─────────────┬──────────────────────┘
           │                           │
           v                           v
┌─────────────────────────────────────────────────────────────┐
│                      Providers                              │
├───────────┬───────────┬───────────┬─────────────────────────┤
│ GugikProv │ Bdot10k   │ Corine    │ SoilGrids               │
│ (NMT)     │ Provider  │ Provider  │ Provider                │
└─────┬─────┴─────┬─────┴─────┬─────┴──────────┬──────────────┘
      │           │           │                │
      v           v           v                v
┌─────────┐ ┌─────────┐ ┌──────────────┐ ┌─────────────┐
│ GUGiK   │ │ GUGiK   │ │ CLMS API     │ │ ISRIC WCS   │
│ WCS/    │ │ OpenData│ │ (Auth Proxy) │ │             │
│ OpenData│ │         │ │ EEA WMS      │ │             │
└─────────┘ └─────────┘ └──────────────┘ └─────────────┘
```

### 4.2 Hydrology Module

```
┌─────────────────────────────────────────────────────────────┐
│                    HSGCalculator                            │
├─────────────────────────────────────────────────────────────┤
│  calculate_hsg_by_godlo()                                   │
│  calculate_hsg_by_bbox()                                    │
│  get_hsg_statistics()                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           v
┌─────────────────────────────────────────────────────────────┐
│              SoilGridsProvider                              │
│  (pobiera clay, sand, silt)                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           v
┌─────────────────────────────────────────────────────────────┐
│  USDA Texture Triangle  →  HSG Mapping                      │
│  (12 klas tekstury)        (4 grupy hydrologiczne)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Public API

```python
# kartograf/__init__.py exports:
from kartograf import (
    # Core
    SheetParser,
    BBox,

    # Download (NMT)
    DownloadManager,
    DownloadProgress,
    FileStorage,

    # Land Cover
    LandCoverManager,

    # Providers
    BaseProvider,
    GugikProvider,
    LandCoverProvider,
    Bdot10kProvider,
    CorineProvider,
    SoilGridsProvider,

    # Hydrology
    HSGCalculator,

    # Exceptions
    KartografError,
    ParseError,
    ValidationError,
    DownloadError,

    # Version
    __version__,  # "0.3.1"
)
```

---

## 6. Dependencies

### 6.1 Runtime Dependencies

```
Python >= 3.12
requests >= 2.31.0     # HTTP client
pyproj >= 3.6.0        # CRS transformations
PyJWT[crypto] >= 2.8.0 # OAuth2 JWT (CLMS)
rasterio >= 1.3.0      # GeoTIFF processing
numpy >= 1.24.0        # Array operations
```

### 6.2 Development Dependencies

```
pytest >= 7.4.0        # Testing
pytest-cov >= 4.1.0    # Coverage
black >= 23.7.0        # Formatting
flake8 >= 6.1.0        # Linting
```

---

## 7. Non-Functional Requirements

### 7.1 Performance

| Requirement | Target |
|-------------|--------|
| Parse time | < 0.1s |
| NMT download | < 30s |
| Land Cover download | < 60s |
| HSG calculation | < 120s |

### 7.2 Reliability

- Success rate >= 95%
- Retry logic: 3 attempts, exponential backoff
- Atomic writes (tmp → rename)
- Resumable downloads

### 7.3 Security

- Auth Proxy isolates CLMS credentials
- Credentials stored in macOS Keychain
- No hardcoded secrets in code

---

## 8. Future Enhancements

### Version 0.4+
- [ ] Parallel downloads (multi-threading)
- [ ] Metadata cache (SQLite)
- [ ] Automatic mosaic creation

### Version 1.0+
- [ ] GUI interface
- [ ] Additional data sources (ortophoto, LIDAR)
- [ ] PostGIS integration
- [ ] REST API server

---

## 9. Cross-Project Integration

### 9.1 Dependency Map

```
HYDROGRAF (główna aplikacja)
    ├── IMGWTools (dane IMGW)
    ├── Kartograf (dane GIS) ← TEN PROJEKT
    └── Hydrolog (obliczenia hydrologiczne)
            ├── IMGWTools (wymagany)
            └── Kartograf (opcjonalny)
```

### 9.2 Integration Points

| Projekt | Używa z Kartograf |
|---------|-------------------|
| Hydrograf | DownloadManager, LandCoverManager |
| Hydrolog | HSGCalculator, SoilGridsProvider |

---

**Wersja dokumentu:** 2.0
**Data ostatniej aktualizacji:** 2026-01-21
**Status:** Production - v0.3.1
