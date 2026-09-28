# Zad. 16: Szablony segmentow `FileStorage` z rejestru zrodel (zn. 11) — raport

## Co zrobiono

`FileStorage` (`kartograf/download/storage.py`) trzymal `_RESOLUTION_SUBDIRS`/
`_PRODUCT_SUBDIRS` — slowniki z kopiami szablonow segmentow bit-w-bit
identycznymi z `SourceDescriptor.storage_subdir` w
`kartograf/sources/registry.py`. Zamienione na `_RESOLUTION_SOURCES`/
`_PRODUCT_SOURCES`, ktore mapuja resolution/product na KLUCZ deskryptora
(`"1m" -> "pl.gugik.nmt_1m"`, `"nmpt" -> "pl.gugik.nmpt"`, itd.); sam szablon
teraz zawsze czytany przez `get_source(key).storage_subdir` (nowa metoda
statyczna `_descriptor_template`). Import `from kartograf.sources.registry
import get_source` na gorze modulu (nie lokalny, w przeciwienstwie do
istniejacej konwencji w `download/manager.py`/`download/cutout.py`) — wymagane,
zeby `monkeypatch.setattr(storage_mod, "get_source", ...)` w tescie mial
efekt (lokalny `from ... import get_source` wewnatrz funkcji obchodzilby
monkeypatch, re-importujac swiezy symbol przy kazdym wywolaniu).

Nieznany `product`/`resolution` (poza `_PRODUCT_SOURCES`/`_RESOLUTION_SOURCES`)
nadal dostaje passthrough — zachowanie identyczne jak przed zmiana
(`test_unknown_product_passthrough` przechodzi bez modyfikacji).

Poprawiony takze docstring wlasciwosci `resolution` (i sekcji `Attributes`
klasy), ktory klamal: twierdzil "empty ... when the segment comes from
`product` or an explicit `subdir`". Zmierzone na zywym kodzie (patrz sekcja
"Weryfikacja dokumentacji" nizej): jawny `subdir` sam w sobie NIE czysci
`resolution` — konstruktor ustawia `self._resolution = ""` WYLACZNIE w gala
`if product:`. Docstring teraz mowi: puste TYLKO gdy segment pochodzi
z `product`.

## Weryfikacja dokumentacji (zywy kod)

```
$ .venv/bin/python -c "
from kartograf.download.storage import FileStorage
s1 = FileStorage('/tmp/x', subdir='nmt/cz_dmr5g_{vcrs}')
print('subdir only, default resolution:', repr(s1.resolution))
s2 = FileStorage('/tmp/x', subdir='nmt/cz_dmr5g_{vcrs}', resolution='5m')
print('subdir + resolution=5m:', repr(s2.resolution))
s3 = FileStorage('/tmp/x', product='orto')
print('product only:', repr(s3.resolution))
s4 = FileStorage('/tmp/x', product='orto', subdir='orto/pl_{uklad}')
print('product + subdir:', repr(s4.resolution))
"
subdir only, default resolution: '1m'
subdir + resolution=5m: '5m'
product only: ''
product + subdir: ''
```
Potwierdzone: `resolution` pusty WYLACZNIE gdy `product` jest prawdziwe;
`subdir` sam w sobie nie ma na to wplywu. Stary docstring byl blednie.

## RED/GREEN

**RED** — nowy test przed implementacja (`tests/test_storage.py`,
`TestFileStorageSegments::test_segment_templates_come_from_registry`,
dodany po `test_delete_with_sidecar_in_new_layout`, przed `class
TestPruneEmptyDirs`):

```
$ .venv/bin/python -m pytest tests/test_storage.py -q -k test_segment_templates_come_from_registry
...
E   AttributeError: <module 'kartograf.download.storage' from
    '/home/claude-agent/workspace/Kartograf/kartograf/download/storage.py'>
    has no attribute 'get_source'
======================= 2 failed, 76 deselected in 0.38s =======================
```
Zgodne z przewidywaniem briefu.

**GREEN** — po implementacji:
```
$ .venv/bin/python -m pytest tests/test_storage.py -q -k test_segment_templates_come_from_registry
tests/test_storage.py ..                                                 [100%]
======================= 2 passed, 76 deselected in 0.27s =======================

$ .venv/bin/python -m pytest tests/test_storage.py -q
tests/test_storage.py .................................................. [ 64%]
............................                                             [100%]
============================== 78 passed in 0.39s ==============================
```

## Dowody mutacyjne

**Mutacja 1 — "1m" (resolution):** w galezi `else` (`_subdir`) dodana linia
wymuszajaca hardcoded kopie szablonu zamiast wywolania deskryptora:
```python
else:
    key = self._RESOLUTION_SOURCES.get(self._resolution)
    template = self._descriptor_template(key) if key else self._resolution
    if self._resolution == "1m":
        template = "nmt/pl_{uklad}_1m_{vcrs}"  # MUTATION: hardcoded copy
```
```
$ .venv/bin/python -m pytest tests/test_storage.py -q -k "test_segment_templates_come_from_registry and kwargs0"
FAILED tests/test_storage.py::TestFileStorageSegments::test_segment_templates_come_from_registry[kwargs0-pl.gugik.nmt_1m-N-34-130-D-d-2-4-nmt/test_1992_evrf2007]
E   AssertionError: assert 'nmt/test_1992_evrf2007' in '.../nmt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc'
======================= 1 failed, 77 deselected in 0.30s =======================
```
Przywrocone `git checkout -- kartograf/download/storage.py` (bezpieczne —
PO commicie zadania). Ponowny test:
```
$ .venv/bin/python -m pytest tests/test_storage.py -q -k "test_segment_templates_come_from_registry and kwargs0"
tests/test_storage.py .                                                  [100%]
======================= 1 passed, 77 deselected in 0.27s =======================
$ git status --short
(pusto)
```

