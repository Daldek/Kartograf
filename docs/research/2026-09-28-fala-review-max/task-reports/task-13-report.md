# Zad. 13 — raport: porazka nie zostawia pustego drzewa `<segment>/bbox/` (zn. 10)

Start: develop @ `b3477f4`. Commit: `d4632ab` "fix(download): porazka wycinka nie zostawia pustych katalogow bbox/".

## Co zrobiono

1. Nowa funkcja modulu `prune_empty_dirs(start: Path, stop: Path) -> None` w
   `kartograf/download/storage.py` (po klasie `FileStorage`): usuwa `start`
   i kolejnych pustych rodzicow w gore, dopoki `stop in current.parents`;
   nigdy nie rusza `stop` ani niczego poza nim. `rmdir()` rzuca `OSError` na
   niepustym katalogu — pierwszy taki przypadek konczy petle (`return`).
2. `kartograf/cli/download_cmd.py::_cz_download_bbox` — lokalny import
   `prune_empty_dirs` (dolaczony do istniejacej grupy lokalnych importow na
   poczatku funkcji, obok `wkid`/`bbox_to_crs`/`get_source` — spojne ze
   stylem pliku). Dwie sciezki sprzatania po `target.parent.mkdir(parents=True,
   exist_ok=True)`:
   - `except (DownloadError, ValidationError)`: sprzatanie + `print
     Error:` + `return 1` (istniejace zachowanie bez zmian, dochodzi tylko
     sprzatanie PRZED printem).
   - nowy `except BaseException`: sprzatanie + `raise` — kazdy INNY wyjatek
     (nie tylko dwa obsluzone typy) tez nie zostawia pustego drzewa.
3. `kartograf/download/cutout.py::run_pl_cutout` — wywolanie
   `build_pl_cutout(...)` owiniete w `try/except BaseException:
   prune_empty_dirs(cutout.target_path.parent, cutout.output_dir); raise`.
   Import `prune_empty_dirs` dolaczony do istniejacego top-level importu
   `FileStorage` z `kartograf.download.storage` (ten modul byl juz importowany
   na poziomie pliku — spojne ze stylem `cutout.py`: importy "core" na gorze,
   ciezsze/CZ-specyficzne lokalnie w funkcjach).
4. `docs/CHANGELOG.md` — bullet w `### Fixed` sekcji `[0.7.0] - Unreleased`
   (na koncu sekcji, przed `### Tests`, wzorem poprzednich zadan fali).

## RED (przed implementacja)

```
.venv/bin/python -m pytest tests/test_storage.py::TestPruneEmptyDirs \
  "tests/test_cli.py::TestCmdDownloadCz::test_bbox_download_error_returns_1" \
  "tests/test_pl_cutout.py::TestMissingSheets::test_failed_build_leaves_no_empty_bbox_dir" -v
```
Wynik: **5 failed** —
- 3x `TestPruneEmptyDirs::*` — `ImportError: cannot import name 'prune_empty_dirs'`
- `test_bbox_download_error_returns_1` — `AssertionError: assert not True` (katalog `nmt/` zostal)
- `test_failed_build_leaves_no_empty_bbox_dir` — `AssertionError: assert not True` (katalog `bbox/` zostal)

Wszystkie failures z oczekiwanego powodu (brak funkcji / brak sprzatania), nie z literowki.

## GREEN (po implementacji)

```
.venv/bin/python -m pytest tests/test_storage.py::TestPruneEmptyDirs -v          → 3 passed
.venv/bin/python -m pytest tests/test_cli.py::TestCmdDownloadCz -v               → 23 passed
.venv/bin/python -m pytest tests/test_pl_cutout.py -v                            → 60 passed
  (w tym test_failed_build_keeps_previous_result — dalej zielony: katalog
  z poprzednim wynikiem nie jest pusty, rmdir na nim rzuca OSError)
```

## Pelna suita, ruff, mypy

```
.venv/bin/python -m pytest tests/ -q -m "not live"
→ 1846 passed, 8 deselected in 28.87s   (baseline dispatchu: 1842 + 4 nowe testy)

.venv/bin/python -m ruff check kartograf/ tests/          → All checks passed!
.venv/bin/python -m ruff format --check kartograf/ tests/ → 87 files already formatted
  (po drodze: E501 w docstringu nowego testu — poprawione zawinieciem linii)

.venv/bin/python -m mypy kartograf/ → Found 32 errors in 9 files
diff normalizowanej listy (sed -E 's/:[0-9]+: /: /' | sort) vs
.superpowers/sdd/2026-09-28-fala-review-max-i-wycinek-biblioteczny/mypy-baseline.txt
→ NO DIFF (32 == 32, identyczna lista)
```

