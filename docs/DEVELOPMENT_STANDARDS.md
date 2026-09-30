# Standardy deweloperskie — Kartograf

**Wersja:** 2.3
**Data:** 2026-09-30
**Status:** Obowiazujacy
**Zrodlo:** Zunifikowane standardy workspace (`shared/standards/DEVELOPMENT_STANDARDS.md` — repozytorium zewnetrzne, nieobecne w tym workspace)

> **Nota 2.1 (2026-08-18):** aktualizacja do stanu po etapie 1 (v0.7.0-dev) —
> struktura projektu (sekcja 7.1), komenda mypy bez `--strict` + baseline
> (sekcja 8.3), przyklad nazewnictwa plikow (sekcja 4.1).
>
> **Nota 2.2 (2026-09-29, audyt dokumentacji):** komendy testow offline
> z `-m "not live"` (sekcje 6.3, 10.1, 15), liczba testow i `download/`
> w strukturze (7.1), `NoCoverageError` i wyjatki transformacji w hierarchii
> (11.1), odnotowany rozjazd jezyka docstringow/commitow z praktyka (9.4).
>
> **Nota 2.3 (2026-09-30):** cache PL zapisuje rekord skorowidza lub
> potwierdzony brak pokrycia (`get_record/set_record`, TTL 7 dni); uszkodzenie
> odpowiedzi albo awaria warstwy to `DownloadError`, nie wpis negatywny.
> `GridMismatchError(ValidationError)` chroni wartości 1:1 wycinka w EPSG:2180;
> testy sieciowe `live` (16) są poza bramką offline.

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
| Pliki .py | snake_case | `sheet_parser.py`, `gugik_nmpt.py` |
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
# Z aktywnym venv (offline — domyslna brama)
pytest tests/ -v --tb=short -m "not live"

# Jawne wskazanie interpretera (bez aktywacji)
.venv/bin/python -m pytest tests/ -v -m "not live"

# Testy sieciowe (8, WMS GUGiK) — tylko swiadomie
.venv/bin/python -m pytest tests/ -m live
```

`pyproject.toml` nie odfiltrowuje testow `live` (`addopts` bez `-m`), wiec
komenda bez `-m "not live"` wychodzi w siec.

---

## 7. Python — struktura projektu

### 7.1 Kartograf — flat layout

```
Kartograf/
├── kartograf/               # kod zrodlowy (flat layout)
│   ├── __init__.py          # public API exports
│   ├── exceptions.py        # hierarchia wyjatkow
│   ├── core/                # parsery godel (PL-1992, PL-2000, CZ TM33), rejestr systemow, BBox, geometry
│   ├── sources/             # deskryptory zrodel danych (registry PL/CZ/EU/GLOBAL, sidecar metadata)
│   ├── transform/           # transformacje CRS (przypiete operacje pyproj)
│   ├── transport/           # wspolny transport (http: atomic download + retry; mosaic: merge kafli)
│   ├── providers/           # providery danych
│   │   ├── base.py          # BaseProvider, LandCoverProvider
│   │   ├── pl/              # GUGiK: gugik.py, gugik_nmpt.py, gugik_orto.py, gugik_laz.py, skorowidz.py, bdot10k.py
│   │   ├── cuzk/            # CUZK (Czechy): client.py, sheets.py, dmr.py
│   │   ├── corine.py        # CORINE z Copernicus
│   │   └── soilgrids.py     # SoilGrids z ISRIC
│   ├── cache/               # MetadataCache (SQLite WAL, record_cache 7d + sheet_cache 30d)
│   ├── download/            # DownloadManager (NMT/NMPT/Orto), FileStorage, wycinek PL (cutout.py, ADR-027)
│   ├── landcover/           # land cover management
│   ├── hydrology/           # obliczenia hydrologiczne (HSG)
│   ├── auth/                # autentykacja CLMS (Auth Proxy)
│   └── cli/                 # CLI podzielone per komenda: _parser.py (argparse),
│                            # parse_cmd.py, download_cmd.py, landcover_cmd.py,
│                            # soilgrids_cmd.py, cache_cmd.py + fasada commands.py
├── tests/                   # conftest.py + fixtures/ (2057 testow offline + 16 `live`, stan 2026-09-30)
├── docs/                    # dokumentacja
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .editorconfig
└── .gitignore
```

Zrodlem prawdy dla aktualnej struktury modulow jest sekcja "Struktura modulow"
w `CLAUDE.md` (korzen repo).

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
mypy kartograf/
```

Projekt utrzymuje baseline mypy (32 przedistniejace bledy, bez `--strict`;
stan po audycie 0.7.0 — baseline spadl z 33 do 32 po usunieciu jednego
bledu `no-redef` w `cli/download_cmd.py`, zadanie 16 planu audytu).
Nowy kod nie moze dodawac nowych bledow do tego dlugu.

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

