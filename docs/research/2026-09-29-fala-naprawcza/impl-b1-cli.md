# Pakiet B1 — CLI integrator: S2 (D2/D10/D11), S3, N2, N4, N6, N7, N8, K2/D12, handoffy B2/B3

Data: 2026-09-30. Galaz `develop`, baza: `683f9c3` (B3). Testy offline, zero sieci.
Pakiet zaczal agent B1 (transkrypt `history://B1Cli`, przerwany na `_download_pl_cutout`),
dokonczyl B1CliResume w tym samym drzewie — jeden commit.

## Co zmienione

### S2 — tryb listy arkuszy z tolerancja R5 (D2, D10, D11)
- `download/manager.py`: `DownloadResult.hard_failures` (property: `failed` minus
  `no_coverage`); `DownloadProgress.status` += `"no_coverage"` (obie sciezki
  hierarchii/listy raportuja go zamiast `"failed"` dla `NoCoverageError`; nadal w
  `failed` i `no_coverage`).
- `cli/download_cmd.py`:
  - `_download_godlo_list(manager, godla, skip_existing, on_progress) -> (paths, DownloadResult)`
    = JEDNO `manager.download_sheets(...)` (rozwiniecie godel grubszych niz 1:10000 robi
    `expand_sheets`, rownoleglosc = `max_workers` managera, kazdy arkusz probowany
    niezaleznie od `--workers`). Usuniete: `_expands_to_hierarchy`, `_report_failed_sheets`,
    petla sekwencyjna/pula watkow w CLI.
  - `_finish_pl_sheets(result, paths, *, output_dir, quiet) -> int` — wspolny finisz
    `--bbox`/`--geometry` (bez `--target-crs`) i hierarchii godla (`--scale` albo godlo
    grubsze niz 1:10000, D10). Macierz: wszystko ok/pominiete -> 0, cisza;
    >= 1 plik + reszta bez danych -> `Warning: GUGiK nie ma danych dla K z M arkuszy
    (do 10 godel) — pominiete (morze, obszar za granica); pobrano N`, rc 0;
    >= 1 porazka pobrania -> `Error: K z M arkuszy nie pobrano (blad pobrania, nie brak
    danych): {PELNA lista} — ponow pobranie`, rc 1 (plus Warning jw.);
    0 plikow i wszystkie bez danych -> `Error: GUGiK nie ma danych dla zadnego z M arkuszy
    obszaru`, rc 1. Podsumowanie stdout: `Downloaded {succeeded} files to {dir}
    ({skipped} already existed)`. Pojedynczy arkusz 1:10000/PL-2000 bez danych = rc 1
    (`DownloadError` z managera, bez zmian).
  - `_download_pl_sheet_list(args, godla, parent_request, *, what, target_scale)` —
    wspolny tor bbox/geometry (manager + `MetadataCache` na czas zadania + finisz);
    `_download_pl_bbox`/`_download_pl_geometry` to teraz tylko wybor arkuszy + dispatch.
  - `_dispatch_area`: `Warning: czesc {kraje} zadania zakonczyla sie bledem (patrz Error
    wyzej) — pobrano {kraje}; kod 0 (...)` — bez zgadywania przyczyny (po D2 kod 1 galezi
    PL = blad pobrania albo zero danych). Pod `auto` z CZ ok i PL czesciowo bez danych
    Warning NIE pada (L5 B2).
  - pasek postepu: `∅` dla `no_coverage` (D11), linia konczona jak `completed`/`failed`.
- `_last_result(manager)` — narrowing `Optional` po hierarchii/liscie (kontrakt managera).

### S3 — jawne przyciecie pod `--country auto`
- `_country_bbox -> CountryPart(bbox, clipped: tuple["W"|"S"|"E"|"N", ...])`; PL po
  przycieciu: tylko krawedzie z `clipped` biora wartosc z transformacji przycietego
  prostokata, pozostale = ORYGINAL 1:1 (Rozewie: `455000, 773000, 459000, <784000`, dotad
  454889.74/772961.81/459082.21). Czesc CZ bez zmian (inny uklad, obwiednia z probkowaniem).
