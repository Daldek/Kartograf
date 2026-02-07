# Standardy deweloperskie — Kartograf

**Wersja:** 2.0
**Data:** 2026-02-03
**Status:** Obowiazujacy
**Zrodlo:** Zunifikowane standardy workspace (`shared/standards/DEVELOPMENT_STANDARDS.md`)

---

## Spis tresci

1. [Git Workflow](#1-git-workflow)
2. [Conventional Commits](#2-conventional-commits)
3. [Code Review](#3-code-review)
4. [Python — nazewnictwo](#4-python--nazewnictwo)
5. [Python — formatowanie (Ruff)](#5-python--formatowanie-ruff)
6. [Python — srodowisko wirtualne](#6-python--srodowisko-wirtualne)
7. [Python — struktura projektu](#7-python--struktura-projektu)
8. [Python — type hints](#8-python--type-hints)
9. [Python — docstrings](#9-python--docstrings)
10. [Python — testowanie](#10-python--testowanie)
11. [Python — obsluga bledow](#11-python--obsluga-bledow)
12. [Python — logging](#12-python--logging)
13. [Python — wydajnosc](#13-python--wydajnosc)
14. [Bezpieczenstwo](#14-bezpieczenstwo)
15. [Pre-merge checklist](#15-pre-merge-checklist)

---

## 1. Git Workflow

### 1.1 Branching (Git Flow)

```
main              # Stabilna wersja (tylko merge z develop)
develop           # Aktywny rozwoj (DOMYSLNA GALAZ ROBOCZA)
feature/<nazwa>   # Nowe funkcjonalnosci
fix/<nazwa>       # Poprawki bledow
hotfix/<nazwa>    # Pilne poprawki produkcyjne (branch z main)
```

**Zasady:**
- `main` — tylko stabilny, przetestowany kod
- `develop` — integracja feature'ow, domyslna galaz robocza
- `feature/*` — branch z `develop`, merge do `develop`
- `fix/*` — branch z `develop`, merge do `develop`
- `hotfix/*` — branch z `main`, merge do `main` i `develop`

### 1.2 Tagowanie

Tagi `v<X.Y.Z>` (SemVer) przy wydaniach:

```bash
git tag -a v0.4.0 -m "Release v0.4.0: NMPT, Ortofotomapa, nowa struktura storage"
git push origin v0.4.0
```

Checkpointy robocze (CP) sa sledzone tylko w `docs/PROGRESS.md`, bez tagow Git.

### 1.3 Zasady commitow

- Kazda logiczna zmiana = osobny commit
- Commituj czesto, malymi porcjami
- Latwiejsze code review i rollback

---

## 2. Conventional Commits

### 2.1 Format

```
<type>(<scope>): <opis>

<body>           # opcjonalny

<footer>         # opcjonalny (np. Closes #12)
```

### 2.2 Typy

| Typ | Kiedy |
|-----|-------|
| `feat` | Nowa funkcjonalnosc |
| `fix` | Poprawka bledu |
| `docs` | Tylko dokumentacja |
| `test` | Dodanie/zmiana testow |
| `refactor` | Refaktoryzacja (bez zmian funkcjonalnosci) |
| `perf` | Optymalizacja wydajnosci |
| `style` | Formatowanie (nie wplywa na logike) |
| `chore` | Config, dependencies, build |

### 2.3 Scope — specyficzne dla Kartograf

```bash
feat(parser): add support for 2000 coordinate system
fix(download): handle timeout in retry logic
feat(landcover): add BDOT10k provider
feat(soilgrids): add WCS download for soil data
feat(hsg): implement USDA texture classification
fix(auth): fix proxy token refresh
docs(readme): update installation instructions
test(parser): add edge case tests for hierarchy
refactor(providers): extract common validation
chore(deps): update requests to 2.32.0
```

---

## 3. Code Review

### 3.1 Proces

```
1. Deweloper tworzy PR
2. Automated checks:
   ├─ Formatowanie (ruff format --check)
   ├─ Linting (ruff check)
   ├─ Type checking (mypy)
   └─ Testy (pytest --cov)
3. Manual review
4. Poprawki jesli potrzeba
5. Approval → Merge
```

### 3.2 Co sprawdza reviewer

- **Poprawnosc** — czy kod dziala zgodnie z wymaganiami?
- **Testy** — czy pokrywaja nowa logike i edge cases?
- **Standardy** — zgodnosc z tym dokumentem
- **Czytelnosc** — czy kod jest zrozumialy bez nadmiernych komentarzy?
- **Bezpieczenstwo** — brak hardcoded secrets, walidacja inputu

### 3.3 Wymagania PR

- Wszystkie testy przechodza
- Pokrycie kodu w normie (patrz sekcja 10)
- Brak bledow ruff / mypy
- Minimum 1 approval
- Brak konfliktow z target branch
- Dokumentacja zaktualizowana (jesli potrzeba)

---

## 4. Python — nazewnictwo

### 4.1 Konwencje

| Element | Konwencja | Przyklad |
|---------|-----------|----------|
| Zmienne | snake_case + jednostka | `area_km2`, `elevation_m` |
| Funkcje | snake_case + czasownik | `download_sheet()`, `parse_godlo()` |
| Klasy | PascalCase | `SheetParser`, `GugikProvider` |
| Stale | UPPER_SNAKE_CASE | `DEFAULT_FORMAT`, `MAX_RETRIES` |
| Pliki .py | snake_case | `sheet_parser.py`, `landcover_base.py` |
| Protected | `_prefix` | `self._cache` |
| Private | `__prefix` | `self.__internal_state` |

### 4.2 Jednostki w nazwach zmiennych

**ZAWSZE** dodawaj jednostke do nazwy zmiennej fizycznej:

```python
# GOOD
area_km2 = 45.3
elevation_m = 250.0
resolution_m = 1  # 1m or 5m
bbox_coords = [50.0, 19.0, 51.0, 20.0]
timeout_s = 30

# BAD — unit ambiguity
area = 45.3       # km2 or m2?
resolution = 1    # meters or pixels?
```

### 4.3 Prefiksy semantyczne

| Prefiks | Znaczenie | Przyklad w Kartograf |
|---------|-----------|----------------------|
| `download_*` | Pobranie pliku / archiwum | `download_sheet()`, `download_bbox()` |
| `parse_*` | Parsowanie danych | `parse_godlo()` |
| `calculate_*` | Obliczenie wyniku | `calculate_hsg_by_godlo()` |
| `get_*` | Pobranie atrybutu / danych | `get_parent()`, `get_children()` |
| `list_*` | Listowanie zasobow | `list_sources()`, `list_layers()` |
| `classify_*` | Klasyfikacja | `classify_usda_texture()` |

---

## 5. Python — formatowanie (Ruff)

### 5.1 Konfiguracja

```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"
```

### 5.2 Komendy

```bash
# Formatowanie
ruff format kartograf/ tests/

# Sprawdzenie (bez zmian)
ruff format --check kartograf/ tests/

# Linting
ruff check kartograf/ tests/

# Linting z auto-fix
ruff check --fix kartograf/ tests/
```

### 5.3 Zasady formatowania

```python
# Line length: 88 characters
# Indentation: 4 spaces (NEVER tabs)

# GOOD — multi-line when exceeds 88 chars
def download_hierarchy(
    godlo: str,
    target_scale: str,
    skip_existing: bool = True,
    on_progress: ProgressCallback | None = None,
) -> list[Path]:
    pass

# BAD — too long
def download_hierarchy(godlo: str, target_scale: str, skip_existing: bool = True) -> list[Path]:
    pass
```

### 5.4 Importy

```python
# Order: stdlib → third-party → local
# Alphabetical within groups
# Blank lines between groups
# Ruff sorts automatically (rule I)

import logging
from pathlib import Path

import requests
from pyproj import Transformer

from kartograf.core.sheet_parser import BBox, SheetParser
from kartograf.exceptions import DownloadError
```

---

## 6. Python — srodowisko wirtualne

### 6.1 Dwa konteksty pracy

| Kontekst | Srodowisko | Lokalizacja |
|----------|------------|-------------|
| Deweloper (czlowiek) | venv w projekcie | `Kartograf/.venv/` |
| Agent AI (Claude Code) | Docker container | `/workspace/` mount |

### 6.2 Deweloper — lokalne venv

```bash
cd ~/workspace/projects/Kartograf
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 6.3 Uruchamianie testow

```bash
# Z aktywnym venv
pytest tests/ -v --tb=short

# Jawne wskazanie interpretera (bez aktywacji)
.venv/bin/python -m pytest tests/ -v
```

---

## 7. Python — struktura projektu

### 7.1 Kartograf — flat layout

```
Kartograf/
├── kartograf/               # kod zrodlowy (flat layout)
│   ├── __init__.py          # public API exports
│   ├── exceptions.py        # hierarchia wyjatkow
│   ├── core/                # parser godel, BBox
│   ├── providers/           # providery danych (GUGiK NMT/NMPT/Orto, BDOT10k, CORINE, SoilGrids)
│   ├── download/            # download management (NMT/NMPT/Orto)
│   ├── landcover/           # land cover management
│   ├── hydrology/           # obliczenia hydrologiczne (HSG)
│   ├── auth/                # autentykacja CLMS (Auth Proxy)
│   └── cli/                 # interfejs CLI
├── tests/                   # testy (574)
│   ├── conftest.py
│   ├── test_sheet_parser.py
│   ├── test_gugik_provider.py
│   ├── test_gugik_nmpt.py
│   ├── test_gugik_orto.py
│   ├── test_download_manager.py
│   ├── test_landcover.py
│   ├── test_soilgrids.py
│   ├── test_hsg.py
│   ├── test_cli.py
│   └── test_integration.py
├── docs/                    # dokumentacja
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .editorconfig
└── .gitignore
```

### 7.2 Konfiguracja w pyproject.toml

Wszystkie narzedzia konfiguruj w jednym pliku `pyproject.toml`.
Nie tworz osobnych plikow konfiguracyjnych (`setup.cfg`, `tox.ini`, `.flake8`, itp.).

---

## 8. Python — type hints

### 8.1 Python 3.12+ style

```python
# GOOD — modern syntax
def download_sheet(godlo: str) -> Path:
    pass

def get_provider(name: str | None = None) -> LandCoverProvider | None:
    pass

def download_hierarchy(
    godlo: str,
    target_scale: str,
    on_progress: ProgressCallback | None = None,
) -> list[Path]:
    pass

# BAD — legacy typing
from typing import List, Optional, Union

def get_provider(name: Optional[str] = None) -> Optional[LandCoverProvider]:
    pass
```

### 8.2 Wymagane wszedzie

Type hints sa wymagane dla:
- Wszystkich argumentow funkcji publicznych
- Wartosci zwracanych
- Atrybutow klas (dataclass)

### 8.3 Type checking

```bash
mypy kartograf/ --strict
```

---

## 9. Python — docstrings

### 9.1 Styl: NumPy, jezyk: angielski

```python
def download_sheet(
    godlo: str,
    output_dir: str = "./data",
) -> Path:
    """
    Download NMT sheet from GUGiK OpenData.

    Parameters
    ----------
    godlo : str
        Sheet identifier (e.g. "N-34-130-D-d-2-4").
    output_dir : str, optional
        Output directory, by default "./data".

    Returns
    -------
    Path
        Full path to the downloaded file.

    Raises
    ------
    DownloadError
        If download fails after retries.

    Examples
    --------
    >>> manager = DownloadManager()
    >>> path = manager.download_sheet("N-34-130-D-d-2-4")
    """
    pass
```

### 9.2 Klasy

```python
class SheetParser:
    """
    Parser for Polish topographic map sheet identifiers (godlo).

    Supports scales from 1:1,000,000 to 1:10,000 in "1992" and "2000"
    coordinate system layouts.

    Parameters
    ----------
    godlo : str
        Sheet identifier (e.g. "N-34-130-D-d-2-4").
    uklad : str or None, optional
        Coordinate system layout ("1992" or "2000").

    Examples
    --------
    >>> parser = SheetParser("N-34-130-D-d-2-4")
    >>> parser.scale
    '1:10000'
    """
    pass
```

### 9.3 Komentarze inline

```python
# GOOD — explains "why", not "what"
# 1:500k to 1:200k division produces 36 sheets (not 4!)
children = self._get_children_from_500k()

# EVRF2007 is the current standard; KRON86 is legacy
default_crs = "EVRF2007"

# BAD — states the obvious
# Set timeout to 30
timeout = 30
```

### 9.4 Jezyk

- **Pliki .md** — po polsku
- **Docstrings i komentarze w kodzie** — po angielsku
- **Commit messages** — po angielsku

---

## 10. Python — testowanie

### 10.1 Progi pokrycia

| Warstwa | Wymagane pokrycie |
|---------|-------------------|
| Core (parser, providers, manager) | **>= 80%** |
| CLI, utility, formatowanie | **>= 60%** |

```bash
pytest tests/ --cov=kartograf --cov-report=html --cov-fail-under=60
```

### 10.2 Nazewnictwo testow

```python
# Pattern: test_<function>_<scenario>[_<expected>]

def test_parse_valid_godlo_10k():
    """Test parsing 1:10000 scale sheet identifier."""
    pass

def test_download_with_retry_on_timeout():
    """Test download retries on HTTP timeout."""
    pass

def test_parse_invalid_godlo_raises():
    """Test that invalid godlo raises ValueError."""
    pass
```

### 10.3 AAA Pattern (Arrange-Act-Assert)

```python
def test_sheet_hierarchy_up():
    # Arrange
    parser = SheetParser("N-34-130-D-d-2-4")

    # Act
    hierarchy = parser.get_hierarchy_up()

    # Assert
    assert len(hierarchy) == 7
    assert hierarchy[0].scale == "1:10000"
    assert hierarchy[-1].scale == "1:1000000"
```

### 10.4 Fixtures i mocking

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def sample_godlo():
    """Fixture with sample sheet identifier."""
    return "N-34-130-D-d-2-4"

def test_download_with_mock_http(sample_godlo):
    """Test download using mocked HTTP response."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = Mock(status_code=200, content=b"data")
        result = provider.download(sample_godlo, Path("/tmp/test.asc"))
        assert result.exists()
```

---

## 11. Python — obsluga bledow

### 11.1 Hierarchia wyjatkow Kartograf

```python
# kartograf/exceptions.py

class KartografError(Exception):
    """Base exception for Kartograf."""
    pass

class ParseError(KartografError):
    """Invalid sheet identifier (godlo)."""
    pass

class ValidationError(KartografError):
    """Invalid input parameter."""
    pass

class DownloadError(KartografError):
    """Download or network error."""
    pass
```

### 11.2 Walidacja na wejsciu

```python
def download_sheet(godlo: str) -> Path:
    """Download NMT sheet."""
    if not godlo or not godlo.strip():
        raise ValidationError("Godlo cannot be empty")

    parser = SheetParser(godlo)  # raises ParseError if invalid
    ...
```

### 11.3 Raise from

```python
# GOOD — preserve exception chain
try:
    response = requests.get(url, timeout=30)
except requests.RequestException as e:
    raise DownloadError(f"Failed to download {godlo}: {e}") from e

# BAD — loses original traceback
except requests.RequestException as e:
    raise DownloadError(f"Failed: {e}")
```

---

## 12. Python — logging

### 12.1 Konfiguracja

```python
import logging

logger = logging.getLogger(__name__)
```

### 12.2 Poziomy logowania

```python
# DEBUG — development only
logger.debug("Parsing sheet: %s", godlo)

# INFO — normal operations
logger.info("Downloaded %s successfully", filename)

# WARNING — unusual but not an error
logger.warning("Retry %d/%d for %s", attempt, max_retries, url)

# ERROR — failure that doesn't crash the app
logger.error("Failed to fetch data: %s", exc)
```

**Uwaga:** Uzywaj `%s` formatting w loggerze (lazy evaluation), nie f-stringow.

---

## 13. Python — wydajnosc

### 13.1 Priorytet

```
Poprawnosc > Czytelnosc > Wydajnosc
```

### 13.2 HTTP requests

```python
# GOOD — reuse session for multiple requests
session = requests.Session()
for godlo in godla:
    response = session.get(url, timeout=30)

# BAD — new connection each time
for godlo in godla:
    response = requests.get(url)
```

### 13.3 Duze pliki — streaming

```python
def download_large_file(url: str, filepath: Path) -> None:
    """Download large file with streaming."""
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
```

### 13.4 Limity czasowe Kartograf

| Operacja | Timeout |
|----------|---------|
| GUGiK (NMT) | 30s |
| Land Cover (BDOT10k, CORINE) | 60s |
| SoilGrids (ISRIC WCS) | 60s |
| Retry: max 3 proby, exponential backoff | — |

---

## 14. Bezpieczenstwo

### 14.1 NIGDY

```python
# NEVER hardcode secrets
API_KEY = "sk-1234567890"  # NEVER!

# NEVER commit .env
# .gitignore must contain: .env, *.pem, *.key

# NEVER eval() on user input
eval(user_input)  # NEVER!
```

### 14.2 ZAWSZE

```python
import os

# ALWAYS use environment variables for secrets
client_id = os.getenv("CLMS_CLIENT_ID")

# ALWAYS validate input at system boundaries
if not godlo or not godlo.strip():
    raise ValidationError("Godlo cannot be empty")

# ALWAYS set timeouts for HTTP requests
response = requests.get(url, timeout=30)
```

### 14.3 Auth Proxy — specyficzne dla Kartograf

CLMS credentials sa izolowane w osobnym procesie (Auth Proxy):

```
CorineProvider → localhost HTTP → AuthProxy (subprocess) → Keychain → CLMS API
```

- Credentials (klucz prywatny RSA) nigdy nie opuszczaja procesu proxy
- Glowna aplikacja nigdy nie widzi credentials
- Tylko odpowiedzi API sa przekazywane do aplikacji

---

## 15. Pre-merge checklist

```markdown
- [ ] Testy przechodza (`pytest tests/ -v`)
- [ ] Pokrycie kodu w normie (80% core / 60% utility)
- [ ] Formatowanie OK (`ruff format --check kartograf/ tests/`)
- [ ] Linting OK (`ruff check kartograf/ tests/`)
- [ ] Type hints OK (`mypy kartograf/`)
- [ ] Docstrings dla publicznych funkcji/klas
- [ ] Brak hardcoded secrets
- [ ] Dokumentacja zaktualizowana (jesli potrzeba)
- [ ] PROGRESS.md / CHANGELOG.md zaktualizowany
- [ ] Minimum 1 approval
- [ ] Brak konfliktow z target branch
```

---

**Wersja dokumentu:** 2.0
**Data ostatniej aktualizacji:** 2026-02-03
**Zrodlo:** `shared/standards/DEVELOPMENT_STANDARDS.md` v1.0

*Odstepstwa od tych standardow wymagaja uzasadnienia w `CLAUDE.md` projektu.*
