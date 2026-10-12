# Magazyn wersjonowany — plan 2/3: sygnaly, LAZ, CZ, wycinki `bbox/` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Data:** 2026-10-12

**Goal:** Wszystkie pozostale tory `kartograf download` na magazynie wersji z planu 1/3 — kafle LAZ, arkusze CZ (TM33/SM5), wycinki CZ i wycinki PL z WCS w `bbox/` — z sygnalem swiezosci per kanal zrodla (`index`/`http`/`none`, inwentaryzacja spec 8), `extra.http` w sidecarze wersji, trybami `update` (domyslny / `check` / `upgrade` / `force`) i planem `kartograf-plan/1` obejmujacym kazdy tor; usuniete `DownloadManager.download_bbox` (D27) i tymczasowe odrzucenie `--check-updates`/`--upgrade` z planu 1/3 (decyzja implementacyjna 8).

**Architecture:** Nowy modul `kartograf/download/fetch.py` — jedna polityka "plik bez kampanii na wersjach" (lokalna / sprawdzenie sygnalu / pobranie do `.incoming/` / `commit_version` / dowiazanie), uzywana przez LAZ, CZ, oba wycinki i tor `_fetch_sheet_plain` w `DownloadManager` (zastepuje jego wlasna kopie logiki). Typy planu (`PlanItem`, `UpdatePlan`) przechodza do `kartograf/download/plan.py` z polem `track`, zeby tory spoza `DownloadManager` budowaly i wykonywaly pozycje bez importu menedzera. `commit_version` dostaje sygnal `http` (D23 dla zrodel bez etykiety edycji). Transport: `response_signal`, `download_to(on_response=)`, `head_signal`. Arkusz CZ przechodzi z CLI do biblioteki (`download/cz_sheets.py`).

**Spec:** `docs/superpowers/specs/2026-10-08-versioned-store-design.md` — ZAAKCEPTOWANY 2026-10-11 (D1-D24), rewizja 2026-10-12 (D26-D28, decyzje uzytkownika; D25 odrzucone). Numeracja decyzji (Dn) odnosi sie do specu.

**Plan 1/3:** `docs/superpowers/plans/2026-10-08-versioned-store-1-core-pl-sheets.md` — wykonany na galezi `feat/versioned-store` (`52c2b94`..`d3b1314`, poprawka `1c84b3e`). Jego "Global Constraints" obowiazuja bez zmian; decyzje implementacyjne 1-10 obowiazuja, z wyjatkiem 1 (rozszerzona o sygnal `http`, nizej decyzja 3) i 8 (usuwana w Task 11).

**Poza planem 2/3 (plan 3/3):** land cover (BDOT10k, CORINE, SoilGrids) i HSG w ukladzie `data/` (D11), `keep_raw`, `source_files[]` w `calculate_hsg_by_bbox`, flagi trybow w `landcover`/`soilgrids`, pelna dokumentacja i E2E calosci. Inwentaryzacja (Task 1) obejmuje TAKZE zrodla planu 3/3 (spec 8: "pierwsze zadanie planu" przed implementacja sekcji 4) — plan 3/3 korzysta z jej raportu i fixtur. Galaz trafia do `develop` dopiero po planie 3/3.

---

## Weryfikacja specu wzgledem stanu po planie 1/3 (2026-10-12)

Wynik przegladu specu, kodu galezi i probnych zapytan `HEAD` (2026-10-12, bez pobierania danych):

1. **LAZ (rozstrzygniete D26):** nazwa pliku kafla = `<zgloszenie>_<rekord>_<godlo>.laz` (`LazTile.filename`, `kartograf/providers/pl/gugik_laz.py:133-135`; fixtury `tests/fixtures/gugik_laz/real_2026_10_1*/`), wiec nowszy nalot to inne pliki, czesto inne godla (PL-1992 vs PL-2000). Regula D5 "lokalna wersja + `Info:`" nie ma tu odpowiednika per plik; uzytkownik wybral wersjonowanie per plik i wyjatek od D5 dla LAZ. `HEAD` kafla LAZ (`opendata.geoportal.gov.pl`): tylko `Content-Length`, bez `ETag`/`Last-Modified`.
2. **`DownloadManager.download_bbox` (rozstrzygniete D27):** od v0.2.0 (`dace652`, 2026-01-18, ADR-004) pisze `output_dir / filename` w korzeniu magazynu i zawsze nadpisuje (`kartograf/download/manager.py:1817-1879`); dubluje `download_pl_cutout(EPSG:2180)` bez maski PRG; Hydrograf go nie wola (`Hydrograf/docs/integrations/KARTOGRAF.md:459`), Hydrolog/IMGWTools — brak wystapien. Usuwane.
3. **`Content-Length` jako sygnal uzupelniajacy (rozstrzygniete D28):** nie.
4. **`update_signal` per kanal, nie per deskryptor (doprecyzowanie w spec 4.1):** `cz.cuzk.dmr4g` ma kanal plikow SM5 (`openzu`, `HEAD` 2026-10-12: `ETag` i `Last-Modified` obecne) i kanal `exportImage` (bez sygnalu tresci); `pl.gugik.nmt_1m` — arkusze ze skorowidza i WCS.
5. **CUZK `metadata`:** JSON uslugi `ags.cuzk.gov.cz/.../dmr5g/ImageServer?f=json` nie ma pola edycji/daty (klucze sprawdzone 2026-10-12; `ETag` dotyczy dokumentu JSON, nie tresci rastra). Spodziewane: TM33 i wycinki CZ = `none`, SM5 = `http`. Potwierdza Task 1.
6. **D23 dla sygnalu `http`:** `commit_version` porownuje dzis tylko etykiety (`kartograf/download/versions.py:353-359`; decyzja 1 planu 1/3). Dla zrodla z etykieta `downloaded` i sygnalem `http` ta sama tresc pod nowym `ETag` musi dac `relabeled` (spec 3.1 pkt 3) — Task 4.
7. **Arkusz CZ tylko w CLI:** `_cz_download_sheet` (`kartograf/cli/download_cmd.py:2394-2458`) laczy pobranie, nodata, `mapname`/`cz_share` i sidecar. Tryby `update` sa w spec 4.2 parametrem biblioteki — przeniesienie do `download/cz_sheets.py` (Task 7).
8. **Plan aktualizacji jest PL-owy:** `PlanItem.sheet`, `upgrade(manager, plan)` (`kartograf/download/updates.py:34-55, 236-295`). Pozycje LAZ/CZ/wycinkow potrzebuja `track` i jednostki zadania (godlo kafla, godlo CZ, wspolrzedne bbox) — Task 5.
9. **D24 juz obslugiwane przez `ensure_link`:** stary zwykly plik bez `extra.link` w sidecarze = nieznana sciezka, zastepowany hardlinkiem (`kartograf/download/links.py:232-270`). W planie 2/3 tylko testy regresji dla LAZ i CZ (Task 6, 7, 8).
10. **`_print_legacy_krovak_info`** (`kartograf/cli/download_cmd.py:1978`) czyta sidecar POMINIETEGO starego pliku CZ; po D10/D24 stary plik nigdy nie jest "lokalna wersja" — funkcja martwa, usuwana w Task 11.

Bez sprzecznosci w D1-D24 wzgledem kodu planu 1/3.

