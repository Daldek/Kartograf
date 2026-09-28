# Zad. 9 — raport implementera (opus)

**Status:** DONE_WITH_CONCERNS (odstepstwa od briefu opisane nizej; 1 dodatkowy commit z poprawka dopuszczona w dispatchu, 1 commit testow po przezytych mutacjach)

BASE `6bc1c19` -> HEAD `2ad46cf`:

| SHA | Temat |
|---|---|
| `4faef3e` | fix(download): wycinek PL na siatce arkuszy, arkusze w VRT (EPSG:2180/Float32), blad dla arkuszy PL-2000 |
| `f14660b` | fix(transport): owijanie VRT nie dziedziczy kafli 128 px — zapis GTiff bez RasterBlockError |
| `2ad46cf` | test(download): wycinek PL — obrona sortowania wejsc i zapasu 1 px w sumie R-01 |

## Co zrobiono

### `4faef3e` (brief, Step 1-7)
- `kartograf/download/cutout.py`
  - `_PL2000_MIN_X` + `_reject_pl2000_sheets()` — kod z briefu doslownie (komunikat, strefa, `EPSG:{2171 + zone}`).
  - `build_pl_cutout`: `_reject_pl2000_sheets(sheet_paths)` na poczatku (przed `mkdir`/tmp); mozaika z `sorted(Path(p) for p in sheet_paths)`, `snap_to_source_grid=True`, `assign_crs="EPSG:2180"`, `dtype="float32"` (+ komentarz z briefu). Docstring: akapit o siatce arkuszy (rozszerzenie na zewnatrz < 1 px, 1:1 przy EPSG:2180, arkusz spoza siatki wiekszosci = ostrzezenie + najblizszy sasiad), VRT (EPSG:2180 + Float32: `.prj` Hydrografu, Int32), sortowaniu (profil z pierwszego zrodla, pierwsze wygrywa w zakladce, `as_completed`), odrzucaniu PL-2000.
  - `select_pl_cutout_sheets`: `selection` = obwiednia zrodla +- `cutout.pixel_size` (kod z briefu), uzyta w OBU miejscach (bbox i suma R-01); docstring zaktualizowany.
  - docstring modulu: "przycinana do obszaru zadania" -> "... rozszerzonego na zewnatrz do siatki pikseli arkuszy (< 1 px; ...)".
- `tests/test_pl_cutout.py`: helpery `_write_grid_sheet`, `_ids`, `_HYDROGRAF_2180_WKT` (tresc bajt-w-bajt jak w `tests/test_transport_mosaic.py` z Zad. 4); klasa `TestSheetGrid` (7 testow / 9 przypadkow z briefu, po `_BBOX_2180`, przed `TestDownloadPlBboxCutout`); `TestDownloadPlBboxCutout.test_pl2000_sheet_returns_1_with_reason`. Tresc testow = brief; zmiany wylacznie formatujace (ruff format, recznie zawiniete docstringi > 88 znakow, komentarz "— P-01" przeniesiony do osobnej linii nad stala).
- `docs/CHANGELOG.md` (`### Changed` — na gorze sekcji; `### Fixed` — na koncu, jak poprzednie zadania fali) i `CLAUDE.md` (punkt `--target-crs` dla PL) — patrz "Odstepstwa".

