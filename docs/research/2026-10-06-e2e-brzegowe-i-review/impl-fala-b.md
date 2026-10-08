# Fala naprawcza B — implementacja (2026-10-06)

Galaz `fix/review-2026-10-06` (worktree `Kartograf-fix`), baza `97175ff`
(fala A). Kontrakt: `cykl-e2e.md` E12-E17 (wersja z `develop` `21d4e84`;
w tej galezi plik jest jeszcze w wersji sprzed E12), raporty
`e2e-a-nmt.md`, `e2e-b-orto-laz-wycinek.md`, `review-1-duplikacje.md` (D3),
`review-2-deklaracje.md` (N3). Kazde zadanie TDD: test czerwony na kodzie
bazowym z wlasciwego powodu -> minimalna zmiana -> zielony -> mutacja
(zepsucie naprawy) -> test znow czerwony -> przywrocenie.

## Wynik koncowy

- `pytest tests/ -m "not live"`: **2178 passed** (baza 2125; +53 przypadki),
  16 deselected (`live`).
- `ruff check kartograf/ tests/`: All checks passed; `ruff format --check`:
  91 files already formatted.
- `mypy kartograf/`: 32 bledy; lista bez numerow linii (`sed -E
  's/:[0-9]+: /: /' | sort`) **identyczna** z baza `97175ff` (`diff` pusty).
  Po B2 byl 33. blad (`_partial_sheets` dostawal `Any | None`) — naprawiony
  commitem `0362b42`.
- `docs/DECISIONS.md` nietkniety (CRLF zachowane).

## Tabela mutacji

| Zad. | Mutacja | Wynik |
|------|---------|-------|
| B1 | `DownloadManager`: `variant=None` zamiast `provider.storage_variant` | 3 failed (`TestOrtoVariantStorage`: CIR przy RGB, segment CIR, segment B/W) |
| B2 | `_is_partial_sheet` (CLI) zawsze `False` | 3 failed (`TestPartialSheetWarning`: godlo, lista, hierarchia) |
| B2 | `_partial_sheets` (cutout) nigdy nie zwraca godla | 4 failed (sheet_sources lib, Warning wycinka, skip, all_nodata+partial) |
| B2 | `_sheet_source` bez klucza `full_sheet` | 5 failed (`TestPartialSheetVisibility` + `TestMissingSheets`) |
| B3 | CLI `--force` znow `cache=None` | 2 failed (`test_force_writes_fresh_record`, `test_force_passes_refresh_cache_to_provider_factory`) |
| B3 | `get_record` ignoruje `refresh` | 2 failed (zapis swiezego rekordu, `MetadataCache(refresh=True)`) |
| B4a | `existed = False` (zawsze "Downloaded to") | 1 failed (`test_second_run_reports_skip`) |
| B4b | sidecar bez `extra.all_nodata` | 3 failed (`TestEmptyCutoutSkip`) |
| B4b | `skipped_pl_cutout` ignoruje `extra.all_nodata` | 2 failed (skip CLI, skip biblioteki) |
| B5 | `_write_laz_sidecar` wolany bez `year`/`min_density` | 1 failed (`test_filters_recorded`) |
| B6 | `_resolve_record` wola `_layers(endpoint)` bez timeoutu | 1 failed (`test_explicit_download_timeout_reaches_capabilities`) |
| B6 | domyslny timeout `_fetch_wms_layers` = 10 | 2 failed (`test_layers_default_timeout_is_provider_timeout[nmt/orto]`) |
| B7 | skorowidz: stary `_horizontal_crs` (bez strip) | 2 failed (`' PL-1992'`, `'PL-2000:S7 '`) |
| B7 | `_feature_to_tile` nie odrzuca nieznanego `uklad_xy` | 9 failed (wszystkie nietypowe wartosci) |
| B7 | `LazTile.uklad` zgaduje z godla | 15 failed (kontrakt + `TestLazTileUklad`) |
| B8 | `pl_sheet_horizontal_crs` zawsze zwraca uklad godla (dodatkowo) | 3 failed (w tym nowy test E17) |

Wszystkie mutacje przywrocone (`git status` czysty po kazdej).

## B1 (E12, FAIL C12-f) — wariant orto w tozsamosci pliku

