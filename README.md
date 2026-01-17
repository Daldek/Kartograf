# Kartograf

Narzędzie do automatycznego pobierania danych NMT (Numeryczny Model Terenu) z zasobów GUGiK dla Polski.

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

# Pobieranie pojedynczego arkusza
kartograf download N-34-130-D-d-2-4 --format GTiff

# Pobieranie hierarchii
kartograf download N-34-130-D --scale 1:10000 --output ./data
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
```

## Funkcjonalności

- ✅ **Parser godeł** - Obsługa układów 1992 i 2000, skal 1:1 000 000 - 1:10 000
- ✅ **Bounding box** - Obliczanie współrzędnych arkusza (EPSG:2180, EPSG:4326)
- ✅ **Hierarchia arkuszy** - Automatyczne określanie arkuszy nadrzędnych i podrzędnych
- ✅ **Pobieranie NMT** - Z retry logic i progress tracking
- ✅ **Organizacja plików** - Automatyczna struktura katalogów
- ✅ **Formaty** - GeoTIFF, PNG, JPEG (WCS), ASC (OpenData)

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
│   ├── providers/       # Providery danych (GUGiK)
│   ├── download/        # Download management
│   └── cli/             # CLI interface
├── tests/               # Testy
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

**Wersja 0.2.0** - Dostosowano do nowego API GUGiK WCS. Zobacz [CHANGELOG.md](docs/CHANGELOG.md) dla szczegółów