### `f14660b` — pulapka blokow VRT (minor z Zad. 4, dopuszczona w dispatchu "if you hit it")
- **Trafilem ja przez `build_pl_cutout`** (skrypt w scratchpadzie, nie test repo): pierwszy (po sortowaniu) arkusz 200x100 albo 460x50 -> `RasterBlockError: The height and width of TIFF dataset blocks must be multiples of 16`; 460x64, 100x100, 160x200 — OK. Przed `4faef3e` tor PL nie owijal zrodel, wiec ekspozycja jest nowa i pochodzi z tego zadania.
- **Zad. 11 jej nie zamyka dla EPSG:2180**: brief Zad. 11 (d) dodaje `tiled=True, blockxsize=512, blockysize=512` tylko w galezi `if pinned is not None` — sciezka samego cropu (EPSG:2180) dalej dziedziczylaby kafle VRT. Ksztaltu arkuszy 1 m ani przycietych arkuszy przygranicznych/przybrzeznych offline nie znamy (min 407x432 zmierzono tylko na 1977 arkuszach 5 m z cache Hydrografu), a ta fala wlasnie uruchamia wycinek na granicy (R6).
- Poprawka = minimalna z dispatchu: `kwds.setdefault("tiled", False)` w galezi `if wrap:` `mosaic_and_crop` (+ komentarz, + zdanie w docstringu). Tor CZ nie owija -> bez zmian (`tests/test_cuzk_client.py tests/test_cuzk_dmr.py` zielone).
- Testy (`tests/test_transport_mosaic.py`): `test_wrapping_writes_short_wide_first_source[200-100|460-50]` (RED przed poprawka: `RasterBlockError`), `test_wrapping_keeps_explicit_tiling_from_dst_kwds` (straznik `setdefault` — jawne kafle 512 z Zad. 11 nie moga zostac nadpisane).
- Uklad blokow wyniku EPSG:2180 (arkusz 5 m 460x480 px, wynik 440x420): `6bc1c19` — paski po 1 wierszu (profil AAIGrid); `4faef3e` — kafle 128x128 (profil VRT); `f14660b` — paski po 128 wierszy. Wszystkie poprawne dla czytnikow.

### `2ad46cf` — testy po przezytych mutacjach (regula 4)
Dwie mutacje spoza minimum briefu, bronione przez zachowania, ktore brief wprowadza ("wejscia posortowane", "selekcja w obu miejscach — bbox i suma R-01"), PRZESZLY cala suite (1829 passed kazda):
- (5b) tylko suma R-01 bez zapasu (`find_sheets_for_bbox(src, ...)` w galezi geometrii) — brief'owy `test_selection_expanded_by_one_pixel` sprawdza wylacznie tryb bbox;
- (6) `sorted(...)` -> `[Path(p) for p in sheet_paths]` — przy wymuszonym `dtype="float32"` zaden test nie widzi kolejnosci (test Int32 bije tylko w polaczeniu z `dtype=None`, P-07).

Dodane: `TestSheetGrid.test_geometry_sum_selection_expanded_by_one_pixel` (geometria + EPSG:5514, oba discovery zamockowane, asercja obwiedni +-5 m i sumy godel) oraz `TestSheetGrid.test_input_order_does_not_change_result` (arkusze o roznych wartosciach w 10-px zakladce, `[a, b]` vs `[b, a]` -> raster identyczny). Po dodaniu obie mutacje FAIL (nizej).

## RED / GREEN

RED (brief Step 2, kod `6bc1c19` + nowe testy):
```
.venv/bin/python -m pytest tests/test_pl_cutout.py -q -p no:cacheprovider -k "TestSheetGrid or test_pl2000_sheet_returns_1_with_reason"
E   assert 530009.87 == 530010 ± 1.0e-06                      # [ulamkowy]
E   assert 530009.5 == 530010 ± 1.0e-06                       # [calkowity]
E   Mismatched elements: 12325 / 12325 (100%) ... Max absolute difference among violations: 0.63895416   # rampa
E   kartograf.exceptions.ValidationError: mosaic_and_crop: niezgodne CRS wejsc: ['EPSG:2180', 'None']  # .prj
E     Obtained: 100      Expected: 100.25 ± 1.0e-04             # Int32 [a_first]
E   Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>   # PL-2000
E     At index 0 diff: 530010 != 530005.0                        # selekcja
E   assert 0 == 1                                                # CLI PL-2000
================== 8 failed, 1 passed, 38 deselected in 0.92s ==================
```
`[b_first]` zielony przed naprawa — zgodnie z P-07 (straznik regresji, nie RED).