- **Zmiana:** `BaseProvider.storage_variant` (domyslnie `None`);
  `GugikOrtoProvider.storage_variant`: RGB -> `None`, CIR -> `"cir"`,
  B/W -> `"bw"`. `FileStorage(variant=...)` dokleja `_<wariant>` na koniec
  segmentu (walidacja `[a-z0-9]+`). Miejsca budowy sciezki orto:
  `DownloadManager.__init__` (storage z deskryptora) i CLI
  `_create_provider_and_storage` — oba przekazuja wariant providera.
  RGB zostaje w `orto/pl_<uklad>/` (bez migracji), CIR w
  `orto/pl_<uklad>_cir/`, B/W w `orto/pl_<uklad>_bw/`. Szablon deskryptora
  `orto/pl_{uklad}` bez zmian (wariant to wymiar zadania, nie zrodla).
- **Test:** `tests/test_gugik_orto.py::TestOrtoVariantStorage` — surowa
  fixtura `orto_2024.html` (CIR przed RGB): RGB pobrane, potem
  `DownloadManager(provider=GugikOrtoProvider(color="CIR")).download_sheet`
  -> inna sciezka (`orto/pl_1992_cir`), tresc CIR, URL CIR, sidecar
  `extra.source.kolor == "CIR"`; parametryzacja segmentow RGB/CIR/B-W.
  `tests/test_storage.py::TestStorageVariant` (sufiks, walidacja).
- **Przed:** 3 failed — `('orto', 'pl_1992') != ('orto', 'pl_1992_cir')`
  (CIR dostawal sciezke RGB, skip zwracal RGB).
- **Po:** passed.
- **Docs:** ARCHITECTURE sekcja 3 (drzewo, tabela deskryptorow, nowa regula
  segmentow 5), CLAUDE.md "Uklad data/", CHANGELOG.
- **Commit:** `dd5ae69` fix(orto): wariant koloru w segmencie storage — CIR nie dzieli sciezki z RGB

## B2 (E13) — niepelny arkusz widoczny

- **Regula wyboru bez zmian:** `select_sheet_record` nietkniety
  (`test_newest_wins_regardless_of_full_sheet` dalej zielony).
- **Stan wyjsciowy:** `extra.source.full_sheet` w sidecarze arkusza JUZ
  byl (`SkorowidzRecord.to_source`); brakowalo go w `sheet_sources`
  wycinka i w CLI.
- **Zmiana:**
  - `cutout._sheet_source` niesie `full_sheet`; `PlCutoutResult.partial_sheets`
    (godla z `full_sheet is False`; `None` nie jest "niepelny"), liczone po
    budowie i odtwarzane przy skip z `extra.sheet_sources`.
  - CLI `_warn_partial_sheets(paths)` czyta sidecary plikow wyniku: tor godla
    (pojedynczy arkusz) i `_finish_pl_sheets` (lista `--bbox`/`--geometry`
    i hierarchia). Dziala takze dla arkuszy pominietych jako istniejace.
  - `_report_pl_cutout`: `Warning:` o arkuszach z niepelnej kampanii; przy
    `all_nodata` + niepelne arkusze JEDEN komunikat "wycinek w calosci
    nodata — najnowsza kampania GUGiK jest niepelna dla N arkuszy (...)
    (starsza kampania moze miec dane ...)" zamiast "brak danych GUGiK".
- **Testy:** `tests/test_cli.py::TestPartialSheetWarning` (prawdziwy
  `DownloadManager`, provider z `source_info` -> sidecar `full_sheet: false`;
  godlo, lista, hierarchia, kontrola bez ostrzezenia),
  `tests/test_pl_cutout.py::TestPartialSheetVisibility` (sheet_sources,
  Warning, skip powtarza, brak Warning dla pelnych, C14-b all_nodata).
- **Przed:** 6 failed (`KeyError: 'full_sheet'`, pusty stderr, stary
  komunikat "brak danych GUGiK").
- **Po:** passed.
- **Swiadoma zmiana testu:** `TestMissingSheets::test_sidecar_lists_sheet_sources_from_sheet_sidecars`
  — oczekiwane wpisy `sheet_sources` dostaly `full_sheet` (True/False z
  `source`, `None` bez sidecara) + asercja `result.partial_sheets`.
- **Commit:** `0dde66c` feat(skorowidz): niepelny arkusz widoczny — Warning i full_sheet w sheet_sources

## B3 (E14) — `--force` zapisuje swiezy rekord

- **Mechanizm:** `MetadataCache(refresh=True)` — kazdy odczyt
  (`get_record`/`get_teryt`/`get_sheet`) jest chybieniem, zapisy dzialaja.
  CLI `_pl_metadata_cache` otwiera cache zawsze, przy `--force` w trybie
  `refresh` (wczesniej `None`). Biblioteka: docstring `download_pl_cutout`
  mowi, ze `force=True` sam nie omija cache rekordow — trzeba podac
  `MetadataCache(refresh=True)`.
