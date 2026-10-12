# Magazyn wersjonowany — plan 3/3: land cover, SoilGrids, HSG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-12

**Goal:** BDOT10k, CORINE i SoilGrids (`LandCoverManager`) oraz HSG (`HSGCalculator`) w magazynie wersji z planow 1/3 i 2/3: segmenty `data/` (D11, spec 3.4), sygnal `metadata` = wydanie zrodla (D29, D30), podglad CORINE jako osobny produkt (D31), zapis wylacznie do magazynu (D32), HSG liczony z wersji wejsc z ponownym uzyciem (`reused`, D33), tryby `update` i plan `kartograf-plan/1` w bibliotece i w CLI `landcover download` / `soilgrids hsg`; pelna dokumentacja, E2E calosci na zywo i przygotowanie galezi do `develop`.

**Architecture:** `fetch.py` dostaje porownanie wydan (`edition=`), rozdzial na `use_local` (decyzja bez sieci danych) i `store_file` (zapis pobranego pliku jako wersji), status `reused` i regule "sygnal `http` tylko z kanalu `http`". Nowy `kartograf/sources/edition.py` (`Edition`, walidacja etykiety) i metody `edition()` providerow SoilGrids i CORINE. Nowy `kartograf/landcover/store.py` — segmenty z parametrami tresci i sloty (`teryt/`, `bbox/`, hierarchia godla). `LandCoverManager` i `HSGCalculator` zwracaja wyniki z `VersionedFile` zamiast `Path` i nie przyjmuja `output_path`. Plan aktualizacji: nowe tory `landcover` i `hsg`. CLI: wspolna obsluga trybow i pliku planu z `download_cmd.py`.

**Spec:** `docs/superpowers/specs/2026-10-08-versioned-store-design.md` — ZAAKCEPTOWANY 2026-10-11 (D1-D24), rewizje 2026-10-12 (D26-D28; D29-D33 z weryfikacji przed tym planem, `docs/research/2026-10-12-plan3-spec-check/raport.md`). Numeracja decyzji (Dn) odnosi sie do specu.

**Plany 1/3 i 2/3:** `docs/superpowers/plans/2026-10-08-versioned-store-1-core-pl-sheets.md`, `docs/superpowers/plans/2026-10-12-versioned-store-2-laz-cz-cutouts.md` — wykonane na `feat/versioned-store` (`52c2b94`..`369e7cf`, weryfikacja na zywo planu 2/3: `docs/research/2026-10-12-plan2-live/raport.md`). Ich "Global Constraints" i decyzje implementacyjne obowiazuja; plan 2/3 decyzja 7 (tory planu) rozszerzona nizej (decyzja 5).

**Po planie 3/3:** galaz `feat/versioned-store` idzie do `develop` (Task 12, za zgoda uzytkownika). Poza zakresem (backlog): CLMS 1990 jako dane (katalog CLMS ma rekord, kod tylko podglad WMS), sprawdzenie pobrania CLMS na zywo (`CLMS_CREDENTIALS` odlozone przez uzytkownika 2026-10-12).

---

## Weryfikacja specu wzgledem kodu po planie 2/3 (2026-10-12)

Pelny raport: `docs/research/2026-10-12-plan3-spec-check/raport.md`. Skrot:

1. **Sygnal SoilGrids i CORINE (rozstrzygniete D29, D30):** wydanie z GetCapabilities mapy wlasciwosci (`SoilGrids250m 2.0 - Clay content` -> `2.0`) i z publicznego katalogu CLMS (`characteristics_release_major_version` = `V2020_20u1`, bez credentials). Wersja bez wydania nie powstaje.
2. **UID-y CLMS w kodzie:** `CorineProvider.CLMS_DATASET_UIDS` i `CLMS_RASTER_DOWNLOAD_IDS` (`kartograf/providers/corine.py:207-220`) dla 2012/2006/2000 nie istnieja w katalogu (`items_total: 0`); poprawne wartosci w raporcie. Odczyt wydania wymaga poprawnych UID-ow — poprawka w Task 1. Pobranie CLMS pozostaje niesprawdzone na zywo.
3. **Podglad CORINE bez credentials (D31):** stylizowany PNG z WMS (`extra.fallback = "wms_png"`, `kartograf/landcover/manager.py:676-687`); osobny segment `_preview`, kanal `WMS` (`none`).
4. **`metadata` w `fetch.py` niezaimplementowane:** `_use_local` i `inspect_version` traktuja `metadata` jak `index` (`kartograf/download/fetch.py:179-181, 294-295`) — lokalna wersja zawsze aktualna. Task 2.
5. **Sygnal `http` z kanalu `none`:** `fetch_version` przekazuje do `commit_version` slownik z `fetch` jako `signal` (`fetch.py:236-246`); BDOT10k zwraca `{"content_length": ...}`, a `same_http_signal` = `None` daje `relabeled` zamiast `unchanged` (`versions.py:405-420`). Task 2: `signal` tylko dla kanalu `http`.
6. **Segmenty lowercase:** ADR-026 regula 1 (`docs/ARCHITECTURE.md` 3.3); przyklad specu poprawiony (`_ptwp-swrs`).
7. **`output_path` u konsumentow (D32):** Hydrograf wola `LandCoverManager.download_by_*(..., output_path=...)` i `HSGCalculator().calculate_hsg_by_bbox(bbox, hsg_path)` (`Hydrograf/backend/scripts/download_landcover.py:134,154,189`, `Hydrograf/backend/core/cn_calculator.py:143`, `Hydrograf/backend/scripts/bootstrap.py:708`) — wpis BREAKING z "Co zrobic".
8. **Kolizja nazw HSG w CLI:** `soilgrids hsg --bbox ... -o <katalog>` pisze `hsg_bbox_<depth>.tif` bez wspolrzednych (`kartograf/cli/soilgrids_cmd.py:102-109`) — znika z hierarchia `bbox/<wsp>`.
9. **GPKG BDOT10k na udziale SMB:** skladany w lokalnym katalogu tymczasowym i kopiowany (`kartograf/providers/pl/bdot10k.py:654-677`) — `.incoming/` na udziale nie wraca do bledu SQLite z 2026-10-07.

## Global Constraints

Jak w planach 1/3 i 2/3 (Python z `.venv`, brama przed kazdym commitem: `pytest -m "not live"`, `ruff check .`, `ruff format --check .`, `mypy kartograf/ tests/`; Conventional Commits po polsku, autor `Daldek <git@debever.pl>` bez `Co-Authored-By`, commit wylacznie przez straznik wzorcow `! git diff --cached -U0 | grep '^+' | grep -qiEf "$HOME/.config/kartograf/forbidden-patterns.txt" && git commit ...`; angielskie identyfikatory, komunikaty CLI po polsku bez diakrytykow w kodzie; CRLF w `docs/DECISIONS.md`; testy zachowania zamiast okablowania). Dodatkowo:

