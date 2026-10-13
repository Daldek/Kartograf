# Spojnosc CLI, biblioteki i API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-12

**Goal:** To samo zadanie uruchomione przez CLI i przez publiczne API daje te same pliki, sidecary, statusy, plan, komunikaty o danych i bledy (spec sekcja 1). CLI tylko tlumaczy flagi na wywolanie biblioteki i wypisuje wynik (Z1); kazda funkcja pobierajaca ma blizniaka `check_*` (Z2); komunikaty o danych powstaja w bibliotece (Z3); jeden typ bledu wejscia (Z4); polski ASCII w CLI i wyjatkach (Z5); wspolny cache (Z6); testy zgodnosci (Z7).

**Architecture:** Nowe moduly: `kartograf/_clock.py` (jedno zrodlo czasu), `kartograf/notices.py` (`Notice`), `kartograf/cache/defaults.py` (rozstrzyganie `cache: MetadataCache | bool`), `kartograf/download/options.py` (walidacja wyborow danych przeniesiona z `_pl_option_error`/`_cz_option_error`), `kartograf/download/area.py` (kraje, obwiednia geometrii, `parent_request`, arkusze obszaru PL), `kartograf/download/data.py` (`download_data`/`check_data` -> `DataReport`). Funkcje torow (`DownloadManager`, wycinki PL/CZ, arkusz CZ, LAZ) dostaja jednolity ksztalt (spec 4.4). `LandCoverManager.download` i `HSGCalculator.calculate_hsg` jako funkcje poziomu komendy (spec 4.2-4.3). `kartograf/cli/download_cmd.py` (2790 linii) kurczy sie do tlumaczenia flag i wypisywania wyniku; testy logiki przechodza z `tests/test_cli.py` do testow biblioteki.

**Spec:** `docs/superpowers/specs/2026-10-12-cli-api-consistency-design.md` — ZAAKCEPTOWANY 2026-10-12 (Z1-Z7, S1-S6 wg propozycji). Dowody: `docs/research/2026-10-12-cli-api-consistency/raport.md` (R1-R13).

**Galaz:** `chore/cli-api-consistency` (z `develop` `d5215e8`). Do `develop` po Task 18, za zgoda uzytkownika.

---

## Global Constraints

Jak w planach magazynu wersjonowanego (Python z `.venv`; brama przed kazdym commitem: `.venv/bin/python -m pytest tests/ -m "not live" -q`, `.venv/bin/python -m ruff check .`, `.venv/bin/python -m ruff format --check .`, `.venv/bin/python -m mypy kartograf/ tests/`; Conventional Commits po polsku, autor `Daldek <git@debever.pl>` bez `Co-Authored-By`; commit wylacznie przez straznik wzorcow `! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit -m "..."` — brak pliku wzorcow = zatrzymaj sie i zapytaj; angielskie identyfikatory i docstringi; CRLF w `docs/DECISIONS.md`; testy zachowania, nie okablowania). Dodatkowo:

- **Stan wyjsciowy:** 3379 testow offline zielonych (`--collect-only`: 3379/3397, 18 `live`); `tests/test_cli.py` 510 testow / 11 598 linii, 261 celow `patch("kartograf.cli.download_cmd....")`; `fail_under = 60` (`pyproject.toml:89`).
- **Migracja testow:** test, ktory sprawdza walidacje, wybor danych albo komunikat o danych, przechodzi razem z logika do testow biblioteki (cel patcha `kartograf.download.data.*` / `kartograf.download.area.*` itd.), z asercja na `DataReport`/`Notice`/wyjatku zamiast na stderr. W `tests/test_cli.py` zostaja testy tlumaczenia: flagi -> argumenty funkcji (atrapa `download_data` sprawdza kwargs), wynik -> wyjscie i kod, plik planu. Testy pinujace usuwane zachowanie (`last_result`, `last_sheet`, `check_updates()`, `upgrade()`, `UpgradeReport`, `prepare_pl_cutout`/`run_*` jako API, `stat` HSG, `download_all_counties`, `calculate_hsg_by_*`, `ValueError` z wejscia) przepisuj albo usuwaj — bez podwojnych sciezek.
- **Teksty:** nowe i przenoszone komunikaty od razu po polsku ASCII (Z5); Task 14 domyka reszte.
- **Live:** tylko Task 17; katalog danych wskazuje uzytkownik, sciezki nie zapisuj w repo.
- **Hydrograf/Hydrolog:** poza tym repo; zmiany API opisuje CHANGELOG [0.8.0] "Co zrobic" (Task 16).

## Decyzje implementacyjne (bez nowych decyzji produktowych)