## Global Constraints

Jak w planie 1/3 (Python z `.venv`, brama przed kazdym commitem, Conventional Commits po polsku, autor `Daldek <git@debever.pl>` bez `Co-Authored-By`, straznik wzorcow commitow, angielskie identyfikatory, CRLF w `docs/DECISIONS.md`, dane na zywo poza repo i poza `/tmp` z jawnym `--output`, testy zachowania zamiast okablowania). Dodatkowo:

- Stale: `TRACKS = ("pl_sheet", "laz_tile", "cz_sheet", "pl_cutout", "cz_cutout")`; `SignalKind = Literal["index", "metadata", "http", "none"]`.
- Testy stare, ktore pinuja usuwane zachowanie (`force: bool` w LAZ/CZ, `skipped`, nazwa wycinka z data, `DownloadManager.download_bbox`, `_reject_update_modes`), usuwaj albo przepisuj — bez podwojnych sciezek.
- Task 1 wymaga sieci i katalogu danych testow na zywo — zapytaj uzytkownika o katalog na poczatku Task 1 (sciezki nie zapisuj w repo).

## Decyzje implementacyjne (bez nowych decyzji produktowych)

1. **Sygnal per kanal:** `AccessChannel.update_signal: SignalKind` (domyslnie `"none"`); wartosc wg Task 1. Tor wybiera kanal, ktorym pobiera (np. SM5 = kanal `DIRECT_FILES`, TM33 i bbox = `exportImage`).
2. **Porownanie sygnalu `http`:** rowne, gdy oba maja `etag` i sa rowne; gdy lokalny nie ma `etag` — gdy oba maja rowne `last_modified`; w pozostalych przypadkach "niesprawdzalne" (`unverifiable`, jak `none`). `content_length` nie bierze udzialu (D28).
3. **D23 dla `http`:** `commit_version(..., signal=)`; przy tym samym sha256 i etykiecie `downloaded` — `unchanged`, gdy ktoras wersja o tym sha ma rowny sygnal (decyzja 2) albo sygnal jest `None`; w przeciwnym razie `relabeled` z dzisiejsza etykieta `downloaded`. Katalog `<dzis>_<sha8>` juz istnieje (ponowne pobranie tego samego dnia) = `unchanged` (istniejacy krok 5 specu 3.1).
4. **Tryb domyslny przy `http`:** jedno `HEAD` na plik z lokalna wersja (tani sygnal, spec 4.2 kolumna "Domyslnie"); blad `HEAD` = lokalna + `Warning:`; `--upgrade` = blad tego pliku.
5. **LAZ (D26):** etykieta `<akt_data>_<zgloszenie>` (`label_source="campaign"`; brak `akt_data` = `<akt_rok>_<zgloszenie>`), `zgloszenie` = pierwszy segment nazwy pliku. Brak `extra.campaign` w sidecarze LAZ, wiec `version_key` uzywa daty z etykiety (istniejaca galaz `kartograf/download/versions.py:228-233`). Domyslnie i `--upgrade`: kafel z lokalna wersja = `local`; `--force` pobiera ponownie; `--check-updates`: pozycje `current`/`missing` dla kafli selekcji (nigdy `newer` — nowszy nalot to nowe pozycje `missing`).
6. **Wycinki (PL WCS, CZ) i TM33:** sygnal `none` (o ile Task 1 nie wykaze inaczej); etykieta `downloaded`. Wynik lokalnej wersji odtwarza pola wyniku (`all_nodata`, `masked_pixels`, `zero_pixels`) z sidecara wersji, bez odczytu rastra.
7. **Plan aktualizacji:** `PlanItem.sheet` -> `PlanItem.unit` + nowe pole `track`; schemat zostaje `kartograf-plan/1` (galaz nie wydana). `upgrade(manager, plan)` wykonuje tylko `track == "pl_sheet"`; pozostale tory dostaja `plan=` w swoich funkcjach `run_*` i wspolny wybor `select_planned(plan, fresh, track)` (pozycje usuniete z planu nie sa wykonywane, zmieniony sygnal = `stale`). CLI `--country auto` laczy plany PL i CZ (`UpdatePlan.merge`, ten sam `store`).
8. **Wyniki torow:** wspolny `VersionedFile` (sciezka standardowa, status `new`/`unchanged`/`relabeled`/`local`, etykieta, sha256, sciezka wersji, `newer`, `unverified`) zamiast `skipped`/`downloaded`; `LazDownloadResult.files`, `CzCutoutResult`/`PlCutoutResult`/`CzSheetResult` z polem `file: VersionedFile` i `stale: tuple[PlanItem, ...]`.
9. **Brak publicznego API arkusza CZ:** `download/cz_sheets.py::run_cz_sheet` jak `run_cz_cutout` — warstwa biblioteki dla CLI, bez eksportu w `kartograf/__init__.py` (nowe API publiczne poza zakresem).

## Review Focus

1. **Jedna polityka trybow dla plikow bez kampanii:** LAZ, CZ, wycinki i `_fetch_sheet_plain` przechodza przez `fetch_version`; zadna z nich nie ma wlasnej galezi "plik istnieje". Task 4 `test_fetch_version_matrix` (tabela 4.2 x `none`/`http`/`index`), Task 6-9 testy torow.
2. **D23 dla `http`:** ta sama tresc pod nowym `ETag` = `relabeled`, pod tym samym = `unchanged`, bez sygnalu = `unchanged`. Task 4 `test_commit_same_content_new_etag_is_relabeled`, `test_commit_same_content_same_etag_is_unchanged`.
3. **`--check-updates` nigdy nie pobiera:** zadne `download_to`/`export_image` w trybie `check` dla zadnego toru (sesje-atrapy liczace wywolania). Task 6-9 `test_check_*_never_downloads`.
4. **Plan nieaktualny per tor:** pozycja LAZ, ktorej kafel zniknal z selekcji, oraz pozycja SM5 z innym `ETag` niz w planie = `stale`, bez pobrania. Task 6 `test_laz_upgrade_plan_stale_tile`, Task 7 `test_cz_sm5_upgrade_plan_etag_changed_is_stale`.
5. **D26:** nowszy nalot LAZ pobiera sie domyslnie, kafel z lokalna wersja nie. Task 6 `test_laz_default_keeps_local_tile_and_fetches_new_flight`.
6. **D24:** stary zwykly plik 0.7.x w sciezce LAZ/CZ zastapiony dowiazaniem bez komunikatu. Task 6 `test_laz_legacy_plain_file_replaced_by_link`, Task 7 i 8 analogicznie.
7. **D15:** `bbox/<wsp>.tif` bez daty; domyslnie lokalna wersja bez sieci (bez PRG i WCS); `--force` z ta sama trescia = `unchanged`. Task 9.

---

## Mapa plikow