GREEN: `tests/test_pl_cutout.py` 47 passed; pelna suita `1826 passed, 8 deselected` (przed `f14660b`).

RED/GREEN `f14660b`:
```
.venv/bin/python -m pytest tests/test_transport_mosaic.py -q -p no:cacheprovider -k "short_wide or explicit_tiling"
E   rasterio.errors.RasterBlockError: The height and width of TIFF dataset blocks must be multiples of 16   (x2)
FAILED ...test_wrapping_writes_short_wide_first_source[200-100]
FAILED ...test_wrapping_writes_short_wide_first_source[460-50]
================== 2 failed, 1 passed, 23 deselected in 0.39s ==================
# po poprawce: mosaic + cutout + CZ (test_cuzk_client.py, test_cuzk_dmr.py): 147 passed
```

## Zmierzone liczby (test rampy, P-02)
Skrypt w scratchpadzie odtwarzajacy `test_target_5514_warp_has_no_subpixel_shift` (wycinek z arkuszy vs `warp_to_grid` idealnego rastra, 145x85 = 12 325 pikseli, transformacje wynikow rowne):
- **przed naprawa** (`6bc1c19`): srednio **0,3499 m**, maks. **0,6390 m**, rozni sie **12 325 / 12 325** pikseli (100 %);
- **po naprawie** (`4faef3e`): **0 / 12 325** pikseli — bit-w-bit (srednio 0,0000, maks. 0,0000).
Zgodne z briefem (0,35 / 0,64 -> 0).

## Dowody mutacyjne (wszystkie PO commitach; przywracanie `git checkout -- <plik>`, po kazdej `git status` czysty)

Mutacje wykonywane pomocnikiem podmieniajacym DOKLADNIE jedno wystapienie fragmentu (przerwanie przy 0 albo >1 trafieniach).

| # | Mutacja | Komenda (skupiona) | FAIL | Po przywroceniu |
|---|---|---|---|---|
| 1 | `snap_to_source_grid=True` -> `False` (cutout.py) | `pytest tests/test_pl_cutout.py -k "test_target_2180_on_sheet_grid_exact_values or test_target_5514_warp_has_no_subpixel_shift"` | 3 failed: `assert 530009.87 == 530010`, `assert 530009.5 == 530010`, `Mismatched elements: 12325 / 12325 (100%)`, maks. 0.63895416 | 3 passed |
| 2 | `assign_crs="EPSG:2180"` -> `None` | `-k test_mixed_prj_cache_builds` | 1 failed: `ValidationError: mosaic_and_crop: niezgodne CRS wejsc: ['EPSG:2180', 'None']` | 1 passed |
| 3 | `dtype="float32"` -> `None` | `-k test_integer_first_sheet_keeps_decimals` | **oba** `[a_first]` i `[b_first]` FAIL (`Obtained: 100`) — sortowanie stawia `a.asc` pierwsze (P-07) | 2 passed |
| 4 | usuniete wywolanie `_reject_pl2000_sheets(sheet_paths)` | `-k pl2000` | 2 failed: `DID NOT RAISE <class '...ValidationError'>` (biblioteka), `assert 0 == 1` (CLI) | 2 passed |
| 5a | `selection = BBox(... +- px ...)` -> `selection = src` (oba miejsca bez zapasu) | `-k test_selection_expanded_by_one_pixel` | 1 failed: `At index 0 diff: 530010 != 530005.0` | 1 passed |
| 5b | tylko suma R-01: `find_sheets_for_bbox(selection, ...)` -> `find_sheets_for_bbox(src, ...)` | pelna suita | **przed `2ad46cf`: 1829 passed (PRZEZYLA — znalezisko)**; po: 1 failed `test_geometry_sum_selection_expanded_by_one_pixel` (`At index 0 diff: 529983.9346337096 != 529978.9346337096`), 1830 passed | 2 passed (nowe testy) |
| 6 | `sorted(Path(p) for p in sheet_paths)` -> `[Path(p) for p in sheet_paths]` | pelna suita | **przed `2ad46cf`: 1829 passed (PRZEZYLA — znalezisko)**; po: 1 failed `test_input_order_does_not_change_result` (`Mismatched elements: 770 / 18557` = 10 px zakladki x 77 wierszy), 1830 passed | j.w. |
| 7a | `kwds.setdefault("tiled", False)` -> `pass` (mosaic.py) | pelna suita | 2 failed `test_wrapping_writes_short_wide_first_source[200-100|460-50]` (`RasterBlockError ... multiples of 16`), 1829 passed | 3 passed |
| 7b | `kwds.setdefault("tiled", False)` -> `kwds["tiled"] = False` | pelna suita | 1 failed `test_wrapping_keeps_explicit_tiling_from_dst_kwds` (`assert [(10, 200)] == [(512, 512)]`), 1830 passed | j.w. |