1. **Zegar:** `kartograf/_clock.py` z `def now() -> datetime` (UTC). Uzywaja go `sources/sidecar.py:182` (`_now_iso`), `download/versions.py:77` (`VersionRef.downloaded` bez `now`) i `download/plan.py:152` (`new_plan`, `checked_at`). Parametry `now=` (`run_pl_wcs_cutout`, `run_cz_cutout`) zostaja, domyslnie z `_clock.now()`. Testy: fixtura `frozen_clock` w `tests/conftest.py` (`monkeypatch.setattr("kartograf._clock.now", ...)`). TTL cache (`time.time()` w `cache/metadata.py`) i sprzatanie `.incoming` (`versions.cleanup_stale`) bez zmian — nie wplywaja na wynik.
2. **Cache (Z6):** `kartograf/cache/defaults.py`: `DEFAULT_CACHE_FILENAME = ".kartograf_cache.db"` (przeniesione z `cli/cache_cmd.py`), `default_cache_path() -> Path` (cwd), kontekst `open_cache(cache: MetadataCache | bool, *, force: bool, on_notice=None) -> Iterator[MetadataCache | None]`: `False` -> `None`; `True` -> wlasny `MetadataCache(default_cache_path(), refresh=force)` zamykany na wyjsciu; instancja + `force=False` -> ta instancja (nie zamykana); instancja + `force=True` -> nowy `MetadataCache(cache.db_path, ttl_seconds=..., refresh=True, strict=...)` na tym samym pliku (WAL), zamykany na wyjsciu — bez przelaczania flagi wspoldzielonej instancji. Wylaczenie cache (`MetadataCache(on_disabled=...)`) daje `Notice("warning", CACHE_DISABLED, ...)` przez `on_notice`.
3. **`on_notice`:** funkcje poziomu komendy (`download_data`, `check_data`, `LandCoverManager.download/check`, `HSGCalculator.calculate_hsg/check_hsg`) przyjmuja `on_notice: Callable[[Notice], None] | None`. Kazdy komunikat trafia do `on_notice` w chwili powstania ORAZ do `notices` wyniku. CLI wypisuje z `on_notice` (zachowuje dzisiejsza kolejnosc: `Info:` o przycieciu krajow i rozmiarze wycinka PRZED pobraniem) i nie wypisuje `notices` drugi raz. Z `check_*`: tylko `on_notice` (wynik to `UpdatePlan`).
4. **`Notice.code`:** stale `str` w `kartograf/notices.py` (np. `SHEET_LIST`, `GEOMETRY_LAYER_DEFAULT`, `AUTO_NARROWED_TO_PL`, `AUTO_CLIPPED`, `AUTO_AREA_OUTSIDE`, `AUTO_PARTIAL_SUCCESS`, `CAMPAIGN_OPTS_PL_ONLY`, `LEGACY_CAMPAIGNS_DIR`, `NEWER_AVAILABLE`, `NO_COVERAGE_HINT`, `NO_COVERAGE_SOME`, `UNVERIFIED_LOCAL`, `CHECK_FAILED`, `BETTER_COVERAGE`, `LINK_OUTSIDE_RANGE`, `SHEET_CRS_MISMATCH`, `INCOMPLETE_CAMPAIGN`, `CUTOUT_SIZE`, `ALL_NODATA`, `LAZ_SUPERSEDED`, `CORINE_PREVIEW`, `CACHE_DISABLED`). Pelna lista z warunkami: inwentaryzacja w Task 11 Step 1 (zrodlo: `download_cmd.py` 199-227, 257-271, 545-546, 742-804, 933, 1010-1012, 1391-1393, 1465-1466, 1596-1611, 1645-1646, 1680-1712, 1781-1784, 1854-1947, 2000-2084, 2133-2136, 2152-2155, 2327-2340, 2538-2545; `landcover_cmd.py` 277-281). Biblioteka nie loguje tekstu `Notice` drugi raz (usuwa podwojna linie I-1 i `_library_log_muted`, `download_cmd.py:2484`).
5. **`DataReport.ok`:** liczony w bibliotece wg dzisiejszych regul: arkusze PL `_finish_pl_sheets` (`download_cmd.py:1715-1803`: brak plikow = `False`; bledy twarde = `False`; tylko brak pokrycia przy >= 1 pliku = `True` + `Notice`), LAZ (bledy kafli = `False`), wycinki (blad = `False`, `all_nodata` = `True` + `Notice`), `stale` niepuste = `False`, `country="auto"` z >= 1 krajem udanym = `True` + `AUTO_PARTIAL_SUCCESS` (ADR-023 pkt 4-5, `download_cmd.py:1006-1015`). CLI: `0 if report.ok else 1`; bledy wejscia nadal wyjatkiem (`main` -> `Error:`, kod 1).
6. **`DownloadResult` (arkusze PL):** zostaje typem wyniku; `download_sheet`, `download_hierarchy`, `download_sheets` go ZWRACAJA. Pola `succeeded`, `failed`, `skipped`, `no_coverage`, `unverified`, ... bez zmian (Hydrograf czyta je dzis z `last_result`). `files` zmienia typ na `dict[str, tuple[VersionedFile, ...]]` (godlo -> pliki z pelnym `VersionedFile`); dochodza `stale: tuple[PlanItem, ...]` i `notices: tuple[Notice, ...]`. `last_result`, `last_sheet` usuniete. `SheetFetch` zostaje typem wewnetrznym (poza `__all__`).
7. **Plan dla arkuszy PL:** cialo `updates.upgrade` (`updates.py:130`) przechodzi do `DownloadManager.download_sheets(..., update="upgrade", plan=plan)` przez `select_planned` (`plan.py:186`) jak w innych torach; `updates.check_updates` (`updates.py:115`) -> `DownloadManager.check_sheets(sheets)`. Modul `updates.py` zostaje wewnetrzny (budowa pozycji `_items`) albo wchodzi do `manager.py` — wybor wykonawcy wg rozmiaru diffu.
8. **`max_workers` -> `workers`** w `DownloadManager`, `download_laz_area` (spojnie z `--workers`, spec 4.4); domyslne `1` w torach, `4` w `download_data` i CLI.
9. **CRS obszaru w torach:** LAZ, land cover, HSG przyjmuja `BBox` w dowolnym obslugiwanym CRS; przeliczenie do EPSG:2180 ta sama droga co dzis CLI (`_resolve_laz_bbox` `download_cmd.py:2273-2304`, `country_bbox` dla ukladow CZ z przypieta operacja). `transform_bbox` eksportowany bez zmian; dla ukladow CZ biblioteka uzywa sciezki przypietej, nie `transform_bbox`.
10. **HSG bez `stat` (R3):** stala `_HSG_STAT = "mean"` w `hydrology/hsg.py`; segmenty `soil/global_soilgrids_<prop>_<depth>_mean` i `hsg/global_soilgrids_<depth>_mean` oraz klucz `stat` w sidecarze bez zmian — istniejace magazyny dzialaja bez migracji.
11. **`LandCoverManager.download` zawsze `LandCoverAreaResult`** (S3): `teryt` -> jeden element; BDOT10k z `bbox`/`sheet`/`geometry` -> kazdy powiat (dzisiejsze `download_all_counties`); CORINE/SoilGrids -> jeden element. `LandCoverResult` zostaje typem elementu (`files`). Dochodza `notices`, `ok` (`failed` puste i `stale` puste). Usuniete: `download_all_counties`, `check_all_counties` (wchloniete) oraz `download_by_teryt/bbox/sheet` i `download_batch` (drugi ksztalt wyniku; decyzja uzytkownika 2026-10-12).
12. **Nazwy wyjatkow:** `ValidationError` bez zmian hierarchii (`exceptions.py`), 32 miejsca wejscia z 36 `raise ValueError` przechodza na `ValidationError` (lista w Task 2); 4 niezmienniki zostaja (`campaigns.py:121`, `campaigns.py:430` — lapany lokalnie w 431, `links.py:212` — wewnetrzny JSON, `providers/pl/wcs.py:145`).

## Review Focus

1. **Zgodnosc bajtowa CLI = API (Z7):** `tests/test_parity.py` — kazdy scenariusz specu 6 porownuje drzewa wyjscia (sciezki + bajty plikow i sidecarow), statusy, plan, `Notice` i typ/tekst bledu przy zamrozonym zegarze.
2. **CLI bez logiki danych (Z1):** po Task 12-13 w `kartograf/cli/` nie ma `find_sheets_for_bbox`, `country_bbox`, `split_bbox_by_country`, `get_overall_bbox`, `DownloadManager`, providerow ani walidacji wartosci; test `test_cli_imports_no_data_logic` (AST importow `kartograf/cli/*.py` vs lista zakazana) — jedyny test na tekst zrodla, bo pilnuje reguly architektonicznej, nie zachowania; uzasadnienie w docstringu testu.
3. **Kolejnosc komunikatow:** `Info:` o przycieciu krajow i rozmiarze wycinka przed pierwszym pobraniem (decyzja 3) — testy z atrapa liczaca pobrania i kolejnoscia wywolan `on_notice`.
4. **`force` i cache wspoldzielony:** `force=True` z instancja uzytkownika nie zmienia jej odczytow w innych watkach (decyzja 2) — `test_force_with_user_cache_does_not_flip_shared_instance`.
5. **Brak migracji magazynu:** HSG i SoilGrids po usunieciu `stat` trafiaja w te same segmenty (decyzja 10) — `test_hsg_segment_unchanged_after_stat_removal` na magazynie z wersja utworzona starym kodem (fixtura katalogu).
6. **Wyjatki:** zaden `except ValueError` w `kartograf/` nie lapie po zmianie `ValidationError` z wejscia (Task 2 Step 1), a CLI nie ma obejsc `except ValueError` (`landcover_cmd.py:248`, `download_cmd.py:1054`, `2411`).

## Mapa plikow

