# Zad. 7: `DownloadManager.expand_sheets()` + `download_sheets()` — raport implementacji

Commit: `3ce32a1` (na `2856f41`, HEAD-1)
`feat(download): DownloadManager.download_sheets/expand_sheets — lista arkuszy z porazkami w last_result`

## Co zrobiono

1. `kartograf/download/manager.py` — dwie nowe metody dopisane dokladnie po `download_hierarchy`, przed `_download_single_sheet_task` (tresc z briefu, doslownie, bez odejsc):
   - `DownloadManager.expand_sheets(godla: list[str]) -> list[str]` (`@staticmethod`) — dla kazdego godla: `SheetParser(godlo)`; jesli `uklad != "2000"` i `scale != "1:10000"` — rozwiniecie przez `get_all_descendants("1:10000")` (lista `.godlo`); inaczej jeden lisc (`parser.godlo`, znormalizowany). Dedup przez `set` + lista wynikowa w kolejnosci pierwszego wystapienia.
   - `DownloadManager.download_sheets(godla, skip_existing=True, on_progress=None, max_workers=None) -> list[Path]` — `self.last_result = None`; `leaves = [SheetParser(g) for g in self.expand_sheets(godla)]` (cale rozwiniecie/parsowanie PRZED wejsciem w pobieranie — to ten fragment gwarantuje "ParseError przed jakimkolwiek pobraniem"); potem dispatch do istniejacych `_download_hierarchy_sequential`/`_download_hierarchy_parallel` (te same helpery co `download_hierarchy`, z Zad. 6 wlacznie z obsluga `NoCoverageError`/`no_coverage`) — zero duplikacji logiki pobierania/postepu/last_result.
2. `tests/test_download_manager.py` — nowa klasa `TestDownloadManagerDownloadSheets` (7 testow: `test_expand_sheets_leaves_dedup_order`, `test_expands_coarse_and_dedupes[1]`/`[4]`, `test_failures_collected_not_raised[1]`/`[4]`, `test_skip_existing`, `test_invalid_godlo_raises_before_any_download`) — tresc z briefu doslownie, wstawiona po `TestDownloadResultNoCoverage` (przed `TestDownloadManagerDownloadBbox`). `ruff format` przelamal jedna asercje (`sorted(manager.last_result.failed) == [...]`) na wiele linii (E501) — tresc bez zmian.
3. `docs/CHANGELOG.md` — bullet z briefu dopisany na poczatku `### Added` w `[0.7.0] - Unreleased` (przed bulletem `NoCoverageError` z Zad. 6, ten sam wzorzec "najnowsze na gorze" co Zad. 6 zastosowal wobec Zad. 5).

Zadne odejscie od kotwic z briefu — kod wstawiany "po `download_hierarchy`" pokrywal sie z aktualnym stanem `manager.py` (HEAD `2856f41`, bez zmian od Zad. 6).

## RED (przed implementacja)

```
.venv/bin/python -m pytest tests/test_download_manager.py::TestDownloadManagerDownloadSheets -v
```
```
tests/test_download_manager.py::TestDownloadManagerDownloadSheets::test_expand_sheets_leaves_dedup_order FAILED
  AttributeError: type object 'DownloadManager' has no attribute 'expand_sheets'
tests/test_download_manager.py::TestDownloadManagerDownloadSheets::test_expands_coarse_and_dedupes[1] FAILED
  AttributeError: 'DownloadManager' object has no attribute 'download_sheets'. Did you mean: 'download_sheet'?
... (5 kolejnych analogicznych)
=========================== 7 failed in 0.43s ===============================
```

## GREEN (po implementacji)

```
.venv/bin/python -m pytest tests/test_download_manager.py::TestDownloadManagerDownloadSheets -v
```
```
7 passed in 0.28s
```

Pelna suita offline:
```
.venv/bin/python -m pytest tests/ -q -m "not live"
```
```
1806 passed, 8 deselected in 26.99s
```
Punkt startowy (kontroler, Zad. 6): 1799 passed. Przybylo 7 testow (dokladnie te dopisane w kroku 1) → 1806. Zgadza sie.

## ruff / mypy

- `ruff check kartograf/ tests/`: pierwszy przebieg — 1 blad `E501` (linia 93 znakow w nowym tescie, przewidziane przez `IMPLEMENTER_COMMON.md` p.3). Po `ruff format kartograf/ tests/` (1 plik przeformatowany: `tests/test_download_manager.py`, tylko zawiniecie listy w `test_failures_collected_not_raised`, tresc bez zmian): `All checks passed!`.
- `ruff format --check kartograf/ tests/`: `86 files already formatted`.
- `mypy kartograf/`: `Found 32 errors in 9 files`. Diff listy wzgledem `.superpowers/sdd/2026-09-28-fala-review-max-i-wycinek-biblioteczny/mypy-baseline.txt` (obie strony przez `grep ': error:' | sed -E 's/:[0-9]+: /: /' | sort`): **0 different, 0 new, 0 fixed** — listy identyczne (32/32).

## Dowody mutacyjne (wszystkie PO commicie `3ce32a1`, przywracane `git checkout -- kartograf/download/manager.py`)

