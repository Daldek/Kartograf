# Zad. 11: Rozmiar wycinka — kompresja pliku posredniego, kontrola miejsca na dysku, `Info:` (zn. 9)

## Co zrobiono

1. `kartograf/download/cutout.py`:
   - stala `_ASC_BYTES_PER_VALUE = 5.5` (dolne oszacowanie, fakt 9 planu).
   - `PlCutout.grid_shape` (wysokosc, szerokosc px, jak `warp_to_grid`) i
     `PlCutout.estimated_bytes` (float32 bez kompresji, bajty) — nowe properties.
   - `estimate_pl_cutout_bytes(cutout, sheets, *, storage=None) -> (bajty, pending)`:
     wynik + arkusze jeszcze niepobrane (`DownloadManager.expand_sheets` + `storage.get_path().exists()`),
     po 5,5 B/wartosc z powierzchni arkusza (`SheetParser(leaf).get_bbox("EPSG:2180")`).
   - `check_pl_cutout_disk_space(cutout, sheets, *, storage=None) -> None`:
     `shutil.disk_usage` na najblizszym istniejacym przodku `target_path.parent`;
     `ValidationError` gdy `free < need`.
   - `run_pl_cutout`: wywolanie `check_pl_cutout_disk_space(cutout, sheets, storage=storage)`
     wstawione PO ustaleniu `storage` (defaults), PRZED `DownloadManager(...)`.
   - `build_pl_cutout`: `dst_kwds` buduje sie warunkowo — `pinned is not None`
     (plik posredni JEST tylko posrednikiem, warp go czyta i kasuje) dostaje
     `compress="deflate", predictor=3, tiled=True, blockxsize=512, blockysize=512,
     bigtiff="IF_SAFER"`; `pinned is None` (EPSG:2180 — plik posredni JEST wynikiem,
     `os.replace` na `target_path`) zostaje bez kompresji, jak dotad.
   - Docstringi `build_pl_cutout`/`run_pl_cutout` uzupelnione o nowe zachowanie (polski ASCII).
2. `kartograf/cli/download_cmd.py` (`_download_pl_cutout`): po bloku "Found N sheets"
   (wewnatrz `if not args.quiet`), PRZED `try: result = run_pl_cutout(...)`,
   nowy blok bezwarunkowy (nie pod `-q`, jak `Warning:` nizej):
   `if cutout.estimated_bytes >= 2**30: print("Info: wycinek ~X GiB (W x H px float32)", file=sys.stderr)`.
3. `tests/test_pl_cutout.py`: nowa klasa `TestCutoutSize` (4 testy) — wstawiona
   po `TestDownloadPlBboxCutout` (przed `TestGeometryCutout`), bo
   `test_disk_check_blocks_before_download` uzywa `TestDownloadPlBboxCutout()._run(...)`.
4. `docs/CHANGELOG.md` — nowy bullet w `## [0.7.0] - Unreleased` / `### Changed`
   (tresc doslownie z briefu, Step 6).

Tresc kodu i tekstow wzieta doslownie z briefu (Step 3); jedyna zmiana
wzgledem briefu to formatowanie `dst_kwds.update(...)` (ruff format rozbil na
osobne linie kwargs — tresc identyczna).

## RED (przed implementacja)

```
.venv/bin/python -m pytest tests/test_pl_cutout.py::TestCutoutSize -v
```
```
tests/test_pl_cutout.py::TestCutoutSize::test_disk_check_blocks_before_download FAILED
    assert rc == 1
E   assert 0 == 1
tests/test_pl_cutout.py::TestCutoutSize::test_estimate_counts_only_pending_sheets FAILED
E   ImportError: cannot import name 'estimate_pl_cutout_bytes' from 'kartograf.download.cutout'
tests/test_pl_cutout.py::TestCutoutSize::test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe FAILED
E   KeyError: 'compress'
tests/test_pl_cutout.py::TestCutoutSize::test_large_grid_prints_info FAILED
E   AssertionError: assert ('Info:' in '')
=========================== 4 failed in 0.55s ============================
```
(Uwaga poboczna: w logach RED i GREEN widac ostrzezenie GDAL
`CPLE_IllegalArg ... BLOCKXSIZE can only be used with TILED=YES` — zweryfikowane,
ze to PRE-ISTNIEJACY quirk na `develop` (wystepuje juz w przechodzacym
`test_target_5514_content_lt_1px` PRZED jakakolwiek zmiana tego zadania:
`kwds.setdefault("tiled", False)` w `mosaic.py` zostawia `blockxsize`
odziedziczony z profilu VRT). Poza zakresem Zad. 11 — GDAL tylko ostrzega
i ignoruje opcje, test przechodzil i przechodzi.)

