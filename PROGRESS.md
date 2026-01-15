# Plan Implementacji Kartograf

**Repozytorium:** https://github.com/Daldek/Kartograf.git
**Status:** W trakcie implementacji
**Ostatnia aktualizacja:** 2026-01-15

---

## Szybki Start (dla powracającego dewelopera)

1. Sprawdź **"Aktualny Etap"** poniżej
2. Przeczytaj kryteria ukończenia dla tego etapu
3. Po ukończeniu: oznacz etap jako [x] i przejdź do następnego

---

## Aktualny Etap: 1 - Setup Projektu

**Status:** Do zrobienia

---

## Etapy Implementacji

### Etap 0: Inicjalizacja Git + PROGRESS.md (S - 10 min)
- [x] Ukończony

---

### Etap 1: Setup Projektu (S - 20 min)
- [ ] Ukończony

**Pliki do utworzenia:**
- `pyproject.toml` - konfiguracja projektu, entry points
- `requirements.txt` - requests>=2.31.0
- `requirements-dev.txt` - pytest, pytest-cov, black, flake8
- `.gitignore`
- `.flake8`
- `src/kartograf/__init__.py` (pusty)
- `tests/__init__.py` (pusty)

**Kryterium ukończenia:**
- `pip install -e .` działa
- `pytest tests/` uruchamia się
- Struktura katalogów utworzona

---

### Etap 2: Wyjątki (S - 15 min)
- [ ] Ukończony

**Pliki:**
- `src/kartograf/exceptions.py`
- `src/kartograf/core/__init__.py`

**Kryterium:** Import `from kartograf.exceptions import KartografError` działa

---

### Etap 3: Parser Godła - Podstawy (M - 45 min)
- [ ] Ukończony

**Pliki:**
- `src/kartograf/core/sheet_parser.py`
- `tests/test_sheet_parser.py`

**Kryterium:**
- `SheetParser("N-34-130-D-d-2-4")` parsuje poprawnie
- Walidacja formatu i układu
- Właściwości: `godlo`, `scale`, `uklad`, `components`
- Testy dla skal 1:1M do 1:10k

**Wzorce regex:**
```python
PATTERNS = {
    "1:1000000": r"^([A-Z])-(\d{1,2})$",
    "1:500000": r"^([A-Z])-(\d{1,2})-([A-D])$",
    "1:200000": r"^([A-Z])-(\d{1,2})-(\d{1,3})$",
    "1:100000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])$",
    "1:50000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-dA-D])$",
    "1:25000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-dA-D])-([1-4])$",
    "1:10000": r"^([A-Z])-(\d{1,2})-(\d{1,3})-([A-D])-([a-dA-D])-([1-4])-([1-4])$",
}
```

---

### Etap 4: Parser Godła - Hierarchia (M - 40 min)
- [ ] Ukończony

**Pliki:** Rozszerzenie `sheet_parser.py` i `test_sheet_parser.py`

**Metody do dodania:**
- `get_parent()` - arkusz nadrzędny
- `get_children()` - arkusze podrzędne
- `get_hierarchy_up()` - ścieżka do 1:1M
- `get_all_descendants(target_scale)` - wszystkie potomki

**UWAGA:** Podział 1:500k → 1:200k to **36 arkuszy**, nie 4!

---

### Etap 5: Provider Base (S - 25 min)
- [ ] Ukończony

**Pliki:**
- `src/kartograf/providers/__init__.py`
- `src/kartograf/providers/base.py`
- `src/kartograf/providers/gugik.py` (szkielet)

**Kryterium:** Abstrakcyjna klasa `BaseProvider` z metodami `construct_url()`, `download()`

---

### Etap 6: GugikClient - Pobieranie (M - 50 min)
- [ ] Ukończony

**Pliki:** Rozszerzenie `gugik.py`, `tests/test_gugik_client.py`

**Kryterium:**
- `construct_url(godlo, format)` generuje URL WCS
- `download()` z retry (3 próby, exponential backoff)
- Timeout 30s
- Testy z mock HTTP