| Plik | Odpowiedzialnosc |
|---|---|
| `docs/research/2026-10-1x-signal-inventory/raport.md` (NOWY), `tests/fixtures/signals/real_<data>/` (NOWE) | Task 1: wyniki inwentaryzacji, nagrane naglowki |
| `kartograf/sources/descriptor.py`, `kartograf/sources/registry.py` | `AccessChannel.update_signal`, wartosci per kanal |
| `kartograf/transport/http.py` | `response_signal`, `download_to(on_response=)`, `head_signal` |
| `kartograf/providers/pl/bdot10k.py` | naglowki przez `response_signal` (jedna konwencja; sidecar land cover bez zmian do planu 3/3) |
| `kartograf/download/versions.py` | `commit_version(signal=)`, `http_signal_of(version)`, `same_http_signal` |
| `kartograf/download/fetch.py` (NOWY) | `FileSlot`, `VersionedFile`, `fetch_version`, `inspect_version` |
| `kartograf/download/plan.py` (NOWY) | `PlanItem` (`track`, `unit`), `UpdatePlan` (+ `merge`), `ItemStatus`, `PLAN_SCHEMA`, `select_planned` |
| `kartograf/download/updates.py` | `check_updates`/`upgrade` dla `pl_sheet` na typach z `plan.py` |
| `kartograf/download/storage.py` | `get_raw_versions_root`, `get_raw_versions_base`, `bbox_slot` |
| `kartograf/download/manager.py` | `_fetch_sheet_plain` na `fetch_version`; usuniete `download_bbox` |
| `kartograf/download/laz.py` | LAZ na wersjach (D26), `update=`, `plan=`, `check_laz_updates` |
| `kartograf/providers/cuzk/client.py`, `kartograf/providers/cuzk/dmr.py` | `on_response` w `fetch_file`/`download`, `sm5_signal(sheet)` (`HEAD`) |
| `kartograf/download/cz_sheets.py` (NOWY) | `run_cz_sheet`, `check_cz_sheet` (z CLI `_cz_download_sheet`) |
| `kartograf/download/cz_cutout.py` | wycinek CZ na wersjach, `update=` zamiast `force=`, `check_cz_cutout` |
| `kartograf/download/cutout.py` | wycinek PL na wersjach (D15), bez `dated_cutout_path`, `update=`, `check_pl_cutout` |
| `kartograf/cli/_parser.py`, `kartograf/cli/download_cmd.py` | tryby dla wszystkich torow `download`, plan laczony, linie statusu; bez `_reject_update_modes`, `_cz_download_sheet`, `_print_legacy_krovak_info` |
| `kartograf/__init__.py` | `PlanItem`/`UpdatePlan` z `download/plan.py` (te same nazwy, `kartograf/__init__.py:85-90`); NOWE eksporty `VersionedFile`, `check_laz_updates`, `check_cz_cutout`, `check_pl_cutout` (obok `run_*`/`download_*` tych torow, 61-76, 144-167) — kazdy w zadaniu, ktore go tworzy; przyklady w docstringu modulu (12-37) bez `skipped`/`force` |
| `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `docs/SCOPE.md`; `docs/PROGRESS.md` na `develop` | ADR-036 (D26-D28, realizacja W-U3/W-U8), errata ADR-004, BREAKING |

Fakty o obecnym kodzie (zweryfikowane 2026-10-12 na `feat/versioned-store` `1c84b3e`):
- `commit_version(staged, versions_root, name, version, digest, write_sidecar)` — `kartograf/download/versions.py:315-407`; dedupe po etykiecie 350-359; `version_key` 213-233; `read_version` 167-188.
- `_fetch_sheet_plain` — `kartograf/download/manager.py:1133-1199` (lokalna bez `force`, pobranie do `.incoming`, `commit_version` z `VersionRef.downloaded()`, `_link`); `download_bbox` 1817-1879; `_write_sidecar(..., digest=, version=)` 1935-1981.
- `PlanItem`/`UpdatePlan`/`UpgradeReport`/`_item` — `kartograf/download/updates.py:34-122`; `_items` 151-213; `check_updates` 216-233; `upgrade` 236-295.
- LAZ: `write_laz_sidecar` `kartograf/download/laz.py:85-150`, `run_laz_download` 152-246 (`fetch` z `not force and target.exists()` 192-212), `download_laz_area` 249-349; `LazTile.filename` `kartograf/providers/pl/gugik_laz.py:133-135`, `GugikLazProvider.download` 964-1000; `FileStorage.get_raw_path(identifier, filename, *, system)` `kartograf/download/storage.py:292-349`.
- CZ: `run_cz_cutout(provider, bbox, *, output_dir, image_crs, force, parent_request, on_download)` `kartograf/download/cz_cutout.py:97-167`, `download_cz_cutout` 170-212, `write_cz_sidecar` 59-94; CLI `_run_cz` `kartograf/cli/download_cmd.py:647`, `_cz_download_sheet` 2394-2458, `_cz_download_bbox` 2475-2531, `_cmd_download_cz` 2534-2632; `CuzkDmrProvider.download` `kartograf/providers/cuzk/dmr.py:218-260`, `_download_sm5` 375-408, `CuzkClient.fetch_file` `kartograf/providers/cuzk/client.py:108-131`, `export_image` 133-.
- Wycinek PL: `PlCutoutResult` `kartograf/download/cutout.py:104-116`, `dated_cutout_path` 250-253, `write_pl_wcs_cutout_sidecar` 283-341, `run_pl_wcs_cutout` 344-446, `download_pl_cutout` 449-498; `bbox_cutout_path` `kartograf/download/storage.py:651-664`.
- Transport: `download_to(session, url, output_path, *, timeout, retries, description, validate, save, chunk_size)` `kartograf/transport/http.py:211-282`; BDOT10k zbiera naglowki samodzielnie `kartograf/providers/pl/bdot10k.py:266-270`.
- CLI: odrzucenie trybow `kartograf/cli/download_cmd.py:1178-1185, 1211-1212, 1391-1399`; `_update_mode` 1402-1407; `_plan_line` 1438; `_run_plan_modes` 1451-1497; `_status_lines` 1499-1515; `_print_version_summary` 1518; `_download_pl_cutout` 1999-2104; `_cmd_download_laz` 2251-2371; `--upgrade`/`--plan` help `kartograf/cli/_parser.py:273-295`; `--plan` bez trybu `kartograf/cli/commands.py:55-58`.
- Deskryptory: `AccessChannel` `kartograf/sources/descriptor.py:39-53`; rejestr `kartograf/sources/registry.py` (`pl.gugik.nmt_1m` 78, `nmt_5m` 108, `nmpt` 129, `orto` 159, `laz` 177, `bdot10k` 197, `eu.clms.corine` 215, `global.isric.soilgrids` 235, `cz.cuzk.dmr5g` 254, `cz.cuzk.dmr4g` 289).
- Testy: `tests/test_versions.py`, `tests/test_updates.py`, `tests/test_laz_download.py` (`FakeProvider`, `_tile`, `wfs_session`), `tests/test_laz_campaigns.py`, `tests/test_cz_cutout.py`, `tests/test_cuzk_dmr.py`, `tests/test_pl_cutout.py`, `tests/test_transport_http.py`, `tests/test_sources_registry.py`, `tests/test_download_manager.py` (`download_bbox` 680-720), `tests/test_cli.py` (`TestCmdDownloadLaz` 4258, `TestCzDownloadingAfterValidation` 5022, `TestCmdDownloadCz` 5295), `tests/test_cli_update_modes.py`.

---

### Task 1: Inwentaryzacja sygnalow na zywo (spec 8)

**Files:**
- Create: `docs/research/<data>-signal-inventory/raport.md`, `tests/fixtures/signals/real_<data>/<zrodlo>_<obiekt>.json` (status, wybrane naglowki: `ETag`, `Last-Modified`, `Content-Length`, `Content-Type`, `Digest`, `Cache-Control`; dla GetCapabilities/metadanych — surowa odpowiedz obok)
- Modify: `docs/superpowers/specs/2026-10-08-versioned-store-design.md` (sekcja 8: wyniki; 4.6: powtarzalnosc bajtowa) i ta tabela "Przyporzadkowanie" nizej, jesli wynik rozni sie od oczekiwanego

Przed startem: zapytaj uzytkownika o katalog danych testow na zywo; komendy z jawnym `--output` w tym katalogu.

- [ ] **Step 1: `HEAD` i `GET` z naglowkami** (bez zapisu danych w repo) dla: arkusz NMT/NMPT/orto (`opendata.geoportal.gov.pl`, potwierdzenie 2026-10-08), kafel LAZ, paczka BDOT10k, CORINE (CLMS: wymaga `CLMS_CREDENTIALS`; bez nich — zapisz "nie sprawdzono"), SoilGrids WCS (GetCoverage + GetCapabilities: wersja zbioru), CUZK SM5 ZIP (`openzu`), CUZK `exportImage` (TM33 i bbox), CUZK `ImageServer?f=json` i usluga `Metadata` (rok aktualizacji), GUGiK WCS GetCoverage (wycinek) i GetCapabilities (data aktualizacji).
- [ ] **Step 2: Powtarzalnosc bajtowa** — ten sam obiekt dwa razy, porownanie sha256: wycinek PL WCS (maly bbox, EPSG:2180 i EPSG:3045), wycinek CZ (natywny i EPSG:2180), arkusz SM5, kafel TM33, maly kafel LAZ, GPKG BDOT10k skladany lokalnie (jeden powiat), warstwa SoilGrids (maly bbox). Komendy CLI dla torow CLI, biblioteka dla reszty.
- [ ] **Step 3: Raport** — tabela zrodlo/kanal -> naglowki, sygnal (`index`/`metadata`/`http`/`none`), etykieta (`campaign`/`edition`/`downloaded`; dokladna postac edycji dla CORINE `<rok>` i SoilGrids), powtarzalnosc (tak/nie, sha256 obu pobran).
- [ ] **Step 4: Porownanie z oczekiwanym przyporzadkowaniem** (ponizej). Roznica dla zrodla z planu 2/3 = zatrzymaj sie, opisz uzytkownikowi skutek dla Task 2-9 i popraw te tabele oraz spec 8 przed Task 2. Roznica dla zrodla planu 3/3 = tylko raport i spec 8.

Oczekiwane przyporzadkowanie (z `HEAD` 2026-10-08 i 2026-10-12):

| Deskryptor / kanal | Sygnal | Etykieta | Tor |
|---|---|---|---|
| `pl.gugik.nmt_1m`/`nmt_5m`/`nmpt`/`orto` — arkusze | `index` | `campaign` | plan 1/3 (bez zmian) |
| `pl.gugik.nmt_1m`/`nmpt` — WCS | `none` | `downloaded` | `pl_cutout` |
| `pl.gugik.laz` — pliki | `index` (D26: plik = rekord) | `campaign` (decyzja 5) | `laz_tile` |
| `cz.cuzk.dmr4g` — pliki SM5 | `http` (`ETag`, `Last-Modified`) | `downloaded` | `cz_sheet` |
| `cz.cuzk.dmr4g`/`dmr5g` — `exportImage` | `none` | `downloaded` | `cz_sheet` (TM33), `cz_cutout` |
| `pl.gugik.bdot10k` | wg Task 1 (0.7.1: tylko `Content-Length` -> `none`) | wg Task 1 | plan 3/3 |
| `eu.clms.corine` | `metadata` (`year`) | `edition` `<rok>` | plan 3/3 |
| `global.isric.soilgrids` | wg Task 1 | wg Task 1 | plan 3/3 |

- [ ] **Step 5: Commit** — `docs(research): inwentaryzacja sygnalow swiezosci zrodel (spec 8)` (raport, fixtury, poprawki specu).

---

### Task 2: `update_signal` w kanalach deskryptorow

**Files:**
- Modify: `kartograf/sources/descriptor.py` (`AccessChannel` 39-53), `kartograf/sources/registry.py` (kanaly wszystkich deskryptorow wg Task 1)
- Test: `tests/test_sources_registry.py`

**Interfaces:**
```python
SignalKind = Literal["index", "metadata", "http", "none"]

