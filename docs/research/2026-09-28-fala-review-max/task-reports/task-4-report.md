# Zad. 4 — raport implementera (opus)

**Status:** DONE_WITH_CONCERNS (jedno swiadome odstepstwo od kodu briefu — sekcja "Odstepstwa", pkt 1; do decyzji reviewera)
**Commit:** `dc45432` feat(transport): mosaic_and_crop(assign_crs=, dtype=) — normalizacja zrodel przez VRT (BASE `784ea47`)
**Pliki:** `kartograf/transport/mosaic.py`, `tests/test_transport_mosaic.py` (nic w `kartograf/providers/cuzk/*`, nic w `transform/raster.py`)

## Co zrobiono

`kartograf/transport/mosaic.py`:
- importy `os`, `warnings`, `escape` (xml.sax.saxutils), `CRS` (pyproj), `MemoryFile` (rasterio.io);
- `_VRT_TYPES` (l. 33), `_vrt_xml` (l. 44), `_same_projection` (l. 64) — doslownie z briefu (P-01), tylko sformatowane przez ruff;
- `mosaic_and_crop(..., assign_crs: str | None = None, dtype: str | None = None)` (keyword-only, l. 137):
  - petla metadanych zbiera `meta = {crs, transform, width, height, count, dtype, nodata}` do `metas` (+ `res` do `res_set`), jeden deskryptor naraz jak po Zad. 2; `transforms = [m["transform"] for m in metas]` (l. 211, P-20) — `_snap_outward` konsumuje je bez zmian;
  - bez `assign_crs`: kontrola `crs_set` jak dotad (ten sam komunikat "niezgodne CRS wejsc"); z `assign_crs`: `target = CRS.from_user_input(assign_crs)`, zrodlo z `meta["crs"] is not None and not _same_projection(...)` -> `ValidationError` z komunikatem z briefu ("... ma CRS ..., a wymuszany jest ..."); CRS `None` dozwolony, `crs_set` nie sprawdzany;
  - przy owijaniu (`assign_crs or dtype`): `count != 1` -> `ValidationError` ("... ma N pasm — owijanie w VRT ... tylko rastry jednopasmowe"); typ (`dtype or meta["dtype"]`) spoza `_VRT_TYPES` -> `ValidationError` ("typ pasma ... spoza obslugiwanych: [...]") — walidacja PRZED przyciaganiem i merge (fail-fast);
  - przy owijaniu `kwds.setdefault("driver", "GTiff")` (l. 280); owijanie tuz przed `merge`, PO przyciaganiu z Zad. 3; blok `memfiles`/`try`/`finally: memfile.close()` jak w briefie (l. 285-320), `zip(..., strict=True)`;
  - docstring: akapit o `assign_crs`/`dtype` (po co: `.prj` od Hydrografu -> `CRS mismatch`; Int32 z pierwszego zrodla; co odrzuca; domyslny GTiff). Kazde zdanie sprawdzone testem albo sonda (nizej).
- Wywolanie CZ (`providers/cuzk/client.py:182`: `mosaic_and_crop(tile_paths, bbox, output_path, nodata=no_data)`) nie owija (`wrap=False`) — sciezka identyczna jak przed zmiana (merge dostaje `paths`, `kwds` bez `driver`).

`tests/test_transport_mosaic.py`: `from pyproj import CRS` na gorze; helpery `_write_asc_text`, `_write_prj`, `_HYDROGRAF_2180_WKT`, `_2180_WKT_VARIANTS` i 4 testy z briefu DOSLOWNIE (ruff format przelamal tylko argumenty wywolan); plus 3 testy wlasne (4 przypadki):
- `test_wrapping_rejects_multiband_source` — wymaganie briefu "zrodlo wielopasmowe przy owijaniu -> ValidationError" nie mialo testu;
- `test_wrapping_rejects_type_without_vrt_name[zadany_typ|typ_zrodla]` — wymaganie "typ spoza `_VRT_TYPES` -> ValidationError" (zadany `float16`; wlasny typ zrodla `int8` przy samym `assign_crs`); z asercja sensownosci, ze zrodlo naprawde czyta sie jako dany typ;
- `test_wrapping_keeps_each_source_own_nodata` — straz odstepstwa nr 1.

## Odstepstwa od briefu i rozbieznosci (do decyzji reviewera)

