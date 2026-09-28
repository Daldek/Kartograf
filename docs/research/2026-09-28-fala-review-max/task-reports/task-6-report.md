# Zad. 6: `NoCoverageError` — raport implementacji

Commit: `cc10773674ddc5f77a9c7cb3c16b30b93da19e84`
`feat(download): NoCoverageError — brak danych GUGiK odrozniony od awarii pobrania`

## Co zrobiono

1. `kartograf/exceptions.py` — nowa klasa `NoCoverageError(DownloadError)` po `DownloadError`, docstring wg brief (dosłownie).
2. `kartograf/__init__.py` — import + `__all__` (sekcja Exceptions).
3. `kartograf/providers/pl/gugik.py`:
   - import `NoCoverageError`;
   - `Raises` w docstring `_get_opendata_url` rozbite na `NoCoverageError` / `DownloadError`;
   - fallback URL innego arkusza: `logger.debug` -> `logger.warning` z komunikatem `"{godlo}: skorowidz zwrocil URL innego arkusza ({urls[0]}) — ..."` + komentarz;
   - koncowka funkcji: dodana posrednia galaz `if transport_errors: raise DownloadError(...)` ("brak pokrycia niepewny", z `transport_errors`/`len(wms_layers)`/`godlo`/`last_error`), koncowe `raise DownloadError(...)` zmienione na `raise NoCoverageError(...)` (tresc komunikatu bez zmian — dokladnie ta sama, ktorej bronia stare testy).
4. `kartograf/download/manager.py`:
   - import `NoCoverageError`;
   - `DownloadResult.no_coverage: list[str] = field(default_factory=list)` + docstring pola;
   - `_download_single_sheet_task`: nowy `except NoCoverageError as e:` PRZED `except DownloadError as e:` (kolejnosc obowiazkowa — `NoCoverageError` to podklasa), zwraca `status="no_coverage"`; docstring statusow rozszerzony;
   - `_download_hierarchy_sequential`: nowy `except NoCoverageError as e:` PRZED `except DownloadError as e:`, dopisuje do `result.failed` ORAZ `result.no_coverage`, `on_progress` z `status="failed"` (DownloadProgress statusy bez zmian);
   - `_download_hierarchy_parallel`: pod lockiem `elif status == "failed":` -> `elif status in ("failed", "no_coverage"):` + warunkowe dopisanie do `result.no_coverage`; w dispatchu `on_progress` analogicznie `elif status in ("failed", "no_coverage"):` (nadal raportuje `DownloadProgress(status="failed", ...)`).
5. Testy:
   - `tests/test_gugik_provider.py`: (a) `test_get_opendata_url_not_found` — dopisany import + `assert isinstance(exc_info.value, NoCoverageError)`; (b) `test_get_opendata_url_partial_transport_error_keeps_no_coverage_message` ZASTAPIONY przez `test_get_opendata_url_partial_transport_error_is_not_no_coverage` (dokladnie tresc z briefu); (c) nowy `test_fallback_url_of_other_sheet_warns` (caplog).
   - `tests/test_download_manager.py`: nowa klasa `TestDownloadResultNoCoverage` (fixture `provider` + `test_no_coverage_is_subset_of_failed` sparametryzowany `workers=[1,4]`), dokladnie tresc z briefu (jedna linia zawinieta przez `ruff format` — patrz nizej).
6. `docs/CHANGELOG.md` — `### Added` i `### Changed` w `[0.7.0] - Unreleased`, tresc z briefu (2 bulletpointy, dopisane na poczatku odpowiednich sekcji).

Zadne odejscie od kotwic file:line z briefu — kod pod l. 542-575 (`gugik.py`) i sekcje `manager.py` wskazane w briefie zgadzaly sie z aktualnym stanem (HEAD `c5b15dc`).

## RED (przed implementacja)

