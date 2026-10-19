# fix-store-project - wycinek E (`project`, odczyt magazynu, `cache`, tryby aktualizacji)

Worktree `<worktree>`, galaz `fix/e2e-store-project` (z `develop @ bef87501`).
Brama `scripts/gate.sh` ZIELONA: ruff check, ruff format --check, mypy, pytest offline - **7184 passed, 18 deselected** (`GATE OK`, 176 s).
Pierwszy przebieg bramy mial 1 porazke (`tests/test_cli_errors.py::test_oserror_is_io_error_in_json_mode` uzywal `--plan KATALOG` jako sposobu na `OSError`, czyli dokladnie bledu P3-8) - test przestawiony na wymuszony `IsADirectoryError` przy zapisie (commit `e1e88928`), drugi przebieg zielony.

## Commity (bez Co-Authored-By)

| Commit | Zakres |
|---|---|
| `60dd6256` | fix(store): jednostka i obrys kafla LAZ z kafla (P2-2) + numer arkusza ZTM |
| `f69f8759` | fix(project): `--force` naprawia uszkodzona wersje (P3-1); BOM i plik w `--project` (P3-15) |
| `047b81aa` | fix(cli): `project add -q` (P3-4), `--plan KATALOG` (P3-8), `--upgrade --plan` bez pozycji (P3-25), hint `project init` (P3-12) |
| `970d6e0b` | fix(cache): komunikaty cache bez dostepu / `cache clear` bez pliku (P3-13, C P3-18) |
| `45e86f3d` | docs: USAGE 4.3/8.1/8.2/8.3/9.1/9.5/2, ARCHITECTURE 3.3.1/3.5/4.7/4.11 |
| `e1e88928` | test(cli): przestawienie testu `io_error` po P3-8 |

## E P2-2 - kafel LAZ: `Sidecar.unit` i `file_footprint` z kafla - NAPRAWIONE

**Przyczyna.** `write_laz_sidecar` zapisuje w `request` OBSZAR zadania (`bbox` = okno EPSG:2180 + `bbox_crs`; takze 0.7.x i 0.8.0-dev), a kafel jest jedna z jego czesci (`extra.tile_sheet`). `store.py::_unit` bral wiec `<coords>` obszaru, a `store_geometry.py::file_footprint` zwracal `request.bbox` jako obrys kazdego kafla; galaz `header` (LAS/LAZ) byla dla kafli Kartografa martwa. Godlo kafla LAZ jest nieprzezroczyste (`SheetParser` go nie parsuje: ADR-021), wiec obrysu z kodu nie da sie policzyc.

**Zmiana (tylko czytnik, format sidecara BEZ zmian; czyta tez 0.7.x, 0.8.0-dev i klucz `godlo_kafla` sprzed ADR-031):**
- `store.py::_unit` (+ `_typed`): po `request.teryt|ku|sheet|tile` i `extra.source.sheet`, a PRZED bboxem, jednostka = `extra.tile_sheet`;
- `store_geometry.py::file_footprint` + `_is_tile`: dla kafla (`extra.tile_sheet`) pomija `request.bbox`; kolejnosc dalej jak wczesniej (godlo -> naglowek LAS -> jednostka). Bez czytelnego naglowka brak obrysu (`None`), nigdy obszar zadania;
- `store.py::_unit_slot` (znalezisko audytu, patrz nizej): w segmencie samych arkuszy/kafli (`kinds <= {"sheet","tile"}`, np. ZTM) sam numer (`0510`) to arkusz, nie TERYT.

