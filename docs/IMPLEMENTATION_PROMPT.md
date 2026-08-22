# Prompt implementacyjny — Kartograf

**Wersja:** 4.1
**Data:** 2026-08-22
**Dla:** Claude Code i inni asystenci AI

> **Nota 4.0 (2026-08-18):** aktualizacja do stanu po etapie 1 (v0.7.0-dev,
> NMT Czechy/CUZK): architektura, Public API, przeplywy BDOT10k, zniesione
> ograniczenia (parallel/cache/mozaikowanie). Tam gdzie CLAUDE.md pokrywa
> temat, ten dokument odsyla do CLAUDE.md zamiast duplikowac tresc.
>
> **Nota 4.1 (2026-08-22, audyt przedwydaniowy 0.7.0):** korekty zgodnosci
> z kodem — timeouty BDOT10k/SoilGrids, WCS NMT tylko 1m i tylko KRON86,
> kanoniczna `download_by_admin_unit` w 8.1 oraz przyklad HSG (brakowal
> wymagany `output_path`, wiec rzucal `TypeError`).

---

## 1. Kontekst projektu

Pracujesz nad **Kartograf** — narzedziem do pobierania danych przestrzennych z zasobow GUGiK (Polska), CUZK (Czechy), Copernicus i ISRIC.

**Funkcjonalnosci:**
- **NMT (PL)** — Numeryczny Model Terenu (1m, 5m) z GUGiK
- **NMT (CZ)** — DMR 5G/4G z CUZK (2m i 5m), godlo TM33/SM5 lub bbox, `--country {pl,cz,auto}` (etap 1, v0.7.0-dev)
- **NMPT** — Numeryczny Model Pokrycia Terenu / DSM (1m) z GUGiK
- **Ortofotomapa** — zdjecia lotnicze Standard Resolution (25cm, TIF) z GUGiK
- **LAZ** — chmury punktow LIDAR (dane pomiarowe ALS, .laz) z GUGiK przez WFS
- **BDOT10k** — pokrycie terenu (15 warstw: 12 PT* + 3 SW*) z GUGiK
- **CORINE Land Cover** — europejska klasyfikacja (44 klasy) z Copernicus
- **SoilGrids** — dane glebowe (11 parametrow, 6 glebokosci) z ISRIC
- **HSG** — grupy hydrologiczne SCS-CN z danych SoilGrids
- **CLI** — 5 komend top-level (parse, download, landcover, soilgrids, cache; `hsg` to subkomenda `soilgrids`) + --product, --geometry, --system, --country

**Stack technologiczny:**
- Python 3.12+
- requests (HTTP), pyproj (CRS), PyJWT (OAuth2), rasterio (GeoTIFF), numpy (arrays), pyshp (SHP)
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

Pelne, aktualne drzewo modulow (z opisami per plik) utrzymuje sekcja
**"Struktura modulow" w CLAUDE.md** (korzen repo) — traktuj ja jako zrodlo
prawdy. Skrot warstw:

```
kartograf/
├── __init__.py              # Public API — eksporty wszystkich klas
├── exceptions.py            # KartografError → ParseError, ValidationError, DownloadError
├── core/                    # WARSTWA BAZOWA: sheet_parser.py (PL-1992, BBox),
│                            # parser_2000.py (PL-2000), parser_tm33.py (CZ TM33),
│                            # parser_registry.py (rejestr systemow godel), geometry.py (SHP/GPKG)
├── sources/                 # DESKRYPTORY ZRODEL: descriptor.py, registry.py (PL/CZ/EU/GLOBAL),
│                            # sidecar.py (metadane <plik>.meta.json)
├── transform/               # TRANSFORMACJE CRS: crs.py (przypiete operacje pyproj)
├── transport/               # TRANSPORT: http.py (atomic download + retry),
│                            # mosaic.py (merge kafli + crop)
├── providers/               # WARSTWA DANYCH: base.py (BaseProvider, LandCoverProvider),
│   ├── pl/                  # GUGiK: gugik.py, gugik_nmpt.py, gugik_orto.py,
│   │                        # gugik_laz.py (WFS), bdot10k.py; fabryka create_nmt_provider()
│   ├── cuzk/                # CUZK (Czechy): client.py, sheets.py, dmr.py;
│   │                        # fabryka create_dmr_provider()
│   ├── corine.py            # CORINE z Copernicus (CLMS API + WMS)
│   └── soilgrids.py         # SoilGrids z ISRIC (WCS)
├── cache/                   # MetadataCache (SQLite WAL, TTL 7 dni)
├── download/                # DownloadManager (parallel), FileStorage
├── landcover/               # LandCoverManager (dispatch do providerow)
├── hydrology/               # HSGCalculator
├── auth/                    # Auth Proxy (CLMS): proxy.py, client.py
└── cli/                     # CLI per komenda: _parser.py (argparse) + parse_cmd.py,
                             # download_cmd.py, landcover_cmd.py, soilgrids_cmd.py,
                             # cache_cmd.py; commands.py to fasada zgodnosci + entry point
```

### Przeplywy danych