- **Test:** `tests/test_gugik_orto.py::TestForceRefreshesRecordCache` —
  w cwd cache z przestarzalym rekordem (URL `70000_...`), `kartograf
  download <godlo> --product orto --force`: pobrany aktualny URL i
  `MetadataCache().get_record(...)` zwraca NOWY rekord; test jednostkowy
  `refresh=True`.
- **Przed:** 2 failed (cache po `--force` nadal z URL `70000`;
  `TypeError: unexpected keyword 'refresh'`).
- **Po:** passed.
- **Swiadoma zmiana testu:** `test_force_passes_no_cache_to_provider_factory`
  -> `test_force_passes_refresh_cache_to_provider_factory` (cache jest
  `MetadataCache` z `_refresh is True`, zamkniety po zadaniu). Kontrakt N6
  "`--force` = `None`" zmieniony swiadomie zgodnie z E14.
- **Docs:** CLAUDE.md (Skorowidz GUGiK), ARCHITECTURE 4.1, SCOPE, CHANGELOG.
- **Commit:** `60eaeb1` fix(cache): --force odswieza cache rekordow zamiast go pomijac

## B4 (E15) — skip

- **(a) Zmiana:** tryb godla CLI sprawdza przed `download_sheet`, czy plik
  docelowy juz istnieje (ta sama `storage.get_path` i ten sam warunek
  `skip_existing` co manager) i drukuje
  `Skipped <godlo> - already exists at <plik>` (wzor: tor CZ). Kontrakt
  biblioteki (`last_result` = `None` dla pojedynczego arkusza) bez zmian.
- **(b) Zmiana:** `write_pl_cutout_sidecar(all_nodata=)` ->
  `extra.all_nodata: true`; `skipped_pl_cutout` odtwarza `all_nodata`
  z sidecara (bez czytania rastra); `_report_pl_cutout` przy skip dopisuje
  "(z sidecara istniejacego wycinka)" do kazdego ostrzezenia.
- **Testy:** `tests/test_cli.py::TestSingleGodloSkipMessage` (drugi
  przebieg bez sieci: `Skipped ...`, bez `Downloaded to`; `--force` znow
  `Downloaded to`), `tests/test_pl_cutout.py::TestEmptyCutoutSkip`
  (sidecar `all_nodata`, brak flagi dla wycinka z danymi, skip CLI
  powtarza `Warning:`, `skipped_pl_cutout().all_nodata`).
- **Przed:** 4 failed (`Downloaded to` przy skip; `KeyError: 'all_nodata'`;
  pusty stderr przy skip; `all_nodata=False`).
- **Po:** passed.
- **Docs:** CLAUDE.md (zdanie "skipped nie czyta ponownie rastra" zastapione
  opisem odtwarzania z sidecara), ARCHITECTURE (tabela `extra`, krok 4 4.3),
  CHANGELOG.
- **Commit:** `f545c11` fix(cli): skip mowi o skip; pusty wycinek zapisany w sidecarze

## B5 (E16) — LAZ `request.year`/`min_density`

- **Zmiana:** `_write_laz_sidecar(..., year=, min_density=)` dopisuje klucze
  do `request` tylko gdy podane.
- **Test:** `tests/test_cli.py::TestLazSidecarRequestFilters` (z filtrami
  -> `year == 2023`, `min_density == 13`; bez filtrow -> brak kluczy).
- **Przed:** 1 failed (`KeyError: 'year'`). **Po:** passed.
- **Docs:** CLAUDE.md (LAZ --year) i ARCHITECTURE 4.7: `gestosc` /
  `--min-density` to wartosc nominalna z WFS (`char_przestrz`), faktyczna
  bywa kilkukrotnie wyzsza (~119 pkt/m2 przy nominale 15). CHANGELOG.
- **Commit:** `aab9628` fix(laz): sidecar request zapisuje --year i --min-density

## B6 (N3) — timeout GetCapabilities

- **Zmiana:** `SkorowidzLayersMixin._fetch_wms_layers(endpoint, timeout=None)`
  i `_layers(endpoint, timeout=None)`: `None` -> `DEFAULT_TIMEOUT` providera
  (30 s NMT/NMPT, 60 s orto); `_resolve_record` przekazuje `timeout` z
  `download(timeout=)`. Atrapa w `conftest.py` przyjmuje `timeout=None`.
- **Test:** `tests/test_wms_layer_validation.py::TestCapabilitiesTimeout`
  (marker `real_wms_layers`): pelny `download()` -> GetCapabilities z
  timeoutem 30/30/60 (NMT/NMPT/orto), jawne `timeout=45` dociera do
  GetCapabilities, domyslny `_layers()` = timeout providera.
