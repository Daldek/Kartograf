# Implementacja — pakiet A2 CZ (K2, K6, N3 + helper N2)

Data: 2026-09-29. Galaz `develop`, baza `c5b3110`. Projekt: `research-cz.md`
sekcje 1.2-1.3, 2.2-2.3, 3.2-3.3, 4.2, 6; decyzje D1 + rozstrzygniecia
koordynatora (pin niejawny w `build_pinned_transform`, `MAX_EXPORT_PIXELS =
4_000_000`, kafle kwadratowawe, snap NW). Prace rozpoczal agent `A2Cz`
(transkrypt `history://A2Cz`, padl na limicie), dokonczyl `A23Finish`.
Zero sieci; tylko wlasne pliki testow.

## Co zmienione

### K2 — `kartograf/transform/crs.py`
- `DATUM_STEP_PINS: dict[int, frozenset[str]] = {5514: {"EPSG:1622", "EPSG:1623"}}`
  (komentarz: obszary uzycia EPSG to prostokaty, slowacki siega Zlina
  i Jaworzynki, AOI nie rozstrzyga).
- `_epsg_code(crs)` (`CRS.from_user_input(...).to_epsg()`, `None` bez
  autorytetu), `_operation_codes(transformer)` (kody krokow z
  `to_json_dict()`, `INVERSE(EPSG)` -> `EPSG`, operacja pojedyncza = `[doc]`).
- `build_pinned_transform`: `required` = suma pinow dla `src_crs`/`dst_crs`;
  filtr PO filtrze dokladnosci, PRZED probe; odrzut trafia do `rejected`
  z powodem `krok datum spoza przypietych ['EPSG:1622', 'EPSG:1623'] (operacja
  innego kraju dla tego samego datum)`. Sygnatury bez zmian, `min` po
  dokladnosci zostaje.
- `KNOWN_PATHS`: 5514<->2180 `0.5 -> 1.0` z nowymi notami (EPSG:1622, pin,
  EPSG:4829 = SK); NOWE wpisy 5514->3045 (1.0) i 5514->4326 (1.0, EPSG:1623);
  Bpv->EVRF2007 nota `+0,11..+0,15 m` (L4 U7). Docstring modulu pkt 3.
- `providers/cuzk/dmr.py`: TYLKO komentarze/docstringi (`NATIVE_CRS`,
  `_HORIZONTAL_POLICY`, docstring `_export_raster`) — "1,25 m dla 3045" to
  roznica operacji 1622/4829 w lokalnej referencji, nie blad serwera
  (errata ADR-024; 135 m dla `imageSR=2180` zostaje).
- `transform/raster.py`: docstring `:4-7` — usuniete "tor CZ zweryfikowany
  na zywo — nie ruszamy" (D1); oba tory wymuszaja operacje z `transform/crs.py`.

### K6 — `kartograf/providers/cuzk/client.py`
- `MAX_EXPORT_PIXELS = 4_000_000` (komentarz z sondami: 7,5 Mpx OK, 8,38 Mpx
  HTTP 500); `export_image` idzie torem pojedynczym tylko gdy
  `w <= 15000 and h <= 4100 and w*h <= MAX_EXPORT_PIXELS`.
- `_tile_grid(bbox, pixel_size, width_px, height_px, max_w, max_h, max_px)`:
  `col_cap = min(max_w, isqrt(max_px))`, `row_cap = min(max_h, max_px // tile_w)`;
  `_splits(total_px, parts)` po liczbie czesci (podzial rowny, offsety
  `i*base + min(i, extra)`); petla, kotwica NW, N->S, W->E — bez zmian.

### N3 — `kartograf/providers/cuzk/client.py`
- `export_image`: po `width_px/height_px = round(...)` bbox jest snapowany do
  kotwicy NW: `BBox(min_x, max_y - h*px, min_x + w*px, max_y, crs)` — PRZED
  rozgalezieniem tor pojedynczy / kafle, wiec obie sciezki i `merge(bounds=)`
  dziela siatke. Nazwa pliku i `request.bbox` w CLI nadal niosa bbox sprzed
  snapu (kontrakt jak w torze z warpem).

