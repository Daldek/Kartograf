# Manifest projektu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-15

**Goal:** Grupa `kartograf project` i publiczne API projektu wg specu:
plik `kartograf-project.json` (`kartograf-project/1`) z zadaniami (komendy
danych grup ADR-039 z opcjami) i przypietymi wersjami plikow (SHA-256);
komendy `init`, `add`, `remove`, `download` (z `--check-updates`,
`--upgrade`, `--force`), `status`, `verify`; odtwarzanie danych tylko przy
identycznych sumach; bez SQLite i bez blokad zakresow bajtow.

**Architecture:** Nowy pakiet `kartograf/project/`: `model.py`
(dataclassy manifestu i wynikow), `commands.py` (tabela komend danych:
pobranie, `check_*`, walidacja bez sieci, opcje JSON <-> argumenty
biblioteki, adaptery rodzin wyniku), `manifest.py` (odczyt i scisla
walidacja, zapis atomowy, blokada `mkdir`, scalanie per zadanie),
`operations.py` (osiem funkcji API). CLI: `kartograf/cli/groups/project.py`
(rejestracja grupy, ADR-039 D2) i `kartograf/cli/project_cmd.py`
(tlumaczenie i wydruk); komendy danych grup dostaja `_task` - to samo
tlumaczenie flag, ktorego uzywa `_handler`. W bibliotece danych: walidacja
bez sieci wydzielona z prologow `download`/`check` oraz krotki produktow
i zrodel grup przeniesione z CLI do biblioteki.

**Spec:** `docs/superpowers/specs/2026-10-15-manifest-projektu-design.md`
(decyzje M1-M12, sekcje 3-7); ADR-040. Kontrakty: ADR-036 (magazyn), ADR-037
(CLI = API), ADR-039 (grupy).

**Galaz:** `feat/project-manifest` z aktualnego `develop` (grupy ADR-039
scalone w `dd5641b`). Integracja do `develop` - koordynator.

---

## Global Constraints

- Python z `.venv` uruchamiany z korzenia worktree; brama przed kazdym
  commitem: `python -m pytest tests/ -m "not live" -q`, `python -m ruff
  check .`, `python -m ruff format --check .`, `python -m mypy kartograf/
  tests/`. Conventional Commits po polsku, autor `Daldek
  <git@debever.pl>` bez `Co-Authored-By`; commit wylacznie przez straznik
  wzorcow `! git diff --cached -U0 | grep '^+' | grep -qiEf
  "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit ...`
  (brak pliku wzorcow = zatrzymaj sie i zapytaj). Angielskie identyfikatory
  i docstringi; teksty `Notice` i wyjatkow po polsku ASCII (Z5);
  `ValidationError` dla wejscia i manifestu, `DownloadError` dla zrodla
  (STANDARDS 11); CRLF w `docs/DECISIONS.md`.
- Testy zachowania, nie okablowania: prawdziwy magazyn w `tmp_path`
  budowany prawdziwymi funkcjami biblioteki z fake'ami providerow
  z istniejacych testow (lista nizej). `tests/conftest.py::_block_network`
  (autouse) dowodzi braku sieci; `frozen_clock` ustala `pinned_at`.
  Asercje na statusach, `Notice.code`, bajtach plikow, przypieciach
  i typach wyjatkow - nie na tekstach komunikatow (wyjatek: testy
  zgodnosci CLI = API, ktore porownuja tekst CLI z tekstem wyjatku API).
- Zadnej bazy SQLite w katalogu projektu ani w magazynie: operacje
  projektu domyslnie `cache=False` (spec M12).
- Format sidecara `kartograf-meta/1`, plan `kartograf-plan/1` i zachowanie
  magazynu (ADR-036) bez zmian.
- Dane live wylacznie poza repo i `/tmp` (`<katalog-danych>`), z jawnym
  `--output` przy `project init`; sciezki danych nie trafiaja do repo.

**Fixtury offline (istniejace na `develop` dd5641b):**
- arkusze PL: `tests/test_manager_campaigns.py::FakeCampaignProvider`,
  `REC`, `C14_ALL`; `tests/test_parity.py::AnySheetProvider`, `_pl_store`
  (patch `kartograf.download.data._create_provider_and_storage`);
- LAZ: `tests/test_cli_update_modes.py::LazCliProvider`;
- CZ: `tests/test_cli.py::_cz_provider_mock` (patch
  `kartograf.providers.cuzk.create_dmr_provider`, jak w
  `tests/test_parity.py`);
- land cover: `tests/test_parity_landcover.py::_providers`, `_bdot`;
  `tests/test_landcover_output_params.py::FakePackages`;
  `tests/conftest.py::FakeSoilGrids`, `FakeCorine`;
- HSG: `tests/test_hsg.py::RasterSoilGrids`;
- CLI = API: `tests/parity.py::run_both`, `assert_same_store` (wzor
  harnessu dla komend `project`).

Wspolne fixtury projektu (magazyn z jednym przypietym zadaniem PL, pusty
magazyn, drugi projekt) umiesc w `tests/project_fixtures.py` (modul
pomocniczy jak `tests/parity.py`), nie kopiuj ich miedzy plikami testow.

## Decyzje implementacyjne (bez nowych decyzji produktowych)

