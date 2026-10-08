# Zad. 2: `mosaic_and_crop` bez wyczerpania deskryptorow — raport

## Co zrobiono

1. Dopisano `import os`, `import sys` na gorze `tests/test_transport_mosaic.py`.
2. Dodano test `test_many_inputs_do_not_exhaust_file_descriptors` (verbatim z briefu) na koncu `tests/test_transport_mosaic.py`.
3. Przepisano `kartograf/transport/mosaic.py::mosaic_and_crop` (verbatim z briefu): usunieto `import contextlib`; metadane (CRS, rozdzielczosc) czyta teraz petla sekwencyjna po sciezkach (`with rasterio.open(path) as src: ...`, jeden deskryptor otwarty na raz, zamykany po kazdej iteracji), a `rasterio.merge.merge()` dostaje liste `Path` zamiast otwartych datasetow — sam otwiera zrodla leniwie, po jednym, per kawalek wyniku (`merge.py` wewnetrznie). Docstring modulu i funkcji zaktualizowane wg briefu (m.in. "kolejni: Saksonia (brak WCS), wycinek PL (ADR-027)").
4. CHANGELOG: dopisano bullet do istniejacej sekcji `### Fixed` pod `## [0.7.0] - Unreleased` (koniec sekcji, przed `### Tests`), tresc verbatim z briefu.
5. Commit `26ab9cb`.

## RED (Step 2)

Komenda:
```
.venv/bin/python -m pytest tests/test_transport_mosaic.py::test_many_inputs_do_not_exhaust_file_descriptors -q
```
Wynik (przed implementacja, na starym kodzie z `ExitStack`):
```
rasterio._err.CPLE_OpenFailedError: /tmp/.../t065.tif: Too many open files
...
kartograf/transport/mosaic.py:38: in mosaic_and_crop
    sources = [stack.enter_context(rasterio.open(p)) for p in inputs]
...
E   rasterio.errors.RasterioIOError: /tmp/.../t065.tif: Too many open files
1 failed in 0.66s
```
Dokladnie zgodne z oczekiwaniem briefu (RasterioIOError "Too many open files" przy `rasterio.open` w `ExitStack`).

## GREEN (Step 4)

```
.venv/bin/python -m pytest tests/test_transport_mosaic.py tests/test_cuzk_client.py tests/test_cuzk_dmr.py tests/test_pl_cutout.py -q
```
```
109 passed in 6.85s
```

```
.venv/bin/python -m pytest tests/ -q -m "not live"
```
```
1780 passed, 8 deselected in 25.83s
```
(baseline 1779 + 1 nowy test = 1780; 8 deselected = testy `live`, zgodnie z Global Constraints).

## Dowod mutacyjny (Step 5)

Mutacja: tymczasowo przywrocono stary ksztalt funkcji — `import contextlib` +
```python
with contextlib.ExitStack() as stack:
    sources = [stack.enter_context(rasterio.open(p)) for p in paths]
    ...
    merge(sources, ...)
```
(caly blok w `with`, jak przed zadaniem; zapisano kopie dobrej wersji do scratchpada przed mutacja).

Komenda:
```
.venv/bin/python -m pytest tests/test_transport_mosaic.py::test_many_inputs_do_not_exhaust_file_descriptors -q
```
Fragment FAIL:
```
E   rasterio._err.CPLE_OpenFailedError: /tmp/.../t065.tif: Too many open files
kartograf/transport/mosaic.py:46: in mosaic_and_crop
    sources = [stack.enter_context(rasterio.open(p)) for p in paths]
E   rasterio.errors.RasterioIOError: /tmp/.../t065.tif: Too many open files
1 failed in 0.64s
```

Przywrocenie: skopiowano z powrotem zapisana (przed mutacja) dobra wersje pliku (identyczna z ta z commitu).

Potwierdzenie PASS po przywroceniu:
```
.venv/bin/python -m pytest tests/test_transport_mosaic.py -q
8 passed in 1.64s
```

`git status --short` po przywroceniu (przed `git add`): tylko
```
 M kartograf/transport/mosaic.py
 M tests/test_transport_mosaic.py
```
— zadnych innych zmian w drzewie roboczym.

## Zmierzone liczby

