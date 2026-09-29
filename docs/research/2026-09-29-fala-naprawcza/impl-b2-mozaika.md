# Pakiet B2 — mozaika/wycinek: S5 (D3 + D8), N4 (wycinek), N9

Data: 2026-09-29. Galaz `develop`, baza: `5e5e653` (A1). Testy offline, zero sieci.

## Co zmienione

### S5 — `transport/mosaic.py` (D3)
- Detekcja siatki wydzielona z `_snap_outward` do publicznego
  `check_source_grid(paths) -> SourceGrid(reference: Affine, off_grid: tuple[OffGridSource(path, dx_px, dy_px), ...])`
  (otwiera zrodla po jednym, tylko metadane) + wewnetrzne `_source_grid(paths, transforms)`
  na gotowych transformacjach (`mosaic_and_crop` uzywa metas, ktore i tak czyta).
- Siatke odniesienia wybiera nadal wiekszosc (kubelki `_phase_key`, remis = pierwsze na
  liscie), ale o przynaleznosci KAZDEGO zrodla rozstrzyga `|przesuniecie| <= 1e-6 px`
  z owinieciem przez 1 (`_shift_px`, modulo w [-0,5; 0,5)) — nie rownosc kubelkow.
- `mosaic_and_crop(..., snap_to_source_grid=True)` przy `off_grid` rzuca
  `GridMismatchError` (`exceptions.py`, podklasa `ValidationError`, atrybut `.off_grid`)
  z komunikatem `"{n} z {m} zrodel lezy na innej siatce pikseli niz pozostale (maks.
  przesuniecie {worst:.3f} px): {do 10 nazw}"` (`SourceGrid.describe_off_grid`).
  Galaz `logger.warning` "najblizszym sasiadem" i akapity docstringow o niej usuniete;
  `logging` w module nie jest juz potrzebne. `_snap_outward(bounds, reference)` robi tylko
  rozszerzenie bboxa.
- `_vrt_xml`/`_VRT_TYPES` przeniesione do `transform/raster.py` jako `vrt_xml`/`VRT_TYPES`
  (mozaika importuje je stamtad) — jeden mechanizm owijania dla mozaiki i warpu (nizej).
- `has_valid_pixels` (A2) nietkniete.

### S5 — `transform/raster.py` (D8, W1)
- `warp_to_grid(sources: Path | Sequence[Path], ...)`: lista zrodel = kazde
  reprojektowane RAZ ze swojej siatki do TEGO SAMEGO pasma docelowego (pierwsze
  `init_dest_nodata=True`, kolejne `False`), bez `merge` i bez pliku posredniego.
  Lista jest przetwarzana OD KONCA: smoke-test (skrypt jednorazowy, rasterio 1.5.0 /
  GDAL) potwierdzil, ze GDAL nadpisuje wazne piksele kolejnym zrodlem, a nodata zrodla NIE
  nadpisuje waznych pikseli poprzednika — wiec pierwsze na liscie wygrywa w zakladce jak
  w `rasterio.merge`. Test trwaly:
  `test_transform_raster.py::test_many_sources_first_wins_and_nodata_never_overwrites`.
- Kazde zrodlo idzie przez VRT 1:1 w `/vsimem/` z wymuszonym SRS (`src_crs`) i pasmem
  Float32 (`_vrt_over`): `reproject` ze zrodla BEZ CRS (arkusz ASC GUGiK bez `.prj`)
  zwracal SAM nodata mimo jawnego `src_crs` (zmierzone; pierwsza wersja W1 dala 7072/7072
  nodata) — test `test_source_without_crs_takes_src_crs`. Dotyczy takze pojedynczego
  zrodla (plik posredni mozaiki) — wynik bit w bit identyczny ze sciezka sprzed zmiany
  (sprawdzone skryptem: `np.array_equal` == True, max |diff| 0.0 na mozaice 2 arkuszy 1 m
  -> EPSG:5514).
- Pusta lista -> `ValidationError`.