@dataclass(frozen=True)
class AccessChannel:
    ...
    update_signal: SignalKind = "none"

def channel_signal(key: str, transport: TransportKind) -> SignalKind  # registry; unknown key/channel = ValidationError
```

- [ ] **Step 1: Testy** — `test_channel_signals_match_inventory` (parametryzowany tabela z Task 1: klucz, kanal -> sygnal), `test_unknown_channel_signal_is_error`.
- [ ] **Step 2: Implementacja** i brama.
- [ ] **Step 3: Commit** — `feat(sources): sygnal swiezosci per kanal dostepu (update_signal)`

---

### Task 3: Transport — naglowki odpowiedzi i `HEAD`

**Files:**
- Modify: `kartograf/transport/http.py` (`download_to` 211-282), `kartograf/providers/pl/bdot10k.py` (266-270: zbieranie naglowkow przez `response_signal`)
- Test: `tests/test_transport_http.py`, `tests/test_landcover.py` (asercje `pkg.http` ok. 2064-2067 i 2273-2276 bez zmian wartosci)

**Interfaces:**
```python
def response_signal(response: requests.Response) -> dict:
    """{"etag": str | None, "last_modified": str | None, "content_length": int | None}"""

def download_to(..., on_response: Callable[[requests.Response], None] | None = None) -> Path
    # called after validate, before writing; on a retried attempt called again (last attempt wins)

def head_signal(session, url: str, *, timeout: float, retries: int = MAX_RETRIES,
                description: str = "") -> dict
    # HEAD with the retry policy of get_with_retry; returns response_signal(...)
```

- [ ] **Step 1: Testy** — `test_response_signal_missing_headers_are_none`, `test_response_signal_non_numeric_length_is_none`, `test_download_to_on_response_sees_last_attempt` (pierwsza proba 503, druga 200 z `ETag`), `test_head_signal_retries_and_returns_headers`, `test_head_signal_404_is_download_error_without_retry`; BDOT10k: istniejace testy `http` przechodza bez zmian.
- [ ] **Step 2: Implementacja** (BDOT10k: `on_response=lambda r: headers.update(response_signal(r))` zamiast lokalnego parsowania) i brama.
- [ ] **Step 3: Commit** — `feat(transport): sygnal HTTP odpowiedzi (on_response, head_signal)`

---

### Task 4: Polityka plikow bez kampanii — `fetch.py`, `commit_version(signal=)`, sloty magazynu

**Files:**
- Create: `kartograf/download/fetch.py`, `tests/test_fetch.py`
- Modify: `kartograf/download/versions.py` (`commit_version` 315-407, dedupe 350-359), `kartograf/download/storage.py` (nowe metody obok `get_versions_root` 266 i `get_raw_path` 292), `kartograf/download/manager.py` (`_fetch_sheet_plain` 1133-1199 na `fetch_version`)
- Test: `tests/test_versions.py`, `tests/test_storage.py`, `tests/test_download_manager.py` (tor bez kampanii)

**Interfaces:**
```python
# versions.py
def http_signal_of(v: LocalVersion) -> dict | None          # extra.http of the version sidecar
def same_http_signal(local: dict | None, remote: dict | None) -> bool | None
    # decision 2: True/False; None = not comparable (unverifiable)