- **Przed:** 4 failed (`[10] == [30]`, `[10] == [60]`, `10 != 45`).
- **Po:** passed.
- **Commit:** `26e4a63` fix(skorowidz): GetCapabilities z timeoutem providera zamiast 10 s

## B7 (D3, E11) — jeden parser `uklad_xy`

- **Zmiana:** `sources/registry.py::parse_pl_uklad(value) -> (uklad, strefa) | None`
  (strip + fullmatch `PL-1992` / `PL-2000:S[5-8]`). Uzycie:
  `horizontal_crs_for_uklad`, `skorowidz._horizontal_crs` (cienki adapter
  zwracajacy `(None, None)`), `LazTile.uklad` i
  `GugikLazProvider._feature_to_tile`. Nietypowa wartosc: rekord skorowidza
  bez ukladu (odrzucany jak dotad), kafel LAZ **pominiety w discovery**
  z ostrzezeniem w logu, `LazTile.uklad` recznie zbudowanego kafla ->
  `ValidationError` (BREAKING: koniec zgadywania z formatu godla).
- **Test kontraktowy:** `tests/test_uklad_contract.py` — realne wartosci
  (E11: `PL-1992`, `PL-2000:S5..S8`) i tolerowane biale znaki daja te sama
  odpowiedz w czterech sciezkach (parser, rekord skorowidza z
  `parse_skorowidz_records`, `horizontal_crs_for_uklad`, kafel z XML WFS
  i `LazTile.uklad`); nietypowe (`PL-2000`, `PL-2000:S9`, `PL-2000:S4`,
  `pl-2000:s6`, `PL-1992:S1`, `""`, `EPSG:2180`, `PL-2000 S6`,
  `PL-1992-NH`, `None`) sa odrzucane wszedzie.
- **Przed:** (po dodaniu samego `parse_pl_uklad`, konsumenci bez zmian)
  12 failed — skorowidz odrzucal `' PL-1992'`, `LazTile.uklad` dawal
  `2000`/`1992` dla nietypowych, discovery przepuszczal kafle.
- **Po:** passed.
- **exp2 (review-1) po zmianie** (`PYTHONPATH=Kartograf-fix`; kopia skryptu
  lapie `ValidationError`, bo oryginal wolalby `.uklad` bez try):

  ```
  uklad_xy           skorowidz._horizontal_crs    registry.horizontal_crs_for_uklad  LazTile.uklad(segment)
  'PL-1992'          ('1992', None)               EPSG:2180                          1992
  'PL-2000:S6'       ('2000', 6)                  EPSG:2177                          2000
  'PL-2000'          (None, None)                 None                               ValidationError
  'PL-2000:S9'       (None, None)                 None                               ValidationError
  ' PL-1992'         ('1992', None)               EPSG:2180                          1992
  'pl-2000:s6'       (None, None)                 None                               ValidationError
  'PL-1992 '         ('1992', None)               EPSG:2180                          1992
  ```

  Kolumny zgodne. Uwaga: skrypt uruchomiony bez `PYTHONPATH` importuje
  pakiet z `Kartograf/` (editable install w `.venv`), nie z worktree.
- **Swiadoma zmiana testow:** `TestLazTileUklad` — 4 testy kaskady
  (`crs=None` -> godlo, `EPSG:2180` -> godlo, fallback `2000`) zastapione
  parametryzowanym `test_unrecognized_crs_is_an_error_not_a_guess`.
- **Docs:** ARCHITECTURE 4.7 i tabela wymiarow `{uklad}`, CHANGELOG
  (BREAKING).
- **Commit:** `4594a87` fix(sources)!: jeden parser ukladu GUGiK — parse_pl_uklad (D3)

## B8 (E17) — PL-2000 strefa 7 w EPSG:2180 (dokumentacja)

- **Fixtura:** `tests/fixtures/gugik_asc/77912_1384976_7.125.11.19.head.asc`
  — naglowek + 2 wiersze (19,7 KB, CRLF jak w oryginale) z
  `<katalog-danych>/.../a/raw/C6/77912_1384976_7.125.11.19.head`.
