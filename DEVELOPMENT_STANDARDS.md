# DEVELOPMENT_STANDARDS.md - Standardy Deweloperskie
## Kartograf - Narzędzie do Pobierania Danych NMT

**Wersja:** 1.0  
**Data:** 2026-01-15  
**Status:** Obowiązujący

---

## 1. Wprowadzenie

Ten dokument definiuje **wszystkie standardy deweloperskie** dla projektu Kartograf:
- 📝 Konwencje nazewnictwa i formatowania
- ✅ Zasady testowania i jakości kodu
- 🔀 Git workflow i code review
- 📚 Dokumentacja

**Wszyscy członkowie zespołu muszą przestrzegać tych standardów.**

---

## CZĘŚĆ I: KONWENCJE KODOWANIA

---

## 2. Nazewnictwo

### 2.1 Python

#### Zmienne i Funkcje
```python
# DOBRZE - snake_case + jednostka gdzie potrzeba
area_km2 = 45.3
sheet_count = 256
download_path = "/path/to/data"

def parse_godlo(godlo_str: str) -> SheetInfo:
    pass

def download_sheet(godlo: str, format: str) -> str:
    pass

# ŹLE
areaKm2 = 45.3  # camelCase
a = 45.3  # nieopisowe
def ParseGodlo(godlo):  # PascalCase
    pass
```

#### Klasy i Stałe
```python
# DOBRZE - PascalCase dla klas
class SheetParser:
    pass

class GugikClient:
    pass

class DownloadManager:
    pass

# DOBRZE - UPPER_SNAKE_CASE dla stałych
DEFAULT_FORMAT = "GTiff"
MAX_RETRIES = 3
BASE_URL = "https://mapy.geoportal.gov.pl"

# ŹLE
class sheet_parser:  # snake_case
    pass

max_retries = 3  # nie wygląda jak stała
```

#### Zmienne Prywatne
```python
class SheetParser:
    def __init__(self):
        self.godlo = ""             # publiczne
        self._components = {}        # protected (konwencja)
        self.__cache = {}            # private (name mangling)
```

---

### 2.2 Pliki i Katalogi

#### Struktura
```
kartograf/                 # kebab-case dla głównego folderu
├── src/
│   └── kartograf/        # snake_case
│       ├── core/
│       │   ├── sheet_parser.py
│       │   └── hierarchy.py
│       ├── providers/
│       │   ├── base.py
│       │   └── gugik.py
│       ├── download/
│       │   ├── manager.py
│       │   └── storage.py
│       └── cli/
│           └── commands.py
├── tests/
│   ├── test_sheet_parser.py
│   └── test_gugik_client.py
└── docs/
```

#### Nazwy Plików
```
# Python - snake_case
sheet_parser.py
gugik_client.py
test_download_manager.py

# Dokumentacja - UPPERCASE lub kebab-case
README.md
SCOPE.md
architecture-diagram.png
```

---

### 2.3 Jednostki

**Dodawaj jednostkę do nazwy zmiennej gdy ma to sens:**

```python
# DOBRZE
area_km2 = 45.3
length_m = 8200
bbox_coords = [50.0, 19.0, 51.0, 20.0]

# ŹLE
area = 45.3      # km2 czy m2?
length = 8200    # m czy km?
```

---

## 3. Formatowanie Kodu

### 3.1 Python (PEP 8 + Black)

#### Długość Linii i Wcięcia
```python
# Maksymalnie 88 znaków (Black standard)
# 4 spacje (NIGDY tabulatory)

# DOBRZE
def download_sheets_for_hierarchy(
    godlo: str,
    target_scale: str,
    format: str = "GTiff"
) -> List[str]:
    pass

# ŹLE (> 88 znaków)
def download_sheets_for_hierarchy(godlo: str, target_scale: str, format: str = "GTiff") -> List[str]:
    pass
```

#### Importy
```python
# Kolejność: stdlib → third-party → local
# Alfabetycznie w każdej grupie
# Puste linie między grupami

import os
import sys
from typing import List, Optional, Dict

import requests
from dataclasses import dataclass

from kartograf.core.sheet_parser import SheetParser
from kartograf.providers.gugik import GugikClient
```

#### Spacje
```python
# DOBRZE
x = 5
result = function(a, b, c)
my_list = [1, 2, 3]
my_dict = {'key': 'value'}

if x > 0:
    pass

# ŹLE
x=5                        # brak spacji wokół =
result = function (a,b,c)  # spacja przed (, brak po przecinkach
my_list=[1,2,3]            # brak spacji
```