- `_area_outside_extents(wgs, extents) -> (envelope | None, share)` — czysta funkcja: krawedzie
  prostokatow tna bbox WGS84 na komorki, komorka bez pokrycia srodka = utracona; udzial
  wazony `cos(lat)`. Wykrywa utrate w narozniku (13-15°E x 53-55°N), slepa dla samego testu
  krawedzi.
- `_print_clipping_info` (stderr, `-q` nie tlumi), wolane w `_dispatch_area` PRZED praca,
  tylko pod `auto`: (1) per kraj z `clipped`: `Info: --country auto: czesc PL przycieta do
  obwiedni kraju (N: 54,90°N); plik i request.bbox niosa zasieg przyciety, oryginal w
  extra.parent_request.bbox`; (2) tylko przy realnej utracie: `Info: --country auto: obszar
  18,30°E-18,36°E x 54,90°N-54,92°N (~18 % powierzchni zadania) lezy poza zasiegiem PL/CZ
  i zostal pominiety; caly bbox pobiera jawne --country pl (...)`. Bogatynia: jeden Info
  (CZ, 51,06°N), zero "poza zasiegiem". Bez przyciecia — cisza (regresja zachowana).
  Nazwa pliku/`request.bbox` = zasieg przyciety (status quo), bez pola w sidecarze.

### N2 — wynik w 100 % nodata
- `download/cutout.py::run_pl_cutout`: po `build_pl_cutout` -> `all_nodata = not
  has_valid_pixels(target, PL_NODATA)` (helper A2 z `transport/mosaic.py`),
  `logger.warning`, `PlCutoutResult.all_nodata: bool = False` (addytywnie; przy
  `skipped=True` zawsze False — plik nie jest czytany). Regula "zero arkuszy =
  ValidationError" bez zmian.
- CLI PL (`_report_pl_cutout`): `Warning: wycinek w calosci nodata — pobrane arkusze nie
  wnosza zadnego piksela w obszarze zadania (brak danych GUGiK / obszar poza pokryciem)`, rc 0.
- CLI CZ (`_warn_cz_all_nodata`, w `_cz_download_godlo` i `_cz_download_bbox` po pobraniu):
  `Warning: {plik} jest w calosci nodata — obszar poza pokryciem DMR CUZK (poza granica
  CZ?)`, rc 0; best-effort (blad odczytu = cisza, jak `_read_tif_nodata`; brak tagu ->
  `CUZK_NODATA`). Sidecar CZ godla dostaje `nodata` z tego samego odczytu (jeden `open`).

### N4 — arkusze pominiete i pominiety wycinek
- `download/manager.py::_note_reuse(data_path)` na trzech sciezkach `skip_existing`
  (`download_sheet`, `_download_single_sheet_task`, `_download_hierarchy_sequential`):
  jesli manager ma `sidecar_extra.parent_request` i sidecar arkusza ISTNIEJE, dopisuje
  zadanie do `extra.parent_requests` (lista, addytywnie, bez duplikatow, zadanie rowne
  `parent_request` nie jest dopisywane; zapis tmp + `os.replace`; `downloaded_at` i reszta
  bez zmian). Bez sidecara (cache sprzed 0.7.0) nic nie powstaje. Best-effort (warning w logu).
- CLI `_download_pl_cutout` przy pominietym wycinku: `skipped_pl_cutout(cutout)` (B2) ->
  `_report_pl_cutout(result, from_sidecar=True)`: ten sam `Warning:` o `missing_sheets`
  z dopiskiem `(z sidecara istniejacego wycinka)` (dotad "bez ponownego Warning").

### N6 — `MetadataCache` w torach PL (P4)
- `_pl_metadata_cache(args)` (contextmanager, wzor CZ): `--force` -> `None` (rekordy
  skorowidza ani czytane, ani zapisywane), inaczej `MetadataCache()` w cwd + `close()` w
  `finally`. Uzyte w `cmd_download` (galaz godla), `_download_pl_sheet_list`,
  `_download_pl_cutout`. `_create_provider_and_storage(..., cache=None)` przekazuje do
  `create_nmt_provider(cache=)`, `GugikNmptProvider(cache=)`, `GugikOrtoProvider(cache=)`.