1. **`NoDataValue` VRT = nodata WLASNE zrodla (`nodata=meta["nodata"]`), a nie `nodata if nodata is not None else meta["nodata"]` z briefu.** Powod — zmierzone (sonda w scratchpadzie, potem test): VRT `SimpleSource` kopiuje piksele zrodla doslownie, wiec gdy nodata mozaiki != nodata zrodla, piksele nodata zrodla przestaja byc maskowane. Przy zachodzacych arkuszach (fakt 1: w zakladce wazny jest tylko jeden z dwoch) pierwsze zrodlo wpisuje swoje `-9999` jako DANE i blokuje wazne piksele nastepnego (merge "first" wypelnia tylko piksele rowne nodata mozaiki):
   - bez owijania: `[1.5, 1.5, 2.5, 2.5, 2.5, 2.5]`; z wyrazeniem briefu (nodata mozaiki -32768): `[1.5, 1.5, -9999, -9999, 2.5, 2.5]` — 8/24 pikseli zepsutych (mutacja 9 nizej); z `meta["nodata"]`: identycznie jak bez owijania.
   - Dla wywolania PL z planu (Zad. 9: `nodata=-9999.0`, naglowki GUGiK `-9999`) oba wyrazenia daja ten sam wynik — defekt byl utajony; w pozostalych przypadkach (nodata mozaiki None; zrodlo bez nodata) wyniki tez sa identyczne (przeanalizowane: merge i tak traktuje piksel rowny nodata mozaiki jako "do nadpisania"). Nodata WYNIKU nadal ustawia `merge` (test sprawdza `w.nodata == -32768.0`).
   - Efekt uboczny: do XML nie trafia juz `nodata` od wywolujacego, tylko `src.nodata` z rasterio (Python float) — znika pulapka numpy 2 (`repr(np.float64(-9999.0))` = `'np.float64(-9999.0)'`, a `np.float64` przechodzi przez adnotacje `float`). NaN nodata sprawdzony: wynik z owijaniem = bez owijania.
   - Sygnatura `_vrt_xml(..., nodata)` bez zmian (jak w briefie); zmienione jest tylko wyrazenie w wywolaniu + komentarz przy nim + zdanie w docstringu.
2. **Mutacja 2 pada wczesniej, niz przewiduje brief:** na `assert src.dtypes[0] == "float32"` (`'int32' == 'float32'`), a nie na wartosci. Wartosc pod mutacja sprawdzona osobno (sonda): `dtype int32 value b: 100` (fakt 5 potwierdzony: 100,25 -> 100); po przywroceniu `float32 100.25`.
3. **Mutacja 4 w wersji doslownej ("lista `rasterio.open(mf.name)` w `ExitStack`", merge dalej dostaje nazwy) PRZECHODZI** — to NIE jest luka testu: GDAL otwiera zrodlo `SimpleSource` leniwie (przy pierwszym odczycie). Zmierzone: 300 otwartych, nieczytanych VRT = **+0 fd**; po odczycie przez wszystkie = **+100 fd** (pula `GDAL_MAX_DATASET_POOL_SIZE`); po zamknieciu +0. Szkodliwy wariant "wszystkie VRT naraz" to przekazanie OTWARTYCH datasetow do `merge` (4b) — ten pada przy zapasie 64 (`t064.tif: Too many open files`).
4. **Prog maskowania puli (P-05) = 100, nie "~110":** mutacja 4b pada dla zapasu <= 99 (sprawdzone 64, 80, 90, 95, 97, 98, 99), przechodzi od 100 (100, 105, 110, 120, 160). Zapas 64 z briefu jest wewnatrz okna rozrozniania [1, 99].

## RED (Step 2)

```
$ .venv/bin/python -m pytest tests/test_transport_mosaic.py -q --tb=line -p no:randomly
E   TypeError: mosaic_and_crop() got an unexpected keyword argument 'assign_crs'
E   TypeError: mosaic_and_crop() got an unexpected keyword argument 'dtype'
FAILED ...::test_assign_crs_merges_sources_with_and_without_prj[wkt1_gdal]
FAILED ...::test_assign_crs_merges_sources_with_and_without_prj[wkt1_esri]
FAILED ...::test_assign_crs_merges_sources_with_and_without_prj[hydrograf]
FAILED ...::test_assign_crs_rejects_source_with_other_crs
FAILED ...::test_dtype_float32_keeps_decimals_when_first_source_is_integer
FAILED ...::test_vrt_wrapping_does_not_exhaust_file_descriptors
FAILED ...::test_wrapping_rejects_multiband_source
FAILED ...::test_wrapping_rejects_type_without_vrt_name[zadany_typ]
FAILED ...::test_wrapping_rejects_type_without_vrt_name[typ_zrodla]
FAILED ...::test_wrapping_keeps_each_source_own_nodata
======================== 10 failed, 13 passed in 1.86s =========================
```

