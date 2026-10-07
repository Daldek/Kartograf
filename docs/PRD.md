# PRD.md - Product Requirements Document
**Kartograf - Narzędzie do Pobierania Danych Przestrzennych**

**Wersja:** 3.8
**Data:** 2026-09-30
**Product Owner:** Piotr
**Status:** Production (v0.6.1)

> **Nota (3.5, 2026-08-18):** PRD pozostaje snapshotem zakresu wydania v0.6.1;
> wersja 3.5 usuwa jedynie wewnętrzne sprzeczności (parallel downloads i metadata
> cache odhaczone jako zaimplementowane, LAZ w Public API i diagramie, korekta
> "resumable downloads" i pokrycia testowego). Zakres CZ/CUZK rozwijany na
> develop (v0.7.0-dev: `--country {pl,cz,auto}`, DMR 5G/4G) jest celowo
> nieopisany do czasu wydania 0.7.0 — patrz `docs/SCOPE.md` sekcja 2.2.
>
> **Nota (3.6, 2026-08-22, audyt przedwydaniowy 0.7.0):** dokument nadal jest
> snapshotem v0.6.1, ale przykłady w sekcjach 3.x i lista eksportów w sekcji 5
> zostały punktowo uzgodnione z kodem na `develop` (0.7.0-dev), bo były
> nieprawdziwe niezależnie od wersji: przykładowy bbox leżał w Czechach,
> `output_dir=` nie jest parametrem `LandCoverManager.download()`, a sekcja 5
> gubiła trzy eksporty etapu 1. Liczby jakościowe (sekcja 2.1) pozostają z
> v0.6.1 — aktualne dane wydania 0.7.0 są w `docs/SCOPE.md` 6.2. Decyzja
> o pełnym podniesieniu PRD do 0.7.0 należy do Product Ownera (pozycja
> w checkliście release).
>
> **Nota (3.8, 2026-09-30):** sekcja 3.4 opisuje discovery LAZ z poprawną
> kolejnością osi WFS (N,E); pozostałe wymagania wydania 0.7.0 opisują
> `docs/SCOPE.md` i `docs/ARCHITECTURE.md`.

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
1. **Unified API** - jednolity interfejs dla NMT, NMPT, Ortofoto, LAZ, Land Cover, SoilGrids
2. **Multiple Providers** - GUGiK (NMT/NMPT/Orto/LAZ/BDOT10k), CORINE, SoilGrids
3. **Intelligent Selection** - godło (PL-1992/PL-2000), TERYT, bbox, geometry file
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
| Test coverage (core) | >= 80% | ~89% (osiągnięty) |
| Reliability | >= 95% success rate | Osiągnięty |
| Performance | Download < 60s | Osiągnięty |
| Code quality | ruff | Osiągnięty |

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

# Reverse lookup: bbox → godła
from kartograf import find_sheets_for_bbox
bbox = BBox(771000, 509000, 772000, 510000, "EPSG:2180")
sheets = find_sheets_for_bbox(bbox, "1:10000")

# Reverse lookup: geometry file → godła
from kartograf import find_sheets_for_geometry
sheets = find_sheets_for_geometry(Path("area.shp"), "1:10000")

# Pobieranie przez godło (ASC)
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")

# Pobieranie przez bbox (GeoTIFF, WCS) — tylko NMT 1m i tylko KRON86:
# endpoint WCS dla EVRF2007 został wycofany przez GUGiK (HTTP 404 od 2026-08),
# więc download_bbox pod EVRF2007 kończy się ValidationError. Wysokości
# EVRF2007 bierz z arkuszy: download_sheet() albo CLI `--bbox`, a jako jeden
# GeoTIFF: download_pl_cutout() / CLI `--target-crs` (0.7.0).
kron = DownloadManager(output_dir="./data", vertical_crs="KRON86")
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
path = kron.download_bbox(bbox, "area.tif")

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
kartograf download --bbox 771000,509000,772000,510000
kartograf download --bbox 19.93,50.05,19.95,50.07 --bbox-crs EPSG:4326
kartograf download N-34-130-D --resolution 5m
kartograf download N-34-130-D-d-2-4 --product nmpt
kartograf download N-34-130-D-d-2-4 --product orto
kartograf download N-34-130-D-d-2-4 --product laz
kartograf download --bbox 771000,509000,772000,510000 --product orto
kartograf download --geometry area.shp
kartograf download --geometry area.gpkg --layer catchments
```

---

### 3.2 Feature: NMPT (Numeryczny Model Pokrycia Terenu)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Pobieranie danych NMPT (Digital Surface Model) z GUGiK — teren + obiekty powierzchniowe (drzewa, budynki).

#### Capabilities
```python
from kartograf import GugikNmptProvider

# NMPT provider (tylko 1m, KRON86 lub EVRF2007)
provider = GugikNmptProvider(vertical_crs="EVRF2007")
provider.download("N-34-130-D-d-2-4", Path("./sheet.asc"))