### S5 — `download/cutout.py::build_pl_cutout`
- Przed mozaika `grid = check_source_grid(sorted(paths))`:
  - `pinned is None` (EPSG:2180) i `off_grid` -> `GridMismatchError` z podpowiedzia CLI:
    `"{n} z {m} arkuszy lezy na innej siatce pikseli niz pozostale (maks. przesuniecie
    X px): ... — wycinek EPSG:2180 wymaga wspolnej siatki (wartosci 1:1). Zadaj wycinek
    w ukladzie z pelnym warpem (--target-crs EPSG:5514 albo EPSG:3045) albo pobierz
    obszar jako arkusze (bez --target-crs). Arkusze zostaja w cache."`; blad pada PRZED
    `mkdir` katalogu `bbox/`;
  - `pinned` i `off_grid` -> W1: `warp_to_grid(paths, ...)`; funkcja zwraca
    `tuple[str, ...]` godel (stem) arkuszy off-grid;
  - jedna faza -> dotychczasowa sciezka (mozaika 1:1 + warp), zwraca `()`.
- `PlCutoutResult.off_grid_sheets: tuple[str, ...] = ()`;
  `write_pl_cutout_sidecar(off_grid_sheets=)` -> `extra.off_grid_sheets` tylko gdy
  niepuste (czyli tylko na sciezce W1); `run_pl_cutout` przekazuje wynik `build_pl_cutout`
  do sidecara i wyniku. `kartograf.GridMismatchError` w `__all__`.

### N4 (wycinek) — `download/cutout.py`
- `skipped_pl_cutout(cutout) -> PlCutoutResult(skipped=True, missing_sheets=...,
  off_grid_sheets=...)` czyta `extra.missing_sheets`/`extra.off_grid_sheets` z sidecara
  istniejacego wycinka (best-effort: brak/nieczytelny sidecar albo brak pol = puste;
  pomocnik `_sidecar_sheet_list` odrzuca inny ksztalt). Uzyte w `run_pl_cutout` i
  `download_pl_cutout` zamiast `PlCutoutResult(path, skipped=True)`. `sheet_paths` przy
  skipie zostaje `()` (udokumentowane w docstringu dataclassy).

### N9 — `download/cutout.py::estimate_pl_cutout_bytes`
- `_sheet_frame_transformer()` (`functools.cache`, jeden `Transformer.from_crs(4326->2180)`
  na proces) + `_sheet_frame_2180(godlo)` (obwiednia 4 przetransformowanych naroznikow
  WGS84 arkusza — dokladnie jak `SheetParser.get_bbox("EPSG:2180")`, ale bez budowy
  transformera per arkusz). Bez zmiany API; `core/sheet_parser.py` nietkniety (poza
  wlasnoscia B2).
- Pomiar (skrypt jednorazowy, 512 arkuszy 1:10000 = `M-34-76` + `M-34-64`, zero w
  cache, ten sam bbox): **przed** 3,336 s / 3,316 s (1. i 2. wywolanie),
  **po** 0,059 s / 0,046 s; `need` identyczne (14 893 748 652 B). Podwojne wywolanie
  (wolajacy + `run_pl_cutout`) kosztuje wiec ~0,1 s zamiast ~6,6 s.

## Zmiany wlasnosci (uzgodnione)
- Main (IRC): `run_pl_cutout` (linie skipu i wywolania `build_pl_cutout`/sidecara/wyniku)
  oraz `download_pl_cutout` (linia skipu) tymczasowo B2; B1 dopisze `all_nodata` po tym
  commicie.
- A1 (IRC): `write_pl_cutout_sidecar(off_grid_sheets=)` i linia skipu w
  `download_pl_cutout` edytowane dopiero PO jego commicie `5e5e653` (jego wersja pliku
  identyczna z kopia, na ktorej pracowalem w osobnym worktree).

## Testy: failing-before / passing-after

Dowod: nowe pliki testow uruchomione na drzewie `git worktree` z HEAD `5e5e653`
(kod sprzed B2) — 10 nowych testow FAILED, po zmianach wszystkie PASSED
(`test_transport_mosaic.py` 38, `test_transform_raster.py` 13, `test_pl_cutout.py` 73 =
124 passed).

