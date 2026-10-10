# Wybor roku danych (`--year`, `--min-year`, `--max-year`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wdrozyc w 0.7.2 spec
`docs/superpowers/specs/2026-10-09-year-range-selection-design.md`
(decyzje U1-U13): `--year` dla NMT/NMPT/orto/LAZ, nowa flaga `--max-year`,
zatrzymanie zadania przy konflikcie roku przed pobraniem (lista lat
i podpowiedz), wszystkie loty z przedzialu z gorna granica, pomiar
pokrycia lotow, nowe pola sidecara, odrzucenie flag roku dla wycinkow
i CZ.

**Architecture:** Jedna warstwa = jedno zadanie = jeden commit na galezi
`feat/year-range` (z `develop`). Czysta logika przedzialu (rok rekordu,
filtr, klasyfikacja, podpowiedzi, tresc bledu, rozwiazanie strategii)
w JEDNYM miejscu: `kartograf/download/campaigns.py`; provider skorowidza,
`DownloadManager`, LAZ i CLI tylko jej uzywaja. Nowy wyjatek
`YearRangeError(DownloadError)` niesie gotowy komunikat 6.2 — CLI drukuje
go istniejacym `except DownloadError` (bez osobnego formatowania). Faza
sprawdzania w `DownloadManager` wola provider RAZ na arkusz bez granic
(`campaigns="all"`, pelna lista, `campaigns_cache`) i filtruje sama, wiec
`extra.available_years` nie kosztuje drugiego zapytania.

**Tech Stack:** Python 3.12, `requests`, `rasterio`, `numpy`, `sqlite3`,
`pytest` (offline; `conftest` blokuje gniazda i podstawia
GetCapabilities).

**Spec:** `docs/superpowers/specs/2026-10-09-year-range-selection-design.md`
(stan 2026-10-10 z korektami przy planie, sekcja "Korekty specu" nizej).

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
  `Daldek <git@debever.pl>`, BEZ stopki `Co-Authored-By` (`CLAUDE.md`).
  Docstringi i komentarze po angielsku; dokumentacja po polsku bez
  diakrytykow (poza `USAGE.md`, ktory ma diakrytyki); komunikaty CLI
  polskie bez diakrytykow.
