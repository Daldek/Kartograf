# Prompt implementacyjny — Kartograf

**Wersja:** 2.0
**Data:** 2026-02-03
**Dla:** Claude Code i inni asystenci AI

---

## 1. Kontekst projektu

Pracujesz nad **Kartograf** — narzedziem do pobierania danych przestrzennych z zasobow GUGiK, Copernicus i ISRIC dla Polski.

**Funkcjonalnosci:**
- **NMT** — Numeryczny Model Terenu (1m, 5m) z GUGiK
- **NMPT** — Numeryczny Model Pokrycia Terenu / DSM (1m) z GUGiK
- **Ortofotomapa** — zdjecia lotnicze Standard Resolution (25cm, TIF) z GUGiK
- **BDOT10k** — pokrycie terenu (12 warstw) z GUGiK
- **CORINE Land Cover** — europejska klasyfikacja (44 klasy) z Copernicus
- **SoilGrids** — dane glebowe (11 parametrow, 6 glebokosci) z ISRIC
- **HSG** — grupy hydrologiczne SCS-CN z danych SoilGrids
- **CLI** — 5 komend (parse, download, landcover, soilgrids, hsg) + --product {nmt,nmpt,orto}

**Stack technologiczny:**
- Python 3.12+
- requests (HTTP), pyproj (CRS), PyJWT (OAuth2), rasterio (GeoTIFF), numpy (arrays)
- Flat layout, pyproject.toml, ruff, pytest

**Uzycie:**
- Jako standalone CLI tool
- Jako biblioteka Python w Hydrograf i Hydrolog

---

## 2. Dokumentacja — przeczytaj PRZED praca

1. **CLAUDE.md** (korzen projektu) — kontekst sesji, komendy, workflow
2. **docs/PROGRESS.md** — aktualny stan, co zrobiono, nastepne kroki
3. **docs/SCOPE.md** — zakres (co JEST i czego NIE MA)
4. **docs/PRD.md** — wymagania produktowe
5. **docs/DEVELOPMENT_STANDARDS.md** — standardy kodowania
6. **docs/CHANGELOG.md** — historia zmian

**WAZNE:** Przed napisaniem JAKIEGOKOLWIEK kodu, przeczytaj CLAUDE.md i PROGRESS.md.

---

## 3. Architektura modulow

```
kartograf/
├── __init__.py              # Public API — eksporty wszystkich klas
├── exceptions.py            # KartografError → ParseError, ValidationError, DownloadError
│
├── core/                    # WARSTWA BAZOWA
│   └── sheet_parser.py      # SheetParser — parser godel (1:1M do 1:10k)
│                            # BBox — bounding box z transformacja CRS
│
├── providers/               # WARSTWA DANYCH (abstrakcje nad API)
│   ├── base.py              # BaseProvider — abstrakcja dla NMT
│   ├── gugik.py             # GugikProvider — NMT z GUGiK (WCS + OpenData)
│   ├── gugik_nmpt.py        # GugikNmptProvider — NMPT/DSM (dziedziczy z GugikProvider)
│   ├── gugik_orto.py        # GugikOrtoProvider — Ortofotomapa (BaseProvider, TIF)
│   ├── landcover_base.py    # LandCoverProvider — abstrakcja dla pokrycia terenu
│   ├── bdot10k.py           # Bdot10kProvider — BDOT10k z GUGiK
│   ├── corine.py            # CorineProvider — CORINE z Copernicus (CLMS API + WMS)
│   └── soilgrids.py         # SoilGridsProvider — dane glebowe z ISRIC (WCS)
│
├── download/                # WARSTWA POBIERANIA (NMT/NMPT/Orto)
│   ├── manager.py           # DownloadManager — koordynacja pobierania arkuszy
│   └── storage.py           # FileStorage — hierarchiczna struktura katalogow
│
├── landcover/               # WARSTWA POBIERANIA (Land Cover)
│   └── manager.py           # LandCoverManager — dispatch do providerow
│
├── hydrology/               # WARSTWA OBLICZEN
│   └── hsg.py               # HSGCalculator — klasyfikacja USDA, mapowanie HSG
│
├── auth/                    # WARSTWA AUTENTYKACJI
│   ├── proxy.py             # Auth Proxy — serwer HTTP izolujacy credentials
│   └── client.py            # Auth Proxy client — singleton, auto-start proxy
│
└── cli/                     # WARSTWA CLI
    └── commands.py          # Komendy: parse, download, landcover, soilgrids, hsg
```

