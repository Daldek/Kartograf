# Instrukcje dla Claude Code

## Opis projektu

Kartograf — narzedzie do pobierania danych przestrzennych (NMT z GUGiK, BDOT10k, CORINE z Copernicus, SoilGrids z ISRIC) dla Polski. Dostepny jako CLI i biblioteka Python. Czesc toolchainu hydrologicznego (Hydrograf, Hydrolog, Kartograf, IMGWTools).

Glowne funkcjonalnosci:
- **NMT** — pobieranie Numerycznego Modelu Terenu z GUGiK (1m i 5m)
- **BDOT10k** — polska baza pokrycia terenu (12 warstw PT*)
- **CORINE Land Cover** — europejska klasyfikacja pokrycia terenu (44 klasy)
- **SoilGrids** — globalne dane glebowe z ISRIC (11 parametrow, 6 glebokosci)
- **HSG** — kalkulacja Hydrologic Soil Groups dla metody SCS-CN

## Srodowisko Python

Uzywaj srodowiska wirtualnego z `.venv`:
- Python: `.venv/bin/python`
- Pip: `.venv/bin/pip`
- Wymagany Python: 3.12+

Zmienne srodowiskowe (opcjonalne):
- `CLMS_CLIENT_ID` — client ID dla Copernicus CLMS API (potrzebne do CORINE GeoTIFF)
- `CLMS_CLIENT_SECRET` — client secret dla CLMS API

Bez zmiennych CLMS: CORINE automatycznie pobiera podglad PNG przez WMS (fallback).

## Dokumentacja

**Przeczytaj w kolejnosci:**
1. `docs/PROGRESS.md` — aktualny stan projektu i zadania
2. `docs/SCOPE.md` — zakres projektu (co jest, czego nie ma)
3. `docs/PRD.md` — wymagania produktowe
4. `docs/CHANGELOG.md` — historia zmian per-release
5. `docs/DECISIONS.md` — rejestr decyzji architektonicznych (co i dlaczego)

## Struktura modulow

```
kartograf/
├── __init__.py          # Public API exports
├── exceptions.py        # KartografError, ParseError, ValidationError, DownloadError
├── core/                # Logika bazowa
│   └── sheet_parser.py  # SheetParser — parser godel map topograficznych, BBox
├── providers/           # Providery danych (abstrakcje nad API)
│   ├── base.py          # BaseProvider — abstrakcja dla NMT
│   ├── gugik.py         # GugikProvider — NMT z GUGiK (WCS + OpenData)
│   ├── landcover_base.py # LandCoverProvider — abstrakcja dla pokrycia terenu
│   ├── bdot10k.py       # Bdot10kProvider — BDOT10k z GUGiK
│   ├── corine.py        # CorineProvider — CORINE z Copernicus (CLMS API + WMS)
│   └── soilgrids.py     # SoilGridsProvider — dane glebowe z ISRIC (WCS)
├── download/            # Zarzadzanie pobieraniem NMT
│   ├── manager.py       # DownloadManager — koordynacja pobierania arkuszy
│   └── storage.py       # FileStorage — hierarchiczna struktura katalogow
├── landcover/           # Zarzadzanie pobieraniem pokrycia terenu
│   └── manager.py       # LandCoverManager — dispatch do providerow
├── hydrology/           # Obliczenia hydrologiczne
│   └── hsg.py           # HSGCalculator — klasyfikacja USDA, mapowanie HSG
├── auth/                # Autentykacja CLMS (Auth Proxy)
│   ├── proxy.py         # Serwer HTTP izolujacy credentials (subprocess)
│   └── client.py        # Klient singleton, automatycznie uruchamia proxy
└── cli/                 # Interfejs wiersza polecen
    └── commands.py      # Komendy CLI (parse, download, landcover, soilgrids)
```

## Komendy

```bash
# Testy
.venv/bin/python -m pytest tests/ -v

# Testy z pokryciem
.venv/bin/python -m pytest tests/ --cov=kartograf --cov-report=html

# Linter
.venv/bin/python -m ruff check kartograf/ tests/

# Formatowanie
.venv/bin/python -m ruff format kartograf/ tests/

# Sprawdzenie formatowania (bez zmian)
.venv/bin/python -m ruff format --check kartograf/ tests/

# Type checking
.venv/bin/python -m mypy kartograf/

# CLI
kartograf --help
kartograf parse N-34-130-D-d-2-4
kartograf download N-34-130-D-d-2-4
kartograf download N-34-130-D --scale 1:10000 --resolution 5m
kartograf landcover download --source bdot10k --teryt 1465
kartograf landcover download --source corine --year 2018 --godlo N-34-130-D
kartograf landcover download --source soilgrids --godlo N-34-130-D --property soc
kartograf soilgrids hsg --godlo N-34-130-D --stats
kartograf landcover list-sources
kartograf landcover list-layers --source soilgrids
```

## Workflow sesji

### Poczatek sesji
1. Przeczytaj `docs/PROGRESS.md` — sekcja "Ostatnia sesja"
2. `git status` + `git log --oneline -5`
3. Sprawdz na ktorej jestes galezi (`git branch --show-current`)

### W trakcie sesji
- Commituj czesto (male zmiany)
- Aktualizuj `docs/CHANGELOG.md` na biezaco
- W razie watpliwosci — pytaj

### Koniec sesji
**OBOWIAZKOWO zaktualizuj** `docs/PROGRESS.md`:
- Co zostalo zrobione
- Co jest w trakcie (plik, linia, kontekst)
- Nastepne kroki

### Git Workflow

**Galecie:**
- **main** — stabilna wersja (tylko merge z develop)
- **develop** — aktywny rozwoj (ZAWSZE pracuj na tej galezi)

**Commity:** Conventional Commits (`feat(parser): ...`, `fix(download): ...`, `docs(readme): ...`)

## Specyfika projektu

### Zaleznosci zewnetrzne
- **requests** >= 2.31.0 — HTTP client (wymagane)
- **pyproj** >= 3.6.0 — transformacje CRS (wymagane)
- **PyJWT[crypto]** >= 2.8.0 — OAuth2 JWT dla CLMS API (wymagane)
- **rasterio** >= 1.3.0 — przetwarzanie rastrow GeoTIFF (wymagane)
- **numpy** >= 1.24.0 — operacje na tablicach (wymagane)

### Integracje
- Kartograf jest uzywany przez **Hydrograf** jako zrodlo danych GIS (NMT, Land Cover)
- Kartograf jest uzywany przez **Hydrolog** opcjonalnie (HSGCalculator, SoilGridsProvider)
- Kartograf NIE zawiera obliczen hydrologicznych (poza HSG) — to zadanie Hydrolog
- Kartograf NIE zawiera danych obserwacyjnych — to zadanie IMGWTools

### Ograniczenia
- Pobieranie jest synchroniczne (brak async/parallel) — zaplanowane na v0.4+
- NMT 5m dostepne tylko w ukladzie EVRF2007
- WCS (download_bbox) niedostepne dla NMT 5m — tylko arkusze OpenData
- CORINE GeoTIFF wymaga OAuth2 credentials w CLMS — bez nich fallback na PNG (WMS)
- SoilGrids: tylko WGS84 bbox (transformacja z EPSG:2180 automatyczna)
- Timeout: 30s dla GUGiK, 60s dla Land Cover
- Max 3 proby retry (nie konfigurowalne)