- Kazde zadanie zmieniajace zachowanie dopisuje wpis do `docs/CHANGELOG.md`,
  sekcja `## [0.7.2] - Unreleased` (`### Dodane` / `### Zmienione` z "Co
  zrobic"); tresci wpisow: spec 11.1-11.2. Zadania wylacznie z testami
  albo refaktorem — bez wpisu.
- Testy offline; fixtury z SUROWYCH odpowiedzi
  (`tests/fixtures/gugik_skorowidz/real_2026_10_06/`,
  `tests/fixtures/gugik_laz/real_2026_10_06/`); dane syntetyczne tylko
  tam, gdzie spec 10.2 na to pozwala (czysta funkcja, przypadek bez
  surowego odpowiednika). Testy nie przypinaja calego brzmienia
  komunikatow — asercje na fragment niosacy fakt (lata, godla, flagi,
  liczby); wyjatek: test CLI T5 (spec 10.1) sprawdza uklad 6.2
  (naglowek, linie arkuszy, linia podpowiedzi).
- Testy przypinajace USUWANE zachowanie (skan czesciowy, `--year` tylko
  LAZ, `--min-year` pomijany z `Warning:`) — usunac albo przepisac na
  nowa intencje, nie przypinac na nowo starego brzmienia.
- Numery linii w zadaniach = stan `feat/year-range` z 2026-10-10
  (`8028147`); po wczesniejszych zadaniach przesuwaja sie — szukaj po
  symbolu.
- Dane pobierane na zywo (Task 8): poza repo i poza `/tmp`, jawne
  `--output`, katalog wskazuje uzytkownik; CLI z korzenia repo.

## Review Focus

1. **U6: nic nie pobrane po konflikcie albo awarii sprawdzania** — lista
   z jednym arkuszem konfliktowym albo jednym bledem skorowidza nie
   zostawia ZADNEGO pliku w `kampanie/` ani dowiazania. Testy: Task 3
   `test_manager_year_2024_list_stops_before_any_download`,
   `test_manager_check_failure_aborts_whole_task`; LAZ Task 5
   `test_laz_year_2024_w2_conflict_lists_years`.
2. **U8: regula dowiazania bez zmian** — przy kilku lotach w przedziale
   dowiazanie wskazuje najnowszy lot w przedziale, takze gdy starszy ma
   wieksze pokrycie. Test: Task 4
   `test_manager_coverage_measured_only_when_newest_partial`.
3. **U13: samo `--min-year` = jeden lot** — zadnych dodatkowych pobran
   wobec 0.7.1. Test: Task 3 `test_manager_min_year_alone_downloads_newest_only`.
4. **Bez flag roku zero zmian** — `newest` nadal przez `record_cache`,
   fallback I-1 dziala. Test: Task 3
   `test_manager_without_range_unchanged_uses_record_cache`.
5. **P8 (LAZ)** — konflikt liczony z referencji pokryciem, nie po godle;
   obszar `w2` z `--year 2022` to konflikt (kafel 2022 pokrywa ok. 53 %
   obszaru), z `--year 2023` — pobranie. Testy: Task 5.

---

## Mapa plikow

| Plik | Odpowiedzialnosc | Zadanie |
|---|---|---|
| `kartograf/exceptions.py`, `kartograf/__init__.py` | `YearRangeError`, eksport | 1 |
| `kartograf/download/campaigns.py` | walidacja granic, strategia, rok rekordu, filtr, klasyfikacja, podpowiedzi, komunikaty; pomiar pokrycia | 1, 4 |
| `kartograf/providers/pl/skorowidz.py` | `resolve_campaigns(max_year=)`, bez skanu czesciowego, `available_years` | 2 |
| `kartograf/download/manager.py` | `max_year`, sentinel, faza sprawdzania, rekordy z fazy 1, sidecar, pomiar | 3, 4 |
| `kartograf/download/links.py` | dopisanie pol do sidecara sciezki standardowej | 4 |
| `kartograf/providers/pl/gugik_laz.py`, `kartograf/download/laz.py` | przedzial LAZ, referencja P8, sidecar | 5 |
| `kartograf/cli/_parser.py`, `kartograf/cli/download_cmd.py` | flagi, walidacja, straze, `Info:` 6.3 | 6 |
| `docs/DECISIONS.md` (CRLF), `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `docs/SCOPE.md` | ADR-032, erraty, opis | 7 |
| `docs/CHANGELOG.md`, `docs/PROGRESS.md` | wpisy | 1-8 |
| `tests/test_campaigns.py`, `tests/test_provider_campaigns.py`, `tests/test_skorowidz.py`, `tests/test_metadata_cache.py`, `tests/test_manager_campaigns.py`, `tests/test_laz_campaigns.py`, `tests/test_real_gugik_responses.py`, `tests/test_cli.py`, `tests/test_pl_cutout.py` | testy | 1-6 |

---

### Task 1: Logika przedzialu w `campaigns.py` i `YearRangeError`

**Files:**
- Modify: `kartograf/exceptions.py` (po `NoCoverageError`, `:92-116`)
- Modify: `kartograf/__init__.py` (import `:73-80`, `__all__` `:174-178`)
- Modify: `kartograf/download/campaigns.py` (`validate_campaign_args`
  `:68-83`; nowe funkcje obok)
- Modify: `kartograf/providers/pl/skorowidz.py` (`_record_year` `:390-394`
  -> import z `campaigns.py`; `_meets_min_year` `:397-402` zostaje do
  Task 2)
- Modify (wolajacy `validate_campaign_args`, nowa sygnatura):
  `kartograf/download/manager.py:353`, `kartograf/providers/pl/skorowidz.py:697`,
  `kartograf/providers/pl/gugik_laz.py:636`, `kartograf/cli/download_cmd.py:959`
- Test: `tests/test_campaigns.py` (`:241-248`)

- [ ] **Step 1: `YearRangeError`**

```python
class YearRangeError(DownloadError):
    """
    Data exists, but not in the requested year range — raised before any download.

    Attributes
    ----------
    sheets : dict[str, tuple[int, ...]]
        Sheet code (LAZ: tile sheet code) -> every year the source has for it
        (ascending); only the conflicting sheets.
    min_year, max_year : int or None
        The requested range (closed; ``None`` = open side).
    hints : tuple[str, ...]
        Flag suggestions (``--min-year 2024 (rok 2024 i nowsze)``), the same
        texts as the message's ``Podpowiedz:`` line; empty when none applies.
    """

    def __init__(
        self,
        message: str,
        *,
        sheets: Mapping[str, tuple[int, ...]],
        min_year: int | None,
        max_year: int | None,
        hints: tuple[str, ...] = (),
    ):
        super().__init__(message)
        self.sheets = dict(sheets)
        self.min_year = min_year
        self.max_year = max_year
        self.hints = tuple(hints)
```

Eksport w `kartograf/__init__.py` obok `NoCoverageError` (import
i `__all__`).

- [ ] **Step 2: Funkcje w `kartograf/download/campaigns.py`**

Sygnatury (wszystkie publiczne w module, poza `__all__` pakietu):

```python
def validate_campaign_args(
    campaigns: str | None, min_year: int | None, max_year: int | None
) -> None:
    """Strategy (None = unresolved sentinel, else CAMPAIGN_STRATEGIES), each
    bound an int (bool excluded) in 1900..2100, and min_year <= max_year."""

def resolve_campaign_strategy(campaigns: str | None, max_year: int | None) -> str:
    """Sentinel None -> "all" with an upper bound, else "newest" (U13);
    explicit "newest" with max_year -> ValidationError (P3a). Sheet products
    only — LAZ keeps an explicit "newest" with any range (Q8)."""

def record_year(record) -> int | None:
    """``aktualnoscRok``, else ``aktualnosc[:4]``; non-digit -> None (P2)."""

def in_year_range(year: int | None, min_year: int | None, max_year: int | None) -> bool:
    """Closed range, each side optional; an undetermined year meets no range."""

def year_range_label(min_year: int | None, max_year: int | None) -> str:
    """'z roku 2024' | 'od roku 2026' | 'do roku 2020' | 'z lat 2023-2024' (6.2)."""

def year_range_hints(
    conflicts: Mapping[str, Sequence[int]], min_year: int | None, max_year: int | None
) -> tuple[str, ...]:
    """Spec 6.2 'Podpowiedz' algorithm over the conflicting sheets."""

def year_range_error(
    conflicts: Mapping[str, Sequence[int]],
    min_year: int | None,
    max_year: int | None,
    *,
    total: int,
    unit: str = "arkuszy",
) -> YearRangeError:
    """YearRangeError with the 6.2 message: header, up to 20 lines
    '  <godlo>: dostepne roczniki ...', '  ... i N innych', 'Podpowiedz: ...'."""
```

Komunikaty walidacji (CLI zamienia nazwy parametrow na flagi, Task 6):
`min_year musi byc liczba calkowita 1900..2100, otrzymano X` (jak dzis),
to samo dla `max_year`; `min_year (2025) nie moze byc wiekszy niz
max_year (2023)`; strategia P3a: `campaigns="newest" wyklucza sie
z max_year — gorna granica roku pobiera wszystkie kampanie z przedzialu
(pomin campaigns)`.

`year_range_hints` wg 6.2 (L = `min_year`, U = `max_year`): dla kazdego
arkusza `newer` = lata > U (gdy U podane), `older` = lata < L (gdy L
podane). Grupa "nowsze" = arkusze z niepustym `newer`, grupa "starsze" =
z niepustym `older`.
- grupa nowsze obejmuje wszystkie konfliktowe: L podane -> `--min-year L
  (rok L i nowsze)`; L brak -> `--max-year U'`, U' = max po arkuszach z
  min(`newer`);
- grupa starsze obejmuje wszystkie: U podane -> `--max-year U (rok U
  i starsze)`; U brak -> `--min-year L'`, L' = min po arkuszach
  z max(`older`);
- obie grupy niepuste i kazdy arkusz jest w ktorejs: obie linie ("albo");
  T9 (przedzial) daje dwie linie z L i U;
- inaczej: brak podpowiedzi (tylko lista lat).

Uwaga dla T5/T9: arkusz z latami po obu stronach przedzialu jest w obu
grupach — podpowiedz `--min-year L` obejmuje go (ma nowsze), `--max-year
U` tez (ma starsze).

`skorowidz.py`: `_record_year` zastapiony importem `record_year`
(import lokalny jak przy `validate_campaign_args`, `:694-695`, albo
modulowy, jesli nie tworzy cyklu — sprawdz `python -c "import kartograf"`).

- [ ] **Step 3: Testy (`tests/test_campaigns.py`)**

Rozszerzyc parametryzacje `test_validate_campaign_args_rejects` o:
`max_year` poza zakresem, `max_year=True`, `min_year=2025, max_year=2023`;
`test_validate_campaign_args_accepts` o `(None, None, None)`,
`("all", 2023, 2024)`, `("newest", 2024, None)`.

Nowe (czyste funkcje; lata arkuszy c14 z fixtures `real_2026_10_06`,
spec 5: -1: 2019, 2023, 2025; -2 i -4: 2019, 2022, 2023, 2024, 2025,
2026; -3: 2019, 2025):

- `test_resolve_campaign_strategy`: `(None, None)` -> `newest`;
  `(None, 2025)` -> `all`; `("all", None)` -> `all`; `("newest", 2025)`
  -> `ValidationError`.
- `test_in_year_range_boundaries`: domkniete granice, `None` po obu
  stronach, `year=None` -> False.
- `test_record_year_prefers_aktualnosc_rok`: rekord z c14 (84183:
  `aktualnoscRok` 2025) i kopia rekordu z wyczyszczonym rokiem
  (`dataclasses.replace(..., raw={...})`) -> `None`.
- `test_year_range_hints_spec_cases` (parametryzacja T3, T4, T5, T6, T7,
  T9 z tabeli 5 specu): T3 -2 `[2018, 2018]` -> `("--min-year 2018 (rok
  2018 i nowsze)",)`; T4 -1 `[2026, 2026]` -> `--max-year 2026`; T5 -1, -3
  `[2024, 2024]` -> obie; T6 -1, -3 `[2026, 2026]` -> tylko `--max-year
  2026`; T7 -1, -3 `[2026, None]` -> `--min-year 2025`; T9 -3 `[2023,
  2024]` -> obie.
- `test_year_range_error_lists_years_and_truncates`: 2 arkusze z 4 ->
  naglowek `z roku 2024 dla 2 z 4 arkuszy`, linie z latami, `sheets`,
  `hints`; 25 syntetycznych godel -> 20 linii + `... i 5 innych`
  (spec 10.2), `sheets` pelne.

- [ ] **Step 4: Wolajacy** — `validate_campaign_args(campaigns, min_year,
  None)` w czterech miejscach (bez zmiany zachowania w tym zadaniu).

- [ ] **Step 5: Brama i commit** (bez CHANGELOG)

`refactor(campaigns): logika przedzialu lat i YearRangeError`

---

### Task 2: Provider skorowidza — przedzial, pelna lista, `available_years`

**Files:**
- Modify: `kartograf/providers/pl/skorowidz.py`: `_meets_min_year`
  (`:397-402`, usunac), `_covers` (`:405-407`, usunac),
  `_partial_scan_no_coverage` (`:417-423`, usunac), `layer_upper_year`
  (`:310-...`, usunac — jedynym uzytkownikiem jest skan czesciowy),
  `_resolve_all` (`:580-677`), `resolve_campaigns` (`:679-722`), nowa
  `available_years`
- Test: `tests/test_provider_campaigns.py`, `tests/test_skorowidz.py`
  (`:29`, `:650-661` `test_layer_upper_year` — usunac),
  `tests/test_metadata_cache.py` (`:1109` `_CAMP_PAYLOAD` bez
  `scanned_from`)

- [ ] **Step 1: `_resolve_all(parser, timeout, query)`** — bez parametru
  `min_year`: zawsze wszystkie warstwy; wpis `campaigns_cache`
  z `scanned_from` innym niz `None` = chybienie (jak wpis sprzed ADR-031);
  zapis bez klucza `scanned_from`. Docstring: P5.

- [ ] **Step 2: `resolve_campaigns`**

```python
def resolve_campaigns(
    self,
    godlo: str,
    *,
    campaigns: str | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    timeout: int | None = None,
) -> list[SkorowidzRecord]:
```

- `validate_campaign_args(campaigns, min_year, max_year)`;
  `strategy = resolve_campaign_strategy(campaigns, max_year)`.
- Bez granic: jak dzis (`newest` -> `_resolve_record`, `record_cache`;
  `all` -> `_resolve_all`).
- Z granica: `found = self._resolve_all(...)` (pusta lista ->
  `NoCoverageError` jak dzis, z `query.no_coverage`); `kept` = rekordy
  z `in_year_range(record_year(r), ...)`; `kept` puste ->
  `year_range_error({godlo: lata}, ..., total=1)`; `newest` ->
  `[kept[0]]` (lista jest malejaca po kluczu ADR-028, wiec `kept[0]` to
  najnowszy w przedziale, a dla `[L, inf)` najnowszy w ogole); `all` ->
  `kept`.

- [ ] **Step 3: `available_years(godlo, timeout=None) -> tuple[int, ...]`**
  — lata rekordow `_resolve_all` rosnaco, bez `None`; brak danych ->
  `NoCoverageError` z `_resolve_all`.

- [ ] **Step 4: Testy (`tests/test_provider_campaigns.py`)**

Usunac (opisuja usuwany skan czesciowy, spec 10.1):
`test_all_min_year_skips_cumulative_layer_below_bound` (`:158`),
`test_all_cache_partial_scan_*` (`:261`, `:387`),
`test_all_cached_partial_no_coverage_message_uses_current_bound`
(`:307`) i pozostale testy `scanned_from` w pliku (`:385-403`).

Przepisac na nowa intencje:
- `test_newest_min_year_older_newest_is_no_coverage_with_date` (`:114`)
  -> `test_newest_min_year_2026_c14_is_year_range_error`:
  `YearRangeError`, `sheets == {G: (2019, 2023, 2025)}`, `hints`
  z `--min-year 2025`; NIE `NoCoverageError`.
- `test_newest_min_year_does_not_skip_layers` (`:119`): asercja na
  `YearRangeError` i odpytanie wszystkich warstw.
- `test_all_min_year_2023_queries_2023iStarsze_and_filters_by_aktualnosc`
  (`:165`): czesc z cache (`min_year=2026` -> 0 kampanii) oczekuje
  `YearRangeError`, `s2.get.call_count == 0` zostaje.
- test `:185-195` (tekst "Brak kampanii ... od roku 2026"): `YearRangeError`
  z latami zamiast tekstu.
- `test_all_record_without_year_is_dropped_by_min_year` (`:443`),
  `test_newest_record_without_year_fails_min_year` (`:449`): wyjatek
  `YearRangeError` (lata bez `None`).

Nowe (spec 10.1, wiersze "provider"):
- `test_resolve_campaigns_year_2025_c14_returns_both_flights`: -1 ->
  ids `["84183", "83233"]`; -2 -> `["84183", "83233", "81468"]`.
- `test_resolve_campaigns_explicit_newest_with_max_year_is_validation_error`:
  `campaigns="newest", max_year=2025` -> `ValidationError` (zero zapytan);
  `campaigns="newest", min_year=2024` -> `["84183"]`;
  `campaigns=None, max_year=2025` -> lista dwoch.
- `test_newest_with_min_year_matches_newest_without_range`: dla
  -1..-4 c14 `resolve_campaigns(g, min_year=2019)[0].url ==
  resolve_campaigns(g)[0].url` (ta sama regula ADR-028 z listy i z
  `_resolve_record`).
- `test_resolve_campaigns_year_2024_c14_conflict_lists_years`: -1 ->
  `YearRangeError.sheets == {G: (2019, 2023, 2025)}`.
- `test_resolve_campaigns_max_year_2022_c14`: -1 -> `["73021"]`; -2 ->
  `["75162", "73021"]`.
- `test_resolve_campaigns_range_queries_all_layers_no_partial_scan`:
  `min_year=2026` -> `queried_layers` = 4 warstwy; wpis cache bez klucza
  `scanned_from`; recznie zapisany wpis `{"sources": [...],
  "scanned_from": 2024}` -> ponowne zapytanie (chybienie).
- `test_available_years_c14`: -2 -> `(2019, 2022, 2023, 2024, 2025, 2026)`.
- `test_orto_cir_year_2025_conflict_rgb_has_it` (T17): fixture orto
  `N-34-139-A-c-1-1`, wariant CIR -> `YearRangeError` z latami CIR
  (2011, 2014, 2017, 2022, 2024) — PRZED zapisem testu sprawdz lata
  w fixtures (`parse_skorowidz_records`), wpisz faktyczne.

`tests/test_metadata_cache.py:1109`: `_CAMP_PAYLOAD = {"sources": [{"url": "u"}]}`.

- [ ] **Step 5: CHANGELOG** (`### Zmienione`): pozycje spec 11.2
  o `--campaigns all --min-year` (pelna lista, wpisy ze skanu
  czesciowego odpytywane ponownie) i biblioteczne
  `resolve_campaigns(campaigns="newest", max_year=...)` = `ValidationError`.

- [ ] **Step 6: Brama i commit**

`feat(skorowidz): przedzial lat w resolve_campaigns, pelna lista kampanii`

---

### Task 3: `DownloadManager` — przedzial, faza sprawdzania, sidecar

**Files:**
- Modify: `kartograf/download/manager.py`: `CampaignProvider`
  (`:191-205`), `DownloadManager.__init__` (`:293-400`), wlasciwosci
  (`:412-420`), `download_sheet` (`:441-511`), `download_hierarchy`
  (`:513-589`), `download_sheets` (`:620-654`), `_fetch_sheet`
  (`:656-672`), `_fetch_campaigns` (`:700-863`),
  `_download_single_sheet_task` (`:906-936`), `_download_many`
  (`:990-1049`), `_write_campaign_sidecar` (`:1213-1240`)
- Test: `tests/test_manager_campaigns.py` (`FakeCampaignProvider`
  `:89-150`, `:678` do przepisania), `tests/test_pl_cutout.py:2501`
  (stub `resolve_campaigns` z `max_year`)

- [ ] **Step 1: Konstruktor i protokol**

- `DownloadManager(..., campaigns: str | None = None, min_year=None,
  max_year=None)`; `validate_campaign_args(campaigns, min_year,
  max_year)`; `self._campaigns = resolve_campaign_strategy(campaigns,
  max_year)`; straz providera bez kampanii: `campaigns == "all"` albo
  dowolna granica -> `ValidationError` (komunikat
  `(--campaigns/--min-year/--max-year/--year)`).
- Wlasciwosc `max_year`; `campaigns` zwraca strategie ROZWIAZANA.
- `CampaignProvider.resolve_campaigns(self, godlo, *, campaigns=None,
  min_year=None, max_year=None)`.
- `_has_range = min_year is not None or max_year is not None`.

- [ ] **Step 2: Faza sprawdzania**

```python
@dataclass(frozen=True)
class YearRangeCheck:
    """Result of the year-range check phase (spec 8.2)."""

    selected: dict[str, tuple[SkorowidzRecord, ...]]  # in range, newest first
    available: dict[str, tuple[int, ...]]  # every year of a selected sheet
    no_data: dict[str, NoCoverageError]
    conflicts: dict[str, tuple[int, ...]]
    failed: dict[str, DownloadError]

def check_year_range(self, godla: list[str]) -> YearRangeCheck:
    """Classify sheets against [min_year, max_year] before any download."""
```

- Tylko provider z kampaniami i z granica (inaczej `ValidationError`).
- Per arkusz `resolve_campaigns(godlo, campaigns="all")` (BEZ granic —
  pelna lista z `campaigns_cache`), filtr `in_year_range(record_year(r),
  ...)`; `NoCoverageError` -> `no_data`; inny `DownloadError` -> `failed`;
  `selected` = rekordy w przedziale (`all`) albo `(najnowszy,)`
  (`newest`). Rownolegle (`ThreadPoolExecutor`, `self._max_workers`)
  przy > 1 arkuszu i workers > 1.
- Publiczna (Hydrograf/QGIS), opis w docstringu.

- [ ] **Step 3: Przeplyw z przedzialem**

- `_download_many` (lista, hierarchia) i `download_sheet` (pojedynczy
  1:10000/PL-2000): przy `_has_range` najpierw `check_year_range`:
  `failed` niepuste -> `DownloadError` (P9, tresc 6.4: `nie udalo sie
  sprawdzic roku danych dla N z M arkuszy (blad skorowidza, nie brak
  danych): ... — ponow pobranie`); `conflicts` niepuste ->
  `year_range_error(conflicts, ..., total=len(godla))`. Oba PRZED
  pierwszym pobraniem; `last_result`/`last_sheet` zostaja `None`.
- Pojedynczy arkusz: `no_data` -> rzuca ten `NoCoverageError` (jak dzis).
- Lista: arkusz z `no_data` idzie do wyniku jako `no_coverage`
  (z `hints`) BEZ wywolania `_fetch_campaigns`; reszta pobierana.
- `_fetch_campaigns(godlo, skip_existing, on_download, records=None,
  available=None)`: `records` podane -> bez `resolve_campaigns`; I-1
  wylacznie bez przedzialu (`records is None` i `newest` i brak granic —
  dzisiejszy warunek `:761-766` rozszerzony o `max_year`).
- Docstringi `download_sheet`/`download_sheets`/`download_hierarchy`:
  `YearRangeError`/`DownloadError` przed pobraniem przy granicy.

- [ ] **Step 4: Sidecar kampanii (`_write_campaign_sidecar`)** —
  `request.campaigns` = strategia rozwiazana; `min_year`, `max_year` gdy
  podane; `year` gdy `min_year == max_year`; `extra.available_years`
  (lista int rosnaco) gdy przeplyw z przedzialem.

- [ ] **Step 5: Testy (`tests/test_manager_campaigns.py`)**

`FakeCampaignProvider.resolve_campaigns(self, godlo, *, campaigns=None,
min_year=None, max_year=None, timeout=None)`: zwraca rekordy
`self.records[resolve_campaign_strategy(campaigns, max_year)]` filtrowane
`in_year_range(record_year(r), ...)`; zapisuje `(godlo, campaigns,
min_year, max_year)` w `resolve_calls`; dodac slownik `errors: dict[godlo,
Exception]` (P9). Fake'i do listy c14: rekordy wszystkich 4 arkuszy
(`c14_records(g)`, jak `test_parallel_all_campaigns_writes_each_file_once`
`:691`).

Przepisac `test_min_year_newest_no_coverage_in_list_is_no_coverage_status`
(`:678`) -> `test_manager_min_year_alone_conflict_is_error_not_skip` (T7):
lista c14, `min_year=2026` -> `YearRangeError` z -1 i -3, `hints`
z `--min-year 2025`, zero pobran, `last_result is None`.

Nowe (spec 10.1, wiersze "manager"):
- `test_manager_year_2024_list_stops_before_any_download` (T5).
- `test_manager_year_2025_list_downloads_every_flight_links_newest` (T1):
  10 plikow w `kampanie/`, dowiazania na 84183, sidecar
  `request.campaigns == "all"`, `request.year == 2025`,
  `extra.available_years`.
- `test_manager_max_year_2022_list` (T8): 6 plikow; dowiazania -1/-3 ->
  73021, -2/-4 -> 75162.
- `test_manager_min_year_alone_downloads_newest_only` (T16): 4 pliki,
  -1/-3 -> 84183, -2/-4 -> 83998; `request.campaigns == "newest"`.
- `test_manager_explicit_all_with_range_same_as_default` (T15, T16a: 14
  plikow).
- `test_manager_explicit_newest_with_max_year_rejected` (T26/T26a).
- `test_manager_year_with_no_data_sheet_is_skipped` (T2): piaty arkusz
  bez rekordow -> `no_coverage`, reszta pobrana.
- `test_manager_check_failure_aborts_whole_task` (P9): `errors` dla
  jednego arkusza -> `DownloadError` z jego godlem, zero pobran.
- `test_manager_check_reads_full_list_once_per_sheet`: `resolve_calls`
  = jedno wywolanie na arkusz, `campaigns="all"` bez granic.
- `test_manager_without_range_unchanged_uses_record_cache`: realny
  `GugikProvider` (`c14_session`, `MetadataCache` w `tmp_path`) bez flag
  -> `get_record` ustawiony, `get_campaigns` pusty; I-1 (blad
  transportu przy istniejacym dowiazaniu) -> `unverified`.
- `test_manager_range_disables_local_fallback`: ten sam scenariusz I-1
  z `min_year=2024` -> `DownloadError`.

`tests/test_pl_cutout.py:2501`: stub z `max_year=None`.

- [ ] **Step 6: CHANGELOG** (`### Dodane`: biblioteka
  `DownloadManager(max_year=)`, `check_year_range`, `YearRangeError`;
  `### Zmienione`: `--min-year` zatrzymuje zadanie zamiast pomijac
  arkusz; `download_sheets`/`download_hierarchy` z granica rzucaja przed
  pobraniem; domyslne `campaigns=None`) — tresci wg spec 11.

- [ ] **Step 7: Brama i commit**

`feat(manager): przedzial lat z faza sprawdzania przed pobraniem`

---

### Task 4: Pomiar pokrycia lotow (P4, U10)

**Files:**
- Modify: `kartograf/download/campaigns.py` (nowa `measure_coverage`;
  docstring modulu: dodatkowe IO)
- Modify: `kartograf/download/links.py` (nowa `update_sidecar_extra`)
- Modify: `kartograf/download/manager.py` (`SheetFetch`, `DownloadResult`,
  `_record`, `_fetch_campaigns`)
- Test: `tests/test_campaigns.py`, `tests/test_manager_campaigns.py`

- [ ] **Step 1: `measure_coverage(path: Path, ext: str) -> float | None`**

- `.asc`: naglowek `read_asc_header` (`NODATA_value`, brak = `-9999`);
  dane czytane strumieniowo (blokami, np. 8 MiB, z przeniesieniem
  niepelnej liczby miedzy blokami), liczone komorki `!= nodata` (po
  `float`); wynik `valid / (ncols * nrows)`, zaokraglony do 4 miejsc.
  Liczba komorek inna niz `ncols * nrows` -> `DownloadError`.
- `.tif`: `rasterio`; bez `nodata` i bez kanalu alfa -> `None`; inaczej
  `read_masks(1, window=...)` po `block_windows(1)`, udzial niezerowych.
- Blad odczytu -> `DownloadError` (manager zamienia na
  `logger.warning`, spec 8.2 faza 4).

- [ ] **Step 2: `update_sidecar_extra(data_path, updates: dict) -> None`**
  w `links.py` — odczyt `<plik>.meta.json`, `extra.update(updates)`,
  zapis tmp + `os.replace` (wzorzec `_note_reuse`, manager `:1257-1281`);
  best-effort (blad = `logger.warning`); brak sidecara = nic.

- [ ] **Step 3: Faza pomiaru w `_fetch_campaigns`** (po dowiazaniu, tylko
  `self._campaigns == "all"` z przedzialem):
  - warunek U10: `len(local) > 1` i lot dowiazania ma
    `full_sheet is not True`;
  - dla kazdego lotu: `extra.coverage` z sidecara kampanii, a gdy brak —
    `measure_coverage` + `update_sidecar_extra(path, {"coverage": c})`
    (`None` = pole nie zapisywane);
  - sidecar sciezki standardowej (`update_sidecar_extra(std, ...)`):
    `extra.coverage` lotu dowiazania (gdy zmierzone), `extra.flights`
    (wszystkie lokalne loty z przedzialu malejaco po `sort_key`:
    `{"id", "date", "full_sheet", "coverage"?}`), `extra.better_coverage`
    = `id` lotu o najwiekszym pokryciu, gdy wieksze niz lot dowiazania;
  - bez warunku U10 (jeden lot albo najnowszy pelny): `extra.flights`
    bez `coverage`, bez pomiaru i bez `better_coverage`;
  - `SheetFetch.better_coverage: str | None`,
    `DownloadResult.better_coverage: dict[str, str]` (wypelniane
    w `_record`).

- [ ] **Step 4: Testy**

`tests/test_campaigns.py`:
- `test_coverage_of_asc_counts_nodata`: ASC 3x2 z `NODATA_value -1`
  (4 z 6 waznych) -> `0.6667`; bez `NODATA_value` z `-9999` -> wynik
  wg `-9999`; wartosc rozbita granica bloku (mala wielkosc bloku
  parametrem testowym albo monkeypatch stalej) -> ten sam wynik.
- `test_coverage_of_tif_without_nodata_is_none` i z `nodata` (GeoTIFF
  zapisany `rasterio` w `tmp_path`).

`tests/test_manager_campaigns.py` (zawartosc ASC per URL przez
`FakeCampaignProvider(contents=...)`, rama arkusza jak `asc_for`, rozny
udzial `-9999` w danych):
- `test_manager_coverage_measured_only_when_newest_partial` (T14 vs
  T27): -1 `year=2025`: obie kampanie z `extra.coverage`, sidecar
  standardowy `extra.better_coverage == "83233"`, `extra.flights` z dwoma
  wpisami, dowiazanie nadal na 84183; `last_result.better_coverage ==
  {G: "83233"}`; -4 `year=2025` (84183 pelny): brak `extra.coverage`
  i `better_coverage`, `extra.flights` bez `coverage`.
- `test_manager_coverage_newest_has_more_data_no_info`: najnowszy
  niepelny z wiekszym pokryciem -> `extra.flights` z pokryciem, bez
  `better_coverage`.
- `test_manager_single_flight_in_range_no_measurement` (T28).
- `test_manager_coverage_read_from_sidecar_on_rerun`: drugie
  uruchomienie nie mierzy ponownie (`measure_coverage` podmieniony
  licznikiem).
- `test_manager_min_year_alone_no_measurement`: `newest` z `min_year`
  -> brak `extra.flights`.

- [ ] **Step 5: CHANGELOG** (`### Dodane`: pokrycie lotu, pola
  sidecara — spec 11.1).

- [ ] **Step 6: Brama i commit**

`feat(manager): pokrycie lotow w przedziale lat i lot o wiekszym pokryciu`

---

### Task 5: LAZ — przedzial i referencja pokrycia (P8)

**Files:**
- Modify: `kartograf/providers/pl/gugik_laz.py`: `select_tiles`
  (`:568-674`), `discover_tiles` (`:542-566`)
- Modify: `kartograf/download/laz.py`: `write_laz_sidecar` (`:85-142`),
  `run_laz_download` (`:145-233`), `download_laz_area` (`:236-334`)
- Test: `tests/test_laz_campaigns.py`, `tests/test_real_gugik_responses.py`
  (klasa `TestLazDiscoveryOnRealWfs` `:588`)

- [ ] **Step 1: `select_tiles(bbox, year=None, min_density=None, ...,
  *, campaigns="newest", min_year=None, max_year=None)`**

- `year` z `min_year`/`max_year` -> `ValidationError` (`year wyklucza sie
  z min_year/max_year`); `validate_campaign_args(campaigns, lo, hi)`
  z `lo = hi = year`, gdy `year` podany. LAZ: domyslnie `newest` (bez
  sentinela — LAZ nie ma `kampanie/`, Q8); jawne `newest` z gorna
  granica dozwolone.
- Roczniki uslugi: przedzial bez wspolnego rocznika -> `DownloadError`
  (T23; `year` — tekst jak dzis `:653-657`, przedzial — `przedzial
  2010-2017 nie ma rocznika w usludze EVRF2007 (dostepne: ...)`).
- Bez przedzialu: jak dzis.
- Z przedzialem: zapytania do WSZYSTKICH rocznikow uslugi; filtr
  `min_density`; `R = select_newest_cover(wszystkie)`; w przedziale `C =
  select_newest_cover(...)` (`newest`) albo `select_all_intersecting`
  (`all`); dla kazdego kafla `r` z `R.tiles` o roku spoza przedzialu:
  `part = clip(r, obszar)`, kawalki niepokryte przez pelne kafle `C`
  (`full_sheet is not False`, z `footprint`, powiekszone o
  `tolerance_m`; ten sam godlo = pokrycie, jak w `select_newest_cover`)
  -> konflikt `{r.godlo: lata}`, lata = `year` wszystkich kafli
  (dowolny rok), ktorych obszar przecina niepokryty kawalek ze znaczaca
  powierzchnia (`_significant`). Konflikty -> `year_range_error(...,
  total=len(R.tiles), unit="kafli obszaru")` z naglowkiem LAZ (6.4: `brak
  kafli LAZ ...`; parametr `unit`/prefiks w `year_range_error`);
  inaczej zwrot `C`.
- Wyodrebnic sprawdzenie pokrycia z `select_newest_cover` do funkcji
  pomocniczej (np. `_uncovered_parts(tile, cover_tiles, area,
  tolerance_m)`), uzywanej w obu miejscach — bez drugiej kopii reguly.

- [ ] **Step 2: `download/laz.py`** — `max_year` w `download_laz_area`
  (do `select_tiles` i `run_laz_download`), `run_laz_download`,
  `write_laz_sidecar`: `request.min_year`/`max_year` gdy podane,
  `request.year` gdy `year` podany albo `min_year == max_year`;
  `extra.acquisition_date` (`tile.date`) i `extra.full_sheet`
  (`tile.full_sheet`) zawsze, gdy znane.

- [ ] **Step 3: Testy**

Fakty z fixtures `w2` (EVRF2007, zmierzone 2026-10-10): kafle 2025
`N-34-139-A-c-1-1-3-4` (PL-1992, pelny), 2023 ten sam godlo (pelny),
2022 `7.173.21.06.2` (PL-2000:S7, pelny) — rama 2022 pokrywa ok. 53 %
obszaru `W2_BBOX`; warstwa 2024 istnieje i jest pusta.

`tests/test_laz_campaigns.py`:
- usunac `test_min_year_skips_older_year_layers` (`:74`) — zastapic
  `test_range_queries_every_service_year` (`min_year=2025` ->
  `feature_years` = wszystkie roczniki uslugi).
- `test_year_and_min_year_are_exclusive` (`:105`) ->
  `test_laz_year_and_range_exclusive`: `year` + `min_year`, `year` +
  `max_year`, `min_year > max_year` -> `ValidationError`, zero zapytan.
- `test_sidecar_request_records_campaigns_and_min_year` (`:153`)
  rozszerzyc -> `test_laz_sidecar_acquisition_date_and_max_year`.

`tests/test_real_gugik_responses.py` (`TestLazDiscoveryOnRealWfs`):
- `test_laz_year_2023_w2_covers_reference` (T21): kafel 2023 wybrany
  (`test_c13_year_2023_returns_the_single_older_tile` `:614` — asercja
  `feature_years == ["2023"]` zmienia sie na wszystkie roczniki; wynik
  kafli bez zmian).
- `test_laz_year_2022_w2_partial_cover_conflict` (T21a):
  `YearRangeError.sheets == {"N-34-139-A-c-1-1-3-4": (2023, 2025)}` —
  PRZED zapisem asercji sprawdz lata z faktycznych przeciec (rama 2022
  nie przecina niepokrytego kawalka ze znaczaca powierzchnia),
  wpisz faktyczne; podpowiedz `--min-year 2022`.
- `test_laz_year_2024_w2_conflict_lists_years` (T22): `sheets` z latami
  przecinajacymi caly obszar (2022, 2023, 2025 — sprawdz jak wyzej);
  podpowiedzi obie.
- `test_laz_range_without_service_year` (T23): `min_year=2010,
  max_year=2017` na EVRF2007 -> `DownloadError`, bez GetFeature.

- [ ] **Step 4: CHANGELOG** (`### Zmienione`: LAZ `--year`/`--min-year`
  — spec 11.2; `### Dodane`: `max_year`, pola sidecara LAZ).

- [ ] **Step 5: Brama i commit**

`feat(laz): przedzial lat z referencja pokrycia (P8)`

---

### Task 6: CLI — flagi, walidacja, straze, komunikaty

**Files:**
- Modify: `kartograf/cli/_parser.py` (`--year` `:263-270`, `--campaigns`
  `:271-278`, `--min-year` `:279-285`, nowy `--max-year`)
- Modify: `kartograf/cli/download_cmd.py`: `_campaign_opts` (`:230-232`),
  `_reject_laz_only_opts` (`:265-306`),
  `_reject_campaign_opts_without_pl` (`:309-339`),
  `_reject_campaign_opts_with_target_crs` (`:342-369`), `cmd_download`
  (`:956-967`, single sheet `:1099-1121`), `_finish_pl_sheets`
  (`:1240-1327`), `_download_pl_sheet_list` (`:1686-1751`),
  `_cmd_download_laz` (`:1829-1952`), `_print_laz_superseded`
  (`:1810-1827`)
- Test: `tests/test_cli.py` (`TestCampaignOptions` `:6708`,
  `test_laz_year_and_min_year_exclusive` `:6759`,
  `test_target_crs_with_min_year_rejected` `:6835`, `TestLazOnlyOptions`
  `:7833-8070`)

- [ ] **Step 1: Parser** — teksty pomocy wg spec 6.1; `--campaigns`
  `default=None`; `--max-year` (`type=int`, `metavar="YYYY"`).

- [ ] **Step 2: `_campaign_opts(args) -> tuple[str | None, int | None,
  int | None]`** — `(campaigns, min_year, max_year)`, `--year Y` ->
  `min_year = max_year = Y` (po walidacji T10). Wszystkie wolajace
  (`:323`, `:354`, `:957`, `:1706`, `:1849`) przechodza na nowa krotke.

- [ ] **Step 3: `cmd_download` przed siecia** (w miejscu `:956-967`):
  T10/T11 (`--year` z `--min-year`/`--max-year`), T12/T13 przez
  `validate_campaign_args` (zamiana `min_year`/`max_year` na flagi
  w komunikacie), T26 przez `resolve_campaign_strategy` dla produktow
  arkuszowych (komunikat z flagami: `--campaigns newest wyklucza sie
  z --year/--max-year ...`); strategia rozwiazana trafia do
  `DownloadManager` i `_finish_pl_sheets`/podsumowania pojedynczego
  godla. LAZ: bez T26 (Q8).

- [ ] **Step 4: Straze**
  - `_reject_laz_only_opts`: tylko `--min-density` (docstring bez
    zapowiedzi 0.7.2); `--year` dla CZ obsluguje straz CZ ponizej.
  - `_reject_campaign_opts_without_pl`: dowolna flaga roku albo
    strategia `all`; teksty T18/T19 z wyliczeniem
    `--campaigns all/--min-year/--max-year/--year`.
  - `_reject_campaign_opts_with_target_crs`: `--campaigns all` jak dzis;
    kazda flaga roku -> `Error: <flaga> nie dziala z --target-crs —
    wycinek sklada najnowsze kampanie, nazwa wycinka nie niesie roku`
    (T20; nazwa flagi wg tej, ktora podano).
  - `_cmd_download_laz`: usunac lokalna kontrole `--min-year i --year`
    (`:1850-1852`, zastapiona T10); przekazac `min_year`/`max_year`
    (zmapowany `--year`) do `select_tiles` i `run_laz_download`.
  - `_print_laz_superseded`: dopisek "inny rocznik:
    --year/--min-year/--max-year" (spec 6.4).

- [ ] **Step 5: `Info:` 6.3** — `_print_better_coverage(result, paths)`
  wolane w `_finish_pl_sheets` i w torze pojedynczego godla
  (`SheetFetch.better_coverage`): arkusze z `result.better_coverage`,
  szczegoly (katalog lotu, pelny/niepelny, procent z przecinkiem)
  z `extra.flights` sidecara sciezki standardowej (best-effort, jak
  `_warn_partial_sheets`); stderr takze z `-q`; do 10 arkuszy, dalej
  `... i N innych`.

- [ ] **Step 6: Testy (`tests/test_cli.py`)**

Usunac/przepisac: `_LAZ_ONLY_YEAR_ERROR`,
`_LAZ_ONLY_YEAR_WITH_MIN_YEAR_ERROR` i przypadki `--year` w
`TestLazOnlyOptions` (`:7833-8070`) — zostaja przypadki `--min-density`;
przypadki CZ z `--year` przechodza na nowy tekst T18.
`test_laz_year_and_min_year_exclusive` (`:6759`) -> T10 dla LAZ i NMT.
`test_target_crs_with_min_year_rejected` (`:6835`) -> parametryzacja
trzech flag (`test_cli_year_flags_rejected_with_target_crs`).

Nowe (spec 10.1, wiersze "CLI"/"parser"): `test_parser_max_year_and_year_for_nmt`,
`test_cli_year_conflicts_with_min_max` (T10-T13, `GugikProvider` nie
tworzony), `test_cli_explicit_newest_with_year_rejected` (T26, T26a,
`--campaigns all --year`), `test_cli_year_cz_godlo_rejected` /
`test_cli_year_pl_cz_info` (T18/T19), `test_cli_year_nmt_list_error_message_and_hints`
(T5: uklad 6.2, kod 1, `MetadataCache` zamkniety),
`test_cli_year_info_better_coverage` (T14: tekst 6.3 na stderr z `-q`,
kod 0), `test_cli_year_passed_to_manager_for_nmt_nmpt_orto`
(`min_year == max_year == 2025`, `campaigns == "all"` w
`DownloadManager`), `test_cli_min_year_alone_keeps_newest`
(`campaigns == "newest"`), `test_cli_laz_year_mapped_to_range`.

- [ ] **Step 7: CHANGELOG** (`### Dodane`: `--max-year`, `--year` dla
  NMT/NMPT/orto; `### Zmienione`: `--year`/`--max-year` = wszystkie
  kampanie z przedzialu, jawne `newest` = `Error:`, `--year`/`--max-year`
  z `--target-crs` = `Error:` — spec 11.1-11.2).

- [ ] **Step 8: Brama i commit**

`feat(cli): wybor roku --year/--min-year/--max-year dla NMT, NMPT, orto i LAZ`

---

### Task 7: Dokumentacja i ADR-032

**Files:**
- Modify: `docs/DECISIONS.md` (CRLF — zachowac; sprawdz `file
  docs/DECISIONS.md` przed i po)
- Modify: `docs/ARCHITECTURE.md` (3.2 pola sidecara; 4.1 kampanie
  i przedzial; 4.3 wycinek; 4.6 `--country auto`; 4.7 LAZ)
- Modify: `docs/USAGE.md` (1.1 — usunac zapowiedz "w 0.7.2", przyklady
  `--year`/`--min-year`/`--max-year`; 4 kampanie)
- Modify: `docs/SCOPE.md` 2 (ograniczenia: CZ bez roku, wycinki bez roku)

- [ ] **Step 1: ADR-032** "Wybor roku danych: przedzial lat, zatrzymanie
  przy konflikcie" — tresc: spec sekcje 2-3, 5-9 (decyzje U1-U13, P1-P10,
  korekty z tego planu); indeks na poczatku pliku.