1. **`expand_sheets`: usuniecie dedup** (`if leaf not in seen: seen.add(leaf); leaves.append(leaf)` → zawsze `leaves.append(leaf)`):
   `pytest tests/test_download_manager.py::TestDownloadManagerDownloadSheets -v`
   → **3 failed, 4 passed**: `test_expand_sheets_leaves_dedup_order` (`AssertionError`, dodatkowy duplikat `'N-34-130-D-d-2-4'` w liscie), `test_expands_coarse_and_dedupes[1]` i `[4]` (`assert 6 == 4` — trzy razy `.../N-34-130-D-d-2-4.asc` w zwroconej liscie). Zgadza sie z pre-flight kontrolera ("mutation (1) FAILs 3 tests"). Przywrocono `git checkout -- kartograf/download/manager.py`, `git status --short` puste (czysty), 7/7 PASSED.

2. **Leniwe rozwijanie per-godlo** (zamiast `leaves = [SheetParser(g) for g in self.expand_sheets(godla)]` przed petla pobierania — petla `for g in godla: for leaf_godlo in self.expand_sheets([g]): ...pobierz od razu...`, wiec `ParseError` dla drugiego godla wypada PO pobraniu pierwszego):
   `pytest tests/test_download_manager.py::TestDownloadManagerDownloadSheets::test_invalid_godlo_raises_before_any_download -v`
   → FAIL: `AssertionError: assert ['N-34-130-D-d-2-1'] == []` (pierwszy godlo zdazyl sie pobrac, zanim `expand_sheets(["XYZ"])` rzucil `ParseError`). Przywrocono, `git status --short` puste, 7/7 PASSED.

3. **`_download_hierarchy_sequential`: cialo `except DownloadError as e:` → `raise`** (usuniete `result.failed.append(...)` + `on_progress(...)`):
   `pytest "tests/test_download_manager.py::TestDownloadManagerDownloadSheets::test_failures_collected_not_raised" -v`
   → `[1]` **FAILED** (`kartograf.exceptions.DownloadError: blad N-34-130-D-d-2-1` propaguje nieprzechwycony z `download_sheets`), `[4]` **PASSED** (tor rownolegly nietkniety ta mutacja — `_download_single_sheet_task` przechwytuje `DownloadError` sam, niezaleznie od `_download_hierarchy_sequential`; ogolny `except Exception` w `_download_hierarchy_parallel` obsluguje future, do ktorego ta mutacja w ogole nie dociera). Dokladnie zgodne z adnotacja P-06 w briefie i z pre-flight kontrolera. Przywrocono, `git status --short` puste, 7/7 PASSED.

Wszystkie 3 mutacje z briefu daly FAIL dokladnie tam, gdzie przewidywal brief/pre-flight kontrolera; zaden test nie okazal sie "znaleziskiem" (test broniacy niczego) — kazda mutacja zostala wykryta przez co najmniej jeden wariant testu, a rozbieznosc `[1]`/`[4]` w mutacji 3 byla jawnie przewidziana (P-06), nie jest usterka testu.

## Zmierzone liczby

- Testy offline: 1806 passed, 8 deselected (`-m live`) — start 1799 (kontroler/Zad. 6), +7 nowych (dokladnie tyle, ile dopisano w Step 1).
- Testy `test_download_manager.py` (skupione): 71 passed (64 sprzed Zad. 7 + 7 nowych).
- mypy: 32/32 bledow, lista identyczna z baseline (0 nowych, 0 naprawionych).
- ruff check: 0 bledow po `ruff format`; ruff format --check: 86/86 plikow sformatowanych.

## Pliki

- `kartograf/download/manager.py` (+67 linii: `expand_sheets` + `download_sheets`)
- `tests/test_download_manager.py` (+73 linie: `TestDownloadManagerDownloadSheets`)
- `docs/CHANGELOG.md` (+4 linie w `### Added`)

## Samoocena i watpliwosci

- Zgodnosc z briefem: pelna — kod, testy i tresc CHANGELOG przepisane doslownie z briefu; jedyna zmiana to zawijanie dlugiej linii przez `ruff format` (tresc identyczna).
- `download_sheets` celowo NIE ma wlasnego try/except wokol `_download_hierarchy_*` — deleguje w calosci do mechanizmu z Zad. 6 (`_download_single_sheet_task`, `DownloadResult.no_coverage`), wiec "porazki nigdy nie rzucaja" dziedziczy sie automatycznie z juz przetestowanego kodu `download_hierarchy`; nowe testy tej klasy pokrywaja WYLACZNIE nowa sciezke wejscia (`expand_sheets` + dispatch), nie duplikuja pokrycia `no_coverage`/postepu z `TestDownloadResultNoCoverage`/`TestDownloadManagerDownloadHierarchy` — to zamierzone (brief: "Nowe metody uzywaja maszynerii hierarchii").
- `test_skip_existing` polega na tym, ze domyslny `FileStorage(tmp_path)` (bez argumentow) daje identyczna sciezke co storage managera zbudowany z domyslnym providerem `Mock(spec=GugikProvider)` (ktorego `descriptor_key` jest Mockiem, nie str — `isinstance(key, str)` w `__init__` jest False, wiec `subdir=None` i oba `FileStorage` uzywaja tych samych domyslnych `resolution="1m"`/`vertical_crs="EVRF2007"`) — zweryfikowane empirycznie (test przechodzi), nie tylko przez lekture kodu.
- Tor CZ (`providers/cuzk/*`) i `transform/raster.py` — nie dotkniete; pelna suita (w tym `test_cuzk_client.py`/`test_cuzk_dmr.py`) przeszla w ramach `pytest tests/ -q -m "not live"`.
- Brak watpliwosci blokujacych. Fundament pod Zad. 8 (wycinek biblioteczny PL) gotowy: `expand_sheets`/`download_sheets` daja liste lisci + `last_result` bez ryzyka przerwania na pierwszej porazce.
