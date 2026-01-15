# Kartograf

Narzędzie do automatycznego pobierania danych NMT (Numeryczny Model Terenu) z zasobów GUGiK dla Polski.

## Szybki Start

### Instalacja

```bash
# Klonowanie repozytorium
git clone https://github.com/yourusername/kartograf.git
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
from kartograf import SheetParser, DownloadManager

# Parsowanie godła
parser = SheetParser("N-34-130-D-d-2-4", uklad="1992")
print(parser.scale)  # "1:10000"

# Pobieranie danych
manager = DownloadManager(output_dir="./data")
paths = manager.download_hierarchy(
    godlo="N-34-130-D",
    target_scale="1:10000",
    format="GTiff"
)
```

## Funkcjonalności

- ✅ **Parser godeł** - Obsługa układów 1992 i 2000, skal 1:1 000 000 - 1:10 000
- ✅ **Hierarchia arkuszy** - Automatyczne określanie arkuszy nadrzędnych i podrzędnych
- ✅ **Pobieranie NMT** - Z retry logic i progress tracking
- ✅ **Organizacja plików** - Automatyczna struktura katalogów
- ✅ **Formaty** - GeoTIFF, Arc/Info ASCII Grid, XYZ

## Dokumentacja

- [SCOPE.md](docs/SCOPE.md) - Zakres projektu (co JEST i czego NIE MA)
- [PRD.md](docs/PRD.md) - Product Requirements Document
- [IMPLEMENTATION_PROMPT.md](IMPLEMENTATION_PROMPT.md) - Instrukcje dla AI assistants
- [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md) - Standardy kodowania

## Wymagania

- Python 3.12+
- requests >= 2.31.0

## Struktura Projektu

```
kartograf/
├── src/kartograf/       # Kod źródłowy
│   ├── core/            # Logika główna
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
pytest tests/ --cov=src/kartograf --cov-report=html

# Formatowanie
black src/ tests/

# Linting
flake8 src/ tests/ --max-line-length=88
```

## Licencja

MIT

## Autor

Piotr Daldek

## Status

🚧 **MVP w budowie** - Zobacz [SCOPE.md](docs/SCOPE.md) dla szczegółów