- [ ] **Step 2: Erraty** — ADR-030 (f) (stop zamiast pominiecia,
  `--max-year`), (g)/[Q5] (skan czesciowy usuniety), (h)
  (`campaigns_cache` dla `newest` z przedzialem), (i) (nowe pola),
  (j)/[Q2] (odrzucenie rozszerzone na `--year`/`--max-year`); ADR-029
  errata (`--year` == przedzial, referencja pokrycia P8).
- [ ] **Step 3: ARCHITECTURE, USAGE, SCOPE** wg listy wyzej; `kartograf
  download --help` zgodny z opisem USAGE (porownac recznie).
- [ ] **Step 4: Brama i commit**

`docs: ADR-032 wybor roku danych, erraty ADR-029/ADR-030, opis`

---

### Task 8: Zamkniecie

- [ ] **Step 1: Fixtury z 10.3 specu** (test `live` nagrywajacy, potem
  kopia surowych odpowiedzi do `tests/fixtures/...` wg README fixtures):
  orto — dwa loty RGB o tej samej wielkosci piksela w jednym roku; LAZ —
  obszar `w3` z czesciowym konfliktem; LAZ — dwie dostawy NIE tego
  samego arkusza w 2025 (Wroclaw); NMT PL-2000 z dwoma lotami w roku.
  Dla kazdej nagranej fixtury test offline z tabeli 10.3. Usluga
  niedostepna albo brak przypadku w danych = wpis w PROGRESS (co
  sprawdzono, z jakim wynikiem), bez testu syntetycznego w zastepstwie.