- Stale: `TRACKS = ("pl_sheet", "laz_tile", "cz_sheet", "pl_cutout", "cz_cutout", "landcover", "hsg")`; `FileStatus = Literal["new", "unchanged", "relabeled", "local", "reused"]`; etykieta wydania `[A-Za-z0-9._+-]+`.
- Testy offline: SoilGrids GetCapabilities z `tests/fixtures/signals/real_2026_10_12/isric_soilgrids_capabilities_get.xml`, katalog CLMS z `.../clms_corine_2018_search.json`; atrapy sesji licza zapytania (zero pobran danych w trybie `check` i przy lokalnej wersji).
- Testy, ktore pinuja usuwane zachowanie (nazwy `<zrodlo>_..._<tryb>_<id>.<ext>`, `output_path` menedzera, `keep_intermediate`, `--keep-intermediate`, wynik `Path`, nadpisywanie przy kazdym pobraniu, `storage_subdir is None` dla land cover), usuwaj albo przepisuj — bez podwojnych sciezek.
- Live (Task 11): katalog danych testow na zywo wskazany przez uzytkownika 2026-10-12 — sciezki NIE zapisuj w repo, w commitach ani w raportach (w raporcie `<katalog-danych>`); jawne `--output`, cache CLI w korzeniu repo.

## Decyzje implementacyjne (bez nowych decyzji produktowych)

1. **Wydanie (`Edition`):** `kartograf/sources/edition.py` — `Edition(id, url, title=None, dataset_uid=None)`, `to_extra()` -> `extra.edition` (klucze z wartoscia rozna od `None`), `edition_label(raw, *, what)` — `DownloadError`, gdy `raw` nie pasuje do `[A-Za-z0-9._+-]+`. SoilGrids: `SoilGridsProvider.edition(property, timeout=...)` — GetCapabilities WCS 2.0.1 mapy wlasciwosci, pierwszy `ows:Title` (`ServiceIdentification`), regex `^SoilGrids250m (\S+) - `; brak dopasowania, blad HTTP albo XML = `DownloadError`. CORINE: `CorineProvider.edition(year, timeout=...)` — `GET {CLMS_API_BASE}/@search?UID=<uid>&fullobjects=1` z `Accept: application/json`, bez tokenu; dokladnie jeden rekord, pole `characteristics_release_major_version`; inaczej `DownloadError`. Oba przez `get_with_retry` (polityka ponowien transportu).
2. **Porownanie `metadata` (D30) w `fetch.py`:** parametr `edition: Callable[[], Edition] | None` (wolajacy memoizuje: jedno zapytanie na wydanie w zadaniu, spec 4.1). Lokalna wersja z `label_source == "edition"`: `label == edition().id` = aktualna; inna = nowsza (domyslnie `local` + `newer=<id>`, `upgrade` pobiera). Lokalna wersja z innym `label_source` (nie powstaje z Kartografa) = nieporownywalna (`unverified="none"` / `unverifiable`). `edition()` = `DownloadError`: lokalna jest — domyslnie `unverified="check_failed: ..."`, `upgrade` i `force` = blad; brak lokalnej = blad (zadnej wersji bez wydania). Etykieta nowej wersji: `VersionRef(edition().id, "edition")`.
3. **`use_local` i `store_file`:** `fetch_version` = `use_local(...)` (wersja lokalna albo `None` = pobierz) + pobranie do `.incoming/` + `store_file(...)` (sha256 jednym odczytem, `commit_version`, sidecar, dowiazanie). Wolajacy z wieloma plikami z jednego pobrania (BDOT10k GPKG + ZIP) uzywa obu funkcji bezposrednio. Zachowanie `fetch_version` dla torow planu 2/3 bez zmian.
4. **`signal` dla `commit_version`:** tylko kanal `http` przekazuje naglowki jako sygnal D23; `none`/`metadata`/`index` — `signal=None` (naglowki trafiaja do `extra.http` sidecara jak dzis). Etykieta wydania rozroznia `relabeled` dla `metadata`.
5. **Tory planu:** `landcover` (jednostka: TERYT, wspolrzedne bbox albo godlo; jedna pozycja na plik — przy `keep_raw` dwie pozycje tej samej jednostki) i `hsg` (jednostka jak wyzej; status `missing`/`current`, nigdy `newer`; `available_label` = wydanie wejsc). `available_signal` dla `metadata` = `{"edition": <id>}`. `select_planned` bez zmian.
6. **Segmenty (spec 3.4):** `storage_subdir` deskryptorow = prefiks bez placeholderow (`landcover/pl_bdot10k`, `landcover/eu_corine`, `soil/global_soilgrids`); `landcover_segment(key, tokens)` dokleja `_` + tokeny lowercase (kazdy `[a-z0-9.-]+`, inaczej `ValidationError`). HSG: stala `HSG_SEGMENT_PREFIX = "hsg/global_soilgrids"` (pochodna, bez deskryptora). Tokeny: BDOT10k GPKG `("gpkg", *[<warstwy posortowane, '-'>])`, ZIP `("gpkg", "zip")`, SHP `("shp",)`; CORINE `(str(year),)` albo `(str(year), "preview")`; SoilGrids `(property, depth, stat)`; HSG `(depth, stat)`.
7. **Sloty:** `selection_slot(output_dir, segment, ext, *, teryt=None, bbox=None, sheet=None)`: teryt -> `<seg>/teryt/<T><ext>`, wersje `<seg>/versions/teryt/`; bbox -> `bbox_slot` (EPSG:2180, `.10g`); arkusz -> `<seg>/<path_parts(godlo)>/<godlo><ext>`, wersje `<seg>/versions/<path_parts>/` (`SheetParser(...).sheet`, `parser_registry.path_parts`). Jednostka planu: `selection_unit(...)` (TERYT / wspolrzedne `_`-laczone / godlo).
8. **Wyniki:** `LandCoverResult(unit, file: VersionedFile, raw: VersionedFile | None = None)`; `LandCoverAreaResult(files: tuple[LandCoverResult, ...], failed: tuple[LandCoverFailure, ...] = (), stale: tuple[PlanItem, ...] = ())` dla BDOT10k wielu powiatow (blad per plik, reszta sie wykonuje — spec 4.2); `LandCoverFailure(unit, error)`; `HsgResult(unit, file: VersionedFile, inputs: tuple[LandCoverResult, ...], stale: tuple[PlanItem, ...] = ())`. Pojedynczy plik: blad = wyjatek (jak dzis).
9. **BDOT10k z `keep_raw`:** paczka pobierana, gdy ktorykolwiek z zadanych slotow (GPKG, ZIP) wg `use_local` wymaga pobrania; `download_package(teryt, <incoming GPKG>/<T>.gpkg, raw_path=<incoming ZIP>/<T>.zip, ...)` — kazdy plik w `.incoming/` wlasnego segmentu; najpierw `store_file` ZIP, potem GPKG z `extra.source_files = [{"name": "package", "file": <sciezka wersji ZIP wzgledem --output>, "sha256": ...}]`. Slot z lokalna wersja, gdy drugi wymagal pobrania: pobrana tresc i tak trafia przez `store_file` (ta sama tresc = `unchanged`).
10. **CORINE kanal:** `CorineProvider.uses_clms(year) -> bool` (`has_clms_token and year in CLMS_YEARS`) wybiera segment i kanal przed siecia; podglad = segment `_preview`, `.png`, `none`, etykieta `downloaded`.
11. **HSG (D33):** wejscia = `LandCoverManager(output_dir, soilgrids_provider)` z tym samym wyborem i `update`; `reused`: wersja HSG, ktorej `extra.source_files` ma te same trzy `sha256` (kolejnosc clay, sand, silt) — najnowsza taka wersja, dowiazanie na nia (`refresh=True`, gdy cel inny). Inaczej obliczenie do `.incoming/` i `store_file` (`VersionRef(<wydanie>, "edition")`, wydanie = posortowane unikalne etykiety wejsc laczone `+`). `--force` dotyczy wejsc; HSG liczony tylko przy innym zestawie sha256. Sidecar wersji: `emit_sidecar("global.isric.soilgrids", ..., exclusive=True, digest=, version=)`, `extra`: `derived`, `depth`, `stat`, `classes`, `source_layers`, `source_files` (`name`, `file`, `sha256`, `label`).
12. **CLI:** wspolna grupa flag `add_update_flags(parser, *, check_help, upgrade_help, force_help)` w `_parser.py` (download, `landcover download`, `soilgrids hsg`); wspolny cykl pliku planu `run_with_plan_file(args, body)` wyodrebniony z `cmd_download` (`kartograf/cli/download_cmd.py:1121-1144`); `commands.py` — `--plan` bez trybu = blad parsera dla wszystkich trzech komend. Linie statusu i podsumowanie z `download_cmd.py` (`_report_file`, `_print_version_summary` + licznik `uzyte ponownie`, `_STATUS_TEXT["reused"] = "uzyta ponownie"`).