## Odstepstwa od briefu (do akceptacji reviewera)
1. **CHANGELOG `### Fixed`, wpis 1** — zdanie z briefu "Arkusze GUGiK maja narozniki pikseli pol piksela od liczb calkowitych" jest nieprecyzyjne: zmierzono tylko 5 m (narozniki 5k + 2,5 m = pol piksela od WIELOKROTNOSCI 5 m, 0,5 m od liczb calkowitych), siatka 1 m jest nieznana offline (fakt 1: checklista live). Zapisano: "narozniki pikseli w polowie miedzy wielokrotnosciami piksela (5 m: na 5k + 2,5 m, zmierzone na 1977 arkuszach; siatka 1 m — do potwierdzenia na zywych danych) ... bboxow o CALKOWITYCH wspolrzednych (np. wielokrotnosci 5 m przy 5 m: 0,5 px = 2,5 m ...)". Dopisane tez (zweryfikowane w kodzie: `skip_existing = not force` w `run_pl_cutout`, `skip_existing and target_path.exists()` w `DownloadManager`): "`--force` pobiera ponownie takze arkusze; tanszy wariant: usun stary plik wycinka i uruchom komende bez `--force` — arkusze z cache zostana uzyte ponownie". Nakaz "przebuduj z `--force`" z Global Constraints zostal.
2. **CHANGELOG `### Fixed`, wpis 2** — "konczyly sie `CRS mismatch`" bylo nieprawda dla uzytkownika: przed naprawa mieszany cache konczyl sie NASZYM bledem `mosaic_and_crop: niezgodne CRS wejsc: ['EPSG:2180', 'None']` (kontrola obecna od `7af6e2f`, odpala przed `merge`; RED wyzej) — zapisano `niezgodne CRS wejsc`. Int32 doprecyzowany: tylko gdy arkusz calkowity trafil na poczatek listy ("przy pobieraniu rownoleglym: kolejnosc ukonczenia pobran" — `_download_hierarchy_parallel` zbiera sciezki w petli `as_completed`); dopisane "a lista zrodel jest sortowana".
3. **CHANGELOG `### Changed`** — dopisane zdanie o zapasie 1 piksela w `select_pl_cutout_sheets` (publiczne API zmienia zachowanie: przy krawedzi bboxa do 1 px od granicy arkusza pobiera sie sasiedni arkusz) oraz "(kazdego `--target-crs`)" przy bledzie PL-2000 (`_reject_pl2000_sheets` dziala w kazdym ukladzie docelowym); "Arkusz zapisany przez GUGiK ..." -> "Arkusz wydany przez skorowidz GUGiK ..." (pod godlem PL-1992 zapisuje go Kartograf, nie GUGiK).
4. `CLAUDE.md` — tekst z briefu doslownie.
5. Dwa dodatkowe commity (`f14660b`, `2ad46cf`) — uzasadnienie wyzej.