## GREEN (Step 3-4)

```
$ .venv/bin/python -m pytest tests/test_transport_mosaic.py -q -p no:randomly
============================== 23 passed in 2.79s ==============================
$ .venv/bin/python -m pytest tests/test_cuzk_client.py tests/test_cuzk_dmr.py -q
============================== 74 passed in 5.24s ==============================
$ .venv/bin/python -m pytest tests/ -q -m "not live"
===================== 1795 passed, 8 deselected in 26.82s ======================   (baseline 1785 + 10 nowych)
```

## Dowody mutacyjne (wszystkie PO commicie `dc45432`; kazda: zmiana -> FAIL -> `git checkout -- kartograf/transport/mosaic.py` -> PASS -> `git status --short` pusty)

Mutacje nakladane skryptem, ktory podmienia DOKLADNIE jedno wystapienie (inaczej przerywa); zmiana potwierdzana `git diff`.

| # | Mutacja | Test (komenda: `.venv/bin/python -m pytest <test> -q`) | FAIL (fragment) | Po przywroceniu |
|---|---|---|---|---|
| 1 | `sources.append(memfile.name)` -> `sources.append(path)` (kontrola `crs_set` pominieta jak przy `assign_crs`) | `::test_assign_crs_merges_sources_with_and_without_prj` | `rasterio.errors.RasterioError: CRS mismatch with source: .../b.asc` — 3 failed | 3 passed |
| 2 | `dtype=dtype or meta["dtype"]` -> `dtype=meta["dtype"]` | `::test_dtype_float32_keeps_decimals_when_first_source_is_integer` | `AssertionError: assert 'int32' == 'float32'` (wartosc pod mutacja: 100 — sonda) | 1 passed |
| 3 | kontrola "wymuszany" -> `pass` | `::test_assign_crs_rejects_source_with_other_crs` | `Failed: DID NOT RAISE <class 'kartograf.exceptions.ValidationError'>` | 1 passed |
| 4a | wszystkie VRT otwarte w `ExitStack`, merge dostaje nazwy | `::test_vrt_wrapping_does_not_exhaust_file_descriptors` | **PASS** — nieszkodliwa (+0 fd, leniwe zrodla VRT; pkt 3 wyzej) | 1 passed |
| 4b | jw., ale merge dostaje OTWARTE datasety (`held or sources`) | jw. | `CPLE_OpenFailedError: .../t064.tif: Too many open files` -> `RasterioIOError: Read failed` | 1 passed |
| 5 | `kwds.setdefault("driver", "GTiff")` -> `pass` | `::test_assign_crs_merges_sources_with_and_without_prj` | `CPLE_AppDefinedError: Writing through VRTSourcedRasterBand is not supported.` -> `RasterioIOError: Write failed` w `mosaic.py:311` (merge) — ZANIM asercja drivera (P-17); z nowych testow pada 5 (3 warianty + Int32 + fd), reszta rzuca przed merge albo podaje driver jawnie | 23 passed |
| 6 | `_same_projection` -> samo `candidate.equals(target, ignore_axis_order=True)` | `::test_assign_crs_merges_sources_with_and_without_prj` | `ValidationError: ... zrodlo a.asc ma CRS PROJCS["ETRF2000-PL / CS92",...], a wymuszany jest EPSG:2180` (wkt1_gdal) oraz `... ma CRS EPSG:2180, a wymuszany jest EPSG:2180` (wkt1_esri, hydrograf) — 3 failed | 23 passed |
| 7 | usuniety check `count != 1` | `::test_wrapping_rejects_multiband_source` | `Failed: DID NOT RAISE` | 1 passed |
| 8 | usuniety check typu spoza `_VRT_TYPES` | `::test_wrapping_rejects_type_without_vrt_name` | `KeyError: 'float16'`, `KeyError: 'int8'` — 2 failed | 2 passed |
| 9 | `nodata=meta["nodata"]` -> wyrazenie z briefu `nodata if nodata is not None else meta["nodata"]` | `::test_wrapping_keeps_each_source_own_nodata` | `Mismatched elements: 8 / 24 (33.3%)`, `[0, 2]: -9999.0 (ACTUAL), 2.5 (DESIRED)` | 1 passed |
| 10 | (P-20) `transforms = [... for m in reversed(metas)]` | `tests/test_transport_mosaic.py` | `test_snap_uses_majority_grid_and_warns`: ostrzezenie wskazuje `b.tif` zamiast `odd.tif` — 1 failed, 22 passed | 23 passed |