- **Test:** `tests/test_sidecar.py::TestPl2000SheetPublishedIn2180` —
  prawdziwy `DownloadManager` + `GugikProvider`, rekord `PL-2000:S7`
  (`gfi_record`), plik = fixtura. Potwierdzone: segment
  `nmt/pl_2000_1m_evrf2007` (godlo), sidecar `horizontal_crs == EPSG:2180`
  (plik), `extra.source.uklad == "PL-2000:S7"` (rekord), `nodata == -9999`,
  ostrzezenie loggera `kartograf.sources.sidecar` "godlo 7.125.11.19
  wskazuje EPSG:2178, ale wspolrzedne pliku (x = 567976) sa w EPSG:2180 —
  zapisano uklad pliku". Test przeszedl od razu (kod juz tak dzialal);
  mutacja `pl_sheet_horizontal_crs` -> zawsze uklad godla: 3 failed.
- **ROZBIEZNOSC z opisem zadania:** ostrzezenie NIE ma prefiksu `Warning:`.
  Idzie przez `logging` (CLI nie konfiguruje handlerow, wiec Python wypisuje
  je na stderr handlerem `lastResort` — sama tresc). Sprawdzone przebiegiem
  CLI z atrapa sesji poza pytestem: stderr zawiera
  `Sidecar .../7.125.11.19.asc: godlo 7.125.11.19 wskazuje EPSG:2178, ale
  wspolrzedne pliku (x = 567976) sa w EPSG:2180 — zapisano uklad pliku`,
  rc 0. CLAUDE.md opisuje zachowanie FAKTYCZNE ("przez logger na stderr —
  BEZ prefiksu `Warning:`"). Czy zamienic to na `Warning:` CLI — decyzja
  koordynatora (zmiana kodu poza zakresem B8).
- **Commit:** `67971e5` docs(skorowidz): arkusze PL-2000 strefy 7 w EPSG:2180 — test i opis zachowania

## Pozostale commity

- `0362b42` fix(cutout): typ listy sheet_sources w skipped_pl_cutout (mypy)

## Odstepstwa i decyzje

1. **B1 — sufiks na koncu segmentu.** `FileStorage(variant=)` dokleja
   `_<wariant>` na koniec segmentu, a nie przed `_<vcrs>`. Dzis tylko orto
   uzywa wariantu, a szablon orto nie ma `{vcrs}`, wiec kolejnosc ADR-026
   `<kraj>_<uklad>[_<wariant>][_<vcrs>]` jest zachowana; docstring to mowi.
   Ogolna wstawka przed `{vcrs}` nie dzialalaby z `subdir` juz rozwiazanym
   przez `resolve_subdir(vertical_crs=)` w managerze — pominieta jako
   nadmiarowa.
2. **B2 — ostrzezenie takze przy skip.** `Warning:` o niepelnym arkuszu
   wynika z sidecara pliku wyniku, wiec powtarza sie przy ponownym
   uruchomieniu (spojnie z E15: ostrzezenia powtarzaja sie przy skip).
3. **B3 — `refresh` obejmuje wszystkie odczyty `MetadataCache`**
   (`get_teryt`, `get_sheet` tez), nie tylko `get_record`: to jeden tryb
   obiektu, a CLI uzywa go tylko w torach PL. Tor CZ (D16) bez zmian.
4. **B4a — wykrycie skip w CLI, nie w managerze.** CLI sprawdza istnienie
   pliku przed `download_sheet` zamiast wypelniac `last_result` dla
   pojedynczego arkusza: kontrakt biblioteki (`last_result is None` po
   pojedynczym arkuszu, 4 testy w `test_parallel_download.py`) zostaje.
5. **B7 — kafel z nieznanym `uklad_xy` pomijany w discovery** (wariant
   "odrzucony"), a `LazTile.uklad` rzuca `ValidationError` (wariant "jawny
   blad") — oba dopuszczone w zadaniu; razem domykaja oba wejscia (WFS
   i reczna konstrukcja). Biale znaki na brzegach sa tolerowane wszedzie
   (wczesniej tylko w rejestrze; skorowidz je odrzucal). Wielkosc liter
   NIE jest tolerowana (`pl-2000:s6` odrzucone) — w danych nie wystepuje.
6. **B8 — brak prefiksu `Warning:`** (wyzej). CLAUDE.md opisuje stan
   faktyczny zamiast deklaracji z zadania.
7. **`cykl-e2e.md` w tej galezi jest w wersji sprzed E8-E18** (commity
   `ae89a73`, `21d4e84` sa tylko na `develop`); kontrakt czytany z
   `develop`. Raport nie konfliktuje (nowy plik).
8. **Fixtury:** dodana tylko jedna (`tests/fixtures/gugik_asc/...`, B8).
   B1/B2/B3 korzystaja z istniejacej surowej `orto_2024.html` i syntetycznych
   rekordow `gfi_record` — surowe body z rundy (E18) przygotowuje rownolegly
   agent w `Kartograf-fixtures`.