# Przez bbox (WCS)
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
provider.download_bbox(bbox, Path("./area.tif"))
```

#### CLI Commands
```bash
kartograf download N-34-130-D-d-2-4 --product nmpt
kartograf download --bbox 771000,509000,772000,510000 --product nmpt
```

---

### 3.3 Feature: Ortofotomapa (Standard Resolution)

**Priority:** P0 (Critical)
**Status:** Production

#### Description
Pobieranie ortofotomapy (zdjęcia lotnicze) z GUGiK w rozdzielczości 25cm.

#### Capabilities
```python
from kartograf import GugikOrtoProvider

# Ortofoto provider (brak vertical CRS — 2D RGB)
provider = GugikOrtoProvider()
provider.download("N-34-130-D-d-2-4", Path("./sheet.tif"))

# Przez bbox (WCS, formaty: GTiff, PNG, JPEG)
bbox = BBox(450000, 550000, 460000, 560000, "EPSG:2180")
provider.download_bbox(bbox, Path("./area.tif"), format="GTiff")
```

#### CLI Commands
```bash
kartograf download N-34-130-D-d-2-4 --product orto
kartograf download --bbox 771000,509000,772000,510000 --product orto
```

---

### 3.4 Feature: LAZ (Chmury Punktów LIDAR)

**Priority:** P1 (High)
**Status:** Production

#### Description
Pobieranie chmur punktów LIDAR (dane pomiarowe ALS, pliki `.laz`) z GUGiK. Discovery jest **area-based** przez WFS: jedno godło 1:10000 (lub `--bbox` / `--geometry`) zwraca wiele kafli LAZ (godłowane drobniej niż 1:10000), każdy z własnym URL OpenData. Godło kafla jest nieparsowalne i traktowane jako etykieta.

#### Capabilities
```python
from kartograf import GugikLazProvider, BBox

provider = GugikLazProvider(vertical_crs="EVRF2007")
bbox = BBox(530000, 382000, 533000, 386000, "EPSG:2180")
tiles = provider.discover_tiles(bbox, year=2024, min_density=12)
for tile in tiles:
    provider.download(tile.url, Path("./laz") / tile.filename)
```

#### CLI Commands
```bash
kartograf download N-34-130-D-d-2-4 --product laz
kartograf download N-34-130-D-d-2-4 --product laz --year 2024 --min-density 12
kartograf download --bbox 530000,382000,533000,386000 --product laz --vertical-crs KRON86
kartograf download --geometry area.shp --product laz
```

#### Notes
- WFS EPSG:2180 przyjmuje bbox i zwraca envelope w kolejności osi (N,E);
  discovery odrzuca zestaw kafli, w którym żaden nie przecina obszaru.
- Źródło: GUGiK WFS (`DanePomiaroweLidarEVRF2007` / `DanePomiaroweLidarKRON86`)
- Domyślnie najnowszy kafel per obszar: starszy kafel pomijany, gdy jego część obszaru pokrywają nowsze (ramy w EPSG:2180, tolerancja 1 m; ADR-029)
- Pobieranie równoległe (`--workers`), pomijanie istniejących plików

---

### 3.5 Feature: BDOT10k (Land Cover - GUGiK)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie danych pokrycia terenu z polskiej bazy BDOT10k.

#### Capabilities
```python
from pathlib import Path

from kartograf import LandCoverManager, Bdot10kProvider

# katalog wyjściowy ustawia KONSTRUKTOR; download() przyjmuje output_path=
lc = LandCoverManager(output_dir="./data")
lc.set_provider("bdot10k")

# Pobieranie przez TERYT (powiat) — nazwa pliku generowana automatycznie
lc.download(teryt="1465")

# Pobieranie przez godło z jawną ścieżką pliku
lc.download(godlo="N-34-130-D", output_path=Path("./data/bdot10k_N-34-130-D.gpkg"))
```

#### Warstwy (15 warstw — pobierany caly plik)

**Pokrycie terenu (PT* — 12 warstw):**
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

**Hydrografia (SW* — 3 warstwy):**
| Warstwa | Opis |
|---------|------|
| SWRS | Rzeki i strumienie |
| SWKN | Kanały |
| SWRM | Rowy melioracyjne |

#### CLI Commands
```bash
kartograf landcover download --source bdot10k --teryt 1465
kartograf landcover download --source bdot10k --godlo N-34-130-D
kartograf landcover list-layers --source bdot10k
```

---

### 3.6 Feature: CORINE Land Cover (Copernicus)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie europejskiej klasyfikacji pokrycia terenu CORINE (44 klasy).

#### Capabilities
```python
from pathlib import Path

from kartograf import LandCoverManager, CorineProvider

lc = LandCoverManager(output_dir="./data")
lc.set_provider("corine")