| Plik | Zmiana |
|---|---|
| `kartograf/_clock.py` | NOWY (Task 1) |
| `kartograf/notices.py` | NOWY (Task 3) |
| `kartograf/cache/defaults.py` | NOWY (Task 4); `cli/cache_cmd.py` korzysta |
| `kartograf/exceptions.py`, providery, `landcover/manager.py`, `download/storage.py`, `download/laz.py`, `core/sheet_parser.py` | Task 2 |
| `kartograf/download/manager.py`, `download/updates.py` | Task 5 |
| `kartograf/download/cutout.py` | Task 6 |
| `kartograf/download/cz_cutout.py`, `download/cz_sheets.py` | Task 7 |
| `kartograf/download/laz.py`, `providers/pl/gugik_laz.py` | Task 8 |
| `kartograf/landcover/manager.py`, `landcover/store.py` | Task 9 |
| `kartograf/hydrology/hsg.py` | Task 10 |
| `kartograf/download/options.py`, `download/area.py`, `download/data.py` | NOWE (Task 11) |
| `kartograf/cli/download_cmd.py`, `cli/_parser.py`, `cli/commands.py` | Task 12 |
| `kartograf/cli/landcover_cmd.py`, `cli/soilgrids_cmd.py`, `cli/_parser.py` | Task 13 |
| `kartograf/cli/*.py`, teksty wyjatkow w `kartograf/**` | Task 14 |
| `kartograf/__init__.py` | Task 5-11 (eksporty), Task 16 (docstring) |
| `tests/conftest.py` (`frozen_clock`), `tests/parity.py` (harness), `tests/test_parity.py` | Task 1, 12, 13, 15 |
| `tests/test_download_data.py`, `tests/test_download_options.py`, `tests/test_download_area.py` | NOWE (Task 11-12, przejete z `test_cli.py`) |
| `tests/test_cli_language.py` | NOWY (Task 14) |
| `README.md`, `docs/*` | Task 0, 16 |

---

### Task 0: Przyklad w README

**Files:** Modify: `README.md:83`

- [ ] **Step 1:** `print(result.path)` -> `print(result.file.path)` (`PlCutoutResult` ma `file`, nie `path`). Sprawdzenie: `inspect.signature` + pola dataclass dla kazdego przykladu Pythona w `README.md` (skrypt jednorazowy, nie commitowany).
- [ ] **Step 2: Commit** — `docs(readme): poprawny atrybut wyniku wycinka PL`

---

### Task 1: Zegar i harness zgodnosci

**Files:**
- Create: `kartograf/_clock.py`, `tests/parity.py`
- Modify: `kartograf/sources/sidecar.py:182-185`, `kartograf/download/versions.py:77-80`, `kartograf/download/plan.py:152-160`, `tests/conftest.py`
- Test: `tests/test_clock.py`

**Interfaces:**
```python
# kartograf/_clock.py
def now() -> datetime: ...          # datetime.now(UTC)

# tests/parity.py
def run_both(cli_argv: list[str], api_call: Callable[[Path], object], tmp_path: Path) -> ParityRun: ...
def assert_same_store(a: Path, b: Path) -> None: ...   # te same sciezki wzgledne, bajty plikow i sidecarow
```

- [ ] **Step 1: Testy** — `test_frozen_clock_fixes_downloaded_at_label_and_checked_at` (zamrozony zegar -> `downloaded_at`, etykieta `downloaded` i `checked_at` rowne zadanej chwili), `test_two_runs_same_instant_byte_identical_sidecar` (dwa zapisy tej samej tresci do roznych magazynow -> identyczne bajty sidecara), `test_assert_same_store_reports_first_difference` (harness: rozny bajt -> czytelny komunikat ze sciezka).
- [ ] **Step 2: Implementacja** — `_clock.now`; `_now_iso`, `VersionRef.downloaded`, `new_plan` przez `_clock.now()`; fixtura `frozen_clock(monkeypatch)` w `tests/conftest.py`; `tests/parity.py` (`run_both` uruchamia `kartograf.cli.main` z `-o <tmp>/cli` i `api_call(<tmp>/api)` w `monkeypatch.chdir(tmp_path)`, zbiera kod/stdout/stderr i wynik). Istniejace `now=NOW` w `tests/test_wcs_cutout.py` bez zmian.
- [ ] **Step 3:** Brama.
- [ ] **Step 4: Commit** — `test: wspolny zegar i harness zgodnosci CLI = API`

---

### Task 2: Wyjatki wejscia = `ValidationError` (Z4, R6)

**Files:**
- Modify (32 miejsca `raise ValueError` -> `ValidationError`): `kartograf/landcover/manager.py:270, 614, 616, 649, 655, 662`; `kartograf/download/storage.py:120`; `kartograf/download/laz.py:413`; `kartograf/providers/base.py:199, 412`; `kartograf/providers/corine.py:414, 420`; `kartograf/providers/pl/gugik_orto.py:268, 274`; `kartograf/providers/pl/gugik.py:178, 186, 193, 481, 487, 493`; `kartograf/providers/pl/bdot10k.py:252`; `kartograf/providers/pl/gugik_laz.py:321, 364, 503, 740, 747`; `kartograf/providers/soilgrids.py:191, 274, 281, 287, 293`; `kartograf/core/sheet_parser.py:612`
- Bez zmian (niezmienniki): `kartograf/download/campaigns.py:121, 430`, `kartograf/download/links.py:212`, `kartograf/providers/pl/wcs.py:145`
- Modify (obejscia CLI): `kartograf/cli/landcover_cmd.py:248-253`, `kartograf/cli/download_cmd.py:1054`, `2411`
- Test: 26 x `pytest.raises(ValueError` (`tests/test_landcover.py` 6, `test_gugik_provider.py` 6, `test_soilgrids.py` 4, `test_sheet_parser.py` 2, `test_gugik_orto.py` 2, `test_gugik_laz.py` 2, `test_laz_download.py` 1, `test_integration.py` 1, `test_gugik_nmpt.py` 1, `test_edition.py` 1)

- [ ] **Step 1: Analiza lapania** — dla kazdego `except ValueError`/`except (..., ValueError, ...)` w `kartograf/` (m.in. `download_cmd.py:1054, 1620, 1828, 2411`, `landcover_cmd.py:248`, `campaigns.py:431, 465, 504`, `links.py:62, 156`, `plan.py:82`, `versions.py:200`, `landcover/manager.py:100`, `corine.py:352`, `cuzk/client.py:98`, `cuzk/sheets.py:258`, `gugik_laz.py:204, 1043`, `prg.py:136`, `skorowidz.py:153, 165`, `sidecar.py:70, 108`, `http.py:65, 68`, `auth/client.py:421`, `auth/proxy.py:134`): czy w bloku `try` jest wywolanie, ktore po zmianie rzuca `ValidationError`. Zapisz w opisie commitu; miejsca, ktore dzis polykaja blad wejscia z `ValueError`, to zmiana zachowania — test.
- [ ] **Step 2: Testy** — 26 asercji `ValueError` -> `ValidationError` (te, ktore dotycza wejscia); `test_input_errors_are_kartograf_errors` (parametryzowany: bbox EPSG:4326 do LAZ przed Task 8, zly `vertical_crs` w `GugikProvider`, zla `property` SoilGrids, zly `format` BDOT10k, rok CORINE -> `isinstance(e, KartografError)` i nie `ValueError`). Sciezka CLI bez nowych testow: `main` juz zamienia `KartografError` na jedna linie `Error:` (`commands.py:98-102`).
- [ ] **Step 3: Implementacja** — zamiany; usuniecie obejsc CLI; STANDARDS 11.1/11.2: regula Z4 (wejscie = `ValidationError`, zrodlo = `DownloadError`, niezmiennik = wbudowany, nieznany argument = `TypeError`; `ValidationError` nie dziedziczy z `ValueError`). Brama.
- [ ] **Step 4: Commit** — `refactor(errors)!: bledy wejscia jako ValidationError w calej bibliotece (Z4)`

