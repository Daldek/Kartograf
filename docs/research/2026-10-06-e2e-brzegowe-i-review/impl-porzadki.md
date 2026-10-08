# Implementacja: ostatnia fala porzadkowa (K6, K7b, K9, D6, D9-PL, LAZ, strip)

Galaz `refactor/cleanup` (worktree `Kartograf-cleanup`), baza develop
`a813ea4`. Zrodla: `ocena-parserow.md` (plan K6-K9), `impl-parsery.md`
(pozostawione), `impl-dedup-providers.md` (D6, D9 strona PL, sesja LAZ),
`impl-dedup-download.md` (LAZ sidecar przez `emit_sidecar`). Bez sieci.

## Bilans

| Stan | Testy offline | ruff | format | mypy |
|---|---|---|---|---|
| baza `a813ea4` | 2375 passed (16 live deselected) | czysto | czysto | 32 bledy |
| koniec | 2405 passed (16 live deselected) | czysto | czysto | 32 bledy, lista (bez numerow linii) identyczna z baza |

Linie (`git diff --shortstat a813ea4 HEAD`): `kartograf/` +122 / -325
(netto **-203**), `tests/` +318 / -119 (netto +199).

| Commit | Zadanie | kartograf/ | tests/ |
|---|---|---|---|
| `83c197b` | K6 `fix(download): jedna obwiednia bboxa w cutout/CLI/dmr` | +52 / -221 | +71 / -86 |
| `a2dc1c5` | K7b `fix(cli): parse_bbox_arg w torach download PL/CZ/LAZ` | +11 / -33 | +50 / -19 |
| `1e15068` | K9 `refactor(cli)!: fasada commands.py bez prywatnych helperow` | +5 / -11 | +13 / -13 |
| `1e0e5a6` | D6 `refactor(cli): jeden helper komunikatu TransformError` | +7 / -9 | +34 / 0 |
| `fb9162f` | D9 PL `refactor(download): CONTENT_POLICY i WARP_MARGIN_PX z transform.crs` | +5 / -10 | +21 / 0 |
| `038bf13` | LAZ `fix(laz): sesja HTTP na watek (SessionPerThread)` | +7 / -4 | +67 / -5 |
| `22c20d1` | LAZ `refactor(laz): sidecar kafla przez emit_sidecar` | +32 / -37 | +37 / 0 |
| `478843a` | strip `fix(cuzk): CuzkDmrProvider.download obcina godlo` | +3 / 0 | +29 / 0 |

Mutacje uruchamiane skryptem w prywatnym katalogu `/tmp/claude-2001/cleanup/`
(kopia pliku -> podmiana -> pytest -> przywrocenie; skrypt przerywa, gdy
wzorzec nie pasuje). Po kazdej mutacji `git diff` pliku = stan sprzed niej.

## 1. K6 — jedna obwiednia w cutout/CLI/dmr (`83c197b`)

**Zmiana.**
- `core/geometry._transform_bbox` (4 narozniki, transformer na wywolanie)
  usuniete razem z importem `Transformer`. Wolajacy: `cli/download_cmd.py`
  (`_bbox_to_wgs84`, `_country_bbox`, `_resolve_laz_bbox`) i
  `download/cutout._bbox_to_2180` -> `core.bbox.transform_bbox`.
- `is_czech_crs` zastepuje `cutout._CZ_CRS` i `download_cmd._CZ_CRS_WKIDS`
  (`_country_bbox`, `_geometry_envelope`, `_resolve_laz_bbox`, `_bbox_to_2180`).
- `cutout._sheet_frame_transformer`/`_sheet_frame_2180` usuniete;
  `estimate_pl_cutout_bytes` -> `SheetParser(leaf).get_bbox("EPSG:2180")`
  (cache w `core.bbox`, test "jeden `from_crs`" przepiety na
  `core.bbox._transformer.cache_clear()`).