## Weryfikacja twierdzen w nowych tekstach (regula 5)
- `GugikProvider._get_opendata_url` ma fallback "pierwszy znaleziony URL" z ostrzezeniem (gugik.py ~l.553-563) — komentarz tam juz zapowiada glosne odrzucenie w wycinku (Zad. 6).
- Sidecar wycinka zapisuje tylko `request` (bbox ZADANIA) — raster wiekszy o < 1 px nie czyni go falszywym; `transform` = `None` przy `pinned is None`; nazwa pliku z `bbox_target` (= zadanie dla EPSG:2180).
- `merge` metoda `first`: pierwsze wazne zrodlo wygrywa w zakladce (potwierdzone mutacja 6 po dodaniu testu).
- Uwaga (nie zmieniane, tekst Zad. 4): docstring `mosaic_and_crop` mowi "i ``merge`` rzucal ``CRS mismatch``" — prawda o samym `merge`, ale w naszym przeplywie wczesniej odpalala wlasna kontrola `niezgodne CRS wejsc`.

## Pliki
- `/home/claude-agent/workspace/Kartograf/kartograf/download/cutout.py`
- `/home/claude-agent/workspace/Kartograf/kartograf/transport/mosaic.py` (tylko `f14660b`)
- `/home/claude-agent/workspace/Kartograf/tests/test_pl_cutout.py`
- `/home/claude-agent/workspace/Kartograf/tests/test_transport_mosaic.py` (tylko `f14660b`)
- `/home/claude-agent/workspace/Kartograf/docs/CHANGELOG.md`
- `/home/claude-agent/workspace/Kartograf/CLAUDE.md`

## Bramka (HEAD `2ad46cf`, drzewo czyste)
- `.venv/bin/python -m pytest tests/ -q -m "not live"` -> **1831 passed, 8 deselected** (1817 + 9 z briefu + 3 pulapka blokow + 2 straznicy mutacji).
- `ruff check kartograf/ tests/` -> All checks passed; `ruff format --check` -> 87 files already formatted.
- `mypy kartograf/` -> Found 32 errors in 9 files; diff listy (`sed -E 's/:[0-9]+: /: /' | sort`) wobec `mypy-baseline.txt`: **pusty**.

## Samoocena i watpliwosci
- Kod z briefu wszedl doslownie; wynik rampy bit-w-bit, wszystkie mutacje z briefu FAIL.
- **Geometria + EPSG:2180 (bez warpu) nie dostaje zapasu 1 px**: tam nie ma sumy R-01 (celowo — R2/ARCHITECTURE 4.3), a `find_sheets_for_geometry` bierze obwiednie obiektow bez zapasu, zas crop jest teraz przyciagany na zewnatrz. Gdy krawedz obwiedni lezy < 1 px wewnatrz nominalnej granicy arkusza, a raster sasiada nie jest wybrany, pasek < 1 px przy krawedzi moze byc nodata. Na realnych arkuszach GUGiK malo prawdopodobne (arkusze zachodza na siebie, fakt 1: 70 m = 14 px przy 5 m, wiec raster wybranego arkusza siega poza jego nominalna granice); kontrakt z CLAUDE.md ("nodata tylko tam, gdzie nie siega zaden pobrany arkusz") pozostaje doslownie prawdziwy. Brief tego nie obejmowal — nie zmienialem; do decyzji kontrolera.
- `f14660b` zmienia wspolny `transport/mosaic.py` poza lista plikow briefu — na podstawie wprost dopuszczonej sciezki z dispatchu; jesli kontroler uzna, ze "hit" wymagal realnego arkusza GUGiK, commit jest samodzielny i odwracalny (`git revert f14660b`), ale wtedy sciezka EPSG:2180 zostaje narazona takze po Zad. 11.
- `_reject_pl2000_sheets` otwiera kazdy arkusz drugi raz (poza przebiegiem metadanych w `mosaic_and_crop`): wg faktu 4 ~0,3-0,5 ms/arkusz, czyli ~0,6 s na 1200 arkuszy — pomijalne.