---

### Task 3: `Notice` i typy wynikow poziomu komendy

**Files:**
- Create: `kartograf/notices.py`, `tests/test_notices.py`
- Modify: `kartograf/__init__.py` (`Notice` w `__all__`)

**Interfaces:**
```python
@dataclass(frozen=True)
class Notice:
    level: Literal["info", "warning"]
    code: str
    text: str

class NoticeSink:                    # zbiera i przekazuje dalej
    def __init__(self, on_notice: Callable[[Notice], None] | None) -> None: ...
    def emit(self, level, code, text) -> None: ...   # append + on_notice(n)
    @property
    def notices(self) -> tuple[Notice, ...]: ...
```

- [ ] **Step 1: Testy** — `test_sink_forwards_in_order_and_collects`, `test_sink_without_callback_collects`, `test_notice_text_ascii` (konstruktor odrzuca znaki spoza ASCII — `ValueError`, bo to blad programu, nie wejscia (Z4); pilnuje Z5 u zrodla).
- [ ] **Step 2: Implementacja**, stale kodow (decyzja 4), brama.
- [ ] **Step 3: Commit** — `feat(api): Notice - komunikaty o danych w wyniku biblioteki (Z3)`

---

### Task 4: Wspolny cache metadanych (Z6, R12)

**Files:**
- Create: `kartograf/cache/defaults.py`, `tests/test_cache_defaults.py`
- Modify: `kartograf/cli/cache_cmd.py:14-16` (`cli_cache_path` -> `default_cache_path`), `kartograf/cli/download_cmd.py:189-247` (`_cli_metadata_cache`, `_pl_metadata_cache` -> `open_cache`), `kartograf/cli/landcover_cmd.py:216`
- Test: `tests/test_cli.py::test_force_passes_refresh_cache_to_provider_factory` (1434), `::test_without_force_opens_cache_in_cwd_and_closes_it` (1514), `::test_force_refreshes_sheet_index_cache` (5348), `tests/test_gugik_orto.py::TestForceRefreshesRecordCache` (859-911)

**Interfaces:**
```python
def default_cache_path() -> Path: ...
@contextmanager
def open_cache(cache: MetadataCache | bool, *, force: bool,
               on_notice: Callable[[Notice], None] | None = None) -> Iterator[MetadataCache | None]: ...
```

- [ ] **Step 1: Testy** — `test_true_opens_cwd_cache_and_closes`, `test_false_is_none`, `test_instance_passed_through_not_closed`, `test_force_true_reads_miss_writes_hit_on_default`, `test_force_with_user_cache_does_not_flip_shared_instance` (instancja uzytkownika po wywolaniu z `force=True` dalej czyta trafienia; wpis zapisany w trakcie widoczny), `test_disabled_cache_emits_notice` (plik w katalogu tylko do odczytu -> `Notice("warning", "cache_disabled")` raz).
- [ ] **Step 2: Implementacja** (decyzja implementacyjna 2); CLI tworzy cache tylko przez `open_cache`; `Notice` z Task 3. Brama.
- [ ] **Step 3: Commit** — `feat(cache): wspolny domyslny cache metadanych CLI i biblioteki (Z6)`

---

### Task 5: Tor arkuszy PL — wynik, plan, `check_sheets`, `year`

**Files:**
- Modify: `kartograf/download/manager.py` (`DownloadResult` 103-203, `SheetFetch` 224-290, `__init__` ~460-553, `download_sheet` 760-856, `download_hierarchy` 858-967, `download_sheets` 969+), `kartograf/download/updates.py` (115-190), `kartograf/__init__.py` (bez `check_updates`, `upgrade`, `UpgradeReport`, `SheetFetch`)
- Modify (wywolujacy): `kartograf/cli/download_cmd.py` (`_last_result` 1434-1440, `_run_plan_modes` 1525-1556, `_download_sheet_list` 1651-1674, `_sheet_result` 1949-1966, sciezka `--sheet` 1360-1432)
- Test: `tests/test_updates.py`, `tests/test_manager_campaigns.py`, `tests/test_download_manager*.py`, `tests/test_cli_update_modes.py`, `tests/test_cli.py` (helpery `_sheet_list_manager`, `_mock_manager` 75-105)

**Interfaces:**
```python
class DownloadManager:
    def __init__(self, output_dir, provider, *, storage=None, workers: int = 1,
                 sidecar_extra=None, year: int | None = None, all_campaigns=False,
                 min_year=None, max_year=None, full_sheet=False,
                 on_notice: Callable[[Notice], None] | None = None): ...
    def download_sheet(self, sheet, *, update=None, plan=None, on_progress=None) -> DownloadResult: ...
    def download_hierarchy(self, sheet, target_scale, *, update=None, plan=None, on_progress=None) -> DownloadResult: ...
    def download_sheets(self, sheets, *, update=None, plan=None, on_progress=None) -> DownloadResult: ...
    def check_sheets(self, sheets) -> UpdatePlan: ...
# DownloadResult: + files: dict[str, tuple[VersionedFile, ...]], stale: tuple[PlanItem, ...], notices: tuple[Notice, ...]
```

- [ ] **Step 1: Testy** — `test_download_sheet_returns_result_with_versioned_files` (status, etykieta, `version_path`), `test_hierarchy_returns_result_failures_collected`, `test_check_sheets_plan_equals_old_check_updates` (te same pozycje co `check_updates` przed zmiana — fixtura planu z `tests/test_updates.py`), `test_download_sheets_upgrade_with_plan_downloads_only_planned`, `test_download_sheets_stale_plan_item_reported_not_downloaded` (`stale`, zero pobran), `test_year_equals_min_max` i `test_year_with_min_year_is_validation_error` (tekst jak CLI `download_cmd.py:1219`), `test_no_last_result_attribute`, `test_newer_and_unverified_become_notices` (`NEWER_AVAILABLE`, `UNVERIFIED_LOCAL` z tekstami z `download_cmd.py:1645-1646, 1708-1710`).
- [ ] **Step 2: Implementacja** (decyzje 6, 7, 8); `updates.py` bez publicznych `check_updates`/`upgrade`; CLI przechodzi na wartosc zwracana (zachowanie CLI bez zmian — `tests/test_cli_update_modes.py` asercje na stdout/stderr bez zmian). Brama.
- [ ] **Step 3: Commit** — `feat(download)!: arkusze PL zwracaja DownloadResult, plan= i check_sheets (spec 4.4)`

---

### Task 6: Wycinek PL — `check_pl_cutout` z argumentami `download_pl_cutout`

**Files:**
- Modify: `kartograf/download/cutout.py` (`prepare_pl_cutout` 159, `check_pl_cutout` 375, `run_pl_wcs_cutout` 406, `download_pl_cutout` 533), `kartograf/__init__.py` (bez `PlCutout`, `prepare_pl_cutout`, `run_pl_wcs_cutout`), `kartograf/cli/download_cmd.py` (`_download_pl_cutout` 2085-2158)
- Test: `tests/test_wcs_cutout.py`, `tests/test_pl_cutout.py` (`TestPreparePlCutout`), `tests/test_cli.py` (patche `prepare_pl_cutout`)