**Decyzja o zapisie (do wiadomosci koordynatora).** Rozwazylem zapis `request` kafla jak dla arkuszy NMT/CZ LAZ (`request = {sheet|tile}`, obszar w `extra.parent_request`). NIE zrobilem tego: (1) `request.bbox` jest jedynym sladem obszaru przy wywolaniu bibliotecznym bez `parent_request` i w trybie `--sheet` (tam brak `parent_request`; przestawienie wymagaloby jeszcze `parent_request` dla trybu arkusza); (2) czytnik i tak musi obslugiwac stary ksztalt (0.7.x/0.8.0-dev zostaja w magazynach na zawsze, wersje sa niezmienne - ADR-036), wiec zmiana zapisu dawalaby dwa ksztalty bez zysku; (3) zmiana kontraktu sidecara tuz przed tagiem. Alternatywa (rekomendacja na 0.9: `request.tile` + `parent_request` zawsze dla LAZ, czytnik bez zmian) opisana tu, nie wdrozona. CZ LAZ (`cz_laz.py`) sprawdzony: `request={"sheet": ...}` + `parent_request`, bez bledu.

**Audyt innych jednostek na obszar.** Skrypt po 67 magazynach z drzewa E2E (sekcje A-F, ~1,6 tys. wpisow z sidecarem): dla kazdego wpisu `iter_store(units=[sidecar.unit])` musi odnalezc wpis. PRZED: bledy tylko LAZ PL (`laz/pl_1992_evrf2007`, `laz/pl_1992_kron86`) i ZTM `maps/cz_ztm_100000_sjtsk_pdf` (arkusz `0510` - cztery cyfry wygladaja jak TERYT). PO: zero bledow. Kolekcje (kafle mesh `request.tile`), wycinki, CZ i reszta - bez bledow.

**Testy regresyjne (padaja na starym kodzie, przechodza po):** `tests/test_laz_download.py::TestTilesInTheStoreApi` (kafle zapisane PRAWDZIWYM `_run_laz_download`, odczyt `iter_store`/`file_footprint`, PL-1992 i PL-2000, naglowek LAS = obrys, unit = godlo, petla `units`), `tests/test_store_geometry.py::test_laz_tile_*` (naglowek zamiast obszaru, klucz `godlo_kafla`, brak naglowka = brak obrysu), `tests/test_store_api.py::test_unit_of_a_laz_tile_*` i `::test_unit_of_a_ztm_sheet_*`.

**Na zywo (kafel 83134_1728146_M-34-64-D-d-1-4-4-1.laz, 59 MB, GUGiK):**
- PRZED (magazyn E2E E, kod `bef87501`): `unit = 566000_243000_566100_243100`; `iter_store(units=[unit]) -> []`; `file_footprint`: source `request`, 100,0 x 100,0 m.
- PO, ten sam magazyn: `unit = M-34-64-D-d-1-4-4-1`; `iter_store(units=[unit]) -> ['link','version']`; source `header`, EPSG:2180 (565977.27, 242585.65, 566542.61, 243171.5) = 565,3 x 585,9 m (= naglowek LAS z raportu E2E).
- PO, swiezo pobrany kod PO zmianach (`elevation download --product laz --bbox 566000,243000,566100,243100 ... -o <katalog-danych>/laz-store`, rc 0): identyczny wynik jak wyzej. Skrypty i logi: `~/scratch/fix-store-project/` (`laz_before.txt`, `live_out.txt`, `audit_before.txt`, `audit_after.txt`).

**Docs:** ARCHITECTURE 3.3.1 (akapit `units`/`Sidecar.unit` i `file_footprint`), 4.7 (`request.bbox` LAZ = obszar), USAGE 2 (akapit `file_footprint`), docstringi `Sidecar`, `file_footprint`, `write_laz_sidecar`.

## E P3-1 - `project download --force` nie naprawial uszkodzonej wersji - NAPRAWIONE (prawdziwa naprawa)

**Przyczyna.** `commit_version` uznaje wersje o tym samym `sha256` ZE SIDECARA za ta sama tresc (`unchanged`) i wyrzuca pobrane, poprawne bajty; uszkodzony plik (ta sama SHA w sidecarze, inne bajty) zostaje. Komunikat `verify` dla SHA nie mial sciezki naprawy z komunikatu o rozmiarze.