## Review Focus

1. **Porownywalnosc wersji (D29, D30):** zadna wersja SoilGrids/CORINE bez etykiety wydania; metadane niedostepne bez lokalnej wersji = blad, z lokalna = `Warning:` (domyslnie) / blad (`--upgrade`). Task 2 `test_fetch_version_metadata_matrix`, Task 4 `test_soilgrids_edition_unavailable_without_local_is_error`.
2. **`--check-updates` nigdy nie pobiera danych:** land cover i HSG — atrapy licza `download_to`/WCS GetCoverage/paczki = 0; dozwolone tylko GetCapabilities, katalog CLMS i PRG. Task 4-6 `test_check_*_never_downloads`.
3. **Kanal `none` bez falszywego `relabeled`:** ponowne pobranie BDOT10k tej samej tresci innego dnia = `unchanged`. Task 2 `test_none_channel_headers_are_not_a_signal`, Task 5 `test_bdot_force_same_content_unchanged_next_day`.
4. **HSG `reused`:** te same wejscia = zero obliczen; zmiana jednej warstwy = nowa wersja; `--force` z ta sama trescia wejsc = `reused`. Task 6.
5. **Segmenty lowercase i rozdzial podgladu:** `pl_bdot10k_gpkg_ptwp-swrs`, `eu_corine_2018_preview` nigdy nie dzieli wersji z `eu_corine_2018`. Task 3, 4.
6. **Jedna polityka:** land cover i HSG przez `use_local`/`store_file`/`fetch_version`; zadnej wlasnej galezi "plik istnieje".

---

## Mapa plikow

| Plik | Odpowiedzialnosc |
|---|---|
| `kartograf/sources/edition.py` (NOWY) | `Edition`, `edition_label` |
| `kartograf/sources/descriptor.py`, `kartograf/sources/registry.py` | `TransportKind.WMS`; kanaly CORINE (`CLMS_API` `metadata`, `WMS` `none`), SoilGrids `metadata`; `storage_subdir` prefiksy land cover |
| `kartograf/providers/soilgrids.py`, `kartograf/providers/corine.py` | `edition()`; CORINE: UID-y z katalogu, `uses_clms` |
| `kartograf/download/fetch.py` | `use_local`, `store_file`, `edition=`, `reused`, `signal` tylko dla `http` |
| `kartograf/download/plan.py` | tory `landcover`, `hsg` |
| `kartograf/landcover/store.py` (NOWY) | `landcover_segment`, `HSG_SEGMENT_PREFIX`, `selection_slot`, `selection_unit` |
| `kartograf/landcover/manager.py` | magazyn, `update=`, `plan=`, `check*`, wyniki `LandCoverResult`/`LandCoverAreaResult`; bez `output_path`, `_generate_output_path`, `_source_prefix` |
| `kartograf/hydrology/hsg.py` | `HSGCalculator(output_dir, provider=None)`, wersje, `reused`, `check_hsg_by_*`, `HsgResult`; bez `keep_intermediate` i katalogu tymczasowego wejsc |
| `kartograf/cli/_parser.py`, `kartograf/cli/commands.py`, `kartograf/cli/download_cmd.py`, `kartograf/cli/landcover_cmd.py`, `kartograf/cli/soilgrids_cmd.py` | flagi trybow, plik planu, linie statusu |
| `kartograf/__init__.py` | eksporty `LandCoverResult`, `LandCoverAreaResult`, `LandCoverFailure`, `HsgResult`, `Edition`; przyklad land cover w docstringu modulu (42-45) |
| `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `docs/SCOPE.md`, `docs/PRD.md`; `docs/PROGRESS.md` na `develop` | ADR-036 (D29-D33), ADR-026 realizacja, BREAKING, opisy ukladu |

Fakty o obecnym kodzie (zweryfikowane 2026-10-12 na `feat/versioned-store` `9a8f392`):
- `fetch.py`: `UpdateMode`/`FileStatus` 43-46, `Fetch`/`Probe`/`WriteSidecar` 50-53, `FileSlot` 76-104, `VersionedFile` 107-125, `_use_local` 157-181, `fetch_version` 184-258 (commit z `signal=http` 238-246), `inspect_version` 261-310.
- `versions.py`: `LabelSource` 42, `_VERSION_DIR` 47, `VersionRef.downloaded` 77-80, `version_key` 235-255 (etykieta bez daty: `downloaded_at`), `same_http_signal` 344-361, `commit_version` 364-468 (dedupe 405-420).
- `plan.py`: `Track`/`TRACKS` 26-27, `items_for` 117-119, `_item` 122-130, `select_planned` 183-206.
- `storage.py`: `storage_for_provider` 635-672, `bbox_cutout_path` 675-688, `bbox_slot` 691-706.
- `landcover/manager.py`: `PROVIDERS` 26-30, `__init__` 101-129, `download` 187-250, `download_by_teryt` 252-284, `download_by_bbox` 286-337, `download_by_sheet` 339-386, `download_all_counties` 388-415, `_download_county` 437-466, `_write_bdot_sidecars` 468-494, `download_batch` 501-582, `_content_params` 584-608, `_generate_output_path` 610-651, `_source_prefix` 653-658, `_write_sidecar` 660-697.
- `providers/pl/bdot10k.py`: `Bdot10kPackage` 63-72, `download_package` 174-292 (`raw_path` 211-214, 267-268), `_extract_gpkg_from_zip` 476-607, `_write_raw_zip` 610-624, `_merge_gpkg_files` 626-677.
- `providers/corine.py`: `CLMS_API_BASE` 204, UID-y 207-220, lata 229-231, `download_by_bbox` 319-378, `_download_via_clms` 447-497, `_download_via_clms_direct` 593-655 (zapis `.tif` 644-652), `download_by_teryt` 752-770.
- `providers/soilgrids.py`: `WCS_BASE` 105, `download_by_bbox` 165-251, `_download_via_wcs` 253-298, `_construct_wcs_url` 300-354, `download_by_teryt` 360-382.
- `hydrology/hsg.py`: `HSGCalculator` 366-669 (`__init__` 386-395, `calculate_hsg_by_sheet` 406-456, `calculate_hsg_by_bbox` 458-579, `_write_sidecar` 581-615, `get_hsg_statistics` 617-669), `hsg_from_rasters` 672-742, `_write_rasters_sidecar` 745-770.
- `sources/`: `TransportKind` `descriptor.py:18-28`, `AccessChannel` 46-63, `SourceDescriptor.resolve_subdir` 95-124; rejestr `registry.py` `pl.gugik.bdot10k` 205-223, `eu.clms.corine` 224-244, `global.isric.soilgrids` 245-264, `channel_signal` 379-395; `emit_sidecar` `sidecar.py:318-422`.
- CLI: `_parser.py` tryby `download` 265-295, `landcover download` 418-501, `soilgrids hsg` 535-588; `commands.py:54-58` (`--plan` bez trybu); `download_cmd.py` `_PlanContext` 1081-1101, `cmd_download` 1104-1144, `_update_mode` 1427-1432, `_plan_line` 1463-1477, `_report_plan` 1480-1487, `_report_stale` 1490-1499, `_STATUS_TEXT` 1526-1531, `_status_lines` 1534-1550, `_report_file` 1553-1589, `_print_version_summary` 1600-1609; `landcover_cmd.py` `cmd_landcover_download` 129-272; `soilgrids_cmd.py` `cmd_soilgrids_hsg` 41-187.
- Testy: `tests/test_landcover.py` (`TestLandCoverManagerDownload` 1172, `TestSidecarLandCover` 1632, `TestLandCoverNoSideEffectsOnInit` 1868, `TestLandCoverCLI` 332), `tests/test_landcover_output_params.py` (calosc pinuje nazwy plikow), `tests/test_hsg.py` (`TestHSGCalculatorCalculateFull` 421, `TestHSGSidecar` 689, `TestHSGOutputDirOnWrite` 786, `TestHSGCLI` 348, `TestHsgFromRasters` 823), `tests/test_soilgrids.py` (`TestSoilGridsManager` 318), `tests/test_sources_registry.py` (406: `storage_subdir is None`), `tests/test_fetch.py`, `tests/test_plan.py`, `tests/test_cli_update_modes.py`.

---

### Task 1: Wydania zrodel i deskryptory

**Files:**
- Create: `kartograf/sources/edition.py`, `tests/test_edition.py`
- Modify: `kartograf/sources/descriptor.py` (`TransportKind` 18-28), `kartograf/sources/registry.py` (205-264), `kartograf/providers/soilgrids.py`, `kartograf/providers/corine.py` (204-231)
- Test: `tests/test_sources_registry.py` (406), `tests/test_soilgrids.py`, `tests/test_landcover.py` (`TestCorineProvider`)

**Interfaces:**
```python
# sources/edition.py
@dataclass(frozen=True)
class Edition:
    id: str                       # version label (D29), [A-Za-z0-9._+-]+
    url: str                      # metadata request
    title: str | None = None      # SoilGrids: raw ows:Title
    dataset_uid: str | None = None  # CORINE: CLMS dataset UID
    def to_extra(self) -> dict    # extra.edition, None values skipped