#### Docstrings (NumPy Style)
```python
def download_sheet(
    godlo: str,
    format: str = 'GTiff',
    output_dir: str = './data'
) -> str:
    """
    Pobiera plik NMT dla podanego godła arkusza.

    Parameters
    ----------
    godlo : str
        Godło arkusza mapy (np. "N-34-130-D-d-2-4")
    format : str, optional
        Format pliku: 'GTiff', 'AAIGrid', lub 'XYZ', domyślnie 'GTiff'
    output_dir : str, optional
        Katalog docelowy, domyślnie './data'

    Returns
    -------
    str
        Pełna ścieżka do pobranego pliku

    Raises
    ------
    ValueError
        Jeśli format jest nieobsługiwany
    DownloadError
        Jeśli pobieranie się nie powiodło

    Examples
    --------
    >>> path = download_sheet("N-34-130-D-d-2-4", format="GTiff")
    >>> print(path)
    './data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif'
    """
    pass
```

---

## 4. Testowanie

### 4.1 Pokrycie Kodu

```python
# Minimum 80% dla core logic
# pytest --cov=src/kartograf --cov-report=html

# Core modules (wymagane ≥ 80%):
# - sheet_parser.py
# - gugik.py
# - manager.py

# Utility modules (opcjonalne < 80%):
# - cli/commands.py
```

### 4.2 Struktura Testów

```python
# Nazwa pliku: test_<module_name>.py
# Nazwa funkcji: test_<function_name>_<scenario>

def test_parse_valid_godlo():
    """Test parsowania poprawnego godła."""
    parser = SheetParser("N-34-130-D")
    assert parser.scale == "1:100000"


def test_parse_invalid_godlo():
    """Test walidacji niepoprawnego godła."""
    with pytest.raises(ValueError):
        SheetParser("INVALID")


def test_download_with_retry():
    """Test pobierania z ponowną próbą po błędzie."""
    # Setup
    client = GugikClient()
    
    # Act
    with patch('requests.get', side_effect=[RequestException, Mock()]):
        result = client.download("N-34-130-D")
    
    # Assert
    assert result is not None
```

### 4.3 Fixtures i Mocking

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def sample_godlo():
    """Fixture z przykładowym godłem."""
    return "N-34-130-D-d-2-4"


@pytest.fixture
def mock_http_response():
    """Mock odpowiedzi HTTP."""
    response = Mock()
    response.status_code = 200
    response.content = b"mock_data"
    return response


def test_with_fixtures(sample_godlo, mock_http_response):
    """Test używający fixtures."""
    parser = SheetParser(sample_godlo)
    assert parser.godlo == "N-34-130-D-D-2-4"
```

---

## 5. Git Workflow

### 5.1 Conventional Commits

```bash
# Format: <type>(<scope>): <subject>

feat(parser): dodaj obsługę układu 2000
fix(download): napraw retry logic dla timeout
docs(readme): aktualizuj przykłady użycia
test(parser): dodaj testy dla hierarchii
refactor(core): wydziel walidację do osobnej funkcji
chore(deps): aktualizuj requests do 2.31.0

# Type:
# - feat: nowa funkcja
# - fix: naprawa błędu
# - docs: tylko dokumentacja
# - test: dodanie testów
# - refactor: refaktoryzacja bez zmian funkcjonalności
# - chore: zmiany w buildzie, dependencies, etc.
```

### 5.2 Branching Strategy

```
main (stable, tagged releases)
  ↑
develop (integration branch)
  ↑
feature/sheet-parser
feature/gugik-client
fix/download-retry
```

### 5.3 Pull Request Template

```markdown
## Opis
Krótki opis zmian (1-2 zdania)

## Typ zmian
- [ ] feat - nowa funkcja
- [ ] fix - naprawa błędu
- [ ] docs - dokumentacja
- [ ] test - testy
- [ ] refactor - refaktoryzacja

## Checklist
- [ ] Kod sformatowany (black)
- [ ] Linting przeszedł (flake8)
- [ ] Type hints dodane
- [ ] Docstrings dla public funkcji
- [ ] Testy napisane (pokrycie ≥ 80% dla core)
- [ ] Wszystkie testy przechodzą
- [ ] Dokumentacja zaktualizowana

## Związane Issue
Closes #XX
```

---

## 6. Code Review

### 6.1 Reviewer Checklist

**Sprawdź:**
- **Funkcjonalność:** Czy kod robi to co powinien?
- **Testy:** Czy są testy? Czy pokrywają edge cases?
- **Czytelność:** Czy kod jest zrozumiały?
- **Konwencje:** Zgodność z DEVELOPMENT_STANDARDS.md?
- **Dokumentacja:** Czy docstrings są kompletne?

### 6.2 Czas Odpowiedzi

- Standardowy PR: **24 godziny**
- Krytyczny PR: **4 godziny**

---

## 7. Bezpieczeństwo

### 7.1 NIGDY

```python
# ❌ NIGDY hardcode secrets
API_KEY = "secret-key"  # NIGDY!

# ❌ NIGDY commit .env
# Dodaj do .gitignore:
.env
.env.local
*.pem
*.key

# ❌ NIGDY eval() na user input
eval(user_input)  # NIGDY!
```

### 7.2 ZAWSZE

```python
# ✅ ZAWSZE zmienne środowiskowe
import os
API_KEY = os.getenv('GUGIK_API_KEY')

