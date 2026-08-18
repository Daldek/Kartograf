# Kartograf

Narzędzie do automatycznego pobierania danych przestrzennych z zasobów GUGiK (Polska), CUZK (Czechy), Copernicus i ISRIC:
- **NMT (PL)** - Numeryczny Model Terenu z GUGiK (dane wysokościowe, 1m/5m)
- **NMT (CZ)** - DMR 5G/4G z CUZK (2m/5m, godło TM33/SM5 lub bbox, `--country {pl,cz,auto}`)
- **NMPT** - Numeryczny Model Pokrycia Terenu / DSM (teren + obiekty, 1m)
- **Ortofotomapa** - Zdjęcia lotnicze Standard Resolution (25cm, TIF)
- **LAZ** - Chmury punktów LIDAR (dane pomiarowe ALS) z GUGiK przez WFS
- **BDOT10k** - Baza Danych Obiektów Topograficznych (pokrycie terenu, wektory)
- **CORINE Land Cover** - Europejska klasyfikacja pokrycia terenu (44 klasy)
- **SoilGrids** - Globalne dane glebowe (tekstura, węgiel organiczny, pH)
- **HSG** - Hydrologic Soil Groups dla metody SCS-CN (grupy hydrologiczne gleb)

## Szybki Start

### Instalacja

```bash
# Klonowanie repozytorium
git clone https://github.com/Daldek/Kartograf.git
cd Kartograf

# Utworzenie środowiska wirtualnego
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalacja pakietu
pip install -e .
```

### Użycie

#### Jako CLI

```bash
# Informacje o godle (auto-detekcja PL-1992 / PL-2000)
kartograf parse N-34-130-D-d-2-4

# Pobieranie NMT: pojedynczy arkusz albo hierarchia, opcjonalnie 5m
kartograf download N-34-130-D-d-2-4
kartograf download N-34-130-D --scale 1:10000 --resolution 5m --output ./data

# Inne produkty GUGiK: NMPT (DSM), ortofotomapa, chmury punktów LAZ
kartograf download N-34-130-D-d-2-4 --product nmpt
kartograf download N-34-130-D-d-2-4 --product laz

# Selekcja obszaru: bbox albo plik geometrii (SHP/GPKG)
kartograf download --bbox 419000,230000,426000,237000 --product orto
kartograf download --geometry zlewnia.gpkg --layer catchments

# PL-2000: godło albo bbox w CRS strefy
kartograf download 6.179.12.20
kartograf download --bbox 6500000,5895000,6508000,5900000 --bbox-crs EPSG:2177 --system 2000

# NMT Czechy (CUZK DMR 5G/4G); na pograniczu --country auto dzieli żądanie na PL i CZ
kartograf download 302_5550 --country cz
kartograf download --bbox 18.60,49.752,18.65,49.768 --bbox-crs EPSG:4326 --country auto

# Pokrycie terenu i gleby: BDOT10k, CORINE, SoilGrids
kartograf landcover download --source bdot10k --teryt 1465
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D
kartograf landcover download --source soilgrids --godlo N-34-130-D --property clay --depth 15-30cm

# Hydrologic Soil Groups dla metody SCS-CN
kartograf soilgrids hsg --godlo N-34-130-D --stats

# Przegląd źródeł/warstw i cache metadanych
kartograf landcover list-sources
kartograf landcover list-layers --source soilgrids
kartograf cache stats
```

#### Jako biblioteka Python

```python
from pathlib import Path
from kartograf import SheetParser, DownloadManager, BBox

# Parsowanie godła i bounding box arkusza
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)                      # "1:10000"
bbox = parser.get_bbox(crs="EPSG:2180")  # lub "EPSG:4326"

# Pobieranie przez godło → ASC (OpenData); hierarchia: download_hierarchy()
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")

# Pobieranie przez bbox → GeoTIFF (WCS) - tylko dla NMT 1m
area = BBox(min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180")
path = manager.download_bbox(area, "my_area.tif")

# Land Cover: BDOT10k / CORINE / SoilGrids
from kartograf import LandCoverManager
lc = LandCoverManager()
lc.download(teryt="1465")                   # BDOT10k (powiat)
lc.set_provider("corine")
lc.download(godlo="N-34-130-D", year=2018)  # CORINE

# Hydrologic Soil Groups
from kartograf import HSGCalculator
calc = HSGCalculator()
calc.calculate_hsg_by_godlo("N-34-130-D", Path("./hsg.tif"))
stats = calc.get_hsg_statistics(Path("./hsg.tif"))
```

Pozostałe elementy publicznego API (m.in. `GugikNmptProvider`, `GugikOrtoProvider`,
`GugikLazProvider`, `CuzkDmrProvider`/`create_dmr_provider` dla Czech, `Parser2000`,
`ParserTM33`, `MetadataCache`, `FileStorage`) — patrz eksporty w `kartograf/__init__.py`
oraz [SCOPE.md](docs/SCOPE.md).