**Zmiana (`project/operations.py`):** `download_project(update="force")` przed pobraniem odklada wersje, ktore `verify` nazywa uszkodzonymi (rozmiar, SHA-256, sidecar) - `_set_aside_corrupt`/`_set_aside`: dane + sidecar przenoszone do ukrytego katalogu `.<etykieta>_<sha8>.corrupt-<czas>` obok wersji (nic nie jest usuwane; skan i `list_versions` pomijaja ukryte katalogi; odmowa dla wersji poza magazynem - dowiazanie symboliczne; wycofanie przy bledzie przeniesienia). Po pobraniu te same bajty wracaja pod przypieta wersje (`_repin_repaired` -> `_repin_version`), wynik zadania `odtworzono`, manifest bajtowo bez zmian; inna tresc u zrodla przepina zadanie jak kazde `--force`. Jeden opis naprawy w `status` i `verify` (`_repair_advice`: kopia magazynu albo `project download --force NAZWA`). Standardowa sciezka (hardlink tego samego inode) jest dowiazywana od nowa przez istniejace `ensure_link`. Bez sieci: wersja zostaje odlozona (`status`: brak przypietego pliku), zwykle `project download NAZWA` odtwarza ja z tych samych bajtow (test).

**Testy (padaja na starym kodzie):** `tests/test_project_download.py`: `test_force_repairs_a_corrupt_pinned_version[flip|truncate]`, `test_force_without_a_source_leaves_the_repair_to_the_next_download`, `test_force_never_moves_a_version_that_lies_outside_the_store`, `test_status_and_verify_offer_the_repair_of_a_corrupt_version[flip|truncate]`, `test_force_leaves_intact_versions_alone`.

**Na zywo (ISRIC, zadanie `soil download` 626000,480000,628000,482000, odwrocony ostatni bit pliku wersji):** PRZED (stary kod): `verify` rc 1 -> `download --force` rc 0 `gleba: bez zmian` -> `verify` nadal rc 1. PO: `verify` rc 1 z `... albo uruchom kartograf project download --project ... --force gleba (odklada uszkodzona wersje i pobiera ja ponownie)`; `download --force` rc 0 `gleba: odtworzono (1 plik)`; `verify` rc 0 `ok`; obok wersji ukryty `.2.0_717f0989.corrupt-20261019T120835`.

**Docs:** USAGE 8.1 (nowy akapit naprawy), 8.2, 4.3, docstring `download_project`.

## Pozostale P3

