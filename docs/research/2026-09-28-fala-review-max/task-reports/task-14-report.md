# Zad. 14: `resolve_subdir` odrzuca pusty wymiar (zn. 7) — raport

## Co zrobiono

`SourceDescriptor.resolve_subdir` (`kartograf/sources/descriptor.py`) rzuca teraz
`ValidationError`, gdy `uklad` lub `vertical_crs` jest pustym stringiem albo samym
whitespace — zamiast cicho produkowac segment storage z dangling podkreslnikiem
(`nmt/pl_1992_1m_`). `None` nadal oznacza "wypelnij pozniej" (legalne, no-op).
Sciezka publiczna: `DownloadManager.__init__` z wlasnym providerem, ktorego
`vertical_crs == ""` (linia 212-223 `manager.py`: `isinstance(str)` przepuszcza
pusty string dalej do `resolve_subdir(vertical_crs=vertical_crs)`).

Implementacja dokladnie wg brief (petla po `(("uklad", uklad), ("vcrs",
vertical_crs))`, `value is not None and not value.strip()`), wstawiona po
kontroli `storage_subdir is None`, przed `subdir.replace(...)`. Dodany import
`from kartograf.exceptions import ValidationError` — brak cyklu (`exceptions.py`
nie importuje nic z pakietu; zweryfikowane czytaniem pliku, potwierdzone
uruchomieniem testow/mypy bez bledow importu).

Docstring `resolve_subdir` uzupelniony o akapit tlumaczacy rozroznienie
None/pusty-string i odsylajacy do zn. 7.

## RED (przed implementacja)

```
.venv/bin/python -m pytest tests/test_sources_registry.py::TestResolveSubdir -v -m "not live"
...
tests/test_sources_registry.py::TestResolveSubdir::test_empty_dimension_raises[kwargs0] FAILED
tests/test_sources_registry.py::TestResolveSubdir::test_empty_dimension_raises[kwargs1] FAILED
tests/test_sources_registry.py::TestResolveSubdir::test_empty_dimension_raises[kwargs2] FAILED
E   Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>
3 failed, 6 passed in 0.36s
```

```
.venv/bin/python -m pytest "tests/test_download_manager.py::TestDownloadManagerStorageFromDescriptor::test_provider_with_empty_vertical_crs_raises" -v -m "not live"
...
FAILED ... - Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>
1 failed in 0.36s
```

Wszystkie 4 przypadki (3 parametrized w `TestResolveSubdir` + 1 w
`TestDownloadManagerStorageFromDescriptor`) padaly przed implementacja, zgodnie
z pre-flight kontrolera ("RED (4 cases)").

## GREEN (po implementacji)

```
.venv/bin/python -m pytest tests/test_sources_registry.py::TestResolveSubdir \
  "tests/test_download_manager.py::TestDownloadManagerStorageFromDescriptor" -v -m "not live"
...
20 passed in 0.30s
```

Pelna suita:

```
.venv/bin/python -m pytest tests/ -q -m "not live"
===================== 1850 passed, 8 deselected in 28.68s ======================
```

Punkt startowy wg COMMON-CONTEXT/dispatch: 1846 offline. Po zadaniu: **1850**
(+4: 3 parametrized `test_empty_dimension_raises` + 1
`test_provider_with_empty_vertical_crs_raises`). Zero regresji.

## Dowod mutacyjny

Mutacja (PO commicie `e6f70cf`, wiec `git checkout --` bezpieczny): usunieta
cala petla walidacyjna z `resolve_subdir` (kod wraca do stanu sprzed zadania —
prosto z kontroli `storage_subdir is None` do `subdir = self.storage_subdir`).

Komenda:
```
.venv/bin/python -m pytest tests/test_sources_registry.py::TestResolveSubdir::test_empty_dimension_raises \
  "tests/test_download_manager.py::TestDownloadManagerStorageFromDescriptor::test_provider_with_empty_vertical_crs_raises" \
  -v -m "not live"
```

Wynik (FAIL, wszystkie 4):
```
tests/test_sources_registry.py::TestResolveSubdir::test_empty_dimension_raises[kwargs0] FAILED
tests/test_sources_registry.py::TestResolveSubdir::test_empty_dimension_raises[kwargs1] FAILED
tests/test_sources_registry.py::TestResolveSubdir::test_empty_dimension_raises[kwargs2] FAILED
tests/test_download_manager.py::TestDownloadManagerStorageFromDescriptor::test_provider_with_empty_vertical_crs_raises FAILED
E   Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>
4 failed in 0.33s
```