### Helper N2 — `kartograf/transport/mosaic.py`
- `has_valid_pixels(path, nodata) -> bool` na koncu modulu (`block_windows`,
  `isfinite`, `!= nodata`, wczesne wyjscie). Wiring (`PlCutoutResult.all_nodata`,
  `Warning:` CLI) robi B1. Odstepstwo od "TYLKO na koncu": `import numpy as np`
  poszedl na szczyt modulu (jedna linia; numpy jest zaleznoscia wymagana,
  import lokalny bylby niepotrzebna anomalia). B2 pracuje po tym commicie.

## Testy (failing-before / passing-after)

Dowod failing-before: `git worktree add /tmp/kb HEAD` (= `c5b3110`), skopiowane
TYLKO nowe pliki testow A2 + A3, uruchomione `pytest tests/test_transform_crs.py
tests/test_cuzk_dmr.py tests/test_cuzk_client.py tests/test_transport_mosaic.py
tests/test_gugik_laz.py -m "not live"` -> **60 failed, 137 passed**. Po zmianach
te same pliki + `test_cli.py` + `test_pl_cutout.py`: **515 passed**.
Ruff check + format czyste na wszystkich plikach pakietu. Mypy: zero bledow
w plikach A2 (suma 34 w 11 plikach pochodzi z cudzych niezacommitowanych zmian,
weryfikacja bazowa w fali C).

| blad | test | failing-before (HEAD) | po |
|---|---|---|---|
| K2 | `TestDatumStepPins::test_5514_pairs_pin_czech_operation` x6 (5514<->2180/3045/4258) | `'S-JTSK to ETRS89 (1)' in '... S-JTSK to ETRS89 (3) ...'` | pass |
| K2 | `test_5514_wgs84_pairs_pin_twin_operation` x2 | dzis `WGS 84 (5)` | pass |
| K2 | `test_pin_reports_rejected_datum_step` (mock z krokiem 4829) | `DID NOT RAISE TransformUnavailableError` | pass, `rejected` niesie "EPSG:1622" |
| K2 | `test_pin_ignores_pairs_without_pinned_crs` x3 (25833->2180, 2180->3045, 8357->5621) | pass (kontrola) | pass |
| K2 | `test_pinned_operation_moves_content_by_known_offset` (Karkonosze 15.74E 50.735N, `dist(pinned, EPSG:4829)`) | `0.0 == 2.73 ± 0.05` | pass (2,73 m) |
| K2 | `test_pin_accepts_single_inverse_operation` (`{"id": {"authority": "INVERSE(EPSG)", ...}}` bez `steps`, `epsg:5514` malymi literami) | n/d (helper nie istnial) | pass |
| K2 | `TestGdalOperation::test_operation_carries_datum_step` (ZMIANA: `"molobadekas"` -> `"helmert" and "x=570.8"`) | `'helmert' in 'proj=pipeline ... molobadekas ...'` | pass |
| K2 | `TestKnownPaths::test_pl_cutout_pairs_documented_with_measured_accuracy` (0.5 -> 1.0 dla 2180->5514) | `0.5 == 1.0` | pass |
| K2 | `test_cuzk_dmr.py::test_warp_forces_the_pinned_operation` x2 (sanity `helmert`) | `'helmert' in '... molobadekas ...'` | pass |
| K2 | `test_cuzk_dmr.py::test_tm33_tile_uses_czech_datum_operation` (`download("302_5550")`, `horizontal_transform("EPSG:3045")`) | opis z "(3)" | pass |
| K6 | `TestExportPixelGrid::test_pixel_budget_tiles_below_dimension_limits` (3000x3000 px, domyslne 15000/4100) | jedno zapytanie `size=3000,3000` | >1 zapytanie, kazde <= 4 Mpx, suma 9 Mpx, piksele bit w bit z kafla, `.part*.tif` posprzatane |
| K6 | `test_tile_grid_respects_budget_and_covers_request` x4 (5000x5000, 1800x12300, 50000x50, 8x8) | `TypeError: _tile_grid() takes 6 positional arguments` | pass (kafle rozlaczne, suma = zadanie, kotwica NW, `w*h <= max_px`) |
| K6 | `test_default_budget_is_below_measured_server_limit` (`0 < MAX_EXPORT_PIXELS <= 6_000_000`) | `AttributeError` | pass |
| N3 | `test_single_shot_snaps_bbox_to_pixel_grid_nw` (`BBox(0,0,1000.7,181.4)`, px 2) | URL `bbox=0,0,1000.7,181.4` | `bbox=0,-0.6,1000,181.4`, `size=500,91`, `res == (2,2)`, `top == 181.4` |
| N3 | `test_tiled_and_single_paths_share_the_grid` (budzet 4 Mpx vs 10 kpx) | `AttributeError` | identyczne `transform`, `shape (91, 500)`, tresc |
| N2 | `test_transport_mosaic.py::test_has_valid_pixels_distinguishes_nodata_and_nonfinite` x7, `..._finds_only_valid_pixel_in_last_block` | `ImportError` | pass |