| Test | Na HEAD sprzed B2 | Po |
|---|---|---|
| `test_transport_mosaic.py::test_snap_rejects_off_grid_source` (`odd.tif`, `0.250 px`, `.off_grid`, brak pliku) | modul nie importuje sie (`GridMismatchError`/`check_source_grid` nie istnieja); stary kod = `logger.warning` i plik powstaje | PASS |
| `test_snap_tolerates_float_noise` (x0 = 0 i 1e-9) | jw. | PASS |
| `test_check_source_grid_wraps_phase_through_one`, `..._reports_shift_of_every_off_grid_source`, `..._rejects_mixed_resolution` | jw. | PASS |
| `test_snap_uses_majority_grid_and_warns` | pinowal ostrzezenie — USUNIETY | — |
| `test_pl_cutout.py::TestOffGridSheets::test_target_2180_off_grid_sheets_is_an_error` (ASC 5 m `xllcorner 535807.22`/`538045.16`, `cellsize 5` -> `run_pl_cutout` 2180) | FAIL (plik powstaje; `GridMismatchError` nie istnieje) | PASS: `GridMismatchError`, "1 z 2 arkuszy", "0.412 px", `--target-crs EPSG:5514`, `EPSG:3045`, `.off_grid[0].dx_px == -0.412`, brak pliku, brak `bbox/`, arkusze w cache |
| `TestOffGridSheets::test_cli_target_2180_off_grid_returns_1_with_hint` (worker CLI `_download_pl_bbox`) | FAIL (`rc 0`) | PASS: rc 1, stderr `Error: 1 z 2 arkuszy ... --target-crs EPSG:5514 ... Arkusze zostaja w cache` — bez edycji `test_cli.py` |
| `TestOffGridSheets::test_target_5514_warps_each_off_grid_sheet_separately` (te same arkusze, 100,25 i 200 [Int32]) | FAIL (brak `off_grid_sheets`; stary kod: mozaika posrednia z kolumna nodata na szwie, po bilinearze ~70 wartosci posrednich — zmierzone skryptem na HEAD) | PASS: dokladnie {100.25, 200.0}, zero nodata, zachodni wygrywa do 538107, sidecar `extra.off_grid_sheets` |
| `TestOffGridSheets::test_single_phase_sheets_keep_mosaic_path` | FAIL (atrybut) | PASS: `mosaic_and_crop` raz, warp z `*.mosaic.tif`, bez `off_grid_sheets` |
| `TestMissingSheets::test_skipped_run_reads_missing_sheets_from_sidecar` | FAIL (`() == ('N-34-130-D-d-2-4',)`) | PASS (provider nie wolany; bez sidecara `()`) |
| `TestLibraryApi::test_skipped_download_reads_sheet_lists_from_sidecar` | FAIL (jw.) | PASS |
| `TestCutoutSize::test_estimate_builds_one_transformer_for_all_sheets` (licznik `Transformer.from_crs`, 3 arkusze x 2 wywolania -> 1; bajty == wzor `SheetParser`) | FAIL (brak cache; stary kod: 6 transformerow) | PASS |
| `test_transform_raster.py::test_many_sources_first_wins_and_nodata_never_overwrites`, `test_source_without_crs_takes_src_crs`, `test_empty_source_list_is_an_error` | FAIL (`list` bez `.name`; zrodlo bez CRS -> sam nodata) | PASS |

Ruff check + format: czyste na wszystkich plikach pakietu. mypy `kartograf/`: lista 32
bledow identyczna z baseline (pierwsza wersja importowala `Affine` z `affine` ->
`import-untyped`; poprawione na `rasterio.transform.Affine`).

## Smoke offline na danych L1 (19 arkuszy 5 m, 19 faz)

Kopia `e2e-data/2026-09-29-live/L1-centrum-produkty/data/nmt` w `/tmp`, provider-atrapa
rzucajacy `NoCoverageError` (zero sieci), biblioteka (`prepare` -> `select` -> `run`):
- `check_source_grid` na wszystkich 19 arkuszach: **18 z 19 off-grid**
  (odniesienie `535807.22/239418.19`).
- bbox L1 `536000,233000,541000,238000`, `--target-crs EPSG:2180`, 9 arkuszy:
  **`GridMismatchError` "8 z 9 arkuszy ... (maks. przesuniecie 0.412 px)"** w 0,01 s,
  bez pliku, bez `bbox/`. (Uwaga: kopia katalogu L1 zawiera stary wycinek z testu na zywo
  — przy pierwszym przebiegu `run_pl_cutout` zwrocil `skipped=True`, stary plik ma
  766 px nodata; usuniety przed wlasciwym smoke.)