def commit_version(staged, versions_root, name, version, digest, write_sidecar,
                   *, signal: dict | None = None) -> VersionCommit
    # write_sidecar(data, version, digest) unchanged; the caller puts `signal` into extra.http

# storage.py
def get_raw_versions_root(self, identifier: str, *, system: str | None = None) -> Path
def get_raw_versions_base(self, identifier: str, *, system: str | None = None) -> Path
def bbox_slot(output_dir, subdir: str, bbox: BBox, extension: str) -> "FileSlot"
    # std = bbox_cutout_path(...); versions_base = <output>/<subdir>/versions; root = .../versions/bbox

# fetch.py
FileStatus = Literal["new", "unchanged", "relabeled", "local"]

@dataclass(frozen=True)
class FileSlot:
    std: Path            # standard (link) path
    versions_base: Path  # <segment>/versions (staging .incoming, D19)
    versions_root: Path  # <segment>/versions/<hierarchy>
    ext: str
    @property
    def name(self) -> str: ...

@dataclass(frozen=True)
class VersionedFile:
    path: Path
    status: FileStatus
    label: str
    sha256: str
    version_path: Path
    newer: str | None = None       # default mode: the source signal differs (Info)
    unverified: str | None = None  # "none" (no cheap signal) | "check_failed: <error>"

Fetch = Callable[[Path], dict | None]  # download into the staged path; returns the http signal or None
Probe = Callable[[], dict]             # current http signal (HEAD); raises DownloadError

def fetch_version(slot: FileSlot, update: UpdateMode | None, *, signal: SignalKind,
                  fetch: Fetch, version: VersionRef,
                  write_sidecar: Callable[[Path, VersionRef, ContentDigest, dict | None], None],
                  probe: Probe | None = None, coverage: bool = False) -> VersionedFile
def inspect_version(slot: FileSlot, *, track: str, unit: str, signal: SignalKind,
                    probe: Probe | None = None,
                    available: tuple[str | None, dict | None] = (None, None)) -> PlanItem
```

Regula `fetch_version` (tabela 4.2; lokalna = `newest_version(list_versions(root, name))`, zawsze z `_link`/`ensure_link` jak w `_fetch_sheet_plain`):

| Lokalna | `signal` | `None` (domyslny) | `"upgrade"` | `"force"` |
|---|---|---|---|---|
| brak | dowolny | pobiera | pobiera | pobiera |
| jest | `none`, `index`, `metadata` bez `probe` | `local` | `local`, `unverified="none"` dla `none` | pobiera |
| jest | `http`, sygnal rowny | `local` | `local` | pobiera |
| jest | `http`, sygnal rozny | `local`, `newer=<etag/last_modified>` | pobiera | pobiera |
| jest | `http`, nieporownywalny | `local`, `unverified="none"` | `local`, `unverified="none"` | pobiera |
| jest | `http`, `probe` = `DownloadError` | `local`, `unverified="check_failed: ..."` | `DownloadError` | pobiera |

`update="check"` = `ValidationError` (jak `_validate_update` w `manager.py:359`); sprawdzenie robi `inspect_version` (statusy `current`/`newer`/`missing`/`unverifiable`/`check_failed`).

- [ ] **Step 1: Testy `versions.py`** — `test_commit_same_content_new_etag_is_relabeled` (etykieta `downloaded`, inny `ETag` -> nowy katalog z dzisiejsza etykieta, hardlink, `os.path.samefile`), `test_commit_same_content_same_etag_is_unchanged`, `test_commit_same_content_without_signal_is_unchanged` (istniejace zachowanie), `test_commit_same_day_relabel_collision_is_unchanged`, `test_same_http_signal_rules` (decyzja 2, `content_length` ignorowane).
- [ ] **Step 2: Testy `fetch.py`** — `test_fetch_version_matrix` (parametryzowany: kazda komorka tabeli wyzej osobnym przypadkiem; `fetch` i `probe` atrapy liczace wywolania), `test_fetch_version_never_reads_twice` (D20: `read_content` raz), `test_fetch_version_failure_leaves_no_version_and_no_staging`, `test_fetch_version_writes_extra_http`, `test_inspect_version_statuses` (5 statusow), `test_inspect_version_never_calls_fetch`.
- [ ] **Step 3: Testy storage** — `test_raw_versions_root_follows_hierarchy_and_system`, `test_bbox_slot_paths` (`<segment>/bbox/<wsp>.tif`, `<segment>/versions/bbox/`).
- [ ] **Step 4: Implementacja**; `_fetch_sheet_plain` przepisany na `fetch_version(signal="none")` — zachowanie bez zmian (istniejace testy toru bez kampanii przechodza bez modyfikacji asercji) i brama.
- [ ] **Step 5: Commit** — `feat(versions): polityka plikow bez kampanii (fetch_version) i D23 dla sygnalu http`

---

### Task 5: Plan aktualizacji dla wszystkich torow — `plan.py`

**Files:**
- Create: `kartograf/download/plan.py`
- Modify: `kartograf/download/updates.py` (typy 29-122 przeniesione; `_items` 151-213, `upgrade` 236-295 na `unit`/`track`), `kartograf/__init__.py`, `kartograf/cli/download_cmd.py` (`_plan_line` 1438, `_run_plan_modes` 1451: `item.unit`)
- Test: `tests/test_updates.py`, `tests/test_plan.py` (NOWY)

**Interfaces:**
```python
PLAN_SCHEMA = "kartograf-plan/1"
Track = Literal["pl_sheet", "laz_tile", "cz_sheet", "pl_cutout", "cz_cutout"]

@dataclass(frozen=True)
class PlanItem:
    track: Track
    segment: str
    hierarchy: str
    name: str
    unit: str            # sheet code, LAZ tile sheet, CZ sheet, bbox coords
    local_label: str | None
    local_sha256: str | None
    available_label: str | None
    available_signal: dict | None
    status: ItemStatus
    error: str | None = None

class UpdatePlan:  # fields as today
    def merge(self, other: "UpdatePlan") -> "UpdatePlan"  # different store = ValidationError
    def items_for(self, track: Track) -> tuple[PlanItem, ...]

def require_store(plan: UpdatePlan, store: str) -> None  # schema + store check (from upgrade)
def store_id(output_dir: str | Path) -> str               # str(Path(output_dir).resolve())
def select_planned(plan: UpdatePlan, fresh: list[PlanItem], track: Track
                   ) -> tuple[list[PlanItem], list[PlanItem]]
    # (todo, stale): planned newer/missing items of `track` whose fresh item has the same
    # (segment, hierarchy, name, available_label, available_signal) and is still newer/missing;
    # a planned item without such a fresh item = stale; fresh items absent from the plan are skipped