- `providers/cuzk/dmr.bbox_to_crs`: cialo -> `transform_bbox(...,
  transformer=pinned)`, `_EDGE_SAMPLES` usuniete. **Odstepstwo od planu:**
  sama funkcja `bbox_to_crs` ZOSTAJE jako cienkie wejscie "operacja
  przypieta do obwiedni" — wybiera `_ENVELOPE_POLICY` z punktem kontrolnym
  w srodku bboxa, gdy wolajacy nie poda operacji. Bez niej szesc miejsc
  w CLI/cutout musialoby kopiowac budowe operacji (polityka + probe), czyli
  odtworzyc duplikacje, ktora krok usuwa. Kopia probkowania zniknela.
- Martwe galezie `system is None` (`detect_system` typowane `-> SheetSystem`,
  `next(...)` po literale z fallbackiem `pl1992`): `cmd_download`
  (`system_id/system_country`), `_cz_download_godlo` (`is_sm5`),
  `storage.FileStorage._resolve_subdir`, `dmr.download`. mypy bez zmian
  listy (galezie nie sluzyly juz typom).

**Pomiary ryzyk z planu.**
- Bbox WGS84 przez 19E (`BBox(18, 50, 20, 50.2, "EPSG:4326")`) w wycinku PL
  i LAZ: `min_y` 237447,4 -> **236968,4486** (+479 m pasa na S); nazwa
  wycinka `428355.061_236968.4486_571644.939_259677.447.tif`.
- Obwiednie CZ, 9 -> 21 probek: siedem bboxow (pogranicze 4326->5514,
  caly prostokat CZ 12,5-18,8E/48,6-51N, Krovak->2180, 3045->5514,
  4326->2180) — wynik **bit w bit identyczny** (max |d| = 0,0 m); nawet
  4 narozniki daja tu 0,000 m wobec 201 probek (CZ lezy daleko od
  poludnika osiowego Krovaka 24,83E). Zaden test CZ nie wymagal zmiany liczb.
- Arkusze 1:10000 w `estimate_pl_cutout_bytes`: test porownujacy z
  `SheetParser.get_bbox` przechodzi bez zmian.
- `test_cli.py` (bboxy `EPSG:4326`): jedyna zmiana — asercja "niepinowany
  transformer nie celuje w uklad czeski" przepieta z argumentu `[5]`
  `_transform_bbox` na `call.args[1]` (cel) wywolan `core.bbox._transformer`.
  Rozpoznawanie kraju (5514 -> 4326, niepinowane) bylo i jest dozwolone.

**Testy.** Nowe (czerwone na starym kodzie, sprawdzone `git stash` kodu):
`TestPreparePlCutout::test_wgs84_bbox_across_19e_keeps_southern_band`,
`TestResolveLazBbox::test_bbox_wgs84_across_19e_keeps_southern_band`.
Usuniete: `test_geometry.py::TestTransformBbox` (3; funkcja usunieta,
zachowanie pokrywa `test_core_bbox.py`). `test_core_bbox::test_pinned_transform_passes`
porownywal z `bbox_to_crs`, ktore teraz woła te sama funkcje (tautologia) —
przepisany na "obwiednia obejmuje obrazy 4 naroznikow". Testy patchujace
`geom._transform_bbox`/`kartograf.core.geometry.Transformer` (4) patchuja
teraz `core.bbox._transformer`.

**Mutacje.**
- `transform_bbox` (sciezka pyproj) `densify_pts=0`: pada m.in. nowy test
  wycinka 19E, nowy test LAZ 19E, `TestAutoSplitBBox::test_rozewie_clips_only_north_edge_and_informs`
  (`_country_bbox`), testy geometrii i `core.bbox` — wszyscy dawni
  wolajacy `_transform_bbox`.
- `is_czech_crs` zawsze `False`: padaja LAZ Krovak/UTM33N (2),
  `_geometry_envelope` (`test_geometry_in_czech_crs_leaves_krovak_by_pinned_operation_for_pl`),
  `_country_bbox` (`test_pl_part_of_cz_crs_bbox_leaves_krovak_pinned`),
  wycinek (`test_czech_crs_label_leaves_krovak_by_pinned_operation` x2)
  + 6 testow jednostkowych — wszyscy dawni konsumenci obu zbiorow.
- Sciezka duck `transform_bbox` (operacja przypieta) zredukowana do 4
  naroznikow: pada tylko test jednostkowy (84 punkty). Testy CZ jej nie
  bronia — zgodnie z pomiarem wyzej, dla danych CZ nie ma to wplywu na wynik.

