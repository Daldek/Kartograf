# Implementacja uproszczenia parserow (K1-K5, K7a)

Data: 2026-10-07. Galaz `refactor/parsers` (worktree
`Kartograf-parsers`), baza `develop` @ `a9d502f`. Plan:
`ocena-parserow.md`, sekcja "Plan dla implementera". Bez sieci.

## Bilans

| | Przed | Po |
|---|---|---|
| Testy offline (`-m "not live"`) | 2216 passed | **2293 passed** (+77) |
| `ruff check` / `ruff format --check` | czysto | czysto |
| `mypy kartograf/` | 32 bledy w 9 plikach | 32 bledy w 9 plikach — **lista bez numerow linii identyczna** (diff pusty; zmienia sie tylko "checked 54 -> 55 source files") |
| `kartograf/` (linie) | — | +310 / -402 (**-92 netto**, mimo nowego modulu `core/bbox.py` 159 linii) |
| `tests/` (linie) | — | +466 / -106 |

Wydajnosc (`SheetParser("N-34-130-D-d-2-4").get_bbox("EPSG:2180")` x200,
ten sam skrypt, `PYTHONPATH` na worktree vs `develop`):

| Pomiar | develop | refactor/parsers |
|---|---|---|
| PL-1992 `get_bbox("EPSG:2180")` x200 | 1371 ms | **8 ms** |
| PL-2000 `get_bbox("EPSG:4326")` x200 | 518 ms | 470 ms (koszt dominuje `Parser2000.__init__`, nie transformacja) |
| `find_sheets_for_bbox` 50 km w 2180 x20 | 138 ms | 85 ms |

Uwaga metodyczna: skrypt uruchamiany z katalogu scratchpad importuje
`kartograf` z instalacji edytowalnej (= repo glowne), nie z worktree —
pierwszy pomiar "po" bez `PYTHONPATH` pokazywal stary kod. Liczby wyzej
sa z jawnym `PYTHONPATH` (sprawdzone `kartograf.__file__`).

## Kroki

### K1 — `core/bbox.py` (commit `42c3214`, `refactor(core)`)

- Nowy modul-lisc: `BBox` (przeniesiona z `sheet_parser`, ksztalt bez
  zmian), `validate_bbox(bbox, *, crs=None)` (NaN/inf, `min > max`, uklad;
  punkt dozwolony), `transform_bbox(bbox, target_crs, *, transformer=None)`
  (`None` -> `lru_cache`'owany pyproj + `transform_bounds(densify_pts=21)`;
  obiekt z `.transform` -> 84 probki, obwiednia min/max; ten sam uklad po
  normalizacji etykiety albo rownosci `CRS` -> te same wspolrzedne
  z etykieta docelowa), `is_czech_crs(label)` (wkid 5514/3045, autorytet
  `EPSG`/`ESRI`/brak, `strip().upper()`). Bez importu `kartograf.transform`.
- `sheet_parser` importuje `BBox` z `core.bbox` — `kartograf.BBox`,
  `core.sheet_parser.BBox`, `core.geometry.BBox` to ta sama klasa (test `is`).
- Testy: `tests/test_core_bbox.py` (39): import paths, tozsamosc
  (`"epsg:2180"`, WKT), 4326->2180 `min_y` = 236968,4 (nie 237447,4),
  2180->4326 `max_y` = 53,3551052, jeden `from_crs` na 200 wywolan, duck
  84 punkty, `PinnedTransform` vs `dmr.bbox_to_crs` (<= 5 cm), walidacja,
  `is_czech_crs`.
- Mutacje (kazda oblewa): `densify_pts=0` -> 2 testy (w tym blad PROJ dla
  wyjscia geograficznego); brak `lru_cache` -> test cache; brak `min > max`
  -> 3; brak `isfinite` -> 12; `_DENSIFY = 2` -> 3.
- Docs: drzewa modulow w `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/SCOPE.md`.
- Bilans: kod +160/-11, testy +146.

### K2 — `SheetParser.get_bbox` i selekcja PL-1992 (commit `bd0dc6c`, `refactor(core)`)

- `get_bbox("EPSG:2180")` -> `transform_bbox`; kopia
  `_transform_bbox_to_wgs84` (6 punktow, poprawka 2026-09-28) i
  `_PL1992_CENTRAL_X` usuniete — `find_sheets_for_bbox` woła
  `transform_bbox(bbox, "EPSG:4326")`. Import `Transformer` znika z modulu.