- [ ] **Step 2: Przebieg na zywo** (katalog od uzytkownika, jawne
  `--output`): T1 (`--bbox` c14 `--year 2025`: 10 plikow kampanii,
  `Info:` 6.3 jesli pokrycie sie rozni), T5 (`--year 2024`: `Error:`,
  nic nie pobrane), T16 (`--min-year 2024`: 4 pliki), T20 (wycinek
  z `--year`: `Error:`), T22 (LAZ `w2 --year 2024`: `Error:`), orto
  `--year` na arkuszu miejskim. Raport
  `docs/research/2026-10-XX-year-range/raport.md`.
- [ ] **Step 3: Review galezi** (reviewer), poprawki.
- [ ] **Step 4: PROGRESS** — backlog "Do 0.7.2" (b) odhaczony; zdania
  "Otwarte decyzje przed wydaniem 0.7.2" o wyborze roku zamkniete;
  wpis sesji.
- [ ] **Step 5: Merge** `--no-ff` `feat/year-range` -> `develop` (po
  zgodzie uzytkownika), usuniecie galezi.

---

## Korekty specu przy planie (2026-10-10)

Wprowadzone w specu w tym samym commicie co plan:

- **T21 (LAZ):** spec zakladal, ze kafel 2022 `7.173.21.06.2` pokrywa
  obszar `w2`. Pomiar na fixtures: rama 2022 obejmuje ok. 53 % obszaru
  (niepokryty kawalek 28 198 m2 z 60 000 m2), wiec `--year 2022` to wg
  P8 konflikt (T21a). Przypadek "rocznik pokrywa referencje" ilustruje
  `--year 2023` (ten sam godlo = ta sama rama).