def edition_label(raw: str, *, what: str) -> str   # DownloadError when not [A-Za-z0-9._+-]+

# descriptor.py
class TransportKind(StrEnum):
    ...
    WMS = "wms"  # CORINE preview (EEA/DLR)

# soilgrids.py
def edition(self, property: str, timeout: int = DEFAULT_TIMEOUT) -> Edition
def capabilities_url(self, property: str) -> str

# corine.py
CLMS_DATASET_UIDS = {2018: "0407d497d3c44bcd93ce8fd5bf78596a", 2012: "a5ee71470be04d66bcff498f94ceb5dc",
                     2006: "d443c86fec2f49e08ff12c7decdbf2af", 2000: "6704f90ca82e4f228a46111519f8978e"}
CLMS_RASTER_DOWNLOAD_IDS = {2018: "7bcdf9d1-6ba0-4d4e-afa8-01451c7316cb", 2012: "b1027c88-6256-435b-98a3-62f019cbb381",
                            2006: "4841f8cb-6e7c-4227-bb35-cd787609c546", 2000: "19d7fbd8-53ee-4d09-89b6-fe5231247763"}
def uses_clms(self, year: int) -> bool
def edition(self, year: int, timeout: int = DEFAULT_TIMEOUT) -> Edition   # year not in CLMS_YEARS = ValidationError
```

Rejestr: `pl.gugik.bdot10k` `storage_subdir="landcover/pl_bdot10k"`; `eu.clms.corine` `storage_subdir="landcover/eu_corine"`, kanaly `CLMS_API` (`metadata`) i `WMS` (`none`, `horizontal_crs="EPSG:3857"`, `notes` o 1990 = DLR EPSG:4326 i "podglad, nie dane"); `global.isric.soilgrids` `storage_subdir="soil/global_soilgrids"`, kanal `WCS` `update_signal="metadata"`.

- [ ] **Step 1: Testy** — `test_edition_label_rejects_unsafe` (spacja, `/`, pusty), `test_edition_to_extra_skips_none`; `test_soilgrids_edition_from_recorded_capabilities` (fixtura XML -> `id="2.0"`, `title="SoilGrids250m 2.0 - Clay content"`, `url` z `map=/map/clay.map`), `test_soilgrids_edition_unknown_title_is_download_error`, `test_soilgrids_edition_http_error_is_download_error`; `test_corine_edition_from_recorded_catalogue` (fixtura JSON -> `V2020_20u1`, `dataset_uid`), `test_corine_edition_no_record_is_download_error` (`items_total: 0`), `test_corine_edition_without_credentials_sends_no_token` (naglowki zapytania bez `Authorization`), `test_corine_uids_match_catalogue` (stale = tabela raportu), `test_corine_uses_clms` (token x rok); rejestr: `test_channel_signals_match_inventory` rozszerzony o CORINE WMS i SoilGrids `metadata`, `test_landcover_storage_prefixes` zamiast asercji `storage_subdir is None` (406).
- [ ] **Step 2: Testy live** (`-m live`, bez credentials): `test_live_soilgrids_edition` (`clay`, `sand`, `silt` -> to samo `id`), `test_live_corine_edition_2018`.
- [ ] **Step 3: Implementacja** i brama (offline).
- [ ] **Step 4: Commit** — `feat(sources): wydania SoilGrids i CORINE jako sygnal metadata (D29)`

---

### Task 2: `fetch.py` — wydania, `use_local`/`store_file`, `reused`, tory planu

**Files:**
- Modify: `kartograf/download/fetch.py` (43-310), `kartograf/download/plan.py` (26-27)
- Test: `tests/test_fetch.py`, `tests/test_plan.py`

**Interfaces:**
```python
FileStatus = Literal["new", "unchanged", "relabeled", "local", "reused"]
EditionLookup = Callable[[], Edition]   # memoized by the caller (one request per job)