Po ostatniej mutacji: `git status --short` pusty, `git diff HEAD --stat` pusty, HEAD = `dc45432`.

## Pomiary, o ktore prosi brief

**Deskryptory (Step 4)** — replika testu w osobnych procesach, zapas H = limit - `in_use` (`in_use` liczy tez przejsciowy fd samego `os.listdir`):
- poprawny kod z owijaniem: OK dla H = 64, 16, 8, 6, 5, 4, 3, 2, **1**; FAIL dla H = **0** (`RasterioIOError: Read failed`) — czyli faktycznie 2 wolne deskryptory (wynik + jedno czytane zrodlo);
- ta sama miara BEZ owijania: identycznie (OK przy 1, FAIL przy 0) — VRT w `/vsimem/` nie kosztuje zadnego deskryptora;
- mutacja 4b: FAIL dla H <= 99, OK od H = 100 (pula 100 + wynik).

**`_same_projection` na zrodlo** (300 powtorzen, CRS z `.prj` obok ASC): WKT1_GDAL 0,36 ms, `.prj` Hydrografu 0,28 ms (1200 arkuszy ~0,3 s), WKT1_ESRI z pyproj **25,5 ms** (1200 arkuszy ~31 s). Caly koszt ESRI to `CRS.from_user_input(src_crs.to_wkt())` (24,9 ms; `equals`/`to_dict` < 0,05 ms) — linia doslownie z briefu. Realny przypadek (Hydrograf) jest tani; ewentualna optymalizacja (memo po tekscie WKT — arkusze jednego wycinka maja ten sam `.prj`) NIE wprowadzona (poza zakresem).

## Bramki

- Pelna suita offline: **1795 passed, 8 deselected** (`-m "not live"`); CZ: 74 passed.
- `ruff check kartograf/ tests/`: All checks passed; `ruff format --check`: 86 files already formatted.
- `mypy kartograf/`: `Found 32 errors in 9 files`; lista po `sed -E 's/:[0-9]+: /: /' | sort` **identyczna** z `mypy-baseline.txt` (diff pusty).

## Samoocena i watpliwosci

- Kod = brief poza pkt 1 "Odstepstw" (swiadome, udowodnione mutacja 9 i sonda). Jesli kontroler woli doslownosc — wystarczy przywrocic wyrazenie, ale wtedy test `test_wrapping_keeps_each_source_own_nodata` pada (i powinien).
- Komunikaty `ValidationError` dla wielu pasm i typu spoza mapy — wlasne (brief ich nie podaje); testy dopasowuja `"pasm"` i `"typ pasma"`.
- `CRS.from_user_input(assign_crs)` z blednym napisem rzuci `pyproj.exceptions.CRSError`, nie `ValidationError` — wywolujacy podaja stale ("EPSG:2180"), wiec zostawione jak w briefie.
- `warnings.catch_warnings()` w `_same_projection` nie jest bezpieczne watkowo (globalne filtry) — dzisiejsi wywolujacy z `assign_crs` sa jednowatkowi; tylko odnotowuje.
- Przy owijaniu profil wyniku bez `dst_kwds` bierze bloki z profilu PIERWSZEGO VRT, a ten ma blok `min(128, rozmiar zrodla)` (zmierzone): zrodla 300x300 -> wynik GTiff `tiled=True` 128x128; zrodla 4x4 -> wynik paskowy (`tiled=False`, blok 8x4). Oba zapisuja sie poprawnie; bloki 512 + kompresja to Zad. 9 (fakt 6/10).