```
CLI → DownloadManager → GugikProvider → GUGiK API (WCS/OpenData) → FileStorage
CLI → DownloadManager → GugikNmptProvider → GUGiK API (WCS/OpenData) → FileStorage
CLI → DownloadManager → GugikOrtoProvider → GUGiK API (WCS/OpenData) → FileStorage
CLI → CuzkDmrProvider → CUZK ArcGIS REST (exportImage) / pliki openzu → FileStorage
      (przeplyw CZ omija DownloadManager — precedens LAZ, ADR-023)
CLI → GugikLazProvider → GUGiK WFS (discovery) → GUGiK OpenData (.laz) → pliki
CLI → LandCoverManager → Bdot10kProvider → GUGiK OpenData (ZIP; TERYT przez WMS GetFeatureInfo) → FileStorage
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
| GUGiK | LAZ (chmury punktow) | WFS (discovery) + OpenData | Brak | 30s / 60s |
| GUGiK | BDOT10k (GeoPackage) | OpenData (ZIP); TERYT przez WMS GetFeatureInfo | Brak | 120s / 30s (WMS TERYT) |
| CUZK | DMR 5G/4G (GeoTIFF/ZIP) | ArcGIS REST (query, exportImage) + pliki openzu | Brak | 60s |
| Copernicus CLMS | CORINE (GeoTIFF) | REST API | OAuth2 RSA | 60s |
| EEA Discomap | CORINE (PNG) | WMS | Brak | 60s |
| ISRIC SoilGrids | Gleba (GeoTIFF) | WCS | Brak | 120s (przez godlo: 60s) |

### Specyfika API

**GUGiK NMT:**
- OpenData: pobieranie przez godlo → ASC (1m i 5m)
- WCS: pobieranie przez bbox → GeoTIFF (tylko 1m i tylko KRON86 — endpoint
  EVRF2007 wycofany przez GUGiK, HTTP 404 od 2026-08; `download_bbox` pod
  EVRF2007 konczy sie `ValidationError`)
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
    # Cache
    MetadataCache,
    # Core
    SheetParser, Parser2000, ParserTM33, BBox,
    find_sheets_for_bbox, find_sheets_2000_for_bbox, find_sheets_for_geometry,
    # Download (NMT/NMPT/Orto/LAZ)
    DownloadManager, DownloadProgress, DownloadResult, FileStorage,
    # Land Cover
    LandCoverManager,
    # Providers
    BaseProvider, GugikProvider, GugikNmptProvider, GugikOrtoProvider,
    GugikLazProvider, LazTile,
    LandCoverProvider, Bdot10kProvider, CorineProvider, SoilGridsProvider,
    CuzkDmrProvider, create_dmr_provider,
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
# 2. Dziedzicz z LandCoverProvider (providers/base.py)
# 3. Zaimplementuj metody: download_by_admin_unit, download_by_bbox,
#    download_by_godlo (download_by_teryt to zdeprecjonowany alias z bazy)
# 4. Zarejestruj w slowniku modulowym PROVIDERS w kartograf/landcover/manager.py
# 5. Dodaj eksport do kartograf/__init__.py
# 6. Napisz testy w tests/test_nowy_provider.py
# 7. Dodaj argumenty CLI w cli/_parser.py i logike w module per komenda
#    (cli/*_cmd.py); cli/commands.py to tylko fasada zgodnosci
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
# 1. Zidentyfikuj provider (GugikProvider, GugikLazProvider, Bdot10kProvider,
#    CorineProvider, SoilGridsProvider, CuzkDmrProvider)
# 2. Sprawdz retry logic i timeout
# 3. Dodaj test reprodukujacy blad
# 4. Napraw i potwierdz testem
# 5. Sprawdz czy nie zepsules istniejacych testow
```

---

## 9. Ograniczenia techniczne

- **Pobieranie rownolegle** — ThreadPoolExecutor, domyslnie 4 workery (CLI: `--workers`)
- **NMT 5m** — tylko OpenData (ASC), brak WCS; wymaga EVRF2007
- **CORINE GeoTIFF** — wymaga OAuth2 credentials; bez nich fallback na PNG (WMS)
- **SoilGrids** — tylko WGS84 bbox (transformacja automatyczna)
- **Retry** — max 3 proby, exponential backoff (nie konfigurowalne)
- **Cache metadanych** — MetadataCache (SQLite WAL, TTL 7 dni); CLI: `kartograf cache stats|clear|path`
- **Mozaikowanie** — `transport/mosaic.py` (merge kafli + crop), uzywane m.in. dla kafelkowanych bboxow CZ (exportImage)
- **Pelna, aktualna lista ograniczen** (w tym CZ/CUZK etap 1) — CLAUDE.md, sekcja "Ograniczenia"

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
from pathlib import Path

from kartograf import HSGCalculator, SoilGridsProvider
calc = HSGCalculator()
hsg_path = calc.calculate_hsg_by_godlo("N-34-130-D", Path("./hsg.tif"))
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

**Wersja dokumentu:** 4.1
**Data ostatniej aktualizacji:** 2026-08-22
**Status:** Aktywny dla wszystkich asystentow AI pracujacych nad projektem
