# Design: v0.6 — PL-2000 Verification, Parallel Downloads, Metadata Cache

**Data:** 2026-03-03
**Wersja docelowa:** v0.6.0
**Organizacja:** 3 zespoly po 5 subagentow + zespol merge (3 agenty)

---

## 1. Architektura ogolna

### Worktree i branche

```
main
 └── develop  (base dla wszystkich 3 feature branches)
      ├── feature/pl2000-verification   ← WT1 — Zespol Weryfikacja (5 agentow)
      ├── feature/parallel-downloads    ← WT2 — Zespol Parallel (5 agentow)
      └── feature/metadata-cache        ← WT3 — Zespol Cache (5 agentow)
```

Kazdy worktree tworzony przez `git worktree add` od `develop`.
Wszystkie 3 zespoly pracuja **rownolegle**.

### Kolejnosc merge (po zakonczeniu prac)

1. `feature/pl2000-verification` → `develop` (czysto addytywny — nowe testy)
2. `feature/metadata-cache` → `develop` (nowy modul + male zmiany w providers)
3. `feature/parallel-downloads` → `develop` (modyfikuje manager + providers + CLI)

### Nowe pliki/moduly

```
kartograf/
├── cache/
│   ├── __init__.py
│   └── metadata.py          ← MetadataCache (SQLite)
├── download/
│   └── manager.py            ← +ThreadPoolExecutor, +max_workers param
tests/
├── test_pl2000_verification.py   ← offline + live BBox tests
├── test_metadata_cache.py        ← cache unit tests
├── test_parallel_download.py     ← parallel download tests
```

---

## 2. Kontekst startowy dla wszystkich zespolow

### Srodowisko Python

- Python: `.venv/bin/python`
- Pip: `.venv/bin/pip`
- Pytest: `.venv/bin/python -m pytest tests/ -v`
- Ruff lint: `.venv/bin/python -m ruff check kartograf/ tests/`
- Ruff format: `.venv/bin/python -m ruff format kartograf/ tests/`
- Mypy: `.venv/bin/python -m mypy kartograf/`
- CLI: `.venv/bin/kartograf`

### Dostepne narzedzia i pluginy

Kazdy subagent ma dostep do:

- **Read** — czytanie plikow (uzywaj zamiast `cat`)
- **Write** — tworzenie nowych plikow
- **Edit** — edycja istniejacych plikow (uzywaj zamiast `sed`)
- **Glob** — wyszukiwanie plikow po wzorcu (uzywaj zamiast `find`)
- **Grep** — wyszukiwanie w tresci plikow (uzywaj zamiast `grep`/`rg`)
- **Bash** — komendy systemowe, git, pytest, ruff
- **Agent** — delegowanie podzadan do sub-agentow
- **WebFetch** — pobieranie tresci z URL (do live testow WMS)
- **WebSearch** — wyszukiwanie w internecie (do dokumentacji GUGiK)

### Pluginy/skille

- **superpowers:test-driven-development** — TDD workflow (RED → GREEN → REFACTOR)
- **superpowers:systematic-debugging** — debugging bledow i test failures
- **superpowers:verification-before-completion** — weryfikacja przed zgloszeniem ukonczenia
- **superpowers:code-review** — code review po ukonczeniu pracy
- **simplify** — review kodu pod katem reuse i jakosci

### Wymagania startowe

1. **Branch:** Kazdy zespol MUSI pracowac na swoim feature branch odcietym od `develop`
2. **Testy:** Przed commitem uruchom `pytest tests/ -v` — WSZYSTKIE testy musza przechodzic
3. **Linter:** Przed commitem uruchom `ruff check` i `ruff format --check`
4. **Commity:** Conventional Commits (`feat(...)`, `test(...)`, `fix(...)`)
5. **Istniejace testy:** 835 testow — NIE modyfikuj istniejacych testow chyba ze zmiana jest konieczna
6. **CLAUDE.md:** Przeczytaj i stosuj sie do wytycznych