```
.venv/bin/python -m pytest tests/test_gugik_provider.py::TestGugikProviderGetOpendataUrl tests/test_download_manager.py::TestDownloadResultNoCoverage -q
```
```
tests/test_gugik_provider.py .F.F.F..                                    [ 80%]
tests/test_download_manager.py EE                                        [100%]
...
E   ImportError: cannot import name 'NoCoverageError' from 'kartograf.exceptions'
...
E   AssertionError: assert ('N-34-130-D-d-2-4' in '')
E    +  where '' = <_pytest.logging.LogCaptureFixture object at ...>.text
=================== 3 failed, 5 passed, 2 errors in 0.48s ====================
```
(`ImportError` na testach (a)/(b)/nowej fixture providera; test (c) fallback-warning failuje bo produkcyjny kod nadal robi `logger.debug`.)

## GREEN (po implementacji)

```
.venv/bin/python -m pytest tests/test_gugik_provider.py::TestGugikProviderGetOpendataUrl tests/test_download_manager.py::TestDownloadResultNoCoverage -v
```
```
10 passed in 0.35s
```

Pelna suita offline:
```
.venv/bin/python -m pytest tests/ -q -m "not live"
```
```
1799 passed, 8 deselected in 25.83s
```
Punkt startowy (kontroler): 1796 passed. Przybylo 3 testy: `test_fallback_url_of_other_sheet_warns` (+1) i sparametryzowany `test_no_coverage_is_subset_of_failed[1]`/`[4]` (+2) = +3 -> 1799. Zgadza sie.

## ruff / mypy

- `ruff check kartograf/ tests/`: pierwszy przebieg 1 blad (`E501` w nowym teście, linia z `raise NoCoverageError(...)` w jednej linii > 88 znakow — dokladnie ostrzezenie z `IMPLEMENTER_COMMON.md` p.3, ze kod z planu bywa nie-ruff-clean). Naprawione przez `ruff format kartograf/ tests/` (przelamalo argumenty `NoCoverageError(...)` na 3 linie w `tests/test_download_manager.py`, tresc bez zmian). Po tym: `All checks passed!`.
- `ruff format --check kartograf/ tests/`: `86 files already formatted`.
- `mypy kartograf/`: `Found 32 errors in 9 files` — diff listy (`sed -E 's/:[0-9]+: /: /' | sort`, oba pliki ograniczone do linii `: error:` — baseline sam w sobie ma tylko 32 linie error, bez linii `Found ...`/`note: annotation-unchecked`, wiec porownanie zrobione na przefiltrowanych `: error:`): **0 different, 0 new, 0 fixed** — listy identyczne.

## Dowody mutacyjne (wszystkie PO commicie `cc10773`, przywracane `git checkout -- <plik>`)

1. **`raise NoCoverageError` -> `raise DownloadError`** (koncowka `_get_opendata_url`):
   `pytest tests/test_gugik_provider.py::...::test_get_opendata_url_not_found tests/test_download_manager.py::TestDownloadResultNoCoverage -q`
   -> `test_get_opendata_url_not_found` FAIL (`AssertionError: assert False ... isinstance(DownloadError(...), NoCoverageError)`); test managera (2 warianty) **PASSED** bez zmian — potwierdzone P-10 (mock providera w teście managera rzuca `NoCoverageError` sam, niezalezny od `gugik.py`). Przywrocono `git checkout -- kartograf/providers/pl/gugik.py`, test (a) PASS, `git status` czysty.

2. **Usuniecie galezi `if transport_errors:`**:
   `pytest tests/test_gugik_provider.py::...::test_get_opendata_url_partial_transport_error_is_not_no_coverage -q`
   -> FAIL (`AssertionError: assert not True ... isinstance(NoCoverageError(...), NoCoverageError)` — bez posredniej galezi kod leci prosto do `NoCoverageError`). Przywrocono, PASS, `git status` czysty.