### Przeplywy danych

```
CLI → DownloadManager → GugikProvider → GUGiK API (WCS/OpenData) → FileStorage
CLI → DownloadManager → GugikNmptProvider → GUGiK API (WCS/OpenData) → FileStorage
CLI → DownloadManager → GugikOrtoProvider → GUGiK API (WCS/OpenData) → FileStorage
CLI → LandCoverManager → Bdot10kProvider → GUGiK API (WFS) → FileStorage
CLI → LandCoverManager → CorineProvider → AuthProxy → CLMS API → FileStorage
CLI → LandCoverManager → SoilGridsProvider → ISRIC WCS → FileStorage
CLI → HSGCalculator → SoilGridsProvider → rasterio → numpy → FileStorage
```

---

## 4. Zrodla danych i API

| Zrodlo | Typ danych | API | Autentykacja | Timeout |
|--------|-----------|-----|--------------|---------|
| GUGiK | NMT/NMPT (ASC/GeoTIFF) | WCS, OpenData | Brak | 30s |
| GUGiK | Ortofoto (TIF/GeoTIFF) | WCS, OpenData | Brak | 60s |
| GUGiK | BDOT10k (GeoPackage) | WFS | Brak | 60s |
| Copernicus CLMS | CORINE (GeoTIFF) | REST API | OAuth2 RSA | 60s |
| EEA Discomap | CORINE (PNG) | WMS | Brak | 60s |
| ISRIC SoilGrids | Gleba (GeoTIFF) | WCS | Brak | 60s |

### Specyfika API

**GUGiK NMT:**
- OpenData: pobieranie przez godlo → ASC (1m) lub GeoTIFF (5m)
- WCS: pobieranie przez bbox → GeoTIFF (tylko 1m)
- NMT 5m wymaga ukladu EVRF2007

**CORINE:**
- CLMS API: wymaga OAuth2 RSA (client_id + private key)
- Fallback na WMS (EEA Discomap): PNG podglad, bez autentykacji
- Auth Proxy izoluje credentials w osobnym procesie

**SoilGrids:**
- WCS z ISRIC: bbox w WGS84 (transformacja automatyczna z EPSG:2180)
- 11 parametrow × 6 glebokosci × 5 statystyk

---

## 5. Public API

```python
from kartograf import (
    # Core
    SheetParser, BBox, find_sheets_for_bbox,
    # Download (NMT/NMPT/Orto)
    DownloadManager, DownloadProgress, FileStorage,
    # Land Cover
    LandCoverManager,
    # Providers
    BaseProvider, GugikProvider, GugikNmptProvider, GugikOrtoProvider,
    LandCoverProvider, Bdot10kProvider, CorineProvider, SoilGridsProvider,
    # Hydrology
    HSGCalculator,
    # Exceptions
    KartografError, ParseError, ValidationError, DownloadError,
)
```

---

## 6. Workflow implementacji

### 6.1 Przed rozpoczeciem

```
1. Przeczytaj CLAUDE.md i PROGRESS.md
2. Sprawdz galaz: git branch --show-current (powinno byc: develop)
3. Sprawdz status: git status
4. Zrozum zadanie — znajdz relevantne sekcje w SCOPE.md / PRD.md
5. Zadaj pytania jesli cos niejasne
```

### 6.2 Implementacja

```
1. Pisz kod zgodnie z DEVELOPMENT_STANDARDS.md
2. Type hints (Python 3.12+ style: X | None zamiast Optional[X])
3. Docstrings NumPy style, po angielsku
4. Walidacja inputu na granicy systemu
5. Timeout dla kazdego requestu HTTP
6. raise ... from err (zachowaj lancuch wyjatkow)
```

### 6.3 Testowanie

```
1. Napisz testy (pytest, AAA pattern)
2. Uzyj fixtures i mocking (nie wywoluj prawdziwych API)
3. Pokrycie: 80% core / 60% utility
4. Uruchom: pytest tests/ -v --tb=short
5. Sprawdz linting: ruff check kartograf/ tests/
```

### 6.4 Commit