| Pozycja | Status | Zmiana | Test | Na zywo |
|---|---|---|---|---|
| P3-4 `project add -q` | naprawione (`-q` byl testowanym, ale mylacym zachowaniem - stary test dodawania komend przestawiony bez `-q`) | `cli/project_cmd.py::_reject_run_options`: `quiet` -> `invalid_input`, `option=quiet` | `test_add_rejects_run_options[-q,--quiet]` | PRZED rc 0 (po cichu pominiete); PO rc 2 `Error: -q/--quiet nie jest czescia zadania ...` |
| P3-8 `--check-updates --plan KATALOG` | naprawione | `cli/download_cmd.py::run_with_plan_file`: katalog w miejscu pliku -> `invalid_input` przed siecia | `test_plan_file_that_is_a_directory_is_one_error_line` | PO rc 2 przed siecia |
| P3-12 hint `project init` | naprawione | `NAZWA <grupa> <komenda> ...` | (tekst; brak testu brzmienia) | PO widoczne w wydruku |
| P3-13 / C P3-18 `cache` | naprawione | `cache/metadata.py::is_unwritable_error` (po `sqlite_errorname`: CANTOPEN dla nieistniejacego pliku/katalogu, READONLY, PERM, FULL) -> `cache_disabled` mowi "niedostepny do otwarcia lub zapisu ... sprawdz uprawnienia", bez `cache clear`; istniejacy plik bez prawa odczytu zostaje "nieczytelny" (clear go usuwa); to samo `cache stats` (`cache_info._unusable`); `cache clear` bez pliku: `Cache jest pusty: nie ma pliku cache (...)` (JSON bez zmian: `cleared:true`, `exists:false`) | `tests/test_cache_unusable_messages.py` (3); stary test `test_cache_clear_does_not_create_db` przestawiony na nowy tekst | PRZED `Cache wyczyszczony.`; PO `Cache jest pusty: nie ma pliku cache (...)` |
| P3-15 manifest | naprawione | `project/manifest.py::_load`: `utf-8-sig` (BOM; zapis zawsze bez BOM); `--project` = plik daje `... to plik, a --project wymaga katalogu projektu ..., np. --project <katalog>` zamiast zdublowanej sciezki | `test_bom_of_an_editor_...`, `test_project_given_as_the_manifest_file_...` | - |
| P3-25 `--upgrade --plan` bez pozycji | naprawione (tor arkuszy PL / LAZ / kolekcje; tor `soil`/`landcover` zawsze drukuje linie `lokalna wersja`, wiec nie byl niemy) | `run_with_plan_file` + `_present` (zapamietuje wynik takze w trybie tekstowym) + `_ran_nothing`: `Info: plan X: brak pozycji do wykonania (pozycje sa aktualne albo juz wykonane)` na stderr, nie w `--json`; obejmuje tez plan wykonany po raz drugi | `test_upgrade_plan_that_runs_nothing_says_so` | na zywo tor `soil` nie jest niemy (`lokalna wersja 2.0`) - przypadek PL sheet pokryty testem offline |

## Docs (P3-3/P3-7/P3-14/P3-19)
- USAGE 9.5 (tabela `parse_command`/`run_command`) i ARCHITECTURE 4.11: klucze `CommandCall.run` = `output_dir`, `upgrade`, `force`, `check_updates`, `plan`, `workers`, `quiet`, `json`, `summary` (nie `update`; mapowanie na `update=` robi wywolujacy).
- USAGE 8.2: bez `--year` pierwsze `download` przypina LOKALNY starszy lot (tryb domyslny 4.3), nowszy dopiero `--upgrade`.
- USAGE 9.1: znaczenie `ok` w `kartograf-project-check/1` (`status`/`verify` vs `--check-updates`, projekt bez przypiec ma tam `ok:true`).
- USAGE 8.3: wzgledne `--output`/`--geometry` czytane wzgledem CWD, zapisywane wzgledem projektu (lancuch `../..`), geometria `.gpkg`/`.shp`; dodatkowo (P3-6) `status`/`verify`/`download` nie widza zmiany geometrii.

## Proponowany wpis CHANGELOG (styl [0.8.0], ASCII)