## Funkcjonalności

### NMT (Numeryczny Model Terenu)
- ✅ **Parser godeł** - Obsługa układów PL-1992 (1:1M - 1:10k) i PL-2000 (1:10k - 1:500)
- ✅ **Bounding box** - Obliczanie współrzędnych arkusza (EPSG:2180, EPSG:4326)
- ✅ **Hierarchia arkuszy** - Automatyczne określanie arkuszy nadrzędnych i podrzędnych
- ✅ **Selekcja obszaru** - Godło, bbox, plik geometrii (SHP/GPKG)
- ✅ **Pobieranie NMT** - Z retry logic i progress tracking
- ✅ **Organizacja plików** - Automatyczna struktura katalogów (`data/nmt_1m/`, `data/nmt_5m/`)
- ✅ **Formaty** - GeoTIFF, PNG, JPEG (WCS), ASC (OpenData)
- ✅ **Rozdzielczości:**
  - `1m` (GRID1) - wysoka rozdzielczość, KRON86 i EVRF2007
  - `5m` (GRID5) - niższa rozdzielczość, tylko EVRF2007

### NMT Czechy (CUZK, od 0.7.0-dev)
- ✅ **DMR 5G** (2m, godło TM33 lub bbox) i **DMR 4G** (5m, godło SM5)
- ✅ **CLI** - `--country {pl,cz,auto}`; `auto` na pograniczu dzieli żądanie na osobne pliki PL i CZ
- ✅ **Układy** - natywnie S-JTSK/Bpv (EPSG:5514); opcjonalna reprojekcja lokalna `--target-crs` oraz `--vertical-crs EVRF2007`

### NMPT (Numeryczny Model Pokrycia Terenu)
- ✅ **Digital Surface Model** - Teren + obiekty powierzchniowe (drzewa, budynki)
- ✅ **Pobieranie przez godło** → ASC (OpenData)
- ✅ **Pobieranie przez bbox** → GeoTIFF (WCS)
- ✅ **Rozdzielczość** - Tylko 1m, układy KRON86 i EVRF2007
- ✅ **Organizacja** - `data/nmpt/`

### Ortofotomapa (Standard Resolution)
- ✅ **Zdjęcia lotnicze** - 25cm, format TIF
- ✅ **Pobieranie przez godło** → TIF (OpenData)
- ✅ **Pobieranie przez bbox** → GeoTIFF (WCS), także PNG i JPEG
- ✅ **4 warstwy WMS** - 2026, 2025, 2024 + Starsze (roczniki 2018-2023 skonsolidowane)
- ✅ **Organizacja** - `data/orto/`

### LAZ (Chmury Punktów LIDAR)
- ✅ **Dane pomiarowe ALS** (.laz) z GUGiK przez WFS, selekcja obszarem (godło/bbox/geometria)
- ✅ **Filtry** - `--year`, `--min-density`; organizacja - `data/laz/`

### Land Cover (Pokrycie Terenu)
- ✅ **BDOT10k** - Polska baza wektorowa (GUGiK), szczegółowość 1:10 000
  - 15 warstw: 12 pokrycia terenu (PT*) + 3 hydrograficzne (SW*)
  - Lasy, wody, zabudowa, tereny rolne, rzeki, kanały, rowy melioracyjne, itp.
  - Automatyczne scalanie warstw do jednego GeoPackage (z zachowaniem rtree index)
- ✅ **CORINE Land Cover** - Europejska klasyfikacja (Copernicus), 44 klasy
- ✅ **Metody selekcji** - TERYT (powiat), bbox, godło arkusza, plik geometrii (SHP/GPKG)
- ✅ **Formaty** - GeoPackage, Shapefile, GeoTIFF, PNG

### SoilGrids (Dane Glebowe)
- ✅ **ISRIC SoilGrids** - Globalne dane glebowe, rozdzielczość 250m
- ✅ **11 parametrów glebowych:**
  - `clay`, `sand`, `silt` - tekstura gleby (%)
  - `soc` - węgiel organiczny (g/kg)
  - `phh2o` - pH w H2O
  - `nitrogen` - azot całkowity (g/kg)
  - `bdod` - gęstość objętościowa (kg/dm³)
  - `cec` - pojemność wymiany kationowej (cmol/kg)
  - `cfvo` - fragmenty gruboziarniste (%)
  - `ocd`, `ocs` - gęstość i zasób węgla organicznego
- ✅ **6 głębokości:** 0-5cm, 5-15cm, 15-30cm, 30-60cm, 60-100cm, 100-200cm
- ✅ **5 statystyk:** mean, Q0.05, Q0.5, Q0.95, uncertainty