### K2 komunikaty + D12
- `cmd_download` (godlo + `--target-crs`, PL i CZ) oraz `_cmd_download_cz`: `--target-crs
  dziala tylko z --bbox/--geometry; godlo wyznacza zasieg i uklad produktu (arkusz PL 1:1
  w ukladzie godla, arkusz SM5 1:1 w EPSG:5514, kafel TM33 na siatce EPSG:3045)`.
- `_print_legacy_krovak_info(target)` przy `skip_existing` w `_cz_download_godlo`,
  `_cz_download_bbox` i `_download_pl_cutout`: sidecar z `transform.horizontal`
  zawierajacym `S-JTSK to ETRS89 (3)` -> `Info: {plik} pochodzi sprzed naprawy operacji
  S-JTSK (tresc przesunieta 1-5 m) — pobierz ponownie z --force`; brak/nieczytelny
  sidecar, `(1)`/`(2)`, `horizontal: null` -> cisza. Bez automatycznej przebudowy.

### N7, N8, orto (handoffy A/B3)
- N7: `Error: No LAZ tiles found for the given area (sprawdz obszar, --year i
  --vertical-crs; wszystkie roczniki WFS odpowiedzialy)` — prawdziwe po A (discovery
  wszystko-albo-nic, `DownloadError` z nazwa rocznika). CLI nie drukuje ostrzezen ponowien
  (sa w logu providera), wiec nic do skracania.
- N8: `_write_laz_sidecar`: `horizontal_crs=horizontal_crs_for_uklad(tile.crs)`
  (`PL-2000:S7` -> `EPSG:2178`, `PL-2000:S6` -> `EPSG:2177`, nieznany -> uklad kanalu).
- orto: `_product_label(product, resolution)` -> `Downloading N-... (product: orto)...`,
  `Found N sheets ... (product: orto)`; NMT/NMPT bez zmian (`resolution: 1m`).

### Handoffy B2
- `off_grid_sheets` niepuste -> `Info: N arkuszy o innej fazie siatki przeprobkowanych
  osobno (W1; lista w sidecarze: extra.off_grid_sheets)` (takze przy pominietym wycinku,
  z sidecara).
- `GridMismatchError` (podklasa `ValidationError`) lapie istniejacy
  `except Exception` wokol `run_pl_cutout` -> `Error: ...` z podpowiedzia `--target-crs`,
  rc 1 (test `test_cli_target_2180_off_grid_returns_1_with_hint` z B2 — bez zmian).

## Testy

`tests/test_cli.py`:
- Migracja mockow trybu obszarowego na kontrakt `download_sheets` + `last_result`
  (helper `_sheet_list_manager(*paths, failed=, no_coverage=, skipped=)`, 29 miejsc);
  `TestAreaModeHierarchyExitCode` (petla `download_sheet`) USUNIETA, zastapiona
  `TestSheetListExitCode` na prawdziwym `DownloadManager` + `FileStorage` w `tmp_path`
  i atrapie `_SheetProvider` (wynik per przyrostek godla).
- Autouse `_cwd_outside_repo` na poziomie modulu (tory PL tez otwieraja
  `MetadataCache` w cwd); cztery per-klasowe `_isolate_cache` usuniete (tak samo w
  `test_pl_cutout.py`).
- `TestCmdDownload`: hierarchia godla pod nowy finisz (tresc `Error:`), NOWE:
  `test_hierarchy_no_coverage_with_files_warns_and_returns_0`,
  `test_hierarchy_all_no_coverage_returns_exit_1`.
- `TestAutoSplitBBox`: komunikat `Warning: czesc ... zakonczyla sie bledem`; NOWE S3:
  Rozewie, Osinow, Bogatynia, pas wewnatrz obu prostokatow (cisza), naroznik 13-15°E,
  test jednostkowy `_area_outside_extents`; `TestAutoSplitGeometry::test_geometry_auto_clipping_prints_info`.
- `TestCmdDownloadProduct`: `test_orto_messages_do_not_claim_a_resolution`,
  `test_force_passes_no_cache_to_provider_factory`,
  `test_without_force_opens_cache_in_cwd_and_closes_it[godlo|bbox-list]`.