```
- **Odczyt magazynu (kafle LAZ, ZTM):** `Sidecar.unit` kafla LAZ to jego godlo
  (`extra.tile_sheet`, takze w sidecarach 0.7.x i 0.8.0-dev), a nie obszar zadania
  z `request.bbox`; `file_footprint` kafla bierze obrys z naglowka LAS (bez
  czytelnego naglowka: brak obrysu), wiec `iter_store(units=[unit])` odnajduje
  kafel, a kafle jednego zadania nie dziela obrysu. W segmencie samych arkuszy
  (ZTM) sam numer (`0510`) to arkusz, nie TERYT. Format sidecara bez zmian
  (E2E 0.8.0 P2-2).
- **Projekt:** `project download --force` naprawia uszkodzona przypieta wersje
  (inny rozmiar, SHA-256 albo sidecar): odklada ja do ukrytego katalogu
  `.<etykieta>_<sha8>.corrupt-<czas>` i pobiera ponownie; te same bajty wracaja
  pod przypieta wersje (`odtworzono`, manifest bez zmian). `status` i `verify`
  podaja ten sam opis naprawy. Manifest z BOM-em edytora jest czytany;
  `--project` wskazujacy plik daje czytelny blad. `project add ... -q` to blad
  (`-q` nie jest czescia zadania). Podpowiedz po `project init`:
  `NAZWA <grupa> <komenda> ...` (E2E 0.8.0 P3-1, P3-4, P3-12, P3-15).
- **CLI:** `--check-updates --plan KATALOG` jest odrzucane przed siecia
  (`invalid_input`); `--upgrade --plan` bez pozycji do wykonania wypisuje
  `Info:` (E2E 0.8.0 P3-8, P3-25).
- **Cache:** `cache_disabled` i `cache stats` nie nazywaja cache "nieczytelnym",
  gdy nie da sie go otworzyc ani zapisac (katalog tylko do odczytu, pelny dysk,
  katalog w miejscu pliku) - podpowiedz dotyczy uprawnien, nie `cache clear`;
  `cache clear` bez pliku bazy mowi, ze nie ma czego czyscic (E2E 0.8.0 P3-13).
- **Dokumentacja:** klucze `CommandCall.run`, znaczenie `ok` w
  `kartograf-project-check/1`, odczyt wzglednych `--output`/`--geometry`,
  przypiecie lokalnego starszego lotu, naprawa wersji `--force` (E2E 0.8.0
  P3-3, P3-7, P3-14, P3-19).
```

## Erraty ADR (propozycja, nie edytowalem DECISIONS.md)
- ADR-045 errata: `Sidecar.unit` kafla LAZ = `extra.tile_sheet` (nie `<coords>` obszaru); `file_footprint` pomija `request.bbox` dla kafla (obrys z naglowka LAS); `iter_store(units=...)` w segmencie samych arkuszy traktuje sam numer jako arkusz (ZTM `0510`). Zapis `request` kafla LAZ bez zmian (obszar zadania) - rozwazone przestawienie na `request.tile` + `parent_request`, odlozone (zob. wyzej).
- ADR-040 errata: `--force` projektu naprawia wersje uszkodzone wg `verify` (odkladanie do `.<etykieta>_<sha8>.corrupt-<czas>`); bezposrednie komendy danych (`elevation download --force` itd.) nadal NIE nadpisuja i nie naprawiaja (USAGE 4.3) - naprawa na poziomie `commit_version` (status `repaired`) wymagalaby zmiany dokumentow `kartograf-download/1` i bylaby osobna decyzja.

## Uwagi dla koordynatora
- **Konflikty przy scalaniu:** `kartograf/store.py` (moje hunki: docstring `Sidecar`, `_CODE_KINDS`, `_unit`, `_typed`, `_unit_slot`; FixLinks: koniec pliku `link_target`) i ARCHITECTURE 3.3.1 / USAGE 4, 7 (FixLinks) - rozlaczne akapity, ale ten sam plik.
- **Incydent `git stash`:** `git stash` jest WSPOLDZIELONY miedzy worktree; moj `stash pop` i `stash pop` FixLinks zamienily nasze zmiany (store.py/store_geometry.py <-> links.py). FixLinks przywrocil oba drzewa; zweryfikowalem, ze `git diff` w moim worktree to dokladnie moje zmiany (links.py czysty). Porownanie ze starym kodem robilem potem na kopii `git archive HEAD` poza repo.
- Dane na udziale: `<katalog-danych>/fix-store-project/` (projekty testowe `projekt-OLD|NEW`, magazyny `magazyn-OLD|NEW`, `laz-store` 59 MB), razem < 100 MB; nic z tego nie trafilo do repo.
- Nie zrobione / poza zakresem: P3-2/P3-5/P3-6 (kod)/P3-9..P3-11/P3-16..P3-24 (poza moim wycinkiem), P2-1 (FixLinks). Poza P3-6 (jedno zdanie w USAGE 8.3) nie ruszalem ich.