### Zaleznosci juz zainstalowane

- requests >= 2.31.0
- pyproj >= 3.6.0
- PyJWT[crypto] >= 2.8.0
- rasterio >= 1.3.0
- numpy >= 1.24.0
- pyshp >= 2.3.0
- ruff (dev)
- pytest, pytest-cov (dev)

### Kluczowe pliki do przeczytania na start

- `CLAUDE.md` — instrukcje projektu
- `docs/PROGRESS.md` — aktualny stan
- `docs/DECISIONS.md` — decyzje architektoniczne
- `kartograf/__init__.py` — public API exports

---

## 3. Zespol 1 — Weryfikacja PL-2000 BBox

### Cel
Potwierdzic poprawnosc `Parser2000._calculate_native_bbox()` i `find_sheets_2000_for_bbox()` wzgledem oficjalnych danych GUGiK.

### Branch: `feature/pl2000-verification` (od `develop`)

### Agent 1A — Offline testy BBox (reference values)

- Zebrac znane BBox-y arkuszy PL-2000 z dokumentacji GUGiK / instrukcji technicznej K-1
- Stworzyc parametryzowane testy (`@pytest.mark.parametrize`) porownujace `Parser2000(godlo).get_bbox()` z reference values
- Minimum 20 arkuszy: po 5 na strefe (5,6,7,8), rozne skale (1:10k, 1:5k, 1:2k)
- Tolerancja porownania: 0.01m (sub-centymetrowa precyzja)
- Plik: `tests/test_pl2000_verification.py`

### Agent 1B — Offline testy hierarchii i children

- Testy `get_children()` — czy suma BBox-ow dzieci pokrywa dokladnie BBox rodzica
- Testy `get_all_descendants()` — spojnosc hierarchii (zaden potomek nie wychodzi poza BBox przodka)
- Testy granicy stref — arkusze na 16.5°E, 19.5°E, 22.5°E (granice stref 5/6, 6/7, 7/8)
- Property-based: losowy BBox → `find_sheets_2000_for_bbox()` → kazdy znaleziony arkusz ma BBox przecinajacy sie z query BBox
- Plik: `tests/test_pl2000_verification.py` (osobne klasy testowe)

### Agent 1C — Live testy WMS (@pytest.mark.live)

- Testy oznaczone `@pytest.mark.live` (domyslnie pomijane, uruchamiane `pytest -m live`)
- Zapytania do GUGiK WMS `GetFeatureInfo` — sprawdzenie czy dla obliczonego srodka BBox GUGiK zwraca dane
- Porownanie: center point z `Parser2000` vs center point z odpowiedzi WMS (tolerancja 100m)
- 8-12 arkuszy (po 2-3 na strefe), timeout 30s, graceful skip gdy serwer niedostepny
- Plik: `tests/test_pl2000_verification.py` (klasa `TestPL2000Live`)
- Dodac `live` marker do `conftest.py`: `pytest.ini` lub `pyproject.toml`

### Agent 1D — Edge cases i multi-zone

- Arkusze na skraju Polski (polnoc: pas max, poludnie: pas min, wschod: strefa 8, zachod: strefa 5)
- Multi-zone BBox: BBox przecinajacy 2 strefy → `find_sheets_2000_for_bbox()` zwraca arkusze z obu stref
- Walidacja bledow: niepoprawne godla, strefa poza zakresem, ark_2k > 25
- Test round-trip: godlo → BBox → `find_sheets_2000_for_bbox(bbox)` → lista zawiera oryginalne godlo
- Plik: `tests/test_pl2000_verification.py` (klasa `TestPL2000EdgeCases`)

### Agent 1V — Weryfikacja poprawnosci

- Uruchom pelny test suite: `pytest tests/ -v` — 835 istniejacych + nowe testy
- Sprawdz `ruff check` i `ruff format --check`
- Zweryfikuj ze nowe testy nie modyfikuja istniejacych plikow zrodlowych (tylko testy!)
- Review kodu: czytelnosc, konwencje nazewnicze, parametryzacja
- Sprawdz pokrycie: `pytest tests/ --cov=kartograf --cov-report=term-missing`
- Raport: lista ewentualnych problemow do naprawienia przed merge