## 2. K7b — `parse_bbox_arg` w download, martwa galaz CZ (`a2dc1c5`)

**Zmiana.** `_cmd_download_bbox` i `_resolve_laz_bbox` -> `parse_bbox_arg(args.bbox,
args.bbox_crs)` (ValidationError -> `Error: ...` w barierze `main`).
`_resolve_laz_bbox` nie rzuca `ValueError`; `except` w `_cmd_download_laz`
bez `ValueError` (w bloku nie ma juz zrodla `ValueError`; niespodziewany
i tak lapie bariera `main`, kod 1). `_cz_download_bbox(bbox: BBox)` bez galezi
`bbox is None`; `_cmd_download_cz`: `bbox is None` = tryb godlowy (CLI:
`cmd_download` -> `_run_cz(args)` dla godla, `_dispatch_area` zawsze podaje
bbox, takze dla jawnego `--country cz`). Trzecia "kopia" z planu byla
w `_cz_download_bbox` — usunieta razem z galezia.

**Testy.**
- Nowy `TestCmdDownloadBBox::test_download_rejects_bad_bbox_before_network`
  (5 wartosci x tory auto/pl/cz/laz = 20): kod 1, `Error: Invalid bbox
  format` na stderr, bez `ValueError`, bez `Expected` na stdout, zaden
  provider nie powstaje. Na starym kodzie: **20 failed**.
- Usuniety `TestCmdDownloadCz::test_invalid_bbox_string_returns_1` —
  wolal `_cmd_download_cz` z `args.bbox` jako tekstem, czyli wylacznie
  martwa galaz; ten sam przypadek (`--country cz`, `1,2,3`) pokrywa nowy test
  przez `main`.
- `test_bbox_string_is_normalized_to_image_sr` (plan: `:3408`) przepisany
  na `main([... "--country", "cz" ...])` — te same asercje nazwy pliku.
- `TestResolveLazBbox::test_bbox_wrong_value_count_raises`: `ValueError` ->
  `ValidationError("Invalid bbox format")`.

**Mutacja.** `parse_bbox_arg` bez `validate_bbox`: pada po 3 przypadki
(`10,10,5,5`, `nan`, `-inf`) w kazdym z torow auto/pl/cz/laz (12) + testy
landcover/soilgrids z K7a.

## 3. K8 (opcjonalny) — NIE ZROBIONY

`read_raster_nodata(path)` w `sources/sidecar.py` przenioslby jedyna
implementacje odczytu tagu GeoTIFF (`cli/download_cmd._read_tif_nodata`,
9 linii, 2 wywolania w torze CZ) do biblioteki, obok jedynej implementacji
ASC. Nie ma tu dwoch kopii jednej logiki (ASC i TIFF to rozne formaty,
`dmr.py:~463` ma inna semantyke — domyslna wartosc zapisu), bilans ~0 linii,
a nowa publiczna funkcja w `sidecar.py` to nowe API do utrzymania.
Zostawione; `docs/ARCHITECTURE.md:260` nadal poprawnie opisuje `_read_tif_nodata`.

## 4. K9 — fasada `cli/commands.py` (`1e15068`)

**Zmiana.** Fasada nie re-eksportuje `_create_provider_and_storage`
i `_resolve_laz_bbox` (`__all__` i import); zostaja `main`, `create_parser`,
`cmd_*`, `create_progress_callback`, formatery. 13 importow w `test_cli.py`
przepietych na `kartograf.cli.download_cmd`. Entry point
(`pyproject: kartograf.cli.commands:main`) i `kartograf/__init__.py` bez
zmian. CHANGELOG: BREAKING (prywatne nazwy, uzywaly ich tylko testy).

**Testy/mutacje.** Refaktoryzacja importow — suita zielona przed/po; brak
zachowania do mutowania.

## 5. D6 — jeden helper komunikatu `TransformError` (`1e0e5a6`)

**Zmiana.** Dwie reczne kopie f-stringa `Error: {e} Remedium: {remedy}`
(`_resolve_cz_geometry_bbox`, fabryka providera w `_cmd_download_cz`) ->
istniejacy `_print_transform_error` (trzecie miejsce = sam helper, juz
uzywany w `_run_cz`, `_dispatch_area`, wycinku PL). Tresc komunikatu bez
zmian (dla `ValidationError`/`ValueError` bez `remedy` — samo `Error: ...`).