# ✅ ZAWSZE walidacja input
def parse_godlo(godlo: str) -> SheetParser:
    if not isinstance(godlo, str):
        raise TypeError("Godło musi być string")
    
    if not godlo.strip():
        raise ValueError("Godło nie może być puste")
    
    return SheetParser(godlo)

# ✅ ZAWSZE timeout dla requests
response = requests.get(url, timeout=30)
```

---

## 8. Wydajność

### 8.1 Priorytety

```
Poprawność > Czytelność > Wydajność
```

**Najpierw:** Zrób działające  
**Potem:** Zrób czytelne  
**Na końcu:** Zrób szybkie (jeśli potrzeba)

### 8.2 HTTP Requests

```python
# ✅ DOBRZE - używaj session dla multiple requests
import requests

session = requests.Session()
for godlo in godla:
    response = session.get(url)

# ❌ ŹLE - nowy connection dla każdego request
for godlo in godla:
    response = requests.get(url)  # Wolniejsze!
```

### 8.3 File I/O

```python
# ✅ DOBRZE - context manager
with open(filepath, 'wb') as f:
    f.write(content)

# ✅ DOBRZE - chunked download dla dużych plików
def download_large_file(url: str, filepath: str):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
```

### 8.4 Limity Czasowe

- Parsowanie godła: **< 0.1s**
- Pobieranie pojedynczego arkusza: **< 30s**
- Request timeout: **30s**

---

## 9. Logging

### 9.1 Log Levels

```python
import logging

logger = logging.getLogger(__name__)

# DEBUG - szczegóły debugowania (tylko development)
logger.debug(f"Parsing godlo: {godlo}")

# INFO - normalne operacje
logger.info(f"Downloaded {filename} successfully")

# WARNING - ostrzeżenia (nie błędy)
logger.warning(f"Retrying download after {retry_count} attempts")

# ERROR - błędy które nie przerywają działania
logger.error(f"Failed to download {godlo}: {e}")

# CRITICAL - błędy krytyczne
logger.critical(f"Configuration file not found")
```

### 9.2 Format Logów

```python
# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kartograf.log'),
        logging.StreamHandler()
    ]
)
```

---

## 10. Dokumentacja

### 10.1 Wymagana Dokumentacja

**Code-level:**
- ✅ Docstrings dla wszystkich public funkcji/klas
- ✅ Inline comments dla nieoczywistej logiki
- ✅ Type hints

**Project-level:**
- ✅ README.md z quick start
- ✅ docs/SCOPE.md
- ✅ docs/PRD.md
- ✅ CHANGELOG.md

### 10.2 README.md Template

```markdown
# Kartograf

## Instalacja
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

## Użycie

### Jako CLI
```bash
kartograf parse N-34-130-D-d-2-4
kartograf download N-34-130-D --scale 1:10000
```

### Jako biblioteka
```python
from kartograf import SheetParser, DownloadManager

parser = SheetParser("N-34-130-D")
manager = DownloadManager()
manager.download_hierarchy(parser, target_scale="1:10000")
```

## Testy
```bash
pytest tests/ --cov=src/kartograf
```
```

---

## 11. Pre-Merge Checklist

**Przed każdym merge sprawdź:**

```markdown
- [ ] Kod sformatowany (black)
- [ ] Brak linting errors (flake8 --max-line-length=88)
- [ ] Type hints dodane
- [ ] Docstrings dla public funkcji
- [ ] Testy napisane (pokrycie ≥ 80% dla core)
- [ ] Wszystkie testy przechodzą
- [ ] Dokumentacja zaktualizowana
- [ ] Brak hardcoded secrets
- [ ] Minimum 1 approval
- [ ] Brak konfliktów z target branch
```

---

## 12. Podsumowanie Kluczowych Standardów

| Aspekt | Standard | Przykład |
|--------|----------|----------|
| **Python zmienne** | snake_case | `sheet_count`, `godlo_str` |
| **Python funkcje** | snake_case + czasownik | `parse_godlo()`, `download_sheet()` |
| **Python klasy** | PascalCase | `SheetParser`, `GugikClient` |
| **Pliki Python** | snake_case | `sheet_parser.py` |
| **Stałe** | UPPER_SNAKE_CASE | `DEFAULT_FORMAT`, `MAX_RETRIES` |
| **Commits** | Conventional Commits | `feat(parser): add hierarchy` |
| **Testy** | Pokrycie ≥ 80% (core) | pytest --cov |
| **Długość linii** | Python: 88 | Black |
| **Code review** | Minimum 1 approval | - |

---

**Wersja dokumentu:** 1.0  
**Data ostatniej aktualizacji:** 2026-01-15  
**Status:** Obowiązujący dla wszystkich członków zespołu  

---

*Te standardy są obowiązkowe. Odstępstwa wymagają uzasadnienia i zatwierdzenia przez Tech Lead.*