**Mutacja 2 — "nmpt" (product):** analogicznie w galezi `elif self._product:`:
```python
elif self._product:
    key = self._PRODUCT_SOURCES.get(self._product)
    template = self._descriptor_template(key) if key else self._product
    if self._product == "nmpt":
        template = "nmpt/pl_{uklad}_1m_{vcrs}"  # MUTATION: hardcoded copy
```
```
$ .venv/bin/python -m pytest tests/test_storage.py -q -k "test_segment_templates_come_from_registry and kwargs1"
FAILED tests/test_storage.py::TestFileStorageSegments::test_segment_templates_come_from_registry[kwargs1-pl.gugik.nmpt-N-34-130-D-d-2-4-nmpt/test_1992_evrf2007]
E   AssertionError: assert 'nmpt/test_1992_evrf2007' in '.../nmpt/pl_1992_1m_evrf2007/N-34/130/D/d/2/4/N-34-130-D-d-2-4.asc'
======================= 1 failed, 77 deselected in 0.30s =======================
```
Przywrocone `git checkout -- kartograf/download/storage.py`. Ponowny test:
```
$ .venv/bin/python -m pytest tests/test_storage.py -q -k "test_segment_templates_come_from_registry"
tests/test_storage.py ..                                                 [100%]
======================= 2 passed, 76 deselected in 0.27s =======================
$ git status --short
(pusto)
$ git diff HEAD -- kartograf/download/storage.py
(pusto)
```

Obie mutacje: kod padal bez dostepu do (zamockowanego) deskryptora, test
lapal to poprawnie. Po przywroceniu drzewo robocze identyczne z commitem
(potwierdzone `git status` i `git diff HEAD`).

## Zmierzone liczby

- Pelna suita OFFLINE przed zadaniem: **1852 passed, 8 deselected** (punkt
  startowy przekazany przez kontrolera, zweryfikowany).
- Po zadaniu: **1854 passed, 8 deselected** (+2 z nowego parametrized testu).
- `ruff check kartograf/ tests/`: All checks passed.
- `ruff format --check kartograf/ tests/`: 87 files already formatted.
- `mypy kartograf/`: **32 bledy** — lista (po `sed -E 's/:[0-9]+: /: /' | sort`)
  identyczna bit-w-bit z `.superpowers/sdd/2026-09-28-fala-review-max-i-wycinek-biblioteczny/mypy-baseline.txt`
  (`diff` exit 0, ZERO nowych/usunietych). Pre-istniejacy blad w samym
  `storage.py` (`storage.py:107: error: Incompatible types in assignment
  (expression has type "None", variable has type "str")`) dotyczy
  `self._product = None` w konstruktorze — niezwiazany z ta zmiana,
  niezmieniony.
- Import cycle: potwierdzone (jak w pre-flight kontrolera) — `kartograf.sources.registry`
  importuje tylko `kartograf.core.sheet_parser` i `kartograf.sources.descriptor`,
  zero zaleznosci od `kartograf.download`; `import kartograf` dziala.

## Pliki

- Zmodyfikowane: `kartograf/download/storage.py` (mapy -> klucze deskryptorow,
  `_descriptor_template`, docstringi `resolution`), `tests/test_storage.py`
  (nowy parametrized test w `TestFileStorageSegments`), `docs/CHANGELOG.md`
  (`### Changed`, wpis zn. 11; umieszczony w klastrze biezacej fali —
  bezposrednio po wpisie o kompresji pliku posredniego wycinka, przed
  starszymi wpisami audytu 0.7.0).

## Commit

`08fb3d5` — `refactor(storage): szablony segmentow FileStorage z rejestru zrodel`
(3 pliki zmienione: `docs/CHANGELOG.md`, `kartograf/download/storage.py`,
`tests/test_storage.py`).

## Samoocena i watpliwosci

- Rozbieznosc wobec kotwic briefu: brief podawal `kartograf/download/storage.py:110-150`
  jako miejsce zmiany map — aktualne linie w momencie startu (przed edycja)
  to 110-120 dla map i 128-130 dla `resolution` property; przesuniecie
  nieistotne, kod jest zrodlem prawdy (zgodnie z zasada #1 IMPLEMENTER_COMMON).
  Tresc zmiany zgadza sie z briefem 1:1.
- Test `tests/test_sources_registry.py::TestDescriptorProviderConsistency`
  NIE byl dotykany (brief: "zostaja — sa teraz tautologiczne, ale
  nieszkodliwe") — zweryfikowane, ze nadal przechodzi (w pelnej suicie).
- Umiejscowienie wpisu w CHANGELOG w sekcji `### Changed` nie jest w 100%
  jednoznaczne — sekcja miesza wpisy tej fali (zn. 1/R1, zn. 2/R5, decyzja
  kontrolera o kompresji — wszystkie na samej gorze, zaraz po naglowku
  `### Changed`) ze starszymi wpisami audytu 0.7.0 (tagi `(audyt 0.7.0:
  ...)`, ponizej). Wybralem wstawienie zaraz PO ostatnim wpisie tej fali
  (kompresja pliku posredniego) i PRZED pierwszym wpisem audytu — spojne
  z obserwowanym klastrowaniem. Tresc wpisu (nie pozycja) jest tym, czego
  wymagal brief Step 6 doslownie.
- Zero konfliktow z Zad. 15 (`_resolved_subdir(identifier, uklad=None)`,
  `get_raw_path(..., uklad=)`) ani Zad. 13 (`prune_empty_dirs`) — oba
  pozostaly nietkniete, potwierdzone diffem commita (3 pliki, zero zmian
  poza `_subdir`/mapami/docstringami i nowym testem/CHANGELOG).