**Odstepstwo praktyki (stan 2026-09-29, do rozstrzygniecia przez wlasciciela
projektu):** kod od etapu 0 ma docstringi i komentarze takze po polsku bez
polskich znakow (w calosci m.in. `download/cutout.py`, `transport/mosaic.py`,
wiekszosc `cli/download_cmd.py`), a commity sa po polsku (Conventional
Commits). Nowe publiczne API wycinka (`download_pl_cutout` i kroki) ma
docstringi bez pelnego kompletu sekcji NumPy. Do decyzji: ujednolicic
standard z praktyka albo praktyke ze standardem.

---

## 10. Python — testowanie

### 10.1 Progi pokrycia

| Warstwa | Wymagane pokrycie |
|---------|-------------------|
| Core (parser, providers, manager) | **>= 80%** |
| CLI, utility, formatowanie | **>= 60%** |

```bash
pytest tests/ -m "not live" --cov=kartograf --cov-report=html --cov-fail-under=60
```

Powyzsza komenda (oraz `[tool.coverage.report] fail_under = 60` w
`pyproject.toml`) egzekwuje **wylacznie prog globalny** (60%). `pytest-cov`/
`coverage.py` nie ma wbudowanego progu per-warstwa ani per-plik — prog
**>= 80%** dla warstwy core (parser, providers, manager) jest dzis
kontrolowany recznie, druga komenda liczaca pokrycie tylko dla tych
katalogow (na tych samych danych `.coverage`, bez ponownego uruchamiania
testow):

```bash
pytest tests/ --cov=kartograf --cov-report=term -q -p no:cacheprovider -m "not live"
coverage report --include='kartograf/core/*,kartograf/providers/*,kartograf/download/*' --fail-under=80
```

**Znane odstepstwa (0.7.0)** — moduly warstwy core/providers ponizej progu
80%, zidentyfikowane `pytest tests/ -q -p no:cacheprovider --cov=kartograf
--cov-report=term-missing | grep -E '^kartograf/.* [0-7][0-9]%'` (kanoniczny
przebieg audytu 0.7.0: 1716 testow, 93% pokrycia calosci pakietu):
- `kartograf/providers/corine.py` — 54%: tor CLMS/OAuth2
  (`_exchange_token`, `_download_via_clms_direct`, `_poll_clms_task`) bez
  testow, dlug sprzed 0.6.0; backlog 0.7.1 (A8-3).
- `kartograf/providers/base.py` — 73%: domyslne/abstrakcyjne metody `ABC`
  (m.in. `download_by_admin_unit`, fallback `NotImplementedError`) sa
  nadpisywane przez kazdego konkretnego providera — sciezka bazowa nie
  jest cwiczona bezposrednio w testach warstwy bazowej.

Progi warstwowe nie sa dzis egzekwowane automatycznie w CI (workflow CI
nie istnieje w tym repo) — do wprowadzenia razem z zadaniem CI (backlog
A8-7, patrz `docs/PROGRESS.md`).

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

**Izolacja sieci:** `tests/conftest.py` blokuje kazde polaczenie spoza
loopback (`_block_network`, autouse) — testy jednostkowe MUSZA byc offline;
siec realna wymaga jawnego markera `@pytest.mark.live` (domyslnie
odfiltrowanego przez `-m "not live"`), a GetCapabilities WMS jest domyslnie
serwowane offline przez stub (`_offline_wms_layers`, autouse), ktory testy
cwiczace sam `_fetch_wms_layers` jawnie wylaczaja markerem
`@pytest.mark.real_wms_layers`.

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

class NoCoverageError(DownloadError):
    """Source has no data for the sheet (all index layers answered);
    the PL cutout maps it to nodata (R5)."""
    pass

# kartograf/transform/crs.py: TransformError(KartografError),
# TransformUnavailableError(TransformError) — z polem remedy
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
| GUGiK NMT / NMPT | 30s |
| GUGiK Ortofoto | 60s |
| GUGiK LAZ — discovery (WFS) | 30s |
| GUGiK LAZ — pobieranie kafli | 60s |
| BDOT10k (wszystkie `download_by_*`, w tym `_get_teryt_for_point`) | 120s |
| CORINE — bbox/godlo | 60s |
| CORINE — TERYT | 120s |
| CUZK (DMR 5G/4G) | 60s |
| SoilGrids — bbox/HSG | 120s |
| SoilGrids — przez godlo | 60s |
| HSG (kalkulacja) | 120s |
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
- [ ] Testy przechodza (`pytest tests/ -v -m "not live"`; testy `live` — 16
      testow sieciowych — tylko swiadomie: `pytest tests/ -m live`)
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

**Wersja dokumentu:** 2.3
**Data ostatniej aktualizacji:** 2026-09-30
**Zrodlo:** `shared/standards/DEVELOPMENT_STANDARDS.md` v1.0 (repozytorium zewnetrzne, nieobecne w tym workspace)

*Odstepstwa od tych standardow wymagaja uzasadnienia w `CLAUDE.md` projektu.*
