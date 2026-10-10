# Drugie dowiazanie do najnowszego pelnego lotu (`full_sheet/`, `--full-sheet`) — Implementation Plan

**Status:** WYKONANY 2026-10-10 (Task 1-6; odstepstwa od planu:
`docs/PROGRESS.md`, sesja "Drugie dowiazanie do pelnego lotu —
implementacja"); checkboxy ponizej nieodhaczane.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wdrozyc w 0.7.2 spec
`docs/superpowers/specs/2026-10-10-full-sheet-link-design.md` (decyzje
F-U1..F-U5): drugie dowiazanie `<segment>/full_sheet/<hierarchia>/<godlo>.<ext>`
do najnowszego lokalnego lotu z `full_sheet is True`, flaga CLI
`--full-sheet` / `DownloadManager(full_sheet=True)` dociagajaca najnowszy
pelny lot, gdy najnowszy nie jest pelny, wspolny `Warning:` z E13,
`Info:` jak U15 dla dowiazania pelnego spoza przedzialu, straze CLI
(LAZ, `--target-crs`, CZ).

**Architecture:** Jedna warstwa = jedno zadanie = jeden commit na galezi
`feat/full-sheet-link`. Mechanika dowiazania BEZ nowej logiki:
`ensure_standard_link` jest juz ogolne wzgledem sciezki `link` (cel
z sidecara `link`, nigdy wstecz, hardlink -> kopia) — zmienia tylko
nazwe na `ensure_link` i jest wolane drugi raz w `_fetch_campaigns` dla
sciezki `full_sheet/`. Dociaganie (Task 3) to jedno dodatkowe wywolanie
`resolve_campaigns(campaigns="all", ...)` w managerze, bez nowego API
providera. CLI (Task 4) czyta fakty z `DownloadResult`, nie liczy
niczego sam.

**Tech Stack:** Python 3.12, `pytest` (offline; `conftest` blokuje
gniazda), `rasterio` (tylko istniejacy pomiar), bez nowych zaleznosci.

**Spec:** `docs/superpowers/specs/2026-10-10-full-sheet-link-design.md`
(zaakceptowany 2026-10-10). Pomiar flagi na granicach:
`docs/research/2026-10-10-full-sheet-link/granica-pelne-pokrycie.md`.

## Global Constraints

- Python wylacznie z `.venv`: `.venv/bin/python -m pytest ...`,
  `.venv/bin/python -m ruff ...`, `.venv/bin/python -m mypy ...`, CLI
  `.venv/bin/kartograf`.
- Brama przed KAZDYM commitem: `.venv/bin/python -m pytest tests/ -m "not live" -q`
  zielone, `.venv/bin/python -m ruff check .` i
  `.venv/bin/python -m ruff format --check .` czyste,
  `.venv/bin/python -m mypy kartograf/ tests/` bez bledow.
- Commit WYLACZNIE przez straznik wzorcow:
  `F="$HOME/.config/kartograf/forbidden-patterns.txt"; test -r "$F" && ! git diff --cached -U0 | grep '^+' | grep -qiEf "$F" && git commit ...`.
  Brak pliku wzorcow = zatrzymaj sie i zapytaj. Tresci wzorcow nie
  wpisuj do repo ani nie wypisuj.
- Commity: Conventional Commits z opisem po polsku, autor
  `Daldek <git@debever.pl>`, BEZ stopki `Co-Authored-By`. Docstringi
  i komentarze po angielsku; dokumentacja po polsku bez diakrytykow
  (poza `USAGE.md`, ktory ma diakrytyki); komunikaty CLI po polsku bez
  diakrytykow.
- `docs/DECISIONS.md` ma konce linii CRLF — zachowaj je (sprawdz
  `git diff --stat`: kilka-kilkadziesiat linii, nie cały plik).
- Kazde zadanie zmieniajace zachowanie dopisuje wpis do
  `docs/CHANGELOG.md`, sekcja `## [0.7.2] - Unreleased`.
- Testy offline na rekordach z surowych nagran
  (`tests/fixtures/gugik_skorowidz/real_2026_10_06/`, helpery
  `c14_records()`, `c14_fake()`, `FakeCampaignProvider` w
  `tests/test_manager_campaigns.py`). C14 = N-34-139-C-a-3-1: najnowszy
  84183 (2025-10-21) NIE, 83233 (2025-04-27) TAK; N-34-139-C-a-3-4:
  84183 TAK. Asercje na fakty (sciezki, inode, godla, pola wyniku),
  nie na cale brzmienie komunikatow.
- Numery linii = stan `develop` `fc4c176`; po wczesniejszych zadaniach
  przesuwaja sie — szukaj po symbolu.
- Dane na zywo (Task 6): poza repo i poza `/tmp`, jawne `--output`,
  katalog wskazuje uzytkownik (sciezki nie zapisuj w repo); CLI z korzenia
  repo.

## Review Focus

1. **Sciezka standardowa bez zmian** — przy kazdej kombinacji
   (`newest`/`all`, przedzial, `--full-sheet`) dowiazanie standardowe
   wskazuje ten sam lot co przed zmiana. Test: Task 3
   `test_full_sheet_flag_keeps_standard_link_on_newest`.
2. **Bez flagi zero dodatkowych pobran** — domyslne `newest` pobiera
   jeden lot, `resolve_campaigns` wolane raz (bez `all`). Test: Task 2
   `test_without_flag_partial_newest_downloads_one_flight`.
3. **`full_sheet/` nigdy nie wskazuje lotu NIE ani bez flagi** — test
   Task 2 `test_full_link_only_for_declared_full_flights`.
4. **Nigdy wstecz i `Info:`** — Task 2
   `test_full_link_never_moves_back_reports_outside_range`.
5. **`list_files()` bez duplikatow** — Task 1
   `test_list_files_excludes_full_sheet_tree`.

---

## Mapa plikow

| Plik | Odpowiedzialnosc | Zadanie |
|---|---|---|
| `kartograf/download/campaigns.py` | stala `FULL_SHEET_DIR` obok `CAMPAIGNS_DIR` | 1 |
| `kartograf/download/storage.py` | `get_full_sheet_path`, `list_files`, `delete` | 1 |
| `kartograf/download/links.py` | `ensure_standard_link` -> `ensure_link`, `write_standard_sidecar` -> `write_link_sidecar` | 1 |
| `kartograf/download/manager.py` | drugie dowiazanie, pola `SheetFetch`/`DownloadResult`, `full_sheet=`, dociaganie, `request.full_sheet` | 1-3 |
| `kartograf/cli/_parser.py`, `kartograf/cli/download_cmd.py` | flaga, straze, komunikaty | 4 |
| `docs/DECISIONS.md` (CRLF), `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `docs/SCOPE.md`, `README.md` (jesli opisuje uklad `kampanie/`) | ADR-033, erraty, opis | 5 |
| `docs/CHANGELOG.md`, `docs/PROGRESS.md` | wpisy | 1-6 |
| `tests/test_links.py` (albo plik testow `links.py` — znajdz po `ensure_standard_link`), `tests/test_storage*.py`, `tests/test_manager_campaigns.py`, `tests/test_cli.py` | testy | 1-4 |

---

### Task 1: Uklad `full_sheet/` w `FileStorage` i ogolne nazwy w `links.py`

**Files:** `kartograf/download/campaigns.py`, `kartograf/download/storage.py`,
`kartograf/download/links.py`, `kartograf/download/manager.py` (wolajacy),
testy wolajace stare nazwy.

- [ ] **Step 1: testy (czerwone)** — w pliku testow storage:
  - `test_full_sheet_path_mirrors_standard_hierarchy`: dla
    `FileStorage(tmp, resolution="1m")` i `N-34-139-C-a-3-1`
    `get_full_sheet_path(g, ".asc")` ==
    `tmp/nmt/pl_1992_1m_evrf2007/full_sheet/N-34/139/C/a/3/1/N-34-139-C-a-3-1.asc`
    (ta sama hierarchia co `get_path`, wstawiony `full_sheet/` po
    segmencie); PL-2000 (`{uklad}` w segmencie) — segment z ukladu godla.
  - `test_list_files_excludes_full_sheet_tree`: pliki w sciezce
    standardowej, w `kampanie/...` i w `full_sheet/...`;
    `list_files()` zwraca tylko standardowy, `list_files(campaigns=True)`
    tylko kampanii.
  - `test_delete_removes_standard_and_full_sheet_links`: oba pliki
    + sidecary istnieja, `delete(g)` -> oba usuniete, plik w `kampanie/`
    zostaje; `delete` zwraca `True` takze, gdy istnial tylko
    `full_sheet/`.
- [ ] **Step 2: implementacja.**
  - `campaigns.py`: `FULL_SHEET_DIR = "full_sheet"` przy `CAMPAIGNS_DIR`
    (komentarz: second link to the newest declared-full flight, spec 3).
  - `storage.py`: `get_full_sheet_path(godlo, ext=".asc")` — jak
    `get_campaign_path`, ale `<segment>/FULL_SHEET_DIR/<hierarchia>/`;
    wspolny prywatny helper hierarchii, jesli redukuje powtorzenie trzech
    metod (bez nowej abstrakcji ponad to). `list_files`: warunek
    `parts[:1]` — `campaigns=False` pomija `CAMPAIGNS_DIR` i
    `FULL_SHEET_DIR`; docstring. `delete`: usuwa sciezke standardowa
    i `full_sheet/` (kazda z sidecarem), zwraca `True`, gdy usunieto
    cokolwiek; docstring.
  - `links.py`: zmiana nazw `ensure_standard_link` -> `ensure_link`,
    `write_standard_sidecar` -> `write_link_sidecar` (docstringi: "link
    path" zamiast "standard path" tam, gdzie mowa o mechanice; docstring
    modulu wspomina drugie dowiazanie `full_sheet/`). Bez aliasow —
    migruj WSZYSTKICH wolajacych (`grep -rn "ensure_standard_link\|write_standard_sidecar" kartograf tests docs`):
    `manager.py` (`_fetch_campaigns`, `_note_standard_reuse`,
    `_local_newest`), testy, wzmianki w `docs/ARCHITECTURE.md`.
- [ ] **Step 3:** brama; commit
  `refactor(links): uklad full_sheet/ w FileStorage, ogolne nazwy dowiazan`.
  Bez wpisu CHANGELOG (zachowanie uzytkownika bez zmian poza
  `list_files`/`delete` — wpis trafia w Task 2 razem z drzewem).

### Task 2: Drugie dowiazanie w `_fetch_campaigns`

**Files:** `kartograf/download/manager.py`, `tests/test_manager_campaigns.py`,
`docs/CHANGELOG.md`.

**Interfejs (spec 5.3, 5.4):**
```python
@dataclass(frozen=True)
class SheetFetch:
    ...
    full_link: Path | None = None              # full_sheet/ path, when it exists after this call
    full_link_outside_range: Path | None = None  # campaign file it keeps pointing at (U15)
    no_full_flight: bool = False               # Task 3: index has no full flight in range

@dataclass
class DownloadResult:
    ...
    full_links: dict[str, Path] = field(default_factory=dict)
    full_link_outside_range: dict[str, Path] = field(default_factory=dict)
    without_full: list[str] = field(default_factory=list)  # Task 3
```
Docstringi pol w stylu istniejacych (`link_outside_range`). `_record`
przenosi pola jak `link_outside_range`.

- [ ] **Step 1: testy (czerwone)** — `FakeCampaignProvider` z rekordami C14:
  - `test_full_link_same_file_when_newest_full` (F1): -4, domyslnie ->
    `full_sheet/...` istnieje, `os.path.samefile` z plikiem kampanii 84183
    i ze sciezka standardowa; sidecar `full_sheet/` ma `extra.link`,
    `extra.link_target` wskazujacy 84183 i `extra.campaign.full_sheet` true;
    `result.full_links[g]` == sciezka.
  - `test_without_flag_partial_newest_downloads_one_flight` (F2): G
    domyslnie -> jeden plik kampanii (84183), brak `full_sheet/`,
    `full_links` bez G; provider wolany tylko z `campaigns="newest"`.
  - `test_campaigns_all_links_newest_full_flight` (F4): G,
    `campaigns="all"` -> `full_sheet/` -> 83233; standard -> 84183.
  - `test_full_link_only_for_declared_full_flights`: rekordy z
    `full_sheet` False i None (podmiana `dataclasses.replace` na rekordach
    C14) przy `all` -> brak `full_sheet/`.
  - `test_full_link_kept_when_run_has_no_full_candidate` (F6): po F4
    uruchomienie domyslne -> `full_sheet/` bez zmian (inode, mtime),
    `full_links[g]` = istniejaca sciezka.
  - `test_full_link_never_moves_back_reports_outside_range` (F8): po F4
    `campaigns="all", max_year=2024` (loty 78047 2023-09-05 TAK i 73021
    2019-04-18 TAK) -> `full_sheet/` nadal 83233,
    `result.full_link_outside_range[g]` = plik 83233.
  - `test_full_link_failure_fails_sheet`: `ensure_link` dla sciezki
    `full_sheet/` rzuca `OSError` (monkeypatch po sciezce) ->
    `DownloadError` z tekstem `dowiazanie` i sciezka `full_sheet`;
    sciezka standardowa ustawiona.
  - `test_local_newest_leaves_full_link_untouched` (F11): I-1 jak
    istniejacy test I-1 + istniejace `full_sheet/` -> bez zmian,
    `full_link` ustawione.
  - `test_force_refreshes_full_link`: `skip_existing=False` (sciezka
    `--force`) przepina `full_sheet/` na swiezo pobrany plik (nowy inode).
- [ ] **Step 2: implementacja** w `_fetch_campaigns` po dowiazaniu
  standardowym (przed blokiem `if errors or link_error`):
  ```python
  full = self._storage.get_full_sheet_path(godlo, self._default_ext)
  candidates = [rp for rp in local if rp[0].full_sheet is True]
  full_target: Path | None = None
  if candidates:
      ref_f, path_f = max(candidates, key=lambda rp: rp[0].sort_key)
      try:
          full_target = ensure_link(full, path_f, ref_f.sort_key,
                                    refresh=path_f in downloaded).target
      except OSError as e:
          full_link_error = e   # appended to problems like link_error
  else:
      full_target = linked_campaign(full)  # existing link stays untouched
  ```
  Rozszerzenie zrodla wynika z pliku kampanii (`campaign_extension`) —
  sciezka `full_sheet/` musi miec to samo rozszerzenie co cel (jak
  sciezka standardowa; sprawdz, jak dzis `std` obsluguje `.xyz` -> `.asc`
  i powtorz). `full_link_outside_range`: jak `link_outside_range`, gdy
  `_has_range` i `full_target` nie nalezy do `local`. `_local_newest`:
  `full_link=full if linked_campaign(full) else None`. `_note_reuse`
  dla sciezki `full_sheet/`, gdy dowiazanie bez zmian (jak
  `_note_standard_reuse`, jesli dotyczy `parent_requests`).
- [ ] **Step 3:** CHANGELOG `### Dodane`: drugie dowiazanie
  `<segment>/full_sheet/<hierarchia>/<godlo>.<ext>` do najnowszego
  lokalnego lotu oznaczonego w skorowidzu jako pelny (pelny = w granicach
  Polski), hardlink bez kosztu miejsca, `list_files()` je pomija,
  `delete()` je usuwa, `DownloadResult.full_links`/`full_link_outside_range`.
- [ ] **Step 4:** brama; commit
  `feat(campaigns): dowiazanie full_sheet/ do najnowszego pelnego lotu`.

### Task 3: `DownloadManager(full_sheet=True)` — dociaganie pelnego lotu

**Files:** `kartograf/download/manager.py`, `tests/test_manager_campaigns.py`,
`docs/CHANGELOG.md`.

- [ ] **Step 1: testy (czerwone):**
  - `test_full_sheet_flag_fetches_newest_full_flight` (F3): G,
    `full_sheet=True` -> pliki 84183 i 83233; standard -> 84183,
    `full_sheet/` -> 83233; `result.campaign_files[g]` ma oba; sidecar
    83233 `request.full_sheet is True`.
  - `test_full_sheet_flag_keeps_standard_link_on_newest`: jw. — sidecar
    standardowy `extra.link_target` na 84183.
  - `test_full_sheet_flag_noop_when_newest_full` (F13): -4 -> jeden plik,
    `resolve_campaigns` bez `campaigns="all"`.
  - `test_full_sheet_flag_without_full_flight_reports` (F7): rekordy C14
    z `full_sheet=False` we wszystkich -> jeden plik, brak `full_sheet/`,
    `result.without_full == [g]`; kod bez wyjatku.
  - `test_full_sheet_flag_respects_year_range`: G z `max_year=2024` —
    najnowszy w przedziale 78047 jest TAK, wiec flaga nic nie dociaga
    (jeden plik, `full_sheet/` -> 78047); wariant z rekordem 78047
    podmienionym na `full_sheet=False` -> dociagniety 73021, nie 83233.
  - `test_full_sheet_flag_with_all_adds_nothing`: `campaigns="all",
    full_sheet=True` -> te same pliki co `all`.
  - `test_full_sheet_requires_campaign_provider`: provider bez
    `supports_campaigns` + `full_sheet=True` -> `ValidationError` (jak
    `campaigns="all"`).
  - `test_full_sheet_full_flight_download_failure_fails_sheet`: `fail_urls`
    = URL 83233 -> `DownloadError` arkusza; standard -> 84183 istnieje.
- [ ] **Step 2: implementacja.**
  - `__init__(..., full_sheet: bool = False)`; walidacja providera razem
    z istniejaca dla `all`/przedzialu; `self._full_sheet`; property
    `full_sheet` jak `campaigns`.
  - `_fetch_campaigns`: po ustaleniu `chosen` (takze z `records` z fazy
    sprawdzania przedzialu), gdy `self._full_sheet`,
    `self._campaigns == "newest"` i `chosen[0].full_sheet is not True`:
    ```python
    pool = self._campaign_provider.resolve_campaigns(
        godlo, campaigns="all", min_year=self._min_year, max_year=self._max_year
    )
    extra_full = next((r for r in pool if r.full_sheet is True), None)
    if extra_full is None:
        no_full_flight = True
    else:
        chosen = [*chosen, extra_full]
    ```
    Reszta petli bez zmian (pobranie, sidecar, `local`); Task 2 dowiaze
    `full_sheet/`. Blad `resolve_campaigns` = wyjatek arkusza (jak przy
    `all`).
  - `_write_campaign_sidecar`: `request["full_sheet"] = True`, gdy flaga
    (wszystkie pliki zadania — `request` opisuje zadanie, nie lot).
  - `SheetFetch.no_full_flight` -> `DownloadResult.without_full`.
- [ ] **Step 3:** CHANGELOG `### Dodane`: `DownloadManager(full_sheet=True)`
  (CLI w Task 4) — najwyzej jeden dodatkowy lot na arkusz, tylko gdy
  najnowszy nie jest pelny; `DownloadResult.without_full`.
- [ ] **Step 4:** brama; commit
  `feat(campaigns): full_sheet=True dociaga najnowszy pelny lot`.

### Task 4: CLI `--full-sheet`, straze i komunikaty

**Files:** `kartograf/cli/_parser.py`, `kartograf/cli/download_cmd.py`,
`tests/test_cli.py`, `docs/CHANGELOG.md`.

- [ ] **Step 1: testy (czerwone)** (wzor: istniejace testy straz
  `--campaigns all`/`--min-year`):
  - `--full-sheet --product laz` -> `Error:` z `--full-sheet`, kod 1, bez
    sieci, katalog wyjscia nie powstal.
  - `--full-sheet --target-crs EPSG:2180` -> `Error:`, kod 1, przed
    siecia.
  - CZ bez PL + `--full-sheet` -> `Error:` (istniejacy komunikat
    `_reject_campaign_opts_without_pl` wymienia `--full-sheet`); PL+CZ
    pod `auto` -> `Info:`.
  - godlo G z `--full-sheet` (fake manager/provider jak w istniejacych
    testach CLI kampanii) -> `DownloadManager` dostaje `full_sheet=True`;
    stderr: jeden `Warning:` z G i `full_sheet/`.
  - G bez flagi -> `Warning:` z G i podpowiedzia `--full-sheet`.
  - F7 -> `Warning:` "brak pelnego lotu w skorowidzu" z G.
  - F8 -> `Info:` wymienia `full_sheet/` i plik kampanii.
  - skip (F5): drugi przebieg drukuje ten sam `Warning:`.
- [ ] **Step 2: implementacja.**
  - `_parser.py`: `--full-sheet` (`action="store_true"`), help: "Tylko PL
    NMT/NMPT/orto: gdy najnowszy lot arkusza nie jest pelny
    (calyArkuszWypelnionyTrescia), pobierz tez najnowszy pelny lot
    i dowiaz go w <segment>/full_sheet/; pelny = w granicach Polski; nie
    dziala z --target-crs ani z LAZ".
  - Straze: `--full-sheet` dla LAZ — w `_reject_laz_only_opts` sasiedzie
    (nowa funkcja `_reject_non_laz_opts_for_laz` albo rozszerzenie
    istniejacej, jesli naturalne; wolane w tym samym punkcie);
    `_reject_campaign_opts_with_target_crs` i
    `_reject_campaign_opts_without_pl` traktuja `--full-sheet` jak opcje
    kampanii (komunikaty wymieniaja flage).
  - `DownloadManager(..., full_sheet=args.full_sheet)` w torze PL.
  - Komunikat E13 (`_warn_partial_sheets`) dostaje fakty z wyniku:
    sygnatura `_warn_partial_sheets(paths, result)` (albo `full_links`,
    `without_full`, `flag`), jeden `Warning:` z trzema grupami (spec
    5.3): z `full_sheet/` (godla z `result.full_links`), "brak pelnego
    lotu w skorowidzu" (`result.without_full`), "pelny lot nie pobrany —
    uzyj --full-sheet" (reszta, tylko bez flagi). Tor pojedynczego godla
    (`_warn_sheet_sidecars([result])` przy `sheet`) przekazuje
    jednoelementowy `DownloadResult` z pol `SheetFetch`, jak dzis
    `_print_better_coverage`. Wycinek (`partial_sheets`) bez zmian.
  - `_print_link_outside_range`: dodatkowo `result.full_link_outside_range`
    (jedna linia na arkusz, z nazwa drzewa).
- [ ] **Step 3:** CHANGELOG `### Dodane`: flaga `--full-sheet`; `### Zmienione`:
  `Warning:` o niepelnej najnowszej kampanii wskazuje `full_sheet/` albo
  podpowiada `--full-sheet`.
- [ ] **Step 4:** brama; recznie `.venv/bin/kartograf download --help`
  (flaga widoczna); commit `feat(cli): --full-sheet i komunikat o pelnym locie`.

### Task 5: Dokumentacja

**Files:** `docs/DECISIONS.md` (CRLF), `docs/ARCHITECTURE.md`,
`docs/USAGE.md`, `docs/SCOPE.md`, `README.md` (jesli opisuje `kampanie/`),
`CLAUDE.md` (mapa dokumentacji: wiersz kampanii — wzmianka o
`full_sheet/`), `docs/CHANGELOG.md`.

- [ ] **Step 1:** ADR-033 "Drugie dowiazanie do najnowszego pelnego lotu
  (`full_sheet/`, `--full-sheet`)": kontekst (E13, pomiar 8 par),
  decyzje F-U1..F-U5, znaczenie TAK = pelne w granicach Polski (raport
  granic), alternatywy odrzucone (zmiana klucza ADR-028, mozaika,
  `--min-coverage`, dociaganie domyslne, `full_coverage/`), skutki.
  Wiersz w indeksie na poczatku pliku; errata ADR-030 (d) (drugie
  dowiazanie, `delete`/`list_files`), dopisek ADR-032 (flaga w modelu A:
  `--campaigns` = liczba lotow, `--full-sheet` = najwyzej jeden dodatkowy).
  CRLF zachowany.
- [ ] **Step 2:** ARCHITECTURE 3.3 (drzewo `full_sheet/` w ukladzie
  `data/`), 4.1 (akapit E13: znaczenie TAK, regula drugiego dowiazania,
  dociaganie, I-1, wycinki bez zmian); USAGE 4 (przyklad
  `--full-sheet`, opis drzewa, arkusze graniczne: nodata za granica jest
  normalne); SCOPE 2.12 + wiersz historii zmian; README, jesli dotyczy.
- [ ] **Step 3:** brama (dokumentacja nie zmienia testow, ale ruff/pytest
  i tak); commit `docs(campaigns): ADR-033 i opis full_sheet/`.

### Task 6: Weryfikacja na zywo, review, PROGRESS

- [ ] **Step 1:** katalog danych od uzytkownika; na zywo (CLI z korzenia
  repo, jawne `--output`):
  1. `N-34-139-C-a-3-4` -> `full_sheet/` = ten sam inode co standard
     (`stat -c %i`).
  2. `N-34-139-C-a-3-1` bez flagi -> 1 plik, `Warning:` z podpowiedzia.
  3. jw. z `--full-sheet` -> 84183 + 83233, `full_sheet/` -> 83233,
     `Warning:` z `full_sheet/`; podsumowanie 2 pliki.
  4. powtorka 3 -> Skipped, ten sam `Warning:`, bez pobrania.
  5. orto `M-34-90-C-b-4-4 --product orto --full-sheet` -> 84466 + 81437,
     `full_sheet/` -> 81437.
  6. `--full-sheet --product laz` i `--target-crs EPSG:2180` -> `Error:`.
  Raport `docs/research/2026-10-1x-full-sheet-link/raport.md` (bez
  sciezki katalogu danych).
- [ ] **Step 2:** review galezi (reviewer) wg "Review Focus"; poprawki
  osobnym commitem.
- [ ] **Step 3:** PROGRESS (sesja, backlog (c) [x] po merge), merge
  `--no-ff` do `develop` po decyzji uzytkownika.