def use_local(slot: FileSlot, update: UpdateMode | None, *, signal: SignalKind,
              probe: Probe | None = None, edition: EditionLookup | None = None) -> VersionedFile | None
    # None = the file must be downloaded; links the standard path to the local version
def store_file(slot: FileSlot, staged: Path, *, version: VersionRef, write_sidecar: WriteSidecar,
               http: dict | None, signal: SignalKind, coverage: bool = False) -> VersionedFile
    # read_content once, commit_version(signal=http if signal == "http" else None), link
def fetch_version(slot, update, *, signal, fetch, write_sidecar, version: VersionRef | None = None,
                  probe=None, edition: EditionLookup | None = None, coverage=False) -> VersionedFile
    # signal == "metadata": edition required, version None (VersionRef(edition().id, "edition"));
    # other signals: version required, edition None (ValidationError otherwise)
def inspect_version(slot, *, track, unit, signal, probe=None, edition: EditionLookup | None = None,
                    available=(None, None)) -> PlanItem
    # metadata: available = (id, {"edition": id}); check_failed on DownloadError of edition()

# plan.py
Track = Literal["pl_sheet", "laz_tile", "cz_sheet", "pl_cutout", "cz_cutout", "landcover", "hsg"]
```

Regula `metadata` (decyzja 2), uzupelnienie tabeli z planu 2/3 Task 4:

| Lokalna | `edition()` | `None` (domyslny) | `"upgrade"` | `"force"` |
|---|---|---|---|---|
| brak | `id` | pobiera (etykieta `id`) | pobiera | pobiera |
| brak | `DownloadError` | blad | blad | blad |
| jest (`edition`), rowna | `id` | `local` | `local` | pobiera |
| jest (`edition`), inna | `id2` | `local`, `newer=id2` | pobiera (`id2`) | pobiera |
| jest | `DownloadError` | `local`, `unverified="check_failed: ..."` | blad | blad |
| jest, `label_source != "edition"` | `id` | `local`, `unverified="none"` | `local`, `unverified="none"` | pobiera |

- [ ] **Step 1: Testy** — `test_fetch_version_metadata_matrix` (kazda komorka osobno; `edition` i `fetch` atrapy liczace wywolania), `test_metadata_same_content_new_edition_is_relabeled` (D23: ten sam sha, nowe wydanie -> nowy katalog `<id2>_<sha8>` z hardlinkiem), `test_metadata_edition_called_once_per_file`, `test_inspect_version_metadata_statuses` (`missing` z `available_label`, `current`, `newer`, `check_failed`, `unverifiable`), `test_none_channel_headers_are_not_a_signal` (`fetch` zwraca `{"content_length": 10}`, `signal="none"`, ta sama tresc innego dnia -> `unchanged`, `extra.http` w sidecarze nowej wersji nie powstaje), `test_http_channel_signal_unchanged` (istniejace testy `http` bez zmian), `test_store_file_equals_fetch_version_tail` (ta sama wersja i sidecar co `fetch_version` z ta sama trescia), `test_fetch_version_rejects_version_and_edition_mix`; `test_plan_round_trip_all_tracks` z `landcover` i `hsg`.
- [ ] **Step 2: Implementacja** (`fetch_version` = `use_local` + pobranie + `store_file`; tory planu 2/3 bez zmian asercji) i brama.
- [ ] **Step 3: Commit** — `feat(versions): sygnal metadata (wydanie), use_local/store_file i tory landcover/hsg`

---

### Task 3: Segmenty i sloty land cover

**Files:**
- Create: `kartograf/landcover/store.py`, `tests/test_landcover_store.py`

**Interfaces:**
```python
HSG_SEGMENT_PREFIX = "hsg/global_soilgrids"

def landcover_segment(descriptor_key: str, tokens: Sequence[str]) -> str
    # get_source(key).storage_subdir + "_" + "_".join(t.lower()); token [a-z0-9.-]+ else ValidationError
def hsg_segment(depth: str, stat: str) -> str
def selection_slot(output_dir: Path, segment: str, ext: str, *, teryt: str | None = None,
                   bbox: BBox | None = None, sheet: str | None = None) -> FileSlot   # exactly one
def selection_unit(*, teryt=None, bbox=None, sheet=None) -> str
```

- [ ] **Step 1: Testy** — `test_segments_lowercase_and_tokens` (BDOT10k `gpkg`, `gpkg_ptwp-swrs` z `["SWRS", "PTWP"]`, `gpkg_zip`, `shp`; CORINE `eu_corine_2018`, `eu_corine_1990_preview`; SoilGrids `global_soilgrids_clay_0-5cm_q0.05`; HSG `hsg/global_soilgrids_0-5cm_mean`), `test_segment_rejects_unsafe_token`, `test_teryt_slot_paths`, `test_bbox_slot_matches_cutout_convention` (`bbox_cutout_path`, `.10g`), `test_sheet_slot_uses_sheet_hierarchy` (`N-34-130-D` i godlo z zerem wiodacym -> kanoniczne), `test_selection_slot_requires_exactly_one`.
- [ ] **Step 2: Implementacja** i brama.
- [ ] **Step 3: Commit** — `feat(landcover): segmenty i sloty land cover w ukladzie data/ (spec 3.4)`

---

### Task 4: `LandCoverManager` — SoilGrids i CORINE w magazynie

**Files:**
- Modify: `kartograf/landcover/manager.py` (101-415, 584-697), `kartograf/__init__.py` (42-45, 104-105, 174-175)
- Test: `tests/test_landcover.py` (`TestLandCoverManagerDownload`, `TestSidecarLandCover`, `TestLandCoverNoSideEffectsOnInit`), `tests/test_landcover_output_params.py` (przepisany: parametry tresci w segmencie i w `request`), `tests/test_soilgrids.py` (`TestSoilGridsManager`)

**Interfaces:**
```python
@dataclass(frozen=True)
class LandCoverResult:
    unit: str
    file: VersionedFile
    raw: VersionedFile | None = None        # BDOT10k keep_raw ZIP
    stale: tuple[PlanItem, ...] = ()

class LandCoverManager:
    def __init__(self, output_dir: str | Path, provider: LandCoverProvider | str,
                 cache: MetadataCache | None = None)            # output_dir = store root (--output)
    def download(self, teryt=None, bbox=None, sheet=None, *, update: UpdateMode | None = None,
                 plan: UpdatePlan | None = None, **kwargs) -> LandCoverResult
    def download_by_teryt(self, teryt, *, update=None, plan=None, **kwargs) -> LandCoverResult
    def download_by_bbox(self, bbox, *, update=None, plan=None, **kwargs) -> LandCoverResult
    def download_by_sheet(self, sheet, *, update=None, plan=None, **kwargs) -> LandCoverResult
    def check(self, teryt=None, bbox=None, sheet=None, **kwargs) -> UpdatePlan   # track "landcover"
    def download_batch(self, items, max_workers=4, **kwargs) -> list[LandCoverResult]