---

## 4. Zespol 2 — Parallel Downloads

### Cel
Zmienic sekwencyjne pobieranie na rownolegle z konfigurowalna liczba watkow.

### Branch: `feature/parallel-downloads` (od `develop`)

### Agent 2A — DownloadManager parallelizacja

- `concurrent.futures.ThreadPoolExecutor` w `download_hierarchy()`
- Nowy parametr `max_workers=4` (domyslnie 4, konfigurowalne)
- Thread-safe progress reporting: `threading.Lock` wokol callback-a
- Nowa metoda `download_sheets(godla_list, ...)` — parallel download listy arkuszy
- Graceful shutdown: `executor.shutdown(wait=True)`, `KeyboardInterrupt` handling
- `DownloadResult` dataclass: `succeeded: list[Path]`, `failed: list[str]`, `skipped: list[str]`
- Backward compatible: `max_workers=1` → sekwencyjne (stare zachowanie)
- Plik: `kartograf/download/manager.py`

### Agent 2B — Thread-safety providers NMT/NMPT/Orto

- `requests.Session()` per-thread (nie shared) — tworzony w kazdym task-u
- Weryfikacja `FileStorage.write_atomic()` — juz atomowe (tmp+rename), sprawdzic thread-safety nazw tmp
- `_get_opendata_url()` — stateless HTTP GET, bezpieczne do wywolywania rownolegle
- Dodac `_create_session()` method do GugikProvider (factory per-thread)
- Testy: 10 rownoleg\u0142ych downloads z mock-owanym providerem, weryfikacja brak race conditions
- Plik: `kartograf/providers/gugik.py`, `tests/test_parallel_download.py`

### Agent 2C — LandCover providers parallelizacja

- `LandCoverManager` — nowy `download_batch(items, max_workers=4)` z ThreadPoolExecutor
- `Bdot10kProvider` — wielu powiatow rownolegle (kazdy `download_by_teryt()` w osobnym watku)
- `SoilGridsProvider` — wielu properties/depths rownolegle
- `CorineProvider` — WMS fallback mozna parallel; CLMS jest inherently serial (server-side async task)
- SQLite operations w BDOT10k merge (`_merge_gpkg_files`) — per-file, nie trzeba lockow
- Pliki: `kartograf/landcover/manager.py`, `kartograf/providers/bdot10k.py`, `kartograf/providers/soilgrids.py`

### Agent 2D — CLI + progress + testy

- CLI: `--workers N` (domyslnie 4) w `download` i `landcover download`
- `--workers 1` — wymusza sekwencyjne pobieranie (backward compat)
- Live progress: `DownloadProgress` callback z thread-safe counter + lock
- Testy: mock-based parallel download tests, weryfikacja poprawnej liczby watkow
- Aktualizacja `CHANGELOG.md`
- Pliki: `kartograf/cli/commands.py`, `tests/test_cli.py`, `tests/test_parallel_download.py`

### Agent 2V — Weryfikacja poprawnosci

- Uruchom pelny test suite: `pytest tests/ -v` — wszystkie testy musza przechodzic
- Sprawdz `ruff check` i `ruff format --check`
- **Test thread-safety:** uruchom testy parallel z `-x` (fail fast) kilka razy
- Review: czy `max_workers=1` zachowuje dokladnie stare zachowanie (backward compat)?
- Review: czy KeyboardInterrupt jest obsluzony (brak zombie threads)?
- Review: czy progress callback jest thread-safe?
- Sprawdz pokrycie: `pytest tests/ --cov=kartograf --cov-report=term-missing`
- Raport: lista ewentualnych problemow

### Kluczowe decyzje implementacyjne

