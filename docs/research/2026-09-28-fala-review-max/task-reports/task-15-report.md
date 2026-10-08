# Zad. 15: Uklad kafla LAZ — jedno zrodlo prawdy dla CLI i biblioteki (zn. 8)

Status: DONE

Commit: `2f4c4b1` — "fix(storage): uklad kafla LAZ z LazTile.uklad — jeden segment dla CLI i biblioteki"

## Co zrobiono

1. **`kartograf/providers/pl/gugik_laz.py`** — dodano wlasnosc `LazTile.uklad`
   (kaskada: `crs`/`uklad_xy` -> format godla -> `"2000"` z ostrzezeniem w
   logu). Kod przeniesiony 1:1 z usunietego CLI-owego `_laz_uklad`, tylko jako
   `@property` na dataclassie zamiast wolnej funkcji; uzywa istniejacego
   modulowego `logger` (byl juz w pliku, wiec nie trzeba go bylo dodawac).

2. **`kartograf/download/storage.py`**:
   - `_resolved_subdir(self, identifier, uklad=None)` — nowy opcjonalny
     parametr. Gdy podany, wypelnia `{uklad}` wprost; `None` (domyslnie)
     zachowuje dotychczasowa detekcje z formatu identyfikatora
     (`parser_registry.detect_system`).
   - `get_raw_path(self, identifier, filename, *, uklad=None)` — nowy
     keyword-only parametr. Walidacja: `uklad` inne niz `None`/`"1992"`/`"2000"`
     -> `ValidationError`. Docstring rozszerzony (parametr `uklad`, `Raises`,
     przyklad z `tile.uklad` jako prozaiczny blok kodu — NIE jako `>>>`
     doctest, zeby nie zostawic niedomknietej referencji do niezdefiniowanego
     `tile` w wykonywalnym przykladzie; i tak nie ma znaczenia bo repo nie uzywa
     `--doctest-modules`, ale wolalem nie zostawiac mylacego wzorca).

3. **`kartograf/cli/download_cmd.py`** (`_cmd_download_laz`):
   - Usunieto wolna funkcje `_laz_uklad` (przeniesiona do `LazTile.uklad`).
   - Usunieto slownik `storages: dict[str, FileStorage]` + helper
     `_storage_for(tile)` (cache FileStorage per uklad) oraz towarzyszacy mu
     `from kartograf.sources.registry import get_source` /
     `descriptor = get_source("pl.gugik.laz")` (uzywane WYLACZNIE przez
     `_storage_for` — bez innych uzyc w tej funkcji, wiec bezpiecznie
     usuniete; `ruff check` potwierdza brak unused-import).
   - Zastapione jednym `storage = FileStorage(output_dir, product="laz",
     vertical_crs=vertical_crs)` budowanym raz przed petla pobierania.
   - `_fetch(tile)`: `target = storage.get_raw_path(tile.godlo, tile.filename,
     uklad=tile.uklad)`.
   - Zweryfikowano rownowaznosc szablonu: `FileStorage._PRODUCT_SUBDIRS["laz"]
     == "laz/pl_{uklad}_{vcrs}"` jest identyczny ze
     `SourceDescriptor("pl.gugik.laz").storage_subdir` (potwierdzone w
     `kartograf/sources/registry.py:173` i `docs/ARCHITECTURE.md` tabela 3.1)
     — usuniecie posredniego `descriptor.resolve_subdir()` nie zmienia
     wynikowej sciezki.

4. **Testy** — patrz sekcja RED/GREEN i pliki nizej.