- Baseline pelnej suity offline (przed zadaniem): `1779 passed, 8 deselected` (zmierzone na starcie tej sesji, HEAD `dbc5926`).
- Po zadaniu: `1780 passed, 8 deselected` (+1 = nowy test FD).
- Ogniskowane testy (mosaic + CZ + pl_cutout): `109 passed`.
- mypy: **32 bledy w 9 plikach** (`Found 32 errors in 9 files`), identyczna lista co `mypy-baseline.txt` po normalizacji (`grep "error:" | sed -E 's/:[0-9]+: /: /' | sort`) — `diff` pusty, zero nowych bledow. Zaden z 32 bledow nie dotyczy `kartograf/transport/mosaic.py`.

## Pliki

- `kartograf/transport/mosaic.py` — implementacja (leniwe otwieranie zrodel).
- `tests/test_transport_mosaic.py` — nowy test + importy `os`/`sys`.
- `docs/CHANGELOG.md` — bullet w `### Fixed` pod `## [0.7.0] - Unreleased`.

## Wynik pelnej suity / ruff / mypy

- `.venv/bin/python -m pytest tests/ -q -m "not live"` → `1780 passed, 8 deselected` (dwukrotnie, przed i po commicie).
- `.venv/bin/python -m ruff check kartograf/ tests/` → `All checks passed!`
- `.venv/bin/python -m ruff format --check kartograf/ tests/` → `86 files already formatted`
- `.venv/bin/python -m mypy kartograf/` → 32 bledy, identyczne z baseline (diff listy pusty).

## Rozbieznosci brief vs kod

Brak. Kotwice file:line z briefu (`transport/mosaic.py`, `providers/cuzk/client.py:182`) zgadzaly sie z kodem na `HEAD=dbc5926`. Kod verbatim z briefu (Step 3, Step 5 mutacja) wklejony bez modyfikacji i dziala jak opisano w RED/GREEN.

`tests/test_pl_cutout.py` (785 linii) juz istnieje w repo i testuje warstwe CLI (`_build_pl_cutout`/`_download_pl_bbox`/`_prepare_pl_cutout` w `kartograf/cli/download_cmd.py`), NIE biblioteczny `kartograf.download.cutout` z R3 (ten modul jeszcze nie istnieje — `kartograf/download/` ma tylko `__init__.py`, `manager.py`, `storage.py`). To spojne z zakresem Zad. 2 (`mosaic_and_crop` jest wspolny dla obu torow, wiec test CLI-level PL cutout jest wlasciwym regresyjnym sprawdzianem "wynik bez zmian"); ewentualna biblioteczna refaktoryzacja `download.cutout` to inne zadanie tej fali (poza zakresem Zad. 2), nieukonczone w chwili tej pracy.

## Odchylenie od briefu: stopka commita

Brief (IMPLEMENTER_COMMON.md pkt 8) podaje stopke `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. System-reminder tej sesji (attribution dla commitow/PR) jawnie zastepuje wczesniejsze wytyczne attribution i podaje `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`, zastrzegajac ze pierwszenstwo maja wylacznie instrukcje uzytkownika w CLAUDE.md lub w pamieci — a IMPLEMENTER_COMMON.md nie jest ani CLAUDE.md, ani pamiecia uzytkownika. Uzyto wiec `Claude Sonnet 5` w commicie `26ab9cb`. Odnotowuje to jawnie na wypadek, gdyby re-reviewer oczekiwal literalnie stopki z briefu.

## Samoocena i watpliwosci

- Implementacja jest doslownym przepisaniem kodu podanego w briefie (Step 3), wiec ryzyko rozbieznosci z zamierzonym zachowaniem jest niskie.
- Test FD (`test_many_inputs_do_not_exhaust_file_descriptors`) jest zaleznym od platformy (`skipif` poza Linuksem) — zgodnie z brief, bo mechanizm `/proc/self/fd` jest linux-only; na macOS test bedzie pomijany (test CI/dev tego zadania byl na Linuksie, wiec RED/GREEN/mutacja sa w pelni zweryfikowane).
- Nie zmieniano niczego w `kartograf/providers/cuzk/*` ani w `transform/raster.py` (zgodnie z zamrozeniem toru CZ) — potwierdzone `git diff --stat` (tylko 3 pliki: mosaic.py, test_transport_mosaic.py, CHANGELOG.md).
- Nie uruchamiano subagentow/reviewerow (zgodnie z zasada 9 IMPLEMENTER_COMMON.md).
- Watpliwosci: brak. Brief byl precyzyjny i kod dzialal dokladnie tak, jak przewidywala pre-flight symulacja kontrolera (RED = "Too many open files", GREEN, mutacja FAILs, testy CZ zielone).