Dodatkowo (spoza gate'u, dla pewnosci ze tor CZ nietkniety):
`tests/test_cuzk_client.py tests/test_cuzk_dmr.py tests/test_cuzk_sheets.py`
→ 111 passed. Zaden plik pod `kartograf/providers/cuzk/` ani
`kartograf/transform/raster.py` nie zmienil sie (`git diff HEAD~1 HEAD
--name-only` — 7 plikow: storage.py, download_cmd.py, cutout.py, 3x test,
CHANGELOG).

## Dowody mutacyjne (PO commicie `d4632ab`, przywracane `git checkout --`)

**Mutacja 1** — usuniete wywolanie `prune_empty_dirs` w galezi
`except (DownloadError, ValidationError)` `_cz_download_bbox`:
```
.venv/bin/python -m pytest "tests/test_cli.py::TestCmdDownloadCz::test_bbox_download_error_returns_1" -v
FAILED — AssertionError: assert not True
  where True = exists()
  where exists = (.../'nmt').exists
```
Przywrocone `git checkout -- kartograf/cli/download_cmd.py` → 1 passed,
`git status` czysty.

**Mutacja 2** — usuniety `try/except` wokol `build_pl_cutout(...)`
w `run_pl_cutout`:
```
.venv/bin/python -m pytest "tests/test_pl_cutout.py::TestMissingSheets::test_failed_build_leaves_no_empty_bbox_dir" -v
FAILED — AssertionError: assert not True
  where True = exists()
  where exists = PosixPath('.../nmt/pl_1992_1m_evrf2007/bbox').exists
```
Przywrocone `git checkout -- kartograf/download/cutout.py` →
`TestMissingSheets` 4 passed, `git status` czysty.

**Mutacja 3** — w `prune_empty_dirs` warunek zmieniony na
`while stop in current.parents or current == stop:` (usuwa takze `stop`,
gdy dojdzie do niego):
```
.venv/bin/python -m pytest "tests/test_storage.py::TestPruneEmptyDirs" -v
FAILED test_removes_empty_chain_but_not_stop —
  AssertionError: assert (not False and False)
  where False = exists()  # (tmp_path / "nmt").exists() -> False, OK
  and   False = exists()  # tmp_path.exists() -> False, ZLE — stop skasowany
(pozostale 2 testy w klasie PASSED — nie dotykaja stanu current==stop)
```
Przywrocone `git checkout -- kartograf/download/storage.py` → 74 passed
(caly `tests/test_storage.py`), `git status` czysty.

Po wszystkich trzech mutacjach + przywroceniach: `git diff --stat HEAD`
pusty, `git status --short` pusty — drzewo robocze identyczne z commitem
`d4632ab`.

## Pliki

- `kartograf/download/storage.py` — `prune_empty_dirs` (nowa funkcja modulu)
- `kartograf/cli/download_cmd.py` — `_cz_download_bbox` (sprzatanie przy porazce)
- `kartograf/download/cutout.py` — `run_pl_cutout` (sprzatanie przy porazce `build_pl_cutout`)
- `tests/test_storage.py` — `TestPruneEmptyDirs` (3 testy)
- `tests/test_cli.py` — `test_bbox_download_error_returns_1` (+1 assert)
- `tests/test_pl_cutout.py` — `TestMissingSheets::test_failed_build_leaves_no_empty_bbox_dir` (nowy test)
- `docs/CHANGELOG.md` — bullet w `### Fixed`

## Samoocena i watpliwosci

- Brief byl doslowny (kod testow, implementacji, komunikatow) — uzyty 1:1,
  z jedna kosmetyczna roznica: import `prune_empty_dirs` w `_cz_download_bbox`
  umiescilem w istniejacej grupie lokalnych importow na poczatku funkcji
  (zamiast tuz przed pierwszym uzyciem, jak w szkicu briefu) — spojne ze
  stylem reszty funkcji (wszystkie lokalne importy `_cz_download_bbox` sa
  zebrane w jednym miejscu, zaraz po docstringu). Zachowanie identyczne,
  zweryfikowane pelna suita + mutacjami po przeniesieniu.
- Jedyna korekta w trakcie: E501 (89 > 88) w docstringu nowego testu
  `test_failed_build_leaves_no_empty_bbox_dir` — zawiniete na dwie linie,
  ruff + pytest zielone po poprawce.
- `TestMissingSheets::_provider()` uzyty przez nowy test NIE ma parametru
  `broken`/`no_coverage` ustawionego — `mosaic_and_crop` jest patchowany
  osobno, wiec `provider.download` normalnie zapisuje wszystkie arkusze
  z `TestLibraryApi._SHEETS` przed porazka na etapie mozaiki; to zgodne
  z zamiarem testu (porazka BUDOWY, nie pobrania) i z assercja
  `cut.target_path.parent.parent.exists()` (segment z arkuszami zostaje).
- Zero nowych bledow mypy (diagnoza LISTA, nie liczba — 32 == 32, identyczne
  linie po normalizacji numerow linii).
- Bez watpliwosci blokujacych. Nie zmienialem `kartograf/providers/cuzk/*`
  ani `kartograf/transform/raster.py` (zweryfikowane `git diff HEAD~1 HEAD
  --name-only`); dodatkowo uruchomione testy CUZK (111 passed) jako
  potwierdzenie braku efektow ubocznych.