1. **Model** (`kartograf/project/model.py`): zamrozone dataclassy
   `PinnedFile`, `ProjectTask`, `Project`, `TaskResult`, `ProjectReport`,
   `FileCheck`, `ProjectCheck` oraz aliasy `PinRole`, `TaskOutcome`,
   `PinStatus` - pola i znaczenie dokladnie wg specu 4.3.
   `ProjectTask.options` i `geometry_sha256` w postaci JSON opakowane
   w `types.MappingProxyType`.
2. **Postac JSON opcji** (`commands.py`): `BBox` <-> `"bbox": [min_x,
   min_y, max_x, max_y]` + `"bbox_crs"`; `Path` <-> napis (regula sciezek
   specu 3.2 stosowana w `operations.py`); mapa per kraj <-> obiekt;
   sekwencja (`layers`) <-> lista; `None` i `False` pomijane.
   `options_to_json(command, options) -> dict` i `options_from_json(command,
   data, *, project_dir) -> dict` (argumenty biblioteki, sciezki
   wzgledne rozstrzygniete wzgledem `project_dir`).
3. **Tabela komend** (`commands.py`): `TaskCommand(name: str, options:
   Mapping[str, OptionKind], validate, download, check, files)` - KOREKTA:
   `options` to klucze JSON (flagi danych komendy, z `bbox_crs`) z rodzajem
   wartosci (`str`, `int`, `flag`, `bbox`, `bbox_crs`, `path`,
   `per_country`, `str_list`), wiec pozycja sama opisuje typy do walidacji
   odczytu (`check_options_json`) i konwersji; pozycje buduja fabryki
   `_data_command`, `_landcover_command`, `_hsg_command`;
   `COMMANDS: Mapping[str, TaskCommand]` z pozycjami `elevation download`,
   `imagery download`, `landcover download`, `soil download`, `soil hsg`
   (spec 5). Sygnatury:
   `validate(output_dir: Path, options: dict) -> None` (bez sieci,
   `ValidationError`), `download(output_dir, options, /, *, update, cache,
   on_progress, on_notice) -> object`, `check(output_dir, options, /, *, cache,
   on_notice) -> UpdatePlan` (protokoly `TaskDownload`/`TaskCheck`),
   `files(result) -> TaskFiles`, gdzie
   `TaskFiles(complete: bool, files: tuple[tuple[PinRole, str,
   VersionedFile], ...], errors: tuple[str, ...])` realizuje regule
   pelnego sukcesu specu 4.6; `unit_report_files` (protokol `UnitReport`:
   `files[].unit/file`, `failed[].error`, `ok`) obsluguje `DataReport`
   i raporty kolekcji planu C bez zmian. `on_progress` przekazywany tylko
   funkcjom, ktore go przyjmuja (dzis `download_data`). `model.py`
   (decyzja 1) powstaje w Task 2, bo tabela uzywa `PinRole`.