**Testy.** Nowy `TestCmdDownloadCz::test_provider_factory_transform_error_reports_remedy`
(fabryka CZ rzuca `TransformUnavailableError` z remedium przy `--target-crs`;
pelna tresc komunikatu, kod 1). Przed nim format tej sciezki nie byl bronony
(`test_kron86_prints_remedy` sprawdza kod, nie format).

**Mutacje.**
- Helper `Remedium:` -> `Remedy:`: 4 failed — wszystkie trzy dawne kopie
  (`test_cz_bbox_transform_error_returns_1_with_remedy` — `_run_cz`;
  `test_geometry_cz_transform_unavailable_reports_remedy` — geometria CZ;
  `test_provider_factory_transform_error_reports_remedy` — fabryka) oraz
  `test_godlo_without_safe_horizontal_operation_exits_cleanly`.
- Miejsce fabryki `return 0` zamiast helpera: 2 failed (nowy test,
  `test_kron86_prints_remedy`); miejsce geometrii `pass`: 1 failed.
- Uwaga (poza zakresem D6): mutacja `return 0` w `_dispatch_area` przy
  `_country_bbox` (`TransformError` z czesci kraju, juz przez helper przed
  ta praca) przechodzi cala suite — ta galaz nie ma testu kodu wyjscia.

## 6. D9 strona PL (`fb9162f`)

**Zmiana.** `download/cutout.py` importuje `CONTENT_POLICY` i `WARP_MARGIN_PX`
z `kartograf.transform.crs`; lustrzane `WARP_MARGIN_PX = 4` i
`_HORIZONTAL_POLICY` usuniete (nazwa `cutout.WARP_MARGIN_PX` nadal istnieje
jako import). Import `TransformPolicy` zbedny.

**Testy.** Nowy `TestPreparePlCutout::test_source_has_warp_margin_of_four_pixels`
(1m: 4 m, 5m: 20 m wokol obwiedni celu sprowadzonej do 2180) — lustro
`test_native_request_has_warp_margin_of_four_pixels` toru CZ.

**Mutacje** (w `transform/crs.py`):
- `WARP_MARGIN_PX = 0` przed nowym testem: wycinek PL **0 failed**
  (stala nie byla broniona); po: 2 failed (`[1m-4.0]`, `[5m-20.0]`);
  `= 3`: te same 2.
- `CONTENT_POLICY` `min_accuracy_m=0.5`: 12 failed w `test_pl_cutout.py`
  (operacja 1,0 m odrzucona) — wycinek PL korzysta teraz ze wspolnej stalej
  (wczesniej mutacja przechodzila wycinek, bo mial wlasna kopie).

## 7. Sesja LAZ na watek (`038bf13`)

**Zmiana.** `GugikLazProvider`: `self._sessions = SessionPerThread(session)`
zamiast `session or make_gugik_session()`; `_get_wfs_xml` i `download`
wolaja `self._sessions.get()`. Sesja wstrzyknieta wygrywa zawsze. Sesja
watku powstaje przy pierwszym zapytaniu (fabryka rozwiazywana w
`transport.http`), wiec testy patchuja `kartograf.transport.http.make_gugik_session`
(`_LAZ_SESSION_PATCH` w `test_gugik_laz.py`, `_cli` w `test_laz_download.py`);
`test_fetch_years_descending` wola zapytanie wewnatrz `with patch(...)`.

**Testy.** Nowa klasa `test_gugik_laz.py::TestSessionPerThread`:
`test_threads_get_separate_sessions` (2 watki -> 2 sesje, po 1 zapytaniu),
`test_same_thread_reuses_session`, `test_injected_session_wins_in_every_thread`.
Na starym kodzie: 2 pierwsze **failed** (jedna sesja z konstruktora);
trzeci przechodzi (zachowanie zachowane).

**Mutacje.** `SessionPerThread.get` z jedna sesja na instancje (zamiast
`threading.local`): pada `test_threads_get_separate_sessions` (LAZ; NMT,
orto, BDOT10k i transport pokrywaja to samo od D2). Sesja wstrzyknieta
ignorowana (`SessionPerThread(None)`): 29 failed w testach LAZ.