- `find_sheets_for_bbox` woła `validate_bbox(bbox)` na wejsciu (przed
  dyspozycja do PL-2000). Listy dozwolonych CRS bez zmian.
- TDD: 5 z 8 nowych testow (`TestSheetParserBBoxViaCoreBBox`) oblewalo na
  starym kodzie (N-34 -468 m, cache, odwrocony, NaN x2); arkusze 1:10000
  (`N-34-130-D-d-2-4`, `M-34-76-A-a-1`) bez zmian co do 1e-6 — zielone przed
  i po. Zadna istniejaca asercja nie wymagala zmiany.
- Mutacje: bez `validate_bbox` -> 3 testy; `get_bbox` przywrocony do
  starego kodu (nowy transformer + 4 narozniki) -> 2 testy.
- Bilans: kod +14/-83, testy +66.

### K3 — `parser_2000`: naprawa gubienia wiersza (commit `2cd6bcb`, `fix(parser)`)

- `Parser2000._transform_bbox`, `_transform_bbox_to_wgs84`,
  `_transform_bbox_to_zone_crs` (trzy kopie 4-naroznikowe) usuniete;
  `get_bbox` i `find_sheets_2000_for_bbox` wolaja `transform_bbox`;
  `validate_bbox` na wejsciu `find_sheets_2000_for_bbox`. Struktura
  (bbox -> WGS84 -> strefa) bez zmian; gesta obwiednia zawiera narozniki,
  wiec wynik jest nadzbiorem dawnego.
- Regresja: `find_sheets_for_bbox(BBox(17.6, 50.535, 18.4, 50.555,
  "EPSG:4326"), system="2000")` — przed: 8 arkuszy (`6.136.17..24`), po: 16
  (wraca wiersz `6.135.17..24`). Testy `TestFindSheets2000DenseEnvelope`
  (4) — wszystkie czerwone przed poprawka.
- Mutacje: `_transform_bbox_to_zone_crs` z 4 naroznikow wstawiony z powrotem
  w miejsce `transform_bbox(bbox_wgs84, zone_crs)` -> 2 testy (8 zamiast 16);
  bez `validate_bbox` -> 1 test.
- Bilans: kod +15/-131, testy +41.

### K4 — czytniki SHP/GPKG (commit `a567af1`, `refactor(core)`)

- `_read_shp_bboxes`/`_read_gpkg_bboxes`: `transform_bbox(BBox(...,
  source_crs.to_wkt()), target_crs)` — klucz cache to WKT (string), jeden
  transformer na warstwe. `_transform_bbox` zostaje nietkniety (wolajacy
  w `cli/download_cmd.py` i `download/cutout.py`) z dopiskiem w docstringu
  "do usuniecia w K6".
- Testy `TestReadersUseCoreBBox` (4): `from_crs` raz dla 3 obiektow (SHP
  i GPKG), obiekt 50 km przez 19E -> `max_y` 53,3551052, ten sam uklad bez
  zmian wspolrzednych. Trzy z czterech czerwone na starym kodzie (stary kod
  = mutacja: 3 transformery, -65 m).
- Bilans: kod +14/-13, testy +63.

### Mutacja ujednoliconego helpera (wszyscy dawni wolajacy)

`transform_bbox` z `transform_bounds` zamienionym na 4 narozniki (ten sam
transformer): **7 testow oblewa** w czterech plikach — `test_core_bbox` (2),
`test_sheet_parser` (`test_top_edge_across_central_meridian_keeps_sheets`
— dawny test poprawki 6-punktowej, oraz N-34), `test_parser_2000` (2,
regresja wiersza), `test_geometry` (obiekt przez 19E). `_transformer` bez
cache (`__wrapped__`): **5 testow** w tych samych czterech plikach
(sheet_parser, parser_2000, geometry x2, core_bbox).

### K5 — rejestr, `Sm5Sheet`, wzorce CZ, `strip()` (commit `c129d46`, `refactor(core)!`)

- `core/parser_registry.py`: literal `SYSTEMS` (pl2000, cz_tm33, cz_sm5,
  pl1992) zamiast `register_system`/`_REGISTRY`; `SheetSystem` bez
  `parser_factory` i bez fabryk `_make_parser_*`; `detect_system` ->
  `SheetSystem` (nigdy `None`) i `strip()`; `path_parts` dzieli godlo bez
  bialych znakow. Publiczne `CZ_TM33_PATTERN` (z grupami) i
  `CZ_SM5_PATTERN` — `parser_tm33` i `providers/cuzk/sheets` je importuja
  (koniec leniwego importu `core -> providers`).