**Interfaces:**
```python
def download_pl_cutout(bbox, *, target_crs, output_dir, vertical_crs, product,
                       update=None, plan=None, parent_request=None,
                       cache: MetadataCache | bool = True, on_notice=None) -> PlCutoutResult: ...
def check_pl_cutout(bbox, *, target_crs, output_dir, vertical_crs, product,
                    cache: MetadataCache | bool = True, on_notice=None) -> UpdatePlan: ...
# PlCutoutResult: + notices
```

- [ ] **Step 1: Testy** — `test_target_crs_keyword_only` (pozycyjnie -> `TypeError`), `test_check_pl_cutout_same_args_as_download`, `test_download_pl_cutout_plan_stale_no_download`, `test_cutout_size_notice_before_first_wcs_request` (`CUTOUT_SIZE`, warunek z `download_cmd.py:2128-2138`: >1 kawalek albo >= 1 GiB i plik do pobrania; kolejnosc: `on_notice` przed pierwszym zapytaniem atrapy), `test_all_nodata_notice` (tekst z `download_cmd.py:2152-2155`). Testy `run_pl_wcs_cutout`/`prepare_pl_cutout` przepisane na `_run_pl_wcs_cutout`/`_prepare_pl_cutout` (wewnetrzne) albo na `download_pl_cutout` — bez duplikatow.
- [ ] **Step 2: Implementacja** (prywatne `_prepare_pl_cutout`, `_run_pl_wcs_cutout`; CLI wola `download_pl_cutout`/`check_pl_cutout` z `on_notice`). Brama.
- [ ] **Step 3: Commit** — `feat(cutout)!: wycinek PL - check_pl_cutout z argumentami pobrania, plan= i Notice`

---

### Task 7: CZ — wycinek i arkusz publiczne w jednym ksztalcie (R4)

**Files:**
- Modify: `kartograf/download/cz_cutout.py` (`check_cz_cutout` 155, `run_cz_cutout` 173, `download_cz_cutout` 258), `kartograf/download/cz_sheets.py` (`check_cz_sheet` 81, `run_cz_sheet` 108; NOWE `download_cz_sheet`), `kartograf/__init__.py` (+ `download_cz_sheet`, `check_cz_sheet`, `CzSheetResult`; bez `run_cz_cutout`), `kartograf/cli/download_cmd.py` (`_run_cz` 645-672, `_cz_download_sheet` 2497-2536, `_cz_download_bbox` 2548-2600, `_warn_cz_all_nodata` 2538-2545)
- Test: `tests/test_cz_cutout.py`, `tests/test_cz_sheets.py`, `tests/test_cli.py` (`TestCmdDownloadCz` 5324-6256)

**Interfaces:**
```python
def download_cz_cutout(bbox, *, output_dir, target_crs, vertical_crs, resolution,
                       update=None, plan=None, parent_request=None, cache=True, on_notice=None) -> CzCutoutResult: ...
def check_cz_cutout(bbox, *, output_dir, target_crs, vertical_crs, resolution, cache=True, on_notice=None) -> UpdatePlan: ...
def download_cz_sheet(sheet, *, output_dir, vertical_crs, resolution: str | None = None,
                      update=None, plan=None, cache=True, on_notice=None) -> CzSheetResult: ...
def check_cz_sheet(sheet, *, output_dir, vertical_crs, resolution=None, cache=True, on_notice=None) -> UpdatePlan: ...
```
`resolution` arkusza: SM5 tylko `5m` (pominiete = `5m`), TM33 wymagane (`2m`/`5m`) — reguly z `_cz_option_error` (`download_cmd.py:455-493`), komunikaty te same.

- [ ] **Step 1: Testy** — `test_check_cz_cutout_same_args_as_download` (bez providera i `image_crs`), `test_download_cz_cutout_plan`, `test_download_cz_sheet_sm5_without_resolution`, `test_download_cz_sheet_sm5_2m_is_validation_error` (tekst `download_cmd.py:472`), `test_download_cz_sheet_tm33_requires_resolution`, `test_check_cz_sheet_plan_items`, `test_cz_all_nodata_notice` (tekst `download_cmd.py:2542`). Testy `run_*` przepisane na funkcje publiczne albo prywatne `_run_*`.
- [ ] **Step 2: Implementacja**; CLI wola funkcje publiczne. Errata decyzji 9 planu 2/3 zapisywana w Task 16. Brama.
- [ ] **Step 3: Commit** — `feat(cz)!: publiczne API arkusza CZ i wycinek CZ w ksztalcie pobranie/sprawdzenie (R4)`

---

### Task 8: LAZ — obszar w dowolnym CRS, `plan=`, `check_laz_area`

**Files:**
- Modify: `kartograf/download/laz.py` (`check_laz_updates` 188, `run_laz_download` 214, `download_laz_area` 338-442), `kartograf/providers/pl/gugik_laz.py` (wymog EPSG:2180 zostaje wewnatrz providera), `kartograf/__init__.py` (+ `check_laz_area`; bez `run_laz_download`, `check_laz_updates`), `kartograf/cli/download_cmd.py` (`_resolve_laz_bbox` 2273-2304 -> biblioteka, `_laz_parent_request` 2307-2321, `_print_laz_superseded` 2327-2340, `_cmd_download_laz` 2346-2480)
- Test: `tests/test_laz_download.py`, `tests/test_cli.py` (`TestCmdDownloadLaz` 4266-4834, testy `_resolve_laz_bbox` 4841-4950)

**Interfaces:**
```python
def download_laz_area(bbox, *, output_dir, vertical_crs, year=None, min_year=None, max_year=None,
                      all_campaigns=False, min_density=None, update=None, plan=None, workers=1,
                      parent_request=None, cache=True, on_progress=None, on_notice=None,
                      provider=None, tolerance_m=...) -> LazDownloadResult: ...
def check_laz_area(bbox, *, output_dir, vertical_crs, year=None, min_year=None, max_year=None,
                   all_campaigns=False, min_density=None, cache=True, on_notice=None) -> UpdatePlan: ...
# LazDownloadResult: + notices
```

- [ ] **Step 1: Testy** — `test_bbox_epsg4326_same_tiles_as_2180` (przeliczenie jak `_resolve_laz_bbox`), `test_bbox_epsg5514_uses_pinned_transform`, `test_check_laz_area_same_args`, `test_download_laz_area_plan_stale`, `test_superseded_notice` (tekst `download_cmd.py:2332-2334`), `test_no_tiles_is_no_coverage_error` (tekst `NO_TILES_MESSAGE`), `test_workers_param_name`.
- [ ] **Step 2: Implementacja** (decyzje 8, 9). Brama.
- [ ] **Step 3: Commit** — `feat(laz)!: LAZ w dowolnym CRS obszaru, plan= i check_laz_area`

---

### Task 9: Land cover — `download`/`check` poziomu komendy (S3, R7 w bibliotece)

**Files:**
- Modify: `kartograf/landcover/manager.py` (`LandCoverResult` 106, `LandCoverAreaResult` 131, `__init__` 219, `download` 314, `download_by_*` 379-443, `download_all_counties` 444, `check` 496, `check_all_counties` 519, `download_batch` 537), `kartograf/landcover/store.py:84-87` (przeliczenie bbox przed slotem), `kartograf/__init__.py`, `kartograf/cli/landcover_cmd.py` (`_landcover_task` 260-318: wybor "wszystkie powiaty" i `Info:` CORINE -> biblioteka)
- Test: `tests/test_landcover.py`, `tests/test_landcover_output_params.py`, `tests/test_cli_landcover_hsg.py`, `tests/test_cli.py` (`TestCmdLandcoverDownload` 2719-3019)

