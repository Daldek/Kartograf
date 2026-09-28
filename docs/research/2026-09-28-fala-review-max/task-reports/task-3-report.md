# Zad. 3 — raport: `mosaic_and_crop(snap_to_source_grid=True)`

## Co zrobiono

`kartograf/transport/mosaic.py`:
- Nowy parametr `snap_to_source_grid: bool = False` (keyword-only, po `dst_kwds`) w `mosaic_and_crop`. Domyslnie `False` — wywolanie CZ (`providers/cuzk/client.py:182`, `mosaic_and_crop(tile_paths, bbox, output_path, nodata=no_data)`) nie przekazuje tego argumentu, wiec zachowanie toru CZ jest bit-w-bit identyczne co przed zadaniem (zweryfikowane: `tests/test_cuzk_client.py`/`test_cuzk_dmr.py` zielone bez zmian w `providers/cuzk/*`).
- Petla metadanych (juz sekwencyjna po Zad. 2) rozszerzona o `transforms.append(src.transform)` obok istniejacego `crs_set`/`res_set`.
- Nowa funkcja modulowa `_phase(value, step) -> int`: faza linii siatki w jednostkach tolerancji `_GRID_TOL_PX = 1e-6`, z domknieciem "faza tuz ponizej 1 == faza 0".
- Nowa funkcja modulowa `_snap_outward(bounds, paths, transforms)`:
  - najpierw waliduje brak rotacji/skosu (`t.b != 0 or t.d != 0`) dla KAZDEGO zrodla -> `ValidationError("mosaic_and_crop: obrocona siatka zrodla {path.name}")`;
  - wyznacza siatke odniesienia jako siatke WIEKSZOSCI zrodel (`Counter(keys).most_common(1)`, remis = pierwsze wystapienie w kolejnosci wejscia, bo `Counter.most_common` i `list.index` sa stabilne);
  - zwraca bounds rozszerzone NA ZEWNATRZ (`math.floor`/`math.ceil` z tolerancja `_GRID_TOL_PX` przy krawedziach juz-na-siatce) oraz liste zrodel spoza siatki wiekszosci z ich przesunieciem w px (x, y).
- W `mosaic_and_crop`: gdy `snap_to_source_grid=True`, bounds przechodza przez `_snap_outward`; zrodla spoza siatki nie przerywaja przetwarzania — ida do `logger.warning` (nazwa loggera `kartograf.transport.mosaic`) z maks. przesunieciem w px i lista nazw (obciete do 10 + "..."); `merge()` dostaje juz-przyciagniete `bounds` zamiast surowego bboxa.
- Docstring `mosaic_and_crop` rozszerzony o akapit opisujacy `snap_to_source_grid`.

`tests/test_transport_mosaic.py`:
- `import logging` na gorze.
- Helper `_write_lattice_tile(path, col0, row0, cols, rows, *, x0=0.5, y_top=100.5, res=1.0)` — kafel z narozami w `k + 0,5` (jak arkusze GUGiK, fakt 1 planu), wartosc piksela = `1000*wiersz_globalny + kolumna_globalna` (jednoznaczna, kazde przesuniecie tresci widac jako rozbieznosc wartosci).
- 4 nowe testy zachowania (1 sparametryzowany na 2 przypadki = 5 testow): `test_snap_copies_source_pixels_exactly` (parametrize ulamkowy/calkowity), `test_snap_uses_majority_grid_and_warns`, `test_snap_keeps_bbox_already_on_grid`, `test_snap_rejects_rotated_source` — kod wklejony z brief.md 1:1 (jedyne zmiany: 3 zawiniecia dlugich linii pod E501, patrz "Odchylenia od briefu" nizej).

Zadnych zmian w `kartograf/providers/cuzk/*` ani `kartograf/transform/raster.py`.

## RED (Step 2)

```
.venv/bin/python -m pytest tests/test_transport_mosaic.py -q -k "snap"
```
```
tests/test_transport_mosaic.py FFFFF                                     [100%]
...
E   TypeError: mosaic_and_crop() got an unexpected keyword argument 'snap_to_source_grid'
...
======================= 5 failed, 8 deselected in 0.36s ========================
```
Dokladnie taki wynik przewidywal pre-flight kontrolera.