4. **Produkty i zrodla grup w bibliotece:** `ELEVATION_PRODUCTS = ("nmt",
   "nmpt", "laz")` i `IMAGERY_PRODUCTS = ("orto",)` w
   `kartograf/download/options.py`, `LANDCOVER_SOURCES = ("bdot10k",
   "corine")` w `kartograf/landcover/manager.py`. Dzisiejsze
   `cli/groups/elevation.py::PRODUCTS`, `cli/groups/imagery.py::PRODUCTS`
   i `cli/groups/landcover.py::SOURCES` importuja je (jedna lista; plany
   A/E dopisuja produkty wylacznie tam). Pozycja tabeli odrzuca produkt
   albo zrodlo spoza swojej komendy tymi samymi funkcjami co CLI:
   `options.py::require_product(product, products)` (tekst "--product
   wymagane: ..." grupy) i `manager.py::require_landcover_source(source)`
   (opis zrodel `LANDCOVER_SOURCE_CHOICES` przeniesiony z CLI).
5. **Walidacja bez sieci** wydzielona z prologow funkcji pobrania
   (jedno miejsce, bez zmiany tekstow i kolejnosci bledow):
   `kartograf/download/data.py::validate_data_request(**selection)` -
   KOREKTA wzgledem pierwszej wersji planu (`validate_request(_task(...))`
   nie lapie m.in. braku `vertical_crs` arkusza ani CZ bez rozdzielczosci:
   te reguly sa w galeziach `_execute`): ten sam `_execute` z `_Run(dry=True)`,
   w ktorym kazdy tor konczy sie tuz przed pierwszym zapytaniem do zrodla
   (`_download_pl_sheet`, `_download_pl_sheet_list`, `_download_pl_cutout`,
   `_download_cz`, `_download_laz`); czytany jest tylko plik geometrii.
   `LandCoverManager.validate_request(*, teryt=None,
   sheet=None, bbox=None, geometry=None, layer=None, **options)` (=
   `_validated`: `validate_request_bbox` + `_check_options` + `_selection`
   z prologu `download`/`check`; do `_selection` przeniesione z `_jobs`
   "teryt tylko dla BDOT10k" i dodane parsowanie godla - ten sam blad co
   wczesniej, tylko przed otwarciem cache), `HSGCalculator.validate_request(*,
   sheet=None, bbox=None, geometry=None, layer=None, depth)` (= `_validated`:
   `_selection` + `validate_request` menedzera SoilGrids dla wejscia, uzywane
   tez przez `calculate_hsg`/`check_hsg`). Metody nie
   wchodza do `__all__` jako nowe nazwy (sa metodami klas juz
   eksportowanych); `validate_data_request` zostaje wewnetrzna.
6. **PinnedFile z wyniku:** `path = VersionedFile.path.relative_to(store)`,
   `version = VersionedFile.version_path.relative_to(store)` (oba
   `as_posix()`), `label`, `sha256`; `size_bytes` z sidecara wersji
   odczytanego `kartograf/download/versions.py::read_version(version_path.parent,
   version_path.name)`; `None` (brak albo zly sidecar) = blad zadania.
   Deduplikacja po `version` z zachowaniem kolejnosci wyniku.
7. **Zapis manifestu** (`manifest.py`): `json.dumps(doc, indent=2,
   ensure_ascii=False) + "\n"`, kolejnosc kluczy jak w specu 3.3.
   Zapis: plik tymczasowy `kartograf-project.json.<host>_<pid>.tmp`
   w katalogu projektu, `flush` + `os.fsync`, `os.replace`, `fsync`
   katalogu (bledy `EINVAL`/`ENOTSUP`/`EBADF` przy katalogu ignorowane;
   na Windows pomijane). Blokada: `os.mkdir(".kartograf-project.lock")`
   + plik `owner` z `host pid czas`; ponawianie co 0,1 s do 5 s, potem
   `ValidationError` (spec 4.11); zwolnienie w `finally`; brak
   przejmowania cudzej blokady.
8. **Scalanie per zadanie:** `commit_tasks(project_dir, changes:
   Mapping[str, tuple[dict | None, dict | None]]) -> tuple[str, ...]` -
   para (stan zadania z odczytu operacji, stan nowy; `None` = brak
   zadania) per nazwa. Pod blokada ponowny odczyt; zadanie, ktorego stan
   biezacy rozni sie od stanu z odczytu, jest konfliktem (zwrocone
   nazwy, nic dla niego nie zapisano); pozostale zmiany jednym
   `os.replace`. Kolejnosc zadan: istniejace na swoich miejscach, nowe na
   koncu. Ta sama funkcja obsluguje `add`, `remove` i zapisy po kazdym
   zadaniu `download`.
9. **Walidacja odczytu** (`manifest.py::read_manifest`): JSON, `schema`,
   komplet i typy kluczy, nazwy zadan (`^[a-z0-9][a-z0-9_-]{0,63}$`,
   unikalne), `command` w `COMMANDS`, klucze `options` w
   `TaskCommand.options`, `pinned_at` i `kartograf_version` razem `null`
   albo razem napisy, `geometry_sha256` dokladnie gdy `options.geometry`
   i zadanie przypiete, przypiecia: `path`/`version` wzgledne, bez `.`
   i `..`, `version` z segmentem `versions` i bez `.incoming`, `path` bez
   `versions`, `sha256` = 64 male znaki hex, `size_bytes` >= 0, `role`
   ze slownika. Komunikat wskazuje miejsce (`zadanie teren: files[2].version: ...`).
10. **Mapowanie planu na przypiecia** (`operations.py`, spec 4.8): klucz
    pozycji `PurePosixPath(item.segment, item.hierarchy, item.name).as_posix()`
    porownany z `PinnedFile.path`. W obrebie klucza najpierw pary
    o rownej etykiecie (`pin.label` rowne `item.available_label` albo
    `item.local_label`), potem jedna pozostala pozycja z jednym pozostalym
    przypieciem; reszta pozycji -> `added`, reszta przypiec -> `removed`.
    Status pary: przypieta wersja nie istnieje -> `missing`;
    `item.status == "check_failed"` -> `check_failed`;
    `item.local_sha256 == pin.sha256` -> `current`/`unverifiable` wg
    `item.status`, a `newer`/`missing` -> `newer`; inaczej -> `newer`.
    Wyjatek `DownloadError` z calego `check_*` -> kazde przypiecie
    zadania `check_failed` z przyczyna.
11. **Geometria:** `geometry_sha256` liczona
    `kartograf/sources/sidecar.py::file_digest` dla pliku GPKG albo
    istniejacych `.shp`, `.shx`, `.dbf`, `.prj` przy kazdym zapisie
    przypiec. Odtworzenie wymaga zgodnosci (spec 4.6); `check_project`
    przy roznicy emituje `Notice("warning", PROJECT_GEOMETRY_CHANGED, ...)`
    (nowa stala w `kartograf/notices.py`); `upgrade`/`force` zapisuja
    nowe sumy.
12. **Komunikaty zagniezdzone:** `NoticeSink` projektu; komunikat funkcji
    biblioteki wywolanej dla zadania -> `Notice(n.level, n.code,
    f"{task}: {n.text}")`.

## Review Focus

1. Przypiecia nigdy nie zmieniaja tresci w `download` bez trybu (wolno
   zmienic `version`/`label` przy identycznym `sha256`), w `check_project`,
   `project_status` ani `verify_project`.
2. Pelny sukces: `--country auto` z jednym krajem nieudanym nie przypina;
   porazka `upgrade`/`force` zostawia stare przypiecia zadania w calosci.
3. `check_project` liczy wzgledem przypiecia (`local_sha256`), takze gdy
   magazyn ma nowsza wersje, a `check_*` daje `current`.
4. Scalanie per zadanie i blokada: brak zgubionych zmian, blokada tylko
   na czas zapisu, zadnego SQLite.
5. CLI tylko tlumaczy: `project add` bierze `_task` grup i nie powtarza
   regul opcji; `kartograf/cli/project_cmd.py` nie importuje providerow,
   menedzerow ani `kartograf/download/*` (poza typami do wydruku).

## Mapa plikow

| Plik | Zmiana |
|---|---|
| `kartograf/download/options.py`, `kartograf/landcover/manager.py`, `kartograf/cli/groups/{elevation,imagery,landcover}.py` | krotki produktow/zrodel w bibliotece (Task 1) |
| `kartograf/download/data.py`, `kartograf/landcover/manager.py`, `kartograf/hydrology/hsg.py` | walidacja bez sieci (Task 1) |
| `kartograf/project/commands.py` | NOWY (Task 2) |
| `kartograf/project/model.py`, `kartograf/project/manifest.py`, `kartograf/project/__init__.py` | NOWE (Task 3) |
| `kartograf/project/operations.py` | NOWY (Task 4-7) |
| `kartograf/notices.py` | `PROJECT_GEOMETRY_CHANGED` (Task 7) |
| `kartograf/__init__.py` | eksport API i typow projektu (Task 4, 7) |
| `kartograf/cli/download_cmd.py`, `kartograf/cli/landcover_cmd.py`, `kartograf/cli/soil_cmd.py`, `kartograf/cli/groups/{elevation,imagery,landcover,soil}.py` | `_task` (Task 8) |
| `kartograf/cli/_args.py` | `add_update_flags` z opcjonalnym `plan_help` (Task 8) |
| `kartograf/cli/groups/project.py`, `kartograf/cli/project_cmd.py` | NOWE (Task 8) |
| `tests/project_fixtures.py`, `tests/test_project_commands.py`, `tests/test_project_manifest.py`, `tests/test_project_api.py`, `tests/test_project_download.py`, `tests/test_project_check.py`, `tests/test_project_cli.py` | NOWE |
| `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `README.md`, `docs/DEVELOPMENT_STANDARDS.md`, `docs/CHANGELOG.md`, `docs/PROGRESS.md`, `docs/SCOPE.md` | Task 9 |

---

### Task 1: Biblioteka danych - listy grup i walidacja bez sieci

**Files:**
- Modify: `kartograf/download/options.py`, `kartograf/download/data.py`,
  `kartograf/landcover/manager.py`, `kartograf/hydrology/hsg.py`,
  `kartograf/cli/groups/elevation.py`, `kartograf/cli/groups/imagery.py`,
  `kartograf/cli/groups/landcover.py`
- Test: `tests/test_input_errors.py` (rozszerzenie) albo nowy
  `tests/test_validate_request.py`

**Interfaces:**
```python
# kartograf/download/options.py
ELEVATION_PRODUCTS: tuple[str, ...] = ("nmt", "nmpt", "laz")
IMAGERY_PRODUCTS: tuple[str, ...] = ("orto",)
# kartograf/landcover/manager.py
LANDCOVER_SOURCES: tuple[str, ...] = ("bdot10k", "corine")
# kartograf/download/data.py
def validate_data_request(**selection) -> None: ...   # selection = klucze _SELECTION
# kartograf/landcover/manager.py
class LandCoverManager:
    def validate_request(self, *, teryt=None, sheet=None, bbox=None,
                         geometry=None, layer=None, **options) -> None: ...
# kartograf/hydrology/hsg.py
class HSGCalculator:
    def validate_request(self, *, sheet=None, bbox=None, geometry=None,
                         layer=None, depth: str) -> None: ...
```

- [x] **Step 1: Testy** - `test_validate_data_request_equals_download_error`
  (parametryzacja: brak `vertical_crs`, dwa wybory obszaru, `bbox` bez
  `country`, `resolution` spoza listy: ten sam typ i tekst wyjatku co
  `download_data` z tymi samymi argumentami, zero zapytan);
  `test_landcover_validate_request_equals_download_error` (CORINE bez
  `year`, `layers` z SHP, zly TERYT, dwa wybory, opcja innego zrodla);
  `test_hsg_validate_request_rejects_depth_and_selection`.
- [x] **Step 2: Implementacja** - wydziel funkcje/metody z prologow
  `_execute`, `LandCoverManager.download`/`check`,
  `HSGCalculator.calculate_hsg`/`check_hsg` i wywolaj je w tych
  prologach. Przenies krotki produktow i zrodel; grupy CLI importuja je
  z biblioteki. Istniejace testy (`tests/test_parity*.py`,
  `tests/test_input_errors.py`, `tests/test_cli*.py`) bez zmian
  i zielone.
- [x] **Step 3: Brama i commit** - `refactor(api): walidacja wyboru bez sieci i listy produktow grup w bibliotece`

---

### Task 2: Tabela komend projektu (`commands.py`)

**Files:**
- Create: `kartograf/project/commands.py`, `tests/test_project_commands.py`,
  `tests/project_fixtures.py`

**Interfaces:** decyzje 2-3 i 6 (bez `PinnedFile` - tabela zwraca
`VersionedFile`, przypiecia buduje `operations.py`).

- [x] **Step 1: Testy opcji** - `test_options_json_roundtrip`
  (`BBox` z `EPSG:5514`, `Path` wzgledna i bezwzgledna, `{"pl": "1m",
  "cz": "2m"}`, `layers`, `keep_raw=True`: `options_to_json` i
  `options_from_json` sa odwrotne, `None`/`False` pomijane);
  `test_options_reject_unknown_and_foreign` (`vertical_crs` w `landcover
  download`, `source="soilgrids"` w `landcover download`, `product="nmt"`
  w `imagery download`, `timeout`, `output_dir`, `update` -> `ValidationError`).
- [x] **Step 2: Testy walidacji** - `test_validate_matches_library`
  (dla kazdej pozycji: przypadek poprawny bez wyjatku i bez sieci,
  przypadek bledny = ten sam typ i tekst co Task 1).
- [x] **Step 3: Testy rodzin wyniku** (prawdziwe wywolania z fixtur
  offline): `test_files_pl_sheet_and_laz_tiles` (wszystkie `VersionedFile`,
  role `output`), `test_files_auto_partial_success_incomplete`
  (`DataReport.ok` i jeden kraj w `failed` -> `complete=False`),
  `test_files_bdot_area_failed_powiat_incomplete`,
  `test_files_bdot_keep_raw_has_raw_role`, `test_files_hsg_output_and_three_inputs`.
- [x] **Step 4: Implementacja** - pozycje tabeli wolaja: `download_data`/
  `check_data` (`elevation download`, `imagery download`, produkt z
  `ELEVATION_PRODUCTS`/`IMAGERY_PRODUCTS`), `LandCoverManager(output_dir,
  source, cache=cache).download/check` (`landcover download`, `source`
  z `LANDCOVER_SOURCES`), `LandCoverManager(output_dir, "soilgrids",
  cache=cache)` (`soil download`), `HSGCalculator(output_dir,
  cache=cache).calculate_hsg/check_hsg` (`soil hsg`). Walidacja = Task 1.
  Zbior `options` kazdej pozycji = flagi danych komendy (test zgodnosci
  z parserem w Task 8).
- [x] **Step 5: Brama i commit** - `feat(project): tabela komend danych projektu`

---

### Task 3: Model i plik manifestu (`model.py`, `manifest.py`)

**Files:**
- Create: `kartograf/project/model.py`, `kartograf/project/manifest.py`,
  `kartograf/project/__init__.py`, `tests/test_project_manifest.py`

**Interfaces:**
```python
MANIFEST_NAME = "kartograf-project.json"
PROJECT_SCHEMA = "kartograf-project/1"
LOCK_NAME = ".kartograf-project.lock"

def read_manifest(project_dir: Path) -> tuple[Project, dict[str, dict]]
    # Project + stan JSON kazdego zadania z chwili odczytu (do scalania)
def create_manifest(project_dir: Path, output_dir_text: str) -> None
    # init: blad, gdy plik istnieje (sprawdzenie pod blokada)
def commit_tasks(project_dir: Path,
                 changes: Mapping[str, tuple[dict | None, dict | None]]) -> tuple[str, ...]
def task_to_json(task: ProjectTask) -> dict
```

- [ ] **Step 1: Testy formatu** - `test_manifest_bytes_stable` (zloty plik
  z przykladu specu 3.3: odczyt -> zapis daje identyczne bajty; kolejnosc
  kluczy, wciecie, nowa linia na koncu); `test_read_rejects_invalid`
  (parametryzacja wg decyzji 9: zly JSON, `kartograf-project/2`, nieznany
  klucz, brak klucza, dubel nazwy, zla nazwa, nieznana komenda, obca
  opcja, `version` z `..`, bezwzgledna, z `.incoming`, bez `versions`,
  `path` z `versions`, `sha256` nie-hex, `pinned_at` bez
  `kartograf_version`, `geometry_sha256` bez `geometry`) - zawsze
  `ValidationError`, nic nie zapisane.
- [ ] **Step 2: Testy zapisu** - `test_commit_merges_other_tasks` (dwa
  odczyty, dwa `commit_tasks` z roznymi zadaniami: oba w pliku);
  `test_commit_conflict_same_task` (drugi zapis tego samego zadania
  zwraca konflikt, plik bez jego zmiany); `test_lock_busy_times_out_without_takeover`
  (katalog blokady z `owner` istnieje: `ValidationError` po skroconym
  czasie, katalog blokady nietkniety); `test_interrupted_replace_keeps_old_manifest`
  (`os.replace` rzuca: stare bajty, brak pliku tymczasowego, brak
  blokady); `test_project_dir_has_no_extra_files` (po serii operacji
  w katalogu projektu tylko `kartograf-project.json`).
- [ ] **Step 3: Implementacja** wg decyzji 1, 7-9.
- [ ] **Step 4: Brama i commit** - `feat(project): manifest kartograf-project/1 - format, walidacja, zapis atomowy`

---

### Task 4: API `init_project`, `open_project`, `add_project_task`, `remove_project_task`

**Files:**
- Create: `kartograf/project/operations.py`, `tests/test_project_api.py`
- Modify: `kartograf/project/__init__.py`, `kartograf/__init__.py`
  (`__all__`: funkcje projektu i typy `Project`, `ProjectTask`,
  `PinnedFile`, `ProjectReport`, `TaskResult`, `ProjectCheck`, `FileCheck`)

**Interfaces:** sygnatury z specu 4.3.

- [ ] **Step 1: Testy** - `test_init_creates_store_and_refuses_existing`
  (drugi `init` = `ValidationError`, bajty bez zmian);
  `test_paths_saved_relative_to_project` (cwd inny niz projekt: wzgledne
  `output_dir` i `geometry` zapisane wzgledem projektu, bezwzgledne bez
  zmian, separator `/`); `test_moved_project_with_store_resolves`
  (przeniesienie obu katalogow, `open_project` wskazuje nowe miejsca);
  `test_missing_store_dir_is_error` (operacje poza `init`);
  `test_add_validates_without_network` (bledny wybor: wyjatek Task 1,
  manifest bez zmian); `test_add_duplicate_and_bad_name`;
  `test_add_missing_geometry_file`; `test_remove_keeps_store_files`.
- [ ] **Step 2: Implementacja** - `add_project_task` waliduje nazwe,
  komende, opcje (`options_to_json` + `TaskCommand.validate`), plik
  geometrii; zapis przez `commit_tasks` ze stanem `None` (nowe zadanie).
- [ ] **Step 3: Brama i commit** - `feat(project): init, add, remove i odczyt projektu w API`

---

### Task 5: `download_project` bez trybu - przypiecie, `unchanged`, odtwarzanie

**Files:**
- Modify: `kartograf/project/operations.py`
- Create: `tests/test_project_download.py`

- [ ] **Step 1: Testy przypiecia** - `test_first_download_pins_every_file`
  (parametryzacja: arkusz PL, `--country auto` PL+CZ, LAZ z kilkoma
  kaflami, BDOT10k obszar z `keep_raw`, SoilGrids, CORINE, HSG: kazdy
  `VersionedFile` wyniku = jeden `PinnedFile`, role, `size_bytes`
  z sidecara, `pinned_at` z `frozen_clock`, `kartograf_version`);
  `test_incomplete_task_pins_nothing_and_retry_reuses_store` (BDOT10k:
  jeden powiat zawodzi -> `failed`, `files` puste; ponowienie z dzialajacym
  powiatem -> przypiete, udany powiat nie pobrany drugi raz - licznik
  wywolan fake'a); `test_auto_partial_success_not_pinned`;
  `test_written_after_each_task` (drugie zadanie rzuca: pierwsze zostaje
  przypiete w pliku); `test_no_metadata_cache_in_project_dir`.
- [ ] **Step 2: Testy stanu przypietego** - `test_pinned_task_is_offline_noop`
  (fake zrodla rzuca przy kazdym uzyciu, wynik `unchanged`);
  `test_second_project_newer_version_keeps_first_pins` (projekt B pobiera
  nowsza kampanie do tego samego magazynu: przypiecia A bez zmian,
  `verify_project(A)` OK po Task 7, sciezka standardowa wskazuje nowsza).
- [ ] **Step 3: Testy odtwarzania** - `test_restore_on_empty_store_same_content`
  (manifest skopiowany do projektu z pustym magazynem: `restored`, te same
  `sha256`; dla toru bez sygnalu `version`/`label` moga sie zmienic);
  `test_restore_conflict_keeps_pin` (zrodlo zwraca inna tresc: `failed`,
  przypiecie bez zmian, nowy plik w magazynie nieprzypiety);
  `test_restore_partial_saves_restored_pins`; `test_restore_needs_same_geometry`.
- [ ] **Step 4: Implementacja** - per zadanie wg specu 4.6: wybor
  przypadku po stanie przypiec i `stat` wersji (plik + sidecar,
  `size_bytes`); wywolanie `TaskCommand.download(update=None)`;
  `TaskCommand.files`; budowa `PinnedFile` (decyzja 6); zapis
  `commit_tasks` po kazdym zadaniu; konflikt scalania = blad zadania;
  wyjatki `KartografError` biblioteki konczace tylko zadanie.
- [ ] **Step 5: Brama i commit** - `feat(project): download - przypiecie zadan i odtwarzanie po SHA-256`

---

### Task 6: `download_project` z `update="upgrade"` i `"force"`

**Files:**
- Modify: `kartograf/project/operations.py`, `tests/test_project_download.py`

- [ ] **Step 1: Testy** - `test_upgrade_repins_whole_task` (nowsza
  kampania w fake'u skorowidza: nowe przypiecie, stare w `unpinned`, nowe
  `pinned_at`); `test_upgrade_failure_keeps_all_pins` (jedna jednostka
  zawodzi: przypiecia zadania identyczne bajtowo);
  `test_upgrade_takes_newer_local_version_without_download` (drugi projekt
  pobral nowsza wersje: zero pobran, przepiecie);
  `test_upgrade_without_signal_keeps_pin` (tor `none`: `unchanged`,
  `Notice` `UNVERIFIED_LOCAL` z prefiksem zadania);
  `test_force_same_content_keeps_pin_new_content_repins` (wycinek albo
  BDOT10k); `test_upgrade_adds_and_removes_files` (LAZ: nowy kafel
  dopisany, kafel spoza wyniku odpiety, plik zostaje w magazynie);
  `test_upgrade_only_named_task`; `test_upgrade_accepts_changed_geometry`
  (nowe `geometry_sha256`).
- [ ] **Step 2: Implementacja** - wspolna sciezka z Task 5 z
  `update=...`; przy pelnym sukcesie przypiecia = wynik w calosci,
  `unchanged` gdy identyczne (bez zapisu pliku).
- [ ] **Step 3: Brama i commit** - `feat(project): download --upgrade/--force przepina cale zadanie`

---

### Task 7: `project_status`, `verify_project`, `check_project`

**Files:**
- Modify: `kartograf/project/operations.py`, `kartograf/notices.py`,
  `kartograf/__init__.py`
- Create: `tests/test_project_check.py`

- [ ] **Step 1: Testy status/verify** - `test_status_detects_missing_and_size_without_reading`
  (`file_digest` i odczyt danych zablokowane atrapa rzucajaca:
  `missing`, `corrupt` przy innym rozmiarze, `ok`);
  `test_status_not_downloaded_not_ok`; `test_verify_detects_corruption`
  (zmiana jednego bajtu, podmieniony sidecar, sidecar z innym `sha256`/
  `size_bytes`/etykieta, dowiazanie symboliczne poza magazyn ->
  `corrupt`/`missing`, `ok=False`, manifest i magazyn bez zmian);
  `test_verify_after_store_copy` (kopia magazynu z dowiazaniami twardymi,
  nowy `output_dir`: `ok`).
- [ ] **Step 2: Testy check** - `test_check_statuses_against_pin`
  (prawdziwe `check_*` na fixturach: `current`, `newer` u zrodla,
  `newer` gdy magazyn ma nowsza wersje, a plan daje `current`, `added`
  (nowy kafel LAZ), `removed`, `unverifiable` (wycinek, BDOT10k),
  `check_failed` (sonda rzuca), `missing`);
  `test_check_hsg_new_input_edition_is_newer`;
  `test_check_downloads_nothing_and_keeps_manifest_bytes`;
  `test_check_not_downloaded_task_skipped_offline`;
  `test_check_geometry_changed_warns` (`PROJECT_GEOMETRY_CHANGED`);
  `test_slot_std_path_invariant` (dla kazdego konstruktora slotu z
  decyzji 10: `slot.std == slot.output_dir / slot.segment / slot.hierarchy / slot.name`;
  konstruktory: `download/storage.py::bbox_slot`,
  `landcover/store.py::selection_slot`, slot arkusza w
  `download/manager.py`, `download/laz.py::laz_slot`,
  `download/cz_sheets.py::_sheet_slot`).
- [ ] **Step 3: Implementacja** wg specu 4.8-4.9 i decyzji 10-11.
- [ ] **Step 4: Brama i commit** - `feat(project): status, verify i check-updates wzgledem przypiec`

---

### Task 8: CLI - `_task` w grupach i grupa `project`

**Files:**
- Modify: `kartograf/cli/download_cmd.py` (`_download_arguments` dzieli sie
  na argumenty danych i `output_dir`), `kartograf/cli/landcover_cmd.py`
  i `kartograf/cli/soil_cmd.py` (wydzielone budowanie argumentow
  z `cmd_landcover_download`/`run_land_cover`, `cmd_soil_download`,
  `cmd_soil_hsg`), `kartograf/cli/groups/{elevation,imagery,landcover,soil}.py`
  (`set_defaults(_handler=..., _task=...)`), `kartograf/cli/_args.py`
  (`add_update_flags(..., plan_help: str | None = ...)`: `None` = bez
  `--plan`)
- Create: `kartograf/cli/groups/project.py`, `kartograf/cli/project_cmd.py`,
  `tests/test_project_cli.py`

**Interfaces:**
```python
# kontrakt komend danych (uzupelnienie ADR-039, spec 5)
_task: Callable[[argparse.Namespace], dict]   # argumenty biblioteki bez output_dir,
                                               # trybow, workers, quiet, stats
# kartograf/cli/groups/project.py
def register(subparsers: argparse._SubParsersAction) -> None
    # init (--project, --output), add (--project, NAZWA, REMAINDER),
    # remove (--project, NAZWA), download (--project, ZADANIA*, tryby, -q),
    # status/verify (--project, ZADANIA*, -q)
```

- [ ] **Step 1: Testy tlumaczenia** - `test_task_hook_equals_handler_arguments`
  (dla kazdej komendy danych i kilku zestawow flag: `_task(ns)` rowne
  argumentom, ktore `_handler` przekazuje funkcji biblioteki - wzorem
  `tests/test_cli_translation.py`); `test_task_options_equal_parser_data_flags`
  (zbior `dest` akcji parsera komendy bez `help`, `output`, trybow,
  `plan`, `workers`, `quiet` i `stats` rowny `TaskCommand.options`;
  chroni przed rozjazdem przy nowych flagach).
- [ ] **Step 2: Testy `project add`** - `test_add_rejects_modes_and_foreign_output`
  (`--upgrade`, `--force`, `--check-updates`, `--plan`, `-o` innego
  katalogu -> kod 1 i `Error:`, manifest bez zmian); `test_add_accepts_output_equal_to_store`;
  `test_add_rejects_non_data_commands` (`elevation list-sources`,
  `soil list-layers`, `parse`, `cache`); `test_add_project_flag_after_name_hint`;
  `test_add_removed_command_error` (`removed_command_error` dla
  zagniezdzonej komendy, np. `download`); `test_add_double_dash_allowed`.
- [ ] **Step 3: Testy CLI = API** - `test_project_cli_equals_api`
  (harness wzorem `tests/parity.py::run_both`: ta sama sekwencja `init`,
  `add` x2, `download`, `status`, `verify`, `download --check-updates`,
  `download --upgrade` przez CLI i przez API w osobnych katalogach -
  identyczne bajty manifestow po normalizacji `output_dir`, magazyny
  `assert_same_store`, kody wyjscia = `ok`, `Notice` wypisane jako
  `Info:`/`Warning:`, bledy jako `Error:` z tekstem wyjatku);
  `test_quiet_keeps_warnings`.
- [ ] **Step 4: Implementacja** - `project add`: `create_parser()`
  zagniezdzony, `removed_command_error`, `_task`, nazwa komendy
  z `ns.command` i `getattr(ns, f"{ns.command}_command")`, kontrola
  `output`/trybow (spec 4.5), wywolanie `add_project_task`. Pozostale
  komendy: jedna funkcja API kazda, wydruk wg specu 4.2 (slownictwo
  USAGE 4.3), kody wyjscia wg specu 4.8-4.11, pasek postepu
  `create_progress_callback` dla `download` bez `-q`.
- [ ] **Step 5: Smoke** - z korzenia worktree: `python -m
  kartograf.cli.commands project --help`, `... project add --help`,
  `... project add t elevation download --help` (pomoc komendy grupy).
- [ ] **Step 6: Brama i commit** - `feat(cli): grupa project (init, add, remove, download, status, verify)`

---

### Task 9: Dokumentacja

**Files:** `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `README.md`,
`docs/DEVELOPMENT_STANDARDS.md`, `docs/CHANGELOG.md`, `docs/PROGRESS.md`,
`docs/SCOPE.md`

- [ ] ARCHITECTURE: sekcja 2 (pakiet `kartograf/project/`, zaleznosci:
  `project` -> `download`, `landcover`, `hydrology`; CLI -> `project`),
  nowa 3.5 "Manifest projektu `kartograf-project/1`" (format, sciezki,
  zapis, scalanie - streszczenie specu 3 i 4.12), sekcja 5 (nowa grupa
  danych: pozycja w `kartograf/project/commands.py` + `_task` + test).
- [ ] USAGE: nowa sekcja "Projekt" (spis tresci): przyklady ze specu 4.2,
  tabela przenoszenia (spec 3.2), zalecenie jawnego wariantu (`--year`)
  dla odtwarzalnosci (spec 4.6), relacja z `availability` (spec 4.10),
  biblioteka (`init_project`, `add_project_task`, `download_project`,
  `check_project`, `verify_project`).
- [ ] README: krotki przyklad projektu i link do USAGE.
- [ ] DEVELOPMENT_STANDARDS 17: punkt listy kontrolnej nowej grupy/komendy
  danych - pozycja tabeli projektu, `_task`, test zadania projektu.
- [ ] CHANGELOG `[0.8.0] - Unreleased`, "Dodane": grupa `kartograf
  project` i API projektu (bez "Co zrobic" - zmiana nielamiaca);
  "Zmienione": listy produktow grup w bibliotece (wewnetrzne).
- [ ] SCOPE 3.3 wiersz 2: stan "zrobione (0.8.0)" po E2E; PROGRESS:
  koniec sesji z wynikami bramy i E2E.
- [ ] Commit - `docs: manifest projektu w ARCHITECTURE, USAGE, README i CHANGELOG`

---

### Task 10: Smoke CLI i weryfikacja na zywo

- [ ] **Smoke offline:** prawdziwe CLI na malym magazynie z fixtur (albo
  przez `python -m kartograf.cli.commands` z fake'ami w skrypcie
  tymczasowym poza repo): `init`, `add`, `download`, `status`, `verify`,
  `download --check-updates`, podmiana wersji w magazynie (drugi projekt),
  `download --upgrade`; obejrzyj JSON na dysku. Skrypt usun po smoke.
- [ ] **E2E na zywo** (spec 7; dane w `<katalog-danych>`, nigdy w repo
  ani `/tmp`): projekt A (NMT PL arkusz, BDOT10k powiat, SoilGrids + HSG
  maly arkusz, arkusz SM5 CZ), `download`, `status`, `verify`; projekt B
  na tym samym magazynie (te same przypiecia bez pobierania);
  `download --check-updates` w A (sygnaly `index`, `http`, `metadata`,
  `none`; brak pobran - rozmiar magazynu bez zmian); kopia magazynu
  `rsync -aH`, nowy `output_dir`, `verify`; projekt z pustym magazynem:
  `download` -> `restored`. CLMS bez credentials pomijamy.
- [ ] Raport `docs/research/2026-10-XX-project-e2e/raport.md` (polecenia
  z `<katalog-danych>`, statusy, liczby plikow, ograniczenia sygnalow);
  commit - `docs(research): E2E manifestu projektu na zywo`.

---

## Integracja z planami A-E podprojektu 3

- **Plan A, B, E (produkty w `elevation`/`imagery`):** nowe produkty
  dopisuja do `ELEVATION_PRODUCTS`/`IMAGERY_PRODUCTS` (Task 1) - projekt
  bez zmian; nowe flagi danych komendy wymagaja tylko, by test
  `test_task_options_equal_parser_data_flags` przeszedl (zbior opcji
  pozycji tabeli). `elevation availability` nie jest komenda danych - nie
  ustawia `_task`.
- **Plany C, D, E (nowe grupy):** komenda `download` nowej grupy ustawia
  `_task`, a do `COMMANDS` dochodzi pozycja z `download_collection`/
  `check_collection` (plan C), walidacja bez sieci wspolna z funkcja
  pobrania i adapter `CollectionReport.files[].file` (rola `output`,
  pelny sukces = `ok` i puste `failed`) oraz test jednego zadania
  projektu. Gdy ten plan scala sie po planie C - te kroki naleza do Task 2
  i 8 tego planu; gdy wczesniej - do planu C/D/E (spec 5).
- **Konflikty plikow:** `kartograf/__init__.py` (`__all__`),
  `kartograf/notices.py`, `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md` -
  dopisywanie w swoich miejscach, bez przestawiania cudzych wpisow.

## Kryteria zamkniecia

- Kryteria akceptacji specu 6 (1-11) pokryte testami z Task 1-8 i smoke
  z Task 10; brama zielona.
- E2E na zywo wykonane i opisane (spec 7), bez danych w repo i `/tmp`.
- Dokumentacja (Task 9) zaktualizowana, `docs/DECISIONS.md` z CRLF.