```
1. Conventional Commits: feat(parser): add bbox calculation
2. Commituj czesto, male zmiany
3. Zaktualizuj CHANGELOG.md (sekcja [Unreleased])
4. Zaktualizuj PROGRESS.md na koniec sesji
```

---

## 7. Czego NIE robic

- **Nie dodawaj funkcji poza zakresem** — sprawdz SCOPE.md sekcja "Out of Scope"
- **Nie zmieniaj architektury** bez konsultacji — struktura jest przemyslana
- **Nie pomijaj testow** — minimum 60% pokrycia
- **Nie hardcoduj secrets** — uzyj env vars / Auth Proxy
- **Nie uzywaj Optional/Union** — uzyj `X | None` i `X | Y` (Python 3.12+)
- **Nie uzywaj f-stringow w loggerze** — uzyj `%s` formatting
- **Nie twrz osobnych plikow konfiguracyjnych** — wszystko w pyproject.toml
- **Nie wywoluj prawdziwych API w testach** — mockuj requestsy

---

## 8. Typowe zadania

### 8.1 Dodanie nowego providera danych

```python
# 1. Stworz klase w kartograf/providers/nowy_provider.py
# 2. Dziedzicz z LandCoverProvider (landcover_base.py)
# 3. Zaimplementuj metody: download_by_teryt, download_by_bbox, download_by_godlo
# 4. Zarejestruj w LandCoverManager._init_providers()
# 5. Dodaj eksport do kartograf/__init__.py
# 6. Napisz testy w tests/test_nowy_provider.py
# 7. Dodaj komende CLI w commands.py
```

### 8.2 Rozszerzenie parsera godel

```python
# 1. Edytuj kartograf/core/sheet_parser.py
# 2. Dodaj nowy pattern do PATTERNS dict
# 3. Dodaj logike subdivision w _get_children_from_*()
# 4. Zaktualizuj testy w tests/test_sheet_parser.py
# 5. Przetestuj hierarchie (get_parent, get_children, get_all_descendants)
```

### 8.3 Naprawa bledu w pobieraniu

```python
# 1. Zidentyfikuj provider (GugikProvider, Bdot10kProvider, CorineProvider, SoilGridsProvider)
# 2. Sprawdz retry logic i timeout
# 3. Dodaj test reprodukujacy blad
# 4. Napraw i potwierdz testem
# 5. Sprawdz czy nie zepsules istniejacych testow
```

---

## 9. Ograniczenia techniczne

- **Synchroniczne pobieranie** — brak async/parallel (zaplanowane na v0.5+)
- **NMT 5m** — tylko OpenData (ASC), brak WCS; wymaga EVRF2007
- **CORINE GeoTIFF** — wymaga OAuth2 credentials; bez nich fallback na PNG (WMS)
- **SoilGrids** — tylko WGS84 bbox (transformacja automatyczna)
- **Retry** — max 3 proby, exponential backoff (nie konfigurowalne)
- **Brak cache** — kazde wywolanie pobiera dane od nowa (zaplanowane)
- **Brak mozaikowania** — kazdy arkusz osobno (zaplanowane)

---

## 10. Integracje z innymi projektami

### Hydrograf (hub)
```python
from kartograf import DownloadManager, SheetParser
manager = DownloadManager(output_dir="./data")
manager.download_hierarchy("N-34-130-D", target_scale="1:10000")
```

### Hydrolog (obliczenia)
```python
from kartograf import HSGCalculator, SoilGridsProvider
calc = HSGCalculator()
hsg_path = calc.calculate_hsg_by_godlo("N-34-130-D")
```

---

## 11. Checklist przed zakonczeniem sesji

```markdown
- [ ] Kod sformatowany (`ruff format kartograf/ tests/`)
- [ ] Linting OK (`ruff check kartograf/ tests/`)
- [ ] Testy przechodza (`pytest tests/ -v`)
- [ ] CHANGELOG.md zaktualizowany (sekcja [Unreleased])
- [ ] PROGRESS.md zaktualizowany (sekcja "Ostatnia sesja")
- [ ] Commity zgodne z Conventional Commits
- [ ] Brak hardcoded secrets
```

---

**Wersja dokumentu:** 3.0
**Data ostatniej aktualizacji:** 2026-02-07
**Status:** Aktywny dla wszystkich asystentow AI pracujacych nad projektem