3a. **`_download_hierarchy_parallel`: pominiecie dopisania do `no_coverage` pod lockiem**:
   `pytest tests/test_download_manager.py::TestDownloadResultNoCoverage::test_no_coverage_is_subset_of_failed -v`
   -> `[workers=4]` FAIL (`assert [] == ['N-34-130-D-d-2-1']`), `[workers=1]` (tor sekwencyjny, nietkniety ta mutacja) PASSED. Przywrocono, oba PASS, `git status` czysty.

3b. **`_download_hierarchy_sequential`: pominiecie dopisania do `no_coverage`**:
   ta sama komenda co 3a
   -> `[workers=1]` FAIL (`assert [] == ['N-34-130-D-d-2-1']`), `[workers=4]` (tor rownolegly, nietkniety ta mutacja) PASSED. Przywrocono, oba PASS, `git status` czysty.

4. **Fallback URL: `logger.warning(...)` -> `logger.debug(...)`** (bez tresci z godlem/URL):
   `pytest tests/test_gugik_provider.py::...::test_fallback_url_of_other_sheet_warns -q`
   -> FAIL (`AssertionError: assert ('N-34-130-D-d-2-4' in '')` — `caplog.text` puste, bo `caplog.at_level("WARNING")` nie lapie `DEBUG`). Przywrocono, PASS, `git status` czysty.

Wszystkie 5 mutacji (brief wymienial 4 punkty, w tym jeden opisany jako "dwie osobne mutacje" dla sekwencyjnego/rownoleglego toru — stad 3a/3b) daly FAIL dokladnie tam, gdzie przewidywal brief/pre-flight; zaden nie okazal sie "znaleziskiem" (test broniacy niczego).

## Zmierzone liczby

- Testy offline: 1799 passed, 8 deselected (`-m live`) — start 1796 (kontroler), +3 nowe.
- mypy: 32/32 bledow, lista identyczna z baseline (0 nowych, 0 naprawionych).
- ruff check: 0 bledow po `ruff format`; ruff format --check: 86/86 plikow sformatowanych.

## Pliki

- `kartograf/exceptions.py`
- `kartograf/__init__.py`
- `kartograf/providers/pl/gugik.py`
- `kartograf/download/manager.py`
- `tests/test_gugik_provider.py`
- `tests/test_download_manager.py`
- `docs/CHANGELOG.md`

## Samoocena i watpliwosci

- Zgodnosc z briefem: pelna, tresci komunikatow/docstringow/komentarzy przepisane doslownie z brief (gdzie brief podawal dokladny kod).
- CLI z komunikatem "may not have coverage": zgrepowalem `kartograf/` i `tests/` — fraza literalna nie wystepuje nigdzie indziej (tekst w `gugik.py` ma zmienna `{self._resolution}` w srodku, wiec nie jest to literal match nigdzie w CLI); `GugikNmptProvider` dziedziczy `_get_opendata_url` bez override, wiec zmiana obejmuje NMPT automatycznie. Zaden test CLI (`test_cli.py`) nie odwoluje sie do tego komunikatu ani do `NoCoverageError` — tryby bez `--target-crs` (godlo/lista arkuszy) nadal koncza sie kodem 1 dla KAZDEGO `DownloadError`, w tym `NoCoverageError` (podklasa) — kody wyjscia nietkniete, zgodnie z ograniczeniem kontrolera.
- Tor CZ (`providers/cuzk/*`) i `transform/raster.py` — nie dotkniete; pelna suita (w tym `test_cuzk_client.py`/`test_cuzk_dmr.py`) przeszla w ramach `pytest tests/ -q -m "not live"`.
- Brak watpliwosci blokujacych. Jedno drobne odstepstwo od "doslownosci" briefu: `ruff format` przelamal jedna linie w nowym teście (`tests/test_download_manager.py`, wywolanie `NoCoverageError(...)` na 3 linie zamiast 1) — tresc identyczna, tylko formatowanie (przewidziane przez `IMPLEMENTER_COMMON.md` p.3).