- `TestCmdDownloadCz`: N2 (`test_bbox_all_nodata_warns_but_returns_0`,
  `test_tm33_godlo_all_nodata_warns_but_returns_0`, kontrola z danymi), D12
  (`test_skipped_tm33_tile_reports_legacy_krovak_sidecar[(3)|(1)|None]`,
  `test_skipped_bbox_cutout_reports_legacy_krovak_sidecar`, bez sidecara = cisza), K2
  (`test_target_crs_with_godlo_message_names_product_frames`).
- `TestCmdDownloadLaz`: N7 (asercja podpowiedzi w `test_laz_no_tiles_found_errors`), N8
  (`test_laz_sidecar_horizontal_crs_comes_from_tile`).
- `TestProgressNoCoverage` (D11 `∅`).

`tests/test_download_manager.py`: `test_hard_failures_excludes_no_coverage_and_progress_status[1|4]`,
`TestReuseNotedInSidecar` (4 testy N4: dopisanie/duplikaty/rowne parent_request, sciezka
`download_sheet`, brak sidecara, manager bez `parent_request`).

`tests/test_pl_cutout.py`: `test_without_target_crs_behaviour_unchanged` (nowy zwrot
`_download_godlo_list`), `_run(..., bbox=)`, `_write_sheet_asc(fill=)`; NOWE:
`test_all_nodata_cutout_warns_and_returns_0` + kontrola,
`test_skipped_cutout_repeats_missing_sheets_warning_from_sidecar`,
`test_skipped_cutout_to_krovak_reports_legacy_sidecar` (sprawdza tez, ze nowy wycinek NIE
pinuje kroku "(3)"), `TestMissingSheets::test_cutout_entirely_nodata_warns_and_flags_result`,
`TestOffGridSheets::test_cli_target_5514_off_grid_prints_info`.

## Dowody

- Failing-before: `git worktree add --detach /tmp/kb 683f9c3` + skopiowane 3 pliki testow,
  selekcja `-k` nowych testow: **38 failed, 4 passed** (4 = kontrole: sidecar `(1)`/`None`
  bez Info, brak sidecara = nic, manager bez parent_request). Charakterystyczne bledy HEAD:
  S2 `--workers 1` -> `Error: 1 of 4 sheets failed: N-34-130-D-d-2-3` (1 proba, Warning
  brak), all-no-coverage -> `Error: 2 of 2 sheets failed to download`; S3 Rozewie
  `454889.74 != 455000`; N6 `cache` brak w kwargs; D12/N2 brak komunikatu; N8 `EPSG:2180`.
- Passing-after: `tests/test_cli.py tests/test_download_manager.py tests/test_pl_cutout.py
  tests/test_gugik_laz.py -m "not live"` = **488 passed**. Ruff check/format czyste na 6
  plikach. Mypy trzech modulow: 22 bledy = baseline HEAD (wszystkie w innych plikach).
- Smoke CLI offline (`kartograf download ...` z `/tmp`): godlo CZ + `--target-crs` ->
  nowy komunikat K2, rc 1; godlo PL + `--target-crs` -> komunikat z trzema ramami, rc 1;
  bbox 10-11°E x 56-57°N -> `Error: obszar nie przecina zasiegu ...`, rc 1, bez sieci.
  Skrypt jednorazowy `_country_bbox`/`_print_clipping_info` dla Rozewia/Osinowa/Bogatyni/
  pasa/naroznika — wartosci i komunikaty jak w sekcji S3.

## Uwagi dla Main

- Docs (CLAUDE.md "Ograniczenia" + pkt (3)/(4) `--country auto`, S2 "Tryb listy arkuszy
  nie ma tolerancji R5", N2 "bez komunikatu", N4, N6; README; CHANGELOG; ARCHITECTURE 4.3)
  NIE byly w moim zakresie plikow — do aktualizacji wg powyzszego.
- `test_gugik_laz.py` bez zmian, zielony (46).
- `MetadataCache.__del__` przy zamykaniu interpretera loguje `ImportError: sys.meta_path is
  None` gdy instancja nie zostala zamknieta — tory PL zamykaja cache w `finally`, wiec po
  zmianie ten szum w testach zniknal.