```

Przeplyw (raster): `params = _content_params(kwargs)` (bez zmian) -> segment (SoilGrids `(property, depth, stat)`; CORINE `uses_clms(year)` ? `(year,)` : `(year, "preview")`) -> `selection_slot` (`.tif`; podglad `.png`) -> `fetch_version(signal=channel_signal(key, kanal), edition=<memo provider.edition(...)> dla metadata, version=VersionRef.downloaded() dla podgladu, fetch=lambda staged: provider.download_by_*(..., staged, **kwargs) i None)`; sidecar wersji: `emit_sidecar(key, data, request={**request, **params}, ..., extra={**fallback, "edition": edition.to_extra()} , exclusive=True, digest=, version=)` (CORINE PNG: `horizontal_crs` i `extra.fallback` jak dzis). `plan=`: `select_planned(plan, [check(...) item], "landcover")` -> pozycja `todo` pobierana z `update="upgrade"`, `stale` w wyniku, pozycja spoza planu -> lokalna/brak bez pobrania. Usuniete: `output_path`, `_generate_output_path`, `_source_prefix`, `_write_sidecar` (zastapione sidecarem wersji).

- [ ] **Step 1: Testy** — `test_soilgrids_lands_as_edition_version` (`soil/global_soilgrids_clay_0-5cm_mean/sheet-hierarchia/<godlo>.tif`, wersja `2.0_<sha8>`, `extra.edition`, hardlink), `test_soilgrids_default_local_one_capabilities_no_wcs` (atrapa: 1 GetCapabilities, 0 GetCoverage), `test_soilgrids_new_edition_default_info_upgrade_downloads` (`newer="2.1"` / pobranie, etykieta `2.1`), `test_soilgrids_edition_unavailable_without_local_is_error` (0 GetCoverage), `test_soilgrids_edition_unavailable_with_local_warns` (`unverified` check_failed), `test_soilgrids_force_same_content_unchanged`, `test_check_soilgrids_never_downloads` (`missing`/`current`/`newer`/`check_failed`), `test_corine_clms_segment_and_edition` (atrapa tokenu, `eu_corine_2018/`, etykieta `V2020_20u1`), `test_corine_preview_separate_segment_downloaded_label` (bez tokenu: `eu_corine_2018_preview/...png`, `extra.fallback`, sygnal `none`; wersja nigdy w `eu_corine_2018/`), `test_corine_1990_preview_only`, `test_manager_has_no_output_path` (`TypeError` dla `output_path=`), `test_upgrade_plan_stale_and_removed_items` (zmienione wydanie od planu = `stale`, bez pobrania), `test_no_dir_created_on_init` (zachowane z `TestLandCoverNoSideEffectsOnInit`).
- [ ] **Step 2: Implementacja** — testy SoilGrids/CORINE zielone; testy BDOT10k menedzera (nowe sygnatury wspolne) przepisuje Task 5, wiec Task 4 nie ma osobnego commitu ani bramy calosci.
- [ ] **Step 3:** Bez commitu — Task 5 konczy sie wspolnym commitem obu zadan.

---

### Task 5: `LandCoverManager` — BDOT10k w magazynie

**Files:**
- Modify: `kartograf/landcover/manager.py` (`download_by_teryt`/`bbox`/`sheet` galezie BDOT10k, `download_all_counties` 388-415, `_download_county` 437-466, `_write_bdot_sidecars` 468-494)
- Test: `tests/test_landcover.py` (`TestLandCoverManagerDownload`, `TestSidecarLandCover`, `TestBdot10kShpFormat`, testy `keep_raw`/`raw_path`, `download_all_counties`), `tests/test_landcover_output_params.py` (`TestBdot10kOutputParams`)

**Interfaces:**
```python
@dataclass(frozen=True)
class LandCoverFailure:
    unit: str
    error: str

@dataclass(frozen=True)
class LandCoverAreaResult:
    files: tuple[LandCoverResult, ...]
    failed: tuple[LandCoverFailure, ...] = ()
    stale: tuple[PlanItem, ...] = ()

def download_all_counties(self, *, bbox=None, sheet=None, update=None, plan=None,
                          **kwargs) -> LandCoverAreaResult      # errors per powiat, the rest continues
def check_all_counties(self, *, bbox=None, sheet=None, **kwargs) -> UpdatePlan
```

Przeplyw (decyzja 9): sloty `teryt/<T>` w segmencie GPKG (z warstwami) albo SHP, przy `keep_raw` takze ZIP; `use_local` (sygnal `none`) dla kazdego; gdy ktorykolwiek `None` — `download_package` do `.incoming/` obu segmentow, `store_file` ZIP, potem GPKG z `extra.source_files`. Sidecar wersji: `request` (`teryt` albo wybor), `extra.source` (`url`, `teryt`, `format`), `extra.http`, `extra.parent_request` (obszar), bez `raw_file` (zastapione `source_files`). `download_by_bbox`/`download_by_sheet` dla BDOT10k: jeden powiat jak dzis (`ValidationError` przy kilku), wynik w `teryt/<T>` z `extra.parent_request`. PRG dziala jak dzis (cache; `--force` = `MetadataCache(refresh=True)` w CLI).

- [ ] **Step 1: Testy** — `test_bdot_gpkg_version_and_link` (`landcover/pl_bdot10k_gpkg/teryt/1465.gpkg`), `test_bdot_layers_segment_lowercase_sorted`, `test_bdot_shp_segment_zip`, `test_bdot_keep_raw_zip_own_version_and_source_files` (sha256 ZIP w `source_files` GPKG, `file` = sciezka wersji ZIP wzgledem `--output`), `test_bdot_keep_raw_missing_zip_triggers_one_download` (GPKG lokalny, ZIP brak -> 1 pobranie, GPKG `unchanged`), `test_bdot_default_local_without_package_request` (0 zapytan paczki), `test_bdot_force_same_content_unchanged_next_day` (`now` dzien+1 -> `unchanged`, ta sama etykieta), `test_bdot_upgrade_is_local_unverified_none`, `test_check_bdot_never_downloads` (`unverifiable`/`missing`), `test_all_counties_error_per_powiat` (drugi powiat `DownloadError`, pierwszy i trzeci w `files`, blad w `failed`), `test_bdot_area_parent_request_in_version_sidecar`, `test_bdot_failure_leaves_no_version_and_no_staging`.
- [ ] **Step 2: Implementacja** i brama.
- [ ] **Step 3: Commit** (Task 4 + 5) — `feat(landcover)!: land cover w magazynie wersji (wydania SoilGrids/CORINE, podglad CORINE, BDOT10k z keep_raw; D29-D32)`

---

### Task 6: HSG z wersji wejsc (D33)

**Files:**
- Modify: `kartograf/hydrology/hsg.py` (366-615), `kartograf/__init__.py`
- Test: `tests/test_hsg.py` (`TestHSGCalculator`, `TestHSGCalculatorCalculation`, `TestHSGCalculatorCalculateFull`, `TestHSGSidecar`, `TestHSGOutputDirOnWrite`; `TestHsgFromRasters` bez zmian)

**Interfaces:**
```python
@dataclass(frozen=True)
class HsgResult:
    unit: str
    file: VersionedFile                     # new / unchanged / reused / local
    inputs: tuple[LandCoverResult, ...]     # clay, sand, silt
    stale: tuple[PlanItem, ...] = ()