## 8. Sidecar LAZ przez `emit_sidecar` (`22c20d1`)

**Zmiana.** `download/laz.write_laz_sidecar` buduje `request` (bbox,
`year`, `min_density` gdy podane) i `extra` (`godlo_kafla`, `rok`,
`gestosc`, `url`, `parent_request` gdy podany) i wola
`emit_sidecar(key if isinstance(key, str) else "pl.gugik.laz", target, ...,
horizontal_crs=horizontal_crs_for_uklad(tile.crs))`. Wlasny `try/except`
i `logger` modulu usuniete. Roznice: ostrzezenie loguje
`kartograf.sources.sidecar` (tekst ten sam); `emit_sidecar` przekazuje
`data_path` do `build_metadata` — dla `.laz` bez skutku (nodata tylko dla
`.asc`, uklad z godla tylko dla `request.godlo`, ktorego LAZ nie ma);
`provider.vertical_crs` i `horizontal_crs_for_uklad` sa liczone przed
`try` (provider LAZ zawsze ma `vertical_crs`; parser ukladu nie rzuca).

**Testy.** Nowe w `test_laz_download.py::TestRunLazDownload`:
`test_sidecar_failure_does_not_abort_download` (awaria `build_metadata` ->
kafel pobrany, brak sidecara, ostrzezenie w logu),
`test_provider_without_descriptor_key_still_gets_laz_sidecar`. Oba
przechodza takze na starym kodzie (refaktoryzacja bez zmiany zachowania);
istniejace testy tresci (`request.year/min_density`, `parent_request`,
`horizontal_crs` PL-2000:S6) bez zmian.

**Mutacje** (w `sources/sidecar.emit_sidecar`): `except Exception` ->
`except ZeroDivisionError`: pada `test_sidecar_failure_does_not_abort_download`
(przed nim LAZ tej polityki nie bronil); `request={}`: padaja
`test_tiles_land_in_storage_with_sidecar` i `test_year_downloads_that_year_only`.

## 9. `CuzkDmrProvider.download` — `strip()` (`478843a`)

**Zmiana.** `godlo = godlo.strip()` na wejsciu `download` (przed
`detect_system`); URL openzu, `sm5_sheet` i `ParserTM33` dostaja to samo
obciete godlo.

**Testy.** `test_cuzk_dmr.py::TestDownloadDispatch::test_sm5_godlo_with_whitespace_builds_clean_url`
(`" CTES96"`, `"CTES96 "`, `"\tCTES96\n"`: `sm5_sheet("CTES96")` i URL
`.../CTES96.zip`) — na starym kodzie **3 failed**;
`test_tm33_godlo_with_whitespace_is_parsed` (regresja, przechodzil i wczesniej).

**Mutacja.** Usuniecie `strip()`: 3 failed.

## Czego nie zrobilem i dlaczego

- **K8** — patrz sekcja 3 (brak duplikacji, nowe API, bilans ~0).
- **`bbox_to_crs` nie usuniete** (plan K6: "USUNAC") — zostaje jako
  cienkie wejscie wyboru operacji obwiedniowej; usuniecie przenioslo by
  budowe operacji (polityka + probe) do szesciu wolajacych.
- **`wkid()` w `_country_bbox`/`_cz_download_bbox`/`dmr.download_bbox`**
  (porownanie dwoch ukladow, nie test "czy czeski") — poza zakresem
  `is_czech_crs`, bez zmian.
- **Opcjonalne z `impl-parsery.md`:** `corine.py`/`soilgrids.py`
  `_transform_bbox_to_*` — juz zastapione w deduplikacji (`envelope_from_2180`,
  D19); nic do zrobienia.
- **Walidacja CZ przez `validate_bbox`** (`impl-parsery.md`, "swiadomie
  niezrobione") — inna semantyka bboxa zdegenerowanego; bez zmian.
- **Test kodu wyjscia `_dispatch_area` przy `TransformError` z
  `_country_bbox`** — luka znaleziona mutacja (sekcja 5), poza zakresem
  D6 (miejsce juz uzywalo helpera); do dopisania przy najblizszej pracy
  w CLI.