- `sheet_parser._is_pl2000_format` bez galezi `None`.
- `providers/cuzk/sheets.py`: `Sm5Sheet` usuniety; `SheetIndex.sm5_sheet`
  obcina biale znaki (walidacja, `where`, klucz cache).
  `providers/cuzk/__init__.py` bez eksportu `Sm5Sheet`.
- **Dodatkowo (poza planem, wymuszone przez `strip()` w rejestrze):**
  `cli/_parser.py` — pozycyjne `godlo` w `download` i `parse` ma
  `type=str.strip`. Bez tego `kartograf download " 302_5550"` po zmianie
  rejestru trafialby do toru CZ z nieobcietym godlem, a
  `_cz_download_godlo` zbudowalby plik `" 302_5550.tif"` i sidecar z
  odstepem (gorzej niz dzisiejszy blad PL). `cli/download_cmd.py` nietkniety.
- Testy: usuniete `TestSm5SheetParserObject` (8), test duplikatu
  `register_system`, 4 testy `parser_factory`; dodane: `TestWhitespace`
  (10, rejestr), `test_systems_order_fallback_last`,
  `test_detect_never_returns_none`, `test_cz_patterns_are_shared_with_parsers`,
  2 testy `sm5_sheet(" CTES96 ")` (zapytanie i klucz cache po obcieciu),
  `TestCreateParserGodloStrip` (5, CLI).
- Mutacje: `detect_system` bez `strip` -> 5; `path_parts` na surowym
  godle -> 4; `sm5_sheet` bez `strip` -> 2; `download` bez `type=str.strip`
  -> 3.
- Docs: `ARCHITECTURE.md` (uwaga o leniwym imporcie zastapiona opisem
  kierunku importow; instrukcja "nowy kraj" bez `parser_factory`/`Sm5Sheet`;
  drzewo modulow), `SCOPE.md`, `CLAUDE.md`. Historia w `PROGRESS.md` bez zmian.
- Bilans: kod +54/-138, testy +76/-106.

### K7a — `parse_bbox_arg` (commit `a87b1a6`, `fix(cli)`)

- `cli/_parser.py::parse_bbox_arg(text, crs) -> BBox`: 4 wartosci, liczby,
  `validate_bbox`; jeden komunikat `Invalid bbox format: <powod>.
  Expected: min_x,min_y,max_x,max_y (e.g., ...)` jako `ValidationError`
  (`main` drukuje `Error:` na stderr, kod 1).
- `cli/landcover_cmd.py`, `cli/soilgrids_cmd.py`: kopie z
  `try/except/print/return 1` zastapione jedna linia; `Expected` nie idzie
  juz na stdout.
- TDD: 12 z 13 nowych/zmienionych testow CLI czerwonych na starym kodzie
  (odwrocony/NaN/inf przechodzily do managera; `Expected` na stdout);
  plus `TestParseBboxArg` (10) dla samego helpera.
- Mutacje: helper bez `validate_bbox` -> 11 testow w obu wolajacych
  (landcover 4, soilgrids 3) i helperze (4); `len(parts) < 4` zamiast `!= 4`
  -> 2.
- Bilans: kod +54/-27, testy +74.

### CHANGELOG

`docs/CHANGELOG.md`, `[0.7.0]` -> `### Parsery 2026-10-07` (BREAKING,
Fixed, Added).

## Kroki pozostawione na pozniej (dokladnie, co zostalo)

**K6** [konflikt: `download/cutout.py`, `cli/download_cmd.py`,
`download/storage.py`, `providers/cuzk/dmr.py`] — bez zmian wzgledem
planu, plus ponizsze resztki z K1-K5:

- `core/geometry.py::_transform_bbox` (4 narozniki) — nadal wolany z
  `cli/download_cmd.py` (`_bbox_to_wgs84`, `_country_bbox`,
  `_resolve_laz_bbox`) i `download/cutout.py::_bbox_to_2180`; testy
  `tests/test_geometry.py::TestTransformBbox`, `tests/test_pl_cutout.py`
  (3 importy), `tests/test_cli.py` (`patch.object(geom, "_transform_bbox")`
  x3, `patch("kartograf.core.geometry.Transformer")`). Usunac razem
  z wolajacymi; `geometry.Transformer` znika z modulu dopiero wtedy.