class HSGCalculator:
    def __init__(self, output_dir: str | Path, provider=None)
    def calculate_hsg_by_bbox(self, bbox, *, depth: str, stat: str, update: UpdateMode | None = None,
                              plan: UpdatePlan | None = None, timeout: int = 120) -> HsgResult
    def calculate_hsg_by_sheet(self, sheet, *, depth, stat, update=None, plan=None, timeout=120) -> HsgResult
    def check_hsg_by_bbox(self, bbox, *, depth, stat) -> UpdatePlan     # 3 x "landcover" + 1 x "hsg"
    def check_hsg_by_sheet(self, sheet, *, depth, stat) -> UpdatePlan
    def get_hsg_statistics(self, hsg_path: Path) -> dict                 # unchanged
```

Przeplyw (decyzja 11): wejscia przez `LandCoverManager(output_dir, self.provider)` (ten sam wybor: bbox -> `bbox/`, arkusz -> hierarchia godla); dowolny blad wejscia = wyjatek (HSG nie powstaje). Klasyfikacja jak dzis (`_classify_hsg`, `_write_hsg_geotiff`) z plikow wersji wejsc do `.incoming/` slotu HSG. `check_hsg_*`: pozycje wejsc z `LandCoverManager.check` + pozycja `hsg` (`current`, gdy jest wersja z sha256 BIEZACYCH lokalnych wejsc; inaczej `missing`).

- [ ] **Step 1: Testy** — `test_hsg_version_from_input_versions` (`hsg/global_soilgrids_0-5cm_mean/bbox/<wsp>.tif`, etykieta `2.0`, `source_files` z trzema sha256 i sciezkami wersji), `test_hsg_rerun_reused_no_compute` (atrapa `_classify_hsg` liczy wywolania = 0, 0 GetCoverage), `test_hsg_new_input_content_new_version` (`--force` wejscia clay z inna trescia -> nowa wersja HSG), `test_hsg_force_same_inputs_is_reused`, `test_hsg_mixed_editions_label` (`2.0+2.1`), `test_hsg_input_error_no_result`, `test_check_hsg_never_downloads_or_computes`, `test_hsg_sheet_and_bbox_distinct_paths` (koniec kolizji `hsg_bbox_<depth>.tif`), `test_hsg_no_keep_intermediate` (`TypeError`), `test_calculator_requires_output_dir`; usun `test_calculate_hsg_keep_intermediate` (587) i analog w `TestHSGOutputDirOnWrite` (816).
- [ ] **Step 2: Implementacja** i brama.
- [ ] **Step 3: Commit** — `feat(hsg)!: HSG w magazynie wersji z ponownym uzyciem wg wejsc (D33)`

---

### Task 7: CLI `landcover download`

**Files:**
- Modify: `kartograf/cli/_parser.py` (265-295 -> `add_update_flags`; 418-501), `kartograf/cli/commands.py` (54-58), `kartograf/cli/download_cmd.py` (1121-1144 -> `run_with_plan_file`; `_STATUS_TEXT` 1526-1531, `_print_version_summary` 1600-1609), `kartograf/cli/landcover_cmd.py` (129-272)
- Test: `tests/test_landcover.py` (`TestLandCoverCLI`, `TestBdot10kShpFormat`), `tests/test_landcover_output_params.py` (`TestLandCoverCliOutputParams`), `tests/test_cli_update_modes.py`

**Zachowanie:**
- Flagi `--check-updates`/`--upgrade`/`--force`/`--plan PLIK` (wzajemne wykluczanie jak w `download`; `--plan` bez trybu = blad parsera). Help: BDOT10k `none`, SoilGrids/CORINE wydanie, podglad CORINE `none`.
- `--check-updates`: linie `_plan_line` (`unit` = TERYT / wspolrzedne / godlo), `--plan` zapisuje plan; `check_failed` = kod 1.
- Pobranie: linia statusu na plik (`_report_file`; BDOT10k `keep_raw` — dwie linie), BDOT10k wielu powiatow — linie + `_print_version_summary`, `Error: <TERYT>: ...` per powiat, kod 1 przy jakimkolwiek bledzie (czesciowy sukces, ARCHITECTURE 4.2). `newer` wydania: `lokalna wersja 2.0; dostepna nowsza 2.1 (--upgrade)`.
- `--force`: `_cli_metadata_cache(True)` (odswiezenie PRG) dla BDOT10k.
- `Downloaded to:` znika (BREAKING; zastapione liniami statusu ze sciezka standardowa w podsumowaniu).

- [ ] **Step 1: Testy** — `test_landcover_update_flags_exclusive`, `test_landcover_plan_without_mode_is_error`, `test_landcover_check_writes_plan` (pozycje `landcover`), `test_landcover_upgrade_plan_stale_exit_1`, `test_landcover_status_lines_and_summary` (BDOT10k 2 powiaty, jeden blad -> kod 1, obie linie), `test_landcover_soilgrids_newer_edition_info`, `test_landcover_corine_preview_line` (bez tokenu); istniejace testy `Downloaded to:` i nazw plikow przepisane.
- [ ] **Step 2: Implementacja** (wyodrebnienie `run_with_plan_file` bez zmiany zachowania `download` — testy `tests/test_cli_update_modes.py` bez zmian asercji) i brama.
- [ ] **Step 3: Smoke offline** — `.venv/bin/kartograf landcover download --help`, `--plan` bez trybu (`Error`, kod 2), kody wyjscia z atrapami (testy wyzej).
- [ ] **Step 4: Commit** — `feat(cli)!: tryby aktualizacji i plan w landcover download`

---

### Task 8: CLI `soilgrids hsg`

**Files:**
- Modify: `kartograf/cli/_parser.py` (535-588: bez `--keep-intermediate`, `--output DIR`, `add_update_flags`, `--plan`), `kartograf/cli/commands.py`, `kartograf/cli/soilgrids_cmd.py` (41-187)
- Test: `tests/test_hsg.py` (`TestHSGCLI` 348; 385-392 `--keep-intermediate` usuniete)

**Zachowanie:** `--output` = katalog magazynu; wartosc z sufiksem `.tif` = `Error: --output to katalog magazynu (od 0.8.0); plik poza magazynem: hsg_from_rasters` (kod 1, przed siecia). Linie: trzy wejscia (`clay`/`sand`/`silt` + jednostka) i HSG (`uzyta ponownie <etykieta>` / `nowa wersja ...`); `--stats` czyta `result.file.path`; `--check-updates`/`--plan` jak Task 7 (pozycje `landcover` i `hsg`).

- [ ] **Step 1: Testy** — `test_hsg_cli_output_tif_rejected`, `test_hsg_cli_reused_line`, `test_hsg_cli_check_plan_tracks`, `test_hsg_cli_keep_intermediate_removed` (argparse: kod 2), `test_hsg_cli_stats_from_store_path`.
- [ ] **Step 2: Implementacja** i brama.
- [ ] **Step 3: Commit** — `feat(cli)!: soilgrids hsg w magazynie wersji (bez --keep-intermediate)`

---

### Task 9: Docstringi i publiczne API

**Files:**
- Modify: `kartograf/__init__.py` (docstring modulu 12-46, eksporty), docstringi klas `LandCoverManager` (59-99) i `HSGCalculator` (367-380) — przyklady na nowych sygnaturach.

- [ ] **Step 1:** Eksporty `LandCoverResult`, `LandCoverAreaResult`, `LandCoverFailure`, `HsgResult`, `Edition` w `__all__`; przyklady bez `output_path`, `keep_intermediate`, wyniku `Path`. Wyszukanie `output_path=` i `keep_intermediate` w `kartograf/landcover`, `kartograf/hydrology` (poza `hsg_from_rasters` i providerami) = brak.
- [ ] **Step 2:** Brama.
- [ ] **Step 3: Commit** — `docs(api): land cover i HSG w przykladach biblioteki (wyniki z wersja)`

---

### Task 10: Dokumentacja

**Files:**
- Modify: `docs/DECISIONS.md` (CRLF: ADR-036, ADR-026 status/errata), `docs/CHANGELOG.md` (`[0.8.0]`), `docs/ARCHITECTURE.md` (3.3, 4.8 od 1368), `docs/USAGE.md` (1.5 od 247, biblioteka 393-420, 481-482, 5 od 788), `docs/SCOPE.md` (2.6-2.8, 3.3 status podprojektu 1), `docs/PRD.md` (3.5-3.8, 520)

- [ ] **Step 1: DECISIONS** — ADR-036: D29-D33 (sygnaly `metadata`, brak wersji bez wydania, podglad CORINE, tylko magazyn, HSG z wersji wejsc), tabela sygnalow per kanal uzupelniona o land cover; ADR-026: land cover i HSG w ukladzie (spec 3.4, oznaczenie "realizacja w planie 3/3" zamienione na stan); indeks. Sprawdz CRLF: `.venv/bin/python -c "b=open('docs/DECISIONS.md','rb').read().split(b'\n'); print([i for i,l in enumerate(b[:-1],1) if not l.endswith(b'\r')][:5])"` -> `[]`.
- [ ] **Step 2: CHANGELOG `[0.8.0]` BREAKING** (kazdy z "Co zrobic"): sciezki land cover/HSG (segmenty 3.4, bez migracji — ponowne pobranie); `LandCoverManager`/`HSGCalculator` bez `output_path`, wyniki `LandCoverResult`/`LandCoverAreaResult`/`HsgResult` zamiast `Path` (Hydrograf: `download_landcover.py`, `cn_calculator.py`, `bootstrap.py` — uzyc `result.file.path`; plik poza magazynem: `provider.download_by_*` / `hsg_from_rasters`); `HSGCalculator(output_dir)`; usuniete `keep_intermediate`/`--keep-intermediate`; `soilgrids hsg --output` tylko katalog; `download_all_counties` nie przerywa na pierwszym bledzie; brak `Downloaded to:`; land cover nie pobiera ponownie istniejacego wyniku. Naprawione: UID-y CLMS 2012/2006/2000, kolizja `hsg_bbox_<depth>.tif`. Dodane: `--check-updates`/`--upgrade`/`--force`/`--plan` w `landcover download` i `soilgrids hsg`, `extra.edition`, `Edition`.
- [ ] **Step 3: ARCHITECTURE/USAGE/SCOPE/PRD** — 4.8 przepisane (segmenty, sygnaly, wydania, podglad, HSG `reused`), przyklady CLI z liniami statusu, przyklady biblioteki, ograniczenie: poprawka w obrebie wydania wykrywa tylko `--force`; CLMS na zywo niesprawdzony.
- [ ] **Step 4: Commit** — `docs: magazyn wersjonowany dla land cover i HSG (ADR-036 D29-D33, CHANGELOG)`
- [ ] **Step 5: PROGRESS** — na `develop` (galaz nie zmienia `docs/PROGRESS.md`): sesja, stan planu 3/3, nastepny krok (Task 11-12).

---

### Task 11: E2E calosci na zywo

**Files:** `docs/research/<data>-store-e2e/raport.md` (NOWY; sciezka danych jako `<katalog-danych>`); w repo poza raportem tylko testy odtwarzajace bledy.

Katalog danych testow na zywo: wskazany przez uzytkownika 2026-10-12 (NIE zapisywac). Swiezy `--output` per scenariusz, polecenia sekwencyjne, cache CLI w korzeniu repo.

- [ ] **Step 1: BDOT10k** (`--teryt 1465`, GPKG): pobranie -> rerun (`lokalna wersja ... (bez sprawdzania; --check-updates)`, zero pobran paczki) -> `--check-updates --plan` (`nie da sie sprawdzic bez pobrania`) -> `--force` (`bez zmian` wg powtarzalnosci z inwentaryzacji) ; listing `versions/teryt/`, `nlink` = 2. Wariant `--bbox` z 2 powiatami: dwie linie, `extra.parent_request`.
- [ ] **Step 2: SoilGrids** (maly bbox, `clay 0-5cm mean`): pobranie (`2.0_<sha8>`, `extra.edition`) -> rerun (1 GetCapabilities, 0 GetCoverage) -> `--check-updates` (`aktualne (2.0)`) -> `--upgrade` (lokalna) -> `--force` (`bez zmian`).
- [ ] **Step 3: CORINE bez credentials** (`--year 2018 --sheet ...`): `eu_corine_2018_preview/...png`, etykieta daty; rerun lokalny; `-m live` test wydania CLMS (Task 1 Step 2) zielony.
- [ ] **Step 4: HSG** (`soilgrids hsg --bbox ... --depth 0-5cm`): wejscia + `nowa wersja 2.0_<sha8>` -> rerun (`uzyta ponownie`) -> `--force` (wejscia `bez zmian`, HSG `uzyta ponownie`) -> `--check-updates --plan` (pozycje `landcover` x3 i `hsg`).
- [ ] **Step 5: Regresja calosci magazynu** — po jednym scenariuszu z planow 1/3 i 2/3 na swiezym `--output`: arkusz PL (`--sheet`, kampanie), LAZ (bbox), CZ SM5, wycinek PL `--target-crs EPSG:2180`, `--country auto --check-updates --plan` -> `--upgrade --plan`.
- [ ] **Step 6:** Raport (komendy, kody wyjscia, listingi `versions/`, liczby hardlinkow; bez sciezki katalogu danych), commit `docs(research): E2E magazynu wersjonowanego (plan 3/3)`. Kazda niezgodnosc: test odtwarzajacy (failing), poprawka, osobny commit.

---

### Task 12: Galaz do `develop`

**Files:** brak zmian kodu.

- [ ] **Step 1:** `git rebase develop` (PROGRESS tylko z `develop`; konflikty dokumentow rozwiazac na korzysc obu tresci), pelna brama na wyniku rebase.
- [ ] **Step 2:** Za zgoda uzytkownika: merge `feat/versioned-store` do `develop` (`--no-ff`), push `develop` i `push --force-with-lease` galezi albo jej usuniecie — decyzja uzytkownika.
- [ ] **Step 3: PROGRESS** na `develop`: podprojekt 1 roadmapy zrealizowany na `develop`; przed wydaniem 0.8.0: Hydrograf/Hydrolog (CHANGELOG [0.8.0] "Co zrobic"), backlog (CLMS z credentials, CLMS 1990 jako dane).