Testy zmienione mechanicznie (nie pinowaly bledu, ale wymagaly kontraktu):
`_mock_transformer(..., codes=("EPSG:1622",))` w `test_transform_crs.py`,
`_fake_operation(..., codes=...)` w `test_cuzk_dmr.py` (mocki na parze
5514->2180 musza deklarowac krok datum); 4 testy kafelkowania w
`test_cuzk_client.py` (`test_tiling_above_limits_mosaics`,
`..._fractional_height_...`, `..._corrupted_tile_...`, `..._crs_mismatch_...`)
patchuja dodatkowo `MAX_EXPORT_PIXELS = 4_000_000`.

Kosmetyka opisu przypietej operacji w mockach: `tests/test_pl_cutout.py:1215-1218`
("(3)"/0.5 -> "(1)"/1.0) — w commicie A2; `tests/test_cli.py:2939-2940`,
`:3010`, `:3137` — te same zmiany, ale plik `test_cli.py` zawiera takze nowe
testy LAZ (A3), wiec jest zacommitowany w commicie A3 (`fix(laz): ...`).

Testy usuniete: brak (w A2 zadnego testu nie trzeba bylo usunac; zmienione
asercje wymienione wyzej). Usuniete nieprawdziwe komentarze: `dmr.py:53-56`,
`:86-89`, `:269-273`; `raster.py:4-7`; `crs.py` KNOWN_PATHS 5514<->2180.

## Ryzyka / do weryfikacji na zywo (fala C pkt 4, scenariusze L4)
- K2: Karkonosze S-STYK CZ vs GUGiK 1 m — oczekiwane <= ~0,4 m (z 4829 bylo
  2,3 m). Sidecar `transform.horizontal` = `"pinned: ... S-JTSK to ETRS89 (1)
  ... (1.0 m)"`. Pliki z "(3)" w cache uzytkownikow NIE sa przebudowywane
  (D12: `Info:` w CLI robi B1; CHANGELOG/README fala C).
- K6: 10 x 10 km 2 m (5000x5000 px) = 9 kafli 1667x1667 (2,78 Mpx) — ma
  przejsc bez HTTP 500; szwy bit w bit (NW kotwica, `merge` bez resamplingu).
  Limit dmr4g (5 m) nieweryfikowany — ten sam budzet, ryzyko tylko w strone
  mniejszych kafli.
- N3: wycinek z przykladu CLAUDE.md (`18.60,49.752,18.65,49.768`) — piksel
  dokladnie 2,000 m; krawedz E/S rozni sie od zadania o <= ½ px (jak dotad
  w torze z warpem).
- Po pinie `_country_bbox` (4326->5514) i lon/lat uzywaja EPSG:1623 zamiast
  EPSG:5239 (roznica 5-7 cm; bez znaczenia dla obwiedni i pionu).
- `_epsg_code` dla WKT bez autorytetu daje `None` = brak pinu (dzis takich
  wywolan nie ma).
- Komunikaty CLI `download_cmd.py:678-682`/`:1642-1645` ("tryb godlowy 1:1")
  — B1.

## Pliki (commit `fix(cuzk): ...`)
`kartograf/transform/crs.py`, `kartograf/providers/cuzk/client.py`,
`kartograf/providers/cuzk/dmr.py`, `kartograf/transport/mosaic.py`,
`kartograf/transform/raster.py`, `tests/test_transform_crs.py`,
`tests/test_cuzk_dmr.py`, `tests/test_cuzk_client.py`,
`tests/test_transport_mosaic.py`, `tests/test_pl_cutout.py`, ten raport.