```

- [ ] **Step 1: Testy** — `test_plan_round_trip_all_tracks`, `test_plan_unknown_track_is_validation_error`, `test_merge_rejects_other_store`, `test_select_planned_stale_and_removed` (zmieniony sygnal = `stale`; pozycja usunieta z planu nie jest w `todo`; pozycja juz `current` w swiezym sprawdzeniu — ani `todo`, ani `stale`), istniejace testy `test_updates.py` przepisane na `unit`/`track="pl_sheet"`.
- [ ] **Step 2: Implementacja** (`updates.py` uzywa `require_store`, `store_id`, `select_planned`-owej reguly dla `pl_sheet` bez zmiany zachowania) i brama.
- [ ] **Step 3: Commit** — `refactor(updates)!: plan aktualizacji z torem pozycji (plan.py, unit zamiast sheet)`

---

### Task 6: LAZ na wersjach (D26, D24)

**Files:**
- Modify: `kartograf/download/laz.py` (`LazDownloadResult` 61-82, `write_laz_sidecar` 85-150, `run_laz_download` 152-246, `download_laz_area` 249-349)
- Test: `tests/test_laz_download.py`, `tests/test_laz_campaigns.py` (asercje `downloaded`/`skipped` -> `files[*].status`)

**Interfaces:**
```python
@dataclass(frozen=True)
class LazDownloadResult:
    tiles: tuple[LazTile, ...]
    files: tuple[VersionedFile, ...] = ()     # replaces downloaded/skipped
    failed: tuple[LazTileFailure, ...] = ()
    superseded: tuple[SupersededLazTile, ...] = ()
    stale: tuple[PlanItem, ...] = ()

def laz_version_ref(tile: LazTile) -> VersionRef        # decision 5
def laz_slot(storage: FileStorage, tile: LazTile) -> FileSlot
def run_laz_download(selection, *, provider, bbox, output_dir, year=None, min_density=None,
                     all_campaigns=False, min_year=None, max_year=None, max_workers=1,
                     update: UpdateMode | None = None, plan: UpdatePlan | None = None,
                     on_progress=None, parent_request=None) -> LazDownloadResult
def check_laz_updates(selection, *, provider, output_dir) -> UpdatePlan  # track "laz_tile"
def download_laz_area(bbox, *, ..., update: UpdateMode | None = None, ...)  # force= removed
```

Sygnal pozycji: `available_signal = {"url": tile.url, "year": tile.year, "date": tile.date}`; `fetch_version(signal="index")` bez `probe` (decyzja 5). `upgrade` z planem: tylko kafle z `select_planned(plan, check_laz_updates(...).items, "laz_tile")[0]`; reszta selekcji pominieta, `stale` w wyniku.

- [ ] **Step 1: Testy** — `test_laz_tile_lands_as_version_with_link` (`laz/pl_<sys>_<vcrs>/versions/<hier>/<label>_<sha8>/<plik>.laz`, sciezka standardowa = hardlink, sidecar wersji z `extra.version`, `sha256`), `test_laz_default_keeps_local_tile_and_fetches_new_flight` (D26), `test_laz_force_same_content_is_unchanged`, `test_laz_force_new_content_is_new_version`, `test_check_laz_never_downloads` (statusy `current`/`missing`), `test_laz_upgrade_plan_stale_tile` (kafel z planu zniknal z selekcji -> `stale`, brak pobrania), `test_laz_upgrade_plan_skips_removed_items`, `test_laz_legacy_plain_file_replaced_by_link` (D24: stary zwykly plik z sidecarem 0.7.x bez `extra.link` -> hardlink do nowej wersji), `test_laz_parallel_workers_one_version_per_tile`.
- [ ] **Step 2: Implementacja** (sidecar wersji przez `write_laz_sidecar(..., digest=, version=)` -> `emit_sidecar(exclusive=True)` jak w planie 1/3) i brama.
- [ ] **Step 3: Commit** — `feat(laz)!: kafle LAZ w magazynie wersji (D26, update=, plan aktualizacji)`

---

### Task 7: Arkusze CZ w bibliotece i na wersjach (sygnal `http` dla SM5)

**Files:**
- Create: `kartograf/download/cz_sheets.py`, `tests/test_cz_sheets.py`
- Modify: `kartograf/providers/cuzk/client.py` (`fetch_file` 108-131: `on_response`), `kartograf/providers/cuzk/dmr.py` (`download` 218-260, `_download_sm5` 375-408: `on_response`; nowe `sm5_signal`), `kartograf/cli/download_cmd.py` (`_cz_download_sheet` 2394-2458 usuniety — CLI wola `run_cz_sheet` w Task 11)
- Test: `tests/test_cuzk_dmr.py`, `tests/test_cuzk_client.py`

**Interfaces:**
```python
# dmr.py
def download(self, sheet, output_path, timeout=..., *, on_download=None,
             on_response: Callable[[requests.Response], None] | None = None) -> Path
    # on_response only for SM5 (openzu ZIP); TM33 (exportImage) never calls it
def sm5_signal(self, sheet: str, timeout: int = ...) -> dict   # head_signal of the openzu URL

# cz_sheets.py
@dataclass(frozen=True)
class CzSheetResult:
    file: VersionedFile
    all_nodata: bool
    stale: tuple[PlanItem, ...] = ()

def run_cz_sheet(provider, sheet: str, *, output_dir, update: UpdateMode | None = None,
                 plan: UpdatePlan | None = None, on_download=None) -> CzSheetResult
def check_cz_sheet(provider, sheet: str, *, output_dir) -> UpdatePlan   # track "cz_sheet"
```

Przeniesione bez zmiany tresci sidecara: nodata z naglowka, `capability` (`sheet_files` SM5 / `bbox_raster` TM33), `horizontal_crs` (5514 / 3045), `extra.mapname`, `extra.cz_share` (best-effort jak dzis), `Warning` all-nodata jako log + `all_nodata` w wyniku. Sygnal: SM5 `http` (`probe = provider.sm5_signal`), TM33 `none`.

- [ ] **Step 1: Testy** — `test_sm5_version_with_extra_http` (naglowki z nagranej odpowiedzi Task 1), `test_sm5_default_same_etag_is_local_one_head`, `test_sm5_default_new_etag_is_local_with_newer`, `test_sm5_upgrade_new_etag_downloads`, `test_sm5_upgrade_head_failure_is_error`, `test_sm5_default_head_failure_is_local_unverified`, `test_tm33_default_is_local_without_network`, `test_tm33_upgrade_is_local_unverified_none`, `test_check_cz_sheet_never_downloads` (SM5: `current`/`newer`/`check_failed`; TM33: `unverifiable`/`missing`), `test_cz_sm5_upgrade_plan_etag_changed_is_stale`, `test_cz_sheet_legacy_plain_file_replaced_by_link` (D24), `test_cz_sheet_sidecar_fields_unchanged` (`mapname`, `cz_share`, `capability`, `horizontal_crs` jak przed przeniesieniem).
- [ ] **Step 2: Implementacja** i brama (testy CLI CZ przechodza po Task 11).
- [ ] **Step 3: Commit** — `feat(cz)!: arkusze CZ w bibliotece i w magazynie wersji (sygnal http SM5)`

---

### Task 8: Wycinek CZ na wersjach

**Files:**
- Modify: `kartograf/download/cz_cutout.py` (`CzCutoutResult` 23-30, `run_cz_cutout` 97-167, `download_cz_cutout` 170-212)
- Test: `tests/test_cz_cutout.py`

**Interfaces:**
```python
@dataclass(frozen=True)
class CzCutoutResult:
    file: VersionedFile
    all_nodata: bool = False
    stale: tuple[PlanItem, ...] = ()