## GREEN (Step 4)

```
.venv/bin/python -m pytest tests/test_transport_mosaic.py -q
```
```
tests/test_transport_mosaic.py .............                             [100%]
============================== 13 passed in 1.53s ==============================
```
(8 istniejacych + 5 nowych = 13.)

CZ (bez zmian w `providers/cuzk/*`):
```
.venv/bin/python -m pytest tests/test_cuzk_client.py tests/test_cuzk_dmr.py -q
```
```
tests/test_cuzk_client.py .....................                          [ 28%]
tests/test_cuzk_dmr.py .....................................................
============================== 74 passed in 5.18s ==============================
```

Pelna suita offline:
```
.venv/bin/python -m pytest tests/ -q -m "not live"
```
```
===================== 1785 passed, 8 deselected in 26.15s ======================
```
Punkt startowy (controller notes) = 1780 -> 1785 = +5, zgodnie z 5 nowymi testami (parametrize liczy sie jako 2 osobne testy).

## Ruff / mypy

Kod z briefu NIE byl ruff-clean (jak ostrzegala IMPLEMENTER_COMMON.md pkt 3): 3x E501 (jedna linia w `mosaic.py`, dwie w tescie). Zawiniete bez zmiany semantyki — patrz "Odchylenia od briefu".

```
.venv/bin/python -m ruff check kartograf/ tests/          # All checks passed! (po poprawce E501)
.venv/bin/python -m ruff format kartograf/ tests/         # 1 file reformatted (test — tylko zawijanie/wciecia wywolan), potem:
.venv/bin/python -m ruff format --check kartograf/ tests/ # 86 files already formatted
```

mypy — diff listy (`sed -E 's/:[0-9]+: /: /' | sort`) wzgledem `.superpowers/sdd/2026-09-28-fala-review-max-i-wycinek-biblioteczny/mypy-baseline.txt`:
```
diff mypy-baseline-sorted.txt mypy-final.txt
MYPY DIFF CLEAN   # brak roznicy — 32 bledy w obu, ANI JEDEN nowy w mosaic.py
```
`kartograf/transport/mosaic.py` nie generuje zadnego bledu mypy (rasterio ma `ignore_missing_imports=True` w pyproject, wiec `src.transform`/`Affine`-owe atrybuty sa `Any` — brak potrzeby dodatkowych adnotacji).

## Dowody mutacyjne

Uwaga procesowa (patrz "Incydent" nizej): przy mutacji 1 pierwsze podejscie do "przywroc" uzylo `git checkout -- kartograf/transport/mosaic.py`, co cofnelo caly plik do stanu HEAD (implementacja nie byla jeszcze scommitowana) — nie tylko mutacje. Wykryte natychmiast przez `git status`/`grep snap_to_source_grid` (0 wystapien). Odtworzone z pelnej tresci pliku zlapanej przez `Read` tuz przed mutacjami (Write, potem ponowny `Read` wymagany przez narzedzie). Od mutacji 1 (powtorzonej) w dalej uzywano WYLACZNIE `Edit`/odwrotny `Edit` (nigdy wiecej `git checkout --` na niescommitowanym pliku). Po odtworzeniu: `git status --short` = tylko `mosaic.py` + `test_transport_mosaic.py` zmienione, pelna suita 1785 zielona, ruff/mypy czyste — bez strat.

1. **`if snap_to_source_grid:` -> `if False:`**
   Komenda: `pytest tests/test_transport_mosaic.py -q -k test_snap_copies_source_pixels_exactly`
   FAIL (oba warianty):
   ```
   E   assert 2.87 == 3 ± 1.0e-09   (ulamkowy)
   E   assert 2.5 == 2 ± 1.0e-09    (calkowity)
   ======================= 2 failed, 11 deselected in 0.35s =======================
   ```
   Przywrocono (`Edit` odwrotny) -> pelny plik testowy zielony (13 passed).

2. **`ref = transforms[keys.index(majority)]` -> `ref = transforms[0]`**
   Komenda: `pytest tests/test_transport_mosaic.py -q -k test_snap_uses_majority_grid_and_warns`
   FAIL:
   ```
   E   assert 2.25 == 2 ± 1.0e-09
   ======================= 1 failed, 12 deselected in 0.32s =======================
   ```
   (siatka odniesienia przesuwa sie na "odd" zamiast wiekszosci — test lapie dokladnie to, co mial lapac). Przywrocono -> 13 passed.