**Interfaces:**
```python
class LandCoverManager:
    def __init__(self, output_dir, provider, cache: MetadataCache | bool = True): ...
    def download(self, *, teryt=None, sheet=None, bbox=None, geometry: Path | None = None, layer=None,
                 update=None, plan=None, workers: int = 1, on_notice=None, **options) -> LandCoverAreaResult: ...
    def check(self, *, teryt=None, sheet=None, bbox=None, geometry=None, layer=None,
              on_notice=None, **options) -> UpdatePlan: ...
# LandCoverAreaResult: files, failed, stale, notices, ok
```

- [ ] **Step 1: Testy** — `test_bdot_bbox_downloads_every_county` (2 powiaty z atrapy PRG -> 2 elementy, jak dzis CLI), `test_bdot_one_county_failure_others_downloaded_ok_false`, `test_teryt_single_element`, `test_soilgrids_bbox_epsg4326` (wersja w tym samym slocie co bbox przeliczony do 2180), `test_geometry_envelope_selection` (obwiednia jak `get_overall_bbox`), `test_geometry_gpkg_many_layers_notice` (`GEOMETRY_LAYER_DEFAULT`, tekst `download_cmd.py:222-224`), `test_corine_preview_notice` (tekst `landcover_cmd.py:277-281`), `test_workers_parallel_counties` (atrapa liczy rownolegle wywolania <= `workers`), `test_check_matches_download_selection`; testy `download_all_counties`/`check_all_counties`/`download_by_*`/`download_batch` przepisane na `download`/`check` albo usuniete (duplikaty). CHANGELOG (Task 16): usuniete `download_by_*`, `download_batch` z "Co zrobic".
- [ ] **Step 2: Implementacja** (decyzja 11); CLI: jedno wywolanie `download`/`check`, wypisanie `files`/`failed`/`stale`, kod z `ok`. Brama.
- [ ] **Step 3: Commit** — `feat(landcover)!: LandCoverManager.download/check jako funkcje poziomu komendy (S3)`

---

### Task 10: HSG — `calculate_hsg`/`check_hsg`, bez `stat` (R3, S4)

**Files:**
- Modify: `kartograf/hydrology/hsg.py` (`HsgResult` 377, `HSGCalculator` 393-740, `_input_plan` 905), `kartograf/landcover/store.py:49-51` (`hsg_segment` bez zmian sciezki), `kartograf/__init__.py`, `kartograf/cli/soilgrids_cmd.py` (95-210)
- Test: `tests/test_hsg.py`, `tests/test_cli_landcover_hsg.py`, `tests/test_cli.py` (`TestCmdSoilgrids` 3020-3254)

**Interfaces:**
```python
class HSGCalculator:
    def __init__(self, output_dir, provider=None, cache: MetadataCache | bool = True): ...
    def calculate_hsg(self, *, sheet=None, bbox=None, geometry=None, layer=None, depth: str,
                      update=None, plan=None, timeout: int = 120, on_notice=None) -> HsgResult: ...
    def check_hsg(self, *, sheet=None, bbox=None, geometry=None, layer=None, depth: str,
                  on_notice=None) -> UpdatePlan: ...
# HsgResult: + notices, ok
```

- [ ] **Step 1: Testy** — `test_calculate_hsg_bbox_and_sheet_and_geometry`, `test_stat_argument_rejected` (`TypeError`), `test_hsg_segment_unchanged_after_stat_removal` (magazyn z wersja HSG zapisana przed zmiana — fixtura katalogu z `hsg/global_soilgrids_0-5cm_mean/` -> `reused`), `test_bbox_any_crs`, `test_check_hsg_items`, `test_exactly_one_selection`.
- [ ] **Step 2: Implementacja** (decyzja 10); CLI: jedno wywolanie. Brama.
- [ ] **Step 3: Commit** — `feat(hsg)!: calculate_hsg/check_hsg z sheet/bbox/geometry, HSG zawsze ze statystyki mean (R3)`

---

### Task 11: `download_data` / `check_data` (R1, R5, R11)

**Files:**
- Create: `kartograf/download/options.py`, `kartograf/download/area.py`, `kartograf/download/data.py`; testy `tests/test_download_options.py`, `tests/test_download_area.py`, `tests/test_download_data.py`
- Modify: `kartograf/__init__.py` (+ `download_data`, `check_data`, `DataReport`, `UnitFile`, `UnitFailure`, `get_overall_bbox`, `transform_bbox`, `parent_request_for`)

**Przeniesienie z `kartograf/cli/download_cmd.py` (linie):**

| Do | Z |
|---|---|
| `options.py` | `_check_country_value_syntax` 300-321, `_country_value` 323-337, `_per_country_hint` 339-344, `_pl_option_error` 346-452, `_cz_option_error` 455-493, `_reject_laz_only_opts` 495-508, `_reject_full_sheet_for_laz` 510-520, `_reject_campaign_opts_without_pl` 522-550, `_reject_campaign_opts_with_target_crs` 552-594, `_reject_non_nmt_for_cz` 273-283, rok wylaczny/granice 1216-1236, kraj godla vs `--country` 1250-1262, `--target-crs` z `--sheet` 1278-1284, `_pl_target_scale` 636-643 |
| `area.py` | `_area_outside_extents` 693-741, `_print_clipping_info` 742-804 (-> `Notice`), `_build_parent_request` 806-823 (-> `parent_request_for`), `_validate_cross_country` 829-862, `_pl_only_flags` 864-893, `_resolve_cz_geometry_bbox` 1019-1057, `_geometry_envelope` 1059-1093, `_announce_geometry_layer` 199-229 (-> `Notice`), `_resolve_laz_bbox` (Task 8) |
| `data.py` | `_dispatch_area` 895-1016, `_cmd_download` 1162-1432 (bez parsowania), `_download_pl_bbox` 2161-2198, `_download_pl_sheet_list` 2201-2270, `_download_pl_geometry` 2744+, `_cmd_download_cz` 2602-2690, `_cmd_download_laz` 2346-2480, `_finish_pl_sheets` 1715-1803 (-> `ok` + `Notice`), `_print_coverage_hints` 1680-1701, `_warn_unverified` 1703-1712, `_print_better_coverage` 1854-1907, `_print_link_outside_range` 1918-1947, `_warn_crs_mismatch_sheets` 2000-2018, `_warn_partial_sheets` 2040-2084, `_info_legacy_campaigns` 1459-1476, `_info_newer` 1638-1649, `_create_provider_and_storage` 129-173 |

Bledy wejscia: dzisiejsze teksty `Error: <tekst>` z tych funkcji staja sie `ValidationError(<tekst>)` (CLI wypisuje je przez `main`, `commands.py:98-102` — ten sam tekst i kod 1).

**Interfaces:** spec 4.1; dodatkowo `on_notice` (decyzja 3). `UnitFile(unit, country, file)`, `UnitFailure(unit, country, error, kind)`, `DataReport(files, failed, stale, superseded, notices, ok)`.