def run_cz_cutout(provider, bbox, *, output_dir, image_crs, update: UpdateMode | None = None,
                  plan: UpdatePlan | None = None, parent_request=None, on_download=None) -> CzCutoutResult
def check_cz_cutout(provider, bbox, *, output_dir, image_crs) -> UpdatePlan   # track "cz_cutout"
def download_cz_cutout(bbox, *, output_dir, target_crs, vertical_crs, resolution,
                       update: UpdateMode | None = None, cache=None, parent_request=None) -> CzCutoutResult
```

Slot: `bbox_slot(output_dir, descriptor.resolve_subdir(...), bbox_po_normalizacji, ".tif")`; sygnal `none`; pobranie `provider.download_bbox(bbox, staged, on_download=)` do `.incoming/`; `all_nodata` lokalnej wersji z `extra.all_nodata` sidecara wersji (decyzja 6).

- [ ] **Step 1: Testy** — `test_cz_cutout_version_and_link`, `test_cz_cutout_default_local_without_network`, `test_cz_cutout_force_same_content_unchanged`, `test_cz_cutout_local_all_nodata_from_sidecar`, `test_check_cz_cutout_never_downloads`, `test_cz_cutout_failure_leaves_no_version_and_no_empty_tree`, `test_cz_cutout_legacy_plain_file_replaced_by_link` (D24); istniejace testy `force`/`skipped` przepisane.
- [ ] **Step 2: Implementacja** i brama.
- [ ] **Step 3: Commit** — `feat(cz)!: wycinek CZ w magazynie wersji (update= zamiast force=)`

---

### Task 9: Wycinek PL z WCS na wersjach (D15)

**Files:**
- Modify: `kartograf/download/cutout.py` (`PlCutoutResult` 104-116, `dated_cutout_path` 250-253 usuniety, `_check_wcs_disk_space` 267-280, `run_pl_wcs_cutout` 344-446, `download_pl_cutout` 449-498; docstringi ADR-035 "every call downloads" i "dated")
- Test: `tests/test_pl_cutout.py`, `tests/test_wcs_cutout.py`

**Interfaces:**
```python
@dataclass(frozen=True)
class PlCutoutResult:
    file: VersionedFile
    all_nodata: bool = False
    masked_pixels: int = 0
    zero_pixels: int = 0
    stale: tuple[PlanItem, ...] = ()

def run_pl_wcs_cutout(cutout, *, provider=None, update: UpdateMode | None = None,
                      plan: UpdatePlan | None = None, parent_request=None,
                      now: datetime | None = None) -> PlCutoutResult   # `today` -> label time
def check_pl_cutout(cutout) -> UpdatePlan                               # track "pl_cutout"
def download_pl_cutout(bbox, target_crs, *, output_dir, vertical_crs, product,
                       update: UpdateMode | None = None, parent_request=None) -> PlCutoutResult