## GREEN (po implementacji)

```
.venv/bin/python -m pytest tests/test_pl_cutout.py::TestCutoutSize -v
```
```
tests/test_pl_cutout.py::TestCutoutSize::test_disk_check_blocks_before_download PASSED
tests/test_pl_cutout.py::TestCutoutSize::test_estimate_counts_only_pending_sheets PASSED
tests/test_pl_cutout.py::TestCutoutSize::test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe PASSED
tests/test_pl_cutout.py::TestCutoutSize::test_large_grid_prints_info PASSED
============================== 4 passed in 0.41s ===============================
```

Caly `tests/test_pl_cutout.py`: **59 passed** (55 istniejacych + 4 nowe).
Sanity CZ (`tests/test_cuzk_client.py tests/test_cuzk_dmr.py`, tor CZ nie
byl ruszany w tym zadaniu — `transport/mosaic.py` i `providers/cuzk/*` bez
zmian): **74 passed**.

Pelna suita offline:
```
.venv/bin/python -m pytest tests/ -q -m "not live"
```
```
===================== 1841 passed, 8 deselected in 26.70s ======================
```
(baseline z brief/COMMON-CONTEXT: 1837 offline; 1837 + 4 nowe = 1841 — zgadza sie.)

## Dowody mutacyjne

Wszystkie wykonane PO commicie zadania (`209ca14`), kazda przywrocona
`git checkout -- <plik>` (bezpieczne, bo commit juz istnieje), kazda
zakonczona `git status --short` pustym i ponownym PASS.

**(1) Usuniecie wywolania `check_pl_cutout_disk_space` w `run_pl_cutout`.**
Zmiana: skasowana linia `check_pl_cutout_disk_space(cutout, sheets, storage=storage)`
przed `manager = DownloadManager(...)`.
```
.venv/bin/python -m pytest tests/test_pl_cutout.py::TestCutoutSize::test_disk_check_blocks_before_download -v
```
```
FAILED ... test_disk_check_blocks_before_download - assert 0 == 1
    assert rc == 1
E   assert 0 == 1
```
Przywrocone (`git checkout -- kartograf/download/cutout.py`) -> PASS, `git status --short` puste.

**(2) `estimate_pl_cutout_bytes` liczy takze arkusze z cache.**
Zmiana: `if storage.get_path(leaf, ".asc").exists(): continue` -> `if False: continue`
(skip nigdy sie nie wykonuje, pending liczy WSZYSTKIE arkusze, nie tylko brakujace).
```
.venv/bin/python -m pytest tests/test_pl_cutout.py::TestCutoutSize::test_estimate_counts_only_pending_sheets -v
```
```
FAILED ... assert (2, 2) == (2, 1)
    At index 1 diff: 2 != 1
```
Przywrocone -> PASS, `git status --short` puste.

**(3) Usuniecie `dst_kwds.update(...)` (kompresja/tiled/bigtiff) w `build_pl_cutout`.**
Zmiana: caly blok `if pinned is not None: dst_kwds.update(...)` skasowany —
`dst_kwds` zostaje `{"driver": "GTiff", "crs": "EPSG:2180"}` zawsze.
```
.venv/bin/python -m pytest tests/test_pl_cutout.py::TestCutoutSize::test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe -v
```
```
FAILED ... KeyError: 'compress'
```
Przywrocone -> PASS, `git status --short` puste.

