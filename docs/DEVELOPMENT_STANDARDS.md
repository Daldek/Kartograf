# Standardy deweloperskie — Kartograf

**Wersja:** 3.0
**Data:** 2026-10-08
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
> testy sieciowe `live` są poza bramką offline.
>
> **Nota 3.0 (2026-10-08, przeglad dokumentacji):** dokument jest glownym
> zrodlem konwencji i procesu pracy projektu. Przejete
> z usunietego `IMPLEMENTATION_PROMPT.md`: workflow, "Czego NIE robic",
> typowe zadania (15-17); z CLAUDE.md: srodowisko i zmienne srodowiskowe
> (6.1-6.2), komendy narzedziowe (6.3), pelne zasady katalog danych danych (6.4),
> workflow sesji (15), praca na `develop` (1.1). Fragmenty powielajace stan
> kodu (drzewo projektu 7.1, hierarchia wyjatkow 11.1, tabela timeoutow
> 13.4, liczby testow i pokrycia 10.1) zastapione regula i odsylaczem do
> zrodla prawdy; `CLMS_CREDENTIALS` zamiast nieistniejacej zmiennej (14).

---

## Spis tresci

1. [Git Workflow](#1-git-workflow)
2. [Conventional Commits](#2-conventional-commits)
3. [Code Review](#3-code-review)
4. [Python — nazewnictwo](#4-python--nazewnictwo)
5. [Python — formatowanie (Ruff)](#5-python--formatowanie-ruff)
6. [Python — srodowisko i narzedzia](#6-python--srodowisko-i-narzedzia)
7. [Python — struktura projektu](#7-python--struktura-projektu)
8. [Python — type hints](#8-python--type-hints)
9. [Python — docstrings](#9-python--docstrings)
10. [Python — testowanie](#10-python--testowanie)
11. [Python — obsluga bledow](#11-python--obsluga-bledow)
12. [Python — logging](#12-python--logging)
13. [Python — wydajnosc](#13-python--wydajnosc)
14. [Bezpieczenstwo](#14-bezpieczenstwo)
15. [Workflow sesji i implementacji](#15-workflow-sesji-i-implementacji)
16. [Czego NIE robic](#16-czego-nie-robic)
17. [Typowe zadania](#17-typowe-zadania)
18. [Pre-merge checklist](#18-pre-merge-checklist)

---

## 1. Git Workflow

### 1.1 Branching (Git Flow)

```
main              # Stabilna wersja (tylko merge z develop)
develop           # Aktywny rozwoj (DOMYSLNA GALAZ ROBOCZA)
feature/<nazwa>   # Nowe funkcjonalnosci
fix/<nazwa>       # Poprawki bledow
docs/<nazwa>      # Tylko dokumentacja
hotfix/<nazwa>    # Pilne poprawki produkcyjne (branch z main)
```

**Zasady:**
- `main` — tylko stabilny, przetestowany kod
- `develop` — integracja feature'ow, domyslna galaz robocza
- `feature/*` — branch z `develop`, merge do `develop`
- `fix/*`, `docs/*` — branch z `develop`, merge do `develop`
- `hotfix/*` — branch z `main`, merge do `main` i `develop`
- Praca biezaca ZAWSZE na `develop` albo na galezi krotkotrwalej
  z `develop` — nigdy bezposrednio na `main`

### 1.2 Tagowanie

Tagi `v<X.Y.Z>` (SemVer) przy wydaniach:

```bash
git tag -a v0.4.0 -m "Release v0.4.0: NMPT, Ortofotomapa, nowa struktura storage"
git push origin v0.4.0
```

Checkpointy robocze (CP) sa sledzone tylko w `docs/PROGRESS.md`, bez tagow Git.

Przed wydaniem: testy offline nie zastepuja ponownych testow na zywych
serwisach (`-m live` oraz przebiegi CLI na katalog danych, sekcja 6.4).

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
2. Kontrole (uruchamiane lokalnie, komendy w sekcji 6.3):
   ├─ Formatowanie (ruff format --check)
   ├─ Linting (ruff check)
   ├─ Type checking (mypy, bez nowych bledow — sekcja 8.3)
   └─ Testy offline z pokryciem (pytest -m "not live" --cov)
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
| Funkcje | snake_case + czasownik | `download_sheet()`, `parse_bbox_arg()` |
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
| `parse_*` | Parsowanie danych | `parse_bbox_arg()`, `parse_skorowidz_records()` |
| `calculate_*` | Obliczenie wyniku | `calculate_hsg_by_godlo()` |
| `get_*` | Pobranie atrybutu / danych | `get_parent()`, `get_children()` |
| `list_*` | Listowanie zasobow | `list_files()` |
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

## 6. Python — srodowisko i narzedzia

### 6.1 Srodowisko wirtualne

Wymagany Python 3.12+ (`requires-python` w `pyproject.toml`). Jedno
srodowisko wirtualne `.venv/` w korzeniu projektu — dla ludzi i agentow AI:

- Python: `.venv/bin/python`
- Pip: `.venv/bin/pip`
- CLI: `.venv/bin/kartograf`

```bash
cd Kartograf
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 6.2 Zmienne srodowiskowe (opcjonalne)

- `CLMS_CREDENTIALS` — credentials Copernicus CLMS API jako JSON string
  (pola `client_id`, `private_key`, `token_uri`, opcjonalnie
  `key_id`/`user_id`); potrzebne do CORINE GeoTIFF. Dziala na kazdym
  systemie: czyta ja wylacznie **podproces Auth Proxy**
  (`python -m kartograf.auth.proxy`), ktory dziedziczy srodowisko rodzica —
  glowny proces nie widzi kluczy ani tokenu. Kolejnosc zrodel w proxy:
  `CLMS_CREDENTIALS`, potem (tylko macOS) Keychain (service `clms-token`).
  Bez zadnego z nich `AuthProxyClient.is_available()` na systemie innym niz
  macOS zwraca `False` bez uruchamiania podprocesu. Bez credentials CORINE
  pobiera podglad PNG przez WMS (sidecar: `extra.fallback = "wms_png"`).
  Z poziomu biblioteki: `CorineProvider(clms_credentials={...})` (tryb
  bezposredni, z pominieciem proxy). Szczegoly: sekcja 14.3.
- `KARTOGRAF_DEBUG=1` — pelny traceback zamiast skroconego `Error: ...`
  z CLI (dla kazdego wyjatku docierajacego do bariery `main`, takze
  `KartografError`).

### 6.3 Komendy: testy, lint, typy

```bash
# Testy offline (domyslna brama)
.venv/bin/python -m pytest tests/ -v -m "not live"

# Testy z pokryciem (offline)
.venv/bin/python -m pytest tests/ -m "not live" --cov=kartograf --cov-report=html

# Testy sieciowe (live) — tylko swiadomie
.venv/bin/python -m pytest tests/ -m live

# Liczba testow (zamiast liczb w dokumentacji)
.venv/bin/python -m pytest tests/ --collect-only -q -m "not live"

# Linter
.venv/bin/python -m ruff check kartograf/ tests/

# Formatowanie / sprawdzenie formatowania (bez zmian)
.venv/bin/python -m ruff format kartograf/ tests/
.venv/bin/python -m ruff format --check kartograf/ tests/

# Type checking (sekcja 8.3)
.venv/bin/python -m mypy kartograf/
```

Testy sa **offline**: `tests/conftest.py` przewraca kazdy test otwierajacy
gniazdo spoza loopbacku; wyjatek maja tylko testy z markerem `live`
(zapytania o metadane, bez pobierania plikow). `pyproject.toml` nie
odfiltrowuje testow `live` (`addopts` bez `-m`), wiec komenda bez
`-m "not live"` wychodzi w siec. Szczegoly izolacji: sekcja 10.4.

### 6.4 katalog danych danych — gdzie zapisywac pobrane dane

Od 2026-10-06 **wszystkie dane przestrzenne pobierane przez agentow AI**
(testy na zywo, weryfikacje E2E, reczne wywolania CLI, dane do analiz)
zapisujemy na serwerze sieciowym `<katalog-danych>` — NIE w repo
i NIE w `/tmp`.

- Udzial CIFS/SMB `<udzial>` zapis dla
  `claude-agent` (pliki 0640, katalogi 0750).
- Domyslne `--output` CLI wskazuja na repo — **zawsze podawaj `--output`
  jawnie**:

  ```bash
  kartograf download N-34-130-D-d-2-4 -o <katalog-danych>/kartograf/data
  kartograf download --bbox 530000,382000,533000,386000 --target-crs EPSG:5514 \
      -o <katalog-danych>/kartograf/e2e/<RRRR-MM-DD>-<cel>
  ```

- Uklad katalogow:
  - `<katalog-danych>/kartograf/data/` — kanoniczny uklad `data/`
    (ADR-026), wspolny dla kolejnych sesji (reuzycie pobranych arkuszy);
  - `<katalog-danych>/kartograf/e2e/<RRRR-MM-DD>-<cel>/` — przebiegi
    testow na zywo i weryfikacji;
  - wyniki/notatki z przebiegu (raporty `.md`) trafiaja do `docs/research/`
    w repo — na katalog danych idzie tylko ciezki raster/LAZ/GPKG.
- Cache metadanych `.kartograf_cache.db` (SQLite WAL) **zostaje lokalnie**
  (biezacy katalog = repo, gitignorowany): WAL na udziale sieciowym jest
  zawodny. Uruchamiaj CLI z korzenia repo i kieruj na katalog danych tylko
  `--output`.
- Montowanie jest `soft`: przy niedostepnosci serwera zapis konczy sie
  bledem I/O (nie wisi). Przed dlugim pobieraniem sprawdz
  `df -h <katalog-danych>`; gdy udzial nie jest zamontowany, zatrzymaj
  sie i zapytaj uzytkownika zamiast pisac lokalnie.
- Testy pytest nie dotycza katalog danych (offline: `tmp_path`; `live`: tylko
  zapytania o metadane, bez plikow).

---

## 7. Python — struktura projektu

### 7.1 Kartograf — flat layout

Pakiet `kartograf/` lezy w korzeniu repo (bez `src/`); testy w `tests/`
(`conftest.py` + `fixtures/`), dokumentacja w `docs/`, konfiguracja narzedzi
w `pyproject.toml`.

Zrodlem prawdy dla struktury modulow i zaleznosci miedzy warstwami jest
`docs/ARCHITECTURE.md`, sekcja 2 ("Warstwy i zaleznosci modulow"), a
ostatecznie sam katalog `kartograf/`. Ten dokument nie powiela drzewa
modulow. Nowy modul umieszczaj w warstwie zgodnej z ARCHITECTURE i aktualizuj
tam jego opis w tym samym commicie.

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

Projekt utrzymuje baseline mypy (konfiguracja `[tool.mypy]` w
`pyproject.toml`, bez `--strict`) z przedistniejacymi bledami. Nowy kod nie
moze dodawac nowych bledow do tego dlugu. Porownuj **liste bledow bez
numerow linii** przed i po zmianie, nie ich liczbe (przesuniecie linii
zmienia numery, a liczba moze sie zgadzac mimo zamiany bledow):

```bash
.venv/bin/python -m mypy kartograf/ | sed -E 's/:[0-9]+:/:/' | sort > mypy-po.txt
# to samo na develop -> mypy-przed.txt; diff nie moze miec nowych pozycji
diff mypy-przed.txt mypy-po.txt
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

**Odstepstwo praktyki (do rozstrzygniecia przez wlasciciela projektu):** kod od etapu 0 ma docstringi i komentarze takze po polsku bez
polskich znakow (w calosci m.in. `download/cutout.py`, `transport/mosaic.py`,
wiekszosc `cli/download_cmd.py`), a commity sa po polsku (Conventional
Commits). Nowe publiczne API wycinka (`download_pl_cutout` i kroki) ma
docstringi bez pelnego kompletu sekcji NumPy. Do decyzji: ujednolicic
standard z praktyka albo praktyke ze standardem.

---

## 10. Python — testowanie

### 10.1 Progi pokrycia

| Warstwa | Wymagane pokrycie | Egzekwowanie |
|---------|-------------------|--------------|
| Caly pakiet (prog globalny) | `fail_under` w `[tool.coverage.report]` (`pyproject.toml`) | automatycznie przy `--cov` |
| Core (`core/`, `providers/`, `download/`) | **>= 80%** | recznie, komenda ponizej |

```bash
.venv/bin/python -m pytest tests/ -m "not live" --cov=kartograf --cov-report=html
```

`fail_under` w `pyproject.toml` jest jedynym zrodlem progu globalnego —
nie powielaj jego wartosci w komendach (`--cov-fail-under`).
`pytest-cov`/`coverage.py` nie ma wbudowanego progu per-warstwa — prog
**>= 80%** dla warstwy core sprawdzaj druga komenda, na tych samych danych
`.coverage` (bez ponownego uruchamiania testow):

```bash
.venv/bin/python -m pytest tests/ --cov=kartograf --cov-report=term -q -p no:cacheprovider -m "not live"
.venv/bin/python -m coverage report --include='kartograf/core/*,kartograf/providers/*,kartograf/download/*' --fail-under=80
```

Moduly core ponizej progu (znane odstepstwa) wyznaczaj na biezaco, zamiast
utrzymywac ich liste z procentami w dokumentacji:

```bash
.venv/bin/python -m pytest tests/ -q -p no:cacheprovider -m "not live" --cov=kartograf \
    --cov-report=term-missing | grep -E '^kartograf/(core|providers|download)/.* [0-7]?[0-9]%'
```

Odstepstwo od progu core wymaga wpisu w backlogu `docs/PROGRESS.md`
(modul + przyczyna). Progi warstwowe nie sa egzekwowane automatycznie —
sprawdzaj je recznie przed merge (sekcja 18).

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
    """Test that invalid godlo raises ParseError."""
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

**Fixtury z realnych odpowiedzi:** odpowiedzi serwerow w testach offline
buduj z SUROWYCH odpowiedzi zapisanych z prawdziwych uslug (wzor:
`tests/fixtures/cuzk/`, `tests/fixtures/gugik_skorowidz/`), nie
z wyobrazenia o formacie.

---

## 11. Python — obsluga bledow

### 11.1 Wyjatki Kartograf

Zrodlem prawdy hierarchii wyjatkow jest `kartograf/exceptions.py` (wyjatki
transformacji CRS: `kartograf/transform/crs.py`). Ten dokument nie powiela
listy klas. Zasady:

- Kazdy wlasny wyjatek dziedziczy (bezposrednio lub posrednio)
  z `KartografError` — uzytkownik biblioteki lapie wszystkie bledy pakietu
  jednym `except KartografError`.
- Uzywaj najwezszej istniejacej klasy (np. brak danych u zrodla to
  `NoCoverageError`, nie ogolny `DownloadError`); nowa klase dodawaj tylko,
  gdy wywolujacy musi ja odroznic, i od razu opisz ja w docstringu.
- Informacje dla wywolujacego przekazuj atrybutami wyjatku (np.
  `DownloadError.status_code`), nie przez parsowanie komunikatu.
- `KartografError` docierajacy do bariery CLI (`main`) daje
  `Error: <komunikat>` i kod 1 (pelny traceback: `KARTOGRAF_DEBUG=1`,
  sekcja 6.2) — komunikat ma byc zrozumialy dla uzytkownika.
- Zawsze zachowuj lancuch wyjatkow: `raise ... from err` (sekcja 11.3).

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

W providerach nie tworz sesji recznie: sesje (takze per watek,
`SessionPerThread`) daje `kartograf/transport/http.py`.

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

### 13.4 Timeouty i ponowienia

- **Kazde zapytanie HTTP ma jawny timeout.** Wartosci domyslne sa stalymi
  w modulach providerow (`DEFAULT_TIMEOUT` w klasie providera, np.
  `GugikProvider.DEFAULT_TIMEOUT`, `Bdot10kProvider.DEFAULT_TIMEOUT`; osobne
  stale dla innych operacji, np. `GugikLazProvider.WFS_TIMEOUT`) — to one sa
  zrodlem prawdy, nie dokumentacja: `grep -rn "_TIMEOUT =" kartograf/providers`.
- **Ponowienia sa w jednym miejscu:** `kartograf/transport/http.py` —
  `download_to` dla plikow (zapis atomowy przez `os.replace`) i
  `get_with_retry` dla zapytan. Providery nie implementuja wlasnych petli
  retry.
- Ponawiane sa tylko bledy sieci, HTTP 429 i 5xx (`is_retryable`); inne 4xx
  koncza od razu z `DownloadError.status_code`.
- Najwyzej `MAX_RETRIES` (3) proby, nie konfigurowalne z CLI; przerwa wg
  `backoff_delay` (2 s, potem 4 s); naglowek `Retry-After` wydluza przerwe,
  maksymalnie do `MAX_RETRY_AFTER` (60 s).

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

# ALWAYS use environment variables for secrets — read them only where
# they are needed (CLMS: only the Auth Proxy subprocess, see 14.3)
raw_credentials = os.environ.get("CLMS_CREDENTIALS")

# ALWAYS validate input at system boundaries
if not godlo or not godlo.strip():
    raise ValidationError("Godlo cannot be empty")

# ALWAYS set timeouts for HTTP requests
response = requests.get(url, timeout=30)
```

### 14.3 Auth Proxy — specyficzne dla Kartograf

CLMS credentials sa izolowane w osobnym procesie (Auth Proxy):

```
CorineProvider → AuthProxyClient → HTTP 127.0.0.1 → Auth Proxy (podproces
`python -m kartograf.auth.proxy`: CLMS_CREDENTIALS, potem tylko macOS
Keychain `clms-token`) → CLMS API
```

- Credentials (klucz prywatny RSA) nigdy nie opuszczaja procesu proxy
- Glowna aplikacja nie widzi kluczy ani tokenu
- Tylko odpowiedzi API sa przekazywane do aplikacji
- Wyjatek swiadomy: `CorineProvider(clms_credentials={...})` w bibliotece
  (tryb bezposredni, z pominieciem proxy)
- Zmienne srodowiskowe i fallback bez credentials: sekcja 6.2

---

## 15. Workflow sesji i implementacji

### 15.1 Poczatek sesji

```
1. Przeczytaj docs/PROGRESS.md — sekcja "Ostatnia sesja" (blok START)
2. git status + git log --oneline -5
3. Sprawdz galaz: git branch --show-current (develop albo galaz z develop)
4. Zrozum zadanie — znajdz relevantne sekcje w SCOPE.md / PRD.md / ARCHITECTURE.md
5. Zadaj pytania, jesli cos jest niejasne
```

Kolejnosc lektury dokumentacji: `docs/PROGRESS.md` (stan i zadania) ->
`docs/SCOPE.md` (zakres) -> `docs/ARCHITECTURE.md` (architektura, kontrakty
danych, uklad `data/`) -> `docs/PRD.md` (wymagania) -> `docs/CHANGELOG.md`
(historia zmian) -> `docs/DECISIONS.md` (ADR — co i dlaczego).

### 15.2 Implementacja

```
1. Pisz kod zgodnie z tym dokumentem
2. Type hints (Python 3.12+ style: X | None zamiast Optional[X]) — sekcja 8
3. Docstrings NumPy style — sekcja 9
4. Walidacja inputu na granicy systemu — sekcja 11.2
5. Timeout dla kazdego requestu HTTP — sekcja 13.4
6. raise ... from err (zachowaj lancuch wyjatkow) — sekcja 11.3
```

### 15.3 Testowanie

```
1. Napisz testy (pytest, AAA pattern) — sekcja 10
2. Testy offline: fixtures i mocking, bez prawdziwych API (sekcja 10.4)
3. Pokrycie: progi z sekcji 10.1
4. Uruchom: pytest tests/ -v --tb=short -m "not live"
5. Sprawdz linting: ruff check kartograf/ tests/
```

### 15.4 W trakcie sesji — commity

```
1. Conventional Commits (sekcja 2): feat(parser): add bbox calculation
2. Commituj czesto, male zmiany
3. Aktualizuj docs/CHANGELOG.md na biezaco — sekcja wersji niewydanej
   (naglowek "## [X.Y.Z] - Unreleased" na gorze pliku)
4. W razie watpliwosci — pytaj
```

### 15.5 Koniec sesji

**OBOWIAZKOWO** zaktualizuj `docs/PROGRESS.md` (sekcja "Ostatnia sesja"):

- co zostalo zrobione,
- co jest w trakcie (plik, linia, kontekst),
- nastepne kroki.

---

## 16. Czego NIE robic

- **Nie dodawaj funkcji poza zakresem** — sprawdz `docs/SCOPE.md`, sekcja 3 ("Out of Scope")
- **Nie zmieniaj architektury** bez konsultacji — decyzje sa w `docs/DECISIONS.md`
- **Nie pomijaj testow** — progi pokrycia z sekcji 10.1
- **Nie hardcoduj secrets** — uzyj zmiennych srodowiskowych / Auth Proxy (sekcja 14)
- **Nie uzywaj Optional/Union** — uzyj `X | None` i `X | Y` (Python 3.12+)
- **Nie uzywaj f-stringow w loggerze** — uzyj `%s` formatting
- **Nie tworz osobnych plikow konfiguracyjnych** — wszystko w `pyproject.toml`
- **Nie wywoluj prawdziwych API w testach** — mockuj requesty; siec tylko w testach `live`
- **Nie zapisuj pobranych danych w repo ani w `/tmp`** — katalog danych danych (sekcja 6.4)

---

## 17. Typowe zadania

### 17.1 Nowy provider pokrycia terenu / gleb (`LandCoverProvider`)

```python
# 1. Stworz klase w kartograf/providers/ (provider krajowy w podpakiecie
#    kraju, np. kartograf/providers/pl/), dziedziczaca z LandCoverProvider
#    (kartograf/providers/base.py).
# 2. Zaimplementuj metody abstrakcyjne — te oznaczone @abstractmethod
#    w kartograf/providers/base.py (LandCoverProvider i jego baza
#    DataSourceProvider): wlasciwosci name i base_url oraz download_by_bbox.
#    download_by_godlo jest dziedziczone (godlo -> bbox EPSG:2180 ->
#    download_by_bbox); nadpisz je tylko, gdy zrodlo ma wlasny tor godla.
#    download_by_admin_unit (TERYT) jest opcjonalne — domyslnie
#    NotImplementedError; download_by_teryt to zdeprecjonowany alias z bazy.
# 3. Dodaj deskryptor zrodla w kartograf/sources/registry.py i ustaw
#    descriptor_key w providerze (katalog zapisu, sidecar) — patrz
#    docs/ARCHITECTURE.md sekcja 5.
# 4. Zarejestruj w slowniku modulowym PROVIDERS w kartograf/landcover/manager.py
# 5. Dodaj eksport do kartograf/__init__.py (__all__)
# 6. Napisz testy offline w tests/ (fixtury z realnych odpowiedzi serwera)
# 7. CLI: dopisz zrodlo do choices --source w cli/_parser.py i logike
#    w cli/landcover_cmd.py; cli/commands.py to tylko fasada zgodnosci
```

Nowe zrodlo NMT albo nowy kraj: checklista w `docs/ARCHITECTURE.md`,
sekcja 5 ("Jak dodac nowe zrodlo albo nowy kraj").

### 17.2 Rozszerzenie parsera godel

```python
# 1. PL-1992: kartograf/core/sheet_parser.py — wzorzec w PATTERNS, logika
#    podzialu w get_children() / _get_children_from_*();
#    PL-2000: kartograf/core/parser_2000.py.
# 2. Nowy system godel (kraj): klasa parsera w core/ + wpis SheetSystem
#    w literale SYSTEMS w core/parser_registry.py (ARCHITECTURE sekcja 5, pkt 3)
# 3. Zaktualizuj testy: tests/test_sheet_parser.py, tests/test_parser_2000.py,
#    tests/test_parser_registry.py
# 4. Przetestuj hierarchie (get_parent, get_children, get_all_descendants)
```

### 17.3 Naprawa bledu w pobieraniu

```python
# 1. Zidentyfikuj provider (kartograf/providers/: pl/, cuzk/, corine.py,
#    soilgrids.py)
# 2. Sprawdz timeout providera i transport: retry/backoff sa wspolne
#    w kartograf/transport/http.py (download_to, get_with_retry), nie
#    w providerach
# 3. Dodaj test reprodukujacy blad (offline, fixtura z realnej odpowiedzi)
# 4. Napraw i potwierdz testem
# 5. Uruchom caly zestaw testow offline — nic innego nie moze sie zepsuc
```

---

## 18. Pre-merge checklist

```markdown
- [ ] Testy offline przechodza (`pytest tests/ -v -m "not live"`; testy
      `live` tylko swiadomie: `pytest tests/ -m live`)
- [ ] Pokrycie kodu w normie (sekcja 10.1: `fail_under` + 80% core)
- [ ] Formatowanie OK (`ruff format --check kartograf/ tests/`)
- [ ] Linting OK (`ruff check kartograf/ tests/`)
- [ ] Type hints OK (`mypy kartograf/` — bez nowych bledow wzgledem baseline'u, sekcja 8.3)
- [ ] Docstrings dla publicznych funkcji/klas
- [ ] Brak hardcoded secrets
- [ ] Dokumentacja zaktualizowana (jesli potrzeba)
- [ ] PROGRESS.md / CHANGELOG.md zaktualizowany
- [ ] Minimum 1 approval
- [ ] Brak konfliktow z target branch
```

---

**Wersja dokumentu:** 3.0
**Data ostatniej aktualizacji:** 2026-10-08
**Zrodlo:** `shared/standards/DEVELOPMENT_STANDARDS.md` v1.0 (repozytorium zewnetrzne, nieobecne w tym workspace)

*Odstepstwa od tych standardow wymagaja uzasadnienia — w tym dokumencie (jak sekcja 9.4) albo w ADR (`docs/DECISIONS.md`).*