- [ ] **Step 1: Inwentaryzacja komunikatow** — tabela w docstringu modulu `data.py`: kazdy `Info:`/`Warning:` z `download_cmd.py` -> kod `Notice` + warunek (decyzja 4); kazdy `Error:` -> `ValidationError` (wejscie), `UnitFailure` (jednostka) albo `ok=False`.
- [ ] **Step 2: Testy `options.py`** — przeniesione z `tests/test_cli.py` testy walidacji (`_resolve_pl_options` od 1978, grupy `--system`/`--scale`/`--resolution`/`--vertical-crs`/per kraj/lata/`--target-crs`) jako testy `validate_*` z tymi samymi tekstami; asercje na `ValidationError` zamiast stderr.
- [ ] **Step 3: Testy `area.py`** — przeniesione z `TestAutoSplitBBox` (7069-8100): kraje, zawezenie `auto -> pl`, przyciecie (`Notice`), `parent_request_for`, obwiednia geometrii PL/CZ.
- [ ] **Step 4: Testy `data.py`** — scenariusze z `TestCmdDownload` (654-1130), `TestCmdDownloadBBox` (2004-2450), geometrii, LAZ, CZ, wycinkow, `--check-updates`/`--upgrade --plan`, kampanii — z atrapami `kartograf.download.data.*` zamiast `kartograf.cli.download_cmd.*`; asercje na `DataReport` (`files`, `failed`, `notices` kod+tekst, `ok`). `test_check_data_auto_one_merged_plan` (PL+CZ jak `run_with_plan_file` 1132-1137), `test_partial_success_auto_ok_true_with_notice`, `test_explicit_country_failure_ok_false`.
- [ ] **Step 5: Implementacja** — `download_data`/`check_data` skladaja funkcje torow z Task 5-8; `cache` przez `open_cache` (jeden na wywolanie, przekazywany do providerow). Brama (CLI jeszcze uzywa starego kodu — oba zestawy testow zielone).
- [ ] **Step 6: Commit** — `feat(download): download_data/check_data - logika komendy download w bibliotece (R1, R5, R11)`

---

### Task 12: CLI `download` jako tlumacz (Z1)

**Files:**
- Modify: `kartograf/cli/download_cmd.py` — zostaja: `_ProgressPrinter`/`create_progress_callback` 60-122, `_error_lead` 124-126, parsowanie flag -> kwargs, `run_with_plan_file`/`_PlanContext` 1095-1138, `_report_plan`/`_plan_line`/`_report_stale` 1478-1523, `_status_lines`/`_report_file`/`_unit_of`/`_print_version_summary` 1558-1637, `_print_transform_error` 674-686, `_print_sheet_list` 257-271 (naglowek listy arkuszy na stdout: biblioteka emituje `Notice` `SHEET_LIST` z lista godel przed pobraniem, CLI wypisuje go w dzisiejszym formacie na stdout, `-q` ukrywa — prezentacja, nie wybor danych); reszta usunieta (przeniesiona w Task 11). `kartograf/cli/commands.py`.
- Create: `tests/test_parity.py` (scenariusze `download`)
- Test: `tests/test_cli.py` (przepisany: tlumaczenie), `tests/test_cli_update_modes.py`

- [ ] **Step 1: Testy tlumaczenia** — `test_flags_map_to_download_data_kwargs` (parametryzowany po kazdej fladze `download --help`: atrapa `download_data` dostaje odpowiedni argument; `--bbox` + `--bbox-crs` -> `BBox(..., crs)`; `pl=..,cz=..` -> `dict`), `test_check_updates_calls_check_data_and_writes_plan`, `test_report_ok_false_exit_1`, `test_notices_printed_once_on_stderr_in_order`, `test_validation_error_single_error_line`, `test_cli_imports_no_data_logic` (Review Focus 2).
- [ ] **Step 2: Testy zgodnosci** (`tests/test_parity.py`, `frozen_clock`, atrapy HTTP z `tests/conftest.py`/`tests/fixtures/`): arkusz PL-1992 1:10000; godlo grubsze; PL-2000 ze `scale`; obszar PL `system=1992` i `2000`; `geometry` PL; kampanie (`all_campaigns`, `min_year`, `full_sheet`); wycinek PL; arkusz CZ SM5 i TM33; wycinek CZ; `country="auto"` (PL+CZ, zawezenie, czesciowy sukces); LAZ (EPSG:4326, `min_density`); `check` + plan + `upgrade` (takze nieaktualny plan). Kazdy: `assert_same_store`, te same statusy, `notices` = linie `Info:`/`Warning:` CLI, kod CLI = `ok`.
- [ ] **Step 3: Implementacja** — `_cmd_download` = parsowanie + `download_data`/`check_data` + wypisanie; usuniecie przeniesionych funkcji (Task 11) i ich testow z `tests/test_cli.py` (zostaja w testach biblioteki). Brama; liczba testow offline po przeniesieniu nie spada ponizej stanu sprzed Task 11 minus testy usunietych duplikatow (zapisz liczby w opisie commitu).
- [ ] **Step 4: Smoke offline** — `.venv/bin/kartograf download --help`; brak `--product` / `--output` / `--vertical-crs` -> `Error:` z lista wartosci, kod 1, przed siecia.
- [ ] **Step 5: Commit** — `refactor(cli)!: kartograf download tylko tlumaczy flagi na download_data (Z1)`

---

### Task 13: CLI `landcover`/`soilgrids` jako tlumacz + flagi R7

**Files:**
- Modify: `kartograf/cli/_parser.py` (landcover download ~418-501: `--layers`, `--keep-raw`, `--bbox-crs`, `--workers`, `--quiet`; soilgrids hsg ~535-607: `--bbox-crs`, `--quiet`), `kartograf/cli/landcover_cmd.py`, `kartograf/cli/soilgrids_cmd.py`
- Test: `tests/test_cli_landcover_hsg.py`, `tests/test_cli.py` (`TestCmdLandcoverDownload`, `TestCmdSoilgrids`), `tests/test_parity.py` (scenariusze land cover/HSG)

- [ ] **Step 1: Testy** — `test_layers_flag_comma_list` (`--layers SWRS,PTWP` -> `layers=("SWRS","PTWP")`; zly kod -> `Error:` z `normalize_layers`), `test_keep_raw_flag`, `test_bbox_crs_landcover_and_hsg`, `test_workers_landcover`, `test_quiet_suppresses_status_lines_not_notices`; zgodnosc: BDOT10k `teryt`, BDOT10k obszar wielu powiatow, CORINE (CLMS i podglad), SoilGrids, HSG `bbox` i `geometry`, `check` + plan.
- [ ] **Step 2: Implementacja** — jedno wywolanie biblioteki na komende; `--quiet` jak w `download` (stdout bez linii statusu, stderr z `Notice`). Brama.
- [ ] **Step 3: Commit** — `feat(cli)!: landcover i soilgrids hsg tylko tlumacza; --layers, --keep-raw, --bbox-crs, --workers, --quiet (R7)`

---

### Task 14: Jezyk polski ASCII (Z5, R9)

**Files:**
- Modify: `kartograf/cli/_parser.py` (opisy i `help` po angielsku: `--sheet`, `--bbox`, `--bbox-crs`, `--quiet`, `--min-density`, `--geometry`, `--layer`, `--workers`, `--teryt`, opisy komend `parse`, `download`, `landcover`, `soilgrids`, `cache` i podkomend; `metavar`: `PLIK`, `KATALOG`, `GODLO`, `BBOX`, `ROK`, `N`, `NAZWA`, `KOD`), `kartograf/cli/*.py` (komunikaty i postep po angielsku: m.in. `Must provide one of`, `File not found`, `No sheets found`, `Downloading ...`, `Skipped ...`, `tiles`, `Legend:`), teksty wyjatkow po angielsku w `kartograf/**` (providery: `Invalid ...`, `Unsupported ...`, `BBox must be ...`; `core/geometry.py`), 141 literalow z diakrytykami albo znakami spoza ASCII (`cli/download_cmd.py` 39 — glownie `—`, `°`, `↓`; `core/sheet_parser.py` 21; `providers/pl/bdot10k.py` 9; `cli/_parser.py` 8; `sources/registry.py` 7; `providers/pl/gugik_laz.py` 7; `providers/cuzk/dmr.py` 7; reszta <= 6 na plik). Literaly, ktore sa danymi (nazwy z odpowiedzi serwera, wzorce dopasowania tekstu GUGiK/CUZK w `sources/registry.py`, `skorowidz.py`), zostaja — kazde takie miejsce opisane komentarzem.
- Create: `tests/test_cli_language.py`
- Test: testy z `match=`/asercjami na tekscie (inwentaryzacja w Step 1)