**(4) Usuniecie bloku `Info:` w CLI (`_download_pl_cutout`).**
Zmiana: caly blok `if cutout.estimated_bytes >= 2**30: print("Info: ...")` skasowany.
```
.venv/bin/python -m pytest tests/test_pl_cutout.py::TestCutoutSize::test_large_grid_prints_info -v
```
```
FAILED ... AssertionError: assert ('Info:' in '')
```
Przywrocone -> PASS, `git status --short` puste.

**(5) [P-19] Z `dst_kwds.update(...)` usuniete `blockxsize`/`blockysize`, zostawione `tiled=True`.**
Zmiana: `dst_kwds.update(compress="deflate", predictor=3, tiled=True, bigtiff="IF_SAFER")`
(bez `blockxsize=512, blockysize=512`).
```
.venv/bin/python -m pytest tests/test_pl_cutout.py::TestCutoutSize::test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe tests/test_pl_cutout.py::TestBuildPlCutout -v
```
```
FAILED TestCutoutSize::test_warp_mosaic_tmp_is_compressed_and_bigtiff_safe
E   rasterio.errors.RasterBlockError: The height and width of TIFF dataset blocks must be multiples of 16
FAILED TestBuildPlCutout::test_target_5514_content_lt_1px
E   rasterio.errors.RasterBlockError: The height and width of TIFF dataset blocks must be multiples of 16
FAILED TestBuildPlCutout::test_failed_build_keeps_previous_result
E   rasterio.errors.RasterBlockError: The height and width of TIFF dataset blocks must be multiples of 16
3 failed, 3 passed in 0.84s
```
Dokladnie taki blad, jaki przewidywal brief/P-19 (potwierdza fakt 10 planu:
kafle 512 sa WYMAGANE, nie tylko jawne — bez rozmiarow GDAL sam dobiera
domyslny rozmiar niezgodny z regula "wielokrotnosc 16" przy `tiled=True`
odziedziczonym z profilu zrodla VRT). Przywrocone
(`git checkout -- kartograf/download/cutout.py`) -> `TestBuildPlCutout` +
`TestCutoutSize` znow zielone, `git status --short` puste.

Po kazdej mutacji uruchomiony byl focused test (nie cala suita) — zgodnie
z zasada "skupione testy w trakcie". Pelna suita (1841/1841) uruchomiona
dopiero na koncu, na przywroconym stanie (patrz "Weryfikacja koncowa").

## Zmierzone liczby (o ktore prosi brief)

- RED: 4/4 nowe testy FAIL z oczekiwanych powodow.
- GREEN: 4/4 nowe testy PASS; `test_pl_cutout.py` 59/59; CZ sanity 74/74.
- Pelna suita offline: **1841 passed, 8 deselected** (`-m "not live"`) —
  baseline planu 1837 + 4 nowe = 1841, zgodnosc potwierdzona.
- Mutacje: 5/5 dały FAIL na dokladnie przewidzianym tescie/bledzie; wszystkie
  przywrocone do stanu z commita, `git status --short` puste po kazdej.

## Pliki

- Zmiana: `/home/claude-agent/workspace/Kartograf/kartograf/download/cutout.py`
- Zmiana: `/home/claude-agent/workspace/Kartograf/kartograf/cli/download_cmd.py`
- Zmiana: `/home/claude-agent/workspace/Kartograf/tests/test_pl_cutout.py`
- Zmiana: `/home/claude-agent/workspace/Kartograf/docs/CHANGELOG.md`

## Weryfikacja koncowa (po wszystkich mutacjach i przywroceniach)

```
.venv/bin/python -m pytest tests/ -q -m "not live"
```
```
===================== 1841 passed, 8 deselected in 27.54s ======================
```

```
.venv/bin/python -m ruff check kartograf/ tests/
```
```
All checks passed!
```

```
.venv/bin/python -m ruff format --check kartograf/ tests/
```
```
87 files already formatted
```