5. **Dokumentacja**:
   - `CLAUDE.md` (sekcja "Uklad data/") — dopisano wyjatek: "; wyjatek: kafle
     LAZ — `uklad_xy` kafla (`LazTile.uklad`)".
   - `docs/ARCHITECTURE.md` sekcja 3.1, tabela "Kto wypelnia ktory
     placeholder" — wiersz `{uklad}` (jawnie) zaktualizowany:
     `_laz_uklad(tile)` -> `LazTile.uklad` przez
     `FileStorage.get_raw_path(..., uklad=)`.
   - `docs/ARCHITECTURE.md` sekcja 4.7 (LAZ) — dodatkowo (POZA lista z briefu,
     ale bezposrednio dotkniete przez zmiane i faktycznie nieaktualne po niej):
     zdanie "Jedno zadanie moze wiec zapisac kafle do dwoch segmentow naraz
     (`FileStorage` cache'owany per uklad)" opisywalo juz nieistniejacy
     mechanizm (dawny slownik `storages`) — przepisane na "jeden `FileStorage`
     wystarcza na cale zadanie, `{uklad}` rozwiazuje sie per wywolanie
     `get_raw_path`". Zglaszam to jako rozszerzenie poza literalna liste plikow
     brief (ktory wymienial tylko wiersz tabeli w 3.1), bo zostawienie zdania
     w 4.7 byloby dokumentacja klamiaca o wlasnym mechanizmie wprowadzonym
     tym samym zadaniem.
   - `docs/CHANGELOG.md` `### Added` (`[0.7.0] - Unreleased`) — nowy bullet
     jak w briefie (dopisany po bulletcie `FileStorage(vertical_crs=)`).

## RED/GREEN

Testy napisane rownolegle z produkcyjnym kodem (nie scisle sekwencyjnie
plik-po-pliku), wiec RED pokazany retroaktywnie: PO napisaniu wszystkich
testow i implementacji, produkcyjne pliki zostaly cofniete do stanu `HEAD`
(`git stash push -- <3 pliki produkcyjne>`, zachowujac nowe testy w drzewie
roboczym), uruchomione, a nastepnie przywrocone (`git stash pop`) — patrz
"Uwagi/watpliwosci" nizej po wyjasnienie, dlaczego nie scisle TDD krok-po-kroku.

**RED** (`git stash push -m "task15-red-check-prod-only" -- kartograf/providers/pl/gugik_laz.py kartograf/download/storage.py kartograf/cli/download_cmd.py`, potem):

```
.venv/bin/python -m pytest tests/test_gugik_laz.py::TestLazTileUklad tests/test_storage.py::TestFileStorageSegments::test_laz_uklad_from_tile_overrides_identifier tests/test_storage.py::TestFileStorageSegments::test_laz_unknown_uklad_rejected "tests/test_cli.py::TestCmdDownloadLaz::test_laz_writes_sidecar_next_to_tile" -q -m "not live"
```
```
tests/test_gugik_laz.py FFFFFF                                           [ 66%]
tests/test_storage.py FF                                                 [ 88%]
tests/test_cli.py F                                                      [100%]
...
E   AttributeError: 'LazTile' object has no attribute 'uklad'          (x6, test_gugik_laz.py)
E   TypeError: FileStorage.get_raw_path() got an unexpected keyword argument 'uklad'   (x2, test_storage.py)
E   AttributeError: 'LazTile' object has no attribute 'uklad'          (test_cli.py, przez tile.uklad w nowej asercji)
=========================== 9 failed in 0.46s ===============================
```

Restore (`git stash pop`) -> **GREEN**:

```
.venv/bin/python -m pytest tests/test_gugik_laz.py::TestLazTileUklad tests/test_storage.py::TestFileStorageSegments tests/test_cli.py::TestCmdDownloadLaz -q -m "not live"
```
```
tests/test_gugik_laz.py ......                                           [ 19%]
tests/test_storage.py ...............                                    [ 67%]
tests/test_cli.py ..........                                             [100%]
============================== 31 passed in 0.45s ===============================
```

## Dowody mutacyjne

Wszystkie wykonane PO commicie `2f4c4b1` (`git checkout -- <plik>` bezpiecznie
przywraca stan zacommitowany). Cztery mutacje (trzy z briefu + jedna dodatkowa
dla nowej walidacji `ValidationError`):

**(1) `get_raw_path` ignoruje `uklad`** — w `storage.py` zmieniono
`self._resolved_subdir(identifier, uklad)` na
`self._resolved_subdir(identifier, None)`:
```
.venv/bin/python -m pytest tests/test_storage.py::TestFileStorageSegments::test_laz_uklad_from_tile_overrides_identifier "tests/test_cli.py::TestCmdDownloadLaz::test_laz_writes_sidecar_next_to_tile" "tests/test_cli.py::TestCmdDownloadLaz::test_laz_segment_carries_vertical_crs_from_flag" -q -m "not live"
```
```
FAILED tests/test_storage.py::...::test_laz_uklad_from_tile_overrides_identifier
  AssertionError: assert ('laz', 'pl_1992_evrf2007') == ('laz', 'pl_2000_evrf2007')
FAILED tests/test_cli.py::...::test_laz_writes_sidecar_next_to_tile
  AssertionError: assert 'pl_2000_evrf2007' in '.../laz/pl_1992_evrf2007/...'
FAILED tests/test_cli.py::...::test_laz_segment_carries_vertical_crs_from_flag
  AssertionError: assert 'pl_2000_kron86' in '.../laz/pl_1992_kron86/...'
3 failed in 0.45s
```
`git checkout -- kartograf/download/storage.py` -> 3 passed. Potwierdza brief:
istniejace substring-asercje ORAZ nowa asercja rownosci/literalnego segmentu
lapia ta mutacje.

**(2) CLI bez `uklad=tile.uklad`** — w `download_cmd.py` `_fetch` zmienione na
`storage.get_raw_path(tile.godlo, tile.filename)`:
```
.venv/bin/python -m pytest "tests/test_cli.py::TestCmdDownloadLaz::test_laz_writes_sidecar_next_to_tile" "tests/test_cli.py::TestCmdDownloadLaz::test_laz_segment_carries_vertical_crs_from_flag" -q -m "not live"
```
```
FAILED ...test_laz_writes_sidecar_next_to_tile
  AssertionError: assert 'pl_2000_evrf2007' in '.../laz/pl_1992_evrf2007/...'
FAILED ...test_laz_segment_carries_vertical_crs_from_flag
  AssertionError: assert 'pl_2000_kron86' in '.../laz/pl_1992_kron86/...'
2 failed in 0.44s
```
`git checkout -- kartograf/cli/download_cmd.py` -> `TestCmdDownloadLaz` 10
passed.

**(3) `LazTile.uklad` sprawdza format godla PRZED `crs`** — w `gugik_laz.py`
zamieniono kolejnosc blokow `if` (godlo najpierw, `crs` potem):
```
.venv/bin/python -m pytest tests/test_gugik_laz.py::TestLazTileUklad -q -m "not live"
```
```
FAILED ...::test_crs_pl2000_wins_over_dash_godlo
  AssertionError: assert '1992' == '2000'
1 failed, 5 passed in 0.29s
```
`git checkout -- kartograf/providers/pl/gugik_laz.py` -> 6 passed.

**(4, dodatkowa) walidacja nieznanego `uklad` usunieta** — w `storage.py`
usunieto blok `if uklad is not None and uklad not in ("1992", "2000"): raise
ValidationError(...)`:
```
.venv/bin/python -m pytest tests/test_storage.py::TestFileStorageSegments::test_laz_unknown_uklad_rejected -q -m "not live"
```
```
FAILED ...::test_laz_unknown_uklad_rejected
  Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>
1 failed in 0.30s
```
`git checkout -- kartograf/download/storage.py` -> 1 passed.

Po kazdej mutacji: `git status --short` puste (poza przywroconym plikiem —
czyli w istocie zero roznicy wobec `2f4c4b1`).

## Zmierzone liczby

- Pelna suita offline PRZED zadaniem (wg brief/ledger): 1850 (nie mierzone
  przeze mnie od zera — punkt startowy podany w briefie/COMMON-CONTEXT).
- Pelna suita offline PO zadaniu: **1852 passed, 8 deselected**
  (`pytest tests/ -q -m "not live"`) — delta +2 netto: `test_gugik_laz.py`
  +6 (`TestLazTileUklad`), `test_cli.py` -6 (usunieta `TestLazUklad`) +0 netto
  tam, `test_storage.py` +2 (`test_laz_uklad_from_tile_overrides_identifier`,
  `test_laz_unknown_uklad_rejected`). 1850 + 2 = 1852, zgadza sie.
- `ruff check kartograf/ tests/` — All checks passed (0).
- `ruff format --check kartograf/ tests/` — 87 files already formatted (0
  diff) — pierwsze uruchomienie `ruff format` (bez `--check`) przeformatowalo
  1 plik (`tests/test_cli.py`: zwiniecie 2-liniowego wywolania
  `FileStorage(...)` do jednej linii, bo miescilo sie w limicie) — zgodnie
  z ostrzezeniem z brief/COMMON-CONTEXT, ze kod prosto z planu bywa
  nie-ruff-clean.
- `mypy kartograf/` — **32 bledy w 9 plikach**, lista IDENTYCZNA z baseline
  (`diff` po `grep ": error:" | sed -E 's/:[0-9]+: /: /' | sort` wzgledem
  `.superpowers/sdd/.../mypy-baseline.txt` -> zero roznic). Uwaga
  proceduralna: surowy output mypy zawiera tez 3 linie `note:
  annotation-unchecked` dla `auth/proxy.py`, ktorych NIE MA w
  `mypy-baseline.txt` (plik bazowy zawiera wylacznie linie `error:`,
  juz znormalizowane i posortowane, bez podsumowania "Found N errors") —
  odfiltrowanie do samych `error:` przed diffem bylo konieczne, inaczej diff
  falszywie raportowal 3 "nowe" wpisy. To rozbieznosc w SAMEJ metodzie
  porownania (obie strony sa nadal '32 bledy'), nie w kodzie.

## Pliki

- `kartograf/providers/pl/gugik_laz.py` — `LazTile.uklad` (nowa wlasnosc)
- `kartograf/download/storage.py` — `_resolved_subdir(uklad=)`,
  `get_raw_path(..., uklad=)`
- `kartograf/cli/download_cmd.py` — `_cmd_download_laz` uproszczony, usuniety
  `_laz_uklad`
- `tests/test_gugik_laz.py` — nowa `TestLazTileUklad` (6 testow) + `import
  logging`
- `tests/test_storage.py` — 2 nowe testy w `TestFileStorageSegments`
- `tests/test_cli.py` — usunieta `TestLazUklad` (6 testow), rozszerzony
  `test_laz_writes_sidecar_next_to_tile` (asercje spojnosci CLI/biblioteka +
  literalny segment), odswiezony docstring
  `test_laz_segment_carries_vertical_crs_from_flag` (nie wspomina juz
  `_storage_for`)
- `CLAUDE.md`, `docs/ARCHITECTURE.md` (3.1 + 4.7), `docs/CHANGELOG.md`

## Wynik koncowy (po mutacjach, stan robionej kopii)

```
git status --short   -> (puste)
git log --oneline -1 -> 2f4c4b1 fix(storage): uklad kafla LAZ z LazTile.uklad — jeden segment dla CLI i biblioteki
pytest tests/ -q -m "not live"  -> 1852 passed, 8 deselected
ruff check kartograf/ tests/    -> All checks passed!
ruff format --check kartograf/ tests/ -> 87 files already formatted
mypy kartograf/                 -> 32 errors, lista identyczna z baseline
```

## Samoocena i watpliwosci

- **Odstepstwo od scislego TDD krok-po-kroku**: napisalem produkcyjny kod i
  testy w bliskiej kolejnosci (nie: "napisz WSZYSTKIE testy -> uruchom RED ->
  dopiero wtedy implementuj"), a RED pokazalem retroaktywnie przez
  `git stash` samych plikow produkcyjnych (bezpieczne, odwracalne, nic nie
  bylo jeszcze zacommitowane w momencie stashowania). Efekt koncowy jest
  identyczny jak przy scislym RED->GREEN (dowod w sekcji RED/GREEN wyzej), ale
  zglaszam to jako odstepstwo proceduralne, nie ukrywam.
- **Rozszerzenie poza literalna liste plikow z briefu**: dotknalem
  `docs/ARCHITECTURE.md` sekcja 4.7 (opis przeplywu LAZ), ktorej brief nie
  wymienial wprost (wymienial tylko "sekcja 3.1, wiersz `{uklad}`"). Zrobilem
  to, bo zdanie w 4.7 opisywalo dokladnie usuwany mechanizm (`FileStorage`
  cache'owany per uklad w slowniku) i po mojej zmianie byloby po prostu
  falszywe — zostawienie go wydawalo mi sie gorsze niz drobne rozszerzenie
  zakresu. Jesli to nadgorliwosc wzgledem briefu, latwo cofnac (jeden akapit).
- **`godło` z diakrytykiem w angielskim docstringu `storage.py`**: moj nowy
  tekst zawiera `dash-form godło` (z polskim „ł”) w ANGIELSKIM docstringu
  `get_raw_path`. Sprawdzilem `git show HEAD:kartograf/download/storage.py`
  sprzed zadania — cale QA slowo „godło” bylo juz uzywane z diakrytykiem
  w angielskich docstringach TEGO PLIKU kilkanascie razy (np. "godło
  components", "Normalize godło"), wiec potraktowalem to jako ustalona,
  pre-existing konwencje pliku (polski termin techniczny jako zapozyczenie
  w angielskim tekscie), a nie zlamanie zasady "komentarze/dokumentacja PO
  POLSKU bez diakrytykow" (ta zasada explicite dotyczy polskiego tekstu;
  docstringi `storage.py` sa po angielsku z jednym zapozyczonym polskim
  rzeczownikiem, spojnie z reszta pliku). Zaznaczam to jawnie, zeby kontroler
  mogl osobno ocenic, czy interpretacja jest trafna.
- **Nic w torze CZ, `transport/mosaic.py`, `transform/raster.py` nie
  dotkniete** — zgodnie z global constraints; `tests/test_cuzk_client.py
  tests/test_cuzk_dmr.py tests/test_cuzk_sheets.py` (111 testow) przebiegly
  bez zmian jako dodatkowa kontrola.
- Nie uruchamialem zadnych subagentow/pomocnikow (zgodnie z zasada 9
  IMPLEMENTER_COMMON) — cala praca wykonana bezposrednio.
- `descriptor`/`get_source` usuniete z `_cmd_download_laz` — zweryfikowane
  grepem, ze `get_source("pl.gugik.laz")` w tym pliku nadal wystepuje, ale
  WYLACZNIE w niezwiazanej funkcji `_write_laz_sidecar` (buduje metadane
  sidecara, nie sciezke pliku) — nie zostal osierocony zaden import.