3. **`math.ceil((max_x - x0) / rx - _GRID_TOL_PX)` -> `math.ceil((max_x - x0) / rx)`**
   Komenda: `pytest tests/test_transport_mosaic.py -q -k test_snap_keeps_bbox_already_on_grid`
   FAIL:
   ```
   E   assert (4, 5) == (3, 5)
   E     At index 0 diff: 4 != 3
   ======================= 1 failed, 12 deselected in 0.31s =======================
   ```
   Dokladnie szerokosc 4 zamiast 3, jak przewidywal brief. Przywrocono -> 13 passed.

4. **Usunieta petla walidujaca rotacje** (`for path, t in zip(...): if t.b != 0 or t.d != 0: raise ValidationError(...)`)
   Komenda: `pytest tests/test_transport_mosaic.py -q -k test_snap_rejects_rotated_source`
   FAIL:
   ```
   E   Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>
   ======================= 1 failed, 12 deselected in 0.31s =======================
   ```
   Przywrocono -> 13 passed.

Po wszystkich 4 mutacjach + przywroceniach: `git status --short` = tylko dwa zamierzone pliki, pelna suita offline ponownie 1785 passed, CZ 74 passed, ruff + mypy czyste (patrz wyzej — mierzone PO ostatnim przywroceniu).

## Odchylenia od briefu

- **E501 x3** (kod z briefu, nie moj wybor tresci) — zawiniete bez zmiany semantyki:
  - `mosaic.py`: `raise ValidationError(f"...")` rozbite na 3 linie (parens).
  - test: `assert (src.transform.c - 0.5) == pytest.approx(round(src.transform.c - 0.5), abs=1e-9)` -> wyciagniete do zmiennej posredniej `phase = src.transform.c - 0.5; assert phase == pytest.approx(round(phase), abs=1e-9)` (ten sam warunek, czytelniejszy).
  - test: `_write_lattice_tile(tmp_path / "a.tif", 0, 0, 10, 10, x0=0.0, y_top=1.0, res=0.1)` zawiniete na wiele linii (te same argumenty).
  - `ruff format` dodatkowo przelamal wywolania `mosaic_and_crop(...)`/`rasterio.open(...)` w nowych testach na wiele linii (kosmetyka, bez zmiany logiki) — diff pokazany w sekcji ruff wyzej.
- Zadnych odchylen semantycznych od briefu. Kotwice file:line w briefie byly przyblizone (np. `dst_kwds` na koncu sygnatury) — kod jest zrodlem prawdy i zgadza sie z aktualnym stanem po Zad. 2 (HEAD `d50b7d5`).

## Pliki

- `kartograf/transport/mosaic.py` (modyfikacja, +99/-1 wg `git diff --stat`)
- `tests/test_transport_mosaic.py` (modyfikacja, +119)

## Samoocena i watpliwosci

- Zachowanie zgodne z brief 1:1 (kod przeniesiony doslownie, poza kosmetyka E501). Wszystkie 4 mutacje z briefu FAILuja dokladnie tak, jak przewidziano w pre-flight (w tym dokladne liczby: `4 != 3`, `2.25 != 2`, `2.87`/`2.5`).
- `_snap_outward` przyjmuje `transforms: list` bez adnotacji elementu (tak jak w briefie) — rasterio jest pod `ignore_missing_imports`, wiec `Affine` i tak byloby `Any`; nie dodawalem wlasnej adnotacji, bo brief podaje sygnature doslownie, a mypy nie zglasza tu niczego.
- Jedyna realna watpliwosc dotyczy incydentu z `git checkout --` opisanego wyzej w sekcji "Dowody mutacyjne" — nie mial skutku (odtworzone identycznie, zweryfikowane pelna suita + ruff + mypy), ale odnotowuje to jawnie jako lekcje procesowa: na niescommitowanym pliku "przywroc" = `Edit` odwrotny, NIE `git checkout --`.
- Nie commitowalem az do konca (Step 6 nizej) — zgodnie z zasada "commit po kazdym zadaniu", commit nastapi jako ostatni krok tego zadania.