- **Sekcja 7, `extra.parent_requests[].min_year/...`:** spec pisal "jak
  dzis `min_year`", ale `parent_request` (`_build_parent_request`) nie
  niesie zadnej flagi roku — wiersz usuniety; pola roku sa w `request`
  sidecara kampanii.
- **P3a / 8.2:** regula "jawne `newest` z gorna granica = blad" jest
  w `resolve_campaign_strategy`, nie w `validate_campaign_args` — ta
  druga sluzy tez LAZ, gdzie jawne `newest` z gorna granica jest
  dozwolone (Q8). LAZ zachowuje domyslne `campaigns="newest"` zamiast
  sentinela (zachowanie identyczne ze specem 8.5).

## Korekta po Task 8 (2026-10-10)

- **T21a nieprawdziwy:** fixtures `real_2026_10_06/w2_*` byly nagrane dla
  okna C13 `637400,487000,637450,487050`, a testy odtwarzaly je dla
  `W2_BBOX` (`637200,486900,637500,487100`). Przebieg na zywo `--year
  2022` pobral dwa kafle (`7.173.21.06.1`, `.06.2`); nagranie dla
  `W2_BBOX` (`tests/fixtures/gugik_laz/real_2026_10_10/`) to potwierdza.
  Kod zgodny z P8; poprawione testy, ADR-032, ARCHITECTURE 4.7 i spec
  (T21a, T25). Pomocniki `laz_session` sprawdzaja teraz okno `BBOX`.