- bbox L1, `EPSG:5514`: W1, 12 arkuszy (3 poza cache -> `missing_sheets`), 1074x1074,
  `off_grid_sheets` = 8, 0,50 s, brak kolumn/wierszy w calosci nodata.
- bbox wewnatrz bloku 16 arkuszy `M-34-76-A-a` (1,5 km od krawedzi, zero brakujacych):
  2180 -> `GridMismatchError` "15 z 16 (0.472 px)"; 5514 -> W1 1300x1355 w 0,82 s;
  3045 -> W1 1274x1330 w 0,62 s; w obu zero kolumn/wierszy nodata, wartosci 203..427 m.

**Pozostalosc (nie regresja rodzaju, do udokumentowania w fali C):** w wyniku W1 na
bloku 16 arkuszy jest 910 (5514) / 922 (3045) pojedynczych pikseli nodata (~0,05 %)
rozsianych wzdluz szwow; stara sciezka (mozaika `merge` + warp, HEAD sprzed B2) na tym
samym bloku daje 673 / 661. Analiza: kazdy arkusz GUGiK 5 m ma ~2,5-3 tys. px nodata
w klinach miedzy prostokatem a trapezem tresci (linie siatki geograficznej), sasiednie
arkusze zachodza na siebie o ~3 px, a "schodki" tresci dwu arkuszy leza na roznych
siatkach — 100 % tych dziur ma wazny piksel w otoczeniu 3x3 ktoregos arkusza (okno
bilineara 2x2 go nie siega), zadna nie jest dziura w unii tresci. To wlasciwosc danych
i bilineara z maska nodata, obecna takze przed zmiana; W1 ma ich o ~35 % wiecej, bo
schodki nie sa juz zaokraglane na wspolna siatke. Wypelnianie takich dziur to osobna
funkcja (nie w zakresie D8).

## Ryzyka / uwagi
- `check_source_grid` w `build_pl_cutout` otwiera kazdy arkusz raz wiecej (metadane;
  `_reject_pl2000_sheets` i `mosaic_and_crop` robily to juz dwukrotnie) — dla 1200
  arkuszy ASC to rzad sekundy wobec godzin pobierania.
- W1 reprojektuje CALY arkusz (GDAL sam liczy okno zrodla z zasiegu celu), wiec arkusze
  z zapasu R-01 daleko od bboxa kosztuja tylko otwarcie.
- Szwy W1 = niezalezne warpy: brak mieszania wartosci przez szew (test wymaga dokladnie
  dwu poziomow); na sciezce mozaiki interpolator widzi sasiada zza szwu (wartosci
  posrednie miedzy poziomami) — jak dotad.
- Docs do fali C (nie ruszane): CLAUDE.md (S5 w "Ograniczenia", "znany blad S5"),
  README `:255`, SCOPE `:63-64`, ARCHITECTURE 4.3 krok 5-6 (+ `extra.off_grid_sheets`,
  `skipped` z sidecara, kontrola dysku "tania"), ADR-027 addendum D3/D8, CHANGELOG
  (Fixed: S5, N4, N9; Breaking: kod 1 dla 2180 z arkuszy o roznych fazach; nowy wyjatek).

## Handoff dla B1 (CLI)
- `_download_pl_cutout` pomija istniejacy wycinek PRZED biblioteka (`download_cmd.py:1004`)
  — uzyc `skipped_pl_cutout(cutout)` i wypisac ten sam `Warning:` co przy budowie
  z dopiskiem "(z sidecara istniejacego wycinka)"; analogicznie `Info:` o
  `result.off_grid_sheets` (W1) — pole juz jest w `PlCutoutResult`.
- `run_pl_cutout` jest gotowe na `all_nodata` (N2); moje zmiany w nim: linia skipu
  (`skipped_pl_cutout`), `off_grid = build_pl_cutout(...)`, `off_grid_sheets=` w sidecarze
  i wyniku.
- `test_cli.py` nie wymagal edycji (test rc 1 dla 2180 zyje w `test_pl_cutout.py`).

## Pliki
`kartograf/transport/mosaic.py`, `kartograf/transform/raster.py`, `kartograf/exceptions.py`,
`kartograf/download/cutout.py`, `kartograf/__init__.py`, `tests/test_transport_mosaic.py`,
`tests/test_transform_raster.py`, `tests/test_pl_cutout.py`, ten raport.