# Pobieranie przez godło (rozszerzenie wymusza provider: .tif, .png dla WMS)
lc.download(
    godlo="N-34-130-D",
    year=2018,
    output_path=Path("./data/corine_2018_N-34-130-D.tif"),
)
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

### 3.7 Feature: SoilGrids (Dane Glebowe)

**Priority:** P1
**Status:** Production

#### Description
Pobieranie globalnych danych glebowych z ISRIC SoilGrids (rozdzielczość 250m).

#### Capabilities
```python
from pathlib import Path

from kartograf import LandCoverManager, SoilGridsProvider

lc = LandCoverManager(output_dir="./data")
lc.set_provider("soilgrids")

# Pobieranie węgla organicznego (selekcja: godło albo bbox — TERYT
# nie jest obsługiwany przez SoilGrids i kończy się NotImplementedError)
lc.download(
    godlo="N-34-130-D",
    property="soc",
    depth="0-5cm",
    stat="mean",
    output_path=Path("./data/soilgrids_soc_0-5cm.tif"),
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

### 3.8 Feature: HSG (Hydrologic Soil Groups)

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
┌───────────────────────────────────────────────────────────────────────────┐
│                                 Providers                                 │
├─────────┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│ Gugik   │ GugikNmpt│ GugikOrto│ GugikLaz │ Bdot10k  │ Corine   │ SoilGrids│
│ (NMT)   │ (NMPT)   │ (Orto)   │ (LAZ)    │ Provider │ Provider │ Provider │
└────┬────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┘
     │         │          │          │          │          │          │
     v         v          v          v          v          v          v
┌───────────────────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────┐ ┌─────────┐
│ GUGiK WCS / OpenData  │ │ GUGiK WFS │ │ GUGiK    │ │ CLMS API     │ │ ISRIC   │
│ (NMT, NMPT, Ortofoto) │ │ + OpenData│ │ OpenData │ │ (Auth Proxy) │ │ WCS     │
└───────────────────────┘ │ (LAZ)     │ │ (BDOT10k)│ └──────────────┘ └─────────┘
                          └───────────┘ └──────────┘
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

Lista odzwierciedla `kartograf/__init__.py::__all__` na `develop` (39 nazw);
źródłem prawdy pozostaje sam moduł.

```python
# kartograf/__init__.py exports:
from kartograf import (
    # Cache
    MetadataCache,

    # Core
    SheetParser,
    Parser2000,
    ParserTM33,
    BBox,
    find_sheets_for_bbox,
    find_sheets_2000_for_bbox,
    find_sheets_for_geometry,

    # Download (NMT/NMPT/Orto/LAZ)
    DownloadManager,
    DownloadProgress,
    DownloadResult,
    FileStorage,

    # Download — wycinek PL (ADR-027)
    PlCutout,
    PlCutoutResult,
    PlCutoutSheets,
    download_pl_cutout,
    prepare_pl_cutout,
    run_pl_cutout,
    select_pl_cutout_sheets,

    # Land Cover
    LandCoverManager,

    # Providers
    BaseProvider,
    GugikProvider,
    GugikNmptProvider,
    GugikOrtoProvider,
    GugikLazProvider,
    LazTile,
    LandCoverProvider,
    Bdot10kProvider,
    CorineProvider,
    SoilGridsProvider,

    # Providers — CZ (CUZK, etap 1)
    CuzkDmrProvider,
    create_dmr_provider,

    # Hydrology
    HSGCalculator,

    # Exceptions
    KartografError,
    ParseError,
    ValidationError,
    DownloadError,
    NoCoverageError,

    # Version
    __version__,  # "0.7.0-dev" (0.7.0 po wydaniu)
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
pyshp >= 2.3.0         # Shapefile reading
```

### 6.2 Development Dependencies

```
pytest >= 8.0          # Testing
pytest-cov >= 5.0      # Coverage
ruff >= 0.8            # Linting + Formatting
mypy >= 1.13           # Type checking
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
- Skip-existing: already downloaded files are not re-fetched

### 7.3 Security

- Auth Proxy isolates CLMS credentials
- Credentials stored in macOS Keychain
- No hardcoded secrets in code

---

## 8. Future Enhancements

### Version 0.6+
- [x] Parallel downloads (multi-threading) (implemented in v0.6.0)
- [x] Metadata cache (SQLite) (implemented in v0.6.0)
- [x] Automatic mosaic creation — NMT PL: wycinek `--target-crs` /
      `download_pl_cutout` (0.7.0); pozostałe produkty — etap 2

### Version 1.0+
- [ ] GUI interface
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

**Wersja dokumentu:** 3.8
**Data ostatniej aktualizacji:** 2026-09-30
**Status:** Production - v0.6.1 (snapshot; punktowe korekty spójności do 3.8, patrz noty na początku dokumentu)