Przywrocenie: `git checkout -- kartograf/sources/descriptor.py` (bezpieczne —
plik byl juz zacommitowany w `e6f70cf`). Po przywroceniu:
```
4 passed in 0.28s
```
`git status` / `git diff HEAD -- kartograf/sources/descriptor.py` — puste
(drzewo identyczne z `HEAD`). Pelna suita ponownie: `1850 passed, 8 deselected`.

## Zmierzone liczby (dla ledgera)

- Testy offline przed zadaniem (wg dispatchu): 1846.
- Testy offline po zadaniu: **1850** (1858 razem z 8 `live`, nieuruchamianymi
  w bramce).
- mypy: 32 bledy w 9 plikach, lista identyczna z
  `.superpowers/sdd/2026-09-28-fala-review-max-i-wycinek-biblioteczny/mypy-baseline.txt`
  po normalizacji (`sed -E 's/:[0-9]+: /: /' | sort` na liniach `error:`) —
  zero nowych.

## Pliki

- `kartograf/sources/descriptor.py` — implementacja (import `ValidationError`,
  petla walidacyjna w `resolve_subdir`, uzupelniony docstring).
- `tests/test_sources_registry.py` — `TestResolveSubdir.test_empty_dimension_raises`
  (parametrized, 3 przypadki); uzyto wzorca klasy (`self._descriptor(...)`,
  nie `get_source(...)` z modulu) — brief sugerowal "dopasuj sposob pobrania
  deskryptora do tej klasy", a klasa ma wlasny helper `_descriptor` uzywany
  przez wszystkie pozostale testy w niej.
- `tests/test_download_manager.py` — `TestDownloadManagerStorageFromDescriptor.test_provider_with_empty_vertical_crs_raises`
  (dokladnie wg brief, bez zmian).
- `docs/CHANGELOG.md` — wpis w `### Fixed` sekcji `[0.7.0] - Unreleased`,
  wstawiony zaraz po istniejacym wpisie "review max, zn. 10" (ten sam wzorzec
  co pozostale wpisy "review max" w tym pliku), tresc dokladnie wg Step 6
  briefu.

## Weryfikacje

- Pelna suita offline: `1850 passed, 8 deselected` (komenda:
  `.venv/bin/python -m pytest tests/ -q -m "not live"`).
- `ruff check kartograf/ tests/`: `All checks passed!`
- `ruff format --check kartograf/ tests/`: `87 files already formatted`.
- `mypy kartograf/`: 32 bledy, lista identyczna z baseline (diff pusty po
  normalizacji numerow linii) — zero nowych.
- Brak cyklu importu `kartograf/sources/descriptor.py` -> `kartograf/exceptions.py`
  (potwierdzone: `exceptions.py` nie ma zadnych importow wewnatrz pakietu;
  cala suita + mypy przechodza bez `ImportError`/cyklicznych bledow).
- Tor CZ nietkniety (zadna zmiana poza plikami z listy powyzej); nie bylo
  potrzeby uruchamiac osobno `test_cuzk_client.py`/`test_cuzk_dmr.py` — objete
  pelna suita.

## Samoocena i watpliwosci

- Brief podawal przyklad testu w `TestResolveSubdir` uzywajacy
  `get_source("pl.gugik.nmt_1m")`, ale z dopiskiem "(dopasuj sposob pobrania
  deskryptora do tej klasy)". Zdecydowalem sie uzyc `self._descriptor(...)`
  (lokalny helper klasy, uzywany przez wszystkie inne testy `TestResolveSubdir`,
  z jawnym szablonem `"nmt/pl_{uklad}_1m_{vcrs}"`) zamiast `get_source(...)`
  z rejestru — to jest dokladnie ten "sposob pobrania deskryptora" ktory ma
  reszta klasy, wiec test jest spojny z sasiadami i nie zalezy od tresci
  prawdziwego wpisu `pl.gugik.nmt_1m` w rejestrze. Zachowanie testowane jest
  identyczne (ten sam mechanizm `resolve_subdir`), wiec ryzyko rozbieznosci
  z intencja briefu oceniam jako niskie — ale to jedyna swiadoma decyzja
  interpretacyjna w tym zadaniu, wiec odnotowuje ja jawnie.
- `Step 4` briefu ("Zielono + pelna suita") i `Step 5` ("Dowod mutacyjny")
  wykonane w kolejnosci zgodnej z IMPLEMENTER_COMMON (commit przed mutacja);
  brief mial commit jako Step 7 (na koncu) — kolejnosc ta sama, tylko
  mutacja fizycznie wykonana PO commicie zamiast "przed", co jest wymogiem
  wspolnych zasad (#4), nie odstepstwem od briefu (ktory nie precyzuje
  kolejnosci commit/mutacja).
- Brak innych watpliwosci — zmiana jest lokalna, jednowatkowa logicznie,
  pokryta RED/GREEN/mutacja dla wszystkich 4 przypadkow z pre-flight.