- [ ] **Step 1: Inwentaryzacja** — skrypt jednorazowy (AST: literaly `str` poza docstringami z `ord(ch) > 127` albo bez polskiego slownika w `help`/`print`/`raise`); lista miejsc i testow do zmiany w opisie commitu.
- [ ] **Step 2: Testy** — `test_help_of_every_command_is_ascii` (rekurencyjnie po `create_parser()` podparserach: `format_help()` ASCII), `test_error_paths_are_ascii_polish` (parametryzowane reprezentatywne bledy wejscia CLI i biblioteki: tekst ASCII; slowa kluczowe po polsku, np. `wymagane`, `nie`, `dostepne`); ASCII `Notice` pilnuje juz Task 3.
- [ ] **Step 3: Implementacja** — tlumaczenia; myslnik `—` -> `-`, `°` -> ` st.` albo `deg`, strzalka paska postepu -> ASCII; STANDARDS 9.4: regula Z5. Brama.
- [ ] **Step 4: Commit** — `refactor(cli)!: pomoc, komunikaty i bledy po polsku w ASCII (Z5)`

---

### Task 15: Kompletnosc testow zgodnosci (Z7)

**Files:** `tests/test_parity.py`

- [ ] **Step 1:** Tabela spec 6 vs testy (w docstringu modulu): kazdy wiersz ma test; brakujace dopisac. Bledy wejscia: brak wymaganej wartosci, zla wartosc, obszar poza krajami — ten sam typ i tekst (CLI: `Error: <tekst>`).
- [ ] **Step 2:** Mutacja kontrolna (jednorazowo, bez commitu): zmiana jednego tekstu `Notice` tylko w CLI albo pominiecie `parent_request` w jednej sciezce -> co najmniej jeden test zgodnosci czerwony.
- [ ] **Step 3:** Brama. **Commit** — `test(parity): komplet scenariuszy zgodnosci CLI = API (spec 6)`

---

### Task 16: Dokumentacja

**Files:**
- Modify: `docs/DECISIONS.md` (CRLF: ADR-037 "Spojnosc CLI i API" z Z1-Z7 i S1-S6; errata ADR-036 / decyzji 9 planu 2/3: arkusz CZ publiczny; indeks), `docs/DEVELOPMENT_STANDARDS.md` (9.4 Z5, 11 Z4 — jesli nie w Task 2/14 — nowa sekcja "CLI tylko tlumaczy" Z1-Z3), `docs/ARCHITECTURE.md` (2 moduly, 4.1-4.8: `download_data`, tory, `Notice`, cache), `docs/USAGE.md` (biblioteka: `download_data`, `check_data`, `download_cz_sheet`, `LandCoverManager.download`, `calculate_hsg`; flagi R7; cache), `README.md` (przyklad `download_data`), `kartograf/__init__.py` (docstring modulu 1-50), `docs/CHANGELOG.md` (`[0.8.0]`), `docs/SCOPE.md`, `docs/PRD.md` (jesli opisuja API)
- [ ] **Step 1: CHANGELOG [0.8.0] BREAKING z "Co zrobic"** — wyniki arkuszy PL (`DownloadResult` z wartosci zwracanej zamiast `last_result`; Hydrograf `scripts/download_dem.py`), `check_updates`/`upgrade` -> `check_sheets`/`download_sheets(plan=)`, `max_workers` -> `workers`, kroki wewnetrzne poza API (`prepare_pl_cutout`, `run_*`, `PlCutout`, `check_laz_updates`, `UpgradeReport`, `SheetFetch`), `target_crs` keyword-only, `check_cz_cutout`/`check_pl_cutout` nowe argumenty, `LandCoverManager.download` -> `LandCoverAreaResult` (Hydrograf `scripts/download_landcover.py`, `core/cn_calculator.py`), usuniete `download_all_counties`/`download_by_*`/`download_batch`, HSG `calculate_hsg`/`check_hsg` bez `stat` (Hydrograf `core/cn_calculator.py`, `scripts/bootstrap.py`), `ValidationError` zamiast `ValueError`, domyslny cache w cwd (`cache=False` wylacza), komunikaty CLI po polsku ASCII; dodane: `download_data`, `check_data`, `Notice`, `download_cz_sheet`, `check_laz_area`, `get_overall_bbox`, `transform_bbox`, flagi R7.
- [ ] **Step 2:** Pozostale pliki; CRLF `docs/DECISIONS.md`: `.venv/bin/python -c "b=open('docs/DECISIONS.md','rb').read().split(b'\n'); print([i for i,l in enumerate(b[:-1],1) if not l.endswith(b'\r')][:5])"` -> `[]`. Przyklady Pythona z dokumentacji sprawdzone skryptem jednorazowym (sygnatury + pola wynikow), przyklady CLI przez `create_parser().parse_args` (jak w raporcie).
- [ ] **Step 3: Commit** — `docs: spojnosc CLI i API (ADR-037, CHANGELOG [0.8.0], USAGE, ARCHITECTURE)`
- [ ] **Step 4: PROGRESS** — sesja, stan planu, nastepny krok (Task 17-18), pozycja backlogu "Spojnosc CLI, biblioteki i API" zamknieta.

---

### Task 17: Weryfikacja na zywo

**Files:** `docs/research/<data>-cli-api-consistency-live/raport.md` (NOWY; sciezka danych jako `<katalog-danych>`)

Katalog danych: od uzytkownika (zapytaj na poczatku zadania). Kazdy scenariusz dwa razy: CLI do `<katalog-danych>/.../cli`, skrypt biblioteki do `.../api`, ta sama minuta; porownanie drzew (`sha256` plikow, sidecary bez `downloaded_at`, bo zegar nie jest zamrozony).

- [ ] **Step 1:** Arkusz PL NMT 1 m; obszar PL `--system 1992`; wycinek PL `--target-crs EPSG:2180`; arkusz CZ SM5; `--country auto` na pograniczu; LAZ maly bbox w EPSG:4326; BDOT10k obszar 2 powiatow; SoilGrids; HSG `--geometry`; `--check-updates --plan` -> `--upgrade --plan`.
- [ ] **Step 2:** Raport (komendy, kody, roznice = 0 poza czasem), commit `docs(research): weryfikacja na zywo spojnosci CLI i API`. Kazda niezgodnosc: test odtwarzajacy, poprawka, osobny commit.

---

### Task 18: Galaz do `develop`

- [ ] **Step 1:** `git rebase develop`, pelna brama.
- [ ] **Step 2:** Za zgoda uzytkownika: merge `--no-ff` do `develop`; push wylacznie za zgoda.
- [ ] **Step 3: PROGRESS** — przed wydaniem 0.8.0: Hydrograf/Hydrolog wg CHANGELOG [0.8.0] "Co zrobic".