```

Sekwencja przy pobraniu (bez zmian merytorycznych ADR-035): kontrola miejsca (tylko gdy pobiera) -> maska PRG -> WCS do pliku roboczego w `.incoming/<host>_<pid>_<token>/` -> maska -> `os.replace`/`warp_to_grid` do `staged` w tym samym katalogu roboczym -> `fetch_version` (sha256, wersja, sidecar wersji z `extra.source`, `extra.mask`, `extra.zero_pixels`, `extra.all_nodata`) -> dowiazanie `bbox/<wsp>.tif`. Lokalna wersja: pola wyniku z sidecara wersji, bez PRG i WCS.

- [ ] **Step 1: Testy** — `test_pl_cutout_undated_link_and_version` (`bbox/<wsp>.tif` bez daty, wersja `versions/bbox/<RRRR-MM-DD>_<sha8>/<wsp>.tif`), `test_pl_cutout_default_local_without_prg_or_wcs` (sesje-atrapy: zero zapytan), `test_pl_cutout_force_same_content_unchanged`, `test_pl_cutout_force_new_content_new_version_link_moves`, `test_pl_cutout_local_result_fields_from_sidecar`, `test_check_pl_cutout_never_downloads` (`unverifiable`/`missing`), `test_pl_cutout_failure_keeps_previous_version_and_link`, `test_pl_cutout_dated_files_ignored` (stary `<wsp>_<RRRRMMDD>.tif` nie jest wersja ani dowiazaniem, D10), `test_disk_space_checked_only_when_fetching`; testy `dated_cutout_path` usuniete.
- [ ] **Step 2: Implementacja** i brama.
- [ ] **Step 3: Commit** — `feat(cutout)!: wycinek PL z WCS w magazynie wersji (bbox/ bez daty, D15)`

---

### Task 10: Usuniecie `DownloadManager.download_bbox` (D27)

**Files:**
- Modify: `kartograf/download/manager.py` (1817-1879; przyklad w docstringu klasy ok. 455-470)
- Test: `tests/test_download_manager.py` (testy 680-720 usuniete)
- Docs w Task 12: `docs/USAGE.md` 371-376 i 826-832, `docs/ARCHITECTURE.md` 964-1001, ADR-004 (errata)

- [ ] **Step 1:** Usun metode i jej testy; wyszukanie `download_bbox` w `kartograf/` i `tests/` zostawia tylko providery (`BaseProvider.download_bbox` `kartograf/providers/base.py:128`, `GugikProvider` `providers/pl/gugik.py:415` — dziedziczy `GugikNmptProvider`, `GugikOrtoProvider` `providers/pl/gugik_orto.py:234`, `CuzkDmrProvider` `providers/cuzk/dmr.py:262`) i ich testy.
- [ ] **Step 2:** Brama.
- [ ] **Step 3: Commit** — `refactor(manager)!: usuniete DownloadManager.download_bbox (D27)`

---

### Task 11: CLI `kartograf download` — tryby dla wszystkich torow

**Files:**
- Modify: `kartograf/cli/download_cmd.py` (usun `_reject_update_modes` 1391-1399 i wywolania 1178-1185, 1211-1212; `_run_plan_modes` 1451-1497 uogolnione na tory; `_download_pl_cutout` 1999-2104; `_cmd_download_laz` 2251-2371; `_run_cz` 647, `_cz_download_bbox` 2475-2531, `_cmd_download_cz` 2534-2632; usun `_cz_download_sheet` 2394-2458 i `_print_legacy_krovak_info` 1978-1997), `kartograf/cli/_parser.py` (help `--check-updates`/`--upgrade`/`--force`/`--plan` 265-295: bez "Tylko PL")
- Test: `tests/test_cli.py` (`TestCmdDownloadLaz`, `TestCzDownloadingAfterValidation`, `TestCmdDownloadCz`, klasy `--target-crs`), `tests/test_cli_update_modes.py`

**Zachowanie:**
- Mapowanie trybow jak `_update_mode` (1402-1407) dla kazdego toru.
- `--check-updates`: kazdy tor buduje plan (`check_laz_updates`, `check_cz_sheet`, `check_cz_cutout`, `check_pl_cutout`, `check_updates`); `--country auto` z PL+CZ — `UpdatePlan.merge`; linie `_plan_line` (`item.unit`), `--plan PLIK` zapisuje polaczony plan; kod 1 przy `check_failed` (jak dzis).
- `--upgrade --plan PLIK`: plan wczytany raz, `require_store`; kazdy tor dostaje `plan=`; pozycje `stale` drukowane jak dzis dla PL; kod czesciowego sukcesu (ARCHITECTURE 4.2).
- Linie statusu: `_status_lines(unit, ((file.version_path.parent.name, file.status),), file.newer)` dla torow jednoplikowych; LAZ — linia na kafel; `local` + `unverified == "none"` -> dopisek `(bez sprawdzania; --check-updates)` w trybie domyslnym i `Info: ... niesprawdzona — zrodlo bez taniego sygnalu; pobierz ponownie: --force` przy `--upgrade`; `unverified` `check_failed` -> `Warning:` (stderr, takze z `-q`).
- Podsumowanie `_print_version_summary` z licznikami takze dla LAZ (wiele plikow); tory jednoplikowe — bez podsumowania (jedna linia statusu).

- [ ] **Step 1: Testy** — `test_update_flags_accepted_for_every_download_track` (LAZ, CZ `--sheet`, CZ bbox, `--target-crs`, `--country auto`: brak `Error:` odrzucenia), `test_check_updates_auto_writes_merged_plan` (pozycje `pl_sheet` i `cz_cutout` w jednym pliku), `test_upgrade_plan_executes_only_planned_tracks`, `test_status_line_local_none_hint`, `test_upgrade_none_signal_info_force`, `test_sm5_check_failed_warning_exit_code`, `test_laz_summary_counters`, `test_cz_sheet_cli_uses_library` (`run_cz_sheet` wolany z `update`), istniejace testy `Skipped ...`/`force` przepisane na linie statusu.
- [ ] **Step 2: Implementacja** i brama.
- [ ] **Step 3: Smoke offline** — `--help` (nowe teksty), `Error:` dla `--plan` bez trybu, kody wyjscia z atrapami providerow (test CLI wyzej), bez sieci.
- [ ] **Step 4: Commit** — `feat(cli)!: --check-updates, --upgrade i plan dla LAZ, CZ i wycinkow`

---

### Task 12: Dokumentacja

**Files:**
- Modify: `docs/DECISIONS.md` (CRLF), `docs/CHANGELOG.md`, `docs/ARCHITECTURE.md` (3.2, 3.3, 4.3-4.7, 964-1001), `docs/USAGE.md` (371-376, 826-832, wycinki, LAZ, CZ, tryby), `docs/SCOPE.md` (2.11, 2.12, 3.3 status podprojektu 1)

- [ ] **Step 1: DECISIONS** — ADR-036: decyzje D26-D28 (wyjatek LAZ od D5, usuniecie `download_bbox`, brak `Content-Length`), sygnaly per kanal (tabela z Task 1), ADR-035 W-U3/W-U8 zrealizowane (oznaczenie "realizacja w planie 2/3" zamienione na stan); errata ADR-004 (`download_bbox` menedzera usuniete, provider zostaje); indeks. Sprawdz CRLF: `.venv/bin/python -c "b=open('docs/DECISIONS.md','rb').read().split(b'\n'); print([i for i,l in enumerate(b[:-1],1) if not l.endswith(b'\r')][:5])"` -> `[]`.
- [ ] **Step 2: CHANGELOG `[0.8.0]` BREAKING** (styl wpisow istniejacych, kazdy z "Co zrobic"): LAZ/CZ/wycinki w `versions/` (D24: stare pliki nadpisywane dowiazaniem), wycinek PL bez daty w nazwie i bez pobierania przy kazdym uruchomieniu (D15), `force=` -> `update=` w `download_laz_area`/`run_laz_download`/`run_cz_cutout`/`download_cz_cutout`, `update=` w `download_pl_cutout`/`run_pl_wcs_cutout` (`today` -> `now`), wyniki z `file: VersionedFile` zamiast `skipped`/`downloaded`/`path`, `PlanItem.sheet` -> `unit` + `track`, usuniete `DownloadManager.download_bbox` (D27), LAZ: nowszy nalot pobiera sie domyslnie (D26); Dodane: `--check-updates`/`--upgrade`/`--plan` dla LAZ, CZ i wycinkow, `extra.http` w sidecarach SM5.
- [ ] **Step 3: ARCHITECTURE/USAGE/SCOPE** — uklad `versions/` dla LAZ, CZ i `bbox/`, sygnaly per kanal, tryby per tor, wynik powtarzalnosci bajtowej z Task 1 (spec 4.6), przyklady biblioteki bez `download_bbox` menedzera (NMT/NMPT -> `download_pl_cutout`; orto/surowy WCS -> `provider.download_bbox(bbox, path)` poza magazynem).
- [ ] **Step 4: Commit** — `docs: magazyn wersjonowany dla LAZ, CZ i wycinkow (ADR-036, CHANGELOG)`
- [ ] **Step 5: PROGRESS** — na `develop` (galaz nie zmienia `docs/PROGRESS.md`): sesja, stan planu 2/3, nastepny krok (plan 3/3).

---

### Task 13: Weryfikacja na zywo

**Files:** brak zmian w repo (chyba ze test wykaze blad — wtedy osobny commit z testem odtwarzajacym).

Katalog danych od uzytkownika, swiezy `--output`, cache CLI w cwd (korzen repo).

- [ ] **Step 1: LAZ** — maly bbox z dwoma nalotami (np. z fixtur `w2`): pobranie -> rerun (`lokalna wersja`, zero pobran kafli) -> `--check-updates --plan` (`aktualne`) -> `--force` (`bez zmian` przy powtarzalnych bajtach) -> `--year` starszy nalot (nowe pliki, stare zostaja) ; listing `versions/`, `nlink` = 2.
- [ ] **Step 2: CZ SM5** (`--resolution 5m --sheet CTES96`): pobranie (`extra.http` w sidecarze wersji) -> rerun (jedno `HEAD`, `lokalna wersja`) -> `--check-updates` (`aktualne`) -> `--upgrade` (lokalna) -> `--force`.
- [ ] **Step 3: CZ TM33 i wycinek CZ** — pobranie -> rerun bez sieci (lokalna, dopisek `--check-updates`) -> `--upgrade` (`Info:` o `--force`) -> `--force` (status wg powtarzalnosci z Task 1).
- [ ] **Step 4: Wycinek PL** (`--bbox ... --country pl --target-crs EPSG:2180` i `EPSG:3045`): `bbox/<wsp>.tif` bez daty, rerun bez zapytan PRG/WCS, `--force`.
- [ ] **Step 5: `--country auto`** na pograniczu PL/CZ: `--check-updates --plan` (plan z pozycjami `pl_sheet` i `cz_cutout`) -> `--upgrade --plan`.
- [ ] **Step 6: D24** — katalog z danymi 0.7.x (LAZ, CZ): pierwsze pobranie 0.8.0 zastepuje stary plik dowiazaniem.
- [ ] **Step 7:** Przekaz uzytkownikowi komendy, kody wyjscia, listingi `versions/`, liczby hardlinkow. Kazda niezgodnosc: test odtwarzajacy w `tests/` (failing), poprawka, osobny commit.
