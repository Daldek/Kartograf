# Kartograf

Narzędzie do automatycznego pobierania danych przestrzennych z zasobów GUGiK i Copernicus dla Polski:
- **NMT** (Numeryczny Model Terenu) - dane wysokościowe
- **Land Cover** - pokrycie terenu (BDOT10k, CORINE)

## Szybki Start

### Instalacja

```bash
# Klonowanie repozytorium
git clone https://github.com/Daldek/Kartograf.git
cd kartograf

# Utworzenie środowiska wirtualnego
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalacja zależności
pip install -r requirements.txt
```

### Użycie

#### Jako CLI

```bash
# Informacje o godle
kartograf parse N-34-130-D-d-2-4

# Pobieranie NMT (pojedynczy arkusz)
kartograf download N-34-130-D-d-2-4

# Pobieranie NMT (hierarchia)
kartograf download N-34-130-D --scale 1:10000 --output ./data

# Pobieranie Land Cover (BDOT10k - powiat)
kartograf landcover download --source bdot10k --teryt 1465

# Pobieranie Land Cover (BDOT10k - godło)
kartograf landcover download --source bdot10k --godlo N-34-130-D

# Pobieranie Land Cover (CORINE)
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D

# Lista źródeł i warstw
kartograf landcover list-sources
kartograf landcover list-layers --source bdot10k
```

#### Jako biblioteka Python

```python
from kartograf import SheetParser, DownloadManager, BBox

# Parsowanie godła
parser = SheetParser("N-34-130-D-d-2-4")
print(parser.scale)      # "1:10000"
print(parser.godlo)      # "N-34-130-D-d-2-4"
print(parser.components) # {"pas": "N", "slup": "34", ...}

# Bounding box arkusza
bbox = parser.get_bbox(crs="EPSG:2180")  # lub "EPSG:4326"
print(f"x: [{bbox.min_x:.2f}, {bbox.max_x:.2f}]")
print(f"y: [{bbox.min_y:.2f}, {bbox.max_y:.2f}]")

# Pobieranie arkusza przez godło → ASC (OpenData)
manager = DownloadManager(output_dir="./data")
path = manager.download_sheet("N-34-130-D-d-2-4")  # → .asc

# Pobieranie hierarchii arkuszy → ASC (OpenData)
paths = manager.download_hierarchy(
    godlo="N-34-130-D",
    target_scale="1:10000"
)  # → 64 plików .asc

# Pobieranie przez bbox → GeoTIFF (WCS)
bbox = BBox(min_x=450000, min_y=550000, max_x=460000, max_y=560000, crs="EPSG:2180")
path = manager.download_bbox(bbox, "my_area.tif")  # → .tif

# ===== Land Cover =====
from kartograf import LandCoverManager

lc = LandCoverManager()

# BDOT10k - przez godło
lc.download(godlo="N-34-130-D")

# BDOT10k - przez TERYT (powiat)
lc.download(teryt="1465")

# CORINE - przez godło
lc.set_provider("corine")
lc.download(godlo="N-34-130-D", year=2018)
```

## Funkcjonalności

### NMT (Numeryczny Model Terenu)
- ✅ **Parser godeł** - Obsługa układów 1992 i 2000, skal 1:1 000 000 - 1:10 000
- ✅ **Bounding box** - Obliczanie współrzędnych arkusza (EPSG:2180, EPSG:4326)
- ✅ **Hierarchia arkuszy** - Automatyczne określanie arkuszy nadrzędnych i podrzędnych
- ✅ **Pobieranie NMT** - Z retry logic i progress tracking
- ✅ **Organizacja plików** - Automatyczna struktura katalogów
- ✅ **Formaty** - GeoTIFF, PNG, JPEG (WCS), ASC (OpenData)

### Land Cover (Pokrycie Terenu)
- ✅ **BDOT10k** - Polska baza wektorowa (GUGiK), szczegółowość 1:10 000
- ✅ **CORINE Land Cover** - Europejska klasyfikacja (Copernicus), 44 klasy
- ✅ **Metody selekcji** - TERYT (powiat), bbox, godło arkusza
- ✅ **Formaty** - GeoPackage, Shapefile, GML

## Dokumentacja

- [SCOPE.md](docs/SCOPE.md) - Zakres projektu (co JEST i czego NIE MA)
- [PRD.md](docs/PRD.md) - Product Requirements Document
- [IMPLEMENTATION_PROMPT.md](docs/IMPLEMENTATION_PROMPT.md) - Instrukcje dla AI assistants
- [DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md) - Standardy kodowania
- [PROGRESS.md](docs/PROGRESS.md) - Plan i status implementacji
- [CHANGELOG.md](docs/CHANGELOG.md) - Historia zmian

## Wymagania

- Python 3.12+
- requests >= 2.31.0
- pyproj >= 3.6.0

## Struktura Projektu

```
Kartograf/
├── kartograf/           # Kod źródłowy
│   ├── core/            # Parser godeł
│   ├── providers/       # Providery danych (GUGiK, BDOT10k, CORINE)
│   ├── download/        # Download management (NMT)
│   ├── landcover/       # Land Cover management
│   └── cli/             # CLI interface
├── tests/               # Testy (283)
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
black kartograf/ tests/

# Linting
flake8 kartograf/ tests/ --max-line-length=88
```

## Licencja

MIT

## Autor

Piotr Daldek

## Status

**Wersja 0.3.0-dev** - Dodano funkcjonalność Land Cover (BDOT10k, CORINE). Zobacz [CHANGELOG.md](docs/CHANGELOG.md) dla szczegółów