**URL GUGiK:**
```python
BASE_URL = "https://mapy.geoportal.gov.pl"
WCS_GEOTIFF = f"{BASE_URL}/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
```

---

### Etap 7: Storage (S - 25 min)
- [ ] Ukończony

**Pliki:**
- `src/kartograf/download/__init__.py`
- `src/kartograf/download/storage.py`
- `tests/test_storage.py`

**Kryterium:**
- `FileStorage(output_dir)` klasa
- `get_path(godlo, ext)` → `data/N-34/130/D/d/2/4/N-34-130-D-d-2-4.tif`
- Atomic writes (tmp → rename)

---

### Etap 8: Download Manager (M - 50 min)
- [ ] Ukończony

**Pliki:**
- `src/kartograf/download/manager.py`
- `tests/test_download_manager.py`

**Kryterium:**
- `download_sheet(godlo, format)` - jeden arkusz
- `download_hierarchy(godlo, target_scale, format, on_progress)` - hierarchia
- Skip już pobranych plików
- Progress callback

---

### Etap 9: CLI - Parse (S - 30 min)
- [ ] Ukończony

**Pliki:**
- `src/kartograf/cli/__init__.py`
- `src/kartograf/cli/commands.py`
- `tests/test_cli.py`

**Kryterium:**
- `kartograf --help` działa
- `kartograf parse N-34-130-D` wyświetla info
- `kartograf parse N-34-130-D --hierarchy` wyświetla hierarchię

---

### Etap 10: CLI - Download (M - 35 min)
- [ ] Ukończony

**Pliki:** Rozszerzenie `commands.py`

**Kryterium:**
- `kartograf download N-34-130-D-d-2-4` pobiera arkusz
- `kartograf download N-34-130-D --scale 1:10000` pobiera hierarchię
- Opcje: `--format`, `--output`
- Progress bar w konsoli

---

### Etap 11: Public API (S - 15 min)
- [ ] Ukończony

**Pliki:** Wszystkie `__init__.py`

**Kryterium:** `from kartograf import SheetParser, DownloadManager` działa

---

### Etap 12: Testy Integracyjne (M - 40 min)
- [ ] Ukończony

**Pliki:**
- `tests/test_integration.py`
- `tests/conftest.py`

**Kryterium:** Pokrycie >= 80% dla core logic

---

### Etap 13: Dokumentacja (S - 20 min)
- [ ] Ukończony

**Pliki:**
- `README.md` - aktualizacja przykładów
- `CHANGELOG.md` - wersja 0.1.0

---

## Diagram Zależności

```
Etap 0 (Git) → Etap 1 (Setup) → Etap 2 (Wyjątki)
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
              Etap 3 (Parser)                     Etap 5 (Provider)
                    │                                   │
                    ▼                                   ▼
              Etap 4 (Hierarchia)                 Etap 6 (GugikClient)
                    │                                   │
                    ▼                                   │
              Etap 7 (Storage)                          │
                    │                                   │
                    └─────────────┬─────────────────────┘
                                  ▼
                            Etap 8 (Manager)
                                  │
                                  ▼
                         Etap 9-10 (CLI)
                                  │
                                  ▼
                         Etap 11-13 (Finalizacja)
```

---

## Komendy Pomocnicze

```bash
# Aktywacja środowiska
source .venv/bin/activate

# Testy
pytest tests/ -v
pytest tests/ --cov=src/kartograf --cov-report=html

# Formatowanie i linting
black src/ tests/
flake8 src/ tests/ --max-line-length=88

# Instalacja w trybie dev
pip install -e .
```

---

## Pliki Krytyczne

1. `src/kartograf/core/sheet_parser.py` - parser godeł
2. `src/kartograf/providers/gugik.py` - integracja z GUGiK
3. `src/kartograf/download/manager.py` - zarządzanie pobieraniem
4. `src/kartograf/cli/commands.py` - interfejs CLI
5. `pyproject.toml` - konfiguracja projektu

---

## Uwagi

- **Podział 1:500k → 1:200k:** 36 arkuszy (nie 4!)
- **URL WCS:** może wymagać weryfikacji z API GUGiK
- **Testy:** zawsze uruchamiaj przed commitem