### Hydrologic Soil Groups (HSG)
- ✅ **Kalkulacja HSG** dla metody SCS-CN (Curve Number)
- ✅ **Klasyfikacja USDA** - trójkąt tekstury, 12 klas
- ✅ **4 grupy hydrologiczne:**
  - A - wysoka infiltracja (piasek)
  - B - umiarkowana infiltracja (glina)
  - C - wolna infiltracja (glina ilasta)
  - D - bardzo wolna infiltracja (ił)
- ✅ **Automatyczne pobieranie** clay/sand/silt z SoilGrids
- ✅ **Statystyki pokrycia** dla każdej grupy HSG

## Konfiguracja CLMS API (opcjonalne)

Aby pobierać dane CORINE jako **GeoTIFF z kodami klas** (zamiast podglądu PNG),
potrzebujesz konta w Copernicus Land Monitoring Service:

1. Zarejestruj się na https://land.copernicus.eu
2. Wygeneruj API credentials (profil → API access)
3. Zapisz credentials w zmiennej środowiskowej `CLMS_CREDENTIALS` (JSON string
   o polach jak niżej) albo — na macOS — w Keychain:

```bash
security add-generic-password -a "$USER" -s "clms-token" -w '{
  "client_id": "...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "token_uri": "https://land.copernicus.eu/@@oauth2-token",
  "key_id": "...",
  "user_id": "..."
}'
```

**Bezpieczeństwo:** Credentials są izolowane w osobnym procesie (Auth Proxy).
Główna aplikacja nigdy nie widzi kluczy prywatnych.

**Bez konfiguracji:** CORINE automatycznie pobiera podgląd PNG przez WMS.

## Dokumentacja

- [SCOPE.md](docs/SCOPE.md) - Zakres projektu (co JEST i czego NIE MA)
- [PRD.md](docs/PRD.md) - Product Requirements Document
- [PROGRESS.md](docs/PROGRESS.md) - Status implementacji i checkpointy
- [CHANGELOG.md](docs/CHANGELOG.md) - Historia zmian
- [DECISIONS.md](docs/DECISIONS.md) - Rejestr decyzji architektonicznych (ADR)
- [DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md) - Standardy kodowania
- [IMPLEMENTATION_PROMPT.md](docs/IMPLEMENTATION_PROMPT.md) - Kontekst dla asystentow AI

## Wymagania

- Python 3.12+
- requests >= 2.31.0
- pyproj >= 3.6.0
- PyJWT[crypto] >= 2.8.0
- rasterio >= 1.3.0
- numpy >= 1.24.0
- pyshp >= 2.3.0

## Struktura Projektu

```
Kartograf/
├── kartograf/           # Kod źródłowy
│   ├── auth/            # Auth Proxy (bezpieczna autentykacja CLMS)
│   ├── cache/           # Cache metadanych (SQLite)
│   ├── core/            # Parsery godeł (PL-1992/PL-2000/TM33), BBox, geometria (SHP/GPKG)
│   ├── sources/         # Deskryptory źródeł danych + sidecar metadanych
│   ├── transform/       # Transformacje CRS (przypięte operacje)
│   ├── transport/       # Wspólny transport HTTP + mozaikowanie rastrów
│   ├── providers/       # Providery danych (pl/: GUGiK, BDOT10k; cuzk/: DMR CZ; CORINE, SoilGrids)
│   ├── download/        # Download management (NMT/NMPT/Orto/LAZ)
│   ├── landcover/       # Land Cover management
│   ├── hydrology/       # Hydrologic Soil Groups (HSG)
│   └── cli/             # CLI interface (moduły per komenda)
├── tests/               # Testy (1402)
├── docs/                # Dokumentacja
└── README.md
```

## Dla Deweloperów

### Środowisko

```bash
# Aktywuj .venv
source .venv/bin/activate

# Przeczytaj dokumentację przed rozpoczęciem
cat CLAUDE.md
```

### Testy

```bash
# Uruchom wszystkie testy
pytest tests/

# Z pokryciem kodu
pytest tests/ --cov=kartograf --cov-report=html

# Formatowanie
ruff format kartograf/ tests/

# Linting
ruff check kartograf/ tests/
```

## Licencja

Projekt udostępniony na licencji MIT. Szczegóły w pliku `LICENSE`.

## Autor

[Piotr de Bever](https://www.linkedin.com/in/piotr-de-bever/)

## Status

**Wersja 0.7.0-dev** - NMT Czechy (CUZK DMR 5G/4G, `--country {pl,cz,auto}`, parser godeł TM33/SM5, sidecary metadanych `.meta.json`). Wcześniej: v0.6.x (LAZ przez WFS, pobieranie równoległe `--workers`, cache metadanych SQLite, walidacja warstw WMS), v0.5.0 (PL-2000, 15 warstw BDOT10k). 1402 testy, pokrycie ~89%. Zobacz [CHANGELOG.md](docs/CHANGELOG.md) dla szczegolów.