- `is_czech_crs` istnieje, ale nie ma jeszcze konsumentow: zastapic nim
  `download/cutout.py::_CZ_CRS` i `cli/download_cmd.py::_CZ_CRS_WKIDS`.
- `download/cutout.py::_sheet_frame_transformer/_sheet_frame_2180` —
  zbedne po K2 (`get_bbox` ma cache, 8 ms/200); `estimate_pl_cutout_bytes`
  moze wrocic do `SheetParser(leaf).get_bbox("EPSG:2180")`;
  `test_pl_cutout.py:1073` `cache_clear` -> `kartograf.core.bbox._transformer`.
- `providers/cuzk/dmr.py`: `bbox_to_crs`/`_EDGE_SAMPLES` -> `transform_bbox(...,
  transformer=pinned)`; galaz `system is None` (`:223`) martwa.
  **Nowa resztka z K5:** `CuzkDmrProvider.download(" CTES96")` z biblioteki
  (CLI obcina juz godlo) przechodzi teraz detekcje jako `cz_sm5`
  i `sm5_sheet` (obcina), ale URL openzu budowany jest z nieobcietego
  `godlo` (`_download_sm5`, `self._files_endpoint.format(sheet=godlo)`) —
  dodac `godlo = godlo.strip()` na poczatku `download`. Dotad taki godlo
  konczyl sie `ValidationError` przed siecia; dzis — bledem pobrania.
  Brak konsumentow bibliotecznych CZ (Hydrograf/Hydrolog), waga niska.
- `cli/download_cmd.py:900-901` i `:1917` (`system is not None`),
  `download/storage.py:206-212` — martwe galezie `None` (mypy nie protestuje).
- Opcjonalnie (providers zablokowane): `providers/corine.py`
  `_transform_bbox_to_epsg3857/_wgs84`, `providers/soilgrids.py`
  `_transform_bbox_to_wgs84` -> `transform_bbox(...)[:4]`.

**K7b** [konflikt: `cli/download_cmd.py`] — bez zmian wzgledem planu: trzy
kopie parsowania `--bbox` (`_cmd_download_bbox`, `_resolve_laz_bbox` —
przestaje rzucac `ValueError`, przejrzec `except (..., ValueError)`
w `_cmd_download_laz`; `_cz_download_bbox` — usunac martwa galaz
`bbox is None`) -> `parse_bbox_arg(args.bbox, args.bbox_crs)`; testy
`test_cli.py` (`Invalid bbox format` — fraza zostaje; testy wolajace
`_cmd_download_cz(args)` wprost przepiac na `main([...])`).

**K8** (opcjonalny) i **K9** — bez zmian wzgledem planu.

**Swiadomie niezrobione z planu:** zastapienie walidacji CZ
(`parser_tm33.find_tiles_tm33_for_bbox`, `cuzk/sheets._validate_request_bbox`)
przez `validate_bbox` (sekcja 3.2) — obie odrzucaja tez bbox
zdegenerowany (`min >= max`, test
`test_degenerate_bbox_rejected_before_network`), czyli maja inna semantyke
niz `validate_bbox` (punkt dozwolony); podmiana zmienilaby zachowanie
zapytan `exportImage`/`query`. Do decyzji przy odmrozeniu toru CZ.

## Commity

| Commit | Krok |
|---|---|
| `42c3214` | K1 `refactor(core): core/bbox.py — BBox, validate_bbox, transform_bbox, is_czech_crs` |
| `bd0dc6c` | K2 `refactor(core): SheetParser.get_bbox i selekcja arkuszy przez core.bbox` |
| `2cd6bcb` | K3 `fix(parser): PL-2000 z bboxa WGS84 przez poludnik osiowy strefy nie gubi wiersza arkuszy` |
| `a567af1` | K4 `refactor(core): czytniki SHP/GPKG przez core.bbox.transform_bbox` |
| `c129d46` | K5 `refactor(core)!: rejestr systemow godel bez parser_factory i Sm5Sheet, strip() spojnie` |
| `a87b1a6` | K7a `fix(cli): parse_bbox_arg — jedno parsowanie --bbox z walidacja w landcover/soilgrids` |
| `b8f1a22` (+ poprawka) | `docs: CHANGELOG Parsery 2026-10-07 i raport implementacji uproszczenia parserow` |