- `ThreadPoolExecutor` (nie asyncio) — prostsze, requests jest synchroniczny
- Session per-thread — unikamy shared state
- `max_workers=4` domyslnie — kompromis szybkosc vs obciazenie serwera
- Brak rate-limitingu na start — mozna dodac pozniej

---

## 5. Zespol 3 — Metadata Cache (SQLite)

### Cel
Lokalny SQLite cache eliminujacy powtarzajace sie zapytania WMS o metadane.

### Branch: `feature/metadata-cache` (od `develop`)

### Schema bazy

```sql
CREATE TABLE IF NOT EXISTS url_cache (
    godlo TEXT NOT NULL,
    resolution TEXT NOT NULL,
    vertical_crs TEXT NOT NULL,
    product TEXT NOT NULL DEFAULT 'nmt',
    url TEXT NOT NULL,
    cached_at REAL NOT NULL,
    PRIMARY KEY (godlo, resolution, vertical_crs, product)
);

CREATE TABLE IF NOT EXISTS teryt_cache (
    x REAL NOT NULL,
    y REAL NOT NULL,
    teryt TEXT NOT NULL,
    cached_at REAL NOT NULL,
    PRIMARY KEY (x, y)
);

CREATE TABLE IF NOT EXISTS bbox_cache (
    godlo TEXT PRIMARY KEY,
    system TEXT NOT NULL,
    min_x REAL NOT NULL,
    min_y REAL NOT NULL,
    max_x REAL NOT NULL,
    max_y REAL NOT NULL,
    crs TEXT NOT NULL,
    cached_at REAL NOT NULL
);
```

### Agent 3A — MetadataCache klasa + schema

- `kartograf/cache/__init__.py` — eksport MetadataCache
- `kartograf/cache/metadata.py` — klasa `MetadataCache`
- Konstruktor: `MetadataCache(db_path=None, ttl_days=7)`
- Domyslna sciezka: `{output_dir}/.kartograf_cache.db`
- Metody: `get_url()`, `set_url()`, `get_teryt()`, `set_teryt()`, `get_bbox()`, `set_bbox()`
- TTL: 7 dni domyslnie — `cached_at + ttl < time.time()` → stale
- Thread-safe: `sqlite3` z `check_same_thread=False` + WAL mode (`PRAGMA journal_mode=WAL`)
- `clear()` — usun wszystkie wpisy
- `vacuum()` — odzyskaj miejsce
- `stats()` → dict z liczba wpisow per tabela, rozmiarem pliku
- `close()` — zamknij polaczenie
- Pliki: `kartograf/cache/metadata.py`, `kartograf/cache/__init__.py`

### Agent 3B — Integracja z GugikProvider (NMT/NMPT/Orto)

- `GugikProvider.__init__()` — nowy opcjonalny parametr `cache=None`
- `_get_opendata_url()` — sprawdz cache → hit: zwroc URL; miss: zapytaj WMS → zapisz w cache
- Klucz cache: `(godlo, resolution, vertical_crs, product_name)`
- GugikNmptProvider i GugikOrtoProvider — dziedzicza cache z GugikProvider
- Backward compatible: `cache=None` → bez cache (domyslne zachowanie)
- Testy: mock cache, weryfikacja cache hit/miss, weryfikacja ze WMS NIE jest wolane przy hit
- Pliki: `kartograf/providers/gugik.py`, `kartograf/providers/gugik_nmpt.py`, `kartograf/providers/gugik_orto.py`

### Agent 3C — Integracja z LandCover providers

- `Bdot10kProvider` — cache TERYT lookup (`_get_teryt_for_point()` → `cache.get_teryt(x, y)`)
- `SoilGridsProvider` — opcjonalny cache (mniejszy zysk, ale spojnosc API)
- `CorineProvider` — bez cache (CLMS task URLs sa jednorazowe)
- Kazdy provider: opcjonalny `cache` parametr w konstruktorze
- LandCoverManager: przekazuje `cache` do providerow (jesli dostepny)
- Pliki: `kartograf/providers/bdot10k.py`, `kartograf/providers/soilgrids.py`, `kartograf/landcover/manager.py`