mypy (diff LISTY `plik: komunikat` po `sed -E 's/:[0-9]+: /: /' | sort`,
wzgledem `.superpowers/sdd/2026-09-28-fala-review-max-i-wycinek-biblioteczny/mypy-baseline.txt`):
```
diff mypy-baseline-sorted.txt mypy-final.txt
```
```
(brak wyjscia — 0 diff)
MYPY: NO NEW ERRORS (0 diff)
```
32 bledy w obu (baseline = po zadaniu). Uwaga poboczna: surowe wyjscie `mypy`
(bez filtra `grep "error:"`) ma DODATKOWO 3 linie `note: By default the
bodies of untyped functions are not checked...` (`kartograf/auth/proxy.py`) —
nieobecne w `mypy-baseline.txt`, bo baseline zawiera tylko linie `error:`
(zweryfikowane: `grep -c "note:" mypy-baseline.txt` = 0). To nie sa nowe
bledy: `Found 32 errors in 9 files` identyczne przed i po. Odnotowuje to
tutaj, zeby nastepny agent/reviewer nie zlapal sie na "35 != 32" przy
niefiltrowanym porownaniu.

`git status --short`: puste. `git log --oneline -1`:
`209ca14 feat(download): wycinek PL — kompresja pliku posredniego, kontrola miejsca na dysku, Info dla duzych siatek`

## Samoocena i watpliwosci

- Implementacja jest doslownie z briefu (Step 3), wiec ryzyko rozjazdu
  z intencja jest niskie. Jedyne odstepstwo od briefu to formatowanie
  (`ruff format` rozbil `dst_kwds.update(compress=..., predictor=..., ...)`
  z 2 linii na 6 — tresc identyczna, tylko styl).
- `check_pl_cutout_disk_space` w harnessie CLI (gdzie `DownloadManager` jest
  MagicMockiem) liczy TYLKO `cutout.estimated_bytes` (bo
  `DownloadManager.expand_sheets(...)` na MagicMocku zwraca `MagicMock()`,
  ktory iteruje jako pusta sekwencja — zweryfikowane empirycznie w GREEN:
  `test_creates_cutout_and_sidecar` i inne testy `TestDownloadPlBboxCutout`
  dalej przechodza z realnymi (male) bboxami, bo `cutout.estimated_bytes`
  tych testow jest rzedu dziesiatek KB, a prawdziwy wolny dysk to z pewnoscia
  wiecej). To jest zamierzone zachowanie z uwag kontrolera w dispatchu —
  potwierdzone dzialaniem, nie tylko zalozeniem.
- Testy `TestLibraryApi`/`TestMissingSheets`, ktore wywoluja `run_pl_cutout`
  NAPRAWDE (bez mocka `DownloadManager`), teraz tez przechodza przez REALNY
  `check_pl_cutout_disk_space` (prawdziwy `shutil.disk_usage` na `tmp_path`).
  Wszystkie nadal przechodza (male bboxy testowe, prawdziwy wolny dysk >> need)
  — zweryfikowane w pelnej suicie (1841 passed), zaden z tych testow nie byl
  wczesniej explicite wymieniony w brief, ale jest to naturalna konsekwencja
  wstawienia kontroli PRZED `DownloadManager` w `run_pl_cutout` (dotyczy
  KAZDEGO wywolania, nie tylko CLI).
- Nie zmienialem `transform/raster.py` ani `providers/cuzk/*` (zakaz z
  Global Constraints) ani `transport/mosaic.py` (Zad. 11 tego nie wymagalo —
  `kwds.update(dst_kwds)` w mosaic.py juz istnial z wczesniejszych zadan i
  poprawnie nadpisuje `setdefault("tiled", False)`, zweryfikowane odczytem
  kodu PRZED implementacja).
- Watpliwosc mniejszej wagi: `check_pl_cutout_disk_space` wywoluje
  `estimate_pl_cutout_bytes`, ktora otwiera `SheetParser(leaf)` dla KAZDEGO
  brakujacego arkusza (koszt: parsowanie godla + `get_bbox`) — przy duzym
  obszarze (tysiace arkuszy) to dodatkowy, ale tani (bez sieci/IO poza
  `Path.exists()`) narzut przed pobraniem. Brief nie prosil o pomiar tego
  kosztu i nie wydaje sie problemem w skali NMT PL (nawet 75x75 km to rzedu
  1200 arkuszy — patrz komentarz w `mosaic.py` o limicie deskryptorow), wiec
  zostawiam bez zmian.
- Zero pytan blokujacych — brief byl kompletny i spojny z kodem zastanym.