### Agent 3D — CLI + TTL + testy + invalidacja

- CLI: `kartograf cache stats` — wyswietl statystyki (rozmiar, wpisy, hit ratio)
- CLI: `kartograf cache clear` — wyczysc cache
- CLI: `kartograf cache path` — wyswietl sciezke do pliku cache
- Nowy subparser `cache` w `kartograf/cli/commands.py`
- Testy: pelne unit testy MetadataCache (CRUD, TTL expiry, thread-safety z WAL)
- Testy integracyjne: provider + cache end-to-end (mock HTTP, real SQLite)
- Aktualizacja `CHANGELOG.md`
- Pliki: `kartograf/cli/commands.py`, `tests/test_metadata_cache.py`, `tests/test_cli.py`

### Agent 3V — Weryfikacja poprawnosci

- Uruchom pelny test suite: `pytest tests/ -v`
- Sprawdz `ruff check` i `ruff format --check`
- **Test TTL:** sprawdz ze expired entries nie sa zwracane
- **Test WAL:** sprawdz ze concurrent reads dzialaja poprawnie
- Review: czy cache jest opt-in (nie zmienia domyslnego zachowania)?
- Review: czy cache file jest w .gitignore?
- Sprawdz pokrycie: `pytest tests/ --cov=kartograf --cov-report=term-missing`
- Raport: lista ewentualnych problemow

### Kluczowe decyzje

- SQLite WAL mode — concurrent reads + single writer
- TTL 7 dni — URLe OpenData rzadko sie zmieniaja
- Cache jest opt-in (domyslnie wylaczony w providerach, wlaczany przez CLI/DownloadManager)
- Plik cache w `.gitignore`

---

## 6. Zespol Merge

### Po zakonczeniu prac 3 zespolow

Kolejnosc merge (minimalizacja konfliktow):

1. **`feature/pl2000-verification` → `develop`** — czyste addycje, FF merge
2. **`feature/metadata-cache` → `develop`** — nowy modul + male zmiany w providers
3. **`feature/parallel-downloads` → `develop`** — najwiekszy diff, konflikty z cache

### Sklad zespolu (3 agenty)

- **Agent M1** — merge + rozwiazywanie konfliktow
  - Git merge z `--no-ff` (zachowaj historie)
  - Rozwiaz konflikty w providers/ (cache + parallel dotykaja tych samych plikow)
  - Upewnij sie ze parallel downloads korzysta z cache (integracja)

- **Agent M2** — pelny test suite po kazdym merge
  - `pytest tests/ -v` po kazdym merge
  - `ruff check` + `ruff format --check`
  - Jesli testy padaja — napraw i re-merge

- **Agent M3** — dokumentacja i finalizacja
  - Aktualizacja `CHANGELOG.md` (wpis v0.6.0)
  - Aktualizacja `docs/PROGRESS.md` (nowy checkpoint CP9)
  - Aktualizacja `docs/DECISIONS.md` (ADR-018: parallel downloads, ADR-019: metadata cache)
  - `develop` → `main` merge (po zatwierdzeniu)

---

## 7. Metryki sukcesu

- [ ] Wszystkie istniejace 835 testow nadal przechodza
- [ ] Nowe testy PL-2000: minimum 40 testow (offline + live)
- [ ] Parallel downloads: `max_workers=1` zachowuje stare zachowanie
- [ ] Parallel downloads: `max_workers=4` przyspiesza pobieranie (test z mock)
- [ ] Cache: TTL dziala poprawnie (expired entries nie sa zwracane)
- [ ] Cache: thread-safe (WAL mode, concurrent reads)
- [ ] Ruff: zero bledow lint + format
- [ ] Pokrycie testami: >= 80% (cel utrzymany)
- [ ] CLI: `--workers` i `kartograf cache` dzialaja poprawnie
